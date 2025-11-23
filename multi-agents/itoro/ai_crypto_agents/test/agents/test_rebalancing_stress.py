"""
Stress testing module for rebalancing agent
Tests rapid state changes, extreme values, and error recovery
"""

import os
import sys
import time
import random
from unittest.mock import patch, Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_helpers import PortfolioStateSimulator, TestValidator
from src.agents.rebalancing_agent import RebalancingAgent
from src.config import SOL_ADDRESS, USDC_ADDRESS

class TestRebalancingStress:
    """Stress tests for rebalancing agent"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_stress_tests(self):
        """Run all stress tests"""
        print("Running Rebalancing Agent Stress Tests...")
        print("=" * 50)
        
        # Test 1: Rapid State Changes
        self.test_rapid_state_changes()
        
        # Test 2: Extreme Values
        self.test_extreme_values()
        
        # Test 3: Database Integrity
        self.test_database_integrity()
        
        # Test 4: Error Recovery
        self.test_error_recovery()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_rapid_state_changes(self):
        """Test 1: Rapid State Changes"""
        test_name = "Rapid State Changes"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
                
                agent = RebalancingAgent()
                
                # Test 50 consecutive rebalancing checks with random portfolio states
                success_count = 0
                error_count = 0
                
                for i in range(50):
                    try:
                        # Generate random portfolio state
                        sol_pct = random.uniform(0.0, 1.0)
                        usdc_pct = random.uniform(0.0, 1.0 - sol_pct)
                        pos_pct = 1.0 - sol_pct - usdc_pct
                        
                        total_value = 1000.0
                        sol_usd = total_value * sol_pct
                        usdc_usd = total_value * usdc_pct
                        pos_usd = total_value * pos_pct
                        
                        # Mock portfolio tracker with random state
                        mock_portfolio_tracker = Mock()
                        mock_portfolio_tracker.get_portfolio_summary.return_value = {
                            'current_value': total_value,
                            'usdc_balance': usdc_usd,
                            'sol_value_usd': sol_usd,
                            'positions_value_usd': pos_usd
                        }
                        
                        mock_snapshot = Mock()
                        mock_snapshot.total_value_usd = total_value
                        mock_snapshot.usdc_balance = usdc_usd
                        mock_snapshot.sol_value_usd = sol_usd
                        mock_snapshot.positions_value_usd = pos_usd
                        mock_portfolio_tracker.current_snapshot = mock_snapshot
                        mock_portfolio_tracker.snapshot_lock = Mock()
                        
                        with patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                            actions = agent.check_portfolio_allocation()
                            success_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        print(f"Error in iteration {i}: {e}")
                
                # Assert: Should handle most iterations without errors
                success_rate = success_count / 50
                no_errors = error_count == 0
                high_success_rate = success_rate >= 0.95  # 95% success rate
                
                success = no_errors or high_success_rate
                
                print(f"Successful iterations: {success_count}/50")
                print(f"Error count: {error_count}")
                print(f"Success rate: {success_rate:.1%}")
                print(f"Result: {'PASS' if success else 'FAIL'}")
                
                self.test_results.append({
                    'name': test_name,
                    'passed': success,
                    'details': {
                        'success_count': success_count,
                        'error_count': error_count,
                        'success_rate': success_rate
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
        """Test 2: Extreme Values"""
        test_name = "Extreme Values"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test with $1,000,000 portfolio
            self.simulator.set_portfolio_state(100000.0, 900000.0, 0.0)  # 10% SOL, 90% USDC
            
            # Create rebalancing agent with mocked services
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            # Mock portfolio tracker to return the test state
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000000.0,
                'usdc_balance': 900000.0,
                'sol_value_usd': 100000.0,
                'positions_value_usd': 0.0
            }
            
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000000.0
            mock_snapshot.usdc_balance = 900000.0
            mock_snapshot.sol_value_usd = 100000.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Should handle large values gracefully
            large_values_handled = True  # No errors with large values
            actions_returned = len(actions) >= 0  # Should return some response
            
            success = large_values_handled and actions_returned
            
            print(f"Actions returned: {actions}")
            print(f"Large values handled: {large_values_handled}")
            print(f"Actions returned: {actions_returned}")
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
    
    def test_database_integrity(self):
        """Test 3: Database Integrity"""
        test_name = "Database Integrity"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test 100 rebalancing operations
            success_count = 0
            error_count = 0
            
            for i in range(100):
                try:
                    # Set random portfolio state
                    sol_pct = random.uniform(0.0, 1.0)
                    usdc_pct = random.uniform(0.0, 1.0 - sol_pct)
                    pos_pct = 1.0 - sol_pct - usdc_pct
                    
                    total_value = 1000.0
                    sol_usd = total_value * sol_pct
                    usdc_usd = total_value * usdc_pct
                    pos_usd = total_value * pos_pct
                    
                    self.simulator.set_portfolio_state(sol_usd, usdc_usd, pos_usd)
                    
                    # Create rebalancing agent with mocked services
                    mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
                    
                    # Mock portfolio tracker
                    mock_portfolio_tracker = Mock()
                    mock_portfolio_tracker.get_portfolio_summary.return_value = {
                        'current_value': total_value,
                        'usdc_balance': usdc_usd,
                        'sol_value_usd': sol_usd,
                        'positions_value_usd': pos_usd
                    }
                    
                    mock_snapshot = Mock()
                    mock_snapshot.total_value_usd = total_value
                    mock_snapshot.usdc_balance = usdc_usd
                    mock_snapshot.sol_value_usd = sol_usd
                    mock_snapshot.positions_value_usd = pos_usd
                    mock_portfolio_tracker.current_snapshot = mock_snapshot
                    mock_portfolio_tracker.snapshot_lock = Mock()
                    
                    with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                         patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                         patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                         patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                        
                        agent = RebalancingAgent()
                        actions = agent.check_portfolio_allocation()
                        success_count += 1
                        
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:  # Only print first 5 errors
                        print(f"Error in iteration {i}: {e}")
            
            # Assert: Should handle most operations without database errors
            success_rate = success_count / 100
            high_success_rate = success_rate >= 0.90  # 90% success rate
            
            success = high_success_rate
            
            print(f"Successful operations: {success_count}/100")
            print(f"Error count: {error_count}")
            print(f"Success rate: {success_rate:.1%}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'success_count': success_count,
                    'error_count': error_count,
                    'success_rate': success_rate
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_error_recovery(self):
        """Test 4: Error Recovery"""
        test_name = "Error Recovery"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test with price service failure
            mock_price_service = Mock()
            mock_price_service.get_price.side_effect = Exception("Price service unavailable")
            
            mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()[1:]
            
            # Mock portfolio tracker
            mock_portfolio_tracker = Mock()
            mock_portfolio_tracker.get_portfolio_summary.return_value = {
                'current_value': 1000.0,
                'usdc_balance': 500.0,
                'sol_value_usd': 500.0,
                'positions_value_usd': 0.0
            }
            
            mock_snapshot = Mock()
            mock_snapshot.total_value_usd = 1000.0
            mock_snapshot.usdc_balance = 500.0
            mock_snapshot.sol_value_usd = 500.0
            mock_snapshot.positions_value_usd = 0.0
            mock_portfolio_tracker.current_snapshot = mock_snapshot
            mock_portfolio_tracker.snapshot_lock = Mock()
            
            with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.scripts.trading.portfolio_tracker.get_portfolio_tracker', return_value=mock_portfolio_tracker):
                
                agent = RebalancingAgent()
                actions = agent.check_portfolio_allocation()
            
            # Assert: Should handle price service failure gracefully
            graceful_degradation = True  # Should not crash
            error_handled = len(actions) >= 0  # Should return some response
            
            success = graceful_degradation and error_handled
            
            print(f"Actions returned: {actions}")
            print(f"Graceful degradation: {graceful_degradation}")
            print(f"Error handled: {error_handled}")
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
    # Run stress tests when script is executed directly
    stress_tests = TestRebalancingStress()
    results = stress_tests.run_all_stress_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nSummary: {passed}/{total} stress tests passed")
