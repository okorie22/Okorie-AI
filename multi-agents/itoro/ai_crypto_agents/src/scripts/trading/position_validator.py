"""
🌙 Anarcho Capital's Position Validator
Validates positions exist before trading operations
Built with love by Anarcho Capital 🚀
"""

import time
import threading
from typing import Dict, Optional, Tuple, List
from src.scripts.shared_services.logger import debug, info, warning, error, critical
from src import config

class PositionValidator:
    """
    Validates positions exist before trading operations
    Prevents phantom position trading and ensures data integrity
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the position validator"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.validation_cache = {}
        self.cache_lock = threading.RLock()
        self.cache_ttl = 30  # Cache for 30 seconds
        
    
    def validate_position_exists(self, token_address: str, amount: float,
                               agent_name: str = "unknown") -> Tuple[bool, str]:
        """
        Validate that a position exists before selling with phantom position detection

        Args:
            token_address: Token address to validate
            amount: Amount to validate
            agent_name: Name of agent requesting validation

        Returns:
            Tuple of (is_valid, reason)
        """
        # 🚨 COPYBOT SELL BYPASS - NEVER BLOCK COPYBOT SELLS 🚨
        if agent_name.lower() == "copybot":
            debug(f"✅ CopyBot sell bypass: Skipping position validation for {token_address[:8]}...")
            return True, "CopyBot sell - validation bypassed"

        # Startup grace bypass
        import time
        startup_grace = getattr(config, 'VALIDATION_STARTUP_GRACE_SECONDS', 0)
        if startup_grace > 0:
            if not hasattr(config, '_APP_START_TIME'):
                config._APP_START_TIME = time.time()
            
            if time.time() - config._APP_START_TIME < startup_grace:
                info(f"🟢 Startup grace: skipping position validation")
                return True, "Startup grace active"
        
        if not config.POSITION_VALIDATION['ENABLED']:
            return True, "Position validation disabled"
        
        if not config.POSITION_VALIDATION['VALIDATE_BEFORE_SELL']:
            return True, "Sell validation disabled"
        
        try:
            # Check cache first
            cache_key = f"{token_address}_{amount}"
            with self.cache_lock:
                if cache_key in self.validation_cache:
                    cached_result, cached_time = self.validation_cache[cache_key]
                    if time.time() - cached_time < self.cache_ttl:
                        return cached_result
            
            # Get current portfolio data from appropriate source based on trading mode
            from src import paper_trading
            
            if config.PAPER_TRADING_ENABLED:
                # Paper trading mode: use paper trading portfolio
                portfolio_df = paper_trading.get_paper_portfolio()
            else:
                # Live trading mode: use live portfolio data
                # This would need to be implemented based on your live trading setup
                # For now, fall back to paper trading data
                portfolio_df = paper_trading.get_paper_portfolio()
            
            if portfolio_df.empty:
                reason = "No portfolio data available"
                self._cache_result(cache_key, (False, reason))
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            # Find token position
            token_positions = portfolio_df[portfolio_df['token_address'] == token_address]
            
            if token_positions.empty:
                reason = f"No position found for token {token_address[:8]}..."
                self._cache_result(cache_key, (False, reason))
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            current_amount = token_positions['amount'].iloc[0]
            
            # CRITICAL FIX: Normalize amount for validation (handle both raw and token units)
            try:
                from src.scripts.data_processing.token_decimals_helper import normalize_amount_for_validation
                normalized_amount = normalize_amount_for_validation(amount, token_address)
                debug(f"Position validation: current={current_amount:.6f} tokens, requested={amount} -> normalized={normalized_amount:.6f} tokens")
            except ImportError:
                # Fallback if helper not available
                normalized_amount = amount
                debug(f"Token decimals helper not available, using amount as-is: {amount}")
            except Exception as e:
                normalized_amount = amount
                debug(f"Error normalizing amount for validation: {e}, using amount as-is: {amount}")
            
            # PHANTOM POSITION DETECTION: Check for suspicious position data
            if current_amount <= 0:
                reason = f"Position amount is zero or negative: {current_amount}"
                self._cache_result(cache_key, (False, reason))
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            # PHANTOM POSITION DETECTION: Check for extremely large amounts
            if current_amount > 1e15:  # 1 quadrillion tokens - likely data error
                reason = f"Suspicious position amount detected: {current_amount} (possible phantom position)"
                self._cache_result(cache_key, (False, reason))
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            if current_amount < normalized_amount:
                reason = f"Insufficient position: {current_amount:.6f} < {normalized_amount:.6f} tokens"
                self._cache_result(cache_key, (False, reason))
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            # Check minimum position size
            min_size = config.POSITION_VALIDATION['MIN_POSITION_SIZE_USD']
            if amount < min_size:
                reason = f"Position size below minimum: {amount} < {min_size}"
                self._cache_result(cache_key, (False, reason))
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            # PHANTOM POSITION DETECTION: Cross-reference with cloud database
            try:
                from src.scripts.database.cloud_database import get_cloud_database_manager
                cloud_db = get_cloud_database_manager()
                if cloud_db:
                    cloud_portfolio = cloud_db.get_latest_paper_trading_portfolio()
                    if cloud_portfolio:
                        cloud_metadata = cloud_portfolio.get('metadata', {})
                        cloud_positions = cloud_metadata.get('positions', {})
                        cloud_amount = cloud_positions.get(token_address, 0)
                        
                        # Check for significant discrepancy between local and cloud
                        if abs(current_amount - cloud_amount) > max(current_amount * 0.1, 1000):  # 10% or 1000 tokens difference
                            reason = f"Position data mismatch: local={current_amount}, cloud={cloud_amount} (possible phantom position)"
                            self._cache_result(cache_key, (False, reason))
                            warning(f"❌ {agent_name}: {reason}")
                            return False, reason
            except Exception as e:
                debug(f"Cloud database cross-reference failed: {e}")
            
            reason = f"Position validated: {current_amount} >= {amount}"
            self._cache_result(cache_key, (True, reason))
            debug(f"✅ {agent_name}: {reason}")
            return True, reason
            
        except Exception as e:
            reason = f"Position validation error: {str(e)}"
            error(f"❌ {agent_name}: {reason}")
            return False, reason
    
    def validate_usdc_balance(self, required_usdc: float, agent_name: str = "unknown") -> Tuple[bool, str]:
        """
        Validate sufficient USDC balance before buying
        
        Args:
            required_usdc: Required USDC amount
            agent_name: Name of agent requesting validation
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Startup grace bypass
        import time
        startup_grace = getattr(config, 'VALIDATION_STARTUP_GRACE_SECONDS', 0)
        if startup_grace > 0:
            if not hasattr(config, '_APP_START_TIME'):
                config._APP_START_TIME = time.time()
            
            if time.time() - config._APP_START_TIME < startup_grace:
                info(f"🟢 Startup grace: skipping USDC validation")
                return True, "Startup grace active"
        
        if not config.USDC_VALIDATION['ENABLED']:
            return True, "USDC validation disabled"
        
        if not config.POSITION_VALIDATION['VALIDATE_BEFORE_BUY']:
            return True, "Buy validation disabled"
        
        try:
            # Get current portfolio data from appropriate source based on trading mode
            from src import paper_trading
            
            if config.PAPER_TRADING_ENABLED:
                # Paper trading mode: use paper trading portfolio
                portfolio_df = paper_trading.get_paper_portfolio()
            else:
                # Live trading mode: use live portfolio data
                # This would need to be implemented based on your live trading setup
                # For now, fall back to paper trading data
                portfolio_df = paper_trading.get_paper_portfolio()
            
            if portfolio_df.empty:
                reason = "No portfolio data available"
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            # Find USDC position
            usdc_positions = portfolio_df[portfolio_df['token_address'] == config.USDC_ADDRESS]
            
            if usdc_positions.empty:
                # Check if we have sufficient SOL balance that can be converted to USDC
                sol_positions = portfolio_df[portfolio_df['token_address'] == config.SOL_ADDRESS]
                if not sol_positions.empty:
                    sol_amount = sol_positions['amount'].iloc[0]
                    sol_price = sol_positions['last_price'].iloc[0]
                    sol_value_usd = sol_amount * sol_price
                    
                    # Allow trade if SOL value is sufficient (with 20% buffer for conversion)
                    required_with_buffer = required_usdc * 1.2
                    if sol_value_usd >= required_with_buffer:
                        reason = f"No USDC but sufficient SOL: {sol_value_usd:.2f} >= {required_with_buffer:.2f} (will convert)"
                        debug(f"✅ {agent_name}: {reason}")
                        return True, reason
                
                reason = "No USDC balance available and insufficient SOL for conversion"
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            current_usdc = usdc_positions['amount'].iloc[0]
            
            # CRITICAL FIX: Detect and convert lamports to USD
            # USDC uses 6 decimals, so 1 USDC = 1000000 lamports
            # If required_usdc is suspiciously large (>10000), it's likely in lamports
            if required_usdc > 10000:
                # Convert from lamports to USD (6 decimals for USDC)
                required_usdc_usd = required_usdc / 1000000
                debug(f"Detected lamports input: {required_usdc} → ${required_usdc_usd:.2f} USD")
                required_usdc = required_usdc_usd
            else:
                debug(f"Detected USD input: ${required_usdc:.2f}")
            
            # Add small tolerance for floating-point precision issues
            tolerance = 0.01  # 1 cent tolerance
            if current_usdc < (required_usdc - tolerance):
                reason = f"Insufficient USDC: {current_usdc:.2f} < {required_usdc:.2f}"
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            # Check minimum balance threshold
            min_balance = config.USDC_VALIDATION['MIN_BALANCE_USD']
            if current_usdc < min_balance:
                reason = f"USDC below minimum balance: {current_usdc:.2f} < {min_balance}"
                warning(f"❌ {agent_name}: {reason}")
                return False, reason
            
            # Check warning threshold
            warning_threshold = config.USDC_VALIDATION['WARNING_THRESHOLD_USD']
            if current_usdc < warning_threshold:
                warning(f"⚠️ {agent_name}: USDC balance low: {current_usdc:.2f} < {warning_threshold}")
            
            reason = f"USDC validated: {current_usdc:.2f} >= {required_usdc:.2f}"
            debug(f"✅ {agent_name}: {reason}")
            return True, reason
            
        except Exception as e:
            reason = f"USDC validation error: {str(e)}"
            error(f"❌ {agent_name}: {reason}")
            return False, reason
    
    def validate_trading_allowed(self, agent_name: str) -> Tuple[bool, str]:
        """
        Validate that trading is allowed for the agent
        
        Args:
            agent_name: Name of agent requesting validation
            
        Returns:
            Tuple of (is_valid, reason)
        """
        try:
            # Check if copybot is halted
            if agent_name.lower() == 'copybot':
                from src.agents.risk_agent import get_risk_agent
                risk_agent = get_risk_agent()
                
                # Check halt flags - for CopyBot, let execution-time gate decide
                if hasattr(risk_agent, 'copybot_halt_reason') and risk_agent.copybot_halt_reason:
                    # CopyBot proceeds to execution-time gate instead of being blocked here
                    info(f"⏸️ {agent_name}: Halt flag exists but allowing execution-time gate to decide")
                
                if hasattr(risk_agent, 'copybot_stop_reason') and risk_agent.copybot_stop_reason:
                    reason = f"Copybot stopped: {risk_agent.copybot_stop_reason}"
                    warning(f"🛑 {agent_name}: {reason}")
                    return False, reason
            
            # Check if harvesting is rebalancing (for copybot)
            if agent_name.lower() == 'copybot' and config.COPYBOT_HALT_FLAGS['HARVESTING_REBALANCING']:
                if self._is_harvesting_rebalancing():
                    reason = "Harvesting agent is rebalancing - copybot halted"
                    warning(f"⏸️ {agent_name}: {reason}")
                    return False, reason
            
            return True, "Trading allowed"
            
        except Exception as e:
            reason = f"Trading validation error: {str(e)}"
            error(f"❌ {agent_name}: {reason}")
            return False, reason
    
    def _is_harvesting_rebalancing(self) -> bool:
        """Check if harvesting agent is currently rebalancing"""
        try:
            # Trade lock manager removed - using SimpleAgentCoordinator
            # For now, assume no rebalancing is in progress
            return False
            
        except Exception as e:
            debug(f"Error checking harvesting rebalancing status: {e}")
            return False
    
    def _cache_result(self, cache_key: str, result: Tuple[bool, str]):
        """Cache validation result"""
        with self.cache_lock:
            self.validation_cache[cache_key] = (result, time.time())
            
            # Clean old cache entries
            current_time = time.time()
            expired_keys = [
                key for key, (_, timestamp) in self.validation_cache.items()
                if current_time - timestamp > self.cache_ttl
            ]
            for key in expired_keys:
                del self.validation_cache[key]
    
    def clear_cache(self):
        """Clear validation cache"""
        with self.cache_lock:
            self.validation_cache.clear()
            debug("Position validation cache cleared")

# Global instance
def get_position_validator() -> PositionValidator:
    """Get the global position validator instance"""
    return PositionValidator()

# Convenience functions
def validate_position_exists(token_address: str, amount: float, agent_name: str = "unknown") -> Tuple[bool, str]:
    """Validate position exists"""
    validator = get_position_validator()
    return validator.validate_position_exists(token_address, amount, agent_name)

def validate_usdc_balance(required_usdc: float, agent_name: str = "unknown") -> Tuple[bool, str]:
    """Validate USDC balance"""
    validator = get_position_validator()
    return validator.validate_usdc_balance(required_usdc, agent_name)

def validate_trading_allowed(agent_name: str) -> Tuple[bool, str]:
    """Validate trading is allowed"""
    validator = get_position_validator()
    return validator.validate_trading_allowed(agent_name)