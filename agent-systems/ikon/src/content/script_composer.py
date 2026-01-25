"""
Script Composer for IKON IUL Pipeline
Expands ideas into compliant 30-second scripts with optional 2nd draft
"""

import logging
from typing import Dict, Any, Optional
from src.content.ideas_manager import IdeaSchema
from config import IUL_PIPELINE_CONFIG

logger = logging.getLogger("script_composer")


class ScriptComposer:
    """Composes 30-second scripts from IUL education ideas"""
    
    def __init__(self, deepseek_connection):
        """
        Initialize script composer
        
        Args:
            deepseek_connection: DeepSeek AI connection
        """
        self.deepseek = deepseek_connection
        self.config = IUL_PIPELINE_CONFIG
    
    def compose_script(self, idea: IdeaSchema, force_second_draft: bool = False) -> Dict[str, Any]:
        """
        Compose script from idea
        
        Args:
            idea: IdeaSchema instance
            force_second_draft: Force a second draft regardless of score
            
        Returns:
            Dictionary with script, word_count, needs_revision, compliance_hints
        """
        logger.info(f"Composing script for idea: {idea.idea_id}")
        
        # First draft
        first_draft = self._generate_first_draft(idea)
        
        # Check if second draft is needed
        compliance_risk = idea.scores.get("compliance_risk", 50)
        needs_revision = force_second_draft or (20 <= compliance_risk <= 40)
        
        if needs_revision:
            logger.info(f"Generating second draft (compliance_risk={compliance_risk})")
            final_script = self._generate_second_draft(idea, first_draft)
        else:
            final_script = first_draft
        
        # Word count check
        word_count = len(final_script.split())
        
        result = {
            "script": final_script,
            "word_count": word_count,
            "first_draft": first_draft,
            "revised": needs_revision,
            "within_target": (self.config["min_word_count"] <= word_count <= self.config["max_word_count"]),
            "compliance_hints": self._extract_compliance_hints(final_script)
        }
        
        logger.info(f"Script composed: {word_count} words, revised={needs_revision}")
        return result
    
    def _generate_first_draft(self, idea: IdeaSchema) -> str:
        """Generate first draft script"""
        prompt = f"""You are an IUL education script writer. Create a 30-second YouTube Short script (140-160 words) that is:

EDUCATIONAL ONLY - No individualized advice, no recommendations for specific people
COMPLIANT - No guarantees, no "risk-free" claims, no "beats the market" statements
ENGAGING - Strong hook, clear value, conversational tone

IDEA DETAILS:
Topic: {idea.topic}
Hook: {idea.hook}
Key Points:
{chr(10).join('- ' + bp for bp in idea.bullet_points)}
CTA: {idea.cta}

STRICT REQUIREMENTS:
1. Start with the hook (0-2 seconds, ~10 words)
2. Expand on 2-3 key points (20-25 seconds, ~120-140 words)
3. End with CTA and disclaimer (~5 seconds, ~20-30 words)
4. Use "can" or "may" instead of "will" or "should"
5. Avoid "you should", "you need", "guaranteed", "risk-free"
6. Keep educational framing: "Some people explore...", "This approach involves..."
7. Total: 140-160 words for natural pacing

DISCLAIMER TO INCLUDE:
"{idea.disclaimer}"

Generate ONLY the script text, no labels or formatting."""

        try:
            script = self.deepseek.generate_text(
                prompt=prompt,
                temperature=0.7,
                max_tokens=400
            )
            return script.strip()
        except Exception as e:
            logger.error(f"First draft generation failed: {e}")
            # Fallback: basic script from idea components
            return self._generate_fallback_script(idea)
    
    def _generate_second_draft(self, idea: IdeaSchema, first_draft: str) -> str:
        """Generate revised second draft"""
        prompt = f"""You are reviewing an IUL education script for compliance and clarity.

FIRST DRAFT:
{first_draft}

REVIEW CRITERIA:
1. Remove ANY implied guarantees or "risk-free" language
2. Replace "you should" with "some people consider" or "this approach may"
3. Ensure educational tone (explaining concepts, not selling/recommending)
4. Verify disclaimer is present: "{idea.disclaimer}"
5. Check word count is 140-160 words for 30-second pacing
6. Maintain the engaging hook and clear CTA

IMPROVE the script for:
- Stronger compliance (no advice, no guarantees)
- Clearer educational framing
- Better pacing and flow
- More natural conversational tone

Generate ONLY the improved script text, no commentary."""

        try:
            revised_script = self.deepseek.generate_text(
                prompt=prompt,
                temperature=0.6,  # Slightly less creative for revision
                max_tokens=400
            )
            return revised_script.strip()
        except Exception as e:
            logger.error(f"Second draft generation failed: {e}")
            return first_draft  # Return first draft as fallback
    
    def _generate_fallback_script(self, idea: IdeaSchema) -> str:
        """Generate basic fallback script if AI fails"""
        script_parts = [
            idea.hook,
            "",
            "\n\n".join(idea.bullet_points),
            "",
            f"{idea.cta}",
            "",
            idea.disclaimer
        ]
        return "\n".join(script_parts)
    
    def _extract_compliance_hints(self, script: str) -> Dict[str, Any]:
        """Extract compliance hints from script"""
        script_lower = script.lower()
        
        # Check for blocked phrases
        blocked_found = []
        for phrase in self.config["blocked_phrases"]:
            if phrase.lower() in script_lower:
                blocked_found.append(phrase)
        
        # Check for disclaimer
        has_disclaimer = any(
            word in script_lower 
            for word in ["educational", "not advice", "disclaimer", "consult"]
        )
        
        # Check for advice patterns
        advice_patterns = ["you should", "you need", "you must", "your situation"]
        advice_found = [p for p in advice_patterns if p in script_lower]
        
        return {
            "blocked_phrases_found": blocked_found,
            "has_disclaimer": has_disclaimer,
            "advice_patterns_found": advice_found,
            "appears_compliant": (
                len(blocked_found) == 0 and 
                has_disclaimer and 
                len(advice_found) == 0
            )
        }
    
    def validate_script_length(self, script: str) -> Dict[str, Any]:
        """Validate script meets length requirements"""
        word_count = len(script.split())
        
        return {
            "word_count": word_count,
            "min_words": self.config["min_word_count"],
            "target_words": self.config["target_word_count"],
            "max_words": self.config["max_word_count"],
            "within_range": (
                self.config["min_word_count"] <= word_count <= self.config["max_word_count"]
            ),
            "is_target": (
                abs(word_count - self.config["target_word_count"]) <= 10
            )
        }
