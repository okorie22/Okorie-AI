#!/usr/bin/env python3
"""
Webhook Address Sync Script
Automatically syncs Helius webhook addresses with WALLETS_TO_TRACK configuration.

Usage:
    python src/scripts/sync_webhook_addresses.py

This script will:
1. Read WALLETS_TO_TRACK from src/config.py
2. Add your personal wallet (DEFAULT_WALLET_ADDRESS) if not present
3. Update your Helius webhook with the combined address list
4. Show you what addresses were added/removed

Features:
- Never removes your personal wallet
- Automatically adds new wallets from WALLETS_TO_TRACK
- Removes old wallets not in WALLETS_TO_TRACK
- Shows detailed sync information
"""

import os
import sys
import json
import requests
from typing import Set, List, Optional
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from {env_path}")
    else:
        print(f"⚠️ No .env file found at {env_path}")
except ImportError:
    print("⚠️ python-dotenv not installed, trying to load .env manually")
    # Manual .env loading
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        print(f"✅ Loaded environment variables from {env_path}")

def get_personal_wallet_address() -> Optional[str]:
    """Get personal wallet address from webhook config"""
    try:
        from src.scripts.webhooks.webhook_config import get_personal_wallet_address as config_get_personal_wallet
        return config_get_personal_wallet()
    except ImportError:
        # Fallback to environment variable
        return os.environ.get('DEFAULT_WALLET_ADDRESS')

def get_config_wallets() -> Set[str]:
    """Get WALLETS_TO_TRACK from config"""
    try:
        from src.scripts.webhooks.webhook_config import WALLETS_TO_TRACK
        return set(WALLETS_TO_TRACK)
    except ImportError as e:
        print(f"❌ Error importing WALLETS_TO_TRACK from config: {e}")
        return set()

def get_helius_api_key() -> Optional[str]:
    """Get Helius API key from webhook config"""
    try:
        from src.scripts.webhooks.webhook_config import HELIUS_API_KEY
        return HELIUS_API_KEY if HELIUS_API_KEY else None
    except ImportError:
        # Fallback to environment variable
        return os.environ.get('HELIUS_API_KEY')

def get_webhook_url() -> str:
    """Get webhook URL"""
    return "https://helius-webhook-handler.onrender.com/webhook"

def get_current_webhook_addresses(api_key: str) -> Optional[Set[str]]:
    """Get current webhook addresses from Helius"""
    try:
        list_url = "https://api.helius.xyz/v0/webhooks"
        list_response = requests.get(
            f"{list_url}?api-key={api_key}",
            timeout=10
        )
        
        if list_response.status_code == 200:
            existing_webhooks = list_response.json()
            print(f"📋 Found {len(existing_webhooks)} existing webhooks")
            
            webhook_url = get_webhook_url()
            for webhook in existing_webhooks:
                if webhook.get('webhookURL') == webhook_url:
                    webhook_id = webhook.get('webhookID')
                    current_addresses = set(webhook.get('accountAddresses', []))
                    print(f"🔍 Found webhook {webhook_id} with {len(current_addresses)} addresses")
                    return current_addresses
            
            print("⚠️ Could not find our webhook in Helius")
            return None
        else:
            print(f"❌ Failed to list webhooks: {list_response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting current webhook addresses: {e}")
        return None

def update_webhook_addresses(api_key: str, new_addresses: List[str]) -> bool:
    """Update webhook with new address list"""
    try:
        # Get webhook ID
        list_url = "https://api.helius.xyz/v0/webhooks"
        list_response = requests.get(
            f"{list_url}?api-key={api_key}",
            timeout=10
        )
        
        if list_response.status_code != 200:
            print(f"❌ Failed to list webhooks: {list_response.status_code}")
            return False
        
        existing_webhooks = list_response.json()
        webhook_id = None
        webhook_url = get_webhook_url()
        
        for webhook in existing_webhooks:
            if webhook.get('webhookURL') == webhook_url:
                webhook_id = webhook.get('webhookID')
                break
        
        if not webhook_id:
            print("❌ Could not find webhook ID")
            return False
        
        # Update webhook
        update_url = f"https://api.helius.xyz/v0/webhooks/{webhook_id}"
        update_data = {
            "webhookURL": webhook_url,
            "accountAddresses": new_addresses,
            "transactionTypes": ["ANY"],
            "webhookType": "raw",
            "authHeader": None
        }
        
        print(f"🔄 Updating webhook {webhook_id} with {len(new_addresses)} addresses...")
        update_response = requests.put(
            f"{update_url}?api-key={api_key}",
            json=update_data,
            timeout=10
        )
        
        print(f"Update response status: {update_response.status_code}")
        if update_response.status_code == 200:
            print("✅ Webhook successfully updated")
            return True
        else:
            print(f"❌ Failed to update webhook: {update_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating webhook addresses: {e}")
        return False

def sync_webhook_addresses():
    """Main sync function"""
    print("🔄 Starting webhook address sync...")
    print("=" * 50)
    
    # Check prerequisites
    api_key = get_helius_api_key()
    if not api_key:
        print("❌ HELIUS_API_KEY not found")
        print("Please set your Helius API key in one of these ways:")
        print("1. Environment variable: export HELIUS_API_KEY=your_api_key_here")
        print("2. Or check your webhook configuration in src/scripts/webhook_config.py")
        return False
    
    personal_wallet = get_personal_wallet_address()
    if not personal_wallet:
        print("❌ DEFAULT_WALLET_ADDRESS not found")
        print("Please set your personal wallet address in one of these ways:")
        print("1. Environment variable: export DEFAULT_WALLET_ADDRESS=your_wallet_address_here")
        print("2. Or check your webhook configuration in src/scripts/webhook_config.py")
        return False
    
    # Get addresses from config
    config_wallets = get_config_wallets()
    if not config_wallets:
        print("⚠️ No wallets found in WALLETS_TO_TRACK config")
    
    # Create final address list
    final_addresses = {personal_wallet}  # Always include personal wallet
    final_addresses.update(config_wallets)  # Add config wallets
    
    print(f"📊 Address Configuration:")
    print(f"  Personal Wallet: {personal_wallet[:8]}...")
    print(f"  Config Wallets: {len(config_wallets)} addresses")
    for wallet in config_wallets:
        print(f"    {wallet[:8]}...")
    print(f"  Total Addresses: {len(final_addresses)}")
    print()
    
    # Get current webhook addresses
    current_addresses = get_current_webhook_addresses(api_key)
    if current_addresses is None:
        print("❌ Could not get current webhook addresses")
        return False
    
    print(f"🔍 Current webhook addresses ({len(current_addresses)} addresses):")
    for addr in sorted(current_addresses):
        print(f"  {addr[:8]}...")
    print()
    
    # Check if sync is needed
    if current_addresses == final_addresses:
        print("✅ Webhook addresses are already in sync - no update needed")
        return True
    
    # Calculate changes
    addresses_to_add = final_addresses - current_addresses
    addresses_to_remove = current_addresses - final_addresses
    
    print("📋 Changes Required:")
    if addresses_to_add:
        print(f"➕ Addresses to add ({len(addresses_to_add)}):")
        for addr in sorted(addresses_to_add):
            print(f"    {addr[:8]}...")
    else:
        print("➕ No addresses to add")
    
    if addresses_to_remove:
        print(f"➖ Addresses to remove ({len(addresses_to_remove)}):")
        for addr in sorted(addresses_to_remove):
            print(f"    {addr[:8]}...")
    else:
        print("➖ No addresses to remove")
    print()
    
    # Confirm update
    print("🔄 Proceeding with webhook update...")
    
    # Update webhook
    success = update_webhook_addresses(api_key, list(final_addresses))
    if success:
        print("✅ Webhook addresses successfully synced!")
        print(f"📊 Final webhook configuration: {len(final_addresses)} addresses")
        return True
    else:
        print("❌ Failed to sync webhook addresses")
        return False

def main():
    """Main entry point"""
    print("🌐 Helius Webhook Address Sync Tool")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        success = sync_webhook_addresses()
        if success:
            print("\n🎉 Sync completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Sync failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Sync cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
