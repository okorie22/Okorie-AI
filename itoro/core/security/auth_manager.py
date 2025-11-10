"""
Centralized API key management for the ITORO ecosystem.

This module keeps track of API keys used by agents, data aggregator, and
commerce services. Keys can be stored in environment variables or loaded from
external secrets managers. The manager exposes verification helpers along with
utility functions for key rotation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

logger = logging.getLogger(__name__)


def _normalize_key(key: str) -> str:
    return key.strip()


@dataclass
class ApiKeyRecord:
    key_id: str
    hashed_value: str
    scopes: Iterable[str]


class AuthManager:
    """Simple in-memory API key registry with HMAC validation."""

    def __init__(self, secret: Optional[str] = None) -> None:
        self._keys: Dict[str, ApiKeyRecord] = {}
        self._secret = secret or os.getenv("CORE_AUTH_SECRET") or secrets.token_hex(32)
        self._load_from_env()

    # ------------------------------------------------------------------
    def _load_from_env(self) -> None:
        """
        Load API keys from the CORE_API_KEYS env var.

        Format: key_id1:key_value1|key_id2:key_value2
        """

        raw = os.getenv("CORE_API_KEYS")
        if not raw:
            return

        for pair in raw.split("|"):
            try:
                key_id, key_value = pair.split(":", maxsplit=1)
            except ValueError:
                logger.warning("Invalid API key entry: %s", pair)
                continue
            self.add_key(key_id, key_value, scopes=("default",))

    # ------------------------------------------------------------------
    def add_key(
        self,
        key_id: str,
        key_value: str,
        scopes: Iterable[str] = ("default",),
    ) -> None:
        normalized = _normalize_key(key_value)
        hashed = self._hash_key(normalized)
        self._keys[key_id] = ApiKeyRecord(key_id=key_id, hashed_value=hashed, scopes=tuple(scopes))
        logger.debug("Registered API key key_id=%s scopes=%s", key_id, scopes)

    def remove_key(self, key_id: str) -> None:
        self._keys.pop(key_id, None)
        logger.debug("Removed API key key_id=%s", key_id)

    def verify(self, provided_key: str, required_scope: Optional[str] = None) -> bool:
        normalized = _normalize_key(provided_key)
        for record in self._keys.values():
            if self._compare_hash(normalized, record.hashed_value):
                if required_scope and required_scope not in record.scopes:
                    continue
                return True
        return False

    def rotate_key(self, key_id: str) -> str:
        new_value = secrets.token_urlsafe(32)
        self.add_key(key_id, new_value, scopes=self._keys[key_id].scopes)
        return new_value

    def _hash_key(self, key: str) -> str:
        return hmac.new(self._secret.encode(), key.encode(), hashlib.sha256).hexdigest()

    def _compare_hash(self, key: str, hashed_value: str) -> bool:
        digest = self._hash_key(key)
        return hmac.compare_digest(digest, hashed_value)


__all__ = ["AuthManager", "ApiKeyRecord"]

