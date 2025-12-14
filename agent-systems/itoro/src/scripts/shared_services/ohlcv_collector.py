"""
🌙 Moon Dev's OHLCV Data Collector with Fallback
Collects Open-High-Low-Close-Volume data with Birdeye → Hyperliquid fallback
Built with love by Moon Dev 🚀
"""

from src.config import *
from src import nice_funcs as n
from src import nice_funcs_hl as hl
import pandas as pd
from datetime import datetime, timedelta
import os
from termcolor import colored, cprint
import time

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
    cprint(f"\n🤖 Moon Dev's AI Agent fetching data for {token}...", "white", "on_blue")

    # Calculate bars needed (approximate)
    bars_needed = (days_back * 24 * 60) // get_timeframe_minutes(timeframe)

    # PHASE 1: Try Birdeye (Premium Data Source)
    if has_birdeye_key():
        cprint(f"🎯 Trying Birdeye (premium data)...", "white", "on_blue")
        try:
            data = n.get_data(token, days_back, timeframe)

            if data is not None and not data.empty and len(data) > 0:
                cprint(f"✅ Birdeye success: {len(data)} candles", "white", "on_green")

                # Save data if configured
                save_data_to_file(data, token, "birdeye")

                return {
                    'data': data,
                    'source': 'birdeye',
                    'quality': 'premium',
                    'bars_requested': bars_needed,
                    'bars_received': len(data)
                }

        except Exception as e:
            cprint(f"⚠️ Birdeye failed: {str(e)}", "white", "on_yellow")
    else:
        cprint(f"ℹ️ Birdeye API key not available, skipping...", "white", "on_blue")

    # PHASE 2: Hyperliquid Fallback (Free Data Source)
    cprint(f"🔄 Falling back to Hyperliquid (free data)...", "white", "on_cyan")
    try:
        # Convert days_back to bars for Hyperliquid
        bars = min(bars_needed, 5000)  # Hyperliquid limit

        # Map timeframe to Hyperliquid format
        hl_timeframe = map_timeframe_to_hyperliquid(timeframe)

        data = hl.get_data(address=token, timeframe=hl_timeframe, bars=bars)

        if data is not None and not data.empty and len(data) > 0:
            cprint(f"✅ Hyperliquid fallback success: {len(data)} candles", "white", "on_green")

            # Standardize column names to match Birdeye format
            data = standardize_hyperliquid_data(data)

            # Save data if configured
            save_data_to_file(data, token, "hyperliquid")

            return {
                'data': data,
                'source': 'hyperliquid',
                'quality': 'standard',
                'bars_requested': bars_needed,
                'bars_received': len(data)
            }

    except Exception as e:
        cprint(f"❌ Hyperliquid fallback failed: {str(e)}", "white", "on_red")

    # PHASE 3: Complete failure
    cprint(f"💀 All data sources failed for {token}", "white", "on_red")
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
    """
    if data.empty:
        return data

    # Hyperliquid returns: timestamp, open, high, low, close, volume
    # Should already be in correct format, but ensure column names
    expected_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

    # Rename columns if needed
    column_mapping = {}
    for i, col in enumerate(data.columns):
        if i < len(expected_columns):
            column_mapping[col] = expected_columns[i]

    if column_mapping:
        data = data.rename(columns=column_mapping)

    # Ensure timestamp is datetime
    if 'timestamp' in data.columns:
        data['timestamp'] = pd.to_datetime(data['timestamp'])

    return data

def save_data_to_file(data, token, source):
    """Save data to file with source indication"""
    if not SAVE_OHLCV_DATA:
        return

    # Create filename with source
    safe_token = token[:8] if len(token) > 8 else token
    filename = f"{safe_token}_{source}_latest.csv"
    save_path = os.path.join("data", filename)

    # Ensure directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Save to CSV
    data.to_csv(save_path)
    cprint(f"💾 Cached {source} data for {safe_token}", "white", "on_green")

def collect_all_tokens():
    """Collect OHLCV data for all monitored tokens"""
    market_data = {}
    
    cprint("\n🔍 Moon Dev's AI Agent starting market data collection...", "white", "on_blue")
    
    for token in MONITORED_TOKENS:
        data = collect_token_data(token)
        if data is not None:
            market_data[token] = data
            
    cprint("\n✨ Moon Dev's AI Agent completed market data collection!", "white", "on_green")
    
    return market_data

if __name__ == "__main__":
    try:
        collect_all_tokens()
    except KeyboardInterrupt:
        print("\n👋 Moon Dev OHLCV Collector shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("🔧 Moon Dev suggests checking the logs and trying again!") 
