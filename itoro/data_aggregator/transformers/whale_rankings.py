"""
Transformer for whale ranking payloads.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Iterable, List

from core.database import WhaleRankingRecord

logger = logging.getLogger(__name__)


class WhaleRankingTransformer:
    def normalize(self, adapter, raw_rankings: Iterable[dict]) -> List[WhaleRankingRecord]:
        records: List[WhaleRankingRecord] = []
        for payload in raw_rankings:
            try:
                records.append(self._to_record(adapter, payload))
            except Exception:  # pragma: no cover
                logger.exception("Failed to normalize whale ranking payload from adapter=%s", adapter.name)
        return records

    def _to_record(self, adapter, payload: dict) -> WhaleRankingRecord:
        ranking_id = str(payload.get("ranking_id") or payload.get("id") or uuid.uuid4())
        address = payload.get("address") or payload.get("wallet") or ""
        if not address:
            raise ValueError("Whale ranking payload missing address.")

        rank = int(payload.get("rank") or payload.get("position") or 0)
        score = _maybe_float(payload.get("score") or payload.get("ranking_score")) or 0.0

        pnl_30d = _maybe_float(payload.get("pnl_30d") or payload.get("pnl30d"))
        pnl_7d = _maybe_float(payload.get("pnl_7d") or payload.get("pnl7d"))
        pnl_1d = _maybe_float(payload.get("pnl_1d") or payload.get("pnl1d"))
        winrate_7d = _maybe_float(payload.get("winrate_7d") or payload.get("win_rate_7d"))

        last_active = payload.get("last_active") or payload.get("updated_at")
        last_active = _parse_timestamp(last_active)

        is_active = bool(payload.get("is_active", True))
        metadata = dict(payload)

        return WhaleRankingRecord(
            ranking_id=ranking_id,
            ecosystem=adapter.ecosystem,
            address=str(address),
            rank=rank,
            score=score,
            pnl_30d=pnl_30d,
            pnl_7d=pnl_7d,
            pnl_1d=pnl_1d,
            winrate_7d=winrate_7d,
            last_active=last_active,
            is_active=is_active,
            metadata=metadata,
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

