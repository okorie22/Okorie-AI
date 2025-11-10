"""
Transformer for strategy metadata payloads.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Iterable, List

from core.database import StrategyMetadataRecord

logger = logging.getLogger(__name__)


class StrategyMetadataTransformer:
    def normalize(self, adapter, raw_items: Iterable[dict]) -> List[StrategyMetadataRecord]:
        records: List[StrategyMetadataRecord] = []
        for payload in raw_items:
            try:
                records.append(self._to_record(adapter, payload))
            except Exception:  # pragma: no cover
                logger.exception("Failed to normalize strategy metadata from adapter=%s", adapter.name)
        return records

    def _to_record(self, adapter, payload: dict) -> StrategyMetadataRecord:
        strategy_id = str(payload.get("strategy_id") or payload.get("id") or uuid.uuid4())
        timestamp = _parse_timestamp(payload.get("timestamp") or payload.get("evaluated_at"))
        name = payload.get("strategy_name") or payload.get("name") or "Unnamed Strategy"
        agent_source = payload.get("agent") or payload.get("source_agent") or adapter.name

        sharpe_ratio = _maybe_float(payload.get("sharpe_ratio") or payload.get("sharpe"))
        win_rate = _maybe_float(payload.get("win_rate") or payload.get("winrate"))
        drawdown = _maybe_float(payload.get("drawdown"))
        var = _maybe_float(payload.get("value_at_risk") or payload.get("var"))

        notes = payload.get("notes") or payload.get("comment")
        metrics = dict(payload)

        return StrategyMetadataRecord(
            strategy_id=strategy_id,
            ecosystem=adapter.ecosystem,
            name=name,
            agent_source=agent_source,
            timestamp=timestamp,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            drawdown=drawdown,
            value_at_risk=var,
            notes=notes,
            metrics=metrics,
        )


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.utcnow()
    text = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.utcnow()


def _maybe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

