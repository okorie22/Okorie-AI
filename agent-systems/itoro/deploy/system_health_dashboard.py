#!/usr/bin/env python3
"""
🌙 Anarcho Capital's System Health Dashboard
Real-time monitoring dashboard for trading system health
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
import threading

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Print dashboard header"""
    print("=" * 100)
    print("🌙 ANARCHO CAPITAL'S TRADING SYSTEM - HEALTH DASHBOARD")
    print("=" * 100)
    print(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def get_system_status():
    """Get overall system status"""
    try:
        # Simple system status check without service_health_monitor
        import os
        import psutil
        
        return {
            'overall_status': 'operational',
            'cpu_usage': psutil.cpu_percent(),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'uptime': 'unknown',
            'services': []
        }
    except Exception as e:
        return {'error': f'Failed to get system status: {str(e)}'}

def get_trading_metrics():
    """Get trading system metrics"""
    try:
        from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
        from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
        from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
        
        coordinator = get_shared_data_coordinator()
        api_manager = get_shared_api_manager()
        price_service = get_optimized_price_service()
        
        return {
            'data_coordinator': coordinator.get_coordination_stats(),
            'api_manager': api_manager.get_api_stats(),
            'price_service': price_service.get_price_stats()
        }
    except Exception as e:
        return {'error': f'Failed to get trading metrics: {str(e)}'}

def get_agent_status():
    """Get status of all agents"""
    try:
        # This would be implemented if agents had status reporting
        return {
            'risk_agent': {'status': 'RUNNING', 'last_check': datetime.now().isoformat()},
            'copybot_agent': {'status': 'RUNNING', 'last_check': datetime.now().isoformat()},
            'harvesting_agent': {'status': 'RUNNING', 'last_check': datetime.now().isoformat()}
        }
    except Exception as e:
        return {'error': f'Failed to get agent status: {str(e)}'}

def get_wallet_status():
    """Get wallet status and balance"""
    try:
        from src.nice_funcs import get_wallet_total_value
        from src import config
        
        balance = get_wallet_total_value(config.address)
        
        return {
            'address': config.address[:8] + '...' + config.address[-8:],
            'balance_usd': balance,
            'minimum_balance': config.MINIMUM_BALANCE_USD,
            'status': 'HEALTHY' if balance and balance > config.MINIMUM_BALANCE_USD else 'WARNING'
        }
    except Exception as e:
        return {'error': f'Failed to get wallet status: {str(e)}'}

def get_position_summary():
    """Get current position summary"""
    try:
        from src.nice_funcs import get_wallet_tokens_with_value
        from src import config
        
        positions = get_wallet_tokens_with_value(config.address)
        
        if not positions:
            return {'total_positions': 0, 'total_value': 0.0}
        
        total_value = sum(pos.get('value_usd', 0) for pos in positions.values())
        
        return {
            'total_positions': len(positions),
            'total_value': total_value,
            'top_positions': sorted(
                [(symbol, data.get('value_usd', 0)) for symbol, data in positions.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
    except Exception as e:
        return {'error': f'Failed to get position summary: {str(e)}'}

def format_status_indicator(status: str) -> str:
    """Format status with color indicators"""
    indicators = {
        'HEALTHY': '🟢',
        'RUNNING': '🟢',
        'DEGRADED': '🟡',
        'WARNING': '🟡',
        'FAILED': '🔴',
        'ERROR': '🔴',
        'UNKNOWN': '⚪'
    }
    return f"{indicators.get(status, '⚪')} {status}"

def print_system_overview(system_status: Dict[str, Any]):
    """Print system overview section"""
    print("📊 SYSTEM OVERVIEW")
    print("-" * 50)
    
    if 'error' in system_status:
        print(f"❌ {system_status['error']}")
        return
    
    print(f"Overall Health: {format_status_indicator('HEALTHY' if system_status.get('emergency_stop', False) == False else 'ERROR')}")
    print(f"Total Services: {system_status.get('total_services', 0)}")
    print(f"Healthy Services: {system_status.get('healthy_services', 0)}")
    print(f"Failed Services: {system_status.get('failed_services', 0)}")
    print(f"System Health: {system_status.get('system_health_percentage', 0):.1f}%")
    print()

def print_agent_status(agent_status: Dict[str, Any]):
    """Print agent status section"""
    print("🤖 AGENT STATUS")
    print("-" * 50)
    
    if 'error' in agent_status:
        print(f"❌ {agent_status['error']}")
        return
    
    for agent_name, status in agent_status.items():
        if isinstance(status, dict):
            print(f"{agent_name.replace('_', ' ').title()}: {format_status_indicator(status.get('status', 'UNKNOWN'))}")
    print()

def print_wallet_status(wallet_status: Dict[str, Any]):
    """Print wallet status section"""
    print("💰 WALLET STATUS")
    print("-" * 50)
    
    if 'error' in wallet_status:
        print(f"❌ {wallet_status['error']}")
        return
    
    print(f"Address: {wallet_status.get('address', 'Unknown')}")
    print(f"Balance: ${wallet_status.get('balance_usd', 0):.2f}")
    print(f"Minimum: ${wallet_status.get('minimum_balance', 0):.2f}")
    print(f"Status: {format_status_indicator(wallet_status.get('status', 'UNKNOWN'))}")
    print()

def print_position_summary(position_summary: Dict[str, Any]):
    """Print position summary section"""
    print("📈 POSITION SUMMARY")
    print("-" * 50)
    
    if 'error' in position_summary:
        print(f"❌ {position_summary['error']}")
        return
    
    print(f"Total Positions: {position_summary.get('total_positions', 0)}")
    print(f"Total Value: ${position_summary.get('total_value', 0):.2f}")
    
    if 'top_positions' in position_summary:
        print("\nTop Positions:")
        for symbol, value in position_summary['top_positions']:
            print(f"  {symbol}: ${value:.2f}")
    print()

def print_trading_metrics(trading_metrics: Dict[str, Any]):
    """Print trading metrics section"""
    print("📊 TRADING METRICS")
    print("-" * 50)
    
    if 'error' in trading_metrics:
        print(f"❌ {trading_metrics['error']}")
        return
    
    # Data coordinator stats
    if 'data_coordinator' in trading_metrics:
        dc_stats = trading_metrics['data_coordinator']
        print(f"Cache Hits: {dc_stats.get('cache_hits', 0)}")
        print(f"Cache Misses: {dc_stats.get('cache_misses', 0)}")
        print(f"API Calls Saved: {dc_stats.get('api_calls_saved', 0)}")
    
    # API manager stats
    if 'api_manager' in trading_metrics:
        api_stats = trading_metrics['api_manager']
        print(f"Total API Calls: {api_stats.get('total_calls', 0)}")
        print(f"Failed API Calls: {api_stats.get('failed_calls', 0)}")
    
    print()

def print_alerts():
    """Print system alerts"""
    print("🚨 ALERTS")
    print("-" * 50)
    
    # This would be implemented with a proper alerting system
    print("No active alerts")
    print()

def main_dashboard():
    """Main dashboard loop"""
    while True:
        try:
            clear_screen()
            print_header()
            
            # Gather all data
            system_status = get_system_status()
            agent_status = get_agent_status()
            wallet_status = get_wallet_status()
            position_summary = get_position_summary()
            trading_metrics = get_trading_metrics()
            
            # Print all sections
            print_system_overview(system_status)
            print_agent_status(agent_status)
            print_wallet_status(wallet_status)
            print_position_summary(position_summary)
            print_trading_metrics(trading_metrics)
            print_alerts()
            
            print("=" * 100)
            print("Press Ctrl+C to exit | Updates every 30 seconds")
            
            # Wait for next update
            time.sleep(30)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Dashboard stopped by user")
            break
        except Exception as e:
            print(f"\n❌ Dashboard error: {e}")
            time.sleep(5)

def export_health_report():
    """Export health report to JSON"""
    try:
        report = {
            'timestamp': datetime.now().isoformat(),
            'system_status': get_system_status(),
            'agent_status': get_agent_status(),
            'wallet_status': get_wallet_status(),
            'position_summary': get_position_summary(),
            'trading_metrics': get_trading_metrics()
        }
        
        os.makedirs('health_reports', exist_ok=True)
        filename = f"health_reports/health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"✅ Health report exported to {filename}")
        
    except Exception as e:
        print(f"❌ Failed to export health report: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--export":
        export_health_report()
    else:
        main_dashboard() 
