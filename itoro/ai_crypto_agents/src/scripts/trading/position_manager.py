"""
🌙 Anarcho Capital's Position Manager
Unified position sizing and management system for all agents
Built with love by Anarcho Capital 🚀
"""

import threading
import time
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import os
# Local imports with fallback for relative imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src import config
except ImportError:
    # Try relative imports when running from test directory
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    import src.config as config

class PositionAction(Enum):
    """Types of position actions"""
    BUY = "BUY"
    SELL = "SELL"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    CLOSE = "CLOSE"

@dataclass
class PositionRequest:
    """Request for position sizing calculation"""
    agent_id: str
    token_address: str
    action: PositionAction
    requested_amount_usd: Optional[float] = None
    current_position_usd: Optional[float] = None
    account_balance_usd: Optional[float] = None
    confidence_level: Optional[float] = None
    change_percentage: Optional[float] = None  # For position modifications
    reason: str = ""

@dataclass
class PositionResponse:
    """Response with approved position size and limits"""
    approved: bool
    approved_amount_usd: float
    original_request_usd: float
    limit_reason: Optional[str] = None
    position_id: Optional[str] = None
    max_position_size_usd: float = 0.0
    current_total_allocation_pct: float = 0.0
    recommendations: List[str] = None

@dataclass
class ActivePosition:
    """Tracks an active position across all agents"""
    token_address: str
    current_size_usd: float
    agent_id: str
    entry_time: datetime
    last_updated: datetime
    position_id: str
    entry_price: Optional[float] = None
    current_price: Optional[float] = None

class PositionManager:
    """
    Unified position manager that ensures consistent sizing across all agents
    Prevents oversized positions and coordinates between agents
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
        """Initialize the position manager"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Position tracking
        self.active_positions: Dict[str, ActivePosition] = {}
        self.position_lock = threading.RLock()
        
        # Account tracking
        self.account_balance_cache = None
        self.balance_cache_time = None
        self.balance_cache_expiry = 30  # seconds
        
        # Position limits and sizing
        self.max_position_count = config.MAX_CONCURRENT_POSITIONS
        self.max_total_allocation = config.MAX_TOTAL_ALLOCATION_PERCENT
        self.max_single_position = config.MAX_SINGLE_POSITION_PERCENT
        self.dust_threshold = config.DUST_THRESHOLD_USD
        
        # Dynamic sizing settings
        self.use_dynamic_sizing = config.USE_DYNAMIC_POSITION_SIZING
        self.new_position_base_pct = config.NEW_POSITION_BASE_PERCENT
        self.new_position_small_account_pct = config.NEW_POSITION_SMALL_ACCOUNT_PERCENT
        self.small_account_threshold = config.SMALL_ACCOUNT_THRESHOLD
        self.max_position_increase_pct = config.MAX_POSITION_INCREASE_PERCENT
        
        # Safety limits
        self.base_position_size = config.usd_size
        self.max_order_size = config.max_usd_order_size
        
        info("Position Manager initialized with unified sizing controls")
    
    def request_position_sizing(self, request: PositionRequest) -> PositionResponse:
        """
        Main entry point for all position sizing requests
        Ensures consistency and safety across all agents
        """
        try:
            with self.position_lock:
                # Get current account balance
                account_balance = self._get_account_balance()
                if request.account_balance_usd:
                    account_balance = request.account_balance_usd
                
                # Calculate appropriate position size
                if request.action == PositionAction.BUY:
                    return self._handle_new_position(request, account_balance)
                elif request.action in [PositionAction.INCREASE, PositionAction.DECREASE]:
                    return self._handle_position_modification(request, account_balance)
                elif request.action in [PositionAction.SELL, PositionAction.CLOSE]:
                    return self._handle_position_close(request, account_balance)
                else:
                    return PositionResponse(
                        approved=False,
                        approved_amount_usd=0.0,
                        original_request_usd=request.requested_amount_usd or 0.0,
                        limit_reason=f"Unsupported action: {request.action}"
                    )
        
        except Exception as e:
            error(f"Error in position sizing request: {str(e)}")
            return PositionResponse(
                approved=False,
                approved_amount_usd=0.0,
                original_request_usd=request.requested_amount_usd or 0.0,
                limit_reason=f"Error: {str(e)}"
            )
    
    def _handle_new_position(self, request: PositionRequest, account_balance: float) -> PositionResponse:
        """Handle new position requests"""
        
        # Check if we can open new positions
        current_position_count = len(self.active_positions)
        if current_position_count >= self.max_position_count:
            return PositionResponse(
                approved=False,
                approved_amount_usd=0.0,
                original_request_usd=request.requested_amount_usd or 0.0,
                limit_reason=f"Maximum positions reached ({current_position_count}/{self.max_position_count})"
            )
        
        # Check if token already has a position
        if request.token_address in self.active_positions:
            existing_position = self.active_positions[request.token_address]
            warning(f"Position already exists for {request.token_address}, converting to INCREASE action")
            
            # Convert to increase request
            modified_request = PositionRequest(
                agent_id=request.agent_id,
                token_address=request.token_address,
                action=PositionAction.INCREASE,
                requested_amount_usd=request.requested_amount_usd,
                current_position_usd=existing_position.current_size_usd,
                account_balance_usd=account_balance,
                confidence_level=request.confidence_level,
                reason=request.reason
            )
            return self._handle_position_modification(modified_request, account_balance)
        
        # Calculate appropriate size for new position
        if self.use_dynamic_sizing:
            if account_balance < self.small_account_threshold:
                base_pct = self.new_position_small_account_pct
                info(f"Small account detected (${account_balance:.2f}), using {base_pct*100:.1f}% allocation")
            else:
                base_pct = self.new_position_base_pct
            
            calculated_size = account_balance * base_pct
            # Cap at configured maximum
            calculated_size = min(calculated_size, self.base_position_size)
        else:
            calculated_size = self.base_position_size
        
        # Use requested amount if provided and reasonable
        if request.requested_amount_usd:
            requested_size = request.requested_amount_usd
            # Don't allow requests much larger than calculated size
            if requested_size > calculated_size * 2:
                warning(f"Requested size (${requested_size:.2f}) much larger than calculated (${calculated_size:.2f})")
                calculated_size = min(requested_size, calculated_size * 1.5)
            else:
                calculated_size = requested_size
        
        # Apply safety limits
        safety_result = self._apply_safety_limits(calculated_size, account_balance, None)
        if not safety_result[0]:
            return PositionResponse(
                approved=False,
                approved_amount_usd=0.0,
                original_request_usd=request.requested_amount_usd or calculated_size,
                limit_reason=safety_result[1]
            )
        
        approved_size = safety_result[2]
        
        # Ensure minimum viable position
        approved_size = max(approved_size, 0.25)
        
        # Create position tracking
        position_id = f"{request.agent_id}_{request.token_address}_{int(time.time())}"
        
        return PositionResponse(
            approved=True,
            approved_amount_usd=approved_size,
            original_request_usd=request.requested_amount_usd or calculated_size,
            position_id=position_id,
            max_position_size_usd=account_balance * self.max_single_position,
            current_total_allocation_pct=self._get_current_allocation_percentage(account_balance),
            recommendations=[
                f"Position size calculated using {'dynamic' if self.use_dynamic_sizing else 'fixed'} sizing",
                f"Account balance: ${account_balance:.2f}",
                f"Max single position: ${account_balance * self.max_single_position:.2f}"
            ]
        )
    
    def _handle_position_modification(self, request: PositionRequest, account_balance: float) -> PositionResponse:
        """Handle position increase/decrease requests"""
        
        current_position_size = request.current_position_usd or 0.0
        
        if request.action == PositionAction.INCREASE:
            # Calculate maximum allowed increase
            max_increase = account_balance * self.max_position_increase_pct
            
            # Use requested amount if provided
            if request.requested_amount_usd:
                requested_increase = request.requested_amount_usd
            else:
                # Default increase based on change percentage if provided
                if request.change_percentage:
                    requested_increase = current_position_size * (abs(request.change_percentage) / 100.0)
                else:
                    requested_increase = max_increase * 0.5  # Default to 50% of max allowed
            
            # Apply limits
            approved_increase = min(requested_increase, max_increase)
            
            # Check total position size after increase
            new_total_size = current_position_size + approved_increase
            max_single_position_size = account_balance * self.max_single_position
            
            if new_total_size > max_single_position_size:
                approved_increase = max(0, max_single_position_size - current_position_size)
                if approved_increase < self.dust_threshold:
                    return PositionResponse(
                        approved=False,
                        approved_amount_usd=0.0,
                        original_request_usd=requested_increase,
                        limit_reason=f"Position increase would exceed single position limit"
                    )
            
            # Apply safety limits
            safety_result = self._apply_safety_limits(approved_increase, account_balance, current_position_size)
            if not safety_result[0]:
                return PositionResponse(
                    approved=False,
                    approved_amount_usd=0.0,
                    original_request_usd=requested_increase,
                    limit_reason=safety_result[1]
                )
            
            return PositionResponse(
                approved=True,
                approved_amount_usd=safety_result[2],
                original_request_usd=requested_increase,
                current_total_allocation_pct=self._get_current_allocation_percentage(account_balance),
                recommendations=[
                    f"Position increase approved",
                    f"New position size will be: ${new_total_size:.2f}",
                    f"Remaining increase capacity: ${max_single_position_size - new_total_size:.2f}"
                ]
            )
        
        elif request.action == PositionAction.DECREASE:
            # For decreases, allow up to 100% of current position
            max_decrease = current_position_size
            
            if request.requested_amount_usd:
                requested_decrease = min(request.requested_amount_usd, max_decrease)
            elif request.change_percentage:
                requested_decrease = current_position_size * (abs(request.change_percentage) / 100.0)
            else:
                requested_decrease = max_decrease * 0.5  # Default to 50% reduction
            
            approved_decrease = min(requested_decrease, max_decrease)
            
            return PositionResponse(
                approved=True,
                approved_amount_usd=approved_decrease,
                original_request_usd=requested_decrease,
                current_total_allocation_pct=self._get_current_allocation_percentage(account_balance),
                recommendations=[
                    f"Position decrease approved",
                    f"Remaining position size will be: ${current_position_size - approved_decrease:.2f}"
                ]
            )
    
    def _handle_position_close(self, request: PositionRequest, account_balance: float) -> PositionResponse:
        """Handle position close requests"""
        
        # For closes, approve the full current position or requested amount
        current_position_size = request.current_position_usd or 0.0
        
        if request.requested_amount_usd and request.requested_amount_usd < current_position_size:
            # Partial close
            approved_amount = request.requested_amount_usd
        else:
            # Full close
            approved_amount = current_position_size
        
        return PositionResponse(
            approved=True,
            approved_amount_usd=approved_amount,
            original_request_usd=request.requested_amount_usd or current_position_size,
            current_total_allocation_pct=self._get_current_allocation_percentage(account_balance),
            recommendations=[
                f"Position close approved",
                f"Closing ${approved_amount:.2f} of ${current_position_size:.2f}"
            ]
        )
    
    def _apply_safety_limits(self, requested_size: float, account_balance: float, 
                           current_position_size: Optional[float] = None) -> Tuple[bool, str, float]:
        """Apply safety limits to position sizing"""
        
        if requested_size <= 0:
            return False, "Position size must be positive", 0.0
        
        if requested_size < self.dust_threshold:
            return False, f"Position size below dust threshold (${self.dust_threshold})", 0.0
        
        # Check single position limit
        max_single_position = account_balance * self.max_single_position
        if current_position_size:
            available_for_position = max_single_position - current_position_size
            if requested_size > available_for_position:
                if available_for_position < self.dust_threshold:
                    return False, "Single position limit reached", 0.0
                else:
                    return True, "Size reduced to fit single position limit", available_for_position
        elif requested_size > max_single_position:
            return True, "Size reduced to single position limit", max_single_position
        
        # Check total allocation limit
        current_allocation = self._get_current_total_allocation(account_balance)
        max_total_allocation_usd = account_balance * self.max_total_allocation
        available_allocation = max_total_allocation_usd - current_allocation
        
        if requested_size > available_allocation:
            if available_allocation < self.dust_threshold:
                return False, "Total allocation limit reached", 0.0
            else:
                return True, "Size reduced to fit total allocation limit", available_allocation
        
        # Check against configured maximums
        if requested_size > self.base_position_size * 2:
            return True, "Size reduced to 2x base position size", self.base_position_size * 2
        
        return True, "Approved", requested_size
    
    def register_position(self, token_address: str, size_usd: float, agent_id: str, 
                         entry_price: Optional[float] = None) -> str:
        """BULLETPROOF: Register a new position with automatic cleanup"""
        with self.position_lock:
            # MEMORY LEAK FIX: Clean up old positions before adding new ones
            self._cleanup_old_positions()
            
            position_id = f"{agent_id}_{token_address}_{int(time.time())}"
            
            # SAFETY CHECK: Validate parameters
            if not token_address or size_usd <= 0:
                error(f"❌ Invalid position parameters: token={token_address}, size=${size_usd}")
                return ""
            
            # MEMORY LEAK FIX: Check for existing position and handle appropriately
            if token_address in self.active_positions:
                existing_pos = self.active_positions[token_address]
                warning(f"⚠️ Updating existing position for {token_address[:8]}...")
                warning(f"   Old: ${existing_pos.current_size_usd:.2f} ({existing_pos.agent_id})")
                warning(f"   New: ${size_usd:.2f} ({agent_id})")
            
            self.active_positions[token_address] = ActivePosition(
                token_address=token_address,
                current_size_usd=size_usd,
                agent_id=agent_id,
                entry_time=datetime.now(),
                last_updated=datetime.now(),
                position_id=position_id,
                entry_price=entry_price
            )
            
            info(f"✅ Registered position: {token_address[:8]}... ${size_usd:.2f} for {agent_id}")
            info(f"📊 Total active positions: {len(self.active_positions)}")
            
            return position_id
    
    def _cleanup_old_positions(self):
        """MEMORY LEAK FIX: Clean up old/stale positions - ALL SCENARIOS"""
        try:
            current_time = datetime.now()
            positions_to_remove = []
            
            # SCENARIO 1: Check for corrupted/invalid positions
            for token_address, position in list(self.active_positions.items()):
                try:
                    # Validate position data integrity
                    if not hasattr(position, 'current_size_usd') or not hasattr(position, 'last_updated'):
                        positions_to_remove.append((token_address, "corrupted data"))
                        continue
                        
                    # CLEANUP CRITERIA
                    age_hours = (current_time - position.last_updated).total_seconds() / 3600
                    
                    # Remove positions that are:
                    # 1. Very old (7+ days without update) 
                    # 2. Very small (dust positions)
                    # 3. Have zero or negative size
                    # 4. Have invalid data
                    should_remove = False
                    removal_reason = ""
                    
                    if age_hours > 168:  # 7 days
                        should_remove = True
                        removal_reason = f"aged {age_hours:.1f} hours"
                    elif position.current_size_usd <= 0:
                        should_remove = True
                        removal_reason = "zero/negative size"
                    elif position.current_size_usd < self.dust_threshold:
                        should_remove = True
                        removal_reason = f"dust (${position.current_size_usd:.4f})"
                    elif not isinstance(position.current_size_usd, (int, float)):
                        should_remove = True
                        removal_reason = "invalid size data"
                    elif age_hours > 24 and position.current_size_usd < 1.0:  # Old small positions
                        should_remove = True
                        removal_reason = f"old small position (${position.current_size_usd:.2f})"
                    
                    if should_remove:
                        positions_to_remove.append((token_address, removal_reason))
                        
                except Exception as pos_error:
                    # SCENARIO 2: Handle corrupted position objects
                    positions_to_remove.append((token_address, f"position error: {str(pos_error)}"))
            
            # SCENARIO 3: Check for memory overflow (too many positions)
            if len(self.active_positions) > 50:  # Reasonable limit for swing trading
                # Sort by size and remove smallest positions
                sorted_positions = sorted(
                    self.active_positions.items(),
                    key=lambda x: x[1].current_size_usd if hasattr(x[1], 'current_size_usd') else 0
                )
                
                # Remove smallest positions to get back to 30 max
                excess_positions = sorted_positions[:len(self.active_positions) - 30]
                for token_address, position in excess_positions:
                    positions_to_remove.append((token_address, "memory overflow protection"))
            
            # SCENARIO 4: Remove duplicates (same token, multiple entries)
            seen_tokens = set()
            for token_address in list(self.active_positions.keys()):
                if token_address in seen_tokens:
                    positions_to_remove.append((token_address, "duplicate entry"))
                seen_tokens.add(token_address)
            
            # ATOMIC REMOVAL: Remove all identified positions
            removed_count = 0
            for token_address, reason in positions_to_remove:
                try:
                    if token_address in self.active_positions:
                        del self.active_positions[token_address]
                        removed_count += 1
                        debug(f"🧹 Cleaned up position {token_address[:8]}... ({reason})")
                except KeyError:
                    # Already removed, skip
                    pass
            
            if removed_count > 0:
                info(f"🧹 Memory cleanup: removed {removed_count} positions, {len(self.active_positions)} remaining")
            
            # SCENARIO 5: Final memory health check
            if len(self.active_positions) > 100:
                warning(f"⚠️ High position count: {len(self.active_positions)} positions tracked")
                
        except Exception as e:
            error(f"❌ Critical error in position cleanup: {str(e)}")
            # Emergency cleanup on error
            try:
                if len(self.active_positions) > 200:
                    warning("🚨 Emergency position cleanup due to error")
                    # Keep only the 20 most recent positions
                    recent_positions = dict(sorted(
                        self.active_positions.items(),
                        key=lambda x: x[1].last_updated if hasattr(x[1], 'last_updated') else datetime.min,
                        reverse=True
                    )[:20])
                    self.active_positions = recent_positions
                    warning(f"🚨 Emergency cleanup complete: {len(self.active_positions)} positions remaining")
            except:
                # Last resort - clear all positions if corrupted
                error("🚨 CRITICAL: Clearing all positions due to corruption")
                self.active_positions = {}
    
    def remove_position(self, token_address: str) -> bool:
        """MEMORY LEAK FIX: Explicitly remove a position"""
        with self.position_lock:
            if token_address in self.active_positions:
                position = self.active_positions[token_address]
                del self.active_positions[token_address]
                info(f"🗑️ Removed position: {token_address[:8]}... (${position.current_size_usd:.2f})")
                info(f"📊 Remaining active positions: {len(self.active_positions)}")
                return True
            else:
                warning(f"⚠️ Attempted to remove non-existent position: {token_address[:8]}...")
                return False
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """MEMORY LEAK FIX: Get memory usage statistics"""
        with self.position_lock:
            current_time = datetime.now()
            position_ages = []
            total_value = 0.0
            dust_count = 0
            
            for position in self.active_positions.values():
                age_hours = (current_time - position.last_updated).total_seconds() / 3600
                position_ages.append(age_hours)
                total_value += position.current_size_usd
                
                if position.current_size_usd < self.dust_threshold:
                    dust_count += 1
            
            return {
                'total_positions': len(self.active_positions),
                'total_value_usd': total_value,
                'dust_positions': dust_count,
                'avg_age_hours': sum(position_ages) / len(position_ages) if position_ages else 0,
                'oldest_position_hours': max(position_ages) if position_ages else 0,
                'memory_usage_estimate_mb': len(self.active_positions) * 0.001  # Rough estimate
            }
    
    def update_position(self, token_address: str, new_size_usd: float, 
                       current_price: Optional[float] = None):
        """Update an existing position"""
        with self.position_lock:
            if token_address in self.active_positions:
                position = self.active_positions[token_address]
                position.current_size_usd = new_size_usd
                position.last_updated = datetime.now()
                if current_price:
                    position.current_price = current_price
                
                debug(f"Updated position: {token_address[:8]}... to ${new_size_usd:.2f}")
            else:
                warning(f"Attempted to update non-existent position: {token_address[:8]}...")
    
    def remove_position(self, token_address: str):
        """Remove a position (after closing)"""
        with self.position_lock:
            if token_address in self.active_positions:
                position = self.active_positions.pop(token_address)
                info(f"Removed position: {token_address[:8]}... was ${position.current_size_usd:.2f}")
            else:
                warning(f"Attempted to remove non-existent position: {token_address[:8]}...")
    
    def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of all positions"""
        with self.position_lock:
            total_positions = len(self.active_positions)
            total_allocation_usd = sum(pos.current_size_usd for pos in self.active_positions.values())
            account_balance = self._get_account_balance()
            
            return {
                'total_positions': total_positions,
                'max_positions': self.max_position_count,
                'total_allocation_usd': total_allocation_usd,
                'total_allocation_pct': total_allocation_usd / account_balance if account_balance > 0 else 0,
                'max_allocation_pct': self.max_total_allocation,
                'available_allocation_usd': (account_balance * self.max_total_allocation) - total_allocation_usd,
                'account_balance': account_balance,
                'positions': {addr: {'size_usd': pos.current_size_usd, 'agent': pos.agent_id} 
                            for addr, pos in self.active_positions.items()}
            }
    
    def _get_account_balance(self) -> float:
        """Get current account balance with caching"""
        current_time = time.time()
        
        if (self.account_balance_cache is not None and 
            self.balance_cache_time is not None and 
            current_time - self.balance_cache_time < self.balance_cache_expiry):
            return self.account_balance_cache
        
        try:
            # Try to get balance from shared services or nice_funcs
            from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
            
            coordinator = get_shared_data_coordinator()
            balance = coordinator.get_personal_wallet_balance()
            
            if balance is not None:
                self.account_balance_cache = balance
                self.balance_cache_time = current_time
                return balance
            
        except Exception as e:
            debug(f"Error getting account balance from coordinator: {str(e)}", file_only=True)
        
        # Fallback to default
        warning("Could not get account balance, using fallback value")
        return 1000.0  # Fallback balance
    
    def _get_current_allocation_percentage(self, account_balance: float) -> float:
        """Get current total allocation as percentage of account balance"""
        total_allocation = self._get_current_total_allocation(account_balance)
        return total_allocation / account_balance if account_balance > 0 else 0.0
    
    def _get_current_total_allocation(self, account_balance: float) -> float:
        """Get current total allocation in USD"""
        with self.position_lock:
            return sum(pos.current_size_usd for pos in self.active_positions.values())

# Global instance
_position_manager = None

def get_position_manager() -> PositionManager:
    """Get the global position manager instance"""
    global _position_manager
    if _position_manager is None:
        _position_manager = PositionManager()
    return _position_manager 