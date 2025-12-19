import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

# Load and prepare data
print("[INFO] Loading OHLCV data...")
price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()

# Drop unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Ensure required columns exist
required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
for col in required_cols:
    if col not in price_data.columns:
        raise ValueError(f"Missing required column: {col}")

# Set datetime index
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')

# Sort by timestamp
price_data = price_data.sort_index()

# Rename columns to match backtesting.py requirements
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

# Add open_interest column if not present
if 'open_interest' not in price_data.columns and 'oi' not in price_data.columns:
    price_data['Open_Interest'] = 0
elif 'oi' in price_data.columns:
    price_data = price_data.rename(columns={'oi': 'Open_Interest'})
elif 'open_interest' in price_data.columns:
    price_data = price_data.rename(columns={'open_interest': 'Open_Interest'})

print(f"[INFO] Data loaded: {len(price_data)} rows")
print(f"[INFO] Data columns: {list(price_data.columns)}")
print(f"[INFO] Data date range: {price_data.index[0]} to {price_data.index[-1]}")

class LiquiditySurge(Strategy):
    # Strategy parameters - OPTIMIZED
    liquidity_threshold = 50  # Increased to 50% for stronger signals
    risk_per_trade = 0.02  # Increased to 2% for higher returns
    risk_reward_ratio = 2.0  # Increased to 1:2 for better reward
    max_holding_bars = 8  # Reduced to 8 bars for quicker exits
    atr_multiplier = 1.2  # Reduced for tighter stops
    atr_period = 10  # Reduced for more responsive ATR
    rsi_period = 10  # Reduced for more responsive RSI
    rsi_overbought = 75  # Increased to avoid false overbought signals
    rsi_oversold = 25  # Decreased to avoid false oversold signals
    
    # New parameters for optimization
    volume_multiplier = 1.5  # Volume filter multiplier
    min_volume_threshold = 1.2  # Minimum volume relative to average
    trend_filter_period = 20  # EMA period for trend filter
    volatility_filter_period = 20  # Period for volatility filter
    min_volatility_multiplier = 0.5  # Minimum volatility threshold
    trailing_stop_activation = 0.5  # Activate trailing stop at 0.5x target
    trailing_stop_distance = 0.8  # Trailing stop distance from ATR
    
    def init(self):
        # Calculate liquidity: Volume * Average Price ((H+L+C)/3)
        avg_price = (self.data.High + self.data.Low + self.data.Close) / 3
        liquidity = self.data.Volume * avg_price
        
        # Calculate liquidity percentage change using numpy operations
        liquidity_np = np.array(liquidity)
        liquidity_pct_change = np.zeros_like(liquidity_np)
        
        # Calculate percentage change manually
        for i in range(1, len(liquidity_np)):
            if liquidity_np[i-1] != 0:
                liquidity_pct_change[i] = (liquidity_np[i] / liquidity_np[i-1] - 1) * 100
        
        self.liquidity_pct_change = self.I(
            lambda: liquidity_pct_change,
            name='Liquidity_Pct_Change'
        )
        
        # Calculate ATR for stop loss
        self.atr = self.I(
            talib.ATR,
            self.data.High,
            self.data.Low,
            self.data.Close,
            timeperiod=self.atr_period,
            name='ATR'
        )
        
        # Calculate RSI for confirmation
        self.rsi = self.I(
            talib.RSI,
            self.data.Close,
            timeperiod=self.rsi_period,
            name='RSI'
        )
        
        # Calculate EMA for trend filter
        self.ema = self.I(
            talib.EMA,
            self.data.Close,
            timeperiod=self.trend_filter_period,
            name='EMA'
        )
        
        # Calculate volume SMA for volume filter
        self.volume_sma = self.I(
            talib.SMA,
            self.data.Volume,
            timeperiod=20,
            name='Volume_SMA'
        )
        
        # Calculate volatility (standard deviation)
        self.volatility = self.I(
            talib.STDDEV,
            self.data.Close,
            timeperiod=self.volatility_filter_period,
            name='Volatility'
        )
        
        # Calculate price position relative to EMA
        self.price_vs_ema = self.I(
            lambda: (self.data.Close / self.ema - 1) * 100,
            name='Price_vs_EMA'
        )
        
        # Track entry bars for time-based exit
        self.entry_bar = 0
        self.entry_price = 0
        self.initial_stop = 0
        self.initial_target = 0
        
        # Track current position direction
        self.position_direction = 0  # 0: no position, 1: long, -1: short
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # Check if we have enough data
        if current_bar < max(self.atr_period, self.rsi_period, self.trend_filter_period) + 5:
            return
            
        # Get current values using array indexing
        liquidity_change = self.liquidity_pct_change[-1]
        atr_value = self.atr[-1]
        rsi_value = self.rsi[-1]
        current_close = self.data.Close[-1]
        current_volume = self.data.Volume[-1]
        volume_sma_value = self.volume_sma[-1] if self.volume_sma[-1] > 0 else 1
        ema_value = self.ema[-1]
        volatility_value = self.volatility[-1]
        avg_volatility = np.mean(self.volatility[-self.volatility_filter_period:]) if len(self.volatility) >= self.volatility_filter_period else volatility_value
        
        # Calculate volume ratio
        volume_ratio = current_volume / volume_sma_value
        
        # Calculate stop loss and take profit distances
        if atr_value > 0:
            stop_distance = atr_value * self.atr_multiplier
            target_distance = stop_distance * self.risk_reward_ratio
        else:
            stop_distance = current_close * 0.01
            target_distance = stop_distance * self.risk_reward_ratio
        
        # Dynamic position sizing based on volatility and signal strength
        volatility_factor = max(0.5, min(2.0, avg_volatility / (volatility_value + 0.0001)))
        signal_strength = min(2.0, abs(liquidity_change) / self.liquidity_threshold)
        
        # Calculate position size based on risk with dynamic adjustments
        if self.equity > 0 and stop_distance > 0:
            base_risk_amount = self.equity * self.risk_per_trade
            adjusted_risk = base_risk_amount * volatility_factor * signal_strength
            position_size = adjusted_risk / stop_distance
            position_size = int(round(position_size))
        else:
            position_size = 100
            
        # Ensure position size is valid
        if position_size <= 0:
            position_size = 100
        
        # Check for exit conditions
        if self.position:
            bars_held = current_bar - self.entry_bar
            current_pnl = (current_close - self.entry_price) / self.entry_price * 100 if self.position_direction == 1 else (self.entry_price - current_close) / self.entry_price * 100
            
            # Time-based exit
            if bars_held >= self.max_holding_bars:
                if self.position_direction == 1:
                    print(f"[EXIT] Time-based exit for long position after {bars_held} bars, PnL: {current_pnl:.2f}%")
                    self.position.close()
                    self.position_direction = 0
                elif self.position_direction == -1:
                    print(f"[EXIT] Time-based exit for short position after {bars_held} bars, PnL: {current_pnl:.2f}%")
                    self.position.close()
                    self.position_direction = 0
            
            # Trailing stop logic
            if self.position_direction == 1:
                # Calculate profit from entry
                profit_distance = current_close - self.entry_price
                target_profit = self.initial_target - self.entry_price
                
                # Activate trailing stop when 50% of target is reached
                if profit_distance >= target_profit * self.trailing_stop_activation:
                    trailing_stop = current_close - atr_value * self.trailing_stop_distance
                    if trailing_stop > self.position.sl:
                        self.position.sl = trailing_stop
            
            elif self.position_direction == -1:
                # Calculate profit from entry
                profit_distance = self.entry_price - current_close
                target_profit = self.entry_price - self.initial_target
                
                # Activate trailing stop when 50% of target is reached
                if profit_distance >= target_profit * self.trailing_stop_activation:
                    trailing_stop = current_close + atr_value * self.trailing_stop_distance
                    if trailing_stop < self.position.sl:
                        self.position.sl = trailing_stop
            
            # Contrary signal exit with stronger conditions
            if self.position_direction == 1:
                if liquidity_change > self.liquidity_threshold * 1.2 and rsi_value > self.rsi_overbought:
                    print(f"[EXIT] Strong contrary signal exit for long position, Liquidity: {liquidity_change:.2f}%, RSI: {rsi_value:.2f}")
                    self.position.close()
                    self.position_direction = 0
            elif self.position_direction == -1:
                if liquidity_change < -self.liquidity_threshold * 1.2 and rsi_value < self.rsi_oversold:
                    print(f"[EXIT] Strong contrary signal exit for short position, Liquidity: {liquidity_change:.2f}%, RSI: {rsi_value:.2f}")
                    self.position.close()
                    self.position_direction = 0
        
        # Check for entry signals (only if no position)
        if not self.position:
            # Market regime filters
            # Avoid low volatility periods
            if volatility_value < avg_volatility * self.min_volatility_multiplier:
                return
                
            # Volume filter - require above average volume
            if volume_ratio < self.min_volume_threshold:
                return
            
            # Long entry: liquidity drop < -50% (capitulation) with stronger filters
            if liquidity_change < -self.liquidity_threshold:
                # Stronger RSI confirmation (oversold)
                if rsi_value < self.rsi_oversold:
                    # Trend filter - price should be below EMA for better long entries
                    price_below_ema = current_close < ema_value * 1.02
                    
                    if price_below_ema:
                        print(f"[LONG] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}, Volume ratio: {volume_ratio:.2f}")
                        
                        # Calculate stop and target prices
                        stop_price = current_close - stop_distance
                        target_price = current_close + target_distance
                        
                        # Enter long position
                        self.buy(size=position_size, sl=stop_price, tp=target_price)
                        self.entry_bar = current_bar
                        self.entry_price = current_close
                        self.initial_stop = stop_price
                        self.initial_target = target_price
                        self.position_direction = 1
                        print(f"[LONG] Position size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")
            
            # Short entry: liquidity spike > +50% (euphoric buying) with stronger filters
            elif liquidity_change > self.liquidity_threshold:
                # Stronger RSI confirmation (overbought)
                if rsi_value > self.rsi_overbought:
                    # Trend filter - price should be above EMA for better short entries
                    price_above_ema = current_close > ema_value * 0.98
                    
                    if price_above_ema:
                        print(f"[SHORT] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}, Volume ratio: {volume_ratio:.2f}")
                        
                        # Calculate stop and target prices
                        stop_price = current_close + stop_distance
                        target_price = current_close - target_distance
                        
                        # Enter short position
                        self.sell(size=position_size, sl=stop_price, tp=target_price)
                        self.entry_bar = current_bar
                        self.entry_price = current_close
                        self.initial_stop = stop_price
                        self.initial_target = target_price
                        self.position_direction = -1
                        print(f"[SHORT] Position size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")

# Run backtest
print("\n[INFO] Starting backtest...")
bt = Backtest(
    price_data,
    LiquiditySurge,
    cash=1000000,  # $1,000,000 initial capital
    commission=0.001,  # 0.1% commission
    exclusive_orders=True
)

# Run with default parameters
stats = bt.run()
print("\n" + "="*80)
print("BACKTEST RESULTS")
print("="*80)
print(stats)
print("\n" + "="*80)
print("STRATEGY DETAILS")
print("="*80)
print(stats._strategy)