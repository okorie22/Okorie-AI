"""
Test CSV Import Script

Creates a sample CSV with 10 test leads and imports them to verify:
1. CSV parsing
2. Lead normalization
3. Deduplication
4. Scoring
5. Enrichment
6. Conversation creation
"""
import sys
import csv
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy.orm import Session

from src.storage.database import SessionLocal, engine, Base
from src.ingestion.lead_processor import LeadProcessor
from src.intelligence.scorer import LeadScorer
from src.intelligence.enricher import LeadEnricher
from src.workflow.state_machine import WorkflowEngine


# Sample test leads (realistic data)
TEST_LEADS = [
    {
        "first_name": "John",
        "last_name": "Smith",
        "email": "john.smith@techcorp.com",
        "phone": "+1-555-0101",
        "company_name": "TechCorp Solutions",
        "title": "CEO",
        "industry": "Information Technology",
        "employee_count": "45",
        "company_website": "https://techcorp.example.com",
        "state": "Texas",
        "city": "Austin",
    },
    {
        "first_name": "Sarah",
        "last_name": "Johnson",
        "email": "sarah.j@legalfirm.com",
        "phone": "+1-555-0102",
        "company_name": "Johnson & Associates Law",
        "title": "Managing Partner",
        "industry": "Legal Services",
        "employee_count": "28",
        "company_website": "https://johnsonlaw.example.com",
        "state": "California",
        "city": "San Francisco",
    },
    {
        "first_name": "Michael",
        "last_name": "Chen",
        "email": "m.chen@healthplus.com",
        "phone": "+1-555-0103",
        "company_name": "HealthPlus Medical Group",
        "title": "Medical Director",
        "industry": "Hospital & Health Care",
        "employee_count": "67",
        "company_website": "https://healthplus.example.com",
        "state": "New York",
        "city": "New York",
    },
    {
        "first_name": "Emily",
        "last_name": "Rodriguez",
        "email": "emily.r@constructco.com",
        "phone": "+1-555-0104",
        "company_name": "Rodriguez Construction Inc",
        "title": "President",
        "industry": "Construction",
        "employee_count": "38",
        "company_website": "https://rodriguezconst.example.com",
        "state": "Florida",
        "city": "Miami",
    },
    {
        "first_name": "David",
        "last_name": "Thompson",
        "email": "david@accountingpros.com",
        "phone": "+1-555-0105",
        "company_name": "Thompson Accounting Professionals",
        "title": "CPA, Partner",
        "industry": "Accounting",
        "employee_count": "22",
        "company_website": "https://thompsonaccounting.example.com",
        "state": "Illinois",
        "city": "Chicago",
    },
    {
        "first_name": "Lisa",
        "last_name": "Martinez",
        "email": "lisa.martinez@designstudio.com",
        "phone": "+1-555-0106",
        "company_name": "Martinez Design Studio",
        "title": "Creative Director",
        "industry": "Design",
        "employee_count": "15",
        "company_website": "https://martinezdesign.example.com",
        "state": "Washington",
        "city": "Seattle",
    },
    {
        "first_name": "Robert",
        "last_name": "Wilson",
        "email": "robert.w@financialgroup.com",
        "phone": "+1-555-0107",
        "company_name": "Wilson Financial Group",
        "title": "Managing Director",
        "industry": "Financial Services",
        "employee_count": "52",
        "company_website": "https://wilsonfinancial.example.com",
        "state": "Massachusetts",
        "city": "Boston",
    },
    {
        "first_name": "Jennifer",
        "last_name": "Brown",
        "email": "jbrown@consultingfirm.com",
        "phone": "+1-555-0108",
        "company_name": "Brown Management Consulting",
        "title": "Senior Partner",
        "industry": "Management Consulting",
        "employee_count": "31",
        "company_website": "https://brownconsulting.example.com",
        "state": "Georgia",
        "city": "Atlanta",
    },
    {
        "first_name": "James",
        "last_name": "Anderson",
        "email": "james.a@realestate.com",
        "phone": "+1-555-0109",
        "company_name": "Anderson Commercial Real Estate",
        "title": "Principal Broker",
        "industry": "Real Estate",
        "employee_count": "19",
        "company_website": "https://andersonrealestate.example.com",
        "state": "Colorado",
        "city": "Denver",
    },
    {
        "first_name": "Patricia",
        "last_name": "Garcia",
        "email": "patricia@marketingagency.com",
        "phone": "+1-555-0110",
        "company_name": "Garcia Marketing Agency",
        "title": "CEO & Founder",
        "industry": "Marketing & Advertising",
        "employee_count": "26",
        "company_website": "https://garciamarketing.example.com",
        "state": "Arizona",
        "city": "Phoenix",
    },
]


def create_test_csv(output_path: str = "test_leads.csv"):
    """Create a test CSV file with sample leads"""
    
    logger.info(f"Creating test CSV with {len(TEST_LEADS)} leads...")
    
    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = TEST_LEADS[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for lead in TEST_LEADS:
            writer.writerow(lead)
    
    logger.info(f"✅ Created: {output_path}")
    return output_path


def import_and_verify(csv_path: str, db: Session):
    """Import CSV and verify the full pipeline"""
    
    logger.info("=" * 60)
    logger.info("STARTING TEST IMPORT")
    logger.info("=" * 60)
    
    # Initialize components
    lead_processor = LeadProcessor(db)
    scorer = LeadScorer(db)
    enricher = LeadEnricher(db)
    workflow_engine = WorkflowEngine(db)
    
    # Step 1: Import leads
    logger.info("\n[STEP 1] Importing leads from CSV...")
    result = lead_processor.process_csv_file(csv_path)
    
    logger.info(f"✅ Import complete:")
    logger.info(f"  - Imported: {result['imported']}")
    logger.info(f"  - Duplicates: {result['duplicates']}")
    logger.info(f"  - Errors: {result['errors']}")
    
    if result['imported'] == 0:
        logger.error("❌ No leads imported!")
        return
    
    # Step 2: Score leads
    logger.info("\n[STEP 2] Scoring leads...")
    from src.storage.models import Lead, LeadScore
    
    # Find leads without a score relationship
    scored_lead_ids = db.query(LeadScore.lead_id).all()
    scored_lead_ids = [id[0] for id in scored_lead_ids]
    
    unscored_leads = db.query(Lead).filter(
        ~Lead.id.in_(scored_lead_ids)
    ).all()
    
    logger.info(f"Found {len(unscored_leads)} unscored leads")
    
    scored_count = 0
    for lead in unscored_leads:
        try:
            score_result = scorer.score_lead(lead)
            if score_result:
                scored_count += 1
                # Refresh to get the score relationship
                db.refresh(lead)
                if lead.score:
                    logger.debug(f"  - {lead.first_name} {lead.last_name}: Tier {lead.score.tier} ({lead.score.score} pts)")
        except Exception as e:
            logger.error(f"  - Error scoring {lead.id}: {e}")
    
    logger.info(f"✅ Scored {scored_count} leads")
    
    # Step 3: Show tier distribution
    logger.info("\n[STEP 3] Tier Distribution:")
    from sqlalchemy import func
    tier_counts = db.query(
        LeadScore.tier,
        func.count(LeadScore.id)
    ).group_by(LeadScore.tier).all()
    
    for tier, count in tier_counts:
        logger.info(f"  - Tier {tier}: {count} leads")
    
    # Step 4: Enrich high-value leads (tier 1-2)
    logger.info("\n[STEP 4] Enriching tier 1-2 leads...")
    enrich_result = enricher.enrich_high_priority_leads(tier_threshold=2)
    
    logger.info(f"✅ Enrichment complete:")
    logger.info(f"  - Enriched: {enrich_result['enriched']}")
    logger.info(f"  - Skipped: {enrich_result['skipped']}")
    logger.info(f"  - Errors: {enrich_result['errors']}")
    
    # Step 5: Create conversations for tier 1-2 leads
    logger.info("\n[STEP 5] Creating conversations for high-value leads...")
    
    # Get leads with tier 1-2 scores
    tier_1_2_lead_ids = db.query(LeadScore.lead_id).filter(
        LeadScore.tier.in_([1, 2])
    ).all()
    tier_1_2_lead_ids = [id[0] for id in tier_1_2_lead_ids]
    
    high_value_leads = db.query(Lead).filter(
        Lead.id.in_(tier_1_2_lead_ids)
    ).all()
    
    logger.info(f"Found {len(high_value_leads)} tier 1-2 leads")
    
    conversations_created = 0
    for lead in high_value_leads:
        try:
            conversation = workflow_engine.start_conversation_for_lead(lead)
            if conversation:
                conversations_created += 1
                logger.debug(f"  - Created conversation for {lead.first_name} {lead.last_name} (ID: {conversation.id})")
        except Exception as e:
            logger.error(f"  - Error creating conversation for {lead.id}: {e}")
    
    logger.info(f"✅ Created {conversations_created} conversations")
    
    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST IMPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✅ Leads imported: {result['imported']}")
    logger.info(f"✅ Leads scored: {scored_count}")
    logger.info(f"✅ Leads enriched: {enrich_result['enriched']}")
    logger.info(f"✅ Conversations created: {conversations_created}")
    logger.info("=" * 60)
    
    # Show sample lead details
    logger.info("\n[SAMPLE LEAD DETAILS]")
    if tier_1_2_lead_ids:
        sample_lead = db.query(Lead).filter(Lead.id.in_(tier_1_2_lead_ids)).first()
        
        if sample_lead:
            logger.info(f"\nName: {sample_lead.first_name} {sample_lead.last_name}")
            logger.info(f"Company: {sample_lead.company_name}")
            logger.info(f"Title: {sample_lead.title}")
            logger.info(f"Industry: {sample_lead.industry}")
            logger.info(f"Employee Count: {sample_lead.employee_count}")
            
            if sample_lead.score:
                logger.info(f"Score: {sample_lead.score.score}")
                logger.info(f"Tier: {sample_lead.score.tier}")
            
            logger.info(f"Email: {sample_lead.email}")
            logger.info(f"Phone: {sample_lead.phone}")
            
            if sample_lead.enrichment:
                logger.info(f"\n[ENRICHMENT DATA]")
                logger.info(f"Website Summary: {sample_lead.enrichment.website_summary[:200]}..." if sample_lead.enrichment.website_summary else "No summary")
                if sample_lead.enrichment.personalization_bullets:
                    logger.info(f"Personalization Bullets: {sample_lead.enrichment.personalization_bullets}")
    
    logger.info("\n✅ TEST COMPLETE!")


def main():
    """Main entry point"""
    
    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)
    
    # Create test CSV
    csv_path = create_test_csv()
    
    # Import and verify
    db = SessionLocal()
    try:
        import_and_verify(csv_path, db)
    finally:
        db.close()
    
    logger.info(f"\n📊 View results in database:")
    logger.info(f"   Database: C:\\Users\\Top Cash Pawn\\ITORO\\agent-systems\\igwe\\iul_appointment_setter.db")
    logger.info(f"   Open with: DB Browser for SQLite")


if __name__ == "__main__":
    main()
