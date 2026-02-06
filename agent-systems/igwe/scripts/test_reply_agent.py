"""
Test script to verify the reply agent triggers properly for inbounds.

Tests:
1. Reply agent triggering for new leads
2. Reply agent triggering for existing leads
3. Deduplication (same Message-ID sent twice)
4. Notification sending

Usage:
    python -m scripts.test_reply_agent
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import requests
import time
from datetime import datetime
import json

# Configuration
API_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
INBOUND_URL = f"{API_BASE_URL}/webhooks/sendgrid/inbound"

def test_reply_agent_trigger():
    """Test that reply agent gets triggered for an inbound"""
    print("\n" + "="*70)
    print("TEST 1: Reply Agent Triggering")
    print("="*70)
    
    test_email = f"test-reply-agent-{int(time.time())}@example.com"
    message_id = f"<test-{int(time.time())}@example.com>"
    
    payload = {
        "from": f"Test User <{test_email}>",
        "to": "info@mail.reimaginewealth.org",
        "subject": "Test Reply Agent",
        "text": "Yes I am very interested in learning more about IUL",
        "html": "<p>Yes I am very interested in learning more about IUL</p>",
        "headers": f"Message-ID: {message_id}\nDate: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')}"
    }
    
    print(f"\nSending test inbound from: {test_email}")
    print(f"Message-ID: {message_id}")
    
    response = requests.post(INBOUND_URL, data=payload)
    
    print(f"\nResponse Status: {response.status_code}")
    try:
        print(f"Response Body: {response.json()}")
    except:
        print(f"Response Body: {response.text}")
    
    if response.status_code == 200:
        print("\n[PASS] Inbound accepted")
        print("\nNext Steps:")
        print("   1. SSH into your VM")
        print("   2. Run: sudo journalctl -u igwe-app -n 100 --no-pager | grep -E 'AI Analysis:|Queuing delayed reply'")
        print("   3. You should see lines like:")
        print("      - 'AI Analysis: intent=interested, confidence=...'")
        print("      - 'Queuing delayed reply for conversation...'")
        print("\n   If you see those lines, the reply agent is working!")
        return True
    else:
        print("\n[FAIL] Inbound rejected")
        return False


def test_deduplication():
    """Test that duplicate Message-IDs are rejected"""
    print("\n" + "="*70)
    print("TEST 2: Deduplication")
    print("="*70)
    
    test_email = f"test-dedupe-{int(time.time())}@example.com"
    message_id = f"<test-dedupe-{int(time.time())}@example.com>"
    
    payload = {
        "from": f"Duplicate Test <{test_email}>",
        "to": "info@mail.reimaginewealth.org",
        "subject": "Deduplication Test",
        "text": "This message should only appear once",
        "html": "<p>This message should only appear once</p>",
        "headers": f"Message-ID: {message_id}\nDate: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')}"
    }
    
    print(f"\nSending first inbound (should succeed)...")
    print(f"From: {test_email}")
    print(f"Message-ID: {message_id}")
    
    response1 = requests.post(INBOUND_URL, data=payload)
    print(f"\nFirst attempt - Status: {response1.status_code}")
    try:
        print(f"Response: {response1.json()}")
    except:
        print(f"Response: {response1.text}")
    
    # Wait a moment
    time.sleep(2)
    
    print(f"\nSending DUPLICATE inbound (should be rejected)...")
    response2 = requests.post(INBOUND_URL, data=payload)
    print(f"\nSecond attempt - Status: {response2.status_code}")
    try:
        print(f"Response: {response2.json()}")
    except:
        print(f"Response: {response2.text}")
    
    if response1.status_code == 200 and response2.status_code == 200:
        resp2_msg = response2.json().get("message", "")
        if "duplicate" in resp2_msg.lower() or "already processed" in resp2_msg.lower():
            print("\n[PASS] Duplicate was detected and rejected")
            print("\nVerify in dashboard:")
            print(f"   Go to {API_BASE_URL}/messages")
            print(f"   Search for: {test_email}")
            print("   You should see ONLY ONE message, not two")
            return True
        else:
            print("\n[FAIL] Duplicate was NOT detected (created twice)")
            return False
    else:
        print("\n[FAIL] First inbound was rejected")
        return False


def test_notification_sending():
    """Test that notifications are sent for inbounds"""
    print("\n" + "="*70)
    print("TEST 3: Notification Sending")
    print("="*70)
    
    test_email = f"test-notification-{int(time.time())}@example.com"
    message_id = f"<test-notif-{int(time.time())}@example.com>"
    
    payload = {
        "from": f"Notification Test <{test_email}>",
        "to": "info@mail.reimaginewealth.org",
        "subject": "Notification Test",
        "text": "You should receive a notification for this message",
        "html": "<p>You should receive a notification for this message</p>",
        "headers": f"Message-ID: {message_id}\nDate: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')}"
    }
    
    print(f"\nSending test inbound (notification should be sent)...")
    print(f"From: {test_email}")
    
    response = requests.post(INBOUND_URL, data=payload)
    print(f"\nResponse Status: {response.status_code}")
    try:
        print(f"Response Body: {response.json()}")
    except:
        print(f"Response Body: {response.text}")
    
    if response.status_code == 200:
        print("\n[PASS] Inbound accepted")
        print("\nCheck your email:")
        print(f"   Recipient: {os.getenv('HUMAN_NOTIFICATION_EMAIL', 'contact@okemokorie.com')}")
        print("   Subject: [NEW REPLY] Notification replied")
        print("   Body: Should contain the test message")
        print("\n   Click 'View Full Conversation' link in email")
        print("   It should take you to the messages dashboard (NOT 404)")
        return True
    else:
        print("\n[FAIL] Inbound rejected")
        return False


def test_existing_lead():
    """Test reply agent for existing known lead"""
    print("\n" + "="*70)
    print("TEST 4: Existing Lead Reply Agent")
    print("="*70)
    
    # Use your actual email
    test_email = "chibuokem.okorie@gmail.com"
    message_id = f"<test-existing-{int(time.time())}@example.com>"
    
    payload = {
        "from": f"Okem Okorie <{test_email}>",
        "to": "info@mail.reimaginewealth.org",
        "subject": "Follow-up question",
        "text": "What are the tax benefits of IUL?",
        "html": "<p>What are the tax benefits of IUL?</p>",
        "headers": f"Message-ID: {message_id}\nDate: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')}"
    }
    
    print(f"\nSending inbound from existing lead: {test_email}")
    print(f"Message-ID: {message_id}")
    
    response = requests.post(INBOUND_URL, data=payload)
    
    print(f"\nResponse Status: {response.status_code}")
    try:
        print(f"Response Body: {response.json()}")
    except:
        print(f"Response Body: {response.text}")
    
    if response.status_code == 200:
        print("\n[PASS] Inbound accepted")
        print("\nVerify:")
        print("   1. Check logs for 'AI Analysis' and 'Queuing delayed reply'")
        print("   2. Check dashboard - message should appear")
        print("   3. Check notification email")
        return True
    else:
        print("\n[FAIL] Inbound rejected")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("REPLY AGENT TEST SUITE")
    print("="*70)
    print(f"\nTesting against: {API_BASE_URL}")
    print(f"Notification email: {os.getenv('HUMAN_NOTIFICATION_EMAIL', 'contact@okemokorie.com')}")
    
    results = []
    
    # Run all tests
    results.append(("Reply Agent Trigger", test_reply_agent_trigger()))
    time.sleep(3)
    
    results.append(("Deduplication", test_deduplication()))
    time.sleep(3)
    
    results.append(("Notification Sending", test_notification_sending()))
    time.sleep(3)
    
    results.append(("Existing Lead", test_existing_lead()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed - check output above")
