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
    stop_loss_pct = 0.10
    min_holding_candles = 3
    atr_period = 14
    trend_filter_period = 50
    volume_filter_period = 20
    rsi_period = 14
    ema_fast = 8
    ema_slow = 21
    ema_trend = 50
    
    def init(self):
        self.ema_fast_line = self.I(talib.EMA, self.data.Close, timeperiod=self.ema_fast)
        self.ema_slow_line = self.I(talib.EMA, self.data.Close, timeperiod=self.ema_slow)
        self.ema_trend_line = self.I(talib.EMA, self.data.Close, timeperiod=self.ema_trend)
        self.universal_macd = (self.ema_fast_line / self.ema_slow_line) - 1
        self.macd_mean = self.I(talib.SMA, self.universal_macd, timeperiod=20)
        self.macd_std = self.I(talib.STDDEV, self.universal_macd, timeperiod=20)
        self.range_min = self.macd_mean - 1.0 * self.macd_std
        self.range_max = self.macd_mean - 0.2 * self.macd_std
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=self.atr_period)
        self.volume_sma = self.I(talib.SMA, self.data.Volume, timeperiod=self.volume_filter_period)
        self.rsi = self.I(talib.RSI, self.data.Close, timeperiod=self.rsi_period)
        self.adx = self.I(talib.ADX, self.data.High, self.data.Low, self.data.Close, timeperiod=14)
        self.candles_since_entry = 0
        self.entry_price = 0
        self.entry_macd = 0
        self.trailing_stop = 0
        self.position_size = 0
        
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
                    new_trailing_stop = current_price - 1.5 * atr_value
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
                if current_macd >= 0:
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
            ema_trend_val = self.ema_trend_line[-1]
            adx_val = self.adx[-1]
            ema_fast_val = self.ema_fast_line[-1]
            ema_slow_val = self.ema_slow_line[-1]
            
            volume_condition = current_volume > volume_sma_val * 1.2
            trend_condition = current_close > ema_trend_val
            rsi_condition = 35 <= current_rsi <= 65
            adx_condition = adx_val > 25
            ema_alignment = ema_fast_val > ema_slow_val
            
            if range_min_val <= current_macd <= range_max_val:
                if volume_condition and trend_condition and rsi_condition and adx_condition and ema_alignment:
                    atr_value = self.atr[-1]
                    volatility_adjusted_risk = min(self.risk_per_trade * (15 / atr_value), 0.08)
                    stop_distance = current_close * 0.10
                    risk_amount = self.equity * volatility_adjusted_risk
                    position_size = risk_amount / stop_distance
                    position_size = min(position_size, 0.15)
                    
                    self.buy(size=position_size)
                    self.entry_price = current_close
                    self.entry_macd = current_macd
                    self.candles_since_entry = 0
                    self.trailing_stop = 0
    
    def calculate_scaled_roi_target(self):
        candles = self.candles_since_entry
        if candles <= 0:
            return 0.30
        if candles <= 15:
            return 0.30 - (candles / 15) * (0.30 - 0.15)
        if candles <= 40:
            return 0.15 - ((candles - 15) / 25) * (0.15 - 0.08)
        if candles <= 80:
            return 0.08 - ((candles - 40) / 40) * 0.08
        return 0.0

bt = Backtest(price_data, AdaptiveMomentumDivergence, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)