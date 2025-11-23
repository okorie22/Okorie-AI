"""
Centralised configuration helpers for the ITORO multi-ecosystem platform.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection strings for core and ecosystem-specific databases."""

    core: Optional[str]
    crypto: Optional[str]
    forex: Optional[str]
    stock: Optional[str]


@dataclass(frozen=True)
class EventBusSettings:
    """Configuration parameters for the pluggable event bus."""

    backend: str
    redis_url: Optional[str]
    webhook_url: Optional[str]
    webhook_secret: Optional[str]
    aggregator_endpoint: Optional[str]


def load_database_settings() -> DatabaseSettings:
    """Read database DSNs from environment variables."""

    return DatabaseSettings(
        core=os.getenv("CORE_DB_URL"),
        crypto=os.getenv("CORE_CRYPTO_DB_URL"),
        forex=os.getenv("CORE_FOREX_DB_URL"),
        stock=os.getenv("CORE_STOCK_DB_URL"),
    )


def load_event_bus_settings() -> EventBusSettings:
    """Read event bus configuration from environment variables."""

    backend = os.getenv("CORE_EVENT_BUS_BACKEND", "memory").strip().lower()
    redis_url = os.getenv("CORE_REDIS_URL")
    webhook_url = os.getenv("CORE_EVENT_WEBHOOK_URL")
    webhook_secret = os.getenv("CORE_EVENT_WEBHOOK_SECRET")
    aggregator_endpoint = os.getenv("AGG_SIGNAL_ENDPOINT")

    return EventBusSettings(
        backend=backend,
        redis_url=redis_url,
        webhook_url=webhook_url,
        webhook_secret=webhook_secret,
        aggregator_endpoint=aggregator_endpoint,
    )


__all__ = [
    "DatabaseSettings",
    "EventBusSettings",
    "load_database_settings",
    "load_event_bus_settings",
]

