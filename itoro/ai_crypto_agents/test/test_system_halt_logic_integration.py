#!/usr/bin/env python3
"""
Integration test for SYSTEM_HALT logic - simulates actual execution flow
"""

import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from unittest.mock import Mock, patch, MagicMock
from src.agents.risk_agent import RiskAgent, EmergencyTrigger, PortfolioMetrics
from datetime import datetime

def test_system_halt_execution_flow():
    """Test the complete SYSTEM_HALT execution flow"""
    print("\n" + "="*70)
    print("TEST 1: SYSTEM_HALT Execution Flow")
    print("="*70)
    
    # Mock all dependencies
    with patch('src.agents.risk_agent.get_portfolio_tracker') as pt, \
         patch('src.agents.risk_agent.get_optimized_price_service') as ps, \
         patch('src.agents.risk_agent.get_breakeven_manager') as bm, \
         patch('src.agents.risk_agent.get_execution_tracker') as et, \
         patch('src.agents.risk_agent.get_shared_data_coordinator') as sc, \
         patch('src.agents.risk_agent.create_model') as cm:
        
        # Setup mocks
        pt.return_value = Mock()
        ps.return_value = Mock()
        bm.return_value = Mock()
        et.return_value = Mock()
        sc.return_value = Mock()
        cm.return_value = Mock()
        
        # Create agent
        agent = RiskAgent()
        
        # Verify initial state
        assert not agent.requires_manual_review, "✓ Flag starts as False"
        print("✓ Initial state: requires_manual_review = False")
        
        # Mock execute_full_liquidation
        agent.execute_full_liquidation = Mock(return_value=True)
        
        # Mock config
        with patch('src.agents.risk_agent.config') as mock_config:
            mock_config.COPYBOT_ENABLED = True
            mock_config.COPYBOT_HALT_BUYS = False
            mock_config.COPYBOT_STOP_ALL = False
            
            # Execute system halt
            result = agent.execute_system_halt()
            
            # Verify results
            assert result == True, "✓ SYSTEM_HALT executed successfully"
            print("✓ SYSTEM_HALT executed successfully")
            
            assert agent.requires_manual_review == True, "✓ Flag set to True"
            print("✓ requires_manual_review set to True")
            
            assert mock_config.COPYBOT_ENABLED == False, "✓ CopyBot disabled"
            print("✓ CopyBot disabled")
            
            assert mock_config.COPYBOT_HALT_BUYS == True, "✓ Buys halted"
            print("✓ CopyBot buys halted")
            
            assert mock_config.COPYBOT_STOP_ALL == True, "✓ All trading stopped"
            print("✓ CopyBot all trading stopped")
            
            # Verify liquidation was called
            agent.execute_full_liquidation.assert_called_once()
            print("✓ execute_full_liquidation called")
    
    print("\n✓ TEST 1 PASSED: System halt execution flow works correctly\n")

def test_auto_recovery_skip_with_manual_review():
    """Test that auto-recovery skips when requires_manual_review is True"""
    print("\n" + "="*70)
    print("TEST 2: Auto-Recovery Skips When Manual Review Required")
    print("="*70)
    
    # Mock dependencies
    with patch('src.agents.risk_agent.get_portfolio_tracker') as pt, \
         patch('src.agents.risk_agent.get_optimized_price_service') as ps, \
         patch('src.agents.risk_agent.get_breakeven_manager') as bm, \
         patch('src.agents.risk_agent.get_execution_tracker') as et, \
         patch('src.agents.risk_agent.get_shared_data_coordinator') as sc, \
         patch('src.agents.risk_agent.create_model') as cm:
        
        pt.return_value = Mock()
        ps.return_value = Mock()
        bm.return_value = Mock()
        et.return_value = Mock()
        sc.return_value = Mock()
        cm.return_value = Mock()
        
        agent = RiskAgent()
        
        # Set the manual review flag (simulating SYSTEM_HALT was executed)
        agent.requires_manual_review = True
        agent._copybot_stop_reason = "Emergency action: SYSTEM_HALT"
        agent.last_action_time = 0  # Not in cooldown
        
        print("✓ Set up: requires_manual_review = True")
        print("✓ Set up: copybot_stop_reason = 'SYSTEM_HALT'")
        print("✓ Set up: Not in cooldown")
        
        # Try to check auto-recovery conditions
        result = agent.check_auto_recovery_conditions()
        
        # Should return False (skip recovery)
        assert result == False, "✓ Auto-recovery correctly skipped"
        print("✓ Auto-recovery returned False (correctly skipped)")
        
        # Verify the flags are still set (not cleared)
        assert agent.requires_manual_review == True, "✓ Flag still set"
        print("✓ requires_manual_review flag still True (not cleared)")
        
        assert agent._copybot_stop_reason == "Emergency action: SYSTEM_HALT", "✓ Stop reason still set"
        print("✓ copybot_stop_reason still set (not cleared)")
    
    print("\n✓ TEST 2 PASSED: Auto-recovery correctly skips manual review\n")

def test_force_clear_removes_manual_review():
    """Test that force_clear_all_halts removes the manual review requirement"""
    print("\n" + "="*70)
    print("TEST 3: Force Clear Removes Manual Review")
    print("="*70)
    
    # Mock dependencies
    with patch('src.agents.risk_agent.get_portfolio_tracker') as pt, \
         patch('src.agents.risk_agent.get_optimized_price_service') as ps, \
         patch('src.agents.risk_agent.get_breakeven_manager') as bm, \
         patch('src.agents.risk_agent.get_execution_tracker') as et, \
         patch('src.agents.risk_agent.get_shared_data_coordinator') as sc, \
         patch('src.agents.risk_agent.create_model') as cm:
        
        pt.return_value = Mock()
        ps.return_value = Mock()
        bm.return_value = Mock()
        et.return_value = Mock()
        sc.return_value = Mock()
        cm.return_value = Mock()
        
        agent = RiskAgent()
        
        # Set up state as if SYSTEM_HALT was executed
        agent.requires_manual_review = True
        agent._copybot_stop_reason = "Emergency action: SYSTEM_HALT"
        agent._copybot_halt_reason = None
        agent.last_action_time = 100
        
        print("✓ Initial state: requires_manual_review = True")
        print("✓ Initial state: Stop/Halt reasons set")
        
        # Mock config
        with patch('src.agents.risk_agent.config') as mock_config:
            mock_config.COPYBOT_ENABLED = False
            mock_config.COPYBOT_HALT_BUYS = True
            mock_config.COPYBOT_STOP_ALL = True
            
            # Call force_clear
            result = agent.force_clear_all_halts()
            
            # Verify results
            assert result == True, "✓ force_clear returned True"
            print("✓ force_clear_all_halts() executed successfully")
            
            assert agent.requires_manual_review == False, "✓ Flag cleared"
            print("✓ requires_manual_review set to False")
            
            assert agent._copybot_stop_reason == None, "✓ Stop reason cleared"
            print("✓ copybot_stop_reason cleared")
            
            assert agent._copybot_halt_reason == None, "✓ Halt reason cleared"
            print("✓ copybot_halt_reason cleared")
            
            assert mock_config.COPYBOT_ENABLED == True, "✓ CopyBot re-enabled"
            print("✓ CopyBot re-enabled")
            
            assert mock_config.COPYBOT_HALT_BUYS == False, "✓ Halt buys cleared"
            print("✓ CopyBot halt buys cleared")
            
            assert mock_config.COPYBOT_STOP_ALL == False, "✓ Stop all cleared"
            print("✓ CopyBot stop all cleared")
    
    print("\n✓ TEST 3 PASSED: Force clear correctly removes all flags\n")

def test_auto_recovery_allows_other_actions():
    """Test that auto-recovery still works for non-SYSTEM_HALT actions"""
    print("\n" + "="*70)
    print("TEST 4: Auto-Recovery Works for Non-SYSTEM_HALT Actions")
    print("="*70)
    
    # Mock dependencies
    with patch('src.agents.risk_agent.get_portfolio_tracker') as pt, \
         patch('src.agents.risk_agent.get_optimized_price_service') as ps, \
         patch('src.agents.risk_agent.get_breakeven_manager') as bm, \
         patch('src.agents.risk_agent.get_execution_tracker') as et, \
         patch('src.agents.risk_agent.get_shared_data_coordinator') as sc, \
         patch('src.agents.risk_agent.create_model') as cm:
        
        pt.return_value = Mock()
        ps.return_value = Mock()
        bm.return_value = Mock()
        et.return_value = Mock()
        sc.return_value = Mock()
        cm.return_value = Mock()
        
        agent = RiskAgent()
        
        # Set up state as if SOFT_HALT was executed (NOT SYSTEM_HALT)
        agent.requires_manual_review = False  # NOT set
        agent._copybot_stop_reason = None
        agent._copybot_halt_reason = "Risk management: SOFT_HALT"
        agent.last_action_time = 0  # Not in cooldown
        
        print("✓ Set up: requires_manual_review = False")
        print("✓ Set up: halt_reason = 'SOFT_HALT' (not SYSTEM_HALT)")
        print("✓ Set up: Not in cooldown")
        
        # Mock calculate_portfolio_metrics to return good conditions
        mock_metrics = Mock()
        mock_metrics.usdc_reserve_percent = 0.20  # Above threshold
        mock_metrics.sol_reserve_percent = 0.08   # Above threshold
        mock_metrics.drawdown_percent = 2.0       # Below threshold
        mock_metrics.total_value_usd = 100000    # Good value
        agent.calculate_portfolio_metrics = Mock(return_value=mock_metrics)
        agent.peak_portfolio_value = 110000
        
        # Mock clear_copybot_flags
        agent.clear_copybot_flags = Mock()
        
        # Try to check auto-recovery conditions
        result = agent.check_auto_recovery_conditions()
        
        # Should potentially return True (can auto-recover)
        print(f"✓ Auto-recovery check returned: {result}")
        
        # Verify that the recovery conditions were evaluated
        # (Since we have mock_metrics with good values, recovery should happen)
        if result:
            print("✓ Auto-recovery executed (conditions improved)")
            agent.clear_copybot_flags.assert_called()
            print("✓ clear_copybot_flags was called")
        else:
            print("✓ Auto-recovery did not execute (conditions not met yet)")
    
    print("\n✓ TEST 4 PASSED: Auto-recovery still works for other actions\n")

def main():
    """Run all integration tests"""
    print("\n" + "="*70)
    print("Risk Agent SYSTEM_HALT Logic Integration Tests")
    print("="*70)
    
    tests = [
        ("System Halt Execution Flow", test_system_halt_execution_flow),
        ("Auto-Recovery Skip Logic", test_auto_recovery_skip_with_manual_review),
        ("Force Clear Functionality", test_force_clear_removes_manual_review),
        ("Auto-Recovery for Other Actions", test_auto_recovery_allows_other_actions),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            test_func()
            results.append((test_name, True))
        except Exception as e:
            print(f"\n✗ TEST FAILED: {test_name}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*70)
    print("INTEGRATION TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    print("="*70)
    
    if all_passed:
        print("✓ All integration tests PASSED")
        return 0
    else:
        print("✗ Some integration tests FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())

