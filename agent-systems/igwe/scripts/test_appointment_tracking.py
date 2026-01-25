"""
Test the appointment tracking system.
Verifies Calendly API connectivity and polling functionality.
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scheduling.appointment_tracker import AppointmentTracker
from src.storage.database import SessionLocal
from loguru import logger


def test_calendly_api():
    """Test Calendly API connection and polling"""
    print("\n" + "="*80)
    print("🧪 Testing Calendly Appointment Tracking System")
    print("="*80 + "\n")
    
    db = SessionLocal()
    
    try:
        tracker = AppointmentTracker(db)
        
        # Check credentials
        if not tracker.api_key:
            print("❌ CALENDLY_API_KEY not configured in .env")
            return False
        
        if not tracker.user_uri:
            print("❌ CALENDLY_USER_URI not configured in .env")
            return False
        
        print("✅ Calendly credentials configured")
        print(f"   User URI: {tracker.user_uri}")
        print()
        
        # Test polling
        print("📡 Polling Calendly API for scheduled events...")
        result = tracker.poll_scheduled_events(days_ahead=30)
        
        print(f"\n✅ Polling successful!")
        print(f"   New appointments: {result['new']}")
        print(f"   Updated: {result['updated']}")
        print(f"   Cancelled: {result['cancelled']}")
        print(f"   No-shows detected: {result['no_shows']}")
        print(f"   Errors: {result['errors']}")
        
        # Get upcoming appointments
        upcoming = tracker.get_upcoming_appointments(days_ahead=30)
        print(f"\n📅 Upcoming appointments in database: {len(upcoming)}")
        
        if upcoming:
            print("\nNext 3 appointments:")
            for i, appt in enumerate(upcoming[:3], 1):
                lead = db.query(Lead).filter(Lead.id == appt.lead_id).first()
                print(f"   {i}. {lead.first_name} {lead.last_name} - {appt.scheduled_at.strftime('%b %d at %I:%M %p')}")
        
        # Get past appointments needing review
        past = tracker.get_past_appointments_for_review(days_back=14)
        print(f"\n⏳ Past appointments needing review: {len(past)}")
        
        print("\n" + "="*80)
        print("✅ All tests passed! Appointment tracking is working.")
        print("="*80 + "\n")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.error(f"Test error: {e}", exc_info=True)
        return False
    
    finally:
        db.close()


if __name__ == "__main__":
    from src.storage.models import Lead
    success = test_calendly_api()
    sys.exit(0 if success else 1)
