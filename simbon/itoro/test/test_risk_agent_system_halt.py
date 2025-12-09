#!/usr/bin/env python3
"""
Test for Risk Agent SYSTEM_HALT logic
Verifies manual review flag and liquidation behavior
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.agents.risk_agent import RiskAgent, PortfolioMetrics
from datetime import datetime

class TestRiskAgentSystemHalt(unittest.TestCase):
    """Test Risk Agent SYSTEM_HALT functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock all dependencies to avoid initialization errors
        with patch('src.agents.risk_agent.get_portfolio_tracker'), \
             patch('src.agents.risk_agent.get_optimized_price_service'), \
             patch('src.agents.risk_agent.get_breakeven_manager'), \
             patch('src.agents.risk_agent.get_execution_tracker'), \
             patch('src.agents.risk_agent.get_shared_data_coordinator'), \
             patch('src.agents.risk_agent.create_model'):
            self.risk_agent = RiskAgent()
    
    def test_requires_manual_review_initialized(self):
        """Test that requires_manual_review is initialized to False"""
        self.assertFalse(self.risk_agent.requires_manual_review, 
                        "requires_manual_review should be False by default")
    
    def test_execute_system_halt_sets_flag(self):
        """Test that execute_system_halt sets requires_manual_review flag"""
        # Mock execute_full_liquidation
        with patch.object(self.risk_agent, 'execute_full_liquidation', return_value=True), \
             patch('src.agents.risk_agent.config') as mock_config:
            mock_config.COPYBOT_ENABLED = True
            mock_config.COPYBOT_HALT_BUYS = False
            mock_config.COPYBOT_STOP_ALL = False
            
            result = self.risk_agent.execute_system_halt()
            
            # Verify flag is set
            self.assertTrue(self.risk_agent.requires_manual_review, 
                          "requires_manual_review should be True after SYSTEM_HALT")
            
            # Verify CopyBot is stopped
            self.assertFalse(mock_config.COPYBOT_ENABLED, 
                           "CopyBot should be disabled after SYSTEM_HALT")
            self.assertTrue(mock_config.COPYBOT_HALT_BUYS, 
                          "CopyBot should halt buys after SYSTEM_HALT")
            self.assertTrue(mock_config.COPYBOT_STOP_ALL, 
                          "CopyBot should stop all trading after SYSTEM_HALT")
    
    def test_auto_recovery_skips_with_manual_review_flag(self):
        """Test that auto-recovery skips when requires_manual_review is True"""
        # Set manual review flag
        self.risk_agent.requires_manual_review = True
        
        # Mock copybot flags
        self.risk_agent._copybot_stop_reason = "Emergency action: SYSTEM_HALT"
        
        # Call auto-recovery
        result = self.risk_agent.check_auto_recovery_conditions()
        
        # Should return False (skip recovery)
        self.assertFalse(result, "Auto-recovery should skip when manual review required")
    
    def test_force_clear_clears_manual_review_flag(self):
        """Test that force_clear_all_halts clears the requires_manual_review flag"""
        # Set flag
        self.risk_agent.requires_manual_review = True
        self.risk_agent._copybot_stop_reason = "Test reason"
        self.risk_agent._copybot_halt_reason = "Test halt reason"
        
        # Mock config
        with patch('src.agents.risk_agent.config') as mock_config:
            mock_config.COPYBOT_ENABLED = False
            mock_config.COPYBOT_HALT_BUYS = True
            mock_config.COPYBOT_STOP_ALL = True
            
            # Call force clear
            result = self.risk_agent.force_clear_all_halts()
            
            # Verify flag is cleared
            self.assertFalse(self.risk_agent.requires_manual_review, 
                           "requires_manual_review should be False after force_clear_all_halts")
            
            # Verify other flags are cleared
            self.assertIsNone(self.risk_agent._copybot_stop_reason)
            self.assertIsNone(self.risk_agent._copybot_halt_reason)
            self.assertTrue(mock_config.COPYBOT_ENABLED, "CopyBot should be enabled after clear")
    
    def test_system_halt_calls_full_liquidation(self):
        """Test that SYSTEM_HALT calls execute_full_liquidation"""
        # Mock execute_full_liquidation
        liquidation_mock = Mock(return_value=True)
        self.risk_agent.execute_full_liquidation = liquidation_mock
        
        with patch('src.agents.risk_agent.config') as mock_config:
            mock_config.COPYBOT_ENABLED = True
            mock_config.COPYBOT_HALT_BUYS = False
            mock_config.COPYBOT_STOP_ALL = False
            
            result = self.risk_agent.execute_system_halt()
            
            # Verify liquidation was called
            liquidation_mock.assert_called_once()

class TestSystemHaltIntegration(unittest.TestCase):
    """Integration tests for SYSTEM_HALT"""
    
    def test_system_halt_manual_review_flow(self):
        """Test complete SYSTEM_HALT -> MANUAL REVIEW -> RESTART flow"""
        # This tests the complete flow without actually executing
        with patch('src.agents.risk_agent.get_portfolio_tracker'), \
             patch('src.agents.risk_agent.get_optimized_price_service'), \
             patch('src.agents.risk_agent.get_breakeven_manager'), \
             patch('src.agents.risk_agent.get_execution_tracker'), \
             patch('src.agents.risk_agent.get_shared_data_coordinator'), \
             patch('src.agents.risk_agent.create_model'):
            
            risk_agent = RiskAgent()
            
            # Step 1: Verify initial state
            self.assertFalse(risk_agent.requires_manual_review)
            
            # Step 2: Execute SYSTEM_HALT
            with patch.object(risk_agent, 'execute_full_liquidation', return_value=True), \
                 patch('src.agents.risk_agent.config') as mock_config:
                mock_config.COPYBOT_ENABLED = True
                mock_config.COPYBOT_HALT_BUYS = False
                mock_config.COPYBOT_STOP_ALL = False
                
                risk_agent.execute_system_halt()
                
                # Verify SYSTEM_HALT sets manual review flag
                self.assertTrue(risk_agent.requires_manual_review)
                
                # Step 3: Verify auto-recovery is blocked
                recovery_result = risk_agent.check_auto_recovery_conditions()
                self.assertFalse(recovery_result, "Auto-recovery should be blocked")
                
                # Step 4: Manually clear with force_clear_all_halts
                mock_config.COPYBOT_ENABLED = False
                risk_agent.force_clear_all_halts()
                
                # Verify flag is cleared
                self.assertFalse(risk_agent.requires_manual_review)

def run_tests():
    """Run the test suite"""
    print("=" * 60)
    print("Testing Risk Agent SYSTEM_HALT Logic")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestRiskAgentSystemHalt)
    suite.addTests(loader.loadTestsFromTestCase(TestSystemHaltIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

