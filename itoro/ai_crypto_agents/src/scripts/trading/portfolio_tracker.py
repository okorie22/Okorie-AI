"""
🌙 Anarcho Capital's Portfolio Tracker
Robust portfolio value tracking with historical data and accurate PnL calculations
Built with love by Anarcho Capital 🚀
"""

import threading
import time
import json
import os
import sqlite3
from typing import Dict, Optional, List, Tuple, Any, NamedTuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
# Local imports with fallback for relative imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
    from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
    from src import config
except ImportError:
    # Try relative imports when running from test directory
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
    from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
    try:
        import src.config as config
    except ImportError:
        # Final fallback - create a mock config object
        class MockConfig:
            def __getattr__(self, name):
                return None
        config = MockConfig()

# Cloud database import
try:
    from src.scripts.database.cloud_database import get_cloud_database_manager
    CLOUD_DB_AVAILABLE = True
except ImportError:
    CLOUD_DB_AVAILABLE = False

# Entry price tracker import
try:
    from src.scripts.database.entry_price_tracker import get_entry_price_tracker
    ENTRY_PRICE_TRACKER_AVAILABLE = True
except ImportError:
    ENTRY_PRICE_TRACKER_AVAILABLE = False

@dataclass
class PortfolioSnapshot:
    """Snapshot of portfolio value at a specific time"""
    timestamp: datetime
    total_value_usd: float
    usdc_balance: float
    sol_balance: float
    sol_value_usd: float
    positions_value_usd: float
    position_count: int
    sol_price: float = 0.0
    staked_sol_balance: float = 0.0
    staked_sol_value_usd: float = 0.0
    staked_sol_price: float = 0.0
    positions: Dict[str, Any] = field(default_factory=dict)  # token_address -> position_data (dict or float for backward compatibility)

@dataclass
class CapitalFlow:
    """Represents a capital inflow (deposit) or outflow (withdrawal)"""
    timestamp: datetime
    flow_type: str  # 'deposit' or 'withdrawal'
    amount_usd: float
    token_address: str  # The token that was deposited/withdrawn
    token_amount: float
    transaction_signature: str
    notes: Optional[str] = None

@dataclass
class PnLCalculation:
    """Enhanced PnL calculation that accounts for capital flows"""
    current_value: float
    start_value: float
    absolute_pnl: float
    percentage_pnl: float
    period_start: datetime
    period_end: datetime
    is_valid: bool
    error_message: Optional[str] = None
    # New fields for capital flow adjustments
    total_deposits: float = 0.0
    total_withdrawals: float = 0.0
    adjusted_pnl: float = 0.0  # PnL excluding capital flows
    adjusted_percentage_pnl: float = 0.0  # Percentage PnL excluding capital flows
    capital_flow_impact: float = 0.0  # How much capital flows affected the PnL

class PortfolioTracker:
    """
    Tracks portfolio value over time with accurate PnL calculations
    Provides reliable data for risk management and performance monitoring
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
        """Initialize the portfolio tracker"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Initialization mode - prevents agent triggers during startup
        self.initialization_mode = True
        self.initialization_complete_time = None
        
        # Database for historical data with connection management
        # Use distinct files for live vs paper trading to prevent data bleed
        try:
            db_name = 'portfolio_history_paper.db' if getattr(config, 'PAPER_TRADING_ENABLED', False) else 'portfolio_history_live.db'
            # Use data directory to match dashboard expectations
            self.db_path = os.path.join('data', db_name)
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        except Exception:
            # Fallback to src/data when running from test directory
            self.db_path = os.path.join('src', 'data', db_name)
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.db_connection_pool = []  # Connection pool for better management
        self.db_lock = threading.Lock()  # Lock for database operations
        
        # In-memory cache
        self.current_snapshot: Optional[PortfolioSnapshot] = None
        self.recent_snapshots: List[PortfolioSnapshot] = []
        self.snapshot_lock = threading.RLock()
        
        # Shared services
        self.data_coordinator = get_shared_data_coordinator()
        self.price_service = get_optimized_price_service()
        
        # Mark SOL as active trading token for real-time price updates
        self.price_service.mark_token_active(config.SOL_ADDRESS)
        
        # Risk agent registration
        self.risk_agent = None
        
        # Initialize peak portfolio value for drawdown calculations
        self.peak_portfolio_value = 0.0
        
        # Trading statistics tracking
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
        # AI analysis cooldown tracking
        self.ai_analysis_cooldowns = {}
        
        # Agent trigger cooldowns (event-driven with cooldowns)
        self.last_risk_trigger = 0
        self.last_harvesting_trigger = 0
        self.last_copybot_ai_trigger = 0
        
        # Entry price tracker for AI analysis
        if ENTRY_PRICE_TRACKER_AVAILABLE:
            self.entry_price_tracker = get_entry_price_tracker()
        else:
            self.entry_price_tracker = None
        
        # Configuration - read from config for CU optimization (adaptive to price service throttling)
        self.snapshot_interval_seconds = getattr(config, 'PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS', 60)
        self.cache_size = 1440  # Keep 24 hours of minute snapshots in memory
        self.adaptive_intervals_enabled = True  # Sync with price service throttling
        
        # Background tracking
        self.tracking_thread = None
        self.tracking_active = True
        
        # Agent triggering system removed - portfolio tracker only tracks data
        
        # Initialize logging
        info("📊 Portfolio Tracker initialized successfully")
    
    def register_risk_agent(self, risk_agent):
        """Register risk agent for portfolio change events"""
        self.risk_agent = risk_agent
        info("✅ Risk agent registered for portfolio events")
        
        # Initialize database
        self._init_database()
        
        # Check if auto-reset is enabled and perform reset
        self._check_and_perform_auto_reset()
        
        # Load initial state (including peak balance)
        self._load_initial_state()
        
        # Load peak balance from database
        self._load_peak_balance()
        
        # Start background tracking
        self._start_tracking_thread()
        
        info("Portfolio Tracker initialized with historical PnL tracking", file_only=True)
    
    def _get_db_connection(self):
        """Get database connection with proper management"""
        with self.db_lock:
            # Try to reuse existing connection
            if self.db_connection_pool:
                conn = self.db_connection_pool.pop()
                try:
                    # Test connection
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    # Connection is stale, create new one
                    pass
            
            # Create new connection
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            
            # Register connection with reset manager if it's a paper trading database
            if 'paper_trading.db' in self.db_path:
                try:
                    from src.scripts.database.database_reset_manager import get_database_reset_manager
                    manager = get_database_reset_manager()
                    manager.register_connection(conn)
                except ImportError:
                    pass  # Reset manager not available
            
            return conn
    
    def _return_db_connection(self, conn):
        """Return connection to pool for reuse"""
        if conn:
            # Unregister connection from reset manager if it's a paper trading database
            if 'paper_trading.db' in self.db_path:
                try:
                    from src.scripts.database.database_reset_manager import get_database_reset_manager
                    manager = get_database_reset_manager()
                    manager.unregister_connection(conn)
                except ImportError:
                    pass  # Reset manager not available
            
            with self.db_lock:
                if len(self.db_connection_pool) < 3:  # Limit pool size
                    self.db_connection_pool.append(conn)
                else:
                    conn.close()
    
    def _close_all_db_connections(self):
        """Close all database connections"""
        with self.db_lock:
            while self.db_connection_pool:
                conn = self.db_connection_pool.pop()
                try:
                    conn.close()
                except:
                    pass
    
    def _init_database(self):
        """Initialize SQLite database for historical data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create snapshots table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_value_usd REAL NOT NULL,
                    usdc_balance REAL NOT NULL,
                    sol_balance REAL NOT NULL,
                    sol_value_usd REAL NOT NULL,
                    positions_value_usd REAL NOT NULL,
                    staked_sol_balance REAL DEFAULT 0.0,
                    staked_sol_value_usd REAL DEFAULT 0.0,
                    position_count INTEGER NOT NULL,
                    positions_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add staked SOL columns if they don't exist (migration)
            try:
                cursor.execute('ALTER TABLE portfolio_snapshots ADD COLUMN staked_sol_balance REAL DEFAULT 0.0')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute('ALTER TABLE portfolio_snapshots ADD COLUMN staked_sol_value_usd REAL DEFAULT 0.0')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Add SOL price columns if they don't exist (migration)
            try:
                cursor.execute('ALTER TABLE portfolio_snapshots ADD COLUMN sol_price REAL DEFAULT 0.0')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute('ALTER TABLE portfolio_snapshots ADD COLUMN staked_sol_price REAL DEFAULT 0.0')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Create index for timestamp queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON portfolio_snapshots(timestamp)
            ''')
            
            # Create PnL tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pnl_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_timestamp TEXT NOT NULL,
                    end_timestamp TEXT NOT NULL,
                    start_value REAL NOT NULL,
                    end_value REAL NOT NULL,
                    absolute_pnl REAL NOT NULL,
                    percentage_pnl REAL NOT NULL,
                    period_hours REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create peak balance tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peak_balance_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peak_value REAL NOT NULL,
                    achieved_at TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create gain tracking table for harvesting agent
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gain_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    token_address TEXT NOT NULL,
                    gain_type TEXT NOT NULL,  -- 'realized' or 'unrealized'
                    gain_amount_usd REAL NOT NULL,
                    gain_percentage REAL NOT NULL,
                    position_value_usd REAL NOT NULL,
                    threshold_breached TEXT,  -- '20%', '70%', '150%'
                    harvested BOOLEAN DEFAULT FALSE,
                    reallocated BOOLEAN DEFAULT FALSE,
                    reallocation_strategy TEXT,  -- JSON string of allocation
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create harvesting history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS harvesting_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,  -- 'HARVEST_ALL', 'HARVEST_PARTIAL', etc.
                    total_gains_usd REAL NOT NULL,
                    realized_gains_usd REAL NOT NULL,
                    unrealized_gains_usd REAL NOT NULL,
                    ai_confidence REAL NOT NULL,
                    ai_reasoning TEXT,
                    reallocation_success BOOLEAN DEFAULT FALSE,
                    reallocation_details TEXT,  -- JSON string of reallocation results
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create staked SOL tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staked_sol_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    protocol TEXT NOT NULL,  -- 'marinade', 'jito', 'lido'
                    amount_sol REAL NOT NULL,
                    amount_usd REAL NOT NULL,
                    apy REAL,
                    status TEXT DEFAULT 'active',  -- 'active', 'unstaking', 'completed'
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create paper portfolio table for staked SOL tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS paper_portfolio (
                    token_address TEXT PRIMARY KEY,
                    amount REAL NOT NULL,
                    last_price REAL NOT NULL,
                    last_update INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_paper_portfolio_token 
                ON paper_portfolio(token_address)
            ''')
            
            # Create capital flows tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS capital_flows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    flow_type TEXT NOT NULL,  -- 'deposit' or 'withdrawal'
                    amount_usd REAL NOT NULL,
                    token_address TEXT NOT NULL,
                    token_amount REAL NOT NULL,
                    transaction_signature TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for gain tracking
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_gain_tracking_token 
                ON gain_tracking(token_address)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_gain_tracking_timestamp 
                ON gain_tracking(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_harvesting_history_timestamp 
                ON harvesting_history(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_staked_sol_protocol 
                ON staked_sol_tracking(protocol)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_capital_flows_timestamp 
                ON capital_flows(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_capital_flows_type 
                ON capital_flows(flow_type)
            ''')
            
            # Create closed trades table for wins/losses tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS closed_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    token_address TEXT NOT NULL,
                    token_symbol TEXT,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    amount REAL NOT NULL,
                    pnl_usd REAL NOT NULL,
                    pnl_percent REAL NOT NULL,
                    hold_time_seconds INTEGER NOT NULL,
                    trade_type TEXT NOT NULL,  -- 'paper' or 'live'
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create trading statistics table for consecutive wins/losses
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trading_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    consecutive_wins INTEGER DEFAULT 0,
                    consecutive_losses INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_losses INTEGER DEFAULT 0,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for closed trades
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_closed_trades_timestamp 
                ON closed_trades(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_closed_trades_token 
                ON closed_trades(token_address)
            ''')
            
            conn.commit()
            conn.close()
            
            debug("Portfolio database initialized successfully")
            
        except Exception as e:
            error(f"Error initializing portfolio database: {str(e)}")
    
    def force_refresh_portfolio_data(self):
        """Force refresh portfolio data from paper trading database (for testing)"""
        try:
            if config.PAPER_TRADING_ENABLED:
                # Clear current snapshot to force refresh
                with self.snapshot_lock:
                    self.current_snapshot = None
                
                # Force a new snapshot
                self._take_snapshot()
                debug("Forced portfolio data refresh from paper trading database")
                return True
            return False
        except Exception as e:
            error(f"Error forcing portfolio refresh: {e}")
            return False
    
    def take_testing_snapshot_with_dust(self):
        """Take a testing snapshot that includes dust positions (for testing only)"""
        try:
            if not config.PAPER_TRADING_ENABLED:
                warning("Testing snapshot with dust only available in paper trading mode")
                return None
            
            # Get current portfolio data including dust positions
            current_data = self._get_current_portfolio_data(include_dust_for_testing=True)
            if not current_data:
                return None
            
            # UNIFIED: Use the unified snapshot creation method
            snapshot = self._create_unified_snapshot(current_data)
            
            # Store snapshot temporarily for testing (don't save to database)
            with self.snapshot_lock:
                self.current_snapshot = snapshot
            
            debug("Created testing snapshot with dust positions included")
            return snapshot
            
        except Exception as e:
            error(f"Error taking testing snapshot with dust: {e}")
            return None
    
    def _batch_fetch_snapshot_prices(self, portfolio_data: dict) -> dict:
        """Get all prices needed for snapshot from cache (kept fresh by background monitoring)
        
        Args:
            portfolio_data: Dictionary containing portfolio tokens
            
        Returns:
            Dictionary mapping token addresses to prices
        """
        tokens_to_fetch = set([config.SOL_ADDRESS])
        
        # Collect all token addresses from portfolio
        if portfolio_data:
            for token_addr in portfolio_data.keys():
                if token_addr not in [config.USDC_ADDRESS] and token_addr != config.STAKED_SOL_TOKEN_ADDRESS:
                    tokens_to_fetch.add(token_addr)
        
        # Use cache that background monitoring keeps fresh (no API calls!)
        debug(f"💾 Getting cached prices for {len(tokens_to_fetch)} tokens (refreshed by background monitoring)")
        prices = self.price_service.get_prices(
            list(tokens_to_fetch), 
            force_fetch=False,  # Use cache - background monitoring keeps it fresh every 60s
            priority='high',
            agent_type='portfolio'
        )
        debug(f"✅ Retrieved {len([p for p in prices.values() if p])} cached prices (0 API calls)")
        return prices
    
    def _get_current_portfolio_data(self, include_dust_for_testing: bool = False):
        """Get current portfolio data for snapshot creation
        
        Args:
            include_dust_for_testing: If True, include dust positions in the snapshot (for testing only)
        """
        try:
            # Check if paper trading is enabled
            if config.PAPER_TRADING_ENABLED:
                # Use paper trading data instead of live wallet data
                debug("Using paper trading data for portfolio snapshot")
                
                # Import paper trading module
                try:
                    try:
                        from src import paper_trading
                    except ImportError:
                        # Try relative imports when running from test directory
                        import paper_trading
                    portfolio_df = paper_trading.get_paper_portfolio()
                    
                    if portfolio_df.empty:
                        info("Paper portfolio empty - seeding with initial 100% SOL")
                        paper_trading._set_initial_balances()
                        portfolio_df = paper_trading.get_paper_portfolio()
                        if portfolio_df.empty:
                            debug("No paper trading portfolio data available after seeding")
                            return None
                    
                    # Calculate balances from paper trading data
                    usdc_balance = 0.0
                    sol_balance = 0.0
                    staked_sol_balance = 0.0
                    positions_value_usd = 0.0
                    position_count = 0
                    positions = {}
                    
                    # Collect all tokens from portfolio for batch fetching
                    portfolio_tokens = {}
                    for _, row in portfolio_df.iterrows():
                        if row['amount'] > 0 and row['amount'] <= 1e12:  # Valid amounts only
                            portfolio_tokens[row['token_address']] = {
                                'amount': row['amount'],
                                'stored_price': row.get('last_price', 0)
                            }
                    
                    # Batch fetch all prices at once
                    all_prices = self._batch_fetch_snapshot_prices(portfolio_tokens)
                    sol_price = all_prices.get(config.SOL_ADDRESS, 0.0)
                    
                    if not sol_price or sol_price <= 0:
                        sol_price = 0.0
                    
                    for _, row in portfolio_df.iterrows():
                        token_address = row['token_address']
                        amount = row['amount']
                        
                        if amount <= 0:
                            continue
                        
                        # Add validation for unrealistic token amounts
                        if amount > 1e12:  # Reject amounts over 1 trillion tokens
                            debug(f"⚠️ Rejecting unrealistic token amount: {token_address[:8]}... = {amount:.2f}")
                            continue
                        
                        if token_address == config.USDC_ADDRESS:
                            usdc_balance = amount
                        elif token_address == config.SOL_ADDRESS:
                            sol_balance = amount
                        elif "STAKED_SOL" in token_address or token_address == "STAKED_SOL_So11111111111111111111111111111111111111112":
                            staked_sol_balance = amount
                            # Add staked SOL to positions for Individual Positions display
                            staked_sol_value = amount * sol_price
                            # Add to positions_value_usd for Portfolio Status display
                            positions_value_usd += staked_sol_value
                            position_count += 1
                            
                            # Add staked SOL to positions dict
                            positions[token_address] = {
                                'amount': float(amount),
                                'price': float(sol_price),
                                'value_usd': float(staked_sol_value),
                                'symbol': 'stSOL',
                                'name': 'Staked SOL',
                                'last_updated': datetime.now().isoformat()
                            }
                            continue
                        else:
                            # Use price from batch fetch
                            price = all_prices.get(token_address)
                            if not price or (isinstance(price, dict) or float(price) <= 0):
                                # Fallback to stored price if API fails
                                stored_price = row['last_price']
                                price = stored_price if stored_price and stored_price > 0 else 0.0
                            
                            debug(f"💾 Using batch-fetched price for {token_address[:8]}...: ${price:.6f}")
                            
                            # CRITICAL: Validate individual token price BEFORE calculating value
                            if price and price > 0:
                                # Layer 1: Individual price validation - reject unrealistic prices
                                if isinstance(price, (int, float)) and price > 100:  # Realistic max for altcoins
                                    debug(f"⚠️ Rejecting unrealistic price: {token_address[:8]}... = ${price:.6f}")
                                    # Use stored price instead
                                    stored_price = row['last_price']
                                    if stored_price and isinstance(stored_price, (int, float)) and stored_price > 0 and stored_price <= 100:
                                        price = stored_price
                                        debug(f"Using stored price: ${price:.6f}")
                                    else:
                                        continue  # Skip token entirely
                                
                                token_value = amount * price
                                
                                # Layer 2: Sanity check: reject values over $1M per token (likely API error)
                                if token_value > 1_000_000:
                                    debug(f"⚠️ Rejecting unrealistic token value: {token_address[:8]}... = ${token_value:.2f}")
                                    # Use stored price instead
                                    stored_price = row['last_price']
                                    if stored_price and stored_price > 0:
                                        price = stored_price
                                        token_value = amount * price
                                    else:
                                        continue  # Skip this token entirely
                                
                                if include_dust_for_testing or token_value >= config.DUST_THRESHOLD_USD:
                                    positions_value_usd += token_value
                                    position_count += 1
                                    
                                    # Fetch metadata for the token
                                    try:
                                        from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
                                        metadata_service = get_token_metadata_service()
                                        metadata = metadata_service.get_metadata(token_address)
                                        token_symbol = metadata.get('symbol', 'UNK') if metadata else 'UNK'
                                        token_name = metadata.get('name', 'Unknown') if metadata else 'Unknown'
                                    except:
                                        token_symbol = 'UNK'
                                        token_name = 'Unknown'
                                    
                                    positions[token_address] = {
                                        'amount': float(amount),
                                        'price': float(price),
                                        'value_usd': float(token_value),
                                        'symbol': str(token_symbol),
                                        'name': str(token_name),
                                        'last_updated': datetime.now().isoformat()
                                    }
                                    
                                    # Mark token as active for real-time price updates
                                    self.price_service.mark_token_active(token_address)
                    
                    # Use the SOL price we fetched earlier, or fallback to stored price if needed
                    if sol_price <= 0:
                        # Fallback to stored price
                        sol_stored_price = None
                        for _, sol_row in portfolio_df.iterrows():
                            if sol_row['token_address'] == config.SOL_ADDRESS:
                                sol_stored_price = sol_row['last_price']
                                break
                        sol_price = sol_stored_price if sol_stored_price and sol_stored_price > 0 else 200.0
                    
                    sol_value_usd = sol_balance * sol_price
                    staked_sol_value_usd = staked_sol_balance * sol_price
                    
                    # Calculate total value (staked SOL is already included in positions_value_usd)
                    total_value = usdc_balance + sol_value_usd + positions_value_usd
                    
                    # CRITICAL FIX: Log unrealistic portfolio values but preserve actual data for testing
                    # If total value exceeds $1M, log warning but keep actual values for testing
                    if total_value > 1_000_000:
                        warning(f"⚠️ Unrealistic portfolio value detected: ${total_value:.2f}")
                        warning(f"  USDC: ${usdc_balance:.2f}, SOL: ${sol_value_usd:.2f}, Staked SOL: ${staked_sol_value_usd:.2f}, Positions: ${positions_value_usd:.2f}")
                        warning(f"  This may be due to free API tier pricing issues. Consider upgrading to paid Birdeye API.")
                        warning(f"  Preserving actual values for testing purposes.")
                    
                    debug(f"Paper trading data: ${total_value:.2f} (USDC: ${usdc_balance:.2f}, SOL: ${sol_value_usd:.2f}, Staked SOL: ${staked_sol_value_usd:.2f}, Positions: ${positions_value_usd:.2f})")
                    
                    return {
                        'total_value_usd': total_value,
                        'usdc_balance': usdc_balance,
                        'sol_balance': sol_balance,
                        'sol_value_usd': sol_value_usd,
                        'sol_price': sol_price,
                        'staked_sol_balance': staked_sol_balance,
                        'staked_sol_value_usd': staked_sol_value_usd,
                        'staked_sol_price': sol_price,  # Same as SOL
                        'positions_value_usd': positions_value_usd,
                        'position_count': position_count,
                        'positions': positions
                    }
                    
                except ImportError:
                    error("Paper trading module not available")
                    return None
                except Exception as e:
                    error(f"Error getting paper trading data: {str(e)}")
                    return None
            
            # Original live trading logic
            wallet_data = self.data_coordinator.get_personal_wallet_data()
            
            if not wallet_data:
                debug("No wallet data available for snapshot")
                return None
            
            # Calculate balances
            usdc_balance = wallet_data.tokens.get(config.USDC_ADDRESS, 0.0)
            sol_balance = wallet_data.tokens.get(config.SOL_ADDRESS, 0.0)
            
            # Get staked SOL balance (if staking is enabled)
            staked_sol_balance = 0.0
            if hasattr(config, 'STAKED_SOL_TRACKING_ENABLED') and config.STAKED_SOL_TRACKING_ENABLED:
                staked_sol_balance = wallet_data.tokens.get(config.STAKED_SOL_TOKEN_ADDRESS, 0.0)
            
            # Batch fetch all prices for live wallet
            wallet_tokens = {}
            for token_address, balance in wallet_data.tokens.items():
                if (token_address not in [config.USDC_ADDRESS] and
                    token_address not in config.EXCLUDED_TOKENS and
                    token_address != config.STAKED_SOL_TOKEN_ADDRESS and
                    balance > 0):
                    wallet_tokens[token_address] = {'amount': balance, 'stored_price': 0}
            
            # Single batch fetch for all wallet prices
            all_prices = self._batch_fetch_snapshot_prices(wallet_tokens)
            sol_price = all_prices.get(config.SOL_ADDRESS, 0.0)
            
            if not sol_price or (isinstance(sol_price, dict) or float(sol_price) <= 0):
                error("❌ No valid SOL price available; aborting portfolio tracking")
                return None
            debug(f"💾 Using batch-fetched SOL price (live): ${sol_price:.6f}")
            sol_value_usd = sol_balance * sol_price
            staked_sol_value_usd = staked_sol_balance * sol_price
            
            # Calculate positions value
            positions_value_usd = 0.0
            position_count = 0
            positions = {}
            
            for token_address, balance in wallet_data.tokens.items():
                if (token_address not in [config.USDC_ADDRESS, config.SOL_ADDRESS] and
                    token_address not in config.EXCLUDED_TOKENS and
                    token_address != config.STAKED_SOL_TOKEN_ADDRESS and
                    balance > 0):
                    
                    price = all_prices.get(token_address)
                    if price and price > 0:
                        debug(f"💾 Using batch-fetched price for {token_address[:8]}... (live): ${price:.6f}")
                        token_value = balance * price
                        if token_value >= config.DUST_THRESHOLD_USD:
                            positions_value_usd += token_value
                            position_count += 1
                            
                            # Get token symbol dynamically (works for all tokens including small-caps)
                            try:
                                from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
                                metadata_service = get_token_metadata_service()
                                token_symbol = metadata_service.get_token_symbol(token_address)
                            except Exception:
                                token_symbol = token_address[:8] + '...'
                            
                            positions[token_address] = {
                                'amount': balance,
                                'price': price,
                                'value_usd': token_value,
                                'symbol': token_symbol,
                                'name': token_symbol,
                                'last_updated': datetime.now().isoformat()
                            }
                            
                            # Mark token as active for real-time price updates
                            self.price_service.mark_token_active(token_address)
            
            # Add staked SOL to positions if it exists
            if staked_sol_balance > 0:
                staked_sol_value = staked_sol_balance * sol_price
                # Add to positions_value_usd for Portfolio Status display
                positions_value_usd += staked_sol_value
                position_count += 1
                positions[config.STAKED_SOL_TOKEN_ADDRESS] = {
                    'amount': float(staked_sol_balance),
                    'price': float(sol_price),
                    'value_usd': float(staked_sol_value),
                    'symbol': 'stSOL',
                    'name': 'Staked SOL',
                    'last_updated': datetime.now().isoformat()
                }
            
            # Calculate total value (staked SOL is already included in positions_value_usd)
            total_value = usdc_balance + sol_value_usd + positions_value_usd
            
            debug(f"Live trading data: ${total_value:.2f} (USDC: ${usdc_balance:.2f}, SOL: ${sol_value_usd:.2f}, Staked SOL: ${staked_sol_value_usd:.2f}, Positions: ${positions_value_usd:.2f})")
            
            return {
                'total_value_usd': total_value,
                'usdc_balance': usdc_balance,
                'sol_balance': sol_balance,
                'sol_value_usd': sol_value_usd,
                'staked_sol_balance': staked_sol_balance,
                'staked_sol_value_usd': staked_sol_value_usd,
                'positions_value_usd': positions_value_usd,
                'position_count': position_count,
                'positions': positions
            }
            
        except Exception as e:
            error(f"Error getting current portfolio data: {str(e)}")
            return None
    
    def _check_and_perform_auto_reset(self):
        """Check config flags and perform auto-reset if enabled"""
        try:
            # Check if any reset flags are enabled
            should_reset = False
            reset_reason = ""
            
            if getattr(config, 'PORTFOLIO_RESET_ENABLED', False):
                should_reset = True
                reset_reason = "PORTFOLIO_RESET_ENABLED = True"
            
            if getattr(config, 'PAPER_TRADING_RESET_ON_START', False):
                should_reset = True
                reset_reason = "PAPER_TRADING_RESET_ON_START = True"
            
            if not should_reset:
                return
            
            info(f"🔄 Auto-reset triggered: {reset_reason}")
            
            # Use our clean reset system
            from src.scripts.database.database_reset_manager import reset_paper_trading_database
            success = reset_paper_trading_database()
            
            if success:
                info("✅ Auto-reset completed successfully")
            else:
                error("❌ Auto-reset failed")
                
        except Exception as e:
            error(f"Error during auto-reset: {str(e)}")
    
    def _load_initial_state(self):
        """Load initial state from database or create emergency snapshot"""
        try:
            # FOR PAPER TRADING: Read existing portfolio state to preserve allocations
            if config.PAPER_TRADING_ENABLED:
                debug("Paper trading mode: Reading existing portfolio state")
                
                # CRITICAL FIX: Read current portfolio from paper trading database
                # This preserves any existing allocation (including harvesting agent rebalancing)
                try:
                    from src.paper_trading import get_paper_portfolio
                    portfolio_df = get_paper_portfolio()
                    
                    if not portfolio_df.empty:
                        # Calculate portfolio values from DataFrame
                        total_value = 0.0
                        usdc_balance = 0.0
                        sol_balance = 0.0
                        sol_value_usd = 0.0
                        positions_value_usd = 0.0
                        position_count = 0
                        
                        # Process each position in the DataFrame
                        staked_sol_balance = 0.0
                        staked_sol_value_usd = 0.0
                        
                        for _, row in portfolio_df.iterrows():
                            token_address = row['token_address']
                            amount = row['amount']
                            price = row['last_price']
                            value = amount * price
                            total_value += value
                            
                            if token_address == config.USDC_ADDRESS:
                                usdc_balance = amount
                            elif token_address == config.SOL_ADDRESS:
                                sol_balance = amount
                                sol_value_usd = value
                            elif "STAKED_SOL" in token_address or token_address == "STAKED_SOL_So11111111111111111111111111111111111111112":
                                staked_sol_balance = amount
                                staked_sol_value_usd = value
                            else:
                                positions_value_usd += value
                                position_count += 1
                        
                        if total_value > 0:
                            # Use existing portfolio data to preserve allocation
                            debug(f"Using existing portfolio allocation: ${total_value:.2f}")
                            
                            current_snapshot = PortfolioSnapshot(
                                timestamp=datetime.now(),
                                total_value_usd=total_value,
                                usdc_balance=usdc_balance,
                                sol_balance=sol_balance,
                                sol_value_usd=sol_value_usd,
                                positions_value_usd=positions_value_usd,
                                position_count=position_count,
                                staked_sol_balance=staked_sol_balance,
                                staked_sol_value_usd=staked_sol_value_usd
                            )
                            
                            with self.snapshot_lock:
                                self.current_snapshot = current_snapshot
                                self.recent_snapshots = [current_snapshot]
                            
                            # Save to database
                            self._save_snapshot_to_db(current_snapshot)
                            debug("Portfolio tracker initialized with existing allocation")
                            return
                        else:
                            debug("No valid portfolio data found - will create initial state")
                    else:
                        debug("No existing portfolio data found - will create initial state")
                        
                except Exception as e:
                    debug(f"Could not read existing portfolio: {e} - will create initial state")
                
                # Only create initial state if no existing portfolio found
                debug("Creating initial paper trading state")
                initial_balance = 1000.0
                sol_price = self.price_service.get_price(config.SOL_ADDRESS) if hasattr(self, 'price_service') else None
                if not sol_price or (isinstance(sol_price, dict) or float(sol_price) <= 0):
                    sol_price = 150.0
                sol_amount = initial_balance / sol_price
                
                initial_snapshot = PortfolioSnapshot(
                    timestamp=datetime.now(),
                    total_value_usd=initial_balance,
                    usdc_balance=0.0,
                    sol_balance=sol_amount,
                    sol_value_usd=initial_balance,
                    positions_value_usd=0.0,
                    position_count=0
                )
                
                with self.snapshot_lock:
                    self.current_snapshot = initial_snapshot
                    self.recent_snapshots = [initial_snapshot]
                
                self._save_snapshot_to_db(initial_snapshot)
                info(f"Paper trading initial state created: ${initial_balance:.2f} (100% SOL: {sol_amount:.4f} SOL @ ${sol_price:.2f})")
                return
            
            # For live trading: fetch actual wallet data
            debug("Live trading mode: Fetching actual wallet data")
            
            # Get personal wallet data from shared coordinator
            wallet_data = self.data_coordinator.get_personal_wallet_data()
            
            if wallet_data and wallet_data.tokens:
                # Calculate actual balances from live wallet
                usdc_balance = wallet_data.tokens.get(config.USDC_ADDRESS, 0.0)
                sol_balance = wallet_data.tokens.get(config.SOL_ADDRESS, 0.0)
                
                # Batch fetch all prices for wallet tokens
                wallet_tokens = {}
                for token_address, balance in wallet_data.tokens.items():
                    if (token_address not in [config.USDC_ADDRESS] and
                        token_address not in config.EXCLUDED_TOKENS and
                        token_address != config.STAKED_SOL_TOKEN_ADDRESS and
                        balance > 0):
                        wallet_tokens[token_address] = {'amount': balance, 'stored_price': 0}
                
                all_prices = self._batch_fetch_snapshot_prices(wallet_tokens)
                sol_price = all_prices.get(config.SOL_ADDRESS, 205.0)
                sol_value_usd = sol_balance * sol_price
                
                # Calculate positions value
                positions_value_usd = 0.0
                position_count = 0
                positions = {}
                
                for token_address, balance in wallet_data.tokens.items():
                    if (token_address not in [config.USDC_ADDRESS, config.SOL_ADDRESS] and
                        token_address not in config.EXCLUDED_TOKENS and
                        token_address != config.STAKED_SOL_TOKEN_ADDRESS and
                        balance > 0):
                        
                        price = all_prices.get(token_address)
                        if price and price > 0:
                            token_value = balance * price
                            if token_value >= config.DUST_THRESHOLD_USD:
                                positions_value_usd += token_value
                                position_count += 1
                                positions[token_address] = token_value
                
                # Create snapshot with actual wallet data
                total_value = usdc_balance + sol_value_usd + positions_value_usd
                
                live_snapshot = PortfolioSnapshot(
                    timestamp=datetime.now(),
                    total_value_usd=total_value,
                    usdc_balance=usdc_balance,
                    sol_balance=sol_balance,
                    sol_value_usd=sol_value_usd,
                    positions_value_usd=positions_value_usd,
                    position_count=position_count,
                    staked_sol_balance=0.0,  # Live trading doesn't track staked SOL yet
                    staked_sol_value_usd=0.0,
                    positions=positions
                )
                
                with self.snapshot_lock:
                    self.current_snapshot = live_snapshot
                    self.recent_snapshots = [live_snapshot]
                
                # Save to database
                self._save_snapshot_to_db(live_snapshot)
                
                info(f"Live wallet state loaded: ${total_value:.2f} (USDC: ${usdc_balance:.2f}, SOL: {sol_balance:.4f} @ ${sol_price:.2f} = ${sol_value_usd:.2f}, Positions: ${positions_value_usd:.2f})")
                return
            else:
                # Fallback to database if wallet data unavailable
                latest_snapshot = self._get_latest_snapshot_from_db()
                
                if latest_snapshot:
                    # Validate the snapshot value
                    if latest_snapshot.total_value_usd > 1000000:  # Sanity check
                        warning(f"Corrupted portfolio value detected: ${latest_snapshot.total_value_usd:.2f}")
                        self._clear_paper_trading_history()
                        self._create_emergency_snapshot()
                        return
                    
                    with self.snapshot_lock:
                        self.current_snapshot = latest_snapshot
                        self.recent_snapshots = [latest_snapshot]
                        info(f"Loaded portfolio state from database: ${latest_snapshot.total_value_usd:.2f}")
                else:
                    self._create_emergency_snapshot()
                
        except Exception as e:
            error(f"Error loading initial state: {str(e)}")
            self._create_emergency_snapshot()

    def _clear_paper_trading_history(self):
        """Clear portfolio history for paper trading reset"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clear all portfolio-related tables
            cursor.execute("DELETE FROM portfolio_snapshots")
            cursor.execute("DELETE FROM pnl_tracking")
            cursor.execute("DELETE FROM gain_tracking")
            cursor.execute("DELETE FROM harvesting_history")
            cursor.execute("DELETE FROM staked_sol_tracking")
            cursor.execute("DELETE FROM capital_flows")
            
            # CRITICAL FIX: Also clear peak balance tracking to prevent false drawdown signals
            cursor.execute("DELETE FROM peak_balance_tracking")
            
            conn.commit()
            conn.close()
            
            # Reset in-memory state
            with self.snapshot_lock:
                self.recent_snapshots.clear()
                self.current_snapshot = None
                self.peak_portfolio_value = 0.0
            
            info("✅ Cleared all portfolio history and reset in-memory state")
            
        except Exception as e:
            error(f"Error clearing portfolio history: {str(e)}")
    
    def _create_emergency_snapshot(self):
        """Create emergency snapshot with minimal data"""
        try:
            # Use $0 for live trading, $1000 only for paper trading
            if config.PAPER_TRADING_ENABLED:
                emergency_value = 1000.0  # Paper trading fallback value
            else:
                emergency_value = 0.0  # Live trading fallback value
            
            self.current_snapshot = PortfolioSnapshot(
                timestamp=datetime.now(),
                total_value_usd=emergency_value,
                usdc_balance=emergency_value,
                sol_balance=0.0,
                sol_value_usd=0.0,
                positions_value_usd=0.0,
                position_count=0
            )
            
            warning(f"Created emergency portfolio snapshot with ${emergency_value:.2f} ({'paper trading' if config.PAPER_TRADING_ENABLED else 'live trading'} mode)")
            
        except Exception as e:
            error(f"Error creating emergency snapshot: {str(e)}")
    
    def _get_latest_snapshot_from_db(self) -> Optional[PortfolioSnapshot]:
        """Get the most recent snapshot from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, total_value_usd, usdc_balance, sol_balance,
                       sol_value_usd, sol_price, positions_value_usd, position_count, positions_json,
                       staked_sol_balance, staked_sol_value_usd, staked_sol_price
                FROM portfolio_snapshots
                ORDER BY timestamp DESC
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                positions = {}
                if row[7]:  # positions_json
                    try:
                        positions = json.loads(row[7])
                    except:
                        pass
                
                return PortfolioSnapshot(
                    timestamp=datetime.fromisoformat(row[0]),
                    total_value_usd=row[1],
                    usdc_balance=row[2],
                    sol_balance=row[3],
                    sol_value_usd=row[4],
                    positions_value_usd=row[5],
                    position_count=row[6],
                    sol_price=row[7] if len(row) > 7 else 0.0,
                    staked_sol_balance=row[9] if len(row) > 9 else 0.0,
                    staked_sol_value_usd=row[10] if len(row) > 10 else 0.0,
                    staked_sol_price=row[11] if len(row) > 11 else 0.0,
                    positions=positions
                )
            
            return None
            
        except Exception as e:
            error(f"Error loading latest snapshot from database: {str(e)}")
            return None
    
    def _start_tracking_thread(self):
        """Start background tracking thread"""
        if self.tracking_thread is None or not self.tracking_thread.is_alive():
            self.tracking_thread = threading.Thread(target=self._tracking_worker, daemon=True)
            self.tracking_thread.start()
    
    def _tracking_worker(self):
        """Background worker for periodic portfolio snapshots with adaptive intervals
        
        Automatically syncs with price service throttling - increases from 60s to 300s
        when CU limit is reached, then resets to 60s at midnight
        """
        while self.tracking_active:
            try:
                self._take_snapshot()
                
                # Get current interval from price service (adapts based on CU usage)
                current_interval = self._get_adaptive_interval()
                time.sleep(current_interval)
                
            except Exception as e:
                error(f"Error in portfolio tracking worker: {str(e)}")
                time.sleep(self._get_adaptive_interval())  # Use adaptive interval on error too
    
    def _get_adaptive_interval(self) -> int:
        """Get current snapshot interval, adapting to price service throttling status
        
        Returns:
            60 seconds normally, 300 seconds when price service is throttled
        """
        if not self.adaptive_intervals_enabled:
            return self.snapshot_interval_seconds
        
        try:
            # Check price service throttle status
            cu_status = self.price_service.get_cu_status()
            
            if cu_status.get('throttle_active', False):
                throttled_interval = cu_status.get('current_interval', 300)
                # Log throttle status change (only once per activation)
                if not hasattr(self, '_last_throttle_logged') or not self._last_throttle_logged:
                    info(f"📊 Portfolio snapshots adapting to CU throttling: {self.snapshot_interval_seconds}s → {throttled_interval}s")
                    self._last_throttle_logged = True
                return throttled_interval
            else:
                # Reset throttle log flag when back to normal
                if hasattr(self, '_last_throttle_logged') and self._last_throttle_logged:
                    info(f"✅ Portfolio snapshots restored to normal: {self.snapshot_interval_seconds}s")
                    self._last_throttle_logged = False
                return self.snapshot_interval_seconds
                
        except Exception as e:
            debug(f"Error getting adaptive interval: {str(e)}", file_only=True)
            return self.snapshot_interval_seconds  # Fallback to default
    
    def _take_snapshot(self):
        """Take a snapshot of current portfolio state and trigger agents if needed"""
        try:
            # Get current portfolio data
            current_data = self._get_current_portfolio_data()
            if not current_data:
                return
            
            # Create snapshot
            snapshot = PortfolioSnapshot(
                timestamp=datetime.now(),
                total_value_usd=current_data.get('total_value_usd', 0.0),
                usdc_balance=current_data.get('usdc_balance', 0.0),
                sol_balance=current_data.get('sol_balance', 0.0),
                sol_value_usd=current_data.get('sol_value_usd', 0.0),
                positions_value_usd=current_data.get('positions_value_usd', 0.0),
                position_count=current_data.get('position_count', 0),
                sol_price=current_data.get('sol_price', 0.0),
                staked_sol_balance=current_data.get('staked_sol_balance', 0.0),
                staked_sol_value_usd=current_data.get('staked_sol_value_usd', 0.0),
                staked_sol_price=current_data.get('staked_sol_price', 0.0),
                positions=current_data.get('positions', {})
            )
            
            # Store snapshot
            with self.snapshot_lock:
                self.current_snapshot = snapshot
                self.recent_snapshots.append(snapshot)
                
                # Maintain cache size
                if len(self.recent_snapshots) > self.cache_size:
                    self.recent_snapshots.pop(0)
            
            # Update peak portfolio value for drawdown calculations
            self.update_peak_balance(snapshot.total_value_usd)
                
            # Save snapshot to database
            self._save_snapshot_to_db(snapshot)
            
            # Check thresholds and trigger agents directly
            self._check_and_trigger_agents(snapshot)
            
            # 🌐 Save snapshot to cloud database for synchronization
            try:
                from src.scripts.database.cloud_database import get_cloud_database_manager
                db_manager = get_cloud_database_manager()
                if db_manager:
                    # Get detailed position data from local database for cloud sync
                    from src.paper_trading import get_paper_portfolio
                    local_portfolio = get_paper_portfolio()
                    
                    # Build detailed positions data using prices from snapshot (already fetched)
                    positions = {}
                    if snapshot.positions:
                        # Reuse prices from snapshot instead of refetching
                        for token_address, position_data in snapshot.positions.items():
                            if token_address not in ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"]:
                                positions[token_address] = {
                                    'amount': position_data.get('amount', 0),
                                    'price': position_data.get('price', 0),
                                    'value': position_data.get('value_usd', 0)
                                }
                    
                    # Prepare portfolio data for cloud database
                    portfolio_data = {
                        'total_value': snapshot.total_value_usd,
                        'usdc_balance': snapshot.usdc_balance,
                        'sol_balance': snapshot.sol_balance,
                        'sol_value_usd': snapshot.sol_value_usd,
                        'staked_sol_balance': snapshot.staked_sol_balance,
                        'staked_sol_value_usd': snapshot.staked_sol_value_usd,
                        'positions_value_usd': snapshot.positions_value_usd,
                        'change_detected': True,
                        'change_type': 'snapshot',
                        'positions': positions,  # Store positions directly
                        'metadata': {
                            'local_timestamp': snapshot.timestamp.isoformat(),
                            'position_count': snapshot.position_count,
                            'positions': positions  # Also store in metadata for compatibility
                        }
                    }
                    
                    # Save to cloud database
                    db_manager.save_paper_trading_portfolio(portfolio_data)
                    debug("✅ Portfolio snapshot saved to cloud database")
                    debug(f"📋 Portfolio change payload: {portfolio_data}")
                else:
                    debug("Cloud database not available - using local storage only")
            except Exception as e:
                warning(f"⚠️ Failed to save portfolio snapshot to cloud database: {e}")
            
            # Trigger webhook for external systems (webhook server)
            self._trigger_portfolio_change_webhook(snapshot)
            
        except Exception as e:
            error(f"Error taking portfolio snapshot: {e}")
    
    def update_portfolio_snapshot(self):
        """Update the current portfolio snapshot - public interface for agents"""
        try:
            self._take_snapshot()
            info("✅ Portfolio snapshot updated successfully")
            return True
        except Exception as e:
            error(f"❌ Error updating portfolio snapshot: {e}")
            return False
    
    def _trigger_portfolio_change_webhook(self, snapshot: PortfolioSnapshot):
        """Trigger webhook for portfolio changes to activate webhook server agents"""
        try:
            # Get portfolio data
            portfolio_data = {
                'type': 'portfolio_change_detected',
                'timestamp': time.time(),
                'portfolio_data': {
                    'total_value': snapshot.total_value_usd,
                    'usdc_balance': snapshot.usdc_balance,
                    'sol_balance': snapshot.sol_balance,
                    'sol_value_usd': snapshot.sol_value_usd,
                    'positions_value_usd': snapshot.positions_value_usd,
                    'change_detected': True
                }
            }
            
            # Send webhook to webhook server to trigger agents
            try:
                import requests
                response = requests.post(
                    "http://localhost:10000/webhook/portfolio-change",
                    json=portfolio_data,
                    timeout=5
                )
                if response.status_code == 200:
                    debug("📡 Portfolio change webhook sent to webhook server")
                    debug(f"📋 Portfolio change payload: {portfolio_data}")
                else:
                    warning(f"⚠️ Portfolio change webhook failed: {response.status_code}")
            except Exception as e:
                # This is expected when webhook server isn't running locally
                # It's only used for local testing - production uses Helius webhooks
                debug(f"📡 Portfolio change webhook note: Local server not running (expected in production)")
                
        except Exception as e:
            error(f"❌ Error triggering portfolio change webhook: {e}")
    
    
    
    
    def _save_snapshot_to_db(self, snapshot: PortfolioSnapshot):
        """Save snapshot to local database first, then sync to cloud database"""
        try:
            # PRIMARY: Save to local database first
            self._save_snapshot_to_local_db(snapshot)
            debug(f"✅ Portfolio snapshot saved to local database: ${snapshot.total_value_usd:.2f}")
            
            # SECONDARY: Try to sync to cloud database
            if CLOUD_DB_AVAILABLE:
                try:
                    db_manager = get_cloud_database_manager()
                    if db_manager is None:
                        warning("⚠️ Cloud database not configured (local data saved)")
                        return
                    
                    # Check if we're using REST API fallback
                    if hasattr(db_manager, '_test_connection') and hasattr(db_manager, 'save_paper_trading_portfolio'):
                        # Using REST API fallback - use REST API method
                        portfolio_data = {
                            'total_value_usd': snapshot.total_value_usd,
                            'usdc_balance': snapshot.usdc_balance,
                            'sol_balance': snapshot.sol_balance,
                            'sol_value_usd': snapshot.sol_value_usd,
                            'positions_value_usd': snapshot.positions_value_usd,
                            'position_count': snapshot.position_count,
                            'metadata': {
                                'position_count': snapshot.position_count,
                                'positions': snapshot.positions,
                                'timestamp': snapshot.timestamp.isoformat()
                            }
                        }
                        
                        success = db_manager.save_paper_trading_portfolio(portfolio_data)
                        if success:
                            debug(f"✅ Portfolio snapshot synced to cloud database via REST API: ${snapshot.total_value_usd:.2f}")
                        else:
                            raise Exception("REST API sync failed")
                    else:
                        # Using direct PostgreSQL - use execute_query
                        query = '''
                            INSERT INTO portfolio_history (
                                total_value_usd, usdc_balance, sol_balance, sol_value_usd,
                                positions_value_usd, change_detected, change_type, metadata
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        '''
                        
                        # Determine if change was detected
                        change_detected = False
                        change_type = None
                        if hasattr(self, 'previous_snapshot') and self.previous_snapshot:
                            if abs(snapshot.total_value_usd - self.previous_snapshot.total_value_usd) > 1.0:  # $1 threshold
                                change_detected = True
                                change_type = 'value_change'
                        
                        params = (
                            snapshot.total_value_usd,  # total_value_usd
                            snapshot.usdc_balance,  # usdc_balance
                            snapshot.sol_balance,  # sol_balance
                            snapshot.sol_value_usd,  # sol_value_usd
                            snapshot.positions_value_usd,  # positions_value_usd
                            change_detected,  # change_detected
                            change_type,  # change_type
                            json.dumps({
                                'position_count': snapshot.position_count,
                                'positions': snapshot.positions,
                                'timestamp': snapshot.timestamp.isoformat()
                            })  # metadata
                        )
                        
                        db_manager.execute_query(query, params, fetch=False)
                        debug(f"✅ Portfolio snapshot synced to cloud database via PostgreSQL: ${snapshot.total_value_usd:.2f}")
                    
                except Exception as cloud_error:
                    warning(f"⚠️ Cloud database sync failed (local data saved): {cloud_error}")
            
        except Exception as e:
            error(f"Error saving snapshot: {str(e)}")
    
    def _save_snapshot_to_local_db(self, snapshot: PortfolioSnapshot):
        """Fallback method to save snapshot to local database"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with self.db_lock:
                    conn = sqlite3.connect(self.db_path, timeout=20.0)
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO portfolio_snapshots 
                        (timestamp, total_value_usd, usdc_balance, sol_balance, 
                         sol_value_usd, sol_price, positions_value_usd, position_count, positions_json, 
                         staked_sol_balance, staked_sol_value_usd, staked_sol_price)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        snapshot.timestamp.isoformat(),
                        snapshot.total_value_usd,
                        snapshot.usdc_balance,
                        snapshot.sol_balance,
                        snapshot.sol_value_usd,
                        snapshot.sol_price,
                        snapshot.positions_value_usd,
                        snapshot.position_count,
                        json.dumps(snapshot.positions),
                        snapshot.staked_sol_balance,
                        snapshot.staked_sol_value_usd,
                        snapshot.staked_sol_price
                    ))
                    
                    conn.commit()
                    conn.close()
                    debug(f"📁 Portfolio snapshot saved to local database: ${snapshot.total_value_usd:.2f}")
                    return
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    error(f"Error saving snapshot after {max_retries} attempts: {e}")
                    return
            except Exception as e:
                error(f"Error saving snapshot to local database: {e}")
                return
    
    def get_current_portfolio_value(self) -> float:
        """Get current portfolio value with real-time update if needed"""
        try:
            with self.snapshot_lock:
                if self.current_snapshot is None:
                    debug("No current portfolio snapshot available")
                    # In webhook mode, don't trigger agents
                    if hasattr(self, 'webhook_mode') and self.webhook_mode:
                        # Use safe data collection without agent triggering
                        self._collect_portfolio_data_safely()
                    else:
                        self._take_snapshot()
                    
                if self.current_snapshot is None:
                    error("Failed to create portfolio snapshot")
                    return 0.0
                
                # Check if snapshot is too old (more than 5 minutes)
                if (datetime.now() - self.current_snapshot.timestamp).total_seconds() > 300:
                    debug("Portfolio snapshot is stale, taking fresh snapshot")
                    # In webhook mode, don't trigger agents
                    if hasattr(self, 'webhook_mode') and self.webhook_mode:
                        # Use safe data collection without agent triggering
                        self._collect_portfolio_data_safely()
                    else:
                        self._take_snapshot()
                
                return self.current_snapshot.total_value_usd if self.current_snapshot else 0.0
                
        except Exception as e:
            error(f"Error getting current portfolio value: {str(e)}")
            return 0.0
    
    def _collect_portfolio_data_safely(self):
        """Collect portfolio data without triggering agents (webhook mode safe)"""
        try:
            # Get current portfolio data without triggering agents
            current_data = self._get_current_portfolio_data()
            if not current_data:
                return
            
            # Create snapshot for data collection only
            snapshot = PortfolioSnapshot(
                timestamp=datetime.now(),
                total_value_usd=current_data.get('total_value_usd', 0.0),
                usdc_balance=current_data.get('usdc_balance', 0.0),
                sol_balance=current_data.get('sol_balance', 0.0),
                sol_value_usd=current_data.get('sol_value_usd', 0.0),
                positions_value_usd=current_data.get('positions_value_usd', 0.0),
                position_count=current_data.get('position_count', 0),
                staked_sol_balance=current_data.get('staked_sol_balance', 0.0),
                staked_sol_value_usd=current_data.get('staked_sol_value_usd', 0.0),
                positions=current_data.get('positions', {})
            )
            
            # Store snapshot for data collection only
            with self.snapshot_lock:
                self.current_snapshot = snapshot
                self.recent_snapshots.append(snapshot)
                
                # Maintain cache size
                if len(self.recent_snapshots) > self.cache_size:
                    self.recent_snapshots.pop(0)
            
            # Update peak portfolio value for drawdown calculations
            self.update_peak_balance(snapshot.total_value_usd)
                
            # Save snapshot to database
            self._save_snapshot_to_db(snapshot)
            
            # CRITICAL: NO agent triggering - only webhook for external systems
            self._trigger_portfolio_change_webhook(snapshot)
            
        except Exception as e:
            error(f"Error collecting portfolio data safely: {e}")
    
    def calculate_pnl_since_start(self) -> PnLCalculation:
        """Calculate PnL since the beginning of tracking"""
        try:
            current_value = self.get_current_portfolio_value()
            
            # FIXED: Handle empty portfolio case
            if current_value <= 0:
                # If portfolio is empty, reset start balance to 0 to avoid negative PnL
                return PnLCalculation(
                    current_value=0.0,
                    start_value=0.0,
                    absolute_pnl=0.0,
                    percentage_pnl=0.0,
                    period_start=datetime.now(),
                    period_end=datetime.now(),
                    is_valid=True,
                    error_message="Portfolio is empty - PnL reset to 0"
                )
            
            # Check if we're in paper trading mode
            if config.PAPER_TRADING_ENABLED:
                # For paper trading, use the configured initial balance
                start_value = config.PAPER_INITIAL_BALANCE
                start_timestamp = datetime.now() - timedelta(hours=1)  # Assume 1 hour ago for paper trading
            else:
                # For live trading, get the first snapshot from database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT timestamp, total_value_usd
                    FROM portfolio_snapshots
                    ORDER BY timestamp ASC
                    LIMIT 1
                ''')
                
                row = cursor.fetchone()
                conn.close()
                
                if not row:
                    # No historical data - use current value as start (no PnL change)
                    return PnLCalculation(
                        current_value=current_value,
                        start_value=current_value,
                        absolute_pnl=0.0,
                        percentage_pnl=0.0,
                        period_start=datetime.now(),
                        period_end=datetime.now(),
                        is_valid=True,
                        error_message="No historical data - using current value as baseline"
                    )
                
                start_timestamp = datetime.fromisoformat(row[0])
                start_value = row[1]
                
                # SANITY CHECK: If the start value is unreasonably high, reset it
                if start_value > current_value * 10:  # If start value is 10x current value
                    warning(f"Corrupted start value detected: ${start_value:.2f} vs current ${current_value:.2f}")
                    # This is likely paper trading residue - auto-clear the database
                    info("Auto-clearing corrupted paper trading data from database...")
                    self._clear_paper_trading_history()
                    # Reset to current value to avoid false PnL
                    start_value = current_value
                    start_timestamp = datetime.now()
            
            # Validate start value
            if start_value <= 0:
                return PnLCalculation(
                    current_value=current_value,
                    start_value=0.0,
                    absolute_pnl=0.0,
                    percentage_pnl=0.0,
                    period_start=start_timestamp,
                    period_end=datetime.now(),
                    is_valid=False,
                    error_message="Invalid start value (zero or negative)"
                )
            
            return self._calculate_pnl(start_value, current_value, start_timestamp, datetime.now())
            
        except Exception as e:
            error(f"Error calculating PnL since start: {str(e)}")
            current_value = self.get_current_portfolio_value()
            return PnLCalculation(
                current_value=current_value,
                start_value=0.0,
                absolute_pnl=0.0,
                percentage_pnl=0.0,
                period_start=datetime.now(),
                period_end=datetime.now(),
                is_valid=False,
                error_message=str(e)
            )
    
    def calculate_pnl_period(self, hours_back: int) -> PnLCalculation:
        """Calculate PnL for a specific time period"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)
            
            # Get snapshot closest to start time
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, total_value_usd
                FROM portfolio_snapshots
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                LIMIT 1
            ''', (start_time.isoformat(),))
            
            row = cursor.fetchone()
            
            if not row:
                # Try to get the latest available snapshot before the period
                cursor.execute('''
                    SELECT timestamp, total_value_usd
                    FROM portfolio_snapshots
                    WHERE timestamp < ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''', (start_time.isoformat(),))
                
                row = cursor.fetchone()
            
            conn.close()
            
            if not row:
                return PnLCalculation(
                    current_value=0.0,
                    start_value=0.0,
                    absolute_pnl=0.0,
                    percentage_pnl=0.0,
                    period_start=start_time,
                    period_end=end_time,
                    is_valid=False,
                    error_message=f"No data available for {hours_back} hour period"
                )
            
            actual_start_time = datetime.fromisoformat(row[0])
            start_value = row[1]
            current_value = self.get_current_portfolio_value()
            
            return self._calculate_pnl(start_value, current_value, actual_start_time, end_time)
            
        except Exception as e:
            error(f"Error calculating period PnL: {str(e)}")
            return PnLCalculation(
                current_value=0.0,
                start_value=0.0,
                absolute_pnl=0.0,
                percentage_pnl=0.0,
                period_start=datetime.now(),
                period_end=datetime.now(),
                is_valid=False,
                error_message=str(e)
            )
    
    def _calculate_pnl(self, start_value: float, current_value: float, 
                      start_time: datetime, end_time: datetime) -> PnLCalculation:
        """Calculate PnL between two values, accounting for capital flows"""
        try:
            if start_value <= 0:
                return PnLCalculation(
                    current_value=current_value,
                    start_value=start_value,
                    absolute_pnl=0.0,
                    percentage_pnl=0.0,
                    period_start=start_time,
                    period_end=end_time,
                    is_valid=False,
                    error_message="Start value is zero or negative"
                )
            
            # Get capital flows for this period
            total_deposits, total_withdrawals = self.get_total_capital_flows_since(start_time)
            
            # Calculate raw PnL (including capital flows)
            absolute_pnl = current_value - start_value
            percentage_pnl = (absolute_pnl / start_value) * 100 if start_value > 0 else 0.0
            
            # Calculate adjusted PnL (excluding capital flows)
            # Adjusted PnL = Current Value - Start Value - Deposits + Withdrawals
            # This shows the actual trading performance
            adjusted_pnl = current_value - start_value - total_deposits + total_withdrawals
            
            # Calculate adjusted percentage PnL
            adjusted_percentage_pnl = (adjusted_pnl / start_value) * 100 if start_value > 0 else 0.0
            
            # Calculate capital flow impact
            capital_flow_impact = total_deposits - total_withdrawals
            
            return PnLCalculation(
                current_value=current_value,
                start_value=start_value,
                absolute_pnl=absolute_pnl,
                percentage_pnl=percentage_pnl,
                period_start=start_time,
                period_end=end_time,
                is_valid=True,
                total_deposits=total_deposits,
                total_withdrawals=total_withdrawals,
                adjusted_pnl=adjusted_pnl,
                adjusted_percentage_pnl=adjusted_percentage_pnl,
                capital_flow_impact=capital_flow_impact
            )
            
        except Exception as e:
            return PnLCalculation(
                current_value=current_value,
                start_value=start_value,
                absolute_pnl=0.0,
                percentage_pnl=0.0,
                period_start=start_time,
                period_end=end_time,
                is_valid=False,
                error_message=str(e)
            )
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary"""
        try:
            current_value = self.get_current_portfolio_value()
            
            # Get PnL for different periods
            pnl_24h = self.calculate_pnl_period(24)
            pnl_7d = self.calculate_pnl_period(168)  # 7 days
            pnl_total = self.calculate_pnl_since_start()
            
            summary = {
                'current_value': current_value,
                'pnl_24h': {
                    'absolute': pnl_24h.absolute_pnl,
                    'percentage': pnl_24h.percentage_pnl,
                    'adjusted_absolute': pnl_24h.adjusted_pnl,
                    'adjusted_percentage': pnl_24h.adjusted_percentage_pnl,
                    'capital_flows': pnl_24h.total_deposits - pnl_24h.total_withdrawals,
                    'valid': pnl_24h.is_valid
                },
                'pnl_7d': {
                    'absolute': pnl_7d.absolute_pnl,
                    'percentage': pnl_7d.percentage_pnl,
                    'adjusted_absolute': pnl_7d.adjusted_pnl,
                    'adjusted_percentage': pnl_7d.adjusted_percentage_pnl,
                    'capital_flows': pnl_7d.total_deposits - pnl_7d.total_withdrawals,
                    'valid': pnl_7d.is_valid
                },
                'pnl_total': {
                    'absolute': pnl_total.absolute_pnl,
                    'percentage': pnl_total.percentage_pnl,
                    'adjusted_absolute': pnl_total.adjusted_pnl,
                    'adjusted_percentage': pnl_total.adjusted_percentage_pnl,
                    'total_deposits': pnl_total.total_deposits,
                    'total_withdrawals': pnl_total.total_withdrawals,
                    'capital_flow_impact': pnl_total.capital_flow_impact,
                    'valid': pnl_total.is_valid
                }
            }
            
            # Add current snapshot details if available
            if self.current_snapshot:
                summary.update({
                    'usdc_balance': self.current_snapshot.usdc_balance,
                    'sol_balance': self.current_snapshot.sol_balance,
                    'sol_value_usd': self.current_snapshot.sol_value_usd,
                    'positions_value_usd': self.current_snapshot.positions_value_usd,
                    'position_count': self.current_snapshot.position_count,
                    'last_update': self.current_snapshot.timestamp.isoformat()
                })

                # Backward-compatible aliases for existing consumers
                # sol_balance_usd is an alias of sol_value_usd
                summary['sol_balance_usd'] = summary.get('sol_value_usd', 0.0)
                # positions_value is an alias of positions_value_usd
                summary['positions_value'] = summary.get('positions_value_usd', 0.0)
            
            # Add total PnL for easy access
            if 'pnl_total' in summary and 'absolute' in summary['pnl_total']:
                summary['total_pnl'] = summary['pnl_total']['absolute']
            
            # Add peak balance for display
            summary['peak_balance'] = self.peak_portfolio_value
            
            # Add recent portfolio changes
            summary['recent_changes'] = self.get_recent_portfolio_changes()
            
            # Add recent agent executions
            summary['recent_executions'] = self.get_recent_agent_executions()
            
            return summary
            
        except Exception as e:
            error(f"Error getting portfolio summary: {str(e)}")
            return {
                'current_value': 0.0,
                'error': str(e)
            }

    def _load_peak_balance(self):
        """Load peak balance from database"""
        try:
            # CRITICAL FIX: For paper trading, always start with fresh peak balance
            if config.PAPER_TRADING_ENABLED:
                debug("Paper trading mode: Starting with fresh peak balance")
                self.peak_portfolio_value = 0.0
                return
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT peak_value FROM peak_balance_tracking 
                ORDER BY peak_value DESC LIMIT 1
            ''')
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0] > 0:
                self.peak_portfolio_value = float(row[0])
                # Quiet this log to avoid confusing live vs paper outputs
                debug(f"📈 Loaded peak balance from database: ${self.peak_portfolio_value:.2f}")
            else:
                # No peak balance in database, initialize with current value
                current_value = self.get_current_portfolio_value()
                if current_value > 0:
                    self.peak_portfolio_value = current_value
                    self._save_peak_balance(current_value)
                    info(f"📈 Initialized peak balance with current value: ${self.peak_portfolio_value:.2f}")
                
        except Exception as e:
            error(f"Error loading peak balance: {str(e)}")
    
    def _save_peak_balance(self, new_peak_value: float):
        """Save new peak balance to database"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with self.db_lock:
                    conn = sqlite3.connect(self.db_path, timeout=20.0)
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO peak_balance_tracking (peak_value, achieved_at, updated_at)
                        VALUES (?, ?, ?)
                    ''', (
                        new_peak_value,
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                    info(f"📈 New peak balance saved to database: ${new_peak_value:.2f}", file_only=True)
                    return
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    error(f"Error saving peak balance after {max_retries} attempts: {e}")
                    return
            except Exception as e:
                error(f"Error saving peak balance: {e}")
                return
    
    def update_peak_balance(self, new_value: float):
        """Update peak balance if new value is higher"""
        try:
            if new_value > self.peak_portfolio_value:
                old_peak = self.peak_portfolio_value
                self.peak_portfolio_value = new_value
                self._save_peak_balance(new_value)
                info(f"📈 New peak portfolio value: ${self.peak_portfolio_value:.2f} (was ${old_peak:.2f})", file_only=True)
                return True
            return False
        except Exception as e:
            error(f"Error updating peak balance: {str(e)}")
            return False

    def adjust_peak_balance_for_capital_flows(self, capital_flow_amount: float, flow_type: str):
        """Adjust peak balance when capital flows are detected to prevent false drawdown signals"""
        try:
            if flow_type == 'withdrawal':
                # When money is withdrawn, adjust peak balance down to prevent false drawdown
                # This assumes the withdrawal was from the peak balance
                adjusted_peak = max(0, self.peak_portfolio_value - abs(capital_flow_amount))
                if adjusted_peak < self.peak_portfolio_value:
                    old_peak = self.peak_portfolio_value
                    self.peak_portfolio_value = adjusted_peak
                    self._save_peak_balance(adjusted_peak)
                    info(f"📉 Adjusted peak balance for withdrawal: ${adjusted_peak:.2f} (was ${old_peak:.2f})")
                    return True
            elif flow_type == 'deposit':
                # When money is deposited, we don't need to adjust peak balance
                # The deposit will naturally increase the current value
                pass
            
            return False
        except Exception as e:
            error(f"Error adjusting peak balance for capital flows: {str(e)}")
            return False

    def get_adjusted_pnl_display(self) -> str:
        """Get PnL display string excluding capital flows (withdrawals/deposits)"""
        try:
            pnl_calc = self.calculate_pnl_since_start()
            if pnl_calc.is_valid:
                # Use adjusted PnL (excluding capital flows) for display
                if pnl_calc.adjusted_pnl >= 0:
                    return f"${pnl_calc.adjusted_pnl:.2f}"
                else:
                    return f"-${abs(pnl_calc.adjusted_pnl):.2f}"
            else:
                return "N/A"
        except Exception as e:
            error(f"Error getting adjusted PnL display: {e}")
            return "Error"

    def get_current_drawdown_percentage(self) -> float:
        """Get current drawdown percentage accounting for capital flows"""
        try:
            if self.peak_portfolio_value <= 0:
                return 0.0
            
            current_value = self.get_current_portfolio_value()
            
            # Get capital flows since peak was achieved
            # We need to find when the peak was achieved to calculate flows since then
            peak_time = self._get_peak_achieved_time()
            if peak_time and peak_time != "Unknown":
                try:
                    peak_datetime = datetime.fromisoformat(peak_time)
                    total_deposits, total_withdrawals = self.get_total_capital_flows_since(peak_datetime)
                    
                    # Calculate adjusted drawdown: (Current + Withdrawals - Deposits - Peak) / Peak
                    # This shows actual trading performance, not money movements
                    adjusted_current = current_value + total_withdrawals - total_deposits
                    adjusted_drawdown = (adjusted_current - self.peak_portfolio_value) / self.peak_portfolio_value
                    
                    debug(f"Drawdown calculation: Current ${current_value:.2f} + Withdrawals ${total_withdrawals:.2f} - Deposits ${total_deposits:.2f} = Adjusted ${adjusted_current:.2f}")
                    debug(f"Adjusted drawdown: {adjusted_drawdown:.2%} vs Raw drawdown: {(current_value - self.peak_portfolio_value) / self.peak_portfolio_value:.2%}")
                    
                    return min(0, adjusted_drawdown * 100)
                    
                except Exception as flow_error:
                    debug(f"Could not calculate capital flows for drawdown: {flow_error}, using raw calculation")
            
            # Fallback to raw calculation if capital flow calculation fails
            raw_drawdown = (current_value - self.peak_portfolio_value) / self.peak_portfolio_value
            return min(0, raw_drawdown * 100)
            
        except Exception as e:
            error(f"Error calculating drawdown percentage: {str(e)}")
            return 0.0
    
    def get_drawdown_breakdown(self) -> dict:
        """Get detailed breakdown of both raw and adjusted drawdown calculations"""
        try:
            if self.peak_portfolio_value <= 0:
                return {"error": "No peak balance set"}
            
            current_value = self.get_current_portfolio_value()
            raw_drawdown = (current_value - self.peak_portfolio_value) / self.peak_portfolio_value
            
            breakdown = {
                "current_value": current_value,
                "peak_value": self.peak_portfolio_value,
                "raw_drawdown_percentage": raw_drawdown * 100,
                "raw_drawdown_amount": current_value - self.peak_portfolio_value,
                "adjusted_drawdown_percentage": None,
                "adjusted_drawdown_amount": None,
                "capital_flows_since_peak": {
                    "deposits": 0.0,
                    "withdrawals": 0.0,
                    "net_impact": 0.0
                }
            }
            
            # Try to calculate adjusted drawdown
            peak_time = self._get_peak_achieved_time()
            if peak_time and peak_time != "Unknown":
                try:
                    peak_datetime = datetime.fromisoformat(peak_time)
                    total_deposits, total_withdrawals = self.get_total_capital_flows_since(peak_datetime)
                    
                    # If no capital flows found since peak, try to get all capital flows
                    # This handles the case where the peak was set before capital flows were recorded
                    if total_deposits == 0 and total_withdrawals == 0:
                        debug("No capital flows found since peak, checking all capital flows")
                        # Get all capital flows and use them for adjustment
                        all_flows = self.get_capital_flows_since(datetime.min)
                        total_deposits = sum(flow.amount_usd for flow in all_flows if flow.flow_type == 'deposit')
                        total_withdrawals = sum(flow.amount_usd for flow in all_flows if flow.flow_type == 'withdrawal')
                    
                    adjusted_current = current_value + total_withdrawals - total_deposits
                    adjusted_drawdown = (adjusted_current - self.peak_portfolio_value) / self.peak_portfolio_value
                    
                    breakdown["adjusted_drawdown_percentage"] = adjusted_drawdown * 100
                    breakdown["adjusted_drawdown_amount"] = adjusted_current - self.peak_portfolio_value
                    breakdown["capital_flows_since_peak"] = {
                        "deposits": total_deposits,
                        "withdrawals": total_withdrawals,
                        "net_impact": total_withdrawals - total_deposits
                    }
                    
                except Exception as e:
                    debug(f"Could not calculate adjusted drawdown: {e}")
            
            return breakdown
            
        except Exception as e:
            error(f"Error getting drawdown breakdown: {str(e)}")
            return {"error": str(e)}

    def get_portfolio_balances(self) -> Dict[str, Any]:
        """Return comprehensive portfolio balances including all token positions.

        Keys:
        - total_usd
        - usdc_balance
        - sol_balance
        - sol_value_usd
        - positions_value_usd
        - individual_positions (detailed token breakdown)
        """
        try:
            # Ensure we have a fresh-ish snapshot
            with self.snapshot_lock:
                snapshot = self.current_snapshot
            if snapshot is None:
                self._take_snapshot()
                with self.snapshot_lock:
                    snapshot = self.current_snapshot
            if snapshot is None:
                return {}

            # Get individual token positions with detailed data
            individual_positions = {}
            if snapshot.positions:
                try:
                    # Get current prices for all tokens
                    for token_address, position_data in snapshot.positions.items():
                        # Handle both dict and float formats
                        if isinstance(position_data, dict):
                            usd_value = position_data.get('value_usd', 0.0)
                        else:
                            usd_value = float(position_data) if position_data else 0.0
                        
                        # Validate usd_value is numeric
                        if not isinstance(usd_value, (int, float)):
                            error(f"Invalid usd_value type for {token_address}: {type(usd_value)}")
                            continue
                        
                        if usd_value > 0:
                            # Try to get token metadata and current price
                            try:
                                token_info = self.data_coordinator.get_token_info(token_address)
                                if token_info:
                                    token_symbol = token_info.get('symbol', token_address[:8])
                                    current_price = self.price_service.get_price(token_address, force_fetch=True, agent_type='portfolio', priority='high')
                                    
                                    if current_price and isinstance(current_price, (int, float)) and current_price > 0:
                                        token_amount = usd_value / current_price
                                        individual_positions[token_symbol] = {
                                            'address': token_address,
                                            'amount': token_amount,
                                            'price_usd': current_price,
                                            'value_usd': usd_value
                                        }
                                    else:
                                        # Fallback: just show USD value
                                        individual_positions[token_address[:8]] = {
                                            'address': token_address,
                                            'amount': 0,
                                            'price_usd': 0,
                                            'value_usd': usd_value
                                        }
                                else:
                                    # Fallback: just show USD value
                                    individual_positions[token_address[:8]] = {
                                        'address': token_address,
                                        'amount': 0,
                                        'price_usd': 0,
                                        'value_usd': usd_value
                                    }
                            except Exception as e:
                                # Fallback: just show USD value
                                individual_positions[token_address[:8]] = {
                                    'address': token_address,
                                    'amount': 0,
                                    'price_usd': 0,
                                    'value_usd': usd_value
                                }
                except Exception as e:
                    error(f"Error processing individual positions: {str(e)}")

            return {
                'total_usd': snapshot.total_value_usd,
                'usdc_balance': snapshot.usdc_balance,
                'sol_balance': snapshot.sol_balance,
                'sol_value_usd': snapshot.sol_value_usd,
                'positions_value_usd': snapshot.positions_value_usd,
                'individual_positions': individual_positions,
                'position_count': snapshot.position_count,
                'staked_sol_balance': snapshot.staked_sol_balance,
                'staked_sol_value_usd': snapshot.staked_sol_value_usd
            }
        except Exception as e:
            error(f"Error getting portfolio balances: {str(e)}")
            return {}
    
    def set_start_balance(self, start_balance: float):
        """Set a specific start balance for PnL calculations (for risk agent compatibility)"""
        try:
            # Create a synthetic start snapshot if needed
            start_time = datetime.now() - timedelta(seconds=1)
            
            synthetic_snapshot = PortfolioSnapshot(
                timestamp=start_time,
                total_value_usd=start_balance,
                usdc_balance=start_balance,
                sol_balance=0.0,
                sol_value_usd=0.0,
                positions_value_usd=0.0,
                position_count=0
            )
            
            self._save_snapshot_to_db(synthetic_snapshot)
            
            info(f"Set portfolio start balance to ${start_balance:.2f}")
            
        except Exception as e:
            error(f"Error setting start balance: {str(e)}")
    
    def reset_corrupted_pnl_data(self):
        """Reset corrupted PnL data by clearing old snapshots and setting current as baseline"""
        try:
            warning("Resetting corrupted PnL data...")
            
            # Clear old snapshots
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM portfolio_snapshots")
            conn.commit()
            conn.close()
            
            # Take fresh snapshot as baseline
            self._take_snapshot()
            
            info("✅ Corrupted PnL data reset successfully")
            
        except Exception as e:
            error(f"Error resetting corrupted PnL data: {str(e)}")

    def reset_peak_balance_to_current(self):
        """Reset peak balance to current value (useful after major withdrawals)"""
        try:
            current_value = self.get_current_portfolio_value()
            if current_value > 0:
                old_peak = self.peak_portfolio_value
                
                # Clear old peak balance from database first
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM peak_balance_tracking")
                conn.commit()
                conn.close()
                
                # Set new peak balance
                self.peak_portfolio_value = current_value
                self._save_peak_balance(current_value)
                
                info(f"🔄 Reset peak balance to current value: ${current_value:.2f} (was ${old_peak:.2f})")
                info("🗑️ Cleared old peak balance from database")
                return True
            return False
        except Exception as e:
            error(f"Error resetting peak balance: {str(e)}")
            return False
    
    def force_reset_peak_balance(self):
        """Force reset peak balance to current value and clear database"""
        try:
            current_value = self.get_current_portfolio_value()
            if current_value > 0:
                old_peak = self.peak_portfolio_value
                
                # Clear the peak balance table completely
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM peak_balance_tracking")
                conn.commit()
                conn.close()
                
                # Set new peak balance
                self.peak_portfolio_value = current_value
                self._save_peak_balance(current_value)
                
                info(f"🔄 Force reset peak balance to current value: ${current_value:.2f} (was ${old_peak:.2f})")
                info("🗑️ Cleared all peak balance history from database")
                
                # Also clear any corrupted PnL data that might be causing issues
                try:
                    cursor.execute("DELETE FROM pnl_tracking")
                    conn.commit()
                    info("🗑️ Also cleared PnL tracking data")
                except Exception as pnl_error:
                    debug(f"Could not clear PnL tracking: {pnl_error}")
                
                return True
            return False
        except Exception as e:
            error(f"Error force resetting peak balance: {str(e)}")
            return False
    
    def set_peak_balance_manually(self, new_peak_value: float):
        """Manually set peak balance to a specific value (for corrections)"""
        try:
            if new_peak_value < 0:
                error("Peak balance cannot be negative")
                return False
            
            old_peak = self.peak_portfolio_value
            self.peak_portfolio_value = new_peak_value
            self._save_peak_balance(new_peak_value)
            info(f"🔧 Manually set peak balance to: ${new_peak_value:.2f} (was ${old_peak:.2f})")
            return True
            
        except Exception as e:
            error(f"Error manually setting peak balance: {str(e)}")
            return False
    
    def get_peak_balance_info(self) -> str:
        """Get detailed information about peak balance and drawdown"""
        try:
            current_value = self.get_current_portfolio_value()
            if self.peak_portfolio_value <= 0:
                return "❌ No peak balance set"
            
            drawdown = self.get_current_drawdown_percentage()
            
            info = f"""
📈 **Peak Balance Information**
• Current Portfolio Value: ${current_value:.2f}
• Peak Portfolio Value: ${self.peak_portfolio_value:.2f}
• Current Drawdown: {drawdown:.2f}%
• Peak Achieved: {self._get_peak_achieved_time()}

💡 **Analysis**
• Portfolio is ${current_value - self.peak_portfolio_value:.2f} below peak
• If you've made withdrawals, this drawdown may be misleading
• Use 'reset_peak_balance_to_current()' if peak is incorrect
"""
            return info
            
        except Exception as e:
            return f"❌ Error getting peak balance info: {str(e)}"
    
    def _get_peak_achieved_time(self) -> str:
        """Get when the peak balance was achieved"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT achieved_at FROM peak_balance_tracking 
                WHERE peak_value = ? ORDER BY achieved_at DESC LIMIT 1
            ''', (self.peak_portfolio_value,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0]
            else:
                return "Unknown"
                
        except Exception as e:
            return "Unknown"

    def analyze_capital_flows_impact(self) -> dict:
        """Analyze the impact of capital flows on portfolio performance"""
        try:
            pnl_calc = self.calculate_pnl_since_start()
            if not pnl_calc.is_valid:
                return {"error": "Invalid PnL calculation"}
            
            analysis = {
                "raw_pnl": pnl_calc.absolute_pnl,
                "adjusted_pnl": pnl_calc.adjusted_pnl,
                "capital_flow_impact": pnl_calc.capital_flow_impact,
                "total_deposits": pnl_calc.total_deposits,
                "total_withdrawals": pnl_calc.total_withdrawals,
                "trading_performance": pnl_calc.adjusted_pnl,
                "money_moved": pnl_calc.total_deposits + pnl_calc.total_withdrawals,
                "start_value": pnl_calc.start_value,
                "current_value": pnl_calc.current_value,
                "peak_value": self.peak_portfolio_value
            }
            
            # Calculate percentages
            if pnl_calc.start_value > 0:
                analysis["raw_pnl_percentage"] = pnl_calc.percentage_pnl
                analysis["adjusted_pnl_percentage"] = pnl_calc.adjusted_percentage_pnl
                analysis["capital_flow_percentage"] = (pnl_calc.capital_flow_impact / pnl_calc.start_value) * 100
            
            return analysis
            
        except Exception as e:
            error(f"Error analyzing capital flows impact: {str(e)}")
            return {"error": str(e)}
    
    def get_detailed_pnl_breakdown(self) -> str:
        """Get a detailed breakdown of PnL calculations for debugging"""
        try:
            pnl_calc = self.calculate_pnl_since_start()
            if not pnl_calc.is_valid:
                return f"❌ PnL calculation invalid: {pnl_calc.error_message}"
            
            breakdown = f"""
📊 **Detailed PnL Breakdown**
• Current Portfolio Value: ${pnl_calc.current_value:.2f}
• Start Portfolio Value: ${pnl_calc.start_value:.2f}
• Peak Portfolio Value: ${self.peak_portfolio_value:.2f}

💰 **Raw PnL (including capital flows)**
• Absolute: ${pnl_calc.absolute_pnl:.2f}
• Percentage: {pnl_calc.percentage_pnl:.2f}%

🔄 **Adjusted PnL (excluding capital flows)**
• Absolute: ${pnl_calc.adjusted_pnl:.2f}
• Percentage: {pnl_calc.adjusted_percentage_pnl:.2f}%

💸 **Capital Flows Impact**
• Total Deposits: ${pnl_calc.total_deposits:.2f}
• Total Withdrawals: ${pnl_calc.total_withdrawals:.2f}
• Net Impact: ${pnl_calc.capital_flow_impact:.2f}

📈 **What This Means**
• Raw PnL shows total portfolio change: ${pnl_calc.absolute_pnl:.2f}
• Adjusted PnL shows trading performance: ${pnl_calc.adjusted_pnl:.2f}
• Risk management should use ADJUSTED PnL: ${pnl_calc.adjusted_pnl:.2f}
"""
            return breakdown
            
        except Exception as e:
            return f"❌ Error getting PnL breakdown: {str(e)}"
    
    def stop(self):
        """Stop portfolio tracking with proper resource cleanup"""
        info("Stopping portfolio tracking...")
        
        # Stop background tracking
        self.tracking_active = False
        
        # Wait for tracking thread to finish
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(timeout=10)  # Increased timeout
            if self.tracking_thread.is_alive():
                warning("Portfolio tracking thread did not stop gracefully")
        
        # Take final snapshot before shutdown
        try:
            final_snapshot = self._take_snapshot()
            if final_snapshot:
                info("Final portfolio snapshot saved before shutdown")
        except Exception as e:
            warning(f"Could not save final snapshot: {str(e)}")
        
        # Close all database connections
        self._close_all_db_connections()
        
        # Clear caches
        with self.snapshot_lock:
            self.recent_snapshots.clear()
            self.current_snapshot = None
        
        info("Portfolio tracking stopped with full cleanup")

    def update_pnl(self):
        """Update PnL calculations"""
        try:
            # Calculate PnL using existing methods
            pnl_calc = self.calculate_pnl_since_start()
            
            if pnl_calc.is_valid:
                info(f"Current PnL: {pnl_calc.percentage_pnl:.2f}%")
                return pnl_calc.percentage_pnl
            else:
                warning(f"Could not calculate PnL: {pnl_calc.error_message}")
                return 0.0
                
        except Exception as e:
            error(f"Error updating PnL: {e}")
            return 0.0

 

    def record_capital_flow(self, flow_type: str, amount_usd: float, token_address: str, 
                           token_amount: float, transaction_signature: str, notes: Optional[str] = None) -> bool:
        """Record a capital flow (deposit or withdrawal)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO capital_flows 
                (timestamp, flow_type, amount_usd, token_address, token_amount, transaction_signature, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                flow_type,
                amount_usd,
                token_address,
                token_amount,
                transaction_signature,
                notes,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            info(f"✅ Recorded capital flow: {flow_type} ${amount_usd:.2f} of {token_address[:8]}...")
            return True
            
        except Exception as e:
            error(f"❌ Error recording capital flow: {str(e)}")
            return False

    def get_capital_flows_since(self, start_time: datetime) -> List[CapitalFlow]:
        """Get all capital flows since a specific time"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, flow_type, amount_usd, token_address, token_amount, 
                       transaction_signature, notes
                FROM capital_flows
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            ''', (start_time.isoformat(),))
            
            flows = []
            for row in cursor.fetchall():
                flow = CapitalFlow(
                    timestamp=datetime.fromisoformat(row[0]),
                    flow_type=row[1],
                    amount_usd=row[2],
                    token_address=row[3],
                    token_amount=row[4],
                    transaction_signature=row[5],
                    notes=row[6]
                )
                flows.append(flow)
            
            conn.close()
            return flows
            
        except Exception as e:
            error(f"❌ Error getting capital flows: {str(e)}")
            return []

    def get_total_capital_flows_since(self, start_time: datetime) -> Tuple[float, float]:
        """Get total deposits and withdrawals since a specific time"""
        flows = self.get_capital_flows_since(start_time)
        
        total_deposits = sum(flow.amount_usd for flow in flows if flow.flow_type == 'deposit')
        total_withdrawals = sum(flow.amount_usd for flow in flows if flow.flow_type == 'withdrawal')
        
        return total_deposits, total_withdrawals

    def detect_and_record_capital_flows(self, transaction_data: dict) -> bool:
        """Detect and record capital flows from webhook transaction data"""
        try:
            if not transaction_data or 'transfers' not in transaction_data:
                return False
            
            personal_wallet = config.address
            flows_recorded = 0
            
            for transfer in transaction_data['transfers']:
                from_account = transfer.get('fromUserAccount', '')
                to_account = transfer.get('toUserAccount', '')
                token_mint = transfer.get('tokenMint', '')
                amount = float(transfer.get('amount', 0))
                decimals = int(transfer.get('decimals', 9))
                signature = transfer.get('signature', '')
                
                # Convert raw amount to human-readable amount
                token_amount = amount / (10 ** decimals)
                
                # Get token price for USD calculation
                try:
                    try:
                        from src.nice_funcs import token_price
                    except ImportError:
                        # Try relative imports when running from test directory
                        from src.nice_funcs import token_price
                    price = token_price(token_mint)
                    amount_usd = token_amount * price
                except:
                    # If price lookup fails, skip this transfer
                    continue
                
                # Detect deposits (external wallet -> personal wallet)
                if to_account == personal_wallet and from_account != personal_wallet and from_account != 'unknown':
                    if self.record_capital_flow('deposit', amount_usd, token_mint, token_amount, signature, 
                                             f"Deposit from {from_account[:8]}..."):
                        flows_recorded += 1
                        info(f"💰 Detected deposit: {token_amount:.6f} {token_mint[:8]}... (${amount_usd:.2f})")
                
                # Detect withdrawals (personal wallet -> external wallet)
                elif from_account == personal_wallet and to_account != personal_wallet and to_account != 'unknown':
                    if self.record_capital_flow('withdrawal', amount_usd, token_mint, token_amount, signature,
                                             f"Withdrawal to {to_account[:8]}..."):
                        flows_recorded += 1
                        info(f"💸 Detected withdrawal: {token_amount:.6f} {token_mint[:8]}... (${amount_usd:.2f})")
                        
                        # Adjust peak balance to prevent false drawdown signals
                        self.adjust_peak_balance_for_capital_flows(amount_usd, 'withdrawal')
            
            if flows_recorded > 0:
                info(f"✅ Recorded {flows_recorded} capital flow(s) from transaction")
                return True
            
            return False
        
        except Exception as e:
            error(f"❌ Error detecting capital flows: {str(e)}")
            return False

    def get_recent_portfolio_changes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent portfolio changes for display"""
        try:
            # Get recent snapshots to detect changes
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get last 20 snapshots to analyze for changes
            cursor.execute('''
                SELECT timestamp, total_value_usd, usdc_balance, sol_balance, sol_value_usd, positions_value_usd
                FROM portfolio_snapshots
                ORDER BY timestamp DESC
                LIMIT 20
            ''')
            
            snapshots = cursor.fetchall()
            conn.close()
            
            if len(snapshots) < 2:
                return []
            
            changes = []
            previous_snapshot = None
            
            for snapshot_data in snapshots:
                timestamp, total_value, usdc_bal, sol_bal, sol_value, positions_value = snapshot_data
                snapshot_time = datetime.fromisoformat(timestamp)
                
                if previous_snapshot is not None:
                    # Calculate changes
                    prev_total, prev_usdc, prev_sol, prev_sol_value, prev_positions = previous_snapshot
                    
                    # Total value change
                    total_change = total_value - prev_total
                    if abs(total_change) > 0.01:  # Only show significant changes (>$0.01)
                        if total_change > 0:
                            change_type = "Portfolio Gain"
                            change_category = "Total Portfolio"
                        else:
                            change_type = "Portfolio Loss"
                            change_category = "Total Portfolio"
                        
                        changes.append({
                            'type': change_type,
                            'amount': abs(total_change),
                            'timestamp': snapshot_time.strftime('%H:%M:%S'),
                            'category': change_category,
                            'description': f"Overall portfolio value {'increased' if total_change > 0 else 'decreased'}"
                        })
                    
                    # SOL value change
                    sol_change = sol_value - prev_sol_value
                    if abs(sol_change) > 0.01:
                        if sol_change > 0:
                            change_type = "SOL Price Gain"
                            change_category = "SOL Holdings"
                        else:
                            change_type = "SOL Price Loss"
                            change_category = "SOL Holdings"
                        
                        changes.append({
                            'type': change_type,
                            'amount': abs(sol_change),
                            'timestamp': snapshot_time.strftime('%H:%M:%S'),
                            'category': change_category,
                            'description': f"SOL value {'increased' if sol_change > 0 else 'decreased'} due to price movement"
                        })
                    
                    # Positions value change
                    positions_change = positions_value - prev_positions
                    if abs(positions_change) > 0.01:
                        if positions_change > 0:
                            change_type = "Token Positions Gain"
                            change_category = "Token Holdings"
                        else:
                            change_type = "Token Positions Loss"
                            change_category = "Token Holdings"
                        
                        changes.append({
                            'type': change_type,
                            'amount': abs(positions_change),
                            'timestamp': snapshot_time.strftime('%H:%M:%S'),
                            'category': change_category,
                            'description': f"Token positions value {'increased' if positions_change > 0 else 'decreased'} due to price movement"
                        })
                
                previous_snapshot = (total_value, usdc_bal, sol_bal, sol_value, positions_value)
            
            # Sort by timestamp (most recent first) and limit results
            changes.sort(key=lambda x: x['timestamp'], reverse=True)
            return changes[:limit]
            
        except Exception as e:
            error(f"Error getting recent portfolio changes: {str(e)}")
            return []

    def get_recent_agent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent agent executions for display"""
        try:
            try:
                from src.scripts.database.execution_tracker import get_execution_tracker
            except ImportError:
                # Try relative imports when running from test directory
                from src.scripts.database.execution_tracker import get_execution_tracker
            
            execution_tracker = get_execution_tracker()
            executions = execution_tracker.get_executions(limit=limit)
            
            if not executions:
                return []
            
            formatted_executions = []
            for execution in executions:
                # Format the execution for display
                agent_type = execution.get('agent_type', 'Unknown').title()
                action = execution.get('action', 'Unknown').upper()
                token_mint = execution.get('token_mint', 'Unknown')
                amount = execution.get('amount', 0)
                price = execution.get('price', 0)
                usd_value = execution.get('usd_value', 0)
                timestamp = execution.get('timestamp', 0)
                status = execution.get('status', 'Unknown')
                
                # Format token display
                if token_mint and token_mint != 'Unknown':
                    if len(token_mint) > 12:
                        token_display = f"{token_mint[:8]}...{token_mint[-4:]}"
                    else:
                        token_display = token_mint
                else:
                    token_display = "Unknown"
                
                # Format amount and price
                if amount and amount > 0:
                    amount_str = f"{amount:.4f}"
                else:
                    amount_str = "N/A"
                    
                if price and price > 0:
                    price_str = f"${price:.6f}"
                else:
                    price_str = "N/A"
                
                # Format timestamp
                try:
                    exec_time = datetime.fromtimestamp(timestamp)
                    time_str = exec_time.strftime('%H:%M:%S')
                except:
                    time_str = "Unknown"
                
                # Create display string
                if action in ['BUY', 'SELL']:
                    display_str = f"{action} {token_display} {amount_str} @ {price_str}"
                elif action in ['STAKE', 'UNSTAKE']:
                    display_str = f"{action} {token_display} {amount_str}"
                elif action in ['TRANSFER', 'SWAP']:
                    display_str = f"{action} {token_display} {amount_str}"
                else:
                    display_str = f"{action} {token_display}"
                
                formatted_executions.append({
                    'display': display_str,
                    'agent': agent_type,
                    'action': action,
                    'amount': amount,
                    'price': price,
                    'usd_value': usd_value,
                    'timestamp': time_str,
                    'status': status,
                    'raw_data': execution
                })
            
            return formatted_executions
            
        except Exception as e:
            error(f"Error getting recent agent executions: {str(e)}")
            return []

    def add_staked_sol_position(self, wallet_address: str, protocol: str, amount_sol: float, 
                               usd_value: float, apy: float, token_address: str, symbol: str):
        """Add or update a staked SOL position in the portfolio tracker"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with self._lock:
                    # Get database connection with increased timeout
                    db_path = os.path.join('data', 'portfolio_history_paper.db')
                    conn = sqlite3.connect(db_path, timeout=20.0)
                    cursor = conn.cursor()
                    
                    # Insert or update staked SOL position (using existing schema)
                    cursor.execute('''
                        INSERT OR REPLACE INTO staked_sol_tracking 
                        (timestamp, protocol, amount_sol, amount_usd, apy, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        datetime.now().isoformat(),
                        protocol,
                        amount_sol,
                        usd_value,  # Using usd_value as amount_usd
                        apy,
                        'active'
                    ))
                    
                    # Also add to paper portfolio if in paper trading mode
                    if hasattr(config, 'PAPER_TRADING_ENABLED') and config.PAPER_TRADING_ENABLED:
                        cursor.execute('''
                            INSERT OR REPLACE INTO paper_portfolio 
                            (token_address, amount, last_price, last_update)
                            VALUES (?, ?, ?, ?)
                        ''', (
                            token_address,
                            amount_sol,
                            usd_value / amount_sol if amount_sol > 0 else 0,
                            int(time.time())
                        ))
                    
                    conn.commit()
                    conn.close()
                    
                    info(f"✅ Added staked SOL position: {amount_sol:.4f} SOL to {protocol} at {apy:.2f}% APY")
                    return True
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    error(f"❌ Error adding staked SOL position after {max_retries} attempts: {e}")
                    return False
            except Exception as e:
                error(f"❌ Error adding staked SOL position: {e}")
                return False
        
        return False

    def get_staked_sol_positions(self, wallet_address: str = None) -> List[Dict]:
        """Get all staked SOL positions for a wallet"""
        try:
            with self._lock:
                db_path = os.path.join('data', 'portfolio_history_paper.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                if wallet_address:
                    cursor.execute('''
                        SELECT protocol, amount_sol, amount_usd, apy, timestamp, status
                        FROM staked_sol_tracking 
                        WHERE status = 'active'
                        ORDER BY timestamp DESC
                    ''')
                else:
                    cursor.execute('''
                        SELECT protocol, amount_sol, amount_usd, apy, timestamp, status
                        FROM staked_sol_tracking 
                        WHERE status = 'active'
                        ORDER BY timestamp DESC
                    ''')
                
                columns = [description[0] for description in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    position = dict(zip(columns, row))
                    results.append(position)
                
                conn.close()
                return results
                
        except Exception as e:
            error(f"❌ Error getting staked SOL positions: {e}")
            return []

    def update_staked_sol_position(self, wallet_address: str, protocol: str, 
                                  amount_sol: float = None, usd_value: float = None, 
                                  apy: float = None, status: str = None):
        """Update an existing staked SOL position"""
        try:
            with self._lock:
                db_path = os.path.join('data', 'portfolio_history_paper.db')
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Build update query dynamically
                updates = []
                params = []
                
                if amount_sol is not None:
                    updates.append("amount_sol = ?")
                    params.append(amount_sol)
                
                if usd_value is not None:
                    updates.append("amount_usd = ?")  # Use amount_usd instead of usd_value
                    params.append(usd_value)
                
                if apy is not None:
                    updates.append("apy = ?")
                    params.append(apy)
                
                if status is not None:
                    updates.append("status = ?")
                    params.append(status)
                
                if updates:
                    updates.append("timestamp = ?")
                    params.append(datetime.now().isoformat())
                    
                    params.extend([protocol])  # Remove wallet_address since it's not in the schema
                    
                    query = f"UPDATE staked_sol_tracking SET {', '.join(updates)} WHERE protocol = ?"
                    cursor.execute(query, params)
                    
                    conn.commit()
                    info(f"✅ Updated staked SOL position: {protocol} for {wallet_address}")
                
                conn.close()
                return True
                
        except Exception as e:
            error(f"❌ Error updating staked SOL position: {e}")
            return False

    def _check_and_trigger_agents(self, snapshot):
        """Check thresholds and trigger agents when breached"""
        try:
            # Skip all triggers during initialization
            if self.initialization_mode:
                debug("🚀 [INIT] Skipping agent triggers during initialization")
                return
            
            from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
            coordinator = get_simple_agent_coordinator()
            
            # Check Risk Agent triggers (highest priority)
            if self._check_risk_triggers(snapshot):
                if coordinator.start_execution('risk'):
                    threading.Thread(target=self._trigger_risk_agent, args=(snapshot,), daemon=True).start()
            
            # Check Copybot AI Analysis triggers
            elif self._check_copybot_ai_triggers(snapshot):
                if coordinator.start_execution('copybot'):
                    threading.Thread(target=self._trigger_copybot_ai_analysis, args=(snapshot,), daemon=True).start()
            
            # Check Harvesting Agent triggers (includes dust, rebalancing, and realized gains)
            elif self._check_harvesting_triggers(snapshot):
                if coordinator.start_execution('harvesting'):
                    threading.Thread(target=self._trigger_harvesting_agent, args=(snapshot,), daemon=True).start()
                    
        except Exception as e:
            error(f"Error checking agent triggers: {e}")

    def _check_risk_triggers(self, snapshot) -> bool:
        """Check if risk agent should trigger (CRITICAL conditions only)"""
        try:
            from src import config
            import time
            
            # Update consecutive losses from closed trades
            self.update_win_loss_streak()
            
            # Add cooldown check (5 minutes)
            cooldown_seconds = getattr(config, 'RISK_AGENT_COOLDOWN_SECONDS', 300)
            if time.time() - self.last_risk_trigger < cooldown_seconds:
                return False
            
            # CRITICAL: Minimum balance breach
            min_balance = getattr(config, 'MINIMUM_BALANCE_USD', 50)
            if snapshot.total_value_usd < min_balance:
                info(f"🚨 Risk trigger: Balance ${snapshot.total_value_usd:.2f} < ${min_balance}")
                return True
            
            # CRITICAL: Severe drawdown from peak (30%)
            drawdown_limit = getattr(config, 'DRAWDOWN_LIMIT_PERCENT', -30)
            if self.peak_portfolio_value > 0:
                drawdown_pct = ((snapshot.total_value_usd - self.peak_portfolio_value) / self.peak_portfolio_value) * 100
                if drawdown_pct <= drawdown_limit:
                    info(f"🚨 Risk trigger: Drawdown {drawdown_pct:.1f}% <= {drawdown_limit}%")
                    return True
            
            # CRITICAL: PnL loss percentage (10%)
            if hasattr(self, 'starting_balance') and self.starting_balance > 0:
                pnl_pct = ((snapshot.total_value_usd - self.starting_balance) / self.starting_balance) * 100
                max_loss = getattr(config, 'MAX_LOSS_PERCENT', 10)
                if pnl_pct <= -max_loss:
                    info(f"🚨 Risk trigger: PnL {pnl_pct:.1f}% <= -{max_loss}%")
                    return True
            
            # CRITICAL: Consecutive losses (6+ closed losing positions)
            if self.consecutive_losses >= getattr(config, 'CONSECUTIVE_LOSS_LIMIT', 6):
                info(f"🚨 Risk trigger: {self.consecutive_losses} consecutive losses >= {getattr(config, 'CONSECUTIVE_LOSS_LIMIT', 6)}")
                return True
            
            return False
        except Exception as e:
            error(f"Error checking risk triggers: {e}")
            return False


    def _check_harvesting_triggers(self, snapshot) -> bool:
        """Check if harvesting agent should trigger (includes dust, rebalancing, and realized gains)"""
        try:
            from src import config
            import time
            
            # Add cooldown check (10 minutes for harvesting)
            cooldown_seconds = getattr(config, 'HARVESTING_AGENT_COOLDOWN_SECONDS', 600)
            if time.time() - self.last_harvesting_trigger < cooldown_seconds:
                return False
            
            # Check for dust positions
            dust_threshold = getattr(config, 'DUST_THRESHOLD_USD', 1.0)
            for token, value in snapshot.positions.items():
                if token not in [getattr(config, 'SOL_ADDRESS', ''), getattr(config, 'USDC_ADDRESS', '')]:
                    if value <= dust_threshold:
                        return True
            
            # Check for SOL/USDC rebalancing needs
            total = snapshot.total_value_usd
            if total <= 0:
                return False
            
            sol_pct = snapshot.sol_value_usd / total
            usdc_pct = snapshot.usdc_balance / total
            
            # Priority 1: Startup case (100% SOL)
            if sol_pct >= 0.95 and usdc_pct <= 0.05:
                return True
            
            # Priority 2: USDC emergency
            usdc_emergency = getattr(config, 'USDC_EMERGENCY_PERCENT', 0.05)
            if usdc_pct < usdc_emergency:
                return True
            
            # Priority 3: SOL limits
            sol_min = getattr(config, 'SOL_MINIMUM_PERCENT', 0.10)
            sol_max = getattr(config, 'SOL_MAXIMUM_PERCENT', 0.20)
            if sol_pct < sol_min or sol_pct > sol_max:
                return True
            
            # Priority 4: USDC minimum
            usdc_min = getattr(config, 'USDC_MINIMUM_PERCENT', 0.20)
            if usdc_pct < usdc_min:
                return True
            
            # Check for realized gains using proper USDC balance changes
            if len(self.recent_snapshots) >= 2:
                previous_snapshot = self.recent_snapshots[-2]
                realized_gains = self._calculate_realized_gains(snapshot, previous_snapshot)
                if realized_gains.get('has_gains', False):
                    usdc_increase = realized_gains.get('usdc_increase', 0.0)
                    change_pct = realized_gains.get('change_percentage', 0.0)
                    info(f"💰 Realized gains detected: +${usdc_increase:.2f} USDC ({change_pct:.1%} increase)")
                    return True
            
            return False
        except:
            return False

    def _calculate_unrealized_gains(self, snapshot) -> Dict[str, float]:
        """Calculate unrealized gains for open positions (CopyBot trigger)"""
        try:
            unrealized_gains = {}
            
            if not hasattr(snapshot, 'positions') or not snapshot.positions:
                return unrealized_gains
                
            for token_address, position_data in snapshot.positions.items():
                try:
                    # Handle both dict and float formats for backward compatibility
                    if isinstance(position_data, dict):
                        current_value = position_data.get('value_usd', 0.0)
                    else:
                        current_value = float(position_data) if position_data else 0.0
                    
                    # Validate current_value is numeric
                    if not isinstance(current_value, (int, float)):
                        error(f"Invalid current_value type for {token_address}: {type(current_value)}")
                        continue
                    
                    if not token_address or current_value <= 0:
                        continue
                        
                    entry_price = self._get_entry_price(token_address)
                    if not entry_price or entry_price <= 0:
                        continue
                        
                    current_price = self.price_service.get_price(token_address, force_fetch=True, agent_type='portfolio', priority='high')
                    if not current_price or (isinstance(current_price, dict) or float(current_price) <= 0):
                        continue
                        
                    gains_multiplier = current_price / entry_price
                    unrealized_gains[token_address] = {
                        'current_value': current_value,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'gains_multiplier': gains_multiplier,
                        'gains_percentage': (gains_multiplier - 1) * 100
                    }
                    
                except Exception as e:
                    error(f"Error processing position {token_address}: {e}")
                    continue
                
            return unrealized_gains
            
        except Exception as e:
            error(f"Error calculating unrealized gains: {e}")
            return {}

    def _calculate_realized_gains(self, current_snapshot, previous_snapshot) -> Dict[str, Any]:
        """Calculate realized gains from USDC balance changes (Harvesting trigger)"""
        try:
            if not previous_snapshot:
                return {'usdc_increase': 0.0, 'change_percentage': 0.0, 'has_gains': False}
                
            usdc_increase = current_snapshot.usdc_balance - previous_snapshot.usdc_balance
            
            if usdc_increase <= 0:
                return {'usdc_increase': 0.0, 'change_percentage': 0.0, 'has_gains': False}
            
            # Skip if this looks like rebalancing (SOL decreased significantly)
            # If SOL decreased by similar amount, this is likely rebalancing, not gains
            sol_decrease = previous_snapshot.sol_value_usd - current_snapshot.sol_value_usd
            if sol_decrease > usdc_increase * 0.8:  # 80% threshold - SOL decreased by 80%+ of USDC increase
                debug(f"🚫 Skipping realized gains detection - appears to be rebalancing (SOL↓${sol_decrease:.2f}, USDC↑${usdc_increase:.2f})")
                return {'usdc_increase': 0.0, 'change_percentage': 0.0, 'has_gains': False}
                
            change_percentage = 0.0
            if previous_snapshot.usdc_balance > 0:
                change_percentage = usdc_increase / previous_snapshot.usdc_balance
                
            return {
                'usdc_increase': usdc_increase,
                'change_percentage': change_percentage,
                'has_gains': usdc_increase > 0,
                'previous_usdc': previous_snapshot.usdc_balance,
                'current_usdc': current_snapshot.usdc_balance
            }
            
        except Exception as e:
            error(f"Error calculating realized gains: {e}")
            return {'usdc_increase': 0.0, 'change_percentage': 0.0, 'has_gains': False}

    def _trigger_risk_agent(self, snapshot):
        """Trigger risk agent with CopyBot's exact formatting"""
        try:
            import time
            from src.main import print_agent_activation, print_agent_event_processing, print_agent_event_result, print_agent_completion
            
            # Update timestamp
            self.last_risk_trigger = time.time()
            
            # Check if AI analysis is enabled
            from src import config
            is_ai_analysis = getattr(config, 'USE_AI_CONFIRMATION', False)
            
            # Print activation header (CopyBot format)
            if is_ai_analysis:
                print_agent_activation("Risk Agent", "risk", 1, "AI analysis for risk assessment")
                print_agent_event_processing(1, 1, "Processing AI analysis...", "risk")
            else:
                print_agent_activation("Risk Agent", "risk", 1, "Emergency conditions check")
                print_agent_event_processing(1, 1, "Processing emergency conditions...", "risk")
            
            # Use singleton risk agent
            from src.agents.risk_agent import get_risk_agent
            agent = get_risk_agent()
            
            if not agent:
                error("❌ Risk agent not available")
                print_agent_event_result(1, "failed", "Risk agent not available", "risk")
                return
            
            # Trigger event-driven risk check with portfolio change
            if len(self.recent_snapshots) >= 2:
                agent.on_portfolio_change(snapshot, self.recent_snapshots[-2])
            else:
                # Fallback to emergency conditions check
                agent.check_emergency_conditions()
            
            # Print event result and completion
            print_agent_event_result(1, "success", "", "risk")
            print_agent_completion("risk", 1, 1)
            
            # Mark execution complete
            from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
            coordinator = get_simple_agent_coordinator()
            coordinator.finish_execution('risk')
        except Exception as e:
            print_agent_event_result(1, "failed", str(e), "risk")
            error(f"Risk agent execution error: {e}")

    def _trigger_rebalancing_agent(self, snapshot):
        """Trigger rebalancing via harvesting agent"""
        try:
            from src.agents.harvesting_agent import get_harvesting_agent
            agent = get_harvesting_agent()  # Use singleton instead of creating new instance
            actions = agent.check_portfolio_allocation()
            if actions:
                agent.execute_rebalancing(actions)
            
            # Mark execution complete
            from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
            coordinator = get_simple_agent_coordinator()
            coordinator.finish_execution('rebalancing')
        except Exception as e:
            error(f"Rebalancing agent execution error: {e}")

    def _trigger_harvesting_agent(self, snapshot):
        """Trigger harvesting agent with CopyBot's exact formatting"""
        try:
            import time
            from src.main import print_agent_activation, print_agent_event_processing, print_agent_event_result, print_agent_completion
            
            # Update timestamp
            self.last_harvesting_trigger = time.time()
            
            # Check if AI analysis is enabled
            from src import config
            is_ai_analysis = getattr(config, 'USE_AI_CONFIRMATION', False)
            
            # Print activation header (CopyBot format)
            if is_ai_analysis:
                print_agent_activation("Harvesting Agent", "harvesting", 1, "AI analysis for harvesting strategy")
                print_agent_event_processing(1, 1, "Processing AI analysis...", "harvesting")
            else:
                print_agent_activation("Harvesting Agent", "harvesting", 1, "Portfolio rebalancing check")
                print_agent_event_processing(1, 1, "Processing rebalancing...", "harvesting")
            
            # Execute agent (this will print its own INFO logs)
            from src.agents.harvesting_agent import get_harvesting_agent
            agent = get_harvesting_agent()  # Use singleton instead of creating new instance
            if len(self.recent_snapshots) >= 2:
                agent.on_portfolio_change(snapshot, self.recent_snapshots[-2])
            
            # Print event result and completion
            print_agent_event_result(1, "success", "", "harvesting")
            print_agent_completion("harvesting", 1, 1)
            
            # Mark execution complete
            from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
            coordinator = get_simple_agent_coordinator()
            coordinator.finish_execution('harvesting')
        except Exception as e:
            print_agent_event_result(1, "failed", str(e), "harvesting")
            error(f"Harvesting agent execution error: {e}")

    def _check_copybot_ai_triggers(self, snapshot) -> bool:
        """Check if copybot AI analysis should trigger using unrealized gains"""
        try:
            from src import config
            
            if not config.AI_GAINS_ANALYSIS["enabled"]:
                return False
            
            # Calculate unrealized gains for all positions
            unrealized_gains = self._calculate_unrealized_gains(snapshot)
            if not unrealized_gains:
                return False
            
            # Get total portfolio value for position size calculation
            total_value = snapshot.total_value_usd
            if total_value <= 0:
                return False
            
            # Check each position for triggers using unrealized gains data
            for token_address, gains_data in unrealized_gains.items():
                current_value = gains_data['current_value']
                gains_multiplier = gains_data['gains_multiplier']
                
                if not token_address or current_value <= 0:
                    continue
                
                # Calculate position size percentage
                position_size_pct = current_value / total_value
                
                # TRIGGER 1: Position size trigger (15% of portfolio)
                if position_size_pct >= config.AI_GAINS_ANALYSIS["thresholds"]["position_size_trigger"]:
                    if not self._is_ai_analysis_cooldown_active(token_address):
                        info(f"🤖 AI analysis trigger: {token_address[:8]}... at {position_size_pct:.1%} of portfolio")
                        return True
                
                # TRIGGER 2: Gains trigger (300% gains) - using unrealized gains data
                if gains_multiplier >= config.AI_GAINS_ANALYSIS["thresholds"]["analysis_trigger"]:
                    if not self._is_ai_analysis_cooldown_active(token_address):
                        info(f"🤖 AI analysis trigger: {token_address[:8]}... at {gains_multiplier:.2f}x gains")
                        return True
            
            return False
            
        except Exception as e:
            error(f"Error checking copybot AI triggers: {e}")
            return False

    def _trigger_copybot_ai_analysis(self, snapshot):
        """Trigger copybot AI analysis for extreme gains with beautiful formatting"""
        try:
            from src.main import print_agent_activation, print_agent_event_processing, print_agent_event_result, print_agent_completion
            
            # Print activation header (CopyBot format)
            print_agent_activation("CopyBot Agent", "copybot", 1, "AI analysis for extreme gains")
            print_agent_event_processing(1, 1, "Processing AI analysis...", "copybot")
            
            # Execute AI analysis
            from src.agents.copybot_agent import get_copybot_agent
            agent = get_copybot_agent()
            
            if agent:
                agent.analyze_extreme_gains_positions(snapshot)
            
            # Print event result and completion
            print_agent_event_result(1, "success", "", "copybot")
            print_agent_completion("copybot", 1, 1)
            
            # Mark execution complete
            from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
            coordinator = get_simple_agent_coordinator()
            coordinator.finish_execution('copybot')
            
        except Exception as e:
            print_agent_event_result(1, "failed", str(e), "copybot")
            error(f"Copybot AI analysis execution error: {e}")

    def _is_ai_analysis_cooldown_active(self, token_address: str) -> bool:
        """Check if AI analysis is in cooldown for this token"""
        try:
            from src import config
            
            if token_address in self.ai_analysis_cooldowns:
                last_analysis = self.ai_analysis_cooldowns[token_address]
                cooldown_seconds = config.AI_GAINS_ANALYSIS["cooldown_minutes"] * 60
                
                if time.time() - last_analysis < cooldown_seconds:
                    return True
            
            return False
            
        except Exception as e:
            error(f"Error checking AI analysis cooldown: {e}")
            return False

    def _update_ai_analysis_cooldown(self, token_address: str):
        """Update AI analysis cooldown for this token"""
        try:
            self.ai_analysis_cooldowns[token_address] = time.time()
        except Exception as e:
            error(f"Error updating AI analysis cooldown: {e}")

    def _get_entry_price(self, token_address: str) -> Optional[float]:
        """Get entry price for a token"""
        try:
            if not self.entry_price_tracker:
                return None
                
            entry_record = self.entry_price_tracker.get_entry_price(token_address)
            if entry_record:
                return entry_record.entry_price_usd
            return None
        except Exception as e:
            error(f"Error getting entry price for {token_address}: {e}")
            return None

    def record_closed_trade(self, token_address: str, exit_price: float, amount: float, 
                           token_symbol: str = None) -> bool:
        """Record a closed trade with PnL calculation - MODE-AGNOSTIC"""
        try:
            from src import config
            
            # Get entry price
            entry_price = self._get_entry_price(token_address)
            if not entry_price:
                warning(f"No entry price found for {token_address} - cannot calculate PnL")
                return False
            
            # Calculate PnL
            pnl_usd = (exit_price - entry_price) * amount
            pnl_percent = (pnl_usd / (entry_price * amount)) * 100 if entry_price > 0 else 0
            
            # Calculate hold time (simplified - use current time)
            hold_time_seconds = 0  # Could be enhanced to track actual hold time
            
            # Determine trade type based on mode
            trade_type = 'paper' if config.PAPER_TRADING_ENABLED else 'live'
            
            # Record in database
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO closed_trades 
                    (timestamp, token_address, token_symbol, entry_price, exit_price, 
                     amount, pnl_usd, pnl_percent, hold_time_seconds, trade_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now().isoformat(),
                    token_address,
                    token_symbol,
                    entry_price,
                    exit_price,
                    amount,
                    pnl_usd,
                    pnl_percent,
                    hold_time_seconds,
                    trade_type
                ))
                
                conn.commit()
                conn.close()
            
            # Update win/loss streak
            self.update_win_loss_streak()
            
            info(f"✅ Recorded closed trade: {token_symbol or token_address[:8]}... "
                 f"PnL: ${pnl_usd:.2f} ({pnl_percent:.2f}%)")
            return True
            
        except Exception as e:
            error(f"Error recording closed trade: {e}")
            return False

    def update_win_loss_streak(self) -> bool:
        """Update consecutive wins/losses based on recent closed trades - MODE-AGNOSTIC"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Get ALL closed trades ordered by timestamp
                cursor.execute('''
                    SELECT pnl_usd FROM closed_trades
                    ORDER BY timestamp DESC
                ''')
                
                trades = cursor.fetchall()
                if not trades:
                    conn.close()
                    return True
                
                # Calculate consecutive wins/losses from most recent trades
                consecutive_wins = 0
                consecutive_losses = 0
                total_wins = 0
                total_losses = 0
                
                for trade in trades:
                    pnl = trade[0]
                    if pnl > 0:
                        if consecutive_losses > 0:
                            break  # Stop at first win after losses
                        consecutive_wins += 1
                        total_wins += 1
                    elif pnl < 0:
                        if consecutive_wins > 0:
                            break  # Stop at first loss after wins
                        consecutive_losses += 1
                        total_losses += 1
                
                # Update or insert statistics
                cursor.execute('''
                    INSERT OR REPLACE INTO trading_statistics 
                    (id, consecutive_wins, consecutive_losses, total_wins, total_losses, last_updated)
                    VALUES (1, ?, ?, ?, ?, ?)
                ''', (consecutive_wins, consecutive_losses, total_wins, total_losses, 
                      datetime.now().isoformat()))
                
                conn.commit()
                conn.close()
                
                # Update instance variables
                self.consecutive_wins = consecutive_wins
                self.consecutive_losses = consecutive_losses
                
                debug(f"Updated streak: {consecutive_wins} wins, {consecutive_losses} losses")
                return True
                
        except Exception as e:
            error(f"Error updating win/loss streak: {e}")
            return False

    def get_consecutive_stats(self) -> dict:
        """Get current consecutive wins/losses statistics - MODE-AGNOSTIC"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT consecutive_wins, consecutive_losses, total_wins, total_losses, last_updated
                    FROM trading_statistics 
                    WHERE id = 1
                ''')
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    return {
                        'consecutive_wins': result[0],
                        'consecutive_losses': result[1],
                        'total_wins': result[2],
                        'total_losses': result[3],
                        'last_updated': result[4],
                        'win_rate': (result[2] / (result[2] + result[3])) * 100 if (result[2] + result[3]) > 0 else 0
                    }
                else:
                    return {
                        'consecutive_wins': 0,
                        'consecutive_losses': 0,
                        'total_wins': 0,
                        'total_losses': 0,
                        'last_updated': None,
                        'win_rate': 0
                    }
                    
        except Exception as e:
            error(f"Error getting consecutive stats: {e}")
            return {
                'consecutive_wins': 0,
                'consecutive_losses': 0,
                'total_wins': 0,
                'total_losses': 0,
                'last_updated': None,
                'win_rate': 0
            }

    def get_trading_statistics(self) -> dict:
        """Get comprehensive trading statistics for dashboard - MODE-AGNOSTIC"""
        try:
            from src import config
            
            stats = self.get_consecutive_stats()
            stats['current_mode'] = 'paper' if config.PAPER_TRADING_ENABLED else 'live'
            return stats
            
        except Exception as e:
            error(f"Error getting trading statistics: {e}")
            return {
                'consecutive_wins': 0,
                'consecutive_losses': 0,
                'total_wins': 0,
                'total_losses': 0,
                'win_rate': 0,
                'current_mode': 'unknown'
            }
    
    def get_reserved_amount(self, token_address: str) -> float:
        """
        Get reserved amount for a token (used in DeFi collateral)
        
        Args:
            token_address: Address of the token
            
        Returns:
            Reserved amount in token units
        """
        try:
            from src.scripts.defi.defi_position_manager import get_defi_position_manager
            position_manager = get_defi_position_manager()
            return position_manager.get_reserved_amount(token_address)
        except Exception as e:
            debug(f"Error getting reserved amount for {token_address}: {str(e)}")
            return 0.0
    
    def get_available_balance(self, token_address: str, total_balance: float) -> float:
        """
        Get available balance for a token (total minus reserved for DeFi)
        
        Args:
            token_address: Address of the token
            total_balance: Total balance of the token
            
        Returns:
            Available balance (total - reserved)
        """
        try:
            reserved = self.get_reserved_amount(token_address)
            available = max(0, total_balance - reserved)
            
            if reserved > 0:
                debug(f"Token {token_address}: Total={total_balance:.4f}, Reserved={reserved:.4f}, Available={available:.4f}")
            
            return available
        except Exception as e:
            debug(f"Error calculating available balance for {token_address}: {str(e)}")
            return total_balance


# Global instance
_portfolio_tracker = None

def get_portfolio_tracker() -> PortfolioTracker:
    """Get the singleton portfolio tracker instance"""
    global _portfolio_tracker
    if _portfolio_tracker is None:
        try:
            _portfolio_tracker = PortfolioTracker()
            debug("✅ Portfolio tracker instance created successfully")
        except Exception as e:
            error(f"❌ Failed to create portfolio tracker instance: {e}")
            return None
    return _portfolio_tracker 