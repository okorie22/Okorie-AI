"""
Publishing Agent for ZerePy Content Pipeline
Publishes approved clips to YouTube Shorts and prepares for Instagram
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
import time

logger = logging.getLogger("publishing_agent")


class PublishingAgent:
    """
    Publishes approved content to YouTube Shorts and prepares for Instagram
    """
    
    def __init__(self, pipeline_manager, youtube_connection, deepseek_connection,
                 instagram_folder: Optional[str] = None,
                 auto_publish: bool = True):
        """
        Initialize the Publishing Agent
        
        Args:
            pipeline_manager: ContentPipeline instance
            youtube_connection: YouTube API connection
            deepseek_connection: DeepSeek connection for metadata generation
            instagram_folder: Folder to copy Instagram-ready clips
            auto_publish: Whether to auto-publish to YouTube (True) or just prepare
        """
        self.pipeline_manager = pipeline_manager
        self.youtube = youtube_connection
        self.deepseek = deepseek_connection
        self.auto_publish = auto_publish
        
        # Set up Instagram export folder
        if instagram_folder is None:
            instagram_folder = "data/content_pipeline/instagram_ready"
        self.instagram_folder = Path(instagram_folder)
        self.instagram_folder.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Publishing Agent initialized")
        logger.info(f"  Auto-publish: {auto_publish}")
        logger.info(f"  Instagram folder: {self.instagram_folder}")
    
    def publish_approved_clips(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Publish all approved clips for a video
        
        Args:
            video_id: Pipeline video ID
            
        Returns:
            List of published clip dictionaries
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"🚀 PUBLISHING AGENT - PUBLISHING CLIPS")
            logger.info(f"{'='*60}")
            logger.info(f"Video ID: {video_id}")
            
            # Get approved clips
            clips = self.pipeline_manager.get_clips_for_video(video_id)
            approved_clips = [c for c in clips if c.get('approved') == 1]
            
            if not approved_clips:
                logger.warning("No approved clips found")
                return []
            
            logger.info(f"Found {len(approved_clips)} approved clip(s)")
            
            published = []
            
            for i, clip in enumerate(approved_clips, 1):
                logger.info(f"\n📤 Publishing clip {i}/{len(approved_clips)}")
                logger.info(f"  Clip ID: {clip['clip_id']}")
                
                # Get clip path (prefer edited version)
                clip_path = clip.get('edited_path', clip.get('clip_path'))
                
                if not clip_path or not Path(clip_path).exists():
                    logger.error(f"  ❌ Clip file not found: {clip_path}")
                    continue
                
                # Generate metadata
                metadata = self._generate_metadata(clip)
                
                # Prepare for Instagram (always do this for manual posting)
                instagram_path = self._prepare_for_instagram(clip_path, metadata)
                logger.info(f"  ✅ Instagram ready: {instagram_path}")
                
                # Publish to YouTube if auto_publish is enabled
                if self.auto_publish:
                    youtube_url = self._publish_to_youtube_shorts(clip_path, metadata)
                    
                    if youtube_url:
                        # Mark as published in database
                        self.pipeline_manager.mark_clip_published(
                            clip['clip_id'],
                            youtube_url
                        )
                        
                        clip['youtube_url'] = youtube_url
                        clip['instagram_path'] = instagram_path
                        published.append(clip)
                        
                        logger.info(f"  ✅ Published to YouTube: {youtube_url}")
                    else:
                        logger.error(f"  ❌ YouTube upload failed")
                else:
                    logger.info(f"  ⏸️  Auto-publish disabled - YouTube upload skipped")
                    clip['instagram_path'] = instagram_path
                    published.append(clip)
            
            # Update pipeline state
            if published:
                from src.pipeline_manager import PipelineState
                self.pipeline_manager.update_state(video_id, PipelineState.PUBLISHED)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ PUBLISHING AGENT COMPLETE")
            logger.info(f"Published {len(published)}/{len(approved_clips)} clips")
            if not self.auto_publish:
                logger.info(f"📁 Instagram-ready clips: {self.instagram_folder}")
            logger.info(f"{'='*60}\n")
            
            return published
            
        except Exception as e:
            logger.error(f"Failed to publish clips: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _generate_metadata(self, clip: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate title, description, and tags for a clip using AI
        
        Args:
            clip: Clip dictionary
            
        Returns:
            Dictionary with title, description, tags
        """
        try:
            transcript = clip.get('transcript', '')
            
            prompt = f"""Generate YouTube Shorts metadata for this video clip.

CLIP INFO:
Duration: {clip['duration']:.1f} seconds
Content: {transcript[:500]}

Generate:
1. A catchy title (max 100 characters)
2. A compelling description (2-3 sentences, max 500 characters)
3. 5-10 relevant hashtags

Make it engaging and optimized for YouTube Shorts discovery.

Respond in JSON format:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}"""

            response = self.deepseek.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )
            
            # Parse JSON response
            import json
            response_text = response.strip()
            
            # Extract JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # Find JSON object
            if "{" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                response_text = response_text[json_start:json_end]
            
            metadata = json.loads(response_text)
            
            # Add hashtags to description
            if metadata.get('tags'):
                hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in metadata['tags']])
                metadata['description'] += f"\n\n{hashtags}"
            
            logger.info(f"  Generated title: {metadata['title'][:50]}...")
            return metadata
            
        except Exception as e:
            logger.warning(f"Failed to generate metadata with AI: {e}")
            # Fallback metadata
            return {
                "title": f"Short Clip - {time.strftime('%Y%m%d')}",
                "description": "Check out this short clip!",
                "tags": ["shorts", "video", "content"]
            }
    
    def _publish_to_youtube_shorts(self, video_path: str, metadata: Dict[str, str]) -> Optional[str]:
        """
        Upload video to YouTube as a Short
        
        Args:
            video_path: Path to video file
            metadata: Video metadata (title, description, tags)
            
        Returns:
            YouTube URL if successful, None otherwise
        """
        try:
            logger.info("  Uploading to YouTube...")
            
            # Prepare upload parameters
            title = metadata.get('title', 'Untitled Short')
            description = metadata.get('description', '')
            tags = metadata.get('tags', [])
            
            # Add #Shorts to description if not present
            if '#Shorts' not in description and '#shorts' not in description:
                description += "\n\n#Shorts"
            
            # Call YouTube connection to upload
            # Note: This assumes youtube_connection has an upload_video method
            result = self.youtube.perform_action(
                "upload_video",
                params={
                    "file_path": video_path,
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "category_id": "22",  # People & Blogs
                    "privacy_status": "public"
                }
            )
            
            if result and isinstance(result, dict):
                video_id = result.get('id')
                if video_id:
                    youtube_url = f"https://youtube.com/shorts/{video_id}"
                    return youtube_url
            
            logger.error("  YouTube upload returned no video ID")
            return None
            
        except Exception as e:
            logger.error(f"  Failed to upload to YouTube: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _prepare_for_instagram(self, video_path: str, metadata: Dict[str, str]) -> str:
        """
        Copy video to Instagram-ready folder for manual posting
        
        Args:
            video_path: Path to video file
            metadata: Video metadata
            
        Returns:
            Path to Instagram-ready file
        """
        try:
            # Generate safe filename from title
            title = metadata.get('title', 'clip')
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')[:50]
            
            # Create output path
            timestamp = int(time.time())
            output_path = self.instagram_folder / f"{safe_title}_{timestamp}.mp4"
            
            # Copy file
            shutil.copy2(video_path, output_path)
            
            # Also save metadata as text file
            metadata_path = output_path.with_suffix('.txt')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                f.write(f"TITLE:\n{metadata.get('title', '')}\n\n")
                f.write(f"DESCRIPTION:\n{metadata.get('description', '')}\n\n")
                f.write(f"TAGS:\n{', '.join(metadata.get('tags', []))}\n")
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to prepare for Instagram: {e}")
            return ""
    
    def get_published_clips(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get clips published in the last N days
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of published clip dictionaries
        """
        try:
            # This would query the database for published clips
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Failed to get published clips: {e}")
            return []

