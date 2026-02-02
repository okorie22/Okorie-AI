"""
Add email_verified_at column to leads table (for verified-recently gate).
Run once: python scripts/migrate_add_email_verified_at.py
Supports SQLite and Postgres.
"""
import sys
from pathlib import Path

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
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'leads' AND column_name = :name"
    ), {"name": name})
    return result.fetchone()[0] > 0


def migrate():
    is_sqlite = DATABASE_URL.startswith("sqlite")
    with engine.connect() as conn:
        col_exists = column_exists_sqlite if is_sqlite else column_exists_postgres
        if col_exists(conn, "email_verified_at"):
            logger.info("email_verified_at already exists, skipping")
            return
        logger.info("Adding email_verified_at column...")
        if is_sqlite:
            conn.execute(text("ALTER TABLE leads ADD COLUMN email_verified_at TIMESTAMP"))
        else:
            conn.execute(text("ALTER TABLE leads ADD COLUMN email_verified_at TIMESTAMP WITH TIME ZONE"))
        conn.commit()
    logger.success("Migration complete: email_verified_at added.")


if __name__ == "__main__":
    migrate()
