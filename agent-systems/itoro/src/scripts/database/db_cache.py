"""
Database Cache Manager for Anarcho Capital's Trading Desktop App
Provides efficient SQLite-based caching for token prices and metadata
"""

import os
import time
import sqlite3
import threading
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import logging

from src.scripts.webhooks.webhook_config import CACHE_DB_PATH

# Set up logging
# logging.basicConfig(level=logging.INFO)  # Removed - main logger configured in src/scripts/shared_services/logger.py
logger = logging.getLogger(__name__)

# Import logger functions
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
except ImportError:
    # Define fallback logging functions if logger module is not available
    def debug(msg, file_only=False):
        if not file_only:
            print(f"DEBUG: {msg}")
            
    def info(msg):
        print(f"INFO: {msg}")
        
    def warning(msg):
        print(f"WARNING: {msg}")
        
    def error(msg):
        print(f"ERROR: {msg}")

class DatabaseCache:
    """SQLite-based cache for token prices and metadata"""
    
    def __init__(self, db_path: str = CACHE_DB_PATH):
        """Initialize the database cache"""
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Initialize database
        self._initialize_db()
        
        info(f"Database Cache initialized: {db_path}")
    
    def _initialize_db(self):
        """Initialize the database schema"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create token_prices table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_prices (
                token_mint TEXT PRIMARY KEY,
                price REAL,
                update_time INTEGER,
                expiry_time INTEGER
            )
            ''')
            
            # Create token_metadata table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_metadata (
                token_mint TEXT PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                decimals INTEGER,
                logo TEXT,
                extra_data TEXT,
                update_time INTEGER,
                expiry_time INTEGER
            )
            ''')
            
            # Create wallet_tokens table for tracking token changes
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_tokens (
                wallet_address TEXT,
                token_mint TEXT,
                amount REAL,
                decimals INTEGER,
                raw_amount TEXT,
                last_updated INTEGER,
                PRIMARY KEY (wallet_address, token_mint)
            )
            ''')
            
            # Create token_changes table for tracking recent changes
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT,
                token_mint TEXT,
                previous_amount REAL,
                new_amount REAL,
                amount_change REAL,
                pct_change REAL,
                decimals INTEGER,
                change_time INTEGER,
                event_type TEXT,
                processed INTEGER DEFAULT 0
            )
            ''')
            
            # Create indices for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_prices_expiry ON token_prices (expiry_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_expiry ON token_metadata (expiry_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_wallet_tokens ON wallet_tokens (wallet_address)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_token_changes_processed ON token_changes (processed)')
            
            conn.commit()
            conn.close()
    
    def get_price(self, token_mint: str) -> Optional[float]:
        """Get price from cache if valid"""
        current_time = int(time.time())
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT price, expiry_time FROM token_prices WHERE token_mint = ? AND expiry_time > ?',
                (token_mint, current_time)
            )
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                price, expiry = result
                debug(f"DB Cache hit for {token_mint[:8]}... price: ${price}", file_only=True)
                return price
            
            return None
    
    def store_price(self, token_mint: str, price: Optional[float], expiry_time: int) -> None:
        """Store price in cache with expiry time"""
        current_time = int(time.time())
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                '''
                INSERT OR REPLACE INTO token_prices 
                (token_mint, price, update_time, expiry_time) 
                VALUES (?, ?, ?, ?)
                ''',
                (token_mint, price, current_time, expiry_time)
            )
            
            conn.commit()
            conn.close()
    
    def store_prices(self, prices_dict: Dict[str, Optional[float]], expiry_times: Dict[str, int]) -> None:
        """Store multiple prices in cache efficiently"""
        if not prices_dict:
            return
            
        current_time = int(time.time())
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for token_mint, price in prices_dict.items():
                expiry_time = expiry_times.get(token_mint, current_time + 3600)  # Default 1 hour
                
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO token_prices 
                    (token_mint, price, update_time, expiry_time) 
                    VALUES (?, ?, ?, ?)
                    ''',
                    (token_mint, price, current_time, expiry_time)
                )
            
            conn.commit()
            conn.close()
    
    def get_metadata(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Get metadata from cache if valid"""
        current_time = int(time.time())
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                '''
                SELECT symbol, name, decimals, logo, extra_data, expiry_time 
                FROM token_metadata 
                WHERE token_mint = ? AND expiry_time > ?
                ''',
                (token_mint, current_time)
            )
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                symbol, name, decimals, logo, extra_data_json, expiry = result
                metadata = {
                    "symbol": symbol,
                    "name": name,
                    "decimals": decimals,
                    "logo": logo
                }
                
                # Add any extra data if available
                if extra_data_json:
                    try:
                        extra_data = json.loads(extra_data_json)
                        metadata.update(extra_data)
                    except:
                        pass
                        
                debug(f"DB Cache hit for {token_mint[:8]}... metadata: {symbol}/{name}", file_only=True)
                return metadata
            
            return None
    
    def store_metadata(self, token_mint: str, metadata: Optional[Dict[str, Any]], expiry_time: int) -> None:
        """Store metadata in cache with expiry time"""
        if not metadata:
            return
            
        current_time = int(time.time())
        
        # Extract basic fields
        symbol = metadata.get("symbol", "UNK")
        name = metadata.get("name", "Unknown Token")
        decimals = metadata.get("decimals", 9)
        logo = metadata.get("logo", "")
        
        # Put remaining fields in extra_data
        extra_data = {k: v for k, v in metadata.items() if k not in ["symbol", "name", "decimals", "logo"]}
        extra_data_json = json.dumps(extra_data) if extra_data else None
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                '''
                INSERT OR REPLACE INTO token_metadata 
                (token_mint, symbol, name, decimals, logo, extra_data, update_time, expiry_time) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (token_mint, symbol, name, decimals, logo, extra_data_json, current_time, expiry_time)
            )
            
            conn.commit()
            conn.close()
    
    def store_token_balance(self, wallet: str, token_mint: str, amount: float, 
                           decimals: int, raw_amount: Optional[str] = None) -> None:
        """Store token balance for a wallet"""
        current_time = int(time.time())
        
        # If raw_amount is not provided, calculate it
        if raw_amount is None:
            raw_amount = str(int(amount * (10 ** decimals)))
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # First, get the current balance to detect changes
            cursor.execute(
                'SELECT amount FROM wallet_tokens WHERE wallet_address = ? AND token_mint = ?',
                (wallet, token_mint)
            )
            result = cursor.fetchone()
            
            # Store the new balance
            cursor.execute(
                '''
                INSERT OR REPLACE INTO wallet_tokens
                (wallet_address, token_mint, amount, decimals, raw_amount, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (wallet, token_mint, amount, decimals, raw_amount, current_time)
            )
            
            # If this is an update (not a new token), record the change
            if result:
                previous_amount = result[0]
                if previous_amount != amount:
                    # Calculate change metrics
                    amount_change = amount - previous_amount
                    pct_change = (amount_change / previous_amount * 100) if previous_amount != 0 else 0
                    
                    # Record the change
                    cursor.execute(
                        '''
                        INSERT INTO token_changes
                        (wallet_address, token_mint, previous_amount, new_amount, amount_change, 
                         pct_change, decimals, change_time, event_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (wallet, token_mint, previous_amount, amount, amount_change, 
                         pct_change, decimals, current_time, 'change')
                    )
            else:
                # This is a new token
                cursor.execute(
                    '''
                    INSERT INTO token_changes
                    (wallet_address, token_mint, previous_amount, new_amount, amount_change, 
                     pct_change, decimals, change_time, event_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (wallet, token_mint, 0, amount, amount, 
                     100, decimals, current_time, 'add')
                )
            
            conn.commit()
            conn.close()
    
    def get_wallet_tokens(self, wallet: str) -> List[Dict[str, Any]]:
        """Get all tokens for a wallet"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable row factory for easy dict conversion
            cursor = conn.cursor()
            
            cursor.execute(
                '''
                SELECT wt.*, tp.price, tm.symbol, tm.name 
                FROM wallet_tokens wt
                LEFT JOIN token_prices tp ON wt.token_mint = tp.token_mint
                LEFT JOIN token_metadata tm ON wt.token_mint = tm.token_mint
                WHERE wt.wallet_address = ?
                ''',
                (wallet,)
            )
            
            results = cursor.fetchall()
            conn.close()
            
            # Convert rows to dictionaries
            tokens = []
            for row in results:
                token = dict(row)
                # Calculate USD value if price is available
                if token.get('price') is not None:
                    token['value_usd'] = token['amount'] * token['price']
                else:
                    token['value_usd'] = None
                tokens.append(token)
            
            return tokens
    
    def get_token_changes(self, processed_only: bool = False, 
                         limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent token changes"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query with optional filter for processed status
            if processed_only:
                where_clause = "WHERE processed = 1"
            else:
                where_clause = "WHERE processed = 0"
                
            cursor.execute(
                f'''
                SELECT tc.*, tm.symbol, tm.name, tp.price
                FROM token_changes tc
                LEFT JOIN token_metadata tm ON tc.token_mint = tm.token_mint
                LEFT JOIN token_prices tp ON tc.token_mint = tp.token_mint
                {where_clause}
                ORDER BY tc.change_time DESC
                LIMIT ?
                ''',
                (limit,)
            )
            
            results = cursor.fetchall()
            conn.close()
            
            # Convert to list of dicts
            changes = [dict(row) for row in results]
            
            # Add USD values where price is available
            for change in changes:
                if change.get('price') is not None:
                    change['previous_usd'] = change['previous_amount'] * change['price']
                    change['new_usd'] = change['new_amount'] * change['price']
                    change['usd_change'] = change['amount_change'] * change['price']
                else:
                    change['previous_usd'] = None
                    change['new_usd'] = None
                    change['usd_change'] = None
            
            return changes
    
    def mark_changes_processed(self, change_ids: List[int]) -> None:
        """Mark token changes as processed"""
        if not change_ids:
            return
            
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Use parameterized query with multiple placeholders
            placeholders = ','.join(['?'] * len(change_ids))
            cursor.execute(
                f'UPDATE token_changes SET processed = 1 WHERE id IN ({placeholders})',
                change_ids
            )
            
            conn.commit()
            conn.close()
    
    def clear_expired_cache(self, all_price=False, all_metadata=False) -> Tuple[int, int]:
        """Clear expired cache entries, returns (price_count, metadata_count)"""
        current_time = int(time.time())
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete expired price entries
            if all_price:
                cursor.execute('DELETE FROM token_prices')
                price_count = cursor.rowcount
            else:
                cursor.execute('DELETE FROM token_prices WHERE expiry_time < ?', (current_time,))
                price_count = cursor.rowcount
            
            # Delete expired metadata entries
            if all_metadata:
                cursor.execute('DELETE FROM token_metadata')
                metadata_count = cursor.rowcount
            else:
                cursor.execute('DELETE FROM token_metadata WHERE expiry_time < ?', (current_time,))
                metadata_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return price_count, metadata_count
    
    def vacuum_database(self) -> None:
        """Compact the database to reduce file size"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('VACUUM')
            conn.close()
            
            # Get current file size
            file_size_kb = os.path.getsize(self.db_path) / 1024
            info(f"Database compacted. Current size: {file_size_kb:.2f} KB")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get counts
            cursor.execute('SELECT COUNT(*) FROM token_prices')
            price_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM token_metadata')
            metadata_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM wallet_tokens')
            token_balance_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM token_changes')
            change_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM token_changes WHERE processed = 0')
            unprocessed_count = cursor.fetchone()[0]
            
            # Get current file size
            conn.close()
            file_size_kb = os.path.getsize(self.db_path) / 1024
            
            return {
                "price_entries": price_count,
                "metadata_entries": metadata_count,
                "token_balances": token_balance_count,
                "token_changes": change_count,
                "unprocessed_changes": unprocessed_count,
                "database_size_kb": file_size_kb
            }

# Simple usage example
if __name__ == "__main__":
    # Create database cache
    db_cache = DatabaseCache()
    
    # Store some example data
    db_cache.store_price("So11111111111111111111111111111111111111112", 142.75, int(time.time()) + 3600)
    
    # Store example metadata
    sol_metadata = {
        "symbol": "SOL",
        "name": "Solana",
        "decimals": 9,
        "logo": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"
    }
    db_cache.store_metadata("So11111111111111111111111111111111111111112", sol_metadata, int(time.time()) + 86400)
    
    # Test retrieving data
    price = db_cache.get_price("So11111111111111111111111111111111111111112")
    metadata = db_cache.get_metadata("So11111111111111111111111111111111111111112")
    
    print(f"SOL Price: ${price}")
    print(f"SOL Metadata: {metadata}")
    
    # Get cache stats
    stats = db_cache.get_cache_stats()
    print("\nCache Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}") 