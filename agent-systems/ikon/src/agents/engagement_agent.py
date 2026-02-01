"""
Engagement Manager for IKON IUL Pipeline
Handles comment classification, low-risk auto-replies, and escalation
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("engagement_manager")


class EngagementManager:
    """Manages engagement on published IUL content"""
    
    def __init__(self, youtube_connection, deepseek_connection):
        """
        Initialize engagement manager
        
        Args:
            youtube_connection: YouTube API connection
            deepseek_connection: DeepSeek AI connection
        """
        self.youtube = youtube_connection
        self.deepseek = deepseek_connection
        
        # Data storage
        project_root = Path(__file__).parent.parent.parent
        self.data_dir = project_root / "data" / "engagement"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.review_queue_file = self.data_dir / "review_queue.json"
        
        logger.info("Engagement manager initialized")
    
    def process_comments(self, video_id: str = None, max_comments: int = 20) -> Dict[str, Any]:
        """
        Process comments on channel videos
        
        Args:
            video_id: Specific video ID, or None for recent videos
            max_comments: Maximum comments to process
            
        Returns:
            Dictionary with processed, replied, escalated counts
        """
        logger.info(f"Processing comments (video_id={video_id}, max={max_comments})")
        
        # Fetch comments
        comments = self._fetch_comments(video_id, max_comments)
        
        if not comments:
            logger.info("No new comments to process")
            return {"processed": 0, "replied": 0, "escalated": 0}
        
        processed = 0
        replied = 0
        escalated = 0
        
        for comment in comments:
            try:
                # Classify comment
                classification = self._classify_comment(comment["text"])
                
                logger.info(f"Comment classified as: {classification['risk_level']}")
                
                if classification["risk_level"] == "low":
                    # Auto-reply
                    if self._auto_reply(comment, classification):
                        replied += 1
                
                elif classification["risk_level"] in ["medium", "high"]:
                    # Escalate for human review
                    self._escalate_comment(comment, classification)
                    escalated += 1
                
                processed += 1
                time.sleep(1)  # Rate limit
                
            except Exception as e:
                logger.error(f"Failed to process comment {comment.get('id')}: {e}")
        
        logger.info(f"✅ Processed {processed} comments (replied: {replied}, escalated: {escalated})")
        
        return {
            "processed": processed,
            "replied": replied,
            "escalated": escalated
        }
    
    def _fetch_comments(self, video_id: str = None, max_count: int = 20) -> List[Dict[str, Any]]:
        """Fetch comments from video(s)"""
        try:
            if video_id:
                # Specific video
                result = self.youtube.perform_action(
                    "get_video_comments",
                    params={"video_id": video_id, "max_results": max_count}
                )
            else:
                # Recent videos (fetch from multiple)
                # For simplicity, get comments from channel
                result = self.youtube.perform_action(
                    "get_recent_comments",
                    params={"max_results": max_count}
                )
            
            if not result or not isinstance(result, list):
                return []
            
            comments = []
            for item in result:
                comments.append({
                    "id": item.get("id", ""),
                    "video_id": item.get("video_id", ""),
                    "author": item.get("author", ""),
                    "text": item.get("text", ""),
                    "published_at": item.get("published_at", "")
                })
            
            return comments
            
        except Exception as e:
            logger.error(f"Failed to fetch comments: {e}")
            return []
    
    def _classify_comment(self, text: str) -> Dict[str, str]:
        """
        Classify comment risk level using AI
        
        Returns:
            {
                "risk_level": "low" | "medium" | "high",
                "intent": str,
                "suggested_response": str
            }
        """
        prompt = f"""You are a compliance expert for IUL education content. Classify this YouTube comment.

COMMENT:
{text}

RISK LEVELS:
- LOW: General questions about concepts ("what is IUL?", "how does cash value work?")
- MEDIUM: Clarifying questions about specific features (requires nuance)
- HIGH: Requests for advice, quotes, guarantees, or personalized recommendations

RULES:
- Never provide individualized financial/insurance advice
- Never quote premiums or guarantee returns
- Educational responses only

Respond in JSON:
{{
  "risk_level": "low|medium|high",
  "intent": "brief description of what user is asking",
  "suggested_response": "safe educational response (if low risk, otherwise empty)"
}}"""

        try:
            response = self.deepseek.generate_text(
                prompt=prompt,
                temperature=0.3,
                max_tokens=400
            )
            
            # Parse JSON
            json_match = None
            if "```json" in response:
                json_match = response.split("```json")[1].split("```")[0].strip()
            elif "{" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_match = response[start:end]
            else:
                json_match = response.strip()
            
            result = json.loads(json_match)
            return result
            
        except Exception as e:
            logger.error(f"Comment classification failed: {e}")
            # Default to high risk on error (safer)
            return {
                "risk_level": "high",
                "intent": "Unknown",
                "suggested_response": ""
            }
    
    def _auto_reply(self, comment: Dict[str, Any], classification: Dict[str, str]) -> bool:
        """Auto-reply to low-risk comment"""
        try:
            suggested = classification.get("suggested_response", "")
            
            if not suggested:
                logger.warning("No suggested response for low-risk comment")
                return False
            
            # Add standard footer
            reply_text = f"""{suggested}

For personalized guidance, see the link in the description to connect with a licensed professional.

(Educational only. Not financial/insurance advice.)"""
            
            # Post reply
            result = self.youtube.perform_action(
                "reply_to_comment",
                params={
                    "comment_id": comment["id"],
                    "text": reply_text
                }
            )
            
            if result:
                logger.info(f"Auto-replied to comment: {comment['id']}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Auto-reply failed: {e}")
            return False
    
    def _escalate_comment(self, comment: Dict[str, Any], classification: Dict[str, str]):
        """Escalate comment to human review queue"""
        try:
            # Load existing queue
            queue = []
            if self.review_queue_file.exists():
                with open(self.review_queue_file, 'r') as f:
                    queue = json.load(f)
            
            # Add to queue
            queue.append({
                "comment_id": comment["id"],
                "video_id": comment["video_id"],
                "author": comment["author"],
                "text": comment["text"],
                "published_at": comment["published_at"],
                "risk_level": classification["risk_level"],
                "intent": classification["intent"],
                "escalated_at": time.time()
            })
            
            # Save queue
            with open(self.review_queue_file, 'w') as f:
                json.dump(queue, f, indent=2)
            
            logger.info(f"Escalated comment: {comment['id']} (risk: {classification['risk_level']})")
            
        except Exception as e:
            logger.error(f"Failed to escalate comment: {e}")
    
    def get_review_queue(self) -> List[Dict[str, Any]]:
        """Get all comments pending human review"""
        if not self.review_queue_file.exists():
            return []
        
        try:
            with open(self.review_queue_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load review queue: {e}")
            return []
    
    def clear_review_queue(self):
        """Clear review queue (after human review)"""
        try:
            if self.review_queue_file.exists():
                self.review_queue_file.unlink()
            logger.info("Review queue cleared")
        except Exception as e:
            logger.error(f"Failed to clear review queue: {e}")
