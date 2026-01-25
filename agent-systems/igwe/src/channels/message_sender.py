"""
Unified message sender with variant selection and channel routing.
"""
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger

from ..storage.models import Conversation, Lead, MessageChannel
from ..storage.repositories import LeadRepository
from ..conversation.templates import MessageTemplates
from ..workflow.state_machine import ChannelRouter
from .email import SendGridService
from .sms import TwilioService


class MessageSender:
    """
    Unified message sender with template variant support.
    Handles opener/follow-up emails with randomized variants.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.templates = MessageTemplates(db)
        self.router = ChannelRouter(db)
        self.email_service = SendGridService(db)
        self.sms_service = TwilioService(db)
    
    def send_conversation_message(
        self,
        conversation: Conversation,
        stage: str
    ) -> dict:
        """
        Send message for conversation based on stage.
        
        Args:
            conversation: Conversation object
            stage: Template stage (opener_email, followup_1_email, followup_2_email, etc.)
        
        Returns:
            Dict with success status and details
        """
        lead = conversation.lead
        
        if not lead:
            logger.error(f"No lead found for conversation {conversation.id}")
            return {"success": False, "error": "No lead"}
        
        # Check if lead is suppressed
        if self.lead_repo.is_suppressed(lead):
            logger.warning(f"Lead {lead.id} is suppressed, skipping send")
            return {"success": False, "error": "Lead suppressed"}
        
        # Select channel
        channel = self.router.select_channel(lead, conversation)
        
        # Get enrichment if available
        enrichment = lead.enrichment if hasattr(lead, 'enrichment') else None
        
        # Render template with variant selection
        rendered, variant_id = self.templates.render_with_variant(
            stage,
            lead,
            conversation_id=conversation.id,
            enrichment=enrichment
        )
        
        logger.info(
            f"Sending {stage} (variant: {variant_id}) to lead {lead.id} "
            f"via {channel.value}"
        )
        
        # Route to appropriate channel
        if channel == MessageChannel.EMAIL:
            return self._send_email(
                lead,
                conversation,
                rendered,
                variant_id
            )
        
        elif channel == MessageChannel.SMS:
            return self._send_sms(
                lead,
                conversation,
                rendered,
                variant_id
            )
        
        else:
            logger.warning(f"Manual call required for conversation {conversation.id}")
            return {"success": False, "error": "Manual call required"}
    
    def _send_email(
        self,
        lead: Lead,
        conversation: Conversation,
        rendered: dict,
        variant_id: str
    ) -> dict:
        """Send email message"""
        if not lead.email:
            logger.error(f"Lead {lead.id} has no email")
            return {"success": False, "error": "No email"}
        
        result = self.email_service.send_email(
            to_email=lead.email,
            subject=rendered.get("subject", "Follow-up"),
            body=rendered["body"],
            lead_id=lead.id,
            conversation_id=conversation.id,
            metadata={"template_variant_id": variant_id}
        )
        
        # Update message record with variant_id if send was successful
        if result.get("success") and result.get("message_id"):
            try:
                from ..storage.models import Message
                message = self.db.query(Message).filter(
                    Message.id == result["message_id"]
                ).first()
                if message:
                    message.template_variant_id = variant_id
                    self.db.commit()
            except Exception as e:
                logger.warning(f"Could not update variant_id on message: {e}")
        
        return result
    
    def _send_sms(
        self,
        lead: Lead,
        conversation: Conversation,
        rendered: dict,
        variant_id: str
    ) -> dict:
        """Send SMS message"""
        if not lead.phone:
            logger.error(f"Lead {lead.id} has no phone")
            return {"success": False, "error": "No phone"}
        
        if not lead.consent_sms:
            logger.warning(f"Lead {lead.id} has no SMS consent")
            return {"success": False, "error": "No SMS consent"}
        
        result = self.sms_service.send_sms(
            to_number=lead.phone,
            body=rendered["body"],
            lead_id=lead.id,
            conversation_id=conversation.id,
            check_consent=True
        )
        
        # Update message record with variant_id if send was successful
        if result.get("success") and result.get("message_id"):
            try:
                from ..storage.models import Message
                message = self.db.query(Message).filter(
                    Message.id == result["message_id"]
                ).first()
                if message:
                    message.template_variant_id = variant_id
                    self.db.commit()
            except Exception as e:
                logger.warning(f"Could not update variant_id on message: {e}")
        
        return result
