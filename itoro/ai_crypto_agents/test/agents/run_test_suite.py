"""
Main test suite runner for rebalancing and harvesting agents
"""

import os
import sys
import time
from typing import List, Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_rebalancing_scenarios import TestRebalancingScenarios
from test.agents.test_harvesting_scenarios import TestHarvestingScenarios
from test.agents.test_agent_integration import TestAgentIntegration
from test.agents.test_helpers import TestValidator

class TestSuiteRunner:
    """Main test suite runner"""
    
    def __init__(self):
        self.validator = TestValidator()
        self.all_results = []
    
    def run_complete_test_suite(self) -> List[Dict[str, Any]]:
        """Run the complete test suite"""
        print("🚀 Starting Complete Test Suite for Rebalancing & Harvesting Agents")
        print("=" * 80)
        print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Run rebalancing agent tests
        print("\n" + "="*60)
        print("⚖️ REBALANCING AGENT TESTS")
        print("="*60)
        rebalancing_tests = TestRebalancingScenarios()
        rebalancing_results = rebalancing_tests.run_all_tests()
        self.all_results.extend(rebalancing_results)
        
        # Run harvesting agent tests
        print("\n" + "="*60)
        print("🌾 HARVESTING AGENT TESTS")
        print("="*60)
        harvesting_tests = TestHarvestingScenarios()
        harvesting_results = harvesting_tests.run_all_tests()
        self.all_results.extend(harvesting_results)
        
        # Run comprehensive harvesting agent tests
        print("\n" + "="*60)
        print("🌾 COMPREHENSIVE HARVESTING AGENT TESTS")
        print("="*60)
        try:
            import subprocess
            import sys
            
            # Run comprehensive tests with pytest
            cmd = [sys.executable, "-m", "pytest", "test/agents/test_harvesting_comprehensive.py", "-v", "--tb=short"]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
            
            print("Comprehensive Harvesting Test Results:")
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            
            # Add to results
            comprehensive_result = {
                'test_name': 'Comprehensive Harvesting Agent Tests',
                'passed': result.returncode == 0,
                'details': result.stdout,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            self.all_results.append(comprehensive_result)
            
        except Exception as e:
            print(f"Error running comprehensive harvesting tests: {e}")
            comprehensive_result = {
                'test_name': 'Comprehensive Harvesting Agent Tests',
                'passed': False,
                'details': f"Error: {str(e)}",
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            self.all_results.append(comprehensive_result)
        
        # Run integration tests
        print("\n" + "="*60)
        print("🤝 INTEGRATION TESTS")
        print("="*60)
        integration_tests = TestAgentIntegration()
        integration_results = integration_tests.run_all_tests()
        self.all_results.extend(integration_results)
        
        # Generate comprehensive report
        self.generate_comprehensive_report()
        
        return self.all_results
    
    def generate_comprehensive_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("="*80)
        
        # Overall statistics
        total_tests = len(self.all_results)
        passed_tests = sum(1 for result in self.all_results if result.get('passed', False))
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Test completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Detailed results by category
        rebalancing_results = [r for r in self.all_results if 'rebalancing' in r.get('name', '').lower()]
        harvesting_results = [r for r in self.all_results if 'harvesting' in r.get('name', '').lower()]
        integration_results = [r for r in self.all_results if 'integration' in r.get('name', '').lower() or 'coordination' in r.get('name', '').lower()]
        
        print(f"\n📈 Results by Category:")
        print(f"  Rebalancing Tests: {sum(1 for r in rebalancing_results if r['passed'])}/{len(rebalancing_results)} passed")
        print(f"  Harvesting Tests: {sum(1 for r in harvesting_results if r['passed'])}/{len(harvesting_results)} passed")
        print(f"  Integration Tests: {sum(1 for r in integration_results if r['passed'])}/{len(integration_results)} passed")
        
        # Failed tests analysis
        failed_tests_list = [r for r in self.all_results if not r.get('passed', False)]
        if failed_tests_list:
            print(f"\n❌ Failed Tests Analysis:")
            for i, test in enumerate(failed_tests_list, 1):
                print(f"  {i}. {test['name']}")
                if 'error' in test:
                    print(f"     Error: {test['error']}")
                if 'details' in test:
                    print(f"     Details: {test['details']}")
        
        # Success summary
        if success_rate == 100:
            print(f"\n🎉 ALL TESTS PASSED! The agents are working correctly.")
        elif success_rate >= 80:
            print(f"\n✅ Most tests passed ({success_rate:.1f}%). Review failed tests for improvements.")
        else:
            print(f"\n⚠️  Many tests failed ({success_rate:.1f}%). Significant issues need attention.")
        
        # Recommendations
        self.generate_recommendations()
    
    def generate_recommendations(self):
        """Generate recommendations based on test results"""
        print(f"\n💡 Recommendations:")
        
        failed_tests = [r for r in self.all_results if not r.get('passed', False)]
        
        if not failed_tests:
            print("  ✅ All tests passed! Your agents are working correctly.")
            print("  📝 Consider adding more edge cases and stress tests.")
            return
        
        # Analyze failure patterns
        startup_failures = [r for r in failed_tests if 'startup' in r.get('name', '').lower()]
        usdc_failures = [r for r in failed_tests if 'usdc' in r.get('name', '').lower()]
        dust_failures = [r for r in failed_tests if 'dust' in r.get('name', '').lower()]
        gains_failures = [r for r in failed_tests if 'gains' in r.get('name', '').lower()]
        cooldown_failures = [r for r in failed_tests if 'cooldown' in r.get('name', '').lower()]
        
        if startup_failures:
            print("  🔧 Startup rebalancing issues detected:")
            print("     - Check SOL target percentage configuration")
            print("     - Verify startup rebalancing logic in rebalancing_agent.py")
            print("     - Ensure proper cooldown mechanism")
        
        if usdc_failures:
            print("  🔧 USDC depletion handling issues detected:")
            print("     - Check USDC emergency threshold configuration")
            print("     - Verify position liquidation logic")
            print("     - Ensure proper USDC target percentage")
        
        if dust_failures:
            print("  🔧 Dust conversion issues detected:")
            print("     - Check dust threshold configuration")
            print("     - Verify excluded tokens handling")
            print("     - Ensure proper SOL conversion logic")
        
        if gains_failures:
            print("  🔧 Realized gains harvesting issues detected:")
            print("     - Check gains increment threshold (5%)")
            print("     - Verify reallocation percentages")
            print("     - Ensure proper external wallet handling")
        
        if cooldown_failures:
            print("  🔧 Cooldown mechanism issues detected:")
            print("     - Check cooldown duration configuration")
            print("     - Verify time tracking logic")
            print("     - Ensure proper state management")
        
        print("  📚 General recommendations:")
        print("     - Review agent configuration in src/config.py")
        print("     - Check paper trading database state")
        print("     - Verify mock services are properly configured")
        print("     - Test with different portfolio scenarios")
    
    def save_results_to_file(self, filename: str = "test_results.json"):
        """Save test results to file"""
        import json
        
        results_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_tests': len(self.all_results),
            'passed_tests': sum(1 for r in self.all_results if r.get('passed', False)),
            'failed_tests': sum(1 for r in self.all_results if not r.get('passed', False)),
            'results': self.all_results
        }
        
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n💾 Test results saved to: {filepath}")


def main():
    """Main entry point"""
    runner = TestSuiteRunner()
    
    try:
        results = runner.run_complete_test_suite()
        
        # Save results
        runner.save_results_to_file()
        
        # Return exit code based on results
        failed_count = sum(1 for r in results if not r.get('passed', False))
        exit_code = 0 if failed_count == 0 else 1
        
        print(f"\n🏁 Test suite completed with exit code: {exit_code}")
        return exit_code
        
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
