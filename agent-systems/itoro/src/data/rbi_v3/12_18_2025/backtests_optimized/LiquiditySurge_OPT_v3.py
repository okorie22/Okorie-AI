import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

class OptimizedLiquiditySurge(Strategy):
    liquidity_threshold = 35
    risk_per_trade = 0.02
    risk_reward_ratio = 2.0
    max_holding_bars = 8
    atr_multiplier = 1.2
    atr_period = 10
    rsi_period = 10
    rsi_overbought = 75
    rsi_oversold = 25
    ema_fast_period = 20
    ema_slow_period = 50
    volume_multiplier = 1.5
    min_volume_ratio = 1.2
    volatility_filter = 0.5
    
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
        
        self.volume_sma = self.I(
            talib.SMA,
            self.data.Volume,
            timeperiod=20,
            name='Volume_SMA'
        )
        
        self.entry_bar = 0
        self.position_direction = 0
        self.entry_price = 0
        
    def next(self):
        current_bar = len(self.data) - 1
        
        if current_bar < 50:
            return
            
        liquidity_change = self.liquidity_pct_change[-1]
        atr_value = self.atr[-1]
        rsi_value = self.rsi[-1]
        current_close = self.data.Close[-1]
        current_volume = self.data.Volume[-1]
        volume_sma_value = self.volume_sma[-1]
        ema_fast_value = self.ema_fast[-1]
        ema_slow_value = self.ema_slow[-1]
        
        if atr_value > 0:
            stop_distance = atr_value * self.atr_multiplier
            target_distance = stop_distance * self.risk_reward_ratio
        else:
            stop_distance = current_close * 0.008
            target_distance = stop_distance * self.risk_reward_ratio
        
        volatility_ratio = atr_value / current_close if current_close > 0 else 0
        
        if self.equity > 0 and stop_distance > 0:
            if volatility_ratio > self.volatility_filter:
                adjusted_risk = self.risk_per_trade * 0.5
            else:
                adjusted_risk = self.risk_per_trade
            
            risk_amount = self.equity * adjusted_risk
            position_size = risk_amount / stop_distance
            position_size = int(round(position_size))
        else:
            position_size = 100
            
        if position_size <= 0:
            position_size = 100
        
        volume_ratio = current_volume / volume_sma_value if volume_sma_value > 0 else 1
        
        if self.position:
            bars_held = current_bar - self.entry_bar
            
            if bars_held >= self.max_holding_bars:
                if self.position_direction == 1:
                    self.position.close()
                    self.position_direction = 0
                elif self.position_direction == -1:
                    self.position.close()
                    self.position_direction = 0
            
            trailing_stop_distance = atr_value * 1.0
            
            if self.position_direction == 1:
                new_stop = current_close - trailing_stop_distance
                if new_stop > self.position.sl:
                    self.position.sl = new_stop
                
                if liquidity_change > self.liquidity_threshold:
                    self.position.close()
                    self.position_direction = 0
                    
            elif self.position_direction == -1:
                new_stop = current_close + trailing_stop_distance
                if new_stop < self.position.sl:
                    self.position.sl = new_stop
                
                if liquidity_change < -self.liquidity_threshold:
                    self.position.close()
                    self.position_direction = 0
        
        if not self.position and volume_ratio >= self.min_volume_ratio:
            trend_filter = ema_fast_value > ema_slow_value
            
            if liquidity_change < -self.liquidity_threshold:
                if rsi_value < self.rsi_oversold:
                    if trend_filter:
                        stop_price = current_close - stop_distance
                        target_price = current_close + target_distance
                        
                        self.buy(size=position_size, sl=stop_price, tp=target_price)
                        self.entry_bar = current_bar
                        self.position_direction = 1
                        self.entry_price = current_close
                        
            elif liquidity_change > self.liquidity_threshold:
                if rsi_value > self.rsi_overbought:
                    if not trend_filter:
                        stop_price = current_close + stop_distance
                        target_price = current_close - target_distance
                        
                        self.sell(size=position_size, sl=stop_price, tp=target_price)
                        self.entry_bar = current_bar
                        self.position_direction = -1
                        self.entry_price = current_close