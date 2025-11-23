"""
🌙 Anarcho Capital's DeFi Safety Validator
Multi-layer safety checks for USDC and SOL protection
Built with love by Anarcho Capital 🚀
"""

import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical
from src.config.defi_config import DEFI_SAFETY_CONFIG
from src.config import (
    USDC_MINIMUM_PERCENT, USDC_EMERGENCY_PERCENT, SOL_MAXIMUM_PERCENT,
    SOL_TARGET_PERCENT, SOL_FEE_RESERVE_PERCENT, EMERGENCY_USDC_RESERVE_PERCENT,
    EMERGENCY_SOL_RESERVE_PERCENT, MAX_TOTAL_ALLOCATION_PERCENT
)

@dataclass
class SafetyCheckResult:
    """Result of a safety validation check"""
    is_safe: bool
    reason: str
    risk_level: str  # "safe", "warning", "danger"
    recommended_action: Optional[str] = None
    blocked_operations: list = None
    
    def __post_init__(self):
        if self.blocked_operations is None:
            self.blocked_operations = []

class DeFiSafetyValidator:
    """
    Validates DeFi operations against portfolio safety limits
    Ensures USDC and SOL reserves are never breached
    """
    
    def __init__(self):
        """Initialize the safety validator"""
        self.safety_config = DEFI_SAFETY_CONFIG
        self.check_history = []
        self.emergency_stops = 0
        
        info("🛡️ DeFi Safety Validator initialized")
    
    def can_execute_defi_operation(self, amount_usd: float, operation_type: str,
                                   portfolio_snapshot) -> SafetyCheckResult:
        """
        Main safety check before executing ANY DeFi operation
        
        Args:
            amount_usd: Amount to be deployed in DeFi
            operation_type: Type of operation (borrow, lend, yield_farm, etc.)
            portfolio_snapshot: Current portfolio snapshot
            
        Returns:
            SafetyCheckResult with safety status and recommendations
        """
        try:
            if not portfolio_snapshot:
                return SafetyCheckResult(
                    is_safe=False,
                    reason="No portfolio snapshot available",
                    risk_level="danger",
                    recommended_action="Wait for portfolio data"
                )
            
            total_value = portfolio_snapshot.total_value_usd
            # PortfolioSnapshot uses usdc_balance (not usdc_balance_usd) and sol_value_usd (not sol_balance_usd)
            usdc_balance = getattr(portfolio_snapshot, 'usdc_balance_usd', None) or getattr(portfolio_snapshot, 'usdc_balance', 0.0)
            sol_balance_usd = getattr(portfolio_snapshot, 'sol_balance_usd', None) or getattr(portfolio_snapshot, 'sol_value_usd', 0.0)
            
            # Calculate percentages
            usdc_pct = (usdc_balance / total_value) if total_value > 0 else 0
            sol_pct = (sol_balance_usd / total_value) if total_value > 0 else 0
            
            # Safety Check 1: USDC Minimum (20%)
            if usdc_pct < USDC_MINIMUM_PERCENT:
                error(f"🚫 BLOCKED: USDC reserves {usdc_pct*100:.1f}% below minimum {USDC_MINIMUM_PERCENT*100:.0f}%")
                return SafetyCheckResult(
                    is_safe=False,
                    reason=f"USDC reserves {usdc_pct*100:.1f}% below minimum {USDC_MINIMUM_PERCENT*100:.0f}%",
                    risk_level="danger",
                    recommended_action="Wait for USDC reserves to be replenished"
                )
            
            # Safety Check 2: USDC Emergency Threshold (15%)
            if usdc_pct < USDC_EMERGENCY_PERCENT:
                error(f"🚨 EMERGENCY: USDC at {usdc_pct*100:.1f}% - forcing emergency stop")
                self._trigger_emergency_stop()
                return SafetyCheckResult(
                    is_safe=False,
                    reason=f"EMERGENCY: USDC at {usdc_pct*100:.1f}%",
                    risk_level="danger",
                    recommended_action="EMERGENCY STOP - All DeFi operations halted"
                )
            
            # Safety Check 3: SOL Maximum (20%)
            if sol_pct > SOL_MAXIMUM_PERCENT:
                error(f"🚫 BLOCKED: SOL allocation {sol_pct*100:.1f}% exceeds maximum {SOL_MAXIMUM_PERCENT*100:.0f}%")
                return SafetyCheckResult(
                    is_safe=False,
                    reason=f"SOL allocation {sol_pct*100:.1f}% exceeds maximum {SOL_MAXIMUM_PERCENT*100:.0f}%",
                    risk_level="warning",
                    recommended_action="Convert excess SOL to USDC"
                )
            
            # Safety Check 4: Transaction wouldn't breach USDC minimum
            usdc_after = usdc_balance - amount_usd
            usdc_pct_after = (usdc_after / total_value) if total_value > 0 else 0
            
            if usdc_pct_after < USDC_MINIMUM_PERCENT:
                error(f"🚫 BLOCKED: Would drop USDC to {usdc_pct_after*100:.1f}%")
                return SafetyCheckResult(
                    is_safe=False,
                    reason=f"Operation would drop USDC to {usdc_pct_after*100:.1f}% (minimum {USDC_MINIMUM_PERCENT*100:.0f}%)",
                    risk_level="danger",
                    recommended_action=f"Reduce amount to ${(usdc_balance - total_value * USDC_MINIMUM_PERCENT):.2f}"
                )
            
            # Safety Check 5: Emergency reserves
            usdc_reserve = total_value * EMERGENCY_USDC_RESERVE_PERCENT
            if usdc_balance - amount_usd < usdc_reserve:
                error(f"🚫 BLOCKED: Would breach emergency reserve ${usdc_reserve:.2f}")
                return SafetyCheckResult(
                    is_safe=False,
                    reason=f"Would breach emergency USDC reserve of ${usdc_reserve:.2f}",
                    risk_level="danger",
                    recommended_action="Emergency reserves must be maintained"
                )
            
            # Safety Check 6: Total allocation limit
            current_allocation_pct = getattr(portfolio_snapshot, 'current_allocation_pct', 0)
            total_allocation_after = current_allocation_pct + (amount_usd / total_value) if total_value > 0 else 0
            
            if total_allocation_after > MAX_TOTAL_ALLOCATION_PERCENT:
                error(f"🚫 BLOCKED: Would exceed max total allocation {MAX_TOTAL_ALLOCATION_PERCENT*100:.0f}%")
                return SafetyCheckResult(
                    is_safe=False,
                    reason=f"Would exceed max total allocation {MAX_TOTAL_ALLOCATION_PERCENT*100:.0f}%",
                    risk_level="warning",
                    recommended_action="Reduce position size or close some positions"
                )
            
            # Safety Check 7: SOL fee reserve
            sol_reserve = total_value * SOL_FEE_RESERVE_PERCENT
            # Use sol_value_usd for comparison (PortfolioSnapshot attribute)
            if sol_balance_usd < sol_reserve:
                warning(f"⚠️ SOL balance below fee reserve: ${sol_balance_usd:.2f} < ${sol_reserve:.2f}")
                return SafetyCheckResult(
                    is_safe=True,
                    reason="SOL below ideal fee reserve",
                    risk_level="warning",
                    recommended_action="Monitor SOL balance for transaction fees"
                )
            
            # All safety checks passed
            info(f"\033[36m✅ Safety checks passed: USDC {usdc_pct*100:.1f}%, SOL {sol_pct*100:.1f}%\033[0m")
            return SafetyCheckResult(
                is_safe=True,
                reason="All safety checks passed",
                risk_level="safe"
            )
            
        except Exception as e:
            error(f"Error in safety validation: {str(e)}")
            return SafetyCheckResult(
                is_safe=False,
                reason=f"Validation error: {str(e)}",
                risk_level="danger",
                recommended_action="Manual review required"
            )
    
    def check_usdc_reserves(self, portfolio_snapshot) -> Tuple[bool, str]:
        """Check if USDC reserves are adequate"""
        try:
            total_value = portfolio_snapshot.total_value_usd
            # PortfolioSnapshot uses usdc_balance (not usdc_balance_usd)
            usdc_balance = getattr(portfolio_snapshot, 'usdc_balance_usd', None) or getattr(portfolio_snapshot, 'usdc_balance', 0.0)
            usdc_pct = (usdc_balance / total_value) if total_value > 0 else 0
            
            if usdc_pct < USDC_MINIMUM_PERCENT:
                return False, f"USDC {usdc_pct*100:.1f}% below minimum {USDC_MINIMUM_PERCENT*100:.0f}%"
            
            return True, "USDC reserves adequate"
            
        except Exception as e:
            error(f"Error checking USDC reserves: {str(e)}")
            return False, f"Error: {str(e)}"
    
    def check_sol_reserves(self, portfolio_snapshot) -> Tuple[bool, str]:
        """Check if SOL reserves are adequate"""
        try:
            total_value = portfolio_snapshot.total_value_usd
            # PortfolioSnapshot uses sol_value_usd (not sol_balance_usd)
            sol_balance_usd = getattr(portfolio_snapshot, 'sol_balance_usd', None) or getattr(portfolio_snapshot, 'sol_value_usd', 0.0)
            sol_pct = (sol_balance_usd / total_value) if total_value > 0 else 0
            
            if sol_pct > SOL_MAXIMUM_PERCENT:
                return False, f"SOL {sol_pct*100:.1f}% exceeds maximum {SOL_MAXIMUM_PERCENT*100:.0f}%"
            
            return True, "SOL reserves adequate"
            
        except Exception as e:
            error(f"Error checking SOL reserves: {str(e)}")
            return False, f"Error: {str(e)}"
    
    def _trigger_emergency_stop(self):
        """Trigger emergency stop for all DeFi operations"""
        try:
            self.emergency_stops += 1
            critical("🚨 EMERGENCY STOP TRIGGERED - All DeFi operations halted")
            # Add to history
            self.check_history.append({
                'timestamp': datetime.now(),
                'type': 'emergency_stop',
                'reason': 'USDC emergency threshold breached'
            })
            
        except Exception as e:
            error(f"Error triggering emergency stop: {str(e)}")
    
    def get_safety_summary(self, portfolio_snapshot) -> Dict[str, any]:
        """Get comprehensive safety summary"""
        try:
            if not portfolio_snapshot:
                return {"error": "No portfolio data"}
            
            total_value = portfolio_snapshot.total_value_usd
            # PortfolioSnapshot uses usdc_balance and sol_value_usd (with fallback for compatibility)
            usdc_balance = getattr(portfolio_snapshot, 'usdc_balance_usd', None) or getattr(portfolio_snapshot, 'usdc_balance', 0.0)
            sol_balance_usd = getattr(portfolio_snapshot, 'sol_balance_usd', None) or getattr(portfolio_snapshot, 'sol_value_usd', 0.0)
            
            usdc_pct = (usdc_balance / total_value) if total_value > 0 else 0
            sol_pct = (sol_balance_usd / total_value) if total_value > 0 else 0
            
            return {
                'total_value_usd': total_value,
                'usdc_balance_usd': usdc_balance,
                'usdc_percent': usdc_pct,
                'usdc_minimum': USDC_MINIMUM_PERCENT,
                'usdc_emergency': USDC_EMERGENCY_PERCENT,
                'sol_balance_usd': sol_balance_usd,
                'sol_percent': sol_pct,
                'sol_maximum': SOL_MAXIMUM_PERCENT,
                'sol_target': SOL_TARGET_PERCENT,
                'is_usdc_safe': usdc_pct >= USDC_MINIMUM_PERCENT,
                'is_sol_safe': sol_pct <= SOL_MAXIMUM_PERCENT,
                'emergency_stops': self.emergency_stops,
                'risk_level': self._calculate_overall_risk_level(usdc_pct, sol_pct)
            }
            
        except Exception as e:
            error(f"Error getting safety summary: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_overall_risk_level(self, usdc_pct: float, sol_pct: float) -> str:
        """Calculate overall portfolio risk level"""
        if usdc_pct < USDC_EMERGENCY_PERCENT:
            return "danger"
        elif usdc_pct < USDC_MINIMUM_PERCENT or sol_pct > SOL_MAXIMUM_PERCENT:
            return "warning"
        else:
            return "safe"

# Global instance
_safety_validator = None

def get_defi_safety_validator() -> DeFiSafetyValidator:
    """Get the global safety validator instance"""
    global _safety_validator
    if _safety_validator is None:
        _safety_validator = DeFiSafetyValidator()
    return _safety_validator

