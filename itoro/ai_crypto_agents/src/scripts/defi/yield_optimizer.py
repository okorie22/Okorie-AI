"""
🌙 Anarcho Capital's Yield Optimizer
AI-driven yield optimization across Solana DeFi protocols
Built with love by Anarcho Capital 🚀
"""

import os
import time
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# AI imports
try:
    import openai
    import anthropic
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical, system
from src.scripts.defi.defi_protocol_manager import get_defi_protocol_manager
from src.scripts.defi.defi_risk_manager import get_defi_risk_manager
from src.config.defi_config import (
    YIELD_OPTIMIZATION, YIELD_THRESHOLDS, CAPITAL_PROTECTION,
    CORRELATION_LIMITS, get_current_phase_config
)

@dataclass
class YieldOpportunity:
    """Yield opportunity details"""
    protocol: str
    token: str
    apy: float
    tvl: float
    risk_score: float
    expected_return: float
    allocation_recommendation: float
    priority: int
    confidence: float
    last_updated: datetime

@dataclass
class OptimizationStrategy:
    """Yield optimization strategy"""
    strategy_name: str
    target_apy: float
    risk_tolerance: str
    allocation_distribution: Dict[str, float]
    expected_portfolio_apy: float
    confidence: float
    recommendations: List[str]
    timestamp: datetime

@dataclass
class CrossProtocolArbitrage:
    """Cross-protocol arbitrage opportunity"""
    source_protocol: str
    target_protocol: str
    source_apy: float
    target_apy: float
    apy_difference: float
    risk_adjusted_return: float
    recommended_action: str
    confidence: float
    timestamp: datetime

class YieldOptimizer:
    """
    AI-driven yield optimizer for DeFi protocols
    Analyzes opportunities across multiple protocols and provides recommendations
    """
    
    def __init__(self):
        """Initialize the Yield Optimizer"""
        self.protocol_manager = get_defi_protocol_manager()
        self.risk_manager = get_defi_risk_manager()
        self.opportunities_cache = {}
        self.strategies_cache = {}
        self.last_optimization = None
        
        # AI configuration
        self.ai_enabled = AI_AVAILABLE and YIELD_OPTIMIZATION['ai_driven']
        self.ai_model = "claude-3-haiku-20240307"  # Default model
        self.ai_temperature = 0.7
        
        # Optimization parameters
        self.optimization_interval = 3600  # 1 hour
        self.min_confidence_threshold = 0.7
        self.max_protocols_per_strategy = 5
        
        # Performance tracking
        self.optimization_history = []
        self.success_metrics = {
            'total_optimizations': 0,
            'successful_optimizations': 0,
            'average_apy_improvement': 0.0,
            'risk_reduction': 0.0
        }
        
        info("🚀 Yield Optimizer initialized")
    
    async def optimize_yields(self, portfolio_data: Dict[str, Any], 
                            risk_tolerance: str = 'medium') -> OptimizationStrategy:
        """Optimize yields across all available protocols"""
        try:
            # Get current yield opportunities
            opportunities = await self._get_all_yield_opportunities()
            
            if not opportunities:
                return self._create_no_opportunities_strategy()
            
            # Filter opportunities based on risk tolerance
            filtered_opportunities = self._filter_by_risk_tolerance(opportunities, risk_tolerance)
            
            # Generate optimization strategy
            strategy = await self._generate_optimization_strategy(
                filtered_opportunities, portfolio_data, risk_tolerance
            )
            
            # Cache the strategy
            self.strategies_cache[risk_tolerance] = strategy
            self.last_optimization = datetime.now()
            
            # Update performance metrics
            self._update_performance_metrics(strategy)
            
            return strategy
            
        except Exception as e:
            error(f"Failed to optimize yields: {str(e)}")
            return self._create_error_strategy(str(e))
    
    async def _get_all_yield_opportunities(self) -> List[YieldOpportunity]:
        """Get yield opportunities from all protocols"""
        try:
            opportunities = []
            
            # Get lending opportunities
            lending_opps = await self.protocol_manager.get_lending_opportunities(
                min_apy=YIELD_THRESHOLDS['min_apy_threshold'] * 100
            )
            
            for opp in lending_opps:
                opportunity = YieldOpportunity(
                    protocol=opp.protocol,
                    token=opp.token,
                    apy=opp.apy,
                    tvl=0,  # Will be filled from protocol data
                    risk_score=opp.risk_score,
                    expected_return=opp.expected_return,
                    allocation_recommendation=0,  # Will be calculated
                    priority=opp.priority,
                    confidence=0.8,  # Default confidence
                    last_updated=datetime.now()
                )
                opportunities.append(opportunity)
            
            # Get additional yield farming opportunities
            farming_opps = await self._get_yield_farming_opportunities()
            opportunities.extend(farming_opps)
            
            # Sort by expected return and priority
            opportunities.sort(key=lambda x: (x.expected_return, x.priority), reverse=True)
            
            return opportunities
            
        except Exception as e:
            error(f"Failed to get yield opportunities: {str(e)}")
            return []
    
    async def _get_yield_farming_opportunities(self) -> List[YieldOpportunity]:
        """Get yield farming opportunities from additional sources"""
        try:
            opportunities = []
            
            # This would integrate with additional yield farming protocols
            # For now, return empty list
            # Future: Add Orca, Raydium, Francium integration
            
            return opportunities
            
        except Exception as e:
            error(f"Failed to get yield farming opportunities: {str(e)}")
            return []
    
    def _filter_by_risk_tolerance(self, opportunities: List[YieldOpportunity], 
                                 risk_tolerance: str) -> List[YieldOpportunity]:
        """Filter opportunities based on risk tolerance"""
        try:
            risk_thresholds = {
                'conservative': 0.3,
                'moderate': 0.5,
                'medium': 0.6,
                'aggressive': 0.8,
                'very_aggressive': 1.0
            }
            
            max_risk = risk_thresholds.get(risk_tolerance, 0.6)
            
            filtered = [
                opp for opp in opportunities 
                if opp.risk_score <= max_risk
            ]
            
            return filtered
            
        except Exception as e:
            error(f"Failed to filter opportunities by risk: {str(e)}")
            return opportunities
    
    async def _generate_optimization_strategy(self, opportunities: List[YieldOpportunity],
                                            portfolio_data: Dict[str, Any],
                                            risk_tolerance: str) -> OptimizationStrategy:
        """Generate optimization strategy using AI or rules-based approach"""
        try:
            if self.ai_enabled and len(opportunities) > 0:
                return await self._generate_ai_strategy(opportunities, portfolio_data, risk_tolerance)
            else:
                return self._generate_rules_based_strategy(opportunities, portfolio_data, risk_tolerance)
                
        except Exception as e:
            error(f"Failed to generate optimization strategy: {str(e)}")
            return self._create_error_strategy(str(e))
    
    async def _generate_ai_strategy(self, opportunities: List[YieldOpportunity],
                                  portfolio_data: Dict[str, Any],
                                  risk_tolerance: str) -> OptimizationStrategy:
        """Generate optimization strategy using AI"""
        try:
            # Prepare data for AI analysis
            opportunities_data = []
            for opp in opportunities[:10]:  # Top 10 opportunities
                opportunities_data.append({
                    'protocol': opp.protocol,
                    'apy': opp.apy,
                    'risk_score': opp.risk_score,
                    'priority': opp.priority
                })
            
            # Create AI prompt
            prompt = self._create_ai_optimization_prompt(
                opportunities_data, portfolio_data, risk_tolerance
            )
            
            # Get AI response
            ai_response = await self._get_ai_response(prompt)
            
            # Parse AI response
            strategy = self._parse_ai_optimization_response(ai_response, opportunities)
            
            return strategy
            
        except Exception as e:
            error(f"Failed to generate AI strategy: {str(e)}")
            # Fallback to rules-based strategy
            return self._generate_rules_based_strategy(opportunities, portfolio_data, risk_tolerance)
    
    def _create_ai_optimization_prompt(self, opportunities: List[Dict], 
                                     portfolio_data: Dict[str, Any],
                                     risk_tolerance: str) -> str:
        """Create AI prompt for yield optimization"""
        prompt = f"""
You are Anarcho Capital's Yield Optimization AI 🚀

Your task is to analyze DeFi yield opportunities and create an optimal allocation strategy.

Portfolio Data:
- Total Balance: ${portfolio_data.get('total_balance_usd', 0):,.2f}
- Risk Tolerance: {risk_tolerance}
- Current Allocation: {portfolio_data.get('total_allocation_percent', 0)*100:.1f}%

Available Yield Opportunities:
{json.dumps(opportunities, indent=2)}

Requirements:
1. Maximize expected APY while respecting risk tolerance
2. Diversify across protocols (max 5 protocols)
3. Consider protocol priority and risk scores
4. Maintain portfolio balance and risk management

Respond with a JSON object containing:
{{
    "strategy_name": "Descriptive strategy name",
    "target_apy": target_apy_percentage,
    "risk_tolerance": "{risk_tolerance}",
    "allocation_distribution": {{
        "protocol_name": allocation_percentage
    }},
    "expected_portfolio_apy": expected_overall_apy,
    "confidence": confidence_score_0_to_1,
    "recommendations": ["list", "of", "recommendations"]
}}

Focus on:
- Risk-adjusted returns
- Protocol diversification
- Capital efficiency
- Market conditions
"""
        return prompt
    
    async def _get_ai_response(self, prompt: str) -> str:
        """Get AI response for optimization"""
        try:
            if not AI_AVAILABLE:
                return ""
            
            # Try OpenAI first
            try:
                client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                response = client.chat.completions.create(
                    model=self.ai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.ai_temperature,
                    max_tokens=1000
                )
                return response.choices[0].message.content
            except:
                pass
            
            # Try Anthropic as fallback
            try:
                client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
                response = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,
                    temperature=self.ai_temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            except:
                pass
            
            return ""
            
        except Exception as e:
            error(f"Failed to get AI response: {str(e)}")
            return ""
    
    def _parse_ai_optimization_response(self, ai_response: str, 
                                      opportunities: List[YieldOpportunity]) -> OptimizationStrategy:
        """Parse AI response into optimization strategy"""
        try:
            if not ai_response:
                return self._create_error_strategy("No AI response received")
            
            # Try to extract JSON from response
            try:
                # Find JSON in response
                start_idx = ai_response.find('{')
                end_idx = ai_response.rfind('}') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = ai_response[start_idx:end_idx]
                    data = json.loads(json_str)
                else:
                    return self._create_error_strategy("No JSON found in AI response")
                
            except json.JSONDecodeError:
                return self._create_error_strategy("Invalid JSON in AI response")
            
            # Create strategy from parsed data
            strategy = OptimizationStrategy(
                strategy_name=data.get('strategy_name', 'AI Generated Strategy'),
                target_apy=data.get('target_apy', 0.0),
                risk_tolerance=data.get('risk_tolerance', 'medium'),
                allocation_distribution=data.get('allocation_distribution', {}),
                expected_portfolio_apy=data.get('expected_portfolio_apy', 0.0),
                confidence=data.get('confidence', 0.5),
                recommendations=data.get('recommendations', []),
                timestamp=datetime.now()
            )
            
            return strategy
            
        except Exception as e:
            error(f"Failed to parse AI response: {str(e)}")
            return self._create_error_strategy(f"Failed to parse AI response: {str(e)}")
    
    def _generate_rules_based_strategy(self, opportunities: List[YieldOpportunity],
                                     portfolio_data: Dict[str, Any],
                                     risk_tolerance: str) -> OptimizationStrategy:
        """Generate optimization strategy using rules-based approach"""
        try:
            if not opportunities:
                return self._create_no_opportunities_strategy()
            
            # Select top opportunities based on risk-adjusted returns
            selected_opportunities = self._select_best_opportunities(opportunities)
            
            # Calculate allocation distribution
            allocation_distribution = self._calculate_allocation_distribution(
                selected_opportunities, portfolio_data
            )
            
            # Calculate expected portfolio APY
            expected_apy = self._calculate_expected_portfolio_apy(
                selected_opportunities, allocation_distribution
            )
            
            # Generate recommendations
            recommendations = self._generate_rules_based_recommendations(
                selected_opportunities, allocation_distribution
            )
            
            strategy = OptimizationStrategy(
                strategy_name=f"Rules-Based {risk_tolerance.title()} Strategy",
                target_apy=max(opp.apy for opp in selected_opportunities),
                risk_tolerance=risk_tolerance,
                allocation_distribution=allocation_distribution,
                expected_portfolio_apy=expected_apy,
                confidence=0.8,  # Rules-based strategies have high confidence
                recommendations=recommendations,
                timestamp=datetime.now()
            )
            
            return strategy
            
        except Exception as e:
            error(f"Failed to generate rules-based strategy: {str(e)}")
            return self._create_error_strategy(str(e))
    
    def _select_best_opportunities(self, opportunities: List[YieldOpportunity]) -> List[YieldOpportunity]:
        """Select best opportunities based on risk-adjusted returns"""
        try:
            # Calculate risk-adjusted returns
            for opp in opportunities:
                # Simple risk-adjusted return: APY / (1 + risk_score)
                opp.expected_return = opp.apy / (1 + opp.risk_score)
            
            # Sort by risk-adjusted return and priority
            opportunities.sort(key=lambda x: (x.expected_return, x.priority), reverse=True)
            
            # Select top opportunities (max 5)
            selected = opportunities[:self.max_protocols_per_strategy]
            
            return selected
            
        except Exception as e:
            error(f"Failed to select best opportunities: {str(e)}")
            return opportunities[:3] if opportunities else []
    
    def _calculate_allocation_distribution(self, opportunities: List[YieldOpportunity],
                                         portfolio_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate allocation distribution across protocols"""
        try:
            if not opportunities:
                return {}
            
            # Get current phase configuration
            current_config = get_current_phase_config()
            max_allocation = current_config['allocation_percentage']
            
            # Calculate weights based on expected returns and priority
            total_weight = sum(opp.expected_return * opp.priority for opp in opportunities)
            
            allocation_distribution = {}
            
            for opp in opportunities:
                if total_weight > 0:
                    weight = (opp.expected_return * opp.priority) / total_weight
                    allocation = weight * max_allocation
                    
                    # Respect protocol limits
                    protocol_limit = self._get_protocol_allocation_limit(opp.protocol)
                    allocation = min(allocation, protocol_limit)
                    
                    allocation_distribution[opp.protocol] = allocation
            
            return allocation_distribution
            
        except Exception as e:
            error(f"Failed to calculate allocation distribution: {str(e)}")
            return {}
    
    def _get_protocol_allocation_limit(self, protocol_name: str) -> float:
        """Get maximum allocation limit for a protocol"""
        try:
            # This would integrate with protocol configuration
            # For now, use default limits
            default_limits = {
                'solend': 0.15,
                'mango': 0.10,
                'tulip': 0.05
            }
            return default_limits.get(protocol_name, 0.10)
            
        except Exception as e:
            error(f"Failed to get protocol allocation limit: {str(e)}")
            return 0.10
    
    def _calculate_expected_portfolio_apy(self, opportunities: List[YieldOpportunity],
                                        allocation_distribution: Dict[str, float]) -> float:
        """Calculate expected portfolio APY"""
        try:
            if not opportunities or not allocation_distribution:
                return 0.0
            
            total_allocation = sum(allocation_distribution.values())
            if total_allocation == 0:
                return 0.0
            
            weighted_apy = 0.0
            
            for opp in opportunities:
                if opp.protocol in allocation_distribution:
                    weight = allocation_distribution[opp.protocol] / total_allocation
                    weighted_apy += opp.apy * weight
            
            return weighted_apy
            
        except Exception as e:
            error(f"Failed to calculate expected portfolio APY: {str(e)}")
            return 0.0
    
    def _generate_rules_based_recommendations(self, opportunities: List[YieldOpportunity],
                                            allocation_distribution: Dict[str, float]) -> List[str]:
        """Generate recommendations based on rules"""
        try:
            recommendations = []
            
            if not opportunities:
                recommendations.append("No yield opportunities available at current risk tolerance")
                return recommendations
            
            # Protocol diversification
            if len(opportunities) >= 3:
                recommendations.append("✅ Good protocol diversification achieved")
            else:
                recommendations.append("⚠️ Consider adding more protocols for diversification")
            
            # Risk assessment
            avg_risk = sum(opp.risk_score for opp in opportunities) / len(opportunities)
            if avg_risk < 0.3:
                recommendations.append("🟢 Low-risk strategy - suitable for conservative investors")
            elif avg_risk < 0.6:
                recommendations.append("🟡 Moderate-risk strategy - balanced risk-reward")
            else:
                recommendations.append("🔴 High-risk strategy - aggressive yield seeking")
            
            # APY targets
            max_apy = max(opp.apy for opp in opportunities)
            if max_apy >= YIELD_THRESHOLDS['excellent_apy_threshold'] * 100:
                recommendations.append("🚀 Excellent yield opportunities available")
            elif max_apy >= YIELD_THRESHOLDS['target_apy_threshold'] * 100:
                recommendations.append("📈 Good yield opportunities available")
            else:
                recommendations.append("📊 Moderate yield opportunities - consider waiting for better rates")
            
            # Allocation recommendations
            for protocol, allocation in allocation_distribution.items():
                if allocation > 0.1:  # More than 10%
                    recommendations.append(f"💰 Consider {protocol} for {allocation*100:.1f}% allocation")
            
            return recommendations
            
        except Exception as e:
            error(f"Failed to generate recommendations: {str(e)}")
            return ["Error generating recommendations"]
    
    async def find_cross_protocol_arbitrage(self) -> List[CrossProtocolArbitrage]:
        """Find cross-protocol arbitrage opportunities"""
        try:
            arbitrage_opportunities = []
            
            # Get opportunities from all protocols
            opportunities = await self._get_all_yield_opportunities()
            
            # Group by token
            token_opportunities = {}
            for opp in opportunities:
                if opp.token not in token_opportunities:
                    token_opportunities[opp.token] = []
                token_opportunities[opp.token].append(opp)
            
            # Find arbitrage opportunities
            for token, token_opps in token_opportunities.items():
                if len(token_opps) >= 2:
                    # Sort by APY
                    sorted_opps = sorted(token_opps, key=lambda x: x.apy, reverse=True)
                    
                    best_opp = sorted_opps[0]
                    worst_opp = sorted_opps[-1]
                    
                    apy_difference = best_opp.apy - worst_opp.apy
                    
                    # Only consider significant differences
                    if apy_difference >= YIELD_THRESHOLDS['yield_improvement_threshold'] * 100:
                        # Calculate risk-adjusted return
                        risk_adjusted_return = apy_difference / (1 + best_opp.risk_score)
                        
                        arbitrage = CrossProtocolArbitrage(
                            source_protocol=worst_opp.protocol,
                            target_protocol=best_opp.protocol,
                            source_apy=worst_opp.apy,
                            target_apy=best_opp.apy,
                            apy_difference=apy_difference,
                            risk_adjusted_return=risk_adjusted_return,
                            recommended_action=f"Move from {worst_opp.protocol} to {best_opp.protocol}",
                            confidence=min(0.9, 0.5 + (apy_difference / 100)),
                            timestamp=datetime.now()
                        )
                        
                        arbitrage_opportunities.append(arbitrage)
            
            # Sort by risk-adjusted return
            arbitrage_opportunities.sort(key=lambda x: x.risk_adjusted_return, reverse=True)
            
            return arbitrage_opportunities
            
        except Exception as e:
            error(f"Failed to find cross-protocol arbitrage: {str(e)}")
            return []
    
    def _update_performance_metrics(self, strategy: OptimizationStrategy) -> None:
        """Update performance metrics"""
        try:
            self.success_metrics['total_optimizations'] += 1
            
            if strategy.confidence >= self.min_confidence_threshold:
                self.success_metrics['successful_optimizations'] += 1
            
            # Store optimization in history
            self.optimization_history.append({
                'timestamp': strategy.timestamp.isoformat(),
                'strategy_name': strategy.strategy_name,
                'expected_apy': strategy.expected_portfolio_apy,
                'confidence': strategy.confidence,
                'risk_tolerance': strategy.risk_tolerance
            })
            
            # Keep only last 100 optimizations
            if len(self.optimization_history) > 100:
                self.optimization_history = self.optimization_history[-100:]
                
        except Exception as e:
            error(f"Failed to update performance metrics: {str(e)}")
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get summary of optimization performance"""
        try:
            if not self.optimization_history:
                return {'status': 'no_optimizations', 'message': 'No optimizations performed yet'}
            
            recent_optimizations = [
                opt for opt in self.optimization_history
                if (datetime.now() - datetime.fromisoformat(opt['timestamp'])).days < 7
            ]
            
            if recent_optimizations:
                avg_apy = sum(opt['expected_apy'] for opt in recent_optimizations) / len(recent_optimizations)
                avg_confidence = sum(opt['confidence'] for opt in recent_optimizations) / len(recent_optimizations)
            else:
                avg_apy = 0.0
                avg_confidence = 0.0
            
            return {
                'total_optimizations': self.success_metrics['total_optimizations'],
                'successful_optimizations': self.success_metrics['successful_optimizations'],
                'success_rate': (self.success_metrics['successful_optimizations'] / 
                               max(self.success_metrics['total_optimizations'], 1)),
                'recent_optimizations': len(recent_optimizations),
                'average_expected_apy': avg_apy,
                'average_confidence': avg_confidence,
                'last_optimization': self.last_optimization.isoformat() if self.last_optimization else None,
                'ai_enabled': self.ai_enabled
            }
            
        except Exception as e:
            error(f"Failed to get optimization summary: {str(e)}")
            return {'error': str(e)}
    
    def _create_no_opportunities_strategy(self) -> OptimizationStrategy:
        """Create strategy when no opportunities are available"""
        return OptimizationStrategy(
            strategy_name="No Opportunities Available",
            target_apy=0.0,
            risk_tolerance='conservative',
            allocation_distribution={},
            expected_portfolio_apy=0.0,
            confidence=1.0,
            recommendations=["No yield opportunities meet current criteria", "Consider lowering risk tolerance or waiting for better rates"],
            timestamp=datetime.now()
        )
    
    def _create_error_strategy(self, error_message: str) -> OptimizationStrategy:
        """Create strategy when error occurs"""
        return OptimizationStrategy(
            strategy_name="Error in Optimization",
            target_apy=0.0,
            risk_tolerance='conservative',
            allocation_distribution={},
            expected_portfolio_apy=0.0,
            confidence=0.0,
            recommendations=[f"Optimization failed: {error_message}", "Using conservative fallback strategy"],
            timestamp=datetime.now()
        )

# Global instance
_yield_optimizer = None

def get_yield_optimizer() -> YieldOptimizer:
    """Get global yield optimizer instance"""
    global _yield_optimizer
    if _yield_optimizer is None:
        _yield_optimizer = YieldOptimizer()
    return _yield_optimizer

# Test function
async def test_yield_optimizer():
    """Test the yield optimizer"""
    try:
        optimizer = get_yield_optimizer()
        
        # Sample portfolio data
        portfolio_data = {
            'total_balance_usd': 10000.0,
            'total_allocation_percent': 0.7,
            'risk_tolerance': 'medium'
        }
        
        # Test yield optimization
        print("🚀 Testing yield optimization...")
        strategy = await optimizer.optimize_yields(portfolio_data, 'medium')
        print(f"Strategy: {strategy.strategy_name}")
        print(f"Expected APY: {strategy.expected_portfolio_apy:.2f}%")
        print(f"Confidence: {strategy.confidence:.2f}")
        print(f"Allocation: {strategy.allocation_distribution}")
        print(f"Recommendations: {strategy.recommendations}")
        
        # Test arbitrage opportunities
        print("\n🔄 Testing arbitrage opportunities...")
        arbitrage_opps = await optimizer.find_cross_protocol_arbitrage()
        print(f"Found {len(arbitrage_opps)} arbitrage opportunities")
        
        for opp in arbitrage_opps[:3]:  # Show first 3
            print(f"  - {opp.source_protocol} → {opp.target_protocol}: {opp.apy_difference:.2f}% APY difference")
        
        # Test optimization summary
        print("\n📊 Testing optimization summary...")
        summary = optimizer.get_optimization_summary()
        print(f"Optimization Summary: {json.dumps(summary, indent=2)}")
        
        print("\n✅ Yield Optimizer test completed successfully!")
        
    except Exception as e:
        error(f"Yield Optimizer test failed: {str(e)}")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_yield_optimizer())
