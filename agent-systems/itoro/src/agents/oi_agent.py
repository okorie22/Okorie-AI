"""
OI Agent - Open Interest Data Collection & Analytics
Built with love by Anarcho Capital 🚀

Collects open interest data from Hyperliquid for top cryptocurrencies,
stores locally in Parquet format and to Supabase cloud database,
calculates comprehensive analytics for data monetization.
"""

import os
import sys
import pandas as pd
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import requests
from src.agents.base_agent import BaseAgent
from src.scripts.oi.oi_storage import OIStorage
from src.scripts.oi.oi_analytics import OIAnalytics
from src.scripts.shared_services.redis_event_bus import get_event_bus
from src.scripts.shared_services.alert_system import MarketAlert, AlertType, AlertSeverity
import traceback
from typing import List, Dict, Optional

# Import logger
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
except ImportError:
    def debug(msg, file_only=False):
        if not file_only:
            print(f"DEBUG: {msg}")
    def info(msg):
        print(f"INFO: {msg}")
    def warning(msg):
        print(f"WARNING: {msg}")
    def error(msg):
        print(f"ERROR: {msg}")

# Constants for Hyperliquid API
BASE_URL = 'https://api.hyperliquid.xyz/info'

# Import shared Hyperliquid functions
try:
    from src.nice_funcs_hl import get_funding_rates as hl_get_funding_rates, get_24h_volume as hl_get_24h_volume
    SHARED_HL_AVAILABLE = True
except ImportError:
    SHARED_HL_AVAILABLE = False
    warning("Shared Hyperliquid functions not available")

# Import cloud database manager
try:
    from src.scripts.database.cloud_database import get_cloud_database_manager
    CLOUD_DB_AVAILABLE = True
except ImportError:
    CLOUD_DB_AVAILABLE = False
    warning("Cloud database not available")

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration - Import from config
from src import config

# OI Agent Configuration
CHECK_INTERVAL_HOURS = getattr(config, 'OI_CHECK_INTERVAL_HOURS', 4)
TRACKED_SYMBOLS = getattr(config, 'OI_TRACKED_SYMBOLS', ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'AVAX', 'MATIC', 'DOT'])
LOCAL_RETENTION_DAYS = getattr(config, 'OI_LOCAL_RETENTION_DAYS', 30)
AI_INSIGHTS_ENABLED = getattr(config, 'OI_AI_INSIGHTS_ENABLED', True)

# Lookback periods for analytics
LOOKBACK_PERIODS = {
    '4h': 4,
    '24h': 24,
    '7d': 168
}

# AI Analysis Prompt for insights
AI_INSIGHTS_PROMPT = """Analyze the following Open Interest analytics and provide market insights:

Symbol: {symbol}
Timeframe: {timeframe}

Metrics:
- OI Change: {oi_change_pct}%
- Funding Rate Change: {funding_change_pct}%
- OI/Volume Ratio: {oi_volume_ratio}
- Liquidity: {liquidity_status}

Provide a brief market insight (max 2 sentences) about what this data suggests."""


class OIAgent(BaseAgent):
    """OI Agent - Open Interest Data Collection & Analytics"""
    
    def __init__(self):
        """Initialize OI Agent"""
        super().__init__('OI')
        
        load_dotenv()
        
        # Initialize storage and analytics engines
        self.local_storage = OIStorage()
        self.analytics_engine = OIAnalytics()
        
        # Initialize cloud database if available
        if CLOUD_DB_AVAILABLE:
            self.cloud_storage = get_cloud_database_manager()
            if self.cloud_storage:
                info("✅ Cloud database connected")
            else:
                warning("⚠️ Cloud database not available")
                self.cloud_storage = None
        else:
            self.cloud_storage = None
            warning("⚠️ Cloud database module not available")
        
        # Initialize AI client for insights if enabled
        self.ai_model = None
        if AI_INSIGHTS_ENABLED:
            try:
                from src.models.model_factory import model_factory
                self.ai_model = model_factory.get_model('deepseek', 'deepseek-chat')
                if self.ai_model and self.ai_model.is_available():
                    info("🤖 AI insights enabled with DeepSeek")
                else:
                    warning("⚠️ DeepSeek model not available - AI insights disabled")
                    self.ai_model = None
            except ImportError as e:
                warning(f"⚠️ Model factory not available: {e} - AI insights disabled")
                self.ai_model = None
        
        # Initialize Redis event bus for alert publishing
        self.event_bus = get_event_bus()

        info(f"📊 OI Agent initialized - tracking {len(TRACKED_SYMBOLS)} symbols every {CHECK_INTERVAL_HOURS}h")
        info("🔄 Event bus connected for real-time alert publishing")

    def _serialize_for_json(self, data):
        """Convert pandas objects to JSON-serializable format"""
        if isinstance(data, dict):
            return {k: self._serialize_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_for_json(item) for item in data]
        elif hasattr(data, 'isoformat'):  # pandas Timestamp, datetime, etc.
            return data.isoformat()
        elif hasattr(data, 'item'):  # numpy scalars
            return data.item()
        else:
            return data

    def get_funding_rates(self, symbol):
        """
        Get current funding rate for a specific coin on Hyperliquid

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTC', 'ETH', 'FART')

        Returns:
            dict: Funding data including rate, mark price, and open interest
        """
        if SHARED_HL_AVAILABLE:
            # Use shared service for better API efficiency
            return hl_get_funding_rates(symbol)
        else:
            # Fallback to local implementation
            try:
                debug(f"Fetching funding rate for {symbol}...")
                response = requests.post(
                    BASE_URL,
                    headers={'Content-Type': 'application/json'},
                    json={"type": "metaAndAssetCtxs"}
                )

                if response.status_code == 200:
                    data = response.json()
                    if len(data) >= 2 and isinstance(data[0], dict) and isinstance(data[1], list):
                        # Get universe (symbols) from first element
                        universe = {coin['name']: i for i, coin in enumerate(data[0]['universe'])}

                        # Check if symbol exists
                        if symbol not in universe:
                            warning(f"Symbol {symbol} not found in Hyperliquid universe")
                            debug(f"Available symbols: {', '.join(universe.keys())}", file_only=True)
                            return None

                        # Get funding data from second element
                        funding_data = data[1]
                        idx = universe[symbol]

                        if idx < len(funding_data):
                            asset_data = funding_data[idx]
                            return {
                                'funding_rate': float(asset_data['funding']),
                                'mark_price': float(asset_data['markPx']),
                                'open_interest': float(asset_data['openInterest'])
                            }

                    warning("Unexpected response format")
                    return None
                error(f"Bad status code: {response.status_code}")
                return None
            except Exception as e:
                error(f"Error getting funding rate for {symbol}: {str(e)}")
                traceback.print_exc()
                return None

    def get_24h_volume(self, symbol):
        """
        Get 24-hour volume for a symbol from Hyperliquid candle data

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTC', 'ETH')

        Returns:
            float: 24h volume or None if unavailable
        """
        if SHARED_HL_AVAILABLE:
            # Use shared service for better API efficiency
            return hl_get_24h_volume(symbol)
        else:
            # Fallback implementation
            try:
                # Get last 24 hours of 1-hour candles
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=24)

                response = requests.post(
                    BASE_URL,
                    headers={'Content-Type': 'application/json'},
                    json={
                        "type": "candleSnapshot",
                        "req": {
                            "coin": symbol,
                            "interval": "1h",
                            "startTime": int(start_time.timestamp() * 1000),
                            "endTime": int(end_time.timestamp() * 1000),
                            "limit": 24
                        }
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    candle_data = response.json()
                    if candle_data and len(candle_data) > 0:
                        # Sum volume from all candles in the period
                        total_volume = sum(float(candle.get('v', 0)) for candle in candle_data)
                        debug(f"✓ {symbol}: 24h volume = {total_volume:,.2f}")
                        return total_volume

                debug(f"No volume data available for {symbol}")
                return None

            except Exception as e:
                debug(f"Failed to get volume for {symbol}: {str(e)}")
                return None

    def collect_oi_data_multi_symbol(self) -> List[Dict]:
        """
        Collect OI data for all tracked symbols from Hyperliquid
        
        Returns:
            List of OI data records
        """
        try:
            info(f"\n🔍 Collecting OI data for {len(TRACKED_SYMBOLS)} symbols...")
            results = []
            current_time = datetime.now()
            
            for symbol in TRACKED_SYMBOLS:
                try:
                    # Get funding rates (includes OI, funding rate, mark price)
                    data = self.get_funding_rates(symbol)

                    if data:
                        # Get 24h volume data from shared service
                        volume_24h = self.get_24h_volume(symbol)

                        record = {
                            'timestamp': current_time,
                            'symbol': symbol,
                            'open_interest': data['open_interest'],
                            'funding_rate': data['funding_rate'],
                            'mark_price': data['mark_price'],
                            'volume_24h': volume_24h,
                            'metadata': {
                                'source': 'hyperliquid',
                                'collected_at': current_time.isoformat(),
                                'api_endpoints': ['metaAndAssetCtxs', 'candleSnapshot'],
                                'volume_period': '24h',
                                'symbol_info': symbol
                            }
                        }
                        results.append(record)
                        debug(f"✓ {symbol}: OI=${data['open_interest']:,.2f}, FR={data['funding_rate']:.6f}, Vol={volume_24h or 0:,.2f}", file_only=True)
                    else:
                        warning(f"No data received for {symbol}")

                    # Small delay to avoid rate limits
                    time.sleep(0.1)

                except Exception as e:
                    error(f"Failed to collect data for {symbol}: {str(e)}")
                    continue
            
            info(f"✅ Collected data for {len(results)}/{len(TRACKED_SYMBOLS)} symbols")
            return results
            
        except Exception as e:
            error(f"Failed to collect OI data: {str(e)}")
            error(traceback.format_exc())
            return []
    
    def generate_ai_insights(self, analytics: List[Dict]) -> List[Dict]:
        """
        Generate AI insights from analytics data

        Args:
            analytics: List of analytics records

        Returns:
            List of insights with AI-generated interpretations
        """
        try:
            if not self.ai_model or not analytics:
                return []

            insights = []

            for record in analytics[:5]:  # Limit to top 5 to save tokens
                try:
                    # Prepare prompt
                    prompt = AI_INSIGHTS_PROMPT.format(
                        symbol=record.get('symbol', 'N/A'),
                        timeframe=record.get('timeframe', 'N/A'),
                        oi_change_pct=f"{record.get('oi_change_pct', 0):.2f}",
                        funding_change_pct=f"{record.get('funding_rate_change_pct', 0):.2f}" if record.get('funding_rate_change_pct') else "N/A",
                        oi_volume_ratio=f"{record.get('oi_volume_ratio', 0):.2f}" if record.get('oi_volume_ratio') else "N/A",
                        liquidity_status=record.get('metadata', {}).get('liquidity_status', 'unknown')
                    )

                    # Get AI analysis using DeepSeek
                    response = self.ai_model.generate_response(
                        system_prompt="You are an expert cryptocurrency analyst. Provide concise, actionable insights about open interest changes.",
                        user_content=prompt,
                        temperature=0.7,
                        max_tokens=150
                    )

                    # Extract insight text
                    insight_text = response if isinstance(response, str) else str(response)

                    insights.append({
                        'symbol': record['symbol'],
                        'timeframe': record['timeframe'],
                        'insight': insight_text,
                        'timestamp': record['timestamp']
                    })

                except Exception as e:
                    error(f"Failed to generate insight for {record.get('symbol')}: {str(e)}")
                    continue

            info(f"🤖 Generated {len(insights)} AI insights with DeepSeek")
            return insights

        except Exception as e:
            error(f"Failed to generate AI insights: {str(e)}")
            return []
        
    def run_monitoring_cycle(self, reporter=None):
        """Run one monitoring cycle - collect data, calculate analytics, and store
        
        Args:
            reporter: Optional AgentReporter for dashboard integration
        """
        try:
            info("\n" + "="*80)
            info(f"📊 OI Monitoring Cycle Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            info("="*80)
            
            # Step 1: Collect raw OI data from Hyperliquid
            oi_data = self.collect_oi_data_multi_symbol()
            
            if not oi_data:
                warning("No OI data collected, skipping cycle")
                return
                
            # Step 2: Save to local Parquet storage
            info("\n💾 Saving to local storage...")
            self.local_storage.save_oi_snapshot(oi_data)
            
            # Step 3: Load historical data for analytics
            info("\n📈 Loading historical data for analytics...")
            history = self.local_storage.load_history(days=LOCAL_RETENTION_DAYS)
            
            if history is None or history.empty:
                info("⚠️ No historical data available yet, skipping analytics")
                # Still save to cloud database
                if self.cloud_storage:
                    self.cloud_storage.save_oi_data(oi_data)
                return
                
            # Step 4: Calculate analytics
            info("\n🔬 Calculating analytics...")
            analytics = self.analytics_engine.calculate_all_metrics(history)
            
            # Prepare symbol data for dashboard
            symbols_data = {}
            if analytics:
                info(f"✅ Calculated {len(analytics)} analytics records")
                
                # Extract 4h changes for each symbol
                for record in analytics:
                    if record['timeframe'] == '4h':
                        symbol = record['symbol']
                        oi_change = record['oi_change_pct']
                        symbols_data[symbol] = f"{oi_change:+.1f}%"
                        
                        # Publish alerts for significant changes via Redis event bus
                        if abs(oi_change) > 15:  # Threshold for alert
                            # Determine severity based on magnitude
                            if abs(oi_change) > 30:
                                severity = AlertSeverity.CRITICAL
                                confidence = min(abs(oi_change) / 100, 0.95)  # Scale confidence
                            elif abs(oi_change) > 20:
                                severity = AlertSeverity.HIGH
                                confidence = min(abs(oi_change) / 80, 0.85)
                            else:
                                severity = AlertSeverity.MEDIUM
                                confidence = min(abs(oi_change) / 60, 0.75)

                            alert = MarketAlert(
                                agent_source="oi_agent",
                                alert_type=AlertType.OI_SIGNIFICANT_CHANGE,
                                symbol=symbol,
                                severity=severity,
                                confidence=confidence,
                                data={
                                    'oi_change_pct': oi_change,
                                    'timeframe': '4h',
                                    'current_oi': record.get('current_oi', 0),
                                    'analytics': self._serialize_for_json(record)
                                },
                                timestamp=datetime.now(),
                                metadata={
                                    'threshold_triggered': 15,
                                    'change_magnitude': abs(oi_change)
                                }
                            )

                            # Publish to event bus
                            self.event_bus.publish('market_alert', alert.to_dict())
                            info(f"🚨 Published OI alert for {symbol}: {oi_change:+.1f}% change")
                
                # Display sample analytics
                if len(analytics) > 0:
                    sample = analytics[0]
                    info(f"\nSample Analytics ({sample['symbol']} - {sample['timeframe']}):")
                    info(f"  OI Change: {sample['oi_change_pct']:.2f}%")
                    if sample.get('funding_rate_change_pct'):
                        info(f"  Funding Rate Change: {sample['funding_rate_change_pct']:.2f}%")
                    if sample.get('oi_volume_ratio'):
                        info(f"  OI/Volume Ratio: {sample['oi_volume_ratio']:.4f}")
            
            # Report cycle completion to dashboard
            if reporter:
                reporter.report_cycle_complete(
                    metrics={'records': len(oi_data), 'analytics': len(analytics)},
                    symbols=symbols_data
                )
            
            # Step 5: Generate AI insights (if enabled)
            insights = []
            if AI_INSIGHTS_ENABLED and self.ai_model:
                info("\n🤖 Generating AI insights...")
                insights = self.generate_ai_insights(analytics)
            
            # Step 6: Save to Supabase cloud database
            if self.cloud_storage:
                info("\n☁️ Saving to cloud database...")
                
                # Save raw OI data
                if self.cloud_storage.save_oi_data(oi_data):
                    info("✅ Saved OI data to cloud")
                else:
                    warning("⚠️ Failed to save OI data to cloud")
                
                # Save analytics
                if analytics:
                    if self.cloud_storage.save_oi_analytics(analytics):
                        info("✅ Saved analytics to cloud")
                    else:
                        warning("⚠️ Failed to save analytics to cloud")
                else:
                    info("ℹ️ No analytics to save to cloud (insufficient historical data)")
            
            # Step 7: Cleanup old local data
            info("\n🧹 Cleaning up old local data...")
            deleted = self.local_storage.cleanup_old_data(retention_days=LOCAL_RETENTION_DAYS)
            if deleted > 0:
                info(f"Removed {deleted} old files")
            
            # Step 8: Display storage stats
            stats = self.local_storage.get_storage_stats()
            info(f"\n📊 Local Storage Stats:")
            info(f"  Files: {stats['file_count']}")
            info(f"  Size: {stats['total_size_mb']} MB")
            info(f"  Date Range: {stats['oldest_date']} to {stats['newest_date']}")
            
            info("\n" + "="*80)
            info(f"✅ OI Monitoring Cycle Completed")
            info("="*80 + "\n")
            
        except Exception as e:
            error(f"❌ Error in monitoring cycle: {str(e)}")
            error(traceback.format_exc())
            info("\n💤 Waiting 1 minute before retry...")
            time.sleep(60)


if __name__ == "__main__":
    info("🚀 Starting OI Agent...")
    info(f"📊 Configuration:")
    info(f"  Check Interval: {CHECK_INTERVAL_HOURS} hours")
    info(f"  Tracked Symbols: {', '.join(TRACKED_SYMBOLS)}")
    info(f"  Local Retention: {LOCAL_RETENTION_DAYS} days")
    info(f"  AI Insights: {'Enabled' if AI_INSIGHTS_ENABLED else 'Disabled'}")
    info("")
    
    agent = OIAgent()
    
    # Run the agent continuously
    info(f"\n🔄 Starting continuous monitoring (every {CHECK_INTERVAL_HOURS}h)...")
    
    while True:
        try:
            agent.run_monitoring_cycle()
            
            # Sleep for the configured interval
            sleep_seconds = 60 * 60 * CHECK_INTERVAL_HOURS
            next_run = datetime.now() + timedelta(seconds=sleep_seconds)
            info(f"\n💤 Sleeping until next cycle at {next_run.strftime('%Y-%m-%d %H:%M:%S')}...")
            time.sleep(sleep_seconds)
            
        except KeyboardInterrupt:
            info("\n👋 OI Agent shutting down gracefully...")
            break
        except Exception as e:
            error(f"❌ Error in main loop: {str(e)}")
            error(traceback.format_exc())
            info("🔧 Retrying in 1 minute...")
            time.sleep(60)
