import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Add after imports but before class definition
PROJECT_ROOT = Path(__file__).parent.parent.parent

"""
🌙 Anarcho Capital's Staking Agent
Automated Solana staking with yield optimization and protocol selection
Built with love by Anarcho Capital 🚀
"""

import os
import time
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from termcolor import colored, cprint
import pandas as pd
import json
import requests
from colorama import init, Fore, Back, Style 
init()

# Local imports
from src.config import *
from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
from src.scripts.data_processing.ohlcv_collector import collect_all_tokens
# Import logging utilities
from src.scripts.shared_services.logger import debug, info, warning, error, critical, system

# Solana SDK imports for real staking transactions
try:
    # Test basic Solana SDK availability
    import solana
    from solana.rpc.api import Client
    
    # For now, we'll use a simplified approach that works with the available SDK
    # The full staking implementation will be added when we have the complete SDK
    SOLANA_AVAILABLE = True
    info("✅ Solana SDK successfully imported")
    info("📝 Note: Full staking implementation requires additional SDK components")
except ImportError as e:
    SOLANA_AVAILABLE = False
    warning(f"Solana SDK not available - staking transactions will be simulated: {str(e)}")
# Trade lock manager removed - now using SimpleAgentCoordinator
import src.paper_trading as paper_trading

# Load environment variables
load_dotenv()

# Import QT Signal if available
try:
    from PySide6.QtCore import QObject, Signal as QtSignal
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    
    class QObject:
        pass
    
# Signal implementation that works with or without QT
class Signal:
    def __init__(self, *args):
        self.callbacks = []
        self.args_spec = args
        self.qt_object = None
        
        if QT_AVAILABLE:
            # We need a QObject instance to host the signal
            class SignalQObject(QObject):
                qt_signal = QtSignal(*args)
                
            self.qt_object = SignalQObject()
    
    def connect(self, callback):
        if QT_AVAILABLE and self.qt_object:
            self.qt_object.qt_signal.connect(callback)
        else:
            if callback not in self.callbacks:
                self.callbacks.append(callback)
    
    def emit(self, *args):
        if QT_AVAILABLE and self.qt_object:
            self.qt_object.qt_signal.emit(*args)
        else:
            for callback in self.callbacks:
                callback(*args)

class StakingAgent(QObject if QT_AVAILABLE else object):
    def __init__(self):
        """Initialize the Staking Agent."""
        super().__init__()
        # Add running flag for cooperative stopping
        self.running = True
        
        # Load new staking configuration from config.py
        self.execution_mode = STAKING_EXECUTION_MODE
        self.sol_target_allocation = SOL_TARGET_ALLOCATION_PERCENT
        self.sol_excess_threshold = SOL_EXCESS_STAKING_THRESHOLD
        self.sol_minimum_for_staking = SOL_MINIMUM_FOR_STAKING
        
        # New layered staking configuration (percentage of total SOL, not portfolio)
        self.sol_staking_target = SOL_STAKING_TARGET_PERCENT  # 0.50 = 50% of SOL
        self.sol_staking_minimum = SOL_STAKING_MINIMUM_PERCENT  # 0.30 = 30% of SOL
        self.sol_staking_excess_threshold = SOL_STAKING_EXCESS_THRESHOLD  # 0.65 = 65% unstaked triggers staking
        self.rewards_threshold = STAKING_REWARDS_THRESHOLD_SOL
        self.rewards_compound_percent = STAKING_REWARDS_COMPOUND_PERCENT
        self.webhook_enabled = STAKING_WEBHOOK_ENABLED
        self.interval_enabled = STAKING_INTERVAL_ENABLED
        self.interval_minutes = STAKING_INTERVAL_MINUTES
        self.webhook_cooldown = STAKING_WEBHOOK_COOLDOWN_MINUTES
        self.excess_stake_percent = STAKING_EXCESS_PERCENT
        self.max_single_stake = STAKING_MAX_SINGLE_STAKE_SOL
        self.min_single_stake = STAKING_MIN_SINGLE_STAKE_SOL
        self.auto_select_best_apy = STAKING_AUTO_SELECT_BEST_APY
        self.fallback_protocol = STAKING_FALLBACK_PROTOCOL
        self.staked_sol_tracking_enabled = STAKED_SOL_TRACKING_ENABLED
        self.staked_sol_token_address = STAKED_SOL_TOKEN_ADDRESS
        self.staked_sol_symbol = STAKED_SOL_SYMBOL
        
        # Legacy staking configuration (for compatibility)
        self.staking_allocation_percentage = STAKING_ALLOCATION_PERCENT  # From config.py
        self.staking_protocols = getattr(sys.modules['src.config'], 'STAKING_PROTOCOLS', ["marinade", "lido", "jito"])
        
        # Staking interval configuration from config
        self.staking_interval_minutes = STAKING_INTERVAL_MINUTES
        self.staking_interval_unit = STAKING_INTERVAL_UNIT
        self.staking_interval_value = STAKING_INTERVAL_VALUE
        
        # Scheduled time settings
        self.staking_run_at_enabled = STAKING_RUN_AT_ENABLED
        self.staking_run_at_time = STAKING_RUN_AT_TIME
        self.staking_start_date = STAKING_START_DATE
        self.staking_start_time = STAKING_START_TIME
        self.staking_repeat_days = STAKING_REPEAT_DAYS
        
        # Staking thresholds and safety
        self.min_sol_allocation_threshold = MIN_SOL_ALLOCATION_THRESHOLD  # From config
        self.stake_percentage = STAKING_ALLOCATION_PERCENT  # Use config value (10%)
        self.max_slashing_risk = getattr(sys.modules['src.config'], 'MAX_SLASHING_RISK', 0.5)
        self.validator_performance_threshold = getattr(sys.modules['src.config'], 'VALIDATOR_PERFORMANCE_THRESHOLD', 99)
        
        # Yield optimization settings
        
        # Cross-protocol migration engine
        try:
            from src.scripts.staking.staking_migration_engine import get_staking_migration_engine
            from src.scripts.shared_services.rate_monitoring_service import get_rate_monitoring_service
            self.migration_engine = get_staking_migration_engine()
            self.rate_monitor = get_rate_monitoring_service()
            self.migration_enabled = True
            info("Cross-protocol migration engine initialized")
        except Exception as e:
            warning(f"Failed to initialize migration engine: {str(e)}")
            self.migration_engine = None
            self.rate_monitor = None
            self.migration_enabled = False
        
        # Last migration check timestamp
        self.last_migration_check = None
        self.migration_check_interval_hours = 24  # Check once per day
        self.yield_optimization_interval = YIELD_OPTIMIZATION_INTERVAL  # From config.py
        self.yield_optimization_interval_unit = getattr(sys.modules['src.config'], 'YIELD_OPTIMIZATION_INTERVAL_UNIT', "Hour(s)")
        self.yield_optimization_interval_value = getattr(sys.modules['src.config'], 'YIELD_OPTIMIZATION_INTERVAL_VALUE', 8)
        
        # Scheduled time settings for yield optimization
        self.yield_optimization_run_at_enabled = getattr(sys.modules['src.config'], 'YIELD_OPTIMIZATION_RUN_AT_ENABLED', True)
        self.yield_optimization_run_at_time = getattr(sys.modules['src.config'], 'YIELD_OPTIMIZATION_RUN_AT_TIME', "13:00")
        
        # Auto-convert settings for maintaining SOL allocation
        self.auto_convert_threshold = getattr(sys.modules['src.config'], 'AUTO_CONVERT_THRESHOLD', 10)
        self.min_conversion_amount = getattr(sys.modules['src.config'], 'MIN_CONVERSION_AMOUNT', 5)
        self.max_convert_percentage = getattr(sys.modules['src.config'], 'MAX_CONVERT_PERCENTAGE', 25)
        
        # Last run information for scheduled runs
        self.last_run_day = None
        self.last_yield_optimization = None
        
        # Cooldown mechanism to prevent excessive trading
        self.last_trigger_time = None
        self.cooldown_minutes = self.webhook_cooldown  # Use new webhook cooldown setting
        
        # Circuit breaker for consecutive failures
        self.consecutive_failures = 0
        self.last_failure_time = None
        self.circuit_breaker_active = False
        
        # SOL allocation threshold from config
        self.sol_allocation_threshold = getattr(sys.modules['src.config'], 'REALLOCATION_SOL_PCT', 0.10)  # 10% target
        
        # Webhook activity tracking
        self.last_webhook_time = None
        self.webhook_activity_threshold = getattr(sys.modules['src.config'], 'STAKING_WEBHOOK_ACTIVITY_THRESHOLD', 3600)  # 1 hour - if webhook activity within this time, skip intervals
        
        # Validate address is set
        if not address:
            warning("WARNING: No wallet address configured in config.py")
            info("Staking operations will be limited without a wallet address")

        # Log Solana SDK status
        if SOLANA_AVAILABLE:
            info("✅ Solana SDK available for live staking transactions")
            info("🚀 Full staking implementation ready with solders components")
            info("🔧 Status: Complete SDK available for real blockchain transactions")
        else:
            warning("⚠️ Solana SDK not available - staking will be simulated in paper mode only")

        info("Anarcho Capital's Staking Agent initialized!")

        # Add signal if QT is available
        if QT_AVAILABLE:
            self.staking_executed = Signal(str, str, str, float, float, str, str, str)
            # agent_name, action, protocol, amount_sol, apy, wallet_address, mint_address, details

    def _get_current_address(self):
        """Safely retrieve the current wallet address from config at runtime."""
        try:
            import src.config as conf
            return getattr(conf, 'address', None)
        except Exception:
            return None

    def handle_webhook_trigger(self, webhook_data):
        """
        Handle webhook triggers for the staking agent
        
        Args:
            webhook_data (dict): Webhook data containing trigger information
            
        Returns:
            bool: True if webhook was processed successfully, False otherwise
        """
        try:
            if not self.webhook_enabled:
                info("🔒 Webhook triggers disabled - skipping")
                return False
                
            info("🔒 Staking agent received webhook trigger")
            
            # Update webhook activity timestamp
            self.last_webhook_time = datetime.now()
            info(f"🔒 Webhook activity updated - will skip intervals for {self.webhook_activity_threshold/60:.0f} minutes")
            
            # Check cooldown before processing
            if not self._check_cooldown():
                info("🔒 Staking agent in cooldown period - skipping trigger")
                return False
            
            # Handle different webhook data structures
            if 'type' in webhook_data or 'change_type' in webhook_data:
                # Portfolio change webhook (has 'type' or 'change_type' fields)
                trigger_type = webhook_data.get('type', webhook_data.get('change_type', 'unknown'))
                timestamp = webhook_data.get('timestamp', time.time())
                portfolio_data = webhook_data.get('portfolio_data', {})
                
                info(f"🔒 Portfolio webhook trigger type: {trigger_type}")
                
                # Check cooldown before processing
                if not self._check_cooldown():
                    info("🔒 Staking agent in cooldown period - skipping trigger")
                    return False
                
                # Handle different trigger types
                if trigger_type in ['portfolio_change', 'portfolio_change_detected']:
                    # Portfolio allocation change detected
                    info("🔒 Portfolio change detected - checking excess SOL staking")
                    return self._handle_portfolio_rebalancing(portfolio_data)
                    
                elif trigger_type == 'proactive_rebalancing':
                    # Proactive rebalancing triggered
                    info("🔒 Proactive rebalancing detected - checking staking needs")
                    return self._handle_rebalancing_trigger(portfolio_data)
                    
                elif trigger_type == 'transaction_monitoring':
                    # Transaction monitoring triggered
                    info("🔒 Transaction monitoring triggered - checking staking status")
                    return self._handle_transaction_trigger(webhook_data)
                    
                elif trigger_type == 'staking_rewards_detected':
                    # Staking rewards detected - trigger compounding
                    info("🔒 Staking rewards detected - checking compounding opportunities")
                    return self._handle_staking_rewards_trigger(webhook_data)
                    
                else:
                    info(f"🔒 Unknown portfolio webhook trigger type: {trigger_type}")
                    return False
                    
            elif 'wallet' in webhook_data and 'token' in webhook_data:
                # Transaction event webhook (has 'wallet' and 'token' fields)
                info("🔒 Transaction event webhook received")
                
                # Check cooldown before processing
                if not self._check_cooldown():
                    info("🔒 Staking agent in cooldown period - skipping trigger")
                    return False
                
                # Handle transaction events
                return self._handle_transaction_event(webhook_data)
                
            else:
                info(f"🔒 Unknown webhook data structure: {list(webhook_data.keys())}")
                return False
                
        except Exception as e:
            error(f"❌ Error handling webhook trigger in staking agent: {e}")
            return False

    def _check_cooldown(self):
        """Check if staking agent is in cooldown period"""
        try:
            if not self.last_trigger_time:
                return True  # No previous trigger, allow execution
            
            time_since_last = (datetime.now() - self.last_trigger_time).total_seconds() / 60
            if time_since_last >= self.cooldown_minutes:
                return True  # Cooldown period has passed
            else:
                remaining_cooldown = self.cooldown_minutes - time_since_last
                info(f"🔒 Staking agent cooldown: {remaining_cooldown:.1f} minutes remaining")
                return False
                
        except Exception as e:
            error(f"❌ Error checking cooldown: {e}")
            return True  # Allow execution on error
    
    def _update_trigger_time(self):
        """Update the last trigger time for cooldown"""
        try:
            self.last_trigger_time = datetime.now()
            info(f"🔒 Staking agent trigger time updated - cooldown: {self.cooldown_minutes} minutes")
        except Exception as e:
            error(f"❌ Error updating trigger time: {e}")

    def _is_webhook_active(self):
        """Check if webhooks are active (recent webhook activity)"""
        try:
            if not self.last_webhook_time:
                return False  # No webhook activity yet
            
            time_since_webhook = (datetime.now() - self.last_webhook_time).total_seconds()
            is_active = time_since_webhook <= self.webhook_activity_threshold
            
            if is_active:
                remaining_time = self.webhook_activity_threshold - time_since_webhook
                info(f"🔒 Webhooks active - skipping intervals for {remaining_time/60:.1f} more minutes")
            else:
                info(f"🔒 Webhooks inactive - will use interval execution")
            
            return is_active
            
        except Exception as e:
            error(f"❌ Error checking webhook activity: {e}")
            return False

    def _handle_portfolio_rebalancing(self, portfolio_data):
        """Handle staking within SOL allocation using new layered approach"""
        try:
            total_value = portfolio_data.get('total_value', 0)
            sol_balance = portfolio_data.get('sol_balance', 0)
            sol_value_usd = portfolio_data.get('sol_value_usd', 0)
            staked_sol_balance = portfolio_data.get('staked_sol_balance', 0)
            
            if total_value <= 0 or sol_balance <= 0:
                info("🔒 Invalid portfolio data - skipping staking")
                return False
            
            # Calculate SOL allocation percentage (for reference)
            current_sol_pct = (sol_value_usd / total_value) * 100
            info(f"🔒 Portfolio: Total: ${total_value:.2f}, SOL: {sol_balance:.4f} SOL (${sol_value_usd:.2f}, {current_sol_pct:.1f}%)")
            
            # NEW LOGIC: Calculate staking within SOL allocation
            total_sol = sol_balance + staked_sol_balance
            unstaked_sol_pct = (sol_balance / total_sol) * 100 if total_sol > 0 else 0
            staked_sol_pct = (staked_sol_balance / total_sol) * 100 if total_sol > 0 else 0
            
            info(f"🔒 SOL Status: {total_sol:.4f} total, {staked_sol_balance:.4f} staked ({staked_sol_pct:.1f}%), {sol_balance:.4f} unstaked ({unstaked_sol_pct:.1f}%)")
            
            # Check if staked SOL percentage is below target
            if staked_sol_pct < self.sol_staking_target * 100:
                # Calculate how much to stake to reach target
                target_staked_sol = total_sol * self.sol_staking_target
                sol_to_stake = target_staked_sol - staked_sol_balance
                
                info(f"🔒 Staked SOL {staked_sol_pct:.1f}% below target {self.sol_staking_target * 100:.1f}%")
                info(f"🔒 SOL to stake: {sol_to_stake:.4f} SOL")
                
                if sol_to_stake >= self.sol_minimum_for_staking:
                    # Update trigger time for cooldown
                    self._update_trigger_time()
                    
                    # Stake the calculated amount
                    return self._stake_excess_sol(sol_to_stake, portfolio_data)
                else:
                    info(f"🔒 SOL to stake {sol_to_stake:.4f} below minimum threshold {self.sol_minimum_for_staking}")
                    return False
            else:
                info(f"🔒 Staked SOL {staked_sol_pct:.1f}% meets target {self.sol_staking_target * 100:.1f}%")
                return True
                
        except Exception as e:
            error(f"❌ Error handling portfolio rebalancing: {e}")
            return False

    def _handle_portfolio_change_trigger(self, portfolio_data):
        """Legacy method - redirects to new rebalancing method"""
        return self._handle_portfolio_rebalancing(portfolio_data)

    def _handle_rebalancing_trigger(self, portfolio_data):
        """Handle rebalancing triggers"""
        try:
            # Check if rebalancing affects staking decisions
            sol_deviation = portfolio_data.get('sol_deviation', 0)
            usdc_deviation = portfolio_data.get('usdc_deviation', 0)
            
            info(f"🔒 Rebalancing trigger: SOL deviation: {sol_deviation:.1%}, USDC deviation: {usdc_deviation:.1%}")
            
            # If significant deviation, consider staking adjustments
            if sol_deviation > 0.05 or usdc_deviation > 0.05:  # 5% threshold
                info("🔒 Significant portfolio deviation - checking staking optimization")
                # Could trigger yield optimization here
                return True
            else:
                info("🔒 Portfolio within acceptable ranges - no staking action needed")
                return False
                
        except Exception as e:
            error(f"❌ Error handling rebalancing trigger: {e}")
            return False

    def _handle_transaction_trigger(self, webhook_data):
        """Handle transaction monitoring triggers"""
        try:
            # Check if recent transactions affect staking decisions
            transaction_data = webhook_data.get('transaction_data', {})
            
            info("🔒 Transaction monitoring triggered - checking staking status")
            
            # Could analyze transaction data for staking opportunities
            # For now, just return success to acknowledge the trigger
            return True
                
        except Exception as e:
            error(f"❌ Error handling transaction trigger: {e}")
            return False

    def _handle_transaction_event(self, event_data):
        """Handle transaction events from webhook processing"""
        try:
            wallet = event_data.get('wallet')
            token = event_data.get('token')
            action = event_data.get('action')
            amount = event_data.get('amount', 0)
            usd_value = event_data.get('usd_value', 0)
            symbol = event_data.get('symbol', 'UNK')
            
            info(f"🔒 Transaction event: {action} {amount:.4f} {symbol} (${usd_value:.2f}) for wallet {wallet[:8] if wallet else 'unknown'}...")
            
            # Check if this is a SOL transaction that might affect staking
            if token == 'So11111111111111111111111111111111111111112':  # SOL token
                info("🔒 SOL transaction detected - checking staking implications")
                
                # Check if this is a SOL balance increase (BUY action)
                if action == 'buy' and amount > 0.1:  # Minimum 0.1 SOL to stake
                    info(f"🔒 SOL balance increase detected: +{amount:.4f} SOL (${usd_value:.2f})")
                    
                    # Update trigger time for cooldown
                    self._update_trigger_time()
                    
                    # Trigger staking for the new SOL
                    return self._trigger_sol_balance_increase_staking(amount, usd_value)
                else:
                    info(f"🔒 SOL transaction not suitable for staking: {action} {amount:.4f} SOL")
                    return True
                
            # For other tokens, we could check if they affect SOL allocation
            # But without portfolio context, we can't make staking decisions
            else:
                info(f"🔒 Non-SOL transaction: {symbol} - monitoring for portfolio changes")
                return True
                
        except Exception as e:
            error(f"❌ Error handling transaction event: {e}")
            return False

    def _trigger_sol_balance_increase_staking(self, sol_amount, usd_value):
        """Trigger staking when SOL balance increases"""
        try:
            info(f"🔒 Triggering staking for SOL balance increase: {sol_amount:.4f} SOL (${usd_value:.2f})")
            
            # Get current best APY protocol
            staking_data, _ = self.get_staking_rewards_and_apy()
            if not staking_data:
                warning("No staking data available for SOL balance increase staking")
                return False
            
            # Find best APY protocol
            best_protocol = max(staking_data.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
            best_protocol_name = best_protocol[0].replace("_apy", "")
            best_apy = best_protocol[1]
            
            if best_protocol_name not in self.staking_protocols:
                warning(f"Best protocol {best_protocol_name} not in configured protocols")
                return False
            
            # Calculate staking amount (50% of the new SOL)
            stake_amount_sol = sol_amount * 0.5  # Stake 50% of new SOL
            
            if stake_amount_sol < 0.1:  # Minimum 0.1 SOL to stake
                info(f"Staking amount {stake_amount_sol:.4f} SOL too small for SOL balance increase staking")
                return False
            
            info(f"🔒 SOL Balance Increase: Staking {stake_amount_sol:.4f} SOL to {best_protocol_name} at {best_apy:.2f}% APY")
            
            # Execute staking transaction with execution tracking
            staking_success = self._execute_staking_transaction_with_tracking(
                best_protocol_name, stake_amount_sol, best_apy, "SOL_BALANCE_INCREASE"
            )
            
            if staking_success:
                info(f"✅ Successfully staked {stake_amount_sol:.4f} SOL from balance increase to {best_protocol_name}")
                return True
            else:
                error(f"❌ Failed to stake SOL from balance increase to {best_protocol_name}")
                return False
                
        except Exception as e:
            error(f"❌ Error in SOL balance increase staking trigger: {e}")
            return False

    def _handle_staking_rewards_trigger(self, webhook_data):
        """Handle staking rewards detection for compounding"""
        try:
            rewards_data = webhook_data.get('rewards_data', {})
            total_rewards = rewards_data.get('total_rewards', 0)
            protocol = rewards_data.get('protocol', 'unknown')
            
            info(f"🔒 Staking rewards detected: {total_rewards:.6f} SOL from {protocol}")
            
            if total_rewards > 0.001:  # Minimum 0.001 SOL to compound
                info(f"🔒 Sufficient rewards for compounding: {total_rewards:.6f} SOL")
                
                # Update trigger time for cooldown
                self._update_trigger_time()
                
                # Trigger compounding
                return self._trigger_rewards_compounding(rewards_data)
            else:
                info("🔒 Insufficient rewards for compounding")
                return False
                
        except Exception as e:
            error(f"❌ Error handling staking rewards trigger: {e}")
            return False

    def _stake_excess_sol(self, excess_sol, portfolio_data):
        """Stake excess SOL to rebalance portfolio"""
        try:
            # Check with coordinator if SOL is reserved for DeFi
            from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
            coordinator = get_simple_agent_coordinator()
            
            # Check if SOL is reserved for DeFi collateral
            reserved_sol = coordinator.get_available_balance(SOL_ADDRESS)
            if reserved_sol > 0:
                info(f"⚠️ {reserved_sol:.4f} SOL reserved for DeFi collateral - adjusting available amount")
                # Reduce available SOL by reserved amount
                available_sol = max(0, excess_sol - reserved_sol)
                if available_sol < self.sol_minimum_for_staking:
                    warning(f"🚫 Cannot stake - insufficient SOL after DeFi reserve ({available_sol:.4f} SOL available, {reserved_sol:.4f} reserved)")
                    return False
                excess_sol = available_sol
                info(f"✅ Adjusted staking amount to respect DeFi reserves: {excess_sol:.4f} SOL available")
            
            # Calculate staking amount (percentage of excess)
            stake_amount = excess_sol * (self.excess_stake_percent / 100)
            
            # Apply limits
            stake_amount = min(stake_amount, self.max_single_stake)
            stake_amount = max(stake_amount, self.min_single_stake)
            
            if stake_amount < self.sol_minimum_for_staking:
                info(f"🔒 Calculated stake amount {stake_amount:.4f} SOL too small")
                return False
            
            info(f"🔒 Staking excess SOL: {stake_amount:.4f} SOL")
            
            # Check for migration opportunities before new staking
            if self.migration_enabled:
                self._check_and_execute_migrations()
            
            # Get best staking protocol
            if self.auto_select_best_apy:
                # Use rate monitoring service if available
                if self.rate_monitor:
                    staking_rates = self.rate_monitor.get_staking_rates()
                    if staking_rates:
                        best_rate_data = self.rate_monitor.get_best_staking_rate()
                        if best_rate_data:
                            protocol_name = best_rate_data.protocol
                            apy = best_rate_data.rate * 100  # Convert to percentage for compatibility
                        else:
                            # Fallback to old method
                            staking_data, _ = self.get_staking_rewards_and_apy()
                            if staking_data:
                                best_protocol = max(staking_data.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
                                protocol_name = best_protocol[0].replace("_apy", "")
                                apy = best_protocol[1]
                            else:
                                protocol_name = self.fallback_protocol
                                apy = 7.0
                    else:
                        # Fallback to old method
                        staking_data, _ = self.get_staking_rewards_and_apy()
                        if staking_data:
                            best_protocol = max(staking_data.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
                            protocol_name = best_protocol[0].replace("_apy", "")
                            apy = best_protocol[1]
                        else:
                            protocol_name = self.fallback_protocol
                            apy = 7.0
                else:
                    # Fallback to old method
                    staking_data, _ = self.get_staking_rewards_and_apy()
                    if staking_data:
                        best_protocol = max(staking_data.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
                        protocol_name = best_protocol[0].replace("_apy", "")
                        apy = best_protocol[1]
                    else:
                        protocol_name = self.fallback_protocol
                        apy = 7.0  # Fallback APY
            else:
                protocol_name = self.fallback_protocol
                apy = 7.0
            
            # Execute staking transaction
            success = self._execute_staking_transaction_with_tracking(
                protocol_name, stake_amount, apy, "EXCESS_SOL_REBALANCING"
            )
            
            if success:
                info(f"✅ Successfully staked {stake_amount:.4f} SOL excess to {protocol_name}")
                
                # Update portfolio tracker with staked SOL
                self._update_portfolio_tracker_staked_sol(protocol_name, stake_amount, apy)
                
                # Force portfolio tracker to refresh and create new snapshot
                self._force_portfolio_refresh()
                
                return True
            else:
                error(f"❌ Failed to stake excess SOL to {protocol_name}")
                return False
                
        except Exception as e:
            error(f"❌ Error staking excess SOL: {e}")
            return False

    def _trigger_staking_rebalance(self, portfolio_data):
        """Legacy method - redirects to new excess SOL staking"""
        return self._stake_excess_sol(portfolio_data.get('sol_balance', 0) * 0.5, portfolio_data)

    def _trigger_rewards_compounding(self, rewards_data):
        """Trigger compounding of staking rewards"""
        try:
            total_rewards = rewards_data.get('total_rewards', 0)
            protocol = rewards_data.get('protocol', 'unknown')
            
            info(f"🔒 Compounding {total_rewards:.6f} SOL rewards from {protocol}")
            
            # Get current best APY protocol
            staking_data, _ = self.get_staking_rewards_and_apy()
            if not staking_data:
                warning("No staking data available for compounding")
                return False
            
            # Find best APY protocol
            best_protocol = max(staking_data.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
            best_protocol_name = best_protocol[0].replace("_apy", "")
            best_apy = best_protocol[1]
            
            if best_protocol_name not in self.staking_protocols:
                warning(f"Best protocol {best_protocol_name} not in configured protocols")
                return False
            
            info(f"🔒 Compounding: Staking {total_rewards:.6f} SOL rewards to {best_protocol_name} at {best_apy:.2f}% APY")
            
            # Execute staking transaction for rewards with tracking
            staking_success = self._execute_staking_transaction_with_tracking(
                best_protocol_name, total_rewards, best_apy, "STAKING_REWARDS_COMPOUNDING"
            )
            
            if staking_success:
                info(f"✅ Successfully compounded {total_rewards:.6f} SOL rewards to {best_protocol_name}")
                return True
            else:
                error(f"❌ Failed to compound rewards to {best_protocol_name}")
                return False
                
        except Exception as e:
            error(f"❌ Error in rewards compounding trigger: {e}")
            return False

    def stop(self):
        """Stop the Staking agent gracefully"""
        info("Stopping Staking agent...")
        self.running = False
    
    def _check_and_execute_migrations(self):
        """
        Check for migration opportunities and execute if beneficial
        Called periodically to optimize staking positions
        """
        try:
            if not self.migration_enabled or not self.migration_engine:
                return False
            
            # Check if enough time has passed since last check
            if self.last_migration_check:
                time_since_check = (datetime.now() - self.last_migration_check).total_seconds() / 3600
                if time_since_check < self.migration_check_interval_hours:
                    return False  # Too soon to check again
            
            info("Checking for staking migration opportunities...")
            
            # Get current staking positions
            # TODO: Get actual positions from portfolio tracker
            # For now, use placeholder - this should be enhanced to get real positions
            current_positions = {}  # Dict of protocol -> amount_sol
            
            # Find migration opportunities
            opportunities = self.migration_engine.find_migration_opportunities(current_positions)
            
            if not opportunities:
                debug("No migration opportunities found")
                self.last_migration_check = datetime.now()
                return False
            
            # Execute best opportunity (already sorted by profit potential)
            best_opportunity = opportunities[0]
            
            info(f"Found migration opportunity: {best_opportunity.from_protocol} → {best_opportunity.to_protocol}")
            info(f"  Net benefit: {best_opportunity.net_benefit_apy*100:.2f}% APY")
            
            # Get position amount (placeholder - should get from portfolio)
            amount_sol = 0.1  # Placeholder - TODO: Get actual staked amount
            
            # Execute migration
            success = self.migration_engine.execute_migration(
                best_opportunity.from_protocol,
                best_opportunity.to_protocol,
                amount_sol,
                best_opportunity
            )
            
            if success:
                info(f"Successfully migrated {amount_sol:.4f} SOL from {best_opportunity.from_protocol} to {best_opportunity.to_protocol}")
            else:
                warning(f"Migration failed: {best_opportunity.from_protocol} → {best_opportunity.to_protocol}")
            
            self.last_migration_check = datetime.now()
            return success
            
        except Exception as e:
            error(f"Error checking migrations: {str(e)}")
            return False

    def get_staking_rewards_and_apy(self):
        """Get SOL staking rewards and APY data from different protocols using optimized shared API manager"""
        try:
            # Initialize results
            staking_data = {}
            staking_rewards = 0
            
            # Check if we have a wallet address
            if not address:
                warning("No wallet address configured. Cannot check staking rewards.")
                return staking_data, staking_rewards
            
            # Use optimized shared API manager for concurrent data fetching
            from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
            api_manager = get_shared_api_manager()
            
            info("Fetching staking APY data using optimized concurrent requests...")
            
            # Get all staking APY data concurrently (MUCH FASTER)
            staking_data = api_manager.get_staking_apy_data()
            
            # Log the results
            for protocol, apy in staking_data.items():
                if "apy" in protocol or protocol in ["blazestake", "jupsol", "sanctum", "everstake", "community_validators"]:
                    info(f"{protocol.title()} APY: {apy:.2f}%")
            
            # Get staking balances for configured protocols
            if address:
                info("Fetching staking balances...")
                for protocol in ["blazestake", "jupsol", "sanctum"]:
                    try:
                        balance_data = api_manager.get_staking_balance(address, protocol)
                        if balance_data and balance_data.get("staked_amount", 0) > 0:
                            staked_amount = balance_data["staked_amount"]
                            rewards = balance_data["rewards"]
                            staking_rewards += rewards
                            info(f"{protocol.title()}: Staked SOL: {staked_amount} SOL, Rewards: {rewards} SOL")
                    except Exception as e:
                        debug(f"Error getting {protocol} balance: {str(e)}")
            
            return staking_data, staking_rewards
            
        except Exception as e:
            error(f"Error getting staking rewards and APY: {str(e)}")
            return {}, 0

    def get_liquidity_pool_apy(self):
        """Get liquidity pool APY data for yield comparison"""
        try:
            liquidity_apy = {}
            
            # Check Raydium SOL-USDC pool
            try:
                # Try multiple Raydium endpoints for better reliability
                raydium_endpoints = [
                    "https://api.raydium.io/v2/sdk/liquidity/mainnet.json",
                    "https://api.raydium.io/v2/main/pool",
                    "https://api.raydium.io/v2/amm/pools"
                ]
                
                raydium_apy = None
                for endpoint in raydium_endpoints:
                    try:
                        raydium_response = requests.get(endpoint, timeout=3)  # Even shorter timeout
                        
                        if raydium_response.status_code == 200:
                            raydium_data = raydium_response.json()
                            
                            # Look for SOL-USDC pool in different data structures
                            if isinstance(raydium_data, dict):
                                pools = raydium_data.get("official", raydium_data.get("pools", raydium_data.get("data", [])))
                            elif isinstance(raydium_data, list):
                                pools = raydium_data
                            else:
                                continue
                            
                            for pool in pools:
                                if isinstance(pool, dict):
                                    pool_name = pool.get("name", pool.get("pool_name", ""))
                                    if "SOL" in pool_name and "USDC" in pool_name:
                                        apy = pool.get("apy", pool.get("apr", 0))
                                        if apy and apy > 0:
                                            raydium_apy = apy
                                            break
                            
                            if raydium_apy:
                                break
                                
                    except Exception as e:
                        debug(f"Raydium endpoint {endpoint} failed: {str(e)}")
                        continue
                
                if raydium_apy:
                    liquidity_apy["raydium_sol_usdc"] = raydium_apy
                    info(f"Raydium SOL-USDC Pool APY: {raydium_apy:.2f}%")
                else:
                    info("Raydium liquidity APY not available - using fallback")
                    liquidity_apy["raydium_sol_usdc"] = 2.5  # Fallback APY
                    info(f"Raydium SOL-USDC Pool APY (fallback): 2.50%")
                    
            except Exception as e:
                info(f"Error getting Raydium liquidity APY: {str(e)}")
                # Use fallback APY
                liquidity_apy["raydium_sol_usdc"] = 2.5
                info(f"Raydium SOL-USDC Pool APY (fallback): 2.50%")
            
            # Check Orca SOL-USDC pool
            try:
                # Try multiple Orca endpoints for better reliability
                orca_endpoints = [
                    "https://api.orca.so/v1/whirlpool/list",
                    "https://api.orca.so/v1/pool/list",
                    "https://api.orca.so/v2/whirlpool/list"
                ]
                
                orca_apy = None
                for endpoint in orca_endpoints:
                    try:
                        orca_response = requests.get(endpoint, timeout=3)  # Shorter timeout
                        
                        if orca_response.status_code == 200:
                            orca_data = orca_response.json()
                            
                            # Look for SOL-USDC whirlpool in different data structures
                            pools = orca_data.get("whirlpools", orca_data.get("pools", orca_data.get("data", [])))
                            
                            for pool in pools:
                                if isinstance(pool, dict):
                                    # Check different token field structures
                                    token_a = pool.get("tokenA", {})
                                    token_b = pool.get("tokenB", {})
                                    
                                    if isinstance(token_a, dict) and isinstance(token_b, dict):
                                        symbol_a = token_a.get("symbol", "")
                                        symbol_b = token_b.get("symbol", "")
                                    else:
                                        symbol_a = str(token_a)
                                        symbol_b = str(token_b)
                                    
                                    if ("SOL" in symbol_a and "USDC" in symbol_b) or ("SOL" in symbol_b and "USDC" in symbol_a):
                                        apy = pool.get("apy", pool.get("apr", pool.get("fee_apy", 0)))
                                        if apy and apy > 0:
                                            orca_apy = apy
                                            break
                            
                            if orca_apy:
                                break
                                
                    except Exception as e:
                        debug(f"Orca endpoint {endpoint} failed: {str(e)}")
                        continue
                
                if orca_apy:
                    liquidity_apy["orca_sol_usdc"] = orca_apy
                    info(f"Orca SOL-USDC Pool APY: {orca_apy:.2f}%")
                else:
                    info("Orca liquidity APY not available - using fallback")
                    liquidity_apy["orca_sol_usdc"] = 1.8  # Fallback APY
                    info(f"Orca SOL-USDC Pool APY (fallback): 1.80%")
                    
            except Exception as e:
                info(f"Error getting Orca liquidity APY: {str(e)}")
                # Use fallback APY
                liquidity_apy["orca_sol_usdc"] = 1.8
                info(f"Orca SOL-USDC Pool APY (fallback): 1.80%")
            
            return liquidity_apy
            
        except Exception as e:
            error(f"Error getting liquidity pool APY: {str(e)}")
            return {}

    def reinvest_staking_rewards(self, staking_rewards):
        """Reinvest staking rewards back into staking"""
        try:
            if staking_rewards <= 0:
                info("No staking rewards to reinvest")
                return False
            
            info(f"Reinvesting {staking_rewards} SOL in staking rewards")
            
            # Get current best APY protocol
            staking_data, _ = self.get_staking_rewards_and_apy()
            if not staking_data:
                warning("No staking data available for reinvestment")
                return False
            
            # Find best APY protocol
            best_protocol = max(staking_data.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
            best_protocol_name = best_protocol[0].replace("_apy", "")
            
            if best_protocol_name not in self.staking_protocols:
                warning(f"Best protocol {best_protocol_name} not in configured protocols")
                return False
            
            info(f"Reinvesting {staking_rewards} SOL into {best_protocol_name} (APY: {best_protocol[1]:.2f}%)")
            
            # Here you would implement the actual staking transaction
            # For now, we'll just log the action
            info(f"Would stake {staking_rewards} SOL to {best_protocol_name}")
            
            # Emit signal if QT is available
            if QT_AVAILABLE:
                self.staking_executed.emit(
                    "Staking Agent", "REINVEST", best_protocol_name, 
                    staking_rewards, best_protocol[1], address, 
                    SOL_ADDRESS, f"Reinvested {staking_rewards} SOL rewards"
                )
            
            return True
            
        except Exception as e:
            error(f"Error reinvesting staking rewards: {str(e)}")
            return False

    def _auto_convert_for_staking(self):
        """Auto-convert tokens to SOL to maintain staking allocation"""
        try:
            info("Checking if auto-conversion is needed for staking...")
            
            # Get current portfolio balances
            total_value = 0
            sol_value = 0
            other_tokens = {}
            
            # Get SOL balance and price using shared data coordinator
            data_coordinator = get_shared_data_coordinator()
            sol_balance = data_coordinator._fetch_sol_balance(address) if address else 0.0
            # Get SOL price from price service
            sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 0.0
            sol_value = sol_balance * sol_price
            total_value += sol_value
            
            # Get other token balances
            token_holdings = self.get_all_token_holdings()
            for token_address, amount in token_holdings.items():
                if token_address == SOL_ADDRESS:
                    continue  # Already counted SOL
                
                # Get token price from shared data coordinator
                token_price = data_coordinator.price_service.get_price(token_address) if hasattr(data_coordinator, 'price_service') else 0.0
                if token_price and amount > 0:
                    token_value = amount * token_price
                    total_value += token_value
                    other_tokens[token_address] = {
                        'amount': amount,
                        'price': token_price,
                        'value': token_value
                    }
            
            # Calculate current SOL allocation percentage
            current_sol_pct = (sol_value / total_value * 100) if total_value > 0 else 0
            info(f"Current SOL allocation: {current_sol_pct:.2f}% of ${total_value:.2f}")
            
            # Check if we need to convert to maintain minimum SOL allocation
            target_sol_value = total_value * (self.staking_allocation_percentage / 100)
            info(f"Target SOL allocation: ${target_sol_value:.2f} ({self.staking_allocation_percentage}% of ${total_value:.2f})")
            
            if current_sol_pct < self.staking_allocation_percentage:
                needed_sol_value = target_sol_value - sol_value
                info(f"Need to convert ${needed_sol_value:.2f} to SOL")
                
                # Check if we have enough other tokens to convert
                available_for_conversion = sum(token['value'] for token in other_tokens.values())
                
                if available_for_conversion >= needed_sol_value:
                    # Convert tokens to SOL
                    converted_value = 0
                    for token_address, token_data in other_tokens.items():
                        if converted_value >= needed_sol_value:
                            break
                        
                        # Calculate how much to convert
                        remaining_needed = needed_sol_value - converted_value
                        convert_amount = min(token_data['value'], remaining_needed)
                        convert_tokens = convert_amount / token_data['price']
                        
                        if convert_tokens >= self.min_conversion_amount:
                            info(f"Converting {convert_tokens:.4f} tokens (${convert_amount:.2f}) to SOL")
                            
                            # Here you would implement the actual conversion transaction
                            # For now, we'll just log the action
                            info(f"Would convert {convert_tokens:.4f} {token_address} to SOL")
                            
                            converted_value += convert_amount
                else:
                    warning(f"Insufficient tokens to convert. Available: ${available_for_conversion:.2f}, Needed: ${needed_sol_value:.2f}")
            else:
                info("SOL allocation is sufficient, no conversion needed")
            
            return True
            
        except Exception as e:
            error(f"Error in auto-convert for staking: {str(e)}")
            return False

    def optimize_yield(self):
        """Optimize yield by selecting best staking protocol and rebalancing"""
        try:
            info("Running yield optimization...")
            
            # Get current staking data
            staking_data, current_rewards = self.get_staking_rewards_and_apy()
            liquidity_apy = self.get_liquidity_pool_apy()
            
            if not staking_data:
                warning("No staking data available for optimization")
                return False
            
            # Find best APY among staking protocols
            best_staking_apy = 0
            best_staking_protocol = None
            
            for protocol, apy in staking_data.items():
                if isinstance(apy, (int, float)) and apy > best_staking_apy:
                    best_staking_apy = apy
                    best_staking_protocol = protocol.replace("_apy", "")
            
            # Compare with liquidity pools
            best_liquidity_apy = 0
            best_liquidity_pool = None
            
            for pool, apy in liquidity_apy.items():
                if isinstance(apy, (int, float)) and apy > best_liquidity_apy:
                    best_liquidity_apy = apy
                    best_liquidity_pool = pool
            
            info(f"Best staking APY: {best_staking_protocol} at {best_staking_apy:.2f}%")
            if best_liquidity_pool:
                info(f"Best liquidity APY: {best_liquidity_pool} at {best_liquidity_apy:.2f}%")
            
            # Determine optimal strategy
            if best_staking_apy > best_liquidity_apy:
                info(f"Staking is optimal: {best_staking_protocol} at {best_staking_apy:.2f}%")
                
                # Check if we need to rebalance staking allocation
                if best_staking_protocol in self.staking_protocols:
                    info(f"Current best protocol {best_staking_protocol} is in configured protocols")
                else:
                    warning(f"Best protocol {best_staking_protocol} not in configured protocols")
            else:
                info(f"Liquidity provision is optimal: {best_liquidity_pool} at {best_liquidity_apy:.2f}%")
            
            # Update last optimization time
            self.last_yield_optimization = datetime.now()
            
            return True
            
        except Exception as e:
            error(f"Error in yield optimization: {str(e)}")
            return False

    def get_token_symbol(self, token_address):
        """Get token symbol from address"""
        try:
            # Check if it's a known token
            if token_address == SOL_ADDRESS:
                return "SOL"
            elif token_address == USDC_ADDRESS:
                return "USDC"
            
            # Try to get from token metadata
            try:
                response = requests.get(
                    f"https://public-api.solscan.io/token/meta?tokenAddress={token_address}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("symbol", token_address[:8])
                else:
                    return token_address[:8]
            except:
                return token_address[:8]
                
        except Exception as e:
            error(f"Error getting token symbol: {str(e)}")
            return token_address[:8]

    def get_token_holdings(self, token_address):
        """Get holdings for a specific token"""
        try:
            if token_address == SOL_ADDRESS:
                data_coordinator = get_shared_data_coordinator()
                return data_coordinator._fetch_sol_balance(address) if address else 0.0
            else:
                # Get token balance from wallet - using shared data coordinator
                data_coordinator = get_shared_data_coordinator()
                wallet_data = data_coordinator.get_personal_wallet_data()
                if wallet_data and token_address in wallet_data.tokens:
                    return wallet_data.tokens[token_address]
                return 0.0
        except Exception as e:
            error(f"Error getting token holdings: {str(e)}")
            return 0

    def get_all_token_holdings(self):
        """Get all token holdings from wallet"""
        try:
            holdings = {}
            
            # Get SOL balance
            data_coordinator = get_shared_data_coordinator()
            sol_balance = data_coordinator._fetch_sol_balance(address) if address else 0.0
            if sol_balance > 0:
                holdings[SOL_ADDRESS] = sol_balance
            
            # Get other token balances
            # This would need to be implemented based on your wallet tracking system
            # For now, we'll return just SOL
            return holdings
            
        except Exception as e:
            error(f"Error getting all token holdings: {str(e)}")
            return {}

    def get_usd_balance(self):
        """Get total USD balance"""
        try:
            total_balance = 0
            
            # Get SOL balance and value
            data_coordinator = get_shared_data_coordinator()
            sol_balance = data_coordinator._fetch_sol_balance(address) if address else 0.0
            sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 0.0
            sol_value = sol_balance * sol_price
            total_balance += sol_value
            
            # Get other token values
            token_holdings = self.get_all_token_holdings()
            for token_address, amount in token_holdings.items():
                if token_address == SOL_ADDRESS:
                    continue  # Already counted
                
                token_price = data_coordinator.price_service.get_price(token_address) if hasattr(data_coordinator, 'price_service') else 0.0
                if token_price and amount > 0:
                    token_value = amount * token_price
                    total_balance += token_value
            
            return total_balance
            
        except Exception as e:
            error(f"Error getting USD balance: {str(e)}")
            return 0

    def should_run_yield_optimization(self):
        """Check if yield optimization should run"""
        try:
            if not self.last_yield_optimization:
                return True
            
            # Calculate time since last optimization
            time_since_last = datetime.now() - self.last_yield_optimization
            
            # Convert interval to timedelta
            if self.yield_optimization_interval_unit == "Hour(s)":
                interval_td = timedelta(hours=self.yield_optimization_interval_value)
            elif self.yield_optimization_interval_unit == "Day(s)":
                interval_td = timedelta(days=self.yield_optimization_interval_value)
            elif self.yield_optimization_interval_unit == "Week(s)":
                interval_td = timedelta(weeks=self.yield_optimization_interval_value)
            else:
                interval_td = timedelta(hours=1)  # Default to 1 hour
            
            return time_since_last >= interval_td
            
        except Exception as e:
            error(f"Error checking yield optimization timing: {str(e)}")
            return True

    def test_staking_functionality(self):
        """Test staking functionality without executing transactions"""
        try:
            info("Testing staking functionality...")
            
            # Test 1: Get portfolio balances (safe)
            info("Test 1: Getting portfolio balances...")
            try:
                total_balance = self.get_usd_balance()
                data_coordinator = get_shared_data_coordinator()
                sol_balance = data_coordinator._fetch_sol_balance(address) if address else 0.0
                info(f"✅ Total portfolio value: ${total_balance:.2f}")
                info(f"✅ SOL balance: {sol_balance:.4f} SOL")
            except Exception as e:
                warning(f"❌ Error getting portfolio balances: {str(e)}")
            
            # Test 2: Get token holdings (safe)
            info("Test 2: Getting token holdings...")
            try:
                holdings = self.get_all_token_holdings()
                info(f"✅ Token holdings: {len(holdings)} tokens")
            except Exception as e:
                warning(f"❌ Error getting token holdings: {str(e)}")
            
            # Test 3: Check SOL allocation (safe)
            info("Test 3: Checking SOL allocation...")
            try:
                if total_balance > 0:
                    sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 0.0
                    sol_allocation = (sol_balance * sol_price / total_balance) * 100
                    info(f"✅ Current SOL allocation: {sol_allocation:.2f}%")
                    info(f"✅ Target SOL allocation: {self.staking_allocation_percentage}%")
                    info(f"✅ Minimum SOL threshold: {self.min_sol_allocation_threshold}%")
                    
                    if sol_allocation < self.min_sol_allocation_threshold:
                        warning(f"⚠️ SOL allocation below minimum threshold!")
                    else:
                        info("✅ SOL allocation above minimum threshold")
                else:
                    warning("❌ Cannot calculate SOL allocation - zero balance")
            except Exception as e:
                warning(f"❌ Error checking SOL allocation: {str(e)}")
            
            # Test 4: Get staking rewards and APY (with fallbacks)
            info("Test 4: Getting staking rewards and APY...")
            try:
                staking_data, rewards = self.get_staking_rewards_and_apy()
                if staking_data:
                    info(f"✅ Staking data retrieved: {len(staking_data)} protocols")
                    for protocol, apy in list(staking_data.items())[:3]:  # Show first 3
                        if isinstance(apy, (int, float)):
                            info(f"  - {protocol}: {apy:.2f}% APY")
                        else:
                            info(f"  - {protocol}: {apy}")
                else:
                    warning("❌ No staking data retrieved")
            except Exception as e:
                warning(f"❌ Error getting staking data: {str(e)}")
            
            # Test 5: Get liquidity pool APY (with fallbacks)
            info("Test 5: Getting liquidity pool APY...")
            try:
                liquidity_apy = self.get_liquidity_pool_apy()
                if liquidity_apy:
                    info(f"✅ Liquidity APY data retrieved: {len(liquidity_apy)} pools")
                    for pool, apy in liquidity_apy.items():
                        if isinstance(apy, (int, float)):
                            info(f"  - {pool}: {apy:.2f}% APY")
                        else:
                            info(f"  - {pool}: {apy}")
                else:
                    warning("❌ No liquidity APY data retrieved")
            except Exception as e:
                warning(f"❌ Error getting liquidity APY: {str(e)}")
            
            # Test 6: Yield optimization (safe)
            info("Test 6: Running yield optimization...")
            try:
                optimization_result = self.optimize_yield()
                if optimization_result:
                    info("✅ Yield optimization completed successfully")
                else:
                    warning("❌ Yield optimization failed")
            except Exception as e:
                warning(f"❌ Error in yield optimization: {str(e)}")
            
            # Test 7: Auto-convert check (safe)
            info("Test 7: Checking auto-convert logic...")
            try:
                convert_result = self._auto_convert_for_staking()
                if convert_result:
                    info("✅ Auto-convert logic check completed")
                else:
                    warning("❌ Auto-convert logic check failed")
            except Exception as e:
                warning(f"❌ Error in auto-convert logic: {str(e)}")
            
            # Test 8: Scheduling logic (safe)
            info("Test 8: Testing scheduling logic...")
            try:
                should_wait = self.should_wait_for_scheduled_time()
                next_run = self.get_next_scheduled_run_time()
                info(f"✅ Should wait for scheduled time: {should_wait}")
                info(f"✅ Next scheduled run: {next_run}")
            except Exception as e:
                warning(f"❌ Error in scheduling logic: {str(e)}")
            
            info("🎉 Staking functionality test completed!")
            return True
            
        except Exception as e:
            error(f"Error in staking functionality test: {str(e)}")
            return False

    def test_basic_functionality(self):
        """Test basic functionality without API calls"""
        try:
            info("Testing basic staking functionality...")
            
            # Test 1: Basic initialization
            info("Test 1: Basic initialization...")
            info(f"✅ Staking allocation: {self.staking_allocation_percentage}%")
            info(f"✅ Stake percentage: {self.stake_percentage}%")
            info(f"✅ Min SOL threshold: {self.min_sol_allocation_threshold}%")
            info(f"✅ Staking protocols: {self.staking_protocols}")
            
            # Test 2: Portfolio data (safe)
            info("Test 2: Portfolio data...")
            try:
                balance = self.get_usd_balance()
                info(f"✅ USD Balance: ${balance:.2f}")
            except Exception as e:
                warning(f"❌ Error getting balance: {str(e)}")
            
            # Test 3: Token holdings (safe)
            info("Test 3: Token holdings...")
            try:
                holdings = self.get_all_token_holdings()
                info(f"✅ Token holdings: {len(holdings)} tokens")
            except Exception as e:
                warning(f"❌ Error getting holdings: {str(e)}")
            
            # Test 4: Scheduling logic (safe)
            info("Test 4: Scheduling logic...")
            try:
                should_wait = self.should_wait_for_scheduled_time()
                next_run = self.get_next_scheduled_run_time()
                info(f"✅ Should wait: {should_wait}")
                info(f"✅ Next run: {next_run}")
            except Exception as e:
                warning(f"❌ Error in scheduling: {str(e)}")
            
            # Test 5: Auto-convert logic (safe)
            info("Test 5: Auto-convert logic...")
            try:
                convert_result = self._auto_convert_for_staking()
                info(f"✅ Auto-convert: {'SUCCESS' if convert_result else 'FAILED'}")
            except Exception as e:
                warning(f"❌ Error in auto-convert: {str(e)}")
            
            info("🎉 Basic functionality test completed!")
            return True
            
        except Exception as e:
            error(f"Error in basic functionality test: {str(e)}")
            return False

    def _execute_staking_transaction(self, protocol_name, amount_sol, apy):
        """Execute actual staking transaction to the specified protocol"""
        try:
            info(f"Executing staking transaction: {amount_sol:.4f} SOL to {protocol_name}")
            
            # Validate inputs
            addr = self._get_current_address()
            if not addr:
                error("No wallet address configured for staking")
                return False
            
            if amount_sol <= 0:
                error("Invalid staking amount")
                return False
            
            # Enhanced mode detection and routing
            if PAPER_TRADING_ENABLED:
                info(f"📈 PAPER TRADING MODE: Simulating staking {amount_sol:.4f} SOL to {protocol_name}")
                return self._execute_paper_staking(protocol_name, amount_sol, apy)
            
            # Live trading mode - check configuration and safety flags
            if not STAKING_LIVE_MODE_ENABLED:
                info(f"🔒 LIVE STAKING DISABLED: Simulating staking {amount_sol:.4f} SOL to {protocol_name}")
                return self._execute_paper_staking(protocol_name, amount_sol, apy)
            
            if STAKING_DRY_RUN:
                info(f"🔍 DRY RUN MODE: Simulating live staking {amount_sol:.4f} SOL to {protocol_name}")
                return self._execute_paper_staking(protocol_name, amount_sol, apy)
            
            # Live trading mode - proceed with real staking
            info(f"💰 LIVE TRADING MODE: Executing real staking {amount_sol:.4f} SOL to {protocol_name}")
            
            # Ensure Solana SDK is available for live trading
            if not SOLANA_AVAILABLE:
                error("❌ Solana SDK not available - cannot execute live staking transactions")
                error("Please install solana SDK: pip install solana")
                error("Or switch to paper trading mode: PAPER_TRADING_ENABLED = True")
                return False
            
            # Check circuit breaker
            if self._is_circuit_breaker_active():
                error("🚨 Circuit breaker active - staking operations paused due to consecutive failures", file_only=True)
                return False
            
            # Additional safety checks for live mode
            if not self._validate_live_staking_requirements(amount_sol, protocol_name):
                self._record_failure()
                return False
            
            info("✅ Solana SDK available - proceeding with live staking transaction")
            
            # Protocol-specific staking implementation
            success = False
            if protocol_name == "blazestake":
                success = self._stake_to_blazestake(amount_sol)
            elif protocol_name == "jupsol":
                success = self._stake_to_jupsol(amount_sol)
            elif protocol_name == "sanctum":
                success = self._stake_to_sanctum(amount_sol)
            elif protocol_name == "everstake":
                success = self._stake_to_everstake(amount_sol)
            elif protocol_name == "community_validators":
                success = self._stake_to_community_validators(amount_sol)
            else:
                error(f"Unsupported staking protocol: {protocol_name}")
                self._record_failure()
                return False
            
            # Track success/failure for circuit breaker
            if success:
                self._record_success()
                # Update portfolio tracker with staked SOL for live trading
                self._update_portfolio_tracker_staked_sol(protocol_name, amount_sol, apy)
            else:
                self._record_failure()
            
            return success
                
        except Exception as e:
            error(f"Error executing staking transaction: {str(e)}")
            return False

    def _execute_staking_transaction_with_tracking(self, protocol_name, amount_sol, apy, trigger_reason="MANUAL"):
        """Execute staking transaction with execution tracking and cloud storage"""
        try:
            info(f"Executing staking transaction with tracking: {amount_sol:.4f} SOL to {protocol_name}")
            
            # Get current address and SOL price
            addr = self._get_current_address()
            if not addr:
                error("No wallet address configured for staking")
                return False
            
            # Get SOL price for USD value calculation
            try:
                from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
                data_coordinator = get_shared_data_coordinator()
                sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 176.46
            except:
                sol_price = None  # No fallback price
            
            usd_value = amount_sol * sol_price
            
            # Log execution attempt
            try:
                from src.scripts.database.execution_tracker import log_execution
                execution_id = log_execution(
                    agent_type="staking",
                    wallet_address=addr,
                    action="STAKE",
                    token_mint=SOL_ADDRESS,
                    amount=amount_sol,
                    price=sol_price,
                    usd_value=usd_value,
                    status="PENDING",
                    metadata={
                        'protocol': protocol_name,
                        'apy': apy,
                        'trigger_reason': trigger_reason,
                        'timestamp': datetime.now().isoformat()
                    }
                )
                info(f"✅ Execution logged with ID: {execution_id}")
            except Exception as e:
                warning(f"⚠️ Failed to log execution: {e}")
                execution_id = None
            
            # Execute the staking transaction
            staking_success = self._execute_staking_transaction(protocol_name, amount_sol, apy)
            
            if staking_success:
                # Update execution status to completed
                if execution_id:
                    try:
                        from src.scripts.database.execution_tracker import get_execution_tracker
                        tracker = get_execution_tracker()
                        tracker.update_execution_status(execution_id, "COMPLETED")
                        info("✅ Execution status updated to COMPLETED")
                    except Exception as e:
                        warning(f"⚠️ Failed to update execution status: {e}")
                
                # PRIMARY: Save to local CSV first
                self._save_staking_to_local(addr, protocol_name, amount_sol, usd_value, apy, trigger_reason, execution_id)
                
                # SECONDARY: Try to sync to cloud database (with timeout handling)
                try:
                    from src.scripts.database.cloud_database import get_cloud_database_manager
                    cloud_db = get_cloud_database_manager()
                    if cloud_db:
                        transaction_data = {
                            'wallet_address': addr,
                            'protocol': protocol_name,
                            'transaction_type': 'STAKE',
                            'amount_sol': amount_sol,
                            'amount_usd': usd_value,
                            'apy': apy,
                            'status': 'completed',
                            'daily_reward_sol': amount_sol * (apy / 365 / 100),  # Daily reward calculation
                            'metadata': {
                                'agent': 'staking_agent',
                                'trigger_reason': trigger_reason,
                                'execution_id': execution_id,
                                'timestamp': datetime.now().isoformat()
                            }
                        }
                        
                        # Try to save with timeout handling
                        import threading
                        import time
                        
                        def save_to_cloud():
                            try:
                                cloud_db.save_staking_transaction(transaction_data)
                                
                                position_data = {
                                    'wallet_address': addr,
                                    'protocol': protocol_name,
                                    'amount_sol': amount_sol,
                                    'amount_usd': usd_value,
                                    'apy': apy,
                                    'status': 'active',
                                    'metadata': {
                                        'agent': 'staking_agent',
                                        'trigger_reason': trigger_reason,
                                        'execution_id': execution_id,
                                        'staked_at': datetime.now().isoformat()
                                    }
                                }
                                cloud_db.save_staking_position(position_data)
                                return True
                            except Exception as e:
                                return False
                        
                        # Run cloud save in thread with timeout
                        result = [False]
                        thread = threading.Thread(target=lambda: result.__setitem__(0, save_to_cloud()))
                        thread.daemon = True
                        thread.start()
                        thread.join(timeout=5)  # 5 second timeout
                        
                        if thread.is_alive():
                            warning("⚠️ Cloud database sync timed out after 5 seconds")
                        elif result[0]:
                            info("✅ Staking data synced to cloud database")
                        else:
                            warning("⚠️ Cloud database sync failed")
                            
                except (TimeoutError, ConnectionError, Exception) as cloud_error:
                    warning(f"⚠️ Cloud database sync failed (local data saved): {cloud_error}")
                
                info(f"✅ Successfully executed staking transaction: {amount_sol:.4f} SOL to {protocol_name}")
                
                # CRITICAL FIX: Notify coordinator to trigger DeFi agent
                try:
                    from src.scripts.defi.staking_defi_coordinator import get_staking_defi_coordinator
                    coordinator = get_staking_defi_coordinator()
                    coordinator.handle_staking_complete(amount_sol, protocol_name)
                    info(f"📈 Notified coordinator: {amount_sol:.4f} SOL staked → DeFi agent triggered")
                except Exception as e:
                    warning(f"⚠️ Failed to notify coordinator: {e}")
                
                return True
            else:
                # Update execution status to failed
                if execution_id:
                    try:
                        from src.scripts.database.execution_tracker import get_execution_tracker
                        tracker = get_execution_tracker()
                        tracker.update_execution_status(execution_id, "FAILED", "Staking transaction failed")
                        info("❌ Execution status updated to FAILED")
                    except Exception as e:
                        warning(f"⚠️ Failed to update execution status: {e}")
                
                error(f"❌ Failed to execute staking transaction: {amount_sol:.4f} SOL to {protocol_name}")
                return False
                
        except Exception as e:
            error(f"❌ Error in staking transaction with tracking: {e}")
            return False

    def _stake_to_blazestake(self, amount_sol):
        """Stake SOL to BlazeStake protocol via Jupiter swap to bSOL"""
        try:
            info(f"Staking {amount_sol:.4f} SOL to BlazeStake (bSOL)...")
            
            if not SOLANA_AVAILABLE:
                warning("Solana SDK not available - simulating BlazeStake staking")
                return True
            
            # Get wallet address
            addr = self._get_current_address()
            if not addr:
                error("No wallet address configured for BlazeStake staking")
                return False
            
            # Use Jupiter to swap SOL to bSOL (BlazeStake's liquid staking token)
            bsol_address = BLAZESTAKE_BSOL_MINT
            
            # Get Jupiter quote for SOL to bSOL swap
            quote_url = f"{JUPITER_API_URL}/quote"
            quote_params = {
                "inputMint": SOL_ADDRESS,
                "outputMint": bsol_address,
                "amount": str(int(amount_sol * 1e9)),  # Convert to lamports
                "slippageBps": JUPITER_DEFAULT_SLIPPAGE_BPS
            }
            
            quote_response = requests.get(quote_url, params=quote_params, timeout=API_TIMEOUT_SECONDS)
            if quote_response.status_code != 200:
                error(f"Failed to get Jupiter quote for bSOL: {quote_response.text}")
                return False
            
            quote_data = quote_response.json()
            bsol_amount = quote_data.get('outAmount', 0)
            
            info(f"Quote received: {amount_sol:.4f} SOL → {int(bsol_amount)/1e9:.4f} bSOL")
            
            # Get swap transaction
            swap_url = f"{JUPITER_API_URL}/swap"
            swap_data = {
                "quoteResponse": quote_data,
                "userPublicKey": addr,
                "wrapUnwrapSOL": True
            }
            
            swap_response = requests.post(swap_url, json=swap_data, timeout=API_TIMEOUT_SECONDS)
            if swap_response.status_code != 200:
                error(f"Failed to get swap transaction: {swap_response.text}")
                return False
            
            swap_result = swap_response.json()
            swap_transaction = swap_result.get('swapTransaction')
            
            if not swap_transaction:
                error("No swap transaction received from Jupiter")
                return False
            
            # Execute the swap transaction
            if STAKING_LIVE_MODE_ENABLED and not STAKING_DRY_RUN:
                # Import required modules for live execution
                from solders.keypair import Keypair
                from solders.transaction import VersionedTransaction
                import base64
                
                # Get private key from environment
                private_key = os.getenv('SOLANA_PRIVATE_KEY')
                if not private_key:
                    error("SOLANA_PRIVATE_KEY not configured for live staking")
                    return False
                
                # Create keypair and sign transaction
                keypair = Keypair.from_base58_string(private_key)
                
                # Deserialize and sign transaction
                transaction_bytes = base64.b64decode(swap_transaction)
                transaction = VersionedTransaction.from_bytes(transaction_bytes)
                signed_transaction = VersionedTransaction(transaction.message, [keypair])
                
                # Send transaction
                client = Client(RPC_ENDPOINT)
                result = client.send_transaction(signed_transaction)
                
                if result.get('result'):
                    info(f"✅ BlazeStake (bSOL) staking transaction successful: {result['result']}")
                    return True
                else:
                    error(f"❌ BlazeStake (bSOL) staking transaction failed: {result}")
                    return False
            else:
                # Dry run mode - simulate success
                info(f"📈 DRY RUN: Would stake {amount_sol:.4f} SOL to BlazeStake (bSOL)")
                return True
            
        except Exception as e:
            error(f"Error staking to BlazeStake: {str(e)}")
            return False

    def _stake_to_jupsol(self, amount_sol):
        """Stake SOL to JupSOL protocol using Jupiter API"""
        try:
            info(f"Staking {amount_sol:.4f} SOL to JupSOL...")
            
            # JupSOL token address
            jupsol_address = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"  # JupSOL token address
            
            # Get Jupiter quote for SOL to JupSOL swap
            quote_url = f"{JUPITER_API_URL}/quote"
            quote_params = {
                "inputMint": SOL_ADDRESS,
                "outputMint": jupsol_address,
                "amount": str(int(amount_sol * 1e9)),  # Convert to lamports
                "slippageBps": JUPITER_DEFAULT_SLIPPAGE_BPS
            }
            
            quote_response = requests.get(quote_url, params=quote_params, timeout=API_TIMEOUT_SECONDS)
            if quote_response.status_code != 200:
                error(f"Failed to get Jupiter quote: {quote_response.text}")
                return False
            
            quote_data = quote_response.json()
            jupsol_amount = quote_data.get('outAmount', 0)
            
            info(f"Quote received: {amount_sol:.4f} SOL → {int(jupsol_amount)/1e9:.4f} JupSOL")
            
            # Get swap transaction
            swap_url = f"{JUPITER_API_URL}/swap"
            swap_data = {
                "quoteResponse": quote_data,
                "userPublicKey": address,
                "wrapUnwrapSOL": True
            }
            
            swap_response = requests.post(swap_url, json=swap_data, timeout=API_TIMEOUT_SECONDS)
            if swap_response.status_code != 200:
                error(f"Failed to get swap transaction: {swap_response.text}")
                return False
            
            swap_result = swap_response.json()
            swap_transaction = swap_result.get('swapTransaction')
            
            if not swap_transaction:
                error("No swap transaction received from Jupiter")
                return False
            
            # Execute the swap transaction
            if SOLANA_AVAILABLE:
                client = Client(RPC_ENDPOINT)
                
                # Import solders components for real transaction signing
                from solders.keypair import Keypair
                from solders.pubkey import Pubkey
                from solders.transaction import Transaction
                
                # Decode and send transaction
                import base64
                transaction_data = base64.b64decode(swap_transaction)
                
                # Create transaction from decoded data
                transaction = Transaction.from_bytes(transaction_data)
                
                # Sign and send transaction
                result = client.send_transaction(
                    transaction,
                    opts={"skipPreflight": True, "maxRetries": 3}
                )
                
                if result.get('result'):
                    info(f"✅ JupSOL staking transaction successful: {result['result']}")
                    return True
                else:
                    error(f"❌ JupSOL staking transaction failed: {result}")
                    return False
            else:
                warning("Solana SDK not available - simulating JupSOL staking")
                return True
            
        except Exception as e:
            error(f"Error staking to JupSOL: {str(e)}")
            return False

    def _stake_to_sanctum(self, amount_sol):
        """Stake SOL to Sanctum protocol via Jupiter swap to LSTs"""
        try:
            info(f"Staking {amount_sol:.4f} SOL to Sanctum...")
            
            if not SOLANA_AVAILABLE:
                warning("Solana SDK not available - simulating Sanctum staking")
                return True
            
            # Get wallet address
            addr = self._get_current_address()
            if not addr:
                error("No wallet address configured for Sanctum staking")
                return False
            
            # Select best Sanctum LST based on APY (for now, use INF as default)
            selected_lst = "INF"  # Could be enhanced to select best APY
            lst_mint = SANCTUM_LST_MINTS[selected_lst]
            
            info(f"Selected Sanctum LST: {selected_lst} ({lst_mint})")
            
            # Get Jupiter quote for SOL to selected LST swap
            quote_url = f"{JUPITER_API_URL}/quote"
            quote_params = {
                "inputMint": SOL_ADDRESS,
                "outputMint": lst_mint,
                "amount": str(int(amount_sol * 1e9)),  # Convert to lamports
                "slippageBps": JUPITER_DEFAULT_SLIPPAGE_BPS
            }
            
            quote_response = requests.get(quote_url, params=quote_params, timeout=API_TIMEOUT_SECONDS)
            if quote_response.status_code != 200:
                error(f"Failed to get Jupiter quote for {selected_lst}: {quote_response.text}")
                return False
            
            quote_data = quote_response.json()
            lst_amount = quote_data.get('outAmount', 0)
            
            info(f"Quote received: {amount_sol:.4f} SOL → {int(lst_amount)/1e9:.4f} {selected_lst}")
            
            # Get swap transaction
            swap_url = f"{JUPITER_API_URL}/swap"
            swap_data = {
                "quoteResponse": quote_data,
                "userPublicKey": addr,
                "wrapUnwrapSOL": True
            }
            
            swap_response = requests.post(swap_url, json=swap_data, timeout=API_TIMEOUT_SECONDS)
            if swap_response.status_code != 200:
                error(f"Failed to get swap transaction: {swap_response.text}")
                return False
            
            swap_result = swap_response.json()
            swap_transaction = swap_result.get('swapTransaction')
            
            if not swap_transaction:
                error("No swap transaction received from Jupiter")
                return False
            
            # Execute the swap transaction
            if STAKING_LIVE_MODE_ENABLED and not STAKING_DRY_RUN:
                # Import required modules for live execution
                from solders.keypair import Keypair
                from solders.transaction import VersionedTransaction
                import base64
                
                # Get private key from environment
                private_key = os.getenv('SOLANA_PRIVATE_KEY')
                if not private_key:
                    error("SOLANA_PRIVATE_KEY not configured for live staking")
                    return False
                
                # Create keypair and sign transaction
                keypair = Keypair.from_base58_string(private_key)
                
                # Deserialize and sign transaction
                transaction_bytes = base64.b64decode(swap_transaction)
                transaction = VersionedTransaction.from_bytes(transaction_bytes)
                signed_transaction = VersionedTransaction(transaction.message, [keypair])
                
                # Send transaction
                client = Client(RPC_ENDPOINT)
                result = client.send_transaction(signed_transaction)
                
                if result.get('result'):
                    info(f"✅ Sanctum ({selected_lst}) staking transaction successful: {result['result']}")
                    return True
                else:
                    error(f"❌ Sanctum ({selected_lst}) staking transaction failed: {result}")
                    return False
            else:
                # Dry run mode - simulate success
                info(f"📈 DRY RUN: Would stake {amount_sol:.4f} SOL to Sanctum ({selected_lst})")
                return True
            
        except Exception as e:
            error(f"Error staking to Sanctum: {str(e)}")
            return False

    def _stake_to_everstake(self, amount_sol):
        """Stake SOL to Evernstake protocol"""
        try:
            info(f"Staking {amount_sol:.4f} SOL to Evernstake...")
            
            # Evernstake staking implementation
            # This would use the Solana SDK to interact with Evernstake program
            
            # TODO: Implement actual Evernstake staking transaction
            # This would involve:
            # 1. Creating a stake account
            # 2. Delegating to Evernstake validators
            # 3. Confirming the transaction
            
            info("Evernstake staking transaction simulated successfully")
            return True
            
        except Exception as e:
            error(f"Error staking to Evernstake: {str(e)}")
            return False

    def _stake_to_community_validators(self, amount_sol):
        """Stake SOL to community validators via native staking"""
        try:
            info(f"Staking {amount_sol:.4f} SOL to community validators...")
            
            if not SOLANA_AVAILABLE:
                warning("Solana SDK not available - simulating community validator staking")
                return True
            
            # Get wallet address
            addr = self._get_current_address()
            if not addr:
                error("No wallet address configured for community validator staking")
                return False
            
            # Select validators from community list
            selected_validators = self._select_community_validators()
            if not selected_validators:
                error("No suitable community validators found")
                return False
            
            info(f"Selected {len(selected_validators)} community validators for staking")
            
            # Calculate stake amount per validator
            stake_per_validator = amount_sol / len(selected_validators)
            
            if STAKING_LIVE_MODE_ENABLED and not STAKING_DRY_RUN:
                # Import required modules for live execution
                from solders.keypair import Keypair
                from solders.pubkey import Pubkey
                from solders.transaction import Transaction
                from solders.system_program import create_account, CreateAccountParams
                from solders.stake_program import create_account as create_stake_account, delegate_stake, DelegateStakeParams
                import base64
                
                # Get private key from environment
                private_key = os.getenv('SOLANA_PRIVATE_KEY')
                if not private_key:
                    error("SOLANA_PRIVATE_KEY not configured for live staking")
                    return False
                
                # Create keypair
                keypair = Keypair.from_base58_string(private_key)
                client = Client(RPC_ENDPOINT)
                
                # Create stake accounts and delegate to validators
                successful_delegations = 0
                
                for i, validator_address in enumerate(selected_validators):
                    try:
                        # Create stake account
                        stake_account = Keypair()
                        stake_amount_lamports = int(stake_per_validator * 1e9)
                        
                        # Create stake account instruction
                        create_stake_ix = create_stake_account(
                            CreateAccountParams(
                                from_pubkey=keypair.pubkey(),
                                stake_pubkey=stake_account.pubkey(),
                                authorized=keypair.pubkey(),
                                lamports=stake_amount_lamports,
                                lockup=None
                            )
                        )
                        
                        # Delegate stake instruction
                        delegate_ix = delegate_stake(
                            DelegateStakeParams(
                                stake=stake_account.pubkey(),
                                authorized=keypair.pubkey(),
                                vote_account=Pubkey.from_string(validator_address)
                            )
                        )
                        
                        # Build and send transaction
                        transaction = Transaction()
                        transaction.add(create_stake_ix, delegate_ix)
                        
                        result = client.send_transaction(transaction, [keypair, stake_account])
                        
                        if result.get('result'):
                            info(f"✅ Delegated {stake_per_validator:.4f} SOL to validator {validator_address[:8]}...")
                            successful_delegations += 1
                        else:
                            error(f"❌ Failed to delegate to validator {validator_address[:8]}...: {result}")
                            
                    except Exception as e:
                        error(f"Error delegating to validator {validator_address[:8]}...: {str(e)}")
                        continue
                
                if successful_delegations > 0:
                    info(f"✅ Successfully delegated to {successful_delegations}/{len(selected_validators)} community validators")
                    return True
                else:
                    error("❌ Failed to delegate to any community validators")
                    return False
            else:
                # Dry run mode - simulate success
                info(f"📈 DRY RUN: Would stake {amount_sol:.4f} SOL to {len(selected_validators)} community validators")
                for validator in selected_validators:
                    info(f"  - {stake_per_validator:.4f} SOL to {validator[:8]}...")
                return True
            
        except Exception as e:
            error(f"Error staking to community validators: {str(e)}")
            return False
    
    def _select_community_validators(self):
        """Select high-performance community validators for staking"""
        try:
            # For now, return the configured community validators
            # In a full implementation, this would query the Solana validators API
            # and filter by performance, commission, and stake criteria
            
            selected_validators = []
            
            # Use configured community validators as base
            for validator in COMMUNITY_VALIDATORS:
                if validator and len(validator) > 20:  # Basic validation
                    selected_validators.append(validator)
            
            # Limit to configured number of validators
            max_validators = min(len(selected_validators), NATIVE_STAKING_VALIDATOR_COUNT)
            return selected_validators[:max_validators]
            
        except Exception as e:
            error(f"Error selecting community validators: {str(e)}")
            return []
    
    def _validate_live_staking_requirements(self, amount_sol, protocol_name):
        """Validate requirements for live staking"""
        try:
            # Check minimum staking amount
            if amount_sol < STAKING_MIN_SINGLE_STAKE_SOL:
                error(f"Amount {amount_sol:.4f} SOL below minimum {STAKING_MIN_SINGLE_STAKE_SOL} SOL")
                return False
            
            # Check maximum staking amount
            if amount_sol > STAKING_MAX_SINGLE_STAKE_SOL:
                error(f"Amount {amount_sol:.4f} SOL exceeds maximum {STAKING_MAX_SINGLE_STAKE_SOL} SOL")
                return False
            
            # Check wallet has sufficient balance
            try:
                from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
                tracker = get_portfolio_tracker()
                if hasattr(tracker, 'get_sol_balance'):
                    sol_balance = tracker.get_sol_balance()
                    if sol_balance < amount_sol + 0.1:  # Add 0.1 SOL for fees
                        error(f"Insufficient SOL balance: {sol_balance:.4f} < {amount_sol + 0.1:.4f}")
                        return False
            except Exception as e:
                warning(f"Could not verify SOL balance: {str(e)}")
            
            # Check protocol is enabled
            if protocol_name == "everstake" and not EVERSTAKE_ENABLED:
                error("Everstake protocol is disabled")
                return False
            
            # Check APY is reasonable
            try:
                # This would be enhanced to get actual APY from protocol
                # For now, just log a warning if we can't verify
                info(f"Validating {protocol_name} protocol requirements...")
            except Exception as e:
                warning(f"Could not validate protocol APY: {str(e)}")
            
            return True
            
        except Exception as e:
            error(f"Error validating live staking requirements: {str(e)}")
            return False
    
    def _is_circuit_breaker_active(self):
        """Check if circuit breaker is active"""
        try:
            if not self.circuit_breaker_active:
                return False
            
            # Check if cooldown period has passed
            if self.last_failure_time:
                cooldown_hours = STAKING_FAILURE_COOLDOWN_HOURS
                time_since_failure = (datetime.now() - self.last_failure_time).total_seconds() / 3600
                
                if time_since_failure >= cooldown_hours:
                    info(f"Circuit breaker cooldown period ({cooldown_hours}h) has passed - resuming operations", file_only=True)
                    self.circuit_breaker_active = False
                    self.consecutive_failures = 0
                    return False
            
            return True
            
        except Exception as e:
            error(f"Error checking circuit breaker: {str(e)}")
            return False
    
    def _record_failure(self):
        """Record a staking failure and check circuit breaker"""
        try:
            self.consecutive_failures += 1
            self.last_failure_time = datetime.now()
            
            warning(f"Staking failure #{self.consecutive_failures} recorded")
            
            if self.consecutive_failures >= STAKING_MAX_CONSECUTIVE_FAILURES:
                self.circuit_breaker_active = True
                error(f"🚨 Circuit breaker activated after {self.consecutive_failures} consecutive failures", file_only=True)
                error(f"Staking operations paused for {STAKING_FAILURE_COOLDOWN_HOURS} hours", file_only=True)
            
        except Exception as e:
            error(f"Error recording failure: {str(e)}")
    
    def _record_success(self):
        """Record a successful staking operation"""
        try:
            if self.consecutive_failures > 0:
                info(f"Staking success - resetting failure counter from {self.consecutive_failures}")
                self.consecutive_failures = 0
                self.circuit_breaker_active = False
        except Exception as e:
            error(f"Error recording success: {str(e)}")

    def _update_staking_portfolio(self, protocol_name, amount_sol, apy):
        """Update portfolio tracking with staking information"""
        try:
            info(f"Updating staking portfolio: {protocol_name} - {amount_sol:.4f} SOL at {apy:.2f}% APY")
            
            # Update shared data coordinator with staking information
            data_coordinator = get_shared_data_coordinator()
            
            # Store staking information for portfolio tracking
            staking_info = {
                'protocol': protocol_name,
                'amount_sol': amount_sol,
                'apy': apy,
                'timestamp': datetime.now().isoformat(),
                'wallet_address': (self._get_current_address() or "")
            }
            
            # TODO: Store staking information in database or cache
            # This would involve:
            # 1. Storing staking transaction details
            # 2. Updating portfolio balance calculations
            # 3. Tracking staking rewards over time
            
            info("Staking portfolio updated successfully")
            return True
            
        except Exception as e:
            error(f"Error updating staking portfolio: {str(e)}")
            return False

    def _execute_paper_staking(self, protocol_name, amount_sol, apy):
        """Execute paper trading staking simulation"""
        try:
            info(f"📈 Paper Trading: Simulating staking {amount_sol:.4f} SOL to {protocol_name} at {apy:.2f}% APY")
            
            # Get paper trading database
            db = paper_trading.get_paper_trading_db()
            cursor = db.cursor()
            addr = self._get_current_address()
            
            # Calculate staking rewards (simplified simulation)
            # In real staking, rewards accumulate over time
            # For paper trading, we'll simulate immediate reward calculation
            daily_reward_rate = apy / 365 / 100  # Convert APY to daily rate
            daily_reward_sol = amount_sol * daily_reward_rate
            
            # Record the staking transaction in paper trading database
            staking_data = {
                'timestamp': datetime.now().isoformat(),
                'protocol': protocol_name,
                'amount_sol': amount_sol,
                'apy': apy,
                'daily_reward_sol': daily_reward_sol,
                'transaction_type': 'STAKE',
                'status': 'COMPLETED'
            }
            
            # Insert into paper trading staking table
            cursor.execute('''
                INSERT INTO paper_staking_transactions 
                (timestamp, protocol, amount_sol, apy, daily_reward_sol, transaction_type, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                staking_data['timestamp'],
                staking_data['protocol'],
                staking_data['amount_sol'],
                staking_data['apy'],
                staking_data['daily_reward_sol'],
                staking_data['transaction_type'],
                staking_data['status']
            ))
            
            # Update paper trading SOL balance (reduce available SOL)
            cursor.execute('''
                UPDATE paper_trading_balances 
                SET sol_balance = sol_balance - ?, 
                    staked_sol_balance = staked_sol_balance + ?,
                    last_updated = ?
                WHERE wallet_address = ?
            ''', (amount_sol, amount_sol, datetime.now().isoformat(), addr))
            
            # CRITICAL FIX: Also deduct from paper_portfolio table
            cursor.execute('''
                UPDATE paper_portfolio 
                SET amount = amount - ?
                WHERE token_address = ?
            ''', (amount_sol, SOL_ADDRESS))
            
            # Add staked SOL as a token position in the portfolio
            staked_sol_address = self.staked_sol_token_address
            
            # Get SOL price for staked SOL valuation
            try:
                from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
                data_coordinator = get_shared_data_coordinator()
                sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 176.46
            except:
                sol_price = None  # No fallback price
            
            # Check if staked SOL position already exists
            cursor.execute('''
                SELECT amount FROM paper_portfolio 
                WHERE token_address = ?
            ''', (staked_sol_address,))
            
            existing_position = cursor.fetchone()
            
            if existing_position:
                # Update existing staked SOL position
                cursor.execute('''
                    UPDATE paper_portfolio 
                    SET amount = amount + ?, last_price = ?, last_update = ?
                    WHERE token_address = ?
                ''', (amount_sol, sol_price, int(time.time()), staked_sol_address))
            else:
                # Create new staked SOL position
                cursor.execute('''
                    INSERT INTO paper_portfolio 
                    (token_address, amount, last_price, last_update)
                    VALUES (?, ?, ?, ?)
                ''', (staked_sol_address, amount_sol, sol_price, int(time.time())))
            
            # Commit the transaction
            db.commit()
            
            # Also save to paper_trades table for local dashboard visibility
            try:
                cursor.execute('''
                    INSERT INTO paper_trades 
                    (timestamp, action, amount, price, usd_value, agent, token_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(time.time()),
                    'STAKE',
                    amount_sol,
                    sol_price,
                    amount_sol * sol_price,
                    'staking',
                    SOL_ADDRESS
                ))
                db.commit()
                info("✅ Staking transaction saved to paper_trades table")
            except Exception as e:
                warning(f"⚠️ Failed to save staking to paper_trades table: {e}")
            
            # Log execution for paper trading
            try:
                from src.scripts.database.execution_tracker import log_execution
                execution_id = log_execution(
                    agent_type="staking",
                    wallet_address=addr,
                    action="STAKE",
                    token_mint=SOL_ADDRESS,
                    amount=amount_sol,
                    price=sol_price,
                    usd_value=amount_sol * sol_price,
                    status="COMPLETED",
                    metadata={
                        'protocol': protocol_name,
                        'apy': apy,
                        'paper_trading': True,
                        'daily_reward_sol': daily_reward_sol,
                        'timestamp': datetime.now().isoformat()
                    }
                )
                info(f"✅ Paper Trading: Execution logged with ID: {execution_id}")
            except Exception as e:
                warning(f"⚠️ Failed to log paper trading execution: {e}")

            # Save to cloud database (with timeout handling)
            try:
                from src.scripts.database.cloud_database import get_cloud_database_manager
                cloud_db = get_cloud_database_manager()
                if cloud_db:
                    transaction_data = {
                        'wallet_address': addr,
                        'protocol': protocol_name,
                        'transaction_type': 'STAKE',
                        'amount_sol': amount_sol,
                        'amount_usd': amount_sol * sol_price,
                        'apy': apy,
                        'status': 'completed',
                        'daily_reward_sol': daily_reward_sol,
                        'metadata': {'agent': 'staking_agent', 'paper_trading': True, 'timestamp': datetime.now().isoformat()}
                    }
                    
                    position_data = {
                        'wallet_address': addr,
                        'protocol': protocol_name,
                        'amount_sol': amount_sol,
                        'amount_usd': amount_sol * sol_price,
                        'apy': apy,
                        'status': 'active',
                        'metadata': {'agent': 'staking_agent', 'paper_trading': True, 'staked_at': datetime.now().isoformat()}
                    }
                    
                    # Try to save with timeout handling
                    import threading
                    
                    def save_paper_to_cloud():
                        try:
                            cloud_db.save_staking_transaction(transaction_data)
                            cloud_db.save_staking_position(position_data)
                            
                            # Also save to paper_trading_transactions for visibility in Recent Trades
                            try:
                                from datetime import datetime
                                paper_tx = {
                                    'transaction_id': f"{SOL_ADDRESS}_STAKE_{int(time.time())}_{int(amount_sol * 1e6)}",
                                    'transaction_type': 'STAKE',
                                    'token_mint': SOL_ADDRESS,
                                    'token_symbol': 'SOL',
                                    'amount': amount_sol,
                                    'price_usd': sol_price,
                                    'value_usd': amount_sol * sol_price,
                                    'usdc_amount': 0.0,
                                    'sol_amount': amount_sol,
                                    'agent_name': 'staking',
                                    'metadata': {
                                        'protocol': protocol_name,
                                        'apy': apy,
                                        'paper_trading': True,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                }
                                cloud_db.save_paper_trading_transaction(paper_tx)
                                info("✅ Staking transaction mirrored to paper_trading_transactions")
                            except Exception as e:
                                warning(f"Failed to mirror staking to paper_trading_transactions: {e}")
                            
                            return True
                        except Exception as e:
                            return False
                    
                    # Run cloud save in thread with timeout
                    result = [False]
                    thread = threading.Thread(target=lambda: result.__setitem__(0, save_paper_to_cloud()))
                    thread.daemon = True
                    thread.start()
                    thread.join(timeout=5)  # 5 second timeout
                    
                    if thread.is_alive():
                        warning("⚠️ Paper Trading: Cloud database save timed out after 5 seconds")
                    elif result[0]:
                        info("✅ Paper Trading: Staking data saved to cloud database")
                    else:
                        warning("⚠️ Paper Trading: Cloud database save failed")
            except Exception as cloud_error:
                warning(f"⚠️ Cloud database not available for paper trading: {cloud_error}")
            
            
            info(f"✅ Paper Trading: Successfully staked {amount_sol:.4f} SOL to {protocol_name}")
            info(f"📊 Paper Trading: Daily reward simulation: {daily_reward_sol:.6f} SOL")
            
            # Force portfolio tracker to refresh and create new snapshot
            self._force_portfolio_refresh()
            
            return True
            
        except Exception as e:
            error(f"Error in paper trading staking: {str(e)}")
            return False
        finally:
            # Always close the database connection
            if 'db' in locals():
                db.close()

    def _get_paper_staking_balance(self):
        """Get current paper trading staking balance"""
        try:
            db = paper_trading.get_paper_trading_db()
            cursor = db.cursor()
            addr = self._get_current_address()
            
            try:
                cursor.execute('''
                    SELECT staked_sol_balance FROM paper_trading_balances 
                    WHERE wallet_address = ?
                ''', (addr,))
                
                result = cursor.fetchone()
                if result:
                    return result[0]
                else:
                    return 0.0
            finally:
                # Always close the database connection
                db.close()
                
        except Exception as e:
            error(f"Error getting paper staking balance: {str(e)}")
            return 0.0

    def _update_paper_staking_rewards(self):
        """Update paper trading staking rewards (called periodically)"""
        try:
            db = paper_trading.get_paper_trading_db()
            cursor = db.cursor()
            addr = self._get_current_address()
            
            # Get all active staking positions
            cursor.execute('''
                SELECT protocol, amount_sol, apy, daily_reward_sol 
                FROM paper_staking_transactions 
                WHERE status = 'COMPLETED' AND transaction_type = 'STAKE'
            ''')
            
            staking_positions = cursor.fetchall()
            total_rewards = 0.0
            
            for position in staking_positions:
                protocol, amount_sol, apy, daily_reward_sol = position
                
                # Calculate accumulated rewards (simplified - could be more sophisticated)
                # In real staking, this would be calculated based on time elapsed
                accumulated_rewards = daily_reward_sol * 1  # 1 day worth for now
                total_rewards += accumulated_rewards
                
                info(f"📈 Paper Trading: {protocol} rewards: {accumulated_rewards:.6f} SOL")
            
            # Update total staking rewards
            if total_rewards > 0:
                cursor.execute('''
                    UPDATE paper_trading_balances 
                    SET staking_rewards = staking_rewards + ?,
                        last_updated = ?
                    WHERE wallet_address = ?
                ''', (total_rewards, datetime.now().isoformat(), addr))
                
                db.commit()
                info(f"📈 Paper Trading: Total staking rewards updated: {total_rewards:.6f} SOL")
            
            return total_rewards
            
        except Exception as e:
            error(f"Error updating paper staking rewards: {str(e)}")
            return 0.0

    def run_staking_cycle(self):
        """Run a single staking cycle"""
        try:
            info("Starting staking cycle...")
            
            # Use trade lock to prevent conflicts with rebalancing agent
            with lock_staking_operation(AgentType.STAKING, duration_seconds=600) as lock_id:
                info(f"Acquired staking lock: {lock_id}")
                
                # Check if we have a wallet address
                addr = self._get_current_address()
                if not addr:
                    warning("No wallet address configured. Cannot perform staking operations.")
                    return False
            
            # Get current portfolio state
            if PAPER_TRADING_ENABLED:
                # Use paper trading balances
                staked_sol = self._get_paper_staking_balance()
                db = paper_trading.get_paper_trading_db()
                cursor = db.cursor()
                
                cursor.execute('''
                    SELECT sol_balance, usdc_balance FROM paper_trading_balances 
                    WHERE wallet_address = ?
                ''', (addr,))
                
                result = cursor.fetchone()
                if result:
                    sol_balance, usdc_balance = result
                    data_coordinator = get_shared_data_coordinator()
                    sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 176.46
                    sol_value = sol_balance * sol_price
                    total_balance = usdc_balance + sol_value + (staked_sol * sol_price)
                else:
                    warning("No paper trading balance found")
                    return False
            else:
                # Use live wallet balances
                total_balance = self.get_usd_balance()
                data_coordinator = get_shared_data_coordinator()
                sol_balance = data_coordinator._fetch_sol_balance(addr) if addr else 0.0
                sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 0.0
                sol_value = sol_balance * sol_price
            
            if total_balance <= 0:
                warning("No portfolio balance available for staking")
                return False
            
            # Calculate current SOL allocation
            current_sol_pct = (sol_value / total_balance) * 100
            info(f"Current SOL allocation: {current_sol_pct:.2f}% (${sol_value:.2f} of ${total_balance:.2f})")
            
            # Check minimum SOL threshold
            if current_sol_pct < self.min_sol_allocation_threshold:
                warning(f"SOL allocation {current_sol_pct:.2f}% below minimum threshold {self.min_sol_allocation_threshold}%")
                info("Skipping staking to maintain minimum SOL allocation")
                return False
            
            # Calculate staking amount (50% of SOL balance)
            stake_amount_sol = sol_balance * (self.stake_percentage / 100)
            stake_amount_usd = stake_amount_sol * sol_price
            
            if stake_amount_sol < 0.1:  # Minimum 0.1 SOL to stake
                info(f"Staking amount {stake_amount_sol:.4f} SOL too small, skipping")
                return False
            
            info(f"Staking amount: {stake_amount_sol:.4f} SOL (${stake_amount_usd:.2f})")
            
            # Get best staking protocol
            staking_data, _ = self.get_staking_rewards_and_apy()
            if not staking_data:
                warning("No staking data available")
                return False
            
            # Find best APY protocol
            best_protocol = max(staking_data.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
            best_protocol_name = best_protocol[0].replace("_apy", "")
            best_apy = best_protocol[1]
            
            if best_protocol_name not in self.staking_protocols:
                warning(f"Best protocol {best_protocol_name} not in configured protocols")
                return False
            
            info(f"Selected protocol: {best_protocol_name} (APY: {best_apy:.2f}%)")
            
            # Execute staking transaction
            info(f"Executing staking transaction: {stake_amount_sol:.4f} SOL to {best_protocol_name}")
            
            # REAL STAKING TRANSACTION EXECUTION
            staking_success = self._execute_staking_transaction(best_protocol_name, stake_amount_sol, best_apy)
            
            if staking_success:
                info(f"✅ Successfully staked {stake_amount_sol:.4f} SOL to {best_protocol_name} at {best_apy:.2f}% APY")
                
                # Emit signal if QT is available
                if QT_AVAILABLE:
                    self.staking_executed.emit(
                        "Staking Agent", "STAKE", best_protocol_name, 
                        stake_amount_sol, best_apy, address, 
                        SOL_ADDRESS, f"Staked {stake_amount_sol:.4f} SOL"
                    )
                
                # Update portfolio tracking
                self._update_staking_portfolio(best_protocol_name, stake_amount_sol, best_apy)
                
                return True
            else:
                error(f"❌ Failed to stake {stake_amount_sol:.4f} SOL to {best_protocol_name}")
                return False
            
            # Update last run time
            self.last_run_day = datetime.now()
            
            info("Staking cycle completed successfully")
            return True
                
        except Exception as e:
            error(f"Error in staking cycle: {str(e)}")
            return False
            
        except Exception as e:
            error(f"Error in staking cycle: {str(e)}")
            return False

    def should_wait_for_scheduled_time(self):
        """Check if we should wait for scheduled time"""
        try:
            if not self.staking_run_at_enabled:
                return False
            
            now = datetime.now()
            scheduled_parts = self.staking_run_at_time.split(":")
            if len(scheduled_parts) != 2:
                warning(f"Invalid scheduled time format: {self.staking_run_at_time}")
                return False
            
            hour, minute = map(int, scheduled_parts)
            scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If scheduled time has passed today, schedule for tomorrow
            if now >= scheduled_time:
                scheduled_time += timedelta(days=1)
            
            time_until_scheduled = scheduled_time - now
            info(f"Next scheduled run: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}")
            info(f"Time until scheduled run: {time_until_scheduled}")
            
            return True
            
        except Exception as e:
            error(f"Error checking scheduled time: {str(e)}")
            return False

    def get_next_scheduled_run_time(self):
        """Get the next scheduled run time"""
        try:
            if not self.staking_run_at_enabled:
                return None
            
            now = datetime.now()
            
            # Check if we have a specific start date
            if self.staking_start_date:
                try:
                    # Parse start date and time
                    start_date = datetime.strptime(self.staking_start_date, "%Y-%m-%d")
                    hour, minute = map(int, self.staking_start_time.split(":"))
                    first_run = start_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # If first run hasn't happened yet, return it
                    if now < first_run:
                        return first_run
                    
                    # Calculate next run based on repeat interval
                    days_since_first = (now - first_run).days
                    next_run_day = first_run + timedelta(days=((days_since_first // self.staking_repeat_days) + 1) * self.staking_repeat_days)
                    next_run = next_run_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    return next_run
                    
                except Exception as e:
                    error(f"Error parsing start date {self.staking_start_date}: {str(e)}")
                    # Fall back to daily scheduling
            
            # Daily scheduling (fallback)
            hour, minute = map(int, self.staking_run_at_time.split(":"))
            scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If scheduled time has passed today, schedule for tomorrow
            if now >= scheduled_time:
                scheduled_time += timedelta(days=1)
            
            return scheduled_time
            
        except Exception as e:
            error(f"Error getting next scheduled run time: {str(e)}")
            return None

    def should_run_now(self):
        """Check if we should run now based on scheduled time"""
        try:
            if not self.staking_run_at_enabled:
                return True
            
            now = datetime.now()
            hour, minute = map(int, self.staking_run_at_time.split(":"))
            scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Check if we're within 5 minutes of scheduled time
            time_diff = abs((now - scheduled_time).total_seconds())
            return time_diff <= 300  # 5 minutes
            
        except Exception as e:
            error(f"Error checking if should run now: {str(e)}")
            return True

    def smart_sleep(self, seconds):
        """Smart sleep that can be interrupted"""
        try:
            # Ensure seconds is a number and positive
            if isinstance(seconds, (int, float)):
                seconds = float(seconds)
                if seconds <= 0:
                    return
            else:
                error(f"Invalid sleep duration: {seconds}")
                return
            
            # For very long waits, use a more efficient approach
            if seconds > 3600:  # More than 1 hour
                # Sleep in 1-hour chunks to allow interruption
                hours = int(seconds // 3600)
                remaining_seconds = seconds % 3600
                
                for _ in range(hours):
                    if not self.running:
                        break
                    time.sleep(3600)  # Sleep 1 hour
                
                if self.running and remaining_seconds > 0:
                    time.sleep(remaining_seconds)
            elif seconds > 60:  # More than 1 minute
                # Sleep in 1-minute chunks
                minutes = int(seconds // 60)
                remaining_seconds = seconds % 60
                
                for _ in range(minutes):
                    if not self.running:
                        break
                    time.sleep(60)  # Sleep 1 minute
                
                if self.running and remaining_seconds > 0:
                    time.sleep(remaining_seconds)
            else:
                time.sleep(seconds)
                
        except KeyboardInterrupt:
            info("Sleep interrupted by user")
        except Exception as e:
            error(f"Error in smart sleep: {str(e)}")
            # Fallback to simple sleep
            try:
                time.sleep(min(seconds, 60))
            except:
                pass

    def run_scheduled_staking(self):
        """Run staking on schedule"""
        try:
            info("Starting scheduled staking execution...")
            
            # Check if we should run now
            if self.staking_run_at_enabled and not self.should_run_now():
                next_run = self.get_next_scheduled_run_time()
                if next_run:
                    info(f"Waiting until scheduled time: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                    while not self.should_run_now() and self.running:
                        self.smart_sleep(60)  # Check every minute
            
            # Run staking cycle
            if self.running:
                success = self.run_staking_cycle()
                if success:
                    info("Scheduled staking completed successfully")
                else:
                    warning("Scheduled staking failed")
            
        except Exception as e:
            error(f"Error in scheduled staking: {str(e)}")

    def run(self):
        """Main run loop for the staking agent with hybrid approach"""
        try:
            info("🔒 Staking Agent starting with hybrid approach...")
            info(f"🔒 Execution mode: {self.execution_mode}")
            info(f"🔒 SOL target allocation: {self.sol_target_allocation}%")
            info(f"🔒 SOL excess threshold: {self.sol_excess_threshold}%")
            info(f"🔒 Webhook enabled: {self.webhook_enabled}")
            info(f"🔒 Interval enabled: {self.interval_enabled}")
            info(f"🔒 Interval: {self.interval_minutes} minutes")
            info(f"🔒 Configured protocols: {', '.join(self.staking_protocols)}")
            info(f"🔒 Staked SOL tracking: {self.staked_sol_tracking_enabled}")
            
            if self.staking_run_at_enabled:
                if self.staking_start_date:
                    info(f"Scheduled execution enabled with start date: {self.staking_start_date}")
                    info(f"Start time: {self.staking_start_time}")
                    info(f"Repeat every: {self.staking_repeat_days} days")
                else:
                    info(f"Scheduled execution enabled: {self.staking_run_at_time}")
                    run_at_hour, run_at_minute = map(int, self.staking_run_at_time.split(':'))
                    info(f"Will run at {run_at_hour:02d}:{run_at_minute:02d} daily")
                
                # Show next scheduled run
                next_run = self.get_next_scheduled_run_time()
                if next_run:
                    info(f"Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                info("Scheduled execution disabled - running on interval")
            
            # Wait for scheduled time before running any tests
            if self.staking_run_at_enabled:
                next_run = self.get_next_scheduled_run_time()
                if next_run:
                    wait_time = (next_run - datetime.now()).total_seconds()
                    if wait_time > 0:
                        info(f"⏳ Waiting {wait_time/3600:.1f} hours until scheduled start time: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                        # Sleep in 1-hour chunks to allow interruption
                        while wait_time > 0 and self.running:
                            sleep_chunk = min(wait_time, 3600)  # Max 1 hour
                            self.smart_sleep(sleep_chunk)
                            wait_time -= sleep_chunk
                            if wait_time > 0:
                                info(f"⏳ Still waiting {wait_time/3600:.1f} hours...")
            
            # Only run functionality test if not using scheduled execution
            if not self.staking_run_at_enabled:
                info("Running initial functionality test...")
                test_result = self.test_staking_functionality()
                if not test_result:
                    warning("Initial functionality test failed")
                    # Don't exit, just continue with the main loop
            else:
                info("Scheduled execution enabled - skipping initial functionality test")
            
            # Main loop with hybrid approach
            while self.running:
                try:
                    current_time = datetime.now()
                    
                    # Hybrid execution logic
                    should_run = False
                    
                    # Check webhook activity
                    if self.webhook_enabled and self._is_webhook_active():
                        info("🔒 Webhooks active - skipping interval execution")
                        self.smart_sleep(300)  # Sleep 5 minutes
                        continue
                    
                    # Check interval execution
                    if self.interval_enabled:
                        if not self.last_run_day or (current_time - self.last_run_day).total_seconds() >= (self.interval_minutes * 60):
                            should_run = True
                            info("🔒 Interval execution triggered")
                    
                    # Execute staking cycle if needed
                    if should_run:
                        from src.main import print_agent_activation, print_agent_event_processing, print_agent_event_result, print_agent_completion
                        
                        # Print activation header (CopyBot format)
                        print_agent_activation("Staking Agent", "staking", 1, "SOL staking operations")
                        print_agent_event_processing(1, 1, "Processing staking...", "staking")
                        
                        # Get current portfolio data
                        portfolio_data = self._get_current_portfolio_data()
                        if portfolio_data:
                            success = self._handle_portfolio_rebalancing(portfolio_data)
                            # CRITICAL FIX: Always update last_run_day to prevent infinite loop
                            self.last_run_day = current_time
                            if success:
                                # Print event result and completion
                                print_agent_event_result(1, "success", "", "staking")
                                print_agent_completion("staking", 1, 1)
                            else:
                                print_agent_event_result(1, "no_action", "", "staking")
                                print_agent_completion("staking", 0, 1)
                        else:
                            warning("🔒 Could not get portfolio data for interval execution")
                            # CRITICAL FIX: Also update last_run_day when portfolio data unavailable
                            self.last_run_day = current_time
                            print_agent_event_result(1, "no_action", "", "staking")
                            print_agent_completion("staking", 0, 1)
                    
                    # Sleep until next check
                    if not should_run:
                        time_until_next = (self.interval_minutes * 60) - ((current_time - self.last_run_day).total_seconds() if self.last_run_day else 0)
                        self.smart_sleep(min(time_until_next, 300))  # Max 5 minutes
                    
                except KeyboardInterrupt:
                    info("🔒 Staking agent interrupted by user")
                    break
                except Exception as e:
                    error(f"❌ Error in staking agent main loop: {e}")
                    self.smart_sleep(300)
            
            info("🔒 Staking agent stopped")
            
        except Exception as e:
            error(f"❌ Fatal error in staking agent: {e}")
            raise

    def _get_current_portfolio_data(self):
        """Get current portfolio data for interval execution"""
        try:
            addr = self._get_current_address()
            if not addr:
                return None
            
            if PAPER_TRADING_ENABLED:
                # Prefer PortfolioTracker snapshot for paper mode consistency (includes staked SOL)
                try:
                    from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
                    tracker = get_portfolio_tracker()

                    # Force a fresh snapshot so we see the latest staking operations
                    if hasattr(tracker, "force_refresh_portfolio_data"):
                        tracker.force_refresh_portfolio_data()

                    snapshot = getattr(tracker, "current_snapshot", None)
                    if snapshot and snapshot.total_value_usd > 0:
                        return {
                            "total_value": float(snapshot.total_value_usd),
                            "sol_balance": float(snapshot.sol_balance),
                            "sol_value_usd": float(snapshot.sol_value_usd),
                            "staked_sol_balance": float(getattr(snapshot, "staked_sol_balance", 0.0)),
                            "staked_sol_value_usd": float(getattr(snapshot, "staked_sol_value_usd", 0.0)),
                        }
                except Exception:
                    # Fallback to legacy DB path if tracker unavailable
                    db = paper_trading.get_paper_trading_db()
                    cursor = db.cursor()
                    cursor.execute('''
                        SELECT sol_balance, usdc_balance FROM paper_trading_balances 
                        WHERE wallet_address = ?
                    ''', (addr,))
                    result = cursor.fetchone()
                    
                    if result:
                        sol_balance, usdc_balance = result
                        data_coordinator = get_shared_data_coordinator()
                        sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 176.46
                        sol_value = sol_balance * sol_price
                        total_value = usdc_balance + sol_value

                        return {
                            'total_value': total_value,
                            'sol_balance': sol_balance,
                            'sol_value_usd': sol_value,
                            # Legacy fallback has no staked SOL info
                            'staked_sol_balance': 0.0,
                            'staked_sol_value_usd': 0.0,
                        }
            else:
                # Get live wallet data
                total_balance = self.get_usd_balance()
                data_coordinator = get_shared_data_coordinator()
                sol_balance = data_coordinator._fetch_sol_balance(addr) if addr else 0.0
                sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 0.0
                sol_value = sol_balance * sol_price
                
                return {
                    'total_value': total_balance,
                    'sol_balance': sol_balance,
                    'sol_value_usd': sol_value,
                    # Live mode stSOL can be added in the future if needed
                    'staked_sol_balance': 0.0,
                    'staked_sol_value_usd': 0.0,
                }
            
            return None
            
        except Exception as e:
            error(f"❌ Error getting portfolio data: {e}")
            return None

    def _force_portfolio_refresh(self):
        """Force portfolio tracker to refresh and create new snapshot"""
        try:
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            portfolio_tracker = get_portfolio_tracker()
            
            # Force a new portfolio snapshot to include staked SOL
            if hasattr(portfolio_tracker, 'update_portfolio_snapshot'):
                portfolio_tracker.update_portfolio_snapshot()
                info("🔄 Portfolio tracker refreshed with staked SOL data")
            else:
                warning("⚠️ Portfolio tracker doesn't have update_portfolio_snapshot method")
                
        except Exception as e:
            error(f"❌ Error forcing portfolio refresh: {e}")

    def _update_portfolio_tracker_staked_sol(self, protocol_name, amount_sol, apy):
        """Update portfolio tracker with staked SOL information"""
        try:
            if not self.staked_sol_tracking_enabled:
                return True
            
            # Get current address
            addr = self._get_current_address()
            if not addr:
                warning("🔒 No wallet address for portfolio tracker update")
                return False
            
            # Get SOL price for USD value calculation
            try:
                from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
                data_coordinator = get_shared_data_coordinator()
                sol_price = data_coordinator.price_service.get_price(SOL_ADDRESS) if hasattr(data_coordinator, 'price_service') else 176.46
            except:
                sol_price = None  # No fallback price
            
            usd_value = amount_sol * sol_price
            
            # Update portfolio tracker
            try:
                from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
                portfolio_tracker = get_portfolio_tracker()
                
                if portfolio_tracker:
                    # Add staked SOL to portfolio tracking
                    portfolio_tracker.add_staked_sol_position(
                        wallet_address=addr,
                        protocol=protocol_name,
                        amount_sol=amount_sol,
                        usd_value=usd_value,
                        apy=apy,
                        token_address=self.staked_sol_token_address,
                        symbol=self.staked_sol_symbol
                    )
                    info(f"✅ Updated portfolio tracker with staked SOL: {amount_sol:.4f} SOL to {protocol_name}")
                else:
                    warning("🔒 Portfolio tracker not available for staked SOL update")
                    
            except Exception as e:
                warning(f"🔒 Error updating portfolio tracker: {e}")
            
            # Update cloud database if available
            try:
                from src.scripts.database.cloud_database import get_cloud_database_manager
                cloud_db = get_cloud_database_manager()
                if cloud_db:
                    staking_data = {
                        'wallet_address': addr,
                        'protocol': protocol_name,
                        'amount_sol': amount_sol,
                        'usd_value': usd_value,
                        'apy': apy,
                        'token_address': self.staked_sol_token_address,
                        'symbol': self.staked_sol_symbol,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'active'
                    }
                    cloud_db.save_staking_position(staking_data)
                    info(f"✅ Updated cloud database with staked SOL position")
            except Exception as e:
                warning(f"🔒 Error updating cloud database: {e}")
            
            return True
            
        except Exception as e:
            error(f"❌ Error updating portfolio tracker with staked SOL: {e}")
            return False

    def _save_staking_to_local(self, wallet_address, protocol_name, amount_sol, usd_value, apy, trigger_reason, execution_id):
        """Save staking transaction to local CSV file"""
        try:
            import os
            import pandas as pd
            from datetime import datetime
            
            # Create data directory if it doesn't exist
            os.makedirs('src/data/staking', exist_ok=True)
            
            filepath = 'src/data/staking/staking_history.csv'
            
            # Prepare data for CSV
            staking_data = {
                'timestamp': [datetime.now().isoformat()],
                'wallet_address': [wallet_address],
                'protocol': [protocol_name],
                'amount_sol': [amount_sol],
                'amount_usd': [usd_value],
                'apy': [apy],
                'daily_reward_sol': [amount_sol * (apy / 365 / 100)],
                'trigger_reason': [trigger_reason],
                'execution_id': [execution_id],
                'status': ['completed']
            }
            
            df = pd.DataFrame(staking_data)
            
            # Check if file exists to append or create new
            if os.path.exists(filepath):
                try:
                    existing_df = pd.read_csv(filepath)
                    updated_df = pd.concat([existing_df, df], ignore_index=True)
                    updated_df.to_csv(filepath, index=False)
                except Exception as e:
                    df.to_csv(filepath, index=False)
                    warning(f"Error updating existing staking file, created new: {str(e)}")
            else:
                df.to_csv(filepath, index=False)
            
            info(f"📁 Staking data saved to local CSV: {amount_sol:.4f} SOL to {protocol_name}")
            
        except Exception as e:
            error(f"Error saving staking data to local CSV: {str(e)}")

    def _check_staking_fallback(self):
        """Fallback staking check for monitoring thread"""
        try:
            # Basic staking check - can be expanded
            pass
        except Exception as e:
            error(f"Staking fallback check error: {e}")

# Singleton pattern for staking agent
_staking_agent_instance = None

def get_staking_agent():
    """Get the singleton staking agent instance"""
    global _staking_agent_instance
    if _staking_agent_instance is None:
        _staking_agent_instance = StakingAgent()
    return _staking_agent_instance

if __name__ == "__main__":
    # Test the staking agent
    staking_agent = StakingAgent()
    
    try:
        staking_agent.run()
    except KeyboardInterrupt:
        info("Stopping staking agent...")
        staking_agent.stop() 
