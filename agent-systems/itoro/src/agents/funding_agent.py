"""
💰 Moon Dev's Funding Rate Monitor
Built with love by Moon Dev 🚀

Fran the Funding Agent tracks funding rate changes across different timeframes.

Need an API key? for a limited time, bootcamp members get free api keys for claude, openai, helius, birdeye & quant elite gets access to the moon dev api. join here: https://algotradecamp.com
"""

import os
import pandas as pd
import time
from datetime import datetime, timedelta
from termcolor import colored, cprint
from dotenv import load_dotenv
import openai
from pathlib import Path
import traceback
import numpy as np
import re

# Add project root to Python path for direct script execution
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import nice_funcs_hl as hl
from src.agents.base_agent import BaseAgent

# Import configuration
from src import config

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load configuration from config.py
CHECK_INTERVAL_MINUTES = config.FUNDING_CHECK_INTERVAL_MINUTES
MID_NEGATIVE_THRESHOLD = config.FUNDING_MID_NEGATIVE_THRESHOLD
MID_POSITIVE_THRESHOLD = config.FUNDING_MID_POSITIVE_THRESHOLD
NEGATIVE_THRESHOLD = config.FUNDING_NEGATIVE_THRESHOLD
POSITIVE_THRESHOLD = config.FUNDING_POSITIVE_THRESHOLD

# OHLCV Data Settings
TIMEFRAME = config.FUNDING_TIMEFRAME
LOOKBACK_BARS = config.FUNDING_LOOKBACK_BARS

# Symbol to name mapping
SYMBOL_NAMES = config.FUNDING_SYMBOL_NAMES

# AI Settings
MODEL_OVERRIDE = config.FUNDING_MODEL_OVERRIDE
DEEPSEEK_BASE_URL = config.FUNDING_DEEPSEEK_BASE_URL
AI_TEMPERATURE = config.FUNDING_AI_TEMPERATURE
AI_MAX_TOKENS = config.FUNDING_AI_MAX_TOKENS

# AI Analysis Prompt
FUNDING_ANALYSIS_PROMPT = """You must respond in exactly 3 lines:
Line 1: Only write BUY, SELL, or NOTHING
Line 2: One short reason why
Line 3: Only write "Confidence: X%" where X is 0-100

Analyze {symbol} with {rate}% funding rate:

Below is Bitcoin (BTC) market data which shows overall market direction:
{market_data}

Above is Bitcoin's market data which indicates overall market direction.
Below is the funding rate data for {symbol}:
{funding_data}

Remember:
- Super negative funding rates in a trending up market may signal a good buy (shorts getting squeezed)
- Super high funding rates in a downtrend may signal a good sell (longs getting liquidated)
- Use BTC's trend to gauge overall market direction
"""

class FundingAgent(BaseAgent):
    """Fran the Funding Rate Monitor 💰"""
    
    def __init__(self):
        """Initialize Fran the Funding Agent"""
        super().__init__('funding')
        
        # Set active model - DeepSeek only
        self.active_model = MODEL_OVERRIDE
        
        load_dotenv()
        
        # Initialize DeepSeek client
        deepseek_key = os.getenv("DEEPSEEK_KEY")
        if not deepseek_key:
            raise ValueError("🚨 DEEPSEEK_KEY not found in environment variables!")
        
        self.deepseek_client = openai.OpenAI(
            api_key=deepseek_key,
            base_url=DEEPSEEK_BASE_URL
        )
        cprint("🚀 Funding Agent initialized with DeepSeek!", "green")
        
        # Create data directories if they don't exist
        self.data_dir = PROJECT_ROOT / "src" / "data" / "funding"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize storage manager (will be created)
        from src.scripts.data_processing.funding_storage import FundingStorage
        self.storage = FundingStorage()
        
        # Initialize cloud database if available
        try:
            from src.scripts.database.cloud_database import get_cloud_database_manager
            self.cloud_db = get_cloud_database_manager()
            if self.cloud_db:
                print("✅ Cloud database connected")
            else:
                print("⚠️ Cloud database not available")
                self.cloud_db = None
        except ImportError:
            print("⚠️ Cloud database not available")
            self.cloud_db = None
        
        # AI analysis cache
        self.ai_cache = {}
        self.cache_timeout = 1800  # 30 minutes
        
        print("💰 Funding Agent initialized!")
        print(f"🎯 Mid-range alerts: below {MID_NEGATIVE_THRESHOLD}% or above {MID_POSITIVE_THRESHOLD}%")
        print(f"🚨 Extreme alerts (AI): below {NEGATIVE_THRESHOLD}% or above {POSITIVE_THRESHOLD}%")
        print(f"📊 Monitoring {len(SYMBOL_NAMES)} symbols every {CHECK_INTERVAL_MINUTES} minutes")
        
    def _analyze_opportunity(self, symbol, funding_data, market_data):
        """Get AI analysis of the opportunity"""
        try:
            # Debug print raw funding rate
            rate = funding_data['annual_rate'].iloc[0]
            print(f"\n🔍 Raw funding rate for {symbol}: {rate:.2f}%")
            
            # Get BTC market data as market barometer
            btc_data = hl.get_data(
                symbol="BTC",
                timeframe=TIMEFRAME,
                bars=LOOKBACK_BARS,
                add_indicators=True
            )
            
            # Get symbol specific data if not BTC
            symbol_data = None
            if symbol != "BTC":
                symbol_data = hl.get_data(
                    symbol=symbol,
                    timeframe=TIMEFRAME,
                    bars=LOOKBACK_BARS,
                    add_indicators=True
                )
            
            # Format market data context
            market_context = f"BTC Market Data (Last 5 candles):\n{btc_data.tail(5).to_string()}\n\n"
            if symbol_data is not None and symbol != "BTC":
                market_context += f"{symbol} Technical Data (Last 5 candles):\n{symbol_data.tail(5).to_string()}\n\n"
            
            # Add some basic trend analysis
            btc_close = btc_data['close'].iloc[-1]
            btc_sma = btc_data['close'].rolling(20).mean().iloc[-1]
            btc_trend = "UPTREND" if btc_close > btc_sma else "DOWNTREND"
            market_context += f"\nBTC Trend Analysis:\n- Current Price vs 20 SMA: {btc_trend}\n"
            
            # Prepare the context
            rate = funding_data['annual_rate'].iloc[0]
            context = FUNDING_ANALYSIS_PROMPT.format(
                symbol=symbol,
                rate=f"{rate:.2f}",
                market_data=market_context,
                funding_data=funding_data.to_string()
            )
            
            print(f"\n🤖 Analyzing {symbol} with AI...")
            
            # Check cache first
            cache_key = f"{symbol}_{rate:.2f}"
            if cache_key in self.ai_cache:
                cache_time, cached_result = self.ai_cache[cache_key]
                if time.time() - cache_time < self.cache_timeout:
                    print(f"✅ Using cached AI analysis for {symbol}")
                    return cached_result
            
            # Use DeepSeek for AI analysis
            cprint(f"🤖 Using DeepSeek model: {self.active_model}", "cyan")
            response = self.deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": FUNDING_ANALYSIS_PROMPT},
                    {"role": "user", "content": context}
                ],
                max_tokens=AI_MAX_TOKENS,
                temperature=AI_TEMPERATURE,
                stream=False
            )
            content = response.choices[0].message.content.strip()
            
            # Debug: Print raw response
            print("\n🔍 Raw response:")
            print(repr(content))
            
            # Clean up any remaining formatting
            content = content.replace('\\n', '\n')
            content = content.strip('[]')
            
            # Split into lines and clean each line
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            if not lines:
                print("❌ Empty response from AI")
                return None
            
            # First line should be the action
            action = lines[0].strip().upper()
            if action not in ['BUY', 'SELL', 'NOTHING']:
                print(f"⚠️ Invalid action: {action}")
                return None
            
            # Rest is analysis
            analysis = lines[1] if len(lines) > 1 else ""
            
            # Extract confidence from third line
            confidence = 50  # Default confidence
            if len(lines) > 2:
                try:
                    matches = re.findall(r'(\d+)%', lines[2])
                    if matches:
                        confidence = int(matches[0])
                except:
                    print("⚠️ Could not parse confidence, using default")
            
            result = {
                'action': action,
                'analysis': analysis,
                'confidence': confidence
            }
            
            # Cache the result
            self.ai_cache[cache_key] = (time.time(), result)
            
            return result
            
        except Exception as e:
            print(f"❌ Error in AI analysis: {str(e)}")
            traceback.print_exc()
            return None
            
    def _detect_significant_changes(self, current_data):
        """Detect significant funding rates (mid-range and extreme)"""
        try:
            opportunities = {
                'extreme': {},  # Rates requiring AI analysis
                'mid_range': {},  # Rates for logging/alerting only
                'normal': {}  # Normal rates for data collection
            }
            
            for _, row in current_data.iterrows():
                try:
                    annual_rate = float(row['annual_rate'])
                    symbol = str(row['symbol'])
                    
                    # Classify rate severity
                    if annual_rate < NEGATIVE_THRESHOLD or annual_rate > POSITIVE_THRESHOLD:
                        # EXTREME - Run AI analysis
                        market_data = hl.get_data(
                            symbol=symbol,
                            timeframe=TIMEFRAME,
                            bars=LOOKBACK_BARS,
                            add_indicators=True
                        )
                        
                        if not market_data.empty:
                            analysis = self._analyze_opportunity(
                                symbol=symbol,
                                funding_data=row.to_frame().T,
                                market_data=market_data
                            )
                            
                            if analysis:
                                opportunities['extreme'][symbol] = {
                                    'annual_rate': annual_rate,
                                    'action': analysis['action'],
                                    'analysis': analysis['analysis'],
                                    'confidence': analysis['confidence'],
                                    'alert_level': 'EXTREME'
                                }
                    
                    elif annual_rate < MID_NEGATIVE_THRESHOLD or annual_rate > MID_POSITIVE_THRESHOLD:
                        # MID-RANGE - Log only, no AI
                        opportunities['mid_range'][symbol] = {
                            'annual_rate': annual_rate,
                            'alert_level': 'MID_RANGE'
                        }
                    else:
                        # NORMAL - Data collection only
                        opportunities['normal'][symbol] = {
                            'annual_rate': annual_rate,
                            'alert_level': 'NORMAL'
                        }
                            
                except Exception as e:
                    print(f"Error processing {symbol}: {str(e)}")
                    continue
            
            return opportunities
            
        except Exception as e:
            print(f"Error detecting changes: {str(e)}")
            return None

    def _format_alert_messages(self, opportunities):
        """Format funding rate alerts into log messages"""
        try:
            messages = []
            
            # Format extreme alerts (with AI analysis)
            if opportunities and 'extreme' in opportunities:
                for symbol, data in opportunities['extreme'].items():
                    token_name = SYMBOL_NAMES.get(symbol, symbol)
                    rate = data['annual_rate']
                    action = data['action']
                    confidence = data['confidence']
                    analysis = data['analysis'].split('\n')[0] if data.get('analysis') else 'No analysis'
                    
                    if rate < NEGATIVE_THRESHOLD:
                        messages.append(
                            f"🚨 EXTREME: {token_name} negative funding at {rate:.2f}% annual. "
                            f"AI suggests {action} (confidence: {confidence}%). {analysis}"
                        )
                    elif rate > POSITIVE_THRESHOLD:
                        messages.append(
                            f"🚨 EXTREME: {token_name} high funding at {rate:.2f}% annual. "
                            f"AI suggests {action} (confidence: {confidence}%). {analysis}"
                        )
            
            # Format mid-range alerts (no AI analysis)
            if opportunities and 'mid_range' in opportunities:
                for symbol, data in opportunities['mid_range'].items():
                    token_name = SYMBOL_NAMES.get(symbol, symbol)
                    rate = data['annual_rate']
                    
                    if rate < MID_NEGATIVE_THRESHOLD:
                        messages.append(
                            f"⚠️ MID-RANGE: {token_name} at {rate:.2f}% annual (moderately negative)"
                        )
                    elif rate > MID_POSITIVE_THRESHOLD:
                        messages.append(
                            f"⚠️ MID-RANGE: {token_name} at {rate:.2f}% annual (moderately high)"
                        )
            
            return messages
            
        except Exception as e:
            print(f"❌ Error formatting alerts: {str(e)}")
            return []
            
    def _log_alert(self, message):
        """Log alert message (no voice announcements)"""
        if not message:
            return
            
        print(f"\n📢 ALERT: {message}")

    def load_history(self, days=None):
        """Load historical funding rate data from Parquet storage"""
        try:
            if days is None:
                days = config.FUNDING_LOCAL_RETENTION_DAYS
            print(f"📝 Loading {days} days of funding history...")
            self.funding_history = self.storage.load_history(days=days)
            
            if self.funding_history is not None and not self.funding_history.empty:
                print(f"✅ Loaded {len(self.funding_history)} historical records")
            else:
                print("📝 No historical data available yet")
                self.funding_history = pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Error loading history: {str(e)}")
            traceback.print_exc()
            self.funding_history = pd.DataFrame()
    
    def calculate_analytics(self, current_data, history):
        """Calculate funding rate analytics for rate changes and trends"""
        try:
            if history is None or history.empty:
                print("⚠️ No historical data for analytics")
                return []
            
            analytics = []
            current_time = datetime.now()
            
            # Define lookback periods
            periods = {
                '4h': timedelta(hours=4),
                '24h': timedelta(hours=24),
                '7d': timedelta(days=7)
            }
            
            for _, current_row in current_data.iterrows():
                symbol = current_row['symbol']
                current_rate = current_row['annual_rate']
                
                # Get historical data for this symbol
                symbol_history = history[history['symbol'] == symbol].copy()
                
                if symbol_history.empty:
                    continue
                
                # Ensure event_time is datetime
                symbol_history['event_time'] = pd.to_datetime(symbol_history['event_time'])
                symbol_history = symbol_history.sort_values('event_time')
                
                # Calculate rate changes for each period
                for timeframe, delta in periods.items():
                    cutoff_time = current_time - delta
                    period_data = symbol_history[symbol_history['event_time'] >= cutoff_time]
                    
                    if len(period_data) > 0:
                        # Get oldest rate in period
                        oldest_rate = period_data.iloc[0]['annual_rate']
                        
                        # Calculate change
                        if oldest_rate != 0:
                            rate_change_pct = ((current_rate - oldest_rate) / abs(oldest_rate)) * 100
                        else:
                            rate_change_pct = 0
                        
                        # Determine trend
                        if rate_change_pct > 10:
                            trend = "INCREASING"
                        elif rate_change_pct < -10:
                            trend = "DECREASING"
                        else:
                            trend = "STABLE"
                        
                        # Determine alert level
                        if current_rate < NEGATIVE_THRESHOLD or current_rate > POSITIVE_THRESHOLD:
                            alert_level = "EXTREME"
                        elif current_rate < MID_NEGATIVE_THRESHOLD or current_rate > MID_POSITIVE_THRESHOLD:
                            alert_level = "MID_RANGE"
                        else:
                            alert_level = "NORMAL"
                        
                        # Calculate volatility (std dev of rates in period)
                        volatility = period_data['annual_rate'].std() if len(period_data) > 1 else 0
                        
                        analytics.append({
                            'timestamp': current_time,
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'current_rate': current_rate,
                            'rate_change_pct': rate_change_pct,
                            'trend': trend,
                            'alert_level': alert_level,
                            'volatility': volatility,
                            'metadata': {
                                'oldest_rate': oldest_rate,
                                'data_points': len(period_data)
                            }
                        })
            
            print(f"📊 Calculated {len(analytics)} analytics records")
            return analytics
            
        except Exception as e:
            print(f"❌ Error calculating analytics: {str(e)}")
            traceback.print_exc()
            return []
    
    def detect_arbitrage_opportunities(self, current_data):
        """Detect potential arbitrage opportunities from rate discrepancies"""
        try:
            if current_data is None or len(current_data) < 2:
                return []
            
            opportunities = []
            
            # Find pairs with significant rate differences
            for i, row1 in current_data.iterrows():
                for j, row2 in current_data.iterrows():
                    if i >= j:
                        continue
                    
                    symbol1 = row1['symbol']
                    symbol2 = row2['symbol']
                    rate1 = row1['annual_rate']
                    rate2 = row2['annual_rate']
                    
                    # Calculate rate difference
                    rate_diff = abs(rate1 - rate2)
                    
                    # Flag if difference is significant (>5%)
                    if rate_diff > 5.0:
                        opportunities.append({
                            'symbol_pair': f"{symbol1}/{symbol2}",
                            'rate_diff': rate_diff,
                            'symbol1': symbol1,
                            'rate1': rate1,
                            'symbol2': symbol2,
                            'rate2': rate2,
                            'timestamp': datetime.now()
                        })
            
            if opportunities:
                # Sort by rate difference
                opportunities.sort(key=lambda x: x['rate_diff'], reverse=True)
                print(f"💹 Found {len(opportunities)} potential arbitrage opportunities")
            
            return opportunities
            
        except Exception as e:
            print(f"❌ Error detecting arbitrage: {str(e)}")
            return []
            
    def _get_current_funding_with_retry(self, symbol, max_retries=3):
        """Get funding rate for a symbol with retry logic"""
        for attempt in range(max_retries):
            try:
                data = hl.get_funding_rates(symbol)
                if data:
                    return data
                else:
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))  # Exponential backoff
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ {symbol} attempt {attempt + 1} failed: {str(e)}, retrying...")
                    time.sleep(0.5 * (attempt + 1))
                else:
                    raise
        return None
    
    def _get_current_funding(self):
        """Get current funding rates from Hyperliquid API with error handling"""
        try:
            print(f"\n🔍 Collecting funding rates for {len(SYMBOL_NAMES)} symbols...")
            results = []
            current_time = datetime.now()
            success_count = 0
            fail_count = 0
            
            for symbol in SYMBOL_NAMES.keys():
                try:
                    # Get funding rate with retry logic
                    data = self._get_current_funding_with_retry(symbol, max_retries=3)
                    
                    if data:
                        # Calculate annual rate: funding_rate * 3 funding periods per day * 365 days * 100 for percentage
                        annual_rate = data['funding_rate'] * 3 * 365 * 100
                        
                        record = {
                            'symbol': symbol,
                            'funding_rate': data['funding_rate'],
                            'annual_rate': annual_rate,
                            'mark_price': data['mark_price'],
                            'open_interest': data['open_interest'],
                            'event_time': current_time
                        }
                        results.append(record)
                        success_count += 1
                        print(f"✓ {symbol}: FR={data['funding_rate']:.6f}, Annual={annual_rate:.2f}%")
                    else:
                        fail_count += 1
                        print(f"✗ {symbol}: No data received after retries")
                    
                    # Rate limiting between requests
                    time.sleep(0.1)
                    
                except Exception as e:
                    fail_count += 1
                    print(f"✗ {symbol}: {str(e)}")
                    continue
            
            # Circuit breaker: fail if >50% symbols failed
            if fail_count > len(SYMBOL_NAMES) / 2:
                print(f"❌ Circuit breaker triggered: {fail_count}/{len(SYMBOL_NAMES)} symbols failed")
                print(f"⚠️ System requires >50% success rate to continue")
                return None
            
            print(f"\n✅ Collected data for {success_count}/{len(SYMBOL_NAMES)} symbols ({fail_count} failed)")
            
            if results:
                return pd.DataFrame(results)
            return None
            
        except Exception as e:
            print(f"❌ Critical error getting funding data: {str(e)}")
            traceback.print_exc()
            return None

    def _save_to_history(self, current_data):
        """Save current funding data to Parquet storage"""
        try:
            if current_data is not None and not current_data.empty:
                # Convert DataFrame to list of dicts for storage
                records = current_data.to_dict('records')
                
                # Save to local Parquet storage
                success = self.storage.save_funding_snapshot(records)
                
                if success:
                    print(f"💾 Saved {len(records)} funding records to local storage")
                else:
                    print("⚠️ Failed to save to local storage")
                
                # Save to cloud database if available
                if self.cloud_db:
                    try:
                        cloud_success = self.cloud_db.save_funding_data(records)
                        if cloud_success:
                            print(f"☁️ Saved {len(records)} funding records to cloud")
                        else:
                            print("⚠️ Failed to save to cloud database")
                    except Exception as e:
                        print(f"⚠️ Cloud save error: {str(e)}")
                
        except Exception as e:
            print(f"❌ Error saving to history: {str(e)}")
            traceback.print_exc()

    def run_monitoring_cycle(self, reporter=None):
        """Run one monitoring cycle - collect, save, analyze, and alert
        
        Args:
            reporter: Optional AgentReporter for dashboard integration
        """
        try:
            print("\n" + "="*80)
            print(f"💰 Funding Rate Monitoring Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)
            
            # Step 1: Collect funding rates from Hyperliquid
            current_data = self._get_current_funding()
            
            if current_data is None or current_data.empty:
                print("❌ No funding data collected, skipping cycle")
                return
            
            # Step 2: Save to local and cloud storage
            print("\n💾 Saving funding data...")
            self._save_to_history(current_data)
            
            # Step 3: Load historical data for analytics
            print("\n📈 Loading historical data...")
            self.load_history(days=7)  # Load 7 days for analytics
            
            # Step 4: Calculate analytics
            analytics = []
            if not self.funding_history.empty:
                print("\n🔬 Calculating analytics...")
                analytics = self.calculate_analytics(current_data, self.funding_history)
                
                # Save analytics to cloud if available
                if analytics and self.cloud_db:
                    try:
                        self.cloud_db.save_funding_analytics(analytics)
                    except Exception as e:
                        print(f"⚠️ Failed to save analytics to cloud: {str(e)}")
            
            # Step 5: Detect arbitrage opportunities
            arb_opportunities = self.detect_arbitrage_opportunities(current_data)
            if arb_opportunities:
                print(f"\n💹 Top arbitrage opportunities:")
                for opp in arb_opportunities[:3]:  # Show top 3
                    print(f"   {opp['symbol_pair']}: {opp['rate_diff']:.2f}% difference")
            
            # Step 6: Detect significant changes
            print("\n🔍 Analyzing funding rates...")
            opportunities = self._detect_significant_changes(current_data)
            
            # Step 4: Format and log alerts
            if opportunities:
                messages = self._format_alert_messages(opportunities)
                for msg in messages:
                    self._log_alert(msg)
                
                # Count alert types
                extreme_count = len(opportunities.get('extreme', {}))
                mid_count = len(opportunities.get('mid_range', {}))
                normal_count = len(opportunities.get('normal', {}))
                
                print(f"\n📊 Alert Summary: {extreme_count} extreme, {mid_count} mid-range, {normal_count} normal")
            
            # Step 5: Display funding rate table and prepare dashboard data
            symbols_data = {}
            
            print("\n" + "╔" + "═" * 70 + "╗")
            print("║" + " "*20 + "💰 Funding Rates Dashboard" + " "*24 + "║")
            print("╠" + "═" * 70 + "╣")
            print("║  Symbol    │  Annual Rate  │  Alert Level  │  Status         ║")
            print("╟" + "─" * 70 + "╢")
            
            for _, row in current_data.iterrows():
                annual_rate = row['annual_rate']
                symbol = row['symbol']
                
                # Determine alert level
                if annual_rate < NEGATIVE_THRESHOLD or annual_rate > POSITIVE_THRESHOLD:
                    alert_level = "EXTREME 🚨"
                    status = "AI Analyzed"
                    # Report extreme alerts to dashboard
                    if reporter:
                        reporter.report_alert(
                            f"{symbol} funding rate: {annual_rate:.2f}% (EXTREME)",
                            level='ALERT',
                            alert_data={'symbol': symbol, 'rate': annual_rate}
                        )
                elif annual_rate < MID_NEGATIVE_THRESHOLD or annual_rate > MID_POSITIVE_THRESHOLD:
                    alert_level = "MID-RANGE⚠️"
                    status = "Monitoring"
                else:
                    alert_level = "NORMAL ✓"
                    status = "Collecting"
                
                # Add to symbols data for dashboard (only show key symbols)
                if symbol in ['BTC', 'ETH', 'SOL']:
                    symbols_data[symbol] = f"{annual_rate:.2f}%"
                
                print(f"║  {symbol:<8} │  {annual_rate:>8.2f}%  │  {alert_level:<12} │  {status:<14} ║")
            
            print("╚" + "═" * 70 + "╝")
            
            # Report cycle completion to dashboard
            if reporter:
                reporter.report_cycle_complete(
                    metrics={'symbols_count': len(current_data)},
                    symbols=symbols_data
                )
            
            print(f"\n✅ Monitoring cycle completed successfully")
            
        except Exception as e:
            print(f"❌ Error in monitoring cycle: {str(e)}")
            traceback.print_exc()

    def run(self):
        """Run the funding rate monitor continuously with error recovery"""
        print("\n🚀 Starting funding rate monitoring...")
        print(f"📊 Monitoring {len(SYMBOL_NAMES)} symbols every {CHECK_INTERVAL_MINUTES} minutes")
        
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while True:
            try:
                self.run_monitoring_cycle()
                
                # Reset failure counter on success
                consecutive_failures = 0
                
                # Cleanup old files periodically (every 10 cycles)
                if hasattr(self, 'cycle_count'):
                    self.cycle_count += 1
                    if self.cycle_count % 10 == 0:
                        print("\n🧹 Running cleanup...")
                        deleted = self.storage.cleanup_old_files(retention_days=config.FUNDING_LOCAL_RETENTION_DAYS)
                        if deleted > 0:
                            print(f"   Cleaned up {deleted} old files")
                else:
                    self.cycle_count = 1
                
                print(f"\n💤 Sleeping for {CHECK_INTERVAL_MINUTES} minutes...")
                time.sleep(CHECK_INTERVAL_MINUTES * 60)
                
            except KeyboardInterrupt:
                print("\n👋 Funding Agent shutting down gracefully...")
                print(f"📊 Total cycles completed: {getattr(self, 'cycle_count', 0)}")
                break
            except Exception as e:
                consecutive_failures += 1
                print(f"\n❌ Error in main loop (failure {consecutive_failures}/{max_consecutive_failures}): {str(e)}")
                traceback.print_exc()
                
                # Circuit breaker for persistent failures
                if consecutive_failures >= max_consecutive_failures:
                    print(f"\n🚨 CRITICAL: {max_consecutive_failures} consecutive failures detected")
                    print("⚠️ Funding Agent shutting down for safety")
                    break
                
                # Exponential backoff for retries
                retry_delay = min(60 * consecutive_failures, 300)  # Max 5 minutes
                print(f"⏳ Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)

if __name__ == "__main__":
    agent = FundingAgent()
    agent.run()
