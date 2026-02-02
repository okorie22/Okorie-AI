"""
Celery tasks for workflow automation.
"""
from celery import Task
from loguru import logger
from datetime import datetime, timedelta, timezone
from typing import Optional
import asyncio
from pathlib import Path

from .celery_app import celery_app
from ..storage.database import SessionLocal


class DatabaseTask(Task):
    """Base task with database session"""
    _db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(base=DatabaseTask, bind=True)
def process_pending_actions(self):
    """Process conversations with pending actions (legacy - now handled by dispatcher)"""
    from .state_machine import WorkflowEngine
    
    logger.info("Running task: process_pending_actions")
    
    engine = WorkflowEngine(self.db)
    result = engine.process_pending_actions()
    
    logger.info(f"Processed {result['processed']} actions, {result['errors']} errors")
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def dispatch_outbound_messages(self):
    """
    Dispatch batch of outbound messages respecting rate limits and send window.
    
    This task:
    1. Checks if we're within send window (Mon-Fri, 8 AM - 5 PM EST)
    2. Checks if rate limits allow sending
    3. Processes pending conversation actions (sends openers/follow-ups)
    4. Respects batch_size to avoid overwhelming SendGrid
    
    Runs every 10 minutes.
    """
    from ..channels.rate_limiter import SendRateLimiter
    from .state_machine import WorkflowEngine
    from ..config import sendgrid_config
    
    # Print to terminal
    print(f"\n{'='*60}")
    print(f"📧 SCHEDULED TASK STARTED: Message Dispatch")
    print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}\n")
    
    logger.info("Running task: dispatch_outbound_messages")
    
    rate_limiter = SendRateLimiter(self.db)
    
    # Check if we're within send window
    if not rate_limiter.is_within_send_window():
        logger.warning("Outside send window, skipping dispatch")
        return {"skipped": "outside_window"}
    
    # Get rate limit stats and calculate effective batch size
    stats = rate_limiter.get_send_stats()
    batch_size = sendgrid_config.batch_size
    
    # Log detailed stats BEFORE calculation for debugging
    logger.info(
        f"Rate limit check: batch_size={batch_size}, "
        f"hourly_remaining={stats['hourly_remaining']}/{stats['hourly_cap']}, "
        f"daily_remaining={stats['daily_remaining']}/{stats['daily_cap']}, "
        f"sent_today={stats['sent_today']}, sent_this_hour={stats['sent_this_hour']}"
    )
    
    # Calculate effective batch size (cap by available headroom)
    effective_batch = min(
        batch_size,
        max(0, stats["hourly_remaining"]),
        max(0, stats["daily_remaining"]),
    )
    
    # Log the calculation result
    logger.info(
        f"Effective batch calculation: min({batch_size}, max(0, {stats['hourly_remaining']}), "
        f"max(0, {stats['daily_remaining']})) = {effective_batch}"
    )
    
    if effective_batch <= 0:
        logger.warning(
            f"Rate limit reached, deferring dispatch. "
            f"effective_batch={effective_batch}, stats={stats}"
        )
        return {"skipped": "rate_limited", "stats": stats}
    
    if effective_batch < batch_size:
        logger.info(
            f"Capping batch to headroom: requested={batch_size}, effective={effective_batch}"
        )
    
    logger.info(
        f"Proceeding with dispatch: {stats['sent_today']}/{stats['daily_cap']} daily, "
        f"{stats['sent_this_hour']}/{stats['hourly_cap']} hourly, effective_batch={effective_batch}"
    )
    
    # Process pending actions with effective batch limit
    engine = WorkflowEngine(self.db)
    result = engine.process_pending_actions(limit=effective_batch)
    
    logger.info(
        f"Dispatched {result['processed']} messages (batch size: {effective_batch}), {result['errors']} errors"
    )
    
    # Print completion to terminal
    stats = rate_limiter.get_send_stats()
    print(f"\n{'='*60}")
    print(f"✅ TASK COMPLETED: Message Dispatch")
    print(f"   Processed: {result['processed']}")
    print(f"   Errors: {result['errors']}")
    print(f"   Today's Sent: {stats.get('messages_sent_today', 0)}/{stats.get('daily_limit', 0)}")
    print(f"{'='*60}\n")
    
    return {
        "success": True,
        "processed": result['processed'],
        "errors": result['errors'],
        "stats": stats
    }


@celery_app.task(base=DatabaseTask, bind=True)
def score_unscored_leads(self):
    """Score all leads that don't have scores"""
    from ..intelligence.scorer import LeadScorer
    
    logger.info("Running task: score_unscored_leads")
    
    scorer = LeadScorer(self.db)
    result = scorer.score_all_unscored()
    
    logger.info(f"Scored {result['scored']} leads, {result['errors']} errors")
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def enrich_high_priority_leads(self):
    """Enrich tier 1-2 leads that don't have enrichment"""
    from ..intelligence.enricher import LeadEnricher
    
    logger.info("Running task: enrich_high_priority_leads")
    
    enricher = LeadEnricher(self.db)
    result = enricher.enrich_high_priority_leads(tier_threshold=2)
    
    logger.info(f"Enriched {result['enriched']} leads, {result['skipped']} skipped, {result['errors']} errors")
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def send_24h_reminders(self):
    """Send 24-hour appointment reminders"""
    from ..scheduling.reminders import ReminderService
    
    logger.info("Running task: send_24h_reminders")
    
    service = ReminderService(self.db)
    result = service.send_24h_reminders()
    
    logger.info(f"Sent {result['sent']} reminders, {result['errors']} errors")
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def send_2h_reminders(self):
    """Send 2-hour appointment reminders"""
    from ..scheduling.reminders import ReminderService
    
    logger.info("Running task: send_2h_reminders")
    
    service = ReminderService(self.db)
    result = service.send_2h_reminders()
    
    logger.info(f"Sent {result['sent']} reminders, {result['errors']} errors")
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def check_no_shows(self):
    """Check for appointment no-shows"""
    from ..scheduling.reminders import ReminderService
    
    logger.info("Running task: check_no_shows")
    
    service = ReminderService(self.db)
    result = service.check_no_shows()
    
    logger.info(f"Processed {result['no_shows']} no-shows")
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def sync_calendly_appointments(self):
    """
    Poll Calendly API for appointment updates.
    Syncs scheduled events, detects cancellations, and marks no-shows.
    """
    from ..scheduling.appointment_tracker import AppointmentTracker
    
    logger.info("Running task: sync_calendly_appointments")
    
    tracker = AppointmentTracker(self.db)
    result = tracker.poll_scheduled_events(days_ahead=30)
    
    logger.info(
        f"Calendly sync: {result['new']} new, {result['updated']} updated, "
        f"{result['cancelled']} cancelled, {result.get('unmatched', 0)} unmatched, {result['no_shows']} no-shows"
    )
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def send_message_task(self, conversation_id: int, template_name: str):
    """
    Async task to send a message.
    Used for auto-responses and confirmation emails.
    """
    from ..channels.message_sender import MessageSender
    from ..storage.repositories import ConversationRepository
    
    logger.info(f"Sending {template_name} message for conversation {conversation_id}")
    
    conv_repo = ConversationRepository(self.db)
    conversation = conv_repo.get_by_id(conversation_id)
    
    if not conversation:
        logger.error(f"Conversation {conversation_id} not found")
        return {"error": "Conversation not found"}
    
    sender = MessageSender(self.db)
    result = sender.send_conversation_message(conversation, template_name)
    
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def send_delayed_reply(
    self,
    conversation_id: int,
    channel: str,
    body: str,
    lead_id: int,
    to_email: Optional[str] = None,
    to_phone: Optional[str] = None,
    subject: Optional[str] = None,
):
    """
    Send a reply-agent response after a delay (30–90 min).
    Called from SendGrid/Twilio webhooks when analysis is AUTO_REPLY; the actual send happens here.
    """
    from ..channels.email import SendGridService
    from ..channels.sms import TwilioService
    from ..storage.repositories import ConversationRepository
    from ..storage.models import ConversationState
    
    logger.info(f"Sending delayed reply for conversation {conversation_id} via {channel}")
    
    conv_repo = ConversationRepository(self.db)
    conversation = conv_repo.get_by_id(conversation_id)
    if not conversation:
        logger.error(f"Conversation {conversation_id} not found for delayed reply")
        return {"error": "Conversation not found"}
    
    if channel == "email":
        if not to_email:
            logger.error("Delayed email reply missing to_email")
            return {"error": "Missing to_email"}
        email_service = SendGridService(self.db)
        result = email_service.send(
            to_email=to_email,
            subject=subject or "Re: Your inquiry",
            body=body,
            lead_id=lead_id,
            conversation_id=conversation_id,
        )
        if not result.get("success"):
            return result
    elif channel == "sms":
        if not to_phone:
            logger.error("Delayed SMS reply missing to_phone")
            return {"error": "Missing to_phone"}
        sms_service = TwilioService(self.db)
        result = sms_service.send_sms(
            to_number=to_phone,
            body=body,
            lead_id=lead_id,
            conversation_id=conversation_id,
            check_consent=False,
        )
        if not result.get("success"):
            return result
    else:
        logger.error(f"Unknown channel for delayed reply: {channel}")
        return {"error": f"Unknown channel: {channel}"}
    
    conv_repo.update(conversation_id, {"state": ConversationState.ENGAGED})
    logger.info(f"Delayed reply sent for conversation {conversation_id}")
    return {"success": True, "conversation_id": conversation_id, "channel": channel}


def count_leads_imported_today(db):
    """Count leads created today (helper function)"""
    from ..storage.models import Lead
    from datetime import datetime
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.query(Lead).filter(Lead.created_at >= today_start).count()


@celery_app.task(base=DatabaseTask, bind=True)
def run_apify_import(self):
    """
    Scheduled task: Run Apify actor, download results, import leads.
    
    This is the core lead sourcing task that:
    1. Checks warmup mode and daily lead quota
    2. Selects next actor and token (rotation)
    3. Generates next parameter set (rotation)
    4. Starts Apify actor run
    5. Waits for completion
    6. Downloads CSV
    7. Imports leads into database
    8. Scores new leads
    9. Starts conversations for tier 1-2 leads
    """
    from ..sources.apify import ApifyClient
    from ..sources.param_rotator import ParamRotator
    from ..ingestion.apify_adapter import ApifyLeadAdapter
    from ..ingestion.lead_processor import LeadProcessor
    from ..intelligence.scorer import LeadScorer
    from ..storage.models import LeadSourceRun, Lead
    from ..storage.repositories import LeadRepository, ConversationRepository
    from ..config import apify_config, workflow_config
    from .state_machine import WorkflowEngine
    from .warmup import WarmupManager
    
    # Print to terminal so user sees task execution
    print(f"\n{'='*60}")
    print(f"🔄 SCHEDULED TASK STARTED: Apify Lead Import")
    print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}\n")
    
    logger.info("Running task: run_apify_import")
    
    # Check warmup mode and lead quota
    warmup = WarmupManager()
    
    # Skip if it's a weekend during warmup
    if warmup.should_skip_today():
        logger.info("Skipping Apify import: Weekend")
        return {"skipped": "weekend"}
    
    # Check if we already have enough leads for today
    leads_needed = warmup.get_leads_needed()
    leads_imported_today = count_leads_imported_today(self.db)
    
    if leads_imported_today >= leads_needed:
        logger.info(
            f"Already imported {leads_imported_today} leads today "
            f"(need {leads_needed}), skipping"
        )
        return {
            "skipped": "daily_quota_met",
            "leads_imported_today": leads_imported_today,
            "leads_needed": leads_needed
        }
    
    logger.info(
        f"Warmup mode active - Day {warmup.get_current_day()}: "
        f"{leads_imported_today}/{leads_needed} leads imported"
    )
    
    # Initialize components (outside loop for efficiency)
    apify_client = ApifyClient()
    param_rotator = ParamRotator(self.db)
    lead_adapter = ApifyLeadAdapter()
    lead_processor = LeadProcessor(self.db)
    scorer = LeadScorer(self.db)
    lead_repo = LeadRepository(self.db)
    workflow_engine = WorkflowEngine(self.db)
    
    # Loop: run multiple actors until quota met or max runs reached
    max_runs = apify_config.max_runs_per_tick
    runs_completed = 0
    total_new_leads = 0
    total_duplicates = 0
    total_conversations_started = 0
    run_results = []
    
    for run_num in range(1, max_runs + 1):
        # Check if we've met quota
        leads_imported_today = count_leads_imported_today(self.db)
        remaining_needed = leads_needed - leads_imported_today
        
        if remaining_needed <= 0:
            logger.info(f"Quota met after {runs_completed} runs ({leads_imported_today}/{leads_needed})")
            break
        
        logger.info(f"Starting Apify run {run_num}/{max_runs} (need {remaining_needed} more leads)")
        
        try:
            
            # Select actor - ONLY use Actor 2 (pipelinelabs) as Actor 1 returns bad data
            actors = apify_config.actors
            if not actors:
                logger.error("No Apify actors configured")
                return {"error": "No actors configured"}
            
            # Filter to only use pipelinelabs actor (Actor 2)
            actor_id = None
            for a in actors:
                if "pipelinelabs" in a:
                    actor_id = a
                    break
            
            if not actor_id:
                logger.warning("pipelinelabs actor not found, falling back to first available actor")
                actor_id = actors[0]
            
            logger.info(f"Run {run_num}: Selected actor: {actor_id}")
            
            # Generate next parameter set
            used_hashes = param_rotator.get_used_param_hashes(actor_id, limit=50)
            params = param_rotator.get_next_params(actor_id, used_hashes)
            params_hash = param_rotator.generate_param_hash(params)
            
            logger.info(f"Run {run_num}: Using params hash: {params_hash}")
            
            # Create run record (will be populated after actor starts)
            run_record = None
            
            # Start Apify run (async)
            output_path = Path(f"/tmp/apify_import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_run{run_num}.csv")
            
            async def run_apify():
                return await apify_client.run_and_download(actor_id, params, output_path)
            
            # Execute async function
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in current thread, create new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If event loop is already running (unlikely in Celery), create new one
                import nest_asyncio
                nest_asyncio.apply()
                result = asyncio.run(run_apify())
            else:
                result = loop.run_until_complete(run_apify())
            
            # Create run record with actual run_id
            run_record = LeadSourceRun(
                run_id=result["run_id"],
                actor_name=actor_id,
                params_hash=params_hash,
                params_json=params,
                dataset_id=result["dataset_id"],
                status="completed",
                token_alias="rotating",
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow()
            )
            self.db.add(run_record)
            self.db.commit()
            
            logger.info(f"Run {run_num}: Apify run completed: {result['run_id']}")
            
            # Process CSV
            csv_path = Path(result["csv_path"])
            leads_data = lead_adapter.process_csv(csv_path, actor_id, deduplicate=True)
            
            logger.info(f"Run {run_num}: Extracted {len(leads_data)} leads from CSV")
            
            # Email verification (Rapid Email Validator)
            verification_map = {}
            if workflow_config.email_verification_enabled:
                emails_to_verify = [
                    (lead_data.get("email") or "").strip().lower()
                    for lead_data in leads_data
                    if lead_data.get("email")
                ]
                if emails_to_verify:
                    from ..ingestion.email_verifier import build_email_to_result_map
                    verification_map = build_email_to_result_map(emails_to_verify)
                    logger.info(f"Run {run_num}: Verified {len(verification_map)} emails")
            
            # Import leads
            new_leads = []
            duplicates = 0
            
            for lead_data in leads_data:
                # Check for duplicates by email first
                existing = lead_repo.find_by_email(lead_data["email"])
                
                # If no email match, check phone (if provided)
                if not existing and lead_data.get("phone"):
                    existing = lead_repo.find_by_phone(lead_data["phone"])
                
                if existing:
                    duplicates += 1
                    logger.debug(f"Duplicate found: {lead_data['email']}")
                    continue
                
                # Attach verification result for this lead
                email = (lead_data.get("email") or "").strip().lower()
                if email:
                    ver = verification_map.get(email, {})
                    lead_data["email_deliverable"] = ver.get("deliverable", False)
                    lead_data["email_verification_status"] = ver.get("status")
                    lead_data["email_verified_at"] = datetime.now(timezone.utc) if verification_map else None
                else:
                    lead_data["email_deliverable"] = None
                    lead_data["email_verification_status"] = None
                    lead_data["email_verified_at"] = None
                
                # Create new lead
                lead = Lead(**{k: v for k, v in lead_data.items() if k != 'metadata'})
                self.db.add(lead)
                new_leads.append(lead)
            
            self.db.commit()
            
            logger.info(f"Run {run_num}: Imported {len(new_leads)} new leads, skipped {duplicates} duplicates")
            
            # Update run record with stats
            run_record.total_rows = len(leads_data)
            run_record.new_leads_imported = len(new_leads)
            run_record.duplicates_skipped = duplicates
            self.db.commit()
            
            # Score new leads
            for lead in new_leads:
                try:
                    scorer.score_lead(lead)
                except Exception as e:
                    logger.error(f"Error scoring lead {lead.id}: {e}")
            
            self.db.commit()
            logger.info(f"Run {run_num}: Scored {len(new_leads)} new leads")
            
            # Start conversations only for leads with deliverable email (verified)
            conversations_started = 0
            if workflow_config.auto_start_conversations:
                for lead in new_leads:
                    if lead.email and lead.email_deliverable:
                        try:
                            workflow_engine.start_conversation(lead)
                            conversations_started += 1
                        except Exception as e:
                            logger.error(f"Error starting conversation for lead {lead.id}: {e}")
                
                logger.info(f"Run {run_num}: Started {conversations_started} conversations (leads with deliverable email)")
            
            # Cleanup CSV
            if csv_path.exists():
                csv_path.unlink()
            
            # Track stats for this run
            total_new_leads += len(new_leads)
            total_duplicates += duplicates
            total_conversations_started += conversations_started
            runs_completed += 1
            
            run_results.append({
                "run_number": run_num,
                "run_id": result["run_id"],
                "actor_id": actor_id,
                "new_leads": len(new_leads),
                "duplicates": duplicates,
                "conversations_started": conversations_started
            })
            
            logger.info(f"Run {run_num}: Complete. Total progress: {total_new_leads} leads imported so far")
        
        except Exception as e:
            error_msg = str(e).replace('{', '{{').replace('}', '}}')
            logger.error(f"Error in run {run_num}: {error_msg}", exc_info=True)
            
            # Update run record if exists
            if 'run_record' in locals():
                run_record.status = "failed"
                run_record.error_message = str(e)
                run_record.finished_at = datetime.utcnow()
                self.db.commit()
            
            # Continue to next run instead of failing entire task
            logger.warning(f"Run {run_num} failed, continuing to next run if applicable")
            continue
    
    # Return summary of all runs
    return {
        "success": True,
        "runs_completed": runs_completed,
        "max_runs": max_runs,
        "total_new_leads": total_new_leads,
        "total_duplicates": total_duplicates,
        "total_conversations_started": total_conversations_started,
        "leads_imported_today": count_leads_imported_today(self.db),
        "leads_needed": leads_needed,
        "run_results": run_results
    }


@celery_app.task(base=DatabaseTask, bind=True)
def re_verify_stale_emails(self):
    """
    Re-verify leads whose email_verified_at is null or older than 30 days.
    Updates email_deliverable, email_verification_status, email_verified_at.
    Run daily so send path (verified-within-30-days gate) stays valid.
    """
    from sqlalchemy import or_
    from ..storage.models import Lead
    from ..ingestion.email_verifier import validate_batch

    BATCH_SIZE = 100
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    query = self.db.query(Lead).filter(
        Lead.email.isnot(None),
        Lead.email != "",
        or_(Lead.email_verified_at.is_(None), Lead.email_verified_at < cutoff)
    ).order_by(Lead.id)
    leads = query.all()
    total = len(leads)
    if total == 0:
        logger.info("re_verify_stale_emails: no stale leads to verify")
        return {"processed": 0}

    logger.info(f"re_verify_stale_emails: verifying {total} stale leads")
    processed = 0
    for i in range(0, total, BATCH_SIZE):
        batch = leads[i : i + BATCH_SIZE]
        emails = [lead.email.strip().lower() for lead in batch if lead.email]
        if not emails:
            continue
        results = validate_batch(emails)
        email_to_result = {r["email"]: r for r in results}
        for lead in batch:
            if not lead.email:
                continue
            key = lead.email.strip().lower()
            info = email_to_result.get(key, {})
            lead.email_deliverable = info.get("deliverable", False)
            lead.email_verification_status = info.get("status")
            lead.email_verified_at = datetime.now(timezone.utc)
            processed += 1
        self.db.commit()
        logger.info(f"re_verify_stale_emails: batch {i // BATCH_SIZE + 1}, {min(i + BATCH_SIZE, total)}/{total}")
    logger.info(f"re_verify_stale_emails: done, {processed} leads updated")
    return {"processed": processed}
