"""
Direct SQLite migration to add job_title column.
Run this when the system is stopped.
"""
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).resolve().parents[1] / "iul_appointment_setter.db"

def migrate():
    """Add job_title column using direct SQL execution"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(leads)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'job_title' in columns:
            print("✓ job_title column already exists")
            return
        
        # Add the column
        print("Adding job_title column...")
        cursor.execute("ALTER TABLE leads ADD COLUMN job_title VARCHAR(255)")
        conn.commit()
        print("✓ Migration complete! job_title column added.")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
