"""
Remotion Renderer Bridge for IKON IUL Pipeline
Python wrapper for Remotion CLI video generation
"""

import os
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("remotion_renderer")


class RemotionRenderer:
    """Bridge between Python pipeline and Remotion video renderer"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Remotion renderer
        
        Args:
            config: Remotion configuration from agent config
        """
        self.config = config
        self.project_dir = Path(config.get("project_dir", "remotion"))
        self.composition = config.get("composition", "IULShortV1")
        self.fps = config.get("fps", 30)
        self.width = config.get("width", 1080)
        self.height = config.get("height", 1920)
        self.duration_frames = config.get("duration_frames", 900)
        
        # Output settings
        project_root = Path(__file__).parent.parent.parent
        self.output_dir = project_root / "data" / "rendered"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate project exists
        if not self.project_dir.exists():
            logger.error(f"Remotion project not found at {self.project_dir}")
            logger.info("Run 'npm install' in the remotion directory first")
        
        logger.info(f"Remotion renderer initialized: {self.composition} ({self.width}x{self.height}@{self.fps}fps)")
    
    def render_video(self, idea_id: str, props: Dict[str, Any], audio_path: str) -> Dict[str, Any]:
        """
        Render video using Remotion
        
        Args:
            idea_id: Unique idea identifier
            props: Props for Remotion composition (hook, bulletPoints, cta, disclaimer)
            audio_path: Path to audio file
            
        Returns:
            {
                "video_path": str,
                "thumbnail_path": str,
                "duration": float,
                "render_time": float,
                "success": bool
            }
        """
        logger.info(f"Rendering video for idea: {idea_id}")
        start_time = time.time()
        
        try:
            # Validate props
            validation_errors = self._validate_props(props)
            if validation_errors:
                raise ValueError(f"Invalid props: {', '.join(validation_errors)}")
            
            # Add audio path to props
            props_with_audio = props.copy()
            props_with_audio["audioPath"] = str(Path(audio_path).absolute())
            
            # Write props to temp file
            props_file = self._write_props_file(props_with_audio)
            
            # Generate output paths
            video_filename = f"{idea_id}_{int(time.time())}.mp4"
            video_path = self.output_dir / video_filename
            
            # Build Remotion render command
            cmd = self._build_render_command(props_file, video_path)
            
            # Execute render
            logger.info(f"Executing Remotion render: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=str(self.project_dir.absolute()),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Check result
            if result.returncode != 0:
                logger.error(f"Remotion render failed (exit code {result.returncode})")
                logger.error(f"STDERR: {result.stderr}")
                raise Exception(f"Render failed: {result.stderr}")
            
            # Verify output file exists
            if not video_path.exists():
                raise FileNotFoundError(f"Render completed but output file not found: {video_path}")
            
            # Generate thumbnail
            thumbnail_path = self._generate_thumbnail(video_path)
            
            # Calculate metrics
            render_time = time.time() - start_time
            duration = self.duration_frames / self.fps
            
            # Cleanup props file
            props_file.unlink(missing_ok=True)
            
            logger.info(f"✅ Video rendered successfully: {video_path} ({render_time:.1f}s)")
            
            return {
                "video_path": str(video_path),
                "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
                "duration": duration,
                "render_time": render_time,
                "success": True,
                "composition": self.composition,
                "resolution": f"{self.width}x{self.height}"
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Remotion render timed out (5 minutes)")
            return {
                "success": False,
                "error": "Render timeout",
                "render_time": time.time() - start_time
            }
        except Exception as e:
            logger.error(f"Remotion render failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "render_time": time.time() - start_time
            }
    
    def _validate_props(self, props: Dict[str, Any]) -> List[str]:
        """Validate required props are present"""
        errors = []
        
        required_fields = ["hook", "bulletPoints", "cta", "disclaimer"]
        for field in required_fields:
            if field not in props:
                errors.append(f"Missing required field: {field}")
        
        # Validate bullet points
        if "bulletPoints" in props:
            if not isinstance(props["bulletPoints"], list):
                errors.append("bulletPoints must be a list")
            elif len(props["bulletPoints"]) < 2 or len(props["bulletPoints"]) > 4:
                errors.append("bulletPoints must contain 2-4 items")
        
        return errors
    
    def _write_props_file(self, props: Dict[str, Any]) -> Path:
        """Write props to temporary JSON file"""
        props_file = Path(tempfile.mktemp(suffix=".json", prefix="remotion_props_"))
        
        with open(props_file, 'w', encoding='utf-8') as f:
            json.dump(props, f, indent=2)
        
        logger.debug(f"Props written to: {props_file}")
        return props_file
    
    def _build_render_command(self, props_file: Path, output_path: Path) -> List[str]:
        """Build Remotion CLI render command"""
        cmd = [
            "npx",
            "remotion",
            "render",
            self.composition,
            str(output_path),
            "--props", str(props_file.absolute()),
            "--overwrite"
        ]
        
        return cmd
    
    def _generate_thumbnail(self, video_path: Path) -> Optional[Path]:
        """Generate thumbnail from video (middle frame)"""
        try:
            thumbnail_path = video_path.with_suffix('.jpg')
            
            # Use ffmpeg to extract middle frame
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-ss", "15",  # 15 seconds in (middle of 30s video)
                "-vframes", "1",
                "-y",
                str(thumbnail_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and thumbnail_path.exists():
                logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
                return thumbnail_path
            else:
                logger.warning("Failed to generate thumbnail")
                return None
                
        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {e}")
            return None
    
    def validate_environment(self) -> Dict[str, bool]:
        """
        Validate that all required tools are available
        
        Returns:
            Dictionary of checks and their status
        """
        checks = {}
        
        # Check Node.js
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            checks["node"] = result.returncode == 0
            if checks["node"]:
                logger.info(f"Node.js found: {result.stdout.strip()}")
        except Exception:
            checks["node"] = False
            logger.error("Node.js not found")
        
        # Check npm
        try:
            result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            checks["npm"] = result.returncode == 0
            if checks["npm"]:
                logger.info(f"npm found: {result.stdout.strip()}")
        except Exception:
            checks["npm"] = False
            logger.error("npm not found")
        
        # Check Remotion project
        checks["remotion_project"] = self.project_dir.exists()
        if not checks["remotion_project"]:
            logger.error(f"Remotion project not found at {self.project_dir}")
        
        # Check package.json
        package_json = self.project_dir / "package.json"
        checks["package_json"] = package_json.exists()
        if not checks["package_json"]:
            logger.error("package.json not found in Remotion project")
        
        # Check node_modules
        node_modules = self.project_dir / "node_modules"
        checks["dependencies_installed"] = node_modules.exists()
        if not checks["dependencies_installed"]:
            logger.warning("Dependencies not installed - run 'npm install' in remotion directory")
        
        # Check ffmpeg
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            checks["ffmpeg"] = result.returncode == 0
            if checks["ffmpeg"]:
                logger.info("ffmpeg found")
        except Exception:
            checks["ffmpeg"] = False
            logger.error("ffmpeg not found (required for thumbnail generation)")
        
        # Summary
        all_critical = checks.get("node") and checks.get("npm") and checks.get("remotion_project")
        checks["ready"] = all_critical
        
        if checks["ready"]:
            logger.info("✅ Remotion environment validated")
        else:
            logger.warning("⚠️ Remotion environment incomplete - see errors above")
        
        return checks


import time  # Add missing import
