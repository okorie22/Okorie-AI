"""
Test script for OI Agent
Tests the complete data collection, storage, and analytics pipeline
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.oi_agent import OIAgent
from src.scripts.oi.oi_storage import OIStorage
from src.scripts.oi.oi_analytics import OIAnalytics
import pandas as pd
from datetime import datetime, timedelta

def test_oi_storage():
    """Test OI storage functionality"""
    print("\n" + "="*80)
    print("🧪 Testing OI Storage")
    print("="*80)
    
    storage = OIStorage()
    
    # Create test data
    test_data = [
        {
            'timestamp': datetime.now(),
            'symbol': 'BTC',
            'open_interest': 1500000000,
            'funding_rate': 0.0001,
            'mark_price': 45000.0,
            'volume_24h': 5000000000
        },
        {
            'timestamp': datetime.now(),
            'symbol': 'ETH',
            'open_interest': 800000000,
            'funding_rate': 0.00015,
            'mark_price': 2500.0,
            'volume_24h': 2000000000
        }
    ]
    
    # Test save
    print("\n📝 Test 1: Save OI snapshot")
    if storage.save_oi_snapshot(test_data):
        print("✅ Save test passed")
    else:
        print("❌ Save test failed")
        return False
    
    # Test load
    print("\n📖 Test 2: Load history")
    history = storage.load_history(days=7)
    if history is not None:
        print(f"✅ Load test passed - loaded {len(history)} records")
        print(f"   Columns: {history.columns.tolist()}")
    else:
        print("⚠️ No history available yet (expected for first run)")
    
    # Test latest snapshot
    print("\n📊 Test 3: Get latest snapshot")
    latest = storage.get_latest_snapshot()
    if latest is not None:
        print(f"✅ Latest snapshot test passed - {len(latest)} records")
        print(latest.to_string())
    else:
        print("⚠️ No snapshot available yet")
    
    # Test stats
    print("\n📈 Test 4: Storage stats")
    stats = storage.get_storage_stats()
    print(f"✅ Storage stats:")
    print(f"   Files: {stats['file_count']}")
    print(f"   Size: {stats['total_size_mb']} MB")
    print(f"   Date Range: {stats['oldest_date']} to {stats['newest_date']}")
    
    return True

def test_oi_analytics():
    """Test OI analytics engine"""
    print("\n" + "="*80)
    print("🧪 Testing OI Analytics")
    print("="*80)
    
    analytics = OIAnalytics()
    
    # Create test data with multiple timestamps
    test_data = []
    base_time = datetime.now() - timedelta(days=7)
    
    for i in range(50):
        timestamp = base_time + timedelta(hours=i * 3.36)
        
        test_data.append({
            'timestamp': timestamp,
            'symbol': 'BTC',
            'open_interest': 1500000000 + (i * 10000000),
            'funding_rate': 0.0001 + (i * 0.000001),
            'mark_price': 45000 + (i * 100),
            'volume_24h': 5000000000 + (i * 50000000)
        })
        
        test_data.append({
            'timestamp': timestamp,
            'symbol': 'ETH',
            'open_interest': 800000000 + (i * 5000000),
            'funding_rate': 0.00015 - (i * 0.000001),
            'mark_price': 2500 + (i * 50),
            'volume_24h': 2000000000 + (i * 20000000)
        })
    
    test_df = pd.DataFrame(test_data)
    
    # Test calculate all metrics
    print("\n🔬 Test 1: Calculate all metrics")
    analytics_records = analytics.calculate_all_metrics(test_df)
    if analytics_records:
        print(f"✅ Analytics test passed - generated {len(analytics_records)} records")
        if len(analytics_records) > 0:
            sample = analytics_records[0]
            print(f"\n   Sample Analytics ({sample['symbol']} - {sample['timeframe']}):")
            print(f"   - OI Change: {sample['oi_change_pct']:.2f}%")
            print(f"   - OI Change (abs): ${sample['oi_change_abs']:,.2f}")
            if sample.get('funding_rate_change_pct'):
                print(f"   - Funding Rate Change: {sample['funding_rate_change_pct']:.2f}%")
            if sample.get('oi_volume_ratio'):
                print(f"   - OI/Volume Ratio: {sample['oi_volume_ratio']:.4f}")
    else:
        print("❌ Analytics test failed - no records generated")
        return False
    
    # Test OI changes
    print("\n📊 Test 2: Calculate OI changes")
    oi_changes = analytics.calculate_oi_changes(test_df, timeframe_hours=24)
    print(f"✅ OI Changes (24h):")
    for symbol, change in oi_changes.items():
        print(f"   {symbol}: {change:.2f}%")
    
    # Test volume metrics
    print("\n📈 Test 3: Calculate volume metrics")
    volume_metrics = analytics.calculate_volume_metrics(test_df)
    print(f"✅ Volume Metrics:")
    for symbol, metrics in volume_metrics.items():
        print(f"   {symbol}:")
        print(f"     Current Volume: ${metrics.get('current_volume', 0):,.0f}")
        print(f"     Avg Volume: ${metrics.get('avg_volume', 0):,.0f}")
        if metrics.get('volume_change_pct'):
            print(f"     Volume Change: {metrics['volume_change_pct']:.2f}%")
    
    # Test liquidity shifts
    print("\n💧 Test 4: Estimate liquidity shifts")
    liquidity_shifts = analytics.estimate_liquidity_shifts(test_df, window_hours=48)
    print(f"✅ Liquidity Shifts:")
    for symbol, shift in liquidity_shifts.items():
        print(f"   {symbol}: {shift}")
    
    return True

def test_oi_agent():
    """Test OI Agent end-to-end"""
    print("\n" + "="*80)
    print("🧪 Testing OI Agent (End-to-End)")
    print("="*80)
    
    try:
        # Initialize agent
        print("\n🚀 Initializing OI Agent...")
        agent = OIAgent()
        print("✅ Agent initialized successfully")
        
        # Run one monitoring cycle
        print("\n🔄 Running monitoring cycle...")
        agent.run_monitoring_cycle()
        print("✅ Monitoring cycle completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 OI AGENT TEST SUITE")
    print("="*80)
    
    results = []
    
    # Run tests
    print("\n" + "="*80)
    print("Phase 1: Storage Tests")
    print("="*80)
    results.append(("Storage", test_oi_storage()))
    
    print("\n" + "="*80)
    print("Phase 2: Analytics Tests")
    print("="*80)
    results.append(("Analytics", test_oi_analytics()))
    
    print("\n" + "="*80)
    print("Phase 3: End-to-End Agent Test")
    print("="*80)
    results.append(("Agent", test_oi_agent()))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

