#!/usr/bin/env python3
"""
Script to find all Discord channels and identify text channels
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def main():
    print("🔍 Discord Channel Finder")
    print("Finding all channels in your server...")
    print("-" * 50)

    try:
        from src.cli import ZerePyCLI

        # Create CLI and load agent
        cli = ZerePyCLI()
        cli._load_default_agent()

        if not cli.agent:
            print("❌ No agent loaded")
            return

        print("📊 Getting server information...")

        # Get server info first
        server_info = cli.agent.connection_manager.perform_action(
            connection_name="discord",
            action_name="get-server-info",
            params=[]
        )

        if server_info:
            print("✅ Connected to server!")
            print(f"   Server: {server_info.get('name', 'Unknown')}")
            print(f"   Members: {server_info.get('member_count', 0)}")
            print(f"   Text channels: {server_info.get('text_channels', 0)}")
            print(f"   Voice channels: {server_info.get('voice_channels', 0)}")

        print("\n📝 Getting channel list...")

        # Get channel activity to see all text channels
        channel_data = cli.agent.connection_manager.perform_action(
            connection_name="discord",
            action_name="get-channel-activity",
            params=["hours_back=1"]
        )

        if channel_data and 'channels' in channel_data:
            channels = channel_data['channels']

            print(f"\n📋 Found {len(channels)} TEXT channels:")
            print("-" * 70)
            print("Channel Name".ljust(25) + "Channel ID".ljust(20) + "Messages (24h)")
            print("-" * 70)

            text_channels = []
            for channel in channels:
                name = channel.get('channel_name', 'Unknown')
                ch_id = channel.get('channel_id', 'Unknown')
                msg_count = channel.get('message_count', 0)
                text_channels.append((name, ch_id, msg_count))
                print(f"{name:<25} {ch_id:<20} {msg_count}")

            if text_channels:
                print("
💡 RECOMMENDED: Use one of these text channel IDs in your agent config:"                print(f"   Example: '{text_channels[0][1]}' for #{text_channels[0][0]}")
            else:
                print("❌ No text channels found!")

        else:
            print("❌ Could not retrieve channel information")
            print("💡 Make sure your Discord bot has proper permissions")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
