"""
Anarcho Capital's OHLCV Data Collector
Collects Open-High-Low-Close-Volume data for specified tokens
Built with love by Anarcho Capital

⚠️ PHASE 1 REFACTOR WARNING ⚠️
This script is now for OFFLINE ANALYTICS ONLY.
Do NOT use this in runtime trading agents as it consumes Birdeye API credits.
Use OptimizedPriceService.get_price() for real-time price fetching during trading.
"""

from src.config import *
import pandas as pd
from datetime import datetime
import os
from termcolor import colored, cprint
import time
from src.scripts.shared_services.logger import debug, info, warning, error, critical
import numpy as np
import requests
import random
import socket
socket.setdefaulttimeout(15)  # Increase timeout

# Token name cache
TOKEN_NAMES = {
    'VFdxjTdFzXrYr3ivWyf64NuXo9U7vdPK7AG7idnNZJV': 'SolChicks',
    'CR2L1ob96JGWQkdFbt8rLwqdLLmqFwjcNGL2eFBn1RPt': 'CHILL GUY',
    '2HdzfUiFWfZHZ544ynffeneuibbDK6biCdjovejr8ez9': 'MOODENG',
    'C94njgTrKMQBmgqe23EGLrtPgfvcjWtqBBvGQ7Cjiank': 'WIF',
    '67mTTGnVRunoSLGitgRGK2FJp5cT1KschjzWH9zKc3r': 'BONK',
    '9YnfbEaXPaPmoXnKZFmNH8hzcLyjbRf56MQP7oqGpump': 'PUMP',
    'DayN9FxpLAeiVrFQnRxwjKq7iVQxTieVGybhyXvSpump': 'PUMP',
    'Caykk3E1qZM6QBf82A2bZZiaLGntefrt4VAJXDWQ8Gm2': 'ETH',
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'USDC',
    'So11111111111111111111111111111111111111111': 'SOL'
}

# Price cache to avoid repeated API calls
PRICE_CACHE = {}

def get_token_name(token_address):
    """Get token name with enhanced fallback"""
    # Check local cache first
    if token_address in TOKEN_NAMES:
        return TOKEN_NAMES[token_address]
    
    # Try Jupiter API for token info
    try:
        url = "https://token.jup.ag/all"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            tokens = response.json()
            for token in tokens:
                if token.get('address') == token_address:
                    name = token.get('name', f"Unknown-{token_address[:4]}")
                    TOKEN_NAMES[token_address] = name
                    return name
    except Exception as e:
        warning(f"Jupiter token info error: {str(e)}")
    
    # Try Birdeye token info
    try:
        headers = {"X-API-KEY": os.getenv("BIRDEYE_API_KEY", "9ca8697fa5974150a760c7d7ad9310e3")}
        url = f"https://public-api.birdeye.so/public/tokenlist?address={token_address}"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data', {}).get('name'):
                name = data['data']['name']
                TOKEN_NAMES[token_address] = name
                return name
    except Exception as e:
        warning(f"Birdeye token info error: {str(e)}")
    
    # Fallback to abbreviated address
    name = f"Token-{token_address[:4]}..{token_address[-4:]}"
    TOKEN_NAMES[token_address] = name
    return name

def get_cached_price(token_address):
    """Get price from wallet tracker cache if available"""
    # First check our local cache
    if token_address in PRICE_CACHE:
        return PRICE_CACHE[token_address]
    
    # Try to load price from artificial_memory cache
    try:
        cache_path = os.path.join(os.getcwd(), "src/data/artificial_memory_d.json")
        if os.path.exists(cache_path):
            import json
            with open(cache_path, "r") as f:
                cached_data = json.load(f)
                
            # Search through all wallets for this token
            data = cached_data.get('data', {}).get('data', {})
            for wallet, tokens in data.items():
                for token in tokens:
                    if token.get('mint') == token_address and token.get('price') is not None:
                        price = token.get('price')
                        if price is not None:
                            price = float(price)
                        else:
                            price = None  # No fallback price
                        PRICE_CACHE[token_address] = price
                        debug(f"Found cached price ${price} for {token_address[:8]}", file_only=True)
                        return price
    except Exception as e:
        debug(f"Error reading cached price: {str(e)}", file_only=True)
    
    # Default value if no cached price found
    default_price = None  # No fallback price
    PRICE_CACHE[token_address] = default_price
    return default_price

def collect_token_data(token_address, suppress_logs=False):
    """Collects OHLCV data for a specific token"""
    start_time = time.time()
    try:
        token_name = get_token_name(token_address)
        
        # Modify print statements to be conditional
        if not suppress_logs:
            info(f"Collecting market data for {token_address[:6]}")
        
        # Direct print for debugging - ensure visibility
        print(f"⏱️ DIRECT TIMING: Starting data collection for {token_name}")
            
        # Step 1: Try Birdeye API (primary source)
        birdeye_start = time.time()
        try:
            debug(f"Attempting Birdeye data for {token_name}", file_only=False)
            headers = {"X-API-KEY": os.getenv("BIRDEYE_API_KEY", "9ca8697fa5974150a760c7d7ad9310e3")}
            url = f"https://public-api.birdeye.so/public/candle?address={token_address}&type=day&limit=14"
            response = requests.get(url, headers=headers, timeout=10)
            
            birdeye_elapsed = time.time() - birdeye_start
            debug(f"TIMING: Birdeye API call took {birdeye_elapsed:.2f} seconds", file_only=False)
            # Direct print for debugging - ensure visibility
            print(f"⏱️ DIRECT TIMING: Birdeye API call took {birdeye_elapsed:.2f} seconds")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    candles = data['data']
                    if candles:
                        # Convert Birdeye format to our dataframe
                        df = pd.DataFrame(candles)
                        df['date'] = pd.to_datetime(df['time'], unit='s')
                        df['name'] = token_name
                        df['source'] = 'Birdeye'  # Add source information
                        info(f"Birdeye data found for {token_name}")
                        total_elapsed = time.time() - start_time
                        debug(f"TIMING: Total collection time for {token_name}: {total_elapsed:.2f} seconds (Birdeye success)", file_only=False)
                        print(f"⏱️ DIRECT TIMING: Total collection time: {total_elapsed:.2f}s (Birdeye success)")
                        return df
        except Exception as e:
            birdeye_elapsed = time.time() - birdeye_start
            warning(f"Birdeye data failed after {birdeye_elapsed:.2f} seconds: {str(e)}")
            print(f"⏱️ DIRECT TIMING: Birdeye failed after {birdeye_elapsed:.2f}s: {str(e)}")
        
        # Skip CoinGecko step since it's unlikely to have data for smaller tokens
        # and proceed directly to synthetic data generation
        
        # Generate synthetic data as fallback
        synthetic_start = time.time()
        warning(f"Birdeye API failed. Generating synthetic data for {token_name}")
        print(f"⏱️ DIRECT TIMING: Starting synthetic data generation")
        synthetic_data = generate_synthetic_data(token_address, 14)
        synthetic_elapsed = time.time() - synthetic_start
        debug(f"TIMING: Synthetic data generation took {synthetic_elapsed:.2f} seconds", file_only=False)
        print(f"⏱️ DIRECT TIMING: Synthetic data generation took {synthetic_elapsed:.2f} seconds")
        
        total_elapsed = time.time() - start_time
        debug(f"TIMING: Total collection time for {token_name}: {total_elapsed:.2f} seconds (using synthetic data)", file_only=False)
        print(f"⏱️ DIRECT TIMING: Total collection time: {total_elapsed:.2f}s (synthetic data)")
        return synthetic_data
    except Exception as e:
        total_elapsed = time.time() - start_time
        if not suppress_logs:
            error(f"Error collecting data for {token_address} after {total_elapsed:.2f} seconds: {str(e)}")
            print(f"⏱️ DIRECT TIMING: Error collecting data after {total_elapsed:.2f}s: {str(e)}")
        return None

def generate_synthetic_data(token_address, days=14):
    """Generate synthetic OHLCV data for testing"""
    # Use cached price instead of fetching new price
    current_price = get_cached_price(token_address)
    debug(f"Using cached price ${current_price} for synthetic data generation", file_only=False)
    
    # Get token name
    token_name = get_token_name(token_address)
    
    # Create date range
    end_date = datetime.now()
    dates = pd.date_range(end=end_date, periods=days)
    
    # Generate price data with trend and volatility
    base_price = current_price
    trend = random.choice([-0.01, 0.01])  # Slight downtrend or uptrend
    volatility = random.uniform(0.02, 0.10)  # Random volatility
    
    # Generate price series with some randomness
    closes = []
    for i in range(days):
        # Random daily movement with trend
        daily_change = trend + random.normalvariate(0, volatility)
        # Ensure price doesn't go negative
        base_price = max(0.00001, base_price * (1 + daily_change))
        closes.append(base_price)
    
    # Create OHLCV data
    df = pd.DataFrame({
        'date': dates,
        'price': closes,
        'open': [p * (1 - random.uniform(0, 0.02)) for p in closes],
        'high': [p * (1 + random.uniform(0, 0.03)) for p in closes],
        'low': [p * (1 - random.uniform(0, 0.03)) for p in closes],
        'close': closes,
        'volume': [random.uniform(10000, 1000000) * p for p in closes],
        'name': [token_name] * days,
        'source': ['Synthetic'] * days  # Add source information
    })
    
    # Add simple technical indicators
    df['MA20'] = df['close'].rolling(window=min(7, len(df))).mean()
    df['MA40'] = df['close'].rolling(window=min(10, len(df))).mean()
    
    # Fill NaN values in moving averages for first few rows
    df['MA20'] = df['MA20'].fillna(df['close'])
    df['MA40'] = df['MA40'].fillna(df['close'])
    
    # Boolean indicators
    df['ABOVE_MA20'] = df['close'] > df['MA20']
    df['ABOVE_MA40'] = df['close'] > df['MA40']
    
    # Reset index and return
    df = df.reset_index(drop=True)
    
    return df

def collect_all_tokens(token_list=None):
    """Collect data for multiple tokens"""
    if token_list is None:
        token_list = MONITORED_TOKENS
    
    all_data = {}
    for token in token_list:
        data = collect_token_data(token)
        if data is not None and not data.empty:
            all_data[token] = data
            debug(f"Data collected for {get_token_name(token)}", file_only=True)
        # Avoid rate limits
        time.sleep(1)
    
    info(f"Collected data for {len(all_data)} tokens")
    return all_data

if __name__ == "__main__":
    try:
        collect_all_tokens()
    except KeyboardInterrupt:
        info("OHLCV Collector shutting down gracefully")
    except Exception as e:
        error(f"Error: {str(e)}")
        warning("Check the logs and try again") 
