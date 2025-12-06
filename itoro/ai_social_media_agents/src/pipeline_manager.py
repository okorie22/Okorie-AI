"""
Content Pipeline Manager for ZerePy
Orchestrates the automated video content creation workflow
"""

import sqlite3
import json
import time
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger("pipeline_manager")


class PipelineState(Enum):
    """Pipeline workflow states"""
    NEW_VIDEO = "new_video"
    COMPLIANCE_CHECK = "compliance_check"
    PROCESSING = "processing"
    CLIPPING = "clipping"
    EDITING = "editing"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ERROR = "error"


class ContentPipeline:
    """Manages the content creation pipeline workflow"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the content pipeline
        
        Args:
            db_path: Optional path to database file. Defaults to 'data/pipeline.db'
        """
        # Set up database path
        if db_path is None:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "pipeline.db")
        
        self.db_path = db_path
        self._init_database()
        
        # Create processing directories
        self._init_directories()
        
        # Compliance agent (optional)
        self.compliance_agent = None
    
    def _init_directories(self):
        """Initialize required directories for pipeline"""
        base_dir = Path("data/content_pipeline")
        
        self.dirs = {
            "raw_videos": base_dir / "raw_videos",
            "processed_clips": base_dir / "processed_clips",
            "edited_clips": base_dir / "edited_clips",
            "published": base_dir / "published",
            "rejected": base_dir / "rejected"
        }
        
        for directory in self.dirs.values():
            directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized pipeline directories at {base_dir}")
    
    def _init_database(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main pipeline tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_pipeline (
                video_id TEXT PRIMARY KEY,
                original_path TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                state TEXT NOT NULL,
                metadata TEXT,
                error_message TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL
            )
        """)
        
        # Generated clips table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_clips (
                clip_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                clip_path TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                duration REAL NOT NULL,
                transcript TEXT,
                score REAL,
                approved BOOLEAN DEFAULT 0,
                published BOOLEAN DEFAULT 0,
                youtube_url TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (video_id) REFERENCES content_pipeline(video_id)
            )
        """)
        
        # Pipeline events table (audit log)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp REAL NOT NULL,
                FOREIGN KEY (video_id) REFERENCES content_pipeline(video_id)
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_state ON content_pipeline(state)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clips_video ON generated_clips(video_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_video ON pipeline_events(video_id)")
        
        conn.commit()
        conn.close()
        logger.info(f"Initialized pipeline database: {self.db_path}")
    
    def set_compliance_agent(self, compliance_agent):
        """Set the compliance agent for content checking"""
        self.compliance_agent = compliance_agent
        logger.info("✅ Compliance agent configured for pipeline")
    
    def trigger_pipeline(self, video_path: str, metadata: Optional[Dict[str, Any]] = None, 
                        skip_compliance: bool = False) -> str:
        """
        Start processing a new video through the pipeline
        
        Args:
            video_path: Path to the video file
            metadata: Optional metadata about the video
            skip_compliance: Skip compliance check (for testing)
            
        Returns:
            video_id: Unique identifier for this pipeline run
        """
        video_id = str(uuid.uuid4())
        current_time = time.time()
        
        # Get original filename
        original_filename = Path(video_path).name
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert into pipeline table
        cursor.execute("""
            INSERT INTO content_pipeline 
            (video_id, original_path, original_filename, state, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            video_path,
            original_filename,
            PipelineState.NEW_VIDEO.value,
            json.dumps(metadata) if metadata else None,
            current_time,
            current_time
        ))
        
        # Log event
        self._log_event(cursor, video_id, "pipeline_triggered", {"video_path": video_path})
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Pipeline triggered for video: {original_filename} (ID: {video_id})")
        
        # Run compliance check if agent is configured
        if self.compliance_agent and not skip_compliance:
            logger.info(f"🔍 Running compliance check...")
            self.update_state(video_id, PipelineState.COMPLIANCE_CHECK)
            
            try:
                compliance_result = self.compliance_agent.check_pipeline_compliance(
                    video_path, 
                    quick_check=True  # Fast check to not slow down pipeline
                )
                
                # Store compliance data in metadata
                if not metadata:
                    metadata = {}
                metadata["compliance"] = compliance_result
                
                # Update metadata in database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE content_pipeline 
                    SET metadata = ?
                    WHERE video_id = ?
                """, (json.dumps(metadata), video_id))
                conn.commit()
                conn.close()
                
                # Check if video passes compliance
                if not compliance_result.get("compliant", False):
                    score = compliance_result.get("score", 0.0)
                    issues = compliance_result.get("issues", [])
                    
                    logger.warning(f"❌ Video failed compliance check (score: {score:.2f})")
                    logger.warning(f"Issues: {', '.join(issues)}")
                    
                    # Reject if score is too low (< 0.5)
                    if score < 0.5:
                        self.update_state(
                            video_id, 
                            PipelineState.REJECTED,
                            error_message=f"Compliance failed: {', '.join(issues)}"
                        )
                        logger.error(f"🚫 Video rejected due to compliance issues")
                        return video_id
                    else:
                        logger.info(f"⚠️  Compliance issues detected but score adequate, proceeding with caution")
                else:
                    logger.info(f"✅ Compliance check passed (score: {compliance_result.get('score', 1.0):.2f})")
                
            except Exception as e:
                logger.error(f"Compliance check error: {e}")
                logger.info("⚠️  Proceeding without compliance check")
        
        # Update to processing state
        self.update_state(video_id, PipelineState.PROCESSING)
        
        return video_id
    
    def update_state(self, video_id: str, new_state: PipelineState, 
                    error_message: Optional[str] = None):
        """
        Update the pipeline state for a video
        
        Args:
            video_id: Video identifier
            new_state: New pipeline state
            error_message: Optional error message if state is ERROR
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.time()
        
        # Update state
        if new_state == PipelineState.ERROR:
            cursor.execute("""
                UPDATE content_pipeline 
                SET state = ?, error_message = ?, updated_at = ?
                WHERE video_id = ?
            """, (new_state.value, error_message, current_time, video_id))
        elif new_state == PipelineState.PUBLISHED:
            cursor.execute("""
                UPDATE content_pipeline 
                SET state = ?, updated_at = ?, completed_at = ?
                WHERE video_id = ?
            """, (new_state.value, current_time, current_time, video_id))
        else:
            cursor.execute("""
                UPDATE content_pipeline 
                SET state = ?, updated_at = ?
                WHERE video_id = ?
            """, (new_state.value, current_time, video_id))
        
        # Log event
        event_data = {"new_state": new_state.value}
        if error_message:
            event_data["error"] = error_message
        self._log_event(cursor, video_id, "state_changed", event_data)
        
        conn.commit()
        conn.close()
        
        logger.info(f"📊 Pipeline state updated: {video_id} → {new_state.value}")
    
    def get_pipeline_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a pipeline
        
        Args:
            video_id: Video identifier
            
        Returns:
            Dictionary with pipeline status or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM content_pipeline WHERE video_id = ?
        """, (video_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            result = dict(row)
            if result.get("metadata"):
                result["metadata"] = json.loads(result["metadata"])
            return result
        return None
    
    def get_active_pipelines(self) -> List[Dict[str, Any]]:
        """
        Get all active (non-completed) pipelines
        
        Returns:
            List of active pipeline dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        active_states = [
            PipelineState.NEW_VIDEO.value,
            PipelineState.PROCESSING.value,
            PipelineState.CLIPPING.value,
            PipelineState.EDITING.value,
            PipelineState.REVIEW_PENDING.value,
            PipelineState.APPROVED.value
        ]
        
        placeholders = ','.join('?' * len(active_states))
        cursor.execute(f"""
            SELECT * FROM content_pipeline 
            WHERE state IN ({placeholders})
            ORDER BY created_at DESC
        """, active_states)
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get("metadata"):
                result["metadata"] = json.loads(result["metadata"])
            results.append(result)
        
        return results
    
    def add_generated_clip(self, video_id: str, clip_path: str, start_time: float,
                          end_time: float, transcript: Optional[str] = None,
                          score: Optional[float] = None) -> str:
        """
        Add a generated clip to the database
        
        Args:
            video_id: Parent video identifier
            clip_path: Path to the generated clip file
            start_time: Start time in seconds
            end_time: End time in seconds
            transcript: Optional transcript of the clip
            score: Optional quality score (0-1)
            
        Returns:
            clip_id: Unique identifier for the clip
        """
        clip_id = str(uuid.uuid4())
        duration = end_time - start_time
        current_time = time.time()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO generated_clips 
            (clip_id, video_id, clip_path, start_time, end_time, duration, 
             transcript, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clip_id, video_id, clip_path, start_time, end_time, duration,
            transcript, score, current_time
        ))
        
        # Log event
        self._log_event(cursor, video_id, "clip_generated", {
            "clip_id": clip_id,
            "duration": duration,
            "score": score
        })
        
        conn.commit()
        conn.close()
        
        logger.info(f"✂️ Clip generated: {clip_id} (duration: {duration:.1f}s, score: {score})")
        return clip_id
    
    def get_clips_for_video(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Get all generated clips for a video
        
        Args:
            video_id: Video identifier
            
        Returns:
            List of clip dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM generated_clips 
            WHERE video_id = ?
            ORDER BY score DESC, created_at DESC
        """, (video_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def handle_review_response(self, video_id: str, clip_id: str, approved: bool):
        """
        Process approval/rejection of a clip
        
        Args:
            video_id: Video identifier
            clip_id: Clip identifier
            approved: True if approved, False if rejected
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update clip approval status
        cursor.execute("""
            UPDATE generated_clips 
            SET approved = ?
            WHERE clip_id = ?
        """, (1 if approved else 0, clip_id))
        
        # Update pipeline state
        new_state = PipelineState.APPROVED if approved else PipelineState.REJECTED
        current_time = time.time()
        
        cursor.execute("""
            UPDATE content_pipeline 
            SET state = ?, updated_at = ?
            WHERE video_id = ?
        """, (new_state.value, current_time, video_id))
        
        # Log event
        self._log_event(cursor, video_id, "review_completed", {
            "clip_id": clip_id,
            "approved": approved
        })
        
        conn.commit()
        conn.close()
        
        status = "✅ APPROVED" if approved else "❌ REJECTED"
        logger.info(f"{status} Clip review completed: {clip_id}")
    
    def mark_clip_published(self, clip_id: str, youtube_url: Optional[str] = None):
        """
        Mark a clip as published
        
        Args:
            clip_id: Clip identifier
            youtube_url: Optional YouTube URL where clip was published
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE generated_clips 
            SET published = 1, youtube_url = ?
            WHERE clip_id = ?
        """, (youtube_url, clip_id))
        
        # Get video_id for logging
        cursor.execute("SELECT video_id FROM generated_clips WHERE clip_id = ?", (clip_id,))
        result = cursor.fetchone()
        
        if result:
            video_id = result[0]
            self._log_event(cursor, video_id, "clip_published", {
                "clip_id": clip_id,
                "youtube_url": youtube_url
            })
        
        conn.commit()
        conn.close()
        
        logger.info(f"🚀 Clip published: {clip_id}")
    
    def get_pipeline_events(self, video_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get event history for a pipeline
        
        Args:
            video_id: Video identifier
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM pipeline_events 
            WHERE video_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (video_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get("event_data"):
                try:
                    result["event_data"] = json.loads(result["event_data"])
                except json.JSONDecodeError:
                    pass
            results.append(result)
        
        return results
    
    def _log_event(self, cursor, video_id: str, event_type: str, 
                   event_data: Optional[Dict[str, Any]] = None):
        """
        Log a pipeline event (internal method)
        
        Args:
            cursor: Database cursor
            video_id: Video identifier
            event_type: Type of event
            event_data: Optional event data dictionary
        """
        cursor.execute("""
            INSERT INTO pipeline_events (video_id, event_type, event_data, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            video_id,
            event_type,
            json.dumps(event_data) if event_data else None,
            time.time()
        ))
    
    def cleanup_old_pipelines(self, days: int = 30):
        """
        Clean up old completed/rejected pipelines
        
        Args:
            days: Age threshold in days
        """
        cutoff_time = time.time() - (days * 24 * 3600)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get old pipelines to clean up
        cursor.execute("""
            SELECT video_id, state FROM content_pipeline 
            WHERE (state = ? OR state = ?) AND updated_at < ?
        """, (PipelineState.PUBLISHED.value, PipelineState.REJECTED.value, cutoff_time))
        
        old_pipelines = cursor.fetchall()
        
        for video_id, state in old_pipelines:
            # Delete events
            cursor.execute("DELETE FROM pipeline_events WHERE video_id = ?", (video_id,))
            
            # Delete clips
            cursor.execute("DELETE FROM generated_clips WHERE video_id = ?", (video_id,))
            
            # Delete pipeline entry
            cursor.execute("DELETE FROM content_pipeline WHERE video_id = ?", (video_id,))
        
        conn.commit()
        conn.close()
        
        if old_pipelines:
            logger.info(f"🗑️ Cleaned up {len(old_pipelines)} old pipelines")

