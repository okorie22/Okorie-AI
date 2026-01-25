"""
Appointment reminder system - sends 24h and 2h reminders.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict
from loguru import logger

from ..storage.models import Appointment, AppointmentStatus, ConversationState
from ..storage.repositories import EventRepository, ConversationRepository
from ..conversation.templates import MessageTemplates
from ..channels.email import SendGridService
from ..channels.sms import TwilioService


class ReminderService:
    """Appointment reminder service"""
    
    def __init__(self, db: Session):
        self.db = db
        self.event_repo = EventRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.templates = MessageTemplates()
        self.email_service = SendGridService(db)
        self.sms_service = TwilioService(db)
    
    def send_24h_reminders(self) -> Dict:
        """Send 24-hour reminders for upcoming appointments"""
        # Find appointments 24 hours from now that haven't been reminded
        target_time = datetime.utcnow() + timedelta(hours=24)
        time_window_start = target_time - timedelta(minutes=15)
        time_window_end = target_time + timedelta(minutes=15)
        
        appointments = self.db.query(Appointment).filter(
            Appointment.scheduled_at >= time_window_start,
            Appointment.scheduled_at <= time_window_end,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        ).all()
        
        logger.info(f"Found {len(appointments)} appointments needing 24h reminders")
        
        sent = 0
        errors = 0
        
        for appointment in appointments:
            try:
                # Check if already sent
                if appointment.status == AppointmentStatus.REMINDED_24H or appointment.status == AppointmentStatus.REMINDED_2H:
                    continue
                
                # Get lead
                lead = appointment.lead
                if not lead:
                    logger.warning(f"Lead not found for appointment {appointment.id}")
                    continue
                
                # Format appointment time
                appt_time = appointment.scheduled_at.strftime("%I:%M %p")
                appt_date = appointment.scheduled_at.strftime("%B %d, %Y")
                
                # Send email reminder
                if lead.email:
                    template_data = self.templates.render(
                        "reminder_24h_email",
                        lead,
                        extra_context={
                            "appointment_time": f"{appt_time} on {appt_date}",
                            "timezone": appointment.timezone,
                            "meeting_url": appointment.meeting_url
                        }
                    )
                    
                    self.email_service.send_email(
                        to_email=lead.email,
                        subject=template_data["subject"],
                        body=template_data["body"],
                        lead_id=lead.id,
                        conversation_id=appointment.conversation_id
                    )
                
                # Send SMS reminder if consented
                if lead.consent_sms and lead.phone:
                    template_data = self.templates.render(
                        "reminder_24h_sms",
                        lead,
                        extra_context={
                            "appointment_time": appt_time,
                            "timezone": appointment.timezone,
                            "meeting_url": appointment.meeting_url
                        }
                    )
                    
                    self.sms_service.send_sms(
                        to_number=lead.phone,
                        body=template_data["body"],
                        lead_id=lead.id,
                        conversation_id=appointment.conversation_id
                    )
                
                # Update appointment status
                appointment.status = AppointmentStatus.REMINDED_24H
                
                # Update conversation state
                conversation = appointment.conversation
                if conversation:
                    from ..workflow.state_machine import StateMachine
                    state_machine = StateMachine(self.db)
                    state_machine.transition(conversation, ConversationState.REMINDED_24H)
                
                self.db.commit()
                sent += 1
                
                # Log event
                self.event_repo.log(
                    event_type="reminder_24h_sent",
                    lead_id=lead.id,
                    payload={"appointment_id": appointment.id}
                )
            
            except Exception as e:
                logger.error(f"Error sending 24h reminder for appointment {appointment.id}: {e}")
                errors += 1
        
        return {"sent": sent, "errors": errors}
    
    def send_2h_reminders(self) -> Dict:
        """Send 2-hour reminders for upcoming appointments"""
        # Find appointments 2 hours from now
        target_time = datetime.utcnow() + timedelta(hours=2)
        time_window_start = target_time - timedelta(minutes=10)
        time_window_end = target_time + timedelta(minutes=10)
        
        appointments = self.db.query(Appointment).filter(
            Appointment.scheduled_at >= time_window_start,
            Appointment.scheduled_at <= time_window_end,
            Appointment.status == AppointmentStatus.REMINDED_24H
        ).all()
        
        logger.info(f"Found {len(appointments)} appointments needing 2h reminders")
        
        sent = 0
        errors = 0
        
        for appointment in appointments:
            try:
                lead = appointment.lead
                if not lead:
                    continue
                
                appt_time = appointment.scheduled_at.strftime("%I:%M %p")
                
                # Send email reminder
                if lead.email:
                    template_data = self.templates.render(
                        "reminder_2h_email",
                        lead,
                        extra_context={
                            "appointment_time": appt_time,
                            "meeting_url": appointment.meeting_url
                        }
                    )
                    
                    self.email_service.send_email(
                        to_email=lead.email,
                        subject=template_data["subject"],
                        body=template_data["body"],
                        lead_id=lead.id,
                        conversation_id=appointment.conversation_id
                    )
                
                # Send SMS reminder
                if lead.consent_sms and lead.phone:
                    template_data = self.templates.render(
                        "reminder_2h_sms",
                        lead,
                        extra_context={
                            "appointment_time": appt_time,
                            "meeting_url": appointment.meeting_url
                        }
                    )
                    
                    self.sms_service.send_sms(
                        to_number=lead.phone,
                        body=template_data["body"],
                        lead_id=lead.id,
                        conversation_id=appointment.conversation_id
                    )
                
                # Update appointment status
                appointment.status = AppointmentStatus.REMINDED_2H
                
                # Update conversation state
                conversation = appointment.conversation
                if conversation:
                    from ..workflow.state_machine import StateMachine
                    state_machine = StateMachine(self.db)
                    state_machine.transition(conversation, ConversationState.REMINDED_2H)
                
                self.db.commit()
                sent += 1
                
                # Log event
                self.event_repo.log(
                    event_type="reminder_2h_sent",
                    lead_id=lead.id,
                    payload={"appointment_id": appointment.id}
                )
            
            except Exception as e:
                logger.error(f"Error sending 2h reminder for appointment {appointment.id}: {e}")
                errors += 1
        
        return {"sent": sent, "errors": errors}
    
    def check_no_shows(self) -> Dict:
        """
        Check for no-shows by polling Calendly API 15-30 minutes after appointment time.
        
        Logic:
        1. Find appointments that are 15-30 minutes past scheduled time
        2. Poll Calendly API to check if appointment was cancelled by user
        3. If still "active" in Calendly = no-show
        4. If "canceled" in Calendly = user cancelled, mark accordingly
        """
        # Find appointments between 15-30 minutes past scheduled time
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=30)
        window_end = now - timedelta(minutes=15)
        
        appointments = self.db.query(Appointment).filter(
            Appointment.scheduled_at >= window_start,
            Appointment.scheduled_at <= window_end,
            Appointment.status.in_([AppointmentStatus.REMINDED_2H, AppointmentStatus.PENDING])
        ).all()
        
        logger.info(f"Checking {len(appointments)} appointments for no-shows (15-30 min window)")
        
        no_shows = 0
        cancelled_by_lead = 0
        completed = 0
        errors = 0
        
        # Initialize Calendly service for API polling
        from .calendly import CalendlyService
        calendly_service = CalendlyService(self.db)
        
        for appointment in appointments:
            try:
                lead = appointment.lead
                if not lead:
                    continue
                
                # Poll Calendly API if we have an event UUID
                if appointment.calendly_event_id:
                    invitee_status = calendly_service.check_invitee_status(appointment.calendly_event_id)
                    
                    if invitee_status == "canceled":
                        # Lead cancelled via Calendly
                        logger.info(f"Appointment {appointment.id} was cancelled by lead via Calendly")
                        appointment.status = AppointmentStatus.CANCELLED
                        cancelled_by_lead += 1
                        
                        # Update conversation state
                        conversation = appointment.conversation
                        if conversation:
                            from ..workflow.state_machine import StateMachine
                            state_machine = StateMachine(self.db)
                            state_machine.transition(conversation, ConversationState.CONTACTED)
                        
                        # Log event
                        self.event_repo.log(
                            event_type="appointment_cancelled_by_lead",
                            lead_id=lead.id,
                            payload={"appointment_id": appointment.id}
                        )
                        
                    elif invitee_status == "active":
                        # Still active = no-show (didn't join)
                        logger.info(f"Appointment {appointment.id} marked as NO_SHOW (still active in Calendly)")
                        appointment.status = AppointmentStatus.NO_SHOW
                        
                        # Update conversation state
                        conversation = appointment.conversation
                        if conversation:
                            from ..workflow.state_machine import StateMachine
                            state_machine = StateMachine(self.db)
                            state_machine.transition(conversation, ConversationState.NO_SHOW)
                        
                        # Log event
                        self.event_repo.log(
                            event_type="appointment_no_show",
                            lead_id=lead.id,
                            payload={"appointment_id": appointment.id}
                        )
                        
                        # Send no-show recovery message
                        self._send_no_show_recovery(appointment)
                        
                        no_shows += 1
                    else:
                        # API returned None (error or no API key) - fall back to time-based detection
                        logger.warning(f"Could not check Calendly status for appointment {appointment.id}, using time-based fallback")
                        appointment.status = AppointmentStatus.NO_SHOW
                        
                        # Update conversation state
                        conversation = appointment.conversation
                        if conversation:
                            from ..workflow.state_machine import StateMachine
                            state_machine = StateMachine(self.db)
                            state_machine.transition(conversation, ConversationState.NO_SHOW)
                        
                        self._send_no_show_recovery(appointment)
                        no_shows += 1
                        
                else:
                    # No Calendly event ID - use time-based fallback
                    logger.info(f"Appointment {appointment.id} has no Calendly ID, marking as NO_SHOW (time-based)")
                    appointment.status = AppointmentStatus.NO_SHOW
                    
                    conversation = appointment.conversation
                    if conversation:
                        from ..workflow.state_machine import StateMachine
                        state_machine = StateMachine(self.db)
                        state_machine.transition(conversation, ConversationState.NO_SHOW)
                    
                    self._send_no_show_recovery(appointment)
                    no_shows += 1
                
                self.db.commit()
            
            except Exception as e:
                logger.error(f"Error processing appointment {appointment.id}: {e}")
                errors += 1
        
        return {
            "no_shows": no_shows,
            "cancelled_by_lead": cancelled_by_lead,
            "completed": completed,
            "errors": errors
        }
    
    def _send_no_show_recovery(self, appointment: Appointment):
        """Send no-show recovery message"""
        lead = appointment.lead
        if not lead:
            return
        
        try:
            # Send email
            if lead.email:
                template_data = self.templates.render(
                    "no_show_recovery_email",
                    lead,
                    extra_context={
                        "calendly_link": self.templates._get_calendly_link(lead)
                    }
                )
                
                self.email_service.send_email(
                    to_email=lead.email,
                    subject=template_data["subject"],
                    body=template_data["body"],
                    lead_id=lead.id,
                    conversation_id=appointment.conversation_id
                )
            
            logger.info(f"Sent no-show recovery message for appointment {appointment.id}")
        
        except Exception as e:
            logger.error(f"Error sending no-show recovery: {e}")
