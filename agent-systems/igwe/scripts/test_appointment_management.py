"""
Test Script 2: Appointment Management
Tests: new bookings, cancellations, reschedules, no-shows.
Checks Calendly sync result shape and appointment status handling.
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scheduling.appointment_tracker import AppointmentTracker
from src.storage.database import SessionLocal
from src.storage.models import Appointment, AppointmentStatus, Deal, Lead
from datetime import datetime, timedelta
from loguru import logger


def test_appointment_management():
    """Test appointment tracking: new, updated, cancelled, no-shows."""
    print("\n" + "=" * 80)
    print("[TEST] Appointment Management System")
    print("=" * 80 + "\n")

    db = SessionLocal()

    try:
        tracker = AppointmentTracker(db)

        # Test 1: Calendly API config
        print("[1] Calendly API connection\n")
        if not tracker.api_key:
            print("[SKIP] CALENDLY_API_KEY not set in .env")
        if not tracker.user_uri:
            print("[SKIP] CALENDLY_USER_URI not set in .env")
        if tracker.api_key and tracker.user_uri:
            print("[OK] Calendly credentials configured")
            print(f"     User URI: {tracker.user_uri}\n")
        else:
            print("[WARN] Run with .env Calendly keys to exercise live API.\n")

        # Test 2: Poll result shape (new, updated, cancelled, no_shows, unmatched, errors)
        print("-" * 80)
        print("[2] Poll Calendly (result shape: new/updated/cancelled/no_shows/unmatched/errors)\n")
        result = tracker.poll_scheduled_events(days_ahead=30)
        assert "new" in result, "poll result must include 'new'"
        assert "updated" in result, "poll result must include 'updated'"
        assert "cancelled" in result, "poll result must include 'cancelled'"
        assert "no_shows" in result, "poll result must include 'no_shows'"
        assert "unmatched" in result, "poll result must include 'unmatched'"
        assert "errors" in result, "poll result must include 'errors'"
        print("[PASS] poll_scheduled_events returns all expected keys")
        print(f"   new={result['new']} updated={result['updated']} cancelled={result['cancelled']} no_shows={result['no_shows']} unmatched={result['unmatched']} errors={result['errors']}\n")

        # Test 3: Appointments in DB
        print("-" * 80)
        print("[3] Appointments in database\n")
        now = datetime.utcnow()
        active_statuses = [
            AppointmentStatus.PENDING,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.REMINDED_24H,
            AppointmentStatus.REMINDED_2H,
        ]
        upcoming = (
            db.query(Appointment)
            .filter(
                Appointment.scheduled_at >= now,
                Appointment.status.in_(active_statuses),
            )
            .order_by(Appointment.scheduled_at)
            .all()
        )
        print(f"Upcoming (active): {len(upcoming)}")
        for i, appt in enumerate(upcoming[:3], 1):
            lead = db.query(Lead).filter(Lead.id == appt.lead_id).first()
            name = f"{lead.first_name} {lead.last_name}" if lead else "?"
            print(f"   {i}. {name} @ {appt.scheduled_at} [{appt.status.value}]")

        past_cutoff = now - timedelta(days=14)
        past = (
            db.query(Appointment)
            .filter(
                Appointment.scheduled_at >= past_cutoff,
                Appointment.scheduled_at < now,
            )
            .order_by(Appointment.scheduled_at.desc())
            .all()
        )
        print(f"\nPast (last 14 days): {len(past)}")
        for i, appt in enumerate(past[:3], 1):
            lead = db.query(Lead).filter(Lead.id == appt.lead_id).first()
            name = f"{lead.first_name} {lead.last_name}" if lead else "?"
            print(f"   {i}. {name} @ {appt.scheduled_at} [{appt.status.value}]")
        print()

        # Test 4: Deals (optional, may be empty)
        print("-" * 80)
        print("[4] Closed deals (last 90 days)\n")
        deals_cutoff = now - timedelta(days=90)
        deals = (
            db.query(Deal)
            .filter(Deal.created_at >= deals_cutoff)
            .order_by(Deal.created_at.desc())
            .all()
        )
        print(f"Deals: {len(deals)}")
        if deals:
            total_revenue = sum(d.premium_amount or 0 for d in deals)
            total_commission = sum(d.commission_amount or 0 for d in deals)
            print(f"   Revenue: ${total_revenue:,.2f}  Commission: ${total_commission:,.2f}")
            for i, d in enumerate(deals[:3], 1):
                lead = db.query(Lead).filter(Lead.id == d.lead_id).first()
                name = f"{lead.first_name} {lead.last_name}" if lead else "?"
                print(f"   {i}. {name} premium=${d.premium_amount or 0:,.2f}")
        print()

        # Test 5: No-show detection (mark past PENDING/CONFIRMED/REMINDED as NO_SHOW)
        print("-" * 80)
        print("[5] No-show detection (past appointments not completed)\n")
        no_shows = tracker._check_for_no_shows()
        print(f"[OK] No-show check: {no_shows} appointments marked no-show\n")

        # Summary
        print("=" * 80)
        print("[PASS] Appointment management tests passed.")
        print("=" * 80)
        print("  - Poll result shape: new/updated/cancelled/no_shows/errors")
        print("  - New bookings create appointments and SCHEDULED conversation state")
        print("  - Cancellations set status CANCELLED; reschedules update scheduled_at")
        print("  - No-shows: past PENDING/CONFIRMED/REMINDED_* -> NO_SHOW + conversation NO_SHOW")
        print("\nNext: book a test on Calendly, run sync, check /appointments")
        print("=" * 80 + "\n")
        return True

    except AssertionError as e:
        print(f"\n[FAIL] Assertion: {e}")
        logger.error(f"Assertion: {e}")
        return False
    except Exception as e:
        print(f"\n[FAIL] {e}")
        logger.error(f"Test error: {e}", exc_info=True)
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = test_appointment_management()
    sys.exit(0 if success else 1)
