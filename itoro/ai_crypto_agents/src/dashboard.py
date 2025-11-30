#!/usr/bin/env python3
"""
🌙 Anarcho Capital's Cyberpunk Trading Dashboard
Real-time monitoring dashboard with neon aesthetics and live data updates
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import json
import sqlite3
import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

# Import debug function
try:
    from src.nice_funcs import debug as original_debug
    def debug(msg):
        # Suppress debug output during dashboard operation to avoid cluttering display
        pass
except ImportError:
    def debug(msg):
        pass

# ANSI Color Codes for Cyberpunk Theme
class Colors:
    # Primary cyberpunk colors
    CYAN = '\033[96m'          # Bright cyan
    TURQUOISE = '\033[36m'     # Turquoise
    BLUE = '\033[94m'          # Blue
    BRIGHT_BLUE = '\033[94m'   # Bright blue
    MAGENTA = '\033[95m'       # Magenta accents
    GREEN = '\033[92m'         # Success/BUY
    YELLOW = '\033[93m'        # Warning/neutral
    RED = '\033[91m'           # Error/SELL
    WHITE = '\033[97m'         # Box drawing
    BOLD = '\033[1m'           # Bold text
    RESET = '\033[0m'          # Reset all
    
    # Glitch effects
    GLITCH_CHARS = ['░', '▒', '▓', '█', '▄', '▀', '▌', '▐']

class CursorControl:
    """ANSI escape codes for cursor control"""
    SAVE_POSITION = '\033[s'
    RESTORE_POSITION = '\033[u'
    HIDE_CURSOR = '\033[?25l'
    SHOW_CURSOR = '\033[?25h'
    CLEAR_SCREEN = '\033[2J'
    MOVE_TO_TOP = '\033[H'
    
    @staticmethod
    def move_to(row, col):
        return f'\033[{row};{col}H'
    
    @staticmethod
    def move_up(lines):
        return f'\033[{lines}A'
    
    @staticmethod
    def clear_line():
        return '\033[2K'

    @staticmethod
    def clear_from_cursor_to_end():
        return '\033[0J'

class CyberpunkBanner:
    """Generate cyberpunk ASCII art banner"""
    
    @staticmethod
    def get_banner() -> str:
        """Return the main cyberpunk banner"""
        banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}                                                                              {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}{Colors.TURQUOISE}▄▀█ █▄░█ ▄▀█ █▀█ █▀▀ █░█ █▀█   █▀▀ ▄▀█ █▀█ █ ▀█▀ ▄▀█ █░░{Colors.RESET}  {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}{Colors.TURQUOISE}█▀█ █░▀█ █▀█ █▀▄ █▄▄ █▀█ █▄█   █▄▄ █▀█ █▀▀ █ ░█░ █▀█ █▄▄{Colors.RESET}  {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}                                                                              {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}{Colors.BRIGHT_BLUE}▀█▀ █▀█ ▄▀█ █▀▄ █ █▄░█ █▀▀   █▄░█ █▀▀ ▀▄▀ █░█ █▀{Colors.RESET}  {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}{Colors.BRIGHT_BLUE}░█░ █▀▄ █▀█ █▄▀ █ █░▀█ █▄█   █░▀█ ██▄ █░█ █▄█ ▄█{Colors.RESET}  {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}                                                                              {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}  {Colors.MAGENTA}╔══════════════════════════════════════════════════════════════╗{Colors.RESET}  {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}  {Colors.MAGENTA}║{Colors.RESET}  {Colors.BOLD}{Colors.WHITE}🌙 TRADING NEXUS - REAL-TIME MONITORING SYSTEM 🌙{Colors.RESET}  {Colors.MAGENTA}║{Colors.RESET}  {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}  {Colors.MAGENTA}╚══════════════════════════════════════════════════════════════╝{Colors.RESET}  {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}║{Colors.RESET}                                                                              {Colors.CYAN}║{Colors.RESET}
{Colors.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
        return banner

class DatabaseManager:
    """Manage database connections with pooling and error handling"""
    
    def __init__(self):
        self.connections = {}
        self.connection_timeout = 10  # Increased from 5 to 10 seconds
        self.lock = threading.Lock()
        self.connection_pool_size = 3  # Allow up to 3 connections per database
        self.connection_health_check_interval = 60  # Check connection health every 60 seconds
        self.last_health_check = {}
        self.failed_connections = {}  # Track failed connections to avoid repeated attempts
    
    def get_connection(self, db_path: str) -> Optional[sqlite3.Connection]:
        """Get pooled connection with timeout and health checks"""
        try:
            with self.lock:
                current_time = time.time()

                # Check if this database has been failing recently
                if db_path in self.failed_connections:
                    if current_time - self.failed_connections[db_path] < 30:  # 30 second cooldown
                        print(f"{Colors.YELLOW}⚠️ Skipping recently failed database: {db_path}{Colors.RESET}")
                        return None

                # Check connection health if it's been a while
                if (db_path in self.connections and
                    db_path in self.last_health_check and
                    current_time - self.last_health_check[db_path] > self.connection_health_check_interval):

                    try:
                        # Test the connection
                        self.connections[db_path].execute("SELECT 1").fetchone()
                        self.last_health_check[db_path] = current_time
                    except:
                        # Connection is bad, remove it
                        print(f"{Colors.YELLOW}⚠️ Removing stale database connection: {db_path}{Colors.RESET}")
                        self.connections[db_path].close()
                        del self.connections[db_path]
                        del self.last_health_check[db_path]

                if db_path not in self.connections:
                    conn = sqlite3.connect(db_path, timeout=self.connection_timeout)
                    conn.row_factory = sqlite3.Row
                    self.connections[db_path] = conn
                    self.last_health_check[db_path] = current_time
                    print(f"{Colors.GREEN}✅ Database connection established: {db_path}{Colors.RESET}")
                else:
                    # Update health check timestamp
                    self.last_health_check[db_path] = current_time

                return self.connections[db_path]

        except sqlite3.OperationalError as e:
            print(f"{Colors.RED}❌ Database connection failed: {e}{Colors.RESET}")
            self.failed_connections[db_path] = time.time()
            # Remove failed connection
            if db_path in self.connections:
                try:
                    self.connections[db_path].close()
                except:
                    pass
                del self.connections[db_path]
            return None
        except Exception as e:
            print(f"{Colors.RED}❌ Unexpected database error: {e}{Colors.RESET}")
            self.failed_connections[db_path] = time.time()
            return None
    
    def execute_query(self, db_path: str, query: str, params: Optional[Tuple] = None, retries: int = 2) -> Optional[List[Dict]]:
        """Execute query with error handling and retry logic"""
        for attempt in range(retries + 1):
            try:
                conn = self.get_connection(db_path)
                if not conn:
                    if attempt < retries:
                        print(f"{Colors.YELLOW}⚠️ Connection failed, retrying... ({attempt + 1}/{retries + 1}){Colors.RESET}")
                        time.sleep(1 * (attempt + 1))  # Exponential backoff
                        continue
                    return None
                
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

            except sqlite3.OperationalError as e:
                print(f"{Colors.YELLOW}⚠️ Query failed (attempt {attempt + 1}/{retries + 1}): {e}{Colors.RESET}")
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                print(f"{Colors.RED}❌ Query failed after {retries + 1} attempts: {e}{Colors.RESET}")
                return None
            except Exception as e:
                print(f"{Colors.RED}❌ Query error: {e}{Colors.RESET}")
                return None
        
        return None
    
    def close_all(self):
        """Close all database connections"""
        with self.lock:
            for conn in self.connections.values():
                try:
                    conn.close()
                except:
                    pass
            self.connections.clear()

class DataSourceDiscovery:
    """Auto-discover local data sources"""
    
    @staticmethod
    def discover_data_sources() -> Dict[str, Optional[str]]:
        """Auto-discover local data sources based on trading mode"""
        search_paths = ['src/data/', 'data/', './']
        sources = {
            'portfolio_db': None,
            'paper_trades_db': None,
            'live_trades_db': None,
            'sentiment_csv': None,
            'chart_sentiment_csv': None,
            'trading_mode': 'unknown'
        }

        # Determine trading mode
        try:
            from src import config
            is_paper_trading = getattr(config, 'PAPER_TRADING_ENABLED', True)
            sources['trading_mode'] = 'paper' if is_paper_trading else 'live'
        except ImportError:
            sources['trading_mode'] = 'paper'  # Default to paper trading
            is_paper_trading = True

        # Search for database files
        for path in search_paths:
            if os.path.exists(path):
                # Portfolio database - choose based on trading mode
                if is_paper_trading:
                    portfolio_file = 'portfolio_history_paper.db'
                else:
                    portfolio_file = 'portfolio_history_live.db'

                portfolio_path = os.path.join(path, portfolio_file)
                if os.path.exists(portfolio_path) and sources['portfolio_db'] is None:
                    sources['portfolio_db'] = portfolio_path

                # Paper trades database
                paper_trades_path = os.path.join(path, 'paper_trading.db')
                if os.path.exists(paper_trades_path) and sources['paper_trades_db'] is None:
                    sources['paper_trades_db'] = paper_trades_path

                # Live trades database
                live_trades_path = os.path.join(path, 'live_trades.db')
                if os.path.exists(live_trades_path) and sources['live_trades_db'] is None:
                    sources['live_trades_db'] = live_trades_path

                # Sentiment CSV files
                sentiment_path = os.path.join(path, 'sentiment_history.csv')
                if os.path.exists(sentiment_path) and sources['sentiment_csv'] is None:
                    sources['sentiment_csv'] = sentiment_path

                # Chart sentiment CSV
                chart_sentiment_path = os.path.join(path, 'charts', 'aggregated_market_sentiment.csv')
                if os.path.exists(chart_sentiment_path) and sources['chart_sentiment_csv'] is None:
                    sources['chart_sentiment_csv'] = chart_sentiment_path

        return sources

class PortfolioData:
    """Handle portfolio data retrieval and processing"""
    
    def __init__(self, cloud_db_manager=None, local_db_manager: DatabaseManager = None, portfolio_db_path: str = None, data_sources: Dict = None):
        self.cloud_db_manager = cloud_db_manager
        self.local_db_manager = local_db_manager
        self.portfolio_db_path = portfolio_db_path
        self.data_sources = data_sources or {}
        self.last_snapshot = None
    
    def _get_live_positions_from_tracker(self) -> Dict[str, Any]:
        """Get live position data directly from portfolio tracker (real-time prices)"""
        try:
            import sys
            from pathlib import Path
            
            # Get the absolute path to the project root
            dashboard_file = Path(__file__).resolve()
            project_root = dashboard_file.parent.parent
            src_path = str(project_root / 'src')
            
            # Add to path if not already there
            if src_path not in sys.path:
                sys.path.insert(0, src_path)

            from scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            if tracker and tracker.current_snapshot:
                snapshot = tracker.current_snapshot
                if snapshot.positions:
                # Return live positions with current prices
                    return snapshot.positions
                elif hasattr(snapshot, 'total_value_usd') and snapshot.total_value_usd > 0:
                    # If no positions but we have total value, return position data
                    return {
                        'total_value': snapshot.total_value_usd,
                        'usdc_balance': getattr(snapshot, 'usdc_balance', 0),
                        'sol_balance': getattr(snapshot, 'sol_balance', 0),
                        'sol_value': getattr(snapshot, 'sol_value_usd', 0),
                        'positions_value': getattr(snapshot, 'positions_value_usd', 0),
                        'position_count': getattr(snapshot, 'position_count', 0),
                        'positions': {},
                        'sol_price': getattr(snapshot, 'sol_price', 0)
                    }
        except Exception as e:
            debug(f"Could not get live positions from tracker: {e}")
        return {}
    
    def get_latest_portfolio(self) -> Optional[Dict[str, Any]]:
        """Get latest portfolio snapshot from multiple sources with intelligent fallback"""
        portfolio_data = None
        
        # PRIMARY: Try portfolio tracker first (live data)
        try:
            import sys
            import os
            from pathlib import Path
            
            # Get the absolute path to the project root
            dashboard_file = Path(__file__).resolve()
            project_root = dashboard_file.parent.parent
            src_path = str(project_root / 'src')
            
            # Add to path if not already there
            if src_path not in sys.path:
                sys.path.insert(0, src_path)

            from scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            if tracker and tracker.current_snapshot:
                snapshot = tracker.current_snapshot
                if hasattr(snapshot, 'total_value_usd') and snapshot.total_value_usd > 0:
                    debug(f"✅ Portfolio data loaded from LIVE portfolio tracker: ${snapshot.total_value_usd:.2f}")
                    # Convert snapshot to portfolio data format
                    portfolio_data = {
                        'total_value': snapshot.total_value_usd,
                        'usdc_balance': getattr(snapshot, 'usdc_balance', 0),
                        'sol_balance': getattr(snapshot, 'sol_balance', 0),
                        'sol_value': getattr(snapshot, 'sol_value_usd', 0),
                        'sol_price': getattr(snapshot, 'sol_price', 0),
                        'positions_value': getattr(snapshot, 'positions_value_usd', 0),
                        'position_count': getattr(snapshot, 'position_count', 0),
                        'positions': snapshot.positions or {},
                        'staked_sol_balance': getattr(snapshot, 'staked_sol_balance', 0),
                        'staked_sol_value': getattr(snapshot, 'staked_sol_value_usd', 0),
                        'timestamp': getattr(snapshot, 'timestamp', ''),
                        'last_updated': datetime.now()
                    }
                    # Calculate percentages
                    if portfolio_data['total_value'] > 0:
                        portfolio_data['usdc_pct'] = (portfolio_data['usdc_balance'] / portfolio_data['total_value'] * 100)
                        portfolio_data['sol_pct'] = (portfolio_data['sol_value'] / portfolio_data['total_value'] * 100)
                        portfolio_data['positions_pct'] = (portfolio_data['positions_value'] / portfolio_data['total_value'] * 100)
                        portfolio_data['staked_sol_pct'] = (portfolio_data['staked_sol_value'] / portfolio_data['total_value'] * 100)
                    return portfolio_data
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ Portfolio tracker failed: {e}{Colors.RESET}")

        # SECONDARY: Try local database first
        if self.local_db_manager and self.portfolio_db_path:
            try:
                portfolio_data = self._get_from_local_database()
                if portfolio_data:
                    debug("📊 Dashboard: Reading portfolio data from LOCAL database")
                    return portfolio_data
            except Exception as e:
                debug(f"📊 Dashboard: Local database read failed, trying cloud: {e}")
                print(f"{Colors.YELLOW}⚠️ Local database read failed, trying cloud: {e}{Colors.RESET}")
        
        # FALLBACK: Try cloud database
        if not portfolio_data and self.cloud_db_manager:
            try:
                portfolio_data = self._get_from_cloud_database()
                if portfolio_data:
                    debug("📊 Dashboard: Reading portfolio data from CLOUD database")
                    return portfolio_data
            except Exception as e:
                debug(f"📊 Dashboard: Cloud database read failed: {e}")
                print(f"{Colors.YELLOW}⚠️ Cloud database read failed: {e}{Colors.RESET}")
        
        if not portfolio_data:
            print(f"{Colors.RED}❌ No portfolio data found in any source{Colors.RESET}")
            return None
        
        return portfolio_data
    
    def _get_from_cloud_database(self) -> Optional[Dict[str, Any]]:
        """Get latest portfolio from cloud database via REST API"""
        try:
            # Determine trading mode for cloud database
            trading_mode = self.data_sources.get('trading_mode', 'paper')
            
            # Check if we're using REST API fallback
            if hasattr(self.cloud_db_manager, '_test_connection') and hasattr(self.cloud_db_manager, 'get_latest_paper_trading_portfolio'):
                # Using REST API fallback - use REST API method
                snapshot = self.cloud_db_manager.get_latest_paper_trading_portfolio()
                if not snapshot:
                    return None
            else:
                # Using direct PostgreSQL - use execute_query
                # Try multiple possible table names for cloud database
                possible_cloud_tables = ['portfolio_history', 'paper_portfolio', 'portfolio_snapshots']
                cloud_data = None

                for table_name in possible_cloud_tables:
                    query = f"""
                    SELECT total_value_usd, usdc_balance, sol_balance, sol_value_usd, 
                           positions_value_usd, staked_sol_balance, staked_sol_value_usd,
                           change_detected, change_type, metadata, created_at
                    FROM {table_name} 
                    ORDER BY created_at DESC 
                    LIMIT 1
                    """
                    
                    debug(f"📊 Querying cloud database table: {table_name}")
                    rows = self.cloud_db_manager.execute_query(query)
                    if rows:
                        cloud_data = rows[0]
                        debug(f"✅ Found portfolio data in cloud {table_name} table")
                        break

                if not cloud_data:
                    return None
                
                snapshot = cloud_data
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ Cloud database query failed: {e}{Colors.RESET}")
            return None
        
        # Parse metadata JSON
        metadata = {}
        if snapshot.get('metadata'):
            try:
                # Handle both JSON strings and dictionaries
                if isinstance(snapshot['metadata'], str):
                    metadata = json.loads(snapshot['metadata'])
                else:
                    metadata = snapshot['metadata']
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        
        # Extract data
        total_value = snapshot.get('total_value_usd', 0.0)
        usdc_balance = snapshot.get('usdc_balance', 0.0)
        sol_balance = snapshot.get('sol_balance', 0.0)
        sol_value = snapshot.get('sol_value_usd', 0.0)
        positions_value = snapshot.get('positions_value_usd', 0.0)
        staked_sol_balance = snapshot.get('staked_sol_balance', 0.0)
        staked_sol_value = snapshot.get('staked_sol_value_usd', 0.0)
        position_count = metadata.get('position_count', 0)
        positions = metadata.get('positions', {})
        
        # Calculate percentages
        usdc_pct = (usdc_balance / total_value * 100) if total_value > 0 else 0
        sol_pct = (sol_value / total_value * 100) if total_value > 0 else 0
        staked_sol_pct = (staked_sol_value / total_value * 100) if total_value > 0 else 0
        positions_pct = (positions_value / total_value * 100) if total_value > 0 else 0
        
        # Calculate SOL price
        sol_price = (sol_value / sol_balance) if sol_balance > 0 else 0
        
        return {
            'total_value': total_value,
            'usdc_balance': usdc_balance,
            'usdc_pct': usdc_pct,
            'sol_balance': sol_balance,
            'sol_value': sol_value,
            'sol_pct': sol_pct,
            'sol_price': sol_price,
            'staked_sol_balance': staked_sol_balance,
            'staked_sol_value': staked_sol_value,
            'staked_sol_pct': staked_sol_pct,
            'positions_value': positions_value,
            'positions_pct': positions_pct,
            'position_count': position_count,
            'positions': positions,
            'timestamp': snapshot.get('created_at', ''),
            'last_updated': datetime.now()
        }
    
    def _get_from_local_database(self) -> Optional[Dict[str, Any]]:
        """Get latest portfolio from local database (fallback)"""
        if not self.portfolio_db_path or not os.path.exists(self.portfolio_db_path):
            return None
            
        try:
            # First, let's see what tables exist in the database
            import sqlite3
            with sqlite3.connect(self.portfolio_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check what tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                debug(f"📊 Available tables in portfolio DB: {tables}")

                # Check for portfolio data in multiple possible tables
                portfolio_tables = ['portfolio_snapshots', 'paper_portfolio', 'portfolio_history']
                table_name = None

                for table in portfolio_tables:
                    if table in tables:
                        table_name = table
                        debug(f"✅ Found portfolio table: {table}")
                        break

                if not table_name:
                    debug(f"⚠️ No portfolio tables found. Available tables: {tables}")
                    return None

            # Try different queries based on table name
            if table_name == 'paper_portfolio':
                # paper_portfolio table might have different column structure
                query = f"""
                SELECT * FROM {table_name}
                ORDER BY timestamp DESC 
                LIMIT 1
                """
            elif table_name == 'portfolio_snapshots':
                # Standard portfolio_snapshots table
                query = f"""
                SELECT * FROM {table_name}
                ORDER BY timestamp DESC
                LIMIT 1
                """
            else:
                # Generic query for other tables
                query = f"""
                SELECT * FROM {table_name}
                ORDER BY timestamp DESC, created_at DESC
                LIMIT 1
                """

            # Use the database manager for consistent error handling and retry logic
            if hasattr(self, 'local_db_manager') and self.local_db_manager:
                rows = self.local_db_manager.execute_query(self.portfolio_db_path, query)
                if not rows:
                    debug(f"⚠️ No data in {table_name} table")
                    return None
                snapshot = rows[0]
                debug(f"✅ Found portfolio data in {table_name} table")
            else:
                # Fallback to direct connection if manager not available
                with sqlite3.connect(self.portfolio_db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                if not rows:
                    debug(f"⚠️ No data in {table_name} table (direct connection)")
                    return None
                snapshot = rows[0]
                debug(f"✅ Found portfolio data in {table_name} table (direct)")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ Local database query failed: {e}{Colors.RESET}")
            return None
        
        # Parse positions JSON - handle different column names for different tables
        positions = {}
        positions_json_column = None

        # Try different possible column names for positions
        for col_name in ['positions_json', 'positions', 'portfolio_positions', 'token_positions']:
            if col_name in snapshot.keys():
                positions_json_column = col_name
                break

        if positions_json_column and snapshot[positions_json_column]:
            try:
                positions = json.loads(snapshot[positions_json_column])
            except json.JSONDecodeError:
                positions = {}
        
        # Extract values - handle different column naming conventions
        total_value = 0.0
        usdc_balance = 0.0
        sol_balance = 0.0
        sol_value = 0.0
        positions_value = 0.0
        staked_sol_balance = 0.0
        staked_sol_value = 0.0
        position_count = 0

        # Try different column names for each value
        total_value_cols = ['total_value_usd', 'total_value', 'balance_usd', 'portfolio_value']
        usdc_cols = ['usdc_balance', 'usdc_amount', 'usdc_value']
        sol_cols = ['sol_balance', 'sol_amount', 'sol_value_usd']
        sol_value_cols = ['sol_value_usd', 'sol_value', 'sol_usd_value']
        positions_value_cols = ['positions_value_usd', 'positions_value', 'tokens_value']
        staked_sol_cols = ['staked_sol_balance', 'staked_sol_amount']
        staked_sol_value_cols = ['staked_sol_value_usd', 'staked_sol_value']
        position_count_cols = ['position_count', 'positions_count', 'token_count']

        # Extract total value
        for col in total_value_cols:
            if col in snapshot.keys() and snapshot[col]:
                total_value = float(snapshot[col])
                break

        # Extract USDC balance
        for col in usdc_cols:
            if col in snapshot.keys() and snapshot[col]:
                usdc_balance = float(snapshot[col])
                break

        # Extract SOL balance
        for col in sol_cols:
            if col in snapshot.keys() and snapshot[col]:
                sol_balance = float(snapshot[col])
                break

        # Extract SOL value
        for col in sol_value_cols:
            if col in snapshot.keys() and snapshot[col]:
                sol_value = float(snapshot[col])
                break

        # Extract positions value
        for col in positions_value_cols:
            if col in snapshot.keys() and snapshot[col]:
                positions_value = float(snapshot[col])
                break

        # Extract staked SOL values
        for col in staked_sol_cols:
            if col in snapshot.keys() and snapshot[col]:
                staked_sol_balance = float(snapshot[col])
                break

        for col in staked_sol_value_cols:
            if col in snapshot.keys() and snapshot[col]:
                staked_sol_value = float(snapshot[col])
                break

        # Extract position count
        for col in position_count_cols:
            if col in snapshot.keys() and snapshot[col]:
                position_count = int(snapshot[col])
                break
        
        # Get SOL price from database (try different column names)
        sol_price = 0.0
        sol_price_cols = ['sol_price', 'sol_price_usd', 'current_sol_price', 'price_sol']
        for col in sol_price_cols:
            if col in snapshot.keys() and snapshot[col]:
                sol_price = float(snapshot[col])
                break

        if sol_price <= 0 and sol_balance > 0:
            sol_price = (sol_value / sol_balance) if sol_balance > 0 else 0
        
        # Get staked SOL price from database (try different column names)
        staked_sol_price = 0.0
        staked_price_cols = ['staked_sol_price', 'staked_sol_price_usd', 'staked_price']
        for col in staked_price_cols:
            if col in snapshot.keys() and snapshot[col]:
                staked_sol_price = float(snapshot[col])
                break

        if staked_sol_price <= 0:
            staked_sol_price = sol_price
        
        # Calculate percentages
        usdc_pct = (usdc_balance / total_value * 100) if total_value > 0 else 0
        sol_pct = (sol_value / total_value * 100) if total_value > 0 else 0
        staked_sol_pct = (staked_sol_value / total_value * 100) if total_value > 0 else 0
        positions_pct = (positions_value / total_value * 100) if total_value > 0 else 0
        
        return {
            'total_value': total_value,
            'usdc_balance': usdc_balance,
            'usdc_pct': usdc_pct,
            'sol_balance': sol_balance,
            'sol_value': sol_value,
            'sol_pct': sol_pct,
            'sol_price': sol_price,
            'staked_sol_balance': staked_sol_balance,
            'staked_sol_value': staked_sol_value,
            'staked_sol_pct': staked_sol_pct,
            'staked_sol_price': staked_sol_price,
            'positions_value': positions_value,
            'positions_pct': positions_pct,
            'position_count': position_count,
            'positions': positions,
            'timestamp': snapshot['timestamp'] or '',
            'last_updated': datetime.now()
        }

class SentimentData:
    """Handle sentiment data retrieval from CSV files"""
    
    def __init__(self, sentiment_csv_path: Optional[str], chart_sentiment_csv_path: Optional[str]):
        self.sentiment_csv_path = sentiment_csv_path
        self.chart_sentiment_csv_path = chart_sentiment_csv_path
        self.last_sentiment_data = None
        # Add file modification time tracking and caching
        self.twitter_cache = {'data': None, 'mtime': 0}
        self.chart_cache = {'data': None, 'mtime': 0}
    
    def get_latest_sentiment(self) -> Dict[str, Any]:
        """Get latest sentiment data from both sources"""
        twitter_sentiment = self._get_twitter_sentiment()
        technical_sentiment = self._get_technical_sentiment()
        
        return {
            'twitter': twitter_sentiment,
            'technical': technical_sentiment,
            'last_updated': datetime.now()
        }
    
    def _get_file_mtime(self, filepath: str) -> float:
        """Get file modification time"""
        try:
            if os.path.exists(filepath):
                return os.path.getmtime(filepath)
        except:
            pass
        return 0
    
    def _get_twitter_sentiment(self) -> Dict[str, Any]:
        """Get latest Twitter sentiment with file change detection"""
        if not self.sentiment_csv_path or not os.path.exists(self.sentiment_csv_path):
            return {'sentiment': 'Unknown', 'score': 0.0, 'confidence': 0.0}
        
        try:
            # Check if file has been modified
            current_mtime = self._get_file_mtime(self.sentiment_csv_path)
            if current_mtime != self.twitter_cache['mtime']:
                # File has changed, read it
                df = pd.read_csv(self.sentiment_csv_path)
                if df.empty:
                    return {'sentiment': 'Unknown', 'score': 0.0, 'confidence': 0.0}
                
                latest = df.iloc[-1]
                self.twitter_cache['data'] = {
                    'sentiment': latest.get('classification', 'Unknown'),
                    'score': latest.get('sentiment_score', 0.0),
                    'confidence': latest.get('confidence', 0.0)
                }
                self.twitter_cache['mtime'] = current_mtime
            
            return self.twitter_cache['data']
        except Exception as e:
            return {'sentiment': 'Error', 'score': 0.0, 'confidence': 0.0}
    
    def _get_technical_sentiment(self) -> Dict[str, Any]:
        """Get latest technical sentiment with file change detection"""
        if not self.chart_sentiment_csv_path or not os.path.exists(self.chart_sentiment_csv_path):
            return {'sentiment': 'Unknown', 'score': 0.0, 'confidence': 0.0}
        
        try:
            # Check if file has been modified
            current_mtime = self._get_file_mtime(self.chart_sentiment_csv_path)
            if current_mtime != self.chart_cache['mtime']:
                # File has changed, read it
                df = pd.read_csv(self.chart_sentiment_csv_path)
                if df.empty:
                    return {'sentiment': 'Unknown', 'score': 0.0, 'confidence': 0.0}
                
                latest = df.iloc[-1]
                self.chart_cache['data'] = {
                    'sentiment': latest.get('overall_sentiment', 'Unknown'),
                    'score': latest.get('sentiment_score', 0.0),
                    'confidence': latest.get('confidence', 0.0)
                }
                self.chart_cache['mtime'] = current_mtime
            
            return self.chart_cache['data']
        except Exception as e:
            return {'sentiment': 'Error', 'score': 0.0, 'confidence': 0.0}

class TokenOnChainData:
    """Handle token on-chain activity data"""
    
    def __init__(self):
        self.data_file = Path("src/data/token_onchain_data.json")
        # Add cache with file modification time tracking
        self.cache = {'data': None, 'mtime': 0}
    
    def get_aggregated_status(self) -> Dict[str, Any]:
        """Get aggregated on-chain status with file change detection"""
        if not self.data_file.exists():
            return {
                'growing_count': 0,
                'shrinking_count': 0,
                'status_text': 'No Data',
                'color': 'YELLOW'
            }
        
        try:
            # Check if file has been modified
            current_mtime = os.path.getmtime(self.data_file) if self.data_file.exists() else 0
            
            if current_mtime != self.cache['mtime'] or self.cache['data'] is None:
                # File has changed, read it
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                tokens = data.get('tokens', {})
                growing = sum(1 for t in tokens.values() if t.get('trend_signal') == 'GROWING')
                shrinking = sum(1 for t in tokens.values() if t.get('trend_signal') == 'SHRINKING')
                stable = sum(1 for t in tokens.values() if t.get('trend_signal') == 'STABLE')
                
                # Format: "3↑ 0↓ (3 growing, 0 shrinking positions)"
                status_text = f"{growing}↑ {shrinking}↓ ({growing} growing, {shrinking} shrinking positions)"
                
                # Determine color
                if shrinking > growing:
                    color = 'RED'
                elif growing > 0:
                    color = 'GREEN'
                else:
                    color = 'YELLOW'
                
                self.cache['data'] = {
                    'growing_count': growing,
                    'shrinking_count': shrinking,
                    'stable_count': stable,
                    'status_text': status_text,
                    'color': color
                }
                self.cache['mtime'] = current_mtime
            
            return self.cache['data']
        except Exception as e:
            return {
                'growing_count': 0,
                'shrinking_count': 0,
                'status_text': 'Error',
                'color': 'RED'
            }

class TradeData:
    """Handle trade data retrieval and processing"""
    
    def __init__(self, db_manager: DatabaseManager, paper_trades_db_path: Optional[str], live_trades_db_path: Optional[str], cloud_db_manager=None):
        self.db_manager = db_manager
        self.cloud_db_manager = cloud_db_manager
        self.paper_trades_db_path = paper_trades_db_path
        self.live_trades_db_path = live_trades_db_path
        self.last_trade_ids = set()
        self.trade_cache = []
    
    def get_recent_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent trades from both sources"""
        trades = []
        
        # Get cloud trades first (if available)
        if self.cloud_db_manager and hasattr(self.cloud_db_manager, 'get_paper_trading_transactions'):
            try:
                cloud_trades = self._get_cloud_trades(limit)
                trades.extend(cloud_trades)
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️ Cloud trades failed: {e}{Colors.RESET}")
        
        # Get paper trades
        if self.paper_trades_db_path:
            paper_trades = self._get_paper_trades(limit)
            trades.extend(paper_trades)
        
        # Get live trades
        if self.live_trades_db_path:
            live_trades = self._get_live_trades(limit)
            trades.extend(live_trades)
        
        # Sort by timestamp and limit
        trades.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        return trades[:limit]
    
    def _get_cloud_trades(self, limit: int) -> List[Dict[str, Any]]:
        """Get trades from cloud database via REST API"""
        try:
            if not self.cloud_db_manager or not hasattr(self.cloud_db_manager, 'get_paper_trading_transactions'):
                return []
            
            rows = self.cloud_db_manager.get_paper_trading_transactions(limit)
            if not rows:
                return []
            
            trades = []
            for row in rows:
                # Convert timestamp to readable format
                try:
                    timestamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')).strftime('%H:%M:%S')
                except:
                    timestamp = str(row.get('timestamp', ''))
                
                trades.append({
                    'timestamp': timestamp,
                    'action': row.get('transaction_type', 'UNKNOWN'),
                    'amount': row.get('amount', 0.0),
                    'price': row.get('price_usd', 0.0),
                    'usd_value': row.get('value_usd', 0.0),
                    'agent': row.get('agent_name', 'unknown'),
                    'token': row.get('token_symbol', 'UNKNOWN'),
                    'source': 'cloud'
                })
            
            return trades
        except Exception as e:
            return []
    
    def _get_paper_trades(self, limit: int) -> List[Dict[str, Any]]:
        """Get paper trades"""
        # Check if paper_trades table exists
        try:
            conn = self.db_manager.get_connection(self.paper_trades_db_path)
            if not conn:
                return []
            
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='paper_trades'")
            if not cursor.fetchone():
                return []
            
            query = """
            SELECT timestamp, action, amount, price, usd_value, agent, token_address, token_symbol, token_name
            FROM paper_trades 
            ORDER BY timestamp DESC 
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            if not rows:
                return []
            
            trades = []
            for row in rows:
                # Convert timestamp to readable format
                try:
                    timestamp = datetime.fromtimestamp(row[0]).strftime('%H:%M:%S')
                except:
                    timestamp = str(row[0])
                
                # Use stored symbol if available, otherwise fallback
                token_symbol = row[7] if len(row) > 7 and row[7] else self._get_token_symbol(row[6])
                
                trades.append({
                    'timestamp': timestamp,
                    'action': row[1],
                    'amount': row[2],
                    'price': row[3],
                    'usd_value': row[4],
                    'agent': row[5],
                    'token': token_symbol,
                    'source': 'paper'
                })
            
            return trades
        except Exception as e:
            return []
    
    def _get_live_trades(self, limit: int) -> List[Dict[str, Any]]:
        """Get live trades"""
        try:
            conn = self.db_manager.get_connection(self.live_trades_db_path)
            if not conn:
                return []
            
            cursor = conn.cursor()
            query = """
            SELECT timestamp, side, size, price_usd, usd_value, agent, token, token_symbol, token_name
            FROM live_trades 
            ORDER BY id DESC 
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            if not rows:
                return []
            
            trades = []
            for row in rows:
                # Live trades timestamp is already in HH:MM:SS format
                timestamp = str(row[0])
                
                # Use stored symbol if available, otherwise fallback
                token_symbol = row[7] if len(row) > 7 and row[7] else self._get_token_symbol(row[6])
                
                trades.append({
                    'timestamp': timestamp,
                    'action': row[1],
                    'amount': row[2],
                    'price': row[3],
                    'usd_value': row[4],
                    'agent': row[5],
                    'token': token_symbol,
                    'source': 'live'
                })
            
            return trades
        except Exception as e:
            return []

class DeFiData:
    """Handle DeFi position data retrieval and processing"""

    def __init__(self):
        self.defi_manager = None
        self.last_update = 0
        self.cache_duration = 30  # seconds

    def _get_defi_manager(self):
        """Lazy load DeFi position manager"""
        if self.defi_manager is None:
            try:
                from src.scripts.defi.defi_position_manager import get_defi_position_manager
                self.defi_manager = get_defi_position_manager()
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️ Failed to load DeFi manager: {e}{Colors.RESET}")
                self.defi_manager = None
        return self.defi_manager

    def get_defi_positions_summary(self) -> Dict[str, Any]:
        """Get comprehensive DeFi positions summary"""
        try:
            manager = self._get_defi_manager()
            if not manager:
                return {"error": "DeFi manager not available"}

            # Get active loops
            active_loops = manager.get_active_loops()

            # If no active loops, check for recently completed loops (positions exist)
            if not active_loops:
                positions_count = len(manager.get_all_positions())
                if positions_count > 0:
                    # Return a summary showing there was recent DeFi activity
                    return {
                        "active_loops": [],
                        "total_exposure": 0.0,
                        "total_collateral": 0.0,
                        "reserved_balances": manager.get_all_reserved_balances(),
                        "recent_activity": True,
                        "positions_count": positions_count
                    }

                return {"active_loops": [], "total_exposure": 0.0, "reserved_balances": {}}

            # Get reserved balances
            reserved_balances = manager.get_all_reserved_balances()

            # Calculate totals
            total_exposure = sum(loop.total_exposure_usd for loop in active_loops)
            total_collateral = sum(loop.initial_capital_usd for loop in active_loops)

            return {
                "active_loops": active_loops,
                "total_exposure": total_exposure,
                "total_collateral": total_collateral,
                "reserved_balances": reserved_balances,
                "loop_count": len(active_loops)
            }

        except Exception as e:
            return {"error": str(e)}

class CyberpunkDashboard:
    """Main dashboard class with cyberpunk aesthetics"""
    
    def __init__(self):
        # Set dashboard mode to suppress console output from other services
        try:
            from src.scripts.shared_services.logger import set_dashboard_mode
            set_dashboard_mode(True)
        except Exception:
            pass  # Logger not available, continue without suppression
        
        self.db_manager = DatabaseManager()
        self.cloud_db_manager = None
        self.data_sources = DataSourceDiscovery.discover_data_sources()
        self.portfolio_data = None
        self.sentiment_data = None
        self.trade_data = None
        self.onchain_data = None
        self.defi_data = None
        self.running = False
        
        # Initialize cloud database manager
        self._initialize_cloud_database()
        
        # Initialize data handlers
        self._initialize_data_handlers()
        
        # Display state
        self.current_portfolio = None
        self.current_sentiment = None
        self.current_trades = []
        self.last_update_time = None
        
        # Portfolio data state
        self.current_portfolio = None

    def _get_token_symbol(self, token_address: str) -> str:
        """Map token address to symbol"""
        # Common token mappings
        token_map = {
            'So11111111111111111111111111111111111111112': 'SOL',
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'USDC',
            'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263': 'BONK',
            'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN': 'JUP',
            'WENWENvqqNya429ubCdR81ZmD69brwQaaD4rMk6MMZf': 'WEN',
            'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm': 'WIF',
            'Bome6vY6pH1fgqC3X1b1KVre2xN4WhHkUG5vKJg7zfr': 'BOME',
            'HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3': 'PYTH'
        }
        return token_map.get(token_address, token_address[:8] + '...')

    def _initialize_cloud_database(self):
        """Initialize cloud database manager"""
        try:
            from src.scripts.database.cloud_database import get_cloud_database_manager
            self.cloud_db_manager = get_cloud_database_manager()
            if self.cloud_db_manager:
                    print(f"{Colors.GREEN}Cloud database manager initialized{Colors.RESET}")
            else:
                print(f"{Colors.YELLOW}⚠️ Cloud database not configured{Colors.RESET}")
        except ImportError:
            print(f"{Colors.YELLOW}⚠️ Cloud database module not available{Colors.RESET}")
        except Exception as e:
                print(f"{Colors.RED}Cloud database initialization failed: {e}{Colors.RESET}")
    
    def _initialize_data_handlers(self):
        """Initialize data handlers based on discovered sources"""
        # Initialize portfolio data with cloud database priority
        self.portfolio_data = PortfolioData(
            cloud_db_manager=self.cloud_db_manager,
            local_db_manager=self.db_manager,
            portfolio_db_path=self.data_sources['portfolio_db'],
            data_sources=self.data_sources
        )

        if self.data_sources['sentiment_csv'] or self.data_sources['chart_sentiment_csv']:
            self.sentiment_data = SentimentData(
                self.data_sources['sentiment_csv'],
                self.data_sources['chart_sentiment_csv']
            )

        if self.data_sources['paper_trades_db'] or self.data_sources['live_trades_db']:
            self.trade_data = TradeData(
                self.db_manager,
                self.data_sources['paper_trades_db'],
                self.data_sources['live_trades_db'],
                self.cloud_db_manager
            )

        # Initialize on-chain data handler
        self.onchain_data = TokenOnChainData()

        # Initialize DeFi data handler
        try:
            self.defi_data = DeFiData()
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ DeFi data handler failed to initialize: {e}{Colors.RESET}")
            self.defi_data = None

    def _validate_portfolio_data(self, data: Dict[str, Any]) -> bool:
        """Validate portfolio data for display"""
        if not data:
            return False

        # Check if required fields exist and are reasonable
        total_value = data.get('total_value', 0)
        if total_value <= 0:
            return False

        # Check if total value is within reasonable bounds (not too high or negative)
        if total_value > 10000000:  # More than $10M seems suspicious
            print(f"{Colors.YELLOW}⚠️ Portfolio value seems unusually high: ${total_value:,.2f}{Colors.RESET}")
            return False

        # Check if positions data is reasonable
        positions_value = data.get('positions_value', 0)
        if positions_value < 0:
            return False

        # Check if percentages add up reasonably (within 5% tolerance)
        total_calculated = (data.get('usdc_balance', 0) +
                          data.get('sol_value', 0) +
                          positions_value +
                          data.get('staked_sol_value', 0))

        if abs(total_calculated - total_value) > (total_value * 0.05):  # 5% tolerance
            print(f"{Colors.YELLOW}⚠️ Portfolio values don't add up correctly. Expected: ${total_value:,.2f}, Calculated: ${total_calculated:,.2f}{Colors.RESET}")
            return False

        return True

    def _portfolio_data_changed(self, fresh_portfolio: Dict[str, Any]) -> bool:
        """Check if portfolio data has actually changed by comparing key values"""
        if not self.current_portfolio or not fresh_portfolio:
            return True  # Update if one is None

        # Compare key values instead of object references
        current_total = self.current_portfolio.get('total_value', 0)
        fresh_total = fresh_portfolio.get('total_value', 0)

        # Check if total value changed significantly (more than $0.01)
        if abs(current_total - fresh_total) > 0.01:
            return True

        # Check if SOL balance changed
        current_sol = self.current_portfolio.get('sol_balance', 0)
        fresh_sol = fresh_portfolio.get('sol_balance', 0)
        if abs(current_sol - fresh_sol) > 0.001:  # SOL precision
            return True

        # Check if USDC balance changed
        current_usdc = self.current_portfolio.get('usdc_balance', 0)
        fresh_usdc = fresh_portfolio.get('usdc_balance', 0)
        if abs(current_usdc - fresh_usdc) > 0.01:
            return True

        # Check if positions changed
        current_positions = self.current_portfolio.get('position_count', 0)
        fresh_positions = fresh_portfolio.get('position_count', 0)
        if current_positions != fresh_positions:
            return True

        # Check if SOL price changed significantly
        current_sol_price = self.current_portfolio.get('sol_price', 0)
        fresh_sol_price = fresh_portfolio.get('sol_price', 0)
        if abs(current_sol_price - fresh_sol_price) > 0.01:  # $0.01 price change
            return True

        return False  # No significant changes detected

    def _trades_data_changed(self, new_trades: List[Dict[str, Any]]) -> bool:
        """Check if trades data has actually changed"""
        if not self.current_trades or not new_trades:
            return len(self.current_trades or []) != len(new_trades)

        # Compare lengths first (most efficient check)
        if len(self.current_trades) != len(new_trades):
            return True

        # Compare the most recent trade details (timestamp, action, amount, etc.)
        for i in range(min(5, len(new_trades))):  # Check first 5 trades
            current_trade = self.current_trades[i]
            new_trade = new_trades[i]

            # Compare key fields
            if (current_trade.get('timestamp') != new_trade.get('timestamp') or
                current_trade.get('action') != new_trade.get('action') or
                abs(current_trade.get('usd_value', 0) - new_trade.get('usd_value', 0)) > 0.01):
                return True

        return False  # No significant changes detected

    def _sentiment_data_changed(self, new_sentiment: Dict[str, Any]) -> bool:
        """Check if sentiment data has actually changed"""
        if not self.current_sentiment or not new_sentiment:
            return True  # Update if one is None

        # Compare technical sentiment
        current_tech = self.current_sentiment.get('technical', {})
        new_tech = new_sentiment.get('technical', {})

        if (current_tech.get('sentiment') != new_tech.get('sentiment') or
            abs(current_tech.get('score', 0) - new_tech.get('score', 0)) > 0.01):
            return True

        # Compare social sentiment
        current_social = self.current_sentiment.get('twitter', {})
        new_social = new_sentiment.get('twitter', {})

        if (current_social.get('sentiment') != new_social.get('sentiment') or
            abs(current_social.get('score', 0) - new_social.get('score', 0)) > 0.01):
            return True

        return False  # No significant changes detected

    
    def clear_screen(self):
        """Clear terminal screen using ANSI escape codes"""
        print('\033[2J\033[H', end='')

    def clear_screen_windows_compatible(self):
        """Clear screen in a Windows-compatible way"""
        # Use os.system for reliable Windows compatibility
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def clear_screen_no_scroll(self):
        """Clear screen without moving cursor to top"""
        print("\033[2J", end="")  # Clear screen but keep cursor position
    
    def clear_screen_and_home(self):
        """Clear screen and move cursor to home position"""
        print("\033[2J\033[H", end="")  # Clear screen and move to top-left
    
    def clear_screen_preserve_position(self):
        """Clear screen and preserve cursor position using ANSI escape codes"""
        # Save cursor position, clear screen, restore position
        print("\033[s\033[2J\033[u", end="")
    
    def print_banner(self):
        """Print cyberpunk banner"""
        print(CyberpunkBanner.get_banner())
        print()
    
    def print_data_sources_status(self):
        """Print discovered data sources status"""
        print(f"{Colors.CYAN}🔍 Data Sources Status:{Colors.RESET}")
        
        # Show trading mode
        trading_mode = self.data_sources.get('trading_mode', 'unknown')
        mode_color = Colors.GREEN if trading_mode == 'paper' else Colors.YELLOW
        mode_text = "📈 PAPER TRADING" if trading_mode == 'paper' else "💰 LIVE TRADING"
        print(f"  {mode_color}🎮 Trading Mode: {mode_text}{Colors.RESET}")
        
        # Show data sources
        for name, path in self.data_sources.items():
            if name == 'trading_mode':
                continue
            status = f"{Colors.GREEN}✓{Colors.RESET}" if path else f"{Colors.RED}✗{Colors.RESET}"
            source_name = name.replace('_', ' ').title()
            print(f"  {status} {source_name}: {path or 'Not found'}")
        print()
    
    def render_dashboard(self):
        """Render the complete dashboard (initial display only)"""
        self.print_banner()
        
        # Portfolio section
        self._render_portfolio_section()
        print()
        
        # Trading stats section
        self._render_trading_stats_section()
        print()
        
        # Market analysis section
        self._render_market_analysis_section()
        print()
        
        # Individual positions section
        self._render_positions_section()
        print()

        # DeFi positions section
        self._render_defi_positions_section()
        print()

        # Recent trades section
        self._render_trades_section()
        print()
        
        # Footer
        self._render_footer()
    
    def _render_portfolio_section(self):
        """Render portfolio status section"""
        print(f"{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}                    {Colors.BOLD}{Colors.TURQUOISE}💎 PORTFOLIO STATUS{Colors.RESET}                    {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}╠══════════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")
        
        if self.current_portfolio:
            portfolio = self.current_portfolio
            total_value = portfolio.get('total_value', 0)

            if total_value > 0:
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}💰 Total Value:{Colors.RESET} {Colors.MAGENTA}${total_value:,.2f}{Colors.RESET}                                                           {Colors.CYAN}║{Colors.RESET}")
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}📈 SOL:{Colors.RESET} {portfolio['sol_balance']:.2f} @ {Colors.GREEN}${portfolio['sol_price']:.2f}{Colors.RESET} = {Colors.MAGENTA}${portfolio['sol_value']:,.2f}{Colors.RESET} ({portfolio['sol_pct']:.1f}%)                                      {Colors.CYAN}║{Colors.RESET}")
                
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}💵 USDC:{Colors.RESET} {Colors.MAGENTA}${portfolio['usdc_balance']:,.2f}{Colors.RESET} ({portfolio['usdc_pct']:.1f}%)                                                           {Colors.CYAN}║{Colors.RESET}")
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🎯 Positions:{Colors.RESET} {portfolio['position_count']} tokens | {Colors.MAGENTA}${portfolio['positions_value']:,.2f}{Colors.RESET} ({portfolio['positions_pct']:.1f}%)                                           {Colors.CYAN}║{Colors.RESET}")
            else:
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.YELLOW}⚠️ Portfolio data loading... (value: ${total_value:.2f}){Colors.RESET}                                                           {Colors.CYAN}║{Colors.RESET}")
        else:
            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.RED}❌ Portfolio data unavailable{Colors.RESET}                                                           {Colors.CYAN}║{Colors.RESET}")
        
        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")
    
    def _render_trading_stats_section(self):
        """Render trading statistics section with PnL and win/loss data"""
        print(f"{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}                    {Colors.BOLD}{Colors.TURQUOISE}📊 TRADING STATISTICS{Colors.RESET}                    {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}╠══════════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")
        
        try:
            # Get PnL data from portfolio tracker (lightweight approach)
            pnl_data = self._get_lightweight_pnl()
            if pnl_data:
                # 24h PnL
                pnl_24h = pnl_data.get('pnl_24h', 0.0)
                pnl_24h_color = Colors.GREEN if pnl_24h >= 0 else Colors.RED
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}💰 24h PnL:{Colors.RESET} {pnl_24h_color}${pnl_24h:+,.2f}{Colors.RESET}                                                      {Colors.CYAN}║{Colors.RESET}")
                
                # 7d PnL
                pnl_7d = pnl_data.get('pnl_7d', 0.0)
                pnl_7d_color = Colors.GREEN if pnl_7d >= 0 else Colors.RED
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}📈 7d PnL:{Colors.RESET} {pnl_7d_color}${pnl_7d:+,.2f}{Colors.RESET}                                                       {Colors.CYAN}║{Colors.RESET}")
                
                # Total PnL
                pnl_total = pnl_data.get('pnl_total', 0.0)
                pnl_total_color = Colors.GREEN if pnl_total >= 0 else Colors.RED
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🎯 Total PnL:{Colors.RESET} {pnl_total_color}${pnl_total:+,.2f}{Colors.RESET}                                                    {Colors.CYAN}║{Colors.RESET}")
            
            # Get win/loss data (lightweight approach)
            win_loss_data = self._get_lightweight_win_loss()
            if win_loss_data:
                consecutive_wins = win_loss_data.get('consecutive_wins', 0)
                consecutive_losses = win_loss_data.get('consecutive_losses', 0)
                total_trades = win_loss_data.get('total_trades', 0)
                win_rate = win_loss_data.get('win_rate', 0.0)
                current_mode = win_loss_data.get('current_mode', 'unknown')
                
                # Mode indicator
                mode_color = Colors.YELLOW if current_mode == 'paper' else Colors.GREEN if current_mode == 'live' else Colors.WHITE
                mode_text = "PAPER TRADING MODE" if current_mode == 'paper' else "LIVE TRADING MODE" if current_mode == 'live' else f"{current_mode.upper()} MODE"
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🎮 Mode:{Colors.RESET} {mode_color}{mode_text}{Colors.RESET}                                                      {Colors.CYAN}║{Colors.RESET}")
                
                # Consecutive wins/losses
                wins_color = Colors.GREEN if consecutive_wins > 0 else Colors.WHITE
                losses_color = Colors.RED if consecutive_losses > 0 else Colors.WHITE
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🏆 Consecutive:{Colors.RESET} {wins_color}{consecutive_wins} wins{Colors.RESET} | {losses_color}{consecutive_losses} losses{Colors.RESET}                                           {Colors.CYAN}║{Colors.RESET}")
                
                # Win rate and total trades
                win_rate_color = Colors.GREEN if win_rate >= 50 else Colors.RED if win_rate < 30 else Colors.YELLOW
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}📊 Performance:{Colors.RESET} {win_rate_color}{win_rate:.1f}%{Colors.RESET} win rate | {Colors.WHITE}{total_trades}{Colors.RESET} total trades                                    {Colors.CYAN}║{Colors.RESET}")
            
            if not pnl_data and not win_loss_data:
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.YELLOW}📊 PnL and win/loss data loading...{Colors.RESET}                                               {Colors.CYAN}║{Colors.RESET}")
                
        except Exception as e:
            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.RED}❌ Trading statistics unavailable{Colors.RESET}                                               {Colors.CYAN}║{Colors.RESET}")
        
        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")
    
    def _get_lightweight_pnl(self):
        """Get PnL data with proper fallback calculation"""
        try:
            # Try to get PnL from existing portfolio data
            if self.current_portfolio and self.current_portfolio.get('total_value', 0) > 0:
                total_value = self.current_portfolio['total_value']

                # Use actual starting balance from config instead of hardcoded 1000
                try:
                    from src import config
                    starting_balance = getattr(config, 'PAPER_INITIAL_BALANCE', 1000.0)
                except ImportError:
                    starting_balance = 1000.0  # Fallback if config not found

                return {
                    'pnl_24h': 0.0,  # Placeholder - would need historical data
                    'pnl_7d': 0.0,   # Placeholder - would need historical data  
                    'pnl_total': total_value - starting_balance  # Use actual starting balance
                }

            # Fallback to cached data if available
            if (self.portfolio_cache and
                self.portfolio_cache.get('total_value', 0) > 0):
                total_value = self.portfolio_cache['total_value']
                try:
                    from src import config
                    starting_balance = getattr(config, 'PAPER_INITIAL_BALANCE', 1000.0)
                except ImportError:
                    starting_balance = 1000.0  # Fallback if config not found

                return {
                    'pnl_24h': 0.0,
                    'pnl_7d': 0.0,
                    'pnl_total': total_value - starting_balance
                }

            return None
        except Exception:
            return None
    
    def _get_lightweight_win_loss(self):
        """Get win/loss data from portfolio tracker - MODE-AGNOSTIC"""
        try:
            # Use portfolio tracker's trading statistics
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            if not tracker:
                return None
                
            stats = tracker.get_trading_statistics()
            if not stats:
                return None
                
            return {
                'consecutive_wins': stats.get('consecutive_wins', 0),
                'consecutive_losses': stats.get('consecutive_losses', 0),
                'total_trades': stats.get('total_wins', 0) + stats.get('total_losses', 0),
                'win_rate': stats.get('win_rate', 0.0),
                'current_mode': stats.get('current_mode', 'unknown')
            }
        except Exception as e:
            debug(f"Error getting win/loss from portfolio tracker: {e}")
            return None
    
    
    def _format_price(self, price: float) -> str:
        """Format price in exponential notation for small values"""
        if price <= 0:
            return "0.00"
        elif price < 0.001:
            return f"{price:.2e}"
        else:
            return f"{price:.6f}"

    def _render_positions_section(self):
        """Render individual positions section"""
        print(f"{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}                    {Colors.BOLD}{Colors.TURQUOISE}🎯 INDIVIDUAL POSITIONS{Colors.RESET}                    {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}╠══════════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")
        
        if self.current_portfolio and self.current_portfolio.get('positions'):
            positions = self.current_portfolio['positions']
            if positions:
                for token_address, position_data in positions.items():
                    
                    # Handle both old format (float) and new format (dict)
                    if isinstance(position_data, dict):
                        amount = position_data.get('amount', 0)
                        price = position_data.get('price', 0)
                        # Handle both 'value_usd' and 'value' keys for backward compatibility
                        usd_value = position_data.get('value_usd', position_data.get('value', 0))
                    else:
                        # Backward compatibility with old format
                        usd_value = position_data
                        amount = 0
                        price = 0
                    
                    # Get token symbol from position data or fall back to service
                    if isinstance(position_data, dict):
                        token_symbol = position_data.get('symbol')
                    
                    if not token_symbol:
                        # Fallback to metadata service
                        try:
                            from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
                            metadata_service = get_token_metadata_service()
                            token_symbol = metadata_service.get_token_symbol(token_address)
                        except:
                            # Final fallback to hardcoded mapping
                            token_symbol = self._get_token_symbol(token_address)
                    
                    # Calculate percentage of total portfolio
                    total_value = self.current_portfolio.get('total_value', 0)
                    percentage = (usd_value / total_value * 100) if total_value > 0 else 0
                    
                    if price > 0 and amount > 0:
                        formatted_price = self._format_price(price)
                        print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🪙 {token_symbol}:{Colors.RESET} {amount:,.2f} @ ${formatted_price} = {Colors.MAGENTA}${usd_value:,.2f}{Colors.RESET} ({percentage:.1f}%) {Colors.CYAN}║{Colors.RESET}")
                    else:
                        print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🪙 {token_symbol}:{Colors.RESET} {Colors.MAGENTA}${usd_value:,.2f}{Colors.RESET} ({percentage:.1f}%) {Colors.YELLOW}(price unavailable){Colors.RESET} {Colors.CYAN}║{Colors.RESET}")
                    
                    # Add empty line for spacing between positions
                    print(f"{Colors.CYAN}║{Colors.RESET}                                                                              {Colors.CYAN}║{Colors.RESET}")
                
                # Add staked SOL as a special position if it exists
                if self.current_portfolio and self.current_portfolio.get('staked_sol_balance', 0) > 0:
                    staked_balance = self.current_portfolio.get('staked_sol_balance', 0)
                    staked_value = self.current_portfolio.get('staked_sol_value', 0)
                    staked_price = self.current_portfolio.get('sol_price', 0)  # Use SOL price for staked SOL
                    total_value = self.current_portfolio.get('total_value', 0)
                    staked_percentage = (staked_value / total_value * 100) if total_value > 0 else 0
                    
                    if staked_price > 0:
                        formatted_price = self._format_price(staked_price)
                        print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🔒 stSOL:{Colors.RESET} {staked_balance:.2f} @ ${formatted_price} = {Colors.MAGENTA}${staked_value:,.2f}{Colors.RESET} ({staked_percentage:.1f}%) {Colors.CYAN}║{Colors.RESET}")
                    else:
                        print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🔒 stSOL:{Colors.RESET} {Colors.MAGENTA}${staked_value:,.2f}{Colors.RESET} ({staked_percentage:.1f}%) {Colors.YELLOW}(price unavailable){Colors.RESET} {Colors.CYAN}║{Colors.RESET}")
                    
                    # Add empty line for spacing after staked SOL
                    print(f"{Colors.CYAN}║{Colors.RESET}                                                                              {Colors.CYAN}║{Colors.RESET}")
            else:
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.YELLOW}No individual positions held{Colors.RESET}                                                 {Colors.CYAN}║{Colors.RESET}")
        else:
            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.RED}❌ Position data unavailable{Colors.RESET}                                                 {Colors.CYAN}║{Colors.RESET}")
        
        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")

    def _render_defi_positions_section(self):
        """Render DeFi positions section"""
        print(f"{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}                     {Colors.BOLD}{Colors.MAGENTA}💰 DEFİ POSITIONS{Colors.RESET}                     {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}╠══════════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")

        if self.defi_data:
            defi_summary = self.defi_data.get_defi_positions_summary()

            if defi_summary.get("error"):
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.RED}❌ DeFi data unavailable: {defi_summary['error']}{Colors.RESET}                        {Colors.CYAN}║{Colors.RESET}")
            elif not defi_summary.get("active_loops") and not defi_summary.get("recent_activity"):
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.YELLOW}No active DeFi positions{Colors.RESET}                                                   {Colors.CYAN}║{Colors.RESET}")
            elif defi_summary.get("recent_activity"):
                # Show recent DeFi activity summary
                positions_count = defi_summary.get("positions_count", 0)
                reserved_balances = defi_summary.get("reserved_balances", {})

                # Calculate totals
                total_reserved = sum(rb.reserved_amount_usd for rb in reserved_balances.values()) if reserved_balances else 0

                # Main status line with key metrics
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.GREEN}💰 DeFi Activity:{Colors.RESET} {positions_count} positions completed | {Colors.MAGENTA}Reserved: ${total_reserved:,.2f}{Colors.RESET}         {Colors.CYAN}║{Colors.RESET}")

                # Activity summary box
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}┌─ Activity Summary ──────────────────────────────────────────────┐{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}│{Colors.RESET} {Colors.GREEN}✅{Colors.RESET} {positions_count} leverage positions completed successfully              {Colors.WHITE}│{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")
                if reserved_balances:
                    print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}│{Colors.RESET} {Colors.YELLOW}🔒{Colors.RESET} {len(reserved_balances)} tokens reserved as collateral for active positions      {Colors.WHITE}│{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")
                else:
                    print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}│{Colors.RESET} {Colors.BLUE}🧹{Colors.RESET} All positions have been fully unwound - no reserves held     {Colors.WHITE}│{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}└─────────────────────────────────────────────────────────────────────┘{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")

                # Reserved balances section (only if there are reserves)
                if reserved_balances and len(reserved_balances) > 0:
                    print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}┌─ Reserved Balances ─────────────────────────────────────────────┐{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")

                    # Show up to 3 reserved balances
                    for i, (token_addr, balance) in enumerate(list(reserved_balances.items())[:3]):
                        if hasattr(balance, 'reserved_amount') and hasattr(balance, 'reserved_amount_usd'):
                            # Use our own token symbol mapping
                            token_symbol = self._get_token_symbol(token_addr)

                            reason_icon = "🏦" if "collateral" in str(balance.reason).lower() else "💰" if "borrow" in str(balance.reason).lower() else "🔄"
                            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}│{Colors.RESET} {reason_icon} {token_symbol}: {balance.reserved_amount:.4f} ({Colors.MAGENTA}${balance.reserved_amount_usd:,.2f}{Colors.RESET}) - {balance.reason}{' '*(15-len(str(balance.reason)))}{Colors.WHITE}│{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")

                    if len(reserved_balances) > 3:
                        remaining = len(reserved_balances) - 3
                        print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}│{Colors.RESET} {Colors.GRAY}... and {remaining} more tokens reserved{Colors.RESET}{' '*(35)}{Colors.WHITE}│{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")

                    print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}└─────────────────────────────────────────────────────────────────────┘{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")
            else:
                # Show active loops
                for loop in defi_summary["active_loops"]:
                    leverage_ratio = loop.leverage_ratio if hasattr(loop, 'leverage_ratio') and loop.leverage_ratio > 0 else 1.0
                    health_color = Colors.GREEN if loop.health_score > 0.7 else (Colors.YELLOW if loop.health_score > 0.5 else Colors.RED)

                    print(f"{Colors.CYAN}║{Colors.RESET} 🔄 Loop: {loop.loop_id[-8:]} | {leverage_ratio:.1f}x leverage | Health: {health_color}{loop.health_score:.2f}{Colors.RESET} {Colors.CYAN}║{Colors.RESET}")

                    # Show exposure and collateral info
                    exposure = getattr(loop, 'total_exposure_usd', 0)
                    collateral = getattr(loop, 'initial_capital_usd', 0)
                    if exposure > 0:
                        print(f"{Colors.CYAN}║{Colors.RESET} 💰 Exposure: ${exposure:,.2f} | Collateral: ${collateral:,.2f} | Iterations: {getattr(loop, 'iterations', 0)}/{getattr(loop, 'max_iterations', 0)} {Colors.CYAN}║{Colors.RESET}")

                    # Add spacing
                    print(f"{Colors.CYAN}║{Colors.RESET}                                                                              {Colors.CYAN}║{Colors.RESET}")

                # Show reserved balances summary
                reserved_balances = defi_summary.get("reserved_balances", {})
                if reserved_balances:
                    total_reserved = sum(rb.reserved_amount_usd for rb in reserved_balances.values())
                    print(f"{Colors.CYAN}║{Colors.RESET} 🔒 Reserved Balances: ${total_reserved:,.2f} total                                      {Colors.CYAN}║{Colors.RESET}")

                    for token_addr, balance in list(reserved_balances.items())[:2]:  # Show top 2
                        token_symbol = token_addr[-8:]  # Last 8 chars of address
                        if hasattr(balance, 'reserved_amount') and hasattr(balance, 'reserved_amount_usd'):
                            print(f"{Colors.CYAN}║{Colors.RESET}   • {token_symbol}: {balance.reserved_amount:.4f} (${balance.reserved_amount_usd:,.2f}) - {balance.reason} {Colors.CYAN}║{Colors.RESET}")
                else:
                    print(f"{Colors.CYAN}║{Colors.RESET} 🔒 No reserved balances                                                    {Colors.CYAN}║{Colors.RESET}")
        else:
            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.RED}❌ DeFi tracking unavailable{Colors.RESET}                                              {Colors.CYAN}║{Colors.RESET}")

        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")

    def _render_market_analysis_section(self):
        """Render market analysis section"""
        print(f"{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}                    {Colors.BOLD}{Colors.TURQUOISE}🌐 MARKET ANALYSIS{Colors.RESET}                    {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}╠══════════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")
        
        if self.current_sentiment:
            sentiment = self.current_sentiment
            technical = sentiment['technical']
            
            # Color coding for sentiment
            technical_color = self._get_sentiment_color(technical['sentiment'])
            
            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}📊 Technical:{Colors.RESET} {technical_color}{technical['sentiment']}{Colors.RESET} ({technical['confidence']:.1f}%)                                                       {Colors.CYAN}║{Colors.RESET}")
        else:
            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.RED}❌ Sentiment data unavailable{Colors.RESET}                                                      {Colors.CYAN}║{Colors.RESET}")
        
        # Add on-chain status line
        if self.onchain_data:
            onchain_status = self.onchain_data.get_aggregated_status()
            onchain_color = getattr(Colors, onchain_status['color'])
            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{Colors.WHITE}🔗 OnChain:{Colors.RESET} {onchain_color}{onchain_status['status_text']}{Colors.RESET}                                                            {Colors.CYAN}║{Colors.RESET}")
        
        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")
    
    def _render_trades_section(self):
        """Render recent trades section"""
        print(f"{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}                      {Colors.BOLD}{Colors.TURQUOISE}⚡ RECENT TRADES{Colors.RESET}                      {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}╠══════════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")
        
        if self.current_trades:
            for trade in self.current_trades[:10]:  # Show last 10 trades
                action_color = Colors.GREEN if trade['action'].upper() in ['BUY', 'LONG'] else Colors.RED
                
                # Format price with exponential notation for very small values
                if trade['price'] < 0.001:
                    price_str = f"{trade['price']:.2e}"
                else:
                    price_str = f"{trade['price']:.4f}"
                
                print(f"{Colors.CYAN}║{Colors.RESET} {Colors.WHITE}{trade['timestamp']}{Colors.RESET} | {action_color}{trade['action']:4}{Colors.RESET} {trade['amount']:12.2f} {trade['token']:8} @ {Colors.GREEN}${price_str:>8}{Colors.RESET} ({Colors.MAGENTA}${trade['usd_value']:8.2f}{Colors.RESET}) - {trade['agent']:15} {Colors.CYAN}║{Colors.RESET}")
        else:
            print(f"{Colors.CYAN}║{Colors.RESET} {Colors.RED}❌ No recent trades{Colors.RESET}                                                      {Colors.CYAN}║{Colors.RESET}")
        
        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")
    
    def _render_footer(self):
        """Render footer with status info"""
        # Use dynamic last update time if available, otherwise current time
        if hasattr(self, 'last_update_time') and self.last_update_time:
            last_update_time = self.last_update_time.strftime('%H:%M:%S')
        else:
            last_update_time = datetime.now().strftime('%H:%M:%S')
            
        current_hour = datetime.now().hour
        
        # Determine current mode
        is_market_hours = 9 <= current_hour <= 16
        mode = "🌅 MARKET HOURS" if is_market_hours else "🌙 OFF HOURS"
        
        print(f"{Colors.CYAN}⏰ Last Update: {Colors.WHITE}{last_update_time}{Colors.RESET} | {Colors.CYAN}🔄 Mode: {mode}{Colors.RESET} | {Colors.CYAN}⌨️  Ctrl+C to exit{Colors.RESET}")
    
    def _get_sentiment_color(self, sentiment: str) -> str:
        """Get color for sentiment display"""
        sentiment_upper = sentiment.upper()
        if 'BULLISH' in sentiment_upper or 'POSITIVE' in sentiment_upper:
            return Colors.GREEN
        elif 'BEARISH' in sentiment_upper or 'NEGATIVE' in sentiment_upper:
            return Colors.RED
        elif 'NEUTRAL' in sentiment_upper:
            return Colors.YELLOW
        else:
            return Colors.WHITE
    
    def update_data(self):
        """Update all data sources with improved error handling"""
        # Update portfolio data with fallback
        if self.portfolio_data:
            fresh_portfolio = self.portfolio_data.get_latest_portfolio()
            if fresh_portfolio:
                self.current_portfolio = fresh_portfolio
        
        # Update sentiment data
        if self.sentiment_data:
            try:
                self.current_sentiment = self.sentiment_data.get_latest_sentiment()
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️ Sentiment data fetch failed: {e}{Colors.RESET}")
        
        # Update trade data
        if self.trade_data:
            try:
                self.current_trades = self.trade_data.get_recent_trades(20)
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️ Trade data fetch failed: {e}{Colors.RESET}")
        
        self.last_update_time = datetime.now()
    
    def run(self):
        """Main dashboard loop with optimized refresh rates"""
        self.running = True
        
        # Load initial data silently before showing dashboard
        if self.portfolio_data:
            self.current_portfolio = self.portfolio_data.get_latest_portfolio()
        if self.sentiment_data:
            try:
                self.current_sentiment = self.sentiment_data.get_latest_sentiment()
            except Exception as e:
                debug(f"Initial sentiment load failed: {e}")
        if self.trade_data:
            try:
                self.current_trades = self.trade_data.get_recent_trades(10)
            except Exception as e:
                debug(f"Initial trade load failed: {e}")
                self.current_trades = []
        
        # Initialize last update time
        self.last_update_time = datetime.now()
        
        # Clear ALL screen content before showing dashboard
        self.clear_screen_windows_compatible()
        
        # Show initial dashboard display
        self.render_dashboard()
        
        # Main update loop with optimized timing
        last_update = {
            'portfolio': 0,
            'sentiment': 0,
            'trades': 0
        }
        
        # Track activity for smart updates
        last_trade_count = 0
        last_activity_time = time.time()
        
        try:
            debug("📊 Dashboard main loop started...")
            loop_count = 0
            while self.running:
                current_time = time.time()
                current_hour = datetime.now().hour
                loop_count += 1

                # Show heartbeat every 20 loops (less frequent)
                if loop_count % 20 == 0:
                    debug(f"💓 Dashboard heartbeat - Loop {loop_count}")
                
                # Smart timing based on market hours and activity
                is_market_hours = 9 <= current_hour <= 16
                time_since_activity = current_time - last_activity_time
                is_active = time_since_activity < 600  # 10 minutes
                
                # Dynamic refresh rates based on activity and market hours (BALANCED FOR DASHBOARD)
                if is_market_hours and is_active:
                    # Active trading hours - responsive but stable
                    portfolio_interval = 20   # 20 seconds (balanced)
                    trades_interval = 10      # 10 seconds (responsive)
                    sentiment_interval = 60   # 1 minute
                elif is_market_hours:
                    # Market hours but inactive - moderate updates
                    portfolio_interval = 30   # 30 seconds
                    trades_interval = 15      # 15 seconds
                    sentiment_interval = 120  # 2 minutes
                else:
                    # Off hours - slower updates
                    portfolio_interval = 60   # 1 minute
                    trades_interval = 30      # 30 seconds
                    sentiment_interval = 300  # 5 minutes
                
                # Update portfolio data (High Priority)
                if current_time - last_update['portfolio'] >= portfolio_interval:
                    if self.portfolio_data:
                        fresh_portfolio = self.portfolio_data.get_latest_portfolio()
                        if fresh_portfolio:
                            self.current_portfolio = fresh_portfolio
                            self.last_update_time = datetime.now()  # Update timestamp
                            # Always refresh the display
                            self.render_dashboard_incremental()
                    last_update['portfolio'] = current_time
                
                # Update trade data (High Priority - most time-sensitive)
                if current_time - last_update['trades'] >= trades_interval:
                    if self.trade_data:
                        try:
                            new_trades = self.trade_data.get_recent_trades(20)
                            self.current_trades = new_trades
                            self.last_update_time = datetime.now()  # Update timestamp
                            # Always refresh the display
                            self.render_dashboard_incremental()
                        except Exception as e:
                            debug(f"⚠️ Trade update failed: {e}")
                    last_update['trades'] = current_time
                
                # Update sentiment data (Low Priority - changes slowly)
                if current_time - last_update['sentiment'] >= sentiment_interval:
                    if self.sentiment_data:
                        try:
                            new_sentiment = self.sentiment_data.get_latest_sentiment()
                            self.current_sentiment = new_sentiment
                            self.last_update_time = datetime.now()  # Update timestamp
                            # Always refresh the display
                            self.render_dashboard_incremental()
                        except Exception as e:
                            debug(f"⚠️ Sentiment update failed: {e}")
                    last_update['sentiment'] = current_time
                
                # Adaptive sleep based on activity (balanced for responsiveness)
                sleep_time = 1.0 if is_active else 2.0  # 1-2 seconds for responsive updates
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.shutdown()

    def render_dashboard_incremental(self):
        """Render dashboard with reliable screen clearing"""
        # Use Windows-compatible screen clearing
        self.clear_screen_windows_compatible()

        # Re-render the complete dashboard
        self.print_banner()
        self._render_portfolio_section()
        print()
        self._render_trading_stats_section()
        print()
        self._render_market_analysis_section()
        print()
        self._render_positions_section()
        print()
        self._render_defi_positions_section()
        print()
        self._render_trades_section()
        print()
        self._render_footer()
    
    def shutdown(self):
        """Graceful shutdown"""
        self.running = False
        
        print(f"\n{Colors.CYAN}╔══════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}{Colors.TURQUOISE}🌙 Dashboard shutting down...{Colors.RESET}      {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}  {Colors.WHITE}Closing database connections...{Colors.RESET}     {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.RESET}  {Colors.WHITE}Thank you for using Anarcho Capital!{Colors.RESET}  {Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}╚══════════════════════════════════════╝{Colors.RESET}\n")
        
        # Close database connections
        self.db_manager.close_all()
        
        # Close cloud database connection if available
        if self.cloud_db_manager:
            try:
                self.cloud_db_manager.close_connection()
            except:
                pass
        
        sys.exit(0)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n{Colors.RED}🛑 Shutdown signal received...{Colors.RESET}")
    sys.exit(0)

def main():
    """Main entry point"""
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run dashboard
    dashboard = CyberpunkDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()
