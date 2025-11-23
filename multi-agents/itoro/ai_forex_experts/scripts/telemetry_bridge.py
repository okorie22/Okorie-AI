"""
Bridge forex copy-trading signals into shared cloud transports.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

import requests

from core.config import load_database_settings, load_event_bus_settings
from core.database import DatabaseConnectionError, DatabaseConnectionManager, UnifiedTradingSignal
from core.messaging import get_global_event_bus

logger = logging.getLogger(__name__)


class ForexTelemetryBridge:
    """
    Monitors the MT5/MT4 CSV export and forwards unseen signals to shared transports.

    Priority order:
        1. Shared database (forex-specific DSN or core DSN)
        2. Webhook endpoint (if configured)
        3. In-memory event bus (local fallback)
    """

    def __init__(
        self,
        csv_path: str = "../Experts/signals.csv",
        db_manager: Optional[DatabaseConnectionManager] = None,
        http_session: Optional[requests.Session] = None,
    ) -> None:
        self.csv_path = Path(csv_path).resolve()
        self._seen_ids: set[str] = set()

        self.db_manager = db_manager or DatabaseConnectionManager()
        self.http_session = http_session or requests.Session()
        self.event_bus = get_global_event_bus()

        self.database_target = self._select_database_target()
        self.event_settings = load_event_bus_settings()
        self._webhook_enabled = bool(
            self.event_settings.aggregator_endpoint and self.event_settings.webhook_secret
        )
        self.signal_service_endpoint = os.getenv("SIGNAL_SERVICE_ENDPOINT")
        self.signal_service_api_key = os.getenv("SIGNAL_SERVICE_API_KEY")

        if self.database_target:
            logger.info("Forex bridge will persist signals via '%s' database target", self.database_target)
        if self._webhook_enabled:
            logger.info(
                "Forex bridge will forward signals to webhook endpoint %s",
                self.event_settings.aggregator_endpoint,
            )
        if self.signal_service_endpoint:
            logger.info(
                "Forex bridge will stream signals to commerce ingest endpoint %s",
                self.signal_service_endpoint,
            )
        if not self.database_target and not self._webhook_enabled:
            logger.warning("No remote transport configured; falling back to in-memory event bus only.")

    def publish_latest(self) -> int:
        """
        Read the CSV and publish unseen signals. Returns the number published.
        """

        if not self.csv_path.exists():
            logger.debug("Forex telemetry CSV not found at %s", self.csv_path)
            return 0

        new_signals = list(self._read_unseen_rows())
        for signal in new_signals:
            self._dispatch_signal(signal)
        return len(new_signals)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _read_unseen_rows(self) -> Iterable[UnifiedTradingSignal]:
        with self.csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                signal_id = row.get("id") or row.get("signal_id")
                if not signal_id:
                    continue
                if signal_id in self._seen_ids:
                    continue

                self._seen_ids.add(signal_id)
                yield self._row_to_signal(row)

    def _dispatch_signal(self, signal: UnifiedTradingSignal) -> None:
        persisted = False

        push_success = False
        if self.signal_service_endpoint and self.signal_service_api_key:
            push_success = self._post_to_signal_service(signal)
            persisted = persisted or push_success

        if self.database_target and not push_success:
            persisted = self._write_signal_to_db(signal) or persisted

        if self._webhook_enabled:
            persisted = self._post_signal(signal) or persisted

        if not persisted:
            logger.debug("Publishing forex signal %s to local event bus", signal.signal_id)
            self.event_bus.publish_signal(signal, topic="signals")

    def _write_signal_to_db(self, signal: UnifiedTradingSignal) -> bool:
        try:
            with self.db_manager.connection(self.database_target) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO trading_signals (
                        signal_id, ecosystem, timestamp, symbol, action, signal_type,
                        entry_price, stop_loss, take_profit, confidence, volume,
                        agent_source, raw_payload
                    ) VALUES (
                        %(signal_id)s, %(ecosystem)s, %(timestamp)s, %(symbol)s, %(action)s, %(signal_type)s,
                        %(entry_price)s, %(stop_loss)s, %(take_profit)s, %(confidence)s, %(volume)s,
                        %(agent_source)s, %(raw_payload)s
                    )
                    ON CONFLICT (signal_id) DO NOTHING
                    """,
                    {
                        "signal_id": signal.signal_id,
                        "ecosystem": signal.ecosystem,
                        "timestamp": signal.timestamp,
                        "symbol": signal.symbol,
                        "action": signal.action,
                        "signal_type": signal.signal_type,
                        "entry_price": signal.entry_price,
                        "stop_loss": signal.stop_loss,
                        "take_profit": signal.take_profit,
                        "confidence": signal.confidence,
                        "volume": signal.volume,
                        "agent_source": signal.agent_source,
                        "raw_payload": json.dumps(signal.raw_payload or {}),
                    },
                )
                conn.commit()
            logger.debug("Persisted forex signal %s to database", signal.signal_id)
            return True
        except DatabaseConnectionError:
            logger.exception("Database connection not available for forex telemetry bridge.")
            self.database_target = None
            return False
        except Exception:
            logger.exception("Failed to persist forex signal %s to database", signal.signal_id)
            return False

    def _post_signal(self, signal: UnifiedTradingSignal) -> bool:
        payload = signal.to_dict()
        body = json.dumps(payload, default=str).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Signal-Id": signal.signal_id,
            "X-Ecosystem": signal.ecosystem,
        }

        secret = self.event_settings.webhook_secret
        if secret:
            signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-Signature"] = signature

        try:
            response = self.http_session.post(
                self.event_settings.aggregator_endpoint,
                data=body,
                headers=headers,
                timeout=10,
            )
            if response.status_code >= 400:
                logger.error(
                    "Webhook publishing failed for signal %s: %s %s",
                    signal.signal_id,
                    response.status_code,
                    response.text[:200],
                )
                return False
            logger.debug("Forwarded forex signal %s via webhook", signal.signal_id)
            return True
        except requests.RequestException:
            logger.exception("Error posting forex signal %s to webhook", signal.signal_id)
            return False

    def _select_database_target(self) -> Optional[str]:
        db_settings = load_database_settings()
        if db_settings.forex:
            return "forex"
        if db_settings.core:
            return "core"
        return None

    def _post_to_signal_service(self, signal: UnifiedTradingSignal) -> bool:
        if not self.signal_service_endpoint or not self.signal_service_api_key:
            return False

        payload = {
            "ecosystem": signal.ecosystem or "forex",
            "symbol": signal.symbol,
            "action": signal.action,
            "confidence": (signal.confidence or 0.0),
            "price": (signal.entry_price or 0.0),
            "volume": (signal.volume or 0.0),
            "source_agent": signal.agent_source or "forex_ea",
            "timestamp": signal.timestamp.isoformat(),
            "signal_id": signal.signal_id,
            "metadata": signal.raw_payload or {},
        }

        try:
            response = self.http_session.post(
                self.signal_service_endpoint,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.signal_service_api_key,
                },
                timeout=10,
            )
            if response.status_code >= 400:
                logger.error(
                    "Commerce ingest failed for signal %s: %s %s",
                    signal.signal_id,
                    response.status_code,
                    response.text[:200],
                )
                return False
            logger.debug("Forwarded forex signal %s via commerce ingest API", signal.signal_id)
            return True
        except requests.RequestException:
            logger.exception("Error posting forex signal %s to commerce ingest endpoint", signal.signal_id)
            return False

    @staticmethod
    def _row_to_signal(row: dict) -> UnifiedTradingSignal:
        timestamp = datetime.utcnow()
        price = _maybe_float(row.get("price"))
        return UnifiedTradingSignal(
            signal_id=str(row.get("id") or row.get("signal_id")),
            ecosystem="forex",
            timestamp=timestamp,
            symbol=row.get("symbol") or row.get("pair") or "UNKNOWN",
            action=(row.get("side") or row.get("action") or "HOLD").upper(),
            signal_type=(row.get("type") or "MARKET").upper(),
            entry_price=price,
            stop_loss=_maybe_float(row.get("sl")),
            take_profit=_maybe_float(row.get("tp")),
            confidence=_maybe_float(row.get("confidence")),
            volume=_maybe_float(row.get("volume")),
            agent_source="forex_bridge",
            tags=["forex", "copytrade"],
            raw_payload=row,
        )


def publish_batch(rows: Sequence[dict]) -> int:
    """
    Convenience helper used in tests to publish synthetic CSV rows.
    """

    bridge = ForexTelemetryBridge()
    count = 0
    for row in rows:
        bridge._dispatch_signal(ForexTelemetryBridge._row_to_signal(row))
        count += 1
    return count


def _maybe_float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    bridge = ForexTelemetryBridge()
    published = bridge.publish_latest()
    logger.info("Published %s forex signals", published)

