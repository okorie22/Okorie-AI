from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.config import EventBusSettings
from core.database import UnifiedTradingSignal
from core.messaging.event_bus import EventBus


class TestEventBus(TestCase):
    def setUp(self):
        self.signal = UnifiedTradingSignal(
            signal_id="evt-test",
            ecosystem="crypto",
            timestamp=datetime.utcnow(),
            symbol="SOL/USDC",
            action="BUY",
            signal_type="MARKET",
            entry_price=150.0,
            confidence=0.9,
            volume=5.0,
            agent_source="unit-test",
        )

    @patch("core.messaging.event_bus.load_event_bus_settings")
    def test_default_backend_is_memory(self, mock_settings):
        mock_settings.return_value = EventBusSettings(
            backend="memory",
            redis_url=None,
            webhook_url=None,
            webhook_secret=None,
            aggregator_endpoint=None,
        )
        bus = EventBus()
        self.assertEqual(bus.backend, "memory")
        bus.publish_signal(self.signal)  # Should not raise

    @patch("core.messaging.event_bus.WebhookPublisher")
    @patch("core.messaging.event_bus.load_event_bus_settings")
    def test_webhook_backend_selected_and_invoked(self, mock_settings, mock_publisher):
        publisher_instance = mock_publisher.return_value
        mock_settings.return_value = EventBusSettings(
            backend="webhook",
            redis_url=None,
            webhook_url="https://aggregator.test/api/signals",
            webhook_secret="secret",
            aggregator_endpoint="https://aggregator.test/api/signals",
        )
        bus = EventBus()
        self.assertEqual(bus.backend, "webhook")

        # Run remote publishing synchronously for test determinism
        bus._executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)  # type: ignore
        bus.publish_signal(self.signal)
        publisher_instance.publish.assert_called_once()

    @patch("core.messaging.event_bus.load_event_bus_settings")
    def test_missing_redis_url_falls_back_to_memory(self, mock_settings):
        mock_settings.return_value = EventBusSettings(
            backend="redis",
            redis_url=None,
            webhook_url=None,
            webhook_secret=None,
            aggregator_endpoint=None,
        )
        bus = EventBus()
        self.assertEqual(bus.backend, "memory")
        bus.publish_signal(self.signal)

