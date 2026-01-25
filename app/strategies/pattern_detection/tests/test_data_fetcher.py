"""
Test Data Fetcher - Verify Consistent OHLCV Retrieval
Tests Binance API and fallback sources
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_fetcher import BinanceDataFetcher


def test_binance_single_symbol():
    """Test fetching single symbol from Binance"""
    print("\n" + "="*80)
    print("TEST: Binance Single Symbol Fetch")
    print("="*80)
    
    fetcher = BinanceDataFetcher()
    
    # Test BTC
    print("\n[TEST] Fetching BTCUSDT (1d, 100 candles)...")
    df = fetcher.get_ohlcv('BTCUSDT', '1d', 100)
    
    if df is not None and len(df) > 0:
        print(f"[PASS] Successfully fetched {len(df)} candles")
        print(f"[INFO] Date range: {df.index[0]} to {df.index[-1]}")
        print(f"[INFO] Latest close: ${df['Close'].iloc[-1]:.2f}")
        print(f"\n[SAMPLE] Last 5 candles:")
        print(df.tail())
        return True
    else:
        print("[FAIL] Failed to fetch data")
        return False


def test_multiple_symbols():
    """Test fetching multiple symbols"""
    print("\n" + "="*80)
    print("TEST: Multiple Symbols Fetch")
    print("="*80)
    
    fetcher = BinanceDataFetcher()
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    
    print(f"\n[TEST] Fetching {len(symbols)} symbols...")
    results = fetcher.fetch_multiple_symbols(symbols, '1d', 50)
    
    if len(results) == len(symbols):
        print(f"[PASS] Successfully fetched all {len(symbols)} symbols")
        for symbol, data in results.items():
            print(f"  {symbol}: {len(data)} candles, Latest: ${data['Close'].iloc[-1]:.2f}")
        return True
    else:
        print(f"[FAIL] Only fetched {len(results)}/{len(symbols)} symbols")
        return False


def test_different_intervals():
    """Test fetching different timeframes"""
    print("\n" + "="*80)
    print("TEST: Different Intervals")
    print("="*80)
    
    fetcher = BinanceDataFetcher()
    intervals = ['1d', '4h', '1h']
    
    all_passed = True
    for interval in intervals:
        print(f"\n[TEST] Fetching BTCUSDT {interval}...")
        df = fetcher.get_ohlcv('BTCUSDT', interval, 20)
        
        if df is not None and len(df) > 0:
            print(f"[PASS] {interval}: {len(df)} candles")
        else:
            print(f"[FAIL] {interval}: Failed to fetch")
            all_passed = False
    
    return all_passed


def test_data_consistency():
    """Test data consistency across multiple calls"""
    print("\n" + "="*80)
    print("TEST: Data Consistency")
    print("="*80)
    
    fetcher = BinanceDataFetcher()
    
    print("\n[TEST] Fetching ETHUSDT twice with 2-second delay...")
    
    # First fetch
    df1 = fetcher.get_ohlcv('ETHUSDT', '1d', 10)
    time.sleep(2)
    
    # Second fetch
    df2 = fetcher.get_ohlcv('ETHUSDT', '1d', 10)
    
    if df1 is None or df2 is None:
        print("[FAIL] One or both fetches failed")
        return False
    
    # Compare data (should be nearly identical for historical candles)
    historical_match = (df1.iloc[:-1]['Close'] == df2.iloc[:-1]['Close']).all()
    
    if historical_match:
        print("[PASS] Historical data consistent across calls")
        return True
    else:
        print("[FAIL] Data inconsistency detected")
        return False


def test_data_validation():
    """Test data validation logic"""
    print("\n" + "="*80)
    print("TEST: Data Validation")
    print("="*80)
    
    fetcher = BinanceDataFetcher()
    
    print("\n[TEST] Fetching and validating SOLUSDT...")
    df = fetcher.get_ohlcv('SOLUSDT', '1d', 50)
    
    if df is None:
        print("[FAIL] Failed to fetch data")
        return False
    
    # Check validation criteria
    checks = {
        'No nulls': not df.isnull().any().any(),
        'OHLC logic': (
            (df['High'] >= df['Low']).all() and
            (df['High'] >= df['Open']).all() and
            (df['High'] >= df['Close']).all() and
            (df['Low'] <= df['Open']).all() and
            (df['Low'] <= df['Close']).all()
        ),
        'Positive prices': (df[['Open', 'High', 'Low', 'Close']] > 0).all().all(),
        'Positive volume': (df['Volume'] >= 0).all()
    }
    
    all_passed = True
    for check_name, result in checks.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {check_name}")
        if not result:
            all_passed = False
    
    return all_passed


def test_latency():
    """Test fetch latency"""
    print("\n" + "="*80)
    print("TEST: Fetch Latency")
    print("="*80)
    
    fetcher = BinanceDataFetcher()
    
    print("\n[TEST] Measuring fetch latency for BTCUSDT...")
    start_time = time.time()
    df = fetcher.get_ohlcv('BTCUSDT', '1d', 100)
    elapsed = time.time() - start_time
    
    if df is not None:
        print(f"[RESULT] Fetch completed in {elapsed:.2f} seconds")
        if elapsed < 5.0:
            print("[PASS] Latency under 5 seconds")
            return True
        else:
            print("[WARN] Latency over 5 seconds (acceptable but slow)")
            return True
    else:
        print("[FAIL] Fetch failed")
        return False


def run_all_tests():
    """Run all data fetcher tests"""
    print("\n" + "#"*80)
    print("# DATA FETCHER TEST SUITE")
    print("# Testing Binance API and Fallback Sources")
    print("#"*80)
    
    tests = [
        ("Binance Single Symbol", test_binance_single_symbol),
        ("Multiple Symbols", test_multiple_symbols),
        ("Different Intervals", test_different_intervals),
        ("Data Consistency", test_data_consistency),
        ("Data Validation", test_data_validation),
        ("Fetch Latency", test_latency)
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
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

