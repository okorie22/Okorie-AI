"""
Video Condenser Agent for ZerePy Content Pipeline
Condenses long-form videos into engaging shorts while preserving narrative flow
"""

import logging
import subprocess
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

logger = logging.getLogger("condenser_agent")


class CondenserAgent:
    """
    Condenses long-form videos into engaging shorts while maintaining narrative flow
    Uses transcript analysis and content understanding to preserve coherence
    """
    
    def __init__(self, deepseek_connection, pipeline_manager,
                 config_override: Optional[Dict[str, Any]] = None):
        """
        Initialize the Condenser Agent
        
        Args:
            deepseek_connection: DeepSeek API connection for AI analysis
            pipeline_manager: ContentPipeline instance
            config_override: Optional config overrides
        """
        # Import config
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from config import CLIPS_CONFIG, AI_CONFIG, PIPELINE_MODES
        
        # Get condensation mode config
        mode_config = PIPELINE_MODES.get("condensation", {})
        editing_profile = mode_config.get("editing_profile", {})
        
        # Use centralized config with mode-specific settings
        config = CLIPS_CONFIG.copy()
        if config_override:
            config.update(config_override)
        
        self.deepseek = deepseek_connection
        self.pipeline_manager = pipeline_manager
        
        # Condensation-specific settings
        self.preserve_narrative_flow = mode_config.get("preserve_narrative_flow", True)
        self.fade_duration = editing_profile.get("fade_duration", 0.5)
        self.target_duration_min = config.get("target_duration_min", 45)
        self.target_duration_max = config.get("target_duration_max", 90)
        self.whisper_model_name = config.get("whisper_model", "base")
        
        # Lazy-loaded Whisper model
        self._whisper_model = None
        
        # Create processing directories
        self.processed_clips_dir = Path(config.get("processed_clips_dir"))
        self.temp_dir = Path(config.get("temp_dir"))
        self.processed_clips_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Condenser Agent initialized")
        logger.info(f"  Target duration: {self.target_duration_min}-{self.target_duration_max}s")
        logger.info(f"  Preserve narrative flow: {self.preserve_narrative_flow}")
    
    @property
    def whisper_model(self):
        """Lazy-load Whisper model"""
        if self._whisper_model is None:
            try:
                import whisper
                logger.info(f"Loading Whisper model: {self.whisper_model_name}...")
                self._whisper_model = whisper.load_model(self.whisper_model_name)
                logger.info("✅ Whisper model loaded")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise
        return self._whisper_model
    
    def process_video_for_condensation(self, video_path: str, video_id: str) -> Dict[str, Any]:
        """
        Process a long-form video and condense it into an engaging short
        
        Args:
            video_path: Path to the source video
            video_id: Pipeline video ID
            
        Returns:
            Dictionary with condensed clip information
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🎬 CONDENSING LONG-FORM VIDEO")
        logger.info(f"{'='*60}")
        logger.info(f"Video: {Path(video_path).name}")
        
        try:
            # Step 1: Get video duration
            duration = self._get_video_duration(video_path)
            logger.info(f"📊 Source video duration: {duration:.1f}s ({duration/60:.1f} min)")
            
            # Step 2: Transcribe the video
            logger.info(f"🎤 Transcribing audio...")
            transcript_data = self._transcribe_video(video_path)
            full_transcript = transcript_data.get("text", "")
            segments = transcript_data.get("segments", [])
            logger.info(f"✅ Transcription complete: {len(segments)} segments")
            
            # Step 3: Analyze content structure and identify key moments
            logger.info(f"🔍 Analyzing content structure...")
            condensation_plan = self._analyze_content_structure(
                full_transcript, segments, duration
            )
            
            # Step 4: Extract and combine segments
            logger.info(f"✂️  Extracting and combining segments...")
            condensed_clip = self._create_condensed_clip(
                video_path, condensation_plan, video_id
            )
            
            logger.info(f"✅ Condensation complete!")
            logger.info(f"Output: {condensed_clip['clip_path']}")
            logger.info(f"Duration: {condensed_clip['duration']:.1f}s")
            logger.info(f"{'='*60}\n")
            
            return condensed_clip
            
        except Exception as e:
            logger.error(f"Condensation failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data.get('format', {}).get('duration', 0))
        except Exception as e:
            logger.error(f"Failed to get duration: {e}")
        return 0
    
    def _transcribe_video(self, video_path: str) -> Dict[str, Any]:
        """Transcribe video using Whisper"""
        try:
            result = self.whisper_model.transcribe(
                video_path,
                verbose=False,
                word_timestamps=True
            )
            return result
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {"text": "", "segments": []}
    
    def _analyze_content_structure(self, transcript: str, segments: List[Dict],
                                   duration: float) -> Dict[str, Any]:
        """
        Analyze content to create a condensation plan that preserves flow
        
        Args:
            transcript: Full video transcript
            segments: Transcript segments with timestamps
            duration: Total video duration
            
        Returns:
            Condensation plan with selected segments
        """
        # Build analysis prompt
        prompt = f"""Analyze this long-form video transcript and create a condensation plan.

VIDEO DETAILS:
- Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)
- Target condensed duration: {self.target_duration_min}-{self.target_duration_max} seconds

TRANSCRIPT:
{transcript[:4000]}  # Limit for token efficiency

TASK:
Create a condensation plan that:
1. Identifies the main narrative arc or key topics
2. Selects segments that preserve story flow and coherence
3. Ensures smooth transitions between selected segments
4. Maintains the core message and value
5. Fits within target duration

Respond with JSON:
{{
  "narrative_summary": "Brief summary of main narrative/message",
  "key_moments": [
    {{
      "start_time": 0.0,
      "end_time": 15.0,
      "reason": "Why this segment is important",
      "transition_note": "How it connects to next segment"
    }}
  ],
  "estimated_duration": 60,
  "flow_notes": "Notes on maintaining narrative flow"
}}

Ensure segments flow naturally and tell a coherent story."""

        try:
            response = self.deepseek.make_request(prompt)
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                logger.info(f"📋 Condensation plan: {plan.get('narrative_summary', '')}")
                logger.info(f"📊 Selected {len(plan.get('key_moments', []))} key segments")
                return plan
            else:
                logger.warning("Failed to parse AI response, using fallback")
                return self._create_fallback_plan(duration, segments)
                
        except Exception as e:
            logger.error(f"Content analysis error: {e}")
            return self._create_fallback_plan(duration, segments)
    
    def _create_fallback_plan(self, duration: float, segments: List[Dict]) -> Dict[str, Any]:
        """Create a simple fallback condensation plan"""
        # Simple strategy: extract evenly spaced segments
        target_duration = (self.target_duration_min + self.target_duration_max) / 2
        segment_duration = 10  # 10 second segments
        num_segments = int(target_duration / segment_duration)
        
        step = duration / (num_segments + 1)
        key_moments = []
        
        for i in range(num_segments):
            start = step * (i + 1)
            end = start + segment_duration
            if end <= duration:
                key_moments.append({
                    "start_time": start,
                    "end_time": end,
                    "reason": "Evenly distributed segment",
                    "transition_note": "Sequential"
                })
        
        return {
            "narrative_summary": "Condensed highlights",
            "key_moments": key_moments,
            "estimated_duration": len(key_moments) * segment_duration,
            "flow_notes": "Evenly distributed segments"
        }
    
    def _create_condensed_clip(self, video_path: str, plan: Dict[str, Any],
                               video_id: str) -> Dict[str, Any]:
        """
        Extract and combine segments into condensed clip with transitions
        
        Args:
            video_path: Source video path
            plan: Condensation plan with segments
            video_id: Pipeline video ID
            
        Returns:
            Condensed clip information
        """
        segments = plan.get("key_moments", [])
        if not segments:
            raise ValueError("No segments in condensation plan")
        
        # Create temp directory for segment files
        temp_dir = self.temp_dir / f"condense_{video_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Extract individual segments
            segment_files = []
            for i, segment in enumerate(segments):
                start_time = segment["start_time"]
                duration = segment["end_time"] - segment["start_time"]
                
                segment_file = temp_dir / f"segment_{i:03d}.mp4"
                
                # Extract segment with fade effects if preserving flow
                if self.preserve_narrative_flow and self.fade_duration > 0:
                    # Add fade in/out for smooth transitions
                    cmd = [
                        'ffmpeg', '-i', video_path,
                        '-ss', str(start_time),
                        '-t', str(duration),
                        '-vf', f'fade=t=in:st=0:d={self.fade_duration},fade=t=out:st={duration-self.fade_duration}:d={self.fade_duration}',
                        '-af', f'afade=t=in:st=0:d={self.fade_duration},afade=t=out:st={duration-self.fade_duration}:d={self.fade_duration}',
                        '-c:v', 'libx264', '-c:a', 'aac',
                        '-y', str(segment_file)
                    ]
                else:
                    cmd = [
                        'ffmpeg', '-i', video_path,
                        '-ss', str(start_time),
                        '-t', str(duration),
                        '-c', 'copy',
                        '-y', str(segment_file)
                    ]
                
                subprocess.run(cmd, capture_output=True, check=True)
                segment_files.append(segment_file)
                logger.info(f"  ✓ Extracted segment {i+1}/{len(segments)}")
            
            # Combine all segments
            output_filename = f"condensed_{video_id}_{int(time.time())}.mp4"
            output_path = self.processed_clips_dir / output_filename
            
            # Create concat file
            concat_file = temp_dir / "concat.txt"
            with open(concat_file, 'w') as f:
                for seg_file in segment_files:
                    f.write(f"file '{seg_file.absolute()}'\n")
            
            # Concatenate segments
            cmd = [
                'ffmpeg', '-f', 'concat', '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                '-y', str(output_path)
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            
            # Get final duration
            final_duration = self._get_video_duration(str(output_path))
            
            return {
                "clip_id": f"condensed_{video_id}",
                "video_id": video_id,
                "clip_path": str(output_path),
                "duration": final_duration,
                "segment_count": len(segments),
                "narrative_summary": plan.get("narrative_summary", ""),
                "created_at": time.time()
            }
            
        finally:
            # Cleanup temp files
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")

