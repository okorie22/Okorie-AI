"""
💰 ITORO Commerce Layer Configuration
Built for monetizing trading intelligence and data streams

This configuration manages all commerce agents, cloud storage, and revenue systems.
All settings are environment-variable driven for security and flexibility.
"""

import os
import json
from dotenv import load_dotenv
from typing import Dict, List, Any

# Load environment variables
load_dotenv()

# =============================================================================
# 🌐 CLOUD DATABASE CONFIGURATION
# =============================================================================

# Supported cloud databases: 'supabase', 'firebase', 'mongodb', 'aws_s3'
CLOUD_DATABASE_TYPE = os.getenv('CLOUD_DATABASE_TYPE', 'supabase')

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Firebase Configuration
FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID')
FIREBASE_PRIVATE_KEY = os.getenv('FIREBASE_PRIVATE_KEY')
FIREBASE_CLIENT_EMAIL = os.getenv('FIREBASE_CLIENT_EMAIL')

# MongoDB Atlas Configuration
MONGODB_CONNECTION_STRING = os.getenv('MONGODB_CONNECTION_STRING')
MONGODB_DATABASE_NAME = os.getenv('MONGODB_DATABASE_NAME', 'itoro_commerce')

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET', 'itoro-commerce-data')

# =============================================================================
# 🤖 COMMERCE AGENT CONFIGURATION
# =============================================================================

# Agent update intervals (in seconds)
SIGNAL_SERVICE_UPDATE_INTERVAL = int(os.getenv('SIGNAL_SERVICE_UPDATE_INTERVAL', '300'))  # 5 minutes
DATA_SERVICE_UPDATE_INTERVAL = int(os.getenv('DATA_SERVICE_UPDATE_INTERVAL', '3600'))  # 1 hour
WHALE_RANKING_UPDATE_INTERVAL = int(os.getenv('WHALE_RANKING_UPDATE_INTERVAL', '3600'))  # 1 hour
STRATEGY_METADATA_UPDATE_INTERVAL = int(os.getenv('STRATEGY_METADATA_UPDATE_INTERVAL', '3600'))  # 1 hour

# Data retention settings (in days)
SIGNAL_HISTORY_RETENTION_DAYS = int(os.getenv('SIGNAL_HISTORY_RETENTION_DAYS', '30'))
WHALE_RANKING_RETENTION_DAYS = int(os.getenv('WHALE_RANKING_RETENTION_DAYS', '90'))
STRATEGY_METADATA_RETENTION_DAYS = int(os.getenv('STRATEGY_METADATA_RETENTION_DAYS', '365'))

# Whale ranking weekly schedule
WHALE_RANKING_WEEKLY_SCHEDULE = {
    'day': 6,  # Sunday (0=Monday, 6=Sunday)
    'hour': 10,
    'enabled': True
}

# Maximum records per dataset
MAX_SIGNAL_RECORDS = int(os.getenv('MAX_SIGNAL_RECORDS', '10000'))
MAX_WHALE_RECORDS = int(os.getenv('MAX_WHALE_RECORDS', '1000'))
MAX_STRATEGY_RECORDS = int(os.getenv('MAX_STRATEGY_RECORDS', '5000'))

# =============================================================================
# 💰 REVENUE & PAYMENT CONFIGURATION
# =============================================================================

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# SolanaPay Configuration
SOLANA_PAY_WALLET_PRIVATE_KEY = os.getenv('SOLANA_PAY_WALLET_PRIVATE_KEY')
SOLANA_PAY_WALLET_PUBLIC_KEY = os.getenv('SOLANA_PAY_WALLET_PUBLIC_KEY')
SOLANA_NETWORK = os.getenv('SOLANA_NETWORK', 'mainnet-beta')  # or 'devnet'

# Payment processing settings
PAYMENT_CURRENCY = os.getenv('PAYMENT_CURRENCY', 'USD')
MINIMUM_PURCHASE_AMOUNT = float(os.getenv('MINIMUM_PURCHASE_AMOUNT', '5.00'))

# =============================================================================
# 📡 API & EXTERNAL SERVICE CONFIGURATION
# =============================================================================

# Telegram Bot Configuration
def _parse_json_env(value: str, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_API')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_ADMIN_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_CHANNEL_MAP = _parse_json_env(os.getenv('TELEGRAM_CHANNEL_MAP'), {})
TELEGRAM_CONTENT_ENABLED = True
TELEGRAM_CONTENT_SCHEDULES = ['09:00', '14:00', '19:00']
TELEGRAM_CONTENT_TOPICS = ["market_analysis", "trading_tips", "forex_signals", "gmgn_promos", "educational"]
TELEGRAM_CONTENT_ROTATION = 'random'
TELEGRAM_CONTENT_MAX_RETRIES = 2
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_KEY')  # Keep as env var since it's a secret
GMGN_PROMO_LINK = 'https://gmgn.ai/sol/address/FC3NLfsATTEvPYizxjrYjijyo71ktwG6KwEbgF9ehnAd'
FOREX_COMMUNITY_LINK = 'https://t.me/+5r26a1NP_vRiNjAx'

# Signal ingestion configuration
SIGNAL_TRIGGER_MODE = os.getenv('SIGNAL_TRIGGER_MODE', 'true').lower() == 'true'
SIGNAL_WEBHOOK_SECRET = os.getenv('SIGNAL_WEBHOOK_SECRET')
SIGNAL_WEBHOOK_ALLOWED_IPS = _parse_json_env(os.getenv('SIGNAL_WEBHOOK_ALLOWED_IPS'), [])
GMGN_ECOSYSTEMS = [
    item.strip()
    for item in os.getenv('GMGN_ECOSYSTEMS', '').split(',')
    if item and item.strip()
]

# GMGN API Configuration
GMGN_API_KEY = os.getenv('GMGN_API_KEY')
GMGN_BASE_URL = os.getenv('GMGN_BASE_URL', 'https://api.gmgn.ai')

# Ocean Protocol Configuration
OCEAN_MARKET_URL = os.getenv('OCEAN_MARKET_URL', 'https://market.oceanprotocol.com')
OCEAN_NETWORK = os.getenv('OCEAN_NETWORK', 'polygon')  # ethereum, polygon, bsc

# Dune Analytics Configuration
DUNE_API_KEY = os.getenv('DUNE_API_KEY')
DUNE_USERNAME = os.getenv('DUNE_USERNAME')

# RapidAPI Configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')

# =============================================================================
# 🔐 SECURITY & AUTHENTICATION
# =============================================================================

# API Key settings
API_KEY_LENGTH = int(os.getenv('API_KEY_LENGTH', '32'))
API_KEY_EXPIRY_DAYS = int(os.getenv('API_KEY_EXPIRY_DAYS', '365'))

# Rate limiting
RATE_LIMIT_REQUESTS_PER_HOUR = int(os.getenv('RATE_LIMIT_REQUESTS_PER_HOUR', '1000'))
RATE_LIMIT_REQUESTS_PER_DAY = int(os.getenv('RATE_LIMIT_REQUESTS_PER_DAY', '10000'))

# Encryption settings
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')  # 32-byte key for AES-256
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

# =============================================================================
# 📊 DATA PROCESSING CONFIGURATION
# =============================================================================

# Data aggregation settings
AGGREGATION_TIMEZONE = os.getenv('AGGREGATION_TIMEZONE', 'UTC')
AGGREGATION_BATCH_SIZE = int(os.getenv('AGGREGATION_BATCH_SIZE', '100'))

# Performance calculation settings
PERFORMANCE_CALCULATION_METHOD = os.getenv('PERFORMANCE_CALCULATION_METHOD', 'time_weighted')  # simple, time_weighted
RISK_FREE_RATE = float(os.getenv('RISK_FREE_RATE', '0.02'))  # 2% annual risk-free rate

# Data quality thresholds
MIN_SIGNAL_CONFIDENCE = float(os.getenv('MIN_SIGNAL_CONFIDENCE', '0.6'))
MIN_WHALE_SCORE = float(os.getenv('MIN_WHALE_SCORE', '0.1'))

# =============================================================================
# 🔧 SYSTEM CONFIGURATION
# =============================================================================

# Logging settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
LOG_DIRECTORY = os.path.join('logs')
LOG_FILENAME = 'commerce_system.log'
LOG_MAX_SIZE_MB = int(os.getenv('LOG_MAX_SIZE_MB', '10'))
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))

# Debug settings
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
SHOW_DEBUG_IN_CONSOLE = os.getenv('SHOW_DEBUG_IN_CONSOLE', 'false').lower() == 'true'

# System paths
DATA_CACHE_DIR = os.path.join('data', 'cache')
EXPORT_DIR = os.path.join('data', 'exports')

# =============================================================================
# 📋 DATA SCHEMA DEFINITIONS
# =============================================================================

# Signal data schema
SIGNAL_SCHEMA = {
    'timestamp': 'datetime',
    'symbol': 'string',
    'action': 'string',  # 'BUY', 'SELL', 'HOLD'
    'confidence': 'float',
    'price': 'float',
    'volume': 'float',
    'source_agent': 'string',
    'metadata': 'json'
}

# Whale ranking schema
WHALE_RANKING_SCHEMA = {
    'address': 'string',
    'twitter_handle': 'string',
    'pnl_30d': 'float',
    'pnl_7d': 'float',
    'pnl_1d': 'float',
    'winrate_7d': 'float',
    'txs_30d': 'integer',
    'token_active': 'integer',
    'last_active': 'datetime',
    'is_blue_verified': 'boolean',
    'avg_holding_period_7d': 'float',
    'score': 'float',
    'rank': 'integer',
    'last_updated': 'datetime'
}

# Strategy metadata schema
STRATEGY_SCHEMA = {
    'strategy_id': 'string',
    'strategy_name': 'string',
    'agent_type': 'string',
    'performance_metrics': 'json',
    'risk_metrics': 'json',
    'last_updated': 'datetime',
    'is_active': 'boolean'
}

# =============================================================================
# 🏷️ PRICING TIERS
# =============================================================================

PRICING_TIERS = {
    'free': {
        'name': 'Free',
        'monthly_price': 0,
        'max_requests_per_day': 100,
        'max_signals_per_day': 10,
        'data_retention_days': 7,
        'support_level': 'community'
    },
    'basic': {
        'name': 'Basic',
        'monthly_price': 9.99,
        'max_requests_per_day': 1000,
        'max_signals_per_day': 100,
        'data_retention_days': 30,
        'support_level': 'email'
    },
    'pro': {
        'name': 'Pro',
        'monthly_price': 29.99,
        'max_requests_per_day': 10000,
        'max_signals_per_day': 1000,
        'data_retention_days': 90,
        'support_level': 'priority'
    },
    'enterprise': {
        'name': 'Enterprise',
        'monthly_price': 99.99,
        'max_requests_per_day': -1,  # unlimited
        'max_signals_per_day': -1,   # unlimited
        'data_retention_days': 365,
        'support_level': 'dedicated'
    }
}

# API pricing per request
API_PRICING = {
    'signal_realtime': 0.01,    # $0.01 per real-time signal
    'signal_historical': 0.005, # $0.005 per historical signal
    'whale_ranking': 0.02,      # $0.02 per ranking request
    'strategy_data': 0.03,      # $0.03 per strategy data request
    'bulk_export': 0.50         # $0.50 per bulk export
}

# =============================================================================
# 🎯 VALIDATION FUNCTIONS
# =============================================================================

def validate_config() -> List[str]:
    """
    Validate configuration settings and return list of missing required configs.

    Returns:
        List of missing configuration keys
    """
    missing_configs = []

    # Required cloud database configs
    if CLOUD_DATABASE_TYPE == 'supabase':
        if not SUPABASE_URL:
            missing_configs.append('SUPABASE_URL')
        if not SUPABASE_ANON_KEY:
            missing_configs.append('SUPABASE_ANON_KEY')
    elif CLOUD_DATABASE_TYPE == 'firebase':
        if not FIREBASE_PROJECT_ID:
            missing_configs.append('FIREBASE_PROJECT_ID')
        if not FIREBASE_PRIVATE_KEY:
            missing_configs.append('FIREBASE_PRIVATE_KEY')
    elif CLOUD_DATABASE_TYPE == 'mongodb':
        if not MONGODB_CONNECTION_STRING:
            missing_configs.append('MONGODB_CONNECTION_STRING')
    elif CLOUD_DATABASE_TYPE == 'aws_s3':
        if not AWS_ACCESS_KEY_ID:
            missing_configs.append('AWS_ACCESS_KEY_ID')
        if not AWS_SECRET_ACCESS_KEY:
            missing_configs.append('AWS_SECRET_ACCESS_KEY')
        if not AWS_S3_BUCKET:
            missing_configs.append('AWS_S3_BUCKET')

    # Required payment configs (at least one payment method)
    payment_methods = []
    if STRIPE_SECRET_KEY:
        payment_methods.append('stripe')
    if SOLANA_PAY_WALLET_PRIVATE_KEY:
        payment_methods.append('solana_pay')

    if not payment_methods:
        missing_configs.append('PAYMENT_METHOD (Stripe or SolanaPay)')

    # Required API keys for services
    if not TELEGRAM_BOT_TOKEN:
        missing_configs.append('TELEGRAM_BOT_TOKEN (for SignalServiceAgent)')

    return missing_configs

def get_cloud_config() -> Dict[str, Any]:
    """
    Get cloud database configuration based on selected type.

    Returns:
        Dictionary containing cloud database configuration
    """
    if CLOUD_DATABASE_TYPE == 'supabase':
        return {
            'type': 'supabase',
            'url': SUPABASE_URL,
            'anon_key': SUPABASE_ANON_KEY,
            'service_role_key': SUPABASE_SERVICE_ROLE_KEY
        }
    elif CLOUD_DATABASE_TYPE == 'firebase':
        return {
            'type': 'firebase',
            'project_id': FIREBASE_PROJECT_ID,
            'private_key': FIREBASE_PRIVATE_KEY,
            'client_email': FIREBASE_CLIENT_EMAIL
        }
    elif CLOUD_DATABASE_TYPE == 'mongodb':
        return {
            'type': 'mongodb',
            'connection_string': MONGODB_CONNECTION_STRING,
            'database_name': MONGODB_DATABASE_NAME
        }
    elif CLOUD_DATABASE_TYPE == 'aws_s3':
        return {
            'type': 'aws_s3',
            'access_key_id': AWS_ACCESS_KEY_ID,
            'secret_access_key': AWS_SECRET_ACCESS_KEY,
            'region': AWS_REGION,
            'bucket': AWS_S3_BUCKET
        }
    else:
        raise ValueError(f"Unsupported cloud database type: {CLOUD_DATABASE_TYPE}")

# Validate configuration on import
missing = validate_config()
if missing:
    print(f"WARNING: Missing required configuration: {', '.join(missing)}")
    print("Some commerce agents may not function properly without these settings.")
