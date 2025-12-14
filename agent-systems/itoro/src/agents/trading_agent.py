"""
🌙 Moon Dev's LLM Trading Agent
Handles all LLM-based trading decisions
"""

# ============================================================================
# AI MODEL CONFIGURATION - EDIT THESE SETTINGS
# ============================================================================

# AI Model Configuration (via Model Factory)
# Available types: 'groq', 'openai', 'claude', 'deepseek', 'xai', 'ollama'
# DeepSeek provides excellent reasoning for trading decisions
AI_MODEL_TYPE = 'deepseek'  # Using DeepSeek for all AI trading decisions
AI_MODEL_NAME = 'deepseek-chat'   # Fast chat model for trading

# Available DeepSeek models:
# - 'deepseek-chat' (default) - Fast chat model, good for trading
# - 'deepseek-reasoner' - Enhanced reasoning capabilities

# Available xAI models:
# - 'grok-4-fast-reasoning' (default) - Best value! 2M context, cheap, fast
# - 'grok-4-0709' - Most intelligent, higher cost
# - 'grok-3' - Previous generation

# Available Groq models:
# - 'llama-3.3-70b-versatile' (default) - Fast & powerful

# Available Claude models:
# - 'claude-3-5-haiku-latest' (default) - Fast
# - 'claude-3-5-sonnet-latest' - Balanced
# - 'claude-3-opus-latest' - Most powerful

# ============================================================================
# END CONFIGURATION
# ============================================================================

# Keep only these prompts
TRADING_PROMPT = """
You are Moon Dev's AI Trading Assistant 🌙

Analyze the provided market data and strategy signals (if available) to make a trading decision.

Market Data Criteria:
1. Price action relative to MA20 and MA40
2. RSI levels and trend
3. Volume patterns
4. Recent price movements

{strategy_context}

Respond in this exact format:
1. First line must be one of: BUY, SELL, or NOTHING (in caps)
2. Then explain your reasoning, including:
   - Technical analysis
   - Strategy signals analysis (if available)
   - Risk factors
   - Market conditions
   - Confidence level (as a percentage, e.g. 75%)

Remember: 
- Moon Dev always prioritizes risk management! 🛡️
- Never trade USDC or SOL directly
- Consider both technical and strategy signals
"""

ALLOCATION_PROMPT = """
You are Moon Dev's Portfolio Allocation Assistant 🌙

Given the total portfolio size and trading recommendations, allocate capital efficiently.
Consider:
1. Position sizing based on confidence levels
2. Risk distribution
3. Keep cash buffer as specified
4. Maximum allocation per position

Format your response as a Python dictionary:
{
    "token_address": allocated_amount,  # In USD
    ...
    "USDC_ADDRESS": remaining_cash  # Always use USDC_ADDRESS for cash
}

Remember:
- Total allocations must not exceed total_size
- Higher confidence should get larger allocations
- Never allocate more than {MAX_POSITION_PERCENTAGE}% to a single position
- Keep at least {CASH_PERCENTAGE}% in USDC as safety buffer
- Only allocate to BUY recommendations
- Cash must be stored as USDC using USDC_ADDRESS: {USDC_ADDRESS}
"""

import os
import sys
import pandas as pd
import json
from termcolor import colored, cprint
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
from pathlib import Path

# Add project root to path for imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Local imports
from src.config import *
from src import nice_funcs as n
from src.scripts.data_processing.ohlcv_collector import collect_all_tokens
from src.models.model_factory import model_factory
from src.scripts.shared_services.redis_event_bus import get_event_bus

# Load environment variables
load_dotenv()

class TradingAgent:
    def __init__(self):
        # Initialize AI model via model factory
        cprint(f"\n🤖 Initializing Trading Agent with {AI_MODEL_TYPE} model...", "cyan")
        self.model = model_factory.get_model(AI_MODEL_TYPE, AI_MODEL_NAME)

        if not self.model:
            cprint(f"❌ Failed to initialize {AI_MODEL_TYPE} model!", "red")
            cprint("Available models:", "yellow")
            for model_type in model_factory._models.keys():
                cprint(f"  - {model_type}", "yellow")
            sys.exit(1)

        cprint(f"✅ Using model: {self.model.model_name}", "green")

        # Initialize Redis event bus
        self.event_bus = get_event_bus()
        self.strategy_signals = []  # Queue for strategy signals

        # Subscribe to trading signals from strategy agent
        self.event_bus.subscribe('trading_signal', self.handle_trading_signal)

        self.recommendations_df = pd.DataFrame(columns=['token', 'action', 'confidence', 'reasoning'])
        cprint("🔄 Trading Agent connected to event bus for strategy signals", "cyan")
        cprint("🤖 Moon Dev's LLM Trading Agent initialized!", "green")

    def handle_trading_signal(self, signal_data: dict):
        """
        Handle incoming trading signals from the strategy agent

        Args:
            signal_data: Trading signal from Redis event bus
        """
        try:
            cprint(f"📡 Trading Agent received signal: {signal_data.get('symbol', 'UNKNOWN')} {signal_data.get('direction', 'UNKNOWN')}", "cyan")

            # Add to strategy signals queue
            self.strategy_signals.append(signal_data)

            # Log signal details
            confidence = signal_data.get('confidence', 0)
            strategy = signal_data.get('strategy_type', 'unknown')
            reasoning = signal_data.get('reasoning', 'No reasoning provided')

            cprint(f"   🎯 Strategy: {strategy} | Confidence: {confidence:.1%}", "cyan")
            cprint(f"   💭 Reasoning: {reasoning[:100]}{'...' if len(reasoning) > 100 else ''}", "cyan")

        except Exception as e:
            cprint(f"❌ Error handling trading signal: {e}", "red")

    def chat_with_ai(self, system_prompt, user_content):
        """Send prompt to AI model via model factory"""
        try:
            response = self.model.generate_response(
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=AI_TEMPERATURE,
                max_tokens=AI_MAX_TOKENS
            )

            # Handle response format
            if hasattr(response, 'content'):
                return response.content
            return str(response)

        except Exception as e:
            cprint(f"❌ AI model error: {e}", "red")
            return None

    def analyze_market_data(self, token, market_data):
        """Analyze market data using AI model"""
        try:
            # Skip analysis for excluded tokens
            if token in EXCLUDED_TOKENS:
                print(f"⚠️ Skipping analysis for excluded token: {token}")
                return None

            # Prepare strategy context
            strategy_context = ""
            if 'strategy_signals' in market_data:
                strategy_context = f"""
Strategy Signals Available:
{json.dumps(market_data['strategy_signals'], indent=2)}
                """
            else:
                strategy_context = "No strategy signals available."

            # Call AI model via model factory
            response = self.chat_with_ai(
                TRADING_PROMPT.format(strategy_context=strategy_context),
                f"Market Data to Analyze:\n{market_data}"
            )

            if not response:
                cprint(f"❌ No response from AI for {token}", "red")
                return None

            # Parse the response
            lines = response.split('\n')
            action = lines[0].strip() if lines else "NOTHING"
            
            # Extract confidence from the response (assuming it's mentioned as a percentage)
            confidence = 0
            for line in lines:
                if 'confidence' in line.lower():
                    # Extract number from string like "Confidence: 75%"
                    try:
                        confidence = int(''.join(filter(str.isdigit, line)))
                    except:
                        confidence = 50  # Default if not found
            
            # Add to recommendations DataFrame with proper reasoning
            reasoning = '\n'.join(lines[1:]) if len(lines) > 1 else "No detailed reasoning provided"
            self.recommendations_df = pd.concat([
                self.recommendations_df,
                pd.DataFrame([{
                    'token': token,
                    'action': action,
                    'confidence': confidence,
                    'reasoning': reasoning
                }])
            ], ignore_index=True)
            
            print(f"🎯 Moon Dev's AI Analysis Complete for {token[:4]}!")
            return response
            
        except Exception as e:
            print(f"❌ Error in AI analysis: {str(e)}")
            # Still add to DataFrame even on error, but mark as NOTHING with 0 confidence
            self.recommendations_df = pd.concat([
                self.recommendations_df,
                pd.DataFrame([{
                    'token': token,
                    'action': "NOTHING",
                    'confidence': 0,
                    'reasoning': f"Error during analysis: {str(e)}"
                }])
            ], ignore_index=True)
            return None
    
    def allocate_portfolio(self):
        """Get AI-recommended portfolio allocation"""
        try:
            cprint("\n💰 Calculating optimal portfolio allocation...", "cyan")
            max_position_size = usd_size * (MAX_POSITION_PERCENTAGE / 100)
            cprint(f"🎯 Maximum position size: ${max_position_size:.2f} ({MAX_POSITION_PERCENTAGE}% of ${usd_size:.2f})", "cyan")

            # Get allocation from AI via model factory
            allocation_prompt = f"""You are Moon Dev's Portfolio Allocation AI 🌙

Given:
- Total portfolio size: ${usd_size}
- Maximum position size: ${max_position_size} ({MAX_POSITION_PERCENTAGE}% of total)
- Minimum cash (USDC) buffer: {CASH_PERCENTAGE}%
- Available tokens: {MONITORED_TOKENS}
- USDC Address: {USDC_ADDRESS}

Provide a portfolio allocation that:
1. Never exceeds max position size per token
2. Maintains minimum cash buffer
3. Returns allocation as a JSON object with token addresses as keys and USD amounts as values
4. Uses exact USDC address: {USDC_ADDRESS} for cash allocation

Example format:
{{
    "token_address": amount_in_usd,
    "{USDC_ADDRESS}": remaining_cash_amount  # Use exact USDC address
}}"""

            response = self.chat_with_ai("", allocation_prompt)

            if not response:
                cprint("❌ No response from AI for portfolio allocation", "red")
                return None

            # Parse the response
            allocations = self.parse_allocation_response(response)
            if not allocations:
                return None
                
            # Fix USDC address if needed
            if "USDC_ADDRESS" in allocations:
                amount = allocations.pop("USDC_ADDRESS")
                allocations[USDC_ADDRESS] = amount
                
            # Validate allocation totals
            total_allocated = sum(allocations.values())
            if total_allocated > usd_size:
                cprint(f"❌ Total allocation ${total_allocated:.2f} exceeds portfolio size ${usd_size:.2f}", "red")
                return None
                
            # Print allocations
            cprint("\n📊 Portfolio Allocation:", "green")
            for token, amount in allocations.items():
                token_display = "USDC" if token == USDC_ADDRESS else token
                cprint(f"  • {token_display}: ${amount:.2f}", "green")
                
            return allocations
            
        except Exception as e:
            cprint(f"❌ Error in portfolio allocation: {str(e)}", "red")
            return None

    def execute_allocations(self, allocation_dict):
        """Execute the allocations using spot or leverage trading"""
        from src.config import USE_LEVERAGE_TRADING, LEVERAGE_EXCHANGE, LEVERAGE_SUPPORTED_ASSETS

        try:
            print("\n🚀 Moon Dev executing portfolio allocations...")

            # Determine trading mode
            leverage_mode = USE_LEVERAGE_TRADING and LEVERAGE_EXCHANGE == 'hyperliquid'
            if leverage_mode:
                print("⚡ LEVERAGE MODE: Using Hyperliquid perpetual futures")
            else:
                print("🏪 SPOT MODE: Using traditional spot trading")
            for token, amount in allocation_dict.items():
                # Skip USDC and other excluded tokens
                if token in EXCLUDED_TOKENS:
                    print(f"💵 Keeping ${amount:.2f} in {token}")
                    continue

                print(f"\n🎯 Processing allocation for {token}...")

                try:
                    # Check if token is supported for leverage trading
                    token_symbol = self._get_token_symbol(token)
                    is_leverage_supported = leverage_mode and token_symbol in LEVERAGE_SUPPORTED_ASSETS

                    if is_leverage_supported:
                        # LEVERAGE TRADING PATH
                        print(f"⚡ Executing LEVERAGED trade for {token_symbol}")
                        success = self._execute_leverage_trade(token, amount, 'BUY')
                        if success:
                            print(f"✅ Leveraged entry complete for {token_symbol}")
                        else:
                            print(f"❌ Leveraged entry failed for {token_symbol}")
                    else:
                        # SPOT TRADING PATH (existing logic)
                        current_position = n.get_token_balance_usd(token)
                        target_allocation = amount

                        print(f"🎯 Target allocation: ${target_allocation:.2f} USD")
                        print(f"📊 Current position: ${current_position:.2f} USD")

                        if current_position < target_allocation:
                            print(f"✨ Executing SPOT entry for {token}")
                            n.ai_entry(token, amount)
                            print(f"✅ Spot entry complete for {token}")
                        else:
                            print(f"⏸️ Position already at target size for {token}")

                except Exception as e:
                    print(f"❌ Error executing entry for {token}: {str(e)}")

                time.sleep(2)  # Small delay between entries
                
        except Exception as e:
            print(f"❌ Error executing allocations: {str(e)}")
            print("🔧 Moon Dev suggests checking the logs and trying again!")

    def _execute_leverage_trade(self, token_address: str, usd_amount: float, direction: str):
        """
        Execute a leveraged trade on Hyperliquid

        Args:
            token_address: Token contract address
            usd_amount: Position size in USD
            direction: 'BUY' or 'SELL'

        Returns:
            bool: Success status
        """
        try:
            from src import nice_funcs_hl as hl
            from src.config import DEFAULT_LEVERAGE

            # Use the high-level leverage entry function
            result = hl.hyperliquid_leverage_entry(
                token_address=token_address,
                direction=direction,
                confidence=0.8,  # High confidence for AI-driven trades
                usd_size=usd_amount
            )

            return result is not None and result.get('success', False)

        except Exception as e:
            print(f"❌ Leverage trade execution failed: {str(e)}")
            return False

    def _get_token_symbol(self, token_address: str):
        """
        Convert token address to symbol for leverage trading

        Args:
            token_address: Token contract address

        Returns:
            str: Token symbol
        """
        # Common token mappings (expand as needed)
        token_map = {
            'So11111111111111111111111111111111111111111': 'SOL',
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'USDC',
            '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump': 'BONK',
            '67mTTGnVRunoSLGitgRGK2FJp5cT1KschjzWH9zKc3r': 'WIF',
            'C94njgTrKMQBmgqe23EGLrtPgfvcjWtqBBvGQ7Cjiank': 'WIF',
            '67mTTGnVRunoSLGitgRGK2FJp5cT1KschjzWH9zKc3r': 'BONK',
            '9YnfbEaXPaPmoXnKZFmNH8hzcLyjbRf56MQP7oqGpump': 'PUMP'
        }

        return token_map.get(token_address, token_address[:4].upper())

    def _get_leverage_position_value(self, token_symbol: str):
        """
        Get the current leveraged position value for a token

        Args:
            token_symbol: Token symbol (e.g., 'BTC', 'ETH')

        Returns:
            float: Position value in USD
        """
        try:
            from src import nice_funcs_hl as hl

            # Get position from Hyperliquid
            position = hl.get_hyperliquid_position(f"{token_symbol}PERP")

            if position and position.get('size', 0) != 0:
                # Calculate position value (simplified)
                # In reality, you'd get the mark price and calculate properly
                size = abs(position['size'])
                entry_price = position.get('entry_price', 0)
                return size * entry_price
            else:
                return 0

        except Exception as e:
            print(f"❌ Error getting leverage position for {token_symbol}: {str(e)}")
            return 0

    def _execute_leverage_exit(self, token_symbol: str, percentage: float = 100.0):
        """
        Execute a leveraged position exit

        Args:
            token_symbol: Token symbol to exit
            percentage: Percentage of position to close (0-100)

        Returns:
            bool: Success status
        """
        try:
            from src import nice_funcs_hl as hl

            # Close position using Hyperliquid
            result = hl.hyperliquid_close_position(token_symbol, percentage)

            return result is not None and result.get('success', False)

        except Exception as e:
            print(f"❌ Leverage exit failed for {token_symbol}: {str(e)}")
            return False

    def handle_exits(self):
        """Check and exit positions based on SELL or NOTHING recommendations"""
        from src.config import USE_LEVERAGE_TRADING, LEVERAGE_EXCHANGE, LEVERAGE_SUPPORTED_ASSETS

        cprint("\n🔄 Checking for positions to exit...", "white", "on_blue")

        # Determine trading mode
        leverage_mode = USE_LEVERAGE_TRADING and LEVERAGE_EXCHANGE == 'hyperliquid'

        for _, row in self.recommendations_df.iterrows():
            token = row['token']

            # Skip excluded tokens (USDC and SOL)
            if token in EXCLUDED_TOKENS:
                continue

            action = row['action']
            token_symbol = self._get_token_symbol(token)
            is_leverage_supported = leverage_mode and token_symbol in LEVERAGE_SUPPORTED_ASSETS

            # Check if we have a position (different logic for spot vs leverage)
            if is_leverage_supported:
                # LEVERAGE POSITION CHECK
                current_position = self._get_leverage_position_value(token_symbol)
                position_type = "leveraged"
            else:
                # SPOT POSITION CHECK
                current_position = n.get_token_balance_usd(token)
                position_type = "spot"

            if current_position > 0 and action in ["SELL", "NOTHING"]:
                cprint(f"\n🚫 AI Agent recommends {action} for {token}", "white", "on_yellow")
                cprint(f"💰 Current {position_type} position: ${current_position:.2f}", "white", "on_blue")

                try:
                    if is_leverage_supported:
                        # LEVERAGE EXIT
                        cprint(f"📉 Closing LEVERAGED position...", "white", "on_cyan")
                        success = self._execute_leverage_exit(token_symbol)
                        if success:
                            cprint(f"✅ Successfully closed leveraged position", "white", "on_green")
                        else:
                            cprint(f"❌ Failed to close leveraged position", "white", "on_red")
                    else:
                        # SPOT EXIT
                        cprint(f"📉 Closing SPOT position with chunk_kill...", "white", "on_cyan")
                        n.chunk_kill(token, max_usd_order_size, slippage)
                        cprint(f"✅ Successfully closed spot position", "white", "on_green")
                except Exception as e:
                    cprint(f"❌ Error closing {position_type} position: {str(e)}", "white", "on_red")
            elif current_position > 0:
                cprint(f"✨ Keeping {position_type} position for {token} (${current_position:.2f}) - AI recommends {action}", "white", "on_blue")

    def parse_allocation_response(self, response):
        """Parse the AI's allocation response and handle both string and TextBlock formats"""
        try:
            # Handle TextBlock format from Claude 3
            if isinstance(response, list):
                response = response[0].text if hasattr(response[0], 'text') else str(response[0])
            
            print("🔍 Raw response received:")
            print(response)
            
            # Find the JSON block between curly braces
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON object found in response")
            
            json_str = response[start:end]
            
            # More aggressive JSON cleaning
            json_str = (json_str
                .replace('\n', '')          # Remove newlines
                .replace('    ', '')        # Remove indentation
                .replace('\t', '')          # Remove tabs
                .replace('\\n', '')         # Remove escaped newlines
                .replace(' ', '')           # Remove all spaces
                .strip())                   # Remove leading/trailing whitespace
            
            print("\n🧹 Cleaned JSON string:")
            print(json_str)
            
            # Parse the cleaned JSON
            allocations = json.loads(json_str)
            
            print("\n📊 Parsed allocations:")
            for token, amount in allocations.items():
                print(f"  • {token}: ${amount}")
            
            # Validate amounts are numbers
            for token, amount in allocations.items():
                if not isinstance(amount, (int, float)):
                    raise ValueError(f"Invalid amount type for {token}: {type(amount)}")
                if amount < 0:
                    raise ValueError(f"Negative allocation for {token}: {amount}")
            
            return allocations
            
        except Exception as e:
            print(f"❌ Error parsing allocation response: {str(e)}")
            print("🔍 Raw response:")
            print(response)
            return None

    def parse_portfolio_allocation(self, allocation_text):
        """Parse portfolio allocation from text response"""
        try:
            # Clean up the response text
            cleaned_text = allocation_text.strip()
            if "```json" in cleaned_text:
                # Extract JSON from code block if present
                json_str = cleaned_text.split("```json")[1].split("```")[0]
            else:
                # Find the JSON object between curly braces
                start = cleaned_text.find('{')
                end = cleaned_text.rfind('}') + 1
                json_str = cleaned_text[start:end]
            
            # Parse the JSON
            allocations = json.loads(json_str)
            
            print("📊 Parsed allocations:")
            for token, amount in allocations.items():
                print(f"  • {token}: ${amount}")
            
            return allocations
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing allocation JSON: {e}")
            print(f"🔍 Raw text received:\n{allocation_text}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error parsing allocations: {e}")
            return None

    def run(self):
        """Run the trading agent (implements BaseAgent interface)"""
        self.run_trading_cycle()

    def run_trading_cycle(self, strategy_signals=None):
        """Run one complete trading cycle"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cprint(f"\n⏰ AI Agent Run Starting at {current_time}", "white", "on_green")
            
            # Collect OHLCV data for all tokens
            cprint("📊 Collecting market data...", "white", "on_blue")
            market_data = collect_all_tokens()
            
            # Get strategy signals received from event bus
            current_strategy_signals = self.strategy_signals.copy()
            self.strategy_signals.clear()  # Clear after processing

            # Group strategy signals by token
            strategy_signals_by_token = {}
            for signal in current_strategy_signals:
                token = signal.get('symbol', 'UNKNOWN')
                if token not in strategy_signals_by_token:
                    strategy_signals_by_token[token] = []
                strategy_signals_by_token[token].append(signal)

            if current_strategy_signals:
                cprint(f"🎯 Processing {len(current_strategy_signals)} strategy signals from event bus", "cyan")

            # Analyze each token's data
            for token, data in market_data.items():
                cprint(f"\n🤖 AI Agent Analyzing Token: {token}", "white", "on_green")

                # Include strategy signals for this token if available
                if token in strategy_signals_by_token:
                    signals_for_token = strategy_signals_by_token[token]
                    cprint(f"📊 Including {len(signals_for_token)} strategy signals in analysis", "cyan")
                    data['strategy_signals'] = signals_for_token

                    # Log strategy signals
                    for signal in signals_for_token:
                        direction = signal.get('direction', 'UNKNOWN')
                        confidence = signal.get('confidence', 0)
                        strategy = signal.get('strategy_type', 'unknown')
                        cprint(f"   🎯 {strategy}: {direction} ({confidence:.1%} confidence)", "cyan")

                analysis = self.analyze_market_data(token, data)
                print(f"\n📈 Analysis for contract: {token}")
                print(analysis)
                print("\n" + "="*50 + "\n")
            
            # Show recommendations summary
            cprint("\n📊 Moon Dev's Trading Recommendations:", "white", "on_blue")
            summary_df = self.recommendations_df[['token', 'action', 'confidence']].copy()
            print(summary_df.to_string(index=False))
            
            # Handle exits first
            self.handle_exits()
            
            # Then proceed with new allocations
            cprint("\n💰 Calculating optimal portfolio allocation...", "white", "on_blue")
            allocation = self.allocate_portfolio()
            
            if allocation:
                cprint("\n💼 Moon Dev's Portfolio Allocation:", "white", "on_blue")
                print(json.dumps(allocation, indent=4))
                
                cprint("\n🎯 Executing allocations...", "white", "on_blue")
                self.execute_allocations(allocation)
                cprint("\n✨ All allocations executed!", "white", "on_blue")
            else:
                cprint("\n⚠️ No allocations to execute!", "white", "on_yellow")
            
            # Clean up temp data
            cprint("\n🧹 Cleaning up temporary data...", "white", "on_blue")
            try:
                for file in os.listdir('temp_data'):
                    if file.endswith('_latest.csv'):
                        os.remove(os.path.join('temp_data', file))
                cprint("✨ Temp data cleaned successfully!", "white", "on_green")
            except Exception as e:
                cprint(f"⚠️ Error cleaning temp data: {str(e)}", "white", "on_yellow")
            
        except Exception as e:
            cprint(f"\n❌ Error in trading cycle: {str(e)}", "white", "on_red")
            cprint("🔧 Moon Dev suggests checking the logs and trying again!", "white", "on_blue")

def main():
    """Main function to run the trading agent every 15 minutes"""
    cprint("🌙 Moon Dev AI Trading System Starting Up! 🚀", "white", "on_blue")
    
    agent = TradingAgent()
    INTERVAL = SLEEP_BETWEEN_RUNS_MINUTES * 60  # Convert minutes to seconds
    
    while True:
        try:
            agent.run_trading_cycle()
            
            next_run = datetime.now() + timedelta(minutes=SLEEP_BETWEEN_RUNS_MINUTES)
            cprint(f"\n⏳ AI Agent run complete. Next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}", "white", "on_green")
            
            # Sleep until next interval
            time.sleep(INTERVAL)
                
        except KeyboardInterrupt:
            cprint("\n👋 Moon Dev AI Agent shutting down gracefully...", "white", "on_blue")
            break
        except Exception as e:
            cprint(f"\n❌ Error: {str(e)}", "white", "on_red")
            cprint("🔧 Moon Dev suggests checking the logs and trying again!", "white", "on_blue")
            # Still sleep and continue on error
            time.sleep(INTERVAL)

if __name__ == "__main__":
    main() 
