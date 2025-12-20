"""
MACD Parameter Scanner
Tests different MACD parameter combinations to find optimal settings for 5-minute BTC data.
"""

import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib
from pathlib import Path
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

class ParameterizedMACDStrategy(Strategy):
    """MACD Strategy with configurable parameters"""
    
    def init(self, fast_period=12, slow_period=26, entry_min_mult=-1.5, entry_max_mult=-0.5, 
             exit_min=-0.02323, exit_max=-0.00707, stop_loss_pct=0.318, min_holding=5):
        # Store parameters
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.entry_min_mult = entry_min_mult
        self.entry_max_mult = entry_max_mult
        self.exit_min = exit_min
        self.exit_max = exit_max
        self.stop_loss_pct = stop_loss_pct
        self.min_holding = min_holding
        
        # Initialize trade counter
        self.trade_count = 0
        
        # Calculate EMAs
        self.ema_fast = self.I(talib.EMA, self.data.Close, timeperiod=fast_period)
        self.ema_slow = self.I(talib.EMA, self.data.Close, timeperiod=slow_period)
        
        # Calculate Universal MACD: (EMA_fast/EMA_slow) - 1
        self.universal_macd = (self.ema_fast / self.ema_slow) - 1
        
        # Track entry price and entry bar
        self.entry_price = None
        self.entry_bar = None
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # Calculate adaptive entry range using rolling window
        if current_bar >= 20:
            # Get last 20 values of universal_macd
            macd_values = self.universal_macd[-21:-1]  # Last 20 values
            mean_val = np.mean(macd_values)
            std_val = np.std(macd_values)
            
            range_min = mean_val + self.entry_min_mult * std_val
            range_max = mean_val + self.entry_max_mult * std_val
            
            current_macd = self.universal_macd[-1]
            
            # ENTRY LOGIC
            if not self.position and current_bar >= 20:
                if range_min <= current_macd <= range_max:
                    # Fixed position sizing: 1.5% target, 0.5-3% range
                    entry_price = self.data.Close[-1]
                    target_position_pct = 0.015  # 1.5% of equity
                    position_size_fraction = min(target_position_pct, 0.03)  # Cap at 3%
                    position_size_fraction = max(position_size_fraction, 0.005)  # Minimum 0.5%
                    
                    # Convert to units for self.buy()
                    position_value = self.equity * position_size_fraction
                    position_size = position_value / entry_price
                    
                    # Validate position size
                    if (0.005 <= position_size_fraction <= 0.03) and position_size > 0:
                        self.trade_count += 1
                        self.buy(size=position_size)
                        self.entry_price = entry_price
                        self.entry_bar = current_bar
            
            # EXIT LOGIC (if in position)
            if self.position:
                candles_held = current_bar - self.entry_bar
                current_price = self.data.Close[-1]
                
                # 1. Stop Loss check
                stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
                if current_price <= stop_loss_price:
                    self.position.close()
                    self.entry_price = None
                    self.entry_bar = None
                    return
                
                # 2. ROI Targets (progressive scaling)
                roi_target = 0.0
                if candles_held == 0:
                    roi_target = 0.213  # 21.3%
                elif candles_held <= 27:
                    roi_target = 0.213 - (0.213 - 0.099) * (candles_held / 27)
                elif candles_held <= 60:
                    roi_target = 0.099 - (0.099 - 0.03) * ((candles_held - 27) / (60 - 27))
                elif candles_held <= 164:
                    roi_target = 0.03 - 0.03 * ((candles_held - 60) / (164 - 60))
                
                take_profit_price = self.entry_price * (1 + roi_target)
                
                if current_price >= take_profit_price and roi_target > 0:
                    self.position.close()
                    self.entry_price = None
                    self.entry_bar = None
                    return
                
                # 3. MACD Exit (only after minimum holding period)
                if candles_held >= self.min_holding:
                    current_macd = self.universal_macd[-1]
                    if self.exit_min <= current_macd <= self.exit_max:
                        self.position.close()
                        self.entry_price = None
                        self.entry_bar = None
                        return


def load_data(data_file_path):
    """Load and prepare OHLCV data"""
    price_data = pd.read_csv(data_file_path)
    
    # Clean column names
    price_data.columns = price_data.columns.str.strip().str.lower()
    
    # Drop any unnamed columns
    price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])
    
    # Ensure proper column mapping
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    for col in required_columns:
        if col not in price_data.columns:
            for actual_col in price_data.columns:
                if col in actual_col.lower():
                    price_data = price_data.rename(columns={actual_col: col})
                    break
    
    # Set datetime index
    if 'timestamp' in price_data.columns:
        price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
        price_data = price_data.set_index('timestamp')
    elif 'date' in price_data.columns:
        price_data['date'] = pd.to_datetime(price_data['date'])
        price_data = price_data.set_index('date')
    
    # Ensure proper column capitalization for backtesting.py
    price_data = price_data.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })
    
    return price_data


def scan_macd_parameters(data_file_path, output_file=None):
    """
    Scan MACD parameter combinations and return results DataFrame
    
    Parameters:
    - data_file_path: Path to CSV data file
    - output_file: Optional path to save results CSV
    """
    print(f"[SCAN] Loading data from: {data_file_path}")
    price_data = load_data(data_file_path)
    print(f"[SCAN] Data loaded: {len(price_data)} rows")
    print(f"[SCAN] Date range: {price_data.index[0]} to {price_data.index[-1]}")
    
    # Parameter combinations to test
    macd_periods = [
        (8, 21, 5),    # Shorter for intraday
        (12, 26, 9),   # Traditional
        (5, 13, 5),    # Very short
        (15, 30, 10),  # Longer for 5m
    ]
    
    entry_ranges = [
        (-2.5, -0.8),   # Much wider
        (-2.0, -1.0),   # Wider
        (-1.5, -0.5),   # Current
        (-1.0, -0.2),   # Narrower
    ]
    
    exit_ranges = [
        (-0.03, -0.01),     # Wider
        (-0.025, -0.005),   # Current
        (-0.02, -0.008),    # Narrower
    ]
    
    results = []
    total_combinations = len(macd_periods) * len(entry_ranges) * len(exit_ranges)
    current = 0
    
    print(f"[SCAN] Testing {total_combinations} parameter combinations...")
    
    for fast, slow, signal in macd_periods:
        for entry_min_mult, entry_max_mult in entry_ranges:
            for exit_min, exit_max in exit_ranges:
                current += 1
                print(f"[SCAN] [{current}/{total_combinations}] Testing: fast={fast}, slow={slow}, entry=({entry_min_mult:.1f}, {entry_max_mult:.1f}), exit=({exit_min:.4f}, {exit_max:.4f})")
                
                try:
                    # Create strategy with parameters
                    strategy_class = type('MACDStrategy', (ParameterizedMACDStrategy,), {})
                    
                    # Run backtest
                    bt = Backtest(
                        price_data,
                        strategy_class,
                        cash=1000000,
                        commission=0.002,
                        exclusive_orders=True
                    )
                    
                    stats = bt.run(
                        fast_period=fast,
                        slow_period=slow,
                        entry_min_mult=entry_min_mult,
                        entry_max_mult=entry_max_mult,
                        exit_min=exit_min,
                        exit_max=exit_max
                    )
                    
                    # Extract key metrics
                    result = {
                        'fast_period': fast,
                        'slow_period': slow,
                        'signal_period': signal,  # Note: not used in current strategy but included for completeness
                        'entry_min_mult': entry_min_mult,
                        'entry_max_mult': entry_max_mult,
                        'exit_min': exit_min,
                        'exit_max': exit_max,
                        'return_pct': stats['Return [%]'],
                        'win_rate': stats['Win Rate [%]'] if not pd.isna(stats['Win Rate [%]']) else 0,
                        'sharpe': stats['Sharpe Ratio'] if not pd.isna(stats['Sharpe Ratio']) else 0,
                        'max_dd': stats['Max. Drawdown [%]'],
                        'trades': stats['# Trades'],
                        'profit_factor': stats['Profit Factor'] if not pd.isna(stats['Profit Factor']) else 0,
                        'expectancy': stats['Expectancy [%]'] if not pd.isna(stats['Expectancy [%]']) else 0,
                    }
                    
                    results.append(result)
                    print(f"  → Return: {result['return_pct']:.2f}%, Trades: {result['trades']}, Sharpe: {result['sharpe']:.2f}")
                    
                except Exception as e:
                    print(f"  → ERROR: {str(e)}")
                    results.append({
                        'fast_period': fast,
                        'slow_period': slow,
                        'signal_period': signal,
                        'entry_min_mult': entry_min_mult,
                        'entry_max_mult': entry_max_mult,
                        'exit_min': exit_min,
                        'exit_max': exit_max,
                        'return_pct': None,
                        'win_rate': None,
                        'sharpe': None,
                        'max_dd': None,
                        'trades': 0,
                        'profit_factor': None,
                        'expectancy': None,
                        'error': str(e)
                    })
    
    # Create DataFrame
    df_results = pd.DataFrame(results)
    
    # Filter valid results
    print(f"\n[SCAN] Filtering results...")
    valid_results = df_results[
        (df_results['trades'] >= 10) &  # Minimum 10 trades
        (df_results['return_pct'] > -5)  # Return better than -5%
    ].copy()
    
    print(f"[SCAN] Valid results: {len(valid_results)}/{len(df_results)}")
    
    # Sort by return (descending)
    valid_results = valid_results.sort_values('return_pct', ascending=False)
    
    # Save results
    if output_file is None:
        output_dir = Path(__file__).parent.parent / "data" / "rbi_v3"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "parameter_scan_results.csv"
    
    df_results.to_csv(output_file, index=False)
    print(f"[SCAN] Results saved to: {output_file}")
    
    # Print top 5 results
    print(f"\n[SCAN] Top 5 Parameter Combinations:")
    print("=" * 100)
    for idx, row in valid_results.head(5).iterrows():
        print(f"Rank {len(valid_results) - list(valid_results.index).index(idx)}:")
        print(f"  Fast={row['fast_period']}, Slow={row['slow_period']}, Entry=({row['entry_min_mult']:.1f}, {row['entry_max_mult']:.1f}), Exit=({row['exit_min']:.4f}, {row['exit_max']:.4f})")
        print(f"  Return: {row['return_pct']:.2f}%, Trades: {row['trades']}, Win Rate: {row['win_rate']:.1f}%, Sharpe: {row['sharpe']:.2f}")
        print()
    
    return df_results, valid_results


if __name__ == "__main__":
    # Default data file path
    default_data_file = Path(__file__).parent.parent / "data" / "rbi" / "BTC-USD-5m.csv"
    
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    else:
        data_file = str(default_data_file)
    
    if not os.path.exists(data_file):
        print(f"[ERROR] Data file not found: {data_file}")
        print(f"[INFO] Usage: python macd_parameter_scanner.py [data_file_path]")
        sys.exit(1)
    
    print("=" * 100)
    print("MACD Parameter Scanner")
    print("=" * 100)
    
    results, valid_results = scan_macd_parameters(data_file)
    
    print(f"\n[SCAN] Complete! Scanned {len(results)} combinations, found {len(valid_results)} valid results.")
