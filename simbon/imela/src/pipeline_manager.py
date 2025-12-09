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
    
    def __init__(self, mode: str = "talking_head", db_path: Optional[str] = None):
        """
        Initialize the content pipeline
        
        Args:
            mode: Pipeline mode ('talking_head', 'condensation', 'compilation', 'ai_generation')
            db_path: Optional path to database file. Defaults to 'data/pipeline.db'
        """
        # Import config
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import PIPELINE_MODES, get_mode_config
        
        # Set pipeline mode
        self.mode = mode
        try:
            self.mode_config = get_mode_config(mode)
        except ValueError:
            logger.warning(f"Unknown mode '{mode}', defaulting to 'talking_head'")
            self.mode = "talking_head"
            self.mode_config = get_mode_config("talking_head")
        
        logger.info(f"Pipeline initialized in '{self.mode}' mode")
        
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
        
        # Compilation timeout checker (for compilation mode)
        self._running = False
        self._timeout_thread = None
    
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
                mode TEXT DEFAULT 'talking_head',
                compilation_group_id TEXT,
                timeout_trigger_time REAL,
                metadata TEXT,
                error_message TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL
            )
        """)
        
        # Migrate existing databases - add new columns if they don't exist
        self._migrate_database(cursor)
        
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
        
        # Compilation groups table for multi-video compilations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compilation_groups (
                group_id TEXT PRIMARY KEY,
                folder_path TEXT NOT NULL,
                mode TEXT DEFAULT 'compilation',
                video_count INTEGER DEFAULT 0,
                expected_videos INTEGER,
                timeout_at REAL NOT NULL,
                state TEXT NOT NULL,
                metadata TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                triggered_at REAL
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_state ON content_pipeline(state)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_mode ON content_pipeline(mode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_compilation_group ON content_pipeline(compilation_group_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clips_video ON generated_clips(video_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_video ON pipeline_events(video_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compilation_state ON compilation_groups(state)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compilation_timeout ON compilation_groups(timeout_at)")
        
        conn.commit()
        conn.close()
        logger.info(f"Initialized pipeline database: {self.db_path}")
    
    def _migrate_database(self, cursor):
        """Migrate existing database schema to add new columns"""
        try:
            # Check if mode column exists
            cursor.execute("PRAGMA table_info(content_pipeline)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if "mode" not in columns:
                logger.info("Migrating database: adding mode column")
                cursor.execute("ALTER TABLE content_pipeline ADD COLUMN mode TEXT DEFAULT 'talking_head'")
            
            if "compilation_group_id" not in columns:
                logger.info("Migrating database: adding compilation_group_id column")
                cursor.execute("ALTER TABLE content_pipeline ADD COLUMN compilation_group_id TEXT")
            
            if "timeout_trigger_time" not in columns:
                logger.info("Migrating database: adding timeout_trigger_time column")
                cursor.execute("ALTER TABLE content_pipeline ADD COLUMN timeout_trigger_time REAL")
                
        except Exception as e:
            logger.warning(f"Database migration completed with warnings: {e}")
    
    def set_compliance_agent(self, compliance_agent):
        """Set the compliance agent for content checking"""
        self.compliance_agent = compliance_agent
        logger.info("✅ Compliance agent configured for pipeline")
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using ffprobe"""
        try:
            import subprocess
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                import json as json_lib
                data = json_lib.loads(result.stdout)
                return float(data.get('format', {}).get('duration', 0))
        except Exception as e:
            logger.warning(f"Failed to get video duration: {e}")
        return 0
    
    def _validate_mode_requirements(self, video_path: str, mode: str):
        """Validate that input meets mode requirements"""
        from config import PIPELINE_MODES
        
        mode_config = PIPELINE_MODES.get(mode, {})
        
        if mode == "condensation":
            min_duration = mode_config.get("min_source_duration", 300)
            duration = self._get_video_duration(video_path)
            if duration > 0 and duration < min_duration:
                logger.warning(
                    f"Video may be too short for condensation mode: {duration}s "
                    f"(recommended: {min_duration}s+)"
                )
        
        elif mode == "ai_generation":
            if not mode_config.get("enabled", False):
                logger.error("AI generation mode is not enabled. Please configure API keys.")
                raise ValueError("AI generation mode requires API configuration")
    
    def _handle_compilation_trigger(self, video_path: str, group_id: str, 
                                    metadata: Optional[Dict[str, Any]], 
                                    skip_compliance: bool) -> str:
        """Handle compilation mode video addition"""
        import hashlib
        from config import COMPILATION_CONFIG
        
        # Generate group_id from folder if not provided
        if not group_id:
            folder_path = Path(video_path).parent
            group_id = hashlib.md5(str(folder_path).encode()).hexdigest()[:16]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if group exists
        cursor.execute("SELECT * FROM compilation_groups WHERE group_id = ?", (group_id,))
        existing = cursor.fetchone()
        
        timeout_seconds = COMPILATION_CONFIG["timeout_minutes"] * 60
        timeout_at = time.time() + timeout_seconds
        
        if not existing:
            # Create new group
            cursor.execute("""
                INSERT INTO compilation_groups 
                (group_id, folder_path, video_count, timeout_at, state, created_at, updated_at)
                VALUES (?, ?, 1, ?, 'collecting', ?, ?)
            """, (group_id, str(Path(video_path).parent), timeout_at, time.time(), time.time()))
            logger.info(f"Created new compilation group: {group_id}")
        else:
            # Update existing group - reset timeout
            cursor.execute("""
                UPDATE compilation_groups 
                SET video_count = video_count + 1, timeout_at = ?, updated_at = ?
                WHERE group_id = ?
            """, (timeout_at, time.time(), group_id))
            logger.info(f"Added video to compilation group: {group_id}")
        
        # Add video to pipeline with group_id
        video_id = str(uuid.uuid4())
        current_time = time.time()
        original_filename = Path(video_path).name
        
        if metadata is None:
            metadata = {}
        metadata["mode"] = "compilation"
        metadata["compilation_group_id"] = group_id
        
        cursor.execute("""
            INSERT INTO content_pipeline 
            (video_id, original_path, original_filename, state, mode, compilation_group_id,
             timeout_trigger_time, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            video_path,
            original_filename,
            PipelineState.NEW_VIDEO.value,
            "compilation",
            group_id,
            timeout_at,
            json.dumps(metadata),
            current_time,
            current_time
        ))
        
        self._log_event(cursor, video_id, "compilation_video_added", {
            "group_id": group_id,
            "timeout_at": timeout_at
        })
        
        conn.commit()
        conn.close()
        
        logger.info(
            f"Video added to compilation group {group_id}, "
            f"timeout in {COMPILATION_CONFIG['timeout_minutes']} minutes"
        )
        return video_id
    
    def trigger_pipeline(self, video_path: str, mode: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None, 
                        compilation_group_id: Optional[str] = None,
                        skip_compliance: bool = False) -> str:
        """
        Start processing a new video through the pipeline
        
        Args:
            video_path: Path to the video file
            mode: Pipeline mode (overrides instance mode if provided)
            metadata: Optional metadata about the video
            compilation_group_id: For compilation mode grouping
            skip_compliance: Skip compliance check (for testing)
            
        Returns:
            video_id: Unique identifier for this pipeline run
        """
        # Use provided mode or instance mode
        pipeline_mode = mode if mode else self.mode
        
        # Validate mode
        if pipeline_mode == "compilation" and compilation_group_id:
            return self._handle_compilation_trigger(video_path, compilation_group_id, metadata, skip_compliance)
        
        # Normal single-video processing
        video_id = str(uuid.uuid4())
        current_time = time.time()
        
        # Get original filename
        original_filename = Path(video_path).name
        
        # Add mode to metadata
        if metadata is None:
            metadata = {}
        metadata["mode"] = pipeline_mode
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert into pipeline table with mode
        cursor.execute("""
            INSERT INTO content_pipeline 
            (video_id, original_path, original_filename, state, mode, compilation_group_id, 
             metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            video_path,
            original_filename,
            PipelineState.NEW_VIDEO.value,
            pipeline_mode,
            compilation_group_id,
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
                    quick_check=False  # Full analysis for better compliance checking
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

        # Automatically continue pipeline processing
        try:
            self._continue_pipeline_processing(video_id, pipeline_mode)
        except Exception as e:
            logger.error(f"Failed to continue pipeline processing: {e}")
            self.update_state(video_id, PipelineState.ERROR, str(e))

        return video_id

    def _continue_pipeline_processing(self, video_id: str, mode: str):
        """
        Continue automatic pipeline processing after compliance check
        """
        logger.info(f"🔄 Continuing automatic pipeline processing for video {video_id}")

        # Get video path from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT original_path FROM content_pipeline
            WHERE video_id = ?
        """, (video_id,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            raise ValueError(f"Video {video_id} not found in database")

        video_path = result[0]
        logger.info(f"📹 Processing video: {video_path}")

        # Get required connections for agents
        deepseek_conn = None
        try:
            # Import agent to get connection
            from src.agent import ZerePyAgent
            from pathlib import Path

            # Load agent to get connections
            agent_path = Path("agents") / "imela.json"
            if agent_path.exists():
                import json
                agent_data = json.load(open(agent_path))
                agent = ZerePyAgent("imela")
                deepseek_conn = agent.connection_manager.connections.get("deepseek")
        except Exception as e:
            logger.warning(f"Could not get deepseek connection: {e}")

        # Get required connections for agents
        youtube_conn = None
        try:
            # Load agent to get connections
            from src.agent import ZerePyAgent
            agent = ZerePyAgent("imela")
            youtube_conn = agent.connection_manager.connections.get("youtube")
        except Exception as e:
            logger.warning(f"Could not get youtube connection: {e}")

        # Start clipping process
        self._process_video_clips(video_id, video_path, mode, deepseek_conn, youtube_conn)

    def _process_video_clips(self, video_id: str, video_path: str, mode: str, deepseek_conn=None, youtube_conn=None):
        """
        Process video clips using the ClipsAgent
        """
        logger.info(f"✂️ Starting clip extraction for video {video_id}")

        # Update state to clipping
        self.update_state(video_id, PipelineState.CLIPPING)

        try:
            # Import and initialize clips agent
            from src.agents.clips_agent import ClipsAgent
            from config import CLIPS_CONFIG

            clips_agent = ClipsAgent(deepseek_connection=deepseek_conn, pipeline_manager=self)
            clips = clips_agent.process_video(video_id, video_path)

            if not clips:
                logger.warning(f"⚠️ No clips generated for video {video_id}")
                self.update_state(video_id, PipelineState.ERROR, "No clips generated")
                return

            logger.info(f"✅ Generated {len(clips)} clips for video {video_id}")

            # Store clips in database
            for clip in clips:
                self.add_generated_clip(
                    video_id=video_id,
                    clip_path=clip['clip_path'],
                    start_time=clip['start_time'],
                    end_time=clip['end_time'],
                    transcript=clip.get('transcript'),
                    score=clip.get('score')
                )

            # Continue to editing
            self._process_video_editing(video_id, clips, deepseek_conn, youtube_conn)

        except Exception as e:
            logger.error(f"❌ Clipping failed for video {video_id}: {e}")
            self.update_state(video_id, PipelineState.ERROR, f"Clipping failed: {e}")

    def _process_video_editing(self, video_id: str, clips: list, deepseek_conn=None, youtube_conn=None):
        """
        Process video editing using the EditingAgent
        """
        logger.info(f"🎬 Starting video editing for video {video_id}")

        # Update state to editing
        self.update_state(video_id, PipelineState.EDITING)

        try:
            # Import and initialize editing agent
            from src.agents.editing_agent import EditingAgent

            editing_agent = EditingAgent(pipeline_manager=self)
            edited_clips = editing_agent.process_clips(video_id)

            if not edited_clips:
                logger.warning(f"⚠️ No edited clips generated for video {video_id}")
                self.update_state(video_id, PipelineState.ERROR, "No edited clips generated")
                return

            logger.info(f"✅ Generated {len(edited_clips)} edited clips for video {video_id}")

            # Continue to review
            self._process_video_review(video_id, edited_clips, deepseek_conn, youtube_conn)

        except Exception as e:
            logger.error(f"❌ Editing failed for video {video_id}: {e}")
            self.update_state(video_id, PipelineState.ERROR, f"Editing failed: {e}")

    def _process_video_review(self, video_id: str, edited_clips: list, deepseek_conn=None, youtube_conn=None):
        """
        Process video review using the ReviewAgent
        """
        logger.info(f"📧 Starting review process for video {video_id}")

        # Update state to review pending
        self.update_state(video_id, PipelineState.REVIEW_PENDING)

        try:
            # Import and initialize review agent
            from src.agents.review_agent import ReviewAgent

            review_agent = ReviewAgent(pipeline_manager=self)
            email_sent = review_agent.send_for_review(video_id)

            if email_sent:
                logger.info(f"✅ Review email sent for video {video_id}")
                # For automated testing, auto-approve clips
                # In production, this would wait for manual approval
                logger.info(f"🔄 Auto-approving clips for automated testing")
                self.update_state(video_id, PipelineState.APPROVED)
                # Continue to publishing
                self._process_video_publishing(video_id, edited_clips, deepseek_conn, youtube_conn)
            else:
                logger.warning(f"⚠️ Failed to send review email for video {video_id}")
                self.update_state(video_id, PipelineState.ERROR, "Review email failed")

        except Exception as e:
            logger.error(f"❌ Review failed for video {video_id}: {e}")
            self.update_state(video_id, PipelineState.ERROR, f"Review failed: {e}")

    def _process_video_publishing(self, video_id: str, edited_clips: list, deepseek_conn=None, youtube_conn=None):
        """
        Process video publishing using the PublishingAgent
        """
        logger.info(f"📺 Starting publishing process for video {video_id}")

        try:
            # Import and initialize publishing agent
            from src.agents.publishing_agent import PublishingAgent

            publishing_agent = PublishingAgent(
                pipeline_manager=self,
                youtube_connection=youtube_conn,
                deepseek_connection=deepseek_conn
            )
            published_clips = publishing_agent.publish_approved_clips(video_id)

            if published_clips and len(published_clips) > 0:
                logger.info(f"✅ Video {video_id} published successfully! ({len(published_clips)} clips)")
                self.update_state(video_id, PipelineState.PUBLISHED)
            else:
                logger.warning(f"⚠️ Publishing failed for video {video_id} - no clips published")
                self.update_state(video_id, PipelineState.ERROR, "Publishing failed")

        except Exception as e:
            logger.error(f"❌ Publishing failed for video {video_id}: {e}")
            self.update_state(video_id, PipelineState.ERROR, f"Publishing failed: {e}")

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
    
    def check_compilation_timeouts(self):
        """Check for compilation groups ready to process (timeout reached)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        current_time = time.time()
        cursor.execute("""
            SELECT group_id, folder_path, video_count FROM compilation_groups 
            WHERE state = 'collecting' AND timeout_at <= ?
        """, (current_time,))
        
        ready_groups = cursor.fetchall()
        
        for row in ready_groups:
            group_id = row['group_id']
            video_count = row['video_count']
            logger.info(
                f"⏰ Compilation timeout reached for group {group_id} "
                f"({video_count} videos), triggering compilation"
            )
            self._trigger_compilation_for_group(group_id, cursor)
        
        conn.commit()
        conn.close()
    
    def _trigger_compilation_for_group(self, group_id: str, cursor):
        """Trigger compilation processing for a group"""
        # Update group state
        cursor.execute("""
            UPDATE compilation_groups 
            SET state = 'processing', triggered_at = ?, updated_at = ?
            WHERE group_id = ?
        """, (time.time(), time.time(), group_id))
        
        # Get all videos in this group
        cursor.execute("""
            SELECT video_id, original_path FROM content_pipeline 
            WHERE compilation_group_id = ? AND state = 'new_video'
        """, (group_id,))
        
        videos = cursor.fetchall()
        
        if videos:
            logger.info(f"🎬 Starting compilation of {len(videos)} videos in group {group_id}")
            # Log event for first video (group representative)
            first_video_id = videos[0]['video_id']
            self._log_event(cursor, first_video_id, "compilation_triggered", {
                "group_id": group_id,
                "video_count": len(videos)
            })
            
            # Update all videos in group to processing state
            for video in videos:
                cursor.execute("""
                    UPDATE content_pipeline 
                    SET state = ?, updated_at = ?
                    WHERE video_id = ?
                """, (PipelineState.PROCESSING.value, time.time(), video['video_id']))
        else:
            logger.warning(f"No videos found for compilation group {group_id}")
    
    def start_timeout_checker(self):
        """Start background thread to check compilation timeouts"""
        if self._running:
            logger.warning("Timeout checker already running")
            return
        
        from config import COMPILATION_CONFIG
        import threading
        
        def timeout_loop():
            check_interval = COMPILATION_CONFIG.get("check_interval_seconds", 30)
            while self._running:
                try:
                    self.check_compilation_timeouts()
                except Exception as e:
                    logger.error(f"Error in timeout checker: {e}")
                time.sleep(check_interval)
        
        self._running = True
        self._timeout_thread = threading.Thread(target=timeout_loop, daemon=True)
        self._timeout_thread.start()
        logger.info("✅ Compilation timeout checker started")
    
    def stop_timeout_checker(self):
        """Stop the timeout checker thread"""
        if self._running:
            self._running = False
            if self._timeout_thread:
                self._timeout_thread.join(timeout=5)
            logger.info("🛑 Compilation timeout checker stopped")
    
    def get_compilation_groups(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get compilation groups, optionally filtered by state"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if state:
            cursor.execute("SELECT * FROM compilation_groups WHERE state = ?", (state,))
        else:
            cursor.execute("SELECT * FROM compilation_groups")
        
        groups = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return groups
    
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

