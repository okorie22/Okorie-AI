"""
👑 ITORO Master Agent - Supreme Asset Manager & Orchestrator
Monitors system performance, adapts strategies, and optimizes configs to achieve PnL goals
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.agents.base_agent import BaseAgent
from src.scripts.shared_services.logger import info, warning, error, debug
from src.scripts.shared_services.config_manager import get_config_manager
from src.scripts.shared_services.performance_monitor import get_performance_monitor
from src.scripts.trading.master_agent_ai import get_master_agent_ai


class MasterAgent(BaseAgent):
    """
    Master orchestrator for ITORO trading system
    Adaptive personality, intelligent optimization, goal-oriented management
    """
    
    def __init__(self):
        """Initialize the Master Agent"""
        super().__init__("master_agent")
        
        # Load agent configuration
        self.config = self._load_agent_config()
        
        # Initialize services
        self.config_manager = get_config_manager()
        self.performance_monitor = get_performance_monitor()
        self.ai = get_master_agent_ai()
        
        # Agent state
        self.personality_mode = self.config['config'][1]['personality_mode']  # BALANCED default
        self.monthly_pnl_goal_percent = self.config['config'][1]['monthly_pnl_target_percent']
        self.monitoring_interval = self.config['config'][1]['monitoring_interval_seconds']
        self.auto_adjust_data = self.config['config'][1]['auto_adjust_data_configs']
        self.require_approval_trading = self.config['config'][1]['require_approval_trading_configs']
        
        # Set PnL goal in performance monitor
        self.performance_monitor.set_monthly_pnl_goal(self.monthly_pnl_goal_percent)
        
        # Running state
        self.is_running = False
        self.thread = None
        
        # Decision tracking
        self.last_personality_change = None
        self.last_config_adjustment = None
        self.decisions_history = []
        
        # Performance tracking for rollback detection
        self.performance_checkpoints = []
        
        info(f"👑 Master Agent initialized in {self.personality_mode} mode")
        info(f"🎯 Monthly PnL goal: {self.monthly_pnl_goal_percent}%")
    
    def _load_agent_config(self) -> Dict[str, Any]:
        """Load agent configuration from JSON"""
        try:
            config_path = Path("agents/itoro_master.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
            else:
                error("Master agent config file not found")
                return self._get_default_config()
        except Exception as e:
            error(f"Error loading master agent config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'name': 'ItoroMasterAgent',
            'loop_delay': 1800,
            'config': [
                {'name': 'deepseek', 'model': 'deepseek-chat'},
                {
                    'name': 'master_agent',
                    'monthly_pnl_target_percent': 30.0,
                    'personality_mode': 'BALANCED',
                    'auto_adjust_data_configs': True,
                    'require_approval_trading_configs': True,
                    'monitoring_interval_seconds': 1800,
                    'performance_evaluation_interval_hours': 1,
                    'config_rollback_threshold_hours': 24,
                    'min_confidence_for_suggestions': 0.70
                }
            ]
        }
    
    def start(self):
        """Start the Master Agent monitoring loop"""
        if self.is_running:
            warning("Master Agent is already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.thread.start()
        
        info("👑 Master Agent monitoring loop started")
    
    def stop(self):
        """Stop the Master Agent"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        info("👑 Master Agent stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop for the Master Agent"""
        while self.is_running:
            try:
                # Run monitoring cycle
                self._execute_monitoring_cycle()
                
                # Sleep until next cycle
                time.sleep(self.monitoring_interval)
            
            except Exception as e:
                error(f"Error in Master Agent monitoring loop: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def _execute_monitoring_cycle(self):
        """Execute a complete monitoring cycle"""
        try:
            debug("👑 Master Agent: Starting monitoring cycle")
            
            # 1. Collect system health data
            health_summary = self.performance_monitor.get_system_health_summary()
            if not health_summary:
                warning("Unable to get system health summary")
                return
            
            # 2. Evaluate personality mode
            self._evaluate_personality_mode(health_summary)
            
            # 3. Check goal progress
            goal_progress = self.performance_monitor.get_goal_progress()
            if goal_progress:
                self._evaluate_goal_progress(goal_progress)
            
            # 4. Evaluate data quality
            data_quality = health_summary.get('data_quality')
            if data_quality:
                self._evaluate_data_quality(data_quality)
            
            # 5. Generate config recommendations
            self._generate_config_recommendations(health_summary)
            
            # 6. Check for rollback needs
            self._check_config_rollback_needs()
            
            # 7. Log decision
            self._log_monitoring_cycle(health_summary)
            
            debug("👑 Master Agent: Monitoring cycle completed")
        
        except Exception as e:
            error(f"Error in monitoring cycle: {e}")
    
    def _evaluate_personality_mode(self, health_summary: Dict[str, Any]):
        """Evaluate and potentially change personality mode"""
        try:
            performance = health_summary.get('performance')
            if not performance:
                return
            
            # Get market sentiment (from chart analysis if available)
            market_sentiment = self._get_market_sentiment()
            
            # Use AI to recommend personality mode
            recommended_mode, reasoning, confidence = self.ai.recommend_personality_mode(
                performance_data=performance,
                market_sentiment=market_sentiment
            )
            
            # Change mode if different and confidence is high enough
            if recommended_mode != self.personality_mode and confidence >= 0.7:
                old_mode = self.personality_mode
                self.personality_mode = recommended_mode
                self.last_personality_change = datetime.now()
                
                info(f"👑 Personality mode changed: {old_mode} → {recommended_mode}")
                info(f"   Reasoning: {reasoning}")
                info(f"   Confidence: {confidence:.2f}")
                
                # Log decision
                self.decisions_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'decision_type': 'personality_change',
                    'old_value': old_mode,
                    'new_value': recommended_mode,
                    'reasoning': reasoning,
                    'confidence': confidence
                })
        
        except Exception as e:
            error(f"Error evaluating personality mode: {e}")
    
    def _evaluate_goal_progress(self, goal_progress: Dict[str, Any]):
        """Evaluate progress toward PnL goal"""
        try:
            # Analyze gap between current and goal
            gap_analysis = self.ai.analyze_goal_gap(goal_progress)
            
            if gap_analysis:
                on_track = gap_analysis.get('on_track', False)
                gap_severity = gap_analysis.get('gap_severity', 'unknown')
                
                # Only show warning if we actually have data and are off track
                if not on_track and gap_severity not in ['none', 'unknown']:
                    warning(f"⚠️ Off track for PnL goal - Gap severity: {gap_severity}")
                    
                    # Log main blockers
                    blockers = gap_analysis.get('main_blockers', [])
                    if blockers:
                        warning(f"   Main blockers: {', '.join(blockers)}")
                    
                    # Consider recommended actions
                    actions = gap_analysis.get('recommended_actions', [])
                    for action in actions:
                        debug(f"   Recommended: {action.get('action')} (impact: {action.get('expected_impact_percent')}%)")
                elif on_track or gap_severity == 'none':
                    debug(f"✅ PnL goal tracking: {gap_severity if gap_severity == 'none' else 'On track'}")
                    # Show blockers as info if it's just insufficient data
                    blockers = gap_analysis.get('main_blockers', [])
                    if blockers and gap_severity == 'none':
                        debug(f"   Status: {', '.join(blockers)}")
        
        except Exception as e:
            error(f"Error evaluating goal progress: {e}")
    
    def _evaluate_data_quality(self, data_quality: Dict[str, Any]):
        """Evaluate data quality and adjust collection parameters if needed"""
        try:
            # Use AI to evaluate data quality issues
            evaluation = self.ai.evaluate_data_quality_issues(data_quality)
            
            if not evaluation:
                return
            
            quality_level = evaluation.get('overall_quality', 'unknown')
            critical_issues = evaluation.get('critical_issues', [])
            
            if critical_issues:
                warning(f"⚠️ Data quality issues detected: {quality_level}")
                for issue in critical_issues:
                    warning(f"   - {issue}")
            
            # Auto-adjust data collection configs if enabled
            if self.auto_adjust_data:
                adjustments = evaluation.get('recommended_adjustments', [])
                for adj in adjustments:
                    parameter = adj.get('parameter')
                    value = adj.get('recommended_value')
                    reasoning = adj.get('reasoning')
                    confidence = adj.get('confidence', 0.5)
                    
                    # Only apply if confidence is high enough
                    min_confidence = self.config['config'][1]['min_confidence_for_suggestions']
                    if confidence >= min_confidence:
                        success = self.config_manager.apply_change(
                            parameter=parameter,
                            new_value=value,
                            reason=reasoning,
                            agent="master_agent",
                            confidence=confidence
                        )
                        
                        if success:
                            self.last_config_adjustment = datetime.now()
        
        except Exception as e:
            error(f"Error evaluating data quality: {e}")
    
    def _check_suggestion_memory(self, parameter: str, value: Any) -> bool:
        """Check if we've already made this suggestion recently (avoid redundancy)"""
        try:
            memory_file = Path("src/data/master_agent/suggestion_memory.json")
            if not memory_file.exists():
                return False  # No memory, suggestion is new
            
            with open(memory_file, 'r') as f:
                memory = json.load(f)
            
            # Check if we suggested this exact change in the last 24 hours
            for entry in memory:
                if entry['parameter'] == parameter and entry['value'] == value:
                    suggestion_time = datetime.fromisoformat(entry['timestamp'])
                    age_hours = (datetime.now() - suggestion_time).total_seconds() / 3600
                    
                    if age_hours < 24:
                        debug(f"⏭️ Skipping redundant suggestion: {parameter} = {value} (suggested {age_hours:.1f}h ago)")
                        return True  # Already suggested recently
            
            return False  # New suggestion
        
        except Exception as e:
            error(f"Error checking suggestion memory: {e}")
            return False
    
    def _add_to_suggestion_memory(self, parameter: str, value: Any, category: str):
        """Add suggestion to memory to avoid redundancy"""
        try:
            memory_file = Path("src/data/master_agent/suggestion_memory.json")
            
            # Load existing memory
            memory = []
            if memory_file.exists():
                with open(memory_file, 'r') as f:
                    memory = json.load(f)
            
            # Add new entry
            memory.append({
                'timestamp': datetime.now().isoformat(),
                'parameter': parameter,
                'value': value,
                'category': category
            })
            
            # Keep only last 100 entries
            memory = memory[-100:]
            
            # Save
            with open(memory_file, 'w') as f:
                json.dump(memory, f, indent=2)
        
        except Exception as e:
            error(f"Error adding to suggestion memory: {e}")
    
    def _generate_config_recommendations(self, health_summary: Dict[str, Any]):
        """Generate configuration recommendations"""
        try:
            # Use AI to generate recommendations
            recommendations = self.ai.recommend_config_adjustments(
                health_summary=health_summary,
                personality_mode=self.personality_mode
            )
            
            if not recommendations:
                return
            
            min_confidence = self.config['config'][1]['min_confidence_for_suggestions']
            
            for rec in recommendations:
                parameter = rec.get('parameter')
                value = rec.get('value')
                category = rec.get('category', 'unknown')
                reasoning = rec.get('reasoning')
                confidence = rec.get('confidence', 0.5)
                
                # Skip low confidence recommendations
                if confidence < min_confidence:
                    continue
                
                # Check if we've made this suggestion recently (avoid redundancy)
                if self._check_suggestion_memory(parameter, value):
                    continue
                
                # For data configs: auto-apply if enabled
                if category == 'data' and self.auto_adjust_data:
                    success = self.config_manager.apply_change(
                        parameter=parameter,
                        new_value=value,
                        reason=reasoning,
                        agent="master_agent",
                        confidence=confidence
                    )
                    
                    if success:
                        self.last_config_adjustment = datetime.now()
                        self._add_to_suggestion_memory(parameter, value, category)
                
                # For trading configs: create suggestion (requires approval)
                elif category == 'trading':
                    self.config_manager.apply_change(
                        parameter=parameter,
                        new_value=value,
                        reason=reasoning,
                        agent="master_agent",
                        confidence=confidence
                    )
                    self._add_to_suggestion_memory(parameter, value, category)
        
        except Exception as e:
            error(f"Error generating config recommendations: {e}")
    
    def _check_config_rollback_needs(self):
        """Check if recent config changes need to be rolled back"""
        try:
            # Get recent changes (last 24 hours)
            recent_changes = self.config_manager.get_recent_changes(hours=24)
            
            if not recent_changes:
                return
            
            # Get performance before and after changes
            # (Simplified - would need more sophisticated tracking)
            current_performance = self.performance_monitor.calculate_current_performance()
            
            if not current_performance:
                return
            
            # Check if performance has degraded significantly
            # If consecutive losses increased or win rate dropped sharply
            if current_performance.consecutive_losses >= 7:
                warning("⚠️ Performance degradation detected - considering rollback")
                
                # Use AI to assess impact of changes
                # For now, simple heuristic: rollback data config changes if losses are high
                for change in recent_changes:
                    if change.category == 'data':
                        info(f"🔄 Rolling back {change.parameter} due to performance degradation")
                        self.config_manager.rollback_change(change.parameter)
        
        except Exception as e:
            error(f"Error checking rollback needs: {e}")
    
    def _get_market_sentiment(self) -> str:
        """Get current market sentiment from chart analysis"""
        try:
            # Try to read recent sentiment from files
            sentiment_file = Path("src/data/sentiment_history.csv")
            if sentiment_file.exists():
                # Read last line (most recent sentiment)
                with open(sentiment_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        last_line = lines[-1]
                        # Parse sentiment (simplified)
                        if 'bullish' in last_line.lower():
                            return 'bullish'
                        elif 'bearish' in last_line.lower():
                            return 'bearish'
            
            return 'neutral'
        except:
            return 'neutral'
    
    def _log_monitoring_cycle(self, health_summary: Dict[str, Any]):
        """Log the monitoring cycle results"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'personality_mode': self.personality_mode,
                'overall_health_score': health_summary.get('overall_health_score'),
                'goal_progress': health_summary.get('goal_progress'),
                'recent_decisions': len(self.decisions_history)
            }
            
            # Save to file
            log_file = Path("src/data/master_agent/monitoring_log.json")
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Append to log
            logs = []
            if log_file.exists():
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            
            logs.append(log_entry)
            
            # Keep only last 1000 entries
            logs = logs[-1000:]
            
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
        
        except Exception as e:
            error(f"Error logging monitoring cycle: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current Master Agent status"""
        return {
            'is_running': self.is_running,
            'personality_mode': self.personality_mode,
            'monthly_pnl_goal_percent': self.monthly_pnl_goal_percent,
            'last_personality_change': self.last_personality_change.isoformat() if self.last_personality_change else None,
            'last_config_adjustment': self.last_config_adjustment.isoformat() if self.last_config_adjustment else None,
            'total_decisions': len(self.decisions_history),
            'auto_adjust_data': self.auto_adjust_data,
            'require_approval_trading': self.require_approval_trading
        }
    
    def get_recent_decisions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent decisions made by the Master Agent"""
        return self.decisions_history[-limit:]
    
    def approve_trading_config(self, parameter: str) -> bool:
        """Approve a pending trading config suggestion"""
        try:
            success = self.config_manager.approve_suggestion(parameter)
            
            if success:
                info(f"✅ Approved trading config: {parameter}")
                
                # Log approval
                self.decisions_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'decision_type': 'config_approval',
                    'parameter': parameter,
                    'approved': True
                })
            
            return success
        
        except Exception as e:
            error(f"Error approving trading config: {e}")
            return False


# Singleton accessor
_master_agent = None

def get_master_agent() -> MasterAgent:
    """Get the global MasterAgent instance"""
    global _master_agent
    if _master_agent is None:
        _master_agent = MasterAgent()
    return _master_agent

