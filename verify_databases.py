#!/usr/bin/env python3
"""
🔍 ITORO Database Verification Script
Verifies connectivity to both cloud and local databases
"""

import os
import sqlite3
import sys

def check_env_vars():
    """Check environment variables"""
    print("=== ENVIRONMENT VARIABLES ===")
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE')

    print(f"SUPABASE_URL: {'✅ SET' if supabase_url else '❌ NOT SET'}")
    print(f"SUPABASE_SERVICE_ROLE: {'✅ SET' if supabase_key else '❌ NOT SET'}")

    if supabase_url:
        print(f"  URL: {supabase_url}")

    return bool(supabase_url and supabase_key)

def check_local_database():
    """Check local SQLite database"""
    print("\n=== LOCAL DATABASE (SQLite) ===")

    db_paths = [
        'multi-agents/itoro/ai_crypto_agents/data/paper_trading.db',
        'multi-agents/itoro/ai_crypto_agents/src/data/paper_trading.db'
    ]

    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f"✅ Database file exists: {db_path}")
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()

                print(f"📊 Found {len(tables)} tables:")
                for table_name, in tables:
                    print(f"  - {table_name}")

                    # Check if table has data (sample first 3 rows)
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        print(f"    Records: {count}")
                    except:
                        print("    Records: N/A"

                conn.close()
                return True

            except Exception as e:
                print(f"❌ Database error: {e}")
                return False

        else:
            print(f"❌ Database file not found: {db_path}")

    return False

def check_cloud_database():
    """Check cloud database connectivity"""
    print("\n=== CLOUD DATABASE (Supabase) ===")

    try:
        sys.path.append('multi-agents/itoro/ai_crypto_agents/src')

        from scripts.database.cloud_database import CloudDatabaseManager

        print("🔌 Attempting cloud database connection...")
        db = CloudDatabaseManager()

        # Try a simple query
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Check portfolio_history table
            cursor.execute("SELECT COUNT(*) FROM portfolio_history")
            count = cursor.fetchone()[0]
            print(f"✅ portfolio_history table: {count} records")

            # Check portfolio_balances table
            cursor.execute("SELECT COUNT(*) FROM portfolio_balances")
            count = cursor.fetchone()[0]
            print(f"✅ portfolio_balances table: {count} records")

            # Check whale_data table
            cursor.execute("SELECT COUNT(*) FROM whale_data")
            count = cursor.fetchone()[0]
            print(f"✅ whale_data table: {count} records")

        print("✅ Cloud database connection: SUCCESS")
        return True

    except Exception as e:
        print(f"❌ Cloud database connection failed: {e}")
        return False

def check_eliza_config():
    """Check Eliza configuration"""
    print("\n=== ELIZA CONFIGURATION ===")

    # Check .env file
    env_file = '.env'
    if os.path.exists(env_file):
        print("✅ .env file exists")

        with open(env_file, 'r') as f:
            content = f.read()

        env_vars = {
            'PAPER_TRADING_DB_PATH': 'multi-agents/itoro/ai_crypto_agents/data/paper_trading.db',
            'SUPABASE_URL': None,
            'SUPABASE_SERVICE_ROLE': None
        }

        for var in env_vars:
            if var in content:
                print(f"✅ {var}: CONFIGURED")
            else:
                print(f"❌ {var}: NOT FOUND")

    else:
        print("❌ .env file not found")

def main():
    """Main verification function"""
    print("🔍 ITORO Database Verification")
    print("=" * 50)

    # Check environment
    env_ok = check_env_vars()

    # Check local database
    local_ok = check_local_database()

    # Check cloud database
    cloud_ok = check_cloud_database() if env_ok else False

    # Check Eliza config
    check_eliza_config()

    # Summary
    print("\n" + "=" * 50)
    print("📊 VERIFICATION SUMMARY")
    print(f"Environment Variables: {'✅' if env_ok else '❌'}")
    print(f"Local Database: {'✅' if local_ok else '❌'}")
    print(f"Cloud Database: {'✅' if cloud_ok else '❌'}")

    if local_ok and cloud_ok:
        print("\n🎉 ALL DATABASES CONNECTED SUCCESSFULLY!")
        print("Your Eliza ITORO bridge should now access real trading data.")
    else:
        print("\n⚠️  Some databases are not connected.")
        if not local_ok:
            print("  - Initialize local database: Run ITORO system first")
        if not cloud_ok:
            print("  - Check Supabase credentials in .env file")

if __name__ == "__main__":
    main()
