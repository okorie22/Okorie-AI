#!/usr/bin/env python3
"""
🎬 Anarcho Capital's Enhanced Health Check Demo
Demonstrate the AI/Neural Network themed health monitoring system
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def demo_theme():
    """Demo the AI/Neural Network theme"""
    print("🎬 Demonstrating AI/Neural Network Theme...")
    print("=" * 60)
    
    try:
        from deploy.health_theme import get_theme, print_banner, print_header, print_status, print_metric, print_summary_stats
        
        # Show banner
        print_banner("DEMO NEURAL NETWORK")
        
        # Show headers
        print_header("🧠 Neural Network Demo", "Testing theme functionality")
        
        # Show status messages
        print_status("healthy", "System operational", "All neural pathways active")
        print_status("warning", "Memory usage elevated", "85% utilization detected")
        print_status("critical", "Database connection lost", "Attempting reconnection...")
        
        # Show metrics
        print_metric("CPU Usage", "42.3", "%", "healthy")
        print_metric("Memory", "7.8", "GB", "warning")
        print_metric("Cache Hit Rate", "94.7", "%", "healthy")
        print_metric("API Response", "156", "ms", "healthy")
        
        # Show progress bar
        theme = get_theme()
        theme.print_progress_bar(85, 100, "Neural Processing")
        
        # Show summary
        print_summary_stats({
            "total": 15,
            "passed": 12,
            "warnings": 2,
            "critical": 1
        })
        
        print("\n✅ Theme demo completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Theme demo failed: {e}")
        return False

def demo_health_check():
    """Demo the enhanced health check system"""
    print("\n🎬 Demonstrating Enhanced Health Check...")
    print("=" * 60)
    
    try:
        from deploy.enhanced_system_health_check import EnhancedSystemHealthCheck
        
        # Create health check instance
        health_check = EnhancedSystemHealthCheck(verbose=False, live_mode=False)
        
        print("Running comprehensive health check...")
        print("This may take a moment as we test all system components...")
        
        # Run health check
        results = health_check.run_health_check()
        
        # Get summary
        summary = health_check.get_health_summary(results)
        
        print(f"\n✅ Health check completed: {summary['passed']}/{summary['total']} checks passed")
        print(f"Health percentage: {summary['health_percentage']:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Health check demo failed: {e}")
        return False

def demo_live_dashboard():
    """Demo the live dashboard (briefly)"""
    print("\n🎬 Demonstrating Live Dashboard...")
    print("=" * 60)
    
    try:
        from deploy.enhanced_system_health_dashboard import LiveHealthDashboard
        
        # Create dashboard instance
        dashboard = LiveHealthDashboard(refresh_interval=5)
        
        print("Dashboard initialized successfully!")
        print("Features available:")
        print("  • Real-time system monitoring")
        print("  • AI/Neural Network themed interface")
        print("  • Comprehensive health checks")
        print("  • Performance metrics")
        print("  • Security validation")
        print("  • Data quality monitoring")
        
        print("\nTo run the live dashboard:")
        print("  python deploy/enhanced_system_health_dashboard.py")
        print("  python deploy/enhanced_system_health_dashboard.py --verbose")
        print("  python deploy/enhanced_system_health_dashboard.py --interval 15")
        
        return True
        
    except Exception as e:
        print(f"❌ Dashboard demo failed: {e}")
        return False

def main():
    """Main demo function"""
    print("🧠 Anarcho Capital Enhanced Health Check Demo")
    print("=" * 60)
    print("This demo showcases the AI/Neural Network themed health monitoring system")
    print("Built with love by Anarcho Capital 🚀")
    print()
    
    # Demo theme
    theme_success = demo_theme()
    
    # Demo health check
    health_success = demo_health_check()
    
    # Demo dashboard
    dashboard_success = demo_live_dashboard()
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 Demo Results Summary")
    print("=" * 60)
    
    print(f"🎨 Theme System: {'✅ SUCCESS' if theme_success else '❌ FAILED'}")
    print(f"🔧 Health Check: {'✅ SUCCESS' if health_success else '❌ FAILED'}")
    print(f"📊 Live Dashboard: {'✅ SUCCESS' if dashboard_success else '❌ FAILED'}")
    
    overall_success = theme_success and health_success and dashboard_success
    
    print(f"\n🎉 Overall Demo: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
    
    if overall_success:
        print("\n🚀 Enhanced health check system is ready for use!")
        print("\nAvailable commands:")
        print("  python deploy/enhanced_system_health_check.py          # Single health check")
        print("  python deploy/enhanced_system_health_check.py --verbose # Detailed health check")
        print("  python deploy/enhanced_system_health_dashboard.py      # Live monitoring")
        print("  python deploy/test_enhanced_health_check.py            # Run tests")
    else:
        print("\n⚠️  Some components need attention")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
