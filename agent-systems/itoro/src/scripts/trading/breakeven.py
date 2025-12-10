"""
🌙 Anarcho Capital's Breakeven Management System
Adapted from freqtrade for spot trading bots
Built with love by Anarcho Capital 🚀
"""

import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pandas as pd

# Local imports with fallback for relative imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src import config
except ImportError:
    # Try relative imports when running from test directory
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    import src.config as config

@dataclass
class BreakevenPosition:
    """Data class for tracking breakeven positions"""
    token_address: str
    entry_price: float
    current_price: float
    amount: float
    entry_time: datetime
    last_check: datetime
    status: str  # 'profitable', 'loss', 'breakeven'
    profit_percent: float
    usd_value: float
    target_exit_price: float
    timeout_minutes: int = 60

class BreakevenManager:
    """
    Breakeven management system for spot trading bots
    Closes profitable positions and holds loss positions until breakeven
    """
    
    def __init__(self):
        """Initialize the breakeven manager"""
        self.positions: Dict[str, BreakevenPosition] = {}
        self.breakeven_history: List[Dict] = []
        self.last_breakeven_check = datetime.now()
        
        # Configuration
        self.min_profit_percent = config.BREAKEVEN_MIN_PROFIT_PERCENT
        self.max_loss_percent = config.BREAKEVEN_MAX_LOSS_PERCENT
        self.timeout_minutes = config.BREAKEVEN_TIMEOUT_MINUTES
        self.partial_close_percent = config.BREAKEVEN_PARTIAL_CLOSE_PERCENT
        
        # Performance tracking
        self.total_positions_processed = 0
        self.profitable_closes = 0
        self.breakeven_closes = 0
        self.forced_closes = 0
        
        info("🔄 Breakeven Manager initialized")
    
    def add_position(self, token_address: str, entry_price: float, amount: float, 
                    current_price: float = None, entry_time: datetime = None) -> bool:
        """Add a new position to breakeven tracking"""
        try:
            if entry_time is None:
                entry_time = datetime.now()
            
            if current_price is None:
                current_price = entry_price
            
            usd_value = amount * current_price
            profit_percent = ((current_price - entry_price) / entry_price) * 100
            
            # Determine initial status
            if profit_percent >= self.min_profit_percent:
                status = 'profitable'
            elif profit_percent <= self.max_loss_percent:
                status = 'forced_close'
            else:
                status = 'loss'
            
            position = BreakevenPosition(
                token_address=token_address,
                entry_price=entry_price,
                current_price=current_price,
                amount=amount,
                entry_time=entry_time,
                last_check=datetime.now(),
                status=status,
                profit_percent=profit_percent,
                usd_value=usd_value,
                target_exit_price=entry_price,  # Breakeven target
                timeout_minutes=self.timeout_minutes
            )
            
            self.positions[token_address] = position
            self.total_positions_processed += 1
            
            info(f"📊 Added position to breakeven tracking: {token_address[:8]}... (${usd_value:.2f}, {profit_percent:.2f}%)")
            return True
            
        except Exception as e:
            error(f"Error adding position to breakeven tracking: {str(e)}")
            return False
    
    def update_position_price(self, token_address: str, current_price: float) -> bool:
        """Update position with current price and recalculate metrics"""
        try:
            if token_address not in self.positions:
                return False
            
            position = self.positions[token_address]
            position.current_price = current_price
            position.last_check = datetime.now()
            position.usd_value = position.amount * current_price
            position.profit_percent = ((current_price - position.entry_price) / position.entry_price) * 100
            
            # Update status based on new price
            if position.profit_percent >= self.min_profit_percent:
                position.status = 'profitable'
            elif position.profit_percent <= self.max_loss_percent:
                position.status = 'forced_close'
            elif position.profit_percent >= 0:
                position.status = 'breakeven'
            else:
                position.status = 'loss'
            
            return True
            
        except Exception as e:
            error(f"Error updating position price: {str(e)}")
            return False
    
    def check_breakeven_conditions(self) -> Dict[str, List[str]]:
        """Check all positions for breakeven conditions"""
        try:
            actions = {
                'close_profitable': [],
                'close_breakeven': [],
                'close_forced': [],
                'hold_loss': [],
                'partial_close': []
            }
            
            current_time = datetime.now()
            
            for token_address, position in self.positions.items():
                # Check timeout for loss positions
                time_held = (current_time - position.entry_time).total_seconds() / 60
                
                if position.status == 'profitable':
                    # Close profitable positions
                    actions['close_profitable'].append(token_address)
                    
                elif position.status == 'breakeven':
                    # Close positions that reached breakeven
                    actions['close_breakeven'].append(token_address)
                    
                elif position.status == 'forced_close':
                    # Force close positions that exceeded max loss
                    actions['close_forced'].append(token_address)
                    
                elif position.status == 'loss':
                    if time_held >= position.timeout_minutes:
                        # Force close after timeout
                        actions['close_forced'].append(token_address)
                    else:
                        # Hold until breakeven or timeout
                        actions['hold_loss'].append(token_address)
                
                # Check for partial close opportunities
                if position.profit_percent >= self.min_profit_percent * 0.5:  # Half of minimum profit
                    actions['partial_close'].append(token_address)
            
            return actions
            
        except Exception as e:
            error(f"Error checking breakeven conditions: {str(e)}")
            return {'close_profitable': [], 'close_breakeven': [], 'close_forced': [], 'hold_loss': [], 'partial_close': []}
    
    def execute_breakeven_strategy(self, price_service) -> Dict[str, int]:
        """Execute the breakeven strategy and return results"""
        try:
            results = {
                'profitable_closed': 0,
                'breakeven_closed': 0,
                'forced_closed': 0,
                'partial_closed': 0,
                'held': 0
            }
            
            # Update all position prices
            for token_address in list(self.positions.keys()):
                try:
                    current_price = price_service.get_price(token_address)
                    if current_price and isinstance(current_price, (int, float)) and current_price > 0:
                        self.update_position_price(token_address, current_price)
                except Exception as e:
                    debug(f"Could not update price for {token_address}: {str(e)}")
            
            # Check breakeven conditions
            actions = self.check_breakeven_conditions()
            
            # Execute actions
            for token_address in actions['close_profitable']:
                if self._close_position(token_address, 'profitable'):
                    results['profitable_closed'] += 1
                    self.profitable_closes += 1
            
            for token_address in actions['close_breakeven']:
                if self._close_position(token_address, 'breakeven'):
                    results['breakeven_closed'] += 1
                    self.breakeven_closes += 1
            
            for token_address in actions['close_forced']:
                if self._close_position(token_address, 'forced'):
                    results['forced_closed'] += 1
                    self.forced_closes += 1
            
            for token_address in actions['partial_close']:
                if self._partial_close_position(token_address):
                    results['partial_closed'] += 1
            
            results['held'] = len(actions['hold_loss'])
            
            # Log results
            if any(results.values()):
                info(f"🔄 Breakeven strategy executed:")
                info(f"  • Profitable closed: {results['profitable_closed']}")
                info(f"  • Breakeven closed: {results['breakeven_closed']}")
                info(f"  • Forced closed: {results['forced_closed']}")
                info(f"  • Partial closed: {results['partial_closed']}")
                info(f"  • Positions held: {results['held']}")
            
            return results
            
        except Exception as e:
            error(f"Error executing breakeven strategy: {str(e)}")
            return {'profitable_closed': 0, 'breakeven_closed': 0, 'forced_closed': 0, 'partial_closed': 0, 'held': 0}
    
    def _close_position(self, token_address: str, reason: str) -> bool:
        """Close a position and record the action"""
        try:
            if token_address not in self.positions:
                return False
            
            position = self.positions[token_address]
            
            # Record the close action
            close_record = {
                'token_address': token_address,
                'close_time': datetime.now().isoformat(),
                'reason': reason,
                'entry_price': position.entry_price,
                'exit_price': position.current_price,
                'profit_percent': position.profit_percent,
                'usd_value': position.usd_value,
                'time_held_minutes': (datetime.now() - position.entry_time).total_seconds() / 60
            }
            
            self.breakeven_history.append(close_record)
            
            # Remove from active positions
            del self.positions[token_address]
            
            info(f"✅ Closed position {token_address[:8]}... ({reason}): {position.profit_percent:.2f}%")
            return True
            
        except Exception as e:
            error(f"Error closing position: {str(e)}")
            return False
    
    def _partial_close_position(self, token_address: str) -> bool:
        """Partially close a position"""
        try:
            if token_address not in self.positions:
                return False
            
            position = self.positions[token_address]
            
            # Calculate partial close amount
            partial_amount = position.amount * self.partial_close_percent
            remaining_amount = position.amount - partial_amount
            
            if remaining_amount <= 0:
                # If remaining amount is too small, close entirely
                return self._close_position(token_address, 'partial')
            
            # Update position with remaining amount
            position.amount = remaining_amount
            position.usd_value = remaining_amount * position.current_price
            
            info(f"📊 Partial close {token_address[:8]}...: {self.partial_close_percent*100:.0f}% ({position.profit_percent:.2f}%)")
            return True
            
        except Exception as e:
            error(f"Error partial closing position: {str(e)}")
            return False
    
    def get_breakeven_summary(self) -> Dict[str, Any]:
        """Get summary of breakeven performance"""
        try:
            total_positions = len(self.positions)
            profitable_positions = len([p for p in self.positions.values() if p.status == 'profitable'])
            loss_positions = len([p for p in self.positions.values() if p.status == 'loss'])
            breakeven_positions = len([p for p in self.positions.values() if p.status == 'breakeven'])
            
            total_value = sum(p.usd_value for p in self.positions.values())
            total_profit = sum(p.usd_value * (p.profit_percent / 100) for p in self.positions.values())
            
            return {
                'active_positions': total_positions,
                'profitable_positions': profitable_positions,
                'loss_positions': loss_positions,
                'breakeven_positions': breakeven_positions,
                'total_value': total_value,
                'total_profit': total_profit,
                'performance_stats': {
                    'total_processed': self.total_positions_processed,
                    'profitable_closes': self.profitable_closes,
                    'breakeven_closes': self.breakeven_closes,
                    'forced_closes': self.forced_closes
                },
                'last_check': self.last_breakeven_check.isoformat()
            }
            
        except Exception as e:
            error(f"Error getting breakeven summary: {str(e)}")
            return {}
    
    def save_breakeven_data(self, filepath: str = None) -> bool:
        """Save breakeven data to file"""
        try:
            if filepath is None:
                filepath = os.path.join('src', 'data', 'breakeven_data.json')
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            data = {
                'positions': {
                    addr: {
                        'token_address': pos.token_address,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'amount': pos.amount,
                        'entry_time': pos.entry_time.isoformat(),
                        'last_check': pos.last_check.isoformat(),
                        'status': pos.status,
                        'profit_percent': pos.profit_percent,
                        'usd_value': pos.usd_value,
                        'target_exit_price': pos.target_exit_price,
                        'timeout_minutes': pos.timeout_minutes
                    }
                    for addr, pos in self.positions.items()
                },
                'history': self.breakeven_history,
                'performance_stats': {
                    'total_processed': self.total_positions_processed,
                    'profitable_closes': self.profitable_closes,
                    'breakeven_closes': self.breakeven_closes,
                    'forced_closes': self.forced_closes
                },
                'last_save': datetime.now().isoformat()
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            debug(f"Breakeven data saved to {filepath}")
            return True
            
        except Exception as e:
            error(f"Error saving breakeven data: {str(e)}")
            return False
    
    def load_breakeven_data(self, filepath: str = None) -> bool:
        """Load breakeven data from file"""
        try:
            if filepath is None:
                filepath = os.path.join('src', 'data', 'breakeven_data.json')
            
            if not os.path.exists(filepath):
                debug("No breakeven data file found")
                return False
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Load positions
            self.positions.clear()
            for addr, pos_data in data.get('positions', {}).items():
                position = BreakevenPosition(
                    token_address=pos_data['token_address'],
                    entry_price=pos_data['entry_price'],
                    current_price=pos_data['current_price'],
                    amount=pos_data['amount'],
                    entry_time=datetime.fromisoformat(pos_data['entry_time']),
                    last_check=datetime.fromisoformat(pos_data['last_check']),
                    status=pos_data['status'],
                    profit_percent=pos_data['profit_percent'],
                    usd_value=pos_data['usd_value'],
                    target_exit_price=pos_data['target_exit_price'],
                    timeout_minutes=pos_data['timeout_minutes']
                )
                self.positions[addr] = position
            
            # Load history
            self.breakeven_history = data.get('history', [])
            
            # Load performance stats
            stats = data.get('performance_stats', {})
            self.total_positions_processed = stats.get('total_processed', 0)
            self.profitable_closes = stats.get('profitable_closes', 0)
            self.breakeven_closes = stats.get('breakeven_closes', 0)
            self.forced_closes = stats.get('forced_closes', 0)
            
            info(f"📊 Loaded {len(self.positions)} breakeven positions from {filepath}")
            return True
            
        except Exception as e:
            error(f"Error loading breakeven data: {str(e)}")
            return False

# Global breakeven manager instance
_breakeven_manager = None

def get_breakeven_manager() -> BreakevenManager:
    """Get the global breakeven manager instance"""
    global _breakeven_manager
    if _breakeven_manager is None:
        _breakeven_manager = BreakevenManager()
    return _breakeven_manager
