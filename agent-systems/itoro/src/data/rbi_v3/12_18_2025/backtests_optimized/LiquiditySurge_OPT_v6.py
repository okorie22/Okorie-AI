import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
price_data.columns = price_data.columns.str.strip().str.lower()
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])
required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
for col in required_cols:
    if col not in price_data.columns:
        raise ValueError(f"Missing required column: {col}")
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')
price_data = price_data.sort_index()
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})
if 'open_interest' not in price_data.columns and 'oi' not in price_data.columns:
    price_data['Open_Interest'] = 0
elif 'oi' in price_data.columns:
    price_data = price_data.rename(columns={'oi': 'Open_Interest'})
elif 'open_interest' in price_data.columns:
    price_data = price_data.rename(columns={'open_interest': 'Open_Interest'})

class LiquiditySurge(Strategy):
    liquidity_threshold = 50
    risk_per_trade = 0.02
    risk_reward_ratio = 2.0
    max_holding_bars = 15
    atr_multiplier = 1.2
    atr_period = 14
    rsi_period = 14
    rsi_overbought = 75
    rsi_oversold = 25
    ema_fast_period = 9
    ema_slow_period = 21
    volume_ma_period = 20
    min_volume_multiplier = 1.5
    trend_filter = True
    
    def init(self):
        avg_price = (self.data.High + self.data.Low + self.data.Close) / 3
        liquidity = self.data.Volume * avg_price
        liquidity_np = np.array(liquidity)
        liquidity_pct_change = np.zeros_like(liquidity_np)
        for i in range(1, len(liquidity_np)):
            if liquidity_np[i-1] != 0:
                liquidity_pct_change[i] = (liquidity_np[i] / liquidity_np[i-1] - 1) * 100
        self.liquidity_pct_change = self.I(
            lambda: liquidity_pct_change,
            name='Liquidity_Pct_Change'
        )
        self.atr = self.I(
            talib.ATR,
            self.data.High,
            self.data.Low,
            self.data.Close,
            timeperiod=self.atr_period,
            name='ATR'
        )
        self.rsi = self.I(
            talib.RSI,
            self.data.Close,
            timeperiod=self.rsi_period,
            name='RSI'
        )
        self.ema_fast = self.I(
            talib.EMA,
            self.data.Close,
            timeperiod=self.ema_fast_period,
            name='EMA_Fast'
        )
        self.ema_slow = self.I(
            talib.EMA,
            self.data.Close,
            timeperiod=self.ema_slow_period,
            name='EMA_Slow'
        )
        self.volume_ma = self.I(
            talib.SMA,
            self.data.Volume,
            timeperiod=self.volume_ma_period,
            name='Volume_MA'
        )
        self.entry_bar = 0
        self.position_direction = 0
        
    def next(self):
        current_bar = len(self.data) - 1
        if current_bar < max(self.atr_period, self.volume_ma_period, self.ema_slow_period):
            return
            
        liquidity_change = self.liquidity_pct_change[-1]
        atr_value = self.atr[-1]
        rsi_value = self.rsi[-1]
        current_close = self.data.Close[-1]
        current_volume = self.data.Volume[-1]
        volume_ma = self.volume_ma[-1]
        ema_fast = self.ema_fast[-1]
        ema_slow = self.ema_slow[-1]
        
        if atr_value > 0:
            stop_distance = atr_value * self.atr_multiplier
            target_distance = stop_distance * self.risk_reward_ratio
        else:
            stop_distance = current_close * 0.01
            target_distance = stop_distance * self.risk_reward_ratio
        
        if self.equity > 0 and stop_distance > 0:
            risk_amount = self.equity * self.risk_per_trade
            position_size = risk_amount / stop_distance
            position_size = int(round(position_size))
        else:
            position_size = 100
            
        if position_size <= 0:
            position_size = 100
        
        volume_filter = current_volume > volume_ma * self.min_volume_multiplier
        
        if self.position:
            bars_held = current_bar - self.entry_bar
            if bars_held >= self.max_holding_bars:
                if self.position_direction == 1:
                    print(f"Time exit long after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
                elif self.position_direction == -1:
                    print(f"Time exit short after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
            
            if self.position_direction == 1 and liquidity_change > self.liquidity_threshold:
                print("Contrary exit long")
                self.position.close()
                self.position_direction = 0
            elif self.position_direction == -1 and liquidity_change < -self.liquidity_threshold:
                print("Contrary exit short")
                self.position.close()
                self.position_direction = 0
        
        if not self.position and volume_filter:
            trend_aligned_long = not self.trend_filter or (ema_fast > ema_slow)
            trend_aligned_short = not self.trend_filter or (ema_fast < ema_slow)
            
            if liquidity_change < -self.liquidity_threshold and trend_aligned_long:
                if rsi_value < self.rsi_oversold:
                    print(f"LONG: Liquidity {liquidity_change:.2f}%, RSI {rsi_value:.2f}")
                    stop_price = current_close - stop_distance
                    target_price = current_close + target_distance
                    self.buy(size=position_size, sl=stop_price, tp=target_price)
                    self.entry_bar = current_bar
                    self.position_direction = 1
                    print(f"Size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")
            
            elif liquidity_change > self.liquidity_threshold and trend_aligned_short:
                if rsi_value > self.rsi_overbought:
                    print(f"SHORT: Liquidity {liquidity_change:.2f}%, RSI {rsi_value:.2f}")
                    stop_price = current_close + stop_distance
                    target_price = current_close - target_distance
                    self.sell(size=position_size, sl=stop_price, tp=target_price)
                    self.entry_bar = current_bar
                    self.position_direction = -1
                    print(f"Size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")

print("Starting backtest...")
bt = Backtest(
    price_data,
    LiquiditySurge,
    cash=1000000,
    commission=0.001,
    exclusive_orders=True
)
stats = bt.run()
print("BACKTEST RESULTS")
print(stats)
print("STRATEGY DETAILS")
print(stats._strategy)