"""
IUL Pipeline Manager for IKON
Orchestrates the idea → published workflow with Redis queue integration
"""

import logging
import time
import sqlite3
from pathlib import Path
from enum import Enum
from typing import Dict, Any, Optional
from src.queue.redis_client import RedisQueueClient, JobSchema
from src.content.ideas_manager import IdeasManager, IdeaStatus
from src.content.script_composer import ScriptComposer
from src.agents.compliance_agent import ComplianceAgent
from src.media.tts_elevenlabs import TTSService
from src.media.remotion_renderer import RemotionRenderer
from src.agents.publishing_agent import PublishingAgent

logger = logging.getLogger("iul_pipeline")


class PipelineState(Enum):
    """IUL pipeline states"""
    QUEUED = "queued"
    SCRIPTING = "scripting"
    COMPLIANCE = "compliance"
    TTS = "tts"
    RENDERING = "rendering"
    POST_CHECK = "post_check"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    ERROR = "error"


class IULPipelineManager:
    """Manages the IUL content generation pipeline"""
    
    def __init__(self, redis_client: RedisQueueClient, ideas_manager: IdeasManager,
                 script_composer: ScriptComposer, compliance_agent: ComplianceAgent,
                 tts_service: TTSService, remotion_renderer: RemotionRenderer,
                 publishing_agent: PublishingAgent, db_path: str = None):
        """
        Initialize IUL pipeline manager
        
        Args:
            redis_client: Redis queue client
            ideas_manager: Ideas storage manager
            script_composer: Script composition service
            compliance_agent: Compliance checking service
            tts_service: Text-to-speech service
            remotion_renderer: Video rendering service
            publishing_agent: Publishing service
            db_path: Optional database path for state tracking
        """
        self.redis = redis_client
        self.ideas = ideas_manager
        self.script_composer = script_composer
        self.compliance = compliance_agent
        self.tts = tts_service
        self.renderer = remotion_renderer
        self.publisher = publishing_agent
        
        # Initialize database for state tracking
        if db_path is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "iul_pipeline.db")
        
        self.db_path = db_path
        self._init_database()
        
        logger.info("IUL Pipeline Manager initialized")
    
    def _init_database(self):
        """Initialize SQLite database for pipeline state tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Pipeline state tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                idea_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                state TEXT NOT NULL,
                started_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL,
                error_message TEXT,
                metadata TEXT
            )
        """)
        
        # State transitions log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_transitions (
                transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT NOT NULL,
                timestamp REAL NOT NULL,
                duration REAL,
                metadata TEXT,
                FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_state ON pipeline_runs(state)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_idea ON pipeline_runs(idea_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transitions_run ON state_transitions(run_id)")
        
        conn.commit()
        conn.close()
        logger.info(f"Initialized pipeline database: {self.db_path}")
    
    def process_queue(self, max_jobs: int = 1, timeout: int = 0):
        """
        Process jobs from Redis queue
        
        Args:
            max_jobs: Maximum number of jobs to process
            timeout: Timeout for blocking dequeue (0 = non-blocking)
        """
        logger.info(f"Processing queue (max_jobs={max_jobs})")
        
        processed = 0
        while processed < max_jobs:
            job = self.redis.dequeue("ideas:ready", timeout=timeout)
            
            if not job:
                logger.debug("No jobs available in queue")
                break
            
            logger.info(f"Dequeued job: {job.job_id} (idea: {job.idea_id})")
            
            try:
                self._process_job(job)
                processed += 1
            except Exception as e:
                logger.error(f"Job processing failed: {e}")
                self.redis.requeue_with_backoff("ideas:ready", job, str(e))
        
        logger.info(f"Processed {processed} job(s)")
    
    def _process_job(self, job: JobSchema):
        """Process a single job through the pipeline"""
        idea_payload = job.payload
        idea_id = job.idea_id
        
        logger.info(f"\n{'='*60}")
        logger.info(f"PROCESSING PIPELINE JOB: {idea_id}")
        logger.info(f"{'='*60}\n")
        
        # Create run tracking
        run_id = job.job_id
        self._create_run(run_id, idea_id, job.job_id)
        
        # Load idea from storage
        idea_obj = self.ideas.get_idea_by_id(idea_id)
        if not idea_obj:
            raise ValueError(f"Idea {idea_id} not found in storage")
        
        # Update idea status
        self.ideas.update_idea_status(idea_id, IdeaStatus.QUEUED)
        
        try:
            # Step 1: Script Composition
            self._update_state(run_id, PipelineState.SCRIPTING)
            self.ideas.update_idea_status(idea_id, IdeaStatus.SCRIPTING)
            
            script_result = self.script_composer.compose_script(idea_obj)
            if not script_result["within_target"]:
                logger.warning(f"Script word count outside target: {script_result['word_count']}")
            
            final_script = script_result["script"]
            
            # Update idea with final script
            self.ideas.update_idea_status(
                idea_id, IdeaStatus.SCRIPTING,
                script_final=final_script
            )
            
            # Step 2: Compliance Check
            self._update_state(run_id, PipelineState.COMPLIANCE)
            self.ideas.update_idea_status(idea_id, IdeaStatus.COMPLIANCE)
            
            compliance_result = self.compliance.check_script_compliance_iul(final_script)
            
            if not compliance_result["compliant"]:
                self._update_state(run_id, PipelineState.ERROR, 
                                 f"Compliance failed: {', '.join(compliance_result['issues'])}")
                self.ideas.update_idea_status(
                    idea_id, IdeaStatus.REJECTED,
                    error=f"Compliance: {compliance_result['issues']}"
                )
                return
            
            # Update idea with compliance result
            self.ideas.update_idea_status(
                idea_id, IdeaStatus.COMPLIANCE,
                compliance_result=compliance_result
            )
            
            # Step 3: TTS Generation
            self._update_state(run_id, PipelineState.TTS)
            self.ideas.update_idea_status(idea_id, IdeaStatus.TTS)
            
            audio_result = self.tts.generate_audio(final_script, idea_id)
            audio_path = audio_result["audio_path"]
            
            logger.info(f"Audio generated: {audio_path} ({audio_result['duration']:.1f}s)")
            
            # Update idea with audio path
            self.ideas.update_idea_status(
                idea_id, IdeaStatus.TTS,
                audio_path=audio_path
            )
            
            # Step 4: Video Rendering
            self._update_state(run_id, PipelineState.RENDERING)
            self.ideas.update_idea_status(idea_id, IdeaStatus.RENDERING)
            
            # Build Remotion props
            remotion_props = {
                "hook": idea_obj.hook,
                "bulletPoints": idea_obj.bullet_points,
                "cta": idea_obj.cta,
                "disclaimer": idea_obj.disclaimer
            }
            
            render_result = self.renderer.render_video(idea_id, remotion_props, audio_path)
            
            if not render_result.get("success"):
                raise Exception(f"Render failed: {render_result.get('error')}")
            
            video_path = render_result["video_path"]
            thumbnail_path = render_result.get("thumbnail_path")
            
            logger.info(f"Video rendered: {video_path}")
            
            # Update idea with video paths
            self.ideas.update_idea_status(
                idea_id, IdeaStatus.RENDERING,
                video_path=video_path,
                thumbnail_path=thumbnail_path
            )
            
            # Step 5: Post-Render Check (optional)
            self._update_state(run_id, PipelineState.POST_CHECK)
            self.ideas.update_idea_status(idea_id, IdeaStatus.POST_CHECK)
            
            video_check = self.compliance.quick_video_check(video_path)
            if not video_check["passed"]:
                logger.warning(f"Post-render check issues: {video_check['issues']}")
                # Don't fail on post-render issues, just log them
            
            # Step 6: Publishing
            self._update_state(run_id, PipelineState.PUBLISHING)
            self.ideas.update_idea_status(idea_id, IdeaStatus.PUBLISHING)
            
            publish_result = self.publisher.publish_iul_short(
                idea_id=idea_id,
                idea=idea_obj.to_dict(),
                video_path=video_path,
                audio_path=audio_path,
                thumbnail_path=thumbnail_path
            )
            
            if not publish_result.get("success"):
                raise Exception(f"Publishing failed: {publish_result.get('error')}")
            
            youtube_url = publish_result["youtube_url"]
            video_id = publish_result["video_id"]
            
            logger.info(f"Published: {youtube_url}")
            
            # Update idea as published
            self.ideas.update_idea_status(
                idea_id, IdeaStatus.PUBLISHED,
                youtube_video_id=video_id,
                youtube_url=youtube_url,
                published_at=time.time()
            )
            
            # Complete run
            self._update_state(run_id, PipelineState.COMPLETED)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ PIPELINE COMPLETED: {idea_id}")
            logger.info(f"YouTube URL: {youtube_url}")
            logger.info(f"{'='*60}\n")
            
        except Exception as e:
            logger.error(f"Pipeline error for {idea_id}: {e}")
            self._update_state(run_id, PipelineState.ERROR, str(e))
            self.ideas.update_idea_status(idea_id, IdeaStatus.ERROR, error=str(e))
            raise
    
    def _create_run(self, run_id: str, idea_id: str, job_id: str):
        """Create pipeline run record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.time()
        cursor.execute("""
            INSERT INTO pipeline_runs 
            (run_id, idea_id, job_id, state, started_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (run_id, idea_id, job_id, PipelineState.QUEUED.value, current_time, current_time))
        
        conn.commit()
        conn.close()
    
    def _update_state(self, run_id: str, new_state: PipelineState, error: str = None):
        """Update pipeline run state"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.time()
        
        # Get previous state
        cursor.execute("SELECT state, updated_at FROM pipeline_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        
        if row:
            prev_state, prev_time = row
            duration = current_time - prev_time
            
            # Log transition
            cursor.execute("""
                INSERT INTO state_transitions 
                (run_id, from_state, to_state, timestamp, duration)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, prev_state, new_state.value, current_time, duration))
        
        # Update run state
        if new_state == PipelineState.ERROR:
            cursor.execute("""
                UPDATE pipeline_runs 
                SET state = ?, error_message = ?, updated_at = ?
                WHERE run_id = ?
            """, (new_state.value, error, current_time, run_id))
        elif new_state == PipelineState.COMPLETED:
            cursor.execute("""
                UPDATE pipeline_runs 
                SET state = ?, updated_at = ?, completed_at = ?
                WHERE run_id = ?
            """, (new_state.value, current_time, current_time, run_id))
        else:
            cursor.execute("""
                UPDATE pipeline_runs 
                SET state = ?, updated_at = ?
                WHERE run_id = ?
            """, (new_state.value, current_time, run_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Pipeline state: {run_id} → {new_state.value}")
    
    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get pipeline run status"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_active_runs(self) -> list:
        """Get all active pipeline runs"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        active_states = [
            PipelineState.QUEUED.value,
            PipelineState.SCRIPTING.value,
            PipelineState.COMPLIANCE.value,
            PipelineState.TTS.value,
            PipelineState.RENDERING.value,
            PipelineState.POST_CHECK.value,
            PipelineState.PUBLISHING.value
        ]
        
        placeholders = ','.join('?' * len(active_states))
        cursor.execute(f"""
            SELECT * FROM pipeline_runs 
            WHERE state IN ({placeholders})
            ORDER BY started_at DESC
        """, active_states)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def cleanup_old_runs(self, days: int = 30):
        """Clean up old completed/error runs"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete old transitions
        cursor.execute("""
            DELETE FROM state_transitions 
            WHERE run_id IN (
                SELECT run_id FROM pipeline_runs 
                WHERE (state = ? OR state = ?) AND updated_at < ?
            )
        """, (PipelineState.COMPLETED.value, PipelineState.ERROR.value, cutoff_time))
        
        # Delete old runs
        cursor.execute("""
            DELETE FROM pipeline_runs 
            WHERE (state = ? OR state = ?) AND updated_at < ?
        """, (PipelineState.COMPLETED.value, PipelineState.ERROR.value, cutoff_time))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old pipeline runs")


# CLI entry point for manual testing
if __name__ == "__main__":
    import sys
    import os
    from config import REDIS_CONFIG
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load connections (simplified for testing)
    logger.info("Initializing pipeline components...")
    
    # Initialize components
    redis_client = RedisQueueClient(redis_url=REDIS_CONFIG["url"])
    ideas_manager = IdeasManager()
    
    # Check Redis connection
    if not redis_client.healthcheck():
        logger.error("Redis connection failed - ensure Redis is running")
        sys.exit(1)
    
    # Show queue stats
    stats = redis_client.get_stats()
    logger.info(f"Queue stats: {stats}")
    
    # Check if --once flag
    once_mode = "--once" in sys.argv
    
    if once_mode:
        logger.info("Running in once mode (process one job)")
        # Process would happen here with full component initialization
        logger.info("Note: Full pipeline requires all connections to be initialized")
    else:
        logger.info("Use --once flag to process one job")
