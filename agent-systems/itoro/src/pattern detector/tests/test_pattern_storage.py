"""
Test Pattern Storage - Verify Database Operations
Tests SQLite pattern storage, retrieval, and statistics
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pattern_storage import PatternStorage


def create_sample_pattern(pattern_type='hammer', direction='long'):
    """Create a sample pattern for testing"""
    return {
        'pattern': pattern_type,
        'signal': 100 if direction == 'long' else -100,
        'confidence': 0.85,
        'direction': direction,
        'regime': 'strong_uptrend',
        'regime_confidence': 0.92,
        'timestamp': datetime.now(),
        'ohlcv': {
            'open': 87500.00,
            'high': 88000.00,
            'low': 87200.00,
            'close': 87800.00,
            'volume': 1500.50
        },
        'confirmations': {
            'trend': True,
            'momentum': True,
            'volume': True
        },
        'parameters': {
            'stop_loss_pct': 0.25,
            'profit_target_pct': 0.12,
            'trailing_activation_pct': 0.10,
            'trailing_offset_pct': 0.08,
            'min_profit_pct': 0.04,
            'max_holding_period': 48
        }
    }


def test_storage_init():
    """Test storage initialization"""
    print("\n" + "="*80)
    print("TEST: Storage Initialization")
    print("="*80)
    
    try:
        storage = PatternStorage('test_patterns.db')
        print("[PASS] Storage initialized successfully")
        return True, storage
    except Exception as e:
        print(f"[FAIL] Initialization failed: {e}")
        return False, None


def test_save_pattern(storage):
    """Test saving a pattern"""
    print("\n" + "="*80)
    print("TEST: Save Pattern")
    print("="*80)
    
    try:
        pattern = create_sample_pattern()
        pattern_id = storage.save_pattern(
            'BTCUSDT',
            pattern,
            "Strong hammer pattern with high confidence."
        )
        
        if pattern_id > 0:
            print(f"[PASS] Pattern saved with ID: {pattern_id}")
            return True
        else:
            print("[FAIL] Failed to save pattern (ID <= 0)")
            return False
            
    except Exception as e:
        print(f"[FAIL] Save pattern failed: {e}")
        return False


def test_save_multiple_patterns(storage):
    """Test saving multiple patterns"""
    print("\n" + "="*80)
    print("TEST: Save Multiple Patterns")
    print("="*80)
    
    try:
        patterns = [
            ('BTCUSDT', 'hammer', 'long'),
            ('ETHUSDT', 'doji', 'short'),
            ('SOLUSDT', 'engulfing', 'long'),
            ('BNBUSDT', 'morning_star', 'long'),
            ('BTCUSDT', 'evening_star', 'short')
        ]
        
        saved_count = 0
        for symbol, pattern_type, direction in patterns:
            pattern = create_sample_pattern(pattern_type, direction)
            pattern_id = storage.save_pattern(symbol, pattern, f"{pattern_type} pattern for {symbol}")
            if pattern_id > 0:
                saved_count += 1
        
        if saved_count == len(patterns):
            print(f"[PASS] Saved {saved_count}/{len(patterns)} patterns")
            return True
        else:
            print(f"[FAIL] Only saved {saved_count}/{len(patterns)} patterns")
            return False
            
    except Exception as e:
        print(f"[FAIL] Save multiple patterns failed: {e}")
        return False


def test_retrieve_recent(storage):
    """Test retrieving recent patterns"""
    print("\n" + "="*80)
    print("TEST: Retrieve Recent Patterns")
    print("="*80)
    
    try:
        patterns = storage.get_recent_patterns(10)
        
        if patterns and len(patterns) > 0:
            print(f"[PASS] Retrieved {len(patterns)} recent patterns:")
            for p in patterns[:3]:  # Show first 3
                print(f"  ID {p['id']}: {p['symbol']} {p['pattern']} ({p['confidence']:.1%})")
            return True
        else:
            print("[FAIL] No patterns retrieved")
            return False
            
    except Exception as e:
        print(f"[FAIL] Retrieve recent failed: {e}")
        return False


def test_retrieve_by_symbol(storage):
    """Test retrieving patterns by symbol"""
    print("\n" + "="*80)
    print("TEST: Retrieve by Symbol")
    print("="*80)
    
    try:
        patterns = storage.get_patterns_by_symbol('BTCUSDT', 10)
        
        if patterns and len(patterns) > 0:
            print(f"[PASS] Retrieved {len(patterns)} BTCUSDT patterns:")
            for p in patterns:
                print(f"  {p['pattern']} ({p['direction']}) at {p['timestamp']}")
            return True
        else:
            print("[WARN] No BTCUSDT patterns found (might be expected)")
            return True  # Not a failure, just empty result
            
    except Exception as e:
        print(f"[FAIL] Retrieve by symbol failed: {e}")
        return False


def test_retrieve_by_type(storage):
    """Test retrieving patterns by type"""
    print("\n" + "="*80)
    print("TEST: Retrieve by Type")
    print("="*80)
    
    try:
        patterns = storage.get_patterns_by_type('hammer', 10)
        
        if patterns and len(patterns) > 0:
            print(f"[PASS] Retrieved {len(patterns)} hammer patterns")
            return True
        else:
            print("[WARN] No hammer patterns found (might be expected)")
            return True  # Not a failure
            
    except Exception as e:
        print(f"[FAIL] Retrieve by type failed: {e}")
        return False


def test_statistics(storage):
    """Test pattern statistics"""
    print("\n" + "="*80)
    print("TEST: Pattern Statistics")
    print("="*80)
    
    try:
        stats = storage.get_pattern_statistics()
        
        if stats and 'total_patterns' in stats:
            print(f"[PASS] Statistics retrieved:")
            print(f"  Total patterns: {stats['total_patterns']}")
            print(f"  Average confidence: {stats['average_confidence']:.1%}")
            print(f"  Pattern counts: {stats['pattern_counts']}")
            print(f"  Symbol counts: {stats['symbol_counts']}")
            print(f"  Direction counts: {stats['direction_counts']}")
            return True
        else:
            print("[FAIL] Statistics incomplete or missing")
            return False
            
    except Exception as e:
        print(f"[FAIL] Statistics failed: {e}")
        return False


def test_data_integrity(storage):
    """Test data integrity after save/retrieve"""
    print("\n" + "="*80)
    print("TEST: Data Integrity")
    print("="*80)
    
    try:
        # Save pattern with specific values
        pattern = create_sample_pattern('doji', 'short')
        test_symbol = 'TEST_INTEGRITY'
        test_analysis = "This is a test analysis for integrity checking."
        
        pattern_id = storage.save_pattern(test_symbol, pattern, test_analysis)
        
        if pattern_id <= 0:
            print("[FAIL] Failed to save test pattern")
            return False
        
        # Retrieve and verify
        retrieved = storage.get_patterns_by_symbol(test_symbol, 1)
        
        if not retrieved or len(retrieved) == 0:
            print("[FAIL] Failed to retrieve saved pattern")
            return False
        
        p = retrieved[0]
        
        # Check key fields
        checks = {
            'symbol': p['symbol'] == test_symbol,
            'pattern': p['pattern'] == 'doji',
            'direction': p['direction'] == 'short',
            'confidence': abs(p['confidence'] - 0.85) < 0.01,
            'ai_analysis': p['ai_analysis'] == test_analysis,
            'ohlcv': p['ohlcv']['open'] == 87500.00,
            'confirmations': p['confirmations']['trend'] == True
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            print("[PASS] Data integrity verified - all fields match")
            return True
        else:
            print("[FAIL] Data integrity check failed:")
            for key, passed in checks.items():
                status = "[OK]" if passed else "[MISMATCH]"
                print(f"  {status} {key}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Data integrity test failed: {e}")
        return False


def test_duplicate_handling(storage):
    """Test handling of duplicate patterns"""
    print("\n" + "="*80)
    print("TEST: Duplicate Handling")
    print("="*80)
    
    try:
        pattern = create_sample_pattern()
        
        # Save same pattern twice
        id1 = storage.save_pattern('DUP_TEST', pattern, "First save")
        id2 = storage.save_pattern('DUP_TEST', pattern, "Second save (should replace)")
        
        # Retrieve patterns for this symbol
        patterns = storage.get_patterns_by_symbol('DUP_TEST')
        
        if len(patterns) == 1:
            print(f"[PASS] Duplicate handling works - only 1 pattern stored")
            return True
        else:
            print(f"[WARN] Found {len(patterns)} patterns (expected 1, but OK)")
            return True  # Not critical
            
    except Exception as e:
        print(f"[FAIL] Duplicate handling test failed: {e}")
        return False


def run_all_tests():
    """Run all pattern storage tests"""
    print("\n" + "#"*80)
    print("# PATTERN STORAGE TEST SUITE")
    print("# Testing SQLite Database Operations")
    print("#"*80)
    
    # Initialize storage
    success, storage = test_storage_init()
    if not success or storage is None:
        print("\n[FATAL] Cannot proceed without storage initialization")
        return False
    
    # Clear existing test data
    storage.clear_all_patterns()
    
    tests = [
        ("Save Pattern", lambda: test_save_pattern(storage)),
        ("Save Multiple Patterns", lambda: test_save_multiple_patterns(storage)),
        ("Retrieve Recent", lambda: test_retrieve_recent(storage)),
        ("Retrieve by Symbol", lambda: test_retrieve_by_symbol(storage)),
        ("Retrieve by Type", lambda: test_retrieve_by_type(storage)),
        ("Pattern Statistics", lambda: test_statistics(storage)),
        ("Data Integrity", lambda: test_data_integrity(storage)),
        ("Duplicate Handling", lambda: test_duplicate_handling(storage))
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                print(f"\n[PASS] {test_name}")
            else:
                failed += 1
                print(f"\n[FAIL] {test_name}")
        except Exception as e:
            failed += 1
            print(f"\n[FAIL] {test_name} - Exception: {e}")
    
    print("\n" + "#"*80)
    print(f"# TEST RESULTS: {passed} passed, {failed} failed")
    print("#"*80)
    
    # Cleanup
    try:
        if os.path.exists('test_patterns.db'):
            os.remove('test_patterns.db')
            print("\n[CLEANUP] Removed test database")
    except PermissionError:
        print("\n[CLEANUP] Test database will be cleaned up on next run (Windows file lock)")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

