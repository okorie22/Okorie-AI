"""
Ideas Manager for IKON IUL Pipeline
Handles idea storage, status tracking, and deduplication using JSONL format
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger("ideas_manager")


class IdeaStatus(Enum):
    """Status of an idea in the pipeline"""
    READY = "ready"           # Ready to be queued
    QUEUED = "queued"         # Queued in Redis
    SCRIPTING = "scripting"   # Being expanded into script
    COMPLIANCE = "compliance" # In compliance check
    TTS = "tts"               # Generating audio
    RENDERING = "rendering"   # Rendering video
    POST_CHECK = "post_check" # Post-render check
    PUBLISHING = "publishing" # Being published
    PUBLISHED = "published"   # Successfully published
    REJECTED = "rejected"     # Failed compliance/quality checks
    ERROR = "error"           # Technical error occurred


@dataclass
class IdeaSchema:
    """Schema for IUL education ideas"""
    idea_id: str
    created_at: float
    topic: str
    hook: str
    bullet_points: List[str]
    script: str
    script_final: Optional[str]  # After 2nd draft (if needed)
    cta: str
    disclaimer: str
    keywords: List[str]
    
    # Scoring
    scores: Dict[str, float]  # hook_score, topic_fit_score, compliance_risk
    
    # Status tracking
    status: str
    dedupe_key: str
    
    # Pipeline metadata
    compliance_result: Optional[Dict[str, Any]] = None
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    published_at: Optional[float] = None
    
    # Analytics (populated post-publish)
    analytics: Optional[Dict[str, Any]] = None
    
    # Error tracking
    error_history: Optional[List[Dict[str, Any]]] = None
    
    def __post_init__(self):
        if self.error_history is None:
            self.error_history = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IdeaSchema':
        """Create IdeaSchema from dictionary"""
        # Handle list fields that might be None
        if 'bullet_points' in data and data['bullet_points'] is None:
            data['bullet_points'] = []
        if 'keywords' in data and data['keywords'] is None:
            data['keywords'] = []
        if 'error_history' in data and data['error_history'] is None:
            data['error_history'] = []
        return cls(**data)
    
    def to_jsonl(self) -> str:
        """Convert to JSONL line"""
        return json.dumps(self.to_dict())
    
    def update_status(self, new_status: IdeaStatus, error: str = None):
        """Update status and optionally log error"""
        self.status = new_status.value
        if error:
            self.error_history.append({
                "status": new_status.value,
                "error": error,
                "timestamp": time.time()
            })


class IdeasManager:
    """Manager for IUL education ideas storage and retrieval"""
    
    def __init__(self, ideas_file: Path = None):
        """
        Initialize ideas manager
        
        Args:
            ideas_file: Path to ideas JSONL file
        """
        if ideas_file is None:
            # Default location
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            ideas_dir = project_root / "data" / "ideas"
            ideas_dir.mkdir(parents=True, exist_ok=True)
            ideas_file = ideas_dir / "ideas.jsonl"
        
        self.ideas_file = Path(ideas_file)
        self.ideas_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create file if it doesn't exist
        if not self.ideas_file.exists():
            self.ideas_file.touch()
            logger.info(f"Created ideas file: {self.ideas_file}")
        
        logger.info(f"Ideas manager initialized with file: {self.ideas_file}")
    
    def save_idea(self, idea: IdeaSchema) -> bool:
        """
        Save idea to JSONL file (append)
        
        Args:
            idea: IdeaSchema instance
            
        Returns:
            True if successful
        """
        try:
            with open(self.ideas_file, 'a', encoding='utf-8') as f:
                f.write(idea.to_jsonl() + '\n')
            logger.debug(f"Saved idea {idea.idea_id} to {self.ideas_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save idea {idea.idea_id}: {e}")
            return False
    
    def load_all_ideas(self) -> List[IdeaSchema]:
        """
        Load all ideas from JSONL file
        
        Returns:
            List of IdeaSchema instances
        """
        ideas = []
        
        try:
            with open(self.ideas_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        idea_dict = json.loads(line)
                        idea = IdeaSchema.from_dict(idea_dict)
                        ideas.append(idea)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping malformed line {line_num}: {e}")
                    except Exception as e:
                        logger.warning(f"Error loading idea on line {line_num}: {e}")
            
            logger.debug(f"Loaded {len(ideas)} ideas from {self.ideas_file}")
            return ideas
            
        except FileNotFoundError:
            logger.warning(f"Ideas file not found: {self.ideas_file}")
            return []
        except Exception as e:
            logger.error(f"Error loading ideas: {e}")
            return []
    
    def get_idea_by_id(self, idea_id: str) -> Optional[IdeaSchema]:
        """
        Get idea by ID
        
        Args:
            idea_id: Idea identifier
            
        Returns:
            IdeaSchema if found, None otherwise
        """
        ideas = self.load_all_ideas()
        for idea in ideas:
            if idea.idea_id == idea_id:
                return idea
        return None
    
    def get_ideas_by_status(self, status: IdeaStatus) -> List[IdeaSchema]:
        """
        Get ideas by status
        
        Args:
            status: IdeaStatus enum value
            
        Returns:
            List of matching ideas
        """
        ideas = self.load_all_ideas()
        return [idea for idea in ideas if idea.status == status.value]
    
    def get_ideas_by_score_range(self, min_score: float, max_score: float, 
                                   score_key: str = "hook_score") -> List[IdeaSchema]:
        """
        Get ideas within a score range
        
        Args:
            min_score: Minimum score (0-100)
            max_score: Maximum score (0-100)
            score_key: Score field name
            
        Returns:
            List of matching ideas
        """
        ideas = self.load_all_ideas()
        matching = []
        
        for idea in ideas:
            if score_key in idea.scores:
                score = idea.scores[score_key]
                if min_score <= score <= max_score:
                    matching.append(idea)
        
        return matching
    
    def check_dedupe_key_exists(self, dedupe_key: str) -> bool:
        """
        Check if dedupe key already exists
        
        Args:
            dedupe_key: Deduplication key
            
        Returns:
            True if exists
        """
        ideas = self.load_all_ideas()
        for idea in ideas:
            if idea.dedupe_key == dedupe_key:
                return True
        return False
    
    def update_idea_status(self, idea_id: str, new_status: IdeaStatus, 
                           error: str = None, **updates) -> bool:
        """
        Update idea status and optionally other fields
        
        Args:
            idea_id: Idea identifier
            new_status: New IdeaStatus
            error: Optional error message
            **updates: Additional fields to update
            
        Returns:
            True if successful
        """
        ideas = self.load_all_ideas()
        updated = False
        
        for idea in ideas:
            if idea.idea_id == idea_id:
                idea.update_status(new_status, error)
                
                # Apply additional updates
                for key, value in updates.items():
                    if hasattr(idea, key):
                        setattr(idea, key, value)
                
                updated = True
                break
        
        if updated:
            # Rewrite entire file (atomic operation)
            return self._rewrite_ideas_file(ideas)
        else:
            logger.warning(f"Idea {idea_id} not found for status update")
            return False
    
    def _rewrite_ideas_file(self, ideas: List[IdeaSchema]) -> bool:
        """
        Rewrite entire ideas file (for updates)
        
        Args:
            ideas: List of all ideas
            
        Returns:
            True if successful
        """
        try:
            # Write to temp file first (atomic)
            temp_file = self.ideas_file.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                for idea in ideas:
                    f.write(idea.to_jsonl() + '\n')
            
            # Replace original file
            temp_file.replace(self.ideas_file)
            logger.debug(f"Rewrote ideas file with {len(ideas)} ideas")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rewrite ideas file: {e}")
            return False
    
    def get_ready_ideas(self, min_hook_score: float = 75, 
                        max_compliance_risk: float = 20) -> List[IdeaSchema]:
        """
        Get ideas ready to be queued to pipeline
        
        Args:
            min_hook_score: Minimum hook score threshold
            max_compliance_risk: Maximum compliance risk threshold
            
        Returns:
            List of ready ideas
        """
        ideas = self.get_ideas_by_status(IdeaStatus.READY)
        
        qualified = []
        for idea in ideas:
            hook_score = idea.scores.get("hook_score", 0)
            compliance_risk = idea.scores.get("compliance_risk", 100)
            
            if hook_score >= min_hook_score and compliance_risk <= max_compliance_risk:
                qualified.append(idea)
        
        # Sort by hook score descending
        qualified.sort(key=lambda x: x.scores.get("hook_score", 0), reverse=True)
        
        return qualified
    
    def get_published_ideas(self, days_back: int = None) -> List[IdeaSchema]:
        """
        Get published ideas, optionally filtered by recency
        
        Args:
            days_back: Only include ideas published within this many days
            
        Returns:
            List of published ideas
        """
        ideas = self.get_ideas_by_status(IdeaStatus.PUBLISHED)
        
        if days_back:
            cutoff_time = time.time() - (days_back * 24 * 3600)
            ideas = [idea for idea in ideas 
                    if idea.published_at and idea.published_at >= cutoff_time]
        
        # Sort by published date descending
        ideas.sort(key=lambda x: x.published_at or 0, reverse=True)
        
        return ideas
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about ideas
        
        Returns:
            Dictionary of status counts
        """
        ideas = self.load_all_ideas()
        
        stats = {
            "total": len(ideas),
            "by_status": {}
        }
        
        # Count by status
        for status in IdeaStatus:
            count = len([idea for idea in ideas if idea.status == status.value])
            stats["by_status"][status.value] = count
        
        return stats
    
    def cleanup_old_ideas(self, days: int = 90, keep_published: bool = True) -> int:
        """
        Clean up old ideas to prevent file bloat
        
        Args:
            days: Remove ideas older than this many days
            keep_published: Don't remove published ideas regardless of age
            
        Returns:
            Number of ideas removed
        """
        cutoff_time = time.time() - (days * 24 * 3600)
        ideas = self.load_all_ideas()
        
        kept_ideas = []
        removed_count = 0
        
        for idea in ideas:
            # Keep if recent
            if idea.created_at >= cutoff_time:
                kept_ideas.append(idea)
                continue
            
            # Keep if published and flag is set
            if keep_published and idea.status == IdeaStatus.PUBLISHED.value:
                kept_ideas.append(idea)
                continue
            
            # Otherwise remove
            removed_count += 1
        
        if removed_count > 0:
            self._rewrite_ideas_file(kept_ideas)
            logger.info(f"Cleaned up {removed_count} old ideas (kept {len(kept_ideas)})")
        
        return removed_count


def create_idea(idea_id: str, topic: str, hook: str, bullet_points: List[str],
                cta: str, keywords: List[str], scores: Dict[str, float],
                dedupe_key: str = None, script: str = "", 
                disclaimer: str = None) -> IdeaSchema:
    """
    Helper function to create a new idea
    
    Args:
        idea_id: Unique identifier
        topic: Topic description
        hook: Hook/opening line
        bullet_points: List of key points
        cta: Call to action text
        keywords: List of keywords
        scores: Score dictionary
        dedupe_key: Optional deduplication key
        script: Optional initial script
        disclaimer: Optional disclaimer (uses default if None)
        
    Returns:
        IdeaSchema instance
    """
    from config import IUL_PIPELINE_CONFIG
    
    if disclaimer is None:
        disclaimer = IUL_PIPELINE_CONFIG["required_disclaimer"]
    
    if dedupe_key is None:
        # Generate from topic and timestamp
        import hashlib
        import time
        content = f"{topic}_{int(time.time() / 86400)}"  # Daily dedupe
        dedupe_key = hashlib.md5(content.encode()).hexdigest()[:16]
    
    return IdeaSchema(
        idea_id=idea_id,
        created_at=time.time(),
        topic=topic,
        hook=hook,
        bullet_points=bullet_points,
        script=script,
        script_final=None,
        cta=cta,
        disclaimer=disclaimer,
        keywords=keywords,
        scores=scores,
        status=IdeaStatus.READY.value,
        dedupe_key=dedupe_key
    )
