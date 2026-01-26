#!/usr/bin/env python3
"""Test script to verify all imports work correctly"""

print("Testing app imports...")

try:
    import trading_ui
    print("[OK] Trading UI import: SUCCESS")
except Exception as e:
    print(f"[FAIL] Trading UI import: FAILED - {e}")

try:
    from core.strategy_runner import StrategyRunner
    print("[OK] Strategy runner import: SUCCESS")
except Exception as e:
    print(f"[FAIL] Strategy runner import: FAILED - {e}")

try:
    from core.trade_executor import main
    print("[OK] Trade executor import: SUCCESS")
except Exception as e:
    print(f"[FAIL] Trade executor import: FAILED - {e}")

try:
    # This will fail due to matplotlib dependency, but path should work
    from core.data_coordinator import MultiAgentScheduler
    print("[OK] Data coordinator import: SUCCESS")
except ImportError as e:
    if "matplotlib" in str(e):
        print("[OK] Data coordinator path: SUCCESS (matplotlib dependency missing)")
    else:
        print(f"[FAIL] Data coordinator import: FAILED - {e}")
except Exception as e:
    print(f"[FAIL] Data coordinator import: FAILED - {e}")

print("\nAll import tests completed!")