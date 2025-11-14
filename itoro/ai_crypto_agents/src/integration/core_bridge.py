"""
Bridge utilities to publish crypto ecosystem data into the shared core layer.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable, Sequence, Optional

import requests
from datetime import datetime

from core.database import UnifiedTradingSignal, WhaleRankingRecord
from core.messaging import get_global_event_bus

logger = logging.getLogger(__name__)

SIGNAL_SERVICE_ENDPOINT = os.getenv("SIGNAL_SERVICE_ENDPOINT")
SIGNAL_SERVICE_API_KEY = os.getenv("SIGNAL_SERVICE_API_KEY")


def publish_trading_signals(signals: Sequence[UnifiedTradingSignal]) -> None:
    """Publish unified trading signals to the global event bus."""
    bus = get_global_event_bus()
    for signal in signals:
        _post_to_signal_service(signal)
        logger.debug("Publishing crypto trading signal %s", signal.signal_id)
        bus.publish_signal(signal, topic="signals")


def publish_whale_rankings(wallets: Iterable) -> None:
    """
    Publish whale rankings derived from WhaleWallet objects produced by
    `whale_agent`. The objects must expose the attributes used below.
    """

    bus = get_global_event_bus()
    for wallet in wallets:
        try:
            record = _wallet_to_record(wallet)
        except Exception:  # pragma: no cover - protective logging
            logger.exception("Failed to convert whale wallet into record")
            continue

        logger.debug("Publishing whale ranking %s", record.ranking_id)
        bus.publish_signal(
            UnifiedTradingSignal(
                signal_id=f"whale:{record.ranking_id}",
                ecosystem="crypto",
                timestamp=record.last_active,
                symbol=record.address,
                action="HOLD",
                signal_type="ANALYTICS",
                confidence=record.score,
                raw_payload=record.to_dict(),
            ),
            topic="whale_rankings",
        )


def _wallet_to_record(wallet) -> WhaleRankingRecord:
    """Convert WhaleWallet dataclass to WhaleRankingRecord."""
    if isinstance(wallet.last_active, str):
        try:
            last_active = datetime.fromisoformat(wallet.last_active)
        except ValueError:
            last_active = datetime.utcnow()
    else:
        last_active = wallet.last_active

    metadata = {
        "twitter_handle": getattr(wallet, "twitter_handle", None),
        "txs_30d": getattr(wallet, "txs_30d", 0),
        "token_active": getattr(wallet, "token_active", 0),
        "is_blue_verified": getattr(wallet, "is_blue_verified", False),
        "avg_holding_period_7d": getattr(wallet, "avg_holding_period_7d", 0.0),
    }

    return WhaleRankingRecord(
        ranking_id=getattr(wallet, "ranking_id", None) or wallet.address,
        ecosystem="crypto",
        address=wallet.address,
        rank=getattr(wallet, "rank", 0),
        score=float(getattr(wallet, "score", 0.0)),
        pnl_30d=_maybe_float(getattr(wallet, "pnl_30d", None)),
        pnl_7d=_maybe_float(getattr(wallet, "pnl_7d", None)),
        pnl_1d=_maybe_float(getattr(wallet, "pnl_1d", None)),
        winrate_7d=_maybe_float(getattr(wallet, "winrate_7d", None)),
        last_active=last_active,
        is_active=getattr(wallet, "is_active", True),
        metadata=metadata,
    )


def _maybe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _post_to_signal_service(signal: UnifiedTradingSignal) -> bool:
    if not SIGNAL_SERVICE_ENDPOINT or not SIGNAL_SERVICE_API_KEY:
        return False

    payload = {
        "ecosystem": signal.ecosystem or "crypto",
        "symbol": signal.symbol,
        "action": signal.action,
        "confidence": signal.confidence or 0.0,
        "price": signal.entry_price or 0.0,
        "volume": signal.volume or 0.0,
        "source_agent": signal.agent_source or "crypto_agent",
        "timestamp": signal.timestamp.isoformat(),
        "signal_id": signal.signal_id,
        "metadata": signal.raw_payload or {},
    }

    try:
        response = requests.post(
            SIGNAL_SERVICE_ENDPOINT,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": SIGNAL_SERVICE_API_KEY,
            },
            timeout=10,
        )
        if response.status_code >= 400:
            logger.error(
                "Failed to forward crypto signal %s to commerce ingest: %s %s",
                signal.signal_id,
                response.status_code,
                response.text[:200],
            )
            return False
        logger.debug("Forwarded crypto signal %s via commerce ingest API", signal.signal_id)
        return True
    except requests.RequestException:
        logger.exception("Error posting crypto signal %s to commerce ingest endpoint", signal.signal_id)
        return False

