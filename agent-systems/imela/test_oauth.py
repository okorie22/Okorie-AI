#!/usr/bin/env python3
"""
Test script for YouTube OAuth flow - runs without CLI interface
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load environment variables from root .env
def load_env():
    """Load .env from ITORO root directory"""
    try:
        current = Path(__file__).parent
        itoro_root = current.parent.parent.parent
        env_file = itoro_root / '.env'

        if env_file.exists():
            with open(env_file, 'rb') as f:
                raw_content = f.read()

            content = raw_content.decode('utf-8', errors='replace')
            content = content.replace('\x00', '').replace('\ufeff', '')

            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    try:
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")

                            if key and value and not os.getenv(key):
                                os.environ[key] = value
                    except Exception:
                        continue
    except Exception:
        pass

# Load env and test OAuth
load_env()

from connections.youtube_connection import YouTubeConnection
import logging

logging.basicConfig(level=logging.INFO)

def test_oauth():
    """Test YouTube OAuth flow"""
    print("🔍 Testing YouTube OAuth flow...")
    print(f"Client ID: {os.getenv('YOUTUBE_CLIENT_ID', 'NOT SET')[:20]}...")
    print(f"Client Secret: {'SET' if os.getenv('YOUTUBE_CLIENT_SECRET') else 'NOT SET'}")

    try:
        # Create connection and force OAuth
        yt = YouTubeConnection()
        yt.clear_credentials()  # Clear any existing tokens

        # This should trigger OAuth
        creds = yt._get_credentials()

        if creds and creds.valid:
            print("✅ OAuth successful!")
            return True
        else:
            print("❌ OAuth failed - invalid credentials")
            return False

    except Exception as e:
        print(f"❌ OAuth error: {e}")
        return False

if __name__ == "__main__":
    test_oauth()
