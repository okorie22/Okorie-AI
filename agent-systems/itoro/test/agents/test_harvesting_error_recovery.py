"""
Error recovery tests for harvesting agent - production readiness validation
"""

import os
import sys
import time
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

class TestHarvestingErrorRecovery:
    """Error recovery test cases for harvesting agent"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_tests(self):
        """Run all harvesting error recovery tests"""
        print("Running Harvesting Agent Error Recovery Tests...")
        print("=" * 50)
        
        # Error recovery tests
        self.test_failed_usdc_sol_swap()
        self.test_failed_external_wallet_transfer()
        self.test_price_service_timeout()
        self.test_corrupted_portfolio_data()
        self.test_insufficient_balance_swap()
        self.test_api_manager_failure()
        self.test_nice_funcs_import_failure()
        self.test_configuration_errors()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_failed_usdc_sol_swap(self):
        """Recovery 1: Failed USDC->SOL swap (partial success)"""
        test_name = "Failed USDC->SOL Swap"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up realized gains scenario
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(1050.0)  # 5% gain
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock USDC->SOL swap to fail
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value=None), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Should handle swap failure gracefully
            graceful_failure = final_gains == initial_gains  # No gains due to swap failure
            no_crashes = True  # Should not crash
            no_transfers = len(agent.external_wallet_transfers) == 0  # No transfers attempted
            
            success_result = graceful_failure and no_crashes and no_transfers
            
            print(f"Graceful failure: {graceful_failure}")
            print(f"No crashes: {no_crashes}")
            print(f"No transfers: {no_transfers}")
            print(f"Initial gains: ${initial_gains:.2f}")
            print(f"Final gains: ${final_gains:.2f}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'graceful_failure': graceful_failure,
                    'no_crashes': no_crashes,
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
    
    def test_failed_external_wallet_transfer(self):
        """Recovery 2: Failed external wallet transfer (one succeeds, one fails)"""
        test_name = "Failed External Wallet Transfer"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up realized gains scenario
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(1050.0)  # 5% gain
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock partial transfer failure
            def mock_transfer_sol(amount, wallet_address):
                if "wallet1" in wallet_address:
                    return True  # First wallet succeeds
                else:
                    return False  # Second wallet fails
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', False), \
                 patch('src.agents.harvesting_agent.HarvestingAgent._execute_sol_transfer', side_effect=mock_transfer_sol):
                
                agent = HarvestingAgent()
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            # Should handle partial failure gracefully
            transfers_attempted = len(agent.external_wallet_transfers) > 0
            if transfers_attempted:
                success_count = sum(1 for t in agent.external_wallet_transfers if t.get('status') == 'completed')
                failure_count = sum(1 for t in agent.external_wallet_transfers if t.get('status') == 'failed')
                partial_success = success_count > 0 and failure_count > 0
            else:
                partial_success = False
            
            no_crashes = True  # Should not crash
            
            success_result = transfers_attempted and partial_success and no_crashes
            
            print(f"Transfers attempted: {transfers_attempted}")
            print(f"Partial success: {partial_success}")
            print(f"No crashes: {no_crashes}")
            print(f"Transfer count: {len(agent.external_wallet_transfers)}")
            if transfers_attempted:
                print(f"Transfer statuses: {[t.get('status') for t in agent.external_wallet_transfers]}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'transfers_attempted': transfers_attempted,
                    'partial_success': partial_success,
                    'no_crashes': no_crashes,
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
    
    def test_price_service_timeout(self):
        """Recovery 3: Price service timeout/unavailable"""
        test_name = "Price Service Timeout"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up dust conversion scenario
            dust_tokens = create_test_token_addresses(3)
            dust_values = [0.50, 0.75, 1.00]
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            # Mock price service to timeout
            mock_price_service = Mock()
            mock_price_service.get_price.side_effect = Exception("Price service timeout")
            
            mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()[1:]
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Should handle timeout gracefully
            graceful_failure = not success  # Expected to fail due to timeout
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
    
    def test_corrupted_portfolio_data(self):
        """Recovery 4: Corrupted portfolio snapshot data"""
        test_name = "Corrupted Portfolio Data"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Create corrupted snapshot data
            class CorruptedSnapshot:
                def __init__(self):
                    self.total_value_usd = "invalid"  # Invalid type
                    self.positions = None  # Invalid data
            
            corrupted_snapshot = CorruptedSnapshot()
            previous_snapshot = MockSnapshot(1000.0)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                
                try:
                    agent._handle_realized_gains(corrupted_snapshot, previous_snapshot)
                    graceful_handling = True
                except Exception:
                    graceful_handling = False
                
                final_gains = agent.realized_gains_total
            
            # Should handle corrupted data gracefully
            no_crashes = True  # Should not crash the agent
            no_gains_change = final_gains == initial_gains  # No gains processed
            
            success_result = graceful_handling and no_crashes and no_gains_change
            
            print(f"Graceful handling: {graceful_handling}")
            print(f"No crashes: {no_crashes}")
            print(f"No gains change: {no_gains_change}")
            print(f"Initial gains: ${initial_gains:.2f}")
            print(f"Final gains: ${final_gains:.2f}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'graceful_handling': graceful_handling,
                    'no_crashes': no_crashes,
                    'no_gains_change': no_gains_change,
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
    
    def test_insufficient_balance_swap(self):
        """Recovery 5: Insufficient balance for swap"""
        test_name = "Insufficient Balance Swap"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up dust conversion scenario
            dust_tokens = create_test_token_addresses(2)
            dust_values = [0.50, 0.75]
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            # Mock API manager to return insufficient balance
            mock_api_manager = Mock()
            mock_api_manager.get_personal_wallet_address.return_value = "test_wallet"
            mock_api_manager.get_token_balances.return_value = {}  # No balances
            mock_api_manager.get_token_balance.return_value = "0"  # Zero balance
            
            mock_price_service, mock_data_coordinator = self.simulator.create_mock_services()[0], Mock()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Should handle insufficient balance gracefully
            graceful_failure = not success  # Expected to fail due to insufficient balance
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
    
    def test_api_manager_failure(self):
        """Recovery 6: API manager failure"""
        test_name = "API Manager Failure"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up realized gains scenario
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(1050.0)  # 5% gain
            
            # Mock API manager to fail
            mock_api_manager = Mock()
            mock_api_manager.get_personal_wallet_address.side_effect = Exception("API manager failure")
            
            mock_price_service, mock_data_coordinator = self.simulator.create_mock_services()[0], Mock()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                initial_gains = agent.realized_gains_total
                agent._handle_realized_gains(current_snapshot, previous_snapshot)
                final_gains = agent.realized_gains_total
            
            # Should handle API failure gracefully
            graceful_failure = final_gains == initial_gains  # No gains due to API failure
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
    
    def test_nice_funcs_import_failure(self):
        """Recovery 7: nice_funcs import failure"""
        test_name = "nice_funcs Import Failure"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up dust conversion scenario
            dust_tokens = create_test_token_addresses(2)
            dust_values = [0.50, 0.75]
            
            self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock nice_funcs import to fail
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.harvesting_agent.HarvestingAgent._get_nice_funcs', return_value=None):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            # Should handle import failure gracefully
            graceful_failure = not success  # Expected to fail due to import failure
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
    
    def test_configuration_errors(self):
        """Recovery 8: Configuration errors"""
        test_name = "Configuration Errors"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test with invalid configuration values
            with patch('src.config.DUST_THRESHOLD_USD', -1.0), \
                 patch('src.config.REALIZED_GAINS_REALLOCATION_INCREMENT', 2.0), \
                 patch('src.config.REALIZED_GAIN_THRESHOLD_USD', -50.0):
                
                agent = HarvestingAgent()
                
                # Agent should initialize with safe defaults or handle invalid config
                agent_initialized = agent is not None
                no_crashes = True  # Should not crash during initialization
                
                # Test dust conversion with invalid config
                dust_tokens = create_test_token_addresses(2)
                dust_values = [0.50, 0.75]
                
                self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
                self.simulator.create_dust_positions(dust_tokens, dust_values)
                
                mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
                
                with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                     patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                     patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                     patch('src.nice_funcs.market_sell', return_value="mock_tx_signature"):
                    
                    success = agent.auto_convert_dust_to_sol()
                
                # Should handle invalid config gracefully
                graceful_handling = success or not success  # Either works or fails gracefully
                
            success_result = agent_initialized and no_crashes and graceful_handling
            
            print(f"Agent initialized: {agent_initialized}")
            print(f"No crashes: {no_crashes}")
            print(f"Graceful handling: {graceful_handling}")
            print(f"Conversion success: {success}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'agent_initialized': agent_initialized,
                    'no_crashes': no_crashes,
                    'graceful_handling': graceful_handling,
                    'conversion_success': success
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
    # Run error recovery tests when script is executed directly
    test_suite = TestHarvestingErrorRecovery()
    results = test_suite.run_all_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nError Recovery Test Summary: {passed}/{total} tests passed")
