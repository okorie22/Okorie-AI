"""
Pluggable event bus for broadcasting unified events between agents.

The EventBus supports in-process subscribers and forwards published signals to
optional remote transports (Redis Streams or HTTPS webhooks) for cross-VPS
communication.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

try:  # Optional dependency
    import redis  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    redis = None

try:  # Optional dependency
    import requests
except ImportError:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

import os

from core.config import EventBusSettings, load_event_bus_settings
from core.database import UnifiedTradingSignal
from .signal_queue import SignalQueue

logger = logging.getLogger(__name__)

SignalHandler = Callable[[UnifiedTradingSignal], None]
_GLOBAL_EVENT_BUS: Optional["EventBus"] = None


class RemotePublisher:
    """Interface for remote transports."""

    def publish(self, signal: UnifiedTradingSignal, topic: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def shutdown(self) -> None:  # pragma: no cover - interface
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Publisher", "").lower()


class NoopPublisher(RemotePublisher):
    def publish(self, signal: UnifiedTradingSignal, topic: str) -> None:
        pass

    @property
    def name(self) -> str:
        return "memory"


class RedisPublisher(RemotePublisher):
    def __init__(self, url: str, stream_prefix: str = "core_signals", maxlen: int = 10_000) -> None:
        if redis is None:
            raise RuntimeError("redis package is not installed; cannot use Redis event bus backend.")
        self.client = redis.Redis.from_url(url)
        self.stream_prefix = stream_prefix
        self.maxlen = maxlen

    def publish(self, signal: UnifiedTradingSignal, topic: str) -> None:
        stream = f"{self.stream_prefix}:{topic}"
        payload = json.dumps(signal.to_dict(), default=str)
        self.client.xadd(
            stream,
            {"payload": payload},
            maxlen=self.maxlen,
            approximate=True,
        )

    def shutdown(self) -> None:
        try:
            self.client.close()
        except Exception:  # pragma: no cover - best effort close
            logger.debug("Failed to close Redis client cleanly", exc_info=True)

    @property
    def name(self) -> str:
        return "redis"


class WebhookPublisher(RemotePublisher):
    def __init__(self, url: str, secret: str, session: Optional["requests.Session"] = None) -> None:
        if requests is None:
            raise RuntimeError("requests package is not installed; cannot use webhook event bus backend.")
        self.url = url
        self.secret = secret.encode("utf-8")
        self.session = session or requests.Session()

    def publish(self, signal: UnifiedTradingSignal, topic: str) -> None:
        payload = signal.to_dict()
        body = json.dumps(payload, default=str).encode("utf-8")
        signature = hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Signal-Id": signal.signal_id,
            "X-Ecosystem": signal.ecosystem,
            "X-Topic": topic,
            "X-Signature": signature,
        }

        response = self.session.post(self.url, data=body, headers=headers, timeout=10)
        if response.status_code >= 400:
            logger.error(
                "Webhook backend rejected signal %s (%s): %s",
                signal.signal_id,
                response.status_code,
                response.text[:200],
            )

    def shutdown(self) -> None:
        try:
            self.session.close()
        except Exception:  # pragma: no cover - best effort close
            logger.debug("Failed to close webhook session cleanly", exc_info=True)

    @property
    def name(self) -> str:
        return "webhook"


def _build_remote_publisher(settings: EventBusSettings) -> RemotePublisher:
    backend = (settings.backend or "memory").lower()
    if backend == "redis":
        if not settings.redis_url:
            logger.warning(
                "CORE_EVENT_BUS_BACKEND=redis but CORE_REDIS_URL is not set. Falling back to in-memory bus."
            )
            return NoopPublisher()
        stream_prefix = os.getenv("CORE_EVENT_STREAM_PREFIX", "core_signals")
        try:
            maxlen = int(os.getenv("CORE_EVENT_STREAM_MAXLEN", "10000"))
        except ValueError:
            maxlen = 10_000
        try:
            return RedisPublisher(settings.redis_url, stream_prefix=stream_prefix, maxlen=maxlen)
        except Exception as exc:
            logger.error("Failed to initialise Redis event bus backend: %s", exc)
            return NoopPublisher()

    if backend == "webhook":
        if not settings.webhook_url or not settings.webhook_secret:
            logger.warning(
                "CORE_EVENT_BUS_BACKEND=webhook but CORE_EVENT_WEBHOOK_URL/SECRET are missing. "
                "Falling back to in-memory bus."
            )
            return NoopPublisher()
        try:
            return WebhookPublisher(settings.webhook_url, settings.webhook_secret)
        except Exception as exc:
            logger.error("Failed to initialise webhook event bus backend: %s", exc)
            return NoopPublisher()

    return NoopPublisher()


class EventBus:
    """Publish/subscribe bus for unified trading events."""

    def __init__(
        self,
        settings: Optional[EventBusSettings] = None,
        remote_publisher: Optional[RemotePublisher] = None,
        max_workers: int = 8,
        queue: Optional[SignalQueue] = None,
    ) -> None:
        self.settings = settings or load_event_bus_settings()
        self._remote_publisher = remote_publisher or _build_remote_publisher(self.settings)
        self.backend = self._remote_publisher.name

        self._subscribers: Dict[str, List[SignalHandler]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._queue = queue or SignalQueue()

        logger.info("Event bus initialised with backend '%s'", self.backend)

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------
    def subscribe(self, topic: str, handler: SignalHandler) -> None:
        """Register a handler for a topic."""
        with self._lock:
            handlers = self._subscribers.setdefault(topic, [])
            handlers.append(handler)
        logger.debug("Subscribed handler=%s to topic=%s", handler, topic)

    def unsubscribe(self, topic: str, handler: SignalHandler) -> None:
        """Remove a handler from a topic."""
        with self._lock:
            handlers = self._subscribers.get(topic, [])
            if handler in handlers:
                handlers.remove(handler)
        logger.debug("Unsubscribed handler=%s from topic=%s", handler, topic)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------
    def publish_signal(self, signal: UnifiedTradingSignal, topic: str = "signals") -> None:
        """Publish a unified trading signal to the bus and queue."""
        logger.debug(
            "Publishing signal signal_id=%s ecosystem=%s topic=%s via backend=%s",
            signal.signal_id,
            signal.ecosystem,
            topic,
            self.backend,
        )
        self._queue.enqueue(signal)
        if not isinstance(self._remote_publisher, NoopPublisher):
            self._executor.submit(self._remote_publish, signal, topic)
        self._dispatch(topic, signal)

    def _remote_publish(self, signal: UnifiedTradingSignal, topic: str) -> None:
        try:
            self._remote_publisher.publish(signal, topic)
        except Exception:  # pragma: no cover - ensures bus stability
            logger.exception("Remote publisher failed for signal %s on topic %s", signal.signal_id, topic)

    def _dispatch(self, topic: str, signal: UnifiedTradingSignal) -> None:
        handlers = self._subscribers.get(topic)
        if not handlers:
            logger.debug("No handlers registered for topic=%s", topic)
            return

        for handler in list(handlers):
            self._executor.submit(self._safe_call, handler, signal)

    @staticmethod
    def _safe_call(handler: SignalHandler, signal: UnifiedTradingSignal) -> None:
        try:
            handler(signal)
        except Exception:  # pragma: no cover - ensures bus stability
            logger.exception(
                "Subscriber %s failed while processing signal %s",
                handler,
                signal.signal_id,
            )

    # ------------------------------------------------------------------
    # Queue utilities
    # ------------------------------------------------------------------
    def next_signal(self, timeout: Optional[float] = None) -> Optional[UnifiedTradingSignal]:
        """Retrieve the next signal from the queue."""
        return self._queue.dequeue(timeout=timeout)

    def queue_size(self) -> int:
        return self._queue.size()

    def shutdown(self, wait: bool = True) -> None:
        """Cleanly shutdown the event bus."""
        self._remote_publisher.shutdown()
        self._executor.shutdown(wait=wait)
        self._queue.close()


def get_global_event_bus() -> "EventBus":
    """Return a lazily instantiated shared EventBus."""
    global _GLOBAL_EVENT_BUS
    if _GLOBAL_EVENT_BUS is None:
        _GLOBAL_EVENT_BUS = EventBus()
    return _GLOBAL_EVENT_BUS


__all__ = ["EventBus", "get_global_event_bus"]

