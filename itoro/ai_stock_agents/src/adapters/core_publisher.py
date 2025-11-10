"""
Placeholder adapter for publishing stock ecosystem data to the core layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from core.database import UnifiedTradingSignal
from core.messaging import get_global_event_bus


@dataclass
class StockSignal:
    """Lightweight representation of a stock trading signal."""

    symbol: str
    action: str
    signal_type: str = "MARKET"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: Optional[float] = None
    volume: Optional[float] = None
    metadata: Optional[dict] = None

    def to_unified(self) -> UnifiedTradingSignal:
        metadata = self.metadata or {}
        return UnifiedTradingSignal(
            signal_id=f"stock:{self.symbol}:{datetime.utcnow().isoformat()}",
            ecosystem="stock",
            timestamp=datetime.utcnow(),
            symbol=self.symbol,
            action=self.action.upper(),
            signal_type=self.signal_type.upper(),
            entry_price=self.entry_price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            confidence=self.confidence,
            volume=self.volume,
            agent_source=metadata.get("agent_source", "stock_system"),
            tags=metadata.get("tags", []),
            raw_payload=metadata,
        )


def publish_stock_signals(signals: Iterable[StockSignal]) -> None:
    """
    Convert StockSignal objects to UnifiedTradingSignal and publish them on the
    shared event bus. Intended for future stock agents.
    """

    bus = get_global_event_bus()
    for signal in signals:
        unified = signal.to_unified()
        bus.publish_signal(unified, topic="signals")

