"""
Cross-Protocol Risk Manager
Manages risk across multiple DeFi protocols
Built with love by Anarcho Capital
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass

from src.scripts.shared_services.logger import debug, info, warning, error
from src.config.defi_config import (
    DEFI_PROTOCOLS,
    SECONDARY_PROTOCOLS,
    PROTOCOL_DIVERSIFICATION,
    CROSS_PROTOCOL_CONFIG
)
from src.scripts.trading.portfolio_tracker import get_portfolio_tracker


@dataclass
class RiskScore:
    """Risk assessment for a protocol"""
    protocol: str
    risk_level: str  # 'low', 'medium', 'high'
    risk_score: float  # 0.0 to 1.0 (higher = riskier)
    diversification_score: float  # 0.0 to 1.0 (higher = better diversified)
    liquidation_risk: float  # 0.0 to 1.0 (higher = riskier)
    health_status: str  # 'healthy', 'warning', 'critical'
    issues: List[str] = None  # List of identified issues


class CrossProtocolRiskManager:
    """
    Manages risk across multiple DeFi protocols
    Ensures diversification, monitors protocol health, and triggers emergency migrations
    """
    
    def __init__(self):
        """Initialize the cross-protocol risk manager"""
        self.config = CROSS_PROTOCOL_CONFIG
        
        # Diversification limits
        self.max_allocation_per_protocol = PROTOCOL_DIVERSIFICATION.get('primary_protocols', 0.50)  # 50% max
        self.min_allocation_per_protocol = 0.05  # 5% minimum
        
        # Risk level mapping
        self.risk_map = {
            'low': 0.2,
            'medium': 0.5,
            'medium_high': 0.7,
            'high': 0.9
        }
        
        info("\033[36mCross-Protocol Risk Manager initialized\033[0m")
    
    def assess_protocol_risk(self, protocol: str) -> RiskScore:
        """
        Assess risk for a specific protocol
        
        Args:
            protocol: Protocol name to assess
            
        Returns:
            RiskScore object
        """
        try:
            all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
            protocol_config = all_protocols.get(protocol.lower())
            
            if not protocol_config:
                warning(f"Unknown protocol: {protocol}")
                return RiskScore(
                    protocol=protocol,
                    risk_level='high',
                    risk_score=1.0,
                    diversification_score=0.0,
                    liquidation_risk=1.0,
                    health_status='critical',
                    issues=['Unknown protocol']
                )
            
            # Get risk level
            risk_level = protocol_config.get('risk_level', 'medium')
            risk_score = self.risk_map.get(risk_level, 0.5)
            
            # Check audit status
            audit_status = protocol_config.get('audit_status', 'unknown')
            if audit_status != 'audited':
                risk_score += 0.2  # Increase risk if not audited
                issues = ['Protocol not audited']
            else:
                issues = []
            
            # Check enabled status
            if not protocol_config.get('enabled', False):
                issues.append('Protocol disabled')
                health_status = 'critical'
            else:
                health_status = 'healthy' if risk_score < 0.5 else 'warning'
            
            # Calculate diversification score (placeholder - should get from portfolio)
            diversification_score = 0.5  # TODO: Calculate from actual allocations
            
            # Estimate liquidation risk (placeholder - should calculate from positions)
            liquidation_risk = risk_score * 0.5  # TODO: Calculate from actual positions
            
            return RiskScore(
                protocol=protocol,
                risk_level=risk_level,
                risk_score=min(risk_score, 1.0),
                diversification_score=diversification_score,
                liquidation_risk=liquidation_risk,
                health_status=health_status,
                issues=issues
            )
            
        except Exception as e:
            error(f"Error assessing protocol risk: {str(e)}")
            return RiskScore(
                protocol=protocol,
                risk_level='high',
                risk_score=1.0,
                diversification_score=0.0,
                liquidation_risk=1.0,
                health_status='critical',
                issues=[f'Error: {str(e)}']
            )
    
    def check_diversification_limits(self) -> Tuple[bool, Dict[str, float]]:
        """
        Check if protocol allocations exceed diversification limits
        
        Returns:
            Tuple of (is_diversified: bool, allocations: Dict[protocol -> allocation_pct])
        """
        try:
            portfolio_tracker = get_portfolio_tracker()
            current_snapshot = portfolio_tracker.current_snapshot if portfolio_tracker else None
            
            if not current_snapshot:
                warning("No portfolio snapshot available for diversification check")
                return True, {}  # Assume OK if can't check
            
            total_value = current_snapshot.total_value_usd
            if total_value <= 0:
                return True, {}
            
            # TODO: Get actual protocol allocations from portfolio tracker
            # For now, return placeholder
            allocations = {}
            
            # Check if any protocol exceeds max allocation
            is_diversified = True
            for protocol, allocation_pct in allocations.items():
                if allocation_pct > self.max_allocation_per_protocol:
                    warning(f"Protocol {protocol} exceeds max allocation: {allocation_pct*100:.1f}% > {self.max_allocation_per_protocol*100:.1f}%")
                    is_diversified = False
            
            return is_diversified, allocations
            
        except Exception as e:
            error(f"Error checking diversification: {str(e)}")
            return True, {}  # Assume OK on error
    
    def should_emergency_migrate(self, protocol: str) -> Tuple[bool, str]:
        """
        Determine if emergency migration is needed for a protocol
        
        Args:
            protocol: Protocol to check
            
        Returns:
            Tuple of (should_migrate: bool, reason: str)
        """
        try:
            risk_score = self.assess_protocol_risk(protocol)
            
            # Emergency triggers
            if risk_score.health_status == 'critical':
                return True, f"Protocol health critical: {', '.join(risk_score.issues)}"
            
            if risk_score.liquidation_risk > 0.8:
                return True, f"High liquidation risk: {risk_score.liquidation_risk:.2f}"
            
            if risk_score.risk_score > 0.9:
                return True, f"Extreme risk level: {risk_score.risk_score:.2f}"
            
            # Check if protocol is disabled
            all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
            protocol_config = all_protocols.get(protocol.lower())
            if protocol_config and not protocol_config.get('enabled', False):
                return True, "Protocol disabled in config"
            
            return False, ""
            
        except Exception as e:
            error(f"Error checking emergency migration: {str(e)}")
            return False, ""
    
    def get_portfolio_risk_summary(self) -> Dict:
        """
        Get overall portfolio risk summary across all protocols
        
        Returns:
            Dictionary with risk metrics
        """
        try:
            all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
            
            protocol_risks = {}
            total_risk_score = 0.0
            protocol_count = 0
            
            for protocol_name, protocol_config in all_protocols.items():
                if not protocol_config.get('enabled', False):
                    continue
                
                risk_score = self.assess_protocol_risk(protocol_name)
                protocol_risks[protocol_name] = risk_score
                total_risk_score += risk_score.risk_score
                protocol_count += 1
            
            avg_risk = total_risk_score / protocol_count if protocol_count > 0 else 0.5
            
            # Check diversification
            is_diversified, allocations = self.check_diversification_limits()
            
            return {
                'average_risk_score': avg_risk,
                'is_diversified': is_diversified,
                'protocol_count': protocol_count,
                'protocol_risks': {k: {
                    'risk_level': v.risk_level,
                    'risk_score': v.risk_score,
                    'health_status': v.health_status
                } for k, v in protocol_risks.items()},
                'allocations': allocations
            }
            
        except Exception as e:
            error(f"Error getting portfolio risk summary: {str(e)}")
            return {'error': str(e)}


# Global instance
_risk_manager = None


def get_cross_protocol_risk_manager() -> CrossProtocolRiskManager:
    """Get the global cross-protocol risk manager instance"""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = CrossProtocolRiskManager()
    return _risk_manager

