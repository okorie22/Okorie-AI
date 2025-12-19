import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
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
    liquidity_threshold = 40  # 40% threshold for liquidity changes
    risk_per_trade = 0.01  # Risk 1% of equity per trade
    risk_reward_ratio = 1.5  # 1:1.5 risk-reward ratio
    max_holding_bars = 10  # Exit after 10 bars if no target/stop hit
    atr_multiplier = 1.5  # ATR multiplier for stop loss
    atr_period = 14  # ATR period
    rsi_period = 14  # RSI period for confirmation
    rsi_overbought = 70  # RSI overbought level
    rsi_oversold = 30  # RSI oversold level
    
    def init(self):
        # Calculate liquidity: Volume * Average Price ((H+L+C)/3)
        avg_price = (self.data.High + self.data.Low + self.data.Close) / 3
        liquidity = self.data.Volume * avg_price
        
        # Calculate liquidity percentage change
        self.liquidity_pct_change = self.I(
            lambda x: (x / pd.Series(x).shift(1) - 1) * 100,
            liquidity,
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
        
        # Track entry bars for time-based exit
        self.entry_bar = 0
        
        # Track current position direction
        self.position_direction = 0  # 0: no position, 1: long, -1: short
        
    def next(self):
        current_bar = len(self.data) - 1
        
        # Check if we have enough data
        if current_bar < 2:
            return
            
        # Get current values
        liquidity_change = self.liquidity_pct_change[-1]
        atr_value = self.atr[-1]
        rsi_value = self.rsi[-1]
        current_close = self.data.Close[-1]
        
        # Calculate stop loss and take profit distances
        if atr_value > 0:
            stop_distance = atr_value * self.atr_multiplier
            target_distance = stop_distance * self.risk_reward_ratio
        else:
            # Fallback to percentage-based stops if ATR is 0
            stop_distance = current_close * 0.01  # 1% stop
            target_distance = stop_distance * self.risk_reward_ratio
        
        # Calculate position size based on risk
        if self.equity > 0 and stop_distance > 0:
            risk_amount = self.equity * self.risk_per_trade
            position_size = risk_amount / stop_distance
            position_size = int(round(position_size))
        else:
            position_size = 100  # Default position size
            
        # Ensure position size is valid
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
                elif self.position_direction == -1:
                    print(f"[EXIT] Time-based exit for short position after {bars_held} bars")
                    self.position.close()
                    self.position_direction = 0
            
            # Contrary signal exit
            if self.position_direction == 1 and liquidity_change > self.liquidity_threshold:
                print("[EXIT] Contrary signal exit for long position (bearish liquidity spike)")
                self.position.close()
                self.position_direction = 0
            elif self.position_direction == -1 and liquidity_change < -self.liquidity_threshold:
                print("[EXIT] Contrary signal exit for short position (bullish liquidity drain)")
                self.position.close()
                self.position_direction = 0
        
        # Check for entry signals (only if no position)
        if not self.position:
            # Long entry: liquidity drop < -40% (capitulation)
            if liquidity_change < -self.liquidity_threshold:
                # Optional RSI confirmation (oversold)
                if rsi_value < self.rsi_oversold:
                    print(f"[LONG] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}")
                    
                    # Calculate stop and target prices
                    stop_price = current_close - stop_distance
                    target_price = current_close + target_distance
                    
                    # Enter long position
                    self.buy(size=position_size, sl=stop_price, tp=target_price)
                    self.entry_bar = current_bar
                    self.position_direction = 1
                    print(f"[LONG] Position size: {position_size}, Stop: {stop_price:.2f}, Target: {target_price:.2f}")
            
            # Short entry: liquidity spike > +40% (euphoric buying)
            elif liquidity_change > self.liquidity_threshold:
                # Optional RSI confirmation (overbought)
                if rsi_value > self.rsi_overbought:
                    print(f"[SHORT] Entry signal: Liquidity change {liquidity_change:.2f}%, RSI {rsi_value:.2f}")
                    
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