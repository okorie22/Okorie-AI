"""
FastAPI application that orchestrates Telegram channel management tasks.

Provides endpoints to trigger automated content, send manual announcements,
and inspect scheduler health for the Telegram management agent.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI(
    title="ITORO Telegram Management API",
    description="Programmatic controls for Telegram content automation.",
    version="1.0.0",
)


from ..agents.signal_service_agent import get_telegram_management_agent
from ..shared.utils import api_key_manager, rate_limiter


class ManualPostRequest(BaseModel):
    message: str = Field(..., max_length=4096, description="Telegram-compatible HTML message body")
    parse_mode: Optional[str] = Field("HTML", description="Telegram parse mode (HTML/Markdown)")


class TriggerContentRequest(BaseModel):
    content_type: str = Field(
        "market",
        description="Content block to trigger (market | tip | promo | community)",
    )
    symbol: Optional[str] = Field(None, description="Optional trading pair for market updates")


def authenticate_request(
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")

    user_info = api_key_manager.validate_api_key(api_key)
    if not user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if not rate_limiter.is_allowed(user_info["user_id"], user_info.get("tier", "free")):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    return user_info


@app.post("/api/v1/signals", status_code=status.HTTP_410_GONE)
async def ingest_signal(*_: Any, **__: Any) -> JSONResponse:
    """
    Deprecated endpoint retained for backward compatibility.
    """
    return JSONResponse(
        {
            "detail": (
                "Signal ingestion is no longer supported. "
                "Please integrate directly with the Telegram Management API."
            )
        },
        status_code=status.HTTP_410_GONE,
    )


@app.post("/api/v1/telegram/posts", status_code=status.HTTP_202_ACCEPTED)
async def post_custom_message(
    payload: ManualPostRequest,
    user_info: Dict[str, Any] = Depends(authenticate_request),
) -> JSONResponse:
    agent = get_telegram_management_agent()
    success = agent.post_custom(payload.message)
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to dispatch Telegram message")
    return JSONResponse(
        {
            "status": "sent",
            "user": user_info["user_id"],
            "length": len(payload.message),
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


@app.post("/api/v1/telegram/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_content(
    payload: TriggerContentRequest,
    user_info: Dict[str, Any] = Depends(authenticate_request),
) -> JSONResponse:
    agent = get_telegram_management_agent()
    content_type = payload.content_type.lower()

    handlers = {
        "market": lambda: agent.post_market_update(payload.symbol or "EUR/USD"),
        "tip": agent.post_trading_tip,
        "promo": agent.post_promotion,
        "community": agent.post_community_prompt,
    }

    handler = handlers.get(content_type)
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content_type '{payload.content_type}'",
        )

    success = handler()
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to dispatch Telegram content")

    return JSONResponse(
        {
            "status": "triggered",
            "content_type": content_type,
            "requested_by": user_info["user_id"],
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


@app.get("/health", status_code=status.HTTP_200_OK)
async def health() -> Dict[str, Any]:
    agent = get_telegram_management_agent()
    return {"status": "ok", **agent.health_check()}

