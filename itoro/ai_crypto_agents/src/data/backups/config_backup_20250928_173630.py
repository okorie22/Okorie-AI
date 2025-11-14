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
PAPER_TRADING_ENABLED = True # Set to False for live trading mode
PAPER_INITIAL_BALANCE = 1000.0  # Initial paper trading balance in USD
PAPER_TRADING_SLIPPAGE = 104  # Simulated slippage for paper trades (100 = 1%)
PAPER_TRADING_RESET_ON_START = True  # Whether to reset paper portfolio on app start
PAPER_TRADING_INITIAL_BALANCE = 1000.0
PAPER_TRADING_DB_PATH = os.path.join('src', 'data', 'paper_trading.db')

# Portfolio Reset Configuration
PORTFOLIO_RESET_ENABLED = True  # Enable portfolio reset when PORTFOLIO_RESET_CLEAR_HISTORY is True
PORTFOLIO_RESET_PRESERVE_LIVE_BALANCE = True  # Keep current live wallet balance when resetting
PORTFOLIO_RESET_CLEAR_HISTORY = True  # Clear all historical data (snapshots, PnL, capital flows)
PORTFOLIO_RESET_CLEAR_PEAK_BALANCE = True  # Reset peak balance to current value
PORTFOLIO_RESET_REASON = "Manual reset via config"  # Reason for the reset (for logging)


# Paper trading position limits
PAPER_MAX_POSITION_SIZE = 1000.0  # Maximum size for any single position in USD
PAPER_MIN_POSITION_SIZE = 10   # Minimum position size in USD
PAPER_MAX_TOTAL_ALLOCATION = 0.65  # Maximum 95% of portfolio can be allocated

# Status update interval (in seconds)
STATUS_UPDATE_INTERVAL = 3600  # Update status display every 1 hour

# =============================================================================
# 🔊 LOGGING CONFIGURATION
# =============================================================================

# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "DEBUG"  # Set to DEBUG for detailed troubleshooting
BIRDEYE_API_DEBUG = True  # Enable Birdeye API debugging
PRICE_SERVICE_DEBUG = True  # Enable detailed price service logging

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
RISK_MODEL_OVERRIDE = "deepseek-chat"
RISK_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
COPYBOT_MODEL_OVERRIDE = "deepseek-chat"
DCA_MODEL_OVERRIDE = "deepseek-chat"
DCA_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
CHART_MODEL_OVERRIDE = "deepseek-chat"  # Use the correct DeepSeek model name
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
# Prioritized scoring: PNL (30d > 7d > 1d) → Winrate → Holding Period → Token Active → Others
WHALE_SCORING_WEIGHTS = {
    'pnl_30d': 0.35,           # 30-day PnL weight (highest priority - long-term profitability)
    'pnl_7d': 0.20,            # 7-day PnL weight (medium-term consistency)
    'pnl_1d': 0.03,          # 1-day PnL weight (short-term performance)
    'winrate_7d': 0.20,        # 7-day win rate weight (consistency indicator)
    'avg_holding_period_7d': 0.10,  # Holding period weight (trading style indicator)
    'token_active': 0.10,    # Active tokens weight (diversification, maintain threshold)
    'is_blue_verified': 0.01,  # Twitter verification weight (credibility)
    'txs_30d': 0.01            # Transaction count weight (inverse - activity level)
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
WHALE_MAX_STORED_WALLETS = 100   # Maximum wallets to store
WHALE_HISTORY_MAX_RECORDS = 1000 # Maximum history entries to keep
WHALE_HISTORY_RETENTION_DAYS = 365 # Keep 365 days of history data

# =============================================================================
# 💰 CORE TRADING CONFIGURATION
# =============================================================================

# Core token addresses for mainnet trading
USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Never trade or close
SOL_ADDRESS = "So11111111111111111111111111111111111111112"  # Never trade or close

# Define excluded tokens and rebalancing allowed tokens AFTER dynamic address assignment
EXCLUDED_TOKENS = [USDC_ADDRESS, SOL_ADDRESS]

# Tokens that can be used for rebalancing (but not regular trading)
REBALANCING_ALLOWED_TOKENS = [USDC_ADDRESS, SOL_ADDRESS]  # USDC and SOL can be sold for rebalancing

# Get wallet address from environment variable 
address = os.getenv('DEFAULT_WALLET_ADDRESS')
# Back-compat alias used by some modules
DEFAULT_WALLET_ADDRESS = address

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

def debug_birdeye_api_key():
    """Debug function to verify BIRDEYE_API_KEY loading"""
    api_key = os.getenv("BIRDEYE_API_KEY")
    if api_key:
        print(f"BIRDEYE_API_KEY loaded successfully: {api_key[:8]}...{api_key[-4:]}")
        return True
    else:
        print("BIRDEYE_API_KEY not found in environment variables")
        print("Checking all environment variables containing 'BIRDEYE'...")
        for key, value in os.environ.items():
            if 'BIRDEYE' in key.upper():
                print(f"  Found: {key} = {value[:8]}...{value[-4:]}")
        return False

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

# Paper Trading Settings (using existing configuration from above)

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
RPC_MAX_RETRIES = 5  # Increased from 3 to 5 for better resilience
RPC_RETRY_DELAY = 2.0  # Increased from 1.0 to 2.0 seconds
RPC_TIMEOUT = 20  # Increased from 15 to 20 seconds
RPC_IGNORE_AUTH_ERRORS = True  # Ignore 401 errors for free RPC endpoints
RPC_HEALTH_CHECK_INTERVAL = 60  # Check RPC health every 60 seconds

# QuickNode API Access (from your add-ons)
QUICKNODE_TOKEN_METRICS_API = True  # Token price, OHLCV, sentiment
QUICKNODE_PRIORITY_FEE_API = True   # Priority fee data
QUICKNODE_MEV_RESILIENCE = True     # MEV protection
QUICKNODE_PUMPFUN_API = True        # Pump.fun integration
QUICKNODE_JUPITER_SWAP_API = True   # Jupiter swap integration
QUICKNODE_OPENOCEAN_API = True      # OpenOcean integration

# Jupiter API configuration
JUPITER_API_KEY = os.getenv('JUPITER_API_KEY', '')  # Optional - Jupiter works without API key

# Use Jupiter v6 for mainnet (with Address Lookup Tables)
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
API_TIMEOUT_SECONDS = 20  # INCREASED: From 15 to 20 seconds for Jupiter API reliability
API_MAX_RETRIES = 3  # INCREASED: From 2 to 3 retries for better failure handling
JUPITER_API_TIMEOUT = 20  # Jupiter-specific timeout for price fetching and trading
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

PRICE_SOURCE_MODE = os.getenv('PRICE_SOURCE_MODE', 'birdeye')  # Use Birdeye with paid subscription
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

# Hybrid approach configuration - DISABLED for paid Birdeye tier
USE_HYBRID_PRICE_FETCHING = False  # Use Birdeye exclusively with paid subscription
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

# Price validation optimization settings
PRICE_VALIDATION_ENABLED = True
PRICE_VALIDATION_FREQUENCY_MINUTES = 5  # Only validate every 5 minutes instead of every price fetch
PRICE_VALIDATION_CACHE_THRESHOLD = 60   # Skip validation if price is < 60 seconds old and similar
PRICE_CHANGE_THRESHOLD = 0.01  # Only revalidate if price changes by more than 1%
MAX_PRICE_VALIDATION_CALLS_PER_HOUR = 120  # Limit to 120 validations per hour max

# Enhanced caching for performance
PRICE_CACHE_OPTIMIZATION = True
SMART_PRICE_CACHING = True  # Enable smart caching that skips validation for stable prices

# =============================================================================
# 🎯 POSITION SIZING & RISK MANAGEMENT
# =============================================================================

# Position sizing (OPTIMIZED FOR $115/WEEK SWING TRADING)
POSITION_SIZING_MODE = "dynamic"  # "fixed" or "dynamic"
BASE_POSITION_SIZE_USD = 20.0  # Base position size for swing trades
POSITION_SIZE_PERCENTAGE = 0.05  # 5% for swing trade conviction

MIN_POSITION_SIZE_USD = 1.0  # Minimum viable swing position
MAX_POSITION_SIZE_USD = 1000.0  # Maximum position size

# Weekly budget management
WEEKLY_BUDGET_USD = 115.0  # Weekly deposit target
MAX_WEEKLY_POSITIONS = 6  # Maximum new positions per week
SWING_TRADE_HOLD_PERIOD_DAYS = 5  # Target hold period
CASH_RESERVE_PERCENTAGE = 20  # Keep 25% in USDC for opportunities

# Dynamic position sizing
USE_DYNAMIC_POSITION_SIZING = True
NEW_POSITION_BASE_PERCENT = 0.02  # Base percentage for new positions
NEW_POSITION_SMALL_ACCOUNT_PERCENT = 0.02  # Percentage when account < $1000
SMALL_ACCOUNT_THRESHOLD = 1000.0  # Threshold for small account protection
MAX_POSITION_INCREASE_PERCENT = 0.05  # Max increase as % of account

# Position limits
MAX_CONCURRENT_POSITIONS = 10  # Maximum simultaneous positions
MAX_TOTAL_ALLOCATION_PERCENT = 0.60  # Maximum total allocation

# Dust handling
# Any non-zero balance with USD value <= DUST_THRESHOLD_USD OR < $0.01 is treated as dust
DUST_THRESHOLD_USD = 1.0  # More aggressive dust cleanup
ALLOW_EXCLUDED_DUST = True  # Permit dust conversion even for excluded tokens

# Risk management settings
CASH_PERCENTAGE = 20  # Cash buffer percentage
MAX_SINGLE_POSITION_PERCENT = 0.10  # 12% max for highest conviction
SLEEP_AFTER_CLOSE = 1800
MAX_LOSS_GAIN_CHECK_HOURS = 24  # Monitoring window

# Max Loss/Gain Settings
USE_PERCENTAGE = True  # Use percentage-based limits vs USD
MAX_LOSS_USD = 50.0  # Maximum loss in USD
MAX_GAIN_USD = 200.0  # Maximum gain in USD
MAX_LOSS_PERCENT = 10  # Maximum loss percentage
MAX_GAIN_PERCENT = 300  # Maximum gain percentage
MINIMUM_BALANCE_USD = 0  # Minimum balance limit for risk management

# Enhanced risk management
RISK_MANAGEMENT_ENABLED = True
EMERGENCY_STOP_ENABLED = True
DRAWDOWN_LIMIT_PERCENT = -0.16  # 10% maximum drawdown
CONSECUTIVE_LOSS_LIMIT = 6  # Maximum consecutive losses
POSITION_SIZE_SCALING = True  # Scale position size based on performance
CORRELATION_LIMIT = 0.5  # Maximum correlation between positions
VOLATILITY_ADJUSTMENT = True  # Adjust position sizes based on volatility

# Enhanced Emergency Stop Configuration
EMERGENCY_STOP_INTELLIGENT_DECISION = True  # Enable intelligent decision between close all vs breakeven
EMERGENCY_STOP_BREAKEVEN_MIN_CONFIDENCE = 70  # Minimum confidence required for breakeven strategy
EMERGENCY_STOP_CRITICAL_LOSS_THRESHOLD = -25  # Close positions with >15% loss immediately
EMERGENCY_STOP_LARGE_POSITION_LOSS_THRESHOLD = -10  # Close large positions with >10% loss
EMERGENCY_STOP_LARGE_POSITION_SIZE_USD = 50  # USD threshold for "large" positions
EMERGENCY_STOP_BREAKEVEN_CANDIDATE_THRESHOLD = 5  # Positions within 5% of breakeven are candidates
EMERGENCY_STOP_FALLBACK_ENABLED = True  # Enable fallback to close all if strategy fails
EMERGENCY_STOP_MARKET_SENTIMENT_WEIGHT = 0.3  # Weight given to market sentiment in decision
EMERGENCY_STOP_POSITION_ANALYSIS_WEIGHT = 0.4  # Weight given to position analysis in decision
EMERGENCY_STOP_DRAWDOWN_WEIGHT = 0.3  # Weight given to drawdown in decision

# Drawdown recovery threshold (50% improvement required)
DRAWDOWN_RECOVERY_THRESHOLD = 0.5  # 50% improvement required

# SOL fee reserve percentage
SOL_FEE_RESERVE_PERCENT = 5.0  # 5% of portfolio for SOL fees

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

# Agent coordination flags
HARVESTING_STARTUP_DONE = False  # Global flag for CopyBot coordination

# Agent Priority Configuration (Higher number = Higher priority)
AGENT_PRIORITIES = {
    'RISK': 100,        # Risk agent has highest priority
    'HARVESTING': 80,   # Harvesting agent has high priority
    'COPYBOT': 20,      # Copybot has lower priority
    'STAKING': 10       # Staking has lowest priority
}

# Agent Halt Flags
COPYBOT_HALT_FLAGS = {
    'ENABLED': True,                    # Enable copybot halt mechanism
    'HARVESTING_REBALANCING': True,     # Halt copybot during harvesting rebalancing
    'USDC_LOW_THRESHOLD': 0.20,        # Halt copybot when USDC < 5%
    'SOL_LOW_THRESHOLD': 0.02,         # Halt copybot when SOL < 2%
    'MAX_ALLOCATION_EXCEEDED': True,    # Halt copybot when max allocation exceeded
    'SINGLE_POSITION_EXCEEDED': True,  # ← ENABLE THIS to stop when single position > 10%
    'DRAWDOWN_BREACH': True            # Halt copybot when drawdown limit exceeded
}

# Position Validation Settings
POSITION_VALIDATION = {
    'ENABLED': True,                    # Enable position validation for all agents
    'VALIDATE_BEFORE_SELL': True,      # Validate position exists before selling
    'VALIDATE_BEFORE_BUY': True,       # Validate USDC balance before buying
    'MIN_POSITION_SIZE_USD': 0.01,     # Minimum position size to validate
    'VALIDATION_TIMEOUT_SECONDS': 5    # Timeout for position validation
}

# USDC Balance Validation
USDC_VALIDATION = {
    'ENABLED': True,                    # Enable USDC balance validation
    'MIN_BALANCE_USD': 10.0,           # Minimum USDC balance required
    'WARNING_THRESHOLD_USD': 50.0,     # USDC balance warning threshold
    'CRITICAL_THRESHOLD_USD': 20.0,    # USDC balance critical threshold
    'BLOCK_TRADING_BELOW_MIN': True    # Block trading when below minimum
}

# Trade Lock Manager Settings
TRADE_LOCK_SETTINGS = {
    'ENABLED': True,                    # Enable trade lock manager
    'DEFAULT_LOCK_DURATION': 300,      # Default lock duration in seconds
    'REBALANCING_LOCK_DURATION': 600,  # Rebalancing lock duration
    'CONFLICT_RESOLUTION_TIMEOUT': 60, # Timeout for conflict resolution
    'AUTO_RELEASE_EXPIRED': True       # Auto-release expired locks
}

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
    "DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt",  
    "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm", 
    "4BdKaxN8G6ka4GYtQQWk4G4dZRUTX2vQH9GcXdBREFUk",
    "EHg5YkU2SZBTvuT87rUsvxArGp3HLeye1fXaSDfuMyaf",
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
ENABLE_AI_ANALYSIS = True
COPYBOT_AUTO_BUY_NEW_TOKENS = True
COPYBOT_AUTO_SELL_REMOVED_TOKENS = False  # DISABLED: Prevents selling tokens not held
COPYBOT_WALLET_ACTION_WEIGHT = 0.7
COPYBOT_MIN_CONFIDENCE = 80
COPYBOT_MIRROR_EXACT_PERCENTAGE = False  # Use fixed sizing for safety

# CopyBot Safety Configuration (CRITICAL)
COPYBOT_VALIDATE_HOLDINGS_BEFORE_SELL = True  # Always validate holdings before selling
COPYBOT_MAX_SELL_PERCENTAGE = 100.0  # Maximum percentage of position to sell
COPYBOT_MIN_BALANCE_THRESHOLD = 0.001  # Minimum balance required to execute sell
COPYBOT_BLOCK_ZERO_BALANCE_SELLS = True  # Block sell attempts when balance is zero

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

# Rebalancing Agent Settings (DEPRECATED)
# REBALANCING_ENABLED = True
# REBALANCING_WEBHOOK_FIRST_MODE = True  # Webhook-driven operation (resource efficient)
# REBALANCING_FALLBACK_CHECK_HOURS = 2   # Fallback check every 2 hours
# REBALANCING_CHECK_INTERVAL_MINUTES = 30
# REBALANCING_CONTINUOUS_MODE = False

# =============================================================================
# ⚖️ REBALANCING AGENT CONFIGURATION (DEPRECATED)
# =============================================================================

# All portfolio management is now handled by HarvestingAgent. The following variables are deprecated:
# REBALANCING_ENABLED = True
# REBALANCING_CHECK_INTERVAL_MINUTES = 30
# REBALANCING_CONTINUOUS_MODE = False
# REBALANCING_SELL_STRATEGY = "worst_performing"
# REBALANCING_MAX_SELL_PERCENT = 0.30
# REBALANCING_MIN_POSITION_SIZE = 0.5
# REBALANCING_MAX_FREQUENCY_MINUTES = 5
# REBALANCING_EMERGENCY_MODE = True
# REBALANCING_DRY_RUN = False
# REBALANCING_LOG_LEVEL = "INFO"

# The following variables are still used by HarvestingAgent for portfolio management:
SOL_TARGET_PERCENT = 0.10  # Target 10% of portfolio in SOL
SOL_MINIMUM_PERCENT = 0.07  # Minimum 7% SOL before triggering conversion
SOL_MAXIMUM_PERCENT = 0.20  # Maximum 20% SOL before converting to USDC
SOL_MINIMUM_BALANCE_USD = 10.0  # Minimum $10 SOL balance
USDC_TARGET_PERCENT = 0.20  # Target 20% of portfolio in USDC
USDC_MINIMUM_PERCENT = 0.15  # Minimum 15% USDC before selling positions
USDC_EMERGENCY_PERCENT = 0.10  # Emergency threshold - force position sales (10%)
MIN_CONVERSION_USD = 10.0  # Minimum $10 for conversions
MAX_CONVERSION_USD = 1000.0  # Maximum $100 single conversion for safety
REBALANCING_MAX_SELL_PERCENT = 0.30  # Never sell more than 30% in one rebalancing
REBALANCING_MIN_POSITION_SIZE = 0.5  # Don't sell positions smaller than $0.50
CONVERSION_SLIPPAGE_BPS = 300  # 3% slippage for SOL/USDC conversions
REBALANCING_PRIORITY_FEE = 150000  # Higher priority fee for rebalancing

# =============================================================================
# 🌾 HARVESTING AGENT CONFIGURATION
# =============================================================================

# Dynamic unrealized gains thresholds for AI analysis
# These are percentage-based thresholds that trigger AI analysis
UNREALIZED_GAINS_THRESHOLDS = [0.20, 0.50, 0.75, 1.00, 1.50, 2.00]  # 20%, 50%, 75%, 100%, 150%, 200%
UNREALIZED_GAINS_AI_ANALYSIS_ENABLED = True  # Enable AI analysis for unrealized gains decisions

# Realized gains reallocation settings
REALIZED_GAINS_REALLOCATION_INCREMENT = 0.05  # 5% growth increment for reallocation
REALIZED_GAINS_REALLOCATION_ENABLED = True  # Enable automatic reallocation of realized gains

# Harvesting agent behavior
HARVESTING_DUST_CONVERSION_ENABLED = True  # Auto-convert dust to SOL
HARVESTING_REBALANCING_ENABLED = True  # Enable portfolio rebalancing
HARVESTING_AI_DECISION_ENABLED = True  # Enable AI-driven decisions for harvesting

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
REALLOCATION_STAKED_SOL_PCT = 0.15  # 25% to Staked SOL
REALLOCATION_USDC_PCT = 0.60  # 50% to USDC
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

# Market Analysis Token Configuration
TOKEN_MAP = {
    'So11111111111111111111111111111111111111112': ('SOL', 'SOL'),  # Solana
    'EKpQGSJtjMFqKZ1KQanSqYXRcF8fBopzLHYxdM65Qjm': ('WIF', 'WIF'),  # WIF
    'ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82': ('BOME', 'BOME'),  # BOME
    'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL': ('JTO', 'JTO'),  # JTO
    'HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3': ('PYTH', 'PYTH'),  # PYTH
}

DCA_MONITORED_TOKENS = [
    'So11111111111111111111111111111111111111112',  # SOL
    'EKpQGSJtjMFqKZ1KQanSqYXRcF8fBopzLHYxdM65Qjm',  # WIF
    'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
    '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump',  # FART
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
STAKING_ALLOCATION_PERCENT = 10  # Percentage of SOL to stake
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
STAKING_START_DATE = "2025-09-25"  # Start date (YYYY-MM-DD) - 7 days from now
STAKING_START_TIME = "09:00"  # Start time (HH:MM)
STAKING_REPEAT_DAYS = 7  # Repeat every 7 days

# Staking safety thresholds
MIN_SOL_ALLOCATION_THRESHOLD = 1.0  # Minimum 5% SOL allocation (never stake below this)
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
CHART_ANALYSIS_INTERVAL_MINUTES = 60  # 24 hours (1 day)
CHART_INTERVAL_UNIT = "Day(s)"
CHART_INTERVAL_VALUE = 1
CHART_RUN_AT_ENABLED = True
CHART_RUN_AT_TIME = "09:00"  # Run at 9 AM daily
CHART_INITIAL_DELAY_HOURS = 0  # Wait 1 hour before first analysis
TIMEFRAMES = ['4h']
LOOKBACK_BARS = 300  # Increase from 104 to 300
ENABLE_FIBONACCI = True  # Enable Fibonacci retracement analysis
FIBONACCI_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIBONACCI_LOOKBACK_PERIODS = 75  # Increase from 60 to 75
CHART_INDICATORS = ['20EMA', '50EMA', '100EMA', '200SMA', 'MACD', 'RSI', 'ATR']
CHART_STYLE = 'yahoo'
CHART_VOLUME_PANEL = True
ENABLE_CHART_ANALYSIS = True

# Fibonacci retracement settings (using existing configuration from above)

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

# =============================================================================
# 💱 HYPERLIQUID CONFIGURATION
# =============================================================================

# Token to Hyperliquid Symbol Mapping
TOKEN_TO_HL_MAPPING = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EKpQGSJtjMFqKZ1KQanSqYXRcF8fBopzLHYxdM65Qjm": "WIF",
    "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82": "BOME",
    "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL": "JTO",
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3": "PYTH",
}

# External Market Data Configuration (removed - focusing on Solana ecosystem tokens)
# EXTERNAL_MARKET_DATA = {}  # No external tokens needed

# =============================================================================
# 🔍 BACKTESTING CONFIGURATION
# =============================================================================

DAYSBACK_4_DATA = 6
DATA_TIMEFRAME = '1H'

# =============================================================================
# 🛡️ AI PROMPTS (PORTFOLIO-BASED DECISION MAKING)
# =============================================================================

# Risk Management AI Prompt - Portfolio State with Market Sentiment
RISK_OVERRIDE_PROMPT = """
You are Anarcho Capital's Risk Management Agent 🛡️

Your task is to analyze the current portfolio state and make risk management decisions based on current performance metrics and market sentiment analysis.

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
5. SENTIMENT: Current market sentiment from technical and social analysis
6. EXECUTION_HISTORY: Recent agent execution patterns and success rates

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

{market_sentiment_data}

{execution_history_insights}

Respond in this exact format:
1. First line must be one of: CLOSE_ALL, CLOSE_HALF, CLOSE_PARTIAL, HOLD_POSITIONS, BREAKEVEN, EMERGENCY_STOP
2. Then explain your reasoning, including:
   - Risk assessment based on current metrics
   - Position performance analysis
   - Market sentiment impact on decision
   - Technical vs social sentiment alignment consideration
   - Whale wallet performance insights consideration
   - Recent execution success patterns
   - Confidence level (as a percentage, e.g. 75%)

Remember: 
- Base decisions on current portfolio state AND market sentiment
- Market sentiment should influence risk tolerance (bearish = more conservative, bullish = potentially hold longer)
- Prioritize capital preservation over potential gains
- Consider sentiment alignment - conflicting signals warrant more caution
- Be more conservative when sentiment data is stale or unavailable
- Strong bearish sentiment may justify earlier position closure
- Strong bullish sentiment may justify holding through temporary drawdowns
- Consider whale wallet performance trends as market sentiment indicators
- Factor in recent execution success rates for confidence assessment
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

# Chart Analysis AI Prompt - Enhanced for More Aggressive Trading
CHART_ANALYSIS_PROMPT = """
You must respond in exactly 4 lines:
Line 1: Only write BUY, SELL, or NOTHING
Line 2: One short reason why
Line 3: Only write "Confidence: X%" where X is 65-100 (minimum 65% confidence required)
Line 4: Calculate the optimal entry price level based on indicators

Analyze the chart data for {symbol} {timeframe}:

{chart_data}

CRITICAL TRADING RULES - BE AGGRESSIVE:
- NEVER default to NOTHING unless absolutely no clear direction exists
- RSI < 30 (oversold) = AUTOMATIC BUY signal with 70-80% confidence
- RSI > 70 (overbought) = AUTOMATIC SELL signal with 70-80% confidence
- MACD bullish crossover = BUY signal, bearish crossover = SELL signal
- Volume spikes = Action triggers, not just analysis
- Trend changes = Immediate position changes, not waiting
- VOLATILE_BREAKOUT regime = Must take action, not observe

CONFIDENCE GUIDELINES (65% minimum):
- 65-70%: Good technical setup with some uncertainty
- 75-80%: Strong technical confluence with clear direction
- 85-90%: Multiple indicators aligned with volume confirmation
- 95-100%: Exceptional setup with minimal risk

AUTOMATIC SIGNAL TRIGGERS:
- RSI < 30 + MACD turning bullish = BUY (70-75% confidence)
- RSI > 70 + MACD turning bearish = SELL (70-75% confidence)
- Strong trend with volume = Follow trend direction (75-85% confidence)
- Breakout with volume = Enter in breakout direction (80-90% confidence)
- Support/resistance tests = Enter on successful tests (70-80% confidence)

TRADING LOGIC:
- Oversold conditions = BUY opportunities, not wait
- Overbought conditions = SELL opportunities, not wait
- Trend following = Active participation, not observation
- Breakout trading = Immediate entry, not analysis
- Only NOTHING when truly no technical setup exists

Remember:
- Look for confluence between multiple indicators
- Volume should confirm price action
- Consider the timeframe context - longer timeframes (4h, 1d, 1w) are better for DCA/staking strategies
- For longer timeframes, focus on major trend direction and ignore short-term noise
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

# Harvesting Agent AI Prompt with Market Sentiment
HARVESTING_AI_PROMPT = """
You are Anarcho Capital's Harvesting Agent 🌾

Your task is to analyze the current portfolio state and make harvesting decisions based on realized and unrealized gains, enhanced with market sentiment analysis.

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

{market_sentiment_data}

Respond in this exact format:
1. First line must be one of: HARVEST_ALL, HARVEST_PARTIAL, HARVEST_SELECTIVE, HOLD_GAINS, REALLOCATE_ONLY
2. Then explain your reasoning, including:
   - Gain assessment and current market sentiment
   - Risk vs reward analysis considering technical and social sentiment
   - Market sentiment impact on harvesting timing
   - Sentiment alignment influence on position holding decisions
   - Recent execution success patterns
   - Reallocation strategy justification
   - Confidence level (as a percentage, e.g. 75%)

Remember: 
- Focus on maximizing long-term portfolio growth while preserving capital
- Strong bullish sentiment may justify holding gains longer for additional growth
- Strong bearish sentiment may warrant earlier profit-taking and increased USDC allocation
- Conflicting sentiment signals suggest partial harvesting approach
- Consider sentiment data freshness - stale data warrants more conservative approach
- Factor in the trigger that activated this analysis
- Be strategic about reallocation timing based on market conditions
- Social sentiment can indicate retail investor behavior and potential market tops/bottoms
- Technical sentiment provides insight into institutional and algorithmic trading patterns
- Recent execution success rates provide confidence in current strategy effectiveness
"""

# =============================================================================
# 🎭 SENTIMENT AGENT CONFIGURATION
# =============================================================================

# Sentiment Agent Settings
SENTIMENT_ENABLED = True
SENTIMENT_TOKENS_TO_TRACK = ["Solana", "Bitcoin"]  # Tokens to track for sentiment
SENTIMENT_TWEETS_PER_RUN = 100  # Number of tweets to collect per run
SENTIMENT_DATA_FOLDER = "src/data/sentiment"  # Where to store sentiment data
SENTIMENT_HISTORY_FILE = "src/data/sentiment_history.csv"  # Store sentiment scores over time
SENTIMENT_SQLITE_DB_FILE = "src/data/sentiment_analysis.db"  # SQLite database for structured storage
SENTIMENT_IGNORE_LIST = ['t.co', 'discord', 'join', 'telegram', 'discount', 'pay', 'airdrop', 'giveaway']
SENTIMENT_CHECK_INTERVAL_MINUTES = 60  # How often to run sentiment analysis
SENTIMENT_DATA_RETENTION_DAYS = 30  # Keep data for 30 days

# Analysis modes
SENTIMENT_ANALYSIS_MODE_SHORT_TERM = "short_term"  # Immediate post-scrape analysis
SENTIMENT_ANALYSIS_MODE_LONG_TERM = "long_term"   # 30-day cumulative analysis
SENTIMENT_DEFAULT_ANALYSIS_MODE = SENTIMENT_ANALYSIS_MODE_SHORT_TERM

# Sentiment classification settings
SENTIMENT_ANNOUNCE_THRESHOLD = 0.4  # Announce vocally if abs(sentiment) > this value (-1 to 1 scale)
SENTIMENT_BULLISH_THRESHOLD = 0.2   # Above this is BULLISH
SENTIMENT_BEARISH_THRESHOLD = -0.2  # Below this is BEARISH
# Between thresholds is NEUTRAL

# Engagement metrics weights for enhanced sentiment scoring
SENTIMENT_LIKES_WEIGHT = 0.3
SENTIMENT_RETWEETS_WEIGHT = 0.4
SENTIMENT_REPLIES_WEIGHT = 0.2
SENTIMENT_QUOTES_WEIGHT = 0.1

# Voice settings for sentiment announcements
SENTIMENT_VOICE_ENABLED = False #Set to False to disable voice announcements
SENTIMENT_VOICE_MODEL = "tts-1"  # or tts-1-hd for higher quality
SENTIMENT_VOICE_NAME = "nova"   # Options: alloy, echo, fable, onyx, nova, shimmer
SENTIMENT_VOICE_SPEED = 1      # 0.25 to 4.0

# Apify settings for sentiment agent
SENTIMENT_APIFY_ACTOR_ID = "web.harvester~easy-twitter-search-scraper"
SENTIMENT_MAX_RETRIES = 3
SENTIMENT_RETRY_DELAY = 5  # seconds

# Sentiment AI Model Configuration
SENTIMENT_MODEL_OVERRIDE = "deepseek-chat"  # Options: claude-3-haiku-20240307, deepseek-chat, deepseek-reasoner
SENTIMENT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
SENTIMENT_AI_TEMPERATURE = 0.7
SENTIMENT_AI_MAX_TOKENS = 1024

# BERT Model Configuration (for sentiment analysis)
SENTIMENT_BERT_MODEL = "finiteautomata/bertweet-base-sentiment-analysis"
SENTIMENT_BERT_BATCH_SIZE = 8  # Process in small batches to avoid memory issues

# =============================================================================
# 🔔 WEBHOOK CONFIGURATION
# =============================================================================

# Webhook server settings
WEBHOOK_MODE = True  # Enable webhook mode by default
WEBHOOK_HOST = "127.0.0.1"  # Default fallback - will be auto-updated
WEBHOOK_PORT = int(os.getenv('PORT', 10000))  # Use PORT from env or default to 10000

def get_local_ip_address():
    """Automatically detect the local IP address for webhook configuration"""
    try:
        import socket
        # Create a socket connection to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Connect to a remote address (doesn't actually send data)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            return local_ip
    except Exception:
        # Fallback to localhost if detection fails
        return "127.0.0.1"

# Auto-detect and set webhook host
if os.getenv('RENDER'):
    # On Render, use the public service URL
    WEBHOOK_HOST = "helius-webhook-handler.onrender.com"
    WEBHOOK_BASE_URL = f"https://{WEBHOOK_HOST}"
    print(f"Render environment detected - using public webhook host: {WEBHOOK_HOST}")
else:
    # Local development - auto-detect IP
    WEBHOOK_HOST = get_local_ip_address()
    WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', f"http://{WEBHOOK_HOST}:{WEBHOOK_PORT}")
    print(f"Local environment detected - auto-detected webhook host: {WEBHOOK_HOST}")

print(f"Webhook URL: {WEBHOOK_BASE_URL}")

# Webhook processing settings
WEBHOOK_MIN_TOKEN_VALUE_USD = 0.001  # Minimum token value to process (lowered for testing)
WEBHOOK_RETRY_ATTEMPTS = 3  # Number of retry attempts for failed webhooks
WEBHOOK_DEBUG_MODE = True  # Enable debug logging for webhooks
WEBHOOK_LOG_LEVEL = "INFO"  # Webhook logging level

# Active agents configuration (as dictionary)
WEBHOOK_ACTIVE_AGENTS = {
    'copybot': True,      # 🤖 CopyBot agent
    'risk': True,        # 🛡️ Risk management agent
    'harvesting': True,  # 🌾 Portfolio/harvesting agent
    'staking': True,     # 🔒 Automated staking agent
}

# Staking agent cooldown configuration
STAKING_COOLDOWN_MINUTES = 30  # 30 minutes cooldown between staking triggers
STAKING_WEBHOOK_ACTIVITY_THRESHOLD = 3600  # 1 hour - skip intervals if webhook activity within this time

# Helius webhook settings (free tier)
WEBHOOK_TYPES = ["ANY"]  # Track ALL transaction types for comprehensive monitoring
WEBHOOK_ENHANCED_MODE = True  # Enhanced mode for better transaction data
WEBHOOK_UPDATE_INTERVAL = 3600  # Update webhook registration hourly
WEBHOOK_HEALTH_CHECK_INTERVAL = 60  # Health check interval in seconds

# =============================================================================
# WEBHOOK-FIRST ARCHITECTURE CONFIGURATION
# =============================================================================

# Enable webhook-first architecture (recommended)
WEBHOOK_FIRST_ARCHITECTURE = True

# Enable proactive portfolio monitoring
PROACTIVE_PORTFOLIO_MONITORING = False

# Portfolio monitoring interval (seconds)
PORTFOLIO_MONITORING_INTERVAL = 300  # 5 minutes

# Enable hybrid mode (webhook + proactive monitoring)
HYBRID_MODE_ENABLED = True

# =============================================================================
# AGENT EXECUTION MODES
# =============================================================================

# Risk Agent execution mode
RISK_AGENT_EXECUTION_MODE = "webhook_only"  # Options: "webhook_only", "hybrid", "local_only"

# Harvesting Agent execution mode  
HARVESTING_AGENT_EXECUTION_MODE = "webhook_only"  # Options: "webhook_only", "hybrid", "local_only"

# CopyBot Agent execution mode (always webhook-driven)
COPYBOT_AGENT_EXECUTION_MODE = "webhook_only"  # Always webhook-driven

# =============================================================================
# MONITORING MODE CONFIGURATION
# =============================================================================

# Enable monitoring-only mode for main app agents
MAIN_APP_MONITORING_ONLY = True

# Enable full execution mode for webhook server agents
WEBHOOK_SERVER_FULL_EXECUTION = True

# =============================================================================
# PORTFOLIO MONITORING THRESHOLDS
# =============================================================================

# Rebalancing deviation threshold (percentage)
REBALANCING_DEVIATION_THRESHOLD = 5.0  # 5%

# Note: Using existing allocation targets from above:
# SOL_TARGET_PERCENT = 0.10 (10%)
# USDC_TARGET_PERCENT = 0.20 (20%)
# Remaining 70% for positions

# =============================================================================
# RISK MANAGEMENT CONFIGURATION
# =============================================================================

# Enable AI analysis for risk decisions (using your existing comprehensive system)
RISK_MAX_LOSS_AI_ANALYSIS = True
RISK_DRAWDOWN_AI_ANALYSIS = True
RISK_EMERGENCY_STOP_AI_ANALYSIS = True  # Added missing flag
RISK_POSITION_SIZE_AI_ANALYSIS = True
RISK_CONSECUTIVE_LOSSES_AI_ANALYSIS = True  # Added missing flag

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
# QUICKNODE_RPC_ENDPOINT and QUICKNODE_WSS_ENDPOINT are already defined above
QUICKNODE_TOKEN_METRICS_API = os.getenv('QUICKNODE_TOKEN_METRICS_API', 'true').lower() == 'true'

# Price Source Mode Configuration - CONSOLIDATED ABOVE
# Options: 'jupiter' (Jupiter -> Birdeye -> Pump.fun) or 'birdeye' (Birdeye -> Jupiter -> Pump.fun)
# Birdeye is configured as primary source above for paid subscription

# =============================================================================
# 🏦 DeFi AUTOMATION CONFIGURATION
# =============================================================================

# DeFi Allocation Limits
DEFI_MAX_ALLOCATION_PERCENT = 30.0  # Maximum 30% of portfolio can be allocated to DeFi
DEFI_MIN_ALLOCATION_PERCENT = 5.0   # Minimum 5% allocation to start DeFi operations
DEFI_EMERGENCY_RESERVE_PERCENT = 10.0  # Keep 10% in emergency reserve

# Risk Agent Configuration
RISK_HALT_RESTART_REDUCTION_PERCENT = 0.25  # 25% reduction to restart buying
RISK_WALLET_UPDATE_REDUCTION_PERCENT = 0.20  # 20% reduction to restart after wallet update
RISK_CLOUD_DB_WHALE_TABLE = "whale_data"
RISK_CLOUD_DB_SENTIMENT_TABLE = "sentiment_data"
RISK_CLOUD_DB_CHART_TABLE = "chart_analysis"

# DeFi Risk Management
DEFI_MAX_SINGLE_PROTOCOL_ALLOCATION = 15.0  # Max 15% in any single protocol
DEFI_MAX_SINGLE_ASSET_ALLOCATION = 20.0     # Max 20% in any single asset
DEFI_MIN_COLLATERAL_RATIO = 1.5             # Minimum 150% collateral ratio for borrowing
DEFI_MAX_BORROWING_RATIO = 0.25             # Maximum 25% borrowing ratio

# DeFi Execution Settings
DEFI_EXECUTION_TIMEOUT_SECONDS = 300        # 5 minutes for DeFi operations
DEFI_RETRY_ATTEMPTS = 3                     # Number of retry attempts for failed operations
DEFI_SLIPPAGE_TOLERANCE = 200               # 2% slippage tolerance for DeFi swaps

# DeFi Protocol Preferences
DEFI_PREFERRED_PROTOCOLS = ['solend', 'mango', 'tulip']  # Priority order for protocols
DEFI_BLACKLISTED_PROTOCOLS = []             # Protocols to avoid
DEFI_MIN_APY_THRESHOLD = 5.0               # Minimum APY to consider lending

# DeFi Market Sentiment Integration
DEFI_SENTIMENT_WEIGHT = 0.3                 # Weight of market sentiment in decisions (0-1)
DEFI_BULLISH_AGGRESSION_MULTIPLIER = 1.2   # Increase allocation by 20% in bullish markets
DEFI_BEARISH_CAUTION_MULTIPLIER = 0.8      # Decrease allocation by 20% in bearish markets

# DeFi Monitoring and Alerts
DEFI_MONITORING_INTERVAL_SECONDS = 60       # Check DeFi positions every minute
DEFI_ALERT_THRESHOLD_PERCENT = 5.0          # Alert on 5% portfolio value changes
DEFI_LIQUIDATION_WARNING_THRESHOLD = 1.8    # Warn when collateral ratio drops below 180%

# Run validation on import
_validate_configuration()

# Debug API key loading if in debug mode
if BIRDEYE_API_DEBUG:
    debug_birdeye_api_key()


