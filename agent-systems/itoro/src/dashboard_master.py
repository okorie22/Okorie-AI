"""
👑 ITORO Master Agent Dashboard
Real-time monitoring and control interface for the Master Asset Manager
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.scripts.shared_services.config_manager import get_config_manager
from src.scripts.shared_services.performance_monitor import get_performance_monitor
from src.agents.master_agent import get_master_agent

# Page config
st.set_page_config(
    page_title="ITORO Master Agent Dashboard",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #FFD700;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .personality-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .aggressive {
        background: #ff4444;
        color: white;
    }
    .balanced {
        background: #44ff44;
        color: black;
    }
    .conservative {
        background: #4444ff;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def render_header():
    """Render dashboard header"""
    st.markdown('<h1 class="main-header">👑 ITORO MASTER AGENT DASHBOARD 👑</h1>', unsafe_allow_html=True)
    st.markdown("### Supreme Asset Manager & System Orchestrator")
    st.markdown("---")

def get_master_agent_status_from_file():
    """Read Master Agent status from monitoring log file"""
    try:
        log_file = Path("src/data/master_agent/monitoring_log.json")
        if log_file.exists():
            with open(log_file, 'r') as f:
                logs = json.load(f)
                if logs:
                    latest = logs[-1]
                    # Check if logged in last 35 minutes (monitoring runs every 30 min)
                    log_time = datetime.fromisoformat(latest['timestamp'])
                    is_running = (datetime.now() - log_time).total_seconds() < 2100
                    
                    return {
                        'is_running': is_running,
                        'personality_mode': latest.get('personality_mode', 'BALANCED'),
                        'last_check': latest['timestamp'],
                        'decisions_count': len(logs)
                    }
    except Exception as e:
        pass
    
    return {
        'is_running': False,
        'personality_mode': 'BALANCED',
        'last_check': None,
        'decisions_count': 0
    }

def render_personality_status(master_agent):
    """Render personality mode status"""
    # Get status from file (reflects running main.py instance)
    file_status = get_master_agent_status_from_file()
    mode = file_status['personality_mode']
    
    mode_class = mode.lower()
    mode_emoji = {
        'AGGRESSIVE': '🔥',
        'BALANCED': '⚖️',
        'CONSERVATIVE': '🛡️'
    }.get(mode, '⚖️')
    
    st.markdown(f"""
    <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 2rem;">
        <h2 style="color: white; margin-bottom: 1rem;">Current Personality Mode</h2>
        <div class="personality-badge {mode_class}">
            {mode_emoji} {mode} MODE
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_goal_progress(performance_monitor):
    """Render PnL goal progress"""
    goal_progress = performance_monitor.get_goal_progress()
    
    if goal_progress:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Monthly PnL Goal",
                f"{goal_progress['goal_percent']:.1f}%",
                delta=None
            )
        
        with col2:
            st.metric(
                "Current Progress",
                f"{goal_progress['current_monthly_pnl_percent']:.2f}%",
                delta=f"{goal_progress['progress_percent']:.1f}% of goal"
            )
        
        with col3:
            st.metric(
                "Gap to Goal",
                f"{goal_progress['gap_percent']:.2f}%",
                delta=f"${goal_progress['gap_usd']:.2f}"
            )
        
        with col4:
            on_track = "✅ On Track" if goal_progress['on_track'] else "⚠️ Behind"
            st.metric(
                "Status",
                on_track,
                delta=None
            )
        
        # Progress bar
        progress = min(goal_progress['progress_percent'] / 100, 1.0)
        st.progress(progress)
        
        # Required daily PnL
        st.info(f"📊 Required Daily PnL: ${goal_progress['required_daily_pnl_usd']:.2f} ({goal_progress['days_remaining']} days remaining)")

def render_system_health(performance_monitor):
    """Render system health overview"""
    st.subheader("🏥 System Health Overview")
    
    health = performance_monitor.get_system_health_summary()
    
    if health:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            health_score = health['overall_health_score']
            health_color = "🟢" if health_score >= 80 else "🟡" if health_score >= 60 else "🔴"
            st.metric("Overall Health", f"{health_color} {health_score:.1f}/100")
        
        with col2:
            if health['performance']:
                win_rate = health['performance']['win_rate'] * 100
                st.metric("Win Rate", f"{win_rate:.1f}%")
        
        with col3:
            if health['data_quality']:
                data_quality = health['data_quality']['overall_data_quality_score']
                st.metric("Data Quality", f"{data_quality:.1f}/100")
        
        # Performance metrics
        if health['performance']:
            st.markdown("#### 📈 Performance Metrics")
            perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
            
            perf = health['performance']
            
            with perf_col1:
                st.metric("Total PnL", f"${perf['total_pnl_usd']:.2f}")
            
            with perf_col2:
                st.metric("Daily PnL", f"${perf['daily_pnl_usd']:.2f}")
            
            with perf_col3:
                st.metric("Total Trades", perf['total_trades'])
            
            with perf_col4:
                st.metric("Drawdown", f"{perf['drawdown_percent']:.2f}%")

def render_pending_suggestions(config_manager):
    """Render pending trading config suggestions"""
    st.subheader("📋 Pending Trading Config Suggestions")
    
    suggestions = config_manager.get_pending_suggestions()
    
    if suggestions:
        for idx, suggestion in enumerate(suggestions):
            with st.expander(f"💡 Suggestion {idx + 1}: {suggestion.parameter}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Current Value:**", suggestion.old_value)
                    st.write("**Suggested Value:**", suggestion.new_value)
                
                with col2:
                    st.write("**Confidence:**", f"{suggestion.confidence:.0%}")
                    st.write("**Timestamp:**", suggestion.timestamp)
                
                st.write("**Reasoning:**", suggestion.reason)
                st.write("**Category:**", f"🔧 {suggestion.category.upper()}")
                
                # Action buttons
                col_approve, col_reject = st.columns(2)
                
                with col_approve:
                    if st.button(f"✅ Approve {suggestion.parameter}", key=f"approve_{idx}", type="primary"):
                        success = config_manager.approve_suggestion(suggestion.parameter)
                        if success:
                            st.success(f"✅ Approved! {suggestion.parameter} = {suggestion.new_value}")
                            st.info("💡 Restart main.py to apply this change to config.py file")
                            st.rerun()
                        else:
                            st.error("❌ Failed to approve suggestion")
                
                with col_reject:
                    if st.button(f"❌ Reject {suggestion.parameter}", key=f"reject_{idx}"):
                        success = config_manager.reject_suggestion(suggestion.parameter)
                        if success:
                            st.warning(f"❌ Rejected suggestion for {suggestion.parameter}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to reject suggestion")
    else:
        st.info("No pending suggestions at this time.")

def render_recent_changes(config_manager):
    """Render recent config changes"""
    st.subheader("📝 Recent Config Changes")
    
    recent_changes = config_manager.get_recent_changes(hours=24)
    
    if recent_changes:
        changes_data = []
        for change in recent_changes:
            changes_data.append({
                'Timestamp': change.timestamp,
                'Parameter': change.parameter,
                'Old Value': str(change.old_value),
                'New Value': str(change.new_value),
                'Category': change.category.upper(),
                'Confidence': f"{change.confidence:.0%}",
                'Reason': change.reason[:50] + "..." if len(change.reason) > 50 else change.reason
            })
        
        df = pd.DataFrame(changes_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No config changes in the last 24 hours.")

def render_agent_performance(performance_monitor):
    """Render individual agent performance"""
    st.subheader("🤖 Agent Performance")
    
    agent_perf = performance_monitor.get_agent_performance()
    
    if agent_perf:
        perf_data = []
        for agent_name, perf in agent_perf.items():
            perf_data.append({
                'Agent': agent_name,
                'Executions': perf.total_executions,
                'Success Rate': f"{perf.success_rate:.1%}",
                'PnL Contribution': f"${perf.total_pnl_contribution:.2f}",
                'Avg Time (s)': f"{perf.avg_execution_time_seconds:.2f}",
                'Last Execution': perf.last_execution_time or 'N/A'
            })
        
        df = pd.DataFrame(perf_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No agent performance data available yet.")

def render_data_quality(performance_monitor):
    """Render data quality metrics"""
    st.subheader("📊 Data Quality Metrics")
    
    data_quality = performance_monitor.calculate_data_quality()
    
    if data_quality:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            staleness = data_quality.chart_analysis_staleness_minutes
            status = "🟢" if staleness < 60 else "🟡" if staleness < 180 else "🔴"
            st.metric("Chart Analysis", f"{status} {staleness:.0f}m")
        
        with col2:
            staleness = data_quality.whale_agent_staleness_hours
            status = "🟢" if staleness < 24 else "🟡" if staleness < 48 else "🔴"
            st.metric("Whale Agent", f"{status} {staleness:.1f}h")
        
        with col3:
            staleness = data_quality.sentiment_staleness_minutes
            status = "🟢" if staleness < 30 else "🟡" if staleness < 90 else "🔴"
            st.metric("Sentiment", f"{status} {staleness:.0f}m")
        
        with col4:
            staleness = data_quality.onchain_staleness_minutes
            status = "🟢" if staleness < 60 else "🟡" if staleness < 180 else "🔴"
            st.metric("OnChain", f"{status} {staleness:.0f}m")

def render_decisions_history(master_agent):
    """Render recent Master Agent decisions"""
    st.subheader("🧠 Recent Decisions")
    
    decisions = master_agent.get_recent_decisions(limit=10)
    
    if decisions:
        for idx, decision in enumerate(reversed(decisions)):
            decision_type = decision.get('decision_type', 'unknown')
            timestamp = decision.get('timestamp', 'N/A')
            
            emoji = "🔄" if decision_type == "personality_change" else "⚙️" if decision_type == "config_approval" else "📝"
            
            with st.expander(f"{emoji} Decision {len(decisions) - idx}: {decision_type}"):
                st.json(decision)
    else:
        st.info("No recent decisions recorded.")

def main():
    """Main dashboard function"""
    try:
        # Initialize components
        master_agent = get_master_agent()
        config_manager = get_config_manager()
        performance_monitor = get_performance_monitor()
        
        # Render header
        render_header()
        
        # Sidebar
        with st.sidebar:
            st.image("https://via.placeholder.com/200x200.png?text=ITORO", width=200)
            st.markdown("### Dashboard Controls")
            
            if st.button("🔄 Refresh Data"):
                st.rerun()
            
            st.markdown("---")
            st.markdown("### Quick Stats")
            # Get status from file (reflects running main.py instance)
            file_status = get_master_agent_status_from_file()
            st.write(f"**Running:** {'✅ Yes' if file_status['is_running'] else '❌ No'}")
            st.write(f"**Mode:** {file_status['personality_mode']}")
            st.write(f"**Decisions:** {file_status['decisions_count']}")
            if file_status['last_check']:
                last_check_time = datetime.fromisoformat(file_status['last_check'])
                time_ago = (datetime.now() - last_check_time).total_seconds() / 60
                st.write(f"**Last Check:** {time_ago:.0f}m ago")
        
        # Main content
        render_personality_status(master_agent)
        
        st.markdown("---")
        
        # Goal progress
        render_goal_progress(performance_monitor)
        
        st.markdown("---")
        
        # System health
        render_system_health(performance_monitor)
        
        st.markdown("---")
        
        # Two column layout
        col1, col2 = st.columns(2)
        
        with col1:
            render_pending_suggestions(config_manager)
            st.markdown("---")
            render_recent_changes(config_manager)
        
        with col2:
            render_agent_performance(performance_monitor)
            st.markdown("---")
            render_data_quality(performance_monitor)
        
        st.markdown("---")
        
        # Decisions history
        render_decisions_history(master_agent)
        
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()

