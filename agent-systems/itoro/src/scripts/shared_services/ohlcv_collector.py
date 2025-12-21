"""
[MOON] Moon Dev's OHLCV Data Collector with Fallback
Collects Open-High-Low-Close-Volume data with Birdeye -> Hyperliquid fallback
Built with love by Moon Dev [ROCKET]
"""

try:
    from src.config import *
    from src import nice_funcs as n
    from src import nice_funcs_hl as hl
except ImportError:
    # Fallback for when called from different contexts
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from config import *
        import nice_funcs as n
        import nice_funcs_hl as hl
    except ImportError:
        # Last resort - define minimal required functions/constants
        print("[WARN] Config imports failed, using minimal fallback")

        # Minimal fallback functions
        def get_birdeye_api_key():
            # Try to get from environment
            import os
            return os.getenv('BIRDEYE_API_KEY')

        # Minimal constants
        DAYS_BACK_4_DATA = 30
        DATA_TIMEFRAME = '15m'

        # Dummy functions that return None (will trigger Hyperliquid fallback)
        class n:
            @staticmethod
            def get_data(token, days_back, timeframe):
                """Minimal Birdeye data collection fallback"""
                try:
                    import requests
                    pd = _import_pandas()
                    datetime, timedelta = _import_datetime()
                    import os

                    if pd is None or datetime is None:
                        return None

                    api_key = os.getenv('BIRDEYE_API_KEY')
                    if not api_key:
                        return None

                    # Birdeye API endpoint
                    base_url = "https://public-api.birdeye.so"
                    headers = {"X-API-KEY": api_key}

                    # Convert timeframe to minutes
                    timeframe_minutes = {
                        '1m': 1, '5m': 5, '15m': 15, '30m': 30,
                        '1h': 60, '4h': 240, '1d': 1440
                    }.get(timeframe, 15)

                    # Calculate bars needed
                    bars = (days_back * 24 * 60) // timeframe_minutes

                    # Get historical OHLCV data
                    endpoint = f"/public/ohlcv"
                    params = {
                        "address": token,
                        "type": timeframe,
                        "time_from": int((datetime.now() - timedelta(days=days_back)).timestamp()),
                        "time_to": int(datetime.now().timestamp())
                    }

                    response = requests.get(f"{base_url}{endpoint}", headers=headers, params=params, timeout=10)
                    if response.status_code != 200:
                        return None

                    data = response.json()
                    if not data or 'data' not in data or 'items' not in data['data']:
                        return None

                    # Convert to DataFrame
                    df_data = []
                    for item in data['data']['items'][:bars]:
                        df_data.append({
                            'timestamp': datetime.fromtimestamp(item['timestamp']).strftime('%Y-%m-%d %H:%M:%S'),
                            'open': float(item['o']),
                            'high': float(item['h']),
                            'low': float(item['l']),
                            'close': float(item['c']),
                            'volume': float(item['v'])
                        })

                    df = pd.DataFrame(df_data)
                    return df

                except Exception as e:
                    print(f"[ERROR] Birdeye fallback failed: {str(e)}")
                    return None

        class hl:
            @staticmethod
            def get_data(address=None, symbol=None, timeframe='15m', bars=1000):
                """Minimal Hyperliquid data collection fallback"""
                try:
                    import requests
                    pd = _import_pandas()
                    datetime, timedelta = _import_datetime()

                    if pd is None or datetime is None:
                        return None

                    # Hyperliquid API endpoint
                    url = 'https://api.hyperliquid.xyz/info'

                    # Map timeframe to Hyperliquid format
                    timeframe_map = {
                        '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                        '1h': '1h', '4h': '4h', '1d': '1d'
                    }
                    hl_timeframe = timeframe_map.get(timeframe, '15m')

                    # Prepare request for OHLCV data
                    payload = {
                        "type": "candleSnapshot",
                        "req": {
                            "coin": symbol or address or "BTC",
                            "interval": hl_timeframe,
                            "startTime": int((datetime.now() - timedelta(days=30)).timestamp() * 1000),
                            "endTime": int(datetime.now().timestamp() * 1000)
                        }
                    }

                    response = requests.post(url, json=payload, timeout=10)
                    if response.status_code != 200:
                        return None

                    data = response.json()
                    if not data or len(data) == 0:
                        return None

                    # Convert to DataFrame
                    df_data = []
                    for item in data[:bars]:  # Limit to requested bars
                        df_data.append({
                            'timestamp': datetime.fromtimestamp(item['t'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                            'open': float(item['o']),
                            'high': float(item['h']),
                            'low': float(item['l']),
                            'close': float(item['c']),
                            'volume': float(item['v'])
                        })

                    df = pd.DataFrame(df_data)
                    return df

                except Exception as e:
                    print(f"[ERROR] Hyperliquid fallback failed: {str(e)}")
                    return None

# Deferred imports - only import when actually needed
def _import_pandas():
    """Import pandas only when needed"""
    try:
        import pandas as pd
        return pd
    except ImportError as e:
        # #region agent log
        import json
        import os
        from pathlib import Path
        log_entry = {
            "id": f"log_{int(__import__('time').time() * 1000)}_pandas_import",
            "timestamp": int(__import__('time').time() * 1000),
            "location": "ohlcv_collector.py:_import_pandas",
            "message": "Pandas import failed",
            "data": {
                "error": str(e),
                "python_path": __import__('sys').path[:3],  # First 3 paths
                "working_dir": os.getcwd(),
                "file_location": str(Path(__file__).resolve())
            },
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        log_path = Path(__file__).parent.parent.parent.parent / ".cursor" / "debug.log"
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except:
            pass
        # #endregion
        print("[ERROR] Failed to import pandas")
        return None

def _import_datetime():
    """Import datetime modules only when needed"""
    try:
        from datetime import datetime, timedelta
        return datetime, timedelta
    except ImportError:
        print("[ERROR] Failed to import datetime")
        return None, None

import os
from termcolor import colored, cprint
import time
from dataclasses import dataclass

# RBI data symbols for backtesting
RBI_DATA_SYMBOLS = ['BTC', 'ETH', 'SOL']

# Always save RBI data
SAVE_OHLCV_DATA = True

# Default data collection settings
DAYSBACK_4_DATA = 30
DATA_TIMEFRAME = '15m'

# Multi-source OHLCV collection configuration
@dataclass
class DataSourceConfig:
    """Configuration for OHLCV data sources"""
    name: str
    function: callable
    max_days: int
    max_bars_per_request: int = 1000
    rate_limit_per_minute: int = 60
    priority: int = 1  # Higher = more preferred
    supports_timeframes: list = None  # List of supported timeframes

# Initialize shared API manager
try:
    from shared_api_manager import get_shared_api_manager
    api_manager = get_shared_api_manager()
except ImportError:
    api_manager = None

# Monitored tokens (for collect_all_tokens function)
MONITORED_TOKENS = []

def has_birdeye_key():
    """Check if Birdeye API key is available"""
    try:
        # Try to get from the imported n module first
        key = n.get_birdeye_api_key()
        return key is not None and key != ""
    except:
        # Fallback to environment variable
        import os
        key = os.getenv('BIRDEYE_API_KEY')
        return key is not None and key != ""

def has_birdeye_key():
    """Check if Birdeye API key is available"""
    try:
        key = n.get_birdeye_api_key()
        return key is not None and key != ""
    except:
        return False

def collect_token_data_with_fallback(token, days_back=DAYSBACK_4_DATA, timeframe=DATA_TIMEFRAME):
    """
    Collect OHLCV data with intelligent fallback system

    Priority:
    1. Birdeye (if API key available) - higher quality data
    2. Hyperliquid (free fallback) - real-time perpetual data

    Args:
        token: Token address or symbol
        days_back: Days of historical data
        timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)

    Returns:
        dict: {
            'data': pandas.DataFrame,
            'source': 'birdeye' or 'hyperliquid',
            'quality': 'premium' or 'standard'
        }
    """
    cprint(f"\n[AI] Moon Dev's AI Agent fetching data for {token}...", "white", "on_blue")

    # Calculate bars needed (approximate)
    bars_needed = (days_back * 24 * 60) // get_timeframe_minutes(timeframe)

    # PHASE 1: Try Birdeye (Premium Data Source)
    if has_birdeye_key():
        cprint(f"[TARGET] Trying Birdeye (premium data)...", "white", "on_blue")
        try:
            data = n.get_data(token, days_back, timeframe)

            if data is not None and not data.empty and len(data) > 0:
                cprint(f"[SUCCESS] Birdeye success: {len(data)} candles", "white", "on_green")

            # Save data if configured
            save_data_to_file(data, token, "birdeye", is_rbi_data=(token in RBI_DATA_SYMBOLS), timeframe=timeframe)

            return {
                'data': data,
                'source': 'birdeye',
                'quality': 'premium',
                'bars_requested': bars_needed,
                'bars_received': len(data)
            }

        except Exception as e:
            cprint(f"[WARN] Birdeye failed: {str(e)}", "white", "on_yellow")
    else:
        cprint(f"[INFO] Birdeye API key not available, skipping...", "white", "on_blue")

    # PHASE 2: Hyperliquid Fallback (Free Data Source)
    cprint(f"[FALLBACK] Falling back to Hyperliquid (free data)...", "white", "on_cyan")
    try:
        # Convert days_back to bars for Hyperliquid
        bars = min(bars_needed, 5000)  # Hyperliquid limit

        # Map timeframe to Hyperliquid format
        hl_timeframe = map_timeframe_to_hyperliquid(timeframe)

        # For major crypto symbols, use symbol parameter instead of address
        if token in RBI_DATA_SYMBOLS:
            data = hl.get_data(symbol=token, timeframe=hl_timeframe, bars=bars)

            # For RBI symbols, also collect OI data from Hyperliquid meta
            if data is not None and not data.empty:
                try:
                    # Get current OI from meta endpoint
                    import requests
                    meta_url = 'https://api.hyperliquid.xyz/info'
                    meta_payload = {"type": "metaAndAssetCtxs"}
                    meta_response = requests.post(meta_url, json=meta_payload, timeout=10)

                    if meta_response.status_code == 200:
                        meta_data = meta_response.json()
                        if len(meta_data) >= 2 and isinstance(meta_data[1], list):
                            # Find OI for this symbol
                            universe = {coin['name']: i for i, coin in enumerate(meta_data[0]['universe'])}
                            if token in universe:
                                asset_data = meta_data[1][universe[token]]
                                oi_value = float(asset_data['openInterest'])
                                data['open_interest'] = oi_value  # Add OI column
                                cprint(f"[OI] Added OI data for {token}: {oi_value}", "white", "on_green")
                except Exception as e:
                    cprint(f"[WARN] Could not get OI data for {token}: {str(e)}", "white", "on_yellow")

        else:
            data = hl.get_data(address=token, timeframe=hl_timeframe, bars=bars)

        if data is not None and not data.empty and len(data) > 0:
            cprint(f"[SUCCESS] Hyperliquid fallback success: {len(data)} candles", "white", "on_green")

            # Standardize column names to match Birdeye format
            data = standardize_hyperliquid_data(data)

            # Save data if configured
            save_data_to_file(data, token, "hyperliquid", is_rbi_data=(token in RBI_DATA_SYMBOLS), timeframe=timeframe)

            return {
                'data': data,
                'source': 'hyperliquid',
                'quality': 'standard',
                'bars_requested': bars_needed,
                'bars_received': len(data)
            }

    except Exception as e:
        cprint(f"[ERROR] Hyperliquid fallback failed: {str(e)}", "white", "on_red")

    # PHASE 3: Complete failure
    cprint(f"[FAILURE] All data sources failed for {token}", "white", "on_red")
    return None

def collect_token_data(token, days_back=DAYSBACK_4_DATA, timeframe=DATA_TIMEFRAME):
    """
    Legacy function - now uses fallback system
    Returns just the DataFrame for backward compatibility
    """
    result = collect_token_data_with_fallback(token, days_back, timeframe)
    return result['data'] if result else None

def get_timeframe_minutes(timeframe):
    """Convert timeframe string to minutes"""
    timeframe_map = {
        '1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240, '1d': 1440
    }
    return timeframe_map.get(timeframe, 60)  # Default to 1h

def map_timeframe_to_hyperliquid(timeframe):
    """Map standard timeframe to Hyperliquid format"""
    # Hyperliquid uses: 1m, 5m, 15m, 30m, 1h, 4h, 1d
    timeframe_map = {
        '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
        '1h': '1h', '4h': '4h', '1d': '1d'
    }
    return timeframe_map.get(timeframe, '1h')

def standardize_hyperliquid_data(data):
    """
    Standardize Hyperliquid data columns to match Birdeye format
    Birdeye format: timestamp, open, high, low, close, volume
    Also preserves additional columns like open_interest for RBI data
    """
    pd = _import_pandas()
    if pd is None:
        print("[ERROR] Cannot standardize data without pandas")
        return data

    if data.empty:
        return data

    # Hyperliquid returns: timestamp, open, high, low, close, volume
    # RBI data may also have open_interest
    expected_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

    # Rename columns if needed, but preserve additional columns
    column_mapping = {}
    for i, col in enumerate(data.columns):
        if i < len(expected_columns):
            column_mapping[col] = expected_columns[i]
        # Keep additional columns like open_interest as-is

    if column_mapping:
        data = data.rename(columns=column_mapping)

    # Ensure timestamp is datetime
    if 'timestamp' in data.columns:
        data['timestamp'] = pd.to_datetime(data['timestamp'])

    return data

def fetch_binance_ohlcv(symbol, timeframe='1h', limit=1000, start_time=None, end_time=None):
    """
    Fetch OHLCV data from Binance public API

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        timeframe: Kline interval (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
        limit: Number of klines to fetch (max 1000)
        start_time: Start time in milliseconds
        end_time: End time in milliseconds

    Returns:
        pandas.DataFrame with OHLCV data or None if failed
    """
    try:
        import requests
        pd = _import_pandas()

        if pd is None:
            return None

        base_url = "https://api.binance.com/api/v3/klines"

        params = {
            'symbol': symbol,
            'interval': timeframe,
            'limit': min(limit, 1000)
        }

        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time

        response = requests.get(base_url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Convert to DataFrame
            df_data = []
            for kline in data:
                df_data.append({
                    'timestamp': pd.to_datetime(kline[0], unit='ms'),
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5])
                })

            df = pd.DataFrame(df_data)
            return df
        else:
            print(f"[ERROR] Binance API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"[ERROR] Binance OHLCV fetch failed: {str(e)}")
        return None

def fetch_kucoin_ohlcv(symbol, timeframe='1hour', limit=1500, start_time=None, end_time=None):
    """
    Fetch OHLCV data from KuCoin public API

    Args:
        symbol: Trading pair (e.g., 'BTC-USDT')
        timeframe: Time interval (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 1w)
        limit: Number of records (max 1500)
        start_time: Start time in seconds
        end_time: End time in seconds

    Returns:
        pandas.DataFrame with OHLCV data or None if failed
    """
    try:
        import requests
        pd = _import_pandas()

        if pd is None:
            return None

        base_url = "https://api.kucoin.com/api/v1/market/candles"

        params = {
            'symbol': symbol,
            'type': timeframe
        }

        if start_time:
            params['startAt'] = int(start_time)
        if end_time:
            params['endAt'] = int(end_time)

        response = requests.get(base_url, params=params, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get('code') == '200000' and result.get('data'):
                data = result['data']

                # Convert to DataFrame
                df_data = []
                for candle in data[-limit:]:  # Get last 'limit' records
                    df_data.append({
                        'timestamp': pd.to_datetime(int(candle[0]), unit='s'),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5])
                    })

                df = pd.DataFrame(df_data)
                return df
            else:
                print(f"[ERROR] KuCoin API error: {result.get('msg', 'Unknown error')}")
                return None
        else:
            print(f"[ERROR] KuCoin API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"[ERROR] KuCoin OHLCV fetch failed: {str(e)}")
        return None

def fetch_kraken_ohlcv(symbol, timeframe=60, limit=720, since=None):
    """
    Fetch OHLCV data from Kraken public API

    Args:
        symbol: Trading pair (e.g., 'XXBTZUSD' for BTC/USD)
        timeframe: Time interval in minutes (1, 5, 15, 30, 60, 240, 1440, 10080)
        limit: Number of OHLC entries (max 720)
        since: Starting timestamp

    Returns:
        pandas.DataFrame with OHLCV data or None if failed
    """
    try:
        import requests
        pd = _import_pandas()

        if pd is None:
            return None

        base_url = "https://api.kraken.com/0/public/OHLC"

        params = {
            'pair': symbol,
            'interval': timeframe
        }

        if since:
            params['since'] = since

        response = requests.get(base_url, params=params, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get('error') == [] and result.get('result'):
                pair_data = list(result['result'].values())[0]

                # Convert to DataFrame
                df_data = []
                for ohlc in pair_data[-limit:]:  # Get last 'limit' records
                    df_data.append({
                        'timestamp': pd.to_datetime(int(ohlc[0]), unit='s'),
                        'open': float(ohlc[1]),
                        'high': float(ohlc[2]),
                        'low': float(ohlc[3]),
                        'close': float(ohlc[4]),
                        'volume': float(ohlc[6])  # Volume is at index 6
                    })

                df = pd.DataFrame(df_data)
                return df
            else:
                print(f"[ERROR] Kraken API error: {result.get('error', 'Unknown error')}")
                return None
        else:
            print(f"[ERROR] Kraken API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"[ERROR] Kraken OHLCV fetch failed: {str(e)}")
        return None

def fetch_okx_ohlcv(symbol, timeframe='1H', limit=300, before=None, after=None):
    """
    Fetch OHLCV data from OKX public API

    Args:
        symbol: Trading pair (e.g., 'BTC-USDT')
        timeframe: Bar size (1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M)
        limit: Number of results (max 300)
        before: Request page before this timestamp
        after: Request page after this timestamp

    Returns:
        pandas.DataFrame with OHLCV data or None if failed
    """
    try:
        import requests
        pd = _import_pandas()

        if pd is None:
            return None

        base_url = "https://www.okx.com/api/v5/market/candles"

        params = {
            'instId': symbol,
            'bar': timeframe,
            'limit': str(min(limit, 300))
        }

        if before:
            params['before'] = str(before)
        if after:
            params['after'] = str(after)

        response = requests.get(base_url, params=params, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get('code') == '0' and result.get('data'):
                data = result['data']

                # Convert to DataFrame
                df_data = []
                for candle in data:
                    df_data.append({
                        'timestamp': pd.to_datetime(int(candle[0]), unit='ms'),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5])
                    })

                df = pd.DataFrame(df_data)
                return df
            else:
                print(f"[ERROR] OKX API error: {result.get('msg', 'Unknown error')}")
                return None
        else:
            print(f"[ERROR] OKX API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"[ERROR] OKX OHLCV fetch failed: {str(e)}")
        return None

def fetch_bybit_ohlcv(symbol, timeframe='60', limit=200, start_time=None, end_time=None):
    """
    Fetch OHLCV data from Bybit public API

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        timeframe: Kline interval (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
        limit: Number of klines (max 200)
        start_time: Start time in milliseconds
        end_time: End time in milliseconds

    Returns:
        pandas.DataFrame with OHLCV data or None if failed
    """
    try:
        import requests
        pd = _import_pandas()

        if pd is None:
            return None

        base_url = "https://api.bybit.com/v5/market/kline"

        params = {
            'category': 'spot',
            'symbol': symbol,
            'interval': timeframe,
            'limit': min(limit, 200)
        }

        if start_time:
            params['start'] = start_time
        if end_time:
            params['end'] = end_time

        response = requests.get(base_url, params=params, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get('retCode') == 0 and result.get('result', {}).get('list'):
                data = result['result']['list']

                # Convert to DataFrame
                df_data = []
                for kline in data:
                    df_data.append({
                        'timestamp': pd.to_datetime(int(kline[0]), unit='ms'),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })

                df = pd.DataFrame(df_data)
                return df
            else:
                print(f"[ERROR] Bybit API error: {result.get('retMsg', 'Unknown error')}")
                return None
        else:
            print(f"[ERROR] Bybit API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"[ERROR] Bybit OHLCV fetch failed: {str(e)}")
        return None

def save_data_to_file(data, token, source, is_rbi_data=False, timeframe=None):
    """Save data to file with source indication"""
    if not SAVE_OHLCV_DATA:
        return

    # Create filename with source
    safe_token = token[:8] if len(token) > 8 else token
    if is_rbi_data:
        # For RBI data, save in specific format expected by backtests
        # Use provided timeframe or default to 15m for backward compatibility
        tf = timeframe if timeframe else '15m'
        filename = f"{safe_token}-USD-{tf}.csv"
        save_path = os.path.join("src", "data", "rbi", filename)
    else:
        filename = f"{safe_token}_{source}_latest.csv"
        save_path = os.path.join("src", "data", filename)

    # Ensure directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Save to CSV
    data.to_csv(save_path, index=False)
    cprint(f"[SAVE] Cached {source} data for {safe_token} ({tf if is_rbi_data else 'N/A'}) at {save_path}", "white", "on_green")

# Data source configurations for multi-source collection (defined after functions)
DATA_SOURCES = {
    'hyperliquid': DataSourceConfig(
        name='hyperliquid',
        function=lambda symbol, timeframe='1h', bars=1000, **kwargs: hl.get_data(symbol=symbol, timeframe=timeframe, bars=bars) if 'hl' in globals() else None,
        max_days=30,
        max_bars_per_request=5000,
        rate_limit_per_minute=60,
        priority=1,
        supports_timeframes=['1m', '5m', '15m', '30m', '1h', '4h', '1d']
    ),
    'binance': DataSourceConfig(
        name='binance',
        function=fetch_binance_ohlcv,
        max_days=365,
        max_bars_per_request=1000,
        rate_limit_per_minute=1200,
        priority=2,
        supports_timeframes=['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    ),
    'kucoin': DataSourceConfig(
        name='kucoin',
        function=fetch_kucoin_ohlcv,
        max_days=1500,
        max_bars_per_request=1500,
        rate_limit_per_minute=100,
        priority=3,
        supports_timeframes=['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w']
    ),
    'kraken': DataSourceConfig(
        name='kraken',
        function=fetch_kraken_ohlcv,
        max_days=730,
        max_bars_per_request=720,
        rate_limit_per_minute=15,
        priority=4,
        supports_timeframes=['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
    ),
    'okx': DataSourceConfig(
        name='okx',
        function=fetch_okx_ohlcv,
        max_days=365,
        max_bars_per_request=300,
        rate_limit_per_minute=20,
        priority=5,
        supports_timeframes=['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '1M']
    ),
    'bybit': DataSourceConfig(
        name='bybit',
        function=fetch_bybit_ohlcv,
        max_days=365,
        max_bars_per_request=200,
        rate_limit_per_minute=50,
        priority=6,
        supports_timeframes=['1m', '5m', '15m', '30m', '1h', '4h', '1d']
    )
}

def collect_multi_source_ohlcv(token, total_days_needed=90, timeframe='1h', symbol_mapping=None):
    """
    Collect OHLCV data from multiple sources to overcome individual source limitations

    Args:
        token: Token symbol (e.g., 'BTC', 'ETH', 'SOL')
        total_days_needed: Total days of historical data needed
        timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
        symbol_mapping: Dict mapping token to exchange-specific symbols

    Returns:
        pandas.DataFrame: Combined OHLCV data from multiple sources
    """
    import pandas as pd
    from datetime import datetime, timedelta

    cprint(f"\n[MULTI-SOURCE] Collecting {total_days_needed} days of {timeframe} data for {token}...", "white", "on_blue")

    # Default symbol mapping for major tokens
    if symbol_mapping is None:
        symbol_mapping = {
            'BTC': {
                'binance': 'BTCUSDT',
                'kucoin': 'BTC-USDT',
                'kraken': 'XXBTZUSD',
                'okx': 'BTC-USDT',
                'bybit': 'BTCUSDT',
                'hyperliquid': 'BTC'
            },
            'ETH': {
                'binance': 'ETHUSDT',
                'kucoin': 'ETH-USDT',
                'kraken': 'XETHZUSD',
                'okx': 'ETH-USDT',
                'bybit': 'ETHUSDT',
                'hyperliquid': 'ETH'
            },
            'SOL': {
                'binance': 'SOLUSDT',
                'kucoin': 'SOL-USDT',
                'kraken': 'SOLUSD',
                'okx': 'SOL-USDT',
                'bybit': 'SOLUSDT',
                'hyperliquid': 'SOL'
            }
        }

    # Get exchange symbol for this token
    exchange_symbols = symbol_mapping.get(token, {})

    # Sort data sources by priority (highest first)
    sorted_sources = sorted(DATA_SOURCES.items(), key=lambda x: x[1].priority)

    all_data = []
    collected_days = 0
    current_end_time = datetime.now()

    for source_name, source_config in sorted_sources:
        if collected_days >= total_days_needed:
            break

        # Check if source supports this timeframe
        if source_config.supports_timeframes and timeframe not in source_config.supports_timeframes:
            cprint(f"  [SKIP] {source_name} doesn't support {timeframe} timeframe", "yellow")
            continue

        # Calculate how many days we still need
        days_needed = min(total_days_needed - collected_days, source_config.max_days)

        if days_needed <= 0:
            continue

        # Calculate time range for this source
        start_time = current_end_time - timedelta(days=days_needed)
        end_time = current_end_time

        cprint(f"  [SOURCE] Fetching {days_needed} days from {source_name}...", "cyan")

        try:
            # Get exchange-specific symbol
            symbol = exchange_symbols.get(source_name, token)

            # Call the source function
            if source_name == 'hyperliquid':
                # Special handling for Hyperliquid
                bars_needed = int((days_needed * 24 * 60) / get_timeframe_minutes(timeframe))
                data = source_config.function(symbol=symbol, timeframe=timeframe, bars=min(bars_needed, source_config.max_bars_per_request))
            else:
                # Standard API call with exchange-specific formatting
                if source_name == 'kucoin':
                    # KuCoin uses formats like '1min', '5min', '1hour', '1day'
                    kucoin_timeframes = {
                        '1m': '1min', '5m': '5min', '15m': '15min', '30m': '30min',
                        '1h': '1hour', '2h': '2hour', '4h': '4hour', '6h': '6hour',
                        '8h': '8hour', '12h': '12hour', '1d': '1day', '1w': '1week'
                    }
                    kucoin_tf = kucoin_timeframes.get(timeframe, '1hour')
                    data = source_config.function(
                        symbol=symbol,
                        timeframe=kucoin_tf,
                        limit=min(source_config.max_bars_per_request, int(days_needed * 24 * 60 / get_timeframe_minutes(timeframe))),
                        start_time=int(start_time.timestamp()),
                        end_time=int(end_time.timestamp())
                    )
                elif source_name == 'kraken':
                    # Kraken uses different timeframe format (minutes as int)
                    tf_minutes = get_timeframe_minutes(timeframe)
                    data = source_config.function(
                        symbol=symbol,
                        timeframe=tf_minutes,
                        limit=min(source_config.max_bars_per_request, int(days_needed * 24 * 60 / tf_minutes))
                    )
                elif source_name == 'okx':
                    # OKX uses formats like '1m', '5m', '1H', '1D'
                    okx_timeframes = {
                        '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                        '1h': '1H', '2h': '2H', '4h': '4H', '6h': '6H',
                        '12h': '12H', '1d': '1D', '1w': '1W', '1M': '1M'
                    }
                    okx_tf = okx_timeframes.get(timeframe, '1H')
                    data = source_config.function(
                        symbol=symbol,
                        timeframe=okx_tf,
                        limit=min(source_config.max_bars_per_request, int(days_needed * 24 * 60 / get_timeframe_minutes(timeframe)))
                    )
                elif source_name == 'bybit':
                    # Bybit uses different timeframe format
                    bybit_timeframes = {'1m': '1', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '4h': '240', '1d': 'D'}
                    bybit_tf = bybit_timeframes.get(timeframe, '60')
                    data = source_config.function(
                        symbol=symbol,
                        timeframe=bybit_tf,
                        limit=min(source_config.max_bars_per_request, int(days_needed * 24 * 60 / get_timeframe_minutes(timeframe)))
                    )
                else:
                    # Standard format (Binance)
                    data = source_config.function(
                        symbol=symbol,
                        timeframe=timeframe,
                        limit=min(source_config.max_bars_per_request, int(days_needed * 24 * 60 / get_timeframe_minutes(timeframe))),
                        start_time=int(start_time.timestamp() * 1000),
                        end_time=int(end_time.timestamp() * 1000)
                    )

            if data is not None and not data.empty:
                # Standardize column names
                data = standardize_ohlcv_data(data, source_name)

                # Filter data to our time range
                data = data[(data['timestamp'] >= start_time) & (data['timestamp'] <= end_time)]

                if not data.empty:
                    all_data.append(data)

                    # Calculate actual days collected from this batch
                    if len(data) > 1:
                        days_collected = (data['timestamp'].max() - data['timestamp'].min()).total_seconds() / (24 * 3600)
                        collected_days += days_collected
                    else:
                        # Single candle - estimate based on timeframe
                        tf_minutes = get_timeframe_minutes(timeframe)
                        days_collected = tf_minutes / (24 * 60)  # Convert minutes to days
                        collected_days += days_collected

                    cprint(f"    [SUCCESS] {source_name}: {len(data)} candles ({days_collected:.1f} days, total: {collected_days:.1f})", "green")

                    # Update current_end_time for next source (earliest timestamp from this batch)
                    current_end_time = data['timestamp'].min()

                    # Early termination: if we have enough data, break
                    if collected_days >= total_days_needed:
                        cprint(f"    [TARGET] Reached target of {total_days_needed} days, stopping collection", "cyan")
                        break
                else:
                    cprint(f"    [WARN] {source_name}: No data in requested time range", "yellow")
            else:
                cprint(f"    [ERROR] {source_name}: Failed to fetch data", "red")

        except Exception as e:
            cprint(f"    [ERROR] {source_name}: {str(e)}", "red")
            continue

    # Combine all data
    if all_data:
        combined_data = pd.concat(all_data, ignore_index=True)

        # Sort by timestamp and remove duplicates
        combined_data = combined_data.sort_values('timestamp').drop_duplicates(subset=['timestamp'])

        # Reset index
        combined_data = combined_data.reset_index(drop=True)

        total_days = (combined_data['timestamp'].max() - combined_data['timestamp'].min()).days if len(combined_data) > 1 else 0

        cprint(f"\n[MULTI-SOURCE] Combined {len(combined_data)} candles ({total_days} days) from {len(all_data)} sources", "white", "on_green")

        return combined_data
    else:
        cprint(f"\n[MULTI-SOURCE] Failed to collect any data for {token}", "white", "on_red")
        return None

def standardize_ohlcv_data(data, source_name):
    """
    Standardize OHLCV data from different sources to common format

    Args:
        data: pandas.DataFrame with OHLCV data
        source_name: Name of the data source

    Returns:
        pandas.DataFrame with standardized columns
    """
    pd = _import_pandas()
    if pd is None or data is None or data.empty:
        return data

    # Ensure timestamp is datetime
    if 'timestamp' in data.columns:
        data['timestamp'] = pd.to_datetime(data['timestamp'])

    # Ensure OHLCV columns are float
    ohlcv_columns = ['open', 'high', 'low', 'close', 'volume']
    for col in ohlcv_columns:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')

    # Add source column for tracking
    data['source'] = source_name

    return data

def collect_rbi_data(total_days=90):
    """
    Collect OHLCV data for RBI backtesting (BTC, ETH, SOL) using multi-source collection
    Now supports collecting more than 30 days by combining data from multiple sources

    Args:
        total_days: Total days of historical data to collect (default 90 for 1h timeframe)
    """
    rbi_data = {}

    # Collect multiple timeframes for different strategies
    timeframes = ['5m', '15m', '1h', '4h', '1d']

    cprint(f"\n[DATA] Moon Dev's AI Agent collecting RBI backtest data ({', '.join(timeframes)}) - {total_days} days...", "white", "on_blue")

    for symbol in RBI_DATA_SYMBOLS:
        cprint(f"\n[TARGET] Collecting {symbol} data for RBI backtesting...", "white", "on_blue")
        
        for timeframe in timeframes:
            cprint(f"  [TIMEFRAME] Collecting {timeframe} data...", "cyan")

            # Use multi-source collection for longer timeframes that need more data
            if timeframe in ['1h', '4h', '1d'] and total_days > 30:
                # Use multi-source collection for timeframes that need more than 30 days
                data = collect_multi_source_ohlcv(symbol, total_days_needed=total_days, timeframe=timeframe)
                # Save multi-source data to CSV file
                if data is not None and not data.empty:
                    save_data_to_file(data, symbol, "multi-source", is_rbi_data=True, timeframe=timeframe)
            else:
                # Use single source for shorter timeframes or when 30 days is sufficient
                days_back = 30 if timeframe == '1d' else min(total_days, 30)
                data = collect_token_data(symbol, days_back=days_back, timeframe=timeframe)

            if data is not None and not data.empty:
                # Store with timeframe key for reference
                key = f"{symbol}_{timeframe}"
                rbi_data[key] = data
                cprint(f"  [SUCCESS] {symbol} {timeframe} data collected: {len(data)} candles", "white", "on_green")
        else:
                cprint(f"  [ERROR] Failed to collect {symbol} {timeframe} data", "white", "on_red")

    cprint("\n[COMPLETE] Moon Dev's AI Agent completed RBI data collection!", "white", "on_green")

    return rbi_data

def collect_all_tokens():
    """Collect OHLCV data for all monitored tokens"""
    market_data = {}

    cprint("\n[SEARCH] Moon Dev's AI Agent starting market data collection...", "white", "on_blue")

    for token in MONITORED_TOKENS:
        data = collect_token_data(token)
        if data is not None:
            market_data[token] = data

    cprint("\n[COMPLETE] Moon Dev's AI Agent completed market data collection!", "white", "on_green")

    return market_data

def test_multi_source_collection():
    """Test the multi-source OHLCV collection functionality"""
    cprint("\n[TEST] Testing multi-source OHLCV collection...", "white", "on_blue")

    # Test BTC 1h data collection for 90 days
    data = collect_multi_source_ohlcv('BTC', total_days_needed=90, timeframe='1h')

    if data is not None and not data.empty:
        cprint(f"[TEST] Successfully collected {len(data)} candles", "green")
        cprint(f"[TEST] Date range: {data['timestamp'].min()} to {data['timestamp'].max()}", "green")

        # Show source distribution
        source_counts = data['source'].value_counts()
        cprint("[TEST] Data sources used:", "cyan")
        for source, count in source_counts.items():
            cprint(f"  {source}: {count} candles", "cyan")

        return data
    else:
        cprint("[TEST] Multi-source collection failed", "red")
        return None

if __name__ == "__main__":
    try:
        import sys

        # Check command line arguments
        if len(sys.argv) > 1 and sys.argv[1] == "test":
            # Run multi-source test
            test_multi_source_collection()
        elif len(sys.argv) > 2 and sys.argv[1] == "collect":
            # Collect specific token and timeframe
            token = sys.argv[2]
            timeframe = sys.argv[3] if len(sys.argv) > 3 else '1h'
            days = int(sys.argv[4]) if len(sys.argv) > 4 else 90

            cprint(f"\n[COLLECT] Collecting {days} days of {timeframe} data for {token}...", "white", "on_blue")
            data = collect_multi_source_ohlcv(token, total_days_needed=days, timeframe=timeframe)

            if data is not None:
                cprint(f"[SUCCESS] Collected {len(data)} candles from {data['source'].nunique()} sources", "green")
        else:
            # Default behavior - collect RBI data with multi-source support
            cprint("\n[START] Starting RBI data collection with multi-source support...", "white", "on_blue")

            # Check if user wants more than 30 days
            total_days = 90  # Default for strategies requiring 90+ days
            collect_rbi_data(total_days=total_days)

            # Then collect all monitored tokens (legacy single-source)
        collect_all_tokens()

    except KeyboardInterrupt:
        print("\n[EXIT] Moon Dev OHLCV Collector shutting down gracefully...")
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
        print("[FIX] Moon Dev suggests checking the logs and trying again!") 
        print("\n[USAGE] python ohlcv_collector.py [test|collect TOKEN [TIMEFRAME] [DAYS]]") 
