"""
🌙 Anarcho Capital's Database Manager
Handles automatic database cleanup when switching between paper trading modes
Built with love by Anarcho Capital 🚀
"""

import os
import sqlite3
import threading
import time
from typing import Optional, List
from pathlib import Path
from src.scripts.shared_services.logger import debug, info, warning, error, critical
from src import config

class DatabaseManager:
    """
    Manages database cleanup and state transitions between paper trading modes
    Automatically deletes cached data when switching modes to prevent data corruption
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
        """Initialize the database manager"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Database paths
        self.data_dir = os.path.join('src', 'data')
        self.portfolio_db_path = os.path.join(self.data_dir, 'portfolio_history.db')
        self.paper_trading_db_path = os.path.join(self.data_dir, 'paper_trading.db')
        
        # State tracking
        self.last_paper_trading_state = config.PAPER_TRADING_ENABLED
        self.cleanup_lock = threading.Lock()
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        info("Database Manager initialized")
    
    def check_and_cleanup_on_mode_change(self) -> bool:
        """
        Check if paper trading mode has changed and cleanup databases if needed
        Returns True if cleanup was performed, False otherwise
        """
        current_state = config.PAPER_TRADING_ENABLED
        
        with self.cleanup_lock:
            if current_state != self.last_paper_trading_state:
                info(f"Paper trading mode changed from {self.last_paper_trading_state} to {current_state}")
                info("Performing database cleanup to prevent data corruption...")
                
                # Perform cleanup
                cleanup_success = self._perform_cleanup(current_state)
                
                if cleanup_success:
                    info("Database cleanup completed successfully")
                    self.last_paper_trading_state = current_state
                    return True
                else:
                    error("Database cleanup failed - manual intervention may be required")
                    return False
        
        return False
    
    def _perform_cleanup(self, new_mode: bool) -> bool:
        """
        Perform database cleanup based on the new mode
        Args:
            new_mode: True for paper trading, False for live trading
        Returns:
            True if cleanup was successful
        """
        try:
            cleanup_actions = []
            
            if new_mode:
                # Switching to paper trading - clean live trading data
                cleanup_actions.extend([
                    ("portfolio_history.db", "Live trading portfolio history"),
                    ("wallets.json", "Live wallet cache"),
                    ("current_allocation.csv", "Live allocation data"),
                    ("portfolio_balance.csv", "Live balance data")
                ])
            else:
                # Switching to live trading - clean paper trading data
                cleanup_actions.extend([
                    ("paper_trading.db", "Paper trading database"),
                    ("portfolio_history.db", "Paper trading portfolio history")
                ])
            
            # Perform cleanup
            for filename, description in cleanup_actions:
                file_path = os.path.join(self.data_dir, filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        info(f"Deleted {description}: {filename}")
                        cleanup_actions.append((filename, True, None))
                    except Exception as e:
                        error(f"Failed to delete {description} ({filename}): {str(e)}")
                        cleanup_actions.append((filename, False, str(e)))
                else:
                    debug(f"{description} not found: {filename}")
                    cleanup_actions.append((filename, True, "File not found"))
            
            # Check if any cleanup actions failed
            failed_actions = [action for action in cleanup_actions if not action[1]]
            
            if failed_actions:
                error(f"Some cleanup actions failed: {len(failed_actions)} failures")
                for filename, success, error_msg in failed_actions:
                    error(f"  - {filename}: {error_msg}")
                return False
            
            # Clear any in-memory caches that might be affected
            self._clear_memory_caches()
            
            return True
            
        except Exception as e:
            error(f"Error during database cleanup: {str(e)}")
            return False
    
    def _clear_memory_caches(self):
        """Clear in-memory caches that might contain stale data"""
        try:
            # Import and clear shared services caches
            try:
                from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
                coordinator = get_shared_data_coordinator()
                if hasattr(coordinator, 'clear_cache'):
                    coordinator.clear_cache()
                    debug("Cleared shared data coordinator cache")
            except Exception as e:
                debug(f"Could not clear data coordinator cache: {str(e)}")
            
            try:
                from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
                price_service = get_optimized_price_service()
                if hasattr(price_service, 'clear_cache'):
                    price_service.clear_cache()
                    debug("Cleared price service cache")
            except Exception as e:
                debug(f"Could not clear price service cache: {str(e)}")
            
            try:
                from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
                api_manager = get_shared_api_manager()
                if hasattr(api_manager, 'clear_cache'):
                    api_manager.clear_cache()
                    debug("Cleared API manager cache")
            except Exception as e:
                debug(f"Could not clear API manager cache: {str(e)}")
                
        except Exception as e:
            warning(f"Error clearing memory caches: {str(e)}")
    
    def force_cleanup_all_databases(self) -> bool:
        """
        Force cleanup of all trading databases (use with caution)
        Returns True if successful
        """
        try:
            info("Performing forced cleanup of all trading databases...")
            
            databases_to_clean = [
                ("portfolio_history.db", "Portfolio history"),
                ("paper_trading.db", "Paper trading database"),
                ("wallets.json", "Wallet cache"),
                ("current_allocation.csv", "Allocation data"),
                ("portfolio_balance.csv", "Balance data")
            ]
            
            cleaned_count = 0
            for filename, description in databases_to_clean:
                file_path = os.path.join(self.data_dir, filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        info(f"Deleted {description}: {filename}")
                        cleaned_count += 1
                    except Exception as e:
                        error(f"Failed to delete {description} ({filename}): {str(e)}")
            
            # Clear memory caches
            self._clear_memory_caches()
            
            info(f"Force cleanup completed: {cleaned_count} databases deleted")
            return True
            
        except Exception as e:
            error(f"Error during force cleanup: {str(e)}")
            return False
    
    def get_database_status(self) -> dict:
        """Get status of all trading databases"""
        try:
            status = {
                'data_directory': self.data_dir,
                'databases': {},
                'total_size_mb': 0.0
            }
            
            databases = [
                ("portfolio_history.db", "Portfolio History"),
                ("paper_trading.db", "Paper Trading"),
                ("wallets.json", "Wallet Cache"),
                ("current_allocation.csv", "Allocation Data"),
                ("portfolio_balance.csv", "Balance Data")
            ]
            
            for filename, description in databases:
                file_path = os.path.join(self.data_dir, filename)
                file_status = {
                    'exists': os.path.exists(file_path),
                    'description': description
                }
                
                if file_status['exists']:
                    try:
                        file_size = os.path.getsize(file_path)
                        file_status['size_bytes'] = file_size
                        file_status['size_mb'] = round(file_size / (1024 * 1024), 2)
                        status['total_size_mb'] += file_status['size_mb']
                        
                        # Check if it's a SQLite database
                        if filename.endswith('.db'):
                            try:
                                with sqlite3.connect(file_path) as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                                    tables = cursor.fetchall()
                                    file_status['tables'] = [table[0] for table in tables]
                            except Exception as e:
                                file_status['tables'] = []
                                file_status['db_error'] = str(e)
                    except Exception as e:
                        file_status['error'] = str(e)
                
                status['databases'][filename] = file_status
            
            return status
            
        except Exception as e:
            error(f"Error getting database status: {str(e)}")
            return {'error': str(e)}
    
    def backup_databases(self, backup_dir: str = None) -> bool:
        """
        Create backup of all trading databases
        Args:
            backup_dir: Directory to store backups (defaults to data/backups)
        Returns:
            True if backup was successful
        """
        try:
            if backup_dir is None:
                backup_dir = os.path.join(self.data_dir, 'backups')
            
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = int(time.time())
            backup_success = True
            
            databases_to_backup = [
                "portfolio_history.db",
                "paper_trading.db",
                "wallets.json",
                "current_allocation.csv",
                "portfolio_balance.csv"
            ]
            
            for filename in databases_to_backup:
                source_path = os.path.join(self.data_dir, filename)
                if os.path.exists(source_path):
                    backup_filename = f"{filename}.backup_{timestamp}"
                    backup_path = os.path.join(backup_dir, backup_filename)
                    
                    try:
                        import shutil
                        shutil.copy2(source_path, backup_path)
                        info(f"Backed up {filename} to {backup_filename}")
                    except Exception as e:
                        error(f"Failed to backup {filename}: {str(e)}")
                        backup_success = False
            
            if backup_success:
                info(f"Database backup completed successfully to {backup_dir}")
            else:
                warning("Database backup completed with some failures")
            
            return backup_success
            
        except Exception as e:
            error(f"Error during database backup: {str(e)}")
            return False

# Global instance
_database_manager = None

def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager

def check_paper_trading_mode_change():
    """Check for paper trading mode changes and cleanup if needed"""
    manager = get_database_manager()
    return manager.check_and_cleanup_on_mode_change()

def force_cleanup_databases():
    """Force cleanup all trading databases"""
    manager = get_database_manager()
    return manager.force_cleanup_all_databases()

def get_database_status():
    """Get status of all trading databases"""
    manager = get_database_manager()
    return manager.get_database_status()

def backup_databases(backup_dir: str = None):
    """Create backup of all trading databases"""
    manager = get_database_manager()
    return manager.backup_databases(backup_dir) 
