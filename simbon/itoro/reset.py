#!/usr/bin/env python3
"""
Simple Database Reset Script
Resets paper trading database to clean state
"""

import os
from src.scripts.database.database_reset_manager import reset_paper_trading_database
from src.scripts.shared_services.logger import info

def backup_trading_system_log():
    """Backup trading_system.log to cloud database before clearing"""
    log_path = os.path.join('logs', 'trading_system.log')
    
    if os.path.exists(log_path):
        try:
            file_size = os.path.getsize(log_path)
            # Skip backup if log is too large (> 50MB) to avoid database issues
            if file_size > 50 * 1024 * 1024:  # 50MB
                print(f"⚠️ Log file too large ({file_size / (1024*1024):.2f} MB) - skipping backup")
                return True
            
            from src.scripts.database.cloud_database import get_cloud_database_manager
            db_manager = get_cloud_database_manager()
            
            if db_manager:
                print(f"📦 Backing up trading_system.log ({file_size / (1024*1024):.2f} MB)...")
                success = db_manager.save_log_backup(log_path, backup_type='reset')
                if success:
                    print("✅ Log backup saved to cloud database")
                else:
                    print("⚠️ Log backup failed - continuing anyway")
                return True
            else:
                print("⚠️ Cloud database not available - skipping log backup")
                return True
        except Exception as e:
            print(f"⚠️ Could not backup log: {e} - continuing anyway")
            return True
    else:
        print("ℹ️ trading_system.log not found - skipping backup")
        return True

def clear_trading_system_log():
    """Clear trading_system.log if it exists"""
    log_path = os.path.join('logs', 'trading_system.log')

    if os.path.exists(log_path):
        try:
            # Get file size for logging
            file_size = os.path.getsize(log_path) / (1024 * 1024)  # Convert to MB
            print(f"🧹 Clearing trading_system.log ({file_size:.2f} MB)")

            # Clear the log file by truncating it
            with open(log_path, 'w') as f:
                f.write('')

            print("✅ trading_system.log cleared successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to clear trading_system.log: {e}")
            return False
    else:
        print("ℹ️ trading_system.log not found - skipping")
        return True

def clear_defi_positions_database():
    """Clear DeFi positions database tables"""
    import sqlite3

    defi_db_path = os.path.join('src', 'data', 'defi_positions.db')

    if os.path.exists(defi_db_path):
        try:
            # Get file size for logging
            file_size = os.path.getsize(defi_db_path) / (1024 * 1024)  # Convert to MB
            print(f"🧹 Clearing DeFi positions database ({file_size:.2f} MB)")

            # Connect and clear tables
            conn = sqlite3.connect(defi_db_path, timeout=10, check_same_thread=False)
            cursor = conn.cursor()

            # Clear DeFi tables
            defi_tables = ['defi_positions', 'defi_loops', 'reserved_balances']
            for table in defi_tables:
                try:
                    cursor.execute(f"DELETE FROM {table}")
                    print(f"  ✅ Cleared table: {table}")
                except Exception as e:
                    print(f"  ⚠️ Could not clear table {table}: {e}")

            conn.commit()
            conn.close()

            print("✅ DeFi positions database cleared successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to clear DeFi positions database: {e}")
            return False
    else:
        print("ℹ️ DeFi positions database not found - skipping")
        return True

if __name__ == "__main__":
    print("🔄 Resetting paper trading database...")
    
    # Step 1: Backup trading_system.log to cloud
    print("\nStep 1: Backing up trading_system.log to cloud...")
    backup_trading_system_log()
    
    # Step 2: Clear trading_system.log
    print("\nStep 2: Clearing trading_system.log...")
    clear_trading_system_log()

    # Step 3: Clear DeFi positions database
    print("\nStep 3: Clearing DeFi positions database...")
    clear_defi_positions_database()

    # Step 4: Reset database
    print("\nStep 4: Resetting database...")
    success = reset_paper_trading_database()
    
    if success:
        print("\n✅ Reset complete")
    else:
        print("\n❌ Reset failed")
