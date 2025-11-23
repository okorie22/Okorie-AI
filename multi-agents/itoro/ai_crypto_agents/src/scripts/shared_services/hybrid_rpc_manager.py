#!/usr/bin/env python3
"""
🌙 Anarcho Capital's Hybrid RPC Manager
Uses QuickNode for personal wallet monitoring and Helius for tracked wallet monitoring
Built with love by Anarcho Capital 🚀
"""

import os
import requests
import time
from typing import Optional, Dict, Any
from src.scripts.shared_services.logger import debug, info, warning, error
from src.scripts.shared_services.shared_api_manager import get_shared_api_manager

class HybridRPCManager:
    """
    Hybrid RPC manager that uses different endpoints for different purposes:
    - QuickNode: Personal wallet monitoring (reliable for your wallet)
    - Helius: Tracked wallet monitoring (reliable for external wallets)
    """
    
    def __init__(self):
        """Initialize the hybrid RPC manager"""
        self.quicknode_url = os.getenv('QUICKNODE_RPC_ENDPOINT')
        self.helius_url = os.getenv('RPC_ENDPOINT')  # This is actually Helius
        
        # Alternative mainnet RPC endpoints for better reliability
        self.alternative_mainnet_rpcs = [
            "https://api.mainnet-beta.solana.com",
            "https://solana-api.projectserum.com",
            "https://rpc.ankr.com/solana"
        ]
        
        # Track which endpoint works best for which wallet
        self.wallet_endpoint_preferences = {}
        
        # Performance tracking
        self.endpoint_performance = {
            'quicknode': {'success': 0, 'failure': 0, 'avg_time': 0},
            'helius': {'success': 0, 'failure': 0, 'avg_time': 0},
            'alternative': {'success': 0, 'failure': 0, 'avg_time': 0}
        }
        
        info("Hybrid RPC Manager initialized")
        info(f"QuickNode URL: {self.quicknode_url[:50] if self.quicknode_url else 'Not set'}...")
        info(f"Helius URL: {self.helius_url[:50] if self.helius_url else 'Not set'}...")
        info(f"Alternative mainnet RPCs: {len(self.alternative_mainnet_rpcs)} available")
    
    def get_best_endpoint_for_wallet(self, wallet_address: str) -> str:
        """
        Determine the best RPC endpoint for a specific wallet
        
        Args:
            wallet_address: The wallet address to get endpoint for
            
        Returns:
            The best RPC endpoint URL for this wallet
        """
        # Check if we have a preference for this wallet
        if wallet_address in self.wallet_endpoint_preferences:
            preferred_endpoint = self.wallet_endpoint_preferences[wallet_address]
            if preferred_endpoint == 'quicknode' and self.quicknode_url:
                return self.quicknode_url
            elif preferred_endpoint == 'helius' and self.helius_url:
                return self.helius_url
        
        # Default strategy: QuickNode for personal wallet, Helius for others
        personal_wallet = os.getenv('DEFAULT_WALLET_ADDRESS')
        if wallet_address == personal_wallet:
            # Personal wallet: prefer QuickNode
            if self.quicknode_url:
                return self.quicknode_url
            elif self.helius_url:
                return self.helius_url
        else:
            # Tracked wallet: prefer Helius
            if self.helius_url:
                return self.helius_url
            elif self.quicknode_url:
                return self.quicknode_url
        
        # Fallback to any available endpoint
        return self.quicknode_url or self.helius_url or "https://api.mainnet-beta.solana.com"
    
    def try_alternative_mainnet_rpcs(self, method: str, params: list, timeout: int = 15) -> Optional[Dict[str, Any]]:
        """
        Try alternative mainnet RPC endpoints when primary endpoints fail
        
        Args:
            method: RPC method name
            params: RPC parameters
            timeout: Request timeout in seconds
            
        Returns:
            RPC response or None if all alternative endpoints failed
        """
            
        info("🔄 Trying alternative mainnet RPC endpoints...")
        
        for i, rpc_url in enumerate(self.alternative_mainnet_rpcs):
            try:
                info(f"🔄 Alternative RPC {i+1}/{len(self.alternative_mainnet_rpcs)}: {rpc_url[:50]}...")
                
                payload = {
                    "jsonrpc": "2.0",
                    "id": f"alternative-rpc-{int(time.time())}",
                    "method": method,
                    "params": params
                }
                
                response = requests.post(
                    rpc_url,
                    json=payload,
                    timeout=timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check for RPC error in response
                    if 'error' in data:
                        error_msg = data['error'].get('message', 'Unknown RPC error')
                        warning(f"Alternative RPC {i+1} error: {error_msg}")
                        continue
                    
                    # Success - record performance
                    self.endpoint_performance['alternative']['success'] += 1
                    info(f"✅ Alternative RPC {i+1} successful")
                    return data
                    
                else:
                    warning(f"Alternative RPC {i+1} HTTP {response.status_code}")
                    continue
                    
            except Exception as e:
                warning(f"Alternative RPC {i+1} failed: {str(e)}")
                continue
        
        warning("All alternative mainnet RPC endpoints failed")
        return None
    
    def make_rpc_request(self, method: str, params: list, wallet_address: str = None, timeout: int = 15) -> Optional[Dict[str, Any]]:
        """
        Make an RPC request using the best endpoint for the wallet with automatic fallback
        
        Args:
            method: RPC method name
            params: RPC parameters
            wallet_address: Wallet address (for endpoint selection)
            timeout: Request timeout in seconds
            
        Returns:
            RPC response or None if all endpoints failed
        """
        # Define endpoint priority for fallback
        endpoints_to_try = []
        
        if wallet_address:
            # Use wallet-specific endpoint selection
            primary_endpoint = self.get_best_endpoint_for_wallet(wallet_address)
            if primary_endpoint == self.helius_url:
                endpoints_to_try = [
                    ('helius', self.helius_url),
                    ('quicknode', self.quicknode_url)
                ]
            else:
                endpoints_to_try = [
                    ('quicknode', self.quicknode_url),
                    ('helius', self.helius_url)
                ]
        else:
            # Default priority: Helius first, then QuickNode
            endpoints_to_try = [
                ('helius', self.helius_url),
                ('quicknode', self.quicknode_url)
            ]
        
        # Try each endpoint with automatic fallback
        for endpoint_name, endpoint_url in endpoints_to_try:
            if not endpoint_url:
                continue
                
            debug(f"Trying {endpoint_name} RPC endpoint for wallet {wallet_address[:8] if wallet_address else 'unknown'}...", file_only=True)
            
            payload = {
                "jsonrpc": "2.0",
                "id": f"hybrid-rpc-{int(time.time())}",
                "method": method,
                "params": params
            }
            
            start_time = time.time()
            
            try:
                response = requests.post(
                    endpoint_url,
                    json=payload,
                    timeout=timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                request_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check for RPC error in response
                    if 'error' in data:
                        error_msg = data['error'].get('message', 'Unknown RPC error')
                        warning(f"RPC error from {endpoint_name}: {error_msg}")
                        self._record_failure(endpoint_name, request_time)
                        continue  # Try next endpoint
                    
                    # Success - record performance
                    self._record_success(endpoint_name, request_time)
                    
                    # Store preference for this wallet if successful
                    if wallet_address:
                        self.wallet_endpoint_preferences[wallet_address] = endpoint_name
                    
                    debug(f"✅ {endpoint_name} RPC request successful", file_only=True)
                    return data
                
                elif response.status_code == 401:
                    # Authentication failed - try next endpoint
                    debug(f"Auth failed for {endpoint_name} (HTTP 401), trying next endpoint", file_only=True)
                    self._record_failure(endpoint_name, request_time)
                    continue  # Try next endpoint
                    
                else:
                    warning(f"HTTP {response.status_code} from {endpoint_name} RPC endpoint")
                    self._record_failure(endpoint_name, request_time)
                    continue  # Try next endpoint
                    
            except requests.exceptions.Timeout:
                warning(f"Timeout from {endpoint_name} RPC endpoint")
                self._record_failure(endpoint_name, request_time)
                continue  # Try next endpoint
                
            except requests.exceptions.RequestException as e:
                warning(f"Request error from {endpoint_name} RPC endpoint: {str(e)}")
                self._record_failure(endpoint_name, request_time)
                continue  # Try next endpoint
        
        # All endpoints failed
        error(f"All RPC endpoints failed for method: {method}")
        return None
    
    def _record_success(self, endpoint_name: str, request_time: float):
        """Record successful request performance"""
        if endpoint_name in self.endpoint_performance:
            perf = self.endpoint_performance[endpoint_name]
            perf['success'] += 1
            
            # Update average time
            if perf['success'] == 1:
                perf['avg_time'] = request_time
            else:
                perf['avg_time'] = (perf['avg_time'] * (perf['success'] - 1) + request_time) / perf['success']
    
    def _record_failure(self, endpoint_name: str, request_time: float):
        """Record failed request performance"""
        if endpoint_name in self.endpoint_performance:
            perf = self.endpoint_performance[endpoint_name]
            perf['failure'] += 1
    
    def get_wallet_token_accounts(self, wallet_address: str) -> Optional[list]:
        """
        Get token accounts for a wallet using hybrid RPC strategy
        
        Args:
            wallet_address: Wallet address to get token accounts for
            
        Returns:
            List of token account info or None if failed
        """
        params = [
            wallet_address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
        
        result = self.make_rpc_request("getTokenAccountsByOwner", params, wallet_address)
        
        if result and 'result' in result and result['result']['value']:
            accounts = []
            for account in result['result']['value']:
                account_info = account['account']['data']['parsed']['info']
                if float(account_info['tokenAmount']['amount']) > 0:
                    accounts.append({
                        'mint': account_info['mint'],
                        'amount': float(account_info['tokenAmount']['uiAmountString']),
                        'decimals': account_info['tokenAmount']['decimals']
                    })
            return accounts
        
        return []
    
    def get_sol_balance(self, wallet_address: str) -> float:
        """
        Get SOL balance for a wallet using hybrid RPC strategy
        
        Args:
            wallet_address: Wallet address to get SOL balance for
            
        Returns:
            SOL balance as float
        """
        params = [wallet_address]
        
        result = self.make_rpc_request("getBalance", params, wallet_address)
        
        if result and 'result' in result and 'value' in result['result']:
            balance_lamports = result['result']['value']
            balance_sol = balance_lamports / 1_000_000_000  # Convert lamports to SOL
            return balance_sol
        
        return 0.0
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for both endpoints"""
        stats = {}
        
        for endpoint, perf in self.endpoint_performance.items():
            total_requests = perf['success'] + perf['failure']
            if total_requests > 0:
                success_rate = (perf['success'] / total_requests) * 100
                stats[endpoint] = {
                    'success_rate': f"{success_rate:.1f}%",
                    'total_requests': total_requests,
                    'successful_requests': perf['success'],
                    'failed_requests': perf['failure'],
                    'avg_response_time': f"{perf['avg_time']:.3f}s"
                }
            else:
                stats[endpoint] = {
                    'success_rate': "0.0%",
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'avg_response_time': "0.000s"
                }
        
        return stats
    
    def print_performance_report(self):
        """Print a performance report for both endpoints"""
        stats = self.get_performance_stats()
        
        info("📊 Hybrid RPC Performance Report:")
        print("=" * 50)
        
        for endpoint, perf in stats.items():
            print(f"{endpoint.upper()}:")
            print(f"  Success Rate: {perf['success_rate']}")
            print(f"  Total Requests: {perf['total_requests']}")
            print(f"  Successful: {perf['successful_requests']}")
            print(f"  Failed: {perf['failed_requests']}")
            print(f"  Avg Response Time: {perf['avg_response_time']}")
            print()
        
        # Show wallet preferences
        if self.wallet_endpoint_preferences:
            print("🎯 Wallet Endpoint Preferences:")
            for wallet, endpoint in self.wallet_endpoint_preferences.items():
                print(f"  {wallet[:8]}...: {endpoint}")

# Global instance
_hybrid_rpc_manager = None

def get_hybrid_rpc_manager() -> HybridRPCManager:
    """Get the global hybrid RPC manager instance"""
    global _hybrid_rpc_manager
    if _hybrid_rpc_manager is None:
        _hybrid_rpc_manager = HybridRPCManager()
    return _hybrid_rpc_manager

def test_hybrid_rpc():
    """Test the hybrid RPC manager"""
    print("🧪 Testing Hybrid RPC Manager")
    print("=" * 40)
    
    manager = get_hybrid_rpc_manager()
    
    # Test personal wallet
    personal_wallet = os.getenv('DEFAULT_WALLET_ADDRESS')
    if personal_wallet:
        print(f"\n🔍 Testing personal wallet: {personal_wallet[:8]}...")
        
        # Test SOL balance
        sol_balance = manager.get_sol_balance(personal_wallet)
        print(f"SOL Balance: {sol_balance:.6f} SOL")
        
        # Test token accounts
        token_accounts = manager.get_wallet_token_accounts(personal_wallet)
        print(f"Token Accounts: {len(token_accounts)} found")
        
        for account in token_accounts[:3]:  # Show first 3
            print(f"  - {account['mint'][:8]}...: {account['amount']}")
    
    # Test tracked wallet (if configured)
    from src.config import WALLETS_TO_TRACK
    if WALLETS_TO_TRACK:
        test_wallet = WALLETS_TO_TRACK[0]
        print(f"\n🔍 Testing tracked wallet: {test_wallet[:8]}...")
        
        # Test SOL balance
        sol_balance = manager.get_sol_balance(test_wallet)
        print(f"SOL Balance: {sol_balance:.6f} SOL")
        
        # Test token accounts
        token_accounts = manager.get_wallet_token_accounts(test_wallet)
        print(f"Token Accounts: {len(token_accounts)} found")
        
        for account in token_accounts[:3]:  # Show first 3
            print(f"  - {account['mint'][:8]}...: {account['amount']}")
    
    # Print performance report
    print("\n" + "=" * 40)
    manager.print_performance_report()

if __name__ == "__main__":
    test_hybrid_rpc() 