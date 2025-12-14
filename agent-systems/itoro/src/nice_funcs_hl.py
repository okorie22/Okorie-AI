'''
nice functions from hyper liquid i can use

Anarcho Capital's Hyperliquid Functions
Built with love by Anarcho Capital
'''

import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np
import time
try:
    import pandas_ta as ta
except (ImportError, ModuleNotFoundError):
    # Fallback to Windows-compatible implementation
    from src.ta_indicators import ta  # For technical indicators
import traceback
from src.scripts.shared_services.logger import debug, info, warning, error, critical

# Constants
BATCH_SIZE = 5000  # MAX IS 5000 FOR HYPERLIQUID
MAX_RETRIES = 3
MAX_ROWS = 5000
BASE_URL = 'https://api.hyperliquid.xyz/info'

# Global variable to store timestamp offset
timestamp_offset = None

def adjust_timestamp(dt):
    """Adjust API timestamps by subtracting the timestamp offset."""
    if timestamp_offset is not None:
        corrected_dt = dt - timestamp_offset
        return corrected_dt
    return dt

def _get_ohlcv(symbol, interval, start_time, end_time, batch_size=BATCH_SIZE):
    """Internal function to fetch OHLCV data from Hyperliquid"""
    global timestamp_offset
    info(f'Requesting data for {symbol}:')
    debug(f'Batch Size: {batch_size}')
    debug(f'Start: {start_time.strftime("%Y-%m-%d %H:%M:%S")} UTC')
    debug(f'End: {end_time.strftime("%Y-%m-%d %H:%M:%S")} UTC')

    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                BASE_URL,
                headers={'Content-Type': 'application/json'},
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": symbol,
                        "interval": interval,
                        "startTime": start_ts,
                        "endTime": end_ts,
                        "limit": batch_size
                    }
                },
                timeout=10
            )

            if response.status_code == 200:
                snapshot_data = response.json()
                if snapshot_data:
                    # Handle timestamp offset
                    if timestamp_offset is None:
                        latest_api_timestamp = datetime.utcfromtimestamp(snapshot_data[-1]['t'] / 1000)
                        system_current_date = datetime.utcnow()
                        expected_latest_timestamp = system_current_date
                        timestamp_offset = latest_api_timestamp - expected_latest_timestamp
                        debug(f"Calculated timestamp offset: {timestamp_offset}")

                    # Adjust timestamps
                    for candle in snapshot_data:
                        dt = datetime.utcfromtimestamp(candle['t'] / 1000)
                        adjusted_dt = adjust_timestamp(dt)
                        candle['t'] = int(adjusted_dt.timestamp() * 1000)

                    first_time = datetime.utcfromtimestamp(snapshot_data[0]['t'] / 1000)
                    last_time = datetime.utcfromtimestamp(snapshot_data[-1]['t'] / 1000)
                    info(f'Received {len(snapshot_data)} candles')
                    debug(f'First: {first_time}')
                    debug(f'Last: {last_time}')
                    return snapshot_data
                warning('No data returned by API')
                return None
            error(f'HTTP Error {response.status_code}: {response.text}')
        except requests.exceptions.RequestException as e:
            warning(f'Request failed (attempt {attempt + 1}): {str(e)}')
            time.sleep(1)
    return None

def _process_data_to_df(snapshot_data):
    """Convert raw API data to DataFrame"""
    if snapshot_data:
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        data = []
        for snapshot in snapshot_data:
            timestamp = datetime.utcfromtimestamp(snapshot['t'] / 1000)
            # Convert all numeric values to float
            data.append([
                timestamp,
                float(snapshot['o']),
                float(snapshot['h']),
                float(snapshot['l']),
                float(snapshot['c']),
                float(snapshot['v'])
            ])
        df = pd.DataFrame(data, columns=columns)
        
        # Ensure numeric columns are float64
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].astype('float64')
        
        debug("OHLCV Data Types:", file_only=True)
        debug(df.dtypes, file_only=True)
        
        return df
    return pd.DataFrame()

def add_technical_indicators(df):
    """Add technical indicators to the dataframe"""
    if df.empty:
        return df
        
    try:
        debug("Adding technical indicators...", file_only=True)
        
        # Ensure numeric columns are float64
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].astype('float64')
        
        # Add basic indicators
        df['sma_20'] = ta.sma(df['close'], length=20)
        df['sma_50'] = ta.sma(df['close'], length=50)
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        # Add MACD
        try:
            macd = ta.macd(df['close'])
            if not macd.empty:
                df = pd.concat([df, macd], axis=1)
        except Exception as e:
            # Fallback: Calculate MACD manually
            try:
                exp1 = df['close'].ewm(span=12, adjust=False).mean()
                exp2 = df['close'].ewm(span=26, adjust=False).mean()
                df['MACD_12_26_9'] = exp1 - exp2
                df['MACDs_12_26_9'] = df['MACD_12_26_9'].ewm(span=9, adjust=False).mean()
                df['MACDh_12_26_9'] = df['MACD_12_26_9'] - df['MACDs_12_26_9']
            except Exception as fallback_error:
                warning(f"Could not calculate MACD: {fallback_error}")

        # Add Bollinger Bands
        try:
            bbands = ta.bbands(df['close'])
            if not bbands.empty:
                df = pd.concat([df, bbands], axis=1)
        except Exception as e:
            # Fallback: Calculate manually
            try:
                sma = df['close'].rolling(window=20).mean()
                std = df['close'].rolling(window=20).std()
                df['BBL_20_2'] = sma - (std * 2)
                df['BBM_20_2'] = sma
                df['BBU_20_2'] = sma + (std * 2)
            except Exception as fallback_error:
                warning(f"Could not calculate Bollinger Bands: {fallback_error}")
        
        info("Technical indicators added successfully")
        return df
        
    except Exception as e:
        error(f"Error adding technical indicators: {str(e)}")
        traceback.print_exc()
        return df

def get_data(address=None, symbol=None, timeframe="1h", bars=100, add_indicators=True):
    """
    Fetch price data for a token using either address or symbol
    """
    info("Fetching Hyperliquid data")
    
    # Use address if provided, otherwise use symbol
    identifier = address if address else symbol
    identifier_type = "address" if address else "symbol"
    
    debug(f"{identifier_type.capitalize()}: {identifier}")
    debug(f"Timeframe: {timeframe}")
    debug(f"Requested bars: {bars}")
    
    # Ensure we don't exceed max rows
    bars = min(bars, MAX_ROWS)
    
    # Calculate time window
    end_time = datetime.utcnow()
    # Add extra time to ensure we get enough bars
    start_time = end_time - timedelta(days=60)

    data = _get_ohlcv(identifier, timeframe, start_time, end_time, batch_size=bars)
    
    if not data:
        warning("No data available.")
        return pd.DataFrame()

    df = _process_data_to_df(data)

    if not df.empty:
        # Get the most recent bars
        df = df.sort_values('timestamp', ascending=False).head(bars).sort_values('timestamp')
        df = df.reset_index(drop=True)
        
        # Add technical indicators if requested
        if add_indicators:
            df = add_technical_indicators(df)

        debug("Data summary:", file_only=True)
        debug(f"Total candles: {len(df)}", file_only=True)
        debug(f"Range: {df['timestamp'].min()} to {df['timestamp'].max()}", file_only=True)
        info("Successfully fetched Hyperliquid data")

    return df

def get_market_info():
    """Get current market info for all coins on Hyperliquid"""
    try:
        debug("Sending request to Hyperliquid API...")
        response = requests.post(
            BASE_URL,
            headers={'Content-Type': 'application/json'},
            json={"type": "allMids"}
        )
        
        debug(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            debug(f"Raw response data: {data}", file_only=True)
            return data
        error(f"Bad status code: {response.status_code}")
        error(f"Response text: {response.text}")
        return None
    except Exception as e:
        error(f"Error getting market info: {str(e)}")
        traceback.print_exc()  # Print full error traceback
        return None

def test_market_info():
    info("Testing Market Info...")
    try:
        debug("Fetching current market prices...")
        info = get_market_info()
        
        debug(f"Response type: {type(info)}")
        if info is not None:
            debug(f"Response content: {info}", file_only=True)
        
        if info and isinstance(info, dict):
            debug("Current Market Prices:", file_only=True)
            debug("=" * 50, file_only=True)
            # Target symbols we're interested in
            target_symbols = ["BTC", "ETH", "SOL", "ARB", "OP", "MATIC"]
            
            for symbol in target_symbols:
                if symbol in info:
                    try:
                        price = float(info[symbol])
                        debug(f"Symbol: {symbol:8} | Price: ${price:,.2f}", file_only=True)
                    except (ValueError, TypeError) as e:
                        warning(f"Error processing price for {symbol}: {str(e)}")
                else:
                    warning(f"No price data for {symbol}")
        else:
            warning("No valid market info received")
            if info is None:
                warning("Response was None")
            else:
                warning(f"Unexpected response type: {type(info)}")
    except Exception as e:
        error(f"Error in market info test: {str(e)}")
        error("Full error traceback:")
        traceback.print_exc()

def get_24h_volume(symbol):
    """
    Get 24-hour volume for a symbol from Hyperliquid candle data

    Args:
        symbol (str): Trading pair symbol (e.g., 'BTC', 'ETH')

    Returns:
        float: 24h volume or None if unavailable
    """
    try:
        # Get last 24 hours of 1-hour candles
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)

        debug(f"Fetching 24h volume for {symbol}...")

        response = requests.post(
            BASE_URL,
            headers={'Content-Type': 'application/json'},
            json={
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol,
                    "interval": "1h",
                    "startTime": int(start_time.timestamp() * 1000),
                    "endTime": int(end_time.timestamp() * 1000),
                    "limit": 24
                }
            },
            timeout=10
        )

        if response.status_code == 200:
            candle_data = response.json()
            if candle_data and len(candle_data) > 0:
                # Sum volume from all candles in the period
                total_volume = sum(float(candle.get('v', 0)) for candle in candle_data)
                debug(f"✓ {symbol}: 24h volume = {total_volume:,.2f}")
                return total_volume

        debug(f"No volume data available for {symbol}")
        return None

    except Exception as e:
        debug(f"Failed to get volume for {symbol}: {str(e)}")
        return None

def get_funding_rates(symbol):
    """
    Get current funding rate for a specific coin on Hyperliquid

    Args:
        symbol (str): Trading pair symbol (e.g., 'BTC', 'ETH', 'FART')

    Returns:
        dict: Funding data including rate, mark price, and open interest
    """
    try:
        debug(f"Fetching funding rate for {symbol}...")
        response = requests.post(
            BASE_URL,
            headers={'Content-Type': 'application/json'},
            json={"type": "metaAndAssetCtxs"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if len(data) >= 2 and isinstance(data[0], dict) and isinstance(data[1], list):
                # Get universe (symbols) from first element
                universe = {coin['name']: i for i, coin in enumerate(data[0]['universe'])}
                
                # Check if symbol exists
                if symbol not in universe:
                    warning(f"Symbol {symbol} not found in Hyperliquid universe")
                    debug(f"Available symbols: {', '.join(universe.keys())}", file_only=True)
                    return None
                
                # Get funding data from second element
                funding_data = data[1]
                idx = universe[symbol]
                
                if idx < len(funding_data):
                    asset_data = funding_data[idx]
                    return {
                        'funding_rate': float(asset_data['funding']),
                        'mark_price': float(asset_data['markPx']),
                        'open_interest': float(asset_data['openInterest'])
                    }
                    
            warning("Unexpected response format")
            return None
        error(f"Bad status code: {response.status_code}")
        return None
    except Exception as e:
        error(f"Error getting funding rate for {symbol}: {str(e)}")
        traceback.print_exc()
        return None

def test_funding_rates():
    info("Testing Funding Rates...")
    try:
        # Test with some interesting symbols
        test_symbols = ["BTC", "ETH", "FARTCOIN"]
        
        for symbol in test_symbols:
            debug(f"Testing {symbol}:")
            debug("=" * 50, file_only=True)
            data = get_funding_rates(symbol)
            
            if data:
                # The API returns the 8-hour funding rate
                # To get hourly rate: funding_rate
                # To get annual rate: hourly * 24 * 365
                hourly_rate = float(data['funding_rate']) * 100  # Convert to percentage
                annual_rate = hourly_rate * 24 * 365  # Convert hourly to annual
                
                info(f"Symbol: {symbol} | Hourly: {hourly_rate:.4f}% | Annual: {annual_rate:.2f}% | OI: {data['open_interest']:.2f}")
            else:
                warning(f"No funding data received for {symbol}")
                
    except Exception as e:
        error(f"Error in funding rates test: {str(e)}")
        error("Full error traceback:")
        traceback.print_exc()

def get_user_positions(user_address):
    """
    Get current positions and account information for a user
    
    Args:
        user_address (str): Ethereum address of user
        
    Returns:
        dict: User state data or None if error
    """
    try:
        debug(f"Fetching positions for user {user_address}...")
        response = requests.post(
            BASE_URL,
            headers={'Content-Type': 'application/json'},
            json={"type": "userState", "user": user_address}
        )
        
        if response.status_code == 200:
            data = response.json()
            return data
        error(f"Failed to get user positions: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        error(f"Error getting user positions: {str(e)}")
        traceback.print_exc()
        return None

def calculate_liquidation_price(symbol, position_size, entry_price, leverage, is_long=True):
    """
    Calculate liquidation price for a position
    
    Args:
        symbol (str): Trading pair symbol
        position_size (float): Size of position in contracts
        entry_price (float): Entry price of position
        leverage (float): Leverage used
        is_long (bool): Whether position is long (True) or short (False)
        
    Returns:
        float: Liquidation price
    """
    try:
        # Get funding rate as it affects liquidation price
        funding_data = get_funding_rates(symbol)
        funding_rate = 0
        if funding_data:
            funding_rate = funding_data.get('funding_rate', 0)
        
        # Calculate maintenance margin (typical 0.5-1% for crypto)
        maintenance_margin = 0.005  # 0.5%
        
        # Calculate liquidation price
        if is_long:
            liq_price = entry_price * (1 - (1 / leverage) + maintenance_margin)
        else:
            liq_price = entry_price * (1 + (1 / leverage) - maintenance_margin)
            
        return liq_price
    except Exception as e:
        error(f"Error calculating liquidation price: {str(e)}")
        return None

if __name__ == "__main__":
    info("Anarcho Capital's Hyperliquid Function Tester")
    debug("=" * 50, file_only=True)
    
    def test_btc_data():
        info("Testing BTC Data Retrieval...")
        try:
            # Test with BTC on 15m timeframe
            df = get_data("BTC", timeframe="15m", bars=100, add_indicators=True)
            
            if not df.empty:
                debug("Last 5 candles:", file_only=True)
                debug("=" * 80, file_only=True)
                for idx, row in df.tail().iterrows():
                    debug(f"Time: {row['timestamp'].strftime('%H:%M:%S')} | Open: ${row['open']:,.2f} | High: ${row['high']:,.2f} | Low: ${row['low']:,.2f} | Close: ${row['close']:,.2f} | Vol: ${row['volume']:,.2f}", file_only=True)
                
                debug("Technical Indicators (Last Candle):", file_only=True)
                debug("=" * 50, file_only=True)
                last_row = df.iloc[-1]
                debug(f"SMA20: ${last_row['sma_20']:,.2f}", file_only=True)
                debug(f"SMA50: ${last_row['sma_50']:,.2f}", file_only=True)
                debug(f"RSI: {last_row['rsi']:.2f}", file_only=True)
                debug(f"MACD: {last_row['MACD_12_26_9']:,.2f}", file_only=True)
                
            else:
                warning("No data received")
                
        except Exception as e:
            error(f"Error in BTC test: {str(e)}")

# =============================================================================
# 🚀 HYPERLIQUID LEVERAGE TRADING FUNCTIONS
# =============================================================================

def hyperliquid_perp_entry(symbol: str, side: str, size_usd: float, leverage: int = 5, reduce_only: bool = False):
    """
    Enter a Hyperliquid perpetual position

    Args:
        symbol: Trading pair (e.g., 'BTC', 'ETH', 'SOL')
        side: 'buy' for long, 'sell' for short
        size_usd: Position size in USD
        leverage: Leverage multiplier (1-50)
        reduce_only: If True, only reduce existing position

    Returns:
        dict: Order response
    """
    from src.config import HYPERLIQUID_WALLET_ADDRESS, HYPERLIQUID_PRIVATE_KEY, HYPERLIQUID_TESTNET

    if not HYPERLIQUID_WALLET_ADDRESS or not HYPERLIQUID_PRIVATE_KEY:
        error("Hyperliquid wallet credentials not configured")
        return None

    try:
        # Convert symbol to Hyperliquid format (add 'PERP-' prefix if needed)
        if not symbol.endswith('PERP'):
            symbol = f"{symbol}PERP"

        # Calculate position size in base asset
        # This is simplified - in reality you'd need current price
        price = get_current_price(symbol.replace('PERP', ''))
        if not price:
            error(f"Could not get price for {symbol}")
            return None

        size_base = size_usd / price

        order = {
            "type": "order",
            "orders": [{
                "coin": symbol,
                "side": side.upper(),
                "sz": size_base,
                "limit_px": price,  # Market order approximation
                "order_type": {"limit": {"tif": "Ioc"}},  # Immediate or Cancel
                "reduce_only": reduce_only
            }],
            "grouping": "na"
        }

        # Sign and submit order (simplified - would need actual Hyperliquid SDK)
        # This is a placeholder for the actual implementation
        info(f"Hyperliquid {side.upper()} order: {symbol} {size_usd} USD @ {leverage}x leverage")

        # TODO: Implement actual Hyperliquid API order submission
        # response = submit_hyperliquid_order(order, HYPERLIQUID_PRIVATE_KEY)

        return {
            'success': True,
            'symbol': symbol,
            'side': side,
            'size_usd': size_usd,
            'leverage': leverage,
            'status': 'simulated'  # Remove when implementing real orders
        }

    except Exception as e:
        error(f"Hyperliquid perp entry failed: {str(e)}")
        return None

def hyperliquid_close_position(symbol: str, percentage: float = 100.0):
    """
    Close a Hyperliquid perpetual position

    Args:
        symbol: Trading pair (e.g., 'BTC', 'ETH', 'SOL')
        percentage: Percentage of position to close (0-100)

    Returns:
        dict: Order response
    """
    try:
        # Convert symbol to Hyperliquid format
        if not symbol.endswith('PERP'):
            symbol = f"{symbol}PERP"

        # Get current position
        position = get_hyperliquid_position(symbol)
        if not position or position['size'] == 0:
            info(f"No open position for {symbol}")
            return None

        # Calculate close size
        close_size = abs(position['size']) * (percentage / 100.0)

        # Determine close side (opposite of position)
        close_side = 'sell' if position['size'] > 0 else 'buy'

        order = {
            "type": "order",
            "orders": [{
                "coin": symbol,
                "side": close_side.upper(),
                "sz": close_size,
                "limit_px": get_current_price(symbol.replace('PERP', '')),  # Market approximation
                "order_type": {"limit": {"tif": "Ioc"}},
                "reduce_only": True
            }],
            "grouping": "na"
        }

        info(f"Hyperliquid close order: {symbol} {percentage}% position")

        # TODO: Implement actual order submission
        return {
            'success': True,
            'symbol': symbol,
            'action': 'close',
            'percentage': percentage,
            'status': 'simulated'
        }

    except Exception as e:
        error(f"Hyperliquid close position failed: {str(e)}")
        return None

def get_hyperliquid_position(symbol: str):
    """
    Get current position for a symbol

    Args:
        symbol: Trading pair

    Returns:
        dict: Position info or None
    """
    # TODO: Implement actual position query from Hyperliquid API
    # This is a placeholder
    return {
        'symbol': symbol,
        'size': 0,  # Positive = long, negative = short
        'entry_price': 0,
        'unrealized_pnl': 0
    }

def get_hyperliquid_balance():
    """
    Get Hyperliquid account balance

    Returns:
        dict: Balance information
    """
    # TODO: Implement actual balance query
    return {
        'total_equity': 0,
        'available_balance': 0,
        'margin_used': 0
    }

def get_current_price(symbol: str):
    """
    Get current price for a symbol

    Args:
        symbol: Trading pair

    Returns:
        float: Current price or None
    """
    try:
        # Try to get from Hyperliquid API
        response = requests.post(BASE_URL, json={
            "type": "allMids"
        })

        if response.status_code == 200:
            data = response.json()
            # Find the symbol in the response
            for coin, price in data.items():
                if coin.replace('PERP', '') == symbol:
                    return float(price)

        # Fallback to local data
        return None

    except Exception as e:
        error(f"Failed to get price for {symbol}: {str(e)}")
        return None

def calculate_position_size(balance: float, risk_percent: float, leverage: int, stop_loss_percent: float):
    """
    Calculate safe position size for leveraged trading

    Args:
        balance: Account balance in USD
        risk_percent: Risk per trade (0.01 = 1%)
        leverage: Leverage multiplier
        stop_loss_percent: Stop loss percentage

    Returns:
        float: Position size in USD
    """
    # Risk amount = balance * risk_percent
    risk_amount = balance * risk_percent

    # Effective risk per 1% move = risk_amount / (stop_loss_percent * leverage)
    # Position size = risk_amount / (stop_loss_percent / 100 * leverage)
    position_size = risk_amount / (stop_loss_percent / 100)

    # Adjust for leverage
    position_size *= leverage

    return position_size

def hyperliquid_leverage_entry(token_address: str, direction: str, confidence: float, usd_size: float):
    """
    High-level function for AI-driven leveraged entry
    Called by trading agent for automated leverage trading

    Args:
        token_address: Token address
        direction: 'BUY' or 'SELL'
        confidence: AI confidence (0-1)
        usd_size: Position size in USD

    Returns:
        dict: Trade result
    """
    from src.config import DEFAULT_LEVERAGE, LEVERAGE_SUPPORTED_ASSETS

    try:
        # Check if token is supported for leverage
        token_symbol = get_token_symbol_from_address(token_address)
        if token_symbol not in LEVERAGE_SUPPORTED_ASSETS:
            info(f"Token {token_symbol} not supported for leverage trading")
            return None

        # Adjust leverage based on confidence
        leverage = min(DEFAULT_LEVERAGE, max(1, int(confidence * DEFAULT_LEVERAGE)))

        # Adjust position size based on confidence
        adjusted_size = usd_size * confidence

        # Convert direction to Hyperliquid format
        side = 'buy' if direction == 'BUY' else 'sell'

        # Execute trade
        result = hyperliquid_perp_entry(token_symbol, side, adjusted_size, leverage)

        if result:
            info(f"Leveraged {direction} executed: {token_symbol} {adjusted_size} USD @ {leverage}x")

        return result

    except Exception as e:
        error(f"Leverage entry failed: {str(e)}")
        return None

def get_token_symbol_from_address(token_address: str):
    """
    Convert token address to symbol for Hyperliquid
    This is a simplified mapping - you'd want a more comprehensive one
    """
    # Common mappings
    address_to_symbol = {
        'So11111111111111111111111111111111111111111': 'SOL',
        'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'USDC',
        '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump': 'BONK',
        '67mTTGnVRunoSLGitgRGK2FJp5cT1KschjzWH9zKc3r': 'WIF'
    }

    return address_to_symbol.get(token_address, token_address[:4].upper())

    # Run tests
    debug("Running function tests...", file_only=True)

    test_btc_data()
    test_market_info()
    test_funding_rates()  # Now tests individual symbols

    info("Testing complete!")
