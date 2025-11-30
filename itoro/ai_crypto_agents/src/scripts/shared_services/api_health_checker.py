#!/usr/bin/env python3
"""
🌐 Anarcho Capital's API Health Checker
Monitor health and performance of all external API services
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class APIHealthStatus:
    """API health status information"""
    name: str
    status: str  # 'healthy', 'degraded', 'unhealthy', 'unknown'
    response_time_ms: float
    last_check: datetime
    error_rate: float
    rate_limit_remaining: Optional[int]
    rate_limit_reset: Optional[datetime]
    last_error: Optional[str]
    uptime_percentage: float
    performance_metrics: Dict[str, Any]

class APIHealthChecker:
    """Monitor health of all external API services"""
    
    def __init__(self):
        self.api_configs = {
            'birdeye': {
                'base_url': 'https://public-api.birdeye.so/defi/price',
                'test_endpoint': 'https://public-api.birdeye.so/defi/price?ids=So11111111111111111111111111111111111111112',
                'api_key_header': 'X-API-KEY',
                'timeout': 5,
                'expected_response_time': 2000  # ms
            },
            'jupiter_price': {
                'base_url': 'https://price.jup.ag/v4/price',
                'test_endpoint': 'https://price.jup.ag/v4/price?ids=So11111111111111111111111111111111111111112',
                'api_key_header': None,
                'timeout': 5,
                'expected_response_time': 1000  # ms
            },
            'jupiter_swap': {
                'base_url': 'https://lite-api.jup.ag/swap/v1',
                'test_endpoint': 'https://lite-api.jup.ag/swap/v1/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000',
                'api_key_header': None,
                'timeout': 10,
                'expected_response_time': 3000  # ms
            },
            'pumpfun': {
                'base_url': 'https://api.pumpfunapi.org/price',
                'test_endpoint': 'https://api.pumpfunapi.org/price?token=So11111111111111111111111111111111111111112',
                'api_key_header': None,
                'timeout': 5,
                'expected_response_time': 2000  # ms
            },
            'helius_rpc': {
                'base_url': 'https://mainnet.helius-rpc.com',
                'test_endpoint': 'https://mainnet.helius-rpc.com/?api-key=test',
                'api_key_header': None,
                'timeout': 10,
                'expected_response_time': 5000  # ms
            },
            'quicknode_rpc': {
                'base_url': 'https://radial-maximum-tent.solana-mainnet.quiknode.pro',
                'test_endpoint': 'https://radial-maximum-tent.solana-mainnet.quiknode.pro/9101fbd24628749398074bdd83c57b608d8e8cd2/',
                'api_key_header': None,
                'timeout': 10,
                'expected_response_time': 3000  # ms
            },
            'apify': {
                'base_url': 'https://api.apify.com/v2',
                'test_endpoint': 'https://api.apify.com/v2/acts',
                'api_key_header': 'Authorization',
                'timeout': 10,
                'expected_response_time': 5000  # ms
            }
        }
        
        self.health_history = {}
        self.rate_limits = {}
        
    def check_api_health(self, api_name: str) -> APIHealthStatus:
        """Check health of specific API"""
        if api_name not in self.api_configs:
            return APIHealthStatus(
                name=api_name,
                status='unknown',
                response_time_ms=0,
                last_check=datetime.now(),
                error_rate=100.0,
                rate_limit_remaining=None,
                rate_limit_reset=None,
                last_error=f"Unknown API: {api_name}",
                uptime_percentage=0.0,
                performance_metrics={}
            )
        
        config = self.api_configs[api_name]
        start_time = time.time()
        
        try:
            # Prepare headers
            headers = {}
            api_key = self._get_api_key(api_name)
            if api_key and config['api_key_header']:
                if config['api_key_header'] == 'Authorization':
                    headers['Authorization'] = f'Bearer {api_key}'
                else:
                    headers[config['api_key_header']] = api_key
            
            # Make test request
            response = requests.get(
                config['test_endpoint'],
                headers=headers,
                timeout=config['timeout']
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Check response
            if response.status_code == 200:
                status = 'healthy'
                error_rate = 0.0
                last_error = None
            elif response.status_code == 429:
                status = 'degraded'
                error_rate = 50.0
                last_error = "Rate limited"
            elif response.status_code == 401:
                status = 'unhealthy'
                error_rate = 100.0
                last_error = "Authentication failed"
            else:
                status = 'degraded'
                error_rate = 50.0
                last_error = f"HTTP {response.status_code}"
            
            # Extract rate limit info if available
            rate_limit_remaining = None
            rate_limit_reset = None
            if 'X-RateLimit-Remaining' in response.headers:
                rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
            if 'X-RateLimit-Reset' in response.headers:
                rate_limit_reset = datetime.fromtimestamp(int(response.headers['X-RateLimit-Reset']))
            
            # Calculate uptime percentage
            uptime_percentage = self._calculate_uptime_percentage(api_name, status == 'healthy')
            
            # Performance metrics
            performance_metrics = {
                'status_code': response.status_code,
                'content_length': len(response.content),
                'expected_response_time': config['expected_response_time'],
                'response_time_ratio': response_time_ms / config['expected_response_time'],
                'rate_limit_headers': dict(response.headers)
            }
            
            return APIHealthStatus(
                name=api_name,
                status=status,
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                error_rate=error_rate,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_reset=rate_limit_reset,
                last_error=last_error,
                uptime_percentage=uptime_percentage,
                performance_metrics=performance_metrics
            )
            
        except requests.exceptions.Timeout:
            response_time_ms = (time.time() - start_time) * 1000
            return APIHealthStatus(
                name=api_name,
                status='unhealthy',
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                error_rate=100.0,
                rate_limit_remaining=None,
                rate_limit_reset=None,
                last_error="Request timeout",
                uptime_percentage=self._calculate_uptime_percentage(api_name, False),
                performance_metrics={'timeout': True}
            )
            
        except requests.exceptions.ConnectionError:
            response_time_ms = (time.time() - start_time) * 1000
            return APIHealthStatus(
                name=api_name,
                status='unhealthy',
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                error_rate=100.0,
                rate_limit_remaining=None,
                rate_limit_reset=None,
                last_error="Connection error",
                uptime_percentage=self._calculate_uptime_percentage(api_name, False),
                performance_metrics={'connection_error': True}
            )
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return APIHealthStatus(
                name=api_name,
                status='unhealthy',
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                error_rate=100.0,
                rate_limit_remaining=None,
                rate_limit_reset=None,
                last_error=str(e),
                uptime_percentage=self._calculate_uptime_percentage(api_name, False),
                performance_metrics={'exception': str(e)}
            )
    
    def _get_api_key(self, api_name: str) -> Optional[str]:
        """Get API key for specific service"""
        key_mapping = {
            'birdeye': 'BIRDEYE_API_KEY',
            'jupiter_price': 'JUPITER_API_KEY',
            'jupiter_swap': 'JUPITER_API_KEY',
            'pumpfun': 'PUMPFUN_API_KEY',
            'helius_rpc': 'HELIUS_API_KEY',
            'quicknode_rpc': 'QUICKNODE_API_KEY',
            'apify': 'APIFY_API_TOKEN'
        }
        
        if api_name in key_mapping:
            return os.getenv(key_mapping[api_name])
        return None
    
    def _calculate_uptime_percentage(self, api_name: str, is_healthy: bool) -> float:
        """Calculate uptime percentage for API"""
        if api_name not in self.health_history:
            self.health_history[api_name] = []
        
        # Add current status
        self.health_history[api_name].append({
            'timestamp': datetime.now(),
            'healthy': is_healthy
        })
        
        # Keep only last 100 checks (about 5 minutes at 3-second intervals)
        if len(self.health_history[api_name]) > 100:
            self.health_history[api_name] = self.health_history[api_name][-100:]
        
        # Calculate uptime percentage
        if not self.health_history[api_name]:
            return 0.0
        
        healthy_count = sum(1 for check in self.health_history[api_name] if check['healthy'])
        total_count = len(self.health_history[api_name])
        
        return (healthy_count / total_count) * 100.0
    
    def check_all_apis(self) -> Dict[str, APIHealthStatus]:
        """Check health of all APIs"""
        statuses = {}
        for api_name in self.api_configs.keys():
            statuses[api_name] = self.check_api_health(api_name)
        return statuses
    
    def get_api_health_summary(self) -> Dict[str, Any]:
        """Get overall API health summary"""
        statuses = self.check_all_apis()
        
        total_apis = len(statuses)
        healthy_apis = sum(1 for status in statuses.values() if status.status == 'healthy')
        degraded_apis = sum(1 for status in statuses.values() if status.status == 'degraded')
        unhealthy_apis = sum(1 for status in statuses.values() if status.status == 'unhealthy')
        
        # Calculate average response time
        response_times = [status.response_time_ms for status in statuses.values() if status.response_time_ms > 0]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Calculate average uptime
        uptimes = [status.uptime_percentage for status in statuses.values()]
        avg_uptime = sum(uptimes) / len(uptimes) if uptimes else 0
        
        # Count APIs with rate limits
        rate_limited_apis = sum(1 for status in statuses.values() if status.rate_limit_remaining is not None)
        
        # Find slowest API
        slowest_api = None
        if response_times:
            slowest_status = max(statuses.values(), key=lambda s: s.response_time_ms)
            slowest_api = {
                'name': slowest_status.name,
                'response_time': slowest_status.response_time_ms
            }
        
        return {
            'total_apis': total_apis,
            'healthy_apis': healthy_apis,
            'degraded_apis': degraded_apis,
            'unhealthy_apis': unhealthy_apis,
            'avg_response_time_ms': avg_response_time,
            'avg_uptime_percentage': avg_uptime,
            'rate_limited_apis': rate_limited_apis,
            'slowest_api': slowest_api,
            'health_percentage': (healthy_apis / total_apis * 100) if total_apis > 0 else 0
        }
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get rate limit status for all APIs"""
        statuses = self.check_all_apis()
        rate_limit_info = {}
        
        for api_name, status in statuses.items():
            if status.rate_limit_remaining is not None:
                rate_limit_info[api_name] = {
                    'remaining': status.rate_limit_remaining,
                    'reset_time': status.rate_limit_reset,
                    'status': 'healthy' if status.rate_limit_remaining > 10 else 'warning' if status.rate_limit_remaining > 0 else 'critical'
                }
            else:
                rate_limit_info[api_name] = {
                    'remaining': None,
                    'reset_time': None,
                    'status': 'unknown'
                }
        
        return rate_limit_info
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics for all APIs"""
        statuses = self.check_all_apis()
        metrics = {}
        
        for api_name, status in statuses.items():
            config = self.api_configs[api_name]
            metrics[api_name] = {
                'response_time_ms': status.response_time_ms,
                'expected_response_time_ms': config['expected_response_time'],
                'performance_ratio': status.response_time_ms / config['expected_response_time'],
                'uptime_percentage': status.uptime_percentage,
                'error_rate': status.error_rate,
                'last_error': status.last_error,
                'rate_limit_remaining': status.rate_limit_remaining,
                'status_code': status.performance_metrics.get('status_code'),
                'content_length': status.performance_metrics.get('content_length')
            }
        
        return metrics

# Global instance
api_checker = APIHealthChecker()

def get_api_checker() -> APIHealthChecker:
    """Get global API checker instance"""
    return api_checker

if __name__ == "__main__":
    # Test the API checker
    checker = APIHealthChecker()
    
    print("🌐 API Health Checker Test")
    print("=" * 50)
    
    # Check individual APIs
    for api_name in ['birdeye', 'jupiter_price', 'jupiter_swap']:
        print(f"\nChecking {api_name}...")
        status = checker.check_api_health(api_name)
        print(f"  Status: {status.status}")
        print(f"  Response time: {status.response_time_ms:.2f}ms")
        print(f"  Uptime: {status.uptime_percentage:.1f}%")
        if status.last_error:
            print(f"  Last error: {status.last_error}")
    
    # Get summary
    summary = checker.get_api_health_summary()
    print(f"\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
