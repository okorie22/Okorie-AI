"""
Edge case tests for harvesting agent
Comprehensive testing of boundary conditions and unusual scenarios
"""

import os
import sys
from unittest.mock import patch, Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_helpers import (
    PortfolioStateSimulator, TestValidator, create_test_token_addresses,
    MockJupiterSwap, MockSOLTransfer, MockPriceService, MockAPIManager,
    StressTestUtilities, ErrorRecoveryTestHelper
)
from src.agents.harvesting_agent import HarvestingAgent
from src.config import SOL_ADDRESS, USDC_ADDRESS, EXCLUDED_TOKENS

class MockSnapshot:
    """Mock portfolio snapshot for testing"""
    def __init__(self, total_value_usd, positions=None):
        self.total_value_usd = total_value_usd
        self.positions = positions or {}

class TestHarvestingEdgeCases:
    """Edge case tests for harvesting agent"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_tests(self):
        """Run all edge case tests"""
        print("Running Harvesting Agent Edge Case Tests...")
        print("=" * 60)
        
        # Realized Gains Edge Cases
        self.test_gains_below_usd_threshold()
        self.test_gains_exactly_at_threshold()
        self.test_very_large_gains()
        self.test_multiple_consecutive_gains()
        self.test_negative_portfolio_change()
        
        # Dust Conversion Edge Cases
        self.test_no_dust_positions()
        self.test_all_excluded_tokens_as_dust()
        self.test_mixed_dust_and_large_positions()
        self.test_dust_at_boundary()
        self.test_very_small_dust()
        
        # External Wallet Edge Cases
        self.test_missing_external_wallet_address()
        self.test_external_wallets_disabled()
        self.test_invalid_sol_price()
        
        # Swap Failure Cases
        self.test_jupiter_swap_fails()
        self.test_insufficient_balance_for_swap()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_gains_below_usd_threshold(self):
        """Test: Gains Below USD Threshold ($50)"""
        test_name = "Gains Below USD Threshold ($50)"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set initial portfolio value: $1000
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            previous_snapshot = MockSnapshot(1000.0)
            
            # Simulate 5% gain but only $45 (below $50 threshold)
            self.simulator.simulate_portfolio_gains(4.5)  # 4.5% = $45
            current_snapshot = MockSnapshot(1045.0)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Assert: No harvesting action (below $50 threshold)
            no_harvesting = final_gains == initial_gains
            no_transfers = len(agent.external_wallet_transfers) == 0
            
            # Verify threshold logic
            portfolio_gain = current_snapshot.total_value_usd - previous_snapshot.total_value_usd
            below_threshold = portfolio_gain < 50.0
            
            success = no_harvesting and no_transfers and below_threshold
            
            print(f"No harvesting: {no_harvesting}")
            print(f"No transfers: {no_transfers}")
            print(f"Below threshold: {below_threshold}")
            print(f"Portfolio gain: ${portfolio_gain:.2f}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'no_harvesting': no_harvesting,
                    'no_transfers': no_transfers,
                    'below_threshold': below_threshold,
                    'portfolio_gain': portfolio_gain
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_gains_exactly_at_threshold(self):
        """Test: Gains Exactly at Threshold"""
        test_name = "Gains Exactly at Threshold"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set initial portfolio value: $1000
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            previous_snapshot = MockSnapshot(1000.0)
            
            # Simulate exactly 5% gain = $50 (exactly at threshold)
            self.simulator.simulate_portfolio_gains(5.0)  # 5% = $50
            current_snapshot = MockSnapshot(1050.0)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            mock_sol_transfer = MockSOLTransfer()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Assert: Harvesting should execute (exactly at threshold)
            harvesting_executed = final_gains > initial_gains
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Verify threshold logic
            portfolio_gain = current_snapshot.total_value_usd - previous_snapshot.total_value_usd
            at_threshold = portfolio_gain >= 50.0
            
            success = harvesting_executed and transfers_recorded and at_threshold
            
            print(f"Harvesting executed: {harvesting_executed}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"At threshold: {at_threshold}")
            print(f"Portfolio gain: ${portfolio_gain:.2f}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'harvesting_executed': harvesting_executed,
                    'transfers_recorded': transfers_recorded,
                    'at_threshold': at_threshold,
                    'portfolio_gain': portfolio_gain
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_very_large_gains(self):
        """Test: Very Large Gains"""
        test_name = "Very Large Gains"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set initial portfolio value: $10,000
            self.simulator.set_portfolio_state(1000.0, 2000.0, 7000.0)
            previous_snapshot = MockSnapshot(10000.0)
            
            # Simulate 50% gain = $5,000
            self.simulator.simulate_portfolio_gains(50.0)  # 50% = $5,000
            current_snapshot = MockSnapshot(15000.0)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            mock_sol_transfer = MockSOLTransfer()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Assert: Harvesting should execute with large amounts
            harvesting_executed = final_gains > initial_gains
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Verify large value calculations
            portfolio_gain = current_snapshot.total_value_usd - previous_snapshot.total_value_usd
            large_gain = portfolio_gain >= 1000.0  # $1,000+ gain
            
            # Check reallocation amounts are reasonable
            if transfers_recorded:
                total_transfer_amount = sum(t.get('amount_usd', 0) for t in agent.external_wallet_transfers)
                reasonable_amounts = 1000 <= total_transfer_amount <= 6000  # 40% of $5,000 gain
            else:
                reasonable_amounts = False
            
            success = harvesting_executed and transfers_recorded and large_gain and reasonable_amounts
            
            print(f"Harvesting executed: {harvesting_executed}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Large gain: {large_gain}")
            print(f"Reasonable amounts: {reasonable_amounts}")
            print(f"Portfolio gain: ${portfolio_gain:.2f}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'harvesting_executed': harvesting_executed,
                    'transfers_recorded': transfers_recorded,
                    'large_gain': large_gain,
                    'reasonable_amounts': reasonable_amounts,
                    'portfolio_gain': portfolio_gain
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_multiple_consecutive_gains(self):
        """Test: Multiple Consecutive Gains"""
        test_name = "Multiple Consecutive Gains"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set initial portfolio value: $1000
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            previous_snapshot = MockSnapshot(1000.0)
            
            # Simulate first 5% gain
            self.simulator.simulate_portfolio_gains(5.0)  # 5% = $50
            current_snapshot = MockSnapshot(1050.0)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            mock_sol_transfer = MockSOLTransfer()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                
                # First gain
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                first_gains = agent.realized_gains_total
                
                # Second gain (simulate another 5% from $1050 = $52.50)
                second_previous = MockSnapshot(1050.0)
                second_current = MockSnapshot(1102.50)
                agent._handle_realized_gains(second_current, second_previous)
                final_gains = agent.realized_gains_total
            
            # Assert: Both gains should be harvested
            first_harvested = first_gains > initial_gains
            second_harvested = final_gains > first_gains
            cumulative_tracking = final_gains > initial_gains
            
            # Check transfer history
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            multiple_transfers = len(agent.external_wallet_transfers) >= 4  # 2 wallets × 2 gains
            
            success = (first_harvested and second_harvested and cumulative_tracking and 
                      transfers_recorded and multiple_transfers)
            
            print(f"First gain harvested: {first_harvested}")
            print(f"Second gain harvested: {second_harvested}")
            print(f"Cumulative tracking: {cumulative_tracking}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Multiple transfers: {multiple_transfers}")
            print(f"Final gains total: ${final_gains:.2f}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'first_harvested': first_harvested,
                    'second_harvested': second_harvested,
                    'cumulative_tracking': cumulative_tracking,
                    'transfers_recorded': transfers_recorded,
                    'multiple_transfers': multiple_transfers,
                    'final_gains_total': final_gains
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_negative_portfolio_change(self):
        """Test: Negative Portfolio Value Change"""
        test_name = "Negative Portfolio Value Change"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set initial portfolio value: $1000
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            previous_snapshot = MockSnapshot(1000.0)
            
            # Simulate portfolio loss
            self.simulator.simulate_portfolio_gains(-10.0)  # -10% = -$100
            current_snapshot = MockSnapshot(900.0)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Assert: No harvesting for losses
            no_harvesting = final_gains == initial_gains
            no_transfers = len(agent.external_wallet_transfers) == 0
            
            # Verify loss detection
            portfolio_change = current_snapshot.total_value_usd - previous_snapshot.total_value_usd
            is_loss = portfolio_change < 0
            
            success = no_harvesting and no_transfers and is_loss
            
            print(f"No harvesting: {no_harvesting}")
            print(f"No transfers: {no_transfers}")
            print(f"Is loss: {is_loss}")
            print(f"Portfolio change: ${portfolio_change:.2f}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'no_harvesting': no_harvesting,
                    'no_transfers': no_transfers,
                    'is_loss': is_loss,
                    'portfolio_change': portfolio_change
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_no_dust_positions(self):
        """Test: No Dust Positions"""
        test_name = "No Dust Positions"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set up portfolio with only large positions
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            large_tokens = create_test_token_addresses(3)
            large_values = [100.0, 200.0, 400.0]  # All above dust threshold
            self.simulator.create_dust_positions(large_tokens, large_values)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Assert: Should return gracefully with no operations
            graceful_return = success  # Should return True even with no dust
            no_jupiter_calls = len(mock_jupiter_swap.swap_calls) == 0
            
            # Verify no dust positions were found
            current_state = self.simulator.get_current_state()
            all_positions_large = all(
                value > 1.0 for value in current_state['positions'].values()
            )
            
            success_result = graceful_return and no_jupiter_calls and all_positions_large
            
            print(f"Graceful return: {graceful_return}")
            print(f"No Jupiter calls: {no_jupiter_calls}")
            print(f"All positions large: {all_positions_large}")
            print(f"Current positions: {current_state['positions']}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'graceful_return': graceful_return,
                    'no_jupiter_calls': no_jupiter_calls,
                    'all_positions_large': all_positions_large,
                    'current_positions': current_state['positions']
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_all_excluded_tokens_as_dust(self):
        """Test: All Excluded Tokens as Dust"""
        test_name = "All Excluded Tokens as Dust"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Create dust positions with only excluded tokens
            excluded_tokens = [SOL_ADDRESS, USDC_ADDRESS]
            dust_values = [0.50, 0.75]  # Both below dust threshold
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(excluded_tokens, dust_values)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Assert: No conversion attempts for excluded tokens
            graceful_return = success
            no_jupiter_calls = len(mock_jupiter_swap.swap_calls) == 0
            
            # Verify excluded tokens remain
            current_state = self.simulator.get_current_state()
            sol_remains = SOL_ADDRESS in current_state['positions'] and current_state['positions'][SOL_ADDRESS] > 0
            usdc_remains = USDC_ADDRESS in current_state['positions'] and current_state['positions'][USDC_ADDRESS] > 0
            
            success_result = graceful_return and no_jupiter_calls and sol_remains and usdc_remains
            
            print(f"Graceful return: {graceful_return}")
            print(f"No Jupiter calls: {no_jupiter_calls}")
            print(f"SOL remains: {sol_remains}")
            print(f"USDC remains: {usdc_remains}")
            print(f"Current positions: {current_state['positions']}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'graceful_return': graceful_return,
                    'no_jupiter_calls': no_jupiter_calls,
                    'sol_remains': sol_remains,
                    'usdc_remains': usdc_remains,
                    'current_positions': current_state['positions']
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_mixed_dust_and_large_positions(self):
        """Test: Mixed Dust and Large Positions"""
        test_name = "Mixed Dust and Large Positions"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Create mixed positions
            dust_tokens = create_test_token_addresses(3)
            large_tokens = create_test_token_addresses(3)
            dust_values = [0.50, 0.75, 0.25]  # Dust
            large_values = [100.0, 200.0, 300.0]  # Large
            
            all_tokens = dust_tokens + large_tokens
            all_values = dust_values + large_values
            
            self.simulator.set_portfolio_state(100.0, 200.0, 0.0)
            self.simulator.create_dust_positions(all_tokens, all_values)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Assert: Only dust should be converted
            conversion_success = success
            jupiter_calls = len(mock_jupiter_swap.swap_calls)
            expected_calls = len(dust_tokens)  # Only dust tokens
            
            # Verify dust removed and large positions remain
            current_state = self.simulator.get_current_state()
            dust_removed = all(
                token not in current_state['positions'] or current_state['positions'][token] == 0
                for token in dust_tokens
            )
            large_remain = all(
                token in current_state['positions'] and current_state['positions'][token] > 0
                for token in large_tokens
            )
            
            success_result = conversion_success and jupiter_calls == expected_calls and dust_removed and large_remain
            
            print(f"Conversion success: {conversion_success}")
            print(f"Jupiter calls: {jupiter_calls}/{expected_calls}")
            print(f"Dust removed: {dust_removed}")
            print(f"Large positions remain: {large_remain}")
            print(f"Current positions: {current_state['positions']}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': conversion_success,
                    'jupiter_calls': jupiter_calls,
                    'expected_calls': expected_calls,
                    'dust_removed': dust_removed,
                    'large_remain': large_remain,
                    'current_positions': current_state['positions']
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_dust_at_boundary(self):
        """Test: Dust at Boundary ($1.00 exactly)"""
        test_name = "Dust at Boundary ($1.00 exactly)"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Create dust position exactly at threshold
            dust_tokens = create_test_token_addresses(1)
            dust_values = [1.00]  # Exactly at $1.00 threshold
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Assert: Should convert (≤ threshold)
            conversion_success = success
            jupiter_called = len(mock_jupiter_swap.swap_calls) > 0
            
            # Verify dust was converted
            current_state = self.simulator.get_current_state()
            dust_converted = dust_tokens[0] not in current_state['positions'] or current_state['positions'][dust_tokens[0]] == 0
            
            success_result = conversion_success and jupiter_called and dust_converted
            
            print(f"Conversion success: {conversion_success}")
            print(f"Jupiter called: {jupiter_called}")
            print(f"Dust converted: {dust_converted}")
            print(f"Current positions: {current_state['positions']}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': conversion_success,
                    'jupiter_called': jupiter_called,
                    'dust_converted': dust_converted,
                    'current_positions': current_state['positions']
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_very_small_dust(self):
        """Test: Very Small Dust"""
        test_name = "Very Small Dust"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Create very small dust positions
            dust_tokens = create_test_token_addresses(3)
            dust_values = [0.01, 0.001, 0.0001]  # Very small amounts
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Assert: All should be converted
            conversion_success = success
            jupiter_calls = len(mock_jupiter_swap.swap_calls)
            expected_calls = len(dust_tokens)
            
            # Verify all dust was converted
            current_state = self.simulator.get_current_state()
            all_dust_converted = all(
                token not in current_state['positions'] or current_state['positions'][token] == 0
                for token in dust_tokens
            )
            
            success_result = conversion_success and jupiter_calls == expected_calls and all_dust_converted
            
            print(f"Conversion success: {conversion_success}")
            print(f"Jupiter calls: {jupiter_calls}/{expected_calls}")
            print(f"All dust converted: {all_dust_converted}")
            print(f"Current positions: {current_state['positions']}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': conversion_success,
                    'jupiter_calls': jupiter_calls,
                    'expected_calls': expected_calls,
                    'all_dust_converted': all_dust_converted,
                    'current_positions': current_state['positions']
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_missing_external_wallet_address(self):
        """Test: Missing External Wallet Address"""
        test_name = "Missing External Wallet Address"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set up portfolio for realized gains
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            previous_snapshot = MockSnapshot(1000.0)
            self.simulator.simulate_portfolio_gains(5.0)  # 5% increase
            current_snapshot = MockSnapshot(1050.0)
            
            # Create mock services with empty wallet addresses
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap), \
                 patch('src.config.EXTERNAL_WALLET_1', ''), \
                 patch('src.config.EXTERNAL_WALLET_2', ''), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            # Assert: Should handle gracefully with empty addresses
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Check for error status in transfers
            if transfers_recorded:
                error_statuses = [t.get('status', '') for t in agent.external_wallet_transfers]
                has_error_status = any('no_address' in status for status in error_statuses)
            else:
                has_error_status = False
            
            # Verify graceful failure
            graceful_failure = transfers_recorded and has_error_status
            
            success = graceful_failure
            
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Has error status: {has_error_status}")
            print(f"Graceful failure: {graceful_failure}")
            print(f"Transfer statuses: {[t.get('status', 'unknown') for t in agent.external_wallet_transfers]}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'transfers_recorded': transfers_recorded,
                    'has_error_status': has_error_status,
                    'graceful_failure': graceful_failure,
                    'transfer_statuses': [t.get('status', 'unknown') for t in agent.external_wallet_transfers]
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_external_wallets_disabled(self):
        """Test: External Wallets Disabled"""
        test_name = "External Wallets Disabled"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set up portfolio for realized gains
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            previous_snapshot = MockSnapshot(1000.0)
            self.simulator.simulate_portfolio_gains(5.0)  # 5% increase
            current_snapshot = MockSnapshot(1050.0)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap), \
                 patch('src.config.EXTERNAL_WALLET_ENABLED', False), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            # Assert: Should simulate transfers but not execute
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Check for disabled status
            if transfers_recorded:
                statuses = [t.get('status', '') for t in agent.external_wallet_transfers]
                has_disabled_status = any('disabled' in status for status in statuses)
            else:
                has_disabled_status = False
            
            success = transfers_recorded and has_disabled_status
            
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Has disabled status: {has_disabled_status}")
            print(f"Transfer statuses: {[t.get('status', 'unknown') for t in agent.external_wallet_transfers]}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'transfers_recorded': transfers_recorded,
                    'has_disabled_status': has_disabled_status,
                    'transfer_statuses': [t.get('status', 'unknown') for t in agent.external_wallet_transfers]
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_invalid_sol_price(self):
        """Test: Invalid SOL Price"""
        test_name = "Invalid SOL Price"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set up portfolio for realized gains
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            previous_snapshot = MockSnapshot(1000.0)
            self.simulator.simulate_portfolio_gains(5.0)  # 5% increase
            current_snapshot = MockSnapshot(1050.0)
            
            # Create mock services with invalid SOL price
            mock_price_service = MockPriceService(invalid_prices=True)
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            # Assert: Should handle invalid price gracefully
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Check for error status due to invalid price
            if transfers_recorded:
                statuses = [t.get('status', '') for t in agent.external_wallet_transfers]
                has_error_status = any('failed' in status for status in statuses)
            else:
                has_error_status = False
            
            # Verify graceful handling
            graceful_handling = not transfers_recorded or has_error_status
            
            success = graceful_handling
            
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Has error status: {has_error_status}")
            print(f"Graceful handling: {graceful_handling}")
            print(f"Transfer statuses: {[t.get('status', 'unknown') for t in agent.external_wallet_transfers]}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'transfers_recorded': transfers_recorded,
                    'has_error_status': has_error_status,
                    'graceful_handling': graceful_handling,
                    'transfer_statuses': [t.get('status', 'unknown') for t in agent.external_wallet_transfers]
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_jupiter_swap_fails(self):
        """Test: Jupiter Swap Fails"""
        test_name = "Jupiter Swap Fails"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set up portfolio for dust conversion
            dust_tokens = create_test_token_addresses(2)
            dust_values = [0.50, 0.75]
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            # Create mock services with failing Jupiter swap
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap(should_fail=True)
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Assert: Should handle swap failure gracefully
            graceful_handling = not success  # Should return False when swaps fail
            
            # Verify Jupiter was called but failed
            jupiter_calls = len(mock_jupiter_swap.swap_calls)
            expected_calls = len(dust_tokens)
            
            # Check that dust positions remain (conversion failed)
            current_state = self.simulator.get_current_state()
            dust_remains = any(
                token in current_state['positions'] and current_state['positions'][token] > 0
                for token in dust_tokens
            )
            
            success_result = graceful_handling and jupiter_calls == expected_calls and dust_remains
            
            print(f"Graceful handling: {graceful_handling}")
            print(f"Jupiter calls: {jupiter_calls}/{expected_calls}")
            print(f"Dust remains: {dust_remains}")
            print(f"Current positions: {current_state['positions']}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'graceful_handling': graceful_handling,
                    'jupiter_calls': jupiter_calls,
                    'expected_calls': expected_calls,
                    'dust_remains': dust_remains,
                    'current_positions': current_state['positions']
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_insufficient_balance_for_swap(self):
        """Test: Insufficient Balance for Swap"""
        test_name = "Insufficient Balance for Swap"
        print(f"\n{test_name}")
        print("-" * 40)
        
        try:
            # Set up portfolio for realized gains with very small USDC
            self.simulator.set_portfolio_state(100.0, 1.0, 700.0)  # Only $1 USDC
            previous_snapshot = MockSnapshot(1000.0)
            self.simulator.simulate_portfolio_gains(5.0)  # 5% increase = $50
            current_snapshot = MockSnapshot(1050.0)
            
            # Create mock services
            mock_price_service = MockPriceService()
            mock_api_manager = MockAPIManager()
            mock_data_coordinator = Mock()
            mock_jupiter_swap = MockJupiterSwap()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.nice_funcs', mock_jupiter_swap), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            # Assert: Should handle insufficient balance gracefully
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Check for error status due to insufficient balance
            if transfers_recorded:
                statuses = [t.get('status', '') for t in agent.external_wallet_transfers]
                has_error_status = any('failed' in status for status in statuses)
            else:
                has_error_status = False
            
            # Verify graceful handling
            graceful_handling = not transfers_recorded or has_error_status
            
            success = graceful_handling
            
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Has error status: {has_error_status}")
            print(f"Graceful handling: {graceful_handling}")
            print(f"Transfer statuses: {[t.get('status', 'unknown') for t in agent.external_wallet_transfers]}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'transfers_recorded': transfers_recorded,
                    'has_error_status': has_error_status,
                    'graceful_handling': graceful_handling,
                    'transfer_statuses': [t.get('status', 'unknown') for t in agent.external_wallet_transfers]
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
    test_suite = TestHarvestingEdgeCases()
    results = test_suite.run_all_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nSummary: {passed}/{total} edge case tests passed")
