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
    liquidity_threshold = 35  # Reduced threshold for more signals
    risk_per_trade = 0.02  # Increased risk to 2% per trade
    risk_reward_ratio = 2.0  # Improved risk-reward ratio to 1:2
    max_holding_bars = 8  # Reduced holding period
    atr_multiplier = 1.2  # Tighter stop loss
    atr_period = 10  # Shorter ATR period for faster adaptation
    rsi_period = 10  # Shorter RSI period
    rsi_overbought = 75  # Adjusted overbought level
    rsi_oversold = 25  # Adjusted oversold level
    ema_fast = 20  # Fast EMA for trend filter
    ema_slow = 50  # Slow EMA for trend filter
    volume_multiplier = 1.5  # Volume spike multiplier
    min_volume_ratio = 1.2  # Minimum volume ratio for signal validation
    
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
        
        # Calculate EMAs for trend filter
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
        self.volume_sma = self.I(
            talib.SMA,
            self.data.Volume,
            timeperiod=20,
            name='Volume_SMA'
        )
        
        # Calculate price momentum
        self.momentum = self.I(
            talib.MOM,
            self.data.Close,
            timeperiod=10,
            name='Momentum'
        )
        
        # Track entry bars for time-based exit
        self.entry_bar = 0
        
        # Track current position direction
        self.position_direction = 0
        
        # Track consecutive losses for dynamic position sizing
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # Check if we have enough data
        if current_bar < max(self.ema_slow, 50):
            return
            
        # Get current values using array indexing
        liquidity_change = self.liquidity_pct_change[-1]
        atr_value = self.atr[-1]
        rsi_value = self.rsi[-1]
        current_close = self.data.Close[-1]
        current_volume = self.data.Volume[-1]
        volume_sma_value = self.volume_sma[-1] if self.volume_sma[-1] > 0 else 1
        volume_ratio = current_volume / volume_sma_value
        ema_fast_value = self.ema_fast_line[-1]
        ema_slow_value = self.ema_slow_line[-1]
        momentum_value = self.momentum[-1]
        
        # Calculate trend direction
        trend_up = ema_fast_value > ema_slow_value
        trend_down = ema_fast_value < ema_slow_value
        
        # Calculate stop loss and take profit distances
        if atr_value > 0:
            stop_distance = atr_value * self.atr_multiplier
            target_distance = stop_distance * self.risk_reward_ratio
        else:
            stop_distance = current_close * 0.008  # 0.8% stop
            target_distance = stop_distance * self.risk_reward_ratio
        
        # Dynamic position sizing based on win/loss streak
        base_risk = self.risk_per_trade
        
        # Reduce position size after consecutive losses
        if self.consecutive_losses >= 2:
            position_multiplier = 0.5
        elif self.consecutive_wins >= 3:
            position_multiplier = 1.5  # Increase size after wins
        else:
            position_multiplier = 1.0
        
        # Calculate position size based on risk
        if self.equity > 0 and stop_distance > 0:
            risk_amount = self.equity * base_risk * position_multiplier
            position_size = risk_amount / stop_distance
            position_size = int(round(position_size))
        else:
            position_size = 100
            
        # Ensure position size is valid
        if position_size <= 0:
            position_size = 100
        
        # Check for exit conditions
        if self.position:
            bars_held = current_bar - self.entry_bar
            
            # Time-based exit with partial profit taking
            if bars_held >= self.max_holding_bars:
                if self.position_direction == 1:
                    print(f"[EXIT] Time-based exit for long position after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
                    self.consecutive_losses = 0
                    self.consecutive_wins = 0
                elif self.position_direction == -1:
                    print(f"[EXIT] Time-based exit for short position after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
                    self.consecutive_losses = 0
                    self.consecutive_wins = 0
            
            # Trailing stop for long positions
            if self.position_direction == 1:
                current_stop = self.position.sl
                new_stop = current_close - stop_distance * 0.8  # Tighter trailing stop
                if new_stop > current_stop:
                    self.position.sl = new_stop
            
            # Trailing stop for short positions
            elif self.position_direction == -1:
                current_stop = self.position.sl
                new_stop = current_close + stop_distance * 0.8  # Tighter trailing stop
                if new_stop < current_stop:
                    self.position.sl = new_stop
        
        # Check for entry signals (only if no position)
        if not self.position:
            # Enhanced long entry conditions
            long_condition = (
                liquidity_change < -self.liquidity_threshold and
                volume_ratio > self.min_volume_ratio and
                rsi_value < self.rsi_oversold and
                momentum_value < 0 and  # Price is declining
                trend_up  # Only trade long in uptrend
            )
            
            # Enhanced short entry conditions
            short_condition = (
                liquidity_change > self.liquidity_threshold and
                volume_ratio > self.min_volume_ratio and
                rsi_value > self.rsi_overbought and
                momentum_value > 0 and  # Price is rising
                trend_down  # Only trade short in downtrend
            )
            
            # Long entry
            if long_condition:
                print(f"[LONG] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}, Volume ratio {volume_ratio:.2f}")
                
                # Calculate stop and target prices
                stop_price = current_close - stop_distance
                target_price = current_close + target_distance
                
                # Enter long position
                self.buy(size=position_size, sl=stop_price, tp=target_price)
                self.entry_bar = current_bar
                self.position_direction = 1
                print(f"[LONG] Position size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")
            
            # Short entry
            elif short_condition:
                print(f"[SHORT] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}, Volume ratio {volume_ratio:.2f}")
                
                # Calculate stop and target prices
                stop_price = current_close + stop_distance
                target_price = current_close - target_distance
                
                # Enter short position
                self.sell(size=position_size, sl=stop_price, tp=target_price)
                self.entry_bar = current_bar
                self.position_direction = -1
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