"""
SendGrid email integration with reply webhook support.
"""
from datetime import datetime, timezone, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from sqlalchemy.orm import Session
from typing import Dict, Optional
from loguru import logger
import os

from ..storage.models import Lead, Message, MessageDirection, MessageChannel
from ..storage.repositories import MessageRepository, EventRepository


def _email_body_with_footer(body: str, from_name: str, signature_company: str, signature_style: str) -> str:
    """Append sender signature footer to body. Uses template_variants.EMAIL_SIGNATURE_OPTIONS."""
    from ..conversation.template_variants import EMAIL_SIGNATURE_OPTIONS, DEFAULT_EMAIL_SIGNATURE_FORMAT
    fmt = DEFAULT_EMAIL_SIGNATURE_FORMAT
    for opt in EMAIL_SIGNATURE_OPTIONS:
        if opt.get("id") == signature_style:
            fmt = opt["format"]
            break
    footer = fmt.format(sender_name=from_name or "", sender_company=signature_company or "")
    return (body or "").rstrip() + footer


class SendGridService:
    """SendGrid email service"""
    
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL", "appointments@example.com")
        self.from_name = os.getenv("SENDGRID_FROM_NAME", "Appointment Setter")
        self.client = SendGridAPIClient(self.api_key) if self.api_key else None
        self.message_repo = MessageRepository(db)
        self.event_repo = EventRepository(db)
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        lead_id: int,
        conversation_id: int,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Send email via SendGrid with rate limiting and suppression checks.
        """
        if not self.client:
            logger.error("SendGrid API key not configured")
            return {"success": False, "error": "SendGrid not configured"}
        
        # Check if lead is suppressed
        lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            logger.error(f"Lead {lead_id} not found")
            return {"success": False, "error": "Lead not found"}
        
        if lead.suppression_reason:
            logger.warning(f"Skipping suppressed lead {lead_id}: {lead.suppression_reason}")
            return {"success": False, "error": "Lead suppressed"}
        
        if lead.email_deliverable is not True:
            logger.warning(f"Skipping lead {lead_id}: email not deliverable (status={lead.email_verification_status})")
            return {"success": False, "error": "Email not deliverable"}
        # Only send if verified within last 30 days (stale = re-verify first)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        if not lead.email_verified_at or lead.email_verified_at < cutoff:
            logger.warning(f"Skipping lead {lead_id}: email verification stale or missing (run re-verify job)")
            return {"success": False, "error": "Email verification expired"}
        
        # Check rate limits
        from .rate_limiter import SendRateLimiter
        rate_limiter = SendRateLimiter(self.db)
        
        if not rate_limiter.can_send_batch(1):
            logger.warning("Rate limit exceeded, deferring send")
            return {"success": False, "error": "Rate limited"}
        
        if not rate_limiter.is_within_send_window():
            logger.debug("Outside send window")
            return {"success": False, "error": "Outside window"}
        
        from ..config import sendgrid_config
        body_with_footer = _email_body_with_footer(
            body, self.from_name, sendgrid_config.signature_company, sendgrid_config.signature_style
        )
        sent_at_utc = datetime.now(timezone.utc)
        # Check for TEST MODE
        if sendgrid_config.test_mode:
            logger.info(f"🧪 TEST MODE: Would send email to {to_email}")
            logger.info(f"   Subject: {subject}")
            logger.info(f"   Body preview: {body_with_footer[:200]}...")
            
            # Still log to database (for testing workflow)
            message_record = self.message_repo.create({
                "conversation_id": conversation_id,
                "direction": MessageDirection.OUTBOUND,
                "channel": MessageChannel.EMAIL,
                "body": body_with_footer,
                "message_metadata": {
                    "subject": subject,
                    "to": to_email,
                    "sendgrid_id": "TEST_MODE_SKIPPED",
                    "test_mode": True,
                    **(metadata or {})
                },
                "sent_at": sent_at_utc,
            })
            
            # Log event
            self.event_repo.log(
                event_type="email_sent_test_mode",
                lead_id=lead_id,
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_record.id,
                    "subject": subject,
                    "to": to_email,
                    "test_mode": True
                }
            )
            
            logger.info(f"✅ TEST MODE: Email logged (not sent) to {to_email}")
            
            return {
                "success": True,
                "message_id": message_record.id,
                "sendgrid_id": "TEST_MODE_SKIPPED",
                "test_mode": True
            }
        
        try:
            # Create email (body includes footer)
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", body_with_footer)
            )
            if sendgrid_config.reply_to:
                message.reply_to = sendgrid_config.reply_to
            # Send via SendGrid
            response = self.client.send(message)

            # Log message to database; sent_at set here; delivered_at set by SendGrid webhook when event=delivered
            # SendGrid X-Message-Id is short; webhook sg_message_id is long (prefix = X-Message-Id). Store stripped.
            raw_xmid = (response.headers.get("X-Message-Id") or "").strip()
            message_record = self.message_repo.create({
                "conversation_id": conversation_id,
                "direction": MessageDirection.OUTBOUND,
                "channel": MessageChannel.EMAIL,
                "body": body_with_footer,
                "message_metadata": {
                    "subject": subject,
                    "to": to_email,
                    "sendgrid_id": raw_xmid or None,
                    **(metadata or {})
                },
                "sent_at": sent_at_utc,
            })
            
            # Log event
            self.event_repo.log(
                event_type="email_sent",
                lead_id=lead_id,
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_record.id,
                    "subject": subject,
                    "to": to_email
                }
            )
            
            logger.info(f"Email sent to {to_email}: {subject}")
            
            return {
                "success": True,
                "message_id": message_record.id,
                "sendgrid_id": response.headers.get("X-Message-Id")
            }
        
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return {"success": False, "error": str(e)}
    
    def send(self, to_email: str, subject: str, body: str, lead_id: int, conversation_id: int, metadata: Optional[Dict] = None) -> Dict:
        """Alias for send_email so callers can use .send()."""
        return self.send_email(to_email, subject, body, lead_id, conversation_id, metadata)
    
    def handle_webhook(self, webhook_data: Dict) -> Dict:
        """
        Handle SendGrid webhook events (delivery, open, click, reply).
        """
        event_type = webhook_data.get("event")
        sendgrid_id = (webhook_data.get("sg_message_id") or "").strip()
        
        logger.info(f"Received SendGrid webhook: {event_type} for {sendgrid_id}")
        
        try:
            # Find message by SendGrid ID. X-Message-Id (stored) is short; webhook sg_message_id is long (stored is prefix).
            message = None
            if sendgrid_id:
                # Try DB exact match first (JSONB)
                try:
                    message = self.db.query(Message).filter(
                        Message.direction == MessageDirection.OUTBOUND,
                        Message.channel == MessageChannel.EMAIL,
                        Message.message_metadata["sendgrid_id"].astext == sendgrid_id
                    ).first()
                except Exception:
                    message = None
                # Fallback: compare in Python (webhook id often has suffix; stored id is prefix)
                if not message:
                    candidates = self.db.query(Message).filter(
                        Message.direction == MessageDirection.OUTBOUND,
                        Message.channel == MessageChannel.EMAIL,
                        Message.message_metadata.isnot(None)
                    ).order_by(Message.id.desc()).limit(500).all()
                    for m in candidates:
                        stored = (m.message_metadata or {}).get("sendgrid_id")
                        if isinstance(stored, str):
                            stored = stored.strip()
                            if sendgrid_id == stored or sendgrid_id.startswith(stored) or stored.startswith(sendgrid_id):
                                message = m
                                break
            if not message:
                logger.warning(f"Message not found for SendGrid ID: {sendgrid_id} (event={event_type})")
                return {"success": False, "error": "Message not found", "sg_message_id": sendgrid_id}
            
            # Parse timestamp (SendGrid sends Unix epoch or ISO string); store as UTC datetime
            def _parse_ts(ts) -> Optional[datetime]:
                if ts is None:
                    return None
                if isinstance(ts, (int, float)):
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                if isinstance(ts, str):
                    try:
                        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    except ValueError:
                        pass
                    try:
                        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        return None
                return ts

            ts = _parse_ts(webhook_data.get("timestamp"))
            if event_type == "delivered":
                message.delivered_at = ts
            elif event_type == "open":
                message.read_at = ts
            elif event_type == "click":
                # Update metadata with click info
                if not message.message_metadata:
                    message.message_metadata = {}
                message.message_metadata["clicked"] = True
                message.message_metadata["click_url"] = webhook_data.get("url")
            
            self.db.commit()
            
            return {"success": True, "message_id": message.id}
        
        except Exception as e:
            logger.error(f"Error handling SendGrid webhook: {e}")
            return {"success": False, "error": str(e)}
    
    def handle_inbound_email(self, email_data: Dict) -> Dict:
        """
        Handle inbound email reply (via SendGrid Inbound Parse).
        """
        from_email = email_data.get("from")
        body = email_data.get("text") or email_data.get("html", "")
        subject = email_data.get("subject", "")
        
        logger.info(f"Received inbound email from {from_email}")
        
        try:
            # Find lead by email
            lead = self.db.query(Lead).filter(Lead.email == from_email).first()
            
            if not lead:
                logger.warning(f"Lead not found for email: {from_email}")
                return {"success": False, "error": "Lead not found"}
            
            # Find active conversation
            from ..storage.repositories import ConversationRepository
            conv_repo = ConversationRepository(self.db)
            conversation = conv_repo.get_active_by_lead(lead.id)
            
            if not conversation:
                logger.warning(f"No active conversation for lead {lead.id}")
                return {"success": False, "error": "No active conversation"}
            
            # Log inbound message
            message = self.message_repo.create({
                "conversation_id": conversation.id,
                "direction": MessageDirection.INBOUND,
                "channel": MessageChannel.EMAIL,
                "body": body[:5000],  # Limit body length
                "message_metadata": {"subject": subject, "from": from_email},
                "sent_at": None,
                "delivered_at": None,
                "read_at": None
            })
            
            # Update conversation
            from datetime import datetime
            conversation.last_message_at = datetime.utcnow()
            self.db.commit()
            
            # Log event
            self.event_repo.log(
                event_type="email_received",
                lead_id=lead.id,
                payload={
                    "conversation_id": conversation.id,
                    "message_id": message.id,
                    "from": from_email
                }
            )
            
            # Trigger LLM classification (async task)
            from ..workflow.tasks import send_message_task
            send_message_task.delay(conversation.id, "auto_response")
            
            return {"success": True, "message_id": message.id}
        
        except Exception as e:
            logger.error(f"Error handling inbound email: {e}")
            return {"success": False, "error": str(e)}
