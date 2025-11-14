#!/usr/bin/env python3
"""
🧠 Anarcho Capital's Enhanced Live Health Dashboard
Real-time AI/Neural Network themed system monitoring
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

# Try to import keyboard module, make it optional
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("⚠️  Keyboard module not available - shortcuts disabled")

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import theme and health check modules
from deploy.health_theme import get_theme, print_banner, print_header, print_status, print_metric, print_summary_stats
from deploy.enhanced_system_health_check import EnhancedSystemHealthCheck

class LiveHealthDashboard:
    """Live health monitoring dashboard with AI/Neural Network theme"""
    
    def __init__(self, refresh_interval: int = 30):
        self.refresh_interval = refresh_interval
        self.theme = get_theme()
        self.health_check = EnhancedSystemHealthCheck(verbose=False, live_mode=True)
        self.running = False
        self.verbose = False
        self.current_results = {}
        self.dashboard_thread = None
        
        # Performance tracking
        self.refresh_count = 0
        self.start_time = datetime.now()
        self.last_refresh = datetime.now()
        
        # Keyboard shortcuts
        self.setup_keyboard_shortcuts()
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for dashboard control"""
        if not KEYBOARD_AVAILABLE:
            return
            
        try:
            keyboard.add_hotkey('q', self.quit_dashboard)
            keyboard.add_hotkey('v', self.toggle_verbose)
            keyboard.add_hotkey('r', self.force_refresh)
            keyboard.add_hotkey('h', self.show_help)
        except Exception as e:
            print(f"Warning: Could not setup keyboard shortcuts: {e}")
    
    def quit_dashboard(self):
        """Quit the dashboard"""
        self.running = False
        print("\n🛑 Shutting down neural network monitoring...")
    
    def toggle_verbose(self):
        """Toggle verbose mode"""
        self.verbose = not self.verbose
        print(f"\n{'🔍' if self.verbose else '📊'} Verbose mode: {'ON' if self.verbose else 'OFF'}")
    
    def force_refresh(self):
        """Force immediate refresh"""
        print("\n🔄 Forcing neural network refresh...")
        self.refresh_dashboard()
    
    def show_help(self):
        """Show help information"""
        help_text = """
🧠 Neural Network Dashboard Help
═══════════════════════════════════
Keyboard Shortcuts:
  Q - Quit dashboard
  V - Toggle verbose mode
  R - Force refresh
  H - Show this help
  
Dashboard Features:
  • Real-time system monitoring
  • AI/Neural Network themed interface
  • Comprehensive health checks
  • Performance metrics
  • Security validation
  • Data quality monitoring
        """
        print(help_text)
    
    def refresh_dashboard(self):
        """Refresh dashboard data"""
        try:
            self.last_refresh = datetime.now()
            self.refresh_count += 1
            
            # Run health check
            self.current_results = self.health_check.run_health_check()
            
        except Exception as e:
            print(f"❌ Error refreshing dashboard: {e}")
    
    def display_dashboard(self):
        """Display the main dashboard"""
        self.theme.clear_screen()
        print_banner("ANARCHO CAPITAL LIVE MONITOR")
        
        # Display header with refresh info
        uptime = datetime.now() - self.start_time
        print_header(
            "🧠 Neural Network Live Monitoring", 
            f"Uptime: {uptime.total_seconds()/3600:.1f}h | Refreshes: {self.refresh_count} | Last: {self.last_refresh.strftime('%H:%M:%S')}"
        )
        
        if not self.current_results:
            print_status("checking", "Initializing neural network analysis...", "Please wait")
            return
        
        # Display summary stats
        summary = self.health_check.get_health_summary(self.current_results)
        print_summary_stats(summary)
        
        # Display key metrics
        self.display_key_metrics()
        
        # Display detailed results if verbose
        if self.verbose:
            self.display_detailed_results()
        
        # Display recommendations
        self.display_recommendations()
        
        # Display footer
        self.theme.print_footer("Q: Quit | V: Verbose | R: Refresh | H: Help")
    
    def display_key_metrics(self):
        """Display key system metrics"""
        print_header("⚡ Key Neural Pathways", "Critical system metrics")
        
        # Get performance metrics
        try:
            perf_summary = self.health_check.performance_monitor.get_performance_summary()
            current = perf_summary['current']
            
            print_metric("CPU Usage", f"{current['cpu_percent']:.1f}%", status="healthy" if current['cpu_percent'] < 70 else "warning")
            print_metric("Memory Usage", f"{current['memory_percent']:.1f}%", status="healthy" if current['memory_percent'] < 80 else "warning")
            print_metric("Cache Hit Rate", f"{current['cache_hit_rate']:.1%}", status="healthy" if current['cache_hit_rate'] > 0.8 else "warning")
            print_metric("API Response Time", f"{current['api_response_time_ms']:.0f}ms", status="healthy" if current['api_response_time_ms'] < 2000 else "warning")
            
        except Exception as e:
            print_status("warning", f"Performance metrics unavailable: {str(e)}")
        
        # Get agent status
        try:
            agent_summary = self.health_check.agent_monitor.get_agent_health_summary()
            print_metric("Active Agents", f"{agent_summary['running_agents']}/{agent_summary['total_agents']}", 
                        status="healthy" if agent_summary['health_percentage'] > 80 else "warning")
            
        except Exception as e:
            print_status("warning", f"Agent metrics unavailable: {str(e)}")
        
        # Get trading status
        try:
            trading_summary = self.health_check.trading_checker.get_trading_health_summary()
            print_metric("Trading Health", f"{trading_summary['health_percentage']:.1f}%", 
                        status="healthy" if trading_summary['health_percentage'] > 80 else "warning")
            
        except Exception as e:
            print_status("warning", f"Trading metrics unavailable: {str(e)}")
    
    def display_detailed_results(self):
        """Display detailed health check results"""
        print_header("🔍 Detailed Neural Analysis", "Comprehensive system diagnostics")
        
        for category_name, result in self.current_results.items():
            status_icon = self.theme._get_status_icon(result['status'])
            print(f"\n{status_icon} {category_name}")
            
            if 'error' in result:
                print(f"  Error: {result['error']}")
            elif 'summary' in result:
                summary = result['summary']
                if isinstance(summary, dict):
                    for key, value in summary.items():
                        if isinstance(value, (int, float, str)) and key not in ['total', 'passed', 'warnings', 'critical']:
                            print_metric(key.replace('_', ' ').title(), str(value))
    
    def display_recommendations(self):
        """Display system recommendations"""
        print_header("💡 Neural Optimization Suggestions", "System improvement recommendations")
        
        recommendations = []
        
        try:
            # Collect recommendations from all checkers
            recommendations.extend(self.health_check.agent_monitor.get_agent_health_summary().get('recommendations', []))
            recommendations.extend(self.health_check.api_checker.get_api_health_summary().get('recommendations', []))
            recommendations.extend(self.health_check.db_checker.get_database_recommendations())
            recommendations.extend(self.health_check.trading_checker.get_trading_recommendations())
            recommendations.extend(self.health_check.deps_checker.get_dependencies_recommendations())
            recommendations.extend(self.health_check.security_checker.get_security_recommendations())
            recommendations.extend(self.health_check.data_quality_checker.get_data_quality_recommendations())
            recommendations.extend(self.health_check.integration_checker.get_integration_recommendations())
            recommendations.extend(self.health_check.logic_checker.get_logic_recommendations())
        except Exception as e:
            recommendations.append(f"Error collecting recommendations: {str(e)}")
        
        # Display top recommendations
        unique_recommendations = list(set(recommendations))
        for i, rec in enumerate(unique_recommendations[:5], 1):  # Show top 5
            print(f"  {i}. {rec}")
        
        if len(unique_recommendations) > 5:
            print(f"  ... and {len(unique_recommendations) - 5} more recommendations")
    
    def run_dashboard(self):
        """Run the live dashboard"""
        print("🚀 Starting Neural Network Live Dashboard...")
        print("Press 'H' for help, 'Q' to quit")
        time.sleep(2)
        
        self.running = True
        
        try:
            while self.running:
                self.refresh_dashboard()
                self.display_dashboard()
                
                # Wait for next refresh
                for _ in range(self.refresh_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n🛑 Dashboard interrupted by user")
        except Exception as e:
            print(f"\n❌ Dashboard error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.unhook_all()
            except:
                pass
        
        print("🧠 Neural network monitoring stopped")
        print("Thank you for using Anarcho Capital's AI Trading System!")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Live Health Dashboard')
    parser.add_argument('-i', '--interval', type=int, default=30, help='Refresh interval in seconds (default: 30)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Start in verbose mode')
    
    args = parser.parse_args()
    
    # Create and run dashboard
    dashboard = LiveHealthDashboard(refresh_interval=args.interval)
    dashboard.verbose = args.verbose
    dashboard.run_dashboard()

if __name__ == "__main__":
    main()
