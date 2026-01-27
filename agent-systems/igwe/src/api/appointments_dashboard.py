"""
Appointments and Deals Management Dashboard.
Allows tracking of scheduled appointments and closed deals.
"""
from html import escape
from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from urllib.parse import urlencode

from ..storage.database import get_db
from ..storage.models import (
    Appointment, AppointmentStatus, UnmatchedAppointment,
    Deal, Lead, Conversation, ConversationState, MessageChannel,
)

router = APIRouter(tags=["appointments"])


def _pagination_qs(upcoming_page, unmatched_page, past_page, deals_page, per_page, **overrides):
    p = {
        "upcoming_page": upcoming_page,
        "unmatched_page": unmatched_page,
        "past_page": past_page,
        "deals_page": deals_page,
        "per_page": per_page,
    }
    p.update(overrides)
    return "?" + urlencode(p)


@router.get("/appointments", response_class=HTMLResponse)
async def appointments_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    upcoming_page: int = Query(1, ge=1, description="Upcoming page"),
    unmatched_page: int = Query(1, ge=1, description="Unmatched page"),
    past_page: int = Query(1, ge=1, description="Past page"),
    deals_page: int = Query(1, ge=1, description="Deals page"),
    per_page: int = Query(15, ge=1, le=100, description="Rows per section"),
):
    """
    Appointments and deals management dashboard.
    Shows upcoming appointments, past appointments needing review, and closed deals.
    Uses compact rows and per-section pagination (default 15 per page).
    """
    now = datetime.utcnow()
    past_cutoff = now - timedelta(days=14)
    unmatched_cutoff_future = now + timedelta(days=30)
    deals_cutoff = now - timedelta(days=90)

    # Full lists (for totals and slicing)
    upcoming_all = db.query(Appointment, Lead).join(Lead).filter(
        Appointment.scheduled_at >= now,
        Appointment.status.in_([
            AppointmentStatus.PENDING,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.REMINDED_24H,
            AppointmentStatus.REMINDED_2H
        ])
    ).order_by(Appointment.scheduled_at).all()

    past_appointments_all = db.query(Appointment, Lead).join(Lead).filter(
        Appointment.scheduled_at >= past_cutoff,
        Appointment.scheduled_at < now,
        Appointment.status.in_([
            AppointmentStatus.PENDING,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.REMINDED_24H,
            AppointmentStatus.REMINDED_2H,
            AppointmentStatus.NO_SHOW
        ])
    ).order_by(Appointment.scheduled_at.desc()).all()

    existing_ceids = set(
        r[0] for r in db.query(Appointment.calendly_event_id).filter(
            Appointment.calendly_event_id.isnot(None)
        ).all()
    )
    past_unmatched_q = db.query(UnmatchedAppointment).filter(
        UnmatchedAppointment.scheduled_at >= past_cutoff,
        UnmatchedAppointment.scheduled_at < now,
        UnmatchedAppointment.status.in_(["active", "no_show"]),
    ).order_by(UnmatchedAppointment.scheduled_at.desc()).all()
    past_unmatched_all = [u for u in past_unmatched_q if u.calendly_event_id not in existing_ceids]

    # Combined past list for ordering and pagination: (scheduled_at, 'linked', appt, lead, None) or ('unmatched', None, None, u)
    past_combined = [
        (a.scheduled_at, "linked", a, lead, None) for a, lead in past_appointments_all
    ] + [(u.scheduled_at, "unmatched", None, None, u) for u in past_unmatched_all]
    past_combined.sort(key=lambda x: x[0], reverse=True)
    total_past = len(past_combined)
    past_start = (past_page - 1) * per_page
    past_slice = past_combined[past_start : past_start + per_page]

    unmatched_all = db.query(UnmatchedAppointment).filter(
        UnmatchedAppointment.status == "active",
        UnmatchedAppointment.scheduled_at >= now,
        UnmatchedAppointment.scheduled_at <= unmatched_cutoff_future,
    ).order_by(UnmatchedAppointment.scheduled_at).all()

    closed_deals_all = db.query(Deal, Lead, Appointment).join(
        Lead, Deal.lead_id == Lead.id
    ).outerjoin(
        Appointment, Deal.appointment_id == Appointment.id
    ).filter(
        Deal.created_at >= deals_cutoff,
        Deal.status == "paid"
    ).order_by(Deal.created_at.desc()).all()

    # Paginate each section
    total_scheduled = len(upcoming_all)
    total_unmatched = len(unmatched_all)
    total_deals = len(closed_deals_all)
    upcoming_slice = upcoming_all[(upcoming_page - 1) * per_page : (upcoming_page * per_page)]
    unmatched_slice = unmatched_all[(unmatched_page - 1) * per_page : (unmatched_page * per_page)]
    deals_slice = closed_deals_all[(deals_page - 1) * per_page : (deals_page * per_page)]

    # Stats (use full counts)
    total_pending_review = total_past
    total_upcoming_appointments = total_scheduled + total_unmatched
    # Exclude "linked" and "canceled" unmatched so we don't double-count events that are now in appointments
    total_booked = (
        db.query(Appointment).count()
        + db.query(UnmatchedAppointment).filter(
            UnmatchedAppointment.status.in_(["active", "no_show"])
        ).count()
    )
    total_revenue = sum(deal[0].premium_amount or 0 for deal in closed_deals_all)
    total_commission = sum(deal[0].commission_amount or 0 for deal in closed_deals_all)
    
    # Calculate show rate / close rate (use full DB counts)
    showed_count = db.query(Appointment).filter(
        Appointment.status == AppointmentStatus.COMPLETED,
        Appointment.scheduled_at >= deals_cutoff
    ).count()
    total_past_outcomes = showed_count + db.query(Appointment).filter(
        Appointment.status == AppointmentStatus.NO_SHOW,
        Appointment.scheduled_at >= deals_cutoff
    ).count()
    show_rate = (showed_count / total_past_outcomes * 100) if total_past_outcomes > 0 else 0
    appointments_with_outcome = db.query(Appointment).filter(
        Appointment.status == AppointmentStatus.COMPLETED,
        Appointment.scheduled_at >= deals_cutoff
    ).count()
    close_rate = (total_deals / appointments_with_outcome * 100) if appointments_with_outcome > 0 else 0

    qs = lambda **kw: _pagination_qs(upcoming_page, unmatched_page, past_page, deals_page, per_page, **kw)

    # Build upcoming appointments HTML (compact table)
    upcoming_html = ""
    if upcoming_slice:
        upcoming_html = '<table class="compact-table"><thead><tr><th>Name</th><th>Email</th><th>Date</th><th>Time</th><th>Link</th></tr></thead><tbody>'
        for appointment, lead in upcoming_slice:
            name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "—"
            meeting_cell = f'<a href="{appointment.meeting_url}" style="color:#667eea;">Meeting</a>' if appointment.meeting_url else "—"
            upcoming_html += f'<tr class="compact-row"><td>{name}</td><td>{lead.email or "—"}</td><td>{appointment.scheduled_at.strftime("%b %d, %Y")}</td><td>{appointment.scheduled_at.strftime("%I:%M %p")} {appointment.timezone or ""}</td><td>{meeting_cell}</td></tr>'
        upcoming_html += "</tbody></table>"
    else:
        upcoming_html = '<div class="empty-state"><div class="empty-state-icon">📭</div><p>No upcoming appointments</p></div>'
    upcoming_pagination = ""
    if total_scheduled > per_page:
        start = (upcoming_page - 1) * per_page + 1
        end = min(upcoming_page * per_page, total_scheduled)
        prev_link = f'<a href="/appointments{qs(upcoming_page=upcoming_page - 1)}">‹ Previous</a>' if upcoming_page > 1 else '<span class="pagination-disabled">‹ Previous</span>'
        next_link = f'<a href="/appointments{qs(upcoming_page=upcoming_page + 1)}">Next ›</a>' if end < total_scheduled else '<span class="pagination-disabled">Next ›</span>'
        upcoming_pagination = f'<div class="pagination-bar">Showing {start}–{end} of {total_scheduled} {prev_link} {next_link}</div>'
    
    # Build past appointments HTML (compact table: linked + past unmatched from past_slice)
    past_html = ""
    if past_slice:
        past_html = '<table class="compact-table"><thead><tr><th>Name</th><th>Email</th><th>Date</th><th>Time</th><th>Actions</th></tr></thead><tbody>'
        for _at, typ, appt, lead, u in past_slice:
            if typ == "linked":
                name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "—"
                email = lead.email or "—"
                dt = appt.scheduled_at
                tz = appt.timezone or ""
                actions = f'''
                <form method="post" action="/appointments/{appt.id}/update-status" style="display:inline;"><input type="hidden" name="status" value="showed"><button type="submit" class="btn btn-success">✅ Showed</button></form>
                <form method="post" action="/appointments/{appt.id}/update-status" style="display:inline;"><input type="hidden" name="status" value="no_show"><button type="submit" class="btn btn-danger">❌ No Show</button></form>
                <button onclick="toggleDealForm({appt.id})" class="btn btn-primary">💰 Deal</button>
                <form method="post" action="/appointments/{appt.id}/mark-lost" style="display:inline;"><button type="submit" class="btn btn-outline">🚫 No Sale</button></form>'''
                past_html += f'<tr class="compact-row"><td>{name}</td><td>{email}</td><td>{dt.strftime("%b %d, %Y")}</td><td>{dt.strftime("%I:%M %p")} {tz}</td><td class="compact-actions">{actions}</td></tr>'
                past_html += f'<tr id="deal-form-{appt.id}" class="deal-form-row"><td colspan="5" class="deal-form-cell"><div class="deal-form"><form method="post" action="/appointments/{appt.id}/close-deal"><div class="form-group"><label>Premium ($)</label><input type="number" name="premium_amount" step="0.01" required placeholder="50000"></div><div class="form-group"><label>Commission ($)</label><input type="number" name="commission_amount" step="0.01" required placeholder="5000"></div><div class="form-actions"><button type="submit" class="btn btn-success">Submit</button><button type="button" onclick="toggleDealForm({appt.id})" class="btn btn-outline">Cancel</button></div></form></div></td></tr>'
            else:
                name = (u.invitee_name or "No name").strip() or "—"
                email = u.invitee_email or "—"
                dt = u.scheduled_at
                tz = u.timezone or "UTC"
                actions = f'''
                <form method="post" action="/appointments/unmatched/{u.id}/update-status" style="display:inline;"><input type="hidden" name="status" value="showed"><button type="submit" class="btn btn-success">✅ Showed</button></form>
                <form method="post" action="/appointments/unmatched/{u.id}/update-status" style="display:inline;"><input type="hidden" name="status" value="no_show"><button type="submit" class="btn btn-danger">❌ No Show</button></form>
                <button onclick="toggleDealForm(\'u-{u.id}\')" class="btn btn-primary">💰 Deal</button>'''
                past_html += f'<tr class="compact-row unmatched-row"><td>{name}</td><td>{email}</td><td>{dt.strftime("%b %d, %Y")}</td><td>{dt.strftime("%I:%M %p")} {tz}</td><td class="compact-actions">{actions}</td></tr>'
                past_html += f'<tr id="deal-form-u-{u.id}" class="deal-form-row"><td colspan="5" class="deal-form-cell"><div class="deal-form"><form method="post" action="/appointments/unmatched/{u.id}/close-deal"><div class="form-group"><label>Premium ($)</label><input type="number" name="premium_amount" step="0.01" required placeholder="50000"></div><div class="form-group"><label>Commission ($)</label><input type="number" name="commission_amount" step="0.01" required placeholder="5000"></div><div class="form-actions"><button type="submit" class="btn btn-success">Submit</button><button type="button" onclick="toggleDealForm(\'u-{u.id}\')" class="btn btn-outline">Cancel</button></div></form></div></td></tr>'
        past_html += "</tbody></table>"
    else:
        past_html = '<div class="empty-state"><div class="empty-state-icon">✅</div><p>All appointments have been reviewed!</p></div>'
    past_pagination = ""
    if total_past > per_page:
        start = (past_page - 1) * per_page + 1
        end = min(past_page * per_page, total_past)
        prev_link = f'<a href="/appointments{qs(past_page=past_page - 1)}">‹ Previous</a>' if past_page > 1 else '<span class="pagination-disabled">‹ Previous</span>'
        next_link = f'<a href="/appointments{qs(past_page=past_page + 1)}">Next ›</a>' if end < total_past else '<span class="pagination-disabled">Next ›</span>'
        past_pagination = f'<div class="pagination-bar">Showing {start}–{end} of {total_past} {prev_link} {next_link}</div>'
    
    # Build closed deals HTML (compact table, editable)
    deals_html = ""
    if deals_slice:
        deals_html = '<table class="compact-table"><thead><tr><th>Name</th><th>Company</th><th>Premium</th><th>Commission</th><th>Closed</th><th>Actions</th></tr></thead><tbody>'
        for deal, lead, appointment in deals_slice:
            name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "—"
            company = (lead.company_name or "—") + (" • " + (lead.job_title or "") if lead.job_title else "")
            fn_esc, ln_esc, co_esc = escape(lead.first_name or ""), escape(lead.last_name or ""), escape(lead.company_name or "")
            deals_html += f'<tr class="compact-row"><td>{name}</td><td>{company}</td><td>${(deal.premium_amount or 0):,.0f}</td><td>${(deal.commission_amount or 0):,.0f}</td><td>{deal.created_at.strftime("%b %d, %Y")}</td><td><button type="button" onclick="toggleDealEdit({deal.id})" class="btn btn-outline">✏️ Edit</button></td></tr>'
            deals_html += f'<tr id="deal-edit-{deal.id}" class="deal-form-row"><td colspan="6" class="deal-form-cell"><form method="post" action="/appointments/deals/{deal.id}/update"><div class="deal-form-inline"><div class="form-group"><label>Premium ($)</label><input type="number" name="premium_amount" step="0.01" value="{deal.premium_amount or 0}" required></div><div class="form-group"><label>Commission ($)</label><input type="number" name="commission_amount" step="0.01" value="{deal.commission_amount or 0}" required></div><div class="form-group"><label>First name</label><input type="text" name="first_name" value="{fn_esc}"></div><div class="form-group"><label>Last name</label><input type="text" name="last_name" value="{ln_esc}"></div><div class="form-group"><label>Company</label><input type="text" name="company_name" value="{co_esc}"></div><div class="form-actions"><button type="submit" class="btn btn-success">Save</button><button type="button" onclick="toggleDealEdit({deal.id})" class="btn btn-outline">Cancel</button></div></div></form></td></tr>'
        deals_html += "</tbody></table>"
    else:
        deals_html = '<div class="empty-state"><div class="empty-state-icon">🎯</div><p>No closed deals yet. Keep going!</p></div>'
    deals_pagination = ""
    if total_deals > per_page:
        start = (deals_page - 1) * per_page + 1
        end = min(deals_page * per_page, total_deals)
        prev_link = f'<a href="/appointments{qs(deals_page=deals_page - 1)}">‹ Previous</a>' if deals_page > 1 else '<span class="pagination-disabled">‹ Previous</span>'
        next_link = f'<a href="/appointments{qs(deals_page=deals_page + 1)}">Next ›</a>' if end < total_deals else '<span class="pagination-disabled">Next ›</span>'
        deals_pagination = f'<div class="pagination-bar">Showing {start}–{end} of {total_deals} {prev_link} {next_link}</div>'

    # Build unmatched appointments HTML (compact table)
    unmatched_html = ""
    if unmatched_slice:
        unmatched_html = '<table class="compact-table"><thead><tr><th>Name</th><th>Email</th><th>Date</th><th>Time</th></tr></thead><tbody>'
        for u in unmatched_slice:
            name = (u.invitee_name or "No name").strip() or "—"
            link_cell = f'<a href="{u.meeting_url}" style="color:#667eea;">Meet</a>' if u.meeting_url else "—"
            unmatched_html += f'<tr class="compact-row unmatched-row"><td>{name}</td><td>{u.invitee_email or "—"}</td><td>{u.scheduled_at.strftime("%b %d, %Y")}</td><td>{u.scheduled_at.strftime("%I:%M %p")} {u.timezone or "UTC"}</td></tr>'
        unmatched_html += "</tbody></table>"
    else:
        unmatched_html = '<div class="empty-state"><div class="empty-state-icon">✓</div><p>No unmatched Calendly events. Every appointment is linked to a lead.</p></div>'
    unmatched_pagination = ""
    if total_unmatched > per_page:
        start = (unmatched_page - 1) * per_page + 1
        end = min(unmatched_page * per_page, total_unmatched)
        prev_link = f'<a href="/appointments{qs(unmatched_page=unmatched_page - 1)}">‹ Previous</a>' if unmatched_page > 1 else '<span class="pagination-disabled">‹ Previous</span>'
        next_link = f'<a href="/appointments{qs(unmatched_page=unmatched_page + 1)}">Next ›</a>' if end < total_unmatched else '<span class="pagination-disabled">Next ›</span>'
        unmatched_pagination = f'<div class="pagination-bar">Showing {start}–{end} of {total_unmatched} {prev_link} {next_link}</div>'
    
    # Return inline HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="60">
        <title>Appointments & Deals | IUL Appointment Setter</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 0;
            }}
             h1 {{ 
                font-size: 2rem; 
                margin-bottom: 0.5rem;
                color: #f1f5f9;
            }}
            .subtitle {{ 
                color: #f1f5f9;
                margin-bottom: 2rem;
                font-size: 0.9rem;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 2rem;
                background: transparent;
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
            
            /* Stats Grid */
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 1.5rem;
                margin-bottom: 2rem;
            }}
            @media (max-width: 900px) {{
                .stats-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            }}
            @media (max-width: 500px) {{
                .stats-grid {{ grid-template-columns: 1fr; }}
            }}
            
            .stat-card {{
                background: white;
                padding: 1.5rem;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .stat-card h3 {{
                color: #718096;
                font-size: 0.85rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 0.5rem;
            }}
            
            .stat-value {{
                font-size: 2rem;
                font-weight: 700;
                color: #2d3748;
            }}
            
            .stat-subtitle {{
                font-size: 0.85rem;
                color: #a0aec0;
                margin-top: 0.25rem;
            }}
            
            /* Section */
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
            
            .section-title {{
                font-size: 1.5rem;
                font-weight: 700;
                color: #2d3748;
            }}
            
            .section-badge {{
                background: #667eea;
                color: white;
                padding: 0.25rem 0.75rem;
                border-radius: 12px;
                font-size: 0.9rem;
                font-weight: 600;
            }}
            
            /* Appointment Card */
            .appointment-card {{
                background: #f7fafc;
                border-left: 4px solid #667eea;
                padding: 1.5rem;
                margin-bottom: 1rem;
                border-radius: 8px;
                transition: all 0.3s;
            }}
            
            .appointment-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }}
            
            .appointment-header {{
                display: flex;
                justify-content: space-between;
                align-items: start;
                margin-bottom: 0.5rem;
            }}
            
            .appointment-lead {{
                font-size: 1.2rem;
                font-weight: 600;
                color: #2d3748;
            }}
            
            .appointment-company {{
                color: #718096;
                font-size: 0.9rem;
                margin-top: 0.25rem;
            }}
            
            .appointment-time {{
                background: white;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                font-weight: 500;
                color: #667eea;
                text-align: right;
            }}
            
            .appointment-actions {{
                display: flex;
                gap: 0.5rem;
                margin-top: 1rem;
                flex-wrap: wrap;
            }}
            
            /* Buttons */
            .btn {{
                padding: 0.5rem 1rem;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s;
                text-decoration: none;
                display: inline-block;
                font-size: 0.9rem;
            }}
            
            .btn-success {{
                background: #48bb78;
                color: white;
            }}
            
            .btn-success:hover {{
                background: #38a169;
            }}
            
            .btn-danger {{
                background: #f56565;
                color: white;
            }}
            
            .btn-danger:hover {{
                background: #e53e3e;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a67d8;
            }}
            
            .btn-outline {{
                background: white;
                color: #667eea;
                border: 2px solid #667eea;
            }}
            
            .btn-outline:hover {{
                background: #667eea;
                color: white;
            }}
            
            /* Deal Form */
            .deal-form {{
                display: none;
                background: white;
                border: 2px solid #667eea;
                padding: 1rem;
                margin-top: 1rem;
                border-radius: 8px;
            }}
            
            .deal-form.active {{
                display: block;
            }}
            
            .form-group {{
                margin-bottom: 1rem;
            }}
            
            .form-group label {{
                display: block;
                margin-bottom: 0.5rem;
                font-weight: 500;
                color: #4a5568;
            }}
            
            .form-group input {{
                width: 100%;
                padding: 0.5rem;
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                font-size: 1rem;
            }}
            
            .form-actions {{
                display: flex;
                gap: 0.5rem;
                margin-top: 1rem;
            }}
            
            .empty-state {{
                text-align: center;
                padding: 3rem;
                color: #a0aec0;
            }}
            .alert {{
                background: #16a34a;
                color: white;
                padding: 1rem;
                border-radius: 8px;
                margin-bottom: 1.5rem;
            }}

            .empty-state-icon {{
                font-size: 3rem;
                margin-bottom: 1rem;
            }}
            
            /* Status Badge */
            .status-badge {{
                padding: 0.25rem 0.75rem;
                border-radius: 12px;
                font-size: 0.75rem;
                font-weight: 600;
                text-transform: uppercase;
            }}
            
            .status-pending {{ background: #fef5e7; color: #d68910; }}
            .status-confirmed {{ background: #e8f4f8; color: #117a8b; }}
            .status-no-show {{ background: #f8d7da; color: #721c24; }}
            .status-no_show {{ background: #f8d7da; color: #721c24; }}
            .status-completed {{ background: #d4edda; color: #155724; }}
            .status-showed {{ background: #d4edda; color: #155724; }}
            .status-reminded_24h {{ background: #e8f4f8; color: #117a8b; }}
            .status-reminded_2h {{ background: #e8f4f8; color: #117a8b; }}

            .compact-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
            .compact-table th {{ text-align: left; padding: 0.5rem 0.75rem; background: #e2e8f0; font-weight: 600; color: #4a5568; border-bottom: 2px solid #cbd5e0; }}
            .compact-table td {{ padding: 0.4rem 0.75rem; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }}
            .compact-row:hover {{ background: #edf2f7; }}
            .compact-row.unmatched-row {{ border-left: 3px solid #ed8936; }}
            .compact-actions {{ white-space: nowrap; }}
            .compact-actions .btn {{ padding: 0.3rem 0.6rem; font-size: 0.8rem; }}
            .compact-actions form {{ display: inline; }}
            .deal-form-row {{ display: none; }}
            .deal-form-row.visible {{ display: table-row; }}
            .deal-form-cell {{ background: #f7fafc; padding: 0.75rem 1rem; border-bottom: 1px solid #e2e8f0; }}
            .deal-form-cell .deal-form {{ padding: 0.5rem; margin: 0; border: none; display: block; }}
            .deal-form-cell .form-group {{ margin-bottom: 0.5rem; }}
            .deal-form-cell .form-group label {{ margin-bottom: 0.25rem; font-size: 0.85rem; }}
            .deal-form-inline {{ display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-end; }}
            .deal-form-inline .form-group {{ margin-bottom: 0; }}
            .pagination-bar {{ margin-top: 0.75rem; font-size: 0.9rem; color: #4a5568; display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }}
            .pagination-bar a {{ color: #667eea; font-weight: 500; }}
            .pagination-disabled {{ color: #a0aec0; }}
        </style>
        <script>
            function toggleDealForm(appointmentId) {{
                var row = document.getElementById('deal-form-' + appointmentId);
                if (row) row.classList.toggle('visible');
            }}
            function toggleDealEdit(dealId) {{
                var row = document.getElementById('deal-edit-' + dealId);
                if (row) row.classList.toggle('visible');
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <!-- Navigation Bar -->
            <nav class="navbar">
                <div class="navbar-brand">⚡ IUL Appointment Setter</div>
                <div class="navbar-links">
                    <a href="/dashboard/" class="nav-link">📊 Main Dashboard</a>
                    <a href="/appointments" class="nav-link active">📅 Appointments & Deals</a>
                    <a href="/messages" class="nav-link">💬 Messages</a>
                </div>
            </nav>

            <h1>📊 Appointments & Deals</h1>
            <div class="subtitle">
                Last updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC • Auto-refresh every 30s
            </div>

            {f"<div class='alert'>⚠️ {total_upcoming_appointments} upcoming appointment{'s' if total_upcoming_appointments != 1 else ''} in the next 30 days</div>" if total_upcoming_appointments >= 1 else ""}
            

            <!-- Stats Grid (4 per row) -->
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>📋 Total Booked</h3>
                    <div class="stat-value">{total_booked}</div>
                    <div class="stat-subtitle">All-time (linked + unmatched)</div>
                </div>
                <div class="stat-card">
                    <h3>📆 Scheduled</h3>
                    <div class="stat-value">{total_scheduled}</div>
                    <div class="stat-subtitle">Upcoming appointments</div>
                </div>
                <div class="stat-card">
                    <h3>🔗 Unmatched</h3>
                    <div class="stat-value">{total_unmatched}</div>
                    <div class="stat-subtitle">No lead in DB (personal email, etc.)</div>
                </div>
                <div class="stat-card">
                    <h3>⏳ Pending Review</h3>
                    <div class="stat-value">{total_pending_review}</div>
                    <div class="stat-subtitle">Need status update</div>
                </div>
                <div class="stat-card">
                    <h3>✅ Show Rate</h3>
                    <div class="stat-value">{show_rate:.1f}%</div>
                    <div class="stat-subtitle">Showed vs No-Show</div>
                </div>
                <div class="stat-card">
                    <h3>💰 Close Rate</h3>
                    <div class="stat-value">{close_rate:.1f}%</div>
                    <div class="stat-subtitle">Deals from shows</div>
                </div>
                <div class="stat-card">
                    <h3>💵 Total Revenue</h3>
                    <div class="stat-value">${total_revenue:,.0f}</div>
                    <div class="stat-subtitle">Last 90 days</div>
                </div>
                <div class="stat-card">
                    <h3>💸 Commission</h3>
                    <div class="stat-value">${total_commission:,.0f}</div>
                    <div class="stat-subtitle">Your earnings</div>
                </div>
            </div>
            
            <!-- Upcoming Appointments -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📆 Upcoming Appointments</h2>
                    <span class="section-badge">{total_scheduled}</span>
                </div>
                {upcoming_html}
                {upcoming_pagination}
            </div>
            
            <!-- Unmatched (no lead in DB) - above Past so you see every appointment before review -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">🔗 Unmatched Appointments</h2>
                    <span class="section-badge">{total_unmatched}</span>
                </div>
                <p style="color: #718096; font-size: 0.9rem; margin-bottom: 1rem;">Calendly events whose invitee email is not in your leads (e.g. personal email). Add that email as a lead to link future bookings.</p>
                {unmatched_html}
                {unmatched_pagination}
            </div>
            
            <!-- Past Appointments (Need Review) -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">⏳ Past Appointments - Action Required</h2>
                    <span class="section-badge">{total_pending_review}</span>
                </div>
                {past_html}
                {past_pagination}
            </div>
            
            <!-- Closed Deals -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">💰 Closed Deals (Last 90 Days)</h2>
                    <span class="section-badge">{total_deals}</span>
                </div>
                {deals_html}
                {deals_pagination}
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@router.post("/appointments/{appointment_id}/update-status")
async def update_appointment_status(
    appointment_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update appointment status (showed/no-show)"""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        return {"error": "Appointment not found"}
    
    if status == "showed":
        appointment.status = AppointmentStatus.COMPLETED
        
        # Update conversation state
        if appointment.conversation_id:
            conversation = db.query(Conversation).filter(
                Conversation.id == appointment.conversation_id
            ).first()
            if conversation:
                conversation.state = ConversationState.SHOWED
    
    elif status == "no_show":
        appointment.status = AppointmentStatus.NO_SHOW
        
        # Update conversation state
        if appointment.conversation_id:
            conversation = db.query(Conversation).filter(
                Conversation.id == appointment.conversation_id
            ).first()
            if conversation:
                conversation.state = ConversationState.NO_SHOW
    
    db.commit()
    
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/{appointment_id}/close-deal")
async def close_deal(
    appointment_id: int,
    premium_amount: float = Form(...),
    commission_amount: float = Form(...),
    db: Session = Depends(get_db)
):
    """Mark appointment as closed-won and create deal record"""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        return {"error": "Appointment not found"}
    
    # Update appointment status
    appointment.status = AppointmentStatus.SHOWED
    
    # Update conversation to closed-won
    if appointment.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == appointment.conversation_id
        ).first()
        if conversation:
            conversation.state = ConversationState.CLOSED_WON
    
    # Create deal record
    deal = Deal(
        lead_id=appointment.lead_id,
        appointment_id=appointment.id,
        premium_amount=premium_amount,
        commission_amount=commission_amount,
        status="paid"
    )
    
    db.add(deal)
    db.commit()
    
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/{appointment_id}/mark-lost")
async def mark_deal_lost(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    """Mark appointment as closed-lost (no sale)"""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        return {"error": "Appointment not found"}
    
    # Update appointment status
    appointment.status = AppointmentStatus.COMPLETED
    
    # Update conversation to closed-lost
    if appointment.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == appointment.conversation_id
        ).first()
        if conversation:
            conversation.state = ConversationState.CLOSED_LOST
    
    db.commit()
    
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/unmatched/{unmatched_id}/update-status")
async def update_unmatched_status(
    unmatched_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update unmatched appointment status (showed / no_show) — same flow as linked."""
    u = db.query(UnmatchedAppointment).filter(UnmatchedAppointment.id == unmatched_id).first()
    if not u:
        return {"error": "Unmatched appointment not found"}
    if status == "showed":
        u.status = "showed"
    elif status == "no_show":
        u.status = "no_show"
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/deals/{deal_id}/update")
async def update_deal(
    deal_id: int,
    premium_amount: float = Form(...),
    commission_amount: float = Form(...),
    first_name: str = Form(""),
    last_name: str = Form(""),
    company_name: str = Form(""),
    db: Session = Depends(get_db),
):
    """Update a closed deal's amounts and/or lead name/company."""
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Deal not found", status_code=404)
    lead = db.query(Lead).filter(Lead.id == deal.lead_id).first()
    if not lead:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Lead not found", status_code=404)
    deal.premium_amount = premium_amount
    deal.commission_amount = commission_amount
    if first_name is not None:
        lead.first_name = first_name.strip() or lead.first_name
    if last_name is not None:
        lead.last_name = last_name.strip() or lead.last_name
    if company_name is not None:
        lead.company_name = company_name.strip() or lead.company_name
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/unmatched/{unmatched_id}/close-deal")
async def close_deal_from_unmatched(
    unmatched_id: int,
    premium_amount: float = Form(...),
    commission_amount: float = Form(...),
    db: Session = Depends(get_db)
):
    """Create lead + appointment + deal from unmatched, then track revenue/commission."""
    u = db.query(UnmatchedAppointment).filter(UnmatchedAppointment.id == unmatched_id).first()
    if not u:
        return {"error": "Unmatched appointment not found"}
    parts = (u.invitee_name or "").strip().split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    lead = db.query(Lead).filter(Lead.email == u.invitee_email).first()
    if not lead:
        lead = Lead(
            first_name=first_name or None,
            last_name=last_name or None,
            email=u.invitee_email,
            consent_email=True,
        )
        db.add(lead)
        db.flush()
    conv = db.query(Conversation).filter(Conversation.lead_id == lead.id).first()
    if not conv:
        conv = Conversation(lead_id=lead.id, channel=MessageChannel.EMAIL)
        db.add(conv)
        db.flush()
    appt = Appointment(
        lead_id=lead.id,
        conversation_id=conv.id,
        calendly_event_id=u.calendly_event_id,
        scheduled_at=u.scheduled_at,
        timezone=u.timezone,
        status=AppointmentStatus.COMPLETED,
        meeting_url=u.meeting_url or None,
    )
    db.add(appt)
    db.flush()
    deal = Deal(
        lead_id=lead.id,
        appointment_id=appt.id,
        premium_amount=premium_amount,
        commission_amount=commission_amount,
        status="paid",
    )
    db.add(deal)
    conv.state = ConversationState.CLOSED_WON
    u.status = "linked"  # so this row is excluded from unmatched counts/lists
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)
