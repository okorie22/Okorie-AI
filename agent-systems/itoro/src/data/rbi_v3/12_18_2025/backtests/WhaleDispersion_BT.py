import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import talib

# Load data directly
print("[INFO] Loading data...")

# Load on-chain data (whale concentration)
print("[DEBUG] Loading on-chain data...")
onchain_data = pd.read_json('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/token_onchain_data.json')
print(f"[DEBUG] On-chain data shape: {onchain_data.shape}")
print(f"[DEBUG] On-chain data columns: {list(onchain_data.columns)}")

# Clean column names
onchain_data.columns = onchain_data.columns.str.strip().str.lower()
print(f"[DEBUG] Cleaned columns: {list(onchain_data.columns)}")

# Drop unnamed columns
onchain_data = onchain_data.drop(columns=[col for col in onchain_data.columns if 'unnamed' in col.lower()])

# Check for required columns
required_onchain_cols = ['timestamp', 'symbol', 'whale_concentration', 'market_cap']
missing_cols = [col for col in required_onchain_cols if col not in onchain_data.columns]
if missing_cols:
    print(f"[ERROR] Missing columns in on-chain data: {missing_cols}")
    raise ValueError(f"Missing required columns: {missing_cols}")

# Set datetime index
onchain_data['timestamp'] = pd.to_datetime(onchain_data['timestamp'])
onchain_data = onchain_data.set_index('timestamp')
print(f"[DEBUG] On-chain data index: {onchain_data.index[:5]}")

# Load price data
print("[DEBUG] Loading price data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
print(f"[DEBUG] Price data shape: {price_data.shape}")
print(f"[DEBUG] Price data columns: {list(price_data.columns)}")

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()
print(f"[DEBUG] Cleaned price columns: {list(price_data.columns)}")

# Drop unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Rename columns to match backtesting.py requirements
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

# Ensure required columns exist
required_price_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
for col in required_price_cols:
    if col not in price_data.columns:
        print(f"[ERROR] Missing price column: {col}")
        raise ValueError(f"Missing required price column: {col}")

# Set datetime index
if 'timestamp' in price_data.columns:
    price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
    price_data = price_data.set_index('timestamp')
elif 'date' in price_data.columns:
    price_data['date'] = pd.to_datetime(price_data['date'])
    price_data = price_data.set_index('date')
else:
    print("[ERROR] No timestamp or date column found in price data")
    raise ValueError("No timestamp column found")

print(f"[DEBUG] Price data index: {price_data.index[:5]}")

# Resample to 4h frequency (lowercase to avoid pandas warning)
price_data = price_data.resample('4h').agg({
    'Open': 'first',
    'High': 'max',
    'Low': 'min',
    'Close': 'last',
    'Volume': 'sum'
}).dropna()
print(f"[DEBUG] Resampled price data shape: {price_data.shape}")

# Merge on-chain data with price data
print("[DEBUG] Merging data...")
# Resample on-chain data to match price data frequency
onchain_data_resampled = onchain_data.resample('4h').ffill()

# Merge on timestamp
merged_data = pd.merge(
    price_data,
    onchain_data_resampled,
    left_index=True,
    right_index=True,
    how='left'
)

# Forward fill on-chain data
merged_data['whale_concentration'] = merged_data['whale_concentration'].ffill()
merged_data['market_cap'] = merged_data['market_cap'].ffill()

print(f"[DEBUG] Merged data shape: {merged_data.shape}")
print(f"[DEBUG] Merged data columns: {list(merged_data.columns)}")
print(f"[DEBUG] Whale concentration sample: {merged_data['whale_concentration'].head()}")
print(f"[DEBUG] Market cap sample: {merged_data['market_cap'].head()}")

class WhaleDispersion(Strategy):
    # Strategy parameters
    whale_threshold = 30.0  # 30% concentration threshold
    market_cap_min = 5e9  # $5B minimum market cap
    exit_percentage = 1.0  # Exit 100% of position
    
    def init(self):
        # Calculate indicators using self.I() wrapper
        print("[INFO] Initializing WhaleDispersion strategy...")
        
        # Whale concentration ratio (already in percentage)
        self.whale_conc = self.I(lambda: self.data.df['whale_concentration'].values)
        
        # Market cap (in dollars)
        self.market_cap = self.I(lambda: self.data.df['market_cap'].values)
        
        # Simple moving averages for trend context
        self.sma20 = self.I(talib.SMA, self.data.Close, timeperiod=20)
        self.sma50 = self.I(talib.SMA, self.data.Close, timeperiod=50)
        
        # Track if we're in a position
        self.in_position = False
        
        print(f"[INFO] Strategy initialized with whale threshold: {self.whale_threshold}%")
        print(f"[INFO] Market cap minimum: ${self.market_cap_min:,.0f}")
        
    def next(self):
        current_price = self.data.Close[-1]
        current_bar = len(self.data.Close) - 1
        
        # Get current whale concentration and market cap
        if current_bar < len(self.whale_conc):
            whale_ratio = self.whale_conc[current_bar]
            market_cap_val = self.market_cap[current_bar]
        else:
            whale_ratio = 0
            market_cap_val = 0
        
        # Check if we have valid data
        if pd.isna(whale_ratio) or pd.isna(market_cap_val):
            return
        
        # Debug logging
        if current_bar % 100 == 0:
            print(f"[DEBUG] Bar {current_bar}: Price=${current_price:.2f}, Whale={whale_ratio:.1f}%, MCap=${market_cap_val:,.0f}")
        
        # Check exit conditions
        if self.position:
            self.in_position = True
            
            # Check if token is large-cap
            is_large_cap = market_cap_val >= self.market_cap_min
            
            # Check whale concentration threshold
            whale_above_threshold = whale_ratio > self.whale_threshold
            
            # Exit signal: Both conditions met
            if is_large_cap and whale_above_threshold:
                print(f"[SELL] Exit signal triggered at bar {current_bar}")
                print(f"[SELL] Price: ${current_price:.2f}, Whale Concentration: {whale_ratio:.1f}% > {self.whale_threshold}%")
                print(f"[SELL] Market Cap: ${market_cap_val:,.0f} >= ${self.market_cap_min:,.0f}")
                
                # Exit full position
                self.position.close()
                self.in_position = False
                print(f"[SELL] Position closed at ${current_price:.2f}")
        
        # Entry logic (simplified - just for testing)
        # In real implementation, entry would come from another strategy
        elif not self.position and current_bar > 50:
            # Simple trend-following entry for testing
            if self.sma20[-1] > self.sma50[-1] and current_price > self.sma20[-1]:
                # Calculate position size based on risk
                risk_percentage = 0.02  # 2% risk per trade
                stop_distance = current_price * 0.05  # 5% stop loss
                risk_amount = self.equity * risk_percentage
                
                # Calculate position size and ensure it's integer
                position_size = risk_amount / stop_distance
                position_size = int(round(position_size))
                
                if position_size > 0:
                    print(f"[BUY] Opening test position at bar {current_bar}")
                    print(f"[BUY] Price: ${current_price:.2f}, Size: {position_size} units")
                    self.buy(size=position_size)
                    self.in_position = True

# Prepare data for backtesting
print("[INFO] Preparing data for backtest...")
backtest_data = merged_data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
backtest_data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

# Add whale concentration and market cap as additional columns
backtest_data['whale_concentration'] = merged_data['whale_concentration']
backtest_data['market_cap'] = merged_data['market_cap']

print(f"[INFO] Final backtest data shape: {backtest_data.shape}")
print(f"[INFO] Data range: {backtest_data.index[0]} to {backtest_data.index[-1]}")

# Run backtest
print("[INFO] Starting backtest...")
bt = Backtest(
    backtest_data,
    WhaleDispersion,
    cash=1000000,
    commission=0.001,
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