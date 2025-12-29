"""
Pattern Storage - SQLite Database for Pattern History
Stores detected patterns with AI analysis for historical reference and UI display
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os
import numpy as np


class PatternStorage:
    """
    SQLite-based storage for detected patterns.
    Stores pattern data, AI analysis, and metadata for historical tracking.
    """
    
    def __init__(self, db_path: str = 'patterns.db'):
        """
        Initialize pattern storage with SQLite database.
        
        Args:
            db_path: Path to SQLite database file (default: 'patterns.db')
        """
        self.db_path = db_path
        self.init_db()
        print(f"[PATTERN STORAGE] Initialized with database: {db_path}")
    
    def init_db(self):
        """Create database tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    signal INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    direction TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    regime_confidence REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    ohlcv TEXT NOT NULL,
                    confirmations TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    ai_analysis TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, timestamp, pattern)
                )
            ''')

            # Alert tracking table to remember when patterns were last alerted
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alert_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    last_alert_timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(symbol, pattern_type)
                )
            ''')

            # Create indices for faster queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON patterns(symbol)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON patterns(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON patterns(created_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_pattern ON patterns(pattern)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_alert_symbol ON alert_tracking(symbol)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_alert_pattern ON alert_tracking(pattern_type)')

            conn.commit()
            print("[PATTERN STORAGE] Database schema initialized")
    
    def _convert_booleans_for_json(self, data):
        """
        Recursively convert boolean values to integers and handle other non-serializable types for JSON.
        """
        if isinstance(data, dict):
            return {key: self._convert_booleans_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._convert_booleans_for_json(item) for item in data]
        elif isinstance(data, (bool, np.bool_)):  # Handle both Python bool and numpy.bool_
            return 1 if data else 0
        elif hasattr(data, 'isoformat'):  # Handle Timestamp and datetime objects
            return data.isoformat()
        else:
            return data

    def save_pattern(self, symbol: str, pattern_data: Dict, ai_analysis: str) -> int:
        """
        Save detected pattern to database.

        Args:
            symbol: Trading symbol
            pattern_data: Pattern detection data
            ai_analysis: AI-generated analysis

        Returns:
            Pattern ID (database row ID)
        """
        try:
            # Convert all boolean values to integers for JSON serialization
            pattern_data_json = self._convert_booleans_for_json(pattern_data)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    INSERT OR REPLACE INTO patterns
                    (symbol, pattern, signal, confidence, direction, regime, regime_confidence,
                     timestamp, ohlcv, confirmations, parameters, ai_analysis, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    pattern_data_json['pattern'],
                    pattern_data_json['signal'],
                    pattern_data_json['confidence'],
                    pattern_data_json['direction'],
                    pattern_data_json['regime'],
                    pattern_data_json['regime_confidence'],
                    pattern_data_json['timestamp'].isoformat() if hasattr(pattern_data_json['timestamp'], 'isoformat') else str(pattern_data_json['timestamp']),
                    json.dumps(pattern_data_json['ohlcv']),
                    json.dumps(pattern_data_json['confirmations']),
                    json.dumps(pattern_data_json['parameters']),
                    ai_analysis,
                    datetime.now().isoformat()
                ))
                
                pattern_id = cursor.lastrowid
                conn.commit()
                
                print(f"[PATTERN STORAGE] Saved pattern ID {pattern_id}: {symbol} {pattern_data['pattern']}")
                return pattern_id
                
        except sqlite3.IntegrityError:
            print(f"[PATTERN STORAGE] Duplicate pattern skipped: {symbol} {pattern_data['pattern']} at {pattern_data['timestamp']}")
            return -1
        except Exception as e:
            print(f"[PATTERN STORAGE] Error saving pattern: {e}")
            return -1
    
    def get_recent_patterns(self, limit: int = 50) -> List[Dict]:
        """
        Retrieve recent patterns ordered by creation time.
        
        Args:
            limit: Maximum number of patterns to retrieve (default: 50)
            
        Returns:
            List of pattern dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM patterns
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
                
                patterns = []
                for row in cursor.fetchall():
                    patterns.append(self._row_to_dict(row))
                
                return patterns
                
        except Exception as e:
            print(f"[PATTERN STORAGE] Error retrieving recent patterns: {e}")
            return []
    
    def get_patterns_by_symbol(self, symbol: str, limit: int = 20) -> List[Dict]:
        """
        Retrieve patterns for a specific symbol.
        
        Args:
            symbol: Trading symbol
            limit: Maximum number of patterns to retrieve (default: 20)
            
        Returns:
            List of pattern dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM patterns
                    WHERE symbol = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (symbol, limit))
                
                patterns = []
                for row in cursor.fetchall():
                    patterns.append(self._row_to_dict(row))
                
                return patterns
                
        except Exception as e:
            print(f"[PATTERN STORAGE] Error retrieving patterns for {symbol}: {e}")
            return []
    
    def get_patterns_by_type(self, pattern_type: str, limit: int = 20) -> List[Dict]:
        """
        Retrieve patterns of a specific type.
        
        Args:
            pattern_type: Pattern name (e.g., 'hammer', 'doji', 'engulfing')
            limit: Maximum number of patterns to retrieve (default: 20)
            
        Returns:
            List of pattern dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM patterns
                    WHERE pattern = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (pattern_type, limit))
                
                patterns = []
                for row in cursor.fetchall():
                    patterns.append(self._row_to_dict(row))
                
                return patterns
                
        except Exception as e:
            print(f"[PATTERN STORAGE] Error retrieving {pattern_type} patterns: {e}")
            return []
    
    def get_pattern_statistics(self) -> Dict:
        """
        Get statistics about stored patterns.
        
        Returns:
            Dictionary with pattern statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total patterns
                total = conn.execute('SELECT COUNT(*) FROM patterns').fetchone()[0]
                
                # Patterns by type
                pattern_counts = {}
                cursor = conn.execute('''
                    SELECT pattern, COUNT(*) as count
                    FROM patterns
                    GROUP BY pattern
                    ORDER BY count DESC
                ''')
                for row in cursor.fetchall():
                    pattern_counts[row[0]] = row[1]
                
                # Patterns by symbol
                symbol_counts = {}
                cursor = conn.execute('''
                    SELECT symbol, COUNT(*) as count
                    FROM patterns
                    GROUP BY symbol
                    ORDER BY count DESC
                ''')
                for row in cursor.fetchall():
                    symbol_counts[row[0]] = row[1]
                
                # Direction distribution
                direction_counts = {}
                cursor = conn.execute('''
                    SELECT direction, COUNT(*) as count
                    FROM patterns
                    GROUP BY direction
                ''')
                for row in cursor.fetchall():
                    direction_counts[row[0]] = row[1]
                
                # Average confidence
                avg_confidence = conn.execute('SELECT AVG(confidence) FROM patterns').fetchone()[0] or 0
                
                return {
                    'total_patterns': total,
                    'pattern_counts': pattern_counts,
                    'symbol_counts': symbol_counts,
                    'direction_counts': direction_counts,
                    'average_confidence': avg_confidence
                }
                
        except Exception as e:
            print(f"[PATTERN STORAGE] Error getting statistics: {e}")
            return {}
    
    def delete_old_patterns(self, days: int = 30) -> int:
        """
        Delete patterns older than specified days.
        
        Args:
            days: Delete patterns older than this many days (default: 30)
            
        Returns:
            Number of patterns deleted
        """
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            cutoff_iso = datetime.fromtimestamp(cutoff_date).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    DELETE FROM patterns
                    WHERE created_at < ?
                ''', (cutoff_iso,))
                
                deleted = cursor.rowcount
                conn.commit()
                
                print(f"[PATTERN STORAGE] Deleted {deleted} patterns older than {days} days")
                return deleted
                
        except Exception as e:
            print(f"[PATTERN STORAGE] Error deleting old patterns: {e}")
            return 0
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """
        Convert database row to dictionary.
        
        Args:
            row: SQLite row object
            
        Returns:
            Dictionary representation of pattern
        """
        return {
            'id': row['id'],
            'symbol': row['symbol'],
            'pattern': row['pattern'],
            'signal': row['signal'],
            'confidence': row['confidence'],
            'direction': row['direction'],
            'regime': row['regime'],
            'regime_confidence': row['regime_confidence'],
            'timestamp': row['timestamp'],
            'ohlcv': json.loads(row['ohlcv']),
            'confirmations': json.loads(row['confirmations']),
            'parameters': json.loads(row['parameters']),
            'ai_analysis': row['ai_analysis'],
            'created_at': row['created_at']
        }
    
    def clear_all_patterns(self):
        """Clear all patterns from database (for testing)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM patterns')
                conn.commit()
                print("[PATTERN STORAGE] All patterns cleared")
        except Exception as e:
            print(f"[PATTERN STORAGE] Error clearing patterns: {e}")
    
    def export_to_csv(self, output_path: str):
        """
        Export patterns to CSV file.
        
        Args:
            output_path: Path to output CSV file
        """
        try:
            import csv
            
            patterns = self.get_recent_patterns(limit=10000)
            
            if not patterns:
                print("[PATTERN STORAGE] No patterns to export")
                return
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'id', 'symbol', 'pattern', 'signal', 'confidence', 'direction',
                    'regime', 'regime_confidence', 'timestamp', 'ai_analysis', 'created_at'
                ])
                writer.writeheader()
                
                for p in patterns:
                    writer.writerow({
                        'id': p['id'],
                        'symbol': p['symbol'],
                        'pattern': p['pattern'],
                        'signal': p['signal'],
                        'confidence': p['confidence'],
                        'direction': p['direction'],
                        'regime': p['regime'],
                        'regime_confidence': p['regime_confidence'],
                        'timestamp': p['timestamp'],
                        'ai_analysis': p['ai_analysis'],
                        'created_at': p['created_at']
                    })
            
            print(f"[PATTERN STORAGE] Exported {len(patterns)} patterns to {output_path}")
            
        except Exception as e:
            print(f"[PATTERN STORAGE] Error exporting to CSV: {e}")

    def save_alert_timestamp(self, symbol: str, pattern_type: str, timestamp: datetime) -> bool:
        """
        Save the timestamp of when a pattern alert was sent.

        Args:
            symbol: Trading symbol
            pattern_type: Pattern name (e.g., 'doji', 'hammer')
            timestamp: When the alert was sent

        Returns:
            Success status
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Use INSERT OR REPLACE to update existing entries
                conn.execute('''
                    INSERT OR REPLACE INTO alert_tracking
                    (symbol, pattern_type, last_alert_timestamp, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    pattern_type,
                    timestamp.isoformat(),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                return True
        except Exception as e:
            print(f"[PATTERN STORAGE] Error saving alert timestamp: {e}")
            return False

    def load_alert_tracking(self) -> Dict[str, Dict[str, datetime]]:
        """
        Load all alert tracking data from database.

        Returns:
            Dictionary mapping symbols to pattern_type -> last_alert_timestamp
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT symbol, pattern_type, last_alert_timestamp
                    FROM alert_tracking
                ''')

                alert_tracking = {}
                for row in cursor:
                    symbol, pattern_type, timestamp_str = row
                    if symbol not in alert_tracking:
                        alert_tracking[symbol] = {}

                    # Convert ISO string back to datetime
                    alert_tracking[symbol][pattern_type] = datetime.fromisoformat(timestamp_str)

                return alert_tracking

        except Exception as e:
            print(f"[PATTERN STORAGE] Error loading alert tracking: {e}")
            return {}


if __name__ == "__main__":
    print("="*80)
    print("PATTERN STORAGE - Manual Test")
    print("="*80)
    
    # Initialize storage
    storage = PatternStorage('test_patterns.db')
    
    # Create sample pattern
    sample_pattern = {
        'pattern': 'hammer',
        'signal': 100,
        'confidence': 0.85,
        'direction': 'long',
        'regime': 'strong_uptrend',
        'regime_confidence': 0.92,
        'timestamp': datetime.now(),
        'ohlcv': {
            'open': 87500.00,
            'high': 88000.00,
            'low': 87200.00,
            'close': 87800.00,
            'volume': 1500.50
        },
        'confirmations': {
            'trend': True,
            'momentum': True,
            'volume': True
        },
        'parameters': {
            'stop_loss_pct': 0.25,
            'profit_target_pct': 0.12,
            'trailing_activation_pct': 0.10,
            'trailing_offset_pct': 0.08,
            'min_profit_pct': 0.04,
            'max_holding_period': 48
        }
    }
    
    # Save pattern
    print("\n[TEST] Saving pattern...")
    pattern_id = storage.save_pattern('BTCUSDT', sample_pattern, "Strong hammer pattern with high confidence.")
    print(f"[RESULT] Pattern ID: {pattern_id}")
    
    # Retrieve patterns
    print("\n[TEST] Retrieving recent patterns...")
    patterns = storage.get_recent_patterns(5)
    print(f"[RESULT] Found {len(patterns)} patterns:")
    for p in patterns:
        print(f"  ID {p['id']}: {p['symbol']} {p['pattern']} ({p['confidence']:.1%})")
    
    # Get statistics
    print("\n[TEST] Getting statistics...")
    stats = storage.get_pattern_statistics()
    print(f"[RESULT] Statistics:")
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  Pattern counts: {stats['pattern_counts']}")
    
    print("\n[TEST] Pattern storage test complete!")

