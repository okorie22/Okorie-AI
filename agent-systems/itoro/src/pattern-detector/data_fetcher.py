"""
Data Fetcher - Real-time OHLCV Data Collection
Fetches data from Binance (primary) with automatic fallbacks
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import numpy as np


class BinanceDataFetcher:
    """
    Multi-source OHLCV data fetcher with automatic fallbacks.
    Primary: Binance API (free, no key required)
    Fallbacks: Coinbase, Kraken, KuCoin
    """
    
    def __init__(self, retry_attempts=3, retry_delay=2):
        """
        Initialize data fetcher with retry configuration.
        
        Args:
            retry_attempts: Number of retry attempts per source (default: 3)
            retry_delay: Delay between retries in seconds (default: 2)
        """
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        
        # API endpoints
        self.binance_base_url = "https://api.binance.com/api/v3"
        self.coinbase_base_url = "https://api.exchange.coinbase.com"
        self.kraken_base_url = "https://api.kraken.com/0"
        self.kucoin_base_url = "https://api.kucoin.com/api/v1"
        
        # Interval mapping (standardized to Binance format)
        self.interval_map = {
            '1m': {'binance': '1m', 'coinbase': 60, 'kraken': 1, 'kucoin': '1min'},
            '5m': {'binance': '5m', 'coinbase': 300, 'kraken': 5, 'kucoin': '5min'},
            '15m': {'binance': '15m', 'coinbase': 900, 'kraken': 15, 'kucoin': '15min'},
            '1h': {'binance': '1h', 'coinbase': 3600, 'kraken': 60, 'kucoin': '1hour'},
            '4h': {'binance': '4h', 'coinbase': 14400, 'kraken': 240, 'kucoin': '4hour'},
            '1d': {'binance': '1d', 'coinbase': 86400, 'kraken': 1440, 'kucoin': '1day'}
        }
        
        print("[DATA FETCHER] Initialized with Binance + fallback sources")
    
    def get_ohlcv(self, symbol: str, interval: str = '1d', limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data with automatic fallback.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT', 'ETHUSDT')
            interval: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles to fetch (default: 100)
            
        Returns:
            DataFrame with columns [Open, High, Low, Close, Volume] or None if failed
        """
        # Try sources in order: Binance -> Coinbase -> Kraken -> KuCoin
        sources = [
            ('Binance', self._fetch_binance),
            ('Coinbase', self._fetch_coinbase),
            ('Kraken', self._fetch_kraken),
            ('KuCoin', self._fetch_kucoin)
        ]
        
        for source_name, fetch_func in sources:
            try:
                print(f"[DATA FETCHER] Trying {source_name} for {symbol} {interval}...")
                df = fetch_func(symbol, interval, limit)
                
                if df is not None and self.validate_data(df):
                    print(f"[DATA FETCHER] Success from {source_name}: {len(df)} candles")
                    return df
                else:
                    print(f"[DATA FETCHER] {source_name} data validation failed")
                    
            except Exception as e:
                print(f"[DATA FETCHER] {source_name} failed: {e}")
                continue
        
        print(f"[DATA FETCHER] All sources failed for {symbol}")
        return None
    
    def _fetch_binance(self, symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
        """Fetch from Binance API (primary source)"""
        # Convert symbol format if needed (e.g., BTC-USD -> BTCUSDT)
        binance_symbol = symbol.replace('-', '').replace('_', '')
        
        url = f"{self.binance_base_url}/klines"
        params = {
            'symbol': binance_symbol,
            'interval': self.interval_map[interval]['binance'],
            'limit': limit
        }
        
        for attempt in range(self.retry_attempts):
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    return None
                
                # Parse Binance response
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                
                # Convert to standard format
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.set_index('timestamp')
                df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                
                return df
                
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise e
        
        return None
    
    def _fetch_coinbase(self, symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
        """Fetch from Coinbase API (fallback #1)"""
        # Convert symbol format (BTCUSDT -> BTC-USD)
        if 'USDT' in symbol:
            coinbase_symbol = symbol.replace('USDT', '-USD')
        elif 'USD' in symbol:
            coinbase_symbol = symbol.replace('USD', '-USD')
        else:
            coinbase_symbol = f"{symbol}-USD"
        
        url = f"{self.coinbase_base_url}/products/{coinbase_symbol}/candles"
        
        # Calculate time range
        granularity = self.interval_map[interval]['coinbase']
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=granularity * limit)
        
        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'granularity': granularity
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return None
            
            # Parse Coinbase response [time, low, high, open, close, volume]
            df = pd.DataFrame(data, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.set_index('timestamp')
            df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            df = df.sort_index()
            
            return df
            
        except Exception as e:
            raise e
    
    def _fetch_kraken(self, symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
        """Fetch from Kraken API (fallback #2)"""
        # Convert symbol format (BTCUSDT -> XBTUSD)
        kraken_symbol_map = {
            'BTC': 'XBT',
            'USDT': 'USD'
        }
        
        kraken_symbol = symbol.replace('USDT', 'USD')
        for old, new in kraken_symbol_map.items():
            kraken_symbol = kraken_symbol.replace(old, new)
        
        url = f"{self.kraken_base_url}/public/OHLC"
        params = {
            'pair': kraken_symbol,
            'interval': self.interval_map[interval]['kraken']
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('error') or not data.get('result'):
                return None
            
            # Get the pair key (first key in result)
            pair_key = list(data['result'].keys())[0]
            ohlc_data = data['result'][pair_key]
            
            if not ohlc_data:
                return None
            
            # Parse Kraken response [time, open, high, low, close, vwap, volume, count]
            df = pd.DataFrame(ohlc_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.set_index('timestamp')
            df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            df = df.iloc[-limit:]  # Limit to requested number of candles
            
            return df
            
        except Exception as e:
            raise e
    
    def _fetch_kucoin(self, symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
        """Fetch from KuCoin API (fallback #3)"""
        # Convert symbol format (BTCUSDT -> BTC-USDT)
        kucoin_symbol = symbol.replace('USDT', '-USDT').replace('USD', '-USD')
        
        url = f"{self.kucoin_base_url}/market/candles"
        
        # Calculate time range
        end_time = int(datetime.now().timestamp())
        interval_seconds = {
            '1m': 60, '5m': 300, '15m': 900,
            '1h': 3600, '4h': 14400, '1d': 86400
        }
        start_time = end_time - (interval_seconds[interval] * limit)
        
        params = {
            'symbol': kucoin_symbol,
            'type': self.interval_map[interval]['kucoin'],
            'startAt': start_time,
            'endAt': end_time
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != '200000' or not data.get('data'):
                return None
            
            # Parse KuCoin response [time, open, close, high, low, volume, amount]
            df = pd.DataFrame(data['data'], columns=[
                'timestamp', 'open', 'close', 'high', 'low', 'volume', 'amount'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.set_index('timestamp')
            df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            df = df.sort_index()
            
            return df
            
        except Exception as e:
            raise e
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate OHLCV data quality.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if data is valid, False otherwise
        """
        if df is None or len(df) == 0:
            print("[VALIDATION] Empty data")
            return False
        
        # Check required columns
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_columns):
            print(f"[VALIDATION] Missing columns. Have: {df.columns.tolist()}")
            return False
        
        # Check for missing values
        if df[required_columns].isnull().any().any():
            print("[VALIDATION] Contains null values")
            return False
        
        # Check timestamp freshness (last candle should be recent)
        if hasattr(df.index[-1], 'timestamp'):
            last_timestamp = df.index[-1]
            age = datetime.now() - last_timestamp.to_pydatetime()
            if age > timedelta(days=2):
                print(f"[VALIDATION] Data too old (last: {last_timestamp})")
                return False
        
        # Check OHLC logic (high >= low, high >= open, high >= close, low <= open, low <= close)
        if not (
            (df['High'] >= df['Low']).all() and
            (df['High'] >= df['Open']).all() and
            (df['High'] >= df['Close']).all() and
            (df['Low'] <= df['Open']).all() and
            (df['Low'] <= df['Close']).all()
        ):
            print("[VALIDATION] OHLC logic violation")
            return False
        
        # Check for reasonable values (no zeros, no negative prices)
        if (df[['Open', 'High', 'Low', 'Close']] <= 0).any().any():
            print("[VALIDATION] Invalid price values (zero or negative)")
            return False
        
        print(f"[VALIDATION] Data valid ({len(df)} candles)")
        return True
    
    def fetch_multiple_symbols(self, symbols: List[str], interval: str = '1d', limit: int = 100) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for multiple symbols.
        
        Args:
            symbols: List of trading pairs
            interval: Timeframe
            limit: Number of candles
            
        Returns:
            Dictionary mapping symbols to DataFrames
        """
        results = {}
        
        for symbol in symbols:
            print(f"\n[MULTI-FETCH] Processing {symbol}...")
            df = self.get_ohlcv(symbol, interval, limit)
            if df is not None:
                results[symbol] = df
            time.sleep(0.5)  # Rate limiting between requests
        
        print(f"\n[MULTI-FETCH] Successfully fetched {len(results)}/{len(symbols)} symbols")
        return results


if __name__ == "__main__":
    print("="*80)
    print("DATA FETCHER - Manual Test")
    print("="*80)
    
    fetcher = BinanceDataFetcher()
    
    # Test single symbol
    print("\n[TEST] Fetching BTC daily data...")
    btc_data = fetcher.get_ohlcv('BTCUSDT', '1d', 10)
    
    if btc_data is not None:
        print("\n[RESULT] BTC Data:")
        print(btc_data.tail())
    else:
        print("\n[ERROR] Failed to fetch BTC data")
    
    # Test multiple symbols
    print("\n[TEST] Fetching multiple symbols...")
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    all_data = fetcher.fetch_multiple_symbols(symbols, '1d', 5)
    
    print(f"\n[RESULT] Fetched {len(all_data)} symbols")
    for symbol, data in all_data.items():
        print(f"  {symbol}: {len(data)} candles, Latest close: ${data['Close'].iloc[-1]:.2f}")

