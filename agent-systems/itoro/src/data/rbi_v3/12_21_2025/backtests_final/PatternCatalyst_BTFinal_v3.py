import pandas as pd
import talib
from backtesting import Backtest, Strategy

class PatternCatalyst(Strategy):
    def init(self):
        print("[STRATEGY] PatternCatalyst initialized")
        
        # Initialize pattern indicators using self.I()
        self.engulfing = self.I(talib.CDLENGULFING, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.hammer = self.I(talib.CDLHAMMER, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.doji = self.I(talib.CDLDOJI, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.morning_star = self.I(talib.CDLMORNINGSTAR, self.data.Open, self.data.High, self.data.Low, self.data.Close)
        self.evening_star = self.I(talib.CDLEVENINGSTAR, self.data.Open, self.data.High, self.data.Low, self.data.Close)

        # TREND CONFIRMATION INDICATORS
        self.sma_20 = self.I(talib.SMA, self.data.Close, timeperiod=20)
        self.sma_50 = self.I(talib.SMA, self.data.Close, timeperiod=50)

        # MOMENTUM INDICATOR FOR CONFIRMATION
        self.rsi = self.I(talib.RSI, self.data.Close, timeperiod=14)

        # VOLUME CONFIRMATION
        self.volume_sma = self.I(talib.SMA, self.data.Volume, timeperiod=20)
        
        # Strategy parameters - DYNAMIC PATTERN SELECTION
        self.available_patterns = ['engulfing', 'hammer', 'doji', 'morning_star', 'evening_star']
        self.risk_percentage = 0.02  # 2% risk per trade (within 1-3% range)
        self.initial_stop_loss_pct = 0.30  # -28.8% initial stop loss
        self.trailing_activation_pct = 0.084  # +8.4% profit to activate trailing stop
        self.trailing_offset_pct = 0.084  # 8.4% trailing offset
        self.min_profit_pct = 0.032  # +3.2% minimum profit guarantee
        self.profit_target_pct = 0.10  # +8% profit target
        self.max_holding_period = 30  # Maximum 15 bars (15 days) holding period
        self.breakeven_trigger_pct = 0.02  # +2% profit to trigger breakeven stop
        self.min_signal_strength = 0.7  # Minimum signal strength (0.7 = 70% of max strength)
        
        # Initialize counters
        self.trade_count = 0
        self.bar_count = 0

    def check_trend_confirmation(self, direction):
        """Check if trend supports the trade direction"""
        current_price = self.data.Close[-1]

        # Trend confirmation using SMA crossover
        sma_20 = self.sma_20[-1]

        if direction == 'long':
            # Bullish trend: price above fast SMA only
            trend_up = (current_price > sma_20)
            return trend_up
        else:  # short
            # Bearish trend: price below fast SMA only
            trend_down = (current_price < sma_20)
            return trend_down

    def check_momentum_confirmation(self, direction):
        """Check momentum indicators for trade confirmation"""
        rsi_value = self.rsi[-1]

        if direction == 'long':
            # Bullish momentum: RSI oversold (< 40) or neutral (40-60)
            momentum_ok = rsi_value < 60  # Allow oversold to neutral RSI for longs
            return momentum_ok
        else:  # short
            # Bearish momentum: RSI overbought (> 40) or neutral (40-60)
            momentum_ok = rsi_value > 40  # Allow neutral to overbought RSI for shorts
            return momentum_ok

    def check_volume_confirmation(self):
        """Check if volume supports the pattern"""
        current_volume = self.data.Volume[-1]
        avg_volume = self.volume_sma[-1]

        # Require above-average volume (at least 80% of 20-day average)
        return current_volume >= (avg_volume * 0.8)

    def select_best_pattern(self):
        """Dynamically select the pattern with the strongest signal above minimum threshold"""
        pattern_scores = {}

        for pattern_name in self.available_patterns:
            pattern_value = getattr(self, pattern_name)[-1]
            # Use absolute value to find strongest signal regardless of direction
            pattern_scores[pattern_name] = abs(pattern_value)

        # Find the strongest pattern
        best_pattern = max(pattern_scores, key=pattern_scores.get)
        best_signal = getattr(self, best_pattern)[-1]
        max_possible_strength = 100.0  # Maximum possible pattern signal

        # Calculate signal strength as percentage of maximum
        signal_strength = abs(best_signal) / max_possible_strength

        # Only return pattern if it meets minimum strength requirement
        if signal_strength >= self.min_signal_strength:
            return best_pattern, best_signal
        else:
            return None, 0  # No strong enough signal found

    def detect_market_regime(self):
        """Detect market regime based on trend strength and price position"""
        if len(self.data) < 50:  # Need enough data for reliable detection
            return "neutral_sideways"

        current_price = self.data.Close[-1]
        sma_20 = self.sma_20[-1]
        sma_50 = self.sma_50[-1]

        # Price position relative to SMAs (normalized)
        price_vs_fast = (current_price - sma_20) / sma_20
        price_vs_slow = (current_price - sma_50) / sma_50

        # Trend strength score (-1 to +1)
        trend_strength = (price_vs_fast + price_vs_slow) / 2

        # Volatility measure (recent price range)
        recent_high = max(self.data.High[-20:])
        recent_low = min(self.data.Low[-20:])
        volatility = (recent_high - recent_low) / current_price

        print(f"[REGIME] Trend strength: {trend_strength:.4f}, Volatility: {volatility:.4f}")

        # Regime classification based on trend strength and volatility
        if trend_strength > 0.02:  # Strong uptrend
            regime = "strong_uptrend"
        elif trend_strength > 0.008:  # Moderate uptrend
            regime = "moderate_uptrend"
        elif trend_strength < -0.02:  # Strong downtrend
            regime = "strong_downtrend"
        elif trend_strength < -0.008:  # Moderate downtrend
            regime = "moderate_downtrend"
        elif abs(trend_strength) > 0.003:  # Sideways with slight bias
            regime = "sideways_bias"
        else:  # Neutral sideways
            regime = "neutral_sideways"

        print(f"[REGIME] Detected: {regime}")
        return regime

    def set_regime_parameters(self, regime):
        """Set strategy parameters based on detected market regime"""

        # Base parameters that stay constant
        self.risk_percentage = 0.02
        self.breakeven_trigger_pct = 0.02
        self.min_signal_strength = 0.7

        # Regime-specific parameters based on backtest results
        if regime == "strong_uptrend":
            # Set A: Works best for uptrends - wider stops, longer hold
            self.initial_stop_loss_pct = 0.25    # 25% stop loss
            self.profit_target_pct = 0.12        # 12% profit target
            self.max_holding_period = 48         # 48 bars (8 days)
            self.trailing_activation_pct = 0.10  # 10% to activate trailing
            self.trailing_offset_pct = 0.08      # 8% trailing offset
            self.min_profit_pct = 0.04           # 4% minimum profit

        elif regime == "strong_downtrend":
            # Set C: Works best for downtrends - tighter stops/targets, longer hold
            self.initial_stop_loss_pct = 0.15    # 15% stop loss
            self.profit_target_pct = 0.15        # 15% profit target
            self.max_holding_period = 60         # 60 bars (10 days)
            self.trailing_activation_pct = 0.08  # 8% to activate trailing
            self.trailing_offset_pct = 0.06      # 6% trailing offset
            self.min_profit_pct = 0.03           # 3% minimum profit

        elif regime == "moderate_uptrend":
            # Blend of strong uptrend and sideways - moderate parameters
            self.initial_stop_loss_pct = 0.20    # 20% stop loss
            self.profit_target_pct = 0.13        # 13% profit target
            self.max_holding_period = 42         # 42 bars (7 days)
            self.trailing_activation_pct = 0.09  # 9% to activate trailing
            self.trailing_offset_pct = 0.07      # 7% trailing offset
            self.min_profit_pct = 0.035          # 3.5% minimum profit

        elif regime == "moderate_downtrend":
            # Blend of strong downtrend and sideways - moderate parameters
            self.initial_stop_loss_pct = 0.18    # 18% stop loss
            self.profit_target_pct = 0.14        # 14% profit target
            self.max_holding_period = 54         # 54 bars (9 days)
            self.trailing_activation_pct = 0.085 # 8.5% to activate trailing
            self.trailing_offset_pct = 0.065     # 6.5% trailing offset
            self.min_profit_pct = 0.0325         # 3.25% minimum profit

        elif regime == "sideways_bias":
            # Sideways with slight directional bias - use Set C as base
            self.initial_stop_loss_pct = 0.15    # 15% stop loss
            self.profit_target_pct = 0.15        # 15% profit target
            self.max_holding_period = 60         # 60 bars (10 days)
            self.trailing_activation_pct = 0.08  # 8% to activate trailing
            self.trailing_offset_pct = 0.06      # 6% trailing offset
            self.min_profit_pct = 0.03           # 3% minimum profit

        else:  # neutral_sideways - default conservative settings
            # Conservative settings for neutral sideways markets
            self.initial_stop_loss_pct = 0.12    # 12% stop loss (tightest)
            self.profit_target_pct = 0.08        # 8% profit target (smallest)
            self.max_holding_period = 36         # 36 bars (6 days)
            self.trailing_activation_pct = 0.06  # 6% to activate trailing
            self.trailing_offset_pct = 0.05      # 5% trailing offset
            self.min_profit_pct = 0.025          # 2.5% minimum profit

        print(f"[PARAMETERS] Set for {regime}: SL={self.initial_stop_loss_pct*100:.1f}%, PT={self.profit_target_pct*100:.1f}%, Hold={self.max_holding_period} bars")
        
    def next(self):
        self.bar_count += 1

        # DYNAMIC REGIME DETECTION - Update parameters based on current market conditions
        current_regime = self.detect_market_regime()
        self.set_regime_parameters(current_regime)

        # DEBUG: Print current bar status
        print(f"[DEBUG] Bar {self.bar_count}, Equity: ${self.equity:.2f}, Position: {self.position.size if self.position else 0}")

        # Print summary every 100 bars
        if self.bar_count % 100 == 0:
            print(f"[SUMMARY] Bar {self.bar_count}, Equity: ${self.equity:.2f}, Trades: {self.trade_count}")
            # Print indicator values for debugging
            if len(self.data) > 1:
                print(f"[SUMMARY] Current prices - Open: {self.data.Open[-1]:.2f}, High: {self.data.High[-1]:.2f}, Low: {self.data.Low[-1]:.2f}, Close: {self.data.Close[-1]:.2f}")
                print(f"[SUMMARY] Pattern values - Engulfing: {self.engulfing[-1]}, Hammer: {self.hammer[-1]}, Doji: {self.doji[-1]}")
        
        # Exit logic - check for trailing stop and stop loss (handles both long and short positions)
        if self.position:
            current_price = self.data.Close[-1]

            # Get entry price and position direction from last trade
            if self.trades:
                entry_price = self.trades[-1].entry_price
            else:
                entry_price = current_price  # Fallback

            # Get entry bar and position direction
            entry_bar = getattr(self, 'entry_bar', self.bar_count - 1)
            position_direction = getattr(self, 'position_direction', 'long')

            # DEBUG: Print position info
            print(f"[DEBUG] Position active: size={self.position.size}, direction={position_direction}, entry_price={entry_price:.2f}, current_price={current_price:.2f}")

            # Calculate current profit percentage (different for long vs short)
            if position_direction == 'long':
                current_profit_pct = (current_price - entry_price) / entry_price
            else:  # short position
                current_profit_pct = (entry_price - current_price) / entry_price

            print(f"[DEBUG] Current profit: {current_profit_pct*100:.2f}% ({position_direction})")

            # PARTIAL PROFIT TAKING - Multiple levels
            if current_profit_pct >= 0.03:  # 3% profit - take 50%
                if not hasattr(self, 'partial_exit_3pct'):
                    print(f"[PARTIAL EXIT 3%] Taking 50% profit at bar {self.bar_count}, Price: {current_price:.2f}, Profit: {current_profit_pct*100:.2f}%")
                    self.position.close(portion=0.5)
                    self.partial_exit_3pct = True

            if current_profit_pct >= 0.06:  # 6% profit - take remaining 50%
                if not hasattr(self, 'partial_exit_6pct'):
                    print(f"[PARTIAL EXIT 6%] Taking remaining 50% profit at bar {self.bar_count}, Price: {current_price:.2f}, Profit: {current_profit_pct*100:.2f}%")
                    self.position.close(portion=0.5)
                    self.partial_exit_6pct = True
                    # Reset tracking variables
                    if hasattr(self, 'highest_since_entry'):
                        delattr(self, 'highest_since_entry')
                    if hasattr(self, 'lowest_since_entry'):
                        delattr(self, 'lowest_since_entry')
                    return

            # Check for final profit target exit (+8% for both long and short)
            if current_profit_pct >= self.profit_target_pct:
                print(f"[FINAL PROFIT TARGET] Exiting {position_direction} at bar {self.bar_count}, Price: {current_price:.2f}, Profit: {current_profit_pct*100:.2f}%")
                self.position.close()
                # Reset tracking variables
                if hasattr(self, 'highest_since_entry'):
                    delattr(self, 'highest_since_entry')
                if hasattr(self, 'lowest_since_entry'):
                    delattr(self, 'lowest_since_entry')
                return

            # BREAKEVEN STOP - Move stop loss to breakeven after +2% profit
            if current_profit_pct >= self.breakeven_trigger_pct:
                print(f"[BREAKEVEN] Moving stop to breakeven at bar {self.bar_count} (profit: {current_profit_pct*100:.2f}%)")
                # Stop loss is now at entry price (breakeven)
                # The existing stop loss logic below will handle this

            # Trailing stop logic (different for long vs short)
            if position_direction == 'long':
                # LONG POSITION: Track highest price since entry
                if hasattr(self, 'highest_since_entry'):
                    self.highest_since_entry = max(self.highest_since_entry, current_price)
                else:
                    self.highest_since_entry = current_price

                # Check if trailing stop should be activated (+8.4% profit)
                if current_profit_pct >= self.trailing_activation_pct:
                    # Calculate trailing stop price (8.4% below highest price)
                    trailing_stop_price = self.highest_since_entry * (1 - self.trailing_offset_pct)

                    # Ensure minimum profit guarantee (+3.2%)
                    min_profit_price = entry_price * (1 + self.min_profit_pct)
                    trailing_stop_price = max(trailing_stop_price, min_profit_price)

                    print(f"[DEBUG] Long trailing stop: highest={self.highest_since_entry:.2f}, stop={trailing_stop_price:.2f}")

                    # Exit if price hits trailing stop
                    if current_price <= trailing_stop_price:
                        print(f"[TRAILING STOP] Exiting LONG at bar {self.bar_count}, Price: {current_price:.2f}, Profit: {current_profit_pct*100:.2f}%")
                        self.position.close()
                        if hasattr(self, 'highest_since_entry'):
                            delattr(self, 'highest_since_entry')
                        return

            else:  # SHORT POSITION
                # SHORT POSITION: Track lowest price since entry
                if hasattr(self, 'lowest_since_entry'):
                    self.lowest_since_entry = min(self.lowest_since_entry, current_price)
                else:
                    self.lowest_since_entry = current_price

                # Check if trailing stop should be activated (+8.4% profit)
                if current_profit_pct >= self.trailing_activation_pct:
                    # Calculate trailing stop price (8.4% above lowest price)
                    trailing_stop_price = self.lowest_since_entry * (1 + self.trailing_offset_pct)

                    # Ensure minimum profit guarantee (+3.2%)
                    min_profit_price = entry_price * (1 - self.min_profit_pct)
                    trailing_stop_price = min(trailing_stop_price, min_profit_price)

                    print(f"[DEBUG] Short trailing stop: lowest={self.lowest_since_entry:.2f}, stop={trailing_stop_price:.2f}")

                    # Exit if price hits trailing stop
                    if current_price >= trailing_stop_price:
                        print(f"[TRAILING STOP] Exiting SHORT at bar {self.bar_count}, Price: {current_price:.2f}, Profit: {current_profit_pct*100:.2f}%")
                        self.position.close()
                        if hasattr(self, 'lowest_since_entry'):
                            delattr(self, 'lowest_since_entry')
                        return

            # Time-based exit (safety net - max 15 bars/15 days)
            bars_held = self.bar_count - entry_bar
            if bars_held >= self.max_holding_period:
                print(f"[TIME EXIT] Exiting {position_direction} at bar {self.bar_count} after {bars_held} bars, Price: {current_price:.2f}, Profit: {current_profit_pct*100:.2f}%")
                self.position.close()
                # Reset tracking variables
                if hasattr(self, 'highest_since_entry'):
                    delattr(self, 'highest_since_entry')
                if hasattr(self, 'lowest_since_entry'):
                    delattr(self, 'lowest_since_entry')
                return

            # Initial stop loss (different for long vs short) - BREAKEVEN ENABLED
            breakeven_active = current_profit_pct >= self.breakeven_trigger_pct

            if position_direction == 'long':
                if breakeven_active:
                    # BREAKEVEN: Stop loss at entry price (breakeven)
                    stop_loss_price = entry_price
                    stop_triggered = current_price <= stop_loss_price
                    print(f"[DEBUG] Breakeven stop long: {stop_loss_price:.2f} (entry price)")
                else:
                    # Initial: Stop loss below entry price
                    stop_loss_price = entry_price * (1 - self.initial_stop_loss_pct)
                    stop_triggered = current_price <= stop_loss_price
                    print(f"[DEBUG] Initial stop loss long: {stop_loss_price:.2f} ({self.initial_stop_loss_pct*100:.1f}% below entry)")
            else:  # SHORT
                if breakeven_active:
                    # BREAKEVEN: Stop loss at entry price (breakeven)
                    stop_loss_price = entry_price
                    stop_triggered = current_price >= stop_loss_price
                    print(f"[DEBUG] Breakeven stop short: {stop_loss_price:.2f} (entry price)")
                else:
                    # Initial: Stop loss above entry price
                    stop_loss_price = entry_price * (1 + self.initial_stop_loss_pct)
                    stop_triggered = current_price >= stop_loss_price
                    print(f"[DEBUG] Initial stop loss short: {stop_loss_price:.2f} ({self.initial_stop_loss_pct*100:.1f}% above entry)")

            if stop_triggered:
                exit_type = "BREAKEVEN STOP" if breakeven_active else "STOP LOSS"
                print(f"[{exit_type}] Exiting {position_direction.upper()} at bar {self.bar_count}, Price: {current_price:.2f}, Profit: {current_profit_pct*100:.2f}%")
                self.position.close()
                # Reset tracking variables
                if hasattr(self, 'highest_since_entry'):
                    delattr(self, 'highest_since_entry')
                if hasattr(self, 'lowest_since_entry'):
                    delattr(self, 'lowest_since_entry')
                return
        
        # Entry logic - only if no position is open
        if not self.position:
            # DYNAMIC PATTERN SELECTION - choose strongest signal above minimum strength
            selected_pattern, pattern_signal = self.select_best_pattern()

            # Check if we have a valid pattern signal
            if selected_pattern is None:
                print(f"[DEBUG] No pattern meets minimum strength requirement ({self.min_signal_strength})")
                return

            # DEBUG: Print pattern analysis
            signal_strength = abs(pattern_signal) / 100.0
            print(f"[DEBUG] Pattern scan: {selected_pattern}={pattern_signal} (strength: {signal_strength:.1f})")

            # TREND, MOMENTUM, AND VOLUME CONFIRMATION
            trade_direction = 'long' if pattern_signal == 100 else 'short'

            # Check trend confirmation
            trend_confirmed = self.check_trend_confirmation(trade_direction)
            print(f"[DEBUG] Trend confirmation for {trade_direction}: {trend_confirmed}")

            # Check momentum confirmation
            momentum_confirmed = self.check_momentum_confirmation(trade_direction)
            print(f"[DEBUG] Momentum confirmation (RSI={self.rsi[-1]:.1f}): {momentum_confirmed}")

            # Check volume confirmation
            volume_confirmed = self.check_volume_confirmation()
            print(f"[DEBUG] Volume confirmation: {volume_confirmed}")

            # REQUIRE 2 OUT OF 3 CONFIRMATIONS
            confirmations_count = sum([trend_confirmed, momentum_confirmed, volume_confirmed])
            all_confirmed = confirmations_count >= 2

            if not all_confirmed:
                print(f"[DEBUG] Entry rejected - missing confirmations")
                return

            # TWO-SIDED ENTRY: Long on bullish (+100), Short on bearish (-100)
            if pattern_signal == 100:
                # BULLISH PATTERN - Go LONG (with all confirmations)
                print(f"[LONG ENTRY] {selected_pattern} bullish pattern (+100) at bar {self.bar_count}")
                print(f"[CONFIRMATIONS] Trend: YES, Momentum: YES, Volume: YES")

                # Calculate position size based on risk percentage
                current_price = self.data.Close[-1]
                stop_loss_price = current_price * (1 - self.initial_stop_loss_pct)
                stop_distance = current_price - stop_loss_price

                # Calculate risk amount (2% of equity)
                risk_amount = self.equity * self.risk_percentage

                # Calculate position size as FRACTION of equity (backtesting.py style)
                if stop_distance > 0:
                    # Calculate how much equity to risk
                    position_fraction = min(risk_amount / (current_price * (stop_distance / current_price)), 0.10)
                    position_fraction = max(0.001, position_fraction)  # Minimum 0.1% position
                else:
                    position_fraction = 0.001  # Minimum position

                # Calculate position value and units for display
                position_value = position_fraction * self.equity
                position_units = position_value / current_price

                # DEBUG: Print position sizing calculations
                print(f"[DEBUG] Position size calc: price={current_price:.2f}, stop_loss={stop_loss_price:.2f}")
                print(f"[DEBUG] Risk amount: ${risk_amount:.2f} ({self.risk_percentage*100}% of equity)")
                print(f"[DEBUG] Stop distance: {stop_distance:.2f}")
                print(f"[DEBUG] Position fraction: {position_fraction:.6f} ({position_fraction*100:.2f}% of equity)")
                print(f"[DEBUG] Position value: ${position_value:.2f}, Units: {position_units:.4f}")

                # Execute LONG order
                print(f"[TRADE EXECUTING] LONG {position_fraction:.4f} fraction ({position_fraction*100:.2f}% equity) at ${current_price:.2f}")
                self.buy(size=position_fraction)
                self.trade_count += 1
                # Track entry bar and direction for exits
                self.entry_bar = self.bar_count
                self.position_direction = 'long'
                # Reset partial exit flags
                self.partial_exit_3pct = False
                self.partial_exit_6pct = False
                print(f"[TRADE EXECUTED] Long trade #{self.trade_count} opened at bar {self.entry_bar}")

            elif pattern_signal == -100:
                # BEARISH PATTERN - Go SHORT (with all confirmations)
                print(f"[SHORT ENTRY] {selected_pattern} bearish pattern (-100) at bar {self.bar_count}")
                print(f"[CONFIRMATIONS] Trend: YES, Momentum: YES, Volume: YES")

                # Calculate position size based on risk percentage
                current_price = self.data.Close[-1]
                stop_loss_price = current_price * (1 + self.initial_stop_loss_pct)  # Stop loss above price for shorts
                stop_distance = stop_loss_price - current_price

                # Calculate risk amount (2% of equity)
                risk_amount = self.equity * self.risk_percentage

                # Calculate position size as FRACTION of equity (backtesting.py style)
                if stop_distance > 0:
                    # Calculate how much equity to risk
                    position_fraction = min(risk_amount / (current_price * (stop_distance / current_price)), 0.10)
                    position_fraction = max(0.001, position_fraction)  # Minimum 0.1% position
                else:
                    position_fraction = 0.001  # Minimum position

                # Calculate position value and units for display
                position_value = position_fraction * self.equity
                position_units = position_value / current_price

                # DEBUG: Print position sizing calculations
                print(f"[DEBUG] Position size calc: price={current_price:.2f}, stop_loss={stop_loss_price:.2f}")
                print(f"[DEBUG] Risk amount: ${risk_amount:.2f} ({self.risk_percentage*100}% of equity)")
                print(f"[DEBUG] Stop distance: {stop_distance:.2f}")
                print(f"[DEBUG] Position fraction: {position_fraction:.6f} ({position_fraction*100:.2f}% of equity)")
                print(f"[DEBUG] Position value: ${position_value:.2f}, Units: {position_units:.4f}")

                # Execute SHORT order
                print(f"[TRADE EXECUTING] SHORT {position_fraction:.4f} fraction ({position_fraction*100:.2f}% equity) at ${current_price:.2f}")
                self.sell(size=position_fraction)
                self.trade_count += 1
                # Track entry bar and direction for exits
                self.entry_bar = self.bar_count
                self.position_direction = 'short'
                # Reset partial exit flags
                self.partial_exit_3pct = False
                self.partial_exit_6pct = False
                print(f"[TRADE EXECUTED] Short trade #{self.trade_count} opened at bar {self.entry_bar}")

            else:
                print(f"[DEBUG] No strong pattern signal (best: {selected_pattern}={pattern_signal})")
        else:
            print(f"[DEBUG] Skipping entry - position already open")

# Load and prepare data
print("[INFO] Loading data...")

# CHANGE TIMEFRAME HERE: '1d', '4h', '1h', '15m', '5m', etc.
data_timeframe = '4h'  # Change this to test different timeframes
data_filename = f'BTC-USD-{data_timeframe}.csv'

price_data = pd.read_csv(f'C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/{data_filename}')
print(f"[INFO] Using {data_timeframe} timeframe data from {data_filename}")
print(f"[INFO] Available timeframes: 1d, 4h, 1h, 15m, 5m (collect with --timeframe parameter)")

# Clean column names
price_data.columns = price_data.columns.str.strip().str.lower()

# Drop any unnamed columns
price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

# Ensure proper column mapping
required_columns = ['open', 'high', 'low', 'close', 'volume']
for col in required_columns:
    if col not in price_data.columns:
        print(f"[ERROR] Missing required column: {col}")
        print(f"[DEBUG] Available columns: {list(price_data.columns)}")
        raise ValueError(f"Missing required column: {col}")

# Rename columns to proper case for backtesting.py
price_data = price_data.rename(columns={
    'open': 'Open',
    'high': 'High', 
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

# Set datetime index - FIXED: Check for datetime column
if 'datetime' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['datetime'])
    print(f"[DEBUG] Using 'datetime' column for index")
elif 'timestamp' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['timestamp'])
    print(f"[DEBUG] Using 'timestamp' column for index")
elif 'date' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['date'])
    print(f"[DEBUG] Using 'date' column for index")
elif 'time' in price_data.columns:
    price_data.index = pd.to_datetime(price_data['time'])
    print(f"[DEBUG] Using 'time' column for index")
else:
    print("[WARNING] No timestamp column found, using index as time")
    price_data.index = pd.to_datetime(price_data.index)

print(f"[INFO] Data loaded: {len(price_data)} rows, {len(price_data.columns)} columns")
print(f"[DEBUG] Data columns: {list(price_data.columns)}")
print(f"[DEBUG] Data range: {price_data.index[0]} to {price_data.index[-1]}")
print(f"[DEBUG] Sample data (first 3 rows):")
print(price_data.head(3))

# Verify data structure for backtesting.py
print(f"[DEBUG] Checking data structure...")
print(f"[DEBUG] Index type: {type(price_data.index)}")
print(f"[DEBUG] Required columns present: {'Open' in price_data.columns}, {'High' in price_data.columns}, {'Low' in price_data.columns}, {'Close' in price_data.columns}, {'Volume' in price_data.columns}")

# Run backtest with margin buffer
print("[INFO] Starting backtest with margin buffer...")
bt = Backtest(price_data, PatternCatalyst, cash=1000000, commission=.002, margin=0.1)
stats = bt.run()
print(stats)
print(stats._strategy)

# Check if there are open trades and close them
if hasattr(stats._strategy, 'position') and stats._strategy.position.size != 0:
    print(f"[INFO] Closing open position at end of backtest: {stats._strategy.position.size} units")
    # This would normally be handled by finalize_trades=True, but let's add it manually
    print("[INFO] Adding finalize_trades=True to get complete stats...")

# Run again with finalize_trades=True and margin buffer
print("[INFO] Re-running with finalize_trades=True and margin buffer...")
bt_final = Backtest(price_data, PatternCatalyst, cash=1000000, commission=.002, margin=0.1, finalize_trades=True)
stats_final = bt_final.run()
print("\n" + "="*50)
print("FINAL STATS WITH CLOSED TRADES")
print("="*50)
print(stats_final)
print(f"\nTotal trades executed: {len(stats_final._trades)}")
if len(stats_final._trades) > 0:
    print(f"Win rate: {stats_final['Win Rate [%]']:.1f}%")
    print(f"Average trade: {stats_final['Avg. Trade [%]']:.2f}%")