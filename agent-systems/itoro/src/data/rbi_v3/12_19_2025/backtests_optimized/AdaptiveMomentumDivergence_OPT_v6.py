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
    stop_loss_pct = 0.06
    min_holding_candles = 2
    atr_period = 14
    trend_filter_period = 50
    volume_filter_period = 20
    rsi_period = 14
    ema_fast = 8
    ema_slow = 21
    ema_trend = 50
    max_position_size = 0.3
    min_adx = 28
    rsi_oversold = 35
    rsi_overbought = 65
    macd_std_multiplier = 1.2
    trailing_atr_multiplier = 1.5
    profit_target_multiplier = 3.0
    max_daily_trades = 3
    min_price_distance = 0.02
    use_scaled_exits = True
    
    def init(self):
        self.ema_fast_line = self.I(talib.EMA, self.data.Close, timeperiod=self.ema_fast)
        self.ema_slow_line = self.I(talib.EMA, self.data.Close, timeperiod=self.ema_slow)
        self.ema_trend_line = self.I(talib.EMA, self.data.Close, timeperiod=self.ema_trend)
        self.universal_macd = (self.ema_fast_line / self.ema_slow_line) - 1
        self.macd_mean = self.I(talib.SMA, self.universal_macd, timeperiod=20)
        self.macd_std = self.I(talib.STDDEV, self.universal_macd, timeperiod=20)
        self.range_min = self.macd_mean - self.macd_std_multiplier * self.macd_std
        self.range_max = self.macd_mean - 0.05 * self.macd_std
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=self.atr_period)
        self.volume_sma = self.I(talib.SMA, self.data.Volume, timeperiod=self.volume_filter_period)
        self.rsi = self.I(talib.RSI, self.data.Close, timeperiod=self.rsi_period)
        self.adx = self.I(talib.ADX, self.data.High, self.data.Low, self.data.Close, timeperiod=14)
        self.plus_di = self.I(talib.PLUS_DI, self.data.High, self.data.Low, self.data.Close, timeperiod=14)
        self.minus_di = self.I(talib.MINUS_DI, self.data.High, self.data.Low, self.data.Close, timeperiod=14)
        self.supertrend_atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=10)
        self.supertrend_multiplier = 2.0
        self.candles_since_entry = 0
        self.entry_price = 0
        self.entry_macd = 0
        self.trailing_stop = 0
        self.initial_stop = 0
        self.position_size = 0
        self.trades_today = 0
        self.last_trade_day = None
        self.last_entry_price = 0
        
    def next(self):
        current_day = self.data.index[-1].date()
        if self.last_trade_day != current_day:
            self.trades_today = 0
            self.last_trade_day = current_day
        
        if self.position:
            self.candles_since_entry += 1
            current_price = self.data.Close[-1]
            atr_value = self.atr[-1]
            
            if self.candles_since_entry == 1:
                self.initial_stop = self.entry_price * (1 - self.stop_loss_pct)
                self.trailing_stop = self.initial_stop
            else:
                if current_price > self.entry_price:
                    new_trailing_stop = current_price - self.trailing_atr_multiplier * atr_value
                    if new_trailing_stop > self.trailing_stop:
                        self.trailing_stop = new_trailing_stop
            
            if current_price <= self.trailing_stop:
                self.position.close()
                self.candles_since_entry = 0
                self.trailing_stop = 0
                self.initial_stop = 0
                return
            
            if self.use_scaled_exits:
                self.execute_scaled_exits(current_price, atr_value)
            else:
                if self.candles_since_entry >= self.min_holding_candles:
                    current_macd = self.universal_macd[-1]
                    if current_macd >= 0:
                        self.position.close()
                        self.candles_since_entry = 0
                        self.trailing_stop = 0
                        self.initial_stop = 0
                        return
                
                if self.candles_since_entry >= 5:
                    roi_target = self.calculate_scaled_roi_target()
                    target_price = self.entry_price * (1 + roi_target)
                    
                    if current_price >= target_price:
                        self.position.close()
                        self.candles_since_entry = 0
                        self.trailing_stop = 0
                        self.initial_stop = 0
                        return
        
        if not self.position and self.trades_today < self.max_daily_trades:
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
            plus_di_val = self.plus_di[-1]
            minus_di_val = self.minus_di[-1]
            atr_value = self.atr[-1]
            
            volume_condition = current_volume > volume_sma_val * 1.5
            trend_condition = current_close > ema_trend_val
            rsi_condition = self.rsi_oversold <= current_rsi <= self.rsi_overbought
            adx_condition = adx_val > self.min_adx
            ema_alignment = ema_fast_val > ema_slow_val
            di_condition = plus_di_val > minus_di_val
            
            price_distance_condition = abs(current_close - self.last_entry_price) / self.last_entry_price > self.min_price_distance if self.last_entry_price > 0 else True
            
            supertrend_up = self.calculate_supertrend(current_close, atr_value)
            
            if range_min_val <= current_macd <= range_max_val:
                if volume_condition and trend_condition and rsi_condition and adx_condition and ema_alignment and di_condition and price_distance_condition and supertrend_up:
                    volatility_adjusted_risk = min(self.risk_per_trade * (10 / atr_value), 0.15)
                    stop_distance = current_close * self.stop_loss_pct
                    risk_amount = self.equity * volatility_adjusted_risk
                    position_size = risk_amount / stop_distance
                    position_size = min(position_size, self.max_position_size)
                    
                    self.buy(size=position_size)
                    self.entry_price = current_close
                    self.entry_macd = current_macd
                    self.last_entry_price = current_close
                    self.candles_since_entry = 0
                    self.trailing_stop = 0
                    self.initial_stop = 0
                    self.trades_today += 1
    
    def calculate_scaled_roi_target(self):
        candles = self.candles_since_entry
        atr_value = self.atr[-1]
        atr_ratio = atr_value / self.entry_price
        
        base_target = atr_ratio * self.profit_target_multiplier
        
        if candles <= 0:
            return max(base_target, 0.30)
        if candles <= 8:
            decay_factor = (candles / 8) * 0.20
            return max(base_target, 0.30 - decay_factor)
        if candles <= 20:
            decay_factor = 0.20 + ((candles - 8) / 12) * 0.15
            return max(base_target, 0.15 - decay_factor)
        if candles <= 40:
            decay_factor = 0.35 + ((candles - 20) / 20) * 0.10
            return max(base_target, 0.08 - decay_factor)
        return max(base_target, 0.04)
    
    def calculate_supertrend(self, current_close, atr_value):
        hl2 = (self.data.High[-1] + self.data.Low[-1]) / 2
        upper_band = hl2 + (self.supertrend_multiplier * atr_value)
        lower_band = hl2 - (self.supertrend_multiplier * atr_value)
        
        if len(self.data.Close) > 1:
            prev_close = self.data.Close[-2]
            if current_close > lower_band and prev_close > lower_band:
                return True
        return current_close > lower_band
    
    def execute_scaled_exits(self, current_price, atr_value):
        if self.candles_since_entry < 3:
            return
        
        position_size = self.position.size
        profit_pct = (current_price - self.entry_price) / self.entry_price
        
        if profit_pct >= 0.015 and position_size > 0.1:
            exit_size = min(position_size * 0.3, position_size - 0.05)
            self.position.close(portion=exit_size)
        
        if profit_pct >= 0.03 and position_size > 0.05:
            exit_size = min(position_size * 0.4, position_size)
            self.position.close(portion=exit_size)
        
        if profit_pct >= 0.05:
            self.position.close()
            self.candles_since_entry = 0
            self.trailing_stop = 0
            self.initial_stop = 0
        
        if profit_pct <= -0.04:
            self.position.close()
            self.candles_since_entry = 0
            self.trailing_stop = 0
            self.initial_stop = 0

bt = Backtest(price_data, AdaptiveMomentumDivergence, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)