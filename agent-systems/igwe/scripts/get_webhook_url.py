"""
Print your SendGrid webhook URL. Run this after ngrok is already running (ngrok http 8000).
Paste the printed URL into SendGrid Inbound Parse → Destination URL.
"""
import urllib.request
import json
import sys

def main():
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
        with urllib.request.urlopen(req, timeout=5) as f:
            data = json.loads(f.read().decode())
    except Exception as e:
        print("Could not reach ngrok. Is ngrok running? Run: ngrok http 8000", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    tunnels = data.get("tunnels") or []
    for t in tunnels:
        if t.get("proto") == "https":
            public_url = t.get("public_url", "").rstrip("/")
            webhook_url = f"{public_url}/webhooks/sendgrid/inbound"
            print(webhook_url)
            return
    print("No HTTPS tunnel found. Run: ngrok http 8000", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
