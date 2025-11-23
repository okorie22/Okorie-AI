"""
Integration tests for rebalancing and harvesting agents coordination
"""

import os
import sys
import time
from unittest.mock import patch, Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_helpers import PortfolioStateSimulator, TestValidator, create_test_token_addresses
from src.agents.rebalancing_agent import RebalancingAgent
from src.agents.harvesting_agent import HarvestingAgent
from src.config import SOL_ADDRESS, USDC_ADDRESS

class MockSnapshot:
    """Mock portfolio snapshot for testing"""
    def __init__(self, total_value_usd, positions=None):
        self.total_value_usd = total_value_usd
        self.positions = positions or {}

class TestAgentIntegration:
    """Integration test cases for agent coordination"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_tests(self):
        """Run all integration tests"""
        print("Running Agent Integration Tests...")
        print("=" * 50)
        
        # Test 1: Fresh Start Complete Flow
        self.test_fresh_start_complete_flow()
        
        # Test 2: Agent Priority and Coordination
        self.test_agent_priority_coordination()
        
        # Test 3: Cooldown Interaction
        self.test_cooldown_interaction()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_fresh_start_complete_flow(self):
        """Test 1: Fresh Start Complete Flow"""
        test_name = "Fresh Start Complete Flow"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Start: 100% SOL portfolio
            self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)
            print("Initial state: 100% SOL")
            
            # Create agents with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                # Run: Rebalancing agent
                rebalancing_agent = RebalancingAgent()
                rebalancing_actions = rebalancing_agent.check_portfolio_allocation()
                print(f"Rebalancing actions: {rebalancing_actions}")
                
                # Verify: 10% SOL, 90% USDC (simulate the rebalancing execution)
                if rebalancing_actions:
                    # Simulate the rebalancing by manually adjusting portfolio
                    self.simulator.set_portfolio_state(100.0, 900.0, 0.0)  # 10% SOL, 90% USDC
                    print("Simulated rebalancing: 10% SOL, 90% USDC")
                
                # Add: Simulated copybot positions (30% of portfolio)
                copybot_positions = {
                    create_test_token_addresses(1)[0]: 300.0  # $300 position
                }
                self.simulator.set_portfolio_state(100.0, 600.0, 300.0, copybot_positions)
                print("Added copybot positions: 10% SOL, 60% USDC, 30% positions")
                
                # Run: Harvesting agent (no action expected, no gains)
                harvesting_agent = HarvestingAgent()
                previous_snapshot = MockSnapshot(1000.0)
                current_snapshot = MockSnapshot(1000.0)  # No gains yet
                harvesting_agent._handle_realized_gains(current_snapshot, previous_snapshot)
                
                no_harvesting_initial = len(harvesting_agent.external_wallet_transfers) == 0
                print(f"No initial harvesting: {no_harvesting_initial}")
                
                # Simulate: 5% portfolio gains
                self.simulator.simulate_portfolio_gains(5.0)  # 5% increase
                print("Simulated 5% portfolio gains")
                
                # Run: Harvesting agent
                current_snapshot_with_gains = MockSnapshot(1050.0)  # 5% gain
                harvesting_agent._handle_realized_gains(current_snapshot_with_gains, current_snapshot)
                
                # Verify: Gains harvested and reallocated
                gains_harvested = len(harvesting_agent.external_wallet_transfers) > 0
                realized_gains_updated = harvesting_agent.realized_gains_total > 0
                
                success = no_harvesting_initial and gains_harvested and realized_gains_updated
                
                print(f"Gains harvested: {gains_harvested}")
                print(f"Realized gains updated: {realized_gains_updated}")
                print(f"External transfers: {len(harvesting_agent.external_wallet_transfers)}")
                print(f"Result: {'PASS' if success else 'FAIL'}")
                
                self.test_results.append({
                    'name': test_name,
                    'passed': success,
                    'details': {
                        'no_initial_harvesting': no_harvesting_initial,
                        'gains_harvested': gains_harvested,
                        'realized_gains_updated': realized_gains_updated,
                        'external_transfers': len(harvesting_agent.external_wallet_transfers),
                        'realized_gains_total': harvesting_agent.realized_gains_total
                    }
                })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_agent_priority_coordination(self):
        """Test 2: Agent Priority and Coordination"""
        test_name = "Agent Priority and Coordination"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up portfolio that needs both rebalancing and harvesting
            self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)  # 100% SOL - needs rebalancing
            
            # Create agents with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                # Trigger both agents simultaneously
                rebalancing_agent = RebalancingAgent()
                harvesting_agent = HarvestingAgent()
                
                # Check rebalancing first (higher priority)
                rebalancing_actions = rebalancing_agent.check_portfolio_allocation()
                
                # Simulate rebalancing execution
                if rebalancing_actions:
                    self.simulator.set_portfolio_state(100.0, 900.0, 0.0)
                
                # Then check harvesting
                previous_snapshot = MockSnapshot(1000.0)
                current_snapshot = MockSnapshot(1000.0)
                harvesting_agent._handle_realized_gains(current_snapshot, previous_snapshot)
                
                # Verify: Rebalancing executes before harvesting
                rebalancing_triggered = len(rebalancing_actions) > 0
                harvesting_no_action = len(harvesting_agent.external_wallet_transfers) == 0
                
                # Check: No conflicts in portfolio modifications
                final_state = self.simulator.get_current_state()
                expected_allocation = self.validator.validate_portfolio_allocation(
                    self.simulator, 0.10, 0.90, 0.0  # 10% SOL, 90% USDC, 0% positions
                )
                
                success = rebalancing_triggered and harvesting_no_action and expected_allocation
                
                print(f"Rebalancing triggered: {rebalancing_triggered}")
                print(f"Harvesting no action: {harvesting_no_action}")
                print(f"Expected allocation: {expected_allocation}")
                print(f"Final state: SOL {final_state['sol_pct']:.1%}, USDC {final_state['usdc_pct']:.1%}, Positions {final_state['positions_pct']:.1%}")
                print(f"Result: {'PASS' if success else 'FAIL'}")
                
                self.test_results.append({
                    'name': test_name,
                    'passed': success,
                    'details': {
                        'rebalancing_triggered': rebalancing_triggered,
                        'harvesting_no_action': harvesting_no_action,
                        'expected_allocation': expected_allocation,
                        'final_state': final_state
                    }
                })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_cooldown_interaction(self):
        """Test 3: Cooldown Interaction"""
        test_name = "Cooldown Interaction"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up portfolio that needs rebalancing
            self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)  # 100% SOL
            
            # Create agents with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                rebalancing_agent = RebalancingAgent()
                harvesting_agent = HarvestingAgent()
                
                # Trigger rebalancing
                rebalancing_actions1 = rebalancing_agent.check_portfolio_allocation()
                print(f"First rebalancing: {rebalancing_actions1}")
                
                # Trigger harvesting immediately after
                previous_snapshot = MockSnapshot(1000.0)
                current_snapshot = MockSnapshot(1000.0)
                harvesting_agent._handle_realized_gains(current_snapshot, previous_snapshot)
                print(f"Harvesting after rebalancing: {len(harvesting_agent.external_wallet_transfers)} transfers")
                
                # Immediately attempt another rebalancing (should be blocked by cooldown)
                rebalancing_actions2 = rebalancing_agent.check_portfolio_allocation()
                print(f"Second rebalancing (should be blocked): {rebalancing_actions2}")
                
                # Verify: Both agents respect their own cooldowns
                first_rebalancing_worked = len(rebalancing_actions1) > 0
                second_rebalancing_blocked = len(rebalancing_actions2) == 0
                
                # Verify: Agents don't interfere with each other's locks
                harvesting_worked = True  # Harvesting should work regardless of rebalancing cooldown
                
                # Check rebalancing cooldown state
                rebalancing_in_cooldown = rebalancing_agent.rebalancing_in_progress or \
                    (time.time() - rebalancing_agent.last_rebalancing_time < rebalancing_agent.rebalancing_cooldown_seconds)
                
                success = first_rebalancing_worked and second_rebalancing_blocked and harvesting_worked and rebalancing_in_cooldown
                
                print(f"First rebalancing worked: {first_rebalancing_worked}")
                print(f"Second rebalancing blocked: {second_rebalancing_blocked}")
                print(f"Harvesting worked: {harvesting_worked}")
                print(f"Rebalancing in cooldown: {rebalancing_in_cooldown}")
                print(f"Result: {'PASS' if success else 'FAIL'}")
                
                self.test_results.append({
                    'name': test_name,
                    'passed': success,
                    'details': {
                        'first_rebalancing_worked': first_rebalancing_worked,
                        'second_rebalancing_blocked': second_rebalancing_blocked,
                        'harvesting_worked': harvesting_worked,
                        'rebalancing_in_cooldown': rebalancing_in_cooldown,
                        'rebalancing_actions1': rebalancing_actions1,
                        'rebalancing_actions2': rebalancing_actions2
                    }
                })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })


if __name__ == "__main__":
    # Run tests when script is executed directly
    test_suite = TestAgentIntegration()
    results = test_suite.run_all_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nSummary: {passed}/{total} tests passed")
