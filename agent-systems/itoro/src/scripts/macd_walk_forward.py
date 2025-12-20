"""
MACD Walk-Forward Optimization Framework
Implements rolling window optimization to test strategy robustness across different time periods.
"""

import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib
from pathlib import Path
from datetime import datetime, timedelta
import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import parameter scanner's strategy class
from scripts.macd_parameter_scanner import ParameterizedMACDStrategy, load_data


def optimize_parameters_on_window(train_data, param_grid=None):
    """
    Optimize MACD parameters on a training window
    
    Parameters:
    - train_data: Training data DataFrame
    - param_grid: Optional custom parameter grid, otherwise uses default
    
    Returns:
    - Dictionary with best parameters and performance
    """
    if param_grid is None:
        # Default parameter grid (smaller than full scan for speed)
        param_grid = {
            'fast_period': [8, 12, 15],
            'slow_period': [21, 26, 30],
            'entry_min_mult': [-2.0, -1.5, -1.0],
            'entry_max_mult': [-1.0, -0.5, -0.2],
            'exit_min': [-0.025, -0.02],
            'exit_max': [-0.01, -0.005],
        }
    
    best_params = None
    best_return = float('-inf')
    best_stats = None
    
    total_combinations = (
        len(param_grid['fast_period']) *
        len(param_grid['slow_period']) *
        len(param_grid['entry_min_mult']) *
        len(param_grid['entry_max_mult']) *
        len(param_grid['exit_min']) *
        len(param_grid['exit_max'])
    )
    
    current = 0
    
    for fast in param_grid['fast_period']:
        for slow in param_grid['slow_period']:
            for entry_min_mult in param_grid['entry_min_mult']:
                for entry_max_mult in param_grid['entry_max_mult']:
                    for exit_min in param_grid['exit_min']:
                        for exit_max in param_grid['exit_max']:
                            current += 1
                            
                            try:
                                strategy_class = type('MACDStrategy', (ParameterizedMACDStrategy,), {})
                                
                                bt = Backtest(
                                    train_data,
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
                                
                                # Only consider strategies with at least 5 trades
                                if stats['# Trades'] >= 5:
                                    return_pct = stats['Return [%]']
                                    
                                    if return_pct > best_return:
                                        best_return = return_pct
                                        best_params = {
                                            'fast_period': fast,
                                            'slow_period': slow,
                                            'entry_min_mult': entry_min_mult,
                                            'entry_max_mult': entry_max_mult,
                                            'exit_min': exit_min,
                                            'exit_max': exit_max,
                                        }
                                        best_stats = {
                                            'return_pct': return_pct,
                                            'trades': stats['# Trades'],
                                            'win_rate': stats['Win Rate [%]'] if not pd.isna(stats['Win Rate [%]']) else 0,
                                            'sharpe': stats['Sharpe Ratio'] if not pd.isna(stats['Sharpe Ratio']) else 0,
                                            'max_dd': stats['Max. Drawdown [%]'],
                                        }
                                        
                            except Exception as e:
                                # Skip failed combinations
                                continue
    
    return best_params, best_stats


def walk_forward_optimization(data, window_days=7, test_days=3, param_grid=None):
    """
    Perform walk-forward optimization with rolling windows
    
    Parameters:
    - data: Full dataset DataFrame with datetime index
    - window_days: Number of days for training window
    - test_days: Number of days for testing window
    - param_grid: Optional custom parameter grid
    
    Returns:
    - DataFrame with results for each window
    """
    results = []
    start_date = data.index[0]
    end_date = data.index[-1]
    
    current_date = start_date
    window_num = 0
    
    print(f"[WALK-FORWARD] Starting walk-forward optimization")
    print(f"[WALK-FORWARD] Training window: {window_days} days, Testing window: {test_days} days")
    print(f"[WALK-FORWARD] Data range: {start_date} to {end_date}")
    print()
    
    while current_date + timedelta(days=window_days + test_days) <= end_date:
        window_num += 1
        train_start = current_date
        train_end = current_date + timedelta(days=window_days)
        test_start = train_end
        test_end = test_start + timedelta(days=test_days)
        
        # Extract windows
        train_data = data[train_start:train_end].copy()
        test_data = data[test_start:test_end].copy()
        
        if len(train_data) < 100 or len(test_data) < 20:
            print(f"[WALK-FORWARD] Window {window_num}: Skipping (insufficient data)")
            current_date += timedelta(days=test_days)
            continue
        
        print(f"[WALK-FORWARD] Window {window_num}:")
        print(f"  Training: {train_start.date()} to {train_end.date()} ({len(train_data)} bars)")
        print(f"  Testing:  {test_start.date()} to {test_end.date()} ({len(test_data)} bars)")
        
        # Optimize on training data
        print(f"  Optimizing parameters on training data...")
        best_params, train_stats = optimize_parameters_on_window(train_data, param_grid)
        
        if best_params is None:
            print(f"  → No valid parameters found, skipping window")
            current_date += timedelta(days=test_days)
            continue
        
        print(f"  → Best params: fast={best_params['fast_period']}, slow={best_params['slow_period']}, "
              f"entry=({best_params['entry_min_mult']:.1f}, {best_params['entry_max_mult']:.1f}), "
              f"exit=({best_params['exit_min']:.4f}, {best_params['exit_max']:.4f})")
        print(f"  → Train return: {train_stats['return_pct']:.2f}%, Trades: {train_stats['trades']}")
        
        # Test on out-of-sample data
        print(f"  Testing on out-of-sample data...")
        try:
            strategy_class = type('MACDStrategy', (ParameterizedMACDStrategy,), {})
            
            bt = Backtest(
                test_data,
                strategy_class,
                cash=1000000,
                commission=0.002,
                exclusive_orders=True
            )
            
            test_stats = bt.run(**best_params)
            
            result = {
                'window_num': window_num,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'train_bars': len(train_data),
                'test_bars': len(test_data),
                'fast_period': best_params['fast_period'],
                'slow_period': best_params['slow_period'],
                'entry_min_mult': best_params['entry_min_mult'],
                'entry_max_mult': best_params['entry_max_mult'],
                'exit_min': best_params['exit_min'],
                'exit_max': best_params['exit_max'],
                'train_return': train_stats['return_pct'],
                'train_trades': train_stats['trades'],
                'train_sharpe': train_stats['sharpe'],
                'test_return': test_stats['Return [%]'],
                'test_trades': test_stats['# Trades'],
                'test_sharpe': test_stats['Sharpe Ratio'] if not pd.isna(test_stats['Sharpe Ratio']) else 0,
                'test_win_rate': test_stats['Win Rate [%]'] if not pd.isna(test_stats['Win Rate [%]']) else 0,
                'test_max_dd': test_stats['Max. Drawdown [%]'],
            }
            
            results.append(result)
            
            print(f"  → Test return: {result['test_return']:.2f}%, Trades: {result['test_trades']}, "
                  f"Sharpe: {result['test_sharpe']:.2f}")
            
        except Exception as e:
            print(f"  → ERROR testing: {str(e)}")
            result = {
                'window_num': window_num,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'error': str(e)
            }
            results.append(result)
        
        print()
        
        # Slide window forward
        current_date += timedelta(days=test_days)
    
    df_results = pd.DataFrame(results)
    
    return df_results


def analyze_walk_forward_results(df_results):
    """Analyze walk-forward results and calculate robustness metrics"""
    if len(df_results) == 0:
        print("[ANALYSIS] No results to analyze")
        return None
    
    # Filter out error rows
    valid_results = df_results[df_results['test_return'].notna()].copy()
    
    if len(valid_results) == 0:
        print("[ANALYSIS] No valid results to analyze")
        return None
    
    print("=" * 100)
    print("WALK-FORWARD ANALYSIS RESULTS")
    print("=" * 100)
    
    # Basic statistics
    print(f"\n[ANALYSIS] Total Windows: {len(df_results)}")
    print(f"[ANALYSIS] Valid Windows: {len(valid_results)}")
    
    # Consistency metrics
    positive_windows = (valid_results['test_return'] > 0).sum()
    consistency_pct = (positive_windows / len(valid_results)) * 100
    print(f"[ANALYSIS] Positive Return Windows: {positive_windows}/{len(valid_results)} ({consistency_pct:.1f}%)")
    
    # Performance metrics
    avg_test_return = valid_results['test_return'].mean()
    std_test_return = valid_results['test_return'].std()
    median_test_return = valid_results['test_return'].median()
    
    print(f"\n[ANALYSIS] Test Return Statistics:")
    print(f"  Average: {avg_test_return:.2f}%")
    print(f"  Median:  {median_test_return:.2f}%")
    print(f"  Std Dev: {std_test_return:.2f}%")
    print(f"  Min:     {valid_results['test_return'].min():.2f}%")
    print(f"  Max:     {valid_results['test_return'].max():.2f}%")
    
    # Stability metrics
    avg_sharpe = valid_results['test_sharpe'].mean()
    print(f"\n[ANALYSIS] Average Sharpe Ratio: {avg_sharpe:.2f}")
    
    # Parameter frequency analysis
    print(f"\n[ANALYSIS] Most Common Parameters:")
    param_freq = valid_results.groupby(['fast_period', 'slow_period']).size().sort_values(ascending=False)
    for (fast, slow), count in param_freq.head(5).items():
        pct = (count / len(valid_results)) * 100
        print(f"  Fast={fast}, Slow={slow}: {count} windows ({pct:.1f}%)")
    
    # Best and worst windows
    best_window = valid_results.loc[valid_results['test_return'].idxmax()]
    worst_window = valid_results.loc[valid_results['test_return'].idxmin()]
    
    print(f"\n[ANALYSIS] Best Window (Window {best_window['window_num']}):")
    print(f"  Test Return: {best_window['test_return']:.2f}%")
    print(f"  Params: fast={best_window['fast_period']}, slow={best_window['slow_period']}")
    
    print(f"\n[ANALYSIS] Worst Window (Window {worst_window['window_num']}):")
    print(f"  Test Return: {worst_window['test_return']:.2f}%")
    print(f"  Params: fast={worst_window['fast_period']}, slow={worst_window['slow_period']}")
    
    return {
        'total_windows': len(df_results),
        'valid_windows': len(valid_results),
        'consistency_pct': consistency_pct,
        'avg_test_return': avg_test_return,
        'std_test_return': std_test_return,
        'median_test_return': median_test_return,
        'avg_sharpe': avg_sharpe,
    }


if __name__ == "__main__":
    # Default data file path
    default_data_file = Path(__file__).parent.parent / "data" / "rbi" / "BTC-USD-5m.csv"
    
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    else:
        data_file = str(default_data_file)
    
    if not os.path.exists(data_file):
        print(f"[ERROR] Data file not found: {data_file}")
        print(f"[INFO] Usage: python macd_walk_forward.py [data_file_path] [window_days] [test_days]")
        sys.exit(1)
    
    # Parse optional arguments
    window_days = 7
    test_days = 3
    if len(sys.argv) > 2:
        window_days = int(sys.argv[2])
    if len(sys.argv) > 3:
        test_days = int(sys.argv[3])
    
    print("=" * 100)
    print("MACD Walk-Forward Optimization")
    print("=" * 100)
    
    # Load data
    print(f"[LOAD] Loading data from: {data_file}")
    price_data = load_data(data_file)
    print(f"[LOAD] Data loaded: {len(price_data)} rows")
    print(f"[LOAD] Date range: {price_data.index[0]} to {price_data.index[-1]}")
    print()
    
    # Run walk-forward optimization
    results = walk_forward_optimization(price_data, window_days=window_days, test_days=test_days)
    
    # Save results
    output_dir = Path(__file__).parent.parent / "data" / "rbi_v3"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"walk_forward_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    results.to_csv(output_file, index=False)
    print(f"[SAVE] Results saved to: {output_file}")
    
    # Analyze results
    analysis = analyze_walk_forward_results(results)
    
    # Save analysis summary
    if analysis:
        summary_file = output_dir / f"walk_forward_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"[SAVE] Summary saved to: {summary_file}")
    
    print(f"\n[COMPLETE] Walk-forward optimization complete!")
