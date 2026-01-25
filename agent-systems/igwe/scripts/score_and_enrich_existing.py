"""
Quick script to score and enrich existing leads in database
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.storage.database import SessionLocal
from src.storage.models import Lead, LeadScore
from src.intelligence.scorer import LeadScorer
from src.intelligence.enricher import LeadEnricher
from src.workflow.state_machine import WorkflowEngine

db = SessionLocal()

try:
    # Get all leads without scores
    scored_lead_ids = [id[0] for id in db.query(LeadScore.lead_id).all()]
    unscored_leads = db.query(Lead).filter(~Lead.id.in_(scored_lead_ids) if scored_lead_ids else True).all()
    
    logger.info(f"Found {len(unscored_leads)} unscored leads")
    
    # Score them
    scorer = LeadScorer(db)
    for lead in unscored_leads:
        try:
            scorer.score_lead(lead)
            db.refresh(lead)
            if lead.score:
                logger.info(f"✅ Scored: {lead.first_name} {lead.last_name} - Tier {lead.score.tier} ({lead.score.score} pts)")
        except Exception as e:
            logger.error(f"❌ Error scoring {lead.id}: {e}")
    
    # Show tier distribution
    tier_counts = db.query(LeadScore.tier).all()
    logger.info(f"\n📊 Tier Distribution: {dict((f'Tier {t}', tier_counts.count((t,))) for t in set([t[0] for t in tier_counts]))}")
    
    # Enrich tier 1-2 leads
    enricher = LeadEnricher(db)
    result = enricher.enrich_high_priority_leads(tier_threshold=2)
    logger.info(f"\n🌐 Enrichment: {result['enriched']} enriched, {result['skipped']} skipped, {result['errors']} errors")
    
    # Create conversations
    tier_1_2_ids = [id[0] for id in db.query(LeadScore.lead_id).filter(LeadScore.tier.in_([1, 2])).all()]
    high_value_leads = db.query(Lead).filter(Lead.id.in_(tier_1_2_ids)).all()
    
    workflow_engine = WorkflowEngine(db)
    conv_count = 0
    for lead in high_value_leads:
        try:
            conv = workflow_engine.start_conversation_for_lead(lead)
            if conv:
                conv_count += 1
                logger.info(f"💬 Created conversation for {lead.first_name} {lead.last_name}")
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
    
    logger.info(f"\n✅ COMPLETE: {len(unscored_leads)} scored, {conv_count} conversations created")
    
finally:
    db.close()
