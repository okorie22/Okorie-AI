"""
Optional FastAPI application for receiving webhook-published signals.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Optional

from core.config import load_event_bus_settings
from core.database import UnifiedTradingSignal
from core.messaging import get_global_event_bus

try:  # Optional dependency
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore

logger = logging.getLogger(__name__)


def create_app(event_bus=None) -> "FastAPI":
    """
    Create a FastAPI application that validates webhook requests and forwards
    them to the shared event bus. Raises RuntimeError if FastAPI is not installed.
    """

    if FastAPI is None:
        raise RuntimeError("FastAPI is required for webhook reception. Install `fastapi` and `uvicorn`.")

    event_bus = event_bus or get_global_event_bus()
    settings = load_event_bus_settings()
    if not settings.webhook_secret:
        raise RuntimeError("CORE_EVENT_WEBHOOK_SECRET must be set to use the webhook receiver.")

    secret = settings.webhook_secret.encode("utf-8")
    app = FastAPI(title="ITORO Aggregator Webhook", version="1.0.0")

    @app.post("/api/signals")
    async def ingest_signal(
        request: Request,
        x_signature: Optional[str] = Header(None, convert_underscores=True),
        x_topic: Optional[str] = Header("signals", convert_underscores=True),
    ):
        body = await request.body()
        if not x_signature:
            raise HTTPException(status_code=401, detail="Missing signature header.")

        expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_signature, x_signature):
            raise HTTPException(status_code=401, detail="Invalid signature.")

        try:
            payload = json.loads(body)
            signal = UnifiedTradingSignal.from_dict(payload)
        except Exception as exc:
            logger.exception("Failed to parse webhook payload: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid signal payload.") from exc

        event_bus.publish_signal(signal, topic=x_topic or "signals")
        return JSONResponse({"status": "accepted"}, status_code=202)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "backend": event_bus.backend}

    return app


# Expose `app` for `uvicorn data_aggregator.webhook_server:app`
try:
    app = create_app()
except RuntimeError as exc:  # pragma: no cover - optional dependency not installed
    logger.warning("Webhook server disabled: %s", exc)
    app = None

