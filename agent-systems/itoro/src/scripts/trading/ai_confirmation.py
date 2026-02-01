"""
AI Confirmation Service for Anarcho Capital's Copy Trading System
Provides lightweight AI confirmation for new token buy decisions using volume + volatility analysis
"""

import os
import time
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, Tuple
import requests

from src.config import (
    AI_CONFIRMATION_ENABLED,
    AI_CONFIRMATION_CONFIDENCE_THRESHOLD,
    AI_CONFIRMATION_CACHE_MINUTES,
    AI_CONFIRMATION_LOOKBACK_DAYS,
    AI_CONFIRMATION_TIMEFRAME,
    AI_CONFIRMATION_MIN_CANDLES,
    AI_VOLUME_DELTA_PERIODS,
    AI_VOLATILITY_ATR_PERIODS,
    AI_VOLUME_SURGE_THRESHOLD,
    AI_MAX_VOLATILITY_THRESHOLD,
    AI_CONFIRMATION_WEIGHTS,
    AI_EXIT_TARGETS,
    AI_EXIT_STOP_LOSS,
    AI_CONFIRMATION_PROMPT,
    AI_MODEL,
    AI_TEMPERATURE,
    AI_MAX_TOKENS
)
from src.scripts.shared_services.logger import debug, info, warning, error
from src.ta_indicators import ta

class AIConfirmation:
    """Lightweight AI confirmation using volume + volatility analysis"""
    
    def __init__(self):
        self.analysis_cache = {}
        self.cache_expiry = {}
        
        # Initialize AI model for enhanced analysis - direct DeepSeek client
        try:
            import openai
            import os
            
            deepseek_key = os.getenv("DEEPSEEK_KEY")
            if deepseek_key:
                self.deepseek_client = openai.OpenAI(
                    api_key=deepseek_key,
                    base_url="https://api.deepseek.com"
                )
            else:
                warning("No DEEPSEEK_KEY found - AI confirmation disabled")
                self.deepseek_client = None
        except Exception as e:
            warning(f"Failed to initialize DeepSeek client: {e}")
            self.deepseek_client = None
    
    def _determine_analysis_mode(self, candle_count: int) -> str:
        """Determine which analysis mode to use based on available data"""
        from src.config import (
            AI_CONFIRMATION_LAUNCH_MODE_MAX,
            AI_CONFIRMATION_ACTIVE_MODE_MAX
        )
        
        if candle_count <= AI_CONFIRMATION_LAUNCH_MODE_MAX:
            return 'launch'
        elif candle_count <= AI_CONFIRMATION_ACTIVE_MODE_MAX:
            return 'active'
        else:
            return 'mature'
        
    def analyze_buy_opportunity(self, token_address: str) -> Dict[str, Any]:
        """
        Analyze if token passes buy confirmation
        
        Args:
            token_address: Token mint address to analyze
            
        Returns:
            {
                'approved': bool,
                'confidence': float,
                'reason': str,
                'exit_target_pct': float,  # Recommended exit %
                'stop_loss_pct': float,
                'analysis_data': dict
            }
        """
        try:
            # Check if analysis is enabled
            if not AI_CONFIRMATION_ENABLED:
                return self._create_approved_result("AI confirmation disabled")
            
            # Check cache first
            cached_result = self._get_cached_analysis(token_address)
            if cached_result:
                return cached_result
            
            # Fetch OHLCV data (1-minute primary)
            ohlcv_1m = self._fetch_ohlcv_data(token_address, '1m')
            if ohlcv_1m is None or ohlcv_1m.empty:
                return self._create_rejected_result("No OHLCV data available")

            # Determine analysis mode
            candle_count = len(ohlcv_1m)
            mode = self._determine_analysis_mode(candle_count)
            info(f"🧠 AI Analysis: {mode.upper()} mode | {candle_count} candles scanned")

            # Route to appropriate analysis method
            if mode == 'launch':
                result = self._analyze_launch_mode(ohlcv_1m, token_address)
            elif mode == 'active':
                result = self._analyze_active_mode(ohlcv_1m, token_address)
            else:
                result = self._analyze_mature_mode(ohlcv_1m, token_address)

            # Cache and return
            self._cache_analysis(token_address, result)
            return result
            
        except Exception as e:
            token_display = token_address[:8] if token_address and isinstance(token_address, str) else "INVALID"
            error(f"Error in AI confirmation analysis for {token_display}...: {e}")
            # Fail-open: allow trade if AI confirmation fails
            return self._create_approved_result(f"AI analysis error: {str(e)}")
    
    def _fetch_ohlcv_data(self, token_address: str, timeframe: str = '1m') -> Optional[pd.DataFrame]:
        """Fetch OHLCV data using free multi-source collector with fallback"""
        try:
            # Handle None or invalid token addresses
            if not token_address or not isinstance(token_address, str):
                warning("Invalid token address provided for OHLCV data")
                return None
            
            # Use OHLCV collector with fallback system
            from src.scripts.shared_services.ohlcv_collector import collect_token_data_with_fallback
            
            result = collect_token_data_with_fallback(
                token=token_address,
                days_back=AI_CONFIRMATION_LOOKBACK_DAYS,
                timeframe=timeframe
            )
            
            if result and result.get('data') is not None:
                df = result['data']
                
                # Ensure datetime column exists (collector may use 'timestamp')
                if 'datetime' not in df.columns:
                    if 'timestamp' in df.columns:
                        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
                    elif 'date' in df.columns:
                        df['datetime'] = pd.to_datetime(df['date'])
                    else:
                        # If no timestamp column, create from index
                        warning(f"No timestamp column found in OHLCV data for {token_address[:8]}...")
                        return None
                
                # Ensure required columns exist
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                if not all(col in df.columns for col in required_cols):
                    warning(f"Missing required OHLCV columns for {token_address[:8]}...")
                    return None
                
                # Sort by datetime
                df = df.sort_values('datetime').reset_index(drop=True)
                
                debug(f"✅ OHLCV data fetched via {result.get('source', 'unknown')}: {len(df)} candles")
                return df
            else:
                warning(f"No OHLCV data available from collector for {token_address[:8]}...")
                return None
                
        except Exception as e:
            warning(f"Error fetching OHLCV data via collector for {token_address[:8]}...: {e}")
            return None
    
    def _analyze_launch_mode(self, df: pd.DataFrame, token_address: str) -> Dict[str, Any]:
        """
        Launch Mode (≤3 candles): Volume-only analysis for brand new tokens
        Focus: Is there immediate buying interest?
        """
        try:
            volumes = df['volume'].values
            
            if len(volumes) == 0:
                return self._create_rejected_result("No volume data")
            
            # Simple volume check - is current volume significant?
            current_volume = volumes[-1]
            avg_volume = np.mean(volumes) if len(volumes) > 1 else current_volume
            
            # For very new tokens, look for ANY volume (not zero)
            if current_volume == 0:
                return self._create_rejected_result("Zero volume - no activity")
            
            # Calculate volume surge (be generous for new tokens)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Lower threshold for launch tokens (1.5x instead of 2x)
            from src.config import AI_VOLUME_SURGE_THRESHOLD
            if volume_ratio >= AI_VOLUME_SURGE_THRESHOLD:
                volume_score = min(1.0, 0.5 + (volume_ratio - 1.0) * 0.3)
            else:
                volume_score = max(0.3, 0.5 + (volume_ratio - 1.0) * 0.4)
            
            # In launch mode, approve if any reasonable volume exists
            confidence = volume_score
            approved = confidence >= 0.5  # Lower threshold for launch
            
            reason = f"Launch mode: {len(df)} candles, volume ratio {volume_ratio:.2f}x"
            
            return {
                'approved': approved,
                'confidence': confidence,
                'reason': reason,
                'exit_target_pct': None,
                'stop_loss_pct': None,
                'analysis_data': {
                    'mode': 'launch',
                    'volume_score': volume_score,
                    'volume_ratio': volume_ratio,
                    'ohlcv_candles': len(df)
                }
            }
        except Exception as e:
            error(f"Error in launch mode analysis: {e}")
            return self._create_rejected_result(f"Launch mode error: {e}")
    
    def _analyze_active_mode(self, df: pd.DataFrame, token_address: str) -> Dict[str, Any]:
        """
        Active Mode (4-50 candles): Volume + Volatility + Basic EMA
        Focus: Confirm momentum with stability indicators
        """
        try:
            # Calculate indicators
            volume_score = self._calculate_volume_signal(df)
            volatility_score = self._calculate_volatility_signal(df)
            
            # Calculate simple EMAs if enough data
            ema_score = 0.5  # Default neutral
            if len(df) >= 20:
                closes = df['close'].values
                ema9 = self._calculate_ema(closes, 9)
                ema20 = self._calculate_ema(closes, 20)
                
                # Bullish if EMA9 > EMA20
                if ema9[-1] > ema20[-1]:
                    ema_score = 0.7
                elif ema9[-1] < ema20[-1]:
                    ema_score = 0.3
            
            # Weighted confidence (volume heavy, with volatility and EMA support)
            confidence = (
                0.5 * volume_score +
                0.3 * volatility_score +
                0.2 * ema_score
            )
            
            from src.config import AI_CONFIRMATION_CONFIDENCE_THRESHOLD
            approved = confidence >= AI_CONFIRMATION_CONFIDENCE_THRESHOLD
            
            # Enhanced reason with threshold info
            threshold_info = f" (need {AI_CONFIRMATION_CONFIDENCE_THRESHOLD:.1%})" if not approved else ""
            reason = f"Active mode: vol={volume_score:.1%}, volatility={volatility_score:.1%}, ema={ema_score:.1%}{threshold_info}"
            
            return {
                'approved': approved,
                'confidence': confidence,
                'reason': reason,
                'exit_target_pct': None,
                'stop_loss_pct': None,
                'analysis_data': {
                    'mode': 'active',
                    'volume_score': volume_score,
                    'volatility_score': volatility_score,
                    'ema_score': ema_score,
                    'ohlcv_candles': len(df)
                }
            }
        except Exception as e:
            error(f"Error in active mode analysis: {e}")
            return self._create_rejected_result(f"Active mode error: {e}")
    
    def _analyze_mature_mode(self, df: pd.DataFrame, token_address: str) -> Dict[str, Any]:
        """
        Mature Mode (>50 candles): Full technical analysis
        Focus: Complete indicator suite with liquidity and trend confirmation
        """
        try:
            # Calculate all indicators
            volume_score = self._calculate_volume_signal(df)
            volatility_score = self._calculate_volatility_signal(df)
            
            # Calculate EMAs
            closes = df['close'].values
            ema9 = self._calculate_ema(closes, 9)
            ema20 = self._calculate_ema(closes, 20)
            
            # EMA trend score
            if ema9[-1] > ema20[-1]:
                ema_score = 0.8
            elif ema9[-1] < ema20[-1]:
                ema_score = 0.2
            else:
                ema_score = 0.5
            
            # Price momentum (recent vs historical)
            recent_close = closes[-1]
            historical_avg = np.mean(closes[:-10]) if len(closes) > 10 else np.mean(closes)
            momentum_score = 0.7 if recent_close > historical_avg else 0.3
            
            # Full weighted confidence
            confidence = (
                0.4 * volume_score +
                0.3 * volatility_score +
                0.2 * ema_score +
                0.1 * momentum_score
            )
            
            from src.config import AI_CONFIRMATION_CONFIDENCE_THRESHOLD
            approved = confidence >= AI_CONFIRMATION_CONFIDENCE_THRESHOLD
            
            # Enhanced reason with threshold info
            threshold_info = f" (need {AI_CONFIRMATION_CONFIDENCE_THRESHOLD:.1%})" if not approved else ""
            reason = f"Mature mode: vol={volume_score:.1%}, volatility={volatility_score:.1%}, ema={ema_score:.1%}, momentum={momentum_score:.1%}{threshold_info}"
            
            return {
                'approved': approved,
                'confidence': confidence,
                'reason': reason,
                'exit_target_pct': None,
                'stop_loss_pct': None,
                'analysis_data': {
                    'mode': 'mature',
                    'volume_score': volume_score,
                    'volatility_score': volatility_score,
                    'ema_score': ema_score,
                    'momentum_score': momentum_score,
                    'ohlcv_candles': len(df)
                }
            }
        except Exception as e:
            error(f"Error in mature mode analysis: {e}")
            return self._create_rejected_result(f"Mature mode error: {e}")
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average"""
        try:
            alpha = 2 / (period + 1)
            ema = np.zeros_like(data)
            ema[0] = data[0]
            
            for i in range(1, len(data)):
                ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
            
            return ema
        except Exception as e:
            error(f"Error calculating EMA: {e}")
            return data
    
    def _calculate_volume_signal(self, df: pd.DataFrame) -> float:
        """Calculate volume surge score (0-1)"""
        try:
            volumes = df['volume'].values
            
            if len(volumes) < AI_VOLUME_DELTA_PERIODS + 1:
                return 0.5  # Neutral score if insufficient data
            
            # Compare recent volume vs historical average
            recent_volume = np.mean(volumes[-AI_VOLUME_DELTA_PERIODS:])
            historical_volume = np.mean(volumes[:-AI_VOLUME_DELTA_PERIODS])
            
            if historical_volume <= 0:
                return 0.5  # Neutral if no historical volume
            
            volume_ratio = recent_volume / historical_volume
            
            # Convert ratio to score (0-1)
            # 2x volume = 0.8 score, 1x volume = 0.5 score, 0.5x volume = 0.2 score
            if volume_ratio >= AI_VOLUME_SURGE_THRESHOLD:
                return min(1.0, 0.5 + (volume_ratio - 1.0) * 0.3)  # Strong surge
            else:
                return max(0.0, 0.5 + (volume_ratio - 1.0) * 0.5)  # Normal range
                
        except Exception as e:
            error(f"Error calculating volume signal: {e}")
            return 0.5
    
    def _calculate_volatility_signal(self, df: pd.DataFrame) -> float:
        """Calculate volatility stability score (0-1) - lower volatility = higher score"""
        try:
            close_prices = df['close'].values
            
            if len(close_prices) < AI_VOLATILITY_ATR_PERIODS + 1:
                return 0.5  # Neutral score if insufficient data
            
            # Calculate ATR (Average True Range)
            high = df['high'].values
            low = df['low'].values
            
            # True Range calculation
            tr1 = high[1:] - low[1:]  # High - Low
            tr2 = np.abs(high[1:] - close_prices[:-1])  # High - Previous Close
            tr3 = np.abs(low[1:] - close_prices[:-1])   # Low - Previous Close
            
            true_range = np.maximum(tr1, np.maximum(tr2, tr3))
            
            # Calculate ATR
            atr = np.mean(true_range[-AI_VOLATILITY_ATR_PERIODS:])
            current_price = close_prices[-1]
            
            # Convert ATR to percentage
            atr_pct = atr / current_price if current_price > 0 else 0
            
            # Convert volatility to score (inverted - lower volatility = higher score)
            if atr_pct <= AI_MAX_VOLATILITY_THRESHOLD:
                # Low volatility = high score
                volatility_score = 1.0 - (atr_pct / AI_MAX_VOLATILITY_THRESHOLD) * 0.5
                return max(0.5, volatility_score)
            else:
                # High volatility = low score
                return max(0.0, 0.5 - (atr_pct - AI_MAX_VOLATILITY_THRESHOLD) * 2.0)
                
        except Exception as e:
            error(f"Error calculating volatility signal: {e}")
            return 0.5
    
    def _determine_exit_target(self, volume_score: float, volatility_score: float) -> float:
        """Determine exit target based on analysis strength"""
        try:
            # Calculate overall signal strength
            overall_strength = (volume_score + volatility_score) / 2
            
            if overall_strength >= 0.8:
                # Strong signals = aggressive target
                return AI_EXIT_TARGETS['aggressive']
            elif overall_strength >= 0.6:
                # Moderate signals = moderate target
                return AI_EXIT_TARGETS['moderate']
            else:
                # Weak signals = conservative target
                return AI_EXIT_TARGETS['conservative']
                
        except Exception as e:
            error(f"Error determining exit target: {e}")
            return AI_EXIT_TARGETS['moderate']
    
    def _generate_reason(self, volume_score: float, volatility_score: float, 
                        confidence: float, approved: bool) -> str:
        """Generate brief reason for recommendation"""
        try:
            if approved:
                reasons = []
                if volume_score > 0.7:
                    reasons.append("Strong volume")
                if volatility_score > 0.7:
                    reasons.append("Low volatility")
                if confidence > 0.8:
                    reasons.append("High confidence")
                
                return "Strong signals: " + ", ".join(reasons[:2]) if reasons else "Good technical setup"
            else:
                reasons = []
                if volume_score < 0.5:
                    reasons.append("Weak volume")
                if volatility_score < 0.5:
                    reasons.append("High volatility")
                if confidence < 0.5:
                    reasons.append("Low confidence")
                
                return "Weak signals: " + ", ".join(reasons[:2]) if reasons else "Poor technical setup"
                
        except Exception as e:
            error(f"Error generating reason: {e}")
            return "Analysis incomplete"
    
    def _create_approved_result(self, reason: str) -> Dict[str, Any]:
        """Create a standardized approved result"""
        return {
            'approved': True,
            'confidence': 0.5,
            'reason': reason,
            'exit_target_pct': None,  # Disabled - AI Analysis handles exits
            'stop_loss_pct': None,  # Disabled - no stop loss
            'analysis_data': {}
        }
    
    def _create_rejected_result(self, reason: str) -> Dict[str, Any]:
        """Create a standardized rejected result"""
        return {
            'approved': False,
            'confidence': 0.0,
            'reason': reason,
            'exit_target_pct': None,  # Disabled - AI Analysis handles exits
            'stop_loss_pct': None,  # Disabled - no stop loss
            'analysis_data': {}
        }
    
    def _get_cached_analysis(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis result if still valid"""
        current_time = time.time()
        if (token_address in self.analysis_cache and 
            token_address in self.cache_expiry and
            self.cache_expiry[token_address] > current_time):
            return self.analysis_cache[token_address]
        return None
    
    def _generate_ai_reason(self, token_address: str, volume_score: float, volatility_score: float, 
                           confidence: float, approved: bool) -> str:
        """Generate AI-powered reason for the decision"""
        if approved:
            return f"Approved based on volume score {volume_score:.1%} and volatility {volatility_score:.1%} (confidence: {confidence:.1%})"
        else:
            return f"Rejected due to low confidence {confidence:.1%} (volume: {volume_score:.1%}, volatility: {volatility_score:.1%})"
    
    def _cache_analysis(self, token_address: str, result: Dict[str, Any]) -> None:
        """Cache analysis result with expiry"""
        current_time = time.time()
        cache_duration = AI_CONFIRMATION_CACHE_MINUTES * 60  # Convert to seconds
        
        self.analysis_cache[token_address] = result
        self.cache_expiry[token_address] = current_time + cache_duration

# Singleton instance
_ai_confirmation = None

def get_ai_confirmation() -> AIConfirmation:
    """Get singleton instance of AI confirmation service"""
    global _ai_confirmation
    if _ai_confirmation is None:
        _ai_confirmation = AIConfirmation()
    return _ai_confirmation
