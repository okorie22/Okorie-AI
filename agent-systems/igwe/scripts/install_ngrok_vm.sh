#!/bin/bash
# Install ngrok on the VM (Ubuntu/Debian) so you can expose port 8000 over HTTPS for SendGrid.
# Run on the VM: bash install_ngrok_vm.sh
# Then: ngrok config add-authtoken YOUR_TOKEN
# Then: ngrok http 8000

set -e

if command -v ngrok &>/dev/null; then
  echo "ngrok is already installed: $(ngrok version 2>/dev/null || ngrok --version 2>/dev/null)"
  echo "Next: ngrok config add-authtoken YOUR_TOKEN"
  echo "Then: ngrok http 8000"
  exit 0
fi

echo "Installing ngrok..."
# Official Linux amd64 binary (no curl needed; wget is on Ubuntu by default)
wget -q "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz" -O /tmp/ngrok.tgz
sudo tar -xzf /tmp/ngrok.tgz -C /usr/local/bin
rm -f /tmp/ngrok.tgz

if command -v ngrok &>/dev/null; then
  echo "Installed: $(ngrok version 2>/dev/null || ngrok --version 2>/dev/null)"
  echo ""
  echo "Next steps:"
  echo "  1. ngrok config add-authtoken YOUR_AUTH_TOKEN"
  echo "  2. Start igwe (python main.py) if not already running"
  echo "  3. ngrok http 8000"
  echo "  4. In SendGrid Event Webhook, set Post URL to the https://... URL ngrok shows"
else
  echo "Install failed: ngrok not in PATH"
  exit 1
fi
