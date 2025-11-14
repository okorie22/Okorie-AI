import hashlib
import hmac
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.config import DatabaseSettings, EventBusSettings
from core.database import UnifiedTradingSignal


class TestForexTelemetryBridge(TestCase):
    def setUp(self):
        self.signal = UnifiedTradingSignal(
            signal_id="test-signal",
            ecosystem="forex",
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            action="BUY",
            signal_type="MARKET",
            entry_price=1.2345,
            stop_loss=1.2000,
            take_profit=1.2600,
            confidence=0.8,
            volume=1.0,
            agent_source="unit-test",
            tags=["forex", "unittest"],
            raw_payload={"id": "test-signal"},
        )

    @patch("ai_forex_experts.scripts.telemetry_bridge.get_global_event_bus")
    @patch("ai_forex_experts.scripts.telemetry_bridge.load_event_bus_settings")
    @patch("ai_forex_experts.scripts.telemetry_bridge.load_database_settings")
    def test_publishes_to_database_when_available(
        self, mock_load_db, mock_load_event, mock_get_bus
    ):
        mock_load_db.return_value = DatabaseSettings(
            core=None, crypto=None, forex="postgres://dsn", stock=None
        )
        mock_load_event.return_value = EventBusSettings(
            backend="memory",
            redis_url=None,
            webhook_url=None,
            webhook_secret=None,
            aggregator_endpoint=None,
        )

        mock_bus = MagicMock()
        mock_get_bus.return_value = mock_bus

        db_manager = MagicMock()
        connection_cm = db_manager.connection.return_value
        connection = connection_cm.__enter__.return_value = MagicMock()
        cursor = connection.cursor.return_value = MagicMock()

        from ai_forex_experts.scripts.telemetry_bridge import ForexTelemetryBridge

        bridge = ForexTelemetryBridge(db_manager=db_manager)
        bridge._dispatch_signal(self.signal)

        cursor.execute.assert_called_once()
        connection.commit.assert_called_once()
        mock_bus.publish_signal.assert_not_called()

    @patch("ai_forex_experts.scripts.telemetry_bridge.get_global_event_bus")
    @patch("ai_forex_experts.scripts.telemetry_bridge.load_event_bus_settings")
    @patch("ai_forex_experts.scripts.telemetry_bridge.load_database_settings")
    def test_webhook_fallback_when_database_unavailable(
        self, mock_load_db, mock_load_event, mock_get_bus
    ):
        mock_load_db.return_value = DatabaseSettings(core=None, crypto=None, forex=None, stock=None)
        secret = "super-secret"
        aggregator_endpoint = "https://aggregator.test/api/signals"
        mock_load_event.return_value = EventBusSettings(
            backend="webhook",
            redis_url=None,
            webhook_url=aggregator_endpoint,
            webhook_secret=secret,
            aggregator_endpoint=aggregator_endpoint,
        )
        mock_bus = MagicMock()
        mock_get_bus.return_value = mock_bus

        http_session = MagicMock()
        http_session.post.return_value.status_code = 202

        from ai_forex_experts.scripts.telemetry_bridge import ForexTelemetryBridge

        bridge = ForexTelemetryBridge(db_manager=MagicMock(), http_session=http_session)
        bridge._dispatch_signal(self.signal)

        http_session.post.assert_called_once()
        args, kwargs = http_session.post.call_args
        self.assertEqual(args[0], aggregator_endpoint)
        body = kwargs["data"]
        expected_signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        self.assertEqual(kwargs["headers"]["X-Signature"], expected_signature)
        mock_bus.publish_signal.assert_not_called()

    @patch("ai_forex_experts.scripts.telemetry_bridge.get_global_event_bus")
    @patch("ai_forex_experts.scripts.telemetry_bridge.load_event_bus_settings")
    @patch("ai_forex_experts.scripts.telemetry_bridge.load_database_settings")
    def test_event_bus_used_when_no_transports(
        self, mock_load_db, mock_load_event, mock_get_bus
    ):
        mock_load_db.return_value = DatabaseSettings(core=None, crypto=None, forex=None, stock=None)
        mock_load_event.return_value = EventBusSettings(
            backend="memory",
            redis_url=None,
            webhook_url=None,
            webhook_secret=None,
            aggregator_endpoint=None,
        )
        mock_bus = MagicMock()
        mock_get_bus.return_value = mock_bus

        from ai_forex_experts.scripts.telemetry_bridge import ForexTelemetryBridge

        bridge = ForexTelemetryBridge(db_manager=MagicMock(), http_session=MagicMock())
        bridge._dispatch_signal(self.signal)

        mock_bus.publish_signal.assert_called_once()

