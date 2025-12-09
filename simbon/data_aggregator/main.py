"""
Entry point for data aggregation pipelines.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Iterable, List, Optional, Sequence
from core.messaging import EventBus, get_global_event_bus
from core.monitoring.health_checker import HealthChecker

from data_aggregator.base import AdapterResult, BaseAdapter, BaseExporter
from data_aggregator.adapters import CryptoAdapter, ForexAdapter, StockAdapter
from data_aggregator.exporters import CommerceExporter
from data_aggregator.transformers import (
    SignalNormalizer,
    StrategyMetadataTransformer,
    TradeTransformer,
    WhaleRankingTransformer,
)
from data_aggregator.validators import DataQualityValidator, DuplicateChecker

logger = logging.getLogger(__name__)


class DataAggregator:
    """
    Coordinates adapters, transformers, validators, and exporters to keep
    the commerce system fed with high-quality data.
    """

    def __init__(
        self,
        adapters: Sequence[BaseAdapter],
        signal_transformer,
        whale_transformer,
        strategy_transformer,
        trade_transformer,
        validators: Sequence,
        exporters: Sequence[BaseExporter],
        event_bus: Optional[EventBus] = None,
        health_checker: Optional[HealthChecker] = None,
        interval_seconds: float = 60.0,
    ) -> None:
        self.adapters = list(adapters)
        self.signal_transformer = signal_transformer
        self.whale_transformer = whale_transformer
        self.strategy_transformer = strategy_transformer
        self.trade_transformer = trade_transformer
        self.validators = list(validators)
        self.exporters = list(exporters)
        self.event_bus = event_bus or EventBus()
        self.health_checker = health_checker or HealthChecker()
        self.interval_seconds = interval_seconds

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._register_health_probes()

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        logger.info("Starting data aggregator with %s adapters", len(self.adapters))
        self._running = True
        self.health_checker.start()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.event_bus.shutdown()
        self.health_checker.stop()

    def run_once(self) -> None:
        """Execute a single aggregation cycle."""
        for adapter in self.adapters:
            self._process_adapter(adapter)

    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        while self._running:
            start = time.time()
            self.run_once()
            elapsed = time.time() - start
            sleep_time = max(0.0, self.interval_seconds - elapsed)
            time.sleep(sleep_time)

    def _process_adapter(self, adapter: BaseAdapter) -> None:
        logger.debug("Collecting data from adapter=%s", adapter.name)

        try:
            result = adapter.collect()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Adapter %s failed: %s", adapter.name, exc)
            return

        signals = self.signal_transformer.normalize(adapter, result.raw_signals)
        rankings = self.whale_transformer.normalize(adapter, result.raw_whale_rankings)
        strategies = self.strategy_transformer.normalize(adapter, result.raw_strategy_metadata)
        trades = self.trade_transformer.normalize(adapter, result.raw_executed_trades)

        signals = self._apply_validators(signals)
        rankings = self._apply_validators(rankings)
        strategies = self._apply_validators(strategies)
        trades = self._apply_validators(trades)

        for exporter in self.exporters:
            try:
                exporter.export_signals(signals)
                exporter.export_whale_rankings(rankings)
                exporter.export_strategy_metadata(strategies)
                exporter.export_executed_trades(trades)
            except Exception:  # pragma: no cover - ensure one exporter failure does not halt pipeline
                logger.exception("Exporter %s failed", exporter.__class__.__name__)

    def _apply_validators(self, records: Iterable):
        validated = list(records)
        for validator in self.validators:
            validated = validator.validate(validated)
        return validated

    def _register_health_probes(self) -> None:
        for adapter in self.adapters:
            self.health_checker.register(
                f"adapter:{adapter.name}",
                lambda adapter=adapter: adapter_health(adapter),
            )


def build_default_aggregator(interval_seconds: float = 60.0) -> DataAggregator:
    """
    Convenience factory that wires the default adapters, transformers,
    validators, and exporters together.
    """

    signal_transformer = SignalNormalizer()
    whale_transformer = WhaleRankingTransformer()
    strategy_transformer = StrategyMetadataTransformer()
    trade_transformer = TradeTransformer()

    validators = [
        DuplicateChecker(key_field="signal_id"),
        DataQualityValidator(required_fields=("signal_id", "symbol")),
    ]

    event_bus = get_global_event_bus()
    exporters = [CommerceExporter(event_bus=event_bus)]

    adapters = [
        CryptoAdapter(),
        ForexAdapter(),
        StockAdapter(),
    ]

    health_checker = HealthChecker(interval_seconds=interval_seconds)

    aggregator = DataAggregator(
        adapters=adapters,
        signal_transformer=signal_transformer,
        whale_transformer=whale_transformer,
        strategy_transformer=strategy_transformer,
        trade_transformer=trade_transformer,
        validators=validators,
        exporters=exporters,
        event_bus=event_bus,
        health_checker=health_checker,
        interval_seconds=interval_seconds,
    )
    return aggregator


def adapter_health(adapter: BaseAdapter) -> bool:
    try:
        adapter.collect()
        return True
    except Exception:
        logger.exception("Health probe failed for adapter=%s", adapter.name)
        return False


__all__ = [
    "DataAggregator",
    "BaseAdapter",
    "BaseExporter",
    "AdapterResult",
    "build_default_aggregator",
]


if __name__ == "__main__":  # pragma: no cover - manual execution entry point
    logging.basicConfig(level=logging.INFO)
    aggregator = build_default_aggregator()
    try:
        aggregator.start()
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down data aggregator...")
        aggregator.stop()

