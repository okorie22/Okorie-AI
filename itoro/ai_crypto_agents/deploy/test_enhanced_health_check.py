#!/usr/bin/env python3
"""
🧪 Anarcho Capital's Enhanced Health Check Test
Test the enhanced health check system and theme
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_theme():
    """Test the AI/Neural Network theme"""
    print("🧪 Testing AI/Neural Network Theme...")
    
    try:
        from deploy.health_theme import get_theme, print_banner, print_header, print_status, print_metric, print_summary_stats
        
        theme = get_theme()
        
        # Test banner
        print_banner("TEST BANNER")
        
        # Test header
        print_header("Test Section", "Testing neural theme functionality")
        
        # Test status messages
        print_status("healthy", "System operational", "All checks passed")
        print_status("warning", "High memory usage", "85% utilized")
        print_status("critical", "Database connection failed", "Retrying...")
        
        # Test metrics
        print_metric("CPU Usage", "45.2", "%", "healthy")
        print_metric("Memory", "8.5", "GB", "warning")
        print_metric("Cache Hit Rate", "92.3", "%", "healthy")
        
        # Test progress bar
        theme.print_progress_bar(75, 100, "Test Progress")
        
        # Test summary stats
        print_summary_stats({"total": 25, "passed": 20, "warnings": 4, "critical": 1})
        
        print("✅ Theme test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Theme test failed: {e}")
        return False

def test_health_checkers():
    """Test individual health checkers"""
    print("\n🧪 Testing Health Checkers...")
    
    test_results = {}
    
    # Test agent health monitor
    try:
        from src.scripts.shared_services.agent_health_monitor import get_agent_monitor
        agent_monitor = get_agent_monitor()
        summary = agent_monitor.get_agent_health_summary()
        test_results['agent_monitor'] = True
        print("✅ Agent health monitor: OK")
    except Exception as e:
        test_results['agent_monitor'] = False
        print(f"❌ Agent health monitor: {e}")
    
    # Test API health checker
    try:
        from src.scripts.shared_services.api_health_checker import get_api_checker
        api_checker = get_api_checker()
        summary = api_checker.get_api_health_summary()
        test_results['api_checker'] = True
        print("✅ API health checker: OK")
    except Exception as e:
        test_results['api_checker'] = False
        print(f"❌ API health checker: {e}")
    
    # Test database health checker
    try:
        from src.scripts.database.db_health_checker import get_db_checker
        db_checker = get_db_checker()
        summary = db_checker.get_database_health_summary()
        test_results['db_checker'] = True
        print("✅ Database health checker: OK")
    except Exception as e:
        test_results['db_checker'] = False
        print(f"❌ Database health checker: {e}")
    
    # Test performance monitor
    try:
        from src.scripts.shared_services.performance_monitor import get_performance_monitor
        perf_monitor = get_performance_monitor()
        summary = perf_monitor.get_performance_summary()
        test_results['performance_monitor'] = True
        print("✅ Performance monitor: OK")
    except Exception as e:
        test_results['performance_monitor'] = False
        print(f"❌ Performance monitor: {e}")
    
    # Test trading health checker
    try:
        from src.scripts.trading.trading_health_checker import get_trading_checker
        trading_checker = get_trading_checker()
        summary = trading_checker.get_trading_health_summary()
        test_results['trading_checker'] = True
        print("✅ Trading health checker: OK")
    except Exception as e:
        test_results['trading_checker'] = False
        print(f"❌ Trading health checker: {e}")
    
    # Test external dependencies checker
    try:
        from src.scripts.shared_services.external_deps_checker import get_deps_checker
        deps_checker = get_deps_checker()
        summary = deps_checker.get_dependencies_health_summary()
        test_results['deps_checker'] = True
        print("✅ External dependencies checker: OK")
    except Exception as e:
        test_results['deps_checker'] = False
        print(f"❌ External dependencies checker: {e}")
    
    # Test security checker
    try:
        from src.scripts.shared_services.security_checker import get_security_checker
        security_checker = get_security_checker()
        summary = security_checker.get_security_summary()
        test_results['security_checker'] = True
        print("✅ Security checker: OK")
    except Exception as e:
        test_results['security_checker'] = False
        print(f"❌ Security checker: {e}")
    
    # Test data quality checker
    try:
        from src.scripts.data_processing.data_quality_checker import get_data_quality_checker
        data_quality_checker = get_data_quality_checker()
        summary = data_quality_checker.get_data_quality_summary()
        test_results['data_quality_checker'] = True
        print("✅ Data quality checker: OK")
    except Exception as e:
        test_results['data_quality_checker'] = False
        print(f"❌ Data quality checker: {e}")
    
    # Test integration checker
    try:
        from src.scripts.webhooks.integration_checker import get_integration_checker
        integration_checker = get_integration_checker()
        summary = integration_checker.get_integration_summary()
        test_results['integration_checker'] = True
        print("✅ Integration checker: OK")
    except Exception as e:
        test_results['integration_checker'] = False
        print(f"❌ Integration checker: {e}")
    
    # Test business logic checker
    try:
        from src.scripts.trading.logic_health_checker import get_logic_checker
        logic_checker = get_logic_checker()
        summary = logic_checker.get_logic_health_summary()
        test_results['logic_checker'] = True
        print("✅ Business logic checker: OK")
    except Exception as e:
        test_results['logic_checker'] = False
        print(f"❌ Business logic checker: {e}")
    
    return test_results

def test_enhanced_health_check():
    """Test the enhanced health check system"""
    print("\n🧪 Testing Enhanced Health Check System...")
    
    try:
        from deploy.enhanced_system_health_check import EnhancedSystemHealthCheck
        
        # Create health check instance
        health_check = EnhancedSystemHealthCheck(verbose=False, live_mode=False)
        
        # Run a quick health check
        print("Running health check...")
        results = health_check.run_health_check()
        
        # Get summary
        summary = health_check.get_health_summary(results)
        print(f"Health check completed: {summary['passed']}/{summary['total']} checks passed")
        
        print("✅ Enhanced health check system: OK")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced health check system: {e}")
        return False

def test_live_dashboard():
    """Test the live dashboard (without running it)"""
    print("\n🧪 Testing Live Dashboard...")
    
    try:
        from deploy.enhanced_system_health_dashboard import LiveHealthDashboard
        
        # Create dashboard instance
        dashboard = LiveHealthDashboard(refresh_interval=30)
        
        # Test dashboard initialization
        print("Dashboard initialized successfully")
        
        print("✅ Live dashboard: OK")
        return True
        
    except Exception as e:
        print(f"❌ Live dashboard: {e}")
        return False

def main():
    """Main test function"""
    print("🧠 Anarcho Capital Enhanced Health Check Test Suite")
    print("=" * 60)
    
    # Test theme
    theme_success = test_theme()
    
    # Test health checkers
    checker_results = test_health_checkers()
    
    # Test enhanced health check
    health_check_success = test_enhanced_health_check()
    
    # Test live dashboard
    dashboard_success = test_live_dashboard()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    print(f"🎨 Theme System: {'✅ PASS' if theme_success else '❌ FAIL'}")
    print(f"🔧 Enhanced Health Check: {'✅ PASS' if health_check_success else '❌ FAIL'}")
    print(f"📊 Live Dashboard: {'✅ PASS' if dashboard_success else '❌ FAIL'}")
    
    print("\n🔍 Individual Health Checkers:")
    for checker_name, success in checker_results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {checker_name}")
    
    # Overall result
    all_checkers_passed = all(checker_results.values())
    overall_success = theme_success and health_check_success and dashboard_success and all_checkers_passed
    
    print(f"\n🎯 Overall Test Result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    if overall_success:
        print("\n🎉 Enhanced health check system is ready for use!")
        print("Run 'python deploy/enhanced_system_health_check.py' for a full health check")
        print("Run 'python deploy/enhanced_system_health_dashboard.py' for live monitoring")
    else:
        print("\n⚠️  Some components need attention before the system is ready")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
