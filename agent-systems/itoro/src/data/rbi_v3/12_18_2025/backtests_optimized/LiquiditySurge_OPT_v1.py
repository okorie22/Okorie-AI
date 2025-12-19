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
    risk_per_trade = 0.02  # Increased risk to 2% for higher returns
    risk_reward_ratio = 2.0  # Increased to 1:2 risk-reward ratio
    max_holding_bars = 8  # Reduced holding period to 8 bars
    atr_multiplier = 1.2  # Reduced ATR multiplier for tighter stops
    atr_period = 10  # Reduced ATR period for more responsive stops
    rsi_period = 10  # Reduced RSI period for faster signals
    rsi_overbought = 75  # Increased overbought threshold
    rsi_oversold = 25  # Decreased oversold threshold
    ema_fast = 9  # Fast EMA for trend filter
    ema_slow = 21  # Slow EMA for trend filter
    min_volume_multiplier = 1.5  # Minimum volume multiplier filter
    volatility_filter = 0.5  # Minimum ATR/Close ratio for valid signals
    trailing_stop_activation = 1.5  # Activate trailing stop after 1.5x risk
    trailing_stop_distance = 0.8  # Trailing stop at 0.8x ATR
    
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
        self.ema_fast = self.I(
            talib.EMA,
            self.data.Close,
            timeperiod=self.ema_fast,
            name='EMA_Fast'
        )
        
        self.ema_slow = self.I(
            talib.EMA,
            self.data.Close,
            timeperiod=self.ema_slow,
            name='EMA_Slow'
        )
        
        # Calculate volume average for volume filter
        self.volume_avg = self.I(
            talib.SMA,
            self.data.Volume,
            timeperiod=20,
            name='Volume_Avg'
        )
        
        # Track entry bars for time-based exit
        self.entry_bar = 0
        self.entry_price = 0
        self.initial_stop = 0
        self.trailing_active = False
        
        # Track current position direction
        self.position_direction = 0  # 0: no position, 1: long, -1: short
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # Check if we have enough data
        if current_bar < max(self.atr_period, self.rsi_period, self.ema_slow) + 1:
            return
            
        # Get current values using array indexing
        liquidity_change = self.liquidity_pct_change[-1]
        atr_value = self.atr[-1]
        rsi_value = self.rsi[-1]
        current_close = self.data.Close[-1]
        current_volume = self.data.Volume[-1]
        volume_avg = self.volume_avg[-1]
        ema_fast_val = self.ema_fast[-1]
        ema_slow_val = self.ema_slow[-1]
        
        # Calculate volatility filter
        volatility_ratio = atr_value / current_close if current_close > 0 else 0
        
        # Calculate stop loss and take profit distances
        if atr_value > 0:
            stop_distance = atr_value * self.atr_multiplier
            target_distance = stop_distance * self.risk_reward_ratio
        else:
            stop_distance = current_close * 0.01
            target_distance = stop_distance * self.risk_reward_ratio
        
        # Calculate position size based on risk with volatility adjustment
        if self.equity > 0 and stop_distance > 0:
            # Adjust risk based on volatility - reduce position in high volatility
            volatility_adjustment = max(0.5, min(1.5, 1.0 / (volatility_ratio * 100 + 0.1)))
            adjusted_risk = self.risk_per_trade * volatility_adjustment
            risk_amount = self.equity * adjusted_risk
            position_size = risk_amount / stop_distance
            position_size = int(round(position_size))
        else:
            position_size = 100
            
        if position_size <= 0:
            position_size = 100
        
        # Check for exit conditions
        if self.position:
            bars_held = current_bar - self.entry_bar
            
            # Time-based exit
            if bars_held >= self.max_holding_bars:
                if self.position_direction == 1:
                    print(f"[EXIT] Time-based exit for long position after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
                    self.trailing_active = False
                elif self.position_direction == -1:
                    print(f"[EXIT] Time-based exit for short position after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
                    self.trailing_active = False
            
            # Trailing stop logic
            if self.trailing_active:
                if self.position_direction == 1:
                    # Long position trailing stop
                    trailing_stop_price = current_close - (atr_value * self.trailing_stop_distance)
                    if trailing_stop_price > self.initial_stop:
                        self.position.sl = trailing_stop_price
                elif self.position_direction == -1:
                    # Short position trailing stop
                    trailing_stop_price = current_close + (atr_value * self.trailing_stop_distance)
                    if trailing_stop_price < self.initial_stop:
                        self.position.sl = trailing_stop_price
            
            # Activate trailing stop after reaching profit target
            if not self.trailing_active:
                if self.position_direction == 1:
                    profit_pct = (current_close - self.entry_price) / stop_distance
                    if profit_pct >= self.trailing_stop_activation:
                        self.trailing_active = True
                        print(f"[TRAILING] Activating trailing stop for long position at {profit_pct:.1f}x risk")
                elif self.position_direction == -1:
                    profit_pct = (self.entry_price - current_close) / stop_distance
                    if profit_pct >= self.trailing_stop_activation:
                        self.trailing_active = True
                        print(f"[TRAILING] Activating trailing stop for short position at {profit_pct:.1f}x risk")
            
            # Contrary signal exit with stronger filter
            if self.position_direction == 1:
                if liquidity_change > self.liquidity_threshold * 1.2:  # Stronger bearish signal required
                    print("[EXIT] Contrary signal exit for long position (strong bearish liquidity spike)")
                    self.position.close()
                    self.position_direction = 0
                    self.trailing_active = False
            elif self.position_direction == -1:
                if liquidity_change < -self.liquidity_threshold * 1.2:  # Stronger bullish signal required
                    print("[EXIT] Contrary signal exit for short position (strong bullish liquidity drain)")
                    self.position.close()
                    self.position_direction = 0
                    self.trailing_active = False
        
        # Check for entry signals (only if no position)
        if not self.position:
            # Volume filter - require above average volume
            volume_ok = current_volume > volume_avg * self.min_volume_multiplier
            
            # Volatility filter - avoid extremely low volatility periods
            volatility_ok = volatility_ratio > self.volatility_filter / 100
            
            # Trend filter for long entries
            trend_bullish = ema_fast_val > ema_slow_val
            trend_bearish = ema_fast_val < ema_slow_val
            
            # Long entry: liquidity drop < -50% (capitulation)
            if liquidity_change < -self.liquidity_threshold and volume_ok and volatility_ok:
                # RSI confirmation (oversold) AND trend alignment
                if rsi_value < self.rsi_oversold and trend_bullish:
                    print(f"[LONG] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}, Trend aligned")
                    
                    # Calculate stop and target prices
                    stop_price = current_close - stop_distance
                    target_price = current_close + target_distance
                    
                    # Enter long position
                    self.buy(size=position_size, sl=stop_price, tp=target_price)
                    self.entry_bar = current_bar
                    self.entry_price = current_close
                    self.initial_stop = stop_price
                    self.position_direction = 1
                    self.trailing_active = False
                    print(f"[LONG] Position size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")
            
            # Short entry: liquidity spike > +50% (euphoric buying)
            elif liquidity_change > self.liquidity_threshold and volume_ok and volatility_ok:
                # RSI confirmation (overbought) AND trend alignment
                if rsi_value > self.rsi_overbought and trend_bearish:
                    print(f"[SHORT] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}, Trend aligned")
                    
                    # Calculate stop and target prices
                    stop_price = current_close + stop_distance
                    target_price = current_close - target_distance
                    
                    # Enter short position
                    self.sell(size=position_size, sl=stop_price, tp=target_price)
                    self.entry_bar = current_bar
                    self.entry_price = current_close
                    self.initial_stop = stop_price
                    self.position_direction = -1
                    self.trailing_active = False
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