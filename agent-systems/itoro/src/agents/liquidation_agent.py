"""
🌊 Anarcho Capital's Liquidation Monitor
Built with love by Anarcho Capital 🚀

Luna the Liquidation Agent tracks sudden increases in liquidation volume and provides AI-powered trading signals

Event-driven architecture with real-time WebSocket feeds from multiple exchanges
"""

import os
import sys
import pandas as pd
import time
from datetime import datetime, timedelta
from termcolor import colored, cprint
from dotenv import load_dotenv
from pathlib import Path

# Add project root to Python path for direct script execution
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import nice_funcs as n
from src import nice_funcs_hl as hl
from src.agents.base_agent import BaseAgent
from src.scripts.shared_services.redis_event_bus import get_event_bus
from src.scripts.shared_services.alert_system import MarketAlert, AlertType, AlertSeverity
import traceback
import numpy as np
import re
from src import config

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Import storage and analysis tools
from src.scripts.data_processing.liquidation_storage import LiquidationStorage


class LiquidationAgent(BaseAgent):
    """Luna the Liquidation Monitor 🌊"""
    
    def __init__(self):
        """Initialize Luna the Liquidation Agent"""
        super().__init__('liquidation')
        
        # Load configuration from config.py
        self.check_interval = config.LIQUIDATION_CHECK_INTERVAL
        self.symbols = config.LIQUIDATION_SYMBOLS
        self.threshold = config.LIQUIDATION_THRESHOLD
        self.comparison_window = config.LIQUIDATION_COMPARISON_WINDOW
        self.lookback_bars = config.LIQUIDATION_LOOKBACK_BARS
        self.timeframe = config.LIQUIDATION_TIMEFRAME
        self.exchanges = config.LIQUIDATION_EXCHANGES
        
        # AI Settings
        self.ai_model = config.LIQUIDATION_AI_MODEL
        self.ai_temperature = config.LIQUIDATION_AI_TEMPERATURE
        self.ai_max_tokens = config.LIQUIDATION_AI_MAX_TOKENS
        
        print(f"🤖 Using AI Model: {self.ai_model}")
        print(f"   Temperature: {self.ai_temperature}")
        print(f"   Max Tokens: {self.ai_max_tokens}")
                
        load_dotenv()

        # Initialize DeepSeek AI model via model factory
        try:
            from src.models.model_factory import model_factory
            self.ai_model = model_factory.get_model('deepseek', 'deepseek-chat')
            if self.ai_model and self.ai_model.is_available():
                print("🚀 DeepSeek model initialized via model factory!")
            else:
                raise ValueError("DeepSeek model not available")
        except ImportError as e:
            raise ValueError(f"🚨 Model factory not available: {e}")
        
        # Initialize storage
        self.storage = LiquidationStorage()
        
        # Create data directory if doesn't exist
        self.data_dir = PROJECT_ROOT / "src" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize tracking for previous values
        self.previous_values = {}

        # Initialize Redis event bus for alert publishing
        self.event_bus = get_event_bus()

        print("🌊 Luna the Liquidation Agent initialized!")
        print("🔄 Event bus connected for real-time alert publishing")
        print(f"🎯 Alerting on liquidation increases above +{self.threshold*100:.0f}% from previous")
        print(f"📊 Analyzing symbols: {', '.join(self.symbols)}")
        print(f"🌐 Monitoring exchanges: {', '.join(self.exchanges)}")
        print(f"📈 Using {self.lookback_bars} {self.timeframe} candles for market context")
        print(f"⏱️  Comparison window: {self.comparison_window} minutes")
        
    def _get_current_liquidations(self, symbol: str):
        """
        Get current liquidation data from local storage for a symbol
        
        Args:
            symbol: Symbol to analyze (e.g., 'BTC')
        
        Returns:
            Tuple of (long_liquidations, short_liquidations) or (None, None)
        """
        try:
            print(f"\n🔍 Fetching liquidation data for {symbol}...")
            
            # Load recent data from storage
            hours_to_load = max(1, int(self.comparison_window / 60) + 1)
            history = self.storage.load_history(hours=hours_to_load)
            
            if history is None or history.empty:
                print(f"⚠️ No liquidation history found for {symbol}")
                return None, None
            
            # Filter for the symbol
            symbol_history = history[history['symbol'] == symbol]
            
            if symbol_history.empty:
                print(f"⚠️ No data found for {symbol}")
                return None, None
            
            # Calculate time window
            cutoff_time = datetime.now() - timedelta(minutes=self.comparison_window)
            recent_data = symbol_history[symbol_history['event_time'] >= cutoff_time]
            
            if recent_data.empty:
                print(f"⚠️ No recent data for {symbol} (window: {self.comparison_window}min)")
                return None, None
            
            # Separate long and short liquidations
            long_liquidations = recent_data[recent_data['side'] == 'long']['usd_value'].sum()
            short_liquidations = recent_data[recent_data['side'] == 'short']['usd_value'].sum()
            
            # Get event counts
            long_events = len(recent_data[recent_data['side'] == 'long'])
            short_events = len(recent_data[recent_data['side'] == 'short'])
            
            # Get exchange breakdown
            exchanges_active = recent_data['exchange'].nunique()
            
            # Print summary box
            print("\n" + "╔" + "═" * 70 + "╗")
            print(f"║        🌙 {symbol} Liquidation Data ({self.comparison_window}min)                  ║")
            print("╠" + "═" * 70 + "╣")
            print(f"║  LONGS:  ${long_liquidations:,.2f} ({long_events} events)".ljust(71) + "║")
            print(f"║  SHORTS: ${short_liquidations:,.2f} ({short_events} events)".ljust(71) + "║")
            print(f"║  Total Events: {len(recent_data):<10} Exchanges Active: {exchanges_active}".ljust(71) + "║")
            print("╚" + "═" * 70 + "╝")
            
            return long_liquidations, short_liquidations
            
        except Exception as e:
            print(f"❌ Error getting liquidation data for {symbol}: {str(e)}")
            traceback.print_exc()
            return None, None
            
    def _analyze_opportunity(self, symbol: str, current_longs: float, current_shorts: float, 
                            previous_longs: float, previous_shorts: float):
        """
        Get AI analysis of the liquidation event
        
        Args:
            symbol: Trading symbol
            current_longs: Current long liquidations
            current_shorts: Current short liquidations
            previous_longs: Previous long liquidations
            previous_shorts: Previous short liquidations
        
        Returns:
            Analysis dictionary or None
        """
        try:
            # Calculate percentage changes
            pct_change_longs = ((current_longs - previous_longs) / previous_longs) * 100 if previous_longs > 0 else 0
            pct_change_shorts = ((current_shorts - previous_shorts) / previous_shorts) * 100 if previous_shorts > 0 else 0
            total_pct_change = ((current_longs + current_shorts - previous_longs - previous_shorts) / 
                              (previous_longs + previous_shorts)) * 100 if (previous_longs + previous_shorts) > 0 else 0
            
            # Get market data silently
            market_data = hl.get_data(
                symbol=symbol,
                timeframe=self.timeframe,
                bars=self.lookback_bars,
                add_indicators=True
            )
            
            if market_data is None or market_data.empty:
                print(f"⚠️ Could not fetch market data for {symbol}, proceeding with liquidation analysis only")
                market_data_str = f"No market data available for {symbol}"
            else:
                # Format market data nicely - show last 5 candles
                market_data_str = market_data.tail(5).to_string()
            
            # Prepare the AI prompt
            prompt = f"""
You must respond in exactly 3 lines:
Line 1: Only write BUY, SELL, or NOTHING
Line 2: One short reason why
Line 3: Only write "Confidence: X%" where X is 0-100

Analyze {symbol} market with total {total_pct_change:.2f}% increase in liquidations:

Current Long Liquidations: ${current_longs:,.2f} ({pct_change_longs:+.1f}% change)
Current Short Liquidations: ${current_shorts:,.2f} ({pct_change_shorts:+.1f}% change)
Time Period: Last {self.comparison_window} minutes

Market Data (Last {self.lookback_bars} {self.timeframe} candles):
{market_data_str}

Large long liquidations often indicate potential bottoms (shorts taking profit)
Large short liquidations often indicate potential tops (longs taking profit)
Consider the ratio of long vs short liquidations and their relative changes
"""
            
            print(f"\n🤖 Analyzing {symbol} liquidation spike with DeepSeek AI...")

            # Call DeepSeek API via model factory
            response_text = self.ai_model.generate_response(
                system_prompt="You are a liquidation analyst. You must respond in exactly 3 lines: BUY/SELL/NOTHING, reason, and confidence.",
                user_content=prompt,
                temperature=self.ai_temperature,
                max_tokens=self.ai_max_tokens
            )
            
            # Handle response
            if not response_text:
                print("❌ No response from AI")
                return None
            
            # Parse response
            lines = [line.strip() for line in response_text.split('\n') if line.strip()]
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
            
            return {
                'symbol': symbol,
                'action': action,
                'analysis': analysis,
                'confidence': confidence,
                'pct_change': total_pct_change,
                'pct_change_longs': pct_change_longs,
                'pct_change_shorts': pct_change_shorts,
                'model_used': self.ai_model
            }
            
        except Exception as e:
            print(f"❌ Error in AI analysis for {symbol}: {str(e)}")
            traceback.print_exc()
            return None
            
    def _print_analysis(self, analysis):
        """Print detailed analysis"""
        print("\n" + "╔" + "═" * 60 + "╗")
        print(f"║        🌙 {analysis['symbol']} Liquidation Analysis 💦              ║")
        print("╠" + "═" * 60 + "╣")
        print(f"║  Action: {analysis['action']:<47} ║")
        print(f"║  Confidence: {analysis['confidence']}%{' '*43} ║")
        print(f"║  Reason: {analysis['analysis'][:47]:<47} ║")
        print(f"║  Long Change: {analysis['pct_change_longs']:+.1f}%{' '*38} ║")
        print(f"║  Short Change: {analysis['pct_change_shorts']:+.1f}%{' '*37} ║")
        print("╚" + "═" * 60 + "╝")
            
    def run_monitoring_cycle(self, reporter=None):
        """Run one monitoring cycle across all symbols
        
        Args:
            reporter: Optional AgentReporter for dashboard integration
        """
        try:
            print(f"\n{'='*70}")
            print(f"🌊 Liquidation Monitoring Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*70}")
            
            # Track symbols status for dashboard
            symbols_data = {}
            alert_detected = False
            
            # Check each symbol
            for symbol in self.symbols:
                try:
                    # Get current liquidation data
                    current_longs, current_shorts = self._get_current_liquidations(symbol)
                    
                    if current_longs is None or current_shorts is None:
                        continue
                    
                    # Get previous values for comparison
                    symbol_key = f"{symbol}_{self.comparison_window}m"
                    if symbol_key in self.previous_values:
                        previous_longs = self.previous_values[symbol_key]['longs']
                        previous_shorts = self.previous_values[symbol_key]['shorts']
                        
                        # Only trigger if we have valid previous data
                        if previous_longs > 0 and previous_shorts > 0:
                            # Check if we have a significant increase
                            threshold = 1 + self.threshold
                            if (current_longs > (previous_longs * threshold) or 
                                current_shorts > (previous_shorts * threshold)):
                                
                                print(f"\n🚨 SIGNIFICANT LIQUIDATION SPIKE DETECTED for {symbol}!")
                                alert_detected = True
                                symbols_data[symbol] = "🚨 ALERT"
                                
                                # Calculate percentage changes
                                pct_change_longs = ((current_longs - previous_longs) / previous_longs) * 100
                                pct_change_shorts = ((current_shorts - previous_shorts) / previous_shorts) * 100
                                
                                # Publish alerts via Redis event bus
                                # Determine severity based on magnitude
                                total_change = abs(pct_change_longs) + abs(pct_change_shorts)
                                if total_change > 100:  # Very large spike
                                    severity = AlertSeverity.CRITICAL
                                    confidence = min(total_change / 200, 0.95)
                                elif total_change > 50:  # Significant spike
                                    severity = AlertSeverity.HIGH
                                    confidence = min(total_change / 150, 0.85)
                                else:  # Moderate spike
                                    severity = AlertSeverity.MEDIUM
                                    confidence = min(total_change / 100, 0.75)

                                alert = MarketAlert(
                                    agent_source="liquidation_agent",
                                    alert_type=AlertType.LIQUIDATION_SPIKE,
                                    symbol=symbol,
                                    severity=severity,
                                    confidence=confidence,
                                    data={
                                        'total_liquidations': current_longs + current_shorts,
                                        'long_liquidations': current_longs,
                                        'short_liquidations': current_shorts,
                                        'long_liquidations_pct': pct_change_longs,
                                        'short_liquidations_pct': pct_change_shorts,
                                        'total_change_pct': total_change,
                                        'timeframe_minutes': self.comparison_window,
                                        'threshold_triggered': self.threshold
                                    },
                                    timestamp=datetime.now(),
                                    metadata={
                                        'liquidation_analysis': True,
                                        'market_impact': 'high' if total_change > 75 else 'medium',
                                        'ai_analyzed': True
                                    }
                                )

                                # Publish to event bus
                                self.event_bus.publish('market_alert', alert.to_dict())
                                print(f"🌊 Published liquidation alert for {symbol}: ${current_longs + current_shorts:,.0f} total liquidations")
                                
                                # Get AI analysis
                                analysis = self._analyze_opportunity(
                                    symbol, current_longs, current_shorts,
                                    previous_longs, previous_shorts
                                )
                                
                                if analysis:
                                    self._print_analysis(analysis)
                            else:
                                symbols_data[symbol] = "NORMAL"
                        else:
                            symbols_data[symbol] = "NORMAL"
                    else:
                        symbols_data[symbol] = "NORMAL"
                    
                    # Update previous values
                    self.previous_values[symbol_key] = {
                        'longs': current_longs,
                        'shorts': current_shorts,
                        'timestamp': datetime.now()
                    }
                    
                except Exception as e:
                    print(f"❌ Error processing {symbol}: {str(e)}")
                    symbols_data[symbol] = "ERROR"
                    continue
            
            # Report cycle completion to dashboard
            if reporter:
                reporter.report_cycle_complete(
                    metrics={'symbols_checked': len(self.symbols), 'alerts': alert_detected},
                    symbols=symbols_data
                )
                
        except Exception as e:
            print(f"❌ Error in monitoring cycle: {str(e)}")
            if reporter:
                reporter.report_error(f"Cycle error: {str(e)}", e)
            traceback.print_exc()

    def run(self):
        """Run the liquidation monitor continuously"""
        print("\n🌊 Starting liquidation monitoring...")
        print(f"💡 Note: The liquidation_collector.py script should be running to collect data")
        print(f"⏱️  Check interval: {self.check_interval} seconds")
        
        while True:
            try:
                self.run_monitoring_cycle()
                print(f"\n💤 Sleeping for {self.check_interval} seconds...")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n👋 Luna the Liquidation Agent shutting down gracefully...")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {str(e)}")
                time.sleep(60)  # Sleep for a minute before retrying


if __name__ == "__main__":
    agent = LiquidationAgent()
    agent.run()
