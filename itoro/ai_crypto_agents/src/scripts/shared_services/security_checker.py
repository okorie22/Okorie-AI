#!/usr/bin/env python3
"""
🔒 Anarcho Capital's Security Checker
Validate API keys, wallet security, and trade safety systems
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import re
import base58
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class SecurityStatus:
    """Security status information"""
    component: str
    status: str  # 'secure', 'warning', 'insecure', 'unknown'
    last_check: datetime
    issues: List[str]
    recommendations: List[str]
    performance_metrics: Dict[str, Any]

class SecurityChecker:
    """Monitor security and safety systems"""
    
    def __init__(self):
        self.required_api_keys = [
            'HELIUS_API_KEY',
            'BIRDEYE_API_KEY',
            'DEFAULT_WALLET_ADDRESS',
            'RPC_ENDPOINT'
        ]
        
        self.optional_api_keys = [
            'JUPITER_API_KEY',
            'PUMPFUN_API_KEY',
            'COINGECKO_API_KEY',
            'APIFY_API_TOKEN',
            'QUICKNODE_RPC_ENDPOINT'
        ]
        
        self.security_thresholds = {
            'min_api_key_length': 20,
            'max_api_key_length': 200,
            'min_wallet_address_length': 32,
            'max_wallet_address_length': 50,
            'max_slippage_percent': 10.0,
            'min_position_size_usd': 0.01,
            'max_position_size_usd': 10000.0
        }
    
    def check_api_keys(self) -> SecurityStatus:
        """Check API key security"""
        issues = []
        recommendations = []
        
        # Check required API keys
        missing_required = []
        for key in self.required_api_keys:
            value = os.getenv(key)
            if not value:
                missing_required.append(key)
            else:
                # Validate key format
                if len(value) < self.security_thresholds['min_api_key_length']:
                    issues.append(f"{key} is too short (minimum {self.security_thresholds['min_api_key_length']} characters)")
                elif len(value) > self.security_thresholds['max_api_key_length']:
                    issues.append(f"{key} is too long (maximum {self.security_thresholds['max_api_key_length']} characters)")
        
        if missing_required:
            issues.append(f"Missing required API keys: {', '.join(missing_required)}")
        
        # Check optional API keys
        missing_optional = []
        for key in self.optional_api_keys:
            value = os.getenv(key)
            if not value:
                missing_optional.append(key)
        
        if missing_optional:
            recommendations.append(f"Consider adding optional API keys for better performance: {', '.join(missing_optional)}")
        
        # Check for hardcoded keys in config
        try:
            from src import config
            config_file = os.path.join(project_root, 'src', 'config.py')
            with open(config_file, 'r') as f:
                config_content = f.read()
            
            # Look for hardcoded API keys (basic check)
            hardcoded_patterns = [
                r'api[_-]?key\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']'
            ]
            
            for pattern in hardcoded_patterns:
                if re.search(pattern, config_content, re.IGNORECASE):
                    issues.append("Potential hardcoded API keys found in config file")
                    break
        except Exception:
            pass  # Ignore config file issues
        
        # Determine status
        if issues:
            if any('Missing required' in issue for issue in issues):
                status = 'insecure'
            else:
                status = 'warning'
        else:
            status = 'secure'
        
        performance_metrics = {
            'required_keys_present': len(self.required_api_keys) - len(missing_required),
            'optional_keys_present': len(self.optional_api_keys) - len(missing_optional),
            'total_keys_checked': len(self.required_api_keys) + len(self.optional_api_keys)
        }
        
        return SecurityStatus(
            component='api_keys',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_wallet_security(self) -> SecurityStatus:
        """Check wallet address security"""
        issues = []
        recommendations = []
        
        wallet_address = os.getenv('DEFAULT_WALLET_ADDRESS')
        
        if not wallet_address:
            issues.append("No wallet address configured")
            status = 'insecure'
        else:
            # Validate wallet address format
            if len(wallet_address) < self.security_thresholds['min_wallet_address_length']:
                issues.append(f"Wallet address too short (minimum {self.security_thresholds['min_wallet_address_length']} characters)")
            elif len(wallet_address) > self.security_thresholds['max_wallet_address_length']:
                issues.append(f"Wallet address too long (maximum {self.security_thresholds['max_wallet_address_length']} characters)")
            
            # Check if it looks like a valid Solana address
            if not self._is_valid_solana_address(wallet_address):
                issues.append("Wallet address does not appear to be a valid Solana address")
            
            # Check for common test addresses
            test_addresses = [
                '11111111111111111111111111111111',  # System program
                'So11111111111111111111111111111111111111112',  # SOL mint
                'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'  # USDC mint
            ]
            
            if wallet_address in test_addresses:
                issues.append("Wallet address appears to be a system/token address, not a user wallet")
            
            if issues:
                status = 'insecure'
            else:
                status = 'secure'
                recommendations.append("Wallet address format is valid")
        
        performance_metrics = {
            'wallet_configured': wallet_address is not None,
            'address_length': len(wallet_address) if wallet_address else 0,
            'appears_valid': self._is_valid_solana_address(wallet_address) if wallet_address else False
        }
        
        return SecurityStatus(
            component='wallet_security',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def _is_valid_solana_address(self, address: str) -> bool:
        """Check if address looks like a valid Solana address"""
        try:
            # Basic length check
            if len(address) < 32 or len(address) > 50:
                return False
            
            # Try base58 decoding
            decoded = base58.b58decode(address)
            return len(decoded) == 32
        except Exception:
            return False
    
    def check_trade_safety(self) -> SecurityStatus:
        """Check trade safety parameters"""
        issues = []
        recommendations = []
        
        try:
            from src import config
            
            # Check slippage settings
            slippage = getattr(config, 'slippage', 200)  # Default 2%
            if slippage > self.security_thresholds['max_slippage_percent'] * 100:  # Convert to basis points
                issues.append(f"Slippage too high: {slippage/100:.1f}% (maximum {self.security_thresholds['max_slippage_percent']:.1f}%)")
            
            # Check position size limits
            min_position = getattr(config, 'MIN_POSITION_SIZE_USD', 0.01)
            max_position = getattr(config, 'MAX_POSITION_SIZE_USD', 1000.0)
            
            if min_position < self.security_thresholds['min_position_size_usd']:
                issues.append(f"Minimum position size too low: ${min_position} (minimum ${self.security_thresholds['min_position_size_usd']})")
            
            if max_position > self.security_thresholds['max_position_size_usd']:
                issues.append(f"Maximum position size too high: ${max_position} (maximum ${self.security_thresholds['max_position_size_usd']})")
            
            # Check risk management settings
            max_loss_percent = getattr(config, 'MAX_LOSS_PERCENT', 10)
            if max_loss_percent > 50:
                issues.append(f"Maximum loss percentage too high: {max_loss_percent}% (recommended < 50%)")
            
            # Check emergency stop settings
            emergency_stop_enabled = getattr(config, 'EMERGENCY_STOP_ENABLED', True)
            if not emergency_stop_enabled:
                issues.append("Emergency stop is disabled - this is a security risk")
            
            # Check paper trading mode
            paper_trading = getattr(config, 'PAPER_TRADING_ENABLED', True)
            if not paper_trading:
                recommendations.append("Live trading mode detected - ensure all safety checks are enabled")
            
            # Check validation settings
            trade_validation = getattr(config, 'ENABLE_TRADE_VALIDATION', True)
            if not trade_validation:
                issues.append("Trade validation is disabled - this is a security risk")
            
            if issues:
                status = 'insecure'
            elif recommendations:
                status = 'warning'
            else:
                status = 'secure'
            
            performance_metrics = {
                'slippage_bps': slippage,
                'min_position_usd': min_position,
                'max_position_usd': max_position,
                'max_loss_percent': max_loss_percent,
                'emergency_stop_enabled': emergency_stop_enabled,
                'paper_trading_enabled': paper_trading,
                'trade_validation_enabled': trade_validation
            }
            
        except Exception as e:
            issues.append(f"Error checking trade safety: {str(e)}")
            status = 'insecure'
            performance_metrics = {}
        
        return SecurityStatus(
            component='trade_safety',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_emergency_systems(self) -> SecurityStatus:
        """Check emergency stop and safety systems"""
        issues = []
        recommendations = []
        
        try:
            from src import config
            
            # Check emergency stop configuration
            emergency_stop_enabled = getattr(config, 'EMERGENCY_STOP_ENABLED', True)
            if not emergency_stop_enabled:
                issues.append("Emergency stop system is disabled")
            
            # Check drawdown limits
            drawdown_limit = getattr(config, 'DRAWDOWN_LIMIT_PERCENT', -30)
            if drawdown_limit > -10:  # Less than 10% drawdown limit
                issues.append(f"Drawdown limit too restrictive: {drawdown_limit}% (recommended -20% to -30%)")
            elif drawdown_limit < -50:  # More than 50% drawdown limit
                issues.append(f"Drawdown limit too permissive: {drawdown_limit}% (recommended -20% to -30%)")
            
            # Check consecutive loss limits
            consecutive_loss_limit = getattr(config, 'CONSECUTIVE_LOSS_LIMIT', 6)
            if consecutive_loss_limit > 10:
                issues.append(f"Consecutive loss limit too high: {consecutive_loss_limit} (recommended < 10)")
            
            # Check risk agent settings
            risk_enabled = getattr(config, 'RISK_ENABLED', True)
            if not risk_enabled:
                issues.append("Risk management agent is disabled")
            
            # Check position validation
            position_validation = getattr(config, 'POSITION_VALIDATION', {})
            if not position_validation.get('ENABLED', False):
                issues.append("Position validation is disabled")
            
            if issues:
                status = 'insecure'
            elif recommendations:
                status = 'warning'
            else:
                status = 'secure'
            
            performance_metrics = {
                'emergency_stop_enabled': emergency_stop_enabled,
                'drawdown_limit_percent': drawdown_limit,
                'consecutive_loss_limit': consecutive_loss_limit,
                'risk_agent_enabled': risk_enabled,
                'position_validation_enabled': position_validation.get('ENABLED', False)
            }
            
        except Exception as e:
            issues.append(f"Error checking emergency systems: {str(e)}")
            status = 'insecure'
            performance_metrics = {}
        
        return SecurityStatus(
            component='emergency_systems',
            status=status,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_all_security(self) -> Dict[str, SecurityStatus]:
        """Check all security components"""
        statuses = {}
        
        statuses['api_keys'] = self.check_api_keys()
        statuses['wallet_security'] = self.check_wallet_security()
        statuses['trade_safety'] = self.check_trade_safety()
        statuses['emergency_systems'] = self.check_emergency_systems()
        
        return statuses
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get overall security summary"""
        statuses = self.check_all_security()
        
        total_components = len(statuses)
        secure_components = sum(1 for status in statuses.values() if status.status == 'secure')
        warning_components = sum(1 for status in statuses.values() if status.status == 'warning')
        insecure_components = sum(1 for status in statuses.values() if status.status == 'insecure')
        
        # Count total issues
        total_issues = sum(len(status.issues) for status in statuses.values())
        total_recommendations = sum(len(status.recommendations) for status in statuses.values())
        
        # Find most critical issues
        critical_issues = []
        for status in statuses.values():
            for issue in status.issues:
                if any(keyword in issue.lower() for keyword in ['missing', 'disabled', 'insecure', 'risk']):
                    critical_issues.append(f"{status.component}: {issue}")
        
        return {
            'total_components': total_components,
            'secure_components': secure_components,
            'warning_components': warning_components,
            'insecure_components': insecure_components,
            'total_issues': total_issues,
            'total_recommendations': total_recommendations,
            'critical_issues': critical_issues,
            'security_percentage': (secure_components / total_components * 100) if total_components > 0 else 0
        }
    
    def get_security_recommendations(self) -> List[str]:
        """Get comprehensive security recommendations"""
        statuses = self.check_all_security()
        all_recommendations = []
        
        for status in statuses.values():
            all_recommendations.extend(status.recommendations)
            for issue in status.issues:
                if 'missing' in issue.lower():
                    all_recommendations.append(f"Fix missing configuration: {issue}")
                elif 'disabled' in issue.lower():
                    all_recommendations.append(f"Enable security feature: {issue}")
                elif 'too high' in issue.lower() or 'too low' in issue.lower():
                    all_recommendations.append(f"Adjust security parameter: {issue}")
        
        return list(set(all_recommendations))  # Remove duplicates

# Global instance
security_checker = SecurityChecker()

def get_security_checker() -> SecurityChecker:
    """Get global security checker instance"""
    return security_checker

if __name__ == "__main__":
    # Test the security checker
    checker = SecurityChecker()
    
    print("🔒 Security Checker Test")
    print("=" * 50)
    
    # Check individual components
    for component in ['api_keys', 'wallet_security', 'trade_safety', 'emergency_systems']:
        print(f"\nChecking {component}...")
        if component == 'api_keys':
            status = checker.check_api_keys()
        elif component == 'wallet_security':
            status = checker.check_wallet_security()
        elif component == 'trade_safety':
            status = checker.check_trade_safety()
        else:
            status = checker.check_emergency_systems()
        
        print(f"  Status: {status.status}")
        print(f"  Issues: {len(status.issues)}")
        for issue in status.issues:
            print(f"    - {issue}")
        print(f"  Recommendations: {len(status.recommendations)}")
        for rec in status.recommendations:
            print(f"    - {rec}")
    
    # Get summary
    summary = checker.get_security_summary()
    print(f"\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Get recommendations
    recommendations = checker.get_security_recommendations()
    if recommendations:
        print(f"\nAll Recommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
