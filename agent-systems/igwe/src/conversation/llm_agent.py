"""
LLM Conversation Agent with structured outputs and compliance guardrails.
"""
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from enum import Enum
import os
import json
from loguru import logger
import requests


class Intent(str, Enum):
    """Message intent classification"""
    INTERESTED = "interested"
    OBJECTION = "objection"
    WRONG_PERSON = "wrong_person"
    STOP = "stop"
    NEED_INFO = "need_info"
    QUESTION = "question"
    READY_TO_SCHEDULE = "ready_to_schedule"
    UNKNOWN = "unknown"


class NextStage(str, Enum):
    """Suggested next conversation stage"""
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    SCHEDULED = "scheduled"
    NOT_INTERESTED = "not_interested"
    STOPPED = "stopped"
    STAY_CURRENT = "stay_current"


class LLMResponse(BaseModel):
    """Structured LLM output"""
    intent: Intent
    next_stage: NextStage
    response_text: str = Field(..., max_length=500)
    qualification_data: Optional[Dict] = None
    proposed_times: Optional[List[str]] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_human_review: bool = False


class ComplianceGuardrails:
    """Compliance checking and filtering"""
    
    # Stop words that trigger immediate opt-out
    STOP_WORDS = [
        "stop", "unsubscribe", "remove", "don't contact", "do not contact",
        "take me off", "opt out", "opt-out", "cease", "desist"
    ]
    
    # Prohibited content patterns
    PROHIBITED_PATTERNS = [
        "guarantee", "guaranteed return", "guaranteed rate",
        "risk-free", "risk free", "no risk",
        "specific rate of", "will earn", "will grow",
        "medical advice", "diagnose", "treat",
        "promise", "assured"
    ]
    
    # Keywords triggering human escalation
    ESCALATION_KEYWORDS = [
        "sue", "lawsuit", "lawyer", "attorney",
        "report", "complaint", "ftc", "sec",
        "attorney general", "fraud", "scam",
        "harass", "threat"
    ]
    
    @classmethod
    def check_stop_intent(cls, message: str) -> bool:
        """Check if message contains stop intent"""
        message_lower = message.lower()
        return any(word in message_lower for word in cls.STOP_WORDS)
    
    @classmethod
    def check_prohibited_content(cls, message: str) -> List[str]:
        """Check for prohibited content. Returns list of violations."""
        message_lower = message.lower()
        violations = []
        
        for pattern in cls.PROHIBITED_PATTERNS:
            if pattern in message_lower:
                violations.append(pattern)
        
        return violations
    
    @classmethod
    def needs_escalation(cls, message: str) -> bool:
        """Check if message should be escalated to human"""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in cls.ESCALATION_KEYWORDS)
    
    @classmethod
    def sanitize_response(cls, response: str) -> str:
        """Remove or replace prohibited content from response"""
        sanitized = response
        
        # Replace problematic phrases
        replacements = {
            "guaranteed": "expected",
            "guarantee": "anticipate",
            "risk-free": "lower-risk",
            "no risk": "managed risk",
            "will earn": "may earn",
            "will grow": "can grow",
        }
        
        for bad, good in replacements.items():
            sanitized = sanitized.replace(bad, good)
            sanitized = sanitized.replace(bad.title(), good.title())
        
        return sanitized


class LLMAgent:
    """LLM-powered conversation agent with guardrails"""
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.provider = os.getenv("LLM_PROVIDER", "deepseek")
        self.guardrails = ComplianceGuardrails()
    
    def classify_intent(self, message: str, conversation_history: List[Dict]) -> LLMResponse:
        """
        Classify incoming message intent and determine next action.
        Returns structured response with guardrails applied.
        """
        # Check compliance first
        if self.guardrails.check_stop_intent(message):
            return LLMResponse(
                intent=Intent.STOP,
                next_stage=NextStage.STOPPED,
                response_text="",
                confidence=1.0,
                needs_human_review=False
            )
        
        if self.guardrails.needs_escalation(message):
            logger.warning(f"Message requires human escalation: {message[:100]}")
            return LLMResponse(
                intent=Intent.UNKNOWN,
                next_stage=NextStage.STAY_CURRENT,
                response_text="I've noted your message and will have someone reach out to you directly.",
                confidence=0.5,
                needs_human_review=True
            )
        
        # Call LLM for classification
        try:
            prompt = self._build_classification_prompt(message, conversation_history)
            llm_output = self._call_llm(prompt)
            
            # Parse structured output
            response = self._parse_llm_response(llm_output)
            
            # Apply compliance filters
            response.response_text = self.guardrails.sanitize_response(response.response_text)
            
            # Check if response contains prohibited content
            violations = self.guardrails.check_prohibited_content(response.response_text)
            if violations:
                logger.warning(f"LLM generated prohibited content: {violations}")
                response.needs_human_review = True
                response.response_text = "Thank you for your interest. Let me have a colleague reach out to discuss your specific situation."
            
            return response
        
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
            # Fallback response
            return LLMResponse(
                intent=Intent.UNKNOWN,
                next_stage=NextStage.STAY_CURRENT,
                response_text="Thank you for your message. I'll get back to you shortly.",
                confidence=0.0,
                needs_human_review=True
            )
    
    def generate_response(
        self,
        message: str,
        lead_data: Dict,
        conversation_stage: str
    ) -> str:
        """
        Generate contextual response based on message and lead data.
        """
        try:
            prompt = self._build_response_prompt(message, lead_data, conversation_stage)
            response = self._call_llm(prompt)
            
            # Apply compliance filters
            response = self.guardrails.sanitize_response(response)
            
            # Check violations
            violations = self.guardrails.check_prohibited_content(response)
            if violations:
                logger.warning(f"Generated response has violations: {violations}")
                return "Thank you for your interest. Let me have a colleague provide specific details."
            
            return response
        
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Thank you for your message. I'll get back to you shortly."
    
    def _build_classification_prompt(self, message: str, history: List[Dict]) -> str:
        """Build prompt for intent classification"""
        history_text = "\n".join([
            f"{h['role']}: {h['content']}" for h in history[-3:]  # Last 3 messages
        ])
        
        return f"""You are an AI assistant helping classify customer messages for an IUL insurance appointment setter.

Conversation history:
{history_text}

New message from prospect:
"{message}"

Classify the intent and suggest next action. Return JSON with:
{{
  "intent": "interested|objection|wrong_person|stop|need_info|question|ready_to_schedule|unknown",
  "next_stage": "engaged|qualified|scheduled|not_interested|stopped|stay_current",
  "response_text": "Brief, professional response (max 2 sentences)",
  "qualification_data": {{"age_band": "...", "goal": "..."}},  # if applicable
  "proposed_times": ["..."],  # if scheduling
  "confidence": 0.0-1.0
}}

Guidelines:
- Be professional and compliant
- Never make guarantees or promises about returns
- Focus on scheduling, not selling
- Keep responses brief and actionable"""
    
    def _build_response_prompt(self, message: str, lead_data: Dict, stage: str) -> str:
        """Build prompt for response generation"""
        return f"""You are an AI assistant helping schedule IUL strategy consultations.

Lead information:
- Name: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
- Company: {lead_data.get('company_name', '')}
- Industry: {lead_data.get('industry', '')}
- Conversation stage: {stage}

Their message:
"{message}"

Generate a brief, professional response (max 2 sentences) that:
1. Addresses their question/concern
2. Moves toward scheduling a call
3. Stays compliant (no guarantees, no medical advice, no specific rate promises)

Response:"""
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM API (DeepSeek or OpenAI)"""
        if not self.api_key:
            logger.warning("No LLM API key configured, using fallback")
            return self._fallback_response()
        
        if self.provider == "deepseek":
            return self._call_deepseek(prompt)
        else:
            return self._call_openai(prompt)
    
    def _call_deepseek(self, prompt: str) -> str:
        """Call DeepSeek API"""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 300
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 300
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _parse_llm_response(self, llm_output: str) -> LLMResponse:
        """Parse LLM output into structured response"""
        try:
            # Try to extract JSON from response
            json_start = llm_output.find("{")
            json_end = llm_output.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = llm_output[json_start:json_end]
                data = json.loads(json_str)
                return LLMResponse(**data)
            else:
                # If no JSON, treat as plain text response
                return LLMResponse(
                    intent=Intent.UNKNOWN,
                    next_stage=NextStage.STAY_CURRENT,
                    response_text=llm_output[:500],
                    confidence=0.5
                )
        
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return LLMResponse(
                intent=Intent.UNKNOWN,
                next_stage=NextStage.STAY_CURRENT,
                response_text="Thank you for your message. I'll review and get back to you.",
                confidence=0.0,
                needs_human_review=True
            )
    
    def _fallback_response(self) -> str:
        """Fallback response when LLM is unavailable"""
        return json.dumps({
            "intent": "unknown",
            "next_stage": "stay_current",
            "response_text": "Thank you for your interest. I'll get back to you shortly.",
            "confidence": 0.0
        })
