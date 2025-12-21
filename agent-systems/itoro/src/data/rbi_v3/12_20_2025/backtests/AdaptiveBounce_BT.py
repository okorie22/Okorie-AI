import pandas as pd
import talib
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

class AdaptiveBounce(Strategy):
    def init(self):
        # Print initialization message
        print("[STRATEGY] AdaptiveBounce initialized")
        
        # Calculate indicators using self.I() wrapper
        # Bollinger Bands (20 period, 2 std dev)
        self.bb_upper = self.I(talib.BBANDS, self.data.Close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)[0]
        self.bb_middle = self.I(talib.BBANDS, self.data.Close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)[1]
        self.bb_lower = self.I(talib.BBANDS, self.data.Close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)[2]
        
        # RSI (14 period)
        self.rsi = self.I(talib.RSI, self.data.Close, timeperiod=14)
        
        # 50-period SMA for trend filter
        self.sma50 = self.I(talib.SMA, self.data.Close, timeperiod=50)
        
        # Track consecutive bars below lower BB
        self.bars_below_bb = self.I(lambda x: [0]*len(x), self.data.Close)
        
        # Initialize trade counter for reduced logging
        self.trade_count = 0
        
        # Print data info
        print(f"[INFO] Data loaded: {len(self.data)} bars")
        print(f"[INFO] Required minimum bars: 50")
        
    def next(self):
        # Skip if we don't have enough data for indicators
        if len(self.data) < 50:
            return
            
        # Update consecutive bars below lower BB counter
        current_idx = len(self.data) - 1
        if current_idx > 0:
            prev_bars = self.bars_below_bb[current_idx - 1]
            if self.data.Close[-1] < self.bb_lower[-1]:
                self.bars_below_bb[current_idx] = prev_bars + 1
            else:
                self.bars_below_bb[current_idx] = 0
        else:
            if self.data.Close[-1] < self.bb_lower[-1]:
                self.bars_below_bb[current_idx] = 1
            else:
                self.bars_below_bb[current_idx] = 0
        
        # ENTRY CONDITIONS (ALL must be true)
        entry_conditions = []
        
        # 1. RSI below 30 (oversold)
        rsi_oversold = self.rsi[-1] < 30
        entry_conditions.append(rsi_oversold)
        
        # 2. Price below lower Bollinger Band
        price_below_bb = self.data.Close[-1] < self.bb_lower[-1]
        entry_conditions.append(price_below_bb)
        
        # 3. Price above 50-period SMA (positive trend context)
        price_above_sma50 = self.data.Close[-1] > self.sma50[-1]
        entry_conditions.append(price_above_sma50)
        
        # 4. Limited duration: max 2 consecutive bars below lower BB
        limited_extremes = self.bars_below_bb[-1] <= 2
        entry_conditions.append(limited_extremes)
        
        # Check if we're not already in a position
        no_position = not self.position
        
        # ENTRY LOGIC
        if all(entry_conditions) and no_position:
            # Fixed position size: 2% of equity
            position_size = 0.02  # 2% of equity
            
            # Calculate stop loss price (18% below entry)
            entry_price = self.data.Close[-1]
            stop_loss_price = entry_price * 0.82
            
            # Execute buy order with stop loss
            self.buy(size=position_size, sl=stop_loss_price)
            
            # Increment trade counter
            self.trade_count += 1
            
            # Print trade entry (reduced frequency)
            if self.trade_count % 10 == 0 or self.trade_count <= 5:
                print(f"[TRADE {self.trade_count}] Entry at bar {len(self.data)}, Price: ${entry_price:.2f}, Size: {position_size*100:.1f}%")
        
        # EXIT CONDITIONS (ANY can trigger exit)
        if self.position:
            entry_price = self.position.entry_price
            current_price = self.data.Close[-1]
            
            exit_conditions = []
            
            # 1. RSI crosses above 70 (overbought)
            rsi_overbought = self.rsi[-1] > 70
            exit_conditions.append(rsi_overbought)
            
            # 2. Price closes above BB middle line
            price_above_middle = self.data.Close[-1] > self.bb_middle[-1]
            exit_conditions.append(price_above_middle)
            
            # 3. Fixed take profit: +12% from entry
            profit_target = entry_price * 1.12
            take_profit_hit = current_price >= profit_target
            exit_conditions.append(take_profit_hit)
            
            # EXIT LOGIC
            if any(exit_conditions):
                # Determine exit reason
                if rsi_overbought:
                    exit_reason = "RSI > 70"
                elif price_above_middle:
                    exit_reason = "Price above BB middle"
                elif take_profit_hit:
                    exit_reason = "+12% profit target"
                else:
                    exit_reason = "Other condition"
                
                # Close position
                self.position.close()
                
                # Print trade exit (reduced frequency)
                if self.trade_count % 10 == 0 or self.trade_count <= 5:
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    print(f"[EXIT {self.trade_count}] {exit_reason}, Profit: {profit_pct:.2f}%")
        
        # Print periodic summary (every 200 bars)
        if len(self.data) % 200 == 0:
            equity = self.equity
            print(f"[SUMMARY] Bar {len(self.data)}, Equity: ${equity:.2f}, Trades: {self.trade_count}")

# Data loading and preparation
if __name__ == "__main__":
    # Load 1-hour timeframe data
    print("[INFO] Loading 1-hour BTC data...")
    price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-1h.csv')
    
    # Clean column names
    price_data.columns = price_data.columns.str.strip().str.lower()
    
    # Drop any unnamed columns
    price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])
    
    # Ensure proper column mapping for backtesting.py
    # Required columns: 'Open', 'High', 'Low', 'Close', 'Volume'
    column_mapping = {}
    
    # Try to find the correct columns
    for col in price_data.columns:
        col_lower = col.lower()
        if 'open' in col_lower:
            column_mapping['Open'] = col
        elif 'high' in col_lower:
            column_mapping['High'] = col
        elif 'low' in col_lower:
            column_mapping['Low'] = col
        elif 'close' in col_lower:
            column_mapping['Close'] = col
        elif 'volume' in col_lower:
            column_mapping['Volume'] = col
        elif 'date' in col_lower or 'time' in col_lower or 'timestamp' in col_lower:
            column_mapping['datetime'] = col
    
    # Rename columns to match backtesting.py requirements
    for bt_col, data_col in column_mapping.items():
        if bt_col != 'datetime':
            price_data.rename(columns={data_col: bt_col}, inplace=True)
    
    # Set datetime index
    if 'datetime' in column_mapping:
        price_data['datetime'] = pd.to_datetime(price_data[column_mapping['datetime']])
        price_data.set_index('datetime', inplace=True)
    
    # Ensure we have all required columns
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing_cols = [col for col in required_cols if col not in price_data.columns]
    
    if missing_cols:
        print(f"[WARNING] Missing columns: {missing_cols}")
        print(f"[INFO] Available columns: {list(price_data.columns)}")
        # Try to use first 5 columns if they match OHLCV pattern
        if len(price_data.columns) >= 5:
            price_data.columns = ['Open', 'High', 'Low', 'Close', 'Volume'] + list(price_data.columns[5:])
            print("[INFO] Assigned first 5 columns as OHLCV")
    
    print(f"[INFO] Data shape: {price_data.shape}")
    print(f"[INFO] Data columns: {list(price_data.columns)}")
    print(f"[INFO] Data range: {price_data.index[0]} to {price_data.index[-1]}")
    
    # Run backtest
    print("\n[INFO] Starting backtest...")
    bt = Backtest(price_data, AdaptiveBounce, cash=1000000, commission=.002)
    
    # Run with default parameters
    stats = bt.run()
    
    # Print full statistics
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)
    print(stats)
    print("\n" + "="*80)
    print("STRATEGY DETAILS")
    print("="*80)
    print(stats._strategy)
    
    # Print final trade summary
    print(f"\n[FINAL] Total trades executed: {stats['# Trades']}")
    print(f"[FINAL] Final equity: ${stats['Equity Final [$]']:.2f}")
    print(f"[FINAL] Return: {stats['Return [%]']:.2f}%")