"""
OI Analytics Engine
Calculates comprehensive analytics from Open Interest data
Built with love by Anarcho Capital 🚀
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
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


class OIAnalytics:
    """Analytics calculator for Open Interest data"""
    
    def __init__(self):
        """Initialize OI analytics engine"""
        info("📊 OI Analytics Engine initialized")
        
    def calculate_all_metrics(self, history_df: pd.DataFrame) -> List[Dict]:
        """
        Calculate all analytics metrics from historical data
        
        Args:
            history_df: DataFrame with columns [timestamp, symbol, open_interest, funding_rate, mark_price, volume_24h]
            
        Returns:
            List of analytics records ready for database storage
        """
        try:
            if history_df is None or history_df.empty:
                warning("No historical data available for analytics")
                return []
            
            analytics_records = []
            
            # Get unique symbols
            symbols = history_df['symbol'].unique()
            
            for symbol in symbols:
                symbol_data = history_df[history_df['symbol'] == symbol].sort_values('timestamp')

                debug(f"Processing {symbol}: {len(symbol_data)} records, timestamps: {symbol_data['timestamp'].tolist()}", file_only=True)

                if len(symbol_data) < 2:
                    debug(f"Not enough data for {symbol} analytics", file_only=True)
                    continue
                
                # Calculate analytics for different timeframes
                timeframes = [
                    ('4h', 4),
                    ('24h', 24),
                    ('7d', 168)
                ]
                
                for timeframe_name, hours in timeframes:
                    debug(f"Calculating {timeframe_name} analytics for {symbol} (needs data from {hours}h ago)", file_only=True)
                    analytics = self._calculate_timeframe_analytics(
                        symbol_data,
                        symbol,
                        timeframe_name,
                        hours
                    )

                    if analytics:
                        analytics_records.append(analytics)
                        debug(f"Generated {timeframe_name} analytics for {symbol}", file_only=True)
                    else:
                        debug(f"Failed to generate {timeframe_name} analytics for {symbol}", file_only=True)
            
            info(f"✅ Calculated {len(analytics_records)} analytics records")
            return analytics_records
            
        except Exception as e:
            error(f"Failed to calculate analytics: {str(e)}")
            error(traceback.format_exc())
            return []
    
    def _calculate_timeframe_analytics(
        self, 
        symbol_data: pd.DataFrame, 
        symbol: str, 
        timeframe: str, 
        hours: int
    ) -> Optional[Dict]:
        """Calculate analytics for a specific timeframe"""
        try:
            # Get current and historical data points
            current_time = symbol_data['timestamp'].max()
            target_time = current_time - timedelta(hours=hours)

            debug(f"  {timeframe}: current_time={current_time}, target_time={target_time}", file_only=True)

            current_data = symbol_data[symbol_data['timestamp'] == current_time].iloc[0]
            historical_data = symbol_data[symbol_data['timestamp'] <= target_time]

            debug(f"  {timeframe}: found {len(historical_data)} historical records", file_only=True)

            if historical_data.empty:
                debug(f"  {timeframe}: No historical data available", file_only=True)
                return None
            
            past_data = historical_data.iloc[-1]
            
            # Calculate OI changes
            oi_change_pct = self._calculate_percentage_change(
                past_data['open_interest'],
                current_data['open_interest']
            )
            oi_change_abs = current_data['open_interest'] - past_data['open_interest']
            
            # Calculate funding rate changes
            funding_rate_change_pct = self._calculate_percentage_change(
                past_data['funding_rate'],
                current_data['funding_rate']
            ) if pd.notna(past_data['funding_rate']) and pd.notna(current_data['funding_rate']) else None
            
            # Get volume if available
            volume_24h = current_data.get('volume_24h')
            
            # Calculate liquidity depth (estimate based on OI and volume)
            liquidity_depth = self._estimate_liquidity_depth(
                current_data['open_interest'],
                volume_24h
            )
            
            # Calculate OI to volume ratio
            oi_volume_ratio = self.calculate_oi_volume_ratio(
                current_data['open_interest'],
                volume_24h
            )
            
            # Long/short ratio would come from liquidation data (set to None for now)
            long_short_ratio = None
            
            return {
                'timestamp': current_time,
                'timeframe': timeframe,
                'symbol': symbol,
                'oi_change_pct': oi_change_pct,
                'oi_change_abs': oi_change_abs,
                'funding_rate_change_pct': funding_rate_change_pct,
                'volume_24h': volume_24h,
                'liquidity_depth': liquidity_depth,
                'long_short_ratio': long_short_ratio,
                'oi_volume_ratio': oi_volume_ratio,
                'metadata': {
                    'current_oi': float(current_data['open_interest']),
                    'past_oi': float(past_data['open_interest']),
                    'current_funding_rate': float(current_data['funding_rate']) if pd.notna(current_data['funding_rate']) else None,
                    'past_funding_rate': float(past_data['funding_rate']) if pd.notna(past_data['funding_rate']) else None
                }
            }
            
        except Exception as e:
            error(f"Failed to calculate {timeframe} analytics for {symbol}: {str(e)}")
            return None
    
    def calculate_oi_changes(self, history_df: pd.DataFrame, timeframe_hours: int = 24) -> Dict[str, float]:
        """
        Calculate OI percentage changes for each symbol
        
        Args:
            history_df: Historical OI data
            timeframe_hours: Timeframe to calculate changes over
            
        Returns:
            Dictionary mapping symbol to percentage change
        """
        try:
            changes = {}
            symbols = history_df['symbol'].unique()
            
            for symbol in symbols:
                symbol_data = history_df[history_df['symbol'] == symbol].sort_values('timestamp')
                
                if len(symbol_data) < 2:
                    continue
                
                current = symbol_data.iloc[-1]
                target_time = current['timestamp'] - timedelta(hours=timeframe_hours)
                historical = symbol_data[symbol_data['timestamp'] <= target_time]
                
                if not historical.empty:
                    past = historical.iloc[-1]
                    pct_change = self._calculate_percentage_change(
                        past['open_interest'],
                        current['open_interest']
                    )
                    changes[symbol] = pct_change
            
            return changes
            
        except Exception as e:
            error(f"Failed to calculate OI changes: {str(e)}")
            return {}
    
    def calculate_funding_rate_changes(self, history_df: pd.DataFrame, timeframe_hours: int = 24) -> Dict[str, float]:
        """
        Calculate funding rate percentage changes for each symbol
        
        Args:
            history_df: Historical OI data with funding rates
            timeframe_hours: Timeframe to calculate changes over
            
        Returns:
            Dictionary mapping symbol to funding rate percentage change
        """
        try:
            changes = {}
            symbols = history_df['symbol'].unique()
            
            for symbol in symbols:
                symbol_data = history_df[history_df['symbol'] == symbol].sort_values('timestamp')
                
                if len(symbol_data) < 2:
                    continue
                
                current = symbol_data.iloc[-1]
                target_time = current['timestamp'] - timedelta(hours=timeframe_hours)
                historical = symbol_data[symbol_data['timestamp'] <= target_time]
                
                if not historical.empty:
                    past = historical.iloc[-1]
                    
                    if pd.notna(past['funding_rate']) and pd.notna(current['funding_rate']):
                        pct_change = self._calculate_percentage_change(
                            past['funding_rate'],
                            current['funding_rate']
                        )
                        changes[symbol] = pct_change
            
            return changes
            
        except Exception as e:
            error(f"Failed to calculate funding rate changes: {str(e)}")
            return {}
    
    def calculate_volume_metrics(self, history_df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Calculate volume-related metrics for each symbol
        
        Args:
            history_df: Historical OI data with volume
            
        Returns:
            Dictionary with volume metrics per symbol
        """
        try:
            metrics = {}
            symbols = history_df['symbol'].unique()
            
            for symbol in symbols:
                symbol_data = history_df[history_df['symbol'] == symbol].sort_values('timestamp')
                
                if 'volume_24h' not in symbol_data.columns:
                    continue
                
                # Remove NaN values
                volume_data = symbol_data['volume_24h'].dropna()
                
                if len(volume_data) == 0:
                    continue
                
                metrics[symbol] = {
                    'current_volume': float(volume_data.iloc[-1]) if len(volume_data) > 0 else None,
                    'avg_volume': float(volume_data.mean()),
                    'volume_change_pct': self._calculate_percentage_change(
                        volume_data.iloc[0], 
                        volume_data.iloc[-1]
                    ) if len(volume_data) > 1 else None,
                    'volume_volatility': float(volume_data.std()) if len(volume_data) > 1 else None
                }
            
            return metrics
            
        except Exception as e:
            error(f"Failed to calculate volume metrics: {str(e)}")
            return {}
    
    def estimate_liquidity_shifts(self, history_df: pd.DataFrame, window_hours: int = 24) -> Dict[str, str]:
        """
        Estimate liquidity shifts based on OI and volume patterns
        
        Args:
            history_df: Historical OI data
            window_hours: Time window for analysis
            
        Returns:
            Dictionary mapping symbol to liquidity shift status (increasing/decreasing/stable)
        """
        try:
            shifts = {}
            symbols = history_df['symbol'].unique()
            
            for symbol in symbols:
                symbol_data = history_df[history_df['symbol'] == symbol].sort_values('timestamp')
                
                # Get data within window
                cutoff_time = symbol_data['timestamp'].max() - timedelta(hours=window_hours)
                window_data = symbol_data[symbol_data['timestamp'] >= cutoff_time]
                
                if len(window_data) < 2:
                    continue
                
                # Calculate OI trend
                oi_values = window_data['open_interest'].values
                oi_trend = np.polyfit(range(len(oi_values)), oi_values, 1)[0]
                
                # Determine shift
                if oi_trend > 0.01:  # Threshold for significant increase
                    shifts[symbol] = 'increasing'
                elif oi_trend < -0.01:  # Threshold for significant decrease
                    shifts[symbol] = 'decreasing'
                else:
                    shifts[symbol] = 'stable'
            
            return shifts
            
        except Exception as e:
            error(f"Failed to estimate liquidity shifts: {str(e)}")
            return {}
    
    def calculate_long_short_ratio(self, liquidation_data: Optional[pd.DataFrame] = None) -> Dict[str, float]:
        """
        Calculate long/short ratio from liquidation data
        
        Args:
            liquidation_data: DataFrame with liquidation events
            
        Returns:
            Dictionary mapping symbol to long/short ratio
        """
        try:
            if liquidation_data is None or liquidation_data.empty:
                debug("No liquidation data available for long/short ratio", file_only=True)
                return {}
            
            ratios = {}
            symbols = liquidation_data['symbol'].unique() if 'symbol' in liquidation_data.columns else []
            
            for symbol in symbols:
                symbol_liq = liquidation_data[liquidation_data['symbol'] == symbol]
                
                # Separate longs and shorts
                longs = symbol_liq[symbol_liq['side'] == 'SELL']['usd_value'].sum()  # SELL = long liquidation
                shorts = symbol_liq[symbol_liq['side'] == 'BUY']['usd_value'].sum()  # BUY = short liquidation
                
                if shorts > 0:
                    ratios[symbol] = longs / shorts
                elif longs > 0:
                    ratios[symbol] = float('inf')  # All longs
                else:
                    ratios[symbol] = 1.0  # No liquidations
            
            return ratios
            
        except Exception as e:
            error(f"Failed to calculate long/short ratio: {str(e)}")
            return {}
    
    def calculate_oi_volume_ratio(self, oi_data: float, volume_data: float) -> Optional[float]:
        """
        Calculate OI to volume ratio for a single datapoint
        
        Args:
            oi_data: Open interest value
            volume_data: 24h volume
            
        Returns:
            OI/Volume ratio or None
        """
        try:
            if pd.isna(oi_data) or pd.isna(volume_data) or volume_data == 0:
                return None
            
            return float(oi_data / volume_data)
            
        except Exception as e:
            error(f"Failed to calculate OI/volume ratio: {str(e)}")
            return None
    
    def _calculate_percentage_change(self, old_value: float, new_value: float) -> Optional[float]:
        """Calculate percentage change between two values"""
        try:
            if pd.isna(old_value) or pd.isna(new_value) or old_value == 0:
                return None
            
            return float(((new_value - old_value) / abs(old_value)) * 100)
            
        except Exception as e:
            return None
    
    def _estimate_liquidity_depth(self, oi: float, volume: Optional[float]) -> Optional[float]:
        """
        Estimate liquidity depth based on OI and volume
        This is a simplified metric - higher is better
        """
        try:
            if pd.isna(oi):
                return None
            
            if pd.isna(volume) or volume == 0:
                # If no volume data, return OI as proxy
                return float(oi)
            
            # Weighted average of OI and volume
            # Higher OI and volume = better liquidity
            return float((oi * 0.6 + volume * 0.4) / 2)
            
        except Exception as e:
            return None


if __name__ == "__main__":
    # Test the analytics engine
    info("🧪 Testing OI Analytics Engine...")
    
    analytics = OIAnalytics()
    
    # Create test data
    test_data = []
    base_time = datetime.now() - timedelta(days=7)
    
    for i in range(50):  # 50 data points over 7 days
        timestamp = base_time + timedelta(hours=i * 3.36)  # ~3.36 hours apart
        
        test_data.append({
            'timestamp': timestamp,
            'symbol': 'BTC',
            'open_interest': 1500000000 + (i * 10000000),  # Increasing OI
            'funding_rate': 0.0001 + (i * 0.000001),
            'mark_price': 45000 + (i * 100),
            'volume_24h': 5000000000 + (i * 50000000)
        })
        
        test_data.append({
            'timestamp': timestamp,
            'symbol': 'ETH',
            'open_interest': 800000000 + (i * 5000000),
            'funding_rate': 0.00015 - (i * 0.000001),  # Decreasing funding rate
            'mark_price': 2500 + (i * 50),
            'volume_24h': 2000000000 + (i * 20000000)
        })
    
    test_df = pd.DataFrame(test_data)
    
    # Test calculate all metrics
    analytics_records = analytics.calculate_all_metrics(test_df)
    if analytics_records:
        info(f"✅ Analytics test passed - generated {len(analytics_records)} records")
        info(f"Sample record: {analytics_records[0]}")
    else:
        error("❌ Analytics test failed")
    
    # Test OI changes
    oi_changes = analytics.calculate_oi_changes(test_df, timeframe_hours=24)
    info(f"✅ OI Changes: {oi_changes}")
    
    # Test volume metrics
    volume_metrics = analytics.calculate_volume_metrics(test_df)
    info(f"✅ Volume Metrics: {volume_metrics}")
    
    # Test liquidity shifts
    liquidity_shifts = analytics.estimate_liquidity_shifts(test_df, window_hours=48)
    info(f"✅ Liquidity Shifts: {liquidity_shifts}")
    
    info("🎉 OI Analytics tests complete!")

