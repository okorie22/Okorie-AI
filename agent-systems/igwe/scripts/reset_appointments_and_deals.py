"""
Reset appointments and deals tables to empty (for clearing test data).
Deletes in order: deals -> appointments -> unmatched_appointments.
Uses DATABASE_URL from .env. Run from igwe dir: python scripts/reset_appointments_and_deals.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.database import SessionLocal
from src.storage.models import Deal, Appointment, UnmatchedAppointment


def main():
    db = SessionLocal()
    try:
        deals_count = db.query(Deal).count()
        appointments_count = db.query(Appointment).count()
        unmatched_count = db.query(UnmatchedAppointment).count()

        print(f"Current: {deals_count} deals, {appointments_count} appointments, {unmatched_count} unmatched appointments")
        print("Deleting...")

        db.query(Deal).delete()
        db.query(Appointment).delete()
        db.query(UnmatchedAppointment).delete()
        db.commit()

        print("Done. Appointments and deals reset to 0.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
