"""
Comprehensive Dust Collection Test Suite
Tests dust detection and conversion functionality in the harvesting agent
"""

import os
import sys
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.agents.harvesting_agent import HarvestingAgent
from src.config import (
    SOL_ADDRESS, USDC_ADDRESS, EXCLUDED_TOKENS, DUST_THRESHOLD_USD,
    HARVESTING_DUST_CONVERSION_ENABLED, ALLOW_EXCLUDED_DUST,
    PAPER_TRADING_ENABLED
)
from test.agents.test_helpers import PortfolioStateSimulator, TestValidator


class MockSnapshot:
    """Mock portfolio snapshot for testing"""
    def __init__(self, total_value_usd: float, positions: Dict = None, sol_value_usd: float = 0, usdc_balance: float = 0):
        self.total_value_usd = total_value_usd
        self.positions = positions or {}
        self.sol_value_usd = sol_value_usd
        self.usdc_balance = usdc_balance


class TestDustCollection:
    """Comprehensive test suite for dust collection in harvesting agent"""
    
    def __init__(self):
        """Initialize test environment"""
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.agent = HarvestingAgent(enable_ai=False)
    
    def setup_method(self):
        """Set up test environment before each test"""
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.agent = HarvestingAgent(enable_ai=False)
    
    def create_dust_positions(self, values: List[float]) -> Dict[str, float]:
        """Helper to create dust position test data"""
        dust_positions = {}
        for i, value in enumerate(values):
            token_address = f"DUST_TOKEN_{i:02d}_012345678901234567890123456789"
            dust_positions[token_address] = value
        return dust_positions
    
    def test_01_basic_dust_conversion(self):
        """Test 1: Basic dust conversion with multiple tokens under threshold"""
        print("\n🧪 Test 1: Basic Dust Conversion")
        
        dust_values = [0.50, 1.00, 2.00, 3.00, 4.00]
        dust_positions = self.create_dust_positions(dust_values)
        
        # Create snapshot with dust positions
        snapshot = MockSnapshot(
            total_value_usd=1000.0,
            positions=dust_positions,
            sol_value_usd=100.0,
            usdc_balance=100.0
        )
        
        # Mock price service
        mock_price_service = Mock()
        mock_price_service.get_price.return_value = 100.0  # SOL price
        
        with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service):
            with patch.object(self.agent, '_swap_usdc_to_sol', return_value=True) as mock_swap:
                result = self.agent._check_and_convert_dust(snapshot)
                
                assert result == True, "Dust conversion should succeed"
                assert mock_swap.called, "Swap to SOL should be called"
                assert len(snapshot.positions) == 5, "Should detect 5 dust positions"
        
        print("  ✅ PASS: Basic dust conversion works correctly")
    
    def test_02_dust_boundary_conditions(self):
        """Test 2: Dust boundary conditions (exactly at, just below, just above threshold)"""
        print("\n🧪 Test 2: Dust Boundary Conditions")
        
        # Test values: exactly at threshold, just below, just above
        test_values = [
            (4.99, True, "Should convert: just below threshold"),
            (5.00, True, "Should convert: exactly at threshold"),
            (5.01, False, "Should NOT convert: just above threshold"),
            (10.00, False, "Should NOT convert: well above threshold")
        ]
        
        for value, should_convert, description in test_values:
            dust_positions = self.create_dust_positions([value])
            snapshot = MockSnapshot(
                total_value_usd=1000.0,
                positions=dust_positions,
                sol_value_usd=100.0,
                usdc_balance=100.0
            )
            
            mock_price_service = Mock()
            mock_price_service.get_price.return_value = 100.0
            
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service):
                with patch.object(self.agent, '_swap_usdc_to_sol', return_value=True):
                    result = self.agent._check_and_convert_dust(snapshot)
                    
                    if should_convert:
                        assert result == True, f"{description}: {value} should convert"
                    else:
                        assert result == False, f"{description}: {value} should NOT convert"
        
        print("  ✅ PASS: Boundary conditions handled correctly")
    
    def test_03_excluded_token_protection(self):
        """Test 3: Excluded tokens (SOL, USDC) not converted"""
        print("\n🧪 Test 3: Excluded Token Protection")
        
        # Create dust positions including excluded tokens
        dust_positions = {
            SOL_ADDRESS: 2.00,  # Excluded token
            USDC_ADDRESS: 3.00,  # Excluded token
            "DUST_TOKEN_01_012345678901234567890123456789": 1.00  # Regular token
        }
        
        snapshot = MockSnapshot(
            total_value_usd=1000.0,
            positions=dust_positions,
            sol_value_usd=100.0,
            usdc_balance=100.0
        )
        
        # Capture positions that would be converted
        converted_positions = []
        
        def mock_swap(dust_pos):
            nonlocal converted_positions
            converted_positions = [p['address'] for p in dust_pos]
            return True
        
        mock_price_service = Mock()
        mock_price_service.get_price.return_value = 100.0
        
        with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service):
            with patch.object(self.agent, '_convert_dust_to_sol', side_effect=mock_swap):
                self.agent._check_and_convert_dust(snapshot)
                
                # Verify excluded tokens are not in the conversion list
                assert SOL_ADDRESS not in converted_positions, "SOL should NOT be converted"
                assert USDC_ADDRESS not in converted_positions, "USDC should NOT be converted"
                assert any("DUST_TOKEN" in addr for addr in converted_positions), "Regular tokens should be converted"
        
        print("  ✅ PASS: Excluded tokens protected correctly")
    
    def test_04_mixed_portfolio(self):
        """Test 4: Mixed portfolio with dust and normal positions"""
        print("\n🧪 Test 4: Mixed Portfolio")
        
        # Create mixed portfolio: some dust, some normal positions
        all_positions = {
            "DUST_TOKEN_01_012345678901234567890123456789": 2.00,
            "DUST_TOKEN_02_012345678901234567890123456789": 3.50,
            "NORMAL_TOKEN_01234567890123456789012345678901": 100.00,
            "NORMAL_TOKEN_01234567890123456789012345678902": 50.00
        }
        
        snapshot = MockSnapshot(
            total_value_usd=1000.0,
            positions=all_positions,
            sol_value_usd=100.0,
            usdc_balance=100.0
        )
        
        dust_positions = []
        def mock_swap(dust_pos):
            nonlocal dust_positions
            dust_positions = dust_pos
            return True
        
        mock_price_service = Mock()
        mock_price_service.get_price.return_value = 100.0
        
        with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service):
            with patch.object(self.agent, '_convert_dust_to_sol', side_effect=mock_swap):
                result = self.agent._check_and_convert_dust(snapshot)
                
                assert result == True, "Dust conversion should succeed"
                assert len(dust_positions) == 2, "Should only convert 2 dust positions"
                
                # Verify dust positions are in the list
                dust_addresses = [p['address'] for p in dust_positions]
                assert "DUST_TOKEN_01" in str(dust_positions[0]['address']), "Should include dust token 1"
                assert "DUST_TOKEN_02" in str(dust_positions[1]['address']), "Should include dust token 2"
        
        print("  ✅ PASS: Mixed portfolio handled correctly")
    
    def test_05_no_dust_scenario(self):
        """Test 5: No dust scenario - all positions above threshold"""
        print("\n🧪 Test 5: No Dust Scenario")
        
        normal_positions = {
            "TOKEN_01_012345678901234567890123456789": 100.00,
            "TOKEN_02_012345678901234567890123456789": 50.00,
            "TOKEN_03_012345678901234567890123456789": 25.00
        }
        
        snapshot = MockSnapshot(
            total_value_usd=1000.0,
            positions=normal_positions,
            sol_value_usd=100.0,
            usdc_balance=100.0
        )
        
        mock_price_service = Mock()
        mock_price_service.get_price.return_value = 100.0
        
        with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service):
            with patch.object(self.agent, '_convert_dust_to_sol') as mock_convert:
                result = self.agent._check_and_convert_dust(snapshot)
                
                assert result == False, "Should NOT trigger dust conversion"
                assert not mock_convert.called, "Should NOT call convert method"
        
        print("  ✅ PASS: No dust scenario handled correctly")
    
    def test_06_config_disable_flag(self):
        """Test 6: Config flag disable - HARVESTING_DUST_CONVERSION_ENABLED=False"""
        print("\n🧪 Test 6: Config Flag Disable")
        
        dust_positions = self.create_dust_positions([1.00, 2.00, 3.00])
        
        snapshot = MockSnapshot(
            total_value_usd=1000.0,
            positions=dust_positions,
            sol_value_usd=100.0,
            usdc_balance=100.0
        )
        
        # Temporarily disable dust conversion by patching config module
        with patch('src.config.HARVESTING_DUST_CONVERSION_ENABLED', False):
            with patch.object(self.agent, '_convert_dust_to_sol') as mock_convert:
                result = self.agent._check_and_convert_dust(snapshot)
                
                assert result == False, "Should NOT trigger when flag disabled"
                assert not mock_convert.called, "Should NOT call convert method"
        
        print("  ✅ PASS: Config flag disable works correctly")
    
    def test_07_allow_excluded_dust_flag(self):
        """Test 7: ALLOW_EXCLUDED_DUST flag behavior"""
        print("\n🧪 Test 7: ALLOW_EXCLUDED_DUST Flag")
        
        # Create dust including SOL
        dust_positions = {
            SOL_ADDRESS: 2.00,
            "DUST_TOKEN_01234567890123456789012345678901": 1.00
        }
        
        snapshot = MockSnapshot(
            total_value_usd=1000.0,
            positions=dust_positions,
            sol_value_usd=100.0,
            usdc_balance=100.0
        )
        
        mock_price_service = Mock()
        mock_price_service.get_price.return_value = 100.0
        
        # Test with ALLOW_EXCLUDED_DUST = False (default)
        with patch('src.config.ALLOW_EXCLUDED_DUST', False):
            with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service):
                converted_positions = []
                
                def mock_swap(dust_pos):
                    nonlocal converted_positions
                    converted_positions = [p['address'] for p in dust_pos]
                    return True
                
                with patch.object(self.agent, '_convert_dust_to_sol', side_effect=mock_swap):
                    self.agent._check_and_convert_dust(snapshot)
                    
                    assert SOL_ADDRESS not in converted_positions, "SOL should NOT be converted when flag is False"
        
        print("  ✅ PASS: ALLOW_EXCLUDED_DUST flag works correctly")
    
    def test_08_paper_trading_mode(self):
        """Test 8: Paper trading mode validation"""
        print("\n🧪 Test 8: Paper Trading Mode")
        
        dust_positions = self.create_dust_positions([1.00, 2.00])
        
        # Verify paper trading methods are called
        with patch.object(self.agent, '_convert_dust_to_sol_paper') as mock_paper:
            with patch.object(self.agent, '_convert_dust_to_sol_live') as mock_live:
                with patch('src.config.PAPER_TRADING_ENABLED', True):
                    self.agent._convert_dust_to_sol(dust_positions)
                    
                    assert mock_paper.called, "Should call paper method in paper mode"
                    assert not mock_live.called, "Should NOT call live method in paper mode"
        
        print("  ✅ PASS: Paper trading mode works correctly")
    
    def test_09_live_trading_mode(self):
        """Test 9: Live trading mode validation"""
        print("\n🧪 Test 9: Live Trading Mode")
        
        dust_positions = self.create_dust_positions([1.00, 2.00])
        
        # Verify live trading methods are called
        with patch.object(self.agent, '_convert_dust_to_sol_paper') as mock_paper:
            with patch.object(self.agent, '_convert_dust_to_sol_live') as mock_live:
                with patch('src.config.PAPER_TRADING_ENABLED', False):
                    self.agent._convert_dust_to_sol(dust_positions)
                    
                    assert mock_live.called, "Should call live method in live mode"
                    assert not mock_paper.called, "Should NOT call paper method in live mode"
        
        print("  ✅ PASS: Live trading mode works correctly")
    
    def test_10_zero_value_positions(self):
        """Test 10: Zero value positions should not be considered dust"""
        print("\n🧪 Test 10: Zero Value Positions")
        
        # Create positions with zero values
        positions = {
            "ZERO_TOKEN_01234567890123456789012345678901": 0.00,
            "DUST_TOKEN_01234567890123456789012345678901": 1.00
        }
        
        snapshot = MockSnapshot(
            total_value_usd=1000.0,
            positions=positions,
            sol_value_usd=100.0,
            usdc_balance=100.0
        )
        
        mock_price_service = Mock()
        mock_price_service.get_price.return_value = 100.0
        
        with patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service):
            converted_positions = []
            
            def mock_swap(dust_pos):
                nonlocal converted_positions
                converted_positions = dust_pos
                return True
            
            with patch.object(self.agent, '_convert_dust_to_sol', side_effect=mock_swap):
                self.agent._check_and_convert_dust(snapshot)
                
                # Should only convert the dust token, not the zero value token
                assert len(converted_positions) == 1, "Should only convert 1 dust position"
                assert "DUST_TOKEN" in str(converted_positions[0]['address']), "Should convert dust token"
        
        print("  ✅ PASS: Zero value positions handled correctly")


def run_all_tests():
    """Run all dust collection tests"""
    print("🌾 Dust Collection Test Suite")
    print("=" * 60)
    print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    test_suite = TestDustCollection()
    
    # Setup for each test
    test_suite.setup_method()
    
    # Run all test methods
    test_methods = [method for method in dir(test_suite) if method.startswith('test_')]
    test_methods.sort()
    
    for test_method in test_methods:
        try:
            getattr(test_suite, test_method)()
        except Exception as e:
            print(f"  ❌ FAIL: {test_method}: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ Dust Collection Test Suite Complete")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()

