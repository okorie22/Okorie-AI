#!/bin/bash
# Simple Caddy setup script for Google Cloud VM
# Run this on your VM to get HTTPS working with Caddy

set -e  # Exit on error

echo "=========================================="
echo "Caddy Setup for Inbound Parse Webhook"
echo "=========================================="
echo ""

# Step 1: Kill any existing Caddy processes
echo "Step 1: Cleaning up any existing Caddy processes..."
sudo pkill caddy 2>/dev/null || true
sudo systemctl stop caddy 2>/dev/null || true
sleep 2
echo "✅ Cleaned up"
echo ""

# Step 2: Check if Caddy is installed
echo "Step 2: Checking if Caddy is installed..."
if ! command -v caddy &> /dev/null; then
    echo "⚠️  Caddy not found. Installing via snap..."
    sudo snap install caddy
    echo "✅ Caddy installed"
else
    echo "✅ Caddy is already installed"
    caddy version
fi
echo ""

# Step 3: Check if port 8000 is listening (your FastAPI app)
echo "Step 3: Checking if your app is running on port 8000..."
if ! sudo netstat -tlnp | grep -q ":8000"; then
    echo "❌ WARNING: Nothing is listening on port 8000!"
    echo "   Make sure your FastAPI app (main.py) is running first."
    echo "   Run: screen -S igwe"
    echo "   Then: cd ~/Okorie-AI/agent-systems/igwe && python main.py"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ App is running on port 8000"
fi
echo ""

# Step 4: Open firewall ports
echo "Step 4: Opening firewall ports (80 and 443)..."
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true
echo "✅ Firewall ports opened"
echo ""

# Step 5: Start Caddy in the background
echo "Step 5: Starting Caddy reverse proxy..."
echo "   Domain: api.reimaginewealth.org"
echo "   Proxying to: localhost:8000"
echo ""

# Create a systemd service for Caddy (persistent across reboots)
sudo tee /etc/systemd/system/caddy-reverse-proxy.service > /dev/null <<EOF
[Unit]
Description=Caddy Reverse Proxy for Igwe
After=network.target

[Service]
Type=simple
User=root
ExecStart=/snap/bin/caddy reverse-proxy --from api.reimaginewealth.org --to localhost:8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable caddy-reverse-proxy
sudo systemctl start caddy-reverse-proxy

echo "✅ Caddy is starting..."
echo ""

# Wait for Caddy to start
echo "Waiting for Caddy to obtain Let's Encrypt certificate (this may take 30-60 seconds)..."
sleep 10

# Step 6: Check Caddy status
echo ""
echo "Step 6: Checking Caddy status..."
if sudo systemctl is-active --quiet caddy-reverse-proxy; then
    echo "✅ Caddy is running!"
else
    echo "❌ Caddy failed to start. Check logs:"
    echo "   sudo journalctl -u caddy-reverse-proxy -n 50"
    exit 1
fi
echo ""

# Step 7: Test the endpoint
echo "Step 7: Testing HTTPS endpoint..."
echo "   Testing: https://api.reimaginewealth.org"
echo ""

sleep 5  # Give Let's Encrypt time to complete

if curl -s -o /dev/null -w "%{http_code}" https://api.reimaginewealth.org/webhooks/sendgrid/inbound | grep -q "405\|200\|404"; then
    echo "✅ HTTPS endpoint is reachable!"
    echo ""
    echo "=========================================="
    echo "✅ SUCCESS! Caddy is running!"
    echo "=========================================="
    echo ""
    echo "Your stable webhook URL:"
    echo "   https://api.reimaginewealth.org/webhooks/sendgrid/inbound"
    echo ""
    echo "Next steps:"
    echo "1. Update SendGrid Inbound Parse URL to the above URL"
    echo "2. Test by sending email to: info@mail.reimaginewealth.org"
    echo "3. Check your dashboard: http://$(curl -s ifconfig.me):8000/messages"
    echo ""
    echo "To view Caddy logs:"
    echo "   sudo journalctl -u caddy-reverse-proxy -f"
    echo ""
    echo "To restart Caddy:"
    echo "   sudo systemctl restart caddy-reverse-proxy"
    echo ""
else
    echo "⚠️  HTTPS endpoint not responding yet."
    echo "   This is normal - Let's Encrypt cert generation can take a minute."
    echo ""
    echo "Check logs:"
    echo "   sudo journalctl -u caddy-reverse-proxy -f"
    echo ""
    echo "Wait a minute and test manually:"
    echo "   curl https://api.reimaginewealth.org/webhooks/sendgrid/inbound"
fi

echo ""
echo "Caddy is now running as a systemd service."
echo "It will auto-start on reboot."
echo ""
