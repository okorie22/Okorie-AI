#!/usr/bin/env python3
"""
Test script to verify Discord connection fix
"""
import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load environment variables like the CLI does
from load_env import load_zerepy_env
load_zerepy_env()

from src.connections.discord_connection import DiscordConnection

def test_discord_connection():
    """Test the Discord connection fix"""
    print("Testing Discord connection fix...")

    # Load agent config to get Discord configuration
    agent_path = Path("agents") / "example.json"
    if not agent_path.exists():
        print("❌ Agent config not found")
        return False

    try:
        with open(agent_path, 'r') as f:
            agent_config = json.load(f)

        # Find Discord config
        discord_config = None
        for config in agent_config.get('config', []):
            if config.get('name') == 'discord':
                discord_config = config
                break

        if not discord_config:
            print("❌ Discord config not found in agent")
            return False

        print("✅ Found Discord config")

        # Create connection
        print("🔧 Creating Discord connection...")
        conn = DiscordConnection(discord_config)

        # Test configuration
        print("🔍 Testing configuration...")
        if not conn.is_configured():
            print("❌ Discord not configured")
            return False

        print("✅ Discord configured")

        # Test action
        print("📤 Testing send-message action...")
        try:
            result = conn.perform_action('send-message', {
                'channel_id': '1445575380336513138',
                'content': 'Test message from fixed connection!'
            })
            print("✅ Message sent successfully!")
            print(f"Result: {result}")
            return True
        except Exception as e:
            print(f"❌ Failed to send message: {e}")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_discord_connection()
    sys.exit(0 if success else 1)
