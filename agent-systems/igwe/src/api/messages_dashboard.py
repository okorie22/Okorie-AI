"""
Inbound and Outbound Messages Dashboard.
Tracks messages sent and received via the messages table.
"""
import json
from html import escape
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from ..storage.database import get_db
from ..storage.models import Message, MessageDirection, MessageChannel, Conversation, Lead
from ..channels.email import SendGridService

router = APIRouter(tags=["messages"])


def _messages_qs(direction: str, channel: str, **kw):
    p = {"direction": direction, "channel": channel}
    p.update(kw)
    return "?" + urlencode(p)


@router.get("/messages", response_class=HTMLResponse)
async def messages_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    direction: str = Query("all", description="Filter: all, inbound, outbound"),
    channel: str = Query("all", description="Filter: all, email, sms"),
):
    """
    Inbound and outbound messages dashboard with filters.
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

    # Recent messages (last 7 days), optional filters
    q = (
        db.query(Message, Conversation, Lead)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(Lead, Conversation.lead_id == Lead.id)
        .filter(Message.created_at >= week_start)
    )
    if direction == "inbound":
        q = q.filter(Message.direction == MessageDirection.INBOUND)
    elif direction == "outbound":
        q = q.filter(Message.direction == MessageDirection.OUTBOUND)
    if channel == "email":
        q = q.filter(Message.channel == MessageChannel.EMAIL)
    elif channel == "sms":
        q = q.filter(Message.channel == MessageChannel.SMS)
    recent = q.order_by(desc(Message.created_at)).limit(200).all()

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
        meta = (msg.message_metadata or {})
        if lead.email == "inbound-unknown@system":
            display_from = meta.get("from") or "—"
            lead_name = f"Unknown sender: {display_from}"
        else:
            lead_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or lead.email or "—"
            display_from = lead.email or "—"
        preview = safe_preview(msg.body)
        subject = meta.get("subject", "")
        body_esc = escape((msg.body or "").replace("\n", "<br>"))
        reply_subject = "Re: " + (subject or "your message") if subject else "Re: your message"
        reply_form = ""
        if msg.direction == MessageDirection.INBOUND and lead.email != "inbound-unknown@system":
            reply_form = f"""
                <div id="reply-form-{msg.id}" class="reply-form-row" style="display:none;">
                    <form method="post" action="/messages/send" class="reply-form">
                        <input type="hidden" name="conversation_id" value="{conv.id}">
                        <div class="form-group"><label>Subject</label><input type="text" name="subject" value="{escape(reply_subject)}"></div>
                        <div class="form-group"><label>Message</label><textarea name="body" rows="4" required></textarea></div>
                        <div class="form-actions"><button type="submit" class="btn btn-success">Send reply</button><button type="button" onclick="toggleReplyForm({msg.id})" class="btn btn-outline">Cancel</button></div>
                    </form>
                </div>
            """
        messages_html += f"""
            <div class="message-card {direction_class}" data-msg-id="{msg.id}">
                <div class="message-meta">
                    <span class="message-direction">{direction_label}</span>
                    <span class="message-channel">{channel_label}</span>
                    <span class="message-time">{fmt_ts(msg.created_at)}</span>
                    <button type="button" class="btn-link" onclick="toggleExpand({msg.id})">View full</button>
                    {f'<button type="button" class="btn-link" onclick="toggleReplyForm(' + str(msg.id) + ')">Reply</button>' if msg.direction == MessageDirection.INBOUND and lead.email != "inbound-unknown@system" else ''}
                </div>
                <div class="message-lead">{escape(lead_name)} &lt;{escape(display_from)}&gt;</div>
                <div class="message-subject">{escape(subject or "—")}</div>
                <div class="message-preview">{escape(preview or "—")}</div>
                <div id="msg-full-{msg.id}" class="message-full" style="display:none; margin-top:0.75rem; padding:0.75rem; background:#edf2f7; border-radius:6px; white-space:pre-wrap;">{(msg.body or "").replace("<", "&lt;").replace(">", "&gt;")}</div>
                {reply_form}
            </div>
        """

    if not recent:
        messages_html = """
        <div class="empty-state">
            <div class="empty-state-icon">💬</div>
            <p>No messages in the last 7 days. Outbound and inbound activity will appear here.</p>
        </div>
        """

    # Recent conversations for Compose dropdown (last 50 by last_message_at or updated_at)
    conv_q = (
        db.query(Conversation, Lead)
        .join(Lead, Conversation.lead_id == Lead.id)
        .filter(Lead.email != "inbound-unknown@system")
        .order_by(desc(Conversation.updated_at))
        .limit(50)
    )
    recent_conversations = [(c, lead) for c, lead in conv_q.all()]

    # Filter links (direction, channel) – build once for template
    qs_all_all = _messages_qs("all", "all")
    qs_inbound = _messages_qs("inbound", channel)
    qs_outbound = _messages_qs("outbound", channel)
    qs_email = _messages_qs(direction, "email")
    qs_sms = _messages_qs(direction, "sms")

    send_status = []
    if request.query_params.get("sent") == "1":
        send_status.append(('success', 'Message sent.'))
    if request.query_params.get("send_error") == "1":
        reason = (request.query_params.get("reason") or "").strip()
        msg = "Could not send message."
        if reason:
            msg += f" Reason: {reason}"
        else:
            msg += " Check lead suppression and rate limits."
        send_status.append(('error', msg))

    # For typeahead: id, label, email, search (lowercased name + email)
    conversations_for_js = []
    for c, lead in recent_conversations:
        name = ("%s %s" % (lead.first_name or "", lead.last_name or "")).strip() or lead.email or "—"
        email = (lead.email or "").strip()
        search = (name + " " + email).lower()
        conversations_for_js.append({"id": c.id, "label": name, "email": email, "search": search})
    conversations_js_embed = json.dumps(conversations_for_js).replace("</script>", "</scr\" + \"ipt>")

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
            .filter-row {{ display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; margin-bottom: 1rem; }}
            .filter-group {{ display: flex; gap: 0.5rem; align-items: center; }}
            .filter-group label {{ font-size: 0.85rem; color: #718096; margin-right: 0.25rem; }}
            .filter-link {{ padding: 0.35rem 0.75rem; border-radius: 6px; text-decoration: none; font-size: 0.9rem; background: #edf2f7; color: #4a5568; }}
            .filter-link:hover {{ background: #e2e8f0; color: #2d3748; }}
            .filter-link.active {{ background: #667eea; color: white; }}
            .reply-form-row {{ margin-top: 0.75rem; padding: 1rem; background: #f7fafc; border-radius: 8px; border: 1px solid #e2e8f0; }}
            .reply-form .form-group {{ margin-bottom: 0.75rem; }}
            .reply-form .form-group label {{ display: block; font-size: 0.85rem; font-weight: 600; color: #4a5568; margin-bottom: 0.25rem; }}
            .reply-form .form-actions {{ display: flex; gap: 0.5rem; margin-top: 0.75rem; }}
            .compose-section {{ margin-bottom: 1.5rem; padding: 1rem; background: #f0fff4; border: 1px solid #9ae6b4; border-radius: 8px; }}
            .compose-section h3 {{ font-size: 1rem; margin-bottom: 0.75rem; color: #276749; }}
            .compose-section .reply-form textarea[name="body"] {{ width: 100%; min-width: 520px; box-sizing: border-box; max-width: 900px; }}
            .compose-to-wrap {{ position: relative; max-width: 520px; }}
            .compose-to-wrap input[type="text"] {{ width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 1rem; box-sizing: border-box; }}
            .compose-to-suggestions {{ position: absolute; top: 100%; left: 0; right: 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; max-height: 220px; overflow-y: auto; z-index: 20; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
            .compose-to-suggestions li {{ list-style: none; padding: 0.5rem 0.75rem; cursor: pointer; border-bottom: 1px solid #f0f0f0; }}
            .compose-to-suggestions li:hover {{ background: #edf2f7; }}
            .compose-to-suggestions li:last-child {{ border-bottom: none; }}
            .btn-link {{ background: none; border: none; color: #667eea; cursor: pointer; font-size: 0.9rem; padding: 0 0.25rem; }}
            .btn-link:hover {{ text-decoration: underline; }}
            .btn {{ padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600; cursor: pointer; border: 1px solid transparent; font-size: 0.9rem; }}
            .btn-primary {{ background: #667eea; color: white; }}
            .btn-primary:hover {{ background: #5a67d8; }}
            .btn-success {{ background: #48bb78; color: white; }}
            .btn-success:hover {{ background: #38a169; }}
            .btn-outline {{ background: transparent; color: #4a5568; border-color: #e2e8f0; }}
            .btn-outline:hover {{ background: #f7fafc; }}
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
            {"".join(f'<div class="alert alert-{k}" style="margin-bottom:1rem; padding:0.75rem 1rem; border-radius:8px; background:{"#c6f6d5" if k=="success" else "#fed7d7"}; color:{"#22543d" if k=="success" else "#822727"};">{escape(v)}</div>' for k, v in send_status)}

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
                    <div style="display:flex; align-items:center; gap:1rem;">
                        <button type="button" class="btn btn-primary" onclick="toggleCompose()">✉️ Compose</button>
                        <span class="section-badge">{len(recent)}</span>
                    </div>
                </div>
                <div id="compose-form-wrap" class="compose-section" style="display:none;">
                    <h3>New message</h3>
                    <form method="post" action="/messages/send" class="reply-form" id="compose-form">
                        <div class="form-group">
                            <label>To (type email or select from suggestions)</label>
                            <div class="compose-to-wrap">
                                <input type="email" name="to_email" id="compose-to-search" placeholder="email@example.com" autocomplete="off" required>
                                <input type="hidden" name="conversation_id" id="compose-conversation-id">
                                <ul id="compose-to-suggestions" class="compose-to-suggestions" style="display:none;"></ul>
                            </div>
                        </div>
                        <div class="form-group"><label>Subject</label><input type="text" name="subject" required placeholder="Subject"></div>
                        <div class="form-group"><label>Message</label><textarea name="body" rows="4" required placeholder="Your message"></textarea></div>
                        <div class="form-actions"><button type="submit" class="btn btn-success">Send</button><button type="button" onclick="toggleCompose()" class="btn btn-outline">Cancel</button></div>
                    </form>
                </div>
                <div class="filter-row">
                    <div class="filter-group">
                        <label>Direction:</label>
                        <a href="/messages{qs_all_all}" class="filter-link {"active" if direction == "all" else ""}">All</a>
                        <a href="/messages{qs_inbound}" class="filter-link {"active" if direction == "inbound" else ""}">Inbound</a>
                        <a href="/messages{qs_outbound}" class="filter-link {"active" if direction == "outbound" else ""}">Outbound</a>
                    </div>
                    <div class="filter-group">
                        <label>Channel:</label>
                        <a href="/messages{qs_all_all if channel == "all" else _messages_qs(direction, "all")}" class="filter-link {"active" if channel == "all" else ""}">All</a>
                        <a href="/messages{qs_email}" class="filter-link {"active" if channel == "email" else ""}">Email</a>
                        <a href="/messages{qs_sms}" class="filter-link {"active" if channel == "sms" else ""}">SMS</a>
                    </div>
                </div>
                <div class="messages-list-scroll">
                    {messages_html}
                </div>
            </div>
        </div>
        <script>
        var CONVERSATIONS = {conversations_js_embed};

        function toggleExpand(msgId) {{
            var el = document.getElementById("msg-full-" + msgId);
            if (!el) return;
            var card = el.closest(".message-card");
            var viewLink = card ? card.querySelector(".message-meta .btn-link") : null;
            el.style.display = el.style.display === "none" ? "block" : "none";
            if (viewLink) viewLink.textContent = el.style.display === "none" ? "View full" : "Collapse";
        }}
        function toggleReplyForm(msgId) {{
            var el = document.getElementById("reply-form-" + msgId);
            if (el) el.style.display = el.style.display === "none" ? "block" : "none";
        }}
        function toggleCompose() {{
            var wrap = document.getElementById("compose-form-wrap");
            if (wrap) {{
                wrap.style.display = wrap.style.display === "none" ? "block" : "none";
                if (wrap.style.display === "block") {{
                    var s = document.getElementById("compose-to-search");
                    var h = document.getElementById("compose-conversation-id");
                    var ul = document.getElementById("compose-to-suggestions");
                    if (s) s.value = "";
                    if (h) h.value = "";
                    if (ul) {{ ul.style.display = "none"; ul.innerHTML = ""; }}
                }}
            }}
        }}
        (function() {{
            var searchEl = document.getElementById("compose-to-search");
            var hiddenEl = document.getElementById("compose-conversation-id");
            var ul = document.getElementById("compose-to-suggestions");
            var form = document.getElementById("compose-form");
            if (!searchEl || !hiddenEl || !ul || !form) return;

            function esc(s) {{ var t = (s || '').toString(); return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}
            function showSuggestions(query) {{
                query = (query || "").trim().toLowerCase();
                if (!query) {{ ul.style.display = "none"; ul.innerHTML = ""; return; }}
                var list = CONVERSATIONS.filter(function(c) {{ return c.search.indexOf(query) >= 0; }}).slice(0, 12);
                ul.innerHTML = list.map(function(c) {{
                    var lab = esc(c.label), em = esc(c.email);
                    return '<li data-id="' + c.id + '" data-label="' + (c.label || '').replace(/"/g, '&quot;') + '" data-email="' + (c.email || '').replace(/"/g, '&quot;') + '">' + (lab && em ? lab + ' &lt;' + em + '&gt;' : (em || lab)) + '</li>';
                }}).join("");
                ul.style.display = list.length ? "block" : "none";
            }}
            searchEl.addEventListener("input", function() {{
                hiddenEl.value = "";
                showSuggestions(searchEl.value);
            }});
            searchEl.addEventListener("focus", function() {{ showSuggestions(searchEl.value); }});
            ul.addEventListener("click", function(e) {{
                var li = e.target.closest("li[data-id]");
                if (!li) return;
                var id = li.getAttribute("data-id");
                var c = CONVERSATIONS.filter(function(x) {{ return String(x.id) === String(id); }})[0];
                if (!c) return;
                hiddenEl.value = id;
                searchEl.value = c.email || "";
                ul.style.display = "none";
                ul.innerHTML = "";
            }});
            document.addEventListener("click", function(e) {{
                if (!searchEl.contains(e.target) && !ul.contains(e.target)) ul.style.display = "none";
            }});
            form.addEventListener("submit", function(e) {{
                // Allow raw email submission - no need to select from list
                var emailVal = searchEl.value.trim();
                if (!emailVal) {{
                    e.preventDefault();
                    alert("Please enter a recipient email address.");
                    return;
                }}
            }});
        }})();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/messages/send", response_class=RedirectResponse)
async def messages_send(
    db: Session = Depends(get_db),
    conversation_id: Optional[int] = Form(None),
    to_email: Optional[str] = Form(None),
    subject: str = Form(...),
    body: str = Form(...),
):
    """
    Send an outbound email. Accepts either conversation_id OR to_email.
    If to_email provided, finds or creates lead and conversation.
    Redirects to /messages on success or /messages?send_error=1 on failure.
    """
    from ..storage.repositories import LeadRepository, ConversationRepository
    from ..storage.models import MessageChannel
    
    lead = None
    conv = None
    
    # Try conversation_id first (from dropdown selection)
    if conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv:
            lead = db.query(Lead).filter(Lead.id == conv.lead_id).first()
    
    # Fall back to raw email (typed directly)
    if not lead and to_email:
        to_email_clean = to_email.strip().lower()
        lead_repo = LeadRepository(db)
        lead = lead_repo.get_by_email(to_email_clean)
        
        # Create lead if doesn't exist
        if not lead:
            # Extract name from email if possible
            email_name = to_email_clean.split("@")[0]
            lead = lead_repo.create({
                "email": to_email_clean,
                "first_name": email_name.capitalize(),
                "last_name": "",
            })
        
        # Get or create conversation
        conv_repo = ConversationRepository(db)
        conv = conv_repo.get_active_by_lead(lead.id)
        if not conv:
            conv = conv_repo.create(lead.id, MessageChannel.EMAIL.value)
    
    # If this was a manual compose (to_email provided), force-enable sending for testing.
    # Your SendGridService enforces verification gates; this override lets you send immediately.
    if lead and to_email:
        try:
            now = datetime.now(timezone.utc)
            lead.suppression_reason = None
            lead.email_deliverable = True
            lead.email_verification_status = "MANUAL_OVERRIDE"
            lead.email_verified_at = now
            db.add(lead)
            db.commit()
        except Exception:
            db.rollback()

    # Validate we have everything
    if not lead or not conv or not lead.email or lead.email == "inbound-unknown@system":
        return RedirectResponse(url="/messages?send_error=1&reason=invalid_recipient", status_code=303)
    svc = SendGridService(db)
    out = svc.send_email(
        to_email=lead.email,
        subject=subject.strip(),
        body=(body or "").strip(),
        lead_id=lead.id,
        conversation_id=conv.id,
    )
    if out.get("success"):
        return RedirectResponse(url="/messages?sent=1", status_code=303)
    reason = (out.get("error") or "unknown_error").strip()
    # Keep it short so querystring doesn't explode
    reason = reason[:160]
    return RedirectResponse(url=f"/messages?send_error=1&{urlencode({'reason': reason})}", status_code=303)
