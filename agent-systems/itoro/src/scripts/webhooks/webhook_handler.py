"""
Simplified Webhook Handler - Event Parser & Forwarder Only
Parses Helius transactions and forwards to local copybot via HTTP
"""

import json
import logging
import time
import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime
from typing import Dict, List, Optional

from .webhook_config import (
    HELIUS_API_KEY,
    WALLETS_TO_TRACK,
)

# Flask app
app = Flask(__name__)
logger = logging.getLogger(__name__)

# Configuration
CLOUD_DB_FALLBACK = True  # Enable cloud DB as fallback
HTTP_TIMEOUT = 5  # seconds

# Dynamic webhook URL - will be set on startup
LOCAL_COPYBOT_URL = None
_webhook_url_cache = None
_webhook_url_cache_time = 0
CACHE_DURATION = 120  # 2 minutes cache

def get_ngrok_url_from_api() -> Optional[str]:
    """Get ngrok URL by querying the ngrok API directly"""
    try:
        import requests
        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        if response.status_code == 200:
            tunnels = response.json()
            for tunnel in tunnels.get('tunnels', []):
                if tunnel.get('proto') == 'https':
                    ngrok_url = tunnel.get('public_url')
                    if ngrok_url:
                        logger.info(f"🎯 Retrieved ngrok URL via API: {ngrok_url}")
                        return ngrok_url
        logger.info("🔍 No active ngrok tunnel found via API")
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to check ngrok API: {e}")
        return None

def get_ngrok_tunnel_info() -> Optional[dict]:
    """Get complete ngrok tunnel information including port"""
    try:
        import requests
        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        if response.status_code == 200:
            tunnels = response.json()
            for tunnel in tunnels.get('tunnels', []):
                if tunnel.get('proto') == 'https':
                    config = tunnel.get('config', {})
                    addr = config.get('addr', '')
                    # Extract port from addr (e.g., "localhost:8080" -> "8080")
                    port = '8080'  # default
                    if ':' in addr:
                        port = addr.split(':')[-1]
                    
                    return {
                        'public_url': tunnel.get('public_url'),
                        'config': config,
                        'port': port
                    }
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to get ngrok tunnel info: {e}")
        return None

def get_dynamic_webhook_url() -> Optional[str]:
    """Get the dynamic webhook URL from environment variable, database ngrok_url, ngrok API, or registered IP"""
    global LOCAL_COPYBOT_URL, _webhook_url_cache, _webhook_url_cache_time
    
    # Check cache first
    current_time = time.time()
    if (_webhook_url_cache and 
        (current_time - _webhook_url_cache_time) < CACHE_DURATION):
        return _webhook_url_cache
    
    # Priority 1: Check environment variable first
    env_url = os.environ.get('LOCAL_WEBHOOK_URL')
    if env_url:
        # Ensure it has /webhook suffix if missing
        if not env_url.endswith('/webhook'):
            env_url = f"{env_url.rstrip('/')}/webhook"
        
        logger.info(f"🌐 Using webhook URL from environment: {env_url}")
        
        # Update cache
        _webhook_url_cache = env_url
        _webhook_url_cache_time = current_time
        LOCAL_COPYBOT_URL = env_url
        
        return env_url
    
    # Priority 2: Check database for ngrok_url field
    try:
        from src.scripts.database.cloud_database import get_cloud_database_manager
        
        db = get_cloud_database_manager()
        if not db:
            logger.warning("⚠️ Cloud database not available for webhook URL retrieval")
        else:
            registration = db.get_latest_local_ip_registration()
            if registration:
                # Check for ngrok_url first
                ngrok_url = registration.get('ngrok_url')
                if ngrok_url:
                    webhook_url = f"{ngrok_url.rstrip('/')}/webhook"
                    logger.info(f"🎯 Retrieved ngrok URL from database: {webhook_url}")
                    
                    # Update cache
                    _webhook_url_cache = webhook_url
                    _webhook_url_cache_time = current_time
                    LOCAL_COPYBOT_URL = webhook_url
                    
                    return webhook_url
                
                # Fall back to IP-based URL
                ip = registration.get('public_ip') or registration.get('local_ip')
                port = registration.get('port', 8080)
                if ip:
                    url = f"http://{ip}:{port}/webhook"
                    logger.info(f"🎯 Retrieved webhook URL from database: {url}")
                    
                    # Update cache
                    _webhook_url_cache = url
                    _webhook_url_cache_time = current_time
                    LOCAL_COPYBOT_URL = url
                    
                    return url
            
            logger.warning("⚠️ No registered IP found in database")
        
    except Exception as e:
        logger.error(f"❌ Failed to get webhook URL from database: {e}")
    
    # Priority 3: Try ngrok API directly with dynamic port detection
    try:
        tunnel_info = get_ngrok_tunnel_info()
        if tunnel_info:
            ngrok_url = tunnel_info['public_url']
            detected_port = tunnel_info['port']
            
            webhook_url = f"{ngrok_url.rstrip('/')}/webhook"
            logger.info(f"🎯 Using ngrok URL from API: {webhook_url} (port: {detected_port})")
            
            # Update cache
            _webhook_url_cache = webhook_url
            _webhook_url_cache_time = current_time
            LOCAL_COPYBOT_URL = webhook_url
            
            return webhook_url
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to get ngrok URL from API: {e}")
    
    # Priority 4: Fall back to localhost (won't work from Render but good for local testing)
    logger.warning("⚠️ No webhook URL found via any method")
    return None

def initialize_webhook_url():
    """Initialize the webhook URL with automatic IP detection"""
    global LOCAL_COPYBOT_URL
    
    # Try to get webhook URL from environment first (ngrok URL)
    env_url = os.environ.get('LOCAL_WEBHOOK_URL')
    if env_url:
        # Ensure the URL ends with /webhook
        if not env_url.endswith('/webhook'):
            env_url = f"{env_url}/webhook"
        LOCAL_COPYBOT_URL = env_url
        logger.info(f"🌐 Using webhook URL from environment: {LOCAL_COPYBOT_URL}")
        return
    
    # Try dynamic detection
    dynamic_url = get_dynamic_webhook_url()
    if dynamic_url:
        LOCAL_COPYBOT_URL = dynamic_url
        logger.info(f"🎯 Using dynamic webhook URL: {LOCAL_COPYBOT_URL}")
    else:
        # Fallback to localhost (won't work from Render but good for local testing)
        LOCAL_COPYBOT_URL = "http://localhost:8080/webhook"
        logger.warning(f"⚠️ Using fallback localhost URL: {LOCAL_COPYBOT_URL}")

# Initialize webhook URL on import
initialize_webhook_url()

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Parse transaction, filter for tracked wallets, forward to local copybot"""
    try:
        # Get raw webhook data from Helius
        raw_events = request.get_json()
        if not raw_events:
            return jsonify({"status": "error", "message": "No data"}), 400
        
        events = raw_events if isinstance(raw_events, list) else [raw_events]
        logger.info(f"Received {len(events)} webhook events")
        
        # Debug: Log the raw event structure
        if events:
            logger.info(f"🔍 DEBUG: First event keys: {list(events[0].keys()) if isinstance(events[0], dict) else 'Not a dict'}")
            logger.info(f"🔍 DEBUG: Event type: {events[0].get('type', 'unknown') if isinstance(events[0], dict) else 'unknown'}")
        
        # Parse and filter events
        parsed_events = []
        for i, event in enumerate(events):
            logger.info(f"🔍 DEBUG: Processing event {i+1}/{len(events)}")
            parsed = parse_transaction(event)
            if parsed:
                logger.info(f"🔍 DEBUG: Event {i+1} parsed successfully: {parsed.get('type', 'unknown')}")
                logger.info(f"🔍 DEBUG: Parsed accounts: {[acc.get('wallet', 'unknown') for acc in parsed.get('accounts', [])]}")
                logger.info(f"🔍 DEBUG: Parsed accounts count: {len(parsed.get('accounts', []))}")
                logger.info(f"🔍 DEBUG: Full parsed object: {parsed}")
                
                # Call the wallet transaction check
                is_tracked = is_tracked_wallet_transaction(parsed)
                logger.info(f"🔍 DEBUG: is_tracked_wallet_transaction returned: {is_tracked}")
                
                if is_tracked:
                    logger.info(f"✅ DEBUG: Event {i+1} contains tracked wallet transaction - ADDING TO PARSED_EVENTS")
                    parsed_events.append(parsed)
                    logger.info(f"🔍 DEBUG: parsed_events now has {len(parsed_events)} events")
                else:
                    logger.info(f"❌ DEBUG: Event {i+1} does not contain tracked wallet transaction")
            else:
                logger.info(f"❌ DEBUG: Event {i+1} failed to parse")
        
        logger.info(f"🔍 DEBUG: Total parsed events: {len(parsed_events)}")
        logger.info(f"🔍 DEBUG: Tracked wallets: {WALLETS_TO_TRACK}")
        
        # Debug: Show details of each parsed event
        for i, event in enumerate(parsed_events):
            logger.info(f"🔍 DEBUG: Parsed event {i+1} accounts: {[acc.get('wallet', 'unknown') for acc in event.get('accounts', [])]}")
            logger.info(f"🔍 DEBUG: Parsed event {i+1} account count: {len(event.get('accounts', []))}")
        
        # Add diagnostic logging for IP registration and forwarding (Phase 3)
        logger.info("🔍 DEBUG: Running forwarding diagnostics...")
        try:
            # Test IP registration retrieval
            webhook_url = get_dynamic_webhook_url()
            if webhook_url:
                logger.info(f"🎯 Retrieved webhook URL from database: {webhook_url}")
                logger.info(f"🔍 DEBUG: URL cached: {_webhook_url_cache is not None}")
            else:
                logger.warning("⚠️ No webhook URL available for forwarding")
        except Exception as e:
            logger.error(f"❌ IP registration lookup error: {e}")
        
        if not parsed_events:
            logger.info("⚠️ No tracked wallet events found in this webhook batch")
            logger.info("🔍 DEBUG: Skipping forwarding due to empty parsed_events")
            return jsonify({"status": "ok", "message": "No tracked wallet events"}), 200
        
        logger.info(f"Found {len(parsed_events)} tracked wallet transactions")
        
        # Try direct HTTP to local copybot first
        success = forward_to_local_copybot(parsed_events)
        
        if not success and CLOUD_DB_FALLBACK:
            # Fallback to cloud DB REST API
            save_to_cloud_database(parsed_events)
            logger.warning("Local copybot unreachable, saved to cloud DB fallback")
        
        return jsonify({
            "status": "ok",
            "processed": len(parsed_events),
            "forwarded": success
        }), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


def parse_transaction(event: Dict) -> Optional[Dict]:
    """Parse Helius webhook event into simplified copybot format"""
    try:
        logger.info(f"🔍 Parsing event - type: {event.get('type', 'unknown')}")
        logger.info(f"🔍 Transaction signature: {event.get('signature', 'unknown')}")
        
        # Extract key transaction data
        parsed = {
            'signature': event.get('signature', 'unknown'),
            'timestamp': event.get('timestamp', int(time.time())),
            'type': event.get('type', 'unknown'),
            'accounts': [],
            'parsed_at': datetime.now().isoformat()
        }
        
        # Handle new webhook format with accountData and tokenTransfers
        account_data = event.get('accountData', [])
        token_transfers = event.get('tokenTransfers', [])
        
        logger.info(f"🔍 Found {len(account_data)} account data entries")
        logger.info(f"🔍 Found {len(token_transfers)} token transfers")
        
        # Extract account addresses from accountData
        account_addresses = []
        for account in account_data:
            if 'account' in account:
                account_addresses.append(account['account'])
        
        logger.info(f"🔍 Found {len(account_addresses)} account addresses")
        
        # Parse token transfers - ONLY for tracked wallets
        tracked_accounts_found = 0
        accounts_added = 0
        
        logger.info(f"🔍 DEBUG: Starting to parse {len(token_transfers)} token transfers")
        logger.info(f"🔍 DEBUG: WALLETS_TO_TRACK: {WALLETS_TO_TRACK}")
        
        for i, transfer in enumerate(token_transfers):
            logger.info(f"🔍 DEBUG: Processing token transfer {i+1}/{len(token_transfers)}")
            
            # Extract transfer data
            from_account = transfer.get('fromUserAccount', '')
            to_account = transfer.get('toUserAccount', '')
            token_address = transfer.get('mint', '')
            amount = float(transfer.get('tokenAmount', 0) or 0)
            
            logger.info(f"🔍 DEBUG: Transfer from: {from_account[:8]}... to: {to_account[:8]}...")
            logger.info(f"🔍 DEBUG: Token: {token_address[:8]}..., amount: {amount}")
            
            # Check if either account is in our tracked wallets
            tracked_account = None
            if from_account in WALLETS_TO_TRACK:
                tracked_account = from_account
                action = 'sell'
            elif to_account in WALLETS_TO_TRACK:
                tracked_account = to_account
                action = 'buy'
            
            if tracked_account:
                tracked_accounts_found += 1
                logger.info(f"🔍 DEBUG: Found tracked account {tracked_accounts_found}: {tracked_account[:8]}...")
                
                if amount > 0:  # Only include if there's a transfer
                    logger.info(f"✅ Tracked account {tracked_accounts_found}: {tracked_account[:8]}... (token: {token_address[:8]}..., amount: {amount}, action: {action})")
                    
                    # Get balance tracking information for sell type detection
                    previous_balance = 0.0
                    sell_type = 'full'
                    sell_percentage = 100.0
                    
                    if action == 'sell':
                        try:
                            from src.scripts.webhooks.tracked_wallet_balance_cache import get_balance_cache
                            balance_cache = get_balance_cache()
                            
                            # Get previous balance
                            previous_balance = balance_cache.get_previous_balance(tracked_account, token_address)
                            
                            # Calculate new balance (previous - amount sold)
                            new_balance = max(0.0, previous_balance - amount)
                            
                            # Update balance and get sell type information
                            balance_info = balance_cache.update_balance(tracked_account, token_address, new_balance)
                            sell_type = balance_info['sell_type']
                            sell_percentage = balance_info['sell_percentage']
                            
                            logger.info(f"🔍 Balance tracking: {previous_balance:.6f} -> {new_balance:.6f} ({sell_type}, {sell_percentage:.1f}%)")
                            
                        except Exception as e:
                            logger.warning(f"⚠️ Balance tracking failed: {e}, defaulting to full sell")
                    
                    account_data = {
                        'wallet': tracked_account,
                        'token': token_address,
                        'amount': amount,
                        'action': action,
                        'from_account': from_account,
                        'to_account': to_account,
                        'previous_balance': previous_balance,  # NEW
                        'sell_type': sell_type,  # NEW: 'full', 'half', 'partial'
                        'sell_percentage': sell_percentage  # NEW: actual percentage
                    }
                    
                    logger.info(f"🔍 DEBUG: About to append account data: {account_data}")
                    parsed['accounts'].append(account_data)
                    accounts_added += 1
                    logger.info(f"🔍 DEBUG: Successfully appended account. Total accounts now: {len(parsed['accounts'])}")
                else:
                    logger.info(f"🔍 Tracked account {tracked_account[:8]}... has no token transfer amount")
            else:
                logger.info(f"🔍 DEBUG: No tracked accounts in this transfer")
        
        logger.info(f"🔍 DEBUG: Final parsing results:")
        logger.info(f"🔍 DEBUG: - Tracked accounts found: {tracked_accounts_found}")
        logger.info(f"🔍 DEBUG: - Accounts added to parsed: {accounts_added}")
        logger.info(f"🔍 DEBUG: - Final parsed['accounts'] length: {len(parsed['accounts'])}")
        logger.info(f"🔍 DEBUG: - Final parsed['accounts'] content: {parsed['accounts']}")
        
        logger.info(f"🔍 Parsed {len(parsed['accounts'])} accounts from transaction")
        return parsed if parsed['accounts'] else None
        
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return None


def is_tracked_wallet_transaction(parsed: Dict) -> bool:
    """Check if transaction involves tracked whale wallets only"""
    # Since we now filter at parsing level, all parsed accounts are tracked wallets
    account_wallets = [account['wallet'] for account in parsed.get('accounts', [])]
    logger.info(f"🔍 DEBUG: is_tracked_wallet_transaction called with accounts: {account_wallets}")
    logger.info(f"🔍 DEBUG: Parsed accounts length: {len(parsed.get('accounts', []))}")
    logger.info(f"🔍 DEBUG: Tracked wallets: {WALLETS_TO_TRACK}")
    
    # If we have any accounts, they're all tracked (due to parsing filter)
    if account_wallets:
        logger.info(f"✅ Transaction contains {len(account_wallets)} tracked wallet(s)")
        return True
    
    logger.info("❌ No accounts found in parsed transaction")
    return False


def forward_to_local_copybot(events: List[Dict]) -> bool:
    """Forward parsed events to local copybot via HTTP"""
    global LOCAL_COPYBOT_URL
    
    # Get dynamic webhook URL if not set or cache expired
    if not LOCAL_COPYBOT_URL:
        dynamic_url = get_dynamic_webhook_url()
        if not dynamic_url:
            logger.error("❌ No webhook URL available for forwarding")
            return False
        LOCAL_COPYBOT_URL = dynamic_url
    
    try:
        logger.info(f"🔄 Forwarding {len(events)} events to {LOCAL_COPYBOT_URL}")
        
        response = requests.post(
            LOCAL_COPYBOT_URL,
            json={'events': events},
            timeout=HTTP_TIMEOUT,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully forwarded {len(events)} events to local copybot")
            return True
        else:
            logger.warning(f"⚠️ Local copybot returned {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.warning("⏰ Local copybot timeout")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"🔌 Local copybot connection refused: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Forward error: {e}")
        return False


def save_to_cloud_database(events: List[Dict]) -> bool:
    """Save events to cloud DB as fallback (REST API)"""
    try:
        # Note: Cloud database functionality disabled for simplified deployment
        # This would normally save to cloud database as fallback
        logger.info(f"Cloud DB fallback called for {len(events)} events (disabled in simplified mode)")
        return True
        
    except Exception as e:
        logger.error(f"Cloud DB fallback failed: {e}")
        return False


@app.route('/health', methods=['GET'])
def health_check():
    """Enhanced health check endpoint with full diagnostics"""
    try:
        logger.info("🔍 Health check requested - running full diagnostics")
        
        # Get diagnostic information
        diagnostics = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "ip_registration": {},
            "forwarding_test": {},
            "tracked_wallets": list(WALLETS_TO_TRACK)
        }
        
        # Test IP registration retrieval
        logger.info("🔍 Testing IP registration retrieval...")
        try:
            webhook_url = get_dynamic_webhook_url()
            if webhook_url:
                diagnostics["ip_registration"] = {
                    "status": "success",
                    "webhook_url": webhook_url,
                    "cached": _webhook_url_cache is not None
                }
                logger.info(f"✅ IP registration successful: {webhook_url}")
            else:
                diagnostics["ip_registration"] = {
                    "status": "failed",
                    "error": "No webhook URL retrieved from database"
                }
                logger.warning("❌ IP registration failed - no webhook URL found")
        except Exception as e:
            diagnostics["ip_registration"] = {
                "status": "error",
                "error": str(e)
            }
            logger.error(f"❌ IP registration error: {e}")
        
        # Test forwarding to local server
        logger.info("🔍 Testing forwarding to local server...")
        try:
            if webhook_url:
                # Create a test event for forwarding
                test_events = [{
                    "signature": "health_check_test",
                    "timestamp": int(time.time()),
                    "type": "health_check",
                    "accounts": [],
                    "parsed_at": datetime.now().isoformat()
                }]
                
                logger.info(f"🔄 Attempting test forwarding to {webhook_url}")
                success = forward_to_local_copybot(test_events)
                
                diagnostics["forwarding_test"] = {
                    "status": "success" if success else "failed",
                    "webhook_url": webhook_url,
                    "connection_attempted": True,
                    "result": "Connected successfully" if success else "Connection failed"
                }
                
                if success:
                    logger.info("✅ Local server reachable")
                else:
                    logger.warning("❌ Local server connection failed")
            else:
                diagnostics["forwarding_test"] = {
                    "status": "skipped",
                    "reason": "No webhook URL available"
                }
                logger.warning("⚠️ Skipping forwarding test - no webhook URL")
                
        except Exception as e:
            diagnostics["forwarding_test"] = {
                "status": "error",
                "error": str(e)
            }
            logger.error(f"❌ Forwarding test error: {e}")
        
        # Log summary
        logger.info("🔍 Health check diagnostics complete")
        logger.info(f"📊 IP Registration: {diagnostics['ip_registration']['status']}")
        logger.info(f"📊 Forwarding Test: {diagnostics['forwarding_test']['status']}")
        logger.info(f"📊 Tracked Wallets: {len(diagnostics['tracked_wallets'])}")
        
        return jsonify(diagnostics)
        
    except Exception as e:
        logger.error(f"❌ Health check error: {e}")
        return jsonify({
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }), 500


def get_current_wallets_to_track() -> set:
    """Get current wallets to track from config"""
    try:
        from .webhook_config import WALLETS_TO_TRACK
        return set(WALLETS_TO_TRACK)
    except ImportError:
        return set()

def sync_webhook_addresses_with_config() -> bool:
    """Sync webhook addresses with config (placeholder for compatibility)"""
    try:
        # This is a simplified version - just return True for now
        # The full implementation would sync with Helius API
        logger.info("Webhook address sync called (simplified mode)")
        return True
    except Exception as e:
        logger.error(f"Webhook sync error: {e}")
        return False

def auto_update_helius_webhook() -> bool:
    """Auto-update Helius webhook (placeholder for compatibility)"""
    try:
        # This is a simplified version - just return True for now
        # The full implementation would update Helius webhook
        logger.info("Helius webhook update called (simplified mode)")
        return True
    except Exception as e:
        logger.error(f"Helius webhook update error: {e}")
        return False

def start_webhook_server():
    """Start Flask webhook server"""
    logger.info("Starting simplified webhook handler...")
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == "__main__":
    start_webhook_server()
