"""
🌙 Anarcho Capital's Cloud Database Manager
PostgreSQL-based data storage for distributed trading system
Built with love by Anarcho Capital 🚀
"""

import os
import threading
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import socket

# Optional PostgreSQL imports - only import if available
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    # Create mock objects for when psycopg2 is not available
    class MockPsycopg2:
        class extras:
            pass
    psycopg2 = MockPsycopg2()

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

@dataclass
class DatabaseConfig:
    """Database configuration for cloud deployment"""
    host: str
    port: int
    database: str
    user: str
    password: str
    ssl_mode: str = "require"
    min_connections: int = 1
    max_connections: int = 10
    hostaddr: str | None = None  # optional IPv4

class CloudDatabaseManager:
    """PostgreSQL database manager for cloud deployment"""
    
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
        """Initialize the cloud database manager"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.connection_pool = []
        self.max_connections = 10
        self.connection_lock = threading.Lock()
        
        # Get database configuration from environment
        self.config = self._get_database_config()
        
        # Initialize database connection pool
        self._initialize_connection_pool()
        
        # Probe connectivity before declaring success
        self._probe_connectivity()
        
        # Create database schema
        self._create_schema()
        
        info("🌐 Cloud Database Manager initialized successfully")
    
    def _get_database_config(self) -> DatabaseConfig:
        """Get database configuration from environment variables"""
        # Validate that required environment variables are set
        postgres_host = os.getenv('POSTGRES_HOST', '').strip()
        postgres_user = os.getenv('POSTGRES_USER', '').strip()
        postgres_password = os.getenv('POSTGRES_PASSWORD', '').strip()
        postgres_hostaddr = os.getenv('POSTGRES_HOSTADDR', '').strip() or None
        
        if not postgres_host or not postgres_user or not postgres_password:
            raise ValueError("PostgreSQL configuration incomplete. Missing required environment variables.")
        
        return DatabaseConfig(
            host=postgres_host,
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'trading_system'),
            user=postgres_user,
            password=postgres_password,
            ssl_mode=os.getenv('POSTGRES_SSL_MODE', 'require'),
            min_connections=int(os.getenv('POSTGRES_MIN_CONNECTIONS', '1')),
            max_connections=int(os.getenv('POSTGRES_MAX_CONNECTIONS', '10')),
            hostaddr=postgres_hostaddr,
        )
    
    def _get_connection(self):
        """Get a database connection from the pool"""
        with self.connection_lock:
            if self.connection_pool:
                return self.connection_pool.pop()
            
            # Create new connection if pool is empty
            return self._create_connection()
    
    def _return_connection(self, conn):
        """Return a connection to the pool"""
        with self.connection_lock:
            if len(self.connection_pool) < self.max_connections:
                self.connection_pool.append(conn)
            else:
                conn.close()
    
    def _is_dns_error(self, exc: Exception) -> bool:
        """Check if error is DNS-related and should not be retried"""
        m = str(exc).lower()
        return any(s in m for s in [
            "no address associated with hostname",
            "getaddrinfo failed",
            "name or service not known",
            "temporary failure in name resolution",
        ])
    
    def _create_connection(self):
        """Create a new database connection with IPv4/IPv6 fallback and Supabase pooler"""
        try:
            # Env feature flags
            force_ipv4 = os.getenv('DB_FORCE_IPV4', '').strip().lower() in ('1', 'true', 'yes')
            # Supabase host detection
            host_lower = (self.config.host or '').lower()
            is_supabase = ('.supabase.co' in host_lower) or ('.supabase.com' in host_lower)
            is_pooler_host = ('.pooler.supabase.com' in host_lower) or (self.config.port == 6543)
            # Disable pooler for direct connections (port 5432)
            try_pooler = (os.getenv('DB_TRY_SUPABASE_POOLER', '1') != '0') and is_supabase and not is_pooler_host and (self.config.port != 5432)

            # Helper funcs
            def _resolve_ipv4(host: str, port: int) -> str:
                infos = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
                return infos[0][4][0]

            def _resolve_ipv6(host: str, port: int) -> str:
                infos = socket.getaddrinfo(host, port, family=socket.AF_INET6, type=socket.SOCK_STREAM)
                return infos[0][4][0]

            def _is_ipv6(addr: str) -> bool:
                return ':' in (addr or '')

            # Build connection strategies: list of (name, address, port)
            connection_strategies = []

            # Strategy 1: Use provided hostaddr if available (skip for pooler; skip if ipv6 and force_ipv4)
            if (not is_pooler_host) and self.config.hostaddr and not (force_ipv4 and _is_ipv6(self.config.hostaddr)):
                connection_strategies.append(("hostaddr", self.config.hostaddr, self.config.port))

            # Strategy 2: IPv4 resolution
            if not is_pooler_host:
                try:
                    ipv4_addr = _resolve_ipv4(self.config.host, self.config.port)
                    connection_strategies.append(("hostaddr_ipv4", ipv4_addr, self.config.port))
                except socket.gaierror:
                    debug("No IPv4 address available for database host")

            # Strategy 3: IPv6 resolution (only if not forcing IPv4)
            if (not is_pooler_host) and (not force_ipv4):
                try:
                    ipv6_addr = _resolve_ipv6(self.config.host, self.config.port)
                    connection_strategies.append(("hostaddr_ipv6", ipv6_addr, self.config.port))
                except socket.gaierror:
                    debug("No IPv6 address available for database host")

            # Strategy 4: Hostname directly - SKIP if forcing IPv4 to avoid IPv6 resolution
            if not force_ipv4:
                connection_strategies.append(("hostname", None, self.config.port))

            # Strategy 5: Supabase connection pooler on 6543 (hostname ONLY)
            # IMPORTANT: Supabase's Supavisor requires TLS SNI to match the tenant hostname.
            # Using a raw IP (hostaddr) to the pooler can yield "Tenant or user not found".
            # Therefore, we intentionally avoid any IP-based connection for the pooler and
            # always use the hostname with port 6543 so SNI is preserved.
            if try_pooler or is_pooler_host:
                warning("Supabase host detected; attempting connection via Connection Pooler (port 6543)", file_only=True)
                connection_strategies.append(("pooler_hostname", None, 6543))
                # Do NOT attempt port 5432 with the pooler hostname; that causes tenant errors.

            # Strategy 6: Fallback hostname strategy (always try as last resort)
            # This ensures we always have at least one strategy to try
            if not connection_strategies:
                warning("No connection strategies available, adding fallback hostname strategy")
                connection_strategies.append(("fallback_hostname", None, self.config.port))

            # Try each strategy until one works
            last_error = None
            for strategy_name, address, port in connection_strategies:
                try:
                    debug(f"Trying connection strategy: {strategy_name} (port {port})")

                    if address and not str(strategy_name).startswith("pooler_"):
                        # Use resolved address (non-pooler only)
                        connect_kwargs = dict(
                            host=self.config.host,       # keep hostname for TLS SNI/cert
                            hostaddr=address,            # use resolved IPv4/IPv6 address
                            port=port,
                            database=self.config.database,
                            user=self.config.user,
                            password=self.config.password,
                            sslmode=self.config.ssl_mode,
                            connect_timeout=10,
                            keepalives=1,
                            keepalives_idle=30,
                            keepalives_interval=10,
                            keepalives_count=3,
                        )
                        conn = psycopg2.connect(**connect_kwargs)
                    else:
                        # Use hostname directly (required for Supabase pooler to preserve SNI)
                        connect_kwargs = dict(
                            host=self.config.host,
                            port=port,
                            database=self.config.database,
                            user=self.config.user,
                            password=self.config.password,
                            sslmode=self.config.ssl_mode,
                            connect_timeout=10,
                            keepalives=1,
                            keepalives_idle=30,
                            keepalives_interval=10,
                            keepalives_count=3,
                        )
                        # If connecting to Supabase pooler, add project ref via options when available
                        if ('.pooler.supabase.com' in host_lower) or (port == 6543):
                            project_ref = os.getenv('SUPABASE_PROJECT_REF', '').strip()
                            if not project_ref and '.' in (self.config.user or ''):
                                try:
                                    project_ref = (self.config.user or '').split('.', 1)[1]
                                except Exception:
                                    project_ref = ''
                            
                            # Also try extracting from SUPABASE_URL if available
                            if not project_ref:
                                supabase_url = os.getenv('SUPABASE_URL', '').strip()
                                if supabase_url and 'supabase.co' in supabase_url:
                                    try:
                                        # Extract project ref from URL like: https://xxxxx.supabase.co
                                        parts = supabase_url.replace('https://', '').replace('http://', '').split('.')
                                        if len(parts) > 0:
                                            project_ref = parts[0]
                                            debug(f"Extracted project ref from SUPABASE_URL: {project_ref}")
                                    except Exception:
                                        pass
                            
                            if project_ref:
                                connect_kwargs['options'] = f"project={project_ref}"
                                debug(f"Using Supabase project reference: {project_ref}")
                        conn = psycopg2.connect(**connect_kwargs)

                    conn.autocommit = False
                    debug(f"✅ Connection successful with strategy: {strategy_name}")
                    return conn

                except Exception as e:
                    last_error = e
                    debug(f"❌ Connection failed with strategy {strategy_name}: {e}")
                    continue

            # If all strategies failed, raise the last error
            if last_error:
                error(f"All connection strategies failed. Last error: {last_error}", file_only=True)
                raise last_error
            else:
                raise Exception("No connection strategies available")

        except Exception as e:
            error(f"Failed to create database connection: {e}", file_only=True)
            raise
    
    def _probe_connectivity(self) -> None:
        """Probe database connectivity with a simple query"""
        conn = None
        try:
            conn = self._create_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.commit()
            cursor.close()
            self._return_connection(conn)
        except Exception as e:
            if conn:
                try: 
                    conn.close()
                except: 
                    pass
            raise
    
    def _initialize_connection_pool(self):
        """Initialize the connection pool"""
        try:
            for _ in range(self.config.min_connections):
                conn = self._create_connection()
                self.connection_pool.append(conn)
            info(f"✅ Database connection pool initialized with {len(self.connection_pool)} connections", file_only=True)
        except Exception as e:
            error(f"Failed to initialize connection pool: {e}")
            raise
    
    def _create_schema(self):
        """Create the database schema if it doesn't exist"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Create all tables
            self._create_sentiment_tables(cursor)
            self._create_portfolio_tables(cursor)
            self._create_whale_tables(cursor)
            self._create_artificial_memory_tables(cursor)
            self._create_chart_analysis_tables(cursor)
            self._create_execution_tracking_tables(cursor)
            self._create_entry_prices_tables(cursor)
            self._create_ai_analysis_tables(cursor)
            self._create_paper_trading_tables(cursor)
            self._create_agent_shared_data_table(cursor)
            self._create_log_backup_tables(cursor)
            self._create_database_backup_tables(cursor)
            self._create_onchain_data_tables(cursor)
            self._create_oi_tables(cursor)
            self._create_liquidation_tables(cursor)
            
            conn.commit()
            cursor.close()
            self._return_connection(conn)
            
            info("✅ Database schema created successfully")
            
        except Exception as e:
            error(f"Failed to create database schema: {e}")
            if 'conn' in locals():
                conn.rollback()
                cursor.close()
                self._return_connection(conn)
            raise
    
    def _create_sentiment_tables(self, cursor):
        """Create sentiment-related tables"""
        # Sentiment data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sentiment_data (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                sentiment_type VARCHAR(50) NOT NULL, -- 'chart', 'twitter', 'combined'
                overall_sentiment VARCHAR(50) NOT NULL,
                sentiment_score REAL NOT NULL,
                confidence REAL NOT NULL,
                num_tokens_analyzed INTEGER DEFAULT 0,
                bullish_tokens INTEGER DEFAULT 0,
                bearish_tokens INTEGER DEFAULT 0,
                neutral_tokens INTEGER DEFAULT 0,
                num_tweets INTEGER DEFAULT 0,
                engagement_avg REAL DEFAULT 0.0,
                ai_enhanced_score REAL DEFAULT 0.0,
                ai_model_used VARCHAR(100),
                tokens_analyzed TEXT,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create index for fast sentiment queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sentiment_data_timestamp 
            ON sentiment_data(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sentiment_data_type 
            ON sentiment_data(sentiment_type)
        ''')
    
    def _create_portfolio_tables(self, cursor):
        """Create portfolio-related tables"""
        # Portfolio history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                total_value_usd REAL NOT NULL,
                usdc_balance REAL NOT NULL,
                sol_balance REAL NOT NULL,
                sol_value_usd REAL NOT NULL,
                positions_value_usd REAL NOT NULL,
                change_detected BOOLEAN DEFAULT FALSE,
                change_type VARCHAR(50),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Portfolio balances table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_balances (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                token_mint VARCHAR(100) NOT NULL,
                token_symbol VARCHAR(20),
                token_name VARCHAR(100),
                amount REAL NOT NULL,
                raw_amount TEXT,
                decimals INTEGER DEFAULT 6,
                price_usd REAL,
                value_usd REAL,
                wallet_address VARCHAR(100),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_portfolio_history_timestamp 
            ON portfolio_history(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_portfolio_balances_token 
            ON portfolio_balances(token_mint)
        ''')
    
    def _create_whale_tables(self, cursor):
        """Create whale tracking tables"""
        # Whale data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whale_data (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                wallet_address VARCHAR(100) NOT NULL,
                wallet_name VARCHAR(100),
                total_value_usd REAL,
                pnl_1d REAL,
                pnl_7d REAL,
                pnl_30d REAL,
                top_tokens JSONB DEFAULT '[]',
                trading_volume_24h REAL,
                risk_score REAL,
                is_active BOOLEAN DEFAULT TRUE,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Whale history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whale_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                wallet_address VARCHAR(100) NOT NULL,
                action_type VARCHAR(50), -- 'buy', 'sell', 'transfer'
                token_mint VARCHAR(100),
                amount REAL,
                value_usd REAL,
                transaction_hash VARCHAR(100),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Whale schedules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whale_schedules (
                id SERIAL PRIMARY KEY,
                wallet_address VARCHAR(100) NOT NULL,
                next_execution_time TIMESTAMP WITH TIME ZONE,
                last_update TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                update_interval_hours INTEGER DEFAULT 24,
                is_active BOOLEAN DEFAULT TRUE,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_whale_data_address 
            ON whale_data(wallet_address)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_whale_history_address 
            ON whale_history(wallet_address)
        ''')
    
    def _create_artificial_memory_tables(self, cursor):
        """Create artificial memory tables"""
        # Artificial memory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artificial_memory (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                wallet_address VARCHAR(100) NOT NULL,
                token_mint VARCHAR(100) NOT NULL,
                token_symbol VARCHAR(20),
                token_name VARCHAR(100),
                amount REAL NOT NULL,
                raw_amount TEXT,
                decimals INTEGER DEFAULT 6,
                price_usd REAL,
                value_usd REAL,
                action_type VARCHAR(50), -- 'buy', 'sell', 'hold'
                confidence_score REAL DEFAULT 0.0,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_artificial_memory_wallet 
            ON artificial_memory(wallet_address)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_artificial_memory_token 
            ON artificial_memory(token_mint)
        ''')
    
    def _create_chart_analysis_tables(self, cursor):
        """Create chart analysis tables"""
        # Chart analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chart_analysis (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                token_symbol VARCHAR(20) NOT NULL,
                token_mint VARCHAR(100),
                timeframe VARCHAR(20), -- '1h', '4h', '1d'
                overall_sentiment VARCHAR(50),
                sentiment_score REAL,
                confidence REAL,
                technical_indicators JSONB DEFAULT '{}',
                support_levels JSONB DEFAULT '[]',
                resistance_levels JSONB DEFAULT '[]',
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chart_analysis_symbol 
            ON chart_analysis(token_symbol)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chart_analysis_timestamp 
            ON chart_analysis(timestamp DESC)
        ''')
    
    def _create_execution_tracking_tables(self, cursor):
        """Create execution tracking tables"""
        # Execution tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS execution_tracking (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                execution_id VARCHAR(100) UNIQUE NOT NULL,
                agent_name VARCHAR(100) NOT NULL,
                action_type VARCHAR(50) NOT NULL, -- 'buy', 'sell', 'harvest', 'risk_mitigation'
                token_mint VARCHAR(100),
                amount REAL,
                value_usd REAL,
                status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'executing', 'completed', 'failed'
                error_message TEXT,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_execution_tracking_agent 
            ON execution_tracking(agent_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_execution_tracking_status 
            ON execution_tracking(status)
        ''')

        # Live trades table (canonical executed trades)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS live_trades (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                signature VARCHAR(120) UNIQUE,
                side VARCHAR(10),
                size REAL,
                price_usd REAL,
                usd_value REAL,
                agent VARCHAR(50),
                token_mint VARCHAR(100),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_live_trades_timestamp
            ON live_trades(timestamp DESC)
        ''')
        
        # Staking transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staking_transactions (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                wallet_address VARCHAR(100) NOT NULL,
                protocol VARCHAR(50) NOT NULL,
                transaction_type VARCHAR(50) NOT NULL, -- 'STAKE', 'UNSTAKE', 'REWARDS'
                amount_sol REAL NOT NULL,
                amount_usd REAL NOT NULL,
                apy REAL NOT NULL,
                status VARCHAR(50) DEFAULT 'completed',
                daily_reward_sol REAL,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Staking positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staking_positions (
                id SERIAL PRIMARY KEY,
                wallet_address VARCHAR(100) NOT NULL,
                protocol VARCHAR(50) NOT NULL,
                amount_sol REAL NOT NULL,
                amount_usd REAL NOT NULL,
                apy REAL NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(wallet_address, protocol)
            )
        ''')
        
        # Create indexes for staking tables
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_staking_transactions_wallet 
            ON staking_transactions(wallet_address)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_staking_transactions_timestamp 
            ON staking_transactions(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_staking_positions_wallet 
            ON staking_positions(wallet_address)
        ''')
    
    def _create_entry_prices_tables(self, cursor):
        """Create entry prices tables"""
        # Entry prices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_prices (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                token_mint VARCHAR(100) NOT NULL,
                wallet_address VARCHAR(100) NOT NULL,
                entry_price_usd REAL NOT NULL,
                amount REAL NOT NULL,
                value_usd REAL NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_entry_prices_token 
            ON entry_prices(token_mint)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_entry_prices_wallet 
            ON entry_prices(wallet_address)
        ''')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS ux_entry_prices_token_wallet
            ON entry_prices(token_mint, wallet_address)
        ''')
    
    def _create_ai_analysis_tables(self, cursor):
        """Create AI analysis tables"""
        # AI analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_analysis (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                agent_name VARCHAR(100) NOT NULL,
                action VARCHAR(100) NOT NULL,
                token_symbol VARCHAR(20),
                token_mint VARCHAR(100),
                analysis_text TEXT,
                confidence REAL DEFAULT 0.0,
                price_usd REAL,
                change_percent REAL,
                token_name VARCHAR(100),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Change events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS change_events (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                wallet_address VARCHAR(100) NOT NULL,
                token_mint VARCHAR(100) NOT NULL,
                change_type VARCHAR(50) NOT NULL, -- 'added', 'removed', 'modified'
                old_amount REAL,
                new_amount REAL,
                old_price_usd REAL,
                new_price_usd REAL,
                old_value_usd REAL,
                new_value_usd REAL,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ai_analysis_agent 
            ON ai_analysis(agent_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_change_events_wallet 
            ON change_events(wallet_address)
        ''')
    
    def _create_agent_shared_data_table(self, cursor):
        """Create table for cross-agent data sharing"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_shared_data (
                id SERIAL PRIMARY KEY,
                agent_name VARCHAR(100) NOT NULL,
                data_type VARCHAR(100) NOT NULL,
                data JSONB NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(agent_name, data_type)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_agent_shared_data_agent 
            ON agent_shared_data(agent_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_agent_shared_data_type 
            ON agent_shared_data(data_type)
        ''')
    
    def _create_log_backup_tables(self, cursor):
        """Create log backup table for storing trading system logs"""
        # Log backups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_backups (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                log_filename VARCHAR(100) NOT NULL,
                log_content TEXT,
                log_size_bytes BIGINT,
                log_line_count INTEGER,
                backup_type VARCHAR(50) DEFAULT 'manual', -- 'manual', 'automatic', 'rotation'
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_log_backups_timestamp 
            ON log_backups(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_log_backups_filename
            ON log_backups(log_filename)
        ''')

    def _create_database_backup_tables(self, cursor):
        """Create database backup table for storing database file backups"""
        # Database backups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS database_backups (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                backup_id VARCHAR(100) NOT NULL UNIQUE,
                backup_type VARCHAR(50) DEFAULT 'manual', -- 'manual', 'defi', 'paper_trading', etc.
                data BYTEA, -- Binary data for database files
                size_bytes BIGINT,
                metadata JSONB DEFAULT '{}'
            )
        ''')

        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_database_backups_timestamp
            ON database_backups(timestamp DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_database_backups_type
            ON database_backups(backup_type)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_database_backups_id
            ON database_backups(backup_id)
        ''')

        # RBI Strategy Results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rbi_strategy_results (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                strategy_name VARCHAR(255) NOT NULL,
                strategy_type VARCHAR(50) DEFAULT 'unknown', -- 'youtube', 'pdf', 'text'
                source_url TEXT,
                research_content TEXT,
                backtest_code TEXT,
                performance_metrics JSONB DEFAULT '{}',
                sharpe_ratio DECIMAL(10,4),
                win_rate DECIMAL(5,2),
                max_drawdown DECIMAL(5,2),
                total_return DECIMAL(10,4),
                total_trades INTEGER,
                execution_status VARCHAR(50) DEFAULT 'pending', -- 'success', 'failed', 'pending'
                execution_errors TEXT,
                ai_model_used VARCHAR(100),
                processing_time_seconds INTEGER,
                metadata JSONB DEFAULT '{}'
            )
        ''')

        # Create indexes for RBI table
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_rbi_strategy_results_timestamp
            ON rbi_strategy_results(timestamp DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_rbi_strategy_results_name
            ON rbi_strategy_results(strategy_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_rbi_strategy_results_type
            ON rbi_strategy_results(strategy_type)
        ''')

    def _create_paper_trading_tables(self, cursor):
        """Create paper trading tables for synchronization"""
        # Paper trading portfolio table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_trading_portfolio (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                total_value_usd REAL NOT NULL,
                usdc_balance REAL NOT NULL,
                sol_balance REAL NOT NULL,
                sol_value_usd REAL NOT NULL,
                staked_sol_balance REAL DEFAULT 0.0,
                staked_sol_value_usd REAL DEFAULT 0.0,
                positions_value_usd REAL NOT NULL,
                change_detected BOOLEAN DEFAULT FALSE,
                change_type VARCHAR(50),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Paper trading transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_trading_transactions (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                transaction_id VARCHAR(100) UNIQUE NOT NULL,
                transaction_type VARCHAR(50) NOT NULL, -- 'buy', 'sell', 'convert', 'rebalance'
                token_mint VARCHAR(100) NOT NULL,
                token_symbol VARCHAR(20),
                amount REAL NOT NULL,
                price_usd REAL NOT NULL,
                value_usd REAL NOT NULL,
                usdc_amount REAL,
                sol_amount REAL,
                agent_name VARCHAR(100),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Paper trading balances table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_trading_balances (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                token_mint VARCHAR(100) NOT NULL,
                token_symbol VARCHAR(20),
                amount REAL NOT NULL,
                price_usd REAL,
                value_usd REAL,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_paper_trading_portfolio_timestamp 
            ON paper_trading_portfolio(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_paper_trading_transactions_type 
            ON paper_trading_transactions(transaction_type)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_paper_trading_transactions_token 
            ON paper_trading_transactions(token_mint)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_paper_trading_balances_token 
            ON paper_trading_balances(token_mint)
        ''')
    
    def _create_onchain_data_tables(self, cursor):
        """Create on-chain data tables"""
        # On-chain network metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS onchain_network_metrics (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                active_addresses INTEGER,
                transaction_count BIGINT,
                avg_tx_fee REAL,
                tvl_usd REAL,
                dex_volume_24h REAL,
                stablecoin_supply REAL,
                new_mints_24h INTEGER,
                nft_volume_24h REAL,
                bridge_inflow_24h REAL,
                bridge_outflow_24h REAL,
                net_bridge_flow REAL,
                validator_uptime REAL,
                validator_count INTEGER,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # On-chain health scores table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS onchain_health_scores (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                network_health_score REAL NOT NULL,
                confidence REAL NOT NULL,
                sentiment VARCHAR(50) NOT NULL,
                sentiment_reasoning TEXT,
                ai_summary TEXT,
                driving_factors JSONB DEFAULT '[]',
                concerns JSONB DEFAULT '[]',
                recommendations JSONB DEFAULT '[]',
                raw_metrics_id INTEGER,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_onchain_metrics_timestamp 
            ON onchain_network_metrics(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_onchain_health_timestamp 
            ON onchain_health_scores(timestamp DESC)
        ''')
    
    def _create_oi_tables(self, cursor):
        """Create open interest tracking tables"""
        # OI Raw Data Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oi_data (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                symbol VARCHAR(10) NOT NULL,
                open_interest REAL NOT NULL,
                funding_rate REAL,
                mark_price REAL,
                volume_24h REAL,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # OI Analytics Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oi_analytics (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                timeframe VARCHAR(20),
                symbol VARCHAR(10) NOT NULL,
                oi_change_pct REAL,
                oi_change_abs REAL,
                funding_rate_change_pct REAL,
                volume_24h REAL,
                liquidity_depth REAL,
                long_short_ratio REAL,
                oi_volume_ratio REAL,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes for efficient querying
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_oi_data_timestamp 
            ON oi_data(timestamp DESC, symbol)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_oi_analytics_timestamp 
            ON oi_analytics(timestamp DESC, symbol)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_oi_data_symbol 
            ON oi_data(symbol, timestamp DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_oi_analytics_symbol 
            ON oi_analytics(symbol, timestamp DESC)
        ''')
        
        # Funding Rates Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS funding_rates (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                symbol VARCHAR(20) NOT NULL,
                funding_rate REAL NOT NULL,
                annual_rate REAL NOT NULL,
                mark_price REAL,
                open_interest REAL,
                event_time TIMESTAMP WITH TIME ZONE
            )
        ''')
        
        # Funding Analytics Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS funding_analytics (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                symbol VARCHAR(20) NOT NULL,
                rate_change_pct REAL,
                trend VARCHAR(20),
                alert_level VARCHAR(20),
                timeframe VARCHAR(20),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes for funding tables
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_funding_rates_timestamp 
            ON funding_rates(timestamp DESC, symbol)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_funding_rates_symbol 
            ON funding_rates(symbol, timestamp DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_funding_analytics_timestamp 
            ON funding_analytics(timestamp DESC, symbol)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_funding_analytics_symbol 
            ON funding_analytics(symbol, timestamp DESC)
        ''')
    
    def _create_liquidation_tables(self, cursor):
        """Create liquidation tracking tables"""
        # Raw Liquidation Events Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS liquidation_events (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                event_time TIMESTAMP WITH TIME ZONE NOT NULL,
                exchange VARCHAR(20) NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                side VARCHAR(10) NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                usd_value REAL NOT NULL,
                order_type VARCHAR(20),
                time_in_force VARCHAR(10),
                average_price REAL,
                mark_price REAL,
                index_price REAL,
                price_impact_bps REAL,
                spread_bps REAL,
                cumulative_1m_usd REAL,
                cumulative_5m_usd REAL,
                cumulative_15m_usd REAL,
                event_velocity_1m INTEGER,
                cascade_score REAL,
                cluster_size INTEGER,
                bid_depth_10bps REAL,
                ask_depth_10bps REAL,
                imbalance_ratio REAL,
                volatility_1h REAL,
                volatility_percentile REAL,
                volume_1h REAL,
                oi_change_1h_pct REAL,
                concurrent_exchanges INTEGER,
                cross_exchange_lag_ms REAL,
                dominant_exchange VARCHAR(20),
                event_id INTEGER,
                batch_id VARCHAR(50),
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Liquidation Analytics Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS liquidation_analytics (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                symbol VARCHAR(10) NOT NULL,
                window_minutes INTEGER NOT NULL,
                long_liquidations REAL NOT NULL,
                short_liquidations REAL NOT NULL,
                total_liquidations REAL NOT NULL,
                long_count INTEGER NOT NULL,
                short_count INTEGER NOT NULL,
                dominant_side VARCHAR(10),
                exchanges_active INTEGER,
                avg_cascade_score REAL,
                max_cluster_size INTEGER,
                total_events INTEGER,
                metadata JSONB DEFAULT '{}'
            )
        ''')
        
        # Create indexes for efficient querying
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_liquidation_events_timestamp 
            ON liquidation_events(timestamp DESC, symbol)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_liquidation_events_event_time 
            ON liquidation_events(event_time DESC, symbol)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_liquidation_events_symbol 
            ON liquidation_events(symbol, event_time DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_liquidation_events_exchange 
            ON liquidation_events(exchange, event_time DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_liquidation_events_side 
            ON liquidation_events(side, event_time DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_liquidation_analytics_timestamp 
            ON liquidation_analytics(timestamp DESC, symbol)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_liquidation_analytics_symbol 
            ON liquidation_analytics(symbol, timestamp DESC)
        ''')
    
    def save_onchain_metrics(self, metrics: Dict) -> bool:
        """Save on-chain network metrics to cloud database"""
        try:
            query = '''
                INSERT INTO onchain_network_metrics (
                    timestamp, active_addresses, transaction_count, avg_tx_fee,
                    tvl_usd, dex_volume_24h, stablecoin_supply, new_mints_24h,
                    nft_volume_24h, bridge_inflow_24h, bridge_outflow_24h,
                    net_bridge_flow, validator_uptime, validator_count, metadata
                ) VALUES (
                    NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            '''
            params = (
                metrics.get('active_addresses'),
                metrics.get('transaction_count'),
                metrics.get('avg_tx_fee'),
                metrics.get('tvl_usd'),
                metrics.get('dex_volume_24h'),
                metrics.get('stablecoin_supply'),
                metrics.get('new_mints_24h'),
                metrics.get('nft_volume_24h'),
                metrics.get('bridge_inflow_24h'),
                metrics.get('bridge_outflow_24h'),
                metrics.get('net_bridge_flow'),
                metrics.get('validator_uptime'),
                metrics.get('validator_count'),
                json.dumps(metrics.get('metadata', {}))
            )
            
            self.execute_query(query, params, fetch=False)
            debug("✅ On-chain metrics saved to cloud database")
            return True
            
        except Exception as e:
            warning(f"Failed to save on-chain metrics to cloud: {e}")
            return False
    
    def save_onchain_analysis(self, analysis: Dict) -> bool:
        """Save on-chain health analysis to cloud database"""
        try:
            query = '''
                INSERT INTO onchain_health_scores (
                    timestamp, network_health_score, confidence, sentiment,
                    sentiment_reasoning, ai_summary, driving_factors,
                    concerns, recommendations, raw_metrics_id, metadata
                ) VALUES (
                    NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            '''
            params = (
                analysis.get('network_health_score'),
                analysis.get('confidence'),
                analysis.get('sentiment'),
                analysis.get('sentiment_reasoning'),
                analysis.get('ai_summary'),
                json.dumps(analysis.get('driving_factors', [])),
                json.dumps(analysis.get('concerns', [])),
                json.dumps(analysis.get('recommendations', [])),
                analysis.get('raw_metrics_id'),
                json.dumps(analysis.get('metadata', {}))
            )
            
            self.execute_query(query, params, fetch=False)
            debug("✅ On-chain analysis saved to cloud database")
            return True
            
        except Exception as e:
            warning(f"Failed to save on-chain analysis to cloud: {e}")
            return False
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True):
        """Execute a database query with retries and proper rollback"""
        conn = None
        cursor = None
        attempts = 0
        last_err = None

        def _should_retry(exc: Exception) -> bool:
            msg = str(exc).lower()
            # Don't retry DNS errors - they won't resolve quickly
            if any(s in msg for s in [
                "no address associated with hostname",
                "getaddrinfo failed",
                "name or service not known",
                "temporary failure in name resolution",
            ]):
                return False
            # Retry on network transport issues and transient connectivity
            return any(s in msg for s in [
                "network is unreachable",
                "could not connect to server",
                "connection timed out",
                "timeout expired",
                "connection reset",
                "server closed the connection unexpectedly",
            ])

        while attempts < 3:
            try:
                conn = self._get_connection()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                cursor.execute(query, params)

                if fetch:
                    result = cursor.fetchall()
                    conn.commit()
                    return [dict(row) for row in result]
                else:
                    conn.commit()
                    return cursor.rowcount

            except Exception as e:
                last_err = e
                if conn:
                    try: conn.rollback()
                    except: pass

                if _should_retry(e):
                    attempts += 1
                    backoff = min(2 ** attempts, 8)
                    warning(f"Transient DB error, retrying in {backoff}s (attempt {attempts}/3): {e}")
                    time.sleep(backoff)
                    # ensure fresh connection next attempt
                    if cursor:
                        try: cursor.close()
                        except: pass
                    if conn:
                        try: self._return_connection(conn)
                        except: pass
                    cursor = None
                    conn = None
                    continue

                error(f"Database query failed: {e}")
                raise

            finally:
                if cursor:
                    try: cursor.close()
                    except: pass
                if conn:
                    try: self._return_connection(conn)
                    except: pass

        # exhausted retries
        error(f"Database query failed after retries: {last_err}")
        raise last_err

    # -----------------------------
    # Live portfolio + trades API
    # -----------------------------
    def upsert_live_portfolio_snapshot(self, total_value_usd: float, usdc_balance: float,
                                       sol_balance: float, sol_value_usd: float,
                                       positions_value_usd: float,
                                       metadata: Optional[dict] = None) -> bool:
        """Insert a live portfolio snapshot into portfolio_history table."""
        try:
            query = '''
                INSERT INTO portfolio_history (
                    total_value_usd, usdc_balance, sol_balance, sol_value_usd,
                    positions_value_usd, change_detected, change_type, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            '''
            params = (
                total_value_usd,
                usdc_balance,
                sol_balance,
                sol_value_usd,
                positions_value_usd,
                True,
                'status_update',
                json.dumps(metadata or {})
            )
            self.execute_query(query, params, fetch=False)
            return True
        except Exception as e:
            warning(f"Failed to upsert live portfolio snapshot: {e}")
            return False

    def add_live_trade(self, signature: str, side: str, size: float, price_usd: float,
                       usd_value: float, agent: str, token_mint: str,
                       metadata: Optional[dict] = None, token_symbol: str = None, token_name: str = None) -> bool:
        """Insert a live trade record with metadata."""
        try:
            # Fetch metadata if not provided
            if not token_symbol or not token_name:
                try:
                    from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
                    metadata_service = get_token_metadata_service()
                    token_metadata = metadata_service.get_metadata(token_mint)
                    if token_metadata:
                        token_symbol = token_metadata.get('symbol', 'UNK')
                        token_name = token_metadata.get('name', 'Unknown Token')
                except:
                    pass
            
            token_symbol = token_symbol or 'UNK'
            token_name = token_name or 'Unknown Token'
            
            query = '''
                INSERT INTO live_trades (
                    signature, side, size, price_usd, usd_value, agent, token_mint, metadata, token_symbol, token_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (signature) DO NOTHING
            '''
            params = (signature, side, size, price_usd, usd_value, agent, token_mint,
                      json.dumps(metadata or {}), token_symbol, token_name)
            self.execute_query(query, params, fetch=False)
            return True
        except Exception as e:
            warning(f"Failed to add live trade: {e}")
            return False

    def get_recent_live_trades(self, limit: int = 5) -> List[dict]:
        try:
            query = '''
                SELECT * FROM live_trades ORDER BY timestamp DESC LIMIT %s
            '''
            return self.execute_query(query, (limit,))
        except Exception as e:
            warning(f"Failed to fetch live trades: {e}")
            return []
    
    def save_paper_trading_portfolio(self, portfolio_data: dict) -> bool:
        """Save paper trading portfolio snapshot to cloud database"""
        try:
            # Prepare metadata with positions data
            metadata = portfolio_data.get('metadata', {})
            if 'positions' in portfolio_data:
                metadata['positions'] = portfolio_data['positions']
            
            query = '''
                INSERT INTO paper_trading_portfolio 
                (total_value_usd, usdc_balance, sol_balance, sol_value_usd, staked_sol_balance, staked_sol_value_usd, positions_value_usd, change_detected, change_type, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            params = (
                portfolio_data.get('total_value', 0.0),
                portfolio_data.get('usdc_balance', 0.0),
                portfolio_data.get('sol_balance', 0.0),
                portfolio_data.get('sol_value_usd', 0.0),
                portfolio_data.get('staked_sol_balance', 0.0),
                portfolio_data.get('staked_sol_value_usd', 0.0),
                portfolio_data.get('positions_value_usd', 0.0),
                portfolio_data.get('change_detected', False),
                portfolio_data.get('change_type', 'unknown'),
                json.dumps(metadata)
            )
            
            self.execute_query(query, params, fetch=False)
            info("✅ Paper trading portfolio saved to cloud database")
            return True
            
        except Exception as e:
            warning(f"Failed to save paper trading portfolio to cloud: {e}")
            return False
    
    def save_paper_trading_transaction(self, transaction_data: dict):
        """Save paper trading transaction to cloud database"""
        try:
            query = '''
                INSERT INTO paper_trading_transactions 
                (transaction_id, transaction_type, token_mint, token_symbol, amount, price_usd, value_usd, usdc_amount, sol_amount, agent_name, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            params = (
                transaction_data.get('transaction_id', ''),
                transaction_data.get('transaction_type', ''),
                transaction_data.get('token_mint', ''),
                transaction_data.get('token_symbol', ''),
                transaction_data.get('amount', 0.0),
                transaction_data.get('price_usd', 0.0),
                transaction_data.get('value_usd', 0.0),
                transaction_data.get('usdc_amount', 0.0),
                transaction_data.get('sol_amount', 0.0),
                transaction_data.get('agent_name', ''),
                json.dumps(transaction_data.get('metadata', {}))
            )
            
            self.execute_query(query, params, fetch=False)
            info("✅ Paper trading transaction saved to cloud database")
            
        except Exception as e:
            warning(f"Failed to save paper trading transaction to cloud: {e}")
            raise
    
    def get_latest_paper_trading_portfolio(self):
        """Get the latest paper trading portfolio from cloud database"""
        try:
            query = '''
                SELECT * FROM paper_trading_portfolio 
                ORDER BY timestamp DESC 
                LIMIT 1
            '''
            result = self.execute_query(query)
            return result[0] if result else None
            
        except Exception as e:
            warning(f"Failed to get latest paper trading portfolio from cloud: {e}")
            return None
    
    def get_paper_trading_transactions(self, limit: int = 100):
        """Get recent paper trading transactions from cloud database"""
        try:
            query = '''
                SELECT * FROM paper_trading_transactions 
                ORDER BY timestamp DESC 
                LIMIT %s
            '''
            result = self.execute_query(query, (limit,))
            return result
            
        except Exception as e:
            warning(f"Failed to get paper trading transactions from cloud: {e}")
            return []
    
    def clear_paper_trading_data(self) -> bool:
        """Clear all paper trading data from cloud database"""
        try:
            # Clear portfolio data
            result1 = self.execute_query("DELETE FROM paper_trading_portfolio", fetch=False)
            # Clear transaction data
            result2 = self.execute_query("DELETE FROM paper_trading_transactions", fetch=False)

            if result1 and result2:
                info("✅ Cleared all paper trading data from cloud database")
                return True
            else:
                warning("⚠️ Cloud database clearing may have failed - connection issues")
                return False
        except Exception as e:
            warning(f"Failed to clear paper trading data from cloud: {e}")
            return False

    def clear_all_paper_trading_data(self) -> bool:
        """Enhanced method to clear all paper trading data from cloud database"""
        try:
            # Clear portfolio table
            self.execute_query("DELETE FROM paper_trading_portfolio", fetch=False)

            # Clear trades table
            self.execute_query("DELETE FROM paper_trading_transactions", fetch=False)

            # Clear balances table
            self.execute_query("DELETE FROM paper_trading_balances", fetch=False)

            # Reset any other paper trading related tables
            self.execute_query("DELETE FROM paper_trading_snapshots", fetch=False)

            # Commit the changes
            self.connection.commit()

            info("✅ All paper trading data cleared from cloud database")
            return True
        except Exception as e:
            warning(f"Failed to clear all paper trading data: {e}")
            return False
    
    def save_agent_data(self, agent_name: str, data_type: str, data: dict) -> bool:
        """Save agent-specific data for cross-agent access"""
        try:
            query = '''
                INSERT INTO agent_shared_data (agent_name, data_type, data, timestamp)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (agent_name, data_type) 
                DO UPDATE SET data = EXCLUDED.data, timestamp = NOW()
            '''
            params = (agent_name, data_type, json.dumps(data))
            self.execute_query(query, params, fetch=False)
            debug(f"✅ Agent data saved: {agent_name} - {data_type}")
            return True
            
        except Exception as e:
            warning(f"Failed to save agent data: {e}")
            return False
    
    def get_agent_data(self, agent_name: str = None, data_type: str = None):
        """Get agent data for cross-agent synchronization"""
        try:
            query = "SELECT * FROM agent_shared_data WHERE 1=1"
            params = []
            
            if agent_name:
                query += " AND agent_name = %s"
                params.append(agent_name)
            
            if data_type:
                query += " AND data_type = %s"
                params.append(data_type)
            
            query += " ORDER BY timestamp DESC"
            result = self.execute_query(query, params)
            
            # Parse JSON data
            for row in result:
                if row.get('data'):
                    try:
                        row['data'] = json.loads(row['data'])
                    except:
                        pass
            
            return result
            
        except Exception as e:
            warning(f"Failed to get agent data: {e}")
            return []

    def save_staking_transaction(self, transaction_data: dict) -> bool:
        """Save staking transaction to cloud database"""
        try:
            query = '''
                INSERT INTO staking_transactions 
                (wallet_address, protocol, transaction_type, amount_sol, amount_usd, apy, status, daily_reward_sol, metadata, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            '''
            params = (
                transaction_data.get('wallet_address'),
                transaction_data.get('protocol'),
                transaction_data.get('transaction_type'),
                transaction_data.get('amount_sol'),
                transaction_data.get('amount_usd'),
                transaction_data.get('apy'),
                transaction_data.get('status'),
                transaction_data.get('daily_reward_sol'),
                json.dumps(transaction_data.get('metadata', {}))
            )
            self.execute_query(query, params, fetch=False)
            debug(f"✅ Staking transaction saved: {transaction_data.get('protocol')} - {transaction_data.get('amount_sol')} SOL")
            return True
            
        except Exception as e:
            warning(f"Failed to save staking transaction: {e}")
            return False

    def save_staking_position(self, position_data: dict) -> bool:
        """Save staking position to cloud database"""
        try:
            query = '''
                INSERT INTO staking_positions 
                (wallet_address, protocol, amount_sol, amount_usd, apy, status, metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (wallet_address, protocol) 
                DO UPDATE SET 
                    amount_sol = EXCLUDED.amount_sol,
                    amount_usd = EXCLUDED.amount_usd,
                    apy = EXCLUDED.apy,
                    status = EXCLUDED.status,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            '''
            params = (
                position_data.get('wallet_address'),
                position_data.get('protocol'),
                position_data.get('amount_sol'),
                position_data.get('amount_usd'),
                position_data.get('apy'),
                position_data.get('status'),
                json.dumps(position_data.get('metadata', {}))
            )
            self.execute_query(query, params, fetch=False)
            debug(f"✅ Staking position saved: {position_data.get('protocol')} - {position_data.get('amount_sol')} SOL")
            return True
            
        except Exception as e:
            warning(f"Failed to save staking position: {e}")
            return False
    
    def save_local_ip_registration(self, public_ip: str, local_ip: str = None, 
                                 port: int = 8080, hostname: str = None, ngrok_url: str = None) -> bool:
        """Save local IP registration to cloud database"""
        try:
            # Try with ngrok_url first if provided
            if ngrok_url:
                query = '''
                    INSERT INTO local_ip_registrations 
                    (public_ip, local_ip, port, hostname, ngrok_url, registered_at, last_seen)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (public_ip, port) 
                    DO UPDATE SET 
                        local_ip = EXCLUDED.local_ip,
                        hostname = EXCLUDED.hostname,
                        ngrok_url = EXCLUDED.ngrok_url,
                        last_seen = NOW()
                '''
                params = (public_ip, local_ip, port, hostname, ngrok_url)
            else:
                # Fallback to basic query without ngrok_url
                query = '''
                    INSERT INTO local_ip_registrations 
                    (public_ip, local_ip, port, hostname, registered_at, last_seen)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (public_ip, port) 
                    DO UPDATE SET 
                        local_ip = EXCLUDED.local_ip,
                        hostname = EXCLUDED.hostname,
                        last_seen = NOW()
                '''
                params = (public_ip, local_ip, port, hostname)
            
            self.execute_query(query, params, fetch=False)
            debug(f"✅ Local IP registration saved: {public_ip}:{port}" + (f" (ngrok: {ngrok_url})" if ngrok_url else ""))
            return True
            
        except Exception as e:
            # If ngrok_url column doesn't exist, try without it
            if ngrok_url and "ngrok_url" in str(e):
                try:
                    warning(f"ngrok_url column not found, retrying without ngrok_url...")
                    query = '''
                        INSERT INTO local_ip_registrations 
                        (public_ip, local_ip, port, hostname, registered_at, last_seen)
                        VALUES (%s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (public_ip, port) 
                        DO UPDATE SET 
                            local_ip = EXCLUDED.local_ip,
                            hostname = EXCLUDED.hostname,
                            last_seen = NOW()
                    '''
                    params = (public_ip, local_ip, port, hostname)
                    self.execute_query(query, params, fetch=False)
                    debug(f"✅ Local IP registration saved (without ngrok_url): {public_ip}:{port}")
                    return True
                except Exception as retry_e:
                    warning(f"Failed to save local IP registration (retry): {retry_e}")
                    return False
            else:
                warning(f"Failed to save local IP registration: {e}")
                return False
    
    def get_latest_local_ip_registration(self) -> Optional[Dict]:
        """Get the latest local IP registration from cloud database"""
        try:
            query = '''
                SELECT public_ip, local_ip, port, hostname, registered_at, last_seen
                FROM local_ip_registrations 
                ORDER BY registered_at DESC 
                LIMIT 1
            '''
            result = self.execute_query(query, fetch=True)
            if result and len(result) > 0:
                row = result[0]
                return {
                    'public_ip': row[0],
                    'local_ip': row[1], 
                    'port': row[2],
                    'hostname': row[3],
                    'registered_at': row[4],
                    'last_seen': row[5]
                }
            return None
            
        except Exception as e:
            warning(f"Failed to get latest local IP registration: {e}")
            return None
    
    def save_log_backup(self, log_file_path: str, log_content: str = None, 
                       backup_type: str = 'manual') -> bool:
        """Save log file backup to cloud database"""
        try:
            import os
            
            if not os.path.exists(log_file_path):
                warning(f"Log file not found: {log_file_path}")
                return False
            
            # Get log file info
            file_size = os.path.getsize(log_file_path)
            filename = os.path.basename(log_file_path)
            
            # Read log content if not provided
            if log_content is None:
                try:
                    with open(log_file_path, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                except Exception as e:
                    warning(f"Could not read log file: {e}")
                    return False
            
            # Count lines
            line_count = log_content.count('\n')
            
            query = '''
                INSERT INTO log_backups 
                (log_filename, log_content, log_size_bytes, log_line_count, backup_type, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            '''
            params = (
                filename,
                log_content,
                file_size,
                line_count,
                backup_type,
                json.dumps({'file_path': log_file_path})
            )
            
            self.execute_query(query, params, fetch=False)
            info(f"✅ Log backup saved: {filename} ({file_size/1024:.2f} KB, {line_count} lines)")
            return True
            
        except Exception as e:
            warning(f"Failed to save log backup: {e}")
            return False
    
    def get_recent_log_backups(self, limit: int = 10) -> List[dict]:
        """Get recent log backups from cloud database"""
        try:
            query = '''
                SELECT id, timestamp, log_filename, log_size_bytes, log_line_count, backup_type
                FROM log_backups 
                ORDER BY timestamp DESC 
                LIMIT %s
            '''
            return self.execute_query(query, (limit,))
        except Exception as e:
            warning(f"Failed to fetch log backups: {e}")
            return []

    def backup_defi_positions_database(self, db_path: str = None, backup_type: str = 'manual') -> bool:
        """Backup DeFi positions database to cloud"""
        try:
            import os

            # Default path
            if db_path is None:
                db_path = os.path.join('src', 'data', 'defi_positions.db')

            if not os.path.exists(db_path):
                warning(f"DeFi database not found: {db_path}")
                return False

            # Get database info
            file_size = os.path.getsize(db_path)

            # Read database file as binary
            with open(db_path, 'rb') as f:
                db_content = f.read()

            # Get database statistics
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Count records in each table
            stats = {}
            tables = ['defi_positions', 'defi_loops', 'reserved_balances']
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = cursor.fetchone()[0]
                except:
                    stats[table] = 0

            conn.close()

            metadata = {
                'file_path': db_path,
                'tables': stats,
                'total_positions': stats.get('defi_positions', 0),
                'total_loops': stats.get('defi_loops', 0),
                'reserved_balances': stats.get('reserved_balances', 0)
            }

            query = '''
                INSERT INTO database_backups
                (backup_id, backup_type, data, size_bytes, metadata)
                VALUES (%s, %s, %s, %s, %s)
            '''

            from datetime import datetime
            backup_id = f"defi_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            params = (
                backup_id,
                backup_type,
                db_content,
                file_size,
                json.dumps(metadata)
            )

            success = self.execute_query(query, params, fetch=False)
            if success:
                info(f"✅ DeFi database backup saved to cloud: {backup_id}")
                return True
            else:
                warning("❌ Failed to save DeFi database backup to cloud")
                return False

        except Exception as e:
            error(f"Failed to backup DeFi database: {e}")
            return False

    def restore_defi_positions_database(self, backup_id: str, restore_path: str = None) -> bool:
        """Restore DeFi positions database from cloud backup"""
        try:
            # Default restore path
            if restore_path is None:
                restore_path = os.path.join('src', 'data', 'defi_positions.db')

            # Get backup data from cloud
            query = '''
                SELECT data, metadata FROM database_backups
                WHERE backup_id = %s AND backup_type LIKE %s
            '''
            rows = self.execute_query(query, (backup_id, '%defi%'))

            if not rows:
                warning(f"DeFi backup not found: {backup_id}")
                return False

            # Write database file
            with open(restore_path, 'wb') as f:
                f.write(rows[0]['data'])

            # Parse metadata for logging
            metadata = json.loads(rows[0]['metadata']) if rows[0]['metadata'] else {}
            positions = metadata.get('total_positions', 0)
            loops = metadata.get('total_loops', 0)

            info(f"✅ DeFi database restored from cloud: {positions} positions, {loops} loops")
            return True

        except Exception as e:
            error(f"Failed to restore DeFi database: {e}")
            return False

    def save_oi_data(self, oi_records: List[Dict]) -> bool:
        """Save OI data to cloud database"""
        try:
            if not oi_records:
                warning("No OI data to save")
                return False
            
            query = '''
                INSERT INTO oi_data (
                    timestamp, symbol, open_interest, funding_rate,
                    mark_price, volume_24h, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            
            success_count = 0
            for record in oi_records:
                params = (
                    record.get('timestamp'),
                    record.get('symbol'),
                    record.get('open_interest'),
                    record.get('funding_rate'),
                    record.get('mark_price'),
                    record.get('volume_24h'),
                    json.dumps(record.get('metadata', {}))
                )
                
                result = self.execute_query(query, params, fetch=False)
                if result:
                    success_count += 1
            
            info(f"✅ Saved {success_count}/{len(oi_records)} OI records to cloud")
            return success_count > 0
            
        except Exception as e:
            error(f"Failed to save OI data: {e}")
            return False
    
    def save_oi_analytics(self, analytics_records: List[Dict]) -> bool:
        """Save OI analytics to cloud database"""
        try:
            if not analytics_records:
                warning("No OI analytics to save")
                return False
            
            query = '''
                INSERT INTO oi_analytics (
                    timestamp, timeframe, symbol, oi_change_pct, oi_change_abs,
                    funding_rate_change_pct, volume_24h, liquidity_depth,
                    long_short_ratio, oi_volume_ratio, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            success_count = 0
            for record in analytics_records:
                params = (
                    record.get('timestamp'),
                    record.get('timeframe'),
                    record.get('symbol'),
                    record.get('oi_change_pct'),
                    record.get('oi_change_abs'),
                    record.get('funding_rate_change_pct'),
                    record.get('volume_24h'),
                    record.get('liquidity_depth'),
                    record.get('long_short_ratio'),
                    record.get('oi_volume_ratio'),
                    json.dumps(record.get('metadata', {}))
                )
                
                result = self.execute_query(query, params, fetch=False)
                if result:
                    success_count += 1
            
            info(f"✅ Saved {success_count}/{len(analytics_records)} OI analytics to cloud")
            return success_count > 0
            
        except Exception as e:
            error(f"Failed to save OI analytics: {e}")
            return False
    
    def save_funding_data(self, funding_records: List[Dict]) -> bool:
        """Save funding rate data to cloud database"""
        try:
            if not funding_records:
                warning("No funding data to save")
                return False
            
            query = '''
                INSERT INTO funding_rates (
                    timestamp, symbol, funding_rate, annual_rate,
                    mark_price, open_interest, event_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            
            success_count = 0
            for record in funding_records:
                params = (
                    record.get('event_time'),  # Use event_time as timestamp
                    record.get('symbol'),
                    record.get('funding_rate'),
                    record.get('annual_rate'),
                    record.get('mark_price'),
                    record.get('open_interest'),
                    record.get('event_time')
                )
                
                result = self.execute_query(query, params, fetch=False)
                if result:
                    success_count += 1
            
            info(f"✅ Saved {success_count}/{len(funding_records)} funding records to cloud")
            return success_count > 0
            
        except Exception as e:
            error(f"Failed to save funding data: {e}")
            return False
    
    def save_funding_analytics(self, analytics_records: List[Dict]) -> bool:
        """Save funding analytics to cloud database"""
        try:
            if not analytics_records:
                warning("No funding analytics to save")
                return False
            
            query = '''
                INSERT INTO funding_analytics (
                    timestamp, symbol, rate_change_pct, trend,
                    alert_level, timeframe, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            
            success_count = 0
            for record in analytics_records:
                params = (
                    record.get('timestamp'),
                    record.get('symbol'),
                    record.get('rate_change_pct'),
                    record.get('trend'),
                    record.get('alert_level'),
                    record.get('timeframe'),
                    json.dumps(record.get('metadata', {}))
                )
                
                result = self.execute_query(query, params, fetch=False)
                if result:
                    success_count += 1
            
            info(f"✅ Saved {success_count}/{len(analytics_records)} funding analytics to cloud")
            return success_count > 0
            
        except Exception as e:
            error(f"Failed to save funding analytics: {e}")
            return False
    
    def save_liquidation_events(self, events_list: List[Dict]) -> bool:
        """Save liquidation events to cloud database"""
        try:
            if not events_list:
                warning("No liquidation events to save")
                return False
            
            query = '''
                INSERT INTO liquidation_events (
                    timestamp, event_time, exchange, symbol, side, price, quantity, usd_value,
                    order_type, time_in_force, average_price, mark_price, index_price,
                    price_impact_bps, spread_bps, cumulative_1m_usd, cumulative_5m_usd,
                    cumulative_15m_usd, event_velocity_1m, cascade_score, cluster_size,
                    bid_depth_10bps, ask_depth_10bps, imbalance_ratio, volatility_1h,
                    volatility_percentile, volume_1h, oi_change_1h_pct, concurrent_exchanges,
                    cross_exchange_lag_ms, dominant_exchange, event_id, batch_id, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            success_count = 0
            for event in events_list:
                params = (
                    event.get('timestamp'),
                    event.get('event_time'),
                    event.get('exchange'),
                    event.get('symbol'),
                    event.get('side'),
                    event.get('price'),
                    event.get('quantity'),
                    event.get('usd_value'),
                    event.get('order_type'),
                    event.get('time_in_force'),
                    event.get('average_price'),
                    event.get('mark_price'),
                    event.get('index_price'),
                    event.get('price_impact_bps'),
                    event.get('spread_bps'),
                    event.get('cumulative_1m_usd'),
                    event.get('cumulative_5m_usd'),
                    event.get('cumulative_15m_usd'),
                    event.get('event_velocity_1m'),
                    event.get('cascade_score'),
                    event.get('cluster_size'),
                    event.get('bid_depth_10bps'),
                    event.get('ask_depth_10bps'),
                    event.get('imbalance_ratio'),
                    event.get('volatility_1h'),
                    event.get('volatility_percentile'),
                    event.get('volume_1h'),
                    event.get('oi_change_1h_pct'),
                    event.get('concurrent_exchanges'),
                    event.get('cross_exchange_lag_ms'),
                    event.get('dominant_exchange'),
                    event.get('event_id'),
                    event.get('batch_id'),
                    json.dumps(event.get('metadata', {}))
                )
                
                result = self.execute_query(query, params, fetch=False)
                if result:
                    success_count += 1
            
            info(f"✅ Saved {success_count}/{len(events_list)} liquidation events to cloud")
            return success_count > 0
            
        except Exception as e:
            error(f"Failed to save liquidation events: {e}")
            return False
    
    def save_liquidation_analytics(self, analytics_records: List[Dict]) -> bool:
        """Save liquidation analytics to cloud database"""
        try:
            if not analytics_records:
                warning("No liquidation analytics to save")
                return False
            
            query = '''
                INSERT INTO liquidation_analytics (
                    timestamp, symbol, window_minutes, long_liquidations, short_liquidations,
                    total_liquidations, long_count, short_count, dominant_side,
                    exchanges_active, avg_cascade_score, max_cluster_size, total_events, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            success_count = 0
            for record in analytics_records:
                params = (
                    record.get('timestamp'),
                    record.get('symbol'),
                    record.get('window_minutes'),
                    record.get('long_liquidations'),
                    record.get('short_liquidations'),
                    record.get('total_liquidations'),
                    record.get('long_count'),
                    record.get('short_count'),
                    record.get('dominant_side'),
                    record.get('exchanges_active'),
                    record.get('avg_cascade_score'),
                    record.get('max_cluster_size'),
                    record.get('total_events'),
                    json.dumps(record.get('metadata', {}))
                )
                
                result = self.execute_query(query, params, fetch=False)
                if result:
                    success_count += 1
            
            info(f"✅ Saved {success_count}/{len(analytics_records)} liquidation analytics to cloud")
            return success_count > 0
            
        except Exception as e:
            error(f"Failed to save liquidation analytics: {e}")
            return False
    
    def get_recent_liquidations(self, symbol: str = None, hours: int = 24) -> List[Dict]:
        """Get recent liquidation events from cloud database"""
        try:
            if symbol:
                query = '''
                    SELECT timestamp, event_time, exchange, symbol, side, price, quantity, usd_value,
                           cascade_score, cluster_size, concurrent_exchanges, metadata
                    FROM liquidation_events
                    WHERE symbol = %s AND event_time > NOW() - INTERVAL '%s hours'
                    ORDER BY event_time DESC
                '''
                params = (symbol, hours)
            else:
                query = '''
                    SELECT timestamp, event_time, exchange, symbol, side, price, quantity, usd_value,
                           cascade_score, cluster_size, concurrent_exchanges, metadata
                    FROM liquidation_events
                    WHERE event_time > NOW() - INTERVAL '%s hours'
                    ORDER BY event_time DESC
                '''
                params = (hours,)
            
            return self.execute_query(query, params)
            
        except Exception as e:
            error(f"Failed to get recent liquidations: {e}")
            return []
    
    def get_funding_history(self, symbol: str = None, days: int = 7) -> List[Dict]:
        """Get funding rate history from cloud database"""
        try:
            if symbol:
                query = '''
                    SELECT timestamp, symbol, funding_rate, annual_rate, 
                           mark_price, open_interest, event_time
                    FROM funding_rates
                    WHERE symbol = %s AND timestamp > NOW() - INTERVAL '%s days'
                    ORDER BY timestamp DESC
                '''
                params = (symbol, days)
            else:
                query = '''
                    SELECT timestamp, symbol, funding_rate, annual_rate,
                           mark_price, open_interest, event_time
                    FROM funding_rates
                    WHERE timestamp > NOW() - INTERVAL '%s days'
                    ORDER BY timestamp DESC
                '''
                params = (days,)
            
            return self.execute_query(query, params)
            
        except Exception as e:
            error(f"Failed to get funding history: {e}")
            return []
    
    def get_defi_database_backups(self, limit: int = 10) -> List[dict]:
        """Get recent DeFi database backups from cloud"""
        try:
            query = '''
                SELECT id, backup_id, timestamp, size_bytes, metadata
                FROM database_backups
                WHERE backup_type LIKE %s
                ORDER BY timestamp DESC
                LIMIT %s
            '''
            return self.execute_query(query, ('%defi%', limit))
        except Exception as e:
            warning(f"Failed to fetch DeFi backups: {e}")
            return []

    def close_all_connections(self):
        """Close all database connections"""
        with self.connection_lock:
            for conn in self.connection_pool:
                try:
                    conn.close()
                except:
                    pass
            self.connection_pool.clear()

# Global instance
_cloud_db_manager = None
_cloud_db_backoff_until = 0  # epoch seconds

def get_cloud_database_manager() -> Optional[CloudDatabaseManager]:
    """Get the global cloud database manager instance with universal REST fallback"""
    global _cloud_db_manager, _cloud_db_backoff_until
    now = time.time()
    
    # Check if we're in backoff period
    if now < _cloud_db_backoff_until:
        debug(f"Cloud database circuit breaker active: {_cloud_db_backoff_until - now:.1f}s remaining")
        # Even during backoff, try REST fallback
        return _get_rest_fallback()

    if _cloud_db_manager is None:
        # Try direct PostgreSQL connection first
        postgres_success = _try_postgres_connection()
        
        if postgres_success:
            return _cloud_db_manager
        
        # If PostgreSQL fails, try REST fallback immediately
        info("🔄 PostgreSQL connection failed, attempting REST API fallback...")
        return _get_rest_fallback()

    # If we have a manager, test if it's still working
    if hasattr(_cloud_db_manager, '_test_connection'):
        try:
            if not _cloud_db_manager._test_connection():
                warning("⚠️ Cloud database connection lost, switching to REST fallback")
                return _get_rest_fallback()
        except Exception:
            warning("⚠️ Cloud database connection test failed, switching to REST fallback")
            return _get_rest_fallback()

    return _cloud_db_manager

def _try_postgres_connection() -> bool:
    """Try to establish PostgreSQL connection"""
    global _cloud_db_manager, _cloud_db_backoff_until
    now = time.time()
    
    try:
        # Check if psycopg2 is available
        if not PSYCOPG2_AVAILABLE:
            debug("psycopg2 not available - using REST fallback")
            return False
        
        # Check if we have valid PostgreSQL environment variables
        postgres_host = os.environ.get('POSTGRES_HOST', '').strip()
        postgres_user = os.environ.get('POSTGRES_USER', '').strip()
        postgres_password = os.environ.get('POSTGRES_PASSWORD', '').strip()
        
        if not (postgres_host and postgres_user and postgres_password):
            debug("PostgreSQL not configured - using REST fallback")
            return False

        # Try to create PostgreSQL manager
        _cloud_db_manager = CloudDatabaseManager()
        info("✅ PostgreSQL cloud database connection established")
        return True
        
    except Exception as e:
        msg = str(e).lower()
        
        # Determine backoff duration based on error type
        if any(s in msg for s in [
            "no address associated with hostname",
            "getaddrinfo failed", 
            "name or service not known",
            "temporary failure in name resolution",
        ]):
            backoff = 900  # 15 minutes
            error_type = "DNS resolution"
        elif any(s in msg for s in [
            "network is unreachable",
            "connection timed out",
            "could not connect to server",
        ]):
            backoff = 600  # 10 minutes
            error_type = "Network connectivity"
        else:
            backoff = 300  # 5 minutes
            error_type = "Database connection"
        
        warning(f"PostgreSQL connection failed ({error_type}): {e}", file_only=True)
        warning(f"Circuit breaker activated for {backoff//60} minutes - using REST fallback", file_only=True)
        _cloud_db_backoff_until = now + backoff
        _cloud_db_manager = None
        return False

def _get_rest_fallback() -> Optional[CloudDatabaseManager]:
    """Get REST API fallback manager"""
    global _cloud_db_manager
    
    try:
        supabase_url = os.getenv('SUPABASE_URL', '').strip()
        supabase_service = os.getenv('SUPABASE_SERVICE_ROLE', '').strip()
        
        if not (supabase_url and supabase_service):
            warning("⚠️ Supabase REST API not configured - no cloud database available")
            return None
        
        # Create REST manager
        from src.scripts.database.cloud_database_rest import RestDatabaseManager
        _cloud_db_manager = RestDatabaseManager()
        info("✅ REST API cloud database fallback established", file_only=True)
        
        # Log the fallback switch
        # DISABLED: data_sync_logger was removed in Phase 5 cleanup
        # from src.scripts.data_sync_logger import log_sync_event
        # log_sync_event('Database', 'REST_FALLBACK_ACTIVATED', 'success', 
        #               {'reason': 'PostgreSQL connection failed'})
        
        return _cloud_db_manager
        
    except Exception as e:
        error(f"❌ REST API fallback also failed: {e}")
        _cloud_db_manager = None
        return None


# ==========================================
# RBI AGENT DATABASE FUNCTIONS
# ==========================================

def save_rbi_strategy_result(strategy_data: Dict) -> bool:
    """
    Save RBI strategy result to cloud database

    Args:
        strategy_data: Dictionary containing strategy information
            - strategy_name: Name of the strategy
            - strategy_type: 'youtube', 'pdf', or 'text'
            - source_url: Original source URL (if applicable)
            - research_content: Full research analysis text
            - backtest_code: Generated backtest code
            - performance_metrics: Dict of performance metrics
            - sharpe_ratio: Sharpe ratio (optional)
            - win_rate: Win rate percentage (optional)
            - max_drawdown: Max drawdown percentage (optional)
            - total_return: Total return percentage (optional)
            - total_trades: Number of trades (optional)
            - execution_status: 'success', 'failed', or 'pending'
            - execution_errors: Error messages if failed (optional)
            - ai_model_used: AI model that generated the strategy
            - processing_time_seconds: Time taken to process
            - metadata: Additional metadata (optional)

    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        db_manager = get_cloud_database_manager()
        if not db_manager:
            warning("No cloud database available for RBI results")
            return False

        # Prepare the data
        performance_metrics = strategy_data.get('performance_metrics', {})
        if isinstance(performance_metrics, dict):
            performance_metrics = json.dumps(performance_metrics)
        else:
            performance_metrics = '{}'

        metadata = strategy_data.get('metadata', {})
        if isinstance(metadata, dict):
            metadata = json.dumps(metadata)
        else:
            metadata = '{}'

        query = '''
            INSERT INTO rbi_strategy_results (
                strategy_name, strategy_type, source_url, research_content, backtest_code,
                performance_metrics, sharpe_ratio, win_rate, max_drawdown, total_return,
                total_trades, execution_status, execution_errors, ai_model_used,
                processing_time_seconds, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''

        params = (
            strategy_data.get('strategy_name', 'Unknown'),
            strategy_data.get('strategy_type', 'unknown'),
            strategy_data.get('source_url'),
            strategy_data.get('research_content'),
            strategy_data.get('backtest_code'),
            performance_metrics,
            strategy_data.get('sharpe_ratio'),
            strategy_data.get('win_rate'),
            strategy_data.get('max_drawdown'),
            strategy_data.get('total_return'),
            strategy_data.get('total_trades'),
            strategy_data.get('execution_status', 'pending'),
            strategy_data.get('execution_errors'),
            strategy_data.get('ai_model_used'),
            strategy_data.get('processing_time_seconds'),
            metadata
        )

        success = db_manager.execute_query(query, params, fetch=False)
        if success:
            info(f"✅ Saved RBI strategy result: {strategy_data.get('strategy_name')}")
        else:
            error(f"❌ Failed to save RBI strategy result: {strategy_data.get('strategy_name')}")

        return success

    except Exception as e:
        error(f"❌ Error saving RBI strategy result: {e}")
        return False


def get_rbi_strategy_results(limit: int = 100, strategy_type: str = None) -> List[Dict]:
    """
    Retrieve RBI strategy results from cloud database

    Args:
        limit: Maximum number of results to return
        strategy_type: Filter by strategy type ('youtube', 'pdf', 'text')

    Returns:
        List of strategy result dictionaries
    """
    try:
        db_manager = get_cloud_database_manager()
        if not db_manager:
            warning("No cloud database available for RBI results")
            return []

        query = '''
            SELECT id, timestamp, strategy_name, strategy_type, source_url,
                   research_content, backtest_code, performance_metrics,
                   sharpe_ratio, win_rate, max_drawdown, total_return,
                   total_trades, execution_status, execution_errors,
                   ai_model_used, processing_time_seconds, metadata
            FROM rbi_strategy_results
        '''

        params = []
        if strategy_type:
            query += ' WHERE strategy_type = %s'
            params.append(strategy_type)

        query += ' ORDER BY timestamp DESC LIMIT %s'
        params.append(limit)

        results = db_manager.execute_query(query, params, fetch=True)

        # Parse JSON fields
        for result in results:
            if result.get('performance_metrics'):
                try:
                    result['performance_metrics'] = json.loads(result['performance_metrics'])
                except:
                    result['performance_metrics'] = {}

            if result.get('metadata'):
                try:
                    result['metadata'] = json.loads(result['metadata'])
                except:
                    result['metadata'] = {}

        info(f"📊 Retrieved {len(results)} RBI strategy results")
        return results

    except Exception as e:
        error(f"❌ Error retrieving RBI strategy results: {e}")
        return []


def get_rbi_strategy_stats() -> Dict:
    """
    Get statistics about RBI strategy results

    Returns:
        Dictionary with statistics
    """
    try:
        db_manager = get_cloud_database_manager()
        if not db_manager:
            return {"error": "No cloud database available"}

        # Get basic counts
        query = '''
            SELECT
                COUNT(*) as total_strategies,
                COUNT(CASE WHEN execution_status = 'success' THEN 1 END) as successful_strategies,
                COUNT(CASE WHEN strategy_type = 'youtube' THEN 1 END) as youtube_strategies,
                COUNT(CASE WHEN strategy_type = 'pdf' THEN 1 END) as pdf_strategies,
                COUNT(CASE WHEN strategy_type = 'text' THEN 1 END) as text_strategies,
                AVG(processing_time_seconds) as avg_processing_time,
                MAX(timestamp) as latest_strategy_date
            FROM rbi_strategy_results
        '''

        results = db_manager.execute_query(query, fetch=True)
        if not results:
            return {"error": "No data available"}

        stats = results[0]

        # Get performance stats for successful strategies
        perf_query = '''
            SELECT
                AVG(sharpe_ratio) as avg_sharpe,
                AVG(win_rate) as avg_win_rate,
                AVG(max_drawdown) as avg_max_drawdown,
                AVG(total_return) as avg_total_return,
                AVG(total_trades) as avg_trades
            FROM rbi_strategy_results
            WHERE execution_status = 'success'
            AND sharpe_ratio IS NOT NULL
        '''

        perf_results = db_manager.execute_query(perf_query, fetch=True)
        if perf_results:
            stats.update(perf_results[0])

        return stats

    except Exception as e:
        error(f"❌ Error getting RBI strategy stats: {e}")
        return {"error": str(e)}
