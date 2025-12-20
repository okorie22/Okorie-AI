import pandas as pd
import talib
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

class MultiPatternReversal(Strategy):
    def init(self):
        print("[STRATEGY] Initializing MultiPatternReversal strategy")
        
        # Calculate candlestick patterns using self.I() wrapper
        self.cdl_doji = self.I(talib.CDLDOJI, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_engulfing = self.I(talib.CDLENGULFING, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_hammer = self.I(talib.CDLHAMMER, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        
        # Initialize trade counter for reduced logging
        self.trade_count = 0
        
        print("[STRATEGY] Indicators calculated successfully")
    
    def next(self):
        # Check if we already have a position
        if self.position:
            # Check for exit conditions based on position profit/loss percentage
            current_pl_pct = self.position.pl_pct
            
            # Exit if profit reaches 5% or loss reaches 3%
            if current_pl_pct >= 0.05 or current_pl_pct <= -0.03:
                if self.position.is_long:
                    self.position.close()
                    self.trade_count += 1
                    if self.trade_count % 10 == 0:
                        print(f"[TRADE {self.trade_count}] Exit at bar {len(self.data)}, PL: {current_pl_pct*100:.2f}%")
                return
        
        # Check for entry signals (long positions only)
        entry_signal = False
        
        # Check for bullish patterns (value == 100)
        if self.cdl_doji[-1] == 100:
            entry_signal = True
            pattern_name = "Doji"
        elif self.cdl_engulfing[-1] == 100:
            entry_signal = True
            pattern_name = "Engulfing"
        elif self.cdl_hammer[-1] == 100:
            entry_signal = True
            pattern_name = "Hammer"
        
        # Execute entry if signal detected
        if entry_signal:
            # Fixed position size: 2% of equity (fraction = 0.02)
            position_size = 0.02
            
            # Validate position size doesn't exceed 10% cap
            if position_size > 0.10:
                position_size = 0.10
                print(f"[WARNING] Position size capped at 10%")
            
            # Execute buy order
            self.buy(size=position_size)
            self.trade_count += 1
            
            # Reduced logging - only print every 10th trade
            if self.trade_count % 10 == 0:
                print(f"[TRADE {self.trade_count}] {pattern_name} pattern detected at bar {len(self.data)}")
                print(f"[TRADE {self.trade_count}] Position size: {position_size*100:.2f}% of equity")
        
        # Print periodic summary every 100 bars
        if len(self.data) % 100 == 0:
            print(f"[SUMMARY] Bar {len(self.data)}, Equity: ${self.equity:.2f}, Trades: {self.trade_count}")

# Load and prepare data
print("[INFO] Loading daily BTC data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-1d.csv')

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()

# Drop any unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Ensure proper column mapping
required_columns = ['open', 'high', 'low', 'close', 'volume']
for col in required_columns:
    if col not in price_data.columns:
        print(f"[ERROR] Missing required column: {col}")
        raise ValueError(f"Missing required column: {col}")

# Rename columns to proper case for backtesting.py
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High', 
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

# Set datetime index
if 'timestamp' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['timestamp'])
elif 'date' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['date'])
else:
    # Try to find any datetime column
    for col in price_data.columns:
        if 'time' in col.lower() or 'date' in col.lower():
            price_data.index = pd.to_datetime(price_data[col])
            break

print(f"[INFO] Data loaded: {len(price_data)} rows, {len(price_data.columns)} columns")
print(f"[INFO] Date range: {price_data.index[0]} to {price_data.index[-1]}")

# Check if we have minimum 30 days of data
if len(price_data) < 30:
    print(f"[WARNING] Only {len(price_data)} days of data available, minimum 30 recommended")

# Run backtest
print("[INFO] Starting backtest...")
bt = Backtest(price_data, MultiPatternReversal, cash=1000000, commission=.002)

# Run optimization for basic parameters (if needed)
stats = bt.run()

print("[INFO] Backtest complete")
print(f"[FINAL] Total trades executed: {stats['# Trades']}")
print("\n" + "="*50)
print("BACKTEST RESULTS")
print("="*50)
print(stats)
print("\n" + "="*50)
print("STRATEGY DETAILS")
print("="*50)
print(stats._strategy)