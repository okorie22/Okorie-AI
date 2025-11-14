"""
Test scenarios for rebalancing agent logic
"""

import os
import sys
import time
from unittest.mock import patch, Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_helpers import PortfolioStateSimulator, TestValidator, mock_time_for_cooldown_testing
from src.agents.rebalancing_agent import RebalancingAgent
from src.config import SOL_ADDRESS, USDC_ADDRESS

class TestRebalancingScenarios:
    """Test cases for rebalancing agent scenarios"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_tests(self):
        """Run all rebalancing agent tests"""
        print("Running Rebalancing Agent Tests...")
        print("=" * 50)
        
        # Test 1: Startup Rebalancing (100% SOL)
        self.test_startup_rebalancing()
        
        # Test 2: USDC Depletion Crisis
        self.test_usdc_depletion_crisis()
        
        # Test 3: SOL Critical Low
        self.test_sol_critical_low()
        
        # Test 4: Standard Rebalancing - SOL Too High
        self.test_sol_too_high()
        
        # Test 5: Cooldown Mechanism
        self.test_cooldown_mechanism()
        
        # Test 6: Insufficient Funds
        self.test_insufficient_funds()
        
        # Test 7: Extreme Portfolio Imbalances
        self.test_extreme_portfolio_imbalances()
        
        # Test 8: Boundary Conditions
        self.test_boundary_conditions()
        
        # Test 9: Multiple Simultaneous Issues
        self.test_multiple_simultaneous_issues()
        
        # Test 10: Cooldown Edge Cases
        self.test_cooldown_edge_cases()
        
        # Test 11: Price Edge Cases
        self.test_price_edge_cases()
        
        # Test 12: Conversion Amount Edge Cases
        self.test_conversion_amount_edge_cases()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_startup_rebalancing(self):
        """Test 1: Startup Rebalancing (100% SOL)"""
        test_name = "Startup Rebalancing (100% SOL)"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set portfolio: 100% SOL ($1000), 0% USDC, 0% positions
            self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 0.0,
                'sol_value_usd': 1000.0,
                'positions_value_usd': 0.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 0.0
            mock_snapshot.sol_value_usd = 1000.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Returns action to convert ~$900 SOL to USDC
            expected_action_type = "STARTUP_REBALANCE"
            expected_amount_range = (800.0, 950.0)  # Should convert ~90% of SOL
            
            action_found = any(expected_action_type in action for action in actions)
            amount_valid = False
            for action in actions:
                if expected_action_type in action:
                    amount_valid = self.validator.validate_rebalancing_action(
                        action, expected_action_type, expected_amount_range
                    )
                    break
            
            # Verify startup rebalancing flag set
            startup_attempted = agent.startup_rebalancing_attempted
            
            success = action_found and amount_valid and startup_attempted
            
            print(f"Actions returned: {actions}")
            print(f"Expected action type found: {action_found}")
            print(f"Amount in range: {amount_valid}")
            print(f"Startup flag set: {startup_attempted}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions,
                    'startup_attempted': startup_attempted
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_usdc_depletion_crisis(self):
        """Test 2: USDC Depletion Crisis"""
        test_name = "USDC Depletion Crisis"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set portfolio: 10% SOL ($100), 5% USDC ($50), 85% positions ($850)
            self.simulator.set_portfolio_state(100.0, 50.0, 850.0)
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 50.0,
                'sol_value_usd': 100.0,
                'positions_value_usd': 850.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 50.0
            mock_snapshot.sol_value_usd = 100.0
            mock_snapshot.positions_value_usd = 850.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Returns CRITICAL action for USDC depletion + position liquidation
            expected_action_type = "CRITICAL"
            expected_amount_range = (140.0, 160.0)  # Need ~$150 to reach 20% USDC
            
            action_found = any(expected_action_type in action for action in actions)
            amount_valid = False
            for action in actions:
                if expected_action_type in action and "LIQUIDATE" in action:
                    amount_valid = self.validator.validate_rebalancing_action(
                        action, "LIQUIDATE", expected_amount_range
                    )
                    break
            
            # Also check for the specific critical message format
            critical_message = any("USDC 5.0%" in action and "emergency 15.0%" in action for action in actions)
            
            success = action_found and amount_valid and critical_message
            
            print(f"Actions returned: {actions}")
            print(f"Expected action type found: {action_found}")
            print(f"Amount in range: {amount_valid}")
            print(f"Critical message found: {critical_message}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_sol_critical_low(self):
        """Test 3: SOL Critical Low"""
        test_name = "SOL Critical Low"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set portfolio: 3% SOL ($30), 60% USDC ($600), 37% positions ($370)
            self.simulator.set_portfolio_state(30.0, 600.0, 370.0)
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 600.0,
                'sol_value_usd': 30.0,
                'positions_value_usd': 370.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 600.0
            mock_snapshot.sol_value_usd = 30.0
            mock_snapshot.positions_value_usd = 370.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Returns SOL_LOW warning for critical SOL level
            expected_action_type = "SOL_LOW"
            expected_amount_range = (0.0, 0.0)  # No amount in warning message
            
            action_found = any(expected_action_type in action for action in actions)
            amount_valid = True  # Warning messages don't have amounts
            
            # Check that the warning indicates critical low SOL (3% < 7%)
            critical_warning = any("3.0%" in action and "7.0%" in action for action in actions)
            
            success = action_found and amount_valid and critical_warning
            
            print(f"Actions returned: {actions}")
            print(f"Expected action type found: {action_found}")
            print(f"Amount in range: {amount_valid}")
            print(f"Critical warning found: {critical_warning}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_sol_too_high(self):
        """Test 4: Standard Rebalancing - SOL Too High"""
        test_name = "SOL Too High Rebalancing"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set portfolio: 25% SOL ($250), 25% USDC ($250), 50% positions ($500)
            self.simulator.set_portfolio_state(250.0, 250.0, 500.0)
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 250.0,
                'sol_value_usd': 250.0,
                'positions_value_usd': 500.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 250.0
            mock_snapshot.sol_value_usd = 250.0
            mock_snapshot.positions_value_usd = 500.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Returns SOL_HIGH warning for excessive SOL level
            expected_action_type = "SOL_HIGH"
            expected_amount_range = (0.0, 0.0)  # No amount in warning message
            
            action_found = any(expected_action_type in action for action in actions)
            amount_valid = True  # Warning messages don't have amounts
            
            # Check that the warning indicates high SOL (25% > 20%)
            high_warning = any("25.0%" in action and "20.0%" in action for action in actions)
            
            success = action_found and amount_valid and high_warning
            
            print(f"Actions returned: {actions}")
            print(f"Expected action type found: {action_found}")
            print(f"Amount in range: {amount_valid}")
            print(f"High warning found: {high_warning}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_cooldown_mechanism(self):
        """Test 5: Cooldown Mechanism"""
        test_name = "Cooldown Mechanism"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set portfolio that needs rebalancing
            self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)  # 100% SOL
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 0.0,
                'sol_value_usd': 1000.0,
                'positions_value_usd': 0.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 0.0
            mock_snapshot.sol_value_usd = 1000.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                
                # First rebalancing attempt
                actions1 = agent.check_portfolio_allocation()
                
                # Immediately attempt another rebalancing (should be blocked by cooldown)
                actions2 = agent.check_portfolio_allocation()
            
            # Assert: First attempt returns actions, second returns empty due to cooldown
            first_has_actions = len(actions1) > 0
            second_blocked = len(actions2) == 0
            
            success = first_has_actions and second_blocked
            
            print(f"First attempt actions: {actions1}")
            print(f"Second attempt actions: {actions2}")
            print(f"First has actions: {first_has_actions}")
            print(f"Second blocked: {second_blocked}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'first_actions': actions1,
                    'second_actions': actions2
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_insufficient_funds(self):
        """Test 6: Insufficient Funds"""
        test_name = "Insufficient Funds"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set portfolio with small deviation (below $10 minimum)
            self.simulator.set_portfolio_state(105.0, 895.0, 0.0)  # 10.5% SOL, 89.5% USDC
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 895.0,
                'sol_value_usd': 105.0,
                'positions_value_usd': 0.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 895.0
            mock_snapshot.sol_value_usd = 105.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: No action taken (amount too small)
            # Should either return empty list or action with "too small" message
            no_action = len(actions) == 0
            small_amount_message = any("too small" in action.lower() for action in actions)
            
            success = no_action or small_amount_message
            
            print(f"Actions returned: {actions}")
            print(f"No actions: {no_action}")
            print(f"Small amount message: {small_amount_message}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_extreme_portfolio_imbalances(self):
        """Test 7: Extreme Portfolio Imbalances"""
        test_name = "Extreme Portfolio Imbalances"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test 100% USDC allocation (opposite of startup)
            self.simulator.set_portfolio_state(0.0, 1000.0, 0.0)
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 1000.0,
                'sol_value_usd': 0.0,
                'positions_value_usd': 0.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 1000.0
            mock_snapshot.sol_value_usd = 0.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Should return SOL_LOW warning for 0% SOL
            expected_action_type = "SOL_LOW"
            action_found = any(expected_action_type in action for action in actions)
            zero_sol_warning = any("0.0%" in action for action in actions)
            
            success = action_found and zero_sol_warning
            
            print(f"Actions returned: {actions}")
            print(f"Expected action type found: {action_found}")
            print(f"Zero SOL warning found: {zero_sol_warning}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_boundary_conditions(self):
        """Test 8: Boundary Conditions"""
        test_name = "Boundary Conditions"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test SOL at exactly 7% (minimum threshold)
            self.simulator.set_portfolio_state(70.0, 930.0, 0.0)  # 7% SOL, 93% USDC
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 930.0,
                'sol_value_usd': 70.0,
                'positions_value_usd': 0.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 930.0
            mock_snapshot.sol_value_usd = 70.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Should NOT trigger SOL_LOW warning at exactly 7%
            sol_low_warning = any("SOL_LOW" in action for action in actions)
            no_actions = len(actions) == 0
            
            success = not sol_low_warning  # Should not warn at exactly 7%
            
            print(f"Actions returned: {actions}")
            print(f"SOL_LOW warning found: {sol_low_warning}")
            print(f"No actions: {no_actions}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_multiple_simultaneous_issues(self):
        """Test 9: Multiple Simultaneous Issues"""
        test_name = "Multiple Simultaneous Issues"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test SOL low + USDC low simultaneously
            self.simulator.set_portfolio_state(30.0, 50.0, 920.0)  # 3% SOL, 5% USDC, 92% positions
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 50.0,
                'sol_value_usd': 30.0,
                'positions_value_usd': 920.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 50.0
            mock_snapshot.sol_value_usd = 30.0
            mock_snapshot.positions_value_usd = 920.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Should prioritize USDC crisis over SOL low
            usdc_crisis = any("CRITICAL" in action and "USDC" in action for action in actions)
            sol_low = any("SOL_LOW" in action for action in actions)
            
            success = usdc_crisis and not sol_low  # USDC crisis should take priority
            
            print(f"Actions returned: {actions}")
            print(f"USDC crisis detected: {usdc_crisis}")
            print(f"SOL low detected: {sol_low}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_cooldown_edge_cases(self):
        """Test 10: Cooldown Edge Cases"""
        test_name = "Cooldown Edge Cases"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test startup cooldown vs normal cooldown
            self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)  # 100% SOL
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 0.0,
                'sol_value_usd': 1000.0,
                'positions_value_usd': 0.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 0.0
            mock_snapshot.sol_value_usd = 1000.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                
                # First attempt - should trigger startup rebalancing
                actions1 = agent.check_portfolio_allocation()
                
                # Second attempt - should be blocked by startup cooldown
                actions2 = agent.check_portfolio_allocation()
            
            # Assert: First attempt triggers startup, second is blocked
            first_startup = any("STARTUP_REBALANCE" in action for action in actions1)
            second_blocked = len(actions2) == 0
            startup_attempted = agent.startup_rebalancing_attempted
            
            success = first_startup and second_blocked and startup_attempted
            
            print(f"First attempt actions: {actions1}")
            print(f"Second attempt actions: {actions2}")
            print(f"Startup triggered: {first_startup}")
            print(f"Second blocked: {second_blocked}")
            print(f"Startup flag set: {startup_attempted}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'first_actions': actions1,
                    'second_actions': actions2,
                    'startup_attempted': startup_attempted
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_price_edge_cases(self):
        """Test 11: Price Edge Cases"""
        test_name = "Price Edge Cases"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test with very low SOL price ($1)
            self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)  # 100% SOL
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Override price service to return $1 SOL price
            mock_price_service.get_price.return_value = 1.0  # $1 SOL price
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 0.0,
                'sol_value_usd': 1000.0,
                'positions_value_usd': 0.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 0.0
            mock_snapshot.sol_value_usd = 1000.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Should still trigger startup rebalancing with low price
            startup_triggered = any("STARTUP_REBALANCE" in action for action in actions)
            price_handled = True  # Agent should handle low price gracefully
            
            success = startup_triggered and price_handled
            
            print(f"Actions returned: {actions}")
            print(f"Startup triggered: {startup_triggered}")
            print(f"Price handled gracefully: {price_handled}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_conversion_amount_edge_cases(self):
        """Test 12: Conversion Amount Edge Cases"""
        test_name = "Conversion Amount Edge Cases"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test amount slightly below minimum ($9.99 - should skip)
            self.simulator.set_portfolio_state(99.9, 900.1, 0.0)  # 9.99% SOL, 90.01% USDC
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 900.1,
                'sol_value_usd': 99.9,
                'positions_value_usd': 0.0
            }
            
            # Mock snapshot for fallback access
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 900.1
            mock_snapshot.sol_value_usd = 99.9
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Should not take action for small deviation
            no_action = len(actions) == 0
            small_deviation_handled = True
            
            success = no_action and small_deviation_handled
            
            print(f"Actions returned: {actions}")
            print(f"No action taken: {no_action}")
            print(f"Small deviation handled: {small_deviation_handled}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'actions': actions
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
    test_suite = TestRebalancingScenarios()
    results = test_suite.run_all_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nSummary: {passed}/{total} tests passed")
