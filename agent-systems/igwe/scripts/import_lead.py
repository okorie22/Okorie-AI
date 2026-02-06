"""
Simple Lead Import Script

Usage:
    python scripts/import_lead.py

Just runs and prompts you for lead info, then saves to DB.
"""
import sys
import os

# Add parent directory to path so we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.storage.repositories import LeadRepository, ConversationRepository
from src.storage.models import Base, MessageChannel
from datetime import datetime, timezone


def import_lead():
    """Import a lead by prompting for info"""
    
    # Get DATABASE_URL from environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL not set in environment")
        print("Set it like: set DATABASE_URL=postgresql://user:pass@host/db")
        return
    
    print("\n=== LEAD IMPORT ===\n")
    
    # Prompt for lead info
    email = input("Email (required): ").strip().lower()
    if not email or "@" not in email:
        print("[ERROR] Valid email required")
        return
    
    first_name = input("First name (optional): ").strip() or email.split("@")[0].capitalize()
    last_name = input("Last name (optional): ").strip() or ""
    phone = input("Phone (optional, +1234567890 format): ").strip() or None
    company = input("Company (optional): ").strip() or None
    
    # Connect to DB
    print("\n[OK] Connecting to database...")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        lead_repo = LeadRepository(db)
        
        # Check if lead already exists
        existing = lead_repo.get_by_email(email)
        if existing:
            print(f"[OK] Lead already exists: {existing.first_name} {existing.last_name} ({existing.email})")
            print(f"    Lead ID: {existing.id}")
            
            # Create conversation if doesn't exist
            conv_repo = ConversationRepository(db)
            conv = conv_repo.get_active_by_lead(existing.id)
            if not conv:
                conv = conv_repo.create(existing.id, MessageChannel.EMAIL.value)
                print(f"[OK] Created conversation ID: {conv.id}")
            else:
                print(f"[OK] Conversation already exists: {conv.id}")
            
            return
        
        # Create lead
        lead_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            # Force-enable outbound sends for manually imported leads (testing + ops).
            "suppression_reason": None,
            "email_deliverable": True,
            "email_verification_status": "MANUAL_IMPORT",
            "email_verified_at": datetime.now(timezone.utc),
        }
        if phone:
            lead_data["phone"] = phone
        if company:
            lead_data["company_name"] = company
        
        lead = lead_repo.create(lead_data)
        print(f"\n[OK] Lead created!")
        print(f"    Lead ID: {lead.id}")
        print(f"    Name: {lead.first_name} {lead.last_name}")
        print(f"    Email: {lead.email}")
        if lead.phone:
            print(f"    Phone: {lead.phone}")
        if lead.company_name:
            print(f"    Company: {lead.company_name}")
        
        # Create initial conversation
        conv_repo = ConversationRepository(db)
        conv = conv_repo.create(lead.id, MessageChannel.EMAIL.value)
        print(f"[OK] Created conversation ID: {conv.id}")
        
        print("\n[OK] Done! You can now compose messages to this lead.")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to import lead: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import_lead()
