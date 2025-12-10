#!/usr/bin/env python3
"""
🌐 Anarcho Capital's External Dependencies Checker
Monitor blockchain connectivity, staking protocols, and external services
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

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class ExternalDependencyStatus:
    """External dependency health status"""
    name: str
    status: str  # 'healthy', 'degraded', 'unhealthy', 'unknown'
    response_time_ms: float
    last_check: datetime
    error_message: Optional[str]
    performance_metrics: Dict[str, Any]

class ExternalDependenciesChecker:
    """Monitor health of external dependencies"""
    
    def __init__(self):
        self.dependencies = {
            'solana_rpc': {
                'test_url': 'https://api.mainnet-beta.solana.com',
                'test_payload': {
                    "jsonrpc": "2.0",
                    "id": "health-check",
                    "method": "getHealth"
                },
                'timeout': 10
            },
            'helius_rpc': {
                'test_url': os.getenv('RPC_ENDPOINT', 'https://mainnet.helius-rpc.com'),
                'test_payload': {
                    "jsonrpc": "2.0",
                    "id": "health-check",
                    "method": "getHealth"
                },
                'timeout': 10
            },
            'quicknode_rpc': {
                'test_url': os.getenv('QUICKNODE_RPC_ENDPOINT', 'https://radial-maximum-tent.solana-mainnet.quiknode.pro'),
                'test_payload': {
                    "jsonrpc": "2.0",
                    "id": "health-check",
                    "method": "getHealth"
                },
                'timeout': 10
            },
            'blazestake_api': {
                'test_url': 'https://stake.solblaze.org/api/v1/apy',
                'test_payload': None,
                'timeout': 5
            },
            'jupiter_lst_api': {
                'test_url': 'https://lite-api.jup.ag/tokens/v2/tag?query=lst',
                'test_payload': None,
                'timeout': 5
            },
            'sanctum_api': {
                'test_url': 'https://api.sanctum.so/v1/lst',
                'test_payload': None,
                'timeout': 5
            },
            'cloud_database': {
                'test_url': None,  # Will be tested differently
                'test_payload': None,
                'timeout': 5
            }
        }
    
    def check_solana_rpc(self) -> ExternalDependencyStatus:
        """Check Solana RPC connectivity"""
        return self._check_rpc_dependency('solana_rpc')
    
    def check_helius_rpc(self) -> ExternalDependencyStatus:
        """Check Helius RPC connectivity"""
        return self._check_rpc_dependency('helius_rpc')
    
    def check_quicknode_rpc(self) -> ExternalDependencyStatus:
        """Check QuickNode RPC connectivity"""
        return self._check_rpc_dependency('quicknode_rpc')
    
    def _check_rpc_dependency(self, dep_name: str) -> ExternalDependencyStatus:
        """Check RPC dependency health"""
        if dep_name not in self.dependencies:
            return ExternalDependencyStatus(
                name=dep_name,
                status='unknown',
                response_time_ms=0,
                last_check=datetime.now(),
                error_message=f"Unknown dependency: {dep_name}",
                performance_metrics={}
            )
        
        dep_config = self.dependencies[dep_name]
        start_time = time.time()
        
        try:
            response = requests.post(
                dep_config['test_url'],
                json=dep_config['test_payload'],
                timeout=dep_config['timeout']
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result or 'error' in result:
                    status = 'healthy'
                    error_message = None
                else:
                    status = 'degraded'
                    error_message = 'Unexpected response format'
            elif response.status_code == 401:
                status = 'degraded'  # Auth error is expected for some free RPCs
                error_message = 'Authentication required (normal for free RPC)'
            else:
                status = 'unhealthy'
                error_message = f"HTTP {response.status_code}"
            
            performance_metrics = {
                'status_code': response.status_code,
                'response_size': len(response.content),
                'rpc_method': dep_config['test_payload']['method']
            }
            
            return ExternalDependencyStatus(
                name=dep_name,
                status=status,
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                error_message=error_message,
                performance_metrics=performance_metrics
            )
            
        except requests.exceptions.Timeout:
            return ExternalDependencyStatus(
                name=dep_name,
                status='unhealthy',
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_message='Request timeout',
                performance_metrics={'timeout': True}
            )
        except Exception as e:
            return ExternalDependencyStatus(
                name=dep_name,
                status='unhealthy',
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_message=str(e),
                performance_metrics={'exception': str(e)}
            )
    
    def check_blazestake_api(self) -> ExternalDependencyStatus:
        """Check BlazeStake API health"""
        return self._check_http_dependency('blazestake_api')
    
    def check_jupiter_lst_api(self) -> ExternalDependencyStatus:
        """Check Jupiter LST API health"""
        return self._check_http_dependency('jupiter_lst_api')
    
    def check_sanctum_api(self) -> ExternalDependencyStatus:
        """Check Sanctum API health"""
        return self._check_http_dependency('sanctum_api')
    
    def _check_http_dependency(self, dep_name: str) -> ExternalDependencyStatus:
        """Check HTTP dependency health"""
        if dep_name not in self.dependencies:
            return ExternalDependencyStatus(
                name=dep_name,
                status='unknown',
                response_time_ms=0,
                last_check=datetime.now(),
                error_message=f"Unknown dependency: {dep_name}",
                performance_metrics={}
            )
        
        dep_config = self.dependencies[dep_name]
        start_time = time.time()
        
        try:
            if dep_config['test_payload']:
                response = requests.post(
                    dep_config['test_url'],
                    json=dep_config['test_payload'],
                    timeout=dep_config['timeout']
                )
            else:
                response = requests.get(
                    dep_config['test_url'],
                    timeout=dep_config['timeout']
                )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                status = 'healthy'
                error_message = None
            elif response.status_code == 404:
                status = 'degraded'
                error_message = 'API endpoint not found'
            else:
                status = 'unhealthy'
                error_message = f"HTTP {response.status_code}"
            
            performance_metrics = {
                'status_code': response.status_code,
                'response_size': len(response.content),
                'content_type': response.headers.get('content-type', 'unknown')
            }
            
            return ExternalDependencyStatus(
                name=dep_name,
                status=status,
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                error_message=error_message,
                performance_metrics=performance_metrics
            )
            
        except requests.exceptions.Timeout:
            return ExternalDependencyStatus(
                name=dep_name,
                status='unhealthy',
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_message='Request timeout',
                performance_metrics={'timeout': True}
            )
        except Exception as e:
            return ExternalDependencyStatus(
                name=dep_name,
                status='unhealthy',
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(),
                error_message=str(e),
                performance_metrics={'exception': str(e)}
            )
    
    def check_cloud_database(self) -> ExternalDependencyStatus:
        """Check cloud database connectivity"""
        try:
            from src.scripts.database.cloud_database import get_cloud_database_manager
            
            cloud_db = get_cloud_database_manager()
            
            if not cloud_db:
                return ExternalDependencyStatus(
                    name='cloud_database',
                    status='unhealthy',
                    response_time_ms=0,
                    last_check=datetime.now(),
                    error_message='Cloud database manager not accessible',
                    performance_metrics={}
                )
            
            # Test database connection
            start_time = time.time()
            
            # Try to execute a simple query
            test_query = "SELECT 1 as test"
            result = cloud_db.execute_query(test_query)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if result is not None:
                status = 'healthy'
                error_message = None
            else:
                status = 'degraded'
                error_message = 'Query returned no result'
            
            performance_metrics = {
                'connection_active': True,
                'test_query_successful': result is not None,
                'cloud_db_initialized': True
            }
            
            return ExternalDependencyStatus(
                name='cloud_database',
                status=status,
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                error_message=error_message,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return ExternalDependencyStatus(
                name='cloud_database',
                status='unhealthy',
                response_time_ms=0,
                last_check=datetime.now(),
                error_message=str(e),
                performance_metrics={'exception': str(e)}
            )
    
    def check_file_system(self) -> ExternalDependencyStatus:
        """Check file system health"""
        try:
            start_time = time.time()
            
            # Check critical directories
            critical_dirs = [
                'data',
                'src/data',
                'logs',
                'src/data/charts',
                'src/data/sentiment'
            ]
            
            missing_dirs = []
            for dir_path in critical_dirs:
                if not os.path.exists(dir_path):
                    missing_dirs.append(dir_path)
            
            # Check disk space
            disk_usage = os.statvfs('.')
            free_space_gb = (disk_usage.f_frsize * disk_usage.f_bavail) / (1024**3)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if not missing_dirs and free_space_gb > 1.0:
                status = 'healthy'
                error_message = None
            elif not missing_dirs and free_space_gb > 0.1:
                status = 'degraded'
                error_message = f'Low disk space: {free_space_gb:.1f}GB'
            else:
                status = 'unhealthy'
                if missing_dirs:
                    error_message = f'Missing directories: {", ".join(missing_dirs)}'
                else:
                    error_message = f'Very low disk space: {free_space_gb:.1f}GB'
            
            performance_metrics = {
                'missing_directories': missing_dirs,
                'free_space_gb': free_space_gb,
                'total_directories_checked': len(critical_dirs)
            }
            
            return ExternalDependencyStatus(
                name='file_system',
                status=status,
                response_time_ms=response_time_ms,
                last_check=datetime.now(),
                error_message=error_message,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return ExternalDependencyStatus(
                name='file_system',
                status='unhealthy',
                response_time_ms=0,
                last_check=datetime.now(),
                error_message=str(e),
                performance_metrics={'exception': str(e)}
            )
    
    def check_all_dependencies(self) -> Dict[str, ExternalDependencyStatus]:
        """Check health of all external dependencies"""
        statuses = {}
        
        # RPC dependencies
        statuses['solana_rpc'] = self.check_solana_rpc()
        statuses['helius_rpc'] = self.check_helius_rpc()
        statuses['quicknode_rpc'] = self.check_quicknode_rpc()
        
        # API dependencies
        statuses['blazestake_api'] = self.check_blazestake_api()
        statuses['jupiter_lst_api'] = self.check_jupiter_lst_api()
        statuses['sanctum_api'] = self.check_sanctum_api()
        
        # System dependencies
        statuses['cloud_database'] = self.check_cloud_database()
        statuses['file_system'] = self.check_file_system()
        
        return statuses
    
    def get_dependencies_health_summary(self) -> Dict[str, Any]:
        """Get overall dependencies health summary"""
        statuses = self.check_all_dependencies()
        
        total_deps = len(statuses)
        healthy_deps = sum(1 for status in statuses.values() if status.status == 'healthy')
        degraded_deps = sum(1 for status in statuses.values() if status.status == 'degraded')
        unhealthy_deps = sum(1 for status in statuses.values() if status.status == 'unhealthy')
        
        # Calculate average response time
        response_times = [status.response_time_ms for status in statuses.values() if status.response_time_ms > 0]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Count dependencies with errors
        error_deps = sum(1 for status in statuses.values() if status.error_message)
        
        # Find slowest dependency
        slowest_dep = None
        if response_times:
            slowest_status = max(statuses.values(), key=lambda s: s.response_time_ms)
            slowest_dep = {
                'name': slowest_status.name,
                'response_time_ms': slowest_status.response_time_ms
            }
        
        return {
            'total_dependencies': total_deps,
            'healthy_dependencies': healthy_deps,
            'degraded_dependencies': degraded_deps,
            'unhealthy_dependencies': unhealthy_deps,
            'avg_response_time_ms': avg_response_time,
            'error_dependencies': error_deps,
            'slowest_dependency': slowest_dep,
            'health_percentage': (healthy_deps / total_deps * 100) if total_deps > 0 else 0
        }
    
    def get_dependencies_recommendations(self) -> List[str]:
        """Get recommendations for external dependencies"""
        statuses = self.check_all_dependencies()
        recommendations = []
        
        # Check for unhealthy dependencies
        for dep_name, status in statuses.items():
            if status.status == 'unhealthy':
                recommendations.append(f"Fix critical issues with {dep_name}: {status.error_message}")
            elif status.status == 'degraded':
                recommendations.append(f"Optimize performance of {dep_name}")
        
        # Check for slow dependencies
        for dep_name, status in statuses.items():
            if status.response_time_ms > 5000:  # 5 seconds
                recommendations.append(f"Consider switching from {dep_name} (response time: {status.response_time_ms:.1f}ms)")
        
        return recommendations

# Global instance
deps_checker = ExternalDependenciesChecker()

def get_deps_checker() -> ExternalDependenciesChecker:
    """Get global dependencies checker instance"""
    return deps_checker

if __name__ == "__main__":
    # Test the dependencies checker
    checker = ExternalDependenciesChecker()
    
    print("🌐 External Dependencies Checker Test")
    print("=" * 50)
    
    # Check individual dependencies
    for dep_name in ['solana_rpc', 'helius_rpc', 'blazestake_api', 'file_system']:
        print(f"\nChecking {dep_name}...")
        if dep_name == 'solana_rpc':
            status = checker.check_solana_rpc()
        elif dep_name == 'helius_rpc':
            status = checker.check_helius_rpc()
        elif dep_name == 'blazestake_api':
            status = checker.check_blazestake_api()
        else:
            status = checker.check_file_system()
        
        print(f"  Status: {status.status}")
        print(f"  Response time: {status.response_time_ms:.2f}ms")
        if status.error_message:
            print(f"  Error: {status.error_message}")
    
    # Get summary
    summary = checker.get_dependencies_health_summary()
    print(f"\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Get recommendations
    recommendations = checker.get_dependencies_recommendations()
    if recommendations:
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
