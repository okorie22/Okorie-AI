"""
🌙 Anarcho Capital's DeFi Automation Agent
AI-driven DeFi borrowing and lending automation with comprehensive risk management
Built with love by Anarcho Capital 🚀
"""

import threading
import time
import asyncio
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json

# Local imports with fallback for relative imports
try:
    from src.agents.base_agent import BaseAgent
    from src.scripts.defi.defi_protocol_manager import DeFiProtocolManager
    from src.scripts.defi.defi_risk_manager import DeFiRiskManager
    from src.scripts.defi.yield_optimizer import YieldOptimizer
    from src.scripts.utilities.telegram_bot import TelegramBot
    from src.scripts.defi.defi_event_manager import DeFiEventManager
    from src.scripts.defi.defi_integration_layer import get_defi_integration_layer, DeFiExecutionRequest
    from src.scripts.shared_services.logger import debug, info, warning, error, critical, system
    from src.scripts.defi.leverage_loop_engine import get_leverage_loop_engine
    from src.scripts.defi.defi_safety_validator import get_defi_safety_validator
    from src.scripts.defi.ai_defi_advisor import get_ai_defi_advisor
    from src.scripts.defi.staking_defi_coordinator import get_staking_defi_coordinator
    from src import config
except ImportError:
    # Try relative imports when running from test directory
    from src.agents.base_agent import BaseAgent
    from src.scripts.defi.defi_protocol_manager import DeFiProtocolManager
    from src.scripts.defi.defi_risk_manager import DeFiRiskManager
    from src.scripts.defi.yield_optimizer import YieldOptimizer
    from src.scripts.utilities.telegram_bot import TelegramBot
    from src.scripts.defi.defi_event_manager import DeFiEventManager
    from src.scripts.defi.defi_integration_layer import get_defi_integration_layer, DeFiExecutionRequest
    from src.scripts.shared_services.logger import debug, info, warning, error, critical, system
    from src.scripts.defi.leverage_loop_engine import get_leverage_loop_engine
    from src.scripts.defi.defi_safety_validator import get_defi_safety_validator
    from src.scripts.defi.ai_defi_advisor import get_ai_defi_advisor
    from src.scripts.defi.staking_defi_coordinator import get_staking_defi_coordinator
    import src.config as config

@dataclass
class DeFiOperation:
    """Represents a DeFi operation to be executed"""
    operation_id: str
    operation_type: str  # "lend", "borrow", "yield_farm", "arbitrage"
    protocol: str
    token_address: str
    amount_usd: float
    priority: str
    status: str  # "pending", "approved", "executing", "completed", "failed"
    created_at: datetime
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class DeFiAgent(BaseAgent):
    """
    Main DeFi automation agent that orchestrates all DeFi operations
    Integrates with existing shared services for portfolio management and execution
    """
    
    def __init__(self, enable_ai: bool = True):
        """Initialize the DeFi agent"""
        super().__init__('defi')
        
        # AI configuration
        self.enable_ai = enable_ai
        
        # Core DeFi components (use singleton instances to avoid duplicate initialization)
        from src.scripts.defi.defi_protocol_manager import get_defi_protocol_manager
        from src.scripts.defi.defi_risk_manager import get_defi_risk_manager
        from src.scripts.defi.yield_optimizer import get_yield_optimizer
        from src.scripts.utilities.telegram_bot import get_telegram_bot
        from src.scripts.defi.defi_event_manager import get_defi_event_manager
        
        self.protocol_manager = get_defi_protocol_manager()
        self.risk_manager = get_defi_risk_manager()
        self.yield_optimizer = get_yield_optimizer()
        self.telegram_bot = get_telegram_bot()
        self.event_manager = get_defi_event_manager()
        
        # Leverage and safety components
        self.leverage_engine = get_leverage_loop_engine()
        self.safety_validator = get_defi_safety_validator()
        self.coordinator = get_staking_defi_coordinator()
        
        # Cross-protocol routing components
        try:
            from src.scripts.defi.defi_protocol_router import get_defi_protocol_router
            from src.scripts.defi.defi_arbitrage_engine import get_defi_arbitrage_engine
            from src.scripts.shared_services.rate_monitoring_service import get_rate_monitoring_service
            self.protocol_router = get_defi_protocol_router()
            self.arbitrage_engine = get_defi_arbitrage_engine()
            self.rate_monitor = get_rate_monitoring_service()
            self.cross_protocol_enabled = True
            info("Cross-protocol routing components initialized")
        except Exception as e:
            warning(f"Failed to initialize cross-protocol components: {str(e)}")
            self.protocol_router = None
            self.arbitrage_engine = None
            self.rate_monitor = None
            self.cross_protocol_enabled = False
        
        # Last arbitrage scan timestamp
        self.last_arbitrage_scan = None
        self.arbitrage_scan_interval_hours = 6  # Scan every 6 hours
        
        if enable_ai:
            try:
                self.ai_advisor = get_ai_defi_advisor()
            except Exception as e:
                warning(f"AI advisor unavailable: {str(e)}")
                self.ai_advisor = None
        else:
            self.ai_advisor = None
        
        # Integration layer for shared services
        self.integration_layer = get_defi_integration_layer()
        
        # Register with coordinator
        self.coordinator.register_defi_agent(self)
        
        # Agent state
        self.running = False
        self.agent_thread = None
        self.current_phase = config.CURRENT_PHASE
        
        # Operation tracking
        self.pending_operations: List[DeFiOperation] = []
        self.completed_operations: List[DeFiOperation] = []
        self.failed_operations: List[DeFiOperation] = []
        self.operations_lock = threading.RLock()
        
        # Portfolio state tracking
        self.last_portfolio_check = 0
        self.portfolio_check_interval = 28800  # 8 hours (3 checks per day: 8am, 4pm, midnight)
        self.current_portfolio_state = None
        
        # Risk management state
        self.last_risk_assessment = 0
        self.risk_assessment_interval = 300  # 5 minutes
        self.current_risk_level = "LOW"
        
        # Yield optimization state
        self.last_yield_check = 0
        self.yield_check_interval = 600  # 10 minutes
        self.current_opportunities = []
        
        # Leverage loop monitoring state
        self.last_leverage_monitor = 0
        self.leverage_monitor_interval = config.DEFI_MONITORING_INTERVAL_SECONDS  # 60 seconds from config
        
        # Telegram bot integration (will be started separately in defi.py)
        self.telegram_enabled = config.TELEGRAM_BOT['enabled']
        
        # Telegram bot and event manager will be started separately in defi.py
        # during the engagement phase to avoid duplicate initialization messages
        
        info("DeFi Agent initialized successfully")
    
    def start(self):
        """Start the DeFi agent"""
        if self.running:
            warning("DeFi agent is already running")
            return True
        
        self.running = True
        self.agent_thread = threading.Thread(target=self._run_agent_loop, daemon=True)
        self.agent_thread.start()
        
        info("🚀 DeFi Agent started successfully")
        system(f"DeFi Agent Phase {self.current_phase} - {'AI Enabled' if self.enable_ai else 'Rules-Based Only'}")
        
        return True
    
    def stop(self):
        """Stop the DeFi agent"""
        if not self.running:
            warning("DeFi agent is not running")
            return
        
        self.running = False
        
        # Stop event manager
        self.event_manager.stop_event_processing()
        
        # Stop Telegram bot
        if self.telegram_enabled:
            self.telegram_bot.stop_bot()
        
        # Wait for agent thread to finish
        if self.agent_thread and self.agent_thread.is_alive():
            self.agent_thread.join(timeout=10)
        
        info("🛑 DeFi Agent stopped successfully")
    
    def _run_agent_loop(self):
        """Main agent loop"""
        info("🔄 DeFi Agent loop started")
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check portfolio state
                if current_time - self.last_portfolio_check >= self.portfolio_check_interval:
                    self._check_portfolio_state()
                    self.last_portfolio_check = current_time
                
                # Perform risk assessment
                if current_time - self.last_risk_assessment >= self.risk_assessment_interval:
                    self._perform_risk_assessment()
                    self.last_risk_assessment = current_time
                
                # Check yield opportunities
                if current_time - self.last_yield_check >= self.yield_check_interval:
                    self._check_yield_opportunities()
                    self.last_yield_check = current_time
                
                # Monitor active leverage loops (respects 60-second interval)
                if current_time - self.last_leverage_monitor >= self.leverage_monitor_interval:
                    self._monitor_active_leverage_loops()
                    self.last_leverage_monitor = current_time
                
                # Process pending operations
                self._process_pending_operations()
                
                # Sleep for a short interval
                time.sleep(10)
                
            except Exception as e:
                error(f"Error in DeFi agent loop: {str(e)}")
                time.sleep(30)  # Longer sleep on error
        
        info("🔄 DeFi Agent loop stopped")
    
    def _check_portfolio_state(self):
        """Check current portfolio state and update DeFi allocation"""
        try:
            # Get portfolio data from integration layer
            portfolio_data = self.integration_layer.get_defi_portfolio_data()
            self.current_portfolio_state = portfolio_data
            
            # Skip if no valid portfolio data (allow system to start without portfolio)
            if not portfolio_data or portfolio_data.total_value_usd <= 0:
                debug("No portfolio data available yet - waiting for initialization")
                return
            
            debug(f"Portfolio check: ${portfolio_data.available_for_defi_usd:.2f} available for DeFi")
            
            # Check if we meet minimum requirements for DeFi operations
            min_allocation = config.DEFI_MIN_ALLOCATION_PERCENT * portfolio_data.total_value_usd / 100
            if portfolio_data.available_for_defi_usd < min_allocation:
                debug(f"Insufficient capital for DeFi operations: ${portfolio_data.available_for_defi_usd:.2f} < ${min_allocation:.2f}")
                return
            
            # Check if we're under maximum allocation
            if portfolio_data.current_defi_allocation_usd < portfolio_data.max_defi_allocation_usd:
                debug("Under maximum DeFi allocation - can increase positions")
                
                # Get opportunities from integration layer
                opportunities = self.integration_layer.get_defi_opportunities()
                if opportunities:
                    self._evaluate_and_execute_opportunities(opportunities)
                
                # Check for leverage opportunities
                if self.enable_ai and portfolio_data.available_for_defi_usd > 100:
                    self._execute_leverage_strategy(portfolio_data)
            
        except Exception as e:
            error(f"Error checking portfolio state: {str(e)}")
    
    def _perform_risk_assessment(self):
        """Perform comprehensive risk assessment"""
        try:
            # Get current portfolio state
            if not self.current_portfolio_state:
                return
            
            # Skip risk assessment on initial startup to avoid false emergency stops
            if not hasattr(self, '_risk_assessment_initialized'):
                self._risk_assessment_initialized = True
                debug("Skipping initial risk assessment to prevent false emergency stops")
                return
            
            # Prepare portfolio data for risk manager
            portfolio_data = {
                'total_value_usd': self.current_portfolio_state.total_value_usd,
                'defi_allocation_usd': self.current_portfolio_state.current_defi_allocation_usd,
                'risk_score': self.current_portfolio_state.risk_score,
                'usdc_balance': self.current_portfolio_state.usdc_balance,
                'sol_balance': self.current_portfolio_state.sol_balance,
                'sol_value_usd': self.current_portfolio_state.sol_value_usd
            }
            
            # Perform risk assessment using DeFi risk manager
            risk_assessment = asyncio.run(self.risk_manager.assess_portfolio_risk(portfolio_data))
            
            # Update current risk level
            self.current_risk_level = risk_assessment.risk_level
            
            # Check if we need to take action
            if hasattr(risk_assessment, 'recommendations') and risk_assessment.recommendations:
                self._handle_risk_mitigation(risk_assessment)
            
            debug(f"Risk assessment completed: {self.current_risk_level} risk level")
            
        except Exception as e:
            error(f"Error performing risk assessment: {str(e)}")
    
    def _check_yield_opportunities(self):
        """Check for yield optimization opportunities"""
        try:
            # Prepare portfolio data for yield optimizer
            portfolio_data = {
                'current_allocation_usd': self.current_portfolio_state.current_defi_allocation_usd if self.current_portfolio_state else 0,
                'max_allocation_usd': self.current_portfolio_state.max_defi_allocation_usd if self.current_portfolio_state else 0,
                'total_value_usd': self.current_portfolio_state.total_value_usd if self.current_portfolio_state else 0,
                'usdc_balance': self.current_portfolio_state.usdc_balance if self.current_portfolio_state else 0,
                'sol_balance': self.current_portfolio_state.sol_balance if self.current_portfolio_state else 0
            }
            
            # Get current opportunities from yield optimizer
            async def _get_opportunities():
                return await self.yield_optimizer.optimize_yields(portfolio_data, risk_tolerance=self.current_risk_level)
            
            optimization_strategy = asyncio.run(_get_opportunities())
            
            # Extract opportunities from strategy
            opportunities = getattr(optimization_strategy, 'recommendations', [])
            self.current_opportunities = opportunities
            
            # Evaluate high-priority opportunities
            high_priority_opps = [opp for opp in opportunities if isinstance(opp, str) and 'high' in opp.lower()]
            if high_priority_opps:
                self._evaluate_and_execute_opportunities(high_priority_opps)
            
            debug(f"Yield check completed: {len(opportunities)} opportunities found")
            
        except Exception as e:
            error(f"Error checking yield opportunities: {str(e)}")
    
    def _execute_leverage_strategy(self, portfolio_data):
        """
        Execute leverage loop strategy with AI analysis
        Uses leverage engine with safety validator and AI advisor
        """
        try:
            if not portfolio_data:
                return
            
            # Safety check before leverage operations
            safety_check = self.safety_validator.can_execute_defi_operation(
                portfolio_data.available_for_defi_usd,
                "leverage_loop",
                portfolio_data
            )
            
            if not safety_check.is_safe:
                warning(f"🚫 Leverage strategy blocked: {safety_check.reason}")
                return
            
            # Get available capital from excluded tokens (idle assets)
            from src.config import EXCLUDED_TOKENS, SOL_ADDRESS, USDC_ADDRESS, STAKED_SOL_TOKEN_ADDRESS
            
            available_capital = {
                'SOL': portfolio_data.sol_value_usd,
                'stSOL': portfolio_data.staked_sol_value_usd,  # Use actual stSOL value from portfolio
                'USDC': portfolio_data.usdc_balance
            }
            
            # Check coordinator for trigger context - which asset triggered this execution
            trigger_context = self.coordinator.get_trigger_context()
            preferred_asset = None
            if trigger_context:
                preferred_asset = trigger_context.get('asset_type')  # e.g., 'stSOL'
                debug(f"🎯 Trigger context detected: {preferred_asset} triggered this execution")
                debug(f"🤖 AI Decision Debug: available_capital={available_capital}, preferred_asset={preferred_asset}")
            
            # Get AI advisor decision if enabled
            if self.ai_advisor:
                market_analysis = self.ai_advisor.assess_market_timing()
                market_sentiment = market_analysis.overall_sentiment
                
                # Get yield opportunities
                opportunities = self.integration_layer.get_defi_opportunities()
                
                # Pass preferred asset to AI advisor for collateral selection
                ai_decision = asyncio.run(
                    self.ai_advisor.analyze_leverage_opportunity(
                        available_capital, 
                        opportunities,
                        preferred_asset=preferred_asset
                    )
                )
                
                if not ai_decision.should_proceed:
                    info(f"🤖 AI advises against leverage: {ai_decision.reasoning}")
                    return
                
                # Use AI recommendation
                leverage_ratio = ai_decision.recommended_leverage
                collateral_asset = ai_decision.recommended_collateral
                iterations = int(leverage_ratio)
                
                info(f"🤖 AI recommends: {collateral_asset} collateral, {leverage_ratio:.2f}x leverage, {iterations} iterations")
            else:
                # Fallback to conservative defaults
                market_sentiment = "neutral"
                leverage_ratio = 2.0
                collateral_asset = "USDC"  # Safest choice
                iterations = 2
                
                info(f"📊 Conservative approach: {collateral_asset} collateral, {leverage_ratio:.2f}x leverage")
            
            # Scan for arbitrage opportunities periodically
            if self.cross_protocol_enabled:
                self._scan_arbitrage_opportunities()
            
            # Limit iterations to config maximum
            max_iterations = config.DEFI_MAX_ALLOCATION_PERCENT if hasattr(config, 'DEFI_MAX_ALLOCATION_PERCENT') else 3
            iterations = min(iterations, int(max_iterations))
            
            # Calculate dynamic minimum threshold based on position size
            from src.config.defi_config import LEVERAGE_LOOP_CONFIG
            base_threshold = LEVERAGE_LOOP_CONFIG.get('min_threshold_usd', 25.0)
            portfolio_pct = LEVERAGE_LOOP_CONFIG.get('min_threshold_percentage', 0.05)
            max_threshold = LEVERAGE_LOOP_CONFIG.get('max_threshold_usd', 100.0)

            # Lower threshold for preferred/triggered assets (like stSOL)
            if preferred_asset and collateral_asset == preferred_asset:
                base_threshold = max(base_threshold * 0.5, 10.0)  # 50% lower, minimum $10
                portfolio_pct = portfolio_pct * 0.5  # 50% lower percentage
                debug(f"🎯 Lowered threshold for preferred asset {preferred_asset}: base=${base_threshold:.2f}, pct={portfolio_pct:.3f}")

            # Dynamic threshold: base amount OR percentage of portfolio (whichever is higher), capped at max
            portfolio_size = portfolio_data.total_value_usd
            pct_threshold = portfolio_size * portfolio_pct
            min_threshold = min(max(base_threshold, pct_threshold), max_threshold)
            
            collateral_amount = available_capital[collateral_asset]

            # Apply position sizing limits to respect reserve requirements
            collateral_amount = self._apply_position_sizing_limits(
                collateral_amount, collateral_asset, portfolio_data
            )

            # Execute leverage loop
            if collateral_amount >= min_threshold:
                info(f"🚀 Executing leverage loop with ${collateral_amount:.2f} {collateral_asset} (threshold: ${min_threshold:.2f})")
                
                # Get best protocols for borrowing and lending if cross-protocol enabled
                borrowing_protocol = None
                lending_protocol = None
                
                if self.cross_protocol_enabled and self.protocol_router:
                    borrowing_protocol = self.protocol_router.select_best_borrowing_protocol(
                        amount_usd=collateral_amount * 0.75,  # Estimate borrowing amount
                        collateral_token=collateral_asset
                    )
                    lending_protocol = self.protocol_router.select_best_lending_protocol(
                        amount_usd=collateral_amount * 0.75
                    )
                    
                    if borrowing_protocol:
                        info(f"Selected borrowing protocol: {borrowing_protocol}")
                    if lending_protocol:
                        info(f"Selected lending protocol: {lending_protocol}")
                else:
                    # Fallback to default (Solend)
                    borrowing_protocol = "solend"
                    lending_protocol = "solend"
                
                loop = asyncio.run(
                    self.leverage_engine.execute_leverage_loop(
                        initial_capital_usd=collateral_amount,
                        collateral_token=collateral_asset,
                        market_sentiment=market_sentiment,
                        target_iterations=iterations,
                        borrowing_protocol=borrowing_protocol,
                        lending_protocol=lending_protocol
                    )
                )
                
                if loop:
                    info(f"✅ Leverage loop executed: {loop.iterations} iterations, {loop.current_leverage_ratio:.2f}x leverage")
                    
                    # Monitor loop health
                    health_score = self.leverage_engine.monitor_loop_health(loop)
                    info(f"📊 Loop health score: {health_score:.2f}")
                    
                    if health_score < 0.5:
                        warning("⚠️ Leverage loop health deteriorating - monitoring closely")
            else:
                debug(f"⏸️ Insufficient capital for leverage loop: ${collateral_amount:.2f} {collateral_asset} < ${min_threshold:.2f} minimum (base: ${base_threshold:.2f}, {portfolio_pct*100:.1f}% of ${portfolio_size:.2f} portfolio)")
            
        except Exception as e:
            error(f"Error executing leverage strategy: {str(e)}")
    
    def _scan_arbitrage_opportunities(self):
        """
        Scan for arbitrage opportunities and execute if beneficial
        Called periodically to optimize cross-protocol yields
        """
        try:
            if not self.cross_protocol_enabled or not self.arbitrage_engine:
                return False
            
            # Check if enough time has passed since last scan
            if self.last_arbitrage_scan:
                time_since_scan = (datetime.now() - self.last_arbitrage_scan).total_seconds() / 3600
                if time_since_scan < self.arbitrage_scan_interval_hours:
                    return False  # Too soon to scan again
            
            info("Scanning for arbitrage opportunities...")
            
            # Find arbitrage opportunities
            opportunities = self.arbitrage_engine.find_arbitrage_opportunities()
            
            if not opportunities:
                debug("No arbitrage opportunities found")
                self.last_arbitrage_scan = datetime.now()
                return False
            
            # Get best opportunity (already sorted by profit potential)
            best_opportunity = opportunities[0]
            
            info(f"Found arbitrage opportunity: {best_opportunity.borrow_protocol} ({best_opportunity.borrow_rate*100:.2f}%) → {best_opportunity.lend_protocol} ({best_opportunity.lend_rate*100:.2f}%)")
            info(f"  Spread: {best_opportunity.spread*100:.2f}%, Risk: {best_opportunity.risk_score:.2f}")
            
            # Calculate profit potential
            # Use a reasonable amount for arbitrage (e.g., 10% of available capital)
            # TODO: Get actual available capital from portfolio
            arbitrage_amount = 100.0  # Placeholder - should get from portfolio
            profit = self.arbitrage_engine.calculate_arbitrage_profit(best_opportunity, arbitrage_amount)
            
            info(f"  Profit potential: ${profit:.2f}/year on ${arbitrage_amount:.2f}")
            
            # Execute arbitrage if profitable
            if profit > 0:
                success = self.arbitrage_engine.execute_arbitrage(best_opportunity, arbitrage_amount)
                if success:
                    info(f"Successfully executed arbitrage: {best_opportunity.spread*100:.2f}% spread")
                else:
                    warning(f"Arbitrage execution failed")
            
            self.last_arbitrage_scan = datetime.now()
            return True
            
        except Exception as e:
            error(f"Error scanning arbitrage opportunities: {str(e)}")
            return False
    
    def _monitor_active_leverage_loops(self):
        """Monitor health of all active leverage loops and unwind if needed"""
        try:
            active_loops = self.leverage_engine.active_loops
            
            if not active_loops:
                return
            
            # Get current portfolio state
            portfolio_data = self.integration_layer.get_defi_portfolio_data()
            
            # Check safety thresholds first
            if portfolio_data and portfolio_data.available_for_defi_usd < 100:
                warning("⚠️ Insufficient capital for DeFi operations - unwinding loops")
                self._emergency_unwind_all_loops()
                return
            
            # Monitor each active loop
            for loop_id, loop in list(active_loops.items()):
                try:
                    # Check loop health
                    health_score = self.leverage_engine.monitor_loop_health(loop)
                    loop.health_score = health_score
                    
                    # Check if unwinding is needed
                    should_unwind = False
                    unwind_reason = ""
                    
                    # Reason 1: Health score critically low
                    if health_score < 0.3:
                        should_unwind = True
                        unwind_reason = f"Critical health score: {health_score:.2f}"
                    
                    # Reason 2: USDC emergency threshold
                    if portfolio_data:
                        usdc_pct = (portfolio_data.usdc_balance / portfolio_data.total_value_usd) if portfolio_data.total_value_usd > 0 else 0
                        if usdc_pct < config.USDC_EMERGENCY_PERCENT:
                            should_unwind = True
                            unwind_reason = f"USDC emergency: {usdc_pct*100:.1f}%"
                    
                    # Reason 3: AI recommends unwind
                    if self.ai_advisor:
                        try:
                            analysis = self.ai_advisor.assess_market_timing()
                            if analysis.overall_sentiment == "bearish" and health_score < 0.6:
                                should_unwind = True
                                unwind_reason = "Bearish market + low health"
                        except Exception as e:
                            debug(f"AI analysis failed: {str(e)}")
                    
                    if should_unwind:
                        warning(f"🔄 Unwinding loop {loop_id}: {unwind_reason}")
                        emergency = health_score < 0.3
                        success = self.leverage_engine.unwind_loop(loop, emergency=emergency)
                        
                        if success:
                            info(f"✅ Successfully unwound loop {loop_id}")
                        else:
                            error(f"❌ Failed to unwind loop {loop_id}")
                    
                    # Log health status
                    if health_score < 0.7:
                        warning(f"⚠️ Loop {loop_id} health: {health_score:.2f} (exposure: ${loop.total_exposure_usd:.2f})")
                    
                except Exception as e:
                    error(f"Error monitoring loop {loop_id}: {str(e)}")
                    
        except Exception as e:
            error(f"Error monitoring active leverage loops: {str(e)}")
    
    def _emergency_unwind_all_loops(self):
        """Emergency unwind all active leverage loops"""
        try:
            info("🚨 EMERGENCY UNWIND: Closing all active leverage loops")
            
            active_loops = self.leverage_engine.active_loops.copy()
            
            for loop_id, loop in active_loops.items():
                try:
                    success = self.leverage_engine.unwind_loop(loop, emergency=True)
                    if success:
                        info(f"✅ Emergency unwound loop {loop_id}")
                    else:
                        error(f"❌ Failed to emergency unwind loop {loop_id}")
                except Exception as e:
                    error(f"Error emergency unwinding loop {loop_id}: {str(e)}")
            
            info("🚨 Emergency unwind complete")
            
        except Exception as e:
            error(f"Error in emergency unwind: {str(e)}")
    
    def _evaluate_and_execute_opportunities(self, opportunities: List[Dict[str, Any]]):
        """Evaluate and execute DeFi opportunities"""
        try:
            for opportunity in opportunities:
                # Check if we should execute this opportunity
                if self._should_execute_opportunity(opportunity):
                    # Create execution request
                    execution_request = DeFiExecutionRequest(
                        operation_type=opportunity['type'],
                        protocol=opportunity['protocol'],
                        token_address=opportunity.get('token_address', ''),
                        amount_usd=opportunity['amount_usd'],
                        priority=opportunity.get('priority', 'normal'),
                        requires_approval=self._requires_approval(opportunity),
                        metadata=opportunity
                    )
                    
                    # Request execution
                    execution_id = self.integration_layer.request_defi_execution(execution_request)
                    
                    if execution_id != "failed":
                        # Create operation record
                        operation = DeFiOperation(
                            operation_id=execution_id,
                            operation_type=opportunity['type'],
                            protocol=opportunity['protocol'],
                            token_address=opportunity.get('token_address', ''),
                            amount_usd=opportunity['amount_usd'],
                            priority=opportunity.get('priority', 'normal'),
                            status='pending',
                            created_at=datetime.now(),
                            metadata=opportunity
                        )
                        
                        # Add to pending operations
                        with self.operations_lock:
                            self.pending_operations.append(operation)
                        
                        info(f"DeFi opportunity queued: {opportunity['type']} on {opportunity['protocol']}")
                    else:
                        warning(f"Failed to queue DeFi opportunity: {opportunity['type']} on {opportunity['protocol']}")
                        
        except Exception as e:
            error(f"Error evaluating opportunities: {str(e)}")
    
    def _should_execute_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """Determine if an opportunity should be executed"""
        try:
            # Check if we have sufficient capital
            if not self.current_portfolio_state:
                return False
            
            if opportunity['amount_usd'] > self.current_portfolio_state.available_for_defi_usd:
                return False
            
            # Check risk level compatibility
            if opportunity.get('risk_level') == 'high' and self.current_risk_level == 'HIGH':
                return False
            
            # Check APY threshold
            if opportunity.get('estimated_apy', 0) < config.DEFI_MIN_APY_THRESHOLD:
                return False
            
            # Check if we're already at max allocation
            if self.current_portfolio_state.current_defi_allocation_usd >= self.current_portfolio_state.max_defi_allocation_usd:
                return False
            
            return True
            
        except Exception as e:
            error(f"Error checking opportunity execution: {str(e)}")
            return False
    
    def _requires_approval(self, opportunity: Dict[str, Any]) -> bool:
        """Determine if an opportunity requires manual approval"""
        try:
            amount_usd = opportunity['amount_usd']
            
            # Check approval thresholds from config
            if amount_usd <= config.BORROWING_APPROVAL['auto_approval_limit_usd']:
                return False
            elif amount_usd <= config.BORROWING_APPROVAL['telegram_approval_limit_usd']:
                return True  # Requires Telegram approval
            else:
                return True  # Requires manual approval
            
        except Exception as e:
            error(f"Error checking approval requirement: {str(e)}")
            return True  # Default to requiring approval
    
    def _handle_risk_mitigation(self, risk_assessment):
        """Handle risk mitigation actions"""
        try:
            # Handle both dict and RiskAssessment object
            if isinstance(risk_assessment, dict):
                actions = risk_assessment.get('recommended_actions', [])
            else:
                # RiskAssessment object
                actions = getattr(risk_assessment, 'recommendations', [])
            
            if not actions:
                return  # No actions needed
            
            for action in actions:
                if isinstance(action, str):
                    # If action is a string recommendation
                    if 'reduce' in action.lower():
                        warning(f"Risk mitigation: {action}")
                    elif 'emergency' in action.lower():
                        self._trigger_emergency_stop()
                    elif 'rebalance' in action.lower():
                        self._rebalance_defi_positions()
                elif isinstance(action, dict):
                    # If action is a dict
                    action_type = action.get('type', '')
                    if action_type == 'reduce_allocation':
                        self._reduce_defi_allocation(action.get('amount_usd', 0))
                    elif action_type == 'add_collateral':
                        self._add_collateral_automatically(action.get('amount_usd', 0))
                    elif action_type == 'emergency_stop':
                        self._trigger_emergency_stop()
                    elif action_type == 'rebalance':
                        self._rebalance_defi_positions()
            
        except Exception as e:
            error(f"Error handling risk mitigation: {str(e)}")
    
    def _reduce_defi_allocation(self, amount_usd: float):
        """Reduce DeFi allocation by specified amount"""
        try:
            info(f"Reducing DeFi allocation by ${amount_usd:.2f}")
            
            # This would implement actual position reduction logic
            # For now, just log the action
            
        except Exception as e:
            error(f"Error reducing DeFi allocation: {str(e)}")
    
    def _add_collateral_automatically(self, amount_usd: float):
        """Add collateral automatically to prevent liquidation"""
        try:
            info(f"Adding ${amount_usd:.2f} in collateral automatically")
            
            # This would implement actual collateral addition logic
            # For now, just log the action
            
        except Exception as e:
            error(f"Error adding collateral: {str(e)}")
    
    def _trigger_emergency_stop(self):
        """Trigger emergency stop for DeFi operations"""
        try:
            warning("🚨 EMERGENCY STOP TRIGGERED for DeFi operations")
            
            # Stop all pending operations
            with self.operations_lock:
                for operation in self.pending_operations:
                    operation.status = 'cancelled'
            
            # Send emergency alert
            if self.telegram_enabled:
                self.telegram_bot.send_notification(
                    "🚨 EMERGENCY STOP: DeFi operations halted due to risk assessment",
                    level="critical"
                )
            
        except Exception as e:
            error(f"Error triggering emergency stop: {str(e)}")
    
    def _rebalance_defi_positions(self):
        """Rebalance DeFi positions for optimal allocation"""
        try:
            info("Rebalancing DeFi positions")
            
            # This would implement actual rebalancing logic
            # For now, just log the action
            
        except Exception as e:
            error(f"Error rebalancing DeFi positions: {str(e)}")
    
    def _process_pending_operations(self):
        """Process pending DeFi operations"""
        try:
            with self.operations_lock:
                operations_to_process = [op for op in self.pending_operations if op.status == 'approved']
            
            for operation in operations_to_process:
                # Execute the operation
                success = self.integration_layer.execute_defi_operation(
                    DeFiExecutionRequest(
                        operation_type=operation.operation_type,
                        protocol=operation.protocol,
                        token_address=operation.token_address,
                        amount_usd=operation.amount_usd,
                        priority=operation.priority,
                        requires_approval=False,
                        metadata=operation.metadata
                    )
                )
                
                if success:
                    operation.status = 'completed'
                    operation.executed_at = datetime.now()
                    
                    # Move to completed operations
                    with self.operations_lock:
                        self.pending_operations.remove(operation)
                        self.completed_operations.append(operation)
                    
                    info(f"✅ DeFi operation completed: {operation.operation_type} on {operation.protocol}")
                else:
                    operation.status = 'failed'
                    
                    # Move to failed operations
                    with self.operations_lock:
                        self.pending_operations.remove(operation)
                        self.failed_operations.append(operation)
                    
                    error(f"❌ DeFi operation failed: {operation.operation_type} on {operation.protocol}")
                    
        except Exception as e:
            error(f"Error processing pending operations: {str(e)}")
    
    def request_borrowing(self, token_address: str, amount_usd: float, protocol: str = "solend") -> str:
        """
        Request borrowing operation (requires manual approval)
        
        Args:
            token_address: Token to borrow
            amount_usd: Amount to borrow in USD
            protocol: DeFi protocol to use
            
        Returns:
            Operation ID string
        """
        try:
            # Validate borrowing request
            validation_result = self._validate_borrowing_request(token_address, amount_usd, protocol)
            if not validation_result['valid']:
                return f"validation_failed: {validation_result['reason']}"
            
            # Create borrowing operation
            operation = DeFiOperation(
                operation_id=f"borrow_{int(time.time())}",
                operation_type="borrow",
                protocol=protocol,
                token_address=token_address,
                amount_usd=amount_usd,
                priority="high",
                status="pending",
                created_at=datetime.now(),
                metadata={'requires_manual_approval': True}
            )
            
            # Add to pending operations
            with self.operations_lock:
                self.pending_operations.append(operation)
            
            # Send approval request to Telegram
            if self.telegram_enabled:
                self.telegram_bot.request_borrowing_approval(operation)
            
            info(f"Borrowing request created: ${amount_usd:.2f} {token_address} on {protocol}")
            return operation.operation_id
            
        except Exception as e:
            error(f"Error requesting borrowing: {str(e)}")
            return "failed"
    
    def _validate_borrowing_request(self, token_address: str, amount_usd: float, protocol: str) -> Dict[str, Any]:
        """Validate borrowing request against risk parameters"""
        try:
            if not self.current_portfolio_state:
                return {'valid': False, 'reason': 'Portfolio state not available'}
            
            # Check minimum balance requirements
            if self.current_portfolio_state.total_value_usd < config.BORROWING_REQUIREMENTS['min_total_balance_usd']:
                return {'valid': False, 'reason': f"Insufficient total balance: ${self.current_portfolio_state.total_value_usd:.2f}"}
            
            # Check borrowing ratio
            current_borrowing = self.current_portfolio_state.current_defi_allocation_usd
            max_borrowing = self.current_portfolio_state.total_value_usd * config.BORROWING_REQUIREMENTS['max_borrowing_ratio']
            
            if current_borrowing + amount_usd > max_borrowing:
                return {'valid': False, 'reason': f"Would exceed max borrowing ratio: {config.BORROWING_REQUIREMENTS['max_borrowing_ratio']*100:.1f}%"}
            
            # Check collateral ratio
            total_collateral = self.current_portfolio_state.total_value_usd
            total_borrowing = current_borrowing + amount_usd
            collateral_ratio = total_collateral / total_borrowing if total_borrowing > 0 else float('inf')
            
            if collateral_ratio < config.BORROWING_REQUIREMENTS['min_collateral_ratio']:
                return {'valid': False, 'reason': f"Insufficient collateral ratio: {collateral_ratio:.2f}"}
            
            return {'valid': True, 'reason': 'Validation passed'}
            
        except Exception as e:
            error(f"Error validating borrowing request: {str(e)}")
            return {'valid': False, 'reason': f'Validation error: {str(e)}'}
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        try:
            return {
                'status': 'running' if self.running else 'stopped',
                'phase': self.current_phase,
                'risk_level': self.current_risk_level,
                'pending_operations': len(self.pending_operations),
                'completed_operations': len(self.completed_operations),
                'failed_operations': len(self.failed_operations),
                'portfolio_state': self.current_portfolio_state.__dict__ if self.current_portfolio_state else None,
                'current_opportunities': len(self.current_opportunities),
                'telegram_enabled': self.telegram_enabled,
                'last_portfolio_check': self.last_portfolio_check,
                'last_risk_assessment': self.last_risk_assessment,
                'last_yield_check': self.last_yield_check
            }
        except Exception as e:
            error(f"Error getting agent status: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def get_operations_summary(self) -> Dict[str, Any]:
        """Get operations summary for status display"""
        try:
            return {
                'total_operations': len(self.completed_operations),
                'pending_operations': len(self.pending_operations),
                'failed_operations': len(self.failed_operations),
                'last_operation_time': self.last_portfolio_check,
                'risk_level': self.current_risk_level
            }
        except Exception as e:
            return {
                'total_operations': 0,
                'pending_operations': 0,
                'failed_operations': 0,
                'error': str(e)
            }

    def _apply_position_sizing_limits(self, available_amount: float, asset: str, portfolio_data) -> float:
        """
        Apply position sizing limits to respect reserve requirements
        Similar to staking agent's approach but for DeFi operations
        """
        try:
            from src.config.defi_config import DEFI_SAFETY_CONFIG

            total_value = portfolio_data.total_value_usd

            if asset == 'SOL':
                # SOL limits: Preserve 10% minimum reserve
                min_sol_reserve_pct = 0.10  # 10% total SOL reserve

                current_sol_pct = (portfolio_data.sol_value_usd / total_value) if total_value > 0 else 0
                target_sol_reserve = total_value * min_sol_reserve_pct

                # Calculate maximum SOL that can be used for DeFi (excess above 10%)
                max_sol_for_defi = max(0, portfolio_data.sol_value_usd - target_sol_reserve)

                # Use only 50% of available excess (conservative approach)
                limited_amount = min(available_amount, max_sol_for_defi * 0.5)

                if limited_amount < available_amount:
                    info(f"🔒 SOL position sizing: ${available_amount:.2f} available → ${limited_amount:.2f} allowed (preserves {min_sol_reserve_pct*100:.0f}% reserve)")

            elif asset == 'stSOL':
                # stSOL: More flexible since it's already staked, but still limit to 70% of available
                limited_amount = available_amount * 0.7
                if limited_amount < available_amount:
                    info(f"🔒 stSOL position sizing: ${available_amount:.2f} available → ${limited_amount:.2f} allowed (70% limit)")

            elif asset == 'USDC':
                # USDC limits: Keep 20% minimum reserve
                usdc_min_pct = DEFI_SAFETY_CONFIG.get('usdc_minimum_percent', 0.20)
                current_usdc_pct = (portfolio_data.usdc_balance / total_value) if total_value > 0 else 0
                target_usdc_reserve = total_value * usdc_min_pct

                # Calculate maximum USDC that can be used for DeFi
                max_usdc_for_defi = max(0, portfolio_data.usdc_balance - target_usdc_reserve)

                # Use only 30% of available excess (more conservative for USDC)
                limited_amount = min(available_amount, max_usdc_for_defi * 0.3)

                if limited_amount < available_amount:
                    info(f"🔒 USDC position sizing: ${available_amount:.2f} available → ${limited_amount:.2f} allowed (preserves {usdc_min_pct*100:.0f}% reserve)")

            else:
                # Default: Use 50% of available for unknown assets
                limited_amount = available_amount * 0.5
                debug(f"🔒 Default position sizing for {asset}: ${available_amount:.2f} → ${limited_amount:.2f} (50% limit)")

            return limited_amount

        except Exception as e:
            error(f"Error applying position sizing limits: {str(e)}")
            # On error, use conservative 30% limit
            return available_amount * 0.3

# Singleton pattern for defi agent
_defi_agent_instance = None

def get_defi_agent():
    """Get the singleton defi agent instance"""
    global _defi_agent_instance
    if _defi_agent_instance is None:
        _defi_agent_instance = DeFiAgent()
    return _defi_agent_instance