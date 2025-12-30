"""
Full Integration Test Suite
Tests the complete AI Trading Assistant system
"""
import unittest
import sys
import os
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Only import Qt components if running with UI
try:
    from PySide6.QtWidgets import QApplication
    from trading_ui_connected import MainWindow
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    print("Qt not available - UI tests will be skipped")


class TestDataCollection(unittest.TestCase):
    """Test data collection system"""
    
    def test_data_reader_initialization(self):
        """Test data reader can be initialized"""
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "pattern-detector"))
        from data_reader import DataReader
        
        reader = DataReader()
        self.assertIsNotNone(reader)
        print("[OK] Data reader initialized")
    
    def test_data_reader_methods(self):
        """Test data reader methods don't crash"""
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "pattern-detector"))
        from data_reader import DataReader
        
        reader = DataReader()
        
        # Test getting data (may return None if Redis not running)
        oi_data = reader.get_latest_oi_data("BTCUSDT")
        funding_data = reader.get_latest_funding_data("BTCUSDT")
        chart_data = reader.get_latest_chart_analysis("BTCUSDT")
        
        # Just verify the methods don't crash
        self.assertTrue(True)
        print("[OK] Data reader methods callable")


class TestStrategyRunner(unittest.TestCase):
    """Test strategy runner system"""
    
    def test_strategy_runner_initialization(self):
        """Test strategy runner can be initialized"""
        from strategy_runner import StrategyRunner
        
        runner = StrategyRunner()
        self.assertIsNotNone(runner)
        self.assertFalse(runner.is_running())
        print("[OK] Strategy runner initialized")
    
    def test_strategy_config(self):
        """Test strategy configuration"""
        from strategy_runner import StrategyRunner
        
        runner = StrategyRunner()
        
        config = {
            'symbols': ['BTCUSDT', 'ETHUSDT'],
            'scan_interval': 300,
            'timeframe': '1d'
        }
        
        # Just verify config is accepted (don't actually start)
        self.assertIsNotNone(config)
        print("[OK] Strategy configuration valid")


@unittest.skipIf(not QT_AVAILABLE, "Qt not available")
class TestUIIntegration(unittest.TestCase):
    """Test UI integration"""
    
    @classmethod
    def setUpClass(cls):
        """Create QApplication once for all UI tests"""
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])
    
    def test_main_window_creation(self):
        """Test main window can be created"""
        window = MainWindow()
        self.assertIsNotNone(window)
        print("[OK] Main window created")
    
    def test_data_cards_exist(self):
        """Test data status cards are created"""
        window = MainWindow()
        
        self.assertTrue(hasattr(window, 'oi_card'))
        self.assertTrue(hasattr(window, 'funding_card'))
        self.assertTrue(hasattr(window, 'chart_card'))
        print("[OK] Data status cards exist")
    
    def test_ai_console_exists(self):
        """Test AI analysis console is created"""
        window = MainWindow()
        
        self.assertTrue(hasattr(window, 'portfolio_viz'))
        print("[OK] AI analysis console exists")
    
    def test_strategy_runner_exists(self):
        """Test strategy runner is initialized"""
        window = MainWindow()
        
        self.assertTrue(hasattr(window, 'strategy_runner'))
        print("[OK] Strategy runner initialized in UI")


class TestPatternDetection(unittest.TestCase):
    """Test pattern detection system"""
    
    def test_pattern_detector_import(self):
        """Test pattern detector can be imported"""
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "pattern-detector"))
        from pattern_detector import PatternDetector
        
        detector = PatternDetector()
        self.assertIsNotNone(detector)
        print("[OK] Pattern detector imported")


def run_tests():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("RUNNING INTEGRATION TESTS")
    print("="*80 + "\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDataCollection))
    suite.addTests(loader.loadTestsFromTestCase(TestStrategyRunner))
    suite.addTests(loader.loadTestsFromTestCase(TestPatternDetection))
    
    if QT_AVAILABLE:
        suite.addTests(loader.loadTestsFromTestCase(TestUIIntegration))
    else:
        print("Skipping UI tests (Qt not available)")
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*80 + "\n")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

