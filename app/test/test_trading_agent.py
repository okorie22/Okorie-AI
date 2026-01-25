#!/usr/bin/env python3
"""
Test script for the event-driven trading agent
"""

import sys
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.trading_agent import TradingAgent

def test_signal_handling():
    """Test that trading agent properly handles signals"""
    print("🧪 Testing Trading Agent Signal Handling...")

    # Create agent (this will initialize Redis connection)
    agent = TradingAgent()

    # Test signal without risk parameters (should use defaults)
    test_signal_1 = {
        'symbol': 'BTCUSDT',
        'direction': 'BUY',
        'confidence': 0.85,
        'strategy_type': 'test_strategy'
    }

    print("📤 Sending test signal without risk parameters...")
    # Simulate signal (in real usage, this comes via Redis from strategies)
    agent.on_trading_signal(test_signal_1)

    # Test signal with risk parameters
    test_signal_2 = {
        'symbol': 'ETHUSDT',
        'direction': 'SELL',
        'confidence': 0.75,
        'strategy_type': 'pattern_detection',
        'risk_parameters': {
            'position_size_pct': 0.03,
            'stop_loss_pct': 0.20,
            'take_profit_pct': 0.15,
            'trailing_stop_pct': 0.05
        }
    }

    print("📤 Sending test signal with risk parameters...")
    agent.on_trading_signal(test_signal_2)

    # Test config update
    print("📤 Testing config update...")
    test_config = {
        'inherit_strategy_risk': False,
        'safety_limits': {
            'max_position_pct': 0.05,
            'max_stop_loss_pct': 0.10
        },
        'default_risk': {
            'position_size_pct': 0.02,
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.08
        }
    }

    agent.on_config_update(json.dumps(test_config))

    # Test another signal with new config
    test_signal_3 = {
        'symbol': 'SOLUSDT',
        'direction': 'BUY',
        'confidence': 0.80,
        'strategy_type': 'momentum_strategy',
        'risk_parameters': {
            'position_size_pct': 0.10,  # This should be limited to 5% by safety limits
            'stop_loss_pct': 0.30,      # This should be limited to 10% by safety limits
        }
    }

    print("📤 Sending test signal with config limits applied...")
    agent.on_trading_signal(test_signal_3)

    print("✅ Trading Agent tests completed!")
    print(f"📊 Agent status: {agent.get_status()}")

if __name__ == "__main__":
    test_signal_handling()