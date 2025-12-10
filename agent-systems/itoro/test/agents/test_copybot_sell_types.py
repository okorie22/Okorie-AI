"""
Unit tests for CopyBot sell type methods
Tests _execute_half_sell, _execute_partial_sell, and sell type determination logic
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import tempfile
import sqlite3

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

class TestCopyBotSellTypes(unittest.TestCase):
    """Test CopyBot sell type methods"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the necessary imports and dependencies
        self.mock_config = Mock()
        self.mock_config.PAPER_TRADING_ENABLED = True
        self.mock_config.SOL_ADDRESS = "So11111111111111111111111111111111111111112"
        self.mock_config.USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        self.mock_config.EXCLUDED_TOKENS = []
        
        # Mock the copybot agent
        with patch.dict('sys.modules', {
            'src.config': self.mock_config,
            'src.scripts.shared_services.logger': Mock(),
            'src.scripts.shared_services.optimized_price_service': Mock(),
            'src.paper_trading': Mock(),
            'src.nice_funcs': Mock()
        }):
            from src.agents.copybot_agent import CopyBotAgent
            self.copybot = CopyBotAgent()
        
        # Mock price service
        self.mock_price_service = Mock()
        self.mock_price_service.get_price.return_value = 1.0
        
        # Mock paper trading
        self.mock_paper_trading = Mock()
        self.mock_paper_trading.execute_paper_trade.return_value = True
        
        # Mock nice_funcs
        self.mock_nice_funcs = Mock()
        self.mock_nice_funcs.market_exit.return_value = True
        
        # Mock token balance
        self.copybot.get_token_balance = Mock(return_value=100.0)
        self.copybot._get_nice_funcs = Mock(return_value=self.mock_nice_funcs)
        self.copybot._blocked_token = Mock(return_value=False)
        self.copybot.order_executed = Mock()
    
    def test_execute_half_sell_paper_mode(self):
        """Test _execute_half_sell in paper trading mode"""
        # Setup
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Execute
            result = self.copybot._execute_half_sell(wallet, mint, token_data, self.mock_price_service)
            
            # Verify
            self.assertEqual(result, 'success')
            self.mock_paper_trading.execute_paper_trade.assert_called_once_with(
                mint, "PARTIAL_CLOSE", 50.0, 1.0, "copybot"
            )
            self.copybot.order_executed.emit.assert_called_once()
    
    def test_execute_half_sell_live_mode(self):
        """Test _execute_half_sell in live trading mode"""
        # Setup
        self.mock_config.PAPER_TRADING_ENABLED = False
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        
        with patch('src.config', self.mock_config):
            # Execute
            result = self.copybot._execute_half_sell(wallet, mint, token_data, self.mock_price_service)
            
            # Verify
            self.assertEqual(result, 'success')
            self.mock_nice_funcs.market_exit.assert_called_once_with('TEST', percentage=50)
    
    def test_execute_half_sell_no_balance(self):
        """Test _execute_half_sell with no balance"""
        # Setup
        self.copybot.get_token_balance.return_value = 0.0
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        
        # Execute
        result = self.copybot._execute_half_sell(wallet, mint, token_data, self.mock_price_service)
        
        # Verify
        self.assertEqual(result, 'no_balance')
        self.mock_paper_trading.execute_paper_trade.assert_not_called()
    
    def test_execute_partial_sell_paper_mode(self):
        """Test _execute_partial_sell in paper trading mode"""
        # Setup
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        percentage = 30.0
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Execute
            result = self.copybot._execute_partial_sell(wallet, mint, token_data, self.mock_price_service, percentage)
            
            # Verify
            self.assertEqual(result, 'success')
            self.mock_paper_trading.execute_paper_trade.assert_called_once_with(
                mint, "PARTIAL_CLOSE", 30.0, 1.0, "copybot"
            )
            self.copybot.order_executed.emit.assert_called_once()
    
    def test_execute_partial_sell_live_mode(self):
        """Test _execute_partial_sell in live trading mode"""
        # Setup
        self.mock_config.PAPER_TRADING_ENABLED = False
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        percentage = 75.0
        
        with patch('src.config', self.mock_config):
            # Execute
            result = self.copybot._execute_partial_sell(wallet, mint, token_data, self.mock_price_service, percentage)
            
            # Verify
            self.assertEqual(result, 'success')
            self.mock_nice_funcs.market_exit.assert_called_once_with('TEST', percentage=75.0)
    
    def test_execute_partial_sell_invalid_percentage(self):
        """Test _execute_partial_sell with invalid percentage"""
        # Setup
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        
        # Test invalid percentages
        for invalid_percentage in [0, -10, 150]:
            with self.subTest(percentage=invalid_percentage):
                result = self.copybot._execute_partial_sell(wallet, mint, token_data, self.mock_price_service, invalid_percentage)
                self.assertEqual(result, 'failed')
    
    def test_execute_partial_sell_excluded_token(self):
        """Test _execute_partial_sell with excluded token"""
        # Setup
        self.copybot._blocked_token.return_value = True
        wallet = "test_wallet_123"
        mint = "excluded_token"
        token_data = {
            'symbol': 'EXCLUDED',
            'name': 'Excluded Token'
        }
        percentage = 50.0
        
        # Execute
        result = self.copybot._execute_partial_sell(wallet, mint, token_data, self.mock_price_service, percentage)
        
        # Verify
        self.assertEqual(result, 'skipped')
        self.mock_paper_trading.execute_paper_trade.assert_not_called()
    
    def test_execute_half_sell_price_validation(self):
        """Test _execute_half_sell with price validation"""
        # Setup
        self.mock_price_service.get_price.return_value = 1000.0  # Unrealistic price
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        
        with patch('src.config', self.mock_config):
            # Execute
            result = self.copybot._execute_half_sell(wallet, mint, token_data, self.mock_price_service)
            
            # Verify
            self.assertEqual(result, 'failed')
            self.mock_paper_trading.execute_paper_trade.assert_not_called()
    
    def test_execute_partial_sell_trading_failure(self):
        """Test _execute_partial_sell when trading fails"""
        # Setup
        self.mock_paper_trading.execute_paper_trade.return_value = False
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        percentage = 50.0
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Execute
            result = self.copybot._execute_partial_sell(wallet, mint, token_data, self.mock_price_service, percentage)
            
            # Verify
            self.assertEqual(result, 'failed')
    
    def test_execute_half_sell_nice_funcs_unavailable(self):
        """Test _execute_half_sell when nice_funcs is unavailable in live mode"""
        # Setup
        self.mock_config.PAPER_TRADING_ENABLED = False
        self.copybot._get_nice_funcs.return_value = None
        wallet = "test_wallet_123"
        mint = "test_token_456"
        token_data = {
            'symbol': 'TEST',
            'name': 'Test Token'
        }
        
        with patch('src.config', self.mock_config):
            # Execute
            result = self.copybot._execute_half_sell(wallet, mint, token_data, self.mock_price_service)
            
            # Verify
            self.assertEqual(result, 'failed')


class TestSellTypeDetermination(unittest.TestCase):
    """Test sell type determination logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        with patch.dict('sys.modules', {
            'src.config': Mock(),
            'src.scripts.shared_services.logger': Mock()
        }):
            from src.scripts.webhooks.tracked_wallet_balance_cache import TrackedWalletBalanceCache
            self.balance_cache = TrackedWalletBalanceCache()
    
    def test_determine_sell_type_full(self):
        """Test full sell type determination"""
        # Test cases for full sell (95%+ sold)
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
    
    def test_determine_sell_type_half(self):
        """Test half sell type determination"""
        # Test cases for half sell (45-55% sold)
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
    
    def test_determine_sell_type_partial(self):
        """Test partial sell type determination"""
        # Test cases for partial sell (10-94% sold)
        test_cases = [
            (30.0, 'partial', 30.0),  # 30% sold
            (75.0, 'partial', 75.0),  # 75% sold
            (10.0, 'partial', 10.0),  # 10% sold
        ]
        
        for percentage_sold, expected_type, expected_percentage in test_cases:
            with self.subTest(percentage_sold=percentage_sold):
                sell_type, sell_percentage = self.balance_cache.determine_sell_type(percentage_sold)
                self.assertEqual(sell_type, expected_type)
                self.assertEqual(sell_percentage, expected_percentage)
    
    def test_determine_sell_type_skip(self):
        """Test skip sell type determination"""
        # Test cases for skip (less than 10% sold)
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
    
    def test_calculate_sell_percentage(self):
        """Test sell percentage calculation"""
        test_cases = [
            (100.0, 0.0, 100.0),    # All sold
            (100.0, 50.0, 50.0),    # Half sold
            (100.0, 100.0, 0.0),    # None sold
            (1000.0, 250.0, 75.0),  # 75% sold
            (0.0, 0.0, 0.0),        # No previous balance
        ]
        
        for previous, current, expected in test_cases:
            with self.subTest(previous=previous, current=current):
                result = self.balance_cache.calculate_sell_percentage(previous, current)
                self.assertEqual(result, expected)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestCopyBotSellTypes))
    test_suite.addTest(unittest.makeSuite(TestSellTypeDetermination))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
