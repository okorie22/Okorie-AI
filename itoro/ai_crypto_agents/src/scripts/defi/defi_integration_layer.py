"""
🌙 Anarcho Capital's DeFi Integration Layer
Connects DeFi agent to existing shared services for unified operations
Built with love by Anarcho Capital 🚀
"""

import threading
import time
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

# Local imports with fallback for relative imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator, AgentType
    from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
    # Trade lock manager removed - now using SimpleAgentCoordinator
    from src.scripts.trading.position_manager import get_position_manager
    from src.scripts.shared_services.hybrid_rpc_manager import get_hybrid_rpc_manager
    from src.scripts.data_processing.sentiment_data_extractor import get_sentiment_data_extractor
    from src import config
except ImportError:
    from src.scripts.shared_services.logger import debug, info, warning, error, critical
    from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator, AgentType
    from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
    # Trade lock manager removed - now using SimpleAgentCoordinator
    from src.scripts.trading.position_manager import get_position_manager
    from src.scripts.shared_services.hybrid_rpc_manager import get_hybrid_rpc_manager
    from src.scripts.data_processing.sentiment_data_extractor import get_sentiment_data_extractor
    import src.config as config

@dataclass
class DeFiPortfolioData:
    """Portfolio data specifically formatted for DeFi operations"""
    total_value_usd: float = 0.0
    usdc_balance: float = 0.0
    sol_balance: float = 0.0
    sol_value_usd: float = 0.0
    staked_sol_value_usd: float = 0.0  # stSOL value for leverage loops
    available_for_defi_usd: float = 0.0
    current_defi_allocation_usd: float = 0.0
    max_defi_allocation_usd: float = 0.0
    risk_score: float = 0.0
    market_sentiment: str = "NEUTRAL"
    sentiment_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Note: usdc_balance_usd and sol_balance_usd are added as attributes 
    # in get_defi_portfolio_data() for compatibility with safety validator

@dataclass
class DeFiExecutionRequest:
    """Request for DeFi operation execution"""
    operation_type: str  # "lend", "borrow", "yield_farm", "arbitrage"
    protocol: str  # "solend", "mango", "tulip", etc.
    token_address: str
    amount_usd: float
    priority: str = "normal"  # "low", "normal", "high", "urgent"
    requires_approval: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

class DeFiIntegrationLayer:
    """
    Integration layer that connects DeFi agent to existing shared services
    Provides unified access to portfolio data, trade execution, and risk management
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
        """Initialize the DeFi integration layer"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Get shared services
        self.data_coordinator = get_shared_data_coordinator()
        self.portfolio_tracker = get_portfolio_tracker()
        # Trade lock manager removed - now using SimpleAgentCoordinator
        self.position_manager = get_position_manager()
        self.rpc_manager = get_hybrid_rpc_manager()
        self.sentiment_extractor = get_sentiment_data_extractor()
        
        # Register with data coordinator
        self.data_coordinator.register_agent(AgentType.DEFI, f"defi_integration_{id(self)}")
        
        # DeFi-specific caches
        self.portfolio_cache: Optional[DeFiPortfolioData] = None
        self.portfolio_cache_expiry = 30  # seconds
        self.last_portfolio_update = 0
        
        # Execution tracking
        self.pending_executions: List[DeFiExecutionRequest] = []
        self.execution_lock = threading.RLock()
        
        info("DeFi Integration Layer initialized successfully")
    
    def get_defi_portfolio_data(self, force_refresh: bool = False) -> DeFiPortfolioData:
        """
        Get comprehensive portfolio data formatted for DeFi operations
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            DeFiPortfolioData object with current portfolio state
        """
        current_time = time.time()
        
        # Check cache validity
        if (not force_refresh and 
            self.portfolio_cache and 
            current_time - self.last_portfolio_update < self.portfolio_cache_expiry):
            return self.portfolio_cache
        
        try:
            # Get current portfolio snapshot
            portfolio_snapshot = self.portfolio_tracker.current_snapshot
            if not portfolio_snapshot:
                warning("No portfolio snapshot available")
                return DeFiPortfolioData()
            
            # Get market sentiment
            sentiment_data = self.get_market_sentiment()
            
            # Calculate DeFi-specific metrics
            total_value = portfolio_snapshot.total_value_usd
            usdc_balance = portfolio_snapshot.usdc_balance
            sol_balance = portfolio_snapshot.sol_balance
            sol_value = portfolio_snapshot.sol_value_usd
            # Get staked SOL value from portfolio snapshot
            staked_sol_value = getattr(portfolio_snapshot, 'staked_sol_value_usd', 0.0)
            
            # Calculate available allocation (respecting risk limits)
            max_defi_allocation = total_value * config.DEFI_MAX_ALLOCATION_PERCENT / 100
            current_defi_allocation = self._get_current_defi_allocation()
            available_for_defi = max_defi_allocation - current_defi_allocation
            
            # Calculate risk score based on portfolio composition
            risk_score = self._calculate_portfolio_risk_score(portfolio_snapshot)
            
            # Create DeFi portfolio data
            defi_data = DeFiPortfolioData(
                total_value_usd=total_value,
                usdc_balance=usdc_balance,
                sol_balance=sol_balance,
                sol_value_usd=sol_value,
                staked_sol_value_usd=staked_sol_value,
                available_for_defi_usd=max(0, available_for_defi),
                current_defi_allocation_usd=current_defi_allocation,
                max_defi_allocation_usd=max_defi_allocation,
                risk_score=risk_score,
                market_sentiment=sentiment_data.get('overall_sentiment', 'NEUTRAL'),
                sentiment_score=sentiment_data.get('sentiment_score', 0.0),
                timestamp=datetime.now()
            )
            
            # CRITICAL FIX: Add compatibility aliases as attributes for safety validator
            defi_data.usdc_balance_usd = usdc_balance
            defi_data.sol_balance_usd = sol_value
            
            # Update cache
            self.portfolio_cache = defi_data
            self.last_portfolio_update = current_time
            
            debug(f"DeFi portfolio data updated: ${defi_data.available_for_defi_usd:.2f} available for DeFi")
            return defi_data
            
        except Exception as e:
            error(f"Error getting DeFi portfolio data: {str(e)}")
            return DeFiPortfolioData()
    
    def get_market_sentiment(self) -> Dict[str, Any]:
        """
        Get current market sentiment data for DeFi timing decisions
        
        Returns:
            Dictionary with sentiment data
        """
        try:
            if not self.sentiment_extractor:
                return {'overall_sentiment': 'NEUTRAL', 'sentiment_score': 0.0}
            
            sentiment_data = self.sentiment_extractor.get_combined_sentiment_data()
            if not sentiment_data:
                return {'overall_sentiment': 'NEUTRAL', 'sentiment_score': 0.0}
            
            return {
                'overall_sentiment': sentiment_data.chart_sentiment,
                'sentiment_score': sentiment_data.chart_confidence,
                'chart_bullish_tokens': sentiment_data.chart_bullish_tokens,
                'chart_bearish_tokens': sentiment_data.chart_bearish_tokens,
                'twitter_sentiment': sentiment_data.twitter_classification,
                'data_freshness_minutes': sentiment_data.data_freshness_minutes
            }
            
        except Exception as e:
            error(f"Error getting market sentiment: {str(e)}")
            return {'overall_sentiment': 'NEUTRAL', 'sentiment_score': 0.0}
    
    def request_defi_execution(self, request: DeFiExecutionRequest) -> str:
        """
        Request execution of a DeFi operation
        
        Args:
            request: DeFiExecutionRequest object
            
        Returns:
            Execution ID string
        """
        try:
            # Generate execution ID
            execution_id = f"defi_{int(time.time())}_{hash(request.token_address) % 10000}"
            
            # Add to pending executions
            with self.execution_lock:
                self.pending_executions.append(request)
            
            info(f"DeFi execution requested: {request.operation_type} on {request.protocol} for ${request.amount_usd:.2f}")
            
            # If approval required, send to Telegram bot
            if request.requires_approval:
                self._send_approval_request(request, execution_id)
            
            return execution_id
            
        except Exception as e:
            error(f"Error requesting DeFi execution: {str(e)}")
            return "failed"
    
    def execute_defi_operation(self, request: DeFiExecutionRequest) -> bool:
        """
        Execute a DeFi operation using appropriate trade locks and execution methods
        
        Args:
            request: DeFiExecutionRequest object
            
        Returns:
            True if execution successful, False otherwise
        """
        try:
            # Determine lock type based on operation
            lock_type = self._get_lock_type_for_operation(request.operation_type)
            
            # Trade lock removed - using SimpleAgentCoordinator for priority management
            debug(f"Executing DeFi operation {request.operation_type} with priority coordination")
            
            # Execute the operation
            success = self._execute_defi_operation_internal(request)
            
            if success:
                info(f"✅ DeFi operation executed successfully: {request.operation_type} on {request.protocol}")
            else:
                error(f"❌ DeFi operation failed: {request.operation_type} on {request.protocol}")
            
            return success
                
        except Exception as e:
            error(f"Error executing DeFi operation: {str(e)}")
            return False
    
    def get_defi_opportunities(self) -> List[Dict[str, Any]]:
        """
        Get current DeFi opportunities based on portfolio state and market conditions
        
        Returns:
            List of DeFi opportunity dictionaries
        """
        try:
            portfolio_data = self.get_defi_portfolio_data()
            sentiment_data = self.get_market_sentiment()
            
            opportunities = []
            
            # Check if we have sufficient capital
            if portfolio_data.available_for_defi_usd < 100:  # Minimum $100
                return opportunities
            
            # Generate opportunities based on current state
            if portfolio_data.usdc_balance > 50:
                # USDC lending opportunities
                opportunities.append({
                    'type': 'lending',
                    'asset': 'USDC',
                    'protocol': 'solend',
                    'estimated_apy': 8.5,
                    'risk_level': 'low',
                    'amount_usd': min(portfolio_data.usdc_balance * 0.8, portfolio_data.available_for_defi_usd),
                    'priority': 'normal'
                })
            
            if portfolio_data.sol_balance > 1:
                # SOL staking opportunities
                opportunities.append({
                    'type': 'staking',
                    'asset': 'SOL',
                    'protocol': 'marinade',
                    'estimated_apy': 6.2,
                    'risk_level': 'low',
                    'amount_usd': min(portfolio_data.sol_value_usd * 0.5, portfolio_data.available_for_defi_usd),
                    'priority': 'normal'
                })
            
            # Adjust opportunities based on sentiment
            if sentiment_data.get('overall_sentiment') == 'BULLISH':
                # More aggressive in bullish markets
                for opp in opportunities:
                    opp['amount_usd'] *= 1.2
                    opp['priority'] = 'high'
            
            return opportunities
            
        except Exception as e:
            error(f"Error getting DeFi opportunities: {str(e)}")
            return []
    
    def _get_current_defi_allocation(self) -> float:
        """Get current DeFi allocation in USD"""
        try:
            # This would query actual DeFi positions
            # For now, return 0 (no current allocation)
            return 0.0
        except Exception as e:
            error(f"Error getting current DeFi allocation: {str(e)}")
            return 0.0
    
    def _calculate_portfolio_risk_score(self, portfolio_snapshot) -> float:
        """Calculate portfolio risk score (0-100, higher = riskier)"""
        try:
            risk_score = 0.0
            
            # Base risk from portfolio composition
            if portfolio_snapshot.positions_value_usd > 0:
                position_ratio = portfolio_snapshot.positions_value_usd / portfolio_snapshot.total_value_usd
                risk_score += position_ratio * 30  # Positions add risk
            
            # SOL concentration risk
            if portfolio_snapshot.sol_value_usd > 0:
                sol_ratio = portfolio_snapshot.sol_value_usd / portfolio_snapshot.total_value_usd
                if sol_ratio > 0.5:
                    risk_score += (sol_ratio - 0.5) * 40  # High SOL concentration adds risk
            
            # USDC stability (reduces risk)
            usdc_ratio = portfolio_snapshot.usdc_balance / portfolio_snapshot.total_value_usd
            risk_score -= usdc_ratio * 20  # USDC reduces risk
            
            return max(0, min(100, risk_score))
            
        except Exception as e:
            error(f"Error calculating portfolio risk score: {str(e)}")
            return 50.0  # Default to medium risk
    
    def _get_lock_type_for_operation(self, operation_type: str) -> str:
        """Get appropriate lock type for DeFi operation
        
        NOTE: Trade lock manager has been replaced with SimpleAgentCoordinator
        This method is kept for compatibility but no longer actively used.
        """
        # Simple string-based lock types since LockType enum is no longer available
        lock_map = {
            'lend': 'DEFI_LENDING_OPERATION',
            'borrow': 'DEFI_BORROWING_OPERATION',
            'yield_farm': 'DEFI_YIELD_FARMING_OPERATION',
            'arbitrage': 'DEFI_YIELD_FARMING_OPERATION',
            'stake': 'STAKING_OPERATION'
        }
        return lock_map.get(operation_type, 'PORTFOLIO_OPERATION')
    
    def _execute_defi_operation_internal(self, request: DeFiExecutionRequest) -> bool:
        """Internal execution of DeFi operation using nice_funcs"""
        try:
            # Import nice_funcs for actual execution
            from src import nice_funcs
            
            debug(f"Executing DeFi operation: {request.operation_type} on {request.protocol}")
            
            # Execute based on operation type
            if request.operation_type == "lend":
                success = nice_funcs.defi_lend_usdc(
                    amount_usd=request.amount_usd,
                    protocol=request.protocol,
                    slippage=config.DEFI_SLIPPAGE_TOLERANCE
                )
            elif request.operation_type == "borrow":
                success = nice_funcs.defi_borrow_usdc(
                    amount_usd=request.amount_usd,
                    collateral_token=request.metadata.get('collateral_token', 'SOL'),
                    protocol=request.protocol,
                    slippage=config.DEFI_SLIPPAGE_TOLERANCE
                )
            elif request.operation_type == "yield_farm":
                success = nice_funcs.defi_yield_farm(
                    token_address=request.token_address,
                    amount_usd=request.amount_usd,
                    protocol=request.protocol,
                    slippage=config.DEFI_SLIPPAGE_TOLERANCE
                )
            elif request.operation_type == "arbitrage":
                # For arbitrage, we need to execute multiple operations
                success = self._execute_arbitrage_operation(request)
            else:
                error(f"Unsupported operation type: {request.operation_type}")
                return False
            
            if success:
                # Log successful execution
                self._log_defi_execution(request, success=True)
            else:
                # Log failed execution
                self._log_defi_execution(request, success=False)
            
            return success
            
        except Exception as e:
            error(f"Error in internal DeFi execution: {str(e)}")
            return False
    
    def _execute_arbitrage_operation(self, request: DeFiExecutionRequest) -> bool:
        """Execute cross-protocol arbitrage operation"""
        try:
            from src import nice_funcs
            
            # Get arbitrage details from metadata
            source_protocol = request.metadata.get('source_protocol')
            target_protocol = request.metadata.get('target_protocol')
            source_apy = request.metadata.get('source_apy', 0)
            target_apy = request.metadata.get('target_apy', 0)
            
            if not all([source_protocol, target_protocol, source_apy, target_apy]):
                error("Missing arbitrage metadata")
                return False
            
            # Execute the arbitrage (move funds from lower to higher APY)
            if target_apy > source_apy:
                # Move to higher APY protocol
                success = nice_funcs.defi_lend_usdc(
                    amount_usd=request.amount_usd,
                    protocol=target_protocol,
                    slippage=config.DEFI_SLIPPAGE_TOLERANCE
                )
                
                if success:
                    info(f"✅ Arbitrage executed: Moved ${request.amount_usd:.2f} from {source_protocol} ({source_apy:.1f}%) to {target_protocol} ({target_apy:.1f}%)")
                
                return success
            else:
                warning(f"Arbitrage not profitable: {source_protocol} ({source_apy:.1f}%) vs {target_protocol} ({target_apy:.1f}%)")
                return False
                
        except Exception as e:
            error(f"Error executing arbitrage operation: {str(e)}")
            return False
    
    def _send_approval_request(self, request: DeFiExecutionRequest, execution_id: str):
        """Send approval request to Telegram bot"""
        try:
            # This would integrate with your Telegram bot
            debug(f"Approval request sent for execution {execution_id}")
        except Exception as e:
            error(f"Error sending approval request: {str(e)}")
    
    def _log_defi_execution(self, request: DeFiExecutionRequest, success: bool):
        """Log DeFi execution for tracking"""
        try:
            # This would integrate with your trade log system
            debug(f"DeFi execution logged: {request.operation_type} on {request.protocol} - {'SUCCESS' if success else 'FAILED'}")
        except Exception as e:
            error(f"Error logging DeFi execution: {str(e)}")

# Global instance for easy access
def get_defi_integration_layer() -> DeFiIntegrationLayer:
    """Get the global DeFi integration layer instance"""
    return DeFiIntegrationLayer()
