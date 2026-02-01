"""
🌙 Anarcho Capital's Hyperliquid Exchange Integration
Full SDK implementation for perpetual futures trading on Hyperliquid
Built with love by Anarcho Capital 🚀
"""

import os
import time
from typing import Dict, Optional, List, Any
from datetime import datetime

# Local imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
    from src import config
except ImportError:
    from src.scripts.shared_services.logger import debug, info, warning, error
    import src.config as config

# Hyperliquid SDK imports
try:
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange
    import eth_account
    HYPERLIQUID_SDK_AVAILABLE = True
except ImportError:
    HYPERLIQUID_SDK_AVAILABLE = False
    warning("Hyperliquid Python SDK not installed. Run: pip install hyperliquid-python-sdk")


class HyperliquidExchange:
    """
    Full Hyperliquid exchange integration using official Python SDK
    Handles order placement, position management, and account queries
    """
    
    _instance = None
    _lock = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            import threading
            cls._lock = threading.Lock()
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Hyperliquid exchange connection"""
        if hasattr(self, '_initialized'):
            return
        
        if not HYPERLIQUID_SDK_AVAILABLE:
            raise ImportError("Hyperliquid Python SDK required. Install with: pip install hyperliquid-python-sdk")
        
        self._initialized = True
        
        # Get credentials from config
        self.wallet_address = config.HYPERLIQUID_WALLET_ADDRESS
        self.private_key = config.HYPERLIQUID_PRIVATE_KEY
        self.testnet = getattr(config, 'HYPERLIQUID_TESTNET', False)
        
        if not self.wallet_address or not self.private_key:
            raise ValueError("Hyperliquid credentials not configured. Set HYPERLIQUID_WALLET_ADDRESS and HYPERLIQUID_PRIVATE_KEY")
        
        # Initialize SDK
        api_url = "https://api.hyperliquid-testnet.xyz" if self.testnet else "https://api.hyperliquid.xyz"
        
        try:
            # Create wallet from private key
            wallet = eth_account.Account.from_key(self.private_key)
            
            # Initialize Exchange (for trading) and Info (for data)
            self.exchange = Exchange(wallet, api_url, account_address=self.wallet_address)
            self.info = Info(api_url)
            
            info(f"✅ Hyperliquid Exchange initialized ({'testnet' if self.testnet else 'mainnet'})")
            info(f"📊 Wallet: {self.wallet_address[:10]}...{self.wallet_address[-6:]}")
            
        except Exception as e:
            error(f"Failed to initialize Hyperliquid Exchange: {e}")
            raise
    
    def get_account_balance(self) -> Optional[Dict[str, float]]:
        """
        Get Hyperliquid account balance and equity
        
        Returns:
            Dict with:
            - total_equity: Total account value (balance + unrealized PnL)
            - available_balance: Free collateral available for trading
            - margin_used: Margin currently used by open positions
            - unrealized_pnl: Unrealized profit/loss from open positions
        """
        try:
            user_state = self.info.user_state(self.wallet_address)
            
            if user_state and 'marginSummary' in user_state:
                margin = user_state['marginSummary']
                return {
                    'total_equity': float(margin.get('accountValue', 0)),
                    'available_balance': float(margin.get('freeCollateral', 0)),
                    'margin_used': float(margin.get('totalMarginUsed', 0)),
                    'unrealized_pnl': float(margin.get('totalUnrealizedPnl', 0))
                }
            
            warning("No margin summary in user state response")
            return None
            
        except Exception as e:
            error(f"Error getting Hyperliquid account balance: {e}")
            return None
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open perpetual positions
        
        Returns:
            List of position dicts with:
            - symbol: Token symbol (e.g., 'BTC', 'ETH')
            - size: Position size (positive = long, negative = short)
            - entry_price: Average entry price
            - unrealized_pnl: Current unrealized PnL
            - leverage: Leverage used
            - liquidation_price: Estimated liquidation price
        """
        try:
            user_state = self.info.user_state(self.wallet_address)
            
            if user_state and 'assetPositions' in user_state:
                positions = []
                for pos_data in user_state['assetPositions']:
                    pos = pos_data['position']
                    positions.append({
                        'symbol': pos['coin'],
                        'size': float(pos['szi']),  # Positive = long, negative = short
                        'entry_price': float(pos['entryPx']),
                        'unrealized_pnl': float(pos['unrealizedPnl']),
                        'leverage': float(pos['leverage']['value']) if isinstance(pos['leverage'], dict) else float(pos['leverage']),
                        'liquidation_price': float(pos.get('liquidationPx', 0))
                    })
                return positions
            
            return []
            
        except Exception as e:
            error(f"Error getting Hyperliquid positions: {e}")
            return []
    
    def place_order(self, symbol: str, side: str, size_usd: float, 
                   leverage: int = 5, order_type: str = "market") -> Dict[str, Any]:
        """
        Place a perpetual order on Hyperliquid
        
        Args:
            symbol: Token symbol (BTC, ETH, SOL, etc.) - without 'PERP' suffix
            side: 'A' or 'buy' for long, 'B' or 'sell' for short
            size_usd: Position size in USD
            leverage: Leverage multiplier (1-50)
            order_type: 'market' or 'limit'
        
        Returns:
            Dict with success status and order details
        """
        try:
            # Normalize side
            if side.upper() in ['A', 'BUY', 'LONG']:
                is_buy = True
            elif side.upper() in ['B', 'SELL', 'SHORT']:
                is_buy = False
            else:
                return {'success': False, 'error': f'Invalid side: {side}'}
            
            # Get current price for size calculation
            mids = self.info.all_mids()
            if symbol not in mids:
                error(f"Symbol {symbol} not found in Hyperliquid universe")
                return {'success': False, 'error': 'Symbol not found'}
            
            price = float(mids[symbol])
            size_base = size_usd / price
            
            # Set leverage first (required before placing order)
            try:
                self.exchange.update_leverage(leverage, symbol, False)  # False = isolated margin
                debug(f"Set leverage to {leverage}x for {symbol}")
            except Exception as e:
                warning(f"Failed to set leverage (may already be set): {e}")
            
            # Place order based on type
            if order_type == "market":
                result = self.exchange.market_open(symbol, is_buy, size_base)
            else:
                # Limit order
                result = self.exchange.order(
                    symbol=symbol,
                    is_buy=is_buy,
                    sz=size_base,
                    limit_px=price,
                    order_type={"limit": {"tif": "Ioc"}},  # Immediate or Cancel
                    reduce_only=False
                )
            
            # Check result
            if result.get('status') == 'ok':
                info(f"✅ Hyperliquid order placed: {symbol} {'LONG' if is_buy else 'SHORT'} ${size_usd:.2f} @ {leverage}x")
                return {
                    'success': True,
                    'symbol': symbol,
                    'side': 'A' if is_buy else 'B',
                    'size_usd': size_usd,
                    'leverage': leverage,
                    'order_id': result.get('response', {}).get('data', {}).get('statuses', [{}])[0].get('resting', {}).get('oid')
                }
            else:
                error_msg = result.get('response', {}).get('error', 'Unknown error')
                error(f"❌ Hyperliquid order failed: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            error(f"Error placing Hyperliquid order: {e}")
            import traceback
            error(traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    def close_position(self, symbol: str, percentage: float = 100.0) -> Dict[str, Any]:
        """
        Close a position (partial or full)
        
        Args:
            symbol: Token symbol
            percentage: Percentage to close (0-100)
        
        Returns:
            Dict with success status
        """
        try:
            positions = self.get_positions()
            position = next((p for p in positions if p['symbol'] == symbol), None)
            
            if not position:
                return {'success': False, 'error': 'No position found'}
            
            close_size = abs(position['size']) * (percentage / 100.0)
            is_long = position['size'] > 0
            
            # Close opposite side
            result = self.exchange.market_close(symbol, is_long, close_size)
            
            if result.get('status') == 'ok':
                info(f"✅ Closed {percentage}% of {symbol} position")
                return {'success': True, 'symbol': symbol, 'percentage': percentage}
            else:
                error_msg = result.get('response', {}).get('error', 'Unknown error')
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            error(f"Error closing position: {e}")
            return {'success': False, 'error': str(e)}
    
    def update_leverage(self, symbol: str, leverage: int, cross_margin: bool = False) -> bool:
        """
        Update leverage for a symbol
        
        Args:
            symbol: Token symbol
            leverage: Leverage multiplier (1-50)
            cross_margin: True for cross-margin, False for isolated
        
        Returns:
            True if successful
        """
        try:
            self.exchange.update_leverage(leverage, symbol, cross_margin)
            info(f"✅ Updated leverage for {symbol} to {leverage}x ({'cross' if cross_margin else 'isolated'} margin)")
            return True
        except Exception as e:
            error(f"Error updating leverage: {e}")
            return False
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current position for a specific symbol
        
        Args:
            symbol: Token symbol
        
        Returns:
            Position dict or None if no position
        """
        positions = self.get_positions()
        return next((p for p in positions if p['symbol'] == symbol), None)


# Global singleton instance
_hyperliquid_exchange = None

def get_hyperliquid_exchange() -> Optional[HyperliquidExchange]:
    """Get singleton instance of Hyperliquid exchange"""
    global _hyperliquid_exchange
    if _hyperliquid_exchange is None:
        try:
            _hyperliquid_exchange = HyperliquidExchange()
        except Exception as e:
            error(f"Failed to create Hyperliquid exchange instance: {e}")
            return None
    return _hyperliquid_exchange
