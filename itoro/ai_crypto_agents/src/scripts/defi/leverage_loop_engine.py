"""
🌙 Anarcho Capital's Leverage Loop Engine
Multi-iteration leverage strategy for DeFi yield optimization
Built with love by Anarcho Capital 🚀
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical
from src.scripts.defi.defi_safety_validator import get_defi_safety_validator, SafetyCheckResult
from src.scripts.defi.defi_position_manager import get_defi_position_manager, DeFiPosition, DeFiLoop as DBDeFiLoop
from src.config.defi_config import LEVERAGE_LOOP_CONFIG, LEVERAGE_AI_CONFIG
from src import config

@dataclass
class LeveragePosition:
    """Represents a single leverage position"""
    position_id: str
    iteration: int
    collateral_token: str
    collateral_amount_usd: float
    borrowed_amount_usd: float
    lending_protocol: str
    borrowing_protocol: str
    timestamp: datetime
    liquidation_threshold: float
    current_collateral_ratio: float
    protocol_used: str = "solend"  # Cross-protocol tracking (default for backward compatibility)
    
@dataclass
class LeverageLoop:
    """Represents a complete leverage loop strategy"""
    loop_id: str
    initial_capital_usd: float
    iterations: int
    max_iterations: int
    current_leverage_ratio: float
    total_exposure_usd: float
    total_interest_cost_apy: float
    positions: List[LeveragePosition]
    status: str  # "active", "completed", "unwinding", "liquidated"
    created_at: datetime
    health_score: float  # 0.0 to 1.0

class LeverageLoopEngine:
    """
    Executes multi-iteration leverage loops for yield optimization
    Uses SOL, stSOL, or USDC as collateral to borrow USDC and lend for yield
    """
    
    def __init__(self):
        """Initialize the leverage loop engine"""
        self.safety_validator = get_defi_safety_validator()
        self.position_manager = get_defi_position_manager()
        self.active_loops: Dict[str, LeverageLoop] = {}
        self.loop_history: List[LeverageLoop] = []
        
        # Load configuration
        self.config = LEVERAGE_LOOP_CONFIG
        self.ai_config = LEVERAGE_AI_CONFIG
        
        # Recursive leverage settings
        self.recursive_enabled = self.config.get('recursive_leverage_enabled', True)
        self.swap_enabled = self.config.get('swap_to_collateral_enabled', True)
        self.stake_after_swap = self.config.get('stake_after_swap', False)
        
        # Load active positions from database (restore after restart)
        self._load_active_positions_from_db()
        
        info("🔄 Leverage Loop Engine initialized")
    
    def _load_active_positions_from_db(self):
        """Load active positions from database to restore state after restart"""
        try:
            active_db_loops = self.position_manager.get_active_loops()
            
            if not active_db_loops:
                debug("No active DeFi positions found in database")
                return
            
            info(f"\033[36m🔄 Restoring {len(active_db_loops)} active DeFi loops from database\033[0m")
            
            for db_loop in active_db_loops:
                # Get positions for this loop
                db_positions = [pos for pos in self.position_manager.get_active_positions() 
                               if pos.loop_id == db_loop.loop_id]
                
                # Convert DB positions to LeveragePosition objects
                positions = []
                for db_pos in db_positions:
                    position = LeveragePosition(
                        position_id=db_pos.position_id,
                        iteration=db_pos.iteration,
                        collateral_token=db_pos.collateral_token,
                        collateral_amount_usd=db_pos.collateral_amount_usd,
                        borrowed_amount_usd=db_pos.borrowed_amount_usd,
                        lending_protocol=db_pos.lending_protocol,
                        borrowing_protocol=db_pos.borrowing_protocol,
                        timestamp=datetime.fromisoformat(db_pos.created_at),
                        liquidation_threshold=db_pos.liquidation_threshold,
                        current_collateral_ratio=db_pos.current_collateral_ratio,
                        protocol_used=db_pos.borrowing_protocol
                    )
                    positions.append(position)
                
                # Create LeverageLoop object
                loop = LeverageLoop(
                    loop_id=db_loop.loop_id,
                    initial_capital_usd=db_loop.initial_capital_usd,
                    iterations=len(positions),
                    max_iterations=len(positions),
                    current_leverage_ratio=db_loop.leverage_ratio,
                    total_exposure_usd=db_loop.total_exposure_usd,
                    total_interest_cost_apy=0.0,
                    positions=positions,
                    status=db_loop.status,
                    created_at=datetime.fromisoformat(db_loop.created_at),
                    health_score=positions[-1].health_score if positions else 1.0
                )
                
                self.active_loops[loop.loop_id] = loop
                info(f"\033[36m✅ Restored loop {loop.loop_id}: {loop.iterations} positions, {loop.current_leverage_ratio:.2f}x leverage\033[0m")
            
        except Exception as e:
            warning(f"Failed to load active positions from database: {str(e)}")
    
    def calculate_safe_leverage(self, available_capital: Dict[str, float],
                                 market_sentiment: str = "neutral") -> Tuple[float, int]:
        """
        Calculate safe leverage ratio based on available capital and market conditions
        
        Args:
            available_capital: Dict of available capital by token (SOL, stSOL, USDC)
            market_sentiment: Current market sentiment (bullish, neutral, bearish)
            
        Returns:
            Tuple of (max_safe_leverage_ratio, recommended_iterations)
        """
        try:
            # Base leverage from config
            max_leverage = self.config['max_leverage_ratio']
            max_iterations = self.config['max_loop_iterations']
            
            # Apply AI-driven sentiment multiplier
            if self.ai_config['enabled']:
                if market_sentiment == "bullish":
                    leverage_multiplier = self.ai_config['bullish_leverage_multiplier']
                elif market_sentiment == "bearish":
                    leverage_multiplier = self.ai_config['bearish_leverage_multiplier']
                else:
                    leverage_multiplier = self.ai_config['neutral_leverage_multiplier']
                
                max_leverage *= leverage_multiplier
                max_iterations = int(max_iterations * leverage_multiplier)
            
            # Calculate total available capital
            total_capital = sum(available_capital.values())
            
            # Safety: Never exceed 3x leverage
            safe_leverage = min(max_leverage, 3.0)
            safe_iterations = min(max_iterations, 3)

            # Dynamic thresholds based on portfolio percentage
            conservative_threshold = total_capital * 0.001  # 0.1% of portfolio
            moderate_threshold = total_capital * 0.005      # 0.5% of portfolio

            if total_capital < conservative_threshold:
                safe_iterations = 1  # Very conservative for tiny positions
            elif total_capital < moderate_threshold:
                safe_iterations = 2  # Moderate for medium positions
            else:
                safe_iterations = min(safe_iterations, 3)  # Full leverage for large positions
            
            info(f"\033[36m💰 Safe leverage calculated: {safe_leverage:.2f}x with {safe_iterations} iterations\033[0m")
            return safe_leverage, safe_iterations
            
        except Exception as e:
            error(f"Error calculating safe leverage: {str(e)}")
            return 1.5, 1  # Ultra conservative fallback
    
    def _swap_usdc_to_collateral(self, usdc_amount_usd: float, collateral_token: str) -> Optional[float]:
        """
        Swap USDC to collateral token (SOL or stSOL) for recursive leverage
        
        Args:
            usdc_amount_usd: Amount of USDC to swap in USD
            collateral_token: Target collateral token ('SOL' or 'stSOL')
            
        Returns:
            Amount of collateral received in USD (None if swap failed)
        """
        try:
            if not self.swap_enabled:
                warning("Swap to collateral disabled - skipping swap")
                return None
            
            from src import config
            from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
            
            if collateral_token not in ['SOL', 'stSOL']:
                error(f"Unsupported collateral token for swap: {collateral_token}")
                return None
            
            # Get SOL price for conversion
            price_service = get_optimized_price_service()
            sol_price = price_service.get_price(config.SOL_ADDRESS)
            
            if not sol_price or sol_price <= 0:
                error("Cannot get SOL price for swap")
                return None
            
            if config.PAPER_TRADING_ENABLED:
                # Paper mode: simulate swap (account for slippage)
                slippage_factor = 0.995  # 0.5% slippage simulation
                sol_amount = (usdc_amount_usd / sol_price) * slippage_factor
                sol_value_usd = sol_amount * sol_price
                
                info(f"\033[36m📝 PAPER: Swap ${usdc_amount_usd:.2f} USDC → {sol_amount:.4f} SOL (${sol_value_usd:.2f})\033[0m")
                
                # If stSOL needed, simulate staking (1:1 ratio)
                if collateral_token == 'stSOL':
                    info(f"📝 PAPER: Stake {sol_amount:.4f} SOL → {sol_amount:.4f} stSOL")
                    return sol_value_usd
                else:
                    return sol_value_usd
            else:
                # Live mode: execute actual swap
                from src import nice_funcs
                
                # Convert USDC amount to lamports (USDC has 6 decimals)
                usdc_lamports = int(usdc_amount_usd * 1_000_000)  # 1 USDC = 1,000,000 lamports
                
                if usdc_lamports <= 0:
                    error(f"Invalid USDC amount for swap: {usdc_amount_usd}")
                    return None
                
                # Swap USDC to SOL using market_buy
                info(f"💱 LIVE: Swapping ${usdc_amount_usd:.2f} USDC to SOL")
                tx_signature = nice_funcs.market_buy(
                    token=config.SOL_ADDRESS,
                    amount=usdc_lamports,
                    slippage=config.DEFI_SLIPPAGE_TOLERANCE,
                    allow_excluded=True  # Allow excluded tokens for DeFi operations
                )
                
                if not tx_signature:
                    error(f"❌ Failed to swap USDC to SOL")
                    return None
                
                # Calculate SOL received (accounting for slippage)
                sol_amount = usdc_amount_usd / sol_price
                slippage_factor = 0.995  # Estimate 0.5% slippage
                sol_amount *= slippage_factor
                sol_value_usd = sol_amount * sol_price
                
                info(f"✅ LIVE: Swapped ${usdc_amount_usd:.2f} USDC → {sol_amount:.4f} SOL (${sol_value_usd:.2f})")
                
                # If stSOL needed, stake the SOL
                if collateral_token == 'stSOL' and self.stake_after_swap:
                    # TODO: Implement staking SOL to stSOL here
                    # For now, assume SOL can be used as collateral (stSOL is just staked SOL)
                    warning("⚠️ stSOL staking not yet implemented - using SOL as collateral")
                    return sol_value_usd
                elif collateral_token == 'stSOL':
                    # Return SOL value (stSOL is essentially SOL, just staked)
                    return sol_value_usd
                else:
                    return sol_value_usd
                    
        except Exception as e:
            error(f"Error swapping USDC to {collateral_token}: {str(e)}")
            return None
    
    async def execute_leverage_loop(self, initial_capital_usd: float,
                                     collateral_token: str,
                                     market_sentiment: str = "neutral",
                                     target_iterations: int = 3,
                                     borrowing_protocol: Optional[str] = None,
                                     lending_protocol: Optional[str] = None) -> Optional[LeverageLoop]:
        """
        Execute a multi-iteration leverage loop
        
        Args:
            initial_capital_usd: Starting capital in USD
            collateral_token: Token to use as collateral (SOL, stSOL, USDC)
            market_sentiment: Current market sentiment
            target_iterations: Target number of iterations
            
        Returns:
            LeverageLoop object if successful, None otherwise
        """
        try:
            # Safety check before starting
            safety_result = self._pre_loop_safety_check(initial_capital_usd)
            if not safety_result.is_safe:
                error(f"🚫 Leverage loop blocked: {safety_result.reason}")
                return None
            
            # Calculate safe leverage
            leverage_ratio, iterations = self.calculate_safe_leverage(
                {collateral_token: initial_capital_usd},
                market_sentiment
            )
            
            # Limit iterations to target
            iterations = min(iterations, target_iterations)
            
            # Create loop record
            loop_id = f"loop_{int(time.time())}"
            loop = LeverageLoop(
                loop_id=loop_id,
                initial_capital_usd=initial_capital_usd,
                iterations=0,
                max_iterations=iterations,
                current_leverage_ratio=1.0,
                total_exposure_usd=initial_capital_usd,
                total_interest_cost_apy=0.0,
                positions=[],
                status="active",
                created_at=datetime.now(),
                health_score=1.0
            )
            
            # Persist loop to database
            db_loop = DBDeFiLoop(
                loop_id=loop_id,
                initial_capital_usd=initial_capital_usd,
                total_exposure_usd=initial_capital_usd,
                leverage_ratio=1.0,
                status="active",
                created_at=loop.created_at.isoformat(),
                closed_at=None
            )
            self.position_manager.save_loop(db_loop)
            
            info(f"\033[36m🚀 Starting leverage loop {loop_id}: ${initial_capital_usd:.2f} with {iterations} iterations\033[0m")
            
            # Recursive leverage tracking
            total_collateral_usd = initial_capital_usd  # Cumulative collateral across iterations
            cumulative_debt_usd = 0.0  # Total borrowed USDC
            borrowed_amounts = []  # Track all borrowed amounts for final lending
            
            # Determine protocols (use provided or default to Solend)
            borrowing_protocol = borrowing_protocol or "solend"  # Use provided or default to Solend
            lending_protocol = lending_protocol or "solend"     # Use provided or default to Solend
            
            # Execute borrowing iterations (recursive leverage)
            for i in range(iterations):
                try:
                    info(f"\033[36m📊 Loop iteration {i+1}/{iterations}\033[0m")
                    
                    # Calculate maximum borrowing power from current total collateral (75% LTV)
                    max_borrowing_power = total_collateral_usd * 0.75
                    
                    # For recursive strategy: subtract what's already borrowed
                    available_borrow_capacity = max_borrowing_power - cumulative_debt_usd
                    
                    if available_borrow_capacity <= 0:
                        warning(f"⚠️ Max borrowing capacity reached at iteration {i+1}")
                        break
                    
                    # For recursive leverage: use all available capacity each iteration to maximize leverage
                    # This compounds leverage faster than distributing evenly
                    borrow_amount = available_borrow_capacity
                    
                    # Safety check: don't borrow more than 75% of current collateral
                    if borrow_amount > max_borrowing_power:
                        borrow_amount = max_borrowing_power
                        warning(f"⚠️ Capped borrow amount to ${borrow_amount:.2f} (75% of collateral)")
                    
                    info(f"\033[36m💰 Borrowing ${borrow_amount:.2f} USDC (collateral: ${total_collateral_usd:.2f}, debt: ${cumulative_debt_usd:.2f})\033[0m")
                    
                    # Execute borrow based on mode
                    if config.PAPER_TRADING_ENABLED:
                        # Paper mode: simulate borrowing
                        from src.scripts.shared_services.logger import info as log_info
                        log_info(f"\033[36m📝 PAPER: Borrow ${borrow_amount:.2f} USDC on {borrowing_protocol}\033[0m")
                        borrow_success = True
                    else:
                        # Live mode: execute actual borrowing
                        from src import nice_funcs
                        borrow_success = nice_funcs.defi_borrow_usdc(
                            amount_usd=borrow_amount,
                            collateral_token=collateral_token,
                            protocol=borrowing_protocol,
                            slippage=200
                        )
                    
                    if not borrow_success:
                        error(f"❌ Borrow failed in iteration {i+1}")
                        break
                    
                    # Update cumulative debt
                    cumulative_debt_usd += borrow_amount
                    borrowed_amounts.append(borrow_amount)
                    
                    # RECURSIVE LEVERAGE: Swap borrowed USDC back to collateral
                    if self.recursive_enabled and self.swap_enabled:
                        swapped_collateral_usd = self._swap_usdc_to_collateral(borrow_amount, collateral_token)
                        
                        if swapped_collateral_usd and swapped_collateral_usd > 0:
                            # Add swapped collateral to total collateral pool
                            total_collateral_usd += swapped_collateral_usd
                            info(f"\033[36m📈 Total collateral increased to ${total_collateral_usd:.2f} (added ${swapped_collateral_usd:.2f})\033[0m")
                        else:
                            warning(f"⚠️ Swap failed in iteration {i+1}, stopping recursive leverage")
                            break
                    else:
                        # Non-recursive: just track debt (no swap)
                        pass
                    
                    # Create position record for this iteration
                    current_collateral_ratio = total_collateral_usd / cumulative_debt_usd if cumulative_debt_usd > 0 else 2.0
                    
                    position = LeveragePosition(
                        position_id=f"{loop_id}_iter_{i+1}",
                        iteration=i+1,
                        collateral_token=collateral_token,
                        collateral_amount_usd=total_collateral_usd,  # Total cumulative collateral
                        borrowed_amount_usd=borrow_amount,  # Incremental borrow this iteration
                        lending_protocol=lending_protocol,
                        borrowing_protocol=borrowing_protocol,
                        timestamp=datetime.now(),
                        liquidation_threshold=1.5,  # 150% collateral ratio required
                        current_collateral_ratio=current_collateral_ratio,  # Actual ratio based on totals
                        protocol_used=borrowing_protocol  # Track which protocol was used
                    )
                    
                    loop.positions.append(position)
                    loop.iterations += 1
                    
                    # Persist position to database
                    db_position = DeFiPosition(
                        position_id=position.position_id,
                        loop_id=loop_id,
                        iteration=position.iteration,
                        collateral_token=position.collateral_token,
                        collateral_amount_usd=position.collateral_amount_usd,
                        borrowed_amount_usd=position.borrowed_amount_usd,
                        lending_protocol=position.lending_protocol,
                        borrowing_protocol=position.borrowing_protocol,
                        status="active",
                        created_at=position.timestamp.isoformat(),
                        updated_at=position.timestamp.isoformat(),
                        liquidation_threshold=position.liquidation_threshold,
                        current_collateral_ratio=position.current_collateral_ratio,
                        health_score=1.0
                    )
                    self.position_manager.save_position(db_position)
                    
                    # Record borrow transaction to paper_trades
                    self.position_manager.record_defi_transaction_to_paper_trades(
                        action="BORROW",
                        token_address=config.USDC_ADDRESS,
                        amount=borrow_amount,
                        amount_usd=borrow_amount,
                        protocol=borrowing_protocol,
                        agent="defi"
                    )
                    
                    # Update reserved balances
                    from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
                    price_svc = get_optimized_price_service()
                    token_address = config.STAKED_SOL_TOKEN_ADDRESS if collateral_token == 'stSOL' else config.SOL_ADDRESS
                    token_price = price_svc.get_price(token_address) or 1.0
                    
                    self.position_manager.update_reserved_balance(
                        token_address=token_address,
                        amount=total_collateral_usd / token_price,
                        amount_usd=total_collateral_usd,
                        reason="defi_collateral",
                        position_ids=[pos.position_id for pos in loop.positions]
                    )
                    
                    # Update leverage ratio
                    loop.current_leverage_ratio = cumulative_debt_usd / loop.initial_capital_usd if loop.initial_capital_usd > 0 else 1.0
                    loop.total_exposure_usd = cumulative_debt_usd
                    
                    # Update loop in database
                    db_loop.total_exposure_usd = cumulative_debt_usd
                    db_loop.leverage_ratio = loop.current_leverage_ratio
                    self.position_manager.save_loop(db_loop)
                    
                    info(f"\033[36m✅ Iteration {i+1} complete: Collateral ${total_collateral_usd:.2f}, Debt ${cumulative_debt_usd:.2f}, Ratio {current_collateral_ratio:.2f}x\033[0m")
                    
                except Exception as e:
                    error(f"Error in loop iteration {i+1}: {str(e)}")
                    break
            
            # FINAL STEP: Lend all borrowed USDC after all iterations complete
            if cumulative_debt_usd > 0 and loop.iterations > 0:
                total_to_lend = cumulative_debt_usd
                
                info(f"\033[36m💰 Final step: Lending ${total_to_lend:.2f} USDC (sum of all borrows)\033[0m")
                
                if config.PAPER_TRADING_ENABLED:
                    # Paper mode: simulate lending
                    from src.scripts.shared_services.logger import info as log_info
                    log_info(f"\033[36m📝 PAPER: Lend ${total_to_lend:.2f} USDC on {lending_protocol}\033[0m")
                    lend_success = True
                else:
                    # Live mode: execute actual lending
                    from src import nice_funcs
                    lend_success = nice_funcs.defi_lend_usdc(
                        amount_usd=total_to_lend,
                        protocol=lending_protocol,
                        slippage=200
                    )
                
                if not lend_success:
                    warning(f"⚠️ Final lending step failed")
                else:
                    info(f"✅ All borrowed USDC (${total_to_lend:.2f}) lent successfully")
                    
                    # Record lend transaction to paper_trades
                    self.position_manager.record_defi_transaction_to_paper_trades(
                        action="LEND",
                        token_address=config.USDC_ADDRESS,
                        amount=total_to_lend,
                        amount_usd=total_to_lend,
                        protocol=lending_protocol,
                        agent="defi"
                    )
                    
                    # Update final leverage calculation
                    loop.current_leverage_ratio = cumulative_debt_usd / loop.initial_capital_usd
                    info(f"\033[36m🎯 Final leverage: {loop.current_leverage_ratio:.2f}x (${cumulative_debt_usd:.2f} debt / ${loop.initial_capital_usd:.2f} initial)\033[0m")
            
            # Update status
            if loop.iterations == loop.max_iterations:
                loop.status = "completed"
            else:
                loop.status = "partial"
            
            # Update loop status in database
            self.position_manager.update_loop_status(loop_id, loop.status)
            
            # Add to active loops
            self.active_loops[loop_id] = loop
            
            info(f"✅ Leverage loop {loop_id} completed: {loop.iterations}/{iterations} iterations, {loop.current_leverage_ratio:.2f}x leverage")
            return loop
            
        except Exception as e:
            error(f"Error executing leverage loop: {str(e)}")
            return None
    
    def monitor_loop_health(self, loop: LeverageLoop) -> float:
        """
        Monitor health of a leverage loop
        
        Returns:
            Health score (0.0 to 1.0), where 1.0 is healthy and 0.0 is liquidation risk
        """
        try:
            if not loop.positions:
                return 1.0
            
            # For recursive leverage, use the latest position's collateral ratio (which reflects total state)
            # Or calculate from total exposure
            if loop.positions:
                # Get the most recent position (last iteration has cumulative totals)
                latest_position = loop.positions[-1]
                current_collateral_ratio = latest_position.current_collateral_ratio
            else:
                # Fallback: calculate from average
                current_collateral_ratio = sum(pos.current_collateral_ratio for pos in loop.positions) / len(loop.positions)
            
            # Health score based on distance from liquidation
            # 2.0 = healthy, 1.5 = liquidation threshold
            if current_collateral_ratio >= 2.0:
                health_score = 1.0
            elif current_collateral_ratio >= 1.5:
                # Linear interpolation between 1.5 and 2.0
                health_score = (current_collateral_ratio - 1.5) / 0.5
            else:
                health_score = 0.0  # Liquidation risk
            
            loop.health_score = health_score
            
            return health_score
            
        except Exception as e:
            error(f"Error monitoring loop health: {str(e)}")
            return 0.5  # Assume medium risk on error
    
    def unwind_loop(self, loop: LeverageLoop, emergency: bool = False) -> bool:
        """
        Unwind a leverage loop position by layer
        
        For recursive leverage: Withdraw single large lent position, then repay incremental borrows
        
        Args:
            loop: Loop to unwind
            emergency: If True, aggressive unwinding
            
        Returns:
            True if successful
        """
        try:
            info(f"🔄 Unwinding leverage loop {loop.loop_id} (emergency={emergency})")
            
            if not loop.positions:
                warning("No positions to unwind")
                return True
            
            # Calculate total borrowed amount (for recursive leverage with single lend)
            total_borrowed = sum(pos.borrowed_amount_usd for pos in loop.positions)
            lending_protocol = loop.positions[0].lending_protocol if loop.positions else "solend"
            
            # Step 1: Withdraw the single large lent position (for recursive leverage)
            if config.PAPER_TRADING_ENABLED:
                info(f"📝 PAPER: Withdraw lent ${total_borrowed:.2f} USDC from {lending_protocol}")
                withdraw_success = True
            else:
                from src import nice_funcs
                info(f"💰 LIVE: Withdrawing lent ${total_borrowed:.2f} USDC from {lending_protocol}")
                withdraw_success = nice_funcs.defi_withdraw_usdc(
                    amount_usd=total_borrowed,
                    protocol=lending_protocol,
                    slippage=200
                )
            
            if not withdraw_success:
                error(f"❌ Failed to withdraw lent USDC from {lending_protocol}")
                return False
            
            # Record withdraw transaction to paper_trades
            self.position_manager.record_defi_transaction_to_paper_trades(
                action="WITHDRAW",
                token_address=config.USDC_ADDRESS,
                amount=total_borrowed,
                amount_usd=total_borrowed,
                protocol=lending_protocol,
                agent="defi"
            )
            
            # Step 2: Repay borrows in reverse order (LIFO) - unwind incremental borrows
            for position in reversed(loop.positions):
                try:
                    info(f"Closing position {position.position_id} (repay ${position.borrowed_amount_usd:.2f})")
                    
                    if config.PAPER_TRADING_ENABLED:
                        info(f"📝 PAPER: Repay borrow ${position.borrowed_amount_usd:.2f} on {position.borrowing_protocol}")
                        repay_success = True
                    else:
                        # Live mode: repay the borrowed USDC
                        from src import nice_funcs
                        info(f"💰 LIVE: Repaying borrowed ${position.borrowed_amount_usd:.2f} on {position.borrowing_protocol}")
                        repay_success = nice_funcs.defi_repay_usdc(
                            amount_usd=position.borrowed_amount_usd,
                            collateral_token=position.collateral_token,
                            protocol=position.borrowing_protocol,
                            slippage=200
                        )
                    
                    if not repay_success:
                        error(f"❌ Failed to repay position {position.position_id}")
                        # Continue with other positions even if one fails
                    else:
                        # Record repay transaction to paper_trades
                        self.position_manager.record_defi_transaction_to_paper_trades(
                            action="REPAY",
                            token_address=config.USDC_ADDRESS,
                            amount=position.borrowed_amount_usd,
                            amount_usd=position.borrowed_amount_usd,
                            protocol=position.borrowing_protocol,
                            agent="defi"
                        )
                        
                        # Update position status in database
                        self.position_manager.update_position_status(position.position_id, "closed")
                    
                except Exception as e:
                    error(f"Error closing position {position.position_id}: {str(e)}")
            
            loop.status = "unwinding" if not emergency else "emergency"
            
            # Update loop status in database
            self.position_manager.update_loop_status(loop.loop_id, loop.status)
            
            # Clear reserved balances for this loop's collateral
            for position in loop.positions:
                token_address = config.STAKED_SOL_TOKEN_ADDRESS if position.collateral_token == 'stSOL' else config.SOL_ADDRESS
                self.position_manager.clear_reserved_balance(token_address)
            
            # Move to history
            if loop.loop_id in self.active_loops:
                del self.active_loops[loop.loop_id]
            
            self.loop_history.append(loop)
            
            info(f"✅ Leverage loop {loop.loop_id} unwound successfully")
            return True
            
        except Exception as e:
            error(f"Error unwinding loop: {str(e)}")
            return False
    
    def emergency_unwind_all_loops(self) -> int:
        """
        Emergency unwind all active leverage positions
        
        Returns:
            Number of loops unwound
        """
        try:
            info("🚨 EMERGENCY: Unwinding all leverage loops")
            
            unwound_count = 0
            for loop_id, loop in list(self.active_loops.items()):
                if self.unwind_loop(loop, emergency=True):
                    unwound_count += 1
            
            return unwound_count
            
        except Exception as e:
            error(f"Error in emergency unwind: {str(e)}")
            return 0
    
    def _pre_loop_safety_check(self, amount_usd: float) -> SafetyCheckResult:
        """Check safety before starting a leverage loop"""
        try:
            # Import portfolio snapshot
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            tracker = get_portfolio_tracker()
            snapshot = tracker.current_snapshot
            
            if not snapshot:
                return SafetyCheckResult(
                    is_safe=False,
                    reason="No portfolio snapshot",
                    risk_level="danger"
                )
            
            # Use safety validator
            return self.safety_validator.can_execute_defi_operation(amount_usd, "leverage_loop", snapshot)
            
        except Exception as e:
            error(f"Error in pre-loop safety check: {str(e)}")
            return SafetyCheckResult(
                is_safe=False,
                reason=f"Safety check error: {str(e)}",
                risk_level="danger"
            )
    
    def get_active_loops_summary(self) -> Dict[str, Any]:
        """Get summary of all active leverage loops"""
        try:
            total_exposure = sum(loop.total_exposure_usd for loop in self.active_loops.values())
            total_positions = sum(len(loop.positions) for loop in self.active_loops.values())
            
            return {
                'active_loops': len(self.active_loops),
                'total_exposure_usd': total_exposure,
                'total_positions': total_positions,
                'average_leverage': sum(loop.current_leverage_ratio for loop in self.active_loops.values()) / len(self.active_loops) if self.active_loops else 0,
                'loops': [
                    {
                        'loop_id': loop.loop_id,
                        'iterations': loop.iterations,
                        'leverage_ratio': loop.current_leverage_ratio,
                        'exposure': loop.total_exposure_usd,
                        'health': loop.health_score,
                        'status': loop.status
                    }
                    for loop in self.active_loops.values()
                ]
            }
            
        except Exception as e:
            error(f"Error getting active loops summary: {str(e)}")
            return {"error": str(e)}

# Global instance
_leverage_engine = None

def get_leverage_loop_engine() -> LeverageLoopEngine:
    """Get the global leverage loop engine instance"""
    global _leverage_engine
    if _leverage_engine is None:
        _leverage_engine = LeverageLoopEngine()
    return _leverage_engine

