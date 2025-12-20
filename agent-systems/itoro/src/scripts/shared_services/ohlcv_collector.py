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

# RBI data symbols for backtesting
RBI_DATA_SYMBOLS = ['BTC', 'ETH', 'SOL']

# Always save RBI data
SAVE_OHLCV_DATA = True

# Default data collection settings
DAYSBACK_4_DATA = 30
DATA_TIMEFRAME = '15m'

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

def collect_rbi_data():
    """Collect OHLCV data for RBI backtesting (BTC, ETH, SOL) - Multiple timeframes: 5m, 15m, 4h, 1d"""
    rbi_data = {}

    # Collect multiple timeframes for different strategies
    timeframes = ['5m', '15m', '4h', '1d']

    cprint("\n[DATA] Moon Dev's AI Agent collecting RBI backtest data (5m, 15m, 4h, 1d)...", "white", "on_blue")

    for symbol in RBI_DATA_SYMBOLS:
        cprint(f"\n[TARGET] Collecting {symbol} data for RBI backtesting...", "white", "on_blue")
        
        for timeframe in timeframes:
            cprint(f"  [TIMEFRAME] Collecting {timeframe} data...", "cyan")
            # For daily (1d) timeframe, collect minimum 30 days (data source limitation)
            # For other timeframes, 30 days is sufficient
            days_back = 30 if timeframe == '1d' else 30
            data = collect_token_data(symbol, days_back=days_back, timeframe=timeframe)
        if data is not None:
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

if __name__ == "__main__":
    try:
        # Collect RBI backtest data first
        cprint("\n[START] Starting RBI data collection...", "white", "on_blue")
        collect_rbi_data()

        # Then collect all monitored tokens
        collect_all_tokens()
    except KeyboardInterrupt:
        print("\n[EXIT] Moon Dev OHLCV Collector shutting down gracefully...")
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
        print("[FIX] Moon Dev suggests checking the logs and trying again!") 
