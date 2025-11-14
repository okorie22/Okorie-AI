#!/usr/bin/env python3
"""
Simple script to send BONK, WIF, and PYTH buy events to copybot
"""

import requests
import json
import time
import sys

def send_buy_event(token_name, token_address, wallet_address="DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm"):
    """Send a buy event for a specific token"""

    event = {
        "signature": f"copybot_test_{token_name.lower()}_{int(time.time())}",
        "timestamp": int(time.time()),
        "accounts": [{
            "wallet": wallet_address,
            "token": token_address,
            "action": "buy",
            "amount": 100.0,  # $100 position
            "post_balance": 1000
        }]
    }

    print(f"\n🚀 Sending {token_name} buy event...")
    print(f"📡 Signature: {event['signature']}")
    print(f"👤 Wallet: {wallet_address[:8]}...")
    print(f"🪙 Token: {token_address}")

    try:
        response = requests.post(
            "http://localhost:8080/webhook",
            json={"events": [event]},
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )

        print(f"✅ Response: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"📋 Result: {json.dumps(result, indent=2)}")

            if result.get('status') == 'blocked':
                print(f"🚨 BLOCKED: {result.get('reason', 'Unknown reason')}")
            elif result.get('status') == 'processed':
                print(f"🎯 PROCESSED: {result.get('count', 0)} events")

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    print("🌙 COPYBOT BUY EVENT SIMULATOR")
    print("=" * 50)

    # Token addresses
    tokens = {
        "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"
    }

    # Check if coordinator is running
    try:
        response = requests.get("http://localhost:8080/status", timeout=3)
        print(f"✅ Coordinator is running (status: {response.status_code})")
    except:
        print("❌ ERROR: Coordinator not running!")
        print("💡 Start your copybot with: python src/main.py")
        return

    # Send buy events
    for token_name, token_address in tokens.items():
        send_buy_event(token_name, token_address)
        time.sleep(1)  # 1 second delay between events

    print("🎉 All buy events sent!")
    print("📊 Check your copybot terminal to see if it bought these tokens")

if __name__ == "__main__":
    main()
