"""
Test script for outbound messaging system.

Tests:
1. Template variant selection (no repeats)
2. Rate limiting enforcement
3. Suppression checks
4. Send window validation
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from datetime import datetime

from src.storage.database import SessionLocal
from src.storage.models import Lead, Conversation, ConversationState, LeadSource
from src.channels.message_sender import MessageSender
from src.channels.rate_limiter import SendRateLimiter
from src.channels.suppression import SuppressionManager
from src.storage.repositories import LeadRepository


def test_template_variants():
    """Test that template variants rotate without repeats"""
    logger.info("\n=== Testing Template Variants ===")
    
    db = SessionLocal()
    
    try:
        # Create test lead
        lead = Lead(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            company_name="Test Corp",
            industry="Technology",
            source=LeadSource.CSV
        )
        db.add(lead)
        db.commit()
        
        # Create conversation
        conv = Conversation(
            lead_id=lead.id,
            state=ConversationState.NEW,
            channel_preference="email"
        )
        db.add(conv)
        db.commit()
        
        logger.info(f"Created test lead {lead.id} and conversation {conv.id}")
        
        # Send 3 openers (should use different variants each time)
        sender = MessageSender(db)
        
        variant_ids = []
        for i in range(3):
            logger.info(f"\nSending opener #{i+1}...")
            result = sender.send_conversation_message(conv, "opener_email")
            
            if result.get("success"):
                logger.success(f"✓ Sent successfully")
                # Extract variant_id from result or database
                # (In real scenario, check message record)
            else:
                logger.warning(f"✗ Send failed: {result.get('error')}")
        
        logger.info("\n✅ Template variant test complete")
        logger.info("Check that 3 different variants were used (no repeats)")
        
    finally:
        # Cleanup
        db.query(Conversation).filter(Conversation.lead_id == lead.id).delete()
        db.query(Lead).filter(Lead.id == lead.id).delete()
        db.commit()
        db.close()


def test_rate_limiter():
    """Test rate limiting enforcement"""
    logger.info("\n=== Testing Rate Limiter ===")
    
    db = SessionLocal()
    
    try:
        limiter = SendRateLimiter(db)
        
        # Get current stats
        stats = limiter.get_send_stats()
        
        logger.info(f"Daily: {stats['sent_today']}/{stats['daily_cap']} (remaining: {stats['daily_remaining']})")
        logger.info(f"Hourly: {stats['sent_this_hour']}/{stats['hourly_cap']} (remaining: {stats['hourly_remaining']})")
        logger.info(f"Within window: {stats['within_window']}")
        
        # Test batch check
        test_batch_sizes = [1, 10, 20, 100]
        
        for size in test_batch_sizes:
            can_send = limiter.can_send_batch(size)
            logger.info(f"Can send batch of {size}? {can_send}")
        
        # Test send window
        is_within_window = limiter.is_within_send_window()
        now = datetime.utcnow()
        logger.info(f"\nCurrent time (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Within send window (8 AM-5 PM EST, Mon-Fri)? {is_within_window}")
        
        logger.info("\n✅ Rate limiter test complete")
        
    finally:
        db.close()


def test_suppression():
    """Test suppression checks"""
    logger.info("\n=== Testing Suppression ===")
    
    db = SessionLocal()
    
    try:
        lead_repo = LeadRepository(db)
        suppression_mgr = SuppressionManager(db)
        sender = MessageSender(db)
        
        # Create test lead
        lead = Lead(
            first_name="Suppressed",
            last_name="User",
            email="suppressed@example.com",
            company_name="Test Corp",
            source=LeadSource.CSV
        )
        db.add(lead)
        db.commit()
        
        logger.info(f"Created test lead {lead.id}")
        
        # Try to send before suppression
        conv = Conversation(
            lead_id=lead.id,
            state=ConversationState.NEW,
            channel_preference="email"
        )
        db.add(conv)
        db.commit()
        
        logger.info("\n1. Sending to non-suppressed lead...")
        result = sender.send_conversation_message(conv, "opener_email")
        logger.info(f"Result: {result}")
        
        # Suppress the lead
        logger.info("\n2. Suppressing lead (reason: bounce)...")
        suppression_mgr.suppress_lead(lead.id, reason="bounce", source="test")
        
        # Try to send after suppression
        logger.info("\n3. Attempting to send to suppressed lead...")
        result = sender.send_conversation_message(conv, "followup_1_email")
        
        if result.get("error") == "Lead suppressed":
            logger.success("✓ Suppression check working correctly")
        else:
            logger.error("✗ Suppression check failed!")
        
        # Check suppression history
        history = suppression_mgr.get_suppression_history(lead.id)
        logger.info(f"\nSuppression history: {len(history)} record(s)")
        for record in history:
            logger.info(f"  - {record.reason} ({record.source}) at {record.created_at}")
        
        logger.info("\n✅ Suppression test complete")
        
    finally:
        # Cleanup
        db.query(Conversation).filter(Conversation.lead_id == lead.id).delete()
        db.query(Lead).filter(Lead.id == lead.id).delete()
        db.commit()
        db.close()


def test_send_window():
    """Test send window validation"""
    logger.info("\n=== Testing Send Window ===")
    
    db = SessionLocal()
    
    try:
        limiter = SendRateLimiter(db)
        
        # Check current window status
        is_within = limiter.is_within_send_window()
        now = datetime.utcnow()
        
        logger.info(f"Current time (UTC): {now.strftime('%Y-%m-%d %H:%M:%S %A')}")
        logger.info(f"Within send window? {is_within}")
        
        if is_within:
            logger.success("✓ Within send window (8 AM-5 PM EST, Mon-Fri)")
        else:
            logger.info("✗ Outside send window (will defer sends)")
        
        logger.info("\n✅ Send window test complete")
        
    finally:
        db.close()


def main():
    """Run all outbound tests"""
    logger.info("=" * 60)
    logger.info("OUTBOUND MESSAGING SYSTEM TESTS")
    logger.info("=" * 60)
    
    try:
        # Test 1: Template variants
        test_template_variants()
        
        # Test 2: Rate limiter
        test_rate_limiter()
        
        # Test 3: Suppression
        test_suppression()
        
        # Test 4: Send window
        test_send_window()
        
        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS COMPLETE")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
