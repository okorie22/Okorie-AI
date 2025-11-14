"""
Integration tests for webhook sell type detection
Tests full event flow: webhook -> balance check -> sell type -> execution
"""

import unittest
import sys
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

class TestWebhookSellIntegration(unittest.TestCase):
    """Test webhook sell type detection integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock configuration
        self.mock_config = Mock()
        self.mock_config.HALF_SELL_THRESHOLD = 0.45
        self.mock_config.HALF_SELL_UPPER_THRESHOLD = 0.55
        self.mock_config.PARTIAL_SELL_MIN_THRESHOLD = 0.10
        self.mock_config.FULL_SELL_THRESHOLD = 0.95
        
        # Mock tracked wallets
        self.tracked_wallets = ["wallet1", "wallet2", "wallet3"]
        
        # Mock webhook handler
        with patch.dict('sys.modules', {
            'src.config': self.mock_config,
            'src.scripts.shared_services.logger': Mock(),
            'src.scripts.webhooks.tracked_wallet_balance_cache': Mock()
        }):
            from src.scripts.webhooks.webhook_handler import parse_transaction
            self.parse_transaction = parse_transaction
    
    def test_parse_transaction_half_sell(self):
        """Test webhook parsing for half sell detection"""
        # Mock balance cache
        mock_balance_cache = Mock()
        mock_balance_cache.get_previous_balance.return_value = 100.0
        mock_balance_cache.update_balance.return_value = {
            'previous_balance': 100.0,
            'current_balance': 50.0,
            'change_amount': -50.0,
            'change_percentage': 50.0,
            'sell_type': 'half',
            'sell_percentage': 50.0
        }
        
        # Mock webhook event
        webhook_event = {
            "type": "TRANSFER",
            "signature": "test_signature_123",
            "tokenTransfers": [
                {
                    "fromUserAccount": "wallet1",
                    "toUserAccount": "other_wallet",
                    "mint": "token1",
                    "tokenAmount": 50.0
                }
            ]
        }
        
        with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', self.tracked_wallets), \
             patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=mock_balance_cache):
            
            # Parse transaction
            result = self.parse_transaction(webhook_event)
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertEqual(result['signature'], 'test_signature_123')
            self.assertEqual(len(result['accounts']), 1)
            
            account = result['accounts'][0]
            self.assertEqual(account['wallet'], 'wallet1')
            self.assertEqual(account['token'], 'token1')
            self.assertEqual(account['amount'], 50.0)
            self.assertEqual(account['action'], 'sell')
            self.assertEqual(account['previous_balance'], 100.0)
            self.assertEqual(account['sell_type'], 'half')
            self.assertEqual(account['sell_percentage'], 50.0)
    
    def test_parse_transaction_partial_sell(self):
        """Test webhook parsing for partial sell detection"""
        # Mock balance cache
        mock_balance_cache = Mock()
        mock_balance_cache.get_previous_balance.return_value = 100.0
        mock_balance_cache.update_balance.return_value = {
            'previous_balance': 100.0,
            'current_balance': 70.0,
            'change_amount': -30.0,
            'change_percentage': 30.0,
            'sell_type': 'partial',
            'sell_percentage': 30.0
        }
        
        # Mock webhook event
        webhook_event = {
            "type": "TRANSFER",
            "signature": "test_signature_456",
            "tokenTransfers": [
                {
                    "fromUserAccount": "wallet2",
                    "toUserAccount": "other_wallet",
                    "mint": "token2",
                    "tokenAmount": 30.0
                }
            ]
        }
        
        with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', self.tracked_wallets), \
             patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=mock_balance_cache):
            
            # Parse transaction
            result = self.parse_transaction(webhook_event)
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertEqual(result['signature'], 'test_signature_456')
            self.assertEqual(len(result['accounts']), 1)
            
            account = result['accounts'][0]
            self.assertEqual(account['wallet'], 'wallet2')
            self.assertEqual(account['token'], 'token2')
            self.assertEqual(account['amount'], 30.0)
            self.assertEqual(account['action'], 'sell')
            self.assertEqual(account['previous_balance'], 100.0)
            self.assertEqual(account['sell_type'], 'partial')
            self.assertEqual(account['sell_percentage'], 30.0)
    
    def test_parse_transaction_full_sell(self):
        """Test webhook parsing for full sell detection"""
        # Mock balance cache
        mock_balance_cache = Mock()
        mock_balance_cache.get_previous_balance.return_value = 100.0
        mock_balance_cache.update_balance.return_value = {
            'previous_balance': 100.0,
            'current_balance': 0.0,
            'change_amount': -100.0,
            'change_percentage': 100.0,
            'sell_type': 'full',
            'sell_percentage': 100.0
        }
        
        # Mock webhook event
        webhook_event = {
            "type": "TRANSFER",
            "signature": "test_signature_789",
            "tokenTransfers": [
                {
                    "fromUserAccount": "wallet3",
                    "toUserAccount": "other_wallet",
                    "mint": "token3",
                    "tokenAmount": 100.0
                }
            ]
        }
        
        with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', self.tracked_wallets), \
             patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=mock_balance_cache):
            
            # Parse transaction
            result = self.parse_transaction(webhook_event)
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertEqual(result['signature'], 'test_signature_789')
            self.assertEqual(len(result['accounts']), 1)
            
            account = result['accounts'][0]
            self.assertEqual(account['wallet'], 'wallet3')
            self.assertEqual(account['token'], 'token3')
            self.assertEqual(account['amount'], 100.0)
            self.assertEqual(account['action'], 'sell')
            self.assertEqual(account['previous_balance'], 100.0)
            self.assertEqual(account['sell_type'], 'full')
            self.assertEqual(account['sell_percentage'], 100.0)
    
    def test_parse_transaction_buy_transaction(self):
        """Test webhook parsing for buy transaction (no sell type)"""
        # Mock webhook event
        webhook_event = {
            "type": "TRANSFER",
            "signature": "test_signature_buy",
            "tokenTransfers": [
                {
                    "fromUserAccount": "other_wallet",
                    "toUserAccount": "wallet1",
                    "mint": "token1",
                    "tokenAmount": 50.0
                }
            ]
        }
        
        with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', self.tracked_wallets), \
             patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=Mock()):
            
            # Parse transaction
            result = self.parse_transaction(webhook_event)
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertEqual(result['signature'], 'test_signature_buy')
            self.assertEqual(len(result['accounts']), 1)
            
            account = result['accounts'][0]
            self.assertEqual(account['wallet'], 'wallet1')
            self.assertEqual(account['token'], 'token1')
            self.assertEqual(account['amount'], 50.0)
            self.assertEqual(account['action'], 'buy')
            self.assertEqual(account['previous_balance'], 0.0)  # Default for buy
            self.assertEqual(account['sell_type'], 'full')      # Default for buy
            self.assertEqual(account['sell_percentage'], 100.0) # Default for buy
    
    def test_parse_transaction_balance_tracking_failure(self):
        """Test webhook parsing when balance tracking fails"""
        # Mock balance cache that raises exception
        mock_balance_cache = Mock()
        mock_balance_cache.get_previous_balance.side_effect = Exception("Balance tracking failed")
        
        # Mock webhook event
        webhook_event = {
            "type": "TRANSFER",
            "signature": "test_signature_error",
            "tokenTransfers": [
                {
                    "fromUserAccount": "wallet1",
                    "toUserAccount": "other_wallet",
                    "mint": "token1",
                    "tokenAmount": 50.0
                }
            ]
        }
        
        with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', self.tracked_wallets), \
             patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=mock_balance_cache):
            
            # Parse transaction
            result = self.parse_transaction(webhook_event)
            
            # Verify result (should fallback to defaults)
            self.assertIsNotNone(result)
            self.assertEqual(result['signature'], 'test_signature_error')
            self.assertEqual(len(result['accounts']), 1)
            
            account = result['accounts'][0]
            self.assertEqual(account['wallet'], 'wallet1')
            self.assertEqual(account['token'], 'token1')
            self.assertEqual(account['amount'], 50.0)
            self.assertEqual(account['action'], 'sell')
            self.assertEqual(account['previous_balance'], 0.0)  # Fallback default
            self.assertEqual(account['sell_type'], 'full')      # Fallback default
            self.assertEqual(account['sell_percentage'], 100.0) # Fallback default
    
    def test_parse_transaction_multiple_transfers(self):
        """Test webhook parsing with multiple token transfers"""
        # Mock balance cache
        mock_balance_cache = Mock()
        mock_balance_cache.get_previous_balance.return_value = 100.0
        mock_balance_cache.update_balance.return_value = {
            'previous_balance': 100.0,
            'current_balance': 50.0,
            'change_amount': -50.0,
            'change_percentage': 50.0,
            'sell_type': 'half',
            'sell_percentage': 50.0
        }
        
        # Mock webhook event with multiple transfers
        webhook_event = {
            "type": "TRANSFER",
            "signature": "test_signature_multi",
            "tokenTransfers": [
                {
                    "fromUserAccount": "wallet1",
                    "toUserAccount": "other_wallet",
                    "mint": "token1",
                    "tokenAmount": 50.0
                },
                {
                    "fromUserAccount": "wallet2",
                    "toUserAccount": "other_wallet",
                    "mint": "token2",
                    "tokenAmount": 25.0
                }
            ]
        }
        
        with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', self.tracked_wallets), \
             patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=mock_balance_cache):
            
            # Parse transaction
            result = self.parse_transaction(webhook_event)
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertEqual(result['signature'], 'test_signature_multi')
            self.assertEqual(len(result['accounts']), 2)
            
            # Check first account
            account1 = result['accounts'][0]
            self.assertEqual(account1['wallet'], 'wallet1')
            self.assertEqual(account1['token'], 'token1')
            self.assertEqual(account1['amount'], 50.0)
            self.assertEqual(account1['action'], 'sell')
            self.assertEqual(account1['sell_type'], 'half')
            
            # Check second account
            account2 = result['accounts'][1]
            self.assertEqual(account2['wallet'], 'wallet2')
            self.assertEqual(account2['token'], 'token2')
            self.assertEqual(account2['amount'], 25.0)
            self.assertEqual(account2['action'], 'sell')
            self.assertEqual(account2['sell_type'], 'half')
    
    def test_parse_transaction_no_tracked_wallets(self):
        """Test webhook parsing with no tracked wallets"""
        # Mock webhook event
        webhook_event = {
            "type": "TRANSFER",
            "signature": "test_signature_no_tracked",
            "tokenTransfers": [
                {
                    "fromUserAccount": "other_wallet1",
                    "toUserAccount": "other_wallet2",
                    "mint": "token1",
                    "tokenAmount": 50.0
                }
            ]
        }
        
        with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', self.tracked_wallets), \
             patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=Mock()):
            
            # Parse transaction
            result = self.parse_transaction(webhook_event)
            
            # Verify result (should be empty)
            self.assertIsNotNone(result)
            self.assertEqual(result['signature'], 'test_signature_no_tracked')
            self.assertEqual(len(result['accounts']), 0)


class TestWebhookSellTypeDetection(unittest.TestCase):
    """Test sell type detection logic in webhook processing"""
    
    def test_sell_type_detection_half_sell(self):
        """Test detection of half sell scenarios"""
        # Test cases for half sell detection
        test_cases = [
            (100.0, 50.0, 'half', 50.0),    # 50% sold
            (100.0, 45.0, 'half', 50.0),    # 45% sold
            (100.0, 55.0, 'half', 50.0),    # 55% sold
        ]
        
        for previous, current, expected_type, expected_percentage in test_cases:
            with self.subTest(previous=previous, current=current):
                # Mock balance cache
                mock_balance_cache = Mock()
                mock_balance_cache.get_previous_balance.return_value = previous
                mock_balance_cache.update_balance.return_value = {
                    'previous_balance': previous,
                    'current_balance': current,
                    'change_amount': current - previous,
                    'change_percentage': ((previous - current) / previous * 100) if previous > 0 else 0,
                    'sell_type': expected_type,
                    'sell_percentage': expected_percentage
                }
                
                # Mock webhook event
                webhook_event = {
                    "type": "TRANSFER",
                    "signature": "test_signature",
                    "tokenTransfers": [
                        {
                            "fromUserAccount": "wallet1",
                            "toUserAccount": "other_wallet",
                            "mint": "token1",
                            "tokenAmount": previous - current
                        }
                    ]
                }
                
                with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', ["wallet1"]), \
                     patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=mock_balance_cache):
                    
                    from src.scripts.webhooks.webhook_handler import parse_transaction
                    result = parse_transaction(webhook_event)
                    
                    # Verify sell type detection
                    self.assertIsNotNone(result)
                    self.assertEqual(len(result['accounts']), 1)
                    account = result['accounts'][0]
                    self.assertEqual(account['sell_type'], expected_type)
                    self.assertEqual(account['sell_percentage'], expected_percentage)
    
    def test_sell_type_detection_partial_sell(self):
        """Test detection of partial sell scenarios"""
        # Test cases for partial sell detection
        test_cases = [
            (100.0, 70.0, 'partial', 30.0),  # 30% sold
            (100.0, 25.0, 'partial', 75.0),  # 75% sold
            (100.0, 90.0, 'partial', 10.0),  # 10% sold
        ]
        
        for previous, current, expected_type, expected_percentage in test_cases:
            with self.subTest(previous=previous, current=current):
                # Mock balance cache
                mock_balance_cache = Mock()
                mock_balance_cache.get_previous_balance.return_value = previous
                mock_balance_cache.update_balance.return_value = {
                    'previous_balance': previous,
                    'current_balance': current,
                    'change_amount': current - previous,
                    'change_percentage': ((previous - current) / previous * 100) if previous > 0 else 0,
                    'sell_type': expected_type,
                    'sell_percentage': expected_percentage
                }
                
                # Mock webhook event
                webhook_event = {
                    "type": "TRANSFER",
                    "signature": "test_signature",
                    "tokenTransfers": [
                        {
                            "fromUserAccount": "wallet1",
                            "toUserAccount": "other_wallet",
                            "mint": "token1",
                            "tokenAmount": previous - current
                        }
                    ]
                }
                
                with patch('src.scripts.webhooks.webhook_handler.WALLETS_TO_TRACK', ["wallet1"]), \
                     patch('src.scripts.webhooks.webhook_handler.get_balance_cache', return_value=mock_balance_cache):
                    
                    from src.scripts.webhooks.webhook_handler import parse_transaction
                    result = parse_transaction(webhook_event)
                    
                    # Verify sell type detection
                    self.assertIsNotNone(result)
                    self.assertEqual(len(result['accounts']), 1)
                    account = result['accounts'][0]
                    self.assertEqual(account['sell_type'], expected_type)
                    self.assertEqual(account['sell_percentage'], expected_percentage)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestWebhookSellIntegration))
    test_suite.addTest(unittest.makeSuite(TestWebhookSellTypeDetection))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Webhook Integration Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
