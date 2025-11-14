"""
Test helper utilities for portfolio state manipulation and agent testing
"""

import os
import sys
import time
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from unittest.mock import Mock, patch
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import required modules
from src import paper_trading
from src.config import (
    SOL_ADDRESS, USDC_ADDRESS, EXCLUDED_TOKENS, 
    DUST_THRESHOLD_USD, SOL_TARGET_PERCENT, USDC_TARGET_PERCENT
)
from src.scripts.database.execution_tracker import get_execution_tracker
from src.scripts.utilities.error_handler import safe_execute

class MockSnapshot:
    """Mock portfolio snapshot for testing"""
    def __init__(self, total_value_usd: float, positions: Dict = None):
        self.total_value_usd = total_value_usd
        self.positions = positions or {}

class PortfolioStateSimulator:
    """Helper class for manipulating portfolio state in paper trading database"""
    
    def __init__(self):
        self.db_path = paper_trading.DB_PATH
        self.sol_price = 100.0  # Fixed SOL price for testing
        self.usdc_price = 1.0   # Fixed USDC price for testing
        
    def get_paper_trading_db(self):
        """Get paper trading database connection"""
        return paper_trading.get_paper_trading_db()
    
    def set_portfolio_state(self, sol_usd: float, usdc_usd: float, positions_usd: float, 
                           positions: Optional[Dict[str, float]] = None):
        """
        Set portfolio to specific allocation
        
        Args:
            sol_usd: SOL value in USD
            usdc_usd: USDC value in USD  
            positions_usd: Total positions value in USD
            positions: Dict of {token_address: usd_value} for specific positions
        """
        with self.get_paper_trading_db() as conn:
            # Clear existing portfolio
            conn.execute("DELETE FROM paper_portfolio")
            
            # Add SOL
            if sol_usd > 0:
                sol_amount = sol_usd / self.sol_price
                conn.execute("""
                    INSERT OR REPLACE INTO paper_portfolio (token_address, amount, last_price, last_update)
                    VALUES (?, ?, ?, ?)
                """, (SOL_ADDRESS, sol_amount, self.sol_price, int(time.time())))
            
            # Add USDC
            if usdc_usd > 0:
                usdc_amount = usdc_usd / self.usdc_price
                conn.execute("""
                    INSERT OR REPLACE INTO paper_portfolio (token_address, amount, last_price, last_update)
                    VALUES (?, ?, ?, ?)
                """, (USDC_ADDRESS, usdc_amount, self.usdc_price, int(time.time())))
            
            # Add positions
            if positions:
                for token_address, usd_value in positions.items():
                    if usd_value > 0:
                        # Use a mock price for non-SOL/USDC tokens
                        price = 0.01 if token_address not in [SOL_ADDRESS, USDC_ADDRESS] else self.sol_price
                        amount = usd_value / price
                        conn.execute("""
                            INSERT OR REPLACE INTO paper_portfolio (token_address, amount, last_price, last_update)
                            VALUES (?, ?, ?, ?)
                        """, (token_address, amount, price, int(time.time())))
            elif positions_usd > 0:
                # Create a single mock position
                mock_token = "MOCK_TOKEN_1234567890123456789012345678901234567890"
                price = 0.01
                amount = positions_usd / price
                conn.execute("""
                    INSERT OR REPLACE INTO paper_portfolio (token_address, amount, last_price, last_update)
                    VALUES (?, ?, ?, ?)
                """, (mock_token, amount, price, int(time.time())))
            
            conn.commit()
    
    def get_current_state(self) -> Dict[str, float]:
        """Get current portfolio state"""
        with self.get_paper_trading_db() as conn:
            cursor = conn.execute("SELECT token_address, amount, last_price FROM paper_portfolio")
            rows = cursor.fetchall()
            
            sol_usd = 0.0
            usdc_usd = 0.0
            positions_usd = 0.0
            positions = {}
            
            for token_address, amount, price in rows:
                usd_value = amount * price
                
                if token_address == SOL_ADDRESS:
                    sol_usd = usd_value
                elif token_address == USDC_ADDRESS:
                    usdc_usd = usd_value
                else:
                    positions_usd += usd_value
                    positions[token_address] = usd_value
            
            total_value = sol_usd + usdc_usd + positions_usd
            
            return {
                'sol_usd': sol_usd,
                'usdc_usd': usdc_usd,
                'positions_usd': positions_usd,
                'total_value': total_value,
                'sol_pct': sol_usd / total_value if total_value > 0 else 0,
                'usdc_pct': usdc_usd / total_value if total_value > 0 else 0,
                'positions_pct': positions_usd / total_value if total_value > 0 else 0,
                'positions': positions
            }
    
    def create_dust_positions(self, token_addresses: List[str], values: List[float]):
        """Create dust positions for testing"""
        positions = {}
        for token_address, value in zip(token_addresses, values):
            positions[token_address] = value
        
        # Get current state and add dust positions
        current = self.get_current_state()
        current_positions = current.get('positions', {})
        current_positions.update(positions)
        
        # Rebuild portfolio with dust positions
        self.set_portfolio_state(
            current['sol_usd'],
            current['usdc_usd'], 
            current['positions_usd'],
            current_positions
        )
    
    def simulate_portfolio_gains(self, percentage: float):
        """Simulate portfolio value increase by percentage"""
        current = self.get_current_state()
        total_value = current['total_value']
        gain_amount = total_value * (percentage / 100)
        
        # Distribute gains proportionally across positions
        if current['positions_usd'] > 0:
            positions = current['positions']
            for token_address in positions:
                positions[token_address] *= (1 + percentage / 100)
            
            self.set_portfolio_state(
                current['sol_usd'],
                current['usdc_usd'],
                current['positions_usd'] * (1 + percentage / 100),
                positions
            )
        else:
            # If no positions, add to SOL
            self.set_portfolio_state(
                current['sol_usd'] + gain_amount,
                current['usdc_usd'],
                current['positions_usd']
            )
    
    def reset_to_clean_state(self):
        """Reset to clean state: 100% SOL"""
        self.set_portfolio_state(1000.0, 0.0, 0.0)
    
    def verify_allocation(self, expected_sol_pct: float, expected_usdc_pct: float, 
                         expected_pos_pct: float, tolerance: float = 0.02) -> bool:
        """Verify portfolio allocation matches expected percentages"""
        current = self.get_current_state()
        
        sol_ok = abs(current['sol_pct'] - expected_sol_pct) <= tolerance
        usdc_ok = abs(current['usdc_pct'] - expected_usdc_pct) <= tolerance
        pos_ok = abs(current['positions_pct'] - expected_pos_pct) <= tolerance
        
        return sol_ok and usdc_ok and pos_ok
    
    def create_mock_services(self):
        """Create mock services for testing"""
        # Mock price service
        mock_price_service = Mock()
        mock_price_service.get_price.side_effect = lambda token: {
            SOL_ADDRESS: self.sol_price,
            USDC_ADDRESS: self.usdc_price
        }.get(token, 0.01)  # Default price for other tokens
        
        # Mock API manager
        mock_api_manager = Mock()
        mock_api_manager.get_personal_wallet_address.return_value = "TEST_WALLET_1234567890123456789012345678901234567890"
        mock_api_manager.get_token_balances.return_value = {}
        mock_api_manager.get_token_balance.return_value = "0"
        
        # Mock data coordinator
        mock_data_coordinator = Mock()
        
        return mock_price_service, mock_api_manager, mock_data_coordinator


class TestValidator:
    """Validation helpers for test assertions"""
    
    @staticmethod
    def validate_rebalancing_action(action: str, expected_action_type: str, 
                                  expected_amount_range: Tuple[float, float]) -> bool:
        """Validate rebalancing action matches expected type and amount"""
        if not action:
            return expected_action_type == "NONE"
        
        # Check action type
        action_type_ok = expected_action_type in action
        
        # Check amount range
        import re
        amount_match = re.search(r'\$(\d+\.?\d*)', action)
        if amount_match:
            amount = float(amount_match.group(1))
            amount_ok = expected_amount_range[0] <= amount <= expected_amount_range[1]
        else:
            amount_ok = False
        
        return action_type_ok and amount_ok
    
    @staticmethod
    def validate_portfolio_allocation(simulator: PortfolioStateSimulator, 
                                    expected_sol_pct: float, expected_usdc_pct: float,
                                    sol_tolerance: float = 0.02, usdc_tolerance: float = 0.02) -> bool:
        """Validate portfolio allocation with custom tolerances"""
        return simulator.verify_allocation(expected_sol_pct, expected_usdc_pct, 
                                         1.0 - expected_sol_pct - expected_usdc_pct, 
                                         max(sol_tolerance, usdc_tolerance))
    
    @staticmethod
    def generate_test_report(test_results: List[Dict[str, Any]]) -> str:
        """Generate test report with pass/fail counts"""
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results if result.get('passed', False))
        failed_tests = total_tests - passed_tests
        
        report = f"""
Test Report
===========
Total Tests: {total_tests}
Passed: {passed_tests}
Failed: {failed_tests}
Success Rate: {(passed_tests/total_tests)*100:.1f}%

Detailed Results:
"""
        
        for i, result in enumerate(test_results, 1):
            status = "PASS" if result.get('passed', False) else "FAIL"
            report += f"{i}. {result.get('name', 'Unknown Test')}: {status}\n"
            if not result.get('passed', False) and 'error' in result:
                report += f"   Error: {result['error']}\n"
        
        return report


def mock_time_for_cooldown_testing():
    """Context manager to mock time.time() for cooldown testing"""
    class TimeMock:
        def __init__(self):
            self.current_time = time.time()
        
        def time(self):
            return self.current_time
        
        def advance(self, seconds):
            self.current_time += seconds
    
    time_mock = TimeMock()
    
    class TimeContext:
        def __enter__(self):
            self.patcher = patch('time.time', time_mock.time)
            self.patcher.start()
            return time_mock
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.patcher.stop()
    
    return TimeContext()


def create_test_token_addresses(count: int) -> List[str]:
    """Create mock token addresses for testing"""
    addresses = []
    for i in range(count):
        # Create a mock Solana token address (44 characters)
        mock_address = f"MOCK{i:02d}{'0' * 36}"
        addresses.append(mock_address)
    return addresses


class MockJupiterSwap:
    """Mock Jupiter swap service for testing"""
    
    def __init__(self, should_fail=False, failure_rate=0.0):
        self.should_fail = should_fail
        self.failure_rate = failure_rate
        self.swap_calls = []
        self.failure_count = 0
    
    def market_buy(self, token, amount, slippage, allow_excluded=False):
        """Mock market buy operation"""
        self.swap_calls.append({
            'operation': 'market_buy',
            'token': token,
            'amount': amount,
            'slippage': slippage,
            'allow_excluded': allow_excluded
        })
        
        if self.should_fail or (self.failure_rate > 0 and (self.failure_count / max(1, len(self.swap_calls))) < self.failure_rate):
            self.failure_count += 1
            return None
        
        # Return mock transaction signature
        return f"mock_tx_{len(self.swap_calls)}"
    
    def market_sell(self, token, amount, slippage, allow_excluded=False):
        """Mock market sell operation"""
        self.swap_calls.append({
            'operation': 'market_sell',
            'token': token,
            'amount': amount,
            'slippage': slippage,
            'allow_excluded': allow_excluded
        })
        
        if self.should_fail or (self.failure_rate > 0 and (self.failure_count / max(1, len(self.swap_calls))) < self.failure_rate):
            self.failure_count += 1
            return None
        
        # Return mock transaction signature
        return f"mock_tx_{len(self.swap_calls)}"


class MockSOLTransfer:
    """Mock SOL transfer service for testing"""
    
    def __init__(self, should_fail=False, failure_rate=0.0):
        self.should_fail = should_fail
        self.failure_rate = failure_rate
        self.transfer_calls = []
        self.failure_count = 0
    
    def transfer_sol(self, wallet_address, sol_amount_lamports):
        """Mock SOL transfer operation"""
        self.transfer_calls.append({
            'wallet_address': wallet_address,
            'sol_amount_lamports': sol_amount_lamports
        })
        
        if self.should_fail or (self.failure_rate > 0 and (self.failure_count / max(1, len(self.transfer_calls))) < self.failure_rate):
            self.failure_count += 1
            return False
        
        return True


class MockPriceService:
    """Enhanced mock price service with failure modes"""
    
    def __init__(self, should_fail=False, timeout=False, invalid_prices=False):
        self.should_fail = should_fail
        self.timeout = timeout
        self.invalid_prices = invalid_prices
        self.price_calls = []
        self.sol_price = 100.0
        self.usdc_price = 1.0
    
    def get_price(self, token_address):
        """Mock price retrieval with configurable failure modes"""
        self.price_calls.append(token_address)
        
        if self.should_fail:
            return None
        
        if self.timeout:
            import time
            time.sleep(10)  # Simulate timeout
        
        if self.invalid_prices:
            return -1.0  # Invalid negative price
        
        if token_address == "So11111111111111111111111111111111111111112":  # SOL
            return self.sol_price
        elif token_address == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":  # USDC
            return self.usdc_price
        else:
            return 0.01  # Default price for other tokens


class MockAPIManager:
    """Enhanced mock API manager with failure modes"""
    
    def __init__(self, wallet_available=True, balances_available=True, transfer_success=True):
        self.wallet_available = wallet_available
        self.balances_available = balances_available
        self.transfer_success = transfer_success
        self.api_calls = []
        self.wallet_address = "TEST_WALLET_1234567890123456789012345678901234567890"
    
    def get_personal_wallet_address(self):
        """Mock wallet address retrieval"""
        self.api_calls.append('get_personal_wallet_address')
        if not self.wallet_available:
            return None
        return self.wallet_address
    
    def get_token_balances(self, wallet_address):
        """Mock token balance retrieval"""
        self.api_calls.append('get_token_balances')
        if not self.balances_available:
            return None
        return {}  # Empty balances for testing
    
    def get_token_balance(self, wallet_address, token_address):
        """Mock single token balance retrieval"""
        self.api_calls.append('get_token_balance')
        if not self.balances_available:
            return None
        return "1000000"  # Mock balance
    
    def transfer_sol(self, wallet_address, sol_amount_lamports):
        """Mock SOL transfer"""
        self.api_calls.append('transfer_sol')
        return self.transfer_success


class HarvestingTestUtilities:
    """Utilities for harvesting agent testing"""
    
    @staticmethod
    def create_realized_gains_scenario(simulator, initial_value: float, gain_amount: float) -> Tuple[Any, Any]:
        """Simulate portfolio gaining value for realized gains testing"""
        # Set initial portfolio state
        simulator.set_portfolio_state(
            sol_usd=initial_value * 0.1,  # 10% SOL
            usdc_usd=initial_value * 0.2,  # 20% USDC
            positions_usd=initial_value * 0.7  # 70% positions
        )
        
        # Create mock snapshots
        previous_snapshot = MockSnapshot(initial_value)
        current_snapshot = MockSnapshot(initial_value + gain_amount)
        
        return current_snapshot, previous_snapshot
    
    @staticmethod
    def create_dust_positions(simulator, dust_values: List[float]) -> List[str]:
        """Create multiple dust positions for testing"""
        dust_positions = {}
        token_addresses = []
        
        for i, value in enumerate(dust_values):
            token_address = f"DUST_TOKEN_{i:03d}_{int(time.time())}"
            dust_positions[token_address] = value
            token_addresses.append(token_address)
        
        # Set portfolio with dust positions
        simulator.set_portfolio_state(
            sol_usd=100.0,
            usdc_usd=200.0,
            positions_usd=0.0,
            positions=dust_positions
        )
        
        return token_addresses
    
    @staticmethod
    def mock_ai_sentiment_data(sentiment_type: str = "BULLISH") -> Dict[str, Any]:
        """Provide test sentiment data for AI analysis"""
        sentiment_mapping = {
            "BULLISH": {
                'chart_sentiment': 'BULLISH',
                'twitter_classification': 'POSITIVE',
                'overall_sentiment': 'BULLISH',
                'confidence': 80.0
            },
            "BEARISH": {
                'chart_sentiment': 'BEARISH',
                'twitter_classification': 'NEGATIVE',
                'overall_sentiment': 'BEARISH',
                'confidence': 75.0
            },
            "MIXED": {
                'chart_sentiment': 'NEUTRAL',
                'twitter_classification': 'MIXED',
                'overall_sentiment': 'MIXED',
                'confidence': 60.0
            }
        }
        
        return sentiment_mapping.get(sentiment_type, sentiment_mapping["BULLISH"])
    
    @staticmethod
    def capture_ai_response(agent, trigger_type: str, gains_data: dict) -> Dict[str, Any]:
        """Call AI and capture full response for validation"""
        try:
            # Enable response logging
            original_log_level = agent.logger.level
            agent.logger.setLevel(10)  # DEBUG level
            
            # Call AI decision
            decision = agent.get_ai_harvesting_decision(
                trigger_type=trigger_type,
                gains_data=gains_data
            )
            
            # Restore log level
            agent.logger.setLevel(original_log_level)
            
            # Validate response structure
            assert 'action' in decision, "AI response missing action"
            assert 'confidence' in decision, "AI response missing confidence"
            assert 'reasoning' in decision, "AI response missing reasoning"
            
            return decision
            
        except Exception as e:
            return {
                'action': 'HOLD_GAINS',
                'confidence': 0,
                'reasoning': f'AI call failed: {str(e)}',
                'error': True
            }


class StressTestUtilities:
    """Utilities for stress testing scenarios"""
    
    @staticmethod
    def create_large_portfolio(simulator, total_value_usd, dust_count=0, large_position_count=5):
        """Create a large portfolio for stress testing"""
        # Create base SOL and USDC
        sol_usd = total_value_usd * 0.1
        usdc_usd = total_value_usd * 0.2
        positions_usd = total_value_usd * 0.7
        
        # Create dust positions
        dust_positions = {}
        if dust_count > 0:
            dust_tokens = create_test_token_addresses(dust_count)
            dust_value_per_token = 0.5  # $0.50 each
            for token in dust_tokens:
                dust_positions[token] = dust_value_per_token
            positions_usd -= dust_count * dust_value_per_token
        
        # Create large positions
        large_positions = {}
        if large_position_count > 0:
            large_tokens = create_test_token_addresses(large_position_count)
            large_value_per_token = positions_usd / large_position_count
            for token in large_tokens:
                large_positions[token] = large_value_per_token
        
        # Combine all positions
        all_positions = {**dust_positions, **large_positions}
        
        simulator.set_portfolio_state(sol_usd, usdc_usd, positions_usd, all_positions)
        return simulator.get_current_state()
    
    @staticmethod
    def simulate_rapid_gains(simulator, gain_percentages):
        """Simulate rapid portfolio gains"""
        results = []
        for gain_pct in gain_percentages:
            simulator.simulate_portfolio_gains(gain_pct)
            state = simulator.get_current_state()
            results.append({
                'gain_percentage': gain_pct,
                'total_value': state['total_value'],
                'timestamp': time.time()
            })
        return results


class ErrorRecoveryTestHelper:
    """Helper for testing error recovery scenarios"""
    
    @staticmethod
    def create_failing_services():
        """Create services configured to fail"""
        return {
            'price_service': MockPriceService(should_fail=True),
            'api_manager': MockAPIManager(wallet_available=False, balances_available=False),
            'jupiter_swap': MockJupiterSwap(should_fail=True),
            'sol_transfer': MockSOLTransfer(should_fail=True)
        }
    
    @staticmethod
    def create_partial_failure_services():
        """Create services with partial failures"""
        return {
            'price_service': MockPriceService(should_fail=False, invalid_prices=True),
            'api_manager': MockAPIManager(wallet_available=True, balances_available=False),
            'jupiter_swap': MockJupiterSwap(should_fail=False, failure_rate=0.5),
            'sol_transfer': MockSOLTransfer(should_fail=False, failure_rate=0.3)
        }
    
    @staticmethod
    def create_timeout_services():
        """Create services that timeout"""
        return {
            'price_service': MockPriceService(timeout=True),
            'api_manager': MockAPIManager(),
            'jupiter_swap': MockJupiterSwap(),
            'sol_transfer': MockSOLTransfer()
        }