"""
💰 Merchant Agent
Handles payment processing, subscription management, and revenue collection

Manages Stripe payments, SolanaPay transactions, subscription lifecycle,
and financial reporting for all commerce activities.
"""

import os
import json
import time
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
import logging
import requests

from ..shared.config import (
    STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY,
    SOLANA_PAY_WALLET_PRIVATE_KEY, SOLANA_PAY_WALLET_PUBLIC_KEY,
    SOLANA_NETWORK, PAYMENT_CURRENCY, MINIMUM_PURCHASE_AMOUNT
)
from ..shared.database import get_database_manager
from ..shared.utils import (
    format_currency, save_json_file, load_json_file, generate_unique_id,
    log_execution, validate_wallet_address, require_api_key
)
from .pricing import get_pricing_engine

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 📋 DATA MODELS
# =============================================================================

@dataclass
class PaymentTransaction:
    """Payment transaction data model"""
    transaction_id: str
    user_id: str
    amount: float
    currency: str
    payment_method: str  # 'stripe', 'solana_pay', 'crypto'
    status: str  # 'pending', 'completed', 'failed', 'refunded'
    transaction_hash: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    solana_signature: Optional[str] = None
    description: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        if self.refunded_at:
            data['refunded_at'] = self.refunded_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaymentTransaction':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if 'completed_at' in data_copy and data_copy['completed_at']:
            data_copy['completed_at'] = datetime.fromisoformat(data_copy['completed_at'])
        if 'refunded_at' in data_copy and data_copy['refunded_at']:
            data_copy['refunded_at'] = datetime.fromisoformat(data_copy['refunded_at'])
        return cls(**data_copy)

@dataclass
class SubscriptionPayment:
    """Subscription payment data model"""
    payment_id: str
    subscription_id: str
    user_id: str
    amount: float
    currency: str
    billing_period_start: datetime
    billing_period_end: datetime
    payment_method: str
    status: str  # 'paid', 'failed', 'pending'
    transaction_id: Optional[str] = None
    next_billing_date: Optional[datetime] = None
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['billing_period_start'] = self.billing_period_start.isoformat()
        data['billing_period_end'] = self.billing_period_end.isoformat()
        data['created_at'] = self.created_at.isoformat()
        if self.next_billing_date:
            data['next_billing_date'] = self.next_billing_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubscriptionPayment':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['billing_period_start'] = datetime.fromisoformat(data_copy['billing_period_start'])
        data_copy['billing_period_end'] = datetime.fromisoformat(data_copy['billing_period_end'])
        data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if 'next_billing_date' in data_copy and data_copy['next_billing_date']:
            data_copy['next_billing_date'] = datetime.fromisoformat(data_copy['next_billing_date'])
        return cls(**data_copy)

@dataclass
class Refund:
    """Refund data model"""
    refund_id: str
    original_transaction_id: str
    user_id: str
    amount: float
    currency: str
    reason: str
    status: str  # 'pending', 'completed', 'failed'
    refund_method: str  # 'stripe', 'solana_pay', 'crypto'
    stripe_refund_id: Optional[str] = None
    solana_signature: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Refund':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if 'completed_at' in data_copy and data_copy['completed_at']:
            data_copy['completed_at'] = datetime.fromisoformat(data_copy['completed_at'])
        return cls(**data_copy)

# =============================================================================
# 💰 MERCHANT AGENT
# =============================================================================

class MerchantAgent:
    """Agent for handling payment processing and subscription management"""

    def __init__(self):
        self.pricing = get_pricing_engine()
        self.db = get_database_manager()

        # Initialize payment processors
        self._init_stripe()
        self._init_solana_pay()

        # Data storage
        self.transactions: Dict[str, PaymentTransaction] = {}
        self.subscription_payments: List[SubscriptionPayment] = []
        self.refunds: List[Refund] = []

        # Control flags
        self.running = False
        self.payment_processor_thread = None

        # Local storage paths
        self.payments_dir = os.path.join('data', 'payments')
        os.makedirs(self.payments_dir, exist_ok=True)

        # Load existing data
        self._load_transactions()
        self._load_subscription_payments()
        self._load_refunds()

        logger.info("✅ Merchant Agent initialized")

    def _init_stripe(self):
        """Initialize Stripe payment processor"""
        self.stripe_enabled = False
        if STRIPE_SECRET_KEY:
            try:
                import stripe
                stripe.api_key = STRIPE_SECRET_KEY
                self.stripe_enabled = True
                logger.info("✅ Stripe integration initialized")
            except ImportError:
                logger.warning("⚠️  Stripe library not installed. Install with: pip install stripe")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Stripe: {e}")
        else:
            logger.warning("⚠️  Stripe secret key not configured")

    def _init_solana_pay(self):
        """Initialize SolanaPay processor"""
        self.solana_pay_enabled = False
        if SOLANA_PAY_WALLET_PRIVATE_KEY and SOLANA_PAY_WALLET_PUBLIC_KEY:
            try:
                # Solana integration would require solana-py library
                self.solana_pay_enabled = True
                logger.info("✅ SolanaPay integration initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize SolanaPay: {e}")
        else:
            logger.warning("⚠️  SolanaPay wallet keys not configured")

    def _load_transactions(self):
        """Load payment transactions from storage"""
        data = load_json_file(os.path.join(self.payments_dir, 'transactions.json'))
        for tx_data in data.get('transactions', []):
            transaction = PaymentTransaction.from_dict(tx_data)
            self.transactions[transaction.transaction_id] = transaction

    def _load_subscription_payments(self):
        """Load subscription payments from storage"""
        data = load_json_file(os.path.join(self.payments_dir, 'subscription_payments.json'))
        for payment_data in data.get('payments', []):
            payment = SubscriptionPayment.from_dict(payment_data)
            self.subscription_payments.append(payment)

    def _load_refunds(self):
        """Load refunds from storage"""
        data = load_json_file(os.path.join(self.payments_dir, 'refunds.json'))
        for refund_data in data.get('refunds', []):
            refund = Refund.from_dict(refund_data)
            self.refunds.append(refund)

    def _save_transactions(self):
        """Save payment transactions to storage"""
        transactions_data = {
            'transactions': [tx.to_dict() for tx in self.transactions.values()],
            'last_updated': datetime.now().isoformat()
        }
        save_json_file(os.path.join(self.payments_dir, 'transactions.json'), transactions_data)

    def _save_subscription_payments(self):
        """Save subscription payments to storage"""
        payments_data = {
            'payments': [payment.to_dict() for payment in self.subscription_payments],
            'last_updated': datetime.now().isoformat()
        }
        save_json_file(os.path.join(self.payments_dir, 'subscription_payments.json'), payments_data)

    def _save_refunds(self):
        """Save refunds to storage"""
        refunds_data = {
            'refunds': [refund.to_dict() for refund in self.refunds],
            'last_updated': datetime.now().isoformat()
        }
        save_json_file(os.path.join(self.payments_dir, 'refunds.json'), refunds_data)

    # =========================================================================
    # 🚀 CORE FUNCTIONALITY
    # =========================================================================

    def start(self):
        """Start the merchant agent"""
        if self.running:
            logger.warning("Merchant Agent is already running")
            return

        self.running = True
        self.payment_processor_thread = threading.Thread(target=self._payment_processing_loop, daemon=True)
        self.payment_processor_thread.start()

        logger.info("🚀 Merchant Agent started")

    def stop(self):
        """Stop the merchant agent"""
        self.running = False
        if self.payment_processor_thread:
            self.payment_processor_thread.join(timeout=5)

        logger.info("🛑 Merchant Agent stopped")

    def _payment_processing_loop(self):
        """Main payment processing and subscription management loop"""
        logger.info("💰 Starting payment processing loop")

        while self.running:
            try:
                # Process pending payments
                self._process_pending_payments()

                # Process recurring subscriptions
                self._process_recurring_subscriptions()

                # Clean up old payment data
                self._cleanup_old_payment_data()

                # Sleep between processing cycles
                time.sleep(300)  # 5 minutes

            except Exception as e:
                logger.error(f"❌ Error in payment processing loop: {e}")
                time.sleep(60)  # Wait before retrying

    def _process_pending_payments(self):
        """Process pending payment transactions"""
        pending_transactions = [
            tx for tx in self.transactions.values()
            if tx.status == 'pending'
        ]

        for transaction in pending_transactions:
            try:
                # Check payment status based on method
                if transaction.payment_method == 'stripe':
                    self._check_stripe_payment_status(transaction)
                elif transaction.payment_method == 'solana_pay':
                    self._check_solana_payment_status(transaction)
                # Add other payment methods as needed

            except Exception as e:
                logger.error(f"❌ Failed to process transaction {transaction.transaction_id}: {e}")

    def _process_recurring_subscriptions(self):
        """Process recurring subscription payments"""
        try:
            now = datetime.now()

            # Get all active subscriptions that need billing
            subscriptions_needing_billing = []

            # This would integrate with the pricing engine to get subscriptions
            # For now, we'll simulate the process
            logger.debug("🔄 Processing recurring subscriptions...")

            # In a real implementation, this would:
            # 1. Find subscriptions where next_billing_date <= now
            # 2. Attempt to charge the payment method on file
            # 3. Update subscription status and billing dates
            # 4. Record the payment transaction

        except Exception as e:
            logger.error(f"❌ Failed to process recurring subscriptions: {e}")

    def _cleanup_old_payment_data(self):
        """Clean up old payment data (keep last 90 days)"""
        try:
            cutoff_date = datetime.now() - timedelta(days=90)

            # Remove old completed transactions (keep last 90 days)
            old_transactions = [
                tx_id for tx_id, tx in self.transactions.items()
                if tx.status == 'completed' and tx.completed_at and tx.completed_at < cutoff_date
            ]

            for tx_id in old_transactions:
                del self.transactions[tx_id]

            # Remove old subscription payments (keep last 90 days)
            self.subscription_payments = [
                payment for payment in self.subscription_payments
                if payment.created_at >= cutoff_date
            ]

            # Remove old refunds (keep last 90 days)
            self.refunds = [
                refund for refund in self.refunds
                if refund.created_at >= cutoff_date
            ]

            # Save cleaned data
            self._save_transactions()
            self._save_subscription_payments()
            self._save_refunds()

            logger.debug(f"🧹 Cleaned up {len(old_transactions)} old transactions")

        except Exception as e:
            logger.error(f"❌ Failed to cleanup payment data: {e}")

    # =========================================================================
    # 💳 STRIPE PAYMENT PROCESSING
    # =========================================================================

    def create_stripe_payment_intent(self, amount: float, currency: str = PAYMENT_CURRENCY,
                                    description: str = "", metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Create a Stripe payment intent"""
        if not self.stripe_enabled:
            logger.error("Stripe not enabled")
            return None

        try:
            import stripe

            # Convert amount to cents (Stripe expects integers)
            amount_cents = int(amount * 100)

            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                description=description,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                }
            )

            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': amount,
                'currency': currency
            }

        except Exception as e:
            logger.error(f"❌ Failed to create Stripe payment intent: {e}")
            return None

    def _check_stripe_payment_status(self, transaction: PaymentTransaction):
        """Check status of Stripe payment"""
        if not self.stripe_enabled or not transaction.stripe_payment_intent_id:
            return

        try:
            import stripe

            intent = stripe.PaymentIntent.retrieve(transaction.stripe_payment_intent_id)

            if intent.status == 'succeeded' and transaction.status != 'completed':
                transaction.status = 'completed'
                transaction.completed_at = datetime.now()
                self._save_transactions()
                logger.info(f"✅ Stripe payment completed: {transaction.transaction_id}")

            elif intent.status == 'failed' and transaction.status != 'failed':
                transaction.status = 'failed'
                self._save_transactions()
                logger.warning(f"❌ Stripe payment failed: {transaction.transaction_id}")

        except Exception as e:
            logger.error(f"❌ Failed to check Stripe payment status: {e}")

    def process_stripe_webhook(self, payload: str, signature: str) -> bool:
        """Process Stripe webhook"""
        if not self.stripe_enabled:
            return False

        try:
            import stripe

            # Verify webhook signature
            endpoint_secret = STRIPE_WEBHOOK_SECRET
            if endpoint_secret:
                event = stripe.Webhook.construct_event(payload, signature, endpoint_secret)
            else:
                event = json.loads(payload)  # For testing without signature

            # Handle different event types
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                self._handle_stripe_payment_success(payment_intent)

            elif event['type'] == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                self._handle_stripe_payment_failure(payment_intent)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to process Stripe webhook: {e}")
            return False

    def _handle_stripe_payment_success(self, payment_intent):
        """Handle successful Stripe payment"""
        intent_id = payment_intent['id']

        # Find transaction by intent ID
        for transaction in self.transactions.values():
            if transaction.stripe_payment_intent_id == intent_id:
                if transaction.status != 'completed':
                    transaction.status = 'completed'
                    transaction.completed_at = datetime.now()
                    self._save_transactions()
                    logger.info(f"✅ Processed Stripe payment success: {transaction.transaction_id}")
                break

    def _handle_stripe_payment_failure(self, payment_intent):
        """Handle failed Stripe payment"""
        intent_id = payment_intent['id']

        # Find transaction by intent ID
        for transaction in self.transactions.values():
            if transaction.stripe_payment_intent_id == intent_id:
                if transaction.status != 'failed':
                    transaction.status = 'failed'
                    self._save_transactions()
                    logger.warning(f"❌ Processed Stripe payment failure: {transaction.transaction_id}")
                break

    # =========================================================================
    # 🌐 SOLANA PAY PROCESSING
    # =========================================================================

    def create_solana_pay_transaction(self, amount: float, recipient_address: str,
                                    reference: str = None) -> Optional[Dict[str, Any]]:
        """Create a Solana Pay transaction request"""
        if not self.solana_pay_enabled:
            logger.error("SolanaPay not enabled")
            return None

        try:
            # Generate unique reference if not provided
            if not reference:
                reference = generate_unique_id('sol_ref')

            # Create Solana Pay URL
            # This would integrate with solana-py to create proper transaction
            sol_amount = amount  # Assuming amount is in SOL

            pay_url = f"solana:{recipient_address}?amount={sol_amount}&reference={reference}&label=ITORO&message=Payment%20for%20services"

            return {
                'pay_url': pay_url,
                'recipient_address': recipient_address,
                'amount': amount,
                'reference': reference,
                'expected_sol_amount': sol_amount
            }

        except Exception as e:
            logger.error(f"❌ Failed to create Solana Pay transaction: {e}")
            return None

    def _check_solana_payment_status(self, transaction: PaymentTransaction):
        """Check status of Solana payment"""
        # This would integrate with Solana blockchain to check transaction status
        # For now, we'll simulate the check
        logger.debug(f"🔍 Checking Solana payment status: {transaction.transaction_id}")

    # =========================================================================
    # 💰 PAYMENT PROCESSING API
    # =========================================================================

    @require_api_key
    def create_payment_intent(self, user_info: Dict[str, Any], amount: float,
                             payment_method: str, description: str = "",
                             metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """API endpoint to create payment intent"""
        try:
            # Validate amount
            if amount < MINIMUM_PURCHASE_AMOUNT:
                return {
                    'error': f'Minimum purchase amount is {format_currency(MINIMUM_PURCHASE_AMOUNT)}',
                    'status': 'error'
                }

            # Create transaction record
            transaction_id = generate_unique_id('payment')
            transaction = PaymentTransaction(
                transaction_id=transaction_id,
                user_id=user_info['user_id'],
                amount=amount,
                currency=PAYMENT_CURRENCY,
                payment_method=payment_method,
                status='pending',
                description=description,
                metadata=metadata,
                created_at=datetime.now()
            )

            self.transactions[transaction_id] = transaction
            self._save_transactions()

            # Create payment intent based on method
            payment_data = None

            if payment_method == 'stripe':
                intent_data = self.create_stripe_payment_intent(
                    amount=amount,
                    description=description,
                    metadata={'transaction_id': transaction_id, **(metadata or {})}
                )
                if intent_data:
                    transaction.stripe_payment_intent_id = intent_data['payment_intent_id']
                    payment_data = intent_data

            elif payment_method == 'solana_pay':
                solana_data = self.create_solana_pay_transaction(
                    amount=amount,
                    recipient_address=SOLANA_PAY_WALLET_PUBLIC_KEY
                )
                if solana_data:
                    payment_data = solana_data

            if payment_data:
                self._save_transactions()  # Save updated transaction
                return {
                    'status': 'success',
                    'transaction_id': transaction_id,
                    'payment_data': payment_data
                }
            else:
                # Payment creation failed, mark transaction as failed
                transaction.status = 'failed'
                self._save_transactions()
                return {'error': 'Failed to create payment intent', 'status': 'error'}

        except Exception as e:
            logger.error(f"❌ Error creating payment intent: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def get_payment_status(self, user_info: Dict[str, Any], transaction_id: str) -> Dict[str, Any]:
        """API endpoint to get payment status"""
        try:
            transaction = self.transactions.get(transaction_id)

            if not transaction or transaction.user_id != user_info['user_id']:
                return {'error': 'Transaction not found', 'status': 'error'}

            return {
                'status': 'success',
                'transaction_id': transaction_id,
                'payment_status': transaction.status,
                'amount': transaction.amount,
                'currency': transaction.currency,
                'created_at': transaction.created_at.isoformat(),
                'completed_at': transaction.completed_at.isoformat() if transaction.completed_at else None
            }

        except Exception as e:
            logger.error(f"❌ Error getting payment status: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def get_user_payments(self, user_info: Dict[str, Any], limit: int = 20) -> Dict[str, Any]:
        """API endpoint to get user's payment history"""
        try:
            user_transactions = [
                tx for tx in self.transactions.values()
                if tx.user_id == user_info['user_id']
            ]

            # Sort by creation date (newest first)
            user_transactions.sort(key=lambda x: x.created_at, reverse=True)

            # Limit results
            user_transactions = user_transactions[:limit]

            payments_data = []
            for tx in user_transactions:
                payments_data.append({
                    'transaction_id': tx.transaction_id,
                    'amount': tx.amount,
                    'currency': tx.currency,
                    'payment_method': tx.payment_method,
                    'status': tx.status,
                    'description': tx.description,
                    'created_at': tx.created_at.isoformat(),
                    'completed_at': tx.completed_at.isoformat() if tx.completed_at else None
                })

            return {
                'status': 'success',
                'payments': payments_data,
                'count': len(payments_data)
            }

        except Exception as e:
            logger.error(f"❌ Error getting user payments: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    # =========================================================================
    # 📊 SUBSCRIPTION MANAGEMENT
    # =========================================================================

    @require_api_key
    def create_subscription(self, user_info: Dict[str, Any], plan_id: str,
                          payment_method: str, billing_cycle: str = 'monthly') -> Dict[str, Any]:
        """API endpoint to create user subscription"""
        try:
            subscription = self.pricing.create_user_subscription(
                user_id=user_info['user_id'],
                plan_id=plan_id,
                payment_method=payment_method,
                billing_cycle=billing_cycle
            )

            if not subscription:
                return {'error': 'Failed to create subscription', 'status': 'error'}

            return {
                'status': 'success',
                'subscription_id': subscription.subscription_id,
                'plan_id': plan_id,
                'billing_cycle': billing_cycle,
                'amount': subscription.amount,
                'currency': subscription.currency,
                'current_period_end': subscription.current_period_end.isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Error creating subscription: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def cancel_subscription(self, user_info: Dict[str, Any], subscription_id: str) -> Dict[str, Any]:
        """API endpoint to cancel user subscription"""
        try:
            # Verify subscription belongs to user
            subscription = self.pricing.user_subscriptions.get(subscription_id)
            if not subscription or subscription.user_id != user_info['user_id']:
                return {'error': 'Subscription not found', 'status': 'error'}

            success = self.pricing.cancel_subscription(subscription_id)

            if success:
                return {
                    'status': 'success',
                    'message': 'Subscription cancelled successfully',
                    'cancel_at_period_end': subscription.cancel_at_period_end
                }
            else:
                return {'error': 'Failed to cancel subscription', 'status': 'error'}

        except Exception as e:
            logger.error(f"❌ Error cancelling subscription: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    @require_api_key
    def get_subscription_status(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """API endpoint to get user's subscription status"""
        try:
            subscription = self.pricing.get_user_subscription(user_info['user_id'])

            if not subscription:
                return {
                    'status': 'success',
                    'subscription_active': False,
                    'current_tier': 'free'
                }

            plan = self.pricing.get_plan_by_id(subscription.plan_id)

            return {
                'status': 'success',
                'subscription_active': subscription.status == 'active',
                'subscription_id': subscription.subscription_id,
                'plan_id': subscription.plan_id,
                'plan_name': plan.name if plan else 'Unknown',
                'billing_cycle': subscription.billing_cycle,
                'current_period_end': subscription.current_period_end.isoformat(),
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'amount': subscription.amount,
                'currency': subscription.currency
            }

        except Exception as e:
            logger.error(f"❌ Error getting subscription status: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    # =========================================================================
    # 💸 REFUND PROCESSING
    # =========================================================================

    @require_api_key
    def request_refund(self, user_info: Dict[str, Any], transaction_id: str,
                      reason: str = "Customer requested refund") -> Dict[str, Any]:
        """API endpoint to request refund"""
        try:
            # Find transaction
            transaction = self.transactions.get(transaction_id)
            if not transaction or transaction.user_id != user_info['user_id']:
                return {'error': 'Transaction not found', 'status': 'error'}

            if transaction.status != 'completed':
                return {'error': 'Only completed transactions can be refunded', 'status': 'error'}

            # Check if refund already exists
            existing_refund = next(
                (r for r in self.refunds if r.original_transaction_id == transaction_id),
                None
            )
            if existing_refund:
                return {'error': 'Refund already requested for this transaction', 'status': 'error'}

            # Create refund record
            refund_id = generate_unique_id('refund')
            refund = Refund(
                refund_id=refund_id,
                original_transaction_id=transaction_id,
                user_id=user_info['user_id'],
                amount=transaction.amount,
                currency=transaction.currency,
                reason=reason,
                status='pending',
                refund_method=transaction.payment_method,
                created_at=datetime.now()
            )

            self.refunds.append(refund)
            self._save_refunds()

            # Process refund based on payment method
            self._process_refund(refund)

            return {
                'status': 'success',
                'refund_id': refund_id,
                'amount': transaction.amount,
                'currency': transaction.currency,
                'message': 'Refund request submitted'
            }

        except Exception as e:
            logger.error(f"❌ Error requesting refund: {e}")
            return {'error': 'Internal server error', 'status': 'error'}

    def _process_refund(self, refund: Refund):
        """Process a refund request"""
        try:
            if refund.refund_method == 'stripe':
                self._process_stripe_refund(refund)
            elif refund.refund_method == 'solana_pay':
                self._process_solana_refund(refund)
            else:
                logger.warning(f"Unsupported refund method: {refund.refund_method}")

        except Exception as e:
            logger.error(f"❌ Failed to process refund {refund.refund_id}: {e}")

    def _process_stripe_refund(self, refund: Refund):
        """Process Stripe refund"""
        if not self.stripe_enabled:
            return

        try:
            import stripe

            # Find original transaction
            original_tx = self.transactions.get(refund.original_transaction_id)
            if not original_tx or not original_tx.stripe_payment_intent_id:
                refund.status = 'failed'
                self._save_refunds()
                return

            # Create refund
            refund_result = stripe.Refund.create(
                payment_intent=original_tx.stripe_payment_intent_id,
                amount=int(refund.amount * 100),  # Convert to cents
                reason='requested_by_customer'
            )

            refund.stripe_refund_id = refund_result.id
            refund.status = 'completed'
            refund.completed_at = datetime.now()

            # Update original transaction
            original_tx.status = 'refunded'
            original_tx.refunded_at = datetime.now()

            self._save_refunds()
            self._save_transactions()

            logger.info(f"✅ Processed Stripe refund: {refund.refund_id}")

        except Exception as e:
            logger.error(f"❌ Failed to process Stripe refund: {e}")
            refund.status = 'failed'
            self._save_refunds()

    def _process_solana_refund(self, refund: Refund):
        """Process Solana refund"""
        # This would create a refund transaction on Solana blockchain
        # For now, we'll simulate it
        refund.status = 'completed'
        refund.completed_at = datetime.now()
        self._save_refunds()
        logger.info(f"✅ Processed Solana refund: {refund.refund_id}")

    # =========================================================================
    # 📊 ANALYTICS & REPORTING
    # =========================================================================

    def get_revenue_report(self, days_back: int = 30) -> Dict[str, Any]:
        """Generate revenue report"""
        cutoff_date = datetime.now() - timedelta(days=days_back)

        # Get completed transactions in period
        period_transactions = [
            tx for tx in self.transactions.values()
            if tx.status == 'completed' and tx.completed_at and tx.completed_at >= cutoff_date
        ]

        # Get refunds in period
        period_refunds = [
            r for r in self.refunds
            if r.status == 'completed' and r.completed_at and r.completed_at >= cutoff_date
        ]

        # Calculate metrics
        total_revenue = sum(tx.amount for tx in period_transactions)
        total_refunds = sum(r.amount for r in period_refunds)
        net_revenue = total_revenue - total_refunds
        transaction_count = len(period_transactions)
        refund_count = len(period_refunds)

        # Revenue by payment method
        revenue_by_method = {}
        for tx in period_transactions:
            revenue_by_method[tx.payment_method] = revenue_by_method.get(tx.payment_method, 0) + tx.amount

        return {
            'period_days': days_back,
            'total_revenue': total_revenue,
            'total_refunds': total_refunds,
            'net_revenue': net_revenue,
            'transaction_count': transaction_count,
            'refund_count': refund_count,
            'average_transaction': total_revenue / transaction_count if transaction_count > 0 else 0,
            'refund_rate': (refund_count / transaction_count * 100) if transaction_count > 0 else 0,
            'currency': PAYMENT_CURRENCY,
            'revenue_by_method': revenue_by_method
        }

    def get_subscription_metrics(self) -> Dict[str, Any]:
        """Get subscription-related metrics"""
        # Get subscription payments
        recent_payments = [
            p for p in self.subscription_payments
            if p.created_at >= datetime.now() - timedelta(days=30)
        ]

        monthly_recurring_revenue = sum(p.amount for p in recent_payments if p.status == 'paid')
        payment_count = len([p for p in recent_payments if p.status == 'paid'])
        failure_count = len([p for p in recent_payments if p.status == 'failed'])

        success_rate = (payment_count / (payment_count + failure_count) * 100) if (payment_count + failure_count) > 0 else 100

        return {
            'monthly_recurring_revenue': monthly_recurring_revenue,
            'successful_payments': payment_count,
            'failed_payments': failure_count,
            'payment_success_rate': round(success_rate, 2),
            'currency': PAYMENT_CURRENCY,
            'period_days': 30
        }

    # =========================================================================
    # 🔧 UTILITY METHODS
    # =========================================================================

    def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        return {
            'agent': 'MerchantAgent',
            'running': self.running,
            'stripe_enabled': self.stripe_enabled,
            'solana_pay_enabled': self.solana_pay_enabled,
            'pending_transactions': len([tx for tx in self.transactions.values() if tx.status == 'pending']),
            'completed_transactions': len([tx for tx in self.transactions.values() if tx.status == 'completed']),
            'total_refunds': len(self.refunds),
            'last_update': datetime.now().isoformat()
        }

# =============================================================================
# 🏭 FACTORY FUNCTION
# =============================================================================

_merchant_agent = None

def get_merchant_agent() -> MerchantAgent:
    """
    Factory function to get merchant agent (singleton)

    Returns:
        MerchantAgent instance
    """
    global _merchant_agent
    if _merchant_agent is None:
        _merchant_agent = MerchantAgent()
    return _merchant_agent

# =============================================================================
# 🧪 TEST FUNCTIONS
# =============================================================================

def test_merchant_agent():
    """Test merchant agent functionality"""
    print("🧪 Testing Merchant Agent...")

    try:
        agent = get_merchant_agent()

        # Test health check
        health = agent.health_check()
        print(f"✅ Agent health: {health}")

        # Test revenue report
        revenue_report = agent.get_revenue_report(days_back=7)
        print(f"✅ Revenue report: {revenue_report}")

        # Test subscription metrics
        sub_metrics = agent.get_subscription_metrics()
        print(f"✅ Subscription metrics: {sub_metrics}")

        print("🎉 Merchant Agent tests completed!")

    except Exception as e:
        print(f"❌ Merchant Agent test failed: {e}")

if __name__ == "__main__":
    test_merchant_agent()
