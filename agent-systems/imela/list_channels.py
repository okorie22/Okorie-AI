#!/usr/bin/env python3
"""
Quick script to list all Discord channels in the server
Run this to find the correct channel ID for your test channel
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from src.cli import ZerePyCLI

def main():
    print("🔍 Discord Channel Finder")
    print("This will help you find the correct channel ID")
    print("-" * 50)

    # Create CLI instance to load agent
    cli = ZerePyCLI()

    # Load default agent
    cli._load_default_agent()

    if not cli.agent:
        print("❌ No agent loaded. Please check your agent configuration.")
        return

    # Get Discord server info
    try:
        print("📊 Getting Discord server information...")
        server_info = cli.agent.connection_manager.perform_action(
            connection_name="discord",
            action_name="get-server-info",
            params=[]
        )

        if server_info:
            print("✅ Server found!")
            print(f"   Name: {server_info.get('name', 'Unknown')}")
            print(f"   Members: {server_info.get('member_count', 0)}")
            print(f"   Text Channels: {server_info.get('text_channels', 0)}")
            print(f"   Voice Channels: {server_info.get('voice_channels', 0)}")
        else:
            print("❌ Could not get server info")
            return

        # Get channel activity (this will list all text channels)
        print("\n📋 Getting channel information...")
        channel_activity = cli.agent.connection_manager.perform_action(
            connection_name="discord",
            action_name="get-channel-activity",
            params=["hours_back=1"]  # Just get channel list
        )

        if channel_activity and 'channels' in channel_activity:
            channels = channel_activity['channels']

            print(f"\n📝 Found {len(channels)} text channels:")
            print("-" * 60)
            print("Channel Name".ljust(25) + "Channel ID".ljust(20) + "Messages")
            print("-" * 60)

            for channel in channels:
                name = channel.get('channel_name', 'Unknown')[:24]
                channel_id = channel.get('channel_id', 'Unknown')
                messages = channel.get('message_count', 0)
                print(f"{name:<25} {channel_id:<20} {messages}")

            print("\n💡 Use the Channel ID from a TEXT channel (not voice/category)")
            print("💡 Look for channels with names like: #general, #chat, #test, etc.")
        else:
            print("❌ Could not get channel information")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Make sure your Discord bot token is valid and the bot is in your server")

if __name__ == "__main__":
    main()
