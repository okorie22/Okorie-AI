"""
🌙 Anarcho Capital's AI DeFi Advisor
DeepSeek-driven decision making for leverage and market timing
Built with love by Anarcho Capital 🚀
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical
from src.config.defi_config import LEVERAGE_AI_CONFIG, YIELD_THRESHOLDS
from src.models.deepseek_model import DeepSeekModel
from src.scripts.data_processing.sentiment_data_extractor import get_sentiment_data_extractor

@dataclass
class AIAdvisorDecision:
    """AI decision for DeFi operations"""
    should_proceed: bool
    confidence: float  # 0.0 to 1.0
    recommended_leverage: float
    recommended_collateral: str
    market_timing: str  # "favorable", "neutral", "unfavorable"
    reasoning: str
    risk_assessment: str  # "low", "medium", "high"
    suggestions: List[str]

@dataclass
class MarketAnalysis:
    """Comprehensive market analysis for DeFi timing"""
    overall_sentiment: str
    sentiment_score: float
    chart_sentiment: str
    twitter_sentiment: str
    bullish_tokens: List[str]
    bearish_tokens: List[str]
    recommendation: str
    confidence: float

class AIDefiAdvisor:
    """
    AI-driven advisor for DeFi leverage decisions
    Uses DeepSeek model and sentiment data for optimal timing
    """
    
    def __init__(self):
        """Initialize the AI advisor"""
        self.config = LEVERAGE_AI_CONFIG
        self.sentiment_extractor = get_sentiment_data_extractor()
        
        # Initialize DeepSeek model
        try:
            # Import API key
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv('DEEPSEEK_KEY', '')
            if api_key:
                self.deepseek = DeepSeekModel(api_key=api_key)
                self.ai_enabled = self.config['enabled']
                info("✅ AI DeFi Advisor initialized with DeepSeek")
            else:
                warning("⚠️ DeepSeek API key not configured")
                self.ai_enabled = False
                self.deepseek = None
        except Exception as e:
            warning(f"⚠️ DeepSeek model unavailable: {str(e)}")
            self.ai_enabled = False
            self.deepseek = None
        
        info("🤖 AI DeFi Advisor initialized")
    
    async def analyze_leverage_opportunity(self, available_capital: Dict[str, float],
                                          yield_opportunities: List[Dict[str, Any]],
                                          preferred_asset: Optional[str] = None) -> AIAdvisorDecision:
        """
        Analyze whether a leverage opportunity is wise
        
        Args:
            available_capital: Available capital by token
            yield_opportunities: List of yield opportunities
            
        Returns:
            AIAdvisorDecision with recommendation
        """
        try:
            if not self.ai_enabled:
                # Fallback to conservative default
                return AIAdvisorDecision(
                    should_proceed=False,
                    confidence=0.5,
                    recommended_leverage=1.5,
                    recommended_collateral="USDC",
                    market_timing="neutral",
                    reasoning="AI unavailable - conservative approach",
                    risk_assessment="medium",
                    suggestions=["Wait for AI model availability"]
                )
            
            # Get market sentiment
            market_analysis = self._analyze_market_conditions()
            
            # Analyze yield opportunities
            best_yield = yield_opportunities[0] if yield_opportunities else None
            
            if not best_yield:
                return AIAdvisorDecision(
                    should_proceed=False,
                    confidence=0.0,
                    recommended_leverage=0.0,
                    recommended_collateral="USDC",
                    market_timing="neutral",
                    reasoning="No viable yield opportunities found",
                    risk_assessment="medium",
                    suggestions=["Monitor for opportunities", "Reassess in 24 hours"]
                )
            
            # Generate AI reasoning
            prompt = self._build_leverage_prompt(market_analysis, available_capital, best_yield)
            
            try:
                # Use generate_response with correct method signature
                response = self.deepseek.generate_response(
                    system_prompt="You are Anarcho Capital's DeFi Advisor. Analyze leverage opportunities and provide clear recommendations.",
                    user_content=prompt,
                    temperature=0.7,
                    max_tokens=500
                )
                ai_response = response.content  # Extract content from ModelResponse
                
                # Parse AI response - pass actual available_capital and preferred_asset
                decision = self._parse_ai_response(ai_response, market_analysis, best_yield, available_capital, preferred_asset)
                
                info(f"\033[36m🤖 AI Recommendation: {'PROCEED' if decision.should_proceed else 'WAIT'} (confidence: {decision.confidence:.2f})\033[0m")
                return decision
                
            except Exception as e:
                error(f"AI analysis error: {str(e)}")
                # Fallback decision - pass preferred_asset for collateral selection
                return self._generate_fallback_decision(market_analysis, best_yield, preferred_asset)
            
        except Exception as e:
            error(f"Error in leverage opportunity analysis: {str(e)}")
            return AIAdvisorDecision(
                should_proceed=False,
                confidence=0.0,
                recommended_leverage=0.0,
                recommended_collateral="USDC",
                market_timing="unfavorable",
                reasoning=f"Analysis error: {str(e)}",
                risk_assessment="high",
                suggestions=["Error occurred - manual review required"]
            )
    
    def recommend_collateral_asset(self, available_assets: Dict[str, float],
                                   market_sentiment: str,
                                   preferred_asset: Optional[str] = None) -> str:
        """
        Recommend best collateral asset based on conditions

        Args:
            available_assets: Available assets and amounts
            market_sentiment: Current market sentiment
            preferred_asset: Asset that triggered the DeFi agent (e.g., 'stSOL'), should be prioritized

        Returns:
            Recommended collateral token (SOL, stSOL, or USDC)
        """
        try:
            # Get sentiment scores for each asset
            asset_scores = {}

            # Much lower threshold for stSOL since it's passive unused income
            # stSOL should be preferred even with small amounts
            stsol_threshold = 10.0  # Very low threshold for stSOL
            preferred_threshold = 25.0 if preferred_asset and preferred_asset != "stSOL" else stsol_threshold
            standard_threshold = 50.0  # Standard threshold for other assets

            for asset, amount in available_assets.items():
                # Determine threshold based on asset type
                if asset == "stSOL":
                    threshold = stsol_threshold  # Always low for stSOL
                elif asset == preferred_asset:
                    threshold = preferred_threshold
                else:
                    threshold = standard_threshold

                if amount < threshold:
                    continue  # Skip if below threshold

                score = 0.0

                # Heavily prefer stSOL as it's unused passive income
                if asset == "stSOL":
                    score = 2.0  # High base score for stSOL
                    # Massive boost if it's the preferred/trigger asset
                    if asset == preferred_asset:
                        score += 2.0  # Add 2.0 boost for trigger asset (stSOL)
                    # Additional boost in bullish markets
                    if market_sentiment == "bullish":
                        score += 0.5

                # Prefer SOL for fee efficiency but much lower than stSOL
                elif asset == "SOL":
                    score = 1.0
                    # Reduce SOL score if stSOL is available (preserve SOL for fees)
                    if "stSOL" in available_assets and available_assets["stSOL"] >= stsol_threshold:
                        score = 0.7  # Reduce SOL preference when stSOL is available

                # USDC is always safe but lowest priority
                elif asset == "USDC":
                    score = 0.5

                asset_scores[asset] = score

            if not asset_scores:
                # If preferred asset is available but below threshold, still consider it
                if preferred_asset and preferred_asset in available_assets:
                    amount = available_assets[preferred_asset]
                    # Much lower minimum for stSOL
                    min_amount = 10.0 if preferred_asset == "stSOL" else 25.0
                    if amount >= min_amount:
                        info(f"\033[36m💰 Recommended collateral: {preferred_asset} (triggered asset, amount: ${amount:.2f})\033[0m")
                        return preferred_asset
                return "USDC"  # Default safe choice

            # Return highest scoring asset
            recommended = max(asset_scores.items(), key=lambda x: x[1])[0]
            info(f"\033[36m💰 Recommended collateral: {recommended} (score: {asset_scores.get(recommended, 0):.2f})\033[0m")
            debug(f"📊 Asset scoring breakdown: {asset_scores}")
            debug(f"🎯 Preferred asset: {preferred_asset}, Market sentiment: {market_sentiment}")
            return recommended
            
        except Exception as e:
            error(f"Error recommending collateral: {str(e)}")
            return "USDC"  # Safe fallback
    
    def calculate_optimal_leverage_ratio(self, available_capital: float,
                                         market_sentiment: str,
                                         yield_apy: float) -> float:
        """
        Calculate optimal leverage ratio based on market conditions
        
        Args:
            available_capital: Available capital in USD
            market_sentiment: Current market sentiment
            yield_apy: Expected yield APY
            
        Returns:
            Optimal leverage ratio
        """
        try:
            # Base leverage
            if yield_apy < YIELD_THRESHOLDS['min_apy_threshold']:
                return 1.0  # No leverage for low yields
            
            # Apply sentiment multiplier
            if market_sentiment == "bullish":
                multiplier = self.config['bullish_leverage_multiplier']
            elif market_sentiment == "bearish":
                multiplier = self.config['bearish_leverage_multiplier']
            else:
                multiplier = self.config['neutral_leverage_multiplier']
            
            # Base leverage based on yield
            if yield_apy >= YIELD_THRESHOLDS['excellent_apy_threshold']:
                base_leverage = 2.5
            elif yield_apy >= YIELD_THRESHOLDS['target_apy_threshold']:
                base_leverage = 2.0
            else:
                base_leverage = 1.5
            
            # Apply sentiment multiplier
            optimal_leverage = base_leverage * multiplier
            
            # Cap at 3x for safety
            optimal_leverage = min(optimal_leverage, 3.0)
            
            info(f"📊 Optimal leverage calculated: {optimal_leverage:.2f}x (APY: {yield_apy:.2f}%, sentiment: {market_sentiment})")
            return optimal_leverage
            
        except Exception as e:
            error(f"Error calculating optimal leverage: {str(e)}")
            return 1.5  # Conservative fallback
    
    def assess_market_timing(self) -> MarketAnalysis:
        """
        Assess current market timing for DeFi operations
        
        Returns:
            MarketAnalysis with sentiment and recommendations
        """
        try:
            sentiment_data = self.sentiment_extractor.get_combined_sentiment_data()
            
            if not sentiment_data:
                return MarketAnalysis(
                    overall_sentiment="neutral",
                    sentiment_score=0.5,
                    chart_sentiment="NEUTRAL",
                    twitter_sentiment="NEUTRAL",
                    bullish_tokens=[],
                    bearish_tokens=[],
                    recommendation="wait",
                    confidence=0.5
                )
            
            # Extract sentiment
            chart_sentiment = sentiment_data.chart_sentiment if hasattr(sentiment_data, 'chart_sentiment') else "NEUTRAL"
            sentiment_score = sentiment_data.chart_confidence if hasattr(sentiment_data, 'chart_confidence') else 0.5
            
            # Determine overall sentiment
            if chart_sentiment in ["BULLISH", "VERY_BULLISH"]:
                overall_sentiment = "bullish"
            elif chart_sentiment in ["BEARISH", "VERY_BEARISH"]:
                overall_sentiment = "bearish"
            else:
                overall_sentiment = "neutral"
            
            # Generate recommendation
            if overall_sentiment == "bullish" and sentiment_score > 0.7:
                recommendation = "favorable"
                confidence = sentiment_score
            elif overall_sentiment == "bearish" or sentiment_score < 0.3:
                recommendation = "unfavorable"
                confidence = 1.0 - sentiment_score
            else:
                recommendation = "neutral"
                confidence = 0.5
            
            bullish_tokens = getattr(sentiment_data, 'chart_bullish_tokens', [])
            bearish_tokens = getattr(sentiment_data, 'chart_bearish_tokens', [])
            
            return MarketAnalysis(
                overall_sentiment=overall_sentiment,
                sentiment_score=sentiment_score,
                chart_sentiment=chart_sentiment,
                twitter_sentiment=getattr(sentiment_data, 'twitter_classification', 'NEUTRAL'),
                bullish_tokens=bullish_tokens,
                bearish_tokens=bearish_tokens,
                recommendation=recommendation,
                confidence=confidence
            )
            
        except Exception as e:
            error(f"Error assessing market timing: {str(e)}")
            return MarketAnalysis(
                overall_sentiment="neutral",
                sentiment_score=0.5,
                chart_sentiment="NEUTRAL",
                twitter_sentiment="NEUTRAL",
                bullish_tokens=[],
                bearish_tokens=[],
                recommendation="wait",
                confidence=0.5
            )
    
    def _analyze_market_conditions(self) -> MarketAnalysis:
        """Analyze current market conditions"""
        try:
            return self.assess_market_timing()
        except Exception as e:
            error(f"Error analyzing market conditions: {str(e)}")
            return MarketAnalysis(
                overall_sentiment="neutral",
                sentiment_score=0.5,
                chart_sentiment="NEUTRAL",
                twitter_sentiment="NEUTRAL",
                bullish_tokens=[],
                bearish_tokens=[],
                recommendation="wait",
                confidence=0.5
            )
    
    def _build_leverage_prompt(self, market_analysis: MarketAnalysis,
                               available_capital: Dict[str, float],
                               yield_opportunity: Dict[str, Any]) -> str:
        """Build AI prompt for leverage analysis"""
        return f"""
Analyze this DeFi leverage opportunity:

Market Conditions:
- Overall Sentiment: {market_analysis.overall_sentiment}
- Sentiment Score: {market_analysis.sentiment_score:.2f}
- Chart Analysis: {market_analysis.chart_sentiment}
- Bullish Tokens: {market_analysis.bullish_tokens}
- Bearish Tokens: {market_analysis.bearish_tokens}

Available Capital:
{available_capital}

Yield Opportunity:
- Protocol: {yield_opportunity.get('protocol', 'unknown')}
- APY: {yield_opportunity.get('estimated_apy', 0):.2f}%
- Risk Level: {yield_opportunity.get('risk_level', 'medium')}

Provide a clear recommendation with the following format:
PROCEED/WAIT
CONFIDENCE: 0.0-1.0
LEVERAGE: X.Xx (e.g., 2.5x, 1.5x, 3.0x)
RISK: low/medium/high
REASONING: Your analysis

Example format:
PROCEED
CONFIDENCE: 0.7
LEVERAGE: 2.5x
RISK: medium
REASONING: Market conditions favorable, good yield spread...
"""
    
    def _parse_ai_response(self, response: str, market_analysis: MarketAnalysis,
                          yield_opportunity: Dict[str, Any], available_capital: Dict[str, float],
                          preferred_asset: Optional[str] = None) -> AIAdvisorDecision:
        """Parse AI response into structured decision"""
        try:
            import re
            response_lower = response.lower()
            
            should_proceed = "proceed" in response_lower or "yes" in response_lower or "recommend" in response_lower
            confidence = 0.7 if "high" in response_lower or "strong" in response_lower else 0.5
            
            # Enhanced leverage extraction - try multiple patterns
            leverage = None
            leverage_patterns = [
                r'leverage[:\s]+([\d.]+)',
                r'(\d+\.?\d*)\s*x\s*leverage',
                r'leverage\s+of\s+(\d+\.?\d*)',
                r'(\d+\.?\d*)\s*times',
                r'(\d+\.?\d*)\s*x\s*multiplier'
            ]
            
            for pattern in leverage_patterns:
                leverage_match = re.search(pattern, response_lower)
                if leverage_match:
                    try:
                        leverage = float(leverage_match.group(1))
                        leverage = max(1.0, min(3.0, leverage))  # Clamp between 1.0 and 3.0
                        break
                    except (ValueError, IndexError):
                        continue
            
            # If no leverage found in AI response, calculate optimal leverage based on market conditions
            if leverage is None:
                apy = yield_opportunity.get('estimated_apy', 0) if yield_opportunity else 0
                # Use the highest available capital amount to determine optimal leverage
                max_available = max(available_capital.values()) if available_capital else 0
                leverage = self.calculate_optimal_leverage_ratio(max_available, market_analysis.overall_sentiment, apy)
                info(f"📊 Leverage not in AI response - calculated optimal: {leverage:.2f}x")
            
            # Determine risk
            if "high risk" in response_lower or "dangerous" in response_lower or "risky" in response_lower:
                risk = "high"
            elif "low risk" in response_lower or "safe" in response_lower or "conservative" in response_lower:
                risk = "low"
            else:
                risk = "medium"
            
            # Use ACTUAL available_capital instead of hardcoded values
            # Pass preferred_asset to prioritize trigger asset (e.g., stSOL)
            recommended_collateral = self.recommend_collateral_asset(
                available_capital,
                market_analysis.overall_sentiment,
                preferred_asset=preferred_asset
            )
            
            return AIAdvisorDecision(
                should_proceed=should_proceed,
                confidence=confidence,
                recommended_leverage=leverage,
                recommended_collateral=recommended_collateral,
                market_timing=market_analysis.recommendation,
                reasoning=response[:200],
                risk_assessment=risk,
                suggestions=["Follow AI recommendation"]
            )
            
        except Exception as e:
            error(f"Error parsing AI response: {str(e)}")
            return self._generate_fallback_decision(market_analysis, yield_opportunity, preferred_asset)
    
    def _generate_fallback_decision(self, market_analysis: MarketAnalysis,
                                   yield_opportunity: Dict[str, Any],
                                   preferred_asset: Optional[str] = None) -> AIAdvisorDecision:
        """Generate fallback decision when AI unavailable"""
        apy = yield_opportunity.get('estimated_apy', 0) if yield_opportunity else 0
        
        should_proceed = apy > 0.10 and market_analysis.overall_sentiment != "bearish"
        confidence = 0.6 if should_proceed else 0.4
        
        # Use preferred asset if available, otherwise default to USDC
        # Create minimal available_capital dict for collateral recommendation
        minimal_capital = {preferred_asset: 100.0} if preferred_asset else {}
        if not minimal_capital:
            collateral = "USDC"
        else:
            collateral = self.recommend_collateral_asset(
                minimal_capital,
                market_analysis.overall_sentiment,
                preferred_asset=preferred_asset
            )
        
        return AIAdvisorDecision(
            should_proceed=should_proceed,
            confidence=confidence,
            recommended_leverage=1.5 if apy > 0.10 else 1.0,
            recommended_collateral=collateral,
            market_timing=market_analysis.recommendation,
            reasoning="Fallback decision - AI unavailable",
            risk_assessment="medium",
            suggestions=["Use conservative approach", "Reassess with AI later"]
        )

# Global instance
_ai_advisor = None

def get_ai_defi_advisor() -> AIDefiAdvisor:
    """Get the global AI DeFi advisor instance"""
    global _ai_advisor
    if _ai_advisor is None:
        _ai_advisor = AIDefiAdvisor()
    return _ai_advisor

