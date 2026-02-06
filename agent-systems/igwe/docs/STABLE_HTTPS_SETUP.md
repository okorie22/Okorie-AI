# Stable HTTPS URL Setup for Google Cloud VM

This guide sets up a permanent HTTPS endpoint for your SendGrid webhooks using your existing domain and Caddy (free, auto-renewing Let's Encrypt certificates).

## Prerequisites
- ✅ You own `reimaginewealth.org`
- ✅ You have a Google Cloud VM running
- ✅ Your FastAPI app runs on port 8000

## Step 1: Get Your VM's External IP

1. Go to Google Cloud Console: https://console.cloud.google.com/compute/instances
2. Find your VM instance (looks like `igwe-instance-20260201-071107`)
3. Copy the **External IP** (should be something like `34.45.194.58`)

## Step 2: Add DNS A Record

You need to point a subdomain to your VM. Choose one:
- `api.reimaginewealth.org` (recommended)
- `webhooks.reimaginewealth.org`

### If your DNS is managed by Cloudflare:
1. Go to Cloudflare Dashboard → DNS → Records
2. Click "Add record"
3. Type: `A`
4. Name: `api` (or `webhooks`)
5. IPv4 address: [Your VM External IP from Step 1]
6. **IMPORTANT**: Set Proxy status to "DNS only" (gray cloud, not orange)
7. TTL: Auto
8. Click Save

### If your DNS is managed by Namecheap:
1. Go to Namecheap Dashboard → Domain List → Manage
2. Click "Advanced DNS"
3. Click "Add New Record"
4. Type: `A Record`
5. Host: `api` (or `webhooks`)
6. Value: [Your VM External IP from Step 1]
7. TTL: Automatic
8. Click Save

**Wait 5-10 minutes for DNS to propagate.**

Verify DNS is working:
```bash
# From your local computer:
nslookup api.reimaginewealth.org
```
Should return your VM's IP.

## Step 3: Install Caddy on Your VM

SSH into your VM, then run these commands:

```bash
# Install Caddy
sudo apt update
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

Verify Caddy is installed:
```bash
caddy version
```

## Step 4: Configure Caddy as Reverse Proxy

Create a Caddyfile:

```bash
sudo nano /etc/caddy/Caddyfile
```

**Replace the entire contents** with this (replace `api.reimaginewealth.org` with your chosen subdomain):

```
api.reimaginewealth.org {
    reverse_proxy localhost:8000
    
    # Optional: logging
    log {
        output file /var/log/caddy/access.log
    }
}
```

Save and exit (Ctrl+X, Y, Enter).

## Step 5: Open Firewall Ports

Google Cloud needs to allow HTTPS traffic:

```bash
# Allow HTTPS (port 443)
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp  # Needed for Let's Encrypt validation

# If ufw is not enabled yet:
sudo ufw enable
```

**Also verify in Google Cloud Console:**
1. Go to VPC Network → Firewall
2. Make sure there's a rule allowing ingress on ports 80 and 443
3. If not, create one: Source IP ranges: `0.0.0.0/0`, Protocols: tcp:80,443

## Step 6: Start Caddy

```bash
# Reload Caddy configuration
sudo systemctl reload caddy

# Check Caddy status
sudo systemctl status caddy

# View Caddy logs (to see Let's Encrypt cert generation)
sudo journalctl -u caddy -f
```

**Caddy will automatically:**
- Obtain a Let's Encrypt certificate for your domain
- Set up HTTPS on port 443
- Redirect HTTP → HTTPS
- Auto-renew certificates before they expire

## Step 7: Verify HTTPS Works

From your local computer, test the endpoint:

```bash
# Should return 405 Method Not Allowed (expected - SendGrid needs POST)
curl https://api.reimaginewealth.org/webhooks/sendgrid/inbound
```

If you see an SSL certificate error, wait a minute and try again (Let's Encrypt cert generation can take 30-60 seconds).

## Step 8: Update SendGrid Inbound Parse

1. Go to SendGrid: https://app.sendgrid.com/settings/parse
2. Click the settings icon next to `mail.reimaginewealth.org`
3. Change the URL to: `https://api.reimaginewealth.org/webhooks/sendgrid/inbound`
4. Click Update

## Step 9: Test End-to-End

Send an email to `info@mail.reimaginewealth.org` from Gmail.

You should:
- See the webhook hit in your VM logs
- Receive a notification email
- See the message in your dashboard

## Troubleshooting

### DNS not resolving
```bash
# Check DNS
nslookup api.reimaginewealth.org
```
If it doesn't return your VM IP, wait longer or check your DNS settings.

### Caddy errors
```bash
# Check Caddy logs
sudo journalctl -u caddy -n 50 --no-pager

# Check if Caddy is listening
sudo netstat -tlnp | grep caddy
```

### Let's Encrypt cert issues
Make sure:
- Port 80 is open (needed for ACME challenge)
- Port 443 is open
- DNS points to your VM
- Cloudflare proxy is OFF (DNS only mode)

### App not responding
Make sure your FastAPI app is still running:
```bash
# Check if app is running on port 8000
sudo netstat -tlnp | grep 8000
```

## Summary

Your stable HTTPS URL: `https://api.reimaginewealth.org/webhooks/sendgrid/inbound`

- ✅ Free (Let's Encrypt)
- ✅ Auto-renewing certificates
- ✅ No ngrok dependency
- ✅ Production-ready

## Maintenance

Caddy handles everything automatically. You only need to:
- Keep Caddy service running (`sudo systemctl enable caddy` ensures it starts on boot)
- Keep your FastAPI app running on port 8000

That's it! Your inbound parse webhook is now production-ready.
