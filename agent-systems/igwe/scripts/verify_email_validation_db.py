"""
Quick verification: query Postgres (or SQLite) to confirm email_deliverable
and email_verification_status were updated by validate_leads_emails.py.
Uses DATABASE_URL from .env. Run from igwe dir: python scripts/verify_email_validation_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.storage.database import engine, DATABASE_URL

def main():
    # Mask password in log
    display_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL[:50]
    print(f"Database: ...@{display_url}")
    print()

    with engine.connect() as conn:
        # Check columns exist (Postgres)
        if DATABASE_URL.startswith("postgresql"):
            r = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'leads' AND column_name IN ('email_deliverable', 'email_verification_status')
                ORDER BY column_name
            """))
            cols = [row[0] for row in r]
            if len(cols) != 2:
                print("Missing columns:", cols)
                return
            print("Columns OK: email_deliverable, email_verification_status")
        else:
            print("Columns assumed (SQLite)")

        # Count by deliverable and status
        r = conn.execute(text("""
            SELECT email_deliverable, email_verification_status, COUNT(*) AS cnt
            FROM leads
            WHERE email IS NOT NULL AND TRIM(email) != ''
            GROUP BY email_deliverable, email_verification_status
            ORDER BY email_deliverable NULLS LAST, email_verification_status
        """))
        rows = r.fetchall()

    print()
    print("Leads with email (grouped by validation result):")
    print("-" * 60)
    total = 0
    for email_deliverable, status, cnt in rows:
        total += cnt
        deliverable_label = "True (deliverable)" if email_deliverable else "False (not deliverable)"
        print(f"  email_deliverable={deliverable_label}, status={status or 'NULL'}: {cnt} leads")
    print("-" * 60)
    print(f"  Total leads with email: {total}")
    print()
    print("Verification complete.")

if __name__ == "__main__":
    main()
