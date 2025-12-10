"""
Simple production test for harvesting agent - just the core functionality
"""

import os
import sys
from unittest.mock import patch, Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_helpers import PortfolioStateSimulator, create_test_token_addresses
from src.agents.harvesting_agent import HarvestingAgent
from src.config import SOL_ADDRESS, USDC_ADDRESS

class MockSnapshot:
    def __init__(self, total_value_usd):
        self.total_value_usd = total_value_usd

def test_harvesting_agent():
    """Test the core harvesting agent functionality"""
    print("🌾 Testing Harvesting Agent Core Functionality")
    print("=" * 50)
    
    simulator = PortfolioStateSimulator()
    results = []
    
    # Test 1: Dust Conversion
    print("\n1. Testing Dust Conversion...")
    try:
        # Create dust positions
        dust_tokens = create_test_token_addresses(3)
        dust_values = [0.50, 0.75, 1.00]
        
        simulator.set_portfolio_state(100.0, 100.0, 0.0)
        simulator.create_dust_positions(dust_tokens, dust_values)
        
        mock_price_service, mock_api_manager, mock_data_coordinator = simulator.create_mock_services()
        
        with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
             patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
             patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
             patch('src.nice_funcs.market_sell', return_value="mock_tx_signature"):
            
            agent = HarvestingAgent()
            success = agent.auto_convert_dust_to_sol()
        
        current_state = simulator.get_current_state()
        dust_removed = all(token not in current_state['positions'] or current_state['positions'][token] == 0 
                          for token in dust_tokens)
        
        dust_test_passed = success and dust_removed
        print(f"   Dust conversion: {'✅ PASS' if dust_test_passed else '❌ FAIL'}")
        results.append(('Dust Conversion', dust_test_passed))
        
    except Exception as e:
        print(f"   Dust conversion: ❌ FAIL - {e}")
        results.append(('Dust Conversion', False))
    
    # Test 2: Realized Gains Harvesting
    print("\n2. Testing Realized Gains Harvesting...")
    try:
        # Set up 5% gain scenario
        previous_snapshot = MockSnapshot(1000.0)
        current_snapshot = MockSnapshot(1050.0)  # 5% gain = $50
        
        mock_price_service, mock_api_manager, mock_data_coordinator = simulator.create_mock_services()
        
        with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
             patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
             patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
             patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
             patch('src.config.PAPER_TRADING_ENABLED', True):
            
            agent = HarvestingAgent()
            initial_gains = agent.realized_gains_total
            agent._handle_realized_gains(current_snapshot, previous_snapshot)
            final_gains = agent.realized_gains_total
        
        gains_harvested = final_gains > initial_gains
        transfers_recorded = len(agent.external_wallet_transfers) > 0
        
        gains_test_passed = gains_harvested and transfers_recorded
        print(f"   Realized gains: {'✅ PASS' if gains_test_passed else '❌ FAIL'}")
        print(f"   Gains amount: ${agent.realized_gains_total:.2f}")
        print(f"   Transfers: {len(agent.external_wallet_transfers)}")
        results.append(('Realized Gains', gains_test_passed))
        
    except Exception as e:
        print(f"   Realized gains: ❌ FAIL - {e}")
        results.append(('Realized Gains', False))
    
    # Test 3: Below Threshold (should NOT harvest)
    print("\n3. Testing Below Threshold (should NOT harvest)...")
    try:
        previous_snapshot = MockSnapshot(1000.0)
        current_snapshot = MockSnapshot(1030.0)  # 3% gain - below 5% threshold
        
        mock_price_service, mock_api_manager, mock_data_coordinator = simulator.create_mock_services()
        
        with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
             patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
             patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
            
            agent = HarvestingAgent()
            initial_gains = agent.realized_gains_total
            agent._handle_realized_gains(current_snapshot, previous_snapshot)
            final_gains = agent.realized_gains_total
        
        no_harvesting = final_gains == initial_gains
        no_transfers = len(agent.external_wallet_transfers) == 0
        
        threshold_test_passed = no_harvesting and no_transfers
        print(f"   Below threshold: {'✅ PASS' if threshold_test_passed else '❌ FAIL'}")
        results.append(('Below Threshold', threshold_test_passed))
        
    except Exception as e:
        print(f"   Below threshold: ❌ FAIL - {e}")
        results.append(('Below Threshold', False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 PRODUCTION READINESS SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🚀 RESULT: PRODUCTION READY")
        print("   The harvesting agent is working correctly!")
    else:
        print("❌ RESULT: NOT PRODUCTION READY")
        print("   Some issues need to be fixed.")
    
    return passed == total

if __name__ == "__main__":
    test_harvesting_agent()
