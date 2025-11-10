"""
📈 Strategy Metadata Agent
Publishes strategy summaries and risk profiles as JSON datasets

Analyzes trading strategy performance, generates risk assessments,
and publishes comprehensive strategy metadata for traders and analysts.
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
import logging
import statistics

from ..shared.config import (
    STRATEGY_METADATA_UPDATE_INTERVAL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
)
from ..shared.database import get_database_manager, StrategyMetadata, ExecutedTrade, TradingSignal
from ..shared.utils import (
    TelegramNotifier, api_key_manager, rate_limiter, require_api_key,
    log_execution, format_currency, format_percentage, generate_unique_id,
    calculate_sharpe_ratio, calculate_max_drawdown
)
from .pricing import get_pricing_engine

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 📋 DATA MODELS
# =============================================================================

@dataclass
class StrategyAnalysis:
    """Strategy analysis data model"""
    analysis_id: str
    strategy_id: str
    strategy_name: str
    agent_type: str
    analysis_period_days: int
    performance_metrics: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    market_conditions: Dict[str, Any]
    recommendations: List[str]
    confidence_score: float
    generated_at: datetime
    published: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['generated_at'] = self.generated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyAnalysis':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['generated_at'] = datetime.fromisoformat(data_copy['generated_at'])
        return cls(**data_copy)

@dataclass
class RiskAssessment:
    """Risk assessment data model"""
    assessment_id: str
    strategy_id: str
    risk_level: str  # 'low', 'medium', 'high', 'extreme'
    risk_score: float  # 0-1 scale
    risk_factors: Dict[str, float]
    mitigation_strategies: List[str]
    max_drawdown_threshold: float
    volatility_threshold: float
    assessment_date: datetime
    valid_until: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['assessment_date'] = self.assessment_date.isoformat()
        if self.valid_until:
            data['valid_until'] = self.valid_until.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RiskAssessment':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['assessment_date'] = datetime.fromisoformat(data_copy['assessment_date'])
        if 'valid_until' in data_copy and data_copy['valid_until']:
            data_copy['valid_until'] = datetime.fromisoformat(data_copy['valid_until'])
        return cls(**data_copy)

@dataclass
class StrategyPublication:
    """Strategy publication tracking data model"""
    publication_id: str
    strategy_id: str
    publication_type: str  # 'summary', 'risk_profile', 'performance_report', 'market_analysis'
    content: Dict[str, Any]
    published_channels: List[str]
    publication_date: datetime
    engagement_metrics: Dict[str, int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['publication_date'] = self.publication_date.isoformat()
        if self.engagement_metrics is None:
            data['engagement_metrics'] = {}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyPublication':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['publication_date'] = datetime.fromisoformat(data_copy['publication_date'])
        if 'engagement_metrics' not in data_copy:
            data_copy['engagement_metrics'] = {}
        return cls(**data_copy)

# =============================================================================
# 📈 STRATEGY METADATA AGENT
# =============================================================================

class StrategyMetadataAgent:
    """Agent for publishing strategy summaries and risk profiles"""

    def __init__(self):
        self.db = get_database_manager()
        self.pricing = get_pricing_engine()

        # Initialize notification channels
        self.telegram = None
        self._init_telegram()

        # Data storage
        self.analyses: List[StrategyAnalysis] = []
        self.risk_assessments: List[RiskAssessment] = []
        self.publications: List[StrategyPublication] = []

        # Control flags
        self.running = False
        self.update_thread = None

        # Load existing data
        self._load_analyses()
        self._load_risk_assessments()
        self._load_publications()

        logger.info("✅ Strategy Metadata Agent initialized")

    def _init_telegram(self):
        """Initialize Telegram notifier"""
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID:
            self.telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID)
            logger.info("✅ Telegram integration initialized")
        else:
            logger.warning("⚠️  Telegram credentials not configured")

    def _load_analyses(self):
        """Load strategy analyses from storage"""
        # In a real implementation, this would load from cloud storage
        self.analyses = []

    def _load_risk_assessments(self):
        """Load risk assessments from storage"""
        # In a real implementation, this would load from cloud storage
        self.risk_assessments = []

    def _load_publications(self):
        """Load publications from storage"""
        # In a real implementation, this would load from cloud storage
        self.publications = []

    # =========================================================================
    # 🚀 CORE FUNCTIONALITY
    # =========================================================================

    def start(self):
        """Start the strategy metadata agent"""
        if self.running:
            logger.warning("Strategy Metadata Agent is already running")
            return

        self.running = True
        self.update_thread = threading.Thread(target=self._metadata_update_loop, daemon=True)
        self.update_thread.start()

        logger.info("🚀 Strategy Metadata Agent started")

    def stop(self):
        """Stop the strategy metadata agent"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)

        logger.info("🛑 Strategy Metadata Agent stopped")

    def _metadata_update_loop(self):
        """Main strategy analysis and publication loop"""
        logger.info("📈 Starting strategy metadata update loop")

        while self.running:
            try:
                # Analyze strategies and generate metadata
                self._analyze_strategies()

                # Generate risk assessments
                self._assess_risks()

                # Publish strategy metadata
                self._publish_metadata()

                # Clean up old data
                self._cleanup_old_data()

                # Sleep until next update
                time.sleep(STRATEGY_METADATA_UPDATE_INTERVAL)

            except Exception as e:
                logger.error(f"❌ Error in metadata update loop: {e}")
                time.sleep(60)  # Wait before retrying

    def _analyze_strategies(self):
        """Analyze all active strategies and generate performance metadata"""
        try:
            # Get all strategy metadata
            strategies = self.db.get_strategy_metadata()

            for strategy in strategies:
                if not strategy.is_active:
                    continue

                # Analyze strategy performance
                analysis = self._perform_strategy_analysis(strategy)

                if analysis:
                    # Check if we already have a recent analysis
                    existing_analysis = self._get_recent_analysis(strategy.strategy_id)
                    if not existing_analysis or self._should_update_analysis(existing_analysis):
                        self.analyses.append(analysis)
                        logger.info(f"✅ Generated analysis for strategy: {strategy.strategy_name}")

        except Exception as e:
            logger.error(f"❌ Failed to analyze strategies: {e}")

    def _perform_strategy_analysis(self, strategy: StrategyMetadata) -> Optional[StrategyAnalysis]:
        """Perform detailed analysis of a trading strategy"""
        try:
            # Get trades for this strategy (we'll need to filter by agent type)
            # For now, simulate getting trade data
            trades = self.db.get_executed_trades(limit=1000)

            if len(trades) < 10:
                return None  # Insufficient data for analysis

            # Calculate performance metrics
            performance_metrics = self._calculate_performance_metrics(trades)

            # Assess market conditions
            market_conditions = self._assess_market_conditions(trades)

            # Generate recommendations
            recommendations = self._generate_strategy_recommendations(performance_metrics, market_conditions)

            # Calculate confidence score
            confidence_score = self._calculate_analysis_confidence(performance_metrics, len(trades))

            analysis = StrategyAnalysis(
                analysis_id=generate_unique_id('analysis'),
                strategy_id=strategy.strategy_id,
                strategy_name=strategy.strategy_name,
                agent_type=strategy.agent_type,
                analysis_period_days=30,  # Last 30 days
                performance_metrics=performance_metrics,
                risk_metrics=self._calculate_risk_metrics(trades),
                market_conditions=market_conditions,
                recommendations=recommendations,
                confidence_score=confidence_score,
                generated_at=datetime.now()
            )

            return analysis

        except Exception as e:
            logger.error(f"❌ Failed to analyze strategy {strategy.strategy_id}: {e}")
            return None

    def _calculate_performance_metrics(self, trades: List[ExecutedTrade]) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        if not trades:
            return {}

        # Basic metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl_realized and t.pnl_realized > 0])
        losing_trades = len([t for t in trades if t.pnl_realized and t.pnl_realized < 0])

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # P&L calculations
        realized_pnl = sum(t.pnl_realized for t in trades if t.pnl_realized) or 0
        total_volume = sum(t.value_usd for t in trades)

        # Calculate returns over time
        trade_returns = []
        cumulative_returns = []
        cumulative_pnl = 0

        for trade in sorted(trades, key=lambda x: x.timestamp):
            if trade.pnl_realized:
                trade_return = trade.pnl_realized / trade.value_usd if trade.value_usd > 0 else 0
                trade_returns.append(trade_return)
                cumulative_pnl += trade.pnl_realized
                cumulative_returns.append(cumulative_pnl / total_volume if total_volume > 0 else 0)

        # Advanced metrics
        sharpe_ratio = calculate_sharpe_ratio(trade_returns) if trade_returns else 0
        max_drawdown = calculate_max_drawdown(cumulative_returns) if cumulative_returns else 0

        # Calculate profit factor
        gross_profit = sum(t.pnl_realized for t in trades if t.pnl_realized and t.pnl_realized > 0) or 0
        gross_loss = abs(sum(t.pnl_realized for t in trades if t.pnl_realized and t.pnl_realized < 0) or 0)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'realized_pnl': realized_pnl,
            'total_volume': total_volume,
            'return_percentage': (realized_pnl / total_volume * 100) if total_volume > 0 else 0,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'avg_trade_size': total_volume / total_trades if total_trades > 0 else 0,
            'avg_win': gross_profit / winning_trades if winning_trades > 0 else 0,
            'avg_loss': gross_loss / losing_trades if losing_trades > 0 else 0
        }

    def _calculate_risk_metrics(self, trades: List[ExecutedTrade]) -> Dict[str, Any]:
        """Calculate risk metrics for the strategy"""
        if not trades:
            return {}

        # Calculate returns for risk analysis
        trade_returns = []
        for trade in trades:
            if trade.pnl_realized and trade.value_usd > 0:
                trade_returns.append(trade.pnl_realized / trade.value_usd)

        if not trade_returns:
            return {}

        # Basic risk metrics
        volatility = statistics.stdev(trade_returns) if len(trade_returns) > 1 else 0
        var_95 = self._calculate_var(trade_returns, 0.95)  # 95% Value at Risk
        var_99 = self._calculate_var(trade_returns, 0.99)  # 99% Value at Risk

        # Maximum consecutive losses
        max_consecutive_losses = self._calculate_max_consecutive_losses(trades)

        # Risk-adjusted returns
        avg_return = statistics.mean(trade_returns)
        sortino_ratio = self._calculate_sortino_ratio(trade_returns)

        return {
            'volatility': volatility,
            'var_95': var_95,
            'var_99': var_99,
            'max_consecutive_losses': max_consecutive_losses,
            'sortino_ratio': sortino_ratio,
            'return_volatility_ratio': avg_return / volatility if volatility > 0 else 0,
            'risk_adjusted_return': avg_return / abs(var_95) if var_95 != 0 else 0
        }

    def _calculate_var(self, returns: List[float], confidence_level: float) -> float:
        """Calculate Value at Risk"""
        if not returns:
            return 0

        sorted_returns = sorted(returns)
        index = int((1 - confidence_level) * len(sorted_returns))
        return abs(sorted_returns[index])

    def _calculate_max_consecutive_losses(self, trades: List[ExecutedTrade]) -> int:
        """Calculate maximum consecutive losing trades"""
        max_consecutive = 0
        current_consecutive = 0

        for trade in trades:
            if trade.pnl_realized and trade.pnl_realized < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def _calculate_sortino_ratio(self, returns: List[float]) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        if not returns:
            return 0

        # Calculate downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]
        if not negative_returns:
            return float('inf')  # No downside risk

        downside_deviation = statistics.stdev(negative_returns)
        avg_return = statistics.mean(returns)

        return avg_return / downside_deviation if downside_deviation > 0 else float('inf')

    def _assess_market_conditions(self, trades: List[ExecutedTrade]) -> Dict[str, Any]:
        """Assess market conditions during trading period"""
        if not trades:
            return {}

        # Group trades by symbol
        symbol_performance = {}
        for trade in trades:
            if trade.symbol not in symbol_performance:
                symbol_performance[trade.symbol] = {'trades': 0, 'pnl': 0}

            symbol_performance[trade.symbol]['trades'] += 1
            if trade.pnl_realized:
                symbol_performance[trade.symbol]['pnl'] += trade.pnl_realized

        # Find best and worst performing symbols
        best_symbol = max(symbol_performance.items(), key=lambda x: x[1]['pnl']) if symbol_performance else None
        worst_symbol = min(symbol_performance.items(), key=lambda x: x[1]['pnl']) if symbol_performance else None

        # Calculate trade frequency by hour
        hourly_distribution = {}
        for trade in trades:
            hour = trade.timestamp.hour
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1

        peak_hour = max(hourly_distribution.items(), key=lambda x: x[1]) if hourly_distribution else None

        return {
            'total_symbols_traded': len(symbol_performance),
            'best_performing_symbol': {
                'symbol': best_symbol[0] if best_symbol else None,
                'pnl': best_symbol[1]['pnl'] if best_symbol else 0,
                'trades': best_symbol[1]['trades'] if best_symbol else 0
            } if best_symbol else {},
            'worst_performing_symbol': {
                'symbol': worst_symbol[0] if worst_symbol else None,
                'pnl': worst_symbol[1]['pnl'] if worst_symbol else 0,
                'trades': worst_symbol[1]['trades'] if worst_symbol else 0
            } if worst_symbol else {},
            'peak_trading_hour': peak_hour[0] if peak_hour else None,
            'trading_hour_distribution': hourly_distribution
        }

    def _generate_strategy_recommendations(self, performance: Dict[str, Any],
                                         market_conditions: Dict[str, Any]) -> List[str]:
        """Generate strategy recommendations based on analysis"""
        recommendations = []

        # Performance-based recommendations
        win_rate = performance.get('win_rate', 0)
        if win_rate < 0.4:
            recommendations.append("Consider adjusting entry criteria - win rate below 40%")
        elif win_rate > 0.7:
            recommendations.append("Strong win rate - consider increasing position sizes")

        sharpe_ratio = performance.get('sharpe_ratio', 0)
        if sharpe_ratio < 0.5:
            recommendations.append("Risk-adjusted returns need improvement - consider reducing volatility")
        elif sharpe_ratio > 2.0:
            recommendations.append("Excellent risk-adjusted performance - strategy is well-balanced")

        max_drawdown = performance.get('max_drawdown', 0)
        if max_drawdown > 0.3:
            recommendations.append("High drawdown detected - implement stricter risk management")
        elif max_drawdown < 0.1:
            recommendations.append("Low drawdown - strategy demonstrates good risk control")

        # Market condition recommendations
        best_symbol = market_conditions.get('best_performing_symbol', {})
        if best_symbol.get('symbol'):
            recommendations.append(f"Strong performance in {best_symbol['symbol']} - consider increasing allocation")

        peak_hour = market_conditions.get('peak_trading_hour')
        if peak_hour is not None:
            recommendations.append(f"Optimal trading time identified: {peak_hour:02d}:00 UTC")

        return recommendations[:5]  # Limit to top 5 recommendations

    def _calculate_analysis_confidence(self, performance: Dict[str, Any], sample_size: int) -> float:
        """Calculate confidence score for the analysis"""
        # Base confidence on sample size
        size_confidence = min(sample_size / 100, 1.0)  # Max confidence at 100+ trades

        # Adjust based on performance metrics consistency
        win_rate = performance.get('win_rate', 0)
        consistency_bonus = 1.0 if 0.4 <= win_rate <= 0.7 else 0.8  # Prefer balanced strategies

        sharpe_ratio = performance.get('sharpe_ratio', 0)
        risk_adjustment = min(sharpe_ratio / 2.0, 1.0)  # Better Sharpe = higher confidence

        return min(size_confidence * consistency_bonus * (0.5 + risk_adjustment * 0.5), 1.0)

    def _assess_risks(self):
        """Generate risk assessments for all strategies"""
        try:
            strategies = self.db.get_strategy_metadata()

            for strategy in strategies:
                if not strategy.is_active:
                    continue

                assessment = self._generate_risk_assessment(strategy)
                if assessment:
                    self.risk_assessments.append(assessment)

        except Exception as e:
            logger.error(f"❌ Failed to assess risks: {e}")

    def _generate_risk_assessment(self, strategy: StrategyMetadata) -> Optional[RiskAssessment]:
        """Generate comprehensive risk assessment for a strategy"""
        try:
            # Get recent analysis
            analysis = self._get_recent_analysis(strategy.strategy_id)
            if not analysis:
                return None

            risk_metrics = analysis.risk_metrics
            performance = analysis.performance_metrics

            # Calculate overall risk score
            volatility = risk_metrics.get('volatility', 0)
            max_drawdown = performance.get('max_drawdown', 0)
            var_95 = risk_metrics.get('var_95', 0)
            consecutive_losses = risk_metrics.get('max_consecutive_losses', 0)

            # Risk scoring algorithm
            risk_score = (
                volatility * 0.3 +
                max_drawdown * 0.3 +
                var_95 * 0.2 +
                min(consecutive_losses / 10, 1.0) * 0.2  # Cap at 10 consecutive losses
            )

            # Determine risk level
            if risk_score < 0.3:
                risk_level = 'low'
            elif risk_score < 0.6:
                risk_level = 'medium'
            elif risk_score < 0.8:
                risk_level = 'high'
            else:
                risk_level = 'extreme'

            # Identify key risk factors
            risk_factors = {
                'volatility': volatility,
                'max_drawdown': max_drawdown,
                'value_at_risk': var_95,
                'concentration_risk': consecutive_losses / 10  # Normalized
            }

            # Generate mitigation strategies
            mitigation_strategies = self._generate_risk_mitigations(risk_level, risk_factors)

            assessment = RiskAssessment(
                assessment_id=generate_unique_id('risk'),
                strategy_id=strategy.strategy_id,
                risk_level=risk_level,
                risk_score=risk_score,
                risk_factors=risk_factors,
                mitigation_strategies=mitigation_strategies,
                max_drawdown_threshold=0.25,  # 25% max drawdown threshold
                volatility_threshold=0.5,     # 50% volatility threshold
                assessment_date=datetime.now(),
                valid_until=datetime.now() + timedelta(days=30)
            )

            return assessment

        except Exception as e:
            logger.error(f"❌ Failed to generate risk assessment for {strategy.strategy_id}: {e}")
            return None

    def _generate_risk_mitigations(self, risk_level: str, risk_factors: Dict[str, float]) -> List[str]:
        """Generate risk mitigation strategies"""
        mitigations = []

        if risk_level in ['high', 'extreme']:
            mitigations.append("Implement maximum drawdown limits (recommended: 20-25%)")
            mitigations.append("Reduce position sizes to lower volatility")

        if risk_factors.get('max_drawdown', 0) > 0.25:
            mitigations.append("Add stop-loss mechanisms and position size reduction")

        if risk_factors.get('volatility', 0) > 0.4:
            mitigations.append("Diversify across more assets to reduce concentration risk")

        if risk_factors.get('value_at_risk', 0) > 0.15:
            mitigations.append("Implement Value at Risk (VaR) limits for daily exposure")

        if risk_factors.get('concentration_risk', 0) > 0.5:
            mitigations.append("Avoid consecutive position increases during losing streaks")

        # Default mitigations
        if not mitigations:
            mitigations = [
                "Regular strategy performance monitoring",
                "Maintain emergency stop-loss protocols",
                "Keep sufficient cash reserves for opportunities"
            ]

        return mitigations[:5]  # Limit to top 5

    def _publish_metadata(self):
        """Publish strategy metadata and analyses"""
        try:
            # Publish strategy summaries
            self._publish_strategy_summaries()

            # Publish risk profiles
            self._publish_risk_profiles()

            # Publish performance reports
            self._publish_performance_reports()

        except Exception as e:
            logger.error(f"❌ Failed to publish metadata: {e}")

    def _publish_strategy_summaries(self):
        """Publish strategy summary reports"""
        recent_analyses = [
            analysis for analysis in self.analyses
            if not analysis.published and analysis.generated_at >= datetime.now() - timedelta(hours=1)
        ]

        for analysis in recent_analyses:
            try:
                publication = StrategyPublication(
                    publication_id=generate_unique_id('pub'),
                    strategy_id=analysis.strategy_id,
                    publication_type='summary',
                    content={
                        'strategy_name': analysis.strategy_name,
                        'agent_type': analysis.agent_type,
                        'performance_summary': {
                            'win_rate': analysis.performance_metrics.get('win_rate', 0),
                            'total_return': analysis.performance_metrics.get('return_percentage', 0),
                            'sharpe_ratio': analysis.performance_metrics.get('sharpe_ratio', 0),
                            'max_drawdown': analysis.performance_metrics.get('max_drawdown', 0)
                        },
                        'risk_assessment': analysis.risk_metrics,
                        'recommendations': analysis.recommendations,
                        'confidence_score': analysis.confidence_score
                    },
                    published_channels=[],
                    publication_date=datetime.now()
                )

                # Publish to channels
                self._publish_to_channels(publication)
                self.publications.append(publication)
                analysis.published = True

            except Exception as e:
                logger.error(f"❌ Failed to publish summary for {analysis.strategy_id}: {e}")

    def _publish_risk_profiles(self):
        """Publish risk profile reports"""
        recent_assessments = [
            assessment for assessment in self.risk_assessments
            if assessment.assessment_date >= datetime.now() - timedelta(hours=1)
        ]

        for assessment in recent_assessments:
            try:
                publication = StrategyPublication(
                    publication_id=generate_unique_id('pub'),
                    strategy_id=assessment.strategy_id,
                    publication_type='risk_profile',
                    content={
                        'risk_level': assessment.risk_level,
                        'risk_score': assessment.risk_score,
                        'key_risk_factors': assessment.risk_factors,
                        'mitigation_strategies': assessment.mitigation_strategies,
                        'thresholds': {
                            'max_drawdown': assessment.max_drawdown_threshold,
                            'volatility': assessment.volatility_threshold
                        }
                    },
                    published_channels=[],
                    publication_date=datetime.now()
                )

                self._publish_to_channels(publication)
                self.publications.append(publication)

            except Exception as e:
                logger.error(f"❌ Failed to publish risk profile for {assessment.strategy_id}: {e}")

    def _publish_performance_reports(self):
        """Publish comprehensive performance reports"""
        # Publish weekly performance report every Monday
        if datetime.now().weekday() == 0 and datetime.now().hour == 8:
            if not self._published_this_week('performance_report'):
                self._publish_weekly_performance_report()

    def _publish_weekly_performance_report(self):
        """Publish weekly comprehensive performance report"""
        try:
            # Gather all recent analyses
            weekly_analyses = [
                analysis for analysis in self.analyses
                if analysis.generated_at >= datetime.now() - timedelta(days=7)
            ]

            if not weekly_analyses:
                return

            # Aggregate performance data
            total_strategies = len(set(a.strategy_id for a in weekly_analyses))
            avg_win_rate = statistics.mean(a.performance_metrics.get('win_rate', 0) for a in weekly_analyses)
            avg_sharpe = statistics.mean(a.performance_metrics.get('sharpe_ratio', 0) for a in weekly_analyses)

            # Strategy rankings
            strategy_performance = []
            for analysis in weekly_analyses:
                perf = analysis.performance_metrics
                strategy_performance.append({
                    'strategy_name': analysis.strategy_name,
                    'win_rate': perf.get('win_rate', 0),
                    'total_return': perf.get('return_percentage', 0),
                    'sharpe_ratio': perf.get('sharpe_ratio', 0),
                    'max_drawdown': perf.get('max_drawdown', 0)
                })

            # Sort by Sharpe ratio
            strategy_performance.sort(key=lambda x: x['sharpe_ratio'], reverse=True)

            publication = StrategyPublication(
                publication_id=generate_unique_id('pub'),
                strategy_id='weekly_report',
                publication_type='performance_report',
                content={
                    'report_type': 'weekly_performance_summary',
                    'period': 'last_7_days',
                    'summary_stats': {
                        'total_strategies_analyzed': total_strategies,
                        'average_win_rate': avg_win_rate,
                        'average_sharpe_ratio': avg_sharpe,
                        'total_analyses': len(weekly_analyses)
                    },
                    'top_performers': strategy_performance[:5],
                    'market_insights': self._generate_market_insights(weekly_analyses)
                },
                published_channels=[],
                publication_date=datetime.now()
            )

            self._publish_to_channels(publication)
            self.publications.append(publication)

        except Exception as e:
            logger.error(f"❌ Failed to publish weekly performance report: {e}")

    def _generate_market_insights(self, analyses: List[StrategyAnalysis]) -> List[str]:
        """Generate market insights from strategy analyses"""
        insights = []

        # Analyze overall market performance
        avg_returns = [a.performance_metrics.get('return_percentage', 0) for a in analyses]
        if avg_returns:
            avg_market_return = statistics.mean(avg_returns)
            if avg_market_return > 5:
                insights.append("Bullish market conditions detected across strategies")
            elif avg_market_return < -5:
                insights.append("Bearish market conditions - increased volatility observed")

        # Analyze risk trends
        avg_volatility = statistics.mean([
            a.risk_metrics.get('volatility', 0) for a in analyses
            if a.risk_metrics.get('volatility', 0) > 0
        ]) if analyses else 0

        if avg_volatility > 0.3:
            insights.append("High market volatility - risk management crucial")
        elif avg_volatility < 0.1:
            insights.append("Low volatility environment - opportunities for momentum strategies")

        return insights

    def _publish_to_channels(self, publication: StrategyPublication):
        """Publish content to available channels"""
        channels_published = []

        # Publish to Telegram
        if self.telegram:
            try:
                message = self._format_publication_message(publication)
                success = self.telegram.send_message(message)
                if success:
                    channels_published.append('telegram')
            except Exception as e:
                logger.error(f"❌ Failed to publish to Telegram: {e}")

        publication.published_channels = channels_published

    def _format_publication_message(self, publication: StrategyPublication) -> str:
        """Format publication for messaging"""
        content = publication.content

        if publication.publication_type == 'summary':
            message = f"""
📊 <b>STRATEGY ANALYSIS</b> 📊
<b>{content['strategy_name']}</b> ({content['agent_type']})

<b>Performance:</b>
• Win Rate: {format_percentage(content['performance_summary']['win_rate'])}
• Total Return: {format_percentage(content['performance_summary']['total_return'])}
• Sharpe Ratio: {content['performance_summary']['sharpe_ratio']:.2f}
• Max Drawdown: {format_percentage(content['performance_summary']['max_drawdown'])}

<b>Risk Metrics:</b>
• Volatility: {format_percentage(content['risk_metrics'].get('volatility', 0))}
• VaR (95%): {format_percentage(content['risk_metrics'].get('var_95', 0))}

<b>Confidence:</b> {format_percentage(content['confidence_score'])}

<i>Analysis by ITORO Strategy Intelligence</i>
"""

        elif publication.publication_type == 'risk_profile':
            message = f"""
⚠️ <b>RISK ASSESSMENT</b> ⚠️
<b>Risk Level:</b> {content['risk_level'].upper()}
<b>Risk Score:</b> {content['risk_score']:.2f}

<b>Key Risk Factors:</b>
• Volatility: {format_percentage(content['key_risk_factors'].get('volatility', 0))}
• Max Drawdown: {format_percentage(content['key_risk_factors'].get('max_drawdown', 0))}
• Value at Risk: {format_percentage(content['key_risk_factors'].get('value_at_risk', 0))}

<b>Recommendations:</b>
{chr(10).join('• ' + rec for rec in content['mitigation_strategies'][:3])}

<i>ITORO Risk Management System</i>
"""

        elif publication.publication_type == 'performance_report':
            message = f"""
📈 <b>WEEKLY PERFORMANCE REPORT</b> 📈

<b>Market Overview:</b>
• Strategies Analyzed: {content['summary_stats']['total_strategies_analyzed']}
• Avg Win Rate: {format_percentage(content['summary_stats']['average_win_rate'])}
• Avg Sharpe Ratio: {content['summary_stats']['average_sharpe_ratio']:.2f}

<b>Top Performers:</b>
"""

            for i, performer in enumerate(content['top_performers'][:3]):
                message += f"{i+1}. {performer['strategy_name']} (Sharpe: {performer['sharpe_ratio']:.2f})\n"

            if content.get('market_insights'):
                message += f"\n<b>Market Insights:</b>\n"
                message += "\n".join('• ' + insight for insight in content['market_insights'])

            message += f"\n<i>Weekly analysis by ITORO Intelligence</i>"

        return message.strip()

    def _get_recent_analysis(self, strategy_id: str) -> Optional[StrategyAnalysis]:
        """Get the most recent analysis for a strategy"""
        strategy_analyses = [
            analysis for analysis in self.analyses
            if analysis.strategy_id == strategy_id
        ]

        if not strategy_analyses:
            return None

        return max(strategy_analyses, key=lambda x: x.generated_at)

    def _should_update_analysis(self, analysis: StrategyAnalysis) -> bool:
        """Check if analysis should be updated"""
        # Update if older than 24 hours
        return (datetime.now() - analysis.generated_at).total_seconds() > 86400

    def _published_this_week(self, publication_type: str) -> bool:
        """Check if publication type was published this week"""
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        return any(
            pub for pub in self.publications
            if pub.publication_type == publication_type and pub.publication_date >= week_start
        )

    def _cleanup_old_data(self):
        """Clean up old analyses and publications"""
        cutoff_date = datetime.now() - timedelta(days=90)

        # Remove old analyses
        self.analyses = [a for a in self.analyses if a.generated_at >= cutoff_date]

        # Remove old risk assessments
        self.risk_assessments = [r for r in self.risk_assessments if r.assessment_date >= cutoff_date]

        # Remove old publications (keep last 200)
        if len(self.publications) > 200:
            self.publications = self.publications[-200:]

    # =========================================================================
    # 📊 API ENDPOINTS
    # =========================================================================

    @require_api_key
    def get_strategy_analysis(self, user_info: Dict[str, Any], strategy_id: Optional[str] = None,
                            analysis_type: str = 'performance') -> Dict[str, Any]:
        """API endpoint to get strategy analysis"""
        try:
            # Record API usage
            self.pricing.record_api_usage(
                user_id=user_info['user_id'],
                endpoint='strategy_analysis'
            )

            if strategy_id:
                # Get specific strategy analysis
                analysis = self._get_recent_analysis(strategy_id)
                if not analysis:
                    return {'error': 'Strategy analysis not found', 'status': 'error'}

                response_data = analysis.to_dict()
            else:
                # Get all recent analyses
                recent_analyses = [
                    analysis for analysis in self.analyses
                    if analysis.generated_at >= datetime.now() - timedelta(days=7)
                ]

                response_data = {
                    'analyses': [a.to_dict() for a in recent_analyses],
                    'count': len(recent_analyses)
                }

            return {
                'status': 'success',
                'data': response_data,
                'user_tier': user_info.get('tier', 'free')
            }

        except Exception as e:
            logger.error(f"❌ Error getting strategy analysis: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def get_risk_assessment(self, user_info: Dict[str, Any], strategy_id: str) -> Dict[str, Any]:
        """API endpoint to get risk assessment for a strategy"""
        try:
            # Record API usage
            self.pricing.record_api_usage(
                user_id=user_info['user_id'],
                endpoint='risk_assessment'
            )

            # Get recent risk assessment
            recent_assessments = [
                assessment for assessment in self.risk_assessments
                if assessment.strategy_id == strategy_id and
                assessment.assessment_date >= datetime.now() - timedelta(days=30)
            ]

            if not recent_assessments:
                return {'error': 'Risk assessment not found', 'status': 'error'}

            # Return most recent assessment
            assessment = max(recent_assessments, key=lambda x: x.assessment_date)

            return {
                'status': 'success',
                'assessment': assessment.to_dict()
            }

        except Exception as e:
            logger.error(f"❌ Error getting risk assessment: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def get_strategy_metadata(self, user_info: Dict[str, Any], include_analysis: bool = False) -> Dict[str, Any]:
        """API endpoint to get all strategy metadata"""
        try:
            # Record API usage
            self.pricing.record_api_usage(
                user_id=user_info['user_id'],
                endpoint='strategy_metadata'
            )

            # Get all strategy metadata
            strategies = self.db.get_strategy_metadata()

            strategy_data = []
            for strategy in strategies:
                strategy_dict = strategy.to_dict()

                if include_analysis:
                    analysis = self._get_recent_analysis(strategy.strategy_id)
                    if analysis:
                        strategy_dict['latest_analysis'] = analysis.to_dict()

                strategy_data.append(strategy_dict)

            return {
                'status': 'success',
                'strategies': strategy_data,
                'count': len(strategy_data),
                'include_analysis': include_analysis
            }

        except Exception as e:
            logger.error(f"❌ Error getting strategy metadata: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def get_performance_report(self, user_info: Dict[str, Any], period: str = 'weekly') -> Dict[str, Any]:
        """API endpoint to get performance reports"""
        try:
            # Record API usage
            self.pricing.record_api_usage(
                user_id=user_info['user_id'],
                endpoint='performance_report'
            )

            # Get publications of the specified type
            if period == 'weekly':
                pub_type = 'performance_report'
            elif period == 'daily':
                pub_type = 'summary'
            else:
                pub_type = 'performance_report'

            recent_pubs = [
                pub for pub in self.publications
                if pub.publication_type == pub_type and
                pub.publication_date >= datetime.now() - timedelta(days=7)
            ]

            if not recent_pubs:
                return {'error': 'No recent performance reports available', 'status': 'error'}

            # Return most recent report
            report = max(recent_pubs, key=lambda x: x.publication_date)

            return {
                'status': 'success',
                'report': report.to_dict()
            }

        except Exception as e:
            logger.error(f"❌ Error getting performance report: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    # =========================================================================
    # 📈 ANALYTICS & MONITORING
    # =========================================================================

    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy metadata statistics"""
        total_strategies = len(set(a.strategy_id for a in self.analyses))
        total_analyses = len(self.analyses)
        total_assessments = len(self.risk_assessments)
        total_publications = len(self.publications)

        # Analysis frequency
        recent_analyses = len([
            a for a in self.analyses
            if a.generated_at >= datetime.now() - timedelta(days=7)
        ])

        # Risk level distribution
        risk_levels = {}
        for assessment in self.risk_assessments:
            risk_levels[assessment.risk_level] = risk_levels.get(assessment.risk_level, 0) + 1

        # Publication types
        pub_types = {}
        for pub in self.publications:
            pub_types[pub.publication_type] = pub_types.get(pub.publication_type, 0) + 1

        return {
            'total_strategies': total_strategies,
            'total_analyses': total_analyses,
            'total_risk_assessments': total_assessments,
            'total_publications': total_publications,
            'recent_analyses': recent_analyses,
            'risk_level_distribution': risk_levels,
            'publication_types': pub_types
        }

    def get_market_intelligence(self) -> Dict[str, Any]:
        """Get aggregated market intelligence from all strategies"""
        try:
            recent_analyses = [
                a for a in self.analyses
                if a.generated_at >= datetime.now() - timedelta(days=7)
            ]

            if not recent_analyses:
                return {'error': 'Insufficient data for market intelligence'}

            # Aggregate performance metrics
            win_rates = [a.performance_metrics.get('win_rate', 0) for a in recent_analyses]
            returns = [a.performance_metrics.get('return_percentage', 0) for a in recent_analyses]
            volatilities = [a.risk_metrics.get('volatility', 0) for a in recent_analyses]

            # Market sentiment based on aggregated metrics
            avg_win_rate = statistics.mean(win_rates) if win_rates else 0
            avg_return = statistics.mean(returns) if returns else 0
            avg_volatility = statistics.mean(volatilities) if volatilities else 0

            # Determine market sentiment
            if avg_win_rate > 0.6 and avg_return > 2:
                sentiment = 'bullish'
            elif avg_win_rate < 0.4 or avg_return < -2:
                sentiment = 'bearish'
            else:
                sentiment = 'neutral'

            return {
                'market_sentiment': sentiment,
                'confidence_score': min(abs(avg_return) / 10, 1.0),  # Confidence based on return magnitude
                'aggregated_metrics': {
                    'average_win_rate': avg_win_rate,
                    'average_return': avg_return,
                    'average_volatility': avg_volatility,
                    'strategies_analyzed': len(recent_analyses)
                },
                'volatility_level': 'high' if avg_volatility > 0.3 else 'low' if avg_volatility < 0.1 else 'moderate',
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Failed to generate market intelligence: {e}")
            return {'error': 'Failed to generate market intelligence'}

    # =========================================================================
    # 🔧 UTILITY METHODS
    # =========================================================================

    def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        return {
            'agent': 'StrategyMetadataAgent',
            'running': self.running,
            'analyses_count': len(self.analyses),
            'assessments_count': len(self.risk_assessments),
            'publications_count': len(self.publications),
            'telegram_enabled': self.telegram is not None,
            'last_update': datetime.now().isoformat()
        }

# =============================================================================
# 🏭 FACTORY FUNCTION
# =============================================================================

_strategy_metadata_agent = None

def get_strategy_metadata_agent() -> StrategyMetadataAgent:
    """
    Factory function to get strategy metadata agent (singleton)

    Returns:
        StrategyMetadataAgent instance
    """
    global _strategy_metadata_agent
    if _strategy_metadata_agent is None:
        _strategy_metadata_agent = StrategyMetadataAgent()
    return _strategy_metadata_agent

# =============================================================================
# 🧪 TEST FUNCTIONS
# =============================================================================

def test_strategy_metadata_agent():
    """Test strategy metadata agent functionality"""
    print("🧪 Testing Strategy Metadata Agent...")

    try:
        agent = get_strategy_metadata_agent()

        # Test health check
        health = agent.health_check()
        print(f"✅ Agent health: {health}")

        # Test strategy stats
        stats = agent.get_strategy_stats()
        print(f"✅ Strategy stats: {stats}")

        # Test market intelligence
        intelligence = agent.get_market_intelligence()
        print(f"✅ Market intelligence: {intelligence}")

        print("🎉 Strategy Metadata Agent tests completed!")

    except Exception as e:
        print(f"❌ Strategy Metadata Agent test failed: {e}")

if __name__ == "__main__":
    test_strategy_metadata_agent()
