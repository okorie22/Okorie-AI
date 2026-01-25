"""
Analytics API endpoints - Daily and weekly stats dashboard
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import Dict, List
from loguru import logger

from ..storage.database import get_db
from ..storage.models import (
    Lead, Conversation, Message, Appointment, LeadScore,
    ConversationState, AppointmentStatus, MessageDirection
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/health")
async def analytics_health():
    """Health check for analytics endpoints"""
    return {"status": "healthy", "service": "Analytics API"}


@router.get("/daily")
async def get_daily_stats(db: Session = Depends(get_db)) -> Dict:
    """
    Get today's statistics dashboard
    
    Returns metrics for:
    - Lead acquisition
    - Email deliverability
    - Conversation progression
    - Appointment stats
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Lead stats
    leads_today = db.query(func.count(Lead.id)).filter(
        Lead.created_at >= today_start
    ).scalar() or 0
    
    # Get tier 1-2 leads (join with LeadScore)
    leads_tier_1_2 = db.query(func.count(Lead.id)).join(
        LeadScore, Lead.id == LeadScore.lead_id
    ).filter(
        Lead.created_at >= today_start,
        LeadScore.tier.in_([1, 2])
    ).scalar() or 0
    
    # Tier distribution (from LeadScore table)
    tier_dist = {}
    tier_counts = db.query(
        LeadScore.tier,
        func.count(LeadScore.id)
    ).join(
        Lead, LeadScore.lead_id == Lead.id
    ).filter(
        Lead.created_at >= today_start
    ).group_by(LeadScore.tier).all()
    
    for tier, count in tier_counts:
        tier_dist[f"tier_{tier}"] = count
    
    # Email stats
    emails_sent_today = db.query(func.count(Message.id)).filter(
        Message.created_at >= today_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email"
    ).scalar() or 0
    
    emails_delivered = db.query(func.count(Message.id)).filter(
        Message.created_at >= today_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email",
        Message.status == "delivered"
    ).scalar() or 0
    
    emails_bounced = db.query(func.count(Message.id)).filter(
        Message.created_at >= today_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email",
        Message.status == "bounced"
    ).scalar() or 0
    
    emails_complained = db.query(func.count(Message.id)).filter(
        Message.created_at >= today_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email",
        or_(Message.status == "spamreport", Message.status == "complained")
    ).scalar() or 0
    
    # Calculate rates
    bounce_rate = (emails_bounced / emails_sent_today * 100) if emails_sent_today > 0 else 0
    complaint_rate = (emails_complained / emails_sent_today * 100) if emails_sent_today > 0 else 0
    delivery_rate = (emails_delivered / emails_sent_today * 100) if emails_sent_today > 0 else 0
    
    # Conversation stats
    conversations_started = db.query(func.count(Conversation.id)).filter(
        Conversation.created_at >= today_start
    ).scalar() or 0
    
    conversations_engaged = db.query(func.count(Conversation.id)).filter(
        Conversation.updated_at >= today_start,
        Conversation.state.in_([
            ConversationState.ENGAGED,
            ConversationState.QUALIFIED
        ])
    ).scalar() or 0
    
    # State distribution
    state_dist = {}
    state_counts = db.query(
        Conversation.state,
        func.count(Conversation.id)
    ).filter(
        Conversation.created_at >= today_start
    ).group_by(Conversation.state).all()
    
    for state, count in state_counts:
        state_dist[state.value] = count
    
    # Appointment stats
    appointments_scheduled = db.query(func.count(Appointment.id)).filter(
        Appointment.created_at >= today_start
    ).scalar() or 0
    
    appointments_today = db.query(func.count(Appointment.id)).filter(
        and_(
            Appointment.scheduled_at >= today_start,
            Appointment.scheduled_at < today_start + timedelta(days=1)
        )
    ).scalar() or 0
    
    appointments_showed = db.query(func.count(Appointment.id)).filter(
        Appointment.updated_at >= today_start,
        Appointment.status == AppointmentStatus.COMPLETED
    ).scalar() or 0
    
    appointments_no_show = db.query(func.count(Appointment.id)).filter(
        Appointment.updated_at >= today_start,
        Appointment.status == AppointmentStatus.NO_SHOW
    ).scalar() or 0
    
    # Inbound replies
    inbound_replies = db.query(func.count(Message.id)).filter(
        Message.created_at >= today_start,
        Message.direction == MessageDirection.INBOUND
    ).scalar() or 0
    
    # Suppressed leads
    suppressed_today = db.query(func.count(Lead.id)).filter(
        Lead.suppressed_at >= today_start
    ).scalar() or 0
    
    return {
        "date": today_start.isoformat(),
        "leads": {
            "total": leads_today,
            "tier_1_2": leads_tier_1_2,
            "tier_distribution": tier_dist,
        },
        "emails": {
            "sent": emails_sent_today,
            "delivered": emails_delivered,
            "bounced": emails_bounced,
            "complained": emails_complained,
            "bounce_rate_percent": round(bounce_rate, 2),
            "complaint_rate_percent": round(complaint_rate, 4),
            "delivery_rate_percent": round(delivery_rate, 2),
            "health_status": "🟢 HEALTHY" if bounce_rate < 2 and complaint_rate < 0.1 else "🔴 WARNING"
        },
        "conversations": {
            "started": conversations_started,
            "engaged": conversations_engaged,
            "state_distribution": state_dist,
        },
        "appointments": {
            "scheduled_today": appointments_scheduled,
            "happening_today": appointments_today,
            "showed": appointments_showed,
            "no_show": appointments_no_show,
        },
        "engagement": {
            "inbound_replies": inbound_replies,
            "suppressed": suppressed_today,
        }
    }


@router.get("/weekly")
async def get_weekly_stats(db: Session = Depends(get_db)) -> Dict:
    """
    Get this week's statistics (last 7 days)
    
    Returns comprehensive weekly metrics and trends
    """
    week_start = datetime.utcnow() - timedelta(days=7)
    
    # Lead stats
    leads_week = db.query(func.count(Lead.id)).filter(
        Lead.created_at >= week_start
    ).scalar() or 0
    
    # Get tier 1-2 leads (join with LeadScore)
    leads_tier_1_2 = db.query(func.count(Lead.id)).join(
        LeadScore, Lead.id == LeadScore.lead_id
    ).filter(
        Lead.created_at >= week_start,
        LeadScore.tier.in_([1, 2])
    ).scalar() or 0
    
    # Tier distribution (from LeadScore table)
    tier_dist = {}
    tier_counts = db.query(
        LeadScore.tier,
        func.count(LeadScore.id)
    ).join(
        Lead, LeadScore.lead_id == Lead.id
    ).filter(
        Lead.created_at >= week_start
    ).group_by(LeadScore.tier).all()
    
    for tier, count in tier_counts:
        tier_dist[f"tier_{tier}"] = count
    
    # Email stats
    emails_sent = db.query(func.count(Message.id)).filter(
        Message.created_at >= week_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email"
    ).scalar() or 0
    
    emails_delivered = db.query(func.count(Message.id)).filter(
        Message.created_at >= week_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email",
        Message.status == "delivered"
    ).scalar() or 0
    
    emails_opened = db.query(func.count(Message.id)).filter(
        Message.created_at >= week_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email",
        Message.status == "opened"
    ).scalar() or 0
    
    emails_clicked = db.query(func.count(Message.id)).filter(
        Message.created_at >= week_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email",
        Message.status == "clicked"
    ).scalar() or 0
    
    emails_bounced = db.query(func.count(Message.id)).filter(
        Message.created_at >= week_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email",
        Message.status == "bounced"
    ).scalar() or 0
    
    emails_complained = db.query(func.count(Message.id)).filter(
        Message.created_at >= week_start,
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == "email",
        or_(Message.status == "spamreport", Message.status == "complained")
    ).scalar() or 0
    
    # Calculate rates
    bounce_rate = (emails_bounced / emails_sent * 100) if emails_sent > 0 else 0
    complaint_rate = (emails_complained / emails_sent * 100) if emails_sent > 0 else 0
    open_rate = (emails_opened / emails_delivered * 100) if emails_delivered > 0 else 0
    click_rate = (emails_clicked / emails_delivered * 100) if emails_delivered > 0 else 0
    
    # Conversation funnel
    conv_new = db.query(func.count(Conversation.id)).filter(
        Conversation.created_at >= week_start,
        Conversation.state == ConversationState.NEW
    ).scalar() or 0
    
    conv_contacted = db.query(func.count(Conversation.id)).filter(
        Conversation.created_at >= week_start,
        Conversation.state == ConversationState.CONTACTED
    ).scalar() or 0
    
    conv_engaged = db.query(func.count(Conversation.id)).filter(
        Conversation.created_at >= week_start,
        Conversation.state == ConversationState.ENGAGED
    ).scalar() or 0
    
    conv_qualified = db.query(func.count(Conversation.id)).filter(
        Conversation.created_at >= week_start,
        Conversation.state == ConversationState.QUALIFIED
    ).scalar() or 0
    
    conv_scheduled = db.query(func.count(Conversation.id)).filter(
        Conversation.created_at >= week_start,
        Conversation.state == ConversationState.SCHEDULED
    ).scalar() or 0
    
    # Appointments
    appointments_scheduled = db.query(func.count(Appointment.id)).filter(
        Appointment.created_at >= week_start
    ).scalar() or 0
    
    appointments_showed = db.query(func.count(Appointment.id)).filter(
        Appointment.created_at >= week_start,
        Appointment.status == AppointmentStatus.COMPLETED
    ).scalar() or 0
    
    appointments_no_show = db.query(func.count(Appointment.id)).filter(
        Appointment.created_at >= week_start,
        Appointment.status == AppointmentStatus.NO_SHOW
    ).scalar() or 0
    
    show_rate = (appointments_showed / appointments_scheduled * 100) if appointments_scheduled > 0 else 0
    
    # Inbound activity
    inbound_replies = db.query(func.count(Message.id)).filter(
        Message.created_at >= week_start,
        Message.direction == MessageDirection.INBOUND
    ).scalar() or 0
    
    # Escalations (conversations needing human review)
    escalations = db.query(func.count(Conversation.id)).filter(
        Conversation.updated_at >= week_start,
        or_(
            Conversation.state == ConversationState.NEEDS_HUMAN_REVIEW,
            Conversation.state == ConversationState.HUMAN_HANDLING
        )
    ).scalar() or 0
    
    # Suppression
    suppressed_week = db.query(func.count(Lead.id)).filter(
        Lead.suppressed_at >= week_start
    ).scalar() or 0
    
    # Daily breakdown (last 7 days)
    daily_breakdown = []
    for i in range(7):
        day_start = (datetime.utcnow() - timedelta(days=6-i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_leads = db.query(func.count(Lead.id)).filter(
            Lead.created_at >= day_start,
            Lead.created_at < day_end
        ).scalar() or 0
        
        day_emails = db.query(func.count(Message.id)).filter(
            Message.created_at >= day_start,
            Message.created_at < day_end,
            Message.direction == MessageDirection.OUTBOUND,
            Message.channel == "email"
        ).scalar() or 0
        
        daily_breakdown.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "day_of_week": day_start.strftime("%A"),
            "leads_imported": day_leads,
            "emails_sent": day_emails,
        })
    
    return {
        "period": "last_7_days",
        "start_date": week_start.isoformat(),
        "end_date": datetime.utcnow().isoformat(),
        "leads": {
            "total": leads_week,
            "tier_1_2": leads_tier_1_2,
            "tier_1_2_percent": round((leads_tier_1_2 / leads_week * 100) if leads_week > 0 else 0, 2),
            "tier_distribution": tier_dist,
            "daily_average": round(leads_week / 7, 1),
        },
        "emails": {
            "sent": emails_sent,
            "delivered": emails_delivered,
            "opened": emails_opened,
            "clicked": emails_clicked,
            "bounced": emails_bounced,
            "complained": emails_complained,
            "bounce_rate_percent": round(bounce_rate, 2),
            "complaint_rate_percent": round(complaint_rate, 4),
            "open_rate_percent": round(open_rate, 2),
            "click_rate_percent": round(click_rate, 2),
            "health_status": "🟢 HEALTHY" if bounce_rate < 2 and complaint_rate < 0.1 else "🔴 WARNING",
            "daily_average": round(emails_sent / 7, 1),
        },
        "conversation_funnel": {
            "new": conv_new,
            "contacted": conv_contacted,
            "engaged": conv_engaged,
            "qualified": conv_qualified,
            "scheduled": conv_scheduled,
            "conversion_rates": {
                "contacted_to_engaged": round((conv_engaged / conv_contacted * 100) if conv_contacted > 0 else 0, 2),
                "engaged_to_qualified": round((conv_qualified / conv_engaged * 100) if conv_engaged > 0 else 0, 2),
                "qualified_to_scheduled": round((conv_scheduled / conv_qualified * 100) if conv_qualified > 0 else 0, 2),
            }
        },
        "appointments": {
            "scheduled": appointments_scheduled,
            "showed": appointments_showed,
            "no_show": appointments_no_show,
            "show_rate_percent": round(show_rate, 2),
        },
        "engagement": {
            "inbound_replies": inbound_replies,
            "reply_rate_percent": round((inbound_replies / emails_sent * 100) if emails_sent > 0 else 0, 2),
            "escalations": escalations,
            "escalation_rate_percent": round((escalations / inbound_replies * 100) if inbound_replies > 0 else 0, 2),
        },
        "suppression": {
            "suppressed_this_week": suppressed_week,
            "suppression_rate_percent": round((suppressed_week / leads_week * 100) if leads_week > 0 else 0, 2),
        },
        "daily_breakdown": daily_breakdown,
    }


@router.get("/conversation/{conversation_id}")
async def get_conversation_details(conversation_id: int, db: Session = Depends(get_db)) -> Dict:
    """Get detailed conversation history and stats"""
    
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    lead = conversation.lead
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at).all()
    
    return {
        "conversation_id": conversation.id,
        "state": conversation.state.value,
        "channel": conversation.channel,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "lead": {
            "id": lead.id,
            "name": f"{lead.first_name} {lead.last_name}",
            "email": lead.email,
            "company": lead.company_name,
            "title": lead.title,
            "tier": lead.tier,
            "score": lead.score,
        },
        "messages": [
            {
                "id": msg.id,
                "direction": msg.direction.value,
                "channel": msg.channel,
                "body": msg.body[:200] + "..." if len(msg.body) > 200 else msg.body,
                "status": msg.status,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ],
        "message_count": len(messages),
    }
