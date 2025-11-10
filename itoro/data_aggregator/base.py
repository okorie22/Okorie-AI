"""
Shared base classes for the data aggregator components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from core.database import (
    ExecutedTradeRecord,
    StrategyMetadataRecord,
    UnifiedTradingSignal,
    WhaleRankingRecord,
)


@dataclass
class AdapterResult:
    """Container for raw payloads emitted by adapters."""

    raw_signals: list[dict] = field(default_factory=list)
    raw_whale_rankings: list[dict] = field(default_factory=list)
    raw_strategy_metadata: list[dict] = field(default_factory=list)
    raw_executed_trades: list[dict] = field(default_factory=list)


class BaseAdapter:
    """Base class all adapters should extend."""

    name: str = "base"
    ecosystem: str = "core"

    def collect(self) -> AdapterResult:  # pragma: no cover - interface
        raise NotImplementedError


class BaseExporter:
    """Base exporter interface."""

    def export_signals(self, signals: Sequence[UnifiedTradingSignal]) -> None:
        raise NotImplementedError

    def export_whale_rankings(self, rankings: Sequence[WhaleRankingRecord]) -> None:
        raise NotImplementedError

    def export_strategy_metadata(self, items: Sequence[StrategyMetadataRecord]) -> None:
        raise NotImplementedError

    def export_executed_trades(self, trades: Sequence[ExecutedTradeRecord]) -> None:
        raise NotImplementedError


__all__ = ["AdapterResult", "BaseAdapter", "BaseExporter"]

