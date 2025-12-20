import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

class MultiPatternReversal(Strategy):
    def init(self):
        print("[STRATEGY] MultiPatternReversal initialized")
        
        # Calculate pattern recognition indicators using self.I() wrapper
        self.cdl_doji = self.I(talib.CDLDOJI, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_engulfing = self.I(talib.CDLENGULFING, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_hammer = self.I(talib.CDLHAMMER, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        
        # Initialize trade counter for reduced logging
        self.trade_count = 0
        
        # Debug counter for periodic prints
        self.bar_count = 0
        
        # Debug: Print initial indicator values
        print(f"[DEBUG INIT] Data length: {len(self.data)}")
        print(f"[DEBUG INIT] First few closes: {self.data.Close[0]:.2f}, {self.data.Close[1]:.2f}, {self.data.Close[2]:.2f}")
        
        # Debug: Print first few indicator values to verify calculation
        if len(self.data) > 5:
            print(f"[DEBUG INIT] First 5 Doji values: {[self.cdl_doji[i] for i in range(5)]}")
            print(f"[DEBUG INIT] First 5 Engulfing values: {[self.cdl_engulfing[i] for i in range(5)]}")
            print(f"[DEBUG INIT] First 5 Hammer values: {[self.cdl_hammer[i] for i in range(5)]}")
    
    def next(self):
        # Increment bar counter
        self.bar_count += 1
        
        # Print periodic summary every 100 bars
        if self.bar_count % 100 == 0:
            print(f"[SUMMARY] Bar {self.bar_count}, Equity: ${self.equity:.2f}, Position: {self.position.size if self.position else 0}")
            print(f"[SUMMARY] Indicators - Doji: {self.cdl_doji[-1]}, Engulfing: {self.cdl_engulfing[-1]}, Hammer: {self.cdl_hammer[-1]}")
        
        # Debug print for every bar
        print(f"[DEBUG] Bar {self.bar_count}, Equity: ${self.equity:.2f}, Position: {self.position.size if self.position else 0}, Close: ${self.data.Close[-1]:.2f}")
        
        # Skip if we don't have enough data
        if len(self.data) < 30:
            print(f"[DEBUG] Skipping - insufficient data: {len(self.data)} bars")
            return
        
        # Check if we're already in a position
        if self.position:
            print(f"[DEBUG] Managing existing position, size: {self.position.size}")
            # Manage existing position with trailing stop and ROI table
            self.manage_position()
        else:
            print(f"[DEBUG] Checking for entry signals")
            # Check for entry signals
            self.check_entry_signals()
    
    def check_entry_signals(self):
        # Entry condition: ANY bullish pattern detected
        entry_signal = False
        pattern_type = None
        
        # Debug print indicator values
        print(f"[DEBUG] Pattern values - Doji: {self.cdl_doji[-1]}, Engulfing: {self.cdl_engulfing[-1]}, Hammer: {self.cdl_hammer[-1]}")
        
        # Check each pattern for bullish signal (value == 100)
        if self.cdl_doji[-1] == 100:
            entry_signal = True
            pattern_type = "Doji"
            print(f"[DEBUG] Doji pattern detected: {self.cdl_doji[-1]}")
        elif self.cdl_engulfing[-1] == 100:
            entry_signal = True
            pattern_type = "Engulfing"
            print(f"[DEBUG] Engulfing pattern detected: {self.cdl_engulfing[-1]}")
        elif self.cdl_hammer[-1] == 100:
            entry_signal = True
            pattern_type = "Hammer"
            print(f"[DEBUG] Hammer pattern detected: {self.cdl_hammer[-1]}")
        
        print(f"[DEBUG] Entry signal: {entry_signal}, Pattern type: {pattern_type}")
        
        if entry_signal:
            # Calculate position size: 2% of equity (0.02 fraction)
            position_size = 0.02  # 2% of equity
            
            # Cap at maximum 10% of equity (safety check)
            position_size = min(position_size, 0.10)
            
            print(f"[DEBUG] Position size calculation: equity=${self.equity:.2f}, size_fraction={position_size:.4f}")
            
            # Check if we have enough cash
            required_cash = self.equity * position_size
            print(f"[DEBUG] Required cash: ${required_cash:.2f}, Available: ${self.equity:.2f}")
            
            # Execute buy order - CRITICAL: Actually call self.buy()
            print(f"[DEBUG] EXECUTING BUY ORDER: size={position_size}, price=${self.data.Close[-1]:.2f}")
            self.buy(size=position_size)
            
            # Increment trade counter
            self.trade_count += 1
            
            # Print every trade for debugging
            print(f"[TRADE {self.trade_count}] {pattern_type} pattern detected at bar {self.bar_count}, Price: ${self.data.Close[-1]:.2f}, Size: {position_size*100:.1f}%")
        else:
            print(f"[DEBUG] No entry signal - all patterns: Doji={self.cdl_doji[-1]}, Engulfing={self.cdl_engulfing[-1]}, Hammer={self.cdl_hammer[-1]}")
    
    def manage_position(self):
        if not self.position:
            print("[DEBUG] No position to manage")
            return
        
        current_price = self.data.Close[-1]
        
        # Get entry price from last trade
        if self.trades:
            entry_price = self.trades[-1].entry_price
        else:
            print("[DEBUG] No trades found, cannot get entry price")
            return
        
        print(f"[DEBUG] Managing position - Entry: ${entry_price:.2f}, Current: ${current_price:.2f}, Size: {self.position.size}")
        
        # Calculate current profit/loss percentage
        current_pnl_pct = (current_price - entry_price) / entry_price * 100
        print(f"[DEBUG] Current PnL: {current_pnl_pct:.2f}%")
        
        # ROI Table (Time-Decaying Profit Targets)
        # Note: These are extremely long periods, so trailing stop will be primary exit
        
        # Immediate exit if 93.6% profit reached
        if current_pnl_pct >= 93.6:
            print(f"[DEBUG] ROI target 93.6% reached: {current_pnl_pct:.2f}%")
            self.position.close()
            print(f"[EXIT] ROI target 93.6% reached at bar {self.bar_count}, PnL: {current_pnl_pct:.1f}%")
            return
        
        # Trailing stop logic
        # Activate trailing stop after price moves 3.2% above entry
        if current_pnl_pct >= 3.2:
            # Calculate trailing stop price: 8.4% below current price
            trailing_stop_price = current_price * (1 - 0.084)
            print(f"[DEBUG] Trailing stop active - Current: ${current_price:.2f}, Stop: ${trailing_stop_price:.2f}, Low: ${self.data.Low[-1]:.2f}")
            
            # Check if price has fallen below trailing stop
            if self.data.Low[-1] <= trailing_stop_price:
                print(f"[DEBUG] Trailing stop triggered: Low=${self.data.Low[-1]:.2f} <= Stop=${trailing_stop_price:.2f}")
                self.position.close()
                print(f"[EXIT] Trailing stop triggered at bar {self.bar_count}, PnL: {current_pnl_pct:.1f}%")
                return
        
        # Fixed stop loss at -28.8%
        stop_loss_price = entry_price * (1 - 0.288)
        print(f"[DEBUG] Stop loss check - Entry: ${entry_price:.2f}, Stop: ${stop_loss_price:.2f}, Low: ${self.data.Low[-1]:.2f}")
        
        if self.data.Low[-1] <= stop_loss_price:
            print(f"[DEBUG] Stop loss triggered: Low=${self.data.Low[-1]:.2f} <= Stop=${stop_loss_price:.2f}")
            self.position.close()
            print(f"[EXIT] Stop loss triggered at bar {self.bar_count}, PnL: {current_pnl_pct:.1f}%")
            return
        
        print(f"[DEBUG] Position remains open - PnL: {current_pnl_pct:.2f}%")

# Load and prepare data
print("[INFO] Loading data...")

# Load OHLCV data
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()

# Drop any unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Debug: Print available columns
print(f"[DEBUG] Available columns after cleaning: {list(price_data.columns)}")

# Check for datetime column
datetime_col = None
for col in price_data.columns:
    if 'date' in col or 'time' in col or 'datetime' in col:
        datetime_col = col
        print(f"[DEBUG] Found datetime column: {col}")
        break

if datetime_col:
    # Convert to datetime and set as index
    price_data['datetime'] = pd.to_datetime(price_data[datetime_col])
    price_data = price_data.set_index('datetime')
    # Drop the original datetime column if it's different
    if datetime_col != 'datetime':
        price_data = price_data.drop(columns=[datetime_col])
else:
    print("[WARNING] No datetime column found, using index as time")

# Ensure proper column mapping
required_columns = ['open', 'high', 'low', 'close', 'volume']
column_mapping = {}

# Check for required columns (case-insensitive)
available_cols_lower = [col.lower() for col in price_data.columns]
print(f"[DEBUG] Lowercase columns: {available_cols_lower}")

for req in required_columns:
    if req in available_cols_lower:
        # Find the actual column name
        for actual_col in price_data.columns:
            if actual_col.lower() == req:
                column_mapping[actual_col] = req.capitalize()
                break
    else:
        print(f"[ERROR] Required column '{req}' not found in data")
        print(f"[DEBUG] Available columns: {list(price_data.columns)}")
        raise ValueError(f"Missing required column: {req}")

# Rename columns
price_data = price_data.rename(columns=column_mapping)
print(f"[DEBUG] After renaming, columns: {list(price_data.columns)}")

# Ensure we have all required columns with proper capitalization
for req in ['Open', 'High', 'Low', 'Close', 'Volume']:
    if req not in price_data.columns:
        print(f"[ERROR] Column '{req}' missing after renaming")
        print(f"[DEBUG] Available: {list(price_data.columns)}")
        raise ValueError(f"Missing column after renaming: {req}")

print(f"[INFO] Data loaded: {len(price_data)} rows, columns: {list(price_data.columns)}")
print(f"[INFO] Date range: {price_data.index[0]} to {price_data.index[-1]}")

# Check if resampling is needed (original code had resampling logic)
# For now, use the data as-is since it's already 15m
data_to_use = price_data
print(f"[INFO] Using {len(data_to_use)} rows of data")

# Run backtest
print("[INFO] Running backtest...")
bt = Backtest(data_to_use, MultiPatternReversal, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)