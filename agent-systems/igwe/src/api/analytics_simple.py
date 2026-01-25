"""
Simplified Analytics API - Quick stats without complex joins
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict
from loguru import logger

from ..storage.database import get_db
from ..storage.models import Lead, Conversation, Message, Appointment, LeadScore

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/simple")
async def get_simple_stats(db: Session = Depends(get_db)) -> Dict:
    """
    Get simple system stats without complex queries
    """
    try:
        # Simple counts
        total_leads = db.query(Lead).count()
        total_scored = db.query(LeadScore).count()
        total_conversations = db.query(Conversation).count()
        total_messages = db.query(Message).count()
        total_appointments = db.query(Appointment).count()
        
        # Tier breakdown
        tier_counts = {}
        for tier in [1, 2, 3, 4, 5]:
            count = db.query(LeadScore).filter(LeadScore.tier == tier).count()
            if count > 0:
                tier_counts[f"tier_{tier}"] = count
        
        # Today's activity
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        leads_today = db.query(Lead).filter(Lead.created_at >= today_start).count()
        messages_today = db.query(Message).filter(Message.created_at >= today_start).count()
        
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "totals": {
                "leads": total_leads,
                "scored_leads": total_scored,
                "conversations": total_conversations,
                "messages": total_messages,
                "appointments": total_appointments,
            },
            "tier_distribution": tier_counts,
            "today": {
                "leads_imported": leads_today,
                "messages_sent": messages_today,
            }
        }
    
    except Exception as e:
        logger.error(f"Error in simple analytics: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
