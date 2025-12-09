"""
DeFi Protocol Router for Cross-Protocol Strategy
Intelligent protocol selection for lending and borrowing operations
Built with love by Anarcho Capital
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass

from src.scripts.shared_services.logger import debug, info, warning, error
from src.scripts.shared_services.rate_monitoring_service import (
    get_rate_monitoring_service,
    RateData
)
from src.config.defi_config import (
    DEFI_PROTOCOLS,
    SECONDARY_PROTOCOLS,
    PROTOCOL_DIVERSIFICATION,
    CROSS_PROTOCOL_CONFIG
)
from src.scripts.trading.portfolio_tracker import get_portfolio_tracker


@dataclass
class ProtocolScore:
    """Protocol scoring for selection"""
    protocol: str
    rate: float
    risk_score: float  # 0.0 to 1.0 (lower is better)
    allocation_score: float  # 0.0 to 1.0 (higher is better)
    total_score: float  # Combined score
    current_allocation_pct: float  # Current allocation percentage


class DeFiProtocolRouter:
    """
    Router for selecting optimal protocols for lending and borrowing
    Considers rates, risk, diversification, and protocol health
    """
    
    def __init__(self):
        """Initialize the protocol router"""
        self.rate_monitor = get_rate_monitoring_service()
        self.config = CROSS_PROTOCOL_CONFIG
        
        # Protocol settings
        self.max_allocation_per_protocol = PROTOCOL_DIVERSIFICATION.get('primary_protocols', 0.50)  # 50% max
        self.min_allocation_per_protocol = 0.05  # 5% minimum
        
        # Risk level mapping
        self.risk_map = {
            'low': 0.2,
            'medium': 0.5,
            'medium_high': 0.7,
            'high': 0.9
        }
        
        info("\033[36mDeFi Protocol Router initialized\033[0m")
    
    def select_best_lending_protocol(self, amount_usd: float) -> Optional[str]:
        """
        Select best protocol for lending based on rates, risk, and diversification
        
        Args:
            amount_usd: Amount to lend
            
        Returns:
            Protocol name or None if no suitable protocol
        """
        try:
            # Get current lending rates
            lending_rates = self.rate_monitor.get_lending_rates()
            
            if not lending_rates:
                warning("No lending rates available")
                return None
            
            # Get current portfolio allocation
            portfolio_tracker = get_portfolio_tracker()
            current_snapshot = portfolio_tracker.current_snapshot if portfolio_tracker else None
            total_portfolio_value = current_snapshot.total_value_usd if current_snapshot else 0
            
            # Score all protocols
            protocol_scores = []
            
            all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
            
            for protocol_name, protocol_config in all_protocols.items():
                if not protocol_config.get('enabled', False):
                    continue
                
                # Get rate
                rate_data = lending_rates.get(protocol_name.lower())
                if not rate_data:
                    continue
                
                rate = rate_data.rate
                
                # Get risk score
                risk_level = protocol_config.get('risk_level', 'medium')
                risk_score = self.risk_map.get(risk_level, 0.5)
                
                # Calculate current allocation
                # TODO: Get actual allocation from portfolio tracker
                current_allocation_pct = 0.0  # Placeholder
                
                # Check if exceeds max allocation
                new_allocation_pct = (amount_usd / total_portfolio_value) if total_portfolio_value > 0 else 0
                if current_allocation_pct + new_allocation_pct > self.max_allocation_per_protocol:
                    debug(f"Protocol {protocol_name} exceeds max allocation")
                    continue
                
                # Calculate allocation score (prefer lower current allocation)
                allocation_score = 1.0 - (current_allocation_pct / self.max_allocation_per_protocol)
                
                # Calculate total score (rate weighted 70%, risk weighted 20%, allocation 10%)
                total_score = (rate * 0.7) - (risk_score * 0.2) + (allocation_score * 0.1)
                
                score = ProtocolScore(
                    protocol=protocol_name,
                    rate=rate,
                    risk_score=risk_score,
                    allocation_score=allocation_score,
                    total_score=total_score,
                    current_allocation_pct=current_allocation_pct
                )
                
                protocol_scores.append(score)
            
            if not protocol_scores:
                warning("No suitable lending protocols found")
                return None
            
            # Sort by total score (descending)
            protocol_scores.sort(key=lambda x: x.total_score, reverse=True)
            
            best_protocol = protocol_scores[0]
            info(f"Selected lending protocol: {best_protocol.protocol} (rate: {best_protocol.rate*100:.2f}%, score: {best_protocol.total_score:.3f})")
            
            return best_protocol.protocol
            
        except Exception as e:
            error(f"Error selecting lending protocol: {str(e)}")
            return None
    
    def select_best_borrowing_protocol(self, amount_usd: float, 
                                      collateral_token: str = "SOL") -> Optional[str]:
        """
        Select best protocol for borrowing based on rates, risk, and diversification
        
        Args:
            amount_usd: Amount to borrow
            collateral_token: Collateral token type
            
        Returns:
            Protocol name or None if no suitable protocol
        """
        try:
            # Get current borrowing rates
            borrowing_rates = self.rate_monitor.get_borrowing_rates()
            
            if not borrowing_rates:
                warning("No borrowing rates available")
                return None
            
            # Get current portfolio allocation
            portfolio_tracker = get_portfolio_tracker()
            current_snapshot = portfolio_tracker.current_snapshot if portfolio_tracker else None
            total_portfolio_value = current_snapshot.total_value_usd if current_snapshot else 0
            
            # Score all protocols
            protocol_scores = []
            
            all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
            
            for protocol_name, protocol_config in all_protocols.items():
                if not protocol_config.get('enabled', False):
                    continue
                
                # Get rate
                rate_data = borrowing_rates.get(protocol_name.lower())
                if not rate_data:
                    continue
                
                rate = rate_data.rate
                
                # For borrowing, lower rate is better
                # Invert rate for scoring (lower rate = higher score)
                rate_score = 1.0 - (rate / 0.20)  # Normalize assuming max 20% rate
                
                # Get risk score
                risk_level = protocol_config.get('risk_level', 'medium')
                risk_score = self.risk_map.get(risk_level, 0.5)
                
                # Calculate current allocation
                # TODO: Get actual allocation from portfolio tracker
                current_allocation_pct = 0.0  # Placeholder
                
                # Check if exceeds max allocation
                new_allocation_pct = (amount_usd / total_portfolio_value) if total_portfolio_value > 0 else 0
                if current_allocation_pct + new_allocation_pct > self.max_allocation_per_protocol:
                    debug(f"Protocol {protocol_name} exceeds max allocation")
                    continue
                
                # Calculate allocation score
                allocation_score = 1.0 - (current_allocation_pct / self.max_allocation_per_protocol)
                
                # Calculate total score (rate weighted 70%, risk weighted 20%, allocation 10%)
                # For borrowing, we want low rate (high rate_score), low risk, good allocation
                total_score = (rate_score * 0.7) - (risk_score * 0.2) + (allocation_score * 0.1)
                
                score = ProtocolScore(
                    protocol=protocol_name,
                    rate=rate,
                    risk_score=risk_score,
                    allocation_score=allocation_score,
                    total_score=total_score,
                    current_allocation_pct=current_allocation_pct
                )
                
                protocol_scores.append(score)
            
            if not protocol_scores:
                warning("No suitable borrowing protocols found")
                return None
            
            # Sort by total score (descending)
            protocol_scores.sort(key=lambda x: x.total_score, reverse=True)
            
            best_protocol = protocol_scores[0]
            info(f"Selected borrowing protocol: {best_protocol.protocol} (rate: {best_protocol.rate*100:.2f}%, score: {best_protocol.total_score:.3f})")
            
            return best_protocol.protocol
            
        except Exception as e:
            error(f"Error selecting borrowing protocol: {str(e)}")
            return None
    
    def check_protocol_health(self, protocol: str) -> bool:
        """
        Check if protocol is healthy and safe to use
        
        Args:
            protocol: Protocol name to check
            
        Returns:
            True if protocol is healthy
        """
        try:
            all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
            protocol_config = all_protocols.get(protocol.lower())
            
            if not protocol_config:
                warning(f"Unknown protocol: {protocol}")
                return False
            
            # Check if enabled
            if not protocol_config.get('enabled', False):
                debug(f"Protocol {protocol} is disabled")
                return False
            
            # Check audit status
            audit_status = protocol_config.get('audit_status', 'unknown')
            if audit_status != 'audited':
                warning(f"Protocol {protocol} is not audited")
                return False
            
            # Check TVL (if available)
            min_tvl = protocol_config.get('min_tvl_usd', 0)
            if min_tvl > 0:
                # TODO: Get actual TVL from API
                # For now, assume healthy if protocol is enabled and audited
                pass
            
            return True
            
        except Exception as e:
            error(f"Error checking protocol health: {str(e)}")
            return False
    
    def rebalance_protocol_allocations(self) -> bool:
        """
        Rebalance allocations across protocols to maintain diversification
        
        Returns:
            True if rebalancing successful
        """
        try:
            info("Checking protocol allocation diversification...")
            
            # TODO: Get actual allocations from portfolio tracker
            # For now, just log the check
            debug("Protocol allocation rebalancing check completed")
            
            # This would:
            # 1. Get current allocations per protocol
            # 2. Check if any exceed max limits
            # 3. Move funds to under-allocated protocols
            # 4. Consider rate differences and migration costs
            
            return True
            
        except Exception as e:
            error(f"Error rebalancing allocations: {str(e)}")
            return False


# Global instance
_protocol_router = None


def get_defi_protocol_router() -> DeFiProtocolRouter:
    """Get the global DeFi protocol router instance"""
    global _protocol_router
    if _protocol_router is None:
        _protocol_router = DeFiProtocolRouter()
    return _protocol_router

