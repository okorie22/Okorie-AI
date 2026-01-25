"""
Competitor Analyzer for IKON IUL Pipeline
Monitors competitor channels from config and detects trending topics
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List
from collections import Counter
import re

logger = logging.getLogger("competitor_analyzer")


class CompetitorAnalyzer:
    """Analyzes competitor channels for trending topics and strategies"""
    
    def __init__(self, youtube_connection, config: Dict[str, Any]):
        """
        Initialize competitor analyzer
        
        Args:
            youtube_connection: YouTube API connection
            config: IUL_INTEL_CONFIG from config.py
        """
        self.youtube = youtube_connection
        self.config = config
        self.competitors = config["competitors"]
        
        # Cache settings
        self.cache_ttl = config["gather_cadence"]["competitors"]  # 6 hours
        
        # Data storage
        project_root = Path(__file__).parent.parent.parent
        self.data_dir = project_root / "data" / "intel"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.snapshots_file = self.data_dir / "competitor_snapshots.jsonl"
        
        logger.info(f"Competitor analyzer initialized ({len(self.competitors)} competitors)")
    
    def analyze(self) -> Dict[str, Any]:
        """
        Analyze competitor channels
        
        Returns:
            Dictionary with competitor_data, trending_topics, insights
        """
        logger.info("Analyzing competitor channels...")
        
        competitor_data = []
        
        for competitor in self.competitors:
            channel_id = competitor["channel_id"]
            label = competitor["label"]
            
            logger.info(f"Analyzing: {label}")
            
            try:
                data = self._analyze_competitor(channel_id, label)
                competitor_data.append(data)
                time.sleep(1)  # Rate limit
            except Exception as e:
                logger.error(f"Failed to analyze {label}: {e}")
        
        # Detect trending topics across competitors
        trending_topics = self._detect_trending_topics(competitor_data)
        
        # Generate insights
        insights = self._generate_insights(competitor_data, trending_topics)
        
        result = {
            "timestamp": time.time(),
            "competitor_data": competitor_data,
            "trending_topics": trending_topics,
            "insights": insights
        }
        
        # Save snapshot
        self._save_snapshot(result)
        
        logger.info(f"✅ Analyzed {len(competitor_data)} competitors, found {len(trending_topics)} trending topics")
        return result
    
    def _analyze_competitor(self, channel_id: str, label: str) -> Dict[str, Any]:
        """Analyze a single competitor channel"""
        videos_per_check = self.config["quota_limits"]["competitor_videos_per_check"]
        
        # Fetch recent uploads
        recent_videos = []
        
        try:
            # Use channel RSS feed (no quota) or API
            result = self.youtube.perform_action(
                "get_channel_uploads",
                params={"channel_id": channel_id, "max_results": videos_per_check}
            )
            
            if result and isinstance(result, list):
                for video in result[:videos_per_check]:
                    video_id = video.get("id")
                    
                    recent_videos.append({
                        "video_id": video_id,
                        "title": video.get("title", ""),
                        "published_at": video.get("published_at", ""),
                        "views": video.get("views", 0),
                        "description": video.get("description", "")[:300]
                    })
        except Exception as e:
            logger.warning(f"Failed to fetch videos for {label}: {e}")
        
        # Extract patterns
        title_keywords = self._extract_keywords([v["title"] for v in recent_videos])
        desc_keywords = self._extract_keywords([v["description"] for v in recent_videos])
        
        # Calculate publish cadence
        if len(recent_videos) >= 2:
            first_time = self._parse_time(recent_videos[0]["published_at"])
            last_time = self._parse_time(recent_videos[-1]["published_at"])
            time_span_days = (first_time - last_time) / 86400 if first_time and last_time else 0
            cadence = len(recent_videos) / max(time_span_days, 1) if time_span_days > 0 else 0
        else:
            cadence = 0
        
        return {
            "channel_id": channel_id,
            "label": label,
            "video_count": len(recent_videos),
            "recent_videos": recent_videos,
            "title_keywords": title_keywords[:10],  # Top 10
            "desc_keywords": desc_keywords[:10],
            "publish_cadence_per_day": round(cadence, 2)
        }
    
    def _extract_keywords(self, texts: List[str]) -> List[tuple]:
        """Extract and rank keywords from texts"""
        # Combine all texts
        combined = " ".join(texts).lower()
        
        # Remove common stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", 
                     "of", "with", "is", "are", "was", "be", "by", "this", "that", "it"}
        
        # Extract words (alphanumeric only, 3+ chars)
        words = re.findall(r'\b[a-z0-9]{3,}\b', combined)
        words = [w for w in words if w not in stop_words]
        
        # Count frequency
        counter = Counter(words)
        
        # Return top keywords with counts
        return counter.most_common(20)
    
    def _detect_trending_topics(self, competitor_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect trending topics across all competitors"""
        all_keywords = []
        
        for comp in competitor_data:
            all_keywords.extend([kw[0] for kw in comp.get("title_keywords", [])])
        
        # Count occurrences across competitors
        counter = Counter(all_keywords)
        
        # Filter to keywords appearing in multiple competitors
        trending = []
        for keyword, count in counter.most_common(15):
            if count >= 2:  # Appears in at least 2 competitors
                trending.append({
                    "keyword": keyword,
                    "frequency": count,
                    "trending_score": count * 10  # Simple scoring
                })
        
        return trending
    
    def _generate_insights(self, competitor_data: List[Dict[str, Any]], 
                          trending_topics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate actionable insights"""
        insights = {}
        
        # Average publish cadence
        cadences = [c["publish_cadence_per_day"] for c in competitor_data if c["publish_cadence_per_day"] > 0]
        insights["avg_competitor_cadence"] = round(sum(cadences) / len(cadences), 2) if cadences else 0
        
        # Most active competitor
        if competitor_data:
            most_active = max(competitor_data, key=lambda c: c["publish_cadence_per_day"])
            insights["most_active_competitor"] = {
                "label": most_active["label"],
                "cadence": most_active["publish_cadence_per_day"]
            }
        
        # Top trending topic
        if trending_topics:
            insights["hottest_topic"] = trending_topics[0]["keyword"]
        
        return insights
    
    def _parse_time(self, time_str: str) -> Optional[float]:
        """Parse ISO time string to timestamp"""
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return dt.timestamp()
        except Exception:
            return None
    
    def _save_snapshot(self, data: Dict[str, Any]):
        """Save competitor snapshot to JSONL"""
        try:
            with open(self.snapshots_file, 'a') as f:
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
    
    def get_historical_snapshots(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Load historical competitor snapshots"""
        cutoff_time = time.time() - (days_back * 24 * 3600)
        snapshots = []
        
        if not self.snapshots_file.exists():
            return []
        
        try:
            with open(self.snapshots_file, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("timestamp", 0) >= cutoff_time:
                        snapshots.append(data)
            return snapshots
        except Exception as e:
            logger.error(f"Failed to load snapshots: {e}")
            return []
