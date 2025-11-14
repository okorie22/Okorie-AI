#!/usr/bin/env python3
"""
🤖 Anarcho Capital's Agent Health Monitor
Comprehensive monitoring of all trading system agents
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class AgentStatus:
    """Agent status information"""
    name: str
    status: str  # 'running', 'stopped', 'error', 'unknown'
    last_execution: Optional[datetime]
    thread_active: bool
    cooldown_remaining: int  # seconds
    error_count: int
    success_count: int
    last_error: Optional[str]
    performance_metrics: Dict[str, Any]

class AgentHealthMonitor:
    """Monitor health of all trading system agents"""
    
    def __init__(self):
        self.agents = {}
        self.monitoring_active = False
        self.monitor_thread = None
        
    def get_agent_status(self, agent_name: str) -> Optional[AgentStatus]:
        """Get status of specific agent"""
        try:
            # Import agent modules dynamically
            if agent_name == 'risk_agent':
                return self._check_risk_agent()
            elif agent_name == 'copybot_agent':
                return self._check_copybot_agent()
            elif agent_name == 'harvesting_agent':
                return self._check_harvesting_agent()
            elif agent_name == 'staking_agent':
                return self._check_staking_agent()
            elif agent_name == 'sentiment_agent':
                return self._check_sentiment_agent()
            elif agent_name == 'chartanalysis_agent':
                return self._check_chart_analysis_agent()
            else:
                return None
        except Exception as e:
            return AgentStatus(
                name=agent_name,
                status='error',
                last_execution=None,
                thread_active=False,
                cooldown_remaining=0,
                error_count=1,
                success_count=0,
                last_error=str(e),
                performance_metrics={}
            )
    
    def _check_risk_agent(self) -> AgentStatus:
        """Check risk agent status"""
        try:
            from src.agents.risk_agent import RiskAgent
            
            # Try to get agent instance
            agent = RiskAgent()
            
            # Check if agent is running
            is_running = getattr(agent, 'is_running', False)
            thread_active = getattr(agent, 'thread', None) is not None and getattr(agent.thread, 'is_alive', lambda: False)()
            
            # Get last execution time
            last_execution = getattr(agent, 'last_check_time', None)
            if last_execution and last_execution > 0:
                last_execution = datetime.fromtimestamp(last_execution)
            else:
                last_execution = None
            
            # Calculate cooldown remaining
            cooldown_remaining = 0
            if last_execution:
                next_execution = last_execution + timedelta(minutes=getattr(agent, 'check_interval_minutes', 15))
                if next_execution > datetime.now():
                    cooldown_remaining = int((next_execution - datetime.now()).total_seconds())
            
            # Get performance metrics
            performance_metrics = {
                'consecutive_losses': getattr(agent, 'consecutive_losses', 0),
                'consecutive_wins': getattr(agent, 'consecutive_wins', 0),
                'peak_portfolio_value': getattr(agent, 'peak_portfolio_value', 0.0),
                'position_size_multiplier': getattr(agent, 'position_size_multiplier', 1.0),
                'emergency_stop_triggered': getattr(agent, 'emergency_stop_triggered', False)
            }
            
            status = 'running' if is_running and thread_active else 'stopped'
            if getattr(agent, 'emergency_stop_triggered', False):
                status = 'error'
            
            return AgentStatus(
                name='risk_agent',
                status=status,
                last_execution=last_execution,
                thread_active=thread_active,
                cooldown_remaining=cooldown_remaining,
                error_count=0,
                success_count=1 if is_running else 0,
                last_error=None,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return AgentStatus(
                name='risk_agent',
                status='error',
                last_execution=None,
                thread_active=False,
                cooldown_remaining=0,
                error_count=1,
                success_count=0,
                last_error=str(e),
                performance_metrics={}
            )
    
    def _check_copybot_agent(self) -> AgentStatus:
        """Check copybot agent status"""
        try:
            from src.agents.copybot_agent import CopyBotAgent
            
            # Try to get agent instance
            agent = CopyBotAgent()
            
            # Check if agent is running
            is_running = getattr(agent, 'is_running', False)
            thread_active = getattr(agent, 'thread', None) is not None and getattr(agent.thread, 'is_alive', lambda: False)()
            
            # Get last execution time
            last_execution = getattr(agent, 'last_check_time', None)
            if last_execution and last_execution > 0:
                last_execution = datetime.fromtimestamp(last_execution)
            else:
                last_execution = None
            
            # Calculate cooldown remaining
            cooldown_remaining = 0
            if last_execution:
                next_execution = last_execution + timedelta(minutes=getattr(agent, 'check_interval_minutes', 8))
                if next_execution > datetime.now():
                    cooldown_remaining = int((next_execution - datetime.now()).total_seconds())
            
            # Get performance metrics
            performance_metrics = {
                'tracked_wallets': len(getattr(agent, 'tracked_wallets', [])),
                'last_wallet_update': getattr(agent, 'last_wallet_update', None),
                'mirror_enabled': getattr(agent, 'mirror_enabled', False),
                'ai_analysis_enabled': getattr(agent, 'ai_analysis_enabled', False)
            }
            
            status = 'running' if is_running and thread_active else 'stopped'
            
            return AgentStatus(
                name='copybot_agent',
                status=status,
                last_execution=last_execution,
                thread_active=thread_active,
                cooldown_remaining=cooldown_remaining,
                error_count=0,
                success_count=1 if is_running else 0,
                last_error=None,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return AgentStatus(
                name='copybot_agent',
                status='error',
                last_execution=None,
                thread_active=False,
                cooldown_remaining=0,
                error_count=1,
                success_count=0,
                last_error=str(e),
                performance_metrics={}
            )
    
    def _check_harvesting_agent(self) -> AgentStatus:
        """Check harvesting agent status"""
        try:
            from src.agents.harvesting_agent import HarvestingAgent
            
            # Try to get agent instance
            agent = HarvestingAgent()
            
            # Check if agent is running
            is_running = getattr(agent, 'is_running', False)
            thread_active = getattr(agent, 'thread', None) is not None and getattr(agent.thread, 'is_alive', lambda: False)()
            
            # Get last execution time
            last_execution = getattr(agent, 'last_check_time', None)
            if last_execution and last_execution > 0:
                last_execution = datetime.fromtimestamp(last_execution)
            else:
                last_execution = None
            
            # Calculate cooldown remaining
            cooldown_remaining = 0
            if last_execution:
                next_execution = last_execution + timedelta(minutes=getattr(agent, 'check_interval_minutes', 30))
                if next_execution > datetime.now():
                    cooldown_remaining = int((next_execution - datetime.now()).total_seconds())
            
            # Get performance metrics
            performance_metrics = {
                'harvesting_enabled': getattr(agent, 'enabled', False),
                'dust_conversion_enabled': getattr(agent, 'dust_conversion_enabled', False),
                'rebalancing_enabled': getattr(agent, 'rebalancing_enabled', False),
                'last_harvest_time': getattr(agent, 'last_harvest_time', None),
                'realized_gains_total': getattr(agent, 'realized_gains_total', 0.0)
            }
            
            status = 'running' if is_running and thread_active else 'stopped'
            
            return AgentStatus(
                name='harvesting_agent',
                status=status,
                last_execution=last_execution,
                thread_active=thread_active,
                cooldown_remaining=cooldown_remaining,
                error_count=0,
                success_count=1 if is_running else 0,
                last_error=None,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return AgentStatus(
                name='harvesting_agent',
                status='error',
                last_execution=None,
                thread_active=False,
                cooldown_remaining=0,
                error_count=1,
                success_count=0,
                last_error=str(e),
                performance_metrics={}
            )
    
    def _check_staking_agent(self) -> AgentStatus:
        """Check staking agent status"""
        try:
            from src.agents.staking_agent import StakingAgent
            
            # Try to get agent instance
            agent = StakingAgent()
            
            # Check if agent is running
            is_running = getattr(agent, 'is_running', False)
            thread_active = getattr(agent, 'thread', None) is not None and getattr(agent.thread, 'is_alive', lambda: False)()
            
            # Get last execution time
            last_execution = getattr(agent, 'last_execution_time', None)
            if last_execution and last_execution > 0:
                last_execution = datetime.fromtimestamp(last_execution)
            else:
                last_execution = None
            
            # Calculate cooldown remaining
            cooldown_remaining = 0
            if last_execution:
                next_execution = last_execution + timedelta(minutes=getattr(agent, 'check_interval_minutes', 1440))  # Daily
                if next_execution > datetime.now():
                    cooldown_remaining = int((next_execution - datetime.now()).total_seconds())
            
            # Get performance metrics
            performance_metrics = {
                'staking_enabled': getattr(agent, 'enabled', False),
                'execution_mode': getattr(agent, 'execution_mode', 'hybrid'),
                'webhook_enabled': getattr(agent, 'webhook_enabled', False),
                'interval_enabled': getattr(agent, 'interval_enabled', False),
                'last_stake_time': getattr(agent, 'last_stake_time', None)
            }
            
            status = 'running' if is_running and thread_active else 'stopped'
            
            return AgentStatus(
                name='staking_agent',
                status=status,
                last_execution=last_execution,
                thread_active=thread_active,
                cooldown_remaining=cooldown_remaining,
                error_count=0,
                success_count=1 if is_running else 0,
                last_error=None,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return AgentStatus(
                name='staking_agent',
                status='error',
                last_execution=None,
                thread_active=False,
                cooldown_remaining=0,
                error_count=1,
                success_count=0,
                last_error=str(e),
                performance_metrics={}
            )
    
    def _check_sentiment_agent(self) -> AgentStatus:
        """Check sentiment agent status"""
        try:
            from src.agents.sentiment_agent import SentimentAgent
            
            # Try to get agent instance
            agent = SentimentAgent()
            
            # Check if agent is running
            is_running = getattr(agent, 'is_running', False)
            thread_active = getattr(agent, 'thread', None) is not None and getattr(agent.thread, 'is_alive', lambda: False)()
            
            # Get last execution time
            last_execution = getattr(agent, 'last_check_time', None)
            if last_execution and last_execution > 0:
                last_execution = datetime.fromtimestamp(last_execution)
            else:
                last_execution = None
            
            # Calculate cooldown remaining
            cooldown_remaining = 0
            if last_execution:
                next_execution = last_execution + timedelta(minutes=getattr(agent, 'check_interval_minutes', 60))
                if next_execution > datetime.now():
                    cooldown_remaining = int((next_execution - datetime.now()).total_seconds())
            
            # Get performance metrics
            performance_metrics = {
                'sentiment_enabled': getattr(agent, 'enabled', False),
                'tokens_tracked': len(getattr(agent, 'tokens_to_track', [])),
                'last_sentiment_update': getattr(agent, 'last_sentiment_update', None),
                'voice_enabled': getattr(agent, 'voice_enabled', False)
            }
            
            status = 'running' if is_running and thread_active else 'stopped'
            
            return AgentStatus(
                name='sentiment_agent',
                status=status,
                last_execution=last_execution,
                thread_active=thread_active,
                cooldown_remaining=cooldown_remaining,
                error_count=0,
                success_count=1 if is_running else 0,
                last_error=None,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return AgentStatus(
                name='sentiment_agent',
                status='error',
                last_execution=None,
                thread_active=False,
                cooldown_remaining=0,
                error_count=1,
                success_count=0,
                last_error=str(e),
                performance_metrics={}
            )
    
    def _check_chart_analysis_agent(self) -> AgentStatus:
        """Check chart analysis agent status"""
        try:
            from src.agents.chartanalysis_agent import ChartAnalysisAgent
            
            # Try to get agent instance
            agent = ChartAnalysisAgent()
            
            # Check if agent is running
            is_running = getattr(agent, 'running', False)
            thread_active = True  # Chart analysis runs on demand
            
            # Get last execution time
            last_execution = getattr(agent, 'last_analysis_time', None)
            if last_execution and last_execution > 0:
                last_execution = datetime.fromtimestamp(last_execution)
            else:
                last_execution = None
            
            # Calculate cooldown remaining
            cooldown_remaining = 0
            if last_execution:
                next_execution = last_execution + timedelta(minutes=getattr(agent, 'check_interval_minutes', 60))
                if next_execution > datetime.now():
                    cooldown_remaining = int((next_execution - datetime.now()).total_seconds())
            
            # Get performance metrics
            performance_metrics = {
                'tokens_monitored': len(getattr(agent, 'dca_tokens', [])),
                'last_chart_update': getattr(agent, 'last_chart_update', None),
                'aggregated_sentiment_enabled': getattr(agent, 'aggregated_sentiment_enabled', False),
                'charts_generated': len(getattr(agent, 'charts_dir', []).glob('*.png')) if hasattr(agent, 'charts_dir') else 0
            }
            
            status = 'running' if is_running else 'stopped'
            
            return AgentStatus(
                name='chartanalysis_agent',
                status=status,
                last_execution=last_execution,
                thread_active=thread_active,
                cooldown_remaining=cooldown_remaining,
                error_count=0,
                success_count=1 if is_running else 0,
                last_error=None,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return AgentStatus(
                name='chartanalysis_agent',
                status='error',
                last_execution=None,
                thread_active=False,
                cooldown_remaining=0,
                error_count=1,
                success_count=0,
                last_error=str(e),
                performance_metrics={}
            )
    
    def get_all_agent_status(self) -> Dict[str, AgentStatus]:
        """Get status of all agents"""
        agent_names = [
            'risk_agent',
            'copybot_agent', 
            'harvesting_agent',
            'staking_agent',
            'sentiment_agent',
            'chartanalysis_agent'
        ]
        
        statuses = {}
        for agent_name in agent_names:
            statuses[agent_name] = self.get_agent_status(agent_name)
        
        return statuses
    
    def get_agent_health_summary(self) -> Dict[str, Any]:
        """Get overall agent health summary"""
        statuses = self.get_all_agent_status()
        
        total_agents = len(statuses)
        running_agents = sum(1 for status in statuses.values() if status and status.status == 'running')
        stopped_agents = sum(1 for status in statuses.values() if status and status.status == 'stopped')
        error_agents = sum(1 for status in statuses.values() if status and status.status == 'error')
        
        # Calculate average cooldown
        cooldowns = [status.cooldown_remaining for status in statuses.values() if status and status.cooldown_remaining > 0]
        avg_cooldown = sum(cooldowns) / len(cooldowns) if cooldowns else 0
        
        # Count agents with recent activity (within last hour)
        recent_activity = 0
        for status in statuses.values():
            if status and status.last_execution:
                if datetime.now() - status.last_execution < timedelta(hours=1):
                    recent_activity += 1
        
        return {
            'total_agents': total_agents,
            'running_agents': running_agents,
            'stopped_agents': stopped_agents,
            'error_agents': error_agents,
            'recent_activity': recent_activity,
            'avg_cooldown_remaining': avg_cooldown,
            'health_percentage': (running_agents / total_agents * 100) if total_agents > 0 else 0
        }

# Global instance
agent_monitor = AgentHealthMonitor()

def get_agent_monitor() -> AgentHealthMonitor:
    """Get global agent monitor instance"""
    return agent_monitor

if __name__ == "__main__":
    # Test the agent monitor
    monitor = AgentHealthMonitor()
    
    print("🤖 Agent Health Monitor Test")
    print("=" * 50)
    
    statuses = monitor.get_all_agent_status()
    for agent_name, status in statuses.items():
        if status:
            print(f"{agent_name}: {status.status}")
            print(f"  Last execution: {status.last_execution}")
            print(f"  Thread active: {status.thread_active}")
            print(f"  Cooldown remaining: {status.cooldown_remaining}s")
            print(f"  Error count: {status.error_count}")
            print()
    
    summary = monitor.get_agent_health_summary()
    print("Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
