"""
Unified data models shared across trading ecosystems and commerce services.

These dataclasses represent the canonical schema used by the data aggregator,
core messaging layer, and commerce agents. Each source system can supply
partial data; defaults and optional fields keep the schema flexible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class UnifiedTradingSignal:
    """
    Canonical representation for trading signals across ecosystems.

    Attributes:
        signal_id: Stable unique identifier for the signal.
        ecosystem: Which ecosystem generated the signal (e.g. 'crypto', 'forex').
        timestamp: When the signal was generated.
        symbol: Market symbol, normalized to a shared naming convention.
        action: Signal action such as 'BUY', 'SELL', 'HOLD'.
        signal_type: Order type, e.g. 'MARKET', 'LIMIT', 'STOP'.
        entry_price: Suggested entry price when available.
        stop_loss: Suggested stop loss if supplied.
        take_profit: Suggested take profit if supplied.
        confidence: Confidence score between 0.0-1.0 when available.
        volume: Optional position size units.
        agent_source: Which agent generated the signal.
        tags: Optional list of tags (e.g. strategy identifiers).
        raw_payload: Original payload for traceability and downstream auditing.
    """

    signal_id: str
    ecosystem: str
    timestamp: datetime
    symbol: str
    action: str
    signal_type: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: Optional[float] = None
    volume: Optional[float] = None
    agent_source: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the signal into a JSON-serializable dictionary."""
        return {
            "signal_id": self.signal_id,
            "ecosystem": self.ecosystem,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "action": self.action,
            "signal_type": self.signal_type,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "confidence": self.confidence,
            "volume": self.volume,
            "agent_source": self.agent_source,
            "tags": list(self.tags),
            "raw_payload": dict(self.raw_payload),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedTradingSignal":
        """Construct a signal from serialized data."""
        parsed = data.copy()
        timestamp = parsed.get("timestamp")
        if isinstance(timestamp, str):
            parsed["timestamp"] = datetime.fromisoformat(timestamp)
        return cls(**parsed)


@dataclass(slots=True)
class WhaleRankingRecord:
    """Canonical whale ranking format used by crypto and other ecosystems."""

    ranking_id: str
    ecosystem: str
    address: str
    rank: int
    score: float
    pnl_30d: Optional[float]
    pnl_7d: Optional[float]
    pnl_1d: Optional[float]
    winrate_7d: Optional[float]
    last_active: datetime
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ranking_id": self.ranking_id,
            "ecosystem": self.ecosystem,
            "address": self.address,
            "rank": self.rank,
            "score": self.score,
            "pnl_30d": self.pnl_30d,
            "pnl_7d": self.pnl_7d,
            "pnl_1d": self.pnl_1d,
            "winrate_7d": self.winrate_7d,
            "last_active": self.last_active.isoformat(),
            "is_active": self.is_active,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class StrategyMetadataRecord:
    """Aggregated performance metrics for trading strategies."""

    strategy_id: str
    ecosystem: str
    name: str
    agent_source: str
    timestamp: datetime
    sharpe_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    drawdown: Optional[float] = None
    value_at_risk: Optional[float] = None
    notes: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        output = {
            "strategy_id": self.strategy_id,
            "ecosystem": self.ecosystem,
            "name": self.name,
            "agent_source": self.agent_source,
            "timestamp": self.timestamp.isoformat(),
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "drawdown": self.drawdown,
            "value_at_risk": self.value_at_risk,
            "notes": self.notes,
            "metrics": dict(self.metrics),
        }
        return output


@dataclass(slots=True)
class ExecutedTradeRecord:
    """Normalized representation of executed trades across ecosystems."""

    trade_id: str
    ecosystem: str
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    price: float
    fees: Optional[float] = None
    pnl: Optional[float] = None
    account_reference: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "ecosystem": self.ecosystem,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "fees": self.fees,
            "pnl": self.pnl,
            "account_reference": self.account_reference,
            "metadata": dict(self.metadata),
        }

