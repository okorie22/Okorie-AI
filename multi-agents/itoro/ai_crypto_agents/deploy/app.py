#!/usr/bin/env python3

# CRITICAL: Auto-reset MUST happen BEFORE any Python imports
import os
import sys
import subprocess

# Add parent directory to path for imports
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

# Auto-reset paper trading database BEFORE any imports
try:
    # Read config directly to check if reset is enabled
    config_path = os.path.join(root_dir, 'src', 'config.py')
    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
        config_content = f.read()
    
    # Check if PAPER_TRADING_RESET_ON_START = True
    if 'PAPER_TRADING_RESET_ON_START = True' in config_content:
        print("🔄 Paper trading reset enabled - initializing robust reset...")
        
        # Use the new database reset manager for robust connection cleanup
        try:
            # Add the src directory to path for imports
            sys.path.insert(0, os.path.join(root_dir, 'src'))
            from scripts.database.database_reset_manager import reset_paper_trading_database
            
            if reset_paper_trading_database():
                print("✅ Paper trading DB auto-reset completed successfully")
            else:
                print("⚠️ Paper trading DB auto-reset failed - continuing with existing database")
        except ImportError as e:
            print(f"⚠️ Database reset manager not available: {e}")
            # Fallback to simple file deletion
            db_path = os.path.join(root_dir, 'data', 'paper_trading.db')
            if os.path.exists(db_path):
                try:
                    import stat
                    os.chmod(db_path, stat.S_IWRITE)
                    os.remove(db_path)
                    print("🧹 Paper trading DB auto-reset completed (fallback method)")
                except Exception as fallback_error:
                    print(f"⚠️ Could not reset DB (fallback): {fallback_error}")
            else:
                print("📝 No paper trading DB found to reset")
        except Exception as e:
            print(f"⚠️ Reset failed: {e}")
    else:
        print("📝 Paper trading reset disabled in config")
except Exception as e:
    print(f"⚠️ Reset check failed: {e}")

# NOW import everything else
import logging
from src.scripts.webhooks.webhook_handler import app, sync_webhook_addresses_with_config, auto_update_helius_webhook, get_current_wallets_to_track

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log environment variables (without sensitive values)
logger.info("Starting webhook handler app")
logger.info(f"Environment check: PORT={os.environ.get('PORT', 'not set')}")
logger.info(f"RPC_ENDPOINT: {'configured' if os.environ.get('RPC_ENDPOINT') else 'not configured'}")
logger.info(f"HELIUS_API_KEY: {'configured' if os.environ.get('HELIUS_API_KEY') else 'not configured'}")

# DEBUG: Check WebSocket endpoints
websocket_endpoint = os.environ.get('WEBSOCKET_ENDPOINT')
quicknode_wss = os.environ.get('QUICKNODE_WSS_ENDPOINT')
logger.info(f"WEBSOCKET_ENDPOINT: {'configured' if websocket_endpoint else 'not configured'}")
logger.info(f"QUICKNODE_WSS_ENDPOINT: {'configured' if quicknode_wss else 'not configured'}")

if websocket_endpoint:
    logger.info(f"Helius WebSocket: {websocket_endpoint[:50]}...")
if quicknode_wss:
    logger.info(f"QuickNode WebSocket: {quicknode_wss[:50]}...")

if __name__ == "__main__":
    # Get port from environment (for Render compatibility)
    port = int(os.environ.get("PORT", 10000))
    
    # Log startup
    logger.info(f"Starting Flask server on port {port}")
    
    # Ensure wallets.json equals config (config + personal) and auto-sync Helius addresses
    try:
        # Force-load and sync wallets.json from config
        _ = get_current_wallets_to_track()

        # Sync Helius webhook URL/addresses per environment
        helius_api_key = os.environ.get('HELIUS_API_KEY')
        if helius_api_key:
            # Only update to local IP when not on Render
            if not os.environ.get('RENDER') and not os.environ.get('RENDER_SERVICE_NAME'):
                if auto_update_helius_webhook():
                    logger.info("✅ Webhook URL auto-updated for local development")
                else:
                    logger.warning("⚠️ Failed to auto-update webhook URL for local development")

            if sync_webhook_addresses_with_config():
                logger.info("✅ Helius webhook addresses synced with config on startup")
            else:
                logger.warning("⚠️ Failed to sync Helius webhook addresses on startup")
        else:
            logger.warning("⚠️ HELIUS_API_KEY not configured - skipping webhook sync")
    except Exception as e:
        logger.warning(f"⚠️ Startup sync encountered an issue: {e}")
    
    # Start Flask development server (Windows compatible)
    logger.info(f"🚀 Starting Flask server on {port}")
    app.run(host='0.0.0.0', port=port, debug=False) 