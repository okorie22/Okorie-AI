"""
Test script to demonstrate TEST_MODE functionality.
Verifies that emails/SMS are logged but not actually sent.
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger

from src.storage.models import Base, Lead, Conversation, Message, ConversationState
from src.channels.email import SendGridService
from src.channels.sms import TwilioService
from src.config import sendgrid_config, twilio_config


def test_email_test_mode(db):
    """Test that emails are logged but not sent in TEST_MODE"""
    logger.info("=" * 60)
    logger.info("Testing EMAIL TEST_MODE")
    logger.info("=" * 60)
    
    # Create test lead
    lead = Lead(
        first_name="John",
        last_name="Test",
        email="test@example.com",
        company_name="Test Company",
        title="CEO",
        consent_email=True
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    
    # Create test conversation
    conversation = Conversation(
        lead_id=lead.id,
        state=ConversationState.NEW,
        channel="email"
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    # Attempt to send email
    email_service = SendGridService(db)
    result = email_service.send_email(
        to_email="test@example.com",
        subject="Test Email",
        body="This is a test email that should NOT be sent if TEST_MODE is enabled.",
        lead_id=lead.id,
        conversation_id=conversation.id
    )
    
    logger.info(f"\nEmail send result: {result}")
    
    # Check if message was logged
    message = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).first()
    
    if message:
        logger.info(f"✅ Message logged in database (ID: {message.id})")
        logger.info(f"   Test mode flag: {message.metadata.get('test_mode', False)}")
        logger.info(f"   SendGrid ID: {message.metadata.get('sendgrid_id')}")
        
        if message.metadata.get('test_mode'):
            logger.success("✅ TEST_MODE working correctly for emails!")
        else:
            logger.warning("⚠️  TEST_MODE might be disabled - check SENDGRID_TEST_MODE")
    else:
        logger.error("❌ Message not logged in database")
    
    return result.get('success', False)


def test_sms_test_mode(db):
    """Test that SMS are logged but not sent in TEST_MODE"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing SMS TEST_MODE")
    logger.info("=" * 60)
    
    # Create test lead
    lead = Lead(
        first_name="Jane",
        last_name="Test",
        phone="+15551234567",
        company_name="Test Company 2",
        title="COO",
        consent_sms=True
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    
    # Create test conversation
    conversation = Conversation(
        lead_id=lead.id,
        state=ConversationState.NEW,
        channel="sms"
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    # Attempt to send SMS
    sms_service = TwilioService(db)
    result = sms_service.send_sms(
        to_number="+15551234567",
        body="This is a test SMS that should NOT be sent if TEST_MODE is enabled.",
        lead_id=lead.id,
        conversation_id=conversation.id,
        check_consent=False  # Skip consent for testing
    )
    
    logger.info(f"\nSMS send result: {result}")
    
    # Check if message was logged
    message = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).first()
    
    if message:
        logger.info(f"✅ Message logged in database (ID: {message.id})")
        logger.info(f"   Test mode flag: {message.metadata.get('test_mode', False)}")
        logger.info(f"   Twilio SID: {message.metadata.get('twilio_sid')}")
        
        if message.metadata.get('test_mode'):
            logger.success("✅ TEST_MODE working correctly for SMS!")
        else:
            logger.warning("⚠️  TEST_MODE might be disabled - check TWILIO_TEST_MODE")
    else:
        logger.error("❌ Message not logged in database")
    
    return result.get('success', False)


def main():
    logger.info("🧪 TEST_MODE Demonstration Script\n")
    
    # Check configuration
    logger.info("Current Configuration:")
    logger.info(f"  SENDGRID_TEST_MODE: {sendgrid_config.test_mode}")
    logger.info(f"  TWILIO_TEST_MODE: {twilio_config.test_mode}")
    logger.info("")
    
    if not sendgrid_config.test_mode:
        logger.warning("⚠️  WARNING: SENDGRID_TEST_MODE is False - emails will be sent!")
        logger.warning("   Set SENDGRID_TEST_MODE=True in .env to prevent actual sends")
    
    if not twilio_config.test_mode:
        logger.warning("⚠️  WARNING: TWILIO_TEST_MODE is False - SMS will be sent!")
        logger.warning("   Set TWILIO_TEST_MODE=True in .env to prevent actual sends")
    
    # Create test database
    engine = create_engine("sqlite:///./test_mode_demo.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Run tests
        email_success = test_email_test_mode(db)
        sms_success = test_sms_test_mode(db)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("TEST_MODE Summary")
        logger.info("=" * 60)
        
        if sendgrid_config.test_mode and email_success:
            logger.success("✅ Email TEST_MODE: Working correctly")
        elif not sendgrid_config.test_mode:
            logger.warning("⚠️  Email TEST_MODE: Disabled (emails would be sent)")
        else:
            logger.error("❌ Email TEST_MODE: Failed")
        
        if twilio_config.test_mode and sms_success:
            logger.success("✅ SMS TEST_MODE: Working correctly")
        elif not twilio_config.test_mode:
            logger.warning("⚠️  SMS TEST_MODE: Disabled (SMS would be sent)")
        else:
            logger.error("❌ SMS TEST_MODE: Failed")
        
        logger.info("\n💡 Tip: Check test_mode_demo.db to see logged messages")
        logger.info("   All messages should have test_mode=True in metadata")
    
    finally:
        db.close()
        # Cleanup test database
        if os.path.exists("test_mode_demo.db"):
            os.remove("test_mode_demo.db")
            logger.info("\n🧹 Test database cleaned up")


if __name__ == "__main__":
    main()
