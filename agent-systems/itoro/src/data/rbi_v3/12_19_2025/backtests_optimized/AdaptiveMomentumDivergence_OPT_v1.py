import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
price_data.columns = price_data.columns.str.strip().str.lower()
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])
required_columns = {'open', 'high', 'low', 'close', 'volume'}
available_columns = set(price_data.columns)
if not required_columns.issubset(available_columns):
    raise ValueError("Missing required OHLCV columns")
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

class AdaptiveMomentumDivergence(Strategy):
    risk_per_trade = 0.02
    stop_loss_pct = 0.15
    min_holding_candles = 3
    atr_period = 14
    trend_filter_period = 50
    volume_filter_period = 20
    
    def init(self):
        self.ema12 = self.I(talib.EMA, self.data.Close, timeperiod=12)
        self.ema26 = self.I(talib.EMA, self.data.Close, timeperiod=26)
        self.ema50 = self.I(talib.EMA, self.data.Close, timeperiod=self.trend_filter_period)
        self.universal_macd = (self.ema12 / self.ema26) - 1
        self.macd_mean = self.I(talib.SMA, self.universal_macd, timeperiod=20)
        self.macd_std = self.I(talib.STDDEV, self.universal_macd, timeperiod=20)
        self.range_min = self.macd_mean - 1.2 * self.macd_std
        self.range_max = self.macd_mean - 0.3 * self.macd_std
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=self.atr_period)
        self.volume_sma = self.I(talib.SMA, self.data.Volume, timeperiod=self.volume_filter_period)
        self.rsi = self.I(talib.RSI, self.data.Close, timeperiod=14)
        self.candles_since_entry = 0
        self.entry_price = 0
        self.entry_macd = 0
        self.trailing_stop = 0
        
    def next(self):
        if self.position:
            self.candles_since_entry += 1
            current_price = self.data.Close[-1]
            atr_value = self.atr[-1]
            
            if self.candles_since_entry == 1:
                initial_stop = self.entry_price * (1 - self.stop_loss_pct)
                self.trailing_stop = initial_stop
            else:
                if current_price > self.entry_price:
                    new_trailing_stop = current_price - 2 * atr_value
                    if new_trailing_stop > self.trailing_stop:
                        self.trailing_stop = new_trailing_stop
            
            if current_price <= self.trailing_stop:
                self.position.close()
                self.candles_since_entry = 0
                self.trailing_stop = 0
                return
            
            roi_target = self.calculate_scaled_roi_target()
            target_price = self.entry_price * (1 + roi_target)
            
            if current_price >= target_price:
                self.position.close()
                self.candles_since_entry = 0
                self.trailing_stop = 0
                return
            
            if self.candles_since_entry >= self.min_holding_candles:
                current_macd = self.universal_macd[-1]
                if -0.015 <= current_macd <= -0.005:
                    self.position.close()
                    self.candles_since_entry = 0
                    self.trailing_stop = 0
                    return
        
        if not self.position:
            current_macd = self.universal_macd[-1]
            range_min_val = self.range_min[-1]
            range_max_val = self.range_max[-1]
            current_volume = self.data.Volume[-1]
            volume_sma_val = self.volume_sma[-1]
            current_rsi = self.rsi[-1]
            current_close = self.data.Close[-1]
            ema50_val = self.ema50[-1]
            
            volume_condition = current_volume > volume_sma_val * 0.8
            trend_condition = current_close > ema50_val
            rsi_condition = 30 <= current_rsi <= 70
            
            if range_min_val <= current_macd <= range_max_val:
                if volume_condition and trend_condition and rsi_condition:
                    atr_value = self.atr[-1]
                    volatility_adjusted_risk = min(self.risk_per_trade * (20 / atr_value), 0.05)
                    stop_distance = current_close * 0.15
                    risk_amount = self.equity * volatility_adjusted_risk
                    position_size = risk_amount / stop_distance
                    position_size = min(position_size, 0.1)
                    
                    self.buy(size=position_size)
                    self.entry_price = current_close
                    self.entry_macd = current_macd
                    self.candles_since_entry = 0
                    self.trailing_stop = 0
    
    def calculate_scaled_roi_target(self):
        candles = self.candles_since_entry
        if candles <= 0:
            return 0.25
        if candles <= 20:
            return 0.25 - (candles / 20) * (0.25 - 0.12)
        if candles <= 50:
            return 0.12 - ((candles - 20) / 30) * (0.12 - 0.05)
        if candles <= 100:
            return 0.05 - ((candles - 50) / 50) * 0.05
        return 0.0

bt = Backtest(price_data, AdaptiveMomentumDivergence, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)