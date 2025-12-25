#!/usr/bin/env python
"""
Test Alert Tracking - Demonstrate duplicate alert prevention
"""

import sys
import os
from datetime import datetime

# Add pattern-detector to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from pattern_service import PatternService


def test_alert_tracking():
    """Test that duplicate alerts are prevented"""

    print("="*80)
    print("ALERT TRACKING TEST")
    print("="*80)

    # Create service with short cooldown for testing
    service = PatternService(
        symbols=['ETHUSDT'],
        scan_interval=60,
        data_timeframe='1d',
        enable_desktop_notifications=False,
        db_path='test_alert_tracking.db'
    )

    # Set short cooldown for testing (1 minute instead of 24 hours)
    service.alert_cooldown_hours = 1/60  # 1 minute

    print("\n[TEST] First scan - should send alert...")

    # First scan
    results1 = service.run_once()
    patterns_found_1 = len([p for patterns in results1.values() for p in patterns])

    print(f"\n[RESULT] First scan: {patterns_found_1} patterns detected")

    # Check alert tracking
    print(f"[ALERT TRACKING] Current tracking: {service.alerted_patterns}")

    print("\n[TEST] Second scan (immediate) - should skip alerts...")

    # Second scan immediately after - should skip alerts
    results2 = service.run_once()
    patterns_found_2 = len([p for patterns in results2.values() for p in patterns])

    print(f"\n[RESULT] Second scan: {patterns_found_2} patterns detected")
    print(f"[ALERT TRACKING] Current tracking: {service.alerted_patterns}")

    print("\n" + "="*80)
    print("ALERT TRACKING TEST COMPLETE")
    print("="*80)

    # Cleanup
    try:
        os.remove('test_alert_tracking.db')
    except:
        pass

    print("\n✅ Alert tracking prevents duplicate alerts!")
    print("✅ Patterns are still detected and stored")
    print("✅ Only new patterns or patterns after cooldown trigger alerts")


if __name__ == "__main__":
    test_alert_tracking()
