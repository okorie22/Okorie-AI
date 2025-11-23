"""
🌙 Anarcho Capital's Database Reset Manager
Handles robust database reset with proper connection cleanup
Built with love by Anarcho Capital 🚀
"""

import os
import sqlite3
import threading
import time
import gc
import stat
from typing import List, Optional
from pathlib import Path
from datetime import datetime
from src.scripts.shared_services.logger import debug, info, warning, error, critical

class DatabaseResetManager:
    """
    Manages database reset operations with proper connection cleanup
    Handles WinError 32 file access conflicts on Windows systems
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the database reset manager"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.reset_lock = threading.Lock()
        
        # Database paths
        self.data_dir = os.path.join('src', 'data')
        self.paper_trading_db_path = os.path.join(self.data_dir, 'paper_trading.db')

        # NEW: in-process guard to avoid double reset
        self._reset_done = False

        # Track active connections
        self.active_connections: List[sqlite3.Connection] = []
        self.connection_lock = threading.Lock()
        
        info("Database Reset Manager initialized")

    # NEW
    def is_reset_done(self) -> bool:
        return self._reset_done
    
    def register_connection(self, conn: sqlite3.Connection):
        """Register a database connection for cleanup tracking"""
        with self.connection_lock:
            if conn not in self.active_connections:
                self.active_connections.append(conn)
                debug(f"Registered database connection: {id(conn)}")
    
    def unregister_connection(self, conn: sqlite3.Connection):
        """Unregister a database connection"""
        with self.connection_lock:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
                debug(f"Unregistered database connection: {id(conn)}")
    
    def _close_all_connections(self) -> bool:
        """Close all registered database connections"""
        closed_count = 0
        with self.connection_lock:
            connections_to_close = self.active_connections.copy()
            self.active_connections.clear()
        
        for conn in connections_to_close:
            try:
                if conn:
                    conn.close()
                    closed_count += 1
                    debug(f"Closed database connection: {id(conn)}")
            except Exception as e:
                warning(f"Error closing database connection {id(conn)}: {e}")
        
        info(f"Closed {closed_count} database connections")
        return closed_count > 0
    
    def _force_close_sqlite_connections(self) -> bool:
        """Force close any remaining SQLite connections using various methods"""
        try:
            # Method 1: Force garbage collection
            gc.collect()
            time.sleep(0.1)
            
            # Method 2: Try to connect and immediately close to release any locks
            try:
                test_conn = sqlite3.connect(self.paper_trading_db_path, timeout=1.0)
                test_conn.close()
                debug("Test connection successful - database should be accessible")
            except sqlite3.OperationalError as e:
                warning(f"Database still locked after cleanup: {e}")
                return False
            
            # Method 3: Check for WAL files and handle them
            wal_path = self.paper_trading_db_path + '-wal'
            shm_path = self.paper_trading_db_path + '-shm'
            
            for wal_file in [wal_path, shm_path]:
                if os.path.exists(wal_file):
                    try:
                        os.remove(wal_file)
                        debug(f"Removed WAL file: {wal_file}")
                    except Exception as e:
                        warning(f"Could not remove WAL file {wal_file}: {e}")
            
            return True
            
        except Exception as e:
            error(f"Error in force close SQLite connections: {e}")
            return False
    
    def _safe_file_removal(self, file_path: str, max_retries: int = 5) -> bool:
        """Safely remove a file with retry logic and proper error handling"""
        if not os.path.exists(file_path):
            return True
        
        for attempt in range(max_retries):
            try:
                # Method 1: Direct removal
                os.remove(file_path)
                info(f"Successfully removed database file: {file_path}")
                return True
                
            except PermissionError as e:
                if attempt < max_retries - 1:
                    warning(f"Permission denied (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(1 * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    # Method 2: Try rename and delete
                    try:
                        temp_path = file_path + f'.deleted_{int(time.time())}'
                        os.rename(file_path, temp_path)
                        os.remove(temp_path)
                        info(f"Successfully removed database file via rename: {file_path}")
                        return True
                    except Exception as rename_error:
                        error(f"Failed to remove database file after {max_retries} attempts: {e}, rename error: {rename_error}")
                        return False
                        
            except OSError as e:
                if e.errno == 32:  # WinError 32: The process cannot access the file
                    if attempt < max_retries - 1:
                        warning(f"File in use (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(2 * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        error(f"File still in use after {max_retries} attempts: {e}")
                        return False
                else:
                    error(f"OS error removing file: {e}")
                    return False
                    
            except Exception as e:
                error(f"Unexpected error removing file: {e}")
                return False
        
        return False
    
    def reset_paper_trading_database(self) -> bool:
        """
        Reset the paper trading database by clearing all tables
        Simple, fast, and reliable - no file deletion needed
        """
        with self.reset_lock:
            info("🔄 Starting paper trading database reset...")
            
            try:
                # Step 1: Close all registered connections
                info("Step 1: Closing registered database connections...")
                self._close_all_connections()
                
                # Step 2: Clear paper trading database tables
                info("Step 2: Clearing paper trading database tables...")
                try:
                    conn = sqlite3.connect(self.paper_trading_db_path, timeout=10, check_same_thread=False)
                    cursor = conn.cursor()
                    
                    # Clear all tables
                    tables_to_clear = [
                        'paper_portfolio',
                        'paper_trading_balances', 
                        'paper_trading_transactions',
                        'paper_staking_transactions'
                    ]
                    
                    for table in tables_to_clear:
                        try:
                            cursor.execute(f"DELETE FROM {table}")
                            debug(f"Cleared table: {table}")
                        except Exception as e:
                            debug(f"Could not clear table {table}: {e}")
                    
                    conn.commit()
                    conn.close()
                    info("✅ Cleared paper trading database tables")
                except Exception as e:
                    error(f"Failed to clear paper trading database: {e}")
                    return False
                
                # Step 3: Clear portfolio history database tables
                info("Step 3: Clearing portfolio history database tables...")
                try:
                    # Check both possible locations for portfolio history database
                    portfolio_db_paths = [
                        os.path.join('data', 'portfolio_history_paper.db'),  # data/ (primary)
                        os.path.join(self.data_dir, 'portfolio_history_paper.db'),  # src/data/ (fallback)
                    ]
                    
                    portfolio_db_path = None
                    for path in portfolio_db_paths:
                        if os.path.exists(path):
                            portfolio_db_path = path
                            info(f"Found portfolio history database at: {portfolio_db_path}")
                            break
                    
                    if portfolio_db_path:
                        conn = sqlite3.connect(portfolio_db_path, timeout=10, check_same_thread=False)
                        cursor = conn.cursor()
                        
                        tables_to_clear = [
                            'portfolio_snapshots',
                            'pnl_tracking',
                            'gain_tracking', 
                            'harvesting_history',
                            'staked_sol_tracking',
                            'capital_flows',
                            'peak_balance_tracking',
                            'trading_statistics',
                            'closed_trades'
                        ]
                        
                        for table in tables_to_clear:
                            try:
                                cursor.execute(f"DELETE FROM {table}")
                                debug(f"Cleared table: {table}")
                            except Exception as e:
                                debug(f"Could not clear table {table}: {e}")
                        
                        conn.commit()
                        conn.close()
                        info("✅ Cleared portfolio history database tables")
                    else:
                        warning("Portfolio history database not found in any location")
                except Exception as e:
                    warning(f"Could not clear portfolio history database: {e}")
                
                # Step 4: Clear cloud database
                info("Step 4: Clearing cloud database...")
                try:
                    from src.scripts.database.cloud_database import get_cloud_database_manager
                    db_manager = get_cloud_database_manager()
                    if db_manager:
                        success = db_manager.clear_paper_trading_data()
                        if success:
                            info("✅ Cleared cloud database")
                        else:
                            warning("⚠️ Cloud database clearing had issues")
                    else:
                        warning("⚠️ Cloud database not available - skipping cloud cleanup")
                except Exception as e:
                    warning(f"Could not clear cloud database: {e}")
                
                # Step 5: Reinitialize with fresh data
                info("Step 5: Reinitializing with fresh data...")
                try:
                    from src.paper_trading import init_paper_trading_db, _set_initial_balances
                    init_paper_trading_db()
                    _set_initial_balances()
                    self._reset_done = True
                    info("✅ Paper trading database reset completed successfully")
                    return True
                except Exception as e:
                    error(f"Failed to reinitialize database: {e}")
                    return False
                    
            except Exception as e:
                error(f"Error during database reset: {e}")
                return False
    
    def is_database_accessible(self) -> bool:
        """Check if the database is accessible for operations"""
        try:
            with sqlite3.connect(self.paper_trading_db_path, timeout=1.0) as conn:
                conn.execute("SELECT 1")
                return True
        except Exception:
            return False
    
    def get_database_info(self) -> dict:
        """Get information about the database file"""
        info_dict = {
            'exists': os.path.exists(self.paper_trading_db_path),
            'accessible': self.is_database_accessible(),
            'size': 0,
            'modified': None,
            'wal_files': []
        }
        
        if info_dict['exists']:
            try:
                stat_info = os.stat(self.paper_trading_db_path)
                info_dict['size'] = stat_info.st_size
                info_dict['modified'] = stat_info.st_mtime
            except Exception:
                pass
            
            # Check for WAL files
            wal_path = self.paper_trading_db_path + '-wal'
            shm_path = self.paper_trading_db_path + '-shm'
            
            for wal_file in [wal_path, shm_path]:
                if os.path.exists(wal_file):
                    info_dict['wal_files'].append(wal_file)
        
        return info_dict

# Global instance
_database_reset_manager = None

def get_database_reset_manager() -> DatabaseResetManager:
    """Get the global database reset manager instance"""
    global _database_reset_manager
    if _database_reset_manager is None:
        _database_reset_manager = DatabaseResetManager()
    return _database_reset_manager

def reset_paper_trading_database() -> bool:
    """Convenience function to reset the paper trading database"""
    manager = get_database_reset_manager()
    return manager.reset_paper_trading_database()
