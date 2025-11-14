"""
DeFi Arbitrage Engine for Cross-Protocol Strategy
Handles arbitrage opportunities between lending and borrowing protocols
Built with love by Anarcho Capital
"""

import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.scripts.shared_services.logger import debug, info, warning, error
from src.scripts.shared_services.rate_monitoring_service import (
    get_rate_monitoring_service, 
    ArbitrageOpportunity,
    RateData
)
from src.config.defi_config import CROSS_PROTOCOL_CONFIG, DEFI_PROTOCOLS, SECONDARY_PROTOCOLS
from src import config


@dataclass
class DeFiPosition:
    """DeFi position tracking across protocols"""
    protocol: str
    position_type: str  # 'lending' or 'borrowing'
    amount_usd: float
    rate: float
    opened_at: datetime
    collateral_token: Optional[str] = None  # For borrowing positions
    collateral_amount_usd: Optional[float] = None


@dataclass
class ArbitrageExecution:
    """Arbitrage execution record"""
    opportunity: ArbitrageOpportunity
    executed_at: datetime
    amount_usd: float
    success: bool
    profit_realized: Optional[float] = None
    notes: Optional[str] = None


class DeFiArbitrageEngine:
    """
    Engine for detecting and executing cross-protocol arbitrage opportunities
    Routes lending to highest-rate protocols and borrowing to lowest-rate protocols
    """
    
    def __init__(self):
        """Initialize the DeFi arbitrage engine"""
        self.rate_monitor = get_rate_monitoring_service()
        self.config = CROSS_PROTOCOL_CONFIG
        
        # Arbitrage settings
        self.min_arbitrage_spread = self.config.get('arbitrage_min_spread', 0.03)  # 3%
        self.arbitrage_enabled = self.config.get('enable_arbitrage', False)
        
        # Position tracking
        self.positions: Dict[str, List[DeFiPosition]] = {}  # protocol -> positions
        self.arbitrage_history: List[ArbitrageExecution] = []
        
        info("\033[36mDeFi Arbitrage Engine initialized\033[0m")
    
    def find_arbitrage_opportunities(self, min_spread: Optional[float] = None) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities between protocols
        
        Args:
            min_spread: Minimum spread required (default from config)
            
        Returns:
            List of ArbitrageOpportunity objects sorted by profit potential
        """
        try:
            if not self.arbitrage_enabled:
                debug("Arbitrage is disabled in config")
                return []
            
            if min_spread is None:
                min_spread = self.min_arbitrage_spread
            
            # Use rate monitoring service to find opportunities
            opportunities = self.rate_monitor.find_arbitrage_opportunities(min_spread)
            
            if opportunities:
                info(f"Found {len(opportunities)} arbitrage opportunities")
                for opp in opportunities[:3]:  # Log top 3
                    info(f"  {opp.borrow_protocol} ({opp.borrow_rate*100:.2f}%) → {opp.lend_protocol} ({opp.lend_rate*100:.2f}%) = {opp.spread*100:.2f}% spread")
            
            return opportunities
            
        except Exception as e:
            error(f"Error finding arbitrage opportunities: {str(e)}")
            return []
    
    def calculate_arbitrage_profit(self, opportunity: ArbitrageOpportunity, 
                                   amount_usd: float) -> float:
        """
        Calculate expected profit from arbitrage opportunity
        
        Args:
            opportunity: ArbitrageOpportunity object
            amount_usd: Amount to use for arbitrage
            
        Returns:
            Expected annual profit in USD
        """
        try:
            # Annual profit = spread * amount
            annual_profit = opportunity.spread * amount_usd
            
            # Subtract transaction costs (estimated)
            transaction_cost_pct = 0.002  # 0.2% for gas/fees
            transaction_cost = amount_usd * transaction_cost_pct
            
            net_profit = annual_profit - transaction_cost
            
            return net_profit
            
        except Exception as e:
            error(f"Error calculating arbitrage profit: {str(e)}")
            return 0.0
    
    def execute_arbitrage(self, opportunity: ArbitrageOpportunity, 
                         amount_usd: float) -> bool:
        """
        Execute arbitrage opportunity
        
        Args:
            opportunity: ArbitrageOpportunity to execute
            amount_usd: Amount to use for arbitrage
            
        Returns:
            True if successful
        """
        try:
            info(f"Executing arbitrage: Borrow ${amount_usd:.2f} from {opportunity.borrow_protocol}, Lend to {opportunity.lend_protocol}")
            
            if config.PAPER_TRADING_ENABLED:
                # Paper mode: simulate arbitrage
                info(f"PAPER: Borrow ${amount_usd:.2f} USDC from {opportunity.borrow_protocol} @ {opportunity.borrow_rate*100:.2f}%")
                info(f"PAPER: Lend ${amount_usd:.2f} USDC to {opportunity.lend_protocol} @ {opportunity.lend_rate*100:.2f}%")
                info(f"PAPER: Net spread: {opportunity.spread*100:.2f}% APY")
                
                # Record position
                self._record_position(
                    opportunity.borrow_protocol,
                    'borrowing',
                    amount_usd,
                    opportunity.borrow_rate
                )
                self._record_position(
                    opportunity.lend_protocol,
                    'lending',
                    amount_usd,
                    opportunity.lend_rate
                )
                
                # Record execution
                execution = ArbitrageExecution(
                    opportunity=opportunity,
                    executed_at=datetime.now(),
                    amount_usd=amount_usd,
                    success=True,
                    profit_realized=self.calculate_arbitrage_profit(opportunity, amount_usd)
                )
                self.arbitrage_history.append(execution)
                
                info(f"Arbitrage executed successfully: {opportunity.spread*100:.2f}% spread on ${amount_usd:.2f}")
                return True
            else:
                # Live mode: execute actual arbitrage
                # TODO: Implement actual borrowing and lending
                warning("Live arbitrage execution not yet implemented - simulation only")
                
                execution = ArbitrageExecution(
                    opportunity=opportunity,
                    executed_at=datetime.now(),
                    amount_usd=amount_usd,
                    success=False,
                    notes="Live execution not implemented"
                )
                self.arbitrage_history.append(execution)
                return False
                
        except Exception as e:
            error(f"Error executing arbitrage: {str(e)}")
            return False
    
    def rebalance_protocol_positions(self) -> bool:
        """
        Rebalance positions across protocols to optimize yields
        
        Returns:
            True if rebalancing successful
        """
        try:
            info("Rebalancing protocol positions...")
            
            # Find current best rates
            best_lending = self.rate_monitor.get_best_lending_rate()
            best_borrowing = self.rate_monitor.get_best_borrowing_rate()
            
            if not best_lending or not best_borrowing:
                warning("Cannot get rate data for rebalancing")
                return False
            
            # Check if we should rebalance lending positions
            # TODO: Get actual positions and compare rates
            # For now, just log the best rates
            info(f"Best lending rate: {best_lending.protocol} @ {best_lending.rate*100:.2f}%")
            info(f"Best borrowing rate: {best_borrowing.protocol} @ {best_borrowing.rate*100:.2f}%")
            
            # TODO: Implement actual position rebalancing
            # This would:
            # 1. Check current positions
            # 2. Compare rates
            # 3. Move funds to higher-yielding protocols
            # 4. Consider migration costs
            
            return True
            
        except Exception as e:
            error(f"Error rebalancing positions: {str(e)}")
            return False
    
    def _record_position(self, protocol: str, position_type: str, 
                        amount_usd: float, rate: float, 
                        collateral_token: Optional[str] = None):
        """Record a DeFi position"""
        try:
            if protocol not in self.positions:
                self.positions[protocol] = []
            
            position = DeFiPosition(
                protocol=protocol,
                position_type=position_type,
                amount_usd=amount_usd,
                rate=rate,
                opened_at=datetime.now(),
                collateral_token=collateral_token
            )
            
            self.positions[protocol].append(position)
            
        except Exception as e:
            error(f"Error recording position: {str(e)}")
    
    def get_positions(self) -> Dict[str, List[DeFiPosition]]:
        """Get all tracked positions"""
        return self.positions.copy()
    
    def get_arbitrage_history(self, days: int = 30) -> List[ArbitrageExecution]:
        """Get arbitrage execution history"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            return [
                exec for exec in self.arbitrage_history
                if exec.executed_at > cutoff_date
            ]
        except Exception as e:
            error(f"Error getting arbitrage history: {str(e)}")
            return []
    
    def get_total_arbitrage_profit(self, days: int = 30) -> float:
        """Calculate total arbitrage profit over specified period"""
        try:
            history = self.get_arbitrage_history(days)
            return sum(exec.profit_realized or 0.0 for exec in history if exec.success)
        except Exception as e:
            error(f"Error calculating total profit: {str(e)}")
            return 0.0


# Global instance
_arbitrage_engine = None


def get_defi_arbitrage_engine() -> DeFiArbitrageEngine:
    """Get the global DeFi arbitrage engine instance"""
    global _arbitrage_engine
    if _arbitrage_engine is None:
        _arbitrage_engine = DeFiArbitrageEngine()
    return _arbitrage_engine

