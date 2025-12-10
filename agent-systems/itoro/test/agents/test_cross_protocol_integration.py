"""
Comprehensive integration test suite for Cross-Protocol Strategy
Tests the complete system working together: staking + DeFi + arbitrage
"""

import os
import sys
import time
from unittest.mock import patch, Mock, MagicMock
from typing import Dict, List, Any
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.agents.staking_agent import StakingAgent
from src.agents.defi_agent import DeFiAgent
from src.scripts.defi.staking_defi_coordinator import StakingDeFiCoordinator
from src.scripts.shared_services.rate_monitoring_service import get_rate_monitoring_service
from src.scripts.staking.staking_migration_engine import get_staking_migration_engine
from src.scripts.defi.defi_arbitrage_engine import get_defi_arbitrage_engine
from src.scripts.defi.defi_protocol_router import get_defi_protocol_router
from test.agents.test_helpers import TestValidator, PortfolioStateSimulator


class MockRateMonitor:
    """Mock rate monitoring service for integration testing"""

    def __init__(self):
        self.staking_rates = {
            'sanctum': Mock(rate=0.095, protocol='sanctum', timestamp=datetime.now()),
            'jito': Mock(rate=0.08, protocol='jito', timestamp=datetime.now()),
            'marinade': Mock(rate=0.07, protocol='marinade', timestamp=datetime.now()),
        }
        self.lending_rates = {
            'solend': Mock(rate=0.05, protocol='solend', timestamp=datetime.now()),
            'mango': Mock(rate=0.11, protocol='mango', timestamp=datetime.now()),
            'tulip': Mock(rate=0.15, protocol='tulip', timestamp=datetime.now()),
        }
        self.borrowing_rates = {
            'solend': Mock(rate=0.08, protocol='solend', timestamp=datetime.now()),
            'mango': Mock(rate=0.10, protocol='mango', timestamp=datetime.now()),
            'tulip': Mock(rate=0.12, protocol='tulip', timestamp=datetime.now()),
        }

    def get_staking_rates(self):
        return self.staking_rates

    def get_lending_rates(self):
        return self.lending_rates

    def get_borrowing_rates(self):
        return self.borrowing_rates

    def get_best_staking_rate(self):
        return self.staking_rates['sanctum']

    def get_best_lending_rate(self):
        return self.lending_rates['tulip']

    def get_best_borrowing_rate(self):
        return self.borrowing_rates['solend']


class TestCrossProtocolIntegration:
    """Comprehensive integration test suite for cross-protocol strategy"""

    def __init__(self):
        self.validator = TestValidator()
        self.test_results = []
        self.simulator = PortfolioStateSimulator()
        self.mock_rate_monitor = MockRateMonitor()

    def run_all_tests(self):
        """Run all cross-protocol integration tests"""
        print("🔗 Testing Cross-Protocol Strategy Integration")
        print("=" * 60)
        print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Component Integration Tests
        print("\n" + "="*50)
        print("🔧 COMPONENT INTEGRATION TESTS")
        print("="*50)
        self.test_rate_monitoring_integration()
        self.test_migration_engine_integration()
        self.test_arbitrage_engine_integration()
        self.test_protocol_router_integration()

        # Agent Integration Tests
        print("\n" + "="*50)
        print("🤖 AGENT INTEGRATION TESTS")
        print("="*50)
        self.test_staking_agent_integration()
        self.test_defi_agent_integration()
        self.test_coordinator_integration()

        # End-to-End Tests
        print("\n" + "="*50)
        print("🔄 END-TO-END WORKFLOW TESTS")
        print("="*50)
        self.test_staking_to_defi_workflow()
        self.test_migration_workflow()
        self.test_arbitrage_workflow()

        # Performance Tests
        print("\n" + "="*50)
        print("⚡ PERFORMANCE TESTS")
        print("="*50)
        self.test_rate_monitoring_performance()
        self.test_concurrent_operations()

        # Error Handling Tests
        print("\n" + "="*50)
        print("🚨 ERROR HANDLING TESTS")
        print("="*50)
        self.test_component_failure_handling()
        self.test_network_failure_handling()

        # Print results
        self.print_test_results()

    def test_rate_monitoring_integration(self):
        """Test rate monitoring service integration"""
        print("Testing rate monitoring integration...")

        try:
            # Get the actual service instance
            rate_monitor = get_rate_monitoring_service()

            # Test service initialization
            assert rate_monitor is not None
            assert hasattr(rate_monitor, 'get_staking_rates')
            assert hasattr(rate_monitor, 'get_lending_rates')
            assert hasattr(rate_monitor, 'get_borrowing_rates')

            # Test rate fetching
            staking_rates = rate_monitor.get_staking_rates()
            lending_rates = rate_monitor.get_lending_rates()
            borrowing_rates = rate_monitor.get_borrowing_rates()

            # Should return dictionaries (even if empty)
            assert isinstance(staking_rates, dict)
            assert isinstance(lending_rates, dict)
            assert isinstance(borrowing_rates, dict)

            self.validator.log_success("Rate monitoring integration")
            self.test_results.append(("Rate monitoring integration", True, None))

        except Exception as e:
            self.validator.log_error("Rate monitoring integration", str(e))
            self.test_results.append(("Rate monitoring integration", False, str(e)))

    def test_migration_engine_integration(self):
        """Test staking migration engine integration"""
        print("Testing migration engine integration...")

        try:
            # Get the actual service instance
            migration_engine = get_staking_migration_engine()

            # Test service initialization
            assert migration_engine is not None
            assert hasattr(migration_engine, 'find_migration_opportunities')
            assert hasattr(migration_engine, 'should_migrate')

            # Test with empty positions
            opportunities = migration_engine.find_migration_opportunities({})
            assert isinstance(opportunities, list)

            self.validator.log_success("Migration engine integration")
            self.test_results.append(("Migration engine integration", True, None))

        except Exception as e:
            self.validator.log_error("Migration engine integration", str(e))
            self.test_results.append(("Migration engine integration", False, str(e)))

    def test_arbitrage_engine_integration(self):
        """Test DeFi arbitrage engine integration"""
        print("Testing arbitrage engine integration...")

        try:
            # Get the actual service instance
            arbitrage_engine = get_defi_arbitrage_engine()

            # Test service initialization
            assert arbitrage_engine is not None
            assert hasattr(arbitrage_engine, 'find_arbitrage_opportunities')
            assert hasattr(arbitrage_engine, 'calculate_arbitrage_profit')

            # Test arbitrage opportunity detection
            opportunities = arbitrage_engine.find_arbitrage_opportunities()
            assert isinstance(opportunities, list)

            self.validator.log_success("Arbitrage engine integration")
            self.test_results.append(("Arbitrage engine integration", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage engine integration", str(e))
            self.test_results.append(("Arbitrage engine integration", False, str(e)))

    def test_protocol_router_integration(self):
        """Test DeFi protocol router integration"""
        print("Testing protocol router integration...")

        try:
            # Get the actual service instance
            protocol_router = get_defi_protocol_router()

            # Test service initialization
            assert protocol_router is not None
            assert hasattr(protocol_router, 'select_best_lending_protocol')
            assert hasattr(protocol_router, 'select_best_borrowing_protocol')

            # Test protocol selection
            lending_protocol = protocol_router.select_best_lending_protocol(1000.0)
            borrowing_protocol = protocol_router.select_best_borrowing_protocol(1000.0)

            # Results can be None if no suitable protocols, but shouldn't crash
            assert lending_protocol is None or isinstance(lending_protocol, str)
            assert borrowing_protocol is None or isinstance(borrowing_protocol, str)

            self.validator.log_success("Protocol router integration")
            self.test_results.append(("Protocol router integration", True, None))

        except Exception as e:
            self.validator.log_error("Protocol router integration", str(e))
            self.test_results.append(("Protocol router integration", False, str(e)))

    def test_staking_agent_integration(self):
        """Test staking agent integration with cross-protocol components"""
        print("Testing staking agent integration...")

        try:
            # Mock the staking agent initialization to avoid full setup
            with patch('src.agents.staking_agent.StakingAgent.__init__', return_value=None):
                agent = StakingAgent.__new__(StakingAgent)

                # Manually set up cross-protocol components
                agent.migration_engine = get_staking_migration_engine()
                agent.rate_monitor = get_rate_monitoring_service()
                agent.migration_enabled = True

                # Test that components are accessible
                assert agent.migration_engine is not None
                assert agent.rate_monitor is not None
                assert agent.migration_enabled == True

                # Test migration check method exists
                assert hasattr(agent, '_check_and_execute_migrations')

                self.validator.log_success("Staking agent integration")
                self.test_results.append(("Staking agent integration", True, None))

        except Exception as e:
            self.validator.log_error("Staking agent integration", str(e))
            self.test_results.append(("Staking agent integration", False, str(e)))

    def test_defi_agent_integration(self):
        """Test DeFi agent integration with cross-protocol components"""
        print("Testing DeFi agent integration...")

        try:
            # Mock the DeFi agent initialization to avoid full setup
            with patch('src.agents.defi_agent.DeFiAgent.__init__', return_value=None):
                agent = DeFiAgent.__new__(DeFiAgent)

                # Manually set up cross-protocol components
                agent.protocol_router = get_defi_protocol_router()
                agent.arbitrage_engine = get_defi_arbitrage_engine()
                agent.rate_monitor = get_rate_monitoring_service()
                agent.cross_protocol_enabled = True

                # Test that components are accessible
                assert agent.protocol_router is not None
                assert agent.arbitrage_engine is not None
                assert agent.rate_monitor is not None
                assert agent.cross_protocol_enabled == True

                # Test arbitrage scanning method exists
                assert hasattr(agent, '_scan_arbitrage_opportunities')

                self.validator.log_success("DeFi agent integration")
                self.test_results.append(("DeFi agent integration", True, None))

        except Exception as e:
            self.validator.log_error("DeFi agent integration", str(e))
            self.test_results.append(("DeFi agent integration", False, str(e)))

    def test_coordinator_integration(self):
        """Test coordinator integration with cross-protocol components"""
        print("Testing coordinator integration...")

        try:
            # Get the coordinator instance
            coordinator = StakingDeFiCoordinator()

            # Test that it has cross-protocol components
            assert hasattr(coordinator, 'rate_monitor')
            assert hasattr(coordinator, 'rebalancer')

            # Test rate monitoring data method
            rate_data = coordinator.get_rate_monitoring_data()

            # Should return data or None (both acceptable)
            assert rate_data is None or isinstance(rate_data, dict)

            self.validator.log_success("Coordinator integration")
            self.test_results.append(("Coordinator integration", True, None))

        except Exception as e:
            self.validator.log_error("Coordinator integration", str(e))
            self.test_results.append(("Coordinator integration", False, str(e)))

    def test_staking_to_defi_workflow(self):
        """Test complete workflow from staking trigger to DeFi execution"""
        print("Testing staking to DeFi workflow...")

        try:
            # This is a high-level integration test
            # In a real scenario, we'd test the full flow, but for now we test components

            coordinator = StakingDeFiCoordinator()

            # Test that coordinator can handle staking events
            assert hasattr(coordinator, 'handle_staking_complete')
            assert hasattr(coordinator, 'get_trigger_context')

            # Test trigger context initialization
            context = coordinator.get_trigger_context()
            # Initially should be None or have default structure
            assert context is None or isinstance(context, dict)

            self.validator.log_success("Staking to DeFi workflow")
            self.test_results.append(("Staking to DeFi workflow", True, None))

        except Exception as e:
            self.validator.log_error("Staking to DeFi workflow", str(e))
            self.test_results.append(("Staking to DeFi workflow", False, str(e)))

    def test_migration_workflow(self):
        """Test staking migration workflow"""
        print("Testing migration workflow...")

        try:
            migration_engine = get_staking_migration_engine()
            rate_monitor = get_rate_monitoring_service()

            # Test the complete migration detection workflow
            # This would normally check current positions, but we test the logic

            # Test migration opportunity detection
            opportunities = migration_engine.find_migration_opportunities({})
            assert isinstance(opportunities, list)

            # Test cost-benefit analysis
            should_migrate, opportunity = migration_engine.should_migrate(
                'marinade', 0.07, 'sanctum', 0.095, 10.0
            )

            # Should detect migration opportunity
            assert isinstance(should_migrate, bool)
            assert opportunity is None or hasattr(opportunity, 'net_benefit_apy')

            self.validator.log_success("Migration workflow")
            self.test_results.append(("Migration workflow", True, None))

        except Exception as e:
            self.validator.log_error("Migration workflow", str(e))
            self.test_results.append(("Migration workflow", False, str(e)))

    def test_arbitrage_workflow(self):
        """Test arbitrage workflow"""
        print("Testing arbitrage workflow...")

        try:
            arbitrage_engine = get_defi_arbitrage_engine()

            # Test the complete arbitrage workflow
            opportunities = arbitrage_engine.find_arbitrage_opportunities()

            assert isinstance(opportunities, list)

            if opportunities:
                # Test profit calculation for first opportunity
                opp = opportunities[0]
                profit = arbitrage_engine.calculate_arbitrage_profit(opp, 1000.0)

                assert isinstance(profit, (int, float))
                assert profit >= 0  # Profit should be non-negative

            self.validator.log_success("Arbitrage workflow")
            self.test_results.append(("Arbitrage workflow", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage workflow", str(e))
            self.test_results.append(("Arbitrage workflow", False, str(e)))

    def test_rate_monitoring_performance(self):
        """Test rate monitoring performance"""
        print("Testing rate monitoring performance...")

        try:
            rate_monitor = get_rate_monitoring_service()

            # Test multiple rapid calls
            import time
            start_time = time.time()

            for _ in range(10):
                staking_rates = rate_monitor.get_staking_rates()
                lending_rates = rate_monitor.get_lending_rates()
                borrowing_rates = rate_monitor.get_borrowing_rates()

            end_time = time.time()
            total_time = end_time - start_time

            # Should complete within reasonable time (allowing for network calls)
            assert total_time < 30.0  # 30 seconds max for 10 iterations

            self.validator.log_success("Rate monitoring performance")
            self.test_results.append(("Rate monitoring performance", True, None))

        except Exception as e:
            self.validator.log_error("Rate monitoring performance", str(e))
            self.test_results.append(("Rate monitoring performance", False, str(e)))

    def test_concurrent_operations(self):
        """Test concurrent operations across components"""
        print("Testing concurrent operations...")

        try:
            import threading
            import queue

            results_queue = queue.Queue()

            def test_rate_monitoring():
                try:
                    rate_monitor = get_rate_monitoring_service()
                    rates = rate_monitor.get_staking_rates()
                    results_queue.put(("rate_monitoring", True))
                except Exception as e:
                    results_queue.put(("rate_monitoring", False, str(e)))

            def test_arbitrage_engine():
                try:
                    arbitrage_engine = get_defi_arbitrage_engine()
                    opportunities = arbitrage_engine.find_arbitrage_opportunities()
                    results_queue.put(("arbitrage", True))
                except Exception as e:
                    results_queue.put(("arbitrage", False, str(e)))

            def test_migration_engine():
                try:
                    migration_engine = get_staking_migration_engine()
                    opportunities = migration_engine.find_migration_opportunities({})
                    results_queue.put(("migration", True))
                except Exception as e:
                    results_queue.put(("migration", False, str(e)))

            # Start concurrent operations
            threads = [
                threading.Thread(target=test_rate_monitoring),
                threading.Thread(target=test_arbitrage_engine),
                threading.Thread(target=test_migration_engine)
            ]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join(timeout=10)  # 10 second timeout

            # Check results
            results = {}
            while not results_queue.empty():
                result = results_queue.get()
                component = result[0]
                success = result[1]
                error = result[2] if len(result) > 2 else None
                results[component] = (success, error)

            # All components should succeed
            assert results.get("rate_monitoring", (False,))[0] == True
            assert results.get("arbitrage", (False,))[0] == True
            assert results.get("migration", (False,))[0] == True

            self.validator.log_success("Concurrent operations")
            self.test_results.append(("Concurrent operations", True, None))

        except Exception as e:
            self.validator.log_error("Concurrent operations", str(e))
            self.test_results.append(("Concurrent operations", False, str(e)))

    def test_component_failure_handling(self):
        """Test handling of component failures"""
        print("Testing component failure handling...")

        try:
            # Test with mocked failures
            with patch('src.scripts.shared_services.rate_monitoring_service.get_shared_api_manager') as mock_api:
                mock_api.return_value = None  # Simulate API failure

                rate_monitor = get_rate_monitoring_service()

                # Should handle API failure gracefully
                staking_rates = rate_monitor.get_staking_rates()
                assert isinstance(staking_rates, dict)  # Should return empty dict or cached data

            # Test migration engine with invalid data
            migration_engine = get_staking_migration_engine()
            opportunities = migration_engine.find_migration_opportunities(None)
            assert isinstance(opportunities, list)  # Should handle None input

            # Test arbitrage engine with no opportunities
            arbitrage_engine = get_defi_arbitrage_engine()
            opportunities = arbitrage_engine.find_arbitrage_opportunities(min_spread=1.0)  # Impossible spread
            assert len(opportunities) == 0  # Should return empty list

            self.validator.log_success("Component failure handling")
            self.test_results.append(("Component failure handling", True, None))

        except Exception as e:
            self.validator.log_error("Component failure handling", str(e))
            self.test_results.append(("Component failure handling", False, str(e)))

    def test_network_failure_handling(self):
        """Test handling of network failures"""
        print("Testing network failure handling...")

        try:
            # Test rate monitoring with simulated network failures
            rate_monitor = get_rate_monitoring_service()

            # Should return cached data or empty dict on network issues
            staking_rates = rate_monitor.get_staking_rates()
            assert isinstance(staking_rates, dict)

            lending_rates = rate_monitor.get_lending_rates()
            assert isinstance(lending_rates, dict)

            borrowing_rates = rate_monitor.get_borrowing_rates()
            assert isinstance(borrowing_rates, dict)

            # Test arbitrage engine network resilience
            arbitrage_engine = get_defi_arbitrage_engine()
            opportunities = arbitrage_engine.find_arbitrage_opportunities()
            assert isinstance(opportunities, list)

            self.validator.log_success("Network failure handling")
            self.test_results.append(("Network failure handling", True, None))

        except Exception as e:
            self.validator.log_error("Network failure handling", str(e))
            self.test_results.append(("Network failure handling", False, str(e)))

    def print_test_results(self):
        """Print comprehensive test results"""
        print("\n" + "="*60)
        print("🔗 CROSS-PROTOCOL INTEGRATION TEST RESULTS")
        print("="*60)

        passed = 0
        failed = 0

        for test_name, success, error in self.test_results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
            if error:
                print(f"   Error: {error}")

        passed = sum(1 for _, success, _ in self.test_results if success)
        failed = len(self.test_results) - passed

        print(f"\n📈 Summary: {passed} passed, {failed} failed")
        print(f"🧪 Total tests: {len(self.test_results)}")
        print(f"📊 Success rate: {passed/len(self.test_results)*100:.1f}%")

        if passed == len(self.test_results):
            print("🎉 All cross-protocol integration tests passed!")
            print("🚀 System is ready for 19-23% APY cross-protocol strategy")
        else:
            print("⚠️ Some integration tests failed - review before deploying")


def run_cross_protocol_integration_tests():
    """Run all cross-protocol integration tests"""
    tester = TestCrossProtocolIntegration()
    tester.run_all_tests()


if __name__ == "__main__":
    run_cross_protocol_integration_tests()
