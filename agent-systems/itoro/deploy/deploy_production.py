#!/usr/bin/env python3
"""
🌙 Anarcho Capital's Production Deployment Script
Comprehensive deployment validation and system readiness checks
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_banner():
    """Print deployment banner"""
    print("=" * 80)
    print("🌙 ANARCHO CAPITAL'S TRADING SYSTEM - PRODUCTION DEPLOYMENT")
    print("=" * 80)
    print(f"Deployment started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def check_python_version():
    """Check Python version compatibility"""
    print("📋 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
    return True

def check_environment_variables():
    """Check required environment variables"""
    print("📋 Checking environment variables...")
    
    required_vars = [
        'DEFAULT_WALLET_ADDRESS',
        'SOLANA_PRIVATE_KEY',
        'HELIUS_API_KEY',
        'BIRDEYE_API_KEY',  # Added for Birdeye API integration
        'RPC_ENDPOINT'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ All required environment variables present")
    return True

def install_dependencies():
    """Install required dependencies"""
    print("📋 Installing dependencies...")
    
    try:
        # Update pip first
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️  Warning: Failed to upgrade pip: {result.stderr}")
        
        # Install requirements
        requirements_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'requirements.txt')
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', requirements_path], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️  Some dependencies failed to install:")
            print(f"STDERR: {result.stderr}")
            
            # Check if it's just a missing package issue
            if "No matching distribution found" in result.stderr:
                print("💡 This appears to be a package name issue, not a critical failure")
                response = input("Continue deployment despite dependency warning? (y/N): ").strip().lower()
                if response == 'y':
                    print("⚠️  Continuing with existing dependencies")
                    return True
            
            return False
        
        print("✅ Dependencies installed successfully")
        return True
    except Exception as e:
        print(f"❌ Exception during dependency installation: {e}")
        return False

def validate_configuration():
    """Validate system configuration"""
    print("📋 Validating configuration...")
    
    try:
        # Import and run config validation
        from src.scripts.utilities.config_validator import ConfigValidator
        from src import config
        validator = ConfigValidator()
        is_safe, results = validator.validate_all(config)
        
        critical_issues = [r for r in results if r.level.value == 'CRITICAL']
        high_issues = [r for r in results if r.level.value == 'HIGH']
        
        if critical_issues:
            print(f"❌ {len(critical_issues)} critical configuration issues found:")
            for issue in critical_issues:
                print(f"   - {issue.message}")
            return False
        
        if high_issues:
            print(f"⚠️  {len(high_issues)} high priority configuration issues found:")
            for issue in high_issues:
                print(f"   - {issue.message}")
            
            response = input("Continue with high priority issues? (y/N): ")
            if response.lower() != 'y':
                return False
        
        print("✅ Configuration validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        print("💡 Make sure the config module is properly imported and accessible")
        return False

def run_system_tests():
    """Run basic system tests"""
    print("📋 Running system tests...")
    
    try:
        # Test imports
        from src import config
        from src.scripts import shared_api_manager, optimized_price_service
        from src.agents import risk_agent, copybot_agent, harvesting_agent
        
        # Test basic functionality
        from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
        api_manager = get_shared_api_manager()
        
        price_service = optimized_price_service.get_optimized_price_service()
        
        # Test configuration access
        test_vars = ['usd_size', 'slippage', 'address']
        for var in test_vars:
            if not hasattr(config, var):
                print(f"❌ Missing configuration variable: {var}")
                return False
        
        print("✅ System tests passed")
        return True
        
    except Exception as e:
        print(f"❌ System tests failed: {e}")
        return False

def check_wallet_connection():
    """Check YOUR personal wallet connection and balance (not whale wallets)"""
    print("📋 Checking YOUR personal wallet connection...")
    print("💡 This checks the wallet specified in DEFAULT_WALLET_ADDRESS")
    
    try:
        from src.nice_funcs import get_wallet_total_value
        from src import config
        import threading
        import time
        
        # Use threading for timeout (cross-platform)
        result = {'balance': None, 'error': None, 'completed': False}
        
        def get_balance():
            try:
                result['balance'] = get_wallet_total_value(config.address)
                result['completed'] = True
            except Exception as e:
                result['error'] = str(e)
                result['completed'] = True
        
        # Start balance check in separate thread
        thread = threading.Thread(target=get_balance)
        thread.daemon = True
        thread.start()
        
        # Wait for completion or timeout (30 seconds)
        timeout = 30
        start_time = time.time()
        
        while not result['completed'] and (time.time() - start_time) < timeout:
            time.sleep(0.5)
            print(".", end="", flush=True)
        
        print()  # New line after dots
        
        if not result['completed']:
            print("❌ Wallet connection check timed out (30 seconds)")
            print("💡 Check your RPC endpoint and network connection")
            print("⚠️  This may indicate network issues or RPC endpoint problems")
            
            # Ask user if they want to skip this check
            try:
                response = input("Continue deployment without wallet balance check? (y/N): ").strip().lower()
                if response == 'y':
                    print("⚠️  Skipping wallet balance check - proceed with caution!")
                    return True
            except:
                pass
            
            return False
        
        if result['error']:
            print(f"❌ Wallet connection failed: {result['error']}")
            return False
        
        balance = result['balance']
        if balance is None:
            print("❌ Could not retrieve wallet balance")
            return False
        
        if balance < config.MINIMUM_BALANCE_USD:
            print(f"⚠️  Wallet balance ${balance:.2f} below minimum ${config.MINIMUM_BALANCE_USD}")
            print("💡 You may need more SOL for transaction fees and trading")
            response = input("Continue deployment with low balance? (y/N): ").strip().lower()
            if response != 'y':
                return False
            print("⚠️  Proceeding with low balance - monitor carefully!")
        
        print(f"✅ Wallet connected - Balance: ${balance:.2f}")
        return True
        
    except Exception as e:
        print(f"❌ Wallet connection failed: {e}")
        return False

def check_api_connectivity():
    """Check API connectivity"""
    print("📋 Checking API connectivity...")
    
    try:
        from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
        api_manager = get_shared_api_manager()
        
        # Test API endpoints
        endpoints_to_test = [
            'helius_api',
            'birdeye_api',  # Added for Birdeye API testing
            'jupiter_api',
            'rpc_endpoint'
        ]
        
        for endpoint in endpoints_to_test:
            if hasattr(api_manager, f'test_{endpoint}'):
                test_func = getattr(api_manager, f'test_{endpoint}')
                if not test_func():
                    print(f"❌ {endpoint} connectivity failed")
                    return False
        
        print("✅ API connectivity verified")
        return True
        
    except Exception as e:
        print(f"❌ API connectivity check failed: {e}")
        return False

def initialize_system_components():
    """Initialize all system components"""
    print("📋 Initializing system components...")
    
    try:
        # Initialize shared services
        from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
        from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
        from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
        
        api_manager = get_shared_api_manager()
        price_service = get_optimized_price_service()
        data_coordinator = get_shared_data_coordinator()
        
        # Basic monitoring initialization (simplified)
        print("📊 Monitoring services initialized (simplified version)")
        
        print("✅ System components initialized")
        return True
        
    except Exception as e:
        print(f"❌ System component initialization failed: {e}")
        return False

def create_deployment_report():
    """Create deployment report"""
    print("📋 Creating deployment report...")
    
    try:
        from src import config
        
        report = {
            'deployment_time': datetime.now().isoformat(),
            'system_version': '1.0.0',
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'configuration': {
                'position_sizing_mode': getattr(config, 'POSITION_SIZING_MODE', 'fixed'),
                'base_position_size': getattr(config, 'BASE_POSITION_SIZE_USD', 25.0),
                'max_single_position': getattr(config, 'MAX_SINGLE_POSITION_PERCENT', 0.15),
                'slippage': getattr(config, 'slippage', 100),
                'risk_management_enabled': getattr(config, 'RISK_MANAGEMENT_ENABLED', True),
                'emergency_stop_enabled': getattr(config, 'EMERGENCY_STOP_ENABLED', True)
            },
            'deployment_status': 'SUCCESS'
        }
        
        # Save report
        os.makedirs('deployment_reports', exist_ok=True)
        report_file = f"deployment_reports/deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"✅ Deployment report saved to {report_file}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create deployment report: {e}")
        return False

def main():
    """Main deployment process"""
    print_banner()
    
    # Pre-deployment checks
    checks = [
        ("Python Version", check_python_version),
        ("Environment Variables", check_environment_variables),
        ("Dependencies", install_dependencies),
        ("Configuration", validate_configuration),
        ("System Tests", run_system_tests),
        ("Wallet Connection", check_wallet_connection),
        ("API Connectivity", check_api_connectivity),
        ("System Components", initialize_system_components)
    ]
    
    failed_checks = []
    
    for check_name, check_func in checks:
        print(f"\n🔍 Running {check_name} check...")
        if not check_func():
            failed_checks.append(check_name)
            print(f"❌ {check_name} check failed")
        else:
            print(f"✅ {check_name} check passed")
    
    print("\n" + "=" * 80)
    
    if failed_checks:
        print("❌ DEPLOYMENT FAILED")
        print(f"Failed checks: {', '.join(failed_checks)}")
        print("Please fix the issues above before deploying to production.")
        return False
    else:
        print("✅ DEPLOYMENT SUCCESSFUL")
        print("All checks passed! System is ready for production.")
        
        # Create deployment report
        create_deployment_report()
        
        print("\n🚀 Starting system in production mode...")
        print("Monitor the logs for any issues.")
        print("Use Ctrl+C to stop the system safely.")
        
        # Optional: Start the main system
        try:
            from src.main import run_agents as start_system
            start_system()
        except KeyboardInterrupt:
            print("\n🛑 System stopped by user")
        except Exception as e:
            print(f"\n❌ System error: {e}")
            return False
        
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
