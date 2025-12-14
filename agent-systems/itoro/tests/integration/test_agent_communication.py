"""
🌙 Anarcho Capital's Agent Communication Integration Tests
Tests the complete agent communication flow using Redis event bus
Built with love by Anarcho Capital 🚀
"""

import pytest
import time
import threading
from datetime import datetime
from unittest.mock import Mock, patch

# Import our components
from src.scripts.shared_services.redis_event_bus import get_event_bus
from src.scripts.shared_services.alert_system import MarketAlert, AlertType, AlertSeverity, get_alert_manager
from src.strategies.templates.strategy_manager import StrategyTemplateManager
from src.agents.strategy_agent import StrategyAgent
from src.agents.trading_agent import TradingAgent


class TestAgentCommunication:
    """Integration tests for agent communication via Redis event bus"""

    def setup_method(self):
        """Setup test environment"""
        self.event_bus = get_event_bus()
        self.alert_manager = get_alert_manager()
        self.strategy_manager = StrategyTemplateManager()

        # Clear any existing alerts
        self.alert_manager.active_alerts.clear()
        self.alert_manager.alert_history.clear()

    def teardown_method(self):
        """Clean up after each test"""
        # Clear event bus subscriptions (this is a simplified cleanup)
        pass

    def test_redis_event_bus_basic_functionality(self):
        """Test basic Redis event bus publish/subscribe functionality"""
        received_messages = []

        def test_callback(message):
            received_messages.append(message)

        # Subscribe to test channel
        self.event_bus.subscribe('test_channel', test_callback)

        # Give it a moment to subscribe
        time.sleep(0.1)

        # Publish test message
        test_data = {'test': 'data', 'timestamp': datetime.now().isoformat()}
        result = self.event_bus.publish('test_channel', test_data)

        # Wait for message to be processed
        time.sleep(0.2)

        # Verify message was received
        assert result == True
        assert len(received_messages) == 1
        assert received_messages[0]['data']['test'] == 'data'

    def test_market_alert_creation_and_serialization(self):
        """Test MarketAlert creation and JSON serialization"""
        alert = MarketAlert(
            agent_source="test_agent",
            alert_type=AlertType.OI_SIGNIFICANT_CHANGE,
            symbol="BTC",
            severity=AlertSeverity.HIGH,
            confidence=0.85,
            data={
                'oi_change_pct': 25.5,
                'timeframe': '4h'
            },
            timestamp=datetime.now(),
            metadata={'test': True}
        )

        # Test serialization
        alert_dict = alert.to_dict()
        assert alert_dict['agent_source'] == 'test_agent'
        assert alert_dict['alert_type'] == 'oi_change'
        assert alert_dict['symbol'] == 'BTC'
        assert alert_dict['confidence'] == 0.85

        # Test deserialization
        alert_from_dict = MarketAlert.from_dict(alert_dict)
        assert alert_from_dict.agent_source == alert.agent_source
        assert alert_from_dict.alert_type == alert.alert_type
        assert alert_from_dict.symbol == alert.symbol

    def test_strategy_template_signal_generation(self):
        """Test strategy template signal generation"""
        # Create test alert
        alert = MarketAlert(
            agent_source="oi_agent",
            alert_type=AlertType.OI_SIGNIFICANT_CHANGE,
            symbol="BTC",
            severity=AlertSeverity.HIGH,
            confidence=0.8,
            data={
                'oi_change_pct': 30.0,
                'timeframe': '4h',
                'current_oi': 1000000
            },
            timestamp=datetime.now()
        )

        # Test strategy template generation
        signals = self.strategy_manager.generate_signals(alert)

        # Should generate OI momentum signal
        assert len(signals) > 0
        signal = signals[0]
        assert 'strategy_name' in signal
        assert 'direction' in signal
        assert 'confidence' in signal
        assert signal['direction'] in ['BUY', 'SELL']

    def test_alert_priority_scoring(self):
        """Test alert priority scoring system"""
        # Create alerts with different severities
        low_alert = MarketAlert(
            agent_source="test",
            alert_type=AlertType.OI_SIGNIFICANT_CHANGE,
            symbol="BTC",
            severity=AlertSeverity.LOW,
            confidence=0.5,
            data={},
            timestamp=datetime.now()
        )

        high_alert = MarketAlert(
            agent_source="test",
            alert_type=AlertType.FUNDING_RATE_EXTREME,
            symbol="BTC",
            severity=AlertSeverity.CRITICAL,
            confidence=0.9,
            data={},
            timestamp=datetime.now()
        )

        # Test priority scores
        low_score = low_alert.get_priority_score()
        high_score = high_alert.get_priority_score()

        assert high_score > low_score

        # Critical severity should result in high priority
        assert high_score > 150  # Our threshold for "high priority"

    def test_strategy_trigger_logic(self):
        """Test which alerts should trigger strategy generation"""
        # Alert that should trigger strategy
        trigger_alert = MarketAlert(
            agent_source="oi_agent",
            alert_type=AlertType.OI_SIGNIFICANT_CHANGE,
            symbol="BTC",
            severity=AlertSeverity.HIGH,
            confidence=0.85,
            data={'oi_change_pct': 25.0},
            timestamp=datetime.now()
        )

        # Alert that should NOT trigger strategy
        no_trigger_alert = MarketAlert(
            agent_source="oi_agent",
            alert_type=AlertType.OI_SIGNIFICANT_CHANGE,
            symbol="BTC",
            severity=AlertSeverity.LOW,
            confidence=0.3,
            data={'oi_change_pct': 5.0},
            timestamp=datetime.now()
        )

        assert trigger_alert.should_trigger_strategy() == True
        assert no_trigger_alert.should_trigger_strategy() == False

    @patch('src.models.model_factory.model_factory.get_model')
    def test_strategy_agent_initialization(self, mock_get_model):
        """Test strategy agent initialization with mocked AI model"""
        # Mock the AI model
        mock_model = Mock()
        mock_model.is_available.return_value = True
        mock_model.generate_response.return_value = "[0, 2]"  # Mock AI response
        mock_get_model.return_value = mock_model

        # Create strategy agent
        agent = StrategyAgent()

        # Verify initialization
        assert agent.ai_model is not None
        assert agent.event_bus is not None
        assert agent.alert_manager is not None
        assert agent.strategy_manager is not None

    @patch('src.models.model_factory.model_factory.get_model')
    def test_trading_agent_initialization(self, mock_get_model):
        """Test trading agent initialization with mocked AI model"""
        # Mock the AI model
        mock_model = Mock()
        mock_model.is_available.return_value = True
        mock_model.model_name = "deepseek-chat"
        mock_get_model.return_value = mock_model

        # Create trading agent
        agent = TradingAgent()

        # Verify initialization
        assert agent.model is not None
        assert agent.event_bus is not None
        assert hasattr(agent, 'strategy_signals')

    def test_end_to_end_alert_flow_simulation(self):
        """Simulate the complete alert flow without actual agents"""
        # Step 1: Simulate strategy agent processing FIRST
        signals_received = []

        def mock_strategy_callback(event_data):
            # Extract alert data from event envelope
            alert_data = event_data['data']
            # Convert to alert object
            received_alert = MarketAlert.from_dict(alert_data)

            # Generate signals using strategy manager
            signals = self.strategy_manager.generate_signals(received_alert)
            signals_received.extend(signals)

            # Publish trading signals
            for signal in signals:
                trading_signal = {
                    'source': 'strategy_agent',
                    'symbol': 'BTC',
                    'strategy_type': signal.get('strategy_name'),
                    'direction': signal.get('direction'),
                    'confidence': signal.get('confidence', 0),
                    'reasoning': signal.get('reasoning', ''),
                    'timestamp': datetime.now().isoformat()
                }
                self.event_bus.publish('trading_signal', trading_signal)

        # Subscribe to alerts FIRST
        print("DEBUG: Subscribing to market_alert...")
        self.event_bus.subscribe('market_alert', mock_strategy_callback)
        print("DEBUG: Subscribed successfully")

        # Give subscription time to settle
        time.sleep(0.1)
        print("DEBUG: Subscription settled")

        # Step 2: Create and publish alert (simulating OI agent)
        alert = MarketAlert(
            agent_source="oi_agent",
            alert_type=AlertType.OI_SIGNIFICANT_CHANGE,
            symbol="BTC",
            severity=AlertSeverity.HIGH,
            confidence=0.85,
            data={
                'oi_change_pct': 28.0,
                'timeframe': '4h',
                'current_oi': 1500000
            },
            timestamp=datetime.now()
        )

        # Publish alert to event bus
        print("DEBUG: Publishing alert...")
        result = self.event_bus.publish('market_alert', alert.to_dict())
        print(f"DEBUG: Publish result: {result}")
        assert result == True

        # Wait for processing
        print("DEBUG: Waiting for processing...")
        time.sleep(0.3)
        print(f"DEBUG: Signals received count: {len(signals_received)}")

        # Verify strategy signals were generated
        assert len(signals_received) > 0

        # Step 3: Simulate trading agent receiving signals
        trading_signals_received = []

        def mock_trading_callback(signal_data):
            trading_signals_received.append(signal_data)

        # Subscribe to trading signals
        self.event_bus.subscribe('trading_signal', mock_trading_callback)

        # Wait for processing
        time.sleep(0.2)

        # Verify trading signals were received
        assert len(trading_signals_received) > 0

        # Verify signal structure
        signal = trading_signals_received[0]
        assert 'source' in signal
        assert 'symbol' in signal
        assert 'direction' in signal
        assert 'confidence' in signal
        assert signal['symbol'] == 'BTC'


if __name__ == "__main__":
    # Run basic functionality test
    test = TestAgentCommunication()
    test.setup_method()

    try:
        print("🧪 Running agent communication tests...")

        # Test basic event bus
        test.test_redis_event_bus_basic_functionality()
        print("✅ Redis event bus test passed")

        # Test alert system
        test.test_market_alert_creation_and_serialization()
        print("✅ Alert serialization test passed")

        # Test strategy templates
        test.test_strategy_template_signal_generation()
        print("✅ Strategy template test passed")

        # Test priority scoring
        test.test_alert_priority_scoring()
        print("✅ Alert priority test passed")

        # Test strategy triggers
        test.test_strategy_trigger_logic()
        print("✅ Strategy trigger test passed")

        # Test end-to-end flow
        test.test_end_to_end_alert_flow_simulation()
        print("✅ End-to-end flow test passed")

        print("\n🎉 All integration tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
    finally:
        test.teardown_method()
