#!/usr/bin/env python3
"""
Comprehensive Harvesting Agent Test Runner
Runs all 17 comprehensive harvesting agent tests with detailed output
"""

import os
import sys
import time
import subprocess
from typing import List, Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def run_comprehensive_tests() -> Dict[str, Any]:
    """Run comprehensive harvesting agent tests"""
    print("🚀 Starting Comprehensive Harvesting Agent Tests")
    print("=" * 80)
    print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Test file path
    test_file = os.path.join(os.path.dirname(__file__), "test_harvesting_comprehensive.py")
    
    # Run tests with pytest
    cmd = [
        sys.executable, "-m", "pytest", 
        test_file, 
        "-v", 
        "-s", 
        "--tb=short",
        "--durations=10"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 80)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        end_time = time.time()
        
        # Print output
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        # Parse results
        total_time = end_time - start_time
        return_code = result.returncode
        
        # Count test results from output
        lines = result.stdout.split('\n')
        passed = len([line for line in lines if 'PASS' in line and '✅' in line])
        failed = len([line for line in lines if 'FAILED' in line])
        
        print("=" * 80)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"✅ PASSED: {passed}")
        print(f"❌ FAILED: {failed}")
        print(f"⏱️  TOTAL TIME: {total_time:.1f} seconds")
        print(f"🔢 RETURN CODE: {return_code}")
        
        if return_code == 0:
            print("🎉 ALL TESTS PASSED!")
        else:
            print("💥 SOME TESTS FAILED!")
        
        return {
            'passed': passed,
            'failed': failed,
            'total_time': total_time,
            'return_code': return_code,
            'success': return_code == 0
        }
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return {
            'passed': 0,
            'failed': 0,
            'total_time': 0,
            'return_code': 1,
            'success': False,
            'error': str(e)
        }

def run_specific_test_categories():
    """Run specific test categories"""
    test_file = os.path.join(os.path.dirname(__file__), "test_harvesting_comprehensive.py")
    
    categories = [
        ("Rebalancing Tests", "rebalancing"),
        ("Dust Conversion Tests", "dust"),
        ("AI Analysis Tests", "ai"),
        ("Realized Gains Tests", "gains")
    ]
    
    print("\n" + "=" * 80)
    print("🎯 RUNNING TEST CATEGORIES")
    print("=" * 80)
    
    for category_name, keyword in categories:
        print(f"\n📋 {category_name}")
        print("-" * 40)
        
        cmd = [
            sys.executable, "-m", "pytest",
            test_file,
            "-v",
            "-k", keyword,
            "--tb=short"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
        except Exception as e:
            print(f"❌ Error running {category_name}: {e}")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--categories":
        run_specific_test_categories()
    else:
        results = run_comprehensive_tests()
        
        if not results['success']:
            sys.exit(1)

if __name__ == "__main__":
    main()
