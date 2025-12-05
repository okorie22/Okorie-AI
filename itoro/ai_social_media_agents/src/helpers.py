def print_h_bar():
    # ZEREBRO WUZ HERE :)
    print("--------------------------------------------------------------------")

def find_env_file():
    """Find .env file by walking up the directory tree and load manually to avoid null character issues"""
    from pathlib import Path
    import os
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Start from current file location (src/helpers.py)
    # Path: ITORO/itoro/ai_social_media_agents/src/helpers.py
    # Need: ITORO/.env
    current = Path(__file__).parent.parent  # ai_social_media_agents directory
    itoro_root = current.parent.parent / '.env'  # ITORO/.env
    
    # Try ITORO root first (most likely location)
    if itoro_root.exists():
        try:
            # Read .env file manually to avoid null character issues
            with open(itoro_root, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Remove null characters
                content = content.replace('\x00', '')
                # Split by lines and set environment variables
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        try:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            # Only set if not already set
                            if key and value and not os.getenv(key):
                                os.environ[key] = value
                        except Exception:
                            continue
            logger.debug(f"Loaded .env from: {itoro_root}")
            return str(itoro_root)
        except Exception as e:
            logger.warning(f"Failed to load .env from {itoro_root}: {e}")
    
    # Walk up the directory tree looking for .env
    for path in [current] + list(current.parents):
        env_file = path / '.env'
        if env_file.exists() and env_file != itoro_root:
            try:
                # Read manually to avoid null characters
                with open(env_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().replace('\x00', '')
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            try:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                if key and value and not os.getenv(key):
                                    os.environ[key] = value
                            except Exception:
                                continue
                logger.debug(f"Loaded .env from: {env_file}")
                return str(env_file)
            except Exception as e:
                logger.warning(f"Failed to load .env from {env_file}: {e}")
                continue
    
    return None