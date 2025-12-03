#!/usr/bin/env python3
"""
Load environment variables from ITORO root .env file
This works around issues with embedded null characters in the main .env
"""
import os
import sys
from pathlib import Path

def load_zerepy_env():
    """Load ZerePy-specific environment variables"""
    # Known values from ITORO root .env
    env_vars = {
        'DEEPSEEK_KEY': 'sk-8954c2a2ed664a43ba110ece54595444',
        'DISCORD_BOT_TOKEN': 'MTQ0NTU3MDA1ODQ0MDAyMDA0OA.GerKkQ.aaSKk6DjMVlh0CsUx6ZDvn8RWMgJKk8JVw9g_I',
    }
    
    # Set them if not already set
    for key, value in env_vars.items():
        if not os.getenv(key):
            os.environ[key] = value
    
    return env_vars

if __name__ == "__main__":
    load_zerepy_env()
    print("✅ Environment variables loaded")
    print(f"DEEPSEEK_KEY: {'SET' if os.getenv('DEEPSEEK_KEY') else 'NOT SET'}")
    print(f"DISCORD_BOT_TOKEN: {'SET' if os.getenv('DISCORD_BOT_TOKEN') else 'NOT SET'}")
