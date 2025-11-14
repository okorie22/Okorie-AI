"""
🐋 Whale Agent Integration Example
Shows how to integrate the Whale Agent with the existing trading system
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from .whale_agent import WhaleAgent, WhaleWallet

class WhaleAgentIntegration:
    """
    Integration class for using Whale Agent with the trading system
    """
    
    def __init__(self):
        """Initialize the integration"""
        self.whale_agent = WhaleAgent()
        self.logger = logging.getLogger(__name__)
        
    async def get_top_traders(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top traders for potential copy trading
        """
        try:
            # Update whale data if needed
            if self.whale_agent.should_update():
                self.logger.info("Updating whale data...")
                await self.whale_agent.update_whale_data()
            
            # Get top wallets
            top_wallets = self.whale_agent.get_top_wallets(limit, active_only=True)
            
            # Convert to trading system format
            traders = []
            for wallet in top_wallets:
                trader_info = {
                    'address': wallet.address,
                    'twitter_handle': wallet.twitter_handle,
                    'score': wallet.score,
                    'rank': wallet.rank,
                    'pnl_30d': wallet.pnl_30d,
                    'pnl_7d': wallet.pnl_7d,
                    'winrate_7d': wallet.winrate_7d,
                    'txs_30d': wallet.txs_30d,
                    'token_active': wallet.token_active,
                    'is_verified': wallet.is_blue_verified,
                    'avg_holding_period': wallet.avg_holding_period_7d,
                    'last_active': wallet.last_active,
                    'recommendation': self._get_trading_recommendation(wallet)
                }
                traders.append(trader_info)
            
            return traders
            
        except Exception as e:
            self.logger.error(f"Error getting top traders: {e}")
            return []
    
    def _get_trading_recommendation(self, wallet: WhaleWallet) -> str:
        """
        Generate trading recommendation based on wallet metrics
        """
        if wallet.score >= 0.8:
            return "STRONG_BUY"
        elif wallet.score >= 0.6:
            return "BUY"
        elif wallet.score >= 0.4:
            return "HOLD"
        else:
            return "AVOID"
    
    async def get_trader_analysis(self, address: str) -> Dict[str, Any]:
        """
        Get detailed analysis for a specific trader
        """
        try:
            wallet = self.whale_agent.get_wallet_by_address(address)
            
            if not wallet:
                return {
                    'found': False,
                    'message': 'Trader not found in ranked list'
                }
            
            # Calculate additional metrics
            risk_score = self._calculate_risk_score(wallet)
            consistency_score = self._calculate_consistency_score(wallet)
            
            analysis = {
                'found': True,
                'address': wallet.address,
                'twitter_handle': wallet.twitter_handle,
                'overall_score': wallet.score,
                'rank': wallet.rank,
                'risk_score': risk_score,
                'consistency_score': consistency_score,
                'performance': {
                    'pnl_30d': wallet.pnl_30d,
                    'pnl_7d': wallet.pnl_7d,
                    'pnl_1d': wallet.pnl_1d,
                    'winrate_7d': wallet.winrate_7d
                },
                'activity': {
                    'txs_30d': wallet.txs_30d,
                    'token_active': wallet.token_active,
                    'avg_holding_period': wallet.avg_holding_period_7d,
                    'last_active': wallet.last_active
                },
                'social': {
                    'is_verified': wallet.is_blue_verified,
                    'twitter_handle': wallet.twitter_handle
                },
                'recommendation': self._get_trading_recommendation(wallet),
                'risk_level': self._get_risk_level(risk_score),
                'copy_trading_suitable': self._is_copy_trading_suitable(wallet)
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing trader {address}: {e}")
            return {
                'found': False,
                'message': f'Error analyzing trader: {e}'
            }
    
    def _calculate_risk_score(self, wallet: WhaleWallet) -> float:
        """
        Calculate risk score (0-1, lower is less risky)
        """
        # Factors that increase risk
        high_tx_risk = min(1.0, wallet.txs_30d / 1000.0)  # More transactions = higher risk
        low_winrate_risk = 1.0 - wallet.winrate_7d  # Lower win rate = higher risk
        short_holding_risk = max(0, (1.0 - wallet.avg_holding_period_7d / 7.0))  # Shorter holding = higher risk
        
        # Weighted risk score
        risk_score = (
            0.4 * high_tx_risk +
            0.4 * low_winrate_risk +
            0.2 * short_holding_risk
        )
        
        return min(1.0, risk_score)
    
    def _calculate_consistency_score(self, wallet: WhaleWallet) -> float:
        """
        Calculate consistency score (0-1, higher is more consistent)
        """
        # High win rate indicates consistency
        winrate_consistency = wallet.winrate_7d
        
        # Reasonable transaction count indicates consistency
        tx_consistency = 1.0 - min(1.0, abs(wallet.txs_30d - 500) / 500.0)
        
        # Stable token count indicates consistency
        token_consistency = 1.0 - min(1.0, abs(wallet.token_active - 150) / 150.0)
        
        # Weighted consistency score
        consistency_score = (
            0.5 * winrate_consistency +
            0.3 * tx_consistency +
            0.2 * token_consistency
        )
        
        return max(0.0, consistency_score)
    
    def _get_risk_level(self, risk_score: float) -> str:
        """
        Get risk level description
        """
        if risk_score <= 0.3:
            return "LOW"
        elif risk_score <= 0.6:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def _is_copy_trading_suitable(self, wallet: WhaleWallet) -> bool:
        """
        Determine if wallet is suitable for copy trading
        """
        return (
            wallet.score >= 0.6 and  # Good overall score
            wallet.winrate_7d >= 0.5 and  # Decent win rate
            wallet.txs_30d <= 800 and  # Not too many transactions
            wallet.token_active >= 50 and  # Reasonable token count
            wallet.is_active  # Currently active
        )
    
    async def get_market_sentiment(self) -> Dict[str, Any]:
        """
        Get overall market sentiment based on whale activity
        """
        try:
            stats = self.whale_agent.get_wallet_statistics()
            
            if stats['active_wallets'] == 0:
                return {
                    'sentiment': 'NEUTRAL',
                    'confidence': 0.0,
                    'message': 'No active whale data available'
                }
            
            # Calculate sentiment based on average metrics
            avg_score = stats['avg_score']
            avg_pnl = stats['avg_pnl_30d']
            avg_winrate = stats['avg_winrate']
            
            # Determine sentiment
            if avg_score >= 0.7 and avg_pnl > 0 and avg_winrate >= 0.6:
                sentiment = 'BULLISH'
                confidence = min(1.0, avg_score)
            elif avg_score >= 0.5 and avg_pnl > -1000 and avg_winrate >= 0.5:
                sentiment = 'NEUTRAL'
                confidence = min(1.0, avg_score * 0.8)
            else:
                sentiment = 'BEARISH'
                confidence = min(1.0, (1.0 - avg_score) * 0.8)
            
            return {
                'sentiment': sentiment,
                'confidence': confidence,
                'metrics': {
                    'avg_score': avg_score,
                    'avg_pnl_30d': avg_pnl,
                    'avg_winrate': avg_winrate,
                    'active_wallets': stats['active_wallets'],
                    'verified_count': stats['verified_count']
                },
                'last_update': stats['last_update']
            }
            
        except Exception as e:
            self.logger.error(f"Error getting market sentiment: {e}")
            return {
                'sentiment': 'UNKNOWN',
                'confidence': 0.0,
                'message': f'Error: {e}'
            }
    
    async def get_portfolio_recommendations(self, risk_tolerance: str = 'MEDIUM') -> List[Dict[str, Any]]:
        """
        Get portfolio recommendations based on whale activity
        """
        try:
            # Get top traders
            top_traders = await self.get_top_traders(20)
            
            # Filter based on risk tolerance
            if risk_tolerance == 'LOW':
                filtered_traders = [
                    t for t in top_traders 
                    if t['score'] >= 0.7 and t['winrate_7d'] >= 0.6
                ]
            elif risk_tolerance == 'HIGH':
                filtered_traders = [
                    t for t in top_traders 
                    if t['score'] >= 0.5
                ]
            else:  # MEDIUM
                filtered_traders = [
                    t for t in top_traders 
                    if t['score'] >= 0.6 and t['winrate_7d'] >= 0.5
                ]
            
            # Create recommendations
            recommendations = []
            for i, trader in enumerate(filtered_traders[:10]):
                allocation = self._calculate_allocation(i, risk_tolerance)
                
                recommendation = {
                    'rank': i + 1,
                    'trader': trader,
                    'allocation_percent': allocation,
                    'reasoning': self._get_recommendation_reasoning(trader, allocation)
                }
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio recommendations: {e}")
            return []
    
    def _calculate_allocation(self, rank: int, risk_tolerance: str) -> float:
        """
        Calculate allocation percentage based on rank and risk tolerance
        """
        if risk_tolerance == 'LOW':
            base_allocation = 0.15  # 15% for top trader
            decay_factor = 0.7
        elif risk_tolerance == 'HIGH':
            base_allocation = 0.20  # 20% for top trader
            decay_factor = 0.8
        else:  # MEDIUM
            base_allocation = 0.18  # 18% for top trader
            decay_factor = 0.75
        
        return base_allocation * (decay_factor ** rank)
    
    def _get_recommendation_reasoning(self, trader: Dict[str, Any], allocation: float) -> str:
        """
        Generate reasoning for the recommendation
        """
        reasons = []
        
        if trader['score'] >= 0.8:
            reasons.append("Excellent overall score")
        elif trader['score'] >= 0.6:
            reasons.append("Good overall score")
        
        if trader['winrate_7d'] >= 0.7:
            reasons.append("High win rate")
        elif trader['winrate_7d'] >= 0.5:
            reasons.append("Decent win rate")
        
        if trader['is_verified']:
            reasons.append("Verified trader")
        
        if trader['pnl_30d'] > 10000:
            reasons.append("Strong 30-day performance")
        
        if trader['txs_30d'] <= 500:
            reasons.append("Reasonable transaction frequency")
        
        return f"Allocate {allocation:.1%}: " + ", ".join(reasons)

# Example usage
async def main():
    """Example usage of the Whale Agent Integration"""
    print("🐋 Whale Agent Integration Example")
    print("=" * 50)
    
    integration = WhaleAgentIntegration()
    
    # Get top traders
    print("\n🏆 Top Traders:")
    top_traders = await integration.get_top_traders(5)
    for trader in top_traders:
        print(f"  {trader['rank']}. {trader['twitter_handle']}")
        print(f"     Score: {trader['score']:.3f}")
        print(f"     PnL 30d: ${trader['pnl_30d']:,.2f}")
        print(f"     Recommendation: {trader['recommendation']}")
        print()
    
    # Get market sentiment
    print("📊 Market Sentiment:")
    sentiment = await integration.get_market_sentiment()
    print(f"  Sentiment: {sentiment['sentiment']}")
    print(f"  Confidence: {sentiment['confidence']:.1%}")
    if 'metrics' in sentiment:
        print(f"  Active Wallets: {sentiment['metrics']['active_wallets']}")
        print(f"  Average Score: {sentiment['metrics']['avg_score']:.3f}")
    
    # Get portfolio recommendations
    print("\n💼 Portfolio Recommendations (Medium Risk):")
    recommendations = await integration.get_portfolio_recommendations('MEDIUM')
    for rec in recommendations[:3]:
        trader = rec['trader']
        print(f"  {rec['rank']}. {trader['twitter_handle']}")
        print(f"     Allocation: {rec['allocation_percent']:.1%}")
        print(f"     Reasoning: {rec['reasoning']}")
        print()

if __name__ == "__main__":
    asyncio.run(main()) 