"""
Comprehensive test runner for rebalancing agent production readiness
Runs all test suites and generates production readiness report
"""

import os
import sys
import time
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_rebalancing_scenarios import TestRebalancingScenarios
from test.agents.test_rebalancing_stress import TestRebalancingStress
from test.agents.test_production_config import TestProductionConfig

class ComprehensiveTestRunner:
    """Comprehensive test runner for production readiness"""
    
    def __init__(self):
        self.start_time = time.time()
        self.results = {
            'base_tests': [],
            'edge_cases': [],
            'stress_tests': [],
            'config_tests': []
        }
        self.summary = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'success_rate': 0.0
        }
    
    def run_all_tests(self):
        """Run all test suites"""
        print("=" * 80)
        print("REBALANCING AGENT PRODUCTION READINESS TEST SUITE")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Run base test scenarios
        print("PHASE 1: Base Test Scenarios")
        print("-" * 40)
        try:
            base_suite = TestRebalancingScenarios()
            self.results['base_tests'] = base_suite.run_all_tests()
        except Exception as e:
            print(f"Error running base tests: {e}")
            self.results['base_tests'] = [{'name': 'Base Tests', 'passed': False, 'error': str(e)}]
        
        print("\n" + "=" * 80)
        
        # Run stress tests
        print("PHASE 2: Stress Tests")
        print("-" * 40)
        try:
            stress_suite = TestRebalancingStress()
            self.results['stress_tests'] = stress_suite.run_all_stress_tests()
        except Exception as e:
            print(f"Error running stress tests: {e}")
            self.results['stress_tests'] = [{'name': 'Stress Tests', 'passed': False, 'error': str(e)}]
        
        print("\n" + "=" * 80)
        
        # Run configuration tests
        print("PHASE 3: Configuration Validation")
        print("-" * 40)
        try:
            config_suite = TestProductionConfig()
            self.results['config_tests'] = config_suite.run_all_config_tests()
        except Exception as e:
            print(f"Error running config tests: {e}")
            self.results['config_tests'] = [{'name': 'Config Tests', 'passed': False, 'error': str(e)}]
        
        # Calculate summary
        self.calculate_summary()
        
        # Generate final report
        self.generate_final_report()
        
        return self.results
    
    def calculate_summary(self):
        """Calculate test summary statistics"""
        all_tests = []
        for test_type, tests in self.results.items():
            all_tests.extend(tests)
        
        self.summary['total_tests'] = len(all_tests)
        self.summary['passed_tests'] = sum(1 for test in all_tests if test.get('passed', False))
        self.summary['failed_tests'] = self.summary['total_tests'] - self.summary['passed_tests']
        
        if self.summary['total_tests'] > 0:
            self.summary['success_rate'] = (self.summary['passed_tests'] / self.summary['total_tests']) * 100
        else:
            self.summary['success_rate'] = 0.0
    
    def generate_final_report(self):
        """Generate comprehensive production readiness report"""
        end_time = time.time()
        duration = end_time - self.start_time
        
        print("\n" + "=" * 80)
        print("PRODUCTION READINESS REPORT")
        print("=" * 80)
        
        print(f"Test Duration: {duration:.2f} seconds")
        print(f"Total Tests: {self.summary['total_tests']}")
        print(f"Passed: {self.summary['passed_tests']}")
        print(f"Failed: {self.summary['failed_tests']}")
        print(f"Success Rate: {self.summary['success_rate']:.1f}%")
        print()
        
        # Detailed results by category
        print("DETAILED RESULTS BY CATEGORY:")
        print("-" * 40)
        
        for test_type, tests in self.results.items():
            if tests:
                passed = sum(1 for test in tests if test.get('passed', False))
                total = len(tests)
                rate = (passed / total * 100) if total > 0 else 0
                print(f"{test_type.replace('_', ' ').title()}: {passed}/{total} ({rate:.1f}%)")
        
        print()
        
        # Production readiness assessment
        print("PRODUCTION READINESS ASSESSMENT:")
        print("-" * 40)
        
        if self.summary['success_rate'] >= 95:
            readiness = "✅ PRODUCTION READY"
            recommendation = "GO - Deploy to production"
        elif self.summary['success_rate'] >= 85:
            readiness = "⚠️  NEARLY READY"
            recommendation = "CAUTION - Address failing tests before production"
        elif self.summary['success_rate'] >= 70:
            readiness = "❌ NOT READY"
            recommendation = "NO GO - Significant issues need resolution"
        else:
            readiness = "🚨 CRITICAL ISSUES"
            recommendation = "NO GO - Major problems require immediate attention"
        
        print(f"Status: {readiness}")
        print(f"Recommendation: {recommendation}")
        print()
        
        # Failed tests summary
        if self.summary['failed_tests'] > 0:
            print("FAILED TESTS:")
            print("-" * 40)
            for test_type, tests in self.results.items():
                for test in tests:
                    if not test.get('passed', False):
                        print(f"❌ {test_type}: {test.get('name', 'Unknown')}")
                        if 'error' in test:
                            print(f"   Error: {test['error']}")
            print()
        
        # Next steps
        print("NEXT STEPS:")
        print("-" * 40)
        if self.summary['success_rate'] >= 95:
            print("1. ✅ Deploy to production")
            print("2. ✅ Monitor initial performance")
            print("3. ✅ Set up alerting")
        elif self.summary['success_rate'] >= 85:
            print("1. 🔧 Fix failing tests")
            print("2. 🔧 Re-run test suite")
            print("3. 🔧 Review edge cases")
        else:
            print("1. 🚨 Fix critical issues")
            print("2. 🚨 Review test failures")
            print("3. 🚨 Improve error handling")
        
        print("\n" + "=" * 80)
        print("TEST SUITE COMPLETED")
        print("=" * 80)


if __name__ == "__main__":
    # Run comprehensive test suite
    runner = ComprehensiveTestRunner()
    results = runner.run_all_tests()
    
    # Exit with appropriate code
    if runner.summary['success_rate'] >= 95:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure
