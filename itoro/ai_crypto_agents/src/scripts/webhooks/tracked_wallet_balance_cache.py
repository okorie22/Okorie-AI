"""
Tracked Wallet Balance Cache
Stores and tracks token balances for tracked wallets to determine sell types
"""

import sqlite3
import os
import time
from typing import Dict, Tuple, Optional
from datetime import datetime
import threading

# Import configuration
try:
    from src.config import (
        HALF_SELL_THRESHOLD,
        HALF_SELL_UPPER_THRESHOLD,
        PARTIAL_SELL_MIN_THRESHOLD,
        FULL_SELL_THRESHOLD
    )
except ImportError:
    # Default configuration if not available
    HALF_SELL_THRESHOLD = 0.45  # 45-55% considered half sell
    HALF_SELL_UPPER_THRESHOLD = 0.55
    PARTIAL_SELL_MIN_THRESHOLD = 0.10  # Minimum 10% to be considered partial
    FULL_SELL_THRESHOLD = 0.95  # 95%+ considered full sell

# Import logging
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
except ImportError:
    # Fallback logging
    def debug(msg): print(f"DEBUG: {msg}")
    def info(msg): print(f"INFO: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")

class TrackedWalletBalanceCache:
    """
    SQLite-based cache to store tracked wallet token balances
    Tracks previous balance, current balance, and balance changes
    """
    
    def __init__(self, db_path: str = None):
        """Initialize the balance cache"""
        if db_path is None:
            # Default to data directory
            data_dir = os.path.join('src', 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'tracked_wallet_balances.db')
        
        self.db_path = db_path
        self.lock = threading.RLock()
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS wallet_balances (
                        wallet_address TEXT NOT NULL,
                        token_address TEXT NOT NULL,
                        balance REAL NOT NULL,
                        last_updated INTEGER NOT NULL,
                        PRIMARY KEY (wallet_address, token_address)
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS balance_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        wallet_address TEXT NOT NULL,
                        token_address TEXT NOT NULL,
                        previous_balance REAL,
                        current_balance REAL NOT NULL,
                        change_amount REAL NOT NULL,
                        change_percentage REAL,
                        sell_type TEXT,
                        timestamp INTEGER NOT NULL
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_wallet_token 
                    ON wallet_balances (wallet_address, token_address)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_history_wallet_token 
                    ON balance_history (wallet_address, token_address)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_history_timestamp 
                    ON balance_history (timestamp)
                """)
    
    def get_previous_balance(self, wallet: str, token: str) -> float:
        """
        Get the previous balance for a wallet/token pair
        
        Args:
            wallet: Wallet address
            token: Token address
            
        Returns:
            Previous balance or 0.0 if not found
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT balance FROM wallet_balances WHERE wallet_address = ? AND token_address = ?",
                    (wallet, token)
                )
                result = cursor.fetchone()
                return result[0] if result else 0.0
    
    def update_balance(self, wallet: str, token: str, new_balance: float) -> Dict:
        """
        Update the balance for a wallet/token pair and return change information
        
        Args:
            wallet: Wallet address
            token: Token address
            new_balance: New balance amount
            
        Returns:
            Dictionary with change information:
            {
                'previous_balance': float,
                'current_balance': float,
                'change_amount': float,
                'change_percentage': float,
                'sell_type': str,
                'sell_percentage': float
            }
        """
        with self.lock:
            previous_balance = self.get_previous_balance(wallet, token)
            change_amount = new_balance - previous_balance
            change_percentage = self.calculate_sell_percentage(previous_balance, new_balance)
            sell_type, sell_percentage = self.determine_sell_type(change_percentage)
            
            timestamp = int(time.time())
            
            # Update current balance
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO wallet_balances (wallet_address, token_address, balance, last_updated)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(wallet_address, token_address) DO UPDATE SET
                        balance = excluded.balance,
                        last_updated = excluded.last_updated
                """, (wallet, token, new_balance, timestamp))
                
                # Record in history
                conn.execute("""
                    INSERT INTO balance_history (
                        wallet_address, token_address, previous_balance, current_balance,
                        change_amount, change_percentage, sell_type, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (wallet, token, previous_balance, new_balance, change_amount, 
                      change_percentage, sell_type, timestamp))
            
            debug(f"Balance updated: {wallet[:8]}... {token[:8]}... {previous_balance:.6f} -> {new_balance:.6f} ({change_percentage:.1f}% change, {sell_type})")
            
            return {
                'previous_balance': previous_balance,
                'current_balance': new_balance,
                'change_amount': change_amount,
                'change_percentage': change_percentage,
                'sell_type': sell_type,
                'sell_percentage': sell_percentage
            }
    
    def calculate_sell_percentage(self, previous_balance: float, current_balance: float) -> float:
        """
        Calculate the percentage of tokens sold
        
        Args:
            previous_balance: Previous balance
            current_balance: Current balance
            
        Returns:
            Percentage sold (0-100)
        """
        if previous_balance == 0:
            return 0.0  # No previous balance, can't calculate percentage
        
        if current_balance == 0:
            return 100.0  # All tokens sold
        
        # Calculate percentage remaining, then convert to percentage sold
        percentage_remaining = (current_balance / previous_balance)
        percentage_sold = (1 - percentage_remaining) * 100
        
        return max(0.0, min(100.0, percentage_sold))  # Clamp between 0-100
    
    def determine_sell_type(self, percentage_sold: float) -> Tuple[str, float]:
        """
        Determine sell type based on percentage sold

        Args:
            percentage_sold: Percentage of tokens sold (0-100)

        Returns:
            Tuple of (sell_type, sell_percentage)
            sell_type: 'partial'
            sell_percentage: Actual percentage to sell
        """
        if percentage_sold > 0:  # TRUE proportional selling - mirror EXACT percentage
            return 'partial', percentage_sold
        else:
            return 'skip', 0.0  # Only skip if no change (0%)
    
    def get_balance_history(self, wallet: str, token: str, limit: int = 10) -> list:
        """
        Get balance history for a wallet/token pair
        
        Args:
            wallet: Wallet address
            token: Token address
            limit: Maximum number of records to return
            
        Returns:
            List of history records
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT previous_balance, current_balance, change_amount, 
                           change_percentage, sell_type, timestamp
                    FROM balance_history
                    WHERE wallet_address = ? AND token_address = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (wallet, token, limit))
                
                return cursor.fetchall()
    
    def cleanup_old_history(self, days: int = 30):
        """
        Clean up old history records to keep database size manageable
        
        Args:
            days: Number of days of history to keep
        """
        cutoff_timestamp = int(time.time()) - (days * 24 * 60 * 60)
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM balance_history WHERE timestamp < ?",
                    (cutoff_timestamp,)
                )
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    info(f"Cleaned up {deleted_count} old balance history records")
    
    def get_all_balances(self, wallet: str) -> Dict[str, float]:
        """
        Get all token balances for a wallet
        
        Args:
            wallet: Wallet address
            
        Returns:
            Dictionary mapping token addresses to balances
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT token_address, balance FROM wallet_balances WHERE wallet_address = ?",
                    (wallet,)
                )
                return dict(cursor.fetchall())
    
    def clear_wallet_balances(self, wallet: str):
        """
        Clear all balances for a specific wallet
        
        Args:
            wallet: Wallet address
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM wallet_balances WHERE wallet_address = ?",
                    (wallet,)
                )
                conn.execute(
                    "DELETE FROM balance_history WHERE wallet_address = ?",
                    (wallet,)
                )
                info(f"Cleared all balances for wallet {wallet[:8]}...")


# Singleton instance
_balance_cache_instance = None
_cache_lock = threading.Lock()

def get_balance_cache() -> TrackedWalletBalanceCache:
    """Get singleton instance of balance cache"""
    global _balance_cache_instance
    if _balance_cache_instance is None:
        with _cache_lock:
            if _balance_cache_instance is None:
                _balance_cache_instance = TrackedWalletBalanceCache()
    return _balance_cache_instance
