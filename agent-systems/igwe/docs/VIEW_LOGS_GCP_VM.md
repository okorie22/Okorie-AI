# Viewing logs on your Google Cloud VM

Your app runs on a GCP VM. To see logs and debug webhooks/metrics, use the steps below.

## 1. SSH into the VM

- **Google Cloud Console**: Compute Engine → VM instances → click **SSH** next to your instance (opens a browser shell), or use “Open in browser window”.
- **From your PC (if you use gcloud)**:
  ```bash
  gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE --project=YOUR_PROJECT_ID
  ```
  Replace `YOUR_VM_NAME`, `YOUR_ZONE`, and `YOUR_PROJECT_ID` with your values (find them in the Console).

## 2. Where the app and logs live

After SSH, go to the app directory (adjust if yours is different):

```bash
cd /home/YOUR_USER/Okorie-AI/agent-systems/igwe
# or wherever you cloned and run the app
```

The app writes logs under a **`logs/`** folder in this directory:

| File | Contents |
|------|----------|
| `logs/sendgrid_webhook.log` | Each SendGrid webhook event (delivered, bounce, etc.) — **use this to verify webhooks are reaching the app** |
| `logs/fastapi.log` | FastAPI/API server output |
| `logs/celery_worker.log` | Celery worker (tasks, sends) |
| `logs/celery_beat.log` | Celery beat scheduler |
| `logs/system_*.log` | General system log (rotated daily) |

Create the folder if it doesn’t exist (the app creates it when writing the first webhook log):

```bash
mkdir -p logs
```

## 3. Watch SendGrid webhooks in real time

To see whether SendGrid events (delivered, bounce, etc.) are hitting your app:

```bash
tail -f logs/sendgrid_webhook.log
```

Each line is: `timestamp`, `event`, `sg_message_id=...`, `email=...`, `success=true/false`.  
Leave this running while you send test emails; if nothing appears, the Event Webhook URL is not reaching the VM (e.g. ngrok down or wrong URL).

## 4. Watch API and worker logs

```bash
# API (webhook endpoint runs here)
tail -f logs/fastapi.log

# Celery worker (sending emails)
tail -f logs/celery_worker.log
```

## 5. Search recent webhook activity

```bash
# Last 50 webhook lines
tail -50 logs/sendgrid_webhook.log

# Only "delivered" events
grep delivered logs/sendgrid_webhook.log

# Only "bounce" events
grep bounce logs/sendgrid_webhook.log
```

## 6. Get email metrics from the app (no SendGrid UI needed)

If the Event Webhook is configured with an **HTTPS** URL that points to your app (e.g. ngrok HTTPS or your domain), the app stores delivery/bounce and exposes metrics via API:

- **From the VM** (same machine as the app):
  ```bash
  curl -s http://localhost:8000/analytics/email-metrics
  ```
- **From your browser or Postman** (if the API is reachable):
  ```
  https://YOUR_NGROK_OR_DOMAIN/analytics/email-metrics
  ```

Response example:

```json
{
  "status": "ok",
  "email_metrics": {
    "outbound_emails_sent": 150,
    "delivered_count": 120,
    "delivery_rate_pct": 80.0,
    "bounce_dropped_blocked_count": 10,
    "bounce_rate_pct": 6.67
  }
}
```

If `delivery_rate_pct` is 0 but you know emails were sent, webhooks are likely not reaching the app — check `logs/sendgrid_webhook.log` and your SendGrid Event Webhook URL (must be HTTPS).

## 7. SendGrid requires HTTPS

SendGrid will only send events to an **HTTPS** Event Webhook URL. Options:

- **ngrok**: Use an ngrok HTTPS URL (e.g. `https://xxxx.ngrok.io/webhooks/sendgrid`) in SendGrid → Mail Settings → Event Webhook. Ensure ngrok is running on the VM and the URL is updated in SendGrid if it changes.
- **Domain + TLS**: Expose your app with a domain and SSL (e.g. reverse proxy with Let’s Encrypt) and use that HTTPS URL as the Event Webhook.

## 8. Quick checklist for “no metrics / 0% delivery”

1. SSH into the VM and run: `tail -f logs/sendgrid_webhook.log`.
2. Send a test email from the app; see if any line appears (e.g. `delivered`).
3. If **no lines**: Event Webhook URL is not reaching the app — fix ngrok or use an HTTPS URL that reaches the VM.
4. If **lines appear** but `delivery_rate_pct` is still 0: check for errors in `logs/fastapi.log` (e.g. message not found for `sg_message_id`); the app now logs and matches IDs more flexibly.
5. Call `GET /analytics/email-metrics` to read metrics from the app after webhooks are flowing.
