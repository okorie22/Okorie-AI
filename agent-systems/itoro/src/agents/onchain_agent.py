"""
🔗 OnChain Agent
Collects per-token on-chain metrics for open positions
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agents.base_agent import BaseAgent
from src.scripts.shared_services.logger import debug, info, warning, error
from src.scripts.shared_services.redis_event_bus import get_event_bus
from src.scripts.shared_services.alert_system import MarketAlert, AlertType, AlertSeverity
from src.config import (
    TOKEN_ONCHAIN_ENABLED,
    TOKEN_ONCHAIN_DATA_FILE,
    TOKEN_ONCHAIN_CACHE_HOURS,
    TOKEN_ONCHAIN_MIN_LIQUIDITY_USD,
    TOKEN_ONCHAIN_MAX_TOKENS,
    TOKEN_ONCHAIN_INCLUDE_WHALE_DATA,
    TOKEN_ONCHAIN_GROWTH_THRESHOLD,
    TOKEN_ONCHAIN_STALE_THRESHOLD,
    TOKEN_ONCHAIN_WHALE_CONCENTRATION_HIGH,
    TOKEN_ONCHAIN_BIRDEYE_TIMEOUT,
    TOKEN_ONCHAIN_HELIUS_TIMEOUT,
    TOKEN_ONCHAIN_RETRY_ATTEMPTS,
    EXCLUDED_TOKENS
)

load_dotenv()

class OnChainAgent(BaseAgent):
    """
    Collects on-chain metrics for tokens in open positions
    - Holder count and growth trends
    - Transaction volume
    - Liquidity depth
    - Whale concentration
    """
    
    def __init__(self):
        """Initialize the OnChain Agent"""
        super().__init__("onchain")
        
        # Configuration
        self.enabled = TOKEN_ONCHAIN_ENABLED
        self.data_file = project_root / TOKEN_ONCHAIN_DATA_FILE
        self.historical_data_file = project_root / "src/data/token_onchain_history.json"
        self.cache_ttl_hours = TOKEN_ONCHAIN_CACHE_HOURS
        self.min_liquidity = TOKEN_ONCHAIN_MIN_LIQUIDITY_USD
        self.max_tokens = TOKEN_ONCHAIN_MAX_TOKENS
        self.include_whale_data = TOKEN_ONCHAIN_INCLUDE_WHALE_DATA
        self.retry_attempts = TOKEN_ONCHAIN_RETRY_ATTEMPTS
        
        # API clients (loaded from environment)
        self.birdeye_api_key = os.getenv('BIRDEYE_API_KEY', '')
        self.helius_api_key = os.getenv('HELIUS_API_KEY', '')
        self.rpc_endpoint = os.getenv('RPC_ENDPOINT', 'https://api.mainnet-beta.solana.com')
        
        # State
        self.last_update = None
        self.position_cache = {}
        
        # Data structures
        self.onchain_data = {}

        # Initialize Redis event bus for alert publishing
        self.event_bus = get_event_bus()

        # Register singleton
        set_onchain_agent(self)

        info("\033[0;34m🔗 OnChain Agent initialized\033[0m")
        info("\033[0;34m🔄 Event bus connected for real-time alert publishing\033[0m")
    
    def run_single_cycle(self) -> bool:
        """Execute a single data collection cycle"""
        try:
            info("\033[0;34m🔄 Starting on-chain data collection...\033[0m")
            start_time = time.time()
            
            # Get open positions from portfolio tracker
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            
            # CRITICAL: Force a fresh snapshot to ensure we have the latest positions
            # This ensures the on-chain agent sees the same data as the dashboard
            tracker.update_portfolio_snapshot()
            
            portfolio = tracker.get_portfolio_balances()
            
            if not portfolio or not portfolio.get('individual_positions'):
                info("\033[0;34mNo open positions to track\033[0m")
                return True
            
            # Extract token addresses from positions
            positions = portfolio.get('individual_positions', {})
            token_addresses = []
            seen_addresses = set()  # Deduplicate by mint address
            
            for symbol, position_data in positions.items():
                token_address = position_data.get('address')
                if token_address and token_address not in EXCLUDED_TOKENS and token_address not in seen_addresses:
                    token_addresses.append(token_address)
                    seen_addresses.add(token_address)
            
            if not token_addresses:
                info("\033[0;34mNo tokens to track (all excluded)\033[0m")
                return True
            
            info(f"\033[0;34m📊 Found {len(token_addresses)} unique tokens\033[0m")
            
            # Limit to max tokens
            if len(token_addresses) > self.max_tokens:
                info(f"\033[0;34m⚠️ Limiting to {self.max_tokens} of {len(token_addresses)} tokens\033[0m")
                token_addresses = token_addresses[:self.max_tokens]
            
            info(f"\033[0;34m🔍 Tracking {len(token_addresses)} tokens\033[0m")
            
            # Fetch on-chain data for each token
            results = {}
            for token_address in token_addresses:
                try:
                    token_data = self._fetch_token_data(token_address)
                    if token_data:
                        results[token_address] = token_data
                except Exception as e:
                    error(f"Error fetching data for {token_address[:8]}...: {e}")
            
            # Store results
            self.onchain_data = {
                'timestamp': datetime.now().isoformat(),
                'tokens': results
            }
            
            # Save to file
            if not self._save_data():
                error("Failed to save on-chain data to disk")
                return False
            
            elapsed = time.time() - start_time
            info(f"\033[0;34m✅ On-chain collection completed in {elapsed:.2f}s ({len(results)} tokens)\033[0m")

            # Generate alerts based on collected data
            self._generate_onchain_alerts(results)

            self.last_update = datetime.now()
            return True
            
        except Exception as e:
            error(f"Error in token on-chain collection: {e}")
            import traceback
            error(traceback.format_exc())
            return False

    def _generate_onchain_alerts(self, token_results: List[Dict]):
        """Generate alerts based on on-chain data analysis"""
        try:
            info("\033[0;34m🔍 Analyzing on-chain data for alerts...\033[0m")

            alerts_generated = 0

            for token_data in token_results:
                token_address = token_data.get('token_address')
                symbol = token_data.get('symbol', token_address[:8] + '...')

                # Check for whale concentration alerts
                whale_pct = token_data.get('whale_concentration', 0)
                if whale_pct > TOKEN_ONCHAIN_WHALE_CONCENTRATION_HIGH:
                    alert = MarketAlert(
                        agent_source="onchain_agent",
                        alert_type=AlertType.WHALE_CONCENTRATION,
                        symbol=symbol,
                        severity=AlertSeverity.HIGH,
                        confidence=min(whale_pct / 50, 0.9),  # Scale confidence by whale %
                        data={
                            'whale_concentration': whale_pct,
                            'top_10_holders_pct': whale_pct,
                            'total_holders': token_data.get('holder_count', 0),
                            'concentration_level': 'high' if whale_pct > 40 else 'moderate'
                        },
                        timestamp=datetime.now(),
                        metadata={
                            'onchain_metric': 'whale_concentration',
                            'alert_trigger': f'whale_pct_{whale_pct:.1f}',
                            'risk_level': 'high' if whale_pct > 40 else 'medium'
                        }
                    )
                    self.event_bus.publish('market_alert', alert.to_dict())
                    alerts_generated += 1
                    info(f"🐋 Published whale concentration alert for {symbol}: {whale_pct:.1f}%")

                # Check for liquidity change alerts
                liquidity_change_pct = token_data.get('liquidity_change_pct', 0)
                if abs(liquidity_change_pct) > 25:  # 25% change threshold
                    severity = AlertSeverity.CRITICAL if abs(liquidity_change_pct) > 50 else AlertSeverity.HIGH
                    confidence = min(abs(liquidity_change_pct) / 100, 0.9)

                    alert = MarketAlert(
                        agent_source="onchain_agent",
                        alert_type=AlertType.LIQUIDITY_CHANGE,
                        symbol=symbol,
                        severity=severity,
                        confidence=confidence,
                        data={
                            'liquidity_change_pct': liquidity_change_pct,
                            'current_liquidity_usd': token_data.get('liquidity_usd', 0),
                            'direction': 'increase' if liquidity_change_pct > 0 else 'decrease',
                            'magnitude': 'large' if abs(liquidity_change_pct) > 50 else 'moderate'
                        },
                        timestamp=datetime.now(),
                        metadata={
                            'onchain_metric': 'liquidity_change',
                            'alert_trigger': f'liquidity_change_{liquidity_change_pct:+.1f}%',
                            'impact': 'high' if abs(liquidity_change_pct) > 50 else 'medium'
                        }
                    )
                    self.event_bus.publish('market_alert', alert.to_dict())
                    alerts_generated += 1
                    info(f"💧 Published liquidity change alert for {symbol}: {liquidity_change_pct:+.1f}%")

                # Check for holder growth alerts
                holder_change_pct = token_data.get('holder_change_pct', 0)
                if abs(holder_change_pct) > 15:  # 15% change threshold
                    severity = AlertSeverity.HIGH if abs(holder_change_pct) > 25 else AlertSeverity.MEDIUM
                    confidence = min(abs(holder_change_pct) / 50, 0.85)

                    alert = MarketAlert(
                        agent_source="onchain_agent",
                        alert_type=AlertType.HOLDER_GROWTH,
                        symbol=symbol,
                        severity=severity,
                        confidence=confidence,
                        data={
                            'holder_change_pct': holder_change_pct,
                            'current_holders': token_data.get('holder_count', 0),
                            'holder_change_count': token_data.get('holder_change_count', 0),
                            'growth_type': 'expansion' if holder_change_pct > 0 else 'contraction'
                        },
                        timestamp=datetime.now(),
                        metadata={
                            'onchain_metric': 'holder_growth',
                            'alert_trigger': f'holder_change_{holder_change_pct:+.1f}%',
                            'momentum': 'strong' if abs(holder_change_pct) > 25 else 'moderate'
                        }
                    )
                    self.event_bus.publish('market_alert', alert.to_dict())
                    alerts_generated += 1
                    info(f"👥 Published holder growth alert for {symbol}: {holder_change_pct:+.1f}%")

                # Check for on-chain activity trend alerts
                trend_signal = token_data.get('trend_signal')
                volume_24h = token_data.get('volume_24h', 0)
                tx_count_24h = token_data.get('tx_count_24h', 0)

                # Only alert for significant activity trends
                if trend_signal in ['GROWING', 'SHRINKING'] and (volume_24h > 100000 or tx_count_24h > 100):
                    severity = AlertSeverity.MEDIUM
                    confidence = 0.7  # On-chain trends are moderately reliable

                    alert = MarketAlert(
                        agent_source="onchain_agent",
                        alert_type=AlertType.ONCHAIN_ACTIVITY,
                        symbol=symbol,
                        severity=severity,
                        confidence=confidence,
                        data={
                            'trend_signal': trend_signal,
                            'volume_24h': volume_24h,
                            'tx_count_24h': tx_count_24h,
                            'holder_count': token_data.get('holder_count', 0),
                            'liquidity_usd': token_data.get('liquidity_usd', 0),
                            'activity_level': 'high' if volume_24h > 500000 else 'moderate'
                        },
                        timestamp=datetime.now(),
                        metadata={
                            'onchain_metric': 'activity_trend',
                            'alert_trigger': f'trend_{trend_signal.lower()}_volume_{volume_24h:,.0f}',
                            'trend_direction': trend_signal.lower(),
                            'activity_score': min(volume_24h / 1000000, 1.0)  # 0-1 activity score
                        }
                    )
                    self.event_bus.publish('market_alert', alert.to_dict())
                    alerts_generated += 1
                    info(f"📈 Published on-chain activity alert for {symbol}: {trend_signal}")

            info(f"\033[0;34m🚨 Generated {alerts_generated} on-chain alerts\033[0m")

        except Exception as e:
            error(f"Error generating on-chain alerts: {e}")
            import traceback
            error(traceback.format_exc())

    def _fetch_token_data(self, token_address: str) -> Optional[Dict]:
        """Fetch on-chain data for a single token with change detection"""
        try:
            # Fetch from Birdeye
            birdeye_data = self._fetch_birdeye_data(token_address)
            
            if not birdeye_data:
                warning(f"No Birdeye data for {token_address[:8]}...")
                return None
            
            # Debug: Print available fields from Birdeye API  
            debug(f"Birdeye API fields for {token_address[:8]}...: {list(birdeye_data.keys())}", file_only=True)
            
            # Extract current data
            holder_count = birdeye_data.get('holder', 0)
            tx_count_24h = birdeye_data.get('trade24h', 0)
            liquidity_usd = birdeye_data.get('liquidity', 0)
            volume_24h = birdeye_data.get('v24hUSD', 0)
            price_change_24h = birdeye_data.get('priceChange24hPercent', 0)
            
            # Load historical data to calculate changes
            historical_data = {}
            if self.historical_data_file.exists():
                try:
                    with open(self.historical_data_file, 'r') as f:
                        all_history = json.load(f)
                        historical_data = all_history.get(token_address, [])
                except Exception as e:
                    debug(f"Could not load historical data for {token_address[:8]}...: {e}")
            
            # Calculate holder changes from history
            holder_change_pct = 0.0
            holder_change_count = 0
            
            if historical_data and len(historical_data) > 0:
                previous_count = historical_data[-1].get('holder_count', 0)
                if previous_count > 0 and holder_count > 0:
                    holder_change_count = holder_count - previous_count
                    holder_change_pct = ((holder_count - previous_count) / previous_count) * 100
            elif holder_count > 0:
                # First reading, no change yet
                holder_change_count = 0
                holder_change_pct = 0
            
            # Use price change as fallback indicator when historical data insufficient
            use_price_as_indicator = len(historical_data) < 2
            
            # Determine trend
            if use_price_as_indicator and price_change_24h is not None:
                # Use price change when we don't have holder history yet
                price_change = float(price_change_24h) if price_change_24h is not None else 0
                if price_change > 10:
                    trend_signal = "GROWING"
                elif price_change < -5:
                    trend_signal = "SHRINKING"
                else:
                    trend_signal = "STABLE"
            else:
                # Use actual holder change data
                trend_signal = self._calculate_trend(holder_change_pct)
            
            # Get whale data if enabled
            whale_distribution = {}
            if self.include_whale_data:
                whale_distribution = self._fetch_whale_distribution(token_address)
            
            # Calculate whale concentration from holder distribution
            whale_concentration = 0.0
            if whale_distribution and isinstance(whale_distribution, dict):
                # Calculate percentage held by top holders
                total_supply = whale_distribution.get('total_supply', 0)
                if total_supply > 0:
                    top_holders_balance = sum(
                        holder.get('balance', 0)
                        for holder in whale_distribution.get('top_holders', [])[:10]  # Top 10 holders
                    )
                    whale_concentration = (top_holders_balance / total_supply) * 100

            # Calculate liquidity change percentage
            liquidity_change_pct = 0.0
            if historical_data and len(historical_data) > 0:
                prev_liquidity = historical_data[-1].get('liquidity_usd', 0)
                if prev_liquidity > 0:
                    liquidity_change_pct = ((liquidity_usd - prev_liquidity) / prev_liquidity) * 100

            # Compile token data
            token_data = {
                'holder_count': holder_count,
                'holder_change_count': holder_change_count,
                'holder_change_pct': holder_change_pct,
                'tx_count_24h': tx_count_24h,
                'liquidity_usd': liquidity_usd,
                'liquidity_change_pct': liquidity_change_pct,
                'volume_24h': volume_24h,
                'price_change_24h': price_change_24h,
                'trend_signal': trend_signal,
                'whale_concentration': whale_concentration,
                'holder_distribution': whale_distribution,
                'timestamp': datetime.now().isoformat()
            }
            
            return token_data
            
        except Exception as e:
            error(f"Error fetching token data: {e}")
            return None
    
    def _fetch_birdeye_data(self, token_address: str) -> Optional[Dict]:
        """Fetch token overview from free data sources (replaces Birdeye API)"""
        # Use free data source aggregation instead of Birdeye
        return self._fetch_free_onchain_data(token_address)
    
    def _fetch_free_onchain_data(self, token_address: str) -> Optional[Dict]:
        """Fetch onchain data from free sources using Helius, Jupiter, Solana RPC, and Raydium"""
        try:
            from src.scripts.shared_services.hybrid_rpc_manager import get_hybrid_rpc_manager
            from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
            from datetime import datetime, timedelta
            
            rpc_manager = get_hybrid_rpc_manager()
            price_service = get_optimized_price_service()
            
            data = {}
            
            # 1. Price Change (24h) - Calculate from price service
            current_price = price_service.get_price(token_address)
            # TODO: Get 24h ago price from price history cache if available
            # For now, set to 0 (will be calculated if price history is tracked)
            data['priceChange24hPercent'] = 0.0
            
            # 2. Volume (24h USD) - Jupiter Volume API
            try:
                volume_url = f"https://api.jup.ag/volume/v1/{token_address}"
                volume_response = requests.get(volume_url, timeout=5)
                if volume_response.status_code == 200:
                    volume_data = volume_response.json()
                    data['v24hUSD'] = volume_data.get('volume24h', 0)
                else:
                    data['v24hUSD'] = 0
            except Exception as e:
                debug(f"Jupiter volume API failed for {token_address[:8]}...: {e}", file_only=True)
                data['v24hUSD'] = 0
            
            # 3. Transaction Count (24h) - Solana RPC via hybrid_rpc_manager
            try:
                end_time = int(datetime.now().timestamp())
                start_time = int((datetime.now() - timedelta(days=1)).timestamp())
                
                params = [token_address, {"limit": 1000}]
                result = rpc_manager.make_rpc_request(
                    "getSignaturesForAddress",
                    params,
                    wallet_address=None,
                    timeout=10
                )
                
                if result and 'result' in result:
                    signatures = result['result']
                    # Filter by time (last 24h)
                    recent_txs = [
                        sig for sig in signatures 
                        if sig.get('blockTime', 0) >= start_time
                    ]
                    data['trade24h'] = len(recent_txs)
                else:
                    data['trade24h'] = 0
            except Exception as e:
                debug(f"RPC transaction count failed for {token_address[:8]}...: {e}", file_only=True)
                data['trade24h'] = 0
            
            # 4. Liquidity USD - Raydium Pool Data
            try:
                data['liquidity'] = self._fetch_raydium_liquidity(token_address)
            except Exception as e:
                debug(f"Raydium liquidity fetch failed for {token_address[:8]}...: {e}", file_only=True)
                data['liquidity'] = 0
            
            # 5. Holder Count - Helius API (if available)
            try:
                helius_key = os.getenv('HELIUS_API_KEY')
                if helius_key:
                    url = f"https://api.helius.xyz/v0/token-metadata"
                    params = {"api-key": helius_key, "mint": token_address}
                    response = requests.get(url, params=params, timeout=5)
                    if response.status_code == 200:
                        metadata = response.json()
                        data['holder'] = metadata.get('holderCount', 0)
                    else:
                        data['holder'] = 0
                else:
                    data['holder'] = 0
            except Exception as e:
                debug(f"Helius holder count failed for {token_address[:8]}...: {e}", file_only=True)
                data['holder'] = 0
            
            # Return data in Birdeye-compatible format
            return {
                'holder': data.get('holder', 0),
                'trade24h': data.get('trade24h', 0),
                'liquidity': data.get('liquidity', 0),
                'v24hUSD': data.get('v24hUSD', 0),
                'priceChange24hPercent': data.get('priceChange24hPercent', 0.0)
            }
            
        except Exception as e:
            error(f"Error fetching free onchain data for {token_address[:8]}...: {e}")
            import traceback
            error(traceback.format_exc())
            return None
    
    def _fetch_raydium_liquidity(self, token_address: str) -> float:
        """Fetch liquidity from Raydium pools"""
        try:
            # Raydium API endpoint for pool data
            # Note: This is a simplified implementation - may need pool address lookup first
            url = "https://api.raydium.io/v2/ammPools"
            
            # Try to find pools containing this token
            # This is a simplified approach - full implementation would:
            # 1. Query all pools or search by token mint
            # 2. Filter pools containing this token
            # 3. Sum liquidity from all pools
            
            # For now, return 0 if we can't find liquidity
            # Full implementation would require Raydium pool registry or API
            return 0.0
            
        except Exception as e:
            debug(f"Raydium liquidity fetch error: {e}", file_only=True)
            return 0.0
    
    def _fetch_whale_distribution(self, token_address: str) -> Dict:
        """Fetch whale concentration data from Helius/Solana RPC
        
        NOTE: This is currently a placeholder implementation.
        Full whale distribution analysis requires:
        - Helius Enhanced Webhooks API access, or
        - Direct Solana RPC calls to get holder distribution data
        
        For now, returns baseline data since whale concentration analysis
        requires specialized API access that's not yet implemented.
        
        Args:
            token_address: Token address to analyze
            
        Returns:
            Dict with whale distribution metrics (currently baseline values)
        """
        # TODO: Implement real whale distribution fetching
        # Requires: Helius API or Solana RPC integration for holder analysis
        return {
            'whale_pct': 0.0,
            'concentration_risk': 'UNKNOWN',
            'top_10_holders': 0,
            'note': 'Whale distribution analysis not yet implemented'
        }
    
    def _calculate_trend(self, holder_growth_pct: float) -> str:
        """Calculate trend signal based on holder growth
        
        Args:
            holder_growth_pct: Percentage change in holder count (e.g., 10.0 for 10%)
        
        Returns:
            "GROWING" if growth >= threshold
            "SHRINKING" if growth <= staleness threshold  
            "STABLE" otherwise
        """
        # Convert config thresholds (decimals) to percentages for comparison
        growth_threshold_pct = TOKEN_ONCHAIN_GROWTH_THRESHOLD * 100  # 0.10 -> 10.0
        stale_threshold_pct = TOKEN_ONCHAIN_STALE_THRESHOLD * 100   # -0.05 -> -5.0
        
        if holder_growth_pct >= growth_threshold_pct:
            return "GROWING"
        elif holder_growth_pct <= stale_threshold_pct:
            return "SHRINKING"
        else:
            return "STABLE"
    
    def _save_data(self) -> bool:
        """Save on-chain data with historical tracking
        
        Strategy: Stores rolling historical data (last 20 readings per token)
        and overwrites current snapshot with latest data.
        
        Returns:
            True if data was saved successfully, False otherwise
        """
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing historical data
            historical_data = {}
            if self.historical_data_file.exists():
                try:
                    with open(self.historical_data_file, 'r') as f:
                        historical_data = json.load(f)
                except Exception as e:
                    warning(f"Could not load historical data: {e}")
            
            # Store current snapshot in history
            timestamp = datetime.now().isoformat()
            for token_address, token_data in self.onchain_data.get('tokens', {}).items():
                if token_address not in historical_data:
                    historical_data[token_address] = []
                
                # Add to history
                historical_data[token_address].append({
                    'timestamp': timestamp,
                    'holder_count': token_data.get('holder_count'),
                    'holder_change_count': token_data.get('holder_change_count', 0),
                    'holder_change_pct': token_data.get('holder_change_pct', 0),
                    'tx_count_24h': token_data.get('tx_count_24h'),
                    'volume_24h': token_data.get('volume_24h'),
                    'liquidity_usd': token_data.get('liquidity_usd'),
                    'price_change_24h': token_data.get('price_change_24h'),
                    'trend_signal': token_data.get('trend_signal')
                })
                
                # Keep only last 20 data points per token (enough for 20 hours of hourly updates)
                historical_data[token_address] = historical_data[token_address][-20:]
            
            # Save historical data
            with open(self.historical_data_file, 'w') as f:
                json.dump(historical_data, f, indent=2)
            
            # Save current snapshot
            with open(self.data_file, 'w') as f:
                json.dump(self.onchain_data, f, indent=2)
            
            debug(f"Saved on-chain data to {self.data_file}")
            return True
            
        except Exception as e:
            error(f"Error saving on-chain data: {e}")
            import traceback
            error(traceback.format_exc())
            return False
    
    def clean_old_data(self, days_to_keep: int = 7) -> bool:
        """Clean old on-chain data snapshots
        
        Note: Current implementation overwrites data each cycle.
        This method is for future use if we implement historical snapshots.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            # TODO: Implement when we add historical data tracking
            # For now, this is a placeholder since we overwrite each cycle
            info(f"Data cleanup not needed - using overwrite strategy")
            return True
        except Exception as e:
            error(f"Error cleaning old data: {e}")
            return False
    
    def get_token_data(self, token_address: str) -> Optional[Dict]:
        """Get cached on-chain data for a specific token"""
        try:
            if not self.data_file.exists():
                return None
            
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            return data.get('tokens', {}).get(token_address)
            
        except Exception as e:
            error(f"Error reading token data: {e}")
            return None
    
    def get_aggregated_status(self) -> Dict[str, Any]:
        """Get aggregated on-chain status for dashboard"""
        try:
            if not self.data_file.exists():
                return {
                    'growing_count': 0,
                    'shrinking_count': 0,
                    'stable_count': 0,
                    'status_text': 'No Data',
                    'color': 'YELLOW'
                }
            
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            tokens = data.get('tokens', {})
            growing = sum(1 for t in tokens.values() if t.get('trend_signal') == 'GROWING')
            shrinking = sum(1 for t in tokens.values() if t.get('trend_signal') == 'SHRINKING')
            stable = sum(1 for t in tokens.values() if t.get('trend_signal') == 'STABLE')
            
            # Format: "3↑ 0↓ (3 growing, 0 shrinking positions)"
            status_text = f"{growing}↑ {shrinking}↓ ({growing} growing, {shrinking} shrinking positions)"
            
            # Determine color
            if shrinking > growing:
                color = 'RED'
            elif growing > 0:
                color = 'GREEN'
            else:
                color = 'YELLOW'
            
            return {
                'growing_count': growing,
                'shrinking_count': shrinking,
                'stable_count': stable,
                'status_text': status_text,
                'color': color
            }
        except Exception as e:
            error(f"Error getting aggregated status: {e}")
            return {
                'growing_count': 0,
                'shrinking_count': 0,
                'stable_count': 0,
                'status_text': 'Error',
                'color': 'RED'
            }
    
    def run(self):
        """Run method for scheduler compatibility"""
        return self.run_single_cycle()

# Global singleton instance
_onchain_agent_instance = None

def get_onchain_agent() -> Optional[OnChainAgent]:
    """Get the singleton onchain agent instance"""
    global _onchain_agent_instance
    return _onchain_agent_instance

def set_onchain_agent(agent: OnChainAgent):
    """Set the singleton onchain agent instance"""
    global _onchain_agent_instance
    _onchain_agent_instance = agent


if __name__ == "__main__":
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print('\n🛑 Gracefully stopping OnChain Agent...')
        if 'agent' in locals():
            agent.running = False
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🔗 Starting OnChain Agent...")
    try:
        agent = OnChainAgent()
        
        # Run a single cycle for testing
        agent.run_single_cycle()
        
        print("✅ OnChain Agent completed successfully")
    except KeyboardInterrupt:
        print("\n⚠️ OnChain Agent interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
