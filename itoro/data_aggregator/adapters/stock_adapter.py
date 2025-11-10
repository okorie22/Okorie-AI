"""
Placeholder adapter for the stock trading ecosystem.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.database import DatabaseConnectionManager, DatabaseConnectionError
from data_aggregator.base import AdapterResult, BaseAdapter

logger = logging.getLogger(__name__)


class StockAdapter(BaseAdapter):
    name = "stock"
    ecosystem = "stock"

    def __init__(
        self,
        db_manager: Optional[DatabaseConnectionManager] = None,
    ) -> None:
        self.db_manager = db_manager or DatabaseConnectionManager()

    def collect(self) -> AdapterResult:
        """
        The stock system is not yet implemented. This adapter surfaces a hook
        for when stock agents begin publishing to the shared database.
        """

        result = AdapterResult()
        try:
            with self.db_manager.connection(self.ecosystem):
                logger.debug("Stock adapter connected to database successfully.")
        except DatabaseConnectionError:
            logger.debug("Stock adapter could not connect to database; returning empty result.")
        return result

