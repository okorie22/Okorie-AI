"""
Comprehensive test suite for DeFi Arbitrage Engine
Tests arbitrage opportunity detection, profit calculation, and execution logic
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

from src.scripts.defi.defi_arbitrage_engine import (
    DeFiArbitrageEngine, ArbitrageOpportunity, DeFiPosition, get_defi_arbitrage_engine
)
from src.scripts.shared_services.rate_monitoring_service import RateData
from test.agents.test_helpers import TestValidator


class MockRateMonitor:
    """Mock rate monitoring service with arbitrage opportunities"""

    def __init__(self):
        self.lending_rates = {
            'solend': RateData('solend', 0.05, datetime.now(), 'mock'),    # 5%
            'mango': RateData('mango', 0.11, datetime.now(), 'mock'),     # 11%
            'tulip': RateData('tulip', 0.15, datetime.now(), 'mock'),    # 15%
        }
        self.borrowing_rates = {
            'solend': RateData('solend', 0.08, datetime.now(), 'mock'),   # 8%
            'mango': RateData('mango', 0.10, datetime.now(), 'mock'),     # 10%
            'tulip': RateData('tulip', 0.12, datetime.now(), 'mock'),    # 12%
        }

    def get_lending_rates(self):
        return self.lending_rates

    def get_borrowing_rates(self):
        return self.borrowing_rates

    def find_arbitrage_opportunities(self, min_spread=0.03):
        """Mock arbitrage opportunities"""
        opportunities = [
            ArbitrageOpportunity(
                borrow_protocol='solend',
                borrow_rate=0.08,
                lend_protocol='mango',
                lend_rate=0.11,
                spread=0.03,
                profit_potential_apy=0.03,
                risk_score=0.3
            ),
            ArbitrageOpportunity(
                borrow_protocol='solend',
                borrow_rate=0.08,
                lend_protocol='tulip',
                lend_rate=0.15,
                spread=0.07,
                profit_potential_apy=0.07,
                risk_score=0.6
            )
        ]
        return [opp for opp in opportunities if opp.spread >= min_spread]


class TestDeFiArbitrageEngine:
    """Comprehensive test suite for DeFi arbitrage engine"""

    def __init__(self):
        self.validator = TestValidator()
        self.test_results = []
        self.mock_rate_monitor = MockRateMonitor()

    def run_all_tests(self):
        """Run all DeFi arbitrage engine tests"""
        print("💰 Testing DeFi Arbitrage Engine")
        print("=" * 60)
        print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Arbitrage Logic Tests
        print("\n" + "="*50)
        print("🧠 ARBITRAGE LOGIC TESTS")
        print("="*50)
        self.test_arbitrage_opportunity_detection()
        self.test_arbitrage_profit_calculation()
        self.test_arbitrage_risk_scoring()
        self.test_arbitrage_thresholds()

        # Position Management Tests
        print("\n" + "="*50)
        print("📊 POSITION MANAGEMENT TESTS")
        print("="*50)
        self.test_position_tracking()
        self.test_arbitrage_history()

        # Execution Tests
        print("\n" + "="*50)
        print("⚡ EXECUTION TESTS")
        print("="*50)
        self.test_arbitrage_execution_paper()
        self.test_arbitrage_execution_live()

        # Profit Tracking Tests
        print("\n" + "="*50)
        print("💵 PROFIT TRACKING TESTS")
        print("="*50)
        self.test_profit_calculation()
        self.test_total_profit_tracking()

        # Error Handling Tests
        print("\n" + "="*50)
        print("🚨 ERROR HANDLING TESTS")
        print("="*50)
        self.test_error_handling()

        # Print results
        self.print_test_results()

    def test_arbitrage_opportunity_detection(self):
        """Test arbitrage opportunity detection"""
        print("Testing arbitrage opportunity detection...")

        try:
            # Create engine with mocked rate monitor
            with patch('src.scripts.defi.defi_arbitrage_engine.get_rate_monitoring_service') as mock_get_rate:
                mock_get_rate.return_value = self.mock_rate_monitor

                engine = DeFiArbitrageEngine()

                # Find arbitrage opportunities
                opportunities = engine.find_arbitrage_opportunities()

                assert len(opportunities) >= 1  # Should find opportunities

                # Check opportunity structure
                for opp in opportunities:
                    assert hasattr(opp, 'borrow_protocol')
                    assert hasattr(opp, 'lend_protocol')
                    assert hasattr(opp, 'spread')
                    assert hasattr(opp, 'profit_potential_apy')
                    assert hasattr(opp, 'risk_score')
                    assert opp.spread >= 0.03  # Should meet minimum spread

                # Should be sorted by profit potential (descending)
                if len(opportunities) > 1:
                    assert opportunities[0].profit_potential_apy >= opportunities[1].profit_potential_apy

                self.validator.log_success("Arbitrage opportunity detection")
                self.test_results.append(("Arbitrage opportunity detection", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage opportunity detection", str(e))
            self.test_results.append(("Arbitrage opportunity detection", False, str(e)))

    def test_arbitrage_profit_calculation(self):
        """Test arbitrage profit calculation"""
        print("Testing arbitrage profit calculation...")

        try:
            engine = DeFiArbitrageEngine()

            # Create test arbitrage opportunity
            opportunity = ArbitrageOpportunity(
                borrow_protocol='solend',
                borrow_rate=0.08,
                lend_protocol='mango',
                lend_rate=0.11,
                spread=0.03,
                profit_potential_apy=0.03,
                risk_score=0.3
            )

            # Calculate profit for different amounts
            profit_100 = engine.calculate_arbitrage_profit(opportunity, 100.0)
            profit_1000 = engine.calculate_arbitrage_profit(opportunity, 1000.0)
            profit_10000 = engine.calculate_arbitrage_profit(opportunity, 10000.0)

            # Profit should scale with amount
            assert profit_1000 > profit_100
            assert profit_10000 > profit_1000

            # Profit should be positive
            assert profit_100 > 0

            # Should account for transaction costs
            theoretical_profit = 0.03 * 100  # 3% of $100 = $3
            assert profit_100 < theoretical_profit  # Should be reduced by costs

            self.validator.log_success("Arbitrage profit calculation")
            self.test_results.append(("Arbitrage profit calculation", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage profit calculation", str(e))
            self.test_results.append(("Arbitrage profit calculation", False, str(e)))

    def test_arbitrage_risk_scoring(self):
        """Test arbitrage risk scoring"""
        print("Testing arbitrage risk scoring...")

        try:
            # Test with different protocol combinations
            engine = DeFiArbitrageEngine()

            # Low risk: Solend (low) + Mango (medium)
            risk1 = engine._calculate_arbitrage_risk('solend', 'mango')
            assert 0.2 <= risk1 <= 0.6

            # Higher risk: Tulip (high) + Francium (high)
            risk2 = engine._calculate_arbitrage_risk('tulip', 'francium')
            assert risk2 > risk1  # Should be higher risk

            # Same protocol (invalid)
            risk3 = engine._calculate_arbitrage_risk('solend', 'solend')
            assert risk3 == 0.5  # Default risk

            self.validator.log_success("Arbitrage risk scoring")
            self.test_results.append(("Arbitrage risk scoring", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage risk scoring", str(e))
            self.test_results.append(("Arbitrage risk scoring", False, str(e)))

    def test_arbitrage_thresholds(self):
        """Test arbitrage thresholds and validation"""
        print("Testing arbitrage thresholds...")

        try:
            engine = DeFiArbitrageEngine()

            # Test minimum spread threshold
            assert engine.min_arbitrage_spread == 0.03

            # Test arbitrage enabled flag
            assert engine.arbitrage_enabled == True  # Should be enabled

            # Test opportunity filtering by spread
            with patch('src.scripts.defi.defi_arbitrage_engine.get_rate_monitoring_service') as mock_get_rate:
                mock_get_rate.return_value = self.mock_rate_monitor

                # High threshold should return fewer opportunities
                high_threshold_opps = engine.find_arbitrage_opportunities(min_spread=0.05)
                all_opps = engine.find_arbitrage_opportunities(min_spread=0.01)

                assert len(high_threshold_opps) <= len(all_opps)

            self.validator.log_success("Arbitrage thresholds")
            self.test_results.append(("Arbitrage thresholds", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage thresholds", str(e))
            self.test_results.append(("Arbitrage thresholds", False, str(e)))

    def test_position_tracking(self):
        """Test position tracking functionality"""
        print("Testing position tracking...")

        try:
            engine = DeFiArbitrageEngine()

            # Add lending position
            engine._record_position('mango', 'lending', 1000.0, 0.11)

            # Add borrowing position
            engine._record_position('solend', 'borrowing', 1000.0, 0.08)

            # Get positions
            positions = engine.get_positions()

            assert 'mango' in positions
            assert 'solend' in positions

            # Check lending position
            lending_pos = positions['mango'][0]
            assert lending_pos.position_type == 'lending'
            assert lending_pos.amount_usd == 1000.0
            assert lending_pos.rate == 0.11

            # Check borrowing position
            borrowing_pos = positions['solend'][0]
            assert borrowing_pos.position_type == 'borrowing'
            assert borrowing_pos.amount_usd == 1000.0
            assert borrowing_pos.rate == 0.08

            self.validator.log_success("Position tracking")
            self.test_results.append(("Position tracking", True, None))

        except Exception as e:
            self.validator.log_error("Position tracking", str(e))
            self.test_results.append(("Position tracking", False, str(e)))

    def test_arbitrage_history(self):
        """Test arbitrage execution history"""
        print("Testing arbitrage history...")

        try:
            engine = DeFiArbitrageEngine()

            # Create and record arbitrage execution
            opportunity = ArbitrageOpportunity(
                borrow_protocol='solend',
                borrow_rate=0.08,
                lend_protocol='mango',
                lend_rate=0.11,
                spread=0.03,
                profit_potential_apy=0.03,
                risk_score=0.3
            )

            execution = engine.arbitrage_history.append(
                engine.ArbitrageExecution(
                    opportunity=opportunity,
                    executed_at=datetime.now(),
                    amount_usd=1000.0,
                    success=True,
                    profit_realized=25.0
                )
            )

            # Get history
            history = engine.get_arbitrage_history()

            assert len(history) >= 1
            latest_execution = history[-1]  # Should be our added execution

            assert latest_execution.amount_usd == 1000.0
            assert latest_execution.success == True
            assert latest_execution.profit_realized == 25.0

            self.validator.log_success("Arbitrage history")
            self.test_results.append(("Arbitrage history", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage history", str(e))
            self.test_results.append(("Arbitrage history", False, str(e)))

    def test_arbitrage_execution_paper(self):
        """Test arbitrage execution in paper trading mode"""
        print("Testing arbitrage execution (paper trading)...")

        try:
            # Mock config for paper trading
            with patch('src.scripts.defi.defi_arbitrage_engine.config') as mock_config:
                mock_config.PAPER_TRADING_ENABLED = True

                engine = DeFiArbitrageEngine()

                opportunity = ArbitrageOpportunity(
                    borrow_protocol='solend',
                    borrow_rate=0.08,
                    lend_protocol='mango',
                    lend_rate=0.11,
                    spread=0.03,
                    profit_potential_apy=0.03,
                    risk_score=0.3
                )

                success = engine.execute_arbitrage(opportunity, 1000.0)

                # Should succeed in paper trading mode
                assert success == True

                # Check positions were recorded
                positions = engine.get_positions()
                assert 'solend' in positions  # Borrowing position
                assert 'mango' in positions   # Lending position

                self.validator.log_success("Arbitrage execution (paper)")
                self.test_results.append(("Arbitrage execution (paper)", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage execution (paper)", str(e))
            self.test_results.append(("Arbitrage execution (paper)", False, str(e)))

    def test_arbitrage_execution_live(self):
        """Test arbitrage execution in live mode"""
        print("Testing arbitrage execution (live)...")

        try:
            # Mock config for live trading
            with patch('src.scripts.defi.defi_arbitrage_engine.config') as mock_config:
                mock_config.PAPER_TRADING_ENABLED = False

                engine = DeFiArbitrageEngine()

                opportunity = ArbitrageOpportunity(
                    borrow_protocol='solend',
                    borrow_rate=0.08,
                    lend_protocol='mango',
                    lend_rate=0.11,
                    spread=0.03,
                    profit_potential_apy=0.03,
                    risk_score=0.3
                )

                success = engine.execute_arbitrage(opportunity, 1000.0)

                # Should return False (not implemented for live)
                assert success == False

                self.validator.log_success("Arbitrage execution (live)")
                self.test_results.append(("Arbitrage execution (live)", True, None))

        except Exception as e:
            self.validator.log_error("Arbitrage execution (live)", str(e))
            self.test_results.append(("Arbitrage execution (live)", False, str(e)))

    def test_profit_calculation(self):
        """Test profit calculation logic"""
        print("Testing profit calculation...")

        try:
            engine = DeFiArbitrageEngine()

            # Test get_total_arbitrage_profit with no history
            total_profit = engine.get_total_arbitrage_profit()
            assert total_profit == 0.0

            # Add some profit history
            engine.arbitrage_history = [
                engine.ArbitrageExecution(
                    opportunity=None,
                    executed_at=datetime.now(),
                    amount_usd=1000.0,
                    success=True,
                    profit_realized=25.0
                ),
                engine.ArbitrageExecution(
                    opportunity=None,
                    executed_at=datetime.now(),
                    amount_usd=2000.0,
                    success=True,
                    profit_realized=50.0
                ),
                engine.ArbitrageExecution(
                    opportunity=None,
                    executed_at=datetime.now(),
                    amount_usd=1000.0,
                    success=False,
                    profit_realized=None
                )
            ]

            # Test total profit calculation
            total_profit = engine.get_total_arbitrage_profit()
            assert total_profit == 75.0  # 25 + 50 (failed execution ignored)

            # Test date filtering
            old_profit = engine.get_total_arbitrage_profit(days=0)  # Should be 0
            assert old_profit == 0.0

            self.validator.log_success("Profit calculation")
            self.test_results.append(("Profit calculation", True, None))

        except Exception as e:
            self.validator.log_error("Profit calculation", str(e))
            self.test_results.append(("Profit calculation", False, str(e)))

    def test_total_profit_tracking(self):
        """Test total profit tracking across multiple executions"""
        print("Testing total profit tracking...")

        try:
            engine = DeFiArbitrageEngine()

            # Simulate multiple arbitrage executions
            executions = [
                (1000.0, True, 25.0),   # $1000, success, $25 profit
                (2000.0, True, 60.0),   # $2000, success, $60 profit
                (1500.0, False, None),  # $1500, failed, no profit
                (500.0, True, 12.5),    # $500, success, $12.50 profit
            ]

            for amount, success, profit in executions:
                execution = engine.ArbitrageExecution(
                    opportunity=None,
                    executed_at=datetime.now(),
                    amount_usd=amount,
                    success=success,
                    profit_realized=profit
                )
                engine.arbitrage_history.append(execution)

            # Calculate total profit
            total_profit = engine.get_total_arbitrage_profit()

            expected_profit = 25.0 + 60.0 + 12.5  # Only successful executions
            assert abs(total_profit - expected_profit) < 0.01

            # Test history retrieval
            history = engine.get_arbitrage_history()
            assert len(history) == 4

            successful_executions = [h for h in history if h.success]
            assert len(successful_executions) == 3

            self.validator.log_success("Total profit tracking")
            self.test_results.append(("Total profit tracking", True, None))

        except Exception as e:
            self.validator.log_error("Total profit tracking", str(e))
            self.test_results.append(("Total profit tracking", False, str(e)))

    def test_error_handling(self):
        """Test error handling"""
        print("Testing error handling...")

        try:
            engine = DeFiArbitrageEngine()

            # Test with invalid opportunity
            success = engine.execute_arbitrage(None, 1000.0)
            assert success == False  # Should handle gracefully

            # Test profit calculation with invalid data
            profit = engine.calculate_arbitrage_profit(None, 1000.0)
            assert profit == 0.0  # Should return 0 on error

            # Test with empty arbitrage history
            total_profit = engine.get_total_arbitrage_profit()
            assert total_profit == 0.0

            # Test position tracking with invalid data
            engine._record_position('', '', -100.0, -0.1)  # Invalid inputs
            positions = engine.get_positions()
            assert isinstance(positions, dict)  # Should not crash

            self.validator.log_success("Error handling")
            self.test_results.append(("Error handling", True, None))

        except Exception as e:
            self.validator.log_error("Error handling", str(e))
            self.test_results.append(("Error handling", False, str(e)))

    def print_test_results(self):
        """Print comprehensive test results"""
        print("\n" + "="*60)
        print("💰 DEFİ ARBITRAGE ENGINE TEST RESULTS")
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


def run_defi_arbitrage_tests():
    """Run all DeFi arbitrage engine tests"""
    tester = TestDeFiArbitrageEngine()
    tester.run_all_tests()


if __name__ == "__main__":
    run_defi_arbitrage_tests()
