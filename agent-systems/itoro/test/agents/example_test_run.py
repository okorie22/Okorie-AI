#!/usr/bin/env python3
"""
Example test run demonstrating the comprehensive harvesting agent tests
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def run_example_test():
    """Run a single example test to demonstrate functionality"""
    print("🧪 Running Example Harvesting Agent Test")
    print("=" * 50)
    
    try:
        # Import the test class
        from test.agents.test_harvesting_comprehensive import TestHarvestingAgentComprehensive
        
        # Create test instance
        test_instance = TestHarvestingAgentComprehensive()
        
        # Set up test environment
        test_instance.setup_method()
        
        print("✅ Test environment set up successfully")
        print(f"  → Paper trading mode: {test_instance.test_config['PAPER_TRADING_ENABLED']}")
        print(f"  → AI enabled: {test_instance.test_config['HARVESTING_AI_DECISION_ENABLED']}")
        print(f"  → Dust threshold: ${test_instance.test_config['DUST_THRESHOLD_USD']}")
        
        # Run a simple test
        print("\n🧪 Running Test: 100% SOL Startup Rebalancing")
        test_instance.test_01_startup_rebalancing_100_sol()
        
        print("\n🧪 Running Test: Dust Conversion")
        test_instance.test_07_auto_dust_conversion()
        
        print("\n🧪 Running Test: Below Threshold Gains")
        test_instance.test_15_below_threshold_gains()
        
        # Clean up
        test_instance.teardown_method()
        
        print("\n🎉 Example tests completed successfully!")
        print("\nTo run all 17 comprehensive tests:")
        print("  python test/agents/run_harvesting_comprehensive_tests.py")
        print("\nTo run with pytest:")
        print("  pytest test/agents/test_harvesting_comprehensive.py -v")
        
    except Exception as e:
        print(f"❌ Error running example test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_example_test()
