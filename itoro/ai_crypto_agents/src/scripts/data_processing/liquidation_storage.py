"""
Liquidation Agent Local Storage Manager
Handles efficient Parquet-based storage for liquidation event data with enhanced metrics
Built with love by Anarcho Capital 🚀
"""

import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import traceback
import numpy as np

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

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class LiquidationStorage:
    """Local Parquet-based storage for liquidation event data"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize liquidation storage manager"""
        if data_dir is None:
            self.data_dir = PROJECT_ROOT / "src" / "data" / "liquidations"
        else:
            self.data_dir = Path(data_dir)
        
        # Create directory if it doesn't exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        info(f"📂 Liquidation Storage initialized at: {self.data_dir}")
        
        # Event sequence counters per symbol
        self.event_counters = {}
        
    def save_liquidation_event(self, event: Dict) -> bool:
        """
        Save single liquidation event to Parquet file
        
        Args:
            event: Liquidation event record with enhanced metrics
        
        Returns:
            True if successful, False otherwise
        """
        return self.save_liquidation_batch([event])
    
    def save_liquidation_batch(self, events: List[Dict]) -> bool:
        """
        Save batch of liquidation events to Parquet file
        
        Args:
            events: List of liquidation event records with keys:
                - timestamp: datetime (system capture time)
                - event_time: datetime (exchange reported time)
                - exchange: str
                - symbol: str
                - side: str (long/short)
                - price: float
                - quantity: float
                - usd_value: float
                - order_type: str (optional)
                - time_in_force: str (optional)
                - average_price: float (optional)
                - mark_price: float (optional)
                - index_price: float (optional)
                - price_impact_bps: float (optional)
                - spread_bps: float (optional)
                - cumulative_1m_usd: float (optional)
                - cumulative_5m_usd: float (optional)
                - cumulative_15m_usd: float (optional)
                - event_velocity_1m: int (optional)
                - cascade_score: float (optional)
                - cluster_size: int (optional)
                - bid_depth_10bps: float (optional)
                - ask_depth_10bps: float (optional)
                - imbalance_ratio: float (optional)
                - volatility_1h: float (optional)
                - volatility_percentile: float (optional)
                - volume_1h: float (optional)
                - oi_change_1h_pct: float (optional)
                - concurrent_exchanges: int (optional)
                - cross_exchange_lag_ms: float (optional)
                - dominant_exchange: str (optional)
                - event_id: int (optional)
                - batch_id: str (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not events:
                warning("No liquidation events to save")
                return False
            
            # Convert to DataFrame
            df = pd.DataFrame(events)
            
            # Ensure timestamp is datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            else:
                df['timestamp'] = datetime.now()
            
            # Ensure event_time is datetime
            if 'event_time' in df.columns:
                df['event_time'] = pd.to_datetime(df['event_time'])
            else:
                df['event_time'] = df['timestamp']
            
            # Add event_id if not present
            if 'event_id' not in df.columns:
                df['event_id'] = range(len(df))
            
            # Get current date for filename
            current_date = datetime.now().strftime("%Y%m%d")
            filename = f"liquidation_{current_date}.parquet"
            filepath = self.data_dir / filename
            
            # Load existing data for the day if it exists
            if filepath.exists():
                try:
                    existing_df = pd.read_parquet(filepath)
                    # Append new data
                    df = pd.concat([existing_df, df], ignore_index=True)
                    # Remove duplicates based on event_time, exchange, and symbol
                    df = df.drop_duplicates(subset=['event_time', 'exchange', 'symbol', 'side', 'price'], keep='last')
                except Exception as e:
                    warning(f"Could not load existing file, creating new: {str(e)}")
            
            # Sort by event_time
            df = df.sort_values('event_time')
            
            # Save to Parquet with snappy compression
            df.to_parquet(filepath, index=False, compression='snappy')
            
            debug(f"Saved {len(events)} liquidation events to {filename}", file_only=True)
            return True
            
        except Exception as e:
            error(f"Failed to save liquidation events: {str(e)}")
            error(traceback.format_exc())
            return False
    
    def load_history(self, hours: int = 24) -> Optional[pd.DataFrame]:
        """
        Load liquidation history from Parquet files
        
        Args:
            hours: Number of hours of history to load
        
        Returns:
            DataFrame with liquidation history or None if no data
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=hours)
            
            # Find all parquet files in date range
            all_files = []
            current_date = start_date
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                filename = f"liquidation_{date_str}.parquet"
                filepath = self.data_dir / filename
                
                if filepath.exists():
                    all_files.append(filepath)
                
                current_date += timedelta(days=1)
            
            if not all_files:
                debug(f"No liquidation history found for last {hours} hours", file_only=True)
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
            
            # Filter by time range
            history['event_time'] = pd.to_datetime(history['event_time'])
            history = history[history['event_time'] >= start_date]
            
            # Sort by event_time
            history = history.sort_values('event_time')
            
            # Remove duplicates
            history = history.drop_duplicates(subset=['event_time', 'exchange', 'symbol', 'side', 'price'], keep='last')
            
            info(f"Loaded {len(history)} liquidation events from {len(all_files)} files ({hours} hours)")
            return history
            
        except Exception as e:
            error(f"Failed to load liquidation history: {str(e)}")
            error(traceback.format_exc())
            return None
    
    def get_aggregated_stats(self, window_minutes: int = 15, symbol: Optional[str] = None) -> Optional[Dict]:
        """
        Calculate aggregated statistics for a time window
        
        Args:
            window_minutes: Time window in minutes
            symbol: Optional symbol filter
        
        Returns:
            Dictionary with aggregated statistics or None
        """
        try:
            # Load recent history
            history = self.load_history(hours=int(window_minutes / 60) + 1)
            
            if history is None or history.empty:
                return None
            
            # Filter by symbol if specified
            if symbol:
                history = history[history['symbol'] == symbol]
            
            # Filter by time window
            cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
            history = history[history['event_time'] >= cutoff_time]
            
            if history.empty:
                return None
            
            # Calculate statistics
            stats = {
                'window_minutes': window_minutes,
                'symbol': symbol if symbol else 'ALL',
                'total_events': len(history),
                'total_usd_value': history['usd_value'].sum(),
                'long_events': len(history[history['side'] == 'long']),
                'short_events': len(history[history['side'] == 'short']),
                'long_usd_value': history[history['side'] == 'long']['usd_value'].sum(),
                'short_usd_value': history[history['side'] == 'short']['usd_value'].sum(),
                'exchanges_active': history['exchange'].nunique(),
                'exchanges': history['exchange'].unique().tolist(),
                'avg_price': history['price'].mean(),
                'avg_usd_value': history['usd_value'].mean(),
                'max_usd_value': history['usd_value'].max(),
                'timestamp': datetime.now()
            }
            
            # Add dominant side
            if stats['long_usd_value'] > stats['short_usd_value']:
                stats['dominant_side'] = 'long'
            else:
                stats['dominant_side'] = 'short'
            
            return stats
            
        except Exception as e:
            error(f"Failed to calculate aggregated stats: {str(e)}")
            error(traceback.format_exc())
            return None
    
    def get_cascade_events(self, threshold_usd: float = 1000000, window_seconds: int = 60) -> Optional[pd.DataFrame]:
        """
        Query liquidation cascade events (high volume in short time)
        
        Args:
            threshold_usd: Minimum USD value to consider a cascade
            window_seconds: Time window to check for cascades
        
        Returns:
            DataFrame with cascade events or None
        """
        try:
            # Load recent history
            history = self.load_history(hours=24)
            
            if history is None or history.empty:
                return None
            
            # Calculate rolling sum over time windows
            history = history.sort_values('event_time')
            history['rolling_sum'] = history.groupby('symbol')['usd_value'].rolling(
                window=f'{window_seconds}s', 
                on='event_time'
            ).sum().reset_index(level=0, drop=True)
            
            # Filter for cascade events
            cascades = history[history['rolling_sum'] >= threshold_usd]
            
            if cascades.empty:
                return None
            
            info(f"Found {len(cascades)} cascade events (>${threshold_usd:,.0f} in {window_seconds}s)")
            return cascades
            
        except Exception as e:
            error(f"Failed to get cascade events: {str(e)}")
            error(traceback.format_exc())
            return None
    
    def get_cross_exchange_stats(self, symbol: Optional[str] = None, hours: int = 1) -> Optional[Dict]:
        """
        Analyze cross-exchange correlation and timing
        
        Args:
            symbol: Optional symbol filter
            hours: Hours of history to analyze
        
        Returns:
            Dictionary with cross-exchange statistics or None
        """
        try:
            # Load recent history
            history = self.load_history(hours=hours)
            
            if history is None or history.empty:
                return None
            
            # Filter by symbol if specified
            if symbol:
                history = history[history['symbol'] == symbol]
            
            if history.empty:
                return None
            
            # Calculate per-exchange statistics
            exchange_stats = {}
            for exchange in history['exchange'].unique():
                exchange_data = history[history['exchange'] == exchange]
                exchange_stats[exchange] = {
                    'total_events': len(exchange_data),
                    'total_usd_value': exchange_data['usd_value'].sum(),
                    'avg_usd_value': exchange_data['usd_value'].mean(),
                    'long_pct': (len(exchange_data[exchange_data['side'] == 'long']) / len(exchange_data)) * 100
                }
            
            # Calculate correlation metrics
            stats = {
                'symbol': symbol if symbol else 'ALL',
                'hours': hours,
                'exchanges_active': len(exchange_stats),
                'exchange_stats': exchange_stats,
                'total_events': len(history),
                'total_usd_value': history['usd_value'].sum(),
                'timestamp': datetime.now()
            }
            
            # Find dominant exchange
            if exchange_stats:
                dominant_exchange = max(exchange_stats.items(), key=lambda x: x[1]['total_usd_value'])
                stats['dominant_exchange'] = dominant_exchange[0]
                stats['dominant_exchange_pct'] = (dominant_exchange[1]['total_usd_value'] / stats['total_usd_value']) * 100
            
            return stats
            
        except Exception as e:
            error(f"Failed to get cross-exchange stats: {str(e)}")
            error(traceback.format_exc())
            return None
    
    def export_for_sale(self, start_date: datetime, end_date: datetime, format: str = 'parquet') -> Optional[Path]:
        """
        Export liquidation data for data product sales
        
        Args:
            start_date: Start date for export
            end_date: End date for export
            format: Export format ('parquet', 'csv', 'json')
        
        Returns:
            Path to exported file or None
        """
        try:
            # Load data for date range
            hours = int((end_date - start_date).total_seconds() / 3600) + 24
            history = self.load_history(hours=hours)
            
            if history is None or history.empty:
                warning("No data to export")
                return None
            
            # Filter by date range
            history = history[
                (history['event_time'] >= start_date) & 
                (history['event_time'] <= end_date)
            ]
            
            if history.empty:
                warning("No data in specified date range")
                return None
            
            # Create export filename
            export_dir = self.data_dir / "exports"
            export_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"liquidation_export_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{timestamp}"
            
            # Export in requested format
            if format == 'parquet':
                filepath = export_dir / f"{filename}.parquet"
                history.to_parquet(filepath, index=False, compression='snappy')
            elif format == 'csv':
                filepath = export_dir / f"{filename}.csv"
                history.to_csv(filepath, index=False)
            elif format == 'json':
                filepath = export_dir / f"{filename}.json"
                history.to_json(filepath, orient='records', date_format='iso')
            else:
                error(f"Unsupported export format: {format}")
                return None
            
            info(f"Exported {len(history)} events to {filepath}")
            return filepath
            
        except Exception as e:
            error(f"Failed to export data: {str(e)}")
            error(traceback.format_exc())
            return None
    
    def cleanup_old_files(self, retention_hours: int = 24) -> int:
        """
        Remove liquidation files older than retention period
        
        Args:
            retention_hours: Number of hours to keep
        
        Returns:
            Number of files deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(hours=retention_hours)
            deleted_count = 0
            
            # Scan all parquet files
            for filepath in self.data_dir.glob("liquidation_*.parquet"):
                try:
                    # Extract date from filename
                    date_str = filepath.stem.split('_')[1]
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    
                    # Delete if older than retention period
                    if file_date < cutoff_date:
                        filepath.unlink()
                        deleted_count += 1
                        debug(f"Deleted old liquidation file: {filepath.name}", file_only=True)
                        
                except Exception as e:
                    warning(f"Error processing {filepath.name}: {str(e)}")
                    continue
            
            if deleted_count > 0:
                info(f"Cleaned up {deleted_count} old liquidation files (>{retention_hours} hours)")
            
            return deleted_count
            
        except Exception as e:
            error(f"Failed to cleanup old files: {str(e)}")
            return 0
    
    def get_file_count(self) -> int:
        """Get count of liquidation data files"""
        try:
            return len(list(self.data_dir.glob("liquidation_*.parquet")))
        except:
            return 0
    
    def get_total_records(self) -> int:
        """Get total number of liquidation records stored"""
        try:
            total = 0
            for filepath in self.data_dir.glob("liquidation_*.parquet"):
                try:
                    df = pd.read_parquet(filepath)
                    total += len(df)
                except:
                    continue
            return total
        except:
            return 0
    
    def get_date_range(self) -> tuple:
        """Get the date range of stored liquidation data"""
        try:
            files = sorted(self.data_dir.glob("liquidation_*.parquet"))
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
    print("Testing Liquidation Storage Manager...")
    
    storage = LiquidationStorage()
    
    # Test data
    test_events = [
        {
            'timestamp': datetime.now(),
            'event_time': datetime.now(),
            'exchange': 'binance',
            'symbol': 'BTC',
            'side': 'long',
            'price': 50000.0,
            'quantity': 2.5,
            'usd_value': 125000.0,
            'order_type': 'MARKET',
            'mark_price': 50010.0,
            'cumulative_1m_usd': 250000.0,
            'cascade_score': 0.75
        },
        {
            'timestamp': datetime.now(),
            'event_time': datetime.now(),
            'exchange': 'bybit',
            'symbol': 'ETH',
            'side': 'short',
            'price': 3000.0,
            'quantity': 10.0,
            'usd_value': 30000.0,
            'order_type': 'LIMIT',
            'mark_price': 2995.0,
            'cumulative_1m_usd': 50000.0,
            'cascade_score': 0.45
        }
    ]
    
    # Test save
    print("\n1. Testing save_liquidation_batch...")
    success = storage.save_liquidation_batch(test_events)
    print(f"   Result: {'✓ Success' if success else '✗ Failed'}")
    
    # Test load
    print("\n2. Testing load_history...")
    history = storage.load_history(hours=24)
    if history is not None:
        print(f"   Result: ✓ Loaded {len(history)} records")
        print(f"   Symbols: {history['symbol'].unique().tolist()}")
        print(f"   Exchanges: {history['exchange'].unique().tolist()}")
    else:
        print("   Result: ✗ No history found")
    
    # Test aggregated stats
    print("\n3. Testing get_aggregated_stats...")
    stats = storage.get_aggregated_stats(window_minutes=15, symbol='BTC')
    if stats:
        print(f"   Result: ✓ Calculated stats")
        print(f"   Total events: {stats['total_events']}")
        print(f"   Total USD: ${stats['total_usd_value']:,.2f}")
        print(f"   Dominant side: {stats['dominant_side']}")
    else:
        print("   Result: ✗ No stats available")
    
    # Test file stats
    print("\n4. Testing storage stats...")
    file_count = storage.get_file_count()
    total_records = storage.get_total_records()
    date_range = storage.get_date_range()
    print(f"   Files: {file_count}")
    print(f"   Total records: {total_records}")
    if date_range[0] and date_range[1]:
        print(f"   Date range: {date_range[0].strftime('%Y-%m-%d')} to {date_range[1].strftime('%Y-%m-%d')}")
    
    print("\n✓ Liquidation Storage Manager test complete!")

