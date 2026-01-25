import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

# Load data
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-1d.csv')
price_data.columns = price_data.columns.str.strip().str.lower()
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Fix column names - check what columns actually exist
print(f"[DEBUG] Original columns: {list(price_data.columns)}")

# Handle timestamp column - check for different naming
timestamp_col = None
for col in price_data.columns:
    if 'time' in col.lower() or 'date' in col.lower():
        timestamp_col = col
        break

if timestamp_col:
    price_data['datetime'] = pd.to_datetime(price_data[timestamp_col])
else:
    # Create datetime index if no timestamp column found
    price_data['datetime'] = pd.date_range(start='2020-01-01', periods=len(price_data), freq='D')

price_data = price_data.set_index('datetime')

# Rename columns to match backtesting.py requirements
column_mapping = {}
for col in price_data.columns:
    col_lower = col.lower()
    if col_lower == 'open':
        column_mapping[col] = 'Open'
    elif col_lower == 'high':
        column_mapping[col] = 'High'
    elif col_lower == 'low':
        column_mapping[col] = 'Low'
    elif col_lower == 'close':
        column_mapping[col] = 'Close'
    elif col_lower == 'volume':
        column_mapping[col] = 'Volume'

price_data = price_data.rename(columns=column_mapping)

# Ensure required columns exist
required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
for col in required_cols:
    if col not in price_data.columns:
        print(f"[WARNING] Missing column {col}, creating dummy data")
        if col == 'Volume':
            price_data[col] = 1000
        else:
            price_data[col] = price_data['Close'] if 'Close' in price_data.columns else 100

print(f"[DEBUG] Final columns: {list(price_data.columns)}")
print(f"[DEBUG] Data shape: {price_data.shape}")
print(f"[DEBUG] First few rows:\n{price_data.head()}")

class PatternSync(Strategy):
    def init(self):
        print("[STRATEGY] PatternSync initialized for daily timeframe")
        self.trade_count = 0
        
        # Calculate all five candlestick patterns using self.I()
        self.cdl_engulfing = self.I(talib.CDLENGULFING, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_hammer = self.I(talib.CDLHAMMER, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_doji = self.I(talib.CDLDOJI, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_morningstar = self.I(talib.CDLMORNINGSTAR, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_eveningstar = self.I(talib.CDLEVENINGSTAR, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        
        # Parameters
        self.enable_engulfing = True
        self.enable_hammer = True
        self.enable_doji = True
        self.enable_morningstar = True
        self.enable_eveningstar = True
        
        # Risk management parameters
        self.initial_stop_loss = 0.288  # -28.8%
        self.trailing_activation = 0.084  # +8.4%
        self.trailing_offset = 0.032  # +3.2%
        self.position_size_pct = 0.02  # 2% of equity
        
        # Track highest price for trailing stop
        self.highest_price = 0
        self.entry_price = 0
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # DEBUG: Print basic info every bar
        print(f"[DEBUG] Bar {current_bar}, Equity: ${self.equity:.2f}, Position: {self.position.size if self.position else 0}")
        
        # Print summary every 200 bars
        if current_bar % 200 == 0 and current_bar > 0:
            print(f"[SUMMARY] Bar {current_bar}, Equity: ${self.equity:.2f}, Trades: {self.trade_count}")
            print(f"[SUMMARY] Current price: ${self.data.Close[-1]:.2f}")
        
        # Check for long entry signals
        if not self.position:
            long_signal = False
            pattern_name = ""
            
            # DEBUG: Print pattern values
            print(f"[DEBUG] Pattern values - Engulfing: {self.cdl_engulfing[-1] if len(self.cdl_engulfing) > 0 else 'N/A'}, "
                  f"Hammer: {self.cdl_hammer[-1] if len(self.cdl_hammer) > 0 else 'N/A'}, "
                  f"Doji: {self.cdl_doji[-1] if len(self.cdl_doji) > 0 else 'N/A'}, "
                  f"Morning Star: {self.cdl_morningstar[-1] if len(self.cdl_morningstar) > 0 else 'N/A'}, "
                  f"Evening Star: {self.cdl_eveningstar[-1] if len(self.cdl_eveningstar) > 0 else 'N/A'}")
            
            # Check each enabled pattern for bullish reversal
            if self.enable_engulfing and len(self.cdl_engulfing) > 0 and self.cdl_engulfing[-1] == 100:
                long_signal = True
                pattern_name = "Engulfing"
                print(f"[DEBUG] Engulfing pattern detected: {self.cdl_engulfing[-1]}")
            elif self.enable_hammer and len(self.cdl_hammer) > 0 and self.cdl_hammer[-1] == 100:
                long_signal = True
                pattern_name = "Hammer"
                print(f"[DEBUG] Hammer pattern detected: {self.cdl_hammer[-1]}")
            elif self.enable_doji and len(self.cdl_doji) > 0 and self.cdl_doji[-1] == 100:
                long_signal = True
                pattern_name = "Doji"
                print(f"[DEBUG] Doji pattern detected: {self.cdl_doji[-1]}")
            elif self.enable_morningstar and len(self.cdl_morningstar) > 0 and self.cdl_morningstar[-1] == 100:
                long_signal = True
                pattern_name = "Morning Star"
                print(f"[DEBUG] Morning Star pattern detected: {self.cdl_morningstar[-1]}")
            elif self.enable_eveningstar and len(self.cdl_eveningstar) > 0 and self.cdl_eveningstar[-1] == -100:
                long_signal = True
                pattern_name = "Evening Star (bearish reversal)"
                print(f"[DEBUG] Evening Star pattern detected: {self.cdl_eveningstar[-1]}")
            
            if long_signal:
                # Calculate position size (capped at 10% of equity)
                position_size = min(self.position_size_pct, 0.10)
                
                # DEBUG: Print position size calculation
                print(f"[DEBUG] Position size calc: equity=${self.equity:.2f}, size_pct={self.position_size_pct}, "
                      f"capped_size={position_size}, position_size_fraction={position_size:.6f}")
                
                # Execute buy order
                print(f"[ENTRY SIGNAL] {pattern_name} pattern at bar {current_bar}, price: ${self.data.Close[-1]:.2f}, "
                      f"size: {position_size*100:.2f}% of equity")
                
                # CRITICAL: Actually call self.buy() to execute trade
                self.buy(size=position_size)
                self.trade_count += 1
                
                # Store entry price for stop loss calculations
                self.entry_price = self.data.Close[-1]
                self.highest_price = self.entry_price
                
                # Print every trade
                print(f"[TRADE EXECUTED #{self.trade_count}] {pattern_name} pattern at bar {current_bar}, "
                      f"entry: ${self.entry_price:.2f}, size: {position_size*100:.2f}%")
                
        # Manage open position
        if self.position:
            current_price = self.data.Close[-1]
            
            # Update highest price
            if current_price > self.highest_price:
                self.highest_price = current_price
                print(f"[DEBUG] New highest price: ${self.highest_price:.2f}")
            
            # Check for exit signals (bearish patterns)
            exit_signal = False
            exit_reason = ""
            
            if self.enable_engulfing and len(self.cdl_engulfing) > 0 and self.cdl_engulfing[-1] == -100:
                exit_signal = True
                exit_reason = "Bearish Engulfing"
                print(f"[DEBUG] Bearish Engulfing exit signal: {self.cdl_engulfing[-1]}")
            elif self.enable_eveningstar and len(self.cdl_eveningstar) > 0 and self.cdl_eveningstar[-1] == 100:
                exit_signal = True
                exit_reason = "Evening Star"
                print(f"[DEBUG] Evening Star exit signal: {self.cdl_eveningstar[-1]}")
            elif self.enable_morningstar and len(self.cdl_morningstar) > 0 and self.cdl_morningstar[-1] == -100:
                exit_signal = True
                exit_reason = "Bearish Morning Star"
                print(f"[DEBUG] Bearish Morning Star exit signal: {self.cdl_morningstar[-1]}")
            
            # Check trailing stop conditions
            # Use stored entry_price instead of self.position.entry_price
            unrealized_gain = (current_price / self.entry_price) - 1
            
            print(f"[DEBUG] Unrealized gain: {unrealized_gain*100:.2f}%, "
                  f"Trailing activation: {self.trailing_activation*100:.2f}%")
            
            if unrealized_gain >= self.trailing_activation:
                # Calculate trailing stop price
                trailing_stop_price = self.highest_price * (1 - self.trailing_offset)
                
                print(f"[DEBUG] Trailing stop check: current=${current_price:.2f}, "
                      f"highest=${self.highest_price:.2f}, trailing_stop=${trailing_stop_price:.2f}")
                
                if current_price <= trailing_stop_price:
                    exit_signal = True
                    exit_reason = f"Trailing Stop at ${trailing_stop_price:.2f}"
                    print(f"[DEBUG] Trailing stop triggered: ${current_price:.2f} <= ${trailing_stop_price:.2f}")
            
            # Check initial stop loss
            stop_price = self.entry_price * (1 - self.initial_stop_loss)
            
            print(f"[DEBUG] Stop loss check: current=${current_price:.2f}, "
                  f"entry=${self.entry_price:.2f}, stop=${stop_price:.2f}")
            
            if current_price <= stop_price:
                exit_signal = True
                exit_reason = f"Initial Stop Loss at ${stop_price:.2f}"
                print(f"[DEBUG] Stop loss triggered: ${current_price:.2f} <= ${stop_price:.2f}")
            
            # Execute exit if any exit condition met
            if exit_signal:
                print(f"[EXIT SIGNAL] {exit_reason} at bar {current_bar}, price: ${current_price:.2f}")
                
                # CRITICAL: Actually close the position
                self.position.close()
                
                print(f"[POSITION CLOSED #{self.trade_count}] {exit_reason} at bar {current_bar}, "
                      f"exit price: ${current_price:.2f}")

# Run backtest
print("\n" + "="*50)
print("STARTING BACKTEST")
print("="*50 + "\n")

bt = Backtest(price_data, PatternSync, cash=1000000, commission=.002)
stats = bt.run()
print(stats)

# Print additional strategy info
print("\n" + "="*50)
print("STRATEGY SUMMARY")
print("="*50)
print(f"Total trades: {stats['# Trades']}")
print(f"Win rate: {stats['Win Rate [%]']:.2f}%")
print(f"Return: {stats['Return [%]']:.2f}%")
print(f"Sharpe Ratio: {stats['Sharpe Ratio']:.2f}")
print(f"Max Drawdown: {stats['Max. Drawdown [%]']:.2f}%")

# Plot if available
try:
    bt.plot()
except Exception as e:
    print(f"[NOTE] Could not plot: {e}")