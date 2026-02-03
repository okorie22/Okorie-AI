"""
Check DB and webhook log to verify if SendGrid events are being received and recorded.
Run from project root:  python scripts/check_email_webhook_diagnostics.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import SessionLocal
from src.storage.models import Message, Lead, Suppression
from src.storage.models import MessageDirection, MessageChannel


def main():
    db = SessionLocal()
    try:
        # Outbound EMAIL only (dashboard card is "email delivery")
        q = db.query(Message).filter(
            Message.direction == MessageDirection.OUTBOUND,
            Message.channel == MessageChannel.EMAIL,
        )
        sent = q.count()
        delivered = q.filter(Message.delivered_at.isnot(None)).count()
        opened = q.filter(Message.read_at.isnot(None)).count()

        # Suppressions (bounce etc.) - from SendGrid webhook or manual
        bounce_count = db.query(Suppression).filter(Suppression.reason == "bounce").count()
        dropped_count = db.query(Suppression).filter(Suppression.reason == "dropped").count()
        total_suppressions = db.query(Suppression).count()

        # Leads with suppression_reason = bounce (what dashboard uses for bounce rate)
        leads_bounced = db.query(Lead).filter(Lead.suppression_reason == "bounce").count()

        # Last 10 outbound email messages: id, sendgrid_id, delivered_at
        recent = (
            db.query(Message)
            .filter(
                Message.direction == MessageDirection.OUTBOUND,
                Message.channel == MessageChannel.EMAIL,
            )
            .order_by(Message.id.desc())
            .limit(10)
            .all()
        )

        # Webhook log tail
        log_path = Path(__file__).resolve().parent.parent / "logs" / "sendgrid_webhook.log"
        log_lines = []
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    log_lines = f.readlines()
                log_lines = log_lines[-30:]  # last 30
            except Exception:
                log_lines = ["(could not read file)"]
        else:
            log_lines = ["(file does not exist - no webhooks logged yet)"]

        # Print report
        print("=" * 60)
        print("EMAIL DELIVERY DIAGNOSTICS")
        print("=" * 60)
        print(f"Outbound EMAIL sent (total):     {sent}")
        print(f"Delivered (delivered_at set):   {delivered}")
        print(f"Opened (read_at set):            {opened}")
        print(f"Delivery rate:                   {(delivered/sent*100) if sent else 0:.1f}%")
        print()
        print(f"Suppressions (bounce):           {bounce_count}")
        print(f"Suppressions (dropped):         {dropped_count}")
        print(f"Suppressions (total):            {total_suppressions}")
        print(f"Leads with suppression=bounce:   {leads_bounced}")
        print()
        print("Last 10 outbound EMAIL messages:")
        print("-" * 60)
        for m in recent:
            meta = m.message_metadata or {}
            sid = meta.get("sendgrid_id") or "(none)"
            if isinstance(sid, str) and len(sid) > 50:
                sid = sid[:50] + "..."
            da = m.delivered_at.strftime("%Y-%m-%d %H:%M") if m.delivered_at else "NULL"
            print(f"  id={m.id}  sendgrid_id={sid}  delivered_at={da}")
        print()
        print("Last 30 lines of logs/sendgrid_webhook.log:")
        print("-" * 60)
        for line in log_lines:
            print(line.rstrip())
        print("=" * 60)
        if sent and delivered == 0 and not log_lines[0].startswith("("):
            print("VERDICT: Webhook log has entries but delivered_at is never set.")
        elif sent and delivered == 0 and log_path.exists() and len(log_lines) == 0:
            print("VERDICT: Log file exists but empty - webhooks may not be reaching the app.")
        elif sent and delivered == 0 and not log_path.exists():
            print("VERDICT: No webhook log file. Ensure Event Webhook URL is HTTPS and points to this app.")
        elif delivered > 0:
            print("VERDICT: Delivery events are being received and stored.")
        else:
            print("VERDICT: No outbound email messages in DB yet.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
