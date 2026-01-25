"""
Funding Agent Local Storage Manager
Handles efficient Parquet-based storage for funding rate data
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

# Get project root (go up to itoro directory)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class FundingStorage:
    """Local Parquet-based storage for funding rate data"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize funding storage manager"""
        if data_dir is None:
            self.data_dir = PROJECT_ROOT / "src" / "data" / "funding"
        else:
            self.data_dir = Path(data_dir)
        
        # Create directory if it doesn't exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        info(f"📂 Funding Storage initialized at: {self.data_dir}")
        
    def save_funding_snapshot(self, funding_data: List[Dict]) -> bool:
        """
        Save funding snapshot to Parquet file
        
        Args:
            funding_data: List of funding rate records with keys:
                - symbol: str
                - funding_rate: float
                - annual_rate: float
                - mark_price: float
                - open_interest: float
                - event_time: datetime
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not funding_data:
                warning("No funding data to save")
                return False
            
            # Convert to DataFrame
            df = pd.DataFrame(funding_data)
            
            # Ensure event_time is datetime
            if 'event_time' in df.columns:
                df['event_time'] = pd.to_datetime(df['event_time'])
            else:
                df['event_time'] = datetime.now()
            
            # Get current date for filename
            current_date = datetime.now().strftime("%Y%m%d")
            filename = f"funding_{current_date}.parquet"
            filepath = self.data_dir / filename
            
            # IMPORTANT: Do NOT try to read/append the existing file to avoid schema issues.
            # Just overwrite today's file with the latest snapshot.
            # Sort by event_time
            df = df.sort_values('event_time')
            
            # Save to Parquet (overwrite daily file)
            df.to_parquet(filepath, index=False, compression='snappy')
            
            debug(f"Saved {len(funding_data)} funding records to {filename}", file_only=True)
            return True
            
        except Exception as e:
            error(f"Failed to save funding snapshot: {str(e)}")
            error(traceback.format_exc())
            return False
    
    def load_history(self, days: int = 90) -> Optional[pd.DataFrame]:
        """
        Load funding history from Parquet files
        
        Args:
            days: Number of days of history to load
        
        Returns:
            DataFrame with funding history or None if no data
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Find all parquet files in date range
            all_files = []
            current_date = start_date
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                filename = f"funding_{date_str}.parquet"
                filepath = self.data_dir / filename
                
                if filepath.exists():
                    all_files.append(filepath)
                
                current_date += timedelta(days=1)
            
            if not all_files:
                info(f"No funding history found for last {days} days")
                return None
            
            # Load and concatenate all files
            dfs = []
            for filepath in all_files:
                try:
                    df = pd.read_parquet(filepath)
                    dfs.append(df)
                except Exception as e:
                    warning(f"Failed to load {filepath.name}: {str(e)}")
                    continue
            
            if not dfs:
                return None
            
            # Concatenate all DataFrames
            history = pd.concat(dfs, ignore_index=True)
            
            # Filter by date range
            history['event_time'] = pd.to_datetime(history['event_time'])
            history = history[history['event_time'] >= start_date]
            
            # Sort by event_time
            history = history.sort_values('event_time')
            
            # Remove duplicates
            history = history.drop_duplicates(subset=['event_time', 'symbol'], keep='last')
            
            info(f"Loaded {len(history)} funding records from {len(all_files)} files ({days} days)")
            return history
            
        except Exception as e:
            error(f"Failed to load funding history: {str(e)}")
            error(traceback.format_exc())
            return None
    
    def cleanup_old_files(self, retention_days: int = 90) -> int:
        """
        Remove funding files older than retention period
        
        Args:
            retention_days: Number of days to keep
        
        Returns:
            Number of files deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            deleted_count = 0
            
            # Scan all parquet files
            for filepath in self.data_dir.glob("funding_*.parquet"):
                try:
                    # Extract date from filename
                    date_str = filepath.stem.split('_')[1]
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    
                    # Delete if older than retention period
                    if file_date < cutoff_date:
                        filepath.unlink()
                        deleted_count += 1
                        debug(f"Deleted old funding file: {filepath.name}", file_only=True)
                        
                except Exception as e:
                    warning(f"Error processing {filepath.name}: {str(e)}")
                    continue
            
            if deleted_count > 0:
                info(f"Cleaned up {deleted_count} old funding files (>{retention_days} days)")
            
            return deleted_count
            
        except Exception as e:
            error(f"Failed to cleanup old files: {str(e)}")
            return 0
    
    def get_file_count(self) -> int:
        """Get count of funding data files"""
        try:
            return len(list(self.data_dir.glob("funding_*.parquet")))
        except:
            return 0
    
    def get_total_records(self) -> int:
        """Get total number of funding records stored"""
        try:
            total = 0
            for filepath in self.data_dir.glob("funding_*.parquet"):
                try:
                    df = pd.read_parquet(filepath)
                    total += len(df)
                except:
                    continue
            return total
        except:
            return 0
    
    def get_date_range(self) -> tuple:
        """Get the date range of stored funding data"""
        try:
            files = sorted(self.data_dir.glob("funding_*.parquet"))
            if not files:
                return None, None
            
            # Get oldest and newest dates from filenames
            oldest_date_str = files[0].stem.split('_')[1]
            newest_date_str = files[-1].stem.split('_')[1]
            
            oldest_date = datetime.strptime(oldest_date_str, "%Y%m%d")
            newest_date = datetime.strptime(newest_date_str, "%Y%m%d")
            
            return oldest_date, newest_date
        except:
            return None, None


if __name__ == "__main__":
    # Test the storage manager
    print("Testing Funding Storage Manager...")
    
    storage = FundingStorage()
    
    # Test data
    test_data = [
        {
            'symbol': 'BTC',
            'funding_rate': 0.0001,
            'annual_rate': 10.95,
            'mark_price': 50000.0,
            'open_interest': 1000000.0,
            'event_time': datetime.now()
        },
        {
            'symbol': 'ETH',
            'funding_rate': -0.00005,
            'annual_rate': -5.475,
            'mark_price': 3000.0,
            'open_interest': 500000.0,
            'event_time': datetime.now()
        }
    ]
    
    # Test save
    print("\n1. Testing save_funding_snapshot...")
    success = storage.save_funding_snapshot(test_data)
    print(f"   Result: {'✓ Success' if success else '✗ Failed'}")
    
    # Test load
    print("\n2. Testing load_history...")
    history = storage.load_history(days=7)
    if history is not None:
        print(f"   Result: ✓ Loaded {len(history)} records")
        print(f"   Symbols: {history['symbol'].unique().tolist()}")
    else:
        print("   Result: ✗ No history found")
    
    # Test stats
    print("\n3. Testing stats...")
    file_count = storage.get_file_count()
    total_records = storage.get_total_records()
    date_range = storage.get_date_range()
    print(f"   Files: {file_count}")
    print(f"   Total records: {total_records}")
    if date_range[0] and date_range[1]:
        print(f"   Date range: {date_range[0].strftime('%Y-%m-%d')} to {date_range[1].strftime('%Y-%m-%d')}")
    
    print("\n✓ Funding Storage Manager test complete!")

