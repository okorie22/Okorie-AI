import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

# Load data
print("[INFO] Loading data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-1d.csv')

# Clean and prepare data
price_data.columns = price_data.columns.str.strip().str.lower()
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Ensure proper column mapping
column_mapping = {
    'open': 'Open',
    'high': 'High', 
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
}

for old_col, new_col in column_mapping.items():
    if old_col in price_data.columns:
        price_data[new_col] = price_data[old_col]

# Set datetime index
if 'timestamp' in price_data.columns:
    price_data['datetime'] = pd.to_datetime(price_data['timestamp'])
elif 'date' in price_data.columns:
    price_data['datetime'] = pd.to_datetime(price_data['date'])
elif 'datetime' in price_data.columns:
    price_data['datetime'] = pd.to_datetime(price_data['datetime'])
else:
    # Try to find datetime column
    for col in price_data.columns:
        if 'time' in col.lower() or 'date' in col.lower():
            price_data['datetime'] = pd.to_datetime(price_data[col])
            break

price_data = price_data.set_index(pd.to_datetime(price_data['datetime']))

# Ensure required columns exist
required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
for col in required_cols:
    if col not in price_data.columns:
        raise ValueError(f"Required column '{col}' not found in data")

print(f"[INFO] Data loaded: {len(price_data)} rows, columns: {list(price_data.columns)}")
print(f"[INFO] Date range: {price_data.index[0]} to {price_data.index[-1]}")

class MultiPatternReversal(Strategy):
    def init(self):
        print("[STRATEGY] Initializing MultiPatternReversal strategy...")
        
        # Initialize trade counter for reduced logging
        self.trade_count = 0
        
        # Calculate candlestick patterns using TA-Lib
        self.cdl_doji = self.I(talib.CDLDOJI, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_engulfing = self.I(talib.CDLENGULFING, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_hammer = self.I(talib.CDLHAMMER, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        
        print("[STRATEGY] Indicators calculated successfully")
        
    def next(self):
        # DEBUG: Print basic info at start of each bar
        print(f"[DEBUG] Bar {len(self.data)}, Equity: ${self.equity:.2f}, Position: {self.position.size if self.position else 0}")
        
        # Print periodic summary every 100 bars
        if len(self.data) % 100 == 0:
            print(f"[SUMMARY] Bar {len(self.data)}, Equity: ${self.equity:.2f}")
            print(f"[SUMMARY] Doji: {self.cdl_doji[-1]}, Engulfing: {self.cdl_engulfing[-1]}, Hammer: {self.cdl_hammer[-1]}")
        
        # Check for entry conditions
        entry_signal = False
        pattern_type = None
        
        # DEBUG: Print pattern values
        print(f"[DEBUG] Pattern values - Doji: {self.cdl_doji[-1]}, Engulfing: {self.cdl_engulfing[-1]}, Hammer: {self.cdl_hammer[-1]}")
        
        # Check for bullish patterns (TA-Lib returns 100 for bullish patterns)
        if self.cdl_doji[-1] == 100:
            entry_signal = True
            pattern_type = "Bullish Doji"
            print(f"[DEBUG] Doji pattern detected: {self.cdl_doji[-1]} == 100 -> True")
        elif self.cdl_engulfing[-1] == 100:
            entry_signal = True
            pattern_type = "Bullish Engulfing"
            print(f"[DEBUG] Engulfing pattern detected: {self.cdl_engulfing[-1]} == 100 -> True")
        elif self.cdl_hammer[-1] == 100:
            entry_signal = True
            pattern_type = "Hammer"
            print(f"[DEBUG] Hammer pattern detected: {self.cdl_hammer[-1]} == 100 -> True")
        else:
            print(f"[DEBUG] No pattern detected: Doji={self.cdl_doji[-1]}, Engulfing={self.cdl_engulfing[-1]}, Hammer={self.cdl_hammer[-1]}")
        
        # Entry logic
        if entry_signal and not self.position:
            print(f"[DEBUG] Entry signal TRUE with pattern: {pattern_type}, No position: {not self.position}")
            
            # Calculate position size: 2% of equity (capped at 10% maximum)
            position_size_fraction = 0.02  # 2% of equity
            position_size_fraction = min(position_size_fraction, 0.10)  # Cap at 10%
            
            # DEBUG: Print position size calculation
            print(f"[DEBUG] Position size calc: equity={self.equity:.2f}, size_fraction={position_size_fraction:.6f}")
            
            # Set stop loss at -28.8% from entry price
            entry_price = self.data.Close[-1]
            stop_loss_price = entry_price * (1 - 0.288)
            
            # Set take profit levels according to ROI table
            take_profit_price = entry_price * (1 + 0.332)  # 33.2% target
            
            # DEBUG: Print stop and target prices
            print(f"[DEBUG] Entry price: {entry_price:.2f}, Stop loss: {stop_loss_price:.2f}, Take profit: {take_profit_price:.2f}")
            
            # Execute buy order with stop loss and take profit
            print(f"[DEBUG] Executing buy order with size={position_size_fraction}")
            self.buy(
                size=position_size_fraction,
                sl=stop_loss_price,
                tp=take_profit_price
            )
            self.trade_count += 1
            
            # Print trade execution
            print(f"[TRADE {self.trade_count}] {pattern_type} detected at bar {len(self.data)}")
            print(f"[TRADE {self.trade_count}] Position size: {position_size_fraction:.4f} ({position_size_fraction*100:.2f}% of equity)")
            
            # Initialize tracking for trailing stop
            self.highest_price_since_entry = entry_price
            
        # Manual trailing stop implementation
        if self.position:
            print(f"[DEBUG] Position exists: size={self.position.size}")
            # Get entry price from last trade
            if len(self.trades) > 0:
                entry_price = self.trades[-1].entry_price
                current_price = self.data.Close[-1]
                
                # Update highest price since entry
                if not hasattr(self, 'highest_price_since_entry'):
                    self.highest_price_since_entry = current_price
                else:
                    self.highest_price_since_entry = max(self.highest_price_since_entry, current_price)
                
                # Check if profit reaches +3.2% to activate trailing stop
                profit_pct = (current_price - entry_price) / entry_price
                print(f"[DEBUG] Current profit: {profit_pct:.4%}, Entry: {entry_price:.2f}, Current: {current_price:.2f}")
                print(f"[DEBUG] Highest since entry: {self.highest_price_since_entry:.2f}")
                
                if profit_pct >= 0.032:  # +3.2% threshold
                    print(f"[DEBUG] Profit threshold reached (+3.2%), checking trailing stop")
                    # Calculate trailing stop: 8.4% below highest price since entry
                    trailing_stop_price = self.highest_price_since_entry * (1 - 0.084)
                    print(f"[DEBUG] Trailing stop: {trailing_stop_price:.2f}")
                    
                    # Check if current price hits trailing stop
                    if current_price <= trailing_stop_price:
                        print(f"[DEBUG] Trailing stop hit at {current_price:.2f}, closing position")
                        self.position.close()
            else:
                print("[DEBUG] Position exists but no trades recorded")

# Run backtest
print("[INFO] Starting backtest...")
bt = Backtest(
    price_data[['Open', 'High', 'Low', 'Close', 'Volume']],
    MultiPatternReversal,
    cash=1000000,  # 1,000,000 initial capital
    commission=0.001,  # 0.1% commission
    exclusive_orders=True
)

stats = bt.run()
print(stats)
print(stats._strategy)
print(f"[FINAL] Total trades executed: {stats._strategy.trade_count}")