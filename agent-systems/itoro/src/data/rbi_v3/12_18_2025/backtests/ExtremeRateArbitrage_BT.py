import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import talib

# Load data directly
print("[INFO] Loading data...")

# Load OHLCV data
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
price_data.columns = price_data.columns.str.strip().str.lower()
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')

# Ensure proper column names for backtesting.py
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High', 
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

# Load funding data
funding_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/funding/funding_20251218.parquet')
funding_data.columns = funding_data.columns.str.strip().str.lower()
funding_data = funding_data.drop(columns=[col for col in funding_data.columns if 'unnamed' in col.lower()])
funding_data['timestamp'] = pd.to_datetime(funding_data['timestamp'])
funding_data = funding_data.set_index('timestamp')

# Filter for BTC symbol if multiple symbols exist
if 'symbol' in funding_data.columns:
    funding_data = funding_data[funding_data['symbol'] == 'BTC']
    print(f"[INFO] Filtered funding data for BTC, {len(funding_data)} rows")

print(f"[DEBUG] Funding data shape: {funding_data.shape}")
print(f"[DEBUG] Funding data columns: {list(funding_data.columns)}")

# Resample funding data to match price data frequency (15m)
funding_data_resampled = funding_data['funding_rate'].resample('15min').ffill()

# Merge funding data with price data
price_data['FundingRate'] = funding_data_resampled
price_data['FundingRate'] = price_data['FundingRate'].ffill()

print(f"[INFO] Final data shape: {price_data.shape}")
print(f"[INFO] Funding rate data available: {price_data['FundingRate'].notna().sum()} rows")

class ExtremeRateArbitrage(Strategy):
    # Strategy parameters
    negative_threshold = -0.0005  # -0.05%
    positive_threshold = 0.0005   # +0.05%
    long_exit_threshold = -0.0002  # -0.02%
    short_exit_threshold = 0.0002  # +0.02%
    scaling_factor = 100
    base_position_size = 0.01  # 1% of capital
    max_position_size = 0.05   # 5% of capital
    stop_loss_pct = 0.05       # 5% stop loss
    max_holding_period = 24    # 24 hours in 15-min bars (96 bars)
    
    def init(self):
        # Store funding rate as indicator
        self.funding_rate = self.I(lambda x: x, self.data.FundingRate, name='FundingRate')
        
        # Calculate extremity score
        def calc_extremity(rate):
            if rate < self.negative_threshold:
                return abs(rate - self.negative_threshold)
            elif rate > self.positive_threshold:
                return abs(rate - self.positive_threshold)
            else:
                return 0
        
        self.extremity = self.I(calc_extremity, self.funding_rate, name='Extremity')
        
        # Track entry time for time-based exit
        self.entry_time = None
        self.entry_price = None
        
    def next(self):
        current_rate = self.funding_rate[-1]
        current_price = self.data.Close[-1]
        
        # Calculate position size based on extremity
        if current_rate < self.negative_threshold:
            extremity_score = abs(current_rate - self.negative_threshold)
            position_multiplier = 1 + (extremity_score * self.scaling_factor)
            position_size = min(self.base_position_size * position_multiplier, self.max_position_size)
        elif current_rate > self.positive_threshold:
            extremity_score = abs(current_rate - self.positive_threshold)
            position_multiplier = 1 + (extremity_score * self.scaling_factor)
            position_size = min(self.base_position_size * position_multiplier, self.max_position_size)
        else:
            position_size = 0
        
        # Convert position size to integer units
        if position_size > 0:
            risk_amount = self.equity * position_size
            # Use fixed unit size for simplicity (adjust based on price)
            units = int(round(risk_amount / current_price))
            if units < 1:
                units = 1
        else:
            units = 0
        
        # Check for emergency stop loss
        if self.position:
            if self.position.is_long:
                stop_price = self.entry_price * (1 - self.stop_loss_pct)
                if current_price <= stop_price:
                    print(f"[STOP LOSS] Closing long position at {current_price}")
                    self.position.close()
                    self.entry_time = None
                    self.entry_price = None
                    return
                
                # Check funding rate reversal (moves further negative)
                if current_rate < self.position_entry_rate:
                    print(f"[REVERSAL] Funding rate moved further negative, closing long")
                    self.position.close()
                    self.entry_time = None
                    self.entry_price = None
                    return
                    
            elif self.position.is_short:
                stop_price = self.entry_price * (1 + self.stop_loss_pct)
                if current_price >= stop_price:
                    print(f"[STOP LOSS] Closing short position at {current_price}")
                    self.position.close()
                    self.entry_time = None
                    self.entry_price = None
                    return
                
                # Check funding rate reversal (moves further positive)
                if current_rate > self.position_entry_rate:
                    print(f"[REVERSAL] Funding rate moved further positive, closing short")
                    self.position.close()
                    self.entry_time = None
                    self.entry_price = None
                    return
        
        # Entry logic
        if not self.position:
            # Check for consecutive readings (simplified - check current and previous)
            if len(self.funding_rate) >= 2:
                prev_rate = self.funding_rate[-2]
                
                # Long entry: funding rate < -0.05%
                if current_rate < self.negative_threshold and prev_rate < self.negative_threshold:
                    if units > 0:
                        print(f"[LONG ENTRY] Rate: {current_rate:.6f}, Size: {units} units")
                        self.buy(size=units)
                        self.entry_time = len(self.data) - 1
                        self.entry_price = current_price
                        self.position_entry_rate = current_rate
                
                # Short entry: funding rate > +0.05%
                elif current_rate > self.positive_threshold and prev_rate > self.positive_threshold:
                    if units > 0:
                        print(f"[SHORT ENTRY] Rate: {current_rate:.6f}, Size: {units} units")
                        self.sell(size=units)
                        self.entry_time = len(self.data) - 1
                        self.entry_price = current_price
                        self.position_entry_rate = current_rate
        
        # Exit logic for existing positions
        elif self.position:
            # Time-based exit
            if self.entry_time is not None:
                bars_held = len(self.data) - 1 - self.entry_time
                max_bars = self.max_holding_period * 4  # 15-min bars in 24 hours
                
                if bars_held >= max_bars:
                    print(f"[TIME EXIT] Held for {bars_held} bars, closing position")
                    self.position.close()
                    self.entry_time = None
                    self.entry_price = None
                    return
            
            # Rate normalization exit
            if self.position.is_long and current_rate > self.long_exit_threshold:
                print(f"[LONG EXIT] Rate normalized to {current_rate:.6f}")
                self.position.close()
                self.entry_time = None
                self.entry_price = None
                
            elif self.position.is_short and current_rate < self.short_exit_threshold:
                print(f"[SHORT EXIT] Rate normalized to {current_rate:.6f}")
                self.position.close()
                self.entry_time = None
                self.entry_price = None

# Run backtest
print("[INFO] Starting backtest...")
bt = Backtest(price_data, ExtremeRateArbitrage, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)