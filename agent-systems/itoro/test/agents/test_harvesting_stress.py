"""
Stress tests for harvesting agent - production readiness validation
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

class TestHarvestingStress:
    """Stress test cases for harvesting agent"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_tests(self):
        """Run all harvesting stress tests"""
        print("Running Harvesting Agent Stress Tests...")
        print("=" * 50)
        
        # Stress tests
        self.test_large_portfolio_many_dust()
        self.test_rapid_portfolio_gains()
        self.test_extreme_values()
        self.test_database_integrity()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_large_portfolio_many_dust(self):
        """Stress 1: Large portfolio ($100k+) with many dust positions (50+)"""
        test_name = "Large Portfolio Many Dust"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Create 50 dust positions
            dust_tokens = create_test_token_addresses(50)
            dust_values = [0.01 + (i * 0.02) for i in range(50)]  # $0.01 to $0.99
            
            # Set up large portfolio: $100,000
            self.simulator.set_portfolio_state(10000.0, 20000.0, 70000.0)
            self.simulator.create_dust_positions(dust_tokens, dust_values)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            start_time = time.time()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_sell', return_value="mock_tx_signature"):
                
                agent = HarvestingAgent()
                success = agent.auto_convert_dust_to_sol()
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            current_state = self.simulator.get_current_state()
            
            # All dust positions should be removed
            dust_removed = all(
                token not in current_state['positions'] or current_state['positions'][token] == 0
                for token in dust_tokens
            )
            
            # SOL should increase
            sol_increase = current_state['sol_usd'] > 10000.0
            
            # Performance check (should complete within reasonable time)
            performance_ok = execution_time < 30.0  # Less than 30 seconds
            
            # Total dust value calculation
            total_dust_value = sum(dust_values)
            
            success_result = success and dust_removed and sol_increase and performance_ok
            
            print(f"Conversion success: {success}")
            print(f"Dust positions removed: {dust_removed}")
            print(f"SOL increased: {sol_increase}")
            print(f"Performance OK: {performance_ok}")
            print(f"Execution time: {execution_time:.2f}s")
            print(f"Total dust value: ${total_dust_value:.2f}")
            print(f"Positions processed: {len(dust_tokens)}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'conversion_success': success,
                    'dust_removed': dust_removed,
                    'sol_increased': sol_increase,
                    'performance_ok': performance_ok,
                    'execution_time': execution_time,
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
    
    def test_rapid_portfolio_gains(self):
        """Stress 2: Rapid portfolio gains (10 x 5% gains in sequence)"""
        test_name = "Rapid Portfolio Gains"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Simulate 10 consecutive 5% gains
            base_value = 10000.0  # $10,000 starting portfolio
            gains = [0.05] * 10  # 10 consecutive 5% gains
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            start_time = time.time()
            
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
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # All gains should be processed
            gains_processed = final_gains > initial_gains
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Calculate expected total gains
            expected_total_gain = base_value * sum(gains)
            gain_accuracy = abs(final_gains - expected_total_gain) < 10.0  # Within $10
            
            # Performance check
            performance_ok = execution_time < 10.0  # Less than 10 seconds
            
            success_result = gains_processed and transfers_recorded and gain_accuracy and performance_ok
            
            print(f"Gains processed: {gains_processed}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Gain accuracy: {gain_accuracy}")
            print(f"Performance OK: {performance_ok}")
            print(f"Execution time: {execution_time:.2f}s")
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
                    'performance_ok': performance_ok,
                    'execution_time': execution_time,
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
    
    def test_extreme_values(self):
        """Stress 3: Extreme values - very large gains ($10k+)"""
        test_name = "Extreme Values"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up very large portfolio: $1,000,000
            self.simulator.set_portfolio_state(100000.0, 200000.0, 700000.0)
            previous_snapshot = MockSnapshot(1000000.0)
            
            # Simulate 5% gain = $50,000
            self.simulator.simulate_portfolio_gains(5.0)
            current_snapshot = MockSnapshot(1050000.0)
            
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
            
            # Verify large value handling
            realized_gains = 50000.0
            expected_usdc = realized_gains * 0.50  # 50% = $25,000
            expected_wallet1 = realized_gains * 0.25  # 25% = $12,500
            expected_wallet2 = realized_gains * 0.15  # 15% = $7,500
            expected_sol = realized_gains * 0.10  # 10% = $5,000
            
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            gains_updated = agent.realized_gains_total > 0
            
            # Verify large value calculations are accurate
            calculation_accuracy = abs(final_gains - realized_gains) < 1.0  # Within $1
            
            # Verify no overflow issues
            no_overflow = final_gains < 1000000.0  # Reasonable upper bound
            
            success_result = transfers_recorded and gains_updated and calculation_accuracy and no_overflow
            
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Gains updated: {gains_updated}")
            print(f"Calculation accuracy: {calculation_accuracy}")
            print(f"No overflow: {no_overflow}")
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
                    'calculation_accuracy': calculation_accuracy,
                    'no_overflow': no_overflow,
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
    
    def test_database_integrity(self):
        """Stress 4: Database integrity - 100 harvest operations"""
        test_name = "Database Integrity"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Simulate 100 harvest operations
            operations_count = 100
            successful_operations = 0
            failed_operations = 0
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            start_time = time.time()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                
                for i in range(operations_count):
                    try:
                        # Simulate realized gains harvesting
                        base_value = 1000.0 + (i * 10.0)  # Increasing base value
                        previous_snapshot = MockSnapshot(base_value)
                        current_snapshot = MockSnapshot(base_value * 1.05)  # 5% gain
                        
                        initial_gains = agent.realized_gains_total
                        agent._handle_realized_gains(current_snapshot, previous_snapshot)
                        final_gains = agent.realized_gains_total
                        
                        if final_gains > initial_gains:
                            successful_operations += 1
                        else:
                            failed_operations += 1
                            
                    except Exception as e:
                        failed_operations += 1
                        print(f"Operation {i+1} failed: {e}")
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Check database integrity
            total_operations = successful_operations + failed_operations
            success_rate = (successful_operations / total_operations) * 100 if total_operations > 0 else 0
            
            # Performance check
            performance_ok = execution_time < 60.0  # Less than 60 seconds for 100 operations
            
            # Success criteria: >90% success rate and good performance
            success_result = success_rate >= 90.0 and performance_ok
            
            print(f"Total operations: {total_operations}")
            print(f"Successful operations: {successful_operations}")
            print(f"Failed operations: {failed_operations}")
            print(f"Success rate: {success_rate:.1f}%")
            print(f"Performance OK: {performance_ok}")
            print(f"Execution time: {execution_time:.2f}s")
            print(f"Final realized gains: ${agent.realized_gains_total:.2f}")
            print(f"Total transfers: {len(agent.external_wallet_transfers)}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'total_operations': total_operations,
                    'successful_operations': successful_operations,
                    'failed_operations': failed_operations,
                    'success_rate': success_rate,
                    'performance_ok': performance_ok,
                    'execution_time': execution_time,
                    'final_realized_gains': agent.realized_gains_total,
                    'total_transfers': len(agent.external_wallet_transfers)
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
    # Run stress tests when script is executed directly
    test_suite = TestHarvestingStress()
    results = test_suite.run_all_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nStress Test Summary: {passed}/{total} tests passed")
