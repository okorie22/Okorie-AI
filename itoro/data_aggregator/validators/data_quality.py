"""
Basic data quality validation for normalized records.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Iterable, List

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """Ensures records include required fields and removes null entries."""

    def __init__(self, required_fields: Iterable[str] | None = None) -> None:
        self.required_fields = tuple(required_fields or ())

    def validate(self, records: Iterable) -> List:
        cleaned: List = []
        for record in records:
            if record is None:
                continue
            payload = asdict(record) if is_dataclass(record) else dict(record)
            if self._is_valid(payload):
                cleaned.append(record)
            else:
                logger.debug("Dropped record failing quality checks: %s", payload)
        return cleaned

    def _is_valid(self, payload: dict) -> bool:
        for field in self.required_fields:
            if field not in payload:
                continue
            if payload.get(field) in (None, ""):
                return False
        return True

