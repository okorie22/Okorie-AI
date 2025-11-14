#!/usr/bin/env python3
"""
🚀 Anarcho Capital's Performance Monitor
Monitor system performance, cache efficiency, and resource usage
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import deque

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class PerformanceMetrics:
    """Performance metrics data"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_sent_mb: float
    network_recv_mb: float
    cache_hit_rate: float
    api_response_time_ms: float
    price_fetch_time_ms: float
    system_load: float

class PerformanceMonitor:
    """Monitor system performance and resource usage"""
    
    def __init__(self):
        self.metrics_history = deque(maxlen=100)  # Keep last 100 measurements
        self.monitoring_active = False
        self.monitor_thread = None
        self.start_time = datetime.now()
        
        # Performance thresholds
        self.thresholds = {
            'cpu_warning': 70.0,
            'cpu_critical': 90.0,
            'memory_warning': 80.0,
            'memory_critical': 95.0,
            'disk_warning': 85.0,
            'disk_critical': 95.0,
            'cache_hit_warning': 0.7,  # 70%
            'cache_hit_critical': 0.5,  # 50%
            'api_response_warning': 5000.0,  # 5 seconds
            'api_response_critical': 10000.0  # 10 seconds
        }
        
        # Network monitoring
        self.network_start = psutil.net_io_counters()
        self.last_network_check = datetime.now()
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_available_gb = memory.available / (1024**3)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)
            
            # Network usage
            network_current = psutil.net_io_counters()
            time_diff = (datetime.now() - self.last_network_check).total_seconds()
            
            if time_diff > 0:
                network_sent_mb = (network_current.bytes_sent - self.network_start.bytes_sent) / (1024**2) / time_diff
                network_recv_mb = (network_current.bytes_recv - self.network_start.bytes_recv) / (1024**2) / time_diff
            else:
                network_sent_mb = 0
                network_recv_mb = 0
            
            # Update network baseline
            self.network_start = network_current
            self.last_network_check = datetime.now()
            
            # System load (Unix only)
            try:
                system_load = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
            except:
                system_load = 0
            
            # Get cache and API metrics from services
            cache_hit_rate = self._get_cache_hit_rate()
            api_response_time = self._get_api_response_time()
            price_fetch_time = self._get_price_fetch_time()
            
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_gb=memory_used_gb,
                memory_available_gb=memory_available_gb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                cache_hit_rate=cache_hit_rate,
                api_response_time_ms=api_response_time,
                price_fetch_time_ms=price_fetch_time,
                system_load=system_load
            )
            
        except Exception as e:
            # Return default metrics on error
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_gb=0.0,
                memory_available_gb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                cache_hit_rate=0.0,
                api_response_time_ms=0.0,
                price_fetch_time_ms=0.0,
                system_load=0.0
            )
    
    def _get_cache_hit_rate(self) -> float:
        """Get cache hit rate from price service"""
        try:
            from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
            price_service = get_optimized_price_service()
            
            cache_hits = getattr(price_service, 'cache_hits', 0)
            cache_misses = getattr(price_service, 'cache_misses', 0)
            
            total_requests = cache_hits + cache_misses
            if total_requests > 0:
                return cache_hits / total_requests
            return 0.0
            
        except Exception:
            return 0.0
    
    def _get_api_response_time(self) -> float:
        """Get average API response time"""
        try:
            from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
            api_manager = get_shared_api_manager()
            
            # Get average response time from API manager
            if hasattr(api_manager, 'avg_response_time_ms'):
                return api_manager.avg_response_time_ms
            return 0.0
            
        except Exception:
            return 0.0
    
    def _get_price_fetch_time(self) -> float:
        """Get average price fetch time"""
        try:
            from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
            price_service = get_optimized_price_service()
            
            if hasattr(price_service, 'avg_fetch_time_ms'):
                return price_service.avg_fetch_time_ms
            return 0.0
            
        except Exception:
            return 0.0
    
    def start_monitoring(self, interval_seconds: int = 30):
        """Start continuous performance monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_worker,
            args=(interval_seconds,),
            daemon=True
        )
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop continuous performance monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _monitoring_worker(self, interval_seconds: int):
        """Background monitoring worker"""
        while self.monitoring_active:
            try:
                metrics = self.get_current_metrics()
                self.metrics_history.append(metrics)
                time.sleep(interval_seconds)
            except Exception:
                time.sleep(interval_seconds)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary with current and historical data"""
        current_metrics = self.get_current_metrics()
        
        if not self.metrics_history:
            return {
                'current': self._format_metrics(current_metrics),
                'averages': {},
                'trends': {},
                'warnings': [],
                'uptime_hours': 0
            }
        
        # Calculate averages
        cpu_values = [m.cpu_percent for m in self.metrics_history]
        memory_values = [m.memory_percent for m in self.metrics_history]
        cache_values = [m.cache_hit_rate for m in self.metrics_history]
        api_values = [m.api_response_time_ms for m in self.metrics_history]
        
        averages = {
            'cpu_percent': sum(cpu_values) / len(cpu_values),
            'memory_percent': sum(memory_values) / len(memory_values),
            'cache_hit_rate': sum(cache_values) / len(cache_values),
            'api_response_time_ms': sum(api_values) / len(api_values)
        }
        
        # Calculate trends (comparing first half to second half)
        mid_point = len(self.metrics_history) // 2
        if mid_point > 0:
            first_half_cpu = sum(cpu_values[:mid_point]) / mid_point
            second_half_cpu = sum(cpu_values[mid_point:]) / (len(cpu_values) - mid_point)
            
            trends = {
                'cpu_trend': 'increasing' if second_half_cpu > first_half_cpu else 'decreasing',
                'memory_trend': 'increasing' if memory_values[-1] > memory_values[0] else 'decreasing'
            }
        else:
            trends = {'cpu_trend': 'stable', 'memory_trend': 'stable'}
        
        # Check for warnings
        warnings = self._check_performance_warnings(current_metrics)
        
        # Calculate uptime
        uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600
        
        return {
            'current': self._format_metrics(current_metrics),
            'averages': averages,
            'trends': trends,
            'warnings': warnings,
            'uptime_hours': uptime_hours
        }
    
    def _format_metrics(self, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """Format metrics for display"""
        return {
            'timestamp': metrics.timestamp.isoformat(),
            'cpu_percent': round(metrics.cpu_percent, 1),
            'memory_percent': round(metrics.memory_percent, 1),
            'memory_used_gb': round(metrics.memory_used_gb, 2),
            'memory_available_gb': round(metrics.memory_available_gb, 2),
            'disk_usage_percent': round(metrics.disk_usage_percent, 1),
            'disk_free_gb': round(metrics.disk_free_gb, 2),
            'network_sent_mb': round(metrics.network_sent_mb, 2),
            'network_recv_mb': round(metrics.network_recv_mb, 2),
            'cache_hit_rate': round(metrics.cache_hit_rate, 3),
            'api_response_time_ms': round(metrics.api_response_time_ms, 1),
            'price_fetch_time_ms': round(metrics.price_fetch_time_ms, 1),
            'system_load': round(metrics.system_load, 2)
        }
    
    def _check_performance_warnings(self, metrics: PerformanceMetrics) -> List[str]:
        """Check for performance warnings"""
        warnings = []
        
        # CPU warnings
        if metrics.cpu_percent > self.thresholds['cpu_critical']:
            warnings.append(f"CRITICAL: CPU usage at {metrics.cpu_percent:.1f}%")
        elif metrics.cpu_percent > self.thresholds['cpu_warning']:
            warnings.append(f"WARNING: CPU usage at {metrics.cpu_percent:.1f}%")
        
        # Memory warnings
        if metrics.memory_percent > self.thresholds['memory_critical']:
            warnings.append(f"CRITICAL: Memory usage at {metrics.memory_percent:.1f}%")
        elif metrics.memory_percent > self.thresholds['memory_warning']:
            warnings.append(f"WARNING: Memory usage at {metrics.memory_percent:.1f}%")
        
        # Disk warnings
        if metrics.disk_usage_percent > self.thresholds['disk_critical']:
            warnings.append(f"CRITICAL: Disk usage at {metrics.disk_usage_percent:.1f}%")
        elif metrics.disk_usage_percent > self.thresholds['disk_warning']:
            warnings.append(f"WARNING: Disk usage at {metrics.disk_usage_percent:.1f}%")
        
        # Cache warnings
        if metrics.cache_hit_rate < self.thresholds['cache_hit_critical']:
            warnings.append(f"CRITICAL: Cache hit rate at {metrics.cache_hit_rate:.1%}")
        elif metrics.cache_hit_rate < self.thresholds['cache_hit_warning']:
            warnings.append(f"WARNING: Cache hit rate at {metrics.cache_hit_rate:.1%}")
        
        # API response warnings
        if metrics.api_response_time_ms > self.thresholds['api_response_critical']:
            warnings.append(f"CRITICAL: API response time at {metrics.api_response_time_ms:.1f}ms")
        elif metrics.api_response_time_ms > self.thresholds['api_response_warning']:
            warnings.append(f"WARNING: API response time at {metrics.api_response_time_ms:.1f}ms")
        
        return warnings
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """Get detailed resource usage information"""
        current_metrics = self.get_current_metrics()
        
        # Get process information
        process = psutil.Process()
        process_memory = process.memory_info()
        process_cpu = process.cpu_percent()
        
        # Get system information
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        return {
            'system': {
                'uptime_hours': uptime.total_seconds() / 3600,
                'boot_time': boot_time.isoformat(),
                'cpu_count': psutil.cpu_count(),
                'total_memory_gb': psutil.virtual_memory().total / (1024**3)
            },
            'current': self._format_metrics(current_metrics),
            'process': {
                'pid': process.pid,
                'memory_mb': process_memory.rss / (1024**2),
                'cpu_percent': process_cpu,
                'threads': process.num_threads(),
                'open_files': len(process.open_files()) if hasattr(process, 'open_files') else 0
            }
        }
    
    def get_performance_recommendations(self) -> List[str]:
        """Get performance optimization recommendations"""
        current_metrics = self.get_current_metrics()
        recommendations = []
        
        # CPU recommendations
        if current_metrics.cpu_percent > 80:
            recommendations.append("Consider reducing concurrent operations or optimizing algorithms")
        
        # Memory recommendations
        if current_metrics.memory_percent > 85:
            recommendations.append("Consider implementing memory cleanup or increasing system memory")
        
        # Disk recommendations
        if current_metrics.disk_usage_percent > 90:
            recommendations.append("Consider cleaning up old log files or increasing disk space")
        
        # Cache recommendations
        if current_metrics.cache_hit_rate < 0.6:
            recommendations.append("Consider increasing cache size or improving cache strategy")
        
        # API recommendations
        if current_metrics.api_response_time_ms > 5000:
            recommendations.append("Consider implementing API request batching or using faster endpoints")
        
        return recommendations

# Global instance
performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    return performance_monitor

if __name__ == "__main__":
    # Test the performance monitor
    monitor = PerformanceMonitor()
    
    print("🚀 Performance Monitor Test")
    print("=" * 50)
    
    # Get current metrics
    metrics = monitor.get_current_metrics()
    print(f"CPU: {metrics.cpu_percent:.1f}%")
    print(f"Memory: {metrics.memory_percent:.1f}%")
    print(f"Disk: {metrics.disk_usage_percent:.1f}%")
    print(f"Cache hit rate: {metrics.cache_hit_rate:.1%}")
    print(f"API response time: {metrics.api_response_time_ms:.1f}ms")
    
    # Get summary
    summary = monitor.get_performance_summary()
    print(f"\nSummary:")
    print(f"  Uptime: {summary['uptime_hours']:.1f} hours")
    print(f"  Warnings: {len(summary['warnings'])}")
    for warning in summary['warnings']:
        print(f"    - {warning}")
    
    # Get recommendations
    recommendations = monitor.get_performance_recommendations()
    if recommendations:
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
