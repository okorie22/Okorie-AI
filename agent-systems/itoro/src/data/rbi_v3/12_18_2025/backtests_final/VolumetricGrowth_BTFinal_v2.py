import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

class VolumetricGrowth(Strategy):
    # Strategy parameters
    volume_ma_period = 20
    count_ma_period = 20
    momentum_period = 14
    volume_threshold_multiplier = 1.3
    count_threshold_multiplier = 1.2
    min_activity_percent = 0.5
    confirmation_periods = 2
    
    def init(self):
        # Load onchain data
        onchain_data = pd.read_json('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/token_onchain_data.json')
        
        # Clean column names
        onchain_data.columns = onchain_data.columns.str.strip().str.lower()
        
        # Drop unnamed columns
        onchain_data = onchain_data.drop(columns=[col for col in onchain_data.columns if 'unnamed' in col.lower()])
        
        # Extract transaction volume and count from onchain data
        print(f"[DEBUG] Onchain data shape: {onchain_data.shape}")
        print(f"[DEBUG] Onchain data columns: {list(onchain_data.columns)}")
        
        # Parse the JSON structure to extract volume and count
        transaction_volume = []
        transaction_count = []
        
        for idx, row in onchain_data.iterrows():
            try:
                # Assuming row contains 'tokens' column with nested JSON
                if 'tokens' in row:
                    tokens_data = row['tokens']
                    # Sum volume and count across all tokens
                    total_volume = 0
                    total_count = 0
                    
                    if isinstance(tokens_data, dict):
                        for token, metrics in tokens_data.items():
                            if isinstance(metrics, dict):
                                # Adjust these keys based on actual data structure
                                if 'transaction_volume' in metrics:
                                    total_volume += float(metrics['transaction_volume'])
                                if 'transaction_count' in metrics:
                                    total_count += float(metrics['transaction_count'])
                    
                    transaction_volume.append(total_volume)
                    transaction_count.append(total_count)
                else:
                    transaction_volume.append(0)
                    transaction_count.append(0)
            except:
                transaction_volume.append(0)
                transaction_count.append(0)
        
        # Create Series for indicators
        self.transaction_volume = pd.Series(transaction_volume, index=onchain_data.index)
        self.transaction_count = pd.Series(transaction_count, index=onchain_data.index)
        
        # CRITICAL FIX: Align onchain data with price data length
        # Get the minimum length between price data and onchain data
        price_data_len = len(self.data.Close)
        onchain_data_len = len(self.transaction_volume)
        
        print(f"[DEBUG] Price data length: {price_data_len}")
        print(f"[DEBUG] Onchain data length: {onchain_data_len}")
        
        # If onchain data is shorter, pad with zeros
        if onchain_data_len < price_data_len:
            print(f"[WARNING] Onchain data shorter than price data. Padding with zeros.")
            pad_length = price_data_len - onchain_data_len
            transaction_volume_padded = np.concatenate([np.zeros(pad_length), self.transaction_volume.values])
            transaction_count_padded = np.concatenate([np.zeros(pad_length), self.transaction_count.values])
            
            self.transaction_volume = pd.Series(transaction_volume_padded)
            self.transaction_count = pd.Series(transaction_count_padded)
        
        # If onchain data is longer, truncate to match price data
        elif onchain_data_len > price_data_len:
            print(f"[WARNING] Onchain data longer than price data. Truncating.")
            self.transaction_volume = self.transaction_volume.iloc[-price_data_len:]
            self.transaction_count = self.transaction_count.iloc[-price_data_len:]
        
        # Convert to numpy arrays for talib compatibility
        volume_array = self.transaction_volume.values.astype(float)
        count_array = self.transaction_count.values.astype(float)
        
        # Calculate indicators using self.I() wrapper
        # Volume indicators
        self.volume_ma = self.I(talib.SMA, volume_array, timeperiod=self.volume_ma_period)
        self.volume_momentum = self.I(talib.ROC, volume_array, timeperiod=self.momentum_period)
        
        # Count indicators
        self.count_ma = self.I(talib.SMA, count_array, timeperiod=self.count_ma_period)
        self.count_momentum = self.I(talib.ROC, count_array, timeperiod=self.momentum_period)
        
        # Calculate thresholds
        self.volume_30d_avg = self.I(talib.SMA, volume_array, timeperiod=30)
        self.count_30d_avg = self.I(talib.SMA, count_array, timeperiod=30)
        self.volume_90d_avg = self.I(talib.SMA, volume_array, timeperiod=90)
        self.count_90d_avg = self.I(talib.SMA, count_array, timeperiod=90)
        
        # Volume threshold
        self.volume_threshold = self.I(lambda x: x * self.volume_threshold_multiplier, self.volume_30d_avg)
        
        # Count threshold
        self.count_threshold = self.I(lambda x: x * self.count_threshold_multiplier, self.count_30d_avg)
        
        # Minimum activity levels
        self.min_volume = self.I(lambda x: x * self.min_activity_percent, self.volume_90d_avg)
        self.min_count = self.I(lambda x: x * self.min_activity_percent, self.count_90d_avg)
        
        # Track recent peaks for exit conditions
        self.volume_peak = self.I(talib.MAX, volume_array, timeperiod=20)
        self.count_peak = self.I(talib.MAX, count_array, timeperiod=20)
        
        # Debug prints
        print("[INFO] Strategy initialized with onchain data")
        print(f"[INFO] Transaction volume range: {np.nanmin(volume_array):.2f} to {np.nanmax(volume_array):.2f}")
        print(f"[INFO] Transaction count range: {np.nanmin(count_array):.2f} to {np.nanmax(count_array):.2f}")
        print(f"[INFO] Indicator lengths - volume_ma: {len(self.volume_ma)}, Close: {len(self.data.Close)}")
        
        # Store arrays for access in next()
        self.volume_array = volume_array
        self.count_array = count_array
    
    def next(self):
        # Skip if we don't have enough data
        if len(self.data.Close) < 30:
            return
        
        current_idx = len(self.data.Close) - 1
        
        # Skip if indicators not ready
        if (current_idx >= len(self.volume_ma) or 
            current_idx >= len(self.count_ma) or
            current_idx >= len(self.volume_momentum) or
            current_idx >= len(self.count_momentum)):
            return
        
        # Get current values - FIX: Use array indexing, not .iloc
        current_volume = self.volume_array[current_idx]
        current_count = self.count_array[current_idx]
        current_volume_ma = self.volume_ma[current_idx]
        current_count_ma = self.count_ma[current_idx]
        current_volume_mom = self.volume_momentum[current_idx]
        current_count_mom = self.count_momentum[current_idx]
        current_volume_threshold = self.volume_threshold[current_idx]
        current_count_threshold = self.count_threshold[current_idx]
        current_min_volume = self.min_volume[current_idx]
        current_min_count = self.min_count[current_idx]
        current_volume_peak = self.volume_peak[current_idx]
        current_count_peak = self.count_peak[current_idx]
        
        # Check if we have a position
        if self.position:
            # Check exit conditions
            exit_signal = False
            exit_reason = ""
            
            # Condition 1: Volume trend shrinking
            if (current_volume < current_volume_ma and 
                current_volume_mom < 0 and
                current_volume < 0.7 * current_volume_peak):
                exit_signal = True
                exit_reason = "Volume trend shrinking"
            
            # Condition 2: Count trend shrinking
            elif (current_count < current_count_ma and 
                  current_count_mom < 0 and
                  current_count < 0.7 * current_count_peak):
                exit_signal = True
                exit_reason = "Count trend shrinking"
            
            # Condition 3: Divergence warning
            elif ((current_volume > current_volume_ma and current_volume_mom > 0 and 
                   current_count < current_count_ma and current_count_mom < 0) or
                  (current_count > current_count_ma and current_count_mom > 0 and 
                   current_volume < current_volume_ma and current_volume_mom < 0)):
                exit_signal = True
                exit_reason = "Divergence warning"
            
            if exit_signal:
                print(f"[SELL] Closing position: {exit_reason}")
                self.position.close()
                return
        
        else:
            # Check entry conditions
            # Verify minimum activity levels
            if (current_volume < current_min_volume or 
                current_count < current_min_count):
                return
            
            # Check volume conditions
            volume_conditions = (
                current_volume > current_volume_ma and
                current_volume_mom > 0 and
                current_volume > current_volume_threshold
            )
            
            # Check count conditions
            count_conditions = (
                current_count > current_count_ma and
                current_count_mom > 0 and
                current_count > current_count_threshold
            )
            
            # Check confirmation periods
            if current_idx >= self.confirmation_periods:
                volume_confirmed = True
                count_confirmed = True
                
                for i in range(self.confirmation_periods):
                    idx = current_idx - i - 1  # FIX: -1 to get previous bars
                    if idx < 0 or idx >= len(self.volume_ma):
                        volume_confirmed = False
                        count_confirmed = False
                        break
                    
                    # FIX: Use array indexing
                    vol_val = self.volume_array[idx]
                    cnt_val = self.count_array[idx]
                    
                    if not (vol_val > self.volume_ma[idx] and 
                            self.volume_momentum[idx] > 0):
                        volume_confirmed = False
                    if not (cnt_val > self.count_ma[idx] and 
                            self.count_momentum[idx] > 0):
                        count_confirmed = False
                
                confirmation = volume_confirmed and count_confirmed
            else:
                confirmation = False
            
            # All entry conditions met
            if volume_conditions and count_conditions and confirmation:
                print("[BUY] Entry signal detected - both volume and count growing")
                print(f"[DEBUG] Volume: {current_volume:.2f} > MA: {current_volume_ma:.2f}, Mom: {current_volume_mom:.2f}")
                print(f"[DEBUG] Count: {current_count:.2f} > MA: {current_count_ma:.2f}, Mom: {current_count_mom:.2f}")
                
                # Calculate position size based on trend strength
                # Stronger growth = larger position (max 5% of portfolio)
                volume_strength = min(current_volume_mom / 100, 1.0)  # Normalize
                count_strength = min(current_count_mom / 100, 1.0)    # Normalize
                trend_strength = (volume_strength + count_strength) / 2
                
                # Risk percentage based on trend strength (0.5% to 5%)
                risk_percentage = 0.005 + (trend_strength * 0.045)
                risk_percentage = min(risk_percentage, 0.05)  # Max 5%
                
                # Calculate stop loss distance
                # 15% if both metrics positive, 8% if only one
                if current_volume_mom > 0 and current_count_mom > 0:
                    stop_distance = 0.15
                else:
                    stop_distance = 0.08
                
                # Calculate position size
                risk_amount = self.equity * risk_percentage
                position_size = risk_amount / (self.data.Close[-1] * stop_distance)
                
                # Convert to integer units
                position_size = int(round(position_size))
                
                if position_size > 0:
                    print(f"[BUY] Opening position: size={position_size}, risk={risk_percentage*100:.1f}%, price={self.data.Close[-1]:.2f}")
                    self.buy(size=position_size)
                else:
                    print(f"[WARNING] Invalid position size: {position_size}")
            else:
                # Debug why entry conditions not met
                if not volume_conditions:
                    print(f"[DEBUG] Volume conditions failed: V={current_volume:.2f} > MA={current_volume_ma:.2f}: {current_volume > current_volume_ma}, Mom>0: {current_volume_mom > 0}, V>Thresh={current_volume_threshold:.2f}: {current_volume > current_volume_threshold}")
                if not count_conditions:
                    print(f"[DEBUG] Count conditions failed: C={current_count:.2f} > MA={current_count_ma:.2f}: {current_count > current_count_ma}, Mom>0: {current_count_mom > 0}, C>Thresh={current_count_threshold:.2f}: {current_count > current_count_threshold}")
                if not confirmation:
                    print(f"[DEBUG] Confirmation failed")

# Load price data for backtesting
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()

# Drop unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Check for datetime column - handle different possible names
datetime_col = None
for col in price_data.columns:
    if 'date' in col or 'time' in col:
        datetime_col = col
        break

if datetime_col:
    price_data['datetime'] = pd.to_datetime(price_data[datetime_col])
else:
    # If no datetime column found, assume first column is datetime
    price_data['datetime'] = pd.to_datetime(price_data.iloc[:, 0])

# Set datetime index
price_data = price_data.set_index('datetime')

# Ensure proper column names for backtesting.py
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

# Keep only required columns
required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
available_cols = [col for col in required_cols if col in price_data.columns]
price_data = price_data[available_cols]

print(f"[INFO] Price data shape: {price_data.shape}")
print(f"[INFO] Price data columns: {list(price_data.columns)}")
print(f"[INFO] Price data range: {price_data.index.min()} to {price_data.index.max()}")
print(f"[INFO] Price data length: {len(price_data)}")

# Run backtest
bt = Backtest(price_data, VolumetricGrowth, cash=1000000, commission=.002)

stats = bt.run()
print(stats)
print(stats._strategy)