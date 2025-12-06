"""
Memory Manager for ZerePy Agents
Provides persistent storage for messages, actions, and insights using SQLite
"""

import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger("memory_manager")


class MemoryManager:
    """Manages persistent memory storage for agents using SQLite"""
    
    def __init__(self, agent_name: str, db_path: Optional[str] = None):
        """
        Initialize the memory manager
        
        Args:
            agent_name: Name of the agent (used for data isolation)
            db_path: Optional path to database file. Defaults to 'data/{agent_name}_memory.db'
        """
        self.agent_name = agent_name
        
        # Set up database path
        if db_path is None:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / f"{agent_name}_memory.db")
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                channel_id TEXT,
                content TEXT NOT NULL,
                message_type TEXT,
                timestamp REAL NOT NULL,
                reactions INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                engagement_score REAL DEFAULT 0.0
            )
        """)
        
        # Actions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                action_name TEXT NOT NULL,
                timestamp REAL NOT NULL,
                success BOOLEAN,
                outcome TEXT,
                metrics TEXT,
                execution_time REAL
            )
        """)
        
        # Insights table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                insight_type TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_agent ON messages(agent_name, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_agent ON actions(agent_name, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_insights_agent ON insights(agent_name, timestamp)")
        
        conn.commit()
        conn.close()
        logger.info(f"Initialized memory database: {self.db_path}")
    
    def save_message(self, platform: str, content: str, channel_id: Optional[str] = None,
                    message_type: Optional[str] = None, reactions: int = 0,
                    replies: int = 0, views: int = 0, engagement_score: float = 0.0):
        """
        Save a message to the database
        
        Args:
            platform: Platform name (discord, twitter, youtube)
            content: Message content
            channel_id: Optional channel ID
            message_type: Type of message (tweet, reply, community_post, etc.)
            reactions: Number of reactions
            replies: Number of replies
            views: Number of views
            engagement_score: Calculated engagement score
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO messages 
            (agent_name, platform, channel_id, content, message_type, timestamp, 
             reactions, replies, views, engagement_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.agent_name, platform, channel_id, content, message_type,
              time.time(), reactions, replies, views, engagement_score))
        
        conn.commit()
        conn.close()
    
    def get_recent_messages(self, platform: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """
        Get recent messages from the database
        
        Args:
            platform: Optional platform filter
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if platform:
            cursor.execute("""
                SELECT * FROM messages 
                WHERE agent_name = ? AND platform = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (self.agent_name, platform, limit))
        else:
            cursor.execute("""
                SELECT * FROM messages 
                WHERE agent_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (self.agent_name, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def save_action(self, action_name: str, success: bool, outcome: Optional[str] = None,
                   metrics: Optional[Dict] = None, execution_time: Optional[float] = None):
        """
        Save an action result to the database
        
        Args:
            action_name: Name of the action
            success: Whether the action succeeded
            outcome: Optional outcome description
            metrics: Optional metrics dictionary (will be JSON encoded)
            execution_time: Optional execution time in seconds
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        metrics_json = json.dumps(metrics) if metrics else None
        
        cursor.execute("""
            INSERT INTO actions 
            (agent_name, action_name, timestamp, success, outcome, metrics, execution_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (self.agent_name, action_name, time.time(), success, outcome,
              metrics_json, execution_time))
        
        conn.commit()
        conn.close()
    
    def get_recent_actions(self, limit: int = 10) -> List[Dict]:
        """
        Get recent actions from the database
        
        Args:
            limit: Maximum number of actions to return
            
        Returns:
            List of action dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM actions 
            WHERE agent_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (self.agent_name, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Parse metrics JSON
        results = []
        for row in rows:
            result = dict(row)
            if result.get("metrics"):
                try:
                    result["metrics"] = json.loads(result["metrics"])
                except json.JSONDecodeError:
                    result["metrics"] = {}
            results.append(result)
        
        return results
    
    def get_action_statistics(self, action_name: Optional[str] = None, 
                             days: int = 7) -> Dict[str, Any]:
        """
        Get statistics about actions
        
        Args:
            action_name: Optional action name filter
            days: Number of days to look back
            
        Returns:
            Dictionary with statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = time.time() - (days * 24 * 3600)
        
        if action_name:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                    AVG(execution_time) as avg_execution_time
                FROM actions
                WHERE agent_name = ? AND action_name = ? AND timestamp > ?
            """, (self.agent_name, action_name, cutoff_time))
        else:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                    AVG(execution_time) as avg_execution_time
                FROM actions
                WHERE agent_name = ? AND timestamp > ?
            """, (self.agent_name, cutoff_time))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return {
                "total": row[0],
                "successful": row[1] or 0,
                "success_rate": (row[1] or 0) / row[0] if row[0] > 0 else 0.0,
                "avg_execution_time": row[2] or 0.0
            }
        else:
            return {
                "total": 0,
                "successful": 0,
                "success_rate": 0.0,
                "avg_execution_time": 0.0
            }
    
    def save_insight(self, insight_type: str, data: Dict[str, Any]):
        """
        Save an insight to the database
        
        Args:
            insight_type: Type of insight (performance_trend, content_pattern, etc.)
            data: Insight data dictionary (will be JSON encoded)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        data_json = json.dumps(data)
        
        cursor.execute("""
            INSERT INTO insights (agent_name, insight_type, data, timestamp)
            VALUES (?, ?, ?, ?)
        """, (self.agent_name, insight_type, data_json, time.time()))
        
        conn.commit()
        conn.close()
    
    def get_recent_insights(self, insight_type: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Get recent insights from the database
        
        Args:
            insight_type: Optional insight type filter
            limit: Maximum number of insights to return
            
        Returns:
            List of insight dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if insight_type:
            cursor.execute("""
                SELECT * FROM insights 
                WHERE agent_name = ? AND insight_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (self.agent_name, insight_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM insights 
                WHERE agent_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (self.agent_name, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Parse data JSON
        results = []
        for row in rows:
            result = dict(row)
            if result.get("data"):
                try:
                    result["data"] = json.loads(result["data"])
                except json.JSONDecodeError:
                    result["data"] = {}
            results.append(result)
        
        return results
    
    def update_message_engagement(self, message_id: int, reactions: Optional[int] = None,
                                 replies: Optional[int] = None, views: Optional[int] = None,
                                 engagement_score: Optional[float] = None):
        """
        Update engagement metrics for a message
        
        Args:
            message_id: Message ID
            reactions: Optional new reactions count
            replies: Optional new replies count
            views: Optional new views count
            engagement_score: Optional new engagement score
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if reactions is not None:
            updates.append("reactions = ?")
            params.append(reactions)
        if replies is not None:
            updates.append("replies = ?")
            params.append(replies)
        if views is not None:
            updates.append("views = ?")
            params.append(views)
        if engagement_score is not None:
            updates.append("engagement_score = ?")
            params.append(engagement_score)
        
        if updates:
            params.append(message_id)
            params.append(self.agent_name)
            cursor.execute(f"""
                UPDATE messages 
                SET {', '.join(updates)}
                WHERE id = ? AND agent_name = ?
            """, params)
            
            conn.commit()
        
        conn.close()

