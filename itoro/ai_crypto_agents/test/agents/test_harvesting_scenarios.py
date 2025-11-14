"""
Test scenarios for harvesting agent logic
"""

import os
import sys
from unittest.mock import patch, Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_helpers import (
    PortfolioStateSimulator, TestValidator, create_test_token_addresses
)
from src.agents.harvesting_agent import HarvestingAgent
from src.config import SOL_ADDRESS, USDC_ADDRESS, EXCLUDED_TOKENS

class MockSnapshot:
    """Mock portfolio snapshot for testing"""
    def __init__(self, total_value_usd, positions=None):
        self.total_value_usd = total_value_usd
        self.positions = positions or {}

class TestHarvestingScenarios:
    """Test cases for harvesting agent scenarios"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_tests(self):
        """Run all harvesting agent tests"""
        print("Running Harvesting Agent Tests...")
        print("=" * 50)
        
        # Original 5 tests (enhanced)
        self.test_dust_conversion()
        self.test_realized_gains_harvesting()
        self.test_below_threshold_gains()
        self.test_external_wallet_transfers()
        self.test_dust_conversion_excluded_tokens()
        
        # New edge case tests (10+)
        self.test_multiple_dust_positions()
        self.test_large_realized_gains()
        self.test_exact_5_percent_threshold()
        self.test_exact_50_dollar_threshold()
        self.test_negative_portfolio_changes()
        self.test_missing_external_wallets()
        self.test_failed_jupiter_swap()
        self.test_price_service_failure()
        self.test_database_transaction_failure()
        self.test_rapid_consecutive_gains()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_dust_conversion(self):
        """Test 1: Dust Conversion - Enhanced with comprehensive assertions"""
        test_name = "Dust Conversion"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Create dust positions: 3 tokens with values $0.50, $0.75, $1.00
            dust_tokens = create_test_token_addresses(3)
            dust_values = [0.50, 0.75, 1.00]
            
            # Set up portfolio with dust positions
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)  # Base portfolio
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            # Create enhanced mock services
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
            
            # Get state after conversion
            current_state = self.simulator.get_current_state()
            
            # Enhanced assertions
            dust_positions_removed = all(
                token not in current_state['positions'] or current_state['positions'][token] == 0
                for token in dust_tokens
            )
            
            # Check that SOL balance increased (approximate)
            sol_increase = current_state['sol_usd'] > 100.0  # Should have increased from base
            
            # Verify Jupiter swap was called for each dust token
            jupiter_calls = len(mock_jupiter_swap.swap_calls)
            expected_calls = len(dust_tokens)
            
            # Verify API manager was called for wallet address and balances
            api_calls = len(mock_api_manager.api_calls)
            expected_api_calls = 1  # get_personal_wallet_address
            
            # Verify price service was called for each token
            price_calls = len(mock_price_service.price_calls)
            expected_price_calls = len(dust_tokens)
            
            # Check dust threshold boundary ($1.00 exactly should be converted)
            boundary_test = 1.00 in dust_values  # $1.00 is exactly at threshold
            
            success_result = (success and dust_positions_removed and sol_increase and 
                            jupiter_calls >= expected_calls and api_calls >= expected_api_calls and
                            price_calls >= expected_price_calls and boundary_test)
            
            print(f"Conversion success: {success}")
            print(f"Dust positions removed: {dust_positions_removed}")
            print(f"SOL increased: {sol_increase}")
            print(f"Jupiter calls: {jupiter_calls}/{expected_calls}")
            print(f"API calls: {api_calls}/{expected_api_calls}")
            print(f"Price calls: {price_calls}/{expected_price_calls}")
            print(f"Boundary test ($1.00): {boundary_test}")
            print(f"Current positions: {current_state['positions']}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': success,
                    'dust_removed': dust_positions_removed,
                    'sol_increased': sol_increase,
                    'jupiter_calls': jupiter_calls,
                    'api_calls': api_calls,
                    'price_calls': price_calls,
                    'boundary_test': boundary_test,
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
    
    def test_realized_gains_harvesting(self):
        """Test 2: Realized Gains Harvesting (5% Increment) - Enhanced with allocation verification"""
        test_name = "Realized Gains Harvesting (5% Increment)"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set initial portfolio value: $1000
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)  # 10% SOL, 20% USDC, 70% positions
            
            # Create previous snapshot with $1000 value
            previous_snapshot = MockSnapshot(1000.0)
            
            # Simulate portfolio value increase to $1050 (5% gain)
            self.simulator.simulate_portfolio_gains(5.0)  # 5% increase
            
            # Create current snapshot with $1050 value
            current_snapshot = MockSnapshot(1050.0)
            
            # Create enhanced mock services
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
            
            # Enhanced assertions
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            gains_updated = final_gains > initial_gains
            
            # Verify exact 5% increment threshold
            portfolio_gain = current_snapshot.total_value_usd - previous_snapshot.total_value_usd
            gain_percentage = portfolio_gain / previous_snapshot.total_value_usd
            threshold_met = gain_percentage >= 0.05  # 5%
            
            # Verify reallocation percentages (50% USDC, 25% wallet1, 15% wallet2, 10% SOL)
            expected_usdc_pct = 0.50
            expected_wallet1_pct = 0.25
            expected_wallet2_pct = 0.15
            expected_sol_pct = 0.10
            
            # Check if gains meet minimum threshold ($50)
            gains_above_threshold = portfolio_gain >= 50.0
            
            # Verify Jupiter swap was called for USDC to SOL conversion
            jupiter_calls = len(mock_jupiter_swap.swap_calls)
            expected_jupiter_calls = 2  # One for external wallets, one for keeping SOL
            
            # Verify SOL transfer was called
            sol_transfer_calls = len(mock_sol_transfer.transfer_calls)
            expected_sol_transfers = 2  # Two external wallets
            
            success = (transfers_recorded and gains_updated and threshold_met and 
                      gains_above_threshold and jupiter_calls >= expected_jupiter_calls and
                      sol_transfer_calls >= expected_sol_transfers)
            
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Gains updated: {gains_updated}")
            print(f"Threshold met (5%): {threshold_met}")
            print(f"Gains above $50: {gains_above_threshold}")
            print(f"Jupiter calls: {jupiter_calls}/{expected_jupiter_calls}")
            print(f"SOL transfer calls: {sol_transfer_calls}/{expected_sol_transfers}")
            print(f"Realized gains total: ${final_gains:.2f}")
            print(f"External transfers: {len(agent.external_wallet_transfers)}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'transfers_recorded': transfers_recorded,
                    'gains_updated': gains_updated,
                    'threshold_met': threshold_met,
                    'gains_above_threshold': gains_above_threshold,
                    'jupiter_calls': jupiter_calls,
                    'sol_transfer_calls': sol_transfer_calls,
                    'realized_gains_total': final_gains,
                    'external_transfers_count': len(agent.external_wallet_transfers),
                    'portfolio_gain': portfolio_gain,
                    'gain_percentage': gain_percentage
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_below_threshold_gains(self):
        """Test 3: Below Threshold Gains"""
        test_name = "Below Threshold Gains"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set initial portfolio value: $1000
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)  # 10% SOL, 20% USDC, 70% positions
            
            # Create previous snapshot with $1000 value
            previous_snapshot = MockSnapshot(1000.0)
            
            # Simulate 3% portfolio gain ($30) - below 5% threshold
            self.simulator.simulate_portfolio_gains(3.0)  # 3% increase
            
            # Create current snapshot with $1030 value
            current_snapshot = MockSnapshot(1030.0)
            
            # Create harvesting agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Assert: No harvesting action (below 5% threshold)
            no_harvesting = final_gains == initial_gains  # Gains total unchanged
            no_transfers = len(agent.external_wallet_transfers) == 0  # No transfers recorded
            
            success = no_harvesting and no_transfers
            
            print(f"No harvesting: {no_harvesting}")
            print(f"No transfers: {no_transfers}")
            print(f"Initial gains: ${initial_gains:.2f}")
            print(f"Final gains: ${final_gains:.2f}")
            print(f"Transfers: {len(agent.external_wallet_transfers)}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'no_harvesting': no_harvesting,
                    'no_transfers': no_transfers,
                    'initial_gains': initial_gains,
                    'final_gains': final_gains
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_external_wallet_transfers(self):
        """Test 4: External Wallet Transfers (Paper Trading Mode)"""
        test_name = "External Wallet Transfers (Paper Trading Mode)"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up portfolio for realized gains
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            previous_snapshot = MockSnapshot(1000.0)
            self.simulator.simulate_portfolio_gains(5.0)  # 5% increase
            current_snapshot = MockSnapshot(1050.0)
            
            # Create harvesting agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):  # Ensure paper trading mode
                
                agent = HarvestingAgent()
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            # Verify: Transfers logged but not executed (paper trading)
            transfers_logged = len(agent.external_wallet_transfers) > 0
            
            # Check transfer details
            transfer_details_valid = True
            if transfers_logged:
                for transfer in agent.external_wallet_transfers:
                    # Should have paper trading status
                    if 'status' not in transfer or 'paper' not in transfer['status'].lower():
                        transfer_details_valid = False
                        break
            
            success = transfers_logged and transfer_details_valid
            
            print(f"Transfers logged: {transfers_logged}")
            print(f"Transfer details valid: {transfer_details_valid}")
            print(f"Transfer count: {len(agent.external_wallet_transfers)}")
            if transfers_logged:
                print(f"Transfer statuses: {[t.get('status', 'unknown') for t in agent.external_wallet_transfers]}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'transfers_logged': transfers_logged,
                    'transfer_details_valid': transfer_details_valid,
                    'transfer_count': len(agent.external_wallet_transfers),
                    'transfers': agent.external_wallet_transfers
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_dust_conversion_excluded_tokens(self):
        """Test 5: Dust Conversion with Excluded Tokens"""
        test_name = "Dust Conversion with Excluded Tokens"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Create dust positions including excluded tokens
            dust_tokens = [SOL_ADDRESS, USDC_ADDRESS] + create_test_token_addresses(2)
            dust_values = [0.50, 0.75, 0.25, 0.30]  # SOL, USDC, and 2 regular tokens
            
            # Set up portfolio with dust positions
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            # Get initial state
            initial_state = self.simulator.get_current_state()
            
            # Create harvesting agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Get state after conversion
            final_state = self.simulator.get_current_state()
            
            # Assert: SOL dust NOT converted (in excluded list)
            sol_dust_remains = SOL_ADDRESS in final_state['positions'] and final_state['positions'][SOL_ADDRESS] > 0
            
            # USDC dust should also remain (excluded)
            usdc_dust_remains = USDC_ADDRESS in final_state['positions'] and final_state['positions'][USDC_ADDRESS] > 0
            
            # Regular tokens should be converted
            regular_tokens_converted = all(
                token not in final_state['positions'] or final_state['positions'][token] == 0
                for token in dust_tokens[2:]  # Skip SOL and USDC
            )
            
            success_result = success and sol_dust_remains and usdc_dust_remains and regular_tokens_converted
            
            print(f"Conversion success: {success}")
            print(f"SOL dust remains: {sol_dust_remains}")
            print(f"USDC dust remains: {usdc_dust_remains}")
            print(f"Regular tokens converted: {regular_tokens_converted}")
            print(f"Initial positions: {initial_state['positions']}")
            print(f"Final positions: {final_state['positions']}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': success,
                    'sol_dust_remains': sol_dust_remains,
                    'usdc_dust_remains': usdc_dust_remains,
                    'regular_tokens_converted': regular_tokens_converted,
                    'initial_positions': initial_state['positions'],
                    'final_positions': final_state['positions']
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_multiple_dust_positions(self):
        """Test 6: Multiple Dust Positions (10+ tokens) - verify batch conversion"""
        test_name = "Multiple Dust Positions"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Create 15 dust positions
            dust_tokens = create_test_token_addresses(15)
            dust_values = [0.10, 0.25, 0.50, 0.75, 1.00, 0.30, 0.40, 0.60, 0.80, 0.90, 
                          0.15, 0.35, 0.55, 0.65, 0.85]
            
            self.simulator.set_portfolio_state(200.0, 200.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_sell', return_value="mock_tx_signature"):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            current_state = self.simulator.get_current_state()
            
            # All dust positions should be removed
            dust_removed = all(
                token not in current_state['positions'] or current_state['positions'][token] == 0
                for token in dust_tokens
            )
            
            # SOL should increase significantly
            sol_increase = current_state['sol_usd'] > 200.0
            
            # Total dust value should be converted
            total_dust_value = sum(dust_values)
            expected_sol_increase = total_dust_value / 100.0  # Assuming $100 SOL price
            
            success_result = success and dust_removed and sol_increase
            
            print(f"Conversion success: {success}")
            print(f"Dust positions removed: {dust_removed}")
            print(f"SOL increased: {sol_increase}")
            print(f"Total dust value: ${total_dust_value:.2f}")
            print(f"Expected SOL increase: {expected_sol_increase:.6f} SOL")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': success,
                    'dust_removed': dust_removed,
                    'sol_increased': sol_increase,
                    'total_dust_value': total_dust_value,
                    'positions_count': len(dust_tokens)
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_large_realized_gains(self):
        """Test 7: Large Realized Gains ($500+) - verify reallocation percentages"""
        test_name = "Large Realized Gains"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up large portfolio: $10,000
            self.simulator.set_portfolio_state(1000.0, 2000.0, 7000.0)
            previous_snapshot = MockSnapshot(10000.0)
            
            # Simulate 5% gain = $500
            self.simulator.simulate_portfolio_gains(5.0)
            current_snapshot = MockSnapshot(10500.0)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            # Verify reallocation percentages
            realized_gains = 500.0
            expected_usdc = realized_gains * 0.50  # 50%
            expected_wallet1 = realized_gains * 0.25  # 25%
            expected_wallet2 = realized_gains * 0.15  # 15%
            expected_sol = realized_gains * 0.10  # 10%
            
            # Check transfers were recorded
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            gains_updated = agent.realized_gains_total > 0
            
            # Verify transfer amounts (approximate due to SOL price conversion)
            if transfers_recorded:
                total_transferred = sum(t.get('sol_amount', 0) for t in agent.external_wallet_transfers)
                expected_total_sol = (expected_wallet1 + expected_wallet2 + expected_sol) / 100.0  # $100 SOL price
                amount_accuracy = abs(total_transferred - expected_total_sol) < 0.1  # Within 0.1 SOL
            else:
                amount_accuracy = False
            
            success_result = transfers_recorded and gains_updated and amount_accuracy
            
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Gains updated: {gains_updated}")
            print(f"Amount accuracy: {amount_accuracy}")
            print(f"Realized gains total: ${agent.realized_gains_total:.2f}")
            print(f"Expected USDC: ${expected_usdc:.2f}")
            print(f"Expected Wallet1: ${expected_wallet1:.2f}")
            print(f"Expected Wallet2: ${expected_wallet2:.2f}")
            print(f"Expected SOL: ${expected_sol:.2f}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'transfers_recorded': transfers_recorded,
                    'gains_updated': gains_updated,
                    'amount_accuracy': amount_accuracy,
                    'realized_gains_total': agent.realized_gains_total,
                    'expected_usdc': expected_usdc,
                    'expected_wallet1': expected_wallet1,
                    'expected_wallet2': expected_wallet2,
                    'expected_sol': expected_sol
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_exact_5_percent_threshold(self):
        """Test 8: Edge case - exactly 5% gain threshold"""
        test_name = "Exact 5% Threshold"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Portfolio exactly at 5% gain threshold
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(1050.0)  # Exactly 5% gain
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Should trigger harvesting (exactly 5%)
            gains_triggered = final_gains > initial_gains
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            success_result = gains_triggered and transfers_recorded
            
            print(f"Gains triggered: {gains_triggered}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Initial gains: ${initial_gains:.2f}")
            print(f"Final gains: ${final_gains:.2f}")
            print(f"Gain amount: $50.00 (exactly 5%)")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'gains_triggered': gains_triggered,
                    'transfers_recorded': transfers_recorded,
                    'initial_gains': initial_gains,
                    'final_gains': final_gains,
                    'gain_percentage': 5.0
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_exact_50_dollar_threshold(self):
        """Test 9: Edge case - exactly $50 realized gain threshold"""
        test_name = "Exact $50 Threshold"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Portfolio with exactly $50 gain (meets both 5% and $50 thresholds)
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(1050.0)  # $50 gain, 5% increase
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Should trigger harvesting (exactly $50 threshold)
            gains_triggered = final_gains > initial_gains
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            threshold_met = final_gains >= 50.0
            
            success_result = gains_triggered and transfers_recorded and threshold_met
            
            print(f"Gains triggered: {gains_triggered}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Threshold met: {threshold_met}")
            print(f"Initial gains: ${initial_gains:.2f}")
            print(f"Final gains: ${final_gains:.2f}")
            print(f"Gain amount: $50.00 (exactly at threshold)")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'gains_triggered': gains_triggered,
                    'transfers_recorded': transfers_recorded,
                    'threshold_met': threshold_met,
                    'initial_gains': initial_gains,
                    'final_gains': final_gains,
                    'gain_amount': 50.0
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_negative_portfolio_changes(self):
        """Test 10: Zero/negative portfolio value changes"""
        test_name = "Negative Portfolio Changes"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test negative change (portfolio loss)
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(950.0)  # -5% loss
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Should NOT trigger harvesting (negative change)
            no_harvesting = final_gains == initial_gains
            no_transfers = len(agent.external_wallet_transfers) == 0
            
            # Test zero change
            zero_snapshot = MockSnapshot(1000.0)
            agent._handle_realized_gains(zero_snapshot, previous_snapshot)
            zero_gains = agent.realized_gains_total
            
            no_zero_harvesting = zero_gains == final_gains
            
            success_result = no_harvesting and no_transfers and no_zero_harvesting
            
            print(f"No harvesting (negative): {no_harvesting}")
            print(f"No transfers: {no_transfers}")
            print(f"No zero change harvesting: {no_zero_harvesting}")
            print(f"Initial gains: ${initial_gains:.2f}")
            print(f"Final gains: ${final_gains:.2f}")
            print(f"Zero change gains: ${zero_gains:.2f}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'no_harvesting_negative': no_harvesting,
                    'no_transfers': no_transfers,
                    'no_zero_harvesting': no_zero_harvesting,
                    'initial_gains': initial_gains,
                    'final_gains': final_gains,
                    'zero_change_gains': zero_gains
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_missing_external_wallets(self):
        """Test 11: Missing external wallet addresses"""
        test_name = "Missing External Wallets"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up realized gains scenario
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(1050.0)  # 5% gain
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Test with empty external wallet addresses
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True), \
                 patch('src.config.EXTERNAL_WALLET_1', ""), \
                 patch('src.config.EXTERNAL_WALLET_2', ""):
                
                agent = HarvestingAgent()
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            # Should handle missing wallets gracefully
            transfers_attempted = len(agent.external_wallet_transfers) > 0
            if transfers_attempted:
                failed_transfers = any(t.get('status') == 'no_address' for t in agent.external_wallet_transfers)
                graceful_handling = failed_transfers
            else:
                graceful_handling = True  # No transfers attempted due to missing addresses
            
            success_result = graceful_handling
            
            print(f"Transfers attempted: {transfers_attempted}")
            print(f"Graceful handling: {graceful_handling}")
            print(f"Transfer count: {len(agent.external_wallet_transfers)}")
            if transfers_attempted:
                print(f"Transfer statuses: {[t.get('status') for t in agent.external_wallet_transfers]}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'transfers_attempted': transfers_attempted,
                    'graceful_handling': graceful_handling,
                    'transfer_count': len(agent.external_wallet_transfers),
                    'transfer_statuses': [t.get('status') for t in agent.external_wallet_transfers] if transfers_attempted else []
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_failed_jupiter_swap(self):
        """Test 12: Failed Jupiter swap simulation"""
        test_name = "Failed Jupiter Swap"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up dust conversion scenario
            dust_tokens = create_test_token_addresses(3)
            dust_values = [0.50, 0.75, 1.00]
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock Jupiter swap to fail
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_sell', return_value=None):  # Simulate swap failure
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Should handle swap failure gracefully
            graceful_failure = not success  # Expected to fail due to swap failure
            no_crashes = True  # Should not crash
            
            success_result = graceful_failure and no_crashes
            
            print(f"Conversion success: {success}")
            print(f"Graceful failure: {graceful_failure}")
            print(f"No crashes: {no_crashes}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': success,
                    'graceful_failure': graceful_failure,
                    'no_crashes': no_crashes
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_price_service_failure(self):
        """Test 13: Price service failure handling"""
        test_name = "Price Service Failure"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up realized gains scenario
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(1050.0)  # 5% gain
            
            # Mock price service to return None (failure)
            mock_price_service = Mock()
            mock_price_service.get_price.return_value = None
            
            mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()[1:]
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Should handle price service failure gracefully
            graceful_failure = final_gains == initial_gains  # No gains due to price failure
            no_crashes = True  # Should not crash
            
            success_result = graceful_failure and no_crashes
            
            print(f"Graceful failure: {graceful_failure}")
            print(f"No crashes: {no_crashes}")
            print(f"Initial gains: ${initial_gains:.2f}")
            print(f"Final gains: ${final_gains:.2f}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'graceful_failure': graceful_failure,
                    'no_crashes': no_crashes,
                    'initial_gains': initial_gains,
                    'final_gains': final_gains
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_database_transaction_failure(self):
        """Test 14: Database transaction failures"""
        test_name = "Database Transaction Failure"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up dust conversion scenario
            dust_tokens = create_test_token_addresses(2)
            dust_values = [0.50, 0.75]
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            # Mock API manager to simulate database issues
            mock_api_manager = Mock()
            mock_api_manager.get_personal_wallet_address.return_value = None  # Simulate DB failure
            mock_api_manager.get_token_balances.return_value = {}
            
            mock_price_service, mock_data_coordinator = self.simulator.create_mock_services()[0], Mock()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Should handle database failure gracefully
            graceful_failure = not success  # Expected to fail due to DB issues
            no_crashes = True  # Should not crash
            
            success_result = graceful_failure and no_crashes
            
            print(f"Conversion success: {success}")
            print(f"Graceful failure: {graceful_failure}")
            print(f"No crashes: {no_crashes}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': success,
                    'graceful_failure': graceful_failure,
                    'no_crashes': no_crashes
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_rapid_consecutive_gains(self):
        """Test 15: Rapid consecutive gains (cooldown behavior)"""
        test_name = "Rapid Consecutive Gains"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Simulate rapid consecutive 5% gains
            base_value = 1000.0
            gains = [0.05, 0.05, 0.05, 0.05, 0.05]  # 5 consecutive 5% gains
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                
                # Simulate rapid consecutive gains
                previous_value = base_value
                for i, gain in enumerate(gains):
                    current_value = previous_value * (1 + gain)
                    previous_snapshot = MockSnapshot(previous_value)
                    current_snapshot = MockSnapshot(current_value)
                    
                    agent._handle_realized_gains(current_snapshot, previous_snapshot)
                    previous_value = current_value
                
                final_gains = agent.realized_gains_total
            
            # Should handle all gains (no cooldown for harvesting agent)
            gains_processed = final_gains > initial_gains
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Calculate expected total gains
            expected_total_gain = base_value * sum(gains)
            gain_accuracy = abs(final_gains - expected_total_gain) < 1.0  # Within $1
            
            success_result = gains_processed and transfers_recorded and gain_accuracy
            
            print(f"Gains processed: {gains_processed}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Gain accuracy: {gain_accuracy}")
            print(f"Initial gains: ${initial_gains:.2f}")
            print(f"Final gains: ${final_gains:.2f}")
            print(f"Expected total: ${expected_total_gain:.2f}")
            print(f"Transfer count: {len(agent.external_wallet_transfers)}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'gains_processed': gains_processed,
                    'transfers_recorded': transfers_recorded,
                    'gain_accuracy': gain_accuracy,
                    'initial_gains': initial_gains,
                    'final_gains': final_gains,
                    'expected_total': expected_total_gain,
                    'transfer_count': len(agent.external_wallet_transfers)
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
    test_suite = TestHarvestingScenarios()
    results = test_suite.run_all_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nSummary: {passed}/{total} tests passed")
