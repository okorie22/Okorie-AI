"""
Liquidation WebSocket Manager
Handles real-time liquidation streams from multiple exchanges
Built with love by Anarcho Capital 🚀
"""

import asyncio
import websockets
import json
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import traceback
from collections import deque
import time

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


class LiquidationWebSocketManager:
    """Manage WebSocket connections to multiple exchanges for liquidation data"""
    
    # Exchange WebSocket endpoints
    EXCHANGES = {
        'binance': {
            'url': 'wss://fstream.binance.com/ws/!forceOrder@arr',
            'type': 'futures'
        },
        'bybit': {
            'url': 'wss://stream.bybit.com/v5/public/linear',
            'type': 'futures'
        },
        'okx': {
            'url': 'wss://ws.okx.com:8443/ws/v5/public',
            'type': 'futures'
        },
        'kucoin': {
            'url': 'wss://ws-api-futures.kucoin.com/',
            'type': 'futures'
        },
        'bitfinex': {
            'url': 'wss://api-pub.bitfinex.com/ws/2',
            'type': 'futures'
        }
    }
    
    def __init__(self, symbols: List[str] = None):
        """
        Initialize WebSocket manager
        
        Args:
            symbols: List of symbols to track (e.g., ['BTC', 'ETH', 'SOL'])
        """
        self.symbols = symbols or ['BTC', 'ETH', 'SOL']
        self.connections = {}
        self.running = False
        self.callbacks = []
        self.reconnect_delays = {}  # Track reconnection delays per exchange
        self.event_counts = {exchange: 0 for exchange in self.EXCHANGES.keys()}
        self.last_event_time = {exchange: None for exchange in self.EXCHANGES.keys()}
        self.connection_status = {exchange: 'disconnected' for exchange in self.EXCHANGES.keys()}
        
        # Event buffer for recent events (for calculating metrics)
        self.recent_events = deque(maxlen=1000)
        
        info(f"🌊 Liquidation WebSocket Manager initialized")
        info(f"📊 Tracking symbols: {', '.join(self.symbols)}")
        info(f"🌐 Exchanges: {', '.join(self.EXCHANGES.keys())}")
    
    def on_liquidation_event(self, callback: Callable):
        """
        Register a callback function for liquidation events
        
        Args:
            callback: Function to call with normalized liquidation event
        """
        self.callbacks.append(callback)
        debug(f"Registered callback: {callback.__name__}", file_only=True)
    
    async def connect_all_exchanges(self):
        """Connect to all exchange WebSocket streams concurrently"""
        self.running = True
        tasks = []
        
        for exchange in self.EXCHANGES.keys():
            task = asyncio.create_task(self._connect_exchange(exchange))
            tasks.append(task)
        
        info("🚀 Connecting to all exchanges...")
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _connect_exchange(self, exchange: str):
        """
        Connect to a specific exchange and handle reconnections
        
        Args:
            exchange: Exchange name
        """
        reconnect_delay = 1  # Start with 1 second
        max_delay = 60  # Max 60 seconds between reconnections
        
        while self.running:
            try:
                self.connection_status[exchange] = 'connecting'
                info(f"🔌 Connecting to {exchange}...")
                
                exchange_config = self.EXCHANGES[exchange]
                url = exchange_config['url']
                
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                ) as websocket:
                    self.connections[exchange] = websocket
                    self.connection_status[exchange] = 'connected'
                    info(f"✅ Connected to {exchange}")
                    
                    # Subscribe to liquidation streams
                    await self._subscribe_liquidations(exchange, websocket)
                    
                    # Reset reconnect delay on successful connection
                    reconnect_delay = 1
                    
                    # Handle incoming messages
                    await self._handle_messages(exchange, websocket)
                    
            except websockets.exceptions.ConnectionClosed as e:
                self.connection_status[exchange] = 'disconnected'
                warning(f"⚠️ {exchange} connection closed: {e}")
                
            except Exception as e:
                self.connection_status[exchange] = 'error'
                error(f"❌ {exchange} error: {str(e)}")
                error(traceback.format_exc())
            
            # Reconnect with exponential backoff
            if self.running:
                info(f"🔄 Reconnecting to {exchange} in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_delay)
    
    async def _subscribe_liquidations(self, exchange: str, websocket):
        """
        Subscribe to liquidation streams for the exchange
        
        Args:
            exchange: Exchange name
            websocket: WebSocket connection
        """
        try:
            if exchange == 'binance':
                # Binance automatically streams all liquidations
                debug(f"{exchange}: Auto-subscribed to liquidations", file_only=True)
                
            elif exchange == 'bybit':
                # Subscribe to liquidation streams for each symbol
                for symbol in self.symbols:
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [f"liquidation.{symbol}USDT"]
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                debug(f"{exchange}: Subscribed to liquidation streams", file_only=True)
                
            elif exchange == 'okx':
                # Subscribe to liquidation streams
                channels = []
                for symbol in self.symbols:
                    channels.append({
                        "channel": "liquidation-orders",
                        "instId": f"{symbol}-USDT-SWAP"
                    })
                
                subscribe_msg = {
                    "op": "subscribe",
                    "args": channels
                }
                await websocket.send(json.dumps(subscribe_msg))
                debug(f"{exchange}: Subscribed to liquidation streams", file_only=True)
                
            elif exchange == 'kucoin':
                # KuCoin requires token-based connection (simplified for now)
                debug(f"{exchange}: Connection established (token auth required for full functionality)", file_only=True)
                
            elif exchange == 'bitfinex':
                # Subscribe to liquidation feed
                subscribe_msg = {
                    "event": "subscribe",
                    "channel": "status",
                    "key": "liq:global"
                }
                await websocket.send(json.dumps(subscribe_msg))
                debug(f"{exchange}: Subscribed to liquidation streams", file_only=True)
                
        except Exception as e:
            error(f"Failed to subscribe to {exchange}: {str(e)}")
    
    async def _handle_messages(self, exchange: str, websocket):
        """
        Handle incoming WebSocket messages
        
        Args:
            exchange: Exchange name
            websocket: WebSocket connection
        """
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # Normalize the event based on exchange format
                normalized_event = self._normalize_event(exchange, data)
                
                if normalized_event:
                    # Update statistics
                    self.event_counts[exchange] += 1
                    self.last_event_time[exchange] = datetime.now()
                    self.recent_events.append(normalized_event)
                    
                    # Call registered callbacks
                    for callback in self.callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(normalized_event)
                            else:
                                callback(normalized_event)
                        except Exception as e:
                            error(f"Callback error: {str(e)}")
                
            except json.JSONDecodeError:
                debug(f"{exchange}: Invalid JSON received", file_only=True)
            except Exception as e:
                error(f"{exchange} message handling error: {str(e)}")
    
    def _normalize_event(self, exchange: str, raw_data: Dict) -> Optional[Dict]:
        """
        Normalize liquidation event data across different exchange formats
        
        Args:
            exchange: Exchange name
            raw_data: Raw event data from exchange
        
        Returns:
            Normalized event dictionary or None if not a liquidation event
        """
        try:
            if exchange == 'binance':
                return self._normalize_binance(raw_data)
            elif exchange == 'bybit':
                return self._normalize_bybit(raw_data)
            elif exchange == 'okx':
                return self._normalize_okx(raw_data)
            elif exchange == 'kucoin':
                return self._normalize_kucoin(raw_data)
            elif exchange == 'bitfinex':
                return self._normalize_bitfinex(raw_data)
            else:
                return None
                
        except Exception as e:
            debug(f"Normalization error for {exchange}: {str(e)}", file_only=True)
            return None
    
    def _normalize_binance(self, data: Dict) -> Optional[Dict]:
        """Normalize Binance liquidation event"""
        try:
            if 'e' in data and data['e'] == 'forceOrder':
                order = data.get('o', {})
                
                # Extract symbol (remove USDT suffix)
                symbol = order.get('s', '').replace('USDT', '').replace('BUSD', '')
                
                # Filter for tracked symbols
                if symbol not in self.symbols:
                    return None
                
                # Determine side (SELL = long liquidation, BUY = short liquidation)
                side = 'long' if order.get('S') == 'SELL' else 'short'
                
                price = float(order.get('p', 0))
                quantity = float(order.get('q', 0))
                
                return {
                    'timestamp': datetime.now(),
                    'event_time': datetime.fromtimestamp(data.get('E', 0) / 1000),
                    'exchange': 'binance',
                    'symbol': symbol,
                    'side': side,
                    'price': price,
                    'quantity': quantity,
                    'usd_value': price * quantity,
                    'order_type': order.get('o', 'MARKET'),
                    'time_in_force': order.get('f', 'IOC'),
                    'average_price': float(order.get('ap', price))
                }
        except Exception as e:
            debug(f"Binance normalization error: {str(e)}", file_only=True)
        return None
    
    def _normalize_bybit(self, data: Dict) -> Optional[Dict]:
        """Normalize Bybit liquidation event"""
        try:
            if data.get('topic', '').startswith('liquidation'):
                liq_data = data.get('data', {})
                
                # Extract symbol
                symbol = liq_data.get('symbol', '').replace('USDT', '')
                
                if symbol not in self.symbols:
                    return None
                
                side = 'long' if liq_data.get('side') == 'Sell' else 'short'
                price = float(liq_data.get('price', 0))
                quantity = float(liq_data.get('size', 0))
                
                return {
                    'timestamp': datetime.now(),
                    'event_time': datetime.fromtimestamp(int(liq_data.get('updatedTime', 0)) / 1000),
                    'exchange': 'bybit',
                    'symbol': symbol,
                    'side': side,
                    'price': price,
                    'quantity': quantity,
                    'usd_value': price * quantity
                }
        except Exception as e:
            debug(f"Bybit normalization error: {str(e)}", file_only=True)
        return None
    
    def _normalize_okx(self, data: Dict) -> Optional[Dict]:
        """Normalize OKX liquidation event"""
        try:
            if data.get('arg', {}).get('channel') == 'liquidation-orders':
                liq_data = data.get('data', [{}])[0]
                
                # Extract symbol
                inst_id = liq_data.get('instId', '')
                symbol = inst_id.split('-')[0] if '-' in inst_id else ''
                
                if symbol not in self.symbols:
                    return None
                
                side = 'long' if liq_data.get('side') == 'sell' else 'short'
                price = float(liq_data.get('bkPx', 0))
                quantity = float(liq_data.get('sz', 0))
                
                return {
                    'timestamp': datetime.now(),
                    'event_time': datetime.fromtimestamp(int(liq_data.get('ts', 0)) / 1000),
                    'exchange': 'okx',
                    'symbol': symbol,
                    'side': side,
                    'price': price,
                    'quantity': quantity,
                    'usd_value': price * quantity
                }
        except Exception as e:
            debug(f"OKX normalization error: {str(e)}", file_only=True)
        return None
    
    def _normalize_kucoin(self, data: Dict) -> Optional[Dict]:
        """Normalize KuCoin liquidation event"""
        try:
            # KuCoin liquidation format (simplified)
            if data.get('type') == 'message' and data.get('topic', '').startswith('/contractMarket/liquidation'):
                liq_data = data.get('data', {})
                
                symbol = liq_data.get('symbol', '').replace('USDTM', '')
                
                if symbol not in self.symbols:
                    return None
                
                side = 'long' if liq_data.get('side') == 'sell' else 'short'
                price = float(liq_data.get('filledPrice', 0))
                quantity = float(liq_data.get('filledSize', 0))
                
                return {
                    'timestamp': datetime.now(),
                    'event_time': datetime.fromtimestamp(int(liq_data.get('createdAt', 0)) / 1000),
                    'exchange': 'kucoin',
                    'symbol': symbol,
                    'side': side,
                    'price': price,
                    'quantity': quantity,
                    'usd_value': price * quantity
                }
        except Exception as e:
            debug(f"KuCoin normalization error: {str(e)}", file_only=True)
        return None
    
    def _normalize_bitfinex(self, data: Dict) -> Optional[Dict]:
        """Normalize Bitfinex liquidation event"""
        try:
            # Bitfinex liquidation format (array-based)
            if isinstance(data, list) and len(data) > 1:
                if data[1] == 'liq':
                    liq_data = data[2] if len(data) > 2 else {}
                    
                    # Extract symbol
                    symbol_str = liq_data.get('symbol', '')
                    for sym in self.symbols:
                        if sym in symbol_str:
                            symbol = sym
                            break
                    else:
                        return None
                    
                    side = 'long' if liq_data.get('amount', 0) < 0 else 'short'
                    price = float(liq_data.get('price', 0))
                    quantity = abs(float(liq_data.get('amount', 0)))
                    
                    return {
                        'timestamp': datetime.now(),
                        'event_time': datetime.fromtimestamp(int(liq_data.get('mts', 0)) / 1000),
                        'exchange': 'bitfinex',
                        'symbol': symbol,
                        'side': side,
                        'price': price,
                        'quantity': quantity,
                        'usd_value': price * quantity
                    }
        except Exception as e:
            debug(f"Bitfinex normalization error: {str(e)}", file_only=True)
        return None
    
    def get_connection_status(self) -> Dict[str, str]:
        """
        Get connection status for all exchanges
        
        Returns:
            Dictionary with exchange names and their status
        """
        return self.connection_status.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for all exchanges
        
        Returns:
            Dictionary with exchange statistics
        """
        stats = {}
        for exchange in self.EXCHANGES.keys():
            stats[exchange] = {
                'status': self.connection_status[exchange],
                'event_count': self.event_counts[exchange],
                'last_event': self.last_event_time[exchange].isoformat() if self.last_event_time[exchange] else None
            }
        
        stats['total_events'] = sum(self.event_counts.values())
        stats['recent_buffer_size'] = len(self.recent_events)
        
        return stats
    
    async def stop(self):
        """Stop all WebSocket connections gracefully"""
        info("🛑 Stopping WebSocket manager...")
        self.running = False
        
        # Close all connections
        for exchange, ws in self.connections.items():
            try:
                await ws.close()
                self.connection_status[exchange] = 'disconnected'
            except:
                pass
        
        info("✅ WebSocket manager stopped")


async def main():
    """Test the WebSocket manager"""
    print("🧪 Testing Liquidation WebSocket Manager")
    print("=" * 50)
    
    # Create manager
    manager = LiquidationWebSocketManager(symbols=['BTC', 'ETH', 'SOL'])
    
    # Register callback
    event_counter = {'count': 0}
    
    def on_liquidation(event):
        event_counter['count'] += 1
        print(f"\n🌊 Liquidation #{event_counter['count']}")
        print(f"   Exchange: {event['exchange']}")
        print(f"   Symbol: {event['symbol']}")
        print(f"   Side: {event['side']}")
        print(f"   Price: ${event['price']:,.2f}")
        print(f"   USD Value: ${event['usd_value']:,.2f}")
        
        # Print stats every 10 events
        if event_counter['count'] % 10 == 0:
            stats = manager.get_statistics()
            print(f"\n📊 Statistics:")
            print(f"   Total events: {stats['total_events']}")
            for exchange, exchange_stats in stats.items():
                if exchange not in ['total_events', 'recent_buffer_size']:
                    print(f"   {exchange}: {exchange_stats['event_count']} events ({exchange_stats['status']})")
    
    manager.on_liquidation_event(on_liquidation)
    
    # Start connections
    try:
        await manager.connect_all_exchanges()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())

