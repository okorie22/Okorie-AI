import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

# Load data
print("[INFO] Loading price data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-1h.csv')
print(f"[DEBUG] Price data shape: {price_data.shape}")
print(f"[DEBUG] Price data columns: {list(price_data.columns)}")

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()
print(f"[DEBUG] Cleaned columns: {list(price_data.columns)}")

# Drop any unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Ensure required columns exist
required_cols = ['open', 'high', 'low', 'close', 'volume']
for col in required_cols:
    if col not in price_data.columns:
        print(f"[ERROR] Missing required column: {col}")
        raise ValueError(f"Missing required column: {col}")

# Set datetime index
if 'timestamp' in price_data.columns:
    price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
    price_data = price_data.set_index('timestamp')
elif 'date' in price_data.columns:
    price_data['date'] = pd.to_datetime(price_data['date'])
    price_data = price_data.set_index('date')
else:
    print("[ERROR] No timestamp or date column found")
    raise ValueError("No timestamp or date column found")

# Capitalize column names for backtesting.py
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

print(f"[INFO] Data loaded successfully. Shape: {price_data.shape}")
print(f"[INFO] Date range: {price_data.index[0]} to {price_data.index[-1]}")

class BandReversion(Strategy):
    def init(self):
        print("[STRATEGY] Initializing BandReversion strategy...")
        
        # Calculate Bollinger Bands (period=20, std=2)
        self.bb_middle = self.I(talib.SMA, self.data.Close, timeperiod=20)
        self.bb_std = self.I(talib.STDDEV, self.data.Close, timeperiod=20)
        self.bb_upper = self.I(lambda: self.bb_middle + 2 * self.bb_std)
        self.bb_lower = self.I(lambda: self.bb_middle - 2 * self.bb_std)
        
        # Calculate RSI (period=14)
        self.rsi = self.I(talib.RSI, self.data.Close, timeperiod=14)
        
        # Initialize trade counter
        self.trade_count = 0
        print("[STRATEGY] Initialization complete")
    
    def next(self):
        # Skip if we don't have enough data for indicators
        if len(self.data) < 30:
            return
        
        # Entry conditions: Price below BB_lower AND RSI < 30
        price_below_bb = self.data.Close[-1] < self.bb_lower[-1]
        rsi_oversold = self.rsi[-1] < 30
        
        # Exit condition: RSI > 70
        rsi_overbought = self.rsi[-1] > 70
        
        # Check for entry signal (no existing position)
        if not self.position and price_below_bb and rsi_oversold:
            # Calculate position size: 2% of equity (capped at 10%)
            position_size = min(0.02, 0.10)
            
            # Execute buy order
            self.buy(size=position_size)
            self.trade_count += 1
            
            # Set stop loss at -25%
            entry_price = self.data.Close[-1]
            stop_price = entry_price * 0.75  # -25% stop loss
            
            # Print trade entry (every 10th trade)
            if self.trade_count % 10 == 0:
                print(f"[TRADE {self.trade_count}] LONG entry at bar {len(self.data)}, Price: ${entry_price:.2f}, Size: {position_size:.4f} ({position_size*100:.2f}% of equity), Stop: ${stop_price:.2f}")
        
        # Check for exit signal (existing long position)
        elif self.position and rsi_overbought:
            # Close position
            self.position.close()
            
            # Print trade exit (every 10th trade)
            if self.trade_count % 10 == 0:
                print(f"[TRADE EXIT] Closing position at bar {len(self.data)}, Price: ${self.data.Close[-1]:.2f}")
        
        # Print periodic summary (every 200 bars)
        if len(self.data) % 200 == 0:
            print(f"[SUMMARY] Bar {len(self.data)}, Equity: ${self.equity:.2f}, Trades: {self.trade_count}")

# Run backtest
print("\n[INFO] Starting backtest...")
bt = Backtest(price_data, BandReversion, cash=1000000, commission=.002)
stats = bt.run()
print("\n" + "="*80)
print("BACKTEST RESULTS")
print("="*80)
print(stats)
print("\n" + "="*80)
print("STRATEGY DETAILS")
print("="*80)
print(stats._strategy)
print(f"\n[FINAL] Total trades executed: {stats._strategy.trade_count}")