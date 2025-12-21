import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import talib

class BearishMomentum(Strategy):
    def init(self):
        # Load OI data directly
        try:
            oi_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/oi/oi_20251218.parquet')
            print(f"[DEBUG] OI data shape: {oi_data.shape}")
            print(f"[DEBUG] OI data columns: {list(oi_data.columns)}")
            
            # Filter for BTC symbol
            oi_data = oi_data[oi_data['symbol'] == 'BTC'].copy()
            print(f"[DEBUG] Filtered OI data shape: {oi_data.shape}")
            
            if 'open_interest' in oi_data.columns:
                print(f"[DEBUG] OI column exists with {len(oi_data)} rows")
            else:
                print("[ERROR] No 'open_interest' column found in OI data")
                raise ValueError("No 'open_interest' column found in OI data")
            
            # Clean and prepare OI data
            oi_data.columns = oi_data.columns.str.strip().str.lower()
            oi_data = oi_data.drop(columns=[col for col in oi_data.columns if 'unnamed' in col.lower()])
            oi_data['timestamp'] = pd.to_datetime(oi_data['timestamp'])
            oi_data = oi_data.set_index('timestamp')
            
            # Resample to match price data frequency (1H)
            oi_data = oi_data.resample('1H').last().ffill()
            
            # Align OI data with price data
            price_dates = pd.Series(self.data.index)
            aligned_oi = oi_data.reindex(price_dates, method='ffill')
            
            # Add OI to strategy data using self.I()
            self.oi = self.I(lambda: aligned_oi['open_interest'].values, name='OI')
        except Exception as e:
            print(f"[WARNING] Could not load OI data: {e}")
            self.oi = self.I(lambda: np.zeros(len(self.data)), name='OI')
        
        # Calculate indicators using self.I() wrapper
        self.adx = self.I(talib.ADX, self.data.High, self.data.Low, self.data.Close, timeperiod=14, name='ADX')
        self.plus_di = self.I(talib.PLUS_DI, self.data.High, self.data.Low, self.data.Close, timeperiod=25, name='+DI')
        self.minus_di = self.I(talib.MINUS_DI, self.data.High, self.data.Low, self.data.Close, timeperiod=25, name='-DI')
        self.momentum = self.I(talib.MOM, self.data.Close, timeperiod=14, name='Momentum')
        
        # Initialize trade tracking variables
        self.trade_count = 0
        self.entry_bar = 0
        self.position_size = 0.015  # Default 1.5% of equity
        self.stop_loss_pct = 0.08  # 8% stop loss
        self.take_profit_pct = 0.10  # 10% take profit
        self.trailing_stop_activated = False
        self.trailing_stop_price = None
        self.trailing_lock_pct = 0.80  # Lock in 80% of profits beyond 2%
        
        print("[STRATEGY] BearishMomentum initialized with 1H timeframe")
    
    def next(self):
        # Skip if we don't have enough data for indicators
        if len(self.data) < 30:
            return
        
        current_bar = len(self.data)
        
        # Print summary every 200 bars
        if current_bar % 200 == 0:
            print(f"[SUMMARY] Bar {current_bar}, Equity: ${self.equity:.2f}, Trades: {self.trade_count}")
        
        # Check if we have an open position
        if self.position:
            # Update trailing stop if activated
            if self.trailing_stop_activated and self.trailing_stop_price:
                # For short position, trail stop downward as price decreases
                current_price = self.data.Close[-1]
                entry_price = self.position.entry_price
                
                # Calculate profit from entry
                profit_pct = (entry_price - current_price) / entry_price
                
                if profit_pct > 0.02:  # +2% profit
                    # Calculate new trailing stop price
                    profit_beyond_2pct = profit_pct - 0.02
                    lock_amount = profit_beyond_2pct * self.trailing_lock_pct
                    new_stop_price = entry_price * (1 - (0.02 + lock_amount))
                    
                    # Only move stop downward (for short position)
                    if new_stop_price < self.trailing_stop_price:
                        self.trailing_stop_price = new_stop_price
                        if current_bar % 100 == 0:
                            print(f"[TRAILING] Updated stop to {self.trailing_stop_price:.2f}")
            
            # Check minimum holding period (6 bars)
            bars_held = current_bar - self.entry_bar
            if bars_held < 6:
                return
            
            # Check maximum holding period (96 bars)
            if bars_held >= 96:
                if self.trade_count % 10 == 0:
                    print(f"[EXIT] Time-based exit after {bars_held} bars")
                self.position.close()
                self.trailing_stop_activated = False
                self.trailing_stop_price = None
                return
            
            current_price = self.data.Close[-1]
            entry_price = self.position.entry_price
            
            # Check stop loss (price increased 8% from entry)
            stop_loss_price = entry_price * (1 + self.stop_loss_pct)
            if current_price >= stop_loss_price:
                if self.trade_count % 10 == 0:
                    print(f"[EXIT] Stop loss hit at {current_price:.2f}")
                self.position.close()
                self.trailing_stop_activated = False
                self.trailing_stop_price = None
                return
            
            # Check take profit (price decreased 10% from entry)
            take_profit_price = entry_price * (1 - self.take_profit_pct)
            if current_price <= take_profit_price:
                if self.trade_count % 10 == 0:
                    print(f"[EXIT] Take profit hit at {current_price:.2f}")
                self.position.close()
                self.trailing_stop_activated = False
                self.trailing_stop_price = None
                return
            
            # Check trailing stop
            if self.trailing_stop_activated and self.trailing_stop_price:
                if current_price >= self.trailing_stop_price:
                    if self.trade_count % 10 == 0:
                        print(f"[EXIT] Trailing stop hit at {current_price:.2f}")
                    self.position.close()
                    self.trailing_stop_activated = False
                    self.trailing_stop_price = None
                    return
            
            # Check momentum reversal exit condition
            if self.adx[-1] > 25 and self.momentum[-1] > 0:
                if self.trade_count % 10 == 0:
                    print(f"[EXIT] Momentum reversal detected")
                self.position.close()
                self.trailing_stop_activated = False
                self.trailing_stop_price = None
                return
            
            # Check trend reversal exit condition
            if self.plus_di[-1] > 25 and self.plus_di[-1] > self.minus_di[-1]:
                if self.trade_count % 10 == 0:
                    print(f"[EXIT] Trend reversal detected (+DI > -DI)")
                self.position.close()
                self.trailing_stop_activated = False
                self.trailing_stop_price = None
                return
            
            # Activate trailing stop if profit reaches +2%
            if not self.trailing_stop_activated:
                profit_pct = (entry_price - current_price) / entry_price
                if profit_pct > 0.02:
                    self.trailing_stop_activated = True
                    # Initial trailing stop at breakeven + small profit
                    self.trailing_stop_price = entry_price * 0.995  # 0.5% below entry
                    if self.trade_count % 10 == 0:
                        print(f"[TRAILING] Activated at {profit_pct*100:.2f}% profit")
        
        # No position - check for entry conditions
        else:
            # All four entry conditions must be met
            entry_conditions = (
                self.adx[-1] > 25 and  # Strong trend
                self.minus_di[-1] > self.plus_di[-1] and  # Bearish bias
                self.minus_di[-1] > 25 and  # Strong bearish force
                self.momentum[-1] < 0  # Negative momentum
            )
            
            if entry_conditions:
                # Dynamic position sizing: 1-2% of equity with random element
                base_size = 0.015  # 1.5% average
                random_factor = np.random.uniform(0.9, 1.1)  # ±10% variation
                target_size = base_size * random_factor
                
                # Cap at maximum 3% of equity
                position_size = min(target_size, 0.03)
                
                # Ensure minimum 1% position
                position_size = max(position_size, 0.01)
                
                # Validate position size doesn't exceed 10% hard cap
                position_size = min(position_size, 0.10)
                
                # Execute short position
                self.trade_count += 1
                self.entry_bar = current_bar
                self.trailing_stop_activated = False
                self.trailing_stop_price = None
                
                if self.trade_count % 10 == 0:
                    print(f"[SHORT ENTRY] Bar {current_bar}, Size: {position_size*100:.2f}% of equity")
                    print(f"  ADX: {self.adx[-1]:.2f}, -DI: {self.minus_di[-1]:.2f}, +DI: {self.plus_di[-1]:.2f}, Momentum: {self.momentum[-1]:.2f}")
                
                self.sell(size=position_size)

# Load price data
print("[INFO] Loading price data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-1h.csv')

# Clean column names
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
    price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
    price_data = price_data.set_index('timestamp')
elif 'date' in price_data.columns:
    price_data['date'] = pd.to_datetime(price_data['date'])
    price_data = price_data.set_index('date')

# Ensure required columns exist
required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
for col in required_cols:
    if col not in price_data.columns:
        print(f"[ERROR] Missing required column: {col}")
        raise ValueError(f"Missing required column: {col}")

print(f"[INFO] Price data loaded: {len(price_data)} rows, {price_data.index[0]} to {price_data.index[-1]}")

# Run backtest
bt = Backtest(price_data, BearishMomentum, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)