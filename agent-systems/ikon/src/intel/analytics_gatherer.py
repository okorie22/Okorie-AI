"""
Analytics Gatherer for IKON IUL Pipeline
Collects channel and video analytics with quota-aware sampling and caching
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("analytics_gatherer")


class AnalyticsGatherer:
    """Gathers analytics from own YouTube channel"""
    
    def __init__(self, youtube_connection, config: Dict[str, Any]):
        """
        Initialize analytics gatherer
        
        Args:
            youtube_connection: YouTube API connection
            config: IUL_INTEL_CONFIG from config.py
        """
        self.youtube = youtube_connection
        self.config = config
        
        # Cache settings
        self.cache_ttl = config["gather_cadence"]["analytics"]  # 30 minutes
        
        # Data storage
        project_root = Path(__file__).parent.parent.parent
        self.data_dir = project_root / "data" / "intel"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.history_file = self.data_dir / "analytics_history.jsonl"
        self.cache_file = self.data_dir / "analytics_cache.json"
        
        self._last_fetch_time = 0
        
        logger.info("Analytics gatherer initialized")
    
    def gather(self, force: bool = False) -> Dict[str, Any]:
        """
        Gather analytics data
        
        Args:
            force: Force fresh fetch even if cache is valid
            
        Returns:
            Dictionary with channel_stats, recent_videos, insights
        """
        logger.info("Gathering channel analytics...")
        
        # Check cache
        if not force and self._is_cache_valid():
            logger.info("Using cached analytics")
            return self._load_cache()
        
        try:
            # Fetch channel analytics
            channel_stats = self._fetch_channel_stats()
            
            # Sample recent videos
            recent_videos = self._sample_recent_videos()
            
            # Generate insights
            insights = self._generate_insights(channel_stats, recent_videos)
            
            analytics = {
                "timestamp": time.time(),
                "channel_stats": channel_stats,
                "recent_videos": recent_videos,
                "insights": insights
            }
            
            # Save to history and cache
            self._save_to_history(analytics)
            self._save_cache(analytics)
            
            self._last_fetch_time = time.time()
            
            logger.info(f"✅ Analytics gathered: {len(recent_videos)} videos analyzed")
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to gather analytics: {e}")
            # Return cached data if available
            if self.cache_file.exists():
                logger.info("Returning stale cache due to error")
                return self._load_cache()
            raise
    
    def _fetch_channel_stats(self) -> Dict[str, Any]:
        """Fetch channel-level statistics"""
        try:
            result = self.youtube.perform_action("get_channel_analytics")
            
            if isinstance(result, dict):
                return {
                    "subscriber_count": result.get("subscriber_count", 0),
                    "total_views": result.get("total_views", 0),
                    "video_count": result.get("video_count", 0),
                    "avg_view_duration": result.get("avg_view_duration", 0)
                }
            
            return {
                "subscriber_count": 0,
                "total_views": 0,
                "video_count": 0,
                "avg_view_duration": 0
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch channel stats: {e}")
            return {}
    
    def _sample_recent_videos(self) -> List[Dict[str, Any]]:
        """Sample recent videos for analysis"""
        try:
            sample_size = self.config["quota_limits"]["own_videos_sample"]
            
            # Get recent uploads
            result = self.youtube.perform_action(
                "get_recent_uploads",
                params={"max_results": sample_size}
            )
            
            if not result or not isinstance(result, list):
                logger.warning("No recent videos found")
                return []
            
            videos = []
            for video in result[:sample_size]:
                video_id = video.get("id")
                
                # Get detailed stats
                details = self.youtube.perform_action(
                    "get_video_details",
                    params={"video_id": video_id}
                )
                
                if details:
                    videos.append({
                        "video_id": video_id,
                        "title": details.get("title", ""),
                        "published_at": details.get("published_at", ""),
                        "views": details.get("views", 0),
                        "likes": details.get("likes", 0),
                        "comments": details.get("comments", 0),
                        "duration": details.get("duration", 0),
                        "description": details.get("description", "")[:200]  # First 200 chars
                    })
            
            logger.info(f"Sampled {len(videos)} recent videos")
            return videos
            
        except Exception as e:
            logger.warning(f"Failed to sample videos: {e}")
            return []
    
    def _generate_insights(self, channel_stats: Dict[str, Any], 
                          recent_videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate insights from analytics data"""
        insights = {}
        
        if recent_videos:
            # Calculate averages
            total_views = sum(v.get("views", 0) for v in recent_videos)
            total_likes = sum(v.get("likes", 0) for v in recent_videos)
            total_comments = sum(v.get("comments", 0) for v in recent_videos)
            
            count = len(recent_videos)
            
            insights["avg_views"] = total_views / count if count > 0 else 0
            insights["avg_likes"] = total_likes / count if count > 0 else 0
            insights["avg_comments"] = total_comments / count if count > 0 else 0
            insights["avg_engagement_rate"] = (
                (total_likes + total_comments) / total_views 
                if total_views > 0 else 0
            )
            
            # Find best performer
            if recent_videos:
                best_video = max(recent_videos, key=lambda v: v.get("views", 0))
                insights["best_performer"] = {
                    "video_id": best_video["video_id"],
                    "title": best_video["title"],
                    "views": best_video["views"]
                }
            
            # Extract common keywords from top performers
            top_videos = sorted(recent_videos, key=lambda v: v.get("views", 0), reverse=True)[:3]
            insights["top_video_topics"] = [v["title"] for v in top_videos]
        
        return insights
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if not self.cache_file.exists():
            return False
        
        try:
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
            
            cache_time = cache.get("timestamp", 0)
            age = time.time() - cache_time
            
            return age < self.cache_ttl
            
        except Exception:
            return False
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cached analytics"""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return {}
    
    def _save_cache(self, analytics: Dict[str, Any]):
        """Save analytics to cache"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(analytics, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _save_to_history(self, analytics: Dict[str, Any]):
        """Append analytics to history JSONL"""
        try:
            with open(self.history_file, 'a') as f:
                f.write(json.dumps(analytics) + '\n')
        except Exception as e:
            logger.error(f"Failed to save to history: {e}")
    
    def get_historical_analytics(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Load historical analytics data"""
        cutoff_time = time.time() - (days_back * 24 * 3600)
        analytics_list = []
        
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("timestamp", 0) >= cutoff_time:
                        analytics_list.append(data)
            
            return analytics_list
            
        except Exception as e:
            logger.error(f"Failed to load historical analytics: {e}")
            return []
