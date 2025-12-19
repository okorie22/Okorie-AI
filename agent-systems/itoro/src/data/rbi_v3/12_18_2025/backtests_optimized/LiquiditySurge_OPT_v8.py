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
    risk_per_trade = 0.02  # Increased to 2% risk per trade
    risk_reward_ratio = 2.0  # Improved to 1:2 risk-reward ratio
    max_holding_bars = 8  # Reduced to 8 bars for faster exits
    atr_multiplier = 1.2  # Reduced ATR multiplier for tighter stops
    atr_period = 10  # Reduced ATR period for more responsiveness
    rsi_period = 10  # Reduced RSI period for more responsiveness
    rsi_overbought = 75  # Increased to avoid false overbought signals
    rsi_oversold = 25  # Decreased to avoid false oversold signals
    ema_fast = 20  # Fast EMA for trend filter
    ema_slow = 50  # Slow EMA for trend filter
    volume_multiplier = 1.5  # Volume spike multiplier
    min_volume_ratio = 1.2  # Minimum volume ratio vs average
    
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
        
        # Calculate volume average for volume filter
        self.volume_sma = self.I(
            talib.SMA,
            self.data.Volume,
            timeperiod=20,
            name='Volume_SMA'
        )
        
        # Track entry bars for time-based exit
        self.entry_bar = 0
        
        # Track current position direction
        self.position_direction = 0  # 0: no position, 1: long, -1: short
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # Check if we have enough data
        if current_bar < max(self.ema_slow, 20):
            return
            
        # Get current values using array indexing
        liquidity_change = self.liquidity_pct_change[-1]
        atr_value = self.atr[-1]
        rsi_value = self.rsi[-1]
        current_close = self.data.Close[-1]
        current_volume = self.data.Volume[-1]
        volume_sma_value = self.volume_sma[-1] if len(self.volume_sma) > 0 else current_volume
        ema_fast_value = self.ema_fast_line[-1]
        ema_slow_value = self.ema_slow_line[-1]
        
        # Calculate volume ratio
        volume_ratio = current_volume / volume_sma_value if volume_sma_value > 0 else 1
        
        # Determine trend direction
        trend_bullish = ema_fast_value > ema_slow_value
        trend_bearish = ema_fast_value < ema_slow_value
        
        # Calculate stop loss and take profit distances
        if atr_value > 0:
            stop_distance = atr_value * self.atr_multiplier
            target_distance = stop_distance * self.risk_reward_ratio
        else:
            stop_distance = current_close * 0.01
            target_distance = stop_distance * self.risk_reward_ratio
        
        # Dynamic position sizing based on signal strength and volatility
        signal_strength = abs(liquidity_change) / self.liquidity_threshold
        volatility_adjustment = max(0.5, min(2.0, 1.0 / (atr_value / current_close * 100) if atr_value > 0 else 1.0))
        
        adjusted_risk = self.risk_per_trade * min(signal_strength, 1.5) * volatility_adjustment
        
        if self.equity > 0 and stop_distance > 0:
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
            
            # Time-based exit with profit check
            if bars_held >= self.max_holding_bars:
                current_pnl = self.position.pl_pct * 100
                if current_pnl > 0.5 or bars_held >= self.max_holding_bars * 1.5:
                    if self.position_direction == 1:
                        print(f"[EXIT] Time-based exit for long position after {bars_held} bars, PnL: {current_pnl:.2f}%")
                        self.position.close()
                        self.position_direction = 0
                    elif self.position_direction == -1:
                        print(f"[EXIT] Time-based exit for short position after {bars_held} bars, PnL: {current_pnl:.2f}%")
                        self.position.close()
                        self.position_direction = 0
            
            # Trailing stop for profitable positions
            if self.position.pl > 0:
                if self.position_direction == 1:
                    current_stop = self.position.sl if self.position.sl else current_close - stop_distance
                    new_stop = max(current_stop, current_close - stop_distance * 0.8)
                    if new_stop > current_stop:
                        self.position.sl = new_stop
                elif self.position_direction == -1:
                    current_stop = self.position.sl if self.position.sl else current_close + stop_distance
                    new_stop = min(current_stop, current_close + stop_distance * 0.8)
                    if new_stop < current_stop:
                        self.position.sl = new_stop
            
            # Contrary signal exit with confirmation
            if self.position_direction == 1 and liquidity_change > self.liquidity_threshold * 0.8:
                if rsi_value > 60:
                    print("[EXIT] Contrary signal exit for long position")
                    self.position.close()
                    self.position_direction = 0
            elif self.position_direction == -1 and liquidity_change < -self.liquidity_threshold * 0.8:
                if rsi_value < 40:
                    print("[EXIT] Contrary signal exit for short position")
                    self.position.close()
                    self.position_direction = 0
        
        # Check for entry signals (only if no position)
        if not self.position:
            # Volume filter: require above average volume
            if volume_ratio < self.min_volume_ratio:
                return
            
            # Long entry: liquidity drop < -50% (capitulation) with trend and volume confirmation
            if liquidity_change < -self.liquidity_threshold:
                # Enhanced confirmation: RSI oversold AND bullish trend OR strong volume spike
                volume_spike = volume_ratio > self.volume_multiplier
                rsi_confirmation = rsi_value < self.rsi_oversold
                trend_confirmation = trend_bullish or (not trend_bearish)
                
                if (rsi_confirmation and trend_confirmation) or volume_spike:
                    print(f"[LONG] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}, Volume ratio {volume_ratio:.2f}")
                    
                    stop_price = current_close - stop_distance
                    target_price = current_close + target_distance
                    
                    # Scale in: enter with 70% of position, save 30% for potential add
                    initial_size = int(position_size * 0.7)
                    if initial_size > 0:
                        self.buy(size=initial_size, sl=stop_price, tp=target_price)
                        self.entry_bar = current_bar
                        self.position_direction = 1
                        print(f"[LONG] Position size: {initial_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")
            
            # Short entry: liquidity spike > +50% (euphoric buying) with trend and volume confirmation
            elif liquidity_change > self.liquidity_threshold:
                # Enhanced confirmation: RSI overbought AND bearish trend OR strong volume spike
                volume_spike = volume_ratio > self.volume_multiplier
                rsi_confirmation = rsi_value > self.rsi_overbought
                trend_confirmation = trend_bearish or (not trend_bullish)
                
                if (rsi_confirmation and trend_confirmation) or volume_spike:
                    print(f"[SHORT] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}, Volume ratio {volume_ratio:.2f}")
                    
                    stop_price = current_close + stop_distance
                    target_price = current_close - target_distance
                    
                    # Scale in: enter with 70% of position
                    initial_size = int(position_size * 0.7)
                    if initial_size > 0:
                        self.sell(size=initial_size, sl=stop_price, tp=target_price)
                        self.entry_bar = current_bar
                        self.position_direction = -1
                        print(f"[SHORT] Position size: {initial_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")

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