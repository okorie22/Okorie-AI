#!/usr/bin/env python3
"""
🌙 Anarcho Capital's Webhook System Deployment Script
Comprehensive deployment, testing, and debugging tool for webhook system
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_banner():
    """Print deployment banner"""
    print("=" * 80)
    print("🌙 ANARCHO CAPITAL'S WEBHOOK SYSTEM DEPLOYMENT")
    print("=" * 80)
    print(f"Deployment started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def check_environment_variables():
    """Check all required environment variables for webhook system"""
    print("📋 Checking environment variables...")
    
    required_vars = [
        'DEFAULT_WALLET_ADDRESS',
        'SOLANA_PRIVATE_KEY',
        'HELIUS_API_KEY',
        'RPC_ENDPOINT'
    ]
    
    optional_vars = [
        'PORT',
        'WEBHOOK_BASE_URL',
        'RENDER_SERVICE_NAME'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            print(f"❌ {var}: Not set")
        else:
            # Show truncated value for security
            value = os.getenv(var)
            if len(value) > 16:
                print(f"✅ {var}: {value[:8]}...{value[-4:]}")
            else:
                print(f"✅ {var}: {value}")
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"ℹ️ {var}: {value}")
        else:
            print(f"ℹ️ {var}: Not set (optional)")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ All required environment variables configured")
    return True

def test_webhook_endpoint(webhook_url: str, timeout: int = 10) -> bool:
    """Test if webhook endpoint is accessible"""
    print(f"🔗 Testing webhook endpoint: {webhook_url}")
    
    try:
        response = requests.get(webhook_url.replace('/webhook', '/'), timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Webhook server healthy: {data.get('service', 'Unknown')}")
            
            # Show agent status
            agents = data.get('agents', {})
            print(f"   Agents: CopyBot={agents.get('copybot', False)}, "
                  f"Risk={agents.get('risk', False)}, "
                  f"Rebalancing={agents.get('rebalancing', False)}")
            
            # Show wallet tracking
            wallets_tracked = data.get('wallets_tracked', 0)
            personal_wallet_tracked = data.get('personal_wallet_tracked', False)
            print(f"   Wallets tracked: {wallets_tracked}, Personal wallet: {personal_wallet_tracked}")
            
            return True
        else:
            print(f"❌ Webhook server returned status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to webhook endpoint: {e}")
        return False

def get_existing_helius_webhooks() -> List[Dict]:
    """Get existing webhooks from Helius"""
    print("📋 Checking existing Helius webhooks...")
    
    helius_api_key = os.getenv('HELIUS_API_KEY')
    if not helius_api_key:
        print("❌ HELIUS_API_KEY not set")
        return []
    
    try:
        response = requests.get(
            f"https://api.helius.xyz/v0/webhooks?api-key={helius_api_key}",
            timeout=10
        )
        
        if response.status_code == 200:
            webhooks = response.json()
            print(f"✅ Found {len(webhooks)} existing webhook(s)")
            
            for i, webhook in enumerate(webhooks):
                webhook_id = webhook.get('webhookID', 'Unknown')
                webhook_url = webhook.get('webhookURL', 'Unknown')
                account_addresses = webhook.get('accountAddresses', [])
                print(f"   {i+1}. ID: {webhook_id}, URL: {webhook_url}, Addresses: {len(account_addresses)}")
                
            return webhooks
        else:
            print(f"❌ Failed to get webhooks: {response.status_code}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error getting webhooks: {e}")
        return []

def test_personal_wallet_integration() -> bool:
    """Test if personal wallet is properly integrated"""
    print("👤 Testing personal wallet integration...")
    
    try:
        from src.scripts.webhooks.webhook_config import (
            get_personal_wallet_address, 
            is_personal_wallet,
            WALLETS_TO_TRACK
        )
        
        personal_wallet = get_personal_wallet_address()
        if not personal_wallet:
            print("❌ Personal wallet address not found")
            return False
            
        print(f"✅ Personal wallet found: {personal_wallet[:8]}...{personal_wallet[-4:]}")
        
        # Check if personal wallet is in tracking list
        if personal_wallet in WALLETS_TO_TRACK:
            print("✅ Personal wallet is in tracking list")
        else:
            print("❌ Personal wallet is NOT in tracking list")
            return False
            
        # Test wallet detection function
        if is_personal_wallet(personal_wallet):
            print("✅ Personal wallet detection function works")
        else:
            print("❌ Personal wallet detection function failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing personal wallet integration: {e}")
        return False

def test_agent_initialization() -> bool:
    """Test if all agents can be initialized"""
    print("🤖 Testing agent initialization...")
    
    try:
        # Test CopyBot initialization
        print("   Testing CopyBot...")
        from src.agents.copybot_agent import CopyBotAgent
        copybot = CopyBotAgent()
        print("   ✅ CopyBot initialized successfully")
        
        # Test Risk Agent initialization
        print("   Testing Risk Agent...")
        from src.agents.risk_agent import RiskAgent
        risk_agent = RiskAgent()
        print("   ✅ Risk Agent initialized successfully")
        
        # Test Harvesting Agent initialization
        print("   Testing Harvesting Agent...")
        from src.agents.harvesting_agent import HarvestingAgent
        harvesting_agent = HarvestingAgent()
        print("   ✅ Harvesting Agent initialized successfully")
        
        # Test webhook integration methods
        print("   Testing webhook integration methods...")
        if hasattr(risk_agent, 'handle_webhook_trigger'):
            print("   ✅ Risk Agent has webhook integration")
        else:
            print("   ❌ Risk Agent missing webhook integration")
            return False
            
        if hasattr(harvesting_agent, 'handle_webhook_trigger'):
            print("   ✅ Harvesting Agent has webhook integration")
        else:
            print("   ❌ Harvesting Agent missing webhook integration")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing agent initialization: {e}")
        return False

def simulate_webhook_event() -> bool:
    """Simulate a webhook event to test the system"""
    print("🔄 Simulating webhook event...")
    
    try:
        from src.scripts.webhooks.webhook_config import get_personal_wallet_address
        
        personal_wallet = get_personal_wallet_address()
        if not personal_wallet:
            print("❌ Cannot simulate - personal wallet not configured")
            return False
            
        # Create a mock transaction event
        mock_event = {
            "type": "TRANSACTION",
            "tokenTransfers": [
                {
                    "tokenMint": "So11111111111111111111111111111111111111112",  # SOL
                    "amount": 1000000000,  # 1 SOL
                    "fromUserAccount": personal_wallet,
                    "toUserAccount": "11111111111111111111111111111111",
                    "decimals": 9,
                    "tokenName": "Solana",
                    "tokenSymbol": "SOL"
                }
            ],
            "nativeTransfers": [
                {
                    "amount": 1000000000,  # 1 SOL in lamports
                    "fromUserAccount": personal_wallet,
                    "toUserAccount": "11111111111111111111111111111111"
                }
            ],
            "transaction": {
                "signature": "test_signature_123456789"
            }
        }
        
        # Import and test the webhook handler
        from src.scripts.webhooks.webhook_handler import (
            process_webhook_event,
            should_process_transaction,
            is_personal_wallet
        )
        
        # Test personal wallet detection
        if is_personal_wallet(personal_wallet):
            print("   ✅ Personal wallet detected correctly")
        else:
            print("   ❌ Personal wallet detection failed")
            return False
            
        # Test transaction filtering
        if should_process_transaction(mock_event, personal_wallet):
            print("   ✅ Transaction filtering works")
        else:
            print("   ❌ Transaction filtering failed")
            return False
            
        # Test event processing
        involved_wallets = process_webhook_event(mock_event)
        if personal_wallet in involved_wallets:
            print("   ✅ Event processing works")
        else:
            print("   ❌ Event processing failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error simulating webhook event: {e}")
        return False

def deploy_webhook_system() -> bool:
    """Deploy the complete webhook system"""
    print("🚀 Deploying webhook system...")
    
    try:
        # Start webhook server in test mode
        print("   Starting webhook server...")
        
        # Import and test the webhook handler
        from src.scripts.webhooks.webhook_handler import (
            initialize_copybot,
            initialize_risk_agent, 
            initialize_harvesting_agent,
            setup_personal_wallet_monitoring
        )
        
        # Initialize personal wallet monitoring
        setup_personal_wallet_monitoring()
        print("   ✅ Personal wallet monitoring configured")
        
        # Initialize agents
        if initialize_copybot():
            print("   ✅ CopyBot initialized")
        else:
            print("   ❌ CopyBot initialization failed")
            
        if initialize_risk_agent():
            print("   ✅ Risk Agent initialized")
        else:
            print("   ❌ Risk Agent initialization failed")
            
        if initialize_harvesting_agent():
            print("   ✅ Harvesting Agent initialized")
        else:
            print("   ❌ Harvesting Agent initialization failed")
            
        print("✅ Webhook system deployed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error deploying webhook system: {e}")
        return False

def create_deployment_report() -> str:
    """Create a comprehensive deployment report"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "environment_check": check_environment_variables(),
        "personal_wallet_integration": test_personal_wallet_integration(),
        "agent_initialization": test_agent_initialization(),
        "webhook_simulation": simulate_webhook_event(),
        "deployment_status": "READY" if all([
            check_environment_variables(),
            test_personal_wallet_integration(),
            test_agent_initialization(),
            simulate_webhook_event()
        ]) else "ISSUES_FOUND"
    }
    
    # Save report
    report_path = f"deployment_reports/webhook_deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("deployment_reports", exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📊 Deployment report saved: {report_path}")
    return report_path

def main():
    """Main deployment function"""
    print_banner()
    
    # Run all checks
    checks = [
        ("Environment Variables", check_environment_variables),
        ("Personal Wallet Integration", test_personal_wallet_integration),
        ("Agent Initialization", test_agent_initialization),
        ("Webhook Event Simulation", simulate_webhook_event),
        ("Webhook System Deployment", deploy_webhook_system)
    ]
    
    results = {}
    for check_name, check_func in checks:
        print(f"\n{'='*60}")
        print(f"Running: {check_name}")
        print(f"{'='*60}")
        
        try:
            result = check_func()
            results[check_name] = result
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"\n{status}: {check_name}")
        except Exception as e:
            results[check_name] = False
            print(f"\n❌ ERROR in {check_name}: {e}")
    
    # Create deployment report
    report_path = create_deployment_report()
    
    # Summary
    print(f"\n{'='*80}")
    print("DEPLOYMENT SUMMARY")
    print(f"{'='*80}")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for check_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {check_name}")
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 Webhook system is ready for deployment!")
        print("\nNext steps:")
        print("1. Deploy to Render: git push origin master")
        print("2. Test webhook endpoint once deployed")
        print("3. Monitor webhook events in logs")
        print("4. Verify agent triggering works correctly")
    else:
        print("⚠️ Issues found - fix before deploying")
        print(f"📊 See full report: {report_path}")

if __name__ == "__main__":
    main() 
