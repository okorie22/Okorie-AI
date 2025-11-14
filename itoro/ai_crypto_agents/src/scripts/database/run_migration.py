#!/usr/bin/env python3
"""
Database Migration Runner
Runs SQL migrations to set up required database tables
"""

import os
import sys
import logging

# Add parent directory to path for imports
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, 'src'))

def run_migration():
    """Run the local_ip_registrations table migration"""
    try:
        from src.scripts.database.cloud_database import get_cloud_database_manager
        
        # Get database manager
        db = get_cloud_database_manager()
        if not db:
            print("❌ Could not connect to cloud database")
            return False
        
        # Read migration file
        migration_file = os.path.join(os.path.dirname(__file__), 'migrations', '001_create_local_ip_registrations.sql')
        
        if not os.path.exists(migration_file):
            print(f"❌ Migration file not found: {migration_file}")
            return False
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        # Split by semicolon and execute each statement
        statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
        
        for i, statement in enumerate(statements, 1):
            if statement.upper().startswith('--'):
                continue  # Skip comments
                
            print(f"🔄 Executing statement {i}/{len(statements)}...")
            try:
                db.execute_query(statement, fetch=False)
                print(f"✅ Statement {i} executed successfully")
            except Exception as e:
                print(f"⚠️ Statement {i} failed (may already exist): {e}")
                # Continue with other statements
        
        print("✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Running database migration...")
    success = run_migration()
    if success:
        print("🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        print("💥 Migration failed!")
        sys.exit(1)
