import pandas as pd
import talib
from backtesting import Backtest, Strategy

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
        # DEBUG: Print basic info at start of each bar
        print(f"[DEBUG] Bar {len(self.data)}, Equity: ${self.equity:.2f}, Position: {self.position.size if self.position else 0}")
        
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
        
        # DEBUG: Print indicator values
        print(f"[DEBUG] Doji[-1]: {self.cdl_doji[-1]}, Engulfing[-1]: {self.cdl_engulfing[-1]}, Hammer[-1]: {self.cdl_hammer[-1]}")
        
        # Check for entry signals (long positions only)
        entry_signal = False
        pattern_name = ""
        
        # Check for bullish patterns (value == 100)
        if self.cdl_doji[-1] == 100:
            entry_signal = True
            pattern_name = "Doji"
            print(f"[DEBUG] Doji pattern detected: {self.cdl_doji[-1]} == 100")
        elif self.cdl_engulfing[-1] == 100:
            entry_signal = True
            pattern_name = "Engulfing"
            print(f"[DEBUG] Engulfing pattern detected: {self.cdl_engulfing[-1]} == 100")
        elif self.cdl_hammer[-1] == 100:
            entry_signal = True
            pattern_name = "Hammer"
            print(f"[DEBUG] Hammer pattern detected: {self.cdl_hammer[-1]} == 100")
        
        # Execute entry if signal detected
        if entry_signal:
            print(f"[DEBUG] ENTRY SIGNAL: {pattern_name} pattern at bar {len(self.data)}")
            
            # Fixed position size: 2% of equity (fraction = 0.02)
            position_size = 0.02
            
            # Validate position size doesn't exceed 10% cap
            if position_size > 0.10:
                position_size = 0.10
                print(f"[WARNING] Position size capped at 10%")
            
            # DEBUG: Print position size calculation
            print(f"[DEBUG] Position size calc: equity={self.equity:.2f}, size={position_size:.6f} (fraction)")
            
            # Execute buy order
            self.buy(size=position_size)
            self.trade_count += 1
            
            # Reduced logging - only print every 10th trade
            if self.trade_count % 10 == 0:
                print(f"[TRADE {self.trade_count}] {pattern_name} pattern detected at bar {len(self.data)}")
                print(f"[TRADE {self.trade_count}] Position size: {position_size*100:.2f}% of equity")
            else:
                print(f"[TRADE EXECUTED] {pattern_name} pattern, size: {position_size*100:.2f}%")
        else:
            print(f"[DEBUG] No entry signal at bar {len(self.data)}")
        
        # Print periodic summary every 100 bars
        if len(self.data) % 100 == 0:
            print(f"[SUMMARY] Bar {len(self.data)}, Equity: ${self.equity:.2f}, Trades: {self.trade_count}")
            print(f"[SUMMARY] Current price: ${self.data.Close[-1]:.2f}")
            print(f"[SUMMARY] Indicator values - Doji: {self.cdl_doji[-1]}, Engulfing: {self.cdl_engulfing[-1]}, Hammer: {self.cdl_hammer[-1]}")

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
        print(f"[DEBUG] Available columns: {list(price_data.columns)}")
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
if 'datetime' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['datetime'])
    print(f"[DEBUG] Using 'datetime' column for index")
elif 'timestamp' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['timestamp'])
    print(f"[DEBUG] Using 'timestamp' column for index")
elif 'date' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['date'])
    print(f"[DEBUG] Using 'date' column for index")
else:
    # Try to find any datetime column
    datetime_found = False
    for col in price_data.columns:
        if 'time' in col.lower() or 'date' in col.lower():
            price_data.index = pd.to_datetime(price_data[col])
            print(f"[DEBUG] Using '{col}' column for index")
            datetime_found = True
            break
    
    if not datetime_found:
        print(f"[ERROR] No datetime column found. Available columns: {list(price_data.columns)}")
        raise ValueError("No datetime column found in data")

# Ensure we have the required columns after renaming
print(f"[DEBUG] Final columns: {list(price_data.columns)}")
print(f"[DEBUG] Index type: {type(price_data.index)}")

# Check data quality
print(f"[INFO] Data loaded: {len(price_data)} rows, {len(price_data.columns)} columns")
print(f"[INFO] Date range: {price_data.index[0]} to {price_data.index[-1]}")
print(f"[INFO] Sample data:")
print(price_data[['Open', 'High', 'Low', 'Close', 'Volume']].head())

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