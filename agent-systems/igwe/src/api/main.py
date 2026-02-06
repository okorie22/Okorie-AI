"""
FastAPI main application - webhooks and admin endpoints.
"""
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Optional
from loguru import logger
import os
import random

from ..storage.database import get_db
from ..channels.email import SendGridService
from ..channels.sms import TwilioService
from ..scheduling.calendly import CalendlyService
from .analytics import router as analytics_router
from .analytics_simple import router as analytics_simple_router
from .dashboard import router as dashboard_router
from .appointments_dashboard import router as appointments_router
from .messages_dashboard import router as messages_router

# Create FastAPI app
app = FastAPI(
    title="IUL Appointment Setter API",
    description="Automated appointment setter for IUL insurance",
    version="1.0.0"
)

# Include routers
app.include_router(analytics_router)
app.include_router(analytics_simple_router)
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(appointments_router)
app.include_router(messages_router)


@app.on_event("startup")
def ensure_db_tables():
    """Create tables if missing (e.g. Render Postgres)."""
    from ..storage import models  # noqa: F401  # register models with Base
    from ..storage.database import init_db
    init_db()


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "IUL Appointment Setter"}


def _log_webhook_to_file(event: dict, result: Optional[dict] = None) -> None:
    """Append one SendGrid webhook event to logs/sendgrid_webhook.log for debugging on VM."""
    try:
        import os
        from datetime import datetime, timezone
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "sendgrid_webhook.log")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ev = event.get("event") or ""
        mid = event.get("sg_message_id") or ""
        email = event.get("email") or ""
        ok = (result or {}).get("success", False)
        line = f"{ts}\t{ev}\tsg_message_id={mid}\temail={email}\tsuccess={ok}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # do not fail webhook on log write


# SendGrid webhooks
@app.post("/webhooks/sendgrid")
async def sendgrid_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle SendGrid webhook events including bounces, complaints, and delivery"""
    try:
        data = await request.json()
        service = SendGridService(db)
        
        # Import suppression manager
        from ..channels.suppression import SuppressionManager
        suppression_manager = SuppressionManager(db)
        
        # SendGrid sends array of events
        if isinstance(data, list):
            results = []
            for event in data:
                result = service.handle_webhook(event)
                _log_webhook_to_file(event, result)
                results.append(result)
                
                # Check for suppression events (bounce, complaint, spam)
                event_type = event.get("event")
                email = event.get("email")
                
                if event_type in ["bounce", "dropped", "spamreport", "blocked"]:
                    suppression_manager.handle_sendgrid_event(
                        event_type,
                        email,
                        metadata={
                            "reason": event.get("reason"),
                            "status": event.get("status"),
                            "sg_event_id": event.get("sg_event_id")
                        }
                    )
            
            return {"success": True, "processed": len(results)}
        else:
            # Single event
            result = service.handle_webhook(data)
            _log_webhook_to_file(data, result)
            
            # Check for suppression
            event_type = data.get("event")
            email = data.get("email")
            
            if event_type in ["bounce", "dropped", "spamreport", "blocked"]:
                suppression_manager.handle_sendgrid_event(event_type, email, metadata=data)
            
            return result
    
    except Exception as e:
        logger.error(f"Error processing SendGrid webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _should_append_booking_link(intent_value: str, response_text: Optional[str]) -> bool:
    """Append Calendly link only when the reply explicitly invites them to pick a time (close-now), not on value-first replies."""
    if not response_text:
        return False
    r = response_text.lower()
    invite_phrases = (
        "pick a time", "choose a slot", "pick a slot", "grab a slot",
        "when's a good time", "when's good for you", "what time works",
        "book a time", "choose a time", "pick a time here", "grab a time",
    )
    if any(phrase in r for phrase in invite_phrases):
        return True
    if intent_value == "scheduling":
        return True
    return False


@app.post("/webhooks/sendgrid/inbound")
@app.post("/webhooks/sendgrid/inbound/")
async def sendgrid_inbound(request: Request, db: Session = Depends(get_db)):
    """Handle inbound email replies via SendGrid Inbound Parse with AI reply agent"""
    try:
        form_data = await request.form()
        from_raw = form_data.get("from") or ""
        inbound_text = form_data.get("text", "")
        
        # Extract a real email address from SendGrid "from" (often "Name <email@x.com>")
        from email.utils import parseaddr
        import re
        _, parsed = parseaddr(from_raw)
        from_email = (parsed or from_raw or "").strip()
        # Last-resort: regex extract between <>
        m = re.search(r"<([^>]+)>", from_email)
        if m:
            from_email = (m.group(1) or "").strip()
        from_email = from_email.strip().lower()
        
        logger.info(f"Inbound email from: {from_email}")
        
        # Extract Message-ID for deduplication
        headers_raw = form_data.get("headers", "")
        message_id = None
        for line in headers_raw.split("\n"):
            if line.lower().startswith("message-id:"):
                message_id = line.split(":", 1)[1].strip()
                break
        if not message_id:
            # Generate fallback ID from email + subject + timestamp
            from datetime import datetime
            ts = int(datetime.utcnow().timestamp())
            subject = form_data.get("subject", "")
            message_id = f"generated-{from_email}-{subject}-{ts}"
        
        logger.info(f"Message-ID: {message_id}")
        
        # Find lead by email
        from ..storage.repositories import LeadRepository, ConversationRepository, MessageRepository
        lead_repo = LeadRepository(db)
        conv_repo = ConversationRepository(db)
        msg_repo = MessageRepository(db)
        
        # Check for duplicate - temporarily disabled due to JSONB query issues
        # existing_msg = msg_repo.get_by_metadata_field("message_id", message_id)
        # if existing_msg:
        #     logger.info(f"Duplicate inbound detected (Message-ID: {message_id}), skipping")
        #     return {"success": True, "message": "Already processed (duplicate)"}
        
        lead = lead_repo.get_by_email(from_email)
        if not lead:
            # Create a real lead for first-time senders so they become "known" immediately.
            logger.warning(f"Inbound email from new sender (creating lead): {from_email}")
            from ..storage.models import MessageDirection, MessageChannel
            if from_email and "@" in from_email:
                local = from_email.split("@")[0].replace(".", " ").replace("_", " ").strip()
                first = (local.split(" ")[0].capitalize() if local else "Unknown")
                lead = lead_repo.create({
                    "email": from_email,
                    "first_name": first,
                    "last_name": "",
                })
            else:
                # Fallback bucket if email is missing/invalid
                _UNKNOWN_SENDER_EMAIL = "inbound-unknown@system"
                lead = lead_repo.get_by_email(_UNKNOWN_SENDER_EMAIL)
                if not lead:
                    lead = lead_repo.create({
                        "email": _UNKNOWN_SENDER_EMAIL,
                        "first_name": "Unknown",
                        "last_name": "Inbound",
                    })

            conv = conv_repo.get_active_by_lead(lead.id)
            if not conv:
                conv = conv_repo.create(lead.id, MessageChannel.EMAIL.value)
            inbound_html = form_data.get("html") or ""
            msg_repo.create({
                "conversation_id": conv.id,
                "direction": MessageDirection.INBOUND,
                "channel": MessageChannel.EMAIL,
                "body": inbound_text or inbound_html or "",
                "message_metadata": {
                    "from": from_raw or from_email,
                    "subject": form_data.get("subject"),
                    "to": form_data.get("to"),
                    "html": inbound_html,
                    "message_id": message_id,
                },
            })
            
            # Send notification for first-time sender too
            from ..channels.notifications import NotificationService
            from ..config import settings, llm_config
            try:
                notification_service = NotificationService(db, settings)
                if llm_config.human_notification_email:
                    notification_service.send_inbound_notification(
                        lead=lead,
                        inbound_message=inbound_text or inbound_html or "",
                        subject=form_data.get("subject", ""),
                        conversation_id=conv.id
                    )
            except Exception as e:
                logger.warning(f"Failed to send new sender notification: {e}")
            
            # DON'T return early - let new leads continue to ReplyAgent logic below
        
        # Find or create conversation (repository API: get_active_by_lead / create(lead_id, channel))
        from ..storage.models import MessageChannel
        conversation = conv_repo.get_active_by_lead(lead.id)
        if not conversation:
            logger.info(f"Creating new conversation for lead {lead.id}")
            conversation = conv_repo.create(lead.id, MessageChannel.EMAIL.value)
        
        # Save inbound message
        from ..storage.models import MessageDirection, MessageChannel
        msg_repo.create({
            "conversation_id": conversation.id,
            "direction": MessageDirection.INBOUND,
            "channel": MessageChannel.EMAIL,
            "body": inbound_text,
            "message_metadata": {
                "from": from_raw or from_email,
                "subject": form_data.get("subject"),
                "message_id": message_id,
            }
        })
        
        # Send notification about new inbound (for human visibility)
        from ..channels.notifications import NotificationService
        from ..config import settings, llm_config
        try:
            notification_service = NotificationService(db, settings)
            if llm_config.human_notification_email:
                notification_service.send_inbound_notification(
                    lead=lead,
                    inbound_message=inbound_text,
                    subject=form_data.get("subject", ""),
                    conversation_id=conversation.id
                )
        except Exception as e:
            logger.warning(f"Failed to send inbound notification: {e}")
        
        # Load conversation history
        messages = msg_repo.get_by_conversation(conversation.id, limit=5)
        history = [
            {
                "direction": msg.direction.value,
                "body": msg.body,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
        
        # Use ReplyAgent to analyze and respond
        from ..conversation.reply_agent import ReplyAgent
        from ..config import llm_config
        
        # Build lead_data with enrichment if available
        lead_data_dict = {
            "email": lead.email,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "company_name": lead.company_name,
            "industry": lead.industry
        }
        
        # Include enrichment data if available
        if lead.enrichment:
            lead_data_dict["enrichment"] = {
                "website_summary": lead.enrichment.website_summary,
                "personalization_bullets": lead.enrichment.personalization_bullets
            }
        
        agent = ReplyAgent(llm_config)
        analysis = agent.analyze_and_respond(
            inbound_message=inbound_text,
            lead_data=lead_data_dict,
            conversation_history=history
        )
        
        logger.info(f"AI Analysis: intent={analysis.intent}, confidence={analysis.confidence}, escalate={analysis.escalate}")
        
        # Handle based on analysis
        from ..conversation.reply_agent import ReplyAction
        from ..storage.models import ConversationState
        
        if analysis.next_action == ReplyAction.ESCALATE:
            # Escalate to human
            logger.info(f"Escalating conversation {conversation.id} to human")
            
            # Update conversation state
            conv_repo.update(conversation.id, {"state": ConversationState.NEEDS_HUMAN_REVIEW})
            
            # Send notification
            from ..channels.notifications import NotificationService
            from ..config import settings
            notification_service = NotificationService(db, settings)
            notification_service.send_escalation_email(
                conversation=conversation,
                lead=lead,
                inbound_message=inbound_text,
                analysis={
                    "intent": analysis.intent.value,
                    "confidence": analysis.confidence,
                    "escalation_reason": analysis.escalation_reason,
                    "sentiment": analysis.sentiment,
                    "recommendation": agent.generate_human_recommendation(analysis, inbound_text, {
                        "first_name": lead.first_name,
                        "company_name": lead.company_name
                    })
                }
            )
            
            return {"success": True, "action": "escalated"}
        
        elif analysis.next_action == ReplyAction.UNSUBSCRIBE:
            # Handle unsubscribe
            logger.info(f"Unsubscribing lead {lead.id}")
            
            # Mark as suppressed
            from ..channels.suppression import SuppressionManager
            suppression_mgr = SuppressionManager(db)
            suppression_mgr.suppress_lead(lead.id, "unsubscribe", "inbound_request")
            
            # Update conversation state
            conv_repo.update(conversation.id, {"state": ConversationState.STOPPED})
            
            # Send confirmation
            email_service = SendGridService(db)
            email_service.send(
                to_email=lead.email,
                subject="Unsubscribed",
                body=analysis.response_text,
                lead_id=lead.id,
                conversation_id=conversation.id
            )
            
            return {"success": True, "action": "unsubscribed"}
        
        elif analysis.next_action == ReplyAction.AUTO_REPLY:
            # Auto-reply: queue delayed send (30–90 min)
            from ..config import llm_config
            from ..workflow.tasks import send_delayed_reply
            
            response_body = analysis.response_text
            if _should_append_booking_link(analysis.intent.value, analysis.response_text):
                calendly_service = CalendlyService(db)
                booking_link = calendly_service.get_booking_link(
                    lead.first_name or "",
                    lead.last_name or "",
                    lead.email
                )
                response_body += f"\n\nYou can book a time here: {booking_link}"
                logger.info("Appended Calendly link to scheduling response")
            
            min_sec = llm_config.reply_delay_min_minutes * 60
            max_sec = llm_config.reply_delay_max_minutes * 60
            countdown = random.randint(min_sec, max_sec)
            logger.info(f"Queuing delayed reply for conversation {conversation.id} in {countdown // 60} min")
            
            send_delayed_reply.apply_async(
                kwargs={
                    "conversation_id": conversation.id,
                    "channel": "email",
                    "body": response_body,
                    "lead_id": lead.id,
                    "to_email": lead.email,
                    "subject": f"Re: {form_data.get('subject', 'Your inquiry')}",
                },
                countdown=countdown,
            )
            
            return {"success": True, "action": "auto_reply_queued"}
        
        return {"success": True}
    
    except Exception as e:
        logger.error(f"Error processing inbound email: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Twilio webhooks
@app.post("/webhooks/twilio")
async def twilio_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Twilio webhook for SMS with AI reply agent"""
    try:
        form_data = await request.form()
        from_phone = form_data.get("From")
        inbound_text = form_data.get("Body", "")
        
        logger.info(f"Inbound SMS from: {from_phone}")
        
        # Find lead by phone
        from ..storage.repositories import LeadRepository, ConversationRepository, MessageRepository
        lead_repo = LeadRepository(db)
        conv_repo = ConversationRepository(db)
        msg_repo = MessageRepository(db)
        
        lead = lead_repo.get_by_phone(from_phone)
        if not lead:
            logger.warning(f"Inbound SMS from unknown sender: {from_phone}")
            # Send generic response
            from twilio.twiml.messaging_response import MessagingResponse
            resp = MessagingResponse()
            resp.message("Thank you for your message. We'll be in touch soon.")
            return JSONResponse(content={"twiml": str(resp)})
        
        # Find or create conversation
        conversation = conv_repo.get_by_lead(lead.id)
        if not conversation:
            logger.info(f"Creating new conversation for lead {lead.id}")
            from ..storage.models import ConversationState, MessageChannel
            conversation = conv_repo.create({
                "lead_id": lead.id,
                "state": ConversationState.ENGAGED,
                "channel": MessageChannel.SMS
            })
        
        # Save inbound message
        from ..storage.models import MessageDirection
        msg_repo.create({
            "conversation_id": conversation.id,
            "direction": MessageDirection.INBOUND,
            "channel": conversation.channel,
            "body": inbound_text,
            "message_metadata": {
                "from": from_phone,
                "twilio_sid": form_data.get("MessageSid")
            }
        })
        
        # Load conversation history
        messages = msg_repo.get_by_conversation(conversation.id, limit=5)
        history = [
            {
                "direction": msg.direction.value,
                "body": msg.body,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
        
        # Use ReplyAgent to analyze and respond
        from ..conversation.reply_agent import ReplyAgent
        from ..config import llm_config
        
        agent = ReplyAgent(llm_config)
        analysis = agent.analyze_and_respond(
            inbound_message=inbound_text,
            lead_data={
                "email": lead.email,
                "phone": lead.phone,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "company_name": lead.company_name,
                "industry": lead.industry
            },
            conversation_history=history
        )
        
        logger.info(f"AI Analysis: intent={analysis.intent}, confidence={analysis.confidence}, escalate={analysis.escalate}")
        
        # Handle based on analysis
        from ..conversation.reply_agent import ReplyAction
        from ..storage.models import ConversationState
        from twilio.twiml.messaging_response import MessagingResponse
        
        if analysis.next_action == ReplyAction.ESCALATE:
            # Escalate to human
            logger.info(f"Escalating SMS conversation {conversation.id} to human")
            
            # Update conversation state
            conv_repo.update(conversation.id, {"state": ConversationState.NEEDS_HUMAN_REVIEW})
            
            # Send notification
            from ..channels.notifications import NotificationService
            from ..config import settings
            notification_service = NotificationService(db, settings)
            notification_service.send_escalation_email(
                conversation=conversation,
                lead=lead,
                inbound_message=inbound_text,
                analysis={
                    "intent": analysis.intent.value,
                    "confidence": analysis.confidence,
                    "escalation_reason": analysis.escalation_reason,
                    "sentiment": analysis.sentiment,
                    "recommendation": agent.generate_human_recommendation(analysis, inbound_text, {
                        "first_name": lead.first_name,
                        "company_name": lead.company_name
                    })
                }
            )
            
            # Send holding response
            resp = MessagingResponse()
            resp.message("Thanks for your message. I'll have someone reach out to you directly.")
            return JSONResponse(content={"twiml": str(resp)})
        
        elif analysis.next_action == ReplyAction.UNSUBSCRIBE:
            # Handle unsubscribe
            logger.info(f"Unsubscribing lead {lead.id}")
            
            # Mark as suppressed
            from ..channels.suppression import SuppressionManager
            suppression_mgr = SuppressionManager(db)
            suppression_mgr.suppress_lead(lead.id, "unsubscribe", "inbound_sms")
            
            # Update conversation state
            conv_repo.update(conversation.id, {"state": ConversationState.STOPPED})
            
            # Send confirmation
            resp = MessagingResponse()
            resp.message(analysis.response_text)
            return JSONResponse(content={"twiml": str(resp)})
        
        elif analysis.next_action == ReplyAction.AUTO_REPLY:
            # Auto-reply: queue delayed send (30–90 min), return holding message
            from ..config import llm_config
            from ..workflow.tasks import send_delayed_reply
            
            response_body = analysis.response_text
            min_sec = llm_config.reply_delay_min_minutes * 60
            max_sec = llm_config.reply_delay_max_minutes * 60
            countdown = random.randint(min_sec, max_sec)
            logger.info(f"Queuing delayed SMS reply for conversation {conversation.id} in {countdown // 60} min")
            
            send_delayed_reply.apply_async(
                kwargs={
                    "conversation_id": conversation.id,
                    "channel": "sms",
                    "body": response_body,
                    "lead_id": lead.id,
                    "to_phone": from_phone,
                },
                countdown=countdown,
            )
            
            resp = MessagingResponse()
            resp.message("Thanks for your message. We'll get back to you shortly.")
            return JSONResponse(content={"twiml": str(resp)})
        
        # Default response
        resp = MessagingResponse()
        resp.message("Thank you for your message. We'll be in touch soon.")
        return JSONResponse(content={"twiml": str(resp)})
    
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {e}", exc_info=True)
        # Return generic TwiML response even on error
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        resp.message("Thank you for your message.")
        return JSONResponse(content={"twiml": str(resp)})


# Calendly webhooks
@app.post("/webhooks/calendly")
async def calendly_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Calendly webhook for appointment events"""
    try:
        data = await request.json()
        
        service = CalendlyService(db)
        result = service.handle_webhook(data)
        return result
    
    except Exception as e:
        logger.error(f"Error processing Calendly webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# API endpoints
@app.get("/api/leads")
async def list_leads(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all leads"""
    from ..storage.repositories import LeadRepository
    
    repo = LeadRepository(db)
    leads = repo.list_all(skip=skip, limit=limit)
    
    return {
        "leads": [
            {
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "company_name": lead.company_name,
                "state": lead.state,
                "score": lead.score.score if lead.score else None,
                "tier": lead.score.tier if lead.score else None
            }
            for lead in leads
        ]
    }


@app.get("/api/conversations")
async def list_conversations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all conversations"""
    from ..storage.models import Conversation
    
    conversations = db.query(Conversation).offset(skip).limit(limit).all()
    
    return {
        "conversations": [
            {
                "id": conv.id,
                "lead_id": conv.lead_id,
                "state": conv.state.value,
                "channel": conv.channel.value,
                "created_at": conv.created_at.isoformat() if conv.created_at else None
            }
            for conv in conversations
        ]
    }


@app.get("/api/appointments")
async def list_appointments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all appointments"""
    from ..storage.models import Appointment
    
    appointments = db.query(Appointment).offset(skip).limit(limit).all()
    
    return {
        "appointments": [
            {
                "id": appt.id,
                "lead_id": appt.lead_id,
                "scheduled_at": appt.scheduled_at.isoformat() if appt.scheduled_at else None,
                "status": appt.status.value,
                "meeting_url": appt.meeting_url
            }
            for appt in appointments
        ]
    }


@app.get("/api/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Get analytics metrics"""
    from ..api.analytics import AnalyticsService
    
    analytics = AnalyticsService(db)
    metrics = analytics.get_dashboard_metrics()
    
    return metrics


@app.post("/api/leads/import")
async def import_leads(
    background_tasks: BackgroundTasks,
    file_path: str,
    db: Session = Depends(get_db)
):
    """Import leads from CSV file (async)"""
    from ..ingestion.lead_processor import LeadProcessor
    
    def import_task():
        processor = LeadProcessor(db)
        stats = processor.process_csv_file(file_path)
        logger.info(f"Import completed: {stats}")
    
    background_tasks.add_task(import_task)
    
    return {"success": True, "message": "Import started in background"}


# Apify Source Management Endpoints
@app.post("/api/sources/apify/run")
async def trigger_apify_import(
    background_tasks: BackgroundTasks,
    strategy: str = "rotate",  # "rotate" or "custom"
    actor_id: str = None,
    industry: str = None,
    state: str = None,
    size: str = None,
    db: Session = Depends(get_db)
):
    """
    Manually trigger Apify import.
    
    Args:
        strategy: "rotate" (use automated rotation) or "custom" (specify parameters)
        actor_id: Optional actor ID (for custom strategy)
        industry: Optional industry filter (for custom strategy)
        state: Optional state filter (for custom strategy)
        size: Optional company size (for custom strategy)
    """
    from ..workflow.tasks import run_apify_import
    
    if strategy == "rotate":
        # Use standard rotation logic
        task = run_apify_import.delay()
        return {
            "success": True,
            "message": "Apify import task queued (rotation strategy)",
            "task_id": task.id
        }
    
    elif strategy == "custom":
        # Custom parameters (you could extend this to accept custom params)
        # For now, queue the standard task
        task = run_apify_import.delay()
        return {
            "success": True,
            "message": "Apify import task queued (custom parameters)",
            "task_id": task.id,
            "note": "Custom parameter support coming soon"
        }
    
    else:
        raise HTTPException(status_code=400, detail="Invalid strategy. Use 'rotate' or 'custom'")


@app.get("/api/sources/apify/runs")
async def list_apify_runs(limit: int = 20, db: Session = Depends(get_db)):
    """
    List recent Apify runs with stats.
    
    Args:
        limit: Number of runs to return (default 20)
    """
    from ..storage.models import LeadSourceRun
    
    runs = (
        db.query(LeadSourceRun)
        .order_by(LeadSourceRun.started_at.desc())
        .limit(limit)
        .all()
    )
    
    return {
        "runs": [
            {
                "id": run.id,
                "run_id": run.run_id,
                "actor_name": run.actor_name,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "total_rows": run.total_rows,
                "new_leads_imported": run.new_leads_imported,
                "duplicates_skipped": run.duplicates_skipped,
                "params": run.params_json,
                "error_message": run.error_message
            }
            for run in runs
        ]
    }


@app.get("/api/sources/apify/stats")
async def get_apify_stats(db: Session = Depends(get_db)):
    """Get aggregate statistics for Apify imports"""
    from ..storage.models import LeadSourceRun
    from sqlalchemy import func
    
    total_runs = db.query(func.count(LeadSourceRun.id)).scalar()
    successful_runs = db.query(func.count(LeadSourceRun.id)).filter(
        LeadSourceRun.status == "completed"
    ).scalar()
    total_leads_imported = db.query(func.sum(LeadSourceRun.new_leads_imported)).scalar() or 0
    total_duplicates = db.query(func.sum(LeadSourceRun.duplicates_skipped)).scalar() or 0
    
    return {
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": total_runs - successful_runs,
        "total_leads_imported": total_leads_imported,
        "total_duplicates_skipped": total_duplicates,
        "success_rate": f"{(successful_runs / total_runs * 100):.1f}%" if total_runs > 0 else "N/A"
    }


@app.post("/api/sources/apify/test")
async def test_apify_connection():
    """Test Apify API connection with configured tokens"""
    from ..sources.apify import test_connection
    import asyncio
    
    success = await test_connection()
    
    if success:
        return {"success": True, "message": "Apify connection successful"}
    else:
        raise HTTPException(status_code=500, detail="Apify connection failed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
