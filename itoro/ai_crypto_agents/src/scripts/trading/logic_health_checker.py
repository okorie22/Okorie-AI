#!/usr/bin/env python3
"""
🧠 Anarcho Capital's Business Logic Health Checker
Validate trading rules, risk thresholds, and portfolio allocation logic
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class LogicHealthStatus:
    """Business logic health status"""
    component: str
    status: str  # 'valid', 'warning', 'invalid', 'unknown'
    last_check: datetime
    issues: List[str]
    recommendations: List[str]
    performance_metrics: Dict[str, Any]

class LogicHealthChecker:
    """Monitor business logic health and validation"""
    
    def __init__(self):
        self.logic_components = [
            'trading_rules',
            'risk_thresholds',
            'portfolio_allocation',
            'position_sizing',
            'dca_logic',
            'staking_logic'
        ]
    
    def check_trading_rules(self) -> LogicHealthStatus:
        """Check trading rules logic"""
        issues = []
        recommendations = []
        
        try:
            from src import config
            
            # Check trading mode consistency
            paper_trading = getattr(config, 'PAPER_TRADING_ENABLED', True)
            live_trading = not paper_trading
            
            if live_trading and not getattr(config, 'ENABLE_TRADE_VALIDATION', True):
                issues.append("Live trading enabled but trade validation is disabled")
            
            # Check trading intervals
            copybot_interval = getattr(config, 'COPYBOT_CHECK_INTERVAL_MINUTES', 8)
            if copybot_interval < 1:
                issues.append("CopyBot check interval too frequent (less than 1 minute)")
            elif copybot_interval > 60:
                issues.append("CopyBot check interval too slow (more than 60 minutes)")
            
            # Check trading hours
            trading_hours = getattr(config, 'TRADING_HOURS', {})
            if trading_hours and not trading_hours.get('ENABLED', False):
                recommendations.append("Consider enabling trading hours restrictions")
            
            # Check mirror trading settings
            mirror_enabled = getattr(config, 'MIRROR_ENABLED', True)
            if not mirror_enabled:
                recommendations.append("Mirror trading is disabled - consider enabling for better performance")
            
            # Check AI analysis settings
            ai_analysis = getattr(config, 'AI_ANALYSIS_ENABLED', True)
            if not ai_analysis:
                recommendations.append("AI analysis is disabled - consider enabling for better decision making")
            
            performance_metrics = {
                'paper_trading_enabled': paper_trading,
                'trade_validation_enabled': getattr(config, 'ENABLE_TRADE_VALIDATION', True),
                'copybot_interval_minutes': copybot_interval,
                'mirror_enabled': mirror_enabled,
                'ai_analysis_enabled': ai_analysis,
                'trading_hours_enabled': trading_hours.get('ENABLED', False)
            }
            
            status = 'valid' if not issues else 'warning'
            
        except Exception as e:
            issues.append(f"Error checking trading rules: {str(e)}")
            status = 'invalid'
            performance_metrics = {}
        
        return LogicHealthStatus(
            component='trading_rules',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_risk_thresholds(self) -> LogicHealthStatus:
        """Check risk management thresholds"""
        issues = []
        recommendations = []
        
        try:
            from src import config
            
            # Check drawdown limits
            drawdown_limit = getattr(config, 'DRAWDOWN_LIMIT_PERCENT', -30)
            if drawdown_limit > -10:
                issues.append(f"Drawdown limit too restrictive: {drawdown_limit}% (recommended -20% to -30%)")
            elif drawdown_limit < -50:
                issues.append(f"Drawdown limit too permissive: {drawdown_limit}% (recommended -20% to -30%)")
            
            # Check consecutive loss limits
            consecutive_loss_limit = getattr(config, 'CONSECUTIVE_LOSS_LIMIT', 6)
            if consecutive_loss_limit > 10:
                issues.append(f"Consecutive loss limit too high: {consecutive_loss_limit} (recommended < 10)")
            elif consecutive_loss_limit < 3:
                issues.append(f"Consecutive loss limit too low: {consecutive_loss_limit} (recommended > 3)")
            
            # Check position size limits
            min_position = getattr(config, 'MIN_POSITION_SIZE_USD', 0.01)
            max_position = getattr(config, 'MAX_POSITION_SIZE_USD', 1000.0)
            
            if min_position < 0.01:
                issues.append(f"Minimum position size too low: ${min_position} (minimum $0.01)")
            
            if max_position > 10000:
                issues.append(f"Maximum position size too high: ${max_position} (recommended < $10,000)")
            
            # Check risk agent settings
            risk_enabled = getattr(config, 'RISK_ENABLED', True)
            if not risk_enabled:
                issues.append("Risk management agent is disabled")
            
            # Check emergency stop settings
            emergency_stop = getattr(config, 'EMERGENCY_STOP_ENABLED', True)
            if not emergency_stop:
                issues.append("Emergency stop is disabled")
            
            performance_metrics = {
                'drawdown_limit_percent': drawdown_limit,
                'consecutive_loss_limit': consecutive_loss_limit,
                'min_position_usd': min_position,
                'max_position_usd': max_position,
                'risk_agent_enabled': risk_enabled,
                'emergency_stop_enabled': emergency_stop
            }
            
            status = 'valid' if not issues else 'warning'
            
        except Exception as e:
            issues.append(f"Error checking risk thresholds: {str(e)}")
            status = 'invalid'
            performance_metrics = {}
        
        return LogicHealthStatus(
            component='risk_thresholds',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_portfolio_allocation(self) -> LogicHealthStatus:
        """Check portfolio allocation logic"""
        issues = []
        recommendations = []
        
        try:
            from src import config
            
            # Check SOL target percentage
            sol_target = getattr(config, 'SOL_TARGET_PERCENT', 0.10)
            if sol_target < 0.05:
                issues.append(f"SOL target percentage too low: {sol_target:.1%} (recommended > 5%)")
            elif sol_target > 0.50:
                issues.append(f"SOL target percentage too high: {sol_target:.1%} (recommended < 50%)")
            
            # Check rebalancing settings
            rebalancing_enabled = getattr(config, 'REBALANCING_ENABLED', True)
            if not rebalancing_enabled:
                recommendations.append("Portfolio rebalancing is disabled - consider enabling")
            
            # Check harvesting settings
            harvesting_enabled = getattr(config, 'HARVESTING_ENABLED', True)
            if not harvesting_enabled:
                recommendations.append("Portfolio harvesting is disabled - consider enabling")
            
            # Check dust conversion
            dust_conversion = getattr(config, 'HARVESTING_DUST_CONVERSION_ENABLED', True)
            if not dust_conversion:
                recommendations.append("Dust conversion is disabled - consider enabling")
            
            # Check realized gains reallocation
            realized_gains = getattr(config, 'HARVESTING_REALIZED_GAINS_REALLOCATION_ENABLED', True)
            if not realized_gains:
                recommendations.append("Realized gains reallocation is disabled - consider enabling")
            
            performance_metrics = {
                'sol_target_percent': sol_target,
                'rebalancing_enabled': rebalancing_enabled,
                'harvesting_enabled': harvesting_enabled,
                'dust_conversion_enabled': dust_conversion,
                'realized_gains_enabled': realized_gains
            }
            
            status = 'valid' if not issues else 'warning'
            
        except Exception as e:
            issues.append(f"Error checking portfolio allocation: {str(e)}")
            status = 'invalid'
            performance_metrics = {}
        
        return LogicHealthStatus(
            component='portfolio_allocation',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_position_sizing(self) -> LogicHealthStatus:
        """Check position sizing logic"""
        issues = []
        recommendations = []
        
        try:
            from src import config
            
            # Check position sizing mode
            sizing_mode = getattr(config, 'POSITION_SIZING_MODE', 'dynamic')
            if sizing_mode not in ['fixed', 'dynamic', 'percentage']:
                issues.append(f"Invalid position sizing mode: {sizing_mode}")
            
            # Check fixed position size
            if sizing_mode == 'fixed':
                fixed_size = getattr(config, 'FIXED_POSITION_SIZE_USD', 100.0)
                if fixed_size < 1.0:
                    issues.append(f"Fixed position size too small: ${fixed_size} (minimum $1)")
                elif fixed_size > 5000:
                    issues.append(f"Fixed position size too large: ${fixed_size} (recommended < $5,000)")
            
            # Check percentage sizing
            elif sizing_mode == 'percentage':
                percentage = getattr(config, 'POSITION_SIZE_PERCENTAGE', 0.02)
                if percentage < 0.001:  # 0.1%
                    issues.append(f"Position size percentage too small: {percentage:.1%} (minimum 0.1%)")
                elif percentage > 0.10:  # 10%
                    issues.append(f"Position size percentage too large: {percentage:.1%} (recommended < 10%)")
            
            # Check dynamic sizing parameters
            elif sizing_mode == 'dynamic':
                volatility_factor = getattr(config, 'VOLATILITY_FACTOR', 1.0)
                if volatility_factor < 0.5:
                    issues.append(f"Volatility factor too low: {volatility_factor} (minimum 0.5)")
                elif volatility_factor > 3.0:
                    issues.append(f"Volatility factor too high: {volatility_factor} (recommended < 3.0)")
            
            # Check position limits
            max_positions = getattr(config, 'MAX_POSITIONS', 10)
            if max_positions < 1:
                issues.append(f"Maximum positions too low: {max_positions} (minimum 1)")
            elif max_positions > 50:
                issues.append(f"Maximum positions too high: {max_positions} (recommended < 50)")
            
            performance_metrics = {
                'sizing_mode': sizing_mode,
                'max_positions': max_positions,
                'volatility_factor': getattr(config, 'VOLATILITY_FACTOR', 1.0),
                'fixed_size_usd': getattr(config, 'FIXED_POSITION_SIZE_USD', 100.0),
                'percentage_size': getattr(config, 'POSITION_SIZE_PERCENTAGE', 0.02)
            }
            
            status = 'valid' if not issues else 'warning'
            
        except Exception as e:
            issues.append(f"Error checking position sizing: {str(e)}")
            status = 'invalid'
            performance_metrics = {}
        
        return LogicHealthStatus(
            component='position_sizing',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_dca_logic(self) -> LogicHealthStatus:
        """Check DCA (Dollar Cost Averaging) logic"""
        issues = []
        recommendations = []
        
        try:
            from src import config
            
            # Check DCA enabled
            dca_enabled = getattr(config, 'DCA_ENABLED', True)
            if not dca_enabled:
                recommendations.append("DCA is disabled - consider enabling for better risk management")
            
            # Check DCA interval
            dca_interval = getattr(config, 'DCA_INTERVAL_HOURS', 24)
            if dca_interval < 1:
                issues.append(f"DCA interval too frequent: {dca_interval} hours (minimum 1 hour)")
            elif dca_interval > 168:  # 1 week
                issues.append(f"DCA interval too slow: {dca_interval} hours (recommended < 168 hours)")
            
            # Check DCA amount
            dca_amount = getattr(config, 'DCA_AMOUNT_USD', 10.0)
            if dca_amount < 1.0:
                issues.append(f"DCA amount too small: ${dca_amount} (minimum $1)")
            elif dca_amount > 1000:
                issues.append(f"DCA amount too large: ${dca_amount} (recommended < $1,000)")
            
            # Check DCA tokens
            dca_tokens = getattr(config, 'DCA_TOKENS', [])
            if not dca_tokens:
                recommendations.append("No DCA tokens configured")
            elif len(dca_tokens) > 10:
                issues.append(f"Too many DCA tokens: {len(dca_tokens)} (recommended < 10)")
            
            performance_metrics = {
                'dca_enabled': dca_enabled,
                'dca_interval_hours': dca_interval,
                'dca_amount_usd': dca_amount,
                'dca_token_count': len(dca_tokens),
                'dca_tokens': dca_tokens
            }
            
            status = 'valid' if not issues else 'warning'
            
        except Exception as e:
            issues.append(f"Error checking DCA logic: {str(e)}")
            status = 'invalid'
            performance_metrics = {}
        
        return LogicHealthStatus(
            component='dca_logic',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_staking_logic(self) -> LogicHealthStatus:
        """Check staking logic and configuration"""
        issues = []
        recommendations = []
        
        try:
            from src import config
            
            # Check staking enabled
            staking_enabled = getattr(config, 'STAKING_ENABLED', True)
            if not staking_enabled:
                recommendations.append("Staking is disabled - consider enabling for passive income")
            
            # Check staking execution mode
            execution_mode = getattr(config, 'STAKING_EXECUTION_MODE', 'hybrid')
            if execution_mode not in ['webhook', 'interval', 'hybrid']:
                issues.append(f"Invalid staking execution mode: {execution_mode}")
            
            # Check staking interval
            if execution_mode in ['interval', 'hybrid']:
                staking_interval = getattr(config, 'STAKING_INTERVAL_HOURS', 24)
                if staking_interval < 1:
                    issues.append(f"Staking interval too frequent: {staking_interval} hours (minimum 1 hour)")
                elif staking_interval > 168:  # 1 week
                    issues.append(f"Staking interval too slow: {staking_interval} hours (recommended < 168 hours)")
            
            # Check staking thresholds
            min_stake_amount = getattr(config, 'MIN_STAKE_AMOUNT_SOL', 0.1)
            if min_stake_amount < 0.01:
                issues.append(f"Minimum stake amount too small: {min_stake_amount} SOL (minimum 0.01)")
            elif min_stake_amount > 10:
                issues.append(f"Minimum stake amount too large: {min_stake_amount} SOL (recommended < 10)")
            
            # Check staking protocols
            staking_protocols = getattr(config, 'STAKING_PROTOCOLS', [])
            if not staking_protocols:
                recommendations.append("No staking protocols configured")
            elif len(staking_protocols) > 5:
                issues.append(f"Too many staking protocols: {len(staking_protocols)} (recommended < 5)")
            
            performance_metrics = {
                'staking_enabled': staking_enabled,
                'execution_mode': execution_mode,
                'staking_interval_hours': getattr(config, 'STAKING_INTERVAL_HOURS', 24),
                'min_stake_amount_sol': min_stake_amount,
                'protocol_count': len(staking_protocols),
                'protocols': staking_protocols
            }
            
            status = 'valid' if not issues else 'warning'
            
        except Exception as e:
            issues.append(f"Error checking staking logic: {str(e)}")
            status = 'invalid'
            performance_metrics = {}
        
        return LogicHealthStatus(
            component='staking_logic',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_all_logic(self) -> Dict[str, LogicHealthStatus]:
        """Check all business logic components"""
        statuses = {}
        
        statuses['trading_rules'] = self.check_trading_rules()
        statuses['risk_thresholds'] = self.check_risk_thresholds()
        statuses['portfolio_allocation'] = self.check_portfolio_allocation()
        statuses['position_sizing'] = self.check_position_sizing()
        statuses['dca_logic'] = self.check_dca_logic()
        statuses['staking_logic'] = self.check_staking_logic()
        
        return statuses
    
    def get_logic_health_summary(self) -> Dict[str, Any]:
        """Get overall business logic health summary"""
        statuses = self.check_all_logic()
        
        total_components = len(statuses)
        valid_components = sum(1 for status in statuses.values() if status.status == 'valid')
        warning_components = sum(1 for status in statuses.values() if status.status == 'warning')
        invalid_components = sum(1 for status in statuses.values() if status.status == 'invalid')
        
        # Count total issues and recommendations
        total_issues = sum(len(status.issues) for status in statuses.values())
        total_recommendations = sum(len(status.recommendations) for status in statuses.values())
        
        # Find components with most issues
        most_issues = max(statuses.items(), key=lambda x: len(x[1].issues))
        
        return {
            'total_components': total_components,
            'valid_components': valid_components,
            'warning_components': warning_components,
            'invalid_components': invalid_components,
            'total_issues': total_issues,
            'total_recommendations': total_recommendations,
            'most_issues_component': most_issues[0],
            'most_issues_count': len(most_issues[1].issues),
            'logic_health_percentage': (valid_components / total_components * 100) if total_components > 0 else 0
        }
    
    def get_logic_recommendations(self) -> List[str]:
        """Get comprehensive business logic recommendations"""
        statuses = self.check_all_logic()
        all_recommendations = []
        
        for status in statuses.values():
            all_recommendations.extend(status.recommendations)
            for issue in status.issues:
                if 'too high' in issue.lower() or 'too low' in issue.lower():
                    all_recommendations.append(f"Adjust parameter: {issue}")
                elif 'invalid' in issue.lower():
                    all_recommendations.append(f"Fix configuration: {issue}")
                elif 'disabled' in issue.lower():
                    all_recommendations.append(f"Enable feature: {issue}")
        
        return list(set(all_recommendations))  # Remove duplicates

# Global instance
logic_checker = LogicHealthChecker()

def get_logic_checker() -> LogicHealthChecker:
    """Get global logic checker instance"""
    return logic_checker

if __name__ == "__main__":
    # Test the logic checker
    checker = LogicHealthChecker()
    
    print("🧠 Business Logic Health Checker Test")
    print("=" * 50)
    
    # Check individual components
    for component in ['trading_rules', 'risk_thresholds', 'portfolio_allocation', 'position_sizing']:
        print(f"\nChecking {component}...")
        if component == 'trading_rules':
            status = checker.check_trading_rules()
        elif component == 'risk_thresholds':
            status = checker.check_risk_thresholds()
        elif component == 'portfolio_allocation':
            status = checker.check_portfolio_allocation()
        else:
            status = checker.check_position_sizing()
        
        print(f"  Status: {status.status}")
        print(f"  Issues: {len(status.issues)}")
        for issue in status.issues:
            print(f"    - {issue}")
        print(f"  Recommendations: {len(status.recommendations)}")
        for rec in status.recommendations:
            print(f"    - {rec}")
    
    # Get summary
    summary = checker.get_logic_health_summary()
    print(f"\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Get recommendations
    recommendations = checker.get_logic_recommendations()
    if recommendations:
        print(f"\nAll Recommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
