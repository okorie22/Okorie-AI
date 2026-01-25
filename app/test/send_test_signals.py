#!/usr/bin/env python3
"""
Trading Signal Injection Script
Send test signals to the trading agent for testing purposes
"""

import redis
import json
import time
import random
import argparse
from termcolor import colored, cprint

def send_signal(redis_client, signal_data, delay=1):
    """Send a single signal to the trading agent"""
    try:
        cprint(f"[SEND] Signal: {signal_data['symbol']} {signal_data['direction']} ({signal_data['confidence']:.1%})", "cyan")

        # Publish to Redis
        redis_client.publish('trading_signal', json.dumps(signal_data))

        # Wait for processing
        time.sleep(delay)

        cprint("[OK] Signal sent successfully", "green")

    except Exception as e:
        cprint(f"[ERROR] Failed to send signal: {e}", "red")

def create_test_signal(symbol="BTCUSDT", direction="BUY", confidence=0.85,
                      strategy="test_strategy", include_risk_params=True):
    """Create a test trading signal"""
    signal = {
        'symbol': symbol,
        'direction': direction,
        'confidence': confidence,
        'strategy_type': strategy,
        'timestamp': time.time()
    }

    # Optionally include risk parameters (like advanced strategies do)
    if include_risk_params:
        signal['risk_parameters'] = {
            'position_size_pct': 0.03,      # 3% of portfolio
            'stop_loss_pct': 0.05,          # 5% stop loss
            'take_profit_pct': 0.10,        # 10% take profit
            'trailing_stop_pct': 0.03       # 3% trailing stop
        }

    return signal

def run_basic_tests(redis_client):
    """Run basic signal tests"""
    cprint("[TEST] Running Basic Signal Tests...", "yellow")

    # Test 1: Signal with risk parameters (should be accepted)
    cprint("\n[TEST1] Signal with risk parameters", "blue")
    signal1 = create_test_signal("BTCUSDT", "BUY", 0.85, "pattern_detection", True)
    send_signal(redis_client, signal1)

    # Test 2: Signal without risk parameters (should use defaults)
    cprint("\n[TEST2] Signal without risk parameters", "blue")
    signal2 = create_test_signal("ETHUSDT", "SELL", 0.75, "momentum_strategy", False)
    send_signal(redis_client, signal2)

    # Test 3: Low confidence signal
    cprint("\n[TEST3] Low confidence signal", "blue")
    signal3 = create_test_signal("SOLUSDT", "BUY", 0.60, "weak_signal_test", True)
    send_signal(redis_client, signal3)

def run_risk_limit_tests(redis_client):
    """Test safety limit enforcement"""
    cprint("[RISK] Running Risk Limit Tests...", "yellow")

    # Test: Position size too large (should be rejected)
    cprint("\n[TEST] Oversized position (should be rejected)", "blue")
    oversized_signal = create_test_signal("ADAUSDT", "BUY", 0.80, "risk_test", True)
    oversized_signal['risk_parameters']['position_size_pct'] = 0.20  # 20% - over limit
    send_signal(redis_client, oversized_signal)

    # Test: Stop loss too wide (should be rejected)
    cprint("\n[TEST] Stop loss too wide (should be rejected)", "blue")
    wide_sl_signal = create_test_signal("DOTUSDT", "SELL", 0.70, "risk_test", True)
    wide_sl_signal['risk_parameters']['stop_loss_pct'] = 0.20  # 20% - over limit
    send_signal(redis_client, wide_sl_signal)

def run_bulk_test(redis_client, count=5):
    """Send multiple random signals"""
    cprint(f"[BULK] Running Bulk Test: {count} random signals...", "yellow")

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT"]
    directions = ["BUY", "SELL"]
    strategies = ["pattern_detection", "momentum", "mean_reversion", "breakout"]

    for i in range(count):
        cprint(f"\n[SIGNAL] Bulk Signal {i+1}/{count}", "blue")

        # Random signal parameters
        symbol = random.choice(symbols)
        direction = random.choice(directions)
        confidence = random.uniform(0.65, 0.95)
        strategy = random.choice(strategies)
        has_risk = random.choice([True, False])

        signal = create_test_signal(symbol, direction, confidence, strategy, has_risk)
        send_signal(redis_client, signal, 0.5)  # Shorter delay

def run_custom_signal(redis_client, symbol, direction, confidence=0.80, strategy="custom"):
    """Send a custom signal"""
    cprint(f"[CUSTOM] Sending custom signal: {symbol} {direction}", "magenta")

    signal = create_test_signal(symbol, direction, confidence, strategy, True)
    send_signal(redis_client, signal)

def main():
    parser = argparse.ArgumentParser(description='Send test trading signals')
    parser.add_argument('--test', choices=['basic', 'risk', 'bulk', 'custom'],
                       default='basic', help='Test type to run')
    parser.add_argument('--symbol', default='BTCUSDT', help='Symbol for custom signal')
    parser.add_argument('--direction', choices=['BUY', 'SELL'], default='BUY',
                       help='Direction for custom signal')
    parser.add_argument('--confidence', type=float, default=0.80,
                       help='Confidence for custom signal (0.0-1.0)')
    parser.add_argument('--count', type=int, default=5,
                       help='Number of signals for bulk test')
    parser.add_argument('--redis-host', default='localhost', help='Redis host')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port')

    args = parser.parse_args()

    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host=args.redis_host,
            port=args.redis_port,
            decode_responses=True
        )

        # Test connection
        redis_client.ping()
        cprint("[OK] Connected to Redis", "green")

        # Run selected test
        if args.test == 'basic':
            run_basic_tests(redis_client)
        elif args.test == 'risk':
            run_risk_limit_tests(redis_client)
        elif args.test == 'bulk':
            run_bulk_test(redis_client, args.count)
        elif args.test == 'custom':
            run_custom_signal(redis_client, args.symbol, args.direction,
                            args.confidence, "custom_cli")

        cprint("\n[DONE] Signal testing completed!", "green")
        cprint("[INFO] Check trading agent logs to see signal processing", "cyan")

    except redis.ConnectionError:
        cprint("[ERROR] Cannot connect to Redis. Make sure Redis is running.", "red")
        cprint("[HINT] Start Redis: redis-server", "yellow")
    except Exception as e:
        cprint(f"[ERROR] {e}", "red")

if __name__ == "__main__":
    main()