"""
Conversation state machine - manages state transitions and routing logic.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from loguru import logger

from ..storage.models import (
    Conversation, ConversationState, MessageChannel,
    Lead, LeadScore
)
from ..storage.repositories import ConversationRepository, EventRepository


# State transition rules
STATE_TRANSITIONS = {
    ConversationState.NEW: [
        ConversationState.CONTACTED,
        ConversationState.STOPPED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.CONTACTED: [
        ConversationState.ENGAGED,
        ConversationState.NO_RESPONSE,
        ConversationState.STOPPED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.ENGAGED: [
        ConversationState.QUALIFIED,
        ConversationState.NOT_INTERESTED,
        ConversationState.STOPPED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.QUALIFIED: [
        ConversationState.SCHEDULED,
        ConversationState.NOT_INTERESTED,
        ConversationState.STOPPED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.SCHEDULED: [
        ConversationState.CONFIRMED,
        ConversationState.RESCHEDULED,
        ConversationState.CANCELLED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.CONFIRMED: [
        ConversationState.REMINDED_24H,
        ConversationState.RESCHEDULED,
        ConversationState.CANCELLED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.REMINDED_24H: [
        ConversationState.REMINDED_2H,
        ConversationState.RESCHEDULED,
        ConversationState.CANCELLED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.REMINDED_2H: [
        ConversationState.SHOWED,
        ConversationState.NO_SHOW,
        ConversationState.RESCHEDULED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.SHOWED: [
        ConversationState.CLOSED_WON,
        ConversationState.CLOSED_LOST,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.RESCHEDULED: [
        ConversationState.SCHEDULED,
        ConversationState.CANCELLED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    ConversationState.NO_RESPONSE: [
        ConversationState.CONTACTED,
        ConversationState.NOT_INTERESTED,
        ConversationState.NEEDS_HUMAN_REVIEW
    ],
    # New states for human escalation
    ConversationState.NEEDS_HUMAN_REVIEW: [
        ConversationState.HUMAN_HANDLING,
        ConversationState.STOPPED,
        ConversationState.NOT_INTERESTED
    ],
    ConversationState.HUMAN_HANDLING: [
        # Human can transition to any appropriate state
        ConversationState.ENGAGED,
        ConversationState.QUALIFIED,
        ConversationState.SCHEDULED,
        ConversationState.CONTACTED,
        ConversationState.NOT_INTERESTED,
        ConversationState.STOPPED,
        ConversationState.NEEDS_HUMAN_REVIEW  # Can escalate again if needed
    ],
}

# Outbound message stage per conversation state (new, contacted, no_response)
STATE_TO_MESSAGE_STAGE = {
    ConversationState.NEW: "opener_email",
    ConversationState.CONTACTED: "followup_1_email",
    ConversationState.NO_RESPONSE: "followup_2_email",
}


# Terminal states (no further transitions)
TERMINAL_STATES = [
    ConversationState.CLOSED_WON,
    ConversationState.CLOSED_LOST,
    ConversationState.STOPPED,
    ConversationState.NOT_INTERESTED,
    ConversationState.CANCELLED
]


class StateMachine:
    """Manages conversation state transitions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.event_repo = EventRepository(db)
    
    def can_transition(self, current_state: ConversationState, new_state: ConversationState) -> bool:
        """Check if transition is valid"""
        if current_state in TERMINAL_STATES:
            logger.warning(f"Cannot transition from terminal state: {current_state}")
            return False
        
        allowed_states = STATE_TRANSITIONS.get(current_state, [])
        return new_state in allowed_states
    
    def transition(
        self,
        conversation: Conversation,
        new_state: ConversationState,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Transition conversation to new state.
        Returns True if successful, False otherwise.
        """
        if not self.can_transition(conversation.state, new_state):
            logger.error(
                f"Invalid transition: {conversation.state} -> {new_state} "
                f"for conversation {conversation.id}"
            )
            return False
        
        old_state = conversation.state
        conversation.state = new_state
        conversation.updated_at = datetime.utcnow()
        
        # Update next_action_at based on new state
        conversation.next_action_at = self._calculate_next_action(conversation, new_state)
        
        self.db.commit()
        self.db.refresh(conversation)
        
        # Log state change
        self.event_repo.log(
            event_type="state_transition",
            lead_id=conversation.lead_id,
            payload={
                "conversation_id": conversation.id,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "metadata": metadata or {}
            }
        )
        
        logger.info(
            f"Conversation {conversation.id} transitioned: "
            f"{old_state.value} -> {new_state.value}"
        )
        
        return True
    
    def _calculate_next_action(self, conversation: Conversation, state: ConversationState) -> Optional[datetime]:
        """
        Calculate when the next action should occur based on state.
        """
        now = datetime.utcnow()
        
        # Follow-up timing based on state
        if state == ConversationState.CONTACTED:
            # First follow-up after 24 hours
            return now + timedelta(hours=24)
        
        elif state == ConversationState.NO_RESPONSE:
            # Second follow-up after 48 hours
            return now + timedelta(hours=48)
        
        elif state == ConversationState.ENGAGED:
            # Quick follow-up for engaged leads
            return now + timedelta(hours=12)
        
        elif state == ConversationState.QUALIFIED:
            # Prompt scheduling offer
            return now + timedelta(hours=4)
        
        elif state in TERMINAL_STATES:
            # No further action needed
            return None
        
        else:
            # Default: check back in 24 hours
            return now + timedelta(hours=24)


class ChannelRouter:
    """Routes messages to appropriate channels based on lead attributes"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def select_channel(self, lead: Lead, conversation: Conversation) -> MessageChannel:
        """
        Select the best channel for outreach based on:
        - Lead consent
        - Tier priority
        - Response history
        """
        # Check SMS consent
        has_sms_consent = lead.consent_sms
        has_email_consent = lead.consent_email
        
        # Get lead tier
        tier = 5  # Default
        if lead.score:
            tier = lead.score.tier
        
        # Check if we've had responses on email
        email_responses = self.db.query(Conversation).join(Lead).filter(
            Lead.email == lead.email,
            Conversation.state.in_([
                ConversationState.ENGAGED,
                ConversationState.QUALIFIED,
                ConversationState.SCHEDULED
            ])
        ).count()
        
        # Routing logic
        if conversation.state == ConversationState.NEW:
            # First contact: use email (safer, more professional)
            if has_email_consent or lead.email:
                return MessageChannel.EMAIL
            elif has_sms_consent and lead.phone:
                return MessageChannel.SMS
            else:
                return MessageChannel.MANUAL_CALL
        
        elif conversation.state in [ConversationState.ENGAGED, ConversationState.QUALIFIED]:
            # Engaged leads: prefer SMS if consented (faster response)
            if has_sms_consent and lead.phone and tier <= 2:
                return MessageChannel.SMS
            elif lead.email:
                return MessageChannel.EMAIL
            else:
                return MessageChannel.MANUAL_CALL
        
        elif email_responses == 0 and has_sms_consent and lead.phone:
            # No email response but have SMS consent: try SMS
            return MessageChannel.SMS
        
        else:
            # Default to email
            if lead.email:
                return MessageChannel.EMAIL
            elif has_sms_consent and lead.phone:
                return MessageChannel.SMS
            else:
                return MessageChannel.MANUAL_CALL
    
    def should_escalate_to_manual(self, conversation: Conversation) -> bool:
        """
        Determine if conversation should be escalated to manual handling.
        """
        # Count automated follow-ups
        from ..storage.models import Message, MessageDirection
        
        automated_messages = self.db.query(Message).filter(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.OUTBOUND
        ).count()
        
        # Escalate after 3 automated attempts with no engagement
        if automated_messages >= 3 and conversation.state == ConversationState.NO_RESPONSE:
            return True
        
        # High-tier leads get manual attention
        if conversation.lead.score and conversation.lead.score.tier == 1:
            if conversation.state == ConversationState.CONTACTED:
                # Tier 1 leads: escalate after first message if no response in 48h
                time_since_last = datetime.utcnow() - (conversation.last_message_at or conversation.created_at)
                if time_since_last > timedelta(hours=48):
                    return True
        
        return False


class WorkflowEngine:
    """Orchestrates the conversation workflow"""
    
    def __init__(self, db: Session):
        self.db = db
        self.state_machine = StateMachine(db)
        self.router = ChannelRouter(db)
        self.conv_repo = ConversationRepository(db)
        self.event_repo = EventRepository(db)
    
    def start_conversation(self, lead: Lead) -> Conversation:
        """
        Start a new conversation for a lead.
        """
        # Check if active conversation exists
        existing = self.conv_repo.get_active_by_lead(lead.id)
        if existing:
            logger.info(f"Active conversation already exists for lead {lead.id}")
            return existing
        
        # Select initial channel
        temp_conv = Conversation(lead_id=lead.id, state=ConversationState.NEW)
        temp_conv.lead = lead  # Set relationship for router
        channel = self.router.select_channel(lead, temp_conv)
        
        # Create conversation
        conversation = self.conv_repo.create(lead.id, channel.value)
        
        # Set next action (immediate outreach)
        conversation.next_action_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Started conversation {conversation.id} for lead {lead.id} on channel {channel.value}")
        
        return conversation
    
    def process_pending_actions(self, limit: Optional[int] = None) -> Dict:
        """
        Process conversations with pending actions (next_action_at <= now).
        
        Args:
            limit: Optional limit on number of conversations to process per batch
        
        Returns:
            Dict with processing stats
        """
        # Only process conversations in states that need outbound messages
        states_filter = [
            ConversationState.NEW,
            ConversationState.CONTACTED,
            ConversationState.NO_RESPONSE
        ]
        
        pending = self.conv_repo.get_pending_actions(limit=limit, states_filter=states_filter)
        logger.info(f"Processing {len(pending)} pending actions (limit: {limit}, states: {[s.value for s in states_filter]})")
        
        processed = 0
        errors = 0
        
        for conversation in pending:
            try:
                self._process_conversation_action(conversation)
                processed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error processing conversation {conversation.id}: {e}")
        
        return {"processed": processed, "errors": errors}
    
    def _process_conversation_action(self, conversation: Conversation):
        """
        Process a single conversation action based on current state.
        """
        logger.info(f"Processing action for conversation {conversation.id} in state {conversation.state.value}")
        
        # Check if should escalate to manual
        if self.router.should_escalate_to_manual(conversation):
            logger.info(f"Escalating conversation {conversation.id} to manual handling")
            conversation.channel = MessageChannel.MANUAL_CALL
            conversation.next_action_at = None  # Wait for manual action
            self.db.commit()
            
            self.event_repo.log(
                event_type="escalated_to_manual",
                lead_id=conversation.lead_id,
                payload={"conversation_id": conversation.id}
            )
            return
        
        # State-specific actions - send messages based on state
        stage = STATE_TO_MESSAGE_STAGE.get(conversation.state)
        if not stage:
            logger.warning(f"No message stage for state {conversation.state}")
            return
        
        from ..channels.message_sender import MessageSender
        sender = MessageSender(self.db)
        
        logger.info(f"Sending {stage} for conversation {conversation.id}")
        result = sender.send_conversation_message(conversation, stage)
        
        if conversation.state == ConversationState.NEW and result.get("success"):
            self.state_machine.transition(conversation, ConversationState.CONTACTED)
        elif conversation.state == ConversationState.CONTACTED and result.get("success"):
            self.state_machine.transition(conversation, ConversationState.NO_RESPONSE)
        elif conversation.state == ConversationState.NO_RESPONSE and not result.get("success"):
            logger.error(f"Failed to send follow-up 2: {result.get('error')}")
        # NO_RESPONSE: no auto-transition after success; wait for reply or manual close
