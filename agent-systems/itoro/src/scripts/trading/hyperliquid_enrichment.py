"""
Hyperliquid 7d enrichment: winrate_7d and avg_holding_period_7d from user_fills.
Uses public Info API (no private key). For use in whale agent futures path and standalone script.
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    requests = None

# Defaults when enrichment fails or no data
DEFAULT_WINRATE_7D = 0.5
DEFAULT_AVG_HOLDING_PERIOD_7D = 86400.0  # 1 day in seconds

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"


def _fetch_user_fills_by_time(address: str, start_time_ms: int, end_time_ms: int) -> list:
    """Fetch user fills from Hyperliquid Info API (REST). Returns list of fill dicts."""
    if not requests:
        return []
    try:
        payload = {
            "type": "userFillsByTime",
            "user": address,
            "startTime": start_time_ms,
            "endTime": end_time_ms,
        }
        resp = requests.post(HYPERLIQUID_INFO_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _is_open_dir(dir_str: str) -> bool:
    if not dir_str:
        return False
    d = (dir_str or "").strip().lower()
    return d.startswith("open long") or d.startswith("open short")


def _is_close_dir(dir_str: str) -> bool:
    if not dir_str:
        return False
    d = (dir_str or "").strip().lower()
    return d.startswith("close long") or d.startswith("close short")


def _side_from_dir(dir_str: str) -> Optional[str]:
    if not dir_str:
        return None
    d = (dir_str or "").strip().lower()
    if "long" in d:
        return "long"
    if "short" in d:
        return "short"
    return None


def _side_from_fill(f: dict) -> Optional[str]:
    """Infer side from fill: dir (Open/Close Long/Short) or side (A=long, B=short)."""
    side = _side_from_dir(f.get("dir") or "")
    if side:
        return side
    s = (f.get("side") or "").strip().upper()
    if s == "A":
        return "long"
    if s == "B":
        return "short"
    return None


def enrich_wallet_7d_from_hyperliquid(
    address: str,
    info_instance: Any = None,
) -> Dict[str, float]:
    """
    Compute winrate_7d and avg_holding_period_7d from Hyperliquid user_fills (last 7 days).

    Args:
        address: EVM address (0x...).
        info_instance: Optional Hyperliquid Info(api_url) instance. If None, uses REST.

    Returns:
        {"winrate_7d": float, "avg_holding_period_7d": float}. Uses defaults on failure or no data.
    """
    out = {
        "winrate_7d": DEFAULT_WINRATE_7D,
        "avg_holding_period_7d": DEFAULT_AVG_HOLDING_PERIOD_7D,
    }
    if not address or not str(address).startswith("0x"):
        return out

    now = datetime.utcnow()
    start = now - timedelta(days=7)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    fills = []
    if info_instance is not None and hasattr(info_instance, "user_fills_by_time"):
        try:
            fills = info_instance.user_fills_by_time(address, start_ms, end_ms) or []
        except Exception:
            fills = []
    if not fills and requests:
        fills = _fetch_user_fills_by_time(address, start_ms, end_ms)

    if not fills:
        return out

    wins = 0
    closes = 0
    hold_times_sec: list = []

    # Sort by time ascending so we can find open-before-close pairs
    sorted_fills = sorted(fills, key=lambda f: int(f.get("time", 0)))

    for i, f in enumerate(sorted_fills):
        coin = f.get("coin") or ""
        if not coin or (isinstance(coin, str) and coin.startswith("@")):
            continue
        dir_str = f.get("dir") or ""
        ts_ms = int(f.get("time", 0))
        closed_pnl_str = f.get("closedPnl")
        side = _side_from_fill(f)
        key = (coin, side) if side else None

        # Winrate: count closes with closedPnl
        if closed_pnl_str is not None and str(closed_pnl_str).strip() != "":
            try:
                pnl = float(closed_pnl_str)
                closes += 1
                if pnl > 0:
                    wins += 1
            except (ValueError, TypeError):
                pass

            # Avg hold time: find matching open fill (same coin, same side) before this close
            if key:
                open_ts_ms = None
                for j in range(i - 1, -1, -1):
                    prev = sorted_fills[j]
                    if (prev.get("coin") or "") != coin:
                        continue
                    if not _is_open_dir(prev.get("dir") or ""):
                        continue
                    prev_side = _side_from_fill(prev)
                    if prev_side == side:
                        open_ts_ms = int(prev.get("time", 0))
                        break
                if open_ts_ms is not None and ts_ms > open_ts_ms:
                    hold_times_sec.append((ts_ms - open_ts_ms) / 1000.0)

    if closes > 0:
        out["winrate_7d"] = wins / closes
    if hold_times_sec:
        out["avg_holding_period_7d"] = sum(hold_times_sec) / len(hold_times_sec)

    return out
