#!/usr/bin/env python3
"""
🧪 ITORO Commerce System Integration Tests
Comprehensive testing suite for all commerce agents and shared infrastructure

This test suite validates the complete commerce layer functionality including:
- Database connectivity and data operations
- Agent initialization and health checks
- API endpoint functionality
- Payment processing simulation
- Data flow between agents
- Integration with existing trading data
"""

import os
import sys
import json
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/scripts')

# Import commerce system components
from shared.config import *
from shared.database import get_database_manager, TradingSignal, WhaleRanking, StrategyMetadata, ExecutedTrade
from core.database import UnifiedTradingSignal, WhaleRankingRecord, StrategyMetadataRecord, ExecutedTradeRecord
from shared.utils import (
    generate_unique_id, format_currency, calculate_sharpe_ratio,
    api_key_manager, rate_limiter, encryption_manager
)
from scripts.pricing import get_pricing_engine
from agents.signal_service_agent import get_signal_service_agent
from agents.data_service_agent import get_data_service_agent
from agents.merchant_agent import get_merchant_agent
from agents.whale_ranking_agent import get_whale_ranking_agent
from agents.strategy_metadata_agent import get_strategy_metadata_agent

# =============================================================================
# 🎭 TEST DATA GENERATORS
# =============================================================================

def generate_test_signal(symbol: str = "SOL/USD", action: str = "BUY",
                        confidence: float = 0.85, source: str = "test_agent") -> TradingSignal:
    """Generate a test trading signal"""
    return TradingSignal(
        timestamp=datetime.now(),
        symbol=symbol,
        action=action,
        confidence=confidence,
        price=150.50 + (hash(symbol) % 100),  # Pseudo-random price
        volume=1000.0 + (hash(symbol) % 5000),
        source_agent=source
    )

def generate_test_whale_ranking(address: str = None, rank: int = 1,
                               pnl_30d: float = 0.25) -> WhaleRanking:
    """Generate a test whale ranking"""
    if not address:
        address = f"test_wallet_{rank}"

    return WhaleRanking(
        address=address,
        twitter_handle=f"whale_{rank}",
        pnl_30d=pnl_30d,
        pnl_7d=pnl_30d * 0.7,
        pnl_1d=pnl_30d * 0.3,
        winrate_7d=0.75,
        txs_30d=1500 + rank * 100,
        token_active=50 + rank * 10,
        last_active=datetime.now(),
        is_blue_verified=(rank <= 5),
        avg_holding_period_7d=3600.0 + rank * 100,
        score=1.0 - (rank * 0.1),
        rank=rank,
        last_updated=datetime.now()
    )

def generate_test_strategy_metadata(strategy_id: str = "test_strategy",
                                   agent_type: str = "copybot_agent") -> StrategyMetadata:
    """Generate test strategy metadata"""
    return StrategyMetadata(
        strategy_id=strategy_id,
        strategy_name=f"Test {agent_type.title()} Strategy",
        agent_type=agent_type,
        performance_metrics={
            'total_trades': 100,
            'win_rate': 0.65,
            'total_return': 12.5,
            'sharpe_ratio': 1.8,
            'max_drawdown': 0.15
        },
        risk_metrics={
            'volatility': 0.25,
            'var_95': 0.08,
            'sortino_ratio': 2.1
        },
        last_updated=datetime.now(),
        is_active=True
    )

def generate_test_trade(symbol: str = "SOL/USD", side: str = "BUY",
                       quantity: float = 100.0, price: float = 150.50) -> ExecutedTrade:
    """Generate a test executed trade"""
    return ExecutedTrade(
        timestamp=datetime.now(),
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        value_usd=quantity * price,
        source_agent="test_agent",
        pnl_realized=price * quantity * 0.02 if side == "SELL" else None  # 2% profit simulation
    )

# =============================================================================
# 🧪 UNIT TESTS
# =============================================================================

class TestSharedInfrastructure(unittest.TestCase):
    """Test shared infrastructure components"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_manager_initialization(self):
        """Test database manager initialization"""
        db = get_database_manager()
        self.assertIsNotNone(db)

        # Test health check (should work even without cloud connection)
        health = db.health_check()
        self.assertIsInstance(health, dict)
        self.assertIn('connected', health)

    def test_pricing_engine_initialization(self):
        """Test pricing engine initialization"""
        pricing = get_pricing_engine()
        self.assertIsNotNone(pricing)

        # Test plan retrieval
        plans = pricing.get_subscription_plans()
        self.assertIsInstance(plans, list)
        self.assertGreater(len(plans), 0)

    def test_utility_functions(self):
        """Test utility functions"""
        # Test currency formatting
        self.assertEqual(format_currency(1234.56), "$1,234.56")
        self.assertEqual(format_currency(0.5, 'SOL'), "0.5000 SOL")

        # Test Sharpe ratio calculation
        returns = [0.01, 0.02, -0.005, 0.015, 0.008]
        sharpe = calculate_sharpe_ratio(returns)
        self.assertIsInstance(sharpe, float)

        # Test ID generation
        id1 = generate_unique_id('test')
        id2 = generate_unique_id('test')
        self.assertNotEqual(id1, id2)
        self.assertTrue(id1.startswith('test_'))

    def test_encryption_manager(self):
        """Test encryption functionality"""
        test_data = "Hello, World! This is a test message."

        # Test encryption/decryption
        encrypted = encryption_manager.encrypt(test_data)
        decrypted = encryption_manager.decrypt(encrypted)

        if encryption_manager.enabled:
            self.assertNotEqual(encrypted, test_data)
            self.assertEqual(decrypted, test_data)
        else:
            # If encryption is disabled, should return plain text
            self.assertEqual(encrypted, test_data)
            self.assertEqual(decrypted, test_data)

    def test_core_model_conversion(self):
        """Ensure shared models convert to core unified schema and back."""
        unified_signal = UnifiedTradingSignal(
            signal_id="signal_test",
            ecosystem="crypto",
            timestamp=datetime.utcnow(),
            symbol="SOL/USD",
            action="BUY",
            signal_type="MARKET",
            entry_price=150.0,
            confidence=0.9,
            volume=100.0,
            agent_source="unit_test",
        )
        local_signal = TradingSignal.from_core(unified_signal)
        self.assertEqual(local_signal.symbol, unified_signal.symbol)
        self.assertEqual(local_signal.action, unified_signal.action)
        self.assertEqual(local_signal.price, unified_signal.entry_price)
        self.assertEqual(local_signal.volume, unified_signal.volume)
        round_trip_signal = local_signal.to_core()
        self.assertEqual(round_trip_signal.symbol, unified_signal.symbol)

        ranking_record = WhaleRankingRecord(
            ranking_id="ranking_test",
            ecosystem="crypto",
            address="wallet1",
            rank=1,
            score=0.95,
            pnl_30d=0.3,
            pnl_7d=0.2,
            pnl_1d=0.1,
            winrate_7d=0.75,
            last_active=datetime.utcnow(),
            is_active=True,
            metadata={"twitter_handle": "whale"},
        )
        local_ranking = WhaleRanking.from_core(ranking_record)
        self.assertEqual(local_ranking.address, ranking_record.address)
        self.assertEqual(local_ranking.rank, ranking_record.rank)
        round_trip_ranking = local_ranking.to_core()
        self.assertEqual(round_trip_ranking.address, ranking_record.address)

        strategy_record = StrategyMetadataRecord(
            strategy_id="strat1",
            ecosystem="crypto",
            name="Strategy",
            agent_source="copybot",
            timestamp=datetime.utcnow(),
            metrics={"performance": {"win_rate": 0.6}, "risk": {"max_drawdown": 0.1}},
        )
        local_strategy = StrategyMetadata.from_core(strategy_record)
        self.assertEqual(local_strategy.strategy_id, strategy_record.strategy_id)
        round_trip_strategy = local_strategy.to_core()
        self.assertEqual(round_trip_strategy.strategy_id, strategy_record.strategy_id)

        trade_record = ExecutedTradeRecord(
            trade_id="trade_test",
            ecosystem="crypto",
            timestamp=datetime.utcnow(),
            symbol="SOL/USD",
            side="BUY",
            quantity=10.0,
            price=150.0,
            pnl=5.0,
            metadata={"value_usd": 1500.0},
        )
        local_trade = ExecutedTrade.from_core(trade_record)
        self.assertEqual(local_trade.symbol, trade_record.symbol)
        self.assertAlmostEqual(local_trade.value_usd, 1500.0)
        round_trip_trade = local_trade.to_core()
        self.assertEqual(round_trip_trade.trade_id, trade_record.trade_id)

class TestCommerceAgents(unittest.TestCase):
    """Test individual commerce agents"""

    def setUp(self):
        """Set up test agents"""
        self.signal_agent = get_signal_service_agent()
        self.data_agent = get_data_service_agent()
        self.merchant_agent = get_merchant_agent()
        self.whale_agent = get_whale_ranking_agent()
        self.strategy_agent = get_strategy_metadata_agent()

    def test_agent_initialization(self):
        """Test agent initialization"""
        agents = [self.signal_agent, self.data_agent, self.merchant_agent,
                 self.whale_agent, self.strategy_agent]

        for agent in agents:
            with self.subTest(agent=agent.__class__.__name__):
                self.assertIsNotNone(agent)
                health = agent.health_check()
                self.assertIsInstance(health, dict)
                self.assertIn('agent', health)

    def test_signal_service_agent(self):
        """Test signal service agent functionality"""
        # Test health check
        health = self.signal_agent.health_check()
        self.assertIn('running', health)

        # Test API endpoints (mock user info)
        user_info = {'user_id': 'test_user', 'tier': 'basic'}

        # Test signal retrieval (may return empty in test environment)
        result = self.signal_agent.get_live_signals(user_info, limit=5)
        self.assertIn('status', result)

        # Test subscription creation
        subscription_result = self.signal_agent.subscribe_to_signals(
            user_info, 'telegram', {'symbols': ['SOL/USD']}
        )
        self.assertIn('status', subscription_result)

    def test_data_service_agent(self):
        """Test data service agent functionality"""
        # Test health check
        health = self.data_agent.health_check()
        self.assertIn('running', health)

        # Test dataset listing
        user_info = {'user_id': 'test_user', 'tier': 'pro'}
        result = self.data_agent.get_available_datasets(user_info)
        self.assertIn('status', result)

        # Test custom dataset creation
        dataset_id = self.data_agent.create_custom_dataset(
            name="Test Dataset",
            description="Test dataset for integration testing",
            data=[{"test": "data", "value": 123}],
            price_usd=9.99
        )
        if dataset_id:
            self.assertTrue(dataset_id.startswith('custom_dataset'))

    def test_merchant_agent(self):
        """Test merchant agent functionality"""
        # Test health check
        health = self.merchant_agent.health_check()
        self.assertIn('running', health)

        # Test payment intent creation (mock)
        user_info = {'user_id': 'test_user', 'tier': 'basic'}

        # Test subscription creation
        subscription_result = self.merchant_agent.create_subscription(
            user_info, 'basic', 'stripe'
        )
        self.assertIn('status', subscription_result)

    def test_whale_ranking_agent(self):
        """Test whale ranking agent functionality"""
        # Test health check
        health = self.whale_agent.health_check()
        self.assertIn('running', health)

        # Test ranking retrieval
        user_info = {'user_id': 'test_user', 'tier': 'basic'}
        result = self.whale_agent.get_whale_rankings(user_info, limit=10)
        self.assertIn('status', result)

        # Test top performers
        performers_result = self.whale_agent.get_top_performers(user_info, limit=5)
        self.assertIn('status', performers_result)

    def test_strategy_metadata_agent(self):
        """Test strategy metadata agent functionality"""
        # Test health check
        health = self.strategy_agent.health_check()
        self.assertIn('running', health)

        # Test analysis retrieval
        user_info = {'user_id': 'test_user', 'tier': 'pro'}
        result = self.strategy_agent.get_strategy_analysis(user_info)
        self.assertIn('status', result)

        # Test market intelligence
        intelligence = self.strategy_agent.get_market_intelligence()
        self.assertIsInstance(intelligence, dict)

class TestDataIntegration(unittest.TestCase):
    """Test data integration between components"""

    def setUp(self):
        """Set up test data"""
        self.db = get_database_manager()
        self.pricing = get_pricing_engine()

        # Generate test data
        self.test_signals = [generate_test_signal(f"SOL/USD_{i}") for i in range(5)]
        self.test_whales = [generate_test_whale_ranking(rank=i+1) for i in range(10)]
        self.test_strategies = [generate_test_strategy_metadata(f"strategy_{i}") for i in range(3)]
        self.test_trades = [generate_test_trade(f"SOL/USD_{i}") for i in range(20)]

    def test_database_data_operations(self):
        """Test database data operations"""
        # Test signal storage and retrieval
        success = self.db.store_trading_signals(self.test_signals)
        self.assertTrue(success)

        signals = self.db.get_trading_signals(limit=10)
        self.assertIsInstance(signals, list)

        # Test whale ranking storage and retrieval
        success = self.db.store_whale_rankings(self.test_whales)
        self.assertTrue(success)

        rankings = self.db.get_whale_rankings(limit=10)
        self.assertIsInstance(rankings, list)

        # Test strategy metadata storage and retrieval
        success = self.db.store_strategy_metadata(self.test_strategies)
        self.assertTrue(success)

        strategies = self.db.get_strategy_metadata()
        self.assertIsInstance(strategies, list)

        # Test trade storage and retrieval
        success = self.db.store_executed_trades(self.test_trades)
        self.assertTrue(success)

        trades = self.db.get_executed_trades(limit=10)
        self.assertIsInstance(trades, list)

    def test_pricing_integration(self):
        """Test pricing engine integration"""
        # Test user subscription creation
        subscription = self.pricing.create_user_subscription(
            user_id='test_integration_user',
            plan_id='pro',
            payment_method='stripe'
        )
        if subscription:
            self.assertEqual(subscription.plan_id, 'pro')

            # Test user tier retrieval
            tier = self.pricing.get_user_tier('test_integration_user')
            self.assertEqual(tier, 'pro')

            # Test limit checking
            allowed, message = self.pricing.check_tier_limits('test_integration_user', 'api_requests', 100)
            self.assertTrue(allowed)

    def test_agent_data_flow(self):
        """Test data flow between agents"""
        # Store test data in database
        self.db.store_trading_signals(self.test_signals)
        self.db.store_whale_rankings(self.test_whales)
        self.db.store_strategy_metadata(self.test_strategies)

        # Test signal agent data retrieval
        signal_agent = get_signal_service_agent()
        user_info = {'user_id': 'test_user', 'tier': 'basic'}

        result = signal_agent.get_live_signals(user_info)
        self.assertEqual(result['status'], 'success')

        # Test whale agent data retrieval
        whale_agent = get_whale_ranking_agent()
        result = whale_agent.get_whale_rankings(user_info)
        self.assertEqual(result['status'], 'success')

        # Test strategy agent data retrieval
        strategy_agent = get_strategy_metadata_agent()
        result = strategy_agent.get_strategy_analysis(user_info)
        self.assertEqual(result['status'], 'success')

class TestAPIFunctionality(unittest.TestCase):
    """Test API functionality"""

    def setUp(self):
        """Set up API test environment"""
        self.user_info = {'user_id': 'api_test_user', 'tier': 'pro'}
        self.pricing = get_pricing_engine()

    def test_api_key_management(self):
        """Test API key management"""
        # Generate API key
        api_key = api_key_manager.generate_api_key(self.user_info['user_id'])

        self.assertIsInstance(api_key, str)
        self.assertGreater(len(api_key), 10)

        # Validate API key
        validation = api_key_manager.validate_api_key(api_key)
        self.assertIsNotNone(validation)
        self.assertEqual(validation['user_id'], self.user_info['user_id'])

    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        user_id = self.user_info['user_id']

        # Test rate limiting for multiple requests
        allowed_count = 0
        for i in range(10):
            if rate_limiter.is_allowed(user_id):
                allowed_count += 1

        # Should allow some requests but eventually limit
        self.assertGreater(allowed_count, 0)
        self.assertLess(allowed_count, 10)

    def test_pricing_api_calls(self):
        """Test pricing integration with API calls"""
        # Record API usage
        success = self.pricing.record_api_usage(self.user_info['user_id'], 'test_endpoint')
        self.assertTrue(success)

        # Check usage stats
        stats = self.pricing.get_user_usage_stats(self.user_info['user_id'])
        self.assertIsInstance(stats, dict)
        self.assertIn('total_requests', stats)

class TestSystemIntegration(unittest.TestCase):
    """Test complete system integration"""

    def test_full_system_startup(self):
        """Test full system startup and shutdown"""
        agents = [
            get_signal_service_agent(),
            get_data_service_agent(),
            get_merchant_agent(),
            get_whale_ranking_agent(),
            get_strategy_metadata_agent()
        ]

        # Test startup
        for agent in agents:
            with self.subTest(agent=agent.__class__.__name__):
                # Agents should start without errors
                health = agent.health_check()
                self.assertIsInstance(health, dict)

    def test_cross_agent_communication(self):
        """Test communication between agents"""
        # Test that agents can access shared resources
        db = get_database_manager()
        pricing = get_pricing_engine()

        # All agents should be able to access the database and pricing engine
        self.assertIsNotNone(db)
        self.assertIsNotNone(pricing)

        # Test that pricing engine has been initialized with plans
        plans = pricing.get_subscription_plans()
        self.assertGreater(len(plans), 0)

    def test_error_handling(self):
        """Test error handling across the system"""
        # Test database connection failure (should handle gracefully)
        db = get_database_manager()

        # Should not crash even if database operations fail
        result = db.get_trading_signals(limit=1)
        self.assertIsInstance(result, list)  # Should return empty list or data

    def test_configuration_validation(self):
        """Test configuration validation"""
        # Import the example config to test validation
        try:
            import config.example as test_config
            missing = test_config.validate_config()

            # Should have missing configurations in example
            self.assertIsInstance(missing, list)

        except ImportError:
            # Example config may not be available
            pass

class TestPerformance(unittest.TestCase):
    """Test system performance"""

    def test_agent_response_times(self):
        """Test agent response times"""
        import time

        agents = [
            ('Signal Service', get_signal_service_agent()),
            ('Data Service', get_data_service_agent()),
            ('Merchant', get_merchant_agent()),
            ('Whale Ranking', get_whale_ranking_agent()),
            ('Strategy Metadata', get_strategy_metadata_agent())
        ]

        for agent_name, agent in agents:
            with self.subTest(agent=agent_name):
                start_time = time.time()
                health = agent.health_check()
                response_time = time.time() - start_time

                # Health check should complete in reasonable time
                self.assertLess(response_time, 5.0)  # Less than 5 seconds
                self.assertIsInstance(health, dict)

    def test_database_performance(self):
        """Test database performance"""
        import time

        db = get_database_manager()

        # Test signal retrieval performance
        start_time = time.time()
        signals = db.get_trading_signals(limit=50)
        retrieval_time = time.time() - start_time

        # Should retrieve data reasonably quickly
        self.assertLess(retrieval_time, 10.0)  # Less than 10 seconds
        self.assertIsInstance(signals, list)

# =============================================================================
# 🎯 TEST SUITE RUNNER
# =============================================================================

def run_integration_tests():
    """Run the complete integration test suite"""
    print("🚀 Starting ITORO Commerce System Integration Tests...")
    print("=" * 60)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestSharedInfrastructure,
        TestCommerceAgents,
        TestDataIntegration,
        TestAPIFunctionality,
        TestSystemIntegration,
        TestPerformance
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("=" * 60)
    print("📊 Test Results Summary:")
    print(f"   Total tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    print(f"   Skipped: {len(result.skipped)}")

    if result.wasSuccessful():
        print("✅ All integration tests passed!")
        return True
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return False

def run_quick_test():
    """Run a quick smoke test of the system"""
    print("🚀 Running ITORO Commerce Quick Test...")

    try:
        # Test basic imports
        from shared.database import get_database_manager
        from commerce_agents.pricing import get_pricing_engine
        print("✅ Imports successful")

        # Test agent initialization
        db = get_database_manager()
        pricing = get_pricing_engine()

        agents = [
            get_signal_service_agent(),
            get_data_service_agent(),
            get_merchant_agent(),
            get_whale_ranking_agent(),
            get_strategy_metadata_agent()
        ]
        print("✅ Agent initialization successful")

        # Test basic functionality
        health_checks = []
        for agent in agents:
            health = agent.health_check()
            health_checks.append(health['agent'])

        print(f"✅ Health checks passed for: {', '.join(health_checks)}")

        # Test pricing
        plans = pricing.get_subscription_plans()
        print(f"✅ Pricing engine loaded {len(plans)} plans")

        print("🎉 Quick test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        return False

# =============================================================================
# 🎬 MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='ITORO Commerce System Tests')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick smoke test only')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    if args.quick:
        success = run_quick_test()
    else:
        success = run_integration_tests()

    sys.exit(0 if success else 1)
