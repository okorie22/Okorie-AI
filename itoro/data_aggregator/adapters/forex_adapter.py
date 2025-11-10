"""
Adapter for the forex ecosystem which sources signals from CSV/Telegram.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from data_aggregator.base import AdapterResult, BaseAdapter

logger = logging.getLogger(__name__)


class ForexAdapter(BaseAdapter):
    name = "forex"
    ecosystem = "forex"

    def __init__(
        self,
        csv_path: str | Path = "ai_forex_experts/Experts/signals.csv",
        telegram_fetcher: Optional[callable] = None,
        id_fields: Sequence[str] = ("id",),
    ) -> None:
        self.csv_path = Path(csv_path)
        self.telegram_fetcher = telegram_fetcher
        self.id_fields = tuple(id_fields)
        self._seen_ids: Set[str] = set()

    def collect(self) -> AdapterResult:
        result = AdapterResult()

        csv_rows = self._read_csv()
        result.raw_signals.extend(csv_rows)

        if self.telegram_fetcher:
            telegram_rows = self._fetch_telegram()
            result.raw_signals.extend(telegram_rows)

        return result

    # ------------------------------------------------------------------
    def _read_csv(self) -> List[Dict[str, Any]]:
        if not self.csv_path.exists():
            logger.debug("Forex signals CSV not found at %s", self.csv_path)
            return []

        rows: List[Dict[str, Any]] = []
        try:
            with self.csv_path.open("r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for raw_row in reader:
                    signal_id = self._extract_id(raw_row)
                    if signal_id in self._seen_ids:
                        continue
                    raw_row["source"] = "csv"
                    raw_row["signal_id"] = signal_id
                    rows.append(raw_row)
                    self._seen_ids.add(signal_id)
        except Exception:  # pragma: no cover
            logger.exception("Failed to read forex signals CSV at %s", self.csv_path)
        return rows

    def _fetch_telegram(self) -> List[Dict[str, Any]]:
        try:
            messages = self.telegram_fetcher() or []
        except Exception:  # pragma: no cover
            logger.exception("Telegram fetcher failed for forex adapter.")
            return []

        parsed = []
        for message in messages:
            signal_id = self._extract_id(message)
            if signal_id in self._seen_ids:
                continue
            message["source"] = "telegram"
            message["signal_id"] = signal_id
            parsed.append(message)
            self._seen_ids.add(signal_id)
        return parsed

    def _extract_id(self, payload: Dict[str, Any]) -> str:
        for field in self.id_fields:
            value = payload.get(field)
            if value:
                return str(value)
        # Fall back to hash of payload
        return str(hash(tuple(sorted(payload.items()))))

