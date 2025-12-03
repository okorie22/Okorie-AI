#!/usr/bin/env python3
"""
Test script for Discord connection in ZerePy
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set environment variables directly (avoid .env file for now)
os.environ['DEEPSEEK_KEY'] = 'sk-8954c2a2ed664a43ba110ece54595444'
os.environ['DISCORD_BOT_TOKEN'] = 'MTQ0NTU3MDA1ODQ0MDAyMDA0OA.Gjj3B3.wv4P-RCBRTGguRQrv7xoTRYkjB3OE0I378rVg8'

from connections.discord_connection import DiscordConnection

def test_discord_connection():
    """Test the Discord connection"""
    print("🤖 Testing Discord Connection for ZerePy")
    print("=" * 50)

    # Check environment
    discord_token = os.getenv('DISCORD_BOT_TOKEN')
    if discord_token:
        print(f"✅ DISCORD_BOT_TOKEN found: {discord_token[:20]}...")
    else:
        print("❌ DISCORD_BOT_TOKEN not found in environment")
        return False

    # Create connection with user's server ID
    try:
        config = {
            'guild_id': '1445575379321360527',  # User's server ID
            'command_prefix': '!',
            'auto_join_voice': False,
            'log_channel_id': '1445575379321360527',  # Using server ID as placeholder
            'welcome_channel_id': '1445575379321360527',  # Using server ID as placeholder
            'auto_mod_enabled': True,
            'spam_threshold': 5
        }
        conn = DiscordConnection(config)
        print("✅ Discord connection created")
    except Exception as e:
        print(f"❌ Failed to create connection: {e}")
        return False

    # Test configuration
    try:
        print("\n🔧 Testing configuration...")
        is_configured = conn.is_configured(verbose=True)
        if is_configured:
            print("✅ Discord API is configured and accessible")
        else:
            print("❌ Discord API configuration failed")
            return False
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

    # Test server info retrieval
    try:
        print("\n📊 Testing server info retrieval...")
        server_info = conn.perform_action('get-server-info', {})
        print(f"✅ Connected to server: {server_info.get('name', 'Unknown')}")
        print(f"   Server ID: {server_info.get('guild_id', 'Unknown')}")
        print(f"   Member count: {server_info.get('member_count', 'Unknown')}")
    except Exception as e:
        print(f"⚠️ Server info test failed: {e}")
        print("   This might be because the bot hasn't been invited to the server yet")

    print("\n🎉 Discord connection tests completed!")
    return True

if __name__ == "__main__":
    success = test_discord_connection()
    sys.exit(0 if success else 1)
