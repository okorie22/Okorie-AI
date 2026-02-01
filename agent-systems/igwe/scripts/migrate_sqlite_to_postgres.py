"""
Migrate all data from local SQLite to PostgreSQL.

Use this when switching DATABASE_URL to Postgres so that existing local data
(leads, conversations, inbound/outbound messages, appointments, etc.) is
available in Postgres and visible on the VM dashboard.

Prerequisites:
  - Local SQLite DB has data (e.g. iul_appointment_setter.db).
  - Postgres DB exists. If it already has rows, use --truncate to wipe and replace.
  - Set TARGET_DATABASE_URL or DATABASE_URL in .env to your full Postgres URL.

Run from the igwe project root (agent-systems/igwe):

  cd agent-systems/igwe
  python scripts/migrate_sqlite_to_postgres.py

If Postgres already has data (duplicate key error), run:

  python scripts/migrate_sqlite_to_postgres.py --truncate

That truncates all Postgres tables then copies everything from SQLite (all
inbound parse messages and other data are preserved in SQLite and copied over).

After migration, set DATABASE_URL to the Postgres URL in .env (local and VM).
"""
import argparse
import os
import sys
from pathlib import Path

# Add project root (igwe) to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from loguru import logger

from src.storage.database import Base
from src.storage import models  # noqa: F401 - register all models


# Tables in dependency order (parents before children)
MIGRATION_ORDER = [
    models.Lead,
    models.Suppression,
    models.LeadScore,
    models.LeadEnrichment,
    models.Conversation,
    models.Event,
    models.Message,
    models.Appointment,
    models.UnmatchedAppointment,
    models.Deal,
    models.LeadSourceRun,
]

# Reverse order for truncate (children first) so CASCADE works cleanly
TRUNCATE_ORDER = [m.__tablename__ for m in reversed(MIGRATION_ORDER)]


def get_attr_names(model_class):
    """Return list of mapper column attribute names for copying row data."""
    return list(model_class.__mapper__.columns.keys())


def copy_table(source_session, target_session, model_class):
    """Copy all rows from source to target, preserving IDs. Returns count."""
    attr_names = get_attr_names(model_class)
    rows = source_session.query(model_class).order_by(model_class.id).all()
    count = 0
    for row in rows:
        new_row = model_class()
        for attr in attr_names:
            setattr(new_row, attr, getattr(row, attr))
        target_session.add(new_row)
        count += 1
    return count


def reset_postgres_sequence(engine, table_name: str, pk_column: str = "id"):
    """Set the sequence for table_name.id to max(id)+1 so future inserts work."""
    # table_name/pk_column are from our model __tablename__, not user input
    sql = text(
        f"SELECT setval(pg_get_serial_sequence('{table_name}', '{pk_column}'), "
        f"COALESCE((SELECT MAX({pk_column}) FROM {table_name}), 1))"
    )
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()


def truncate_postgres_tables(engine):
    """Truncate all app tables on Postgres (children first, RESTART IDENTITY CASCADE)."""
    tables_str = ", ".join(TRUNCATE_ORDER)
    sql = text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE")
    with engine.connect() as conn:
        conn.execute(sql)
        conn.commit()
    logger.info("Truncated all existing Postgres tables.")


def run_migration(source_url: str, target_url: str, truncate_first: bool = False):
    """Create target tables, copy data from source to target, reset sequences."""
    # Engines
    source_kw = {}
    if source_url.startswith("sqlite"):
        source_kw["connect_args"] = {"check_same_thread": False, "timeout": 30}
    source_engine = create_engine(source_url, **source_kw)
    target_engine = create_engine(target_url, pool_pre_ping=True)

    # Create all tables on target
    logger.info("Creating tables on Postgres (if not exist)...")
    Base.metadata.create_all(bind=target_engine)

    if truncate_first:
        truncate_postgres_tables(target_engine)

    source_session = sessionmaker(bind=source_engine)()
    target_session = sessionmaker(bind=target_engine)()

    try:
        for model_class in MIGRATION_ORDER:
            table_name = model_class.__tablename__
            count = copy_table(source_session, target_session, model_class)
            target_session.commit()
            if count > 0:
                logger.info(f"  {table_name}: {count} rows")
                try:
                    reset_postgres_sequence(target_engine, table_name)
                except Exception as e:
                    logger.warning(f"  Could not reset sequence for {table_name}: {e}")
        logger.success("Migration complete. Postgres now has all data from SQLite.")
    finally:
        source_session.close()
        target_session.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    default_sqlite = "sqlite:///" + str(PROJECT_ROOT / "iul_appointment_setter.db").replace("\\", "/")
    parser.add_argument(
        "--source",
        default=os.getenv("MIGRATE_SOURCE_URL", default_sqlite),
        help="Source DB URL (SQLite). Default: igwe/iul_appointment_setter.db",
    )
    parser.add_argument(
        "--target",
        default=os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL"),
        help="Target DB URL (Postgres). Default: TARGET_DATABASE_URL or DATABASE_URL from .env",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate all Postgres tables before copying (use when Postgres already has data and you want to replace with SQLite data).",
    )
    args = parser.parse_args()

    if not args.target or not args.target.strip().startswith("postgresql"):
        logger.error(
            "Postgres target URL required. Set TARGET_DATABASE_URL or DATABASE_URL in .env to your Postgres URL, "
            "or pass --target 'postgresql://...'"
        )
        sys.exit(1)

    # Require a full URL: postgresql://user:pass@host/dbname (host must have a domain to resolve)
    target = args.target.strip()
    if "@" not in target or target.count("/") < 3:
        logger.error(
            "DATABASE_URL must be the full Postgres URL, e.g. postgresql://USER:PASSWORD@HOST/DBNAME. "
            "Get it from your provider (Render: Database → Connect → External Database URL; Neon: Connection string)."
        )
        sys.exit(1)
    # Warn if host looks like a short Render/Neon ID (won't resolve without domain)
    if "@" in target:
        host_part = target.split("@")[1].split("/")[0].split(":")[0]
        if host_part.startswith("dpg-") and "." not in host_part:
            logger.warning(
                f"Host '{host_part}' has no domain and may not resolve. "
                "Use the full external URL from your provider (e.g. dpg-xxx.oregon-postgres.render.com)."
            )

    logger.info(f"Source: {args.source.split('@')[-1] if '@' in args.source else args.source}")
    logger.info(f"Target: {args.target.split('@')[-1] if '@' in args.target else args.target}")
    if args.truncate:
        logger.warning("--truncate: existing Postgres data will be wiped, then replaced with SQLite data.")
    try:
        run_migration(args.source, args.target, truncate_first=args.truncate)
    except Exception as e:
        if "could not translate host name" in str(e) or "Name or service not known" in str(e):
            logger.error(
                "Could not resolve Postgres host. Your DATABASE_URL must use the **full external hostname** "
                "(e.g. dpg-xxx.oregon-postgres.render.com), not the short ID (dpg-xxx). "
                "Get the full URL from: Render → your DB → Connect → External Database URL; or Neon → Connection string."
            )
        raise


if __name__ == "__main__":
    main()
