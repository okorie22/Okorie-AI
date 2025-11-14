"""
🌙 Anarcho Capital's Database Context Manager
Provides safe database connection handling with automatic cleanup
Built with love by Anarcho Capital 🚀
"""

import sqlite3
from contextlib import contextmanager
from typing import Optional
from src.scripts.shared_services.logger import debug, info, warning, error

@contextmanager
def safe_database_connection(db_path: str, timeout: float = 10.0, check_same_thread: bool = False):
    """
    Context manager for safe database connections with automatic cleanup
    
    Args:
        db_path: Path to the SQLite database file
        timeout: Connection timeout in seconds
        check_same_thread: Whether to check same thread usage
        
    Yields:
        sqlite3.Connection: Database connection
    """
    conn = None
    try:
        # Create connection
        conn = sqlite3.connect(db_path, timeout=timeout, check_same_thread=check_same_thread)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        
        # Register connection with reset manager if it's a paper trading database
        if 'paper_trading.db' in db_path:
            try:
                from src.scripts.database.database_reset_manager import get_database_reset_manager
                manager = get_database_reset_manager()
                manager.register_connection(conn)
                debug(f"Registered database connection: {id(conn)}")
            except ImportError:
                pass  # Reset manager not available
        
        yield conn
        
    except Exception as e:
        error(f"Database connection error: {e}")
        raise
    finally:
        # Cleanup connection
        if conn:
            try:
                # Unregister connection from reset manager
                if 'paper_trading.db' in db_path:
                    try:
                        from src.scripts.database.database_reset_manager import get_database_reset_manager
                        manager = get_database_reset_manager()
                        manager.unregister_connection(conn)
                        debug(f"Unregistered database connection: {id(conn)}")
                    except ImportError:
                        pass  # Reset manager not available
                
                conn.close()
                debug(f"Closed database connection: {id(conn)}")
            except Exception as e:
                warning(f"Error closing database connection: {e}")

def get_paper_trading_connection():
    """Get a safe paper trading database connection"""
    from src.paper_trading import DB_PATH
    return safe_database_connection(DB_PATH, timeout=10.0, check_same_thread=False)
