"""
Celery application configuration for task scheduling and background jobs.
"""
from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

# Create Celery app
celery_app = Celery(
    'iul_appointment_setter',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)

# Periodic task schedule
celery_app.conf.beat_schedule = {
    # Apify lead sourcing - every 2 hours (during warmup) or 6 hours (post-warmup)
    'run-apify-import': {
        'task': 'src.workflow.tasks.run_apify_import',
        'schedule': crontab(minute='0', hour='*/2'),  # Every 2 hours
    },
    # Outbound message dispatcher - every 10 minutes (respects rate limits and send window)
    'dispatch-outbound-messages': {
        'task': 'src.workflow.tasks.dispatch_outbound_messages',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    # Appointment reminders
    'send-appointment-reminders-24h': {
        'task': 'src.workflow.tasks.send_24h_reminders',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'send-appointment-reminders-2h': {
        'task': 'src.workflow.tasks.send_2h_reminders',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    'check-no-shows': {
        'task': 'src.workflow.tasks.check_no_shows',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    # Calendly appointment sync - every 20 minutes (non-rate-limiting)
    'sync-calendly-appointments': {
        'task': 'src.workflow.tasks.sync_calendly_appointments',
        'schedule': crontab(minute='*/20'),  # Every 20 minutes
    },
    # Lead scoring - every 6 hours
    'score-unscored-leads': {
        'task': 'src.workflow.tasks.score_unscored_leads',
        'schedule': crontab(minute='0', hour='*/6'),  # Every 6 hours
    },
    # Website enrichment - daily at 2 AM
    'enrich-high-priority-leads': {
        'task': 'src.workflow.tasks.enrich_high_priority_leads',
        'schedule': crontab(minute='0', hour='2'),  # Daily at 2 AM
    },
    # Re-verify stale email addresses (verified > 30 days ago or never) - daily at 3 AM
    're-verify-stale-emails': {
        'task': 'src.workflow.tasks.re_verify_stale_emails',
        'schedule': crontab(minute='0', hour='3'),  # Daily at 3 AM UTC
    },
}

# Auto-discover tasks from modules
celery_app.autodiscover_tasks([
    'src.workflow',
    'src.channels',
    'src.scheduling'
])
