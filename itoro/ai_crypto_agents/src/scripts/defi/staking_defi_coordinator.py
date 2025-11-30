"""
🌙 Anarcho Capital's Staking-DeFi Coordinator
Coordinates between staking agent and DeFi agent for optimal capital allocation
Built with love by Anarcho Capital 🚀
"""

import time
import threading
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from src.scripts.shared_services.logger import debug, info, warning, error
from src.config import EXCLUDED_TOKENS, SOL_ADDRESS, USDC_ADDRESS, STAKED_SOL_TOKEN_ADDRESS

@dataclass
class StakingEvent:
    """Staking completion event"""
    event_id: str
    timestamp: datetime
    staked_amount_sol: float
    staked_amount_usd: float
    stSOL_received: float
    protocol: str

class StakingDeFiCoordinator:
    """
    Coordinates staking completions with DeFi leverage opportunities
    Only stSOL triggers DeFi agent, SOL/USDC only checked periodically
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Event tracking
        self.staking_events = []
        
        # Cross-protocol components
        try:
            from src.scripts.shared_services.rate_monitoring_service import get_rate_monitoring_service
            from src.scripts.shared_services.portfolio_rebalancer import get_portfolio_rebalancer
            self.rate_monitor = get_rate_monitoring_service()
            self.rebalancer = get_portfolio_rebalancer()
            info("Cross-protocol components initialized in coordinator")
        except Exception as e:
            warning(f"Failed to initialize cross-protocol components: {str(e)}")
            self.rate_monitor = None
            self.rebalancer = None
        self.defi_agent = None
        self.last_staking_event_time = 0
        self.cooldown_seconds = 3600  # 1 hour cooldown
        
        # Coordination state
        self.is_staking_active = False
        self.pending_staked_sol = 0.0
        
        # Trigger context tracking - stores which asset triggered DeFi agent
        self.trigger_context: Optional[Dict] = None
        
        info("🔄 Staking-DeFi Coordinator initialized")
    
    def register_defi_agent(self, defi_agent):
        """Register DeFi agent for notifications"""
        self.defi_agent = defi_agent
        info("✅ DeFi agent registered with coordinator")
    
    def handle_staking_complete(self, staked_amount_sol: float, protocol: str = "marinade"):
        """
        Handle staking completion event
        This is the ONLY event that should trigger DeFi agent
        
        Args:
            staked_amount_sol: Amount staked in SOL
            protocol: Staking protocol used
        """
        try:
            # Check cooldown
            current_time = time.time()
            if current_time - self.last_staking_event_time < self.cooldown_seconds:
                debug(f"⚠️ Staking event ignored - within cooldown period ({int(self.cooldown_seconds/60)} min)")
                return False
            
            # Get SOL price
            from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
            from src.config import SOL_ADDRESS
            price_service = get_optimized_price_service()
            sol_price = price_service.get_price(SOL_ADDRESS)
            
            staked_amount_usd = staked_amount_sol * sol_price
            
            # Only trigger if meaningful amount (> $1)
            if staked_amount_usd < 1.0:
                debug(f"⚠️ Staking amount too small: ${staked_amount_usd:.2f}")
                return False
            
            # Create event
            event = StakingEvent(
                event_id=f"staking_{int(time.time())}",
                timestamp=datetime.now(),
                staked_amount_sol=staked_amount_sol,
                staked_amount_usd=staked_amount_usd,
                stSOL_received=staked_amount_sol,  # 1:1 ratio
                protocol=protocol
            )
            
            # Store event
            self.staking_events.append(event)
            self.last_staking_event_time = current_time
            
            info(f"🎯 STAKING COMPLETE: {staked_amount_sol:.4f} SOL (${staked_amount_usd:.2f}) on {protocol}")
            info(f"📈 This is the ONLY trigger for DeFi leverage - stSOL available")
            
            # Update portfolio snapshot to trigger DeFi agent
            self._trigger_defi_agent(event)
            
            return True
            
        except Exception as e:
            error(f"Error handling staking completion: {str(e)}")
            return False
    
    def _trigger_defi_agent(self, event: StakingEvent):
        """Trigger DeFi agent on staking completion"""
        try:
            if not self.defi_agent:
                warning("No DeFi agent registered - cannot trigger leverage loops")
                return
            
            info(f"🚀 Triggering DeFi agent for stSOL leverage opportunity")
            info(f"💰 Available: {event.staked_amount_sol:.4f} stSOL (${event.staked_amount_usd:.2f})")
            
            # Store trigger context - stSOL was just staked and should be prioritized
            self.trigger_context = {
                'asset_type': 'stSOL',
                'amount_usd': event.staked_amount_usd,
                'amount_sol': event.staked_amount_sol,
                'timestamp': event.timestamp,
                'protocol': event.protocol,
                'trigger_source': 'staking_complete'
            }
            
            # Pass rate monitoring data if available
            if self.rate_monitor:
                try:
                    # Get current best rates for context
                    best_staking = self.rate_monitor.get_best_staking_rate()
                    best_lending = self.rate_monitor.get_best_lending_rate()
                    best_borrowing = self.rate_monitor.get_best_borrowing_rate()
                    
                    # Add rate context to trigger
                    self.trigger_context['rate_context'] = {
                        'best_staking_rate': best_staking.rate if best_staking else None,
                        'best_staking_protocol': best_staking.protocol if best_staking else None,
                        'best_lending_rate': best_lending.rate if best_lending else None,
                        'best_lending_protocol': best_lending.protocol if best_lending else None,
                        'best_borrowing_rate': best_borrowing.rate if best_borrowing else None,
                        'best_borrowing_protocol': best_borrowing.protocol if best_borrowing else None
                    }
                    
                    debug("Rate monitoring data added to trigger context")
                except Exception as e:
                    warning(f"Failed to add rate context: {str(e)}")
            
            # CRITICAL: Actually trigger the DeFi agent to check for leverage opportunities
            if hasattr(self.defi_agent, '_check_portfolio_state'):
                # Call the portfolio state check which includes leverage strategy execution
                self.defi_agent._check_portfolio_state()
                info("📡 DeFi agent triggered - checking leverage opportunities")
            else:
                warning("DeFi agent doesn't have _check_portfolio_state method")
            
        except Exception as e:
            error(f"Error triggering DeFi agent: {str(e)}")
    
    def get_idle_assets(self, portfolio_snapshot) -> Dict[str, float]:
        """
        Get idle assets from EXCLUDED_TOKENS (SOL, stSOL, USDC)
        These are the only assets DeFi should consider
        
        Args:
            portfolio_snapshot: Current portfolio snapshot
            
        Returns:
            Dict of idle assets with USD values
        """
        try:
            if not portfolio_snapshot:
                return {'SOL': 0.0, 'stSOL': 0.0, 'USDC': 0.0}
            
            # Use getattr with defaults for compatibility with different snapshot types
            idle_assets = {
                'SOL': getattr(portfolio_snapshot, 'sol_value_usd', 0.0),
                'stSOL': getattr(portfolio_snapshot, 'staked_sol_value_usd', 0.0),
                'USDC': getattr(portfolio_snapshot, 'usdc_balance_usd', 
                               getattr(portfolio_snapshot, 'usdc_balance', 0.0))
            }
            
            return idle_assets
            
        except Exception as e:
            error(f"Error getting idle assets: {str(e)}")
            return {'SOL': 0.0, 'stSOL': 0.0, 'USDC': 0.0}
    
    def should_check_idle_capital(self) -> bool:
        """
        Determine if DeFi agent should check idle capital
        This happens during periodic checks (1 day intervals)
        
        Returns:
            True if should check now
        """
        try:
            # Check if it's been more than 1 day since last check
            if self.last_staking_event_time == 0:
                return True  # First check
            
            time_since_last_staking = time.time() - self.last_staking_event_time
            days_since = time_since_last_staking / 86400  # Convert to days
            
            # Check if it's been at least 1 day
            return days_since >= 1.0
            
        except Exception as e:
            error(f"Error checking idle capital timing: {str(e)}")
            return False
    
    def get_rate_monitoring_data(self) -> Optional[Dict]:
        """
        Get current rate monitoring data for cross-protocol coordination
        
        Returns:
            Dictionary with current rates from all protocols
        """
        try:
            if not self.rate_monitor:
                return None
            
            staking_rates = self.rate_monitor.get_staking_rates()
            lending_rates = self.rate_monitor.get_lending_rates()
            borrowing_rates = self.rate_monitor.get_borrowing_rates()
            
            return {
                'staking_rates': {k: v.rate for k, v in staking_rates.items()},
                'lending_rates': {k: v.rate for k, v in lending_rates.items()},
                'borrowing_rates': {k: v.rate for k, v in borrowing_rates.items()},
                'timestamp': datetime.now()
            }
        except Exception as e:
            warning(f"Error getting rate monitoring data: {str(e)}")
            return None
    
    def get_trigger_context(self) -> Optional[Dict]:
        """
        Get the latest trigger context - which asset triggered the DeFi agent
        
        Returns:
            Dict with trigger info (asset_type, amount_usd, timestamp, etc.) or None
        """
        try:
            # Check if trigger context is recent (within last hour)
            if self.trigger_context:
                context_age = (datetime.now() - self.trigger_context['timestamp']).total_seconds()
                if context_age < 3600:  # 1 hour validity
                    return self.trigger_context
                else:
                    # Context expired, clear it
                    self.trigger_context = None
            
            return None
            
        except Exception as e:
            error(f"Error getting trigger context: {str(e)}")
            return None
    
    def get_staking_defi_summary(self) -> Dict[str, any]:
        """Get coordination summary"""
        try:
            recent_events = [
                e for e in self.staking_events
                if (datetime.now() - e.timestamp).days < 7
            ]
            
            return {
                'total_staking_events': len(self.staking_events),
                'recent_events_7d': len(recent_events),
                'last_event_time': self.last_staking_event_time,
                'cooldown_active': time.time() - self.last_staking_event_time < self.cooldown_seconds,
                'defi_agent_registered': self.defi_agent is not None,
                'pending_staked_sol': self.pending_staked_sol,
                'has_trigger_context': self.trigger_context is not None
            }
            
        except Exception as e:
            error(f"Error getting coordination summary: {str(e)}")
            return {"error": str(e)}

# Global instance
_coordinator = None

def get_staking_defi_coordinator() -> StakingDeFiCoordinator:
    """Get the global coordinator instance"""
    global _coordinator
    if _coordinator is None:
        _coordinator = StakingDeFiCoordinator()
    return _coordinator

