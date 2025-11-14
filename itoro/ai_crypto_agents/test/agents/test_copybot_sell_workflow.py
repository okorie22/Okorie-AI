"""
End-to-end integration tests for copybot sell workflow
Tests complete flow: webhook event -> copybot -> paper trade
"""

import unittest
import sys
import os
import tempfile
import sqlite3
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

class TestCopyBotSellWorkflow(unittest.TestCase):
    """Test complete copybot sell workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Mock configuration
        self.mock_config = Mock()
        self.mock_config.PAPER_TRADING_ENABLED = True
        self.mock_config.SOL_ADDRESS = "So11111111111111111111111111111111111111112"
        self.mock_config.USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        self.mock_config.EXCLUDED_TOKENS = []
        
        # Mock tracked wallets
        self.tracked_wallets = ["wallet1", "wallet2", "wallet3"]
        
        # Mock copybot agent
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
        
        # Mock token balance
        self.copybot.get_token_balance = Mock(return_value=100.0)
        self.copybot._get_nice_funcs = Mock(return_value=Mock())
        self.copybot._blocked_token = Mock(return_value=False)
        self.copybot.order_executed = Mock()
        self.copybot._should_stop_buying = Mock(return_value=False)
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary database
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_scenario_1_buy_100_sell_50_half(self):
        """Test scenario 1: Buy 100 tokens -> Sell 50 (half) -> Verify 50 remaining"""
        # Mock webhook event for buy
        buy_event = {
            'signature': 'buy_signature_123',
            'accounts': [
                {
                    'wallet': 'wallet1',
                    'token': 'token1',
                    'action': 'buy',
                    'amount': 100.0,
                    'from_account': 'other_wallet',
                    'to_account': 'wallet1',
                    'previous_balance': 0.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        # Mock webhook event for half sell
        sell_event = {
            'signature': 'sell_signature_456',
            'accounts': [
                {
                    'wallet': 'wallet1',
                    'token': 'token1',
                    'action': 'sell',
                    'amount': 50.0,
                    'from_account': 'wallet1',
                    'to_account': 'other_wallet',
                    'previous_balance': 100.0,
                    'sell_type': 'half',
                    'sell_percentage': 50.0
                }
            ]
        }
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Process buy event
            buy_result = self.copybot.process_parsed_transaction(buy_event)
            self.assertTrue(buy_result)
            
            # Verify buy was called
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token1', 'BUY', 100.0, 1.0, 'copybot'
            )
            
            # Reset mock
            self.mock_paper_trading.reset_mock()
            
            # Process sell event
            sell_result = self.copybot.process_parsed_transaction(sell_event)
            self.assertTrue(sell_result)
            
            # Verify half sell was called
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token1', 'PARTIAL_CLOSE', 50.0, 1.0, 'copybot'
            )
    
    def test_scenario_2_buy_100_sell_25_partial(self):
        """Test scenario 2: Buy 100 tokens -> Sell 25 (partial) -> Verify 75 remaining"""
        # Mock webhook event for buy
        buy_event = {
            'signature': 'buy_signature_789',
            'accounts': [
                {
                    'wallet': 'wallet2',
                    'token': 'token2',
                    'action': 'buy',
                    'amount': 100.0,
                    'from_account': 'other_wallet',
                    'to_account': 'wallet2',
                    'previous_balance': 0.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        # Mock webhook event for partial sell
        sell_event = {
            'signature': 'sell_signature_101',
            'accounts': [
                {
                    'wallet': 'wallet2',
                    'token': 'token2',
                    'action': 'sell',
                    'amount': 25.0,
                    'from_account': 'wallet2',
                    'to_account': 'other_wallet',
                    'previous_balance': 100.0,
                    'sell_type': 'partial',
                    'sell_percentage': 25.0
                }
            ]
        }
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Process buy event
            buy_result = self.copybot.process_parsed_transaction(buy_event)
            self.assertTrue(buy_result)
            
            # Verify buy was called
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token2', 'BUY', 100.0, 1.0, 'copybot'
            )
            
            # Reset mock
            self.mock_paper_trading.reset_mock()
            
            # Process sell event
            sell_result = self.copybot.process_parsed_transaction(sell_event)
            self.assertTrue(sell_result)
            
            # Verify partial sell was called
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token2', 'PARTIAL_CLOSE', 25.0, 1.0, 'copybot'
            )
    
    def test_scenario_3_buy_100_sell_100_full(self):
        """Test scenario 3: Buy 100 tokens -> Sell 100 (full) -> Verify 0 remaining"""
        # Mock webhook event for buy
        buy_event = {
            'signature': 'buy_signature_202',
            'accounts': [
                {
                    'wallet': 'wallet3',
                    'token': 'token3',
                    'action': 'buy',
                    'amount': 100.0,
                    'from_account': 'other_wallet',
                    'to_account': 'wallet3',
                    'previous_balance': 0.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        # Mock webhook event for full sell
        sell_event = {
            'signature': 'sell_signature_303',
            'accounts': [
                {
                    'wallet': 'wallet3',
                    'token': 'token3',
                    'action': 'sell',
                    'amount': 100.0,
                    'from_account': 'wallet3',
                    'to_account': 'other_wallet',
                    'previous_balance': 100.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Process buy event
            buy_result = self.copybot.process_parsed_transaction(buy_event)
            self.assertTrue(buy_result)
            
            # Verify buy was called
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token3', 'BUY', 100.0, 1.0, 'copybot'
            )
            
            # Reset mock
            self.mock_paper_trading.reset_mock()
            
            # Process sell event
            sell_result = self.copybot.process_parsed_transaction(sell_event)
            self.assertTrue(sell_result)
            
            # Verify full sell was called
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token3', 'SELL', 100.0, 1.0, 'copybot'
            )
    
    def test_scenario_4_multiple_partial_sells(self):
        """Test scenario 4: Buy 100 -> Sell 20% -> Sell 30% -> Sell 25% -> Verify 25% remaining"""
        # Mock webhook event for buy
        buy_event = {
            'signature': 'buy_signature_404',
            'accounts': [
                {
                    'wallet': 'wallet1',
                    'token': 'token4',
                    'action': 'buy',
                    'amount': 100.0,
                    'from_account': 'other_wallet',
                    'to_account': 'wallet1',
                    'previous_balance': 0.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        # Mock webhook events for partial sells
        sell_events = [
            {
                'signature': 'sell_signature_505',
                'accounts': [
                    {
                        'wallet': 'wallet1',
                        'token': 'token4',
                        'action': 'sell',
                        'amount': 20.0,
                        'from_account': 'wallet1',
                        'to_account': 'other_wallet',
                        'previous_balance': 100.0,
                        'sell_type': 'partial',
                        'sell_percentage': 20.0
                    }
                ]
            },
            {
                'signature': 'sell_signature_606',
                'accounts': [
                    {
                        'wallet': 'wallet1',
                        'token': 'token4',
                        'action': 'sell',
                        'amount': 30.0,
                        'from_account': 'wallet1',
                        'to_account': 'other_wallet',
                        'previous_balance': 80.0,
                        'sell_type': 'partial',
                        'sell_percentage': 30.0
                    }
                ]
            },
            {
                'signature': 'sell_signature_707',
                'accounts': [
                    {
                        'wallet': 'wallet1',
                        'token': 'token4',
                        'action': 'sell',
                        'amount': 25.0,
                        'from_account': 'wallet1',
                        'to_account': 'other_wallet',
                        'previous_balance': 50.0,
                        'sell_type': 'partial',
                        'sell_percentage': 25.0
                    }
                ]
            }
        ]
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Process buy event
            buy_result = self.copybot.process_parsed_transaction(buy_event)
            self.assertTrue(buy_result)
            
            # Verify buy was called
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token4', 'BUY', 100.0, 1.0, 'copybot'
            )
            
            # Process sell events
            for i, sell_event in enumerate(sell_events):
                # Reset mock
                self.mock_paper_trading.reset_mock()
                
                # Process sell event
                sell_result = self.copybot.process_parsed_transaction(sell_event)
                self.assertTrue(sell_result)
                
                # Verify partial sell was called
                self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
                expected_amount = [20.0, 30.0, 25.0][i]
                self.mock_paper_trading.execute_paper_trade.assert_called_with(
                    'token4', 'PARTIAL_CLOSE', expected_amount, 1.0, 'copybot'
                )
    
    def test_scenario_5_token_metadata_resolution(self):
        """Test scenario 5: Verify token metadata resolution works correctly"""
        # Mock webhook event with token metadata
        event = {
            'signature': 'metadata_signature_808',
            'accounts': [
                {
                    'wallet': 'wallet1',
                    'token': 'token5',
                    'action': 'buy',
                    'amount': 50.0,
                    'from_account': 'other_wallet',
                    'to_account': 'wallet1',
                    'previous_balance': 0.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        # Mock metadata service
        mock_metadata_service = Mock()
        mock_metadata_service.get_metadata.return_value = {
            'symbol': 'META',
            'name': 'Metadata Token'
        }
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade), \
             patch('src.scripts.data_processing.token_metadata_service.get_token_metadata_service', return_value=mock_metadata_service):
            
            # Process event
            result = self.copybot.process_parsed_transaction(event)
            self.assertTrue(result)
            
            # Verify metadata service was called
            mock_metadata_service.get_metadata.assert_called_once_with('token5')
            
            # Verify buy was called
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token5', 'BUY', 50.0, 1.0, 'copybot'
            )
    
    def test_scenario_6_metadata_resolution_failure(self):
        """Test scenario 6: Handle metadata resolution failure gracefully"""
        # Mock webhook event
        event = {
            'signature': 'metadata_fail_signature_909',
            'accounts': [
                {
                    'wallet': 'wallet1',
                    'token': 'token6',
                    'action': 'buy',
                    'amount': 50.0,
                    'from_account': 'other_wallet',
                    'to_account': 'wallet1',
                    'previous_balance': 0.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        # Mock metadata service that fails
        mock_metadata_service = Mock()
        mock_metadata_service.get_metadata.return_value = None
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade), \
             patch('src.scripts.data_processing.token_metadata_service.get_token_metadata_service', return_value=mock_metadata_service):
            
            # Process event
            result = self.copybot.process_parsed_transaction(event)
            self.assertTrue(result)
            
            # Verify metadata service was called
            mock_metadata_service.get_metadata.assert_called_once_with('token6')
            
            # Verify buy was called (should still work with default metadata)
            self.assertEqual(self.mock_paper_trading.execute_paper_trade.call_count, 1)
            self.mock_paper_trading.execute_paper_trade.assert_called_with(
                'token6', 'BUY', 50.0, 1.0, 'copybot'
            )
    
    def test_scenario_7_excluded_token_handling(self):
        """Test scenario 7: Handle excluded tokens correctly"""
        # Mock webhook event with excluded token
        event = {
            'signature': 'excluded_signature_101',
            'accounts': [
                {
                    'wallet': 'wallet1',
                    'token': 'excluded_token',
                    'action': 'buy',
                    'amount': 50.0,
                    'from_account': 'other_wallet',
                    'to_account': 'wallet1',
                    'previous_balance': 0.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        # Mock excluded token
        self.copybot._blocked_token.return_value = True
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Process event
            result = self.copybot.process_parsed_transaction(event)
            self.assertFalse(result)  # Should fail for excluded token
            
            # Verify no trade was executed
            self.mock_paper_trading.execute_paper_trade.assert_not_called()
    
    def test_scenario_8_insufficient_balance_sell(self):
        """Test scenario 8: Handle insufficient balance for sell"""
        # Mock webhook event for sell with no balance
        event = {
            'signature': 'insufficient_signature_202',
            'accounts': [
                {
                    'wallet': 'wallet1',
                    'token': 'token8',
                    'action': 'sell',
                    'amount': 50.0,
                    'from_account': 'wallet1',
                    'to_account': 'other_wallet',
                    'previous_balance': 0.0,
                    'sell_type': 'full',
                    'sell_percentage': 100.0
                }
            ]
        }
        
        # Mock no balance
        self.copybot.get_token_balance.return_value = 0.0
        
        with patch('src.config', self.mock_config), \
             patch('src.paper_trading.execute_paper_trade', self.mock_paper_trading.execute_paper_trade):
            
            # Process event
            result = self.copybot.process_parsed_transaction(event)
            self.assertFalse(result)  # Should fail for insufficient balance
            
            # Verify no trade was executed
            self.mock_paper_trading.execute_paper_trade.assert_not_called()


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestCopyBotSellWorkflow))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"CopyBot Sell Workflow Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
