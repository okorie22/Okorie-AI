import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

class AdoptionMomentum(Strategy):
    # Strategy parameters
    threshold = 0.20  # 20% threshold for entry/exit
    
    def init(self):
        # Load onchain data
        onchain_data = pd.read_json('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/token_onchain_data.json')
        
        # Clean column names
        onchain_data.columns = onchain_data.columns.str.strip().str.lower()
        
        # Drop any unnamed columns
        onchain_data = onchain_data.drop(columns=[col for col in onchain_data.columns if 'unnamed' in col.lower()])
        
        # Debug data structure
        print(f"[DEBUG] Onchain data shape: {onchain_data.shape}")
        print(f"[DEBUG] Onchain data columns: {list(onchain_data.columns)}")
        
        # Extract holder count data
        # Assuming data structure: timestamp, tokens: {token: {metrics...}}
        # We need to parse the JSON structure
        holder_counts = []
        timestamps = []
        
        for idx, row in onchain_data.iterrows():
            try:
                # Parse the timestamp
                timestamp = pd.to_datetime(row['timestamp'])
                timestamps.append(timestamp)
                
                # Parse the tokens data
                tokens_data = row['tokens']
                if isinstance(tokens_data, str):
                    import json
                    tokens_data = json.loads(tokens_data)
                
                # Extract holder count for the first token (assuming single token strategy)
                # You may need to adjust this based on your actual data structure
                token_key = list(tokens_data.keys())[0]
                token_data = tokens_data[token_key]
                
                # Look for holder count in various possible field names
                holder_count = None
                possible_fields = ['holder_count', 'holders', 'holder_count_total', 'total_holders']
                
                for field in possible_fields:
                    if field in token_data:
                        holder_count = token_data[field]
                        break
                
                if holder_count is None:
                    # If no holder count found, use 0
                    holder_count = 0
                    print(f"[WARNING] No holder count found for timestamp {timestamp}")
                
                holder_counts.append(holder_count)
                
            except Exception as e:
                print(f"[ERROR] Error parsing row {idx}: {e}")
                # Add placeholder values
                timestamps.append(pd.NaT)
                holder_counts.append(0)
        
        # Create holder count DataFrame
        holder_df = pd.DataFrame({
            'timestamp': timestamps,
            'holder_count': holder_counts
        })
        
        # Set timestamp as index and sort
        holder_df = holder_df.set_index('timestamp')
        holder_df = holder_df.sort_index()
        
        # Remove rows with invalid timestamps
        holder_df = holder_df[holder_df.index.notna()]
        
        # Resample to daily frequency (if needed)
        # Use 'D' for daily resampling
        holder_df = holder_df.resample('D').last().ffill()
        
        print(f"[DEBUG] Holder data shape after processing: {holder_df.shape}")
        print(f"[DEBUG] Holder data sample:\n{holder_df.head()}")
        
        # Calculate percentage change in holder count
        # Calculate outside self.I() first
        holder_pct_change_values = holder_df['holder_count'].pct_change().fillna(0).values
        
        # Use self.I() wrapper for indicator calculation
        self.holder_pct_change = self.I(
            lambda: holder_pct_change_values,
            name='Holder_Pct_Change'
        )
        
        # Store holder count for reference
        self.holder_count = self.I(
            lambda: holder_df['holder_count'].values,
            name='Holder_Count'
        )
        
        # Track position state
        self.position_active = False
        self.entry_price = 0
        
        print("[INFO] Strategy initialized successfully")
    
    def next(self):
        # Get current index
        current_idx = len(self.data.Close) - 1
        
        # Skip if we don't have enough data
        if current_idx < 1:
            return
        
        # Get current holder percentage change
        current_pct_change = self.holder_pct_change[current_idx]
        
        # Get current price
        current_price = self.data.Close[current_idx]
        
        # Debug logging
        if current_idx % 100 == 0:  # Log every 100 bars
            print(f"[DEBUG] Bar {current_idx}: Price={current_price:.2f}, Holder Pct Change={current_pct_change:.4f}")
        
        # ENTRY LOGIC: Holder count increased by 20% or more
        if not self.position_active and current_pct_change >= self.threshold:
            # Calculate position size (100% of equity)
            position_size = 1.0  # Fraction of equity
            
            # Enter long position
            self.buy(size=position_size)
            self.position_active = True
            self.entry_price = current_price
            
            print(f"[BUY] Opening position at {current_price:.2f}")
            print(f"[BUY] Holder count increased by {current_pct_change*100:.1f}%")
        
        # EXIT LOGIC: Holder count decreased by 20% or more
        elif self.position_active and current_pct_change <= -self.threshold:
            # Exit entire position
            self.position.close()
            self.position_active = False
            
            # Calculate profit/loss
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            
            print(f"[SELL] Closing position at {current_price:.2f}")
            print(f"[SELL] Holder count decreased by {abs(current_pct_change)*100:.1f}%")
            print(f"[SELL] P&L: {pnl_pct:.2f}%")

# Load price data
print("[INFO] Loading price data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()

# Drop any unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Set datetime index
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')

# Ensure proper column names for backtesting.py
required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
column_mapping = {
    'open': 'Open',
    'high': 'High', 
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
}

# Rename columns
for old_col, new_col in column_mapping.items():
    if old_col in price_data.columns:
        price_data = price_data.rename(columns={old_col: new_col})

# Ensure all required columns exist
for col in required_columns:
    if col not in price_data.columns:
        print(f"[WARNING] Missing column: {col}")

print(f"[DEBUG] Price data shape: {price_data.shape}")
print(f"[DEBUG] Price data columns: {list(price_data.columns)}")
print(f"[DEBUG] Price data index: {price_data.index[:5]}")

# Run backtest
print("[INFO] Running backtest...")
bt = Backtest(
    price_data,
    AdoptionMomentum,
    cash=1000000,  # $1,000,000 initial capital
    commission=0.001,  # 0.1% commission
    exclusive_orders=True
)

# Run optimization (simple parameter test)
stats = bt.run()
print("\n" + "="*50)
print("BACKTEST RESULTS")
print("="*50)
print(stats)
print("\n" + "="*50)
print("STRATEGY DETAILS")
print("="*50)
print(stats._strategy)