"""
Health monitoring utilities for ITORO agent ecosystems.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

HealthProbe = Callable[[], bool]


@dataclass
class ComponentStatus:
    name: str
    healthy: bool
    last_checked: float
    info: Dict[str, str] = field(default_factory=dict)


class HealthChecker:
    """Registry of health probes with periodic evaluation."""

    def __init__(self, interval_seconds: float = 30.0) -> None:
        self._interval = interval_seconds
        self._probes: Dict[str, HealthProbe] = {}
        self._statuses: Dict[str, ComponentStatus] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def register(self, name: str, probe: HealthProbe) -> None:
        with self._lock:
            self._probes[name] = probe
            self._statuses[name] = ComponentStatus(
                name=name, healthy=False, last_checked=0.0, info={}
            )
        logger.debug("Registered health probe name=%s", name)

    def unregister(self, name: str) -> None:
        with self._lock:
            self._probes.pop(name, None)
            self._statuses.pop(name, None)
        logger.debug("Unregistered health probe name=%s", name)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def status(self) -> Dict[str, ComponentStatus]:
        with self._lock:
            return dict(self._statuses)

    def _run_loop(self) -> None:
        while self._running:
            self._evaluate_all()
            time.sleep(self._interval)

    def _evaluate_all(self) -> None:
        with self._lock:
            items = list(self._probes.items())

        for name, probe in items:
            try:
                healthy = probe()
                info: Dict[str, str] = {"detail": "OK" if healthy else "Unhealthy"}
            except Exception as exc:  # pragma: no cover - fail-safe
                healthy = False
                info = {"detail": str(exc)}
                logger.exception("Health probe %s failed: %s", name, exc)

            status = ComponentStatus(
                name=name,
                healthy=healthy,
                last_checked=time.time(),
                info=info,
            )
            with self._lock:
                self._statuses[name] = status


__all__ = ["HealthChecker", "ComponentStatus"]

