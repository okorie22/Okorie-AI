"""
Backfill conversations for existing leads that don't have one yet.
Run this once to catch up on all historical leads.
"""
from sqlalchemy.orm import Session
from loguru import logger
from datetime import datetime

from ..storage.database import SessionLocal
from ..storage.models import Lead, Conversation
from ..storage.repositories import ConversationRepository
from .state_machine import WorkflowEngine


def backfill_conversations(dry_run: bool = False) -> dict:
    """
    Create conversations for all leads with emails that don't have an active conversation.
    
    Args:
        dry_run: If True, only count how many would be created without actually creating
    
    Returns:
        Dict with stats
    """
    db = SessionLocal()
    
    try:
        # Find all leads with emails that don't have an active conversation
        leads_without_conversations = (
            db.query(Lead)
            .outerjoin(Conversation, Lead.id == Conversation.lead_id)
            .filter(
                Lead.email.isnot(None),
                Lead.suppression_reason.is_(None),  # Not suppressed
                Conversation.id.is_(None)  # No conversation exists
            )
            .all()
        )
        
        total_count = len(leads_without_conversations)
        logger.info(f"Found {total_count} leads without conversations")
        
        if dry_run:
            return {
                "dry_run": True,
                "would_create": total_count
            }
        
        # Create conversations
        engine = WorkflowEngine(db)
        created = 0
        errors = 0
        
        for lead in leads_without_conversations:
            try:
                engine.start_conversation(lead)
                created += 1
                
                if created % 50 == 0:
                    logger.info(f"Progress: {created}/{total_count} conversations created")
            
            except Exception as e:
                errors += 1
                logger.error(f"Error creating conversation for lead {lead.id}: {e}")
        
        logger.info(f"Backfill complete: {created} created, {errors} errors")
        
        return {
            "dry_run": False,
            "total_leads": total_count,
            "created": created,
            "errors": errors
        }
    
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
    
    result = backfill_conversations(dry_run=dry_run)
    print(f"\nBackfill Results:")
    print(f"  Dry Run: {result['dry_run']}")
    if result['dry_run']:
        print(f"  Would Create: {result['would_create']} conversations")
    else:
        print(f"  Total Leads: {result['total_leads']}")
        print(f"  Created: {result['created']}")
        print(f"  Errors: {result['errors']}")
