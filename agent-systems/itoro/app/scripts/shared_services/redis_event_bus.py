"""
🌙 Anarcho Capital's Redis Event Bus
Event-driven communication system for inter-agent messaging
Built with love by Anarcho Capital 🚀
"""

import redis
import json
import threading
import time
import logging
from typing import Callable, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class RedisEventBus:
    """
    Redis-based event bus for inter-agent communication.
    Enables publish/subscribe messaging between agents.
    """

    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0,
                 password: Optional[str] = None, max_connections: int = 10):
        """
        Initialize Redis event bus

        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (optional)
            max_connections: Maximum connection pool size
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password

        # Initialize connection pool for better performance
        self.redis_pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            max_connections=max_connections,
            decode_responses=True
        )

        # Create main client
        self.redis_client = redis.Redis(connection_pool=self.redis_pool)

        # Subscriber management
        self.subscribers: Dict[str, list] = {}
        self.running = False
        self.listener_thread: Optional[threading.Thread] = None

        # Health tracking
        self.last_health_check = 0
        self.health_check_interval = 30  # seconds
        self.is_healthy = False

        logger.info(f"🔄 Redis Event Bus initialized (redis://{host}:{port}/{db})")

    def publish(self, event_type: str, data: Dict[str, Any], channel: Optional[str] = None) -> bool:
        """
        Publish an event to a channel

        Args:
            event_type: Type of event (e.g., 'market_alert', 'trading_signal')
            data: Event data dictionary
            channel: Optional specific channel, defaults to event_type

        Returns:
            bool: Success status
        """
        try:
            channel = channel or event_type

            # Create event envelope
            event_envelope = {
                'event_type': event_type,
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'publisher': 'redis_event_bus',
                'channel': channel
            }

            # Publish to Redis
            message = json.dumps(event_envelope)
            result = self.redis_client.publish(channel, message)

            if result > 0:
                logger.debug(f"📤 Published {event_type} to channel {channel}")
                return True
            else:
                logger.warning(f"⚠️ No subscribers for {event_type} on channel {channel}")
                return True  # Still successful, just no subscribers

        except Exception as e:
            logger.error(f"❌ Failed to publish {event_type}: {e}")
            return False

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None],
                  channel: Optional[str] = None) -> bool:
        """
        Subscribe to an event type

        Args:
            event_type: Event type to subscribe to
            callback: Function to call when event is received
            channel: Optional specific channel, defaults to event_type

        Returns:
            bool: Success status
        """
        try:
            channel = channel or event_type

            if channel not in self.subscribers:
                self.subscribers[channel] = []

            self.subscribers[channel].append(callback)

            # Start listener if not already running
            if not self.running:
                self._start_listener()

            logger.info(f"📡 Subscribed to {event_type} on channel {channel}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to subscribe to {event_type}: {e}")
            return False

    def unsubscribe(self, event_type: str, callback: Optional[Callable] = None,
                   channel: Optional[str] = None) -> bool:
        """
        Unsubscribe from an event type

        Args:
            event_type: Event type to unsubscribe from
            callback: Specific callback to remove (None removes all for this event type)
            channel: Optional specific channel

        Returns:
            bool: Success status
        """
        try:
            channel = channel or event_type

            if channel not in self.subscribers:
                return True

            if callback is None:
                # Remove all subscribers for this channel
                del self.subscribers[channel]
            else:
                # Remove specific callback
                if callback in self.subscribers[channel]:
                    self.subscribers[channel].remove(callback)
                    if not self.subscribers[channel]:
                        del self.subscribers[channel]

            logger.info(f"🔇 Unsubscribed from {event_type} on channel {channel}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to unsubscribe from {event_type}: {e}")
            return False

    def _start_listener(self):
        """Start the Redis pub/sub listener thread"""
        if self.running:
            return

        self.running = True
        self.listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self.listener_thread.start()
        logger.info("🎧 Redis event listener started")

    def _listener_loop(self):
        """Main listener loop for receiving events"""
        while self.running:
            try:
                # Create new pub/sub instance for this thread
                pubsub = self.redis_client.pubsub()
                channels = list(self.subscribers.keys())

                if not channels:
                    time.sleep(1)  # Wait for subscriptions
                    continue

                # Subscribe to all channels
                pubsub.subscribe(channels)
                logger.debug(f"🎧 Listening on channels: {channels}")

                # Listen for messages
                for message in pubsub.listen():
                    if not self.running:
                        break

                    if message['type'] == 'message':
                        try:
                            self._handle_message(message)
                        except Exception as e:
                            logger.error(f"❌ Error handling message: {e}")

            except Exception as e:
                logger.error(f"❌ Listener error: {e}")
                if self.running:
                    time.sleep(5)  # Wait before reconnecting

        logger.info("🛑 Redis event listener stopped")

    def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message from Redis"""
        try:
            channel = message['channel']
            data = json.loads(message['data'])

            # Get subscribers for this channel
            if channel not in self.subscribers:
                return

            # Call all callbacks for this channel
            for callback in self.subscribers[channel]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"❌ Callback error for {channel}: {e}")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in message: {e}")
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Redis connection

        Returns:
            dict: Health status information
        """
        current_time = time.time()

        # Cache health checks
        if current_time - self.last_health_check < self.health_check_interval:
            return {
                'healthy': self.is_healthy,
                'cached': True,
                'last_check': self.last_health_check
            }

        try:
            # Test connection
            self.redis_client.ping()

            # Get basic stats
            info = self.redis_client.info()

            self.is_healthy = True
            self.last_health_check = current_time

            return {
                'healthy': True,
                'cached': False,
                'version': info.get('redis_version'),
                'connected_clients': info.get('connected_clients'),
                'used_memory_human': info.get('used_memory_human'),
                'uptime_days': info.get('uptime_in_days'),
                'total_connections_received': info.get('total_connections_received')
            }

        except Exception as e:
            self.is_healthy = False
            self.last_health_check = current_time

            return {
                'healthy': False,
                'cached': False,
                'error': str(e)
            }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get event bus statistics

        Returns:
            dict: Statistics about the event bus
        """
        try:
            info = self.redis_client.info()
            pubsub_info = self.redis_client.pubsub_numsub(*self.subscribers.keys())

            return {
                'channels_subscribed': len(self.subscribers),
                'total_subscribers': sum(len(callbacks) for callbacks in self.subscribers.values()),
                'redis_connected_clients': info.get('connected_clients', 0),
                'redis_used_memory': info.get('used_memory_human', 'unknown'),
                'channel_details': {channel: len(callbacks) for channel, callbacks in self.subscribers.items()},
                'pubsub_details': dict(pubsub_info)
            }
        except Exception as e:
            return {
                'error': str(e),
                'channels_subscribed': len(self.subscribers),
                'total_subscribers': sum(len(callbacks) for callbacks in self.subscribers.values())
            }

    def shutdown(self):
        """Gracefully shutdown the event bus"""
        logger.info("🔄 Shutting down Redis Event Bus...")
        self.running = False

        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=5)

        # Close connection pool
        self.redis_pool.disconnect()
        logger.info("✅ Redis Event Bus shutdown complete")

# Singleton instance
_event_bus_instance: Optional[RedisEventBus] = None

def get_event_bus() -> RedisEventBus:
    """
    Get the singleton Redis event bus instance

    Returns:
        RedisEventBus: The global event bus instance
    """
    global _event_bus_instance

    if _event_bus_instance is None:
        # Try to get Redis config from environment
        import os
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_db = int(os.getenv('REDIS_DB', '0'))
        redis_password = os.getenv('REDIS_PASSWORD')

        _event_bus_instance = RedisEventBus(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password
        )

    return _event_bus_instance
