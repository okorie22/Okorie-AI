#!/usr/bin/env python3
"""
🗄️ Anarcho Capital's Database Health Checker
Monitor health and performance of all database systems
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import sqlite3
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class DatabaseHealthStatus:
    """Database health status information"""
    name: str
    status: str  # 'healthy', 'degraded', 'unhealthy', 'unknown'
    file_path: str
    file_size_mb: float
    last_modified: datetime
    connection_time_ms: float
    query_time_ms: float
    table_count: int
    record_count: int
    integrity_check: bool
    performance_metrics: Dict[str, Any]

class DatabaseHealthChecker:
    """Monitor health of all database systems"""
    
    def __init__(self):
        self.databases = {
            'portfolio_history': {
                'path': 'data/portfolio_history_paper.db',
                'backup_path': 'src/data/portfolio_history_paper.db',
                'tables': ['portfolio_snapshots'],
                'test_query': 'SELECT COUNT(*) FROM portfolio_snapshots LIMIT 1'
            },
            'paper_trading': {
                'path': 'data/paper_trading.db',
                'backup_path': 'src/data/paper_trading.db',
                'tables': ['trades', 'positions', 'balance_history'],
                'test_query': 'SELECT COUNT(*) FROM trades LIMIT 1'
            },
            'token_cache': {
                'path': 'src/data/token_cache.db',
                'backup_path': 'src/data/token_cache.db',
                'tables': ['price_cache', 'metadata_cache'],
                'test_query': 'SELECT COUNT(*) FROM price_cache LIMIT 1'
            },
            'execution_tracker': {
                'path': 'src/data/execution_tracker.db',
                'backup_path': 'src/data/execution_tracker.db',
                'tables': ['execution_log', 'trade_events'],
                'test_query': 'SELECT COUNT(*) FROM execution_log LIMIT 1'
            },
            'live_trades': {
                'path': 'src/data/live_trades.db',
                'backup_path': 'src/data/live_trades.db',
                'tables': ['trades', 'signatures'],
                'test_query': 'SELECT COUNT(*) FROM trades LIMIT 1'
            },
            'entry_prices': {
                'path': 'src/data/entry_prices.db',
                'backup_path': 'src/data/entry_prices.db',
                'tables': ['entry_prices'],
                'test_query': 'SELECT COUNT(*) FROM entry_prices LIMIT 1'
            },
            'tracked_wallet_balances': {
                'path': 'src/data/tracked_wallet_balances.db',
                'backup_path': 'src/data/tracked_wallet_balances.db',
                'tables': ['wallet_balances', 'balance_history'],
                'test_query': 'SELECT COUNT(*) FROM wallet_balances LIMIT 1'
            }
        }
        
        self.health_history = {}
    
    def check_database_health(self, db_name: str) -> DatabaseHealthStatus:
        """Check health of specific database"""
        if db_name not in self.databases:
            return DatabaseHealthStatus(
                name=db_name,
                status='unknown',
                file_path='',
                file_size_mb=0.0,
                last_modified=datetime.now(),
                connection_time_ms=0,
                query_time_ms=0,
                table_count=0,
                record_count=0,
                integrity_check=False,
                performance_metrics={}
            )
        
        db_config = self.databases[db_name]
        file_path = self._find_database_file(db_config)
        
        if not file_path or not os.path.exists(file_path):
            return DatabaseHealthStatus(
                name=db_name,
                status='unhealthy',
                file_path=file_path or 'not_found',
                file_size_mb=0.0,
                last_modified=datetime.now(),
                connection_time_ms=0,
                query_time_ms=0,
                table_count=0,
                record_count=0,
                integrity_check=False,
                performance_metrics={'error': 'Database file not found'}
            )
        
        # Get file info
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        # Test connection and query performance
        connection_start = time.time()
        query_start = time.time()
        
        try:
            # Connect to database
            conn = sqlite3.connect(file_path, timeout=5)
            connection_time_ms = (time.time() - connection_start) * 1000
            
            cursor = conn.cursor()
            
            # Test query performance
            cursor.execute(db_config['test_query'])
            query_time_ms = (time.time() - query_start) * 1000
            
            # Get table count
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            table_count = len(tables)
            
            # Get record count
            cursor.execute(db_config['test_query'])
            record_count = cursor.fetchone()[0]
            
            # Check integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            integrity_check = integrity_result == 'ok'
            
            # Get performance metrics
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA freelist_count")
            freelist_count = cursor.fetchone()[0]
            
            # Calculate fragmentation
            total_pages = page_count
            free_pages = freelist_count
            fragmentation = (free_pages / total_pages * 100) if total_pages > 0 else 0
            
            conn.close()
            
            # Determine status
            if integrity_check and query_time_ms < 1000 and fragmentation < 50:
                status = 'healthy'
            elif integrity_check and query_time_ms < 5000 and fragmentation < 80:
                status = 'degraded'
            else:
                status = 'unhealthy'
            
            performance_metrics = {
                'page_count': page_count,
                'page_size': page_size,
                'freelist_count': freelist_count,
                'fragmentation_percentage': fragmentation,
                'integrity_result': integrity_result,
                'tables': [table[0] for table in tables]
            }
            
            return DatabaseHealthStatus(
                name=db_name,
                status=status,
                file_path=file_path,
                file_size_mb=file_size_mb,
                last_modified=last_modified,
                connection_time_ms=connection_time_ms,
                query_time_ms=query_time_ms,
                table_count=table_count,
                record_count=record_count,
                integrity_check=integrity_check,
                performance_metrics=performance_metrics
            )
            
        except sqlite3.DatabaseError as e:
            return DatabaseHealthStatus(
                name=db_name,
                status='unhealthy',
                file_path=file_path,
                file_size_mb=file_size_mb,
                last_modified=last_modified,
                connection_time_ms=(time.time() - connection_start) * 1000,
                query_time_ms=0,
                table_count=0,
                record_count=0,
                integrity_check=False,
                performance_metrics={'error': f'Database error: {str(e)}'}
            )
            
        except Exception as e:
            return DatabaseHealthStatus(
                name=db_name,
                status='unhealthy',
                file_path=file_path,
                file_size_mb=file_size_mb,
                last_modified=last_modified,
                connection_time_ms=(time.time() - connection_start) * 1000,
                query_time_ms=0,
                table_count=0,
                record_count=0,
                integrity_check=False,
                performance_metrics={'error': f'Unexpected error: {str(e)}'}
            )
    
    def _find_database_file(self, db_config: Dict[str, Any]) -> Optional[str]:
        """Find database file in primary or backup location"""
        # Try primary path first
        if os.path.exists(db_config['path']):
            return db_config['path']
        
        # Try backup path
        if os.path.exists(db_config['backup_path']):
            return db_config['backup_path']
        
        return None
    
    def check_all_databases(self) -> Dict[str, DatabaseHealthStatus]:
        """Check health of all databases"""
        statuses = {}
        for db_name in self.databases.keys():
            statuses[db_name] = self.check_database_health(db_name)
        return statuses
    
    def get_database_health_summary(self) -> Dict[str, Any]:
        """Get overall database health summary"""
        statuses = self.check_all_databases()
        
        total_dbs = len(statuses)
        healthy_dbs = sum(1 for status in statuses.values() if status.status == 'healthy')
        degraded_dbs = sum(1 for status in statuses.values() if status.status == 'degraded')
        unhealthy_dbs = sum(1 for status in statuses.values() if status.status == 'unhealthy')
        
        # Calculate total size
        total_size_mb = sum(status.file_size_mb for status in statuses.values())
        
        # Calculate average performance
        query_times = [status.query_time_ms for status in statuses.values() if status.query_time_ms > 0]
        avg_query_time = sum(query_times) / len(query_times) if query_times else 0
        
        connection_times = [status.connection_time_ms for status in statuses.values() if status.connection_time_ms > 0]
        avg_connection_time = sum(connection_times) / len(connection_times) if connection_times else 0
        
        # Count integrity issues
        integrity_issues = sum(1 for status in statuses.values() if not status.integrity_check)
        
        # Find largest database
        largest_db = None
        if statuses:
            largest_status = max(statuses.values(), key=lambda s: s.file_size_mb)
            largest_db = {
                'name': largest_status.name,
                'size_mb': largest_status.file_size_mb
            }
        
        # Find slowest database
        slowest_db = None
        if query_times:
            slowest_status = max(statuses.values(), key=lambda s: s.query_time_ms)
            slowest_db = {
                'name': slowest_status.name,
                'query_time_ms': slowest_status.query_time_ms
            }
        
        return {
            'total_databases': total_dbs,
            'healthy_databases': healthy_dbs,
            'degraded_databases': degraded_dbs,
            'unhealthy_databases': unhealthy_dbs,
            'total_size_mb': total_size_mb,
            'avg_query_time_ms': avg_query_time,
            'avg_connection_time_ms': avg_connection_time,
            'integrity_issues': integrity_issues,
            'largest_database': largest_db,
            'slowest_database': slowest_db,
            'health_percentage': (healthy_dbs / total_dbs * 100) if total_dbs > 0 else 0
        }
    
    def get_database_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics for all databases"""
        statuses = self.check_all_databases()
        metrics = {}
        
        for db_name, status in statuses.items():
            metrics[db_name] = {
                'file_size_mb': status.file_size_mb,
                'connection_time_ms': status.connection_time_ms,
                'query_time_ms': status.query_time_ms,
                'table_count': status.table_count,
                'record_count': status.record_count,
                'integrity_check': status.integrity_check,
                'fragmentation_percentage': status.performance_metrics.get('fragmentation_percentage', 0),
                'page_count': status.performance_metrics.get('page_count', 0),
                'last_modified': status.last_modified.isoformat() if status.last_modified else None
            }
        
        return metrics
    
    def get_database_recommendations(self) -> List[str]:
        """Get recommendations for database optimization"""
        statuses = self.check_all_databases()
        recommendations = []
        
        for db_name, status in statuses.items():
            # Check for large databases
            if status.file_size_mb > 100:
                recommendations.append(f"Consider archiving old data from {db_name} (size: {status.file_size_mb:.1f}MB)")
            
            # Check for slow queries
            if status.query_time_ms > 1000:
                recommendations.append(f"Optimize queries in {db_name} (query time: {status.query_time_ms:.1f}ms)")
            
            # Check for high fragmentation
            fragmentation = status.performance_metrics.get('fragmentation_percentage', 0)
            if fragmentation > 50:
                recommendations.append(f"Run VACUUM on {db_name} (fragmentation: {fragmentation:.1f}%)")
            
            # Check for integrity issues
            if not status.integrity_check:
                recommendations.append(f"Fix integrity issues in {db_name}")
        
        return recommendations
    
    def optimize_database(self, db_name: str) -> bool:
        """Optimize specific database"""
        if db_name not in self.databases:
            return False
        
        db_config = self.databases[db_name]
        file_path = self._find_database_file(db_config)
        
        if not file_path or not os.path.exists(file_path):
            return False
        
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Run VACUUM to defragment
            cursor.execute("VACUUM")
            
            # Run ANALYZE to update statistics
            cursor.execute("ANALYZE")
            
            conn.close()
            return True
            
        except Exception:
            return False

# Global instance
db_checker = DatabaseHealthChecker()

def get_db_checker() -> DatabaseHealthChecker:
    """Get global database checker instance"""
    return db_checker

if __name__ == "__main__":
    # Test the database checker
    checker = DatabaseHealthChecker()
    
    print("🗄️ Database Health Checker Test")
    print("=" * 50)
    
    # Check individual databases
    for db_name in ['portfolio_history', 'paper_trading', 'token_cache']:
        print(f"\nChecking {db_name}...")
        status = checker.check_database_health(db_name)
        print(f"  Status: {status.status}")
        print(f"  File size: {status.file_size_mb:.2f}MB")
        print(f"  Query time: {status.query_time_ms:.2f}ms")
        print(f"  Integrity: {status.integrity_check}")
        print(f"  Tables: {status.table_count}")
        print(f"  Records: {status.record_count}")
    
    # Get summary
    summary = checker.get_database_health_summary()
    print(f"\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Get recommendations
    recommendations = checker.get_database_recommendations()
    if recommendations:
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
