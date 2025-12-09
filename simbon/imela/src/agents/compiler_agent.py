"""
Video Compiler Agent for ZerePy Content Pipeline
Combines multiple videos into one cohesive short video with smooth transitions
"""

import logging
import subprocess
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

logger = logging.getLogger("compiler_agent")


class CompilerAgent:
    """
    Combines multiple videos into one cohesive short video
    Handles transitions, audio mixing, and maintaining visual coherence
    """
    
    def __init__(self, deepseek_connection, pipeline_manager,
                 config_override: Optional[Dict[str, Any]] = None):
        """
        Initialize the Compiler Agent
        
        Args:
            deepseek_connection: DeepSeek API connection for AI analysis
            pipeline_manager: ContentPipeline instance
            config_override: Optional config overrides
        """
        # Import config
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from config import CLIPS_CONFIG, COMPILATION_CONFIG, PIPELINE_MODES
        
        # Get compilation mode config
        mode_config = PIPELINE_MODES.get("compilation", {})
        editing_profile = mode_config.get("editing_profile", {})
        
        # Use centralized config with mode-specific settings
        config = CLIPS_CONFIG.copy()
        config.update(COMPILATION_CONFIG)
        if config_override:
            config.update(config_override)
        
        self.deepseek = deepseek_connection
        self.pipeline_manager = pipeline_manager
        
        # Compilation-specific settings
        self.max_source_videos = mode_config.get("max_source_videos", 5)
        self.cross_fade_duration = editing_profile.get("cross_fade_duration", 1.0)
        self.transition_style = editing_profile.get("transition_style", "smooth")
        self.audio_mixing = editing_profile.get("audio_mixing", True)
        self.audio_normalization = editing_profile.get("audio_normalization", True)
        self.consistent_color_grading = editing_profile.get("consistent_color_grading", True)
        self.auto_sort_by_timestamp = config.get("auto_sort_by_timestamp", True)
        self.target_total_duration = config.get("target_total_duration", 60)
        
        # Create processing directories
        self.processed_clips_dir = Path(config.get("processed_clips_dir"))
        self.temp_dir = Path(config.get("temp_dir"))
        self.processed_clips_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Compiler Agent initialized")
        logger.info(f"  Max source videos: {self.max_source_videos}")
        logger.info(f"  Cross-fade duration: {self.cross_fade_duration}s")
        logger.info(f"  Transition style: {self.transition_style}")
    
    def process_videos_for_compilation(self, video_paths: List[str], 
                                       group_id: str) -> Dict[str, Any]:
        """
        Compile multiple videos into one cohesive short video
        
        Args:
            video_paths: List of source video paths
            group_id: Compilation group ID
            
        Returns:
            Dictionary with compiled video information
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🎬 COMPILING MULTIPLE VIDEOS")
        logger.info(f"{'='*60}")
        logger.info(f"Group ID: {group_id}")
        logger.info(f"Source videos: {len(video_paths)}")
        
        try:
            # Step 1: Validate and sort videos
            logger.info(f"📋 Validating and sorting videos...")
            sorted_videos = self._prepare_videos(video_paths)
            logger.info(f"✅ Prepared {len(sorted_videos)} videos for compilation")
            
            # Step 2: Analyze content for coherence
            logger.info(f"🔍 Analyzing content coherence...")
            compilation_plan = self._analyze_compilation_coherence(sorted_videos)
            
            # Step 3: Compile videos with transitions
            logger.info(f"✂️  Compiling videos with transitions...")
            compiled_video = self._compile_videos(sorted_videos, compilation_plan, group_id)
            
            logger.info(f"✅ Compilation complete!")
            logger.info(f"Output: {compiled_video['clip_path']}")
            logger.info(f"Duration: {compiled_video['duration']:.1f}s")
            logger.info(f"{'='*60}\n")
            
            return compiled_video
            
        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _prepare_videos(self, video_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Prepare videos for compilation (validate, sort, get metadata)
        
        Args:
            video_paths: List of video file paths
            
        Returns:
            List of video info dictionaries
        """
        videos = []
        
        for path in video_paths:
            video_path = Path(path)
            if not video_path.exists():
                logger.warning(f"Video not found: {path}")
                continue
            
            # Get video metadata
            duration = self._get_video_duration(str(video_path))
            resolution = self._get_video_resolution(str(video_path))
            creation_time = video_path.stat().st_mtime
            
            videos.append({
                "path": str(video_path),
                "filename": video_path.name,
                "duration": duration,
                "resolution": resolution,
                "creation_time": creation_time
            })
        
        # Sort videos
        if self.auto_sort_by_timestamp:
            videos.sort(key=lambda v: v["creation_time"])
            logger.info("  Sorted by creation timestamp")
        else:
            # Sort alphabetically by filename
            videos.sort(key=lambda v: v["filename"])
            logger.info("  Sorted alphabetically")
        
        # Limit to max videos
        if len(videos) > self.max_source_videos:
            logger.warning(f"Too many videos ({len(videos)}), limiting to {self.max_source_videos}")
            videos = videos[:self.max_source_videos]
        
        return videos
    
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
            logger.error(f"Failed to get duration for {video_path}: {e}")
        return 0
    
    def _get_video_resolution(self, video_path: str) -> str:
        """Get video resolution"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-select_streams', 'v:0', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                streams = data.get('streams', [])
                if streams:
                    width = streams[0].get('width', 0)
                    height = streams[0].get('height', 0)
                    return f"{width}x{height}"
        except Exception as e:
            logger.error(f"Failed to get resolution for {video_path}: {e}")
        return "unknown"
    
    def _analyze_compilation_coherence(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze videos to create compilation plan with coherent flow
        
        Args:
            videos: List of video info dictionaries
            
        Returns:
            Compilation plan with ordering and transition notes
        """
        # Build video summary for AI analysis
        video_summary = "\n".join([
            f"Video {i+1}: {v['filename']} ({v['duration']:.1f}s, {v['resolution']})"
            for i, v in enumerate(videos)
        ])
        
        total_duration = sum(v['duration'] for v in videos)
        
        prompt = f"""Analyze these videos for compilation into a cohesive short video.

VIDEO SET:
{video_summary}

COMPILATION REQUIREMENTS:
- Total current duration: {total_duration:.1f}s
- Target duration: ~{self.target_total_duration}s
- Number of videos: {len(videos)}
- Transition style: {self.transition_style}
- Cross-fade duration: {self.cross_fade_duration}s

TASK:
Create a compilation plan that:
1. Determines if videos should be trimmed to fit target duration
2. Suggests optimal ordering if not chronological
3. Identifies where transitions work best
4. Notes any visual/audio consistency concerns
5. Provides overall coherence strategy

Respond with JSON:
{{
  "keep_original_order": true/false,
  "suggested_order": [0, 1, 2, ...],  // If reordering suggested
  "trim_suggestions": [
    {{"video_index": 0, "trim_start": 0, "trim_end": 10, "reason": "..."}}
  ],
  "transition_notes": [
    {{"between": [0, 1], "style": "crossfade", "note": "..."}}
  ],
  "coherence_strategy": "Brief description of compilation approach",
  "estimated_final_duration": 60
}}"""

        try:
            response = self.deepseek.make_request(prompt)
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                logger.info(f"📋 Compilation strategy: {plan.get('coherence_strategy', '')}")
                return plan
            else:
                logger.warning("Failed to parse AI response, using default plan")
                return self._create_default_plan(videos)
                
        except Exception as e:
            logger.error(f"Compilation analysis error: {e}")
            return self._create_default_plan(videos)
    
    def _create_default_plan(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create default compilation plan"""
        return {
            "keep_original_order": True,
            "suggested_order": list(range(len(videos))),
            "trim_suggestions": [],
            "transition_notes": [
                {"between": [i, i+1], "style": self.transition_style, "note": "Standard transition"}
                for i in range(len(videos) - 1)
            ],
            "coherence_strategy": "Sequential compilation with standard transitions",
            "estimated_final_duration": sum(v['duration'] for v in videos)
        }
    
    def _compile_videos(self, videos: List[Dict[str, Any]], plan: Dict[str, Any],
                        group_id: str) -> Dict[str, Any]:
        """
        Compile videos with transitions and audio mixing
        
        Args:
            videos: List of video info dictionaries
            plan: Compilation plan
            group_id: Compilation group ID
            
        Returns:
            Compiled video information
        """
        # Create temp directory
        temp_dir = self.temp_dir / f"compile_{group_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Reorder if suggested
            if not plan.get("keep_original_order", True):
                suggested_order = plan.get("suggested_order", list(range(len(videos))))
                videos = [videos[i] for i in suggested_order]
            
            # Process each video (apply trims, normalize)
            processed_files = []
            for i, video in enumerate(videos):
                processed_file = temp_dir / f"processed_{i:03d}.mp4"
                
                # Check for trim suggestion
                trim_info = next((t for t in plan.get("trim_suggestions", []) 
                                if t.get("video_index") == i), None)
                
                if trim_info:
                    # Trim video
                    start = trim_info.get("trim_start", 0)
                    end = trim_info.get("trim_end", video["duration"])
                    duration = end - start
                    
                    cmd = [
                        'ffmpeg', '-i', video["path"],
                        '-ss', str(start),
                        '-t', str(duration),
                        '-c:v', 'libx264', '-c:a', 'aac',
                        '-y', str(processed_file)
                    ]
                else:
                    # Just normalize/standardize
                    cmd = [
                        'ffmpeg', '-i', video["path"],
                        '-c:v', 'libx264', '-c:a', 'aac',
                        '-y', str(processed_file)
                    ]
                
                # Add audio normalization if enabled
                if self.audio_normalization:
                    # Use loudnorm filter
                    cmd[cmd.index('-c:a')] = '-af'
                    cmd[cmd.index('aac')] = 'loudnorm'
                    cmd.insert(cmd.index('-y'), '-c:a')
                    cmd.insert(cmd.index('-y'), 'aac')
                
                subprocess.run(cmd, capture_output=True, check=True)
                processed_files.append(processed_file)
                logger.info(f"  ✓ Processed video {i+1}/{len(videos)}")
            
            # Compile with transitions
            output_filename = f"compiled_{group_id}_{int(time.time())}.mp4"
            output_path = self.processed_clips_dir / output_filename
            
            if self.cross_fade_duration > 0:
                # Use xfade filter for crossfade transitions
                output_path = self._compile_with_crossfade(
                    processed_files, output_path, self.cross_fade_duration
                )
            else:
                # Simple concatenation
                output_path = self._compile_simple_concat(processed_files, output_path)
            
            # Get final duration
            final_duration = self._get_video_duration(str(output_path))
            
            return {
                "clip_id": f"compiled_{group_id}",
                "video_id": group_id,
                "clip_path": str(output_path),
                "duration": final_duration,
                "source_count": len(videos),
                "compilation_strategy": plan.get("coherence_strategy", ""),
                "created_at": time.time()
            }
            
        finally:
            # Cleanup temp files
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")
    
    def _compile_with_crossfade(self, video_files: List[Path], 
                                output_path: Path, fade_duration: float) -> Path:
        """Compile videos with crossfade transitions"""
        # For crossfade, we need complex filter graph
        # This is a simplified version - full implementation would handle N videos
        
        if len(video_files) == 1:
            # Single video, just copy
            import shutil
            shutil.copy(video_files[0], output_path)
            return output_path
        
        # For 2+ videos, use progressive xfade
        # Note: Full N-video xfade is complex; this handles 2-3 videos well
        
        if len(video_files) == 2:
            cmd = [
                'ffmpeg',
                '-i', str(video_files[0]),
                '-i', str(video_files[1]),
                '-filter_complex',
                f'[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset={self._get_video_duration(str(video_files[0])) - fade_duration}[v];'
                f'[0:a][1:a]acrossfade=d={fade_duration}[a]',
                '-map', '[v]',
                '-map', '[a]',
                '-c:v', 'libx264', '-c:a', 'aac',
                '-y', str(output_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        else:
            # For 3+ videos, fall back to concat with fade in/out
            self._compile_simple_concat(video_files, output_path)
        
        return output_path
    
    def _compile_simple_concat(self, video_files: List[Path], output_path: Path) -> Path:
        """Simple concatenation of videos"""
        # Create concat file
        concat_file = self.temp_dir / "concat.txt"
        with open(concat_file, 'w') as f:
            for video_file in video_files:
                f.write(f"file '{video_file.absolute()}'\n")
        
        cmd = [
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            '-y', str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

