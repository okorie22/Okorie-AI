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

        # Regime confidence scoring (smooth parameter blending)
        self.regime_confidence = {
            "strong_uptrend": 0.0,
            "moderate_uptrend": 0.0,
            "strong_downtrend": 0.0,
            "moderate_downtrend": 0.0,
            "neutral_sideways": 1.0,  # Start with neutral sideways
            "sideways_bullish_bias": 0.0,
            "sideways_bearish_bias": 0.0,
            "sideways_moderate_bias": 0.0
        }

        # Confidence decay/smoothing factor
        self.confidence_decay = 0.95  # How quickly confidence fades
        self.confidence_boost = 0.2   # How much confidence increases per detection

        # Doji breakout tracking (for next-bar confirmation)
        self.pending_doji_high = None
        self.pending_doji_low = None
        self.pending_doji_bar = None

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

    def _get_allowed_patterns_for_regime(self, dominant_regime):
        """Get list of patterns allowed for the given regime direction"""
        allowed_patterns = []
        
        # Determine allowed directions based on regime
        if dominant_regime in ["strong_uptrend", "moderate_uptrend"]:
            # Uptrend: only bullish patterns allowed
            allowed_directions = [100]  # Only +100 (bullish)
        elif dominant_regime in ["strong_downtrend", "moderate_downtrend"]:
            # Downtrend: only bearish patterns allowed
            allowed_directions = [-100]  # Only -100 (bearish)
        else:
            # Sideways regimes: both directions allowed
            allowed_directions = [100, -100]  # Both bullish and bearish
        
        # Check each pattern and add if direction matches
        for pattern_name in self.available_patterns:
            pattern_value = getattr(self, pattern_name)[-1]
            if pattern_value != 0:  # Pattern detected
                # For doji, we'll handle it separately (it can be either direction after breakout)
                if pattern_name == 'doji':
                    # Doji is allowed in all regimes, but requires breakout confirmation
                    allowed_patterns.append(pattern_name)
                elif pattern_value in allowed_directions:
                    allowed_patterns.append(pattern_name)
        
        return allowed_patterns

    def select_best_pattern(self, dominant_regime=None):
        """Dynamically select the pattern with the strongest signal above minimum threshold
        Now filters by regime direction FIRST, then selects best from allowed patterns"""
        # If regime provided, filter patterns by regime direction first
        if dominant_regime:
            allowed_patterns = self._get_allowed_patterns_for_regime(dominant_regime)
            if not allowed_patterns:
                return None, 0  # No patterns allowed for this regime
        else:
            # Fallback: use all patterns (backward compatibility)
            allowed_patterns = self.available_patterns
        
        pattern_scores = {}

        # Only score patterns that are allowed for the regime
        for pattern_name in allowed_patterns:
            pattern_value = getattr(self, pattern_name)[-1]
            # Use absolute value to find strongest signal regardless of direction
            pattern_scores[pattern_name] = abs(pattern_value)

        if not pattern_scores:
            return None, 0  # No patterns found

        # Find the strongest pattern from allowed patterns
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
        """Update regime confidence scores based on trend strength (no hard switches)"""
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

        # Decay all confidence scores
        for regime in self.regime_confidence:
            self.regime_confidence[regime] *= self.confidence_decay

        # Boost confidence for detected regime
        detected_regime = None
        if trend_strength > 0.02:  # Strong uptrend
            detected_regime = "strong_uptrend"
        elif trend_strength > 0.008:  # Moderate uptrend
            detected_regime = "moderate_uptrend"
        elif trend_strength < -0.02:  # Strong downtrend
            detected_regime = "strong_downtrend"
        elif trend_strength < -0.008:  # Moderate downtrend
            detected_regime = "moderate_downtrend"
        elif abs(trend_strength) <= 0.002:  # Much stricter sideways definition
            detected_regime = "neutral_sideways"
        elif trend_strength > 0.001 and trend_strength <= 0.002:  # Slightly bullish sideways
            detected_regime = "sideways_bullish_bias"
        elif trend_strength < -0.001 and trend_strength >= -0.002:  # Slightly bearish sideways
            detected_regime = "sideways_bearish_bias"
        else:  # Moderate directional bias in sideways
            detected_regime = "sideways_moderate_bias"

        # Boost confidence for detected regime
        if detected_regime:
            self.regime_confidence[detected_regime] += self.confidence_boost
            # Ensure confidence doesn't exceed 1.0
            self.regime_confidence[detected_regime] = min(1.0, self.regime_confidence[detected_regime])

        print(f"[REGIME] Detected: {detected_regime}, Confidence: {self.regime_confidence[detected_regime]:.3f}")
        return detected_regime or "neutral_sideways"

    def set_regime_parameters(self, detected_regime):
        """Blend strategy parameters based on regime confidence scores (smooth transitions)"""

        # Base parameters that stay constant
        self.risk_percentage = 0.02
        self.breakeven_trigger_pct = 0.02
        self.min_signal_strength = 0.7

        # Define parameter sets for each regime
        regime_params = {
            "strong_uptrend": {
                "stop_loss": 0.25, "profit_target": 0.12, "hold_period": 48,
                "trailing_activation": 0.10, "trailing_offset": 0.08, "min_profit": 0.04
            },
            "moderate_uptrend": {
                "stop_loss": 0.20, "profit_target": 0.13, "hold_period": 42,
                "trailing_activation": 0.09, "trailing_offset": 0.07, "min_profit": 0.035
            },
            "strong_downtrend": {
                "stop_loss": 0.15, "profit_target": 0.15, "hold_period": 60,
                "trailing_activation": 0.08, "trailing_offset": 0.06, "min_profit": 0.03
            },
            "moderate_downtrend": {
                "stop_loss": 0.18, "profit_target": 0.14, "hold_period": 54,
                "trailing_activation": 0.085, "trailing_offset": 0.065, "min_profit": 0.0325
            },
            "neutral_sideways": {
                "stop_loss": 0.12, "profit_target": 0.08, "hold_period": 36,
                "trailing_activation": 0.06, "trailing_offset": 0.05, "min_profit": 0.025
            },
            "sideways_bullish_bias": {
                "stop_loss": 0.15, "profit_target": 0.10, "hold_period": 36,
                "trailing_activation": 0.08, "trailing_offset": 0.06, "min_profit": 0.03
            },
            "sideways_bearish_bias": {
                "stop_loss": 0.22, "profit_target": 0.14, "hold_period": 48,
                "trailing_activation": 0.09, "trailing_offset": 0.07, "min_profit": 0.035
            },
            "sideways_moderate_bias": {
                "stop_loss": 0.18, "profit_target": 0.12, "hold_period": 42,
                "trailing_activation": 0.085, "trailing_offset": 0.065, "min_profit": 0.0325
            }
        }

        # Calculate blended parameters based on confidence scores
        total_confidence = sum(self.regime_confidence.values())

        if total_confidence > 0:
            # Weighted average of all parameters
            self.initial_stop_loss_pct = sum(
                self.regime_confidence[regime] * regime_params[regime]["stop_loss"]
                for regime in self.regime_confidence
            ) / total_confidence

            self.profit_target_pct = sum(
                self.regime_confidence[regime] * regime_params[regime]["profit_target"]
                for regime in self.regime_confidence
            ) / total_confidence

            self.max_holding_period = int(sum(
                self.regime_confidence[regime] * regime_params[regime]["hold_period"]
                for regime in self.regime_confidence
            ) / total_confidence)

            self.trailing_activation_pct = sum(
                self.regime_confidence[regime] * regime_params[regime]["trailing_activation"]
                for regime in self.regime_confidence
            ) / total_confidence

            self.trailing_offset_pct = sum(
                self.regime_confidence[regime] * regime_params[regime]["trailing_offset"]
                for regime in self.regime_confidence
            ) / total_confidence

            self.min_profit_pct = sum(
                self.regime_confidence[regime] * regime_params[regime]["min_profit"]
                for regime in self.regime_confidence
            ) / total_confidence

        else:
            # Fallback to neutral sideways
            params = regime_params["neutral_sideways"]
            self.initial_stop_loss_pct = params["stop_loss"]
            self.profit_target_pct = params["profit_target"]
            self.max_holding_period = params["hold_period"]
            self.trailing_activation_pct = params["trailing_activation"]
            self.trailing_offset_pct = params["trailing_offset"]
            self.min_profit_pct = params["min_profit"]

        print(f"[PARAMETERS] Blended - SL={self.initial_stop_loss_pct*100:.1f}%, PT={self.profit_target_pct*100:.1f}%, Hold={self.max_holding_period} bars")
        print(f"[CONFIDENCE] Top regimes: {sorted(self.regime_confidence.items(), key=lambda x: x[1], reverse=True)[:3]}")

    def _get_dominant_regime(self):
        """Get the regime with the highest confidence score"""
        if not self.regime_confidence:
            return "neutral_sideways"

        dominant_regime = max(self.regime_confidence, key=self.regime_confidence.get)
        dominant_confidence = self.regime_confidence[dominant_regime]

        return dominant_regime, dominant_confidence


    def _is_pattern_allowed_for_regime(self, pattern_signal, current_regime):
        """Check if pattern direction is allowed for current regime"""
        # Bullish patterns (+100) only allowed in uptrend/sideways regimes
        # Bearish patterns (-100) only allowed in downtrend/sideways regimes
        # Sideways regimes allow both directions

        if pattern_signal == 100:  # Bullish pattern
            # Allow in uptrend regimes and sideways regimes
            allowed_regimes = [
                "strong_uptrend", "moderate_uptrend",
                "neutral_sideways", "sideways_bullish_bias",
                "sideways_bearish_bias", "sideways_moderate_bias"
            ]
            return current_regime in allowed_regimes

        elif pattern_signal == -100:  # Bearish pattern
            # Allow in downtrend regimes and sideways regimes
            allowed_regimes = [
                "strong_downtrend", "moderate_downtrend",
                "neutral_sideways", "sideways_bullish_bias",
                "sideways_bearish_bias", "sideways_moderate_bias"
            ]
            return current_regime in allowed_regimes

        return False  # Unknown pattern signal

    def next(self):
        self.bar_count += 1

        # DYNAMIC REGIME DETECTION - Update parameters based on current market conditions
        current_regime = self.detect_market_regime()
        self.set_regime_parameters(current_regime)

        # Get dominant regime (highest confidence) for filtering decisions
        dominant_regime, dominant_confidence = self._get_dominant_regime()

        # DEBUG: Print current bar status
        print(f"[DEBUG] Bar {self.bar_count}, Equity: ${self.equity:.2f}, Position: {self.position.size if self.position else 0}, Detected: {current_regime}, Dominant: {dominant_regime} ({dominant_confidence:.3f})")

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
                if not getattr(self, 'partial_exit_3pct', False):
                    print(f"[PARTIAL EXIT 3%] Taking 50% profit at bar {self.bar_count}, Price: {current_price:.2f}, Profit: {current_profit_pct*100:.2f}%")
                    self.position.close(portion=0.5)
                    self.partial_exit_3pct = True

            if current_profit_pct >= 0.06:  # 6% profit - take remaining 50%
                if not getattr(self, 'partial_exit_6pct', False):
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
            # Get dominant regime first (for pattern filtering)
            dominant_regime, dominant_confidence = self._get_dominant_regime()

            # Check for pending doji breakout confirmation first
            doji_breakout_confirmed = False
            if self.pending_doji_high is not None and self.pending_doji_low is not None:
                current_price = self.data.Close[-1]
                current_high = self.data.High[-1]
                current_low = self.data.Low[-1]
                
                # Check for breakout above doji high (long) or below doji low (short)
                breakout_long = current_high > self.pending_doji_high
                breakout_short = current_low < self.pending_doji_low
                
                if breakout_long or breakout_short:
                    # Doji breakout confirmed - determine direction
                    if breakout_long and breakout_short:
                        # Both breakouts - use stronger one
                        high_break = current_high - self.pending_doji_high
                        low_break = self.pending_doji_low - current_low
                        pattern_signal = 100 if high_break >= low_break else -100
                    else:
                        pattern_signal = 100 if breakout_long else -100
                    
                    selected_pattern = 'doji'
                    doji_breakout_confirmed = True
                    print(f"[DOJI BREAKOUT] Confirmed at bar {self.bar_count} - Breakout {'above high' if breakout_long else 'below low'}, Direction: {'LONG' if pattern_signal == 100 else 'SHORT'}")
                    
                    # Clear pending doji
                    self.pending_doji_high = None
                    self.pending_doji_low = None
                    self.pending_doji_bar = None
                else:
                    # No breakout yet - check if doji is too old (expire after 2 bars)
                    if self.bar_count - self.pending_doji_bar > 2:
                        print(f"[DOJI EXPIRED] Pending doji from bar {self.pending_doji_bar} expired (no breakout after 2 bars)")
                        self.pending_doji_high = None
                        self.pending_doji_low = None
                        self.pending_doji_bar = None
                    else:
                        # Still waiting for breakout
                        return
            
            # DYNAMIC PATTERN SELECTION - filter by regime FIRST, then choose strongest signal
            # Skip if doji breakout was just confirmed (already have pattern and signal)
            if not doji_breakout_confirmed:
                selected_pattern, pattern_signal = self.select_best_pattern(dominant_regime)

            # Check if we have a valid pattern signal
            if selected_pattern is None:
                print(f"[DEBUG] No pattern meets minimum strength requirement ({self.min_signal_strength})")
                return

            # DEBUG: Print pattern analysis
            signal_strength = abs(pattern_signal) / 100.0
            print(f"[DEBUG] Pattern scan: {selected_pattern}={pattern_signal} (strength: {signal_strength:.1f})")

            # Special handling for doji: require next-bar breakout confirmation
            # Skip this if doji breakout was just confirmed (already passed breakout check)
            if selected_pattern == 'doji' and not doji_breakout_confirmed:
                # Store doji high/low for next-bar breakout check
                self.pending_doji_high = self.data.High[-1]
                self.pending_doji_low = self.data.Low[-1]
                self.pending_doji_bar = self.bar_count
                print(f"[DOJI SETUP] Doji detected at bar {self.bar_count}, waiting for next-bar breakout (High: {self.pending_doji_high:.2f}, Low: {self.pending_doji_low:.2f})")
                return  # Wait for next bar to confirm breakout

            # REGIME-AWARE PATTERN FILTERING (for non-doji patterns and confirmed doji breakouts)
            # Use dominant regime (highest confidence) instead of detected regime for filtering
            pattern_allowed = self._is_pattern_allowed_for_regime(pattern_signal, dominant_regime)
            if not pattern_allowed:
                print(f"[REGIME FILTER] Pattern {selected_pattern} ({pattern_signal}) rejected - Detected: {current_regime}, Dominant: {dominant_regime} (confidence: {dominant_confidence:.3f})")
                return

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

            # REQUIRE TREND CONFIRMATION + 1 OUT OF 2 (MOMENTUM OR VOLUME)
            trend_mandatory = trend_confirmed
            flexible_confirmations = sum([momentum_confirmed, volume_confirmed])
            all_confirmed = trend_mandatory and (flexible_confirmations >= 1)
            confirmations_count = sum([trend_confirmed, momentum_confirmed, volume_confirmed])  # For display

            if not all_confirmed:
                print(f"[DEBUG] Entry rejected - missing confirmations")
                return

            # TWO-SIDED ENTRY: Long on bullish (+100), Short on bearish (-100)
            if pattern_signal == 100:
                # BULLISH PATTERN - Go LONG (with all confirmations)
                print(f"[LONG ENTRY] {selected_pattern} bullish pattern (+100) at bar {self.bar_count}")
                print(f"[CONFIRMATIONS] Trend: {'YES' if trend_confirmed else 'NO'} (MANDATORY), "
                      f"Momentum: {'YES' if momentum_confirmed else 'NO'}, "
                      f"Volume: {'YES' if volume_confirmed else 'NO'} "
                      f"({flexible_confirmations}/2 flexible, {confirmations_count}/3 total)")

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
                print(f"[CONFIRMATIONS] Trend: {'YES' if trend_confirmed else 'NO'} (MANDATORY), "
                      f"Momentum: {'YES' if momentum_confirmed else 'NO'}, "
                      f"Volume: {'YES' if volume_confirmed else 'NO'} "
                      f"({flexible_confirmations}/2 flexible, {confirmations_count}/3 total)")

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

# Load and prepare data for multiple symbols
print("[INFO] Loading data for multiple symbols...")

# CHANGE TIMEFRAME HERE: '1d', '4h', '1h', '15m', '5m', etc.
data_timeframe = '1d'  # Change this to test different timeframes

# Symbols to test
symbols = ['BTC','ETH', 'SOL', 'BNB']
print(f"[INFO] Testing symbols: {symbols}")
print(f"[INFO] Using {data_timeframe} timeframe")
print(f"[INFO] Available timeframes: 1d, 4h, 1h, 15m, 5m")
print(f"[INFO] Current timeframe: {data_timeframe} (change data_timeframe variable above)")

def load_symbol_data(symbol, timeframe):
    """Load and prepare data for a specific symbol"""
    data_filename = f'{symbol}-USD-{timeframe}.csv'

    try:
        price_data = pd.read_csv(f'C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/{data_filename}')
        print(f"[INFO] Loaded {symbol} data: {len(price_data)} rows")

        # Clean column names
        price_data.columns = price_data.columns.str.strip().str.lower()

        # Drop any unnamed columns
        price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

        # Ensure proper column mapping
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in price_data.columns:
                print(f"[ERROR] Missing required column: {col} for {symbol}")
                print(f"[DEBUG] Available columns: {list(price_data.columns)}")
                return None

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
        elif 'timestamp' in price_data.columns:
            price_data.index = pd.to_datetime(price_data['timestamp'])
        elif 'date' in price_data.columns:
            price_data.index = pd.to_datetime(price_data['date'])
        elif 'time' in price_data.columns:
            price_data.index = pd.to_datetime(price_data['time'])
        else:
            print(f"[WARNING] No timestamp column found for {symbol}, using index as time")
            price_data.index = pd.to_datetime(price_data.index)

        return price_data

    except FileNotFoundError:
        print(f"[WARNING] Data file not found for {symbol}: {data_filename}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load data for {symbol}: {e}")
        return None

def run_symbol_backtest(symbol, price_data):
    """Run backtest for a specific symbol and return results"""
    print(f"\n{'='*60}")
    print(f"BACKTESTING {symbol}")
    print('='*60)

    try:
        # Run backtest with margin buffer
        print(f"[INFO] Starting {symbol} backtest...")
        bt = Backtest(price_data, PatternCatalyst, cash=1000000, commission=.002, margin=0.1)
        stats = bt.run()

        # Run again with finalize_trades=True
        print(f"[INFO] Finalizing {symbol} trades...")
        bt_final = Backtest(price_data, PatternCatalyst, cash=1000000, commission=.002, margin=0.1, finalize_trades=True)
        stats_final = bt_final.run()

        return stats_final

    except Exception as e:
        print(f"[ERROR] Backtest failed for {symbol}: {e}")
        return None

# Run backtests for all symbols
all_results = {}
successful_symbols = []

for symbol in symbols:
    price_data = load_symbol_data(symbol, data_timeframe)
    if price_data is not None:
        stats = run_symbol_backtest(symbol, price_data)
        if stats is not None:
            all_results[symbol] = stats
            successful_symbols.append(symbol)

# Display aggregated results
if successful_symbols:
    print(f"\n{'='*80}")
    print("MULTI-SYMBOL AGGREGATED RESULTS")
    print('='*80)

    total_return = 0
    total_trades = 0
    total_wins = 0
    total_win_rate = 0
    max_dd = 0
    min_dd = 0

    for symbol in successful_symbols:
            stats = all_results[symbol]
            symbol_return = stats['Return [%]']
            symbol_trades = len(stats._trades)
            symbol_win_rate = stats.get('Win Rate [%]', 0)
            symbol_max_dd = stats.get('Max. Drawdown [%]', 0)

            total_return += symbol_return
            total_trades += symbol_trades
            if symbol_trades > 0:
                total_wins += int(symbol_trades * symbol_win_rate / 100)
            max_dd = max(max_dd, abs(symbol_max_dd))

            print(f"\n{symbol}:")
            print(f"  Return [%]: {symbol_return:.2f}")
            print(f"  Buy & Hold Return [%]: {stats.get('Buy & Hold Return [%]', 0):.2f}")
            print(f"  Max. Drawdown [%]: {symbol_max_dd:.2f}")
            print(f"  Avg. Drawdown [%]: {stats.get('Avg. Drawdown [%]', 0):.2f}")
            print(f"  # Trades: {symbol_trades}")
            print(f"  Win Rate [%]: {symbol_win_rate:.1f}")
            print(f"  Best Trade [%]: {stats.get('Best Trade [%]', 0):.2f}")
            print(f"  Worst Trade [%]: {stats.get('Worst Trade [%]', 0):.2f}")
            print(f"  Avg. Trade [%]: {stats.get('Avg. Trade [%]', 0):.2f}")
            print(f"  Profit Factor: {stats.get('Profit Factor', 0):.2f}")
            print(f"  Expectancy [%]: {stats.get('Expectancy [%]', 0):.2f}")
            print(f"  Sharpe Ratio: {stats.get('Sharpe Ratio', 0):.2f}")
            print(f"  Sortino Ratio: {stats.get('Sortino Ratio', 0):.2f}")
            print(f"  Calmar Ratio: {stats.get('Calmar Ratio', 0):.2f}")
            print(f"  Max. Trade Duration: {stats.get('Max. Trade Duration', 'N/A')}")
            print(f"  Avg. Trade Duration: {stats.get('Avg. Trade Duration', 'N/A')}")
            print(f"  Exposure Time [%]: {stats.get('Exposure Time [%]', 0):.2f}")
            print(f"  SQN: {stats.get('SQN', 0):.2f}")
            print(f"  Kelly Criterion: {stats.get('Kelly Criterion', 0):.2f}")

    avg_return = total_return / len(successful_symbols)
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

    print(f"\n{'='*40}")
    print("AGGREGATED SUMMARY:")
    print(f"  Symbols tested: {len(successful_symbols)}")
    print(f"  Average return: {avg_return:.2f}%")
    print(f"  Total trades: {total_trades}")
    print(f"  Overall win rate: {overall_win_rate:.1f}%")
    print(f"  Max drawdown (worst symbol): {max_dd:.2f}%")

    # Calculate additional aggregated stats
    total_pf = 0
    total_expectancy = 0
    total_sharpe = 0
    total_sortino = 0
    total_calmar = 0
    total_sqn = 0

    for symbol in successful_symbols:
        stats = all_results[symbol]
        total_pf += stats.get('Profit Factor', 0)
        total_expectancy += stats.get('Expectancy [%]', 0)
        total_sharpe += stats.get('Sharpe Ratio', 0)
        total_sortino += stats.get('Sortino Ratio', 0)
        total_calmar += stats.get('Calmar Ratio', 0)
        total_sqn += stats.get('SQN', 0)

    avg_pf = total_pf / len(successful_symbols)
    avg_expectancy = total_expectancy / len(successful_symbols)
    avg_sharpe = total_sharpe / len(successful_symbols)
    avg_sortino = total_sortino / len(successful_symbols)
    avg_calmar = total_calmar / len(successful_symbols)
    avg_sqn = total_sqn / len(successful_symbols)

    print(f"  Average Profit Factor: {avg_pf:.2f}")
    print(f"  Average Expectancy [%]: {avg_expectancy:.2f}")
    print(f"  Average Sharpe Ratio: {avg_sharpe:.2f}")
    print(f"  Average Sortino Ratio: {avg_sortino:.2f}")
    print(f"  Average Calmar Ratio: {avg_calmar:.2f}")
    print(f"  Average SQN: {avg_sqn:.2f}")
    print(f"  Prop firm target: 12% return, 9% max DD")
    print(f"  Status: {'PASS' if avg_return >= 12 and max_dd <= 9 else 'FAIL'}")

else:
    print("[ERROR] No successful backtests completed")