"""
Database migration script for deduplication cleanup.

This script:
1. Finds duplicate emails in the leads table
2. Keeps the oldest record
3. Marks duplicates as suppressed with reason="duplicate_cleanup"
4. Prepares database for unique constraint on email/phone
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from loguru import logger
from datetime import datetime

from src.storage.database import SessionLocal, engine
from src.storage.models import Lead, Base


def find_duplicate_emails(db):
    """
    Find all duplicate emails in the database.
    
    Returns:
        List of tuples (email, count)
    """
    duplicates = (
        db.query(Lead.email, func.count(Lead.id).label('count'))
        .group_by(Lead.email)
        .having(func.count(Lead.id) > 1)
        .all()
    )
    
    return [(email, count) for email, count in duplicates]


def cleanup_duplicates(db, dry_run=True):
    """
    Clean up duplicate emails by keeping oldest and marking others as suppressed.
    
    Args:
        db: Database session
        dry_run: If True, only show what would be done without making changes
    
    Returns:
        Dict with stats
    """
    duplicates = find_duplicate_emails(db)
    
    if not duplicates:
        logger.info("✅ No duplicate emails found!")
        return {"duplicates_found": 0, "leads_suppressed": 0}
    
    logger.info(f"Found {len(duplicates)} duplicate email addresses")
    
    total_suppressed = 0
    
    for email, count in duplicates:
        logger.info(f"\nProcessing: {email} ({count} occurrences)")
        
        # Get all leads with this email, ordered by created_at
        leads = (
            db.query(Lead)
            .filter(Lead.email == email)
            .order_by(Lead.created_at.asc())
            .all()
        )
        
        # Keep the first (oldest), suppress the rest
        oldest = leads[0]
        duplicates_to_suppress = leads[1:]
        
        logger.info(f"  Keeping lead {oldest.id} (created: {oldest.created_at})")
        
        for dup in duplicates_to_suppress:
            logger.info(f"  Suppressing lead {dup.id} (created: {dup.created_at})")
            
            if not dry_run:
                dup.suppression_reason = "duplicate_cleanup"
                dup.suppressed_at = datetime.utcnow()
                total_suppressed += 1
    
    if not dry_run:
        db.commit()
        logger.info(f"\n✅ Suppressed {total_suppressed} duplicate leads")
    else:
        logger.info(f"\n🔍 DRY RUN: Would suppress {total_suppressed} duplicate leads")
    
    return {
        "duplicates_found": len(duplicates),
        "leads_suppressed": total_suppressed
    }


def create_unique_constraints(dry_run=True):
    """
    Create unique constraints on email and phone columns.
    
    Note: This should be run AFTER cleaning up duplicates.
    
    Args:
        dry_run: If True, only show SQL that would be executed
    """
    from sqlalchemy import text
    
    sql_commands = [
        # Email unique constraint
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_email_unique ON leads(email) WHERE email IS NOT NULL;",
        # Phone unique constraint
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_phone_unique ON leads(phone) WHERE phone IS NOT NULL;",
    ]
    
    if dry_run:
        logger.info("\n🔍 DRY RUN: Would execute the following SQL:")
        for sql in sql_commands:
            logger.info(f"  {sql}")
    else:
        logger.info("\nCreating unique constraints...")
        with engine.connect() as conn:
            for sql in sql_commands:
                logger.info(f"  Executing: {sql}")
                conn.execute(text(sql))
                conn.commit()
        logger.info("✅ Unique constraints created")


def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup duplicate leads and add unique constraints")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the migration (default is dry-run)"
    )
    parser.add_argument(
        "--skip-constraints",
        action="store_true",
        help="Skip creating unique constraints"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        logger.warning("=" * 60)
        logger.warning("DRY RUN MODE - No changes will be made")
        logger.warning("Use --execute to actually apply changes")
        logger.warning("=" * 60)
    else:
        logger.warning("=" * 60)
        logger.warning("EXECUTING MIGRATION - Changes will be permanent")
        logger.warning("=" * 60)
        
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Migration cancelled")
            return
    
    # Run migration
    db = SessionLocal()
    
    try:
        # Step 1: Cleanup duplicates
        logger.info("\n" + "=" * 60)
        logger.info("Step 1: Cleanup Duplicate Emails")
        logger.info("=" * 60)
        
        stats = cleanup_duplicates(db, dry_run=dry_run)
        
        # Step 2: Create unique constraints (if duplicates were cleaned)
        if not args.skip_constraints:
            logger.info("\n" + "=" * 60)
            logger.info("Step 2: Create Unique Constraints")
            logger.info("=" * 60)
            
            if stats["duplicates_found"] == 0 or not dry_run:
                create_unique_constraints(dry_run=dry_run)
            else:
                logger.info("⏭️  Skipping constraint creation (run with --execute first)")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        logger.info(f"Duplicate emails found: {stats['duplicates_found']}")
        logger.info(f"Leads suppressed: {stats['leads_suppressed']}")
        
        if dry_run:
            logger.info("\n✨ Run with --execute to apply these changes")
        else:
            logger.info("\n✅ Migration complete!")
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
