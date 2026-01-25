"""
Add job_title column to leads table.

Run this once to update your existing database schema.
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from src.storage.database import engine
from loguru import logger


def migrate():
    """Add job_title column to leads table if it doesn't exist"""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text(
            "SELECT COUNT(*) as cnt FROM pragma_table_info('leads') WHERE name='job_title'"
        ))
        exists = result.fetchone()[0] > 0
        
        if exists:
            logger.info("job_title column already exists, skipping migration")
            return
        
        # Add the column
        logger.info("Adding job_title column to leads table...")
        conn.execute(text(
            "ALTER TABLE leads ADD COLUMN job_title VARCHAR(255)"
        ))
        conn.commit()
        logger.success("Migration complete! job_title column added.")


if __name__ == "__main__":
    migrate()
