"""
OI Agent Local Storage Manager
Handles efficient Parquet-based storage for Open Interest data
Built with love by Anarcho Capital 🚀
"""

import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import traceback

# Import logger
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
except ImportError:
    def debug(msg, file_only=False):
        if not file_only:
            print(f"DEBUG: {msg}")
    def info(msg):
        print(f"INFO: {msg}")
    def warning(msg):
        print(f"WARNING: {msg}")
    def error(msg):
        print(f"ERROR: {msg}")

# Get project root (ai_crypto_agents/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class OIStorage:
    """Local Parquet-based storage for OI data"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize OI storage manager"""
        if data_dir is None:
            self.data_dir = PROJECT_ROOT / "src" / "data" / "oi"
        else:
            self.data_dir = Path(data_dir)
        
        # Create directory if it doesn't exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        info(f"📂 OI Storage initialized at: {self.data_dir}")
        
    def save_oi_snapshot(self, oi_data: List[Dict]) -> bool:
        """
        Save OI snapshot to Parquet file
        
        Args:
            oi_data: List of OI records with timestamp, symbol, open_interest, etc.
            
        Returns:
            bool: Success status
        """
        try:
            if not oi_data:
                warning("No OI data to save")
                return False
            
            # Convert to DataFrame
            df = pd.DataFrame(oi_data)
            
            # Ensure timestamp is datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Get current date for filename
            current_date = datetime.now().date()
            filename = f"oi_{current_date.strftime('%Y%m%d')}.parquet"
            filepath = self.data_dir / filename
            
            # If file exists, append to it
            if filepath.exists():
                try:
                    existing_df = pd.read_parquet(filepath)
                    # Check if the file is empty/corrupted
                    if existing_df.empty:
                        warning(f"Existing file {filename} is empty, creating new file")
                    else:
                        df = pd.concat([existing_df, df], ignore_index=True)
                        # Remove duplicates based on timestamp and symbol
                        df = df.drop_duplicates(subset=['timestamp', 'symbol'], keep='last')
                except Exception as e:
                    error(f"Failed to read existing file {filename}: {str(e)}, creating new file")
                    # File is corrupted, we'll overwrite it
            
            # Save to Parquet
            df.to_parquet(filepath, engine='pyarrow', compression='snappy', index=False)
            info(f"✅ Saved {len(oi_data)} OI records to {filename}")
            
            return True
            
        except Exception as e:
            error(f"Failed to save OI snapshot: {str(e)}")
            error(traceback.format_exc())
            return False
    
    def load_history(self, days: int = 30) -> Optional[pd.DataFrame]:
        """
        Load historical OI data from local Parquet files
        
        Args:
            days: Number of days of history to load
            
        Returns:
            DataFrame with historical OI data or None if error
        """
        try:
            # Calculate date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Find all relevant Parquet files
            parquet_files = []
            current_date = start_date
            while current_date <= end_date:
                filename = f"oi_{current_date.strftime('%Y%m%d')}.parquet"
                filepath = self.data_dir / filename
                if filepath.exists():
                    parquet_files.append(filepath)
                current_date += timedelta(days=1)
            
            if not parquet_files:
                warning(f"No OI history found for the last {days} days")
                return None
            
            # Load and combine all files
            dfs = []
            for filepath in parquet_files:
                try:
                    df = pd.read_parquet(filepath)
                    if not df.empty:
                        dfs.append(df)
                except Exception as e:
                    error(f"Failed to read file {filepath.name}: {str(e)}, skipping")
                    continue

            if not dfs:
                warning(f"No valid OI history found for the last {days} days")
                return None

            # Combine all DataFrames
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # Ensure timestamp is datetime
            combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'])
            
            # Sort by timestamp
            combined_df = combined_df.sort_values('timestamp')
            
            # Filter to exact date range
            combined_df = combined_df[
                (combined_df['timestamp'].dt.date >= start_date) &
                (combined_df['timestamp'].dt.date <= end_date)
            ]
            
            info(f"📊 Loaded {len(combined_df)} OI records from {len(parquet_files)} files")
            
            return combined_df
            
        except Exception as e:
            error(f"Failed to load OI history: {str(e)}")
            error(traceback.format_exc())
            return None
    
    def cleanup_old_data(self, retention_days: int = 30) -> int:
        """
        Remove Parquet files older than retention period
        
        Args:
            retention_days: Number of days to keep
            
        Returns:
            Number of files deleted
        """
        try:
            cutoff_date = datetime.now().date() - timedelta(days=retention_days)
            deleted_count = 0
            
            # Find and delete old files
            for filepath in self.data_dir.glob("oi_*.parquet"):
                try:
                    # Extract date from filename
                    filename = filepath.name
                    date_str = filename.replace("oi_", "").replace(".parquet", "")
                    file_date = datetime.strptime(date_str, "%Y%m%d").date()
                    
                    if file_date < cutoff_date:
                        filepath.unlink()
                        deleted_count += 1
                        debug(f"Deleted old file: {filename}", file_only=True)
                        
                except Exception as e:
                    warning(f"Could not process file {filepath.name}: {str(e)}")
            
            if deleted_count > 0:
                info(f"🧹 Cleaned up {deleted_count} old OI data files")
            else:
                debug("No old files to clean up", file_only=True)
            
            return deleted_count
            
        except Exception as e:
            error(f"Failed to cleanup old data: {str(e)}")
            error(traceback.format_exc())
            return 0
    
    def get_latest_snapshot(self) -> Optional[pd.DataFrame]:
        """
        Get the most recent OI snapshot
        
        Returns:
            DataFrame with latest OI data or None if no data
        """
        try:
            # Find the most recent file
            parquet_files = sorted(self.data_dir.glob("oi_*.parquet"), reverse=True)
            
            if not parquet_files:
                warning("No OI snapshots found")
                return None
            
            # Load the most recent file
            latest_file = parquet_files[0]
            df = pd.read_parquet(latest_file)
            
            # Ensure timestamp is datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Get only the most recent timestamp's data
            latest_timestamp = df['timestamp'].max()
            latest_df = df[df['timestamp'] == latest_timestamp]
            
            info(f"📊 Loaded latest snapshot with {len(latest_df)} records from {latest_file.name}")
            
            return latest_df
            
        except Exception as e:
            error(f"Failed to get latest snapshot: {str(e)}")
            error(traceback.format_exc())
            return None
    
    def get_storage_stats(self) -> Dict:
        """
        Get statistics about local storage
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            parquet_files = list(self.data_dir.glob("oi_*.parquet"))
            
            if not parquet_files:
                return {
                    'file_count': 0,
                    'total_size_mb': 0,
                    'oldest_date': None,
                    'newest_date': None
                }
            
            # Calculate total size
            total_size = sum(f.stat().st_size for f in parquet_files)
            total_size_mb = total_size / (1024 * 1024)
            
            # Extract dates from filenames
            dates = []
            for f in parquet_files:
                try:
                    date_str = f.name.replace("oi_", "").replace(".parquet", "")
                    date = datetime.strptime(date_str, "%Y%m%d").date()
                    dates.append(date)
                except:
                    pass
            
            return {
                'file_count': len(parquet_files),
                'total_size_mb': round(total_size_mb, 2),
                'oldest_date': min(dates) if dates else None,
                'newest_date': max(dates) if dates else None
            }
            
        except Exception as e:
            error(f"Failed to get storage stats: {str(e)}")
            return {
                'file_count': 0,
                'total_size_mb': 0,
                'oldest_date': None,
                'newest_date': None,
                'error': str(e)
            }


if __name__ == "__main__":
    # Test the storage class
    info("🧪 Testing OI Storage...")
    
    storage = OIStorage()
    
    # Test data
    test_data = [
        {
            'timestamp': datetime.now(),
            'symbol': 'BTC',
            'open_interest': 1500000000,
            'funding_rate': 0.0001,
            'mark_price': 45000.0,
            'volume_24h': 5000000000
        },
        {
            'timestamp': datetime.now(),
            'symbol': 'ETH',
            'open_interest': 800000000,
            'funding_rate': 0.00015,
            'mark_price': 2500.0,
            'volume_24h': 2000000000
        }
    ]
    
    # Test save
    if storage.save_oi_snapshot(test_data):
        info("✅ Save test passed")
    
    # Test load
    history = storage.load_history(days=7)
    if history is not None:
        info(f"✅ Load test passed - loaded {len(history)} records")
    
    # Test latest snapshot
    latest = storage.get_latest_snapshot()
    if latest is not None:
        info(f"✅ Latest snapshot test passed - {len(latest)} records")
    
    # Test stats
    stats = storage.get_storage_stats()
    info(f"✅ Storage stats: {stats}")
    
    info("🎉 OI Storage tests complete!")

