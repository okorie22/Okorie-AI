"""
🚀 Optimized Price Service for Anarcho Capital
Efficient price fetching with lazy loading and QuickNode integration
"""

import threading
import time
import requests
import os
from typing import Dict, Optional, List, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
# Local imports - use app-internal paths
from scripts.shared_services.logger import debug, info, warning, error
import config
from nice_funcs import get_birdeye_api_key

def get_birdeye_api_key_optimized():
    """Get BIRDEYE_API_KEY with proper error handling for price service"""
    api_key = get_birdeye_api_key()
    if not api_key:
        warning("BIRDEYE_API_KEY not found in environment variables!")
    return api_key

@dataclass
class PriceData:
    """Optimized price data structure"""
    price: float
    timestamp: datetime
    source: str
    token_address: str
    cache_tier: str  # active_trades, recent_activity, monitored, background
    fetch_time_ms: int  # How long the fetch took in milliseconds

@dataclass
class PriceResult:
    """Enhanced price result with error handling information"""
    price: Optional[float]
    success: bool
    error_message: Optional[str] = None
    retry_after: Optional[int] = None  # Seconds to wait before retry
    force_sell_eligible: bool = False  # Whether this token can be force sold by risk agent

@dataclass
class PriceValidation:
    """Price validation result"""
    is_valid: bool
    reason: str
    price: Optional[float] = None
    sources_used: List[str] = None
    cache_age_seconds: Optional[int] = None
    consensus_deviation: Optional[float] = None
    
    def __post_init__(self):
        if self.sources_used is None:
            self.sources_used = []

class OptimizedPriceService:
    """
    Ultra-efficient price service using lazy loading and QuickNode APIs
    Only fetches prices when actually needed for trading decisions
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
        """Initialize the optimized price service"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Initialize monitoring_active early to prevent AttributeError
        self.monitoring_active = True
        
        # Smart cache with tiered expiration
        self.price_cache: Dict[str, PriceData] = {}
        self.cache_lock = threading.RLock()
        
        # Cache expiration times (in seconds) - driven by config
        base_interval = getattr(config, 'PRICE_MONITOR_INTERVAL_SECONDS', 300)  # Updated fallback to match config default (5 min)
        self.cache_expiry = {
            'active_trades': getattr(config, 'PRICE_CACHE_ACTIVE_SECONDS', base_interval),
            'recent_activity': getattr(config, 'PRICE_CACHE_RECENT_SECONDS', base_interval * 2),
            'monitored': getattr(config, 'PRICE_CACHE_MONITORED_SECONDS', max(base_interval * 6, 1800)),  # Updated fallback to match config (30 min)
            'background': getattr(config, 'PRICE_CACHE_BACKGROUND_SECONDS', 3600)  # Updated fallback to match config default (60 min)
        }
        
        # Track active trading tokens (tokens in your portfolio)
        self.active_trading_tokens: Set[str] = set()
        self.recent_activity_tokens: Set[str] = set()
        
        # QuickNode API endpoints
        self.quicknode_rpc = getattr(config, 'QUICKNODE_RPC_ENDPOINT', None)
        self.quicknode_wss = getattr(config, 'QUICKNODE_WSS_ENDPOINT', None)
        
        # Price fetching mode (birdeye or jupiter)
        self.price_mode = getattr(config, 'PRICE_SOURCE_MODE', 'birdeye')
        
        # Performance tracking
        self.cache_hits = 0
        self.cache_misses = 0
        self.failed_fetches = {}  # Track failed price fetches
        
        # CRITICAL: Price validation settings to prevent $121 SOL disasters
        self.max_cache_age = {
            'SOL': 60,   # 1 minute max for SOL (optimized for trading)
            'default': 60  # 1 minute for other tokens
        }
        
        # Initialize missing attributes first
        self._validation_timestamps = {}
        self.retry_delay_seconds = 60
        self.max_retry_attempts = 3
        self.consensus_tolerance = 0.15  # 15% max deviation between sources
        self.min_sources_for_consensus = 2
        
        # Sanity bounds for well-known assets (prevents obviously wrong prices)
        self.sanity_bounds = {
            'So11111111111111111111111111111111111111112': (50.0, 500.0),  # SOL: $50-$500
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': (0.95, 1.05),  # USDC: $0.95-$1.05
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': (0.95, 1.05),  # USDT: $0.95-$1.05
        }
        
        # Circuit breaker for Jupiter API
        self.jupiter_circuit_breaker = {
            'failures': 0,
            'last_failure_time': 0,
            'failure_threshold': 3,
            'failure_window': 30,  # 30 seconds
            'open_duration': 90,   # 90 seconds
            'is_open': False
        }
        self.api_calls = 0
        self.avg_fetch_time_ms = 0
        
        # Error tracking for retry logic
        self.failed_fetches: Dict[str, Tuple[datetime, int]] = {}  # token -> (last_fail_time, fail_count)
        
        # CU tracking and adaptive throttling
        self.cu_tracker = {
            'daily_calls': 0,
            'hourly_calls': 0,
            'last_daily_reset': datetime.now().date(),
            'last_hourly_reset': datetime.now().hour,
            'throttle_active': False,
            'original_interval': getattr(config, 'PRICE_MONITOR_INTERVAL_SECONDS', 300)  # Updated fallback to match config default (5 min)
        }
        self.cu_daily_limit = getattr(config, 'CU_DAILY_LIMIT', 100000)  # Updated fallback to match config default
        self.cu_warning_threshold = getattr(config, 'CU_WARNING_THRESHOLD', 90000)  # Updated fallback to match config default
        self.cu_circuit_breaker_enabled = getattr(config, 'CU_CIRCUIT_BREAKER_ENABLED', True)
        self.cu_throttle_interval = getattr(config, 'PRICE_THROTTLED_INTERVAL_SECONDS', 1200)  # Updated fallback to match config default (20 min)
        
        # Background monitoring thread - ENABLED with smart batch fetching
        self.monitoring_active = True  # Enabled - uses batch fetching for efficiency
        self.monitoring_thread = threading.Thread(target=self._monitor_active_tokens, daemon=True)
        self.monitoring_thread.start()
        
        # Log to file only (not console)
        info(f"🚀 Optimized Price Service initialized with {self.price_mode.upper()} mode", file_only=True)
        info(f"💡 Background monitoring ENABLED - batch fetches all active tokens every {self.cu_tracker['original_interval']}s", file_only=True)
    
    def _get_price_sanity_bounds(self, token_address: str) -> tuple:
        """Get realistic price bounds for token validation"""
        # Known tokens with higher prices
        if token_address == 'So11111111111111111111111111111111111111112':
            return (50.0, 500.0)  # SOL
        elif token_address in ['EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 
                                'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB']:
            return (0.95, 1.05)  # Stablecoins
        else:
            # All other tokens: most altcoins are under $100
            return (0.0000001, 100.0)
    
    def get_price(self, token_address: str, force_fetch: bool = False, priority: str = 'normal', 
                  agent_type: str = 'general') -> Optional[float]:
        """
        Get price with lazy loading - only fetch if needed
        
        Args:
            token_address: Token mint address
            force_fetch: Force fetch even if cached
            priority: 'high' for immediate trading, 'normal' for analysis
            agent_type: 'risk', 'copybot', 'general' - affects error handling strategy
        """
        if not token_address:
            return None
            
        # Check cache first (unless force fetch)
        if not force_fetch:
            cached_price = self._get_cached_price(token_address)
            if cached_price is not None:
                self.cache_hits += 1
                debug(f"💾 Using cached price for {token_address[:8]}...: ${cached_price:.6f}")
                return cached_price
        
        # Fetch price if needed
        self.cache_misses += 1
        start_time = time.time()
        
        try:
            price_result = self._fetch_price_with_error_handling(token_address, agent_type)
            
            if price_result.success and price_result.price is not None:
                fetch_time_ms = int((time.time() - start_time) * 1000)
                cache_tier = self._determine_cache_tier(token_address, priority)
                self._cache_price(token_address, price_result.price, cache_tier, fetch_time_ms)
                debug(f"🔄 Fresh price fetched for {token_address[:8]}...: ${price_result.price:.6f} (tier={cache_tier})")
                return price_result.price
            else:
                # Handle failed price fetch based on agent type
                self._handle_price_fetch_failure(token_address, price_result, agent_type)
                return None
                
        except Exception as e:
            error(f"Error fetching price for {token_address}: {str(e)}")
            return None

    def get_price_with_force_sell_info(self, token_address: str, agent_type: str = 'risk') -> PriceResult:
        """
        Get price with additional information for risk agent force selling
        
        Args:
            token_address: Token mint address
            agent_type: 'risk' for risk agent, 'copybot' for copybot agent
            
        Returns:
            PriceResult with price, success status, and force sell eligibility
        """
        if not token_address:
            return PriceResult(price=None, success=False, error_message="Invalid token address")
        
        # Check if this is a stablecoin (always return $1)
        if self._is_stablecoin(token_address):
            return PriceResult(price=1.0, success=True, force_sell_eligible=False)
        
        # Check cache first
        cached_price = self._get_cached_price(token_address)
        if cached_price is not None:
            self.cache_hits += 1
            return PriceResult(price=cached_price, success=True, force_sell_eligible=False)
        
        # Fetch price with error handling
        self.cache_misses += 1
        try:
            price_result = self._fetch_price_with_error_handling(token_address, agent_type)
            
            if price_result.success and price_result.price is not None:
                # Cache successful price
                cache_tier = self._determine_cache_tier(token_address, 'high')
                self._cache_price(token_address, price_result.price, cache_tier, 0)
            
            return price_result
            
        except Exception as e:
            error(f"Error in get_price_with_force_sell_info for {token_address}: {str(e)}")
            return PriceResult(
                price=None, 
                success=False, 
                error_message=str(e),
                force_sell_eligible=self._is_force_sell_eligible(token_address, agent_type)
            )

    def get_prices(self, token_addresses: List[str], force_fetch: bool = False, priority: str = 'normal',
                   agent_type: str = 'general') -> Dict[str, Optional[float]]:
        """
        Get prices for multiple tokens efficiently
        
        Args:
            token_addresses: List of token mint addresses
            force_fetch: Force fetch even if cached
            priority: 'high' for immediate trading, 'normal' for analysis
            agent_type: 'risk', 'copybot', 'general' - affects error handling strategy
            
        Returns:
            Dictionary mapping token addresses to prices
        """
        if not token_addresses:
            return {}
        
        results = {}
        
        # Check cache first for all tokens
        tokens_to_fetch = []
        for token_address in token_addresses:
            if not token_address:
                results[token_address] = None
                continue
                
            if not force_fetch:
                cached_price = self._get_cached_price(token_address)
                if cached_price is not None:
                    results[token_address] = cached_price
                    self.cache_hits += 1
                    continue
            
            tokens_to_fetch.append(token_address)
            results[token_address] = None  # Placeholder
        
        # Fetch prices for tokens not in cache
        if tokens_to_fetch:
            # Try Birdeye batch first if in birdeye mode and batch is enabled
            if self.price_mode == 'birdeye' and getattr(config, 'BIRDEYE_BATCH_ENABLED', True) and len(tokens_to_fetch) > 1:
                try:
                    batch_prices = self._fetch_birdeye_prices_batch(tokens_to_fetch)
                    if batch_prices:
                        remaining = []
                        for token_address in tokens_to_fetch:
                            price = batch_prices.get(token_address)
                            if price is not None:
                                # Cache and set result
                                cache_tier = self._determine_cache_tier(token_address, priority)
                                self._cache_price(token_address, price, cache_tier, 0)
                                results[token_address] = price
                            else:
                                remaining.append(token_address)
                        tokens_to_fetch = remaining
                except Exception as e:
                    debug(f"Birdeye batch path failed, falling back to per-token: {str(e)}", file_only=True)

            self.cache_misses += len(tokens_to_fetch)
            
            # Process in batches to avoid overwhelming APIs
            batch_size = 10
            for i in range(0, len(tokens_to_fetch), batch_size):
                batch = tokens_to_fetch[i:i + batch_size]
                
                for token_address in batch:
                    try:
                        start_time = time.time()
                        price_result = self._fetch_price_with_error_handling(token_address, agent_type)
                        
                        if price_result.success and price_result.price is not None:
                            fetch_time_ms = int((time.time() - start_time) * 1000)
                            cache_tier = self._determine_cache_tier(token_address, priority)
                            self._cache_price(token_address, price_result.price, cache_tier, fetch_time_ms)
                            results[token_address] = price_result.price
                        else:
                            # Handle failed price fetch based on agent type
                            self._handle_price_fetch_failure(token_address, price_result, agent_type)
                            results[token_address] = None
                            
                    except Exception as e:
                        error(f"Error fetching price for {token_address}: {str(e)}")
                        results[token_address] = None
                
                # Small delay between batches to be respectful to APIs
                if i + batch_size < len(tokens_to_fetch):
                    time.sleep(0.1)
        
        return results
    
    def _fetch_price_with_error_handling(self, token_address: str, agent_type: str) -> PriceResult:
        """
        Fetch price with comprehensive error handling and retry logic
        
        Args:
            token_address: Token mint address
            agent_type: 'risk', 'copybot', 'general'
            
        Returns:
            PriceResult with price and error handling information
        """
        # Check if this token should be skipped entirely
        if self._should_skip_token(token_address):
            return PriceResult(
                price=None, 
                success=False, 
                error_message="Token explicitly excluded from price fetching",
                force_sell_eligible=False
            )
        
        # Check retry logic
        if self._should_skip_due_to_recent_failure(token_address):
            return PriceResult(
                price=None, 
                success=False, 
                error_message="Skipping due to recent failures",
                retry_after=self._get_retry_delay(token_address),
                force_sell_eligible=self._is_force_sell_eligible(token_address, agent_type)
            )
        
        # Handle staked SOL tokens - use regular SOL price
        if token_address.startswith("STAKED_SOL_"):
            sol_address = getattr(config, 'SOL_ADDRESS', "So11111111111111111111111111111111111111112")
            sol_price = self._fetch_sol_price()
            if sol_price is not None:
                return PriceResult(price=sol_price, success=True, force_sell_eligible=False)
            else:
                return PriceResult(
                    price=None, 
                    success=False, 
                    error_message="Failed to fetch SOL price for staked SOL",
                    force_sell_eligible=False
                )
        
        # Handle stablecoins
        if self._is_stablecoin(token_address):
            return PriceResult(price=1.0, success=True, force_sell_eligible=False)
        
        # Handle SOL specially with validation
        if token_address == getattr(config, 'SOL_ADDRESS', "So11111111111111111111111111111111111111112"):
            sol_price = self._fetch_sol_price()
            if sol_price is not None:
                # CRITICAL FIX: Validate SOL price before returning
                validation = self.validate_price_for_trading(
                    token_address=token_address,
                    price=sol_price,
                    sources=[("fresh_fetch", sol_price)],
                    cache_age_seconds=0  # Fresh fetch
                )
                
                if validation.is_valid:
                    return PriceResult(price=sol_price, success=True, force_sell_eligible=False)
                else:
                    error(f"🚫 CRITICAL: Fresh SOL price ${sol_price:.4f} REJECTED by validation: {validation.reason}")
                    return PriceResult(
                        price=None, 
                        success=False, 
                        error_message=f"SOL price validation failed: {validation.reason}",
                        force_sell_eligible=False
                    )
            else:
                return PriceResult(
                    price=None, 
                    success=False, 
                    error_message="Failed to fetch SOL price",
                    force_sell_eligible=False
                )
        
        # Try to fetch price using configured method with performance optimizations
        try:
            price = self._fetch_price_fast(token_address)
            if price is not None and price > 0:
                # PERFORMANCE OPTIMIZATION: Smart validation with rate limiting
                validation_result = self._validate_price_optimized(
                    token_address=token_address,
                    price=price,
                    sources=[("fresh_fetch", price)],
                    agent_type=agent_type
                )

                if validation_result.is_valid:
                    # Clear failure tracking on success
                    self._clear_failure_tracking(token_address)
                    return PriceResult(price=price, success=True, force_sell_eligible=False)
                else:
                    warning(f"🚫 Fresh price ${price:.4f} for {token_address[:8]}... REJECTED: {validation_result.reason}")
                    self._record_failure(token_address)
                    return PriceResult(
                        price=None,
                        success=False,
                        error_message=f"Price validation failed: {validation_result.reason}",
                        retry_after=self._get_retry_delay(token_address),
                        force_sell_eligible=self._is_force_sell_eligible(token_address, agent_type)
                    )
            else:
                # Price fetch failed
                self._record_failure(token_address)
                return PriceResult(
                    price=None, 
                    success=False, 
                    error_message="Price fetch returned null or zero",
                    retry_after=self._get_retry_delay(token_address),
                    force_sell_eligible=self._is_force_sell_eligible(token_address, agent_type)
                )
                
        except Exception as e:
            # Record failure and return error result
            self._record_failure(token_address)
            return PriceResult(
                price=None, 
                success=False, 
                error_message=str(e),
                retry_after=self._get_retry_delay(token_address),
                force_sell_eligible=self._is_force_sell_eligible(token_address, agent_type)
            )
    
    def _handle_price_fetch_failure(self, token_address: str, price_result: PriceResult, agent_type: str):
        """
        Handle price fetch failure based on agent type
        
        Args:
            token_address: Token mint address
            price_result: PriceResult from failed fetch
            agent_type: 'risk', 'copybot', 'general'
        """
        if agent_type == 'copybot':
            # Copybot agent: Skip the token entirely (don't trade without price)
            debug(f"Copybot agent skipping {token_address[:8]}... due to price fetch failure: {price_result.error_message}")
            
        elif agent_type == 'risk':
            # Risk agent: Log for potential force sell consideration
            if price_result.force_sell_eligible:
                warning(f"Risk agent: {token_address[:8]}... eligible for force sell due to price fetch failure")
            else:
                debug(f"Risk agent: {token_address[:8]}... not eligible for force sell, skipping")
                
        else:
            # General case: Log the failure
            debug(f"Price fetch failed for {token_address[:8]}...: {price_result.error_message}")
    
    def _is_stablecoin(self, token_address: str) -> bool:
        """Check if token is a stablecoin"""
        stablecoins = {
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",   # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",   # USDT
            "USDrbBQwQbQ2oWHUPfA8QBHcyVxKUq1xHyXXCmgS3FQ",    # USDR
            "A9mUU4qviSctJVPJdBJWkb28deg915LYJKrzQ19ji3FM"   # USDCet
        }
        return token_address in stablecoins
    
    def _should_skip_token(self, token_address: str) -> bool:
        """Check if token should be skipped entirely"""
        # Skip tokens known to cause problems
        problematic_tokens = {
            "8UaGbxQbV9v2rXxWSSyHV6LR3p6bNH6PaUVWbUnMB9Za"
        }
        return token_address in problematic_tokens
    
    def _should_skip_due_to_recent_failure(self, token_address: str) -> bool:
        """Check if token should be skipped due to recent failures"""
        if token_address not in self.failed_fetches:
            return False
        
        last_fail_time, fail_count = self.failed_fetches[token_address]
        time_since_fail = (datetime.now() - last_fail_time).total_seconds()
        
        # Skip if we've failed too many times recently
        if fail_count >= self.max_retry_attempts:
            retry_delay = self.retry_delay_seconds * (2 ** (fail_count - self.max_retry_attempts))
            return time_since_fail < retry_delay
        
        return False
    
    def _record_failure(self, token_address: str):
        """Record a price fetch failure"""
        now = datetime.now()
        if token_address in self.failed_fetches:
            last_fail_time, fail_count = self.failed_fetches[token_address]
            # Reset count if it's been a while since last failure
            if (now - last_fail_time).total_seconds() > self.retry_delay_seconds * 2:
                fail_count = 1
            else:
                fail_count += 1
        else:
            fail_count = 1
        
        self.failed_fetches[token_address] = (now, fail_count)
        debug(f"Recorded price fetch failure for {token_address[:8]}... (count: {fail_count})")
    
    def _clear_failure_tracking(self, token_address: str):
        """Clear failure tracking for a token after successful fetch"""
        if token_address in self.failed_fetches:
            del self.failed_fetches[token_address]
            debug(f"Cleared failure tracking for {token_address[:8]}...")
    
    def _get_retry_delay(self, token_address: str) -> int:
        """Get retry delay for a token based on failure count"""
        if token_address not in self.failed_fetches:
            return 0
        
        _, fail_count = self.failed_fetches[token_address]
        if fail_count <= self.max_retry_attempts:
            return 0
        
        return self.retry_delay_seconds * (2 ** (fail_count - self.max_retry_attempts))
    
    def _is_force_sell_eligible(self, token_address: str, agent_type: str) -> bool:
        """
        Determine if a token is eligible for force sell by risk agent
        
        Args:
            token_address: Token mint address
            agent_type: 'risk', 'copybot', 'general'
            
        Returns:
            True if token can be force sold by risk agent
        """
        if agent_type != 'risk':
            return False
        
        # Risk agent can force sell any non-stablecoin token
        if self._is_stablecoin(token_address):
            return False
        
        # Don't force sell SOL (native token)
        if token_address == "So11111111111111111111111111111111111111112":
            return False
        
        # Don't force sell excluded tokens
        if token_address in getattr(config, 'EXCLUDED_TOKENS', set()):
            return False
        
        return True
    
    def _should_fetch_price(self, token_address: str, priority: str) -> bool:
        """
        Determine if we should fetch price for this token
        """
        # Always fetch for high priority requests
        if priority == 'high':
            return True
        
        # Always fetch for active trading tokens
        if token_address in self.active_trading_tokens:
            return True
        
        # Fetch for recent activity tokens
        if token_address in self.recent_activity_tokens:
            return True
        
        # Fetch for common tokens (SOL, USDC, etc.)
        if token_address in self._get_common_tokens():
            return True
        
        # Don't fetch for background tokens unless forced
        return False
    
    def _determine_cache_tier(self, token_address: str, priority: str) -> str:
        """Determine cache tier based on token importance"""
        if priority == 'high' or token_address in self.active_trading_tokens:
            tier = 'active_trades'
        elif token_address in self.recent_activity_tokens:
            tier = 'recent_activity'
        elif token_address in self._get_common_tokens():
            tier = 'monitored'
        else:
            tier = 'background'
        
        debug(f"🎯 Cache tier for {token_address[:8]}...: {tier} (priority={priority}, active_tokens={token_address in self.active_trading_tokens})")
        return tier
    
    def _fetch_price_fast(self, token_address: str) -> Optional[float]:
        """
        Fetch price using the fastest available method based on mode
        Tracks API calls for CU monitoring and adaptive throttling
        """
        # Track this API call for CU monitoring
        self._track_api_call()
        
        # For Birdeye mode: Birdeye -> QuickNode -> Jupiter
        if self.price_mode == 'birdeye':
            # Try Birdeye first (paid tier priority)
            price = self._fetch_birdeye_price(token_address)
            if price is not None:
                return price

            # Fallback to QuickNode
            if config.QUICKNODE_TOKEN_METRICS_API:
                price = self._fetch_price_quicknode(token_address)
                if price is not None:
                    return price

            # Final fallback to Jupiter
            return self._fetch_jupiter_lite_price(token_address)

        # For Jupiter mode: QuickNode -> Jupiter -> Birdeye
        else:
            # Try QuickNode first (fastest if available)
            if config.QUICKNODE_TOKEN_METRICS_API:
                price = self._fetch_price_quicknode(token_address)
                if price is not None:
                    return price

            # Use Jupiter mode
            return self._fetch_price_jupiter_mode(token_address)
    
    def _fetch_price_jupiter_mode(self, token_address: str) -> Optional[float]:
        """Jupiter mode: Jupiter Lite API -> Birdeye -> Pump.fun"""
        # Try Jupiter Lite API first (your current method)
        price = self._fetch_jupiter_lite_price(token_address)
        if price is not None:
            return price
        
        # Try Birdeye
        price = self._fetch_birdeye_price(token_address)
        if price is not None:
            return price
        
        # Try Pump.fun
        price = self._fetch_pumpfun_price(token_address)
        if price is not None:
            return price
        
        return None
    
    def _fetch_price_birdeye_mode(self, token_address: str) -> Optional[float]:
        """Birdeye mode: Birdeye -> Jupiter Lite API -> Pump.fun"""
        # Try Birdeye first
        price = self._fetch_birdeye_price(token_address)
        if price is not None:
            return price
        
        # Try Jupiter Lite API
        price = self._fetch_jupiter_lite_price(token_address)
        if price is not None:
            return price
        
        # Try Pump.fun
        price = self._fetch_pumpfun_price(token_address)
        if price is not None:
            return price
        
        return None
    
    def _get_common_tokens(self) -> Set[str]:
        """Get set of common tokens that should always have prices"""
        return {
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        }
    
    def _fetch_price_quicknode(self, token_address: str) -> Optional[float]:
        """Fetch price using QuickNode Token Metrics API (fastest)"""
        try:
            url = f"{self.quicknode_rpc}"
            payload = {
                "jsonrpc": "2.0",
                "id": "quicknode-price",
                "method": "qn_getTokenPrice",
                "params": {
                    "token": token_address
                }
            }
            
            response = requests.post(url, json=payload, timeout=3)  # Short timeout for speed
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'price' in data['result']:
                    price = float(data['result']['price'])
                    return price
            
            return None
            
        except Exception as e:
            debug(f"QuickNode price fetch failed for {token_address[:8]}...: {str(e)}")
            return None
    
    def _fetch_jupiter_lite_price(self, token_address: str) -> Optional[float]:
        """Fetch price from Jupiter Lite API (your current method)"""
        try:
            url = f"https://lite-api.jup.ag/price/v2?ids={token_address}"
            
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and token_address in data['data']:
                    price_data = data['data'][token_address]
                    if price_data and price_data.get("price"):
                        price = float(price_data["price"])
                        return price
            
            return None
            
        except Exception:
            return None
    
    def _fetch_birdeye_price(self, token_address: str) -> Optional[float]:
        """Fetch price from Birdeye (using your API key)"""
        try:
            # Lazy load API key when needed
            api_key = get_birdeye_api_key_optimized()
            if not api_key:
                return None
                
            url = "https://public-api.birdeye.so/defi/price"
            headers = {
                "X-API-KEY": api_key,
                "X-Chain": "solana",
                "accept": "application/json",
            }
            params = {"address": token_address, "chain": "solana"}
            
            response = requests.get(url, headers=headers, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("success", False):
                    price = data.get("data", {}).get("value", 0)
                    if price:
                        return float(price)
                else:
                    warning(
                        f"Birdeye returned success=false for {token_address[:8]}...: "
                        f"{data.get('message', 'no message')}"
                    )
            else:
                warning(f"Birdeye API HTTP {response.status_code} for {token_address[:8]}...")
            
            return None
            
        except requests.Timeout:
            warning(f"Birdeye price timeout for {token_address[:8]}...")
        except Exception as exc:
            warning(f"Birdeye price error for {token_address[:8]}...: {exc}")
        return None
    
    def _fetch_sol_price(self) -> Optional[float]:
        """Fetch SOL price with multi-source fallback and TTL cache - RESPECTS PRICE_SOURCE_MODE"""
        try:
            # Check cache first
            cached_price = self._get_cached_sol_price()
            if cached_price is not None:
                return cached_price
            
            prices = []
            
            # Use the same price fetching logic as other tokens, respecting PRICE_SOURCE_MODE
            if self.price_mode == 'birdeye':
                # Birdeye mode: Birdeye -> Jupiter Lite -> CoinGecko -> Pyth
                try:
                    birdeye_price = self._fetch_birdeye_price("So11111111111111111111111111111111111111112")
                    if birdeye_price and birdeye_price > 0:
                        prices.append(("birdeye", birdeye_price))
                        debug(f"✅ SOL price from Birdeye: ${birdeye_price:.2f}")
                except Exception as e:
                    debug(f"Birdeye SOL price fetch failed: {e}")
                
                # Jupiter Lite API (fallback)
                try:
                    url = "https://lite-api.jup.ag/price/v2?ids=So11111111111111111111111111111111111111112"
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if 'data' in data and "So11111111111111111111111111111111111111112" in data['data']:
                            price_data = data['data']["So11111111111111111111111111111111111111112"]
                            if price_data and price_data.get("price"):
                                jup_price = float(price_data["price"])
                                if jup_price > 0:
                                    prices.append(("jupiter", jup_price))
                except Exception as e:
                    debug(f"Jupiter price fetch failed: {e}")
            else:
                # Jupiter mode: Jupiter Lite -> Birdeye -> CoinGecko -> Pyth
                try:
                    url = "https://lite-api.jup.ag/price/v2?ids=So11111111111111111111111111111111111111112"
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if 'data' in data and "So11111111111111111111111111111111111111112" in data['data']:
                            price_data = data['data']["So11111111111111111111111111111111111111112"]
                            if price_data and price_data.get("price"):
                                jup_price = float(price_data["price"])
                                if jup_price > 0:
                                    prices.append(("jupiter", jup_price))
                except Exception as e:
                    debug(f"Jupiter price fetch failed: {e}")
                
                # Birdeye (fallback)
                try:
                    birdeye_price = self._fetch_birdeye_price("So11111111111111111111111111111111111111112")
                    if birdeye_price and birdeye_price > 0:
                        prices.append(("birdeye", birdeye_price))
                except Exception as e:
                    debug(f"Birdeye SOL price fetch failed: {e}")
            
            # CoinGecko API (fallback for both modes)
            try:
                response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    sol_price = data.get("solana", {}).get("usd", 0)
                    if sol_price and sol_price > 0:
                        prices.append(("coingecko", float(sol_price)))
            except Exception as e:
                debug(f"CoinGecko price fetch failed: {e}")
            
            # Pyth price feed (fallback)
            try:
                pyth_price = self._fetch_pyth_sol_price()
                if pyth_price is not None:
                    prices.append(("pyth", pyth_price))
            except Exception as e:
                debug(f"Pyth price fetch failed: {e}")
            
            # If no sources available, use last known good price
            if len(prices) == 0:
                warning("🚫 No SOL price sources available")
                return self._get_last_known_sol_price()
            
            # If only one source, check if it's reasonable
            if len(prices) == 1:
                source, price = prices[0]
                if 50 <= price <= 500:
                    # Only warn if it's NOT Birdeye (since Birdeye is our reliable paid tier)
                    if source != "birdeye":
                        warning(f"⚠️ Only one SOL price source available ({source}: ${price:.2f}) - accepting due to reasonable price range")
                    else:
                        debug(f"✅ SOL price from Birdeye: ${price:.2f} (primary paid source)", file_only=True)
                    self._cache_sol_price(price, source)
                    return price
                else:
                    warning(f"🚫 Only one SOL price source available ({source}: ${price:.2f}) - rejecting due to price outside reasonable range")
                    return self._get_last_known_sol_price()
            
            # Validate consensus between sources
            vals = [p[1] for p in prices]
            min_p, max_p = min(vals), max(vals)
            deviation = (max_p - min_p) / max_p if max_p > 0 else 0
            
            if deviation > self.consensus_tolerance:
                warning(f"🚫 SOL price consensus failed: {[(s, f'${v:.2f}') for s,v in prices]} (deviation={deviation:.2%} > {self.consensus_tolerance:.2%})")
                return self._get_last_known_sol_price()
            
            # Return median price
            vals.sort()
            median = vals[len(vals)//2]
            # Cache the price
            self._cache_sol_price(median, "consensus")
            return median
            
        except Exception as e:
            error(f"Error fetching SOL price: {e}")
            return self._get_last_known_sol_price()

    def _get_cached_sol_price(self) -> Optional[float]:
        """Get SOL price from cache if valid"""
        with self.cache_lock:
            if hasattr(self, 'sol_price_cache') and self.sol_price_cache:
                price_data, timestamp = self.sol_price_cache
                if time.time() - timestamp < 60:  # 1 minute TTL
                    return price_data
            return None
    
    def _cache_sol_price(self, price: float, source: str):
        """Cache SOL price with timestamp"""
        with self.cache_lock:
            self.sol_price_cache = (price, time.time())
            debug(f"✅ SOL price cached: ${price:.2f} from {source}")
    
    def _get_last_known_sol_price(self) -> Optional[float]:
        """Get last known good SOL price from cache"""
        with self.cache_lock:
            if hasattr(self, 'sol_price_cache') and self.sol_price_cache:
                price_data, timestamp = self.sol_price_cache
                if time.time() - timestamp < 1800:  # 30 minutes TTL for last known good
                    warning(f"⚠️ Using last known SOL price: ${price_data:.2f} (age: {time.time() - timestamp:.1f}s)")
                    return price_data
            return None
    
    def _fetch_pyth_sol_price(self) -> Optional[float]:
        """Fetch SOL price from Pyth price feed"""
        try:
            url = "https://api.pyth.network/v2/price_feeds/solana?ids=So11111111111111111111111111111111111111112"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'price_feeds' in data and len(data['price_feeds']) > 0:
                    price_feed = data['price_feeds'][0]
                    if 'price' in price_feed and 'expo' in price_feed:
                        price = float(price_feed['price']) * (10 ** price_feed['expo'])
                        return price
            return None
        except Exception:
            return None
    
    def _fetch_pumpfun_price(self, token_address: str) -> Optional[float]:
        """Fetch price from Pump.fun"""
        try:
            url = f"https://api.pump.fun/v1/token/{token_address}/price"
            
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if 'price' in data:
                    price = float(data['price'])
                    return price
            
            return None
            
        except Exception:
            return None

    def _validate_price_optimized(self, token_address: str, price: float, sources: List[Tuple[str, float]], agent_type: str) -> PriceValidation:
        """
        Optimized price validation with rate limiting and smart caching
        """
        try:
            # PERFORMANCE OPTIMIZATION: Rate limiting and smart caching
            if hasattr(self, '_validation_timestamps'):
                last_validation = self._validation_timestamps.get(token_address, 0)
            else:
                self._validation_timestamps = {}
                last_validation = 0

            current_time = time.time()
            time_since_validation = current_time - last_validation

            # Skip validation if recently validated and price hasn't changed significantly
            import config
            validation_threshold = getattr(config, 'PRICE_VALIDATION_CACHE_THRESHOLD', 60)
            price_change_threshold = getattr(config, 'PRICE_CHANGE_THRESHOLD', 0.01)

            if time_since_validation < validation_threshold:
                cached_price = self.price_cache.get(token_address)
                if cached_price and abs(price - cached_price.price) < price_change_threshold:
                    return PriceValidation(is_valid=True, reason="Recent valid price, optimized validation skipped")

            # Update validation timestamp
            self._validation_timestamps[token_address] = current_time

            # Perform full validation
            return self.validate_price_for_trading(
                token_address=token_address,
                price=price,
                sources=sources,
                cache_age_seconds=0
            )

        except Exception as e:
            error(f"Error in optimized validation: {e}")
            # Fallback to full validation
            return self.validate_price_for_trading(
                token_address=token_address,
                price=price,
                sources=sources,
                cache_age_seconds=0
            )

    def _get_cached_price(self, token_address: str) -> Optional[float]:
        """Get cached price (legacy method name)"""
        return self._get_cached_price_optimized(token_address)

    def _get_cached_price_optimized(self, token_address: str) -> Optional[float]:
        """Get cached price with optimized validation frequency"""
        with self.cache_lock:
            if token_address in self.price_cache:
                price_data = self.price_cache[token_address]
                if self._is_cache_valid(price_data):
                    # PERFORMANCE OPTIMIZATION: Reduced validation frequency for cached prices
                    cache_age_seconds = (datetime.now() - price_data.timestamp).total_seconds()

                    # Only validate cached prices if they're older than threshold
                    import config
                    cache_threshold = getattr(config, 'PRICE_VALIDATION_CACHE_THRESHOLD', 60)

                    if cache_age_seconds < cache_threshold:
                        return price_data.price

                    # Validate with reduced frequency (every 10th call)
                    if hasattr(self, '_cached_validation_counter'):
                        self._cached_validation_counter += 1
                    else:
                        self._cached_validation_counter = 0

                    if self._cached_validation_counter % 10 == 0:  # Validate every 10th cached lookup
                        validation = self.validate_price_for_trading(
                            token_address=token_address,
                            price=price_data.price,
                            sources=[(price_data.source, price_data.price)],
                            cache_age_seconds=int(cache_age_seconds)
                        )

                        if validation.is_valid:
                            return price_data.price
                        else:
                            debug(f"🚫 Cached price REJECTED by validation: {validation.reason}")
                            del self.price_cache[token_address]
                            return None
                    else:
                        # Skip validation for performance
                        return price_data.price
                else:
                    # Remove expired cache entry
                    del self.price_cache[token_address]
            return None
    
    def _is_cache_valid(self, price_data: PriceData) -> bool:
        """Check if cached price is still valid"""
        cache_duration = self.cache_expiry.get(price_data.cache_tier, 3600)
        age = (datetime.now() - price_data.timestamp).total_seconds()
        is_valid = age < cache_duration
        debug(f"🔍 Cache validation: {price_data.token_address[:8]}... tier={price_data.cache_tier} age={age:.1f}s duration={cache_duration}s valid={is_valid}")
        return is_valid
    
    def _cache_price(self, token_address: str, price: float, cache_tier: str, fetch_time_ms: int):
        """Cache price with appropriate tier"""
        with self.cache_lock:
            self.price_cache[token_address] = PriceData(
                price=price,
                timestamp=datetime.now(),
                source='quicknode' if cache_tier == 'active_trades' else 'fallback',
                token_address=token_address,
                cache_tier=cache_tier,
                fetch_time_ms=fetch_time_ms
            )
    
    def _track_api_call(self):
        """Track API calls and check CU limits with adaptive throttling"""
        if not self.cu_circuit_breaker_enabled:
            return  # Tracking disabled
        
        now = datetime.now()
        
        # Reset daily counter at midnight
        if now.date() > self.cu_tracker['last_daily_reset']:
            info(f"🌅 Midnight reset - Yesterday's CU usage: {self.cu_tracker['daily_calls']} calls")
            self.cu_tracker['daily_calls'] = 0
            self.cu_tracker['last_daily_reset'] = now.date()
            
            # Reset throttling if active
            if self.cu_tracker['throttle_active']:
                info("✅ CU throttle DEACTIVATED - Restored to 60-second intervals")
                self.cu_tracker['throttle_active'] = False
        
        # Increment daily counter
        self.cu_tracker['daily_calls'] += 1
        
        # Check warning threshold (80k)
        if self.cu_tracker['daily_calls'] == self.cu_warning_threshold:
            warning(f"⚠️ CU WARNING: Reached {self.cu_tracker['daily_calls']} calls today (approaching {self.cu_daily_limit} limit)")
            warning(f"💡 Tip: {self.cu_daily_limit - self.cu_tracker['daily_calls']} calls remaining before throttling activates")
        
        # Check throttling threshold (90k) - increase intervals instead of stopping
        if self.cu_tracker['daily_calls'] >= self.cu_daily_limit and not self.cu_tracker['throttle_active']:
            error(f"🚨 CU LIMIT REACHED: {self.cu_tracker['daily_calls']} calls today")
            error(f"🔄 ADAPTIVE THROTTLING ACTIVATED: Intervals increased from 60s to {self.cu_throttle_interval}s")
            error("💡 System continues with reduced frequency until midnight reset")
            self.cu_tracker['throttle_active'] = True
    
    def _get_current_interval(self) -> int:
        """Get current monitoring interval based on throttle status"""
        if self.cu_tracker['throttle_active']:
            return self.cu_throttle_interval  # 300 seconds when throttled
        else:
            return self.cu_tracker['original_interval']  # 60 seconds normally

    def _fetch_birdeye_prices_batch(self, addresses: List[str]) -> Dict[str, float]:
        """Fetch multiple prices from Birdeye in batches to reduce CU consumption"""
        results: Dict[str, float] = {}
        if not addresses:
            return results

        # Lazy load API key
        api_key = get_birdeye_api_key_optimized()
        if not api_key:
            return results

        batch_size = getattr(config, 'BIRDEYE_BATCH_SIZE', 50)
        delay_seconds = getattr(config, 'BIRDEYE_BATCH_DELAY_SECONDS', 0.2)

        headers = {
            "X-API-KEY": api_key,
            "X-Chain": "solana",
            "accept": "application/json",
        }

        for i in range(0, len(addresses), batch_size):
            batch = addresses[i:i + batch_size]
            try:
                ids = ",".join(batch)
                url = f"https://public-api.birdeye.so/public/multi_price?list_address={ids}"
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success", False) and "data" in data:
                        data_map = data.get("data", {})
                        # Track CU approx per returned price
                        for addr, price_data in data_map.items():
                            if price_data is None:
                                continue
                            # Birdeye returns {"value": <price>} for each address
                            val = price_data.get("value")
                            if val is None:
                                continue
                            try:
                                price_f = float(val)
                                if price_f > 0:
                                    results[addr] = price_f
                                    # Track usage per filled price
                                    self._track_api_call()
                            except Exception:
                                continue
                # small delay between batches
                if i + batch_size < len(addresses) and delay_seconds > 0:
                    time.sleep(delay_seconds)
            except Exception as e:
                debug(f"Birdeye batch fetch error: {str(e)}", file_only=True)
                # continue to next batch
                if i + batch_size < len(addresses) and delay_seconds > 0:
                    time.sleep(delay_seconds)

        return results
    
    def _monitor_active_tokens(self):
        """Background thread to monitor active trading tokens with adaptive throttling
        
        Updates prices using batch fetching. Automatically adjusts interval from 60s to 300s
        when CU limit is reached, then resets to 60s at midnight.
        """
        while self.monitoring_active:
            try:
                # Get current interval (adapts based on CU usage)
                current_interval = self._get_current_interval()
                
                # Update prices for active trading tokens using batch fetch
                if self.active_trading_tokens:
                    token_list = list(self.active_trading_tokens)
                    throttle_status = " [THROTTLED]" if self.cu_tracker['throttle_active'] else ""
                    debug(f"🔄 Background monitoring{throttle_status}: batch fetching {len(token_list)} active tokens", file_only=True)
                    try:
                        # Single batch fetch for all active tokens
                        self.get_prices(token_list, force_fetch=True, priority='high')
                        debug(f"✅ Background batch fetch complete for {len(token_list)} tokens", file_only=True)
                    except Exception as e:
                        debug(f"Error in batch monitoring: {str(e)}", file_only=True)
                
                # Sleep for current interval (60s normally, 300s when throttled)
                time.sleep(current_interval)
                
            except Exception as e:
                error(f"Error in active token monitoring: {str(e)}")
                time.sleep(self._get_current_interval())  # Use current interval on error too
        
        debug("Price monitoring stopped")
    
    def mark_token_active(self, token_address: str):
        """Mark token as actively being traded (add to portfolio)"""
        self.active_trading_tokens.add(token_address)
        debug(f"Marked {token_address[:8]}... as active trading token")
    
    def unmark_token_active(self, token_address: str):
        """Unmark token as active (removed from portfolio)"""
        self.active_trading_tokens.discard(token_address)
        debug(f"Unmarked {token_address[:8]}... as active trading token")
    
    def mark_token_recent_activity(self, token_address: str):
        """Mark token as having recent activity"""
        self.recent_activity_tokens.add(token_address)
        debug(f"Marked {token_address[:8]}... as recent activity token")
    
    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics"""
        with self.cache_lock:
            return {
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'api_calls': self.api_calls,
                'cache_size': len(self.price_cache),
                'active_trading_tokens': len(self.active_trading_tokens),
                'recent_activity_tokens': len(self.recent_activity_tokens),
                'avg_fetch_time_ms': self.avg_fetch_time_ms,
                'hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
                'price_mode': self.price_mode,
                'failed_fetches_count': len(self.failed_fetches),
                'jupiter_circuit_breaker': self.jupiter_circuit_breaker,
                'cu_status': self.get_cu_status()
            }
    
    def get_cu_status(self) -> Dict:
        """Get current CU usage and throttling status"""
        if not self.cu_circuit_breaker_enabled:
            return {'enabled': False}
        
        percentage_used = (self.cu_tracker['daily_calls'] / self.cu_daily_limit) * 100 if self.cu_daily_limit > 0 else 0
        calls_remaining = self.cu_daily_limit - self.cu_tracker['daily_calls']
        current_interval = self._get_current_interval()
        
        return {
            'enabled': True,
            'daily_calls': self.cu_tracker['daily_calls'],
            'daily_limit': self.cu_daily_limit,
            'percentage_used': round(percentage_used, 2),
            'calls_remaining': max(0, calls_remaining),
            'throttle_active': self.cu_tracker['throttle_active'],
            'current_interval': current_interval,
            'warning_threshold': self.cu_warning_threshold,
            'next_reset': f"{self.cu_tracker['last_daily_reset'] + timedelta(days=1)} 00:00:00"
        }
    
    def validate_price_for_trading(self, token_address: str, price: float, sources: List[Tuple[str, float]], cache_age_seconds: Optional[int] = None) -> PriceValidation:
        """
        CRITICAL: Validate price before allowing trades to prevent $121 SOL disasters
        This is the guardian that prevents trading on stale/bad prices
        """
        try:
            # RATE LIMITING: Skip validation if price is recent and similar to cached value
            if cache_age_seconds is not None and cache_age_seconds < 60:  # Less than 1 minute old
                cached_price = self.price_cache.get(token_address)
                if cached_price and abs(price - cached_price.price) < 0.01:  # Less than 1 cent difference
                    return PriceValidation(is_valid=True, reason="Recent valid price, skipping validation")
            
            # Get token symbol for logging using config addresses
            import config
            symbol = "UNK"
            if token_address == getattr(config, 'SOL_ADDRESS', "So11111111111111111111111111111111111111112"):
                symbol = "SOL"
            elif token_address == getattr(config, 'USDC_ADDRESS', "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"):
                symbol = "USDC"
            elif token_address == getattr(config, 'USDT_ADDRESS', "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"):
                symbol = "USDT"
            
            # Check startup grace - relax validation during startup
            import time
            startup_grace = getattr(config, 'VALIDATION_STARTUP_GRACE_SECONDS', 0)
            if startup_grace > 0:
                if not hasattr(config, '_APP_START_TIME'):
                    config._APP_START_TIME = time.time()
                
                if time.time() - config._APP_START_TIME < startup_grace:
                    info(f"🟢 Startup grace active: accepting price with relaxed validation for {symbol}", file_only=True)
                    # Accept single source and ignore age during grace
                    return PriceValidation(
                        is_valid=True,
                        reason="startup_grace_active",
                        price=price,
                        sources_used=[s[0] for s in sources],
                        cache_age_seconds=cache_age_seconds,
                        consensus_deviation=None
                    )
            
            # 1. Check sanity bounds (prevents obviously wrong prices)
            # Use dynamic bounds for unknown tokens
            min_price, max_price = self.sanity_bounds.get(
                token_address, 
                self._get_price_sanity_bounds(token_address)
            )
            if not (min_price <= price <= max_price):
                warning(f"🚫 Price ${price:.4f} outside bounds (${min_price}-${max_price})")
                return PriceValidation(
                    is_valid=False,
                    reason=f"price_out_of_bounds_{min_price}_{max_price}",
                    price=price,
                    sources_used=[s[0] for s in sources],
                    cache_age_seconds=cache_age_seconds,
                    consensus_deviation=None
                )
            
            # 2. Check cache age (prevents using stale prices)
            max_age = self.max_cache_age.get(symbol, self.max_cache_age['default'])
            if cache_age_seconds is not None and cache_age_seconds > max_age:
                debug(f"🚫 Price validation FAILED for {symbol}: cache too old ({cache_age_seconds}s > {max_age}s max)")
                return PriceValidation(
                    is_valid=False,
                    reason=f"stale_cache_{cache_age_seconds}s",
                    price=price,
                    sources_used=[s[0] for s in sources],
                    cache_age_seconds=cache_age_seconds,
                    consensus_deviation=None
                )
            
            # 3. Check consensus between sources (prevents using outlier prices)
            if len(sources) >= self.min_sources_for_consensus:
                prices = [s[1] for s in sources]
                min_price, max_price = min(prices), max(prices)
                deviation = (max_price - min_price) / max_price if max_price > 0 else 0
                
                if deviation > self.consensus_tolerance:
                    debug(f"🚫 Price validation FAILED for {symbol}: consensus failed - deviation {deviation:.2%} > {self.consensus_tolerance:.2%} tolerance", file_only=True)
                    debug(f"   Sources: {[(s[0], f'${s[1]:.4f}') for s in sources]}")
                    return PriceValidation(
                        is_valid=False,
                        reason=f"consensus_failed_{deviation:.2%}",
                        price=price,
                        sources_used=[s[0] for s in sources],
                        cache_age_seconds=cache_age_seconds,
                        consensus_deviation=deviation
                    )
            
            # All checks passed - price is safe for trading
            # Reduce logging noise - only log every 10th validation or on failures
            if not hasattr(self, '_validation_count'):
                self._validation_count = 0
            self._validation_count += 1
            
            if self._validation_count % 10 == 0 or symbol in ['SOL', 'USDC']:
                debug(f"✅ Price validation PASSED for {symbol}: ${price:.4f} from {len(sources)} sources, age: {cache_age_seconds}s")
            return PriceValidation(
                is_valid=True,
                reason="validation_passed",
                price=price,
                sources_used=[s[0] for s in sources],
                cache_age_seconds=cache_age_seconds,
                consensus_deviation=None
            )
            
        except Exception as e:
            error(f"❌ Price validation ERROR for {token_address}: {e}")
            return PriceValidation(
                is_valid=False,
                reason=f"validation_error_{str(e)}",
                price=price,
                sources_used=[s[0] for s in sources] if sources else [],
                cache_age_seconds=cache_age_seconds,
                consensus_deviation=None
            )
    
    def is_jupiter_circuit_breaker_open(self) -> bool:
        """Check if Jupiter circuit breaker is open"""
        current_time = time.time()
        cb = self.jupiter_circuit_breaker
        
        # Reset failures if outside failure window
        if current_time - cb['last_failure_time'] > cb['failure_window']:
            cb['failures'] = 0
        
        # Check if circuit should be closed
        if cb['is_open'] and current_time - cb['last_failure_time'] > cb['open_duration']:
            cb['is_open'] = False
            cb['failures'] = 0
            info("🔄 Jupiter circuit breaker CLOSED - attempting reconnection")
        
        return cb['is_open']
    
    def record_jupiter_failure(self):
        """Record a Jupiter API failure for circuit breaker"""
        current_time = time.time()
        cb = self.jupiter_circuit_breaker
        
        cb['failures'] += 1
        cb['last_failure_time'] = current_time
        
        if cb['failures'] >= cb['failure_threshold']:
            cb['is_open'] = True
            warning(f"🔴 Jupiter circuit breaker OPENED after {cb['failures']} failures - blocking Jupiter calls for {cb['open_duration']}s")
    
    def record_jupiter_success(self):
        """Record a Jupiter API success"""
        cb = self.jupiter_circuit_breaker
        if cb['failures'] > 0:
            cb['failures'] = max(0, cb['failures'] - 1)  # Gradually reduce failure count
    
    def clear_stale_cache(self, token_address: str = None):
        """Clear stale cache entries, especially for SOL"""
        with self.cache_lock:
            if token_address:
                # Clear specific token
                if token_address in self.price_cache:
                    del self.price_cache[token_address]
                    info(f"🧹 Cleared stale cache for {token_address[:8]}...")
            else:
                # Clear all cache
                cleared_count = len(self.price_cache)
                self.price_cache.clear()
                info(f"🧹 Cleared all price cache ({cleared_count} entries)")
    
    def force_refresh_sol_price(self):
        """Force refresh SOL price to get current market price"""
        sol_address = "So11111111111111111111111111111111111111112"
        self.clear_stale_cache(sol_address)
        fresh_price = self.get_price(sol_address, force_fetch=True, priority='high')
        if fresh_price:
            info(f"💰 SOL price refreshed: ${fresh_price:.4f}")
        return fresh_price
    
    def shutdown(self):
        """Shutdown the monitoring thread"""
        # Safety check to prevent AttributeError
        if not hasattr(self, 'monitoring_active'):
            self.monitoring_active = False
        self.monitoring_active = False
        if hasattr(self, 'monitoring_thread') and self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
    
    def is_ready(self) -> bool:
        """Check if the price service is ready to use"""
        return self._initialized  # monitoring_active is disabled, so just check initialization
    
    def token_price(self, token_address: str, **kwargs) -> Optional[float]:
        """Get token price with legacy method name for compatibility"""
        return self.get_price(token_address, **kwargs)

def get_optimized_price_service() -> OptimizedPriceService:
    """Get singleton instance of optimized price service"""
    return OptimizedPriceService()

def test_birdeye_connection():
    """Test Birdeye API connection and display status"""
    print("🔍 Testing Birdeye API Connection...")

    # Test API key loading
    api_key = get_birdeye_api_key_optimized()
    if not api_key:
        print("❌ BIRDEYE_API_KEY not found")
        return False

    print(f"✅ API Key loaded: {api_key[:8]}...{api_key[-4:]}")

    # Test SOL price fetch
    try:
        # Create a temporary instance to test the method
        temp_service = OptimizedPriceService()
        price = temp_service._fetch_birdeye_price("So11111111111111111111111111111111111111112")
        if price:
            print(f"✅ SOL Price: ${price:.4f}")
            print("🎉 Birdeye API connection successful!")
            return True
        else:
            print("❌ Failed to fetch SOL price")
            return False
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        return False

# Make test function available at module level
if __name__ == "__main__":
    test_birdeye_connection() 
