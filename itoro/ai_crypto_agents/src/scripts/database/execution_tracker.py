#!/usr/bin/env python3
"""
Execution Tracker Database
Tracks all agent executions including copybot, risk, harvesting, and staking agents
"""

import sqlite3
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

# Cloud database import
try:
    from src.scripts.database.cloud_database import get_cloud_database_manager
    CLOUD_DB_AVAILABLE = True
except ImportError:
    CLOUD_DB_AVAILABLE = False

logger = logging.getLogger(__name__)

class ExecutionTracker:
    def __init__(self, db_path: str = "src/data/execution_tracker.db"):
        """Initialize the execution tracker database"""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create executions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        agent_type TEXT NOT NULL,
                        wallet_address TEXT NOT NULL,
                        token_mint TEXT,
                        action TEXT NOT NULL,
                        amount REAL,
                        price REAL,
                        usd_value REAL,
                        transaction_signature TEXT,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        execution_time_ms INTEGER,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create analysis table for AI decisions
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_analysis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        agent_type TEXT NOT NULL,
                        wallet_address TEXT NOT NULL,
                        token_mint TEXT,
                        action TEXT NOT NULL,
                        analysis_type TEXT NOT NULL,
                        confidence_score REAL,
                        risk_level TEXT,
                        market_conditions TEXT,
                        recommendation TEXT,
                        execution_price REAL,
                        amount REAL,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_agent_type ON executions(agent_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_timestamp ON executions(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_agent_type ON ai_analysis(agent_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON ai_analysis(timestamp)")
                
                conn.commit()
                logger.info("✅ Execution tracker database initialized successfully")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize execution tracker database: {e}")
    
    def log_execution(self, agent_type: str, wallet_address: str, action: str, 
                     token_mint: Optional[str] = None, amount: Optional[float] = None,
                     price: Optional[float] = None, usd_value: Optional[float] = None,
                     transaction_signature: Optional[str] = None, status: str = "PENDING",
                     error_message: Optional[str] = None, execution_time_ms: Optional[int] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Log an agent execution to local database first, then sync to cloud database
        
        Args:
            agent_type: Type of agent (copybot, risk, harvesting, staking)
            wallet_address: Wallet address that executed the action
            action: Action performed (BUY, SELL, STAKE, UNSTAKE, etc.)
            token_mint: Token mint address (if applicable)
            amount: Amount of tokens involved
            price: Price per token
            usd_value: Total USD value of the transaction
            transaction_signature: Blockchain transaction signature
            status: Execution status (PENDING, SUCCESS, FAILED, CANCELLED)
            error_message: Error message if execution failed
            execution_time_ms: Time taken to execute in milliseconds
            metadata: Additional metadata as JSON string
            
        Returns:
            bool: True if logged successfully, False otherwise
        """
        try:
            # PRIMARY: Save to local database first
            success = self._log_execution_to_local_db(agent_type, wallet_address, action, token_mint, amount, price, usd_value, transaction_signature, status, error_message, execution_time_ms, metadata)
            if not success:
                logger.error(f"❌ Failed to log execution to local database: {agent_type} {action} for {wallet_address}")
                return False
            
            # SECONDARY: Try to sync to cloud database
            if CLOUD_DB_AVAILABLE:
                try:
                    db_manager = get_cloud_database_manager()
                    if db_manager is None:
                        logger.warning("⚠️ Cloud database not configured (local data saved)")
                        return True
                    
                    # Generate unique execution ID
                    execution_id = f"{agent_type}_{int(time.time())}_{hash(wallet_address)}"
                    
                    # Save to cloud database
                    query = '''
                        INSERT INTO execution_tracking (
                            execution_id, agent_name, action_type, token_mint, amount,
                            value_usd, status, error_message, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    '''
                    
                    params = (
                        execution_id,  # execution_id
                        agent_type,  # agent_name
                        action,  # action_type
                        token_mint,  # token_mint
                        amount,  # amount
                        usd_value,  # value_usd
                        status,  # status
                        error_message,  # error_message
                        json.dumps({
                            'wallet_address': wallet_address,
                            'price': price,
                            'transaction_signature': transaction_signature,
                            'execution_time_ms': execution_time_ms,
                            'timestamp': time.time(),
                            'original_metadata': metadata
                        })  # metadata
                    )
                    
                    db_manager.execute_query(query, params, fetch=False)
                    logger.info(f"✅ Execution synced to cloud database: {agent_type} {action} for {wallet_address}")
                    
                except Exception as cloud_error:
                    logger.warning(f"⚠️ Cloud database sync failed (local data saved): {cloud_error}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log execution: {e}")
            return False
    
    def _log_execution_to_local_db(self, agent_type: str, wallet_address: str, action: str, 
                                  token_mint: Optional[str] = None, amount: Optional[float] = None,
                                  price: Optional[float] = None, usd_value: Optional[float] = None,
                                  transaction_signature: Optional[str] = None, status: str = "PENDING",
                                  error_message: Optional[str] = None, execution_time_ms: Optional[int] = None,
                                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Fallback method to log execution to local database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO executions (
                        timestamp, agent_type, wallet_address, token_mint, action,
                        amount, price, usd_value, transaction_signature, status,
                        error_message, execution_time_ms, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    time.time(),
                    agent_type,
                    wallet_address,
                    token_mint,
                    action,
                    amount,
                    price,
                    usd_value,
                    transaction_signature,
                    status,
                    error_message,
                    execution_time_ms,
                    json.dumps(metadata) if metadata else None
                ))
                
                conn.commit()
                logger.info(f"📁 Execution logged to local database: {agent_type} {action} for {wallet_address}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to log execution to local database: {e}")
            return False
    
    def log_ai_analysis(self, agent_type: str, wallet_address: str, action: str,
                       analysis_type: str, confidence_score: Optional[float] = None,
                       risk_level: Optional[str] = None, market_conditions: Optional[str] = None,
                       recommendation: Optional[str] = None, execution_price: Optional[float] = None,
                       amount: Optional[float] = None, notes: Optional[str] = None,
                       token_mint: Optional[str] = None) -> bool:
        """
        Log AI analysis decision
        
        Args:
            agent_type: Type of agent (risk, harvesting)
            wallet_address: Wallet address being analyzed
            action: Recommended action (BUY, SELL, HOLD, STAKE, etc.)
            analysis_type: Type of analysis (risk_assessment, market_analysis, etc.)
            confidence_score: AI confidence in the decision (0-100)
            risk_level: Risk assessment (LOW, MEDIUM, HIGH, CRITICAL)
            market_conditions: Market conditions at time of analysis
            recommendation: Detailed recommendation
            execution_price: Price at time of analysis
            amount: Amount recommended
            notes: Additional notes
            token_mint: Token mint address (if applicable)
            
        Returns:
            bool: True if logged successfully, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO ai_analysis (
                        timestamp, agent_type, wallet_address, token_mint, action,
                        analysis_type, confidence_score, risk_level, market_conditions,
                        recommendation, execution_price, amount, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    time.time(),
                    agent_type,
                    wallet_address,
                    token_mint,
                    action,
                    analysis_type,
                    confidence_score,
                    risk_level,
                    market_conditions,
                    recommendation,
                    execution_price,
                    amount,
                    notes
                ))
                
                conn.commit()
                logger.info(f"✅ Logged AI analysis: {agent_type} {analysis_type} for {wallet_address}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to log AI analysis: {e}")
            return False
    
    def get_executions(self, agent_type: Optional[str] = None, 
                      wallet_address: Optional[str] = None,
                      status: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history with optional filters"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM executions WHERE 1=1"
                params = []
                
                if agent_type:
                    query += " AND agent_type = ?"
                    params.append(agent_type)
                
                if wallet_address:
                    query += " AND wallet_address = ?"
                    params.append(wallet_address)
                
                if status:
                    query += " AND status = ?"
                    params.append(status)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                columns = [description[0] for description in cursor.description]
                
                results = []
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    if result.get('metadata'):
                        try:
                            result['metadata'] = json.loads(result['metadata'])
                        except:
                            pass
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"❌ Failed to get executions: {e}")
            return []
    
    def get_ai_analysis(self, agent_type: Optional[str] = None,
                       wallet_address: Optional[str] = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """Get AI analysis history with optional filters"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM ai_analysis WHERE 1=1"
                params = []
                
                if agent_type:
                    query += " AND agent_type = ?"
                    params.append(agent_type)
                
                if wallet_address:
                    query += " AND wallet_address = ?"
                    params.append(wallet_address)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                columns = [description[0] for description in cursor.description]
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                
                return results
                
        except Exception as e:
            logger.error(f"❌ Failed to get AI analysis: {e}")
            return []
    
    def update_execution_status(self, execution_id: int, status: str, 
                              error_message: Optional[str] = None,
                              transaction_signature: Optional[str] = None) -> bool:
        """Update execution status after completion"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if error_message and transaction_signature:
                    cursor.execute("""
                        UPDATE executions 
                        SET status = ?, error_message = ?, transaction_signature = ?
                        WHERE id = ?
                    """, (status, error_message, transaction_signature, execution_id))
                elif error_message:
                    cursor.execute("""
                        UPDATE executions 
                        SET status = ?, error_message = ?
                        WHERE id = ?
                    """, (status, error_message, execution_id))
                elif transaction_signature:
                    cursor.execute("""
                        UPDATE executions 
                        SET status = ?, transaction_signature = ?
                        WHERE id = ?
                    """, (status, transaction_signature, execution_id))
                else:
                    cursor.execute("""
                        UPDATE executions 
                        SET status = ?
                        WHERE id = ?
                    """, (status, execution_id))
                
                conn.commit()
                logger.info(f"✅ Updated execution {execution_id} status to {status}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to update execution status: {e}")
            return False
    
    def get_execution_stats(self, agent_type: Optional[str] = None,
                          wallet_address: Optional[str] = None,
                          time_period_hours: int = 24) -> Dict[str, Any]:
        """Get execution statistics for the specified time period"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cutoff_time = time.time() - (time_period_hours * 3600)
                
                query = "SELECT * FROM executions WHERE timestamp > ?"
                params = [cutoff_time]
                
                if agent_type:
                    query += " AND agent_type = ?"
                    params.append(agent_type)
                
                if wallet_address:
                    query += " AND wallet_address = ?"
                    params.append(wallet_address)
                
                cursor.execute(query, params)
                executions = cursor.fetchall()
                
                if not executions:
                    return {
                        "total_executions": 0,
                        "successful": 0,
                        "failed": 0,
                        "pending": 0,
                        "total_usd_value": 0.0,
                        "success_rate": 0.0
                    }
                
                total = len(executions)
                successful = sum(1 for e in executions if e[10] == "SUCCESS")  # status column
                failed = sum(1 for e in executions if e[10] == "FAILED")
                pending = sum(1 for e in executions if e[10] == "PENDING")
                
                # Calculate total USD value (column 8)
                total_usd_value = sum(e[8] or 0 for e in executions if e[8] is not None)
                
                success_rate = (successful / total) * 100 if total > 0 else 0
                
                return {
                    "total_executions": total,
                    "successful": successful,
                    "failed": failed,
                    "pending": pending,
                    "total_usd_value": total_usd_value,
                    "success_rate": success_rate
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get execution stats: {e}")
            return {}

# Global instance
_execution_tracker = None

def get_execution_tracker() -> ExecutionTracker:
    """Get the global execution tracker instance"""
    global _execution_tracker
    if _execution_tracker is None:
        _execution_tracker = ExecutionTracker()
    return _execution_tracker

def log_execution(*args, **kwargs) -> bool:
    """Global function to log executions"""
    return get_execution_tracker().log_execution(*args, **kwargs)

def log_ai_analysis(*args, **kwargs) -> bool:
    """Global function to log AI analysis"""
    return get_execution_tracker().log_ai_analysis(*args, **kwargs)
