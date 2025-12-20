import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import talib

# Load data
print("[INFO] Loading data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')

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

# Set datetime index
if 'timestamp' in price_data.columns:
    price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
    price_data = price_data.set_index('timestamp')
elif 'date' in price_data.columns:
    price_data['date'] = pd.to_datetime(price_data['date'])
    price_data = price_data.set_index('date')

# Capitalize column names for backtesting.py
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High', 
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

print(f"[INFO] Data shape: {price_data.shape}")
print(f"[INFO] Data columns: {list(price_data.columns)}")
print(f"[INFO] Data index: {price_data.index[:5]}")

class ExponentialMomentum(Strategy):
    # Strategy parameters
    entry_power = 3.849
    exit_power = 3.798
    base = 1.01
    stop_loss_pct = 0.288  # -28.8%
    
    # ROI targets based on holding period
    roi_targets = {
        0: 0.213,   # Entry: 21.3%
        39: 0.048,  # After 39 candles: 4.8%
        56: 0.029,  # After 56 candles: 2.9%
        159: 0.000  # After 159 candles: 0% (exit)
    }
    
    def init(self):
        # Calculate thresholds
        self.entry_threshold = self.base ** self.entry_power
        self.exit_threshold = self.base ** self.exit_power
        
        print(f"[INFO] Entry threshold (1.01^{self.entry_power}): {self.entry_threshold:.4f}")
        print(f"[INFO] Exit threshold (1.01^{self.exit_power}): {self.exit_threshold:.4f}")
        
        # Store close prices for calculations
        self.close_prices = self.I(lambda x: x, self.data.Close)
        
    def next(self):
        # Skip if we don't have enough data
        if len(self.data.Close) < 5:
            return
        
        # Get current index
        current_idx = len(self.data.Close) - 1
        
        # Get required price values
        current_close = self.data.Close[-1]
        prev_close = self.data.Close[-2] if current_idx >= 1 else None
        close_2_ago = self.data.Close[-3] if current_idx >= 2 else None
        close_3_ago = self.data.Close[-4] if current_idx >= 3 else None
        close_4_ago = self.data.Close[-5] if current_idx >= 4 else None
        
        # Check if we have all required prices
        if None in [prev_close, close_2_ago, close_3_ago, close_4_ago]:
            return
        
        # Calculate ratios
        ratio1 = current_close / close_2_ago
        ratio2 = prev_close / close_3_ago
        ratio3 = close_2_ago / close_4_ago
        
        # Debug prints
        if current_idx % 100 == 0:  # Print every 100 candles to avoid spam
            print(f"\n[DEBUG] Candle {current_idx}")
            print(f"[DEBUG] Prices: current={current_close:.2f}, prev={prev_close:.2f}, -2={close_2_ago:.2f}, -3={close_3_ago:.2f}, -4={close_4_ago:.2f}")
            print(f"[DEBUG] Ratios: ratio1={ratio1:.4f}, ratio2={ratio2:.4f}, ratio3={ratio3:.4f}")
            print(f"[DEBUG] Entry threshold: {self.entry_threshold:.4f}, Exit threshold: {self.exit_threshold:.4f}")
            print(f"[DEBUG] Entry conditions: ratio1>{self.entry_threshold}={ratio1>self.entry_threshold}, "
                  f"ratio2>{self.entry_threshold}={ratio2>self.entry_threshold}, "
                  f"ratio3>{self.entry_threshold}={ratio3>self.entry_threshold}")
        
        # Check if we're in a position
        if self.position:
            # Calculate holding period
            holding_period = current_idx - self.position.entry_bar
            
            # Determine current ROI target based on holding period
            current_target = 0.000  # Default to 0%
            for period, target in sorted(self.roi_targets.items()):
                if holding_period >= period:
                    current_target = target
            
            # Check exit conditions
            exit_signal = False
            exit_reason = ""
            
            # Condition 1: Any ratio falls below exit threshold
            if ratio1 < self.exit_threshold:
                exit_signal = True
                exit_reason = "Ratio1 below exit threshold"
            elif ratio2 < self.exit_threshold:
                exit_signal = True
                exit_reason = "Ratio2 below exit threshold"
            elif ratio3 < self.exit_threshold:
                exit_signal = True
                exit_reason = "Ratio3 below exit threshold"
            
            # Condition 2: Stop loss triggered
            elif self.position.pl_pct <= -self.stop_loss_pct:
                exit_signal = True
                exit_reason = f"Stop loss triggered at {self.position.pl_pct:.2%}"
            
            # Condition 3: ROI target reached
            elif self.position.pl_pct >= current_target and current_target > 0:
                exit_signal = True
                exit_reason = f"ROI target {current_target:.1%} reached"
            
            # Condition 4: Maximum holding period reached
            elif holding_period >= 159:
                exit_signal = True
                exit_reason = "Maximum holding period (159 candles) reached"
            
            if exit_signal:
                print(f"[EXIT] Closing position at bar {current_idx}: {exit_reason}")
                print(f"[EXIT] Holding period: {holding_period} candles, P/L: {self.position.pl_pct:.2%}")
                self.position.close()
        
        # Check entry conditions (only if not in position)
        elif not self.position:
            # All three entry conditions must be true
            entry_condition1 = ratio1 > self.entry_threshold
            entry_condition2 = ratio2 > self.entry_threshold
            entry_condition3 = ratio3 > self.entry_threshold
            
            if entry_condition1 and entry_condition2 and entry_condition3:
                print(f"[BUY] Entry signal detected at bar {current_idx}")
                print(f"[BUY] Ratios: {ratio1:.4f}, {ratio2:.4f}, {ratio3:.4f} > {self.entry_threshold:.4f}")
                
                # Calculate position size based on risk management
                # Using 10% of equity for position sizing (adjustable)
                risk_percentage = 0.10
                risk_amount = self.equity * risk_percentage
                
                # Calculate stop distance
                entry_price = current_close
                stop_price = entry_price * (1 - self.stop_loss_pct)
                stop_distance = abs(entry_price - stop_price)
                
                # Calculate position size
                if stop_distance > 0:
                    position_size = risk_amount / stop_distance
                    # Round to nearest integer for whole units
                    position_size = int(round(position_size))
                    
                    # Ensure minimum position size
                    if position_size < 1:
                        position_size = 1
                    
                    print(f"[BUY] Entry price: {entry_price:.2f}, Stop: {stop_price:.2f}")
                    print(f"[BUY] Position size: {position_size} units")
                    
                    # Enter long position
                    self.buy(size=position_size)

# Run backtest
print("\n[INFO] Starting backtest...")
bt = Backtest(price_data, ExponentialMomentum, cash=1000000, commission=.002)

# Run with default parameters
stats = bt.run()
print("\n" + "="*50)
print("BACKTEST RESULTS")
print("="*50)
print(stats)
print("\n" + "="*50)
print("STRATEGY DETAILS")
print("="*50)
print(stats._strategy)