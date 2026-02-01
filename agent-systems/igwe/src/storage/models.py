"""
SQLAlchemy models for the IUL Appointment Setter system.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, JSON, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from .database import Base


class LeadSource(str, enum.Enum):
    """Lead source types"""
    CSV = "csv"
    WEBFORM = "webform"
    REFERRAL = "referral"
    MANUAL = "manual"
    APIFY_ACTOR1 = "apify_actor1"
    APIFY_ACTOR2 = "apify_actor2"


class ConversationState(str, enum.Enum):
    """Conversation state machine states"""
    NEW = "new"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    REMINDED_24H = "reminded_24h"
    REMINDED_2H = "reminded_2h"
    SHOWED = "showed"
    NO_SHOW = "no_show"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    NOT_INTERESTED = "not_interested"
    STOPPED = "stopped"
    NO_RESPONSE = "no_response"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    NEEDS_HUMAN_REVIEW = "needs_human_review"  # AI escalated, awaiting human review
    HUMAN_HANDLING = "human_handling"  # Human actively handling this conversation


class MessageChannel(str, enum.Enum):
    """Communication channels"""
    EMAIL = "email"
    SMS = "sms"
    MANUAL_CALL = "manual_call"


class MessageDirection(str, enum.Enum):
    """Message direction"""
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class AppointmentStatus(str, enum.Enum):
    """Appointment status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REMINDED_24H = "reminded_24h"
    REMINDED_2H = "reminded_2h"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class Lead(Base):
    """Lead model - core contact information"""
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    
    # Personal information
    first_name = Column(String(100), index=True)
    last_name = Column(String(100), index=True)
    email = Column(String(255), unique=True, index=True)  # UNIQUE constraint for deduplication
    phone = Column(String(20), unique=True, nullable=True, index=True)  # UNIQUE constraint for deduplication
    linkedin_url = Column(String(500))
    
    # Company information
    company_name = Column(String(255), index=True)
    company_website = Column(String(500))
    industry = Column(String(100), index=True)
    employee_size = Column(Integer)
    founded_year = Column(Integer)
    job_title = Column(String(255))  # Position/title at company
    
    # Location
    address = Column(String(255))
    city = Column(String(100))
    state = Column(String(50), index=True)
    zipcode = Column(String(20))
    
    # Metadata
    source = Column(Enum(LeadSource), default=LeadSource.CSV)
    consent_sms = Column(Boolean, default=False)
    consent_email = Column(Boolean, default=False)
    
    # Suppression tracking (for bounces, complaints, unsubscribes)
    suppression_reason = Column(String(100), nullable=True)  # bounce, complaint, unsubscribe, duplicate_cleanup
    suppressed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    score = relationship("LeadScore", back_populates="lead", uselist=False)
    enrichment = relationship("LeadEnrichment", back_populates="lead", uselist=False)
    conversations = relationship("Conversation", back_populates="lead")
    appointments = relationship("Appointment", back_populates="lead")
    events = relationship("Event", back_populates="lead")


class Suppression(Base):
    """Suppression log for bounces, complaints, unsubscribes (SendGrid webhook, manual, etc.)."""
    __tablename__ = "suppressions"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True, nullable=False)
    email = Column(String(255), index=True, nullable=False)
    reason = Column(String(100), index=True, nullable=False)  # bounce, complaint, unsubscribe, dropped, blocked
    source = Column(String(100), index=True, nullable=False)  # sendgrid_webhook, manual, cleanup
    event_metadata = Column(JSON, nullable=True)  # extra event data from webhook (avoid name 'metadata' - reserved)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class LeadScore(Base):
    """Lead scoring data"""
    __tablename__ = "lead_scores"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), unique=True, index=True)
    
    # Scores
    score = Column(Integer, index=True)  # Total score 0-100
    tier = Column(Integer, index=True)  # 1-5
    
    # Component scores
    industry_score = Column(Integer)
    employee_score = Column(Integer)
    age_score = Column(Integer)
    location_score = Column(Integer)
    contact_score = Column(Integer)
    
    # Timestamp
    scored_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    lead = relationship("Lead", back_populates="score")


class LeadEnrichment(Base):
    """Website enrichment data"""
    __tablename__ = "lead_enrichment"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), unique=True, index=True)
    
    # Enrichment data
    company_domain = Column(String(255), index=True)  # For caching
    website_summary = Column(Text)
    personalization_bullets = Column(JSON)  # Array of strings
    confidence_score = Column(Integer)  # 0-100
    
    # Timestamp
    enriched_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    lead = relationship("Lead", back_populates="enrichment")


class Conversation(Base):
    """Conversation state and history"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    
    # State
    state = Column(Enum(ConversationState), default=ConversationState.NEW, index=True)
    channel = Column(Enum(MessageChannel), default=MessageChannel.EMAIL)
    
    # Timing
    last_message_at = Column(DateTime(timezone=True))
    next_action_at = Column(DateTime(timezone=True), index=True)
    
    # Qualification data (structured JSON)
    qualification_data = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    lead = relationship("Lead", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")
    appointments = relationship("Appointment", back_populates="conversation")


class Message(Base):
    """Message history"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    
    # Message data
    direction = Column(Enum(MessageDirection))
    channel = Column(Enum(MessageChannel))
    body = Column(Text)
    template_variant_id = Column(String(50), index=True)  # e.g., "opener_v3"
    # NOTE: "metadata" is a reserved attribute name in SQLAlchemy Declarative.
    # Keep the DB column name as "metadata" but use a safe Python attribute name.
    message_metadata = Column("metadata", JSON)  # Delivery status, tracking info, etc.
    
    # Timestamps
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    read_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    conversation = relationship("Conversation", back_populates="messages")


class Appointment(Base):
    """Scheduled appointments"""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    
    # Calendly data
    calendly_event_id = Column(String(255), unique=True, index=True)
    
    # Appointment details
    scheduled_at = Column(DateTime(timezone=True), index=True)
    timezone = Column(String(50))
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING, index=True)
    meeting_url = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    lead = relationship("Lead", back_populates="appointments")
    conversation = relationship("Conversation", back_populates="appointments")


class UnmatchedAppointment(Base):
    """
    Calendly events whose invitee email did not match any lead.
    Keeps visibility of every appointment; no lead/conversation link.
    """
    __tablename__ = "unmatched_appointments"

    id = Column(Integer, primary_key=True, index=True)
    calendly_event_id = Column(String(255), unique=True, index=True, nullable=False)
    invitee_email = Column(String(255), index=True, nullable=False)
    invitee_name = Column(String(255))
    scheduled_at = Column(DateTime(timezone=True), index=True, nullable=False)
    timezone = Column(String(50))
    meeting_url = Column(String(500))
    status = Column(String(20), default="active", index=True)  # "active" | "canceled"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Event(Base):
    """Event log for analytics and debugging"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True, nullable=True)
    
    # Event data
    event_type = Column(String(100), index=True)  # lead_created, message_sent, etc.
    payload = Column(JSON)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationship
    lead = relationship("Lead", back_populates="events")


class Deal(Base):
    """Deal/revenue tracking for attribution"""
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), index=True, nullable=True)
    
    # Deal information
    premium_amount = Column(Float)
    commission_amount = Column(Float)
    status = Column(String(50), index=True)  # pending, paid, cancelled
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class LeadSourceRun(Base):
    """Track Apify actor runs and parameter combinations"""
    __tablename__ = "lead_source_runs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Run identification
    run_id = Column(String(255), unique=True, index=True)  # Apify run ID
    actor_name = Column(String(255), index=True)  # Actor ID
    dataset_id = Column(String(255))
    token_alias = Column(String(50))  # "token_1", "token_2", etc.
    
    # Parameters
    params_hash = Column(String(32), index=True)  # MD5 hash of params
    params_json = Column(JSON)  # Full parameter set
    
    # Results
    status = Column(String(50), index=True)  # succeeded, failed, timeout
    total_rows = Column(Integer)  # Total rows in dataset
    new_leads_imported = Column(Integer)  # New unique leads added
    duplicates_skipped = Column(Integer)  # Duplicates found
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    finished_at = Column(DateTime(timezone=True))
    
    # Error tracking
    error_message = Column(Text, nullable=True)
