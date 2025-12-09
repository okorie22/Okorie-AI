"""
🎛️ ITORO Config Manager - Safe Configuration Control Surface
Provides whitelisted, validated parameter control for the Master Agent
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from src.scripts.shared_services.logger import info, warning, error, debug

@dataclass
class ConfigChange:
    """Record of a configuration change"""
    timestamp: str
    parameter: str
    old_value: Any
    new_value: Any
    reason: str
    agent: str
    confidence: float
    category: str  # 'data' or 'trading'
    
@dataclass
class ConfigParameter:
    """Definition of a controllable config parameter"""
    name: str
    category: str  # 'data' or 'trading'
    min_value: Optional[Any]
    max_value: Optional[Any]
    allowed_values: Optional[List[Any]]
    validation_func: Optional[str]  # Name of validation function
    hot_reload: bool  # Can be changed without restart
    description: str

class ConfigManager:
    """
    Safe configuration management with whitelisting and validation
    Provides a control surface for the Master Agent to adjust system configs
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # Initialize storage
        self.data_dir = Path("src/data/master_agent")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.changes_file = self.data_dir / "config_changes.json"
        self.active_changes_file = self.data_dir / "active_changes.json"
        
        # Track changes
        self.change_history: List[ConfigChange] = []
        self.active_changes: Dict[str, Any] = {}  # Currently active overrides
        
        # Load history
        self._load_change_history()
        self._load_active_changes()
        
        # Define whitelisted parameters
        self.parameters = self._define_parameters()
        
        info("🎛️ Config Manager initialized")
    
    def _define_parameters(self) -> Dict[str, ConfigParameter]:
        """Define all whitelisted config parameters with validation rules"""
        
        params = {}
        
        # =================================================================
        # DATA COLLECTION PARAMETERS (Auto-adjustable)
        # =================================================================
        
        # Chart Analysis
        params["CHART_ANALYSIS_TIMEFRAME"] = ConfigParameter(
            name="CHART_ANALYSIS_TIMEFRAME",
            category="data",
            min_value=None,
            max_value=None,
            allowed_values=["1m", "5m", "15m", "30m", "1H", "4h", "1D"],
            validation_func=None,
            hot_reload=True,
            description="Timeframe for chart analysis data collection (default: 4h)"
        )
        
        params["CHART_ANALYSIS_LOOKBACK"] = ConfigParameter(
            name="CHART_ANALYSIS_LOOKBACK",
            category="data",
            min_value=1,
            max_value=365,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Days to look back for chart analysis (default: 20 days for 4h timeframe)"
        )
        
        params["CHART_ANALYSIS_NUM_CANDLES"] = ConfigParameter(
            name="CHART_ANALYSIS_NUM_CANDLES",
            category="data",
            min_value=10,
            max_value=500,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Number of candlesticks to analyze (default: 120 bars)"
        )
        
        # Whale Agent
        params["WHALE_UPDATE_INTERVAL_HOURS"] = ConfigParameter(
            name="WHALE_UPDATE_INTERVAL_HOURS",
            category="data",
            min_value=6,
            max_value=168,  # 1 week max
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Hours between whale data updates"
        )
        
        params["WHALE_SCORING_WEIGHTS"] = ConfigParameter(
            name="WHALE_SCORING_WEIGHTS",
            category="data",
            min_value=None,
            max_value=None,
            allowed_values=None,
            validation_func="validate_scoring_weights",
            hot_reload=True,
            description="Scoring weights for whale wallet evaluation (dict)"
        )
        
        # Sentiment Analysis
        params["SENTIMENT_CHECK_INTERVAL"] = ConfigParameter(
            name="SENTIMENT_CHECK_INTERVAL",
            category="data",
            min_value=60,
            max_value=3600,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Seconds between sentiment checks"
        )
        
        # =================================================================
        # TRADING PARAMETERS (Suggestion-only, require approval)
        # =================================================================
        
        # Allocation
        params["MAX_TOTAL_ALLOCATION_PERCENT"] = ConfigParameter(
            name="MAX_TOTAL_ALLOCATION_PERCENT",
            category="trading",
            min_value=0.3,
            max_value=0.95,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Maximum portfolio allocation percentage"
        )
        
        params["PAPER_MAX_TOTAL_ALLOCATION"] = ConfigParameter(
            name="PAPER_MAX_TOTAL_ALLOCATION",
            category="trading",
            min_value=0.3,
            max_value=0.95,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Maximum paper trading allocation percentage"
        )
        
        # Position Sizing
        params["PAPER_MAX_POSITION_SIZE"] = ConfigParameter(
            name="PAPER_MAX_POSITION_SIZE",
            category="trading",
            min_value=10.0,
            max_value=500.0,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Maximum position size in USD (paper trading)"
        )
        
        params["PAPER_MIN_POSITION_SIZE"] = ConfigParameter(
            name="PAPER_MIN_POSITION_SIZE",
            category="trading",
            min_value=1.0,
            max_value=50.0,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Minimum position size in USD (paper trading)"
        )
        
        # Risk Management - ✅ CORRECTED TO USE ACTUAL VARIABLES
        params["RISK_AGENT_COOLDOWN_SECONDS"] = ConfigParameter(
            name="RISK_AGENT_COOLDOWN_SECONDS",
            category="trading",
            min_value=300,
            max_value=7200,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Cooldown between risk agent actions (seconds) - Used by Risk Agent"
        )
        
        params["EMERGENCY_CHECK_INTERVAL_MINUTES"] = ConfigParameter(
            name="EMERGENCY_CHECK_INTERVAL_MINUTES",
            category="trading",
            min_value=15,
            max_value=180,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Hybrid monitoring cycle interval (minutes) - Used by Risk Agent"
        )
        
        params["RISK_LOSS_CONFIDENCE_THRESHOLD"] = ConfigParameter(
            name="RISK_LOSS_CONFIDENCE_THRESHOLD",
            category="trading",
            min_value=50,
            max_value=100,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="AI confidence threshold for loss scenarios - Used by Risk Agent"
        )
        
        params["RISK_GAIN_CONFIDENCE_THRESHOLD"] = ConfigParameter(
            name="RISK_GAIN_CONFIDENCE_THRESHOLD",
            category="trading",
            min_value=50,
            max_value=100,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="AI confidence threshold for gain scenarios - Used by Risk Agent"
        )
        
        # SOL/USDC Reserves
        params["SOL_TARGET_PERCENT"] = ConfigParameter(
            name="SOL_TARGET_PERCENT",
            category="trading",
            min_value=0.05,
            max_value=0.50,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Target SOL reserve percentage"
        )
        
        params["SOL_MINIMUM_PERCENT"] = ConfigParameter(
            name="SOL_MINIMUM_PERCENT",
            category="trading",
            min_value=0.02,
            max_value=0.30,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Minimum SOL reserve percentage"
        )
        
        params["USDC_TARGET_PERCENT"] = ConfigParameter(
            name="USDC_TARGET_PERCENT",
            category="trading",
            min_value=0.10,
            max_value=0.70,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Target USDC reserve percentage"
        )
        
        params["USDC_MINIMUM_PERCENT"] = ConfigParameter(
            name="USDC_MINIMUM_PERCENT",
            category="trading",
            min_value=0.05,
            max_value=0.50,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Minimum USDC reserve percentage"
        )
        
        # Harvesting - ✅ CORRECTED TO USE ACTUAL VARIABLES
        params["HARVESTING_INTERVAL_CHECK_MINUTES"] = ConfigParameter(
            name="HARVESTING_INTERVAL_CHECK_MINUTES",
            category="trading",
            min_value=10,
            max_value=180,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Hybrid monitoring cycle interval (minutes) - Used by Harvesting Agent"
        )
        
        params["HARVESTING_DEVIATION_THRESHOLD"] = ConfigParameter(
            name="HARVESTING_DEVIATION_THRESHOLD",
            category="trading",
            min_value=0.5,
            max_value=10.0,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Deviation % that triggers rebalancing - Used by Harvesting Agent"
        )
        
        params["HARVESTING_AGENT_COOLDOWN_SECONDS"] = ConfigParameter(
            name="HARVESTING_AGENT_COOLDOWN_SECONDS",
            category="trading",
            min_value=600,
            max_value=7200,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Cooldown between harvesting triggers (seconds) - Used by Harvesting Agent"
        )
        
        # CopyBot - REMOVED INTERVAL (webhook-based, not interval-based!)
        # NOTE: COPYBOT_INTERVAL_MINUTES removed - CopyBot uses WEBHOOK_MODE (not intervals)
        
        params["COPYBOT_AI_COOLDOWN_SECONDS"] = ConfigParameter(
            name="COPYBOT_AI_COOLDOWN_SECONDS",
            category="trading",
            min_value=60,
            max_value=3600,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Cooldown between AI analysis per token - Used by CopyBot Agent"
        )
        
        params["COPYBOT_MIN_CONFIDENCE"] = ConfigParameter(
            name="COPYBOT_MIN_CONFIDENCE",
            category="trading",
            min_value=0,
            max_value=100,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Minimum AI confidence threshold - Used by CopyBot Agent"
        )
        
        params["COPYBOT_DUST_THRESHOLD"] = ConfigParameter(
            name="COPYBOT_DUST_THRESHOLD",
            category="trading",
            min_value=0.01,
            max_value=10.0,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Minimum USD value for trading (dust filter) - Used by CopyBot Agent"
        )
        
        # Staking
        params["STAKING_ALLOCATION_PERCENT"] = ConfigParameter(
            name="STAKING_ALLOCATION_PERCENT",
            category="trading",
            min_value=0.0,
            max_value=0.50,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Percentage of SOL to allocate to staking"
        )
        
        # DeFi
        params["DEFI_MAX_ALLOCATION_PERCENT"] = ConfigParameter(
            name="DEFI_MAX_ALLOCATION_PERCENT",
            category="trading",
            min_value=0.0,
            max_value=0.30,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Maximum DeFi allocation percentage"
        )
        
        # Exit Targets & Stop Loss
        params["TAKE_PROFIT_PERCENTAGE"] = ConfigParameter(
            name="TAKE_PROFIT_PERCENTAGE",
            category="trading",
            min_value=5,
            max_value=500,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Profit target percentage for positions"
        )
        
        params["AI_EXIT_STOP_LOSS"] = ConfigParameter(
            name="AI_EXIT_STOP_LOSS",
            category="trading",
            min_value=-0.50,
            max_value=-0.01,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Stop loss percentage (e.g., -0.15 = -15%)"
        )
        
        params["MAX_LOSS_PERCENT"] = ConfigParameter(
            name="MAX_LOSS_PERCENT",
            category="trading",
            min_value=1,
            max_value=50,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Maximum portfolio loss percentage before risk action"
        )
        
        params["MAX_LOSS_USD"] = ConfigParameter(
            name="MAX_LOSS_USD",
            category="trading",
            min_value=10.0,
            max_value=1000.0,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Maximum portfolio loss in USD before risk action"
        )
        
        # Consecutive Loss Tracking
        params["MAX_CONSECUTIVE_LOSSES"] = ConfigParameter(
            name="MAX_CONSECUTIVE_LOSSES",
            category="trading",
            min_value=2,
            max_value=15,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Maximum consecutive losing trades before risk action"
        )
        
        params["CONSECUTIVE_LOSS_LIMIT"] = ConfigParameter(
            name="CONSECUTIVE_LOSS_LIMIT",
            category="trading",
            min_value=2,
            max_value=15,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Consecutive loss limit for emergency actions"
        )
        
        # Breakeven Settings
        params["BREAKEVEN_MIN_PROFIT_PERCENT"] = ConfigParameter(
            name="BREAKEVEN_MIN_PROFIT_PERCENT",
            category="trading",
            min_value=0.001,
            max_value=0.20,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Minimum profit percentage to close at breakeven"
        )
        
        params["BREAKEVEN_MAX_LOSS_PERCENT"] = ConfigParameter(
            name="BREAKEVEN_MAX_LOSS_PERCENT",
            category="trading",
            min_value=-0.50,
            max_value=-0.01,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Maximum loss percentage before forced close"
        )
        
        # AI Exit Targets
        params["AI_EXIT_TARGETS_CONSERVATIVE"] = ConfigParameter(
            name="AI_EXIT_TARGETS_CONSERVATIVE",
            category="trading",
            min_value=0.05,
            max_value=0.50,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Conservative exit target (e.g., 0.20 = 20% gain)"
        )
        
        params["AI_EXIT_TARGETS_MODERATE"] = ConfigParameter(
            name="AI_EXIT_TARGETS_MODERATE",
            category="trading",
            min_value=0.20,
            max_value=1.50,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Moderate exit target (e.g., 0.50 = 50% gain)"
        )
        
        params["AI_EXIT_TARGETS_AGGRESSIVE"] = ConfigParameter(
            name="AI_EXIT_TARGETS_AGGRESSIVE",
            category="trading",
            min_value=0.50,
            max_value=5.0,
            allowed_values=None,
            validation_func=None,
            hot_reload=True,
            description="Aggressive exit target (e.g., 1.0 = 100% gain)"
        )
        
        return params
    
    def validate_change(self, parameter: str, new_value: Any) -> Tuple[bool, str]:
        """
        Validate a proposed config change
        Returns: (is_valid, error_message)
        """
        if parameter not in self.parameters:
            return False, f"Parameter '{parameter}' is not whitelisted"
        
        param_def = self.parameters[parameter]
        
        # Check allowed values
        if param_def.allowed_values is not None:
            if new_value not in param_def.allowed_values:
                return False, f"Value must be one of: {param_def.allowed_values}"
        
        # Check min/max bounds
        if param_def.min_value is not None and isinstance(new_value, (int, float)):
            if new_value < param_def.min_value:
                return False, f"Value must be >= {param_def.min_value}"
        
        if param_def.max_value is not None and isinstance(new_value, (int, float)):
            if new_value > param_def.max_value:
                return False, f"Value must be <= {param_def.max_value}"
        
        # Custom validation
        if param_def.validation_func:
            validation_method = getattr(self, param_def.validation_func, None)
            if validation_method:
                is_valid, msg = validation_method(new_value)
                if not is_valid:
                    return False, msg
        
        return True, ""
    
    def validate_scoring_weights(self, weights: Dict[str, float]) -> Tuple[bool, str]:
        """Validate whale scoring weights"""
        if not isinstance(weights, dict):
            return False, "Scoring weights must be a dictionary"
        
        # Check sum is approximately 1.0
        total = sum(weights.values())
        if not (0.95 <= total <= 1.05):
            return False, f"Weights must sum to ~1.0, got {total:.2f}"
        
        # Check all values are between 0 and 1
        for key, value in weights.items():
            if not (0.0 <= value <= 1.0):
                return False, f"Weight '{key}' must be between 0 and 1"
        
        return True, ""
    
    def apply_change(self, parameter: str, new_value: Any, reason: str, 
                     agent: str = "master_agent", confidence: float = 1.0) -> bool:
        """
        Apply a configuration change
        For data configs: apply immediately
        For trading configs: only store as suggestion (requires approval)
        """
        try:
            # Validate the change
            is_valid, error_msg = self.validate_change(parameter, new_value)
            if not is_valid:
                error(f"❌ Config change rejected: {error_msg}")
                return False
            
            param_def = self.parameters[parameter]
            
            # Get current value from config
            import src.config as config
            old_value = getattr(config, parameter, None)
            
            # Create change record
            change = ConfigChange(
                timestamp=datetime.now().isoformat(),
                parameter=parameter,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                agent=agent,
                confidence=confidence,
                category=param_def.category
            )
            
            # Add to history
            self.change_history.append(change)
            self._save_change_history()
            
            # For data configs: apply immediately
            if param_def.category == "data":
                setattr(config, parameter, new_value)
                self.active_changes[parameter] = new_value
                self._save_active_changes()
                info(f"✅ Applied data config change: {parameter} = {new_value} (reason: {reason})")
                return True
            
            # For trading configs: store as suggestion only
            else:
                info(f"📋 Trading config suggestion created: {parameter} = {new_value} (requires approval)")
                return True
        
        except Exception as e:
            error(f"Error applying config change: {e}")
            return False
    
    def rollback_change(self, parameter: str) -> bool:
        """Rollback a config change to its original value"""
        try:
            if parameter not in self.active_changes:
                warning(f"No active change found for {parameter}")
                return False
            
            # Find the original value from history
            import src.config as config
            
            # Get changes for this parameter
            param_changes = [c for c in self.change_history if c.parameter == parameter]
            if not param_changes:
                warning(f"No history found for {parameter}")
                return False
            
            # Rollback to first recorded old_value
            original_value = param_changes[0].old_value
            setattr(config, parameter, original_value)
            
            # Remove from active changes
            del self.active_changes[parameter]
            self._save_active_changes()
            
            info(f"🔄 Rolled back {parameter} to {original_value}")
            return True
        
        except Exception as e:
            error(f"Error rolling back config: {e}")
            return False
    
    def get_recent_changes(self, hours: int = 24, category: Optional[str] = None) -> List[ConfigChange]:
        """Get recent config changes"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        
        recent = []
        for change in self.change_history:
            change_time = datetime.fromisoformat(change.timestamp).timestamp()
            if change_time >= cutoff_time:
                if category is None or change.category == category:
                    recent.append(change)
        
        return recent
    
    def get_pending_suggestions(self) -> List[ConfigChange]:
        """Get trading config suggestions awaiting approval"""
        # Get recent trading config changes
        trading_changes = self.get_recent_changes(hours=168, category="trading")  # Last week
        
        # Filter for unapproved (those not in active_changes)
        pending = [c for c in trading_changes if c.parameter not in self.active_changes]
        
        return pending
    
    def approve_suggestion(self, parameter: str) -> bool:
        """Approve and apply a trading config suggestion"""
        try:
            # Find the most recent suggestion for this parameter
            suggestions = self.get_pending_suggestions()
            matching = [s for s in suggestions if s.parameter == parameter]
            
            if not matching:
                warning(f"No pending suggestion found for {parameter}")
                return False
            
            # Get most recent
            suggestion = matching[-1]
            
            # Apply the change (runtime only - config.py file update requires restart)
            import src.config as config
            setattr(config, parameter, suggestion.new_value)
            self.active_changes[parameter] = suggestion.new_value
            self._save_active_changes()
            
            # Update config.py file
            self._update_config_file(parameter, suggestion.new_value)
            
            info(f"✅ Approved and applied trading config: {parameter} = {suggestion.new_value}")
            return True
        
        except Exception as e:
            error(f"Error approving suggestion: {e}")
            return False
    
    def reject_suggestion(self, parameter: str) -> bool:
        """Reject a trading config suggestion"""
        try:
            # Find the most recent suggestion for this parameter
            suggestions = self.get_pending_suggestions()
            matching = [s for s in suggestions if s.parameter == parameter]
            
            if not matching:
                warning(f"No pending suggestion found for {parameter}")
                return False
            
            # Mark as rejected by adding to active_changes with old value
            # This prevents it from showing up as pending again
            suggestion = matching[-1]
            self.active_changes[parameter] = suggestion.old_value
            self._save_active_changes()
            
            info(f"❌ Rejected trading config suggestion: {parameter}")
            return True
        
        except Exception as e:
            error(f"Error rejecting suggestion: {e}")
            return False
    
    def _update_config_file(self, parameter: str, new_value: Any):
        """Update the config.py file with new value"""
        try:
            config_file = Path("src/config.py")
            if not config_file.exists():
                error("config.py file not found")
                return
            
            # Read the file
            with open(config_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Find and update the parameter
            updated = False
            for i, line in enumerate(lines):
                # Look for the parameter assignment
                if line.strip().startswith(f"{parameter} ="):
                    # Preserve indentation
                    indent = len(line) - len(line.lstrip())
                    
                    # Format the new value
                    if isinstance(new_value, str):
                        value_str = f'"{new_value}"'
                    elif isinstance(new_value, bool):
                        value_str = str(new_value)
                    elif isinstance(new_value, (int, float)):
                        value_str = str(new_value)
                    else:
                        value_str = repr(new_value)
                    
                    # Get the comment if it exists
                    comment = ""
                    if "#" in line:
                        comment = " " + line.split("#", 1)[1].rstrip()
                    
                    # Update the line
                    lines[i] = f"{' ' * indent}{parameter} = {value_str}{comment}\n"
                    updated = True
                    break
            
            if updated:
                # Write back to file
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                info(f"📝 Updated config.py: {parameter} = {new_value}")
            else:
                warning(f"Parameter {parameter} not found in config.py")
        
        except Exception as e:
            error(f"Error updating config.py file: {e}")
    
    def get_parameter_info(self, parameter: str) -> Optional[ConfigParameter]:
        """Get information about a parameter"""
        return self.parameters.get(parameter)
    
    def list_parameters(self, category: Optional[str] = None) -> List[str]:
        """List all whitelisted parameters"""
        if category:
            return [name for name, param in self.parameters.items() if param.category == category]
        return list(self.parameters.keys())
    
    def _load_change_history(self):
        """Load change history from disk"""
        try:
            if self.changes_file.exists():
                with open(self.changes_file, 'r') as f:
                    data = json.load(f)
                    self.change_history = [ConfigChange(**item) for item in data]
        except Exception as e:
            error(f"Error loading change history: {e}")
            self.change_history = []
    
    def _save_change_history(self):
        """Save change history to disk"""
        try:
            with open(self.changes_file, 'w') as f:
                data = [asdict(change) for change in self.change_history]
                json.dump(data, f, indent=2)
        except Exception as e:
            error(f"Error saving change history: {e}")
    
    def _load_active_changes(self):
        """Load active changes from disk"""
        try:
            if self.active_changes_file.exists():
                with open(self.active_changes_file, 'r') as f:
                    self.active_changes = json.load(f)
        except Exception as e:
            error(f"Error loading active changes: {e}")
            self.active_changes = {}
    
    def _save_active_changes(self):
        """Save active changes to disk"""
        try:
            with open(self.active_changes_file, 'w') as f:
                json.dump(self.active_changes, f, indent=2)
        except Exception as e:
            error(f"Error saving active changes: {e}")

# Singleton accessor
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Get the global ConfigManager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

