"""
Staking Migration Engine for Cross-Protocol Strategy
Handles migration opportunities between staking protocols
Built with love by Anarcho Capital
"""

import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.scripts.shared_services.logger import debug, info, warning, error
from src.scripts.shared_services.rate_monitoring_service import get_rate_monitoring_service, RateData
from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
from src.config.defi_config import CROSS_PROTOCOL_CONFIG
from src import config


@dataclass
class MigrationOpportunity:
    """Migration opportunity between protocols"""
    from_protocol: str
    to_protocol: str
    current_rate: float
    target_rate: float
    spread: float  # Target rate - current rate
    migration_cost_sol: float
    net_benefit_apy: float  # Spread - cost equivalent
    should_migrate: bool


@dataclass
class StakingPosition:
    """Staking position tracking"""
    protocol: str
    amount_sol: float
    amount_usd: float
    apy: float
    staked_at: datetime
    last_migration: Optional[datetime] = None


class StakingMigrationEngine:
    """
    Engine for detecting and executing staking protocol migrations
    Optimizes yield by moving staked SOL to higher-yielding protocols
    """
    
    def __init__(self):
        """Initialize the staking migration engine"""
        self.rate_monitor = get_rate_monitoring_service()
        self.price_service = get_optimized_price_service()
        self.config = CROSS_PROTOCOL_CONFIG
        
        # Migration settings
        self.min_migration_spread = self.config.get('min_migration_spread', 0.02)  # 2%
        self.max_migration_frequency_days = self.config.get('max_migration_frequency_days', 7)
        self.migration_cost_sol = self.config.get('migration_cost_sol', 0.01)  # 0.01 SOL default
        
        # Position tracking
        self.positions: Dict[str, StakingPosition] = {}
        self.migration_history: List[Dict] = []
        
        info("Staking Migration Engine initialized")
    
    def should_migrate(self, current_protocol: str, current_rate: float, 
                      best_protocol: str, best_rate: float, 
                      amount_sol: float) -> Tuple[bool, Optional[MigrationOpportunity]]:
        """
        Determine if migration is beneficial
        
        Args:
            current_protocol: Current staking protocol
            current_rate: Current APY (as decimal)
            best_protocol: Best available protocol
            best_rate: Best APY (as decimal)
            amount_sol: Amount staked in SOL
            
        Returns:
            Tuple of (should_migrate: bool, opportunity: MigrationOpportunity)
        """
        try:
            # Check if already on best protocol
            if current_protocol.lower() == best_protocol.lower():
                return False, None
            
            # Calculate spread
            spread = best_rate - current_rate
            
            # Check minimum spread threshold
            if spread < self.min_migration_spread:
                debug(f"Spread {spread*100:.2f}% below minimum {self.min_migration_spread*100:.2f}% threshold")
                return False, None
            
            # Check migration frequency limit
            if self._recently_migrated(current_protocol):
                debug(f"Recently migrated from {current_protocol}, skipping")
                return False, None
            
            # Calculate migration cost
            migration_cost = self.calculate_migration_cost(amount_sol)
            
            # Calculate net benefit (spread - cost equivalent)
            # Convert migration cost to equivalent APY impact
            sol_price = self.price_service.get_price(config.SOL_ADDRESS)
            if not sol_price or sol_price <= 0:
                warning("Cannot get SOL price for migration cost calculation")
                sol_price = 150.0  # Fallback
            
            cost_usd = migration_cost * sol_price
            position_value_usd = amount_sol * sol_price
            
            # Annual cost as percentage of position
            # Migration cost is one-time, but we'll calculate it as equivalent to 1 year of reduced yield
            cost_impact_apy = (cost_usd / position_value_usd) if position_value_usd > 0 else 0
            
            # Net benefit after costs
            net_benefit = spread - cost_impact_apy
            
            # Only migrate if net benefit exceeds threshold
            if net_benefit < self.min_migration_spread:
                debug(f"Net benefit {net_benefit*100:.2f}% below threshold after costs")
                return False, None
            
            opportunity = MigrationOpportunity(
                from_protocol=current_protocol,
                to_protocol=best_protocol,
                current_rate=current_rate,
                target_rate=best_rate,
                spread=spread,
                migration_cost_sol=migration_cost,
                net_benefit_apy=net_benefit,
                should_migrate=True
            )
            
            info(f"Migration opportunity: {current_protocol} ({current_rate*100:.2f}%) → {best_protocol} ({best_rate*100:.2f}%)")
            info(f"  Spread: {spread*100:.2f}%, Cost: {migration_cost:.4f} SOL, Net Benefit: {net_benefit*100:.2f}%")
            
            return True, opportunity
            
        except Exception as e:
            error(f"Error evaluating migration: {str(e)}")
            return False, None
    
    def calculate_migration_cost(self, amount_sol: float) -> float:
        """
        Calculate migration cost (unstake + restake fees)
        
        Args:
            amount_sol: Amount being migrated
            
        Returns:
            Total cost in SOL
        """
        try:
            # Base migration cost (transaction fees)
            base_cost = self.migration_cost_sol
            
            # Additional cost based on amount (slippage, etc.)
            # For now, flat fee
            # TODO: Add actual protocol-specific fees if available
            
            return base_cost
            
        except Exception as e:
            error(f"Error calculating migration cost: {str(e)}")
            return self.migration_cost_sol  # Fallback
    
    def find_migration_opportunities(self, current_positions: Dict[str, float]) -> List[MigrationOpportunity]:
        """
        Find all migration opportunities for current positions
        
        Args:
            current_positions: Dict of protocol -> staked_amount_sol
            
        Returns:
            List of MigrationOpportunity objects
        """
        try:
            opportunities = []
            
            # Get current staking rates
            staking_rates = self.rate_monitor.get_staking_rates()
            
            if not staking_rates:
                warning("No staking rates available for migration analysis")
                return []
            
            # Find best rate
            best_rate_data = self.rate_monitor.get_best_staking_rate()
            if not best_rate_data:
                return []
            
            best_protocol = best_rate_data.protocol
            best_rate = best_rate_data.rate
            
            # Check each current position
            for protocol, amount_sol in current_positions.items():
                if amount_sol <= 0:
                    continue
                
                # Get current protocol rate
                protocol_key = protocol.lower()
                current_rate_data = staking_rates.get(protocol_key)
                
                if not current_rate_data:
                    debug(f"No rate data for protocol {protocol}")
                    continue
                
                current_rate = current_rate_data.rate
                
                # Check if migration is beneficial
                should_migrate, opportunity = self.should_migrate(
                    protocol,
                    current_rate,
                    best_protocol,
                    best_rate,
                    amount_sol
                )
                
                if should_migrate and opportunity:
                    opportunities.append(opportunity)
            
            return opportunities
            
        except Exception as e:
            error(f"Error finding migration opportunities: {str(e)}")
            return []
    
    def execute_migration(self, from_protocol: str, to_protocol: str, 
                         amount_sol: float, opportunity: Optional[MigrationOpportunity] = None) -> bool:
        """
        Execute migration from one protocol to another
        
        Args:
            from_protocol: Current staking protocol
            to_protocol: Target staking protocol
            amount_sol: Amount to migrate
            opportunity: MigrationOpportunity object (optional)
            
        Returns:
            True if migration successful
        """
        try:
            info(f"Executing migration: {amount_sol:.4f} SOL from {from_protocol} to {to_protocol}")
            
            if config.PAPER_TRADING_ENABLED:
                # Paper mode: simulate migration
                info(f"PAPER: Unstaking {amount_sol:.4f} SOL from {from_protocol}")
                info(f"PAPER: Staking {amount_sol:.4f} SOL to {to_protocol}")
                
                # Record migration
                self._record_migration(from_protocol, to_protocol, amount_sol, True)
                return True
            else:
                # Live mode: execute actual migration
                # TODO: Implement actual unstaking and restaking
                # For now, this would call unstake and stake functions
                warning("Live migration not yet implemented - simulation only")
                
                # Record migration attempt
                self._record_migration(from_protocol, to_protocol, amount_sol, False)
                return False
                
        except Exception as e:
            error(f"Error executing migration: {str(e)}")
            return False
    
    def _recently_migrated(self, protocol: str) -> bool:
        """Check if recently migrated from this protocol"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.max_migration_frequency_days)
            
            # Check migration history
            for migration in self.migration_history:
                if migration.get('from_protocol', '').lower() == protocol.lower():
                    migration_date = migration.get('timestamp')
                    if migration_date and migration_date > cutoff_date:
                        return True
            
            return False
            
        except Exception as e:
            error(f"Error checking migration history: {str(e)}")
            return False  # Allow migration if check fails
    
    def _record_migration(self, from_protocol: str, to_protocol: str, 
                          amount_sol: float, success: bool):
        """Record migration in history"""
        try:
            migration_record = {
                'from_protocol': from_protocol,
                'to_protocol': to_protocol,
                'amount_sol': amount_sol,
                'timestamp': datetime.now(),
                'success': success
            }
            
            self.migration_history.append(migration_record)
            
            # Keep only last 100 migrations
            if len(self.migration_history) > 100:
                self.migration_history = self.migration_history[-100:]
            
            info(f"Migration recorded: {from_protocol} → {to_protocol} ({amount_sol:.4f} SOL)")
            
        except Exception as e:
            error(f"Error recording migration: {str(e)}")
    
    def update_position(self, protocol: str, amount_sol: float, apy: float):
        """Update tracked staking position"""
        try:
            sol_price = self.price_service.get_price(config.SOL_ADDRESS) or 150.0
            amount_usd = amount_sol * sol_price
            
            position = StakingPosition(
                protocol=protocol,
                amount_sol=amount_sol,
                amount_usd=amount_usd,
                apy=apy,
                staked_at=datetime.now()
            )
            
            self.positions[protocol.lower()] = position
            
        except Exception as e:
            error(f"Error updating position: {str(e)}")
    
    def get_positions(self) -> Dict[str, StakingPosition]:
        """Get all tracked positions"""
        return self.positions.copy()
    
    def get_migration_history(self, days: int = 30) -> List[Dict]:
        """Get migration history for specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            return [
                m for m in self.migration_history
                if m.get('timestamp', datetime.min) > cutoff_date
            ]
        except Exception as e:
            error(f"Error getting migration history: {str(e)}")
            return []


# Global instance
_migration_engine = None


def get_staking_migration_engine() -> StakingMigrationEngine:
    """Get the global staking migration engine instance"""
    global _migration_engine
    if _migration_engine is None:
        _migration_engine = StakingMigrationEngine()
    return _migration_engine

