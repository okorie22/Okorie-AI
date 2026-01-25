"""
Calendly appointment tracking via API polling.
Polls Calendly API for scheduled events and syncs with database.
"""
import requests
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import os

from ..storage.models import (
    Appointment, AppointmentStatus, UnmatchedAppointment,
    Lead, Conversation, ConversationState,
)
from ..storage.repositories import EventRepository, ConversationRepository


class AppointmentTracker:
    """
    Tracks appointments by polling Calendly API.
    Works with free Calendly plan (no webhooks needed).
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("CALENDLY_API_KEY")
        self.base_url = "https://api.calendly.com"
        self.user_uri = os.getenv("CALENDLY_USER_URI")
        self.event_repo = EventRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def poll_scheduled_events(self, days_ahead: int = 30) -> Dict[str, int]:
        """
        Poll Calendly API for scheduled events and sync with database.
        
        Args:
            days_ahead: How many days ahead to check for appointments
        
        Returns:
            Dict with counts of new, updated, cancelled appointments
        """
        if not self.api_key or not self.user_uri:
            logger.warning("Calendly API credentials not configured")
            return {"new": 0, "updated": 0, "cancelled": 0, "no_shows": 0, "unmatched": 0, "unmatched_no_shows": 0, "errors": 0}
        
        try:
            # Calculate date range
            min_start_time = datetime.utcnow().isoformat() + "Z"
            max_start_time = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"
            
            # Fetch scheduled events from Calendly (omit status to include canceled events
            # so we can mark DB rows when we see status=="canceled")
            url = f"{self.base_url}/scheduled_events"
            params = {
                "user": self.user_uri,
                "min_start_time": min_start_time,
                "max_start_time": max_start_time,
                "count": 100
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            events = data.get("collection", [])
            
            logger.info(f"Retrieved {len(events)} scheduled events from Calendly")
            
            # Sync each event with database
            new_count = 0
            updated_count = 0
            cancelled_count = 0
            unmatched_count = 0
            error_count = 0
            
            for event in events:
                try:
                    result = self._sync_event(event)
                    if result == "new":
                        new_count += 1
                    elif result == "updated":
                        updated_count += 1
                    elif result == "cancelled":
                        cancelled_count += 1
                    elif result == "unmatched":
                        unmatched_count += 1
                except Exception as e:
                    logger.error(f"Error syncing event {event.get('uri')}: {e}")
                    error_count += 1
            
            # No-shows: linked appointments and unmatched (both use 30min-after cutoff)
            no_shows = self._check_for_no_shows()
            unmatched_no_shows = self._check_unmatched_no_shows()
            
            logger.success(
                f"Appointment sync complete: {new_count} new, {updated_count} updated, "
                f"{cancelled_count} cancelled, {unmatched_count} unmatched, {no_shows} no-shows, "
                f"{unmatched_no_shows} unmatched no-shows, {error_count} errors"
            )
            
            return {
                "new": new_count,
                "updated": updated_count,
                "cancelled": cancelled_count,
                "no_shows": no_shows,
                "unmatched": unmatched_count,
                "unmatched_no_shows": unmatched_no_shows,
                "errors": error_count
            }
        
        except Exception as e:
            logger.error(f"Failed to poll Calendly appointments: {e}")
            return {"new": 0, "updated": 0, "cancelled": 0, "no_shows": 0, "unmatched": 0, "unmatched_no_shows": 0, "errors": 1}
    
    def _sync_event(self, event: Dict) -> str:
        """
        Sync a single Calendly event with database.
        
        Returns:
            "new", "updated", "cancelled", or "unmatched"
        """
        event_uuid = event.get("uri", "").split("/")[-1]
        status = event.get("status")
        start_time_str = event.get("start_time")
        end_time_str = event.get("end_time")
        location = event.get("location", {})

        # Canceled: mark existing Appointment or UnmatchedAppointment without needing invitees
        # (invitees may be empty or 404 for canceled events)
        if (status or "").lower() in ("canceled", "cancelled"):
            existing_appt = self.db.query(Appointment).filter(
                Appointment.calendly_event_id == event_uuid
            ).first()
            if existing_appt:
                existing_appt.status = AppointmentStatus.CANCELLED
                self.db.commit()
                logger.info(f"Appointment {existing_appt.id} marked as cancelled (from poll)")
                return "cancelled"
            existing_ua = self.db.query(UnmatchedAppointment).filter(
                UnmatchedAppointment.calendly_event_id == event_uuid
            ).first()
            if existing_ua:
                existing_ua.status = "canceled"
                self.db.commit()
                logger.info(f"Unmatched appointment {existing_ua.id} marked as cancelled (from poll)")
                return "cancelled"
            return "updated"  # canceled event we never stored

        # Parse datetime for active events
        scheduled_at = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

        # Fetch invitees to get email
        invitees = self._fetch_invitees(event.get("uri"))
        if not invitees:
            logger.warning(f"No invitees found for event {event_uuid}")
            return "updated"
        
        invitee = invitees[0]  # Assuming 1-on-1 appointments
        invitee_email = invitee.get("email")
        invitee_name = invitee.get("name", "")
        invitee_timezone = invitee.get("timezone")
        
        # Find lead by email
        lead = self.db.query(Lead).filter(Lead.email == invitee_email).first()
        if not lead:
            return self._upsert_unmatched(event_uuid, invitee_email, invitee_name, invitee_timezone, scheduled_at, location, status)
        
        # Check if appointment already exists
        existing = self.db.query(Appointment).filter(
            Appointment.calendly_event_id == event_uuid
        ).first()
        
        if existing:
            # Update existing appointment (canceled already handled above)
            if (status or "").lower() in ("canceled", "cancelled"):
                existing.status = AppointmentStatus.CANCELLED
                logger.info(f"Appointment {existing.id} marked as cancelled")
                return "cancelled"
            else:
                # Update scheduled time if changed
                if existing.scheduled_at != scheduled_at:
                    existing.scheduled_at = scheduled_at
                    logger.info(f"Appointment {existing.id} rescheduled to {scheduled_at}")
                    return "updated"
                return "updated"
        
        # Create new appointment
        conversation = self.conv_repo.get_active_by_lead(lead.id)
        if not conversation:
            # Create conversation if none exists
            from ..workflow.state_machine import WorkflowEngine
            engine = WorkflowEngine(self.db)
            conversation = engine.start_conversation(lead)
        
        meeting_url = location.get("join_url", "") if location.get("type") == "zoom" else ""
        
        appointment = Appointment(
            lead_id=lead.id,
            conversation_id=conversation.id,
            calendly_event_id=event_uuid,
            scheduled_at=scheduled_at,
            timezone=invitee_timezone or "UTC",
            status=AppointmentStatus.PENDING,
            meeting_url=meeting_url
        )
        
        self.db.add(appointment)
        
        # Update conversation state
        from ..workflow.state_machine import StateMachine
        state_machine = StateMachine(self.db)
        state_machine.transition(conversation, ConversationState.SCHEDULED)
        
        self.db.commit()
        self.db.refresh(appointment)
        
        # Log event
        self.event_repo.log(
            event_type="appointment_booked",
            lead_id=lead.id,
            payload={
                "appointment_id": appointment.id,
                "calendly_event_id": event_uuid,
                "scheduled_at": start_time_str
            }
        )
        
        logger.success(f"New appointment created: {appointment.id} for lead {lead.id}")
        
        return "new"
    
    def _upsert_unmatched(
        self,
        event_uuid: str,
        invitee_email: str,
        invitee_name: str,
        invitee_timezone: Optional[str],
        scheduled_at: datetime,
        location: Dict,
        status: str,
    ) -> str:
        """Create or update an unmatched appointment (invitee email not in leads). Returns 'unmatched'."""
        meeting_url = location.get("join_url", "") if location.get("type") == "zoom" else ""
        cal_status = "canceled" if (status or "").lower() in ("canceled", "cancelled") else "active"
        existing = self.db.query(UnmatchedAppointment).filter(
            UnmatchedAppointment.calendly_event_id == event_uuid
        ).first()
        if existing:
            existing.invitee_email = invitee_email
            existing.invitee_name = invitee_name or existing.invitee_name
            existing.scheduled_at = scheduled_at
            existing.timezone = invitee_timezone or existing.timezone
            existing.meeting_url = meeting_url or existing.meeting_url
            existing.status = cal_status
            self.db.commit()
            logger.debug(f"Unmatched appointment updated: {event_uuid} ({invitee_email})")
        else:
            row = UnmatchedAppointment(
                calendly_event_id=event_uuid,
                invitee_email=invitee_email,
                invitee_name=invitee_name or "",
                scheduled_at=scheduled_at,
                timezone=invitee_timezone or "UTC",
                meeting_url=meeting_url or "",
                status=cal_status,
            )
            self.db.add(row)
            self.db.commit()
            logger.info(f"Unmatched appointment stored: {event_uuid} ({invitee_email}) — no lead in DB")
        return "unmatched"
    
    def _fetch_invitees(self, event_uri: str) -> List[Dict]:
        """Fetch invitees for a scheduled event"""
        try:
            url = f"{self.base_url}/scheduled_events/{event_uri.split('/')[-1]}/invitees"
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("collection", [])
        except Exception as e:
            logger.error(f"Failed to fetch invitees: {e}")
            return []
    
    def _check_for_no_shows(self) -> int:
        """
        Check for appointments that passed and mark as no-show if not updated.
        Runs 30 minutes after appointment time.
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)
        
        # Find appointments that are still PENDING or CONFIRMED but time has passed
        pending_appointments = self.db.query(Appointment).filter(
            Appointment.scheduled_at < cutoff_time,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED,
                                   AppointmentStatus.REMINDED_24H, AppointmentStatus.REMINDED_2H])
        ).all()
        
        no_show_count = 0
        for appointment in pending_appointments:
            appointment.status = AppointmentStatus.NO_SHOW
            
            # Update conversation state
            if appointment.conversation_id:
                conversation = self.conv_repo.get_by_id(appointment.conversation_id)
                if conversation:
                    from ..workflow.state_machine import StateMachine
                    state_machine = StateMachine(self.db)
                    state_machine.transition(conversation, ConversationState.NO_SHOW)
            
            logger.info(f"Appointment {appointment.id} marked as NO_SHOW")
            no_show_count += 1
        
        if no_show_count > 0:
            self.db.commit()
        
        return no_show_count
    
    def _check_unmatched_no_shows(self) -> int:
        """
        Mark unmatched appointments as no_show when scheduled time has passed (30min cutoff).
        Same flow as linked appointments.
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)
        rows = self.db.query(UnmatchedAppointment).filter(
            UnmatchedAppointment.scheduled_at < cutoff_time,
            UnmatchedAppointment.status == "active",
        ).all()
        for u in rows:
            u.status = "no_show"
            logger.info(f"Unmatched appointment {u.id} ({u.invitee_email}) marked no_show")
        if rows:
            self.db.commit()
        return len(rows)
    
    def get_upcoming_appointments(self, days_ahead: int = 7) -> List[Appointment]:
        """Get upcoming appointments for dashboard display"""
        cutoff_time = datetime.utcnow() + timedelta(days=days_ahead)
        
        appointments = self.db.query(Appointment).filter(
            Appointment.scheduled_at >= datetime.utcnow(),
            Appointment.scheduled_at <= cutoff_time,
            Appointment.status.in_([
                AppointmentStatus.PENDING,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.REMINDED_24H,
                AppointmentStatus.REMINDED_2H
            ])
        ).order_by(Appointment.scheduled_at).all()
        
        return appointments
    
    def get_past_appointments_for_review(self, days_back: int = 7) -> List[Appointment]:
        """Get recent past appointments that need status update (showed/no-show)"""
        start_time = datetime.utcnow() - timedelta(days=days_back)
        
        appointments = self.db.query(Appointment).filter(
            Appointment.scheduled_at >= start_time,
            Appointment.scheduled_at < datetime.utcnow(),
            Appointment.status.in_([
                AppointmentStatus.PENDING,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.REMINDED_24H,
                AppointmentStatus.REMINDED_2H,
                AppointmentStatus.NO_SHOW
            ])
        ).order_by(Appointment.scheduled_at.desc()).all()
        
        return appointments
