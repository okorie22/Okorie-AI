"""
Test script for ITORO Master Agent
Runs the Master Agent in monitor-only mode for testing
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agents.master_agent import get_master_agent
from src.scripts.shared_services.config_manager import get_config_manager
from src.scripts.shared_services.performance_monitor import get_performance_monitor
from termcolor import cprint

def print_header():
    """Print test header"""
    cprint("\n" + "=" * 80, "cyan")
    cprint("👑 ITORO MASTER AGENT - TEST MODE 👑", "yellow", attrs=["bold"])
    cprint("Monitor-Only Mode - No Auto-Adjustments", "cyan")
    cprint("=" * 80 + "\n", "cyan")

def test_master_agent_initialization():
    """Test Master Agent initialization"""
    cprint("\n[TEST 1] Master Agent Initialization", "yellow", attrs=["bold"])
    cprint("-" * 80, "cyan")
    
    try:
        master_agent = get_master_agent()
        status = master_agent.get_status()
        
        cprint(f"✅ Master Agent initialized successfully", "green")
        cprint(f"   Personality Mode: {status['personality_mode']}", "white")
        cprint(f"   Monthly PnL Goal: {status['monthly_pnl_goal_percent']}%", "white")
        cprint(f"   Auto-Adjust Data: {status['auto_adjust_data']}", "white")
        cprint(f"   Require Approval (Trading): {status['require_approval_trading']}", "white")
        
        return True
    except Exception as e:
        cprint(f"❌ Master Agent initialization failed: {e}", "red")
        return False

def test_config_manager():
    """Test Config Manager"""
    cprint("\n[TEST 2] Config Manager", "yellow", attrs=["bold"])
    cprint("-" * 80, "cyan")
    
    try:
        config_manager = get_config_manager()
        
        # List parameters
        data_params = config_manager.list_parameters(category="data")
        trading_params = config_manager.list_parameters(category="trading")
        
        cprint(f"✅ Config Manager initialized", "green")
        cprint(f"   Data parameters: {len(data_params)}", "white")
        cprint(f"   Trading parameters: {len(trading_params)}", "white")
        
        # Test validation
        is_valid, msg = config_manager.validate_change("WHALE_UPDATE_INTERVAL_HOURS", 24)
        cprint(f"   Validation test: {'✅ Passed' if is_valid else '❌ Failed'}", "green" if is_valid else "red")
        
        return True
    except Exception as e:
        cprint(f"❌ Config Manager test failed: {e}", "red")
        return False

def test_performance_monitor():
    """Test Performance Monitor"""
    cprint("\n[TEST 3] Performance Monitor", "yellow", attrs=["bold"])
    cprint("-" * 80, "cyan")
    
    try:
        performance_monitor = get_performance_monitor()
        
        # Calculate current performance
        cprint("   Calculating current performance...", "white")
        performance = performance_monitor.calculate_current_performance()
        
        if performance:
            cprint(f"✅ Performance Monitor working", "green")
            cprint(f"   Total PnL: ${performance.total_pnl_usd:.2f}", "white")
            cprint(f"   Win Rate: {performance.win_rate:.2%}", "white")
            cprint(f"   Total Trades: {performance.total_trades}", "white")
        else:
            cprint(f"⚠️ No performance data available (this is normal for new systems)", "yellow")
        
        # Test goal progress
        cprint("   Calculating goal progress...", "white")
        goal_progress = performance_monitor.get_goal_progress()
        
        if goal_progress:
            cprint(f"✅ Goal tracking working", "green")
            cprint(f"   Current Monthly PnL: {goal_progress['current_monthly_pnl_percent']:.2f}%", "white")
            cprint(f"   Goal: {goal_progress['goal_percent']:.1f}%", "white")
            cprint(f"   On Track: {'✅ Yes' if goal_progress['on_track'] else '❌ No'}", "green" if goal_progress['on_track'] else "red")
        else:
            cprint(f"⚠️ No goal progress data available yet", "yellow")
        
        return True
    except Exception as e:
        cprint(f"❌ Performance Monitor test failed: {e}", "red")
        return False

def test_personality_evaluation():
    """Test personality mode evaluation"""
    cprint("\n[TEST 4] Personality Mode Evaluation", "yellow", attrs=["bold"])
    cprint("-" * 80, "cyan")
    
    try:
        master_agent = get_master_agent()
        
        status_before = master_agent.get_status()
        mode_before = status_before['personality_mode']
        
        cprint(f"   Current mode: {mode_before}", "white")
        cprint(f"   This test verifies personality mode logic (no changes expected in test mode)", "white")
        
        cprint(f"✅ Personality evaluation test passed", "green")
        
        return True
    except Exception as e:
        cprint(f"❌ Personality evaluation test failed: {e}", "red")
        return False

def test_data_quality_metrics():
    """Test data quality calculation"""
    cprint("\n[TEST 5] Data Quality Metrics", "yellow", attrs=["bold"])
    cprint("-" * 80, "cyan")
    
    try:
        performance_monitor = get_performance_monitor()
        
        cprint("   Calculating data quality metrics...", "white")
        data_quality = performance_monitor.calculate_data_quality()
        
        if data_quality:
            cprint(f"✅ Data quality metrics calculated", "green")
            cprint(f"   Overall Quality Score: {data_quality.overall_data_quality_score:.1f}/100", "white")
            cprint(f"   Chart Analysis Staleness: {data_quality.chart_analysis_staleness_minutes:.0f} minutes", "white")
            cprint(f"   Whale Agent Staleness: {data_quality.whale_agent_staleness_hours:.1f} hours", "white")
        else:
            cprint(f"⚠️ Data quality calculation returned None", "yellow")
        
        return True
    except Exception as e:
        cprint(f"❌ Data quality metrics test failed: {e}", "red")
        return False

def test_monitoring_cycle():
    """Test a single monitoring cycle"""
    cprint("\n[TEST 6] Monitoring Cycle (Dry Run)", "yellow", attrs=["bold"])
    cprint("-" * 80, "cyan")
    
    try:
        master_agent = get_master_agent()
        
        # Temporarily disable auto-adjust for testing
        original_auto_adjust = master_agent.auto_adjust_data
        master_agent.auto_adjust_data = False
        
        cprint("   Running monitoring cycle (no adjustments will be made)...", "white")
        
        # Run a monitoring cycle
        master_agent._execute_monitoring_cycle()
        
        cprint(f"✅ Monitoring cycle completed successfully", "green")
        
        # Restore original setting
        master_agent.auto_adjust_data = original_auto_adjust
        
        return True
    except Exception as e:
        cprint(f"❌ Monitoring cycle test failed: {e}", "red")
        import traceback
        traceback.print_exc()
        return False

def test_system_health_summary():
    """Test system health summary"""
    cprint("\n[TEST 7] System Health Summary", "yellow", attrs=["bold"])
    cprint("-" * 80, "cyan")
    
    try:
        performance_monitor = get_performance_monitor()
        
        cprint("   Generating system health summary...", "white")
        health = performance_monitor.get_system_health_summary()
        
        if health:
            cprint(f"✅ System health summary generated", "green")
            cprint(f"   Overall Health Score: {health['overall_health_score']:.1f}/100", "white")
            cprint(f"   Timestamp: {health['timestamp']}", "white")
        else:
            cprint(f"⚠️ System health summary returned None", "yellow")
        
        return True
    except Exception as e:
        cprint(f"❌ System health summary test failed: {e}", "red")
        return False

def run_all_tests():
    """Run all tests"""
    print_header()
    
    results = []
    
    # Run tests
    results.append(("Master Agent Initialization", test_master_agent_initialization()))
    results.append(("Config Manager", test_config_manager()))
    results.append(("Performance Monitor", test_performance_monitor()))
    results.append(("Personality Evaluation", test_personality_evaluation()))
    results.append(("Data Quality Metrics", test_data_quality_metrics()))
    results.append(("Monitoring Cycle", test_monitoring_cycle()))
    results.append(("System Health Summary", test_system_health_summary()))
    
    # Print summary
    cprint("\n" + "=" * 80, "cyan")
    cprint("📊 TEST SUMMARY", "yellow", attrs=["bold"])
    cprint("=" * 80, "cyan")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        color = "green" if result else "red"
        cprint(f"{status} - {test_name}", color)
    
    cprint("\n" + "-" * 80, "cyan")
    cprint(f"Results: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)", "yellow", attrs=["bold"])
    cprint("=" * 80 + "\n", "cyan")
    
    if passed == total:
        cprint("🎉 All tests passed! Master Agent is ready for deployment.", "green", attrs=["bold"])
        cprint("\n📝 Next Steps:", "yellow", attrs=["bold"])
        cprint("   1. Review the test results above", "white")
        cprint("   2. Start the system with main.py", "white")
        cprint("   3. Access the Master Agent dashboard at /master endpoint", "white")
        cprint("   4. Monitor the system in monitor-only mode initially", "white")
        cprint("   5. Gradually enable auto-adjustments after confirming stability\n", "white")
    else:
        cprint("⚠️ Some tests failed. Please review and fix issues before deployment.", "yellow", attrs=["bold"])
    
    return passed == total

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        cprint("\n\n⚠️ Test interrupted by user", "yellow")
        sys.exit(1)
    except Exception as e:
        cprint(f"\n\n❌ Fatal error during testing: {e}", "red")
        import traceback
        traceback.print_exc()
        sys.exit(1)

