"""
Direct database insert - add lead to Postgres
Run this from your local machine to add yourself as a lead
"""
import os
from datetime import datetime, timezone

# Your Render Postgres URL
DATABASE_URL = "postgresql://iul_storage_user:jNqpTaQuIMPiJIp9SC8bwk7lmySvrdYe@dpg-d5rcotcoud1c73ejj8jg-a.oregon-postgres.render.com/iul_storage"

os.environ["DATABASE_URL"] = DATABASE_URL

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Create engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def add_lead(email, first_name, last_name, company_name="", phone="", state=""):
    db = SessionLocal()
    try:
        # Check if lead exists
        result = db.execute(
            text("SELECT id, first_name, last_name FROM leads WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if result:
            print(f"[OK] Lead already exists!")
            print(f"   ID: {result[0]}")
            print(f"   Name: {result[1]} {result[2]}")
            print(f"   Email: {email}")
            return result[0]
        
        # Insert lead
        now = datetime.now(timezone.utc)
        result = db.execute(
            text("""
                INSERT INTO leads (
                    email, first_name, last_name, company_name, phone, state,
                    created_at, updated_at, email_deliverable, email_verification_status
                )
                VALUES (
                    :email, :first_name, :last_name, :company_name, :phone, :state,
                    :created_at, :updated_at, TRUE, 'valid'
                )
                RETURNING id
            """),
            {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "company_name": company_name,
                "phone": phone,
                "state": state,
                "created_at": now,
                "updated_at": now
            }
        )
        lead_id = result.fetchone()[0]
        db.commit()
        
        print(f"[OK] Lead created successfully!")
        print(f"   ID: {lead_id}")
        print(f"   Name: {first_name} {last_name}")
        print(f"   Email: {email}")
        
        # Create conversation too
        result = db.execute(
            text("""
                INSERT INTO conversations (
                    lead_id, state, channel, created_at, updated_at
                )
                VALUES (
                    :lead_id, 'new', 'email', :created_at, :updated_at
                )
                RETURNING id
            """),
            {
                "lead_id": lead_id,
                "created_at": now,
                "updated_at": now
            }
        )
        conv_id = result.fetchone()[0]
        db.commit()
        
        print(f"[OK] Conversation created!")
        print(f"   ID: {conv_id}")
        
        return lead_id
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        return None
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ADDING LEADS TO POSTGRES DATABASE")
    print("="*60 + "\n")
    
    # Add okemokorie@yahoo.com
    print("Adding okemokorie@yahoo.com...")
    add_lead(
        email="okemokorie@yahoo.com",
        first_name="Okem",
        last_name="Okorie",
        company_name="Reimagine Wealth",
        phone="+1234567890",
        state="Maryland"
    )
    
    print("\n" + "-"*60 + "\n")
    
    # Add OkemOkorie@proton.me
    print("Adding OkemOkorie@proton.me...")
    add_lead(
        email="OkemOkorie@proton.me",
        first_name="Okem",
        last_name="Okorie",
        company_name="Reimagine Wealth",
        phone="+1234567891",  # Different phone to avoid duplicate
        state="Maryland"
    )
    
    print("\n" + "="*60)
    print("DONE! Refresh your dashboard and try compose again.")
    print("="*60 + "\n")
