"""
Comprehensive test runner for harvesting agent production readiness
"""

import os
import sys
import time
from typing import List, Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_harvesting_scenarios import TestHarvestingScenarios
from test.agents.test_harvesting_stress import TestHarvestingStress
from test.agents.test_harvesting_error_recovery import TestHarvestingErrorRecovery
from test.agents.test_harvesting_integration import TestHarvestingIntegration
from test.agents.test_helpers import TestValidator

class ComprehensiveHarvestingTestRunner:
    """Comprehensive test runner for harvesting agent"""
    
    def __init__(self):
        self.validator = TestValidator()
        self.all_results = []
    
    def run_comprehensive_test_suite(self) -> List[Dict[str, Any]]:
        """Run the comprehensive test suite"""
        print("🚀 Starting Comprehensive Harvesting Agent Test Suite")
        print("=" * 80)
        print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Run scenario tests (15 tests)
        print("\n" + "="*60)
        print("🌾 HARVESTING SCENARIO TESTS")
        print("="*60)
        scenario_tests = TestHarvestingScenarios()
        scenario_results = scenario_tests.run_all_tests()
        self.all_results.extend(scenario_results)
        
        # Run stress tests (4 tests)
        print("\n" + "="*60)
        print("💪 HARVESTING STRESS TESTS")
        print("="*60)
        stress_tests = TestHarvestingStress()
        stress_results = stress_tests.run_all_tests()
        self.all_results.extend(stress_results)
        
        # Run error recovery tests (8 tests)
        print("\n" + "="*60)
        print("🛡️ HARVESTING ERROR RECOVERY TESTS")
        print("="*60)
        error_tests = TestHarvestingErrorRecovery()
        error_results = error_tests.run_all_tests()
        self.all_results.extend(error_results)
        
        # Run integration tests (4 tests)
        print("\n" + "="*60)
        print("🤝 HARVESTING INTEGRATION TESTS")
        print("="*60)
        integration_tests = TestHarvestingIntegration()
        integration_results = integration_tests.run_all_tests()
        self.all_results.extend(integration_results)
        
        # Generate comprehensive report
        self.generate_comprehensive_report()
        
        return self.all_results
    
    def generate_comprehensive_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE HARVESTING AGENT TEST REPORT")
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
        scenario_results = [r for r in self.all_results if 'scenario' in r.get('name', '').lower() or 
                          any(keyword in r.get('name', '').lower() for keyword in 
                              ['dust', 'gains', 'threshold', 'wallet', 'negative', 'jupiter', 'price', 'database', 'rapid'])]
        stress_results = [r for r in self.all_results if 'stress' in r.get('name', '').lower() or
                         any(keyword in r.get('name', '').lower() for keyword in 
                             ['large', 'rapid', 'extreme', 'integrity'])]
        error_results = [r for r in self.all_results if 'error' in r.get('name', '').lower() or
                        any(keyword in r.get('name', '').lower() for keyword in 
                            ['failed', 'timeout', 'corrupted', 'insufficient', 'configuration'])]
        integration_results = [r for r in self.all_results if 'integration' in r.get('name', '').lower() or
                              any(keyword in r.get('name', '').lower() for keyword in 
                                  ['portfolio', 'rebalancing', 'risk', 'workflow'])]
        
        print(f"\n📈 Results by Category:")
        print(f"  Scenario Tests: {sum(1 for r in scenario_results if r['passed'])}/{len(scenario_results)} passed")
        print(f"  Stress Tests: {sum(1 for r in stress_results if r['passed'])}/{len(stress_results)} passed")
        print(f"  Error Recovery Tests: {sum(1 for r in error_results if r['passed'])}/{len(error_results)} passed")
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
            print(f"\n🎉 ALL TESTS PASSED! The harvesting agent is production ready.")
        elif success_rate >= 95:
            print(f"\n✅ Excellent test results ({success_rate:.1f}%). Minor issues need attention.")
        elif success_rate >= 90:
            print(f"\n✅ Good test results ({success_rate:.1f}%). Some issues need fixing.")
        elif success_rate >= 80:
            print(f"\n⚠️  Moderate test results ({success_rate:.1f}%). Several issues need attention.")
        else:
            print(f"\n❌ Poor test results ({success_rate:.1f}%). Significant issues need fixing.")
        
        # Production readiness assessment
        self.assess_production_readiness(success_rate, failed_tests_list)
    
    def assess_production_readiness(self, success_rate: float, failed_tests: List[Dict]):
        """Assess production readiness based on test results"""
        print(f"\n🏭 PRODUCTION READINESS ASSESSMENT")
        print("=" * 50)
        
        # Core functionality tests
        core_tests = [r for r in self.all_results if any(keyword in r.get('name', '').lower() 
                    for keyword in ['dust conversion', 'realized gains', 'external wallet'])]
        core_success_rate = (sum(1 for r in core_tests if r['passed']) / len(core_tests) * 100) if core_tests else 0
        
        # Error handling tests
        error_tests = [r for r in self.all_results if any(keyword in r.get('name', '').lower() 
                    for keyword in ['failed', 'timeout', 'corrupted', 'error'])]
        error_success_rate = (sum(1 for r in error_tests if r['passed']) / len(error_tests) * 100) if error_tests else 0
        
        # Integration tests
        integration_tests = [r for r in self.all_results if any(keyword in r.get('name', '').lower() 
                          for keyword in ['integration', 'coordination', 'workflow'])]
        integration_success_rate = (sum(1 for r in integration_tests if r['passed']) / len(integration_tests) * 100) if integration_tests else 0
        
        print(f"Core Functionality: {core_success_rate:.1f}%")
        print(f"Error Handling: {error_success_rate:.1f}%")
        print(f"Integration: {integration_success_rate:.1f}%")
        print(f"Overall Success Rate: {success_rate:.1f}%")
        
        # Production readiness criteria
        core_ready = core_success_rate >= 90
        error_ready = error_success_rate >= 80
        integration_ready = integration_success_rate >= 80
        overall_ready = success_rate >= 90
        
        print(f"\n📋 Production Readiness Criteria:")
        print(f"  Core Functionality: {'✅ READY' if core_ready else '❌ NOT READY'}")
        print(f"  Error Handling: {'✅ READY' if error_ready else '❌ NOT READY'}")
        print(f"  Integration: {'✅ READY' if integration_ready else '❌ NOT READY'}")
        print(f"  Overall: {'✅ READY' if overall_ready else '❌ NOT READY'}")
        
        # Final recommendation
        if core_ready and error_ready and integration_ready and overall_ready:
            print(f"\n🚀 RECOMMENDATION: GO FOR PRODUCTION")
            print("   The harvesting agent has passed all production readiness tests.")
        elif core_ready and overall_ready:
            print(f"\n⚠️  RECOMMENDATION: CONDITIONAL GO")
            print("   Core functionality works, but some error handling or integration issues exist.")
        else:
            print(f"\n❌ RECOMMENDATION: NO GO")
            print("   Significant issues need to be resolved before production deployment.")
    
    def save_results_to_file(self, filename: str = "harvesting_test_results.json"):
        """Save test results to file"""
        import json
        
        results_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_tests': len(self.all_results),
            'passed_tests': sum(1 for r in self.all_results if r.get('passed', False)),
            'failed_tests': sum(1 for r in self.all_results if not r.get('passed', False)),
            'success_rate': (sum(1 for r in self.all_results if r.get('passed', False)) / len(self.all_results) * 100) if self.all_results else 0,
            'results': self.all_results
        }
        
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n💾 Test results saved to: {filepath}")


def main():
    """Main entry point"""
    runner = ComprehensiveHarvestingTestRunner()
    
    try:
        results = runner.run_comprehensive_test_suite()
        
        # Save results
        runner.save_results_to_file()
        
        # Return exit code based on results
        failed_count = sum(1 for r in results if not r.get('passed', False))
        exit_code = 0 if failed_count == 0 else 1
        
        print(f"\n🏁 Comprehensive test suite completed with exit code: {exit_code}")
        return exit_code
        
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
