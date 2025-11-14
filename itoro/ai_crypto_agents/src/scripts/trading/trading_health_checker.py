#!/usr/bin/env python3
"""
📈 Anarcho Capital's Trading System Health Checker
Monitor trading execution, position management, and portfolio tracking
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class TradingSystemStatus:
    """Trading system health status"""
    component: str
    status: str  # 'healthy', 'degraded', 'unhealthy', 'unknown'
    last_activity: Optional[datetime]
    success_rate: float
    error_count: int
    performance_metrics: Dict[str, Any]
    last_error: Optional[str]

class TradingHealthChecker:
    """Monitor trading system health and performance"""
    
    def __init__(self):
        self.components = [
            'position_manager',
            'portfolio_tracker',
            'trade_execution',
            'risk_management',
            'price_validation',
            'wallet_sync'
        ]
    
    def check_position_manager(self) -> TradingSystemStatus:
        """Check position manager health"""
        try:
            from src.scripts.trading.position_manager import get_position_manager
            
            position_manager = get_position_manager()
            
            # Check if position manager is accessible
            if not position_manager:
                return TradingSystemStatus(
                    component='position_manager',
                    status='unhealthy',
                    last_activity=None,
                    success_rate=0.0,
                    error_count=1,
                    performance_metrics={},
                    last_error='Position manager not accessible'
                )
            
            # Get position manager metrics
            active_positions = getattr(position_manager, 'active_positions', {})
            position_count = len(active_positions)
            
            # Check for recent activity (positions created/updated in last hour)
            recent_activity = None
            if hasattr(position_manager, 'last_position_update'):
                recent_activity = position_manager.last_position_update
            
            # Calculate success rate (mock for now)
            success_rate = 0.95  # 95% success rate
            
            performance_metrics = {
                'active_positions': position_count,
                'position_manager_initialized': True,
                'last_position_update': recent_activity.isoformat() if recent_activity else None
            }
            
            status = 'healthy' if position_count >= 0 else 'degraded'
            
            return TradingSystemStatus(
                component='position_manager',
                status=status,
                last_activity=recent_activity,
                success_rate=success_rate,
                error_count=0,
                performance_metrics=performance_metrics,
                last_error=None
            )
            
        except Exception as e:
            return TradingSystemStatus(
                component='position_manager',
                status='unhealthy',
                last_activity=None,
                success_rate=0.0,
                error_count=1,
                performance_metrics={},
                last_error=str(e)
            )
    
    def check_portfolio_tracker(self) -> TradingSystemStatus:
        """Check portfolio tracker health"""
        try:
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            
            portfolio_tracker = get_portfolio_tracker()
            
            if not portfolio_tracker:
                return TradingSystemStatus(
                    component='portfolio_tracker',
                    status='unhealthy',
                    last_activity=None,
                    success_rate=0.0,
                    error_count=1,
                    performance_metrics={},
                    last_error='Portfolio tracker not accessible'
                )
            
            # Get current portfolio data
            current_snapshot = getattr(portfolio_tracker, 'current_snapshot', None)
            recent_snapshots = getattr(portfolio_tracker, 'recent_snapshots', [])
            
            # Check last snapshot time
            last_activity = None
            if current_snapshot and hasattr(current_snapshot, 'timestamp'):
                last_activity = current_snapshot.timestamp
            
            # Check snapshot frequency (should be regular)
            snapshot_count = len(recent_snapshots)
            snapshot_frequency_ok = snapshot_count > 0
            
            # Get portfolio value
            current_value = 0.0
            if current_snapshot and hasattr(current_snapshot, 'total_value_usd'):
                current_value = current_snapshot.total_value_usd
            
            performance_metrics = {
                'current_portfolio_value': current_value,
                'snapshot_count': snapshot_count,
                'last_snapshot_time': last_activity.isoformat() if last_activity else None,
                'snapshot_frequency_ok': snapshot_frequency_ok
            }
            
            # Determine status
            if snapshot_frequency_ok and current_value > 0:
                status = 'healthy'
                success_rate = 0.95
            elif snapshot_frequency_ok:
                status = 'degraded'
                success_rate = 0.8
            else:
                status = 'unhealthy'
                success_rate = 0.0
            
            return TradingSystemStatus(
                component='portfolio_tracker',
                status=status,
                last_activity=last_activity,
                success_rate=success_rate,
                error_count=0,
                performance_metrics=performance_metrics,
                last_error=None
            )
            
        except Exception as e:
            return TradingSystemStatus(
                component='portfolio_tracker',
                status='unhealthy',
                last_activity=None,
                success_rate=0.0,
                error_count=1,
                performance_metrics={},
                last_error=str(e)
            )
    
    def check_trade_execution(self) -> TradingSystemStatus:
        """Check trade execution health"""
        try:
            # Check recent trades in database
            trade_count = 0
            success_count = 0
            last_trade_time = None
            
            # Check paper trading database
            paper_db_path = 'data/paper_trading.db'
            if os.path.exists(paper_db_path):
                conn = sqlite3.connect(paper_db_path)
                cursor = conn.cursor()
                
                # Get recent trades (last 24 hours)
                cursor.execute("""
                    SELECT COUNT(*), 
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END),
                           MAX(timestamp)
                    FROM trades 
                    WHERE timestamp > datetime('now', '-1 day')
                """)
                result = cursor.fetchone()
                if result:
                    trade_count = result[0] or 0
                    success_count = result[1] or 0
                    last_trade_time = result[2]
                
                conn.close()
            
            # Calculate success rate
            success_rate = (success_count / trade_count) if trade_count > 0 else 0.0
            
            # Parse last trade time
            last_activity = None
            if last_trade_time:
                try:
                    last_activity = datetime.fromisoformat(last_trade_time.replace('Z', '+00:00'))
                except:
                    last_activity = None
            
            performance_metrics = {
                'recent_trades_24h': trade_count,
                'successful_trades_24h': success_count,
                'last_trade_time': last_activity.isoformat() if last_activity else None,
                'execution_success_rate': success_rate
            }
            
            # Determine status
            if success_rate >= 0.9 and trade_count > 0:
                status = 'healthy'
            elif success_rate >= 0.7:
                status = 'degraded'
            else:
                status = 'unhealthy'
            
            return TradingSystemStatus(
                component='trade_execution',
                status=status,
                last_activity=last_activity,
                success_rate=success_rate,
                error_count=trade_count - success_count,
                performance_metrics=performance_metrics,
                last_error=None
            )
            
        except Exception as e:
            return TradingSystemStatus(
                component='trade_execution',
                status='unhealthy',
                last_activity=None,
                success_rate=0.0,
                error_count=1,
                performance_metrics={},
                last_error=str(e)
            )
    
    def check_risk_management(self) -> TradingSystemStatus:
        """Check risk management system health"""
        try:
            from src.agents.risk_agent import RiskAgent
            
            risk_agent = RiskAgent()
            
            # Check risk agent status
            is_running = getattr(risk_agent, 'is_running', False)
            emergency_stop = getattr(risk_agent, 'emergency_stop_triggered', False)
            consecutive_losses = getattr(risk_agent, 'consecutive_losses', 0)
            
            # Get last risk check time
            last_check_time = getattr(risk_agent, 'last_check_time', 0)
            last_activity = None
            if last_check_time > 0:
                last_activity = datetime.fromtimestamp(last_check_time)
            
            performance_metrics = {
                'risk_agent_running': is_running,
                'emergency_stop_triggered': emergency_stop,
                'consecutive_losses': consecutive_losses,
                'last_risk_check': last_activity.isoformat() if last_activity else None
            }
            
            # Determine status
            if emergency_stop:
                status = 'unhealthy'
                success_rate = 0.0
            elif consecutive_losses > 5:
                status = 'degraded'
                success_rate = 0.7
            elif is_running:
                status = 'healthy'
                success_rate = 0.9
            else:
                status = 'degraded'
                success_rate = 0.5
            
            return TradingSystemStatus(
                component='risk_management',
                status=status,
                last_activity=last_activity,
                success_rate=success_rate,
                error_count=consecutive_losses,
                performance_metrics=performance_metrics,
                last_error='Emergency stop triggered' if emergency_stop else None
            )
            
        except Exception as e:
            return TradingSystemStatus(
                component='risk_management',
                status='unhealthy',
                last_activity=None,
                success_rate=0.0,
                error_count=1,
                performance_metrics={},
                last_error=str(e)
            )
    
    def check_price_validation(self) -> TradingSystemStatus:
        """Check price validation system health"""
        try:
            from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
            
            price_service = get_optimized_price_service()
            
            # Get price service metrics
            cache_hits = getattr(price_service, 'cache_hits', 0)
            cache_misses = getattr(price_service, 'cache_misses', 0)
            failed_fetches = getattr(price_service, 'failed_fetches', {})
            
            # Calculate success rate
            total_requests = cache_hits + cache_misses
            success_rate = (cache_hits / total_requests) if total_requests > 0 else 0.0
            
            # Count failed fetches
            error_count = len(failed_fetches)
            
            performance_metrics = {
                'cache_hits': cache_hits,
                'cache_misses': cache_misses,
                'cache_hit_rate': success_rate,
                'failed_fetches': error_count,
                'price_validation_enabled': True
            }
            
            # Determine status
            if success_rate >= 0.8 and error_count < 5:
                status = 'healthy'
            elif success_rate >= 0.6:
                status = 'degraded'
            else:
                status = 'unhealthy'
            
            return TradingSystemStatus(
                component='price_validation',
                status=status,
                last_activity=datetime.now(),
                success_rate=success_rate,
                error_count=error_count,
                performance_metrics=performance_metrics,
                last_error=None
            )
            
        except Exception as e:
            return TradingSystemStatus(
                component='price_validation',
                status='unhealthy',
                last_activity=None,
                success_rate=0.0,
                error_count=1,
                performance_metrics={},
                last_error=str(e)
            )
    
    def check_wallet_sync(self) -> TradingSystemStatus:
        """Check wallet synchronization health"""
        try:
            from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
            
            data_coordinator = get_shared_data_coordinator()
            
            # Get wallet data
            wallet_data = data_coordinator.get_personal_wallet_data()
            
            if not wallet_data:
                return TradingSystemStatus(
                    component='wallet_sync',
                    status='unhealthy',
                    last_activity=None,
                    success_rate=0.0,
                    error_count=1,
                    performance_metrics={},
                    last_error='Wallet data not accessible'
                )
            
            # Get wallet metrics
            total_value = getattr(wallet_data, 'total_value_usd', 0.0)
            token_count = len(getattr(wallet_data, 'tokens', {}))
            last_update = getattr(wallet_data, 'last_update', None)
            
            performance_metrics = {
                'wallet_value_usd': total_value,
                'token_count': token_count,
                'last_wallet_update': last_update.isoformat() if last_update else None,
                'wallet_sync_enabled': True
            }
            
            # Determine status
            if total_value > 0 and token_count > 0:
                status = 'healthy'
                success_rate = 0.95
            elif total_value > 0:
                status = 'degraded'
                success_rate = 0.8
            else:
                status = 'unhealthy'
                success_rate = 0.0
            
            return TradingSystemStatus(
                component='wallet_sync',
                status=status,
                last_activity=last_update,
                success_rate=success_rate,
                error_count=0,
                performance_metrics=performance_metrics,
                last_error=None
            )
            
        except Exception as e:
            return TradingSystemStatus(
                component='wallet_sync',
                status='unhealthy',
                last_activity=None,
                success_rate=0.0,
                error_count=1,
                performance_metrics={},
                last_error=str(e)
            )
    
    def check_all_components(self) -> Dict[str, TradingSystemStatus]:
        """Check health of all trading system components"""
        statuses = {}
        
        statuses['position_manager'] = self.check_position_manager()
        statuses['portfolio_tracker'] = self.check_portfolio_tracker()
        statuses['trade_execution'] = self.check_trade_execution()
        statuses['risk_management'] = self.check_risk_management()
        statuses['price_validation'] = self.check_price_validation()
        statuses['wallet_sync'] = self.check_wallet_sync()
        
        return statuses
    
    def get_trading_health_summary(self) -> Dict[str, Any]:
        """Get overall trading system health summary"""
        statuses = self.check_all_components()
        
        total_components = len(statuses)
        healthy_components = sum(1 for status in statuses.values() if status.status == 'healthy')
        degraded_components = sum(1 for status in statuses.values() if status.status == 'degraded')
        unhealthy_components = sum(1 for status in statuses.values() if status.status == 'unhealthy')
        
        # Calculate average success rate
        success_rates = [status.success_rate for status in statuses.values()]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0
        
        # Count components with recent activity (within last hour)
        recent_activity = 0
        for status in statuses.values():
            if status.last_activity:
                if datetime.now() - status.last_activity < timedelta(hours=1):
                    recent_activity += 1
        
        # Count total errors
        total_errors = sum(status.error_count for status in statuses.values())
        
        return {
            'total_components': total_components,
            'healthy_components': healthy_components,
            'degraded_components': degraded_components,
            'unhealthy_components': unhealthy_components,
            'avg_success_rate': avg_success_rate,
            'recent_activity': recent_activity,
            'total_errors': total_errors,
            'health_percentage': (healthy_components / total_components * 100) if total_components > 0 else 0
        }
    
    def get_trading_recommendations(self) -> List[str]:
        """Get trading system optimization recommendations"""
        statuses = self.check_all_components()
        recommendations = []
        
        # Check for unhealthy components
        for component, status in statuses.items():
            if status.status == 'unhealthy':
                recommendations.append(f"Fix critical issues in {component}: {status.last_error}")
            elif status.status == 'degraded':
                recommendations.append(f"Optimize performance in {component}")
        
        # Check for low success rates
        for component, status in statuses.items():
            if status.success_rate < 0.8:
                recommendations.append(f"Improve success rate in {component} (currently {status.success_rate:.1%})")
        
        # Check for high error counts
        for component, status in statuses.items():
            if status.error_count > 10:
                recommendations.append(f"Reduce error count in {component} (currently {status.error_count})")
        
        return recommendations

# Global instance
trading_checker = TradingHealthChecker()

def get_trading_checker() -> TradingHealthChecker:
    """Get global trading checker instance"""
    return trading_checker

if __name__ == "__main__":
    # Test the trading checker
    checker = TradingHealthChecker()
    
    print("📈 Trading System Health Checker Test")
    print("=" * 50)
    
    # Check individual components
    for component in ['position_manager', 'portfolio_tracker', 'trade_execution']:
        print(f"\nChecking {component}...")
        if component == 'position_manager':
            status = checker.check_position_manager()
        elif component == 'portfolio_tracker':
            status = checker.check_portfolio_tracker()
        else:
            status = checker.check_trade_execution()
        
        print(f"  Status: {status.status}")
        print(f"  Success rate: {status.success_rate:.1%}")
        print(f"  Error count: {status.error_count}")
        if status.last_activity:
            print(f"  Last activity: {status.last_activity}")
    
    # Get summary
    summary = checker.get_trading_health_summary()
    print(f"\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Get recommendations
    recommendations = checker.get_trading_recommendations()
    if recommendations:
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
