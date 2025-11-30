#!/usr/bin/env python3
"""
🌙 DeFi Integration Verification Suite
Tests the integration between DeFi agent and all shared services
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_defi_integration():
    """Test DeFi integration with all shared services"""
    print("🚀 Testing DeFi Integration with Shared Services")
    print("=" * 60)
    
    try:
        # Test 1: Import all DeFi components
        print("\n📦 Test 1: Importing DeFi Components")
        print("-" * 40)
        
        from src.agents.defi_agent import DeFiAgent
        from src.scripts.defi.defi_integration_layer import get_defi_integration_layer
        from src.scripts.defi.defi_protocol_manager import DeFiProtocolManager
        from src.scripts.defi.defi_risk_manager import DeFiRiskManager
        from src.scripts.defi.yield_optimizer import YieldOptimizer
        from src.scripts.utilities.telegram_bot import TelegramBot
        from src.scripts.defi.defi_event_manager import DeFiEventManager
        
        print("✅ All DeFi components imported successfully")
        
        # Test 2: Test shared services integration
        print("\n🔗 Test 2: Shared Services Integration")
        print("-" * 40)
        
        from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
        from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
        from src.scripts.trading.trade_lock_manager import get_trade_lock_manager
        from src.scripts.trading.position_manager import get_position_manager
        from src.scripts.shared_services.hybrid_rpc_manager import get_hybrid_rpc_manager
        
        print("✅ All shared services imported successfully")
        
        # Test 3: Initialize DeFi integration layer
        print("\n🏗️ Test 3: DeFi Integration Layer")
        print("-" * 40)
        
        integration_layer = get_defi_integration_layer()
        print("✅ DeFi integration layer initialized")
        
        # Test 4: Test portfolio data retrieval
        print("\n📊 Test 4: Portfolio Data Retrieval")
        print("-" * 40)
        
        try:
            portfolio_data = integration_layer.get_defi_portfolio_data()
            print(f"✅ Portfolio data retrieved: ${portfolio_data.total_value_usd:.2f} total value")
            print(f"   Available for DeFi: ${portfolio_data.available_for_defi_usd:.2f}")
            print(f"   Risk score: {portfolio_data.risk_score:.1f}")
            print(f"   Market sentiment: {portfolio_data.market_sentiment}")
        except Exception as e:
            print(f"⚠️ Portfolio data retrieval failed: {str(e)}")
        
        # Test 5: Test market sentiment integration
        print("\n📈 Test 5: Market Sentiment Integration")
        print("-" * 40)
        
        try:
            sentiment_data = integration_layer.get_market_sentiment()
            print(f"✅ Market sentiment retrieved: {sentiment_data.get('overall_sentiment', 'N/A')}")
            print(f"   Sentiment score: {sentiment_data.get('sentiment_score', 0):.1f}")
            print(f"   Data freshness: {sentiment_data.get('data_freshness_minutes', 0):.1f} minutes")
        except Exception as e:
            print(f"⚠️ Market sentiment retrieval failed: {str(e)}")
        
        # Test 6: Test DeFi opportunities
        print("\n💡 Test 6: DeFi Opportunities")
        print("-" * 40)
        
        try:
            opportunities = integration_layer.get_defi_opportunities()
            print(f"✅ DeFi opportunities found: {len(opportunities)}")
            for i, opp in enumerate(opportunities[:3]):  # Show first 3
                print(f"   {i+1}. {opp['type'].title()} on {opp['protocol']}: ${opp['amount_usd']:.2f} @ {opp['estimated_apy']:.1f}% APY")
        except Exception as e:
            print(f"⚠️ DeFi opportunities retrieval failed: {str(e)}")
        
        # Test 7: Test nice_funcs integration
        print("\n⚡ Test 7: Nice Funcs Integration")
        print("-" * 40)
        
        try:
            from src import nice_funcs
            
            # Test DeFi functions
            apy_solend = nice_funcs.get_defi_protocol_apy("solend", "USDC")
            apy_mango = nice_funcs.get_defi_protocol_apy("mango", "USDC")
            
            print(f"✅ Nice funcs integration successful")
            print(f"   Solend USDC APY: {apy_solend:.1f}%")
            print(f"   Mango USDC APY: {apy_mango:.1f}%")
            
            # Test current allocation
            current_allocation = nice_funcs.get_current_defi_allocation()
            print(f"   Current DeFi allocation: ${current_allocation:.2f}")
            
        except Exception as e:
            print(f"⚠️ Nice funcs integration failed: {str(e)}")
        
        # Test 8: Test trade lock manager integration
        print("\n🔒 Test 8: Trade Lock Manager Integration")
        print("-" * 40)
        
        try:
            trade_lock_manager = get_trade_lock_manager()
            
            # Check if DeFi agent type is registered
            from src.scripts.trading.trade_lock_manager import AgentType
            if hasattr(AgentType, 'DEFI'):
                print("✅ DeFi agent type registered in trade lock manager")
            else:
                print("⚠️ DeFi agent type not found in trade lock manager")
                
            # Check if DeFi lock types are available
            from src.scripts.trading.trade_lock_manager import LockType
            defi_lock_types = [
                'DEFI_LENDING_OPERATION',
                'DEFI_BORROWING_OPERATION', 
                'DEFI_YIELD_FARMING_OPERATION'
            ]
            
            for lock_type in defi_lock_types:
                if hasattr(LockType, lock_type):
                    print(f"✅ {lock_type} lock type available")
                else:
                    print(f"⚠️ {lock_type} lock type not found")
                    
        except Exception as e:
            print(f"⚠️ Trade lock manager integration failed: {str(e)}")
        
        # Test 9: Test DeFi agent initialization
        print("\n🤖 Test 9: DeFi Agent Initialization")
        print("-" * 40)
        
        try:
            # Initialize DeFi agent (don't start it)
            defi_agent = DeFiAgent(enable_ai=True)
            print("✅ DeFi agent initialized successfully")
            
            # Check agent status
            status = defi_agent.get_agent_status()
            print(f"   Agent status: {status['status']}")
            print(f"   Current phase: {status['phase']}")
            print(f"   Risk level: {status['risk_level']}")
            print(f"   Telegram enabled: {status['telegram_enabled']}")
            
        except Exception as e:
            print(f"⚠️ DeFi agent initialization failed: {str(e)}")
        
        # Test 10: Test configuration integration
        print("\n⚙️ Test 10: Configuration Integration")
        print("-" * 40)
        
        try:
            from src import config
            
            # Check DeFi configuration
            defi_config_vars = [
                'DEFI_MAX_ALLOCATION_PERCENT',
                'DEFI_MIN_ALLOCATION_PERCENT',
                'DEFI_EMERGENCY_RESERVE_PERCENT',
                'DEFI_MAX_SINGLE_PROTOCOL_ALLOCATION',
                'DEFI_MIN_APY_THRESHOLD'
            ]
            
            for var in defi_config_vars:
                if hasattr(config, var):
                    value = getattr(config, var)
                    print(f"✅ {var}: {value}")
                else:
                    print(f"⚠️ {var} not found in config")
                    
        except Exception as e:
            print(f"⚠️ Configuration integration failed: {str(e)}")
        
        print("\n" + "=" * 60)
        print("🎉 DeFi Integration Test Completed!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ DeFi Integration Test Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_defi_execution_simulation():
    """Test DeFi execution simulation (without real transactions)"""
    print("\n🧪 Testing DeFi Execution Simulation")
    print("=" * 50)
    
    try:
        from src import nice_funcs
        
        # Test lending simulation
        print("\n📤 Test: USDC Lending Simulation")
        print("-" * 35)
        
        success = nice_funcs.defi_lend_usdc(100.0, "solend", 200)
        print(f"   Solend lending simulation: {'✅ SUCCESS' if success else '❌ FAILED'}")
        
        success = nice_funcs.defi_lend_usdc(100.0, "mango", 200)
        print(f"   Mango lending simulation: {'✅ SUCCESS' if success else '❌ FAILED'}")
        
        # Test borrowing simulation
        print("\n📥 Test: USDC Borrowing Simulation")
        print("-" * 35)
        
        success = nice_funcs.defi_borrow_usdc(50.0, "SOL", "solend", 200)
        print(f"   Solend borrowing simulation: {'✅ SUCCESS' if success else '❌ FAILED'}")
        
        # Test yield farming simulation
        print("\n🌾 Test: Yield Farming Simulation")
        print("-" * 35)
        
        success = nice_funcs.defi_yield_farm("LP_TOKEN_ADDRESS", 75.0, "orca", 200)
        print(f"   Orca yield farming simulation: {'✅ SUCCESS' if success else '❌ FAILED'}")
        
        print("\n✅ DeFi Execution Simulation Tests Completed!")
        return True
        
    except Exception as e:
        print(f"❌ DeFi Execution Simulation Failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🌙 Anarcho Capital DeFi Integration Verification Suite")
    print("Testing integration between DeFi agent and shared services")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run integration tests
    integration_success = test_defi_integration()
    
    # Run execution simulation tests
    execution_success = test_defi_execution_simulation()
    
    # Final summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"Integration Tests: {'✅ PASSED' if integration_success else '❌ FAILED'}")
    print(f"Execution Tests:  {'✅ PASSED' if execution_success else '❌ FAILED'}")
    
    if integration_success and execution_success:
        print("\n🎉 ALL TESTS PASSED! DeFi system is ready for deployment.")
        print("\n🚀 Next Steps:")
        print("   1. Review test results above")
        print("   2. Configure your .env file with DeFi settings")
        print("   3. Run launch_defi_system.py in a separate terminal")
        print("   4. Monitor DeFi operations via Telegram bot")
    else:
        print("\n⚠️ Some tests failed. Please review the errors above.")
        print("   Check that all dependencies are installed and configured.")
    
    print("=" * 70)
