"""
Anarcho Capital's CopyBot Agent
Analyzes current copybot positions to identify opportunities for increased position sizes

think about list
- not all these tokens will have OHLCV data so we need to address that some how
- good to pass in BTC/ETH data too in order to see market structure
"""

import os
import sys
import time
import traceback
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional, Union, Tuple, Any
import threading
from src import config

# Add the directory containing wallet_tracker.py to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Force debug logging to console for debugging purposes
try:
    config.SHOW_DEBUG_IN_CONSOLE = True  # Override the config setting
    from src.scripts.shared_services.logger import info
    info("Debug logging enabled for console output")
except:
    print("Could not override debug setting, make sure to check the log file for debug messages")

# Import the wallet tracker instead of token list tool
from src.scripts.wallet.wallet_tracker import WalletTracker

# Rest of your imports
import anthropic
import openai
from termcolor import colored, cprint
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import re
import src.config as config
# LAZY IMPORT: nice_funcs will be imported when needed to avoid circular imports
from src.scripts.data_processing.ohlcv_collector import collect_all_tokens, collect_token_data
from concurrent.futures import ThreadPoolExecutor

# Try importing PySide6 with fallback
try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    # Define dummy classes for testing
    class QObject:
        pass
    
    class Signal:
        def __init__(self, *args):
            self.callbacks = []
        
        def emit(self, *args):
            for callback in self.callbacks:
                callback(*args)
        
        def connect(self, callback):
            """Add the callback function to the list of callbacks"""
            self.callbacks.append(callback)

# Import logging utilities
from src.scripts.shared_services.logger import debug, info, warning, error, critical, system

# Import shared services for better coordination
from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator, AgentType
from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
from src.scripts.shared_services.shared_api_manager import get_shared_api_manager
from src.scripts.trading.position_manager import get_position_manager, PositionRequest, PositionAction
from src.scripts.data_processing.change_deduplicator import get_change_deduplicator
# Trade lock manager removed - now using SimpleAgentCoordinator

# Cloud database import
try:
    from src.scripts.database.cloud_database import get_cloud_database_manager
    CLOUD_DB_AVAILABLE = True
except ImportError:
    CLOUD_DB_AVAILABLE = False

# Import leverage utilities
try:
    from src.scripts.utilities.leverage_utils import (
        check_hyperliquid_available, get_hl_symbol, 
        hl_entry, hl_exit, hl_partial_exit, 
        get_hl_positions, get_funding_rates
    )
    LEVERAGE_UTILS_AVAILABLE = True
except ImportError:
    LEVERAGE_UTILS_AVAILABLE = False


# All configuration values are now imported from src.config

AI_ANALYSIS_PATH = os.path.join(os.getcwd(), 'src', 'data', 'ai_analysis.csv')

class CopyBotAgent(QObject):
    """Anarcho Capital's CopyBot Agent 🤖"""
    
    # Update the signal to include change_percent and symbol
    analysis_complete = Signal(str, str, str, str, str, str, str, str, str)  # timestamp, action, token, token_symbol, analysis, confidence, price, change_percent, token_mint
    changes_detected = Signal(dict)  # changes dictionary from TokenAccountTracker
    mirror_mode_active = Signal(bool)  # Signal to indicate mirror mode is active
    order_executed = Signal(str, str, str, float, float, float, object, str, str, str)  # agent_name, action, token, amount, entry_price, exit_price, pnl, wallet_address, mint_address, ai_analysis
    
    def _get_nice_funcs(self):
        """Lazy load nice_funcs to avoid circular imports"""
        if not hasattr(self, '_nice_funcs'):
            try:
                from src import nice_funcs
                self._nice_funcs = nice_funcs
            except ImportError as e:
                error(f"Failed to import nice_funcs: {e}")
                self._nice_funcs = None
        return self._nice_funcs
    
    def __init__(self):
        """Initialize the CopyBot agent with multiple LLM options"""
        super().__init__()  # Initialize QObject
        load_dotenv()
        
        # Track if this is the first run (to skip analysis and execution if configured)
        self.is_first_run = True
        
        # Add market data cache to avoid collecting data more than once
        self.market_data_cache = {}
        
        # AI confirmation exit targets (disabled - AI Analysis handles exits)
        if config.AI_EXIT_TARGETS_ENABLED:
            self.exit_targets = {}  # {token_address: {'target_pct': float, 'stop_loss_pct': float, 'entry_price': float, 'timestamp': float}}
        else:
            self.exit_targets = {}  # Keep for compatibility but disabled
        
        # Get API keys
        self.anthropic_key = os.getenv("ANTHROPIC_KEY")  # Updated env var name
        self.openai_key = os.getenv("OPENAI_KEY")
        self.deepseek_key = os.getenv("DEEPSEEK_KEY")
        
        # Initialize Anthropic client if key exists
        if self.anthropic_key:
            self.anthropic_client = anthropic.Anthropic()  # Updated to new format
        else:
            self.anthropic_client = None
            warning("No Anthropic API key found. Claude models will not be available.")
        
        # Initialize OpenAI client if key exists
        if self.openai_key:
            self.openai_client = openai.OpenAI(api_key=self.openai_key)
        else:
            self.openai_client = None
            warning("No OpenAI API key found. GPT models will not be available.")
            
        # Initialize DeepSeek client if key exists
        if self.deepseek_key:
            self.deepseek_client = openai.OpenAI(
                api_key=self.deepseek_key,
                base_url=config.DEEPSEEK_BASE_URL
            )
        else:
            self.deepseek_client = None
            warning("No DeepSeek API key found. DeepSeek models will not be available.")
            
        # Initialize shared services
        self.data_coordinator = get_shared_data_coordinator()
        self.price_service = get_optimized_price_service()
        self.api_manager = get_shared_api_manager()
        self.position_manager = get_position_manager()
        self.change_deduplicator = get_change_deduplicator()
        # Trade lock manager removed - now using SimpleAgentCoordinator
        
        # Register with data coordinator
        self.data_coordinator.register_agent(AgentType.COPYBOT, f"copybot_agent_{id(self)}")
        
        # Agent identifier for position tracking
        self.agent_id = f"copybot_agent_{id(self)}"
            
        # Check trading mode and leverage availability
        self.trading_mode = config.TRADING_MODE.lower()
        if self.trading_mode not in ["spot", "leverage"]:
            warning(f"Invalid TRADING_MODE: {config.TRADING_MODE}. Defaulting to 'spot'.")
            self.trading_mode = "spot"
            
        info(f"Trading Mode: {self.trading_mode.upper()}")
        
        # Check hyperliquid availability if in leverage mode
        self.leverage_available = False
        if self.trading_mode == "leverage":
            if not LEVERAGE_UTILS_AVAILABLE:
                warning("Leverage trading utilities not available. Falling back to spot trading.")
                self.trading_mode = "spot"
            elif not config.USE_HYPERLIQUID:
                warning("Hyperliquid is disabled in config. Falling back to spot trading.")
                self.trading_mode = "spot"
            else:
                # Test hyperliquid connection
                self.leverage_available = check_hyperliquid_available()
                if not self.leverage_available:
                    warning("Hyperliquid connection failed. Falling back to spot trading.")
                    self.trading_mode = "spot"
                else:
                    info("Hyperliquid connection verified. Leverage trading enabled!")
        
        # Check if necessary functions exist in nice_funcs
        self.ai_analysis_available = (
            (self.anthropic_client and config.COPYBOT_MODEL_OVERRIDE == "deepseek-reasoner") or
            (self.deepseek_client and config.COPYBOT_MODEL_OVERRIDE in ["deepseek-chat", "deepseek-reasoner"]) or
            (self.openai_client and config.COPYBOT_MODEL_OVERRIDE.startswith("gpt-"))
        )
        
        if not self.ai_analysis_available:
            warning("No AI providers available. CopyBot will run in mirror-only mode.")
            self.mirror_mode_active.emit(True)
            
        # Add config value validation to prevent NoneType errors
        if not hasattr(config, 'COPYBOT_WALLET_ACTION_WEIGHT') or config.COPYBOT_WALLET_ACTION_WEIGHT is None:
            config.COPYBOT_WALLET_ACTION_WEIGHT = 0.7  # Default value
            warning("COPYBOT_WALLET_ACTION_WEIGHT not set, using default value 0.7")
            
        # Check for required trading functions in nice_funcs
        required_functions = ['ai_entry', 'chunk_kill', 'get_token_balance_usd']
        nice_funcs = self._get_nice_funcs()
        missing_functions = [func for func in required_functions if not hasattr(nice_funcs, func)] if nice_funcs else required_functions
        if missing_functions:
            warning(f"ERROR: Missing required function(s) in nice_funcs: {', '.join(missing_functions)}")
            warning("CopyBot may not function correctly without these.")
            
        # Check for optional functions and create implementation if missing
        if not nice_funcs or not hasattr(nice_funcs, 'partial_kill'):
            warning("partial_kill function not found in nice_funcs. Adding a basic implementation.")
            # Add a partial_kill implementation to nice_funcs
            def partial_kill_implementation(token, percentage, max_usd_order_size, slippage):
                """Basic implementation of partial_kill that uses chunk_kill"""
                info(f"Using basic partial_kill implementation to sell {percentage*100:.1f}% of {token}")
                
                # Track timing for the operation
                start_time = time.time()
                max_execution_time = 60  # 1 minute timeout for the entire operation
                
                try:
                    # Check if we have the token balance
                    nf = self._get_nice_funcs()
                    if not nf:
                        error("nice_funcs not available")
                        return False
                        
                    balance = nf.get_token_balance_usd(token)
                    if balance <= 0:
                        warning(f"No balance found for {token}")
                        return False
                        
                    # For now, we'll implement a simple version that just does a full sell if percentage > 0.5
                    # and does nothing if percentage < 0.5
                    if percentage >= 0.5:
                        info(f"Percentage {percentage*100:.1f}% >= 50%, doing full sell")
                        # Execute with timeout check
                        success = nf.chunk_kill(token)
                        
                        # Check execution time
                        elapsed = time.time() - start_time
                        if elapsed > max_execution_time:
                            warning(f"Partial kill operation timed out after {elapsed:.2f} seconds")
                            return False
                            
                        if success:
                            info(f"Partial kill completed successfully in {elapsed:.2f} seconds")
                        return success
                    else:
                        info(f"Percentage {percentage*100:.1f}% < 50%, skipping sell (not supported by basic implementation)")
                        return False
                except Exception as e:
                    elapsed = time.time() - start_time
                    error(f"Error in partial_kill after {elapsed:.2f} seconds: {str(e)}")
                    return False
                    
            # Add the implementation to nice_funcs module
            if nice_funcs:
                setattr(nice_funcs, 'partial_kill', partial_kill_implementation)
            info("Added basic partial_kill implementation")
        
        # Set AI parameters - use config values
        self.ai_model = config.AI_MODEL
        self.ai_temperature = config.AI_TEMPERATURE
        self.ai_max_tokens = config.AI_MAX_TOKENS
        
        # Initialize tracked wallets from config
        self.tracked_wallets = config.WALLETS_TO_TRACK
        info(f"📊 CopyBot tracking {len(self.tracked_wallets)} wallets: {[w[:8] + '...' for w in self.tracked_wallets]}")
        
        # Deduplication tracking
        self.recent_transactions = {}  # signature -> timestamp
        self.transaction_window = 10  # seconds
        
        # Model settings
        if self.ai_analysis_available:
            info(f"Using AI Model: {config.COPYBOT_MODEL_OVERRIDE if config.COPYBOT_MODEL_OVERRIDE != '0' else self.ai_model}")
        
        self.recommendations_df = pd.DataFrame(columns=['token', 'action', 'confidence', 'reasoning'])
        info("Anarcho Capital's CopyBot Agent initialized!" + 
              (" (Mirror mode)" if not self.ai_analysis_available else " with multi-model support!") +
              (" with LEVERAGE trading" if self.trading_mode == "leverage" else " with SPOT trading"))
        
        # Load chat models for AI analysis
        self.models = {
            "claude-3-haiku-20240307": None,
            "claude-3-sonnet-20240229": None,
            "gpt-4-turbo": None,
            "deepseek-reasoner": None
        }
        self.model_name = config.AI_MODEL
        
        # AI analysis availability - use config setting instead of env var
        try:
            from src.config import ENABLE_AI_ANALYSIS
            self.ai_analysis_available = ENABLE_AI_ANALYSIS and (
                (self.anthropic_client is not None) or 
                (self.deepseek_client is not None) or 
                (self.openai_client is not None)
            )
            if not self.ai_analysis_available:
                if not ENABLE_AI_ANALYSIS:
                    info("AI Analysis is disabled in config settings. Running in mirror-only mode.")
                else:
                    warning("No AI models available even though AI Analysis is enabled. Check API keys.")
                self.mirror_mode_active.emit(True)
            else:
                info("AI Analysis is enabled and available.")
        except ImportError:
            warning("ENABLE_AI_ANALYSIS not found in config. Defaulting to disabled for better performance.")
            self.ai_analysis_available = False
        
        # Get trading mode
        self.trading_mode = "spot"  # Default to spot trading
        try:
            self.trading_mode = os.getenv("TRADING_MODE", "spot").lower()
        except:
            pass
        
        # Check for leverage trading availability
        self.leverage_available = False
        try:
            from src.leverage import init_hl, get_hl_positions, get_hl_symbol, hl_entry, hl_exit
            self.leverage_available = True
            if self.ai_analysis_available:
                info("with multi-model support!", end=" ")
            info(f"with {self.trading_mode.upper()} trading")
        except Exception as e:
            debug(f"Failed to load leverage trading: {e}", file_only=True)
            if self.ai_analysis_available:
                info("with multi-model support!")
            else:
                info("")
        
    def load_portfolio_data(self, existing_wallet_results=None, changes=None):
        """Load current copybot portfolio data from tracked wallets"""
        try:
            # Use existing wallet results if provided (from run_analysis_cycle)
            wallet_results = existing_wallet_results
            
            # If no existing results were provided, try to get cached data first
            if wallet_results is None:
                # Don't call track_all_wallets again - it should already be called in run_analysis_cycle
                # Use the existing TokenAccountTracker to get the cached data
                tracker = WalletTracker()
                cached_data, _ = tracker.load_cache()
                
                # The cache structure is different from what we need, extract the actual data
                wallet_results = cached_data.get('data', {})
                
                # If no data exists, try to get fresh data but only as a last resort
                if not wallet_results:
                    debug("No cached wallet data found, fetching fresh data", file_only=True)
                    wallet_results = tracker.track_all_wallets()

            # Ensure wallet_results is a dictionary
            if not isinstance(wallet_results, dict):
                warning("Invalid wallet results format. Expected a dictionary.")
                return False
            
            # Create a set of tokens to process if changes are provided
            tokens_to_process = set()
            if changes:
                for wallet, wallet_changes in changes.items():
                    # Add new tokens
                    for token_mint in wallet_changes.get('new', {}):
                        tokens_to_process.add(token_mint)
                    # Add removed tokens
                    for token_mint in wallet_changes.get('removed', {}):
                        tokens_to_process.add(token_mint)
                    # Add modified tokens
                    for token_mint in wallet_changes.get('modified', {}):
                        tokens_to_process.add(token_mint)
                        
                info(f"Processing only {len(tokens_to_process)} tokens with detected changes")
                
            # Convert the wallet results into a DataFrame that matches the expected format
            portfolio_data = []
            for wallet, tokens in wallet_results.items():
                debug(f"Processing {len(tokens)} tokens for wallet: {wallet}", file_only=True)
                for token in tokens:
                    token_mint = token['mint']
                    
                    # Skip tokens not in the changes list if changes are provided
                    if changes and token_mint not in tokens_to_process:
                        continue
                        
                    debug(f"Token mint: {token_mint}", file_only=True)
                    
                    # Check if token data is already in the cache
                    usd_value = 0
                    name = 'Unknown'
                    
                    if hasattr(self, 'market_data_cache') and token_mint in self.market_data_cache:
                        # Use cached data
                        token_data = self.market_data_cache[token_mint]
                        debug(f"Using cached market data for {token_mint}", file_only=True)
                        
                        if token_data is not None and not token_data.empty:
                            if 'price' in token_data.columns:
                                usd_value = token_data['price'].iloc[-1] * float(token['amount'])
                            if 'name' in token_data.columns:
                                name = token_data['name'].iloc[-1]
                    else:
                        # Fetch token data only if not in cache
                        debug(f"Fetching market data for {token_mint}", file_only=True)
                        token_data = collect_token_data(token_mint)
                        
                        # Cache the data for future use
                        if not hasattr(self, 'market_data_cache'):
                            self.market_data_cache = {}
                        
                        if token_data is not None:
                            self.market_data_cache[token_mint] = token_data
                            
                            if not token_data.empty:
                                if 'price' in token_data.columns:
                                    usd_value = token_data['price'].iloc[-1] * float(token['amount'])
                                if 'name' in token_data.columns:
                                    name = token_data['name'].iloc[-1]
                    
                    portfolio_data.append({
                        'Mint Address': token_mint,
                        'Amount': float(token['amount']),
                        'USD Value': usd_value,
                        'name': name,
                    })

            if not portfolio_data:
                warning("No portfolio data found.")
                self.portfolio_df = pd.DataFrame(columns=['wallet', 'Mint Address', 'amount', 'decimals'])
                return False  # Return False if no data is found

            self.portfolio_df = pd.DataFrame(portfolio_data)
            info("Current copybot portfolio loaded from tracked wallets!")
            debug(f"\n{self.portfolio_df}", file_only=True)
            return True

        except Exception as e:
            error(f"Error loading portfolio data: {str(e)}")
            self.portfolio_df = pd.DataFrame(columns=['wallet', 'Mint Address', 'amount', 'decimals'])
            return False  # Return False if an error occurs
            
    def get_ai_response(self, prompt):
        """Get response from the selected AI model"""
        start_time = time.time()
        
        # Start a monitoring thread to alert on timeout
        timeout_threshold = 30  # Alert after 30 seconds
        model_timeout_alert = False
        # Add a flag to signal when the API call is complete
        api_call_complete = threading.Event()
        
        def monitor_timeout():
            nonlocal model_timeout_alert
            time_waiting = 0
            print(f"⏱️ Started monitoring API call to {selected_model}")
            last_update = 0
            while time.time() - start_time < 180 and not api_call_complete.is_set():  # Monitor for up to 3 minutes or until call completes
                current_time = time.time() - start_time
                # Print an update every 10 seconds
                if int(current_time) // 10 > last_update:
                    last_update = int(current_time) // 10
                    print(f"⏱️ API call to {selected_model} running for {current_time:.1f} seconds...")
                
                if current_time > timeout_threshold and not model_timeout_alert:
                    model_timeout_alert = True
                    warning(f"AI MODEL TIMEOUT WARNING: API call to {selected_model} has been running for {current_time:.1f} seconds!")
                    warning(f"API might be overloaded or unresponsive. Consider changing models or reducing prompt size.")
                time.sleep(5)  # Check every 5 seconds
            
            # If the API call is complete, add a final status message
            if api_call_complete.is_set():
                final_time = time.time() - start_time
                print(f"⏱️ API call to {selected_model} completed in {final_time:.1f} seconds")
        
        try:
            # Select the model based on settings hierarchy:
            # 1. Use agent-specific override if set
            # 2. Otherwise fall back to global AI model
            selected_model = config.COPYBOT_MODEL_OVERRIDE if config.COPYBOT_MODEL_OVERRIDE != "0" else self.ai_model
            
            info(f"Using AI model: {selected_model}")
            
            # Start monitoring thread
            monitoring_thread = threading.Thread(target=monitor_timeout)
            monitoring_thread.daemon = True
            monitoring_thread.start()
            
            # Use the appropriate client based on the selected model
            if "deepseek" in selected_model.lower() and self.deepseek_client:
                # Use DeepSeek client with the exact model specified
                info(f"Using DeepSeek {selected_model} model for analysis...")
                debug(f"TIMING: Starting DeepSeek API request at {time.strftime('%H:%M:%S')}", file_only=False)
                print(f"⏱️ DIRECT TIMING: Starting DeepSeek API request at {time.strftime('%H:%M:%S')}")
                api_start = time.time()
                
                try:
                    response = self.deepseek_client.chat.completions.create(
                        model=selected_model,  # Use the exact selected model, not hardcoded
                        messages=[
                            {"role": "system", "content": "You are Anarcho Capital's CopyBot Agent. Analyze portfolio data and recommend BUY, SELL, or NOTHING."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=self.ai_max_tokens,
                        temperature=self.ai_temperature,
                        timeout=30  # Reduced timeout from 60 to 30 seconds
                    )
                    api_time = time.time() - api_start
                    debug(f"TIMING: DeepSeek API request completed in {api_time:.2f} seconds", file_only=False)
                    print(f"⏱️ DIRECT TIMING: DeepSeek API request completed in {api_time:.2f} seconds")
                    # Signal that the API call is complete
                    api_call_complete.set()
                    return response.choices[0].message.content
                except Exception as e:
                    api_time = time.time() - api_start
                    error(f"DeepSeek API request failed after {api_time:.2f} seconds: {str(e)}")
                    print(f"⏱️ DIRECT TIMING: DeepSeek API request FAILED after {api_time:.2f} seconds: {str(e)}")
                    # Signal that the API call is complete even if it failed
                    api_call_complete.set()
                    # Fall back to a different model if DeepSeek fails
                    if self.anthropic_client:
                        warning("Falling back to Claude due to DeepSeek failure")
                        return self._fallback_claude_request(prompt)
                    elif self.openai_client:
                        warning("Falling back to OpenAI due to DeepSeek failure")
                        return self._fallback_openai_request(prompt)
                    else:
                        raise e  # Re-raise if no fallback available
                
            elif selected_model.startswith("gpt-") and self.openai_client:
                info(f"Using OpenAI {selected_model} model for analysis...")
                debug(f"TIMING: Starting OpenAI API request at {time.strftime('%H:%M:%S')}", file_only=False)
                api_start = time.time()
                
                try:
                    response = self.openai_client.chat.completions.create(
                        model=selected_model,
                        messages=[
                            {"role": "system", "content": "You are Anarcho Capital's CopyBot Agent. Analyze portfolio data and recommend BUY, SELL, or NOTHING."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=self.ai_max_tokens,
                        temperature=self.ai_temperature,
                        timeout=30  # Reduced timeout from 60 to 30 seconds
                    )
                    api_time = time.time() - api_start
                    debug(f"TIMING: OpenAI API request completed in {api_time:.2f} seconds", file_only=False)
                    # Signal that the API call is complete
                    api_call_complete.set()
                    return response.choices[0].message.content
                except Exception as e:
                    api_time = time.time() - api_start
                    error(f"OpenAI API request failed after {api_time:.2f} seconds: {str(e)}")
                    # Signal that the API call is complete even if it failed
                    api_call_complete.set()
                    # Fall back to Claude if OpenAI fails
                    if self.anthropic_client:
                        warning("Falling back to Claude due to OpenAI failure")
                        return self._fallback_claude_request(prompt)
                    else:
                        raise e  # Re-raise if no fallback available
                
            elif self.anthropic_client:
                # For Claude models
                info(f"Using Claude {selected_model} model for analysis...")
                debug(f"TIMING: Starting Claude API request at {time.strftime('%H:%M:%S')}", file_only=False)
                api_start = time.time()
                
                try:
                    message = self.anthropic_client.messages.create(
                        model=selected_model,
                        max_tokens=self.ai_max_tokens,
                        temperature=self.ai_temperature,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }]
                    )
                    
                    # Handle Claude response format
                    response = message.content
                    if isinstance(response, list):
                        response = '\n'.join([
                            item.text if hasattr(item, 'text') else str(item)
                            for item in response
                        ])
                    api_time = time.time() - api_start
                    debug(f"TIMING: Claude API request completed in {api_time:.2f} seconds", file_only=False)
                    # Signal that the API call is complete
                    api_call_complete.set()
                    return response
                except Exception as e:
                    api_time = time.time() - api_start
                    error(f"Claude API request failed after {api_time:.2f} seconds: {str(e)}")
                    # Signal that the API call is complete even if it failed
                    api_call_complete.set()
                    # Fall back to OpenAI if Claude fails
                    if self.openai_client:
                        warning("Falling back to OpenAI due to Claude failure")
                        return self._fallback_openai_request(prompt)
                    else:
                        raise e  # Re-raise if no fallback available
            else:
                raise ValueError(f"No AI client available for model: {selected_model}. Please check your API keys.")
                
        except Exception as e:
            total_time = time.time() - start_time
            warning(f"Error getting AI response after {total_time:.2f} seconds: {str(e)}")
            # Signal that the API call is complete
            api_call_complete.set()
            return "NOTHING\nError: Could not get AI analysis. No action recommended."
            
    def _fallback_claude_request(self, prompt):
        """Fallback to Claude when other models fail"""
        debug(f"TIMING: Starting Claude fallback request", file_only=True)
        api_start = time.time()
        # Create an event to signal completion
        api_call_complete = threading.Event()
        
        try:
            message = self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",  # Use haiku as fallback for speed
                max_tokens=self.ai_max_tokens,
                temperature=self.ai_temperature,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Handle Claude response format
            response = message.content
            if isinstance(response, list):
                response = '\n'.join([
                    item.text if hasattr(item, 'text') else str(item)
                    for item in response
                ])
            api_time = time.time() - api_start
            debug(f"TIMING: Claude fallback completed in {api_time:.2f} seconds", file_only=True)
            # Signal that the API call is complete
            api_call_complete.set()
            return response
        except Exception as e:
            api_time = time.time() - api_start
            error(f"Claude fallback failed after {api_time:.2f} seconds: {str(e)}")
            # Signal that the API call is complete even if it failed
            api_call_complete.set()
            return "NOTHING\nError: All AI models failed. No action recommended."
            
    def _fallback_openai_request(self, prompt):
        """Fallback to OpenAI when other models fail"""
        debug(f"TIMING: Starting OpenAI fallback request", file_only=True)
        api_start = time.time()
        # Create an event to signal completion
        api_call_complete = threading.Event()
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Use 3.5-turbo as fallback for speed
                messages=[
                    {"role": "system", "content": "You are Anarcho Capital's CopyBot Agent. Analyze portfolio data and recommend BUY, SELL, or NOTHING."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.ai_max_tokens,
                temperature=self.ai_temperature
            )
            api_time = time.time() - api_start
            debug(f"TIMING: OpenAI fallback completed in {api_time:.2f} seconds", file_only=True)
            # Signal that the API call is complete
            api_call_complete.set()
            return response.choices[0].message.content
        except Exception as e:
            api_time = time.time() - api_start
            error(f"OpenAI fallback failed after {api_time:.2f} seconds: {str(e)}")
            # Signal that the API call is complete even if it failed
            api_call_complete.set()
            return "NOTHING\nError: All AI models failed. No action recommended."
            
    def save_ai_analysis(self, timestamp, action, token, token_symbol, analysis, confidence, price, change_percent=None, token_mint=None, token_name=None):
        """Save an AI analysis event to local CSV first, then sync to cloud database"""
        try:
            # PRIMARY: Save to local CSV first
            self._save_ai_analysis_to_csv(timestamp, action, token, token_symbol, analysis, confidence, price, change_percent, token_mint, token_name)
            
            # SECONDARY: Try to sync to cloud database
            if CLOUD_DB_AVAILABLE:
                try:
                    db_manager = get_cloud_database_manager()
                    if db_manager is not None:
                        # Save to cloud database
                        query = '''
                            INSERT INTO ai_analysis (
                                agent_name, action, token_symbol, token_mint, analysis_text,
                                confidence, price_usd, change_percent, token_name, metadata
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        '''
                        
                        params = (
                            'copybot',  # agent_name
                            action,  # action
                            token_symbol,  # token_symbol
                            token_mint,  # token_mint
                            analysis,  # analysis_text
                            confidence,  # confidence
                            price,  # price_usd
                            change_percent,  # change_percent
                            token_name,  # token_name
                            json.dumps({'timestamp': timestamp, 'token': token})  # metadata
                        )
                        
                        db_manager.execute_query(query, params, fetch=False)
                        debug(f"✅ AI analysis synced to cloud database: {action} on {token_symbol}")
                        
                except Exception as cloud_error:
                    warning(f"⚠️ Cloud database sync failed (local data saved): {cloud_error}")
            
        except Exception as e:
            error(f"Error saving AI analysis: {str(e)}")
    
    def _save_ai_analysis_to_csv(self, timestamp, action, token, token_symbol, analysis, confidence, price, change_percent=None, token_mint=None, token_name=None):
        """Fallback method to save AI analysis to CSV file"""
        try:
            os.makedirs(os.path.dirname(AI_ANALYSIS_PATH), exist_ok=True)
            entry = {
                'timestamp': timestamp,
                'action': action,
                'token': token,
                'token_symbol': token_symbol,
                'analysis': analysis,
                'confidence': confidence,
                'price': price,
                'change_percent': change_percent,
                'token_mint': token_mint,
                'token_name': token_name
            }
            df = pd.DataFrame([entry])
            # If file exists, prepend new entry
            if os.path.isfile(AI_ANALYSIS_PATH):
                existing = pd.read_csv(AI_ANALYSIS_PATH)
                df = pd.concat([df, existing], ignore_index=True)
                df = df.head(25)  # Limit to 25 records
            df.to_csv(AI_ANALYSIS_PATH, index=False)
            debug(f"📁 AI analysis saved to CSV fallback: {action} on {token_symbol}")
            
        except Exception as e:
            error(f"Error saving AI analysis to CSV: {str(e)}")

    def analyze_position(self, token, token_status=None, wallet_action=None, pct_change=None):
        """Analyze a single portfolio position with wallet action context"""
        analysis_start_time = time.time()
        debug(f"TIMING: Starting analysis for token {token}", file_only=False)

        try:
            if token in config.EXCLUDED_TOKENS:
                warning(f"Skipping analysis for excluded token: {token}")
                return None

            # Check if token exists in portfolio_df
            position_data = self.portfolio_df[self.portfolio_df['Mint Address'] == token]
            
            # Special handling for removed tokens that might not be in portfolio_df anymore
            if position_data.empty and token_status == "removed":
                warning(f"Token {token} was removed and is not in current portfolio - creating synthetic data for analysis")
                # Create synthetic position data for analysis
                position_data = pd.DataFrame([{
                    'Mint Address': token,
                    'Amount': 0,  # Amount is zero since it was removed
                    'USD Value': 0,  # USD value is zero
                    'name': f"Removed Token ({token[:6]}...)",  # Use shortened token mint as name
                }])
            elif position_data.empty:
                warning(f"No portfolio data for token: {token}")
                elapsed_time = time.time() - analysis_start_time
                debug(f"TIMING: Analysis aborted due to missing data after {elapsed_time:.2f} seconds", file_only=False)
                return None
                
            info(f"\nAnalyzing position for {position_data['name'].values[0]}...")
            debug(f"Current Amount: {position_data['Amount'].values[0]}", file_only=True)
            debug(f"USD Value: ${position_data['USD Value'].values[0]:.2f}", file_only=True)
            
            # Add wallet action context if available
            if token_status:
                debug(f"Token Status: {token_status}, Percentage Change: {pct_change}", file_only=True)

            # Get token market data - USE CACHE
            market_data_start = time.time()
            debug(f"Getting market data for token: {token}", file_only=True)
            token_market_data = None
            
            # Check cache first - this is the important part!
            if token in self.market_data_cache:
                debug(f"Using cached market data for {token}", file_only=True)
                token_market_data = self.market_data_cache[token]
                market_data_elapsed = time.time() - market_data_start
                debug(f"TIMING: Retrieved cached market data in {market_data_elapsed:.2f} seconds", file_only=False)
            else:
                # Only collect if not in cache
                debug(f"Collecting market data for {token}", file_only=True)
                data_collection_start = time.time()
                token_market_data = collect_token_data(token)
                data_collection_elapsed = time.time() - data_collection_start
                debug(f"TIMING: Market data collection took {data_collection_elapsed:.2f} seconds", file_only=False)
                
                # Cache the data for future reference
                if token_market_data is not None:
                    self.market_data_cache[token] = token_market_data
                
                market_data_elapsed = time.time() - market_data_start
                debug(f"TIMING: Total market data retrieval took {market_data_elapsed:.2f} seconds", file_only=False)
            
            # If no data available (either from cache or collection)
            if token_market_data is None or (isinstance(token_market_data, pd.DataFrame) and token_market_data.empty):
                warning("No market data found")
                token_market_data = "No market data available"

            # Prepare wallet action context for the AI prompt
            prompt_start = time.time()
            wallet_context = ""
            action_weight = 0
            
            if token_status == "new":
                wallet_context = "IMPORTANT: The tracked wallet has just BOUGHT this token. This is a STRONG BUY signal."
                action_weight = config.COPYBOT_WALLET_ACTION_WEIGHT  # Weight toward BUY
            elif token_status == "removed":
                wallet_context = "IMPORTANT: The tracked wallet has SOLD ALL holdings of this token. This is a STRONG SELL signal."
                action_weight = -config.COPYBOT_WALLET_ACTION_WEIGHT  # Weight toward SELL
            elif token_status == "modified" and pct_change is not None:
                # Fix the logic - ensure pct_change is treated correctly
                # Positive pct_change means the wallet INCREASED holdings (BUY signal)
                # Negative pct_change means the wallet DECREASED holdings (SELL signal)
                
                # Add debug logging to verify the value
                debug(f"Processing modified token with pct_change = {pct_change}", file_only=True)
                
                # Use absolute value check first to determine magnitude
                abs_pct_change = abs(pct_change)
                
                # Check if token amount actually increased or decreased based on pct_change sign
                if pct_change > 0:
                    # Wallet INCREASED position - BUY signal
                    if abs_pct_change > 20:
                        wallet_context = f"IMPORTANT: The tracked wallet has SIGNIFICANTLY INCREASED holdings of this token by {abs_pct_change:.2f}%. This is a STRONG BUY signal."
                        action_weight = config.COPYBOT_WALLET_ACTION_WEIGHT * 0.9  # 90% weight toward BUY
                    else:
                        wallet_context = f"IMPORTANT: The tracked wallet has slightly increased holdings of this token by {abs_pct_change:.2f}%. This suggests a BUY signal."
                        action_weight = config.COPYBOT_WALLET_ACTION_WEIGHT * 0.5  # 50% weight toward BUY
                else:
                    # Wallet DECREASED position - SELL signal
                    if abs_pct_change > 20:
                        wallet_context = f"IMPORTANT: The tracked wallet has SIGNIFICANTLY DECREASED holdings of this token by {abs_pct_change:.2f}%. This is a STRONG SELL signal."
                        action_weight = -config.COPYBOT_WALLET_ACTION_WEIGHT * 0.9  # 90% weight toward SELL
                    else:
                        wallet_context = f"IMPORTANT: The tracked wallet has slightly decreased holdings of this token by {abs_pct_change:.2f}%. This suggests a SELL signal."
                        action_weight = -config.COPYBOT_WALLET_ACTION_WEIGHT * 0.5  # 50% weight toward SELL
            
            # Prepare context for LLM with wallet action context
            full_prompt = f"""
{wallet_context}

Your analysis should confirm or reject this signal based on market data, but give significant weight ({int(config.COPYBOT_WALLET_ACTION_WEIGHT*100)}%) to the wallet's action.

{config.PORTFOLIO_ANALYSIS_PROMPT.format(
    portfolio_data=position_data.to_string(),
    market_data=token_market_data
)}

Based on the wallet's action and your analysis, recommend: 
BUY (if you confirm the wallet's buy signal)
SELL (if you confirm the wallet's sell signal)
NOTHING (only if you have strong evidence against the wallet's action)

Confidence should reflect your agreement with the wallet's action, with higher confidence when your analysis agrees.
"""
            
            prompt_elapsed = time.time() - prompt_start
            debug(f"TIMING: Prompt preparation took {prompt_elapsed:.2f} seconds", file_only=False)
            
            info("\nSending data to AI for analysis...")
            
            # Get LLM analysis using the selected model
            ai_start = time.time()
            debug(f"TIMING: Starting AI request at {time.strftime('%H:%M:%S')}", file_only=False)
            response = self.get_ai_response(full_prompt)
            ai_elapsed = time.time() - ai_start
            debug(f"TIMING: AI response received after {ai_elapsed:.2f} seconds", file_only=False)
            
            # Log complete analysis to file only
            debug("AI Analysis Results:", file_only=True)
            debug("=" * 50, file_only=True)
            debug(response, file_only=True)
            debug("=" * 50, file_only=True)
            
            lines = response.split('\n')
            action = lines[0].strip() if lines else "NOTHING"
            
            # Extract confidence with proper regex and validation
            confidence = 0
            for line in lines:
                if 'confidence' in line.lower():
                    try:
                        # Look for patterns like "confidence: 65%" or "65% confidence"
                        match = re.search(r'confidence:?\s*(\d{1,3})\s*%|(\d{1,3})\s*%\s*confidence', line.lower())
                        if match:
                            # Use the first non-None group
                            confidence_str = match.group(1) if match.group(1) else match.group(2)
                            confidence = int(confidence_str)
                            # Validate the range
                            if confidence < 0 or confidence > 100:
                                warning(f"Invalid confidence value: {confidence}. Setting to default 50%.")
                                confidence = 50
                            break
                        else:
                            # Fallback to traditional method but with validation
                            digits = ''.join(filter(str.isdigit, line))
                            if digits:
                                # Check if the number is reasonable (between 0-100)
                                if len(digits) <= 3 and int(digits) <= 100:
                                    confidence = int(digits)
                                else:
                                    # If too large, try to extract just 2-3 digits that might be the confidence
                                    if len(digits) >= 2:
                                        # Try the first 2-3 digits
                                        potential_confidence = int(digits[:2]) if len(digits) >= 2 else int(digits)
                                        if potential_confidence <= 100:
                                            confidence = potential_confidence
                                        else:
                                            confidence = 50
                                    else:
                                        confidence = 50
                    except:
                        warning("Error parsing confidence value, using default 50%.")
                        confidence = 50
            
            # Final validation to ensure confidence is in range 0-100
            if confidence < 0 or confidence > 100:
                warning(f"Confidence value out of range: {confidence}. Clamping to 0-100.")
                confidence = max(0, min(confidence, 100))
            
            # Store recommendation
            store_start = time.time()
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
            
            # Extract token name and price
            token_name = position_data['name'].values[0] if not position_data.empty else "Unknown"
            token_symbol = position_data['symbol'].values[0] if not position_data.empty and 'symbol' in position_data.columns else "UNK"
            price = f"${position_data['USD Value'].values[0] / position_data['Amount'].values[0]:.4f}" if not position_data.empty and position_data['Amount'].values[0] > 0 else "N/A"
            
            # Try to extract change percentage from the analysis
            change_percent = None
            for line in lines:
                # Look for common patterns indicating percentage change
                if any(pattern in line.lower() for pattern in ['change', 'increase', 'decrease', 'moved', 'up by', 'down by']):
                    # Try to extract percentage values
                    percentage_match = re.search(r'(\+|-)?\s*(\d+\.?\d*)%', line)
                    if percentage_match:
                        sign = percentage_match.group(1) or ''
                        value = percentage_match.group(2)
                        change_percent = f"{sign}{value}"
                        break
            
            # Generate a timestamp for the analysis
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Store the mint address
            token_mint = token
            
            # Emit the analysis_complete signal with all relevant data
            results_processing_time = time.time() - store_start
            debug(f"TIMING: Results processing took {results_processing_time:.2f} seconds", file_only=True)
            
            self.analysis_complete.emit(
                timestamp,
                action,
                token_name,
                token_symbol,
                reasoning.split('\n')[0] if reasoning else "No analysis",
                str(confidence),
                price,
                change_percent if change_percent else None,
                token_mint
            )
            # Save to ai_analysis.csv
            self.save_ai_analysis(
                timestamp,
                action,
                token_name,
                token_symbol,
                reasoning.split('\n')[0] if reasoning else "No analysis",
                str(confidence),
                price,
                change_percent if change_percent else None,
                token_mint
            )
            
            info(f"\nSummary for {position_data['name'].values[0]}:")
            info(f"Action: {action}")
            info(f"Confidence: {confidence}%")
            info(f"Position Analysis Complete!")
            
            total_elapsed = time.time() - analysis_start_time
            debug(f"TIMING: Total analysis time for {token_name}: {total_elapsed:.2f} seconds", file_only=False)
            debug(f"TIMING: Analysis breakdown - Market Data: {market_data_elapsed:.2f}s, AI: {ai_elapsed:.2f}s, Processing: {results_processing_time:.2f}s", file_only=False)
            
            return response
            
        except Exception as e:
            elapsed_time = time.time() - analysis_start_time
            warning(f"Error analyzing position after {elapsed_time:.2f} seconds: {str(e)}")
            return None
            
    def execute_position_updates(self, wallet_results=None, changes=None):
        """Execute position updates by mirroring wallet transactions - NO AI ANALYSIS"""
        try:
            # If no changes were provided, try to get them
            if changes is None:
                info("No changes provided, fetching fresh data...")
                tracker = WalletTracker()
                cached_results, _ = tracker.load_cache()
                wallet_results, changes = tracker.track_wallets()
            
            if not changes:
                info("No wallet changes detected")
                return
                
            info(f"Mirroring wallet changes: {len(changes)} wallets with activity")
            
            # Check for allocation-based sell triggers BEFORE processing wallet changes
            self._check_allocation_sell_triggers()
            
            # Process each wallet's changes
            for wallet, wallet_changes in changes.items():
                # Handle BUY transactions (added tokens)
                for token_mint, token_data in wallet_changes.get('added', {}).items():
                    if self._should_stop_buying():
                        warning("CopyBot stopped - not executing BUY")
                        continue
                    
                    # Mirror the buy transaction
                    self._execute_mirror_buy(wallet, token_mint, token_data)
                
                # Handle SELL transactions (removed tokens)
                for token_mint, token_data in wallet_changes.get('removed', {}).items():
                    # Always execute sells - no stopping
                    self._execute_mirror_sell(wallet, token_mint, token_data)
                
                # Handle position changes (modified tokens)
                for token_mint, token_data in wallet_changes.get('modified', {}).items():
                    change = token_data.get('change', 0)
                    if change > 0:
                        # Position increased - mirror as buy
                        if self._should_stop_buying():
                            warning("CopyBot stopped - not executing position increase")
                            continue
                        self._execute_mirror_buy(wallet, token_mint, token_data)
                    elif change < 0:
                        # Position decreased - mirror as sell
                        self._execute_mirror_sell(wallet, token_mint, token_data)
                        
        except Exception as e:
            error(f"Error executing position updates: {str(e)}")
            return False

    def _execute_mirror_buy(self, wallet: str, token_mint: str, token_data: dict):
        """Execute buy transaction by mirroring the wallet action - NO AI ANALYSIS"""
        try:
            # Skip if token is excluded
            if token_mint in config.EXCLUDED_TOKENS:
                warning(f"Skipping buy for excluded token: {token_mint}")
                return
            
            token_name = token_data.get('name', 'Unknown')
            token_symbol = token_data.get('symbol', 'UNK')
            
            info(f"🔄 Mirroring BUY: {token_symbol} ({token_name})")
            
            # Set agent context for proper attribution
            from src.scripts.webhooks.webhook_handler import agent_context
            with agent_context("copybot"):
                # Use simple position sizing
                amount = self._calculate_simple_position_size()
                
                if config.PAPER_TRADING_ENABLED:
                    # Execute paper trading buy
                    try:
                        from src.paper_trading import execute_paper_trade
                        # Get current price for the trade
                        try:
                            from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
                            price_service = get_optimized_price_service()
                            price = price_service.get_price(token_mint) or 0.0
                        except:
                            price = 0.0
                        
                        # Calculate token amount from USD position size
                        if price > 0:
                            token_amount = amount / price
                        else:
                            warning(f"No price available for {token_symbol} - skipping buy")
                            return
                        
                        success = execute_paper_trade(token_mint, "BUY", token_amount, price, "copybot", token_symbol, token_name)
                        
                        if success:
                            info(f"✅ Successfully executed paper BUY: {token_symbol} ({token_name})")
                            
                            # Force portfolio tracker refresh so future lookups see the new position
                            try:
                                from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
                                tracker = get_portfolio_tracker()
                                if tracker:
                                    tracker.force_refresh_portfolio_data()
                            except Exception as e:
                                warning(f"Failed to refresh portfolio tracker after buy: {e}")
                            
                            # Emit order executed signal
                            self.order_executed.emit(
                                "CopyBot", "BUY", token_symbol, 
                                token_amount, price, amount, 0, "", token_mint, 
                                f"Mirrored wallet action: {wallet[:8]}..."
                            )
                        else:
                            warning(f"❌ Failed to execute paper BUY: {token_symbol} ({token_name})")
                            
                    except Exception as e:
                        error(f"Paper trading buy failed: {e}")
                        
                else:
                    # Execute live buy
                    try:
                        # Execute the buy
                        nf = self._get_nice_funcs()
                        if not nf:
                            warning("nice_funcs not available - skipping buy")
                            return
                        
                        info(f"Executing market buy for {token_symbol} with ${amount:.2f}")
                        success = nf.market_entry(token_symbol, amount, agent="copybot")
                        
                        if success:
                            info(f"✅ Successfully mirrored BUY: {token_symbol} ({token_name})")
                            # Emit order executed signal
                            self.order_executed.emit(
                                "CopyBot", "BUY", token_symbol, 
                                amount, 0, 0, 0, "", token_mint, 
                                f"Mirrored wallet action: {wallet[:8]}..."
                            )
                        else:
                            warning(f"❌ Failed to mirror BUY: {token_symbol} ({token_name})")
                            
                    except Exception as e:
                        error(f"Live trading buy failed: {e}")
                    
        except Exception as e:
            error(f"Error executing mirror buy: {str(e)}")

    def _execute_mirror_sell(self, wallet: str, token_mint: str, token_data: dict):
        """Execute sell transaction by mirroring the wallet action - NO AI ANALYSIS"""
        try:
            # Skip if token is excluded
            if token_mint in config.EXCLUDED_TOKENS:
                warning(f"Skipping sell for excluded token: {token_mint}")
                return
            
            token_name = token_data.get('name', 'Unknown')
            token_symbol = token_data.get('symbol', 'UNK')
            
            info(f"🔄 Mirroring SELL: {token_symbol} ({token_name})")
            
            # Use unified balance lookup for reliable balance check
            try:
                token_balance = self.get_token_balance(token_mint)
            except ImportError:
                # Fallback to existing method
                nf = self._get_nice_funcs()
                if not nf:
                    warning("nice_funcs not available - skipping sell")
                    return
                token_balance = nf.get_token_balance(token_mint)
            
            if token_balance <= 0:
                warning(f"No balance found for {token_symbol} ({token_name}) - skipping sell")
                # Emit success event since desired end state is achieved
                self.order_executed.emit(
                    "CopyBot", "SELL", token_symbol, 
                    0, 0, 0, 0, "", token_mint, 
                    f"Token not in wallet (already sold): {wallet[:8]}..."
                )
                return
            
            # Check SOL balance for transaction fees (skip in paper trading)
            if not config.PAPER_TRADING_ENABLED:
                nf = self._get_nice_funcs()
                if not nf:
                    warning("nice_funcs not available for gas check - skipping sell")
                    return
                    
                sol_balance = nf.get_token_balance(config.SOL_ADDRESS)
                min_sol_required = 0.01  # Minimum SOL needed for transaction fees
                
                if sol_balance < min_sol_required:
                    warning(f"❌ Insufficient SOL for transaction fees: {sol_balance:.6f} SOL < {min_sol_required} SOL")
                    warning(f"❌ Cannot execute sell for {token_symbol} - need SOL for gas fees")
                    return
                
                info(f"✅ SOL balance sufficient for sell: {sol_balance:.6f} SOL")
            
            # Execute the sell based on trading mode
            if config.PAPER_TRADING_ENABLED:
                # Execute paper trading sell
                try:
                    from src.paper_trading import execute_paper_trade
                    # Get current price for the trade
                    try:
                        from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
                        price_service = get_optimized_price_service()
                        price = price_service.get_price(token_mint) or 0.0
                    except:
                        price = 0.0
                    
                    success = execute_paper_trade(token_mint, "SELL", token_balance, price, "copybot", token_symbol, token_name)
                    
                    if success:
                        info(f"✅ Successfully mirrored paper SELL: {token_symbol} ({token_name})")
                        # Force portfolio tracker refresh so future lookups see the change
                        try:
                            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
                            tracker = get_portfolio_tracker()
                            if tracker:
                                tracker.force_refresh_portfolio_data()
                        except Exception as e:
                            warning(f"Failed to refresh portfolio tracker after sell: {e}")
                        
                        # Emit order executed signal
                        self.order_executed.emit(
                            "CopyBot", "SELL", token_symbol, 
                            0, 0, 0, 0, "", token_mint, 
                            f"Mirrored wallet action: {wallet[:8]}..."
                        )
                    else:
                        warning(f"❌ Failed to mirror paper SELL: {token_symbol} ({token_name})")
                        
                except Exception as e:
                    error(f"Paper trading sell failed: {e}")
                    
            else:
                # Execute live sell - use chunk_kill for better execution
                nf = self._get_nice_funcs()
                if not nf:
                    warning("nice_funcs not available for live sell")
                    return
                    
                success = nf.chunk_kill(token_mint)
                
                if success:
                    info(f"✅ Successfully mirrored SELL: {token_symbol} ({token_name})")
                    # Emit order executed signal
                    self.order_executed.emit(
                        "CopyBot", "SELL", token_symbol, 
                        0, 0, 0, 0, "", token_mint, 
                        f"Mirrored wallet action: {wallet[:8]}..."
                    )
                else:
                    warning(f"❌ Failed to mirror SELL: {token_symbol} ({token_name})")
                        
        except Exception as e:
            error(f"Error executing mirror sell: {str(e)}")

    def get_portfolio_data(self):
        """Get current portfolio data for self-stop checks"""
        try:
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            summary = tracker.get_portfolio_summary()
            
            # Get individual positions for constraint checks
            positions = []
            if config.PAPER_TRADING_ENABLED:
                try:
                    from src import paper_trading
                    df = paper_trading.get_paper_portfolio()
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            token = row['token_address']
                            # Skip SOL and USDC
                            if token not in [config.SOL_ADDRESS, config.USDC_ADDRESS]:
                                amount = float(row.get('amount', 0))
                                price = float(row.get('last_price', 0))
                                if amount > 0 and price > 0:
                                    value = amount * price
                                    if value >= config.DUST_THRESHOLD_USD:
                                        positions.append({
                                            'mint': token,
                                            'value_usd': value
                                        })
                except Exception as e:
                    from src.scripts.shared_services.logger import debug
                    debug(f"Error getting positions: {e}")
            
            # One-line observability log
            try:
                from src.scripts.shared_services.logger import debug
                total_value = float(summary.get('current_value', 0.0))
                usdc_balance = float(summary.get('usdc_balance', 0.0))
                sol_value = float(summary.get('sol_balance_usd', summary.get('sol_value_usd', 0.0)))
                usdc_pct = (usdc_balance / total_value) * 100 if total_value > 0 else 0.0
                sol_pct = (sol_value / total_value) * 100 if total_value > 0 else 0.0
                debug(f"CopyBot data source: portfolio_tracker (ts={summary.get('last_update', 'n/a')}) USDC%={usdc_pct:.1f}% SOL%={sol_pct:.1f}%")
            except Exception:
                pass

            return {
                'total_value_usd': summary.get('current_value', 0.0),
                'usdc_balance_usd': summary.get('usdc_balance', 0.0),
                # Use normalized alias provided by tracker; fallback to sol_value_usd
                'sol_balance_usd': summary.get('sol_balance_usd', summary.get('sol_value_usd', 0.0)),
                # Use normalized alias provided by tracker; fallback maintained
                'positions_value_usd': summary.get('positions_value_usd', summary.get('positions_value', 0.0)),
                'positions': positions,  # Add positions list
                # ADD THESE MISSING FIELDS:
                'position_count': len(positions),
                'individual_positions': {pos['mint']: {'value_usd': pos['value_usd']} for pos in positions}
            }
        except Exception as e:
            error(f"Error getting portfolio data: {str(e)}")
            return None

    def _calculate_simple_position_size(self) -> float:
        """Calculate simple position size - NO RISK AGENT CHECKS"""
        try:
            account_balance = self.get_account_balance()
            if account_balance <= 0:
                return config.BASE_POSITION_SIZE_USD
            
            # Use simple percentage-based sizing
            position_size = account_balance * config.POSITION_SIZE_PERCENTAGE
            
            # Apply basic limits only
            position_size = max(position_size, config.MIN_POSITION_SIZE_USD)
            position_size = min(position_size, config.MAX_POSITION_SIZE_USD)
            
            debug(f"Position size calculation: USDC ${account_balance:.2f} * {config.POSITION_SIZE_PERCENTAGE:.1%} = ${position_size:.2f}")
            
            return position_size
            
        except Exception as e:
            error(f"Error calculating simple position size: {str(e)}")
            return config.BASE_POSITION_SIZE_USD
    
    def _check_allocation_sell_triggers(self):
        """Check if we need to sell positions due to allocation limits"""
        try:
            portfolio_data = self.get_portfolio_data()
            if not portfolio_data:
                return
            
            total_value = portfolio_data.get('total_value_usd', 0)
            if total_value <= 0:
                return
            
            # Check total allocation limit
            positions_value = portfolio_data.get('positions_value_usd', 0)
            total_allocation_percent = positions_value / total_value if total_value > 0 else 0
            
            # Use paper trading allocation limit if in paper mode
            # NOTE: Use the correct config flag PAPER_TRADING_ENABLED (PAPER_TRADING does not exist)
            max_allocation = (
                config.PAPER_MAX_TOTAL_ALLOCATION
                if getattr(config, "PAPER_TRADING_ENABLED", True)
                else config.MAX_TOTAL_ALLOCATION_PERCENT
            )
            
            if total_allocation_percent > max_allocation:
                warning(f"🚨 Total allocation exceeded: {total_allocation_percent:.1%} > {max_allocation:.1%}")
                warning(f"🚨 Triggering allocation-based sell to reduce positions")
                self._execute_allocation_sell()
                return
            
            # Check individual position limits
            self._check_individual_position_limits()
            
        except Exception as e:
            error(f"Error checking allocation sell triggers: {str(e)}")
    
    def _check_individual_position_limits(self):
        """Check if any individual position exceeds MAX_SINGLE_POSITION_PERCENT"""
        try:
            portfolio_data = self.get_portfolio_data()
            if not portfolio_data:
                return
            
            total_value = portfolio_data.get('total_value_usd', 0)
            if total_value <= 0:
                return
            
            # Get current positions from portfolio tracker
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            summary = tracker.get_portfolio_summary()
            
            if not summary or 'positions' not in summary:
                return
            
            positions = summary.get('positions', {})
            
            for token_mint, position_data in positions.items():
                if token_mint in config.EXCLUDED_TOKENS:
                    continue
                
                position_value = position_data.get('usd_value', 0)
                position_percent = position_value / total_value if total_value > 0 else 0
                
                if position_percent > config.MAX_SINGLE_POSITION_PERCENT:
                    warning(f"🚨 Individual position exceeded: {token_mint[:8]}... {position_percent:.1%} > {config.MAX_SINGLE_POSITION_PERCENT:.1%}")
                    warning(f"🚨 Triggering sell for oversized position")
                    
                    # Calculate exact amount to sell to get back to target
                    target_value = total_value * config.MAX_SINGLE_POSITION_PERCENT
                    amount_to_sell_usd = position_value - target_value
                    
                    self._execute_position_sell(token_mint, position_data, amount_to_sell_usd, "individual_position_limit")
                    
        except Exception as e:
            error(f"Error checking individual position limits: {str(e)}")
    
    def _execute_allocation_sell(self):
        """Execute sell to reduce total allocation"""
        try:
            info("🔄 Executing allocation-based sell to reduce total allocation")
            
            # Get current positions
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            summary = tracker.get_portfolio_summary()
            
            if not summary or 'positions' not in summary:
                warning("No positions found for allocation sell")
                return
            
            positions = summary.get('positions', {})
            total_value = summary.get('total_value_usd', 0)
            
            if total_value <= 0:
                warning("No total value found for allocation sell")
                return
            
            # Calculate how much we need to sell to get back to target
            current_positions_value = summary.get('positions_value_usd', 0)
            max_total_allocation_percent = config.PAPER_MAX_TOTAL_ALLOCATION if config.PAPER_TRADING_ENABLED else config.MAX_TOTAL_ALLOCATION_PERCENT
            target_positions_value = total_value * max_total_allocation_percent
            
            if current_positions_value <= target_positions_value:
                info("Total allocation is within limits")
                return
            
            amount_to_sell_usd = current_positions_value - target_positions_value
            info(f"🔄 Need to sell ${amount_to_sell_usd:.2f} to get back to {max_total_allocation_percent:.1%} allocation")
            
            # Sort positions by value (largest first) and sell from largest
            sorted_positions = sorted(positions.items(), key=lambda x: x[1].get('usd_value', 0), reverse=True)
            
            remaining_to_sell = amount_to_sell_usd
            
            for token_mint, position_data in sorted_positions:
                if token_mint in config.EXCLUDED_TOKENS:
                    continue
                
                if remaining_to_sell <= 0:
                    break
                
                position_value = position_data.get('usd_value', 0)
                sell_amount = min(remaining_to_sell, position_value)
                
                if sell_amount > 0:
                    self._execute_position_sell(token_mint, position_data, sell_amount, "total_allocation_limit")
                    remaining_to_sell -= sell_amount
                
        except Exception as e:
            error(f"Error executing allocation sell: {str(e)}")
    
    def _execute_position_sell(self, token_mint: str, position_data: dict, amount_to_sell_usd: float, reason: str = "position_limit"):
        """Execute sell for a specific position - sells only the amount needed"""
        try:
            token_name = position_data.get('name', 'Unknown')
            token_symbol = position_data.get('symbol', 'UNK')
            total_position_value = position_data.get('usd_value', 0)
            
            # Calculate percentage to sell
            sell_percentage = amount_to_sell_usd / total_position_value if total_position_value > 0 else 0
            sell_percentage = min(sell_percentage, 1.0)  # Cap at 100%
            
            info(f"🔄 Executing {reason} sell: {token_symbol} ({token_name})")
            info(f"🔄 Selling ${amount_to_sell_usd:.2f} of ${total_position_value:.2f} ({sell_percentage:.1%})")
            
            # Get nice_funcs for partial sell
            nf = self._get_nice_funcs()
            if not nf:
                warning("nice_funcs not available - skipping sell")
                return
            
            # Check SOL balance for transaction fees
            sol_balance = nf.get_token_balance(config.SOL_ADDRESS)
            min_sol_required = 0.01
            
            if sol_balance < min_sol_required:
                warning(f"❌ Insufficient SOL for transaction fees: {sol_balance:.6f} SOL < {min_sol_required} SOL")
                return
            
            # Execute sell using chunk_kill
            # Note: chunk_kill sells the entire position, so for partial sells we may need custom logic
            # For now, we'll use chunk_kill which sells the full position
            success = nf.chunk_kill(token_mint)
            
            if success:
                info(f"✅ Successfully executed {reason} sell: {token_symbol}")
                # Emit order executed signal
                self.order_executed.emit(
                    "CopyBot", "SELL", token_symbol, 
                    0, 0, 0, 0, "", token_mint, 
                    f"{reason}: Sold ${amount_to_sell_usd:.2f}"
                )
            else:
                warning(f"❌ Failed to execute {reason} sell: {token_symbol}")
                
        except Exception as e:
            error(f"Error executing position sell: {str(e)}")

    def _aggregate_changes_by_mint(self, changes: dict) -> dict:
        """
        Aggregate account-level changes by mint address to handle multiple accounts per token
        """
        try:
            aggregated_changes = {}
            
            for wallet, wallet_changes in changes.items():
                aggregated_wallet_changes = {
                    "new": {},
                    "removed": {},
                    "modified": {}
                }
                
                # Aggregate new tokens by mint
                mint_new_totals = {}
                for account_key, token_data in wallet_changes.get('new', {}).items():
                    mint = token_data.get('mint', 'unknown')
                    if mint not in mint_new_totals:
                        mint_new_totals[mint] = {
                            'amount': 0,
                            'symbol': token_data.get('symbol', 'UNK'),
                            'name': token_data.get('name', 'Unknown Token'),
                            'price': token_data.get('price'),
                            'usd_value': 0,
                            'mint': mint,
                            'accounts': []
                        }
                    mint_new_totals[mint]['amount'] += token_data.get('amount', 0)
                    mint_new_totals[mint]['accounts'].append(account_key)
                    if token_data.get('usd_value'):
                        mint_new_totals[mint]['usd_value'] += token_data.get('usd_value', 0)
                
                aggregated_wallet_changes['new'] = mint_new_totals
                
                # Aggregate removed tokens by mint
                mint_removed_totals = {}
                for account_key, token_data in wallet_changes.get('removed', {}).items():
                    mint = token_data.get('mint', 'unknown')
                    if mint not in mint_removed_totals:
                        mint_removed_totals[mint] = {
                            'amount': 0,
                            'symbol': token_data.get('symbol', 'UNK'),
                            'name': token_data.get('name', 'Unknown Token'),
                            'price': token_data.get('price'),
                            'usd_value': 0,
                            'mint': mint,
                            'accounts': []
                        }
                    mint_removed_totals[mint]['amount'] += token_data.get('amount', 0)
                    mint_removed_totals[mint]['accounts'].append(account_key)
                    if token_data.get('usd_value'):
                        mint_removed_totals[mint]['usd_value'] += token_data.get('usd_value', 0)
                
                aggregated_wallet_changes['removed'] = mint_removed_totals
                
                # Aggregate modified tokens by mint
                mint_modified_totals = {}
                for account_key, token_data in wallet_changes.get('modified', {}).items():
                    mint = token_data.get('mint', 'unknown')
                    if mint not in mint_modified_totals:
                        mint_modified_totals[mint] = {
                            'previous_amount': 0,
                            'current_amount': 0,
                            'change': 0,
                            'symbol': token_data.get('symbol', 'UNK'),
                            'name': token_data.get('name', 'Unknown Token'),
                            'current_price': token_data.get('current_price'),
                            'mint': mint,
                            'accounts': []
                        }
                    mint_modified_totals[mint]['previous_amount'] += token_data.get('previous_amount', 0)
                    mint_modified_totals[mint]['current_amount'] += token_data.get('current_amount', 0)
                    mint_modified_totals[mint]['change'] += token_data.get('change', 0)
                    mint_modified_totals[mint]['accounts'].append(account_key)
                
                # Calculate percentage change for aggregated modified tokens
                for mint, data in mint_modified_totals.items():
                    if data['previous_amount'] > 0:
                        data['pct_change'] = (data['change'] / data['previous_amount']) * 100
                    else:
                        data['pct_change'] = 0
                
                aggregated_wallet_changes['modified'] = mint_modified_totals
                
                if any(aggregated_wallet_changes.values()):
                    aggregated_changes[wallet] = aggregated_wallet_changes
            
            return aggregated_changes
            
        except Exception as e:
            error(f"Error aggregating changes by mint: {e}")
            return changes  # Return original changes if aggregation fails

    def execute_mirror_trades(self, wallet_results=None, changes=None):
        """
        SURGICAL: Execute trades by mirroring tracked wallets with minimal validation
        """
        try:
            # Basic input validation
            if wallet_results is None or changes is None:
                info("No wallet results or changes provided, fetching fresh data...")
                tracker = WalletTracker()
                cached_results, _ = tracker.load_cache()
                wallet_results, changes = tracker.track_wallets()
                
            # Basic format validation
            if not isinstance(wallet_results, dict) or not isinstance(changes, dict):
                error("Invalid wallet results or changes format")
                return False
                
            # Use shared price service
            price_service = self.price_service
            if not price_service:
                error("Price service not available")
                return False
                
            # Check if there are any changes to mirror
            if not changes:
                info("No changes detected in tracked wallets.")
                return True
                
            # SURGICAL: Use minimal validation - only filter out obviously invalid data
            validated_changes = self._basic_mirror_validation(changes)
            if not validated_changes:
                warning("No valid changes to execute after basic validation")
                return True
            
            # CRITICAL FIX: Aggregate account-level changes by mint for proper execution
            aggregated_changes = self._aggregate_changes_by_mint(validated_changes)
                
            # Count changes for monitoring
            total_new = 0
            total_removed = 0
            total_modified = 0
            total_webhook_tokens = 0
            
            for wallet, wallet_changes in aggregated_changes.items():
                if 'tokens' in wallet_changes:
                    # New webhook structure
                    total_webhook_tokens += len(wallet_changes['tokens'])
                else:
                    # Legacy structure
                    total_new += len(wallet_changes.get('new', {}))
                    total_removed += len(wallet_changes.get('removed', {}))
                    total_modified += len(wallet_changes.get('modified', {}))
            
            if total_webhook_tokens > 0:
                info(f"Executing {total_webhook_tokens} webhook tokens across {len(aggregated_changes)} wallets")
            else:
                info(f"Executing {total_new} new, {total_removed} removed, and {total_modified} modified tokens across {len(aggregated_changes)} wallets")
            
            # Track execution results
            execution_results = {
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'errors': []
            }
            
            # Process each wallet with aggregated changes
            for wallet, wallet_changes in aggregated_changes.items():
                try:
                    # Handle new webhook structure: {'tokens': {'mint': {'action': 'BUY/SELL/MONITOR', ...}}}
                    if 'tokens' in wallet_changes:
                        info(f"🔔 Processing webhook tokens for wallet {wallet[:8]}...")
                        for mint, token_data in wallet_changes['tokens'].items():
                            action = token_data.get('action', 'MONITOR')
                            
                            if action == 'BUY' and config.COPYBOT_AUTO_BUY_NEW_TOKENS:
                                result = self._execute_mirror_buy(wallet, mint, token_data, price_service)
                                if result == 'success':
                                    execution_results['successful'] += 1
                                elif result == 'failed':
                                    execution_results['failed'] += 1
                                else:
                                    execution_results['skipped'] += 1
                                    
                            elif action == 'SELL':  # ← Mirror ALL sell transactions from tracked wallets
                                # Get sell type information from token data
                                sell_type = token_data.get('sell_type', 'full')
                                sell_percentage = token_data.get('sell_percentage', 100)
                                
                                # Route to appropriate sell method based on type
                                if sell_type == 'half':
                                    result = self._execute_half_sell(wallet, mint, token_data, price_service)
                                elif sell_type == 'partial' and sell_percentage != 100:
                                    result = self._execute_partial_sell(wallet, mint, token_data, price_service, sell_percentage)
                                else:  # full sell or default
                                    result = self._execute_mirror_sell(wallet, mint, token_data, price_service)
                                
                                if result == 'success':
                                    execution_results['successful'] += 1
                                elif result == 'failed':
                                    execution_results['failed'] += 1
                                else:
                                    execution_results['skipped'] += 1
                                    
                            elif action == 'MONITOR':
                                info(f"👁️ Monitoring token {mint[:8]}... (no action taken)")
                                execution_results['skipped'] += 1
                                
                            else:
                                info(f"⚠️ Unknown action '{action}' for token {mint[:8]}... - skipping")
                                execution_results['skipped'] += 1
                    
                    # Handle legacy structure: {'new': {...}, 'removed': {...}, 'modified': {...}}
                    else:
                        # Process new tokens (potential buys)
                        if config.COPYBOT_AUTO_BUY_NEW_TOKENS:
                            for mint, token_data in wallet_changes.get('new', {}).items():
                                result = self._execute_mirror_buy(wallet, mint, token_data, price_service)
                                if result == 'success':
                                    execution_results['successful'] += 1
                                elif result == 'failed':
                                    execution_results['failed'] += 1
                                else:
                                    execution_results['skipped'] += 1
                        
                        # Process removed tokens (potential sells)
                        # CRITICAL SAFETY: Validate holdings before processing removed tokens
                        info("⚠️ Processing removed tokens - checking if we actually hold them")
                        
                        if config.COPYBOT_AUTO_SELL_REMOVED_TOKENS:
                            for mint, token_data in wallet_changes.get('removed', {}).items():
                                result = self._execute_mirror_sell(wallet, mint, token_data, price_service)
                                if result == 'success':
                                    execution_results['successful'] += 1
                                elif result == 'failed':
                                    execution_results['failed'] += 1
                                else:
                                    execution_results['skipped'] += 1
                        
                        # Process modified tokens (partial sells or buys)
                        for mint, token_data in wallet_changes.get('modified', {}).items():
                            result = self._execute_mirror_modify(wallet, mint, token_data, price_service)
                            if result == 'success':
                                execution_results['successful'] += 1
                            elif result == 'failed':
                                execution_results['failed'] += 1
                            else:
                                execution_results['skipped'] += 1
                            
                except Exception as e:
                    error(f"Error processing wallet {wallet}: {str(e)}")
                    execution_results['errors'].append(f"Wallet {wallet}: {str(e)}")
                    execution_results['failed'] += 1
            
            # Report execution results
            info(f"Mirror trading completed: {execution_results['successful']} successful, "
                f"{execution_results['failed']} failed, {execution_results['skipped']} skipped")
            
            if execution_results['errors']:
                warning(f"Errors encountered: {len(execution_results['errors'])}")
                for error_msg in execution_results['errors'][:3]:  # Show first 3 errors
                    warning(f"  - {error_msg}")
            
            return execution_results['successful'] > 0 or execution_results['failed'] == 0
            
        except Exception as e:
            error(f"Critical error executing mirror trades: {str(e)}")
            debug(traceback.format_exc(), file_only=True)
            return False
    
    def _basic_mirror_validation(self, changes: dict) -> dict:
        """
        SURGICAL: Basic validation that only filters out obviously invalid data
        """
        validated_changes = {}
        
        try:
            for wallet, wallet_changes in changes.items():
                if not isinstance(wallet_changes, dict):
                    continue
                    
                validated_wallet_changes = {'new': {}, 'removed': {}, 'modified': {}}
                
                # Basic validation for new tokens
                for token_mint, token_data in wallet_changes.get('new', {}).items():
                    if self._basic_token_validation(token_mint, token_data):
                        validated_wallet_changes['new'][token_mint] = token_data
                
                # Basic validation for removed tokens
                for token_mint, token_data in wallet_changes.get('removed', {}).items():
                    if self._basic_token_validation(token_mint, token_data):
                        validated_wallet_changes['removed'][token_mint] = token_data
                
                # Basic validation for modified tokens
                for token_mint, token_data in wallet_changes.get('modified', {}).items():
                    if self._basic_token_validation(token_mint, token_data):
                        validated_wallet_changes['modified'][token_mint] = token_data
                
                # Include wallet if it has any changes
                if any(validated_wallet_changes.values()):
                    validated_changes[wallet] = validated_wallet_changes
                    
        except Exception as e:
            error(f"Error in basic mirror validation: {str(e)}")
            return {}
            
        return validated_changes
    
    def _basic_token_validation(self, token_mint: str, token_data: dict) -> bool:
        """
        SURGICAL: Minimal token validation - only filter out obviously broken data
        """
        try:
            # Only check absolutely essential things
            if not token_mint or len(token_mint) < 32:
                return False
                
            # Check if token is explicitly excluded
            if hasattr(config, 'EXCLUDED_TOKENS') and token_mint in config.EXCLUDED_TOKENS:
                return False
                
            # Ensure data structure is valid
            if not isinstance(token_data, dict):
                return False
                
            # Only require amount field exists (don't check value)
            if 'amount' not in token_data:
                return False
                
            return True
            
        except Exception as e:
            debug(f"Error in basic token validation for {token_mint[:8]}...: {str(e)}")
            return False

    def _blocked_token(self, mint: str, symbol: str, action: str = 'buy') -> bool:
        """Check if token is blocked for CopyBot trading"""
        from src.config import EXCLUDED_TOKENS, REBALANCING_ALLOWED_TOKENS
        
        # Allow selling of rebalancing-allowed tokens (SOL/USDC)
        if action == 'sell' and mint in REBALANCING_ALLOWED_TOKENS:
            return False
        
        # Check by mint address
        if mint in EXCLUDED_TOKENS:
            return True
        
        # Check by symbol (case-insensitive) - only block buying
        if action == 'buy':
            symbol_upper = symbol.upper()
            if symbol_upper in {'SOL', 'USDC'}:
                return True
        
        return False
    
    def _should_stop_all_trading(self) -> bool:
        """Check if CopyBot should stop all trading (including sells)"""
        try:
            # Check if risk agent has stopped all trading
            if hasattr(config, 'COPYBOT_STOP_ALL') and config.COPYBOT_STOP_ALL:
                from src.scripts.shared_services.logger import info
                info("🚫 CopyBot: Risk agent has stopped all trading")
                return True
            
            # Check if CopyBot is disabled
            if hasattr(config, 'COPYBOT_ENABLED') and not config.COPYBOT_ENABLED:
                from src.scripts.shared_services.logger import info
                info("🚫 CopyBot: Agent is disabled")
                return True
            
            return False
            
        except Exception as e:
            from src.scripts.shared_services.logger import warning
            warning(f"Error in _should_stop_all_trading: {e}")
            return True  # Fail safe

    def _should_stop_buying(self) -> bool:
        """Check if CopyBot should stop buying - RISK AGENT HALTS + ALLOCATION LIMITS"""
        try:
            # CRITICAL: Check risk agent halt flags FIRST
            if hasattr(config, 'COPYBOT_HALT_BUYS') and config.COPYBOT_HALT_BUYS:
                from src.scripts.shared_services.logger import info
                info("🚫 CopyBot: Risk agent has halted new buys")
                return True
            
            if hasattr(config, 'COPYBOT_STOP_ALL') and config.COPYBOT_STOP_ALL:
                from src.scripts.shared_services.logger import info
                info("🚫 CopyBot: Risk agent has stopped all trading")
                return True
            
            # Get portfolio data
            portfolio_data = self.get_portfolio_data()
            if not portfolio_data:
                return True
            
            total_value = portfolio_data.get('total_value_usd', 0)
            if total_value <= 0:
                return True
                
            # USDC availability check (or sufficient SOL for conversion)
            usdc_balance_usd = portfolio_data.get('usdc_balance_usd', 0)
            sol_balance_usd = portfolio_data.get('sol_balance_usd', 0)
            total_liquid_assets = usdc_balance_usd + sol_balance_usd
            
            if total_liquid_assets < 10:
                from src.scripts.shared_services.logger import warning
                warning(f"CopyBot: Insufficient liquid assets - USDC ${usdc_balance_usd:.2f} + SOL ${sol_balance_usd:.2f} = ${total_liquid_assets:.2f}")
                return True
            
            # Get reserved balances for DeFi collateral/reserved tokens (e.g., stSOL)
            try:
                from src.scripts.defi.defi_position_manager import DeFiPositionManager
                reserved_map = DeFiPositionManager().get_all_reserved_balances() or {}
            except Exception:
                reserved_map = {}

            # For detailed position analysis, use individual_positions if available
            individual_positions = portfolio_data.get('individual_positions', {})
            if individual_positions:
                # Filter out SOL and USDC addresses
                token_positions = {addr: value for addr, value in individual_positions.items()
                                 if addr not in [config.SOL_ADDRESS, config.USDC_ADDRESS]}
            else:
                # Fallback: use position_count directly (already excludes SOL/USDC)
                token_positions = {}

            # Check concurrent positions limit - count only active trading positions (exclude reserved/collateral)
            active_position_count = 0
            if token_positions:
                for addr, pos_data in token_positions.items():
                    val = float(pos_data.get('value_usd', 0) or 0)
                    rb = reserved_map.get(addr)
                    reserved_usd = float(getattr(rb, 'reserved_amount_usd', 0) or 0)
                    if val > reserved_usd:  # Only count positions with active (non-reserved) value
                        active_position_count += 1
            else:
                # Fallback: use position_count minus reserved tokens
                total_position_count = portfolio_data.get('position_count', 0)
                reserved_positions_count = sum(1 for addr, rb in reserved_map.items()
                                             if addr not in [config.SOL_ADDRESS, config.USDC_ADDRESS])
                active_position_count = max(0, total_position_count - reserved_positions_count)

            if active_position_count >= config.MAX_CONCURRENT_POSITIONS:
                from src.scripts.shared_services.logger import info
                info(f"CopyBot: Max concurrent positions reached ({active_position_count}/{config.MAX_CONCURRENT_POSITIONS})")
                return True

            # Check total allocation limit - EXCLUDE reserved/collateral (e.g., stSOL)
            if token_positions:
                # Sum total positions and active positions (minus reserved portion per token)
                total_position_value = sum(float(pos_data.get('value_usd', 0) or 0)
                                           for pos_data in token_positions.values())
                active_positions_value = 0.0
                for addr, pos_data in token_positions.items():
                    val = float(pos_data.get('value_usd', 0) or 0)
                    rb = reserved_map.get(addr)
                    reserved_usd = float(getattr(rb, 'reserved_amount_usd', 0) or 0)
                    active_positions_value += max(0.0, val - reserved_usd)
            else:
                # Fallback: use positions_value_usd minus reserved tokens that live in positions (exclude SOL/USDC)
                total_position_value = float(portfolio_data.get('positions_value_usd', 0) or 0)
                reserved_positions_usd = 0.0
                for addr, rb in reserved_map.items():
                    if addr not in [config.SOL_ADDRESS, config.USDC_ADDRESS]:
                        try:
                            reserved_positions_usd += float(getattr(rb, 'reserved_amount_usd', 0) or 0)
                        except Exception:
                            pass
                active_positions_value = max(0.0, total_position_value - reserved_positions_usd)

            total_allocation_pct = active_positions_value / total_value
            try:
                from src.scripts.shared_services.logger import debug
                total_positions_pct = (total_position_value / total_value) if total_value > 0 else 0.0
                debug(f"CopyBot: Allocation check - TotalPositions={total_positions_pct*100:.1f}% ActiveTrading={total_allocation_pct*100:.1f}% Limit={config.MAX_TOTAL_ALLOCATION_PERCENT*100:.1f}% (excludes reserved/collateral)")
            except Exception:
                pass

            if total_allocation_pct >= config.MAX_TOTAL_ALLOCATION_PERCENT:
                from src.scripts.shared_services.logger import info
                info(f"CopyBot: Max total allocation reached (active {total_allocation_pct*100:.1f}%/{config.MAX_TOTAL_ALLOCATION_PERCENT*100}%)")
                return True
            
            # Check single position limit - if any existing position exceeds the limit
            if token_positions:
                for pos_data in token_positions.values():
                    position_value = pos_data.get('value_usd', 0)
                    position_percent = position_value / total_value
                    if position_percent > config.MAX_SINGLE_POSITION_PERCENT:
                        from src.scripts.shared_services.logger import info
                        info(f"CopyBot: Single position limit exceeded ({position_percent*100:.1f}%/{config.MAX_SINGLE_POSITION_PERCENT*100}%)")
                        return True
            
            return False
            
        except Exception as e:
            from src.scripts.shared_services.logger import warning
            warning(f"Error in _should_stop_buying: {e}")
            return True  # Fail safe
    
    def _has_excessive_single_position(self, mint: str, amount_usd: float) -> bool:
        """Check if a single position would exceed MAX_SINGLE_POSITION_PERCENT"""
        try:
            from src.config import MAX_SINGLE_POSITION_PERCENT
            
            portfolio_data = self.get_portfolio_data()
            if not portfolio_data:
                return True
            
            total_value = portfolio_data.get('total_value_usd', 0)
            if total_value <= 0:
                return True
            
            # Get current position value
            current_position_value = self._get_current_position_value(mint)
            new_total_position_value = current_position_value + amount_usd
            position_percent = new_total_position_value / total_value
            
            return position_percent > MAX_SINGLE_POSITION_PERCENT
            
        except Exception as e:
            from src.nice_funcs import error
            error(f"Error checking single position limit: {str(e)}")
            return True
    
    def _get_current_position_value(self, mint: str) -> float:
        """Get current USD value of a position"""
        try:
            portfolio_data = self.get_portfolio_data()
            if not portfolio_data:
                return 0.0
            
            positions = portfolio_data.get('positions', [])
            for position in positions:
                if position.get('mint') == mint:
                    return position.get('value_usd', 0.0)
            
            return 0.0
            
        except Exception as e:
            from src.nice_funcs import error
            error(f"Error getting current position value: {str(e)}")
            return 0.0
    
    def _should_restart_buying(self) -> bool:
        """Check if CopyBot should restart buying based on improved conditions"""
        try:
            from src.scripts.webhooks.webhook_handler import risk_agent
            from src.config import (
                MAX_TOTAL_ALLOCATION_PERCENT, MAX_SINGLE_POSITION_PERCENT,
                SOL_TARGET_PERCENT, SOL_MINIMUM_PERCENT, SOL_MINIMUM_BALANCE_USD,
                USDC_TARGET_PERCENT, USDC_MINIMUM_PERCENT, USDC_EMERGENCY_PERCENT
            )
            
            # Check if risk agent has cleared the stop flags
            if risk_agent:
                if hasattr(risk_agent, 'copybot_stop_reason') and risk_agent.copybot_stop_reason:
                    return False  # Still stopped by risk agent
                if hasattr(risk_agent, 'copybot_halt_reason') and risk_agent.copybot_halt_reason:
                    return False  # Still halted by risk agent
            
            # Get current portfolio data
            portfolio_data = self.get_portfolio_data()
            if not portfolio_data:
                return False
            
            total_value = portfolio_data.get('total_value_usd', 0)
            if total_value <= 0:
                return False
            
            # Check if total allocation is now within limits
            positions_value = portfolio_data.get('positions_value_usd', 0)
            total_allocation_percent = positions_value / total_value if total_value > 0 else 0
            
            if total_allocation_percent > MAX_TOTAL_ALLOCATION_PERCENT:
                return False  # Still over allocation limit
            
            # Check if USDC balance has recovered
            usdc_balance_usd = portfolio_data.get('usdc_balance_usd', 0)
            usdc_percent = usdc_balance_usd / total_value if total_value > 0 else 0
            
            if usdc_percent < USDC_MINIMUM_PERCENT:
                return False  # USDC still too low
            
            # Check if SOL balance has recovered
            sol_balance_usd = portfolio_data.get('sol_balance_usd', 0)
            sol_percent = sol_balance_usd / total_value if total_value > 0 else 0
            
            if sol_balance_usd < SOL_MINIMUM_BALANCE_USD:
                return False  # SOL still too low
            
            if sol_percent < SOL_MINIMUM_PERCENT:
                return False  # SOL percentage still too low
            
            # All conditions met - can restart
            from src.nice_funcs import info
            info(f"🔄 CopyBot: Conditions improved - restarting buying operations")
            return True
            
        except Exception as e:
            from src.nice_funcs import error
            error(f"Error checking copybot restart conditions: {str(e)}")
            return False
    
    def _execute_mirror_buy(self, wallet: str, mint: str, token_data: dict, price_service) -> str:
        """Execute a mirror buy with minimal validation"""
        try:
            symbol = token_data.get('symbol', 'UNK')
            name = token_data.get('name', 'Unknown Token')
            
            # Check if copybot should stop buying
            if self._should_stop_buying():
                from src.nice_funcs import info
                info(f"🚫 CopyBot: Stopped buying due to risk/allocation limits")
                return 'stopped'
            
            # Hard-stop guard for excluded tokens
            if self._blocked_token(mint, symbol, 'buy'):
                from src.nice_funcs import info
                info(f"🚫 Skipping excluded token {symbol} ({mint[:8]}...) for CopyBot")
                return 'skipped'
            
            from src.nice_funcs import info
            info(f"NEW token: {symbol} ({name}) in {wallet[:4]}... - Mirroring with BUY")
            
            # Calculate position size
            position_size = self.calculate_dynamic_position_size(mint, position_type="new")
            
            # Check single position limit
            if self._has_excessive_single_position(mint, position_size):
                from src.nice_funcs import warning
                warning(f"🚫 CopyBot: Position size ${position_size:.2f} would exceed single position limit")
                return 'skipped'
            
            # Minimal position size check
            if position_size < 0.25:
                position_size = 0.25
            
            # Hard enforcement of position size limits
            from src.config import PAPER_MAX_POSITION_SIZE
            if position_size > PAPER_MAX_POSITION_SIZE:
                from src.scripts.shared_services.logger import warning
                warning(f"🚫 Position size ${position_size:.2f} exceeds max ${PAPER_MAX_POSITION_SIZE:.2f} - blocking trade")
                return 'failed'
                
            info(f"Buying {symbol} ({name}) for ${position_size:.2f}")
            
            # Execute trade
            try:
                if config.PAPER_TRADING_ENABLED:
                    from src.paper_trading import execute_paper_trade
                    # Get current price
                    price = price_service.get_price(mint, agent_type='copybot')
                    if not price or price <= 0:
                        warning(f"No valid price available for {mint[:8]}... - skipping trade")
                        return 'failed'
                    
                    # Add price validation to prevent unrealistic prices
                    if isinstance(price, (int, float)) and (price <= 0 or price > 1000):  # Reject unrealistic prices
                        from src.scripts.shared_services.logger import warning
                        warning(f"⚠️ Rejecting unrealistic price for {mint[:8]}...: ${price:.6f}")
                        return 'failed'
                    
                    # Calculate token amount based on USD size
                    token_amount = position_size / price
                    success = execute_paper_trade(
                        mint, "BUY", token_amount, price, "copybot",
                        token_symbol=symbol,
                        token_name=name
                    )
                else:
                    nf = self._get_nice_funcs()
                    if not nf:
                        error("Trading functions not available")
                        return 'failed'
                    success = nf.market_entry(symbol, position_size, agent="copybot")
                
                if success:
                    info(f"Successfully mirrored BUY for {symbol}")
                    
                    # Emit signal
                    self.order_executed.emit(
                        "CopyBot", "BUY", symbol, 
                        position_size, price, 0, 
                        0, wallet, mint, f"Mirror trading: New token in wallet {wallet[:4]}..."
                    )
                    return 'success'
                else:
                    from src.scripts.shared_services.logger import warning
                    warning(f"Failed to mirror BUY for {symbol}")
                    return 'failed'
                
            except Exception as e:
                error(f"Error executing BUY for {symbol}: {str(e)}")
                return 'failed'
                
        except Exception as e:
            error(f"Critical error in mirror buy for {mint[:8]}...: {str(e)}")
            return 'failed'
    
    def _execute_mirror_sell(self, wallet: str, mint: str, token_data: dict, price_service) -> str:
        """Execute a mirror sell with minimal validation"""
        try:
            symbol = token_data.get('symbol', 'UNK')
            name = token_data.get('name', 'Unknown Token')
            
            # Hard-stop guard for excluded tokens
            if self._blocked_token(mint, symbol):
                info(f"🚫 Skipping excluded token {symbol} ({mint[:8]}...) for CopyBot")
                return 'skipped'
            
            # Execute trade
            try:
                if config.PAPER_TRADING_ENABLED:
                    from src.paper_trading import execute_paper_trade
                    # Get current price
                    price = price_service.get_price(mint, agent_type='copybot')
                    if not price or price <= 0:
                        warning(f"No valid price available for {mint[:8]}... - skipping trade")
                        return 'failed'
                    
                    # CRITICAL: Validate price before using
                    if isinstance(price, (int, float)) and price > 100 and mint not in [config.SOL_ADDRESS, config.USDC_ADDRESS]:
                        warning(f"🚫 Rejecting unrealistic price ${price:.6f} for {mint[:8]}...")
                        return 'failed'
                    
                    # Get current balance
                    balance = self.get_token_balance(mint)
                    if balance <= 0:
                        # Try to find balance using normalized symbol (handles token name variations)
                        normalized_symbol = self._normalize_token_symbol_for_lookup(symbol)
                        if normalized_symbol != symbol:
                            balance = self._find_balance_by_normalized_symbol(normalized_symbol, mint)

                    if balance > 0:
                        # Check position size before selling
                        position_value = balance * price
                        from src.config import PAPER_MAX_POSITION_SIZE
                        if position_value > PAPER_MAX_POSITION_SIZE:
                            warning(f"🚫 Position value ${position_value:.2f} exceeds max ${PAPER_MAX_POSITION_SIZE:.2f} - blocking sell")
                            return 'failed'
                        
                        # Additional safety check: ensure sell amount doesn't exceed portfolio value
                        try:
                            from src.paper_trading import get_portfolio_value
                            portfolio_value = get_portfolio_value()
                            if position_value > portfolio_value * 1.1:  # Allow 10% buffer for price fluctuations
                                warning(f"🚫 Sell amount ${position_value:.2f} exceeds portfolio value ${portfolio_value:.2f} - capping sell")
                                # Cap at 90% of portfolio value
                                balance = (portfolio_value * 0.9) / price
                                position_value = balance * price
                                info(f"📊 Capped sell amount to {balance:.6f} tokens (${position_value:.2f})")
                        except Exception as e:
                            warning(f"⚠️ Could not validate portfolio value: {e}")
                        
                        success = execute_paper_trade(mint, "SELL", balance, price, "copybot", symbol, name)
                    else:
                        warning(f"No balance to sell for {symbol}")
                        return 'skipped'
                else:
                    nf = self._get_nice_funcs()
                    if not nf:
                        error("Trading functions not available")
                        return 'failed'
                    success = nf.market_exit(symbol, percentage=100, agent="copybot")
                
                if success:
                    info(f"Successfully mirrored SELL for {symbol}")
                    
                    # Emit signal
                    self.order_executed.emit(
                        "CopyBot", "SELL", symbol, 
                        balance, 0, price, 
                        0, wallet, mint, f"Mirror trading: Token removed from wallet {wallet[:4]}..."
                    )
                    return 'success'
                else:
                    warning(f"Failed to mirror SELL for {symbol}")
                    return 'failed'
                
            except Exception as e:
                error(f"Error executing SELL for {symbol}: {str(e)}")
                return 'failed'
                
        except Exception as e:
            error(f"Critical error in mirror sell for {mint[:8]}...: {str(e)}")
            return 'failed'
    
    def _execute_half_sell(self, wallet: str, mint: str, token_data: dict, price_service) -> str:
        """Execute a half sell (50% of position)"""
        try:
            symbol = token_data.get('symbol', 'UNK')
            name = token_data.get('name', 'Unknown Token')
            
            # Hard-stop guard for excluded tokens
            if self._blocked_token(mint, symbol):
                info(f"🚫 Skipping excluded token {symbol} ({mint[:8]}...) for CopyBot")
                return 'skipped'
            
            info(f"HALF SELL: {symbol} ({name}) from {wallet[:4]}... - Selling 50% of position")
            
            # Get current balance
            balance = self.get_token_balance(mint)
            if balance <= 0:
                # Try to find balance using normalized symbol (handles token name variations)
                normalized_symbol = self._normalize_token_symbol_for_lookup(symbol)
                if normalized_symbol != symbol:
                    balance = self._find_balance_by_normalized_symbol(normalized_symbol, mint)

            if balance <= 0:
                warning(f"No balance to sell for {symbol}")
                return 'no_balance'
            
            # Calculate half amount
            half_amount = balance / 2
            
            # Execute trade
            try:
                if config.PAPER_TRADING_ENABLED:
                    from src.paper_trading import execute_paper_trade
                    price = price_service.get_price(mint, agent_type='copybot')
                    if not price or price <= 0:
                        warning(f"No valid price available for {mint[:8]}... - skipping trade")
                        return 'failed'
                    
                    # Validate price
                    if isinstance(price, (int, float)) and price > 100 and mint not in [config.SOL_ADDRESS, config.USDC_ADDRESS]:
                        warning(f"🚫 Rejecting unrealistic price ${price:.6f} for {mint[:8]}...")
                        return 'failed'
                    
                    success = execute_paper_trade(mint, "PARTIAL_CLOSE", half_amount, price, "copybot", symbol, name)
                else:
                    nf = self._get_nice_funcs()
                    if not nf:
                        error("Trading functions not available")
                        return 'failed'
                    success = nf.market_exit(symbol, percentage=50, agent="copybot")  # 50% sell
                
                if success:
                    info(f"Successfully executed HALF SELL for {symbol}")
                    
                    # Emit signal
                    self.order_executed.emit(
                        "CopyBot", "HALF_SELL", symbol, 
                        half_amount, 0, price, 
                        0, wallet, mint, f"Half sell: 50% of position from wallet {wallet[:4]}..."
                    )
                    return 'success'
                else:
                    warning(f"Failed to execute HALF SELL for {symbol}")
                    return 'failed'
                    
            except Exception as e:
                error(f"Error executing HALF SELL for {symbol}: {str(e)}")
                return 'failed'
                
        except Exception as e:
            error(f"Critical error in half sell for {mint[:8]}...: {str(e)}")
            return 'failed'
    
    def _execute_partial_sell(self, wallet: str, mint: str, token_data: dict, price_service, percentage: float) -> str:
        """Execute a partial sell (custom percentage of position)"""
        try:
            symbol = token_data.get('symbol', 'UNK')
            name = token_data.get('name', 'Unknown Token')
            
            # Validate percentage
            if percentage <= 0 or percentage > 100:
                error(f"Invalid sell percentage: {percentage}%")
                return 'failed'
            
            # Hard-stop guard for excluded tokens
            if self._blocked_token(mint, symbol):
                info(f"🚫 Skipping excluded token {symbol} ({mint[:8]}...) for CopyBot")
                return 'skipped'
            
            info(f"PARTIAL SELL: {symbol} ({name}) from {wallet[:4]}... - Selling {percentage}% of position")
            
            # Get current balance
            balance = self.get_token_balance(mint)
            if balance <= 0:
                # Try to find balance using normalized symbol (handles token name variations)
                normalized_symbol = self._normalize_token_symbol_for_lookup(symbol)
                if normalized_symbol != symbol:
                    balance = self._find_balance_by_normalized_symbol(normalized_symbol, mint)

            if balance <= 0:
                warning(f"No balance to sell for {symbol}")
                return 'no_balance'
            
            # Calculate partial amount
            partial_amount = balance * (percentage / 100)
            
            # Execute trade
            try:
                if config.PAPER_TRADING_ENABLED:
                    from src.paper_trading import execute_paper_trade
                    price = price_service.get_price(mint, agent_type='copybot')
                    if not price or price <= 0:
                        warning(f"No valid price available for {mint[:8]}... - skipping trade")
                        return 'failed'
                    
                    # Validate price
                    if isinstance(price, (int, float)) and price > 100 and mint not in [config.SOL_ADDRESS, config.USDC_ADDRESS]:
                        warning(f"🚫 Rejecting unrealistic price ${price:.6f} for {mint[:8]}...")
                        return 'failed'
                    
                    success = execute_paper_trade(mint, "PARTIAL_CLOSE", partial_amount, price, "copybot", symbol, name)
                else:
                    nf = self._get_nice_funcs()
                    if not nf:
                        error("Trading functions not available")
                        return 'failed'
                    success = nf.market_exit(symbol, percentage=percentage, agent="copybot")
                
                if success:
                    info(f"Successfully executed PARTIAL SELL ({percentage}%) for {symbol}")
                    
                    # Emit signal
                    self.order_executed.emit(
                        "CopyBot", "PARTIAL_SELL", symbol, 
                        partial_amount, 0, price, 
                        0, wallet, mint, f"Partial sell: {percentage}% of position from wallet {wallet[:4]}..."
                    )
                    return 'success'
                else:
                    warning(f"Failed to execute PARTIAL SELL for {symbol}")
                    return 'failed'
                    
            except Exception as e:
                error(f"Error executing PARTIAL SELL for {symbol}: {str(e)}")
                return 'failed'
                
        except Exception as e:
            error(f"Critical error in partial sell for {mint[:8]}...: {str(e)}")
            return 'failed'
            
    def _execute_mirror_modify(self, wallet: str, mint: str, token_data: dict, price_service) -> str:
        """
        SURGICAL: Execute a mirror modify with minimal validation
        """
        try:
            symbol = token_data.get('symbol', 'UNK')
            
            # Hard-stop guard for excluded tokens
            if self._blocked_token(mint, symbol):
                info(f"🚫 Skipping excluded token {symbol} ({mint[:8]}...) for CopyBot")
                return 'skipped'
            name = token_data.get('name', 'Unknown Token')
            pct_change = token_data.get('pct_change', 0)
            
            info(f"MODIFIED token: {symbol} ({name}) in {wallet[:4]}... - Change: {pct_change:.2f}%")
            
            # Determine action based on change
            if pct_change > 0:
                # Increase in position - potential buy
                action = "BUY"
                position_size = self.calculate_dynamic_position_size(mint, position_type="modify", pct_change=pct_change)
            else:
                # Decrease in position - potential sell
                action = "SELL"
                position_size = abs(pct_change) * 0.01  # Convert percentage to fraction
            
            # Hard enforcement of position size limits
            from src.config import PAPER_MAX_POSITION_SIZE
            if position_size > PAPER_MAX_POSITION_SIZE:
                warning(f"🚫 Position size ${position_size:.2f} exceeds max ${PAPER_MAX_POSITION_SIZE:.2f} - blocking trade")
                return 'failed'
            
            # Execute trade
            try:
                nf = self._get_nice_funcs()
                if not nf:
                    error("Trading functions not available")
                    return 'failed'
                    
                initial_balance = nf.get_token_balance_usd(mint, symbol)
                
                # Execute trade (lock removed - using SimpleAgentCoordinator for priority management)
                success = False
                try:
                    debug(f"Executing {action} {symbol} with priority coordination")
                    
                    if action == "BUY":
                        success = nf.market_entry(symbol, position_size, agent="copybot")
                    else:
                            success = nf.partial_kill(symbol, position_size)
                        
                except Exception as e:
                    error(f"Trade execution failed for {action} {symbol}: {str(e)}")
                    return 'failed'
                
                if success:
                    final_balance = nf.get_token_balance_usd(mint, symbol)
                                        # Calculate PnL with proper None handling
                    try:
                        if (final_balance is not None and initial_balance is not None and 
                            isinstance(final_balance, (int, float)) and isinstance(initial_balance, (int, float))):
                            pnl = float(final_balance) - float(initial_balance)
                        else:
                            pnl = 0  # Default to zero PnL if balance check fails
                    except (TypeError, ValueError) as e:
                        warning(f"Error calculating PnL for {mint[:8]}...: {e}")
                        pnl = 0
                    
                    info(f"Successfully mirrored {action} for {symbol}")
                    
                    # Emit signal
                    self.order_executed.emit(
                        "CopyBot", action, symbol, 
                        position_size, 0, 0, 
                        pnl, wallet, mint, f"Mirror trading: Modified token in wallet {wallet[:4]}..."
                    )
                    
                    return 'success'
                else:
                    warning(f"Failed to mirror {action} for {symbol}")
                    return 'failed'
                    
            except Exception as e:
                error(f"Error executing {action} for {symbol}: {str(e)}")
                return 'failed'
                
        except Exception as e:
            error(f"Critical error in mirror modify for {mint[:8]}...: {str(e)}")
            return 'failed'

    def _run_fallback_polling(self):
        """Run fallback polling when webhooks are disabled or as safety mechanism"""
        try:
            # Track start time for performance monitoring
            start_time = time.time()
            cycle_phases = {}  # Track time for each phase
            
            # Check if this is the first run and if we should skip analysis
            first_run = self.is_first_run
            if first_run:
                self.is_first_run = False  # Set to false for future runs
                if getattr(config, 'COPYBOT_SKIP_ANALYSIS_ON_FIRST_RUN', True):
                    info("\nFirst run detected. Fetching tokens without analysis or execution...")
                    # IMPORTANT: In webhook mode, first run should collect baseline data but not execute trades
                    if config.WEBHOOK_MODE:
                        info("🔄 WEBHOOK MODE: Collecting baseline data without trade execution")
                        self._collect_baseline_data_only()
                        return
                    else:
                        # Only collect baseline data in non-webhook mode
                        self._collect_baseline_data_only()
                        return
            
            # Initialize or clear market data cache for fresh data this cycle
            if not hasattr(self, 'market_data_cache'):
                self.market_data_cache = {}
            else:
                # Only clear if we want fresh data every cycle
                refresh_data = getattr(config, 'REFRESH_MARKET_DATA_EVERY_CYCLE', False)
                if refresh_data:
                    info("\nClearing market data cache for fresh analysis")
                    self.market_data_cache = {}
                else:
                    info("\nReusing existing market data cache")
            
            # Create a WalletTracker instance and use it to track wallets
            tracking_start = time.time()
            tracker = WalletTracker()
            
            # Get cached data before any updates
            cached_results, _ = tracker.load_cache()
            
            # Call track_wallets to refresh cached data - Do this ONLY ONCE
            wallet_results, changes = tracker.track_wallets()
            tracking_time = time.time() - tracking_start
            cycle_phases["wallet_tracking"] = tracking_time
            info(f"TIMING: Wallet tracking completed in {tracking_time:.2f} seconds")
            
            # Check if any changes were detected
            has_changes = False
            if changes:
                for wallet, wallet_changes in changes.items():
                    if any(wallet_changes.values()):
                        has_changes = True
                        break
            
            if not has_changes:
                info("No changes detected in tracked wallets")
                return False
            
            # Execute mirror trades for all changes
            if config.PAPER_TRADING_ENABLED:
                info("Executing mirror trades in paper trading mode...")
                success = self.execute_mirror_trades(wallet_results, changes)
                if success:
                    info("Successfully executed mirror trades")
                else:
                    warning("Failed to execute mirror trades")
            else:
                info("Paper trading disabled - skipping trade execution")
            
            # Calculate and report total elapsed time
            total_elapsed = time.time() - start_time
            info(f"Complete analysis cycle finished in {total_elapsed:.2f} seconds")
            return True
            
        except Exception as e:
            error(f"Error in analysis cycle: {str(e)}")
            return False

    def run(self):
        """Main entry point for the CopyBot agent - Webhook-First Architecture"""
        try:
            # Add a running flag for cooperative stopping
            if not hasattr(self, 'running'):
                self.running = True
            else:
                self.running = True  # Reset if re-used

            info("Anarcho Capital's CopyBot Agent starting...")
            
            # Webhook mode - no baseline wallet data collection needed
            info("🔔 WEBHOOK MODE: No baseline wallet data collection needed")
            info("📡 System will process individual webhook events as they arrive")
            
            # Check if webhook mode is enabled
            if config.WEBHOOK_MODE:
                info("🔄 WEBHOOK MODE: CopyBot initialized and waiting for webhook events")
                info("📡 System will only execute trades when triggered by webhook events")
                info("🔔 No automatic polling or change detection will occur")
                
                # Keep the agent alive but don't poll continuously
                while getattr(self, 'running', True):
                    if not getattr(self, 'running', True):
                        break
                    
                    # Check AI exit targets periodically (every 1 minute for responsive exits) - DISABLED
                    if config.AI_EXIT_TARGETS_ENABLED:
                        self.check_exit_targets()
                    
                    # Sleep for a long interval - webhooks will wake us up
                    time.sleep(60)  # 1 minute for faster exit target checking
                    
                    # Only run fallback polling if webhooks haven't triggered recently
                    # This is a safety mechanism, not the primary mode
                    if hasattr(self, 'last_webhook_time'):
                        time_since_webhook = time.time() - self.last_webhook_time
                        if time_since_webhook > 7200:  # 2 hours without webhook
                            warning("⚠️ No webhook events for 2 hours - running fallback polling")
                            self._run_fallback_polling()
                            self.last_webhook_time = time.time()  # Reset timer
                    
            else:
                # Fallback to traditional polling mode if webhooks are disabled
                info("⏱️ POLLING MODE: CopyBot will use interval-based polling")
                
                if config.COPYBOT_SKIP_ANALYSIS_ON_FIRST_RUN:
                    # Skip first analysis if configured
                    info("Skipping first analysis as configured")
                else:
                    # Run the initial analysis cycle
                    self._run_fallback_polling()
                
                # This should be a loop that either runs continuously or with intervals
                while getattr(self, 'running', True):  # Keep running until manually stopped
                    if not getattr(self, 'running', True):
                        break
                    
                    # Check AI exit targets periodically (every 1 minute for responsive exits) - DISABLED
                    if config.AI_EXIT_TARGETS_ENABLED:
                        self.check_exit_targets()
                    
                    if config.COPYBOT_CONTINUOUS_MODE:
                        # In continuous mode, immediately run the next cycle
                        info("Running in continuous mode - starting next cycle...")
                        self._run_fallback_polling()
                    else:
                        # In interval mode, wait before running again
                        next_run = datetime.now() + timedelta(minutes=config.COPYBOT_INTERVAL_MINUTES)
                        info(f"Next run scheduled at {next_run.strftime('%H:%M:%S')}")
                        sleep_time = config.COPYBOT_INTERVAL_MINUTES * 60
                        # Sleep in small increments to allow for cooperative stopping
                        slept = 0
                        while slept < sleep_time:
                            if not getattr(self, 'running', True):
                                break
                            time.sleep(min(1, sleep_time - slept))
                            slept += 1
                        if not getattr(self, 'running', True):
                            break
                        info("Starting scheduled analysis cycle...")
                        self._run_fallback_polling()
                    # Check running flag again at the end of the loop
                    if not getattr(self, 'running', True):
                        break
                        
        except KeyboardInterrupt:
            info("CopyBot agent stopping due to keyboard interrupt...")
        except Exception as e:
            error(f"Error in CopyBot agent: {str(e)}")
            # Log full traceback
            debug(traceback.format_exc(), file_only=True)
    
    def handle_webhook_trigger(self, transaction_data):
        """Handle webhook-triggered copybot analysis - Webhook-First Architecture"""
        try:
            info("🔔 WEBHOOK: CopyBot triggered by transaction event")
            
            # Update last webhook time
            self.last_webhook_time = time.time()
            
            # CRITICAL: Check if harvesting agent has completed startup rebalancing
            if not self._check_harvesting_startup_complete():
                info("⏳ CopyBot waiting for harvesting agent startup rebalancing to complete...")
                return True  # Return success but don't execute trades yet
            
            # Use webhook changes directly if provided, otherwise fall back to wallet tracking
            if 'changes' in transaction_data and transaction_data['changes']:
                info("🔔 WEBHOOK: Using provided webhook changes directly")
                changes = transaction_data['changes']
                wallet_results = None  # Not needed for webhook processing
            else:
                info("🔔 WEBHOOK: No changes provided, falling back to wallet tracking")
                tracker = WalletTracker()
                wallet_results, changes = tracker.track_wallets()
            
            # Check if any changes were detected
            has_changes = False
            if changes:
                for wallet, wallet_changes in changes.items():
                    if any(wallet_changes.values()):
                        has_changes = True
                        break
            
            if has_changes:
                info("🔔 WEBHOOK: Changes detected - executing mirror trades")
                # Execute mirror trades for all changes
                if config.PAPER_TRADING_ENABLED:
                    success = self.execute_mirror_trades(wallet_results, changes)
                    if success:
                        info("✅ Successfully executed webhook-triggered mirror trades")
                    else:
                        warning("❌ Failed to execute webhook-triggered mirror trades")
                else:
                    info("Paper trading disabled - skipping webhook trade execution")
            else:
                info("🔔 WEBHOOK: No changes detected in tracked wallets")
            
            # Webhook mode - no need to store baseline data
            
            info("🔔 WEBHOOK: CopyBot analysis completed")
            return True
            
        except Exception as e:
            error(f"Error in webhook-triggered copybot analysis: {e}")
            return False

    def _check_harvesting_startup_complete(self):
        """Check if harvesting agent has completed startup rebalancing."""
        try:
            # First check global flag as primary indicator
            try:
                from src.config import HARVESTING_STARTUP_DONE
                if HARVESTING_STARTUP_DONE:
                    info("✅ Global harvesting startup flag indicates completion - CopyBot can proceed", file_only=True)
                    return True
            except ImportError:
                pass
            
            # Fallback to harvesting agent instance check
            try:
                from src.scripts.webhooks.webhook_handler import harvesting_agent
                if harvesting_agent and hasattr(harvesting_agent, 'startup_rebalancing_complete'):
                    if harvesting_agent.startup_rebalancing_complete:
                        info("✅ Harvesting agent startup rebalancing complete - CopyBot can proceed")
                        return True
                    else:
                        info("⏳ Harvesting agent startup rebalancing not yet complete")
                        return False
                else:
                    info("ℹ️ No harvesting agent or startup rebalancing not needed - CopyBot can proceed")
                    return True
            except ImportError:
                info("ℹ️ Could not import harvesting agent - CopyBot proceeding")
                return True
                
        except Exception as e:
            error(f"❌ Error checking harvesting startup status: {e}")
            # On error, allow CopyBot to proceed to avoid blocking
            return True

    def get_account_balance(self):
        """Get USDC balance for position sizing - OPTIMIZED FOR USDC-BASED SIZING"""
        try:
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            summary = tracker.get_portfolio_summary()
            
            if not summary:
                return 0.0
                
            # Use USDC balance instead of total portfolio value
            usdc_balance = summary.get('usdc_balance', 0.0)
            debug(f"USDC balance for position sizing: ${usdc_balance:.2f}")
            return usdc_balance
            
        except Exception as e:
            error(f"Error getting USDC balance: {str(e)}")
            return 0.0
    
    def calculate_dynamic_position_size(self, token_address: str, position_type="new", 
                                      pct_change=0, account_balance=None, current_position_usd=None):
        """Calculate position size - SIMPLIFIED, NO RISK AGENT CHECKS"""
        try:
            # Use simple position sizing - no risk agent checks
            return self._calculate_simple_position_size()
                
        except Exception as e:
            error(f"Error calculating dynamic position size: {str(e)}")
            return config.BASE_POSITION_SIZE_USD
    
    def _calculate_preliminary_position_size(self, token_address: str, position_type: str, 
                                           pct_change: float, account_balance: float, 
                                           current_position_usd: float) -> float:
        """Calculate preliminary position size for risk checking"""
        try:
            if account_balance is None:
                account_balance = self.get_account_balance()
            
            if position_type == "new":
                # Use base position size for new positions
                return account_balance * config.POSITION_SIZE_PERCENTAGE
            elif position_type == "increase":
                # Use percentage of current position for increases
                if current_position_usd:
                    return current_position_usd * (pct_change / 100)
                else:
                    return account_balance * config.POSITION_SIZE_PERCENTAGE
            else:
                return account_balance * config.POSITION_SIZE_PERCENTAGE
                
        except Exception as e:
            error(f"Error calculating preliminary position size: {str(e)}")
            return config.usd_size
    
    # Trade lock methods removed - now using SimpleAgentCoordinator for priority management
            
    def check_portfolio_limits(self):
        """Check if we can open new positions without exceeding limits"""
        try:
            nf = self._get_nice_funcs()
            if not nf:
                return False, "nice_funcs not available"
                
            # Get current positions
            current_positions = 0
            total_position_value = 0.0
            account_balance = self.get_account_balance()
            
            try:
                # Get working wallet address
                wallet_address = config.address
                if not wallet_address:
                    wallet_address = os.getenv('DEFAULT_WALLET_ADDRESS')
                    if not wallet_address:
                        warning("⚠️ No wallet address configured - cannot check portfolio limits")
                        return False, "Wallet address not configured"
                
                positions = nf.fetch_wallet_holdings_og(wallet_address)
                for _, row in positions.iterrows():
                    token_address = row['Address']
                    if token_address not in config.EXCLUDED_TOKENS:
                        usd_value = row.get('USD Value', 0)
                        if usd_value and usd_value > config.DUST_THRESHOLD_USD:
                            current_positions += 1
                            total_position_value += usd_value
            except Exception as e:
                debug(f"Error getting positions for limit check: {str(e)}", file_only=True)
                
            # Check maximum concurrent positions
            if current_positions >= config.MAX_CONCURRENT_POSITIONS:
                return False, f"Max positions reached ({current_positions}/{config.MAX_CONCURRENT_POSITIONS})"
                
            # Check total allocation percentage
            if account_balance > 0:
                allocation_pct = total_position_value / account_balance
                if allocation_pct >= config.MAX_TOTAL_ALLOCATION_PERCENT:
                    return False, f"Max allocation reached ({allocation_pct*100:.1f}%/{config.MAX_TOTAL_ALLOCATION_PERCENT*100:.0f}%)"
                    
            return True, "OK"
            
        except Exception as e:
            error(f"Error checking portfolio limits: {str(e)}")
            return False, f"Error checking limits: {str(e)}"
            
    def check_single_position_limit(self, position_size):
        """Check if a single position would exceed the maximum position percentage"""
        try:
            account_balance = self.get_account_balance()
            if account_balance <= 0:
                return True, "OK"  # Allow if we can't determine account balance
                
            position_pct = position_size / account_balance
            max_pct = config.MAX_SINGLE_POSITION_PERCENT
            
            if position_pct > max_pct:
                return False, f"Position too large ({position_pct*100:.1f}% > {max_pct*100:.1f}%)"
                
            return True, "OK"
            
        except Exception as e:
            error(f"Error checking single position limit: {str(e)}")
            return True, "OK"  # Allow on error to avoid blocking trades

    def _normalize_token_symbol_for_lookup(self, symbol: str) -> str:
        """Normalize token symbol for consistent lookups"""
        try:
            from src.nice_funcs import normalize_token_symbol
            return normalize_token_symbol(symbol)
        except ImportError:
            # Fallback normalization if nice_funcs not available
            return symbol.upper().replace(' ', '').replace('-', '').replace('_', '')

    def _find_balance_by_normalized_symbol(self, normalized_symbol: str, original_mint: str) -> float:
        """Find token balance using normalized symbol lookup"""
        try:
            from src.paper_trading import get_paper_portfolio

            if config.PAPER_TRADING_ENABLED:
                portfolio_df = get_paper_portfolio()
                if not portfolio_df.empty:
                    # Look for tokens with matching normalized symbols (check normalized_symbol column first, then fallback)
                    for _, row in portfolio_df.iterrows():
                        # Check normalized_symbol column first (faster)
                        stored_normalized = str(row.get('normalized_symbol', '')).upper()
                        if stored_normalized == normalized_symbol:
                            return float(row.get('amount', 0.0))

                        # Fallback to normalizing the stored symbol
                        if not stored_normalized:
                            stored_symbol = str(row.get('token_symbol', '')).upper()
                            stored_normalized = stored_symbol.replace(' ', '').replace('-', '').replace('_', '')
                            if stored_normalized == normalized_symbol:
                                return float(row.get('amount', 0.0))

            # If not found in paper trading, try live balance lookup
            return self.get_token_balance(original_mint)

        except Exception as e:
            warning(f"Error finding balance by normalized symbol '{normalized_symbol}': {e}")
            return 0.0

    def get_token_balance(self, token_mint: str) -> float:
        """Get token balance from paper trading or live wallet"""
        try:
            if config.PAPER_TRADING_ENABLED:
                from src.paper_trading import get_paper_portfolio
                portfolio = get_paper_portfolio()
                token_row = portfolio[portfolio['token_address'] == token_mint]
                if not token_row.empty:
                    return float(token_row['amount'].iloc[0])
                return 0.0
            else:
                nf = self._get_nice_funcs()
                if not nf:
                    return 0.0
                return nf.get_token_balance(token_mint)
        except Exception as e:
            error(f"Error getting token balance: {e}")
            return 0.0
    
    def _check_for_wallet_updates(self):
        """Webhook mode - no wallet data collection needed"""
        info("🔔 WEBHOOK MODE: No wallet data collection needed")
        info("📡 System will process individual webhook events as they arrive")

    def _collect_baseline_data_only(self):
        """Webhook mode - no baseline data collection needed"""
        info("🔔 WEBHOOK MODE: No baseline data collection needed")
        info("📡 System will process individual webhook events as they arrive")
        info("🚀 COPYBOT IS NOW WAITING FOR WEBHOOK EVENTS")
        return True

    def _store_baseline_data_in_memory(self, wallet_results):
        """Store baseline wallet data in artificial memory JSON for user visibility"""
        try:
            import json
            import os
            from datetime import datetime
            
            # Create artificial memory data structure
            memory_data = {
                "timestamp": datetime.now().isoformat(),
                "type": "baseline_wallet_data",
                "source": "copybot_agent",
                "wallet_count": len(wallet_results),
                "wallets": {}
            }
            
            # Process wallet results into user-friendly format
            for wallet_address, wallet_data in wallet_results.items():
                memory_data["wallets"][wallet_address] = {
                    "address": wallet_address,
                    "total_value_usd": wallet_data.get("total_value_usd", 0),
                    "token_count": len(wallet_data.get("tokens", {})),
                    "tokens": {}
                }
                
                # Add token details
                if "tokens" in wallet_data:
                    for token_address, token_data in wallet_data["tokens"].items():
                        memory_data["wallets"][wallet_address]["tokens"][token_address] = {
                            "symbol": token_data.get("symbol", "UNKNOWN"),
                            "amount": float(token_data.get("amount", 0)),
                            "value_usd": float(token_data.get("value_usd", 0)),
                            "price_usd": float(token_data.get("price_usd", 0))
                        }
            
            # Determine file path under repo root (works locally and on Render)
            try:
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                data_dir = os.path.join(repo_root, "data")
                os.makedirs(data_dir, exist_ok=True)
                file_path = os.path.join(data_dir, "artificial_memory_d.json")
            except Exception:
                # Fallback to current working directory
                file_path = os.path.join("src", "data", "artificial_memory_d.json")
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Build minimal snapshot: only mint and amount per wallet
            minimal_snapshot = {
                "timestamp": memory_data["timestamp"],
                "wallets": {}
            }

            for wallet_address, wallet_data in wallet_results.items():
                tokens = []
                for mint, token_info in (wallet_data.get("tokens") or {}).items():
                    amt = token_info.get("amount", 0)
                    try:
                        amt = float(amt)
                    except Exception:
                        amt = 0.0
                    if amt and amt > 0:
                        tokens.append({"mint": mint, "amount": amt})
                minimal_snapshot["wallets"][wallet_address] = {"tokens": tokens}

            # OVERWRITE the file (do not merge with WalletTracker structure)
            with open(file_path, 'w') as f:
                json.dump(minimal_snapshot, f, indent=2)

            info(f"💾 Baseline wallet data stored in {file_path}")
            info(f"📊 Stored data for {len(wallet_results)} wallets")
            
        except Exception as e:
            error(f"Error storing baseline data in memory: {e}")

    # REMOVED: Background price fetching methods - now handled by wallet_tracker.py

    def _perform_ai_confirmation(self, token_address: str) -> Dict[str, Any]:
        """Perform AI confirmation analysis for buy decision"""
        try:
            if not config.AI_CONFIRMATION_ENABLED:
                return {'approved': True, 'reason': 'AI confirmation disabled', 'exit_target_pct': 0.5}
            
            from src.scripts.trading.ai_confirmation import get_ai_confirmation
            ai_confirmation = get_ai_confirmation()
            
            result = ai_confirmation.analyze_buy_opportunity(token_address)
            
            # Safely handle confidence formatting
            confidence = result.get('confidence', 0.0)
            if confidence is None:
                confidence = 0.0
                
            status = 'APPROVED' if result['approved'] else 'REJECTED'
            info(f"AI Confirmation for {token_address[:8]}...: {status} (Confidence: {confidence:.1%})")
            
            return result
            
        except Exception as e:
            error(f"AI confirmation error: {e}")
            # Fail-open: allow trade if AI confirmation fails
            return {'approved': True, 'reason': f'AI error: {str(e)}', 'exit_target_pct': 0.5}

    def process_parsed_transaction(self, parsed_event: Dict) -> bool:
        """Process fully parsed transaction from webhook handler
        
        Args:
            parsed_event: Pre-parsed transaction with wallet, token, action, amount
            
        Returns:
            True if trade executed, False otherwise
        """
        try:
            # Import logging functions at the top
            from src.scripts.shared_services.logger import info, warning, error
            import time
            
            # Extract parsed data
            signature = parsed_event.get('signature')
            accounts = parsed_event.get('accounts', [])
            
            # Check if accounts exist
            if not accounts:
                info("🔍 No accounts found in parsed event - skipping")
                return False
            
            # Deduplicate based on signature
            current_time = time.time()
            
            if signature in self.recent_transactions:
                last_seen = self.recent_transactions[signature]
                if current_time - last_seen < self.transaction_window:
                    # Duplicate detected - log debug info
                    info(f"🔍 Duplicate transaction: {signature[:8]}... (seen {current_time - last_seen:.1f}s ago)")
                    return False
            
            # Record this transaction
            self.recent_transactions[signature] = current_time
            
            # Clean up old entries
            self.recent_transactions = {
                sig: ts for sig, ts in self.recent_transactions.items()
                if current_time - ts < self.transaction_window
            }
            
            # Get price service for token metadata
            from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
            price_service = get_optimized_price_service()
            
            # Track processing results
            processed_accounts = 0
            successful_trades = 0
            rejection_reasons = []
            
            for account in accounts:
                wallet = account.get('wallet')
                token = account.get('token')
                action = account.get('action')  # 'buy' or 'sell'
                amount = account.get('amount')
                
                processed_accounts += 1
                
                # Handle missing action
                if not action:
                    info(f"⏭️  Signal #{processed_accounts}: No action → SKIP")
                    rejection_reasons.append("No action specified")
                    continue
                
                # Skip if not tracked wallet
                if wallet not in self.tracked_wallets:
                    info(f"🚫 Signal #{processed_accounts}: Wallet {wallet[:8]}... not tracked")
                    rejection_reasons.append(f"Untracked wallet {wallet[:8]}...")
                    continue
                
                # Initialize token_symbol early to avoid undefined variable error
                token_symbol = 'UNK'
                token_name = 'Unknown Token'
                
                info(f"📥 Signal #{processed_accounts}: {action.upper()} ${amount:,.0f} {token_symbol} | Wallet: {wallet[:8]}...")
                
                # Create token_data dict for existing methods
                token_data = {
                    'amount': amount,
                    'usd_value': amount,  # Webhook should provide USD value
                    'symbol': 'UNK',  # Will be resolved by price service
                    'name': 'Unknown Token'  # Will be resolved by price service
                }
                
                # Resolve metadata
                try:
                    from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
                    metadata_service = get_token_metadata_service()
                    metadata = metadata_service.get_metadata(token)
                    if metadata:
                        token_data['symbol'] = metadata.get('symbol', 'UNK')
                        token_data['name'] = metadata.get('name', 'Unknown Token')
                        token_symbol = metadata.get('symbol', 'UNK')
                        token_name = metadata.get('name', 'Unknown Token')
                    else:
                        # Keep the default values already set
                        warning(f"Could not resolve metadata for token {token[:8]}...")
                except Exception as e:
                    # Keep the default values already set
                    warning(f"Failed to get token metadata for {token[:8]}...: {e}")
                
                # Check constraints before executing trades
                if action == 'buy':
                    # CRITICAL: Check portfolio limits FIRST before AI analysis
                    # This saves API costs when we can't buy anyway
                    if self._should_stop_buying():
                        info(f"⚠️ Portfolio at capacity - skipping buy")
                        continue
                    
                    # Get current token balance to check if new or existing
                    current_balance = self.get_token_balance(token)
                    is_new_token = current_balance <= 0
                    
                    # Get current price
                    current_price = price_service.get_price(token)
                    if not current_price or current_price <= 0:
                        info(f"⚠️  Signal #{processed_accounts}: Invalid price ${current_price} for {token_symbol}")
                        rejection_reasons.append(f"Invalid price for {token_symbol}")
                        continue
                    
                    # AI confirmation ONLY for NEW tokens
                    if is_new_token:
                        # Perform AI confirmation
                        ai_result = self._perform_ai_confirmation(token)
                        
                        # Safely handle confidence formatting
                        confidence = ai_result.get('confidence', 0.0)
                        if confidence is None:
                            confidence = 0.0
                        
                        if not ai_result['approved']:
                            info(f"❌ Signal #{processed_accounts}: {token_symbol} REJECTED by AI | Confidence: {confidence:.0%} | Reason: {ai_result['reason']}")
                            rejection_reasons.append(f"AI rejected {token_symbol}: {ai_result['reason']}")
                            continue
                        
                        # Store exit target for position management (no stop loss) - DISABLED
                        if config.AI_EXIT_TARGETS_ENABLED:
                            exit_target = ai_result.get('exit_target_pct', 0.5)  # Default to 50% if None
                            if exit_target is None:
                                exit_target = 0.5
                                
                            self.exit_targets[token] = {
                                'target_pct': exit_target,
                                'stop_loss_pct': None,  # Disabled
                                'entry_price': current_price,
                                'timestamp': time.time()
                            }
                        
                        info(f"✅ Signal #{processed_accounts}: {token_symbol} APPROVED by AI | Confidence: {confidence:.0%} | {ai_result['reason']}")
                    else:
                        info(f"📊 Signal #{processed_accounts}: Increasing position in {token_symbol} (no AI check needed)")
                        
                        # Update exit target if exists (averaging up scenario) - DISABLED
                        if config.AI_EXIT_TARGETS_ENABLED and token in self.exit_targets:
                            # Recalculate average entry price
                            old_entry = self.exit_targets[token]['entry_price']
                            # Simple average for now (can be weighted later if needed)
                            new_entry = (old_entry + current_price) / 2
                            self.exit_targets[token]['entry_price'] = new_entry
                            self.exit_targets[token]['timestamp'] = time.time()
                            info(f"📈 Updated exit target entry price: ${new_entry:.6f} (stop loss disabled)")
                    
                    # Execute buy (works for both new and existing tokens)
                    result = self._execute_mirror_buy(wallet, token, token_data, price_service)
                    
                else:  # sell action
                    # Check if all trading should be stopped
                    if self._should_stop_all_trading():
                        info(f"🛑 All trading halted - sell blocked")
                        rejection_reasons.append("All trading stopped")
                        continue
                    
                    # All sell events use existing logic (no AI confirmation)
                    # Remove exit target if it exists (webhook sell takes priority) - DISABLED
                    if config.AI_EXIT_TARGETS_ENABLED and token in self.exit_targets:
                        del self.exit_targets[token]
                        info(f"🗑️ Removed exit target for {token[:8]}... (webhook sell)")
                    
                    # Get sell type information from webhook data
                    sell_type = account.get('sell_type', 'full')
                    sell_percentage = account.get('sell_percentage', 100)
                    
                    # Route to appropriate sell method based on type
                    if sell_type == 'half':
                        result = self._execute_half_sell(wallet, token, token_data, price_service)
                    elif sell_type == 'partial' and sell_percentage != 100:
                        result = self._execute_partial_sell(wallet, token, token_data, price_service, sell_percentage)
                    else:  # full sell or default
                        result = self._execute_mirror_sell(wallet, token, token_data, price_service)
                
                if result == 'success':
                    successful_trades += 1
                    return True
                elif result == 'stopped':
                    rejection_reasons.append("Trade stopped by system")
                    return False
                elif result == 'skipped':
                    rejection_reasons.append("Trade skipped")
                    return False
                else:
                    rejection_reasons.append("Trade failed")
                    return False
                    
            # Log summary of processing results
            if successful_trades > 0:
                info(f"🎯 Result: {successful_trades} trades executed from {processed_accounts} signals")
            else:
                if rejection_reasons:
                    reasons_str = ", ".join(rejection_reasons[:3])  # Show first 3 reasons
                    if len(rejection_reasons) > 3:
                        reasons_str += f" (+{len(rejection_reasons)-3} more)"
                    info(f"🚫 Result: {processed_accounts} signals analyzed, 0 trades | Reasons: {reasons_str}")
                else:
                    info(f"🚫 Result: {processed_accounts} signals analyzed, 0 trades executed")
            return False
            
        except Exception as e:
            error(f"Error processing parsed transaction: {e}")
            return False

    def check_exit_targets(self):
        """Check positions against AI-recommended exit targets (DISABLED - AI Analysis handles exits)"""
        if not config.AI_EXIT_TARGETS_ENABLED:
            return  # Exit targets disabled
            
        try:
            if not self.exit_targets:
                debug("No exit targets to check")
                return
            
            debug(f"Checking {len(self.exit_targets)} exit targets...")
            
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            portfolio = tracker.get_portfolio_balances()
            
            if not portfolio or 'positions' not in portfolio:
                warning("No portfolio data available for exit target checking")
                return
            
            for token_address, exit_info in list(self.exit_targets.items()):
                # Find position in portfolio
                position = None
                for pos in portfolio['positions']:
                    if pos.get('token_address') == token_address:
                        position = pos
                        break
                
                if not position:
                    # Position closed, remove exit target
                    info(f"🗑️ Position closed - removing exit target for {token_address[:8]}...")
                    del self.exit_targets[token_address]
                    continue
                
                # Calculate current gain/loss
                entry_price = exit_info['entry_price']
                current_price = self.price_service.get_price(token_address)
                
                if not current_price or current_price <= 0:
                    warning(f"No valid price for {token_address[:8]}... - skipping exit check")
                    continue
                
                gain_pct = (current_price - entry_price) / entry_price
                
                # Check exit conditions (stop loss disabled)
                target_pct = exit_info['target_pct']
                stop_loss_pct = exit_info['stop_loss_pct']  # Will be None (disabled)
                
                symbol = position.get('symbol', 'UNK')
                
                # Log current status
                debug(f"Exit check: {symbol} - Entry: ${entry_price:.6f}, Current: ${current_price:.6f}, Gain: {gain_pct:.1%}, Target: {target_pct:.1%}")
                
                if gain_pct >= target_pct:
                    info(f"🎯 Exit target reached for {symbol}: {gain_pct:.1%} >= {target_pct:.1%}")
                    self._execute_target_exit(token_address, position, reason='target_reached')
                    del self.exit_targets[token_address]
                    
                # Stop loss is disabled - no stop loss checking
                    
        except Exception as e:
            error(f"Error checking exit targets: {e}")

    def _execute_target_exit(self, token_address: str, position: dict, reason: str):
        """Execute exit using existing sell methods"""
        try:
            symbol = position.get('symbol', 'UNK')
            info(f"Executing exit for {symbol} - Reason: {reason}")
            
            # Create token_data for sell method
            token_data = {
                'symbol': symbol,
                'name': position.get('name', 'Unknown'),
                'amount': position.get('amount', 0)
            }
            
            # Use existing _execute_mirror_sell method (100% exit)
            result = self._execute_mirror_sell(
                wallet='ai_exit',  # Dummy wallet for tracking
                mint=token_address,
                token_data=token_data,
                price_service=self.price_service
            )
            
            if result == 'success':
                info(f"✅ Successfully exited {symbol} position")
            else:
                warning(f"❌ Failed to exit {symbol}: {result}")
                
        except Exception as e:
            error(f"Error executing target exit: {e}")

    def analyze_extreme_gains_positions(self, snapshot):
        """Analyze positions with extreme gains using AI"""
        try:
            if not config.AI_GAINS_ANALYSIS["enabled"]:
                return
            
            info("🤖 Copybot AI analysis triggered by portfolio tracker")
            
            # snapshot.positions is Dict[str, float] = {token_address: usd_value}
            for token_address, current_value in snapshot.positions.items():
                if not token_address:
                    continue
                
                # Ensure current_value is a number, not a dict
                if isinstance(current_value, dict):
                    # If it's a dict, try to get the value_usd
                    current_value = current_value.get('value_usd', 0)
                elif not isinstance(current_value, (int, float)):
                    current_value = 0
                
                if current_value <= 0:
                    continue
                
                # Check if position needs AI analysis
                if self._should_analyze_position(token_address, current_value):
                    self._perform_ai_analysis(token_address, current_value)
                    break  # Only analyze the first qualifying position
                    
        except Exception as e:
            error(f"Error analyzing extreme gains positions: {e}")

    def _should_analyze_position(self, token_address: str, current_value: float) -> bool:
        """Check if position should be analyzed by AI"""
        try:
            # CRITICAL: Skip AI analysis if position has exit target
            # Exit targets take priority over AI analysis
            if token_address in self.exit_targets:
                return False
            
            # Get current portfolio value for position size calculation
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            portfolio_data = tracker.get_portfolio_balances()
            
            if not portfolio_data:
                return False
                
            total_value = portfolio_data.get('total_usd', 0)
            if total_value <= 0:
                return False
            
            # Calculate position size percentage
            position_size_pct = current_value / total_value
            
            # Check position size trigger first (more important for risk management)
            if position_size_pct >= config.AI_GAINS_ANALYSIS["thresholds"].get("position_size_trigger", 0.15):
                info(f"✅ Position {token_address[:8]}... qualifies for AI analysis: {position_size_pct:.1%} of portfolio")
                return True
            
            # Get entry price for gains calculation
            entry_price = self._get_entry_price(token_address)
            if not entry_price or entry_price.entry_price_usd <= 0:
                return False
            
            # Calculate gains multiplier
            current_price = self.price_service.get_price(token_address)
            if not current_price or (isinstance(current_price, dict) or float(current_price) <= 0):
                return False
            
            gains_multiplier = current_price / entry_price.entry_price_usd
            
            # Check gains trigger
            if gains_multiplier >= config.AI_GAINS_ANALYSIS["thresholds"]["analysis_trigger"]:
                info(f"✅ Position {token_address[:8]}... qualifies for AI analysis: {gains_multiplier:.1f}x gains")
                return True
            
            return False
            
        except Exception as e:
            error(f"Error checking if position should be analyzed: {e}")
            return False


    def _perform_ai_analysis(self, token_address: str, current_value: float):
        """Perform AI analysis on position with extreme gains using OHLCV data"""
        try:
            import os
            
            # UPDATE COOLDOWN IMMEDIATELY to prevent repeated analysis
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            if tracker:
                tracker._update_ai_analysis_cooldown(token_address)
            
            # Initialize DeepSeek client if needed
            if not hasattr(self, 'deepseek_client') or not self.deepseek_client:
                import openai
                deepseek_key = os.getenv('DEEPSEEK_KEY')
                if deepseek_key:
                    self.deepseek_client = openai.OpenAI(
                        api_key=deepseek_key,
                        base_url="https://api.deepseek.com"
                    )
                else:
                    error("No DeepSeek API key available")
                    return
            
            # Get position data
            entry_price = self._get_entry_price(token_address)
            current_price = self.price_service.get_price(token_address)
            
            if not entry_price or not current_price:
                warning(f"Missing price data for {token_address[:8]}...")
                return
                
            gains_multiplier = current_price / entry_price.entry_price_usd
            gains_percentage = (gains_multiplier - 1) * 100
            
            # Fetch OHLCV data for technical analysis
            ohlcv_data = self._fetch_ohlcv_for_analysis(token_address)
            if ohlcv_data is None or ohlcv_data.empty:
                warning(f"No OHLCV data available for {token_address[:8]}... - skipping AI analysis")
                return
            else:
                # Calculate technical indicators from OHLCV data
                technical_indicators = self._calculate_technical_indicators(ohlcv_data)
            
            # Determine trigger reason
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            portfolio_data = tracker.get_portfolio_balances() if tracker else {}
            total_value = portfolio_data.get('total_usd', 0)
            position_size_pct = (current_value / total_value * 100) if total_value > 0 else 0
            
            if position_size_pct >= 15:
                trigger_reason = f"Position size {position_size_pct:.1f}% of portfolio"
            elif gains_percentage >= 300:
                trigger_reason = f"Gains {gains_percentage:.1f}%"
            else:
                trigger_reason = "Portfolio analysis"
            
            # Create AI prompt with OHLCV data
            prompt = self._create_ai_analysis_prompt(
                token_address, current_value, entry_price.entry_price_usd, current_price, 
                gains_multiplier, gains_percentage, technical_indicators, 
                position_size_pct, trigger_reason
            )
            
            # Get AI recommendation using DeepSeek
            model = config.COPYBOT_MODEL_OVERRIDE
            info(f"Using {model} for copybot analysis...")
            
            response = self.deepseek_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are Anarcho Capital's CopyBot AI. Analyze positions and make exit decisions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.7,
                stream=False
            )
            
            ai_response = response.choices[0].message.content.strip()
            recommendation = self._parse_ai_recommendation(ai_response)
            
            # Show AI decision and reason
            info(f"🤖 AI Decision: {recommendation}")
            info(f"🤖 AI Reason: {ai_response}")
            
            # Execute recommendation
            if recommendation in ["SELL_PARTIAL", "SELL_HALF", "SELL_ALL"]:
                self._execute_ai_recommendation(token_address, current_value, recommendation)
            
        except Exception as e:
            error(f"Error performing AI analysis: {e}")

    def _create_ai_analysis_prompt(self, token_address: str, current_value: float, 
                                  entry_price: float, current_price: float, 
                                  gains_multiplier: float, gains_percentage: float,
                                  technical_indicators: dict, position_size_pct: float, 
                                  trigger_reason: str) -> str:
        """Create comprehensive AI analysis prompt for exit decision with OHLCV data"""
        # Get token symbol
        symbol = self._get_token_symbol(token_address)
        
        # Extract technical indicators with defaults
        rsi = technical_indicators.get('rsi', 50.0)
        rsi_signal = technical_indicators.get('rsi_signal', '(Neutral)')
        macd_signal = technical_indicators.get('macd_signal', 'Insufficient Data')
        volume_trend = technical_indicators.get('volume_trend', 'Stable')
        volume_change = technical_indicators.get('volume_change', 0.0)
        atr_pct = technical_indicators.get('atr_pct', 0.0)
        
        # Get on-chain data
        onchain_data = self._get_onchain_data(token_address)
        onchain_activity = self._format_onchain_data(onchain_data) if onchain_data else "N/A"
        
        # Format prompt using template from config
        prompt = config.COPYBOT_AI_ANALYSIS_PROMPT.format(
            symbol=symbol,
            token_address_short=token_address[:8],
            entry_price=entry_price,
            current_price=current_price,
            current_value=current_value,
            gains_multiplier=gains_multiplier,
            gains_percentage=gains_percentage,
            rsi=rsi,
            rsi_signal=rsi_signal,
            macd_signal=macd_signal,
            volume_trend=volume_trend,
            volume_change=volume_change,
            atr_pct=atr_pct,
            onchain_activity=onchain_activity,
            position_size_pct=position_size_pct,
            trigger_reason=trigger_reason
        )
        
        return prompt

    def _get_onchain_data(self, token_address: str) -> Optional[Dict]:
        """Get on-chain data for token from agent cache"""
        try:
            from src.agents.onchain_agent import get_onchain_agent
            agent = get_onchain_agent()
            return agent.get_token_data(token_address) if agent else None
        except Exception as e:
            debug(f"Could not get onchain data: {e}")
            return None

    def _format_onchain_data(self, data: Dict) -> str:
        """Format on-chain data for AI prompt"""
        new_holders = data.get('new_holders_24h', 0)
        holder_growth_pct = data.get('holder_growth_pct', 0)
        tx_count = data.get('tx_count_24h', 0)
        liquidity = data.get('liquidity_usd', 0)
        whale_pct = data.get('holder_distribution', {}).get('whale_pct', 0)
        trend = data.get('trend_signal', 'UNKNOWN')
        
        return f"""
- New Holders (24h): {new_holders:+d} ({holder_growth_pct:.1f}%)
- Transactions (24h): {tx_count:,}
- Liquidity: ${liquidity/1e6:.2f}M
- Whale Concentration: {whale_pct:.1f}%
- Trend: {trend}"""

    def _parse_ai_recommendation(self, response: str) -> str:
        """Parse AI response to extract recommendation"""
        try:
            response_upper = response.strip().upper()
            
            if "SELL_PARTIAL" in response_upper or "PARTIAL" in response_upper or "25%" in response_upper:
                return "SELL_PARTIAL"
            elif "SELL_HALF" in response_upper or "HALF" in response_upper or "50%" in response_upper:
                return "SELL_HALF"
            elif "SELL_ALL" in response_upper or ("SELL" in response_upper and "ALL" in response_upper):
                return "SELL_ALL"
            elif "HOLD" in response_upper or "KEEP" in response_upper:
                return "HOLD"
            else:
                return "HOLD"
                
        except Exception as e:
            error(f"Error parsing AI recommendation: {e}")
            return "HOLD"

    def _execute_ai_recommendation(self, token_address: str, current_value: float, recommendation: str):
        """Execute AI recommendation by placing appropriate trade"""
        try:
            if recommendation == "SELL_PARTIAL":
                sell_percentage = 0.25  # Sell 25%
                info(f"🤖 AI recommends SELL_PARTIAL: {token_address[:8]}... ({sell_percentage:.1%})")
                self._execute_ai_sell(token_address, sell_percentage)
                
            elif recommendation == "SELL_HALF":
                sell_percentage = 0.5  # Sell 50%
                info(f"🤖 AI recommends SELL_HALF: {token_address[:8]}... ({sell_percentage:.1%})")
                self._execute_ai_sell(token_address, sell_percentage)
                
            elif recommendation == "SELL_ALL":
                sell_percentage = 0.95  # Sell 95% to account for slippage
                info(f"🤖 AI recommends SELL_ALL: {token_address[:8]}... ({sell_percentage:.1%})")
                self._execute_ai_sell(token_address, sell_percentage)
                
            elif recommendation == "HOLD":
                # No action needed for HOLD - already logged above
                pass
                
            else:
                warning(f"🤖 Unknown AI recommendation: {recommendation} for {token_address[:8]}...")
                
        except Exception as e:
            error(f"Error executing AI recommendation: {e}")

    def _execute_ai_sell(self, token_address: str, sell_percentage: float):
        """Execute AI-driven sell order for unrealized gains"""
        try:
            from src.paper_trading import execute_paper_trade
            
            # Get token metadata
            token_symbol = 'UNK'
            token_name = 'Unknown Token'
            try:
                from src.scripts.data_processing.token_metadata_service import get_token_metadata_service
                metadata_service = get_token_metadata_service()
                metadata = metadata_service.get_metadata(token_address)
                if metadata:
                    token_symbol = metadata.get('symbol', 'UNK')
                    token_name = metadata.get('name', 'Unknown Token')
            except Exception as e:
                debug(f"Could not get token metadata for {token_address[:8]}...: {e}")
            
            # Get current token balance
            token_balance = self.get_token_balance(token_address)
            if token_balance <= 0:
                warning(f"No balance found for {token_address[:8]}... - skipping AI sell")
                return False
            
            # Calculate sell amount
            sell_amount = token_balance * sell_percentage
            if sell_amount <= 0:
                warning(f"Invalid sell amount for {token_address[:8]}... - skipping")
                return False
            
            # Get current price
            current_price = self.price_service.get_price(token_address)
            if not current_price or (isinstance(current_price, dict) or float(current_price) <= 0):
                warning(f"No price available for {token_address[:8]}... - skipping AI sell")
                return False
            
            # CRITICAL: Validate price before using
            if isinstance(current_price, (int, float)) and current_price > 100:
                warning(f"🚫 Rejecting unrealistic price ${current_price:.6f} for {token_address[:8]}...")
                return False
            
            # Execute paper trade
            success = execute_paper_trade(
                token_address=token_address,
                action="SELL",
                amount=sell_amount,
                price=current_price,
                agent="copybot",
                token_symbol=token_symbol,
                token_name=token_name
            )
            
            if success:
                info(f"✅ AI sell executed: {sell_amount:.2f} {token_symbol} @ ${current_price:.6f}")
                return True
            else:
                error(f"❌ AI sell failed for {token_symbol}")
                return False
                
        except Exception as e:
            error(f"Error executing AI sell: {e}")
            return False

    def _check_extreme_gains_fallback(self):
        """Fallback method to check for extreme gains when portfolio tracker doesn't trigger"""
        try:
            if not config.AI_GAINS_ANALYSIS["enabled"]:
                return
            
            # Get current portfolio from portfolio tracker
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            portfolio_data = tracker.get_portfolio_balances()
            
            if not portfolio_data or 'positions' not in portfolio_data:
                return
            
            # Check each position
            for position in portfolio_data['positions']:
                token_address = position.get('token_mint')
                current_value = position.get('value_usd', 0)
                
                if token_address and current_value > 0:
                    if self._should_analyze_position(token_address, current_value):
                        info(f"🔄 Fallback monitoring triggered AI analysis for {token_address[:8]}...")
                        self._perform_ai_analysis(token_address, current_value)
                        
        except Exception as e:
            error(f"Error in copybot fallback check: {e}")

    def _validate_position_with_fallback(self, token_address: str, amount: float) -> Tuple[bool, str]:
        """Validate position with fallback when position validator unavailable"""
        try:
            from src.scripts.trading.position_validator import validate_position_exists
            return validate_position_exists(token_address, amount, "copybot")
        except Exception as e:
            warning(f"Position validator unavailable, using fallback: {e}")
            return self._basic_position_check(token_address, amount)

    def _get_entry_price(self, token_address: str) -> float:
        """Get entry price for token from entry price tracker"""
        try:
            from src.scripts.database.entry_price_tracker import get_entry_price_tracker
            tracker = get_entry_price_tracker()
            record = tracker.get_entry_price(token_address)
            return record.entry_price_usd if record else 0.0
        except Exception as e:
            error(f"Error getting entry price for {token_address}: {e}")
            return 0.0

    def _get_token_symbol(self, token_address: str) -> str:
        """Get token symbol from address or Jupiter"""
        try:
            import requests
            # Try Jupiter first
            url = f"https://lite-api.jup.ag/tokens/v2?ids={token_address}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and token_address in data['data']:
                    token_data = data['data'][token_address]
                    if token_data and token_data.get("symbol"):
                        return token_data["symbol"]
            
            # Fallback: use first 8 chars of address
            return f"{token_address[:8]}..."
            
        except Exception as e:
            error(f"Error getting token symbol for {token_address}: {e}")
            return f"{token_address[:8]}..."

    def _basic_position_check(self, token_address: str, amount: float) -> Tuple[bool, str]:
        """Basic position validation when position validator unavailable"""
        try:
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            portfolio_data = tracker.get_portfolio_balances()
            
            if not portfolio_data:
                return False, "Portfolio data unavailable"
            
            current_value = self._get_current_position_value(token_address)
            new_value = current_value + (amount * self.price_service.get_price(token_address))
            total_value = portfolio_data.get('total_value_usd', 0)
            
            if total_value > 0 and new_value / total_value > 0.15:  # 15% emergency limit
                return False, f"Position would exceed 15% limit: {new_value/total_value*100:.1f}%"
            
            return True, "Basic validation passed"
            
        except Exception as e:
            error(f"Error in basic position check: {e}")
            return False, f"Validation error: {str(e)}"

    def _fetch_ohlcv_for_analysis(self, token_address: str) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for AI exit analysis (same as AI Confirmation)"""
        try:
            import os
            import requests
            import pandas as pd
            from src.config import AI_CONFIRMATION_LOOKBACK_DAYS, AI_CONFIRMATION_TIMEFRAME
            
            # Handle None or invalid token addresses
            if not token_address or not isinstance(token_address, str):
                warning("Invalid token address provided for OHLCV data")
                return None
                
            api_key = os.getenv("BIRDEYE_API_KEY")
            if not api_key:
                warning("No Birdeye API key available for OHLCV data")
                return None
            
            # Calculate time range
            end_time = int(time.time())
            start_time = end_time - (AI_CONFIRMATION_LOOKBACK_DAYS * 24 * 3600)
            
            # Fetch OHLCV data
            url = f"https://public-api.birdeye.so/defi/ohlcv"
            params = {
                'address': token_address,
                'type': AI_CONFIRMATION_TIMEFRAME,  # '1H'
                'time_from': start_time,
                'time_to': end_time
            }
            headers = {"X-API-KEY": api_key}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    candles = data['data']
                    if candles:
                        # Convert to DataFrame
                        df = pd.DataFrame(candles)
                        df['date'] = pd.to_datetime(df['time'], unit='s')
                        df = df.sort_values('time').reset_index(drop=True)
                        return df
            
            warning(f"Failed to fetch OHLCV data for {token_address[:8]}...")
            return None
            
        except Exception as e:
            error(f"Error fetching OHLCV data for {token_address[:8]}...: {e}")
            return None

    def _calculate_technical_indicators(self, ohlcv_data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate RSI, MACD, Volume trends, ATR for exit analysis"""
        try:
            import numpy as np
            from src.ta_indicators import ta
            
            if ohlcv_data is None or ohlcv_data.empty:
                return {}
            
            # Ensure we have required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in ohlcv_data.columns for col in required_cols):
                warning("OHLCV data missing required columns")
                return {}
            
            # Calculate RSI (14 period)
            rsi_values = ta.rsi(ohlcv_data['close'], length=14)
            current_rsi = rsi_values.iloc[-1] if not rsi_values.empty else 50.0
            
            # Determine RSI signal
            if current_rsi > 70:
                rsi_signal = "(Overbought)"
            elif current_rsi < 30:
                rsi_signal = "(Oversold)"
            else:
                rsi_signal = "(Neutral)"
            
            # Calculate MACD (12, 26, 9)
            macd_line, macd_signal_line, macd_histogram = ta.macd(ohlcv_data['close'], fast=12, slow=26, signal=9)
            
            # Determine MACD signal
            if len(macd_line) >= 2 and len(macd_signal_line) >= 2:
                current_macd = macd_line.iloc[-1]
                current_signal = macd_signal_line.iloc[-1]
                prev_macd = macd_line.iloc[-2]
                prev_signal = macd_signal_line.iloc[-2]
                
                if current_macd > current_signal and prev_macd <= prev_signal:
                    macd_signal = "Bullish Crossover"
                elif current_macd < current_signal and prev_macd >= prev_signal:
                    macd_signal = "Bearish Crossover"
                elif current_macd > current_signal:
                    macd_signal = "Bullish Above Signal"
                else:
                    macd_signal = "Bearish Below Signal"
            else:
                macd_signal = "Insufficient Data"
            
            # Calculate volume trend (10 period average)
            volume_avg = ohlcv_data['volume'].rolling(window=10).mean()
            current_volume = ohlcv_data['volume'].iloc[-1]
            avg_volume = volume_avg.iloc[-1] if not volume_avg.empty else current_volume
            
            volume_change = ((current_volume - avg_volume) / avg_volume * 100) if avg_volume > 0 else 0
            
            if volume_change > 10:
                volume_trend = "Increasing"
            elif volume_change < -10:
                volume_trend = "Decreasing"
            else:
                volume_trend = "Stable"
            
            # Calculate ATR volatility (20 period)
            atr_values = ta.atr(ohlcv_data['high'], ohlcv_data['low'], ohlcv_data['close'], length=20)
            current_atr = atr_values.iloc[-1] if not atr_values.empty else 0.0
            current_price = ohlcv_data['close'].iloc[-1]
            atr_pct = (current_atr / current_price * 100) if current_price > 0 else 0.0
            
            return {
                'rsi': current_rsi,
                'rsi_signal': rsi_signal,
                'macd_signal': macd_signal,
                'volume_trend': volume_trend,
                'volume_change': volume_change,
                'atr_pct': atr_pct
            }
            
        except Exception as e:
            error(f"Error calculating technical indicators: {e}")
            return {}


# Global instance
_copybot_agent = None

def get_copybot_agent():
    """Get the singleton copybot agent instance"""
    global _copybot_agent
    if _copybot_agent is None:
        _copybot_agent = CopyBotAgent()
    return _copybot_agent

if __name__ == "__main__":
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print('\n🛑 Gracefully stopping CopyBot...')
        if 'agent' in locals():
            agent.running = False
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🤖 Starting Anarcho Capital's CopyBot Agent...")
    try:
        agent = CopyBotAgent()
        agent.run()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
