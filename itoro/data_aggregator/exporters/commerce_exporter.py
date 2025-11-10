"""
Exporter that pushes validated records into the commerce layer.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from core.database import (
    ExecutedTradeRecord,
    StrategyMetadataRecord,
    UnifiedTradingSignal,
    WhaleRankingRecord,
)
from core.messaging import EventBus, get_global_event_bus
from data_aggregator.base import BaseExporter

logger = logging.getLogger(__name__)


class CommerceExporter(BaseExporter):
    """
    Sends normalized records to the shared EventBus for consumption by commerce
    agents. Can optionally forward payloads to other sinks (REST, storage, etc.).
    """

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or get_global_event_bus()

    def export_signals(self, signals: Sequence[UnifiedTradingSignal]) -> None:
        for signal in signals:
            logger.debug(
                "Exporting signal to commerce layer signal_id=%s ecosystem=%s",
                signal.signal_id,
                signal.ecosystem,
            )
            self.event_bus.publish_signal(signal)

    def export_whale_rankings(self, rankings: Sequence[WhaleRankingRecord]) -> None:
        for ranking in rankings:
            logger.debug(
                "Exporting whale ranking ranking_id=%s ecosystem=%s",
                ranking.ranking_id,
                ranking.ecosystem,
            )
            # Placeholder hook; commerce agents can subscribe via topic naming convention
            self.event_bus.publish_signal(
                UnifiedTradingSignal(
                    signal_id=f"whale:{ranking.ranking_id}",
                    ecosystem=ranking.ecosystem,
                    timestamp=ranking.last_active,
                    symbol=ranking.address,
                    action="HOLD",
                    signal_type="ANALYTICS",
                    raw_payload=ranking.to_dict(),
                ),
                topic="whale_rankings",
            )

    def export_strategy_metadata(self, items: Sequence[StrategyMetadataRecord]) -> None:
        for item in items:
            logger.debug(
                "Exporting strategy metadata strategy_id=%s ecosystem=%s",
                item.strategy_id,
                item.ecosystem,
            )
            self.event_bus.publish_signal(
                UnifiedTradingSignal(
                    signal_id=f"strategy:{item.strategy_id}",
                    ecosystem=item.ecosystem,
                    timestamp=item.timestamp,
                    symbol=item.name,
                    action="HOLD",
                    signal_type="ANALYTICS",
                    raw_payload=item.to_dict(),
                ),
                topic="strategy_metadata",
            )

    def export_executed_trades(self, trades: Sequence[ExecutedTradeRecord]) -> None:
        for trade in trades:
            logger.debug(
                "Exporting executed trade trade_id=%s ecosystem=%s",
                trade.trade_id,
                trade.ecosystem,
            )
            self.event_bus.publish_signal(
                UnifiedTradingSignal(
                    signal_id=f"trade:{trade.trade_id}",
                    ecosystem=trade.ecosystem,
                    timestamp=trade.timestamp,
                    symbol=trade.symbol,
                    action=trade.side,
                    signal_type="TRADE",
                    entry_price=trade.price,
                    volume=trade.quantity,
                    raw_payload=trade.to_dict(),
                ),
                topic="executed_trades",
            )

