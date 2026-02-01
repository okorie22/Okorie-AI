"""
🌙 Anarcho Capital's Cashflow Agent
Handles deposits and withdrawals between Solana wallet and Hyperliquid account
Monitors balances and triggers transfers when thresholds are met
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Local imports
from src.agents.base_agent import BaseAgent
from src.scripts.shared_services.logger import debug, info, warning, error
from src.config import (
    CASHFLOW_AGENT_ENABLED,
    HYPERLIQUID_MIN_BALANCE_USD,
    HYPERLIQUID_MAX_BALANCE_USD,
    HYPERLIQUID_DEPOSIT_THRESHOLD_USD
)

# Try to import Hyperliquid services
try:
    from src.scripts.trading.hyperliquid_account_manager import get_hyperliquid_account_manager
    HYPERLIQUID_AVAILABLE = True
except ImportError:
    HYPERLIQUID_AVAILABLE = False
    warning("Hyperliquid account manager not available - cashflow agent in limited mode")

# Try to import Solana wallet balance services
try:
    from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
    SOLANA_WALLET_AVAILABLE = True
except ImportError:
    SOLANA_WALLET_AVAILABLE = False
    warning("Solana wallet services not available - cashflow agent in limited mode")


class CashflowAgent(BaseAgent):
    """
    Cashflow Agent for managing transfers between Solana wallet and Hyperliquid account
    
    Monitors:
    - Hyperliquid account balance
    - Solana wallet balance
    - Triggers deposits when Hyperliquid balance is low
    - Triggers withdrawals when Hyperliquid balance is high
    
    Note: For MVP, agent monitors and alerts. Full automation requires
    Hyperliquid deposit/withdrawal API integration.
    """
    
    def __init__(self):
        """Initialize the Cashflow Agent"""
        super().__init__("cashflow")
        
        # Configuration
        self.enabled = CASHFLOW_AGENT_ENABLED
        self.min_hyperliquid_balance = HYPERLIQUID_MIN_BALANCE_USD
        self.max_hyperliquid_balance = HYPERLIQUID_MAX_BALANCE_USD
        self.deposit_threshold = HYPERLIQUID_DEPOSIT_THRESHOLD_USD
        
        # Monitoring state
        self.is_running = False
        self.thread = None
        self.check_interval_seconds = 300  # Check every 5 minutes
        
        # Balance tracking
        self.last_hyperliquid_balance = 0.0
        self.last_solana_balance = 0.0
        self.last_check_time = None
        
        # Transfer history
        self.transfer_history = []
        
        # Initialize services
        self.hyperliquid_manager = None
        self.solana_coordinator = None
        
        if HYPERLIQUID_AVAILABLE:
            try:
                self.hyperliquid_manager = get_hyperliquid_account_manager()
            except Exception as e:
                warning(f"Could not initialize Hyperliquid manager: {e}")
        
        if SOLANA_WALLET_AVAILABLE:
            try:
                self.solana_coordinator = get_shared_data_coordinator()
            except Exception as e:
                warning(f"Could not initialize Solana coordinator: {e}")
        
        info("💰 Cashflow Agent initialized")
        if not self.enabled:
            info("⚠️ Cashflow Agent is disabled in config")
    
    def get_hyperliquid_balance(self) -> float:
        """Get current Hyperliquid account balance"""
        if not self.hyperliquid_manager:
            return 0.0
        
        try:
            balance = self.hyperliquid_manager.get_total_equity()
            return balance if balance else 0.0
        except Exception as e:
            error(f"Error getting Hyperliquid balance: {e}")
            return 0.0
    
    def get_solana_balance_usd(self) -> float:
        """Get current Solana wallet balance in USD"""
        if not self.solana_coordinator:
            return 0.0
        
        try:
            balance = self.solana_coordinator.get_personal_wallet_balance()
            return balance if balance else 0.0
        except Exception as e:
            error(f"Error getting Solana balance: {e}")
            return 0.0
    
    def monitor_balance(self):
        """Monitor balances and trigger transfers if needed"""
        try:
            if not self.enabled:
                return
            
            # Get current balances
            hl_balance = self.get_hyperliquid_balance()
            sol_balance = self.get_solana_balance_usd()
            
            self.last_hyperliquid_balance = hl_balance
            self.last_solana_balance = sol_balance
            self.last_check_time = datetime.now()
            
            debug(f"💰 Balance check - Hyperliquid: ${hl_balance:.2f}, Solana: ${sol_balance:.2f}")
            
            # Check if deposit is needed
            if hl_balance < self.deposit_threshold:
                amount_needed = self.min_hyperliquid_balance - hl_balance
                info(f"⚠️ Hyperliquid balance low (${hl_balance:.2f} < ${self.deposit_threshold:.2f})")
                info(f"💡 Recommended deposit: ${amount_needed:.2f} to reach minimum ${self.min_hyperliquid_balance:.2f}")
                
                # Check if Solana wallet has enough
                if sol_balance >= amount_needed:
                    info(f"✅ Solana wallet has sufficient balance (${sol_balance:.2f})")
                    info(f"📝 Manual deposit required: Send ${amount_needed:.2f} from Solana wallet to Hyperliquid")
                    # TODO: Implement automated deposit when API available
                else:
                    warning(f"⚠️ Solana wallet balance insufficient: ${sol_balance:.2f} < ${amount_needed:.2f}")
            
            # Check if withdrawal is needed
            elif hl_balance > self.max_hyperliquid_balance:
                excess = hl_balance - self.max_hyperliquid_balance
                info(f"⚠️ Hyperliquid balance high (${hl_balance:.2f} > ${self.max_hyperliquid_balance:.2f})")
                info(f"💡 Recommended withdrawal: ${excess:.2f} to bring balance to ${self.max_hyperliquid_balance:.2f}")
                info(f"📝 Manual withdrawal required: Withdraw ${excess:.2f} from Hyperliquid to Solana wallet")
                # TODO: Implement automated withdrawal when API available
            
            else:
                debug(f"✅ Balances within acceptable range (${self.deposit_threshold:.2f} - ${self.max_hyperliquid_balance:.2f})")
                
        except Exception as e:
            error(f"Error in balance monitoring: {e}")
            import traceback
            error(traceback.format_exc())
    
    def deposit_to_hyperliquid(self, amount_sol: float) -> Dict[str, Any]:
        """
        Deposit SOL from Solana wallet to Hyperliquid account
        
        Note: For MVP, this is a placeholder. Full implementation requires:
        - Hyperliquid deposit API integration, or
        - Bridge service integration (deBridge)
        
        Args:
            amount_sol: Amount of SOL to deposit
        
        Returns:
            Dict with success status and transaction details
        """
        try:
            info(f"💰 Initiating deposit: {amount_sol} SOL to Hyperliquid")
            
            # TODO: Implement actual deposit logic
            # This would use Hyperliquid deposit API or bridge service
            
            # For now, return instructions
            return {
                'success': False,
                'method': 'manual',
                'instructions': [
                    '1. Go to Hyperliquid.xyz',
                    '2. Connect wallet (Ethereum address matching HYPERLIQUID_WALLET_ADDRESS)',
                    '3. Navigate to Deposit',
                    '4. Select SOL',
                    f'5. Send {amount_sol} SOL from Solana wallet',
                    '6. Wait ~1 minute for confirmation'
                ],
                'note': 'Automated deposits require Hyperliquid deposit API integration'
            }
            
        except Exception as e:
            error(f"Error initiating deposit: {e}")
            return {'success': False, 'error': str(e)}
    
    def withdraw_from_hyperliquid(self, amount_usd: float) -> Dict[str, Any]:
        """
        Withdraw from Hyperliquid to Solana wallet
        
        Note: For MVP, this is a placeholder. Full implementation requires:
        - Hyperliquid withdrawal API integration
        
        Args:
            amount_usd: Amount in USD to withdraw
        
        Returns:
            Dict with success status and transaction details
        """
        try:
            info(f"💰 Initiating withdrawal: ${amount_usd:.2f} from Hyperliquid")
            
            # TODO: Implement actual withdrawal logic
            # This would use Hyperliquid withdrawal API
            
            # For now, return instructions
            return {
                'success': False,
                'method': 'manual',
                'instructions': [
                    '1. Go to Hyperliquid.xyz',
                    '2. Connect wallet',
                    '3. Navigate to Withdraw',
                    f'4. Withdraw ${amount_usd:.2f} USDC (or equivalent in SOL)',
                    '5. Bridge back to Solana if needed',
                    '6. Wait for confirmation'
                ],
                'note': 'Automated withdrawals require Hyperliquid withdrawal API integration'
            }
            
        except Exception as e:
            error(f"Error initiating withdrawal: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_balance_summary(self) -> Dict[str, Any]:
        """Get current balance summary"""
        hl_balance = self.get_hyperliquid_balance()
        sol_balance = self.get_solana_balance_usd()
        
        return {
            'hyperliquid_balance_usd': hl_balance,
            'solana_balance_usd': sol_balance,
            'total_balance_usd': hl_balance + sol_balance,
            'hyperliquid_status': 'low' if hl_balance < self.deposit_threshold else 'high' if hl_balance > self.max_hyperliquid_balance else 'normal',
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'thresholds': {
                'min_hyperliquid': self.min_hyperliquid_balance,
                'max_hyperliquid': self.max_hyperliquid_balance,
                'deposit_threshold': self.deposit_threshold
            }
        }
    
    def start(self):
        """Start the cashflow monitoring agent"""
        try:
            if not self.enabled:
                info("Cashflow Agent is disabled - not starting")
                return
            
            if self.is_running:
                warning("Cashflow Agent is already running")
                return
            
            self.is_running = True
            
            # Start monitoring thread
            self.thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.thread.start()
            
            info("💰 Cashflow Agent started - monitoring balances every 5 minutes")
            
        except Exception as e:
            error(f"Error starting cashflow agent: {e}")
            self.is_running = False
    
    def stop(self):
        """Stop the cashflow agent"""
        try:
            self.is_running = False
            
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            
            info("💰 Cashflow Agent stopped")
            
        except Exception as e:
            error(f"Error stopping cashflow agent: {e}")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                self.monitor_balance()
                time.sleep(self.check_interval_seconds)
            except Exception as e:
                error(f"Error in cashflow monitoring loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def run(self):
        """Run method for scheduler compatibility"""
        self.start()
        # Keep running
        while self.is_running:
            time.sleep(60)


# Global singleton instance
_cashflow_agent = None

def get_cashflow_agent() -> Optional[CashflowAgent]:
    """Get singleton instance of cashflow agent"""
    global _cashflow_agent
    if _cashflow_agent is None:
        try:
            _cashflow_agent = CashflowAgent()
        except Exception as e:
            error(f"Failed to create cashflow agent: {e}")
            return None
    return _cashflow_agent
