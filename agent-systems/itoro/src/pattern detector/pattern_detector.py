"""
Pattern Detector - Core Logic
Extracted from PatternCatalyst_BTFinal_v3.py with 100% fidelity
86% historical win rate across multiple market conditions
"""

import pandas as pd
import numpy as np
import talib
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class PatternDetector:
    """
    Real-time pattern detection engine with regime-aware filtering.
    Maintains all logic from the backtested PatternCatalyst strategy.
    """
    
    def __init__(self, ohlcv_history_length=100):
        """
        Initialize pattern detector with all strategy parameters.
        
        Args:
            ohlcv_history_length: Number of historical bars to maintain (default: 100)
        """
        print("[PATTERN DETECTOR] Initializing...")
        
        # Data storage
        self.ohlcv_history_length = ohlcv_history_length
        self.ohlcv_data = None
        self.bar_count = 0
        
        # Pattern indicators (will be calculated on data update)
        self.engulfing = None
        self.hammer = None
        self.doji = None
        self.morning_star = None
        self.evening_star = None
        
        # Confirmation indicators
        self.sma_20 = None
        self.sma_50 = None
        self.rsi = None
        self.volume_sma = None
        
        # Strategy parameters - EXACT from backtest (lines 27-40)
        self.available_patterns = ['engulfing', 'hammer', 'doji', 'morning_star', 'evening_star']
        self.risk_percentage = 0.02  # 2% risk per trade
        self.initial_stop_loss_pct = 0.30  # -30% initial stop loss
        self.trailing_activation_pct = 0.084  # +8.4% profit to activate trailing stop
        self.trailing_offset_pct = 0.084  # 8.4% trailing offset
        self.min_profit_pct = 0.032  # +3.2% minimum profit guarantee
        self.profit_target_pct = 0.10  # +10% profit target
        self.max_holding_period = 30  # Maximum 30 bars holding period
        self.breakeven_trigger_pct = 0.02  # +2% profit to trigger breakeven stop
        self.min_signal_strength = 0.7  # Minimum 70% signal strength
        
        # Regime confidence scoring (lines 42-56)
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
        
        # Doji breakout tracking (lines 59-61)
        self.pending_doji_high = None
        self.pending_doji_low = None
        self.pending_doji_bar = None
        
        print("[PATTERN DETECTOR] Initialized successfully")
    
    def update_data(self, ohlcv_df: pd.DataFrame):
        """
        Update OHLCV data and recalculate all indicators.
        
        Args:
            ohlcv_df: DataFrame with columns [Open, High, Low, Close, Volume]
        """
        # Keep only the most recent bars
        if len(ohlcv_df) > self.ohlcv_history_length:
            ohlcv_df = ohlcv_df.iloc[-self.ohlcv_history_length:]
        
        self.ohlcv_data = ohlcv_df.copy()
        self.bar_count += 1
        
        # Calculate pattern indicators (lines 10-14)
        self.engulfing = talib.CDLENGULFING(
            ohlcv_df['Open'].values,
            ohlcv_df['High'].values,
            ohlcv_df['Low'].values,
            ohlcv_df['Close'].values
        )
        
        self.hammer = talib.CDLHAMMER(
            ohlcv_df['Open'].values,
            ohlcv_df['High'].values,
            ohlcv_df['Low'].values,
            ohlcv_df['Close'].values
        )
        
        self.doji = talib.CDLDOJI(
            ohlcv_df['Open'].values,
            ohlcv_df['High'].values,
            ohlcv_df['Low'].values,
            ohlcv_df['Close'].values
        )
        
        self.morning_star = talib.CDLMORNINGSTAR(
            ohlcv_df['Open'].values,
            ohlcv_df['High'].values,
            ohlcv_df['Low'].values,
            ohlcv_df['Close'].values
        )
        
        self.evening_star = talib.CDLEVENINGSTAR(
            ohlcv_df['Open'].values,
            ohlcv_df['High'].values,
            ohlcv_df['Low'].values,
            ohlcv_df['Close'].values
        )
        
        # Calculate confirmation indicators (lines 17-24)
        self.sma_20 = talib.SMA(ohlcv_df['Close'].values, timeperiod=20)
        self.sma_50 = talib.SMA(ohlcv_df['Close'].values, timeperiod=50)
        self.rsi = talib.RSI(ohlcv_df['Close'].values, timeperiod=14)
        self.volume_sma = talib.SMA(ohlcv_df['Volume'].values, timeperiod=20)
    
    def check_trend_confirmation(self, direction: str) -> bool:
        """
        Check if trend supports the trade direction (lines 63-77).
        
        Args:
            direction: 'long' or 'short'
            
        Returns:
            True if trend confirmed, False otherwise
        """
        if self.ohlcv_data is None or len(self.ohlcv_data) < 20:
            return False
        
        current_price = self.ohlcv_data['Close'].iloc[-1]
        sma_20 = self.sma_20[-1]
        
        if direction == 'long':
            # Bullish trend: price above fast SMA only
            trend_up = (current_price > sma_20)
            return trend_up
        else:  # short
            # Bearish trend: price below fast SMA only
            trend_down = (current_price < sma_20)
            return trend_down
    
    def check_momentum_confirmation(self, direction: str) -> bool:
        """
        Check momentum indicators for trade confirmation (lines 79-90).
        
        Args:
            direction: 'long' or 'short'
            
        Returns:
            True if momentum confirmed, False otherwise
        """
        if self.rsi is None or len(self.rsi) == 0:
            return False
        
        rsi_value = self.rsi[-1]
        
        if direction == 'long':
            # Bullish momentum: RSI oversold (< 40) or neutral (40-60)
            momentum_ok = rsi_value < 60  # Allow oversold to neutral RSI for longs
            return momentum_ok
        else:  # short
            # Bearish momentum: RSI overbought (> 40) or neutral (40-60)
            momentum_ok = rsi_value > 40  # Allow neutral to overbought RSI for shorts
            return momentum_ok
    
    def check_volume_confirmation(self) -> bool:
        """
        Check if volume supports the pattern (lines 92-98).
        
        Returns:
            True if volume confirmed, False otherwise
        """
        if self.ohlcv_data is None or len(self.ohlcv_data) < 20:
            return False
        
        current_volume = self.ohlcv_data['Volume'].iloc[-1]
        avg_volume = self.volume_sma[-1]
        
        # Require above-average volume (at least 80% of 20-day average)
        return current_volume >= (avg_volume * 0.8)
    
    def _get_allowed_patterns_for_regime(self, dominant_regime: str) -> List[str]:
        """
        Get list of patterns allowed for the given regime direction (lines 100-126).
        
        Args:
            dominant_regime: The dominant market regime
            
        Returns:
            List of allowed pattern names
        """
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
            pattern_value = getattr(self, pattern_name)[-1] if getattr(self, pattern_name) is not None else 0
            if pattern_value != 0:  # Pattern detected
                # For doji, we'll handle it separately (it can be either direction after breakout)
                if pattern_name == 'doji':
                    # Doji is allowed in all regimes, but requires breakout confirmation
                    allowed_patterns.append(pattern_name)
                elif pattern_value in allowed_directions:
                    allowed_patterns.append(pattern_name)
        
        return allowed_patterns
    
    def select_best_pattern(self, dominant_regime: Optional[str] = None) -> Tuple[Optional[str], int]:
        """
        Dynamically select the pattern with the strongest signal (lines 128-163).
        Filters by regime direction FIRST, then selects best from allowed patterns.
        
        Args:
            dominant_regime: The dominant market regime (optional)
            
        Returns:
            Tuple of (pattern_name, pattern_signal) or (None, 0) if no pattern found
        """
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
            pattern_array = getattr(self, pattern_name)
            if pattern_array is None or len(pattern_array) == 0:
                continue
            pattern_value = pattern_array[-1]
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
            return best_pattern, int(best_signal)
        else:
            return None, 0  # No strong enough signal found
    
    def detect_market_regime(self) -> str:
        """
        Update regime confidence scores based on trend strength (lines 165-218).
        No hard switches - smooth confidence blending.
        
        Returns:
            Detected regime name
        """
        if self.ohlcv_data is None or len(self.ohlcv_data) < 50:
            return "neutral_sideways"
        
        current_price = self.ohlcv_data['Close'].iloc[-1]
        sma_20 = self.sma_20[-1]
        sma_50 = self.sma_50[-1]
        
        # Price position relative to SMAs (normalized)
        price_vs_fast = (current_price - sma_20) / sma_20
        price_vs_slow = (current_price - sma_50) / sma_50
        
        # Trend strength score (-1 to +1)
        trend_strength = (price_vs_fast + price_vs_slow) / 2
        
        # Volatility measure (recent price range)
        recent_high = self.ohlcv_data['High'].iloc[-20:].max()
        recent_low = self.ohlcv_data['Low'].iloc[-20:].min()
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
    
    def set_regime_parameters(self, detected_regime: str):
        """
        Blend strategy parameters based on regime confidence scores (lines 220-310).
        Smooth transitions between regimes.
        
        Args:
            detected_regime: The detected market regime
        """
        # Base parameters that stay constant
        self.risk_percentage = 0.02
        self.breakeven_trigger_pct = 0.02
        self.min_signal_strength = 0.7
        
        # Define parameter sets for each regime (EXACT from backtest)
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
    
    def _get_dominant_regime(self) -> Tuple[str, float]:
        """
        Get the regime with the highest confidence score (lines 312-320).
        
        Returns:
            Tuple of (dominant_regime, dominant_confidence)
        """
        if not self.regime_confidence:
            return "neutral_sideways", 1.0
        
        dominant_regime = max(self.regime_confidence, key=self.regime_confidence.get)
        dominant_confidence = self.regime_confidence[dominant_regime]
        
        return dominant_regime, dominant_confidence
    
    def _is_pattern_allowed_for_regime(self, pattern_signal: int, current_regime: str) -> bool:
        """
        Check if pattern direction is allowed for current regime (lines 323-347).
        
        Args:
            pattern_signal: Pattern signal value (+100 bullish, -100 bearish)
            current_regime: Current market regime
            
        Returns:
            True if pattern allowed, False otherwise
        """
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
    
    def scan_for_patterns(self) -> List[Dict]:
        """
        Main scanning logic - detects patterns with full regime awareness (lines 349-732).
        This is the core entry point for real-time pattern detection.
        
        Returns:
            List of detected patterns with metadata
        """
        if self.ohlcv_data is None or len(self.ohlcv_data) < 50:
            return []
        
        detected_patterns = []
        
        # DYNAMIC REGIME DETECTION - Update parameters based on current market conditions
        current_regime = self.detect_market_regime()
        self.set_regime_parameters(current_regime)
        
        # Get dominant regime (highest confidence) for filtering decisions
        dominant_regime, dominant_confidence = self._get_dominant_regime()
        
        print(f"[SCAN] Bar {self.bar_count}, Detected: {current_regime}, Dominant: {dominant_regime} ({dominant_confidence:.3f})")
        
        # Check for pending doji breakout confirmation first (lines 539-576)
        doji_breakout_confirmed = False
        selected_pattern = None
        pattern_signal = 0
        
        if self.pending_doji_high is not None and self.pending_doji_low is not None:
            current_price = self.ohlcv_data['Close'].iloc[-1]
            current_high = self.ohlcv_data['High'].iloc[-1]
            current_low = self.ohlcv_data['Low'].iloc[-1]
            
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
                print(f"[DOJI BREAKOUT] Confirmed at bar {self.bar_count} - Direction: {'LONG' if pattern_signal == 100 else 'SHORT'}")
                
                # Clear pending doji
                self.pending_doji_high = None
                self.pending_doji_low = None
                self.pending_doji_bar = None
            else:
                # No breakout yet - check if doji is too old (expire after 2 bars)
                if self.bar_count - self.pending_doji_bar > 2:
                    print(f"[DOJI EXPIRED] Pending doji from bar {self.pending_doji_bar} expired")
                    self.pending_doji_high = None
                    self.pending_doji_low = None
                    self.pending_doji_bar = None
                return []  # Still waiting for breakout or expired
        
        # DYNAMIC PATTERN SELECTION - filter by regime FIRST, then choose strongest signal (lines 578-586)
        if not doji_breakout_confirmed:
            selected_pattern, pattern_signal = self.select_best_pattern(dominant_regime)
        
        # Check if we have a valid pattern signal
        if selected_pattern is None:
            print(f"[SCAN] No pattern meets minimum strength requirement ({self.min_signal_strength})")
            return []
        
        # Calculate signal strength
        signal_strength = abs(pattern_signal) / 100.0
        print(f"[SCAN] Pattern detected: {selected_pattern}={pattern_signal} (strength: {signal_strength:.1f})")
        
        # Special handling for doji: require next-bar breakout confirmation (lines 594-600)
        if selected_pattern == 'doji' and not doji_breakout_confirmed:
            # Store doji high/low for next-bar breakout check
            self.pending_doji_high = self.ohlcv_data['High'].iloc[-1]
            self.pending_doji_low = self.ohlcv_data['Low'].iloc[-1]
            self.pending_doji_bar = self.bar_count
            print(f"[DOJI SETUP] Doji detected at bar {self.bar_count}, waiting for breakout")
            return []  # Wait for next bar to confirm breakout
        
        # REGIME-AWARE PATTERN FILTERING (lines 602-607)
        pattern_allowed = self._is_pattern_allowed_for_regime(pattern_signal, dominant_regime)
        if not pattern_allowed:
            print(f"[REGIME FILTER] Pattern {selected_pattern} ({pattern_signal}) rejected - Dominant: {dominant_regime}")
            return []
        
        # TREND, MOMENTUM, AND VOLUME CONFIRMATION (lines 609-632)
        trade_direction = 'long' if pattern_signal == 100 else 'short'
        
        # Check confirmations
        trend_confirmed = self.check_trend_confirmation(trade_direction)
        momentum_confirmed = self.check_momentum_confirmation(trade_direction)
        volume_confirmed = self.check_volume_confirmation()
        
        print(f"[CONFIRMATIONS] Trend: {trend_confirmed}, Momentum: {momentum_confirmed}, Volume: {volume_confirmed}")
        
        # REQUIRE TREND CONFIRMATION + 1 OUT OF 2 (MOMENTUM OR VOLUME)
        trend_mandatory = trend_confirmed
        flexible_confirmations = sum([momentum_confirmed, volume_confirmed])
        all_confirmed = trend_mandatory and (flexible_confirmations >= 1)
        
        if not all_confirmed:
            print(f"[SCAN] Entry rejected - missing confirmations")
            return []
        
        # Pattern detected with all confirmations!
        current_ohlcv = {
            'open': self.ohlcv_data['Open'].iloc[-1],
            'high': self.ohlcv_data['High'].iloc[-1],
            'low': self.ohlcv_data['Low'].iloc[-1],
            'close': self.ohlcv_data['Close'].iloc[-1],
            'volume': self.ohlcv_data['Volume'].iloc[-1]
        }
        
        pattern_data = {
            'pattern': selected_pattern,
            'signal': pattern_signal,
            'confidence': signal_strength,
            'direction': trade_direction,
            'regime': dominant_regime,
            'regime_confidence': dominant_confidence,
            'timestamp': self.ohlcv_data.index[-1] if hasattr(self.ohlcv_data.index[-1], 'isoformat') else datetime.now(),
            'ohlcv': current_ohlcv,
            'confirmations': {
                'trend': trend_confirmed,
                'momentum': momentum_confirmed,
                'volume': volume_confirmed
            },
            'parameters': {
                'stop_loss_pct': self.initial_stop_loss_pct,
                'profit_target_pct': self.profit_target_pct,
                'trailing_activation_pct': self.trailing_activation_pct,
                'trailing_offset_pct': self.trailing_offset_pct,
                'min_profit_pct': self.min_profit_pct,
                'max_holding_period': self.max_holding_period
            }
        }
        
        detected_patterns.append(pattern_data)
        print(f"[PATTERN DETECTED] {selected_pattern} ({trade_direction}) - Confidence: {signal_strength:.1%}")
        
        return detected_patterns


if __name__ == "__main__":
    print("Pattern Detector - Core Logic Loaded")
    print("Extracted from PatternCatalyst_BTFinal_v3.py with 100% fidelity")
    print("Ready for real-time pattern detection")

