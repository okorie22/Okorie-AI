"""
🌙 Anarcho Capital's DeFi Position Manager
Persistent tracking and management of DeFi lending positions
Built with love by Anarcho Capital 🚀
"""

import sqlite3
import threading
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from src.scripts.shared_services.logger import debug, info, warning, error, critical

@dataclass
class DeFiPosition:
    """Represents a single DeFi position"""
    position_id: str
    loop_id: str
    iteration: int
    collateral_token: str
    collateral_amount_usd: float
    borrowed_amount_usd: float
    lending_protocol: str
    borrowing_protocol: str
    status: str  # 'active', 'unwinding', 'closed', 'liquidated'
    created_at: str  # ISO format timestamp
    updated_at: str  # ISO format timestamp
    liquidation_threshold: float
    current_collateral_ratio: float
    health_score: float

@dataclass
class DeFiLoop:
    """Represents a complete leverage loop"""
    loop_id: str
    initial_capital_usd: float
    total_exposure_usd: float
    leverage_ratio: float
    status: str  # 'active', 'completed', 'unwinding', 'liquidated'
    created_at: str  # ISO format timestamp
    closed_at: Optional[str] = None  # ISO format timestamp

@dataclass
class ReservedBalance:
    """Represents reserved token balances for DeFi operations"""
    token_address: str
    reserved_amount: float
    reserved_amount_usd: float
    reason: str  # 'defi_collateral', 'defi_borrowed'
    position_ids: List[str]  # List of position IDs using this token
    last_updated: str  # ISO format timestamp

class DeFiPositionManager:
    """
    Manages persistent storage and tracking of DeFi positions
    Provides coordination between agents to prevent conflicts
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
        """Initialize the DeFi position manager"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Database path
        self.db_path = Path(__file__).parent.parent.parent / 'data' / 'defi_positions.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-safe database operations
        self.db_lock = threading.RLock()
        
        # Initialize database schema
        self._init_database()
        
        info("\033[36m🔄 DeFi Position Manager initialized\033[0m")
    
    def _init_database(self):
        """Initialize database schema"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Create defi_positions table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS defi_positions (
                    position_id TEXT PRIMARY KEY,
                    loop_id TEXT,
                    iteration INTEGER,
                    collateral_token TEXT,
                    collateral_amount_usd REAL,
                    borrowed_amount_usd REAL,
                    lending_protocol TEXT,
                    borrowing_protocol TEXT,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    liquidation_threshold REAL,
                    current_collateral_ratio REAL,
                    health_score REAL
                )
                """)
                
                # Create defi_loops table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS defi_loops (
                    loop_id TEXT PRIMARY KEY,
                    initial_capital_usd REAL,
                    total_exposure_usd REAL,
                    leverage_ratio REAL,
                    status TEXT,
                    created_at TEXT,
                    closed_at TEXT
                )
                """)
                
                # Create reserved_balances table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS reserved_balances (
                    token_address TEXT PRIMARY KEY,
                    reserved_amount REAL,
                    reserved_amount_usd REAL,
                    reason TEXT,
                    position_ids TEXT,
                    last_updated TEXT
                )
                """)
                
                conn.commit()
                conn.close()
                
                info("\033[36m✅ DeFi position database initialized\033[0m")
                
        except Exception as e:
            error(f"Failed to initialize DeFi position database: {str(e)}")
            raise
    
    def save_position(self, position: DeFiPosition) -> bool:
        """Save or update a DeFi position"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT OR REPLACE INTO defi_positions 
                (position_id, loop_id, iteration, collateral_token, collateral_amount_usd,
                 borrowed_amount_usd, lending_protocol, borrowing_protocol, status,
                 created_at, updated_at, liquidation_threshold, current_collateral_ratio, health_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    position.position_id, position.loop_id, position.iteration,
                    position.collateral_token, position.collateral_amount_usd,
                    position.borrowed_amount_usd, position.lending_protocol,
                    position.borrowing_protocol, position.status,
                    position.created_at, position.updated_at,
                    position.liquidation_threshold, position.current_collateral_ratio,
                    position.health_score
                ))
                
                conn.commit()
                conn.close()
                
                debug(f"💾 Saved DeFi position {position.position_id}")
                return True
                
        except Exception as e:
            error(f"Failed to save DeFi position: {str(e)}")
            return False
    
    def save_loop(self, loop: DeFiLoop) -> bool:
        """Save or update a DeFi loop"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT OR REPLACE INTO defi_loops 
                (loop_id, initial_capital_usd, total_exposure_usd, leverage_ratio,
                 status, created_at, closed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    loop.loop_id, loop.initial_capital_usd, loop.total_exposure_usd,
                    loop.leverage_ratio, loop.status, loop.created_at, loop.closed_at
                ))
                
                conn.commit()
                conn.close()
                
                debug(f"💾 Saved DeFi loop {loop.loop_id}")
                return True
                
        except Exception as e:
            error(f"Failed to save DeFi loop: {str(e)}")
            return False
    
    def update_reserved_balance(self, token_address: str, amount: float, amount_usd: float,
                               reason: str, position_ids: List[str]) -> bool:
        """Update reserved balance for a token"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                position_ids_json = json.dumps(position_ids)
                last_updated = datetime.now().isoformat()
                
                cursor.execute("""
                INSERT OR REPLACE INTO reserved_balances 
                (token_address, reserved_amount, reserved_amount_usd, reason, position_ids, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (token_address, amount, amount_usd, reason, position_ids_json, last_updated))
                
                conn.commit()
                conn.close()
                
                debug(f"💾 Updated reserved balance for {token_address}: {amount:.4f} (${amount_usd:.2f})")
                return True
                
        except Exception as e:
            error(f"Failed to update reserved balance: {str(e)}")
            return False
    
    def get_position(self, position_id: str) -> Optional[DeFiPosition]:
        """Get a specific DeFi position"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM defi_positions WHERE position_id = ?", (position_id,))
                row = cursor.fetchone()
                
                conn.close()
                
                if row:
                    return DeFiPosition(*row)
                return None
                
        except Exception as e:
            error(f"Failed to get DeFi position: {str(e)}")
            return None
    
    def get_active_positions(self) -> List[DeFiPosition]:
        """Get all active DeFi positions"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM defi_positions WHERE status = 'active'")
                rows = cursor.fetchall()
                
                conn.close()
                
                positions = [DeFiPosition(*row) for row in rows]
                return positions
                
        except Exception as e:
            error(f"Failed to get active positions: {str(e)}")
            return []

    def get_all_positions(self) -> List[DeFiPosition]:
        """Get all DeFi positions regardless of status"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM defi_positions")
                rows = cursor.fetchall()

                conn.close()

                positions = [DeFiPosition(*row) for row in rows]
                return positions

        except Exception as e:
            error(f"Failed to get all positions: {str(e)}")
            return []

    def get_loop(self, loop_id: str) -> Optional[DeFiLoop]:
        """Get a specific DeFi loop"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM defi_loops WHERE loop_id = ?", (loop_id,))
                row = cursor.fetchone()
                
                conn.close()
                
                if row:
                    return DeFiLoop(*row)
                return None
                
        except Exception as e:
            error(f"Failed to get DeFi loop: {str(e)}")
            return None
    
    def get_active_loops(self) -> List[DeFiLoop]:
        """Get all active DeFi loops"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM defi_loops WHERE status = 'active'")
                rows = cursor.fetchall()
                
                conn.close()
                
                loops = [DeFiLoop(*row) for row in rows]
                return loops
                
        except Exception as e:
            error(f"Failed to get active loops: {str(e)}")
            return []
    
    def get_reserved_amount(self, token_address: str) -> float:
        """Get reserved amount for a specific token"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT reserved_amount FROM reserved_balances WHERE token_address = ?", 
                             (token_address,))
                row = cursor.fetchone()
                
                conn.close()
                
                if row:
                    return row[0]
                return 0.0
                
        except Exception as e:
            error(f"Failed to get reserved amount: {str(e)}")
            return 0.0
    
    def get_reserved_balance(self, token_address: str) -> Optional[ReservedBalance]:
        """Get full reserved balance info for a token"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM reserved_balances WHERE token_address = ?", 
                             (token_address,))
                row = cursor.fetchone()
                
                conn.close()
                
                if row:
                    position_ids = json.loads(row[4])
                    return ReservedBalance(
                        token_address=row[0],
                        reserved_amount=row[1],
                        reserved_amount_usd=row[2],
                        reason=row[3],
                        position_ids=position_ids,
                        last_updated=row[5]
                    )
                return None
                
        except Exception as e:
            error(f"Failed to get reserved balance: {str(e)}")
            return None
    
    def is_token_lent(self, token_address: str) -> bool:
        """Check if a token is currently lent in any active position"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("""
                SELECT COUNT(*) FROM defi_positions 
                WHERE collateral_token = ? AND status = 'active'
                """, (token_address,))
                
                count = cursor.fetchone()[0]
                conn.close()
                
                return count > 0
                
        except Exception as e:
            error(f"Failed to check if token is lent: {str(e)}")
            return False
    
    def update_position_status(self, position_id: str, status: str, 
                              health_score: Optional[float] = None) -> bool:
        """Update position status and optionally health score"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                updated_at = datetime.now().isoformat()
                
                if health_score is not None:
                    cursor.execute("""
                    UPDATE defi_positions 
                    SET status = ?, health_score = ?, updated_at = ?
                    WHERE position_id = ?
                    """, (status, health_score, updated_at, position_id))
                else:
                    cursor.execute("""
                    UPDATE defi_positions 
                    SET status = ?, updated_at = ?
                    WHERE position_id = ?
                    """, (status, updated_at, position_id))
                
                conn.commit()
                conn.close()
                
                debug(f"📝 Updated position {position_id} status to {status}")
                return True
                
        except Exception as e:
            error(f"Failed to update position status: {str(e)}")
            return False
    
    def update_loop_status(self, loop_id: str, status: str) -> bool:
        """Update loop status"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                closed_at = datetime.now().isoformat() if status in ['completed', 'liquidated'] else None
                
                cursor.execute("""
                UPDATE defi_loops 
                SET status = ?, closed_at = ?
                WHERE loop_id = ?
                """, (status, closed_at, loop_id))
                
                conn.commit()
                conn.close()
                
                debug(f"📝 Updated loop {loop_id} status to {status}")
                return True
                
        except Exception as e:
            error(f"Failed to update loop status: {str(e)}")
            return False
    
    def clear_reserved_balance(self, token_address: str) -> bool:
        """Clear reserved balance for a token"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM reserved_balances WHERE token_address = ?", 
                             (token_address,))
                
                conn.commit()
                conn.close()
                
                debug(f"🗑️ Cleared reserved balance for {token_address}")
                return True
                
        except Exception as e:
            error(f"Failed to clear reserved balance: {str(e)}")
            return False
    
    def get_all_reserved_balances(self) -> Dict[str, ReservedBalance]:
        """Get all reserved balances"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM reserved_balances")
                rows = cursor.fetchall()
                
                conn.close()
                
                balances = {}
                for row in rows:
                    position_ids = json.loads(row[4])
                    balances[row[0]] = ReservedBalance(
                        token_address=row[0],
                        reserved_amount=row[1],
                        reserved_amount_usd=row[2],
                        reason=row[3],
                        position_ids=position_ids,
                        last_updated=row[5]
                    )
                
                return balances
                
        except Exception as e:
            error(f"Failed to get all reserved balances: {str(e)}")
            return {}
    
    def record_defi_transaction_to_paper_trades(self, action: str, token_address: str, 
                                                amount: float, amount_usd: float,
                                                protocol: str, agent: str = "defi") -> bool:
        """
        Record DeFi transaction to paper_trades table for dashboard visibility
        Note: DeFi actions are tracked in defi_positions.db, so we skip paper_trades recording
        to avoid "Invalid trade action" errors (paper_trades only supports BUY/SELL)
        """
        try:
            # DeFi positions are already tracked in defi_positions.db with full details
            # Paper trading module only supports BUY/SELL actions, not BORROW/LEND/WITHDRAW/REPAY
            # So we just log the transaction for visibility without actually recording it
            debug(f"📊 DeFi transaction logged: {action} {amount:.4f} via {protocol} (tracked in defi_positions.db)")
            return True
            
        except Exception as e:
            warning(f"Failed to log DeFi transaction: {str(e)}")
            return False

# Global instance
_manager = None

def get_defi_position_manager() -> DeFiPositionManager:
    """Get the singleton DeFi position manager instance"""
    global _manager
    if _manager is None:
        _manager = DeFiPositionManager()
    return _manager

