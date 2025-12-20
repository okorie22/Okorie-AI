import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

# Load data
print("[INFO] Loading data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()

# Drop unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Ensure proper column mapping
required_columns = {'open', 'high', 'low', 'close', 'volume'}
available_columns = set(price_data.columns)

if not required_columns.issubset(available_columns):
    print(f"[ERROR] Missing required columns. Available: {available_columns}")
    raise ValueError("Missing required OHLCV columns")

# Set datetime index
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')

# Capitalize column names for backtesting.py
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

print(f"[INFO] Data loaded: {len(price_data)} rows")
print(f"[INFO] Data columns: {list(price_data.columns)}")
print(f"[INFO] Data range: {price_data.index[0]} to {price_data.index[-1]}")

class AdaptiveMomentumDivergence(Strategy):
    # Strategy parameters
    risk_per_trade = 0.02  # 2% risk per trade
    stop_loss_pct = 0.318  # 31.8% stop loss
    min_holding_candles = 5  # Minimum holding period
    
    def init(self):
        # Calculate EMAs
        self.ema12 = self.I(talib.EMA, self.data.Close, timeperiod=12)
        self.ema26 = self.I(talib.EMA, self.data.Close, timeperiod=26)
        
        # Calculate Universal MACD
        self.universal_macd = (self.ema12 / self.ema26) - 1
        
        # Calculate rolling statistics for adaptive entry range
        self.macd_mean = self.I(talib.SMA, self.universal_macd, timeperiod=20)
        self.macd_std = self.I(talib.STDDEV, self.universal_macd, timeperiod=20)
        
        # Calculate adaptive entry range
        self.range_min = self.macd_mean - 1.5 * self.macd_std
        self.range_max = self.macd_mean - 0.5 * self.macd_std
        
        # Track position metrics
        self.candles_since_entry = 0
        self.entry_price = 0
        self.entry_macd = 0
        
    def next(self):
        # Update candles counter if in position
        if self.position:
            self.candles_since_entry += 1
            
            # Check stop loss
            current_price = self.data.Close[-1]
            stop_price = self.entry_price * (1 - self.stop_loss_pct)
            
            if current_price <= stop_price:
                print(f"[STOP LOSS] Price: {current_price:.2f}, Stop: {stop_price:.2f}, Loss: {(current_price/self.entry_price-1)*100:.1f}%")
                self.position.close()
                self.candles_since_entry = 0
                return
            
            # Calculate scaled ROI target
            roi_target = self.calculate_scaled_roi_target()
            target_price = self.entry_price * (1 + roi_target)
            
            if current_price >= target_price:
                print(f"[ROI TARGET] Price: {current_price:.2f}, Target: {target_price:.2f}, Profit: {(current_price/self.entry_price-1)*100:.1f}%")
                self.position.close()
                self.candles_since_entry = 0
                return
            
            # Check MACD exit signal (only after minimum holding period)
            if self.candles_since_entry >= self.min_holding_candles:
                current_macd = self.universal_macd[-1]
                if -0.02323 <= current_macd <= -0.00707:
                    print(f"[MACD EXIT] MACD: {current_macd:.6f}, Candles held: {self.candles_since_entry}")
                    self.position.close()
                    self.candles_since_entry = 0
                    return
        
        # Entry logic (only if not in position)
        if not self.position:
            current_macd = self.universal_macd[-1]
            range_min_val = self.range_min[-1]
            range_max_val = self.range_max[-1]
            
            # Check if MACD is within adaptive entry range
            if range_min_val <= current_macd <= range_max_val:
                # Calculate position size
                entry_price = self.data.Close[-1]
                stop_distance = entry_price * self.stop_loss_pct
                risk_amount = self.equity * self.risk_per_trade
                position_size = risk_amount / stop_distance
                
                # Use fractional position size
                print(f"[ENTRY] MACD: {current_macd:.6f}, Range: [{range_min_val:.6f}, {range_max_val:.6f}]")
                print(f"[ENTRY] Price: {entry_price:.2f}, Size: {position_size:.4f}, Equity: {self.equity:.2f}")
                
                self.buy(size=position_size)
                self.entry_price = entry_price
                self.entry_macd = current_macd
                self.candles_since_entry = 0
    
    def calculate_scaled_roi_target(self):
        """Calculate scaled ROI target based on candles held"""
        candles = self.candles_since_entry
        
        # ROI scaling logic
        if candles <= 0:
            return 0.213  # 21.3% at entry
        
        if candles <= 27:
            # Linear scaling from 21.3% to 9.9% over 27 candles
            return 0.213 - (candles / 27) * (0.213 - 0.099)
        
        if candles <= 60:
            # Linear scaling from 9.9% to 3% over 33 candles
            return 0.099 - ((candles - 27) / 33) * (0.099 - 0.03)
        
        if candles <= 164:
            # Linear scaling from 3% to 0% over 104 candles
            return 0.03 - ((candles - 60) / 104) * 0.03
        
        return 0.0

# Run backtest
print("[INFO] Starting backtest...")
bt = Backtest(price_data, AdaptiveMomentumDivergence, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)