"""
Clips Agent for ZerePy Content Pipeline
Analyzes videos and extracts the best segments for short-form content
"""

import logging
import subprocess
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
import sys
import os

# Import centralized configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import CLIPS_CONFIG, AI_CONFIG

logger = logging.getLogger("clips_agent")


class ClipsAgent:
    """
    Analyzes videos and extracts best segments for short-form content
    Uses Whisper for transcription and AI for content analysis
    """
    
    def __init__(self, deepseek_connection, pipeline_manager,
                 config_override: Optional[Dict[str, Any]] = None):
        """
        Initialize the Clips Agent

        Args:
            deepseek_connection: DeepSeek API connection for AI analysis
            pipeline_manager: ContentPipeline instance
            config_override: Optional config overrides
        """
        # Use centralized config with optional overrides
        config = CLIPS_CONFIG.copy()
        if config_override:
            config.update(config_override)

        self.deepseek = deepseek_connection
        self.pipeline_manager = pipeline_manager
        self.target_duration_min = config["target_duration_min"]
        self.target_duration_max = config["target_duration_max"]
        self.num_clips = config["num_clips"]
        self.whisper_model = config["whisper_model"]
        self.ai_model = config["ai_model"]

        # Create processing directories
        self.processed_clips_dir = Path(config["processed_clips_dir"])
        self.temp_dir = Path(config["temp_dir"])
        self.processed_clips_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Lazy-loaded Whisper model
        self._whisper_model = None

        logger.info(f"Clips Agent initialized")
        logger.info(f"  Target duration: {self.target_duration_min}-{self.target_duration_max}s")
        logger.info(f"  Clips per video: {self.num_clips}")
        logger.info(f"  Whisper model: {self.whisper_model}")
    
    def process_video(self, video_id: str, video_path: str) -> List[Dict[str, Any]]:
        """
        Process a video and generate clip candidates
        
        Args:
            video_id: Pipeline video ID
            video_path: Path to video file
            
        Returns:
            List of clip dictionaries with segments, transcripts, and scores
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"✂️  CLIPS AGENT - PROCESSING VIDEO")
            logger.info(f"{'='*60}")
            logger.info(f"Video ID: {video_id}")
            logger.info(f"Video: {Path(video_path).name}")
            
            # Update pipeline state
            from src.pipeline_manager import PipelineState
            self.pipeline_manager.update_state(video_id, PipelineState.CLIPPING)
            
            # Step 1: Transcribe video with timestamps
            logger.info(f"\n🎤 Step 1: Transcribing audio...")
            transcript = self._transcribe_video(video_path)
            
            if not transcript:
                logger.error("Transcription failed")
                self.pipeline_manager.update_state(
                    video_id, PipelineState.ERROR,
                    error_message="Transcription failed"
                )
                return []
            
            logger.info(f"✅ Transcription complete: {len(transcript)} words")
            
            # Step 2: Analyze audio for engagement signals
            logger.info(f"\n📊 Step 2: Analyzing audio engagement signals...")
            audio_analysis = self._analyze_audio(video_path)
            
            # Step 3: AI analysis to find golden moments
            logger.info(f"\n🤖 Step 3: AI analysis to identify best segments...")
            clip_candidates = self._ai_analyze_content(
                transcript, audio_analysis, video_path
            )
            
            if not clip_candidates:
                logger.warning("No suitable clips found")
                self.pipeline_manager.update_state(
                    video_id, PipelineState.ERROR,
                    error_message="No suitable clips found"
                )
                return []
            
            # Step 4: Extract clips and save to database
            logger.info(f"\n✂️  Step 4: Extracting clips...")
            extracted_clips = []
            
            for i, candidate in enumerate(clip_candidates[:self.num_clips], 1):
                logger.info(f"\nClip {i}/{min(self.num_clips, len(clip_candidates))}:")
                logger.info(f"  Time: {candidate['start_time']:.1f}s - {candidate['end_time']:.1f}s")
                logger.info(f"  Duration: {candidate['duration']:.1f}s")
                logger.info(f"  Score: {candidate['score']:.2f}/1.0")
                logger.info(f"  Reason: {candidate.get('reason', 'N/A')[:100]}")
                
                # Extract clip from video
                clip_path = self._extract_clip(
                    video_path, candidate['start_time'], candidate['end_time'], i
                )
                
                if clip_path:
                    # Add to pipeline database
                    clip_id = self.pipeline_manager.add_generated_clip(
                        video_id=video_id,
                        clip_path=clip_path,
                        start_time=candidate['start_time'],
                        end_time=candidate['end_time'],
                        transcript=candidate.get('transcript', ''),
                        score=candidate['score']
                    )
                    
                    candidate['clip_id'] = clip_id
                    candidate['clip_path'] = clip_path
                    extracted_clips.append(candidate)
                    
                    logger.info(f"✅ Clip extracted: {Path(clip_path).name}")
            
            # Update pipeline state
            self.pipeline_manager.update_state(video_id, PipelineState.EDITING)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ CLIPS AGENT COMPLETE")
            logger.info(f"Generated {len(extracted_clips)} clips")
            logger.info(f"{'='*60}\n")
            
            return extracted_clips
            
        except Exception as e:
            logger.error(f"Failed to process video: {e}")
            import traceback
            traceback.print_exc()
            
            from src.pipeline_manager import PipelineState
            self.pipeline_manager.update_state(
                video_id, PipelineState.ERROR,
                error_message=f"Clips agent error: {str(e)}"
            )
            return []
    
    def _transcribe_video(self, video_path: str) -> Optional[str]:
        """
        Transcribe video audio using Whisper
        
        Args:
            video_path: Path to video file
            
        Returns:
            Transcribed text with timestamps or None if failed
        """
        try:
            # Check if whisper is installed
            try:
                import whisper
            except ImportError:
                logger.warning("Whisper not installed - using mock transcription")
                return self._mock_transcription(video_path)
            
            # Load Whisper model (base is good for speed/accuracy balance)
            logger.info("Loading Whisper model...")
            model = whisper.load_model("base")
            
            # Transcribe
            logger.info("Transcribing (this may take a minute)...")
            result = model.transcribe(video_path, verbose=False)
            
            # Format transcription with timestamps
            transcription_parts = []
            for segment in result['segments']:
                start = segment['start']
                end = segment['end']
                text = segment['text'].strip()
                transcription_parts.append(f"[{start:.1f}s-{end:.1f}s] {text}")
            
            full_transcript = "\n".join(transcription_parts)
            
            # Also store segments for analysis
            self._transcript_segments = result['segments']
            
            return full_transcript
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
    
    def _mock_transcription(self, video_path: str) -> str:
        """Mock transcription for testing without Whisper"""
        duration = self._get_video_duration(video_path)
        return f"[0.0s-{duration:.1f}s] This is a mock transcription for testing purposes. The actual content would be transcribed here."
    
    def _analyze_audio(self, video_path: str) -> Dict[str, Any]:
        """
        Analyze audio for engagement signals (volume changes, pauses, etc.)
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with audio analysis data
        """
        try:
            # Use ffmpeg to extract audio features
            # For now, return basic analysis
            duration = self._get_video_duration(video_path)
            
            return {
                "duration": duration,
                "has_audio": True,
                "volume_peaks": [],  # Could detect volume spikes
                "silence_periods": []  # Could detect pauses
            }
            
        except Exception as e:
            logger.warning(f"Audio analysis failed: {e}")
            return {"duration": 0, "has_audio": False}
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(result.stdout.strip())
        except:
            return 0.0
    
    def _ai_analyze_content(self, transcript: str, audio_analysis: Dict,
                           video_path: str) -> List[Dict[str, Any]]:
        """
        Use AI to analyze content and identify best segments
        
        Args:
            transcript: Transcribed text with timestamps
            audio_analysis: Audio analysis data
            video_path: Path to video file
            
        Returns:
            List of clip candidate dictionaries
        """
        try:
            duration = audio_analysis.get('duration', 0)
            
            # Build analysis prompt
            prompt = f"""Analyze this video transcript and identify the {self.num_clips} best segments for creating engaging short-form content (YouTube Shorts/Instagram Reels).

Video Duration: {duration:.1f} seconds
Target Clip Duration: {self.target_duration_min}-{self.target_duration_max} seconds

TRANSCRIPT:
{transcript[:4000]}  # Limit transcript length for API

CRITERIA FOR "GOLDEN MOMENTS":
1. Key insights, lessons, or "aha" moments
2. Interesting questions or thought-provoking statements
3. Stories, examples, or analogies
4. Strong emotional moments (enthusiasm, emphasis)
5. Complete thoughts that stand alone
6. Engaging opening hooks

IMPORTANT:
- Each segment MUST be {self.target_duration_min}-{self.target_duration_max} seconds long
- Segments should have natural start/end points (complete sentences)
- Prioritize content that works without context
- Look for variety across clips

Respond in JSON format with an array of clips:
[
  {{
    "start_time": <seconds>,
    "end_time": <seconds>,
    "duration": <seconds>,
    "score": <0.0-1.0>,
    "reason": "<why this segment is engaging>",
    "transcript": "<key quotes from this segment>",
    "hook": "<what makes this segment compelling>"
  }}
]

Provide exactly {self.num_clips} clip candidates, ordered by score (highest first)."""

            # Call AI
            logger.info("Sending to AI for analysis...")
            response = self.deepseek.generate_text(
                prompt=prompt,
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse response
            response_text = response.strip()
            
            # Try to extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # Find JSON array
            if "[" in response_text:
                json_start = response_text.find("[")
                json_end = response_text.rfind("]") + 1
                response_text = response_text[json_start:json_end]
            
            clips = json.loads(response_text)
            
            # Validate and filter clips
            valid_clips = []
            for clip in clips:
                duration = clip['end_time'] - clip['start_time']
                clip['duration'] = duration
                
                # Ensure within target range
                if self.target_duration_min <= duration <= self.target_duration_max:
                    # Ensure within video duration
                    if clip['end_time'] <= audio_analysis.get('duration', float('inf')):
                        valid_clips.append(clip)
            
            logger.info(f"✅ AI identified {len(valid_clips)} valid clip candidates")
            return valid_clips
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Fallback: create simple clips
            return self._create_fallback_clips(audio_analysis.get('duration', 0))
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_clips(audio_analysis.get('duration', 0))
    
    def _create_fallback_clips(self, duration: float) -> List[Dict[str, Any]]:
        """Create simple fallback clips if AI analysis fails"""
        if duration < self.target_duration_min:
            # If video is too short, create one clip with the full duration
            # (it will be filtered out later if still too short)
            return [{
                "start_time": 0.0,
                "end_time": duration,
                "duration": duration,
                "score": 0.3,
                "reason": f"Fallback clip (video too short: {duration:.1f}s < {self.target_duration_min}s)",
                "transcript": "",
                "hook": "Full video segment"
            }]

        clips = []
        # Try to create clips that meet minimum duration
        max_clips = min(self.num_clips, int(duration / self.target_duration_min))

        if max_clips == 0:
            # Fallback: create one clip with maximum possible duration
            clip_duration = min(self.target_duration_max, duration)
            clips.append({
                "start_time": 0.0,
                "end_time": clip_duration,
                "duration": clip_duration,
                "score": 0.4,
                "reason": f"Fallback clip (adjusted for short video: {duration:.1f}s)",
                "transcript": "",
                "hook": "Extended segment"
            })
        else:
            # Create multiple clips that meet minimum duration
            clip_duration = min(self.target_duration_max, duration / max_clips)

            for i in range(max_clips):
                start_time = i * clip_duration
                end_time = min(start_time + clip_duration, duration)

                clips.append({
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": end_time - start_time,
                    "score": 0.5,
                    "reason": "Fallback clip (AI analysis unavailable)",
                    "transcript": "",
                    "hook": "Auto-generated segment"
                })

        return clips
    
    def _extract_clip(self, video_path: str, start_time: float, end_time: float,
                     clip_number: int) -> Optional[str]:
        """
        Extract a clip from the video using FFmpeg
        
        Args:
            video_path: Path to source video
            start_time: Start time in seconds
            end_time: End time in seconds
            clip_number: Clip number for naming
            
        Returns:
            Path to extracted clip or None if failed
        """
        try:
            # Generate output path
            video_name = Path(video_path).stem
            timestamp = int(time.time())
            output_dir = Path("data/content_pipeline/processed_clips")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{video_name}_clip{clip_number}_{timestamp}.mp4"
            
            # Extract clip with FFmpeg
            duration = end_time - start_time
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-ss', str(start_time),
                '-i', video_path,
                '-t', str(duration),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-strict', 'experimental',
                '-b:a', '192k',
                '-loglevel', 'error',
                str(output_path)
            ]
            
            subprocess.run(cmd, check=True, timeout=120)
            
            if output_path.exists():
                return str(output_path)
            else:
                logger.error(f"Clip extraction produced no output: {output_path}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timeout during clip extraction")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error during clip extraction: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract clip: {e}")
            return None

