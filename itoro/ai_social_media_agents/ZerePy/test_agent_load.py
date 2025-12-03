#!/usr/bin/env python3
"""
Test agent loading without Twitter requirement
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

os.environ['DEEPSEEK_KEY'] = 'sk-8954c2a2ed664a43ba110ece54595444'

print("🧪 Testing Agent Loading...")
print("=" * 40)

try:
    from agent import ZerePyAgent
    
    print("✅ ZerePyAgent imported")
    
    # Try loading the example agent
    print("\n📋 Loading example agent...")
    agent = ZerePyAgent("example")
    
    print(f"✅ Agent loaded successfully!")
    print(f"   Name: {agent.name}")
    print(f"   Connections: {list(agent.connection_manager.connections.keys())}")
    print(f"   Tweet interval: {agent.tweet_interval}")
    print(f"   Tasks: {len(agent.tasks)}")
    
except KeyError as e:
    print(f"❌ KeyError: {e}")
    print("   This means Twitter is still required somewhere")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 40)
