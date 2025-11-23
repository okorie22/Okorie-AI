# ITORO Commerce Layer Configuration Example
# Copy this file to config.py and customize for your environment

import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# =============================================================================
# 🌐 CLOUD DATABASE CONFIGURATION
# =============================================================================

# Choose your cloud database provider: 'supabase', 'firebase', 'mongodb', 'aws_s3'
CLOUD_DATABASE_TYPE = os.getenv('CLOUD_DATABASE_TYPE', 'supabase')

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://your-project.supabase.co')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', 'your-supabase-anon-key')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE', 'your-supabase-service-role-key')

# Firebase Configuration (if using Firebase)
FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', 'your-firebase-project-id')
FIREBASE_PRIVATE_KEY = os.getenv('FIREBASE_PRIVATE_KEY', "-----BEGIN PRIVATE KEY-----\nyour-private-key\n-----END PRIVATE KEY-----\n")
FIREBASE_CLIENT_EMAIL = os.getenv('FIREBASE_CLIENT_EMAIL', 'firebase-adminsdk@your-project.iam.gserviceaccount.com')

# MongoDB Atlas Configuration (if using MongoDB)
MONGODB_CONNECTION_STRING = os.getenv('MONGODB_CONNECTION_STRING', 'mongodb+srv://username:password@cluster.mongodb.net/')
MONGODB_DATABASE_NAME = os.getenv('MONGODB_DATABASE_NAME', 'itoro_commerce')

# AWS S3 Configuration (if using AWS S3)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'your-aws-access-key-id')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'your-aws-secret-access-key')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET', 'itoro-commerce-data')

# =============================================================================
# 💰 PAYMENT PROCESSOR CONFIGURATION
# =============================================================================

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_your-stripe-publishable-key')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', 'sk_test_your-stripe-secret-key')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_your-webhook-secret')

# Solana Pay Configuration
SOLANA_PAY_WALLET_PRIVATE_KEY = os.getenv('SOLANA_PRIVATE_KEY', 'your-solana-private-key')
SOLANA_PAY_WALLET_PUBLIC_KEY = os.getenv('SOLANA_PAY_WALLET_PUBLIC_KEY', 'your-solana-public-key')
SOLANA_NETWORK = os.getenv('SOLANA_NETWORK', 'mainnet-beta')

# Payment Settings
PAYMENT_CURRENCY = os.getenv('PAYMENT_CURRENCY', 'USD')
MINIMUM_PURCHASE_AMOUNT = float(os.getenv('MINIMUM_PURCHASE_AMOUNT', '5.00'))

# =============================================================================
# 📡 EXTERNAL API CONFIGURATION
# =============================================================================

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_API', 'your-telegram-bot-token')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHAT_ID', '@your_channel_or_chat_id')
TELEGRAM_ADMIN_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'your-admin-chat-id')

def _parse_json_env(value: str, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default

TELEGRAM_CHANNEL_MAP = _parse_json_env(os.getenv('TELEGRAM_CHANNEL_MAP'), {})
GMGN_ECOSYSTEMS = [
    item.strip()
    for item in os.getenv('GMGN_ECOSYSTEMS', '').split(',')
    if item and item.strip()
]
SIGNAL_TRIGGER_MODE = os.getenv('SIGNAL_TRIGGER_MODE', 'true').lower() == 'true'
SIGNAL_WEBHOOK_SECRET = os.getenv('SIGNAL_WEBHOOK_SECRET')
SIGNAL_WEBHOOK_ALLOWED_IPS = _parse_json_env(os.getenv('SIGNAL_WEBHOOK_ALLOWED_IPS'), [])

# GMGN API Configuration
GMGN_API_KEY = os.getenv('GMGN_API_KEY', 'your-gmgn-api-key')
GMGN_BASE_URL = os.getenv('GMGN_BASE_URL', 'https://api.gmgn.ai')

# Ocean Protocol Configuration
OCEAN_MARKET_URL = os.getenv('OCEAN_MARKET_URL', 'https://market.oceanprotocol.com')
OCEAN_NETWORK = os.getenv('OCEAN_NETWORK', 'polygon')

# Dune Analytics Configuration
DUNE_API_KEY = os.getenv('DUNE_API_KEY', 'your-dune-api-key')
DUNE_USERNAME = os.getenv('DUNE_USERNAME', 'your-dune-username')

# RapidAPI Configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', 'your-rapidapi-key')

# =============================================================================
# 🔐 SECURITY & ENCRYPTION
# =============================================================================

# API Security
API_KEY_LENGTH = int(os.getenv('API_KEY_LENGTH', '32'))
API_KEY_EXPIRY_DAYS = int(os.getenv('API_KEY_EXPIRY_DAYS', '365'))

# Encryption Key (32 bytes for AES-256)
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'your-32-byte-encryption-key-here')

# JWT Secret for API authentication
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-jwt-secret-key-here')

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_HOUR = int(os.getenv('RATE_LIMIT_REQUESTS_PER_HOUR', '1000'))
RATE_LIMIT_REQUESTS_PER_DAY = int(os.getenv('RATE_LIMIT_REQUESTS_PER_DAY', '10000'))

# =============================================================================
# 📊 SYSTEM CONFIGURATION
# =============================================================================

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
LOG_DIRECTORY = os.path.join('logs')
LOG_MAX_SIZE_MB = int(os.getenv('LOG_MAX_SIZE_MB', '10'))
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))
SHOW_DEBUG_IN_CONSOLE = os.getenv('SHOW_DEBUG_IN_CONSOLE', 'false').lower() == 'true'

# Agent Update Intervals (seconds)
SIGNAL_SERVICE_UPDATE_INTERVAL = int(os.getenv('SIGNAL_SERVICE_UPDATE_INTERVAL', '300'))
DATA_SERVICE_UPDATE_INTERVAL = int(os.getenv('DATA_SERVICE_UPDATE_INTERVAL', '3600'))
WHALE_RANKING_UPDATE_INTERVAL = int(os.getenv('WHALE_RANKING_UPDATE_INTERVAL', '1800'))
STRATEGY_METADATA_UPDATE_INTERVAL = int(os.getenv('STRATEGY_METADATA_UPDATE_INTERVAL', '3600'))

# Data Retention (days)
SIGNAL_HISTORY_RETENTION_DAYS = int(os.getenv('SIGNAL_HISTORY_RETENTION_DAYS', '30'))
WHALE_RANKING_RETENTION_DAYS = int(os.getenv('WHALE_RANKING_RETENTION_DAYS', '90'))
STRATEGY_METADATA_RETENTION_DAYS = int(os.getenv('STRATEGY_METADATA_RETENTION_DAYS', '365'))

# Data Limits
MAX_SIGNAL_RECORDS = int(os.getenv('MAX_SIGNAL_RECORDS', '10000'))
MAX_WHALE_RECORDS = int(os.getenv('MAX_WHALE_RECORDS', '1000'))
MAX_STRATEGY_RECORDS = int(os.getenv('MAX_STRATEGY_RECORDS', '5000'))

# Aggregation Settings
AGGREGATION_TIMEZONE = os.getenv('AGGREGATION_TIMEZONE', 'UTC')
AGGREGATION_BATCH_SIZE = int(os.getenv('AGGREGATION_BATCH_SIZE', '100'))

# Performance Calculation
PERFORMANCE_CALCULATION_METHOD = os.getenv('PERFORMANCE_CALCULATION_METHOD', 'time_weighted')
RISK_FREE_RATE = float(os.getenv('RISK_FREE_RATE', '0.02'))

# Signal Quality Thresholds
MIN_SIGNAL_CONFIDENCE = float(os.getenv('MIN_SIGNAL_CONFIDENCE', '0.6'))
MIN_WHALE_SCORE = float(os.getenv('MIN_WHALE_SCORE', '0.1'))

# =============================================================================
# 🧪 DEVELOPMENT SETTINGS
# =============================================================================

# Debug Mode
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

# Test Mode (use paper trading data)
TEST_MODE = os.getenv('TEST_MODE', 'true').lower() == 'true'
USE_MOCK_DATA = os.getenv('USE_MOCK_DATA', 'false').lower() == 'true'

# Development Database (optional - overrides cloud settings)
DEV_DATABASE_PATH = os.getenv('DEV_DATABASE_PATH', 'dev_data/commerce_dev.db')

# =============================================================================
# 🔧 FEATURE FLAGS
# =============================================================================

# Enable/disable individual agents
ENABLE_SIGNAL_SERVICE = os.getenv('ENABLE_SIGNAL_SERVICE', 'true').lower() == 'true'
ENABLE_DATA_SERVICE = os.getenv('ENABLE_DATA_SERVICE', 'true').lower() == 'true'
ENABLE_WHALE_RANKING = os.getenv('ENABLE_WHALE_RANKING', 'true').lower() == 'true'
ENABLE_STRATEGY_METADATA = os.getenv('ENABLE_STRATEGY_METADATA', 'true').lower() == 'true'
ENABLE_MERCHANT_SERVICES = os.getenv('ENABLE_MERCHANT_SERVICES', 'true').lower() == 'true'

# =============================================================================
# 📊 MONITORING & ANALYTICS
# =============================================================================

# Prometheus Metrics
ENABLE_PROMETHEUS_METRICS = os.getenv('ENABLE_PROMETHEUS_METRICS', 'false').lower() == 'true'
PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', '9090'))

# Health Checks
ENABLE_HEALTH_CHECKS = os.getenv('ENABLE_HEALTH_CHECKS', 'true').lower() == 'true'

# =============================================================================
# 💾 BACKUP CONFIGURATION
# =============================================================================

# Auto Backup Settings
ENABLE_AUTO_BACKUP = os.getenv('ENABLE_AUTO_BACKUP', 'true').lower() == 'true'
BACKUP_INTERVAL_HOURS = int(os.getenv('BACKUP_INTERVAL_HOURS', '24'))
BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
BACKUP_STORAGE_PATH = os.getenv('BACKUP_STORAGE_PATH', 'backups/')

# =============================================================================
# 🌐 SERVER CONFIGURATION
# =============================================================================

# Web Server Settings
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))
WORKERS = int(os.getenv('WORKERS', '4'))

# CORS Settings
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '["http://localhost:3000"]').split(',')
CORS_ALLOW_CREDENTIALS = os.getenv('CORS_ALLOW_CREDENTIALS', 'true').lower() == 'true'

# SSL Configuration
SSL_CERT_PATH = os.getenv('SSL_CERT_PATH', '/path/to/ssl/cert.pem')
SSL_KEY_PATH = os.getenv('SSL_KEY_PATH', '/path/to/ssl/private.key')
ENABLE_HTTPS = os.getenv('ENABLE_HTTPS', 'false').lower() == 'true'

# Health Check
HEALTH_CHECK_PATH = os.getenv('HEALTH_CHECK_PATH', '/health')
HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', '30'))

# =============================================================================
# 📧 NOTIFICATION SETTINGS
# =============================================================================

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'your-email@gmail.com')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'your-app-password')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@itoro.com')

# Webhook URLs
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/your-webhook-id/your-webhook-token')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', 'https://hooks.slack.com/services/your-slack-webhook')

# =============================================================================
# 🔧 ADVANCED CONFIGURATION
# =============================================================================

# Redis Configuration (for caching)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
REDIS_CACHE_TTL = int(os.getenv('REDIS_CACHE_TTL', '3600'))

# Database Connection Pool
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '20'))
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))

# Custom API Settings
CUSTOM_API_BASE_URL = os.getenv('CUSTOM_API_BASE_URL', 'https://api.your-domain.com')
CUSTOM_API_VERSION = os.getenv('CUSTOM_API_VERSION', 'v1')

# =============================================================================
# 🎯 VALIDATION FUNCTIONS
# =============================================================================

def validate_config() -> list:
    """
    Validate configuration settings and return list of missing required configs.

    Returns:
        List of missing configuration keys
    """
    missing_configs = []

    # Required cloud database configs
    if CLOUD_DATABASE_TYPE == 'supabase':
        if not SUPABASE_URL or SUPABASE_URL == 'https://your-project.supabase.co':
            missing_configs.append('SUPABASE_URL')
        if not SUPABASE_ANON_KEY or SUPABASE_ANON_KEY == 'your-supabase-anon-key':
            missing_configs.append('SUPABASE_ANON_KEY')
    elif CLOUD_DATABASE_TYPE == 'firebase':
        if not FIREBASE_PROJECT_ID or FIREBASE_PROJECT_ID == 'your-firebase-project-id':
            missing_configs.append('FIREBASE_PROJECT_ID')
        if not FIREBASE_PRIVATE_KEY or 'your-private-key' in FIREBASE_PRIVATE_KEY:
            missing_configs.append('FIREBASE_PRIVATE_KEY')
    elif CLOUD_DATABASE_TYPE == 'mongodb':
        if not MONGODB_CONNECTION_STRING or 'username:password' in MONGODB_CONNECTION_STRING:
            missing_configs.append('MONGODB_CONNECTION_STRING')
    elif CLOUD_DATABASE_TYPE == 'aws_s3':
        if not AWS_ACCESS_KEY_ID or AWS_ACCESS_KEY_ID == 'your-aws-access-key-id':
            missing_configs.append('AWS_ACCESS_KEY_ID')
        if not AWS_SECRET_ACCESS_KEY or AWS_SECRET_ACCESS_KEY == 'your-aws-secret-access-key':
            missing_configs.append('AWS_SECRET_ACCESS_KEY')
        if not AWS_S3_BUCKET or AWS_S3_BUCKET == 'itoro-commerce-data':
            missing_configs.append('AWS_S3_BUCKET')

    # Required payment configs (at least one payment method for production)
    payment_methods = []
    if STRIPE_SECRET_KEY and STRIPE_SECRET_KEY != 'sk_test_your-stripe-secret-key':
        payment_methods.append('stripe')
    if SOLANA_PAY_WALLET_PRIVATE_KEY and SOLANA_PAY_WALLET_PRIVATE_KEY != 'your-solana-private-key':
        payment_methods.append('solana_pay')

    if not TEST_MODE and not payment_methods:
        missing_configs.append('PAYMENT_METHOD (Stripe or SolanaPay)')

    # Required API keys for services
    if ENABLE_SIGNAL_SERVICE and (not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'your-telegram-bot-token'):
        missing_configs.append('TELEGRAM_BOT_TOKEN (required for SignalServiceAgent)')

    return missing_configs

def get_cloud_config() -> dict:
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
    if TEST_MODE:
        print("Running in TEST_MODE - some features may be limited.")


# Commerce Agent Settings
SIGNAL_SERVICE_UPDATE_INTERVAL=300
DATA_SERVICE_UPDATE_INTERVAL=3600
WHALE_RANKING_UPDATE_INTERVAL=1800