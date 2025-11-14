#!/usr/bin/env python3
"""
Simple script to add tracked wallets to Helius webhook
Automatically syncs with WALLETS_TO_TRACK from config
"""

import requests
import json
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Import config
from src import config

# Your tracked wallets from config
tracked_wallets = config.WALLETS_TO_TRACK

# Your personal wallet
personal_wallet = os.environ.get('DEFAULT_WALLET_ADDRESS', config.DEFAULT_WALLET_ADDRESS)

# All addresses to register
all_addresses = [personal_wallet] + tracked_wallets if personal_wallet else tracked_wallets

# Helius API details from environment or webhook config
try:
    from src.scripts.webhooks.webhook_config import HELIUS_API_KEY, HELIUS_WEBHOOK_ID
    api_key = HELIUS_API_KEY or os.environ.get('HELIUS_API_KEY')
    webhook_id = HELIUS_WEBHOOK_ID or os.environ.get('HELIUS_WEBHOOK_ID')
except ImportError:
    api_key = os.environ.get('HELIUS_API_KEY')
    webhook_id = os.environ.get('HELIUS_WEBHOOK_ID')

if not api_key or not webhook_id:
    print("❌ Error: Missing HELIUS_API_KEY or HELIUS_WEBHOOK_ID")
    print("   Set environment variables or configure in webhook_config.py")
    sys.exit(1)

print(f"🔄 Adding {len(all_addresses)} addresses to Helius webhook...")
if personal_wallet:
    print(f"Personal wallet: {personal_wallet}")
print(f"Tracked wallets ({len(tracked_wallets)}): {tracked_wallets}")

# Update webhook
update_url = f"https://api.helius.xyz/v0/webhooks/{webhook_id}?api-key={api_key}"

payload = {
    "webhookURL": "https://helius-webhook-handler.onrender.com/webhook",
    "transactionTypes": ["ANY"],
    "accountAddresses": all_addresses,
    "webhookType": "enhanced"
}

try:
    response = requests.put(update_url, json=payload, timeout=30)
    
    if response.status_code == 200:
        print("✅ Successfully updated Helius webhook!")
        print(f"📊 Registered {len(all_addresses)} addresses:")
        for addr in all_addresses:
            print(f"   {addr}")
    else:
        print(f"❌ Failed to update webhook: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error updating webhook: {e}")
    sys.exit(1)