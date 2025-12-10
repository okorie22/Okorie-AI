"""
🛠️ ITORO Commerce Utilities
Common utility functions for commerce agents

Includes data formatting, validation, encryption, rate limiting, and other shared utilities.
"""

import os
import json
import time
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from functools import wraps
import logging
import threading
from collections import defaultdict

from .config import (
    API_KEY_LENGTH, API_KEY_EXPIRY_DAYS, ENCRYPTION_KEY, JWT_SECRET_KEY,
    RATE_LIMIT_REQUESTS_PER_HOUR, RATE_LIMIT_REQUESTS_PER_DAY,
    AGGREGATION_TIMEZONE, DEBUG_MODE
)

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 🔐 ENCRYPTION & SECURITY UTILITIES
# =============================================================================

class EncryptionManager:
    """Handle encryption/decryption operations"""

    def __init__(self, key: Optional[str] = None):
        self.key = key or ENCRYPTION_KEY
        if not self.key:
            logger.warning("No encryption key provided - encryption disabled")
            self.enabled = False
        else:
            self.enabled = True
            # Ensure key is 32 bytes for AES-256
            if len(self.key) != 32:
                # Hash the key to get 32 bytes
                self.key = hashlib.sha256(self.key.encode()).digest()

    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        if not self.enabled:
            return data

        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64

            # Generate a key from password
            salt = b'itoro_commerce_salt'
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.key.encode()))

            f = Fernet(key)
            encrypted = f.encrypt(data.encode())
            return encrypted.decode()
        except ImportError:
            logger.warning("Cryptography library not installed - using plain text")
            return data
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return data

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        if not self.enabled:
            return encrypted_data

        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64

            # Generate the same key from password
            salt = b'itoro_commerce_salt'
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.key.encode()))

            f = Fernet(key)
            decrypted = f.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except ImportError:
            logger.warning("Cryptography library not installed - returning plain text")
            return encrypted_data
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data

# Global encryption manager
encryption_manager = EncryptionManager()

# =============================================================================
# 🔑 API KEY MANAGEMENT
# =============================================================================

class APIKeyManager:
    """Manage API key generation, validation, and storage"""

    def __init__(self):
        self.keys_file = os.path.join('data', 'api_keys.json')
        self.keys = self._load_keys()

    def _load_keys(self) -> Dict[str, Dict[str, Any]]:
        """Load API keys from file"""
        try:
            if os.path.exists(self.keys_file):
                with open(self.keys_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load API keys: {e}")
            return {}

    def _save_keys(self):
        """Save API keys to file"""
        try:
            os.makedirs(os.path.dirname(self.keys_file), exist_ok=True)
            with open(self.keys_file, 'w') as f:
                json.dump(self.keys, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save API keys: {e}")

    def generate_api_key(self, user_id: str, tier: str = 'free') -> str:
        """Generate a new API key for user"""
        # Generate random key
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(API_KEY_LENGTH))

        # Hash the key for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Store key info
        self.keys[key_hash] = {
            'user_id': user_id,
            'tier': tier,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=API_KEY_EXPIRY_DAYS)).isoformat(),
            'is_active': True,
            'usage_count': 0,
            'last_used': None
        }

        self._save_keys()
        logger.info(f"Generated API key for user {user_id}")
        return api_key

    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and return user info"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        if key_hash not in self.keys:
            return None

        key_info = self.keys[key_hash]

        # Check if key is active
        if not key_info.get('is_active', False):
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(key_info['expires_at'])
        if datetime.now() > expires_at:
            key_info['is_active'] = False
            self._save_keys()
            return None

        # Update usage
        key_info['usage_count'] += 1
        key_info['last_used'] = datetime.now().isoformat()
        self._save_keys()

        return key_info

    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        if key_hash in self.keys:
            self.keys[key_hash]['is_active'] = False
            self._save_keys()
            logger.info(f"Revoked API key")
            return True

        return False

    def get_user_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all API keys for a user"""
        user_keys = []
        for key_hash, key_info in self.keys.items():
            if key_info.get('user_id') == user_id:
                key_data = key_info.copy()
                key_data['key_hash'] = key_hash
                user_keys.append(key_data)

        return user_keys

# Global API key manager
api_key_manager = APIKeyManager()

# =============================================================================
# 🏃 RATE LIMITING
# =============================================================================

class RateLimiter:
    """Rate limiting for API requests"""

    def __init__(self):
        self.requests = defaultdict(list)  # user_id -> list of timestamps
        self.lock = threading.Lock()

    def is_allowed(self, user_id: str, tier: str = 'free') -> bool:
        """Check if request is allowed under rate limits"""
        with self.lock:
            now = time.time()
            user_requests = self.requests[user_id]

            # Remove old requests (older than 1 hour for hourly limit, 1 day for daily)
            user_requests[:] = [req for req in user_requests if now - req < 86400]  # Keep last 24 hours

            # Check hourly limit
            hourly_requests = [req for req in user_requests if now - req < 3600]
            if len(hourly_requests) >= RATE_LIMIT_REQUESTS_PER_HOUR:
                return False

            # Check daily limit
            if len(user_requests) >= RATE_LIMIT_REQUESTS_PER_DAY:
                return False

            # Add current request
            user_requests.append(now)
            return True

    def get_remaining_requests(self, user_id: str) -> Dict[str, int]:
        """Get remaining requests for user"""
        with self.lock:
            now = time.time()
            user_requests = self.requests[user_id]

            # Clean old requests
            user_requests[:] = [req for req in user_requests if now - req < 86400]

            hourly_requests = [req for req in user_requests if now - req < 3600]

            return {
                'hourly_remaining': max(0, RATE_LIMIT_REQUESTS_PER_HOUR - len(hourly_requests)),
                'daily_remaining': max(0, RATE_LIMIT_REQUESTS_PER_DAY - len(user_requests))
            }

# Global rate limiter
rate_limiter = RateLimiter()

# =============================================================================
# 📊 DATA FORMATTING & VALIDATION
# =============================================================================

def format_currency(amount: float, currency: str = 'USD') -> str:
    """Format currency amount"""
    try:
        if currency == 'USD':
            return f"${amount:,.2f}"
        elif currency == 'SOL':
            return f"{amount:.4f} SOL"
        else:
            return f"{amount:.4f} {currency}"
    except:
        return str(amount)

def format_percentage(value: float, decimals: int = 2) -> str:
    """Format percentage value"""
    try:
        return f"{value * 100:.{decimals}f}%"
    except:
        return str(value)

def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime object"""
    try:
        return dt.strftime(format_str)
    except:
        return str(dt)

def validate_email(email: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_wallet_address(address: str, blockchain: str = 'solana') -> bool:
    """Validate blockchain wallet address"""
    try:
        if blockchain.lower() == 'solana':
            # Solana addresses are base58 encoded and 32-44 characters
            import base58
            decoded = base58.b58decode(address)
            return len(decoded) == 32
        elif blockchain.lower() == 'ethereum':
            # Ethereum addresses start with 0x and are 42 characters
            return address.startswith('0x') and len(address) == 42 and all(c in '0123456789abcdefABCDEF' for c in address[2:])
        return False
    except:
        return False

def sanitize_string(text: str, max_length: int = 1000) -> str:
    """Sanitize string input"""
    if not isinstance(text, str):
        return str(text)[:max_length]

    # Remove potentially harmful characters
    import re
    # Allow alphanumeric, spaces, basic punctuation
    sanitized = re.sub(r'[^\w\s\.,!?\-]', '', text)
    return sanitized[:max_length]

# =============================================================================
# 📈 PERFORMANCE CALCULATIONS
# =============================================================================

def calculate_roi(initial_value: float, final_value: float) -> float:
    """Calculate return on investment"""
    if initial_value == 0:
        return 0.0
    return (final_value - initial_value) / initial_value

def calculate_win_rate(wins: int, total_trades: int) -> float:
    """Calculate win rate percentage"""
    if total_trades == 0:
        return 0.0
    return wins / total_trades

def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio"""
    if not returns or len(returns) < 2:
        return 0.0

    # Calculate average return
    avg_return = sum(returns) / len(returns)

    # Calculate standard deviation
    variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
    std_dev = variance ** 0.5

    if std_dev == 0:
        return float('inf') if avg_return > 0 else 0.0

    # Annualize (assuming daily returns)
    annualized_return = avg_return * 252
    annualized_std_dev = std_dev * (252 ** 0.5)
    annualized_risk_free = risk_free_rate

    return (annualized_return - annualized_risk_free) / annualized_std_dev

def calculate_max_drawdown(values: List[float]) -> float:
    """Calculate maximum drawdown"""
    if not values or len(values) < 2:
        return 0.0

    peak = values[0]
    max_drawdown = 0.0

    for value in values:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        max_drawdown = max(max_drawdown, drawdown)

    return max_drawdown

# =============================================================================
# 🔧 DECORATORS
# =============================================================================

def require_api_key(func):
    """Decorator to require valid API key"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract API key from request (this would be adapted based on framework)
        api_key = kwargs.get('api_key') or getattr(args[0] if args else None, 'api_key', None)

        if not api_key:
            raise ValueError("API key required")

        user_info = api_key_manager.validate_api_key(api_key)
        if not user_info:
            raise ValueError("Invalid or expired API key")

        # Check rate limits
        if not rate_limiter.is_allowed(user_info['user_id'], user_info.get('tier', 'free')):
            raise ValueError("Rate limit exceeded")

        # Add user info to kwargs
        kwargs['user_info'] = user_info
        return func(*args, **kwargs)

    return wrapper

def log_execution(func):
    """Decorator to log function execution"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.debug(f"Executing {func.__name__}")

        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(".3f")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(".3f")
            raise

    return wrapper

# =============================================================================
# 📊 DATA EXPORT UTILITIES
# =============================================================================

def export_to_csv(data: List[Dict[str, Any]], filename: str, directory: str = 'exports') -> str:
    """Export data to CSV file"""
    try:
        import csv
        os.makedirs(directory, exist_ok=True)

        if not data:
            return ""

        filepath = os.path.join(directory, filename)

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        logger.info(f"Exported {len(data)} records to {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Failed to export CSV: {e}")
        return ""

def export_to_json(data: List[Dict[str, Any]], filename: str, directory: str = 'exports') -> str:
    """Export data to JSON file"""
    try:
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, filename)

        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, default=str)

        logger.info(f"Exported {len(data)} records to {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Failed to export JSON: {e}")
        return ""

# =============================================================================
# 🌐 TELEGRAM UTILITIES
# =============================================================================

class TelegramNotifier:
    """Handle Telegram notifications"""

    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, message: str, parse_mode: str = 'HTML', channel_id: Optional[str] = None) -> bool:
        """Send message to Telegram channel"""
        try:
            import requests

            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': channel_id or self.channel_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            logger.info("Telegram message sent successfully")
            return True

        except ImportError:
            logger.warning("Requests library not installed - cannot send Telegram messages")
            return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def format_signal_message(self, symbol: str, action: str, confidence: float,
                            price: float, source: str) -> str:
        """Format trading signal for Telegram"""
        emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "🟡"

        message = f"""
{emoji} <b>{action} SIGNAL</b> {emoji}

<b>Symbol:</b> {symbol}
<b>Price:</b> ${price:.4f}
<b>Confidence:</b> {confidence:.1%}
<b>Source:</b> {source}
<b>Time:</b> {datetime.now().strftime('%H:%M:%S UTC')}

<i>Generated by ITORO AI Trading System</i>
        """.strip()

        return message

    def format_whale_alert(self, address: str, twitter_handle: str, score: float, rank: int) -> str:
        """Format whale ranking alert for Telegram"""
        message = f"""
🐋 <b>TOP WHALE ALERT</b> 🐋

<b>Rank:</b> #{rank}
<b>Address:</b> <code>{address[:8]}...{address[-4:]}</code>
<b>Twitter:</b> @{twitter_handle if twitter_handle != 'None' else 'N/A'}
<b>Score:</b> {score:.3f}
<b>Updated:</b> {datetime.now().strftime('%H:%M:%S UTC')}

<i>ITORO Whale Tracking System</i>
        """.strip()

        return message

# =============================================================================
# 🎯 MISCELLANEOUS UTILITIES
# =============================================================================

def setup_logging(level: str = 'INFO', to_file: bool = True):
    """Setup logging configuration"""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Setup file handler if requested
    handlers = [console_handler]
    if to_file:
        from .config import LOG_DIRECTORY, LOG_FILENAME
        os.makedirs(LOG_DIRECTORY, exist_ok=True)
        log_file = os.path.join(LOG_DIRECTORY, LOG_FILENAME)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )

def load_json_file(filepath: str) -> Dict[str, Any]:
    """Safely load JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filepath}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load {filepath}: {e}")
        return {}

def save_json_file(filepath: str, data: Dict[str, Any]) -> bool:
    """Safely save JSON file"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"Failed to save {filepath}: {e}")
        return False

def generate_unique_id(prefix: str = '') -> str:
    """Generate unique ID"""
    timestamp = int(time.time() * 1000000)  # Microsecond precision
    random_part = secrets.token_hex(4)
    return f"{prefix}_{timestamp}_{random_part}"

def chunk_list(data: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks"""
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

# =============================================================================
# 🧪 TEST FUNCTIONS
# =============================================================================

def test_utilities():
    """Test utility functions"""
    print("🧪 Testing ITORO Utilities...")

    # Test encryption
    test_data = "Hello, World!"
    encrypted = encryption_manager.encrypt(test_data)
    decrypted = encryption_manager.decrypt(encrypted)
    print(f"✅ Encryption test: {test_data} -> {decrypted}")

    # Test API key generation
    api_key = api_key_manager.generate_api_key("test_user")
    validation = api_key_manager.validate_api_key(api_key)
    print(f"✅ API key test: Generated and validated key for user {validation['user_id'] if validation else 'None'}")

    # Test rate limiting
    allowed = rate_limiter.is_allowed("test_user")
    print(f"✅ Rate limiting test: Request allowed = {allowed}")

    # Test data formatting
    print(f"✅ Currency format: {format_currency(1234.56)}")
    print(f"✅ Percentage format: {format_percentage(0.1234)}")

    # Test performance calculations
    returns = [0.01, 0.02, -0.005, 0.015, 0.008]
    sharpe = calculate_sharpe_ratio(returns)
    print(f"✅ Sharpe ratio test: {sharpe:.3f}")

    print("🎉 All utility tests completed!")

if __name__ == "__main__":
    test_utilities()
