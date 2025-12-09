"""
🌙 Anarcho Capital's Configuration File
Built with love by Anarcho Capital 🚀
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# 📈 PAPER TRADING CONFIGURATION
# =============================================================================

# Paper Trading Settings
PAPER_TRADING_ENABLED = True  # Set to True for paper trading testing
PAPER_INITIAL_BALANCE = 1000.0  # Initial paper trading balance in USD
PAPER_TRADING_SLIPPAGE = 104  # Simulated slippage for paper trades (100 = 1%)
PAPER_TRADING_RESET_ON_START = True  # Whether to reset paper portfolio on app start
PAPER_TRADING_INITIAL_BALANCE = 1000.0
PAPER_TRADING_DB_PATH = os.path.join('src', 'data', 'paper_trading.db')


# Paper trading position limits
PAPER_MAX_POSITION_SIZE = 100.0  # Maximum size for any single position in USD
PAPER_MIN_POSITION_SIZE = 10   # Minimum position size in USD
PAPER_MAX_TOTAL_ALLOCATION = 0.65  # Maximum 95% of portfolio can be allocated

# Status update interval (in seconds)
STATUS_UPDATE_INTERVAL = 3600  # Update status display every 1 hour

# =============================================================================
# 🔊 LOGGING CONFIGURATION
# =============================================================================

# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"  # Default level - less verbose than DEBUG

# Log file settings
LOG_TO_FILE = True  # Whether to save logs to file
LOG_DIRECTORY = "logs"  # Directory to store log files
LOG_FILENAME = "trading_system.log"  # Name of the log file
LOG_MAX_SIZE_MB = 10  # Maximum size of log file before rotation (in MB)
LOG_BACKUP_COUNT = 5  # Number of backup log files to keep

# UI Console logging settings
CONSOLE_LOG_LEVEL = "INFO"  # Level for console UI (can be different from file logging)
SHOW_DEBUG_IN_CONSOLE = False  # Whether to show DEBUG messages in the UI console
SHOW_TIMESTAMPS_IN_CONSOLE = False  # Whether to show timestamps in console messages

# =============================================================================
# 🤖 AI MODEL CONFIGURATION
# =============================================================================

# Global AI Model Settings (used as fallbacks)
AI_MODEL = "claude-3-haiku-20240307"
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 1024

# Agent-specific AI overrides
RISK_MODEL_OVERRIDE = "deepseek-reasoner"
RISK_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
COPYBOT_MODEL_OVERRIDE = "deepseek-reasoner"
DCA_MODEL_OVERRIDE = "deepseek-reasoner"
DCA_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
CHART_MODEL_OVERRIDE = "deepseek-reasoner"
CHART_DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# =============================================================================
# 🐋 APIFY WHALE AGENT CONFIGURATION
# =============================================================================

# Apify API Configuration
APIFY_API_TOKEN = os.getenv('APIFY_API_TOKEN')
APIFY_ACTOR_ID = "jgxPNaFu0r4jDOXD1"  # GMGN CopyTrade Wallet Scraper
APIFY_DEFAULT_INPUT = {
    "chain": "sol",
    "sortBy": "profit_30days",
    "sortDirection": "desc",
    "traderType": "all"
}

# Whale Agent Scoring Configuration
WHALE_SCORING_WEIGHTS = {
    'pnl_30d': 0.25,           # 30-day PnL weight
    'pnl_7d': 0.20,            # 7-day PnL weight
    'winrate_7d': 0.20,        # 7-day win rate weight
    'txs_30d': 0.10,           # Transaction count weight (inverse)
    'token_active': 0.15,      # Active tokens weight
    'is_blue_verified': 0.05,  # Twitter verification weight
    'avg_holding_period_7d': 0.05  # Holding period weight
}

# Whale Agent Thresholds
WHALE_THRESHOLDS = {
    'min_pnl_30d': 50000.0,     # Lowered from 1000.0 - match ideal wallets
    'min_winrate_7d': 0.3,      # Lowered from 0.4 - more realistic
    'max_txs_30d': 10000,       # Increased from 1000 - allow more active traders
    'min_token_active': 10,     # Lowered from 40 - allow focused traders
    'max_token_active': 1000,   # Increased from 300 - more flexible
    'min_avg_holding_period': 0.1,  # Lowered from 1.0 - allow quick traders
    'max_avg_holding_period': 100000.0, # Increased from 30.0 - handle data issues
    'max_inactive_days': 7      # Maximum days since last activity
}

# Whale Agent Data Management
WHALE_DATA_DIR = os.path.join('src', 'data', 'whale_dump')
WHALE_RANKED_FILE = 'ranked_whales.json'
WHALE_HISTORY_FILE = 'whale_history.csv'
WHALE_UPDATE_INTERVAL_HOURS = 48  # Update frequency in hours
WHALE_MAX_STORED_WALLETS = 1000   # Maximum wallets to store

# =============================================================================
# 💰 CORE TRADING CONFIGURATION
# =============================================================================

# Core token addresses
USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Never trade or close
SOL_ADDRESS = "So11111111111111111111111111111111111111112"  # Never trade or close
EXCLUDED_TOKENS = [USDC_ADDRESS, SOL_ADDRESS]

# Get wallet address from environment variable 
address = os.getenv('DEFAULT_WALLET_ADDRESS')

# Validate wallet address
def validate_wallet_address(wallet_addr):
    """Validate that the wallet address is properly formatted"""
    if not wallet_addr:
        return False, "Wallet address is not configured"
    
    if len(wallet_addr) < 32:
        return False, f"Wallet address too short: {len(wallet_addr)} characters"
    
    if len(wallet_addr) > 50:
        return False, f"Wallet address too long: {len(wallet_addr)} characters"
    
    # Basic validation - should be base58 encoded
    try:
        import base58
        base58.b58decode(wallet_addr)
        return True, "Valid wallet address"
    except:
        # If base58 not available, do basic character validation
        valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        if all(c in valid_chars for c in wallet_addr):
            return True, "Valid wallet address (basic validation)"
        else:
            return False, "Wallet address contains invalid characters"

# Validate the configured address
if address:
    is_valid, validation_msg = validate_wallet_address(address)
    if not is_valid:
        print(f"WARNING: {validation_msg}")
        print(f"Current address: {address}")
        print("Please check your DEFAULT_WALLET_ADDRESS environment variable")
else:
    print("WARNING: No wallet address configured (DEFAULT_WALLET_ADDRESS environment variable)")
    print("Personal wallet balance features will not work until this is set")

# Trading Mode Configuration
TRADING_MODE = "spot"
USE_HYPERLIQUID = False
DEFAULT_LEVERAGE = 2.0
MAX_LEVERAGE = 5.0
MIRROR_WITH_LEVERAGE = False
LEVERAGE_SAFETY_BUFFER = 0.8

# Paper Trading Settings
PAPER_TRADING_ENABLED = True  # Toggle paper trading mode on/off
PAPER_INITIAL_BALANCE = 1000.0  # Initial paper trading balance in USD
PAPER_TRADING_SLIPPAGE = 104  # Simulated slippage for paper trades (100 = 1%)
PAPER_TRADING_RESET_ON_START = True  # Whether to reset paper portfolio on app start

# =============================================================================
# 🌐 API CONFIGURATION
# =============================================================================

# RPC Configuration
RPC_ENDPOINT = os.getenv('RPC_ENDPOINT', 'https://mainnet.helius-rpc.com/?api-key=09016bd8-7f90-41a3-877f-0f62d6ad058e')
QUICKNODE_RPC_ENDPOINT = os.getenv('QUICKNODE_RPC_ENDPOINT', 'https://radial-maximum-tent.solana-mainnet.quiknode.pro/9101fbd24628749398074bdd83c57b608d8e8cd2/')
QUICKNODE_WSS_ENDPOINT = os.getenv('QUICKNODE_WSS_ENDPOINT', 'wss://radial-maximum-tent.solana-mainnet.quiknode.pro/9101fbd24628749398074bdd83c57b608d8e8cd2/')
HELIUS_RPC_ENDPOINT = os.getenv('HELIUS_RPC_ENDPOINT', 'https://mainnet.helius-rpc.com/?api-key=09016bd8-7f90-41a3-877f-0f62d6ad058e')

# RPC Priority (QuickNode primary, Helius fallback)
# Note: Free RPC endpoints may have authentication issues - this is normal
PRIMARY_RPC_ENDPOINT = QUICKNODE_RPC_ENDPOINT
FALLBACK_RPC_ENDPOINT = HELIUS_RPC_ENDPOINT

# RPC Authentication Settings
RPC_AUTHENTICATION_REQUIRED = True  # Set to False if using public RPC endpoints
RPC_API_KEY_HEADER = "Authorization"  # Header name for API key
RPC_API_KEY_PREFIX = "Bearer"  # Prefix for API key in header

# RPC Error Handling
RPC_MAX_RETRIES = 3
RPC_RETRY_DELAY = 1.0
RPC_TIMEOUT = 15
RPC_IGNORE_AUTH_ERRORS = True  # Ignore 401 errors for free RPC endpoints

# QuickNode API Access (from your add-ons)
QUICKNODE_TOKEN_METRICS_API = True  # Token price, OHLCV, sentiment
QUICKNODE_PRIORITY_FEE_API = True   # Priority fee data
QUICKNODE_MEV_RESILIENCE = True     # MEV protection
QUICKNODE_PUMPFUN_API = True        # Pump.fun integration
QUICKNODE_JUPITER_SWAP_API = True   # Jupiter swap integration
QUICKNODE_OPENOCEAN_API = True      # OpenOcean integration

# Jupiter API configuration
JUPITER_API_KEY = os.getenv('JUPITER_API_KEY', '')  # Optional - Jupiter works without API key
JUPITER_API_URL = "https://quote-api.jup.ag/v6"
JUPITER_FEE_ACCOUNT = "FG4Y3yX4AAchp1HvNZ7LfzFTewF2f6nDoMDCohTFrdpT"  # For referral fees

# Jupiter exchange constraints
JUPITER_MIN_TRANSACTION_SIZE_USD = 1.0
JUPITER_MAX_TRANSACTION_SIZE_USD = 50000.0
JUPITER_MAX_SLIPPAGE_BPS = 1000  # 10%
JUPITER_MIN_SOL_BALANCE = 0.01
JUPITER_DEFAULT_SLIPPAGE_BPS = 50  # 0.5%

# API timeouts and retries
API_SLEEP_SECONDS = 0.1  # OPTIMIZATION: Reduced from 2 to 0.1 seconds for 20x speed improvement
API_TIMEOUT_SECONDS = 15  # OPTIMIZATION: Reduced from 30 to 15 seconds for faster timeouts
API_MAX_RETRIES = 2  # OPTIMIZATION: Reduced from 3 to 2 retries for faster failure handling
API_RATE_LIMIT_CALLS = 15  # OPTIMIZATION: Increased from 10 to 15 calls per second (more aggressive)
API_RATE_LIMIT_WINDOW = 1  # Time window in seconds
API_BACKOFF_FACTOR = 1.5  # OPTIMIZATION: Reduced from 2 to 1.5 for faster retry recovery
API_MAX_BACKOFF = 30

# Helius-specific rate limits
HELIUS_RATE_LIMIT_CALLS = 5
HELIUS_RATE_LIMIT_WINDOW = 1

# Additional safety timeouts
API_REQUEST_TIMEOUT_SECONDS = 30
TRADE_TIMEOUT_SECONDS = 90
BALANCE_CHECK_TIMEOUT_SECONDS = 15
PRICE_CHECK_TIMEOUT_SECONDS = 12
WALLET_TRACKING_TIMEOUT_SECONDS = 120
WALLET_TOKEN_FETCH_TIMEOUT_SECONDS = 15
POSITION_VALIDATION_TIMEOUT_SECONDS = 10
METADATA_FETCH_TIMEOUT_SECONDS = 8

# =============================================================================
# 💲 PRICE SERVICE CONFIGURATION
# =============================================================================

PRICE_SOURCE_MODE = "birdeye"  # Options: "birdeye", "jupiter" - Switched to Birdeye for better performance
PRICE_CACHE_MINUTES = 3  # OPTIMIZATION: Reduced from 5 to 3 minutes for fresher prices
BATCH_SIZE = 100  # OPTIMIZATION: Increased from 50 to 100 for better batch efficiency
MIN_TOKEN_VALUE = 0.001  # SURGICAL: Reduced from 0.05 to 0.001 for much better coverage
SKIP_UNKNOWN_TOKENS = False  # SURGICAL: Disabled to allow tokens without price data
USE_PARALLEL_PROCESSING = True

# Tiered caching configuration
TIERED_CACHE_ENABLED = True
STABLECOIN_CACHE_HOURS = 12  # OPTIMIZATION: Reduced from 24 to 12 hours for better accuracy
BLUECHIP_CACHE_MINUTES = 5  # OPTIMIZATION: Reduced from 10 to 5 minutes for fresher prices
MIDCAP_CACHE_MINUTES = 3     # OPTIMIZATION: Reduced from 5 to 3 minutes
LOWCAP_CACHE_MINUTES = 1     # OPTIMIZATION: Reduced from 2 to 1 minute for volatile tokens

# Hybrid approach configuration
USE_HYBRID_PRICE_FETCHING = True  # Use Jupiter for primary with BirdEye fallback
PRIORITIZE_HIGH_VALUE_TOKENS = True  # Process high-value tokens first
ENABLE_ASYNC_REFRESH = True  # Enable background price refreshing
PRICE_INIT_CACHE_ONLY = False  # Wait for fresh prices before trading

# Price validation settings
ENABLE_PRICE_VALIDATION = True
MAX_PRICE_AGE_SECONDS = 180
MAX_STABLE_PRICE_AGE_SECONDS = 600  # OPTIMIZATION: Reduced from 900 to 600 seconds (10 minutes)
CRITICAL_PRICE_AGE_SECONDS = 120  # 2 minutes for critical operations
MIN_VALID_PRICE = 0.0000001  # Minimum valid price
MAX_VALID_PRICE = 10000000.0  # Maximum valid price
MAX_PRICE_CHANGE_PERCENT = 40.0  # Maximum price change to consider valid

# =============================================================================
# 🎯 POSITION SIZING & RISK MANAGEMENT
# =============================================================================

# Position sizing (OPTIMIZED FOR $115/WEEK SWING TRADING)
POSITION_SIZING_MODE = "dynamic"  # "fixed" or "dynamic"
BASE_POSITION_SIZE_USD = 20.0  # Base position size for swing trades
POSITION_SIZE_PERCENTAGE = 0.05  # 5% for swing trade conviction
MAX_SINGLE_POSITION_PERCENT = 0.12  # 12% max for highest conviction
MIN_POSITION_SIZE_USD = 10.0  # Minimum viable swing position
MAX_POSITION_SIZE_USD = 100.0  # Maximum position size

# Weekly budget management
WEEKLY_BUDGET_USD = 115.0  # Weekly deposit target
MAX_WEEKLY_POSITIONS = 6  # Maximum new positions per week
SWING_TRADE_HOLD_PERIOD_DAYS = 5  # Target hold period
CASH_RESERVE_PERCENTAGE = 20  # Keep 25% in USDC for opportunities

# Dynamic position sizing
USE_DYNAMIC_POSITION_SIZING = True
NEW_POSITION_BASE_PERCENT = 0.02  # Base percentage for new positions
NEW_POSITION_SMALL_ACCOUNT_PERCENT = 0.05  # Percentage when account < $1000
SMALL_ACCOUNT_THRESHOLD = 1000.0  # Threshold for small account protection
MAX_POSITION_INCREASE_PERCENT = 0.05  # Max increase as % of account

# Position limits
MAX_CONCURRENT_POSITIONS = 10  # Maximum simultaneous positions
MAX_TOTAL_ALLOCATION_PERCENT = 0.65  # Maximum total allocation
DUST_THRESHOLD_USD = 5.0  # Minimum position size to avoid dust

# Risk management settings
CASH_PERCENTAGE = 20  # Cash buffer percentage
MAX_POSITION_PERCENTAGE = 8  # Maximum per position
SLEEP_AFTER_CLOSE = 1800
MAX_LOSS_GAIN_CHECK_HOURS = 24  # Monitoring window

# Max Loss/Gain Settings
USE_PERCENTAGE = True  # Use percentage-based limits vs USD
MAX_LOSS_USD = 50.0  # Maximum loss in USD
MAX_GAIN_USD = 200.0  # Maximum gain in USD
MAX_LOSS_PERCENT = 8  # Maximum loss percentage
MAX_GAIN_PERCENT = 300  # Maximum gain percentage
MINIMUM_BALANCE_USD = 0  # Minimum balance limit for risk management

# Enhanced risk management
RISK_MANAGEMENT_ENABLED = True
EMERGENCY_STOP_ENABLED = True
DRAWDOWN_LIMIT_PERCENT = -0.30  # 10% maximum drawdown
CONSECUTIVE_LOSS_LIMIT = 3  # Maximum consecutive losses
POSITION_SIZE_SCALING = True  # Scale position size based on performance
CORRELATION_LIMIT = 0.5  # Maximum correlation between positions
VOLATILITY_ADJUSTMENT = True  # Adjust position sizes based on volatility

# =============================================================================
# 🚀 TRADE EXECUTION SETTINGS
# =============================================================================

# Legacy compatibility
usd_size = POSITION_SIZE_PERCENTAGE
max_usd_order_size = 25.0
tx_sleep = 3.0
orders_per_open = 2

# Slippage settings
slippage = 200  # 2% default slippage
SLIPPAGE_PROTECTION_ENABLED = True
DYNAMIC_SLIPPAGE_ADJUSTMENT = True
MIN_SLIPPAGE = 100  # 1% minimum slippage
MAX_SLIPPAGE = 300  # 3% maximum slippage
SLIPPAGE_INCREASE_THRESHOLD = 200  # 2% threshold for increasing slippage
PRICE_IMPACT_WARNING_THRESHOLD = 150  # 1.5% warning threshold

# Priority fees
PRIORITY_FEE = 50000  # Default priority fee in lamports
REBALANCING_PRIORITY_FEE = 150000  # Higher priority fee for rebalancing
CONVERSION_SLIPPAGE_BPS = 300  # 3% slippage for SOL/USDC conversions

# Trade execution safety
ENABLE_TRADE_VALIDATION = True
MAX_TRADE_RETRY_ATTEMPTS = 3
TRADE_TIMEOUT_SECONDS = 90

# =============================================================================
# 🔄 AGENT RUNTIME SETTINGS
# =============================================================================

# General agent settings
SLEEP_BETWEEN_RUNS_MINUTES = 15

# Risk Agent settings
RISK_CHECK_INTERVAL_MINUTES = 20
RISK_LOSS_CONFIDENCE_THRESHOLD = 85
RISK_GAIN_CONFIDENCE_THRESHOLD = 80
RISK_CONTINUOUS_MODE = False
USE_AI_CONFIRMATION = True

# Selective risk management
USE_SELECTIVE_RISK_MANAGEMENT = True
SELECTIVE_CLOSE_TARGET_REDUCTION = 0.3  # Close 30% of worst positions
SELECTIVE_CLOSE_MINIMUM_POSITIONS = 1  # Always close at least 1 position
RISK_CLOSE_BY_PERFORMANCE = True  # Close worst performing positions first
RISK_CLOSE_BY_SIZE = False  # Close largest positions first instead
PARTIAL_CLOSE_PERCENTAGE = 0.4  # Sell 40% of position for partial closes

# =============================================================================
# 🤖 COPYBOT CONFIGURATION
# =============================================================================

# Wallet tracking
WALLETS_TO_TRACK = [
    "31gVZf7BDGwTb8Emu2fNZ5uM9ZKz4HGHTjF7HAC7AJod",  # Your test wallet
    # Add more wallets here as needed
]

# CopyBot filtering
FILTER_MODE = "Dynamic"
PERCENTAGE_THRESHOLD = 0.005  # Reduced from 0.015 for better sensitivity (0.5%)
AMOUNT_THRESHOLD = 10.0  # Reduced from 1500 to catch smaller but meaningful moves
ACTIVITY_WINDOW_HOURS = 1.5  # Optimized for swing trader frequency
ENABLE_PERCENTAGE_FILTER = False  # Disabled initially to reduce over-filtering
ENABLE_AMOUNT_FILTER = True  # Keep enabled but with much lower threshold
ENABLE_ACTIVITY_FILTER = False  # Disabled initially to reduce over-filtering

# CopyBot execution settings
COPYBOT_ENABLE_EXECUTION = True
ENABLE_AI_ANALYSIS = False
COPYBOT_AUTO_BUY_NEW_TOKENS = True
COPYBOT_AUTO_SELL_REMOVED_TOKENS = True
COPYBOT_WALLET_ACTION_WEIGHT = 0.7
COPYBOT_MIN_CONFIDENCE = 80
COPYBOT_MIRROR_EXACT_PERCENTAGE = False  # Use fixed sizing for safety

# CopyBot runtime
COPYBOT_CONTINUOUS_MODE = False
COPYBOT_INTERVAL_MINUTES = 8
COPYBOT_SKIP_ANALYSIS_ON_FIRST_RUN = True

# =============================================================================
# 📊 TOKEN CONFIGURATION
# =============================================================================

# Dynamic vs static token monitoring
DYNAMIC_MODE = True  # Set to False to monitor only MONITORED_TOKENS
previous_mode = None  # Track mode changes globally

# Token lists
MONITORED_TOKENS = [
    'VFdxjTdFzXrYr3ivWyf64NuXo7vdPK7AG7idnNZJV',
    'CR2L1ob96JGWQkdFbt8rLwqdLLmqFwjcNGL2eFBn1RPt',
    '2HdzfUiFWfZHZ544ynffeneuibbDK6biCdjovejr8ez9',
    'C94njgTrKMQBmgqe23EGLrtPgfvcjWtqBBvGQ7Cjiank',
    '67mTTGnVRunoSLGitgRGK2FJp5cT1KschjzWH9zKc3r',
    '9YnfbEaXPaPmoXnKZFmNH8hzcLyjbRf56MQP7oqGpump',
    'DayN9FxpLAeiVrFQnRxwjKq7iVQxTieVGybhyXvSpump',
]

# Legacy compatibility
previous_monitored_tokens = []
tokens_to_trade = MONITORED_TOKENS

# Legacy symbol variable - DEPRECATED: This was an old token address, not a variable
# The system now uses token_mint/token_address for token identification
# and retrieves symbols from metadata services
# symbol = '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump'  # DEPRECATED

# =============================================================================
# 🤖 AGENT CONFIGURATION
# =============================================================================

# CopyBot Agent Settings
COPYBOT_ENABLED = True
COPYBOT_INTERVAL_MINUTES = 8  # Fallback polling interval (2 hours = 120 minutes)
COPYBOT_CONTINUOUS_MODE = False
COPYBOT_SKIP_ANALYSIS_ON_FIRST_RUN = False

# Risk Agent Settings
RISK_ENABLED = True
RISK_CHECK_INTERVAL_MINUTES = 15
RISK_CONTINUOUS_MODE = False
RISK_LOSS_CONFIDENCE_THRESHOLD = 90
RISK_GAIN_CONFIDENCE_THRESHOLD = 60

# Harvesting Agent Settings
HARVESTING_ENABLED = True
HARVESTING_WEBHOOK_FIRST_MODE = True  # Webhook-driven operation (resource efficient)
HARVESTING_FALLBACK_CHECK_HOURS = 6   # Fallback health check every 6 hours
HARVESTING_MODEL_OVERRIDE = "deepseek-reasoner"
HARVESTING_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
HARVESTING_GAIN_CONFIDENCE_THRESHOLD = 75

# Webhook delay to prevent agent interference (copybot agent priority)
HARVESTING_WEBHOOK_DELAY_SECONDS = 5  # Delay harvesting check by 5 seconds after webhook

# Rebalancing Agent Settings
REBALANCING_ENABLED = True
REBALANCING_WEBHOOK_FIRST_MODE = True  # Webhook-driven operation (resource efficient)
REBALANCING_FALLBACK_CHECK_HOURS = 2   # Fallback check every 2 hours
REBALANCING_CHECK_INTERVAL_MINUTES = 30
REBALANCING_CONTINUOUS_MODE = False

# =============================================================================
# ⚖️ REBALANCING AGENT CONFIGURATION
# =============================================================================

# Rebalancing agent settings
REBALANCING_ENABLED = True
REBALANCING_CHECK_INTERVAL_MINUTES = 30
REBALANCING_CONTINUOUS_MODE = False

# SOL balance management
SOL_TARGET_PERCENT = 0.10  # Target 5% of portfolio in SOL
SOL_MINIMUM_PERCENT = 0.05  # Minimum 2% SOL before triggering conversion
SOL_MAXIMUM_PERCENT = 0.20  # Maximum 8% SOL before converting to USDC
SOL_MINIMUM_BALANCE_USD = 10.0  # Minimum $10 SOL balance

# USDC reserve management
USDC_TARGET_PERCENT = 0.20  # Target 20% of portfolio in USDC
USDC_MINIMUM_PERCENT = 0.15  # Minimum 15% USDC before selling positions
USDC_EMERGENCY_PERCENT = 0.10  # Emergency threshold - force position sales (10%)

# Conversion settings
MIN_CONVERSION_USD = 10.0  # Minimum $10 for conversions
MAX_CONVERSION_USD = 100.0  # Maximum $100 single conversion for safety

# Position selling for reserves
REBALANCING_SELL_STRATEGY = "worst_performing"
REBALANCING_MAX_SELL_PERCENT = 0.30  # Never sell more than 30% in one rebalancing
REBALANCING_MIN_POSITION_SIZE = 0.5  # Don't sell positions smaller than $0.50

# Safety and limits
REBALANCING_MAX_FREQUENCY_MINUTES = 5  # Minimum time between rebalancing actions
REBALANCING_EMERGENCY_MODE = True  # Enable emergency rebalancing
REBALANCING_DRY_RUN = False  # Set to True for testing without actual trades
REBALANCING_LOG_LEVEL = "INFO"

# =============================================================================
# 🌾 HARVESTING AGENT CONFIGURATION
# =============================================================================

# Harvesting agent settings
HARVESTING_ENABLED = True
HARVESTING_CHECK_INTERVAL_MINUTES = 30
HARVESTING_CONTINUOUS_MODE = False

# Gain thresholds for harvesting
REALIZED_GAIN_THRESHOLD_USD = 50.0  # Minimum $50 realized gain to trigger harvesting
UNREALIZED_GAIN_THRESHOLD_20 = 0.20  # 20% gain threshold
UNREALIZED_GAIN_THRESHOLD_70 = 0.70  # 70% gain threshold  
UNREALIZED_GAIN_THRESHOLD_150 = 1.50  # 150% gain threshold

# Reallocation strategy percentages
REALLOCATION_SOL_PCT = 0.10  # 10% to SOL
REALLOCATION_STAKED_SOL_PCT = 0.25  # 25% to Staked SOL
REALLOCATION_USDC_PCT = 0.50  # 50% to USDC
REALLOCATION_EXTERNAL_PCT = 0.15  # 15% to external wallet

# External wallet transfer settings
EXTERNAL_WALLET_ADDRESS = os.getenv('EXTERNAL_WALLET_ADDRESS', '')  # External wallet for profit transfers
EXTERNAL_WALLET_ENABLED = os.getenv('EXTERNAL_WALLET_ENABLED', 'false').lower() == 'true'  # Enable external transfers

# Staked SOL Configuration
STAKED_SOL_ENABLED = True
STAKED_SOL_PROTOCOLS = ['marinade', 'jito', 'lido']
STAKED_SOL_MIN_AMOUNT_USD = 10.0

# =============================================================================
# 📈 DCA & STAKING CONFIGURATION
# =============================================================================

# DCA token configuration
TOKEN_MAP = {
    'HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC': ('AI16Z', 'AI16Z'),
    'So11111111111111111111111111111111111111112': ('SOL', 'SOL'),
    '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump': ('FART', 'FARTCOIN'),
}

DCA_MONITORED_TOKENS = [
    'HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC',
    'So11111111111111111111111111111111111111112',
    '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump',
]

# DCA settings
USE_DYNAMIC_ALLOCATION = False
TAKE_PROFIT_PERCENTAGE = 206
FIXED_DCA_AMOUNT = 14
DCA_INTERVAL_MINUTES = 30240
DCA_INTERVAL_UNIT = "Day(s)"
DCA_INTERVAL_VALUE = 21
DCA_RUN_AT_ENABLED = False
DCA_RUN_AT_TIME = "12:02"

# Advanced DCA settings
BUY_CONFIDENCE_THRESHOLD = 39
SELL_CONFIDENCE_THRESHOLD = 85
BUY_MULTIPLIER = 1.5  # Buy 50% more than standard amount
MAX_SELL_PERCENTAGE = 25  # Maximum % of holdings to sell
MAX_VOLATILITY_THRESHOLD = 0.05  # Maximum volatility threshold
TREND_AWARENESS_THRESHOLD = 50  # RSI threshold for trend awareness

# Staking configuration
STAKING_ALLOCATION_PERCENT = 50  # Percentage of SOL to stake
STAKING_MIN_THRESHOLD = 5  # Minimum SOL to keep unstaked (5%)

# Liquid staking protocols (receive liquid tokens like bSOL, JupSOL, stepSOL, laineSOL)
LIQUID_STAKING_PROTOCOLS = ["blazestake", "jupsol", "sanctum"]

# Native staking protocols (direct SOL delegation, no liquid tokens)
NATIVE_STAKING_PROTOCOLS = ["everstake", "community_validators"]

# Combined staking protocols for selection
STAKING_PROTOCOLS = LIQUID_STAKING_PROTOCOLS + NATIVE_STAKING_PROTOCOLS

STAKING_AUTO_CONVERT = True  # Auto-convert rewards to SOL
STAKING_RESTAKE_ENABLED = True  # Enable automatic restaking of rewards
STAKING_WITHDRAWAL_ENABLED = True  # Enable withdrawal functionality
STAKING_DELEGATION_ENABLED = True  # Enable delegation to specific validators

# Native staking configuration
NATIVE_STAKING_ENABLED = True
NATIVE_STAKING_MIN_AMOUNT_SOL = 1.0  # Minimum SOL for native staking
NATIVE_STAKING_VALIDATOR_COUNT = 3  # Number of validators to delegate to

# Liquid staking configuration
LIQUID_STAKING_ENABLED = True
LIQUID_STAKING_MIN_AMOUNT_USD = 10.0  # Minimum USD for liquid staking

# JupSOL configuration
JUPSOL_ENABLED = True
JUPSOL_MIN_AMOUNT_USD = 10.0

# Sanctum configuration
SANCTUM_ENABLED = True
SANCTUM_LST_OPTIONS = ["stepSOL", "laineSOL", "alphaSOL", "jupSOL"]  # Available Sanctum LSTs
SANCTUM_MIN_AMOUNT_USD = 10.0

STAKING_INTERVAL_MINUTES = 10080  # Weekly execution (7 days)
STAKING_INTERVAL_UNIT = "Day(s)"
STAKING_INTERVAL_VALUE = 7
STAKING_RUN_AT_ENABLED = True  # Enable scheduled execution
STAKING_RUN_AT_TIME = "09:00"  # Run at 9:00 AM daily
STAKING_START_DATE = "2025-07-26"  # Start date (YYYY-MM-DD) - 7 days from now
STAKING_START_TIME = "09:00"  # Start time (HH:MM)
STAKING_REPEAT_DAYS = 7  # Repeat every 7 days

# Staking safety thresholds
MIN_SOL_ALLOCATION_THRESHOLD = 5.0  # Minimum 5% SOL allocation (never stake below this)
MAX_SLASHING_RISK = 0.5  # Max acceptable slashing risk %
VALIDATOR_PERFORMANCE_THRESHOLD = 99  # Minimum validator uptime %

# Auto-convert settings for maintaining SOL allocation
AUTO_CONVERT_THRESHOLD = 10
MIN_CONVERSION_AMOUNT = 5
MAX_CONVERT_PERCENTAGE = 25

# Yield optimization
YIELD_OPTIMIZATION_INTERVAL = 28800
YIELD_OPTIMIZATION_INTERVAL_UNIT = "Hour(s)"
YIELD_OPTIMIZATION_INTERVAL_VALUE = 8
YIELD_OPTIMIZATION_RUN_AT_ENABLED = True
YIELD_OPTIMIZATION_RUN_AT_TIME = "13:00"

# =============================================================================
# 📊 CHART ANALYSIS CONFIGURATION
# =============================================================================

# Chart analysis settings
CHART_ANALYSIS_INTERVAL_MINUTES = 60
CHART_INTERVAL_UNIT = "Hour(s)"
CHART_INTERVAL_VALUE = 1
CHART_RUN_AT_ENABLED = True
CHART_RUN_AT_TIME = "23:26"
TIMEFRAMES = ['1d']
LOOKBACK_BARS = 104
CHART_INDICATORS = ['20EMA', '50EMA', '100EMA', '200SMA', 'MACD', 'RSI', 'ATR']
CHART_STYLE = 'yahoo'
CHART_VOLUME_PANEL = True
ENABLE_CHART_ANALYSIS = True

# Fibonacci retracement settings
ENABLE_FIBONACCI = True
FIBONACCI_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIBONACCI_LOOKBACK_PERIODS = 60

# Voice settings
VOICE_MODEL = "tts-1"
VOICE_NAME = "shimmer"
VOICE_SPEED = 1.0

# =============================================================================
# 💱 HYPERLIQUID CONFIGURATION
# =============================================================================

# Token to Hyperliquid Symbol Mapping
TOKEN_TO_HL_MAPPING = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    # Add more mappings as needed
}

# =============================================================================
# 🔍 BACKTESTING CONFIGURATION
# =============================================================================

DAYSBACK_4_DATA = 6
DATA_TIMEFRAME = '1H'

# =============================================================================
# 🛡️ AI PROMPTS (PORTFOLIO-BASED DECISION MAKING)
# =============================================================================

# Risk Management AI Prompt - Portfolio State Only
RISK_OVERRIDE_PROMPT = """
You are Anarcho Capital's Risk Management Agent 🛡️

Your task is to analyze the current portfolio state and make risk management decisions based on current performance metrics ONLY.

Available Actions:
- CLOSE_ALL: Close all positions immediately
- CLOSE_HALF: Close 50% of positions (worst performing first)
- CLOSE_PARTIAL: Close 25% of positions (worst performing first)
- HOLD_POSITIONS: Keep all positions open
- BREAKEVEN: Close positions at profit, hold positions at loss until breakeven
- EMERGENCY_STOP: Stop copybot agent and close all positions

Decision Factors:
1. TRIGGER: What triggered this risk check (PnL breach, consecutive losses, drawdown, etc.)
2. TIME: How long positions have been held
3. BALANCE: Current portfolio balance vs initial balance
4. ALLOCATION: Current position distribution and sizes

Current Portfolio State:
{portfolio_data}

Risk Metrics:
- Current PnL: ${current_pnl:.2f}
- Portfolio Balance: ${current_balance:.2f}
- Peak Balance: ${peak_balance:.2f}
- Drawdown: {drawdown_percentage:.2f}%
- Consecutive Losses: {consecutive_losses}
- Consecutive Wins: {consecutive_wins}
- Position Size Multiplier: {position_size_multiplier:.2f}

Respond in this exact format:
1. First line must be one of: CLOSE_ALL, CLOSE_HALF, CLOSE_PARTIAL, HOLD_POSITIONS, BREAKEVEN, EMERGENCY_STOP
2. Then explain your reasoning, including:
   - Risk assessment based on current metrics
   - Position performance analysis
   - Market condition considerations
   - Confidence level (as a percentage, e.g. 75%)

Remember: 
- Base decisions ONLY on current portfolio state
- No historical market data is available
- Prioritize capital preservation over potential gains
- Consider the trigger that activated this check
- Be conservative in volatile conditions
"""

# Breakeven Strategy Configuration
BREAKEVEN_ENABLED = True
BREAKEVEN_MIN_PROFIT_PERCENT = 0.01  # 1% minimum profit to close
BREAKEVEN_MAX_LOSS_PERCENT = -0.05   # 5% maximum loss before forced close
BREAKEVEN_TIMEOUT_MINUTES = 60       # Time to wait for breakeven before forced close
BREAKEVEN_PARTIAL_CLOSE_PERCENT = 0.25  # Close 25% of profitable positions

# Risk Management Actions Configuration
RISK_ACTIONS = {
    'CLOSE_ALL': {
        'description': 'Close all positions immediately',
        'severity': 'high',
        'conditions': ['emergency_stop', 'critical_drawdown', 'severe_loss']
    },
    'CLOSE_HALF': {
        'description': 'Close 50% of positions (worst performing first)',
        'severity': 'medium',
        'conditions': ['moderate_loss', 'consecutive_losses']
    },
    'CLOSE_PARTIAL': {
        'description': 'Close 25% of positions (worst performing first)',
        'severity': 'low',
        'conditions': ['minor_loss', 'risk_reduction']
    },
    'HOLD_POSITIONS': {
        'description': 'Keep all positions open',
        'severity': 'none',
        'conditions': ['good_performance', 'no_risk_breach']
    },
    'BREAKEVEN': {
        'description': 'Close profitable positions, hold loss positions until breakeven',
        'severity': 'medium',
        'conditions': ['mixed_performance', 'breakeven_strategy']
    },
    'EMERGENCY_STOP': {
        'description': 'Stop copybot agent and close all positions',
        'severity': 'critical',
        'conditions': ['emergency_conditions', 'system_risk']
    }
}

# Portfolio State Analysis Configuration
PORTFOLIO_ANALYSIS_CONFIG = {
    'PERFORMANCE_THRESHOLDS': {
        'EXCELLENT': 0.10,    # 10%+ profit
        'GOOD': 0.05,         # 5-10% profit
        'NEUTRAL': 0.00,      # 0-5% profit
        'POOR': -0.05,        # 0-5% loss
        'BAD': -0.10,         # 5-10% loss
        'CRITICAL': -0.15     # 10%+ loss
    },
    'POSITION_SIZE_THRESHOLDS': {
        'LARGE': 0.20,        # 20%+ of portfolio
        'MEDIUM': 0.10,       # 10-20% of portfolio
        'SMALL': 0.05,        # 5-10% of portfolio
        'MINI': 0.01          # 1-5% of portfolio
    },
    'TIME_THRESHOLDS': {
        'SHORT_TERM': 60,     # 1 hour
        'MEDIUM_TERM': 1440,  # 1 day
        'LONG_TERM': 10080    # 1 week
    }
}

# Staking Agent Configuration
# Note: AI analysis has been removed from the staking agent for streamlined operation
# The agent now uses direct protocol comparison and yield optimization without AI recommendations

# Chart Analysis AI Prompt
CHART_ANALYSIS_PROMPT = """
You must respond in exactly 4 lines:
Line 1: Only write BUY, SELL, or NOTHING
Line 2: One short reason why
Line 3: Only write "Confidence: X%" where X is 0-100
Line 4: Calculate the optimal entry price level based on indicators

Analyze the chart data for {symbol} {timeframe}:

{chart_data}

Remember:
- Look for confluence between multiple indicators
- Volume should confirm price action
- Consider the timeframe context - longer timeframes (4h, 1d, 1w) are better for DCA/staking strategies
- For longer timeframes, focus on major trend direction and ignore short-term noise
- Higher confidence is needed for longer timeframe signals
- If a previous recommendation is provided, consider:
  * How the price moved after that recommendation
  * Whether the signal should be maintained or changed based on new data
  * If a previous entry price was accurate, use it to improve your estimate
  * Signal consistency is valuable - avoid flip-flopping between BUY/SELL without clear reason

For optimal entry price calculation:
- Use support/resistance levels from chart patterns
- Consider moving averages as dynamic support/resistance
- Factor in volume-weighted average price (VWAP) if available
- Look for confluence between multiple technical levels
- Provide the price level, not just "current price" or "market price"
"""

# Harvesting Agent AI Prompt
HARVESTING_AI_PROMPT = """
You are Anarcho Capital's Harvesting Agent 🌾

Your task is to analyze the current portfolio state and make harvesting decisions based on realized and unrealized gains.

Available Actions:
- HARVEST_ALL: Harvest all gains and reallocate according to strategy
- HARVEST_PARTIAL: Harvest partial gains (50% of available gains)
- HARVEST_SELECTIVE: Harvest only specific high-performing positions
- HOLD_GAINS: Keep gains unrealized for further growth
- REALLOCATE_ONLY: Reallocate without harvesting new gains

Reallocation Strategy:
- SOL: {reallocation_sol_pct}%
- Staked SOL: {reallocation_staked_sol_pct}%
- USDC: {reallocation_usdc_pct}%
- External Wallet: {reallocation_external_pct}%

Current Portfolio State:
{portfolio_data}

Gain Analysis:
- Realized Gains Total: ${realized_gains_total:.2f}
- Unrealized Gains Total: ${unrealized_gains_total:.2f}
- Current Portfolio Balance: ${current_balance:.2f}
- Peak Portfolio Balance: ${peak_balance:.2f}
- Trigger: {trigger_type}

Respond in this exact format:
1. First line must be one of: HARVEST_ALL, HARVEST_PARTIAL, HARVEST_SELECTIVE, HOLD_GAINS, REALLOCATE_ONLY
2. Then explain your reasoning, including:
   - Gain assessment and market conditions
   - Risk vs reward analysis
   - Reallocation strategy justification
   - Confidence level (as a percentage, e.g. 75%)

Remember: 
- Focus on maximizing long-term portfolio growth while preserving capital
- Consider market volatility and trend direction
- Balance between taking profits and allowing positions to grow
- Factor in the trigger that activated this analysis
- Be strategic about reallocation timing
- Consider the opportunity cost of harvesting vs holding
"""

# =============================================================================
# 🔔 WEBHOOK CONFIGURATION
# =============================================================================

# Webhook server settings
WEBHOOK_MODE = True  # Enable webhook mode by default
WEBHOOK_HOST = "0.0.0.0"  # Listen on all interfaces
WEBHOOK_PORT = int(os.getenv('PORT', 10000))  # Use PORT from env or default to 10000
WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', f"http://{WEBHOOK_HOST}:{WEBHOOK_PORT}")

# Webhook processing settings
WEBHOOK_MIN_TOKEN_VALUE_USD = 0.01  # Minimum token value to process (lowered for testing)
WEBHOOK_RETRY_ATTEMPTS = 3  # Number of retry attempts for failed webhooks
WEBHOOK_DEBUG_MODE = True  # Enable debug logging for webhooks
WEBHOOK_LOG_LEVEL = "INFO"  # Webhook logging level

# Active agents configuration (as dictionary)
WEBHOOK_ACTIVE_AGENTS = {
    'copybot': True,      # CopyBot agent
    'risk': True,         # Risk management agent
    'rebalancing': True,  # Portfolio rebalancing agent
    'harvesting': True,   # Profit harvesting agent
    'staking': True,      # Automated staking agent
    'whale': True         # Whale tracking agent
}

# Helius webhook settings (free tier)
WEBHOOK_TYPES = ["ANY"]  # Track ALL transaction types for comprehensive monitoring
WEBHOOK_ENHANCED_MODE = True  # Enhanced mode for better transaction data
WEBHOOK_UPDATE_INTERVAL = 3600  # Update webhook registration hourly
WEBHOOK_HEALTH_CHECK_INTERVAL = 60  # Health check interval in seconds

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
    if USE_DYNAMIC_POSITION_SIZING:
        if account_balance < SMALL_ACCOUNT_THRESHOLD:
            return account_balance * NEW_POSITION_SMALL_ACCOUNT_PERCENT
        else:
            return account_balance * NEW_POSITION_BASE_PERCENT
    else:
        return BASE_POSITION_SIZE_USD

def _validate_configuration():
    """
    Validate configuration settings and raise errors for invalid values.
    """
    # Add validation logic here
    if MAX_LOSS_PERCENT <= 0 or MAX_LOSS_PERCENT >= 100:
        raise ValueError("MAX_LOSS_PERCENT must be between 0 and 100")
    
    if MAX_GAIN_PERCENT <= 0:
        raise ValueError("MAX_GAIN_PERCENT must be greater than 0")
    
    if WEEKLY_BUDGET_USD <= 0:
        raise ValueError("WEEKLY_BUDGET_USD must be greater than 0")
    
    if BASE_POSITION_SIZE_USD <= 0:
        raise ValueError("BASE_POSITION_SIZE_USD must be greater than 0")

# =============================================================================
# 🚀 OPTIMIZED PRICE SERVICE CONFIGURATION
# =============================================================================

# QuickNode Configuration (for optimized price fetching)
QUICKNODE_RPC_ENDPOINT = os.getenv('QUICKNODE_RPC_ENDPOINT', 'https://your-quicknode-endpoint.com')
QUICKNODE_WSS_ENDPOINT = os.getenv('QUICKNODE_WSS_ENDPOINT', 'wss://your-quicknode-endpoint.com')
QUICKNODE_TOKEN_METRICS_API = os.getenv('QUICKNODE_TOKEN_METRICS_API', 'true').lower() == 'true'

# Price Source Mode Configuration
# Options: 'jupiter' (Jupiter -> Birdeye -> Pump.fun) or 'birdeye' (Birdeye -> Jupiter -> Pump.fun)
# Jupiter mode is generally faster for most tokens
PRICE_SOURCE_MODE = os.getenv('PRICE_SOURCE_MODE', 'jupiter')

# Run validation on import
_validate_configuration()
