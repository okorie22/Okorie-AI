import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

# Load data directly
print("[INFO] Loading data...")

# Load OI data
oi_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/oi/oi_20251218.parquet')
print(f"[DEBUG] OI data shape: {oi_data.shape}")
print(f"[DEBUG] OI data columns: {list(oi_data.columns)}")
print(f"[DEBUG] OI data dtypes: {oi_data.dtypes.to_dict()}")

# Filter for BTC symbol
oi_data = oi_data[oi_data['symbol'] == 'BTC'].copy()
print(f"[DEBUG] Filtered BTC OI data shape: {oi_data.shape}")

if 'open_interest' in oi_data.columns:
    print(f"[DEBUG] OI column exists with {len(oi_data)} rows")
else:
    print("[ERROR] No 'open_interest' column found in OI data")
    raise ValueError("No 'open_interest' column found in OI data")

# Load price data
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
print(f"[DEBUG] Price data shape: {price_data.shape}")
print(f"[DEBUG] Price data columns: {list(price_data.columns)}")

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()
print(f"[DEBUG] Cleaned price columns: {list(price_data.columns)}")

# Drop unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Set datetime index for price data
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')

# Resample to 4H
price_data_4h = price_data.resample('4h').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum'
}).dropna()

print(f"[DEBUG] 4H price data shape: {price_data_4h.shape}")

# Prepare OI data
oi_data['timestamp'] = pd.to_datetime(oi_data['timestamp'])
oi_data = oi_data.set_index('timestamp')
oi_data = oi_data.sort_index()

# Resample OI data to 4H (use last value)
oi_data_4h = oi_data.resample('4h').agg({
    'open_interest': 'last',
    'funding_rate': 'last',
    'mark_price': 'last',
    'volume_24h': 'last'
}).dropna()

print(f"[DEBUG] 4H OI data shape: {oi_data_4h.shape}")

# Align data by index
common_index = price_data_4h.index.intersection(oi_data_4h.index)
price_data_4h = price_data_4h.loc[common_index]
oi_data_4h = oi_data_4h.loc[common_index]

print(f"[DEBUG] Aligned data shape: {price_data_4h.shape}")

# Combine data
combined_data = price_data_4h.copy()
combined_data['OI'] = oi_data_4h['open_interest']

# Ensure proper column names for backtesting.py
combined_data = combined_data.rename(columns={
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

print(f"[INFO] Final combined data shape: {combined_data.shape}")
print(f"[INFO] Data range: {combined_data.index[0]} to {combined_data.index[-1]}")

class InstitutionalFlowMomentum(Strategy):
    # Strategy parameters
    oi_threshold = 15.0  # 15% OI change threshold
    use_trend_filter = True  # Use SMA trend filter
    sma_period = 50
    risk_per_trade = 0.02  # 2% risk per trade
    stop_loss_pct = 0.02  # 2% stop loss
    max_trade_duration = 15  # Max 15 candles (4H each = 60 hours)
    
    def init(self):
        # Calculate OI percentage change using numpy operations
        oi_array = self.data.OI
        # Calculate percentage change manually
        oi_pct_change = np.zeros_like(oi_array)
        for i in range(1, len(oi_array)):
            if oi_array[i-1] != 0:
                oi_pct_change[i] = (oi_array[i] / oi_array[i-1] - 1) * 100
        
        self.oi_pct_change = self.I(
            lambda: oi_pct_change,
            name='OI_Pct_Change'
        )
        
        # Calculate SMA for trend filter
        self.sma = self.I(
            talib.SMA, self.data.Close, timeperiod=self.sma_period,
            name='SMA_50'
        )
        
        # Track trade duration
        self.trade_start_bar = 0
        
        # Debug prints
        print(f"[INFO] Strategy initialized with {len(self.data.Close)} bars")
        print(f"[INFO] OI threshold: {self.oi_threshold}%")
        print(f"[INFO] Using trend filter: {self.use_trend_filter}")
        
    def next(self):
        current_bar = len(self.data.Close) - 1
        
        # Skip if not enough data
        if current_bar < 2:
            return
            
        # Get current values
        current_oi_pct = self.oi_pct_change[-1]
        current_price = self.data.Close[-1]
        current_sma = self.sma[-1] if len(self.sma) > current_bar else None
        
        # Check for position exit conditions
        if self.position:
            # Exit on opposite signal
            if self.position.is_long and current_oi_pct <= -self.oi_threshold:
                print(f"[SELL] Closing long position - OI decreased {current_oi_pct:.2f}%")
                self.position.close()
                return
                
            elif self.position.is_short and current_oi_pct >= self.oi_threshold:
                print(f"[BUY] Closing short position - OI increased {current_oi_pct:.2f}%")
                self.position.close()
                return
                
            # Time-based exit
            trade_duration = current_bar - self.trade_start_bar
            if trade_duration >= self.max_trade_duration:
                print(f"[EXIT] Max trade duration reached ({trade_duration} bars)")
                self.position.close()
                return
                
            # Stop loss check
            if self.position.is_long:
                stop_price = self.position.entry_price * (1 - self.stop_loss_pct)
                if current_price <= stop_price:
                    print(f"[STOP] Long stop loss triggered at {current_price:.2f}")
                    self.position.close()
                    return
            else:
                stop_price = self.position.entry_price * (1 + self.stop_loss_pct)
                if current_price >= stop_price:
                    print(f"[STOP] Short stop loss triggered at {current_price:.2f}")
                    self.position.close()
                    return
        
        # Check for new entry signals (no existing position)
        else:
            # Long signal: OI increase >= 15%
            if current_oi_pct >= self.oi_threshold:
                # Check trend filter if enabled
                trend_ok = True
                if self.use_trend_filter and current_sma is not None:
                    trend_ok = current_price > current_sma
                    
                if trend_ok:
                    print(f"[BUY] OI increased {current_oi_pct:.2f}%, price: {current_price:.2f}")
                    
                    # Calculate position size based on risk
                    stop_distance = current_price * self.stop_loss_pct
                    risk_amount = self.equity * self.risk_per_trade
                    position_size = risk_amount / stop_distance
                    
                    # Convert to integer units
                    position_size = int(round(position_size))
                    
                    if position_size > 0:
                        self.buy(size=position_size)
                        self.trade_start_bar = current_bar
                        print(f"[INFO] Position size: {position_size} units")
            
            # Short signal: OI decrease <= -15%
            elif current_oi_pct <= -self.oi_threshold:
                # Check trend filter if enabled
                trend_ok = True
                if self.use_trend_filter and current_sma is not None:
                    trend_ok = current_price < current_sma
                    
                if trend_ok:
                    print(f"[SELL] OI decreased {current_oi_pct:.2f}%, price: {current_price:.2f}")
                    
                    # Calculate position size based on risk
                    stop_distance = current_price * self.stop_loss_pct
                    risk_amount = self.equity * self.risk_per_trade
                    position_size = risk_amount / stop_distance
                    
                    # Convert to integer units
                    position_size = int(round(position_size))
                    
                    if position_size > 0:
                        self.sell(size=position_size)
                        self.trade_start_bar = current_bar
                        print(f"[INFO] Position size: {position_size} units")

# Run backtest
print("\n[INFO] Starting backtest...")
bt = Backtest(
    combined_data,
    InstitutionalFlowMomentum,
    cash=1000000,
    commission=0.001,  # 0.1% commission
    exclusive_orders=True
)

stats = bt.run()
print("\n" + "="*50)
print("BACKTEST RESULTS")
print("="*50)
print(stats)
print("\n" + "="*50)
print("STRATEGY DETAILS")
print("="*50)
print(stats._strategy)