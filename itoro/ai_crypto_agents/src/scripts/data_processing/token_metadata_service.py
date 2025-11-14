"""
Token Metadata Service for Anarcho Capital's Trading Desktop App
Provides efficient token metadata fetching with extended caching
"""

import os
import time
import requests
import json
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration values and logging
try:
    from src.config import (
        SKIP_UNKNOWN_TOKENS,
        USE_PARALLEL_PROCESSING,
        BATCH_SIZE
    )
    from src.scripts.shared_services.logger import debug, info, warning, error
except ImportError:
    # Default values if config import fails
    SKIP_UNKNOWN_TOKENS = True
    USE_PARALLEL_PROCESSING = True
    BATCH_SIZE = 50

    # Simple debug function fallback
    def debug(msg, file_only=False):
        print(f"DEBUG: {msg}")

class TokenMetadataService:
    """
    Efficient token metadata service with extended caching
    """
    
    def __init__(self, cache_days=7, batch_size=None):
        """Initialize the token metadata service with the specified settings"""
        # Default cache period is 7 days since token metadata rarely changes
        self.cache_days = int(os.getenv("METADATA_CACHE_DAYS", cache_days))

        # Use batch size from config or parameter
        self.batch_size = batch_size or BATCH_SIZE

        # Initialize metadata cache
        self.metadata_cache = {}
        self.metadata_cache_expiry = {}
        self.cache_lock = threading.Lock()

        # Get Birdeye API key
        self.birdeye_api_key = os.getenv("BIRDEYE_API_KEY")
        if not self.birdeye_api_key:
            print("⚠️ BIRDEYE_API_KEY not found - falling back to RPC metadata")

        # Common token metadata (pre-populated for efficiency)
        self.common_tokens = self._initialize_common_tokens()

        # Service is ready when initialized
        self._ready = True

        # Use a simpler initialization message
        debug("Token Metadata Service initialized")
    
    def _initialize_common_tokens(self) -> Dict[str, Dict[str, str]]:
        """Pre-populate metadata for common tokens"""
        return {
            # SOL token
            "So11111111111111111111111111111111111111112": {
                "symbol": "SOL",
                "name": "Solana",
                "decimals": 9,
                "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"
            },
            # USDC token
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {
                "symbol": "USDC",
                "name": "USD Coin",
                "decimals": 6,
                "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v/logo.png"
            },
            # USDT token
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {
                "symbol": "USDT",
                "name": "USDT",
                "decimals": 6,
                "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB/logo.png"
            },
            # BONK token
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": {
                "symbol": "BONK",
                "name": "Bonk",
                "decimals": 5,
                "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263/logo.png"
            },
            # FART token for Anarcho Capital
            "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump": {
                "symbol": "FART",
                "name": "FARTCOIN",
                "decimals": 9,
                "logo": ""
            }
        }
    
    def get_metadata(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a single token with caching
        Returns None if metadata cannot be found
        """
        # Handle staked SOL specially
        if token_mint.startswith("STAKED_SOL_"):
            return {
                'address': token_mint,
                'symbol': 'stSOL',
                'name': 'Staked SOL',
                'decimals': 9,
                'is_staked_sol': True
            }
        
        # Fast path: Check if token is in common tokens
        if token_mint in self.common_tokens:
            return self.common_tokens[token_mint]
            
        # Check if metadata is in cache and still valid
        cached_metadata = self._get_from_cache(token_mint)
        if cached_metadata is not None:
            return cached_metadata
            
        # Get metadata in batch for efficiency (even for single token)
        metadata_dict = self.get_metadata_batch([token_mint])
        return metadata_dict.get(token_mint)
    
    def get_metadata_batch(self, token_mints: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get metadata for multiple tokens in an efficient batch
        Returns a dictionary mapping token mints to metadata (or None if not found)
        """
        if not token_mints:
            return {}
            
        # Remove duplicates while preserving order
        unique_tokens = list(dict.fromkeys(token_mints))
        
        # Check common tokens and cache first
        result = {}
        tokens_to_fetch = []
        
        for mint in unique_tokens:
            # Check common tokens first (fastest path)
            if mint in self.common_tokens:
                result[mint] = self.common_tokens[mint]
                continue
                
            # Check cache
            cached_metadata = self._get_from_cache(mint)
            if cached_metadata is not None:
                result[mint] = cached_metadata
            else:
                tokens_to_fetch.append(mint)
        
        # If all metadata was in cache or common tokens, return immediately
        if not tokens_to_fetch:
            return result
            
        # Process remaining tokens in batches
        if USE_PARALLEL_PROCESSING:
            # Process batches in parallel
            with ThreadPoolExecutor(max_workers=min(10, len(tokens_to_fetch))) as executor:
                for i in range(0, len(tokens_to_fetch), self.batch_size):
                    batch = tokens_to_fetch[i:i + self.batch_size]
                    
                    # Process tokens within batch in parallel
                    future_to_mint = {
                        executor.submit(self._fetch_token_metadata, mint): mint 
                        for mint in batch
                    }
                    
                    for future in as_completed(future_to_mint):
                        mint = future_to_mint[future]
                        try:
                            metadata = future.result()
                            result[mint] = metadata
                            self._cache_metadata({mint: metadata})
                        except Exception as e:
                            print(f"Error fetching metadata for {mint}: {str(e)}")
                            result[mint] = None
                            
                            # Cache failures too, but for a shorter period
                            self._cache_metadata({mint: None}, is_failure=True)
        else:
            # Process batches sequentially
            for i in range(0, len(tokens_to_fetch), self.batch_size):
                batch = tokens_to_fetch[i:i + self.batch_size]
                
                for mint in batch:
                    metadata = self._fetch_token_metadata(mint)
                    result[mint] = metadata
                    self._cache_metadata({mint: metadata})
                    
        return result
    
    def _fetch_token_metadata(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata for a single token using Birdeye API (preferred) or RPC fallback"""

        # Try Birdeye API first (much better metadata)
        if self.birdeye_api_key:
            try:
                url = f"https://public-api.birdeye.so/defi/token_overview?address={token_mint}"
                headers = {"X-API-KEY": self.birdeye_api_key}

                response = requests.get(url, headers=headers, timeout=5)

                if response.status_code == 200:
                    data = response.json()

                    if data.get("success") and data.get("data"):
                        token_data = data["data"]
                        metadata = {
                            "symbol": token_data.get("symbol", "UNK"),
                            "name": token_data.get("name", "Unknown Token"),
                            "decimals": int(token_data.get("decimals", 9)),
                            "logo": token_data.get("logo", "")
                        }
                        return metadata

            except Exception as e:
                debug(f"Birdeye metadata fetch failed for {token_mint[:8]}...: {str(e)}", file_only=True)

        # Fallback to RPC method if Birdeye fails or is not available
        try:
            # Get RPC endpoint for fallback
            rpc_endpoint = os.getenv("RPC_ENDPOINT")
            if not rpc_endpoint:
                debug(f"No RPC endpoint available for fallback metadata for {token_mint[:8]}...", file_only=True)
                if SKIP_UNKNOWN_TOKENS:
                    return None
                else:
                    return {"symbol": "UNK", "name": "Unknown Token", "decimals": 9, "logo": ""}

            # Use RPC to get token metadata
            payload = {
                "jsonrpc": "2.0",
                "id": "anarcho-metadata",
                "method": "getAccountInfo",
                "params": [
                    token_mint,
                    {"encoding": "jsonParsed"}
                ]
            }

            response = requests.post(rpc_endpoint, json=payload, timeout=5)

            if response.status_code == 200:
                data = response.json()

                if "result" in data and data["result"]["value"]:
                    # Extract metadata
                    account_data = data["result"]["value"]
                    program_id = account_data.get("owner")

                    # Check if it's a token account
                    if program_id == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA":
                        parsed_data = account_data.get("data", {}).get("parsed", {}).get("info", {})
                        metadata = {
                            "symbol": parsed_data.get("symbol", "UNK"),
                            "name": parsed_data.get("name", "Unknown Token"),
                            "decimals": int(parsed_data.get("decimals", 9)),
                            "logo": ""  # No logo in basic metadata
                        }
                        return metadata

            # Return default values if metadata not found
            if SKIP_UNKNOWN_TOKENS:
                return None
            else:
                return {"symbol": "UNK", "name": "Unknown Token", "decimals": 9, "logo": ""}

        except requests.exceptions.Timeout:
            debug(f"Timeout fetching metadata for {token_mint[:8]}... (5s timeout)", file_only=True)
            if SKIP_UNKNOWN_TOKENS:
                return None
            else:
                return {"symbol": "UNK", "name": "Unknown Token", "decimals": 9, "logo": ""}
        except Exception as e:
            debug(f"Error fetching metadata for {token_mint[:8]}...: {str(e)}", file_only=True)

            # Return default values on error if not skipping unknown tokens
            if SKIP_UNKNOWN_TOKENS:
                return None
            else:
                return {"symbol": "UNK", "name": "Unknown Token", "decimals": 9, "logo": ""}
    
    def _cache_metadata(self, metadata_dict: Dict[str, Optional[Dict[str, Any]]], is_failure=False) -> None:
        """Save metadata to cache with expiry time"""
        if not metadata_dict:
            return
            
        current_time = time.time()
        
        # Regular cache period is days, failures cache for hours
        if is_failure:
            expiry_time = current_time + (4 * 3600)  # 4 hours for failures
        else:
            expiry_time = current_time + (self.cache_days * 24 * 3600)  # Days for successful lookups
        
        # Use a lock to ensure thread safety when updating the cache
        with self.cache_lock:
            for mint, metadata in metadata_dict.items():
                self.metadata_cache[mint] = metadata
                self.metadata_cache_expiry[mint] = expiry_time
    
    def _get_from_cache(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Check if metadata is in cache and still valid"""
        current_time = time.time()
        
        with self.cache_lock:
            if token_mint in self.metadata_cache and self.metadata_cache_expiry.get(token_mint, 0) > current_time:
                return self.metadata_cache[token_mint]
                
        return None
    
    def clear_cache(self) -> None:
        """Clear the metadata cache"""
        with self.cache_lock:
            self.metadata_cache = {}
            self.metadata_cache_expiry = {}
            
        print("Metadata cache cleared")
    
    def get_token_name(self, token_mint: str) -> str:
        """Convenience method to get just the token name"""
        metadata = self.get_metadata(token_mint)
        if metadata:
            return metadata.get("name", "Unknown Token")
        return "Unknown Token"
    
    def get_token_symbol(self, token_mint: str) -> str:
        """Convenience method to get just the token symbol"""
        # Handle staked SOL specially
        if token_mint.startswith("STAKED_SOL_"):
            return 'stSOL'
        
        metadata = self.get_metadata(token_mint)
        if metadata:
            return metadata.get("symbol", "UNK")
        return "UNK"
    
    def get_token_decimals(self, token_mint: str) -> int:
        """Convenience method to get just the token decimals"""
        metadata = self.get_metadata(token_mint)
        if metadata:
            # Ensure return value is an integer
            return int(metadata.get("decimals", 9))
        return 9
    
    def is_ready(self) -> bool:
        """Check if the service is ready to handle requests"""
        return self._ready and (self.birdeye_api_key is not None or os.getenv("RPC_ENDPOINT") is not None)

# Simple usage example
if __name__ == "__main__":
    # Create metadata service
    metadata_service = TokenMetadataService(cache_days=7)
    
    # Example tokens to test
    test_tokens = [
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "So11111111111111111111111111111111111111112",   # SOL
        "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"   # FART
    ]
    
    # Test batch metadata lookup
    metadata_batch = metadata_service.get_metadata_batch(test_tokens)
    
    print("\nTest Results:")
    for mint, metadata in metadata_batch.items():
        if metadata:
            print(f"Token: {mint}, Symbol: {metadata.get('symbol')}, Name: {metadata.get('name')}")
        else:
            print(f"Token: {mint}, Metadata: Not found")


# Singleton factory function
_metadata_service_instance = None

def get_token_metadata_service() -> TokenMetadataService:
    """Get singleton instance of token metadata service"""
    global _metadata_service_instance
    if _metadata_service_instance is None:
        _metadata_service_instance = TokenMetadataService()
    return _metadata_service_instance