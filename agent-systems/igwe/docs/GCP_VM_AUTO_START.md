# Auto-start igwe app on GCP VM (survives reboots)

After a VM reboot (or overnight), the app and dashboard stay down unless the app is started automatically. This guide sets up a **systemd service** so the app starts on boot and restarts if it crashes.

## One-time setup (do this once after you SSH in)

1. **SSH into your VM** (from Google Cloud Console → Compute Engine → VM instances → SSH on your instance).

2. **Go to the app directory:**
   ```bash
   cd ~/Okorie-AI/agent-systems/igwe
   ```
   If your app is somewhere else (e.g. `/home/another_user/...`), `cd` there instead.

3. **Pull the latest code** so you have `scripts/igwe-app.service` and `scripts/install_systemd_service.sh`:
   ```bash
   git pull
   ```
   (If you deploy without git, copy those two files onto the VM into the same paths.)

4. **Run the install script** (it will use your current user and install the service):
   ```bash
   sudo bash scripts/install_systemd_service.sh
   ```

5. **Check that it’s running:**
   ```bash
   sudo systemctl status igwe-app
   ```
   You should see `active (running)`. Then open your dashboard in the browser: `http://YOUR_VM_IP:8000/dashboard/`

After this, whenever the VM reboots (maintenance, crash, etc.), the app will start again automatically. You don’t need to SSH in and run `python main.py` by hand.

## Useful commands

| What you want        | Command |
|----------------------|--------|
| See if app is running | `sudo systemctl status igwe-app` |
| View live logs       | `journalctl -u igwe-app -f` |
| Restart the app      | `sudo systemctl restart igwe-app` |
| Stop the app         | `sudo systemctl stop igwe-app` |
| Start again          | `sudo systemctl start igwe-app` |

## If SSH still doesn’t work after a reboot

If the VM comes back up but you still can’t connect over SSH:

1. In Google Cloud Console go to **Compute Engine → VM instances**.
2. Select your VM and click **Reset**.
3. Wait until status is **Running**, then try **SSH** again (wait 1–2 minutes if it’s slow).
4. Once you’re in, the **igwe-app** service will start on its own if you already installed it. If you haven’t installed it yet, run the steps in “One-time setup” above.

## What the service does

- Runs `python main.py` (or `venv/bin/python main.py` if you have a venv) from your app directory.
- Loads environment variables from your `.env` in that directory.
- Restarts the process if it exits (e.g. crash).
- Starts automatically at boot (after network is up).

If you use **local Redis** on the VM, ensure Redis is also enabled to start on boot (e.g. `sudo systemctl enable redis-server`) so the app can connect after a reboot. If you use an external `REDIS_URL` (e.g. Upstash), no extra step is needed.
