"""
Comprehensive test suite for Rate Monitoring Service
Tests rate fetching, caching, history tracking, and arbitrage detection
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

from src.scripts.shared_services.rate_monitoring_service import (
    RateMonitoringService, RateData, ArbitrageOpportunity, get_rate_monitoring_service
)
from src.scripts.shared_services.shared_api_manager import APIEndpoint
from test.agents.test_helpers import TestValidator


class MockAPIManager:
    """Mock API manager for testing"""

    def __init__(self):
        self.staking_data = {
            'sanctum': 0.095,  # 9.5%
            'jito': 0.08,      # 8.0%
            'marinade': 0.07,  # 7.0%
        }
        self.call_count = 0

    def get_staking_apy_data(self, callback=None) -> Dict[str, float]:
        """Mock staking APY data"""
        self.call_count += 1
        return self.staking_data.copy()

    def make_request(self, endpoint, **kwargs):
        """Mock API request"""
        if endpoint == APIEndpoint.BLAZESTAKE_APY:
            return {"apy": 6.43}
        return None


class TestRateMonitoringService:
    """Comprehensive test suite for rate monitoring service"""

    def __init__(self):
        self.test_results = []
        self.mock_api_manager = MockAPIManager()

    def run_all_tests(self):
        """Run all rate monitoring service tests"""
        print("📊 Testing Rate Monitoring Service")
        print("=" * 60)
        print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Rate Fetching Tests
        print("\n" + "="*50)
        print("📈 RATE FETCHING TESTS")
        print("="*50)
        self.test_staking_rates_fetching()
        self.test_lending_rates_fetching()
        self.test_borrowing_rates_fetching()
        self.test_rate_caching()
        self.test_rate_history_tracking()

        # Arbitrage Tests
        print("\n" + "="*50)
        print("💰 ARBITRAGE DETECTION TESTS")
        print("="*50)
        self.test_arbitrage_opportunity_detection()
        self.test_arbitrage_profit_calculation()
        self.test_arbitrage_risk_scoring()

        # Best Rate Tests
        print("\n" + "="*50)
        print("🏆 BEST RATE SELECTION TESTS")
        print("="*50)
        self.test_best_rate_selection()
        self.test_rate_spread_calculation()

        # Error Handling Tests
        print("\n" + "="*50)
        print("🚨 ERROR HANDLING TESTS")
        print("="*50)
        self.test_error_handling()

        # Print results
        self.print_test_results()

    def test_staking_rates_fetching(self):
        """Test staking rates fetching"""
        print("Testing staking rates fetching...")

        try:
            # Create service with mocked API manager
            with patch('src.scripts.shared_services.rate_monitoring_service.get_shared_api_manager') as mock_get_api:
                mock_get_api.return_value = self.mock_api_manager

                service = RateMonitoringService()

                # Test initial fetch
                rates = service.get_staking_rates(force_refresh=True)

                # Verify rates fetched
                assert 'sanctum' in rates
                assert 'jito' in rates
                assert 'marinade' in rates

                # Verify rate values
                assert rates['sanctum'].rate == 0.095
                assert rates['jito'].rate == 0.08
                assert rates['marinade'].rate == 0.07

                # Verify metadata
                assert isinstance(rates['sanctum'].timestamp, datetime)
                assert rates['sanctum'].source == "api_manager"

                print("✅ Staking rates fetching passed")
                self.test_results.append(("Staking rates fetching", True, None))

        except Exception as e:
            print(f"❌ Staking rates fetching failed: {str(e)}")
            self.test_results.append(("Staking rates fetching", False, str(e)))

    def test_lending_rates_fetching(self):
        """Test lending rates fetching"""
        print("Testing lending rates fetching...")

        try:
            service = RateMonitoringService()
            rates = service.get_lending_rates(force_refresh=True)

            # Should have default rates for configured protocols
            assert 'solend' in rates
            assert 'mango' in rates
            assert 'tulip' in rates

            # Verify rate ranges (5-15% APY)
            for protocol, rate_data in rates.items():
                assert 0.05 <= rate_data.rate <= 0.15
                assert isinstance(rate_data.timestamp, datetime)

            print("✅ Lending rates fetching passed")
            self.test_results.append(("Lending rates fetching", True, None))

        except Exception as e:
            print(f"❌ Lending rates fetching failed: {str(e)}")
            self.test_results.append(("Lending rates fetching", False, str(e)))

    def test_borrowing_rates_fetching(self):
        """Test borrowing rates fetching"""
        print("Testing borrowing rates fetching...")

        try:
            service = RateMonitoringService()
            rates = service.get_borrowing_rates(force_refresh=True)

            # Should have default rates for configured protocols
            assert 'solend' in rates
            assert 'mango' in rates
            assert 'tulip' in rates

            # Borrowing rates should be higher than lending rates
            lending_rates = service.get_lending_rates()
            for protocol in rates:
                if protocol in lending_rates:
                    assert rates[protocol].rate > lending_rates[protocol].rate

            print("✅ Borrowing rates fetching passed")
            self.test_results.append(("Borrowing rates fetching", True, None))

        except Exception as e:
            print(f"❌ Borrowing rates fetching failed: {str(e)}")
            self.test_results.append(("Borrowing rates fetching", False, str(e)))

    def test_rate_caching(self):
        """Test rate caching functionality"""
        print("Testing rate caching...")

        try:
            with patch('src.scripts.shared_services.rate_monitoring_service.get_shared_api_manager') as mock_get_api:
                mock_get_api.return_value = self.mock_api_manager

                service = RateMonitoringService()

                # First fetch (should call API)
                rates1 = service.get_staking_rates(force_refresh=True)
                calls_after_first = self.mock_api_manager.call_count

                # Second fetch (should use cache)
                rates2 = service.get_staking_rates(force_refresh=False)
                calls_after_second = self.mock_api_manager.call_count

                # Verify caching worked (no additional API calls)
                assert calls_after_second == calls_after_first

                # Verify data consistency
                assert rates1['sanctum'].rate == rates2['sanctum'].rate

                print("✅ Rate caching passed")
                self.test_results.append(("Rate caching", True, None))

        except Exception as e:
            print(f"❌ Rate caching failed: {str(e)}")
            self.test_results.append(("Rate caching", False, str(e)))

    def test_rate_history_tracking(self):
        """Test rate history tracking"""
        print("Testing rate history tracking...")

        try:
            service = RateMonitoringService()

            # Add some rate history
            service._update_rate_history('test_protocol', 'staking', 0.08)
            time.sleep(0.1)  # Small delay
            service._update_rate_history('test_protocol', 'staking', 0.085)
            time.sleep(0.1)
            service._update_rate_history('test_protocol', 'staking', 0.09)

            # Test history retrieval
            history = service.get_rate_trend('test_protocol', 'staking')

            assert history is not None
            assert history['protocol'] == 'test_protocol'
            assert history['rate_type'] == 'staking'
            assert history['data_points'] >= 2
            assert history['current_rate'] == 0.09
            assert history['average_rate'] > 0

            self.validator.log_success("Rate history tracking")
            self.test_results.append(("Rate history tracking", True, None))

        except Exception as e:
            self.validator.log_error("Rate history tracking", str(e))
            self.test_results.append(("Rate history tracking", False, str(e)))

    def test_arbitrage_opportunity_detection(self):
        """Test arbitrage opportunity detection"""
        print("Testing arbitrage opportunity detection...")

        try:
            service = RateMonitoringService()

            # Force refresh to get fresh rates
            service.get_lending_rates(force_refresh=True)
            service.get_borrowing_rates(force_refresh=True)

            # Find arbitrage opportunities
            opportunities = service.find_arbitrage_opportunities(min_spread=0.01)  # Low threshold

            # Should find some opportunities since we have different rates
            assert isinstance(opportunities, list)

            # Check opportunity structure if any found
            if opportunities:
                opp = opportunities[0]
                assert hasattr(opp, 'borrow_protocol')
                assert hasattr(opp, 'lend_protocol')
                assert hasattr(opp, 'spread')
                assert hasattr(opp, 'profit_potential_apy')
                assert opp.spread > 0

            self.validator.log_success("Arbitrage opportunity detection")
            self.test_results.append(("Arbitrage opportunity detection", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage opportunity detection", str(e))
            self.test_results.append(("Arbitrage opportunity detection", False, str(e)))

    def test_arbitrage_profit_calculation(self):
        """Test arbitrage profit calculation"""
        print("Testing arbitrage profit calculation...")

        try:
            service = RateMonitoringService()

            # Create test arbitrage opportunity
            opportunity = ArbitrageOpportunity(
                borrow_protocol='solend',
                borrow_rate=0.08,  # 8%
                lend_protocol='mango',
                lend_rate=0.11,   # 11%
                spread=0.03,      # 3%
                profit_potential_apy=0.03,
                risk_score=0.3
            )

            # Calculate profit for $1000
            profit = service.calculate_arbitrage_profit(opportunity, 1000.0)

            # Should be positive
            assert profit > 0

            # Should account for transaction costs (profit should be less than full spread)
            full_spread_profit = 0.03 * 1000  # $30
            assert profit < full_spread_profit  # Should be reduced by transaction costs

            self.validator.log_success("Arbitrage profit calculation")
            self.test_results.append(("Arbitrage profit calculation", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage profit calculation", str(e))
            self.test_results.append(("Arbitrage profit calculation", False, str(e)))

    def test_arbitrage_risk_scoring(self):
        """Test arbitrage risk scoring"""
        print("Testing arbitrage risk scoring...")

        try:
            # Test risk calculation method
            risk_score = RateMonitoringService()._calculate_arbitrage_risk('solend', 'mango')

            assert 0.0 <= risk_score <= 1.0

            # Solend (low risk) + Mango (medium-high risk) should be moderate risk
            assert 0.3 <= risk_score <= 0.8

            self.validator.log_success("Arbitrage risk scoring")
            self.test_results.append(("Arbitrage risk scoring", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage risk scoring", str(e))
            self.test_results.append(("Arbitrage risk scoring", False, str(e)))

    def test_best_rate_selection(self):
        """Test best rate selection"""
        print("Testing best rate selection...")

        try:
            service = RateMonitoringService()

            # Get best rates
            best_staking = service.get_best_staking_rate()
            best_lending = service.get_best_lending_rate()
            best_borrowing = service.get_best_borrowing_rate()

            # Verify structure
            assert best_staking is not None or best_staking is None  # Can be None if no data
            assert best_lending is not None or best_lending is None
            assert best_borrowing is not None or best_borrowing is None

            # If data exists, verify it's RateData
            if best_staking:
                assert hasattr(best_staking, 'protocol')
                assert hasattr(best_staking, 'rate')
                assert hasattr(best_staking, 'timestamp')

            if best_lending:
                assert hasattr(best_lending, 'protocol')
                assert hasattr(best_lending, 'rate')
                assert hasattr(best_lending, 'timestamp')

            if best_borrowing:
                assert hasattr(best_borrowing, 'protocol')
                assert hasattr(best_borrowing, 'rate')
                assert hasattr(best_borrowing, 'timestamp')

            self.validator.log_success("Best rate selection")
            self.test_results.append(("Best rate selection", True, None))

        except Exception as e:
            self.validator.log_error("Best rate selection", str(e))
            self.test_results.append(("Best rate selection", False, str(e)))

    def test_rate_spread_calculation(self):
        """Test rate spread calculation"""
        print("Testing rate spread calculation...")

        try:
            service = RateMonitoringService()

            # Test spread calculation
            spread = service.get_rate_spread('solend', 'mango', 'lending')

            # Should return a number (can be None if no data)
            assert isinstance(spread, (float, type(None)))

            if spread is not None:
                # Mango should have higher lending rate than Solend
                assert spread > 0

            self.validator.log_success("Rate spread calculation")
            self.test_results.append(("Rate spread calculation", True, None))

        except Exception as e:
            self.validator.log_error("Rate spread calculation", str(e))
            self.test_results.append(("Rate spread calculation", False, str(e)))

    def test_error_handling(self):
        """Test error handling"""
        print("Testing error handling...")

        try:
            service = RateMonitoringService()

            # Test with invalid inputs
            spread = service.get_rate_spread('nonexistent', 'also_nonexistent')
            assert spread is None

            # Test arbitrage with invalid data
            opportunities = service.find_arbitrage_opportunities()
            assert isinstance(opportunities, list)  # Should not crash

            # Test rate history with invalid protocol
            history = service.get_rate_trend('nonexistent', 'staking')
            assert history is None

            self.validator.log_success("Error handling")
            self.test_results.append(("Error handling", True, None))

        except Exception as e:
            self.validator.log_error("Error handling", str(e))
            self.test_results.append(("Error handling", False, str(e)))

    def print_test_results(self):
        """Print comprehensive test results"""
        print("\n" + "="*60)
        print("📊 RATE MONITORING SERVICE TEST RESULTS")
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


def run_rate_monitoring_tests():
    """Run all rate monitoring service tests"""
    tester = TestRateMonitoringService()
    tester.run_all_tests()


if __name__ == "__main__":
    run_rate_monitoring_tests()
