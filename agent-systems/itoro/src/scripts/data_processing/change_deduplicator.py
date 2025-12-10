"""
🌙 Anarcho Capital's Change Deduplicator
Prevents duplicate trade executions from false positive change detections
Built with love by Anarcho Capital 🚀
"""

import threading
import time
import hashlib
import json
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from src.scripts.shared_services.logger import debug, info, warning, error

@dataclass
class ChangeEvent:
    """Represents a detected change event"""
    wallet_address: str
    token_address: str
    change_type: str  # 'new', 'removed', 'modified'
    amount_change: float
    percentage_change: float
    usd_change: Optional[float]
    timestamp: datetime
    fingerprint: str

class ChangeDeduplicator:
    """
    Deduplicates change events to prevent false positive trading
    Maintains a sliding window of recent changes and filters duplicates
    """
    
    def __init__(self):
        self.recent_changes: Dict[str, ChangeEvent] = {}  # fingerprint -> ChangeEvent
        self.processed_changes: Set[str] = set()  # Set of processed fingerprints
        self.change_lock = threading.RLock()
        
        # Configuration
        self.dedup_window_minutes = 5  # Consider changes within 5 minutes as potential duplicates
        self.cleanup_interval_seconds = 300  # Clean up old entries every 5 minutes
        self.min_time_between_same_changes = 60  # Minimum seconds between identical changes
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_active = True
        self.cleanup_thread.start()
        
        info("Change Deduplicator initialized")
    
    def create_change_fingerprint(self, wallet_address: str, token_address: str, 
                                change_type: str, amount_change: float, 
                                percentage_change: float) -> str:
        """Create a unique fingerprint for a change event"""
        # Round values to avoid floating point precision issues
        rounded_amount = round(amount_change, 6)
        rounded_percentage = round(percentage_change, 2)
        
        # Create string representation
        change_data = f"{wallet_address}:{token_address}:{change_type}:{rounded_amount}:{rounded_percentage}"
        
        # Create hash fingerprint
        fingerprint = hashlib.md5(change_data.encode()).hexdigest()[:16]
        return fingerprint
    
    def is_duplicate_change(self, wallet_address: str, token_address: str, 
                          change_type: str, amount_change: float, 
                          percentage_change: float, usd_change: Optional[float] = None) -> bool:
        """
        Check if this change is a duplicate of a recent change
        
        Returns:
            True if this is a duplicate that should be ignored
            False if this is a new/valid change
        """
        try:
            current_time = datetime.now()
            
            # Create fingerprint for this change
            fingerprint = self.create_change_fingerprint(
                wallet_address, token_address, change_type, amount_change, percentage_change
            )
            
            with self.change_lock:
                # Check if we've seen this exact change recently
                if fingerprint in self.recent_changes:
                    previous_change = self.recent_changes[fingerprint]
                    time_diff = (current_time - previous_change.timestamp).total_seconds()
                    
                    if time_diff < self.min_time_between_same_changes:
                        debug(f"Duplicate change detected for {token_address[:8]}... in {wallet_address[:8]}... "
                              f"(last seen {time_diff:.1f}s ago)", file_only=True)
                        return True
                
                # Check for similar changes (different fingerprint but similar parameters)
                for existing_fingerprint, existing_change in self.recent_changes.items():
                    if (existing_change.wallet_address == wallet_address and 
                        existing_change.token_address == token_address and
                        existing_change.change_type == change_type):
                        
                        time_diff = (current_time - existing_change.timestamp).total_seconds()
                        
                        # If within dedup window, check similarity
                        if time_diff < self.dedup_window_minutes * 60:
                            # Check if changes are similar (within tolerance)
                            if self._are_changes_similar(existing_change, amount_change, percentage_change, usd_change):
                                debug(f"Similar change detected for {token_address[:8]}... in {wallet_address[:8]}... "
                                      f"(similar change {time_diff:.1f}s ago)", file_only=True)
                                return True
                
                # Record this change
                change_event = ChangeEvent(
                    wallet_address=wallet_address,
                    token_address=token_address,
                    change_type=change_type,
                    amount_change=amount_change,
                    percentage_change=percentage_change,
                    usd_change=usd_change,
                    timestamp=current_time,
                    fingerprint=fingerprint
                )
                
                self.recent_changes[fingerprint] = change_event
                debug(f"Recorded new change: {token_address[:8]}... in {wallet_address[:8]}... "
                      f"({change_type}, {percentage_change:.2f}%)", file_only=True)
                
                return False
                
        except Exception as e:
            error(f"Error in duplicate change detection: {str(e)}")
            # On error, allow the change (better to have false positives than miss real changes)
            return False
    
    def _are_changes_similar(self, existing_change: ChangeEvent, new_amount_change: float, 
                           new_percentage_change: float, new_usd_change: Optional[float]) -> bool:
        """Check if two changes are similar enough to be considered duplicates"""
        
        # Check percentage change similarity (within 1%)
        percentage_diff = abs(existing_change.percentage_change - new_percentage_change)
        if percentage_diff > 1.0:
            return False
        
        # Check amount change similarity (within 10% of the larger value)
        if existing_change.amount_change != 0 and new_amount_change != 0:
            larger_amount = max(abs(existing_change.amount_change), abs(new_amount_change))
            amount_diff = abs(existing_change.amount_change - new_amount_change)
            amount_tolerance = larger_amount * 0.1
            
            if amount_diff > amount_tolerance:
                return False
        
        # Check USD change similarity if both are available
        if (existing_change.usd_change is not None and new_usd_change is not None and
            existing_change.usd_change != 0 and new_usd_change != 0):
            
            larger_usd = max(abs(existing_change.usd_change), abs(new_usd_change))
            usd_diff = abs(existing_change.usd_change - new_usd_change)
            usd_tolerance = larger_usd * 0.1
            
            if usd_diff > usd_tolerance:
                return False
        
        return True
    
    def mark_change_processed(self, wallet_address: str, token_address: str, 
                            change_type: str, amount_change: float, percentage_change: float):
        """Mark a change as processed to prevent reprocessing"""
        fingerprint = self.create_change_fingerprint(
            wallet_address, token_address, change_type, amount_change, percentage_change
        )
        
        with self.change_lock:
            self.processed_changes.add(fingerprint)
    
    def is_change_processed(self, wallet_address: str, token_address: str, 
                          change_type: str, amount_change: float, percentage_change: float) -> bool:
        """Check if a change has already been processed"""
        fingerprint = self.create_change_fingerprint(
            wallet_address, token_address, change_type, amount_change, percentage_change
        )
        
        with self.change_lock:
            return fingerprint in self.processed_changes
    
    def _cleanup_worker(self):
        """Background worker to clean up old change records"""
        while self.cleanup_active:
            try:
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(minutes=self.dedup_window_minutes * 2)  # Keep 2x window for safety
                
                with self.change_lock:
                    # Clean up old changes
                    old_fingerprints = [
                        fp for fp, change in self.recent_changes.items()
                        if change.timestamp < cutoff_time
                    ]
                    
                    for fp in old_fingerprints:
                        del self.recent_changes[fp]
                    
                    # Clean up old processed changes (keep more history for these)
                    processed_cutoff = current_time - timedelta(hours=1)  # Keep 1 hour of processed changes
                    # Note: We can't easily clean processed_changes since they don't have timestamps
                    # This is acceptable as the set won't grow too large in practice
                    
                    if old_fingerprints:
                        debug(f"Cleaned up {len(old_fingerprints)} old change records", file_only=True)
                
                time.sleep(self.cleanup_interval_seconds)
                
            except Exception as e:
                error(f"Error in change deduplicator cleanup: {str(e)}")
                time.sleep(60)  # Wait longer on error
    
    def get_recent_changes_summary(self) -> Dict[str, Any]:
        """Get summary of recent changes for monitoring"""
        with self.change_lock:
            return {
                'recent_changes_count': len(self.recent_changes),
                'processed_changes_count': len(self.processed_changes),
                'oldest_change': min(change.timestamp for change in self.recent_changes.values()).isoformat() if self.recent_changes else None,
                'newest_change': max(change.timestamp for change in self.recent_changes.values()).isoformat() if self.recent_changes else None
            }
    
    def stop(self):
        """Stop the deduplicator"""
        self.cleanup_active = False
        if self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)

# Global instance
_change_deduplicator = None

def get_change_deduplicator() -> ChangeDeduplicator:
    """Get the global change deduplicator instance"""
    global _change_deduplicator
    if _change_deduplicator is None:
        _change_deduplicator = ChangeDeduplicator()
    return _change_deduplicator 
