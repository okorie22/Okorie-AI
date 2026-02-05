#!/bin/bash
# Install igwe app as a systemd service so it starts on boot and restarts on crash.
# Run this ON THE GCP VM after SSH'ing in. Requires sudo.
#
# Usage:
#   cd ~/Okorie-AI/agent-systems/igwe   # or wherever your app lives
#   bash scripts/install_systemd_service.sh

set -e
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_AS_USER="${SUDO_USER:-$(whoami)}"

if [ -z "$RUN_AS_USER" ] || [ "$RUN_AS_USER" = "root" ]; then
  echo "Run this script as a normal user with sudo: sudo bash scripts/install_systemd_service.sh"
  echo "Or run from SSH as your user and it will use your username for the service."
  exit 1
fi

if [ ! -f "$APP_DIR/main.py" ]; then
  echo "Error: main.py not found in $APP_DIR"
  exit 1
fi

if [ -x "$APP_DIR/venv/bin/python" ]; then
  PYTHON_BIN="$APP_DIR/venv/bin/python"
else
  PYTHON_BIN="/usr/bin/python3"
fi

SERVICE_FILE="$APP_DIR/scripts/igwe-app.service"
DEST="/etc/systemd/system/igwe-app.service"

echo "App directory: $APP_DIR"
echo "Run as user:   $RUN_AS_USER"
echo "Python:        $PYTHON_BIN"
echo ""

# Replace placeholders and install
sed -e "s|APP_DIR|$APP_DIR|g" \
    -e "s|APP_USER|$RUN_AS_USER|g" \
    -e "s|PYTHON_BIN|$PYTHON_BIN|g" \
    "$SERVICE_FILE" | sudo tee "$DEST" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable igwe-app
sudo systemctl start igwe-app

echo ""
echo "Done. Service igwe-app is enabled and started."
echo "  status:  sudo systemctl status igwe-app"
echo "  logs:    journalctl -u igwe-app -f"
echo "  stop:    sudo systemctl stop igwe-app"
echo "  restart: sudo systemctl restart igwe-app"
echo ""
sudo systemctl status igwe-app --no-pager || true
