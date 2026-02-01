"""
Add email_deliverable and email_verification_status columns to leads table.

Run this once to update your existing database schema.
Supports both SQLite and Postgres (DATABASE_URL).
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from src.storage.database import engine, DATABASE_URL
from loguru import logger


def column_exists_sqlite(conn, name: str) -> bool:
    result = conn.execute(text(
        "SELECT COUNT(*) as cnt FROM pragma_table_info('leads') WHERE name=:name"
    ), {"name": name})
    return result.fetchone()[0] > 0


def column_exists_postgres(conn, name: str) -> bool:
    result = conn.execute(text(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = :name
        """
    ), {"name": name})
    return result.fetchone()[0] > 0


def migrate():
    """Add email_deliverable and email_verification_status columns if they don't exist."""
    is_sqlite = DATABASE_URL.startswith("sqlite")

    with engine.connect() as conn:
        if is_sqlite:
            col_exists = lambda n: column_exists_sqlite(conn, n)
        else:
            col_exists = lambda n: column_exists_postgres(conn, n)

        if col_exists("email_deliverable") and col_exists("email_verification_status"):
            logger.info("email_deliverable and email_verification_status already exist, skipping migration")
            return

        if not col_exists("email_deliverable"):
            logger.info("Adding email_deliverable column to leads table...")
            if is_sqlite:
                conn.execute(text("ALTER TABLE leads ADD COLUMN email_deliverable BOOLEAN"))
            else:
                conn.execute(text("ALTER TABLE leads ADD COLUMN email_deliverable BOOLEAN"))
            conn.commit()
            logger.info("email_deliverable column added.")
        else:
            logger.info("email_deliverable already exists, skipping.")

        if not col_exists("email_verification_status"):
            logger.info("Adding email_verification_status column to leads table...")
            if is_sqlite:
                conn.execute(text("ALTER TABLE leads ADD COLUMN email_verification_status VARCHAR(50)"))
            else:
                conn.execute(text("ALTER TABLE leads ADD COLUMN email_verification_status VARCHAR(50)"))
            conn.commit()
            logger.info("email_verification_status column added.")
        else:
            logger.info("email_verification_status already exists, skipping.")

    logger.success("Migration complete! email_deliverable and email_verification_status ready.")


if __name__ == "__main__":
    migrate()
