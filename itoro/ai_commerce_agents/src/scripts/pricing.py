"""
💰 ITORO Pricing Engine
Manages subscription tiers, API pricing, and revenue calculations

Handles pricing logic, tier management, and billing calculations for all commerce agents.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
import logging

try:
    # Try relative imports first (when used as part of package)
    from ..shared.config import PRICING_TIERS, API_PRICING, PAYMENT_CURRENCY
    from ..shared.utils import format_currency, format_percentage, save_json_file, load_json_file
    from ..shared.database import get_database_manager, ExecutedTrade, TradingSignal
except ImportError:
    # Fall back to absolute imports (when imported directly)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shared.config import PRICING_TIERS, API_PRICING, PAYMENT_CURRENCY
    from shared.utils import format_currency, format_percentage, save_json_file, load_json_file
    from shared.database import get_database_manager, ExecutedTrade, TradingSignal

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 📋 DATA MODELS
# =============================================================================

@dataclass
class SubscriptionPlan:
    """Subscription plan data model"""
    plan_id: str
    name: str
    description: str
    monthly_price: float
    annual_price: float
    currency: str
    features: List[str]
    limits: Dict[str, Any]
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubscriptionPlan':
        """Create from dictionary"""
        data_copy = data.copy()
        if 'created_at' in data_copy and data_copy['created_at']:
            data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if 'updated_at' in data_copy and data_copy['updated_at']:
            data_copy['updated_at'] = datetime.fromisoformat(data_copy['updated_at'])
        return cls(**data_copy)

@dataclass
class UserSubscription:
    """User subscription data model"""
    subscription_id: str
    user_id: str
    plan_id: str
    status: str  # 'active', 'cancelled', 'expired', 'past_due'
    current_period_start: datetime
    current_period_end: datetime
    created_at: datetime
    cancel_at_period_end: bool = False
    payment_method: str = 'stripe'  # 'stripe', 'solana_pay', 'free'
    currency: str = 'USD'
    amount: float = 0.0
    billing_cycle: str = 'monthly'  # 'monthly', 'annual'
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['current_period_start'] = self.current_period_start.isoformat()
        data['current_period_end'] = self.current_period_end.isoformat()
        data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSubscription':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['current_period_start'] = datetime.fromisoformat(data_copy['current_period_start'])
        data_copy['current_period_end'] = datetime.fromisoformat(data_copy['current_period_end'])
        data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if 'updated_at' in data_copy and data_copy['updated_at']:
            data_copy['updated_at'] = datetime.fromisoformat(data_copy['updated_at'])
        return cls(**data_copy)

@dataclass
class APIUsage:
    """API usage tracking data model"""
    usage_id: str
    user_id: str
    api_endpoint: str
    request_count: int
    data_transfer_bytes: int
    period_start: datetime
    period_end: datetime
    cost: float
    currency: str
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['period_start'] = self.period_start.isoformat()
        data['period_end'] = self.period_end.isoformat()
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'APIUsage':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['period_start'] = datetime.fromisoformat(data_copy['period_start'])
        data_copy['period_end'] = datetime.fromisoformat(data_copy['period_end'])
        data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        return cls(**data_copy)

@dataclass
class RevenueTransaction:
    """Revenue transaction data model"""
    transaction_id: str
    user_id: str
    transaction_type: str  # 'subscription', 'api_call', 'data_sale', 'signal_sale'
    amount: float
    currency: str
    payment_method: str
    status: str  # 'pending', 'completed', 'failed', 'refunded'
    description: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.processed_at:
            data['processed_at'] = self.processed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RevenueTransaction':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if 'processed_at' in data_copy and data_copy['processed_at']:
            data_copy['processed_at'] = datetime.fromisoformat(data_copy['processed_at'])
        return cls(**data_copy)

# =============================================================================
# 💰 PRICING ENGINE
# =============================================================================

class PricingEngine:
    """Core pricing and revenue management engine"""

    def __init__(self):
        self.db = get_database_manager()
        self.plans_file = os.path.join('data', 'subscription_plans.json')
        self.subscriptions_file = os.path.join('data', 'user_subscriptions.json')
        self.usage_file = os.path.join('data', 'api_usage.json')
        self.revenue_file = os.path.join('data', 'revenue_transactions.json')

        # Initialize data structures
        self._load_subscription_plans()
        self._load_user_subscriptions()
        self._load_api_usage()
        self._load_revenue_transactions()

    def _load_subscription_plans(self):
        """Load subscription plans from file"""
        self.subscription_plans = {}

        # Load default plans from config
        for plan_id, plan_data in PRICING_TIERS.items():
            plan = SubscriptionPlan(
                plan_id=plan_id,
                name=plan_data['name'],
                description=f"{plan_data['name']} tier subscription",
                monthly_price=plan_data['monthly_price'],
                annual_price=plan_data['monthly_price'] * 10,  # 2 months free for annual
                currency=PAYMENT_CURRENCY,
                features=self._get_plan_features(plan_id),
                limits=plan_data,
                created_at=datetime.now()
            )
            self.subscription_plans[plan_id] = plan

        # Load custom plans from file
        custom_plans = load_json_file(self.plans_file)
        for plan_data in custom_plans.get('plans', []):
            plan = SubscriptionPlan.from_dict(plan_data)
            self.subscription_plans[plan.plan_id] = plan

    def _load_user_subscriptions(self):
        """Load user subscriptions from file"""
        self.user_subscriptions = {}
        data = load_json_file(self.subscriptions_file)

        for sub_data in data.get('subscriptions', []):
            subscription = UserSubscription.from_dict(sub_data)
            self.user_subscriptions[subscription.subscription_id] = subscription

    def _load_api_usage(self):
        """Load API usage data from file"""
        self.api_usage = {}
        data = load_json_file(self.usage_file)

        for usage_data in data.get('usage', []):
            usage = APIUsage.from_dict(usage_data)
            key = f"{usage.user_id}_{usage.api_endpoint}_{usage.period_start.date()}"
            self.api_usage[key] = usage

    def _load_revenue_transactions(self):
        """Load revenue transactions from file"""
        self.revenue_transactions = []
        data = load_json_file(self.revenue_file)

        for tx_data in data.get('transactions', []):
            transaction = RevenueTransaction.from_dict(tx_data)
            self.revenue_transactions.append(transaction)

    def _save_subscription_plans(self):
        """Save subscription plans to file"""
        plans_data = {
            'plans': [plan.to_dict() for plan in self.subscription_plans.values()],
            'last_updated': datetime.now().isoformat()
        }
        save_json_file(self.plans_file, plans_data)

    def _save_user_subscriptions(self):
        """Save user subscriptions to file"""
        subscriptions_data = {
            'subscriptions': [sub.to_dict() for sub in self.user_subscriptions.values()],
            'last_updated': datetime.now().isoformat()
        }
        save_json_file(self.subscriptions_file, subscriptions_data)

    def _save_api_usage(self):
        """Save API usage to file"""
        usage_data = {
            'usage': [usage.to_dict() for usage in self.api_usage.values()],
            'last_updated': datetime.now().isoformat()
        }
        save_json_file(self.usage_file, usage_data)

    def _save_revenue_transactions(self):
        """Save revenue transactions to file"""
        transactions_data = {
            'transactions': [tx.to_dict() for tx in self.revenue_transactions],
            'last_updated': datetime.now().isoformat()
        }
        save_json_file(self.revenue_file, transactions_data)

    def _get_plan_features(self, plan_id: str) -> List[str]:
        """Get features list for a plan"""
        features_map = {
            'free': [
                'Basic signal access',
                'Limited API calls (100/day)',
                'Community support',
                '7-day data retention'
            ],
            'basic': [
                'Advanced signal access',
                'API access (1000/hour)',
                'Email support',
                '30-day data retention',
                'Basic analytics'
            ],
            'pro': [
                'Premium signal access',
                'High-volume API (10,000/hour)',
                'Priority support',
                '90-day data retention',
                'Advanced analytics',
                'Custom alerts'
            ],
            'enterprise': [
                'Unlimited signal access',
                'Unlimited API calls',
                'Dedicated support',
                '1-year data retention',
                'Full analytics suite',
                'Custom integrations',
                'White-label options'
            ]
        }
        return features_map.get(plan_id, [])

    # =========================================================================
    # 💳 SUBSCRIPTION MANAGEMENT
    # =========================================================================

    def get_subscription_plans(self) -> List[SubscriptionPlan]:
        """Get all available subscription plans"""
        return list(self.subscription_plans.values())

    def get_plan_by_id(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """Get subscription plan by ID"""
        return self.subscription_plans.get(plan_id)

    def create_user_subscription(self, user_id: str, plan_id: str,
                               payment_method: str = 'stripe',
                               billing_cycle: str = 'monthly') -> Optional[UserSubscription]:
        """Create a new user subscription"""
        plan = self.get_plan_by_id(plan_id)
        if not plan:
            logger.error(f"Plan {plan_id} not found")
            return None

        # Calculate pricing
        amount = plan.monthly_price if billing_cycle == 'monthly' else plan.annual_price

        # Calculate period dates
        now = datetime.now()
        if billing_cycle == 'monthly':
            period_end = now + timedelta(days=30)
        else:
            period_end = now + timedelta(days=365)

        # Create subscription
        subscription = UserSubscription(
            subscription_id=f"sub_{user_id}_{int(time.time())}",
            user_id=user_id,
            plan_id=plan_id,
            status='active',
            current_period_start=now,
            current_period_end=period_end,
            payment_method=payment_method,
            currency=plan.currency,
            amount=amount,
            billing_cycle=billing_cycle,
            created_at=now
        )

        self.user_subscriptions[subscription.subscription_id] = subscription
        self._save_user_subscriptions()

        # Record revenue transaction
        self._record_transaction(
            user_id=user_id,
            transaction_type='subscription',
            amount=amount,
            currency=plan.currency,
            payment_method=payment_method,
            description=f"{plan.name} {billing_cycle} subscription"
        )

        logger.info(f"Created subscription {subscription.subscription_id} for user {user_id}")
        return subscription

    def get_user_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """Get active subscription for user"""
        active_subscriptions = [
            sub for sub in self.user_subscriptions.values()
            if sub.user_id == user_id and sub.status == 'active'
        ]

        if not active_subscriptions:
            return None

        # Return the most recently created active subscription
        return max(active_subscriptions, key=lambda x: x.created_at)

    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a user subscription"""
        if subscription_id not in self.user_subscriptions:
            return False

        subscription = self.user_subscriptions[subscription_id]
        subscription.status = 'cancelled'
        subscription.updated_at = datetime.now()
        self._save_user_subscriptions()

        logger.info(f"Cancelled subscription {subscription_id}")
        return True

    def get_user_tier(self, user_id: str) -> str:
        """Get user's current subscription tier"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return 'free'

        plan = self.get_plan_by_id(subscription.plan_id)
        return plan.plan_id if plan else 'free'

    # =========================================================================
    # 📊 API USAGE TRACKING
    # =========================================================================

    def record_api_usage(self, user_id: str, endpoint: str,
                        data_transfer_bytes: int = 0) -> bool:
        """Record API usage for billing"""
        try:
            now = datetime.now()
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Get current period usage
            usage_key = f"{user_id}_{endpoint}_{period_start.date()}"
            usage = self.api_usage.get(usage_key)

            if not usage:
                usage = APIUsage(
                    usage_id=f"usage_{user_id}_{endpoint}_{int(time.time())}",
                    user_id=user_id,
                    api_endpoint=endpoint,
                    request_count=0,
                    data_transfer_bytes=0,
                    period_start=period_start,
                    period_end=period_start + timedelta(days=1),
                    cost=0.0,
                    currency=PAYMENT_CURRENCY,
                    created_at=now
                )
                self.api_usage[usage_key] = usage

            # Update usage
            usage.request_count += 1
            usage.data_transfer_bytes += data_transfer_bytes
            usage.cost = self.calculate_api_cost(endpoint, usage.request_count, data_transfer_bytes)

            self._save_api_usage()
            return True

        except Exception as e:
            logger.error(f"Failed to record API usage: {e}")
            return False

    def calculate_api_cost(self, endpoint: str, request_count: int,
                          data_transfer_bytes: int = 0) -> float:
        """Calculate API usage cost"""
        base_cost = API_PRICING.get(endpoint, 0.01)  # Default $0.01 per request

        # Apply volume discounts for high usage
        if request_count > 10000:
            base_cost *= 0.8  # 20% discount
        elif request_count > 1000:
            base_cost *= 0.9  # 10% discount

        # Add data transfer costs (per GB)
        data_transfer_gb = data_transfer_bytes / (1024 ** 3)
        data_cost = data_transfer_gb * 0.10  # $0.10 per GB

        return (base_cost * request_count) + data_cost

    def get_user_usage_stats(self, user_id: str, days_back: int = 30) -> Dict[str, Any]:
        """Get usage statistics for a user"""
        cutoff_date = datetime.now() - timedelta(days=days_back)

        user_usage = [
            usage for usage in self.api_usage.values()
            if usage.user_id == user_id and usage.period_start >= cutoff_date
        ]

        total_requests = sum(usage.request_count for usage in user_usage)
        total_cost = sum(usage.cost for usage in user_usage)
        total_data_transfer = sum(usage.data_transfer_bytes for usage in user_usage)

        # Group by endpoint
        endpoint_stats = {}
        for usage in user_usage:
            if usage.api_endpoint not in endpoint_stats:
                endpoint_stats[usage.api_endpoint] = {
                    'requests': 0,
                    'cost': 0.0,
                    'data_transfer': 0
                }
            endpoint_stats[usage.api_endpoint]['requests'] += usage.request_count
            endpoint_stats[usage.api_endpoint]['cost'] += usage.cost
            endpoint_stats[usage.api_endpoint]['data_transfer'] += usage.data_transfer_bytes

        return {
            'total_requests': total_requests,
            'total_cost': total_cost,
            'total_data_transfer_gb': total_data_transfer / (1024 ** 3),
            'currency': PAYMENT_CURRENCY,
            'period_days': days_back,
            'endpoint_breakdown': endpoint_stats
        }

    # =========================================================================
    # 💰 REVENUE MANAGEMENT
    # =========================================================================

    def _record_transaction(self, user_id: str, transaction_type: str,
                           amount: float, currency: str, payment_method: str,
                           description: str, metadata: Optional[Dict] = None) -> str:
        """Record a revenue transaction"""
        transaction = RevenueTransaction(
            transaction_id=f"tx_{user_id}_{transaction_type}_{int(time.time())}",
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            status='completed',
            description=description,
            metadata=metadata,
            created_at=datetime.now(),
            processed_at=datetime.now()
        )

        self.revenue_transactions.append(transaction)
        self._save_revenue_transactions()

        logger.info(f"Recorded {transaction_type} transaction: {format_currency(amount, currency)}")
        return transaction.transaction_id

    def record_data_sale(self, user_id: str, dataset_type: str,
                        amount: float, payment_method: str = 'stripe') -> str:
        """Record revenue from data sales"""
        return self._record_transaction(
            user_id=user_id,
            transaction_type='data_sale',
            amount=amount,
            currency=PAYMENT_CURRENCY,
            payment_method=payment_method,
            description=f"Sale of {dataset_type} dataset",
            metadata={'dataset_type': dataset_type}
        )

    def record_signal_sale(self, user_id: str, signal_count: int,
                          amount: float, payment_method: str = 'stripe') -> str:
        """Record revenue from signal sales"""
        return self._record_transaction(
            user_id=user_id,
            transaction_type='signal_sale',
            amount=amount,
            currency=PAYMENT_CURRENCY,
            payment_method=payment_method,
            description=f"Sale of {signal_count} trading signals",
            metadata={'signal_count': signal_count}
        )

    def get_revenue_stats(self, days_back: int = 30) -> Dict[str, Any]:
        """Get revenue statistics"""
        cutoff_date = datetime.now() - timedelta(days=days_back)

        recent_transactions = [
            tx for tx in self.revenue_transactions
            if tx.created_at >= cutoff_date and tx.status == 'completed'
        ]

        total_revenue = sum(tx.amount for tx in recent_transactions)
        transaction_count = len(recent_transactions)

        # Group by transaction type
        type_breakdown = {}
        for tx in recent_transactions:
            if tx.transaction_type not in type_breakdown:
                type_breakdown[tx.transaction_type] = {'amount': 0.0, 'count': 0}
            type_breakdown[tx.transaction_type]['amount'] += tx.amount
            type_breakdown[tx.transaction_type]['count'] += 1

        # Group by payment method
        payment_breakdown = {}
        for tx in recent_transactions:
            if tx.payment_method not in payment_breakdown:
                payment_breakdown[tx.payment_method] = {'amount': 0.0, 'count': 0}
            payment_breakdown[tx.payment_method]['amount'] += tx.amount
            payment_breakdown[tx.payment_method]['count'] += 1

        return {
            'total_revenue': total_revenue,
            'transaction_count': transaction_count,
            'currency': PAYMENT_CURRENCY,
            'average_transaction': total_revenue / transaction_count if transaction_count > 0 else 0,
            'period_days': days_back,
            'type_breakdown': type_breakdown,
            'payment_method_breakdown': payment_breakdown
        }

    # =========================================================================
    # 🎯 TIER LIMIT CHECKS
    # =========================================================================

    def check_tier_limits(self, user_id: str, resource_type: str,
                         requested_amount: int = 1) -> Tuple[bool, str]:
        """
        Check if user can access a resource based on their tier limits

        Returns:
            (allowed: bool, message: str)
        """
        user_tier = self.get_user_tier(user_id)
        plan = self.get_plan_by_id(user_tier)

        if not plan:
            return False, "User tier not found"

        limits = plan.limits

        if resource_type == 'api_requests':
            # Check daily API limit
            usage_stats = self.get_user_usage_stats(user_id, days_back=1)
            current_usage = usage_stats.get('total_requests', 0)

            if current_usage + requested_amount > limits.get('max_requests_per_day', 100):
                return False, f"Daily API limit exceeded ({current_usage}/{limits.get('max_requests_per_day', 100)})"

        elif resource_type == 'signals':
            # Check daily signal limit
            usage_stats = self.get_user_usage_stats(user_id, days_back=1)
            signal_usage = sum(
                endpoint_data.get('requests', 0)
                for endpoint_data in usage_stats.get('endpoint_breakdown', {}).values()
                if 'signal' in endpoint_data
            )

            if signal_usage + requested_amount > limits.get('max_signals_per_day', 10):
                return False, f"Daily signal limit exceeded ({signal_usage}/{limits.get('max_signals_per_day', 10)})"

        elif resource_type == 'data_retention':
            # Check data retention limit
            retention_limit = limits.get('data_retention_days', 7)
            return True, f"Data retention: {retention_limit} days"

        return True, "Access granted"

    # =========================================================================
    # 📊 ANALYTICS & REPORTING
    # =========================================================================

    def get_user_revenue_summary(self, user_id: str) -> Dict[str, Any]:
        """Get revenue summary for a specific user"""
        user_transactions = [
            tx for tx in self.revenue_transactions
            if tx.user_id == user_id and tx.status == 'completed'
        ]

        total_spent = sum(tx.amount for tx in user_transactions)
        transaction_count = len(user_transactions)

        # Get current subscription
        subscription = self.get_user_subscription(user_id)
        current_plan = None
        if subscription:
            current_plan = self.get_plan_by_id(subscription.plan_id)

        return {
            'user_id': user_id,
            'total_spent': total_spent,
            'transaction_count': transaction_count,
            'currency': PAYMENT_CURRENCY,
            'current_plan': current_plan.name if current_plan else 'Free',
            'monthly_cost': current_plan.monthly_price if current_plan else 0,
            'transactions': [tx.to_dict() for tx in user_transactions[-10:]]  # Last 10 transactions
        }

    def get_top_revenue_sources(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top revenue generating sources"""
        # Group transactions by type and user
        revenue_by_source = {}

        for tx in self.revenue_transactions:
            if tx.status != 'completed':
                continue

            key = f"{tx.transaction_type}_{tx.user_id}"
            if key not in revenue_by_source:
                revenue_by_source[key] = {
                    'transaction_type': tx.transaction_type,
                    'user_id': tx.user_id,
                    'total_revenue': 0.0,
                    'transaction_count': 0
                }

            revenue_by_source[key]['total_revenue'] += tx.amount
            revenue_by_source[key]['transaction_count'] += 1

        # Sort by total revenue
        sorted_sources = sorted(
            revenue_by_source.values(),
            key=lambda x: x['total_revenue'],
            reverse=True
        )

        return sorted_sources[:limit]

    def calculate_lifetime_value(self, user_id: str) -> float:
        """Calculate customer lifetime value"""
        user_transactions = [
            tx for tx in self.revenue_transactions
            if tx.user_id == user_id and tx.status == 'completed'
        ]

        return sum(tx.amount for tx in user_transactions)

    def get_churn_rate(self, period_days: int = 30) -> float:
        """Calculate churn rate for the period"""
        period_start = datetime.now() - timedelta(days=period_days)

        # Get subscriptions that were cancelled in the period
        cancelled_subs = [
            sub for sub in self.user_subscriptions.values()
            if sub.status == 'cancelled' and sub.updated_at and sub.updated_at >= period_start
        ]

        # Get total active subscriptions at the start of the period
        total_active = len([
            sub for sub in self.user_subscriptions.values()
            if sub.status == 'active' and sub.created_at < period_start
        ])

        if total_active == 0:
            return 0.0

        return len(cancelled_subs) / total_active

    # =========================================================================
    # 💡 UTILITY METHODS
    # =========================================================================

    def get_pricing_display(self) -> Dict[str, Any]:
        """Get pricing information for display"""
        plans = []
        for plan in self.get_subscription_plans():
            if plan.is_active:
                plan_data = plan.to_dict()
                plan_data['monthly_formatted'] = format_currency(plan.monthly_price, plan.currency)
                plan_data['annual_formatted'] = format_currency(plan.annual_price, plan.currency)
                plan_data['savings_percent'] = format_percentage(
                    (plan.monthly_price * 12 - plan.annual_price) / (plan.monthly_price * 12)
                )
                plans.append(plan_data)

        return {
            'plans': plans,
            'currency': PAYMENT_CURRENCY,
            'api_pricing': API_PRICING
        }

# =============================================================================
# 🏭 FACTORY FUNCTION
# =============================================================================

def get_pricing_engine() -> PricingEngine:
    """
    Factory function to create pricing engine

    Returns:
        Configured PricingEngine instance
    """
    return PricingEngine()

# =============================================================================
# 🧪 TEST FUNCTIONS
# =============================================================================

def test_pricing_engine():
    """Test pricing engine functionality"""
    print("🧪 Testing ITORO Pricing Engine...")

    try:
        engine = get_pricing_engine()

        # Test plan retrieval
        plans = engine.get_subscription_plans()
        print(f"✅ Loaded {len(plans)} subscription plans")

        # Test user subscription creation
        test_user = "test_user_123"
        subscription = engine.create_user_subscription(
            user_id=test_user,
            plan_id='basic',
            payment_method='stripe',
            billing_cycle='monthly'
        )

        if subscription:
            print(f"✅ Created subscription for user {test_user}")

            # Test tier checking
            tier = engine.get_user_tier(test_user)
            print(f"✅ User tier: {tier}")

            # Test limit checking
            allowed, message = engine.check_tier_limits(test_user, 'api_requests', 50)
            print(f"✅ Limit check: {allowed} - {message}")

            # Test usage recording
            success = engine.record_api_usage(test_user, 'signal_realtime', 1024)
            print(f"✅ API usage recording: {success}")

            # Test revenue stats
            stats = engine.get_revenue_stats(days_back=7)
            print(f"✅ Revenue stats: {format_currency(stats['total_revenue'])}")

            # Test user revenue summary
            summary = engine.get_user_revenue_summary(test_user)
            print(f"✅ User revenue summary: {format_currency(summary['total_spent'])}")

        print("🎉 All pricing engine tests completed!")

    except Exception as e:
        print(f"❌ Pricing engine test failed: {e}")

if __name__ == "__main__":
    test_pricing_engine()
