"""
MOON DEV Moon Dev's Event-Driven Trading Agent
Executes trades based on strategy signals with flexible risk management
"""

# ============================================================================
# EVENT-DRIVEN TRADING AGENT
# ============================================================================
# This agent listens for trading signals and executes trades immediately.
# It supports flexible risk management for marketplace compatibility:
# - Advanced strategies can provide their own risk parameters
# - Simple strategies use user-defined defaults
# - Safety limits always apply regardless of source
# ============================================================================

import os
import sys
import json
from termcolor import colored, cprint
from datetime import datetime
import time
from pathlib import Path
from typing import Dict, Any

# Add project root to path for imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Local imports
from config import *
from nice_funcs import *
from scripts.shared_services.redis_event_bus import get_event_bus

# Load environment variables
os.environ.setdefault('REDIS_HOST', 'localhost')
os.environ.setdefault('REDIS_PORT', '6379')

class TradingAgent:
    """
    Event-Driven Trading Agent

    Listens for trading signals from strategies and executes trades with flexible risk management.
    Supports marketplace compatibility by allowing strategies to provide their own risk parameters
    while maintaining user safety limits.
    """

    def __init__(self):
        cprint(">>> Initializing Event-Driven Trading Agent...", "cyan")

        # Initialize Redis event bus for signal communication
        self.event_bus = get_event_bus()

        # Risk management configuration
        self.risk_config = self._load_risk_config()

        # Trading state
        self.active_positions = {}  # Track current positions
        self.trade_history = []     # Track executed trades

        # Subscribe to trading signals from strategies
        self.event_bus.subscribe('trading_signal', self.on_trading_signal)

        cprint(">>> Trading Agent initialized - listening for strategy signals", "green")
        cprint(f"$ Risk mode: {'Strategy parameters' if self.risk_config['inherit_strategy_risk'] else 'User defaults'}", "cyan")

    def _load_risk_config(self) -> Dict[str, Any]:
        """Load risk management configuration with marketplace compatibility"""
        return {
            # Safety limits (always applied, user-controlled)
            'safety_limits': {
                'max_position_pct': 0.10,      # Max 10% per trade
                'max_stop_loss_pct': 0.15,     # Max 15% stop loss
                'min_stop_loss_pct': 0.01,     # Min 1% stop loss
                'max_portfolio_risk': 0.20,    # Max 20% total exposure
                'max_open_positions': 5
            },

            # User default risk parameters (when strategy doesn't provide)
            'default_risk': {
                'position_size_pct': 0.05,     # 5% default
                'stop_loss_pct': 0.05,         # 5% default stop
                'take_profit_pct': 0.10,       # 10% default target
                'trailing_stop_pct': 0.03      # 3% trailing stop
            },

            # User preference: inherit strategy risk or use defaults
            'inherit_strategy_risk': True,    # User choice via UI

            # Trading mode: paper or live
            'trading_mode': os.getenv('TRADING_MODE', 'paper'),  # Default to paper trading
        }

    def on_trading_signal(self, signal_data: dict):
        """
        Main entry point for trading signals - EVENT-DRIVEN EXECUTION

        Args:
            signal_data: Trading signal from strategy via Redis
        """
        try:
            cprint(f"SIGNAL: Signal received: {signal_data.get('symbol', 'UNKNOWN')} {signal_data.get('direction', 'UNKNOWN')}", "cyan")

            # Validate signal structure
            if not self._validate_signal(signal_data):
                cprint("ERROR: Invalid signal format - ignoring", "red")
                return

            # Resolve risk parameters (strategy-provided or user defaults)
            risk_params = self._resolve_risk_parameters(signal_data)

            # Apply safety limits
            if not self._check_safety_limits(risk_params, signal_data):
                cprint("ERROR: Trade rejected - safety limits exceeded", "red")
                return

            # Execute the trade
            self._execute_trade(signal_data, risk_params)

        except Exception as e:
            cprint(f"ERROR: Error processing trading signal: {e}", "red")

    def _validate_signal(self, signal_data: dict) -> bool:
        """Validate signal has required fields"""
        required_fields = ['symbol', 'direction', 'confidence']
        return all(field in signal_data for field in required_fields)

    def _resolve_risk_parameters(self, signal_data: dict) -> Dict[str, Any]:
        """
        Resolve risk parameters with flexible logic:
        1. Use strategy-provided parameters if user allows inheritance
        2. Fall back to user defaults otherwise
        """
        strategy_risk = signal_data.get('risk_parameters', {})

        if strategy_risk and self.risk_config['inherit_strategy_risk']:
            # Use strategy-provided risk parameters
            cprint(">>> Using strategy-provided risk parameters", "cyan")
            risk_params = strategy_risk.copy()
        else:
            # Use user default risk parameters
            source_msg = "strategy parameters ignored" if strategy_risk else "no strategy parameters provided"
            cprint(f">>> Using user default risk parameters ({source_msg})", "cyan")
            risk_params = self.risk_config['default_risk'].copy()

        # Ensure all required parameters exist
        risk_params.setdefault('position_size_pct', 0.05)
        risk_params.setdefault('stop_loss_pct', 0.05)
        risk_params.setdefault('take_profit_pct', 0.10)
        risk_params.setdefault('trailing_stop_pct', 0.03)

        return risk_params

    def _check_safety_limits(self, risk_params: Dict[str, Any], signal_data: dict) -> bool:
        """Apply user-defined safety limits that always override"""
        limits = self.risk_config['safety_limits']

        # Check position size
        if risk_params['position_size_pct'] > limits['max_position_pct']:
            cprint(f"ERROR: Position size {risk_params['position_size_pct']:.1%} exceeds limit {limits['max_position_pct']:.1%}", "red")
            return False

        # Check stop loss range
        stop_loss = risk_params['stop_loss_pct']
        if stop_loss < limits['min_stop_loss_pct'] or stop_loss > limits['max_stop_loss_pct']:
            cprint(f"ERROR: Stop loss {stop_loss:.1%} outside allowed range [{limits['min_stop_loss_pct']:.1%}, {limits['max_stop_loss_pct']:.1%}]", "red")
            return False

        # Check portfolio exposure
        total_exposure = sum(pos.get('size_pct', 0) for pos in self.active_positions.values())
        new_exposure = total_exposure + risk_params['position_size_pct']
        if new_exposure > limits['max_portfolio_risk']:
            cprint(f"ERROR: Portfolio exposure {new_exposure:.1%} would exceed limit {limits['max_portfolio_risk']:.1%}", "red")
            return False

        # Check max positions
        if len(self.active_positions) >= limits['max_open_positions']:
            cprint(f"ERROR: Maximum positions ({limits['max_open_positions']}) already reached", "red")
            return False

        # Check for existing position in same symbol
        symbol = signal_data['symbol']
        if symbol in self.active_positions:
            cprint(f"WARNING: Already have position in {symbol} - consider closing first", "yellow")
            # Allow overriding existing positions for now

        return True

    def _execute_trade(self, signal_data: dict, risk_params: Dict[str, Any]):
        """Execute the trade with resolved risk parameters"""
        try:
            symbol = signal_data['symbol']
            direction = signal_data['direction']
            confidence = signal_data['confidence']
            strategy = signal_data.get('strategy_type', 'unknown')

            cprint(f">>> Executing {direction} trade for {symbol}", "green")
            cprint(f"   $ Size: {risk_params['position_size_pct']:.1%} | SL: {risk_params['stop_loss_pct']:.1%} | TP: {risk_params['take_profit_pct']:.1%}", "cyan")
            cprint(f"   >>> Strategy: {strategy} | Confidence: {confidence:.1%}", "cyan")

            # Determine trading mode (paper vs live)
            # Determine trading mode from configuration
            trading_mode = self.risk_config.get('trading_mode', 'paper')

            if trading_mode == 'live':
                success = self._execute_paper_trade(signal_data, risk_params)
            else:
                success = self._execute_live_trade(signal_data, risk_params)

            if success:
                # Record the trade
                trade_record = {
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'direction': direction,
                    'size_pct': risk_params['position_size_pct'],
                    'entry_price': self._get_current_price(symbol),
                    'stop_loss_pct': risk_params['stop_loss_pct'],
                    'take_profit_pct': risk_params['take_profit_pct'],
                    'strategy': strategy,
                    'confidence': confidence,
                    'risk_source': 'strategy' if signal_data.get('risk_parameters') else 'user_defaults'
                }

                self.trade_history.append(trade_record)
                self.active_positions[symbol] = trade_record

                cprint(f"SUCCESS: Trade executed successfully for {symbol}", "green")
            else:
                cprint(f"ERROR: Trade execution failed for {symbol}", "red")

        except Exception as e:
            cprint(f"ERROR: Error executing trade: {e}", "red")

    def _execute_paper_trade(self, signal_data: dict, risk_params: Dict[str, Any]) -> bool:
        """Execute paper trade (simulation)"""
        try:
            symbol = signal_data['symbol']
            direction = signal_data['direction']

            # Get current price (simulated)
            current_price = self._get_current_price(symbol)
            if not current_price:
                return False

            # Calculate position size in USD
            portfolio_value = getattr(n, 'portfolio_value', 10000)  # Default $10k
            position_size_usd = portfolio_value * risk_params['position_size_pct']

            cprint(f"PAPER TRADE: PAPER TRADE: {direction} {symbol} at ${current_price:.4f}", "yellow")
            cprint(f"   $ Position Size: ${position_size_usd:.2f} ({risk_params['position_size_pct']:.1%})", "yellow")

            return True

        except Exception as e:
            cprint(f"ERROR: Paper trade error: {e}", "red")
            return False

    def _execute_live_trade(self, signal_data: dict, risk_params: Dict[str, Any]) -> bool:
        """Execute live trade (use existing live trading logic)"""
        try:
            # This would integrate with existing live trading functions
            # For now, just log that live trading would happen
            # Validate user RPC configuration
            rpc_endpoint = os.getenv('USER_RPC_ENDPOINT')
            if not rpc_endpoint:
                cprint("ERROR: USER_RPC_ENDPOINT not configured for live trading", "red")
                return False

            wallet_address = os.getenv('DEFAULT_WALLET_ADDRESS')
            if not wallet_address:
                cprint("ERROR: DEFAULT_WALLET_ADDRESS not configured", "red")
                return False

            # Get token address
            token_address = self._symbol_to_address(symbol)
            if not token_address:
                cprint(f"ERROR: Cannot resolve token address for {symbol}", "red")
                return False

            # Check wallet balance before trading
            portfolio_value = self._get_live_portfolio_value()
            if not portfolio_value or portfolio_value <= 0:
                cprint("ERROR: Insufficient wallet balance for live trading", "red")
                return False

            # Calculate USD amount
            usd_amount = portfolio_value * position_size_pct

            # Get current price for validation
            current_price = self._get_current_price(symbol)
            if not current_price:
                cprint(f"ERROR: Cannot get price for {symbol}", "red")
                return False

            cprint(f"LIVE TRADE: Executing {direction} ${usd_amount:.2f} of {symbol} (balance: ${portfolio_value:.2f})", "yellow")

            # Execute trade using nice_funcs
            success = False
            if direction.upper() == "BUY":
                # Convert USD to lamports for market_buy
                lamports = int(usd_amount * 1000000)  # 1 USDC = 1,000,000 lamports
                slippage = risk_params.get('slippage', 0.5)  # Default 0.5%

                from nice_funcs import market_buy
                result = market_buy(token_address, lamports, slippage=slippage)
                success = result is not None

            elif direction.upper() == "SELL":
                # For selling, we need token amount - simplified calculation
                token_amount = usd_amount / current_price
                slippage = risk_params.get('slippage', 0.5)

                # market_sell already imported from nice_funcs at top
                result = market_sell(token_address, token_amount, slippage=slippage)
                success = result is not None

            else:
                cprint(f"ERROR: Invalid direction {direction}", "red")
                return False

            if success:
                cprint(f"SUCCESS: Live {direction} trade executed for {symbol}", "green")
                return True
            else:
                cprint(f"FAILED: Live {direction} trade failed for {symbol}", "red")
                return False

        except Exception as e:
            cprint(f"ERROR: Live trade error: {e}", "red")
            return False

    def _get_current_price(self, symbol: str) -> float:
        """Get current price for symbol (placeholder)"""
        # This should integrate with price feed
        # For now, return a mock price
        return 100.0  # Mock price

    def update_risk_config(self, new_config: Dict[str, Any]):
        """Update risk configuration from UI"""
        self.risk_config.update(new_config)
        cprint("CONFIG: Risk configuration updated", "cyan")

    def get_status(self) -> Dict[str, Any]:
        """Get trading agent status for UI"""
        return {
            'active_positions': len(self.active_positions),
            'total_trades': len(self.trade_history),
            'risk_mode': 'strategy_inherited' if self.risk_config['inherit_strategy_risk'] else 'user_defaults',
            'safety_limits': self.risk_config['safety_limits']
        }

    def run_event_loop(self):
        """Main event loop - purely event-driven"""
        cprint(">>> Trading Agent active - listening for strategy signals...", "green")
        cprint("INFO: Risk management ready with safety limits applied", "cyan")

        try:
            while True:
                time.sleep(1)  # Keep alive, signals handled by callbacks
        except KeyboardInterrupt:
            cprint(">>> Trading Agent shutting down gracefully...", "cyan")


def main():
    """Event-driven main function - runs trading agent in signal-response mode"""
    cprint("MOON DEV Event-Driven Trading System Starting Up!", "white", "on_blue")
    cprint(">>> System will respond to strategy signals in real-time", "cyan")

    try:
        agent = TradingAgent()
        agent.run_event_loop()

    except KeyboardInterrupt:
        cprint("\n>>> Moon Dev Trading System shutting down gracefully...", "white", "on_blue")
    except Exception as e:
        cprint(f"\nERROR: Fatal error: {str(e)}", "white", "on_red")
        cprint("SUGGESTION: Moon Dev suggests checking the logs and trying again!", "white", "on_blue")


if __name__ == "__main__":
    main()
class TradingAgent:
    """
    Event-Driven Trading Agent

    Listens for trading signals from strategies and executes trades with flexible risk management.
    Supports marketplace compatibility by allowing strategies to provide their own risk parameters
    while maintaining user safety limits.
    """

    def __init__(self):
        cprint(">>> Initializing Event-Driven Trading Agent...", "cyan")

        # Initialize Redis event bus for signal communication
        self.event_bus = get_event_bus()

        # Risk management configuration
        self.risk_config = self._load_risk_config()

        # Trading state
        self.active_positions = {}  # Track current positions
        self.trade_history = []     # Track executed trades

        # Subscribe to trading signals and config updates
        self.event_bus.subscribe('trading_signal', self.on_trading_signal)
        self.event_bus.subscribe('trading_config_update', self.on_config_update)

        cprint(">>> Trading Agent initialized - listening for strategy signals", "green")
        cprint(f"$ Risk mode: {'Strategy parameters' if self.risk_config['inherit_strategy_risk'] else 'User defaults'}", "cyan")

    def _load_risk_config(self) -> Dict[str, Any]:
        """Load risk management configuration with marketplace compatibility"""
        return {
            # Safety limits (always applied, user-controlled)
            'safety_limits': {
                'max_position_pct': 0.10,      # Max 10% per trade
                'max_portfolio_risk': 0.20,    # Max 20% total exposure
                'max_stop_loss_pct': 0.15,     # Max 15% stop loss
                'min_stop_loss_pct': 0.01,     # Min 1% stop loss
                'max_open_positions': 5
            },

            # User default risk parameters (when strategy doesn't provide)
            'default_risk': {
                'position_size_pct': 0.05,     # 5% default
                'stop_loss_pct': 0.05,         # 5% default stop
                'take_profit_pct': 0.10,       # 10% default target
                'trailing_stop_pct': 0.03      # 3% trailing stop
            },

            # User preference: inherit strategy risk or use defaults
            'inherit_strategy_risk': True,    # User choice via UI

            # Trading mode: paper or live
            'trading_mode': os.getenv('TRADING_MODE', 'paper'),  # Default to paper trading
        }

    def on_trading_signal(self, signal_data: dict):
        """
        Main entry point for trading signals - EVENT-DRIVEN EXECUTION

        Args:
            signal_data: Trading signal from strategy via Redis
        """
        try:
            cprint(f"SIGNAL: Signal received: {signal_data.get('symbol', 'UNKNOWN')} {signal_data.get('direction', 'UNKNOWN')}", "cyan")

            # Validate signal structure
            if not self._validate_signal(signal_data):
                cprint("ERROR: Invalid signal format - ignoring", "red")
                return

            # Resolve risk parameters (strategy-provided or user defaults)
            risk_params = self._resolve_risk_parameters(signal_data)

            # Apply safety limits
            if not self._check_safety_limits(risk_params, signal_data):
                cprint("ERROR: Trade rejected - safety limits exceeded", "red")
                return

            # Execute the trade
            self._execute_trade(signal_data, risk_params)

        except Exception as e:
            cprint(f"ERROR: Error processing trading signal: {e}", "red")

    def on_config_update(self, config_data: str):
        """Handle configuration updates from UI"""
        try:
            if isinstance(config_data, str):
                config = json.loads(config_data)
            else:
                config = config_data

            # Update risk configuration
            self.risk_config.update(config)
            cprint("CONFIG: Risk configuration updated from UI", "cyan")

            # Log key settings
            inherit = config.get('inherit_strategy_risk', True)
            mode = "strategy parameters" if inherit else "user defaults"
            cprint(f">>> Risk mode: {mode}", "cyan")

        except Exception as e:
            cprint(f"ERROR: Error updating configuration: {e}", "red")

    def _validate_signal(self, signal_data: dict) -> bool:
        """Validate signal has required fields"""
        required_fields = ['symbol', 'direction', 'confidence']
        return all(field in signal_data for field in required_fields)

    def _resolve_risk_parameters(self, signal_data: dict) -> Dict[str, Any]:
        """
        Resolve risk parameters with flexible logic:
        1. Use strategy-provided parameters if user allows inheritance
        2. Fall back to user defaults otherwise
        """
        strategy_risk = signal_data.get('risk_parameters', {})

        if strategy_risk and self.risk_config['inherit_strategy_risk']:
            # Use strategy-provided risk parameters
            cprint(">>> Using strategy-provided risk parameters", "cyan")
            risk_params = strategy_risk.copy()
        else:
            # Use user default risk parameters
            source_msg = "strategy parameters ignored" if strategy_risk else "no strategy parameters provided"
            cprint(f">>> Using user default risk parameters ({source_msg})", "cyan")
            risk_params = self.risk_config['default_risk'].copy()

        # Ensure all required parameters exist
        risk_params.setdefault('position_size_pct', 0.05)
        risk_params.setdefault('stop_loss_pct', 0.05)
        risk_params.setdefault('take_profit_pct', 0.10)
        risk_params.setdefault('trailing_stop_pct', 0.03)

        return risk_params

    def _check_safety_limits(self, risk_params: Dict[str, Any], signal_data: dict) -> bool:
        """Apply user-defined safety limits that always override"""
        limits = self.risk_config['safety_limits']

        # Check position size
        if risk_params['position_size_pct'] > limits['max_position_pct']:
            cprint(f"ERROR: Position size {risk_params['position_size_pct']:.1%} exceeds limit {limits['max_position_pct']:.1%}", "red")
            return False

        # Check stop loss range
        stop_loss = risk_params['stop_loss_pct']
        if stop_loss < limits['min_stop_loss_pct'] or stop_loss > limits['max_stop_loss_pct']:
            cprint(f"ERROR: Stop loss {stop_loss:.1%} outside allowed range [{limits['min_stop_loss_pct']:.1%}, {limits['max_stop_loss_pct']:.1%}]", "red")
            return False

        # Check portfolio exposure
        total_exposure = sum(pos.get('size_pct', 0) for pos in self.active_positions.values())
        new_exposure = total_exposure + risk_params['position_size_pct']
        if new_exposure > limits['max_portfolio_risk']:
            cprint(f"ERROR: Portfolio exposure {new_exposure:.1%} would exceed limit {limits['max_portfolio_risk']:.1%}", "red")
            return False

        # Check max positions
        if len(self.active_positions) >= limits['max_open_positions']:
            cprint(f"ERROR: Maximum positions ({limits['max_open_positions']}) already reached", "red")
            return False

        # Check for existing position in same symbol
        symbol = signal_data['symbol']
        if symbol in self.active_positions:
            cprint(f"WARNING: Already have position in {symbol} - consider closing first", "yellow")
            # Allow overriding existing positions for now

        return True

    def _execute_trade(self, signal_data: dict, risk_params: Dict[str, Any]):
        """Execute the trade with resolved risk parameters"""
        try:
            symbol = signal_data['symbol']
            direction = signal_data['direction']
            confidence = signal_data['confidence']
            strategy = signal_data.get('strategy_type', 'unknown')

            cprint(f">>> Executing {direction} trade for {symbol}", "green")
            cprint(f"   $ Size: {risk_params['position_size_pct']:.1%} | SL: {risk_params['stop_loss_pct']:.1%} | TP: {risk_params['take_profit_pct']:.1%}", "cyan")
            cprint(f"   >>> Strategy: {strategy} | Confidence: {confidence:.1%}", "cyan")

            # Determine trading mode (paper vs live)
            # Determine trading mode from configuration
            trading_mode = self.risk_config.get('trading_mode', 'paper')

            if trading_mode == 'live':
                success = self._execute_paper_trade(signal_data, risk_params)
            else:
                success = self._execute_live_trade(signal_data, risk_params)

            if success:
                # Record the trade
                trade_record = {
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'direction': direction,
                    'size_pct': risk_params['position_size_pct'],
                    'entry_price': self._get_current_price(symbol),
                    'stop_loss_pct': risk_params['stop_loss_pct'],
                    'take_profit_pct': risk_params['take_profit_pct'],
                    'strategy': strategy,
                    'confidence': confidence,
                    'risk_source': 'strategy' if signal_data.get('risk_parameters') else 'user_defaults'
                }

                self.trade_history.append(trade_record)
                self.active_positions[symbol] = trade_record

                cprint(f"SUCCESS: Trade executed successfully for {symbol}", "green")
            else:
                cprint(f"ERROR: Trade execution failed for {symbol}", "red")
            
        except Exception as e:
            cprint(f"ERROR: Error executing trade: {e}", "red")

    def _execute_paper_trade(self, signal_data: dict, risk_params: Dict[str, Any]) -> bool:
        """Execute paper trade (simulation)"""
        try:
            symbol = signal_data['symbol']
            direction = signal_data['direction']

            # Get current price (simulated)
            current_price = self._get_current_price(symbol)
            if not current_price:
                return False

            # Calculate position size in USD
            portfolio_value = getattr(n, 'portfolio_value', 10000)  # Default $10k
            position_size_usd = portfolio_value * risk_params['position_size_pct']

            cprint(f"PAPER TRADE: PAPER TRADE: {direction} {symbol} at ${current_price:.4f}", "yellow")
            cprint(f"   $ Position Size: ${position_size_usd:.2f} ({risk_params['position_size_pct']:.1%})", "yellow")

            return True

        except Exception as e:
            cprint(f"ERROR: Paper trade error: {e}", "red")
            return False

    def _execute_live_trade(self, signal_data: dict, risk_params: Dict[str, Any]) -> bool:
        """Execute live trade (use existing live trading logic)"""
        try:
            # This would integrate with existing live trading functions
            # For now, just log that live trading would happen
            # Validate user RPC configuration
            rpc_endpoint = os.getenv('USER_RPC_ENDPOINT')
            if not rpc_endpoint:
                cprint("ERROR: USER_RPC_ENDPOINT not configured for live trading", "red")
                return False

            wallet_address = os.getenv('DEFAULT_WALLET_ADDRESS')
            if not wallet_address:
                cprint("ERROR: DEFAULT_WALLET_ADDRESS not configured", "red")
                return False

            # Get token address
            token_address = self._symbol_to_address(symbol)
            if not token_address:
                cprint(f"ERROR: Cannot resolve token address for {symbol}", "red")
                return False

            # Check wallet balance before trading
            portfolio_value = self._get_live_portfolio_value()
            if not portfolio_value or portfolio_value <= 0:
                cprint("ERROR: Insufficient wallet balance for live trading", "red")
                return False

            # Calculate USD amount
            usd_amount = portfolio_value * position_size_pct

            # Get current price for validation
            current_price = self._get_current_price(symbol)
            if not current_price:
                cprint(f"ERROR: Cannot get price for {symbol}", "red")
                return False

            cprint(f"LIVE TRADE: Executing {direction} ${usd_amount:.2f} of {symbol} (balance: ${portfolio_value:.2f})", "yellow")

            # Execute trade using nice_funcs
            success = False
            if direction.upper() == "BUY":
                # Convert USD to lamports for market_buy
                lamports = int(usd_amount * 1000000)  # 1 USDC = 1,000,000 lamports
                slippage = risk_params.get('slippage', 0.5)  # Default 0.5%

                from nice_funcs import market_buy
                result = market_buy(token_address, lamports, slippage=slippage)
                success = result is not None

            elif direction.upper() == "SELL":
                # For selling, we need token amount - simplified calculation
                token_amount = usd_amount / current_price
                slippage = risk_params.get('slippage', 0.5)

                # market_sell already imported from nice_funcs at top
                result = market_sell(token_address, token_amount, slippage=slippage)
                success = result is not None

            else:
                cprint(f"ERROR: Invalid direction {direction}", "red")
                return False

            if success:
                cprint(f"SUCCESS: Live {direction} trade executed for {symbol}", "green")
                return True
            else:
                cprint(f"FAILED: Live {direction} trade failed for {symbol}", "red")
                return False

        except Exception as e:
            cprint(f"ERROR: Live trade error: {e}", "red")
            return False

    def _get_current_price(self, symbol: str) -> float:
        """Get current price for symbol (placeholder)"""
        # This should integrate with price feed
        # For now, return a mock price
        return 100.0  # Mock price

    def update_risk_config(self, new_config: Dict[str, Any]):
        """Update risk configuration from UI"""
        self.risk_config.update(new_config)
        cprint("CONFIG: Risk configuration updated", "cyan")

    def get_status(self) -> Dict[str, Any]:
        """Get trading agent status for UI"""
        return {
            'active_positions': len(self.active_positions),
            'total_trades': len(self.trade_history),
            'risk_mode': 'strategy_inherited' if self.risk_config['inherit_strategy_risk'] else 'user_defaults',
            'safety_limits': self.risk_config['safety_limits']
        }

    def run_event_loop(self):
        """Main event loop - purely event-driven"""
        cprint(">>> Trading Agent active - listening for strategy signals...", "green")
        cprint("INFO: Risk management ready with safety limits applied", "cyan")

        try:
            while True:
                time.sleep(1)  # Keep alive, signals handled by callbacks
        except KeyboardInterrupt:
            cprint(">>> Trading Agent shutting down gracefully...", "cyan")

    def _get_live_portfolio_value(self) -> float:
        """Get actual wallet balance for live trading"""
        try:
            # Use user RPC endpoint for live trading
            rpc_endpoint = os.getenv('USER_RPC_ENDPOINT')
            rpc_api_key = os.getenv('USER_RPC_API_KEY')

            if not rpc_endpoint:
                cprint("ERROR: USER_RPC_ENDPOINT not configured for live trading", "red")
                return 0.0

            import requests
            headers = {}
            if rpc_api_key:
                headers['Authorization'] = f'Bearer {rpc_api_key}'

            wallet_address = os.getenv('DEFAULT_WALLET_ADDRESS')
            if not wallet_address:
                cprint("ERROR: DEFAULT_WALLET_ADDRESS not configured", "red")
                return 0.0

            # Get USDC balance (primary trading token)
            usdc_address = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountBalance",
                "params": [usdc_address, {"encoding": "jsonParsed"}]
            }

            response = requests.post(rpc_endpoint, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'value' in data['result']:
                    # Convert from smallest unit to USD (USDC has 6 decimals)
                    amount = int(data['result']['value']['amount'])
                    balance_usd = amount / 1000000.0
                    cprint(f"Wallet balance: ${balance_usd:.2f} USDC", "cyan")
                    return balance_usd

            cprint("WARNING: Could not retrieve wallet balance", "yellow")
            return 0.0

        except Exception as e:
            cprint(f"ERROR: Failed to get wallet balance: {e}", "red")
            return 0.0

    def _symbol_to_address(self, symbol: str) -> str:
        """Convert symbol to token address"""
        # Common token mappings - expand as needed
        symbol_map = {
            'SOL': 'So11111111111111111111111111111111111111112',
            'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
            'BTC': '9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E',  # BTC (Wormhole)
            'ETH': '7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs',  # ETH (Wormhole)
        }

        # Handle common variations
        clean_symbol = symbol.upper().strip()

        # Direct match first
        if clean_symbol in symbol_map:
            return symbol_map[clean_symbol]

        # Handle variations
        if clean_symbol.endswith('USDT'):
            base = clean_symbol[:-4]  # Remove USDT
            if base in symbol_map:
                return symbol_map[base]
        elif clean_symbol.endswith('USD'):
            base = clean_symbol[:-3]  # Remove USD
            if base in symbol_map:
                return symbol_map[base]

        # For unknown symbols, log warning
        cprint(f"WARNING: Unknown symbol {symbol}, cannot resolve token address", "yellow")
        return None

def main():
    """Event-driven main function - runs trading agent in signal-response mode"""
    cprint("MOON DEV Moon Dev Event-Driven Trading System Starting Up! >>>", "white", "on_blue")
    cprint(">>> System will respond to strategy signals in real-time", "cyan")

    try:
        agent = TradingAgent()
        agent.run_event_loop()

    except KeyboardInterrupt:
        cprint("\n>>> Moon Dev Trading System shutting down gracefully...", "white", "on_blue")
    except Exception as e:
        cprint(f"\nERROR: Fatal error: {str(e)}", "white", "on_red")
        cprint("SUGGESTION: Moon Dev suggests checking the logs and trying again!", "white", "on_blue")

if __name__ == "__main__":
    main()

    def execute_allocations(self, allocation_dict):
        """Execute the allocations using spot or leverage trading"""
        from config import USE_LEVERAGE_TRADING, LEVERAGE_EXCHANGE, LEVERAGE_SUPPORTED_ASSETS

        try:
            print("\n>>> Moon Dev executing portfolio allocations...")

            # Determine trading mode
            leverage_mode = USE_LEVERAGE_TRADING and LEVERAGE_EXCHANGE == 'hyperliquid'
            if leverage_mode:
                print("LEVERAGE: LEVERAGE MODE: Using Hyperliquid perpetual futures")
            else:
                print("SPOT: SPOT MODE: Using traditional spot trading")
            for token, amount in allocation_dict.items():
                # Skip USDC and other excluded tokens
                if token in EXCLUDED_TOKENS:
                    print(f"$ Keeping ${amount:.2f} in {token}")
                    continue

                print(f"\n>>> Processing allocation for {token}...")

                try:
                    # Check if token is supported for leverage trading
                    token_symbol = self._get_token_symbol(token)
                    is_leverage_supported = leverage_mode and token_symbol in LEVERAGE_SUPPORTED_ASSETS

                    if is_leverage_supported:
                        # LEVERAGE TRADING PATH
                        print(f"LEVERAGE: Executing LEVERAGED trade for {token_symbol}")
                        success = self._execute_leverage_trade(token, amount, 'BUY')
                        if success:
                            print(f"SUCCESS: Leveraged entry complete for {token_symbol}")
                        else:
                            print(f"ERROR: Leveraged entry failed for {token_symbol}")
                    else:
                        # SPOT TRADING PATH (existing logic)
                        current_position = n.get_token_balance_usd(token)
                        target_allocation = amount

                        print(f">>> Target allocation: ${target_allocation:.2f} USD")
                        print(f"DATA: Current position: ${current_position:.2f} USD")

                        if current_position < target_allocation:
                            print(f"SPOT: Executing SPOT entry for {token}")
                            n.ai_entry(token, amount)
                            print(f"SUCCESS: Spot entry complete for {token}")
                        else:
                            print(f"PAUSED: Position already at target size for {token}")

                except Exception as e:
                    print(f"ERROR: Error executing entry for {token}: {str(e)}")

                time.sleep(2)  # Small delay between entries
                
        except Exception as e:
            print(f"ERROR: Error executing allocations: {str(e)}")
            print("SUGGESTION: Moon Dev suggests checking the logs and trying again!")

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
            import nice_funcs_hl as hl
            from config import DEFAULT_LEVERAGE

            # Use the high-level leverage entry function
            result = hl.hyperliquid_leverage_entry(
                token_address=token_address,
                direction=direction,
                confidence=0.8,  # High confidence for AI-driven trades
                usd_size=usd_amount
            )

            return result is not None and result.get('success', False)

        except Exception as e:
            print(f"ERROR: Leverage trade execution failed: {str(e)}")
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
            import nice_funcs_hl as hl

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
            print(f"ERROR: Error getting leverage position for {token_symbol}: {str(e)}")
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
            import nice_funcs_hl as hl

            # Close position using Hyperliquid
            result = hl.hyperliquid_close_position(token_symbol, percentage)

            return result is not None and result.get('success', False)

        except Exception as e:
            print(f"ERROR: Leverage exit failed for {token_symbol}: {str(e)}")
            return False

    def handle_exits(self):
        """Check and exit positions based on SELL or NOTHING recommendations"""
        from config import USE_LEVERAGE_TRADING, LEVERAGE_EXCHANGE, LEVERAGE_SUPPORTED_ASSETS

        cprint("\nCHECKING: Checking for positions to exit...", "white", "on_blue")

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
                cprint(f"\nAI RECOMMENDS: AI Agent recommends {action} for {token}", "white", "on_yellow")
                cprint(f"$ Current {position_type} position: ${current_position:.2f}", "white", "on_blue")

                try:
                    if is_leverage_supported:
                        # LEVERAGE EXIT
                        cprint(f"CLOSING: Closing LEVERAGED position...", "white", "on_cyan")
                        success = self._execute_leverage_exit(token_symbol)
                        if success:
                            cprint(f"SUCCESS: Successfully closed leveraged position", "white", "on_green")
                        else:
                            cprint(f"ERROR: Failed to close leveraged position", "white", "on_red")
                    else:
                        # SPOT EXIT
                        cprint(f"CLOSING: Closing SPOT position with chunk_kill...", "white", "on_cyan")
                        n.chunk_kill(token, max_usd_order_size, slippage)
                        cprint(f"SUCCESS: Successfully closed spot position", "white", "on_green")
                except Exception as e:
                    cprint(f"ERROR: Error closing {position_type} position: {str(e)}", "white", "on_red")
            elif current_position > 0:
                cprint(f"SPOT: Keeping {position_type} position for {token} (${current_position:.2f}) - AI recommends {action}", "white", "on_blue")

    def parse_allocation_response(self, response):
        """Parse the AI's allocation response and handle both string and TextBlock formats"""
        try:
            # Handle TextBlock format from Claude 3
            if isinstance(response, list):
                response = response[0].text if hasattr(response[0], 'text') else str(response[0])
            
            print("DEBUG: Raw response received:")
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
            
            print("\nCLEANED: Cleaned JSON string:")
            print(json_str)
            
            # Parse the cleaned JSON
            allocations = json.loads(json_str)
            
            print("\nDATA: Parsed allocations:")
            for token, amount in allocations.items():
                print(f"  - {token}: ${amount}")
            
            # Validate amounts are numbers
            for token, amount in allocations.items():
                if not isinstance(amount, (int, float)):
                    raise ValueError(f"Invalid amount type for {token}: {type(amount)}")
                if amount < 0:
                    raise ValueError(f"Negative allocation for {token}: {amount}")
            
            return allocations
            
        except Exception as e:
            print(f"ERROR: Error parsing allocation response: {str(e)}")
            print("DEBUG: Raw response:")
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
            
            print("DATA: Parsed allocations:")
            for token, amount in allocations.items():
                print(f"  - {token}: ${amount}")
            
            return allocations
            
        except json.JSONDecodeError as e:
            print(f"ERROR: Error parsing allocation JSON: {e}")
            print(f"DEBUG: Raw text received:\n{allocation_text}")
            return None
        except Exception as e:
            print(f"ERROR: Unexpected error parsing allocations: {e}")
            return None

    def run(self):
        """Run the trading agent (implements BaseAgent interface)"""
        self.run_trading_cycle()

    def run_trading_cycle(self, strategy_signals=None):
        """Run one complete trading cycle"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cprint(f"\nTIME: AI Agent Run Starting at {current_time}", "white", "on_green")
            
            # Collect OHLCV data for all tokens
            cprint("DATA: Collecting market data...", "white", "on_blue")
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
                cprint(f">>> Processing {len(current_strategy_signals)} strategy signals from event bus", "cyan")

            # Analyze each token's data
            for token, data in market_data.items():
                cprint(f"\nAI AGENT: AI Agent Analyzing Token: {token}", "white", "on_green")

                # Include strategy signals for this token if available
                if token in strategy_signals_by_token:
                    signals_for_token = strategy_signals_by_token[token]
                    cprint(f"DATA: Including {len(signals_for_token)} strategy signals in analysis", "cyan")
                    data['strategy_signals'] = signals_for_token

                    # Log strategy signals
                    for signal in signals_for_token:
                        direction = signal.get('direction', 'UNKNOWN')
                        confidence = signal.get('confidence', 0)
                        strategy = signal.get('strategy_type', 'unknown')
                        cprint(f"   >>> {strategy}: {direction} ({confidence:.1%} confidence)", "cyan")

                analysis = self.analyze_market_data(token, data)
                print(f"\nANALYSIS: Analysis for contract: {token}")
                print(analysis)
                print("\n" + "="*50 + "\n")
            
            # Show recommendations summary
            cprint("\nDATA: Moon Dev's Trading Recommendations:", "white", "on_blue")
            summary_df = self.recommendations_df[['token', 'action', 'confidence']].copy()
            print(summary_df.to_string(index=False))
            
            # Handle exits first
            self.handle_exits()
            
            # Then proceed with new allocations
            cprint("\n$ Calculating optimal portfolio allocation...", "white", "on_blue")
            allocation = self.allocate_portfolio()
            
            if allocation:
                cprint("\nPORTFOLIO: Moon Dev's Portfolio Allocation:", "white", "on_blue")
                print(json.dumps(allocation, indent=4))
                
                cprint("\n>>> Executing allocations...", "white", "on_blue")
                self.execute_allocations(allocation)
                cprint("\nSPOT: All allocations executed!", "white", "on_blue")
            else:
                cprint("\nWARNING: No allocations to execute!", "white", "on_yellow")
            
            # Clean up temp data
            cprint("\nCLEANED: Cleaning up temporary data...", "white", "on_blue")
            try:
                for file in os.listdir('temp_data'):
                    if file.endswith('_latest.csv'):
                        os.remove(os.path.join('temp_data', file))
                cprint("SPOT: Temp data cleaned successfully!", "white", "on_green")
            except Exception as e:
                cprint(f"WARNING: Error cleaning temp data: {str(e)}", "white", "on_yellow")
            
        except Exception as e:
            cprint(f"\nERROR: Error in trading cycle: {str(e)}", "white", "on_red")
            cprint("SUGGESTION: Moon Dev suggests checking the logs and trying again!", "white", "on_blue")

def main():
    """Main function to run the trading agent every 15 minutes"""
    cprint("MOON DEV Moon Dev AI Trading System Starting Up! >>>", "white", "on_blue")
    
    agent = TradingAgent()
    INTERVAL = SLEEP_BETWEEN_RUNS_MINUTES * 60  # Convert minutes to seconds
    
    while True:
        try:
            agent.run_trading_cycle()
            
            next_run = datetime.now() + timedelta(minutes=SLEEP_BETWEEN_RUNS_MINUTES)
            cprint(f"\nCOMPLETE: AI Agent run complete. Next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}", "white", "on_green")
            
            # Sleep until next interval
            time.sleep(INTERVAL)
                
        except KeyboardInterrupt:
            cprint("\n>>> Moon Dev AI Agent shutting down gracefully...", "white", "on_blue")
            break
        except Exception as e:
            cprint(f"\nERROR: Error: {str(e)}", "white", "on_red")
            cprint("SUGGESTION: Moon Dev suggests checking the logs and trying again!", "white", "on_blue")
            # Still sleep and continue on error
            time.sleep(INTERVAL)

if __name__ == "__main__":
    main() 

