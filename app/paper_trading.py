"""
Paper Trading Module with Enhanced Trade Simulation
"""

import os
import json
import time
import pandas as pd
from datetime import datetime
import sqlite3
from pathlib import Path
# Local imports with fallback for relative imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
    from src.config import (
        PAPER_TRADING_ENABLED, 
        PAPER_INITIAL_BALANCE, 
        PAPER_TRADING_SLIPPAGE,
        PAPER_TRADING_RESET_ON_START,
        SOL_TARGET_PERCENT,
        USDC_TARGET_PERCENT
    )
except ImportError:
    # Try relative imports when running from test directory
    try:
        from src.scripts.shared_services.logger import debug, info, warning, error, critical
        from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
        from src.config import (
            PAPER_TRADING_ENABLED, 
            PAPER_INITIAL_BALANCE, 
            PAPER_TRADING_SLIPPAGE,
            PAPER_TRADING_RESET_ON_START,
            SOL_TARGET_PERCENT,
            USDC_TARGET_PERCENT
        )
    except ImportError:
        # Fallback to default values if all imports fail
        debug = info = warning = error = critical = print
        # Fallback config values
        PAPER_TRADING_ENABLED = True
        PAPER_INITIAL_BALANCE = 1000.0
        PAPER_TRADING_SLIPPAGE = 104
        PAPER_TRADING_RESET_ON_START = True
        SOL_TARGET_PERCENT = 0.5
        USDC_TARGET_PERCENT = 0.5

import asyncio
import random
from typing import List, Tuple

def format_price(price: float) -> str:
    """Format price with appropriate precision for display"""
    if price is None or price <= 0:
        return "$0.0000"
    
    # Use exponential notation for very small prices or prices with more than 3 decimal places
    if price < 0.0001:
        return f"${price:.2e}"
    # Use 4 decimal places for small prices, but check if it needs exponential notation
    elif price < 1.0:
        # Check if the price has more than 3 significant decimal places
        price_str = f"{price:.4f}"
        if len(price_str.split('.')[1].rstrip('0')) > 3:
            return f"${price:.2e}"
        return f"${price_str}"
    # Use 2 decimal places for normal prices
    else:
        return f"${price:.2f}"

# Create data directory if it doesn't exist
data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(data_dir, exist_ok=True)

# SQLite database for paper trading
DB_PATH = os.path.join(data_dir, 'paper_trading.db')

def get_paper_trading_db():
    """Get paper trading database connection with Windows-safe settings"""
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    
    # Register connection with reset manager for proper cleanup
    try:
        from src.scripts.database_reset_manager import get_database_reset_manager
        manager = get_database_reset_manager()
        manager.register_connection(conn)
    except ImportError:
        pass  # Reset manager not available
    
    return conn

def init_paper_trading_db():
    """Initialize paper trading database"""
    with get_paper_trading_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_portfolio (
        token_address TEXT PRIMARY KEY,
        amount REAL,
            last_price REAL,
            last_update INTEGER
        )""")
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
        token_address TEXT,
        action TEXT,
        amount REAL,
        price REAL,
        usd_value REAL,
            agent TEXT
        )""")
        
        # Add staking support tables
        conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trading_balances (
        wallet_address TEXT PRIMARY KEY,
        usdc_balance REAL DEFAULT 0.0,
        sol_balance REAL DEFAULT 0.0,
        staked_sol_balance REAL DEFAULT 0.0,
        staking_rewards REAL DEFAULT 0.0,
        last_updated TEXT
        )""")
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_staking_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        protocol TEXT,
        amount_sol REAL,
        apy REAL,
        daily_reward_sol REAL,
        transaction_type TEXT,
        status TEXT
        )""")
        
        # Add metadata migration
        _migrate_paper_trading_for_metadata(conn)

def _migrate_paper_trading_for_metadata(conn):
    """Add metadata columns to paper trading tables"""
    import sqlite3
    try:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN token_symbol TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN token_name TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE paper_portfolio ADD COLUMN token_symbol TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE paper_portfolio ADD COLUMN token_name TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE paper_portfolio ADD COLUMN normalized_symbol TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass

def reset_paper_trading():
    """Reset paper trading to initial state using database reset manager"""
    try:
        from src.scripts.database.database_reset_manager import reset_paper_trading_database
        return reset_paper_trading_database()
    except Exception as e:
        error(f"Error resetting paper trading: {str(e)}")
        return False

def _is_database_empty():
    """Check if the paper trading database is empty"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM paper_portfolio")
            count = cursor.fetchone()[0]
            return count == 0
    except Exception:
        return True

def _set_initial_balances():
    """Set initial balances in the paper trading database - START WITH 100% SOL"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # NEW: ensure idempotency
            conn.execute("DELETE FROM paper_portfolio")

            # Start with 100% SOL (no USDC initially)
            # Get real SOL price from price service
            use_usdc = False
            try:
                from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
                price_service = get_optimized_price_service()
                sol_price = price_service.get_price('So11111111111111111111111111111111111111112')
                if not sol_price or sol_price <= 0:
                    use_usdc = True
            except Exception:
                use_usdc = True

            if use_usdc:
                # Initialize with 100% USDC to avoid wrong prices
                usdc_amount = PAPER_INITIAL_BALANCE  # USDC is $1
                conn.execute(
                    "INSERT OR REPLACE INTO paper_portfolio (token_address, amount, last_price, last_update, token_symbol, token_name, normalized_symbol) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", usdc_amount, 1.0, int(time.time()), "USDC", "USD Coin", "USDC")
                )
                sol_amount = 0.0
                sol_price = None
                info(f"Paper trading reset to initial state: 100% USDC (${usdc_amount:.2f} USDC = ${PAPER_INITIAL_BALANCE:.2f})")
            else:
                sol_amount = PAPER_INITIAL_BALANCE / sol_price
                # Add initial SOL (100% allocation)
                conn.execute(
                    "INSERT OR REPLACE INTO paper_portfolio (token_address, amount, last_price, last_update, token_symbol, token_name, normalized_symbol) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("So11111111111111111111111111111111111111112", sol_amount, sol_price, int(time.time()), "SOL", "Solana", "SOL")
                )
                info(f"Paper trading reset to initial state: 100% SOL ({sol_amount:.4f} SOL @ ${sol_price:.2f} = ${PAPER_INITIAL_BALANCE:.2f})")
            
            # Initialize staking balances
            from src.config import address
            if address:
                conn.execute('''
                        INSERT OR REPLACE INTO paper_trading_balances 
                        (wallet_address, usdc_balance, sol_balance, staked_sol_balance, staking_rewards, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        address,
                        PAPER_INITIAL_BALANCE if use_usdc else 0.0,
                        sol_amount,
                        0.0,
                        0.0,
                        datetime.now().isoformat()
                    ))
    except Exception as e:
        error(f"Error resetting paper trading: {e}")

def get_paper_portfolio():
    """Get current paper trading portfolio"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query("SELECT * FROM paper_portfolio", conn)
            return df
    except Exception as e:
        error(f"Error getting paper portfolio: {e}")
        return pd.DataFrame()

def get_paper_trades(limit=5):
    """Get recent paper trades"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM paper_trades ORDER BY timestamp DESC LIMIT ?",
                conn,
                params=(limit,)
            )
            return df
    except Exception as e:
        error(f"Error getting paper trades: {e}")
        return pd.DataFrame()

def get_portfolio_value():
    """Calculate total portfolio value in USD for paper trading"""
    try:
        portfolio_df = get_paper_portfolio()
        if portfolio_df.empty:
            return 0.0
        
        total_value = 0.0
        price_service = get_optimized_price_service()
        
        # Track price updates to persist back to database
        price_updates = []
        timestamp = int(time.time())
        
        for _, row in portfolio_df.iterrows():
            token_address = row['token_address']
            amount = row['amount']
            
            if amount <= 0:
                continue
            
            # USDC is always $1
            if token_address == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
                current_price = None  # No fallback price
                total_value += amount
                continue
            
            # Get current price for all other tokens
            current_price = price_service.get_price(token_address)
            
            if current_price and isinstance(current_price, (int, float)) and current_price > 0:
                token_value = amount * current_price
                total_value += token_value
                # Queue price update for database
                price_updates.append((current_price, timestamp, token_address))
            else:
                # Fallback to last known price if current price unavailable
                last_price = row['last_price']
                if last_price and last_price > 0:
                    token_value = amount * last_price
                    total_value += token_value
        
        # Update database with fresh prices
        if price_updates:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.executemany(
                        "UPDATE paper_portfolio SET last_price = ?, last_update = ? WHERE token_address = ?",
                        price_updates
                    )
            except Exception as e:
                debug(f"Failed to update prices in database: {e}")
        
        return total_value
        
    except Exception as e:
        error(f"Error calculating paper portfolio value: {e}")
        return 0.0

def get_token_balance(token_mint: str) -> float:
    """Get token balance for a specific mint in paper trading portfolio"""
    try:
        portfolio_df = get_paper_portfolio()
        if portfolio_df.empty:
            return 0.0
        
        # Find the token in the portfolio
        token_row = portfolio_df[portfolio_df['token_address'] == token_mint]
        if token_row.empty:
            return 0.0
        
        return float(token_row.iloc[0]['amount'])
    except Exception as e:
        error(f"Error getting token balance for {token_mint}: {e}")
        return 0.0

def split_order_into_chunks(amount: float, min_chunk_percent: float = 0.1, max_chunk_percent: float = 0.3) -> List[float]:
    """
    Split a large order into smaller chunks for realistic fill simulation
    
    Args:
        amount: Total amount to split
        min_chunk_percent: Minimum chunk size as percentage of remaining
        max_chunk_percent: Maximum chunk size as percentage of remaining
        
    Returns:
        List of chunk sizes that sum to the original amount
    """
    chunks = []
    remaining = amount
    
    while remaining > 0:
        # Last chunk handles any remaining amount
        if remaining < amount * 0.1:  # If less than 10% remains
            chunks.append(remaining)
            break
            
        # Random chunk size between min and max percent of remaining
        chunk_size = remaining * random.uniform(min_chunk_percent, max_chunk_percent)
        chunk_size = round(chunk_size, 8)  # Round to 8 decimal places
        chunks.append(chunk_size)
        remaining -= chunk_size
    
    return chunks

async def execute_paper_trade_with_delay(
    token_address: str,
    action: str,
    amount: float,
    price: float,
    agent: str = "unknown"
) -> Tuple[bool, str]:
    """
    Execute a paper trade with realistic delay simulation
    
    Args:
        token_address: Token mint address
        action: Trade action (BUY, SELL, etc.)
        amount: Trade amount in token units
        price: Base price for the trade
        agent: Name of agent executing the trade
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Simulate network latency (0.1-0.5s)
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # Get price service for slippage calculation
        price_service = get_optimized_price_service()
        
        # Calculate execution price with slippage
        execution_price = price_service.get_price_with_slippage(
            token_address, amount, action.lower()
        )
        if execution_price is None:
            return False, "Failed to get execution price"
        
        # For large orders, simulate partial fills
        if amount * price > 10000:  # Orders over $10k
            chunks = split_order_into_chunks(amount)
            success = True
            
            for chunk in chunks:
                # Simulate exchange processing delay between fills
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
                # Execute chunk with slippage price
                if not execute_paper_trade(token_address, action, chunk, execution_price, agent):
                    success = False
                    break
            
            return success, "Large order executed with partial fills"
        else:
            # Small orders execute immediately
            success = execute_paper_trade(token_address, action, amount, execution_price, agent)
            return success, "Order executed"
            
    except Exception as e:
        error(f"Error in delayed paper trade execution: {e}")
        return False, f"Execution error: {str(e)}"

def execute_paper_trade(token_address: str, action: str, amount: float, price: float, agent: str = "unknown", token_symbol: str = None, token_name: str = None):
    """Execute a paper trade with optional metadata"""
    try:
        # If metadata not provided, fetch it
        if not token_symbol or not token_name:
            try:
                from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
                metadata_service = get_token_metadata_service()
                metadata = metadata_service.get_metadata(token_address)
                if metadata:
                    token_symbol = metadata.get('symbol', 'UNK')
                    token_name = metadata.get('name', 'Unknown Token')
            except:
                pass
        
        token_symbol = token_symbol or 'UNK'
        token_name = token_name or 'Unknown Token'

        # Normalize token symbol for consistent storage and lookup
        try:
            from src.nice_funcs import normalize_token_symbol
            normalized_symbol = normalize_token_symbol(token_symbol)
        except ImportError:
            # Fallback normalization
            normalized_symbol = token_symbol.upper().replace(' ', '').replace('-', '').replace('_', '')

        token_symbol = normalized_symbol
        
        # NEW: Log all paper trade attempts for diagnostics
        usd_value = amount * price
        debug(f"📝 Paper trade attempt: {action} {amount:.4f} tokens @ ${price:.4f} (${usd_value:.2f}) by {agent}")
        
        # SECURITY: Check for excluded tokens (unless agent is harvesting/risk for rebalancing)
        try:
            from src.config import EXCLUDED_TOKENS, REBALANCING_ALLOWED_TOKENS, SOL_ADDRESS, USDC_ADDRESS
            
            if token_address in EXCLUDED_TOKENS:
                # Allow harvesting and copybot agents to trade excluded tokens for rebalancing
                # Risk agent is blocked from trading SOL/USDC - should only close risky positions
                if agent not in ["harvesting", "harvesting_agent", "copybot", "copybot_agent"] and token_address not in REBALANCING_ALLOWED_TOKENS:
                    error(f"❌ Paper trading blocked: {agent} cannot trade excluded token {token_address[:8]}...")
                    return False
                elif agent == "risk":
                    error(f"❌ Paper trading blocked: Risk agent cannot trade {token_address[:8]}... - should only close risky positions")
                    return False
                else:
                    # Only show "for rebalancing" for harvesting agents
                    if agent in ["harvesting", "harvesting_agent"]:
                        debug(f"✅ Paper trading allowed: {agent} can trade {token_address[:8]}... for rebalancing")
                    else:
                        debug(f"✅ Paper trading allowed: {agent} can trade {token_address[:8]}...")
        except ImportError:
            pass  # Config not available, proceed
        
        # CRITICAL: Position validation before executing trade
        try:
            from src.scripts.trading.position_validator import validate_position_exists, validate_usdc_balance
            
            if action == "BUY":
                # Validate USDC balance before buying
                usdc_valid, usdc_reason = validate_usdc_balance(amount * price, agent)
                if not usdc_valid:
                    error(f"🚫 Paper trade blocked - USDC validation failed: {usdc_reason}")
                    return False
            elif action == "SELL":
                # Validate position exists before selling
                position_valid, position_reason = validate_position_exists(token_address, amount, agent)
                if not position_valid:
                    error(f"🚫 Paper trade blocked - position validation failed: {position_reason}")
                    return False
        except ImportError:
            warning(f"Position validator not available - skipping validation")
        except Exception as e:
            warning(f"Position validation error: {e}")
        
        # Ensure proper decimal handling for token amounts
        # Round to 6 decimal places to avoid floating point precision issues
        amount = round(amount, 6)
        price = round(price, 6)
        
        # Reject invalid prices
        if not price or price <= 0:
            error(f"Rejecting trade with invalid price ${price} for {token_address[:8]}... - no real market price available")
            return False
            
        usd_value = round(amount * price, 2)
        
        # CRITICAL: Final trade value validation to prevent unrealistic sells
        if action == "SELL":
            try:
                from src.paper_trading import get_portfolio_value
                portfolio_value = get_portfolio_value()
                if usd_value > portfolio_value * 1.1:
                    error(f"🚫 Rejecting unrealistic sell: ${usd_value:.2f} > portfolio ${portfolio_value:.2f}")
                    return False
            except Exception as e:
                warning(f"⚠️ Could not validate trade value: {e}")
        
        timestamp = int(time.time())
        
        # 🌐 Save transaction to cloud database for synchronization
        try:
            from src.scripts.database.cloud_database import get_cloud_database_manager
            db_manager = get_cloud_database_manager()
            if db_manager:
                # Prepare transaction data for cloud database
                transaction_data = {
                    'transaction_id': f"{token_address}_{action}_{timestamp}_{int(amount * 1000000)}",
                    'token_symbol': token_symbol,
                    'transaction_type': action.upper(),
                    'token_mint': token_address,
                    'amount': amount,
                    'price_usd': price,
                    'value_usd': usd_value,
                    'usdc_amount': usd_value if action.upper() in ["SELL", "SHORT", "CLOSE"] else 0.0,
                    'sol_amount': amount if token_address == "So11111111111111111111111111111112" else 0.0,
                    'agent_name': agent,
                    'metadata': {
                        'local_timestamp': timestamp,
                        'local_db_path': DB_PATH
                    }
                }
                
                # Save to cloud database
                db_manager.save_paper_trading_transaction(transaction_data)
                debug("✅ Paper trading transaction saved to cloud database")
            else:
                debug("Cloud database not available - using local storage only")
        except Exception as e:
            warning(f"⚠️ Failed to save paper trading transaction to cloud database: {e}")
        
        with sqlite3.connect(DB_PATH) as conn:
            # Record the trade with metadata
            conn.execute(
                "INSERT INTO paper_trades (timestamp, token_address, action, amount, price, usd_value, agent, token_symbol, token_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (timestamp, token_address, action, amount, price, usd_value, agent, token_symbol, token_name)
            )
            
            # Update portfolio
            if action.upper() in ["BUY", "LONG"]:
                # Check if we have enough USDC
                usdc_row = conn.execute(
                    "SELECT amount FROM paper_portfolio WHERE token_address = ?",
                    ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",)
                ).fetchone()
                
                current_usdc = usdc_row[0] if usdc_row else 0.0
                
                # If not enough USDC, try to convert SOL to USDC
                if current_usdc < usd_value:
                    sol_row = conn.execute(
                        "SELECT amount FROM paper_portfolio WHERE token_address = ?",
                        ("So11111111111111111111111111111111111111112",)
                    ).fetchone()
                    
                    current_sol = sol_row[0] if sol_row else 0.0
                    
                    if current_sol > 0:
                        # Get SOL price to calculate how much SOL we need to sell
                        try:
                            # Try multiple import paths for price service
                            try:
                                from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
                                price_service = get_optimized_price_service()
                                sol_price = price_service.get_price("So11111111111111111111111111111111111111112")
                                if not sol_price:
                                    sol_price = 200.0
                            except ImportError:
                                # Fallback: use a reasonable SOL price
                                sol_price = 200.0
                                price_service = None
                            
                            if price_service:
                                sol_price = price_service.get_price("So11111111111111111111111111111111111111112") or 200.0
                            else:
                                sol_price = 200.0
                            sol_needed = (usd_value - current_usdc) / sol_price
                            
                            if sol_needed <= current_sol:
                                # Convert SOL to USDC
                                conn.execute(
                                    "UPDATE paper_portfolio SET amount = amount - ? WHERE token_address = ?",
                                    (sol_needed, "So11111111111111111111111111111111111111112")
                                )
                                conn.execute(
                                    "UPDATE paper_portfolio SET amount = amount + ? WHERE token_address = ?",
                                    (usd_value - current_usdc, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
                                )
                                
                                # Record the SOL->USDC conversion trade
                                conn.execute(
                                    "INSERT INTO paper_trades (timestamp, token_address, action, amount, price, usd_value, agent) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (timestamp, "So11111111111111111111111111111111111111112", "SELL", sol_needed, sol_price, usd_value - current_usdc, "conversion")
                                )
                                info(f"🔄 Converted {sol_needed:.4f} SOL to ${usd_value - current_usdc:.2f} USDC for trade")
                            else:
                                error(f"Insufficient SOL for conversion: need {sol_needed:.4f} SOL, have {current_sol:.4f} SOL")
                                return False
                        except Exception as e:
                            error(f"Error converting SOL to USDC: {e}")
                            return False
                    else:
                        error(f"Insufficient USDC for trade: ${usd_value:.2f} (no SOL available for conversion)")
                        return False
                
                # Deduct USDC
                conn.execute(
                    "UPDATE paper_portfolio SET amount = amount - ? WHERE token_address = ?",
                    (usd_value, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
                )
                
                # Add bought token with metadata
                conn.execute(
                    """
                    INSERT INTO paper_portfolio (token_address, amount, last_price, last_update, token_symbol, token_name, normalized_symbol)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(token_address) DO UPDATE SET
                        amount = amount + ?,
                        last_price = ?,
                        last_update = ?,
                        token_symbol = ?,
                        token_name = ?
                    """,
                    (token_address, amount, price, timestamp, token_symbol, token_name, normalized_symbol, amount, price, timestamp, token_symbol, token_name)
                )
                
                # CRITICAL FIX: Set entry price for unrealized gains calculation
                try:
                    from src.scripts.database.entry_price_tracker import EntryPriceTracker
                    # Force local database usage to avoid cloud connection issues
                    import src.scripts.database.entry_price_tracker as ept
                    original_cloud_available = ept.CLOUD_DB_AVAILABLE
                    ept.CLOUD_DB_AVAILABLE = False
                    
                    entry_tracker = EntryPriceTracker()
                    success = entry_tracker.set_entry_price(
                        mint=token_address,
                        entry_price_usd=price,
                        entry_amount=amount,
                        source="paper_trading_buy",
                        notes=f"Paper trading BUY at ${price:.6f}"
                    )
                    
                    # Restore original setting
                    ept.CLOUD_DB_AVAILABLE = original_cloud_available
                    
                    if success:
                        debug(f"✅ Entry price set for {token_address[:8]}...: ${price:.6f}")
                    else:
                        warning(f"⚠️ Failed to set entry price for {token_address[:8]}...")
                except Exception as e:
                    warning(f"⚠️ Failed to set entry price for {token_address[:8]}...: {e}")
                
                debug(f"Paper trade executed: BUY {amount:.4f} {token_address[:8]} @ ${price:.4f} (${usd_value:.2f})")
                return True
                
            elif action.upper() in ["SELL", "SHORT", "CLOSE"]:
                # Check if we have enough tokens
                token_row = conn.execute(
                    "SELECT amount FROM paper_portfolio WHERE token_address = ?",
                    (token_address,)
                ).fetchone()
                
                if not token_row or token_row[0] < amount:
                    error(f"Insufficient tokens for trade: {amount}")
                    return False
                
                # Add USDC (create entry if it doesn't exist)
                conn.execute(
                    """
                    INSERT INTO paper_portfolio (token_address, amount, last_price, last_update)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(token_address) DO UPDATE SET
                        amount = amount + ?,
                        last_price = ?,
                        last_update = ?
                    """,
                    ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", usd_value, 1.0, timestamp, usd_value, 1.0, timestamp)
                )
                
                # Remove sold tokens
                conn.execute(
                    "UPDATE paper_portfolio SET amount = amount - ? WHERE token_address = ?",
                    (amount, token_address)
                )
                
                # Remove token if balance is 0
                conn.execute(
                    "DELETE FROM paper_portfolio WHERE token_address = ? AND amount <= 0",
                    (token_address,)
                )
                
                # Record closed trade for wins/losses tracking
                # SKIP RECORDING FOR HARVESTING AGENT (it's rebalancing, not trading)
                if agent != "harvesting":
                    try:
                        from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
                        tracker = get_portfolio_tracker()
                        if tracker:
                            tracker.record_closed_trade(token_address, price, amount, token_symbol)
                    except Exception as e:
                        debug(f"Could not record closed trade: {e}")
                
                debug(f"Paper trade executed: SELL {amount:.4f} {token_address[:8]} @ ${price:.4f} (${usd_value:.2f})")
                return True
                
            elif action.upper() == "PARTIAL_CLOSE":
                # Check if we have enough tokens
                token_row = conn.execute(
                    "SELECT amount FROM paper_portfolio WHERE token_address = ?",
                    (token_address,)
                ).fetchone()
                
                if not token_row or token_row[0] < amount:
                    error(f"Insufficient tokens for partial close: {amount}")
                    return False
                
                # Add USDC (create entry if it doesn't exist)
                conn.execute(
                    """
                    INSERT INTO paper_portfolio (token_address, amount, last_price, last_update)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(token_address) DO UPDATE SET
                        amount = amount + ?,
                        last_price = ?,
                        last_update = ?
                    """,
                    ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", usd_value, 1.0, timestamp, usd_value, 1.0, timestamp)
                )
                
                # Remove sold tokens
                conn.execute(
                    "UPDATE paper_portfolio SET amount = amount - ? WHERE token_address = ?",
                    (amount, token_address)
                )
                
                # Record closed trade for wins/losses tracking
                # SKIP RECORDING FOR HARVESTING AGENT (it's rebalancing, not trading)
                if agent != "harvesting":
                    try:
                        from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
                        tracker = get_portfolio_tracker()
                        if tracker:
                            tracker.record_closed_trade(token_address, price, amount, token_symbol)
                    except Exception as e:
                        debug(f"Could not record closed trade: {e}")
                
                debug(f"Paper trade executed: PARTIAL_CLOSE {amount:.4f} {token_address[:8]} @ ${price:.4f} (${usd_value:.2f})")
                return True
                
            elif action.upper() in ["STAKE", "UNSTAKE"]:
                # Handle staking/unstaking actions
                if action.upper() == "STAKE":
                    # Check if we have enough SOL to stake
                    sol_row = conn.execute(
                        "SELECT amount FROM paper_portfolio WHERE token_address = ?",
                        ("So11111111111111111111111111111111111111112",)
                    ).fetchone()
                    
                    current_sol = sol_row[0] if sol_row else 0.0
                    
                    if current_sol < amount:
                        error(f"Insufficient SOL for staking: {amount} (have {current_sol})")
                        return False
                    
                    # Move SOL from regular balance to staked balance
                    conn.execute(
                        "UPDATE paper_portfolio SET amount = amount - ? WHERE token_address = ?",
                        (amount, "So11111111111111111111111111111111111111112")
                    )
                    
                    # Add to staked SOL balance (using a special token address for staked SOL)
                    staked_sol_address = "STAKED_SOL_So11111111111111111111111111111111111111112"
                    conn.execute(
                        """
                        INSERT INTO paper_portfolio (token_address, amount, last_price, last_update)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(token_address) DO UPDATE SET
                            amount = amount + ?,
                            last_price = ?,
                            last_update = ?
                        """,
                        (staked_sol_address, amount, price, timestamp, amount, price, timestamp)
                    )
                    
                    info(f"Paper staking executed: STAKE {amount:.4f} SOL @ ${price:.4f} (${usd_value:.2f})")
                    return True
                    
                elif action.upper() == "UNSTAKE":
                    # Check if we have enough staked SOL to unstake
                    staked_sol_address = "STAKED_SOL_So11111111111111111111111111111111111111112"
                    staked_row = conn.execute(
                        "SELECT amount FROM paper_portfolio WHERE token_address = ?",
                        (staked_sol_address,)
                    ).fetchone()
                    
                    current_staked = staked_row[0] if staked_row else 0.0
                    
                    if current_staked < amount:
                        error(f"Insufficient staked SOL for unstaking: {amount} (have {current_staked})")
                        return False
                    
                    # Move SOL from staked balance back to regular balance
                    conn.execute(
                        "UPDATE paper_portfolio SET amount = amount - ? WHERE token_address = ?",
                        (amount, staked_sol_address)
                    )
                    
                    # Add back to regular SOL balance
                    conn.execute(
                        """
                        INSERT INTO paper_portfolio (token_address, amount, last_price, last_update)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(token_address) DO UPDATE SET
                            amount = amount + ?,
                            last_price = ?,
                            last_update = ?
                        """,
                        ("So11111111111111111111111111111111111111112", amount, price, timestamp, amount, price, timestamp)
                    )
                    
                    # Remove staked SOL entry if balance is 0
                    conn.execute(
                        "DELETE FROM paper_portfolio WHERE token_address = ? AND amount <= 0",
                        (staked_sol_address,)
                    )
                    
                    info(f"Paper unstaking executed: UNSTAKE {amount:.4f} SOL @ ${price:.4f} (${usd_value:.2f})")
                    return True
                
            else:
                error(f"Invalid trade action: {action}")
                return False
            
    except Exception as e:
        error(f"Error executing paper trade: {e}")
    return False

def print_portfolio_status(include_history=True):
    """Print current paper trading portfolio status with accurate local data"""
    try:
        # Import colorama for colored output
        from colorama import Fore, Style
        
        # Get local portfolio data for accurate display
        local_portfolio = get_paper_portfolio()
        
        if local_portfolio.empty:
            print("\n📊 Paper Trading Portfolio Status:")
            print("==================================================")
            print("No positions")
            return
        
        # Calculate accurate portfolio data from local database
        local_positions = []
        local_total_value = 0
        sol_balance = 0
        usdc_balance = 0
        sol_value_usd = 0
        staked_sol_balance = 0
        staked_sol_value_usd = 0
        
        for _, row in local_portfolio.iterrows():
            token_address = row['token_address']
            amount = row['amount']
            price = row['last_price']
            value = amount * price
            local_total_value += value
            
            # Track SOL, Staked SOL, and USDC separately
            if token_address == "So11111111111111111111111111111111111111112":
                sol_balance = amount
                sol_value_usd = value
            elif token_address == "STAKED_SOL_So11111111111111111111111111111111111111112":
                staked_sol_balance = amount
                staked_sol_value_usd = value
            elif token_address == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
                usdc_balance = amount
            else:
                # Other positions
                local_positions.append({
                    'token': token_address,
                    'amount': amount,
                    'value': value,
                    'price': price
                })
        
        # Try to get cloud data for sync status indication
        cloud_portfolio = None
        try:
            from src.scripts.database.cloud_database import get_cloud_database_manager
            db_manager = get_cloud_database_manager()
            if db_manager:
                cloud_portfolio = db_manager.get_latest_paper_trading_portfolio()
        except Exception as e:
            debug(f"Cloud database access failed: {e}")
        
        # Display portfolio with accurate local data
        if cloud_portfolio:
            print("\n📊 Paper Trading Portfolio Status (Cloud Sync):")
        else:
            print("\n📊 Paper Trading Portfolio Status (Local):")
        print("==================================================")
        
        # Show SOL, Staked SOL, and USDC from local data
        if sol_balance > 0:
            sol_pct = (sol_value_usd / local_total_value * 100) if local_total_value > 0 else 0
            print(f"• SOL: {sol_balance:.4f} (${sol_value_usd:.2f} | {sol_pct:.1f}%)")
        
        if staked_sol_balance > 0:
            staked_sol_pct = (staked_sol_value_usd / local_total_value * 100) if local_total_value > 0 else 0
            print(f"• Staked SOL: {staked_sol_balance:.4f} (${staked_sol_value_usd:.2f} | {staked_sol_pct:.1f}%)")
        
        if usdc_balance > 0:
            usdc_pct = (usdc_balance / local_total_value * 100) if local_total_value > 0 else 0
            print(f"• USDC: {usdc_balance:.4f} (${usdc_balance:.2f} | {usdc_pct:.1f}%)")
        
        # Show other individual positions from local database
        for pos in sorted(local_positions, key=lambda x: x['value'], reverse=True):
            token = pos['token']
            amount = pos['amount']
            value = pos['value']
            price = pos['price']
            pct = (value / local_total_value * 100) if local_total_value > 0 else 0
            
            # Format token name
            token_name = token[:8] + "..." if len(token) > 8 else token
            # Format price with better precision for small values
            price_str = format_price(price)
            print(f"• {token_name}: {amount:.4f} @ {price_str} = ${value:.2f} ({pct:.1f}%)")
        
        print(f"{Fore.BLUE}=================================================={Style.RESET_ALL}")
        print(f"{Fore.GREEN}Total Portfolio Value: ${local_total_value:.2f}{Style.RESET_ALL}")
        
        # Calculate and display PnL
        pnl = local_total_value - PAPER_INITIAL_BALANCE
        if pnl >= 0:
            print(f"{Fore.GREEN}PnL: +${pnl:.2f}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}PnL: ${pnl:.2f}{Style.RESET_ALL}")
        
        # Show allocation status using local data
        print("")
        print(f"\n{Fore.BLUE}📈 Allocation Status:{Style.RESET_ALL}")
        print("--------------------------------------------------")
        sol_pct = (sol_value_usd / local_total_value * 100) if local_total_value > 0 else 0
        staked_sol_pct = (staked_sol_value_usd / local_total_value * 100) if local_total_value > 0 else 0
        usdc_pct = (usdc_balance / local_total_value * 100) if local_total_value > 0 else 0
        print(f"SOL:  Target {SOL_TARGET_PERCENT * 100}% | Actual {sol_pct:.1f}%")
        print(f"{Fore.MAGENTA}Staked SOL: Target 5.0% | Actual {staked_sol_pct:.1f}%{Style.RESET_ALL}")
        print(f"USDC: Target {USDC_TARGET_PERCENT * 100}% | Actual {usdc_pct:.1f}%")
        print(f"{Fore.BLUE}--------------------------------------------------{Style.RESET_ALL}")
        
        # Show Market Status section
        print("")
        print(f"\n{Fore.BLUE}📊 Market Status:{Style.RESET_ALL}")
        print("--------------------------------------------------")
        try:
            # Get real sentiment data from cloud database
            from src.scripts.sentiment_data_extractor import get_sentiment_data_extractor
            sentiment_extractor = get_sentiment_data_extractor()
            sentiment_data = sentiment_extractor.get_combined_sentiment_data()
            
            # Extract technical sentiment from chart analysis
            technical_sentiment = sentiment_data.chart_sentiment
            if technical_sentiment == 'NEUTRAL':
                technical_sentiment = 'Neutral'
            elif technical_sentiment == 'BULLISH':
                technical_sentiment = 'Strong Bullish'
            elif technical_sentiment == 'BEARISH':
                technical_sentiment = 'Strong Bearish'
            
            # Extract overall sentiment from Twitter analysis
            overall_sentiment = sentiment_data.twitter_classification
            if overall_sentiment == 'NEUTRAL':
                overall_sentiment = 'Neutral'
            elif overall_sentiment == 'BULLISH':
                overall_sentiment = 'Bullish'
            elif overall_sentiment == 'BEARISH':
                overall_sentiment = 'Bearish'
            
            # Color based on sentiment
            if 'strong bullish' in technical_sentiment.lower():
                tech_color = Fore.BLUE
            elif 'bullish' in technical_sentiment.lower():
                tech_color = Fore.CYAN
            elif 'strong bearish' in technical_sentiment.lower():
                tech_color = Fore.RED
            elif 'bearish' in technical_sentiment.lower():
                tech_color = Fore.LIGHTRED_EX
            else:
                tech_color = Fore.WHITE
            
            if 'strong bullish' in overall_sentiment.lower():
                sent_color = Fore.BLUE
            elif 'bullish' in overall_sentiment.lower():
                sent_color = Fore.CYAN
            elif 'strong bearish' in overall_sentiment.lower():
                sent_color = Fore.RED
            elif 'bearish' in overall_sentiment.lower():
                sent_color = Fore.LIGHTRED_EX
            else:
                sent_color = Fore.WHITE
            
            print(f"Technical: {tech_color}{technical_sentiment}{Style.RESET_ALL}")
            print(f"Sentiment: {sent_color}{overall_sentiment}{Style.RESET_ALL}")
        except Exception:
            print(f"Technical: {Fore.WHITE}Neutral{Style.RESET_ALL}")
            print(f"Sentiment: {Fore.WHITE}Neutral{Style.RESET_ALL}")
        print(f"{Fore.BLUE}--------------------------------------------------{Style.RESET_ALL}")
        
        # Show recent trades from cloud database if available
        print("")
        if include_history and cloud_portfolio:
            try:
                cloud_trades = db_manager.get_paper_trading_transactions(limit=10)
                if cloud_trades:
                    print(f"\n{Fore.BLUE}📜 Recent Trades (Cloud Sync):{Style.RESET_ALL}")
                    
                    # Calculate agent activity counts
                    from collections import Counter
                    agent_counts = Counter([t.get('agent_name', 'unknown') for t in cloud_trades])
                    summary_parts = [f"{agent.title()}: {count}" for agent, count in sorted(agent_counts.items())]
                    summary_line = "Agent Activity (Last 10 trades): " + " | ".join(summary_parts)
                    print(f"{Fore.YELLOW}{summary_line}{Style.RESET_ALL}")
                    
                    print(f"{Fore.BLUE}--------------------------------------------------{Style.RESET_ALL}")
                    for trade in cloud_trades:
                        # Get token symbol/name and mint address
                        token_mint = trade['token_mint']
                        if token_mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
                            token = "USDC"
                            mint_display = token_mint[:8] + "..."
                        elif token_mint == "So11111111111111111111111111111111111111112":
                            token = "SOL"
                            mint_display = token_mint[:8] + "..."
                        else:
                            token = token_mint[:8] + "..."
                            mint_display = token_mint[:8] + "..."
                        # Better timestamp handling - try multiple formats
                        ts = trade.get('timestamp')
                        timestamp = "Recent"
                        if ts:
                            try:
                                if hasattr(ts, 'strftime'):
                                    # It's a datetime object
                                    timestamp = ts.strftime('%H:%M:%S')
                                elif isinstance(ts, str):
                                    # It's a string, try to parse it
                                    from datetime import datetime
                                    if 'T' in ts:
                                        # ISO format
                                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                        timestamp = dt.strftime('%H:%M:%S')
                                    else:
                                        # Try other formats
                                        timestamp = ts[:8] if len(ts) >= 8 else ts
                                else:
                                    timestamp = str(ts)[:8]
                            except Exception:
                                timestamp = str(ts)[:8] if ts else "Recent"
                        
                        # Format price with better precision
                        price_str = format_price(trade['price_usd'])
                        
                        # Determine color based on transaction type
                        transaction_type = trade['transaction_type'].upper()
                        if transaction_type == 'BUY':
                            color_code = '\033[92m'  # Green
                        elif transaction_type == 'SELL':
                            color_code = '\033[91m'  # Red
                        elif transaction_type in ['STAKE', 'UNSTAKE']:
                            color_code = '\033[95m'  # Magenta
                        else:
                            color_code = '\033[97m'  # White
                        
                        reset_code = '\033[0m'  # Reset color
                        print(f"{color_code}{timestamp} | {transaction_type} {trade['amount']:.4f} {token} ({mint_display}) @ {price_str} (${trade['value_usd']:.2f}) - {trade['agent_name']}{reset_code}")
                    print(f"{Fore.BLUE}--------------------------------------------------{Style.RESET_ALL}")
            except Exception as e:
                debug(f"Failed to get cloud trades: {e}")
        
        # Add timestamp and webhook message
        print("")
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{Fore.YELLOW}🕒 {current_time}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}============================================================{Style.RESET_ALL}")
        print(f"{Fore.GREEN}📡 Webhook sent to webhook server{Style.RESET_ALL}")
        
    except Exception as e:
        error(f"Error printing portfolio status: {e}")

# Initialize database on import if enabled (but don't reset automatically)
if PAPER_TRADING_ENABLED:
    init_paper_trading_db()
