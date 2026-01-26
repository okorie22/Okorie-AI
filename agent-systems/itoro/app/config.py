"""
🌙 Anarcho Capital's App Configuration
Streamlined version with only variables actually used by the app
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file in root ITORO folder
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(env_path)

# =============================================================================
# 📈 PAPER TRADING CONFIGURATION
# =============================================================================

# Paper Trading Settings
PAPER_TRADING_ENABLED = True # Set to False for live trading mode
PAPER_INITIAL_BALANCE = 1000.0  # Initial paper trading balance in USD
PAPER_TRADING_SLIPPAGE = 104  # Simulated slippage for paper trades (100 = 1%)
PAPER_TRADING_RESET_ON_START = False  # Whether to reset paper portfolio on app start
PAPER_TRADING_DB_PATH = os.path.join('data', 'paper_trading.db')

# =============================================================================
# 🔊 LOGGING CONFIGURATION
# =============================================================================

# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "DEBUG"  # Set to DEBUG for detailed troubleshooting
LOG_TO_FILE = True  # Whether to save logs to file
LOG_DIRECTORY = os.path.join(os.path.dirname(__file__), "logs")  # Absolute path to app/logs directory
LOG_FILENAME = "trading_system.log"  # Name of the log file
LOG_MAX_SIZE_MB = 10  # Maximum size of log file before rotation (in MB)
LOG_BACKUP_COUNT = 5  # Number of backup log files to keep

# =============================================================================
# 🤖 AI MODEL CONFIGURATION
# =============================================================================

# Global AI Model Settings (used as fallbacks)
AI_MODEL = "deepseek"
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 2048

# =============================================================================
# 💰 CORE TRADING CONFIGURATION
# =============================================================================

# Core token addresses for mainnet trading
USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Never trade or close
SOL_ADDRESS = "So11111111111111111111111111111111111111112"  # Never trade or close
STAKED_SOL_TOKEN_ADDRESS = "STAKED_SOL_So11111111111111111111111111111111111111112"  # Unique identifier for staked SOL

# Define excluded tokens and rebalancing allowed tokens AFTER dynamic address assignment
EXCLUDED_TOKENS = [USDC_ADDRESS, SOL_ADDRESS, STAKED_SOL_TOKEN_ADDRESS]

# Tokens that can be used for rebalancing (but not regular trading)
REBALANCING_ALLOWED_TOKENS = [USDC_ADDRESS, SOL_ADDRESS]  # USDC and SOL can be sold for rebalancing

# Get wallet address from environment variable
address = os.getenv('DEFAULT_WALLET_ADDRESS')
DEFAULT_WALLET_ADDRESS = address

# =============================================================================
# 🚀 LEVERAGE TRADING CONFIGURATION
# =============================================================================

# Leverage Trading Mode
USE_LEVERAGE_TRADING = False  # Set to True for perpetual futures trading
LEVERAGE_EXCHANGE = 'hyperliquid'  # 'hyperliquid', 'jupiter', 'none'

# Leverage Settings
DEFAULT_LEVERAGE = 5  # Default leverage multiplier (5x)
MAX_LEVERAGE = 10  # Maximum allowed leverage (safety limit)
MIN_LEVERAGE = 1  # Minimum leverage (1x = spot)

# Leverage Risk Management
LEVERAGE_MAX_POSITION_SIZE = 0.25  # Max 25% of equity per position (leverage adjusted)
LEVERAGE_STOP_LOSS_MULTIPLIER = 0.5  # Tighter stops for leverage (0.5% vs 2% spot)
LEVERAGE_TAKE_PROFIT_MULTIPLIER = 1.5  # Wider targets for leverage (1.5x normal)

# Hyperliquid Specific Settings
HYPERLIQUID_WALLET_ADDRESS = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
HYPERLIQUID_PRIVATE_KEY = os.getenv('HYPERLIQUID_PRIVATE_KEY')
HYPERLIQUID_VAULT_ADDRESS = os.getenv('HYPERLIQUID_VAULT_ADDRESS')  # Optional vault
HYPERLIQUID_TESTNET = True  # Set to False for mainnet trading

# Leverage Trading Pairs (Hyperliquid supported assets)
LEVERAGE_SUPPORTED_ASSETS = [
    'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'MATIC',
    'DOT', 'LINK', 'UNI', 'AAVE', 'SUSHI', 'COMP', 'NEAR', 'WIF'
]

# =============================================================================
# 🎯 POSITION SIZING & RISK MANAGEMENT
# =============================================================================

# Position sizing (OPTIMIZED FOR $115/WEEK SWING TRADING)
POSITION_SIZING_MODE = "dynamic"  # "fixed" or "dynamic"
BASE_POSITION_SIZE_USD = 20.0  # Base position size for swing trades
MIN_POSITION_SIZE_USD = 1.0  # Minimum viable swing position
MAX_POSITION_SIZE_USD = 1000.0  # Maximum position size

# Position limits
MAX_CONCURRENT_POSITIONS = 12  # Maximum simultaneous positions
MAX_TOTAL_ALLOCATION_PERCENT = 0.50  # Maximum total allocation
MAX_SINGLE_POSITION_PERCENT = 0.10  # 15% max for highest conviction

# Risk management
CASH_PERCENTAGE = 20  # Cash buffer percentage
MINIMUM_BALANCE_USD = 50  # Minimum balance limit for risk management

# =============================================================================
# 📊 OI AGENT CONFIGURATION
# =============================================================================

# OI Agent Settings
OI_CHECK_INTERVAL_HOURS = 4  # How often to collect OI data (hours)
OI_TRACKED_SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'AVAX', 'MATIC', 'DOT']  # Top 10 cryptocurrencies
OI_LOCAL_RETENTION_DAYS = 30  # How long to keep local Parquet files (days)
OI_AI_INSIGHTS_ENABLED = True  # Enable AI-generated market insights

# =============================================================================
# 💰 FUNDING AGENT CONFIGURATION
# =============================================================================

# Funding Agent Settings
FUNDING_CHECK_INTERVAL_MINUTES = 120  # How often to check funding rates (2 hours)
FUNDING_LOCAL_RETENTION_DAYS = 90  # How long to keep local Parquet files (days)

# Funding Rate Alert Thresholds
FUNDING_MID_NEGATIVE_THRESHOLD = -2.0  # Alert if annual rate below -2%
FUNDING_MID_POSITIVE_THRESHOLD = 10.0  # Alert if annual rate above 10%
FUNDING_NEGATIVE_THRESHOLD = -5.0  # AI Run & Alert if annual rate below -5% (EXTREME)
FUNDING_POSITIVE_THRESHOLD = 20.0  # AI Run & Alert if annual rate above 20% (EXTREME)

# Funding Agent AI Settings
FUNDING_MODEL_OVERRIDE = "deepseek-chat"  # DeepSeek's V3 model - fast & efficient
FUNDING_DEEPSEEK_BASE_URL = "https://api.deepseek.com"  # Base URL for DeepSeek API
FUNDING_AI_TEMPERATURE = 0.7
FUNDING_AI_MAX_TOKENS = 150

# OHLCV Data Settings for Funding Analysis
FUNDING_TIMEFRAME = '15m'  # Candlestick timeframe
FUNDING_LOOKBACK_BARS = 100  # Number of candles to analyze

# Symbol to name mapping - 16 major crypto assets
FUNDING_SYMBOL_NAMES = {
    'BTC': 'Bitcoin',
    'ETH': 'Ethereum',
    'SOL': 'Solana',
    'BNB': 'Binance Coin',
    'ADA': 'Cardano',
    'AVAX': 'Avalanche',
    'MATIC': 'Polygon',
    'LINK': 'Chainlink',
    'DOT': 'Polkadot',
    'UNI': 'Uniswap',
    'AAVE': 'Aave',
    'SUSHI': 'SushiSwap',
    'COMP': 'Compound',
    'MKR': 'Maker',
    'NEAR': 'Near Protocol',
    'FARTCOIN': 'Fart Coin'
}

# =============================================================================
# 📊 CHART ANALYSIS CONFIGURATION
# =============================================================================

# Chart analysis settings
CHART_ANALYSIS_INTERVAL_MINUTES = 60  # 24 hours (1 day)
CHART_INTERVAL_UNIT = "Day(s)"
CHART_INTERVAL_VALUE = 1
CHART_RUN_AT_ENABLED = True
CHART_RUN_AT_TIME = "09:00"  # Run at 9 AM daily
CHART_INITIAL_DELAY_HOURS = 0  # Wait 1 hour before first analysis
TIMEFRAMES = ['4h']
LOOKBACK_BARS = 120  # Reduce from 300 to 120 (4h x 120 = 20 days of data)
ENABLE_FIBONACCI = True  # Enable Fibonacci retracement analysis
FIBONACCI_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIBONACCI_LOOKBACK_PERIODS = 75  # Increase from 60 to 75

# Chart indicators
CHART_INDICATORS = ['20EMA', '50EMA', '100EMA', '200SMA', 'MACD', 'RSI', 'ATR']
CHART_STYLE = 'yahoo'
CHART_VOLUME_PANEL = True
ENABLE_CHART_ANALYSIS = True

# Aggregated market sentiment settings
ENABLE_AGGREGATED_SENTIMENT = True
AGGREGATED_SENTIMENT_FILE = "aggregated_market_sentiment.csv"
SENTIMENT_UPDATE_INTERVAL_HOURS = 1  # Update sentiment every hour
SENTIMENT_WEIGHTS = {
    'SOL': 0.40,     # 40% weight for SOL (market indicator)
    'WIF': 0.30,     # 30% weight for WIF (major meme coin)
    'BOME': 0.20,    # 20% weight for BOME (major meme coin)
    'JTO': 0.05,     # 5% weight for JTO
    'PYTH': 0.05,    # 5% weight for PYTH
}

# Default weight for tokens not in SENTIMENT_WEIGHTS
DEFAULT_SENTIMENT_WEIGHT = 0.1  # 10% default weight

# Voice settings
VOICE_MODEL = "tts-1"
VOICE_NAME = "shimmer"
VOICE_SPEED = 1.0

# Chart Analysis AI Prompt
CHART_ANALYSIS_PROMPT = """
You must respond in exactly 4 lines:
Line 1: Only write BUY, SELL, or NOTHING
Line 2: One short reason why
Line 3: Only write "Confidence: X%" where X is 60-95
Line 4: Calculate the optimal entry price level based on indicators

Analyze the chart data for {symbol} {timeframe}:

{chart_data}

TECHNICAL ANALYSIS GUIDELINES - BE DECISIVE:
- RSI < 35 (oversold) = STRONG BUY signal with 75-85% confidence
- RSI > 65 (overbought) = STRONG SELL signal with 75-85% confidence
- MACD bullish crossover = BUY signal with 70-80% confidence
- MACD bearish crossover = SELL signal with 70-80% confidence
- Price above 20EMA + 50EMA = BULLISH bias, consider BUY
- Price below 20EMA + 50EMA = BEARISH bias, consider SELL
- Volume increasing = Confirms signal strength
- Only choose NOTHING if ALL indicators are truly neutral (RSI 45-55, MACD flat, price between EMAs)

CONFIDENCE GUIDELINES:
- 60-70%: Single strong indicator (RSI extreme or MACD crossover)
- 75-85%: Two indicators aligned (RSI + MACD, or EMA + volume)
- 90-95%: Multiple indicators aligned with volume confirmation

SIGNAL STRENGTH EVALUATION:
- Strong BUY: RSI < 35 + MACD bullish crossover + price above 50EMA + volume increasing
- Strong SELL: RSI > 65 + MACD bearish crossover + price below 50EMA + volume increasing
- Moderate BUY: RSI < 45 + MACD above signal + price above 20EMA
- Moderate SELL: RSI > 55 + MACD below signal + price below 20EMA
- Weak BUY: RSI < 50 + price near support + volume increasing
- Weak SELL: RSI > 50 + price near resistance + volume increasing

ENTRY PRICE CALCULATION:
- For BUY: Use support levels (EMAs, recent lows, Fibonacci retracements)
- For SELL: Use resistance levels (EMAs, recent highs, Fibonacci extensions)
- Consider ATR for buffer zones around entry levels
- Factor in market regime volatility for appropriate spacing

MARKET REGIME CONSIDERATIONS:
- STRONG_TREND: Higher confidence for trend-following signals
- WEAK_TREND: Moderate confidence, wait for confirmation
- VOLATILE_BREAKOUT: High confidence for momentum signals
- SIDEWAYS: Lower confidence, focus on range-bound strategies
- NEUTRAL: Default to NOTHING unless clear signal emerges

BE AGGRESSIVE: Default to BUY or SELL unless truly no clear direction exists. The market rewards decisive action over cautious observation.
"""

# Chart AI Model Settings
CHART_MODEL_OVERRIDE = "deepseek-chat"
CHART_DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Token mapping for chart analysis
TOKEN_MAP = {
    'So11111111111111111111111111111111111111112': ('SOL', 'SOL'),  # Solana
    'EKpQGSJtjMFqKZ1KQanSqYXRcF8fBopzLHYxdM65Qjm': ('WIF', 'WIF'),  # WIF
    'ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82': ('BOME', 'BOME'),  # BOME
    'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL': ('JTO', 'JTO'),  # JTO
    'HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3': ('PYTH', 'PYTH'),  # PYTH
}

# DCA monitored tokens
DCA_MONITORED_TOKENS = [
    'So11111111111111111111111111111111111111112',  # SOL
    'EKpQGSJtjMFqKZ1KQanSqYXRcF8fBopzLHYxdM65Qjm',  # WIF
    'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
    '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump',  # FART
]

# =============================================================================
# 🌐 API CONFIGURATION
# =============================================================================

# RPC Configuration
RPC_ENDPOINT = os.getenv('RPC_ENDPOINT', 'https://mainnet.helius-rpc.com/?api-key=09016bd8-7f90-41a3-877f-0f62d6ad058e')
QUICKNODE_RPC_ENDPOINT = os.getenv('QUICKNODE_RPC_ENDPOINT', 'https://radial-maximum-tent.solana-mainnet.quiknode.pro/9101fbd24628749398074bdd83c57b608d8e8cd2/')
HELIUS_RPC_ENDPOINT = os.getenv('HELIUS_RPC_ENDPOINT', 'https://mainnet.helius-rpc.com/?api-key=09016bd8-7f90-41a3-877f-0f62d6ad058e')

# Jupiter API configuration
JUPITER_API_KEY = os.getenv('JUPITER_API_KEY', '')  # Optional - Jupiter works without API key
JUPITER_API_URL = "https://lite-api.jup.ag/swap/v1"

# Price service configuration
PRICE_SOURCE_MODE = os.getenv('PRICE_SOURCE_MODE', 'jupiter')  # Default to Jupiter-first, Birdeye as fallback
BIRDEYE_API_KEY = os.getenv('BIRDEYE_API_KEY')

# =============================================================================
# 🔧 UTILITY FUNCTIONS
# =============================================================================

def get_position_size(account_balance: float, current_position_usd: float = 0.0) -> float:
    """
    Calculate the position size based on account balance and current position.

    Args:
        account_balance: Current account balance in USD
        current_position_usd: Current position size in USD

    Returns:
        Position size in USD
    """
    # Implement position sizing logic here
    if POSITION_SIZING_MODE == "dynamic":
        if account_balance < 1000.0:
            return account_balance * 0.02  # 2% for small accounts
        else:
            return account_balance * 0.05  # 5% for larger accounts
    else:
        return BASE_POSITION_SIZE_USD