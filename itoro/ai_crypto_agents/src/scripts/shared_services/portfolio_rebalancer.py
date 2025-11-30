"""
Portfolio Rebalancer for Cross-Protocol Strategy
Automated rebalancing across protocols based on rate changes
Built with love by Anarcho Capital
"""

import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.scripts.shared_services.logger import debug, info, warning, error
from src.scripts.shared_services.rate_monitoring_service import get_rate_monitoring_service
from src.scripts.defi.defi_protocol_router import get_defi_protocol_router
from src.scripts.defi.cross_protocol_risk_manager import get_cross_protocol_risk_manager
from src.scripts.staking.staking_migration_engine import get_staking_migration_engine
from src.scripts.defi.defi_arbitrage_engine import get_defi_arbitrage_engine
from src.config.defi_config import CROSS_PROTOCOL_CONFIG
from src.scripts.trading.portfolio_tracker import get_portfolio_tracker


@dataclass
class RebalancingOpportunity:
    """Rebalancing opportunity"""
    type: str  # 'staking', 'lending', 'borrowing'
    from_protocol: str
    to_protocol: str
    amount_usd: float
    rate_spread: float
    cost_usd: float
    net_benefit_usd: float
    should_rebalance: bool


class PortfolioRebalancer:
    """
    Automated portfolio rebalancing engine
    Monitors rate changes and rebalances positions to optimize yields
    """
    
    def __init__(self):
        """Initialize the portfolio rebalancer"""
        self.rate_monitor = get_rate_monitoring_service()
        self.protocol_router = get_defi_protocol_router()
        self.risk_manager = get_cross_protocol_risk_manager()
        self.migration_engine = get_staking_migration_engine()
        self.arbitrage_engine = get_defi_arbitrage_engine()
        self.config = CROSS_PROTOCOL_CONFIG
        
        # Rebalancing settings
        self.min_rate_spread = self.config.get('min_migration_spread', 0.02)  # 2%
        self.rebalancing_interval_hours = 24  # Check once per day
        self.last_rebalancing_check = None
        
        info("\033[36mPortfolio Rebalancer initialized\033[0m")
    
    def check_rebalancing_opportunities(self) -> List[RebalancingOpportunity]:
        """
        Check for rebalancing opportunities across all positions
        
        Returns:
            List of RebalancingOpportunity objects
        """
        try:
            opportunities = []
            
            # Check staking rebalancing
            staking_opportunities = self._check_staking_rebalancing()
            opportunities.extend(staking_opportunities)
            
            # Check DeFi lending rebalancing
            lending_opportunities = self._check_lending_rebalancing()
            opportunities.extend(lending_opportunities)
            
            # Check DeFi borrowing rebalancing
            borrowing_opportunities = self._check_borrowing_rebalancing()
            opportunities.extend(borrowing_opportunities)
            
            # Sort by net benefit (descending)
            opportunities.sort(key=lambda x: x.net_benefit_usd, reverse=True)
            
            if opportunities:
                info(f"Found {len(opportunities)} rebalancing opportunities")
            
            return opportunities
            
        except Exception as e:
            error(f"Error checking rebalancing opportunities: {str(e)}")
            return []
    
    def _check_staking_rebalancing(self) -> List[RebalancingOpportunity]:
        """Check for staking rebalancing opportunities"""
        try:
            opportunities = []
            
            # Get current staking positions (placeholder - should get from portfolio)
            current_positions = {}  # Dict of protocol -> amount_sol
            
            # Find migration opportunities
            migration_opportunities = self.migration_engine.find_migration_opportunities(current_positions)
            
            for opp in migration_opportunities:
                sol_price = 150.0  # TODO: Get actual SOL price
                amount_usd = 0.1 * sol_price  # Placeholder amount
                
                opportunity = RebalancingOpportunity(
                    type='staking',
                    from_protocol=opp.from_protocol,
                    to_protocol=opp.to_protocol,
                    amount_usd=amount_usd,
                    rate_spread=opp.spread,
                    cost_usd=opp.migration_cost_sol * sol_price,
                    net_benefit_usd=opp.net_benefit_apy * amount_usd,
                    should_rebalance=opp.should_migrate
                )
                
                opportunities.append(opportunity)
            
            return opportunities
            
        except Exception as e:
            error(f"Error checking staking rebalancing: {str(e)}")
            return []
    
    def _check_lending_rebalancing(self) -> List[RebalancingOpportunity]:
        """Check for lending rebalancing opportunities"""
        try:
            opportunities = []
            
            # Get current best lending rate
            best_lending = self.rate_monitor.get_best_lending_rate()
            
            if not best_lending:
                return []
            
            # TODO: Get actual lending positions from portfolio
            # For now, return placeholder
            # This would compare current positions to best available rate
            
            return opportunities
            
        except Exception as e:
            error(f"Error checking lending rebalancing: {str(e)}")
            return []
    
    def _check_borrowing_rebalancing(self) -> List[RebalancingOpportunity]:
        """Check for borrowing rebalancing opportunities"""
        try:
            opportunities = []
            
            # Get current best borrowing rate
            best_borrowing = self.rate_monitor.get_best_borrowing_rate()
            
            if not best_borrowing:
                return []
            
            # TODO: Get actual borrowing positions from portfolio
            # For now, return placeholder
            # This would compare current positions to best available rate
            
            return opportunities
            
        except Exception as e:
            error(f"Error checking borrowing rebalancing: {str(e)}")
            return []
    
    def execute_rebalancing(self, opportunities: List[RebalancingOpportunity]) -> bool:
        """
        Execute rebalancing for given opportunities
        
        Args:
            opportunities: List of rebalancing opportunities
            
        Returns:
            True if rebalancing successful
        """
        try:
            if not opportunities:
                return False
            
            # Execute best opportunities (limit to top 3)
            executed_count = 0
            for opp in opportunities[:3]:
                if not opp.should_rebalance:
                    continue
                
                if opp.net_benefit_usd <= 0:
                    continue  # Skip if not profitable
                
                info(f"Executing rebalancing: {opp.from_protocol} → {opp.to_protocol} ({opp.type})")
                
                success = False
                if opp.type == 'staking':
                    # Use migration engine
                    success = self.migration_engine.execute_migration(
                        opp.from_protocol,
                        opp.to_protocol,
                        opp.amount_usd / 150.0,  # Convert USD to SOL (placeholder price)
                        None
                    )
                elif opp.type == 'lending':
                    # TODO: Implement lending rebalancing
                    warning("Lending rebalancing not yet implemented")
                elif opp.type == 'borrowing':
                    # TODO: Implement borrowing rebalancing
                    warning("Borrowing rebalancing not yet implemented")
                
                if success:
                    executed_count += 1
                    info(f"Successfully rebalanced {opp.type} position: {opp.from_protocol} → {opp.to_protocol}")
                else:
                    warning(f"Rebalancing failed: {opp.from_protocol} → {opp.to_protocol}")
            
            if executed_count > 0:
                info(f"Rebalancing completed: {executed_count} positions rebalanced")
                return True
            
            return False
            
        except Exception as e:
            error(f"Error executing rebalancing: {str(e)}")
            return False
    
    def periodic_rebalancing_check(self) -> bool:
        """
        Periodic rebalancing check (called by agents)
        
        Returns:
            True if rebalancing was performed
        """
        try:
            # Check if enough time has passed
            if self.last_rebalancing_check:
                time_since_check = (datetime.now() - self.last_rebalancing_check).total_seconds() / 3600
                if time_since_check < self.rebalancing_interval_hours:
                    return False  # Too soon to check again
            
            info("Performing periodic rebalancing check...")
            
            # Check for opportunities
            opportunities = self.check_rebalancing_opportunities()
            
            if not opportunities:
                debug("No rebalancing opportunities found")
                self.last_rebalancing_check = datetime.now()
                return False
            
            # Execute rebalancing
            success = self.execute_rebalancing(opportunities)
            
            self.last_rebalancing_check = datetime.now()
            return success
            
        except Exception as e:
            error(f"Error in periodic rebalancing check: {str(e)}")
            return False
    
    def rebalance_on_rate_threshold(self, threshold: float = None) -> bool:
        """
        Rebalance when rate spreads exceed threshold
        
        Args:
            threshold: Rate spread threshold (default from config)
            
        Returns:
            True if rebalancing triggered
        """
        try:
            if threshold is None:
                threshold = self.min_rate_spread
            
            # Check for arbitrage opportunities
            opportunities = self.arbitrage_engine.find_arbitrage_opportunities(threshold)
            
            if not opportunities:
                return False
            
            # Execute best opportunity
            best_opp = opportunities[0]
            
            # TODO: Get actual amount from portfolio
            amount_usd = 100.0  # Placeholder
            
            success = self.arbitrage_engine.execute_arbitrage(best_opp, amount_usd)
            
            if success:
                info(f"Rebalancing triggered by rate threshold: {threshold*100:.2f}% spread")
            
            return success
            
        except Exception as e:
            error(f"Error in rate threshold rebalancing: {str(e)}")
            return False


# Global instance
_portfolio_rebalancer = None


def get_portfolio_rebalancer() -> PortfolioRebalancer:
    """Get the global portfolio rebalancer instance"""
    global _portfolio_rebalancer
    if _portfolio_rebalancer is None:
        _portfolio_rebalancer = PortfolioRebalancer()
    return _portfolio_rebalancer

