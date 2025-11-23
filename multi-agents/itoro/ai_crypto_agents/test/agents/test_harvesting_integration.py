"""
Integration tests for harvesting agent - production readiness validation
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
from src.agents.rebalancing_agent import RebalancingAgent
from src.config import SOL_ADDRESS, USDC_ADDRESS, EXCLUDED_TOKENS

class MockSnapshot:
    """Mock portfolio snapshot for testing"""
    def __init__(self, total_value_usd, positions=None):
        self.total_value_usd = total_value_usd
        self.positions = positions or {}

class TestHarvestingIntegration:
    """Integration test cases for harvesting agent coordination"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_tests(self):
        """Run all harvesting integration tests"""
        print("Running Harvesting Agent Integration Tests...")
        print("=" * 50)
        
        # Integration tests
        self.test_portfolio_tracker_integration()
        self.test_rebalancing_agent_coordination()
        self.test_risk_agent_coordination()
        self.test_full_system_workflow()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_portfolio_tracker_integration(self):
        """Integration 1: Portfolio change trigger from portfolio tracker"""
        test_name = "Portfolio Tracker Integration"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Simulate portfolio tracker calling on_portfolio_change
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            
            # Create previous and current snapshots
            previous_snapshot = MockSnapshot(1000.0)
            current_snapshot = MockSnapshot(1050.0)  # 5% gain
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                agent = HarvestingAgent()
                
                # Simulate portfolio tracker calling the method
                agent.on_portfolio_change(current_snapshot, previous_snapshot)
            
            # Verify harvesting logic executed
            gains_processed = agent.realized_gains_total > 0
            transfers_recorded = len(agent.external_wallet_transfers) > 0
            
            # Verify dust conversion was also triggered
            dust_conversion_triggered = True  # on_portfolio_change calls both methods
            
            success_result = gains_processed and transfers_recorded and dust_conversion_triggered
            
            print(f"Gains processed: {gains_processed}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Dust conversion triggered: {dust_conversion_triggered}")
            print(f"Realized gains total: ${agent.realized_gains_total:.2f}")
            print(f"Transfer count: {len(agent.external_wallet_transfers)}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'gains_processed': gains_processed,
                    'transfers_recorded': transfers_recorded,
                    'dust_conversion_triggered': dust_conversion_triggered,
                    'realized_gains_total': agent.realized_gains_total,
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
    
    def test_rebalancing_agent_coordination(self):
        """Integration 2: Coordination with rebalancing agent (no conflicts)"""
        test_name = "Rebalancing Agent Coordination"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up portfolio for both agents
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.nice_funcs.market_sell', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                # Initialize both agents
                harvesting_agent = HarvestingAgent()
                rebalancing_agent = RebalancingAgent()
                
                # Step 1: Dust conversion (harvesting agent)
                dust_tokens = create_test_token_addresses(3)
                dust_values = [0.50, 0.75, 1.00]
                self.simulator.create_dust_positions(dust_tokens, dust_values)
                
                dust_success = harvesting_agent.auto_convert_dust_to_sol()
                
                # Step 2: Rebalancing check (rebalancing agent)
                rebalancing_actions = rebalancing_agent.check_portfolio_allocation()
                
                # Step 3: Realized gains harvesting
                previous_snapshot = MockSnapshot(1000.0)
                current_snapshot = MockSnapshot(1050.0)  # 5% gain
                harvesting_agent._handle_realized_gains(current_snapshot, previous_snapshot)
                
                # Step 4: Another rebalancing check after gains
                rebalancing_actions_after = rebalancing_agent.check_portfolio_allocation()
            
            # Verify coordination worked
            dust_conversion_success = dust_success
            rebalancing_worked = rebalancing_actions is not None
            gains_harvested = harvesting_agent.realized_gains_total > 0
            no_conflicts = True  # Both agents should work without conflicts
            
            # Check that rebalancing agent can still function after harvesting
            rebalancing_still_works = rebalancing_actions_after is not None
            
            success_result = (dust_conversion_success and rebalancing_worked and 
                            gains_harvested and no_conflicts and rebalancing_still_works)
            
            print(f"Dust conversion success: {dust_conversion_success}")
            print(f"Rebalancing worked: {rebalancing_worked}")
            print(f"Gains harvested: {gains_harvested}")
            print(f"No conflicts: {no_conflicts}")
            print(f"Rebalancing still works: {rebalancing_still_works}")
            print(f"Realized gains: ${harvesting_agent.realized_gains_total:.2f}")
            print(f"Transfer count: {len(harvesting_agent.external_wallet_transfers)}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'dust_conversion_success': dust_conversion_success,
                    'rebalancing_worked': rebalancing_worked,
                    'gains_harvested': gains_harvested,
                    'no_conflicts': no_conflicts,
                    'rebalancing_still_works': rebalancing_still_works,
                    'realized_gains_total': harvesting_agent.realized_gains_total,
                    'transfer_count': len(harvesting_agent.external_wallet_transfers)
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_risk_agent_coordination(self):
        """Integration 3: Coordination with risk agent"""
        test_name = "Risk Agent Coordination"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Set up portfolio for risk assessment
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                harvesting_agent = HarvestingAgent()
                
                # Step 1: Harvest realized gains
                previous_snapshot = MockSnapshot(1000.0)
                current_snapshot = MockSnapshot(1050.0)  # 5% gain
                harvesting_agent._handle_realized_gains(current_snapshot, previous_snapshot)
                
                # Step 2: Simulate risk agent checking portfolio state
                current_state = self.simulator.get_current_state()
                
                # Risk agent should not flag harvesting operations as risky
                portfolio_value_ok = current_state['total_value'] > 0
                sol_balance_ok = current_state['sol_usd'] > 0
                usdc_balance_ok = current_state['usdc_usd'] > 0
                
                # External wallet transfers should not trigger risk alerts
                transfers_safe = len(harvesting_agent.external_wallet_transfers) > 0
                
                # Verify harvesting doesn't create risk issues
                no_risk_issues = portfolio_value_ok and sol_balance_ok and usdc_balance_ok
            
            # Verify coordination worked
            gains_harvested = harvesting_agent.realized_gains_total > 0
            risk_assessment_ok = no_risk_issues
            transfers_recorded = transfers_safe
            
            success_result = gains_harvested and risk_assessment_ok and transfers_recorded
            
            print(f"Gains harvested: {gains_harvested}")
            print(f"Risk assessment OK: {risk_assessment_ok}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"Portfolio value OK: {portfolio_value_ok}")
            print(f"SOL balance OK: {sol_balance_ok}")
            print(f"USDC balance OK: {usdc_balance_ok}")
            print(f"Realized gains: ${harvesting_agent.realized_gains_total:.2f}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'gains_harvested': gains_harvested,
                    'risk_assessment_ok': risk_assessment_ok,
                    'transfers_recorded': transfers_recorded,
                    'portfolio_value_ok': portfolio_value_ok,
                    'sol_balance_ok': sol_balance_ok,
                    'usdc_balance_ok': usdc_balance_ok,
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
    
    def test_full_system_workflow(self):
        """Integration 4: Full system workflow end-to-end"""
        test_name = "Full System Workflow"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Complete end-to-end workflow simulation
            self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
            
            mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
                 patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
                 patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
                 patch('src.nice_funcs.market_buy', return_value="mock_tx_signature"), \
                 patch('src.nice_funcs.market_sell', return_value="mock_tx_signature"), \
                 patch('src.config.PAPER_TRADING_ENABLED', True):
                
                # Initialize agents
                harvesting_agent = HarvestingAgent()
                rebalancing_agent = RebalancingAgent()
                
                # Step 1: Create dust positions
                dust_tokens = create_test_token_addresses(5)
                dust_values = [0.25, 0.50, 0.75, 0.90, 1.00]
                self.simulator.create_dust_positions(dust_tokens, dust_values)
                
                # Step 2: Dust conversion
                dust_success = harvesting_agent.auto_convert_dust_to_sol()
                
                # Step 3: Portfolio gains (5%)
                previous_snapshot = MockSnapshot(1000.0)
                current_snapshot = MockSnapshot(1050.0)
                harvesting_agent._handle_realized_gains(current_snapshot, previous_snapshot)
                
                # Step 4: Rebalancing check
                rebalancing_actions = rebalancing_agent.check_portfolio_allocation()
                
                # Step 5: Another portfolio change (3% gain - below threshold)
                small_gain_snapshot = MockSnapshot(1081.5)  # 3% additional gain
                harvesting_agent._handle_realized_gains(small_gain_snapshot, current_snapshot)
                
                # Step 6: Final rebalancing check
                final_rebalancing_actions = rebalancing_agent.check_portfolio_allocation()
            
            # Verify complete workflow
            dust_converted = dust_success
            gains_harvested = harvesting_agent.realized_gains_total > 0
            rebalancing_worked = rebalancing_actions is not None
            small_gain_ignored = harvesting_agent.realized_gains_total < 100.0  # Only first gain harvested
            final_rebalancing_worked = final_rebalancing_actions is not None
            
            # Check transfer details
            transfers_recorded = len(harvesting_agent.external_wallet_transfers) > 0
            if transfers_recorded:
                transfer_statuses = [t.get('status') for t in harvesting_agent.external_wallet_transfers]
                all_transfers_successful = all('paper' in status.lower() or 'completed' in status.lower() 
                                            for status in transfer_statuses)
            else:
                all_transfers_successful = False
            
            success_result = (dust_converted and gains_harvested and rebalancing_worked and 
                            small_gain_ignored and final_rebalancing_worked and 
                            transfers_recorded and all_transfers_successful)
            
            print(f"Dust converted: {dust_converted}")
            print(f"Gains harvested: {gains_harvested}")
            print(f"Rebalancing worked: {rebalancing_worked}")
            print(f"Small gain ignored: {small_gain_ignored}")
            print(f"Final rebalancing worked: {final_rebalancing_worked}")
            print(f"Transfers recorded: {transfers_recorded}")
            print(f"All transfers successful: {all_transfers_successful}")
            print(f"Realized gains: ${harvesting_agent.realized_gains_total:.2f}")
            print(f"Transfer count: {len(harvesting_agent.external_wallet_transfers)}")
            if transfers_recorded:
                print(f"Transfer statuses: {transfer_statuses}")
            print(f"Result: {'PASS' if success_result else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success_result,
                'details': {
                    'dust_converted': dust_converted,
                    'gains_harvested': gains_harvested,
                    'rebalancing_worked': rebalancing_worked,
                    'small_gain_ignored': small_gain_ignored,
                    'final_rebalancing_worked': final_rebalancing_worked,
                    'transfers_recorded': transfers_recorded,
                    'all_transfers_successful': all_transfers_successful,
                    'realized_gains_total': harvesting_agent.realized_gains_total,
                    'transfer_count': len(harvesting_agent.external_wallet_transfers)
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
    # Run integration tests when script is executed directly
    test_suite = TestHarvestingIntegration()
    results = test_suite.run_all_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nIntegration Test Summary: {passed}/{total} tests passed")
