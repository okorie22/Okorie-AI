import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

# Load data
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-1d.csv')
price_data.columns = price_data.columns.str.strip().str.lower()
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High', 
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

class PatternSync(Strategy):
    def init(self):
        print("[STRATEGY] PatternSync initialized for daily timeframe")
        self.trade_count = 0
        
        # Calculate all five candlestick patterns using self.I()
        self.cdl_engulfing = self.I(talib.CDLENGULFING, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_hammer = self.I(talib.CDLHAMMER, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_doji = self.I(talib.CDLDOJI, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_morningstar = self.I(talib.CDLMORNINGSTAR, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.cdl_eveningstar = self.I(talib.CDLEVENINGSTAR, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        
        # Parameters
        self.enable_engulfing = True
        self.enable_hammer = True
        self.enable_doji = True
        self.enable_morningstar = True
        self.enable_eveningstar = True
        
        # Risk management parameters
        self.initial_stop_loss = 0.288  # -28.8%
        self.trailing_activation = 0.084  # +8.4%
        self.trailing_offset = 0.032  # +3.2%
        self.position_size_pct = 0.02  # 2% of equity
        
        # Track highest price for trailing stop
        self.highest_price = 0
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # Print summary every 200 bars
        if current_bar % 200 == 0 and current_bar > 0:
            print(f"[SUMMARY] Bar {current_bar}, Equity: ${self.equity:.2f}, Trades: {self.trade_count}")
        
        # Check for long entry signals
        if not self.position:
            long_signal = False
            
            # Check each enabled pattern for bullish reversal
            if self.enable_engulfing and self.cdl_engulfing[-1] == 100:
                long_signal = True
                pattern_name = "Engulfing"
            elif self.enable_hammer and self.cdl_hammer[-1] == 100:
                long_signal = True
                pattern_name = "Hammer"
            elif self.enable_doji and self.cdl_doji[-1] == 100:
                long_signal = True
                pattern_name = "Doji"
            elif self.enable_morningstar and self.cdl_morningstar[-1] == 100:
                long_signal = True
                pattern_name = "Morning Star"
            elif self.enable_eveningstar and self.cdl_eveningstar[-1] == -100:
                long_signal = True
                pattern_name = "Evening Star (bearish reversal)"
            
            if long_signal:
                # Calculate position size (capped at 10% of equity)
                position_size = min(self.position_size_pct, 0.10)
                
                # Execute buy order
                self.buy(size=position_size)
                self.trade_count += 1
                
                # Print every 10th trade
                if self.trade_count % 10 == 0:
                    print(f"[TRADE {self.trade_count}] {pattern_name} pattern detected at bar {current_bar}, size: {position_size*100:.2f}%")
                
                # Set initial stop loss
                entry_price = self.data.Close[-1]
                self.highest_price = entry_price
                stop_price = entry_price * (1 - self.initial_stop_loss)
                
        # Manage open position
        if self.position:
            current_price = self.data.Close[-1]
            
            # Update highest price
            if current_price > self.highest_price:
                self.highest_price = current_price
            
            # Check for exit signals (bearish patterns)
            exit_signal = False
            
            if self.enable_engulfing and self.cdl_engulfing[-1] == -100:
                exit_signal = True
                exit_reason = "Bearish Engulfing"
            elif self.enable_eveningstar and self.cdl_eveningstar[-1] == 100:
                exit_signal = True
                exit_reason = "Evening Star"
            elif self.enable_morningstar and self.cdl_morningstar[-1] == -100:
                exit_signal = True
                exit_reason = "Bearish Morning Star"
            
            # Check trailing stop conditions
            unrealized_gain = (current_price / self.position.entry_price) - 1
            
            if unrealized_gain >= self.trailing_activation:
                # Calculate trailing stop price
                trailing_stop_price = self.highest_price * (1 - self.trailing_offset)
                
                if current_price <= trailing_stop_price:
                    exit_signal = True
                    exit_reason = f"Trailing Stop at {trailing_stop_price:.2f}"
            
            # Check initial stop loss
            stop_price = self.position.entry_price * (1 - self.initial_stop_loss)
            if current_price <= stop_price:
                exit_signal = True
                exit_reason = f"Initial Stop Loss at {stop_price:.2f}"
            
            # Execute exit if any exit condition met
            if exit_signal:
                self.position.close()
                if self.trade_count % 10 == 0:
                    print(f"[EXIT {self.trade_count}] {exit_reason} at bar {current_bar}")

# Run backtest
bt = Backtest(price_data, PatternSync, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)