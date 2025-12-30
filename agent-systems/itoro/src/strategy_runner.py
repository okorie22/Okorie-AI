"""
Strategy Runner
Manages execution of trading strategies (starting with Pattern Detection)
"""
import sys
import os
from pathlib import Path
from typing import Optional, Dict
import threading
import logging

# Add pattern-detector directory to path
sys.path.insert(0, str(Path(__file__).parent / "pattern-detector"))

from pattern_service import PatternService

logger = logging.getLogger(__name__)


class StrategyRunner:
    """
    Manages execution of trading strategies.
    Currently supports Pattern Detection strategy, with architecture to support
    additional strategies in the future.
    """
    
    def __init__(self):
        self.active_strategy = None
        self.strategy_thread = None
        self.running = False
        self.strategy_name = None
        
        logger.info("[STRATEGY RUNNER] Strategy Runner initialized")
        
    def start_pattern_detection(self, config: dict) -> tuple[bool, str]:
        """
        Start pattern detection strategy.
        
        Args:
            config: Configuration dict with keys:
                - symbols: List of symbols to monitor (default: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'])
                - scan_interval: Seconds between scans (default: 300)
                - timeframe: OHLCV timeframe (default: '1d')
                
        Returns:
            Tuple of (success: bool, message: str)
        """
        if self.running:
            return False, "Strategy already running. Stop current strategy first."
        
        try:
            logger.info("[STRATEGY RUNNER] Starting Pattern Detection strategy...")
            
            # Extract config with defaults
            symbols = config.get('symbols', ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'])
            scan_interval = config.get('scan_interval', 300)
            timeframe = config.get('timeframe', '1d')
            
            # Ensure symbols is a list
            if isinstance(symbols, str):
                symbols = [s.strip() for s in symbols.split(',')]
            
            logger.info(f"[STRATEGY RUNNER] Config - Symbols: {symbols}, Interval: {scan_interval}s, Timeframe: {timeframe}")
            
            # Initialize pattern service
            self.active_strategy = PatternService(
                symbols=symbols,
                scan_interval=scan_interval,
                data_timeframe=timeframe
            )
            
            # Start strategy in separate thread
            self.strategy_thread = threading.Thread(
                target=self.active_strategy.run,
                daemon=True,
                name="PatternDetectionThread"
            )
            self.strategy_thread.start()
            
            self.running = True
            self.strategy_name = "Pattern Detection"
            
            logger.info("[STRATEGY RUNNER] Pattern Detection strategy started successfully")
            return True, f"Pattern Detection started - monitoring {len(symbols)} symbols"
            
        except Exception as e:
            logger.error(f"[STRATEGY RUNNER] Failed to start Pattern Detection: {e}")
            self.active_strategy = None
            self.running = False
            return False, f"Failed to start strategy: {str(e)}"
    
    def stop_strategy(self) -> tuple[bool, str]:
        """
        Stop the currently active strategy.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.active_strategy:
            return False, "No active strategy to stop"
        
        try:
            logger.info(f"[STRATEGY RUNNER] Stopping {self.strategy_name}...")
            
            # Stop the strategy
            self.active_strategy.stop()
            
            # Wait for thread to finish (with timeout)
            if self.strategy_thread and self.strategy_thread.is_alive():
                self.strategy_thread.join(timeout=5.0)
            
            strategy_name = self.strategy_name
            self.active_strategy = None
            self.strategy_thread = None
            self.running = False
            self.strategy_name = None
            
            logger.info(f"[STRATEGY RUNNER] {strategy_name} stopped successfully")
            return True, f"{strategy_name} stopped"
            
        except Exception as e:
            logger.error(f"[STRATEGY RUNNER] Error stopping strategy: {e}")
            return False, f"Error stopping strategy: {str(e)}"
    
    def get_status(self) -> Dict:
        """
        Get current strategy status.
        
        Returns:
            Dict with status information:
                - running: bool
                - strategy: str or None
                - details: Dict with strategy-specific details
        """
        if not self.active_strategy:
            return {
                'running': False,
                'strategy': None,
                'details': {}
            }
        
        # Get strategy-specific status
        try:
            strategy_status = self.active_strategy.get_status()
        except Exception as e:
            logger.error(f"[STRATEGY RUNNER] Error getting strategy status: {e}")
            strategy_status = {'error': str(e)}
        
        return {
            'running': self.running,
            'strategy': self.strategy_name,
            'details': strategy_status
        }
    
    def is_running(self) -> bool:
        """Check if a strategy is currently running"""
        return self.running and self.active_strategy is not None
    
    def get_active_strategy(self):
        """Get the active strategy instance (for connecting signals, etc.)"""
        return self.active_strategy

