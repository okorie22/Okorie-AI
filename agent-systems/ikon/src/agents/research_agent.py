"""
Research Agent for IKON IUL Pipeline
Aggregates intelligence and generates scored video ideas
"""

import json
import logging
import time
import uuid
from typing import Dict, Any, List
from src.content.ideas_manager import IdeasManager, create_idea
from src.queue.redis_client import RedisQueueClient, create_job
from config import IUL_PIPELINE_CONFIG

logger = logging.getLogger("research_agent")


class ResearchAgent:
    """Generates IUL education ideas from aggregated intelligence"""
    
    def __init__(self, deepseek_connection, ideas_manager: IdeasManager,
                 redis_client: RedisQueueClient):
        """
        Initialize research agent
        
        Args:
            deepseek_connection: DeepSeek AI connection
            ideas_manager: Ideas storage manager
            redis_client: Redis queue client
        """
        self.deepseek = deepseek_connection
        self.ideas = ideas_manager
        self.redis = redis_client
        
        logger.info("Research agent initialized")
    
    def generate_ideas(self, analytics: Dict[str, Any], competitor_data: Dict[str, Any],
                      search_data: Dict[str, Any], count: int = 5) -> List[Dict[str, Any]]:
        """
        Generate video ideas from intelligence
        
        Args:
            analytics: Channel analytics data
            competitor_data: Competitor analysis data
            search_data: Search insights data
            count: Number of ideas to generate
            
        Returns:
            List of generated ideas
        """
        logger.info(f"Generating {count} IUL education ideas...")
        
        # Build context prompt
        context = self._build_context(analytics, competitor_data, search_data)
        
        # Generate ideas using AI
        ideas_raw = self._generate_ideas_ai(context, count)
        
        # Score and validate ideas
        ideas_scored = []
        for idea_raw in ideas_raw:
            idea_scored = self._score_idea(idea_raw)
            ideas_scored.append(idea_scored)
        
        logger.info(f"✅ Generated {len(ideas_scored)} scored ideas")
        return ideas_scored
    
    def enqueue_ready_ideas(self, min_hook_score: float = 75, 
                           max_compliance_risk: float = 20) -> int:
        """
        Enqueue high-scoring ideas to Redis pipeline
        
        Args:
            min_hook_score: Minimum hook score threshold
            max_compliance_risk: Maximum compliance risk threshold
            
        Returns:
            Number of ideas enqueued
        """
        logger.info("Checking for ready ideas to enqueue...")
        
        ready_ideas = self.ideas.get_ready_ideas(min_hook_score, max_compliance_risk)
        
        enqueued = 0
        for idea in ready_ideas:
            # Check dedupe
            if self.redis.length("ideas:ready") >= 10:
                logger.info("Queue full, skipping enqueue")
                break
            
            # Create job
            job = create_job(idea.idea_id, idea.to_dict(), idea.dedupe_key)
            
            # Enqueue
            if self.redis.enqueue("ideas:ready", job):
                self.ideas.update_idea_status(idea.idea_id, idea.status, 
                                            status="queued")
                enqueued += 1
                logger.info(f"Enqueued: {idea.idea_id} (score: {idea.scores.get('hook_score', 0)})")
        
        logger.info(f"✅ Enqueued {enqueued} ideas to pipeline")
        return enqueued
    
    def _build_context(self, analytics: Dict[str, Any], competitor_data: Dict[str, Any],
                      search_data: Dict[str, Any]) -> str:
        """Build context for AI idea generation"""
        context_parts = []
        
        # Own channel performance
        if analytics and "insights" in analytics:
            insights = analytics["insights"]
            context_parts.append(f"YOUR CHANNEL INSIGHTS:")
            context_parts.append(f"- Average views: {insights.get('avg_views', 0):.0f}")
            context_parts.append(f"- Engagement rate: {insights.get('avg_engagement_rate', 0):.2%}")
            
            if "best_performer" in insights:
                best = insights["best_performer"]
                context_parts.append(f"- Best performer: '{best['title']}' ({best['views']} views)")
        
        # Competitor trends
        if competitor_data and "trending_topics" in competitor_data:
            topics = competitor_data["trending_topics"][:5]
            context_parts.append(f"\nCOMPETITOR TRENDING TOPICS:")
            for topic in topics:
                context_parts.append(f"- {topic['keyword']} (frequency: {topic['frequency']})")
        
        # Search insights
        if search_data and "insights" in search_data:
            insights = search_data["insights"]
            if "rising_keywords" in insights:
                context_parts.append(f"\nRISING SEARCH TERMS:")
                for kw in insights["rising_keywords"][:5]:
                    context_parts.append(f"- {kw}")
            
            if "popular_query_patterns" in insights:
                patterns = insights["popular_query_patterns"]
                context_parts.append(f"\nPOPULAR QUERY PATTERNS:")
                for pattern, count in patterns.items():
                    context_parts.append(f"- {pattern.replace('_', ' ')}: {count}")
        
        return "\n".join(context_parts)
    
    def _generate_ideas_ai(self, context: str, count: int) -> List[Dict[str, Any]]:
        """Generate ideas using AI"""
        prompt = f"""You are an IUL education content strategist. Generate {count} YouTube Shorts ideas for IUL education.

INTELLIGENCE CONTEXT:
{context}

CONTENT REQUIREMENTS:
- Educational ONLY (no sales, no advice)
- One clear claim per Short
- Hook-driven (curiosity, specificity, value)
- 30-second format (hook → 2-3 points → CTA)
- Compliance-safe (no guarantees, no personalized advice)

GENERATE {count} IDEAS in JSON array format:
[
  {{
    "topic": "Brief topic description",
    "hook": "Attention-grabbing opening line (10-15 words)",
    "bullet_points": ["Point 1", "Point 2", "Point 3"],
    "keywords": ["keyword1", "keyword2", "keyword3"]
  }}
]

Focus on educational value, curiosity, and compliance. Make hooks specific and intriguing."""

        try:
            response = self.deepseek.generate_text(
                prompt=prompt,
                temperature=0.8,
                max_tokens=1500
            )
            
            # Parse JSON from response
            json_match = None
            if "```json" in response:
                json_match = response.split("```json")[1].split("```")[0].strip()
            elif "[" in response:
                start = response.find("[")
                end = response.rfind("]") + 1
                json_match = response[start:end]
            else:
                logger.warning("No JSON array found in AI response")
                return []
            
            ideas_raw = json.loads(json_match)
            
            if not isinstance(ideas_raw, list):
                logger.warning("AI response is not a list")
                return []
            
            return ideas_raw[:count]
            
        except Exception as e:
            logger.error(f"AI idea generation failed: {e}")
            return []
    
    def _score_idea(self, idea_raw: Dict[str, Any]) -> Dict[str, Any]:
        """Score and validate an idea"""
        # Generate unique ID
        idea_id = f"idea_{str(uuid.uuid4())[:8]}_{int(time.time())}"
        
        # Score components
        hook_score = self._score_hook(idea_raw.get("hook", ""))
        topic_fit_score = self._score_topic_fit(idea_raw.get("topic", ""))
        compliance_risk = self._score_compliance_risk(idea_raw)
        
        # Add CTA
        cta = self._generate_cta()
        
        # Create idea object
        idea = create_idea(
            idea_id=idea_id,
            topic=idea_raw.get("topic", ""),
            hook=idea_raw.get("hook", ""),
            bullet_points=idea_raw.get("bullet_points", []),
            cta=cta,
            keywords=idea_raw.get("keywords", []),
            scores={
                "hook_score": hook_score,
                "topic_fit_score": topic_fit_score,
                "compliance_risk": compliance_risk
            }
        )
        
        # Save to storage
        self.ideas.save_idea(idea)
        
        return idea.to_dict()
    
    def _score_hook(self, hook: str) -> float:
        """Score hook quality (0-100)"""
        score = 50  # Base score
        
        # Length check (10-20 words ideal)
        word_count = len(hook.split())
        if 10 <= word_count <= 20:
            score += 20
        elif word_count < 10:
            score -= 10
        
        # Specificity indicators
        specific_words = ["how", "why", "what", "when", "which", "most", "never", "always"]
        if any(word in hook.lower() for word in specific_words):
            score += 15
        
        # Curiosity indicators
        curiosity_words = ["secret", "mistake", "don't know", "understand", "truth", "really"]
        if any(word in hook.lower() for word in curiosity_words):
            score += 15
        
        return min(100, max(0, score))
    
    def _score_topic_fit(self, topic: str) -> float:
        """Score topic fit with IUL education (0-100)"""
        score = 60  # Base score
        
        # IUL-specific terms
        iul_terms = ["iul", "indexed universal life", "cash value", "life insurance", 
                     "premium", "policy", "death benefit", "index", "participation"]
        
        topic_lower = topic.lower()
        matches = sum(1 for term in iul_terms if term in topic_lower)
        score += matches * 10
        
        return min(100, max(0, score))
    
    def _score_compliance_risk(self, idea_raw: Dict[str, Any]) -> float:
        """Score compliance risk (0-100, higher = riskier)"""
        risk = 10  # Base low risk
        
        # Check for risky patterns in hook and topic
        text = f"{idea_raw.get('hook', '')} {idea_raw.get('topic', '')}".lower()
        
        risky_words = ["guarantee", "best", "should", "must", "always wins", 
                      "no risk", "risk-free", "beats", "better than"]
        
        for word in risky_words:
            if word in text:
                risk += 20
        
        return min(100, max(0, risk))
    
    def _generate_cta(self) -> str:
        """Generate CTA text"""
        import random
        cta_options = IUL_PIPELINE_CONFIG.get("cta_text_templates", [
            "Get the free checklist → link in description",
            "Download the free guide → see description"
        ])
        return random.choice(cta_options)
