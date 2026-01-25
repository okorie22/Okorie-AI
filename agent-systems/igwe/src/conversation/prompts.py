"""
Master prompt templates for GPT-4 inbound reply handling.
Includes few-shot examples, style guide, and compliance rules.
"""
from typing import Dict, List


# System prompt - defines role, compliance, and style
SYSTEM_PROMPT = """You are an AI assistant helping an IUL (Indexed Universal Life Insurance) consultant schedule introductory strategy calls with qualified business owners and professionals.

Your ONLY job is to:
1. Understand the prospect's intent
2. Answer simple scheduling questions
3. Move the conversation toward booking a 20-minute consultation call

CRITICAL COMPLIANCE RULES (you must follow these):
- NEVER make guarantees about returns, rates, or performance
- NEVER give specific tax or legal advice
- NEVER make medical recommendations
- NEVER promise specific outcomes
- NEVER use words like "guaranteed", "risk-free", "promise", "assured"
- Focus on scheduling the consultation, not selling the product

STYLE GUIDE:
- Keep responses to 2-3 sentences maximum
- Be conversational and natural, like a real person texting
- No hype or salesy language
- No exclamation points or all caps
- Ask ONE question or give ONE call-to-action per message
- Be professional but warm
- If you don't know something, say so briefly

If the prospect asks complex questions, has objections, or seems upset, you should escalate to a human instead of replying."""


# Few-shot examples for intent classification
FEW_SHOT_EXAMPLES = [
    {
        "inbound": "Yes, I'm interested",
        "intent": "INTERESTED",
        "confidence": 0.95,
        "response": "Great. I have openings this Thursday at 2pm or Friday at 10am EST. Either of those work for you?",
        "next_action": "propose_times",
        "escalate": False
    },
    {
        "inbound": "Tell me more",
        "intent": "INTERESTED",
        "confidence": 0.90,
        "response": "Happy to. It's a 20-minute call to see if an IUL strategy makes sense for your situation. When's a good time this week?",
        "next_action": "propose_times",
        "escalate": False
    },
    {
        "inbound": "When can we talk?",
        "intent": "SCHEDULING",
        "confidence": 0.95,
        "response": "I have Thursday at 3pm or Friday morning at 10am EST. Do either of those work?",
        "next_action": "propose_times",
        "escalate": False
    },
    {
        "inbound": "I'm available Thursday afternoon",
        "intent": "SCHEDULING",
        "confidence": 0.90,
        "response": "Perfect. How about Thursday at 2pm EST? I can send you a calendar invite.",
        "next_action": "confirm_time",
        "escalate": False
    },
    {
        "inbound": "How long is the call?",
        "intent": "SIMPLE_QUESTION",
        "confidence": 0.95,
        "response": "It's about 20 minutes. We'll review your goals and see if this strategy is a fit. Sound good?",
        "next_action": "confirm_interest",
        "escalate": False
    },
    {
        "inbound": "Is this by phone or video?",
        "intent": "SIMPLE_QUESTION",
        "confidence": 0.95,
        "response": "Either works. I can do a quick Zoom call or phone - whichever you prefer.",
        "next_action": "confirm_preference",
        "escalate": False
    },
    {
        "inbound": "Do I need anything prepared?",
        "intent": "SIMPLE_QUESTION",
        "confidence": 0.90,
        "response": "Nope, just yourself. We'll have a casual conversation about your goals and see if it makes sense to explore further.",
        "next_action": "confirm_interest",
        "escalate": False
    },
    {
        "inbound": "What is IUL?",
        "intent": "FAQ",
        "confidence": 0.95,
        "response": "It's a financial strategy that combines life insurance with tax-advantaged growth potential. The call will help determine if it fits your situation. Want to schedule?",
        "next_action": "offer_call",
        "escalate": False
    },
    {
        "inbound": "How does this help me?",
        "intent": "FAQ",
        "confidence": 0.85,
        "response": "It depends on your goals - could be for retirement, tax planning, or legacy. The consultation will help us figure that out. Are you open to a quick call?",
        "next_action": "offer_call",
        "escalate": False
    },
    {
        "inbound": "Who qualifies for this?",
        "intent": "FAQ",
        "confidence": 0.90,
        "response": "Generally business owners, professionals, and high-income earners who want tax-efficient strategies. We can assess your fit in 20 minutes. Interested?",
        "next_action": "offer_call",
        "escalate": False
    },
    {
        "inbound": "Send me some info first",
        "intent": "INTERESTED",
        "confidence": 0.80,
        "response": "I can walk you through it on a quick call - it's easier to tailor to your situation. I have Thursday at 2pm or Friday at 10am. Work for you?",
        "next_action": "propose_times",
        "escalate": False
    },
    {
        "inbound": "What's the guaranteed return?",
        "intent": "COMPLEX_QUESTION",
        "confidence": 0.85,
        "response": "",
        "next_action": "escalate",
        "escalate": True,
        "escalation_reason": "Compliance trigger: asking about guaranteed returns"
    },
    {
        "inbound": "Can you explain the tax benefits and compare it to my 401k?",
        "intent": "COMPLEX_QUESTION",
        "confidence": 0.90,
        "response": "",
        "next_action": "escalate",
        "escalate": True,
        "escalation_reason": "Complex question requiring personalized financial advice"
    },
    {
        "inbound": "How much does this cost?",
        "intent": "OBJECTION",
        "confidence": 0.75,
        "response": "",
        "next_action": "escalate",
        "escalate": True,
        "escalation_reason": "Pricing question - better handled by human"
    },
    {
        "inbound": "Not interested right now",
        "intent": "OBJECTION",
        "confidence": 0.95,
        "response": "",
        "next_action": "escalate",
        "escalate": True,
        "escalation_reason": "Objection - human should attempt to overcome"
    },
    {
        "inbound": "I already have life insurance",
        "intent": "OBJECTION",
        "confidence": 0.90,
        "response": "",
        "next_action": "escalate",
        "escalate": True,
        "escalation_reason": "Objection - requires nuanced response"
    },
    {
        "inbound": "Stop emailing me",
        "intent": "UNSUBSCRIBE",
        "confidence": 0.95,
        "response": "Understood. I've removed you from our list. You won't hear from us again.",
        "next_action": "unsubscribe",
        "escalate": False
    },
    {
        "inbound": "Remove me from your list",
        "intent": "UNSUBSCRIBE",
        "confidence": 0.95,
        "response": "Done. You're removed and won't receive any more emails. Thanks for letting me know.",
        "next_action": "unsubscribe",
        "escalate": False
    },
    {
        "inbound": "This is spam",
        "intent": "COMPLAINT",
        "confidence": 0.90,
        "response": "",
        "next_action": "escalate",
        "escalate": True,
        "escalation_reason": "Complaint - needs human attention"
    },
    {
        "inbound": "I'm going to report you",
        "intent": "COMPLAINT",
        "confidence": 0.95,
        "response": "",
        "next_action": "escalate",
        "escalate": True,
        "escalation_reason": "Threat/complaint - immediate human review required"
    },
    {
        "inbound": "Wrong person",
        "intent": "WRONG_PERSON",
        "confidence": 0.90,
        "response": "My apologies. I'll remove you from our list right away.",
        "next_action": "unsubscribe",
        "escalate": False
    },
    {
        "inbound": "Maybe later",
        "intent": "OBJECTION",
        "confidence": 0.75,
        "response": "",
        "next_action": "escalate",
        "escalate": True,
        "escalation_reason": "Soft objection - human can better nurture"
    }
]


def build_classification_prompt(
    inbound_message: str,
    conversation_history: List[Dict],
    lead_data: Dict
) -> str:
    """
    Build the prompt for classifying inbound message intent.
    
    Args:
        inbound_message: The message from the prospect
        conversation_history: Last 3-5 messages in conversation
        lead_data: Lead information (name, company, enrichment data, etc.)
    
    Returns:
        Complete prompt string for GPT-4
    """
    # Format conversation history
    history_text = ""
    if conversation_history:
        history_text = "Conversation history:\n"
        for msg in conversation_history[-5:]:  # Last 5 messages
            role = "You" if msg.get("direction") == "outbound" else "Prospect"
            history_text += f"{role}: {msg.get('body', '')}\n"
        history_text += "\n"
    
    # Format lead context (include enrichment if available)
    enrichment_context = ""
    if lead_data.get('enrichment'):
        enrichment_context = f"""
Company Context (from website):
- {lead_data['enrichment'].get('website_summary', 'N/A')}
- Key points: {', '.join(lead_data['enrichment'].get('personalization_bullets', [])[:3])}

"""
    
    lead_context = f"""Lead Information:
- Name: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
- Company: {lead_data.get('company_name', 'Unknown')}
- Industry: {lead_data.get('industry', 'Unknown')}

{enrichment_context}"""
    
    # Format few-shot examples
    examples_text = "Here are examples of how to classify and respond:\n\n"
    for i, example in enumerate(FEW_SHOT_EXAMPLES[:10], 1):  # Show first 10 examples
        examples_text += f"Example {i}:\n"
        examples_text += f"Prospect: \"{example['inbound']}\"\n"
        examples_text += f"Intent: {example['intent']}\n"
        examples_text += f"Confidence: {example['confidence']}\n"
        if example['escalate']:
            examples_text += f"Action: ESCALATE ({example['escalation_reason']})\n"
        else:
            examples_text += f"Response: \"{example['response']}\"\n"
        examples_text += "\n"
    
    # Build complete prompt
    prompt = f"""{SYSTEM_PROMPT}

{lead_context}

{history_text}

{examples_text}

Now classify this new message from the prospect:
Prospect: "{inbound_message}"

Return a JSON object with:
{{
  "intent": "INTERESTED|SCHEDULING|SIMPLE_QUESTION|FAQ|OBJECTION|COMPLEX_QUESTION|COMPLAINT|UNSUBSCRIBE|WRONG_PERSON|UNKNOWN",
  "confidence": 0.0-1.0,
  "escalate": true|false,
  "escalation_reason": "reason if escalate is true, empty if false",
  "response_text": "your response if not escalating, empty if escalating",
  "next_action": "propose_times|confirm_time|confirm_interest|offer_call|unsubscribe|escalate",
  "sentiment": "positive|neutral|negative"
}}

Remember:
- Escalate if confidence < 0.75
- Escalate for OBJECTION, COMPLEX_QUESTION, COMPLAINT
- Auto-handle UNSUBSCRIBE, WRONG_PERSON
- Keep responses to 2-3 sentences, conversational tone, no hype"""
    
    return prompt


def build_response_generation_prompt(
    inbound_message: str,
    intent: str,
    conversation_history: List[Dict],
    lead_data: Dict
) -> str:
    """
    Build prompt for generating a response (when classification says it's safe to auto-reply).
    
    Args:
        inbound_message: The message from the prospect
        intent: The classified intent
        conversation_history: Last 3-5 messages
        lead_data: Lead information
    
    Returns:
        Complete prompt string for GPT-4
    """
    # Format conversation history
    history_text = ""
    if conversation_history:
        history_text = "Conversation so far:\n"
        for msg in conversation_history[-5:]:
            role = "You" if msg.get("direction") == "outbound" else f"{lead_data.get('first_name', 'Prospect')}"
            history_text += f"{role}: {msg.get('body', '')}\n"
    
    prompt = f"""{SYSTEM_PROMPT}

Lead: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
Company: {lead_data.get('company_name', 'Unknown')}
Industry: {lead_data.get('industry', 'Unknown')}
Intent: {intent}
{enrichment_context}

{history_text}

Their latest message: "{inbound_message}"

Write a brief, natural response (2-3 sentences max) that:
1. Addresses their message
2. Moves toward scheduling the call
3. Follows the style guide (conversational, no hype, one question/CTA)
4. If enrichment context is available, use ONE subtle reference to show you know their business
5. Stays compliant (no guarantees, no specific advice)

Response:"""
    
    return prompt


# Compliance check keywords
COMPLIANCE_TRIGGERS = [
    "guarantee", "guaranteed", "promise", "assured", "risk-free", "no risk",
    "specific rate", "exact return", "will earn", "will grow",
    "medical advice", "tax advice", "legal advice",
    "diagnose", "treat", "cure"
]

ESCALATION_KEYWORDS = [
    "sue", "lawsuit", "lawyer", "attorney", "report", "complaint",
    "ftc", "sec", "attorney general", "fraud", "scam",
    "harass", "harassment", "threat", "police"
]

UNSUBSCRIBE_KEYWORDS = [
    "stop", "unsubscribe", "remove", "opt out", "opt-out",
    "don't contact", "do not contact", "take me off", "cease", "desist"
]
