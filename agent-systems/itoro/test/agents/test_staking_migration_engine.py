"""
Comprehensive test suite for Staking Migration Engine
Tests migration opportunity detection, cost-benefit analysis, and execution logic
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

from src.scripts.staking.staking_migration_engine import (
    StakingMigrationEngine, MigrationOpportunity, get_staking_migration_engine
)
from src.scripts.shared_services.rate_monitoring_service import RateData
from test.agents.test_helpers import TestValidator


class MockRateMonitor:
    """Mock rate monitoring service"""

    def __init__(self):
        self.staking_rates = {
            'sanctum': RateData('sanctum', 0.095, datetime.now(), 'mock'),
            'jito': RateData('jito', 0.08, datetime.now(), 'mock'),
            'marinade': RateData('marinade', 0.07, datetime.now(), 'mock'),
        }

    def get_staking_rates(self):
        return self.staking_rates

    def get_best_staking_rate(self):
        return self.staking_rates['sanctum']  # Sanctum has best rate


class TestStakingMigrationEngine:
    """Comprehensive test suite for staking migration engine"""

    def __init__(self):
        self.validator = TestValidator()
        self.test_results = []
        self.mock_rate_monitor = MockRateMonitor()

    def run_all_tests(self):
        """Run all staking migration engine tests"""
        print("🔄 Testing Staking Migration Engine")
        print("=" * 60)
        print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Migration Logic Tests
        print("\n" + "="*50)
        print("🧠 MIGRATION LOGIC TESTS")
        print("="*50)
        self.test_migration_opportunity_detection()
        self.test_migration_cost_calculation()
        self.test_migration_benefit_analysis()
        self.test_migration_thresholds()

        # Position Management Tests
        print("\n" + "="*50)
        print("📊 POSITION MANAGEMENT TESTS")
        print("="*50)
        self.test_position_tracking()
        self.test_migration_history()

        # Execution Tests
        print("\n" + "="*50)
        print("⚡ EXECUTION TESTS")
        print("="*50)
        self.test_migration_execution_paper()
        self.test_migration_execution_live()

        # Edge Cases Tests
        print("\n" + "="*50)
        print("🎯 EDGE CASES TESTS")
        print("="*50)
        self.test_insufficient_spread()
        self.test_recent_migration_cooldown()
        self.test_invalid_positions()

        # Error Handling Tests
        print("\n" + "="*50)
        print("🚨 ERROR HANDLING TESTS")
        print("="*50)
        self.test_error_handling()

        # Print results
        self.print_test_results()

    def test_migration_opportunity_detection(self):
        """Test migration opportunity detection"""
        print("Testing migration opportunity detection...")

        try:
            # Create engine with mocked rate monitor
            with patch('src.scripts.staking.staking_migration_engine.get_rate_monitoring_service') as mock_get_rate:
                mock_get_rate.return_value = self.mock_rate_monitor

                engine = StakingMigrationEngine()

                # Test current positions (Marinade at 7% vs Sanctum at 9.5%)
                current_positions = {'marinade': 10.0}  # 10 SOL on Marinade

                opportunities = engine.find_migration_opportunities(current_positions)

                assert len(opportunities) == 1
                opp = opportunities[0]

                assert opp.from_protocol == 'marinade'
                assert opp.to_protocol == 'sanctum'
                assert opp.spread > 0.02  # Should exceed minimum spread
                assert opp.should_migrate == True

                self.validator.log_success("Migration opportunity detection")
                self.test_results.append(("Migration opportunity detection", True, None))

        except Exception as e:
            self.validator.log_error("Migration opportunity detection", str(e))
            self.test_results.append(("Migration opportunity detection", False, str(e)))

    def test_migration_cost_calculation(self):
        """Test migration cost calculation"""
        print("Testing migration cost calculation...")

        try:
            engine = StakingMigrationEngine()

            # Test cost calculation for different amounts
            cost_1_sol = engine.calculate_migration_cost(1.0)
            cost_10_sol = engine.calculate_migration_cost(10.0)
            cost_100_sol = engine.calculate_migration_cost(100.0)

            # Cost should be consistent (flat fee)
            assert cost_1_sol == cost_10_sol == cost_100_sol

            # Cost should be positive but reasonable
            assert 0.005 <= cost_1_sol <= 0.02  # 0.005-0.02 SOL

            self.validator.log_success("Migration cost calculation")
            self.test_results.append(("Migration cost calculation", True, None))

        except Exception as e:
            self.validator.log_error("Migration cost calculation", str(e))
            self.test_results.append(("Migration cost calculation", False, str(e)))

    def test_migration_benefit_analysis(self):
        """Test migration benefit analysis"""
        print("Testing migration benefit analysis...")

        try:
            with patch('src.scripts.staking.staking_migration_engine.get_rate_monitoring_service') as mock_get_rate:
                mock_get_rate.return_value = self.mock_rate_monitor

                engine = StakingMigrationEngine()

                # Test should_migrate with good opportunity
                should_migrate, opportunity = engine.should_migrate(
                    'marinade', 0.07, 'sanctum', 0.095, 10.0
                )

                assert should_migrate == True
                assert opportunity is not None
                assert opportunity.spread == 0.025  # 2.5%
                assert opportunity.net_benefit_apy > 0

                # Test should_migrate with poor opportunity (below threshold)
                should_migrate_bad, _ = engine.should_migrate(
                    'sanctum', 0.095, 'jito', 0.08, 10.0  # Only 1.5% spread
                )

                assert should_migrate_bad == False

                self.validator.log_success("Migration benefit analysis")
                self.test_results.append(("Migration benefit analysis", True, None))

        except Exception as e:
            self.validator.log_error("Migration benefit analysis", str(e))
            self.test_results.append(("Migration benefit analysis", False, str(e)))

    def test_migration_thresholds(self):
        """Test migration thresholds and validation"""
        print("Testing migration thresholds...")

        try:
            engine = StakingMigrationEngine()

            # Test minimum spread threshold
            assert engine.min_migration_spread == 0.02

            # Test migration frequency limit
            assert engine.max_migration_frequency_days == 7

            # Test migration cost threshold
            assert 0 < engine.migration_cost_sol <= 0.02

            self.validator.log_success("Migration thresholds")
            self.test_results.append(("Migration thresholds", True, None))

        except Exception as e:
            self.validator.log_error("Migration thresholds", str(e))
            self.test_results.append(("Migration thresholds", False, str(e)))

    def test_position_tracking(self):
        """Test position tracking functionality"""
        print("Testing position tracking...")

        try:
            engine = StakingMigrationEngine()

            # Add a position
            engine.update_position('sanctum', 10.0, 0.095)

            # Get positions
            positions = engine.get_positions()

            assert 'sanctum' in positions
            position = positions['sanctum']

            assert position.protocol == 'sanctum'
            assert position.amount_sol == 10.0
            assert position.apy == 0.095
            assert isinstance(position.staked_at, datetime)

            self.validator.log_success("Position tracking")
            self.test_results.append(("Position tracking", True, None))

        except Exception as e:
            self.validator.log_error("Position tracking", str(e))
            self.test_results.append(("Position tracking", False, str(e)))

    def test_migration_history(self):
        """Test migration history tracking"""
        print("Testing migration history...")

        try:
            engine = StakingMigrationEngine()

            # Record a migration
            engine._record_migration('marinade', 'sanctum', 5.0, True)

            # Get history
            history = engine.get_migration_history()

            assert len(history) == 1
            migration = history[0]

            assert migration['from_protocol'] == 'marinade'
            assert migration['to_protocol'] == 'sanctum'
            assert migration['amount_sol'] == 5.0
            assert migration['success'] == True
            assert isinstance(migration['timestamp'], datetime)

            # Test date filtering
            old_history = engine.get_migration_history(days=0)  # Should be empty
            assert len(old_history) == 0

            self.validator.log_success("Migration history")
            self.test_results.append(("Migration history", True, None))

        except Exception as e:
            self.validator.log_error("Migration history", str(e))
            self.test_results.append(("Migration history", False, str(e)))

    def test_migration_execution_paper(self):
        """Test migration execution in paper trading mode"""
        print("Testing migration execution (paper trading)...")

        try:
            # Mock config for paper trading
            with patch('src.scripts.staking.staking_migration_engine.config') as mock_config:
                mock_config.PAPER_TRADING_ENABLED = True

                engine = StakingMigrationEngine()

                success = engine.execute_migration('marinade', 'sanctum', 5.0)

                # Should succeed in paper trading mode
                assert success == True

                # Check migration was recorded
                history = engine.get_migration_history()
                assert len(history) == 1

                self.validator.log_success("Migration execution (paper)")
                self.test_results.append(("Migration execution (paper)", True, None))

        except Exception as e:
            self.validator.log_error("Migration execution (paper)", str(e))
            self.test_results.append(("Migration execution (paper)", False, str(e)))

    def test_migration_execution_live(self):
        """Test migration execution in live mode"""
        print("Testing migration execution (live)...")

        try:
            # Mock config for live trading
            with patch('src.scripts.staking.staking_migration_engine.config') as mock_config:
                mock_config.PAPER_TRADING_ENABLED = False

                engine = StakingMigrationEngine()

                success = engine.execute_migration('marinade', 'sanctum', 5.0)

                # Should return False (not implemented for live)
                assert success == False

                self.validator.log_success("Migration execution (live)")
                self.test_results.append(("Migration execution (live)", True, None))

        except Exception as e:
            self.validator.log_error("Migration execution (live)", str(e))
            self.test_results.append(("Migration execution (live)", False, str(e)))

    def test_insufficient_spread(self):
        """Test handling of insufficient spread"""
        print("Testing insufficient spread handling...")

        try:
            with patch('src.scripts.staking.staking_migration_engine.get_rate_monitoring_service') as mock_get_rate:
                mock_get_rate.return_value = self.mock_rate_monitor

                engine = StakingMigrationEngine()

                # Test with very small spread (below threshold)
                should_migrate, opportunity = engine.should_migrate(
                    'jito', 0.08, 'marinade', 0.07, 10.0  # Only 1% spread
                )

                assert should_migrate == False
                assert opportunity is None

                self.validator.log_success("Insufficient spread handling")
                self.test_results.append(("Insufficient spread handling", True, None))

        except Exception as e:
            self.validator.log_error("Insufficient spread handling", str(e))
            self.test_results.append(("Insufficient spread handling", False, str(e)))

    def test_recent_migration_cooldown(self):
        """Test recent migration cooldown logic"""
        print("Testing recent migration cooldown...")

        try:
            engine = StakingMigrationEngine()

            # Record a recent migration
            recent_time = datetime.now() - timedelta(days=1)  # 1 day ago
            engine.migration_history.append({
                'from_protocol': 'marinade',
                'to_protocol': 'sanctum',
                'timestamp': recent_time,
                'success': True
            })

            # Check if cooldown prevents migration
            is_recent = engine._recently_migrated('marinade')

            # Should be True since migration was within 7 days
            assert is_recent == True

            # Check old migration (beyond cooldown)
            old_time = datetime.now() - timedelta(days=10)  # 10 days ago
            engine.migration_history[0]['timestamp'] = old_time

            is_recent_old = engine._recently_migrated('marinade')

            # Should be False since migration was more than 7 days ago
            assert is_recent_old == False

            self.validator.log_success("Recent migration cooldown")
            self.test_results.append(("Recent migration cooldown", True, None))

        except Exception as e:
            self.validator.log_error("Recent migration cooldown", str(e))
            self.test_results.append(("Recent migration cooldown", False, str(e)))

    def test_invalid_positions(self):
        """Test handling of invalid positions"""
        print("Testing invalid positions handling...")

        try:
            engine = StakingMigrationEngine()

            # Test with empty positions
            opportunities = engine.find_migration_opportunities({})
            assert len(opportunities) == 0

            # Test with zero amount positions
            opportunities_zero = engine.find_migration_opportunities({'sanctum': 0.0})
            assert len(opportunities_zero) == 0

            self.validator.log_success("Invalid positions handling")
            self.test_results.append(("Invalid positions handling", True, None))

        except Exception as e:
            self.validator.log_error("Invalid positions handling", str(e))
            self.test_results.append(("Invalid positions handling", False, str(e)))

    def test_error_handling(self):
        """Test error handling"""
        print("Testing error handling...")

        try:
            engine = StakingMigrationEngine()

            # Test with invalid rate monitor
            with patch('src.scripts.staking.staking_migration_engine.get_rate_monitoring_service') as mock_get_rate:
                mock_get_rate.return_value = None

                # Should handle gracefully
                opportunities = engine.find_migration_opportunities({'sanctum': 10.0})
                assert isinstance(opportunities, list)  # Should not crash

            # Test invalid migration parameters
            success = engine.execute_migration('', '', -1.0)  # Invalid inputs
            assert success == False  # Should handle gracefully

            self.validator.log_success("Error handling")
            self.test_results.append(("Error handling", True, None))

        except Exception as e:
            self.validator.log_error("Error handling", str(e))
            self.test_results.append(("Error handling", False, str(e)))

    def print_test_results(self):
        """Print comprehensive test results"""
        print("\n" + "="*60)
        print("🔄 STAKING MIGRATION ENGINE TEST RESULTS")
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


def run_staking_migration_tests():
    """Run all staking migration engine tests"""
    tester = TestStakingMigrationEngine()
    tester.run_all_tests()


if __name__ == "__main__":
    run_staking_migration_tests()
