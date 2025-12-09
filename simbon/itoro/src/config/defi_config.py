"""
🌙 Anarcho Capital's DeFi Configuration
Comprehensive DeFi lending and borrowing automation settings
Built with love by Anarcho Capital 🚀
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# 🔗 DEFI PROTOCOL CONFIGURATION
# =============================================================================

# Primary DeFi Protocols (Recommended for Beginners)
DEFI_PROTOCOLS = {
    'solend': {
        'name': 'Solend',
        'address': 'So1endDq2YkqhipRh3WViPa8hdiSpxWy6z3Z6tMCpAo',
        'risk_level': 'low',
        'max_allocation': 0.15,  # 15% of portfolio
        'min_tvl_usd': 100000000,  # $100M minimum TVL
        'audit_status': 'audited',
        'audit_date': '2024-01-15',
        'auditor': 'Trail of Bits',
        'enabled': True,
        'priority': 1
    },
    'mango': {
        'name': 'Mango Markets',
        'address': 'MangoCzJ36AjZyKwVj3VnYU4GTonjfVEnJmvvWaxLac',
        'risk_level': 'medium_high',
        'max_allocation': 0.10,  # 10% of portfolio
        'min_tvl_usd': 50000000,  # $50M minimum TVL
        'audit_status': 'audited',
        'audit_date': '2024-02-20',
        'auditor': 'ConsenSys Diligence',
        'enabled': True,
        'priority': 2
    },
    'tulip': {
        'name': 'Tulip Protocol',
        'address': 'TuLipcqtGVXPQXRqK6W4uSJZVU4FfXDt3xea4qKtJhBn',
        'risk_level': 'high',
        'max_allocation': 0.05,  # 5% of portfolio
        'min_tvl_usd': 25000000,  # $25M minimum TVL
        'audit_status': 'audited',
        'audit_date': '2024-03-10',
        'auditor': 'OpenZeppelin',
        'enabled': True,
        'priority': 3
    }
}

# Secondary Protocols (Advanced users)
SECONDARY_PROTOCOLS = {
    'francium': {
        'name': 'Francium',
        'address': 'FRAXvDnJwWw5TQnYw6n7J2QnYw6n7J2QnYw6n7J2Qn',
        'risk_level': 'high',
        'max_allocation': 0.03,  # 3% of portfolio
        'enabled': False,  # Disabled by default
        'priority': 4
    },
    'orca': {
        'name': 'Orca',
        'address': 'orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE',
        'risk_level': 'medium',
        'max_allocation': 0.05,  # 5% of portfolio
        'enabled': False,  # Disabled by default
        'priority': 5
    }
}

# =============================================================================
# 🛡️ RISK MANAGEMENT CONFIGURATION
# =============================================================================

# Capital Protection (Tier 1)
CAPITAL_PROTECTION = {
    'max_defi_allocation': 0.30,  # Maximum 30% of total portfolio
    'single_protocol_limit': 0.15,  # Maximum 15% in single protocol
    'emergency_reserve': 0.20,  # Always maintain 20% in USDC/SOL
    'gradual_entry_start': 0.05,  # Start with 5% allocation
    'gradual_entry_months': 3,  # Scale up over 3 months
}

# Liquidation Protection (Tier 2)
LIQUIDATION_PROTECTION = {
    'liquidation_buffer': 0.25,  # 25% above liquidation threshold
    'collateral_diversification': True,  # Spread across multiple protocols
    'auto_rebalancing': True,  # Automatic collateral adjustment
    'max_collateral_ratio': 0.80,  # Maximum 80% collateral utilization
    'min_collateral_ratio': 0.50,  # Minimum 50% collateral utilization
}

# Smart Contract Risk (Tier 3)
SMART_CONTRACT_RISK = {
    'audit_required': True,  # Only use audited protocols
    'min_audit_age_months': 6,  # Audits within last 6 months
    'time_locked_operations': True,  # 24-hour delay for large transactions
    'multi_sig_support': True,  # Use hardware wallet for large operations
    'insurance_coverage': False,  # Consider DeFi insurance protocols
}

# =============================================================================
# 💰 BORROWING APPROVAL & BALANCE REQUIREMENTS
# =============================================================================

# Manual Approval System
BORROWING_APPROVAL = {
    'requires_manual_approval': True,
    'auto_approval_limit_usd': 100.0,  # $100 auto-approval
    'telegram_approval_limit_usd': 500.0,  # $500 Telegram approval
    'web_approval_limit_usd': 1000.0,  # $1000+ web interface approval
    'approval_timeout_minutes': 30,  # 30 minutes to approve
    'emergency_override': True,  # Allow emergency override
}

# Account Balance Requirements
BORROWING_REQUIREMENTS = {
    'min_total_balance_usd': 1000.0,  # Minimum $1000 portfolio
    'min_stablecoin_balance_usd': 200.0,  # Minimum $200 USDC
    'min_sol_balance': 2.0,  # Minimum 2 SOL
    'max_borrowing_ratio': 0.30,  # Max 30% of portfolio borrowed
    'emergency_reserve_usd': 500.0,  # Always keep $500 available
    'min_collateral_ratio': 1.5,  # Minimum 150% collateralization
}

# =============================================================================
# 📡 EVENT-DRIVEN ARCHITECTURE CONFIGURATION
# =============================================================================

# Webhook Integration
WEBHOOK_INTEGRATION = {
    'enabled': True,
    'helius_webhooks': True,  # Use existing Helius webhook system
    'defi_specific_events': True,  # DeFi-specific event monitoring
    'event_retention_hours': 24,  # Keep events for 24 hours
    'max_concurrent_events': 100,  # Maximum concurrent event processing
}

# Event Triggers for Lending
LENDING_EVENT_TRIGGERS = {
    'yield_change_threshold': 0.05,  # 5% APY change triggers lending
    'new_opportunity_threshold': 0.10,  # 10% better yield triggers action
    'risk_threshold_breach': 0.20,  # 20% risk increase triggers review
    'market_sentiment_threshold': 0.7,  # 70% bullish sentiment required
    'portfolio_change_threshold': 0.05,  # 5% portfolio change triggers review
}

# Event Triggers for Risk Management
RISK_EVENT_TRIGGERS = {
    'liquidation_warning_threshold': 0.20,  # 20% liquidation risk
    'portfolio_loss_threshold': 0.15,  # 15% portfolio loss in 24h
    'protocol_issue_threshold': 0.50,  # 50% protocol problem severity
    'market_crash_threshold': 0.30,  # 30% market decline in 4h
    'volatility_threshold': 0.25,  # 25% volatility increase
}

# =============================================================================
# 🤖 AUTOMATION STRATEGY CONFIGURATION
# =============================================================================

# Lending Automation
LENDING_AUTOMATION = {
    'enabled': True,
    'auto_lending': True,  # Automatic lending based on events
    'yield_optimization': True,  # Move funds to higher yields
    'portfolio_rebalancing': True,  # Rebalance based on opportunities
    'cross_protocol_arbitrage': True,  # Enabled for cross-protocol strategy
}

# =============================================================================
# 🔄 CROSS-PROTOCOL STRATEGY CONFIGURATION
# =============================================================================

CROSS_PROTOCOL_CONFIG = {
    'rate_monitoring_interval': 300,  # 5 minutes (in seconds)
    'min_migration_spread': 0.02,  # 2% minimum spread to justify migration
    'max_migration_frequency_days': 7,  # Don't migrate more than once per week
    'arbitrage_min_spread': 0.03,  # 3% minimum arbitrage spread
    'migration_cost_sol': 0.01,  # Estimated cost per migration (unstake + restake)
    'enable_auto_migration': True,  # Enable automatic protocol migration
    'enable_arbitrage': True,  # Enable cross-protocol arbitrage for 19-23% APY target
}

# Borrowing Automation
BORROWING_AUTOMATION = {
    'enabled': True,
    'auto_borrowing': False,  # Always require approval for borrowing
    'collateral_management': True,  # Automatic collateral adjustment
    'liquidation_protection': True,  # Automatic liquidation prevention
    'debt_optimization': True,  # Optimize debt across protocols
}

# Yield Farming Automation
YIELD_FARMING_AUTOMATION = {
    'enabled': True,
    'auto_compounding': True,  # Automatic reward reinvestment
    'impermanent_loss_protection': True,  # Monitor and protect against IL
    'liquidity_provision': True,  # Provide liquidity to pools
    'staking_rewards': True,  # Stake tokens for additional rewards
}

# =============================================================================
# 📊 PORTFOLIO DIVERSIFICATION CONFIGURATION
# =============================================================================

# Asset Allocation Strategy
ASSET_ALLOCATION = {
    'stablecoins': 0.40,  # 40% in stablecoins (USDC, USDT)
    'blue_chip_defi': 0.30,  # 30% in blue-chip DeFi tokens
    'yield_farming': 0.20,  # 20% in yield farming opportunities
    'cash_reserve': 0.10,  # 10% in emergency cash reserve
}

# Protocol Diversification
PROTOCOL_DIVERSIFICATION = {
    'primary_protocols': 0.50,  # 50% in established protocols
    'secondary_protocols': 0.30,  # 30% in emerging protocols
    'experimental_protocols': 0.20,  # 20% in new opportunities
}

# Correlation Limits
CORRELATION_LIMITS = {
    'max_position_correlation': 0.30,  # Maximum 30% correlation
    'max_sector_allocation': 0.40,  # Maximum 40% in single sector
    'max_protocol_allocation': 0.15,  # Maximum 15% in single protocol
}

# =============================================================================
# 🚨 EMERGENCY STOP & MANUAL OVERRIDE CONFIGURATION
# =============================================================================

# Emergency Stop Triggers
EMERGENCY_STOP_TRIGGERS = {
    'portfolio_loss_24h': 0.15,  # 15% loss in 24 hours
    'protocol_issues': True,  # Smart contract vulnerabilities
    'market_crash_4h': 0.30,  # 30% market decline in 4 hours
    'liquidation_risk': 0.10,  # 10% above liquidation threshold
    'system_anomalies': True,  # Unusual system behavior
}

# Manual Override Capabilities
MANUAL_OVERRIDE = {
    'immediate_stop': True,  # Stop all DeFi operations
    'selective_closure': True,  # Close specific positions
    'collateral_adjustment': True,  # Add/remove collateral
    'protocol_switching': True,  # Move to safer protocols
    'emergency_withdrawal': True,  # Emergency fund withdrawal
}

# =============================================================================
# 📱 TELEGRAM BOT INTEGRATION CONFIGURATION
# =============================================================================

# Telegram Bot Settings
TELEGRAM_BOT = {
    'enabled': False,  # Disabled for autonomous passive income strategy
    'bot_token': os.getenv('TELEGRAM_BOT_API', ''),
    'chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
    'notification_levels': ['critical', 'warning', 'info'],
    'auto_approval_enabled': True,
    'approval_timeout_minutes': 30,
    'daily_summary': True,  # Send daily portfolio summary
    'real_time_alerts': True,  # Real-time risk alerts
}

# Telegram Commands
TELEGRAM_COMMANDS = {
    '/status': 'Get current DeFi portfolio status',
    '/approve': 'Approve pending borrowing request',
    '/reject': 'Reject pending borrowing request',
    '/stop': 'Emergency stop all DeFi operations',
    '/resume': 'Resume DeFi operations after emergency stop',
    '/risk': 'Get current risk assessment',
    '/yields': 'Get current yield opportunities',
    '/help': 'Show available commands',
}

# =============================================================================
# 🔍 MONITORING & ALERTING CONFIGURATION
# =============================================================================

# Real-Time Monitoring
REAL_TIME_MONITORING = {
    'enabled': True,
    'portfolio_tracking': True,  # Real-time portfolio monitoring
    'yield_tracking': True,  # Automated yield comparison
    'risk_metrics': True,  # Continuous risk assessment
    'liquidation_monitoring': True,  # Liquidation risk monitoring
}

# Alert System
ALERT_SYSTEM = {
    'critical_alerts': True,  # Liquidation warnings, protocol issues
    'warning_alerts': True,  # Yield drops, high volatility
    'info_alerts': True,  # Position updates, yield changes
    'telegram_notifications': True,  # Send alerts to Telegram
    'email_notifications': False,  # Email notifications (future feature)
    'webhook_notifications': True,  # Webhook notifications
}

# =============================================================================
# ⛽ GAS OPTIMIZATION CONFIGURATION
# =============================================================================

# Solana Gas Optimization
SOLANA_GAS_OPTIMIZATION = {
    'batch_transactions': True,  # Group multiple operations
    'priority_fees': True,  # Use priority fees for important transactions
    'timing_optimization': True,  # Execute during low-congestion periods
    'rpc_selection': True,  # Use optimal RPC endpoints
    'max_retries': 3,  # Maximum transaction retry attempts
    'retry_delay_seconds': 2,  # Delay between retries
}

# =============================================================================
# 📈 YIELD OPTIMIZATION CONFIGURATION
# =============================================================================

# Yield Optimization Strategy
YIELD_OPTIMIZATION = {
    'enabled': True,
    'ai_driven': True,  # Use AI for yield optimization
    'cross_protocol': True,  # Compare yields across protocols
    'risk_adjusted': True,  # Consider risk in yield decisions
    'compounding': True,  # Automatic reward reinvestment
    'rebalancing': True,  # Rebalance based on yield opportunities
}

# Yield Thresholds
YIELD_THRESHOLDS = {
    'min_apy_threshold': 0.05,  # Minimum 5% APY to consider
    'target_apy_threshold': 0.10,  # Target 10% APY
    'excellent_apy_threshold': 0.20,  # Excellent 20%+ APY
    'yield_improvement_threshold': 0.02,  # 2% improvement to trigger move
}

# =============================================================================
# 🔄 IMPERMANENT LOSS PROTECTION CONFIGURATION
# =============================================================================

# Impermanent Loss Protection
IMPERMANENT_LOSS_PROTECTION = {
    'enabled': True,
    'monitoring': True,  # Real-time IL calculation
    'exit_triggers': True,  # Automatic exit at IL thresholds
    'hedging': False,  # IL hedging strategies (future feature)
    'max_il_threshold': 0.05,  # 5% maximum IL before exit
    'il_warning_threshold': 0.03,  # 3% IL warning threshold
}

# =============================================================================
# 🎯 LIQUIDATION THRESHOLD MANAGEMENT CONFIGURATION
# =============================================================================

# Liquidation Threshold Strategy
LIQUIDATION_THRESHOLD_MANAGEMENT = {
    'warning_level': 0.30,  # 30% above liquidation
    'action_level': 0.20,  # 20% above liquidation
    'emergency_level': 0.15,  # 15% above liquidation
    'auto_adjustment': True,  # Automatic collateral adjustment
    'manual_intervention': True,  # Manual intervention for large positions
}

# =============================================================================
# 🚀 PHASED ROLLOUT CONFIGURATION
# =============================================================================

# Phase 1: Testing (Month 1)
PHASE_1_CONFIG = {
    'allocation_percentage': 0.05,  # 5% of portfolio
    'protocols': ['solend'],  # Solend only
    'operations': ['lending'],  # Lending only, no borrowing
    'monitoring': 'manual',  # Manual oversight
    'ai_enabled': False,  # No AI initially
    'auto_approval': True,  # Auto-approve small operations
}

# Phase 2: Expansion (Month 2)
PHASE_2_CONFIG = {
    'allocation_percentage': 0.15,  # 15% of portfolio
    'protocols': ['solend', 'mango'],  # Solend + Mango
    'operations': ['lending', 'basic_borrowing'],  # Lending + basic borrowing
    'monitoring': 'automated',  # Automated with manual override
    'ai_enabled': True,  # Enable AI for basic decisions
    'auto_approval': True,  # Auto-approve medium operations
}

# Phase 3: Optimization (Month 3)
PHASE_3_CONFIG = {
    'allocation_percentage': 0.30,  # 30% of portfolio
    'protocols': ['solend', 'mango', 'tulip'],  # Full protocol suite
    'operations': ['full_defi'],  # Full DeFi operations
    'monitoring': 'fully_automated',  # Fully automated with AI
    'ai_enabled': True,  # Full AI optimization
    'auto_approval': True,  # Auto-approve most operations
}

# Current Phase (start with Phase 1)
CURRENT_PHASE = 1

# =============================================================================
# 🔧 UTILITY FUNCTIONS
# =============================================================================

def get_current_phase_config():
    """Get configuration for current deployment phase"""
    if CURRENT_PHASE == 1:
        return PHASE_1_CONFIG
    elif CURRENT_PHASE == 2:
        return PHASE_2_CONFIG
    elif CURRENT_PHASE == 3:
        return PHASE_3_CONFIG
    else:
        return PHASE_1_CONFIG

def is_protocol_enabled(protocol_name):
    """Check if a protocol is enabled in current phase"""
    current_config = get_current_phase_config()
    return protocol_name in current_config['protocols']

def get_max_allocation(protocol_name):
    """Get maximum allocation for a protocol"""
    if protocol_name in DEFI_PROTOCOLS:
        return DEFI_PROTOCOLS[protocol_name]['max_allocation']
    return 0.0

def validate_telegram_config():
    """Validate Telegram bot configuration"""
    if not TELEGRAM_BOT['bot_token']:
        print("WARNING: TELEGRAM_BOT_API not configured")
        return False
    if not TELEGRAM_BOT['chat_id']:
        print("WARNING: TELEGRAM_CHAT_ID not configured")
        return False
    return True

# =============================================================================
# 🔄 LEVERAGE LOOP CONFIGURATION
# =============================================================================

LEVERAGE_LOOP_CONFIG = {
    'enabled': True,
    'max_leverage_ratio': 3.0,  # Maximum 3x leverage (conservative)
    'collateral_tokens': ['SOL', 'stSOL', 'USDC'],
    'borrowing_tokens': ['USDC'],  # Only borrow USDC for now
    'min_interest_spread': 0.02,  # 2% minimum spread between borrow/lend rates
    'liquidation_buffer': 0.30,  # Keep 30% buffer above liquidation
    'max_loop_iterations': 3,  # Max 3 loops (conservative)
    'emergency_grace_period_hours': 24,  # 24h to unwind before liquidation
    # Dynamic minimum threshold based on position size
    'min_threshold_usd': 25.0,  # Base minimum $25
    'min_threshold_percentage': 0.015,  # 1.5% of portfolio (allows $15+ leverage loops)
    'max_threshold_usd': 100.0,  # Cap at $100 minimum
    # Recursive leverage strategy configuration
    'recursive_leverage_enabled': True,  # Enable recursive compounding leverage
    'swap_to_collateral_enabled': True,  # Swap borrowed USDC back to collateral
    'max_iterations_before_lending': 3,  # Complete all borrows before lending
    'stake_after_swap': False,  # Whether to stake swapped SOL to stSOL (optional)
}

# =============================================================================
# 🕐 INTERVAL CONFIGURATION - 1 DAY (COMPLEMENTS 3-DAY STAKING)
# =============================================================================

DEFI_INTERVAL_CONFIG = {
    'enabled': True,
    'interval_minutes': 1440,  # 1 day intervals
    'timing_complements_staking': True,
    'checks_per_staking_cycle': 3,  # 3 checks per staking cycle (3 days)
}

# Scheduled execution times
DEFI_SCHEDULED_RUNS = {
    'morning': '08:00',   # Morning opportunity check
    'evening': '20:00'    # Evening risk check + opportunity scan
}

# =============================================================================
# 🎯 EVENT TRIGGER - stSOL ONLY
# =============================================================================

DEFI_EVENT_TRIGGERS = {
    'staking_complete_trigger': True,      # Trigger when new stSOL minted
    'staked_sol_only': True,               # ONLY stSOL triggers events
    'staked_sol_threshold_usd': 1.0,      # Minimum $1 increase
    'cooldown_minutes': 60,               # 1 hour cooldown
    'ignore_sol_usdc_changes': True,      # Don't trigger on SOL/USDC changes
}

# =============================================================================
# 🛡️ SAFETY MECHANISMS - PORTFOLIO PROTECTION
# =============================================================================

DEFI_SAFETY_CONFIG = {
    # USDC Protection (CRITICAL - Your system needs 20% USDC minimum)
    'usdc_minimum_percent': 0.20,        # 20% minimum (from config)
    'usdc_emergency_percent': 0.15,     # 15% emergency threshold
    'usdc_target_percent': 0.20,         # Target 20%
    'prevent_usdc_drainage': True,
    
    # SOL Protection (CRITICAL - Keep target at 10%)
    'sol_maximum_percent': 0.20,        # Cap at 20% (from config)
    'sol_target_percent': 0.10,         # Target 10% (from config)
    'sol_fee_reserve_percent': 0.05,    # 5% for fees
    'prevent_sol_drainage': True,
    
    # Emergency Stop Conditions
    'emergency_reserve_usdc_percent': 0.10,  # 10% absolute minimum
    'emergency_reserve_sol_percent': 0.02,   # 2% absolute minimum
    'auto_stop_on_breach': True,
    'stop_trading_on_danger': True,
}

# =============================================================================
# 💎 CAPITAL SOURCES - ONLY IDLE TOKENS
# =============================================================================

DEFI_CAPITAL_SOURCES = {
    # These tokens can be used for leverage (from EXCLUDED_TOKENS)
    'available_assets': ['SOL', 'stSOL', 'USDC'],
    
    # Priority: Use stSOL first (from staking), then idle SOL/USDC
    'priority_order': ['stSOL', 'SOL', 'USDC'],
    
    # Safety: Only use if above minimum reserves
    'use_staked_sol': True,      # Can use stSOL from liquid staking
    'use_idle_sol': True,         # Can use idle SOL above fee reserve
    'use_idle_usdc': True,        # Can use USDC above 20% minimum
}

# =============================================================================
# 🤖 AI INTEGRATION CONFIGURATION
# =============================================================================

LEVERAGE_AI_CONFIG = {
    'enabled': True,
    'model': 'deepseek',  # Use DeepSeek for decisions
    'use_chart_sentiment': True,  # Factor in chart analysis
    'bullish_leverage_multiplier': 1.2,  # 20% more leverage in bull markets
    'bearish_leverage_multiplier': 0.8,  # 20% less leverage in bear markets
    'neutral_leverage_multiplier': 1.0,  # Standard leverage in neutral markets
}

# Validate configuration on import
if __name__ == "__main__":
    print("✅ DeFi configuration loaded successfully")
    if not validate_telegram_config():
        print("⚠️  Telegram bot configuration incomplete")
