"""
Editing Agent for ZerePy Content Pipeline
Applies light editing to clips using FFmpeg and MoviePy
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import json

logger = logging.getLogger("editing_agent")


class EditingAgent:
    """
    Applies light automated editing to video clips for YouTube Shorts
    Uses FFmpeg for video processing and optional MoviePy for advanced features
    """
    
    def __init__(self, pipeline_manager, output_format: str = "shorts",
                 add_captions: bool = True, background_music: bool = False,
                 target_resolution: str = "1080p"):
        """
        Initialize the Editing Agent
        
        Args:
            pipeline_manager: ContentPipeline instance
            output_format: Output format ('shorts' for 9:16, 'square' for 1:1)
            add_captions: Whether to add text captions
            background_music: Whether to add background music
            target_resolution: Target resolution ('1080p' or '4k')
        """
        self.pipeline_manager = pipeline_manager
        self.output_format = output_format
        self.add_captions = add_captions
        self.background_music = background_music
        self.target_resolution = target_resolution
        
        # Resolution settings
        if target_resolution == "4k":
            self.width = 2160
            self.height = 3840
        else:  # 1080p
            self.width = 1080
            self.height = 1920
        
        logger.info(f"Editing Agent initialized")
        logger.info(f"  Format: {output_format} ({self.width}x{self.height})")
        logger.info(f"  Captions: {add_captions}")
        logger.info(f"  Background music: {background_music}")
    
    def process_clips(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Process all clips for a video
        
        Args:
            video_id: Pipeline video ID
            
        Returns:
            List of edited clip dictionaries
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"🎬 EDITING AGENT - PROCESSING CLIPS")
            logger.info(f"{'='*60}")
            logger.info(f"Video ID: {video_id}")
            
            # Get clips from pipeline
            clips = self.pipeline_manager.get_clips_for_video(video_id)
            
            if not clips:
                logger.warning("No clips found to edit")
                return []
            
            logger.info(f"Found {len(clips)} clips to edit")
            
            edited_clips = []
            for i, clip in enumerate(clips, 1):
                logger.info(f"\n📝 Editing clip {i}/{len(clips)}")
                logger.info(f"  Clip ID: {clip['clip_id']}")
                logger.info(f"  Duration: {clip['duration']:.1f}s")
                
                # Edit the clip
                edited_path = self.edit_clip(
                    clip['clip_path'],
                    clip.get('transcript', ''),
                    clip['clip_id']
                )
                
                if edited_path:
                    clip['edited_path'] = edited_path
                    edited_clips.append(clip)
                    logger.info(f"  ✅ Edited: {Path(edited_path).name}")
                else:
                    logger.warning(f"  ❌ Edit failed")
            
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ EDITING AGENT COMPLETE")
            logger.info(f"Edited {len(edited_clips)}/{len(clips)} clips")
            logger.info(f"{'='*60}\n")
            
            return edited_clips
            
        except Exception as e:
            logger.error(f"Failed to process clips: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def edit_clip(self, clip_path: str, transcript: str, clip_id: str) -> Optional[str]:
        """
        Apply all editing operations to a single clip
        
        Args:
            clip_path: Path to input clip
            transcript: Transcript text for captions
            clip_id: Clip identifier
            
        Returns:
            Path to edited clip or None if failed
        """
        try:
            # Generate output path
            output_dir = Path("data/content_pipeline/edited_clips")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            output_path = output_dir / f"edited_{clip_id}_{timestamp}.mp4"
            
            # Build FFmpeg filter chain
            filters = []
            
            # Step 1: Convert to vertical format (9:16)
            filters.append(self._get_vertical_filter())
            
            # Step 2: Video enhancements
            filters.append(self._get_enhancement_filter())
            
            # Combine filters
            filter_complex = ",".join(filters)
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output
                '-i', clip_path,
                '-vf', filter_complex,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '44100',
                '-af', 'loudnorm',  # Audio normalization
                '-loglevel', 'error',
                str(output_path)
            ]
            
            logger.info("  Applying video edits...")
            subprocess.run(cmd, check=True, timeout=300)
            
            # If captions are requested, add them in a second pass
            if self.add_captions and transcript:
                captioned_path = self._add_captions(output_path, transcript, clip_id)
                if captioned_path:
                    output_path = Path(captioned_path)
            
            if output_path.exists():
                return str(output_path)
            else:
                logger.error("Editing produced no output")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout during editing")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to edit clip: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_vertical_filter(self) -> str:
        """
        Get FFmpeg filter for converting to vertical format
        
        Returns:
            FFmpeg filter string
        """
        # Scale and crop to 9:16 aspect ratio
        # This crops the center for vertical format
        return f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,crop={self.width}:{self.height}"
    
    def _get_enhancement_filter(self) -> str:
        """
        Get FFmpeg filter for video enhancements
        
        Returns:
            FFmpeg filter string
        """
        enhancements = []
        
        # Auto color correction
        enhancements.append("eq=contrast=1.1:brightness=0.05:saturation=1.2")
        
        # Denoise (light)
        enhancements.append("hqdn3d=1.5:1.5:6:6")
        
        # Sharpen (light)
        enhancements.append("unsharp=5:5:0.8:3:3:0.4")
        
        return ",".join(enhancements)
    
    def _add_captions(self, video_path: Path, transcript: str, clip_id: str) -> Optional[str]:
        """
        Add text captions to video
        
        Args:
            video_path: Path to video file
            transcript: Transcript text
            clip_id: Clip identifier
            
        Returns:
            Path to captioned video or None if failed
        """
        try:
            logger.info("  Adding captions...")
            
            # Generate output path
            output_path = video_path.parent / f"{video_path.stem}_captioned.mp4"
            
            # Extract key quote from transcript (first 100 chars)
            caption_text = transcript[:100].strip()
            if len(transcript) > 100:
                caption_text += "..."
            
            # Escape special characters for FFmpeg
            caption_text = caption_text.replace("'", "\\'").replace(":", "\\:")
            
            # Create drawtext filter for captions
            # Position at bottom with black background box
            drawtext_filter = (
                f"drawtext=text='{caption_text}':"
                f"fontfile=/Windows/Fonts/arial.ttf:"  # Windows font path
                f"fontsize=32:"
                f"fontcolor=white:"
                f"x=(w-text_w)/2:"  # Center horizontally
                f"y=h-th-100:"  # 100px from bottom
                f"box=1:"
                f"boxcolor=black@0.5:"
                f"boxborderw=10"
            )
            
            # Apply caption
            cmd = [
                'ffmpeg',
                '-y',
                '-i', str(video_path),
                '-vf', drawtext_filter,
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'copy',
                '-loglevel', 'error',
                str(output_path)
            ]
            
            subprocess.run(cmd, check=True, timeout=180)
            
            if output_path.exists():
                # Replace original with captioned version
                video_path.unlink()
                output_path.rename(video_path)
                return str(video_path)
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to add captions: {e}")
            # Return original video path if caption addition fails
            return str(video_path)
    
    def apply_background_music(self, video_path: str, music_path: str,
                              volume: float = 0.2) -> Optional[str]:
        """
        Add background music to video
        
        Args:
            video_path: Path to video file
            music_path: Path to music file
            volume: Music volume (0.0-1.0)
            
        Returns:
            Path to video with music or None if failed
        """
        try:
            output_path = Path(video_path).parent / f"{Path(video_path).stem}_music.mp4"
            
            cmd = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-i', music_path,
                '-filter_complex',
                f'[1:a]volume={volume}[music];[0:a][music]amix=inputs=2:duration=shortest',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-loglevel', 'error',
                str(output_path)
            ]
            
            subprocess.run(cmd, check=True, timeout=180)
            
            if output_path.exists():
                return str(output_path)
            return None
            
        except Exception as e:
            logger.error(f"Failed to add background music: {e}")
            return None
    
    def upscale_to_4k(self, video_path: str) -> Optional[str]:
        """
        Upscale video to 4K resolution
        
        Args:
            video_path: Path to video file
            
        Returns:
            Path to upscaled video or None if failed
        """
        try:
            logger.info("  Upscaling to 4K...")
            
            output_path = Path(video_path).parent / f"{Path(video_path).stem}_4k.mp4"
            
            # Use lanczos scaling for quality
            cmd = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-vf', 'scale=2160:3840:flags=lanczos',
                '-c:v', 'libx264',
                '-preset', 'slow',
                '-crf', '18',
                '-c:a', 'copy',
                '-loglevel', 'error',
                str(output_path)
            ]
            
            subprocess.run(cmd, check=True, timeout=600)
            
            if output_path.exists():
                return str(output_path)
            return None
            
        except Exception as e:
            logger.error(f"Failed to upscale: {e}")
            return None
    
    def stabilize_video(self, video_path: str) -> Optional[str]:
        """
        Apply video stabilization (useful for handheld/walking videos)
        
        Args:
            video_path: Path to video file
            
        Returns:
            Path to stabilized video or None if failed
        """
        try:
            logger.info("  Stabilizing video...")
            
            # Two-pass stabilization with FFmpeg vidstab
            transforms_file = Path(video_path).parent / "transforms.trf"
            output_path = Path(video_path).parent / f"{Path(video_path).stem}_stable.mp4"
            
            # Pass 1: Detect
            cmd1 = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-vf', f'vidstabdetect=shakiness=5:accuracy=15:result={transforms_file}',
                '-f', 'null',
                '-loglevel', 'error',
                '-'
            ]
            
            subprocess.run(cmd1, check=True, timeout=300)
            
            # Pass 2: Transform
            cmd2 = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-vf', f'vidstabtransform=input={transforms_file}:zoom=0:smoothing=10',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'copy',
                '-loglevel', 'error',
                str(output_path)
            ]
            
            subprocess.run(cmd2, check=True, timeout=300)
            
            # Cleanup transforms file
            if transforms_file.exists():
                transforms_file.unlink()
            
            if output_path.exists():
                return str(output_path)
            return None
            
        except Exception as e:
            logger.warning(f"Stabilization failed (vidstab may not be installed): {e}")
            return None

