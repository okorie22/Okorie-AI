#!/usr/bin/env python3
"""
Check available connections in ZerePy
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set environment variables
os.environ['DEEPSEEK_KEY'] = 'sk-8954c2a2ed664a43ba110ece54595444'
os.environ['DISCORD_BOT_TOKEN'] = 'MTQ0NTU3MDA1ODQ0MDAyMDA0OA.GerKkQ.aaSKk6DjMVlh0CsUx6ZDvn8RWMgJKk8JVw9g_I'

from connection_manager import ConnectionManager

def check_connections():
    """Check what connections are available"""
    print("🔍 Checking ZerePy Connections")
    print("=" * 40)

    # Load the default agent configuration
    try:
        with open('agents/example.json', 'r') as f:
            import json
            agent_config = json.load(f)
        print(f"✅ Loaded agent: {agent_config['name']}")
    except Exception as e:
        print(f"❌ Failed to load agent config: {e}")
        return

    # Get connections from agent config
    connections_config = agent_config.get('config', [])
    print(f"📋 Agent has {len(connections_config)} connection configurations:")

    for config in connections_config:
        conn_name = config.get('name', 'unknown')
        print(f"  - {conn_name}")

    # Test ConnectionManager
    print(f"\n🔧 Testing ConnectionManager...")
    try:
        cm = ConnectionManager(connections_config)
        print("✅ ConnectionManager created successfully")
        print(f"📊 Available connections: {list(cm.connections.keys())}")

        # Check each connection status
        print(f"\n📈 Connection Status:")
        for name, conn in cm.connections.items():
            try:
                configured = conn.is_configured(verbose=False)
                status = "✅ Configured" if configured else "❌ Not Configured"
                print(f"  - {name}: {status}")
            except Exception as e:
                print(f"  - {name}: ❌ Error - {str(e)}")

    except Exception as e:
        print(f"❌ ConnectionManager failed: {e}")

if __name__ == "__main__":
    check_connections()
