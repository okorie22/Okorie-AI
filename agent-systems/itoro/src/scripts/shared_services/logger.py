"""
Logging utilities for Anarcho Capital's Trading Desktop App
Provides consistent logging with UI integration
"""

import os
import logging
from datetime import datetime
import traceback
import sys
import inspect
import re
from pathlib import Path
from colorama import init, Fore, Back, Style
from termcolor import colored
init()

# Global flag to track if dashboard is running (suppress console output)
_DASHBOARD_MODE = False

def set_dashboard_mode(enabled: bool):
    """Set dashboard mode to suppress console output"""
    global _DASHBOARD_MODE
    _DASHBOARD_MODE = enabled

# Import configuration values
try:
    from src.config import (
        LOG_LEVEL,
        LOG_TO_FILE,
        LOG_DIRECTORY,
        LOG_FILENAME,
        LOG_MAX_SIZE_MB,
        LOG_BACKUP_COUNT,
        CONSOLE_LOG_LEVEL,
        SHOW_DEBUG_IN_CONSOLE,
        SHOW_TIMESTAMPS_IN_CONSOLE
    )
except ImportError:
    # Default values if config import fails
    LOG_LEVEL = "INFO"
    LOG_TO_FILE = True
    LOG_DIRECTORY = "logs"
    LOG_FILENAME = "trading_system.log"
    LOG_MAX_SIZE_MB = 10
    LOG_BACKUP_COUNT = 5
    CONSOLE_LOG_LEVEL = "INFO"
    SHOW_DEBUG_IN_CONSOLE = False  # Disabled debug console output to prevent terminal spam
    SHOW_TIMESTAMPS_IN_CONSOLE = True

# Create logger
logger = logging.getLogger("anarcho_capital")

# Set the level based on configuration
level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

logger.setLevel(level_map.get(LOG_LEVEL, logging.INFO))

# Agent color mapping using termcolor
AGENT_COLORS = {
    'staking_agent': 'magenta',         # Purple for staking
    'copybot_agent': 'yellow',          # Yellow for copybot
    'harvesting_agent': 'green',        # Green for harvesting
    'risk_agent': 'red',                # Red for risk management
    'sentiment_agent': 'blue',          # Blue for sentiment
    'whale_agent': 'magenta',           # Magenta for whale tracking (closest to pink)
    'chartanalysis_agent': 'yellow',    # Yellow for chart analysis
    'defi_agent': 'cyan',               # Cyan for DeFi
    'onchain_agent': 'blue',            # Blue for on-chain data
    'oi_agent': 'red',                  # Red for OI agent
    'funding_agent': 'green',           # Green for funding agent
    'master_agent': 'blue',             # Blue for Master Agent (supreme orchestrator)
}

def get_calling_agent_color():
    """
    Detect which agent is calling the logger and return appropriate color
    """
    try:
        # Get the call stack
        frame = inspect.currentframe()
        # Go up the stack to find the calling module
        for _ in range(5):  # Check up to 5 levels up
            frame = frame.f_back
            if frame is None:
                break
            filename = frame.f_code.co_filename
            if 'staking_agent' in filename:
                return AGENT_COLORS['staking_agent']
            elif 'copybot_agent' in filename:
                return AGENT_COLORS['copybot_agent']
            elif 'harvesting_agent' in filename:
                return AGENT_COLORS['harvesting_agent']
            elif 'risk_agent' in filename:
                return AGENT_COLORS['risk_agent']
            elif 'sentiment_agent' in filename:
                return AGENT_COLORS['sentiment_agent']
            elif 'whale_agent' in filename:
                return AGENT_COLORS['whale_agent']
            elif 'chartanalysis_agent' in filename:
                return AGENT_COLORS['chartanalysis_agent']
            elif 'defi_agent' in filename or 'defi' in filename.lower():
                return AGENT_COLORS['defi_agent']
            elif 'onchain_agent' in filename:
                return AGENT_COLORS['onchain_agent']
            elif 'oi_agent' in filename:
                return AGENT_COLORS['oi_agent']
            elif 'funding_agent' in filename:
                return AGENT_COLORS['funding_agent']
            elif 'master_agent' in filename:
                return AGENT_COLORS['master_agent']
    except:
        pass
    return 'white'  # Default to white if we can't detect the agent

# Unicode-safe console output function
def safe_console_print(msg, prefix="", color=None):
    """
    Safely print message to console with Unicode handling for Windows
    """
    try:
        # Try to set console encoding to UTF-8 if on Windows
        if sys.platform == "win32":
            try:
                # Try to set console code page to UTF-8
                os.system("chcp 65001 > nul 2>&1")
            except:
                pass
        
        # Apply color if specified
        if color:
            colored_msg = colored(f"{prefix}{msg}", color)
        else:
            colored_msg = f"{prefix}{msg}"
        
        # Try direct print first
        print(colored_msg)
    except UnicodeEncodeError:
        try:
            # Try with UTF-8 encoding
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
                if color:
                    colored_msg = colored(f"{prefix}{msg}", color)
                else:
                    colored_msg = f"{prefix}{msg}"
                print(colored_msg)
            else:
                # Fallback: encode and decode with replacement
                safe_msg = msg.encode('utf-8', errors='replace').decode('utf-8')
                if color:
                    colored_msg = colored(f"{prefix}{safe_msg}", color)
                else:
                    colored_msg = f"{prefix}{safe_msg}"
                print(colored_msg)
        except:
            # Ultimate fallback: strip all non-ASCII characters
            safe_msg = ''.join(char for char in msg if ord(char) < 128)
            if color:
                colored_msg = colored(f"{prefix}{safe_msg}", color)
            else:
                colored_msg = f"{prefix}{safe_msg}"
            print(colored_msg)

# Check if logger already has handlers to avoid duplicate handlers
# Also check if we're on Windows and disable file logging if there are conflicts
if not logger.handlers:
    # Create file handler if enabled
    if LOG_TO_FILE:
        try:
            # Create log directory if it doesn't exist
            log_dir = Path(LOG_DIRECTORY)
            log_dir.mkdir(exist_ok=True)
            
            # Setup simple file handler (no rotation to prevent Windows locking issues)
            log_path = log_dir / LOG_FILENAME
            file_handler = logging.FileHandler(
                log_path,
                encoding='utf-8',  # Ensure UTF-8 encoding for file logs
                mode='a'  # Append mode
            )
            
            # Always use detailed formatting for file logs
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(level_map.get(LOG_LEVEL, logging.INFO))
            
            logger.addHandler(file_handler)

        except Exception as e:
            # If file logging fails (e.g., permission issues), disable it
            print(f"Warning: Could not initialize file logging: {e}")
            print("Continuing with console-only logging...")

# Logging functions that respect the file_only parameter
def debug(msg, file_only=False):
    """
    Log debug message, optionally only to file
    
    Args:
        msg: The message to log
        file_only: If True, only log to file, not to console
    """
    logger.debug(msg)
    
    # SUPPRESS OUTPUT WHEN DASHBOARD IS RUNNING
    if _DASHBOARD_MODE and not file_only:
        return  # Suppress console output when dashboard is running
    
    # Print to console if not file_only and debug messages are enabled for console
    if not file_only and SHOW_DEBUG_IN_CONSOLE:
        timestamp = datetime.now().strftime("%H:%M:%S") if SHOW_TIMESTAMPS_IN_CONSOLE else ""
        prefix = f"[{timestamp}] " if timestamp else ""
        # Use cyan for debug messages
        safe_console_print(f"DEBUG: {msg}", prefix, 'cyan')

def info(msg, file_only=False):
    """Log info message, optionally only to file
    
    Args:
        msg: The message to log
        file_only: If True, only log to file, not to console
    """
    timestamp = datetime.now().strftime("%H:%M:%S") if SHOW_TIMESTAMPS_IN_CONSOLE else ""
    prefix = f"[{timestamp}] " if timestamp else ""
    
    # Log to file (should work fine with UTF-8)
    logger.info(msg)
    
    # SUPPRESS OUTPUT WHEN DASHBOARD IS RUNNING
    if _DASHBOARD_MODE and not file_only:
        return  # Suppress console output when dashboard is running
    
    # Print to console if not file_only
    if not file_only:
        # Get agent-specific color
        agent_color = get_calling_agent_color()
        
        # Override colors for specific messages (DeFi terminal custom colors)
        # Check if calling from defi context
        defi_context = False
        try:
            # Check call stack for defi-related files
            frame = inspect.currentframe()
            for _ in range(5):
                if frame is None:
                    break
                filename = frame.f_code.co_filename
                if 'defi' in filename.lower():
                    defi_context = True
                    break
                frame = frame.f_back
        except:
            pass
        
        # If we're in a DeFi context, use cyan for all messages (unless overridden below)
        if defi_context:
            agent_color = 'cyan'
        
        # YELLOW messages - First set of initialization messages (DeFi specific)
        if ("DeFi Protocol Manager initialized" in msg or 
            "DeFi Risk Manager initialized" in msg or 
            "Yield Optimizer initialized" in msg or 
            "Telegram Bot initialized" in msg or 
            ("Initialized" in msg and "event triggers" in msg) or
            "DeFi Event Manager initialized" in msg):
            agent_color = 'yellow'
        
        # CYAN messages - Second set (protocols and DeFi infrastructure) - ONLY in defi context
        elif defi_context and ("Initialized solend protocol" in msg or
              "Initialized mango protocol" in msg or
              "Initialized tulip protocol" in msg or
              "DeFi Safety Validator initialized" in msg or
              "Leverage Loop Engine initialized" in msg or
              "Staking-DeFi Coordinator initialized" in msg or
              "AI DeFi Advisor initialized" in msg or
              "SharedDataCoordinator initialized" in msg or
              "Portfolio Tracker initialized" in msg or
              "Position Manager initialized" in msg or
              "Hybrid RPC Manager initialized" in msg or
              "QuickNode URL:" in msg or
              "Helius URL:" in msg or
              "Alternative mainnet RPCs:" in msg or
              "DeFi Integration Layer initialized" in msg or
              "DeFi agent registered with coordinator" in msg or
              "Telegram bot started successfully" in msg or
              "Telegram bot started for DeFi agent" in msg or
              "DeFi Event Manager started successfully" in msg or
              "DeFi event manager started" in msg or
              "DeFi Agent initialized successfully" in msg):
            agent_color = 'cyan'
        
        # CYAN messages - Shared services used by DeFi (always cyan, no defi_context required)
        elif "Rate Monitoring Service initialized" in msg:
            agent_color = 'cyan'
        
        # Remove embedded ANSI color codes from message before printing
        # This prevents conflicts with termcolor
        msg_clean = re.sub(r'\033\[[0-9;]*m', '', msg)
        
        # Safe console output with agent color
        safe_console_print(f"INFO: {msg_clean}", prefix, agent_color)

def warning(msg, file_only=False):
    """Log warning message, optionally only to file
    
    Args:
        msg: The message to log
        file_only: If True, only log to file, not to console
    """
    timestamp = datetime.now().strftime("%H:%M:%S") if SHOW_TIMESTAMPS_IN_CONSOLE else ""
    prefix = f"[{timestamp}] " if timestamp else ""
    
    # Log to file (should work fine with UTF-8)
    logger.warning(msg)
    
    # Print to console if not file_only
    if not file_only:
        # Get agent-specific color
        agent_color = get_calling_agent_color()
        
        # Check if calling from defi context
        defi_context = False
        try:
            frame = inspect.currentframe()
            for _ in range(5):
                if frame is None:
                    break
                filename = frame.f_code.co_filename
                if 'defi' in filename.lower():
                    defi_context = True
                    break
                frame = frame.f_back
        except:
            pass
        
        # If we're in a DeFi context, use cyan for warnings
        if defi_context:
            agent_color = 'cyan'
        
        # Override for specific DeFi warnings to match initialization colors
        if "DeepSeek API key" in msg or "API key not configured" in msg:
            agent_color = 'cyan'
        
        # Remove embedded ANSI color codes from message before printing
        msg_clean = re.sub(r'\033\[[0-9;]*m', '', msg)
        
        # Safe console output with agent color
        safe_console_print(f"WARNING: {msg_clean}", prefix, agent_color)

def error(msg, file_only=False):
    """Log error message, optionally only to file
    
    Args:
        msg: The message to log
        file_only: If True, only log to file, not to console
    """
    timestamp = datetime.now().strftime("%H:%M:%S") if SHOW_TIMESTAMPS_IN_CONSOLE else ""
    prefix = f"[{timestamp}] " if timestamp else ""
    
    # Log to file (should work fine with UTF-8)
    logger.error(msg)
    
    # Print to console if not file_only
    if not file_only:
        # Get agent-specific color
        agent_color = get_calling_agent_color()
        
        # Check if calling from defi context
        defi_context = False
        try:
            frame = inspect.currentframe()
            for _ in range(5):
                if frame is None:
                    break
                filename = frame.f_code.co_filename
                if 'defi' in filename.lower():
                    defi_context = True
                    break
                frame = frame.f_back
        except:
            pass
        
        # If we're in a DeFi context, use cyan for errors
        if defi_context:
            agent_color = 'cyan'
        
        # Remove embedded ANSI color codes from message before printing
        msg_clean = re.sub(r'\033\[[0-9;]*m', '', msg)
        
        # Safe console output with agent color
        safe_console_print(f"ERROR: {msg_clean}", prefix, agent_color)

def critical(msg):
    """Log critical message"""
    timestamp = datetime.now().strftime("%H:%M:%S") if SHOW_TIMESTAMPS_IN_CONSOLE else ""
    prefix = f"[{timestamp}] " if timestamp else ""
    
    # Log to file (should work fine with UTF-8)
    logger.critical(msg)
    
    # Get agent-specific color
    agent_color = get_calling_agent_color()
    
    # Safe console output with agent color
    safe_console_print(f"CRITICAL: {msg}", prefix, agent_color)

def system(msg):
    """Log system message (always visible)"""
    logger.info(f"[SYSTEM] {msg}")
    timestamp = datetime.now().strftime("%H:%M:%S") if SHOW_TIMESTAMPS_IN_CONSOLE else ""
    prefix = f"[{timestamp}] " if timestamp else ""
    # System messages in cyan
    safe_console_print(f"[SYSTEM] {msg}", prefix, 'cyan')

def log_print(msg):
    """Simple print-style logging without prefix"""
    logger.info(msg)
    # Get agent-specific color for log_print
    agent_color = get_calling_agent_color()
    safe_console_print(msg, color=agent_color)

def log_exception(e):
    """Log an exception with traceback"""
    tb = traceback.format_exc()
    logger.error(f"Exception: {str(e)}\n{tb}")
    timestamp = datetime.now().strftime("%H:%M:%S") if SHOW_TIMESTAMPS_IN_CONSOLE else ""
    prefix = f"[{timestamp}] " if timestamp else ""
    # Exceptions in bright red
    safe_console_print(f"ERROR: Exception: {str(e)}", prefix, 'red')

# If this file is run directly, show log file location
if __name__ == "__main__":
    if LOG_TO_FILE:
        print(f"Log file location: {os.path.abspath(os.path.join(LOG_DIRECTORY, LOG_FILENAME))}")
    
    # Test logging
    debug("This is a debug message")
    info("This is an info message")
    warning("This is a warning message")
    error("This is an error message")
    critical("This is a critical message")
    system("This is a system message")
    log_print("This is a simple print message")
    
    try:
        1/0
    except Exception as e:
        log_exception(e)

def setup_file_logging(log_file_path: str):
    """
    Redirect stdout/stderr to log file for agent isolation
    Used by anomaly launcher to send agent output to individual log files
    
    Args:
        log_file_path: Path to log file (e.g., 'logs/oi_agent.log')
    
    Returns:
        Tuple of (original_stdout, original_stderr, log_file)
    """
    from pathlib import Path
    
    # Create logs directory
    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save original streams
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Open log file in append mode with line buffering
    log_file = open(log_file_path, 'a', buffering=1, encoding='utf-8')
    
    # Redirect stdout and stderr
    sys.stdout = log_file
    sys.stderr = log_file
    
    return original_stdout, original_stderr, log_file


def restore_logging(original_stdout, original_stderr, log_file):
    """
    Restore original stdout/stderr and close log file
    
    Args:
        original_stdout: Original stdout stream
        original_stderr: Original stderr stream  
        log_file: Log file to close
    """
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    
    if log_file and not log_file.closed:
        log_file.close()


# Suppress urllib3 connection warnings to log files only
urllib3_logger = logging.getLogger("urllib3.connectionpool")
urllib3_logger.setLevel(logging.ERROR)
urllib3_logger.propagate = False
