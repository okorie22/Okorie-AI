import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src import config

class TestStakingAgentConfig(unittest.TestCase):
    """Test staking agent configuration"""
    
    def test_staking_allocation_percent(self):
        """Test that staking allocation is set correctly"""
        self.assertEqual(config.STAKING_ALLOCATION_PERCENT, 50)
    
    def test_staking_calculation_with_current_balance(self):
        """Test that staking calculation works with current SOL balance"""
        sol_balance = 0.48  # Current balance from logs
        stake_percentage = config.STAKING_ALLOCATION_PERCENT
        
        stake_amount = sol_balance * (stake_percentage / 100)
        
        # Should be 0.24 SOL with 50% allocation
        self.assertAlmostEqual(stake_amount, 0.24, places=2)
        
        # Should be above minimum threshold
        self.assertGreater(stake_amount, 0.1)
    
    def test_min_sol_allocation_threshold(self):
        """Test minimum SOL allocation threshold"""
        self.assertEqual(config.MIN_SOL_ALLOCATION_THRESHOLD, 1.0)
    
    def test_staking_interval_enabled(self):
        """Test that staking interval is enabled"""
        self.assertTrue(config.STAKING_INTERVAL_ENABLED)
        self.assertEqual(config.STAKING_INTERVAL_MINUTES, 1440)  # 24 hours
    
    def test_staking_execution_mode(self):
        """Test staking execution mode"""
        self.assertEqual(config.STAKING_EXECUTION_MODE, "hybrid")
    
    def test_staking_webhook_enabled(self):
        """Test that staking webhook is enabled"""
        self.assertTrue(config.STAKING_WEBHOOK_ENABLED)
    
    def test_staking_minimum_threshold(self):
        """Test staking minimum threshold"""
        self.assertEqual(config.STAKING_MIN_THRESHOLD, 1)
    
    def test_staking_protocols_configured(self):
        """Test that staking protocols are configured"""
        self.assertIsInstance(config.STAKING_PROTOCOLS, list)
        self.assertGreater(len(config.STAKING_PROTOCOLS), 0)
    
    def test_staking_max_single_stake(self):
        """Test maximum single stake amount"""
        self.assertEqual(config.STAKING_MAX_SINGLE_STAKE_SOL, 0.5)
    
    def test_staking_min_single_stake(self):
        """Test minimum single stake amount"""
        self.assertEqual(config.STAKING_MIN_SINGLE_STAKE_SOL, 0.01)
    
    def test_staking_auto_select_best_apy(self):
        """Test auto select best APY setting"""
        self.assertTrue(config.STAKING_AUTO_SELECT_BEST_APY)
    
    def test_staking_fallback_protocol(self):
        """Test fallback protocol setting"""
        self.assertEqual(config.STAKING_FALLBACK_PROTOCOL, "blazestake")
    
    def test_staked_sol_tracking_enabled(self):
        """Test staked SOL tracking is enabled"""
        self.assertTrue(config.STAKED_SOL_TRACKING_ENABLED)
    
    def test_staked_sol_token_address(self):
        """Test staked SOL token address is configured"""
        self.assertIsNotNone(config.STAKED_SOL_TOKEN_ADDRESS)
        self.assertIsInstance(config.STAKED_SOL_TOKEN_ADDRESS, str)
    
    def test_staked_sol_symbol(self):
        """Test staked SOL symbol is configured"""
        self.assertEqual(config.STAKED_SOL_SYMBOL, "stSOL")
    
    def test_staking_rewards_threshold(self):
        """Test staking rewards threshold"""
        self.assertEqual(config.STAKING_REWARDS_THRESHOLD_SOL, 0.001)
    
    def test_staking_rewards_compound_percent(self):
        """Test staking rewards compound percentage"""
        self.assertEqual(config.STAKING_REWARDS_COMPOUND_PERCENT, 100.0)
    
    def test_staking_excess_percent(self):
        """Test staking excess percentage"""
        self.assertEqual(config.STAKING_EXCESS_PERCENT, 50.0)
    
    def test_staking_webhook_cooldown(self):
        """Test staking webhook cooldown"""
        self.assertEqual(config.STAKING_WEBHOOK_COOLDOWN_MINUTES, 5)
    
    def test_sol_target_allocation_percent(self):
        """Test SOL target allocation percentage"""
        self.assertEqual(config.SOL_TARGET_ALLOCATION_PERCENT, 10.0)
    
    def test_sol_excess_staking_threshold(self):
        """Test SOL excess staking threshold"""
        self.assertEqual(config.SOL_EXCESS_STAKING_THRESHOLD, 10.0)
    
    def test_sol_minimum_for_staking(self):
        """Test SOL minimum for staking"""
        self.assertEqual(config.SOL_MINIMUM_FOR_STAKING, 0.1)

if __name__ == '__main__':
    unittest.main()
