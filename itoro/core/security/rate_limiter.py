"""
Token-bucket based rate limiter for API and inter-service communication.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class RateLimitConfig:
    capacity: int
    refill_rate_per_sec: float


class RateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self) -> None:
        self._limits: Dict[str, RateLimitConfig] = {}
        self._tokens: Dict[str, float] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()

    def configure(self, key: str, capacity: int, refill_rate_per_sec: float) -> None:
        with self._lock:
            self._limits[key] = RateLimitConfig(capacity, refill_rate_per_sec)
            self._tokens[key] = float(capacity)
            self._timestamps[key] = time.monotonic()

    def allow(self, key: str, cost: float = 1.0) -> bool:
        with self._lock:
            if key not in self._limits:
                # Default to unlimited unless configured
                return True

            now = time.monotonic()
            elapsed = now - self._timestamps[key]
            limit = self._limits[key]

            # Refill tokens
            refill = elapsed * limit.refill_rate_per_sec
            self._tokens[key] = min(limit.capacity, self._tokens[key] + refill)
            self._timestamps[key] = now

            if self._tokens[key] >= cost:
                self._tokens[key] -= cost
                return True

            return False


__all__ = ["RateLimiter", "RateLimitConfig"]

