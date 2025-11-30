"""
Adapter for ingesting data from the crypto trading ecosystem.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from core.database import DatabaseConnectionManager, DatabaseConnectionError
from data_aggregator.base import AdapterResult, BaseAdapter

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from psycopg2.extras import RealDictCursor  # type: ignore
except ImportError:  # pragma: no cover - psycopg2 optional
    RealDictCursor = None


class CryptoAdapter(BaseAdapter):
    name = "crypto"
    ecosystem = "crypto"

    def __init__(
        self,
        db_manager: Optional[DatabaseConnectionManager] = None,
        signal_query: str | None = None,
        whale_query: str | None = None,
        strategy_query: str | None = None,
        trades_query: str | None = None,
        batch_size: int = 500,
    ) -> None:
        self.db_manager = db_manager or DatabaseConnectionManager()
        self.signal_query = signal_query or "SELECT * FROM trading_signals ORDER BY timestamp DESC LIMIT %(limit)s"
        self.whale_query = whale_query or "SELECT * FROM whale_rankings ORDER BY last_updated DESC LIMIT %(limit)s"
        self.strategy_query = strategy_query or "SELECT * FROM strategy_metadata ORDER BY timestamp DESC LIMIT %(limit)s"
        self.trades_query = trades_query or "SELECT * FROM executed_trades ORDER BY timestamp DESC LIMIT %(limit)s"
        self.batch_size = batch_size

    def collect(self) -> AdapterResult:
        result = AdapterResult()

        try:
            with self.db_manager.connection(self.ecosystem) as conn:
                cursor = self._get_cursor(conn)
                try:
                    result.raw_signals = self._fetch(cursor, self.signal_query)
                    result.raw_whale_rankings = self._fetch(cursor, self.whale_query)
                    result.raw_strategy_metadata = self._fetch(cursor, self.strategy_query)
                    result.raw_executed_trades = self._fetch(cursor, self.trades_query)
                finally:
                    cursor.close()
        except DatabaseConnectionError:
            logger.exception("Crypto adapter failed to connect to database.")
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Unexpected error in CryptoAdapter.")

        return result

    def _get_cursor(self, connection):
        cursor_factory = RealDictCursor if RealDictCursor is not None else None
        cursor = connection.cursor(cursor_factory=cursor_factory)
        return cursor

    def _fetch(self, cursor, query: str) -> List[Dict[str, Any]]:
        try:
            cursor.execute(query, {"limit": self.batch_size})
            rows = cursor.fetchall()
        except Exception as exc:
            logger.exception("Query failed in CryptoAdapter query=%s error=%s", query, exc)
            return []

        result: List[Dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                result.append(row)
            else:
                # psycopg2 may return tuple; convert using cursor description
                columns = [desc[0] for desc in cursor.description or []]
                record = dict(zip(columns, row))
                result.append(_possibly_parse_json(record))
        return result


def _possibly_parse_json(record: Dict[str, Any]) -> Dict[str, Any]:
    parsed = {}
    for key, value in record.items():
        if isinstance(value, str):
            try:
                parsed[key] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        parsed[key] = value
    return parsed

