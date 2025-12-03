#!/usr/bin/env python3
"""
Simple Discord test - just try to get server info
"""
import os
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set environment variables
os.environ['DISCORD_BOT_TOKEN'] = 'MTQ0NTU3MDA1ODQ0MDAyMDA0OA.Gjj3B3.wv4P-RCBRTGguRQrv7xoTRYkjB3OE0I378rVg8'
os.environ['DEEPSEEK_KEY'] = 'sk-8954c2a2ed664a43ba110ece54595444'

from connections.discord_connection import DiscordConnection

async def test_discord():
    """Test Discord connection with a simple action"""
    print("🤖 Testing Discord Connection (Simple Test)")
    print("=" * 50)
    
    config = {
        'guild_id': '1445575379321360527',
        'command_prefix': '!',
        'auto_join_voice': False,
        'log_channel_id': None,
        'welcome_channel_id': None,
        'auto_mod_enabled': True,
        'spam_threshold': 5
    }
    
    try:
        conn = DiscordConnection(config)
        print("✅ Discord connection object created")
        
        # Try to get server info directly
        print("\n📊 Attempting to get server info...")
        result = await conn.get_server_info()
        
        print(f"✅ SUCCESS! Server info retrieved:")
        print(f"   Server Name: {result.get('name', 'Unknown')}")
        print(f"   Server ID: {result.get('guild_id', 'Unknown')}")
        print(f"   Member Count: {result.get('member_count', 'Unknown')}")
        print(f"   Text Channels: {result.get('text_channels', 'Unknown')}")
        print(f"   Voice Channels: {result.get('voice_channels', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_discord())
    sys.exit(0 if result else 1)
