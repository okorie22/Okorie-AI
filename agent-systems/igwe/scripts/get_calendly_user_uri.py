"""
Fetch Calendly current user via API and print the user URI and scheduling URL.
Use this to set CALENDLY_USER_URI in .env for appointment polling.

  python scripts/get_calendly_user_uri.py

Requires CALENDLY_API_KEY in .env (or environment).
"""
import os
import sys
from pathlib import Path

# Load .env from igwe dir and parents (workspace root often holds .env)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    for base in [PROJECT_ROOT] + list(PROJECT_ROOT.parents)[:3]:
        env_file = base / ".env"
        if env_file.exists():
            load_dotenv(env_file)
except ImportError:
    pass

import requests

BASE_URL = "https://api.calendly.com"


def main():
    api_key = os.getenv("CALENDLY_API_KEY")
    if not api_key:
        print("CALENDLY_API_KEY not set. Add it to .env or set the env var.")
        return 1

    url = f"{BASE_URL}/users/me"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                print("Response:", e.response.json())
            except Exception:
                print("Response text:", e.response.text[:500])
        return 1

    data = r.json()
    resource = data.get("resource") or data
    user_uri = resource.get("uri")
    scheduling_url = resource.get("scheduling_url")
    name = (resource.get("name") or "").strip() or None

    print("")
    print("Calendly current user (use these in .env for appointment management):")
    print("-" * 60)
    if user_uri:
        print("CALENDLY_USER_URI=" + user_uri)
    else:
        print("(uri not found in response)")
    if scheduling_url:
        print("Scheduling URL: " + scheduling_url)
    if name:
        print("Name: " + name)
    print("-" * 60)
    print("")
    print("Add CALENDLY_USER_URI to your .env to run appointment polling.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
