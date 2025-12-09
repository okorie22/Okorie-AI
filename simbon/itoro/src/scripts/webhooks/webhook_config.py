"""
Configuration settings for Anarcho Capital Trading Desktop App
Contains settings for API keys, wallets to track, and other app settings
"""

import os
from typing import List, Dict, Any, Optional
import json

# Directory for data storage
DATA_DIR = "src/data"
os.makedirs(DATA_DIR, exist_ok=True)

# Cache database path
CACHE_DB_PATH = os.path.join(DATA_DIR, "token_cache.db")

# API Keys
JUPITER_API_KEY = os.environ.get("JUPITER_API_KEY", "")
BIRDEYE_API_KEY = os.environ.get("BIRDEYE_API_KEY", "")
HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY", "")
HELIUS_WEBHOOK_ID = os.environ.get("HELIUS_WEBHOOK_ID", "")

# Wallets to track - load from centralized config
WALLETS_TO_TRACK: List[str] = []

# Try to load wallets from config file (same as main system)
WALLET_CONFIG_PATH = os.path.join(DATA_DIR, "wallets.json")
try:
    if os.path.exists(WALLET_CONFIG_PATH):
        with open(WALLET_CONFIG_PATH, 'r') as f:
            wallet_data = json.load(f)
            WALLETS_TO_TRACK = wallet_data.get('wallets', [])
            print(f"Loaded {len(WALLETS_TO_TRACK)} tracked wallets from {WALLET_CONFIG_PATH}")
    else:
        print(f"Warning: Wallet config file not found at {WALLET_CONFIG_PATH}")
except Exception as e:
    print(f"Error loading wallet config: {e}")
    # Fallback to empty list
    WALLETS_TO_TRACK = []

# Personal wallet tracking removed - only track whale wallets

# Price service configuration
PRICE_CONFIG = {
    # API configuration
    "apis": {
        "jupiter": {
            "enabled": True,
            "base_url": "https://price.jup.ag/v4/price",
            "api_key": JUPITER_API_KEY,
            "timeout": 5,  # seconds
            "priority": 1  # Lower number = higher priority
        },
        "birdeye": {
            "enabled": True,
            "base_url": "https://public-api.birdeye.so/defi/price",
            "api_key": BIRDEYE_API_KEY,
            "timeout": 5,
            "priority": 2
        },
        "pumpfun": {
            "enabled": True,
            "base_url": "https://api.pumpfunapi.org/price",
            "timeout": 5,
            "priority": 3
        }
    },
    
    # Cache configuration
    "cache": {
        "default_ttl": 900,  # 15 minutes default TTL
        "stablecoin_ttl": 3600,  # 1 hour for stablecoins
        "sol_ttl": 1800,  # 30 minutes for SOL
        "vacuum_interval": 86400  # Run vacuum once per day
    },
    
    # Retry configuration
    "retry": {
        "max_retries": 3,
        "backoff_factor": 1.5,
        "max_backoff": 10
    }
}

# Webhook server configuration
WEBHOOK_CONFIG = {
    "host": "0.0.0.0",
    "port": int(os.environ.get("PORT", 5000)),
    "debug": False,
    "helius": {
        "enabled": True,
        "webhook_types": ["ANY"],  # Transaction types to track
        "enhanced_mode": True,     # Use enhanced transaction data
        "update_interval": 3600,   # Update webhook registration hourly
        "retry_attempts": 3        # Number of retries for webhook setup
    }
}

# Minimum token value to track (in USD)
MIN_TOKEN_VALUE = 0.1

# Known token addresses
KNOWN_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
}

# Add wallets to tracked list
def add_wallet(address: str, label: Optional[str] = None) -> bool:
    """Add a wallet to the tracked list and save to config"""
    global WALLETS_TO_TRACK
    
    # Validate address format (basic check for Solana address)
    if not isinstance(address, str) or len(address) != 44:
        print(f"Invalid wallet address format: {address}")
        return False
        
    # Check if wallet already in list
    if address in WALLETS_TO_TRACK:
        print(f"Wallet already being tracked: {address}")
        return False
        
    # Add to tracked list
    WALLETS_TO_TRACK.append(address)
    
    # Save to file
    wallet_data = {
        'wallets': WALLETS_TO_TRACK,
        'labels': {}  # Could store wallet labels here
    }
    
    if label:
        wallet_data['labels'][address] = label
        
    try:
        with open(WALLET_CONFIG_PATH, 'w') as f:
            json.dump(wallet_data, f, indent=2)
        print(f"Added wallet {address[:8]}... to tracking list")
        return True
    except Exception as e:
        print(f"Error saving wallet config: {e}")
        return False

# Get personal wallet address from environment
def get_personal_wallet_address() -> Optional[str]:
    """Get the personal wallet address from environment variables"""
    return os.environ.get("DEFAULT_WALLET_ADDRESS")

# Remove wallet from tracked list
def remove_wallet(address: str) -> bool:
    """Remove a wallet from the tracked list and update config"""
    global WALLETS_TO_TRACK
    
    if address not in WALLETS_TO_TRACK:
        print(f"Wallet not found in tracking list: {address}")
        return False
        
    # Remove from list
    WALLETS_TO_TRACK.remove(address)
    
    # Save to file
    try:
        wallet_data = {'wallets': WALLETS_TO_TRACK}
        
        # Preserve labels if they exist
        if os.path.exists(WALLET_CONFIG_PATH):
            with open(WALLET_CONFIG_PATH, 'r') as f:
                existing_data = json.load(f)
                if 'labels' in existing_data:
                    wallet_data['labels'] = existing_data['labels']
                    if address in wallet_data['labels']:
                        del wallet_data['labels'][address]
        
        with open(WALLET_CONFIG_PATH, 'w') as f:
            json.dump(wallet_data, f, indent=2)
        print(f"Removed wallet {address[:8]}... from tracking list")
        return True
    except Exception as e:
        print(f"Error saving wallet config: {e}")
        return False 