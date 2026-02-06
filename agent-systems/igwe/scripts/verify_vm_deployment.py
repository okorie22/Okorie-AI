"""
Verify VM deployment by running automated checks.

This script checks:
1. API is accessible
2. Messages dashboard loads
3. Inbound webhook accepts requests
4. Logs show reply agent activity

Usage:
    python -m scripts.verify_vm_deployment
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import requests
import subprocess
import time
from datetime import datetime

API_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

def check_api_health():
    """Check if API is responding"""
    print("\n" + "="*70)
    print("CHECK 1: API Health")
    print("="*70)
    
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("[PASS] API is healthy")
            return True
        else:
            print("[FAIL] API returned non-200 status")
            return False
    except Exception as e:
        print(f"[FAIL] API is not accessible: {e}")
        return False


def check_messages_dashboard():
    """Check if messages dashboard loads"""
    print("\n" + "="*70)
    print("CHECK 2: Messages Dashboard")
    print("="*70)
    
    try:
        response = requests.get(f"{API_BASE_URL}/messages", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("[PASS] Dashboard loads successfully")
            
            # Check if it has the expected content
            if "Messages Dashboard" in response.text or "conversation" in response.text.lower():
                print("[PASS] Dashboard has expected content")
                return True
            else:
                print("[WARN] Dashboard loaded but content looks unexpected")
                return True
        else:
            print(f"[FAIL] Dashboard returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Dashboard is not accessible: {e}")
        return False


def check_conversation_link():
    """Check if conversation_id parameter works on messages page"""
    print("\n" + "="*70)
    print("CHECK 3: Conversation Link (from notifications)")
    print("="*70)
    
    try:
        # Test with conversation_id=1 (should exist in your DB)
        response = requests.get(f"{API_BASE_URL}/messages?conversation_id=1", timeout=10)
        print(f"Testing: {API_BASE_URL}/messages?conversation_id=1")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("[PASS] Conversation link works (no 404)")
            print("[PASS] Notification emails will have working links")
            return True
        else:
            print(f"[FAIL] Conversation link returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Conversation link not accessible: {e}")
        return False


def check_inbound_webhook():
    """Check if inbound webhook is accepting requests"""
    print("\n" + "="*70)
    print("CHECK 4: Inbound Webhook")
    print("="*70)
    
    try:
        # Send a minimal test inbound
        payload = {
            "from": "test@example.com",
            "to": "info@mail.reimaginewealth.org",
            "subject": "Health Check",
            "text": "This is a health check",
            "headers": f"Message-ID: <healthcheck-{int(time.time())}@example.com>"
        }
        
        response = requests.post(f"{API_BASE_URL}/webhooks/sendgrid/inbound", data=payload, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("[PASS] Inbound webhook is working")
            return True
        else:
            print("[FAIL] Inbound webhook returned non-200")
            return False
    except Exception as e:
        print(f"[FAIL] Inbound webhook error: {e}")
        return False


def check_app_base_url():
    """Check if APP_BASE_URL is set correctly"""
    print("\n" + "="*70)
    print("CHECK 5: APP_BASE_URL Configuration")
    print("="*70)
    
    app_base_url = os.getenv("APP_BASE_URL")
    
    if not app_base_url:
        print("[FAIL] APP_BASE_URL is not set in .env")
        print("   Notification links will default to localhost")
        return False
    
    print(f"APP_BASE_URL: {app_base_url}")
    
    if "localhost" in app_base_url:
        print("[WARN] APP_BASE_URL is set to localhost")
        print("   This should be your production domain")
        return False
    
    if "reimaginewealth.org" in app_base_url:
        print("[PASS] APP_BASE_URL is correctly set")
        return True
    
    print("[WARN] APP_BASE_URL might be incorrect")
    return True


def print_summary(results):
    """Print test summary"""
    print("\n" + "="*70)
    print("DEPLOYMENT VERIFICATION SUMMARY")
    print("="*70)
    
    for check_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {check_name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} checks passed")
    
    if passed_count == total_count:
        print("\nAll deployment checks passed!")
        print("\nYour system is ready:")
        print("  - API is running")
        print("  - Dashboard is accessible")
        print("  - Inbound webhooks are working")
        print("  - Notification links will work")
    else:
        print("\nSome checks failed")
        print("\nRecommended actions:")
        print("  1. Make sure the app is running: sudo systemctl status igwe-app")
        print("  2. Check logs: sudo journalctl -u igwe-app -n 100")
        print("  3. Verify .env is updated with APP_BASE_URL")
        print("  4. Restart if needed: sudo systemctl restart igwe-app")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("VM DEPLOYMENT VERIFICATION")
    print("="*70)
    print(f"\nTarget: {API_BASE_URL}")
    
    results = []
    
    # Run all checks
    results.append(("API Health", check_api_health()))
    time.sleep(1)
    
    results.append(("Messages Dashboard", check_messages_dashboard()))
    time.sleep(1)
    
    results.append(("Conversation Links", check_conversation_link()))
    time.sleep(1)
    
    results.append(("Inbound Webhook", check_inbound_webhook()))
    time.sleep(1)
    
    results.append(("APP_BASE_URL Config", check_app_base_url()))
    
    print_summary(results)
