"""
Database connection utilities used across the ITORO ecosystems.

The DatabaseConnectionManager provides a pluggable way to manage connections to
multiple backing stores (PostgreSQL, Supabase, etc.) while keeping the rest of
the system decoupled from specific drivers. Each ecosystem may provide a custom
factory, but sensible environment-based defaults are included.
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class DatabaseConnectionError(RuntimeError):
    """Raised when a database connection cannot be established."""


@dataclass(slots=True)
class DatabaseConfig:
    """Configuration object describing how to connect to a data source."""

    dsn: str
    ecosystem: str
    driver: str = "psycopg2"
    options: Dict[str, Any] = field(default_factory=dict)


class DatabaseConnectionManager:
    """Thread-safe registry for database connection factories."""

    _instance: Optional["DatabaseConnectionManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "DatabaseConnectionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._configs: Dict[str, DatabaseConfig] = {}

        self._load_defaults_from_env()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def register_factory(
        self,
        ecosystem: str,
        factory: Callable[[], Any],
        config: Optional[DatabaseConfig] = None,
    ) -> None:
        """Register a connection factory for an ecosystem."""
        key = ecosystem.lower()
        self._factories[key] = factory
        if config:
            self._configs[key] = config
        logger.debug("Registered database factory for ecosystem=%s", key)

    def configure(
        self,
        ecosystem: str,
        dsn: str,
        driver: str = "psycopg2",
        **options: Any,
    ) -> None:
        """Register or update connection settings for an ecosystem."""
        config = DatabaseConfig(dsn=dsn, ecosystem=ecosystem, driver=driver, options=options)
        self._configs[ecosystem.lower()] = config
        logger.debug("Configured database for ecosystem=%s using driver=%s", ecosystem, driver)

    def get_factory(self, ecosystem: str) -> Callable[[], Any]:
        """Return a connection factory, building it from config if needed."""
        key = ecosystem.lower()
        if key in self._factories:
            return self._factories[key]

        config = self._configs.get(key)
        if not config:
            raise DatabaseConnectionError(f"No database configuration for ecosystem '{ecosystem}'.")

        factory = self._build_factory_from_config(config)
        self._factories[key] = factory
        return factory

    @contextmanager
    def connection(self, ecosystem: str):
        """
        Context manager that yields a live connection.

        Example:
            with DatabaseConnectionManager().connection(\"crypto\") as conn:
                cursor = conn.cursor()
                cursor.execute(...)
        """

        factory = self.get_factory(ecosystem)
        connection = None
        try:
            connection = factory()
            yield connection
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Error obtaining connection for ecosystem=%s: %s", ecosystem, exc)
            raise DatabaseConnectionError(str(exc)) from exc
        finally:
            if connection is not None:
                self._close_quietly(connection)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_defaults_from_env(self) -> None:
        """
        Populate configuration entries from environment variables.

        Expected env var pattern:
            CORE_DB_URL                -> shared services database
            CORE_CRYPTO_DB_URL         -> crypto ecosystem database
            CORE_FOREX_DB_URL          -> forex ecosystem database
            CORE_STOCK_DB_URL          -> stock ecosystem database
        """

        env_mapping = {
            "core": os.getenv("CORE_DB_URL"),
            "crypto": os.getenv("CORE_CRYPTO_DB_URL"),
            "forex": os.getenv("CORE_FOREX_DB_URL"),
            "stock": os.getenv("CORE_STOCK_DB_URL"),
        }

        for ecosystem, dsn in env_mapping.items():
            if not dsn:
                continue
            self.configure(ecosystem=ecosystem, dsn=dsn)
            logger.debug("Loaded default database config for ecosystem=%s", ecosystem)

    def _build_factory_from_config(self, config: DatabaseConfig) -> Callable[[], Any]:
        driver = config.driver.lower()
        if driver == "psycopg2":
            return self._build_psycopg_factory(config)
        if driver == "supabase":
            return self._build_supabase_factory(config)

        raise DatabaseConnectionError(f"Unsupported database driver '{config.driver}'.")

    @staticmethod
    def _build_psycopg_factory(config: DatabaseConfig) -> Callable[[], Any]:
        try:
            import psycopg2
        except ImportError as exc:  # pragma: no cover - import guard
            raise DatabaseConnectionError(
                "psycopg2 not installed; cannot create PostgreSQL connection."
            ) from exc

        def factory():
            logger.debug("Opening PostgreSQL connection for ecosystem=%s", config.ecosystem)
            return psycopg2.connect(config.dsn, **config.options)

        return factory

    @staticmethod
    def _build_supabase_factory(config: DatabaseConfig) -> Callable[[], Any]:
        try:
            from supabase import create_client  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise DatabaseConnectionError(
                "supabase-py not installed; cannot create Supabase client."
            ) from exc

        parts = config.dsn.split("|")
        if len(parts) != 2:
            raise DatabaseConnectionError(
                "Supabase DSN must be provided as 'url|anon_key' format."
            )
        url, anon_key = parts

        def factory():
            logger.debug("Opening Supabase client for ecosystem=%s", config.ecosystem)
            return create_client(url, anon_key)

        return factory

    @staticmethod
    def _close_quietly(connection: Any) -> None:
        try:
            close_method = getattr(connection, "close", None)
            if callable(close_method):
                close_method()
        except Exception:  # pragma: no cover - best effort close
            logger.debug("Failed to close database connection cleanly", exc_info=True)


__all__ = ["DatabaseConnectionManager", "DatabaseConfig", "DatabaseConnectionError"]

