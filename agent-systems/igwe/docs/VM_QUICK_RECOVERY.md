# VM Setup Instructions - Quick Recovery

You're here because your screen session got corrupted. Let's fix it and get Caddy running.

## Step 1: Kill Zombie Screens and Restart Your App

```bash
# SSH into your VM
ssh your-vm

# Kill all screen sessions (nuclear option)
pkill screen

# Wait a moment
sleep 2

# Verify screens are gone
screen -ls
# Should say "No Sockets found"

# Start fresh screen session
screen -S igwe

# Navigate to your app
cd ~/Okorie-AI/agent-systems/igwe

# Pull latest code (includes Reply-To fix + notifications)
git pull origin main

# Start your app
python main.py

# You should see: "Started IUL Appointment Setter (igwe) - FastAPI + Celery + Beat"

# Detach from screen: Press Ctrl+A, then press D
```

Your app is now running in the background!

## Step 2: Run the Automated Caddy Setup Script

**Option A: Download and run the script (easiest)**

```bash
# Download the setup script
cd ~/Okorie-AI/agent-systems/igwe/scripts
git pull origin main

# Make it executable
chmod +x setup_caddy_vm.sh

# Run it
sudo ./setup_caddy_vm.sh
```

The script will:
- Install Caddy (if not installed)
- Open firewall ports
- Create a systemd service
- Start Caddy as reverse proxy
- Obtain Let's Encrypt certificate
- Test the endpoint

**Option B: Manual setup (if script fails)**

```bash
# Install Caddy via snap (simpler than apt)
sudo snap install caddy

# Verify installation
caddy version

# Open firewall ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Start Caddy as reverse proxy (foreground - for testing)
sudo caddy reverse-proxy --from api.reimaginewealth.org --to localhost:8000
```

Press Ctrl+C to stop when you see "certificate obtained successfully"

Then run as background service:

```bash
# Create systemd service
sudo tee /etc/systemd/system/caddy-proxy.service > /dev/null <<EOF
[Unit]
Description=Caddy Reverse Proxy
After=network.target

[Service]
Type=simple
User=root
ExecStart=/snap/bin/caddy reverse-proxy --from api.reimaginewealth.org --to localhost:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl daemon-reload
sudo systemctl enable caddy-proxy
sudo systemctl start caddy-proxy

# Check status
sudo systemctl status caddy-proxy
```

## Step 3: Verify Everything Works

```bash
# Test HTTPS endpoint (should return 405 or 404, not connection error)
curl https://api.reimaginewealth.org/webhooks/sendgrid/inbound

# Check Caddy logs
sudo journalctl -u caddy-proxy -n 50

# Check your app logs
screen -r igwe
# Then Ctrl+A, D to detach
```

## Step 4: Update SendGrid and Test

**You already did this!** ✅ Your screenshot shows:
- URL: `https://api.reimaginewealth.org/webhooks/sendgrid/inbound`

Now test:

```bash
# From your local computer, send email to:
# info@mail.reimaginewealth.org

# Check if it hit your webhook:
curl http://34.45.194.58:8000/messages
# Should show the inbound message
```

## Troubleshooting

### Screen still showing as existing but can't attach?

```bash
# List screens with PIDs
screen -ls

# Force kill specific screen by PID (example: 979.igwe)
kill -9 979

# Or kill all screens
pkill -9 screen
```

### Caddy not obtaining certificate?

Check:
```bash
# View detailed logs
sudo journalctl -u caddy-proxy -f

# Common issues:
# 1. Port 80 not open (needed for ACME challenge)
sudo ufw status

# 2. DNS not propagating yet
nslookup api.reimaginewealth.org
# Should return: 34.45.194.58

# 3. Cloudflare proxy is ON (must be OFF/DNS only)
# Go to Cloudflare → DNS → Make sure cloud icon is GRAY not orange
```

### App not running on port 8000?

```bash
# Check what's listening
sudo netstat -tlnp | grep 8000

# If nothing, start your app
screen -S igwe
cd ~/Okorie-AI/agent-systems/igwe
python main.py
# Ctrl+A, D to detach
```

## Expected Final State

✅ **Your app running in screen session:**
```bash
screen -ls
# Shows: 979.igwe (Detached)
```

✅ **Caddy running as systemd service:**
```bash
sudo systemctl status caddy-proxy
# Shows: active (running)
```

✅ **HTTPS endpoint reachable:**
```bash
curl https://api.reimaginewealth.org
# Returns response (not connection error)
```

✅ **Inbound Parse configured:**
- SendGrid → Inbound Parse → `https://api.reimaginewealth.org/webhooks/sendgrid/inbound`

## Testing End-to-End

Send email to: `info@mail.reimaginewealth.org`

**Expected results:**
1. SendGrid receives it (MX records)
2. SendGrid POSTs to your webhook via Caddy
3. Your app saves it to Postgres
4. You get notification email at `contact@okemokorie.com`
5. Dashboard shows the inbound message

## Useful Commands

```bash
# View app logs (if running in screen)
screen -r igwe
# Ctrl+A, D to detach

# View Caddy logs
sudo journalctl -u caddy-proxy -f

# Restart Caddy
sudo systemctl restart caddy-proxy

# Restart your app
screen -r igwe
# Ctrl+C to stop
# python main.py to restart
# Ctrl+A, D to detach

# Check open ports
sudo netstat -tlnp | grep -E '(80|443|8000)'
```

---

**You got this!** The hard part (DNS, code changes) is done. Just need to get Caddy running now.
