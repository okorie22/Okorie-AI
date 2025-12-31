"""
Configuration System for SolPattern Detector
Manages all user-configurable settings
"""

import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SolPatternConfig:
    """
    Configuration class for SolPattern Detector.
    Handles all user settings and environment variables.
    """

    def __init__(self):
        """Initialize configuration with defaults and environment overrides."""

        # AI Settings
        self.ai_provider = os.getenv('AI_PROVIDER', 'deepseek')
        self.deepseek_api_key = os.getenv('DEEPSEEK_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.ai_model = os.getenv('AI_MODEL', 'deepseek-chat')

        # Discord Settings (Primary notification method)
        self.discord_enabled = os.getenv('DISCORD_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
        self.discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')
        self.discord_client_id = os.getenv('DISCORD_CLIENT_ID')
        self.discord_client_secret = os.getenv('DISCORD_CLIENT_SECRET')

        # Email Settings (Fallback only)
        self.email_enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_username = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASS')
        self.from_email = os.getenv('FROM_EMAIL', self.email_username)
        self.alert_emails = os.getenv('ALERT_EMAILS', '').split(',') if os.getenv('ALERT_EMAILS') else []

        # Notification Settings
        self.desktop_notifications = os.getenv('DESKTOP_NOTIFICATIONS', 'true').lower() == 'true'
        self.discord_notifications = os.getenv('DISCORD_NOTIFICATIONS', 'true').lower() == 'true'

        # Trading Settings
        self.symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT').split(',')
        self.scan_interval = int(os.getenv('SCAN_INTERVAL', '300'))  # seconds
        self.data_timeframe = os.getenv('DATA_TIMEFRAME', '1d')

        # System Settings
        self.db_path = os.getenv('DB_PATH', 'patterns.db')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        # Alert Settings
        self.alert_cooldown_hours = int(os.getenv('ALERT_COOLDOWN_HOURS', '24'))

        self._validate_config()

    def get_discord_config(self) -> Dict[str, str]:
        """Get Discord configuration for bot initialization"""
        return {
            'bot_token': self.discord_bot_token,
            'client_id': self.discord_client_id,
            'client_secret': self.discord_client_secret,
            'enabled': self.discord_enabled
        }

    def get_notification_config(self) -> Dict[str, bool]:
        """Get notification preferences"""
        return {
            'desktop': self.desktop_notifications,
            'discord': self.discord_notifications,
            'email': self.email_enabled  # Fallback only
        }

    def _validate_config(self):
        """Validate configuration and warn about missing required settings."""

        warnings = []
        errors = []

        # AI Validation
        if self.ai_provider == 'deepseek' and not self.deepseek_api_key:
            warnings.append("DeepSeek API key not found (DEEPSEEK_KEY)")
        elif self.ai_provider == 'openai' and not self.openai_api_key:
            warnings.append("OpenAI API key not found (OPENAI_API_KEY)")

        # Email Validation
        if self.email_enabled:
            if not self.email_username:
                warnings.append("Email username not found (EMAIL_USER)")
            if not self.email_password:
                warnings.append("Email password not found (EMAIL_PASS)")
            if not self.alert_emails:
                warnings.append("No alert email addresses found (ALERT_EMAILS)")

        # Show validation results
        if errors:
            print("[CONFIG] ERROR: Configuration Errors:")
            for error in errors:
                print(f"  - {error}")

        if warnings:
            print("[CONFIG] WARNING: Configuration Warnings:")
            for warning in warnings:
                print(f"  - {warning}")

        if not errors and not warnings:
            print("[CONFIG] SUCCESS: Configuration validated successfully")

    def get_ai_config(self) -> Dict:
        """Get AI-related configuration."""
        return {
            'provider': self.ai_provider,
            'api_key': self.deepseek_api_key if self.ai_provider == 'deepseek' else self.openai_api_key,
            'model': self.ai_model,
            'base_url': "https://api.deepseek.com/v1" if self.ai_provider == 'deepseek' else None
        }

    def get_email_config(self) -> Optional[Dict]:
        """Get email-related configuration."""
        if not self.email_enabled or not self.email_username or not self.alert_emails:
            return None

        return {
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'username': self.email_username,
            'password': self.email_password,
            'from_email': self.from_email,
            'to_emails': [email.strip() for email in self.alert_emails if email.strip()]
        }

    def get_trading_config(self) -> Dict:
        """Get trading-related configuration."""
        return {
            'symbols': [s.strip() for s in self.symbols if s.strip()],
            'scan_interval': self.scan_interval,
            'data_timeframe': self.data_timeframe
        }

    def get_system_config(self) -> Dict:
        """Get system-related configuration."""
        return {
            'db_path': self.db_path,
            'log_level': self.log_level,
            'alert_cooldown_hours': self.alert_cooldown_hours
        }

    def print_config_summary(self):
        """Print a summary of current configuration."""
        print("\n" + "="*60)
        print("SOLPATTERN DETECTOR CONFIGURATION")
        print("="*60)

        print(f"AI Provider: {self.ai_provider}")
        print(f"Email Enabled: {self.email_enabled}")
        print(f"Desktop Notifications: {self.desktop_notifications}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Scan Interval: {self.scan_interval} seconds")
        print(f"Timeframe: {self.data_timeframe}")
        print(f"Database: {self.db_path}")
        print(f"Alert Cooldown: {self.alert_cooldown_hours} hours")

        if self.alert_emails:
            print(f"📬 Alert Emails: {len(self.alert_emails)} configured")

        print("="*60 + "\n")


# Global config instance
config = SolPatternConfig()
