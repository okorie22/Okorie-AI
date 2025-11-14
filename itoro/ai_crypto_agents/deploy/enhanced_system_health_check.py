#!/usr/bin/env python3
"""
🧠 Anarcho Capital's Enhanced System Health Check
Comprehensive AI/Neural Network themed health monitoring system
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import theme and health check modules
from deploy.health_theme import get_theme, print_banner, print_header, print_status, print_metric, print_summary_stats
from src.scripts.shared_services.agent_health_monitor import get_agent_monitor
from src.scripts.shared_services.api_health_checker import get_api_checker
from src.scripts.database.db_health_checker import get_db_checker
from src.scripts.shared_services.performance_monitor import get_performance_monitor
from src.scripts.trading.trading_health_checker import get_trading_checker
from src.scripts.shared_services.external_deps_checker import get_deps_checker
from src.scripts.shared_services.security_checker import get_security_checker
from src.scripts.data_processing.data_quality_checker import get_data_quality_checker
from src.scripts.webhooks.integration_checker import get_integration_checker
from src.scripts.trading.logic_health_checker import get_logic_checker

class EnhancedSystemHealthCheck:
    """Enhanced system health check with AI/Neural Network theme"""
    
    def __init__(self, verbose: bool = False, live_mode: bool = False):
        self.verbose = verbose
        self.live_mode = live_mode
        self.theme = get_theme()
        
        # Initialize health checkers
        self.agent_monitor = get_agent_monitor()
        self.api_checker = get_api_checker()
        self.db_checker = get_db_checker()
        self.performance_monitor = get_performance_monitor()
        self.trading_checker = get_trading_checker()
        self.deps_checker = get_deps_checker()
        self.security_checker = get_security_checker()
        self.data_quality_checker = get_data_quality_checker()
        self.integration_checker = get_integration_checker()
        self.logic_checker = get_logic_checker()
        
        # Health check categories
        self.health_categories = [
            ('Environment Variables', self._check_environment_variables),
            ('Configuration', self._check_configuration),
            ('Database Health', self._check_database_health),
            ('RPC Connectivity', self._check_rpc_connectivity),
            ('Wallet Balance', self._check_wallet_balance),
            ('Webhook Status', self._check_webhook_status),
            ('Agent Health', self._check_agent_health),
            ('API Service Health', self._check_api_health),
            ('Performance Metrics', self._check_performance_metrics),
            ('Trading System Health', self._check_trading_health),
            ('External Dependencies', self._check_external_dependencies),
            ('Security & Safety', self._check_security_safety),
            ('Data Quality', self._check_data_quality),
            ('System Integration', self._check_system_integration),
            ('Business Logic Health', self._check_business_logic)
        ]
    
    def _check_environment_variables(self) -> Dict[str, Any]:
        """Check environment variables"""
        required_vars = [
            'DEFAULT_WALLET_ADDRESS',
            'HELIUS_API_KEY',
            'RPC_ENDPOINT'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        status = 'healthy' if not missing_vars else 'critical'
        return {
            'status': status,
            'missing_vars': missing_vars,
            'total_required': len(required_vars),
            'configured': len(required_vars) - len(missing_vars)
        }
    
    def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration settings"""
        try:
            from src.config import (
                PAPER_TRADING_ENABLED,
                WEBHOOK_MODE,
                RPC_ENDPOINT,
                PRIMARY_RPC_ENDPOINT
            )
            
            issues = []
            if not PAPER_TRADING_ENABLED:
                issues.append("Paper trading disabled")
            if not WEBHOOK_MODE:
                issues.append("Webhook mode disabled")
            
            status = 'healthy' if not issues else 'warning'
            return {
                'status': status,
                'paper_trading': PAPER_TRADING_ENABLED,
                'webhook_mode': WEBHOOK_MODE,
                'rpc_configured': bool(RPC_ENDPOINT),
                'primary_rpc_configured': bool(PRIMARY_RPC_ENDPOINT),
                'issues': issues
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e),
                'issues': ['Configuration import failed']
            }
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            summary = self.db_checker.get_database_health_summary()
            status = 'healthy' if summary['health_percentage'] > 80 else 'warning' if summary['health_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_rpc_connectivity(self) -> Dict[str, Any]:
        """Check RPC connectivity"""
        try:
            rpc_status = self.deps_checker.check_helius_rpc()
            return {
                'status': rpc_status.status,
                'response_time_ms': rpc_status.response_time_ms,
                'error_message': rpc_status.error_message
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_wallet_balance(self) -> Dict[str, Any]:
        """Check wallet balance access"""
        try:
            from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
            
            coordinator = get_shared_data_coordinator()
            wallet_data = coordinator.get_personal_wallet_data()
            
            if wallet_data:
                return {
                    'status': 'healthy',
                    'total_value_usd': wallet_data.total_value_usd,
                    'token_count': len(wallet_data.tokens)
                }
            else:
                return {
                    'status': 'critical',
                    'error': 'Could not fetch wallet data'
                }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_webhook_status(self) -> Dict[str, Any]:
        """Check webhook status"""
        try:
            webhook_status = self.integration_checker.check_helius_webhook()
            return {
                'status': webhook_status.status,
                'response_time_ms': webhook_status.response_time_ms,
                'webhook_count': webhook_status.performance_metrics.get('webhook_count', 0),
                'error_message': webhook_status.error_message
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_agent_health(self) -> Dict[str, Any]:
        """Check agent health"""
        try:
            summary = self.agent_monitor.get_agent_health_summary()
            status = 'healthy' if summary['health_percentage'] > 80 else 'warning' if summary['health_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_api_health(self) -> Dict[str, Any]:
        """Check API service health"""
        try:
            summary = self.api_checker.get_api_health_summary()
            status = 'healthy' if summary['health_percentage'] > 80 else 'warning' if summary['health_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_performance_metrics(self) -> Dict[str, Any]:
        """Check performance metrics"""
        try:
            summary = self.performance_monitor.get_performance_summary()
            current = summary['current']
            
            # Determine status based on performance
            if current['cpu_percent'] > 90 or current['memory_percent'] > 95:
                status = 'critical'
            elif current['cpu_percent'] > 70 or current['memory_percent'] > 80:
                status = 'warning'
            else:
                status = 'healthy'
            
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_trading_health(self) -> Dict[str, Any]:
        """Check trading system health"""
        try:
            summary = self.trading_checker.get_trading_health_summary()
            status = 'healthy' if summary['health_percentage'] > 80 else 'warning' if summary['health_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_external_dependencies(self) -> Dict[str, Any]:
        """Check external dependencies"""
        try:
            summary = self.deps_checker.get_dependencies_health_summary()
            status = 'healthy' if summary['health_percentage'] > 80 else 'warning' if summary['health_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_security_safety(self) -> Dict[str, Any]:
        """Check security and safety"""
        try:
            summary = self.security_checker.get_security_summary()
            status = 'healthy' if summary['security_percentage'] > 80 else 'warning' if summary['security_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_data_quality(self) -> Dict[str, Any]:
        """Check data quality"""
        try:
            summary = self.data_quality_checker.get_data_quality_summary()
            status = 'healthy' if summary['quality_percentage'] > 80 else 'warning' if summary['quality_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_system_integration(self) -> Dict[str, Any]:
        """Check system integration"""
        try:
            summary = self.integration_checker.get_integration_summary()
            status = 'healthy' if summary['integration_percentage'] > 80 else 'warning' if summary['integration_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_business_logic(self) -> Dict[str, Any]:
        """Check business logic health"""
        try:
            summary = self.logic_checker.get_logic_health_summary()
            status = 'healthy' if summary['logic_health_percentage'] > 80 else 'warning' if summary['logic_health_percentage'] > 50 else 'critical'
            return {
                'status': status,
                'summary': summary
            }
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        self.theme.clear_screen()
        print_banner("ANARCHO CAPITAL HEALTH MONITOR")
        
        print_header("🧠 Neural Network Health Analysis", "Comprehensive system diagnostics in progress...")
        
        results = {}
        total_checks = len(self.health_categories)
        
        for i, (category_name, check_func) in enumerate(self.health_categories):
            print(f"\n{self.theme._get_status_icon('checking')} Checking {category_name}...")
            
            try:
                result = check_func()
                results[category_name] = result
                
                status_icon = self.theme._get_status_icon(result['status'])
                print(f"  {status_icon} {category_name}: {result['status'].upper()}")
                
                if self.verbose and 'summary' in result:
                    summary = result['summary']
                    if isinstance(summary, dict):
                        for key, value in summary.items():
                            if isinstance(value, (int, float)):
                                print_metric(key.replace('_', ' ').title(), str(value))
                
            except Exception as e:
                results[category_name] = {
                    'status': 'critical',
                    'error': str(e)
                }
                print(f"  ❌ {category_name}: CRITICAL - {str(e)}")
            
            # Show progress
            self.theme.print_progress_bar(i + 1, total_checks, "Health Check Progress")
        
        return results
    
    def get_health_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Get overall health summary"""
        total_checks = len(results)
        healthy_checks = sum(1 for result in results.values() if result['status'] == 'healthy')
        warning_checks = sum(1 for result in results.values() if result['status'] == 'warning')
        critical_checks = sum(1 for result in results.values() if result['status'] == 'critical')
        
        return {
            'total': total_checks,
            'passed': healthy_checks,
            'warnings': warning_checks,
            'critical': critical_checks,
            'health_percentage': (healthy_checks / total_checks * 100) if total_checks > 0 else 0
        }
    
    def display_results(self, results: Dict[str, Any]):
        """Display health check results with theme"""
        print_header("📊 Neural Network Analysis Complete", "System health assessment finished")
        
        # Display summary
        summary = self.get_health_summary(results)
        print_summary_stats(summary)
        
        # Display detailed results
        if self.verbose:
            print_header("🔍 Detailed Analysis", "Comprehensive system metrics")
            
            for category_name, result in results.items():
                status_icon = self.theme._get_status_icon(result['status'])
                print(f"\n{status_icon} {category_name}")
                
                if 'error' in result:
                    print(f"  Error: {result['error']}")
                elif 'summary' in result:
                    summary = result['summary']
                    if isinstance(summary, dict):
                        for key, value in summary.items():
                            if isinstance(value, (int, float, str)):
                                print_metric(key.replace('_', ' ').title(), str(value))
        
        # Display recommendations
        print_header("💡 Neural Network Recommendations", "System optimization suggestions")
        
        recommendations = []
        
        # Collect recommendations from all checkers
        try:
            recommendations.extend(self.agent_monitor.get_agent_health_summary().get('recommendations', []))
            recommendations.extend(self.api_checker.get_api_health_summary().get('recommendations', []))
            recommendations.extend(self.db_checker.get_database_recommendations())
            recommendations.extend(self.trading_checker.get_trading_recommendations())
            recommendations.extend(self.deps_checker.get_dependencies_recommendations())
            recommendations.extend(self.security_checker.get_security_recommendations())
            recommendations.extend(self.data_quality_checker.get_data_quality_recommendations())
            recommendations.extend(self.integration_checker.get_integration_recommendations())
            recommendations.extend(self.logic_checker.get_logic_recommendations())
        except Exception as e:
            recommendations.append(f"Error collecting recommendations: {str(e)}")
        
        # Remove duplicates and display
        unique_recommendations = list(set(recommendations))
        for i, rec in enumerate(unique_recommendations[:10], 1):  # Show top 10
            print(f"  {i}. {rec}")
        
        if len(unique_recommendations) > 10:
            print(f"  ... and {len(unique_recommendations) - 10} more recommendations")
        
        # Final status
        print_header("🎯 System Status", "Neural network analysis complete")
        
        if summary['health_percentage'] >= 90:
            print_status("excellent", "System operating at optimal performance", "All neural pathways functioning")
        elif summary['health_percentage'] >= 70:
            print_status("good", "System operating normally", "Minor optimizations available")
        elif summary['health_percentage'] >= 50:
            print_status("warning", "System performance degraded", "Attention required")
        else:
            print_status("critical", "System requires immediate attention", "Critical issues detected")
        
        self.theme.print_footer("Press 'q' to quit, 'v' for verbose, 'r' to refresh")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Enhanced System Health Check')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-l', '--live', action='store_true', help='Live monitoring mode')
    parser.add_argument('--summary', action='store_true', help='Quick summary only')
    
    args = parser.parse_args()
    
    # Create health check instance
    health_check = EnhancedSystemHealthCheck(verbose=args.verbose, live_mode=args.live)
    
    if args.live:
        # Live monitoring mode
        print("🔄 Starting live monitoring mode...")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                results = health_check.run_health_check()
                health_check.display_results(results)
                time.sleep(30)  # Refresh every 30 seconds
        except KeyboardInterrupt:
            print("\n🛑 Live monitoring stopped")
    else:
        # Single health check
        results = health_check.run_health_check()
        health_check.display_results(results)

if __name__ == "__main__":
    main()
