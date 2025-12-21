import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

class TriplexSupertrend(Strategy):
    def init(self):
        print("[STRATEGY] TriplexSupertrend initialized")
        
        # Clean column names
        self.data.df.columns = self.data.df.columns.str.strip().str.lower()
        
        # Drop unnamed columns
        self.data.df = self.data.df.drop(columns=[col for col in self.data.df.columns if 'unnamed' in col.lower()])
        
        # Ensure proper column capitalization for backtesting.py
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in self.data.df.columns:
                raise ValueError(f"Required column '{col}' not found in data")
        
        # Calculate ATR for Supertrend calculations
        self.atr_8 = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=8)
        self.atr_9 = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=9)
        self.atr_16 = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=16)
        self.atr_18 = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=18)
        
        # Calculate Supertrend indicators
        # Buy Supertrends (Bullish Confirmation Triad)
        self.st_b1 = self.I(self._calculate_supertrend, multiplier=4, period=8, atr_data=self.atr_8)
        self.st_b2 = self.I(self._calculate_supertrend, multiplier=7, period=9, atr_data=self.atr_9)
        self.st_b3 = self.I(self._calculate_supertrend, multiplier=1, period=8, atr_data=self.atr_8)
        
        # Sell Supertrends (Bearish Confirmation Triad)
        self.st_s1 = self.I(self._calculate_supertrend, multiplier=1, period=16, atr_data=self.atr_16)
        self.st_s2 = self.I(self._calculate_supertrend, multiplier=3, period=18, atr_data=self.atr_18)
        self.st_s3 = self.I(self._calculate_supertrend, multiplier=6, period=18, atr_data=self.atr_18)
        
        # Track trade count for reduced logging
        self.trade_count = 0
        self.last_print_bar = 0
        
    def _calculate_supertrend(self, multiplier, period, atr_data):
        """Calculate Supertrend indicator with given parameters"""
        # Calculate basic upper and lower bands
        hl2 = (self.data.High + self.data.Low) / 2
        
        # Initialize arrays
        supertrend = np.zeros(len(self.data.Close))
        direction = np.zeros(len(self.data.Close))
        
        # Calculate Supertrend
        for i in range(period, len(self.data.Close)):
            atr_value = atr_data[i] * multiplier
            upper_band = hl2[i] + atr_value
            lower_band = hl2[i] - atr_value
            
            if i == period:
                # Initial values
                supertrend[i] = upper_band
                direction[i] = 1  # 1 for bullish (below price), -1 for bearish (above price)
            else:
                # Update upper band
                if upper_band < supertrend[i-1] or self.data.Close[i-1] > supertrend[i-1]:
                    upper_band = supertrend[i-1]
                
                # Update lower band
                if lower_band > supertrend[i-1] or self.data.Close[i-1] < supertrend[i-1]:
                    lower_band = supertrend[i-1]
                
                # Determine Supertrend value and direction
                if supertrend[i-1] == upper_band:
                    if self.data.Close[i] <= upper_band:
                        supertrend[i] = upper_band
                        direction[i] = 1
                    else:
                        supertrend[i] = lower_band
                        direction[i] = -1
                else:  # supertrend[i-1] == lower_band
                    if self.data.Close[i] >= lower_band:
                        supertrend[i] = lower_band
                        direction[i] = -1
                    else:
                        supertrend[i] = upper_band
                        direction[i] = 1
        
        # Return direction array (1 for bullish/up, -1 for bearish/down)
        return direction
    
    def next(self):
        # Skip if not enough data
        if len(self.data) < 30:
            return
            
        # Check for volume validation
        if self.data.Volume[-1] <= 0:
            return
            
        # Print periodic summary every 200 bars
        if len(self.data) - self.last_print_bar >= 200:
            print(f"[SUMMARY] Bar {len(self.data)}, Equity: ${self.equity:.2f}")
            self.last_print_bar = len(self.data)
        
        # Get current Supertrend signals
        st_b1_signal = self.st_b1[-1]
        st_b2_signal = self.st_b2[-1]
        st_b3_signal = self.st_b3[-1]
        st_s1_signal = self.st_s1[-1]
        st_s2_signal = self.st_s2[-1]
        st_s3_signal = self.st_s3[-1]
        
        # Get previous signals for exit conditions
        st_b2_prev = self.st_b2[-2] if len(self.data) > 1 else 0
        st_s2_prev = self.st_s2[-2] if len(self.data) > 1 else 0
        
        # Calculate position size based on volatility (ATR)
        current_atr = self.atr_9[-1] if len(self.atr_9) > 0 else 0
        current_price = self.data.Close[-1]
        
        if current_atr > 0 and current_price > 0:
            # Use ATR-based position sizing: higher volatility = smaller position
            atr_ratio = current_atr / current_price
            # Base position size: 2% of equity, adjusted for volatility
            base_size = 0.02
            volatility_adjustment = min(1.0, 0.01 / max(atr_ratio, 0.001))  # Cap adjustment
            target_fraction = base_size * volatility_adjustment
            
            # Ensure position size is within 1-10% range
            position_fraction = max(0.01, min(target_fraction, 0.10))
        else:
            # Default to 2% if ATR calculation fails
            position_fraction = 0.02
        
        # ENTRY LOGIC
        # Long Entry: ALL THREE Buy Supertrends show bullish (1) signal
        if (st_b1_signal == 1 and st_b2_signal == 1 and st_b3_signal == 1 and 
            not self.position):
            
            self.trade_count += 1
            if self.trade_count % 10 == 0:
                print(f"[TRADE {self.trade_count}] LONG Entry at bar {len(self.data)}")
            
            # Calculate stop loss price (26.5% below entry)
            stop_price = current_price * (1 - 0.265)
            
            # Execute buy with position size as fraction of equity
            self.buy(size=position_fraction, sl=stop_price)
            print(f"[BUY] Position size: {position_fraction:.4f} ({position_fraction*100:.2f}% of equity)")
        
        # Short Entry: ALL THREE Sell Supertrends show bearish (-1) signal
        elif (st_s1_signal == -1 and st_s2_signal == -1 and st_s3_signal == -1 and 
              not self.position):
            
            self.trade_count += 1
            if self.trade_count % 10 == 0:
                print(f"[TRADE {self.trade_count}] SHORT Entry at bar {len(self.data)}")
            
            # Calculate stop loss price (26.5% above entry for short)
            stop_price = current_price * (1 + 0.265)
            
            # Execute sell with position size as fraction of equity
            self.sell(size=position_fraction, sl=stop_price)
            print(f"[SELL] Position size: {position_fraction:.4f} ({position_fraction*100:.2f}% of equity)")
        
        # EXIT LOGIC and TRAILING STOP MANAGEMENT
        if self.position:
            entry_price = self.position.entry_price
            current_pnl_pct = (current_price - entry_price) / entry_price if self.position.is_long else (entry_price - current_price) / entry_price
            
            # Check for trailing stop activation
            if abs(current_pnl_pct) >= 0.10:  # +10% profit reached
                # Update trailing stop if not already set
                if self.position.sl is None or (
                    (self.position.is_long and self.position.sl < current_price * 0.90) or
                    (not self.position.is_long and self.position.sl > current_price * 1.10)
                ):
                    # Set trailing stop at -10% from current price
                    if self.position.is_long:
                        new_sl = current_price * 0.90
                    else:
                        new_sl = current_price * 1.10
                    
                    self.position.sl = new_sl
                    if self.trade_count % 10 == 0:
                        print(f"[TRAILING STOP] Activated at {new_sl:.2f}")
            
            # Exit Long: ST_S2 flips from up (1) to down (-1)
            if self.position.is_long and st_s2_prev == 1 and st_s2_signal == -1:
                self.position.close()
                print(f"[EXIT LONG] ST_S2 flipped bearish at bar {len(self.data)}")
            
            # Exit Short: ST_B2 flips from down (-1) to up (1)
            elif not self.position.is_long and st_b2_prev == -1 and st_b2_signal == 1:
                self.position.close()
                print(f"[EXIT SHORT] ST_B2 flipped bullish at bar {len(self.data)}")

# Load and prepare data
print("[INFO] Loading data...")
try:
    # Load OHLCV data
    price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
    
    # Clean column names
    price_data.columns = price_data.columns.str.strip().str.lower()
    
    # Drop unnamed columns
    price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])
    
    # Ensure required columns exist
    required_mapping = {
        'open': 'Open',
        'high': 'High', 
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    }
    
    # Rename columns to match backtesting.py requirements
    for old_col, new_col in required_mapping.items():
        if old_col in price_data.columns:
            price_data[new_col] = price_data[old_col]
    
    # Set datetime index
    if 'timestamp' in price_data.columns:
        price_data['Date'] = pd.to_datetime(price_data['timestamp'])
    elif 'date' in price_data.columns:
        price_data['Date'] = pd.to_datetime(price_data['date'])
    else:
        # Try to find datetime column
        datetime_cols = [col for col in price_data.columns if 'time' in col.lower() or 'date' in col.lower()]
        if datetime_cols:
            price_data['Date'] = pd.to_datetime(price_data[datetime_cols[0]])
        else:
            raise ValueError("No datetime column found in data")
    
    price_data = price_data.set_index('Date')
    
    # Filter for volume > 0
    price_data = price_data[price_data['Volume'] > 0]
    
    print(f"[INFO] Data loaded: {len(price_data)} rows, {len(price_data.columns)} columns")
    print(f"[INFO] Data columns: {list(price_data.columns)}")
    print(f"[INFO] Date range: {price_data.index.min()} to {price_data.index.max()}")
    
except Exception as e:
    print(f"[ERROR] Failed to load data: {e}")
    raise

# Run backtest
print("[INFO] Starting backtest...")
bt = Backtest(price_data, TriplexSupertrend, cash=1000000, commission=.002)

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
print(f"\n[FINAL] Total trades executed: {stats._strategy.trade_count}")