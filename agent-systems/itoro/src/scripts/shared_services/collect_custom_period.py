#!/usr/bin/env python3
"""
Custom Period OHLCV Data Collector for TriplexSupertrend Strategy Testing
Collects BTC-USD data from specific time periods to test strategy in different market conditions.

Overwrites existing BTC-USD-{timeframe}.csv with new data from specified time period.

Usage:
    python collect_custom_period.py --start-date 2020-11-01 --end-date 2021-11-01
    python collect_custom_period.py --start-date 2021-01-01 --end-date 2021-12-31
    python collect_custom_period.py --start-date 2023-01-01 --end-date 2024-03-31

Suggested uptrend periods to test:
- 2020-11-01 to 2021-11-01: Major bull run (BTC from ~$13k to ~$69k)
- 2021-01-01 to 2021-04-14: Parabolic bull phase
- 2023-01-01 to 2024-03-14: Steady bull market
- 2024-10-01 to 2024-12-31: Recent bull phase (if available)

This script will collect at least 90 days of data and save as BTC-USD-{timeframe}.csv
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import os
import sys
from termcolor import colored, cprint

# Import required modules and functions
import requests
from datetime import datetime, timedelta

def collect_multi_source_ohlcv_for_period(token, start_date, end_date, timeframe='1h', symbol_mapping=None):
    """
    Collect OHLCV data specifically for a date range
    """
    cprint(f"\n[MULTI-SOURCE] Collecting {timeframe} data for {token} from {start_date.date()} to {end_date.date()}...", "white", "on_blue")

    # Default symbol mapping for major tokens
    if symbol_mapping is None:
        symbol_mapping = {
            'BTC': {
                'binance': 'BTCUSDT',
                'kucoin': 'BTC-USDT',
                'kraken': 'XXBTZUSD',
                'okx': 'BTC-USDT',
                'bybit': 'BTCUSDT'
            }
        }

    # Get exchange symbols for this token
    exchange_symbols = symbol_mapping.get(token, {})

    # Try multiple sources in order
    sources_to_try = ['binance', 'kucoin', 'okx', 'bybit', 'kraken']

    all_data = []

    for source_name in sources_to_try:
        cprint(f"  [SOURCE] Trying {source_name} with symbol {exchange_symbols.get(source_name, token)}...", "cyan")

        try:
            exchange_symbol = exchange_symbols.get(source_name, token)

            # Get data from this source for the specific period
            data = fetch_from_exchange(source_name, exchange_symbol, timeframe, start_date, end_date)

            if data is not None and not data.empty:
                # Ensure timestamp is datetime
                data['timestamp'] = pd.to_datetime(data['timestamp'])

                # Debug: Check what data this exchange returned
                cprint(f"    [DEBUG] {source_name} raw data range: {data['timestamp'].min()} to {data['timestamp'].max()}", "cyan")

                # Filter to our time range (in case exchange returned extra data)
                data = data[(data['timestamp'] >= start_date) & (data['timestamp'] <= end_date)]

                if not data.empty:
                    cprint(f"    [DEBUG] {source_name} filtered data range: {data['timestamp'].min()} to {data['timestamp'].max()}", "cyan")
                    all_data.append(data)
                    cprint(f"    [SUCCESS] {source_name}: {len(data)} candles", "green")

        except Exception as e:
            cprint(f"    [ERROR] {source_name} failed: {str(e)}", "red")
            continue

    # Combine all data with proper sorting and deduplication
    if all_data:
        combined_data = pd.concat(all_data, ignore_index=True)

        # Debug: Check timestamp types before conversion
        cprint(f"[DEBUG] Before conversion - timestamp dtypes: {combined_data['timestamp'].dtype}", "yellow")
        cprint(f"[DEBUG] Sample timestamps: {combined_data['timestamp'].head(3).tolist()}", "yellow")

        # Ensure all timestamps are datetime objects
        combined_data['timestamp'] = pd.to_datetime(combined_data['timestamp'], errors='coerce')

        # Debug: Check after conversion
        cprint(f"[DEBUG] After conversion - timestamp dtypes: {combined_data['timestamp'].dtype}", "yellow")
        cprint(f"[DEBUG] Sample timestamps: {combined_data['timestamp'].head(3).tolist()}", "yellow")
        cprint(f"[DEBUG] Min timestamp: {combined_data['timestamp'].min()}", "yellow")
        cprint(f"[DEBUG] Max timestamp: {combined_data['timestamp'].max()}", "yellow")

        # Sort by timestamp and remove duplicates (keep first occurrence)
        combined_data = combined_data.sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='first')

        # Reset index
        combined_data = combined_data.reset_index(drop=True)

        total_days = (combined_data['timestamp'].max() - combined_data['timestamp'].min()).days if len(combined_data) > 1 else 0
        cprint(f"\n[MULTI-SOURCE] Combined {len(combined_data)} candles ({total_days} days)", "white", "on_green")

        return combined_data
    else:
        cprint(f"\n[MULTI-SOURCE] Failed to collect any data for {token}", "white", "on_red")
        return None

# Removed the old incremental collection function - now using the fixed multi-source function

def fetch_from_exchange(exchange_name, symbol, timeframe, start_time, end_time):
    """
    Fetch data from a specific exchange
    """
    try:
        base_url = {
            'binance': "https://api.binance.com/api/v3/klines",
            'kucoin': "https://api.kucoin.com/api/v1/market/candles",
            'okx': "https://www.okx.com/api/v5/market/candles",
            'bybit': "https://api.bybit.com/v5/market/kline",
            'kraken': "https://api.kraken.com/0/public/OHLC"
        }.get(exchange_name)

        if not base_url:
            return None

        # Calculate number of bars needed
        timeframe_minutes = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}.get(timeframe, 60)
        total_minutes = (end_time - start_time).total_seconds() / 60
        limit = min(int(total_minutes / timeframe_minutes), 1000)

        params = {}
        if exchange_name == 'binance':
            params = {
                'symbol': symbol,
                'interval': timeframe,
                'limit': limit,
                'startTime': int(start_time.timestamp() * 1000),
                'endTime': int(end_time.timestamp() * 1000)
            }
        elif exchange_name == 'kucoin':
            params = {
                'symbol': symbol,
                'type': timeframe.replace('h', 'hour').replace('m', 'min').replace('d', 'day'),
                'startAt': int(start_time.timestamp()),
                'endAt': int(end_time.timestamp())
            }
        elif exchange_name == 'okx':
            # OKX requires uppercase timeframe format: 1m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M
            okx_timeframes = {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1H', '2h': '2H', '4h': '4H', '6h': '6H',
                '12h': '12H', '1d': '1D', '1w': '1W', '1M': '1M'
            }
            okx_tf = okx_timeframes.get(timeframe, '1H')
            params = {
                'instId': symbol,
                'bar': okx_tf,
                'limit': str(min(limit, 300))
            }
            # Note: OKX doesn't support date range parameters like other exchanges
            # It returns recent data by default, we'll filter client-side if needed
        elif exchange_name == 'bybit':
            bybit_intervals = {'1m': '1', '5m': '5', '15m': '15', '1h': '60', '4h': '240', '1d': 'D'}
            params = {
                'category': 'spot',
                'symbol': symbol,
                'interval': bybit_intervals.get(timeframe, '60'),
                'limit': min(limit, 200),
                'start': int(start_time.timestamp() * 1000),
                'end': int(end_time.timestamp() * 1000)
            }
        elif exchange_name == 'kraken':
            # Convert timeframe to minutes for Kraken
            tf_minutes = {'1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240, '1d': 1440, '1w': 10080}.get(timeframe, 60)
            params = {
                'pair': symbol,
                'interval': tf_minutes
            }
            # Note: Kraken's 'since' parameter doesn't filter by start date like other exchanges
            # It returns recent data and 'since' is used for pagination
            # We'll filter the results manually after fetching

        response = requests.get(base_url, params=params, timeout=10)

        # Better error handling for HTTP errors
        if response.status_code != 200:
            try:
                error_data = response.json()
                if exchange_name == 'binance':
                    error_msg = error_data.get('msg', f'HTTP {response.status_code}')
                    error_code = error_data.get('code', response.status_code)
                elif exchange_name == 'kucoin':
                    error_msg = error_data.get('msg', f'HTTP {response.status_code}')
                    error_code = error_data.get('code', response.status_code)
                elif exchange_name == 'okx':
                    error_msg = error_data.get('msg', f'HTTP {response.status_code}')
                    error_code = error_data.get('code', response.status_code)
                elif exchange_name == 'bybit':
                    error_msg = error_data.get('retMsg', f'HTTP {response.status_code}')
                    error_code = error_data.get('retCode', response.status_code)
                else:
                    error_msg = f'HTTP {response.status_code}'
                    error_code = response.status_code
                cprint(f"    [ERROR] {exchange_name} API HTTP {response.status_code}: {error_msg} (code: {error_code})", "red")
            except:
                error_text = response.text[:200] if response.text else 'No error message'
                cprint(f"    [ERROR] {exchange_name} API HTTP {response.status_code}: {error_text}", "red")
            return None

        data = response.json()

        # Parse response based on exchange with better error handling
        df_data = []
        
        if exchange_name == 'binance':
            # Check if Binance returned an error in the JSON
            if isinstance(data, dict) and 'code' in data:
                error_msg = data.get('msg', 'Unknown error')
                error_code = data.get('code', 'Unknown')
                cprint(f"    [ERROR] Binance API error: {error_msg} (code: {error_code})", "red")
                return None
            
            if not isinstance(data, list) or len(data) == 0:
                cprint(f"    [ERROR] Binance returned empty or invalid data", "red")
                return None
                
            try:
                for kline in data:
                    if len(kline) < 6:
                        cprint(f"    [WARN] Binance kline has insufficient data: {len(kline)} fields (expected 6+)", "yellow")
                        continue
                    df_data.append({
                        'timestamp': pd.to_datetime(int(kline[0]), unit='ms'),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })
            except (ValueError, IndexError, TypeError) as e:
                cprint(f"    [ERROR] Binance data parsing error: {str(e)}", "red")
                cprint(f"    [DEBUG] Sample kline data: {data[0] if data else 'No data'}", "yellow")
                return None
                
        elif exchange_name == 'kucoin':
            if data.get('code') != '200000':
                error_msg = data.get('msg', 'Unknown error')
                error_code = data.get('code', 'Unknown')
                cprint(f"    [ERROR] KuCoin API error: {error_msg} (code: {error_code})", "red")
                return None
                
            if not data.get('data'):
                cprint(f"    [ERROR] KuCoin API returned no data", "red")
                return None
                
            try:
                # KuCoin API format: [Time, Open, Close, High, Low, Volume, Turnover]
                for candle in data['data']:
                    if len(candle) < 6:
                        cprint(f"    [WARN] KuCoin candle has insufficient data: {len(candle)} fields (expected 6+)", "yellow")
                        continue
                    df_data.append({
                        'timestamp': pd.to_datetime(int(candle[0]), unit='s'),
                        'open': float(candle[1]),      # Open - correct
                        'close': float(candle[2]),     # Close (was incorrectly mapped as high)
                        'high': float(candle[3]),      # High (was incorrectly mapped as low)
                        'low': float(candle[4]),       # Low (was incorrectly mapped as close)
                        'volume': float(candle[5])     # Volume - correct
                    })
            except (ValueError, IndexError, TypeError) as e:
                cprint(f"    [ERROR] KuCoin data parsing error: {str(e)}", "red")
                cprint(f"    [DEBUG] Sample candle data: {data['data'][0] if data.get('data') else 'No data'}", "yellow")
                return None
                
        elif exchange_name == 'okx':
            if data.get('code') != '0':
                error_msg = data.get('msg', 'Unknown error')
                error_code = data.get('code', 'Unknown')
                cprint(f"    [ERROR] OKX API error: {error_msg} (code: {error_code})", "red")
                return None
                
            if not data.get('data'):
                cprint(f"    [ERROR] OKX API returned no data", "red")
                return None
                
            try:
                for candle in data['data']:
                    if len(candle) < 6:
                        cprint(f"    [WARN] OKX candle has insufficient data: {len(candle)} fields (expected 6+)", "yellow")
                        continue

                    timestamp = pd.to_datetime(int(candle[0]), unit='ms')
                    # Filter to our date range (OKX doesn't support date filtering)
                    if timestamp >= start_time and timestamp <= end_time:
                        df_data.append({
                            'timestamp': timestamp,
                            'open': float(candle[1]),
                            'high': float(candle[2]),
                            'low': float(candle[3]),
                            'close': float(candle[4]),
                            'volume': float(candle[5])
                        })
            except (ValueError, IndexError, TypeError) as e:
                cprint(f"    [ERROR] OKX data parsing error: {str(e)}", "red")
                cprint(f"    [DEBUG] Sample candle data: {data['data'][0] if data.get('data') else 'No data'}", "yellow")
                return None

            if not df_data:
                cprint(f"    [WARN] OKX returned data but none in our date range ({start_time.date()} to {end_time.date()})", "yellow")
                if data.get('data'):
                    first_ts = pd.to_datetime(int(data['data'][0][0]), unit='ms')
                    last_ts = pd.to_datetime(int(data['data'][-1][0]), unit='ms')
                    cprint(f"    [DEBUG] OKX data range: {first_ts} to {last_ts}", "yellow")
                return None
                
        elif exchange_name == 'bybit':
            if data.get('retCode') != 0:
                error_msg = data.get('retMsg', 'Unknown error')
                error_code = data.get('retCode', 'Unknown')
                cprint(f"    [ERROR] Bybit API error: {error_msg} (code: {error_code})", "red")
                return None
                
            if not data.get('result', {}).get('list'):
                cprint(f"    [ERROR] Bybit API returned no data", "red")
                return None
                
            try:
                for kline in data['result']['list']:
                    if len(kline) < 6:
                        cprint(f"    [WARN] Bybit kline has insufficient data: {len(kline)} fields (expected 6+)", "yellow")
                        continue
                    df_data.append({
                        'timestamp': pd.to_datetime(int(kline[0]), unit='ms'),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })
            except (ValueError, IndexError, TypeError) as e:
                cprint(f"    [ERROR] Bybit data parsing error: {str(e)}", "red")
                cprint(f"    [DEBUG] Sample kline data: {data['result']['list'][0] if data.get('result', {}).get('list') else 'No data'}", "yellow")
                return None

        elif exchange_name == 'kraken':
            # Kraken returns error as list, empty list means no error
            if data.get('error') and len(data.get('error', [])) > 0:
                error_msg = data.get('error', ['Unknown error'])
                cprint(f"    [ERROR] Kraken API error: {error_msg}", "red")
                return None

            if not data.get('result'):
                cprint(f"    [ERROR] Kraken API returned no result data", "red")
                cprint(f"    [DEBUG] Kraken response: {data}", "yellow")
                return None

            pair_data = list(data['result'].values())
            if not pair_data or len(pair_data) == 0:
                cprint(f"    [ERROR] Kraken API returned empty pair data", "red")
                cprint(f"    [DEBUG] Kraken result keys: {list(data['result'].keys())}", "yellow")
                return None

            # Kraken returns list of OHLC data for each pair
            ohlc_data = pair_data[0]  # Get data for first (only) pair
            if not isinstance(ohlc_data, list) or len(ohlc_data) == 0:
                cprint(f"    [ERROR] Kraken API returned invalid OHLC data format", "red")
                cprint(f"    [DEBUG] Kraken OHLC data type: {type(ohlc_data)}, length: {len(ohlc_data) if hasattr(ohlc_data, '__len__') else 'N/A'}", "yellow")
                cprint(f"    [DEBUG] Kraken OHLC sample: {ohlc_data[:2] if isinstance(ohlc_data, list) and len(ohlc_data) > 0 else 'No data'}", "yellow")
                return None

            try:
                # Kraken OHLC format: [time, open, high, low, close, vwap, volume, count]
                for ohlc in ohlc_data[-limit:]:  # Get last 'limit' records
                    if len(ohlc) < 8:
                        cprint(f"    [WARN] Kraken OHLC has insufficient data: {len(ohlc)} fields (expected 8+)", "yellow")
                        continue

                    timestamp = pd.to_datetime(int(ohlc[0]), unit='s')
                    # Filter to our date range since Kraken doesn't support date filtering in API
                    if timestamp >= start_time and timestamp <= end_time:
                        df_data.append({
                            'timestamp': timestamp,
                            'open': float(ohlc[1]),
                            'high': float(ohlc[2]),
                            'low': float(ohlc[3]),
                            'close': float(ohlc[4]),
                            'volume': float(ohlc[6])  # Volume is at index 6
                        })
            except (ValueError, IndexError, TypeError) as e:
                cprint(f"    [ERROR] Kraken data parsing error: {str(e)}", "red")
                cprint(f"    [DEBUG] Kraken sample OHLC: {ohlc_data[0] if ohlc_data else 'No data'}", "yellow")
                return None

            if not df_data:
                cprint(f"    [WARN] Kraken returned data but none in our date range ({start_time.date()} to {end_time.date()})", "yellow")
                cprint(f"    [DEBUG] Kraken data range: {pd.to_datetime(int(ohlc_data[0][0]), unit='s')} to {pd.to_datetime(int(ohlc_data[-1][0]), unit='s')}", "yellow")
                return None

        if df_data:
            df = pd.DataFrame(df_data)
            # Ensure timestamp is properly parsed as datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        else:
            cprint(f"    [ERROR] {exchange_name} returned no valid data after parsing", "red")
            return None

    except requests.exceptions.Timeout:
        cprint(f"    [ERROR] {exchange_name} request timed out after 10 seconds", "red")
        return None
    except requests.exceptions.RequestException as e:
        cprint(f"    [ERROR] {exchange_name} network error: {str(e)}", "red")
        return None
    except Exception as e:
        cprint(f"    [ERROR] Failed to fetch from {exchange_name}: {str(e)}", "red")
        import traceback
        cprint(f"    [DEBUG] Traceback: {traceback.format_exc()}", "yellow")
        return None

def collect_specific_period_data(symbol='BTC', start_date=None, end_date=None, timeframe='1h'):
    """
    Collect OHLCV data for a specific date range and save as BTC-USD-{timeframe}.csv

    Args:
        symbol: Trading symbol (e.g., 'BTC', 'ETH')
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        timeframe: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)

    Returns:
        pandas.DataFrame: Collected OHLCV data
    """
    cprint(f"\n[COLLECT] Collecting {symbol} {timeframe} data from {start_date} to {end_date}", "white", "on_blue")

    # Parse dates
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    # Calculate total days needed (ensure at least 90 days like ohlcv_collector)
    total_days = max((end_dt - start_dt).days, 90)

    cprint(f"[INFO] Collecting {total_days} days of {timeframe} data (minimum 90 days)...", "cyan")

    # Always use multi-source collection for better data coverage and longer periods
    cprint("[METHOD] Using multi-source collection for comprehensive data", "cyan")

    # Collect data for the specific period we want
    data = collect_multi_source_ohlcv_for_period(symbol, start_dt, end_dt, timeframe)

    if data is None or data.empty:
        cprint("[ERROR] Failed to collect any data", "white", "on_red")
        return None

    # Sort by timestamp
    data = data.sort_values('timestamp').reset_index(drop=True)

    cprint(f"[SUCCESS] Collected {len(data)} candles from {data['timestamp'].min()} to {data['timestamp'].max()}", "white", "on_green")

    # Output directory and filename (BTC-USD-{timeframe}.csv)
    output_dir = "src/data/rbi"
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"BTC-USD-{timeframe}.csv"
    output_path = os.path.join(output_dir, output_filename)

    # Save to CSV in the format expected by backtests (overwrites existing file)
    data_to_save = data[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
    data_to_save['timestamp'] = data_to_save['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    data_to_save.to_csv(output_path, index=False)

    cprint(f"[SAVE] Data saved to: {output_path} (OVERWRITTEN)", "white", "on_green")

    # Show some statistics
    price_change = (data['close'].iloc[-1] - data['open'].iloc[0]) / data['open'].iloc[0] * 100
    trend = "UPTREND" if price_change > 0 else "DOWNTREND"

    cprint(f"[STATS] Price change: {price_change:.2f}% ({trend})", "green" if price_change > 0 else "red")
    cprint(f"[STATS] Volatility (std): ${data['close'].std():.2f}", "cyan")
    cprint(f"[STATS] Volume avg: {data['volume'].mean():.0f}", "cyan")
    cprint(f"[STATS] Data points: {len(data)}", "cyan")

    return data

def main():
    parser = argparse.ArgumentParser(description='Collect OHLCV data for specific time periods and save as BTC-USD-{timeframe}.csv')
    parser.add_argument('--symbol', default='BTC', help='Trading symbol (default: BTC)')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--timeframe', default='1h', help='Timeframe (1m, 5m, 15m, 1h, 4h, 1d)')

    args = parser.parse_args()

    try:
        data = collect_specific_period_data(
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            timeframe=args.timeframe
        )

        if data is not None:
            cprint(f"\n[COMPLETE] Successfully collected data and saved as BTC-USD-{args.timeframe}.csv!", "white", "on_green")
            cprint(f"Your TriplexSupertrend strategy is now ready to test in this new market condition.", "green")
            cprint(f"Run your backtest script to see how the strategy performs in this time period.", "cyan")
        else:
            cprint(f"\n[FAILED] Could not collect data for the specified period.", "white", "on_red")
            sys.exit(1)

    except KeyboardInterrupt:
        cprint(f"\n[EXIT] Collection interrupted by user", "yellow")
    except Exception as e:
        cprint(f"\n[ERROR] {str(e)}", "white", "on_red")
        sys.exit(1)

if __name__ == "__main__":
    main()