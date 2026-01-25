"""
Twilio SMS integration with consent checks and STOP handling.
"""
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from sqlalchemy.orm import Session
from typing import Dict, Optional
from loguru import logger
import os

from ..storage.models import Lead, Message, MessageDirection, MessageChannel, ConversationState
from ..storage.repositories import MessageRepository, EventRepository, ConversationRepository
from ..conversation.llm_agent import ComplianceGuardrails


class TwilioService:
    """Twilio SMS service with TCPA compliance"""
    
    def __init__(self, db: Session):
        self.db = db
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.client = Client(self.account_sid, self.auth_token) if self.account_sid and self.auth_token else None
        self.message_repo = MessageRepository(db)
        self.event_repo = EventRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.guardrails = ComplianceGuardrails()
    
    def send_sms(
        self,
        to_number: str,
        body: str,
        lead_id: int,
        conversation_id: int,
        check_consent: bool = True
    ) -> Dict:
        """
        Send SMS via Twilio with consent verification.
        """
        if not self.client:
            logger.error("Twilio not configured")
            return {"success": False, "error": "Twilio not configured"}
        
        # Verify SMS consent
        if check_consent:
            lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead or not lead.consent_sms:
                logger.error(f"Lead {lead_id} does not have SMS consent")
                return {"success": False, "error": "No SMS consent"}
        
        # Ensure STOP footer is included
        if "reply stop" not in body.lower():
            body += "\n\nReply STOP to unsubscribe."
        
        # Check compliance
        violations = self.guardrails.check_prohibited_content(body)
        if violations:
            logger.error(f"SMS contains prohibited content: {violations}")
            return {"success": False, "error": "Prohibited content"}
        
        # Check for TEST MODE
        from ..config import twilio_config
        if twilio_config.test_mode:
            logger.info(f"🧪 TEST MODE: Would send SMS to {to_number}")
            logger.info(f"   Body preview: {body[:200]}...")
            
            # Still log to database (for testing workflow)
            message_record = self.message_repo.create({
                "conversation_id": conversation_id,
                "direction": MessageDirection.OUTBOUND,
                "channel": MessageChannel.SMS,
                "body": body,
                "message_metadata": {
                    "to": to_number,
                    "twilio_sid": "TEST_MODE_SKIPPED",
                    "status": "test_mode",
                    "test_mode": True
                },
                "sent_at": None
            })
            
            # Log event
            self.event_repo.log(
                event_type="sms_sent_test_mode",
                lead_id=lead_id,
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_record.id,
                    "to": to_number,
                    "test_mode": True
                }
            )
            
            logger.info(f"✅ TEST MODE: SMS logged (not sent) to {to_number}")
            
            return {
                "success": True,
                "message_id": message_record.id,
                "twilio_sid": "TEST_MODE_SKIPPED",
                "test_mode": True
            }
        
        try:
            # Send SMS
            message = self.client.messages.create(
                body=body[:1600],  # SMS length limit
                from_=self.from_number,
                to=to_number
            )
            
            # Log message to database
            message_record = self.message_repo.create({
                "conversation_id": conversation_id,
                "direction": MessageDirection.OUTBOUND,
                "channel": MessageChannel.SMS,
                "body": body,
                "message_metadata": {
                    "to": to_number,
                    "twilio_sid": message.sid,
                    "status": message.status
                },
                "sent_at": message.date_created
            })
            
            # Log event
            self.event_repo.log(
                event_type="sms_sent",
                lead_id=lead_id,
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_record.id,
                    "to": to_number
                }
            )
            
            logger.info(f"SMS sent to {to_number}")
            
            return {
                "success": True,
                "message_id": message_record.id,
                "twilio_sid": message.sid
            }
        
        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS to {to_number}: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error sending SMS to {to_number}: {e}")
            return {"success": False, "error": str(e)}
    
    def handle_webhook(self, webhook_data: Dict) -> Dict:
        """
        Handle Twilio webhook for inbound SMS and status updates.
        """
        message_sid = webhook_data.get("MessageSid") or webhook_data.get("SmsSid")
        from_number = webhook_data.get("From")
        to_number = webhook_data.get("To")
        body = webhook_data.get("Body", "")
        sms_status = webhook_data.get("SmsStatus") or webhook_data.get("MessageStatus")
        
        logger.info(f"Received Twilio webhook from {from_number}: {sms_status}")
        
        # Handle inbound message
        if webhook_data.get("Direction") == "inbound" or not sms_status:
            return self._handle_inbound_sms(from_number, body)
        
        # Handle status update
        return self._handle_status_update(message_sid, sms_status)
    
    def _handle_inbound_sms(self, from_number: str, body: str) -> Dict:
        """Handle inbound SMS"""
        try:
            # Check for STOP command
            if self.guardrails.check_stop_intent(body):
                return self._handle_stop_command(from_number)
            
            # Check for START command
            if body.strip().lower() in ["start", "unstop", "yes"]:
                return self._handle_start_command(from_number)
            
            # Find lead by phone
            lead = self.db.query(Lead).filter(Lead.phone == from_number).first()
            
            if not lead:
                logger.warning(f"Lead not found for phone: {from_number}")
                return {"success": False, "error": "Lead not found"}
            
            # Find active conversation
            conversation = self.conv_repo.get_active_by_lead(lead.id)
            
            if not conversation:
                logger.warning(f"No active conversation for lead {lead.id}")
                return {"success": False, "error": "No active conversation"}
            
            # Log inbound message
            message = self.message_repo.create({
                "conversation_id": conversation.id,
                "direction": MessageDirection.INBOUND,
                "channel": MessageChannel.SMS,
                "body": body,
                "message_metadata": {"from": from_number}
            })
            
            # Update conversation
            from datetime import datetime
            conversation.last_message_at = datetime.utcnow()
            self.db.commit()
            
            # Log event
            self.event_repo.log(
                event_type="sms_received",
                lead_id=lead.id,
                payload={
                    "conversation_id": conversation.id,
                    "message_id": message.id,
                    "from": from_number
                }
            )
            
            # Trigger LLM classification
            from ..workflow.tasks import send_message_task
            send_message_task.delay(conversation.id, "auto_response")
            
            return {"success": True, "message_id": message.id}
        
        except Exception as e:
            logger.error(f"Error handling inbound SMS: {e}")
            return {"success": False, "error": str(e)}
    
    def _handle_stop_command(self, from_number: str) -> Dict:
        """Handle STOP command - opt out from SMS"""
        try:
            lead = self.db.query(Lead).filter(Lead.phone == from_number).first()
            
            if not lead:
                logger.warning(f"Lead not found for STOP command: {from_number}")
                return {"success": False, "error": "Lead not found"}
            
            # Update consent
            lead.consent_sms = False
            
            # Update active conversations to STOPPED
            active_convs = self.db.query.filter(
                Lead.id == lead.id
            ).join(Lead).filter(
                ~ConversationState.state.in_([
                    ConversationState.CLOSED_WON,
                    ConversationState.CLOSED_LOST,
                    ConversationState.STOPPED
                ])
            ).all()
            
            for conv in active_convs:
                conv.state = ConversationState.STOPPED
            
            self.db.commit()
            
            # Log event
            self.event_repo.log(
                event_type="sms_opt_out",
                lead_id=lead.id,
                payload={"phone": from_number}
            )
            
            logger.info(f"Lead {lead.id} opted out of SMS")
            
            # Send confirmation (required by TCPA)
            self.client.messages.create(
                body="You have been unsubscribed from SMS messages. Reply START to resubscribe.",
                from_=self.from_number,
                to=from_number
            )
            
            return {"success": True, "opted_out": True}
        
        except Exception as e:
            logger.error(f"Error handling STOP command: {e}")
            return {"success": False, "error": str(e)}
    
    def _handle_start_command(self, from_number: str) -> Dict:
        """Handle START command - opt back in to SMS"""
        try:
            lead = self.db.query(Lead).filter(Lead.phone == from_number).first()
            
            if not lead:
                logger.warning(f"Lead not found for START command: {from_number}")
                return {"success": False, "error": "Lead not found"}
            
            # Update consent
            lead.consent_sms = True
            self.db.commit()
            
            # Log event
            self.event_repo.log(
                event_type="sms_opt_in",
                lead_id=lead.id,
                payload={"phone": from_number}
            )
            
            logger.info(f"Lead {lead.id} opted back in to SMS")
            
            # Send confirmation
            self.client.messages.create(
                body="You have been resubscribed to SMS messages. Reply STOP to unsubscribe.",
                from_=self.from_number,
                to=from_number
            )
            
            return {"success": True, "opted_in": True}
        
        except Exception as e:
            logger.error(f"Error handling START command: {e}")
            return {"success": False, "error": str(e)}
    
    def _handle_status_update(self, message_sid: str, status: str) -> Dict:
        """Handle message status update"""
        try:
            # Find message by Twilio SID
            message = self.db.query(Message).filter(
                Message.message_metadata["twilio_sid"].astext == message_sid
            ).first()
            
            if not message:
                logger.warning(f"Message not found for SID: {message_sid}")
                return {"success": False, "error": "Message not found"}
            
            # Update status
            if not message.message_metadata:
                message.message_metadata = {}
            message.message_metadata["status"] = status
            
            if status == "delivered":
                from datetime import datetime
                message.delivered_at = datetime.utcnow()
            
            self.db.commit()
            
            return {"success": True, "message_id": message.id}
        
        except Exception as e:
            logger.error(f"Error handling status update: {e}")
            return {"success": False, "error": str(e)}
