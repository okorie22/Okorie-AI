"""
Thread-safe signal queue used by the EventBus and background processors.
"""

from __future__ import annotations

import queue
import threading
from typing import Optional

from core.database import UnifiedTradingSignal


class SignalQueue:
    """Wrapper around Queue providing graceful shutdown behaviour."""

    def __init__(self, maxsize: int = 0) -> None:
        self._queue: queue.Queue[UnifiedTradingSignal] = queue.Queue(maxsize=maxsize)
        self._closed = False
        self._lock = threading.Lock()

    def enqueue(self, signal: UnifiedTradingSignal) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("Cannot enqueue to a closed SignalQueue.")
            self._queue.put(signal, block=False)

    def dequeue(self, timeout: Optional[float] = None) -> Optional[UnifiedTradingSignal]:
        if self._closed and self._queue.empty():
            return None
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def size(self) -> int:
        return self._queue.qsize()

    def close(self) -> None:
        with self._lock:
            self._closed = True
        # Drain queue by putting sentinel None
        try:
            self._queue.put_nowait(None)  # type: ignore[arg-type]
        except queue.Full:
            pass

