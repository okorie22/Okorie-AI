"""
Test script to verify compliance guardrails and core functionality.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.conversation.llm_agent import ComplianceGuardrails, LLMAgent, Intent, NextStage
from src.storage.database import SessionLocal, init_db
from src.ingestion.lead_processor import LeadProcessor
from src.intelligence.scorer import LeadScorer
from src.workflow.state_machine import StateMachine, WorkflowEngine
from loguru import logger


def test_compliance_guardrails():
    """Test compliance checks"""
    logger.info("Testing compliance guardrails...")
    
    guardrails = ComplianceGuardrails()
    
    # Test STOP detection
    assert guardrails.check_stop_intent("STOP"), "Failed to detect STOP"
    assert guardrails.check_stop_intent("Please unsubscribe me"), "Failed to detect unsubscribe"
    assert not guardrails.check_stop_intent("This is great information"), "False positive on STOP"
    
    # Test prohibited content
    violations = guardrails.check_prohibited_content("We guarantee 10% returns")
    assert len(violations) > 0, "Failed to detect prohibited content"
    
    violations = guardrails.check_prohibited_content("This strategy can help you grow your wealth")
    assert len(violations) == 0, "False positive on prohibited content"
    
    # Test escalation keywords
    assert guardrails.needs_escalation("I will sue you"), "Failed to detect escalation keyword"
    assert not guardrails.needs_escalation("Can you tell me more?"), "False positive on escalation"
    
    # Test sanitization
    sanitized = guardrails.sanitize_response("We guarantee great returns")
    assert "guarantee" not in sanitized.lower() or "expect" in sanitized.lower(), "Failed to sanitize"
    
    logger.success("✓ Compliance guardrails tests passed")


def test_state_transitions():
    """Test state machine transitions"""
    logger.info("Testing state machine...")
    
    db = SessionLocal()
    try:
        # Initialize database
        init_db()
        
        state_machine = StateMachine(db)
        
        # Create test lead
        from src.storage.models import Lead, Conversation, ConversationState, MessageChannel
        
        test_lead = Lead(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            source="manual",
            consent_email=True
        )
        db.add(test_lead)
        db.commit()
        db.refresh(test_lead)
        
        # Create conversation
        test_conv = Conversation(
            lead_id=test_lead.id,
            state=ConversationState.NEW,
            channel=MessageChannel.EMAIL
        )
        db.add(test_conv)
        db.commit()
        db.refresh(test_conv)
        
        # Test valid transition
        assert state_machine.can_transition(ConversationState.NEW, ConversationState.CONTACTED), "Valid transition failed"
        
        # Test invalid transition
        assert not state_machine.can_transition(ConversationState.NEW, ConversationState.QUALIFIED), "Invalid transition allowed"
        
        # Test actual transition
        success = state_machine.transition(test_conv, ConversationState.CONTACTED)
        assert success, "Transition execution failed"
        assert test_conv.state == ConversationState.CONTACTED, "State not updated"
        
        # Clean up
        db.delete(test_conv)
        db.delete(test_lead)
        db.commit()
        
        logger.success("✓ State machine tests passed")
    
    finally:
        db.close()


def test_scoring():
    """Test lead scoring"""
    logger.info("Testing lead scoring...")
    
    db = SessionLocal()
    try:
        init_db()
        
        scorer = LeadScorer(db)
        
        # Create test lead
        from src.storage.models import Lead
        
        test_lead = Lead(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            company_name="Test Corp",
            industry="technology",
            employee_size=35,
            founded_year=2018,
            state="Texas",
            linkedin_url="https://linkedin.com/in/johndoe",
            source="csv"
        )
        db.add(test_lead)
        db.commit()
        db.refresh(test_lead)
        
        # Score lead
        score_record = scorer.score_lead(test_lead)
        
        assert score_record is not None, "Scoring failed"
        assert 0 <= score_record.score <= 100, "Invalid score range"
        assert 1 <= score_record.tier <= 5, "Invalid tier"
        
        logger.info(f"Lead scored: {score_record.score} points (Tier {score_record.tier})")
        
        # Clean up
        db.delete(score_record)
        db.delete(test_lead)
        db.commit()
        
        logger.success("✓ Scoring tests passed")
    
    finally:
        db.close()


def test_message_templates():
    """Test message template rendering"""
    logger.info("Testing message templates...")
    
    from src.conversation.templates import MessageTemplates
    from src.storage.models import Lead
    
    templates = MessageTemplates()
    
    # Create test lead
    test_lead = Lead(
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        company_name="Smith & Co",
        industry="law practice",
        employee_size=25,
        state="California"
    )
    
    # Render template
    rendered = templates.render("opener_email", test_lead)
    
    assert "subject" in rendered, "Missing subject"
    assert "body" in rendered, "Missing body"
    assert "Jane" in rendered["body"], "First name not in body"
    assert "Smith & Co" in rendered["body"], "Company name not in body"
    
    logger.success("✓ Message template tests passed")


def run_all_tests():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("Running IUL Appointment Setter Tests")
    logger.info("=" * 60)
    
    try:
        test_compliance_guardrails()
        test_state_transitions()
        test_scoring()
        test_message_templates()
        
        logger.info("=" * 60)
        logger.success("ALL TESTS PASSED ✓")
        logger.info("=" * 60)
        
        return True
    
    except Exception as e:
        logger.error(f"Tests failed: {e}")
        logger.exception(e)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
