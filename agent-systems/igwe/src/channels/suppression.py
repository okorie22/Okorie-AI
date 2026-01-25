"""
Suppression manager - handles bounces, complaints, and unsubscribes.
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from loguru import logger

from ..storage.models import Lead, Suppression, Conversation, ConversationState
from ..storage.repositories import LeadRepository, EventRepository


class SuppressionManager:
    """
    Manage email suppression list (bounces, complaints, unsubscribes).
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.event_repo = EventRepository(db)
    
    def suppress_lead(
        self,
        lead_id: int,
        reason: str,
        source: str = "manual",
        metadata: Optional[dict] = None
    ):
        """
        Mark lead as suppressed.
        
        Args:
            lead_id: Lead ID to suppress
            reason: Reason for suppression (bounce, complaint, unsubscribe, duplicate)
            source: Source of suppression (sendgrid_webhook, manual, cleanup)
            metadata: Additional context
        """
        lead = self.lead_repo.get_by_id(lead_id)
        
        if not lead:
            logger.error(f"Lead {lead_id} not found for suppression")
            return
        
        # Update lead
        lead.suppression_reason = reason
        lead.suppressed_at = datetime.utcnow()
        
        # Create suppression log
        suppression = Suppression(
            lead_id=lead_id,
            email=lead.email,
            reason=reason,
            source=source,
            metadata=metadata
        )
        self.db.add(suppression)
        
        # Close all active conversations
        self._close_active_conversations(lead_id, reason)
        
        self.db.commit()
        
        logger.info(f"Lead {lead_id} ({lead.email}) suppressed: {reason} (source: {source})")
        
        # Log event
        self.event_repo.log(
            event_type="lead_suppressed",
            lead_id=lead_id,
            payload={
                "reason": reason,
                "source": source,
                "email": lead.email
            }
        )
    
    def is_suppressed(self, lead_id: int) -> bool:
        """
        Check if lead is suppressed.
        
        Args:
            lead_id: Lead ID to check
        
        Returns:
            True if suppressed, False otherwise
        """
        lead = self.lead_repo.get_by_id(lead_id)
        return self.lead_repo.is_suppressed(lead) if lead else False
    
    def handle_sendgrid_event(self, event_type: str, email: str, metadata: Optional[dict] = None):
        """
        Handle bounce/complaint/spam events from SendGrid webhook.
        
        Args:
            event_type: SendGrid event type (bounce, dropped, spamreport, etc.)
            email: Email address
            metadata: Additional event data
        """
        # Find lead by email
        lead = self.lead_repo.find_by_email(email)
        
        if not lead:
            logger.warning(f"Lead not found for suppression event: {email}")
            return
        
        # Map SendGrid event types to suppression reasons
        suppression_events = {
            "bounce": "bounce",
            "dropped": "dropped",
            "spamreport": "complaint",
            "blocked": "blocked"
        }
        
        if event_type in suppression_events:
            reason = suppression_events[event_type]
            self.suppress_lead(
                lead.id,
                reason=reason,
                source="sendgrid_webhook",
                metadata=metadata
            )
    
    def handle_unsubscribe(self, email: str, source: str = "manual"):
        """
        Handle unsubscribe request.
        
        Args:
            email: Email address to unsubscribe
            source: Source of unsubscribe (manual, link, email_reply)
        """
        lead = self.lead_repo.find_by_email(email)
        
        if not lead:
            logger.warning(f"Lead not found for unsubscribe: {email}")
            return
        
        self.suppress_lead(
            lead.id,
            reason="unsubscribe",
            source=source
        )
    
    def get_suppression_history(self, lead_id: int) -> list:
        """
        Get suppression history for a lead.
        
        Args:
            lead_id: Lead ID
        
        Returns:
            List of Suppression records
        """
        return self.db.query(Suppression).filter(
            Suppression.lead_id == lead_id
        ).order_by(Suppression.created_at.desc()).all()
    
    def _close_active_conversations(self, lead_id: int, reason: str):
        """Close all active conversations for a suppressed lead"""
        active_conversations = self.db.query(Conversation).filter(
            Conversation.lead_id == lead_id,
            ~Conversation.state.in_([
                ConversationState.CLOSED_WON,
                ConversationState.CLOSED_LOST,
                ConversationState.STOPPED
            ])
        ).all()
        
        for conv in active_conversations:
            conv.state = ConversationState.STOPPED
            logger.info(f"Closed conversation {conv.id} due to lead suppression: {reason}")
