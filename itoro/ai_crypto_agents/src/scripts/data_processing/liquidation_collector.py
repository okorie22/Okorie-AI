"""
Liquidation Data Collector
Background script for continuous real-time liquidation data collection
Built with love by Anarcho Capital 🚀
"""

import asyncio
import signal
from datetime import datetime, timedelta
from typing import List, Dict
from collections import deque
import traceback
from pathlib import Path

# Import configuration
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import config
from src.scripts.shared_services.liquidation_websocket_manager import LiquidationWebSocketManager
from src.scripts.data_processing.liquidation_storage import LiquidationStorage

# Import logger
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
except ImportError:
    def debug(msg, file_only=False):
        if not file_only:
            print(f"DEBUG: {msg}")
    def info(msg):
        print(f"INFO: {msg}")
    def warning(msg):
        print(f"WARNING: {msg}")
    def error(msg):
        print(f"ERROR: {msg}")

# Import cloud database (optional - graceful fallback if not available)
try:
    from src.scripts.database.cloud_database import CloudDatabaseManager
    CLOUD_DB_AVAILABLE = True
except:
    CLOUD_DB_AVAILABLE = False
    warning("Cloud database not available - will store locally only")


class LiquidationCollector:
    """
    Continuous liquidation data collector
    Streams data from multiple exchanges and stores locally + cloud
    """
    
    def __init__(self):
        """Initialize the liquidation collector"""
        info("🌊 Initializing Liquidation Collector...")
        
        # Load configuration
        self.symbols = config.LIQUIDATION_SYMBOLS
        self.exchanges = config.LIQUIDATION_EXCHANGES
        self.batch_interval = config.LIQUIDATION_BATCH_INTERVAL_SECONDS
        self.cloud_sync_interval = config.LIQUIDATION_CLOUD_SYNC_INTERVAL_SECONDS
        self.cloud_sync_batch_size = config.LIQUIDATION_CLOUD_SYNC_BATCH_SIZE
        self.buffer_size = config.LIQUIDATION_BUFFER_SIZE
        self.retention_hours = config.LIQUIDATION_LOCAL_RETENTION_HOURS
        
        # Initialize WebSocket manager
        self.ws_manager = LiquidationWebSocketManager(symbols=self.symbols)
        
        # Initialize storage
        self.storage = LiquidationStorage()
        
        # Initialize cloud database (optional)
        self.cloud_db = None
        if CLOUD_DB_AVAILABLE:
            try:
                self.cloud_db = CloudDatabaseManager()
                info("☁️ Cloud database connected")
            except Exception as e:
                warning(f"Cloud database unavailable: {str(e)}")
                self.cloud_db = None
        
        # Event buffers
        self.event_buffer = deque(maxlen=self.buffer_size)
        self.cloud_buffer = deque(maxlen=self.cloud_sync_batch_size * 2)
        
        # Statistics
        self.stats = {
            'total_events': 0,
            'events_by_exchange': {ex: 0 for ex in self.exchanges},
            'events_by_symbol': {sym: 0 for sym in self.symbols},
            'local_saves': 0,
            'cloud_saves': 0,
            'start_time': datetime.now()
        }
        
        # Running flag
        self.running = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        info(f"📊 Tracking symbols: {', '.join(self.symbols)}")
        info(f"🌐 Monitoring exchanges: {', '.join(self.exchanges)}")
        info(f"💾 Batch interval: {self.batch_interval}s")
        info(f"☁️ Cloud sync interval: {self.cloud_sync_interval}s")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        info(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def _enrich_event(self, event: Dict) -> Dict:
        """
        Enrich liquidation event with calculated metrics
        
        Args:
            event: Base liquidation event
        
        Returns:
            Enriched event with additional metrics
        """
        try:
            # Calculate cumulative metrics from recent events
            now = datetime.now()
            
            # Get recent events for the same symbol
            symbol_events = [e for e in self.event_buffer if e.get('symbol') == event['symbol']]
            
            # 1-minute cumulative
            one_min_ago = now - timedelta(minutes=1)
            recent_1m = [e for e in symbol_events if e.get('timestamp', now) >= one_min_ago]
            event['cumulative_1m_usd'] = sum(e.get('usd_value', 0) for e in recent_1m)
            event['event_velocity_1m'] = len(recent_1m)
            
            # 5-minute cumulative
            five_min_ago = now - timedelta(minutes=5)
            recent_5m = [e for e in symbol_events if e.get('timestamp', now) >= five_min_ago]
            event['cumulative_5m_usd'] = sum(e.get('usd_value', 0) for e in recent_5m)
            
            # 15-minute cumulative
            fifteen_min_ago = now - timedelta(minutes=15)
            recent_15m = [e for e in symbol_events if e.get('timestamp', now) >= fifteen_min_ago]
            event['cumulative_15m_usd'] = sum(e.get('usd_value', 0) for e in recent_15m)
            
            # Calculate cascade score (0-1 based on recent liquidation velocity)
            if event['cumulative_1m_usd'] > 0:
                # Higher score for higher velocity and volume
                velocity_score = min(event['event_velocity_1m'] / 20.0, 1.0)  # Normalize to 0-1
                volume_score = min(event['cumulative_1m_usd'] / 5000000, 1.0)  # $5M max
                event['cascade_score'] = (velocity_score + volume_score) / 2
            else:
                event['cascade_score'] = 0.0
            
            # Calculate cluster size (events in last 10 seconds)
            ten_sec_ago = now - timedelta(seconds=10)
            cluster = [e for e in symbol_events if e.get('timestamp', now) >= ten_sec_ago]
            event['cluster_size'] = len(cluster)
            
            # Multi-exchange correlation
            recent_all = [e for e in self.event_buffer if e.get('timestamp', now) >= one_min_ago]
            exchanges_active = len(set(e.get('exchange') for e in recent_all if e.get('symbol') == event['symbol']))
            event['concurrent_exchanges'] = exchanges_active
            
            # Determine dominant exchange (by volume in last 1 minute)
            exchange_volumes = {}
            for e in recent_1m:
                ex = e.get('exchange')
                exchange_volumes[ex] = exchange_volumes.get(ex, 0) + e.get('usd_value', 0)
            
            if exchange_volumes:
                event['dominant_exchange'] = max(exchange_volumes.items(), key=lambda x: x[1])[0]
            else:
                event['dominant_exchange'] = event['exchange']
            
            # Add batch ID for related events
            event['batch_id'] = f"{event['symbol']}_{now.strftime('%Y%m%d%H%M%S')}"
            
            # Add event_id (sequential per symbol)
            symbol_count = len([e for e in symbol_events if e.get('symbol') == event['symbol']])
            event['event_id'] = symbol_count + 1
            
            return event
            
        except Exception as e:
            error(f"Error enriching event: {str(e)}")
            return event
    
    async def _on_liquidation(self, event: Dict):
        """
        Callback for liquidation events from WebSocket manager
        
        Args:
            event: Liquidation event from WebSocket
        """
        try:
            # Enrich the event with calculated metrics
            enriched_event = self._enrich_event(event)
            
            # Add to buffers
            self.event_buffer.append(enriched_event)
            self.cloud_buffer.append(enriched_event)
            
            # Update statistics
            self.stats['total_events'] += 1
            self.stats['events_by_exchange'][enriched_event['exchange']] = \
                self.stats['events_by_exchange'].get(enriched_event['exchange'], 0) + 1
            self.stats['events_by_symbol'][enriched_event['symbol']] = \
                self.stats['events_by_symbol'].get(enriched_event['symbol'], 0) + 1
            
            # Log significant events
            if enriched_event.get('cascade_score', 0) > 0.7:
                info(f"🌊 CASCADE ALERT: {enriched_event['symbol']} on {enriched_event['exchange']} - "
                     f"${enriched_event['usd_value']:,.0f} ({enriched_event['side']}) "
                     f"Score: {enriched_event['cascade_score']:.2f}")
            
        except Exception as e:
            error(f"Error processing liquidation event: {str(e)}")
            error(traceback.format_exc())
    
    async def _batch_save_loop(self):
        """Background loop to batch save events to local storage"""
        info(f"💾 Starting batch save loop (interval: {self.batch_interval}s)")
        
        while self.running:
            try:
                await asyncio.sleep(self.batch_interval)
                
                if self.event_buffer:
                    # Get all events from buffer
                    events_to_save = list(self.event_buffer)
                    
                    # Save to local storage
                    success = self.storage.save_liquidation_batch(events_to_save)
                    
                    if success:
                        self.stats['local_saves'] += len(events_to_save)
                        debug(f"Saved {len(events_to_save)} events to local storage", file_only=True)
                    else:
                        warning("Failed to save events to local storage")
                
                # Cleanup old files
                if self.stats['local_saves'] % 100 == 0:  # Every 100 saves
                    self.storage.cleanup_old_files(retention_hours=self.retention_hours)
                
            except Exception as e:
                error(f"Error in batch save loop: {str(e)}")
                error(traceback.format_exc())
    
    async def _cloud_sync_loop(self):
        """Background loop to sync events to cloud database"""
        if not self.cloud_db:
            debug("Cloud sync disabled (no database connection)", file_only=True)
            return
        
        info(f"☁️ Starting cloud sync loop (interval: {self.cloud_sync_interval}s)")
        
        while self.running:
            try:
                await asyncio.sleep(self.cloud_sync_interval)
                
                if self.cloud_buffer:
                    # Get batch of events to sync
                    batch_size = min(len(self.cloud_buffer), self.cloud_sync_batch_size)
                    events_to_sync = [self.cloud_buffer.popleft() for _ in range(batch_size)]
                    
                    # Save to cloud database
                    success = self.cloud_db.save_liquidation_events(events_to_sync)
                    
                    if success:
                        self.stats['cloud_saves'] += len(events_to_sync)
                        debug(f"Synced {len(events_to_sync)} events to cloud", file_only=True)
                    else:
                        warning("Failed to sync events to cloud")
                        # Put events back in buffer for retry
                        for event in reversed(events_to_sync):
                            self.cloud_buffer.appendleft(event)
                
            except Exception as e:
                error(f"Error in cloud sync loop: {str(e)}")
                error(traceback.format_exc())
    
    async def _stats_loop(self):
        """Background loop to print statistics"""
        info("📊 Starting stats loop (interval: 60s)")
        
        while self.running:
            try:
                await asyncio.sleep(60)  # Print stats every minute
                
                uptime = datetime.now() - self.stats['start_time']
                
                info("\n" + "=" * 70)
                info("📊 LIQUIDATION COLLECTOR STATISTICS")
                info("=" * 70)
                info(f"⏱️  Uptime: {str(uptime).split('.')[0]}")
                info(f"📈 Total Events: {self.stats['total_events']}")
                info(f"💾 Local Saves: {self.stats['local_saves']}")
                info(f"☁️  Cloud Saves: {self.stats['cloud_saves']}")
                
                info("\n📊 Events by Exchange:")
                for exchange, count in sorted(self.stats['events_by_exchange'].items(), 
                                             key=lambda x: x[1], reverse=True):
                    if count > 0:
                        pct = (count / self.stats['total_events']) * 100 if self.stats['total_events'] > 0 else 0
                        info(f"   {exchange:12} {count:6} ({pct:5.1f}%)")
                
                info("\n📊 Events by Symbol:")
                for symbol, count in sorted(self.stats['events_by_symbol'].items(), 
                                           key=lambda x: x[1], reverse=True):
                    if count > 0:
                        pct = (count / self.stats['total_events']) * 100 if self.stats['total_events'] > 0 else 0
                        info(f"   {symbol:12} {count:6} ({pct:5.1f}%)")
                
                # WebSocket connection status
                ws_status = self.ws_manager.get_connection_status()
                info("\n🔌 Connection Status:")
                for exchange, status in ws_status.items():
                    status_icon = "✅" if status == "connected" else "❌"
                    info(f"   {status_icon} {exchange:12} {status}")
                
                info("=" * 70 + "\n")
                
            except Exception as e:
                error(f"Error in stats loop: {str(e)}")
    
    async def run(self):
        """Main run loop for the collector"""
        self.running = True
        
        info("\n" + "=" * 70)
        info("🌊 LIQUIDATION COLLECTOR STARTING")
        info("=" * 70)
        info(f"📊 Symbols: {', '.join(self.symbols)}")
        info(f"🌐 Exchanges: {', '.join(self.exchanges)}")
        info(f"💾 Local retention: {self.retention_hours} hours")
        info(f"☁️  Cloud sync: {'enabled' if self.cloud_db else 'disabled'}")
        info("=" * 70 + "\n")
        
        # Register callback with WebSocket manager
        self.ws_manager.on_liquidation_event(self._on_liquidation)
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.ws_manager.connect_all_exchanges()),
            asyncio.create_task(self._batch_save_loop()),
            asyncio.create_task(self._cloud_sync_loop()),
            asyncio.create_task(self._stats_loop())
        ]
        
        try:
            # Wait for tasks
            await asyncio.gather(*tasks)
            
        except asyncio.CancelledError:
            info("Tasks cancelled")
        except Exception as e:
            error(f"Error in main run loop: {str(e)}")
            error(traceback.format_exc())
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the collector gracefully"""
        info("\n🛑 Stopping Liquidation Collector...")
        self.running = False
        
        # Stop WebSocket manager
        await self.ws_manager.stop()
        
        # Final save of any remaining events
        if self.event_buffer:
            info(f"💾 Saving {len(self.event_buffer)} remaining events...")
            events = list(self.event_buffer)
            self.storage.save_liquidation_batch(events)
            
            if self.cloud_db and self.cloud_buffer:
                info(f"☁️ Syncing {len(self.cloud_buffer)} remaining events to cloud...")
                events = list(self.cloud_buffer)
                self.cloud_db.save_liquidation_events(events)
        
        # Print final statistics
        uptime = datetime.now() - self.stats['start_time']
        info("\n" + "=" * 70)
        info("📊 FINAL STATISTICS")
        info("=" * 70)
        info(f"⏱️  Total Uptime: {str(uptime).split('.')[0]}")
        info(f"📈 Total Events Collected: {self.stats['total_events']}")
        info(f"💾 Total Local Saves: {self.stats['local_saves']}")
        info(f"☁️  Total Cloud Saves: {self.stats['cloud_saves']}")
        info("=" * 70)
        
        info("✅ Liquidation Collector stopped gracefully")


async def main():
    """Main entry point"""
    collector = LiquidationCollector()
    
    try:
        await collector.run()
    except KeyboardInterrupt:
        info("\n👋 Keyboard interrupt received")
    except Exception as e:
        error(f"Fatal error: {str(e)}")
        error(traceback.format_exc())
    finally:
        await collector.stop()


if __name__ == "__main__":
    asyncio.run(main())

