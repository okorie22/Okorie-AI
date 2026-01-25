"""
CSV import script.
Import leads from a CSV file into the database.
"""
import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import SessionLocal
from src.ingestion.lead_processor import LeadProcessor
from loguru import logger


def import_csv(file_path: str):
    """Import leads from CSV file"""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return
    
    logger.info(f"Starting CSV import from: {file_path}")
    
    db = SessionLocal()
    try:
        processor = LeadProcessor(db)
        stats = processor.process_csv_file(file_path)
        
        logger.success("Import Summary:")
        logger.info(f"  Total rows: {stats['total_rows']}")
        logger.info(f"  Imported: {stats['imported']}")
        logger.info(f"  Duplicates: {stats['duplicates']}")
        logger.info(f"  Errors: {stats['errors']}")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import leads from CSV")
    parser.add_argument("file", help="Path to CSV file")
    args = parser.parse_args()
    
    import_csv(args.file)
