"""
Specialized AI agent for handling inbound email/SMS replies.
Uses GPT-4 with confidence gating and compliance guardrails.
"""
from typing import Dict, Optional, List, Tuple
from pydantic import BaseModel, Field
from enum import Enum
import json
from loguru import logger
import requests

from .prompts import (
    build_classification_prompt,
    build_response_generation_prompt,
    COMPLIANCE_TRIGGERS,
    ESCALATION_KEYWORDS,
    UNSUBSCRIBE_KEYWORDS
)


class ReplyIntent(str, Enum):
    """Inbound reply intent categories"""
    INTERESTED = "interested"
    SCHEDULING = "scheduling"
    SIMPLE_QUESTION = "simple_question"
    FAQ = "faq"
    OBJECTION = "objection"
    COMPLEX_QUESTION = "complex_question"
    COMPLAINT = "complaint"
    UNSUBSCRIBE = "unsubscribe"
    WRONG_PERSON = "wrong_person"
    UNKNOWN = "unknown"


class ReplyAction(str, Enum):
    """Recommended next action"""
    AUTO_REPLY = "auto_reply"
    ESCALATE = "escalate"
    UNSUBSCRIBE = "unsubscribe"


class ReplyAnalysis(BaseModel):
    """Structured output from AI analysis"""
    intent: ReplyIntent
    confidence: float = Field(..., ge=0.0, le=1.0)
    escalate: bool
    escalation_reason: Optional[str] = None
    response_text: Optional[str] = None
    next_action: ReplyAction
    sentiment: str = "neutral"  # positive, neutral, negative
    
    # Metadata for tracking
    compliance_violations: List[str] = []
    question_count: int = 0


class ReplyAgent:
    """
    AI agent for handling inbound replies with hybrid AI-human approach.
    
    GPT-4 handles simple, safe replies (interested, scheduling, FAQ).
    Escalates complex, risky, or compliance-sensitive replies to human.
    """
    
    def __init__(self, config):
        """
        Initialize with configuration.
        
        Args:
            config: LLMConfig with GPT-4 settings
        """
        self.api_key = config.openai_api_key
        self.model = config.gpt4_model
        self.temperature = config.gpt4_temperature
        self.max_tokens = config.gpt4_max_tokens
        self.confidence_threshold = config.reply_confidence_threshold
        self.auto_reply_enabled = config.auto_reply_enabled
    
    def analyze_and_respond(
        self,
        inbound_message: str,
        lead_data: Dict,
        conversation_history: List[Dict]
    ) -> ReplyAnalysis:
        """
        Main entry point: analyze inbound message and decide on action.
        
        Args:
            inbound_message: The message from the prospect
            lead_data: Lead information dict
            conversation_history: List of previous messages
        
        Returns:
            ReplyAnalysis with intent, confidence, and recommended action
        """
        logger.info(f"Analyzing inbound reply from {lead_data.get('email')}")
        
        # Pre-screening: check for obvious patterns
        pre_screen = self._pre_screen_message(inbound_message)
        if pre_screen:
            logger.info(f"Pre-screen match: {pre_screen.intent}")
            return pre_screen
        
        # Call GPT-4 for classification
        try:
            analysis = self._classify_with_gpt4(
                inbound_message,
                lead_data,
                conversation_history
            )
            
            # Apply confidence gating
            if analysis.confidence < self.confidence_threshold:
                logger.warning(f"Low confidence ({analysis.confidence}), escalating")
                analysis.escalate = True
                analysis.escalation_reason = f"Low confidence ({analysis.confidence:.2f})"
                analysis.next_action = ReplyAction.ESCALATE
            
            # Check if auto-reply is disabled
            if not self.auto_reply_enabled and not analysis.escalate:
                logger.info("Auto-reply disabled, escalating")
                analysis.escalate = True
                analysis.escalation_reason = "Auto-reply disabled in config"
                analysis.next_action = ReplyAction.ESCALATE
            
            return analysis
        
        except Exception as e:
            logger.error(f"Error in GPT-4 analysis: {e}", exc_info=True)
            # Fallback: escalate on error
            return ReplyAnalysis(
                intent=ReplyIntent.UNKNOWN,
                confidence=0.0,
                escalate=True,
                escalation_reason=f"AI analysis error: {str(e)}",
                next_action=ReplyAction.ESCALATE,
                sentiment="neutral"
            )
    
    def _pre_screen_message(self, message: str) -> Optional[ReplyAnalysis]:
        """
        Fast pre-screening for obvious patterns (unsubscribe, stop, threats).
        Returns ReplyAnalysis if match found, None otherwise.
        """
        message_lower = message.lower().strip()
        
        # Check for unsubscribe intent
        if any(keyword in message_lower for keyword in UNSUBSCRIBE_KEYWORDS):
            # Simple unsubscribe - auto-handle
            if len(message.split()) <= 5:  # Short message like "stop" or "unsubscribe please"
                return ReplyAnalysis(
                    intent=ReplyIntent.UNSUBSCRIBE,
                    confidence=1.0,
                    escalate=False,
                    response_text="Understood. I've removed you from our list. You won't hear from us again.",
                    next_action=ReplyAction.UNSUBSCRIBE,
                    sentiment="neutral"
                )
        
        # Check for threats/legal keywords - immediate escalation
        if any(keyword in message_lower for keyword in ESCALATION_KEYWORDS):
            return ReplyAnalysis(
                intent=ReplyIntent.COMPLAINT,
                confidence=1.0,
                escalate=True,
                escalation_reason="Threat or legal keywords detected",
                next_action=ReplyAction.ESCALATE,
                sentiment="negative"
            )
        
        # Check for compliance trigger words - escalate
        if any(trigger in message_lower for trigger in COMPLIANCE_TRIGGERS):
            violations = [t for t in COMPLIANCE_TRIGGERS if t in message_lower]
            return ReplyAnalysis(
                intent=ReplyIntent.COMPLEX_QUESTION,
                confidence=0.9,
                escalate=True,
                escalation_reason=f"Compliance keywords detected: {', '.join(violations[:3])}",
                next_action=ReplyAction.ESCALATE,
                sentiment="neutral",
                compliance_violations=violations
            )
        
        return None
    
    def _classify_with_gpt4(
        self,
        inbound_message: str,
        lead_data: Dict,
        conversation_history: List[Dict]
    ) -> ReplyAnalysis:
        """
        Call GPT-4 to classify intent and generate response.
        """
        # Build prompt
        prompt = build_classification_prompt(
            inbound_message,
            conversation_history,
            lead_data
        )
        
        # Call GPT-4
        response_text = self._call_gpt4(prompt)
        
        # Parse JSON response
        analysis = self._parse_gpt4_response(response_text)
        
        # Additional validation
        analysis = self._validate_analysis(analysis, inbound_message)
        
        return analysis
    
    def _call_gpt4(self, prompt: str) -> str:
        """
        Call OpenAI GPT-4 API.
        
        Args:
            prompt: The complete prompt
        
        Returns:
            Response text from GPT-4
        """
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful AI assistant analyzing customer messages for an IUL consultant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        logger.debug(f"Calling GPT-4: {self.model}")
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _parse_gpt4_response(self, response_text: str) -> ReplyAnalysis:
        """
        Parse GPT-4 response into ReplyAnalysis.
        """
        try:
            # Extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)
                
                # Map to ReplyAnalysis
                intent_str = data.get("intent", "UNKNOWN").lower()
                
                # Handle intent mapping
                intent_map = {
                    "interested": ReplyIntent.INTERESTED,
                    "scheduling": ReplyIntent.SCHEDULING,
                    "simple_question": ReplyIntent.SIMPLE_QUESTION,
                    "faq": ReplyIntent.FAQ,
                    "objection": ReplyIntent.OBJECTION,
                    "complex_question": ReplyIntent.COMPLEX_QUESTION,
                    "complaint": ReplyIntent.COMPLAINT,
                    "unsubscribe": ReplyIntent.UNSUBSCRIBE,
                    "wrong_person": ReplyIntent.WRONG_PERSON,
                    "unknown": ReplyIntent.UNKNOWN
                }
                
                intent = intent_map.get(intent_str, ReplyIntent.UNKNOWN)
                escalate = data.get("escalate", False)
                
                # Determine next action
                if escalate:
                    next_action = ReplyAction.ESCALATE
                elif intent == ReplyIntent.UNSUBSCRIBE:
                    next_action = ReplyAction.UNSUBSCRIBE
                else:
                    next_action = ReplyAction.AUTO_REPLY
                
                return ReplyAnalysis(
                    intent=intent,
                    confidence=float(data.get("confidence", 0.5)),
                    escalate=escalate,
                    escalation_reason=data.get("escalation_reason") if escalate else None,
                    response_text=data.get("response_text") if not escalate else None,
                    next_action=next_action,
                    sentiment=data.get("sentiment", "neutral")
                )
            else:
                raise ValueError("No JSON found in response")
        
        except Exception as e:
            logger.error(f"Error parsing GPT-4 response: {e}")
            logger.debug(f"Response text: {response_text}")
            
            # Return safe fallback
            return ReplyAnalysis(
                intent=ReplyIntent.UNKNOWN,
                confidence=0.0,
                escalate=True,
                escalation_reason=f"Parse error: {str(e)}",
                next_action=ReplyAction.ESCALATE,
                sentiment="neutral"
            )
    
    def _validate_analysis(self, analysis: ReplyAnalysis, message: str) -> ReplyAnalysis:
        """
        Additional validation and safety checks on the analysis.
        """
        # Count questions in message
        question_count = message.count("?")
        analysis.question_count = question_count
        
        # If multiple questions (>2), escalate
        if question_count > 2 and not analysis.escalate:
            logger.warning(f"Multiple questions detected ({question_count}), escalating")
            analysis.escalate = True
            analysis.escalation_reason = f"Multiple questions ({question_count}) detected"
            analysis.next_action = ReplyAction.ESCALATE
        
        # If response is too long, escalate (safety)
        if analysis.response_text and len(analysis.response_text) > 500:
            logger.warning("AI generated overly long response, escalating")
            analysis.escalate = True
            analysis.escalation_reason = "Response too long (AI safety)"
            analysis.next_action = ReplyAction.ESCALATE
            analysis.response_text = None
        
        # If negative sentiment and not already escalating, escalate
        if analysis.sentiment == "negative" and not analysis.escalate:
            logger.warning("Negative sentiment detected, escalating")
            analysis.escalate = True
            analysis.escalation_reason = "Negative sentiment detected"
            analysis.next_action = ReplyAction.ESCALATE
        
        # Check if response contains compliance violations
        if analysis.response_text:
            response_lower = analysis.response_text.lower()
            violations = [t for t in COMPLIANCE_TRIGGERS if t in response_lower]
            if violations:
                logger.error(f"AI response contains compliance violations: {violations}")
                analysis.escalate = True
                analysis.escalation_reason = f"AI generated prohibited content: {violations[:2]}"
                analysis.next_action = ReplyAction.ESCALATE
                analysis.response_text = None
                analysis.compliance_violations = violations
        
        return analysis
    
    def generate_human_recommendation(
        self,
        analysis: ReplyAnalysis,
        inbound_message: str,
        lead_data: Dict
    ) -> str:
        """
        Generate a recommendation for human agent on how to handle this conversation.
        
        Args:
            analysis: The AI analysis
            inbound_message: Original message
            lead_data: Lead information
        
        Returns:
            Text recommendation for human
        """
        recommendations = {
            ReplyIntent.OBJECTION: "This is an objection. Consider addressing their concern and reframing the value proposition. Offer to answer specific questions on the call.",
            ReplyIntent.COMPLEX_QUESTION: "They're asking detailed questions that require personalized advice. Acknowledge their questions and position the call as a way to provide tailored answers.",
            ReplyIntent.COMPLAINT: "This is a complaint or negative sentiment. Apologize for any inconvenience, clarify your intent (helping, not selling), and offer to remove them if they prefer.",
            ReplyIntent.UNKNOWN: "The intent is unclear. Consider asking a clarifying question or offering to discuss on a brief call.",
        }
        
        base = recommendations.get(analysis.intent, "Review the message and respond appropriately based on their specific situation.")
        
        # Add context
        if analysis.question_count > 2:
            base += f" Note: They asked {analysis.question_count} questions - consider addressing the most important one first."
        
        if analysis.compliance_violations:
            base += f" Warning: They mentioned {', '.join(analysis.compliance_violations[:2])} - be careful not to make guarantees."
        
        return base
