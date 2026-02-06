"""
Repository pattern for database operations.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from .models import (
    Lead, LeadScore, LeadEnrichment, Conversation, Message,
    Appointment, Event, ConversationState, MessageDirection
)


class LeadRepository:
    """Repository for Lead operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, lead_data: dict) -> Lead:
        """Create a new lead"""
        lead = Lead(**lead_data)
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead
    
    def get_by_id(self, lead_id: int) -> Optional[Lead]:
        """Get lead by ID"""
        return self.db.query(Lead).filter(Lead.id == lead_id).first()
    
    def get_by_email(self, email: str) -> Optional[Lead]:
        """Get lead by email (case-insensitive)"""
        if not email:
            return None
        email_normalized = email.strip().lower()
        return self.db.query(Lead).filter(func.lower(Lead.email) == email_normalized).first()
    
    def find_by_email(self, email: str) -> Optional[Lead]:
        """Find lead by email (alias for get_by_email, for consistency)"""
        return self.get_by_email(email)
    
    def find_by_phone(self, phone: str) -> Optional[Lead]:
        """Find lead by phone"""
        return self.db.query(Lead).filter(Lead.phone == phone).first()
    
    def is_suppressed(self, lead: Lead) -> bool:
        """Check if lead is suppressed (bounce/complaint/unsubscribe)"""
        return lead.suppression_reason is not None
    
    def find_duplicate(self, first_name: str, last_name: str, email: str) -> Optional[Lead]:
        """Find potential duplicate lead (legacy method - use find_by_email or find_by_phone)"""
        return self.db.query(Lead).filter(
            Lead.first_name == first_name,
            Lead.last_name == last_name,
            Lead.email == email
        ).first()
    
    def list_all(self, skip: int = 0, limit: int = 100) -> List[Lead]:
        """List all leads with pagination"""
        return self.db.query(Lead).offset(skip).limit(limit).all()
    
    def update(self, lead_id: int, updates: dict) -> Optional[Lead]:
        """Update lead"""
        lead = self.get_by_id(lead_id)
        if lead:
            for key, value in updates.items():
                setattr(lead, key, value)
            self.db.commit()
            self.db.refresh(lead)
        return lead


class ConversationRepository:
    """Repository for Conversation operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, lead_id: int, channel: str) -> Conversation:
        """Create a new conversation"""
        conversation = Conversation(lead_id=lead_id, channel=channel)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    def get_by_id(self, conversation_id: int) -> Optional[Conversation]:
        """Get conversation by ID"""
        return self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
    
    def get_active_by_lead(self, lead_id: int) -> Optional[Conversation]:
        """Get active conversation for a lead"""
        return self.db.query(Conversation).filter(
            Conversation.lead_id == lead_id,
            Conversation.state.notin_([
                ConversationState.CLOSED_WON,
                ConversationState.CLOSED_LOST,
                ConversationState.STOPPED
            ])
        ).first()
    
    def update_state(self, conversation_id: int, new_state: ConversationState) -> Optional[Conversation]:
        """Update conversation state"""
        conversation = self.get_by_id(conversation_id)
        if conversation:
            conversation.state = new_state
            conversation.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(conversation)
        return conversation
    
    def get_pending_actions(self, limit: Optional[int] = None, states_filter: Optional[List[ConversationState]] = None) -> List[Conversation]:
        """
        Get conversations with pending actions (next_action_at <= now).
        
        Args:
            limit: Optional limit on number of conversations to return
            states_filter: Optional list of conversation states to filter by
        
        Returns:
            List of conversations
        """
        query = self.db.query(Conversation).filter(
            Conversation.next_action_at <= datetime.utcnow()
        )
        
        # Filter by states if provided
        if states_filter:
            query = query.filter(Conversation.state.in_(states_filter))
        
        # Order by next_action_at (oldest first)
        query = query.order_by(Conversation.next_action_at.asc())
        
        # Apply limit if provided
        if limit:
            query = query.limit(limit)
        
        return query.all()


class MessageRepository:
    """Repository for Message operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, message_data: dict) -> Message:
        """Create a new message"""
        message = Message(**message_data)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
    
    def get_conversation_history(self, conversation_id: int) -> List[Message]:
        """Get all messages for a conversation"""
        return self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()
    
    def mark_delivered(self, message_id: int) -> Optional[Message]:
        """Mark message as delivered"""
        message = self.db.query(Message).filter(Message.id == message_id).first()
        if message:
            message.delivered_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(message)
        return message


class EventRepository:
    """Repository for Event logging"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log(self, event_type: str, lead_id: Optional[int], payload: dict) -> Event:
        """Log an event"""
        event = Event(
            event_type=event_type,
            lead_id=lead_id,
            payload=payload
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def get_lead_events(self, lead_id: int) -> List[Event]:
        """Get all events for a lead"""
        return self.db.query(Event).filter(
            Event.lead_id == lead_id
        ).order_by(Event.created_at.desc()).all()
