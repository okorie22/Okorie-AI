"""
🌙 Anarcho Capital's Hyperliquid Account Manager
Centralized account state management for Hyperliquid trading
Tracks balance, positions, and equity separately from Solana wallet
Built with love by Anarcho Capital 🚀
"""

import threading
import time
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta

# Local imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
    from src.scripts.trading.hyperliquid_exchange import get_hyperliquid_exchange
    from src import config
except ImportError:
    from src.scripts.shared_services.logger import debug, info, warning, error
    from src.scripts.trading.hyperliquid_exchange import get_hyperliquid_exchange
    import src.config as config


class HyperliquidAccountManager:
    """
    Centralized Hyperliquid account state management
    Provides cached balance and position data with TTL
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
        """Initialize the Hyperliquid account manager"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Cache settings
        self.balance_cache = None
        self.balance_cache_time = None
        self.cache_ttl = 30  # 30 seconds TTL
        
        # Position cache
        self.positions_cache = None
        self.positions_cache_time = None
        
        # Exchange instance
        self.exchange = None
        try:
            self.exchange = get_hyperliquid_exchange()
            if self.exchange:
                info("✅ Hyperliquid Account Manager initialized")
            else:
                warning("⚠️ Hyperliquid exchange not available - account manager in limited mode")
        except Exception as e:
            warning(f"⚠️ Hyperliquid exchange initialization failed: {e}")
            self.exchange = None
    
    def get_account_balance(self, force_refresh: bool = False) -> Optional[Dict[str, float]]:
        """
        Get Hyperliquid account balance with caching
        
        Args:
            force_refresh: Force refresh even if cache is valid
        
        Returns:
            Dict with balance information or None if unavailable
        """
        if not self.exchange:
            return None
        
        # Check cache
        current_time = time.time()
        if not force_refresh and self.balance_cache and self.balance_cache_time:
            if current_time - self.balance_cache_time < self.cache_ttl:
                return self.balance_cache
        
        # Fetch fresh balance
        try:
            balance = self.exchange.get_account_balance()
            if balance:
                self.balance_cache = balance
                self.balance_cache_time = current_time
                return balance
        except Exception as e:
            error(f"Error fetching Hyperliquid balance: {e}")
            # Return cached value if available
            if self.balance_cache:
                warning("Using cached balance due to fetch error")
                return self.balance_cache
        
        return None
    
    def get_available_balance(self) -> float:
        """
        Get available balance for trading (free collateral)
        
        Returns:
            Available balance in USD, or 0.0 if unavailable
        """
        balance = self.get_account_balance()
        if balance:
            return balance.get('available_balance', 0.0)
        return 0.0
    
    def get_total_equity(self) -> float:
        """
        Get total account equity (balance + unrealized PnL)
        
        Returns:
            Total equity in USD, or 0.0 if unavailable
        """
        balance = self.get_account_balance()
        if balance:
            return balance.get('total_equity', 0.0)
        return 0.0
    
    def get_margin_used(self) -> float:
        """
        Get margin currently used by open positions
        
        Returns:
            Margin used in USD, or 0.0 if unavailable
        """
        balance = self.get_account_balance()
        if balance:
            return balance.get('margin_used', 0.0)
        return 0.0
    
    def can_open_position(self, size_usd: float, leverage: int) -> bool:
        """
        Check if account has enough balance for position
        
        Args:
            size_usd: Position size in USD
            leverage: Leverage multiplier
        
        Returns:
            True if account can open position
        """
        available = self.get_available_balance()
        margin_required = size_usd / leverage
        return available >= margin_required
    
    def sync_positions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Synchronize positions from Hyperliquid account
        
        Args:
            force_refresh: Force refresh even if cache is valid
        
        Returns:
            List of position dicts
        """
        if not self.exchange:
            return []
        
        # Check cache
        current_time = time.time()
        if not force_refresh and self.positions_cache and self.positions_cache_time:
            if current_time - self.positions_cache_time < self.cache_ttl:
                return self.positions_cache
        
        # Fetch fresh positions
        try:
            positions = self.exchange.get_positions()
            if positions is not None:
                self.positions_cache = positions
                self.positions_cache_time = current_time
                return positions
        except Exception as e:
            error(f"Error fetching Hyperliquid positions: {e}")
            # Return cached positions if available
            if self.positions_cache:
                warning("Using cached positions due to fetch error")
                return self.positions_cache
        
        return []
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get position for a specific symbol
        
        Args:
            symbol: Token symbol (e.g., 'BTC', 'ETH')
        
        Returns:
            Position dict or None
        """
        positions = self.sync_positions()
        return next((p for p in positions if p['symbol'] == symbol), None)
    
    def has_position(self, symbol: str) -> bool:
        """Check if account has an open position for symbol"""
        position = self.get_position(symbol)
        return position is not None and abs(position.get('size', 0)) > 0
    
    def get_position_value_usd(self, symbol: str) -> float:
        """
        Get current USD value of position for symbol
        
        Args:
            symbol: Token symbol
        
        Returns:
            Position value in USD, or 0.0 if no position
        """
        position = self.get_position(symbol)
        if position:
            # Position value = size * entry_price (approximate)
            size = abs(position.get('size', 0))
            entry_price = position.get('entry_price', 0)
            return size * entry_price
        return 0.0
    
    def clear_cache(self):
        """Clear all cached data"""
        self.balance_cache = None
        self.balance_cache_time = None
        self.positions_cache = None
        self.positions_cache_time = None
        debug("Cleared Hyperliquid account cache")
    
    def get_account_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive account summary
        
        Returns:
            Dict with account statistics
        """
        balance = self.get_account_balance()
        positions = self.sync_positions()
        
        total_unrealized_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
        total_position_value = sum(self.get_position_value_usd(p['symbol']) for p in positions)
        
        return {
            'total_equity': balance.get('total_equity', 0) if balance else 0,
            'available_balance': balance.get('available_balance', 0) if balance else 0,
            'margin_used': balance.get('margin_used', 0) if balance else 0,
            'unrealized_pnl': total_unrealized_pnl,
            'open_positions_count': len(positions),
            'total_position_value_usd': total_position_value,
            'positions': positions
        }


# Global singleton instance
_hyperliquid_account_manager = None

def get_hyperliquid_account_manager() -> Optional[HyperliquidAccountManager]:
    """Get singleton instance of Hyperliquid account manager"""
    global _hyperliquid_account_manager
    if _hyperliquid_account_manager is None:
        try:
            _hyperliquid_account_manager = HyperliquidAccountManager()
        except Exception as e:
            error(f"Failed to create Hyperliquid account manager: {e}")
            return None
    return _hyperliquid_account_manager
