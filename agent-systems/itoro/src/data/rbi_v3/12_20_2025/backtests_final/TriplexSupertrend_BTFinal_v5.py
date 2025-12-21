import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
import talib

class TriplexSupertrend(Strategy):
    def init(self):
        print("[STRATEGY] TriplexSupertrend initialized")

        # Calculate ATR for Supertrend calculations
        # Note: Long Supertrends now use atr_16 and atr_18 (less sensitive, better for uptrends)
        self.atr_8 = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=8)  # Legacy, not used
        self.atr_9 = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=9)  # Used for position sizing
        self.atr_16 = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=16)  # Used for ST_B1
        self.atr_18 = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=18)  # Used for ST_B2, ST_B3, ST_S2, ST_S3

        # SEPARATE TREND DETECTION - Independent indicator for both longs and shorts
        # This is used ONLY for trend detection, NOT for entry/exit signals
        # This allows us to tune entry/exit multipliers without affecting trend detection
        self.trend_detector = self.I(self._calculate_supertrend, multiplier=2.5, period=18, atr_data=self.atr_18)

        # Calculate Supertrend indicators
        # Buy Supertrends (Bullish Confirmation Triad) - FOR LONG ENTRIES/EXITS ONLY
        self.st_b1 = self.I(self._calculate_supertrend, multiplier=1, period=16, atr_data=self.atr_16)  # Less responsive for longs
        self.st_b2 = self.I(self._calculate_supertrend, multiplier=2, period=18, atr_data=self.atr_18)  # More stable for longs
        self.st_b3 = self.I(self._calculate_supertrend, multiplier=3, period=18, atr_data=self.atr_18)  # Most stable for longs

        # Sell Supertrends (Bearish Confirmation Triad) - FOR SHORT ENTRIES/EXITS ONLY
        self.st_s1 = self.I(self._calculate_supertrend, multiplier=1, period=16, atr_data=self.atr_16)
        self.st_s2 = self.I(self._calculate_supertrend, multiplier=3, period=18, atr_data=self.atr_18)
        self.st_s3 = self.I(self._calculate_supertrend, multiplier=6, period=18, atr_data=self.atr_18)

        # Track trade count
        self.trade_count = 0

    def _calculate_supertrend(self, multiplier, period, atr_data):
        """Calculate Supertrend indicator with CORRECT direction logic"""
        hl2 = (self.data.High + self.data.Low) / 2

        # Initialize arrays - FIX: Use NaN for early values instead of 0
        supertrend = np.zeros(len(self.data.Close))
        direction = np.full(len(self.data.Close), np.nan)  # Start with NaN to avoid 0 values

        # Calculate Supertrend
        for i in range(period, len(self.data.Close)):
            atr_value = atr_data[i] * multiplier
            upper_band = hl2[i] + atr_value
            lower_band = hl2[i] - atr_value

            if i == period:
                # Initial values - start with upper band
                supertrend[i] = upper_band
            else:
                # Update bands to maintain continuity
                if upper_band < supertrend[i-1] or self.data.Close[i-1] > supertrend[i-1]:
                    upper_band = supertrend[i-1]

                if lower_band > supertrend[i-1] or self.data.Close[i-1] < supertrend[i-1]:
                    lower_band = supertrend[i-1]

                # Determine Supertrend value based on previous trend
                if supertrend[i-1] == upper_band:
                    if self.data.Close[i] <= upper_band:
                        supertrend[i] = upper_band
                    else:
                        supertrend[i] = lower_band
                else:  # supertrend[i-1] == lower_band
                    if self.data.Close[i] >= lower_band:
                        supertrend[i] = lower_band
                    else:
                        supertrend[i] = upper_band

            # CORRECTED: Direction based on price vs Supertrend (matches original FSupertrendStrategy)
            # If close > supertrend, trend is UP (bullish) = 1
            # If close < supertrend, trend is DOWN (bearish) = -1
            if self.data.Close[i] > supertrend[i]:
                direction[i] = 1   # Bullish (uptrend)
            else:
                direction[i] = -1  # Bearish (downtrend)

        # FIX: Fill early NaN values with first valid direction to avoid 0 signals
        first_valid_idx = period
        if first_valid_idx < len(direction) and not np.isnan(direction[first_valid_idx]):
            direction[:first_valid_idx] = direction[first_valid_idx]

        return direction

    def next(self):
        # DEBUG logging - print every 200 bars, on position changes, or trades
        should_log = (len(self.data) % 200 == 0 or
                     self.position or
                     (hasattr(self, '_last_position') and self._last_position != self.position))

        if should_log:
            print(f"[BAR {len(self.data)}] Equity: ${self.equity:.0f}, Position: {self.position.size if self.position else 0}")

        self._last_position = self.position

        # Skip if not enough data
        if len(self.data) < 30:
            return

        # Check for volume validation
        if self.data.Volume[-1] <= 0:
            return

        # Get current Supertrend signals
        st_b1_signal = self.st_b1[-1]
        st_b2_signal = self.st_b2[-1]
        st_b3_signal = self.st_b3[-1]
        st_s1_signal = self.st_s1[-1]
        st_s2_signal = self.st_s2[-1]
        st_s3_signal = self.st_s3[-1]

        # Get trend detection signal (INDEPENDENT of entry/exit indicators)
        trend_signal = self.trend_detector[-1]

        # DEBUG: Add signal logging back to see what's happening
        print(f"[DEBUG] Signals: B({st_b1_signal},{st_b2_signal},{st_b3_signal}) S({st_s1_signal},{st_s2_signal},{st_s3_signal}) | Trend: {trend_signal}")

        # Get previous signals for exit conditions
        st_b2_prev = self.st_b2[-2] if len(self.data) > 1 else 0
        st_b3_prev = self.st_b3[-2] if len(self.data) > 1 else 0  # For long exits
        st_s2_prev = self.st_s2[-2] if len(self.data) > 1 else 0  # For short exits
        st_s3_prev = self.st_s3[-2] if len(self.data) > 1 else 0  # For short exits using ST_S3

        # Calculate position size based on volatility (ATR) - CAPPED AT 0.5%
        current_atr = self.atr_9[-1] if len(self.atr_9) > 0 else 0
        current_price = self.data.Close[-1]

        # DEBUG: Check ATR values
        atr_16_val = self.atr_16[-1] if len(self.atr_16) > 0 else 0
        atr_18_val = self.atr_18[-1] if len(self.atr_18) > 0 else 0
        print(f"[DEBUG] ATR values: ATR16={atr_16_val:.4f}, ATR18={atr_18_val:.4f}, ATR9={current_atr:.4f}")

        if current_atr > 0 and current_price > 0:
            atr_ratio = current_atr / current_price
            base_size = 0.022  # 3% base position
            volatility_adjustment = min(1.0, 0.06 / max(atr_ratio, 0.001))  # Scaled up for 3% base
            position_fraction = max(0.01, min(base_size * volatility_adjustment, 0.025))  # Max 3%
        else:
            position_fraction = 0.02

        print(f"[DEBUG] Position fraction: {position_fraction:.6f}, ATR ratio: {current_atr/current_price:.6f} at price ${current_price:.0f}")

        # TREND STRENGTH FILTER - ATR only
        atr_ratio = current_atr / current_price if current_price > 0 else 0

        # ATR requirements (minimum volatility)
        trend_strength_ok_shorts = atr_ratio >= 0.0045  # SHORTS: Strict ATR requirement
        trend_strength_ok_longs = atr_ratio >= 0.0055   # LONGS: More relaxed ATR requirement

        print(f"[DEBUG] Trend strength: ATR ratio={atr_ratio:.6f}, shorts_ok={trend_strength_ok_shorts}, longs_ok={trend_strength_ok_longs}")

        # VOLUME CONFIRMATION FILTER - Different requirements for longs vs shorts
        if len(self.data) >= 5:
            avg_volume_5day = self.data.Volume[-5:].mean()  # 5-bar average volume
            volume_ok_longs = self.data.Volume[-1] > avg_volume_5day * 0.65  # LONGS: 30% of 5-day average
            volume_ok_shorts = self.data.Volume[-1] > avg_volume_5day * 0.35  # SHORTS: 45% of 5-day average
        else:
            avg_volume_5day = 0
            volume_ok_longs = True
            volume_ok_shorts = True  # Allow on insufficient data

        print(f"[DEBUG] Volume confirmation: current={self.data.Volume[-1]:.0f}, avg_5day={avg_volume_5day:.0f}, longs_ok={volume_ok_longs}, shorts_ok={volume_ok_shorts}")


        # ENTRY LOGIC
        # Long Entry: 2/3 Buy Supertrends show bullish (1) signal + filters (SPECIAL FOR LONGS)
        # Trend Protection: If in downtrend (trend_detector != 1), require 3/3 long signals (very strict)
        long_signals_count = sum([st_b1_signal == 1, st_b2_signal == 1, st_b3_signal == 1])
        # USE SEPARATE TREND DETECTOR - Independent of entry/exit indicators
        is_uptrend = (trend_signal == 1)  # Trend detector bullish = uptrend
        is_downtrend = (trend_signal != 1)  # Trend detector not bullish = downtrend/neutral

        # LONGS: 2/3 signals required in uptrend, 3/3 in downtrend (trend protection)
        if is_uptrend:
            long_condition = (long_signals_count >= 2 and trend_strength_ok_longs and volume_ok_longs and self.position.size == 0)
            long_req_text = "2/3 (uptrend)"
        else:
            long_condition = (long_signals_count >= 3 and trend_strength_ok_longs and volume_ok_longs and self.position.size == 0)
            long_req_text = "3/3 (downtrend protection)"

        print(f"[DEBUG] Long condition: {long_signals_count}/3 signals bullish, Trend={trend_signal}, req={long_req_text}, trend_ok={trend_strength_ok_longs}, volume_ok={volume_ok_longs}, position_size={self.position.size}, condition={long_condition}")

        if long_condition:
            self.trade_count += 1
            self.entry_bar = len(self.data)  # Track entry bar for time exits
            print(f"[TRADE {self.trade_count}] LONG Entry at bar {len(self.data)}, price: ${current_price:.0f}")
            print(f"[SIGNAL] ST_B: {st_b1_signal},{st_b2_signal},{st_b3_signal} | ST_S: {st_s1_signal},{st_s2_signal},{st_s3_signal}")

            stop_price = current_price * (1 - 0.265)  # 26.5% stop loss
            self.buy(size=position_fraction, sl=stop_price)

        # Short Entry: Trend protection based on market regime (KEEP SHORT LOGIC AS-IS)
        # In uptrend (trend_detector == 1): Require 3/3 short signals (very strict, trend protection)
        # In downtrend (trend_detector != 1): Require 2/3 short signals (normal entry)
        short_signals_count = sum([st_s1_signal == -1, st_s2_signal == -1, st_s3_signal == -1])

        if is_uptrend:
            short_condition = (short_signals_count >= 3 and trend_strength_ok_shorts and volume_ok_shorts and self.position.size == 0)
            short_req_text = "3/3 (uptrend protection)"
        else:
            short_condition = (short_signals_count >= 2 and trend_strength_ok_shorts and volume_ok_shorts and self.position.size == 0)
            short_req_text = "2/3 (downtrend)"

        print(f"[DEBUG] Short condition: {short_signals_count}/3 signals bearish, Trend={trend_signal}, req={short_req_text}, trend_ok={trend_strength_ok_shorts}, volume_ok={volume_ok_shorts}, position_size={self.position.size}, condition={short_condition}")

        if short_condition:
            self.trade_count += 1
            self.entry_bar = len(self.data)  # Track entry bar for time exits
            print(f"[TRADE {self.trade_count}] SHORT Entry at bar {len(self.data)}, price: ${current_price:.0f}")
            print(f"[SIGNAL] ST_B: {st_b1_signal},{st_b2_signal},{st_b3_signal} | ST_S: {st_s1_signal},{st_s2_signal},{st_s3_signal}")

            stop_price = current_price * (1 + 0.265)  # 26.5% stop loss for shorts
            self.sell(size=position_fraction, sl=stop_price)

        # EXIT LOGIC
        if self.position:
            # Get entry price and calculate PnL
            if self.trades:
                entry_price = self.trades[-1].entry_price
                current_pnl_pct = (entry_price - current_price) / entry_price * 100 if self.position.is_short else (current_price - entry_price) / entry_price * 100
            else:
                current_pnl_pct = 0

            # PROFIT-BASED EXITS (Different targets for longs vs shorts)
            profit_target_long = 15.0   # LONGS: 8% profit target
            profit_target_short = 12.0  # SHORTS: 12% profit target

            profit_exit_long = (self.position.is_long and current_pnl_pct >= profit_target_long)
            profit_exit_short = (not self.position.is_long and current_pnl_pct >= profit_target_short)

            # TIME-BASED EXITS (safety net) - Different for longs vs shorts
            if not hasattr(self, 'entry_bar'):
                self.entry_bar = len(self.data)  # Initialize entry bar
            time_elapsed = len(self.data) - self.entry_bar
            time_exit_long = (self.position.is_long and time_elapsed >= 324)  # LONGS: 360 bars (~15 days)
            time_exit_short = (not self.position.is_long and time_elapsed >= 300)  # SHORTS: 300 bars (~12.5 days)

            # SIGNAL-BASED EXITS (DIFFERENT FOR LONGS VS SHORTS)
            # Exit Long: ST_B3 flips from up (1) to down (-1) - MORE STABLE for longs
            long_exit_condition = (self.position.is_long and st_b3_prev == 1 and st_b3_signal == -1)

            # Exit Short: ST_S3 flips from down (-1) to up (1) - USE MOST STABLE SELL SUPERtrend for shorts
            short_exit_condition = (not self.position.is_long and st_s2_prev == -1 and st_s2_signal == 1)

            # EXIT EXECUTION
            exit_reason = ""
            if profit_exit_long:
                exit_reason = f"PROFIT EXIT LONG ({current_pnl_pct:.1f}%)"
            elif profit_exit_short:
                exit_reason = f"PROFIT EXIT SHORT ({current_pnl_pct:.1f}%)"
            elif time_exit_long:
                exit_reason = "TIME EXIT LONG (13.5 days)"
            elif time_exit_short:
                exit_reason = "TIME EXIT SHORT (12.5 days)"
            elif long_exit_condition:
                exit_reason = "SIGNAL EXIT LONG (ST_B2 flipped)"
            elif short_exit_condition:
                exit_reason = "SIGNAL EXIT SHORT (ST_S2 flipped)"

            if exit_reason:
                print(f"[EXIT] {exit_reason} at bar {len(self.data)}, price: ${current_price:.0f}, PnL: {current_pnl_pct:.1f}%")
                self.position.close()

# Load and prepare data (FIXED: Use correct 1h data file)
print("[INFO] Loading BTC-USD-1h data...")
try:
    price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-1h.csv')

    # Clean column names
    price_data.columns = price_data.columns.str.strip().str.lower()

    # Standardize column names for backtesting.py
    column_mapping = {
        'timestamp': 'datetime',
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    }

    price_data = price_data.rename(columns=column_mapping)

    # Set datetime index
    price_data['datetime'] = pd.to_datetime(price_data['datetime'])
    price_data = price_data.set_index('datetime')

    # Filter for volume > 0
    price_data = price_data[price_data['Volume'] > 0]

    print(f"[INFO] Data loaded: {len(price_data)} rows")
    print(f"[INFO] Date range: {price_data.index.min()} to {price_data.index.max()}")
    print(f"[INFO] Sample prices: Close range ${price_data['Close'].min():.0f} - ${price_data['Close'].max():.0f}")

except Exception as e:
    print(f"[ERROR] Failed to load data: {e}")
    raise

# Run backtest
print("[INFO] Starting TriplexSupertrend backtest...")
bt = Backtest(price_data, TriplexSupertrend, cash=1000000, commission=.0005, margin=0.05, finalize_trades=True)  # 20:1 leverage, close open trades, 0.05% commission

stats = bt.run()
print("\n" + "="*50)
print("BACKTEST RESULTS")
print("="*50)
print(stats)
print("\n" + "="*50)
print("STRATEGY DETAILS")
print("="*50)
print(f"[FINAL] Total trades executed: {stats._strategy.trade_count}")