#!/usr/bin/env python3
"""
Trade Executor Subprocess
Runs the trading agent in event-driven mode as a separate process
"""

import sys
import os
import importlib.util
from pathlib import Path

# Add app directory to path for imports
import os
app_path = os.path.join(os.path.dirname(__file__), '..')
if app_path not in sys.path:
    sys.path.insert(0, app_path)

# Define paths relative to app directory (self-contained app)
shared_path = os.path.join(os.path.dirname(__file__), '..')  # Points to app/

# Import trading_agent module directly to avoid triggering agents/__init__.py
# which has problematic imports that fail in this context
trading_agent_file = os.path.join(shared_path, "agent", "trading_agent.py")
spec = importlib.util.spec_from_file_location("trading_agent", trading_agent_file)
trading_agent_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trading_agent_module)
TradingAgent = trading_agent_module.TradingAgent

def main():
    """Launch trading agent subprocess"""
    print(">>> Starting Trade Executor...")
    print(">>> Listening for strategy signals...")

    try:
        agent = TradingAgent()
        agent.run_event_loop()
    except KeyboardInterrupt:
        print(">>> Trade Executor shutting down...")
    except Exception as e:
        print(f"ERROR: Trade executor error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
