"""
Rate Monitoring Service for Cross-Protocol Strategy
Real-time rate fetching from all staking and DeFi protocols
Built with love by Anarcho Capital
"""

import threading
import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from src.scripts.shared_services.logger import debug, info, warning, error
from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
from src.config.defi_config import DEFI_PROTOCOLS, SECONDARY_PROTOCOLS

# Import CROSS_PROTOCOL_CONFIG with fallback
try:
    from src.config.defi_config import CROSS_PROTOCOL_CONFIG
except ImportError:
    # Fallback config if not yet defined
    CROSS_PROTOCOL_CONFIG = {
        'rate_monitoring_interval': 300,
        'min_migration_spread': 0.02,
        'max_migration_frequency_days': 7,
        'arbitrage_min_spread': 0.03,
    }


@dataclass
class RateData:
    """Rate data structure for a single protocol"""
    protocol: str
    rate: float  # APY as decimal (e.g., 0.085 for 8.5%)
    timestamp: datetime
    source: str
    utilization: Optional[float] = None  # Protocol utilization rate
    tvl_usd: Optional[float] = None  # Total value locked


@dataclass
class RateHistory:
    """Rate history tracking for trend analysis"""
    protocol: str
    rate_type: str  # 'staking', 'lending', 'borrowing'
    history: List[Tuple[datetime, float]] = field(default_factory=list)
    max_history: int = 100  # Keep last 100 data points


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity between protocols"""
    borrow_protocol: str
    borrow_rate: float
    lend_protocol: str
    lend_rate: float
    spread: float  # lend_rate - borrow_rate
    profit_potential_apy: float
    risk_score: float  # 0.0 to 1.0 (higher = riskier)


class RateMonitoringService:
    """
    Centralized rate monitoring service for all protocols
    Provides real-time rate data with caching and history tracking
    """
    
    def __init__(self):
        """Initialize the rate monitoring service"""
        self.api_manager = get_shared_api_manager()
        self.config = CROSS_PROTOCOL_CONFIG
        
        # Rate caches with timestamps
        self.staking_rates: Dict[str, Tuple[RateData, datetime]] = {}
        self.lending_rates: Dict[str, Tuple[RateData, datetime]] = {}
        self.borrowing_rates: Dict[str, Tuple[RateData, datetime]] = {}
        
        # Rate history tracking
        self.rate_history: Dict[str, RateHistory] = {}
        
        # Cache settings
        self.cache_interval_seconds = self.config.get('rate_monitoring_interval', 300)  # 5 minutes default
        
        # Threading
        self.lock = threading.Lock()
        self.is_running = False
        self.monitor_thread = None
        
        info("Rate Monitoring Service initialized")
    
    def start_monitoring(self):
        """Start background rate monitoring"""
        if self.is_running:
            warning("Rate monitoring already running")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        info("Rate monitoring started in background")
    
    def stop_monitoring(self):
        """Stop background rate monitoring"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        info("Rate monitoring stopped")
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.is_running:
            try:
                # Refresh all rates
                self.refresh_all_rates()
                # Sleep for cache interval
                time.sleep(self.cache_interval_seconds)
            except Exception as e:
                error(f"Error in rate monitoring loop: {str(e)}")
                time.sleep(60)  # Wait 1 minute on error
    
    def get_staking_rates(self, force_refresh: bool = False) -> Dict[str, RateData]:
        """
        Get current staking rates from all protocols
        
        Args:
            force_refresh: Force refresh even if cache is valid
            
        Returns:
            Dictionary of protocol -> RateData
        """
        try:
            with self.lock:
                # Check cache validity
                if not force_refresh:
                    cached_data = self._get_valid_cached_rates(self.staking_rates)
                    if cached_data:
                        return cached_data
                
                # Fetch fresh rates
                staking_data = self.api_manager.get_staking_apy_data()
                
                if not staking_data:
                    warning("No staking rate data available")
                    return self._get_valid_cached_rates(self.staking_rates) or {}
                
                # Convert to RateData format
                rates = {}
                current_time = datetime.now()
                
                for protocol, apy in staking_data.items():
                    # Normalize protocol name
                    protocol_name = protocol.replace("_apy", "").lower()
                    
                    # Convert percentage to decimal if needed
                    try:
                        # Handle percentage strings like "9.5%"
                        if isinstance(apy, str) and apy.endswith('%'):
                            apy_value = float(apy.rstrip('%'))
                            rate_value = apy_value / 100.0  # Convert percentage to decimal
                        else:
                            apy_value = float(apy)  # Handle both string and numeric inputs
                            if apy_value > 1.0:     # Assume it's percentage (e.g., 8.5%)
                                rate_value = apy_value / 100.0
                            else:
                                rate_value = apy_value
                    except (ValueError, TypeError):
                        warning(f"Invalid APY value: {apy}, using 0.0")
                        rate_value = 0.0
                    
                    rate_data = RateData(
                        protocol=protocol_name,
                        rate=rate_value,
                        timestamp=current_time,
                        source="api_manager"
                    )
                    
                    rates[protocol_name] = rate_data
                    
                    # Update cache
                    self.staking_rates[protocol_name] = (rate_data, current_time)
                    
                    # Update history
                    self._update_rate_history(protocol_name, 'staking', rate_value)
                
                info(f"Fetched staking rates for {len(rates)} protocols")
                return rates
                
        except Exception as e:
            error(f"Error fetching staking rates: {str(e)}")
            # Return cached data if available
            return self._get_valid_cached_rates(self.staking_rates) or {}
    
    def get_lending_rates(self, force_refresh: bool = False) -> Dict[str, RateData]:
        """
        Get current lending rates from all DeFi protocols
        
        Args:
            force_refresh: Force refresh even if cache is valid
            
        Returns:
            Dictionary of protocol -> RateData
        """
        try:
            with self.lock:
                # Check cache validity
                if not force_refresh:
                    cached_data = self._get_valid_cached_rates(self.lending_rates)
                    if cached_data:
                        return cached_data
                
                # Fetch fresh rates (TODO: Implement actual API calls)
                # For now, use default rates from config
                rates = {}
                current_time = datetime.now()
                
                # Default rates based on protocol risk levels
                default_rates = {
                    'solend': 0.05,  # 5% APY
                    'mango': 0.11,  # 11% APY
                    'tulip': 0.15,  # 15% APY
                    'francium': 0.12,  # 12% APY
                }
                
                # Check enabled protocols
                all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
                
                for protocol_name, protocol_config in all_protocols.items():
                    if not protocol_config.get('enabled', False):
                        continue
                    
                    # Use default rate or fetch from API (when available)
                    rate_value = default_rates.get(protocol_name, 0.05)
                    
                    rate_data = RateData(
                        protocol=protocol_name,
                        rate=rate_value,
                        timestamp=current_time,
                        source="config_default"
                    )
                    
                    rates[protocol_name] = rate_data
                    self.lending_rates[protocol_name] = (rate_data, current_time)
                    self._update_rate_history(protocol_name, 'lending', rate_value)
                
                info(f"\033[36mFetched lending rates for {len(rates)} protocols\033[0m")
                return rates
                
        except Exception as e:
            error(f"Error fetching lending rates: {str(e)}")
            return self._get_valid_cached_rates(self.lending_rates) or {}
    
    def get_borrowing_rates(self, force_refresh: bool = False) -> Dict[str, RateData]:
        """
        Get current borrowing rates from all DeFi protocols
        
        Args:
            force_refresh: Force refresh even if cache is valid
            
        Returns:
            Dictionary of protocol -> RateData
        """
        try:
            with self.lock:
                # Check cache validity
                if not force_refresh:
                    cached_data = self._get_valid_cached_rates(self.borrowing_rates)
                    if cached_data:
                        return cached_data
                
                # Fetch fresh rates (TODO: Implement actual API calls)
                # For now, use default rates from config
                rates = {}
                current_time = datetime.now()
                
                # Default borrowing rates based on protocol risk levels
                default_rates = {
                    'solend': 0.08,  # 8% APY
                    'mango': 0.10,  # 10% APY
                    'tulip': 0.12,  # 12% APY
                    'francium': 0.09,  # 9% APY
                }
                
                # Check enabled protocols
                all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
                
                for protocol_name, protocol_config in all_protocols.items():
                    if not protocol_config.get('enabled', False):
                        continue
                    
                    # Use default rate or fetch from API (when available)
                    rate_value = default_rates.get(protocol_name, 0.08)
                    
                    rate_data = RateData(
                        protocol=protocol_name,
                        rate=rate_value,
                        timestamp=current_time,
                        source="config_default"
                    )
                    
                    rates[protocol_name] = rate_data
                    self.borrowing_rates[protocol_name] = (rate_data, current_time)
                    self._update_rate_history(protocol_name, 'borrowing', rate_value)
                
                info(f"\033[36mFetched borrowing rates for {len(rates)} protocols\033[0m")
                return rates
                
        except Exception as e:
            error(f"Error fetching borrowing rates: {str(e)}")
            return self._get_valid_cached_rates(self.borrowing_rates) or {}
    
    def get_rate_spread(self, protocol1: str, protocol2: str, rate_type: str = 'lending') -> Optional[float]:
        """
        Calculate rate spread between two protocols
        
        Args:
            protocol1: First protocol name
            protocol2: Second protocol name
            rate_type: 'lending', 'borrowing', or 'staking'
            
        Returns:
            Spread (protocol2_rate - protocol1_rate) or None if unavailable
        """
        try:
            if rate_type == 'staking':
                rates = self.get_staking_rates()
            elif rate_type == 'lending':
                rates = self.get_lending_rates()
            elif rate_type == 'borrowing':
                rates = self.get_borrowing_rates()
            else:
                error(f"Unknown rate type: {rate_type}")
                return None
            
            rate1 = rates.get(protocol1.lower())
            rate2 = rates.get(protocol2.lower())
            
            if not rate1 or not rate2:
                return None
            
            return rate2.rate - rate1.rate
            
        except Exception as e:
            error(f"Error calculating rate spread: {str(e)}")
            return None
    
    def find_arbitrage_opportunities(self, min_spread: Optional[float] = None) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities between lending and borrowing protocols
        
        Args:
            min_spread: Minimum spread required (default from config)
            
        Returns:
            List of ArbitrageOpportunity objects
        """
        try:
            if min_spread is None:
                min_spread = self.config.get('arbitrage_min_spread', 0.03)
            
            lending_rates = self.get_lending_rates()
            borrowing_rates = self.get_borrowing_rates()
            
            opportunities = []
            
            # Find all combinations where lend_rate > borrow_rate
            for borrow_protocol, borrow_data in borrowing_rates.items():
                for lend_protocol, lend_data in lending_rates.items():
                    # Skip same protocol
                    if borrow_protocol == lend_protocol:
                        continue
                    
                    spread = lend_data.rate - borrow_data.rate
                    
                    # Only consider if spread meets minimum threshold
                    if spread >= min_spread:
                        # Calculate risk score (higher risk for higher yield protocols)
                        risk_score = self._calculate_arbitrage_risk(borrow_protocol, lend_protocol)
                        
                        opportunity = ArbitrageOpportunity(
                            borrow_protocol=borrow_protocol,
                            borrow_rate=borrow_data.rate,
                            lend_protocol=lend_protocol,
                            lend_rate=lend_data.rate,
                            spread=spread,
                            profit_potential_apy=spread,
                            risk_score=risk_score
                        )
                        
                        opportunities.append(opportunity)
            
            # Sort by profit potential (descending)
            opportunities.sort(key=lambda x: x.profit_potential_apy, reverse=True)
            
            info(f"Found {len(opportunities)} arbitrage opportunities")
            return opportunities
            
        except Exception as e:
            error(f"Error finding arbitrage opportunities: {str(e)}")
            return []
    
    def get_best_staking_rate(self) -> Optional[RateData]:
        """Get the best (highest) staking rate"""
        rates = self.get_staking_rates()
        if not rates:
            return None
        return max(rates.values(), key=lambda x: x.rate)
    
    def get_best_lending_rate(self) -> Optional[RateData]:
        """Get the best (highest) lending rate"""
        rates = self.get_lending_rates()
        if not rates:
            return None
        return max(rates.values(), key=lambda x: x.rate)
    
    def get_best_borrowing_rate(self) -> Optional[RateData]:
        """Get the best (lowest) borrowing rate"""
        rates = self.get_borrowing_rates()
        if not rates:
            return None
        return min(rates.values(), key=lambda x: x.rate)
    
    def refresh_all_rates(self):
        """Force refresh all rates"""
        info("Refreshing all rate data...")
        self.get_staking_rates(force_refresh=True)
        self.get_lending_rates(force_refresh=True)
        self.get_borrowing_rates(force_refresh=True)
    
    def _get_valid_cached_rates(self, cache: Dict[str, Tuple[RateData, datetime]]) -> Optional[Dict[str, RateData]]:
        """Get cached rates if they're still valid"""
        if not cache:
            return None
        
        current_time = datetime.now()
        valid_rates = {}
        
        for protocol, (rate_data, cache_time) in cache.items():
            age_seconds = (current_time - cache_time).total_seconds()
            if age_seconds < self.cache_interval_seconds:
                valid_rates[protocol] = rate_data
        
        return valid_rates if valid_rates else None
    
    def _update_rate_history(self, protocol: str, rate_type: str, rate: float):
        """Update rate history for trend analysis"""
        key = f"{protocol}_{rate_type}"
        
        if key not in self.rate_history:
            self.rate_history[key] = RateHistory(
                protocol=protocol,
                rate_type=rate_type
            )
        
        history = self.rate_history[key]
        current_time = datetime.now()
        
        # Add new data point
        history.history.append((current_time, rate))
        
        # Trim to max history
        if len(history.history) > history.max_history:
            history.history = history.history[-history.max_history:]
    
    def _calculate_arbitrage_risk(self, borrow_protocol: str, lend_protocol: str) -> float:
        """Calculate risk score for arbitrage opportunity"""
        try:
            all_protocols = {**DEFI_PROTOCOLS, **SECONDARY_PROTOCOLS}
            
            borrow_config = all_protocols.get(borrow_protocol, {})
            lend_config = all_protocols.get(lend_protocol, {})
            
            # Risk levels: low=0.2, medium=0.5, medium_high=0.7, high=0.9
            risk_map = {
                'low': 0.2,
                'medium': 0.5,
                'medium_high': 0.7,
                'high': 0.9
            }
            
            borrow_risk = risk_map.get(borrow_config.get('risk_level', 'medium'), 0.5)
            lend_risk = risk_map.get(lend_config.get('risk_level', 'medium'), 0.5)
            
            # Average risk (slightly weight higher risk)
            avg_risk = (borrow_risk + lend_risk) / 2
            if max(borrow_risk, lend_risk) > 0.7:
                avg_risk = max(avg_risk, 0.7)  # Increase risk if either is high
            
            return avg_risk
            
        except Exception as e:
            error(f"Error calculating arbitrage risk: {str(e)}")
            return 0.5  # Default medium risk
    
    def get_rate_trend(self, protocol: str, rate_type: str, days: int = 7) -> Optional[Dict]:
        """Get rate trend over specified days"""
        key = f"{protocol}_{rate_type}"
        
        if key not in self.rate_history:
            return None
        
        history = self.rate_history[key]
        cutoff_time = datetime.now() - timedelta(days=days)
        
        recent_data = [(ts, rate) for ts, rate in history.history if ts >= cutoff_time]
        
        if not recent_data:
            return None
        
        rates = [rate for _, rate in recent_data]
        
        return {
            'protocol': protocol,
            'rate_type': rate_type,
            'current_rate': rates[-1],
            'average_rate': sum(rates) / len(rates),
            'min_rate': min(rates),
            'max_rate': max(rates),
            'trend': 'up' if rates[-1] > rates[0] else 'down',
            'data_points': len(recent_data)
        }


# Global instance
_rate_monitoring_service = None


def get_rate_monitoring_service() -> RateMonitoringService:
    """Get the global rate monitoring service instance"""
    global _rate_monitoring_service
    if _rate_monitoring_service is None:
        _rate_monitoring_service = RateMonitoringService()
    return _rate_monitoring_service

