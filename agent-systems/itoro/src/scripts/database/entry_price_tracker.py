"""
Entry Price Tracker for Unrealized Gains Calculation

This module tracks entry prices for tokens to enable accurate unrealized gains analysis.
Uses SQLite database for efficient storage and retrieval.
"""

import os
import json
import sqlite3
import time
import requests
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

# Local imports with fallback for relative imports
try:
    from src.scripts.shared_services.logger import info, warning, error, debug
except ImportError:
    # Try relative imports when running from test directory
    from src.scripts.shared_services.logger import info, warning, error, debug

# Cloud database import
try:
    from src.scripts.database.cloud_database import get_cloud_database_manager
    CLOUD_DB_AVAILABLE = True
except ImportError:
    CLOUD_DB_AVAILABLE = False

# REST API fallback import
try:
    from src.scripts.database.cloud_database_rest import RestDatabaseManager
    REST_DB_AVAILABLE = True
except ImportError:
    REST_DB_AVAILABLE = False


@dataclass
class EntryPriceRecord:
    """Record of entry price for a token"""
    mint: str
    entry_price_usd: float
    entry_amount: float
    entry_timestamp: float
    last_updated: float
    source: str  # 'manual', 'auto_detected', 'imported', 'test_scenario'
    notes: str = ""


class EntryPriceTracker:
    """Tracks entry prices for tokens to calculate unrealized gains using SQLite"""
    
    def __init__(self, db_path: str = "src/data/entry_prices.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database with entry prices table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS entry_prices (
                        mint TEXT PRIMARY KEY,
                        entry_price_usd REAL NOT NULL,
                        entry_amount REAL NOT NULL,
                        entry_timestamp REAL NOT NULL,
                        last_updated REAL NOT NULL,
                        source TEXT NOT NULL,
                        notes TEXT DEFAULT ''
                    )
                ''')
                conn.commit()
                info(f"✅ Entry price database initialized at {self.db_path}", file_only=True)
        except Exception as e:
            error(f"Failed to initialize entry price database: {e}")
    
    def set_entry_price(self, mint: str, entry_price_usd: float, entry_amount: float, 
                       source: str = "manual", notes: str = "") -> bool:
        """Set or update entry price for a token in local database first, then sync to cloud database"""
        try:
            # Ensure proper decimal precision
            entry_price_usd = round(entry_price_usd, 6)
            entry_amount = round(entry_amount, 6)
            current_time = time.time()
            
            # PRIMARY: Save to local database first
            success = self._set_entry_price_to_local_db(mint, entry_price_usd, entry_amount, source, notes)
            if not success:
                error(f"❌ Failed to save entry price to local database: {mint[:8]}...")
                return False
            
            debug(f"✅ Entry price saved to local database: {mint[:8]}... = ${entry_price_usd:.6f}")
            
            # SECONDARY: Try to sync to cloud database
            if CLOUD_DB_AVAILABLE:
                try:
                    db_manager = get_cloud_database_manager()
                    if db_manager is None:
                        warning("⚠️ Cloud database not configured (local data saved)")
                        return True
                    
                    # Test if cloud database is actually working by trying a simple query
                    try:
                        test_query = "SELECT 1"
                        db_manager.execute_query(test_query, (), fetch=True)
                    except Exception as test_error:
                        # Cloud database is not working, but local save succeeded
                        warning(f"⚠️ Cloud database test failed (local data saved): {test_error}")
                        return True
                    
                    # Check if entry price already exists for average calculation
                    existing_query = '''
                        SELECT entry_price_usd, amount, value_usd FROM entry_prices 
                        WHERE token_mint = %s AND wallet_address = 'default'
                    '''
                    existing_result = db_manager.execute_query(existing_query, (mint,), fetch=True)
                    
                    if existing_result and len(existing_result) > 0:
                        # Calculate average entry price
                        existing_record = existing_result[0]
                        old_price = existing_record['entry_price_usd']
                        old_amount = existing_record['amount']
                        old_value = existing_record['value_usd']
                        
                        # Calculate new average
                        new_value = entry_price_usd * entry_amount
                        total_value = old_value + new_value
                        total_amount = old_amount + entry_amount
                        average_price = total_value / total_amount if total_amount > 0 else entry_price_usd
                        
                        # Update with average entry price
                        query = '''
                            UPDATE entry_prices SET
                                entry_price_usd = %s,
                                amount = %s,
                                value_usd = %s,
                                metadata = %s,
                                timestamp = NOW()
                            WHERE token_mint = %s AND wallet_address = 'default'
                        '''
                        params = (
                            average_price,
                            total_amount,
                            total_value,
                            json.dumps({
                                'source': source,
                                'notes': notes,
                                'entry_timestamp': current_time,
                                'last_updated': current_time,
                                'average_calculation': {
                                    'old_price': old_price,
                                    'old_amount': old_amount,
                                    'new_price': entry_price_usd,
                                    'new_amount': entry_amount,
                                    'average_price': average_price
                                }
                            }),
                            mint
                        )
                        debug(f"📊 Updated average entry price for {mint[:8]}...: ${average_price:.6f} (was ${old_price:.6f})")
                    else:
                        # New entry - no average needed
                        query = '''
                            INSERT INTO entry_prices (
                                token_mint, wallet_address, entry_price_usd, amount, value_usd, metadata
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        '''
                        params = (
                            mint,  # token_mint
                            'default',  # wallet_address
                            entry_price_usd,  # entry_price_usd
                            entry_amount,  # amount
                            entry_price_usd * entry_amount,  # value_usd
                            json.dumps({
                                'source': source,
                                'notes': notes,
                                'entry_timestamp': current_time,
                                'last_updated': current_time
                            })  # metadata
                        )
                        info(f"📝 Set new entry price for {mint[:8]}...: ${entry_price_usd:.6f}")
                    
                    db_manager.execute_query(query, params, fetch=False)
                    info(f"✅ Entry price synced to cloud database: {mint[:8]}... = ${entry_price_usd:.6f}")
                    
                except Exception as cloud_error:
                    warning(f"⚠️ Cloud database sync failed (local data saved): {cloud_error}")
            
            return True
            
        except Exception as e:
            error(f"Failed to set entry price for {mint}: {e}")
            return False
    
    def _set_entry_price_to_local_db(self, mint: str, entry_price_usd: float, entry_amount: float, 
                                    source: str = "manual", notes: str = "") -> bool:
        """Fallback method to set entry price in local database"""
        try:
            current_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                # Check if record exists and get current values
                cursor = conn.execute(
                    "SELECT entry_price_usd, entry_amount FROM entry_prices WHERE mint = ?",
                    (mint,)
                )
                existing_record = cursor.fetchone()
                
                if existing_record:
                    # Calculate average entry price
                    old_price, old_amount = existing_record
                    new_value = entry_price_usd * entry_amount
                    old_value = old_price * old_amount
                    total_value = old_value + new_value
                    total_amount = old_amount + entry_amount
                    average_price = total_value / total_amount if total_amount > 0 else entry_price_usd
                    
                    # Update with average entry price
                    conn.execute('''
                        UPDATE entry_prices 
                        SET entry_price_usd = ?, entry_amount = ?, last_updated = ?, source = ?, notes = ?
                        WHERE mint = ?
                    ''', (average_price, total_amount, current_time, source, notes, mint))
                    info(f"📊 Updated average entry price for {mint[:8]}...: ${average_price:.6f} (was ${old_price:.6f})")
                else:
                    # Create new record
                    conn.execute('''
                        INSERT INTO entry_prices 
                        (mint, entry_price_usd, entry_amount, entry_timestamp, last_updated, source, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (mint, entry_price_usd, entry_amount, current_time, current_time, source, notes))
                    info(f"📝 Set new entry price for {mint[:8]}...: ${entry_price_usd:.6f}")
                
                conn.commit()
            return True
            
        except Exception as e:
            error(f"Failed to set entry price in local database for {mint}: {e}")
            return False
    
    def get_entry_price(self, mint: str) -> Optional[EntryPriceRecord]:
        """Get entry price record for a token from cloud database first, with local fallback"""
        try:
            # Try cloud database first
            if CLOUD_DB_AVAILABLE:
                try:
                    db_manager = get_cloud_database_manager()
                    if db_manager:
                        # Test if cloud database is actually working
                        try:
                            test_query = "SELECT 1"
                            db_manager.execute_query(test_query, (), fetch=True)
                        except Exception as test_error:
                            # Cloud database is not working, fallback to local
                            debug(f"Cloud database test failed, using local: {test_error}")
                            raise Exception("Cloud database not working")
                        query = '''
                            SELECT token_mint, entry_price_usd, amount, value_usd, metadata, timestamp
                            FROM entry_prices 
                            WHERE token_mint = %s AND wallet_address = 'default'
                            ORDER BY timestamp DESC
                            LIMIT 1
                        '''
                        result = db_manager.execute_query(query, (mint,), fetch=True)
                        
                        if result and len(result) > 0:
                            row = result[0]
                            # metadata is already a dict when returned from PostgreSQL JSONB
                            metadata = row.get('metadata', {})
                            if isinstance(metadata, str):
                                metadata = json.loads(metadata)
                            
                            return EntryPriceRecord(
                                mint=row['token_mint'],
                                entry_price_usd=float(row['entry_price_usd']),
                                entry_amount=float(row['amount']),
                                entry_timestamp=metadata.get('entry_timestamp', time.time()),
                                last_updated=metadata.get('last_updated', time.time()),
                                source=metadata.get('source', 'cloud')
                            )
                except Exception as cloud_error:
                    debug(f"Cloud database read failed, trying REST API fallback: {cloud_error}")
                    # Try REST API fallback
                    if REST_DB_AVAILABLE:
                        try:
                            rest_manager = RestDatabaseManager()
                            rest_entry = rest_manager.get_entry_price(mint)
                            if rest_entry:
                                metadata = rest_entry.get('metadata', {})
                                if isinstance(metadata, str):
                                    metadata = json.loads(metadata)
                                
                                return EntryPriceRecord(
                                    mint=rest_entry['token_mint'],
                                    entry_price_usd=float(rest_entry['entry_price_usd']),
                                    entry_amount=float(rest_entry['amount']),
                                    entry_timestamp=metadata.get('entry_timestamp', time.time()),
                                    last_updated=metadata.get('last_updated', time.time()),
                                    source=metadata.get('source', 'rest')
                                )
                        except Exception as rest_error:
                            debug(f"REST API also failed, falling back to local: {rest_error}")
            
            # Fallback to local database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT mint, entry_price_usd, entry_amount, entry_timestamp, last_updated, source, notes FROM entry_prices WHERE mint = ?",
                    (mint,)
                )
                row = cursor.fetchone()
                
                if row:
                    return EntryPriceRecord(
                        mint=row[0],
                        entry_price_usd=row[1],
                        entry_amount=row[2],
                        entry_timestamp=row[3],
                        last_updated=row[4],
                        source=row[5]
                    )
                return None
                
        except Exception as e:
            error(f"Failed to get entry price for {mint}: {e}")
            return None
    
    def get_all_entry_prices(self) -> Dict[str, EntryPriceRecord]:
        """Get all entry price records"""
        try:
            entry_prices = {}
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT mint, entry_price_usd, entry_amount, entry_timestamp, last_updated, source, notes FROM entry_prices"
                )
                
                for row in cursor.fetchall():
                    record = EntryPriceRecord(
                        mint=row[0],
                        entry_price_usd=row[1],
                        entry_amount=row[2],
                        entry_timestamp=row[3],
                        last_updated=row[4],
                        source=row[5],
                        notes=row[6]
                    )
                    entry_prices[row[0]] = record
                    
            return entry_prices
            
        except Exception as e:
            error(f"Failed to get all entry prices: {e}")
            return {}
    
    def delete_entry_price(self, mint: str) -> bool:
        """Delete entry price record for a token"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM entry_prices WHERE mint = ?", (mint,))
                conn.commit()
                info(f"🗑️ Deleted entry price for {mint[:8]}...")
            return True
            
        except Exception as e:
            error(f"Failed to delete entry price for {mint}: {e}")
            return False
    
    def clear_all_entry_prices(self) -> bool:
        """Clear all entry price records"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM entry_prices")
                conn.commit()
                info("🗑️ Cleared all entry price records")
            return True
            
        except Exception as e:
            error(f"Failed to clear entry prices: {e}")
            return False
    
    def calculate_unrealized_gains(self, mint: str, current_price_usd: float, 
                                 current_amount: float) -> Optional[Dict]:
        """Calculate unrealized gains for a token"""
        try:
            entry_record = self.get_entry_price(mint)
            if not entry_record:
                return None
            
            # Calculate gains
            entry_value = entry_record.entry_price_usd * entry_record.entry_amount
            current_value = current_price_usd * current_amount
            
            if entry_value <= 0:
                return None
            
            gain_usd = current_value - entry_value
            gain_percentage = (gain_usd / entry_value) * 100
            
            return {
                'mint': mint,
                'entry_price_usd': entry_record.entry_price_usd,
                'entry_amount': entry_record.entry_amount,
                'entry_value_usd': entry_value,
                'current_price_usd': current_price_usd,
                'current_amount': current_amount,
                'current_value_usd': current_value,
                'gain_usd': gain_usd,
                'gain_percentage': gain_percentage,
                'days_held': (time.time() - entry_record.entry_timestamp) / 86400
            }
            
        except Exception as e:
            error(f"Failed to calculate unrealized gains for {mint}: {e}")
            return None
    
    def auto_detect_entry_prices(self, wallet_data: List[Dict], price_service) -> int:
        """Automatically detect entry prices for tokens without them"""
        try:
            detected_count = 0
            current_time = time.time()
            
            for token_data in wallet_data:
                mint = token_data.get('mint')
                if not mint or self.get_entry_price(mint):
                    continue
                
                # Try to get current price
                current_price = price_service.get_price(mint)
                if not current_price:
                    continue
                
                # For new tokens, assume they were bought at current market price
                # This is a reasonable assumption for recently acquired tokens
                amount = token_data.get('amount', 0)
                if amount > 0:
                    self.set_entry_price(
                        mint=mint,
                        entry_price_usd=current_price,
                        entry_amount=amount,
                        source="auto_detected",
                        notes="Auto-detected from wallet balance"
                    )
                    detected_count += 1
                    
            info(f"🔍 Auto-detected {detected_count} new entry prices")
            return detected_count
            
        except Exception as e:
            error(f"Failed to auto-detect entry prices: {e}")
            return 0
    
    def get_entry_price_summary(self) -> Dict:
        """Get summary statistics of entry prices"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM entry_prices")
                total_count = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(DISTINCT source) FROM entry_prices")
                source_count = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT MIN(entry_timestamp), MAX(entry_timestamp) FROM entry_prices")
                time_range = cursor.fetchone()
                
                return {
                    'total_records': total_count,
                    'unique_sources': source_count,
                    'oldest_record': time_range[0] if time_range[0] else None,
                    'newest_record': time_range[1] if time_range[1] else None,
                    'database_path': str(self.db_path)
                }
                
        except Exception as e:
            error(f"Failed to get entry price summary: {e}")
            return {}


# Global instance and getter function
_entry_price_tracker_instance = None

def get_entry_price_tracker() -> 'EntryPriceTracker':
    """Get the global entry price tracker instance"""
    global _entry_price_tracker_instance
    if _entry_price_tracker_instance is None:
        _entry_price_tracker_instance = EntryPriceTracker()
    return _entry_price_tracker_instance
