"""
[EMERGENCY] Anarcho Capital's Emergency Risk Agent
Streamlined portfolio-level emergency protection system
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import json
import threading
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical
from src.scripts.trading.portfolio_tracker import get_portfolio_tracker, PortfolioSnapshot
from src.scripts.trading.breakeven import get_breakeven_manager
from src.scripts.database.execution_tracker import get_execution_tracker
from src.scripts.shared_services.optimized_price_service import get_optimized_price_service
from src.scripts.shared_services.shared_data_coordinator import get_shared_data_coordinator
# AI model import - DeepSeek required
from src.models.model_factory import create_model
from src.agents.base_agent import BaseAgent
from src import config

# Configuration imports
from src.config import (
    EMERGENCY_USDC_RESERVE_PERCENT,
    EMERGENCY_SOL_RESERVE_PERCENT,
    EMERGENCY_CHECK_INTERVAL_MINUTES,
    CONSECUTIVE_LOSS_LIMIT,
    DRAWDOWN_LIMIT_PERCENT,
    ENABLE_AGGREGATED_SENTIMENT,
    AGGREGATED_SENTIMENT_FILE,
    WALLETS_TO_TRACK,
    DEFAULT_WALLET_ADDRESS,
    PAPER_TRADING_ENABLED,
    EXCLUDED_TOKENS,
    USDC_ADDRESS,
    SOL_ADDRESS,
    AUTO_RECOVERY_USDC_THRESHOLD,
    AUTO_RECOVERY_SOL_THRESHOLD,
    AUTO_RECOVERY_DRAWDOWN_THRESHOLD,
    AUTO_RECOVERY_PORTFOLIO_RECOVERY,
    AUTO_RECOVERY_MIN_CONDITIONS
)

@dataclass
class EmergencyTrigger:
    """Data class for emergency trigger information"""
    trigger_type: str
    severity: str
    value: float
    threshold: float
    description: str
    timestamp: datetime

@dataclass
class PortfolioMetrics:
    """Data class for portfolio metrics"""
    total_value_usd: float
    usdc_reserve_percent: float
    sol_reserve_percent: float
    drawdown_percent: float
    consecutive_losses: int
    peak_value: float
    open_positions: List[Dict[str, Any]]
    
    def __post_init__(self):
        """Validate data after initialization"""
        if self.total_value_usd is None:
            self.total_value_usd = 0.0

class RiskAgent(BaseAgent):
    """
    Streamlined emergency risk protection system
    Monitors 3 core portfolio-level metrics and executes escalating protective actions
    """
    
    def __init__(self):
        """Initialize the emergency risk agent"""
        super().__init__("emergency_risk")
        
        # Configuration
        self.enabled = True
        self.check_interval_minutes = EMERGENCY_CHECK_INTERVAL_MINUTES
        self.usdc_reserve_threshold = EMERGENCY_USDC_RESERVE_PERCENT
        self.sol_reserve_threshold = EMERGENCY_SOL_RESERVE_PERCENT
        
        # Startup mode configuration
        self.startup_mode_enabled = getattr(config, 'STARTUP_MODE_ENABLED', True)
        self.startup_duration_seconds = getattr(config, 'STARTUP_MODE_DURATION_SECONDS', 120)
        self.startup_sol_threshold = getattr(config, 'STARTUP_MODE_SOL_THRESHOLD', 0.95)
        self.startup_usdc_threshold = getattr(config, 'STARTUP_MODE_USDC_THRESHOLD', 0.05)
        self.startup_time = time.time()  # Record when risk agent was initialized
        
        # State tracking
        self.is_running = False
        self.thread = None
        self.peak_portfolio_value = 0.0
        self.last_check_time = 0
        self.emergency_actions_taken = []
        
        # Manual review tracking
        self.requires_manual_review = False
        
        # Cooldown tracking
        self.last_action_time = 0
        self.cooldown_seconds = config.RISK_AGENT_COOLDOWN_SECONDS
        
        # Shared services
        self.portfolio_tracker = get_portfolio_tracker()
        self.price_service = get_optimized_price_service()
        self.data_coordinator = get_shared_data_coordinator()
        self.breakeven_manager = get_breakeven_manager()
        
        # AI model for analysis
        self.ai_model = None
        self._initialize_ai_model()
        
        # Ensure portfolio tracker has a snapshot for risk calculations
        self._ensure_portfolio_snapshot()
        
        info("🚨 [EMERGENCY] Risk Agent initialized successfully")
        if self.startup_mode_enabled:
            info(f"🚀 [STARTUP] Startup mode enabled - {self.startup_duration_seconds}s delay before activation")
    
    def _initialize_ai_model(self):
        """Initialize DeepSeek AI model for risk analysis"""
        try:
            # Use quiet mode to suppress verbose model factory output
            self.ai_model = create_model("deepseek", "deepseek-chat", quiet=True)
            if self.ai_model:
                info("✅ [SUCCESS] DeepSeek AI model initialized for risk analysis")
            else:
                error("❌ Failed to create DeepSeek AI model - risk agent cannot function without AI")
                raise Exception("DeepSeek AI model creation failed")
        except Exception as e:
            error(f"❌ Failed to initialize DeepSeek AI model: {e}")
            error("❌ Risk agent requires DeepSeek AI to function properly")
            raise Exception(f"DeepSeek AI initialization failed: {e}")
    
    def _ensure_portfolio_snapshot(self):
        """Ensure portfolio tracker has a snapshot for risk calculations"""
        try:
            if not self.portfolio_tracker.current_snapshot:
                info("Taking initial portfolio snapshot for risk agent...")
                self.portfolio_tracker._take_snapshot()
                if self.portfolio_tracker.current_snapshot:
                    info("✅ [SUCCESS] Portfolio snapshot created successfully")
                else:
                    warning("⚠️ Could not create portfolio snapshot - risk calculations may be limited")
            
            # Ensure required attributes exist
            if not hasattr(self.portfolio_tracker, 'peak_portfolio_value'):
                self.portfolio_tracker.peak_portfolio_value = 0.0
            if not hasattr(self.portfolio_tracker, 'last_risk_trigger'):
                self.portfolio_tracker.last_risk_trigger = 0
                
        except Exception as e:
            warning(f"Error ensuring portfolio snapshot: {e}")
    
    # =============================================================================
    # PORTFOLIO METRICS CALCULATION MODULE
    # =============================================================================
    
    def calculate_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate current portfolio metrics"""
        try:
            # Get current portfolio snapshot with fallback
            current_snapshot = self.portfolio_tracker.current_snapshot
            if not current_snapshot:
                # Try to trigger a snapshot if none exists
                info("No portfolio snapshot available, taking fresh snapshot...")
                self.portfolio_tracker._take_snapshot()
                current_snapshot = self.portfolio_tracker.current_snapshot
                
            if not current_snapshot:
                warning("No portfolio snapshot available - portfolio may be empty")
                return None
            
            # Calculate USDC and SOL reserves
            total_value = current_snapshot.total_value_usd
            usdc_balance = current_snapshot.usdc_balance
            sol_value = current_snapshot.sol_value_usd
            
            # Portfolio data is available and correct
            
            usdc_reserve_percent = (usdc_balance / total_value) if total_value > 0 else 0
            sol_reserve_percent = (sol_value / total_value) if total_value > 0 else 0
            
            # Calculate drawdown from peak and update peak value
            self._update_peak_portfolio_value(total_value)
            
            drawdown_percent = 0
            if self.peak_portfolio_value > 0:
                drawdown_percent = ((total_value - self.peak_portfolio_value) / self.peak_portfolio_value) * 100
            
            # Get consecutive losses
            consecutive_losses = self.get_consecutive_losses()
            
            # Get open positions with PnL
            open_positions = self._get_open_positions_with_pnl(current_snapshot)
            
            metrics = PortfolioMetrics(
                total_value_usd=total_value,
                usdc_reserve_percent=usdc_reserve_percent,
                sol_reserve_percent=sol_reserve_percent,
                drawdown_percent=drawdown_percent,
                consecutive_losses=consecutive_losses,
                peak_value=self.peak_portfolio_value,
                open_positions=open_positions
            )
            
            return metrics
            
        except Exception as e:
            error(f"Error calculating portfolio metrics: {e}")
            return None
    
    def get_consecutive_losses(self) -> int:
        """Get consecutive losses from execution tracker"""
        try:
            # Get recent execution history
            execution_tracker = get_execution_tracker()
            history = execution_tracker.get_executions(limit=20)
            if not history:
                return 0
            
            consecutive_losses = 0
            for execution in history:
                if execution.get('pnl_usd', 0) < 0:
                    consecutive_losses += 1
                else:
                    break  # Stop at first non-loss
            
            return consecutive_losses
            
        except Exception as e:
            error(f"Error getting consecutive losses: {e}")
            return 0
    
    def _get_open_positions_with_pnl(self, snapshot: PortfolioSnapshot) -> List[Dict[str, Any]]:
        """Get open positions with PnL calculations (excluding protected tokens)"""
        try:
            positions = []
            
            for token_address, position_data in snapshot.positions.items():
                # Handle both dict and float position data
                if isinstance(position_data, dict):
                    usd_value = position_data.get('value_usd', 0)
                else:
                    usd_value = float(position_data)
                
                if usd_value <= 0:
                    continue
                
                # Skip excluded tokens (USDC, SOL, staked SOL)
                if token_address in EXCLUDED_TOKENS:
                    debug(f"Skipping excluded token: {token_address[:8]}...")
                    continue
                
                # Get current price
                current_price = self.price_service.get_price(token_address)
                if not current_price:
                    continue
                
                # Get entry price from portfolio tracker
                entry_price = self.portfolio_tracker._get_entry_price(token_address)
                if not entry_price:
                    continue
                
                # Calculate PnL percentage
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
                
                positions.append({
                    'token_address': token_address,
                    'usd_value': usd_value,
                    'current_price': current_price,
                    'entry_price': entry_price,
                    'pnl_percent': pnl_percent,
                    'amount': usd_value / current_price
                })
            
            # Sort by PnL (worst first)
            positions.sort(key=lambda x: x['pnl_percent'])
            
            return positions
            
        except Exception as e:
            error(f"Error getting open positions with PnL: {e}")
            return []
    
    # =============================================================================
    # COOLDOWN MANAGEMENT
    # =============================================================================
    
    def is_in_cooldown(self) -> bool:
        """Check if risk agent is in cooldown period"""
        if self.last_action_time == 0:
            return False
        
        time_since_action = time.time() - self.last_action_time
        return time_since_action < self.cooldown_seconds
    
    def get_cooldown_remaining(self) -> int:
        """Get remaining cooldown time in seconds"""
        if not self.is_in_cooldown():
            return 0
        
        time_since_action = time.time() - self.last_action_time
        return max(0, int(self.cooldown_seconds - time_since_action))
    
    def set_cooldown(self):
        """Set cooldown after executing an action"""
        self.last_action_time = time.time()
        info(f"⏰ [COOLDOWN] Risk agent cooldown set for {self.cooldown_seconds} seconds")
    
    # =============================================================================
    # EMERGENCY TRIGGER DETECTION MODULE
    # =============================================================================
    
    def _is_in_startup_mode(self) -> bool:
        """Check if we're still in startup mode (first 2 minutes)"""
        if not self.startup_mode_enabled:
            return False
        
        elapsed_time = time.time() - self.startup_time
        return elapsed_time < self.startup_duration_seconds
    
    def _is_startup_portfolio_state(self, metrics: PortfolioMetrics) -> bool:
        """Check if portfolio state indicates startup scenario"""
        if not self.startup_mode_enabled:
            return False
        
        # Startup scenario: High SOL allocation (>95%) and low USDC (<5%)
        sol_percent = metrics.sol_reserve_percent
        usdc_percent = metrics.usdc_reserve_percent
        
        return (sol_percent >= self.startup_sol_threshold and 
                usdc_percent <= self.startup_usdc_threshold)
    
    def check_emergency_triggers(self, metrics: PortfolioMetrics) -> List[EmergencyTrigger]:
        """Check all 3 emergency trigger conditions with startup awareness"""
        triggers = []
        
        try:
            # Check if we're in startup mode
            if self._is_in_startup_mode():
                info("🚀 [STARTUP] Risk agent in startup mode - skipping emergency checks")
                return triggers
            
            # Check if portfolio state indicates startup scenario
            if self._is_startup_portfolio_state(metrics):
                info("🚀 [STARTUP] Portfolio in startup state (high SOL, low USDC) - skipping USDC reserve check")
                # Skip USDC reserve check for startup scenarios
            else:
                # Trigger 1: USDC Reserve Breach (normal operation)
                if metrics.usdc_reserve_percent < self.usdc_reserve_threshold:
                    triggers.append(EmergencyTrigger(
                        trigger_type="usdc_reserve",
                        severity="critical",
                        value=metrics.usdc_reserve_percent,
                        threshold=self.usdc_reserve_threshold,
                        description=f"USDC reserve {metrics.usdc_reserve_percent:.1%} below threshold {self.usdc_reserve_threshold:.1%}",
                        timestamp=datetime.now()
                    ))
            
            # Trigger 2: SOL Reserve Breach
            if metrics.sol_reserve_percent < self.sol_reserve_threshold:
                triggers.append(EmergencyTrigger(
                    trigger_type="sol_reserve",
                    severity="critical",
                    value=metrics.sol_reserve_percent,
                    threshold=self.sol_reserve_threshold,
                    description=f"SOL reserve {metrics.sol_reserve_percent:.1%} below threshold {self.sol_reserve_threshold:.1%}",
                    timestamp=datetime.now()
                ))
            
            # Trigger 3: Consecutive Loss Limit
            if metrics.consecutive_losses >= CONSECUTIVE_LOSS_LIMIT:
                triggers.append(EmergencyTrigger(
                    trigger_type="consecutive_losses",
                    severity="high",
                    value=metrics.consecutive_losses,
                    threshold=CONSECUTIVE_LOSS_LIMIT,
                    description=f"Consecutive losses {metrics.consecutive_losses} >= limit {CONSECUTIVE_LOSS_LIMIT}",
                    timestamp=datetime.now()
                ))
            
            # Trigger 4: Drawdown Limit
            if metrics.drawdown_percent <= DRAWDOWN_LIMIT_PERCENT:
                triggers.append(EmergencyTrigger(
                    trigger_type="drawdown",
                    severity="high",
                    value=metrics.drawdown_percent,
                    threshold=DRAWDOWN_LIMIT_PERCENT,
                    description=f"Drawdown {metrics.drawdown_percent:.1f}% <= limit {DRAWDOWN_LIMIT_PERCENT}%",
                    timestamp=datetime.now()
                ))
            
            return triggers
            
        except Exception as e:
            error(f"Error checking emergency triggers: {e}")
            return []
    
    # =============================================================================
    # MARKET SENTIMENT INTEGRATION MODULE
    # =============================================================================
    
    def get_market_sentiment(self) -> Optional[Dict[str, Any]]:
        """Get latest market sentiment data from aggregated_market_sentiment.csv"""
        try:
            if not ENABLE_AGGREGATED_SENTIMENT:
                return None
            
            filepath = os.path.join('src', 'data', 'charts', AGGREGATED_SENTIMENT_FILE)
            if not os.path.exists(filepath):
                warning("Aggregated sentiment file not found")
                return None
            
            df = pd.read_csv(filepath)
            if df.empty:
                warning("Aggregated sentiment file is empty")
                return None
            
            # Get the latest sentiment data
            latest_row = df.iloc[-1]
            
            # Check data freshness (skip if >1 hour old)
            timestamp = latest_row['timestamp']
            data_age_minutes = (time.time() - timestamp) / 60
            if data_age_minutes > 60:
                warning(f"Market sentiment data is stale ({data_age_minutes:.1f} minutes old)")
                return None
            
            sentiment_data = {
                'overall_sentiment': latest_row['overall_sentiment'],
                'sentiment_score': latest_row['sentiment_score'],
                'confidence': latest_row['confidence'],
                'total_tokens_analyzed': latest_row['total_tokens_analyzed'],
                'bullish_tokens': latest_row['bullish_tokens'],
                'bearish_tokens': latest_row['bearish_tokens'],
                'neutral_tokens': latest_row['neutral_tokens'],
                'timestamp': timestamp,
                'data_age_minutes': data_age_minutes
            }
            
            info(f"📊 Market sentiment: {sentiment_data['overall_sentiment']} (Score: {sentiment_data['sentiment_score']:.2f})")
            return sentiment_data
            
        except Exception as e:
            error(f"Error reading market sentiment: {e}")
            return None
    
    # =============================================================================
    # DEEPSEEK AI ANALYSIS MODULE
    # =============================================================================
    
    def analyze_risk_with_ai(self, triggers: List[EmergencyTrigger], metrics: PortfolioMetrics, 
                           market_sentiment: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze risk with DeepSeek AI using comprehensive context"""
        try:
            if not self.ai_model:
                error("❌ DeepSeek AI model not available - risk analysis cannot proceed")
                raise Exception("DeepSeek AI model required for risk analysis")
            
            # Prepare context for AI
            context = self._prepare_ai_context(triggers, metrics, market_sentiment)
            
            # Generate AI prompt
            prompt = self._generate_ai_prompt(context)
            
            # Get AI response
            response = self.ai_model.generate_response(
                system_prompt="You are Anarcho Capital's Emergency Risk Management Agent. Analyze portfolio risk and recommend protective actions.",
                user_content=prompt
            )
            
            # Parse AI response
            decision = self._parse_ai_response(response, context)
            
            # Display AI analysis
            self._display_ai_analysis(triggers, metrics, market_sentiment, decision)
            
            return decision
            
        except Exception as e:
            error(f"Error in AI risk analysis: {e}")
            return self._get_fallback_decision(triggers, metrics)
    
    def _prepare_ai_context(self, triggers: List[EmergencyTrigger], metrics: PortfolioMetrics, 
                          market_sentiment: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare comprehensive context for AI analysis"""
        
        # Add on-chain data for positions (info only, NOT triggers)
        onchain_summary = {}
        if metrics.open_positions:
            try:
                from src.agents.onchain_agent import get_onchain_agent
                agent = get_onchain_agent()
                if agent:
                    for pos in metrics.open_positions:
                        token_address = pos.get('token_address')
                        if token_address:
                            token_data = agent.get_token_data(token_address)
                            if token_data:
                                # Extract key metrics
                                onchain_summary[token_address] = {
                                    'liquidity_usd': token_data.get('liquidity_usd', 0),
                                    'trend': token_data.get('trend_signal', 'UNKNOWN'),
                                    'new_holders_24h': token_data.get('new_holders_24h', 0),
                                    'holder_growth_pct': token_data.get('holder_growth_pct', 0),
                                    'tx_count_24h': token_data.get('tx_count_24h', 0)
                                }
            except:
                pass  # Silently fail if onchain data unavailable
        
        return {
            'triggers': [
                {
                    'type': t.trigger_type,
                    'severity': t.severity,
                    'value': t.value,
                    'threshold': t.threshold,
                    'description': t.description
                } for t in triggers
            ],
            'portfolio': {
                'total_value_usd': metrics.total_value_usd,
                'usdc_reserve_percent': metrics.usdc_reserve_percent,
                'sol_reserve_percent': metrics.sol_reserve_percent,
                'drawdown_percent': metrics.drawdown_percent,
                'consecutive_losses': metrics.consecutive_losses,
                'peak_value': metrics.peak_value,
                'open_positions_count': len(metrics.open_positions)
            },
            'positions': metrics.open_positions[:10],  # Top 10 worst positions
            'onchain_summary': onchain_summary,
            'market_sentiment': market_sentiment,
            'thresholds': {
                'usdc_reserve': self.usdc_reserve_threshold,
                'sol_reserve': self.sol_reserve_threshold,
                'consecutive_loss_limit': CONSECUTIVE_LOSS_LIMIT,
                'drawdown_limit': DRAWDOWN_LIMIT_PERCENT
            }
        }
    
    def _generate_ai_prompt(self, context: Dict[str, Any]) -> str:
        """Generate comprehensive AI prompt for risk analysis"""
        triggers = context['triggers']
        portfolio = context['portfolio']
        positions = context['positions']
        market_sentiment = context.get('market_sentiment')
        thresholds = context['thresholds']
        
        prompt = f"""EMERGENCY TRIGGER DETECTED: {', '.join([t['type'] for t in triggers])}

PORTFOLIO STATE:
- Total Value: ${portfolio['total_value_usd']:,.2f}
- USDC Reserve: {portfolio['usdc_reserve_percent']:.1%} (Target: {thresholds['usdc_reserve']:.1%})
- SOL Reserve: {portfolio['sol_reserve_percent']:.1%} (Target: {thresholds['sol_reserve']:.1%})
- Drawdown: {portfolio['drawdown_percent']:.1f}% (Limit: {thresholds['drawdown_limit']}%)
- Consecutive Losses: {portfolio['consecutive_losses']} (Limit: {thresholds['consecutive_loss_limit']})
- Open Positions: {portfolio['open_positions_count']}

TRIGGERS DETECTED:
"""
        
        for trigger in triggers:
            prompt += f"- {trigger['type'].upper()}: {trigger['description']} (Severity: {trigger['severity']})\n"
        
        if market_sentiment:
            prompt += f"""
MARKET SENTIMENT:
- Overall: {market_sentiment['overall_sentiment']}
- Score: {market_sentiment['sentiment_score']}/100
- Confidence: {market_sentiment['confidence']:.1f}%
- Bullish Tokens: {market_sentiment['bullish_tokens']} | Bearish Tokens: {market_sentiment['bearish_tokens']}
- Data Age: {market_sentiment['data_age_minutes']:.1f} minutes
"""
        else:
            prompt += "\nMARKET SENTIMENT: No data available\n"
        
        if positions:
            prompt += "\nOPEN POSITIONS (Worst to Best):\n"
            onchain_summary = context.get('onchain_summary', {})
            for pos in positions[:5]:  # Show top 5 worst
                token_address = pos.get('token_address')
                onchain = onchain_summary.get(token_address, {})
                
                if onchain:
                    liquidity = onchain.get('liquidity_usd', 0)
                    if liquidity >= 1e6:
                        liquidity_str = f"${liquidity/1e6:.2f}M"
                    elif liquidity >= 1e3:
                        liquidity_str = f"${liquidity/1e3:.0f}K"
                    else:
                        liquidity_str = f"${liquidity:.0f}"
                    
                    trend = onchain.get('trend', 'UNKNOWN')
                    holders = onchain.get('new_holders_24h', 0)
                    txs = onchain.get('tx_count_24h', 0)
                    prompt += f"- {token_address[:8]}... | PnL: {pos['pnl_percent']:.1f}% | Liq: {liquidity_str} | Trend: {trend} | Holders: {holders:+d} | Txs: {txs:,}\n"
                else:
                    prompt += f"- {token_address[:8]}... | PnL: {pos['pnl_percent']:.1f}% | Value: ${pos['usd_value']:.2f}\n"
        
        prompt += f"""
CONTEXT:
- In bearish markets: Be MORE aggressive with risk protection
- In bullish markets: Consider if drawdown is temporary market dip
- High consecutive losses in bullish market = strategy failing
- Low USDC in bearish market = CRITICAL emergency

HIERARCHY OF ACTIONS:
1. SOFT_HALT: Pause new buys only
2. SELECTIVE_CLOSE: Close worst performers (by loss %)
3. PARTIAL_CLOSE: Reduce all by 30-50%
4. BREAKEVEN_STOPS: Activate breakeven strategy
5. FULL_LIQUIDATION: Close everything except USDC/SOL
6. SYSTEM_HALT: Emergency shutdown requiring manual intervention

Recommend the appropriate action and explain your reasoning considering market sentiment and portfolio state.
Respond in this exact format:
ACTION: [one of the 6 actions above]
CONFIDENCE: [0-100]
REASONING: [detailed explanation of your decision]
"""
        
        return prompt
    
    def _parse_ai_response(self, response, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AI response into structured decision"""
        try:
            # Handle ModelResponse object
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            lines = response_text.strip().split('\n')
            action = "SOFT_HALT"  # Default
            confidence = 50
            reasoning = "AI analysis failed, using default action"
            
            for line in lines:
                if line.startswith("ACTION:"):
                    action = line.replace("ACTION:", "").strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = int(line.replace("CONFIDENCE:", "").strip())
                    except:
                        confidence = 50
                elif line.startswith("REASONING:"):
                    reasoning = line.replace("REASONING:", "").strip()
            
            return {
                'action': action,
                'confidence': confidence,
                'reasoning': reasoning,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            error(f"Error parsing AI response: {e}")
            return {
                'action': 'SOFT_HALT',
                'confidence': 50,
                'reasoning': f"Error parsing AI response: {e}",
                'timestamp': datetime.now()
            }
    
    def _get_fallback_decision(self, triggers: List[EmergencyTrigger], metrics: PortfolioMetrics) -> Dict[str, Any]:
        """Get fallback decision when AI is not available"""
        # Simple rule-based fallback
        critical_triggers = [t for t in triggers if t.severity == "critical"]
        high_triggers = [t for t in triggers if t.severity == "high"]
        
        if critical_triggers:
            return {
                'action': 'FULL_LIQUIDATION',
                'confidence': 90,
                'reasoning': f"Critical triggers detected: {[t.trigger_type for t in critical_triggers]}",
                'timestamp': datetime.now()
            }
        elif high_triggers:
            return {
                'action': 'SELECTIVE_CLOSE',
                'confidence': 75,
                'reasoning': f"High severity triggers detected: {[t.trigger_type for t in high_triggers]}",
                'timestamp': datetime.now()
            }
        else:
            return {
                'action': 'SOFT_HALT',
                'confidence': 60,
                'reasoning': "Minor triggers detected, implementing soft halt",
                'timestamp': datetime.now()
            }
    
    def _display_ai_analysis(self, triggers: List[EmergencyTrigger], metrics: PortfolioMetrics, 
                           market_sentiment: Optional[Dict[str, Any]], decision: Dict[str, Any]):
        """Display AI analysis in clean INFO format like CopyBot"""
        info(f"🎯 [AI] Risk Analysis - Trigger: {', '.join([t.trigger_type for t in triggers])}")
        info(f"📊 [AI] Portfolio: ${metrics.total_value_usd:,.2f} | USDC: {metrics.usdc_reserve_percent:.1%} | SOL: {metrics.sol_reserve_percent:.1%}")
        info(f"📈 [AI] Drawdown: {metrics.drawdown_percent:.1f}% | Losses: {metrics.consecutive_losses}")
        
        if market_sentiment:
            info(f"📊 [AI] Sentiment: {market_sentiment['overall_sentiment']} (Score: {market_sentiment['sentiment_score']:.1f}/100)")
        
        if metrics.open_positions:
            worst_pos = metrics.open_positions[0]
            info(f"📉 [AI] Worst Position: {worst_pos['token_address'][:8]}... | PnL: {worst_pos['pnl_percent']:.1f}%")
        
        info(f"🤖 [AI] Decision: {decision['action']} (Confidence: {decision['confidence']}%)")
        info(f"💭 [AI] Reasoning: {decision['reasoning'][:100]}...")
    
    # =============================================================================
    # EMERGENCY ACTION EXECUTION MODULE
    # =============================================================================
    
    def execute_emergency_action(self, action: str, metrics: PortfolioMetrics) -> bool:
        """Execute the recommended emergency action"""
        try:
            info(f"[EMERGENCY] Executing emergency action: {action}")
            
            if action == "SOFT_HALT":
                return self.execute_soft_halt()
            elif action == "SELECTIVE_CLOSE":
                return self.execute_selective_close(metrics)
            elif action == "PARTIAL_CLOSE":
                return self.execute_partial_close(0.4)  # 40% reduction
            elif action == "BREAKEVEN_STOPS":
                return self.execute_breakeven_stops()
            elif action == "FULL_LIQUIDATION":
                return self.execute_full_liquidation()
            elif action == "SYSTEM_HALT":
                return self.execute_system_halt()
            else:
                warning(f"Unknown action: {action}")
                return False
                
        except Exception as e:
            error(f"Error executing emergency action {action}: {e}")
            return False
    
    def execute_soft_halt(self) -> bool:
        """Pause all new buy orders"""
        try:
            # Set halt flag in config
            config.COPYBOT_HALT_BUYS = True
            info("⏸️ Soft halt executed - new buys paused")
            return True
        except Exception as e:
            error(f"Error executing soft halt: {e}")
            return False
    
    def execute_selective_close(self, metrics: PortfolioMetrics) -> bool:
        """Close worst performing positions"""
        try:
            info("🎯 Executing selective close - targeting worst performers")
            
            # Sort positions by PnL (worst first)
            worst_positions = sorted(metrics.open_positions, key=lambda x: x['pnl_percent'])
            
            closed_count = 0
            target_usdc_percent = 0.15  # Target 15% USDC after closing
            
            for position in worst_positions:
                if metrics.usdc_reserve_percent >= target_usdc_percent:
                    break
                
                # Close this position
                success = self._close_position(position['token_address'], position['amount'])
                if success:
                    closed_count += 1
                    info(f"[SUCCESS] Closed position: {position['token_address'][:8]}... (PnL: {position['pnl_percent']:.1f}%)")
                else:
                    warning(f"❌ Failed to close position: {position['token_address'][:8]}...")
            
            info(f"✅ Selective close completed - closed {closed_count} positions")
            return closed_count > 0
            
        except Exception as e:
            error(f"Error executing selective close: {e}")
            return False
    
    def execute_partial_close(self, percentage: float) -> bool:
        """Close specified percentage of all positions (excluding protected tokens)"""
        try:
            info(f"📉 Executing partial close - reducing all positions by {percentage:.1%}")
            
            current_snapshot = self.portfolio_tracker.current_snapshot
            if not current_snapshot:
                warning("No portfolio snapshot available for partial close")
                return False
            
            closed_count = 0
            for token_address, position_data in current_snapshot.positions.items():
                # Handle both dict and float position data
                if isinstance(position_data, dict):
                    usd_value = position_data.get('value_usd', 0)
                else:
                    usd_value = float(position_data)
                
                if usd_value <= 0:
                    continue
                
                # Skip excluded tokens (USDC, SOL, staked SOL)
                if token_address in EXCLUDED_TOKENS:
                    debug(f"Skipping excluded token in partial close: {token_address[:8]}...")
                    continue
                
                # Calculate amount to close
                amount_to_close = usd_value * percentage
                current_price = self.price_service.get_price(token_address)
                if not current_price:
                    continue
                
                amount_tokens = amount_to_close / current_price
                
                # Close partial position
                success = self._close_position(token_address, amount_tokens)
                if success:
                    closed_count += 1
                    info(f"[SUCCESS] Partially closed: {token_address[:8]}... (${amount_to_close:.2f})")
            
            info(f"✅ Partial close completed - reduced {closed_count} positions")
            return closed_count > 0
            
        except Exception as e:
            error(f"Error executing partial close: {e}")
            return False
    
    def execute_breakeven_stops(self) -> bool:
        """Activate breakeven strategy"""
        try:
            info("[STOP]� Executing breakeven stops strategy")
            
            # Use existing breakeven manager
            results = self.breakeven_manager.execute_breakeven_strategy(self.price_service)
            
            if results:
                info(f"[STOP]� Breakeven strategy executed - {results}")
                return True
            else:
                warning("[STOP]� Breakeven strategy returned no results")
                return False
                
        except Exception as e:
            error(f"Error executing breakeven stops: {e}")
            return False
    
    def execute_full_liquidation(self) -> bool:
        """Close all positions except excluded tokens (USDC, SOL, staked SOL)"""
        try:
            info("🚨 Executing full liquidation - closing all positions except protected tokens")
            
            current_snapshot = self.portfolio_tracker.current_snapshot
            if not current_snapshot:
                warning("No portfolio snapshot available for liquidation")
                return False
            
            closed_count = 0
            for token_address, position_data in current_snapshot.positions.items():
                # Handle both dict and float position data
                if isinstance(position_data, dict):
                    usd_value = position_data.get('value_usd', 0)
                else:
                    usd_value = float(position_data)
                
                if usd_value <= 0:
                    continue
                
                # Skip excluded tokens (USDC, SOL, staked SOL)
                if token_address in EXCLUDED_TOKENS:
                    debug(f"Protecting excluded token from liquidation: {token_address[:8]}...")
                    continue
                
                # Close entire position
                current_price = self.price_service.get_price(token_address)
                if not current_price:
                    continue
                
                amount_tokens = usd_value / current_price
                success = self._close_position(token_address, amount_tokens)
                if success:
                    closed_count += 1
                    info(f"[SUCCESS] Liquidated: {token_address[:8]}... (${usd_value:.2f})")
            
            info(f"✅ Full liquidation completed - closed {closed_count} positions")
            return closed_count > 0
            
        except Exception as e:
            error(f"Error executing full liquidation: {e}")
            return False
    
    def execute_system_halt(self) -> bool:
        """Emergency shutdown - liquidate all positions and stop CopyBot"""
        try:
            info("[EMERGENCY] Executing system halt - emergency shutdown")
            
            # 1. Liquidate all positions first
            liquidation_success = self.execute_full_liquidation()
            if not liquidation_success:
                warning("Full liquidation failed or had no positions to close")
            
            # 2. Stop CopyBot completely
            config.COPYBOT_ENABLED = False
            config.COPYBOT_HALT_BUYS = True
            config.COPYBOT_STOP_ALL = True
            
            # 3. Set manual review required flag
            self.requires_manual_review = True
            
            info("[EMERGENCY] System halt completed - all positions liquidated, CopyBot stopped")
            info("[EMERGENCY] MANUAL REVIEW REQUIRED - Use force_clear_all_halts() to restart")
            return True
            
        except Exception as e:
            error(f"Error executing system halt: {e}")
            return False
    
    def _close_position(self, token_address: str, amount: float) -> bool:
        """Close a position using the trading system"""
        try:
            info(f"🔄 Closing position: {token_address[:8]}... (amount: {amount:.6f})")
            
            # Import trading modules
            from src.scripts.database.execution_tracker import get_execution_tracker
            from src import config
            
            # Get current price
            current_price = self.price_service.get_price(token_address)
            if not current_price:
                error(f"Could not get price for {token_address[:8]}...")
                return False
            
            # Calculate USD value
            usd_value = amount * current_price
            
            # Execute the sell order based on trading mode
            if getattr(config, "PAPER_TRADING_ENABLED", True):
                # Paper trading mode - use paper_trading module
                try:
                    from src import paper_trading
                    success = paper_trading.execute_paper_trade(
                        token_address=token_address,
                        action="SELL",
                        amount=amount,
                        price=current_price,
                        agent="risk_agent"
                    )
                except Exception as e:
                    error(f"Paper trading sell failed for {token_address[:8]}...: {e}")
                    success = False
            else:
                # Live trading mode - use nice_funcs sell_token helper
                try:
                    from src import nice_funcs as n
                    success = n.sell_token(token_address, amount, config.slippage)
                except Exception as e:
                    error(f"Live trading sell failed for {token_address[:8]}...: {e}")
                    success = False
            
            if success:
                # Track the execution
                execution_tracker = get_execution_tracker()
                execution_data = {
                    'action': 'SELL',
                    'token_address': token_address,
                    'amount': amount,
                    'price': current_price,
                    'value_usd': usd_value,
                    'reason': 'Risk management - emergency action',
                    'agent': 'risk_agent',
                    'timestamp': datetime.now().isoformat()
                }
                
                execution_tracker.record_execution(execution_data)
                info(f"[SUCCESS] Closed position: {token_address[:8]}... (${usd_value:.2f})")
                return True
            else:
                error(f"❌ [FAILED] Could not close position: {token_address[:8]}...")
                return False
            
        except Exception as e:
            error(f"Error closing position {token_address}: {e}")
            return False
    
    # =============================================================================
    # HYBRID MONITORING SYSTEM
    # =============================================================================
    
    def on_portfolio_change(self, current_snapshot: PortfolioSnapshot, previous_snapshot: PortfolioSnapshot):
        """Event-driven trigger from portfolio tracker"""
        try:
            if not self.enabled:
                return
            
            # Calculate metrics
            metrics = self.calculate_portfolio_metrics()
            if not metrics:
                return
            
            # Check for triggers
            triggers = self.check_emergency_triggers(metrics)
            if not triggers:
                return
            
            # Get market sentiment
            market_sentiment = self.get_market_sentiment()
            
            # Analyze with AI
            decision = self.analyze_risk_with_ai(triggers, metrics, market_sentiment)
            
            # Execute action
            success = self.execute_emergency_action(decision['action'], metrics)
            
            if success:
                self.emergency_actions_taken.append({
                    'timestamp': datetime.now(),
                    'triggers': [t.trigger_type for t in triggers],
                    'action': decision['action'],
                    'confidence': decision['confidence']
                })
                
                # Set cooldown after successful action
                self.set_cooldown()
            
        except Exception as e:
            error(f"Error in portfolio change handler: {e}")
    
    def _interval_risk_check(self):
        """Interval-based risk check (failsafe)"""
        try:
            if not self.enabled:
                return
            
            # Check cooldown first
            if self.is_in_cooldown():
                remaining = self.get_cooldown_remaining()
                debug(f"⏰ [COOLDOWN] Risk agent in cooldown for {remaining} more seconds")
                return
            
            # Calculate metrics
            metrics = self.calculate_portfolio_metrics()
            if not metrics:
                return
            
            # Check for triggers
            triggers = self.check_emergency_triggers(metrics)
            if not triggers:
                return
            
            info(f"🚨 [EMERGENCY] Interval check detected {len(triggers)} emergency triggers")
            
            # Get market sentiment
            market_sentiment = self.get_market_sentiment()
            
            # Analyze with AI
            decision = self.analyze_risk_with_ai(triggers, metrics, market_sentiment)
            
            # Execute action
            success = self.execute_emergency_action(decision['action'], metrics)
            
            if success:
                self.emergency_actions_taken.append({
                    'timestamp': datetime.now(),
                    'triggers': [t.trigger_type for t in triggers],
                    'action': decision['action'],
                    'confidence': decision['confidence']
                })
                
                # Set cooldown after successful action
                self.set_cooldown()
            
        except Exception as e:
            error(f"Error in interval risk check: {e}")
    
    def start(self):
        """Start the emergency risk agent"""
        try:
            if self.is_running:
                warning("Emergency risk agent is already running")
                return
            
            self.is_running = True
            
            # Start interval monitoring thread
            self.thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.thread.start()
            
            # Schedule immediate check after startup mode expires
            def delayed_startup_check():
                startup_buffer = 5  # 5 second buffer after startup mode expires
                startup_wait_time = self.startup_duration_seconds + startup_buffer
                info(f"🚀 [STARTUP] Scheduling immediate risk check in {startup_wait_time} seconds")
                time.sleep(startup_wait_time)
                
                if self.is_running:  # Only check if agent is still running
                    info("🚀 [STARTUP] Executing immediate post-startup risk check")
                    self._interval_risk_check()
            
            # Start delayed startup check in separate thread
            startup_thread = threading.Thread(target=delayed_startup_check, daemon=True)
            startup_thread.start()
            
            # Subscribe to portfolio tracker events
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            portfolio_tracker = get_portfolio_tracker()
            if portfolio_tracker:
                # Register this agent for portfolio change events
                portfolio_tracker.register_risk_agent(self)
                info("✅ [SUCCESS] Risk agent registered with portfolio tracker")
            else:
                warning("⚠️ Portfolio tracker not available for event registration")
            
            info("🚨 [EMERGENCY] Risk agent started with hybrid monitoring (60min intervals + events + post-startup check)")
            
        except Exception as e:
            error(f"Error starting emergency risk agent: {e}")
            self.is_running = False
    
    def stop(self):
        """Stop the emergency risk agent"""
        try:
            self.is_running = False
            
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            
            info("[EMERGENCY] Emergency risk agent stopped")
            
        except Exception as e:
            error(f"Error stopping emergency risk agent: {e}")
    
    def _monitoring_loop(self):
        """Main monitoring loop for interval-based checks"""
        while self.is_running:
            try:
                self._interval_risk_check()
                time.sleep(self.check_interval_minutes * 60)
            except Exception as e:
                error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            'enabled': self.enabled,
            'is_running': self.is_running,
            'check_interval_minutes': self.check_interval_minutes,
            'peak_portfolio_value': self.peak_portfolio_value,
            'emergency_actions_taken': len(self.emergency_actions_taken),
            'last_action': self.emergency_actions_taken[-1] if self.emergency_actions_taken else None
        }

    # =============================================================================
    # INTEGRATION METHODS FOR SYSTEM COMPATIBILITY
    # =============================================================================
    
    def check_emergency_conditions(self):
        """Check emergency conditions - called by portfolio tracker"""
        try:
            # First check if we should auto-clear flags due to improved conditions
            if self.check_auto_recovery_conditions():
                return  # Flags cleared, no need to check emergency conditions
            
            # Check cooldown first
            if self.is_in_cooldown():
                remaining = self.get_cooldown_remaining()
                debug(f"⏰ [COOLDOWN] Risk agent in cooldown for {remaining} more seconds")
                return
            
            info("🚨 [EMERGENCY] Checking emergency conditions...")
            
            # Calculate metrics
            metrics = self.calculate_portfolio_metrics()
            if not metrics:
                warning("No portfolio metrics available for emergency check")
                return
            
            # Check for triggers
            triggers = self.check_emergency_triggers(metrics)
            if not triggers:
                debug("No emergency triggers detected")
                return
            
            info(f"🚨 [EMERGENCY] Triggers detected: {len(triggers)}")
            for trigger in triggers:
                info(f"  - {trigger.description}")
            
            # Get market sentiment
            market_sentiment = self.get_market_sentiment()
            
            # Analyze with AI
            decision = self.analyze_risk_with_ai(triggers, metrics, market_sentiment)
            
            # Execute action
            success = self.execute_emergency_action(decision['action'], metrics)
            
            if success:
                self.emergency_actions_taken.append({
                    'timestamp': datetime.now(),
                    'triggers': [t.trigger_type for t in triggers],
                    'action': decision['action'],
                    'confidence': decision['confidence']
                })
                
                # Set cooldown after successful action
                self.set_cooldown()
                
                # Set CopyBot control flags based on action
                if decision['action'] in ['FULL_LIQUIDATION', 'SYSTEM_HALT']:
                    self._set_copybot_stop_reason(f"Emergency action: {decision['action']}")
                elif decision['action'] in ['SOFT_HALT', 'SELECTIVE_CLOSE', 'PARTIAL_CLOSE']:
                    self._set_copybot_halt_reason(f"Risk management: {decision['action']}")
            
        except Exception as e:
            error(f"Error in check_emergency_conditions: {e}")
    
    @property
    def copybot_stop_reason(self):
        """Reason why CopyBot is stopped"""
        return getattr(self, '_copybot_stop_reason', None)
    
    @property  
    def copybot_halt_reason(self):
        """Reason why CopyBot is halted"""
        return getattr(self, '_copybot_halt_reason', None)
    
    def _set_copybot_stop_reason(self, reason: str):
        """Set CopyBot stop reason"""
        self._copybot_stop_reason = reason
        info(f"🛑 CopyBot stop reason set: {reason}")
    
    def _set_copybot_halt_reason(self, reason: str):
        """Set CopyBot halt reason"""
        self._copybot_halt_reason = reason
        info(f"⏸️ CopyBot halt reason set: {reason}")
    
    def clear_copybot_flags(self):
        """Clear CopyBot control flags"""
        self._copybot_stop_reason = None
        self._copybot_halt_reason = None
        
        # Clear config halt flags
        config.COPYBOT_HALT_BUYS = False
        config.COPYBOT_STOP_ALL = False
        
        info("🔄 CopyBot control flags cleared")
    
    def force_clear_all_halts(self):
        """Force clear all halt flags - for testing and emergency recovery"""
        try:
            # Clear instance variables
            self._copybot_stop_reason = None
            self._copybot_halt_reason = None
            self.requires_manual_review = False
            
            # Clear config flags
            config.COPYBOT_HALT_BUYS = False
            config.COPYBOT_STOP_ALL = False
            
            # Re-enable CopyBot if it was disabled
            config.COPYBOT_ENABLED = True
            
            # Clear cooldown
            self.last_action_time = 0
            
            info("🚨 FORCE CLEAR: All halt flags cleared, CopyBot re-enabled")
            return True
            
        except Exception as e:
            error(f"Error force clearing halts: {e}")
            return False
    
    def check_auto_recovery_conditions(self) -> bool:
        """Check if conditions have improved enough to auto-clear halt flags"""
        try:
            # Skip if manual review is required (SYSTEM_HALT)
            if getattr(self, 'requires_manual_review', False):
                debug("Manual review required - skipping auto-recovery")
                return False
            
            # Skip if no flags are set
            if not self.copybot_stop_reason and not self.copybot_halt_reason:
                return False
            
            # Get current portfolio metrics
            metrics = self.calculate_portfolio_metrics()
            if not metrics:
                return False
            
            # Check if we're still in cooldown
            if self.is_in_cooldown():
                return False
            
            # Recovery conditions for different halt types
            recovery_conditions = []
            
            # 1. USDC balance recovery
            usdc_percent = metrics.usdc_reserve_percent
            if usdc_percent >= AUTO_RECOVERY_USDC_THRESHOLD:
                recovery_conditions.append("USDC balance recovered")
            
            # 2. SOL balance recovery
            sol_percent = metrics.sol_reserve_percent
            if sol_percent >= AUTO_RECOVERY_SOL_THRESHOLD:
                recovery_conditions.append("SOL balance recovered")
            
            # 3. Drawdown improvement
            if metrics.drawdown_percent < AUTO_RECOVERY_DRAWDOWN_THRESHOLD:
                recovery_conditions.append("Drawdown improved")
            
            # 4. Portfolio value recovery (back to 90% of peak)
            if metrics.total_value_usd >= (self.peak_portfolio_value * AUTO_RECOVERY_PORTFOLIO_RECOVERY):
                recovery_conditions.append("Portfolio value recovered")
            
            # Require minimum conditions to auto-clear
            if len(recovery_conditions) >= AUTO_RECOVERY_MIN_CONDITIONS:
                info(f"🔄 [AUTO-RECOVERY] Conditions improved: {', '.join(recovery_conditions)}")
                self.clear_copybot_flags()
                return True
            
            return False
            
        except Exception as e:
            error(f"Error checking auto-recovery conditions: {e}")
            return False
    
    def _update_peak_portfolio_value(self, current_value: float):
        """Update peak portfolio value for recovery calculations"""
        if current_value > self.peak_portfolio_value:
            self.peak_portfolio_value = current_value
            info(f"📈 [AUTO-RECOVERY] New peak portfolio value: ${current_value:,.2f}")
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics for dashboard/health checks"""
        try:
            metrics = self.calculate_portfolio_metrics()
            if not metrics:
                return {
                    'status': 'error',
                    'message': 'No portfolio metrics available'
                }
            
            triggers = self.check_emergency_triggers(metrics)
            
            return {
                'status': 'active',
                'enabled': self.enabled,
                'is_running': self.is_running,
                'portfolio_metrics': {
                    'total_value_usd': metrics.total_value_usd,
                    'usdc_reserve_percent': metrics.usdc_reserve_percent,
                    'sol_reserve_percent': metrics.sol_reserve_percent,
                    'drawdown_percent': metrics.drawdown_percent,
                    'consecutive_losses': metrics.consecutive_losses,
                    'peak_value': metrics.peak_value,
                    'open_positions_count': len(metrics.open_positions)
                },
                'triggers': [
                    {
                        'type': t.trigger_type,
                        'severity': t.severity,
                        'value': t.value,
                        'threshold': t.threshold,
                        'description': t.description
                    } for t in triggers
                ],
                'copybot_control': {
                    'stop_reason': self.copybot_stop_reason,
                    'halt_reason': self.copybot_halt_reason
                },
                'emergency_actions_taken': len(self.emergency_actions_taken),
                'last_action': self.emergency_actions_taken[-1] if self.emergency_actions_taken else None
            }
            
        except Exception as e:
            error(f"Error getting risk metrics: {e}")
            return {
                'status': 'error',
                'message': f'Error getting risk metrics: {e}'
            }


# =============================================================================
# SINGLETON PATTERN
# =============================================================================

# Global singleton instance
_risk_agent = None

def get_risk_agent() -> 'RiskAgent':
    """Get the singleton risk agent instance"""
    global _risk_agent
    if _risk_agent is None:
        try:
            _risk_agent = RiskAgent()
            info("✅ [SUCCESS] Risk agent singleton created successfully")
        except Exception as e:
            error(f"❌ Failed to create risk agent singleton: {e}")
            return None
    return _risk_agent

def get_risk_agent() -> 'RiskAgent':
    """Get the singleton risk agent instance"""
    global _risk_agent
    if _risk_agent is None:
        try:
            _risk_agent = RiskAgent()
        except Exception as e:
            error(f" Failed to create risk agent singleton: {e}")
            return None
    return _risk_agent


