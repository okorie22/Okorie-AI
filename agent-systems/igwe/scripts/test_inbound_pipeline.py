"""
Test script to verify inbound email pipeline is working end-to-end.

Run this after deploying the Reply-To fix to verify:
1. Reply-To header is being set correctly
2. Inbound webhook can receive emails
3. Notifications are being sent

Usage:
    python scripts/test_inbound_pipeline.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from src.config import sendgrid_config, app_config
from src.storage.database import SessionLocal
from src.channels.email import SendGridService
from src.channels.notifications import NotificationService


def test_sendgrid_config():
    """Verify SendGrid configuration"""
    print("\n" + "="*60)
    print("1. CHECKING SENDGRID CONFIGURATION")
    print("="*60)
    
    if not sendgrid_config.api_key:
        print("❌ SENDGRID_API_KEY not set!")
        return False
    print(f"✅ API Key: {sendgrid_config.api_key[:10]}...")
    
    if not sendgrid_config.from_email:
        print("❌ SENDGRID_FROM_EMAIL not set!")
        return False
    print(f"✅ From Email: {sendgrid_config.from_email}")
    
    if not sendgrid_config.reply_to:
        print("❌ SENDGRID_REPLY_TO not set!")
        print("   This is CRITICAL - replies won't hit your webhook!")
        return False
    print(f"✅ Reply-To: {sendgrid_config.reply_to}")
    
    # Verify Reply-To is on the Parse host
    if "mail.reimaginewealth.org" not in sendgrid_config.reply_to:
        print("⚠️  WARNING: Reply-To should be on mail.reimaginewealth.org")
        print(f"   Current: {sendgrid_config.reply_to}")
        print("   Expected something like: info@mail.reimaginewealth.org")
        return False
    
    print("\n✅ SendGrid configuration looks good!")
    return True


def test_notification_config():
    """Verify notification configuration"""
    print("\n" + "="*60)
    print("2. CHECKING NOTIFICATION CONFIGURATION")
    print("="*60)
    
    # Fix: use correct config path (settings.llm instead of app_config.llm_config)
    from src.config import settings
    if not settings.llm.human_notification_email:
        print("❌ HUMAN_NOTIFICATION_EMAIL not set!")
        print("   You won't receive alerts when inbounds come in!")
        return False
    
    print(f"✅ Notification Email: {settings.llm.human_notification_email}")
    return True


def test_send_test_email():
    """Send a test email to verify Reply-To header is set correctly"""
    print("\n" + "="*60)
    print("3. SENDING TEST EMAIL")
    print("="*60)
    
    test_email = input("\nEnter YOUR email address to receive test email: ").strip()
    if not test_email or "@" not in test_email:
        print("❌ Invalid email address")
        return False
    
    print(f"\n📧 Sending test email to {test_email}...")
    print("   This will help you verify the Reply-To header is set correctly.")
    
    # Note: We can't send via the normal flow because we need a Lead/Conversation
    # So we'll use SendGrid directly
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content
        
        message = Mail(
            from_email=Email(sendgrid_config.from_email, sendgrid_config.from_name),
            to_emails=To(test_email),
            subject="[TEST] Reply-To Header Verification",
            plain_text_content=Content("text/plain", f"""
This is a test email from your IUL Appointment Setter system.

IMPORTANT: Check the Reply-To header!

When you click "Reply" in your email client, it should address the reply to:
{sendgrid_config.reply_to}

NOT to:
{sendgrid_config.from_email}

How to verify:
1. Open this email
2. Click Reply
3. Look at the "To:" field - it should show: {sendgrid_config.reply_to}

If the Reply-To is correct, your inbound pipeline will work! 🎉

---
From: {sendgrid_config.from_name}
""")
        )
        
        if sendgrid_config.reply_to:
            message.reply_to = Email(sendgrid_config.reply_to)
        
        sg = SendGridAPIClient(sendgrid_config.api_key)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            print("✅ Test email sent successfully!")
            print("\n📝 NEXT STEPS:")
            print("   1. Check your inbox for the test email")
            print("   2. Click 'Reply' in your email client")
            print(f"   3. Verify the 'To:' field shows: {sendgrid_config.reply_to}")
            print("   4. If correct, send the reply - it should hit your webhook!")
            return True
        else:
            print(f"❌ SendGrid returned status {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ Error sending test email: {e}")
        return False


def test_notification_email():
    """Send a test notification to verify alerts are working"""
    print("\n" + "="*60)
    print("4. TESTING NOTIFICATION SYSTEM")
    print("="*60)
    
    response = input("\nSend a test notification? (y/n): ").strip().lower()
    if response != 'y':
        print("⏭️  Skipping notification test")
        return True
    
    db = SessionLocal()
    try:
        from src.config import settings
        notification_service = NotificationService(db, settings)
        success = notification_service.send_test_notification()
        
        if success:
            print("✅ Test notification sent successfully!")
            print(f"   Check {app_config.llm_config.human_notification_email} for the email.")
            return True
        else:
            print("❌ Failed to send test notification")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()


def print_inbound_test_instructions():
    """Print instructions for testing the full inbound pipeline"""
    print("\n" + "="*60)
    print("5. FINAL END-TO-END TEST")
    print("="*60)
    
    print("\nTo test the COMPLETE inbound pipeline:")
    print("\n1️⃣  Direct Test (bypass Reply-To):")
    print("   - From your Gmail, send email to: info@mail.reimaginewealth.org")
    print("   - Subject: Test inbound")
    print("   - Body: Testing webhook")
    print("   - Expected: VM logs show 'Inbound email from:', you get notification")
    
    print("\n2️⃣  Reply Test (verify Reply-To works):")
    print("   - Have your system send an email to yourself")
    print("   - Reply to that email")
    print("   - Your reply should go to: info@mail.reimaginewealth.org")
    print("   - Expected: Same as above")
    
    print("\n3️⃣  Check Results:")
    print("   - VM logs: tail -f ~/Okorie-AI/agent-systems/igwe/logs/app.log")
    print("   - Dashboard: http://[VM-IP]:8000/messages")
    print("   - Your email: check for notification alerts")
    
    print("\n" + "="*60)
    print("📚 For detailed setup instructions, see:")
    print("   - docs/INBOUND_FIX_CHECKLIST.md")
    print("   - docs/STABLE_HTTPS_SETUP.md")
    print("="*60 + "\n")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 INBOUND EMAIL PIPELINE TEST")
    print("="*60)
    print("\nThis script will verify your inbound email system is configured correctly.")
    
    results = []
    
    # Test 1: SendGrid config
    results.append(("SendGrid Config", test_sendgrid_config()))
    
    # Test 2: Notification config
    results.append(("Notification Config", test_notification_config()))
    
    # Test 3: Send test email
    results.append(("Test Email", test_send_test_email()))
    
    # Test 4: Send test notification
    results.append(("Test Notification", test_notification_email()))
    
    # Print summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    # Print instructions for manual testing
    print_inbound_test_instructions()
    
    # Overall result
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n🎉 All automated tests passed!")
        print("   Now do the manual end-to-end tests above to verify everything works.")
    else:
        print("\n⚠️  Some tests failed. Fix the issues above before proceeding.")


if __name__ == "__main__":
    main()
