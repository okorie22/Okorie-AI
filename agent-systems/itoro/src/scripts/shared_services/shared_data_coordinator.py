"""
🌙 Anarcho Capital's Shared Data Coordinator
Simplified version for swing trading - coordinates data sharing between agents
Built with love by Anarcho Capital 🚀
"""

import threading
import time
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime, timedelta
import json
import os
from dataclasses import dataclass, field
from enum import Enum
# Local imports with fallback for relative imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
    from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
    from src import config
except ImportError:
    # Keep fallback absolute to 'src.' to avoid bare 'scripts' in production
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
    from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
    import src.config as config

class AgentType(Enum):
    """Types of agents in the system"""
    RISK = "risk"
    COPYBOT = "copybot"
    REBALANCING = "rebalancing"
    HARVESTING = "harvesting"
    STAKING = "staking"  # NEW: Added staking agent type
    DEFI = "defi"  # NEW: Added DeFi agent type

@dataclass
class WalletData:
    """Data class for wallet information"""
    address: str
    tokens: Dict[str, float] = field(default_factory=dict)  # token_address -> balance
    total_value_usd: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class TokenData:
    """Data class for token information"""
    address: str
    symbol: str = "UNK"
    name: str = "Unknown Token"
    decimals: int = 9
    price_usd: Optional[float] = None
    last_price_update: datetime = field(default_factory=datetime.now)

class SharedDataCoordinator:
    """
    Simplified data coordinator for swing trading system
    Manages shared wallet data, token metadata, and price information
    """
    
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
        """Initialize the shared data coordinator"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Get shared services
        self.api_manager = get_shared_api_manager()
        self.price_service = get_optimized_price_service()
        
        # Data caches
        self.wallet_cache: Dict[str, WalletData] = {}
        self.token_cache: Dict[str, TokenData] = {}
        self.staking_cache: Dict[str, Dict] = {}  # NEW: Staking data cache
        
        # Thread safety
        self.wallet_cache_lock = threading.RLock()
        self.token_cache_lock = threading.RLock()
        self.staking_cache_lock = threading.RLock()  # NEW: Staking cache lock
        
        # Agent registration tracking
        self.registered_agents: Dict[AgentType, List[str]] = {
            AgentType.RISK: [],
            AgentType.COPYBOT: [],
            AgentType.REBALANCING: [],
            AgentType.HARVESTING: [],
            AgentType.STAKING: [],
            AgentType.DEFI: []  # NEW: Added DeFi agent tracking
        }
        self.agent_registration_lock = threading.RLock()
        
        # Cache expiration settings
        self.wallet_cache_expiry = timedelta(minutes=5)  # Wallet data expires after 5 minutes
        self.token_cache_expiry = timedelta(minutes=30)  # Token metadata expires after 30 minutes
        self.staking_cache_expiry = timedelta(minutes=10)  # NEW: Staking data expires after 10 minutes
        
        info("SharedDataCoordinator initialized successfully")
    
    def register_agent(self, agent_type: AgentType, agent_id: str):
        """
        Register an agent with the data coordinator
        
        Args:
            agent_type: Type of agent (RISK, COPYBOT, REBALANCING)
            agent_id: Unique identifier for the agent
        """
        with self.agent_registration_lock:
            if agent_id not in self.registered_agents[agent_type]:
                self.registered_agents[agent_type].append(agent_id)
                debug(f"Registered {agent_type.value} agent: {agent_id}")
            else:
                debug(f"Agent {agent_id} already registered as {agent_type.value}")
    
    def unregister_agent(self, agent_type: AgentType, agent_id: str):
        """
        Unregister an agent from the data coordinator
        
        Args:
            agent_type: Type of agent (RISK, COPYBOT, REBALANCING)
            agent_id: Unique identifier for the agent
        """
        with self.agent_registration_lock:
            if agent_id in self.registered_agents[agent_type]:
                self.registered_agents[agent_type].remove(agent_id)
                debug(f"Unregistered {agent_type.value} agent: {agent_id}")
            else:
                debug(f"Agent {agent_id} not found in {agent_type.value} registrations")
    
    def get_registered_agents(self, agent_type: AgentType) -> List[str]:
        """
        Get list of registered agents of a specific type
        
        Args:
            agent_type: Type of agent to get
            
        Returns:
            List of agent IDs
        """
        with self.agent_registration_lock:
            return self.registered_agents[agent_type].copy()
    
    def get_wallet_data(self, wallet_address: str, callback: Optional[Callable] = None) -> Optional[WalletData]:
        """
        Get wallet data with caching
        
        Args:
            wallet_address: The wallet address to get data for
            callback: Optional callback function to call when data is ready
            
        Returns:
            WalletData object or None if not available
        """
        with self.wallet_cache_lock:
            # Check cache first
            if wallet_address in self.wallet_cache:
                cached_data = self.wallet_cache[wallet_address]
                if datetime.now() - cached_data.last_updated < self.wallet_cache_expiry:
                    debug(f"Returning cached wallet data for {wallet_address[:8]}...")
                    if callback:
                        callback(cached_data)
                    return cached_data
            
            # Fetch fresh data with retry logic
            debug(f"Fetching fresh wallet data for {wallet_address[:8]}...")
            max_retries = 3
            for attempt in range(max_retries):
                wallet_data = self._fetch_wallet_data(wallet_address)
                if wallet_data is not None:
                    break
                elif attempt < max_retries - 1:
                    warning(f"Wallet data fetch attempt {attempt + 1} failed for {wallet_address[:8]}..., retrying...")
                    time.sleep(1)  # Brief delay before retry
            
            if wallet_data:
                self.wallet_cache[wallet_address] = wallet_data
                if callback:
                    callback(wallet_data)
                return wallet_data
            
            return None
    
    def _fetch_wallet_data(self, wallet_address: str) -> Optional[WalletData]:
        """
        Fetch wallet data from API
        
        Args:
            wallet_address: The wallet address to fetch data for
            
        Returns:
            WalletData object or None if fetch failed
        """
        try:
            # Build wallet data
            wallet_data = WalletData(address=wallet_address)
            total_value = 0.0
            
            # 1. Fetch native SOL balance
            sol_balance = self._fetch_sol_balance(wallet_address)
            if sol_balance > 0:
                wallet_data.tokens["So11111111111111111111111111111111111111112"] = sol_balance
                sol_price = self.price_service.get_price("So11111111111111111111111111111111111111112")
                if sol_price:
                    total_value += sol_balance * sol_price
                    debug(f"SOL balance: {sol_balance:.6f} (${sol_balance * sol_price:.2f})")
            
            # 2. Fetch token accounts
            token_accounts = self.api_manager.get_wallet_token_accounts(wallet_address)
            if token_accounts is None:
                error(f"Failed to fetch token accounts for wallet {wallet_address[:8]}...")
                return None
            elif len(token_accounts) == 0:
                debug(f"No token accounts found for wallet {wallet_address[:8]}...", file_only=True)
            else:
                for token_account in token_accounts:
                    token_address = token_account.get('mint')
                    balance = token_account.get('amount', 0)
                    
                    if token_address and balance > 0:
                        wallet_data.tokens[token_address] = balance
                        
                        # Get price and add to total value
                        token_price = self.price_service.get_price(token_address)
                        if token_price:
                            token_value = balance * token_price
                            total_value += token_value
                            debug(f"Token {token_address[:8]}...: {balance} (${token_value:.2f})")
            
            wallet_data.total_value_usd = total_value
            wallet_data.last_updated = datetime.now()
            
            # Quiet success log to keep main.py output clean
            debug(f"Successfully fetched wallet data for {wallet_address[:8]}... (${total_value:.2f})", file_only=True)
            return wallet_data
            
        except Exception as e:
            error(f"Error fetching wallet data for {wallet_address[:8]}...: {str(e)}")
            return None
    
    def _fetch_sol_balance(self, wallet_address: str) -> float:
        """Fetch native SOL balance for a wallet using hybrid RPC strategy"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "anarcho-capital-sol-balance",
                "method": "getBalance",
                "params": [wallet_address]
            }
            
            # Use hybrid RPC strategy - pass wallet_address
            result = self.api_manager.make_rpc_request("getBalance", [wallet_address], wallet_address)
            
            if result and 'result' in result and 'value' in result['result']:
                balance_lamports = result['result']['value']
                balance_sol = balance_lamports / 1_000_000_000  # Convert lamports to SOL
                debug(f"SOL balance for {wallet_address[:8]}...: {balance_sol:.6f} SOL")
                return balance_sol
            else:
                debug(f"Failed to fetch SOL balance for {wallet_address[:8]}...")
                return 0.0
                
        except Exception as e:
            error(f"Error fetching SOL balance for {wallet_address[:8]}...: {str(e)}")
            return 0.0
    
    def get_personal_wallet_data(self, callback: Optional[Callable] = None) -> Optional[WalletData]:
        """
        Get personal wallet data using the default wallet address
        
        Args:
            callback: Optional callback function to call when data is ready
            
        Returns:
            WalletData object or None if not available
        """
        personal_wallet = config.address
        if not personal_wallet:
            error("Personal wallet address not configured in DEFAULT_WALLET_ADDRESS")
            return None
            
        # Validate wallet address format
        if len(personal_wallet) < 32:
            error(f"Personal wallet address too short: {len(personal_wallet)} characters")
            return None
            
        debug(f"Fetching personal wallet data for {personal_wallet[:8]}...", file_only=True)
        return self.get_wallet_data(personal_wallet, callback)
    
    def get_token_data(self, token_address: str, callback: Optional[Callable] = None) -> Optional[TokenData]:
        """
        Get token metadata with caching
        
        Args:
            token_address: The token address to get metadata for
            callback: Optional callback function to call when data is ready
            
        Returns:
            TokenData object or None if not available
        """
        with self.token_cache_lock:
            # Check cache first
            if token_address in self.token_cache:
                cached_data = self.token_cache[token_address]
                if datetime.now() - cached_data.last_price_update < self.token_cache_expiry:
                    debug(f"Returning cached token data for {token_address[:8]}...")
                    if callback:
                        callback(cached_data)
                    return cached_data
            
            # Fetch fresh data
            debug(f"Fetching fresh token data for {token_address[:8]}...")
            token_data = self._fetch_token_data(token_address)
            
            if token_data:
                self.token_cache[token_address] = token_data
                if callback:
                    callback(token_data)
                return token_data
            
            return None
    
    def _fetch_token_data(self, token_address: str) -> Optional[TokenData]:
        """
        Fetch token metadata from API
        
        Args:
            token_address: The token address to fetch metadata for
            
        Returns:
            TokenData object or None if fetch failed
        """
        try:
            from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
            
            metadata_service = get_token_metadata_service()
            metadata = metadata_service.get_token_metadata(token_address)
            
            if metadata:
                token_data = TokenData(
                    address=token_address,
                    symbol=metadata.get('symbol', 'UNK'),
                    name=metadata.get('name', 'Unknown Token'),
                    decimals=metadata.get('decimals', 9)
                )
                
                # Get current price
                price = self.price_service.get_price(token_address)
                if price:
                    token_data.price_usd = price
                    token_data.last_price_update = datetime.now()
                
                debug(f"Successfully fetched token data for {token_data.symbol} ({token_address[:8]}...)")
                return token_data
            
            return None
            
        except Exception as e:
            error(f"Error fetching token data for {token_address[:8]}...: {str(e)}")
            return None
    
    def get_personal_wallet_balance(self, callback: Optional[Callable] = None) -> Optional[float]:
        """
        Get personal wallet total balance in USD
        
        Args:
            callback: Optional callback function to call when data is ready
            
        Returns:
            Total wallet balance in USD or None if not available
        """
        def wallet_callback(wallet_data: WalletData):
            if callback:
                callback(wallet_data.total_value_usd)
        
        wallet_data = self.get_personal_wallet_data(wallet_callback)
        return wallet_data.total_value_usd if wallet_data else None
    
    def get_personal_wallet_tokens(self, callback: Optional[Callable] = None) -> Optional[Dict[str, float]]:
        """
        Get personal wallet token balances
        
        Args:
            callback: Optional callback function to call when data is ready
            
        Returns:
            Dictionary of token_address -> balance or None if not available
        """
        def wallet_callback(wallet_data: WalletData):
            if callback:
                callback(wallet_data.tokens)
        
        wallet_data = self.get_personal_wallet_data(wallet_callback)
        return wallet_data.tokens if wallet_data else None
    
    def batch_get_token_prices(self, token_addresses: List[str], callback: Optional[Callable] = None) -> Optional[Dict[str, float]]:
        """
        Get prices for multiple tokens efficiently
        
        Args:
            token_addresses: List of token addresses to get prices for
            callback: Optional callback function to call when data is ready
            
        Returns:
            Dictionary of token_address -> price or None if not available
        """
        try:
            prices = {}
            for token_address in token_addresses:
                price = self.price_service.get_price(token_address)
                if price:
                    prices[token_address] = price
            
            if callback:
                callback(prices)
            
            return prices
            
        except Exception as e:
            error(f"Error batch fetching token prices: {str(e)}")
            return None
    
    def invalidate_wallet_cache(self, wallet_address: str):
        """
        Invalidate wallet cache entry
        
        Args:
            wallet_address: The wallet address to invalidate
        """
        with self.wallet_cache_lock:
            if wallet_address in self.wallet_cache:
                del self.wallet_cache[wallet_address]
                debug(f"Invalidated wallet cache for {wallet_address[:8]}...")
    
    def invalidate_token_cache(self, token_address: str):
        """
        Invalidate token cache entry
        
        Args:
            token_address: The token address to invalidate
        """
        with self.token_cache_lock:
            if token_address in self.token_cache:
                del self.token_cache[token_address]
                debug(f"Invalidated token cache for {token_address[:8]}...")
    
    def clear_all_caches(self):
        """Clear all caches"""
        with self.wallet_cache_lock:
            self.wallet_cache.clear()
        with self.token_cache_lock:
            self.token_cache.clear()
        info("All caches cleared")
    
    def cleanup_expired_cache_entries(self):
        """Remove expired cache entries"""
        now = datetime.now()
        
        # Clean wallet cache
        with self.wallet_cache_lock:
            expired_wallets = [
                addr for addr, data in self.wallet_cache.items()
                if now - data.last_updated > self.wallet_cache_expiry
            ]
            for addr in expired_wallets:
                del self.wallet_cache[addr]
        
        # Clean token cache
        with self.token_cache_lock:
            expired_tokens = [
                addr for addr, data in self.token_cache.items()
                if now - data.last_price_update > self.token_cache_expiry
            ]
            for addr in expired_tokens:
                del self.token_cache[addr]
        
        if expired_wallets or expired_tokens:
            debug(f"Cleaned up {len(expired_wallets)} wallet entries and {len(expired_tokens)} token entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get basic cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        with self.wallet_cache_lock:
            wallet_count = len(self.wallet_cache)
        
        with self.token_cache_lock:
            token_count = len(self.token_cache)
        
        with self.staking_cache_lock:
            staking_count = len(self.staking_cache)
        
        return {
            'wallet_cache_size': wallet_count,
            'token_cache_size': token_count,
            'staking_cache_size': staking_count,
            'last_cleanup': datetime.now()
        }
    
    # NEW: Optimized Staking Data Methods
    def get_staking_data(self, cache_key: str = "default", callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """
        Get staking data with caching for performance
        
        Args:
            cache_key: Cache key for staking data
            callback: Optional callback function
            
        Returns:
            Staking data dictionary or None if not available
        """
        with self.staking_cache_lock:
            # Check cache first
            if cache_key in self.staking_cache:
                cached_data = self.staking_cache[cache_key]
                if datetime.now() - cached_data.get("last_updated", datetime.min) < self.staking_cache_expiry:
                    debug(f"Returning cached staking data for {cache_key}")
                    if callback:
                        callback(cached_data.get("data", {}))
                    return cached_data.get("data", {})
            
            # Fetch fresh data using optimized API manager
            debug(f"Fetching fresh staking data for {cache_key}")
            staking_data = self.api_manager.get_staking_apy_data()
            
            if staking_data:
                # Cache the data
                self.staking_cache[cache_key] = {
                    "data": staking_data,
                    "last_updated": datetime.now()
                }
                
                if callback:
                    callback(staking_data)
                
                return staking_data
            
            return None
    
    def get_staking_balance(self, wallet_address: str, protocol: str, callback: Optional[Callable] = None) -> Optional[Dict[str, float]]:
        """
        Get staking balance for a specific protocol with caching
        
        Args:
            wallet_address: Wallet address to check
            protocol: Staking protocol name
            callback: Optional callback function
            
        Returns:
            Dictionary with staked amount and rewards
        """
        cache_key = f"balance_{wallet_address}_{protocol}"
        
        with self.staking_cache_lock:
            # Check cache first
            if cache_key in self.staking_cache:
                cached_data = self.staking_cache[cache_key]
                if datetime.now() - cached_data.get("last_updated", datetime.min) < self.staking_cache_expiry:
                    debug(f"Returning cached staking balance for {wallet_address[:8]}... on {protocol}")
                    if callback:
                        callback(cached_data.get("data", {}))
                    return cached_data.get("data", {})
            
            # Fetch fresh data
            debug(f"Fetching fresh staking balance for {wallet_address[:8]}... on {protocol}")
            balance_data = self.api_manager.get_staking_balance(wallet_address, protocol)
            
            if balance_data:
                # Cache the data
                self.staking_cache[cache_key] = {
                    "data": balance_data,
                    "last_updated": datetime.now()
                }
                
                if callback:
                    callback(balance_data)
                
                return balance_data
            
            return None
    
    def invalidate_staking_cache(self, cache_key: str = None):
        """
        Invalidate staking cache entries
        
        Args:
            cache_key: Specific cache key to invalidate, or None for all
        """
        with self.staking_cache_lock:
            if cache_key:
                if cache_key in self.staking_cache:
                    del self.staking_cache[cache_key]
                    debug(f"Invalidated staking cache for key: {cache_key}")
            else:
                self.staking_cache.clear()
                debug("Invalidated all staking cache entries")
    
    def cleanup_expired_staking_cache(self):
        """Clean up expired staking cache entries"""
        with self.staking_cache_lock:
            current_time = datetime.now()
            expired_keys = []
            
            for key, data in self.staking_cache.items():
                if current_time - data.get("last_updated", datetime.min) > self.staking_cache_expiry:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.staking_cache[key]
            
            if expired_keys:
                debug(f"Cleaned up {len(expired_keys)} expired staking cache entries")
    
    def shutdown(self):
        """Graceful shutdown"""
        info("SharedDataCoordinator shutting down...")
        self.clear_all_caches()


def get_shared_data_coordinator() -> SharedDataCoordinator:
    """
    Get the shared data coordinator instance
    
    Returns:
        SharedDataCoordinator instance
    """
    return SharedDataCoordinator()


# Example usage
if __name__ == "__main__":
    coordinator = get_shared_data_coordinator()
    
    # Test wallet data fetching
    wallet_data = coordinator.get_personal_wallet_data()
    if wallet_data:
        print(f"Wallet balance: ${wallet_data.total_value_usd:.2f}")
        print(f"Token count: {len(wallet_data.tokens)}")
    
    # Test token data fetching
    sol_address = "So11111111111111111111111111111111111111112"
    token_data = coordinator.get_token_data(sol_address)
    if token_data:
        print(f"Token: {token_data.symbol} - ${token_data.price_usd:.2f}")
    
    # Cleanup
    coordinator.shutdown() 
