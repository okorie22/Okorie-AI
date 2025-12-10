"""
📊 ITORO Performance Monitor - System Metrics Tracking
Tracks PnL, agent performance, and system health for the Master Agent
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from src.scripts.shared_services.logger import info, warning, error, debug

@dataclass
class PerformanceSnapshot:
    """Snapshot of system performance at a point in time"""
    timestamp: str
    total_pnl_usd: float
    daily_pnl_usd: float
    weekly_pnl_usd: float
    monthly_pnl_usd: float
    total_value_usd: float
    portfolio_balance_usd: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    consecutive_losses: int
    consecutive_wins: int
    avg_trade_size_usd: float
    largest_win_usd: float
    largest_loss_usd: float
    drawdown_percent: float

@dataclass
class AgentPerformance:
    """Performance metrics for an individual agent"""
    agent_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    total_pnl_contribution: float
    avg_execution_time_seconds: float
    last_execution_time: Optional[str]

@dataclass
class DataQualityMetrics:
    """Metrics for data collection quality"""
    chart_analysis_last_update: Optional[str]
    chart_analysis_staleness_minutes: float
    whale_agent_last_update: Optional[str]
    whale_agent_staleness_hours: float
    sentiment_last_update: Optional[str]
    sentiment_staleness_minutes: float
    onchain_last_update: Optional[str]
    onchain_staleness_minutes: float
    overall_data_quality_score: float  # 0-100

class PerformanceMonitor:
    """
    Performance monitoring system for ITORO
    Tracks PnL, agent performance, and data quality
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PerformanceMonitor, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # Initialize storage
        self.data_dir = Path("src/data/master_agent")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.snapshots_file = self.data_dir / "performance_snapshots.json"
        self.agent_perf_file = self.data_dir / "agent_performance.json"
        
        # Performance tracking
        self.snapshots: List[PerformanceSnapshot] = []
        self.agent_performance: Dict[str, AgentPerformance] = {}
        
        # Goal tracking
        self.monthly_pnl_goal_percent = 30.0  # Default 30% monthly goal
        
        # Load historical data
        self._load_snapshots()
        self._load_agent_performance()
        
        info("📊 Performance Monitor initialized")
    
    def set_monthly_pnl_goal(self, goal_percent: float):
        """Set the monthly PnL goal"""
        self.monthly_pnl_goal_percent = goal_percent
        info(f"📈 Monthly PnL goal set to {goal_percent}%")
    
    def calculate_current_performance(self) -> PerformanceSnapshot:
        """
        Calculate current performance metrics
        Returns a PerformanceSnapshot with all current metrics
        """
        try:
            from src.scripts.database.execution_tracker import get_execution_tracker
            from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
            from src import config
            
            execution_tracker = get_execution_tracker()
            portfolio_tracker = get_portfolio_tracker()
            
            # Get current portfolio
            current_snapshot = portfolio_tracker.current_snapshot
            if not current_snapshot:
                warning("No portfolio snapshot available")
                return None
            
            total_value = current_snapshot.total_value_usd
            
            # Get execution history
            all_executions = execution_tracker.get_executions(limit=1000)
            
            # Calculate PnL for different timeframes
            now = datetime.now()
            daily_pnl = self._calculate_pnl_for_period(all_executions, hours=24)
            weekly_pnl = self._calculate_pnl_for_period(all_executions, hours=168)
            monthly_pnl = self._calculate_pnl_for_period(all_executions, hours=720)
            
            # Calculate total PnL
            total_pnl = sum([e.get('pnl_usd', 0) for e in all_executions])
            
            # Calculate win/loss stats
            winning_trades = [e for e in all_executions if e.get('pnl_usd', 0) > 0]
            losing_trades = [e for e in all_executions if e.get('pnl_usd', 0) < 0]
            
            total_trades = len(all_executions)
            win_count = len(winning_trades)
            loss_count = len(losing_trades)
            win_rate = win_count / total_trades if total_trades > 0 else 0.0
            
            # Calculate consecutive wins/losses
            consecutive_losses = self._calculate_consecutive_losses(all_executions)
            consecutive_wins = self._calculate_consecutive_wins(all_executions)
            
            # Calculate average trade size
            trade_sizes = [e.get('value_usd', 0) for e in all_executions]
            avg_trade_size = sum(trade_sizes) / len(trade_sizes) if trade_sizes else 0.0
            
            # Get largest win/loss
            win_amounts = [e.get('pnl_usd', 0) for e in winning_trades]
            loss_amounts = [e.get('pnl_usd', 0) for e in losing_trades]
            largest_win = max(win_amounts) if win_amounts else 0.0
            largest_loss = min(loss_amounts) if loss_amounts else 0.0
            
            # Calculate drawdown
            initial_balance = getattr(config, 'PAPER_INITIAL_BALANCE', 1000.0)
            peak_balance = max(total_value, initial_balance)
            drawdown_percent = ((peak_balance - total_value) / peak_balance) * 100 if peak_balance > 0 else 0.0
            
            # Create snapshot
            snapshot = PerformanceSnapshot(
                timestamp=now.isoformat(),
                total_pnl_usd=total_pnl,
                daily_pnl_usd=daily_pnl,
                weekly_pnl_usd=weekly_pnl,
                monthly_pnl_usd=monthly_pnl,
                total_value_usd=total_value,
                portfolio_balance_usd=total_value,
                win_rate=win_rate,
                total_trades=total_trades,
                winning_trades=win_count,
                losing_trades=loss_count,
                consecutive_losses=consecutive_losses,
                consecutive_wins=consecutive_wins,
                avg_trade_size_usd=avg_trade_size,
                largest_win_usd=largest_win,
                largest_loss_usd=largest_loss,
                drawdown_percent=drawdown_percent
            )
            
            # Save snapshot
            self.snapshots.append(snapshot)
            self._save_snapshots()
            
            return snapshot
        
        except Exception as e:
            error(f"Error calculating performance: {e}")
            return None
    
    def _calculate_pnl_for_period(self, executions: List[Dict], hours: int) -> float:
        """Calculate PnL for a specific time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        period_pnl = 0.0
        for execution in executions:
            timestamp_str = execution.get('timestamp')
            if timestamp_str:
                try:
                    exec_time = datetime.fromisoformat(timestamp_str)
                    if exec_time >= cutoff_time:
                        period_pnl += execution.get('pnl_usd', 0)
                except:
                    continue
        
        return period_pnl
    
    def _calculate_consecutive_losses(self, executions: List[Dict]) -> int:
        """Calculate current consecutive losses"""
        consecutive = 0
        for execution in reversed(executions):
            if execution.get('pnl_usd', 0) < 0:
                consecutive += 1
            else:
                break
        return consecutive
    
    def _calculate_consecutive_wins(self, executions: List[Dict]) -> int:
        """Calculate current consecutive wins"""
        consecutive = 0
        for execution in reversed(executions):
            if execution.get('pnl_usd', 0) > 0:
                consecutive += 1
            else:
                break
        return consecutive
    
    def get_goal_progress(self) -> Dict[str, Any]:
        """
        Get progress toward monthly PnL goal
        Returns dict with goal info and progress
        """
        try:
            snapshot = self.calculate_current_performance()
            if not snapshot:
                return None
            
            # Calculate goal metrics
            from src import config
            initial_balance = getattr(config, 'PAPER_INITIAL_BALANCE', 1000.0)
            
            # Monthly PnL as percentage
            monthly_pnl_percent = (snapshot.monthly_pnl_usd / initial_balance) * 100
            
            # Progress toward goal
            progress_percent = (monthly_pnl_percent / self.monthly_pnl_goal_percent) * 100
            
            # Gap to goal
            gap_percent = self.monthly_pnl_goal_percent - monthly_pnl_percent
            gap_usd = (gap_percent / 100) * initial_balance
            
            # Days in month so far
            now = datetime.now()
            days_elapsed = now.day
            days_in_month = 30  # Approximate
            days_remaining = days_in_month - days_elapsed
            
            # Required daily PnL to hit goal
            if days_remaining > 0:
                required_daily_pnl = gap_usd / days_remaining
            else:
                required_daily_pnl = 0.0
            
            return {
                'goal_percent': self.monthly_pnl_goal_percent,
                'current_monthly_pnl_percent': monthly_pnl_percent,
                'current_monthly_pnl_usd': snapshot.monthly_pnl_usd,
                'progress_percent': progress_percent,
                'gap_percent': gap_percent,
                'gap_usd': gap_usd,
                'days_elapsed': days_elapsed,
                'days_remaining': days_remaining,
                'required_daily_pnl_usd': required_daily_pnl,
                'on_track': monthly_pnl_percent >= (self.monthly_pnl_goal_percent * days_elapsed / days_in_month)
            }
        
        except Exception as e:
            error(f"Error calculating goal progress: {e}")
            return None
    
    def update_agent_performance(self, agent_name: str, execution_success: bool, 
                                 execution_time_seconds: float, pnl_contribution: float = 0.0):
        """Update performance metrics for an agent"""
        try:
            if agent_name not in self.agent_performance:
                self.agent_performance[agent_name] = AgentPerformance(
                    agent_name=agent_name,
                    total_executions=0,
                    successful_executions=0,
                    failed_executions=0,
                    success_rate=0.0,
                    total_pnl_contribution=0.0,
                    avg_execution_time_seconds=0.0,
                    last_execution_time=None
                )
            
            perf = self.agent_performance[agent_name]
            
            # Update counts
            perf.total_executions += 1
            if execution_success:
                perf.successful_executions += 1
            else:
                perf.failed_executions += 1
            
            # Update success rate
            perf.success_rate = perf.successful_executions / perf.total_executions
            
            # Update PnL contribution
            perf.total_pnl_contribution += pnl_contribution
            
            # Update average execution time
            total_time = perf.avg_execution_time_seconds * (perf.total_executions - 1)
            perf.avg_execution_time_seconds = (total_time + execution_time_seconds) / perf.total_executions
            
            # Update last execution time
            perf.last_execution_time = datetime.now().isoformat()
            
            self._save_agent_performance()
        
        except Exception as e:
            error(f"Error updating agent performance: {e}")
    
    def get_agent_performance(self, agent_name: Optional[str] = None) -> Dict[str, AgentPerformance]:
        """Get performance metrics for agents"""
        if agent_name:
            return {agent_name: self.agent_performance.get(agent_name)}
        return self.agent_performance
    
    def calculate_data_quality(self) -> DataQualityMetrics:
        """
        Calculate data quality metrics
        Assesses freshness of data from all collection agents
        """
        try:
            now = datetime.now()
            
            # Get data timestamps from various sources
            chart_last = self._get_chart_analysis_timestamp()
            whale_last = self._get_whale_agent_timestamp()
            sentiment_last = self._get_sentiment_timestamp()
            onchain_last = self._get_onchain_timestamp()
            
            # Calculate staleness
            chart_staleness = self._calculate_staleness_minutes(chart_last) if chart_last else 999999
            whale_staleness = self._calculate_staleness_minutes(whale_last) / 60 if whale_last else 999999  # hours
            sentiment_staleness = self._calculate_staleness_minutes(sentiment_last) if sentiment_last else 999999
            onchain_staleness = self._calculate_staleness_minutes(onchain_last) if onchain_last else 999999
            
            # Calculate quality score (0-100)
            # Fresh data = high score, stale data = low score
            chart_score = max(0, 100 - (chart_staleness / 60 * 10))  # -10 per hour stale
            whale_score = max(0, 100 - (whale_staleness * 2))  # -2 per hour stale
            sentiment_score = max(0, 100 - (sentiment_staleness / 60 * 10))  # -10 per hour stale
            onchain_score = max(0, 100 - (onchain_staleness / 60 * 10))  # -10 per hour stale
            
            overall_score = (chart_score + whale_score + sentiment_score + onchain_score) / 4
            
            return DataQualityMetrics(
                chart_analysis_last_update=chart_last.isoformat() if chart_last else None,
                chart_analysis_staleness_minutes=chart_staleness,
                whale_agent_last_update=whale_last.isoformat() if whale_last else None,
                whale_agent_staleness_hours=whale_staleness,
                sentiment_last_update=sentiment_last.isoformat() if sentiment_last else None,
                sentiment_staleness_minutes=sentiment_staleness,
                onchain_last_update=onchain_last.isoformat() if onchain_last else None,
                onchain_staleness_minutes=onchain_staleness,
                overall_data_quality_score=overall_score
            )
        
        except Exception as e:
            error(f"Error calculating data quality: {e}")
            return None
    
    def get_data_quality_summary(self) -> DataQualityMetrics:
        """Get data quality summary (alias for calculate_data_quality for dashboard)"""
        return self.calculate_data_quality()
    
    def _get_chart_analysis_timestamp(self) -> Optional[datetime]:
        """Get last chart analysis timestamp"""
        try:
            # Check for chart data files
            chart_dir = Path("src/data/charts")
            if chart_dir.exists():
                csv_files = list(chart_dir.glob("*.csv"))
                if csv_files:
                    latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
                    return datetime.fromtimestamp(latest_file.stat().st_mtime)
        except:
            pass
        return None
    
    def _get_whale_agent_timestamp(self) -> Optional[datetime]:
        """Get last whale agent update timestamp"""
        try:
            whale_file = Path("src/data/whale_dump/ranked_whales.json")
            if whale_file.exists():
                return datetime.fromtimestamp(whale_file.stat().st_mtime)
        except:
            pass
        return None
    
    def _get_sentiment_timestamp(self) -> Optional[datetime]:
        """Get last sentiment analysis timestamp"""
        try:
            sentiment_file = Path("src/data/sentiment_history.csv")
            if sentiment_file.exists():
                return datetime.fromtimestamp(sentiment_file.stat().st_mtime)
        except:
            pass
        return None
    
    def _get_onchain_timestamp(self) -> Optional[datetime]:
        """Get last onchain data timestamp"""
        try:
            onchain_file = Path("src/data/token_onchain_data.json")
            if onchain_file.exists():
                return datetime.fromtimestamp(onchain_file.stat().st_mtime)
        except:
            pass
        return None
    
    def _calculate_staleness_minutes(self, timestamp: datetime) -> float:
        """Calculate how many minutes ago a timestamp was"""
        if not timestamp:
            return 999999.0
        delta = datetime.now() - timestamp
        return delta.total_seconds() / 60
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive system health summary
        Combines performance, agent metrics, and data quality
        """
        try:
            performance = self.calculate_current_performance()
            goal_progress = self.get_goal_progress()
            data_quality = self.calculate_data_quality()
            
            # Overall health score (0-100)
            health_components = []
            
            # Performance health (40% weight)
            if performance:
                perf_health = 100 if performance.win_rate > 0.6 else (performance.win_rate * 100 * 1.67)
                health_components.append(perf_health * 0.4)
            
            # Goal progress health (30% weight)
            if goal_progress:
                goal_health = min(100, goal_progress['progress_percent'])
                health_components.append(goal_health * 0.3)
            
            # Data quality health (30% weight)
            if data_quality:
                health_components.append(data_quality.overall_data_quality_score * 0.3)
            
            overall_health = sum(health_components) if health_components else 0
            
            return {
                'overall_health_score': overall_health,
                'performance': asdict(performance) if performance else None,
                'goal_progress': goal_progress,
                'data_quality': asdict(data_quality) if data_quality else None,
                'agent_performance': {name: asdict(perf) for name, perf in self.agent_performance.items()},
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            error(f"Error generating system health summary: {e}")
            return None
    
    def _load_snapshots(self):
        """Load performance snapshots from disk"""
        try:
            if self.snapshots_file.exists():
                with open(self.snapshots_file, 'r') as f:
                    data = json.load(f)
                    # Only keep last 1000 snapshots
                    self.snapshots = [PerformanceSnapshot(**item) for item in data[-1000:]]
        except Exception as e:
            error(f"Error loading snapshots: {e}")
            self.snapshots = []
    
    def _save_snapshots(self):
        """Save performance snapshots to disk"""
        try:
            # Only save last 1000 snapshots
            with open(self.snapshots_file, 'w') as f:
                data = [asdict(snapshot) for snapshot in self.snapshots[-1000:]]
                json.dump(data, f, indent=2)
        except Exception as e:
            error(f"Error saving snapshots: {e}")
    
    def _load_agent_performance(self):
        """Load agent performance from disk"""
        try:
            if self.agent_perf_file.exists():
                with open(self.agent_perf_file, 'r') as f:
                    data = json.load(f)
                    self.agent_performance = {
                        name: AgentPerformance(**perf_data) 
                        for name, perf_data in data.items()
                    }
        except Exception as e:
            error(f"Error loading agent performance: {e}")
            self.agent_performance = {}
    
    def _save_agent_performance(self):
        """Save agent performance to disk"""
        try:
            with open(self.agent_perf_file, 'w') as f:
                data = {name: asdict(perf) for name, perf in self.agent_performance.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            error(f"Error saving agent performance: {e}")

# Singleton accessor
_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global PerformanceMonitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor
