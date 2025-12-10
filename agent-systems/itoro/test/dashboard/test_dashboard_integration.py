import unittest
import sys
import os
from io import StringIO
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.dashboard import CyberpunkDashboard

class TestDashboardIntegration(unittest.TestCase):
    """Integration tests for dashboard rendering"""
    
    def setUp(self):
        """Set up test dashboard instance"""
        self.dashboard = CyberpunkDashboard()
    
    @patch('src.dashboard.DatabaseManager')
    @patch('src.dashboard.PortfolioData')
    def test_staked_sol_display_with_balance(self, mock_portfolio, mock_db):
        """Test staked SOL displays correctly when balance exists"""
        # Mock portfolio data with staked SOL
        portfolio_data = {
            'total_value': 1000.0,
            'sol_balance': 5.0,
            'sol_price': 186.92,
            'sol_value': 934.60,
            'sol_pct': 93.46,
            'staked_sol_balance': 2.5,
            'staked_sol_value': 467.30,
            'staked_sol_pct': 46.73,
            'usdc_balance': 65.40,
            'usdc_pct': 6.54,
            'positions_value': 0,
            'positions_pct': 0,
            'position_count': 0,
            'positions': {}
        }
        
        # Set the portfolio data directly on the dashboard
        self.dashboard.current_portfolio = portfolio_data
        
        # Capture output
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.dashboard._render_portfolio_section()
            output = fake_out.getvalue()
            
            # Verify staked SOL is displayed
            self.assertIn('Staked SOL', output)
            self.assertIn('2.5', output)
            self.assertIn('467.30', output)
    
    @patch('src.dashboard.DatabaseManager')
    @patch('src.dashboard.PortfolioData')
    def test_staked_sol_display_zero_balance(self, mock_portfolio, mock_db):
        """Test staked SOL displays as 0 when no balance"""
        # Mock portfolio data without staked SOL
        portfolio_data = {
            'total_value': 1000.0,
            'sol_balance': 0.48,
            'sol_price': 186.92,
            'sol_value': 89.72,
            'sol_pct': 8.97,
            'staked_sol_balance': 0.0,
            'staked_sol_value': 0.0,
            'staked_sol_pct': 0.0,
            'usdc_balance': 910.28,
            'usdc_pct': 91.03,
            'positions_value': 0,
            'positions_pct': 0,
            'position_count': 0,
            'positions': {}
        }
        
        # Set the portfolio data directly on the dashboard
        self.dashboard.current_portfolio = portfolio_data
        
        # Capture output
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.dashboard._render_portfolio_section()
            output = fake_out.getvalue()
            
            # Verify staked SOL shows 0.00
            self.assertIn('Staked SOL', output)
            self.assertIn('0.00', output)
    
    @patch('src.dashboard.TradeData')
    def test_price_display_small_values(self, mock_trade_data):
        """Test that small prices display in exponential notation"""
        # Mock trades with small prices
        mock_trade_data.return_value.get_recent_trades.return_value = [
            {
                'timestamp': '18:47:02',
                'action': 'BUY',
                'amount': 120877.00,
                'token': '2cmWzBaN',
                'price': 0.000409,
                'usd_value': 49.44,
                'agent': 'copybot'
            }
        ]
        
        self.dashboard.current_trades = mock_trade_data.return_value.get_recent_trades.return_value
        
        # Capture output
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.dashboard._render_trades_section()
            output = fake_out.getvalue()
            
            # Verify exponential notation
            self.assertIn('4.09e-04', output)
    
    @patch('src.dashboard.TradeData')
    def test_price_display_normal_values(self, mock_trade_data):
        """Test that normal prices display in decimal notation"""
        # Mock trades with normal prices
        mock_trade_data.return_value.get_recent_trades.return_value = [
            {
                'timestamp': '18:47:02',
                'action': 'BUY',
                'amount': 100.00,
                'token': 'SOL',
                'price': 186.92,
                'usd_value': 18692.00,
                'agent': 'copybot'
            }
        ]
        
        self.dashboard.current_trades = mock_trade_data.return_value.get_recent_trades.return_value
        
        # Capture output
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.dashboard._render_trades_section()
            output = fake_out.getvalue()
            
            # Verify decimal notation
            self.assertIn('186.9200', output)
    
    @patch('src.dashboard.TradeData')
    def test_win_loss_display_with_trades(self, mock_trade_data):
        """Test win/loss statistics display with actual trades"""
        # Mock trades with both wins and losses
        mock_trade_data.return_value.get_recent_trades.return_value = [
            {'token': 'WIN', 'action': 'BUY', 'price': 1.0, 'amount': 100, 'timestamp': '18:00:00', 'usd_value': 100, 'agent': 'copybot'},
            {'token': 'WIN', 'action': 'SELL', 'price': 1.5, 'amount': 100, 'timestamp': '18:01:00', 'usd_value': 150, 'agent': 'copybot'},
            {'token': 'LOSS', 'action': 'BUY', 'price': 2.0, 'amount': 50, 'timestamp': '18:02:00', 'usd_value': 100, 'agent': 'copybot'},
            {'token': 'LOSS', 'action': 'SELL', 'price': 1.8, 'amount': 50, 'timestamp': '18:03:00', 'usd_value': 90, 'agent': 'copybot'},
        ]
        
        self.dashboard.current_trades = mock_trade_data.return_value.get_recent_trades.return_value
        
        # Test the win/loss calculation
        result = self.dashboard._get_lightweight_win_loss()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['total_trades'], 2)
        # With WIN (1.0->1.5) then LOSS (2.0->1.8), consecutive should be 0 wins, 1 loss
        self.assertEqual(result['consecutive_wins'], 0)  # Last trade was a loss
        self.assertEqual(result['consecutive_losses'], 1)  # Last trade was a loss
        self.assertEqual(result['win_rate'], 50.0)
    
    @patch('src.dashboard.TradeData')
    def test_win_loss_display_no_closed_positions(self, mock_trade_data):
        """Test win/loss statistics with only open positions"""
        # Mock trades with only buys (no sells)
        mock_trade_data.return_value.get_recent_trades.return_value = [
            {'token': 'OPEN1', 'action': 'BUY', 'price': 1.0, 'amount': 100, 'timestamp': '18:00:00', 'usd_value': 100, 'agent': 'copybot'},
            {'token': 'OPEN2', 'action': 'BUY', 'price': 2.0, 'amount': 50, 'timestamp': '18:01:00', 'usd_value': 100, 'agent': 'copybot'},
        ]
        
        self.dashboard.current_trades = mock_trade_data.return_value.get_recent_trades.return_value
        
        # Test the win/loss calculation
        result = self.dashboard._get_lightweight_win_loss()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['total_trades'], 0)
        self.assertEqual(result['consecutive_wins'], 0)  # Updated key name
        self.assertEqual(result['consecutive_losses'], 0)  # Updated key name
        self.assertEqual(result['win_rate'], 0.0)
    
    @patch('src.dashboard.DatabaseManager')
    @patch('src.dashboard.PortfolioData')
    @patch('src.dashboard.TradeData')
    def test_full_dashboard_rendering(self, mock_trade_data, mock_portfolio, mock_db):
        """Test complete dashboard rendering with all components"""
        # Mock portfolio data
        mock_portfolio.return_value.get_latest_portfolio.return_value = {
            'total_value': 1000.0,
            'sol_balance': 0.48,
            'sol_price': 186.92,
            'sol_value': 89.72,
            'sol_pct': 8.97,
            'staked_sol_balance': 0.0,
            'staked_sol_value': 0.0,
            'staked_sol_pct': 0.0,
            'usdc_balance': 910.28,
            'usdc_pct': 91.03,
            'positions_value': 0,
            'positions_pct': 0,
            'position_count': 0,
            'positions': {}
        }
        
        # Mock trade data
        mock_trade_data.return_value.get_recent_trades.return_value = [
            {
                'timestamp': '18:47:02',
                'action': 'BUY',
                'amount': 120877.00,
                'token': '2cmWzBaN',
                'price': 0.000409,
                'usd_value': 49.44,
                'agent': 'copybot'
            }
        ]
        
        # Set up dashboard state
        self.dashboard.current_portfolio = mock_portfolio.return_value.get_latest_portfolio.return_value
        self.dashboard.current_trades = mock_trade_data.return_value.get_recent_trades.return_value
        
        # Capture output
        with patch('sys.stdout', new=StringIO()) as fake_out:
            # Test individual sections
            self.dashboard._render_portfolio_section()
            portfolio_output = fake_out.getvalue()
            
            # Reset for trades section
            fake_out.seek(0)
            fake_out.truncate(0)
            
            self.dashboard._render_trades_section()
            trades_output = fake_out.getvalue()
            
            # Verify portfolio section contains staked SOL
            self.assertIn('Staked SOL', portfolio_output)
            self.assertIn('0.00', portfolio_output)
            
            # Verify trades section contains exponential notation
            self.assertIn('4.09e-04', trades_output)

if __name__ == '__main__':
    unittest.main()
