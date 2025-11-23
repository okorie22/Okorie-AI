"""
🌙 Anarcho Capital's DeFi Protocol Manager
Handles integration with Solana DeFi protocols (Solend, Mango, Tulip)
Built with love by Anarcho Capital 🚀
"""

import os
import time
import json
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import aiohttp

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical, system
from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
from src.config.defi_config import (
    DEFI_PROTOCOLS, SECONDARY_PROTOCOLS, 
    CAPITAL_PROTECTION, LIQUIDATION_PROTECTION,
    YIELD_THRESHOLDS, get_current_phase_config
)

# Solana SDK imports
try:
    from solana.rpc.api import Client
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    SOLANA_AVAILABLE = True
except ImportError:
    SOLANA_AVAILABLE = False
    warning("Solana SDK not available - DeFi operations will be simulated")

@dataclass
class ProtocolAPY:
    """Protocol APY information"""
    protocol: str
    token: str
    apy: float
    tvl: float
    risk_level: str
    last_updated: datetime
    source: str

@dataclass
class LendingOpportunity:
    """Lending opportunity details"""
    protocol: str
    token: str
    apy: float
    amount_usd: float
    risk_score: float
    expected_return: float
    priority: int

@dataclass
class BorrowingOpportunity:
    """Borrowing opportunity details"""
    protocol: str
    token: str
    borrow_rate: float
    collateral_required: float
    max_borrow: float
    risk_score: float
    priority: int

class DeFiProtocolManager:
    """
    Manages integration with Solana DeFi protocols
    Handles lending, borrowing, and yield optimization
    """
    
    def __init__(self):
        """Initialize the DeFi Protocol Manager"""
        self.api_manager = get_shared_api_manager()
        self.protocols = {}
        self.apy_cache = {}
        self.opportunity_cache = {}
        self.last_update = {}
        self.cache_duration = 300  # 5 minutes
        
        # Initialize protocol connections
        self._initialize_protocols()
        
        # Health monitoring
        self.protocol_health = {}
        self.last_health_check = {}
        self.health_check_interval = 60  # 1 minute
        
        info("🚀 DeFi Protocol Manager initialized")
    
    def _initialize_protocols(self):
        """Initialize connections to DeFi protocols"""
        try:
            # Initialize primary protocols
            for protocol_name, protocol_config in DEFI_PROTOCOLS.items():
                if protocol_config['enabled']:
                    self.protocols[protocol_name] = self._create_protocol_connection(protocol_name, protocol_config)
                    info(f"✅ Initialized {protocol_name} protocol")
            
            # Initialize secondary protocols
            for protocol_name, protocol_config in SECONDARY_PROTOCOLS.items():
                if protocol_config['enabled']:
                    self.protocols[protocol_name] = self._create_protocol_connection(protocol_name, protocol_config)
                    info(f"✅ Initialized {protocol_name} protocol (secondary)")
                    
        except Exception as e:
            error(f"Failed to initialize DeFi protocols: {str(e)}")
    
    def _create_protocol_connection(self, protocol_name: str, protocol_config: Dict) -> Dict:
        """Create a protocol connection object"""
        return {
            'name': protocol_config['name'],
            'address': protocol_config['address'],
            'risk_level': protocol_config['risk_level'],
            'max_allocation': protocol_config['max_allocation'],
            'enabled': protocol_config['enabled'],
            'priority': protocol_config['priority'],
            'health': 'unknown',
            'last_check': None,
            'connection': None
        }
    
    async def get_protocol_apy(self, protocol_name: str, token_address: str = None) -> Optional[ProtocolAPY]:
        """Get APY for a specific protocol and token"""
        try:
            # Check cache first
            cache_key = f"{protocol_name}_{token_address or 'all'}"
            if cache_key in self.apy_cache:
                cached_data = self.apy_cache[cache_key]
                if time.time() - cached_data['timestamp'] < self.cache_duration:
                    return cached_data['data']
            
            # Fetch fresh data
            apy_data = await self._fetch_protocol_apy(protocol_name, token_address)
            
            if apy_data:
                # Cache the result
                self.apy_cache[cache_key] = {
                    'data': apy_data,
                    'timestamp': time.time()
                }
                return apy_data
            
        except Exception as e:
            error(f"Failed to get APY for {protocol_name}: {str(e)}")
        
        return None
    
    async def _fetch_protocol_apy(self, protocol_name: str, token_address: str = None) -> Optional[ProtocolAPY]:
        """Fetch APY data from protocol APIs"""
        try:
            if protocol_name == 'solend':
                return await self._fetch_solend_apy(token_address)
            elif protocol_name == 'mango':
                return await self._fetch_mango_apy(token_address)
            elif protocol_name == 'tulip':
                return await self._fetch_tulip_apy(token_address)
            else:
                warning(f"Unknown protocol: {protocol_name}")
                return None
                
        except Exception as e:
            error(f"Failed to fetch APY for {protocol_name}: {str(e)}")
            return None
    
    async def _fetch_solend_apy(self, token_address: str = None) -> Optional[ProtocolAPY]:
        """Fetch APY data from Solend"""
        try:
            # Solend API endpoint
            url = "https://api.solend.fi/v1/markets"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Find the token market
                        if token_address:
                            market = next((m for m in data if m.get('mint') == token_address), None)
                        else:
                            # Get USDC market by default
                            market = next((m for m in data if m.get('mint') == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'), None)
                        
                        if market:
                            supply_apy = float(market.get('supplyApy', 0))
                            borrow_apy = float(market.get('borrowApy', 0))
                            tvl = float(market.get('totalSupplyUsd', 0))
                            
                            return ProtocolAPY(
                                protocol='solend',
                                token=market.get('mint', 'unknown'),
                                apy=max(supply_apy, borrow_apy),
                                tvl=tvl,
                                risk_level='low',
                                last_updated=datetime.now(),
                                source='solend_api'
                            )
            
        except Exception as e:
            error(f"Failed to fetch Solend APY: {str(e)}")
        
        return None
    
    async def _fetch_mango_apy(self, token_address: str = None) -> Optional[ProtocolAPY]:
        """Fetch APY data from Mango Markets"""
        try:
            # Mango Markets API endpoint
            url = "https://api.mango.markets/v4/stats"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Mango provides lending rates
                        if 'lendingRates' in data:
                            rates = data['lendingRates']
                            # Find the best rate
                            best_rate = max(rates, key=lambda x: float(x.get('rate', 0)))
                            
                            return ProtocolAPY(
                                protocol='mango',
                                token=best_rate.get('mint', 'unknown'),
                                apy=float(best_rate.get('rate', 0)) * 100,  # Convert to percentage
                                tvl=float(data.get('totalDeposits', 0)),
                                risk_level='medium_high',
                                last_updated=datetime.now(),
                                source='mango_api'
                            )
            
        except Exception as e:
            error(f"Failed to fetch Mango APY: {str(e)}")
        
        return None
    
    async def _fetch_tulip_apy(self, token_address: str = None) -> Optional[ProtocolAPY]:
        """Fetch APY data from Tulip Protocol"""
        try:
            # Tulip Protocol API endpoint
            url = "https://api.tulip.garden/v1/pools"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Find the best yield pool
                        if 'pools' in data:
                            pools = data['pools']
                            best_pool = max(pools, key=lambda x: float(x.get('apy', 0)))
                            
                            return ProtocolAPY(
                                protocol='tulip',
                                token=best_pool.get('token', 'unknown'),
                                apy=float(best_pool.get('apy', 0)),
                                tvl=float(best_pool.get('tvl', 0)),
                                risk_level='high',
                                last_updated=datetime.now(),
                                source='tulip_api'
                            )
            
        except Exception as e:
            error(f"Failed to fetch Tulip APY: {str(e)}")
        
        return None
    
    async def get_lending_opportunities(self, min_apy: float = None, max_risk: str = 'medium') -> List[LendingOpportunity]:
        """Get all available lending opportunities"""
        try:
            opportunities = []
            min_apy = min_apy or YIELD_THRESHOLDS['min_apy_threshold'] * 100
            
            # Get current phase configuration
            current_config = get_current_phase_config()
            enabled_protocols = current_config['protocols']
            
            for protocol_name in enabled_protocols:
                if protocol_name in self.protocols:
                    apy_data = await self.get_protocol_apy(protocol_name)
                    
                    if apy_data and apy_data.apy >= min_apy:
                        # Calculate risk score based on protocol risk level
                        risk_score = self._calculate_risk_score(apy_data.risk_level)
                        
                        if self._is_risk_acceptable(apy_data.risk_level, max_risk):
                            opportunity = LendingOpportunity(
                                protocol=protocol_name,
                                token=apy_data.token,
                                apy=apy_data.apy,
                                amount_usd=0,  # Will be calculated based on portfolio
                                risk_score=risk_score,
                                expected_return=apy_data.apy / 100,  # Convert to decimal
                                priority=self.protocols[protocol_name]['priority']
                            )
                            opportunities.append(opportunity)
            
            # Sort by priority and expected return
            opportunities.sort(key=lambda x: (x.priority, x.expected_return), reverse=True)
            
            return opportunities
            
        except Exception as e:
            error(f"Failed to get lending opportunities: {str(e)}")
            return []
    
    async def get_borrowing_opportunities(self, max_rate: float = None) -> List[BorrowingOpportunity]:
        """Get all available borrowing opportunities"""
        try:
            opportunities = []
            max_rate = max_rate or 15.0  # 15% maximum borrowing rate
            
            # Get current phase configuration
            current_config = get_current_phase_config()
            enabled_protocols = current_config['protocols']
            
            for protocol_name in enabled_protocols:
                if protocol_name in self.protocols:
                    apy_data = await self.get_protocol_apy(protocol_name)
                    
                    if apy_data and apy_data.apy <= max_rate:
                        # For borrowing, we want lower rates
                        opportunity = BorrowingOpportunity(
                            protocol=protocol_name,
                            token=apy_data.token,
                            borrow_rate=apy_data.apy,
                            collateral_required=0,  # Will be calculated
                            max_borrow=0,  # Will be calculated
                            risk_score=self._calculate_risk_score(apy_data.risk_level),
                            priority=self.protocols[protocol_name]['priority']
                        )
                        opportunities.append(opportunity)
            
            # Sort by borrowing rate (lowest first)
            opportunities.sort(key=lambda x: x.borrow_rate)
            
            return opportunities
            
        except Exception as e:
            error(f"Failed to get borrowing opportunities: {str(e)}")
            return []
    
    def _calculate_risk_score(self, risk_level: str) -> float:
        """Calculate numerical risk score from risk level"""
        risk_scores = {
            'low': 0.1,
            'medium': 0.3,
            'medium_high': 0.6,
            'high': 0.8,
            'very_high': 0.9
        }
        return risk_scores.get(risk_level, 0.5)
    
    def _is_risk_acceptable(self, protocol_risk: str, max_risk: str) -> bool:
        """Check if protocol risk is acceptable"""
        risk_levels = ['low', 'medium', 'medium_high', 'high', 'very_high']
        protocol_index = risk_levels.index(protocol_risk)
        max_index = risk_levels.index(max_risk)
        return protocol_index <= max_index
    
    async def check_protocol_health(self, protocol_name: str) -> Dict[str, Any]:
        """Check the health of a specific protocol"""
        try:
            if protocol_name not in self.protocols:
                return {'status': 'unknown', 'error': 'Protocol not found'}
            
            # Check if we need to perform health check
            last_check = self.last_health_check.get(protocol_name, 0)
            if time.time() - last_check < self.health_check_interval:
                return self.protocol_health.get(protocol_name, {'status': 'unknown'})
            
            # Perform health check
            health_status = await self._perform_protocol_health_check(protocol_name)
            
            # Update health status
            self.protocol_health[protocol_name] = health_status
            self.last_health_check[protocol_name] = time.time()
            
            return health_status
            
        except Exception as e:
            error(f"Failed to check protocol health for {protocol_name}: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    async def _perform_protocol_health_check(self, protocol_name: str) -> Dict[str, Any]:
        """Perform actual health check for a protocol"""
        try:
            # Basic health check - try to fetch APY
            apy_data = await self.get_protocol_apy(protocol_name)
            
            if apy_data:
                return {
                    'status': 'healthy',
                    'last_apy': apy_data.apy,
                    'last_tvl': apy_data.tvl,
                    'last_check': datetime.now().isoformat(),
                    'response_time': 'good'
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': 'Failed to fetch APY data',
                    'last_check': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    async def get_protocol_status_summary(self) -> Dict[str, Any]:
        """Get summary status of all protocols"""
        try:
            summary = {
                'total_protocols': len(self.protocols),
                'healthy_protocols': 0,
                'unhealthy_protocols': 0,
                'protocols': {}
            }
            
            for protocol_name in self.protocols:
                health = await self.check_protocol_health(protocol_name)
                summary['protocols'][protocol_name] = health
                
                if health['status'] == 'healthy':
                    summary['healthy_protocols'] += 1
                else:
                    summary['unhealthy_protocols'] += 1
            
            return summary
            
        except Exception as e:
            error(f"Failed to get protocol status summary: {str(e)}")
            return {'error': str(e)}
    
    async def validate_protocol_requirements(self, protocol_name: str, amount_usd: float) -> Dict[str, Any]:
        """Validate if a protocol meets requirements for investment"""
        try:
            if protocol_name not in self.protocols:
                return {'valid': False, 'error': 'Protocol not found'}
            
            protocol_config = self.protocols[protocol_name]
            
            # Check if protocol is enabled
            if not protocol_config['enabled']:
                return {'valid': False, 'error': 'Protocol is disabled'}
            
            # Check health status
            health = await self.check_protocol_health(protocol_name)
            if health['status'] != 'healthy':
                return {'valid': False, 'error': f'Protocol unhealthy: {health.get("error", "Unknown")}'}
            
            # Check allocation limits
            max_allocation = protocol_config['max_allocation']
            if amount_usd > max_allocation:
                return {
                    'valid': False, 
                    'error': f'Amount exceeds max allocation ({max_allocation * 100}%)'
                }
            
            # Check TVL requirements
            apy_data = await self.get_protocol_apy(protocol_name)
            if apy_data and apy_data.tvl < DEFI_PROTOCOLS[protocol_name]['min_tvl_usd']:
                return {
                    'valid': False,
                    'error': f'TVL too low: ${apy_data.tvl:,.0f} < ${DEFI_PROTOCOLS[protocol_name]["min_tvl_usd"]:,.0f}'
                }
            
            return {'valid': True, 'protocol': protocol_config}
            
        except Exception as e:
            error(f"Failed to validate protocol requirements: {str(e)}")
            return {'valid': False, 'error': str(e)}
    
    def clear_cache(self):
        """Clear all cached data"""
        self.apy_cache.clear()
        self.opportunity_cache.clear()
        self.last_update.clear()
        info("🧹 DeFi protocol cache cleared")
    
    def get_supported_protocols(self) -> List[str]:
        """Get list of supported protocols"""
        return list(self.protocols.keys())
    
    def get_protocol_info(self, protocol_name: str) -> Optional[Dict]:
        """Get information about a specific protocol"""
        if protocol_name in self.protocols:
            return self.protocols[protocol_name].copy()
        return None

# Global instance
_defi_protocol_manager = None

def get_defi_protocol_manager() -> DeFiProtocolManager:
    """Get global DeFi protocol manager instance"""
    global _defi_protocol_manager
    if _defi_protocol_manager is None:
        _defi_protocol_manager = DeFiProtocolManager()
    return _defi_protocol_manager

# Test function
async def test_protocol_manager():
    """Test the DeFi protocol manager"""
    try:
        manager = get_defi_protocol_manager()
        
        # Test protocol health
        print("🔍 Testing protocol health...")
        health_summary = await manager.get_protocol_status_summary()
        print(f"Health Summary: {json.dumps(health_summary, indent=2)}")
        
        # Test lending opportunities
        print("\n💰 Testing lending opportunities...")
        opportunities = await manager.get_lending_opportunities(min_apy=5.0)
        print(f"Found {len(opportunities)} lending opportunities")
        
        for opp in opportunities[:3]:  # Show first 3
            print(f"  - {opp.protocol}: {opp.apy:.2f}% APY (Risk: {opp.risk_score:.2f})")
        
        # Test borrowing opportunities
        print("\n💳 Testing borrowing opportunities...")
        borrow_opps = await manager.get_borrowing_opportunities(max_rate=15.0)
        print(f"Found {len(borrow_opps)} borrowing opportunities")
        
        for opp in borrow_opps[:3]:  # Show first 3
            print(f"  - {opp.protocol}: {opp.borrow_rate:.2f}% rate (Risk: {opp.risk_score:.2f})")
        
        print("\n✅ DeFi Protocol Manager test completed successfully!")
        
    except Exception as e:
        error(f"DeFi Protocol Manager test failed: {str(e)}")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_protocol_manager())
