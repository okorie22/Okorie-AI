"""
Unit tests for tracked wallet balance tracking system
Tests balance cache storage, retrieval, and sell type determination
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import time
from unittest.mock import patch, Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

class TestTrackedWalletBalanceCache(unittest.TestCase):
    """Test TrackedWalletBalanceCache functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Mock configuration
        self.mock_config = Mock()
        self.mock_config.HALF_SELL_THRESHOLD = 0.45
        self.mock_config.HALF_SELL_UPPER_THRESHOLD = 0.55
        self.mock_config.PARTIAL_SELL_MIN_THRESHOLD = 0.10
        self.mock_config.FULL_SELL_THRESHOLD = 0.95
        
        with patch.dict('sys.modules', {
            'src.config': self.mock_config,
            'src.scripts.shared_services.logger': Mock()
        }):
            from src.scripts.webhooks.tracked_wallet_balance_cache import TrackedWalletBalanceCache
            self.balance_cache = TrackedWalletBalanceCache(self.temp_db.name)
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary database
        try:
            if os.path.exists(self.temp_db.name):
                os.unlink(self.temp_db.name)
        except PermissionError:
            # Windows file locking issue - ignore
            pass
    
    def test_get_previous_balance_empty(self):
        """Test getting previous balance when none exists"""
        balance = self.balance_cache.get_previous_balance("wallet1", "token1")
        self.assertEqual(balance, 0.0)
    
    def test_update_balance_first_time(self):
        """Test updating balance for the first time"""
        wallet = "wallet1"
        token = "token1"
        new_balance = 100.0
        
        result = self.balance_cache.update_balance(wallet, token, new_balance)
        
        # Verify result
        self.assertEqual(result['previous_balance'], 0.0)
        self.assertEqual(result['current_balance'], 100.0)
        self.assertEqual(result['change_amount'], 100.0)
        self.assertEqual(result['change_percentage'], 0.0)  # No previous balance
        self.assertEqual(result['sell_type'], 'skip')
        self.assertEqual(result['sell_percentage'], 0.0)
        
        # Verify database storage
        balance = self.balance_cache.get_previous_balance(wallet, token)
        self.assertEqual(balance, 100.0)
    
    def test_update_balance_sell_transaction(self):
        """Test updating balance for a sell transaction"""
        wallet = "wallet1"
        token = "token1"
        
        # First, set initial balance
        self.balance_cache.update_balance(wallet, token, 100.0)
        
        # Now simulate a sell (balance decreases)
        result = self.balance_cache.update_balance(wallet, token, 50.0)
        
        # Verify result
        self.assertEqual(result['previous_balance'], 100.0)
        self.assertEqual(result['current_balance'], 50.0)
        self.assertEqual(result['change_amount'], -50.0)
        self.assertEqual(result['change_percentage'], 50.0)  # 50% sold
        self.assertEqual(result['sell_type'], 'half')
        self.assertEqual(result['sell_percentage'], 50.0)
    
    def test_update_balance_buy_transaction(self):
        """Test updating balance for a buy transaction"""
        wallet = "wallet1"
        token = "token1"
        
        # First, set initial balance
        self.balance_cache.update_balance(wallet, token, 50.0)
        
        # Now simulate a buy (balance increases)
        result = self.balance_cache.update_balance(wallet, token, 100.0)
        
        # Verify result
        self.assertEqual(result['previous_balance'], 50.0)
        self.assertEqual(result['current_balance'], 100.0)
        self.assertEqual(result['change_amount'], 50.0)
        self.assertEqual(result['change_percentage'], 0.0)  # No sell
        self.assertEqual(result['sell_type'], 'skip')
        self.assertEqual(result['sell_percentage'], 0.0)
    
    def test_calculate_sell_percentage_edge_cases(self):
        """Test sell percentage calculation edge cases"""
        test_cases = [
            (0.0, 0.0, 0.0),      # No previous balance
            (100.0, 0.0, 100.0),  # All sold
            (100.0, 100.0, 0.0),  # None sold
            (100.0, 50.0, 50.0),  # Half sold
            (1000.0, 250.0, 75.0), # 75% sold
            (100.0, 90.0, 10.0),  # 10% sold
        ]
        
        for previous, current, expected in test_cases:
            with self.subTest(previous=previous, current=current):
                result = self.balance_cache.calculate_sell_percentage(previous, current)
                self.assertAlmostEqual(result, expected, places=1)  # Allow small floating point differences
    
    def test_determine_sell_type_full_sell(self):
        """Test sell type determination for full sells"""
        test_cases = [
            (100.0, 'full', 100.0),  # 100% sold
            (99.0, 'full', 100.0),   # 99% sold
            (95.0, 'full', 100.0),   # 95% sold
        ]
        
        for percentage_sold, expected_type, expected_percentage in test_cases:
            with self.subTest(percentage_sold=percentage_sold):
                sell_type, sell_percentage = self.balance_cache.determine_sell_type(percentage_sold)
                self.assertEqual(sell_type, expected_type)
                self.assertEqual(sell_percentage, expected_percentage)
    
    def test_determine_sell_type_half_sell(self):
        """Test sell type determination for half sells"""
        test_cases = [
            (50.0, 'half', 50.0),    # 50% sold
            (45.0, 'half', 50.0),    # 45% sold
            (55.0, 'half', 50.0),    # 55% sold
        ]
        
        for percentage_sold, expected_type, expected_percentage in test_cases:
            with self.subTest(percentage_sold=percentage_sold):
                sell_type, sell_percentage = self.balance_cache.determine_sell_type(percentage_sold)
                self.assertEqual(sell_type, expected_type)
                self.assertEqual(sell_percentage, expected_percentage)
    
    def test_determine_sell_type_partial_sell(self):
        """Test sell type determination for partial sells"""
        test_cases = [
            (30.0, 'partial', 30.0),  # 30% sold
            (75.0, 'partial', 75.0),  # 75% sold
            (10.0, 'partial', 10.0),  # 10% sold
            (94.0, 'partial', 94.0),  # 94% sold
        ]
        
        for percentage_sold, expected_type, expected_percentage in test_cases:
            with self.subTest(percentage_sold=percentage_sold):
                sell_type, sell_percentage = self.balance_cache.determine_sell_type(percentage_sold)
                self.assertEqual(sell_type, expected_type)
                self.assertEqual(sell_percentage, expected_percentage)
    
    def test_determine_sell_type_skip(self):
        """Test sell type determination for skip cases"""
        test_cases = [
            (5.0, 'skip', 0.0),   # 5% sold
            (1.0, 'skip', 0.0),   # 1% sold
            (0.0, 'skip', 0.0),   # 0% sold
        ]
        
        for percentage_sold, expected_type, expected_percentage in test_cases:
            with self.subTest(percentage_sold=percentage_sold):
                sell_type, sell_percentage = self.balance_cache.determine_sell_type(percentage_sold)
                self.assertEqual(sell_type, expected_type)
                self.assertEqual(sell_percentage, expected_percentage)
    
    def test_balance_history_tracking(self):
        """Test balance history tracking"""
        wallet = "wallet1"
        token = "token1"
        
        # Perform multiple balance updates
        self.balance_cache.update_balance(wallet, token, 100.0)  # Initial
        self.balance_cache.update_balance(wallet, token, 50.0)   # Sell 50%
        self.balance_cache.update_balance(wallet, token, 25.0)   # Sell another 50%
        self.balance_cache.update_balance(wallet, token, 0.0)    # Sell all
        
        # Get history
        history = self.balance_cache.get_balance_history(wallet, token, limit=10)
        
        # Verify history
        self.assertEqual(len(history), 4)
        
        # Check first entry (initial)
        self.assertEqual(history[0][0], 0.0)    # previous_balance
        self.assertEqual(history[0][1], 100.0)  # current_balance
        self.assertEqual(history[0][2], 100.0)  # change_amount
        self.assertEqual(history[0][3], 0.0)    # change_percentage
        self.assertEqual(history[0][4], 'skip') # sell_type
        
        # Check second entry (50% sell)
        self.assertEqual(history[1][0], 100.0)  # previous_balance
        self.assertEqual(history[1][1], 50.0)   # current_balance
        self.assertEqual(history[1][2], -50.0)  # change_amount
        self.assertEqual(history[1][3], 50.0)   # change_percentage
        self.assertEqual(history[1][4], 'half') # sell_type
        
        # Check third entry (another 50% sell)
        self.assertEqual(history[2][0], 50.0)   # previous_balance
        self.assertEqual(history[2][1], 25.0)   # current_balance
        self.assertEqual(history[2][2], -25.0)  # change_amount
        self.assertEqual(history[2][3], 50.0)   # change_percentage
        self.assertEqual(history[2][4], 'half') # sell_type
        
        # Check fourth entry (full sell)
        self.assertEqual(history[3][0], 25.0)   # previous_balance
        self.assertEqual(history[3][1], 0.0)    # current_balance
        self.assertEqual(history[3][2], -25.0)  # change_amount
        self.assertEqual(history[3][3], 100.0)  # change_percentage
        self.assertEqual(history[3][4], 'full') # sell_type
    
    def test_get_all_balances(self):
        """Test getting all balances for a wallet"""
        wallet = "wallet1"
        
        # Set balances for multiple tokens
        self.balance_cache.update_balance(wallet, "token1", 100.0)
        self.balance_cache.update_balance(wallet, "token2", 200.0)
        self.balance_cache.update_balance(wallet, "token3", 300.0)
        
        # Get all balances
        all_balances = self.balance_cache.get_all_balances(wallet)
        
        # Verify
        expected = {
            "token1": 100.0,
            "token2": 200.0,
            "token3": 300.0
        }
        self.assertEqual(all_balances, expected)
    
    def test_clear_wallet_balances(self):
        """Test clearing all balances for a wallet"""
        wallet = "wallet1"
        
        # Set some balances
        self.balance_cache.update_balance(wallet, "token1", 100.0)
        self.balance_cache.update_balance(wallet, "token2", 200.0)
        
        # Verify balances exist
        self.assertEqual(self.balance_cache.get_previous_balance(wallet, "token1"), 100.0)
        self.assertEqual(self.balance_cache.get_previous_balance(wallet, "token2"), 200.0)
        
        # Clear balances
        self.balance_cache.clear_wallet_balances(wallet)
        
        # Verify balances are cleared
        self.assertEqual(self.balance_cache.get_previous_balance(wallet, "token1"), 0.0)
        self.assertEqual(self.balance_cache.get_previous_balance(wallet, "token2"), 0.0)
        
        # Verify history is also cleared
        history = self.balance_cache.get_balance_history(wallet, "token1")
        self.assertEqual(len(history), 0)
    
    def test_cleanup_old_history(self):
        """Test cleanup of old history records"""
        wallet = "wallet1"
        token = "token1"
        
        # Set a balance
        self.balance_cache.update_balance(wallet, token, 100.0)
        
        # Manually insert old history record
        with sqlite3.connect(self.temp_db.name) as conn:
            old_timestamp = int(time.time()) - (31 * 24 * 60 * 60)  # 31 days ago
            conn.execute("""
                INSERT INTO balance_history 
                (wallet_address, token_address, previous_balance, current_balance, 
                 change_amount, change_percentage, sell_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (wallet, token, 0.0, 100.0, 100.0, 0.0, 'skip', old_timestamp))
        
        # Verify old record exists
        history = self.balance_cache.get_balance_history(wallet, token, limit=10)
        self.assertEqual(len(history), 2)  # 1 recent + 1 old
        
        # Cleanup old history (30 days)
        self.balance_cache.cleanup_old_history(days=30)
        
        # Verify old record is removed
        history = self.balance_cache.get_balance_history(wallet, token, limit=10)
        self.assertEqual(len(history), 1)  # Only recent record remains
    
    def test_concurrent_access(self):
        """Test concurrent access to balance cache"""
        import threading
        import time
        
        wallet = "wallet1"
        token = "token1"
        results = []
        
        def update_balance(amount):
            result = self.balance_cache.update_balance(wallet, token, amount)
            results.append(result)
        
        # Create multiple threads updating balance
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_balance, args=(100.0 + i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all updates were processed
        self.assertEqual(len(results), 5)
        
        # Verify final balance
        final_balance = self.balance_cache.get_previous_balance(wallet, token)
        self.assertGreater(final_balance, 0.0)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestTrackedWalletBalanceCache))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Balance Tracking Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
