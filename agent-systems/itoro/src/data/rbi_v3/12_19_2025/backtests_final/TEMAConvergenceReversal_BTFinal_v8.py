import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

# Load data
print("[INFO] Loading price data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
price_data.columns = price_data.columns.str.strip().str.lower()
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Check column names
print(f"[DEBUG] Original columns: {list(price_data.columns)}")

# Rename timestamp column to datetime for consistency
if 'timestamp' in price_data.columns:
    price_data = price_data.rename(columns={'timestamp': 'datetime'})

# Resample to 4h timeframe
print("[INFO] Resampling to 4h timeframe...")
price_data['datetime'] = pd.to_datetime(price_data['datetime'])
price_data = price_data.set_index('datetime')
ohlc_dict = {
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum'
}
data_4h = price_data.resample('4h').apply(ohlc_dict)
data_4h = data_4h.dropna()

# Prepare data for backtesting - use exact column names required
data_4h = data_4h.reset_index()
data_4h.columns = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']

print(f"[INFO] Loaded {len(data_4h)} 4h bars")
print(f"[INFO] Data columns: {list(data_4h.columns)}")
print(f"[DEBUG] First few rows:\n{data_4h.head()}")

class TEMAConvergenceReversal(Strategy):
    # Strategy parameters
    stop_loss_pct = 0.345  # 34.5% stop loss
    risk_per_trade = 0.02  # 2% risk per trade
    
    # ROI table: (candles_since_entry, profit_target)
    roi_table = [
        (0, 0.523),    # 52.3% at entry (limit order)
        (1553, 0.123), # 12.3% after 1553 candles
        (2332, 0.076), # 7.6% after 2332 candles
        (3169, 0.0)    # 0% after 3169 candles
    ]
    
    def init(self):
        # Calculate entry TEMAs
        self.tema15 = self.I(talib.TEMA, self.data.Close, timeperiod=15)
        self.tema30 = self.I(talib.TEMA, self.data.Close, timeperiod=30)
        self.tema45 = self.I(talib.TEMA, self.data.Close, timeperiod=45)
        self.tema60 = self.I(talib.TEMA, self.data.Close, timeperiod=60)
        
        # Calculate exit TEMAs
        self.tema68 = self.I(talib.TEMA, self.data.Close, timeperiod=68)
        self.tema136 = self.I(talib.TEMA, self.data.Close, timeperiod=136)
        self.tema204 = self.I(talib.TEMA, self.data.Close, timeperiod=204)
        self.tema272 = self.I(talib.TEMA, self.data.Close, timeperiod=272)
        self.tema340 = self.I(talib.TEMA, self.data.Close, timeperiod=340)
        self.tema408 = self.I(talib.TEMA, self.data.Close, timeperiod=408)
        self.tema476 = self.I(talib.TEMA, self.data.Close, timeperiod=476)
        self.tema544 = self.I(talib.TEMA, self.data.Close, timeperiod=544)
        self.tema612 = self.I(talib.TEMA, self.data.Close, timeperiod=612)
        self.tema680 = self.I(talib.TEMA, self.data.Close, timeperiod=680)
        self.tema748 = self.I(talib.TEMA, self.data.Close, timeperiod=748)
        self.tema816 = self.I(talib.TEMA, self.data.Close, timeperiod=816)
        
        # Track debug logging
        self.debug_counter = 0
        self.trade_counter = 0
        
    def next(self):
        current_bar = len(self.data.Close) - 1
        
        # Debug logging every 100 bars
        if current_bar % 100 == 0:
            self.debug_counter += 1
            if self.debug_counter % 10 == 0:
                print(f"[DEBUG] Bar {current_bar}, Price: {self.data.Close[-1]:.2f}")
                if len(self.tema15) > 0:
                    print(f"  TEMA15: {self.tema15[-1]:.2f}, TEMA30: {self.tema30[-1]:.2f}")
        
        # Check if we have a position
        if self.position:
            self.manage_position(current_bar)
        else:
            self.check_entry(current_bar)
    
    def check_entry(self, current_bar):
        # Check entry conditions - need enough data for indicators
        if len(self.data.Close) < 100:
            return
            
        # Check if indicators have enough data
        if (len(self.tema15) < 2 or len(self.tema30) < 2 or 
            len(self.tema45) < 2 or len(self.tema60) < 2):
            return
            
        cond1 = self.tema30[-1] < self.tema15[-1]
        cond2 = self.tema45[-1] < self.tema30[-1]
        cond3 = self.tema60[-1] < self.tema45[-1]
        
        if cond1 and cond2 and cond3:
            print(f"[BUY] Entry signal at bar {current_bar}, price: {self.data.Close[-1]:.2f}")
            
            # Calculate position size based on risk
            entry_price = self.data.Close[-1]
            stop_price = entry_price * (1 - self.stop_loss_pct)
            stop_distance = entry_price - stop_price
            
            if stop_distance > 0:
                risk_amount = self.equity * self.risk_per_trade
                position_size = risk_amount / stop_distance
                
                # Convert to units (round down to nearest whole unit)
                position_size = int(position_size)
                
                if position_size > 0:
                    # Place buy order with stop loss
                    self.buy(size=position_size, sl=stop_price)
                    self.trade_counter += 1
                    print(f"[BUY EXECUTED] Trade #{self.trade_counter}, Size: {position_size}, Entry: {entry_price:.2f}, Stop: {stop_price:.2f}")
                else:
                    print(f"[BUY SKIPPED] Position size too small: {position_size}")
            else:
                print(f"[BUY SKIPPED] Invalid stop distance: {stop_distance}")
    
    def manage_position(self, current_bar):
        if not self.position:
            return
            
        # Get entry price from last trade
        if len(self.trades) > 0:
            entry_price = self.trades[-1].entry_price
            # Find entry bar index
            entry_bar = None
            for i in range(len(self.data.Close)-1, -1, -1):
                if self.data.Close[i] == entry_price:
                    entry_bar = i
                    break
            if entry_bar is None:
                entry_bar = current_bar
        else:
            # Fallback if no trades recorded
            entry_price = self.data.Close[-1]
            entry_bar = current_bar
            
        current_price = self.data.Close[-1]
        candles_since_entry = current_bar - entry_bar
        
        # Check exit conditions
        
        # 1. Check for TEMA cross above in any exit pair
        exit_signal = False
        
        # Define exit TEMA pairs directly in the method
        exit_tema_pairs = [
            (self.tema68, self.tema136),
            (self.tema136, self.tema204),
            (self.tema204, self.tema272),
            (self.tema272, self.tema340),
            (self.tema340, self.tema408),
            (self.tema408, self.tema476),
            (self.tema476, self.tema544),
            (self.tema544, self.tema612),
            (self.tema612, self.tema680),
            (self.tema680, self.tema748),
            (self.tema748, self.tema816)
        ]
        
        for i, (short_tema, long_tema) in enumerate(exit_tema_pairs):
            if len(short_tema) < 2 or len(long_tema) < 2:
                continue
                
            # Check if short crossed above long from previous bar
            if (short_tema[-2] <= long_tema[-2]) and (short_tema[-1] > long_tema[-1]):
                exit_signal = True
                print(f"[EXIT] TEMA cross detected in pair {i+1} at bar {current_bar}")
                break
        
        if exit_signal:
            self.position.close()
            print(f"[EXIT] Closed position at {current_price:.2f}")
            return
        
        # 2. Check ROI table profit targets
        current_profit_pct = (current_price - entry_price) / entry_price
        
        # Find applicable ROI target based on candles since entry
        target_profit = None
        for i in range(len(self.roi_table)):
            candles_threshold, profit_target = self.roi_table[i]
            if candles_since_entry <= candles_threshold:
                target_profit = profit_target
                break
        
        # If we're at the last threshold, use 0%
        if target_profit is None:
            target_profit = 0.0
        
        # Check if we've hit the profit target
        if current_profit_pct >= target_profit and target_profit > 0:
            self.position.close()
            print(f"[EXIT] Hit profit target {target_profit*100:.1f}% at bar {current_bar}")
            print(f"[EXIT] Closed at {current_price:.2f}")
            return
        
        # 3. Check breakeven exit (0% profit after 3169 candles)
        if candles_since_entry >= 3169 and current_profit_pct >= 0:
            self.position.close()
            print(f"[EXIT] Time-based breakeven exit at bar {current_bar}")
            print(f"[EXIT] Closed at {current_price:.2f}")
            return

# Run backtest
print("[INFO] Starting backtest...")
bt = Backtest(
    data_4h,
    TEMAConvergenceReversal,
    cash=1000000,
    commission=0.001,
    exclusive_orders=True
)

stats = bt.run()
print(stats)
print(stats._strategy)