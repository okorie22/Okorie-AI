"""
Inbound and Outbound Messages Dashboard.
Tracks messages sent and received via the messages table.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta

from ..storage.database import get_db
from ..storage.models import Message, MessageDirection, MessageChannel, Conversation, Lead

router = APIRouter(tags=["messages"])


@router.get("/messages", response_class=HTMLResponse)
async def messages_dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Inbound and outbound messages dashboard.
    Shows counts and recent activity from the messages table.
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    # Stats: total and today by direction
    total_outbound = db.query(Message).filter(Message.direction == MessageDirection.OUTBOUND).count()
    total_inbound = db.query(Message).filter(Message.direction == MessageDirection.INBOUND).count()
    outbound_today = db.query(Message).filter(
        Message.direction == MessageDirection.OUTBOUND,
        Message.created_at >= today_start,
    ).count()
    inbound_today = db.query(Message).filter(
        Message.direction == MessageDirection.INBOUND,
        Message.created_at >= today_start,
    ).count()

    # By channel (outbound)
    outbound_email = db.query(Message).filter(
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == MessageChannel.EMAIL,
    ).count()
    outbound_sms = db.query(Message).filter(
        Message.direction == MessageDirection.OUTBOUND,
        Message.channel == MessageChannel.SMS,
    ).count()
    inbound_email = db.query(Message).filter(
        Message.direction == MessageDirection.INBOUND,
        Message.channel == MessageChannel.EMAIL,
    ).count()
    inbound_sms = db.query(Message).filter(
        Message.direction == MessageDirection.INBOUND,
        Message.channel == MessageChannel.SMS,
    ).count()

    # Recent messages (last 7 days, join to get lead)
    recent = (
        db.query(Message, Conversation, Lead)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(Lead, Conversation.lead_id == Lead.id)
        .filter(Message.created_at >= week_start)
        .order_by(desc(Message.created_at))
        .limit(200)
        .all()
    )

    def safe_preview(body, max_len=120):
        if not body:
            return ""
        s = (body or "").strip().replace("\n", " ")
        return (s[:max_len] + "…") if len(s) > max_len else s

    def fmt_ts(dt):
        if not dt:
            return "—"
        return dt.strftime("%Y-%m-%d %H:%M") if hasattr(dt, "strftime") else str(dt)

    messages_html = ""
    for msg, conv, lead in recent:
        direction_label = "Inbound" if msg.direction == MessageDirection.INBOUND else "Outbound"
        direction_class = "msg-inbound" if msg.direction == MessageDirection.INBOUND else "msg-outbound"
        channel_label = (msg.channel or MessageChannel.EMAIL).value if msg.channel else "email"
        lead_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or lead.email or "—"
        preview = safe_preview(msg.body)
        meta = (msg.message_metadata or {})
        subject = meta.get("subject", "")
        messages_html += f"""
            <div class="message-card {direction_class}">
                <div class="message-meta">
                    <span class="message-direction">{direction_label}</span>
                    <span class="message-channel">{channel_label}</span>
                    <span class="message-time">{fmt_ts(msg.created_at)}</span>
                </div>
                <div class="message-lead">{lead_name} &lt;{lead.email or '—'}&gt;</div>
                <div class="message-subject">{subject or '—'}</div>
                <div class="message-preview">{preview or '—'}</div>
            </div>
        """

    if not recent:
        messages_html = """
        <div class="empty-state">
            <div class="empty-state-icon">💬</div>
            <p>No messages in the last 7 days. Outbound and inbound activity will appear here.</p>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="60">
        <title>Messages | IUL Appointment Setter</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 0;
            }}
            h1 {{ font-size: 2rem; margin-bottom: 0.5rem; color: #f1f5f9; }}
            .subtitle {{ color: #f1f5f9; margin-bottom: 2rem; font-size: 0.9rem; }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 2rem;
                background: transparent;
            }}
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
            .navbar-brand {{ font-size: 1.3rem; font-weight: 700; color: #667eea; }}
            .navbar-links {{ display: flex; gap: 1rem; }}
            .nav-link {{
                text-decoration: none;
                color: #4a5568;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                font-weight: 500;
                transition: all 0.3s;
            }}
            .nav-link:hover {{ background: #f7fafc; color: #667eea; }}
            .nav-link.active {{ background: #667eea; color: white; }}

            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 1.5rem;
                margin-bottom: 2rem;
            }}
            .stat-card {{
                background: white;
                padding: 1.5rem;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .stat-card h3 {{ color: #718096; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem; }}
            .stat-value {{ font-size: 2rem; font-weight: 700; color: #2d3748; }}
            .stat-subtitle {{ font-size: 0.85rem; color: #a0aec0; margin-top: 0.25rem; }}

            .section {{
                background: white;
                border-radius: 12px;
                padding: 2rem;
                margin-bottom: 2rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .section-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1.5rem;
                padding-bottom: 1rem;
                border-bottom: 2px solid #e2e8f0;
            }}
            .section-title {{ font-size: 1.5rem; font-weight: 700; color: #2d3748; }}
            .section-badge {{ background: #667eea; color: white; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.9rem; font-weight: 600; }}

            .message-card {{
                background: #f7fafc;
                padding: 1rem 1.25rem;
                margin-bottom: 0.75rem;
                border-radius: 8px;
                border-left: 4px solid #667eea;
                transition: all 0.3s;
            }}
            .message-card.msg-inbound {{ border-left-color: #48bb78; }}
            .message-card.msg-outbound {{ border-left-color: #667eea; }}
            .message-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
            .message-meta {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.5rem; font-size: 0.8rem; color: #718096; }}
            .message-direction {{ font-weight: 600; text-transform: uppercase; }}
            .message-channel {{ text-transform: uppercase; }}
            .message-lead {{ font-weight: 600; color: #2d3748; margin-bottom: 0.25rem; }}
            .message-subject {{ font-size: 0.9rem; color: #4a5568; margin-bottom: 0.35rem; }}
            .message-preview {{ font-size: 0.85rem; color: #718096; line-height: 1.4; }}

            .messages-list-scroll {{
                max-height: 50vh;
                min-height: 200px;
                overflow-y: auto;
                padding-right: 0.5rem;
            }}
            .messages-list-scroll::-webkit-scrollbar {{ width: 8px; }}
            .messages-list-scroll::-webkit-scrollbar-track {{ background: #e2e8f0; border-radius: 4px; }}
            .messages-list-scroll::-webkit-scrollbar-thumb {{ background: #a0aec0; border-radius: 4px; }}

            .empty-state {{ text-align: center; padding: 3rem; color: #a0aec0; }}
            .empty-state-icon {{ font-size: 3rem; margin-bottom: 1rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <nav class="navbar">
                <div class="navbar-brand">⚡ IUL Appointment Setter</div>
                <div class="navbar-links">
                    <a href="/dashboard/" class="nav-link">📊 Main Dashboard</a>
                    <a href="/appointments" class="nav-link">📅 Appointments & Deals</a>
                    <a href="/messages" class="nav-link active">💬 Messages</a>
                </div>
            </nav>

            <h1>💬 Inbound & Outbound Messages</h1>
            <div class="subtitle">
                Last updated: {now.strftime("%Y-%m-%d %H:%M:%S")} UTC • Auto-refresh every 60s
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <h3>📤 Outbound (total)</h3>
                    <div class="stat-value">{total_outbound}</div>
                    <div class="stat-subtitle">{outbound_today} today</div>
                </div>
                <div class="stat-card">
                    <h3>📥 Inbound (total)</h3>
                    <div class="stat-value">{total_inbound}</div>
                    <div class="stat-subtitle">{inbound_today} today</div>
                </div>
                <div class="stat-card">
                    <h3>📧 Outbound Email</h3>
                    <div class="stat-value">{outbound_email}</div>
                    <div class="stat-subtitle">Total sent via email</div>
                </div>
                <div class="stat-card">
                    <h3>📱 Outbound TEXT/SMS</h3>
                    <div class="stat-value">{outbound_sms}</div>
                    <div class="stat-subtitle">Total sent via SMS</div>
                </div>
                <div class="stat-card">
                    <h3>📧 Inbound Email</h3>
                    <div class="stat-value">{inbound_email}</div>
                    <div class="stat-subtitle">Replies via email</div>
                </div>
                <div class="stat-card">
                    <h3>📱 Inbound TEXT/SMS</h3>
                    <div class="stat-value">{inbound_sms}</div>
                    <div class="stat-subtitle">Replies via SMS</div>
                </div>
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Recent Messages (last 7 days)</h2>
                    <span class="section-badge">{len(recent)}</span>
                </div>
                <div class="messages-list-scroll">
                    {messages_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
