#!/usr/bin/env python3
"""
🌙 Anarcho Capital Trading System Health Check
Comprehensive diagnostic and repair tool for the trading system
"""

import os
import sys
import sqlite3
import json
import requests
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

def check_environment_variables():
    """Check if required environment variables are set"""
    print("🔍 Checking environment variables...")
    
    required_vars = [
        'DEFAULT_WALLET_ADDRESS',
        'HELIUS_API_KEY',
        'RPC_ENDPOINT'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            print(f"✅ {var}: {value[:8]}..." if len(value) > 8 else f"✅ {var}: {value}")
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return False
    
    return True

def check_database_integrity():
    """Check and repair database integrity issues"""
    print("\n🔍 Checking database integrity...")
    
    # Check portfolio database
    portfolio_db = os.path.join('src', 'data', 'portfolio_history.db')
    if os.path.exists(portfolio_db):
        try:
            conn = sqlite3.connect(portfolio_db)
            cursor = conn.cursor()
            
            # Check for corrupted values
            cursor.execute("""
                SELECT COUNT(*) FROM portfolio_snapshots 
                WHERE total_value_usd > 1000000 OR total_value_usd < 0
            """)
            corrupted_count = cursor.fetchone()[0]
            
            if corrupted_count > 0:
                print(f"⚠️  Found {corrupted_count} corrupted portfolio entries")
                print("🧹 Cleaning corrupted entries...")
                cursor.execute("""
                    DELETE FROM portfolio_snapshots 
                    WHERE total_value_usd > 1000000 OR total_value_usd < 0
                """)
                conn.commit()
                print("✅ Corrupted entries cleaned")
            else:
                print("✅ Portfolio database integrity OK")
            
            conn.close()
        except Exception as e:
            print(f"❌ Error checking portfolio database: {e}")
    
    # Check paper trading database
    paper_db = os.path.join('data', 'paper_trading.db')
    if os.path.exists(paper_db):
        try:
            conn = sqlite3.connect(paper_db)
            cursor = conn.cursor()
            
            # Check if paper trading is disabled but database exists
            from src.config import PAPER_TRADING_ENABLED
            if not PAPER_TRADING_ENABLED:
                print("⚠️  Paper trading disabled but database exists")
                print("🧹 Removing paper trading database...")
                conn.close()
                os.remove(paper_db)
                print("✅ Paper trading database removed")
            else:
                print("✅ Paper trading database OK")
                conn.close()
        except Exception as e:
            print(f"❌ Error checking paper trading database: {e}")

def check_webhook_status():
    """Check webhook registration status"""
    print("\n🔍 Checking webhook status...")
    
    helius_api_key = os.getenv('HELIUS_API_KEY')
    if not helius_api_key:
        print("❌ HELIUS_API_KEY not set - cannot check webhooks")
        return False
    
    try:
        # List existing webhooks
        response = requests.get(
            f"https://api.helius.xyz/v0/webhooks?api-key={helius_api_key}",
            timeout=10
        )
        
        if response.status_code == 200:
            webhooks = response.json()
            print(f"📊 Found {len(webhooks)} existing webhooks")
            
            for webhook in webhooks:
                webhook_id = webhook.get('webhookID', 'unknown')
                webhook_url = webhook.get('webhookURL', 'unknown')
                account_count = len(webhook.get('accountAddresses', []))
                print(f"  - ID: {webhook_id}, URL: {webhook_url[:50]}..., Accounts: {account_count}")
            
            if len(webhooks) >= 1:
                print("⚠️  Helius free tier webhook limit reached (1 webhook max)")
                print("💡 Consider upgrading to paid tier or deleting unused webhooks")
            
            return True
        else:
            print(f"❌ Failed to check webhooks: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking webhook status: {e}")
        return False

def check_rpc_connectivity():
    """Check RPC endpoint connectivity"""
    print("\n🔍 Checking RPC connectivity...")
    
    rpc_endpoint = os.getenv('RPC_ENDPOINT')
    if not rpc_endpoint:
        print("❌ RPC_ENDPOINT not set")
        return False
    
    try:
        # Test RPC connection with a simple request
        payload = {
            "jsonrpc": "2.0",
            "id": "health-check",
            "method": "getHealth"
        }
        
        response = requests.post(
            rpc_endpoint,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                print("✅ RPC endpoint responding correctly")
                return True
            else:
                print(f"⚠️  RPC endpoint responded but with unexpected format: {result}")
                return True  # Still functional
        elif response.status_code == 401:
            print("⚠️  RPC authentication failed - this is normal for free endpoints")
            return True  # Expected for free RPC
        else:
            print(f"❌ RPC endpoint error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ RPC connection failed: {e}")
        return False

def check_wallet_balance():
    """Check if wallet balance can be fetched"""
    print("\n🔍 Checking wallet balance access...")
    
    wallet_address = os.getenv('DEFAULT_WALLET_ADDRESS')
    if not wallet_address:
        print("❌ DEFAULT_WALLET_ADDRESS not set")
        return False
    
    try:
        # Import and test wallet data fetching
        from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
        
        coordinator = get_shared_data_coordinator()
        wallet_data = coordinator.get_personal_wallet_data()
        
        if wallet_data:
            total_value = wallet_data.total_value_usd
            token_count = len(wallet_data.tokens)
            print(f"✅ Wallet accessible: ${total_value:.2f} total value, {token_count} tokens")
            
            # Show token breakdown
            for token_addr, balance in wallet_data.tokens.items():
                if balance > 0:
                    print(f"  - {token_addr[:8]}...: {balance}")
            
            return True
        else:
            print("❌ Could not fetch wallet data")
            return False
            
    except Exception as e:
        print(f"❌ Error checking wallet balance: {e}")
        return False

def reset_portfolio_tracker():
    """Reset portfolio tracker to use live wallet data"""
    print("\n🔄 Resetting portfolio tracker...")
    
    try:
        # Clear portfolio database
        portfolio_db = os.path.join('src', 'data', 'portfolio_history.db')
        if os.path.exists(portfolio_db):
            os.remove(portfolio_db)
            print("✅ Cleared portfolio history database")
        
        # Reinitialize portfolio tracker
        from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
        tracker = get_portfolio_tracker()
        
        # Force a fresh snapshot
        tracker._take_snapshot()
        
        current_value = tracker.get_current_portfolio_value()
        print(f"✅ Portfolio tracker reset: ${current_value:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting portfolio tracker: {e}")
        return False

def check_configuration():
    """Check configuration settings"""
    print("\n🔍 Checking configuration...")
    
    try:
        from src.config import (
            PAPER_TRADING_ENABLED,
            WEBHOOK_MODE,
            WEBHOOK_ACTIVE_AGENTS,
            RPC_ENDPOINT,
            PRIMARY_RPC_ENDPOINT
        )
        
        print(f"📋 Paper Trading: {'✅ Enabled' if PAPER_TRADING_ENABLED else '❌ Disabled'}")
        print(f"📋 Webhook Mode: {'✅ Enabled' if WEBHOOK_MODE else '❌ Disabled'}")
        print(f"📋 Active Agents: {list(WEBHOOK_ACTIVE_AGENTS.keys())}")
        print(f"📋 RPC Endpoint: {RPC_ENDPOINT[:50]}...")
        print(f"📋 Primary RPC: {PRIMARY_RPC_ENDPOINT[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking configuration: {e}")
        return False

def main():
    """Main health check function"""
    print("🌙 Anarcho Capital Trading System Health Check")
    print("=" * 60)
    
    # Run all checks
    checks = [
        ("Environment Variables", check_environment_variables),
        ("Configuration", check_configuration),
        ("Database Integrity", check_database_integrity),
        ("RPC Connectivity", check_rpc_connectivity),
        ("Wallet Balance", check_wallet_balance),
        ("Webhook Status", check_webhook_status),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} check failed with exception: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Health Check Summary:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 All systems operational!")
    else:
        print("⚠️  Some issues detected - review the output above")
        
        # Offer to reset portfolio tracker
        if any(name == "Wallet Balance" and not result for name, result in results):
            print("\n🔄 Would you like to reset the portfolio tracker? (y/n): ", end="")
            try:
                response = input().lower().strip()
                if response in ['y', 'yes']:
                    reset_portfolio_tracker()
            except KeyboardInterrupt:
                print("\nOperation cancelled")

if __name__ == "__main__":
    main() 
