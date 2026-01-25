"""
Test script for ReplyAgent with synthetic inbound replies.
Tests AI classification, confidence gating, and escalation logic.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.conversation.reply_agent import ReplyAgent, ReplyAction, ReplyIntent
from src.config import app_config
from loguru import logger
from datetime import datetime


# Test cases with expected outcomes
TEST_CASES = [
    {
        "name": "Interested - Simple Yes",
        "message": "Yes, I'm interested",
        "expected_intent": ReplyIntent.INTERESTED,
        "expected_action": ReplyAction.AUTO_REPLY,
        "expected_escalate": False
    },
    {
        "name": "Interested - Tell Me More",
        "message": "Tell me more about this",
        "expected_intent": ReplyIntent.INTERESTED,
        "expected_action": ReplyAction.AUTO_REPLY,
        "expected_escalate": False
    },
    {
        "name": "Scheduling - When Can We Talk",
        "message": "When can we talk?",
        "expected_intent": ReplyIntent.SCHEDULING,
        "expected_action": ReplyAction.AUTO_REPLY,
        "expected_escalate": False
    },
    {
        "name": "Scheduling - Available Thursday",
        "message": "I'm available Thursday afternoon",
        "expected_intent": ReplyIntent.SCHEDULING,
        "expected_action": ReplyAction.AUTO_REPLY,
        "expected_escalate": False
    },
    {
        "name": "Simple Question - Call Duration",
        "message": "How long is the call?",
        "expected_intent": ReplyIntent.SIMPLE_QUESTION,
        "expected_action": ReplyAction.AUTO_REPLY,
        "expected_escalate": False
    },
    {
        "name": "Simple Question - Phone or Video",
        "message": "Is this by phone or zoom?",
        "expected_intent": ReplyIntent.SIMPLE_QUESTION,
        "expected_action": ReplyAction.AUTO_REPLY,
        "expected_escalate": False
    },
    {
        "name": "FAQ - What is IUL",
        "message": "What is IUL?",
        "expected_intent": ReplyIntent.FAQ,
        "expected_action": ReplyAction.AUTO_REPLY,
        "expected_escalate": False
    },
    {
        "name": "FAQ - Who Qualifies",
        "message": "Who qualifies for this?",
        "expected_intent": ReplyIntent.FAQ,
        "expected_action": ReplyAction.AUTO_REPLY,
        "expected_escalate": False
    },
    {
        "name": "Compliance Trigger - Guaranteed Return",
        "message": "What's the guaranteed return?",
        "expected_intent": ReplyIntent.COMPLEX_QUESTION,
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Complex Question - Tax Benefits",
        "message": "Can you explain the tax benefits and compare it to my 401k?",
        "expected_intent": ReplyIntent.COMPLEX_QUESTION,
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Multiple Questions",
        "message": "How does this work? What are the fees? How much do I need? When can we start?",
        "expected_intent": None,  # Don't test specific intent
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Objection - Not Interested",
        "message": "Not interested right now, maybe later",
        "expected_intent": ReplyIntent.OBJECTION,
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Objection - Already Have Coverage",
        "message": "I already have life insurance",
        "expected_intent": ReplyIntent.OBJECTION,
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Objection - Cost Concern",
        "message": "How much does this cost? Sounds expensive",
        "expected_intent": ReplyIntent.OBJECTION,
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Unsubscribe - Stop",
        "message": "Stop emailing me",
        "expected_intent": ReplyIntent.UNSUBSCRIBE,
        "expected_action": ReplyAction.UNSUBSCRIBE,
        "expected_escalate": False
    },
    {
        "name": "Unsubscribe - Remove Me",
        "message": "Remove me from your list",
        "expected_intent": ReplyIntent.UNSUBSCRIBE,
        "expected_action": ReplyAction.UNSUBSCRIBE,
        "expected_escalate": False
    },
    {
        "name": "Complaint - This is Spam",
        "message": "This is spam, stop contacting me",
        "expected_intent": ReplyIntent.COMPLAINT,
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Complaint - Threat",
        "message": "I'm going to report you if you don't stop",
        "expected_intent": ReplyIntent.COMPLAINT,
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Complaint - Legal Threat",
        "message": "This is harassment, I'm calling my lawyer",
        "expected_intent": ReplyIntent.COMPLAINT,
        "expected_action": ReplyAction.ESCALATE,
        "expected_escalate": True
    },
    {
        "name": "Wrong Person",
        "message": "Wrong person, I don't own a business",
        "expected_intent": ReplyIntent.WRONG_PERSON,
        "expected_action": ReplyAction.UNSUBSCRIBE,
        "expected_escalate": False
    }
]


# Sample lead data
SAMPLE_LEAD = {
    "email": "john.doe@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "company_name": "Acme Corporation",
    "industry": "Technology"
}


# Sample conversation history
SAMPLE_HISTORY = [
    {
        "direction": "outbound",
        "body": "Hi John, I help business owners like you explore tax-advantaged strategies for retirement and wealth building. Would a 20-minute intro call make sense?",
        "created_at": datetime.utcnow()
    }
]


def run_tests():
    """Run all test cases and report results"""
    
    # Check if GPT-4 is configured
    if not app_config.llm_config.openai_api_key:
        logger.error("❌ OpenAI API key not configured. Set OPENAI_API_KEY in .env file.")
        logger.info("You can still test pre-screening logic (unsubscribe, threats, compliance triggers)")
        print("\nRunning pre-screening tests only...\n")
        run_prescreening_tests()
        return
    
    # Initialize agent
    logger.info("Initializing ReplyAgent with GPT-4...")
    agent = ReplyAgent(app_config.llm_config)
    
    # Run tests
    results = {
        "passed": 0,
        "failed": 0,
        "errors": 0
    }
    
    print("\n" + "="*80)
    print("REPLY AGENT TEST SUITE")
    print("="*80 + "\n")
    
    for i, test in enumerate(TEST_CASES, 1):
        print(f"\nTest {i}/{len(TEST_CASES)}: {test['name']}")
        print("-" * 80)
        print(f"Message: \"{test['message']}\"")
        
        try:
            # Run analysis
            analysis = agent.analyze_and_respond(
                inbound_message=test["message"],
                lead_data=SAMPLE_LEAD,
                conversation_history=SAMPLE_HISTORY
            )
            
            # Check results
            passed = True
            
            # Check escalation
            if analysis.escalate != test["expected_escalate"]:
                print(f"❌ FAIL: Expected escalate={test['expected_escalate']}, got {analysis.escalate}")
                passed = False
            
            # Check action
            if analysis.next_action != test["expected_action"]:
                print(f"❌ FAIL: Expected action={test['expected_action'].value}, got {analysis.next_action.value}")
                passed = False
            
            # Check intent (if specified)
            if test["expected_intent"] and analysis.intent != test["expected_intent"]:
                print(f"⚠️  WARNING: Expected intent={test['expected_intent'].value}, got {analysis.intent.value}")
                # Don't fail on intent mismatch, just warn
            
            # Display results
            print(f"Intent: {analysis.intent.value}")
            print(f"Confidence: {analysis.confidence:.2f}")
            print(f"Action: {analysis.next_action.value}")
            print(f"Escalate: {analysis.escalate}")
            
            if analysis.escalate:
                print(f"Reason: {analysis.escalation_reason}")
            else:
                print(f"Response: \"{analysis.response_text}\"")
            
            if passed:
                print("✅ PASS")
                results["passed"] += 1
            else:
                print("❌ FAIL")
                results["failed"] += 1
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
            logger.error(f"Test error: {e}", exc_info=True)
            results["errors"] += 1
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total: {len(TEST_CASES)}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⚠️  Errors: {results['errors']}")
    
    success_rate = (results["passed"] / len(TEST_CASES)) * 100
    print(f"\nSuccess Rate: {success_rate:.1f}%")
    
    if results["failed"] == 0 and results["errors"] == 0:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. Review output above.")


def run_prescreening_tests():
    """Run only pre-screening tests (no API calls)"""
    
    agent = ReplyAgent(app_config.llm_config)
    
    prescreening_tests = [
        {
            "name": "Unsubscribe - Stop",
            "message": "Stop",
            "expected_action": ReplyAction.UNSUBSCRIBE
        },
        {
            "name": "Threat - Lawyer",
            "message": "I'm calling my lawyer",
            "expected_action": ReplyAction.ESCALATE
        },
        {
            "name": "Compliance - Guaranteed",
            "message": "What's the guaranteed return?",
            "expected_action": ReplyAction.ESCALATE
        }
    ]
    
    for test in prescreening_tests:
        print(f"\n{test['name']}")
        print(f"Message: \"{test['message']}\"")
        
        result = agent._pre_screen_message(test["message"])
        
        if result:
            print(f"Intent: {result.intent.value}")
            print(f"Action: {result.next_action.value}")
            print(f"Escalate: {result.escalate}")
            
            if result.next_action == test["expected_action"]:
                print("✅ PASS")
            else:
                print(f"❌ FAIL: Expected {test['expected_action'].value}")
        else:
            print("No pre-screening match (would go to GPT-4)")


def test_notification():
    """Test notification email"""
    from src.channels.notifications import NotificationService
    from src.storage.database import get_db
    
    print("\n" + "="*80)
    print("TESTING NOTIFICATION SYSTEM")
    print("="*80 + "\n")
    
    if not app_config.llm_config.human_notification_email:
        print("❌ HUMAN_NOTIFICATION_EMAIL not configured in .env")
        return
    
    db = next(get_db())
    notification_service = NotificationService(db, app_config)
    
    print(f"Sending test notification to: {app_config.llm_config.human_notification_email}")
    
    success = notification_service.send_test_notification()
    
    if success:
        print("✅ Test notification sent successfully!")
        print("Check your email inbox.")
    else:
        print("❌ Failed to send test notification")
        print("Check SendGrid configuration and logs.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Reply Agent")
    parser.add_argument("--notification", action="store_true", help="Test notification email only")
    parser.add_argument("--prescreening", action="store_true", help="Test pre-screening logic only (no API)")
    
    args = parser.parse_args()
    
    if args.notification:
        test_notification()
    elif args.prescreening:
        run_prescreening_tests()
    else:
        run_tests()
