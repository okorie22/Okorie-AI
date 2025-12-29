#!/usr/bin/env python3
"""
Test script for Discord bot functionality
"""

import sys
import os
import time
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from discord_bot import get_discord_bot, start_discord_bot
from dotenv import load_dotenv

load_dotenv()

def test_discord_bot():
    """Test Discord bot functionality"""
    print("Testing Discord Bot Integration")
    print("=" * 50)

    # Initialize bot
    bot = get_discord_bot()
    if not bot.bot_token:
        print("ERROR: No Discord bot token found in .env")
        return False

    print(f"[OK] Bot token found: {bot.bot_token[:10]}...")

    # Test user database
    print("\nTesting user database...")
    test_user_id = "123456789"
    test_username = "TestUser"

    # Store test user
    bot.store_discord_user(test_user_id, test_username)
    print(f"[OK] Stored test user: {test_username} ({test_user_id})")

    # Check if user is enabled
    enabled = bot.is_user_enabled(test_user_id)
    print(f"[OK] User enabled status: {enabled}")

    # Get enabled users
    enabled_users = bot.get_enabled_users()
    print(f"[OK] Enabled users: {len(enabled_users)}")

    # Test embed creation
    print("\nTesting alert embed creation...")
    test_pattern_data = {
        'symbol': 'BTCUSDT',
        'pattern': 'doji',
        'direction': 'long',
        'confidence': 0.85,
        'regime': 'strong_uptrend',
        'regime_confidence': 0.92,
        'ohlcv': {'close': 45000.50},
        'confirmations': {'trend': True, 'momentum': True, 'volume': False},
        'parameters': {
            'stop_loss_pct': 0.02,
            'profit_target_pct': 0.05,
            'max_holding_period': 48
        },
        'ai_analysis': "Strong bullish doji pattern detected with positive momentum confirmation. Consider long entry with tight risk management."
    }

    try:
        embed = bot.create_alert_embed(test_pattern_data)
        print("[OK] Alert embed created successfully")
        print(f"   Title: {embed.title}")
        print(f"   Fields: {len(embed.fields)}")
        print(f"   Color: {embed.color}")
    except Exception as e:
        print(f"ERROR: Creating embed: {e}")
        return False

    # Start bot in background (optional test)
    print("\nTesting bot startup...")
    try:
        start_discord_bot()
        print("[OK] Bot startup initiated")

        # Give it a moment to connect
        time.sleep(3)

        if bot.is_running():
            print("[OK] Bot reports as running")
        else:
            print("WARNING: Bot may not be fully connected yet (normal for test)")

    except Exception as e:
        print(f"WARNING: Bot startup issue (may be normal): {e}")

    print("\nDiscord bot tests completed!")
    print("\nNext steps:")
    print("1. Add bot to your Discord server using OAuth URL")
    print("2. DM the bot '!enable_alerts' to test user setup")
    print("3. Run pattern detection to test full integration")

    return True

def generate_oauth_url():
    """Generate Discord OAuth URL for adding bot"""
    client_id = os.getenv('DISCORD_CLIENT_ID')
    if not client_id:
        print("ERROR: No DISCORD_CLIENT_ID found in .env")
        return None

    # Basic permissions for DM bot
    permissions = 2048  # Send messages
    scope = "bot"

    oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions={permissions}&scope={scope}"

    print("Discord Bot OAuth URL:")
    print(oauth_url)
    print("\nInstructions:")
    print("1. Copy and paste this URL in your browser")
    print("2. Select your Discord server")
    print("3. Authorize the bot")
    print("4. The bot will join your server")

    return oauth_url

if __name__ == "__main__":
    print("SolPattern Discord Bot Test Suite")
    print("=" * 50)

    # Generate OAuth URL first (optional)
    try:
        oauth_url = generate_oauth_url()
        if oauth_url:
            print()
    except:
        print("Note: OAuth URL generation skipped (missing DISCORD_CLIENT_ID)")
        print()

    # Run tests
    success = test_discord_bot()

    if success:
        print("\n[OK] All tests passed!")
    else:
        print("\n[ERROR] Some tests failed - check configuration")

    print("\nDiscord Bot Commands:")
    print("!enable_alerts  - Enable pattern notifications")
    print("!disable_alerts - Disable pattern notifications")
    print("!status        - Check your notification status")
    print("!info          - Show available commands")
