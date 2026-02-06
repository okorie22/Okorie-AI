# DEPLOY FIXES - READ THIS ON VM

## Code changes pushed to GitHub

Three fixes applied:
1. **Deduplication** - prevents SendGrid retries from creating duplicate messages/notifications
2. **Reply agent unblocked** - removed early return that prevented AI from analyzing new lead inbounds
3. **Repository method added** - `get_by_metadata_field` for duplicate detection

## VM Deployment Steps

### 1. Pull latest code
```bash
cd ~/Okorie-AI
git pull origin main
```

### 2. Add missing env variable
Edit `~/Okorie-AI/agent-systems/igwe/.env` and add this line:
```bash
APP_BASE_URL=https://api.reimaginewealth.org
```

This fixes notification email links (stops them from pointing to localhost).

### 3. Restart the app
```bash
sudo systemctl restart igwe-app
```

### 4. Verify it's running
```bash
sudo systemctl status igwe-app
```

Should show "active (running)".

## What's Fixed

- **No more duplicate notifications** - same email won't process 3-4 times
- **Reply agent will now run** - AI will analyze and queue responses for ALL inbounds (new and existing leads)
- **Notification links work** - will point to https://api.reimaginewealth.org instead of localhost

## Expected Behavior After Deploy

When someone replies to your emails:
1. Inbound appears in `/messages` dashboard (once, not duplicated)
2. You get ONE notification email at contact@okemokorie.com
3. AI analyzes the message (logs will show "AI Analysis: intent=...")
4. AI queues a reply (logs will show "Queuing delayed reply...")
5. Reply sends after 30-90 minutes, during business hours (8am-5pm EST weekdays)

If you want faster replies for testing, temporarily set in .env:
- `REPLY_DELAY_MIN_MINUTES=1`
- `REPLY_DELAY_MAX_MINUTES=2`

## Important

Keep `SENDGRID_FROM_EMAIL=hello@reimaginewealth.org` as is. Do not change it.
The `SENDGRID_REPLY_TO=info@mail.reimaginewealth.org` is already correct.
