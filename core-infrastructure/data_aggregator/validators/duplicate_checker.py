"""
Duplicate detection for normalized records.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


class DuplicateChecker:
    """
    Removes duplicate records based on a chosen primary key field.
    """

    def __init__(self, key_field: str = "signal_id") -> None:
        self.key_field = key_field
        self._seen = set()

    def validate(self, records: Iterable) -> List:
        unique: List = []
        for record in records:
            payload = asdict(record) if is_dataclass(record) else dict(record)
            unique_key = self._extract_key(payload)
            if unique_key is None:
                unique.append(record)
                continue
            if unique_key in self._seen:
                logger.debug("Skipping duplicate record with key=%s", unique_key)
                continue
            self._seen.add(unique_key)
            unique.append(record)
        return unique

    def _extract_key(self, payload: dict) -> Optional[str]:
        value = payload.get(self.key_field)
        if not value:
            return None
        return str(value)

