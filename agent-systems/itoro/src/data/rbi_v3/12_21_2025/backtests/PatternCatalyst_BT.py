import pandas as pd
import talib
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

class PatternCatalyst(Strategy):
    def init(self):
        print("[STRATEGY] PatternCatalyst initialized")
        
        # Initialize pattern indicators using self.I()
        self.engulfing = self.I(talib.CDLENGULFING, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.hammer = self.I(talib.CDLHAMMER, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.doji = self.I(talib.CDLDOJI, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.morning_star = self.I(talib.CDLMORNINGSTAR, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.evening_star = self.I(talib.CDLEVENINGSTAR, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        
        # Strategy parameters
        self.selected_pattern = 'engulfing'  # Options: engulfing, hammer, doji, morning_star, evening_star
        self.risk_percentage = 0.02  # 2% risk per trade (within 1-3% range)
        self.initial_stop_loss_pct = 0.288  # -28.8% initial stop loss
        self.trailing_activation_pct = 0.084  # +8.4% profit to activate trailing stop
        self.trailing_offset_pct = 0.084  # 8.4% trailing offset
        self.min_profit_pct = 0.032  # +3.2% minimum profit guarantee
        
        # Initialize counters
        self.trade_count = 0
        self.bar_count = 0
        
    def next(self):
        self.bar_count += 1
        
        # Print summary every 100 bars
        if self.bar_count % 100 == 0:
            print(f"[SUMMARY] Bar {self.bar_count}, Equity: ${self.equity:.2f}, Cash: ${self.cash:.2f}")
        
        # Exit logic - check for trailing stop
        if self.position:
            current_price = self.data.Close[-1]
            entry_price = self.position.entry_price
            
            # Calculate current profit percentage
            current_profit_pct = (current_price - entry_price) / entry_price
            
            # Check if trailing stop should be activated
            if current_profit_pct >= self.trailing_activation_pct:
                # Calculate trailing stop price
                highest_since_entry = max(self.data.High[self.position.entry_bar:len(self.data)])
                trailing_stop_price = highest_since_entry * (1 - self.trailing_offset_pct)
                
                # Ensure minimum profit guarantee
                min_profit_price = entry_price * (1 + self.min_profit_pct)
                trailing_stop_price = max(trailing_stop_price, min_profit_price)
                
                # Exit if price hits trailing stop
                if current_price <= trailing_stop_price:
                    if self.trade_count % 10 == 0:
                        print(f"[TRAILING STOP] Exiting at bar {self.bar_count}, Price: {current_price:.2f}")
                    self.position.close()
                    return
            
            # Check initial stop loss (only if trailing stop not active)
            else:
                stop_loss_price = entry_price * (1 - self.initial_stop_loss_pct)
                if current_price <= stop_loss_price:
                    if self.trade_count % 10 == 0:
                        print(f"[STOP LOSS] Exiting at bar {self.bar_count}, Price: {current_price:.2f}")
                    self.position.close()
                    return
        
        # Entry logic - only if no position is open
        if not self.position:
            # Get the selected pattern indicator
            if self.selected_pattern == 'engulfing':
                pattern_signal = self.engulfing[-1]
            elif self.selected_pattern == 'hammer':
                pattern_signal = self.hammer[-1]
            elif self.selected_pattern == 'doji':
                pattern_signal = self.doji[-1]
            elif self.selected_pattern == 'morning_star':
                pattern_signal = self.morning_star[-1]
            elif self.selected_pattern == 'evening_star':
                pattern_signal = self.evening_star[-1]
            else:
                pattern_signal = 0
            
            # Check for bullish pattern signal (+100)
            if pattern_signal == 100:
                # Calculate position size based on risk percentage
                current_price = self.data.Close[-1]
                stop_loss_price = current_price * (1 - self.initial_stop_loss_pct)
                stop_distance = current_price - stop_loss_price
                
                # Calculate risk amount (2% of equity)
                risk_amount = self.equity * self.risk_percentage
                
                # Calculate position size in units
                desired_units = int(round(risk_amount / stop_distance))
                
                # Calculate maximum units based on 10% equity cap
                max_units = int(self.equity * 0.10 / current_price)
                
                # Apply cap and ensure minimum 1 unit
                position_units = max(1, min(desired_units, max_units))
                
                # Calculate position value and percentage
                position_value = position_units * current_price
                position_pct = position_value / self.equity
                
                # Validate position doesn't exceed 10% cap
                if position_pct > 0.10:
                    print(f"[WARNING] Position size {position_pct*100:.2f}% exceeds 10% cap, capping at 10%")
                    position_units = max_units
                    position_value = position_units * current_price
                    position_pct = position_value / self.equity
                
                # Execute buy order
                if self.trade_count % 10 == 0:
                    print(f"[ENTRY] {self.selected_pattern} pattern detected at bar {self.bar_count}")
                    print(f"[POSITION] Size: {position_units} units ({position_pct*100:.2f}% of equity)")
                    print(f"[RISK] Stop loss: {stop_loss_price:.2f} ({self.initial_stop_loss_pct*100:.1f}%)")
                
                self.buy(size=position_units)
                self.trade_count += 1

# Load and prepare data
print("[INFO] Loading data...")
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
if 'timestamp' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['timestamp'])
elif 'date' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['date'])
elif 'time' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['time'])
else:
    print("[WARNING] No timestamp column found, using index as time")

print(f"[INFO] Data loaded: {len(price_data)} rows, {len(price_data.columns)} columns")
print(f"[DEBUG] Data columns: {list(price_data.columns)}")
print(f"[DEBUG] Data range: {price_data.index[0]} to {price_data.index[-1]}")

# Run backtest
print("[INFO] Starting backtest...")
bt = Backtest(price_data, PatternCatalyst, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)