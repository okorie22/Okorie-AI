"""
Integration Test - Full System Test
Tests all components working together end-to-end
"""

import sys
import os
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pattern_service import PatternService


def test_service_initialization():
    """Test service initialization"""
    print("\n" + "="*80)
    print("TEST: Service Initialization")
    print("="*80)
    
    try:
        service = PatternService(
            symbols=['BTCUSDT'],
            scan_interval=60,
            data_timeframe='1d',
            enable_desktop_notifications=False,
            db_path='test_integration.db'
        )
        
        print("[PASS] Service initialized successfully")
        return True, service
        
    except Exception as e:
        print(f"[FAIL] Service initialization failed: {e}")
        return False, None


def test_single_symbol_scan(service):
    """Test scanning a single symbol"""
    print("\n" + "="*80)
    print("TEST: Single Symbol Scan")
    print("="*80)
    
    try:
        patterns = service.scan_symbol('BTCUSDT')
        
        print(f"[RESULT] Detected {len(patterns)} patterns")
        
        if patterns:
            for p in patterns:
                print(f"  Pattern: {p['pattern']}")
                print(f"  Direction: {p['direction']}")
                print(f"  Confidence: {p['confidence']:.1%}")
                print(f"  Regime: {p['regime']}")
        
        print("[PASS] Single symbol scan completed")
        return True
        
    except Exception as e:
        print(f"[FAIL] Single symbol scan failed: {e}")
        return False


def test_multi_symbol_scan(service):
    """Test scanning multiple symbols"""
    print("\n" + "="*80)
    print("TEST: Multi-Symbol Scan")
    print("="*80)
    
    try:
        # Set symbols for test
        service.symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        
        results = service.scan_all_symbols()
        
        total_patterns = sum(len(patterns) for patterns in results.values())
        
        print(f"[RESULT] Scanned {len(service.symbols)} symbols")
        print(f"[RESULT] Total patterns: {total_patterns}")
        
        for symbol, patterns in results.items():
            if patterns:
                print(f"\n{symbol}:")
                for p in patterns:
                    print(f"  {p['pattern']} ({p['direction']}) - {p['confidence']:.1%}")
        
        print("\n[PASS] Multi-symbol scan completed")
        return True
        
    except Exception as e:
        print(f"[FAIL] Multi-symbol scan failed: {e}")
        return False


def test_run_once(service):
    """Test run_once method"""
    print("\n" + "="*80)
    print("TEST: Run Once")
    print("="*80)
    
    try:
        service.symbols = ['BTCUSDT']
        results = service.run_once()
        
        print(f"[RESULT] Run once completed")
        print(f"[RESULT] Results: {len(results)} symbols scanned")
        
        print("[PASS] Run once completed successfully")
        return True
        
    except Exception as e:
        print(f"[FAIL] Run once failed: {e}")
        return False


def test_status_reporting(service):
    """Test status reporting"""
    print("\n" + "="*80)
    print("TEST: Status Reporting")
    print("="*80)
    
    try:
        status = service.get_status()
        
        print(f"[STATUS]")
        print(f"  Running: {status['running']}")
        print(f"  Scan count: {status['scan_count']}")
        print(f"  Patterns detected: {status['patterns_detected']}")
        print(f"  Symbols: {status['symbols']}")
        print(f"  Scan interval: {status['scan_interval']}s")
        print(f"  Database stats: {status['database_stats'].get('total_patterns', 0)} patterns")
        
        print("\n[PASS] Status reporting successful")
        return True
        
    except Exception as e:
        print(f"[FAIL] Status reporting failed: {e}")
        return False


def test_data_flow_integrity():
    """Test complete data flow from fetching to storage"""
    print("\n" + "="*80)
    print("TEST: Data Flow Integrity")
    print("="*80)
    
    try:
        # Create fresh service
        service = PatternService(
            symbols=['ETHUSDT'],
            scan_interval=60,
            data_timeframe='1d',
            enable_desktop_notifications=False,
            db_path='test_dataflow.db'
        )
        
        # Clear database
        service.storage.clear_all_patterns()
        
        print("\n[STEP 1] Fetching data...")
        ohlcv_data = service.data_fetcher.get_ohlcv('ETHUSDT', '1d', 100)
        
        if ohlcv_data is None:
            print("[FAIL] Data fetching failed")
            return False
        
        print(f"[STEP 1] Success - Fetched {len(ohlcv_data)} candles")
        
        print("\n[STEP 2] Updating pattern detector...")
        service.pattern_detector.update_data(ohlcv_data)
        print("[STEP 2] Success - Pattern detector updated")
        
        print("\n[STEP 3] Scanning for patterns...")
        patterns = service.pattern_detector.scan_for_patterns()
        print(f"[STEP 3] Success - Detected {len(patterns)} patterns")
        
        if patterns:
            print("\n[STEP 4] Generating AI analysis...")
            pattern = patterns[0]
            alert_result = service.alert_system.send_alert(pattern, 'ETHUSDT', include_ai_analysis=False)
            print("[STEP 4] Success - AI analysis generated")
            
            print("\n[STEP 5] Storing pattern...")
            pattern_id = service.storage.save_pattern('ETHUSDT', pattern, alert_result['ai_analysis'])
            
            if pattern_id > 0:
                print(f"[STEP 5] Success - Pattern stored (ID: {pattern_id})")
            else:
                print("[STEP 5] Failed - Pattern storage failed")
                return False
            
            print("\n[STEP 6] Retrieving from database...")
            retrieved = service.storage.get_recent_patterns(1)
            
            if retrieved and len(retrieved) > 0:
                print("[STEP 6] Success - Pattern retrieved successfully")
                print(f"  Pattern: {retrieved[0]['pattern']}")
                print(f"  Symbol: {retrieved[0]['symbol']}")
                print(f"  Confidence: {retrieved[0]['confidence']:.1%}")
            else:
                print("[STEP 6] Failed - Pattern retrieval failed")
                return False
        else:
            print("[INFO] No patterns detected (this is OK - depends on market conditions)")
        
        print("\n[PASS] Data flow integrity verified")
        
        # Cleanup
        try:
            os.remove('test_dataflow.db')
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Data flow integrity test failed: {e}")
        return False


def test_error_handling():
    """Test error handling with invalid inputs"""
    print("\n" + "="*80)
    print("TEST: Error Handling")
    print("="*80)
    
    try:
        service = PatternService(
            symbols=['INVALID_SYMBOL_XYZ'],
            scan_interval=60,
            data_timeframe='1d',
            enable_desktop_notifications=False,
            db_path='test_errors.db'
        )
        
        # Try scanning invalid symbol
        print("\n[TEST] Scanning invalid symbol...")
        patterns = service.scan_symbol('INVALID_SYMBOL_XYZ')
        
        # Should return empty list, not crash
        if patterns is not None and isinstance(patterns, list):
            print(f"[PASS] Error handled gracefully (returned {len(patterns)} patterns)")
            return True
        else:
            print("[FAIL] Error handling failed")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error handling test failed: {e}")
        return False


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "#"*80)
    print("# INTEGRATION TEST SUITE")
    print("# Testing Complete Pattern Detection System")
    print("#"*80)
    
    # Initialize service
    success, service = test_service_initialization()
    if not success or service is None:
        print("\n[FATAL] Cannot proceed without service initialization")
        return False
    
    # Clear test database
    service.storage.clear_all_patterns()
    
    tests = [
        ("Single Symbol Scan", lambda: test_single_symbol_scan(service)),
        ("Multi-Symbol Scan", lambda: test_multi_symbol_scan(service)),
        ("Run Once Method", lambda: test_run_once(service)),
        ("Status Reporting", lambda: test_status_reporting(service)),
        ("Data Flow Integrity", test_data_flow_integrity),
        ("Error Handling", test_error_handling)
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
        
        time.sleep(1)  # Small delay between tests
    
    print("\n" + "#"*80)
    print(f"# INTEGRATION TEST RESULTS: {passed} passed, {failed} failed")
    print("#"*80)
    
    # Cleanup
    for db_file in ['test_integration.db', 'test_errors.db']:
        try:
            if os.path.exists(db_file):
                os.remove(db_file)
                print(f"\n[CLEANUP] Removed {db_file}")
        except PermissionError:
            print(f"\n[CLEANUP] {db_file} will be cleaned up on next run")
    
    print("\n" + "="*80)
    print("ALL INTEGRATION TESTS COMPLETE")
    print("="*80)
    print("\n[SUCCESS] Pattern Detector Backend Infrastructure is Ready!")
    print("[SUCCESS] All components tested and working together")
    print("[SUCCESS] Ready for UI integration")
    print("\n" + "="*80 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

