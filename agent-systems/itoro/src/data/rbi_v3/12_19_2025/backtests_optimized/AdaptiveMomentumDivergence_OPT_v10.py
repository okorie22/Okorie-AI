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
    min_holding_candles = 3
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
    rsi_exit_threshold = 70
    min_volume_multiplier = 1.5
    max_holding_candles = 40
    scale_out_candles = [10, 20]
    scale_out_percentages = [0.5, 0.3]
    
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
        self.candles_since_entry = 0
        self.entry_price = 0
        self.entry_macd = 0
        self.trailing_stop = 0
        self.position_size = 0
        self.initial_stop = 0
        self.scaled_out = False
        self.scale_out_levels = []
        
    def next(self):
        if self.position:
            self.candles_since_entry += 1
            current_price = self.data.Close[-1]
            atr_value = self.atr[-1]
            current_rsi = self.rsi[-1]
            
            if self.candles_since_entry == 1:
                self.initial_stop = self.entry_price * (1 - self.stop_loss_pct)
                self.trailing_stop = self.initial_stop
                self.scaled_out = False
                self.scale_out_levels = []
            else:
                if current_price > self.entry_price:
                    new_trailing_stop = current_price - self.trailing_atr_multiplier * atr_value
                    if new_trailing_stop > self.trailing_stop:
                        self.trailing_stop = new_trailing_stop
            
            if current_rsi >= self.rsi_exit_threshold:
                self.position.close()
                self.reset_trade_vars()
                return
            
            if current_price <= self.trailing_stop:
                self.position.close()
                self.reset_trade_vars()
                return
            
            if self.candles_since_entry >= self.min_holding_candles:
                current_macd = self.universal_macd[-1]
                if current_macd >= 0.005:
                    self.position.close()
                    self.reset_trade_vars()
                    return
            
            if not self.scaled_out and self.candles_since_entry >= self.scale_out_candles[0]:
                for i, candle_threshold in enumerate(self.scale_out_candles):
                    if self.candles_since_entry >= candle_threshold and i not in self.scale_out_levels:
                        scale_out_pct = self.scale_out_percentages[i]
                        if self.position.size > 0:
                            close_size = self.position.size * scale_out_pct
                            self.position.close(close_size)
                            self.scale_out_levels.append(i)
                            if i == len(self.scale_out_candles) - 1:
                                self.scaled_out = True
            
            if self.candles_since_entry >= self.max_holding_candles:
                self.position.close()
                self.reset_trade_vars()
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
            plus_di_val = self.plus_di[-1]
            minus_di_val = self.minus_di[-1]
            prev_macd = self.universal_macd[-2] if len(self.universal_macd) > 1 else current_macd
            
            volume_condition = current_volume > volume_sma_val * self.min_volume_multiplier
            trend_condition = current_close > ema_trend_val * 1.01
            rsi_condition = self.rsi_oversold <= current_rsi <= self.rsi_overbought
            adx_condition = adx_val > self.min_adx
            ema_alignment = ema_fast_val > ema_slow_val * 1.005
            di_condition = plus_di_val > minus_di_val * 1.1
            macd_turning = current_macd > prev_macd and current_macd < 0
            
            if range_min_val <= current_macd <= range_max_val and macd_turning:
                if volume_condition and trend_condition and rsi_condition and adx_condition and ema_alignment and di_condition:
                    atr_value = self.atr[-1]
                    atr_ratio = atr_value / current_close
                    volatility_factor = max(0.5, min(2.0, 0.1 / atr_ratio))
                    adjusted_risk = self.risk_per_trade * volatility_factor
                    stop_distance = current_close * self.stop_loss_pct
                    risk_amount = self.equity * adjusted_risk
                    position_size = risk_amount / stop_distance
                    position_size = min(position_size, self.max_position_size)
                    
                    if position_size > 0:
                        self.buy(size=position_size)
                        self.entry_price = current_close
                        self.entry_macd = current_macd
                        self.candles_since_entry = 0
                        self.trailing_stop = 0
                        self.initial_stop = 0
                        self.scaled_out = False
                        self.scale_out_levels = []
    
    def calculate_scaled_roi_target(self):
        candles = self.candles_since_entry
        atr_value = self.atr[-1]
        atr_ratio = atr_value / self.entry_price
        
        base_target = atr_ratio * self.profit_target_multiplier
        
        if candles <= 0:
            return max(base_target, 0.3)
        if candles <= 15:
            decay_factor = (candles / 15) * 0.2
            return max(base_target, 0.3 - decay_factor)
        if candles <= 30:
            decay_factor = 0.2 + ((candles - 15) / 15) * 0.15
            return max(base_target, 0.15 - decay_factor)
        return max(base_target, 0.05)
    
    def reset_trade_vars(self):
        self.candles_since_entry = 0
        self.trailing_stop = 0
        self.initial_stop = 0
        self.scaled_out = False
        self.scale_out_levels = []

bt = Backtest(price_data, AdaptiveMomentumDivergence, cash=1000000, commission=.002)
stats = bt.run()
print(stats)
print(stats._strategy)