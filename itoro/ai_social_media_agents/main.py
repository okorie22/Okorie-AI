import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

# Load environment variables from ITORO root .env
# Workaround for embedded null character issues
def load_env_from_root():
    """Load .env from ITORO root directory"""
    try:
        # Try to find ITORO root
        # Path: ITORO/itoro/ai_social_media_agents/main.py
        # Need: ITORO/.env
        current = Path(__file__).parent  # ai_social_media_agents directory
        itoro_root = current.parent.parent / '.env'  # ITORO/.env
        
        if itoro_root.exists():
            # Read .env file manually to avoid null character issues
            with open(itoro_root, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Remove null characters
                content = content.replace('\x00', '')
                # Split by lines
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        try:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            # Only set ZerePy-relevant keys if not already set
                            zerepy_keys = ['DEEPSEEK_KEY', 'DISCORD_BOT_TOKEN', 'YOUTUBE_CLIENT_ID', 
                                          'YOUTUBE_CLIENT_SECRET', 'TWITTER_CONSUMER_KEY', 
                                          'TWITTER_CONSUMER_SECRET', 'TWITTER_ACCESS_TOKEN',
                                          'TWITTER_ACCESS_TOKEN_SECRET', 'TWITTER_USER_ID']
                            if key in zerepy_keys and key and value and not os.getenv(key):
                                os.environ[key] = value
                        except Exception:
                            continue
    except Exception:
        pass

# Load environment at startup
load_env_from_root()

from src.cli import ZerePyCLI

if __name__ == "__main__":
    cli = ZerePyCLI()
    cli.main_loop()
