"""
Normalize raw signal payloads into UnifiedTradingSignal records.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Iterable, List

from core.database import UnifiedTradingSignal

logger = logging.getLogger(__name__)


class SignalNormalizer:
    def __init__(self, default_confidence: float = 0.5) -> None:
        self.default_confidence = default_confidence

    def normalize(self, adapter, raw_signals: Iterable[dict]) -> List[UnifiedTradingSignal]:
        normalized: List[UnifiedTradingSignal] = []
        for payload in raw_signals:
            try:
                normalized.append(self._to_signal(adapter, payload))
            except Exception:  # pragma: no cover - guard faulty payloads
                logger.exception("Failed to normalize signal payload from adapter=%s", adapter.name)
        return normalized

    def _to_signal(self, adapter, payload: dict) -> UnifiedTradingSignal:
        signal_id = str(payload.get("signal_id") or payload.get("id") or uuid.uuid4())
        timestamp = _parse_timestamp(
            payload.get("timestamp")
            or payload.get("created_at")
            or payload.get("time")
            or payload.get("datetime")
        )

        symbol = payload.get("symbol") or payload.get("pair")
        if not symbol:
            raise ValueError("Signal payload missing symbol field.")

        action = (payload.get("action") or payload.get("side") or "").upper()
        if action not in {"BUY", "SELL", "HOLD"}:
            action = "BUY" if "buy" in str(payload).lower() else "SELL" if "sell" in str(payload).lower() else "HOLD"

        signal_type = (payload.get("type") or payload.get("order_type") or "MARKET").upper()
        confidence = payload.get("confidence")
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = self.default_confidence

        entry_price = _maybe_float(payload.get("price") or payload.get("entry_price"))
        stop_loss = _maybe_float(payload.get("stop_loss") or payload.get("sl"))
        take_profit = _maybe_float(payload.get("take_profit") or payload.get("tp"))
        volume = _maybe_float(payload.get("volume") or payload.get("size"))

        tags = []
        for key in ("tags", "labels", "strategies"):
            value = payload.get(key)
            if isinstance(value, list):
                tags = [str(v) for v in value]
                break
            if isinstance(value, str):
                tags = [part.strip() for part in value.split(",") if part.strip()]
                break

        agent_source = payload.get("agent") or payload.get("source_agent") or adapter.name

        return UnifiedTradingSignal(
            signal_id=signal_id,
            ecosystem=adapter.ecosystem,
            timestamp=timestamp,
            symbol=str(symbol),
            action=action,
            signal_type=signal_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            volume=volume,
            agent_source=agent_source,
            tags=tags,
            raw_payload=dict(payload),
        )


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.utcnow()

    if isinstance(value, (int, float)):
        # assume epoch seconds
        return datetime.utcfromtimestamp(value)

    text = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        logger.debug("Unable to parse timestamp '%s'; using current time.", text)
        return datetime.utcnow()


def _maybe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

