"""
🌙 Anarcho Capital's Redis Health Check Utility
Diagnoses Redis connectivity and event bus functionality
Built with love by Anarcho Capital 🚀
"""

import redis
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime
from termcolor import cprint, colored

class RedisHealthCheck:
    """
    Comprehensive Redis health check and diagnostics utility
    """

    def __init__(self, host: str = 'localhost', port: int = 6379,
                 password: Optional[str] = None, db: int = 0):
        """
        Initialize Redis health checker

        Args:
            host: Redis server host
            port: Redis server port
            password: Redis password (optional)
            db: Redis database number
        """
        self.host = host
        self.port = port
        self.password = password
        self.db = db

        # Test connection parameters
        self.connection_params = {
            'host': host,
            'port': port,
            'db': db,
            'password': password,
            'socket_timeout': 5,
            'socket_connect_timeout': 5
        }

    def run_full_diagnostic(self) -> Dict[str, Any]:
        """
        Run complete Redis health diagnostic

        Returns:
            dict: Comprehensive health report
        """
        cprint("[SEARCH] Running Redis Health Diagnostic...", "cyan")
        cprint("=" * 50, "cyan")

        report = {
            'timestamp': datetime.now().isoformat(),
            'connection_test': self.test_basic_connection(),
            'performance_test': self.test_performance(),
            'pubsub_test': self.test_pubsub_functionality(),
            'memory_analysis': self.analyze_memory_usage(),
            'event_bus_test': self.test_event_bus_integration(),
            'recommendations': []
        }

        # Generate recommendations
        report['recommendations'] = self.generate_recommendations(report)

        # Print summary
        self.print_diagnostic_summary(report)

        return report

    def test_basic_connection(self) -> Dict[str, Any]:
        """Test basic Redis connection"""
        cprint("[PLUG] Testing basic connection...", "yellow")

        try:
            # Test connection
            client = redis.Redis(**self.connection_params)
            start_time = time.time()
            client.ping()
            ping_time = (time.time() - start_time) * 1000  # ms

            # Get server info
            info = client.info()

            return {
                'status': 'healthy',
                'ping_time_ms': round(ping_time, 2),
                'redis_version': info.get('redis_version'),
                'connected_clients': info.get('connected_clients'),
                'uptime_seconds': info.get('uptime_in_seconds'),
                'used_memory_human': info.get('used_memory_human')
            }

        except redis.ConnectionError as e:
            return {
                'status': 'connection_failed',
                'error': f"Connection error: {str(e)}"
            }
        except redis.AuthenticationError as e:
            return {
                'status': 'auth_failed',
                'error': f"Authentication error: {str(e)}"
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': f"Unexpected error: {str(e)}"
            }

    def test_performance(self) -> Dict[str, Any]:
        """Test Redis performance with various operations"""
        cprint("[BOLT] Testing performance...", "yellow")

        try:
            client = redis.Redis(**self.connection_params)

            # Test SET/GET performance
            test_key = f"health_check_test_{int(time.time())}"

            # SET operation
            start_time = time.time()
            client.set(test_key, "test_value", ex=60)  # Expire in 60 seconds
            set_time = (time.time() - start_time) * 1000

            # GET operation
            start_time = time.time()
            value = client.get(test_key)
            get_time = (time.time() - start_time) * 1000

            # Pipeline test (batch operations)
            start_time = time.time()
            with client.pipeline() as pipe:
                for i in range(10):
                    pipe.set(f"pipeline_test_{i}", f"value_{i}", ex=60)
                pipe.execute()
            pipeline_time = (time.time() - start_time) * 1000

            # Cleanup
            client.delete(test_key)
            for i in range(10):
                client.delete(f"pipeline_test_{i}")

            return {
                'status': 'healthy',
                'set_time_ms': round(set_time, 2),
                'get_time_ms': round(get_time, 2),
                'pipeline_time_ms': round(pipeline_time, 2),
                'value_retrieved': value.decode() if value else None
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': f"Performance test failed: {str(e)}"
            }

    def test_pubsub_functionality(self) -> Dict[str, Any]:
        """Test publish/subscribe functionality"""
        cprint("[RADIO] Testing pub/sub functionality...", "yellow")

        try:
            client = redis.Redis(**self.connection_params)
            received_messages = []

            def test_callback(message):
                received_messages.append(message)

            # Create pub/sub instance
            pubsub = client.pubsub()
            test_channel = f"health_check_channel_{int(time.time())}"

            # Subscribe to channel
            pubsub.subscribe(**{test_channel: test_callback})

            # Start listener thread
            pubsub_thread = pubsub.run_in_thread(sleep_time=0.01, daemon=True)

            # Give thread time to start
            time.sleep(0.1)

            # Publish test message
            test_message = {
                'test': 'pubsub_health_check',
                'timestamp': datetime.now().isoformat()
            }

            client.publish(test_channel, json.dumps(test_message))

            # Wait for message
            timeout = 2.0
            start_time = time.time()
            while len(received_messages) == 0 and (time.time() - start_time) < timeout:
                time.sleep(0.01)

            # Stop listener
            pubsub_thread.stop()
            pubsub.close()

            if received_messages:
                received_data = json.loads(received_messages[0]['data'])
                return {
                    'status': 'healthy',
                    'message_received': True,
                    'message_content': received_data,
                    'response_time_ms': round((time.time() - start_time) * 1000, 2)
                }
            else:
                return {
                    'status': 'pubsub_failed',
                    'message_received': False,
                    'error': 'No message received within timeout'
                }

        except Exception as e:
            return {
                'status': 'error',
                'error': f"Pub/sub test failed: {str(e)}"
            }

    def analyze_memory_usage(self) -> Dict[str, Any]:
        """Analyze Redis memory usage"""
        cprint("[BRAIN] Analyzing memory usage...", "yellow")

        try:
            client = redis.Redis(**self.connection_params)
            info = client.info('memory')

            return {
                'status': 'healthy',
                'used_memory': info.get('used_memory'),
                'used_memory_human': info.get('used_memory_human'),
                'used_memory_peak': info.get('used_memory_peak'),
                'used_memory_peak_human': info.get('used_memory_peak_human'),
                'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio'),
                'total_system_memory': info.get('total_system_memory'),
                'total_system_memory_human': info.get('total_system_memory_human')
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': f"Memory analysis failed: {str(e)}"
            }

    def test_event_bus_integration(self) -> Dict[str, Any]:
        """Test integration with our Redis event bus"""
        cprint("[SYNC] Testing event bus integration...", "yellow")

        try:
            # Import our event bus
            from src.scripts.shared_services.redis_event_bus import get_event_bus

            event_bus = get_event_bus()
            test_results = []

            # Test 1: Health check
            health = event_bus.health_check()
            test_results.append({
                'test': 'health_check',
                'status': health.get('healthy', False),
                'details': health
            })

            # Test 2: Basic publish/subscribe
            received_data = None

            def test_callback(data):
                nonlocal received_data
                received_data = data

            test_channel = f"health_test_{int(time.time())}"
            event_bus.subscribe(test_channel, test_callback)

            # Publish test event
            test_event = {
                'test_type': 'health_check',
                'timestamp': datetime.now().isoformat(),
                'message': 'Redis event bus integration test'
            }

            event_bus.publish(test_channel, test_event)

            # Wait for message
            time.sleep(0.2)

            test_results.append({
                'test': 'pubsub_integration',
                'status': received_data is not None,
                'received_data': received_data
            })

            # Test 3: Statistics
            stats = event_bus.get_stats()
            test_results.append({
                'test': 'statistics',
                'status': 'healthy',  # Stats call succeeded
                'details': stats
            })

            return {
                'status': 'healthy' if all(r['status'] for r in test_results) else 'issues_found',
                'tests': test_results
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': f"Event bus integration test failed: {str(e)}"
            }

    def generate_recommendations(self, report: Dict[str, Any]) -> list:
        """Generate recommendations based on diagnostic results"""
        recommendations = []

        # Connection issues
        conn_test = report.get('connection_test', {})
        if conn_test.get('status') != 'healthy':
            recommendations.append({
                'priority': 'critical',
                'category': 'connection',
                'message': f"Redis connection failed: {conn_test.get('error', 'Unknown error')}",
                'solution': "Check Redis server is running and connection parameters are correct"
            })

        # Performance issues
        perf_test = report.get('performance_test', {})
        if perf_test.get('status') == 'healthy':
            if perf_test.get('set_time_ms', 0) > 10:  # >10ms is slow
                recommendations.append({
                    'priority': 'medium',
                    'category': 'performance',
                    'message': f"Redis SET operations are slow ({perf_test.get('set_time_ms')}ms)",
                    'solution': "Consider Redis performance optimization or network latency issues"
                })

        # Memory issues
        mem_analysis = report.get('memory_analysis', {})
        if mem_analysis.get('status') == 'healthy':
            used_memory = mem_analysis.get('used_memory', 0)
            if used_memory > 500 * 1024 * 1024:  # >500MB
                recommendations.append({
                    'priority': 'medium',
                    'category': 'memory',
                    'message': f"High Redis memory usage ({mem_analysis.get('used_memory_human')})",
                    'solution': "Monitor memory usage and consider cleanup of old keys"
                })

        # PubSub issues
        pubsub_test = report.get('pubsub_test', {})
        if pubsub_test.get('status') != 'healthy':
            recommendations.append({
                'priority': 'high',
                'category': 'pubsub',
                'message': "Redis pub/sub functionality has issues",
                'solution': "Check Redis pub/sub configuration and network connectivity"
            })

        # Event bus issues
        event_test = report.get('event_bus_test', {})
        if event_test.get('status') != 'healthy':
            recommendations.append({
                'priority': 'high',
                'category': 'event_bus',
                'message': "Event bus integration has issues",
                'solution': "Check event bus configuration and Redis connectivity"
            })

        return recommendations

    def print_diagnostic_summary(self, report: Dict[str, Any]):
        """Print a formatted diagnostic summary"""
        cprint("\n[CHART] Redis Health Diagnostic Summary", "cyan")
        cprint("=" * 50, "cyan")

        # Overall status
        all_tests = [report[k] for k in ['connection_test', 'performance_test',
                                       'pubsub_test', 'memory_analysis', 'event_bus_test']
                    if isinstance(report.get(k), dict)]

        healthy_tests = sum(1 for test in all_tests if test.get('status') == 'healthy')
        total_tests = len(all_tests)

        if healthy_tests == total_tests:
            cprint(f"[CHECK] Overall Status: HEALTHY ({healthy_tests}/{total_tests} tests passed)", "green")
        elif healthy_tests >= total_tests * 0.8:
            cprint(f"[WARN] Overall Status: MOSTLY HEALTHY ({healthy_tests}/{total_tests} tests passed)", "yellow")
        else:
            cprint(f"[ERROR] Overall Status: ISSUES DETECTED ({healthy_tests}/{total_tests} tests passed)", "red")

        # Key metrics
        conn = report.get('connection_test', {})
        if conn.get('status') == 'healthy':
            cprint(f"[PLUG] Connection: [CHECK] Healthy ({conn.get('ping_time_ms', 0)}ms ping)", "green")
        else:
            cprint(f"[PLUG] Connection: [ERROR] {conn.get('status', 'unknown')}", "red")

        perf = report.get('performance_test', {})
        if perf.get('status') == 'healthy':
            cprint(f"[BOLT] Performance: [CHECK] Good ({perf.get('get_time_ms', 0)}ms GET)", "green")
        else:
            cprint(f"[BOLT] Performance: [ERROR] {perf.get('status', 'unknown')}", "red")

        pubsub = report.get('pubsub_test', {})
        if pubsub.get('status') == 'healthy':
            cprint(f"[RADIO] Pub/Sub: [CHECK] Working ({pubsub.get('response_time_ms', 0)}ms)", "green")
        else:
            cprint(f"[RADIO] Pub/Sub: [ERROR] {pubsub.get('status', 'unknown')}", "red")

        # Recommendations
        recommendations = report.get('recommendations', [])
        if recommendations:
            cprint(f"\n[HINT] Recommendations ({len(recommendations)}):", "yellow")
            for rec in recommendations[:3]:  # Show top 3
                priority_colors = {'critical': 'red', 'high': 'red', 'medium': 'yellow', 'low': 'blue'}
                color = priority_colors.get(rec.get('priority', 'low'), 'white')
                cprint(f"   • {rec['message']}", color)
                cprint(f"     [HINT] {rec['solution']}", "cyan")

        cprint("=" * 50, "cyan")


def main():
    """Command-line interface for Redis health check"""
    import argparse

    parser = argparse.ArgumentParser(description="Redis Health Check Utility")
    parser.add_argument('--host', default='localhost', help='Redis host')
    parser.add_argument('--port', type=int, default=6379, help='Redis port')
    parser.add_argument('--password', help='Redis password')
    parser.add_argument('--db', type=int, default=0, help='Redis database')

    args = parser.parse_args()

    # Run diagnostic
    checker = RedisHealthCheck(
        host=args.host,
        port=args.port,
        password=args.password,
        db=args.db
    )

    try:
        report = checker.run_full_diagnostic()

        # Exit with appropriate code
        if all(test.get('status') == 'healthy'
               for test in [report.get(k, {}) for k in ['connection_test', 'performance_test',
                                                       'pubsub_test', 'memory_analysis', 'event_bus_test']]
               if isinstance(test, dict)):
            exit(0)  # Success
        else:
            exit(1)  # Issues found

    except Exception as e:
        cprint(f"[ERROR] Health check failed: {e}", "red")
        exit(1)


if __name__ == "__main__":
    main()
