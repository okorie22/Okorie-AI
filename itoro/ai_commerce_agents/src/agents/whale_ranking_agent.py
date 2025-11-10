"""
🐋 Whale Ranking Agent
Publishes top wallet rankings and congress leaderboards

Monitors whale wallet performance and publishes rankings through various channels
for traders to follow top-performing crypto wallets and investment strategies.
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
import logging
import requests

from ..shared.config import (
    WHALE_RANKING_UPDATE_INTERVAL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
)
from ..shared.database import get_database_manager, WhaleRanking
from ..shared.utils import (
    TelegramNotifier, api_key_manager, rate_limiter, require_api_key,
    log_execution, format_currency, format_percentage, generate_unique_id
)
from ..scripts.pricing import get_pricing_engine

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 📋 DATA MODELS
# =============================================================================

@dataclass
class RankingPublication:
    """Ranking publication tracking data model"""
    publication_id: str
    ranking_type: str  # 'top_whales', 'congress', 'performance', 'social'
    period: str  # 'daily', 'weekly', 'monthly', 'all_time'
    rankings: List[Dict[str, Any]]
    published_channels: List[str]
    publication_date: datetime
    engagement_metrics: Dict[str, int] = None  # views, likes, shares, etc.
    revenue_generated: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['publication_date'] = self.publication_date.isoformat()
        if self.engagement_metrics is None:
            data['engagement_metrics'] = {}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RankingPublication':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['publication_date'] = datetime.fromisoformat(data_copy['publication_date'])
        if 'engagement_metrics' not in data_copy:
            data_copy['engagement_metrics'] = {}
        return cls(**data_copy)

@dataclass
class WhaleAlert:
    """Whale alert data model"""
    alert_id: str
    wallet_address: str
    alert_type: str  # 'large_transaction', 'performance_change', 'new_leader'
    message: str
    confidence_score: float
    triggered_at: datetime
    published: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['triggered_at'] = self.triggered_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WhaleAlert':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['triggered_at'] = datetime.fromisoformat(data_copy['triggered_at'])
        return cls(**data_copy)

# =============================================================================
# 🐋 WHALE RANKING AGENT
# =============================================================================

class WhaleRankingAgent:
    """Agent for publishing whale wallet rankings and leaderboards"""

    def __init__(self):
        self.db = get_database_manager()
        self.db.connect()  # Ensure database connection
        self.pricing = get_pricing_engine()

        # Initialize notification channels
        self.telegram = None
        self._init_telegram()

        # Data storage
        self.publications: List[RankingPublication] = []
        self.whale_alerts: List[WhaleAlert] = []
        self.last_ranking_update = None

        # Control flags
        self.running = False
        self.update_thread = None

        # Load existing data
        self._load_publications()
        self._load_alerts()

        logger.info("✅ Whale Ranking Agent initialized")

    def _init_telegram(self):
        """Initialize Telegram notifier"""
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID:
            self.telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID)
            logger.info("✅ Telegram integration initialized")
        else:
            logger.warning("⚠️  Telegram credentials not configured")

    def _load_publications(self):
        """Load publications from storage"""
        # In a real implementation, this would load from cloud storage
        self.publications = []

    def _load_alerts(self):
        """Load whale alerts from storage"""
        # In a real implementation, this would load from cloud storage
        self.whale_alerts = []

    # =========================================================================
    # 🚀 CORE FUNCTIONALITY
    # =========================================================================

    def start(self):
        """Start the whale ranking agent"""
        if self.running:
            logger.warning("Whale Ranking Agent is already running")
            return

        self.running = True
        self.update_thread = threading.Thread(target=self._ranking_update_loop, daemon=True)
        self.update_thread.start()

        logger.info("🚀 Whale Ranking Agent started")

    def stop(self):
        """Stop the whale ranking agent"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)

        logger.info("🛑 Whale Ranking Agent stopped")

    def _ranking_update_loop(self):
        """Main ranking publication and alert monitoring loop"""
        logger.info("🐋 Starting whale ranking update loop")

        while self.running:
            try:
                # Publish regular rankings
                self._publish_rankings()

                # Check for whale alerts
                self._check_whale_alerts()

                # Clean up old publications
                self._cleanup_old_publications()

                # Sleep until next update
                time.sleep(WHALE_RANKING_UPDATE_INTERVAL)

            except Exception as e:
                logger.error(f"❌ Error in ranking update loop: {e}")
                time.sleep(60)  # Wait before retrying

    def _get_last_data_update(self) -> Optional[datetime]:
        """Get timestamp of last data update from database"""
        try:
            rankings = self.db.get_whale_rankings(limit=1)
            if rankings:
                return rankings[0].last_updated
            return None
        except Exception as e:
            logger.error(f"Failed to get last data update: {e}")
            return None

    def _publish_rankings(self):
        """Publish whale rankings on schedule (event-driven based on data freshness)"""
        now = datetime.now()

        # Check if new data is available (whale_agent runs every 24h)
        last_data_update = self._get_last_data_update()
        if not last_data_update:
            logger.debug("No whale data available yet")
            return
        
        # Only proceed if data was updated within last hour (fresh data)
        time_since_update = (now - last_data_update).total_seconds()
        if time_since_update > 3600:  # More than 1 hour old
            logger.debug(f"Data not fresh enough ({time_since_update/3600:.1f}h old), skipping publication")
            return

        # Publish daily rankings at specific times
        if self._should_publish_daily_rankings(now):
            self._publish_daily_rankings()

        # Publish weekly rankings on Sundays (changed from Monday per config)
        from ..shared.config import WHALE_RANKING_WEEKLY_SCHEDULE
        if (WHALE_RANKING_WEEKLY_SCHEDULE['enabled'] and 
            now.weekday() == WHALE_RANKING_WEEKLY_SCHEDULE['day'] and 
            now.hour == WHALE_RANKING_WEEKLY_SCHEDULE['hour']):
            if not self._published_this_week('weekly'):
                self._publish_weekly_rankings()
                
                # Also create Ocean Protocol export
                ocean_data = self.export_weekly_rankings_for_ocean()
                self._save_ocean_export(ocean_data)

        # Publish monthly rankings on 1st of month
        if now.day == 1 and now.hour == 10:  # 1st of month 10 AM
            if not self._published_this_month('monthly'):
                self._publish_monthly_rankings()

    def _should_publish_daily_rankings(self, now: datetime) -> bool:
        """Check if daily rankings should be published"""
        # Publish at 6 AM, 12 PM, 6 PM UTC
        target_hours = [6, 12, 18]
        return now.hour in target_hours and now.minute < 5  # Within first 5 minutes of hour

    def _published_this_week(self, ranking_type: str) -> bool:
        """Check if ranking type was published this week"""
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        return any(
            pub for pub in self.publications
            if pub.ranking_type == ranking_type and pub.publication_date >= week_start
        )

    def _published_this_month(self, ranking_type: str) -> bool:
        """Check if ranking type was published this month"""
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        return any(
            pub for pub in self.publications
            if pub.ranking_type == ranking_type and pub.publication_date >= month_start
        )

    def _publish_daily_rankings(self):
        """Publish daily whale rankings"""
        try:
            # Get current whale rankings
            rankings = self.db.get_whale_rankings(limit=50)

            if len(rankings) < 10:
                logger.warning("Insufficient whale data for daily rankings")
                return

            # Create publication
            publication = RankingPublication(
                publication_id=generate_unique_id('ranking'),
                ranking_type='top_whales',
                period='daily',
                rankings=[{
                    'rank': r.rank,
                    'address': r.address,
                    'twitter_handle': r.twitter_handle,
                    'pnl_30d': r.pnl_30d,
                    'pnl_7d': r.pnl_7d,
                    'pnl_1d': r.pnl_1d,
                    'score': r.score,
                    'is_blue_verified': r.is_blue_verified
                } for r in rankings],
                published_channels=[],
                publication_date=datetime.now()
            )

            # Publish to channels
            self._publish_to_channels(publication)

            # Store publication
            self.publications.append(publication)

            logger.info(f"✅ Published daily whale rankings: {publication.publication_id}")

        except Exception as e:
            logger.error(f"❌ Failed to publish daily rankings: {e}")

    def _publish_weekly_rankings(self):
        """Publish weekly whale rankings"""
        try:
            # Get top performers over the week
            rankings = self.db.get_whale_rankings(limit=100)

            # Calculate weekly performance leaders
            weekly_leaders = sorted(rankings, key=lambda x: x.pnl_7d, reverse=True)[:25]

            publication = RankingPublication(
                publication_id=generate_unique_id('ranking'),
                ranking_type='performance',
                period='weekly',
                rankings=[{
                    'rank': i + 1,
                    'address': r.address,
                    'twitter_handle': r.twitter_handle,
                    'pnl_7d': r.pnl_7d,
                    'pnl_30d': r.pnl_30d,
                    'score': r.score
                } for i, r in enumerate(weekly_leaders)],
                published_channels=[],
                publication_date=datetime.now()
            )

            self._publish_to_channels(publication)
            self.publications.append(publication)

            logger.info(f"✅ Published weekly performance rankings: {publication.publication_id}")

        except Exception as e:
            logger.error(f"❌ Failed to publish weekly rankings: {e}")

    def _publish_monthly_rankings(self):
        """Publish monthly whale rankings"""
        try:
            # Get all-time top performers
            rankings = self.db.get_whale_rankings(limit=200)

            # Sort by 30-day performance
            monthly_leaders = sorted(rankings, key=lambda x: x.pnl_30d, reverse=True)[:50]

            publication = RankingPublication(
                publication_id=generate_unique_id('ranking'),
                ranking_type='congress',
                period='monthly',
                rankings=[{
                    'rank': i + 1,
                    'address': r.address,
                    'twitter_handle': r.twitter_handle,
                    'pnl_30d': r.pnl_30d,
                    'pnl_7d': r.pnl_7d,
                    'score': r.score,
                    'is_blue_verified': r.is_blue_verified,
                    'avg_holding_period_7d': r.avg_holding_period_7d
                } for i, r in enumerate(monthly_leaders)],
                published_channels=[],
                publication_date=datetime.now()
            )

            self._publish_to_channels(publication)
            self.publications.append(publication)

            logger.info(f"✅ Published monthly congress rankings: {publication.publication_id}")

        except Exception as e:
            logger.error(f"❌ Failed to publish monthly rankings: {e}")

    def _create_weekly_top_performers(self) -> List[Dict[str, Any]]:
        """Create weekly top performing wallets list for Ocean Protocol"""
        try:
            # Get all rankings from past 7 days
            all_rankings = self.db.get_whale_rankings(limit=200)
            
            if len(all_rankings) < 10:
                logger.warning("Insufficient data for weekly rankings")
                return []
            
            # Sort by 7-day performance
            weekly_winners = sorted(all_rankings, key=lambda x: x.pnl_7d, reverse=True)[:50]
            
            # Format for Ocean Protocol
            weekly_list = []
            for i, whale in enumerate(weekly_winners):
                weekly_list.append({
                    'rank': i + 1,
                    'wallet_address': whale.address,
                    'twitter_handle': whale.twitter_handle,
                    'weekly_pnl_pct': whale.pnl_7d,
                    'monthly_pnl_pct': whale.pnl_30d,
                    'win_rate': whale.winrate_7d,
                    'total_score': whale.score,
                    'verified': whale.is_blue_verified,
                    'active_tokens': whale.token_active,
                    'avg_hold_time_days': whale.avg_holding_period_7d / 86400.0
                })
            
            return weekly_list
        except Exception as e:
            logger.error(f"Failed to create weekly top performers: {e}")
            return []

    def export_weekly_rankings_for_ocean(self) -> Dict[str, Any]:
        """Export weekly rankings in Ocean Protocol compatible format"""
        try:
            weekly_data = self._create_weekly_top_performers()
            
            if not weekly_data:
                return {'error': 'No data available'}
            
            return {
                'dataset_name': 'ITORO Top 50 Crypto Whale Wallets - Weekly',
                'description': 'Top 50 performing crypto wallets based on 7-day performance metrics',
                'data_format': 'JSON',
                'update_frequency': 'Weekly',
                'timestamp': datetime.now().isoformat(),
                'record_count': len(weekly_data),
                'rankings': weekly_data,
                'metadata': {
                    'min_score_threshold': min(r['total_score'] for r in weekly_data),
                    'avg_weekly_pnl': sum(r['weekly_pnl_pct'] for r in weekly_data) / len(weekly_data),
                    'verified_count': sum(1 for r in weekly_data if r['verified'])
                }
            }
        except Exception as e:
            logger.error(f"Failed to export weekly rankings for Ocean Protocol: {e}")
            return {'error': str(e)}

    def _save_ocean_export(self, ocean_data: Dict[str, Any]):
        """Save Ocean Protocol export to storage"""
        try:
            if 'error' in ocean_data:
                logger.warning(f"Skipping Ocean export due to error: {ocean_data['error']}")
                return
            
            # Create export directory if it doesn't exist
            import os
            from pathlib import Path
            export_dir = Path(__file__).parent.parent.parent / 'exports' / 'ocean_protocol'
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # Save to file with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = export_dir / f'whale_rankings_weekly_{timestamp}.json'
            
            import json
            with open(export_file, 'w') as f:
                json.dump(ocean_data, f, indent=2)
            
            logger.info(f"✅ Saved Ocean Protocol export to {export_file}")
            
            # Also save as latest for easy access
            latest_file = export_dir / 'whale_rankings_weekly_latest.json'
            with open(latest_file, 'w') as f:
                json.dump(ocean_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to save Ocean Protocol export: {e}")

    def _publish_to_channels(self, publication: RankingPublication):
        """Publish ranking to available channels"""
        channels_published = []

        # Publish to Telegram
        if self.telegram:
            try:
                message = self._format_ranking_message(publication)
                success = self.telegram.send_message(message)
                if success:
                    channels_published.append('telegram')
                    logger.debug("✅ Published ranking to Telegram")
            except Exception as e:
                logger.error(f"❌ Failed to publish to Telegram: {e}")

        # Store published channels
        publication.published_channels = channels_published

    def _format_ranking_message(self, publication: RankingPublication) -> str:
        """Format ranking publication for messaging"""
        ranking_type_names = {
            'top_whales': '🐋 TOP WHALE RANKINGS',
            'performance': '🚀 WEEKLY PERFORMANCE LEADERS',
            'congress': '👥 MONTHLY CONGRESS RANKINGS'
        }

        period_names = {
            'daily': 'Daily',
            'weekly': 'Weekly',
            'monthly': 'Monthly'
        }

        title = ranking_type_names.get(publication.ranking_type, 'WHALE RANKINGS')
        period = period_names.get(publication.period, publication.period.capitalize())

        message = f"""
🏆 <b>{title}</b> 🏆
📊 <i>{period} Update - {publication.publication_date.strftime('%Y-%m-%d')}</i>

"""

        # Add top 10 rankings
        for i, ranking in enumerate(publication.rankings[:10]):
            rank = ranking.get('rank', i + 1)
            address = ranking.get('address', 'Unknown')
            handle = ranking.get('twitter_handle', 'N/A')
            pnl_7d = ranking.get('pnl_7d', 0)
            score = ranking.get('score', 0)

            # Format address for display
            short_address = f"{address[:4]}...{address[-4:]}" if len(address) > 8 else address

            message += f"""{rank}. <code>{short_address}</code>"""
            if handle and handle != 'None':
                message += f" (@{handle})"
            message += f"""
   💰 7d P&L: {format_percentage(pnl_7d)}
   ⭐ Score: {score:.1f}
"""

        message += f"""

<i>Published by ITORO AI Whale Tracking</i>
🔒 <i>Premium analytics available for subscribers</i>
"""

        return message.strip()

    def _check_whale_alerts(self):
        """Check for whale alerts and publish them"""
        try:
            # Get latest rankings
            current_rankings = self.db.get_whale_rankings(limit=100)

            # Check for significant performance changes
            for ranking in current_rankings[:20]:  # Check top 20 whales
                alert = self._analyze_whale_performance(ranking)
                if alert:
                    self._publish_whale_alert(alert)

            # Check for new leaders
            top_whale = current_rankings[0] if current_rankings else None
            if top_whale and self._is_new_leader(top_whale):
                alert = WhaleAlert(
                    alert_id=generate_unique_id('alert'),
                    wallet_address=top_whale.address,
                    alert_type='new_leader',
                    message=f"New whale leader: {top_whale.twitter_handle or top_whale.address[:8]} with score {top_whale.score:.1f}",
                    confidence_score=0.9,
                    triggered_at=datetime.now()
                )
                self._publish_whale_alert(alert)

        except Exception as e:
            logger.error(f"❌ Failed to check whale alerts: {e}")

    def _analyze_whale_performance(self, ranking: WhaleRanking) -> Optional[WhaleAlert]:
        """Analyze whale performance for alerts"""
        # Check for significant P&L changes
        if ranking.pnl_1d > 0.5:  # 50% daily gain
            return WhaleAlert(
                alert_id=generate_unique_id('alert'),
                wallet_address=ranking.address,
                alert_type='performance_change',
                message=f"Major gain alert: {ranking.twitter_handle or ranking.address[:8]} up {format_percentage(ranking.pnl_1d)} in 24h",
                confidence_score=min(ranking.pnl_1d / 2.0, 0.95),  # Confidence based on gain magnitude
                triggered_at=datetime.now()
            )

        elif ranking.pnl_1d < -0.3:  # 30% daily loss
            return WhaleAlert(
                alert_id=generate_unique_id('alert'),
                wallet_address=ranking.address,
                alert_type='performance_change',
                message=f"Drawdown alert: {ranking.twitter_handle or ranking.address[:8]} down {format_percentage(ranking.pnl_1d)} in 24h",
                confidence_score=min(abs(ranking.pnl_1d) / 1.0, 0.9),
                triggered_at=datetime.now()
            )

        return None

    def _is_new_leader(self, whale: WhaleRanking) -> bool:
        """Check if whale is a new leader"""
        # Check recent publications to see if this whale was #1 before
        recent_pubs = [
            pub for pub in self.publications
            if pub.ranking_type == 'top_whales' and
            (datetime.now() - pub.publication_date).days <= 7
        ]

        for pub in recent_pubs:
            if pub.rankings and pub.rankings[0].get('address') != whale.address:
                return True

        return False

    def _publish_whale_alert(self, alert: WhaleAlert):
        """Publish whale alert to channels"""
        try:
            if self.telegram:
                message = self._format_alert_message(alert)
                success = self.telegram.send_message(message)
                if success:
                    alert.published = True
                    logger.info(f"✅ Published whale alert: {alert.alert_id}")

            # Store alert
            self.whale_alerts.append(alert)

        except Exception as e:
            logger.error(f"❌ Failed to publish whale alert: {e}")

    def _format_alert_message(self, alert: WhaleAlert) -> str:
        """Format whale alert for messaging"""
        emoji_map = {
            'large_transaction': '💰',
            'performance_change': '📈' if 'up' in alert.message else '📉',
            'new_leader': '👑'
        }

        emoji = emoji_map.get(alert.alert_type, '🐋')

        message = f"""
{emoji} <b>WHALE ALERT</b> {emoji}

{alert.message}

🎯 Confidence: {format_percentage(alert.confidence_score)}
🕒 Time: {alert.triggered_at.strftime('%H:%M:%S UTC')}

<i>Real-time whale tracking by ITORO AI</i>
"""

        return message.strip()

    def _cleanup_old_publications(self):
        """Clean up old publications (keep last 100)"""
        if len(self.publications) > 100:
            self.publications = self.publications[-100:]

        # Clean up old alerts (keep last 50)
        if len(self.whale_alerts) > 50:
            self.whale_alerts = self.whale_alerts[-50:]

    # =========================================================================
    # 📊 API ENDPOINTS
    # =========================================================================

    @require_api_key
    def get_whale_rankings(self, user_info: Dict[str, Any], limit: int = 50,
                          period: str = 'daily') -> Dict[str, Any]:
        """API endpoint to get whale rankings"""
        try:
            # Record API usage
            self.pricing.record_api_usage(
                user_id=user_info['user_id'],
                endpoint='whale_rankings'
            )

            # Get rankings based on period
            if period == 'daily':
                rankings = self.db.get_whale_rankings(limit=limit)
            elif period == 'weekly':
                # Sort by weekly performance
                all_rankings = self.db.get_whale_rankings(limit=limit * 2)
                rankings = sorted(all_rankings, key=lambda x: x.pnl_7d, reverse=True)[:limit]
            elif period == 'monthly':
                # Sort by monthly performance
                all_rankings = self.db.get_whale_rankings(limit=limit * 2)
                rankings = sorted(all_rankings, key=lambda x: x.pnl_30d, reverse=True)[:limit]
            else:
                rankings = self.db.get_whale_rankings(limit=limit)

            # Format for API response
            ranking_data = []
            for ranking in rankings:
                ranking_data.append({
                    'rank': ranking.rank,
                    'address': ranking.address,
                    'twitter_handle': ranking.twitter_handle,
                    'pnl_30d': ranking.pnl_30d,
                    'pnl_7d': ranking.pnl_7d,
                    'pnl_1d': ranking.pnl_1d,
                    'winrate_7d': ranking.winrate_7d,
                    'txs_30d': ranking.txs_30d,
                    'token_active': ranking.token_active,
                    'last_active': ranking.last_active.isoformat(),
                    'is_blue_verified': ranking.is_blue_verified,
                    'avg_holding_period_7d': ranking.avg_holding_period_7d,
                    'score': ranking.score,
                    'last_updated': ranking.last_updated.isoformat()
                })

            return {
                'status': 'success',
                'rankings': ranking_data,
                'count': len(ranking_data),
                'period': period,
                'user_tier': user_info.get('tier', 'free')
            }

        except Exception as e:
            logger.error(f"❌ Error getting whale rankings: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def get_top_performers(self, user_info: Dict[str, Any], metric: str = 'score',
                          limit: int = 25) -> Dict[str, Any]:
        """API endpoint to get top performing whales"""
        try:
            # Record API usage
            self.pricing.record_api_usage(
                user_id=user_info['user_id'],
                endpoint='whale_top_performers'
            )

            rankings = self.db.get_whale_rankings(limit=limit * 2)

            # Sort by requested metric
            if metric == 'pnl_7d':
                sorted_rankings = sorted(rankings, key=lambda x: x.pnl_7d, reverse=True)
            elif metric == 'pnl_30d':
                sorted_rankings = sorted(rankings, key=lambda x: x.pnl_30d, reverse=True)
            elif metric == 'winrate':
                sorted_rankings = sorted(rankings, key=lambda x: x.winrate_7d, reverse=True)
            elif metric == 'score':
                sorted_rankings = sorted(rankings, key=lambda x: x.score, reverse=True)
            else:
                sorted_rankings = rankings

            # Take top results
            top_rankings = sorted_rankings[:limit]

            # Format response
            performer_data = []
            for i, ranking in enumerate(top_rankings):
                performer_data.append({
                    'rank': i + 1,
                    'address': ranking.address,
                    'twitter_handle': ranking.twitter_handle,
                    'primary_metric': getattr(ranking, metric.replace('pnl_', 'pnl_')),
                    'score': ranking.score,
                    'is_blue_verified': ranking.is_blue_verified
                })

            return {
                'status': 'success',
                'performers': performer_data,
                'metric': metric,
                'count': len(performer_data)
            }

        except Exception as e:
            logger.error(f"❌ Error getting top performers: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def get_whale_alerts(self, user_info: Dict[str, Any], limit: int = 20) -> Dict[str, Any]:
        """API endpoint to get recent whale alerts"""
        try:
            # Get recent alerts
            recent_alerts = [
                alert for alert in self.whale_alerts[-limit:]
                if alert.published
            ]

            # Format for API response
            alert_data = []
            for alert in recent_alerts:
                alert_data.append({
                    'alert_id': alert.alert_id,
                    'alert_type': alert.alert_type,
                    'message': alert.message,
                    'confidence_score': alert.confidence_score,
                    'wallet_address': alert.wallet_address,
                    'triggered_at': alert.triggered_at.isoformat()
                })

            return {
                'status': 'success',
                'alerts': alert_data,
                'count': len(alert_data)
            }

        except Exception as e:
            logger.error(f"❌ Error getting whale alerts: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def subscribe_to_whale_alerts(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """API endpoint to subscribe to whale alerts"""
        try:
            # This would integrate with SignalServiceAgent for alert subscriptions
            # For now, return success
            return {
                'status': 'success',
                'message': 'Whale alert subscription configured',
                'note': 'Alerts will be sent via Telegram if configured'
            }

        except Exception as e:
            logger.error(f"❌ Error subscribing to whale alerts: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    # =========================================================================
    # 📈 ANALYTICS & MONITORING
    # =========================================================================

    def get_ranking_stats(self) -> Dict[str, Any]:
        """Get ranking publication statistics"""
        total_publications = len(self.publications)
        recent_publications = len([
            pub for pub in self.publications
            if pub.publication_date >= datetime.now() - timedelta(days=7)
        ])

        # Publication types breakdown
        type_breakdown = {}
        for pub in self.publications:
            type_breakdown[pub.ranking_type] = type_breakdown.get(pub.ranking_type, 0) + 1

        # Channel distribution
        channel_distribution = {}
        for pub in self.publications:
            for channel in pub.published_channels:
                channel_distribution[channel] = channel_distribution.get(channel, 0) + 1

        return {
            'total_publications': total_publications,
            'recent_publications': recent_publications,
            'publication_types': type_breakdown,
            'channel_distribution': channel_distribution,
            'alerts_generated': len(self.whale_alerts)
        }

    def get_whale_market_overview(self) -> Dict[str, Any]:
        """Get overview of whale market activity"""
        rankings = self.db.get_whale_rankings(limit=100)

        if not rankings:
            return {'error': 'No whale data available'}

        # Calculate market metrics
        avg_score = sum(r.score for r in rankings) / len(rankings)
        verified_percentage = sum(1 for r in rankings if r.is_blue_verified) / len(rankings) * 100
        avg_pnl_7d = sum(r.pnl_7d for r in rankings) / len(rankings)
        avg_pnl_30d = sum(r.pnl_30d for r in rankings) / len(rankings)

        # Top performers
        top_performer = max(rankings, key=lambda x: x.score)

        return {
            'total_whales_tracked': len(rankings),
            'average_score': round(avg_score, 2),
            'verified_percentage': round(verified_percentage, 1),
            'avg_pnl_7d': round(avg_pnl_7d, 4),
            'avg_pnl_30d': round(avg_pnl_30d, 4),
            'top_performer': {
                'address': top_performer.address,
                'twitter_handle': top_performer.twitter_handle,
                'score': top_performer.score,
                'pnl_30d': top_performer.pnl_30d
            }
        }

    # =========================================================================
    # 🔧 UTILITY METHODS
    # =========================================================================

    def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        return {
            'agent': 'WhaleRankingAgent',
            'running': self.running,
            'telegram_enabled': self.telegram is not None,
            'publications_count': len(self.publications),
            'alerts_count': len(self.whale_alerts),
            'last_ranking_update': self.last_ranking_update.isoformat() if self.last_ranking_update else None,
            'last_update': datetime.now().isoformat()
        }

# =============================================================================
# 🏭 FACTORY FUNCTION
# =============================================================================

_whale_ranking_agent = None

def get_whale_ranking_agent() -> WhaleRankingAgent:
    """
    Factory function to get whale ranking agent (singleton)

    Returns:
        WhaleRankingAgent instance
    """
    global _whale_ranking_agent
    if _whale_ranking_agent is None:
        _whale_ranking_agent = WhaleRankingAgent()
    return _whale_ranking_agent

# =============================================================================
# 🧪 TEST FUNCTIONS
# =============================================================================

def test_whale_ranking_agent():
    """Test whale ranking agent functionality"""
    print("🧪 Testing Whale Ranking Agent...")

    try:
        agent = get_whale_ranking_agent()

        # Test health check
        health = agent.health_check()
        print(f"✅ Agent health: {health}")

        # Test ranking stats
        ranking_stats = agent.get_ranking_stats()
        print(f"✅ Ranking stats: {ranking_stats}")

        # Test market overview
        market_overview = agent.get_whale_market_overview()
        print(f"✅ Market overview: {market_overview}")

        print("🎉 Whale Ranking Agent tests completed!")

    except Exception as e:
        print(f"❌ Whale Ranking Agent test failed: {e}")

if __name__ == "__main__":
    test_whale_ranking_agent()
