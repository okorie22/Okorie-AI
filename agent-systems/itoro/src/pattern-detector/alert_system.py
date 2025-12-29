"""
Alert System - Pattern Alerts with AI Analysis
Sends desktop notifications, email alerts, and generates AI-powered analysis
"""

import os
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    print("[ALERT SYSTEM] Warning: plyer not available, desktop notifications disabled")

from openai import OpenAI
from discord_bot import get_discord_bot


class AlertSystem:
    """
    Alert system with AI-powered pattern analysis.
    Uses DeepSeek/OpenAI for analysis, plyer for desktop notifications, and SMTP for emails.
    """
    
    def __init__(self, ai_config: Optional[Dict] = None, email_config: Optional[Dict] = None,
                 discord_config: Optional[Dict] = None, enable_desktop_notifications: bool = True):
        """
        Initialize alert system.
        
        Args:
            ai_config: AI provider configuration (from config.py)
            email_config: Email configuration (from config.py)
            discord_config: Discord configuration (from config.py)
            enable_desktop_notifications: Enable/disable desktop notifications
        """
        # AI Configuration
        self.ai_config = ai_config or {}
        self.ai_enabled = bool(self.ai_config.get('api_key'))
        
        if self.ai_enabled:
            try:
                self.client = OpenAI(
                    api_key=self.ai_config['api_key'],
                    base_url=self.ai_config.get('base_url')
                )
                print(f"[ALERT SYSTEM] AI analysis enabled ({self.ai_config.get('provider', 'unknown')})")
            except Exception as e:
                print(f"[ALERT SYSTEM] Error initializing AI client: {e}")
            self.ai_enabled = False
                self.client = None
        else:
            self.client = None
            print("[ALERT SYSTEM] Warning: AI analysis disabled - no API key configured")

        # Discord Configuration (Replacing Email)
        self.discord_config = discord_config
        self.discord_enabled = bool(self.discord_config and self.discord_config.get('bot_token'))
        self.discord_bot = None

        if self.discord_enabled:
            try:
                self.discord_bot = get_discord_bot()
                print("[ALERT SYSTEM] Discord notifications enabled")
            except Exception as e:
                print(f"[ALERT SYSTEM] Error initializing Discord bot: {e}")
                self.discord_enabled = False
                self.discord_bot = None
        else:
            print("[ALERT SYSTEM] Discord notifications disabled - no bot token configured")

        # Email Configuration (Kept for backward compatibility)
        self.email_config = email_config
        self.email_enabled = bool(self.email_config and self.email_config.get('username'))

        if self.email_enabled:
            print("[ALERT SYSTEM] Email alerts enabled (fallback)")
        else:
            print("[ALERT SYSTEM] Email alerts disabled")
        
        # Desktop Notifications
        self.enable_desktop_notifications = enable_desktop_notifications and PLYER_AVAILABLE
        if not PLYER_AVAILABLE:
            print("[ALERT SYSTEM] Warning: plyer not available, desktop notifications disabled")
        
        if self.enable_desktop_notifications:
            print("[ALERT SYSTEM] Desktop notifications enabled")
        else:
            print("[ALERT SYSTEM] Desktop notifications disabled")
        
        print("[ALERT SYSTEM] Initialized successfully")
    
    def generate_ai_analysis(self, pattern_data: Dict, symbol: str) -> str:
        """
        Generate AI-powered analysis of the detected pattern.
        
        Args:
            pattern_data: Pattern detection data
            symbol: Trading symbol
            
        Returns:
            AI-generated analysis (2-3 sentences)
        """
        if not self.ai_enabled:
            return self._generate_fallback_analysis(pattern_data, symbol)
        
        try:
            # Construct analysis prompt
            prompt = f"""Analyze this {pattern_data['pattern']} pattern detected in {symbol}:

Pattern: {pattern_data['pattern']}
Direction: {pattern_data['direction'].upper()}
Confidence: {pattern_data['confidence']:.1%}
Market Regime: {pattern_data['regime']} (confidence: {pattern_data['regime_confidence']:.1%})

Price Data:
- Open: ${pattern_data['ohlcv']['open']:.2f}
- High: ${pattern_data['ohlcv']['high']:.2f}
- Low: ${pattern_data['ohlcv']['low']:.2f}
- Close: ${pattern_data['ohlcv']['close']:.2f}
- Volume: {pattern_data['ohlcv']['volume']:.2f}

Confirmations:
- Trend: {'Confirmed' if pattern_data['confirmations']['trend'] else 'Not Confirmed'}
- Momentum: {'Confirmed' if pattern_data['confirmations']['momentum'] else 'Not Confirmed'}
- Volume: {'Confirmed' if pattern_data['confirmations']['volume'] else 'Not Confirmed'}

Parameters:
- Stop Loss: {pattern_data['parameters']['stop_loss_pct']*100:.1f}%
- Profit Target: {pattern_data['parameters']['profit_target_pct']*100:.1f}%
- Max Holding Period: {pattern_data['parameters']['max_holding_period']} bars

Provide a concise 2-3 sentence trading analysis focusing on:
1. Pattern strength and reliability
2. Expected price movement
3. Key risk/reward considerations"""
            
            # Call DeepSeek API
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are an expert trading analyst specializing in technical analysis and candlestick patterns. Provide concise, actionable insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            analysis = response.choices[0].message.content.strip()
            print(f"[AI ANALYSIS] Generated for {symbol} {pattern_data['pattern']}")
            return analysis
            
        except Exception as e:
            print(f"[AI ANALYSIS] Error: {e}")
            return self._generate_fallback_analysis(pattern_data, symbol)
    
    def _generate_fallback_analysis(self, pattern_data: Dict, symbol: str) -> str:
        """
        Generate basic analysis when AI is not available.
        
        Args:
            pattern_data: Pattern detection data
            symbol: Trading symbol
            
        Returns:
            Basic pattern analysis
        """
        direction = pattern_data['direction'].upper()
        confidence = pattern_data['confidence']
        pattern = pattern_data['pattern']
        regime = pattern_data['regime'].replace('_', ' ').title()
        
        analysis = (
            f"{pattern.upper()} pattern detected in {symbol} with {confidence:.0%} confidence, "
            f"signaling a {direction} opportunity. Market regime is {regime}. "
            f"Consider {direction.lower()} entry with stop loss at "
            f"{pattern_data['parameters']['stop_loss_pct']*100:.1f}% and profit target at "
            f"{pattern_data['parameters']['profit_target_pct']*100:.1f}%."
        )
        
        return analysis
    
    def send_email_alert(self, pattern_data: Dict, symbol: str, analysis: str):
        """
        Send email alert for pattern detection.

        Args:
            pattern_data: Pattern detection data
            symbol: Trading symbol
            analysis: AI analysis text
        """
        if not self.email_enabled or not self.email_config:
            return

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = ', '.join(self.email_config['to_emails'])
            msg['Subject'] = f'ALERT: SolPattern - {symbol} {pattern_data["pattern"]}'

            # Email body
            body = f"""
PATTERN DETECTED: {symbol}

Pattern: {pattern_data['pattern'].upper()}
Direction: {pattern_data['direction'].upper()}
Signal: {pattern_data['signal']}
Confidence: {pattern_data['confidence']:.1%}
Price: ${pattern_data.get('price', 'N/A')}

Confirmations:
  Trend: {pattern_data.get('confirmations', {}).get('trend', 'N/A')}
  Momentum: {pattern_data.get('confirmations', {}).get('momentum', 'N/A')}
  Volume: {pattern_data.get('confirmations', {}).get('volume', 'N/A')}

Parameters:
  Stop Loss: {pattern_data.get('parameters', {}).get('stop_loss', 'N/A')}
  Profit Target: {pattern_data.get('parameters', {}).get('profit_target', 'N/A')}
  Max Hold: {pattern_data.get('parameters', {}).get('max_hold', 'N/A')} bars

AI ANALYSIS:
{analysis}

---
SolPattern Detector | Real-time Pattern Analysis
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            server.sendmail(self.email_config['from_email'], self.email_config['to_emails'], msg.as_string())
            server.quit()

            print(f"[EMAIL ALERT] Sent to {len(self.email_config['to_emails'])} recipients")

        except Exception as e:
            print(f"[EMAIL ALERT] Failed to send email: {e}")

    def send_desktop_notification(self, pattern_data: Dict, symbol: str, analysis: str):
        """
        Send desktop notification for detected pattern.
        
        Args:
            pattern_data: Pattern detection data
            symbol: Trading symbol
            analysis: AI-generated analysis
        """
        if not self.enable_desktop_notifications:
            return
        
        try:
            title = f"Pattern Detected: {symbol}"
            message = (
                f"{pattern_data['pattern'].upper()} ({pattern_data['direction'].upper()})\n"
                f"Confidence: {pattern_data['confidence']:.0%}\n"
                f"Price: ${pattern_data['ohlcv']['close']:.2f}"
            )
            
            notification.notify(
                title=title,
                message=message,
                app_name="SolPattern Detector",
                timeout=10
            )
            
            print(f"[DESKTOP NOTIFICATION] Sent for {symbol}")
            
        except Exception as e:
            print(f"[DESKTOP NOTIFICATION] Error: {e}")
    
    def send_alert(self, pattern_data: Dict, symbol: str, include_ai_analysis: bool = True,
                  discord_user_id: Optional[str] = None) -> Dict:
        """
        Send complete alert with AI analysis and notifications.
        
        Args:
            pattern_data: Pattern detection data
            symbol: Trading symbol
            include_ai_analysis: Whether to generate AI analysis (default: True)
            discord_user_id: Discord user ID for private DM notifications
            
        Returns:
            Dictionary with pattern_data and ai_analysis
        """
        # Generate AI analysis
        if include_ai_analysis:
            ai_analysis = self.generate_ai_analysis(pattern_data, symbol)
        else:
            ai_analysis = self._generate_fallback_analysis(pattern_data, symbol)
        
        # Print console alert
        self._print_console_alert(pattern_data, symbol, ai_analysis)
        
        # Send desktop notification
        self.send_desktop_notification(pattern_data, symbol, ai_analysis)
        
        # Send Discord DM (Primary notification method)
        discord_sent = False
        if self.discord_enabled and self.discord_bot and discord_user_id:
            # Add AI analysis to pattern data for Discord embed
            discord_pattern_data = {**pattern_data, 'ai_analysis': ai_analysis}

            try:
                # Get event loop for async call
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                discord_sent = loop.run_until_complete(
                    self.discord_bot.send_pattern_alert(discord_user_id, discord_pattern_data)
                )
                loop.close()

                if discord_sent:
                    print(f"[ALERT] Discord notification sent to user {discord_user_id}")
                else:
                    print(f"[ALERT] Discord notification failed for user {discord_user_id}")

            except Exception as e:
                print(f"[ALERT] Error sending Discord notification: {e}")

        # Send email alert (Fallback only)
        if self.email_enabled and self.email_config and not discord_sent:
            self.send_email_alert(pattern_data, symbol, ai_analysis)
            print("[ALERT] Fallback to email notification")

        # Return combined data
        return {
            'symbol': symbol,
            'pattern_data': pattern_data,
            'ai_analysis': ai_analysis,
            'alert_timestamp': datetime.now().isoformat(),
            'discord_sent': discord_sent,
            'discord_user_id': discord_user_id
        }
    
    def _print_console_alert(self, pattern_data: Dict, symbol: str, analysis: str):
        """
        Print formatted alert to console.
        
        Args:
            pattern_data: Pattern detection data
            symbol: Trading symbol
            analysis: AI-generated analysis
        """
        print("\n" + "="*80)
        print(f"PATTERN ALERT: {symbol}")
        print("="*80)
        print(f"Pattern: {pattern_data['pattern'].upper()}")
        print(f"Direction: {pattern_data['direction'].upper()}")
        print(f"Signal: {pattern_data['signal']}")
        print(f"Confidence: {pattern_data['confidence']:.1%}")
        print(f"Regime: {pattern_data['regime']} ({pattern_data['regime_confidence']:.1%})")
        print(f"\nPrice: ${pattern_data['ohlcv']['close']:.2f}")
        print(f"Time: {pattern_data['timestamp']}")
        print(f"\nConfirmations:")
        print(f"  Trend: {pattern_data['confirmations']['trend']}")
        print(f"  Momentum: {pattern_data['confirmations']['momentum']}")
        print(f"  Volume: {pattern_data['confirmations']['volume']}")
        print(f"\nParameters:")
        print(f"  Stop Loss: {pattern_data['parameters']['stop_loss_pct']*100:.1f}%")
        print(f"  Profit Target: {pattern_data['parameters']['profit_target_pct']*100:.1f}%")
        print(f"  Trailing Activation: {pattern_data['parameters']['trailing_activation_pct']*100:.1f}%")
        print(f"  Max Hold: {pattern_data['parameters']['max_holding_period']} bars")
        print(f"\n[AI ANALYSIS]")
        print(f"{analysis}")
        print("="*80 + "\n")
    
    def send_email_alert(self, pattern_data: Dict, symbol: str, analysis: str, email_address: str):
        """
        Send email alert (placeholder for future implementation).
        
        Args:
            pattern_data: Pattern detection data
            symbol: Trading symbol
            analysis: AI-generated analysis
            email_address: Recipient email address
        """
        # Placeholder for email functionality
        print(f"[EMAIL ALERT] Email alerts not yet implemented (would send to {email_address})")


if __name__ == "__main__":
    print("="*80)
    print("ALERT SYSTEM - Manual Test")
    print("="*80)
    
    # Test alert system
    alert_system = AlertSystem()
    
    # Create sample pattern data
    sample_pattern = {
        'pattern': 'hammer',
        'signal': 100,
        'confidence': 0.85,
        'direction': 'long',
        'regime': 'strong_uptrend',
        'regime_confidence': 0.92,
        'timestamp': datetime.now(),
        'ohlcv': {
            'open': 87500.00,
            'high': 88000.00,
            'low': 87200.00,
            'close': 87800.00,
            'volume': 1500.50
        },
        'confirmations': {
            'trend': True,
            'momentum': True,
            'volume': True
        },
        'parameters': {
            'stop_loss_pct': 0.25,
            'profit_target_pct': 0.12,
            'trailing_activation_pct': 0.10,
            'trailing_offset_pct': 0.08,
            'min_profit_pct': 0.04,
            'max_holding_period': 48
        }
    }
    
    print("\n[TEST] Sending test alert...")
    result = alert_system.send_alert(sample_pattern, 'BTCUSDT', include_ai_analysis=True)
    
    print(f"\n[TEST] Alert sent successfully!")
    print(f"[TEST] Timestamp: {result['alert_timestamp']}")

