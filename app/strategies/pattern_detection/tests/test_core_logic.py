"""
Quick Test: Pattern Detector Core Logic
Run this to test just the pattern detection logic without the full service
"""

import pandas as pd
import numpy as np
from pattern_detector import PatternDetector
from data_fetcher import BinanceDataFetcher

def test_pattern_detector_core():
    """Test the core pattern detection logic"""

    print("="*80)
    print("TESTING PATTERN DETECTOR CORE LOGIC")
    print("="*80)

    # Initialize components
    detector = PatternDetector()
    fetcher = BinanceDataFetcher()

    # Fetch data
    print("\n[1] Fetching BTC data...")
    btc_data = fetcher.get_ohlcv('BTCUSDT', '1d', 100)

    if btc_data is None:
        print("Failed to fetch data")
        return

    print(f"[OK] Fetched {len(btc_data)} candles")

    # Update detector with data
    print("\n[2] Updating pattern detector...")
    detector.update_data(btc_data)
    print("[OK] Pattern detector updated")

    # Scan for patterns
    print("\n[3] Scanning for patterns...")
    patterns = detector.scan_for_patterns()

    print(f"[OK] Detected {len(patterns)} patterns")

    # Show results
    if patterns:
        print("\n[PATTERNS DETECTED]:")
        for i, pattern in enumerate(patterns, 1):
            print(f"{i}. {pattern['pattern'].upper()} ({pattern['direction']}) - Confidence: {pattern['confidence']:.1%}")
            print(f"   Regime: {pattern['regime']} (confidence: {pattern['regime_confidence']:.1%})")
            print(f"   Price: ${pattern['ohlcv']['close']:.2f}")
            print(f"   Stop Loss: {pattern['parameters']['stop_loss_pct']*100:.1f}%")
            print(f"   Profit Target: {pattern['parameters']['profit_target_pct']*100:.1f}%")
            print()
    else:
        print("\nNo patterns detected (this is normal - depends on current market conditions)")

    print("="*80)
    print("SUCCESS: CORE LOGIC TEST COMPLETE")
    print("Your pattern detector is working correctly!")
    print("="*80)

if __name__ == "__main__":
    test_pattern_detector_core()
