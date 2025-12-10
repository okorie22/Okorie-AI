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
        # Current path: ITORO/agent-systems/imela/main.py
        # Target: ITORO/.env
        current = Path(__file__).parent  # imela directory
        agent_systems_dir = current.parent  # agent-systems directory
        itoro_root = agent_systems_dir.parent  # ITORO directory
        env_file = itoro_root / '.env'   # ITORO/.env

        if env_file.exists():
            # Read .env file manually to avoid null character issues
            with open(env_file, 'rb') as f:  # Read as binary to handle encoding issues
                raw_content = f.read()

            # Decode and clean the content
            content = raw_content.decode('utf-8', errors='replace')
            # Remove null characters and other problematic characters
            content = content.replace('\x00', '').replace('\ufeff', '')

            # Split by lines and process
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    try:
                        # Handle multiple = signs by splitting only on first =
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")

                            # Only set ZerePy-relevant keys if not already set
                            zerepy_keys = ['DEEPSEEK_KEY', 'DISCORD_BOT_TOKEN', 'GMAIL_APP_PASSWORD', 'YOUTUBE_CLIENT_ID',
                                          'YOUTUBE_CLIENT_SECRET', 'TWITTER_CONSUMER_KEY',
                                          'TWITTER_CONSUMER_SECRET', 'TWITTER_ACCESS_TOKEN',
                                          'TWITTER_ACCESS_TOKEN_SECRET', 'TWITTER_USER_ID']

                            if key in zerepy_keys and key and value and not os.getenv(key):
                                os.environ[key] = value
                    except Exception:
                        continue

    except Exception:
        pass  # Fail silently, environment variables may already be set

# Load environment at startup
load_env_from_root()

from src.cli import ZerePyCLI

if __name__ == "__main__":
    cli = ZerePyCLI()
    cli.main_loop()
