"""
Enhanced dashboard for comprehensive system monitoring
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import Dict, Any

from ..storage.database import get_db
from ..storage.models import (
    Lead, Conversation, Message, LeadScore, LeadEnrichment, LeadSourceRun,
    ConversationState, MessageDirection
)

router = APIRouter(tags=["dashboard"])


def calculate_next_run_time(cron_minute: str, cron_hour: str) -> datetime:
    """Calculate next run time for a cron schedule"""
    now = datetime.utcnow()
    
    # Parse cron patterns
    if cron_hour == "*/2":  # Every 2 hours
        next_hour = ((now.hour // 2) + 1) * 2
        if next_hour >= 24:
            next_hour = 0
            next_day = now + timedelta(days=1)
            return next_day.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        return now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    
    elif cron_hour == "*/6":  # Every 6 hours
        next_hour = ((now.hour // 6) + 1) * 6
        if next_hour >= 24:
            next_hour = 0
            next_day = now + timedelta(days=1)
            return next_day.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        return now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    
    elif cron_minute == "*/10":  # Every 10 minutes
        next_minute = ((now.minute // 10) + 1) * 10
        if next_minute >= 60:
            return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        return now.replace(minute=next_minute, second=0, microsecond=0)
    
    elif cron_minute == "*/20":  # Every 20 minutes (Calendly sync)
        next_minute = ((now.minute // 20) + 1) * 20
        if next_minute >= 60:
            return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        return now.replace(minute=next_minute, second=0, microsecond=0)
    
    elif cron_hour == "2":  # Daily at 2 AM
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now.hour >= 2:
            next_run += timedelta(days=1)
        return next_run
    
    return now


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Enhanced dashboard with comprehensive system metrics"""
    
    # Basic stats
    total_leads = db.query(Lead).count()
    total_scored = db.query(LeadScore).count()
    total_conversations = db.query(Conversation).count()
    total_messages_sent = db.query(Message).filter(
        Message.direction == MessageDirection.OUTBOUND
    ).count()
    total_messages_received = db.query(Message).filter(
        Message.direction == MessageDirection.INBOUND
    ).count()
    
    # Delivery metrics
    delivered_count = db.query(Message).filter(
        Message.direction == MessageDirection.OUTBOUND,
        Message.delivered_at.isnot(None)
    ).count()
    
    opened_count = db.query(Message).filter(
        Message.direction == MessageDirection.OUTBOUND,
        Message.read_at.isnot(None)
    ).count()
    
    # Count clicked messages (check if 'clicked' key exists and is true)
    # Use SQLite json_extract vs PostgreSQL ->> so dashboard works with both
    dialect_name = db.get_bind().dialect.name
    if dialect_name == 'sqlite':
        clicked_count = db.query(Message).filter(
            Message.direction == MessageDirection.OUTBOUND,
            func.json_extract(Message.message_metadata, '$.clicked') == 'true'
        ).count()
    else:
        clicked_count = db.query(Message).filter(
            Message.direction == MessageDirection.OUTBOUND,
            Message.message_metadata.op('->>')('clicked') == 'true'
        ).count()
    
    bounced_count = db.query(Lead).filter(
        Lead.suppression_reason == 'bounce'
    ).count()
    
    # Calculate rates
    delivery_rate = (delivered_count / total_messages_sent * 100) if total_messages_sent > 0 else 0
    open_rate = (opened_count / delivered_count * 100) if delivered_count > 0 else 0
    click_rate = (clicked_count / delivered_count * 100) if delivered_count > 0 else 0
    reply_rate = (total_messages_received / delivered_count * 100) if delivered_count > 0 else 0
    bounce_rate = (bounced_count / total_messages_sent * 100) if total_messages_sent > 0 else 0
    
    # Enrichment stats
    total_enriched = db.query(LeadEnrichment).count()
    pending_enrichment = db.query(Lead).outerjoin(LeadEnrichment).filter(
        LeadEnrichment.id.is_(None)
    ).join(LeadScore).filter(
        LeadScore.tier <= 2  # High-priority leads only
    ).count()
    
    # Import stats
    total_imports = db.query(LeadSourceRun).count()
    total_imported = db.query(func.sum(LeadSourceRun.new_leads_imported)).scalar() or 0
    total_duplicates = db.query(func.sum(LeadSourceRun.duplicates_skipped)).scalar() or 0
    verified_emails_count = db.query(Lead).filter(
        Lead.email.isnot(None),
        Lead.email != "",
        Lead.email_deliverable.is_(True)
    ).count()
    
    # Tier breakdown
    tier_counts = {}
    for tier in [1, 2, 3, 4, 5]:
        count = db.query(LeadScore).filter(LeadScore.tier == tier).count()
        tier_counts[tier] = count
    
    # Conversation states - ALL states
    all_states = [
        ConversationState.NEW, ConversationState.CONTACTED, ConversationState.ENGAGED,
        ConversationState.QUALIFIED, ConversationState.SCHEDULED, ConversationState.CONFIRMED,
        ConversationState.REMINDED_24H, ConversationState.REMINDED_2H,
        ConversationState.NOT_INTERESTED, ConversationState.NO_RESPONSE
    ]
    state_counts = {}
    for state in all_states:
        count = db.query(Conversation).filter(Conversation.state == state).count()
        if count > 0:  # Only show states with active conversations
            state_counts[state.value] = count
    
    # Today's activity
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    leads_today = db.query(Lead).filter(Lead.created_at >= today_start).count()
    messages_sent_today = db.query(Message).filter(
        Message.direction == MessageDirection.OUTBOUND,
        Message.created_at >= today_start
    ).count()
    enriched_today = db.query(LeadEnrichment).filter(
        LeadEnrichment.enriched_at >= today_start
    ).count()
    
    # Last 7 days lead import trend
    daily_leads = []
    for i in range(6, -1, -1):
        day_start = (datetime.utcnow() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = db.query(Lead).filter(
            Lead.created_at >= day_start,
            Lead.created_at < day_end
        ).count()
        daily_leads.append({
            "date": day_start.strftime("%m/%d"),
            "count": count
        })
    
    # Pending outreach (conversations in NEW state)
    pending_outreach = db.query(Conversation).filter(
        Conversation.state == ConversationState.NEW
    ).count()
    
    # Next scheduled tasks
    next_tasks = {
        "Apify Import": calculate_next_run_time("0", "*/2"),
        "Message Dispatch": calculate_next_run_time("*/10", "*"),
        "Lead Scoring": calculate_next_run_time("0", "*/6"),
        "Enrichment": calculate_next_run_time("0", "2"),
        "Calendly Updates": calculate_next_run_time("*/20", "*"),
    }
    
    # Warmup status
    from ..workflow.warmup import WarmupManager
    warmup_mgr = WarmupManager()
    warmup_status = warmup_mgr.get_warmup_status()
    
    # Format next task times
    now = datetime.utcnow()
    task_times_html = ""
    for task_name, next_time in next_tasks.items():
        delta = next_time - now
        minutes_until = int(delta.total_seconds() / 60)
        
        if minutes_until < 60:
            time_str = f"{minutes_until}m"
        elif minutes_until < 1440:
            time_str = f"{minutes_until // 60}h {minutes_until % 60}m"
        else:
            time_str = f"{minutes_until // 1440}d {(minutes_until % 1440) // 60}h"
        
        task_times_html += f"""
        <div class="task-item">
            <span class="task-name">{task_name}</span>
            <span class="task-time">in {time_str}</span>
        </div>
        """
    
    # HTML dashboard
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>IUL Appointment Setter - Dashboard</title>
        <meta http-equiv="refresh" content="30">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: #0f172a;
                color: #e2e8f0;
                padding: 2rem;
            }}
            .container {{ max-width: 1600px; margin: 0 auto; }}
            h1 {{ 
                font-size: 2rem; 
                margin-bottom: 0.5rem;
                color: #f1f5f9;
            }}
            .subtitle {{ 
                color: #94a3b8;
                margin-bottom: 2rem;
                font-size: 0.9rem;
            }}
            .grid {{ 
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 1.5rem;
                margin-bottom: 2rem;
            }}
            .grid-2 {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 1.5rem;
                margin-bottom: 2rem;
            }}
            .card {{
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 1.5rem;
            }}
            .card-title {{
                font-size: 0.875rem;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 0.75rem;
            }}
            .card-value {{
                font-size: 2.5rem;
                font-weight: 700;
                color: #f1f5f9;
                line-height: 1;
            }}
            .card-value-small {{
                font-size: 1.75rem;
                font-weight: 600;
                color: #f1f5f9;
            }}
            .card-label {{
                font-size: 0.875rem;
                color: #64748b;
                margin-top: 0.5rem;
            }}
            .metric-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.75rem 0;
                border-bottom: 1px solid #334155;
            }}
            .metric-row:last-child {{ border-bottom: none; }}
            .metric-name {{ color: #94a3b8; font-size: 0.9rem; }}
            .metric-value {{ 
                font-size: 1.5rem;
                font-weight: 600;
                color: #10b981;
            }}
            .metric-value.warning {{ color: #f59e0b; }}
            .metric-value.danger {{ color: #ef4444; }}
            .tier-grid {{
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 0.75rem;
                margin-top: 1rem;
            }}
            .tier-item {{
                text-align: center;
                padding: 0.75rem;
                background: #0f172a;
                border-radius: 8px;
            }}
            .tier-item-title {{
                font-size: 0.75rem;
                color: #94a3b8;
                margin-bottom: 0.25rem;
            }}
            .tier-item-value {{
                font-size: 1.5rem;
                font-weight: 600;
                color: #f1f5f9;
            }}
            .state-list {{
                list-style: none;
                margin-top: 0.5rem;
                max-height: 300px;
                overflow-y: auto;
            }}
            .state-list li {{
                display: flex;
                justify-content: space-between;
                padding: 0.5rem 0;
                border-bottom: 1px solid #334155;
            }}
            .state-list li:last-child {{ border-bottom: none; }}
            .task-item {{
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 0.75rem;
                background: #0f172a;
                border-radius: 8px;
                min-width: 0;
            }}
            .task-name {{
                font-size: 0.9rem;
                color: #cbd5e1;
                margin-bottom: 0.5rem;
                text-align: center;
            }}
            .task-time {{
                font-size: 0.85rem;
                color: #3b82f6;
                font-weight: 600;
            }}
            .task-container {{
                display: flex;
                gap: 0.75rem;
                margin-top: 0.5rem;
            }}
            
            /* Navigation Bar */
            .navbar {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 1rem 2rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: -2rem -2rem 2rem -2rem;
                border-radius: 12px 12px 0 0;
            }}
            
            .navbar-brand {{
                font-size: 1.3rem;
                font-weight: 700;
                color: #667eea;
            }}
            
            .navbar-links {{
                display: flex;
                gap: 1rem;
            }}
            
            .nav-link {{
                text-decoration: none;
                color: #4a5568;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                font-weight: 500;
                transition: all 0.3s;
            }}
            
            .nav-link:hover {{
                background: #f7fafc;
                color: #667eea;
            }}
            
            .nav-link.active {{
                background: #667eea;
                color: white;
            }}
            .trend-chart {{
                display: flex;
                align-items: flex-end;
                justify-content: space-between;
                height: 100px;
                margin-top: 1rem;
                gap: 0.5rem;
            }}
            .trend-bar {{
                flex: 1;
                background: linear-gradient(to top, #3b82f6, #60a5fa);
                border-radius: 4px 4px 0 0;
                position: relative;
                min-height: 2px;
            }}
            .trend-label {{
                position: absolute;
                bottom: -1.5rem;
                left: 50%;
                transform: translateX(-50%);
                font-size: 0.75rem;
                color: #64748b;
                white-space: nowrap;
            }}
            .alert {{
                background: #dc2626;
                color: white;
                padding: 1rem;
                border-radius: 8px;
                margin-bottom: 1.5rem;
            }}
            .success {{
                background: #16a34a;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Navigation Bar -->
            <nav class="navbar">
                <div class="navbar-brand">⚡ IUL Appointment Setter</div>
                <div class="navbar-links">
                    <a href="/dashboard/" class="nav-link active">📊 Main Dashboard</a>
                    <a href="/appointments" class="nav-link">📅 Appointments & Deals</a>
                    <a href="/messages" class="nav-link">💬 Messages</a>
                </div>
            </nav>
            
            <h1>📊 Main Dashboard</h1>
            <div class="subtitle">
                Last updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC • Auto-refresh every 30s
            </div>
            
            {"<div class='alert'>⚠️ " + str(pending_outreach) + " leads pending first contact</div>" if pending_outreach > 10 else ""}
            
            <!-- Core Metrics -->
            <div class="grid">
                <div class="card">
                    <div class="card-title">Total Leads</div>
                    <div class="card-value">{total_leads:,}</div>
                    <div class="card-label">{total_scored:,} scored • {total_enriched:,} enriched</div>
                </div>
                
                <div class="card">
                    <div class="card-title">Active Conversations</div>
                    <div class="card-value">{total_conversations:,}</div>
                    <div class="card-label">{pending_outreach:,} pending outreach</div>
                </div>
                
                <div class="card">
                    <div class="card-title">Messages Sent</div>
                    <div class="card-value">{total_messages_sent:,}</div>
                    <div class="card-label">{total_messages_received:,} replies received</div>
                </div>
                
                <div class="card">
                    <div class="card-title">Today's Activity</div>
                    <div class="card-value">{leads_today}</div>
                    <div class="card-label">{messages_sent_today} sent • {enriched_today} enriched</div>
                </div>
            </div>
            
            <!-- Mode & Quota Status -->
            <div class="grid">
                <div class="card">
                    <div class="card-title">{'🔥 Mode Status' if warmup_status['warmup_mode'] else '✅ Mode Status'}</div>
                    <div class="metric-row">
                        <span class="metric-name">Mode</span>
                        <span class="metric-value-small">{'Warmup Day ' + str(warmup_status['current_day']) + '/20' if warmup_status['warmup_mode'] else 'Post-Warmup'}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Daily Message Cap</span>
                        <span class="metric-value-small">{messages_sent_today:,} / {warmup_status['daily_cap']:,}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Daily Lead Quota</span>
                        <span class="metric-value-small">{leads_today:,} / {int(warmup_status['leads_needed_today']):,}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Weekend Skip</span>
                        <span class="metric-value-small {'danger' if warmup_status['skip_today'] else ''}">{' Yes (Paused)' if warmup_status['skip_today'] else '✓ No (Active)'}</span>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">📧 Email Delivery Metrics</div>
                    <div class="metric-row">
                        <span class="metric-name">Delivery Rate</span>
                        <span class="metric-value">{delivery_rate:.1f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Open Rate</span>
                        <span class="metric-value">{open_rate:.1f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Click Rate</span>
                        <span class="metric-value">{click_rate:.1f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Reply Rate</span>
                        <span class="metric-value">{reply_rate:.1f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Bounce Rate</span>
                        <span class="metric-value danger">{bounce_rate:.1f}%</span>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">📥 Import Stats</div>
                    <div class="metric-row">
                        <span class="metric-name">Total Runs</span>
                        <span class="metric-value-small">{total_imports}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Leads Imported</span>
                        <span class="metric-value-small">{total_imported:,}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Duplicates Skipped</span>
                        <span class="metric-value-small">{total_duplicates:,}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Verified Emails</span>
                        <span class="metric-value-small">{verified_emails_count:,}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Success Rate</span>
                        <span class="metric-value-small">{(total_imported / (total_imported + total_duplicates) * 100) if (total_imported + total_duplicates) > 0 else 0:.1f}%</span>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">🔬 Enrichment Status</div>
                    <div class="metric-row">
                        <span class="metric-name">Enriched Leads</span>
                        <span class="metric-value-small">{total_enriched:,}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Pending (Tier 1-2)</span>
                        <span class="metric-value-small">{pending_enrichment:,}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Enrichment Rate</span>
                        <span class="metric-value-small">{(total_enriched / total_leads * 100) if total_leads > 0 else 0:.1f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-name">Today</span>
                        <span class="metric-value-small">{enriched_today}</span>
                    </div>
                </div>
            </div>
            
            <!-- Next Scheduled Tasks - Full Width -->
            <div class="card" style="margin-bottom: 2rem;">
                <div class="card-title">⏰ Next Scheduled Tasks</div>
                <div class="task-container">
                    {task_times_html}
                </div>
            </div>
            
            <!-- Distribution Metrics -->
            <div class="grid-2" style="margin-top: 2rem;">
                <div class="card">
                    <div class="card-title">🎯 Lead Distribution by Tier</div>
                    <div class="tier-grid">
                        <div class="tier-item">
                            <div class="tier-item-title">Tier 1</div>
                            <div class="tier-item-value">{tier_counts.get(1, 0)}</div>
                        </div>
                        <div class="tier-item">
                            <div class="tier-item-title">Tier 2</div>
                            <div class="tier-item-value">{tier_counts.get(2, 0)}</div>
                        </div>
                        <div class="tier-item">
                            <div class="tier-item-title">Tier 3</div>
                            <div class="tier-item-value">{tier_counts.get(3, 0)}</div>
                        </div>
                        <div class="tier-item">
                            <div class="tier-item-title">Tier 4</div>
                            <div class="tier-item-value">{tier_counts.get(4, 0)}</div>
                        </div>
                        <div class="tier-item">
                            <div class="tier-item-title">Tier 5</div>
                            <div class="tier-item-value">{tier_counts.get(5, 0)}</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">💬 Conversation States</div>
                    <ul class="state-list">
                        {"".join([
                            f'<li><span>{state.replace("_", " ").title()}</span><span>{count}</span></li>'
                            for state, count in state_counts.items()
                        ])}
                    </ul>
                </div>
            </div>
            
            <!-- Trend Chart -->
            <div class="card">
                <div class="card-title">📈 7-Day Lead Import Trend</div>
                <div class="trend-chart">
                    {"".join([
                        f'<div class="trend-bar" style="height: {max(5, (day["count"] / max([d["count"] for d in daily_leads] + [1])) * 100)}%">'
                        f'<span class="trend-label">{day["date"]}<br>{day["count"]}</span></div>'
                        for day in daily_leads
                    ])}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)
