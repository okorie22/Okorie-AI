"""
🌙 Anarcho Capital's Simplified Harvesting Agent
Portfolio management agent with 4 clear triggers:
1. Emergency rebalancing (SOL/USDC > 95%)
2. SOL below target rebalancing
3. USDC below target rebalancing  
4. AI-driven realized gains reallocation
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import json
import re
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# AI imports
import openai
import anthropic

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical, logger
from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
from src.agents.base_agent import BaseAgent
from src.scripts.data_processing.sentiment_data_extractor import get_sentiment_data_extractor
from src import config
from src import paper_trading
import pandas as pd

# Configuration imports
from src.config import (
    SOL_TARGET_PERCENT, SOL_MINIMUM_PERCENT, SOL_MAXIMUM_PERCENT,
    USDC_TARGET_PERCENT, USDC_MINIMUM_PERCENT,
    REALIZED_GAIN_THRESHOLD_USD, REALLOCATION_EXTERNAL_PCT,
    EXTERNAL_WALLET_1, EXTERNAL_WALLET_ENABLED,
    HARVESTING_MODEL_OVERRIDE, HARVESTING_AI_PROMPT,
    AI_TEMPERATURE, AI_MAX_TOKENS,
    PAPER_TRADING_ENABLED, HARVESTING_INTERVAL_CHECK_MINUTES,
    CONVERSION_SLIPPAGE_BPS, REBALANCING_PRIORITY_FEE,
    SOL_ADDRESS, USDC_ADDRESS, EXCLUDED_TOKENS,
    HARVESTING_DEEPSEEK_BASE_URL,
    HARVESTING_ENABLED, HARVESTING_USE_CHART_SENTIMENT_ONLY,
    HARVESTING_CHART_SENTIMENT_FILE, HARVESTING_MAX_CHART_DATA_AGE_MINUTES,
    HARVESTING_STARTUP_GRACE_PERIOD_SECONDS,
    HARVESTING_DUST_CONVERSION_ENABLED
)


class HarvestingAgent(BaseAgent):
    def __init__(self, enable_ai: bool = True):
        """Initialize the simplified harvesting agent"""
        super().__init__("harvesting_agent")
        
        # Initialize shared services
        self.data_coordinator = get_shared_data_coordinator()
        self.price_service = get_optimized_price_service()
        self.api_manager = get_shared_api_manager()
        
        # Configuration
        self.enabled = HARVESTING_ENABLED
        self.check_interval_minutes = HARVESTING_INTERVAL_CHECK_MINUTES
        self.continuous_mode = True
        self.monitoring_only = False
        
        # State tracking
        self.last_check_time = 0
        self.is_running = False
        self.thread = None
        self.realized_gains_total = 0.0
        self.last_interval_check = time.time()
        self.external_wallet_transfers = []
        
        # Initialize AI clients only if explicitly requested
        self.ai_enabled = enable_ai
        if enable_ai:
            self._init_ai_clients()
        else:
            self.client = None
            self.deepseek_client = None
            self.claude_client = None
            self.openai_client = None
            self.ai_model = None
            self.ai_temperature = None
            self.ai_max_tokens = None
        
        # Initialize portfolio tracker reference
        try:
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            self.portfolio_tracker = get_portfolio_tracker()
            info("✅ Portfolio tracker connected successfully")
        except Exception as e:
            error(f"Could not initialize portfolio tracker reference: {e}")
            self.portfolio_tracker = None
        
        info("🌾 Simplified Harvesting Agent initialized successfully")
        info(f"  • AI Enabled: {self.ai_enabled}")
        info(f"  • Paper Trading: {PAPER_TRADING_ENABLED}")
        info(f"  • Interval: {self.check_interval_minutes} minutes")
        info(f"  • SOL Target: {SOL_TARGET_PERCENT*100:.1f}%")
        info(f"  • USDC Target: {USDC_TARGET_PERCENT*100:.1f}%")
    
    def _init_ai_clients(self):
        """Initialize AI clients with fallback support"""
        try:
            # DeepSeek (primary) - use your existing API key
            deepseek_api_key = os.getenv('DEEPSEEK_KEY') or os.getenv('DEEPSEEK_API_KEY')
            if deepseek_api_key:
                self.deepseek_client = openai.OpenAI(
                    api_key=deepseek_api_key,
                    base_url=HARVESTING_DEEPSEEK_BASE_URL
                )
                info(f"✅ DeepSeek client initialized with API key: {deepseek_api_key[:8]}...")
            else:
                warning("DEEPSEEK_API_KEY not found in environment")
                self.deepseek_client = None
            
            # Claude (fallback)
            claude_api_key = os.getenv('ANTHROPIC_API_KEY')
            if claude_api_key:
                self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
                info(f"✅ Claude client initialized with API key: {claude_api_key[:8]}...")
            else:
                self.claude_client = None
            
            # OpenAI (fallback)
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if openai_api_key:
                self.openai_client = openai.OpenAI(api_key=openai_api_key)
                info(f"✅ OpenAI client initialized with API key: {openai_api_key[:8]}...")
            else:
                self.openai_client = None
            
            # AI configuration
            self.ai_model = HARVESTING_MODEL_OVERRIDE
            self.ai_temperature = AI_TEMPERATURE
            self.ai_max_tokens = AI_MAX_TOKENS
            
            info(f"🤖 AI Model: {self.ai_model}, Temperature: {self.ai_temperature}, Max Tokens: {self.ai_max_tokens}")
            
        except Exception as e:
            error(f"AI client initialization error: {e}")
            self.deepseek_client = None
            self.claude_client = None
            self.openai_client = None
    
    def on_portfolio_change(self, current_snapshot, previous_snapshot):
        """Main entry point - called by portfolio tracker on significant changes"""
        try:
            info("🌾 Portfolio change detected - checking all triggers")
            
            # Check all 4 triggers
            self._check_emergency_rebalancing(current_snapshot)
            self._check_target_rebalancing(current_snapshot)
            self._check_realized_gains(current_snapshot, previous_snapshot)
            self._check_and_convert_dust(current_snapshot)
            
        except Exception as e:
            error(f"Error in portfolio change handler: {str(e)}")
    
    def run(self):
        """30-minute interval loop for hybrid triggering"""
        try:
            info("🌾 Harvesting Agent running in hybrid mode")
            info(f"  • Interval checks: Every {self.check_interval_minutes} minutes")
            
            # Initialize interval checking
            self.last_interval_check = time.time()
            
            # Hybrid execution loop
            while self.running:
                current_time = time.time()
                interval_seconds = self.check_interval_minutes * 60
                
                # Interval-based check
                if current_time - self.last_interval_check >= interval_seconds:
                    info("🌾 Running interval-based checks...")
                    self._execute_interval_based_checks()
                    self.last_interval_check = current_time
                else:
                    # Heartbeat every 10 minutes
                    if int(current_time) % 600 == 0:
                        next_check_minutes = int((interval_seconds - (current_time - self.last_interval_check))/60)
                        info(f"🌾 Harvesting Agent: Running (next check in {next_check_minutes} min)")
                
                time.sleep(60)  # Check every minute
            
        except Exception as e:
            error(f"Error in harvesting agent run loop: {str(e)}")
            critical(f"Harvesting agent crashed: {traceback.format_exc()}")
    
    def _execute_interval_based_checks(self):
        """Comprehensive interval-based checking for all conditions"""
        try:
            # Get current portfolio snapshot
            current_snapshot = self._get_current_portfolio_snapshot()
            if not current_snapshot:
                warning("No portfolio snapshot available for interval check")
                return
            
            # Check each condition separately
            conditions_met = []
            
            if self._check_emergency_rebalancing(current_snapshot):
                conditions_met.append('emergency_rebalancing')
            
            if self._check_target_rebalancing(current_snapshot):
                conditions_met.append('target_rebalancing')
            
            # Check for dust positions
            if self._check_and_convert_dust(current_snapshot):
                conditions_met.append('dust_conversion')
            
            if conditions_met:
                info(f"Interval check conditions met: {', '.join(conditions_met)}")
            else:
                info("Interval check: no conditions met")
                
        except Exception as e:
            error(f"Error in interval-based checks: {e}")
    
    def _get_current_portfolio_snapshot(self):
        """Get current portfolio snapshot for interval checks"""
        try:
            if self.portfolio_tracker and hasattr(self.portfolio_tracker, 'current_snapshot'):
                return self.portfolio_tracker.current_snapshot
            return None
        except Exception as e:
            error(f"Error getting portfolio snapshot: {e}")
            return None
    
    # =============================================================================
    # DUST COLLECTION LOGIC
    # =============================================================================
    
    def _check_and_convert_dust(self, snapshot):
        """Check for dust positions and convert to SOL (lightweight operation)"""
        try:
            from src.config import DUST_THRESHOLD_USD, ALLOW_EXCLUDED_DUST, EXCLUDED_TOKENS
            
            if not HARVESTING_DUST_CONVERSION_ENABLED:
                return False
            
            # Get dust positions from portfolio tracker
            dust_positions = []
            for token_address, position_data in snapshot.positions.items():
                # Handle both dict and float position data
                if isinstance(position_data, dict):
                    value_usd = position_data.get('value_usd', 0)
                else:
                    value_usd = float(position_data)
                
                # Skip excluded tokens unless allowed
                if token_address in EXCLUDED_TOKENS and not ALLOW_EXCLUDED_DUST:
                    continue
                
                # Check if position is dust
                if 0 < value_usd <= DUST_THRESHOLD_USD:
                    dust_positions.append({
                        'address': token_address,
                        'value_usd': value_usd
                    })
            
            if not dust_positions:
                return False
            
            # Convert dust to SOL
            total_dust_value = sum(pos['value_usd'] for pos in dust_positions)
            info(f"🧹 Found {len(dust_positions)} dust positions totaling ${total_dust_value:.2f}")
            
            success = self._convert_dust_to_sol(dust_positions)
            return success
            
        except Exception as e:
            error(f"Error checking dust: {e}")
            return False
    
    def _convert_dust_to_sol(self, dust_positions):
        """Convert dust positions to SOL"""
        try:
            total_value = sum(pos['value_usd'] for pos in dust_positions)
            
            if PAPER_TRADING_ENABLED:
                return self._convert_dust_to_sol_paper(dust_positions, total_value)
            else:
                return self._convert_dust_to_sol_live(dust_positions, total_value)
        
        except Exception as e:
            error(f"Error converting dust: {e}")
            return False
    
    def _convert_dust_to_sol_paper(self, dust_positions, total_value):
        """Paper trading: Convert dust to SOL"""
        try:
            from src import paper_trading
            
            info(f"🧹 Paper dust conversion: ${total_value:.2f} → SOL")
            
            # Convert each dust position to USDC
            for position in dust_positions:
                try:
                    # Sell dust token
                    paper_trading.execute_paper_trade(
                        token_address=position['address'],
                        action="SELL",
                        amount=position['value_usd'],
                        price=position['value_usd'],
                        agent="harvesting_dust"
                    )
                    
                    # Add equivalent USDC (will be swapped to SOL later)
                    paper_trading.execute_paper_trade(
                        token_address=USDC_ADDRESS,
                        action="BUY",
                        amount=position['value_usd'],
                        price=1.0,
                        agent="harvesting_dust"
                    )
                except Exception as e:
                    error(f"Error converting dust token {position['address'][:8]}...: {e}")
            
            # Now convert accumulated USDC to SOL
            return self._swap_usdc_to_sol(total_value)
            
        except Exception as e:
            error(f"Error in paper dust conversion: {e}")
            return False
    
    def _convert_dust_to_sol_live(self, dust_positions, total_value):
        """Live trading: Convert dust to SOL via Jupiter"""
        try:
            from src import nice_funcs as n
            
            info(f"🧹 Live dust conversion: ${total_value:.2f} → SOL")
            
            # Sell each dust token and accumulate USDC
            for position in dust_positions:
                try:
                    # Use chunk_kill for full dust position sale
                    success = n.chunk_kill(position['address'])
                    if success:
                        info(f"✅ Sold dust: {position['address'][:8]}... (${position['value_usd']:.2f})")
                    else:
                        error(f"❌ Failed to sell dust: {position['address'][:8]}...")
                except Exception as e:
                    error(f"Error selling dust token {position['address'][:8]}: {e}")
            
            # Convert accumulated USDC to SOL
            return self._swap_usdc_to_sol(total_value)
        
        except Exception as e:
            error(f"Error in live dust conversion: {e}")
            return False
    
    # =============================================================================
    # TRIGGER 1: EMERGENCY REBALANCING (95% threshold)
    # =============================================================================
    
    def _check_emergency_rebalancing(self, snapshot):
        """SOL or USDC > 95% - immediate rebalance to targets"""
        try:
            total = snapshot.total_value_usd
            if total <= 0:
                return False
            
            sol_pct = snapshot.sol_value_usd / total
            usdc_pct = snapshot.usdc_balance / total
            
            if sol_pct > 0.95:
                info(f"🚨 EMERGENCY: SOL at {sol_pct*100:.1f}% - rebalancing to targets")
                return self._execute_emergency_sol_rebalancing(snapshot)
            elif usdc_pct > 0.95:
                info(f"🚨 EMERGENCY: USDC at {usdc_pct*100:.1f}% - rebalancing to targets")
                return self._execute_emergency_usdc_rebalancing(snapshot)
            
            return False
            
        except Exception as e:
            error(f"Error checking emergency rebalancing: {str(e)}")
            return False
    
    def _execute_emergency_sol_rebalancing(self, snapshot):
        """Execute emergency SOL rebalancing with proper validation"""
        try:
            total = snapshot.total_value_usd
            target_sol_usd = total * SOL_TARGET_PERCENT
            excess_sol_usd = snapshot.sol_value_usd - target_sol_usd
            
            if excess_sol_usd > 10:  # Minimum $10 to execute
                # Check if we have enough SOL in paper portfolio before attempting trade
                if PAPER_TRADING_ENABLED:
                    try:
                        from src.paper_trading import get_paper_portfolio
                        portfolio_df = get_paper_portfolio()
                        sol_row = portfolio_df[portfolio_df['token_address'] == SOL_ADDRESS]
                        
                        if sol_row.empty:
                            error("❌ No SOL balance in paper portfolio for emergency rebalancing")
                            return False
                        
                        available_sol = float(sol_row.iloc[0]['amount'])
                        sol_price = self.price_service.get_price(SOL_ADDRESS)
                        if not sol_price or sol_price <= 0:
                            error("❌ No valid SOL price for emergency rebalancing")
                            return False
                        
                        needed_sol_amount = excess_sol_usd / sol_price
                        if available_sol < needed_sol_amount:
                            # Adjust to available amount
                            actual_excess_usd = available_sol * sol_price
                            if actual_excess_usd > 10:
                                info(f"🔄 Emergency SOL rebalancing: Converting ${actual_excess_usd:.2f} SOL to USDC (adjusted for available balance)")
                                success = self._swap_sol_to_usdc(actual_excess_usd)
                            else:
                                warning(f"❌ Insufficient SOL for emergency rebalancing: ${actual_excess_usd:.2f} available (min: $10)")
                                return False
                        else:
                            info(f"🔄 Emergency SOL rebalancing: Converting ${excess_sol_usd:.2f} SOL to USDC")
                            success = self._swap_sol_to_usdc(excess_sol_usd)
                    except Exception as e:
                        error(f"❌ Error checking SOL balance for emergency rebalancing: {e}")
                        return False
                else:
                    info(f"🔄 Emergency SOL rebalancing: Converting ${excess_sol_usd:.2f} SOL to USDC")
                    success = self._swap_sol_to_usdc(excess_sol_usd)
                
                if success:
                    # Set cooldown timestamp to prevent immediate target rebalancing
                    self.last_emergency_rebalancing = time.time()
                return success
            
            return True
            
        except Exception as e:
            error(f"Error executing emergency SOL rebalancing: {str(e)}")
            return False
    
    def _execute_emergency_usdc_rebalancing(self, snapshot):
        """Execute emergency USDC rebalancing"""
        try:
            total = snapshot.total_value_usd
            target_usdc_usd = total * USDC_TARGET_PERCENT
            excess_usdc_usd = snapshot.usdc_balance - target_usdc_usd
            
            if excess_usdc_usd > 10:  # Minimum $10 to execute
                info(f"🔄 Emergency USDC rebalancing: Converting ${excess_usdc_usd:.2f} USDC to SOL")
                success = self._swap_usdc_to_sol(excess_usdc_usd)
                if success:
                    # Set cooldown timestamp to prevent immediate target rebalancing
                    self.last_emergency_rebalancing = time.time()
                return success
            
            return True
            
        except Exception as e:
            error(f"Error executing emergency USDC rebalancing: {str(e)}")
            return False
    
    # =============================================================================
    # TRIGGER 2 & 3: TARGET REBALANCING
    # =============================================================================
    
    def _check_target_rebalancing(self, snapshot):
        """Check SOL and USDC target rebalancing with execution cooldown"""
        try:
            total = snapshot.total_value_usd
            if total <= 0:
                return False
            
            sol_pct = snapshot.sol_value_usd / total
            usdc_pct = snapshot.usdc_balance / total
            
            actions_taken = []
            
            # Check if we just did emergency rebalancing (cooldown period)
            current_time = time.time()
            if hasattr(self, 'last_emergency_rebalancing') and (current_time - self.last_emergency_rebalancing) < 300:  # 5 minute cooldown
                info("🕐 Emergency rebalancing cooldown active - skipping target rebalancing")
                return False
            
            # Check SOL below target (independent check)
            if sol_pct < SOL_TARGET_PERCENT:
                needed_sol_usd = (SOL_TARGET_PERCENT * total) - snapshot.sol_value_usd
                if needed_sol_usd > 10:  # Minimum $10 to execute
                    info(f"⚖️ SOL below target: {sol_pct*100:.1f}% < {SOL_TARGET_PERCENT*100:.1f}%")
                    info(f"🔄 Converting ${needed_sol_usd:.2f} USDC to SOL")
                    if self._swap_usdc_to_sol(needed_sol_usd):
                        actions_taken.append('sol_rebalancing')
            
            # Check USDC below target (independent check - NOT elif)
            if usdc_pct < USDC_TARGET_PERCENT:
                needed_usdc_usd = (USDC_TARGET_PERCENT * total) - snapshot.usdc_balance
                if needed_usdc_usd > 10:  # Minimum $10 to execute
                    info(f"⚖️ USDC below target: {usdc_pct*100:.1f}% < {USDC_TARGET_PERCENT*100:.1f}%")
                    info(f"🔄 Raising ${needed_usdc_usd:.2f} USDC reserves")
                    if self._raise_usdc_reserves(needed_usdc_usd, snapshot):
                        actions_taken.append('usdc_rebalancing')
            
            return len(actions_taken) > 0
            
        except Exception as e:
            error(f"Error checking target rebalancing: {str(e)}")
            return False
    
    def _raise_usdc_reserves(self, needed_usdc_usd, snapshot):
        """Raise USDC reserves by selling positions ONLY - NO FALLBACK LOGIC"""
        try:
            # Only try to sell positions - no dangerous fallback logic
            if self._sell_positions_for_usdc(needed_usdc_usd):
                return True
            
            # If no positions to sell, fail safely - do NOT touch SOL
            warning(f"❌ Unable to raise ${needed_usdc_usd:.2f} USDC reserves - no positions available to sell")
            return False
            
        except Exception as e:
            error(f"Error raising USDC reserves: {str(e)}")
            return False
    
    # =============================================================================
    # TRIGGER 4: AI REALIZED GAINS REALLOCATION
    # =============================================================================
    
    def _is_in_startup_grace_period(self) -> bool:
        """Check if we're still in startup grace period (similar to Risk Agent logic)"""
        try:
            if not hasattr(self.portfolio_tracker, 'initialization_complete_time'):
                return False
            
            elapsed_time = time.time() - self.portfolio_tracker.initialization_complete_time
            return elapsed_time < HARVESTING_STARTUP_GRACE_PERIOD_SECONDS
        except Exception as e:
            error(f"Error checking startup grace period: {e}")
            return False
    
    def _is_startup_portfolio_state(self, current_snapshot) -> bool:
        """Check if portfolio state indicates startup scenario (similar to Risk Agent)"""
        try:
            total = current_snapshot.total_value_usd
            if total <= 0:
                return False
            
            sol_percent = current_snapshot.sol_value_usd / total
            usdc_percent = current_snapshot.usdc_balance / total
            
            # Startup scenario: High SOL allocation (>95%) and low USDC (<5%)
            return (sol_percent >= 0.95 and usdc_percent <= 0.05)
        except Exception as e:
            error(f"Error checking startup portfolio state: {e}")
            return False

    def _check_realized_gains(self, current_snapshot, previous_snapshot):
        """Detect USDC increase from closed trades with smart startup detection"""
        try:
            # Smart startup detection - check both time-based and portfolio state
            if self._is_in_startup_grace_period():
                debug(f"🚀 [STARTUP] Skipping realized gains check - in grace period")
                return False
            
            # Additional check: if portfolio is in startup state, skip realized gains
            if self._is_startup_portfolio_state(current_snapshot):
                debug(f"🚀 [STARTUP] Skipping realized gains check - portfolio in startup state")
                return False
            
            if not previous_snapshot:
                return False
            
            usdc_increase = current_snapshot.usdc_balance - previous_snapshot.usdc_balance
            
            if usdc_increase >= REALIZED_GAIN_THRESHOLD_USD:
                info(f"💰 Realized gains detected: ${usdc_increase:.2f} USDC increase")
                info(f"🤖 Triggering AI analysis for gains reallocation")
                return self._execute_ai_gains_reallocation(usdc_increase)
            
            return False
            
        except Exception as e:
            error(f"Error checking realized gains: {str(e)}")
            return False
    
    def _execute_ai_gains_reallocation(self, gains_amount):
        """AI determines conversion and allocation strategy"""
        try:
            if not self.ai_enabled:
                info("🤖 AI disabled - using default allocation strategy")
                return self._execute_default_gains_reallocation(gains_amount)
            
            # Get AI decision
            decision = self._get_ai_allocation_decision(gains_amount)
            
            if decision.get('error'):
                warning("🤖 AI decision failed - using default strategy")
                return self._execute_default_gains_reallocation(gains_amount)
            
            # Convert recommended amount to SOL
            conversion_amount = decision.get('convert_to_sol_amount', gains_amount * 0.5)
            conversion_amount = min(conversion_amount, gains_amount)
            
            info(f"🤖 AI Decision: Convert ${conversion_amount:.2f} to SOL")
            
            if conversion_amount > 10:  # Minimum $10 to execute
                if self._swap_usdc_to_sol(conversion_amount):
                    # Transfer to external wallets
                    external_allocation_pct = decision.get('external_wallet_pct', REALLOCATION_EXTERNAL_PCT)
                    external_amount = conversion_amount * external_allocation_pct
                    
                    if external_amount > 5:  # Minimum $5 for external transfer
                        info(f"🤖 AI Decision: Transfer ${external_amount:.2f} ({external_allocation_pct*100:.1f}%) to external wallet")
                        self._transfer_to_external_wallet(external_amount)
                    
                    return True
            
            return False
            
        except Exception as e:
            error(f"Error executing AI gains reallocation: {str(e)}")
            return False
    
    def _execute_default_gains_reallocation(self, gains_amount):
        """Default gains reallocation strategy when AI is disabled"""
        try:
            # Convert 50% to SOL
            conversion_amount = gains_amount * 0.5
            info(f"📊 Default strategy: Convert ${conversion_amount:.2f} to SOL")
            
            if conversion_amount > 10:
                if self._swap_usdc_to_sol(conversion_amount):
                    # Transfer 15% to external wallet
                    external_amount = conversion_amount * REALLOCATION_EXTERNAL_PCT
                    if external_amount > 5:
                        info(f"📤 Default strategy: Transfer ${external_amount:.2f} to external wallet")
                        self._transfer_to_external_wallet(external_amount)
                    
                    return True
            
            return False
            
        except Exception as e:
            error(f"Error executing default gains reallocation: {str(e)}")
            return False
    
    # =============================================================================
    # TRADING EXECUTION METHODS
    # =============================================================================
    
    def _swap_usdc_to_sol(self, amount_usd):
        """Swap USDC to SOL using paper or live trading"""
        try:
            if PAPER_TRADING_ENABLED:
                return self._swap_usdc_to_sol_paper(amount_usd)
            else:
                return self._swap_usdc_to_sol_live(amount_usd)
        except Exception as e:
            error(f"Error swapping USDC to SOL: {str(e)}")
            return False
    
    def _swap_usdc_to_sol_paper(self, amount_usd):
        """Paper trading: USDC -> SOL with proper validation"""
        try:
            sol_price = self.price_service.get_price(SOL_ADDRESS)
            if not sol_price or (isinstance(sol_price, dict) or float(sol_price) <= 0):
                error("❌ No valid SOL price available")
                return False
            
            sol_amount = amount_usd / sol_price
            
            # Check if we have enough USDC before attempting trade
            try:
                from src.paper_trading import get_paper_portfolio
                portfolio_df = get_paper_portfolio()
                usdc_row = portfolio_df[portfolio_df['token_address'] == USDC_ADDRESS]
                
                if usdc_row.empty:
                    error("❌ No USDC balance in paper portfolio")
                    return False
                
                available_usdc = float(usdc_row.iloc[0]['amount'])
                if available_usdc < amount_usd:
                    error(f"❌ Insufficient USDC balance: ${available_usdc:.2f} available, ${amount_usd:.2f} needed")
                    return False
                
                info(f"📊 Paper trading: Converting ${amount_usd:.2f} USDC to {sol_amount:.6f} SOL")
                
            except Exception as e:
                error(f"❌ Error checking USDC balance: {e}")
                return False
            
            # Sell USDC
            success1 = paper_trading.execute_paper_trade(
                token_address=USDC_ADDRESS,
                action="SELL",
                amount=amount_usd,
                price=1.0,
                agent="harvesting"
            )
            
            if not success1:
                error("❌ Paper trading USDC sell failed")
                return False
            
            # Buy SOL
            success2 = paper_trading.execute_paper_trade(
                token_address=SOL_ADDRESS,
                action="BUY",
                amount=sol_amount,
                price=sol_price,
                agent="harvesting"
            )
            
            if success2:
                info(f"📊 Paper trading: Swapped ${amount_usd:.2f} USDC → {sol_amount:.6f} SOL")
                return True
            else:
                error("❌ Paper trading SOL buy failed")
                return False
                
        except Exception as e:
            error(f"Error in paper trading USDC to SOL swap: {str(e)}")
            return False
    
    def _swap_usdc_to_sol_live(self, amount_usd):
        """Live trading: USDC -> SOL via Jupiter"""
        try:
            sol_price = self.price_service.get_price(SOL_ADDRESS)
            if not sol_price or (isinstance(sol_price, dict) or float(sol_price) <= 0):
                error("❌ No valid SOL price available")
                return False
            
            expected_sol = amount_usd / sol_price
            
            info(f"💱 Live trading: Swapping ${amount_usd:.2f} USDC to ~{expected_sol:.6f} SOL")
            
            # Use shared API manager for Jupiter swap
            success = self.api_manager.swap_tokens(
                input_mint=USDC_ADDRESS,
                output_mint=SOL_ADDRESS,
                amount_usd=amount_usd,
                slippage_bps=CONVERSION_SLIPPAGE_BPS,
                priority_fee=REBALANCING_PRIORITY_FEE
            )
            
            if success:
                info(f"✅ Live trading: USDC to SOL swap completed: ${amount_usd:.2f} → ~{expected_sol:.6f} SOL")
                return True
            else:
                error(f"❌ Live trading: USDC to SOL swap failed: ${amount_usd:.2f}")
                return False
                
        except Exception as e:
            error(f"Error in live trading USDC to SOL swap: {str(e)}")
            return False
    
    def _swap_sol_to_usdc(self, sol_amount_usd):
        """Swap SOL to USDC using paper or live trading"""
        try:
            # Check with coordinator if SOL is reserved for DeFi
            from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
            coordinator = get_simple_agent_coordinator()
            
            # Get SOL price to convert USD to SOL amount
            sol_price = self.price_service.get_price(SOL_ADDRESS)
            if not sol_price or (isinstance(sol_price, dict) or float(sol_price) <= 0):
                error("❌ No valid SOL price available")
                return False
            
            sol_amount = sol_amount_usd / sol_price
            
            # Check if this trade would violate DeFi reserves
            if not coordinator.can_trade_token(SOL_ADDRESS, sol_amount):
                warning(f"🚫 Cannot swap {sol_amount:.4f} SOL - would violate DeFi reserves")
                warning(f"   Requested: ${sol_amount_usd:.2f} USD worth of SOL")
                return False
            
            if PAPER_TRADING_ENABLED:
                return self._swap_sol_to_usdc_paper(sol_amount_usd)
            else:
                return self._swap_sol_to_usdc_live(sol_amount_usd)
        except Exception as e:
            error(f"Error swapping SOL to USDC: {str(e)}")
            return False
    
    def _swap_sol_to_usdc_paper(self, sol_amount_usd):
        """Paper trading: SOL -> USDC with proper validation"""
        try:
            sol_price = self.price_service.get_price(SOL_ADDRESS)
            if not sol_price or (isinstance(sol_price, dict) or float(sol_price) <= 0):
                error("❌ No valid SOL price available")
                return False
            
            sol_amount = sol_amount_usd / sol_price
            
            # Check if we have enough SOL before attempting trade
            try:
                from src.paper_trading import get_paper_portfolio
                portfolio_df = get_paper_portfolio()
                sol_row = portfolio_df[portfolio_df['token_address'] == SOL_ADDRESS]
                
                if sol_row.empty:
                    error("❌ No SOL balance in paper portfolio")
                    return False
                
                available_sol = float(sol_row.iloc[0]['amount'])
                if available_sol < sol_amount:
                    error(f"❌ Insufficient SOL balance: {available_sol:.6f} available, {sol_amount:.6f} needed")
                    return False
                
                info(f"📊 Paper trading: Converting {sol_amount:.6f} SOL to ${sol_amount_usd:.2f} USDC")
                
            except Exception as e:
                error(f"❌ Error checking SOL balance: {e}")
                return False
            
            # Sell SOL
            success1 = paper_trading.execute_paper_trade(
                token_address=SOL_ADDRESS,
                action="SELL",
                amount=sol_amount,
                price=sol_price,
                agent="harvesting"
            )
            
            if not success1:
                error("❌ Paper trading SOL sell failed")
                return False
            
            # Buy USDC
            success2 = paper_trading.execute_paper_trade(
                token_address=USDC_ADDRESS,
                action="BUY",
                amount=sol_amount_usd,
                price=1.0,
                agent="harvesting"
            )
            
            if success2:
                info(f"📊 Paper trading: Swapped {sol_amount:.6f} SOL → ${sol_amount_usd:.2f} USDC")
                return True
            else:
                error("❌ Paper trading USDC buy failed")
                return False
                
        except Exception as e:
            error(f"Error in paper trading SOL to USDC swap: {str(e)}")
            return False
    
    def _swap_sol_to_usdc_live(self, sol_amount_usd):
        """Live trading: SOL -> USDC via Jupiter"""
        try:
            sol_price = self.price_service.get_price(SOL_ADDRESS)
            if not sol_price or (isinstance(sol_price, dict) or float(sol_price) <= 0):
                error("❌ No valid SOL price available")
                return False
            
            sol_amount = sol_amount_usd / sol_price
            
            info(f"💱 Live trading: Swapping {sol_amount:.6f} SOL to ~${sol_amount_usd:.2f} USDC")
            
            # Use nice_funcs for SOL to USDC swap
            from src import nice_funcs as n
            lamports = int(max(sol_amount, 0.0) * 1_000_000_000)
            if lamports <= 0:
                warning("SOL amount too small for swap")
                return False
            
            sig = n.market_sell(SOL_ADDRESS, lamports, CONVERSION_SLIPPAGE_BPS, allow_excluded=True, agent="harvesting_agent")
            
            if sig:
                info(f"✅ Live trading: SOL to USDC swap completed: {sol_amount:.6f} SOL → ~${sol_amount_usd:.2f} USDC")
                return True
            else:
                error(f"❌ Live trading: SOL to USDC swap failed: {sol_amount:.6f} SOL")
                return False
                
        except Exception as e:
            error(f"Error in live trading SOL to USDC swap: {str(e)}")
            return False
    
    def _sell_positions_for_usdc(self, target_usdc_amount):
        """Sell positions to raise USDC reserves"""
        try:
            if PAPER_TRADING_ENABLED:
                return self._sell_positions_for_usdc_paper(target_usdc_amount)
            else:
                return self._sell_positions_for_usdc_live(target_usdc_amount)
        except Exception as e:
            error(f"Error selling positions for USDC: {str(e)}")
            return False
    
    def _sell_positions_for_usdc_paper(self, target_usdc_amount):
        """Paper trading: Sell positions for USDC"""
        try:
            info(f"📊 Paper trading: Selling positions to raise ${target_usdc_amount:.2f} USDC")
            
            # Get wallet data
            wallet_data = self.data_coordinator.get_wallet_data(config.address)
            if not wallet_data:
                error("❌ No wallet data available")
                return False
            
            # Find eligible positions
            eligible_positions = []
            for token_address, balance in wallet_data.tokens.items():
                if (token_address not in EXCLUDED_TOKENS and 
                    token_address not in [SOL_ADDRESS, USDC_ADDRESS] and 
                    balance > 0):
                    
                    price = self.price_service.get_price(token_address)
                    if price and price > 0:
                        usd_value = balance * price
                        if usd_value >= 10:  # Minimum $10 position
                            eligible_positions.append({
                                'address': token_address,
                                'symbol': token_address[:8],
                                'usd_value': usd_value,
                                'amount': balance,
                                'price': price
                            })
            
            if not eligible_positions:
                info("📊 No eligible positions found for selling")
                return False
            
            # Sort by value (highest first)
            eligible_positions.sort(key=lambda x: x['usd_value'], reverse=True)
            
            total_sold = 0.0
            for position in eligible_positions:
                if total_sold >= target_usdc_amount:
                    break
                
                needed = min(target_usdc_amount - total_sold, position['usd_value'])
                sell_percentage = needed / position['usd_value']
                
                if sell_percentage > 0.95:
                    sell_percentage = 1.0
                
                # Execute paper trading sale
                sell_amount = position['amount'] * sell_percentage
                success = paper_trading.execute_paper_trade(
                    token_address=position['address'],
                    action="SELL",
                    amount=sell_amount,
                    price=position['price'],
                    agent="harvesting"
                )
                
                if success:
                    total_sold += needed
                    info(f"📊 Paper trading: Sold {position['symbol']} - ${needed:.2f}")
                else:
                    error(f"❌ Paper trading: Failed to sell {position['symbol']}")
            
            if total_sold > 0:
                info(f"📊 Paper trading: Total sold ${total_sold:.2f} worth of positions")
                return True
            else:
                warning("📊 Paper trading: No positions sold")
                return False
                
        except Exception as e:
            error(f"Error in paper trading position sale: {str(e)}")
            return False
    
    def _sell_positions_for_usdc_live(self, target_usdc_amount):
        """Live trading: Sell positions for USDC"""
        try:
            info(f"💱 Live trading: Selling positions to raise ${target_usdc_amount:.2f} USDC")
            
            # Get wallet data
            wallet_data = self.data_coordinator.get_wallet_data(config.address)
            if not wallet_data:
                error("❌ No wallet data available")
                return False
            
            # Find eligible positions
            eligible_positions = []
            for token_address, balance in wallet_data.tokens.items():
                if (token_address not in EXCLUDED_TOKENS and 
                    token_address not in [SOL_ADDRESS, USDC_ADDRESS] and 
                    balance > 0):
                    
                    price = self.price_service.get_price(token_address)
                    if price and price > 0:
                        usd_value = balance * price
                        if usd_value >= 10:  # Minimum $10 position
                            eligible_positions.append({
                                'address': token_address,
                                'symbol': token_address[:8],
                                'usd_value': usd_value,
                                'amount': balance,
                                'price': price
                            })
            
            if not eligible_positions:
                info("💱 No eligible positions found for selling")
                return False
            
            # Sort by value (highest first)
            eligible_positions.sort(key=lambda x: x['usd_value'], reverse=True)
            
            total_sold = 0.0
            for position in eligible_positions:
                if total_sold >= target_usdc_amount:
                    break
                
                needed = min(target_usdc_amount - total_sold, position['usd_value'])
                sell_percentage = needed / position['usd_value']
                
                if sell_percentage > 0.95:
                    sell_percentage = 1.0
                
                # Execute live trading sale using nice_funcs
                try:
                    from src import nice_funcs as n
                    nf = n
                    
                    if sell_percentage >= 0.99:
                        success = nf.chunk_kill(position['address'])
                    else:
                        success = nf.partial_kill(
                            position['address'], 
                            sell_percentage, 
                            config.max_usd_order_size,
                            config.slippage
                        )
                    
                    if success:
                        total_sold += needed
                        info(f"💱 Live trading: Sold {position['symbol']} - ${needed:.2f}")
                        time.sleep(2)  # Brief pause between sales
                    else:
                        error(f"❌ Live trading: Failed to sell {position['symbol']}")
                        
                except Exception as e:
                    error(f"Error selling {position['symbol']}: {str(e)}")
            
            if total_sold > 0:
                info(f"💱 Live trading: Total sold ${total_sold:.2f} worth of positions")
                return True
            else:
                warning("💱 Live trading: No positions sold")
                return False
                
        except Exception as e:
            error(f"Error in live trading position sale: {str(e)}")
            return False
    
    # =============================================================================
    # AI DECISION MAKING
    # =============================================================================
    
    def _get_ai_allocation_decision(self, gains_amount):
        """Get AI decision for gains allocation strategy"""
        try:
            # Get current portfolio state
            current_balance = self.get_portfolio_value()
            
            # Get chart sentiment data only (no Twitter sentiment)
            market_sentiment_data = self._get_chart_sentiment_data()
            
            # Prepare portfolio data for AI
            portfolio_data = f"""
Current Portfolio State:
- Total Balance: ${current_balance:.2f}
- Realized Gains: ${gains_amount:.2f}
- Trigger: realized_gains_reallocation
"""
            
            # Format the AI prompt with current data
            prompt = HARVESTING_AI_PROMPT.format(
                portfolio_data=portfolio_data,
                realized_gains_total=gains_amount,
                unrealized_gains_total=0.0,
                current_balance=current_balance,
                peak_balance=current_balance,  # Use current as peak for simplicity
                trigger_type="realized_gains_reallocation",
                market_sentiment_data=market_sentiment_data,
                reallocation_sol_pct=REALLOCATION_EXTERNAL_PCT*100,  # Use external % as SOL %
                reallocation_staked_sol_pct=0.0,
                reallocation_usdc_pct=(1-REALLOCATION_EXTERNAL_PCT)*100,
                reallocation_external_pct=REALLOCATION_EXTERNAL_PCT*100
            )
            
            # Get AI response
            ai_response = self._get_ai_response(prompt)
            
            # Parse the response
            decision = self._parse_ai_decision(ai_response)
            
            # Log the decision with chart sentiment context
            chart_sentiment = self._get_latest_chart_sentiment()
            info(f"🤖 AI Allocation Decision: {decision['action']} (Confidence: {decision['confidence']}%)")
            if chart_sentiment:
                info(f"📊 Chart Sentiment: {chart_sentiment.get('overall_sentiment', 'UNKNOWN')} (Score: {chart_sentiment.get('sentiment_score', 0):.1f})")
            info(f"Reasoning: {decision['reasoning']}")
            
            return decision
            
        except Exception as e:
            error(f"Error getting AI allocation decision: {str(e)}")
            return {
                'action': 'HOLD_GAINS',
                'confidence': 0,
                'reasoning': f'Error in AI analysis: {str(e)}',
                'error': True,
                'convert_to_sol_amount': gains_amount * 0.5,
                'external_wallet_pct': REALLOCATION_EXTERNAL_PCT
            }
    
    def _get_ai_response(self, prompt):
        """Get AI response using configured model with fallback support"""
        try:
            model = HARVESTING_MODEL_OVERRIDE.lower()
            info(f"Using {HARVESTING_MODEL_OVERRIDE} for harvesting analysis...")
            
            # Try DeepSeek first (default)
            if self.deepseek_client and model in ["deepseek-chat", "deepseek-reasoner"]:
                response = self.deepseek_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are Anarcho Capital's Harvesting Agent. Analyze gains and make harvesting decisions."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.ai_max_tokens,
                    temperature=self.ai_temperature,
                    stream=False
                )
                response_text = response.choices[0].message.content.strip()
                debug(f"Raw AI response: {response_text}")
                
            # Try Claude as fallback
            elif self.claude_client and model in ["claude-3-haiku-20240307", "claude-3-sonnet-20240229", "claude-3-opus-20240229"]:
                response = self.claude_client.messages.create(
                    model=model,
                    max_tokens=self.ai_max_tokens,
                    temperature=self.ai_temperature,
                    system="You are Anarcho Capital's Harvesting Agent. Analyze gains and make harvesting decisions.",
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text.strip()
                debug(f"Raw AI response: {response_text}")
                
            # Try OpenAI as fallback
            elif self.openai_client and model in ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]:
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are Anarcho Capital's Harvesting Agent. Analyze gains and make harvesting decisions."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.ai_max_tokens,
                    temperature=self.ai_temperature,
                    stream=False
                )
                response_text = response.choices[0].message.content.strip()
                debug(f"Raw AI response: {response_text}")
                
            else:
                # No AI clients available
                info("No AI clients available for harvesting analysis")
                raise ValueError("No AI clients available")
            
            # Handle TextBlock format if using Claude
            if 'TextBlock' in response_text:
                match = re.search(r"text='([^']*)'", response_text)
                if match:
                    response_text = match.group(1)
            
            # Validate response quality
            if not response_text or len(response_text.strip()) < 10:
                warning("🤖 AI returned empty or very short response")
                return "HOLD_GAINS\nAI response was empty or too short - using conservative approach\nConfidence: 25%"
            
            # Check for common error patterns
            error_patterns = [
                "error", "failed", "timeout", "unavailable", "rate limit", 
                "quota exceeded", "invalid", "unauthorized"
            ]
            
            response_lower = response_text.lower()
            for pattern in error_patterns:
                if pattern in response_lower:
                    warning(f"🤖 AI response contains error pattern '{pattern}'")
                    return "HOLD_GAINS\nAI response indicates error - using conservative approach\nConfidence: 25%"
            
            return response_text
            
        except Exception as e:
            error(f"Error getting AI response: {str(e)}")
            return "HOLD_GAINS\nAI analysis failed - using conservative fallback\nConfidence: 25%"
    
    def _parse_ai_decision(self, ai_response):
        """Parse AI response into structured decision"""
        try:
            response_text = ai_response.strip()
            lines = [line.strip() for line in response_text.split('\n') if line.strip()]
            
            if not lines:
                return self._create_fallback_decision("Empty AI response")
            
            action_line = lines[0].upper()
            valid_actions = ['HARVEST_ALL', 'HARVEST_PARTIAL', 'HARVEST_SELECTIVE', 'HOLD_GAINS', 'REALLOCATE_ONLY']
            action = 'HOLD_GAINS'
            
            for valid_action in valid_actions:
                if valid_action in action_line:
                    action = valid_action
                    break
            
            confidence = 50
            confidence_patterns = [
                r'confidence[:\s]*(\d+)%', r'confidence[:\s]*(\d+)',
                r'(\d+)%\s*confidence', r'(\d+)\s*confidence'
            ]
            
            for line in lines:
                line_lower = line.lower()
                if 'confidence' in line_lower and '%' in line:
                    for pattern in confidence_patterns:
                        match = re.search(pattern, line_lower)
                        if match:
                            confidence = min(100, max(0, int(match.group(1))))
                            break
                    if confidence != 50:
                        break
            
            reasoning_lines = []
            skip_keywords = ['confidence', 'action', 'decision']
            
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                if any(keyword in line.lower() for keyword in skip_keywords):
                    continue
                reasoning_lines.append(line)
            
            reasoning = ' '.join(reasoning_lines) if reasoning_lines else "No reasoning provided"
            
            # Extract conversion and allocation amounts from reasoning
            convert_to_sol_amount = 0.5  # Default 50%
            external_wallet_pct = REALLOCATION_EXTERNAL_PCT  # Default from config
            
            # Look for dollar amounts first (more specific), then percentage patterns
            dollar_match = re.search(r'convert.*?\$(\d+(?:\.\d+)?)', reasoning.lower())
            if dollar_match:
                convert_to_sol_amount = float(dollar_match.group(1))
            elif 'convert' in reasoning.lower() and '%' in reasoning:
                convert_match = re.search(r'convert.*?(\d+)%', reasoning.lower())
                if convert_match:
                    convert_to_sol_amount = int(convert_match.group(1)) / 100
            
            if 'external' in reasoning.lower() and '%' in reasoning:
                external_match = re.search(r'external.*?(\d+)%', reasoning.lower())
                if external_match:
                    external_wallet_pct = int(external_match.group(1)) / 100
            
            return {
                'action': action,
                'confidence': confidence,
                'reasoning': reasoning,
                'convert_to_sol_amount': convert_to_sol_amount,
                'external_wallet_pct': external_wallet_pct,
                'error': False
            }
            
        except Exception as e:
            error(f"Error parsing AI decision: {str(e)}")
            return self._create_fallback_decision(f"Parse error: {str(e)}")
    
    def _create_fallback_decision(self, reason):
        """Create fallback decision when AI fails - more conservative approach"""
        return {
            'action': 'HOLD_GAINS',
            'confidence': 25,  # Lower confidence for fallback decisions
            'reasoning': f'Conservative fallback: {reason}. Using default strategy with realistic amounts.',
            'convert_to_sol_amount': 0.5,  # 50% default
            'external_wallet_pct': REALLOCATION_EXTERNAL_PCT,
            'error': True,
            'fallback': True
        }
    
    def get_portfolio_value(self):
        """Get current portfolio value from portfolio tracker"""
        try:
            if self.portfolio_tracker and hasattr(self.portfolio_tracker, 'current_snapshot'):
                snapshot = self.portfolio_tracker.current_snapshot
                if snapshot:
                    return snapshot.total_value_usd
                else:
                    debug("No current snapshot available")
                    return 0.0
            else:
                debug("Portfolio tracker not available")
                return 0.0
        except Exception as e:
            error(f"Error getting portfolio value: {str(e)}")
            return 0.0
    
    # =============================================================================
    # EXTERNAL WALLET TRANSFERS
    # =============================================================================
    
    def _transfer_to_external_wallet(self, amount_usd):
        """Transfer SOL to external wallet"""
        try:
            if not EXTERNAL_WALLET_ENABLED:
                info(f"📤 External wallet transfers disabled - logging transfer: ${amount_usd:.2f}")
                self.external_wallet_transfers.append({
                    'timestamp': datetime.now().isoformat(),
                    'amount_usd': amount_usd,
                    'status': 'disabled'
                })
                return True
            
            if not EXTERNAL_WALLET_1:
                warning("❌ External wallet address not configured")
                self.external_wallet_transfers.append({
                    'timestamp': datetime.now().isoformat(),
                    'amount_usd': amount_usd,
                    'status': 'no_address'
                })
                return False
            
            # Get current SOL price
            sol_price = self.price_service.get_price(SOL_ADDRESS)
            if not sol_price or (isinstance(sol_price, dict) or float(sol_price) <= 0):
                error("❌ No valid SOL price available")
                return False
            
            # Calculate SOL amount to transfer
            sol_amount = amount_usd / sol_price
            
            # Minimum SOL transfer amount (0.001 SOL)
            if sol_amount < 0.001:
                warning(f"❌ Transfer amount too small: {sol_amount:.6f} SOL (minimum: 0.001 SOL)")
                self.external_wallet_transfers.append({
                    'timestamp': datetime.now().isoformat(),
                    'amount_usd': amount_usd,
                    'sol_amount': sol_amount,
                    'status': 'amount_too_small'
                })
                return False
            
            if PAPER_TRADING_ENABLED:
                # Paper trading: simulate SOL transfer
                info(f"📤 Paper trading: Transferring {sol_amount:.6f} SOL (${amount_usd:.2f}) to {EXTERNAL_WALLET_1[:8]}...")
                
                self.external_wallet_transfers.append({
                    'timestamp': datetime.now().isoformat(),
                    'amount_usd': amount_usd,
                    'sol_amount': sol_amount,
                    'sol_price': sol_price,
                    'wallet_address': EXTERNAL_WALLET_1,
                    'status': 'paper_trading_simulated'
                })
                return True
            else:
                # Live trading: execute actual SOL transfer
                info(f"📤 Live trading: Transferring {sol_amount:.6f} SOL (${amount_usd:.2f}) to {EXTERNAL_WALLET_1[:8]}...")
                
                # Execute SOL transfer using shared API manager
                success = self._execute_sol_transfer(sol_amount, EXTERNAL_WALLET_1)
                
                if success:
                    self.external_wallet_transfers.append({
                        'timestamp': datetime.now().isoformat(),
                        'amount_usd': amount_usd,
                        'sol_amount': sol_amount,
                        'sol_price': sol_price,
                        'wallet_address': EXTERNAL_WALLET_1,
                        'status': 'completed'
                    })
                    info(f"✅ SOL transfer completed: {sol_amount:.6f} SOL to {EXTERNAL_WALLET_1[:8]}...")
                    return True
                else:
                    self.external_wallet_transfers.append({
                        'timestamp': datetime.now().isoformat(),
                        'amount_usd': amount_usd,
                        'sol_amount': sol_amount,
                        'sol_price': sol_price,
                        'wallet_address': EXTERNAL_WALLET_1,
                        'status': 'failed'
                    })
                    error(f"❌ SOL transfer failed: {sol_amount:.6f} SOL to {EXTERNAL_WALLET_1[:8]}...")
                    return False
            
        except Exception as e:
            error(f"Error transferring to external wallet: {str(e)}")
            return False
    
    def _execute_sol_transfer(self, sol_amount, destination_address):
        """Execute SOL transfer (paper or live based on config)"""
        if PAPER_TRADING_ENABLED:
            return self._execute_sol_transfer_paper(sol_amount, destination_address)
        else:
            return self._execute_sol_transfer_live(sol_amount, destination_address)
    
    def _execute_sol_transfer_paper(self, sol_amount, destination_address):
        """Execute paper SOL transfer"""
        try:
            info(f"📝 [PAPER] SOL transfer: {sol_amount:.6f} SOL to {destination_address[:8]}...")
            
            # Record the transfer for tracking
            self.external_wallet_transfers.append({
                'timestamp': datetime.now(),
                'amount_sol': sol_amount,
                'destination': destination_address,
                'type': 'paper_transfer',
                'status': 'success'
            })
            
            return True
            
        except Exception as e:
            error(f"Error executing paper SOL transfer: {str(e)}")
            return False
    
    def _execute_sol_transfer_live(self, sol_amount, destination_address):
        """Execute live SOL transfer using shared API manager"""
        try:
            # Use shared API manager for SOL transfer
            success = self.api_manager.transfer_sol(
                amount=sol_amount,
                destination_address=destination_address,
                priority_fee=REBALANCING_PRIORITY_FEE
            )
            
            if success:
                info(f"✅ SOL transfer executed: {sol_amount:.6f} SOL to {destination_address[:8]}...")
                
                # Record the transfer for tracking
                self.external_wallet_transfers.append({
                    'timestamp': datetime.now(),
                    'amount_sol': sol_amount,
                    'destination': destination_address,
                    'type': 'live_transfer',
                    'status': 'success'
                })
                
                return True
            else:
                error(f"❌ SOL transfer failed: {sol_amount:.6f} SOL to {destination_address[:8]}...")
                
                # Record the failed transfer
                self.external_wallet_transfers.append({
                    'timestamp': datetime.now(),
                    'amount_sol': sol_amount,
                    'destination': destination_address,
                    'type': 'live_transfer',
                    'status': 'failed'
                })
                
                return False
                
        except Exception as e:
            error(f"Error executing live SOL transfer: {str(e)}")
            
            # Record the error
            self.external_wallet_transfers.append({
                'timestamp': datetime.now(),
                'amount_sol': sol_amount,
                'destination': destination_address,
                'type': 'live_transfer',
                'status': 'error',
                'error': str(e)
            })
            
            return False
    
    def _get_chart_sentiment_data(self):
        """Get chart sentiment data formatted for AI prompt"""
        try:
            chart_sentiment = self._get_latest_chart_sentiment()
            if not chart_sentiment:
                return "Chart sentiment data unavailable - using neutral assessment"
            
            sentiment = chart_sentiment.get('overall_sentiment', 'NEUTRAL')
            score = chart_sentiment.get('sentiment_score', 0.0)
            confidence = chart_sentiment.get('confidence', 50.0)
            bullish_tokens = chart_sentiment.get('bullish_tokens', 0)
            bearish_tokens = chart_sentiment.get('bearish_tokens', 0)
            neutral_tokens = chart_sentiment.get('neutral_tokens', 0)
            total_tokens = chart_sentiment.get('total_tokens_analyzed', 0)
            
            return f"""
Chart Sentiment Analysis:
- Overall Sentiment: {sentiment}
- Sentiment Score: {score:.1f}/100
- Confidence: {confidence:.1f}%
- Token Analysis: {bullish_tokens} bullish, {bearish_tokens} bearish, {neutral_tokens} neutral ({total_tokens} total)
- Data Source: aggregated_market_sentiment.csv
"""
        except Exception as e:
            error(f"Error getting chart sentiment data: {e}")
            return "Chart sentiment data error - using neutral assessment"
    
    def _get_latest_chart_sentiment(self):
        """Get the latest chart sentiment from aggregated_market_sentiment.csv"""
        try:
            if not os.path.exists(HARVESTING_CHART_SENTIMENT_FILE):
                warning(f"Chart sentiment file not found: {HARVESTING_CHART_SENTIMENT_FILE}")
                return None
            
            # Read the CSV file
            df = pd.read_csv(HARVESTING_CHART_SENTIMENT_FILE)
            
            if df.empty:
                warning("Chart sentiment file is empty")
                return None
            
            # Get the most recent entry (highest timestamp)
            latest_row = df.loc[df['timestamp'].idxmax()]
            
            # Convert timestamp to datetime for age calculation
            chart_timestamp = float(latest_row['timestamp'])
            chart_datetime = datetime.fromtimestamp(chart_timestamp)
            current_time = datetime.now()
            age_minutes = (current_time - chart_datetime).total_seconds() / 60
            
            # Check data freshness
            if age_minutes > HARVESTING_MAX_CHART_DATA_AGE_MINUTES:
                warning(f"Chart sentiment data is {age_minutes:.1f} minutes old (max: {HARVESTING_MAX_CHART_DATA_AGE_MINUTES} min)")
                return None
            
            chart_data = {
                'overall_sentiment': latest_row.get('overall_sentiment', 'NEUTRAL'),
                'sentiment_score': float(latest_row.get('sentiment_score', 0.0)),
                'confidence': float(latest_row.get('confidence', 50.0)),
                'timestamp': chart_timestamp,
                'bullish_tokens': int(latest_row.get('bullish_tokens', 0)),
                'bearish_tokens': int(latest_row.get('bearish_tokens', 0)),
                'neutral_tokens': int(latest_row.get('neutral_tokens', 0)),
                'total_tokens_analyzed': int(latest_row.get('total_tokens_analyzed', 0)),
                'age_minutes': age_minutes
            }
            
            debug(f"📊 Chart sentiment: {chart_data['overall_sentiment']} (Score: {chart_data['sentiment_score']:.1f}, Confidence: {chart_data['confidence']:.1f}%)")
            return chart_data
            
        except Exception as e:
            error(f"Error reading chart sentiment file: {e}")
            return None
    
    def stop(self):
        """Stop the harvesting agent gracefully"""
        try:
            info("🛑 Stopping Harvesting Agent...")
            self.running = False
            info("✅ Harvesting Agent stopped")
        except Exception as e:
            error(f"Error stopping harvesting agent: {str(e)}")
    
    def get_harvesting_metrics_summary(self):
        """Get summary of harvesting metrics"""
        try:
            return {
                'realized_gains_total': self.realized_gains_total,
                'external_wallet_transfers': len(self.external_wallet_transfers),
                'ai_enabled': self.ai_enabled,
                'paper_trading': PAPER_TRADING_ENABLED,
                'last_interval_check': self.last_interval_check,
                'external_wallet_enabled': EXTERNAL_WALLET_ENABLED
            }
        except Exception as e:
            error(f"Error getting harvesting metrics: {str(e)}")
            return {}


# Global singleton instance
_harvesting_agent_instance = None

def get_harvesting_agent():
    """Get the singleton harvesting agent instance"""
    global _harvesting_agent_instance
    if _harvesting_agent_instance is None:
        _harvesting_agent_instance = HarvestingAgent(enable_ai=True)
    return _harvesting_agent_instance


def main():
    """Main function for testing the harvesting agent"""
    try:
        info("🌾 Starting Simplified Harvesting Agent Test")
        agent = HarvestingAgent(enable_ai=True)
        
        # Test initialization
        info("✅ Agent initialized successfully")
        
        # Test metrics
        metrics = agent.get_harvesting_metrics_summary()
        info(f"📊 Agent metrics: {metrics}")
        
        # Test portfolio value
        portfolio_value = agent.get_portfolio_value()
        info(f"💰 Portfolio value: ${portfolio_value:.2f}")
        
        info("🌾 Simplified Harvesting Agent test completed successfully")
        
    except Exception as e:
        critical(f"Main error: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
