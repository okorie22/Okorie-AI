"""
🌙 Moon Dev's Strategy Agent
Handles all strategy-based trading decisions
"""

from src.config import *
import json
from termcolor import cprint
import os
from datetime import datetime
from typing import Dict, Any
from src.scripts.shared_services.redis_event_bus import get_event_bus
from src.scripts.shared_services.alert_system import MarketAlert, AlertType, get_alert_manager
from src.strategies.templates.strategy_manager import StrategyTemplateManager
import importlib
import inspect
import time

# Import exchange manager for unified trading
try:
    from src.exchange_manager import ExchangeManager
    USE_EXCHANGE_MANAGER = True
except ImportError:
    from src import nice_funcs as n
    USE_EXCHANGE_MANAGER = False

# 🎯 Strategy Evaluation Prompt
STRATEGY_EVAL_PROMPT = """
You are Moon Dev's Strategy Validation Assistant 🌙

Analyze the following strategy signals and validate their recommendations:

Strategy Signals:
{strategy_signals}

Market Context:
{market_data}

Your task:
1. Evaluate each strategy signal's reasoning
2. Check if signals align with current market conditions
3. Look for confirmation/contradiction between different strategies
4. Consider risk factors

Respond in this format:
1. First line: EXECUTE or REJECT for each signal (e.g., "EXECUTE signal_1, REJECT signal_2")
2. Then explain your reasoning:
   - Signal analysis
   - Market alignment
   - Risk assessment
   - Confidence in each decision (0-100%)

Remember:
- Moon Dev prioritizes risk management! 🛡️
- Multiple confirming signals increase confidence
- Contradicting signals require deeper analysis
- Better to reject a signal than risk a bad trade
"""

class StrategyAgent:
    def __init__(self):
        """Initialize the Strategy Agent"""
        self.enabled_strategies = []
        self.pending_alerts = []
        self.processed_signals = []

        # Initialize DeepSeek AI model
        try:
            from src.models.model_factory import model_factory
            self.ai_model = model_factory.get_model('deepseek', 'deepseek-chat')
            if self.ai_model and self.ai_model.is_available():
                cprint("✅ Strategy Agent initialized with DeepSeek AI", "green")
            else:
                cprint("⚠️ DeepSeek model not available for Strategy Agent", "yellow")
                self.ai_model = None
        except ImportError as e:
            cprint(f"⚠️ Model factory not available: {e}", "yellow")
            self.ai_model = None

        # Initialize Redis event bus
        self.event_bus = get_event_bus()
        self.alert_manager = get_alert_manager()
        self.strategy_manager = StrategyTemplateManager()

        # Subscribe to market alerts
        self.event_bus.subscribe('market_alert', self.handle_market_alert)

        cprint("🔄 Strategy Agent connected to event bus for real-time alert processing", "cyan")
        cprint(f"🎯 Loaded {len(self.strategy_manager.templates)} strategy templates", "cyan")

        # Initialize exchange manager if available
        if USE_EXCHANGE_MANAGER:
            self.em = ExchangeManager()
            cprint(f"✅ Strategy Agent using ExchangeManager for {EXCHANGE}", "green")
        else:
            self.em = None
            cprint("✅ Strategy Agent using direct nice_funcs", "green")
        
        if ENABLE_STRATEGIES:
            try:
                # Import strategies directly
                from src.strategies.custom.example_strategy import ExampleStrategy
                from src.strategies.custom.private_my_strategy import MyStrategy
                
                # Initialize strategies
                self.enabled_strategies.extend([
                    ExampleStrategy(),
                    MyStrategy()
                ])
                
                print(f"✅ Loaded {len(self.enabled_strategies)} strategies!")
                for strategy in self.enabled_strategies:
                    print(f"  • {strategy.name}")
                    
            except Exception as e:
                print(f"⚠️ Error loading strategies: {e}")
        else:
            print("🤖 Strategy Agent is disabled in config.py")
        
        print(f"🤖 Moon Dev's Strategy Agent initialized with {len(self.enabled_strategies)} strategies!")

    def handle_market_alert(self, alert_data: dict):
        """
        Handle incoming market alerts from the event bus

        Args:
            alert_data: Alert data from Redis event bus
        """
        try:
            # Convert dict to MarketAlert object
            alert = MarketAlert.from_dict(alert_data)

            cprint(f"📡 Strategy Agent received alert: {alert.get_description()}", "cyan")

            # Add to alert manager
            if self.alert_manager.add_alert(alert):
                cprint(f"✅ Alert processed and stored for {alert.symbol}", "green")
            else:
                cprint(f"ℹ️ Alert for {alert.symbol} already exists or lower priority", "blue")

            # Add to pending alerts for processing
            self.pending_alerts.append(alert)

            # Process alerts that should trigger strategies
            if alert.should_trigger_strategy():
                cprint(f"🎯 High-priority alert detected, processing immediately", "yellow")
                self.process_alerts()

        except Exception as e:
            cprint(f"❌ Error processing market alert: {e}", "red")

    def process_alerts(self):
        """Process pending alerts and generate strategy signals"""
        if not self.pending_alerts:
            return

        try:
            cprint(f"🔄 Processing {len(self.pending_alerts)} pending alerts...", "cyan")

            # Group alerts by symbol
            alerts_by_symbol = {}
            for alert in self.pending_alerts:
                if alert.symbol not in alerts_by_symbol:
                    alerts_by_symbol[alert.symbol] = []
                alerts_by_symbol[alert.symbol].append(alert)

            # Process each symbol's alerts
            for symbol, alerts in alerts_by_symbol.items():
                cprint(f"📊 Processing {len(alerts)} alerts for {symbol}", "cyan")

                # Generate strategy signals for this symbol
                signals = self.generate_strategy_signals(symbol, alerts)

                if signals:
                    # Evaluate and filter signals with AI
                    approved_signals = self.evaluate_strategy_signals(signals, symbol)

                    if approved_signals:
                        # Execute approved signals
                        self.execute_strategy_signals(approved_signals)

                        # Publish to trading agent
                        self.publish_trading_signals(approved_signals, symbol)

            # Clear processed alerts
            self.pending_alerts.clear()

        except Exception as e:
            cprint(f"❌ Error processing alerts: {e}", "red")

    def generate_strategy_signals(self, symbol: str, alerts: list) -> list:
        """
        Generate strategy signals based on alerts for a symbol using strategy templates

        Args:
            symbol: Trading symbol
            alerts: List of MarketAlert objects for this symbol

        Returns:
            List of strategy signals
        """
        signals = []

        try:
            # Get market context for signal generation
            market_context = self._get_market_context(symbol)

            for alert in alerts:
                # Use strategy templates to generate signals
                template_signals = self.strategy_manager.generate_signals(alert, market_context)

                for signal in template_signals:
                    # Add symbol and alert info to signal
                    signal['symbol'] = symbol
                    signal['alert_type'] = alert.alert_type.value
                    signal['alert_severity'] = alert.severity.value
                    signals.append(signal)

            cprint(f"🎯 Generated {len(signals)} strategy signals for {symbol} using templates", "green")

        except Exception as e:
            cprint(f"❌ Error generating strategy signals for {symbol}: {e}", "red")

        return signals

    def _get_market_context(self, symbol: str) -> Dict[str, Any]:
        """
        Get market context data for signal generation

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with market context information
        """
        try:
            # Try to get basic market data
            from src.data.ohlcv_collector import collect_token_data
            market_data = collect_token_data(symbol)

            if market_data and 'price_data' in market_data:
                # Extract basic trend and volatility info
                price_data = market_data['price_data']
                if len(price_data) > 20:
                    recent_prices = price_data.tail(20)
                    current_price = recent_prices['close'].iloc[-1]
                    ma20 = recent_prices['close'].rolling(20).mean().iloc[-1]

                    # Simple trend analysis
                    if current_price > ma20 * 1.02:
                        trend = 'bullish'
                    elif current_price < ma20 * 0.98:
                        trend = 'bearish'
                    else:
                        trend = 'neutral'

                    # Simple volatility measure
                    returns = recent_prices['close'].pct_change()
                    volatility = returns.std() * 100  # As percentage

                    if volatility > 5:
                        vol_level = 'high'
                    elif volatility < 2:
                        vol_level = 'low'
                    else:
                        vol_level = 'normal'

                    return {
                        'trend': trend,
                        'volatility': vol_level,
                        'volatility_pct': volatility,
                        'current_price': current_price,
                        'ma20': ma20,
                        'data_available': True
                    }

        except Exception as e:
            cprint(f"⚠️ Could not get market context for {symbol}: {e}", "yellow")

        # Return minimal context if data unavailable
        return {
            'trend': 'unknown',
            'volatility': 'unknown',
            'data_available': False
        }

    def evaluate_strategy_signals(self, signals: list, symbol: str) -> list:
        """
        Evaluate strategy signals using AI to determine which to execute

        Args:
            signals: List of strategy signals
            symbol: Trading symbol

        Returns:
            List of approved signals
        """
        if not signals or not self.ai_model:
            return signals  # Return all if no AI evaluation available

        try:
            # Prepare signals for AI evaluation
            signals_text = json.dumps(signals, indent=2)

            prompt = f"""
            Evaluate these strategy signals for {symbol} and decide which should be executed:

            Strategy Signals:
            {signals_text}

            Consider:
            1. Signal strength and confidence levels
            2. Agreement between different strategies
            3. Risk factors and market conditions
            4. Potential for conflicting signals

            Respond with a JSON array of approved signal indices (0-based) that should be executed.
            Example: [0, 2, 4] means execute signals at indices 0, 2, and 4.

            Only include signals you believe should be executed based on risk management principles.
            """

            response = self.ai_model.generate_response(
                system_prompt="You are a risk-averse trading strategy evaluator. Only approve signals that meet strict risk criteria.",
                user_content=prompt,
                temperature=0.3,
                max_tokens=200
            )

            # Parse AI response
            if isinstance(response, str):
                try:
                    # Try to extract JSON array
                    import re
                    json_match = re.search(r'\[.*\]', response)
                    if json_match:
                        approved_indices = json.loads(json_match.group())
                        approved_signals = [signals[i] for i in approved_indices if i < len(signals)]
                    else:
                        # If no JSON found, approve all signals (fallback)
                        approved_signals = signals
                except:
                    # Fallback: approve signals with confidence > 0.7
                    approved_signals = [s for s in signals if s.get('confidence', 0) > 0.7]
            else:
                approved_signals = signals

            cprint(f"🤖 AI approved {len(approved_signals)}/{len(signals)} signals for {symbol}", "green")

            return approved_signals

        except Exception as e:
            cprint(f"❌ Error in AI evaluation for {symbol}: {e}", "red")
            # Fallback: return high-confidence signals
            return [s for s in signals if s.get('confidence', 0) > 0.7]

    def publish_trading_signals(self, signals: list, symbol: str):
        """
        Publish approved signals to the trading agent via event bus

        Args:
            signals: List of approved strategy signals
            symbol: Trading symbol
        """
        try:
            for signal in signals:
                trading_signal = {
                    'source': 'strategy_agent',
                    'symbol': symbol,
                    'strategy_type': signal.get('strategy_type'),
                    'direction': signal.get('direction'),
                    'confidence': signal.get('confidence', 0),
                    'reasoning': signal.get('reasoning', ''),
                    'alert_data': signal.get('alert_data', {}),
                    'timestamp': str(datetime.now())
                }

                self.event_bus.publish('trading_signal', trading_signal)
                cprint(f"📤 Published trading signal for {symbol}: {signal.get('direction')} ({signal.get('confidence', 0):.1%})", "green")

                # Track processed signals
                self.processed_signals.append(trading_signal)

        except Exception as e:
            cprint(f"❌ Error publishing trading signals for {symbol}: {e}", "red")

    def evaluate_signals(self, signals, market_data):
        """Have LLM evaluate strategy signals"""
        try:
            if not self.ai_model or not signals:
                return None

            # Format signals for prompt
            signals_str = json.dumps(signals, indent=2)

            prompt = STRATEGY_EVAL_PROMPT.format(
                strategy_signals=signals_str,
                market_data=market_data
            )

            # Use DeepSeek model
            response = self.ai_model.generate_response(
                system_prompt="You are Moon Dev's Strategy Validation Assistant. Evaluate strategy signals and make EXECUTE/REJECT decisions.",
                user_content=prompt,
                temperature=AI_TEMPERATURE,
                max_tokens=AI_MAX_TOKENS
            )

            # Ensure response is a string
            if not isinstance(response, str):
                response = str(response)

            # Parse response
            lines = response.split('\n')
            decisions = lines[0].strip().split(',')
            reasoning = '\n'.join(lines[1:])

            print("🤖 Strategy Evaluation with DeepSeek:")
            print(f"Decisions: {decisions}")
            print(f"Reasoning: {reasoning}")

            return {
                'decisions': decisions,
                'reasoning': reasoning
            }

        except Exception as e:
            print(f"❌ Error evaluating signals with DeepSeek: {e}")
            return None

    def get_signals(self, token):
        """Get and evaluate signals from all enabled strategies"""
        try:
            # 1. Collect signals from all strategies
            signals = []
            print(f"\n🔍 Analyzing {token} with {len(self.enabled_strategies)} strategies...")
            
            for strategy in self.enabled_strategies:
                signal = strategy.generate_signals()
                if signal and signal['token'] == token:
                    signals.append({
                        'token': signal['token'],
                        'strategy_name': strategy.name,
                        'signal': signal['signal'],
                        'direction': signal['direction'],
                        'metadata': signal.get('metadata', {})
                    })
            
            if not signals:
                print(f"ℹ️ No strategy signals for {token}")
                return []
            
            print(f"\n📊 Raw Strategy Signals for {token}:")
            for signal in signals:
                print(f"  • {signal['strategy_name']}: {signal['direction']} ({signal['signal']}) for {signal['token']}")
            
            # 2. Get market data for context
            try:
                from src.data.ohlcv_collector import collect_token_data
                market_data = collect_token_data(token)
            except Exception as e:
                print(f"⚠️ Could not get market data: {e}")
                market_data = {}
            
            # 3. Have LLM evaluate the signals
            print("\n🤖 Getting LLM evaluation of signals...")
            evaluation = self.evaluate_signals(signals, market_data)
            
            if not evaluation:
                print("❌ Failed to get LLM evaluation")
                return []
            
            # 4. Filter signals based on LLM decisions
            approved_signals = []
            for signal, decision in zip(signals, evaluation['decisions']):
                if "EXECUTE" in decision.upper():
                    print(f"✅ LLM approved {signal['strategy_name']}'s {signal['direction']} signal")
                    approved_signals.append(signal)
                else:
                    print(f"❌ LLM rejected {signal['strategy_name']}'s {signal['direction']} signal")
            
            # 5. Print final approved signals
            if approved_signals:
                print(f"\n🎯 Final Approved Signals for {token}:")
                for signal in approved_signals:
                    print(f"  • {signal['strategy_name']}: {signal['direction']} ({signal['signal']})")
                
                # 6. Execute approved signals
                print("\n💫 Executing approved strategy signals...")
                self.execute_strategy_signals(approved_signals)
            else:
                print(f"\n⚠️ No signals approved by LLM for {token}")
            
            return approved_signals
            
        except Exception as e:
            print(f"❌ Error getting strategy signals: {e}")
            return []

    def combine_with_portfolio(self, signals, current_portfolio):
        """Combine strategy signals with current portfolio state"""
        try:
            final_allocations = current_portfolio.copy()
            
            for signal in signals:
                token = signal['token']
                strength = signal['signal']
                direction = signal['direction']
                
                if direction == 'BUY' and strength >= STRATEGY_MIN_CONFIDENCE:
                    print(f"🔵 Buy signal for {token} (strength: {strength})")
                    max_position = usd_size * (MAX_POSITION_PERCENTAGE / 100)
                    allocation = max_position * strength
                    final_allocations[token] = allocation
                elif direction == 'SELL' and strength >= STRATEGY_MIN_CONFIDENCE:
                    print(f"🔴 Sell signal for {token} (strength: {strength})")
                    final_allocations[token] = 0
            
            return final_allocations
            
        except Exception as e:
            print(f"❌ Error combining signals: {e}")
            return None 

    def execute_strategy_signals(self, approved_signals):
        """Execute trades based on approved strategy signals"""
        try:
            if not approved_signals:
                print("⚠️ No approved signals to execute")
                return

            print("\n🚀 Moon Dev executing strategy signals...")
            print(f"📝 Received {len(approved_signals)} signals to execute")
            
            for signal in approved_signals:
                try:
                    print(f"\n🔍 Processing signal: {signal}")  # Debug output
                    
                    token = signal.get('token')
                    if not token:
                        print("❌ Missing token in signal")
                        print(f"Signal data: {signal}")
                        continue
                        
                    strength = signal.get('signal', 0)
                    direction = signal.get('direction', 'NOTHING')
                    
                    # Skip USDC and other excluded tokens
                    if token in EXCLUDED_TOKENS:
                        print(f"💵 Skipping {token} (excluded token)")
                        continue
                    
                    print(f"\n🎯 Processing signal for {token}...")
                    
                    # Calculate position size based on signal strength
                    max_position = usd_size * (MAX_POSITION_PERCENTAGE / 100)
                    target_size = max_position * strength
                    
                    # Get current position value (using exchange manager if available)
                    if self.em:
                        current_position = self.em.get_token_balance_usd(token)
                    else:
                        current_position = n.get_token_balance_usd(token)

                    print(f"📊 Signal strength: {strength}")
                    print(f"🎯 Target position: ${target_size:.2f} USD")
                    print(f"📈 Current position: ${current_position:.2f} USD")

                    if direction == 'BUY':
                        if current_position < target_size:
                            print(f"✨ Executing BUY for {token}")
                            if self.em:
                                self.em.ai_entry(token, target_size)
                            else:
                                n.ai_entry(token, target_size)
                            print(f"✅ Entry complete for {token}")
                        else:
                            print(f"⏸️ Position already at or above target size")

                    elif direction == 'SELL':
                        if current_position > 0:
                            print(f"📉 Executing SELL for {token}")
                            if self.em:
                                self.em.chunk_kill(token)
                            else:
                                n.chunk_kill(token, max_usd_order_size, slippage)
                            print(f"✅ Exit complete for {token}")
                        else:
                            print(f"⏸️ No position to sell")
                    
                    time.sleep(2)  # Small delay between trades
                    
                except Exception as e:
                    print(f"❌ Error processing signal: {str(e)}")
                    print(f"Signal data: {signal}")
                    continue
                
        except Exception as e:
            print(f"❌ Error executing strategy signals: {str(e)}")
            print("🔧 Moon Dev suggests checking the logs and trying again!") 
