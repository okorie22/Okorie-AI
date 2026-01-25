"""
Database setup script.
Initialize the database and create all tables.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import init_db, engine
from src.storage.models import Base
from loguru import logger


def setup_database():
    """Create all tables in the database"""
    logger.info("Starting database setup...")
    
    try:
        # Create all tables
        logger.info(f"Creating tables using engine: {engine.url}")
        Base.metadata.create_all(bind=engine)
        logger.success("Database tables created successfully!")
        
        # List all tables
        logger.info("Created tables:")
        for table_name in Base.metadata.tables.keys():
            logger.info(f"  - {table_name}")
        
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        raise


if __name__ == "__main__":
    setup_database()
