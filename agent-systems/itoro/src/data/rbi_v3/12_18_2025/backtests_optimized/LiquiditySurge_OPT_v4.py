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
    # Strategy parameters
    liquidity_threshold = 35  # Reduced threshold for more frequent signals
    risk_per_trade = 0.02  # Increased risk to 2% per trade
    risk_reward_ratio = 2.0  # Improved risk-reward ratio to 1:2
    max_holding_bars = 15  # Increased holding period
    atr_multiplier = 1.2  # Tighter stop loss multiplier
    atr_period = 14
    rsi_period = 14
    rsi_overbought = 75  # Adjusted overbought level
    rsi_oversold = 25  # Adjusted oversold level
    ema_fast = 20  # Fast EMA for trend filter
    ema_slow = 50  # Slow EMA for trend filter
    volume_multiplier = 1.5  # Volume spike multiplier
    min_volume_ratio = 1.2  # Minimum volume ratio for confirmation
    
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
        
        # Calculate ATR for stop loss and position sizing
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
        
        # Calculate EMAs for trend filtering
        self.ema_fast_line = self.I(
            talib.EMA,
            self.data.Close,
            timeperiod=self.ema_fast,
            name='EMA_Fast'
        )
        
        self.ema_slow_line = self.I(
            talib.EMA,
            self.data.Close,
            timeperiod=self.ema_slow,
            name='EMA_Slow'
        )
        
        # Calculate volume moving average for spike detection
        self.volume_ma = self.I(
            talib.SMA,
            self.data.Volume,
            timeperiod=20,
            name='Volume_MA'
        )
        
        # Calculate ADX for trend strength
        self.adx = self.I(
            talib.ADX,
            self.data.High,
            self.data.Low,
            self.data.Close,
            timeperiod=14,
            name='ADX'
        )
        
        # Track entry bars for time-based exit
        self.entry_bar = 0
        self.position_direction = 0
        self.entry_price = 0
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # Check if we have enough data
        if current_bar < 50:
            return
            
        # Get current values
        liquidity_change = self.liquidity_pct_change[-1]
        atr_value = self.atr[-1]
        rsi_value = self.rsi[-1]
        current_close = self.data.Close[-1]
        current_volume = self.data.Volume[-1]
        volume_ma = self.volume_ma[-1]
        ema_fast = self.ema_fast_line[-1]
        ema_slow = self.ema_slow_line[-1]
        adx_value = self.adx[-1]
        
        # Calculate volume spike
        volume_spike = current_volume > (volume_ma * self.volume_multiplier) if volume_ma > 0 else False
        volume_above_avg = current_volume > (volume_ma * self.min_volume_ratio) if volume_ma > 0 else True
        
        # Calculate trend direction
        trend_up = ema_fast > ema_slow
        trend_down = ema_fast < ema_slow
        strong_trend = adx_value > 25
        
        # Calculate stop loss and take profit distances with volatility adjustment
        if atr_value > 0:
            # Dynamic stop based on volatility and trend strength
            base_stop_multiplier = self.atr_multiplier
            if strong_trend:
                base_stop_multiplier *= 1.3  # Wider stops in strong trends
            
            stop_distance = atr_value * base_stop_multiplier
            target_distance = stop_distance * self.risk_reward_ratio
            
            # Adjust target based on trend strength
            if strong_trend:
                target_distance *= 1.5
        else:
            stop_distance = current_close * 0.008  # 0.8% stop
            target_distance = stop_distance * self.risk_reward_ratio
        
        # Dynamic position sizing based on volatility and trend
        if self.equity > 0 and stop_distance > 0:
            base_risk = self.risk_per_trade
            
            # Reduce risk in choppy markets
            if adx_value < 20:
                base_risk *= 0.5
            
            risk_amount = self.equity * base_risk
            position_size = risk_amount / stop_distance
            
            # Scale position based on signal strength
            signal_strength = abs(liquidity_change) / self.liquidity_threshold
            if signal_strength > 1.5:
                position_size *= 1.3
            elif signal_strength > 2.0:
                position_size *= 1.5
            
            position_size = int(round(position_size))
        else:
            position_size = 100
        
        if position_size <= 0:
            position_size = 100
        
        # Check for exit conditions
        if self.position:
            bars_held = current_bar - self.entry_bar
            
            # Trailing stop for profitable positions
            if self.position_direction == 1 and current_close > self.entry_price:
                # Move stop to breakeven + 0.5 ATR after 1:1 risk-reward
                profit_pct = (current_close - self.entry_price) / self.entry_price
                if profit_pct > (stop_distance / self.entry_price):
                    new_stop = self.entry_price + (atr_value * 0.5)
                    if new_stop > self.position.sl:
                        self.position.sl = new_stop
            
            elif self.position_direction == -1 and current_close < self.entry_price:
                profit_pct = (self.entry_price - current_close) / self.entry_price
                if profit_pct > (stop_distance / self.entry_price):
                    new_stop = self.entry_price - (atr_value * 0.5)
                    if new_stop < self.position.sl:
                        self.position.sl = new_stop
            
            # Time-based exit with trend consideration
            if bars_held >= self.max_holding_bars:
                if self.position_direction == 1:
                    print(f"[EXIT] Time-based exit for long position after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
                elif self.position_direction == -1:
                    print(f"[EXIT] Time-based exit for short position after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
            
            # RSI extreme exit
            if self.position_direction == 1 and rsi_value > 80:
                print("[EXIT] RSI overbought exit for long position")
                self.position.close()
                self.position_direction = 0
            elif self.position_direction == -1 and rsi_value < 20:
                print("[EXIT] RSI oversold exit for short position")
                self.position.close()
                self.position_direction = 0
        
        # Check for entry signals (only if no position)
        if not self.position and volume_above_avg:
            # Long entry: liquidity drop with trend alignment
            if liquidity_change < -self.liquidity_threshold:
                # Enhanced entry conditions
                entry_conditions = (
                    rsi_value < self.rsi_oversold and  # Oversold
                    (trend_up or not strong_trend) and  # Either uptrend or no strong trend
                    volume_spike  # Volume confirmation
                )
                
                if entry_conditions:
                    print(f"[LONG] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}")
                    
                    stop_price = current_close - stop_distance
                    target_price = current_close + target_distance
                    
                    # Scale in with partial position
                    self.buy(size=position_size, sl=stop_price, tp=target_price)
                    self.entry_bar = current_bar
                    self.position_direction = 1
                    self.entry_price = current_close
                    print(f"[LONG] Position size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")
            
            # Short entry: liquidity spike with trend alignment
            elif liquidity_change > self.liquidity_threshold:
                # Enhanced entry conditions
                entry_conditions = (
                    rsi_value > self.rsi_overbought and  # Overbought
                    (trend_down or not strong_trend) and  # Either downtrend or no strong trend
                    volume_spike  # Volume confirmation
                )
                
                if entry_conditions:
                    print(f"[SHORT] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}")
                    
                    stop_price = current_close + stop_distance
                    target_price = current_close - target_distance
                    
                    self.sell(size=position_size, sl=stop_price, tp=target_price)
                    self.entry_bar = current_bar
                    self.position_direction = -1
                    self.entry_price = current_close
                    print(f"[SHORT] Position size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")

# Run backtest
print("\n[INFO] Starting backtest...")
bt = Backtest(
    price_data,
    LiquiditySurge,
    cash=1000000,
    commission=0.001,
    exclusive_orders=True
)

stats = bt.run()
print("\n" + "="*80)
print("BACKTEST RESULTS")
print("="*80)
print(stats)
print("\n" + "="*80)
print("STRATEGY DETAILS")
print("="*80)
print(stats._strategy)