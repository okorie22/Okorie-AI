"""
Calendly API integration and webhook handler for appointment scheduling.
"""
import requests
from sqlalchemy.orm import Session
from typing import Dict, Optional
from datetime import datetime
from loguru import logger
import os

from ..storage.models import (
    Appointment,
    AppointmentStatus,
    Conversation,
    ConversationState,
    UnmatchedAppointment,
)
from ..storage.repositories import EventRepository, ConversationRepository


class CalendlyService:
    """Calendly appointment scheduling integration"""
    
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("CALENDLY_API_KEY")
        self.base_url = "https://api.calendly.com"
        self.event_type_uuid = os.getenv("CALENDLY_EVENT_TYPE_UUID")
        self.user_uri = os.getenv("CALENDLY_USER_URI")
        self.event_repo = EventRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def get_booking_link(self, lead_first_name: str, lead_last_name: str, lead_email: str) -> str:
        """
        Generate personalized Calendly booking link with pre-filled data.
        """
        from urllib.parse import urlencode
        
        if not self.user_uri:
            return "https://calendly.com/your-link"
        
        # Build params
        params = {
            "first_name": lead_first_name,
            "last_name": lead_last_name,
            "email": lead_email
        }
        
        query = urlencode({k: v for k, v in params.items() if v})
        return f"{self.user_uri}?{query}"
    
    def get_event_status(self, calendly_event_uuid: str) -> Optional[Dict]:
        """
        Fetch event details from Calendly API to check if it was cancelled or completed.
        
        Returns:
            Dict with status: "active", "canceled", or None if not found/error
        """
        if not self.api_key:
            logger.warning("CALENDLY_API_KEY not set, cannot fetch event status")
            return None
        
        try:
            # Calendly API endpoint for scheduled events
            url = f"{self.base_url}/scheduled_events/{calendly_event_uuid}"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 404:
                logger.info(f"Event {calendly_event_uuid} not found (likely canceled)")
                return {"status": "canceled"}
            
            response.raise_for_status()
            data = response.json()
            
            # Extract status
            resource = data.get("resource", {})
            status = resource.get("status", "active")  # "active" or "canceled"
            
            logger.debug(f"Calendly event {calendly_event_uuid}: {status}")
            
            return {
                "status": status,
                "start_time": resource.get("start_time"),
                "end_time": resource.get("end_time"),
                "name": resource.get("name"),
                "location": resource.get("location"),
            }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Calendly event {calendly_event_uuid}: {e}")
            return None
    
    def check_invitee_status(self, calendly_event_uuid: str) -> Optional[str]:
        """
        Check if invitee cancelled or no-showed.
        
        Returns:
            "active", "canceled", or None
        """
        if not self.api_key:
            return None
        
        try:
            # Get invitees for this event
            url = f"{self.base_url}/scheduled_events/{calendly_event_uuid}/invitees"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            invitees = data.get("collection", [])
            
            if not invitees:
                return "canceled"
            
            # Check first invitee status
            invitee = invitees[0]
            status = invitee.get("status")  # "active" or "canceled"
            
            logger.debug(f"Invitee status for event {calendly_event_uuid}: {status}")
            return status
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching invitees for event {calendly_event_uuid}: {e}")
            return None
    
    def handle_webhook(self, webhook_data: Dict) -> Dict:
        """
        Handle Calendly webhooks for appointment events.
        
        Webhook events:
        - invitee.created: New appointment booked (uses scheduled_event.uri for event id)
        - invitee.canceled: Appointment cancelled (linked and unmatched)
        - invitee.rescheduled: Old event marked canceled, new event treated as created
        """
        event_type = webhook_data.get("event")
        payload = webhook_data.get("payload", {})
        
        logger.info(f"Received Calendly webhook: {event_type}")
        
        if event_type == "invitee.created":
            return self._handle_appointment_created(payload)
        elif event_type == "invitee.canceled":
            return self._handle_appointment_canceled(payload)
        elif event_type == "invitee.rescheduled":
            return self._handle_appointment_rescheduled(payload)
        else:
            logger.warning(f"Unknown Calendly event type: {event_type}")
            return {"success": False, "error": "Unknown event type"}
    
    def _handle_appointment_created(self, payload: Dict) -> Dict:
        """Handle new appointment booking"""
        try:
            # Event id lives in scheduled_event.uri; payload.uuid is invitee uuid
            scheduled_event = payload.get("scheduled_event", {})
            event_uri = scheduled_event.get("uri") or payload.get("uri") or ""
            event_uuid = event_uri.split("/")[-1] if event_uri else payload.get("uuid")
            
            start_time_str = scheduled_event.get("start_time")
            end_time_str = scheduled_event.get("end_time")
            event_name = scheduled_event.get("name")
            location = scheduled_event.get("location", {})
            meeting_url = location.get("join_url") if location.get("type") == "zoom" else scheduled_event.get("location")
            
            # Get invitee info
            invitee_email = payload.get("email")
            invitee_name = payload.get("name", "")
            timezone = payload.get("timezone")
            
            # Parse datetime
            scheduled_at = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            
            # Find lead by email
            from ..storage.models import Lead
            lead = self.db.query(Lead).filter(Lead.email == invitee_email).first()
            
            if not lead:
                logger.warning(f"Lead not found for email: {invitee_email}")
                return {"success": False, "error": "Lead not found"}
            
            # Find active conversation
            conversation = self.conv_repo.get_active_by_lead(lead.id)
            
            if not conversation:
                logger.warning(f"No active conversation for lead {lead.id}")
                # Create a conversation if none exists
                from ..workflow.state_machine import WorkflowEngine
                engine = WorkflowEngine(self.db)
                conversation = engine.start_conversation(lead)
            
            # Create appointment record
            appointment = Appointment(
                lead_id=lead.id,
                conversation_id=conversation.id,
                calendly_event_id=event_uuid,
                scheduled_at=scheduled_at,
                timezone=timezone or "UTC",
                status=AppointmentStatus.PENDING,
                meeting_url=meeting_url or ""
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
                    "scheduled_at": start_time_str,
                    "timezone": timezone
                }
            )
            
            logger.success(f"Appointment created: {appointment.id} for lead {lead.id}")
            
            # Send confirmation (async task)
            from ..workflow.tasks import send_message_task
            send_message_task.delay(conversation.id, "confirmation_email")
            
            return {"success": True, "appointment_id": appointment.id}
        
        except Exception as e:
            logger.error(f"Error handling appointment creation: {e}")
            return {"success": False, "error": str(e)}
    
    def _handle_appointment_canceled(self, payload: Dict) -> Dict:
        """Handle appointment cancellation (linked and unmatched)."""
        try:
            # Event id is under scheduled_event.uri; payload.uuid is invitee uuid
            scheduled_event = payload.get("scheduled_event") or {}
            event_uri = scheduled_event.get("uri") or ""
            event_uuid = event_uri.split("/")[-1] if event_uri else payload.get("uuid")

            if not event_uuid:
                logger.warning("Calendly cancel webhook had no event uuid")
                return {"success": False, "error": "No event uuid in payload"}

            # Linked appointment
            appointment = self.db.query(Appointment).filter(
                Appointment.calendly_event_id == event_uuid
            ).first()
            if appointment:
                appointment.status = AppointmentStatus.CANCELLED
                conversation = self.db.query(Conversation).filter(
                    Conversation.id == appointment.conversation_id
                ).first()
                if conversation:
                    from ..workflow.state_machine import StateMachine
                    state_machine = StateMachine(self.db)
                    state_machine.transition(conversation, ConversationState.CANCELLED)
                self.db.commit()
                self.event_repo.log(
                    event_type="appointment_cancelled",
                    lead_id=appointment.lead_id,
                    payload={
                        "appointment_id": appointment.id,
                        "calendly_event_id": event_uuid,
                    },
                )
                logger.info(f"Appointment {appointment.id} cancelled (webhook)")
                return {"success": True, "appointment_id": appointment.id, "type": "appointment"}

            # Unmatched appointment
            unmatched = self.db.query(UnmatchedAppointment).filter(
                UnmatchedAppointment.calendly_event_id == event_uuid
            ).first()
            if unmatched:
                unmatched.status = "canceled"
                self.db.commit()
                logger.info(
                    f"Unmatched appointment {unmatched.id} ({unmatched.invitee_email}) "
                    "cancelled (webhook)"
                )
                return {"success": True, "unmatched_id": unmatched.id, "type": "unmatched"}

            logger.warning(f"No appointment or unmatched row for Calendly event: {event_uuid}")
            return {"success": False, "error": "Appointment not found"}
        except Exception as e:
            logger.error(f"Error handling appointment cancellation: {e}")
            return {"success": False, "error": str(e)}

    def _handle_appointment_rescheduled(self, payload: Dict) -> Dict:
        """Handle reschedule: mark old event canceled, then treat new as created if present.
        Calendly may send invitee.canceled (old) + invitee.created (new) instead of
        invitee.rescheduled; when we get rescheduled we cancel old and create/update new.
        """
        try:
            # Some payloads have old_invitee / new_invitee or single invitee for the new time
            old_invitee = payload.get("old_invitee") or payload.get("previous_invitee")
            new_invitee = payload.get("new_invitee") or payload.get("invitee") or payload
            if old_invitee and isinstance(old_invitee, dict):
                se = (old_invitee.get("scheduled_event") or {})
                uri = se.get("uri") or ""
                if uri:
                    self._handle_appointment_canceled({"scheduled_event": {"uri": uri}})
            # New time: treat as creation so we create or update
            if new_invitee and isinstance(new_invitee, dict) and new_invitee.get("scheduled_event"):
                return self._handle_appointment_created(new_invitee)
            logger.info("invitee.rescheduled processed (no new_invitee); poll will sync")
            return {"success": True, "rescheduled": True}
        except Exception as e:
            logger.error(f"Error handling reschedule: {e}")
            return {"success": False, "error": str(e)}

    def get_appointment_details(self, calendly_event_uuid: str) -> Optional[Dict]:
        """
        Fetch appointment details from Calendly API.
        """
        if not self.api_key:
            logger.error("Calendly API key not configured")
            return None
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/scheduled_events/{calendly_event_uuid}"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(f"Error fetching Calendly event details: {e}")
            return None
