"""
Transformer for executed trade payloads.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Iterable, List

from core.database import ExecutedTradeRecord

logger = logging.getLogger(__name__)


class TradeTransformer:
    def normalize(self, adapter, raw_trades: Iterable[dict]) -> List[ExecutedTradeRecord]:
        records: List[ExecutedTradeRecord] = []
        for payload in raw_trades:
            try:
                records.append(self._to_record(adapter, payload))
            except Exception:  # pragma: no cover
                logger.exception("Failed to normalize executed trade from adapter=%s", adapter.name)
        return records

    def _to_record(self, adapter, payload: dict) -> ExecutedTradeRecord:
        trade_id = str(payload.get("trade_id") or payload.get("id") or uuid.uuid4())
        timestamp = _parse_timestamp(payload.get("timestamp") or payload.get("executed_at"))
        symbol = payload.get("symbol") or payload.get("pair")
        if not symbol:
            raise ValueError("Executed trade payload missing symbol.")

        side = (payload.get("side") or payload.get("action") or "").upper()
        quantity = _maybe_float(payload.get("quantity") or payload.get("amount") or payload.get("size")) or 0.0
        price = _maybe_float(payload.get("price") or payload.get("fill_price")) or 0.0
        fees = _maybe_float(payload.get("fees") or payload.get("fee"))
        pnl = _maybe_float(payload.get("pnl") or payload.get("profit"))
        account_reference = payload.get("account") or payload.get("account_id")

        metadata = dict(payload)

        return ExecutedTradeRecord(
            trade_id=trade_id,
            ecosystem=adapter.ecosystem,
            timestamp=timestamp,
            symbol=str(symbol),
            side=side or "BUY",
            quantity=quantity,
            price=price,
            fees=fees,
            pnl=pnl,
            account_reference=account_reference,
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

