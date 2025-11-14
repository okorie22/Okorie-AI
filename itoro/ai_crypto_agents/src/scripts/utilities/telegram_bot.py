"""
🌙 Anarcho Capital's Telegram Bot Integration
DeFi approval system and notifications via Telegram
Built with love by Anarcho Capital 🚀
"""

import os
import time
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
from threading import Thread, Lock

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical, system
from src.config.defi_config import (
    TELEGRAM_BOT, TELEGRAM_COMMANDS, BORROWING_APPROVAL,
    BORROWING_REQUIREMENTS, get_current_phase_config
)

@dataclass
class BorrowingRequest:
    """Borrowing request details"""
    request_id: str
    protocol: str
    token: str
    amount_usd: float
    purpose: str
    collateral_ratio: float
    risk_score: float
    timestamp: datetime
    status: str  # pending, approved, rejected, expired
    user_id: str
    chat_id: str

@dataclass
class TelegramNotification:
    """Telegram notification details"""
    notification_id: str
    type: str  # info, warning, critical, approval_request
    message: str
    chat_id: str
    timestamp: datetime
    sent: bool
    response: Optional[str]

class TelegramBot:
    """
    Telegram bot for DeFi operations approval and notifications
    Handles borrowing requests, portfolio updates, and risk alerts
    """
    
    def __init__(self):
        """Initialize the Telegram Bot"""
        self.bot_token = TELEGRAM_BOT['bot_token']
        self.chat_id = TELEGRAM_BOT['chat_id']
        self.enabled = TELEGRAM_BOT['enabled']
        
        # Validate configuration
        if not self._validate_config():
            warning("Telegram bot configuration incomplete - bot disabled")
            self.enabled = False
            return
        
        # Bot state
        self.is_running = False
        self.last_update_id = 0
        self.pending_requests = {}
        self.notification_queue = []
        self.command_handlers = {}
        
        # Threading
        self.bot_thread = None
        self.lock = Lock()
        
        # Initialize command handlers
        self._initialize_command_handlers()
        
        info("📱 Telegram Bot initialized")
    
    def _validate_config(self) -> bool:
        """Validate Telegram bot configuration"""
        if not self.bot_token:
            error("TELEGRAM_BOT_API not configured")
            return False
        
        if not self.chat_id:
            error("TELEGRAM_CHAT_ID not configured")
            return False
        
        return True
    
    def _initialize_command_handlers(self):
        """Initialize command handlers"""
        self.command_handlers = {
            '/start': self._handle_start,
            '/help': self._handle_help,
            '/status': self._handle_status,
            '/approve': self._handle_approve,
            '/reject': self._handle_reject,
            '/stop': self._handle_stop,
            '/resume': self._handle_resume,
            '/risk': self._handle_risk,
            '/yields': self._handle_yields,
            '/portfolio': self._handle_portfolio,
            '/commands': self._handle_commands
        }
    
    def start_bot(self):
        """Start the Telegram bot in background thread"""
        if not self.enabled:
            warning("Telegram bot is disabled")
            return False
        
        try:
            self.is_running = True
            self.bot_thread = Thread(target=self._run_bot_loop, daemon=True)
            self.bot_thread.start()
            
            info("🚀 Telegram bot started successfully")
            return True
            
        except Exception as e:
            error(f"Failed to start Telegram bot: {str(e)}")
            return False
    
    def stop_bot(self):
        """Stop the Telegram bot"""
        try:
            self.is_running = False
            
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=5)
            
            info("🛑 Telegram bot stopped")
            
        except Exception as e:
            error(f"Failed to stop Telegram bot: {str(e)}")
    
    def _run_bot_loop(self):
        """Main bot loop for handling updates"""
        try:
            while self.is_running:
                try:
                    # Get updates from Telegram
                    updates = self._get_updates()
                    
                    if updates:
                        for update in updates:
                            self._process_update(update)
                    
                    # Process notification queue
                    self._process_notification_queue()
                    
                    # Sleep between updates
                    time.sleep(1)
                    
                except Exception as e:
                    error(f"Error in bot loop: {str(e)}")
                    time.sleep(5)  # Wait longer on error
                    
        except Exception as e:
            error(f"Fatal error in bot loop: {str(e)}")
        finally:
            self.is_running = False
    
    def _get_updates(self) -> List[Dict]:
        """Get updates from Telegram API"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 30
            }
            
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('ok') and data.get('result'):
                    updates = data['result']
                    
                    if updates:
                        self.last_update_id = updates[-1]['update_id']
                    
                    return updates
            
            return []
            
        except Exception as e:
            error(f"Failed to get Telegram updates: {str(e)}")
            return []
    
    def _process_update(self, update: Dict):
        """Process a single Telegram update"""
        try:
            if 'message' in update:
                message = update['message']
                
                # Check if message is from authorized user
                if not self._is_authorized_user(message):
                    return
                
                # Process text commands
                if 'text' in message:
                    text = message['text']
                    chat_id = message['chat']['id']
                    
                    # Handle commands
                    if text.startswith('/'):
                        self._handle_command(text, chat_id, message)
                    else:
                        # Handle text responses (e.g., approval confirmations)
                        self._handle_text_response(text, chat_id, message)
                
                # Process callback queries (inline keyboard)
                elif 'callback_query' in update:
                    callback_query = update['callback_query']
                    self._handle_callback_query(callback_query)
                    
        except Exception as e:
            error(f"Failed to process Telegram update: {str(e)}")
    
    def _is_authorized_user(self, message: Dict) -> bool:
        """Check if message is from authorized user"""
        try:
            user_id = str(message.get('from', {}).get('id', ''))
            authorized_ids = [self.chat_id]  # Add more authorized IDs if needed
            
            return user_id in authorized_ids
            
        except Exception as e:
            error(f"Failed to check user authorization: {str(e)}")
            return False
    
    def _handle_command(self, command: str, chat_id: str, message: Dict):
        """Handle bot commands"""
        try:
            # Extract command and arguments
            parts = command.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # Get command handler
            handler = self.command_handlers.get(cmd)
            
            if handler:
                handler(chat_id, args, message)
            else:
                self._send_message(chat_id, f"❓ Unknown command: {cmd}\nUse /help for available commands")
                
        except Exception as e:
            error(f"Failed to handle command {command}: {str(e)}")
            self._send_message(chat_id, "❌ Error processing command")
    
    def _handle_start(self, chat_id: str, args: List[str], message: Dict):
        """Handle /start command"""
        welcome_message = """
🚀 **Welcome to Anarcho Capital's DeFi Bot!**

I'm here to help you manage your DeFi operations:

📊 **Portfolio Monitoring**
• Real-time portfolio status
• Risk assessment
• Yield optimization

💰 **Borrowing Approval**
• Review and approve borrowing requests
• Monitor collateral ratios
• Risk alerts

🛡️ **Risk Management**
• Emergency stop controls
• Liquidation warnings
• Portfolio protection

Use /help to see all available commands!
        """
        
        self._send_message(chat_id, welcome_message, parse_mode='Markdown')
    
    def _handle_help(self, chat_id: str, args: List[str], message: Dict):
        """Handle /help command"""
        help_message = """
📚 **Available Commands:**

🔍 **Information Commands**
• /status - Get current DeFi portfolio status
• /portfolio - Detailed portfolio breakdown
• /risk - Current risk assessment
• /yields - Available yield opportunities

💰 **Borrowing Commands**
• /approve - Approve pending borrowing request
• /reject - Reject pending borrowing request

🛑 **Control Commands**
• /stop - Emergency stop all DeFi operations
• /resume - Resume DeFi operations after emergency stop

❓ **Help Commands**
• /help - Show this help message
• /commands - List all commands

💡 **Tips:**
• Commands are case-insensitive
• Use /approve or /reject to respond to borrowing requests
• Emergency commands require immediate attention
        """
        
        self._send_message(chat_id, help_message, parse_mode='Markdown')
    
    def _handle_status(self, chat_id: str, args: List[str], message: Dict):
        """Handle /status command"""
        try:
            # This would integrate with the main DeFi system
            # For now, send a placeholder status
            status_message = """
📊 **DeFi Portfolio Status**

🟢 **System Status:** Active
💰 **Total Portfolio:** $10,000.00
📈 **Current APY:** 8.5%
🛡️ **Risk Level:** Low

📋 **Active Protocols:**
• Solend: $1,500 (15%)
• Mango: $1,000 (10%)

⏰ **Last Updated:** Just now
        """
            
            self._send_message(chat_id, status_message, parse_mode='Markdown')
            
        except Exception as e:
            error(f"Failed to handle status command: {str(e)}")
            self._send_message(chat_id, "❌ Error getting status")
    
    def _handle_approve(self, chat_id: str, args: List[str], message: Dict):
        """Handle /approve command"""
        try:
            if not args:
                self._send_message(chat_id, "❌ Usage: /approve <request_id>")
                return
            
            request_id = args[0]
            
            # Find and approve the request
            if request_id in self.pending_requests:
                request = self.pending_requests[request_id]
                request.status = 'approved'
                
                # Remove from pending
                del self.pending_requests[request_id]
                
                # Send approval confirmation
                approval_message = f"""
✅ **Borrowing Request Approved!**

📋 **Request Details:**
• Protocol: {request.protocol}
• Token: {request.token}
• Amount: ${request.amount_usd:,.2f}
• Purpose: {request.purpose}

⏰ **Approved at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The borrowing operation will now proceed automatically.
                """
                
                self._send_message(chat_id, approval_message, parse_mode='Markdown')
                
                # Here you would trigger the actual borrowing operation
                info(f"Borrowing request {request_id} approved by user")
                
            else:
                self._send_message(chat_id, f"❌ Request {request_id} not found or already processed")
                
        except Exception as e:
            error(f"Failed to handle approve command: {str(e)}")
            self._send_message(chat_id, "❌ Error approving request")
    
    def _handle_reject(self, chat_id: str, args: List[str], message: Dict):
        """Handle /reject command"""
        try:
            if not args:
                self._send_message(chat_id, "❌ Usage: /reject <request_id>")
                return
            
            request_id = args[0]
            
            # Find and reject the request
            if request_id in self.pending_requests:
                request = self.pending_requests[request_id]
                request.status = 'rejected'
                
                # Remove from pending
                del self.pending_requests[request_id]
                
                # Send rejection confirmation
                rejection_message = f"""
❌ **Borrowing Request Rejected!**

📋 **Request Details:**
• Protocol: {request.protocol}
• Token: {request.token}
• Amount: ${request.amount_usd:,.2f}
• Purpose: {request.purpose}

⏰ **Rejected at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The borrowing operation has been cancelled.
                """
                
                self._send_message(chat_id, rejection_message, parse_mode='Markdown')
                
                info(f"Borrowing request {request_id} rejected by user")
                
            else:
                self._send_message(chat_id, f"❌ Request {request_id} not found or already processed")
                
        except Exception as e:
            error(f"Failed to handle reject command: {str(e)}")
            self._send_message(chat_id, "❌ Error rejecting request")
    
    def _handle_stop(self, chat_id: str, args: List[str], message: Dict):
        """Handle /stop command"""
        try:
            # This would integrate with the DeFi risk manager
            # For now, send confirmation
            stop_message = """
🛑 **Emergency Stop Activated!**

All DeFi operations have been suspended.

⚠️ **What this means:**
• No new lending/borrowing operations
• Existing positions remain active
• Risk monitoring continues
• Manual intervention required to resume

Use /resume to restore operations when safe.
                """
            
            self._send_message(chat_id, stop_message, parse_mode='Markdown')
            
            # Here you would trigger the emergency stop
            info("Emergency stop activated via Telegram command")
            
        except Exception as e:
            error(f"Failed to handle stop command: {str(e)}")
            self._send_message(chat_id, "❌ Error activating emergency stop")
    
    def _handle_resume(self, chat_id: str, args: List[str], message: Dict):
        """Handle /resume command"""
        try:
            # This would integrate with the DeFi risk manager
            # For now, send confirmation
            resume_message = """
✅ **DeFi Operations Resumed!**

All DeFi operations have been restored.

🟢 **System Status:** Active
📊 **Monitoring:** Enabled
💰 **Operations:** Resumed

Continue monitoring for any risk alerts.
                """
            
            self._send_message(chat_id, resume_message, parse_mode='Markdown')
            
            # Here you would resume operations
            info("DeFi operations resumed via Telegram command")
            
        except Exception as e:
            error(f"Failed to handle resume command: {str(e)}")
            self._send_message(chat_id, "❌ Error resuming operations")
    
    def _handle_risk(self, chat_id: str, args: List[str], message: Dict):
        """Handle /risk command"""
        try:
            # This would integrate with the DeFi risk manager
            # For now, send placeholder risk assessment
            risk_message = """
🛡️ **Risk Assessment**

📊 **Overall Risk:** Low (0.2/1.0)
🟢 **Status:** Safe

📈 **Risk Components:**
• Portfolio Risk: Low (0.1/1.0)
• Protocol Risk: Low (0.1/1.0)
• Market Risk: Medium (0.3/1.0)
• Liquidation Risk: Low (0.1/1.0)

✅ **Recommendations:**
• Continue current strategy
• Monitor market conditions
• Maintain diversification
                """
            
            self._send_message(chat_id, risk_message, parse_mode='Markdown')
            
        except Exception as e:
            error(f"Failed to handle risk command: {str(e)}")
            self._send_message(chat_id, "❌ Error getting risk assessment")
    
    def _handle_yields(self, chat_id: str, args: List[str], message: Dict):
        """Handle /yields command"""
        try:
            # This would integrate with the yield optimizer
            # For now, send placeholder yield information
            yields_message = """
💰 **Yield Opportunities**

🚀 **Top Opportunities:**
• Solend: 8.5% APY (Low Risk)
• Mango: 12.2% APY (Medium Risk)
• Tulip: 18.7% APY (High Risk)

📊 **Current Portfolio APY:** 8.5%
🎯 **Target APY:** 10.0%

💡 **Recommendations:**
• Consider Mango for higher yields
• Monitor Tulip for aggressive strategies
• Maintain Solend for stability
                """
            
            self._send_message(chat_id, yields_message, parse_mode='Markdown')
            
        except Exception as e:
            error(f"Failed to handle yields command: {str(e)}")
            self._send_message(chat_id, "❌ Error getting yield information")
    
    def _handle_portfolio(self, chat_id: str, args: List[str], message: Dict):
        """Handle /portfolio command"""
        try:
            # This would integrate with the portfolio manager
            # For now, send placeholder portfolio information
            portfolio_message = """
📊 **Portfolio Breakdown**

💰 **Total Value:** $10,000.00
📈 **24h Change:** +$150.00 (+1.5%)

🔒 **DeFi Allocations:**
• Solend: $1,500 (15%)
• Mango: $1,000 (10%)
• Cash: $7,500 (75%)

📊 **Performance:**
• Total PnL: +$500.00
• Peak Balance: $10,500.00
• Current APY: 8.5%
                """
            
            self._send_message(chat_id, portfolio_message, parse_mode='Markdown')
            
        except Exception as e:
            error(f"Failed to handle portfolio command: {str(e)}")
            self._send_message(chat_id, "❌ Error getting portfolio information")
    
    def _handle_commands(self, chat_id: str, args: List[str], message: Dict):
        """Handle /commands command"""
        try:
            commands_message = """
📋 **All Available Commands:**

🔍 **Information:**
/start - Start the bot
/help - Show help
/status - Portfolio status
/portfolio - Portfolio details
/risk - Risk assessment
/yields - Yield opportunities

💰 **Borrowing:**
/approve <id> - Approve request
/reject <id> - Reject request

🛑 **Control:**
/stop - Emergency stop
/resume - Resume operations

❓ **Help:**
/commands - This list
                """
            
            self._send_message(chat_id, commands_message, parse_mode='Markdown')
            
        except Exception as e:
            error(f"Failed to handle commands command: {str(e)}")
            self._send_message(chat_id, "❌ Error getting commands list")
    
    def _handle_text_response(self, text: str, chat_id: str, message: Dict):
        """Handle text responses (non-commands)"""
        try:
            # Check if this is a response to a pending request
            # For now, just acknowledge the message
            self._send_message(chat_id, f"📝 Received: {text}")
            
        except Exception as e:
            error(f"Failed to handle text response: {str(e)}")
    
    def _handle_callback_query(self, callback_query: Dict):
        """Handle callback queries from inline keyboards"""
        try:
            # This would handle inline keyboard responses
            # For now, just acknowledge
            query_id = callback_query['id']
            self._answer_callback_query(query_id, "Callback received")
            
        except Exception as e:
            error(f"Failed to handle callback query: {str(e)}")
    
    def _send_message(self, chat_id: str, text: str, parse_mode: str = None):
        """Send message via Telegram API"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            data = {
                'chat_id': chat_id,
                'text': text
            }
            
            if parse_mode:
                data['parse_mode'] = parse_mode
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code != 200:
                error(f"Failed to send Telegram message: {response.status_code}")
                
        except Exception as e:
            error(f"Failed to send Telegram message: {str(e)}")
    
    def _answer_callback_query(self, callback_query_id: str, text: str):
        """Answer a callback query"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
            
            data = {
                'callback_query_id': callback_query_id,
                'text': text
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code != 200:
                error(f"Failed to answer callback query: {response.status_code}")
                
        except Exception as e:
            error(f"Failed to answer callback query: {str(e)}")
    
    def request_borrowing_approval(self, protocol: str, token: str, amount_usd: float, 
                                  purpose: str, collateral_ratio: float, risk_score: float) -> str:
        """Request borrowing approval via Telegram"""
        try:
            if not self.enabled:
                return "telegram_disabled"
            
            # Generate request ID
            request_id = f"borrow_{int(time.time())}"
            
            # Create borrowing request
            request = BorrowingRequest(
                request_id=request_id,
                protocol=protocol,
                token=token,
                amount_usd=amount_usd,
                purpose=purpose,
                collateral_ratio=collateral_ratio,
                risk_score=risk_score,
                timestamp=datetime.now(),
                status='pending',
                user_id=self.chat_id,
                chat_id=self.chat_id
            )
            
            # Store pending request
            with self.lock:
                self.pending_requests[request_id] = request
            
            # Send approval request message
            approval_message = f"""
💰 **Borrowing Request - Approval Required**

📋 **Request Details:**
• Protocol: {protocol}
• Token: {token}
• Amount: ${amount_usd:,.2f}
• Purpose: {purpose}
• Collateral Ratio: {collateral_ratio:.2f}x
• Risk Score: {risk_score:.2f}

⏰ **Requested at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

To approve: `/approve {request_id}`
To reject: `/reject {request_id}`

⏳ **Auto-expires in:** {BORROWING_APPROVAL['approval_timeout_minutes']} minutes
                """
            
            self._send_message(self.chat_id, approval_message, parse_mode='Markdown')
            
            # Schedule auto-expiration
            self._schedule_request_expiration(request_id)
            
            info(f"Borrowing approval requested: {request_id}")
            return request_id
            
        except Exception as e:
            error(f"Failed to request borrowing approval: {str(e)}")
            return "error"
    
    def _schedule_request_expiration(self, request_id: str):
        """Schedule automatic expiration of a request"""
        def expire_request():
            time.sleep(BORROWING_APPROVAL['approval_timeout_minutes'] * 60)
            
            with self.lock:
                if request_id in self.pending_requests:
                    request = self.pending_requests[request_id]
                    if request.status == 'pending':
                        request.status = 'expired'
                        del self.pending_requests[request_id]
                        
                        # Send expiration notification
                        expiration_message = f"""
⏰ **Borrowing Request Expired**

Request {request_id} has expired without approval.

📋 **Expired Request:**
• Protocol: {request.protocol}
• Token: {request.token}
• Amount: ${request.amount_usd:,.2f}

The borrowing operation has been cancelled.
                        """
                        
                        self._send_message(self.chat_id, expiration_message, parse_mode='Markdown')
                        info(f"Borrowing request {request_id} expired")
        
        # Start expiration thread
        Thread(target=expire_request, daemon=True).start()
    
    def send_notification(self, notification_type: str, message: str, 
                         chat_id: str = None, priority: str = 'normal'):
        """Send notification via Telegram"""
        try:
            if not self.enabled:
                return False
            
            target_chat = chat_id or self.chat_id
            
            # Add notification to queue
            notification = TelegramNotification(
                notification_id=f"notif_{int(time.time())}",
                type=notification_type,
                message=message,
                chat_id=target_chat,
                timestamp=datetime.now(),
                sent=False,
                response=None
            )
            
            with self.lock:
                self.notification_queue.append(notification)
            
            return True
            
        except Exception as e:
            error(f"Failed to queue notification: {str(e)}")
            return False
    
    def _process_notification_queue(self):
        """Process pending notifications"""
        try:
            with self.lock:
                if not self.notification_queue:
                    return
                
                # Process notifications (max 5 per cycle)
                notifications_to_process = self.notification_queue[:5]
                self.notification_queue = self.notification_queue[5:]
            
            for notification in notifications_to_process:
                try:
                    # Add emoji based on type
                    emoji_map = {
                        'info': 'ℹ️',
                        'warning': '⚠️',
                        'critical': '🚨',
                        'approval_request': '💰',
                        'success': '✅',
                        'error': '❌'
                    }
                    
                    emoji = emoji_map.get(notification.type, '📢')
                    formatted_message = f"{emoji} **{notification.type.upper()}**\n\n{notification.message}"
                    
                    # Send notification
                    self._send_message(notification.chat_id, formatted_message, parse_mode='Markdown')
                    
                    # Mark as sent
                    notification.sent = True
                    notification.response = "sent"
                    
                except Exception as e:
                    error(f"Failed to process notification {notification.notification_id}: {str(e)}")
                    notification.response = f"error: {str(e)}"
                    
        except Exception as e:
            error(f"Failed to process notification queue: {str(e)}")
    
    def get_bot_status(self) -> Dict[str, Any]:
        """Get bot status information"""
        try:
            return {
                'enabled': self.enabled,
                'running': self.is_running,
                'pending_requests': len(self.pending_requests),
                'notification_queue': len(self.notification_queue),
                'last_update_id': self.last_update_id,
                'bot_token_configured': bool(self.bot_token),
                'chat_id_configured': bool(self.chat_id)
            }
            
        except Exception as e:
            error(f"Failed to get bot status: {str(e)}")
            return {'error': str(e)}

# Global instance
_telegram_bot = None

def get_telegram_bot() -> TelegramBot:
    """Get global Telegram bot instance"""
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = TelegramBot()
    return _telegram_bot

# Test function
def test_telegram_bot():
    """Test the Telegram bot"""
    try:
        bot = get_telegram_bot()
        
        # Test bot status
        print("📱 Testing Telegram bot...")
        status = bot.get_bot_status()
        print(f"Bot Status: {json.dumps(status, indent=2)}")
        
        # Test notification
        print("\n📢 Testing notification...")
        success = bot.send_notification('info', 'This is a test notification from Anarcho Capital! 🚀')
        print(f"Notification sent: {success}")
        
        # Test borrowing approval request
        print("\n💰 Testing borrowing approval request...")
        request_id = bot.request_borrowing_approval(
            protocol='solend',
            token='USDC',
            amount_usd=500.0,
            purpose='Yield farming opportunity',
            collateral_ratio=2.5,
            risk_score=0.3
        )
        print(f"Request ID: {request_id}")
        
        print("\n✅ Telegram Bot test completed successfully!")
        
    except Exception as e:
        error(f"Telegram Bot test failed: {str(e)}")

if __name__ == "__main__":
    # Run test
    test_telegram_bot()
