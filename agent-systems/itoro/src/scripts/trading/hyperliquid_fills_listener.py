"""
Hyperliquid WebSocket listener: subscribe to userFills for tracked addresses,
parse fill events, and POST to copybot at /webhook/hyperliquid.
Run where the copybot runs (same machine). No second Render server.
Run: python -m src.scripts.trading.hyperliquid_fills_listener
"""

import json
import os
import signal
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    import requests
except ImportError:
    requests = None
try:
    import websockets
except ImportError:
    websockets = None

try:
    from src.config import (
        HYPERLIQUID_WALLETS_TO_TRACK,
        HYPERLIQUID_COPY_TOP_N,
        WHALE_DATA_DIR,
        WHALE_RANKED_FILE,
        COPYBOT_HYPERLIQUID_WEBHOOK_URL,
        HYPERLIQUID_WEBSOCKET_URL,
    )
except ImportError:
    HYPERLIQUID_WALLETS_TO_TRACK = []
    HYPERLIQUID_COPY_TOP_N = 10
    WHALE_DATA_DIR = os.path.join("src", "data", "whale_dump")
    WHALE_RANKED_FILE = "ranked_whales.json"
    COPYBOT_HYPERLIQUID_WEBHOOK_URL = "http://localhost:8080/webhook/hyperliquid"
    HYPERLIQUID_WEBSOCKET_URL = "wss://api.hyperliquid.xyz/ws"

_shutdown = False


def _get_tracked_addresses():
    """Tracked Hyperliquid addresses: from config or top N from ranked_whales.json."""
    if HYPERLIQUID_WALLETS_TO_TRACK:
        return list(HYPERLIQUID_WALLETS_TO_TRACK)
    ranked_path = Path(WHALE_DATA_DIR) / WHALE_RANKED_FILE
    if not ranked_path.exists():
        return []
    try:
        with open(ranked_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        addresses = list(data.keys())
        return addresses[:HYPERLIQUID_COPY_TOP_N]
    except Exception:
        return []


def _fill_to_event(user: str, fill: dict) -> dict:
    """Convert WsFill to canonical event: wallet, symbol, side, size_usd."""
    coin = fill.get("coin") or ""
    if not coin or (isinstance(coin, str) and coin.startswith("@")):
        return None
    side_str = (fill.get("side") or "B").upper()
    side = "buy" if side_str == "A" else "sell"
    try:
        px = float(fill.get("px", 0))
        sz = float(fill.get("sz", 0))
        size_usd = px * sz
    except (TypeError, ValueError):
        size_usd = 0
    return {
        "wallet": user,
        "symbol": coin,
        "side": side,
        "size_usd": size_usd,
    }


def _post_to_copybot(events: list):
    """POST events to copybot with retry/backoff."""
    if not events or not requests:
        return False
    payload = {"source": "hyperliquid", "events": events}
    for attempt in range(3):
        try:
            r = requests.post(
                COPYBOT_HYPERLIQUID_WEBHOOK_URL,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            if r.status_code == 200:
                return True
            time.sleep(0.5 * (attempt + 1))
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return False


async def _run_listener():
    global _shutdown
    if not websockets:
        print("websockets not installed. pip install websockets")
        return
    addresses = _get_tracked_addresses()
    if not addresses:
        print("No Hyperliquid addresses to track. Set HYPERLIQUID_WALLETS_TO_TRACK or ensure ranked_whales.json exists.")
        return
    print(f"Tracking {len(addresses)} addresses: {[a[:10]+'...' for a in addresses]}")
    print(f"POST target: {COPYBOT_HYPERLIQUID_WEBHOOK_URL}")
    print("Connecting to", HYPERLIQUID_WEBSOCKET_URL)

    while not _shutdown:
        try:
            async with websockets.connect(
                HYPERLIQUID_WEBSOCKET_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                for addr in addresses:
                    sub = {"method": "subscribe", "subscription": {"type": "userFills", "user": addr}}
                    await ws.send(json.dumps(sub))
                print("Subscribed to userFills")

                while not _shutdown:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(msg)
                    channel = data.get("channel")
                    if channel == "subscriptionResponse":
                        continue
                    if channel != "userFills":
                        continue
                    payload_data = data.get("data", {})
                    if payload_data.get("isSnapshot"):
                        continue
                    user = payload_data.get("user", "")
                    fills = payload_data.get("fills", [])
                    events = []
                    for f in fills:
                        ev = _fill_to_event(user, f)
                        if ev:
                            events.append(ev)
                    if events:
                        _post_to_copybot(events)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print("WebSocket error:", e)
            if not _shutdown:
                time.sleep(5)


def main():
    global _shutdown

    def sig_handler(*_):
        global _shutdown
        _shutdown = True

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    asyncio.run(_run_listener())
    return 0


if __name__ == "__main__":
    sys.exit(main())
