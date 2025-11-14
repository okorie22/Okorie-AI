"""
Wallet Tracker for Anarcho Capital's Trading Desktop App
Provides efficient wallet tracking with optimized price fetching
"""

import os
import time
import json
import requests
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from dotenv import load_dotenv

# Import logger functions
try:
    from src.scripts.shared_services.logger import debug, info, warning, error, system
except ImportError:
    # Define fallback logging functions if logger module is not available
    def debug(msg, file_only=False):
        if not file_only:
            print(f"DEBUG: {msg}")
            
    def info(msg):
        print(f"INFO: {msg}")
        
    def warning(msg):
        print(f"WARNING: {msg}")
        
    def error(msg):
        print(f"ERROR: {msg}")
        
    def system(msg):
        print(f"SYSTEM: {msg}")

# Load environment variables
load_dotenv()

# Import configuration values
try:
    from src.config import (
        WALLETS_TO_TRACK,
        DYNAMIC_MODE,
        MONITORED_TOKENS,
        FILTER_MODE,
        PERCENTAGE_THRESHOLD, 
        AMOUNT_THRESHOLD,
        ENABLE_PERCENTAGE_FILTER,
        ENABLE_AMOUNT_FILTER,
        ENABLE_ACTIVITY_FILTER,
        ACTIVITY_WINDOW_HOURS,
        PRICE_SOURCE_MODE,
        PRICE_CACHE_MINUTES,
        BATCH_SIZE,
        MIN_TOKEN_VALUE,
        SKIP_UNKNOWN_TOKENS,
        USE_PARALLEL_PROCESSING,
        API_TIMEOUT_SECONDS,
        API_MAX_RETRIES,
        API_SLEEP_SECONDS
    )
except ImportError:
    # Default values if config import fails
    WALLETS_TO_TRACK = []
    DYNAMIC_MODE = True
    MONITORED_TOKENS = []
    FILTER_MODE = "Dynamic"
    PERCENTAGE_THRESHOLD = 0.01
    AMOUNT_THRESHOLD = 1000
    ENABLE_PERCENTAGE_FILTER = False
    ENABLE_AMOUNT_FILTER = False
    ENABLE_ACTIVITY_FILTER = False
    ACTIVITY_WINDOW_HOURS = 1
    PRICE_SOURCE_MODE = "birdeye"  # Use Birdeye as primary source (paid tier)
    PRICE_CACHE_MINUTES = 30
    BATCH_SIZE = 50
    MIN_TOKEN_VALUE = 0.1
    SKIP_UNKNOWN_TOKENS = True
    USE_PARALLEL_PROCESSING = True
    API_TIMEOUT_SECONDS = 15
    API_MAX_RETRIES = 3
    API_SLEEP_SECONDS = 1

# Import our new services
try:
    from src.scripts.shared_services.optimized_price_service import get_optimized_price_service as PriceService
    from src.scripts.data_processing.token_metadata_service import TokenMetadataService
    from src.scripts.database.db_cache import DatabaseCache
except ImportError:
    print("Warning: Could not import PriceService or TokenMetadataService.")
    print("Using fallback price service functionality.")
    PriceService = None
    TokenMetadataService = None
    DatabaseCache = None

CHANGE_EVENTS_PATH = os.path.join(os.getcwd(), 'src', 'data', 'change_events.csv')

class WalletTracker:
    """
    Efficient wallet tracker with optimized price fetching and caching
    """
    
    def __init__(self):
        """Initialize the wallet tracker"""
        # Use the shared API manager for RPC requests with fallback
        from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
        self.api_manager = get_shared_api_manager()
        
        # Initialize services
        if PriceService:
            self.price_service = PriceService()
        else:
            self.price_service = None
            warning("PriceService not available. Using fallback price fetching.")
            
        if TokenMetadataService:
            self.metadata_service = TokenMetadataService()
        else:
            self.metadata_service = None
            warning("TokenMetadataService not available. Using fallback metadata fetching.")

        # Initialize DB cache for prices if available
        self.db_cache = None
        if 'DatabaseCache' in globals() and DatabaseCache is not None:
            try:
                self.db_cache = DatabaseCache()
            except Exception as e:
                warning(f"DatabaseCache init failed: {e}")
        
        # CRITICAL FIX: Add RPC response caching to prevent timeout issues
        self.rpc_cache = {}
        self.rpc_cache_lock = threading.Lock()
        self.rpc_cache_ttl = 60  # 60 seconds TTL for token accounts
        
        # Setup cache paths based on mode
        self.cache_dir = os.path.join(os.getcwd(), "src/data")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.cache_file = os.path.join(
            self.cache_dir, 
            "artificial_memory_d.json" if DYNAMIC_MODE 
            else "artificial_memory_m.json"
        )
        
        # Initialize previous tokens list for change detection
        self.previous_monitored_tokens = []
        self.previous_mode = None
    
    def _make_rpc_request_with_retry(self, method: str, params: list, wallet_address: str, timeout: int = 15) -> Optional[dict]:
        """Make RPC request with retry logic and jitter"""
        import random
        import time
        
        max_retries = 3
        base_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                data = self.api_manager.make_rpc_request(method, params, wallet_address, timeout)
                if data is not None:
                    return data
            except Exception as e:
                warning(f"RPC request attempt {attempt + 1} failed: {str(e)}")
                
            if attempt < max_retries - 1:
                # Add jitter to prevent thundering herd
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
        
        return None
        
        system(f"Wallet Tracker initialized in {'DYNAMIC' if DYNAMIC_MODE else 'MONITORED'} mode")
        if not DYNAMIC_MODE:
            info(f"Monitoring {len(MONITORED_TOKENS)} specific tokens")
        
    def load_cache(self) -> Tuple[Dict, bool]:
        """Return tuple: (cached_data, cache_empty_status)"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    cached_data = json.load(f)
                self.previous_mode = cached_data.get('mode')
                self.previous_monitored_tokens = cached_data.get('previous_monitored_tokens', [])
                # Return data + cache_was_empty status
                return cached_data.get('data', {}), False
            except Exception as e:
                error(f"Error loading cache: {str(e)}")
                return {}, True  # Consider cache empty if load failed
        return {}, True  # Cache file doesn't exist

    def set_on_cache_saved(self, callback):
        """Set a callback to be called after cache is saved."""
        self._on_cache_saved = callback

    def save_cache(self, data):
        """Save wallet data to a mode-specific cache file."""
        info(f"Saving data to {self.cache_file}...")
        try:
            cache_data = {
                'mode': DYNAMIC_MODE,
                'data': data,
                'previous_monitored_tokens': self.previous_monitored_tokens.copy(),
                'timestamp': datetime.now().isoformat()
            }
            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)
            info(f"Data saved to {self.cache_file}!")
            # Call the callback if set
            if hasattr(self, '_on_cache_saved') and self._on_cache_saved:
                try:
                    self._on_cache_saved()
                except Exception as e:
                    warning(f"Error in on_cache_saved callback: {e}")
        except Exception as e:
            error(f"Error saving cache: {str(e)}")
    
    def clear_cache(self):
        """Clear the wallet cache to force fresh data fetch."""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                info(f"Cleared cache file: {self.cache_file}")
            else:
                info("No cache file to clear")
        except Exception as e:
            error(f"Error clearing cache: {str(e)}")
            
    def get_token_balances(self, wallet_address: str) -> List[Dict]:
        """BULLETPROOF: Fetch balances with comprehensive timeout and error handling"""
        from src import config  # Import config at function level
        
        execution_start_time = time.time()
        MAX_TOTAL_TIME = getattr(config, 'WALLET_TRACKING_TIMEOUT_SECONDS', 60)  # Total operation timeout
        MAX_TOKEN_TIME = 10  # Maximum time per token request
        
        info(f"🔍 BULLETPROOF token balance fetch for {wallet_address[:8]}... (timeout: {MAX_TOTAL_TIME}s)")
        
        # SAFETY CHECK 1: Parameter validation
        if not wallet_address or len(wallet_address) < 32:
            error(f"❌ Invalid wallet address: {wallet_address}")
            return []
        
        balances = []
        found_count = 0
        not_found_count = 0
        timeout_count = 0
        fetch_start_time = time.time()
        token_fetch_times = []
        
        try:
            for token_idx, token in enumerate(MONITORED_TOKENS):
                # SAFETY CHECK 2: Overall timeout check
                elapsed_total = time.time() - execution_start_time
                if elapsed_total > MAX_TOTAL_TIME:
                    warning(f"⏰ Total timeout reached after {elapsed_total:.1f}s, processed {token_idx}/{len(MONITORED_TOKENS)} tokens")
                    break
                
                token_start_time = time.time()
                
                # SAFETY CHECK 3: Individual token timeout
                try:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": f"anarcho-capital-{token_idx}",
                        "method": "getTokenAccountsByOwner",
                        "params": [
                            wallet_address,
                            {"mint": token},
                            {"encoding": "jsonParsed"}
                        ]
                    }
                    
                    # Use the new RPC fallback system
                    params = [
                        wallet_address,
                        {"mint": token},
                        {"encoding": "jsonParsed"}
                    ]
                    
                    result = self.api_manager.make_rpc_request("getTokenAccountsByOwner", params, wallet_address)
                    
                    if result is None:
                        timeout_count += 1
                        not_found_count += 1
                        continue
                    
                    data = result

                    if "result" in data and data["result"]["value"]:
                        parsed_data = data["result"]["value"][0]["account"]["data"]["parsed"]["info"]
                        # CRITICAL FIX: Use unified token balance parsing
                        from src.nice_funcs import parse_token_balance_with_decimals
                        amount, decimals = parse_token_balance_with_decimals(parsed_data)
                        
                        # SAFETY CHECK 4: Validate amount
                        if amount < 0 or decimals < 0:
                            warning(f"⚠️ Invalid token data: amount={amount}, decimals={decimals}")
                            not_found_count += 1
                            continue
                        
                        # Get additional information with timeout protection
                        token_info = {}
                        
                        # Get price with timeout
                        if self.price_service:
                            try:
                                price = self._get_price_with_timeout(token, 5)  # 5 second timeout
                                if price is not None:
                                    token_info["price"] = price
                            except Exception as price_error:
                                debug(f"Price fetch failed for {token}: {price_error}")
                            
                        # Get metadata with timeout
                        if self.metadata_service:
                            try:
                                metadata = self._get_metadata_with_timeout(token, 3)  # 3 second timeout
                                if metadata:
                                    token_info["symbol"] = metadata.get("symbol", "UNK")
                                    token_info["name"] = metadata.get("name", "Unknown Token")
                            except Exception as metadata_error:
                                debug(f"Metadata fetch failed for {token}: {metadata_error}")
                        
                        balances.append({
                            "mint": token,
                            "amount": amount,
                            "decimals": decimals,
                            "raw_amount": int(amount * (10 ** decimals)),
                            "timestamp": datetime.now().isoformat(),
                            "wallet_address": wallet_address,
                            **token_info
                        })
                        found_count += 1
                    else:
                        not_found_count += 1
                        
                except Exception as e:
                    error(f"❌ Error fetching token {token[:8]}...: {str(e)}")
                    not_found_count += 1
                
                # Track timing
                token_elapsed = time.time() - token_start_time
                token_fetch_times.append(token_elapsed)
                
                # Brief pause to prevent overwhelming the RPC
                if token_idx < len(MONITORED_TOKENS) - 1:  # Don't sleep after last token
                    time.sleep(0.1)

            # EXECUTION SUMMARY
            total_time = time.time() - execution_start_time
            avg_token_time = sum(token_fetch_times) / len(token_fetch_times) if token_fetch_times else 0
            
            info(f"✅ Balance fetch complete: {found_count} found, {not_found_count} not found, {timeout_count} timeouts")
            info(f"📊 Timing: {total_time:.1f}s total, {avg_token_time:.1f}s avg per token")
            
            return balances
            
        except Exception as e:
            total_time = time.time() - execution_start_time
            error(f"❌ CRITICAL ERROR in token balance fetch after {total_time:.1f}s: {str(e)}")
            return balances  # Return partial results if any
    
    def _execute_request_with_timeout(self, url, payload, timeout_seconds, operation_name):
        """Execute HTTP request with timeout protection"""
        try:
            response = requests.post(url, json=payload, timeout=timeout_seconds)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            warning(f"⏰ {operation_name} timed out after {timeout_seconds}s")
            return None
        except requests.exceptions.RequestException as e:
            warning(f"⚠️ {operation_name} request failed: {str(e)}")
            return None
        except Exception as e:
            error(f"❌ {operation_name} unexpected error: {str(e)}")
            return None
    
    def _get_price_with_timeout(self, token_address, timeout_seconds):
        """Get token price with timeout"""
        try:
            import threading
            import time
            
            def timeout_handler():
                raise TimeoutError("Price fetch timeout")
            
            # Set timeout using threading.Timer (Windows compatible)
            timer = threading.Timer(timeout_seconds, timeout_handler)
            timer.start()
            
            try:
                price = self.price_service.get_price(token_address)
                timer.cancel()  # Cancel timeout
                return price
            finally:
                timer.cancel()  # Ensure timeout is cancelled
                
        except TimeoutError:
            return None
        except Exception:
            return None

    def _resolve_price(self, token_mint: str) -> float:
        """Resolve USD price with robust fallbacks and store to DB cache.

        - Primary: optimized price service
        - Fallback: Jupiter implied price
        - Avoid $1 default for non-stables
        - Persist to SQLite cache if available
        """
        try:
            stable_mints = {
                'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
                'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',  # USDT
            }
            price = None
            if self.price_service:
                price = self.price_service.get_price(token_mint)
            price = float(price) if price is not None else 0.0
            if price <= 0 or (price == 1.0 and token_mint not in stable_mints):
                try:
                    from src.nice_funcs import get_real_time_price_jupiter
                    price = float(get_real_time_price_jupiter(token_mint) or 0.0)
                except Exception:
                    price = price if price > 0 else 0.0
            if self.db_cache and price and price > 0:
                try:
                    import time as _t
                    ttl = 300
                    self.db_cache.store_price(token_mint, price, int(_t.time()) + ttl)
                except Exception:
                    pass
            return price if price and price > 0 else 0.0
        except Exception:
            return 0.0
    
    def _get_metadata_with_timeout(self, token_address, timeout_seconds):
        """Get token metadata with timeout"""
        try:
            import threading
            import time
            
            def timeout_handler():
                raise TimeoutError("Metadata fetch timeout")
            
            # Set timeout using threading.Timer (Windows compatible)
            timer = threading.Timer(timeout_seconds, timeout_handler)
            timer.start()
            
            try:
                metadata = self.metadata_service.get_metadata(token_address)
                timer.cancel()  # Cancel timeout
                return metadata
            finally:
                timer.cancel()  # Ensure timeout is cancelled
                
        except TimeoutError:
            return None
        except Exception:
            return None

    def get_current_token_accounts(self, wallet_address: str) -> List[Dict]:
        """Fetch all token accounts for a wallet address with caching to prevent timeouts."""
        
        try:
            # CRITICAL FIX: Check cache first to avoid expensive RPC calls
            cache_key = f"token_accounts_{wallet_address}"
            current_time = time.time()
            
            with self.rpc_cache_lock:
                if cache_key in self.rpc_cache:
                    cached_data, cache_time = self.rpc_cache[cache_key]
                    if current_time - cache_time < self.rpc_cache_ttl:
                        debug(f"✅ Using cached token accounts for {wallet_address[:8]}... (age: {current_time - cache_time:.1f}s)")
                        return cached_data
            
            # Cache miss or expired - fetch from RPC
            debug(f"🔄 Fetching fresh token accounts for {wallet_address[:8]}...")
            
            params = [
                wallet_address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"}
            ]
            
            # Pass wallet_address for hybrid RPC strategy with increased timeout and retry logic
            data = self._make_rpc_request_with_retry("getTokenAccountsByOwner", params, wallet_address, timeout=15)
            
            if data is None:
                warning(f"RPC request failed for wallet {wallet_address[:8]}...")
                return []

            if "result" not in data or not data["result"]["value"]:
                warning(f"No token accounts found for {wallet_address[:4]}")
                return []

            token_accounts = []
            zero_balance_count = 0
            token_mints = []
            
            # First pass: Extract all token mints for batch price and metadata fetching
            for account in data["result"]["value"]:
                account_info = account["account"]["data"]["parsed"]["info"]
                if int(account_info["tokenAmount"]["amount"]) == 0:
                    zero_balance_count += 1
                    continue  # Skip tokens with zero balance
                
                token_mints.append(account_info["mint"])
            
            # Batch fetch prices and metadata if services are available
            prices = {}
            metadata = {}
            
            if self.price_service and token_mints:
                prices = self.price_service.get_prices(token_mints)
                
            if self.metadata_service and token_mints:
                metadata = self.metadata_service.get_metadata_batch(token_mints)
            
            # Second pass: Construct token accounts with fetched data
            skipped_low_value = 0
            skipped_no_price = 0
            
            for account in data["result"]["value"]:
                account_info = account["account"]["data"]["parsed"]["info"]
                
                # Skip zero balance tokens
                if int(account_info["tokenAmount"]["amount"]) == 0:
                    continue
                
                mint = account_info["mint"]
                amount = float(account_info["tokenAmount"]["uiAmount"] or 0)
                
                # Get price and token value
                price = prices.get(mint, None) if prices else None
                # Resolve realistic price if missing or suspicious $1 for non-stables
                if price is None or (float(price) == 1.0 and mint not in {
                    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'
                }):
                    price = self._resolve_price(mint)
                token_value = amount * price if price is not None else None
                
                # SURGICAL: Only skip tokens with extremely small values (sub-penny)
                if token_value is not None and token_value < 0.001:
                    skipped_low_value += 1
                    continue
                
                # SURGICAL: Allow tokens without price data (removed SKIP_UNKNOWN_TOKENS check)
                # This allows the system to track all tokens, not just those with known prices
                
                # Get metadata
                token_metadata = metadata.get(mint, {}) if metadata else {}
                
                token_accounts.append({
                    "mint": mint,
                    "account": account["pubkey"],  # CRITICAL FIX: Include account address
                    "amount": amount,
                    "raw_amount": int(account_info["tokenAmount"]["amount"]),
                    "decimals": account_info["tokenAmount"]["decimals"],
                    "timestamp": datetime.now().isoformat(),
                    "wallet_address": wallet_address,
                    "price": price,
                    "value_usd": token_value,
                    "symbol": token_metadata.get("symbol", "UNK") if token_metadata else "UNK",
                    "name": token_metadata.get("name", "Unknown Token") if token_metadata else "Unknown Token",
                })

            total_accounts = len(data["result"]["value"])
            total_skipped = skipped_low_value + skipped_no_price
            
            debug(f"Token filtering stats for {wallet_address[:4]}...")
            debug(f"  Total accounts: {total_accounts}")
            debug(f"  Zero balance: {zero_balance_count}")
            debug(f"  Skipped low value: {skipped_low_value}")
            debug(f"  Skipped no price: {skipped_no_price}")
            debug(f"  Final tokens: {len(token_accounts)}")
            
            # CRITICAL FIX: Cache the results to prevent future timeouts
            with self.rpc_cache_lock:
                self.rpc_cache[cache_key] = (token_accounts, current_time)
                # Keep cache size manageable
                if len(self.rpc_cache) > 50:
                    # Remove oldest 10 entries
                    oldest_keys = sorted(self.rpc_cache.keys(), key=lambda k: self.rpc_cache[k][1])[:10]
                    for old_key in oldest_keys:
                        del self.rpc_cache[old_key]
            
            return token_accounts

        except requests.exceptions.RequestException as e:
            error(f"RPC request failed: {str(e)}")
            return []
        except KeyError as e:
            error(f"Invalid response format: {str(e)}")
            return []
        except Exception as e:
            error(f"Unexpected error in get_current_token_accounts: {str(e) if str(e) else 'Unknown error'}")
            error(f"Error type: {type(e).__name__}")
            if hasattr(e, '__traceback__'):
                import traceback
                error(f"Traceback: {traceback.format_exc()}")
            return []

    def get_wallet_activity(self, wallet_address, mint=None, dynamic_threshold=True, max_lookback_minutes=60):
        """
        Fetch and analyze the wallet's transaction history to detect buys and sells.
        """
        info(f"Fetching transaction history for wallet {wallet_address[:4]}...")
        # Add timing monitor
        activity_start_time = time.time()
        last_update = activity_start_time
        
        # We need to make sure BIRDEYE_API_KEY is properly defined
        from src.nice_funcs import get_birdeye_api_key
        
        BIRDEYE_API_KEY = get_birdeye_api_key()
        
        if not BIRDEYE_API_KEY:
            warning("Warning: BIRDEYE_API_KEY not set, cannot check recent activity")
            return {"buys": [], "sells": []}
        
        url = f"https://public-api.birdeye.so/public/transaction_history?address={wallet_address}"
        headers = {"X-API-KEY": BIRDEYE_API_KEY}
        current_time = int(datetime.now().timestamp())
        
        # Calculate dynamic lookback time based on recent activity
        if dynamic_threshold:
            info(f"Starting dynamic lookback search for activity...")
            # Start with a small lookback window (e.g., 5 minutes)
            lookback_minutes = 5
            while lookback_minutes <= max_lookback_minutes:
                # Update on progress every 10 seconds
                current_time_check = time.time()
                if current_time_check - last_update >= 10:
                    elapsed = current_time_check - activity_start_time
                    info(f"Activity search in progress: {elapsed:.1f}s elapsed, checking {lookback_minutes} minute window...")
                    last_update = current_time_check
                    
                lookback_time = int((datetime.now() - timedelta(minutes=lookback_minutes)).timestamp())
                params = {
                    "time_from": lookback_time,
                    "time_to": current_time,
                    "limit": 100  # Limit to the most recent 100 transactions
                }
                if mint:
                    params["mint"] = mint

                try:
                    debug(f"Querying for transactions in {lookback_minutes} minute window...", file_only=True)
                    response = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT_SECONDS)
                    if response.status_code == 200:
                        transactions = response.json().get("data", {}).get("items", [])
                        if transactions:  # Stop if we find transactions
                            break
                    else:
                        info(f"Failed to fetch wallet activity: HTTP {response.status_code}")
                        return {}
                except Exception as e:
                    info(f"Error fetching wallet activity: {str(e)}")
                    return {}

                # Increase lookback time incrementally
                lookback_minutes += 5
                
                # Check if this is taking too long
                total_elapsed = time.time() - activity_start_time
                if total_elapsed > API_TIMEOUT_SECONDS * 2:
                    warning(f"Wallet activity search has been running for {total_elapsed:.2f} seconds")
        else:
            # Use a fixed lookback window (e.g., 1 hour)
            info(f"Using fixed {ACTIVITY_WINDOW_HOURS} hour lookback window for activity...")
            lookback_time = int((datetime.now() - timedelta(hours=ACTIVITY_WINDOW_HOURS)).timestamp())
            params = {
                "time_from": lookback_time,
                "time_to": current_time,
                "limit": 100
            }
            if mint:
                params["mint"] = mint

            try:
                response = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT_SECONDS)
                if response.status_code != 200:
                    info(f"Failed to fetch wallet activity: HTTP {response.status_code}")
                    return {}
                transactions = response.json().get("data", {}).get("items", [])
            except Exception as e:
                info(f"Error fetching wallet activity: {str(e)}")
                return {}

        # Parse transactions
        activity = {"buys": [], "sells": []}
        for tx in transactions:
            tx_type = tx.get("type")  # e.g., "buy", "sell"
            token_mint = tx.get("tokenMint")
            amount = float(tx.get("amount", 0))
            timestamp = tx.get("timestamp")

            if tx_type == "buy":
                activity["buys"].append({
                    "mint": token_mint,
                    "amount": amount,
                    "timestamp": timestamp
                })
            elif tx_type == "sell":
                activity["sells"].append({
                    "mint": token_mint,
                    "amount": amount,
                    "timestamp": timestamp
                })

        # Log completion time
        total_activity_time = time.time() - activity_start_time
        info(f"Detected {len(activity['buys'])} buys and {len(activity['sells'])} sells in the last {lookback_minutes} minutes.")
        debug(f"TIMING: Wallet activity fetched in {total_activity_time:.2f} seconds", file_only=False)
        
        return activity
        
    def filter_relevant_tokens(self, token_accounts: List[Dict]) -> List[Dict]:
        """
        SURGICAL: Simplified token filtering - only filter out obviously broken data
        """
        if not token_accounts:
            return []
            
        relevant_tokens = []
        skipped_count = 0
        skipped_reasons = {"invalid_data": 0, "zero_amount": 0}
        
        for account in token_accounts:
            mint = account["mint"]
            
            # Basic data validation - only filter out obviously broken data
            if not mint or len(mint) < 32:
                skipped_count += 1
                skipped_reasons["invalid_data"] += 1
                debug(f"Skipping token with invalid mint: {mint}", file_only=True)
                continue
            
            # Skip tokens with zero amount (these are meaningless)
            amount = account.get("amount", 0)
            if amount <= 0:
                skipped_count += 1
                skipped_reasons["zero_amount"] += 1
                debug(f"Skipping token {mint[:8]}... - zero amount", file_only=True)
                continue
            
            # SURGICAL: Very permissive USD value check (only filter out extremely small values)
            if "value_usd" in account and account["value_usd"] is not None:
                if account["value_usd"] < 0.001:  # Only filter out sub-penny values
                    skipped_count += 1
                    skipped_reasons["invalid_data"] += 1
                    debug(f"Skipping token {mint[:8]}... - value ${account['value_usd']:.6f} < $0.001", file_only=True)
                    continue
            
            # Token passes basic validation, add to relevant tokens
            relevant_tokens.append(account)
        
        # Simple logging
        info(f"Token filtering: {len(token_accounts)} total -> {len(relevant_tokens)} relevant (skipped {skipped_count})")
        if skipped_count > 0:
            breakdown = ", ".join([f"{reason}: {count}" for reason, count in skipped_reasons.items() if count > 0])
            debug(f"Skip breakdown: {breakdown}", file_only=True)
        
        return relevant_tokens
    
    def detect_changes(self, cached_results, current_results):
        """Detect changes in token balances, including new, removed, and modified tokens."""
        changes = {}
        
        # SURGICAL: Simplified configuration for change detection
        MIN_CHANGE_THRESHOLD = 0.1  # Reduced from 1% to 0.1%
        MIN_USD_CHANGE_THRESHOLD = 0.01  # Reduced from $0.10 to $0.01
        
        # Extract actual wallet data from cache structure
        cached_data = cached_results.get('data', {}) if isinstance(cached_results, dict) else cached_results
        
        # CRITICAL FIX: Use runtime WALLETS_TO_TRACK instead of imported value
        # This fixes the import caching issue where the tracker uses old imported values
        try:
            from src.config import WALLETS_TO_TRACK as runtime_wallets
            wallets_to_process = runtime_wallets
        except ImportError:
            wallets_to_process = WALLETS_TO_TRACK  # Fallback to imported value
        
        for wallet in wallets_to_process:
            # Create maps for easier lookups with all needed data
            # CRITICAL FIX: Track by account address + mint combination, not just mint
            previous_tokens = {}
            current_tokens = {}
            
            # Build previous tokens map with account-level tracking
            for token in cached_data.get(wallet, []):
                account_key = f"{token.get('account', 'unknown')}_{token.get('mint', 'unknown')}"
                previous_tokens[account_key] = token
            
            # Build current tokens map with account-level tracking
            for token in current_results.get(wallet, []):
                account_key = f"{token.get('account', 'unknown')}_{token.get('mint', 'unknown')}"
                current_tokens[account_key] = token

            wallet_changes = {
                "new": {},
                "removed": {},
                "modified": {}
            }

            # Process new tokens (present in current results but not in cache)
            for account_key, token_data in current_tokens.items():
                if account_key not in previous_tokens:
                    # Extract price and calculate USD value
                    price = token_data.get("price", None)
                    amount = token_data.get("amount", 0)
                    
                    # Ensure values are floats
                    try:
                        amount = float(amount) if amount is not None else 0.0
                        price = float(price) if price is not None else None
                    except (TypeError, ValueError):
                        debug(f"Error converting values to float for new token {account_key}", file_only=True)
                        amount = 0.0
                        price = None
                    
                    # Calculate USD value if price is known
                    usd_value = amount * price if price is not None else None
                    
                    wallet_changes["new"][account_key] = {
                        "amount": amount,
                        "symbol": token_data.get("symbol", "UNK"),
                        "name": token_data.get("name", "Unknown Token"),
                        "price": price,
                        "usd_value": usd_value,
                        "mint": token_data.get("mint", "unknown"),
                        "account": token_data.get("account", "unknown")
                    }

            # Process removed tokens (present in cache but not in current results)
            for account_key, token_data in previous_tokens.items():
                if account_key not in current_tokens:
                    # Extract price and calculate USD value
                    price = token_data.get("price", None)
                    amount = token_data.get("amount", 0)
                    
                    # Ensure values are floats
                    try:
                        amount = float(amount) if amount is not None else 0.0
                        price = float(price) if price is not None else None
                    except (TypeError, ValueError):
                        debug(f"Error converting values to float for removed token {account_key}", file_only=True)
                        amount = 0.0
                        price = None
                    
                    # Calculate USD value if price is known
                    usd_value = amount * price if price is not None else None
                    
                    wallet_changes["removed"][account_key] = {
                        "amount": amount,
                        "symbol": token_data.get("symbol", "UNK"),
                        "name": token_data.get("name", "Unknown Token"),
                        "price": price,
                        "usd_value": usd_value,
                        "mint": token_data.get("mint", "unknown"),
                        "account": token_data.get("account", "unknown")
                    }

            # SURGICAL: Enhanced modified token detection with account-level tracking
            for account_key, curr_data in current_tokens.items():
                prev_data = previous_tokens.get(account_key)
                if prev_data is not None:
                    # Use human-readable amounts
                    curr_amount = curr_data.get("amount", 0)
                    prev_amount = prev_data.get("amount", 0)
                    
                    # Ensure amounts are floats
                    try:
                        curr_amount = float(curr_amount) if curr_amount is not None else 0.0
                        prev_amount = float(prev_amount) if prev_amount is not None else 0.0
                    except (TypeError, ValueError):
                        debug(f"Error converting amount to float for token {account_key}", file_only=True)
                        curr_amount = 0.0
                        prev_amount = 0.0
                    
                    # CRITICAL FIX: Detect zero-balance transitions
                    # If previous amount was positive and current is zero, this is a removal
                    if prev_amount > 0.00001 and curr_amount <= 0.00001:
                        # This should be treated as a removal, not a modification
                        debug(f"Zero-balance transition detected for {account_key}: {prev_amount} -> {curr_amount}", file_only=True)
                        # Move to removed tokens instead of modified
                        wallet_changes["removed"][account_key] = {
                            "amount": prev_amount,
                            "symbol": prev_data.get("symbol", "UNK"),
                            "name": prev_data.get("name", "Unknown Token"),
                            "price": prev_data.get("price", None),
                            "usd_value": prev_data.get("price", 0) * prev_amount if prev_data.get("price") else None,
                            "mint": prev_data.get("mint", "unknown"),
                            "account": prev_data.get("account", "unknown"),
                            "transition_type": "zero_balance"
                        }
                        continue
                    
                    # Get prices
                    curr_price = curr_data.get("price", None)
                    prev_price = prev_data.get("price", None)
                    
                    # Ensure prices are floats
                    try:
                        curr_price = float(curr_price) if curr_price is not None else None
                        prev_price = float(prev_price) if prev_price is not None else None
                    except (TypeError, ValueError):
                        debug(f"Error converting price to float for token {account_key}", file_only=True)
                        curr_price = None
                        prev_price = None
                    
                    # Calculate USD values if prices are known
                    curr_usd = curr_amount * curr_price if curr_price is not None else None
                    prev_usd = prev_amount * prev_price if prev_price is not None else None
                    
                    # SURGICAL: Simple change calculation without epsilon
                    amount_change = curr_amount - prev_amount
                    amount_changed = abs(amount_change) > 0.00001  # Simple threshold instead of epsilon
                    
                    # Only calculate price and USD changes if both values are known numbers
                    if curr_price is not None and prev_price is not None:
                        price_change = curr_price - prev_price
                        usd_change = curr_usd - prev_usd if curr_usd is not None and prev_usd is not None else None
                    else:
                        price_change = None
                        usd_change = None
                    
                    # Calculate percentage change if amount changed
                    pct = 0
                    if amount_changed and prev_amount > 0.00001:
                        # Calculate percentage change (preserve sign for increase/decrease)
                        pct = (amount_change / prev_amount) * 100
                        
                        # SURGICAL: Relaxed minimum change threshold
                        if abs(pct) < MIN_CHANGE_THRESHOLD:
                            amount_changed = False
                            pct = 0
                    
                    # USD change significance check
                    usd_change_significant = False
                    if usd_change is not None and abs(usd_change) >= MIN_USD_CHANGE_THRESHOLD:
                        usd_change_significant = True
                    
                    # Log significant changes
                    if abs(pct) > 1:  # Log changes greater than 1%
                        debug(f"Token {account_key}: Previous: {prev_amount}, Current: {curr_amount}, Change: {amount_change}, PCT: {pct:.2f}%", file_only=True)
                    
                    # Detect price status changes
                    price_status_changed = (
                        (prev_price is None and curr_price is not None) or 
                        (prev_price is not None and curr_price is None)
                    )
                    
                    # SURGICAL: Simplified significance check
                    is_significant_change = (
                        amount_changed and (
                            abs(pct) >= MIN_CHANGE_THRESHOLD or  # Percentage threshold
                            usd_change_significant or  # USD threshold
                            abs(amount_change) > prev_amount * 0.001  # At least 0.1% of position
                        )
                    )
                    
                    # SURGICAL: Simplified validation - only reject obviously bad data
                    change_is_valid = True
                    if amount_changed:
                        # Only reject truly suspicious changes (10000x instead of 1000x)
                        if prev_amount > 0:
                            change_ratio = abs(amount_change / prev_amount)
                            if change_ratio > 10000:  # Much more permissive
                                debug(f"Rejecting highly suspicious change for {account_key}: ratio {change_ratio:.2f}", file_only=True)
                                change_is_valid = False
                    
                    # Add to changes if significant and valid
                    if (is_significant_change or price_status_changed) and change_is_valid:
                        wallet_changes["modified"][account_key] = {
                            "previous_amount": prev_amount,
                            "current_amount": curr_amount,
                            "change": amount_change,
                            "pct_change": round(pct, 2),
                            "symbol": curr_data.get("symbol", "UNK"),
                            "name": curr_data.get("name", "Unknown Token"),
                            "previous_price": prev_price,
                            "current_price": curr_price,
                            "price_change": price_change,
                            "usd_change": usd_change,
                            "previous_usd": prev_usd,
                            "current_usd": curr_usd,
                            "mint": curr_data.get("mint", "unknown"),
                            "account": curr_data.get("account", "unknown")
                        }

            # Add wallet to changes if it has any changes
            if any(wallet_changes.values()):
                changes[wallet] = wallet_changes
        
        return changes
    
    def save_change_events(self, changes):
        """Save detected changes to change_events.csv in the format expected by TrackerTab."""
        os.makedirs(os.path.dirname(CHANGE_EVENTS_PATH), exist_ok=True)
        events = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for wallet, wallet_changes in changes.items():
            # New tokens
            for token_mint, details in wallet_changes.get('new', {}).items():
                events.append({
                    'timestamp': timestamp,
                    'event_type': 'NEW',
                    'wallet': wallet[:8] + '...' + wallet[-4:],
                    'token': details.get('name', 'Unknown Token'),
                    'token_symbol': details.get('symbol', 'UNK'),
                    'token_mint': details.get('mint', 'unknown'),
                    'amount': details.get('amount', 0),
                    'change': None,
                    'percent_change': None,
                    'token_name': details.get('name', 'Unknown Token'),
                    'price': details.get('price', 0),
                    'price_change': 0,
                    'usd_change': 0
                })
            # Removed tokens
            for token_mint, details in wallet_changes.get('removed', {}).items():
                usd_value = details.get('usd_value', 0)
                events.append({
                    'timestamp': timestamp,
                    'event_type': 'REMOVED',
                    'wallet': wallet[:8] + '...' + wallet[-4:],
                    'token': details.get('name', 'Unknown Token'),
                    'token_symbol': details.get('symbol', 'UNK'),
                    'token_mint': details.get('mint', 'unknown'),
                    'amount': details.get('amount', 0),
                    'change': None,
                    'percent_change': None,
                    'token_name': details.get('name', 'Unknown Token'),
                    'price': details.get('price', 0),
                    'price_change': 0,
                    'usd_change': -usd_value
                })
            # Modified tokens
            for token_mint, details in wallet_changes.get('modified', {}).items():
                events.append({
                    'timestamp': timestamp,
                    'event_type': 'MODIFIED',
                    'wallet': wallet[:8] + '...' + wallet[-4:],
                    'token': details.get('name', 'Unknown Token'),
                    'token_symbol': details.get('symbol', 'UNK'),
                    'token_mint': details.get('mint', 'unknown'),
                    'amount': details.get('current_amount', 0),
                    'change': details.get('change', 0),
                    'percent_change': details.get('pct_change', 0),
                    'token_name': details.get('name', 'Unknown Token'),
                    'price': details.get('current_price', 0),
                    'price_change': details.get('price_change', 0),
                    'usd_change': details.get('usd_change', 0)
                })
        if not events:
            return
        df = pd.DataFrame(events)
        # If file exists, prepend new events
        if os.path.isfile(CHANGE_EVENTS_PATH):
            existing = pd.read_csv(CHANGE_EVENTS_PATH)
            df = pd.concat([df, existing], ignore_index=True)
            df = df.head(25)  # Limit to 25 records
        df.to_csv(CHANGE_EVENTS_PATH, index=False)

    def track_wallets(self):
        """
        Track token accounts for all wallets in the WALLETS_TO_TRACK list.
        This is the main entry point for the wallet tracker.
        
        Returns tuple: (wallet_results, changes)
        """
        # Track start time for performance monitoring
        start_time = time.time()
        
        system("Anarcho Capital's Wallet Tracker starting up...")
        info(f"Tracking {len(WALLETS_TO_TRACK)} wallets...")

        # Load cache and check if it was newly created
        cached_results, cache_was_empty = self.load_cache()

        # Normalize token lists to handle formatting issues
        normalized_monitored_tokens = [str(token).strip() for token in MONITORED_TOKENS]
        normalized_previous_tokens = [str(token).strip() for token in self.previous_monitored_tokens]
                
        # More robust change detection
        mode_changed = self.previous_mode != DYNAMIC_MODE
        tokens_changed = sorted(normalized_monitored_tokens) != sorted(normalized_previous_tokens)

        if mode_changed or tokens_changed or cache_was_empty:
            if mode_changed:
                info("Mode changed.")
            if tokens_changed:
                info("Monitored tokens list changed.")
            if cache_was_empty:
                info("Cache was empty/missing.")
            
            # Reset only when necessary
            cached_results = {}
            self.previous_monitored_tokens = MONITORED_TOKENS.copy()
            self.previous_mode = DYNAMIC_MODE
            
            # Save updated state immediately
            self.save_cache(cached_results)
        else:
            info("No Mode or Token List change detected.")

        results = {}
        wallet_stats = {}  # Store wallet-specific stats

        # Create a dictionary to track seen wallets (to prevent duplicate logs)
        processed_wallets = set()

        def fetch_wallet_data(wallet):
            """Helper function to fetch data for a single wallet."""
            if wallet in processed_wallets:
                return wallet, [], {'found': 0, 'skipped': 0}
            
            processed_wallets.add(wallet)
            
            if DYNAMIC_MODE:
                info(f"Fetching all token accounts for {wallet}...")
                token_accounts = self.get_current_token_accounts(wallet)
                
                # Get the initial count before filtering 
                total_tokens = len(token_accounts)
                
                # Apply filtering
                filtered_tokens = self.filter_relevant_tokens(token_accounts)
                
                # Calculate stats
                found_tokens = len(filtered_tokens)
                skipped_tokens = total_tokens - found_tokens
                
                # Print a clearer stats line for the UI to parse - Keep this as print for UI parsing
                print(f"TOKEN_STATS: {wallet[:4]} - Found: {found_tokens}, Skipped: {skipped_tokens}")
                
                stats = {'found': found_tokens, 'skipped': skipped_tokens, 'total': total_tokens}
                
                return wallet, filtered_tokens, stats
            else:
                info(f"Fetching token balances for {wallet}...")
                token_balances = self.get_token_balances(wallet)
                
                # Count total valid tokens
                total_valid_tokens = sum(1 for t in token_balances if t['mint'] in MONITORED_TOKENS)
                
                # Filter tokens
                filtered_tokens = [t for t in token_balances if t['mint'] in MONITORED_TOKENS and t['amount'] > 0]
                
                # Calculate stats
                found_tokens = len(filtered_tokens)
                skipped_tokens = total_valid_tokens - found_tokens
                
                # Ensure the stats are properly displayed with wallet address
                info(f"Found {found_tokens} relevant tokens, skipped {skipped_tokens} tokens for {wallet[:4]}")
                
                # Print a clearer stats line for the UI to parse - Keep this as print for UI parsing
                print(f"TOKEN_STATS: {wallet[:4]} - Found: {found_tokens}, Skipped: {skipped_tokens}")
                
                stats = {'found': found_tokens, 'skipped': skipped_tokens, 'total': total_valid_tokens}
                
                return wallet, filtered_tokens, stats

        # SURGICAL OPTIMIZATION: Improved parallel processing for maximum speed
        if USE_PARALLEL_PROCESSING:
            with ThreadPoolExecutor(max_workers=min(6, len(WALLETS_TO_TRACK) + 2)) as executor:
                # Submit all tasks simultaneously for true parallel execution
                futures = {executor.submit(fetch_wallet_data, wallet): wallet for wallet in WALLETS_TO_TRACK}
                
                # Collect results as they complete (no artificial delays)
                for future in as_completed(futures):
                    wallet, parsed_accounts, stats = future.result()
                    # FIXED: Always add wallet to results, even if empty
                    results[wallet] = parsed_accounts
                    wallet_stats[wallet] = stats  # Store stats for this wallet
                    # OPTIMIZATION: No sleep delay - parallel processing handles rate limiting naturally
        else:
            # Process wallets sequentially with minimal delay
            for wallet in WALLETS_TO_TRACK:
                wallet, parsed_accounts, stats = fetch_wallet_data(wallet)
                # FIXED: Always add wallet to results, even if empty
                results[wallet] = parsed_accounts
                wallet_stats[wallet] = stats  # Store stats for this wallet
                # OPTIMIZATION: Reduced sleep from API_SLEEP_SECONDS to 0.5 seconds
                time.sleep(0.5)  # Minimal delay only for sequential processing

        # Detect changes after fetching current results
        changes = self.detect_changes(cached_results, results)
        if changes:
            info("Change detected!")
            for wallet, change in changes.items():
                info(f"Wallet: {wallet}")
                info(f"New Tokens: {len(change['new'])}")
                info(f"Removed Tokens: {len(change['removed'])}")
                info(f"Modified Tokens: {len(change['modified'])}")
            # Save to change_events.csv
            self.save_change_events(changes)
        else:
            info("No changes detected this round.")

        # Prepare cache data with mode information
        cache_data = {
            'mode': DYNAMIC_MODE,        # Store current mode
            'data': results,             # Store wallet data
            'wallet_stats': wallet_stats # Store wallet stats data
        }

        # Save the updated data for next time
        try:
            self.save_cache(cache_data)
        except Exception as e:
            error(f"Failed to save cache: {str(e)}")
        
        # Calculate elapsed time for performance monitoring
        elapsed_time = time.time() - start_time
        info(f"Wallet tracking completed in {elapsed_time:.2f} seconds")
        
        return results, changes  # Return both results and changes

    def initialize_wallet_data(self):
        """
        Initialize wallet data once during system startup.
        This replaces the duplicate fetching in fetch_historical_data.py and copybot_agent.py
        """
        try:
            # Import config for this method
            from src import config
            
            info("🔄 Initializing wallet data for system startup...")
            
            # Check if we're in webhook mode
            if hasattr(config, 'WEBHOOK_MODE') and config.WEBHOOK_MODE:
                info("🔄 WEBHOOK MODE: Performing initial wallet data fetch for baseline")
                info("📡 After initial fetch, system will wait for webhook events")
            
            # Check RPC connectivity first
            if not self._check_rpc_connectivity():
                warning("RPC connectivity check failed - wallet data may be incomplete")
            
            # Fetch wallet data for all tracked wallets
            wallet_results = {}
            total_tokens = 0
            
            for wallet in config.WALLETS_TO_TRACK:
                try:
                    info(f"📊 Fetching data for wallet {wallet[:8]}...")
                    
                    if config.DYNAMIC_MODE:
                        token_accounts = self.get_current_token_accounts(wallet)
                        filtered_tokens = self.filter_relevant_tokens(token_accounts)
                        wallet_results[wallet] = filtered_tokens
                    else:
                        token_balances = self.get_token_balances(wallet)
                        filtered_tokens = [t for t in token_balances if t['mint'] in config.MONITORED_TOKENS and t['amount'] > 0]
                        wallet_results[wallet] = filtered_tokens
                    
                    token_count = len(wallet_results[wallet])
                    total_tokens += token_count
                    info(f"Found {token_count} valid tokens for wallet {wallet[:8]}...")
                    
                except Exception as e:
                    error(f"Error fetching data for wallet {wallet[:8]}...: {str(e)}")
                    wallet_results[wallet] = []
                    continue
            
            # CRITICAL FIX: Save baseline data to cache for webhook change detection
            if wallet_results:
                info("💾 Saving baseline wallet data to cache...")
                cache_data = {
                    'mode': config.DYNAMIC_MODE,
                    'data': wallet_results,
                    'wallet_stats': {wallet: {'found': len(tokens), 'skipped': 0, 'total': len(tokens)} 
                                   for wallet, tokens in wallet_results.items()},
                    'initialized_at': datetime.now().isoformat(),
                    'timestamp': datetime.now().isoformat(),
                    'previous_monitored_tokens': []  # Initialize empty list
                }
                
                # Ensure the cache file is properly written
                try:
                    self.save_cache(cache_data)
                    info(f"✅ Baseline data saved for {len(wallet_results)} wallets ({total_tokens} total tokens)")
                    
                    # Verify the cache was written
                    if os.path.exists(self.cache_file):
                        with open(self.cache_file, 'r') as f:
                            saved_data = json.load(f)
                        info(f"✅ Cache verification: {len(saved_data.get('data', {}))} wallets saved")
                    else:
                        warning("⚠️ Cache file not found after save operation")
                        
                except Exception as save_error:
                    error(f"❌ Failed to save cache: {save_error}")
                    # Try to save to backup location
                    try:
                        backup_file = self.cache_file.replace('.json', '_backup.json')
                        with open(backup_file, 'w') as f:
                            json.dump(cache_data, f, indent=2)
                        info(f"✅ Saved backup cache to {backup_file}")
                    except Exception as backup_error:
                        error(f"❌ Backup save also failed: {backup_error}")
            else:
                warning("No wallet data to save")
            
            # Start background price fetching for personal wallet tokens only
            self._start_background_price_fetching(wallet_results)
            
            info("✅ Wallet data initialization completed")
            if config.WEBHOOK_MODE:
                info("🚀 INITIAL WALLET FETCHING COMPLETED - SYSTEM IS NOW WAITING FOR WEBHOOK EVENTS")
                info("📡 System will only execute trades when triggered by webhook events")
                info("🔔 No automatic polling or change detection will occur")
            
            return wallet_results
            
        except Exception as e:
            error(f"Error initializing wallet data: {str(e)}")
            return {}
    
    def _check_rpc_connectivity(self):
        """Check RPC connectivity before attempting wallet operations"""
        try:
            # Test with a simple getHealth request
            result = self.api_manager.make_rpc_request("getHealth", [])
            
            if result and 'result' in result and result['result'] == 'ok':
                info("RPC connectivity check passed")
                return True
            else:
                warning(f"RPC health check failed: {result}")
                return False
                
        except Exception as e:
            warning(f"RPC connectivity check failed: {str(e)}")
            return False
    
    def _start_background_price_fetching(self, wallet_results):
        """Start background price fetching for personal wallet tokens only"""
        try:
            # Import config to get personal wallet address
            from src import config
            
            # Only fetch prices for tokens in your personal wallet
            personal_wallet = getattr(config, 'DEFAULT_WALLET_ADDRESS', None)
            if not personal_wallet:
                info("No personal wallet configured - skipping background price fetching")
                return
            
            # Extract token addresses from personal wallet only
            personal_tokens = set()
            if personal_wallet in wallet_results:
                for token_data in wallet_results[personal_wallet]:
                    token_address = token_data.get('mint')
                    if token_address:
                        personal_tokens.add(token_address)
            
            if not personal_tokens:
                info("No tokens found in personal wallet for background price fetching")
                return
            
            info(f"🔄 Starting background price fetching for {len(personal_tokens)} personal wallet tokens...")
            info("💡 Only fetching prices for tokens you actually own")
            
            # Start background thread for price fetching
            import threading
            price_thread = threading.Thread(
                target=self._background_price_fetch_worker,
                args=(list(personal_tokens),),
                daemon=True
            )
            price_thread.start()
            
            info("✅ Background price fetching started successfully")
            
        except Exception as e:
            error(f"Error starting background price fetching: {str(e)}")

    def _background_price_fetch_worker(self, token_addresses):
        """Background worker for fetching prices - personal wallet tokens only"""
        try:
            info(f"🔄 Background price fetching: Processing {len(token_addresses)} personal wallet tokens...")
            
            # Process tokens in batches to avoid overwhelming the API
            batch_size = 20
            processed = 0
            
            for i in range(0, len(token_addresses), batch_size):
                batch = token_addresses[i:i+batch_size]
                
                # Fetch prices for this batch using the price service
                if self.price_service:
                    prices = self.price_service.get_prices(batch)
                    
                    # Count successful price fetches
                    successful = sum(1 for price in prices.values() if price is not None)
                    processed += len(batch)
                    
                    # Log progress every 50 tokens (smaller batches for personal wallet)
                    if processed % 50 == 0 or processed == len(token_addresses):
                        info(f"🔄 Background price fetching: {processed}/{len(token_addresses)} personal tokens processed")
                    
                    # Small delay between batches to be respectful to APIs
                    time.sleep(0.5)
            
            info(f"✅ Background price fetching completed: {len(token_addresses)} personal wallet tokens processed")
            info("💡 Shared price service will continue updating personal wallet prices every 5-15 minutes")
            
        except Exception as e:
            error(f"Error in background price fetching: {str(e)}")


# Main function to demonstrate usage of the wallet tracker
def main():
    """
    Main function to run the wallet tracker independently.
    Useful for testing and cron jobs.
    """
    # Create the wallet tracker
    tracker = WalletTracker()
    
    # Track wallets and detect changes
    results, changes = tracker.track_wallets()
    
    # Display summary
    total_tokens = sum(len(tokens) for wallet, tokens in results.items())
    total_changes = sum(
        len(change.get('new', {})) + 
        len(change.get('removed', {})) + 
        len(change.get('modified', {})) 
        for wallet, change in changes.items()
    ) if changes else 0
    
    print(f"\nSummary:")
    print(f"Tracked {len(WALLETS_TO_TRACK)} wallets")
    print(f"Found {total_tokens} tokens in total")
    print(f"Detected {total_changes} changes")
    
    return results, changes

if __name__ == "__main__":
    main()