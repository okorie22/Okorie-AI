"""
Validate all leads' emails in the database using Rapid Email Validator.
Updates email_deliverable, email_verification_status, and email_verified_at on each lead.

Uses DATABASE_URL from environment (via .env). Run from project root:
  python scripts/validate_leads_emails.py
  python scripts/validate_leads_emails.py --dry-run
  python scripts/validate_leads_emails.py --limit 200
  python scripts/validate_leads_emails.py --stale-only   # only leads needing re-verify (for daily cron)
"""
import argparse
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.storage.database import SessionLocal
from src.storage.models import Lead
from src.ingestion.email_verifier import validate_batch

BATCH_SIZE = 100


def main():
    parser = argparse.ArgumentParser(description="Validate lead emails via Rapid Email Validator")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and log results only, do not update DB")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N leads (for testing)")
    parser.add_argument("--stale-only", action="store_true", help="Only re-verify leads with stale or missing email_verified_at (for daily cron)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Lead).filter(
            Lead.email.isnot(None),
            Lead.email != ""
        ).order_by(Lead.id)
        if args.stale_only:
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            from sqlalchemy import or_
            query = query.filter(or_(Lead.email_verified_at.is_(None), Lead.email_verified_at < cutoff))
        if args.limit:
            query = query.limit(args.limit)
        leads = query.all()
        total = len(leads)
        logger.info(f"Found {total} leads with email to validate" + (" (stale-only)" if args.stale_only else ""))
        if total == 0:
            return

        status_counts: Counter = Counter()
        deliverable_count = 0

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
                status = info.get("status")
                deliverable = info.get("deliverable", False)
                status_counts[status or "UNKNOWN"] += 1
                if deliverable:
                    deliverable_count += 1

                if not args.dry_run:
                    lead.email_deliverable = deliverable
                    lead.email_verification_status = status
                    lead.email_verified_at = datetime.now(timezone.utc)

            if not args.dry_run:
                db.commit()

            processed = min(i + BATCH_SIZE, total)
            logger.info(f"Validated {processed}/{total} leads")

        logger.info(
            f"\nSummary: {total} processed, {deliverable_count} deliverable, "
            f"{total - deliverable_count} not deliverable"
        )
        logger.info("Status breakdown: " + ", ".join(f"{k}: {v}" for k, v in sorted(status_counts.items())))
        if args.dry_run:
            logger.info("(Dry run: no DB updates)")
        else:
            logger.success("Database updated.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
