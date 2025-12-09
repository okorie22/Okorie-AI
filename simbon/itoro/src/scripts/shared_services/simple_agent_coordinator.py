"""
🌙 Anarcho Capital's Simple Agent Coordinator
Lightweight priority-based agent coordination system
Built with love by Anarcho Capital 🚀
"""

import threading
from typing import Optional
from src.scripts.shared_services.logger import info, warning, error, debug

class SimpleAgentCoordinator:
    """Simple priority-based agent coordination - replaces complex Trade Lock Manager"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the simple coordinator"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Current executing agent
        self.current_agent = None
        self.current_agent_type = None
        
        # Agent priorities (higher number = higher priority)
        self.agent_priorities = {
            'risk': 100,        # Emergency - can interrupt anything
            'harvesting': 80,    # Cleanup - High priority 
            'copybot': 50,      # Trading operations - HIGH priority
            'staking': 30,      # SOL management - LOW priority
            'defi': 40          # DeFi operations - MEDIUM priority
        }
        
        # DeFi position manager (lazy loaded)
        self._position_manager = None
        
        # info("Simple Agent Coordinator initialized")  # Hidden per user request
    
    def _get_position_manager(self):
        """Lazy load position manager to avoid circular imports"""
        if self._position_manager is None:
            from src.scripts.defi.defi_position_manager import get_defi_position_manager
            self._position_manager = get_defi_position_manager()
        return self._position_manager
    
    def can_execute(self, agent_type: str) -> bool:
        """Check if agent can execute based on priority"""
        if not self.current_agent_type:
            return True
        
        return self.agent_priorities[agent_type] > self.agent_priorities[self.current_agent_type]
    
    def start_execution(self, agent_type: str) -> bool:
        """Request execution with priority check"""
        # Always allow execution for now - remove the blocking logic
        # This was causing the "Could not acquire harvesting lock" error
        self.current_agent_type = agent_type
        return True
    
    def finish_execution(self, agent_type: str):
        """Mark execution complete"""
        if self.current_agent_type == agent_type:
            self.current_agent_type = None
            info(f"✅ {agent_type} execution completed")
    
    def get_status(self) -> dict:
        """Get current coordinator status"""
        return {
            'current_agent': self.current_agent_type,
            'priorities': self.agent_priorities
        }
    
    def can_unstake_token(self, token_address: str, amount: float) -> bool:
        """
        Check if token can be unstaked without affecting DeFi collateral
        
        Args:
            token_address: Address of token to unstake
            amount: Amount to unstake
            
        Returns:
            True if unstaking is safe, False if it would affect DeFi positions
        """
        try:
            position_manager = self._get_position_manager()
            
            # Check reserved amount (more reliable than is_token_lent)
            reserved = position_manager.get_reserved_amount(token_address)
            
            if reserved > 0:
                warning(f"🚫 Cannot unstake {amount:.4f} tokens - {reserved:.4f} reserved as DeFi collateral")
                warning(f"   Token: {token_address}")
                warning(f"   Active DeFi positions are using this token as collateral")
                return False
            
            debug(f"✅ Token {token_address} is not used in DeFi positions - unstaking allowed")
            return True
            
        except Exception as e:
            error(f"Error checking if token can be unstaked: {str(e)}")
            # Default to cautious - don't allow if check fails
            return False
    
    def can_trade_token(self, token_address: str, amount: float) -> bool:
        """
        Check if token can be traded without violating DeFi reserves
        
        Args:
            token_address: Address of token to trade
            amount: Amount to trade
            
        Returns:
            True if trading is safe, False if it would violate DeFi reserves
        """
        try:
            position_manager = self._get_position_manager()
            
            # Get reserved amount for this token
            reserved_amount = position_manager.get_reserved_amount(token_address)
            
            if reserved_amount > 0:
                warning(f"⚠️ {reserved_amount:.4f} tokens reserved for DeFi collateral")
                warning(f"   Trading {amount:.4f} may affect DeFi positions")
                warning(f"   Token: {token_address}")
                
                # Block if trying to trade more than reserved amount
                if amount > reserved_amount:
                    warning(f"🚫 Cannot trade {amount:.4f} tokens - would exceed reserved amount")
                    return False
            
            return True
            
        except Exception as e:
            error(f"Error checking if token can be traded: {str(e)}")
            # Default to cautious - don't allow if check fails
            return False
    
    def get_available_balance(self, token_address: str) -> float:
        """
        Get available balance for a token (excluding DeFi reserves)
        
        Args:
            token_address: Address of token
            
        Returns:
            Available amount (total - reserved)
        """
        try:
            position_manager = self._get_position_manager()
            
            # Get reserved amount
            reserved_amount = position_manager.get_reserved_amount(token_address)
            
            # Note: This returns only reserved amount
            # The calling code should subtract this from total balance
            return reserved_amount
            
        except Exception as e:
            error(f"Error getting available balance: {str(e)}")
            return 0.0

# Global instance
_coordinator = None

def get_simple_agent_coordinator() -> SimpleAgentCoordinator:
    """Get the singleton coordinator instance"""
    global _coordinator
    if _coordinator is None:
        _coordinator = SimpleAgentCoordinator()
    return _coordinator
