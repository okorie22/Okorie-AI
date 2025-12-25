"""
Test Alert System - Verify AI Analysis and Notifications
Tests DeepSeek API integration and alert delivery
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alert_system import AlertSystem


def create_sample_pattern():
    """Create a sample pattern for testing"""
    return {
        'pattern': 'engulfing',
        'signal': 100,
        'confidence': 0.92,
        'direction': 'long',
        'regime': 'moderate_uptrend',
        'regime_confidence': 0.88,
        'timestamp': datetime.now(),
        'ohlcv': {
            'open': 87500.00,
            'high': 88500.00,
            'low': 87200.00,
            'close': 88300.00,
            'volume': 2500.75
        },
        'confirmations': {
            'trend': True,
            'momentum': True,
            'volume': True
        },
        'parameters': {
            'stop_loss_pct': 0.20,
            'profit_target_pct': 0.13,
            'trailing_activation_pct': 0.09,
            'trailing_offset_pct': 0.07,
            'min_profit_pct': 0.035,
            'max_holding_period': 42
        }
    }


def test_alert_system_init():
    """Test alert system initialization"""
    print("\n" + "="*80)
    print("TEST: Alert System Initialization")
    print("="*80)
    
    try:
        alert_system = AlertSystem()
        print("[PASS] Alert system initialized successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Initialization failed: {e}")
        return False


def test_fallback_analysis():
    """Test fallback analysis (without AI)"""
    print("\n" + "="*80)
    print("TEST: Fallback Analysis")
    print("="*80)
    
    try:
        # Initialize without API key
        alert_system = AlertSystem(deepseek_api_key=None)
        
        pattern = create_sample_pattern()
        analysis = alert_system._generate_fallback_analysis(pattern, 'BTCUSDT')
        
        print(f"\n[FALLBACK ANALYSIS]:")
        print(analysis)
        
        if analysis and len(analysis) > 50:
            print("\n[PASS] Fallback analysis generated successfully")
            return True
        else:
            print("\n[FAIL] Fallback analysis too short or empty")
            return False
            
    except Exception as e:
        print(f"[FAIL] Fallback analysis failed: {e}")
        return False


def test_ai_analysis():
    """Test AI-powered analysis with DeepSeek"""
    print("\n" + "="*80)
    print("TEST: AI Analysis (DeepSeek)")
    print("="*80)
    
    # Check if API key is available
    api_key = os.getenv('DEEPSEEK_KEY')
    if not api_key:
        print("[SKIP] No DEEPSEEK_KEY environment variable set")
        print("[INFO] Set DEEPSEEK_KEY to test AI analysis")
        return True  # Skip but don't fail
    
    try:
        alert_system = AlertSystem(deepseek_api_key=api_key)
        
        if not alert_system.ai_enabled:
            print("[SKIP] AI not enabled")
            return True
        
        pattern = create_sample_pattern()
        
        print("\n[TEST] Generating AI analysis...")
        analysis = alert_system.generate_ai_analysis(pattern, 'BTCUSDT')
        
        print(f"\n[AI ANALYSIS]:")
        print(analysis)
        
        # Verify analysis quality
        if analysis and len(analysis) > 100:
            print("\n[PASS] AI analysis generated successfully")
            return True
        else:
            print("\n[FAIL] AI analysis too short or empty")
            return False
            
    except Exception as e:
        print(f"[FAIL] AI analysis failed: {e}")
        return False


def test_console_alert():
    """Test console alert output"""
    print("\n" + "="*80)
    print("TEST: Console Alert")
    print("="*80)
    
    try:
        alert_system = AlertSystem(deepseek_api_key=None, enable_desktop_notifications=False)
        
        pattern = create_sample_pattern()
        analysis = alert_system._generate_fallback_analysis(pattern, 'ETHUSDT')
        
        print("\n[TEST] Printing console alert...")
        alert_system._print_console_alert(pattern, 'ETHUSDT', analysis)
        
        print("[PASS] Console alert displayed successfully")
        return True
        
    except Exception as e:
        print(f"[FAIL] Console alert failed: {e}")
        return False


def test_complete_alert():
    """Test complete alert flow"""
    print("\n" + "="*80)
    print("TEST: Complete Alert Flow")
    print("="*80)
    
    try:
        alert_system = AlertSystem(enable_desktop_notifications=False)
        
        pattern = create_sample_pattern()
        
        print("\n[TEST] Sending complete alert...")
        result = alert_system.send_alert(pattern, 'SOLUSDT', include_ai_analysis=True)
        
        # Verify result structure
        if (result and 
            'symbol' in result and
            'pattern_data' in result and
            'ai_analysis' in result and
            'alert_timestamp' in result):
            print("\n[PASS] Complete alert sent successfully")
            print(f"[INFO] Alert timestamp: {result['alert_timestamp']}")
            return True
        else:
            print("\n[FAIL] Alert result structure invalid")
            return False
            
    except Exception as e:
        print(f"[FAIL] Complete alert failed: {e}")
        return False


def test_desktop_notification():
    """Test desktop notification (if available)"""
    print("\n" + "="*80)
    print("TEST: Desktop Notification")
    print("="*80)
    
    try:
        from alert_system import PLYER_AVAILABLE
        
        if not PLYER_AVAILABLE:
            print("[SKIP] Plyer not available (desktop notifications disabled)")
            return True
        
        alert_system = AlertSystem(enable_desktop_notifications=True)
        
        pattern = create_sample_pattern()
        analysis = alert_system._generate_fallback_analysis(pattern, 'BNBUSDT')
        
        print("\n[TEST] Sending desktop notification...")
        alert_system.send_desktop_notification(pattern, 'BNBUSDT', analysis)
        
        print("[PASS] Desktop notification sent (check your system)")
        print("[INFO] You should see a notification on your desktop")
        return True
        
    except Exception as e:
        print(f"[FAIL] Desktop notification failed: {e}")
        return False


def test_multiple_patterns():
    """Test handling multiple pattern alerts"""
    print("\n" + "="*80)
    print("TEST: Multiple Pattern Alerts")
    print("="*80)
    
    try:
        alert_system = AlertSystem(enable_desktop_notifications=False)
        
        # Create different patterns
        patterns = [
            {'name': 'hammer', 'symbol': 'BTCUSDT', 'direction': 'long'},
            {'name': 'doji', 'symbol': 'ETHUSDT', 'direction': 'short'},
            {'name': 'morning_star', 'symbol': 'SOLUSDT', 'direction': 'long'}
        ]
        
        results = []
        for p in patterns:
            pattern = create_sample_pattern()
            pattern['pattern'] = p['name']
            pattern['direction'] = p['direction']
            pattern['signal'] = 100 if p['direction'] == 'long' else -100
            
            result = alert_system.send_alert(pattern, p['symbol'], include_ai_analysis=False)
            results.append(result)
        
        if len(results) == len(patterns):
            print(f"\n[PASS] Successfully sent {len(results)} alerts")
            return True
        else:
            print(f"\n[FAIL] Only sent {len(results)}/{len(patterns)} alerts")
            return False
            
    except Exception as e:
        print(f"[FAIL] Multiple alerts failed: {e}")
        return False


def run_all_tests():
    """Run all alert system tests"""
    print("\n" + "#"*80)
    print("# ALERT SYSTEM TEST SUITE")
    print("# Testing DeepSeek AI Integration and Notifications")
    print("#"*80)
    
    tests = [
        ("Alert System Initialization", test_alert_system_init),
        ("Fallback Analysis", test_fallback_analysis),
        ("AI Analysis (DeepSeek)", test_ai_analysis),
        ("Console Alert", test_console_alert),
        ("Complete Alert Flow", test_complete_alert),
        ("Desktop Notification", test_desktop_notification),
        ("Multiple Pattern Alerts", test_multiple_patterns)
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

