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
    stop_loss_pct = 0.08
    min_holding_candles = 3
    atr_period = 14
    trend_filter_period = 50
    volume_filter_period = 20
    rsi_period = 14
    ema_fast = 5
    ema_slow = 13
    ema_trend = 34
    bb_period = 20
    bb_std = 2.0
    adx_threshold = 25
    rsi_oversold = 40
    rsi_overbought = 60
    volume_multiplier = 1.3
    macd_signal_period = 9
    macd_fast = 12
    macd_slow = 26
    
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
        self.bb_upper, self.bb_middle, self.bb_lower = self.I(talib.BBANDS, self.data.Close, timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std)
        self.macd_line, self.macd_signal, self.macd_hist = self.I(talib.MACD, self.data.Close, fastperiod=self.macd_fast, slowperiod=self.macd_slow, signalperiod=self.macd_signal_period)
        self.candles_since_entry = 0
        self.entry_price = 0
        self.entry_macd = 0
        self.trailing_stop = 0
        self.position_size = 0
        self.highest_price = 0
        
    def next(self):
        if self.position:
            self.candles_since_entry += 1
            current_price = self.data.Close[-1]
            atr_value = self.atr[-1]
            
            if current_price > self.highest_price:
                self.highest_price = current_price
            
            if self.candles_since_entry == 1:
                initial_stop = self.entry_price * (1 - self.stop_loss_pct)
                self.trailing_stop = max(initial_stop, self.entry_price - 2.0 * atr_value)
            else:
                if current_price > self.entry_price:
                    dynamic_trailing_distance = 1.2 * atr_value
                    new_trailing_stop = current_price - dynamic_trailing_distance
                    if new_trailing_stop > self.trailing_stop:
                        self.trailing_stop = new_trailing_stop
                
                if self.candles_since_entry >= 10:
                    if current_price > self.entry_price * 1.05:
                        tighter_trailing = current_price - 0.8 * atr_value
                        if tighter_trailing > self.trailing_stop:
                            self.trailing_stop = tighter_trailing
            
            if current_price <= self.trailing_stop:
                self.position.close()
                self.candles_since_entry = 0
                self.trailing_stop = 0
                self.highest_price = 0
                return
            
            roi_target = self.calculate_scaled_roi_target()
            target_price = self.entry_price * (1 + roi_target)
            
            if current_price >= target_price:
                self.position.close()
                self.candles_since_entry = 0
                self.trailing_stop = 0
                self.highest_price = 0
                return
            
            if self.candles_since_entry >= self.min_holding_candles:
                current_macd = self.universal_macd[-1]
                macd_hist_val = self.macd_hist[-1]
                
                if current_macd >= 0 or macd_hist_val < 0:
                    self.position.close()
                    self.candles_since_entry = 0
                    self.trailing_stop = 0
                    self.highest_price = 0
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
            bb_lower_val = self.bb_lower[-1]
            macd_hist_val = self.macd_hist[-1]
            macd_line_val = self.macd_line[-1]
            macd_signal_val = self.macd_signal[-1]
            
            volume_condition = current_volume > volume_sma_val * self.volume_multiplier
            trend_condition = current_close > ema_trend_val
            rsi_condition = self.rsi_oversold <= current_rsi <= self.rsi_overbought
            adx_condition = adx_val > self.adx_threshold
            ema_alignment = ema_fast_val > ema_slow_val
            bb_condition = current_close > bb_lower_val
            macd_bullish = macd_line_val > macd_signal_val and macd_hist_val > 0
            
            if range_min_val <= current_macd <= range_max_val:
                if volume_condition and trend_condition and rsi_condition and adx_condition and ema_alignment and bb_condition and macd_bullish:
                    atr_value = self.atr[-1]
                    volatility_adjusted_risk = min(self.risk_per_trade * (20 / max(atr_value, 0.0001)), 0.10)
                    stop_distance = max(current_close * 0.08, 1.5 * atr_value)
                    risk_amount = self.equity * volatility_adjusted_risk
                    position_size = risk_amount / stop_distance
                    position_size = min(position_size, 0.20)
                    
                    self.buy(size=position_size)
                    self.entry_price = current_close
                    self.entry_macd = current_macd
                    self.candles_since_entry = 0
                    self.trailing_stop = 0
                    self.highest_price = current_close
    
    def calculate_scaled_roi_target(self):
        candles = self.candles_since_entry
        if candles <= 0:
            return 0.35
        if candles <= 10:
            return 0.35 - (candles / 10) * (0.35 - 0.20)
        if candles <= 25:
            return 0.20 - ((candles - 10) / 15) * (0.20 - 0.12)
        if candles <= 50:
            return 0.12 - ((candles - 25) / 25) * (0.12 - 0.06)
        if candles <= 100:
            return 0.06 - ((candles - 50) / 50) * 0.06
        return 0.0

bt = Backtest(price_data, AdaptiveMomentumDivergence, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)