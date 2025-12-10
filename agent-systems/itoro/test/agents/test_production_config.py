"""
Production configuration validator for rebalancing agent
Verifies all safety mechanisms and configuration parameters
"""

import os
import sys
from unittest.mock import patch, Mock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_helpers import TestValidator
from src.config import (
    PAPER_TRADING_ENABLED, SOL_TARGET_PERCENT, USDC_TARGET_PERCENT,
    SOL_MINIMUM_PERCENT, SOL_MAXIMUM_PERCENT, USDC_EMERGENCY_PERCENT,
    MIN_CONVERSION_USD, REBALANCING_ENABLED, SOL_ADDRESS, USDC_ADDRESS
)

class TestProductionConfig:
    """Production configuration validator"""
    
    def __init__(self):
        self.validator = TestValidator()
        self.test_results = []
    
    def run_all_config_tests(self):
        """Run all configuration validation tests"""
        print("Running Production Configuration Validation...")
        print("=" * 50)
        
        # Test 1: Safety Thresholds
        self.test_safety_thresholds()
        
        # Test 2: Paper Trading Mode
        self.test_paper_trading_mode()
        
        # Test 3: Configuration Bounds
        self.test_configuration_bounds()
        
        # Test 4: Address Validation
        self.test_address_validation()
        
        # Test 5: Emergency Parameters
        self.test_emergency_parameters()
        
        # Generate report
        report = self.validator.generate_test_report(self.test_results)
        print(report)
        
        return self.test_results
    
    def test_safety_thresholds(self):
        """Test 1: Safety Thresholds"""
        test_name = "Safety Thresholds"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test SOL minimum < target < maximum
            sol_min_valid = SOL_MINIMUM_PERCENT < SOL_TARGET_PERCENT < SOL_MAXIMUM_PERCENT
            
            # Test USDC emergency < target
            usdc_emergency_valid = USDC_EMERGENCY_PERCENT < USDC_TARGET_PERCENT
            
            # Test minimum conversion amount is reasonable
            min_conversion_valid = 0 < MIN_CONVERSION_USD < 100  # Between $0 and $100
            
            # Test percentages sum to 100
            percentages_sum_valid = abs((SOL_TARGET_PERCENT + USDC_TARGET_PERCENT) - 100) < 0.1
            
            success = (sol_min_valid and usdc_emergency_valid and 
                      min_conversion_valid and percentages_sum_valid)
            
            print(f"SOL min < target < max: {sol_min_valid}")
            print(f"USDC emergency < target: {usdc_emergency_valid}")
            print(f"Min conversion reasonable: {min_conversion_valid}")
            print(f"Percentages sum to 100: {percentages_sum_valid}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'sol_min_valid': sol_min_valid,
                    'usdc_emergency_valid': usdc_emergency_valid,
                    'min_conversion_valid': min_conversion_valid,
                    'percentages_sum_valid': percentages_sum_valid
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_paper_trading_mode(self):
        """Test 2: Paper Trading Mode"""
        test_name = "Paper Trading Mode"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test paper trading is enabled
            paper_trading_enabled = PAPER_TRADING_ENABLED
            
            # Test rebalancing is enabled
            rebalancing_enabled = REBALANCING_ENABLED
            
            success = paper_trading_enabled and rebalancing_enabled
            
            print(f"Paper trading enabled: {paper_trading_enabled}")
            print(f"Rebalancing enabled: {rebalancing_enabled}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'paper_trading_enabled': paper_trading_enabled,
                    'rebalancing_enabled': rebalancing_enabled
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_configuration_bounds(self):
        """Test 3: Configuration Bounds"""
        test_name = "Configuration Bounds"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test SOL target is reasonable (5-20%)
            sol_target_reasonable = 5 <= SOL_TARGET_PERCENT <= 20
            
            # Test USDC target is reasonable (80-95%)
            usdc_target_reasonable = 80 <= USDC_TARGET_PERCENT <= 95
            
            # Test SOL minimum is reasonable (1-10%)
            sol_min_reasonable = 1 <= SOL_MINIMUM_PERCENT <= 10
            
            # Test SOL maximum is reasonable (15-30%)
            sol_max_reasonable = 15 <= SOL_MAXIMUM_PERCENT <= 30
            
            # Test USDC emergency is reasonable (5-20%)
            usdc_emergency_reasonable = 5 <= USDC_EMERGENCY_PERCENT <= 20
            
            success = (sol_target_reasonable and usdc_target_reasonable and 
                      sol_min_reasonable and sol_max_reasonable and 
                      usdc_emergency_reasonable)
            
            print(f"SOL target reasonable (5-20%): {sol_target_reasonable}")
            print(f"USDC target reasonable (80-95%): {usdc_target_reasonable}")
            print(f"SOL min reasonable (1-10%): {sol_min_reasonable}")
            print(f"SOL max reasonable (15-30%): {sol_max_reasonable}")
            print(f"USDC emergency reasonable (5-20%): {usdc_emergency_reasonable}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'sol_target_reasonable': sol_target_reasonable,
                    'usdc_target_reasonable': usdc_target_reasonable,
                    'sol_min_reasonable': sol_min_reasonable,
                    'sol_max_reasonable': sol_max_reasonable,
                    'usdc_emergency_reasonable': usdc_emergency_reasonable
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_address_validation(self):
        """Test 4: Address Validation"""
        test_name = "Address Validation"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test SOL address is valid (44 characters, starts with specific prefix)
            sol_address_valid = (isinstance(SOL_ADDRESS, str) and 
                               len(SOL_ADDRESS) == 44 and 
                               SOL_ADDRESS.startswith('So'))
            
            # Test USDC address is valid (44 characters, starts with specific prefix)
            usdc_address_valid = (isinstance(USDC_ADDRESS, str) and 
                                len(USDC_ADDRESS) == 44 and 
                                USDC_ADDRESS.startswith('EPj'))
            
            # Test addresses are different
            addresses_different = SOL_ADDRESS != USDC_ADDRESS
            
            success = sol_address_valid and usdc_address_valid and addresses_different
            
            print(f"SOL address valid: {sol_address_valid}")
            print(f"USDC address valid: {usdc_address_valid}")
            print(f"Addresses different: {addresses_different}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'sol_address_valid': sol_address_valid,
                    'usdc_address_valid': usdc_address_valid,
                    'addresses_different': addresses_different
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })
    
    def test_emergency_parameters(self):
        """Test 5: Emergency Parameters"""
        test_name = "Emergency Parameters"
        print(f"\n{test_name}")
        print("-" * 30)
        
        try:
            # Test emergency thresholds are conservative
            usdc_emergency_conservative = USDC_EMERGENCY_PERCENT <= 15  # 15% or less
            
            # Test minimum conversion prevents dust trades
            min_conversion_prevents_dust = MIN_CONVERSION_USD >= 5  # At least $5
            
            # Test SOL minimum prevents complete depletion
            sol_min_prevents_depletion = SOL_MINIMUM_PERCENT >= 1  # At least 1%
            
            # Test SOL maximum prevents overexposure
            sol_max_prevents_overexposure = SOL_MAXIMUM_PERCENT <= 25  # At most 25%
            
            success = (usdc_emergency_conservative and min_conversion_prevents_dust and 
                      sol_min_prevents_depletion and sol_max_prevents_overexposure)
            
            print(f"USDC emergency conservative (≤15%): {usdc_emergency_conservative}")
            print(f"Min conversion prevents dust (≥$5): {min_conversion_prevents_dust}")
            print(f"SOL min prevents depletion (≥1%): {sol_min_prevents_depletion}")
            print(f"SOL max prevents overexposure (≤25%): {sol_max_prevents_overexposure}")
            print(f"Result: {'PASS' if success else 'FAIL'}")
            
            self.test_results.append({
                'name': test_name,
                'passed': success,
                'details': {
                    'usdc_emergency_conservative': usdc_emergency_conservative,
                    'min_conversion_prevents_dust': min_conversion_prevents_dust,
                    'sol_min_prevents_depletion': sol_min_prevents_depletion,
                    'sol_max_prevents_overexposure': sol_max_prevents_overexposure
                }
            })
            
        except Exception as e:
            print(f"Error: {e}")
            self.test_results.append({
                'name': test_name,
                'passed': False,
                'error': str(e)
            })


if __name__ == "__main__":
    # Run config tests when script is executed directly
    config_tests = TestProductionConfig()
    results = config_tests.run_all_config_tests()
    
    # Print summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nSummary: {passed}/{total} config tests passed")
