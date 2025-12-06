"""
Gallery Agent for ZerePy Content Pipeline
Monitors cloud folder for new videos and triggers the content pipeline
"""

import time
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
import json

logger = logging.getLogger("gallery_agent")


class VideoFileHandler(FileSystemEventHandler):
    """Handler for new video file events"""
    
    def __init__(self, agent: 'GalleryAgent'):
        self.agent = agent
        self.processed_files = set()  # Track processed files to avoid duplicates
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Check if it's a video file
        if file_path.suffix.lower() in self.agent.file_patterns:
            # Avoid processing the same file multiple times
            if str(file_path) not in self.processed_files:
                self.processed_files.add(str(file_path))
                logger.info(f"📹 New video detected: {file_path.name}")
                self.agent.process_new_video(file_path)


class GalleryAgent:
    """
    Monitors cloud folder for new videos and triggers content pipeline
    """
    
    def __init__(
        self,
        cloud_folder_path: str,
        pipeline_manager,
        file_patterns: Optional[List[str]] = None,
        processing_folder: Optional[str] = None,
        check_interval: int = 60,
        callback: Optional[Callable] = None
    ):
        """
        Initialize the Gallery Agent
        
        Args:
            cloud_folder_path: Path to cloud-synced folder to monitor
            pipeline_manager: ContentPipeline instance
            file_patterns: List of file extensions to monitor (e.g., ['.mp4', '.mov'])
            processing_folder: Folder to copy videos to for processing
            check_interval: Seconds between folder checks (for polling fallback)
            callback: Optional callback function when new video is detected
        """
        self.cloud_folder_path = Path(cloud_folder_path)
        self.pipeline_manager = pipeline_manager
        self.file_patterns = file_patterns or ['.mp4', '.mov', '.avi', '.mkv']
        self.check_interval = check_interval
        self.callback = callback
        
        # Set up processing folder
        if processing_folder is None:
            processing_folder = "data/content_pipeline/raw_videos"
        self.processing_folder = Path(processing_folder)
        self.processing_folder.mkdir(parents=True, exist_ok=True)
        
        # Validate cloud folder exists
        if not self.cloud_folder_path.exists():
            logger.warning(f"Cloud folder does not exist: {self.cloud_folder_path}")
            logger.info("Creating folder and waiting for it to sync...")
            self.cloud_folder_path.mkdir(parents=True, exist_ok=True)
        
        # File system observer for real-time monitoring
        self.observer = None
        self.is_monitoring = False
        
        # Track processed videos
        self.processed_videos_file = Path("data/content_pipeline/processed_videos.json")
        self.processed_videos = self._load_processed_videos()
        
        logger.info(f"Gallery Agent initialized")
        logger.info(f"  Monitoring: {self.cloud_folder_path}")
        logger.info(f"  Processing folder: {self.processing_folder}")
        logger.info(f"  File patterns: {self.file_patterns}")
    
    def _load_processed_videos(self) -> Dict[str, float]:
        """Load list of already processed videos"""
        if self.processed_videos_file.exists():
            try:
                with open(self.processed_videos_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load processed videos list: {e}")
        return {}
    
    def _save_processed_videos(self):
        """Save list of processed videos"""
        try:
            self.processed_videos_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.processed_videos_file, 'w') as f:
                json.dump(self.processed_videos, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save processed videos list: {e}")
    
    def start_monitoring(self):
        """Start monitoring the cloud folder for new videos"""
        if self.is_monitoring:
            logger.warning("Already monitoring")
            return
        
        logger.info("🔍 Starting real-time video monitoring...")
        
        # Set up file system observer
        event_handler = VideoFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.cloud_folder_path), recursive=False)
        self.observer.start()
        
        self.is_monitoring = True
        logger.info(f"✅ Monitoring started: {self.cloud_folder_path}")
        
        # Also check for existing files that weren't processed yet
        self._check_existing_files()
    
    def stop_monitoring(self):
        """Stop monitoring the cloud folder"""
        if not self.is_monitoring:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        self.is_monitoring = False
        logger.info("🛑 Monitoring stopped")
    
    def _check_existing_files(self):
        """Check for existing video files in the folder"""
        logger.info("Checking for existing unprocessed videos...")
        
        found_count = 0
        for pattern in self.file_patterns:
            for video_file in self.cloud_folder_path.glob(f"*{pattern}"):
                if video_file.is_file():
                    file_key = str(video_file.absolute())
                    
                    # Check if already processed
                    if file_key not in self.processed_videos:
                        logger.info(f"📹 Found existing video: {video_file.name}")
                        self.process_new_video(video_file)
                        found_count += 1
        
        if found_count == 0:
            logger.info("No unprocessed videos found")
        else:
            logger.info(f"Processed {found_count} existing video(s)")
    
    def process_new_video(self, video_path: Path):
        """
        Process a newly detected video file
        
        Args:
            video_path: Path to the video file
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"🎬 PROCESSING NEW VIDEO")
            logger.info(f"{'='*60}")
            logger.info(f"File: {video_path.name}")
            logger.info(f"Size: {video_path.stat().st_size / (1024*1024):.1f} MB")
            
            # Wait a bit to ensure file is fully written (cloud sync)
            time.sleep(2)
            
            # Copy to processing folder
            dest_path = self.processing_folder / video_path.name
            
            # Avoid overwriting if file already exists
            if dest_path.exists():
                timestamp = int(time.time())
                stem = video_path.stem
                suffix = video_path.suffix
                dest_path = self.processing_folder / f"{stem}_{timestamp}{suffix}"
            
            logger.info(f"📂 Copying to processing folder...")
            shutil.copy2(video_path, dest_path)
            logger.info(f"✅ Copied to: {dest_path}")
            
            # Extract metadata
            metadata = self._extract_metadata(dest_path)
            
            # Trigger pipeline
            logger.info(f"🚀 Triggering content pipeline...")
            video_id = self.pipeline_manager.trigger_pipeline(
                video_path=str(dest_path),
                metadata=metadata
            )
            
            # Mark as processed
            file_key = str(video_path.absolute())
            self.processed_videos[file_key] = time.time()
            self._save_processed_videos()
            
            # Call callback if provided
            if self.callback:
                try:
                    self.callback(video_id, dest_path, metadata)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            logger.info(f"✅ Pipeline triggered successfully!")
            logger.info(f"Video ID: {video_id}")
            logger.info(f"{'='*60}\n")
            
        except Exception as e:
            logger.error(f"Failed to process video {video_path.name}: {e}")
            import traceback
            traceback.print_exc()
    
    def _extract_metadata(self, video_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from video file
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with metadata
        """
        try:
            import subprocess
            
            # Use ffprobe to get video information
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                
                # Extract relevant metadata
                metadata = {
                    "filename": video_path.name,
                    "size_bytes": video_path.stat().st_size,
                    "size_mb": round(video_path.stat().st_size / (1024*1024), 2)
                }
                
                # Get format information
                if 'format' in info:
                    format_info = info['format']
                    metadata["duration"] = float(format_info.get('duration', 0))
                    metadata["format_name"] = format_info.get('format_name', 'unknown')
                    metadata["bit_rate"] = int(format_info.get('bit_rate', 0))
                
                # Get video stream information
                for stream in info.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        metadata["width"] = stream.get('width', 0)
                        metadata["height"] = stream.get('height', 0)
                        metadata["codec"] = stream.get('codec_name', 'unknown')
                        metadata["fps"] = eval(stream.get('r_frame_rate', '0/1'))
                        
                        # Determine recording type based on aspect ratio
                        if metadata.get("width") and metadata.get("height"):
                            aspect_ratio = metadata["width"] / metadata["height"]
                            if 0.5 <= aspect_ratio <= 0.6:
                                metadata["recording_type"] = "vertical"  # Phone selfie/vertical
                            elif aspect_ratio > 1.5:
                                metadata["recording_type"] = "horizontal"  # Landscape
                            else:
                                metadata["recording_type"] = "square"
                        break
                
                return metadata
                
        except subprocess.TimeoutExpired:
            logger.warning(f"ffprobe timeout for {video_path.name}")
        except FileNotFoundError:
            logger.warning("ffprobe not found - install ffmpeg for metadata extraction")
        except Exception as e:
            logger.warning(f"Failed to extract metadata: {e}")
        
        # Return basic metadata if ffprobe fails
        return {
            "filename": video_path.name,
            "size_bytes": video_path.stat().st_size,
            "size_mb": round(video_path.stat().st_size / (1024*1024), 2)
        }
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "is_monitoring": self.is_monitoring,
            "cloud_folder": str(self.cloud_folder_path),
            "processing_folder": str(self.processing_folder),
            "file_patterns": self.file_patterns,
            "processed_count": len(self.processed_videos)
        }
    
    def cleanup_old_entries(self, days: int = 30):
        """
        Clean up old entries from processed videos list
        
        Args:
            days: Age threshold in days
        """
        cutoff_time = time.time() - (days * 24 * 3600)
        
        old_count = len(self.processed_videos)
        self.processed_videos = {
            k: v for k, v in self.processed_videos.items()
            if v > cutoff_time
        }
        
        removed = old_count - len(self.processed_videos)
        if removed > 0:
            self._save_processed_videos()
            logger.info(f"🗑️ Cleaned up {removed} old processed video entries")

