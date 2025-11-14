#!/usr/bin/env python3
"""
🔗 Anarcho Capital's Integration Checker
Monitor webhook registration, IP registration, and cloud sync systems
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
class IntegrationStatus:
    """Integration status information"""
    component: str
    status: str  # 'connected', 'degraded', 'disconnected', 'unknown'
    last_check: datetime
    response_time_ms: float
    error_message: Optional[str]
    performance_metrics: Dict[str, Any]

class IntegrationChecker:
    """Monitor system integration health"""
    
    def __init__(self):
        self.integrations = {
            'helius_webhook': {
                'api_key': 'HELIUS_API_KEY',
                'test_url': 'https://api.helius.xyz/v0/webhooks',
                'timeout': 10
            },
            'ip_registration': {
                'service_file': 'src/scripts/shared_services/ip_registration_service.py',
                'timeout': 5
            },
            'cloud_sync': {
                'service_file': 'src/scripts/database/cloud_database.py',
                'timeout': 10
            },
            'log_rotation': {
                'log_dir': 'logs',
                'max_size_mb': 10,
                'backup_count': 5
            }
        }
    
    def check_helius_webhook(self) -> IntegrationStatus:
        """Check Helius webhook registration status"""
        try:
            api_key = os.getenv('HELIUS_API_KEY')
            if not api_key:
                return IntegrationStatus(
                    component='helius_webhook',
                    status='disconnected',
                    last_check=datetime.now(),
                    response_time_ms=0,
                    error_message='HELIUS_API_KEY not configured',
                    performance_metrics={}
                )
            
            start_time = time.time()
            
            # Test webhook API
            response = requests.get(
                f"https://api.helius.xyz/v0/webhooks?api-key={api_key}",
                timeout=10
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                webhooks = response.json()
                
                # Check webhook count and limits
                webhook_count = len(webhooks)
                max_webhooks = 1  # Free tier limit
                
                if webhook_count >= max_webhooks:
                    status = 'degraded'
                    error_message = f"Webhook limit reached ({webhook_count}/{max_webhooks})"
                else:
                    status = 'connected'
                    error_message = None
                
                performance_metrics = {
                    'webhook_count': webhook_count,
                    'max_webhooks': max_webhooks,
                    'webhooks': [{
                        'id': wh.get('webhookID', 'unknown'),
                        'url': wh.get('webhookURL', 'unknown'),
                        'account_count': len(wh.get('accountAddresses', []))
                    } for wh in webhooks]
                }
                
            elif response.status_code == 401:
                status = 'disconnected'
                error_message = 'Invalid API key'
                performance_metrics = {}
            else:
                status = 'disconnected'
                error_message = f"HTTP {response.status_code}: {response.text}"
                performance_metrics = {}
            
        except requests.exceptions.Timeout:
            return IntegrationStatus(
                component='helius_webhook',
                status='disconnected',
                last_check=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
                error_message='Request timeout',
                performance_metrics={}
            )
        except Exception as e:
            return IntegrationStatus(
                component='helius_webhook',
                status='disconnected',
                last_check=datetime.now(),
                response_time_ms=0,
                error_message=str(e),
                performance_metrics={}
            )
        
        return IntegrationStatus(
            component='helius_webhook',
            status=status,
            last_check=datetime.now(),
            response_time_ms=response_time_ms,
            error_message=error_message,
            performance_metrics=performance_metrics
        )
    
    def check_ip_registration(self) -> IntegrationStatus:
        """Check IP registration service status"""
        try:
            service_file = self.integrations['ip_registration']['service_file']
            
            if not os.path.exists(service_file):
                return IntegrationStatus(
                    component='ip_registration',
                    status='disconnected',
                    last_check=datetime.now(),
                    response_time_ms=0,
                    error_message='IP registration service file not found',
                    performance_metrics={}
                )
            
            start_time = time.time()
            
            # Try to import and test the service
            from src.scripts.shared_services.ip_registration_service import IPRegistrationService
            
            service = IPRegistrationService()
            
            # Test service functionality
            test_result = service.get_registered_ip()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if test_result:
                status = 'connected'
                error_message = None
            else:
                status = 'degraded'
                error_message = 'No registered IP found'
            
            performance_metrics = {
                'service_available': True,
                'registered_ip': test_result,
                'service_initialized': True
            }
            
        except ImportError:
            return IntegrationStatus(
                component='ip_registration',
                status='disconnected',
                last_check=datetime.now(),
                response_time_ms=0,
                error_message='IP registration service not available',
                performance_metrics={}
            )
        except Exception as e:
            return IntegrationStatus(
                component='ip_registration',
                status='disconnected',
                last_check=datetime.now(),
                response_time_ms=0,
                error_message=str(e),
                performance_metrics={}
            )
        
        return IntegrationStatus(
            component='ip_registration',
            status=status,
            last_check=datetime.now(),
            response_time_ms=response_time_ms,
            error_message=error_message,
            performance_metrics=performance_metrics
        )
    
    def check_cloud_sync(self) -> IntegrationStatus:
        """Check cloud database sync status"""
        try:
            start_time = time.time()
            
            from src.scripts.database.cloud_database import get_cloud_database_manager
            
            cloud_db = get_cloud_database_manager()
            
            if not cloud_db:
                return IntegrationStatus(
                    component='cloud_sync',
                    status='disconnected',
                    last_check=datetime.now(),
                    response_time_ms=0,
                    error_message='Cloud database manager not available',
                    performance_metrics={}
                )
            
            # Test database connection
            test_query = "SELECT 1 as test"
            result = cloud_db.execute_query(test_query)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if result is not None:
                status = 'connected'
                error_message = None
            else:
                status = 'degraded'
                error_message = 'Database query failed'
            
            performance_metrics = {
                'cloud_db_available': True,
                'connection_test_passed': result is not None,
                'response_time_ms': response_time_ms
            }
            
        except ImportError:
            return IntegrationStatus(
                component='cloud_sync',
                status='disconnected',
                last_check=datetime.now(),
                response_time_ms=0,
                error_message='Cloud database service not available',
                performance_metrics={}
            )
        except Exception as e:
            return IntegrationStatus(
                component='cloud_sync',
                status='disconnected',
                last_check=datetime.now(),
                response_time_ms=0,
                error_message=str(e),
                performance_metrics={}
            )
        
        return IntegrationStatus(
            component='cloud_sync',
            status=status,
            last_check=datetime.now(),
            response_time_ms=response_time_ms,
            error_message=error_message,
            performance_metrics=performance_metrics
        )
    
    def check_log_rotation(self) -> IntegrationStatus:
        """Check log file rotation status"""
        try:
            log_dir = self.integrations['log_rotation']['log_dir']
            max_size_mb = self.integrations['log_rotation']['max_size_mb']
            backup_count = self.integrations['log_rotation']['backup_count']
            
            if not os.path.exists(log_dir):
                return IntegrationStatus(
                    component='log_rotation',
                    status='disconnected',
                    last_check=datetime.now(),
                    response_time_ms=0,
                    error_message='Log directory not found',
                    performance_metrics={}
                )
            
            start_time = time.time()
            
            # Check log files
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
            backup_files = [f for f in os.listdir(log_dir) if f.endswith('.log.1') or f.endswith('.log.2')]
            
            # Check main log file size
            main_log_file = os.path.join(log_dir, 'trading_system.log')
            main_log_size_mb = 0
            if os.path.exists(main_log_file):
                main_log_size_mb = os.path.getsize(main_log_file) / (1024 * 1024)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Determine status
            if main_log_size_mb > max_size_mb * 1.5:  # 50% over limit
                status = 'degraded'
                error_message = f'Main log file too large: {main_log_size_mb:.1f}MB (limit: {max_size_mb}MB)'
            elif len(backup_files) >= backup_count:
                status = 'degraded'
                error_message = f'Too many backup files: {len(backup_files)} (limit: {backup_count})'
            elif main_log_size_mb > max_size_mb:
                status = 'degraded'
                error_message = f'Log file approaching limit: {main_log_size_mb:.1f}MB (limit: {max_size_mb}MB)'
            else:
                status = 'connected'
                error_message = None
            
            performance_metrics = {
                'log_files_count': len(log_files),
                'backup_files_count': len(backup_files),
                'main_log_size_mb': main_log_size_mb,
                'max_size_mb': max_size_mb,
                'backup_count': backup_count,
                'rotation_needed': main_log_size_mb > max_size_mb
            }
            
        except Exception as e:
            return IntegrationStatus(
                component='log_rotation',
                status='disconnected',
                last_check=datetime.now(),
                response_time_ms=0,
                error_message=str(e),
                performance_metrics={}
            )
        
        return IntegrationStatus(
            component='log_rotation',
            status=status,
            last_check=datetime.now(),
            response_time_ms=response_time_ms,
            error_message=error_message,
            performance_metrics=performance_metrics
        )
    
    def check_all_integrations(self) -> Dict[str, IntegrationStatus]:
        """Check all integration components"""
        statuses = {}
        
        statuses['helius_webhook'] = self.check_helius_webhook()
        statuses['ip_registration'] = self.check_ip_registration()
        statuses['cloud_sync'] = self.check_cloud_sync()
        statuses['log_rotation'] = self.check_log_rotation()
        
        return statuses
    
    def get_integration_summary(self) -> Dict[str, Any]:
        """Get overall integration summary"""
        statuses = self.check_all_integrations()
        
        total_integrations = len(statuses)
        connected_integrations = sum(1 for status in statuses.values() if status.status == 'connected')
        degraded_integrations = sum(1 for status in statuses.values() if status.status == 'degraded')
        disconnected_integrations = sum(1 for status in statuses.values() if status.status == 'disconnected')
        
        # Calculate average response time
        response_times = [status.response_time_ms for status in statuses.values() if status.response_time_ms > 0]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Count integrations with errors
        error_integrations = sum(1 for status in statuses.values() if status.error_message)
        
        # Find slowest integration
        slowest_integration = None
        if response_times:
            slowest_status = max(statuses.values(), key=lambda s: s.response_time_ms)
            slowest_integration = {
                'component': slowest_status.component,
                'response_time_ms': slowest_status.response_time_ms
            }
        
        return {
            'total_integrations': total_integrations,
            'connected_integrations': connected_integrations,
            'degraded_integrations': degraded_integrations,
            'disconnected_integrations': disconnected_integrations,
            'avg_response_time_ms': avg_response_time,
            'error_integrations': error_integrations,
            'slowest_integration': slowest_integration,
            'integration_percentage': (connected_integrations / total_integrations * 100) if total_integrations > 0 else 0
        }
    
    def get_integration_recommendations(self) -> List[str]:
        """Get integration optimization recommendations"""
        statuses = self.check_all_integrations()
        recommendations = []
        
        # Check for disconnected integrations
        for component, status in statuses.items():
            if status.status == 'disconnected':
                recommendations.append(f"Fix {component}: {status.error_message}")
            elif status.status == 'degraded':
                recommendations.append(f"Optimize {component}: {status.error_message}")
        
        # Check for slow integrations
        for component, status in statuses.items():
            if status.response_time_ms > 5000:  # 5 seconds
                recommendations.append(f"Optimize {component} performance (response time: {status.response_time_ms:.1f}ms)")
        
        return recommendations

# Global instance
integration_checker = IntegrationChecker()

def get_integration_checker() -> IntegrationChecker:
    """Get global integration checker instance"""
    return integration_checker

if __name__ == "__main__":
    # Test the integration checker
    checker = IntegrationChecker()
    
    print("🔗 Integration Checker Test")
    print("=" * 50)
    
    # Check individual integrations
    for component in ['helius_webhook', 'ip_registration', 'cloud_sync', 'log_rotation']:
        print(f"\nChecking {component}...")
        if component == 'helius_webhook':
            status = checker.check_helius_webhook()
        elif component == 'ip_registration':
            status = checker.check_ip_registration()
        elif component == 'cloud_sync':
            status = checker.check_cloud_sync()
        else:
            status = checker.check_log_rotation()
        
        print(f"  Status: {status.status}")
        print(f"  Response time: {status.response_time_ms:.2f}ms")
        if status.error_message:
            print(f"  Error: {status.error_message}")
    
    # Get summary
    summary = checker.get_integration_summary()
    print(f"\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Get recommendations
    recommendations = checker.get_integration_recommendations()
    if recommendations:
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
