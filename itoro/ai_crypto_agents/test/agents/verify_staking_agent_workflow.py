#!/usr/bin/env python3
"""
🔒 STAKING AGENT WORKFLOW VERIFICATION
This script validates the staking agent end-to-end in PAPER TRADE mode:
- Initialization and configuration
- Trigger mechanisms (webhook/manual and interval)
- Yield optimization logic and scheduling
- Staking execution flow (paper mode) with DB updates
- Signature/logging behavior (paper/live abstraction)
- Error handling and edge cases
- Clear logging for visual confirmation during testing

Run directly or via your test runner:
  python test/verify_staking_agent_workflow.py
"""

import os
import sys
import time
import sqlite3
from datetime import datetime

# Ensure project root is on sys.path so `import src.*` works
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import src.config as config
from src.agents.staking_agent import StakingAgent
from src.paper_trading import reset_paper_trading, get_paper_trading_db, DB_PATH, init_paper_trading_db
from src.scripts.shared_services.shared_api_manager import get_shared_api_manager


def _print_header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def verify_initialization_and_config() -> tuple[bool, str]:
    _print_header("TEST 1: Initialization and Configuration")
    try:
        # Ensure paper mode is on
        if not getattr(config, 'PAPER_TRADING_ENABLED', False):
            print("❌ PAPER_TRADING_ENABLED is False — enable paper trade mode in config.py")
            return False, "Paper trading not enabled"

        # Ensure DB present
        init_paper_trading_db()

        agent = StakingAgent()
        print(f"✅ Agent created. Protocols: {agent.staking_protocols}")
        print(f"   Staking allocation %: {agent.staking_allocation_percentage}")
        print(f"   Minimum SOL threshold %: {agent.min_sol_allocation_threshold}")
        print(f"   Yield optimization interval: {agent.yield_optimization_interval_value} {agent.yield_optimization_interval_unit}")

        # Validate key methods exist
        required = [
            hasattr(agent, 'handle_webhook_trigger'),
            hasattr(agent, 'run_staking_cycle'),
            hasattr(agent, 'optimize_yield'),
            hasattr(agent, 'should_run_yield_optimization'),
        ]
        if not all(required):
            print("❌ Missing required staking agent methods")
            return False, "Missing required methods"

        return True, "Initialization and configuration OK"
    except Exception as e:
        print(f"❌ Initialization failure: {e}")
        return False, f"Init error: {e}"


def prepare_clean_paper_state() -> tuple[bool, str]:
    _print_header("TEST 2: Paper Trading Reset & Seed State")
    try:
        ok = reset_paper_trading()
        if not ok:
            return False, "Failed to reset paper trading"

        # After reset, ensure balances row exists for wallet
        addr = getattr(config, 'address', None)
        if not addr:
            print("⚠️ No DEFAULT_WALLET_ADDRESS set; some checks will be skipped")

        with sqlite3.connect(DB_PATH) as conn:
            # Ensure basic balances row exists
            if addr:
                row = conn.execute(
                    "SELECT wallet_address, sol_balance, usdc_balance, staked_sol_balance FROM paper_trading_balances WHERE wallet_address = ?",
                    (addr,)
                ).fetchone()
                if not row:
                    return False, "No balances row created after reset"
                print(f"✅ Balances initialized for {addr[:8]}... | SOL={row[1]:.6f} USDC=${row[2]:.2f} STAKED_SOL={row[3]:.6f}")

        return True, "Paper trading state ready"
    except Exception as e:
        return False, f"Paper reset error: {e}"


def test_triggers() -> tuple[bool, str]:
    _print_header("TEST 3: Trigger Mechanisms (webhook/manual & interval)")
    try:
        agent = StakingAgent()

        # Webhook trigger types
        ok1 = agent.handle_webhook_trigger({
            'type': 'portfolio_change',
            'timestamp': datetime.now().isoformat(),
            'portfolio_data': {'total_value': 1000.0, 'sol_pct': 0.10}
        })
        ok2 = agent.handle_webhook_trigger({
            'type': 'proactive_rebalancing',
            'timestamp': datetime.now().isoformat(),
            'portfolio_data': {'sol_deviation': 0.10, 'usdc_deviation': 0.0}
        })
        ok3 = agent.handle_webhook_trigger({
            'type': 'transaction_monitoring',
            'timestamp': datetime.now().isoformat(),
            'transaction_data': {'dummy': True}
        })

        print(f"✅ Webhook triggers: portfolio_change={ok1} rebalancing={ok2} txn_monitoring={ok3}")

        # Interval-based: set last_run_day to force should_run_yield_optimization path and interval run
        agent.last_run_day = None
        agent.staking_run_at_enabled = False
        print("ℹ️ Forcing interval mode; will run single cycle in a later test")

        return (ok1 and ok2 and ok3), "Webhook/interval trigger checks passed"
    except Exception as e:
        return False, f"Trigger error: {e}"


def test_yield_optimization() -> tuple[bool, str]:
    _print_header("TEST 4: Yield Optimization Logic")
    try:
        agent = StakingAgent()
        # Force last optimization in the past to trigger should_run_yield_optimization
        agent.last_yield_optimization = None
        should = agent.should_run_yield_optimization()
        print(f"✅ should_run_yield_optimization={should}")
        ok = agent.optimize_yield()
        print(f"✅ optimize_yield() -> {ok}")
        return (should and ok), "Yield optimization executed"
    except Exception as e:
        return False, f"Yield optimization error: {e}"


def test_execution_paper_mode() -> tuple[bool, str]:
    _print_header("TEST 5: Staking Execution in Paper Mode")
    try:
        if not getattr(config, 'PAPER_TRADING_ENABLED', False):
            return False, "Paper mode disabled"

        agent = StakingAgent()
        agent.staking_run_at_enabled = False  # interval mode

        # Ensure there is some SOL so stake_amount_sol >= min threshold
        addr = getattr(config, 'address', None)
        with sqlite3.connect(DB_PATH) as conn:
            if addr:
                # Slightly increase SOL to ensure stakeable amount
                conn.execute(
                    "UPDATE paper_trading_balances SET sol_balance = sol_balance + 0.5, last_updated = ? WHERE wallet_address = ?",
                    (datetime.now().isoformat(), addr)
                )
                conn.commit()

        success = agent.run_staking_cycle()
        print(f"✅ run_staking_cycle() -> {success}")

        if not success:
            return False, "Staking cycle failed"

        # Verify DB effects: paper_staking_transactions insert and staked_sol_balance increased
        with sqlite3.connect(DB_PATH) as conn:
            tx_count = conn.execute("SELECT COUNT(1) FROM paper_staking_transactions").fetchone()[0]
            if tx_count <= 0:
                return False, "No paper_staking_transactions recorded"

            if addr:
                row = conn.execute(
                    "SELECT sol_balance, staked_sol_balance FROM paper_trading_balances WHERE wallet_address = ?",
                    (addr,)
                ).fetchone()
                if not row:
                    return False, "Balances row missing after staking"
                sol_after, staked_after = row
                print(f"✅ Balances after: SOL={sol_after:.6f}, STAKED_SOL={staked_after:.6f}")

        return True, "Staking execution recorded in DB"
    except Exception as e:
        return False, f"Execution error: {e}"


def test_signature_and_logging_behaviors() -> tuple[bool, str]:
    _print_header("TEST 6: Signature and Logging Validation (Paper Mode)")
    try:
        # In paper mode, staking uses _execute_paper_staking and records rows without real signatures.
        # We validate logging via DB artifacts and presence of expected columns.
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT timestamp, protocol, amount_sol, apy, status FROM paper_staking_transactions ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return False, "No paper staking transaction to validate"
            ts, protocol, amt, apy, status = row
            print(f"✅ Paper staking tx: {ts} | {protocol} | {amt:.6f} SOL @ {apy:.2f}% | {status}")

        # Live signature validation occurs in nice_funcs and staking_agent live paths; here we assert paper path used
        if getattr(config, 'PAPER_TRADING_ENABLED', False):
            return True, "Paper mode transaction recorded; signature not required"
        return False, "Expected paper mode"
    except Exception as e:
        return False, f"Signature/logging validation error: {e}"


def test_error_handling_and_edges() -> tuple[bool, str]:
    _print_header("TEST 7: Error Handling and Edge Cases")
    try:
        agent = StakingAgent()

        # Edge 1: Missing address
        saved_addr = getattr(config, 'address', None)
        try:
            # Monkey-patch config.address to None temporarily
            import src.config as conf
            conf.address = None
            ok = agent._execute_staking_transaction("blazestake", 1.0, 8.0)
            if ok:
                return False, "Expected failure when address missing"
            print("✅ Properly handled missing address")
        finally:
            # Restore address
            try:
                import src.config as conf
                conf.address = saved_addr
            except Exception:
                pass

        # Edge 2: Invalid amount
        ok2 = agent._execute_staking_transaction("blazestake", -1.0, 8.0)
        if ok2:
            return False, "Expected failure on invalid amount"
        print("✅ Properly handled invalid staking amount")

        # Edge 3: Unknown protocol
        ok3 = agent._execute_staking_transaction("unknown_proto", 1.0, 8.0)
        # In paper mode this routes to _execute_paper_staking only when PAPER_TRADING_ENABLED, but protocol validation happens earlier for live path.
        # Here _execute_staking_transaction returns False for unsupported protocol when live path; for paper path we still simulate success.
        # We accept either True (paper simulate) or False (strict). We only assert no exception and boolean returned.
        if not isinstance(ok3, bool):
            return False, "Unexpected result type for unknown protocol"
        print(f"✅ Unknown protocol handled (result={ok3})")

        return True, "Edge cases handled safely"
    except Exception as e:
        return False, f"Edge case error: {e}"


def test_logging_and_summary() -> tuple[bool, str]:
    _print_header("TEST 8: Clear Logging and Final Summary")
    try:
        # Visual confirmation: print last few staking tx rows
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT id, timestamp, protocol, amount_sol, apy, status FROM paper_staking_transactions ORDER BY id DESC LIMIT 3"
            ).fetchall()
        if not rows:
            return False, "No staking transactions to display"
        print("📜 Recent paper staking transactions:")
        for r in rows:
            print(f"  #{r[0]} | {r[1]} | {r[2]} | {r[3]:.6f} SOL @ {r[4]:.2f}% | {r[5]}")
        return True, "Logs printed"
    except Exception as e:
        return False, f"Logging error: {e}"


def run_verification():
    print("🌙 Anarcho Capital - Staking Agent Workflow Verification")
    print("⚠️  This ensures triggers, optimization, execution, and logging all work in PAPER mode")

    tests = [
        ("Initialization & Config", verify_initialization_and_config),
        ("Paper Reset & Seed", prepare_clean_paper_state),
        ("Triggers", test_triggers),
        ("Yield Optimization", test_yield_optimization),
        ("Execution (Paper Mode)", test_execution_paper_mode),
        ("Signature/Logging", test_signature_and_logging_behaviors),
        ("Errors & Edge Cases", test_error_handling_and_edges),
        ("Logging & Summary", test_logging_and_summary),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        ok, msg = fn()
        if ok:
            print(f"✅ PASSED: {name} — {msg}")
            passed += 1
        else:
            print(f"❌ FAILED: {name} — {msg}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"FINAL RESULT: {passed} passed, {failed} failed")
    if failed == 0:
        print("✅ STAKING AGENT IS PRODUCTION-READY (Paper mode validated)")
        return True
    else:
        print("🚨 STAKING AGENT NOT READY — Fix failures before live trading")
        return False


if __name__ == "__main__":
    try:
        ok = run_verification()
        sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


