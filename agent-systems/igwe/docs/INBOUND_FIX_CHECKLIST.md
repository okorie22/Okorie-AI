# Inbound Email Fix - Complete Checklist

This checklist ensures your inbound emails (replies from Tina, Ron, etc.) hit your system instead of bypassing to Zoho.

## ✅ What We Just Fixed in Code

1. **Reply-To Header**: Changed from raw string to `Email()` object in `src/channels/email.py`
   - Now prospects will reply to `info@mail.reimaginewealth.org` (SendGrid Parse host)
   - Not to `hello@reimaginewealth.org` (Zoho)

2. **Inbound Notifications**: Added alerts when ANY reply comes in
   - You'll get an email notification immediately
   - Not just for escalations

## 🧪 Step 1: Test Current Setup (ngrok)

**Do this now to verify your webhook is reachable:**

1. Send email from your Gmail to: `info@mail.reimaginewealth.org`
2. Subject: "Test inbound"
3. Body: "Testing webhook"

**Expected results:**
- VM logs show: `"Inbound email from: your-email@gmail.com"`
- You receive notification email
- Message appears in dashboard under "Unknown Inbound" lead

**If test fails:**
- Check ngrok is running: `ngrok http 8000`
- Check VM app is running
- Check SendGrid Inbound Parse URL matches ngrok HTTPS URL

## 🌐 Step 2: Set Up Stable HTTPS URL (Production)

**Why:** ngrok URLs change every time you restart. Production needs a stable URL.

**What you're creating:** `https://api.reimaginewealth.org` → Your VM

**Follow these steps** (detailed guide: `STABLE_HTTPS_SETUP.md`):

### Quick Steps:
1. Get VM External IP from Google Cloud Console
2. Add DNS A record: `api.reimaginewealth.org` → [VM IP]
3. SSH to VM and install Caddy:
   ```bash
   sudo apt update && sudo apt install caddy
   ```
4. Configure Caddy (reverse proxy to port 8000)
5. Open firewall ports 80 and 443
6. Caddy auto-generates Let's Encrypt cert (free!)
7. Update SendGrid Inbound Parse URL to: `https://api.reimaginewealth.org/webhooks/sendgrid/inbound`

**Cost:** $0 (Let's Encrypt is free)

## 🔄 Step 3: Deploy Code Changes to VM

Once you've done steps 1 & 2, deploy the fixed code:

**Option A: Git pull (if you use git on VM):**
```bash
# On VM:
cd ~/Okorie-AI/agent-systems/igwe
git pull origin main
sudo systemctl restart igwe  # or however you restart your app
```

**Option B: Manual copy:**
1. Copy `src/channels/email.py` to VM
2. Copy `src/api/main.py` to VM
3. Copy `src/channels/notifications.py` to VM
4. Restart your app on VM

## ✅ Step 4: Final End-to-End Test

**After deploying code + stable URL:**

1. Send a test email from your system to a real prospect (or yourself)
2. Reply to that email
3. Your reply should go to `info@mail.reimaginewealth.org` (check Reply-To header)
4. Verify:
   - VM logs show inbound received
   - You get notification email
   - Message appears in dashboard
   - AI analyzes and responds (or escalates)

## 🎯 What Success Looks Like

**Before fix:**
- Prospect replies → goes to `hello@reimaginewealth.org` → Cloudflare/Zoho → You see in Zoho inbox
- Your system never sees the reply ❌

**After fix:**
- Prospect replies → goes to `info@mail.reimaginewealth.org` → SendGrid Parse → Your webhook → Postgres ✅
- You get notification email ✅
- AI handles response ✅
- You can still see it in dashboard ✅

## 🚨 Important Notes

### About Cloudflare Email Routing
- **Keep it enabled** for `hello@reimaginewealth.org` (your real inbox)
- It's not "competing" with SendGrid
- They handle different domains:
  - Cloudflare: `*@reimaginewealth.org` (your inbox)
  - SendGrid Parse: `*@mail.reimaginewealth.org` (your agent)

### About Reply-To
- Your emails will show:
  - **From:** `hello@reimaginewealth.org` (your sending address)
  - **Reply-To:** `info@mail.reimaginewealth.org` (where replies go)
- Most email clients respect Reply-To and use it for the reply button
- This is the standard way to route replies to a different system

### About BCC (Optional)
If you want a copy of outbound emails in your Zoho inbox:
- Add `message.bcc = Email("your-zoho-email@reimaginewealth.org")` in the send code
- This gives you mailbox visibility of what you sent
- But inbounds still go through Parse (not Zoho)

## 📝 Environment Variables Check

Make sure these are set in your `.env`:

```bash
# SendGrid
SENDGRID_API_KEY=SG.xxx...
SENDGRID_FROM_EMAIL=hello@reimaginewealth.org
SENDGRID_FROM_NAME=Okem Okorie
SENDGRID_REPLY_TO=info@mail.reimaginewealth.org  # CRITICAL - must match Parse host

# Notifications
HUMAN_NOTIFICATION_EMAIL=your-email@gmail.com  # Where to receive alerts
```

## 🔍 Debugging Tips

### Check if Reply-To is being set:
```bash
# SSH to VM, check app logs:
tail -f ~/Okorie-AI/agent-systems/igwe/logs/app.log
```

### Check SendGrid Parse deliveries:
- SendGrid Dashboard → Inbound Parse → Activity
- Shows successful/failed webhook POSTs

### Check your messages dashboard:
- Go to: `http://[VM-IP]:8000/messages`
- Should show inbound messages with direction=INBOUND

### If ngrok session expires:
```bash
# Restart ngrok
ngrok http 8000

# Update SendGrid Inbound Parse URL
# (This is why you want the stable URL!)
```

## ✨ Next Steps After This Works

Once inbounds are flowing correctly:

1. **Monitor the AI quality**: Check if auto-replies are appropriate
2. **Adjust confidence threshold**: If too many escalations, lower `REPLY_CONFIDENCE_THRESHOLD`
3. **Refine reply templates**: Update reply agent prompts in `src/conversation/reply_agent.py`
4. **Add BCC if desired**: Optional visibility of outbound emails in your inbox

## 📞 Support

If you get stuck:
- Check logs: `~/Okorie-AI/agent-systems/igwe/logs/`
- Check Caddy logs: `sudo journalctl -u caddy -n 50`
- Check DNS: `nslookup api.reimaginewealth.org`
- Check ports: `sudo netstat -tlnp | grep -E '(8000|443)'`

---

**Remember:** The goal is to make sure Reply-To points to your Parse subdomain (`mail.reimaginewealth.org`), and that subdomain's MX records point to SendGrid. Everything else flows from that.
