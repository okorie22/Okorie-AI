# 🌙 DeepSeek + Redis Agent Integration

## Overview

This integration transforms the trading system from independent agents to a cohesive, event-driven architecture using DeepSeek AI and Redis-based communication.

## 🏗️ Architecture

```
OI Agent → Redis Event Bus → Strategy Agent → Redis Event Bus → Trading Agent
Funding Agent ↗                                      ↗
Liquidation Agent ↗                                  ↗
```

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install Redis
# Ubuntu/Debian:
sudo apt install redis-server

# macOS:
brew install redis

# Windows: Download from https://redis.io/download

# Start Redis
redis-server

# Install Python dependencies
pip install redis
```

### 2. Environment Setup

Add to your `.env` file:

```bash
# DeepSeek API Key (required)
DEEPSEEK_KEY=your_deepseek_api_key_here

# Redis Configuration (optional, defaults provided)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # Leave empty if no password
```

### 3. Test Redis Connection

```bash
# Run Redis health check
python -m src.scripts.utilities.redis_health_check

# Expected output:
🔍 Running Redis Health Diagnostic...
═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═ ═
🔌 Testing basic connection...
✅ Connection: Healthy (1.23ms ping)
📊 Redis Health Diagnostic Summary
✅ Overall Status: HEALTHY (5/5 tests passed)
```

### 4. Run Integration Tests

```bash
# Run agent communication tests
python -m tests.integration.test_agent_communication

# Expected output:
🧪 Running agent communication tests...
✅ Redis event bus test passed
✅ Alert serialization test passed
✅ Strategy template test passed
✅ Alert priority test passed
✅ Strategy trigger test passed
✅ End-to-end flow test passed

🎉 All integration tests passed!
```

## 🤖 Agent Communication Flow

### Phase 1: Alert Generation
1. **OI Agent** monitors open interest changes
2. **Funding Agent** monitors funding rate extremes
3. **Liquidation Agent** monitors liquidation spikes

When significant events occur, agents publish `MarketAlert` objects to Redis:

```python
alert = MarketAlert(
    agent_source="oi_agent",
    alert_type=AlertType.OI_SIGNIFICANT_CHANGE,
    symbol="BTC",
    severity=AlertSeverity.HIGH,
    confidence=0.85,
    data={'oi_change_pct': 25.0},
    timestamp=datetime.now()
)

event_bus.publish('market_alert', alert.to_dict())
```

### Phase 2: Strategy Processing
1. **Strategy Agent** subscribes to `market_alert` events
2. Uses **Strategy Templates** to generate trading signals
3. Applies AI evaluation to filter and prioritize signals

```python
# Strategy templates automatically generate signals
oi_strategy = OIMomentumStrategy()
signals = oi_strategy.generate_signal(alert)

# AI evaluates and filters signals
approved_signals = strategy_agent.evaluate_strategy_signals(signals)
```

### Phase 3: Trade Execution
1. **Trading Agent** subscribes to `trading_signal` events
2. Incorporates strategy signals into market analysis
3. Makes final trading decisions with full context

```python
# Trading agent receives strategy signals
data['strategy_signals'] = [signal1, signal2, signal3]

# AI analyzes market + strategy signals together
analysis = self.analyze_market_data(token, data)
```

## 🎯 Strategy Templates

The system includes sophisticated strategy templates:

- **OI Momentum**: Trades based on significant OI changes
- **Funding Arbitrage**: Exploits extreme funding rates
- **Liquidation Reversal**: Fades large liquidation events
- **Sentiment Reversal**: Trades against extreme sentiment

## 🔧 Configuration

### AI Model Configuration

All agents now use DeepSeek. Configure in your config files:

```python
# In config.py or agent-specific configs
AI_MODEL_TYPE = 'deepseek'
AI_MODEL_NAME = 'deepseek-chat'  # or 'deepseek-reasoner'
```

### Redis Event Bus

The event bus automatically connects using environment variables:

```bash
# .env file
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password  # optional
```

## 📊 Monitoring & Debugging

### Health Checks

```bash
# Redis connectivity
python -m src.scripts.utilities.redis_health_check

# Event bus statistics
from src.scripts.shared_services.redis_event_bus import get_event_bus
bus = get_event_bus()
stats = bus.get_stats()
print(stats)
```

### Alert System Monitoring

```bash
from src.scripts.shared_services.alert_system import get_alert_manager
manager = get_alert_manager()
stats = manager.get_stats()
print(f"Active alerts: {stats['active_alerts']}")
print(f"Strategy triggers: {stats['strategy_triggers']}")
```

## 🧪 Testing

### Unit Tests

```bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Test specific components
python -m pytest tests/integration/test_agent_communication.py::TestAgentCommunication::test_strategy_template_signal_generation -v
```

### Manual Testing

1. Start Redis server
2. Run health check to verify connectivity
3. Start individual agents to test communication
4. Monitor event bus activity

## 🚨 Troubleshooting

### Redis Connection Issues

```bash
# Check if Redis is running
redis-cli ping

# Check Redis logs
redis-cli monitor

# Test with health check utility
python -m src.scripts.utilities.redis_health_check --host localhost --port 6379
```

### Agent Communication Issues

```bash
# Check event bus subscriptions
from src.scripts.shared_services.redis_event_bus import get_event_bus
bus = get_event_bus()
stats = bus.get_stats()
print(f"Subscriptions: {stats}")

# Verify alerts are being published
from src.scripts.shared_services.alert_system import get_alert_manager
manager = get_alert_manager()
alerts = manager.get_high_priority_alerts()
print(f"High priority alerts: {len(alerts)}")
```

### AI Model Issues

```bash
# Test DeepSeek connectivity
from src.models.model_factory import model_factory
model = model_factory.get_model('deepseek', 'deepseek-chat')
print(f"Model available: {model.is_available()}")

# Test basic AI call
response = model.generate_response(
    system_prompt="You are a trading assistant",
    user_content="Hello",
    max_tokens=50
)
print(f"Response: {response}")
```

## 🎯 Success Metrics

- **Alert Processing**: >95% of alerts processed within 1 second
- **Signal Conversion**: >70% of high-confidence alerts generate trading signals
- **End-to-End Latency**: <2 seconds from alert to trade execution
- **System Reliability**: 99.5% uptime during market hours

## 🔄 Migration Complete

✅ **Phase 1**: All agents migrated to DeepSeek AI
✅ **Phase 2**: Redis Event Bus implemented
✅ **Phase 3**: Strategy Agent completed with templates
✅ **Phase 4**: Trading Agent integrated with signals
✅ **Phase 5**: Testing and health checks implemented

The system is now a cohesive, event-driven trading platform! 🚀
