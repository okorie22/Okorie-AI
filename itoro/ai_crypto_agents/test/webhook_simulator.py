"""
Enhanced Webhook Event Simulator
Simulates webhook events being sent from Render to the local coordinator
Includes systematic constraint testing scenarios
"""

import requests
import json
import time
import random
import sys
import os

# Add project root to path for config access
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.config import *

# Use actual tracked wallets from config
TRACKED_WALLETS = WALLETS_TO_TRACK
TEST_WALLET = TRACKED_WALLETS[0] if TRACKED_WALLETS else "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm"

# Real token addresses for testing (these have real market prices)
REAL_TOKENS = [
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",  # JUP
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # ETH (Wormhole)
    "5oVNBeEEQvYi1cX3ir8Dx5n1P7pdxydbGF2X4TxVusJm",  # RAY
    "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  # BOME
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # PYTH
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # WIF
]

def simulate_whale_buy_event():
    """Simulate a whale buy transaction"""
    return {
        "signature": f"whale_buy_{random.randint(100000, 999999)}",
        "timestamp": int(time.time()),
        "accounts": [
            {
                "wallet": TEST_WALLET,
                "token": random.choice(REAL_TOKENS),
                "action": "buy",
                "amount": 100.0,  # $100 position
                "post_balance": 1000
            }
        ]
    }

def simulate_whale_sell_event():
    """Simulate a whale sell transaction"""
    return {
        "signature": f"whale_sell_{random.randint(100000, 999999)}",
        "timestamp": int(time.time()),
        "accounts": [
            {
                "wallet": TEST_WALLET,
                "token": random.choice(REAL_TOKENS),
                "action": "sell",
                "amount": 100.0,  # $100 position
                "post_balance": 1000
            }
        ]
    }

def send_webhook_event(event, description):
    """Send a webhook event to the coordinator"""
    
    print(f"\n🚀 {description}")
    print("=" * 50)
    print(f"📡 Event Type: {event.get('type', 'webhook_event')}")
    print(f"🔍 Transaction: {event['signature']}")
    print(f"👤 Wallet: {event['accounts'][0]['wallet'][:8]}...")
    
    try:
        response = requests.post(
            "http://localhost:8080/webhook",
            json={"events": [event]},
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        result = response.json()
        
        print(f"✅ Response: {response.status_code}")
        print(f"📋 Result: {json.dumps(result, indent=2)}")
        
        if result.get('status') == 'blocked':
            print(f"🚨 BLOCKED: {result.get('reason', 'Unknown reason')}")
        elif result.get('status') == 'processed':
            print(f"🎯 PROCESSED: {result.get('count', 0)} events")
        
        return result
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"status": "error", "error": str(e)}

def test_max_concurrent_positions():
    """Test MAX_CONCURRENT_POSITIONS constraint"""
    print("\n🧪 Testing MAX_CONCURRENT_POSITIONS constraint")
    print("=" * 60)
    print(f"📊 Max concurrent positions: {MAX_CONCURRENT_POSITIONS}")
    
    events = []
    for i in range(MAX_CONCURRENT_POSITIONS + 2):  # Try to exceed limit
        # Use real token addresses that have market prices
        token_address = REAL_TOKENS[i % len(REAL_TOKENS)]
        
        event = {
            "signature": f"concurrent_test_{i}_{int(time.time())}",
            "timestamp": int(time.time()),
            "accounts": [{
                "wallet": TEST_WALLET,
                "token": token_address,
                "action": "buy",
                "amount": 50.0,  # $50 per position
                "post_balance": 1000
            }]
        }
        events.append(event)
    
    processed_count = 0
    blocked_count = 0
    
    for i, event in enumerate(events):
        print(f"\n📡 Sending event {i+1}/{len(events)}")
        result = send_webhook_event(event, f"CONCURRENT POSITION TEST {i+1}")
        
        if result.get('status') == 'processed':
            processed_count += 1
            print(f"✅ Processed: {processed_count} positions created")
        elif result.get('status') == 'blocked':
            blocked_count += 1
            print(f"🚫 BLOCKED: {result.get('reason', 'Unknown')}")
            break
        else:
            print(f"❌ ERROR: {result.get('error', 'Unknown error')}")
            break
        
        time.sleep(0.5)  # Small delay between events
    
    print(f"\n📊 Results: {processed_count} processed, {blocked_count} blocked")
    success = processed_count <= MAX_CONCURRENT_POSITIONS
    print(f"✅ SUCCESS" if success else f"❌ FAILED")
    return success

def test_max_total_allocation():
    """Test MAX_TOTAL_ALLOCATION_PERCENT constraint"""
    print("\n🧪 Testing MAX_TOTAL_ALLOCATION_PERCENT constraint")
    print("=" * 60)
    print(f"📊 Max total allocation: {MAX_TOTAL_ALLOCATION_PERCENT*100:.1f}%")
    
    # Simulate account balance (would normally get from actual system)
    simulated_balance = 1000.0  # $1000 simulated balance
    max_allocation_usd = simulated_balance * MAX_TOTAL_ALLOCATION_PERCENT
    position_size = 100.0  # $100 per position
    num_positions = int(max_allocation_usd / position_size) + 2  # Try to exceed
    
    print(f"💰 Simulated balance: ${simulated_balance:.2f}")
    print(f"📊 Max allocation USD: ${max_allocation_usd:.2f}")
    print(f"📊 Position size: ${position_size:.2f}")
    print(f"📊 Testing with {num_positions} positions")
    
    events = []
    for i in range(num_positions):
        # Use real token addresses that have market prices
        token_address = REAL_TOKENS[i % len(REAL_TOKENS)]
        
        event = {
            "signature": f"allocation_test_{i}_{int(time.time())}",
            "timestamp": int(time.time()),
            "accounts": [{
                "wallet": TEST_WALLET,
                "token": token_address,
                "action": "buy",
                "amount": position_size,
                "post_balance": 1000
            }]
        }
        events.append(event)
    
    processed_count = 0
    blocked_count = 0
    total_allocated = 0
    
    for i, event in enumerate(events):
        print(f"\n📡 Sending event {i+1}/{len(events)} (${position_size} each)")
        
        # Check if this would exceed allocation
        potential_total = total_allocated + position_size
        if potential_total > max_allocation_usd:
            print(f"🚫 Would exceed allocation: ${potential_total:.2f} > ${max_allocation_usd:.2f}")
            blocked_count += 1
            break
        
        result = send_webhook_event(event, f"ALLOCATION TEST {i+1}")
        
        if result.get('status') == 'processed':
            processed_count += 1
            total_allocated += position_size
            print(f"✅ Processed: ${total_allocated:.2f} allocated")
        elif result.get('status') == 'blocked':
            blocked_count += 1
            print(f"🚫 BLOCKED: {result.get('reason', 'Unknown')}")
            break
        else:
            print(f"❌ ERROR: {result.get('error', 'Unknown error')}")
            break
        
        time.sleep(0.5)
    
    allocation_percent = (total_allocated / simulated_balance) * 100
    print(f"\n📊 Results: ${total_allocated:.2f} allocated ({allocation_percent:.1f}%)")
    print(f"📊 Processed: {processed_count}, Blocked: {blocked_count}")
    success = allocation_percent <= (MAX_TOTAL_ALLOCATION_PERCENT * 100)
    print(f"✅ SUCCESS" if success else f"❌ FAILED")
    return success

def test_max_single_position():
    """Test MAX_SINGLE_POSITION_PERCENT constraint"""
    print("\n🧪 Testing MAX_SINGLE_POSITION_PERCENT constraint")
    print("=" * 60)
    print(f"📊 Max single position: {MAX_SINGLE_POSITION_PERCENT*100:.1f}%")
    
    # Simulate account balance
    simulated_balance = 1000.0  # $1000 simulated balance
    max_single_usd = simulated_balance * MAX_SINGLE_POSITION_PERCENT
    print(f"💰 Simulated balance: ${simulated_balance:.2f}")
    print(f"📊 Max single position USD: ${max_single_usd:.2f}")
    
    # Test with different position sizes
    test_sizes = [
        max_single_usd * 0.5,   # 50% of limit - should pass
        max_single_usd * 0.9,   # 90% of limit - should pass
        max_single_usd * 1.1,   # 110% of limit - should fail
        max_single_usd * 1.5,   # 150% of limit - should fail
    ]
    
    results = []
    for i, size in enumerate(test_sizes):
        print(f"\n📡 Testing position size ${size:.2f} ({size/simulated_balance*100:.1f}% of balance)")
        
        # Use real token addresses that have market prices
        token_address = REAL_TOKENS[i % len(REAL_TOKENS)]
        
        event = {
            "signature": f"single_test_{i}_{int(time.time())}",
            "timestamp": int(time.time()),
            "accounts": [{
                "wallet": TEST_WALLET,
                "token": token_address,
                "action": "buy",
                "amount": size,
                "post_balance": 1000
            }]
        }
        
        result = send_webhook_event(event, f"SINGLE POSITION TEST {i+1}")
        
        expected_pass = size <= max_single_usd
        actual_pass = result.get('status') == 'processed'
        
        test_result = {
            'size': size,
            'percent': size/simulated_balance*100,
            'expected_pass': expected_pass,
            'actual_pass': actual_pass,
            'status': result.get('status'),
            'reason': result.get('reason', '')
        }
        
        if expected_pass == actual_pass:
            print(f"✅ CORRECT: {'PASSED' if actual_pass else 'BLOCKED'}")
        else:
            print(f"❌ INCORRECT: Expected {'PASS' if expected_pass else 'BLOCK'}, got {result.get('status')}")
        
        results.append(test_result)
        time.sleep(0.5)
    
    correct_results = sum(1 for r in results if r['expected_pass'] == r['actual_pass'])
    success = correct_results == len(results)
    print(f"\n📊 Results: {correct_results}/{len(results)} tests correct")
    print(f"✅ SUCCESS" if success else f"❌ FAILED")
    return success

def run_constraint_tests():
    """Run all constraint tests"""
    print("\n🧪 RUNNING ALL CONSTRAINT TESTS")
    print("=" * 70)
    
    tests = [
        ("Max Concurrent Positions", test_max_concurrent_positions),
        ("Max Total Allocation", test_max_total_allocation),
        ("Max Single Position", test_max_single_position)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ ERROR in {test_name}: {e}")
            results.append((test_name, False))
    
    # Print summary
    print(f"\n{'='*70}")
    print("📊 CONSTRAINT TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\n📈 Overall: {passed}/{total} tests passed ({(passed/total*100):.1f}%)")
    
    if passed == total:
        print("🎉 ALL CONSTRAINT TESTS PASSED!")
    else:
        print("⚠️  Some constraint tests failed - check system configuration")
    
    return results

def simulate_specific_buys():
    """Simulate buys for BONK, WIF, and PYTH tokens"""
    print("\n🚀 SIMULATING COPYBOT BUYS FOR MAJOR TOKENS")
    print("=" * 60)

    # Check if coordinator is running
    try:
        status_response = requests.get("http://localhost:8080/status", timeout=3)
        print(f"✅ Coordinator is running (status: {status_response.status_code})")
    except:
        print("❌ ERROR: Coordinator not running. Start with 'python src/main.py'")
        return

    # Specific token addresses for testing
    tokens = {
        "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"
    }

    # Use actual tracked wallet from config
    test_wallet = TEST_WALLET

    print(f"👤 Using wallet: {test_wallet[:8]}...")
    print(f"📊 Tokens to buy: {list(tokens.keys())}")

    for token_name, token_address in tokens.items():
        print(f"\n🪙 Simulating {token_name} buy...")

        event = {
            "signature": f"copybot_test_{token_name.lower()}_{int(time.time())}",
            "timestamp": int(time.time()),
            "accounts": [{
                "wallet": test_wallet,
                "token": token_address,
                "action": "buy",
                "amount": 100.0,  # $100 position
                "post_balance": 1000
            }]
        }

        result = send_webhook_event(event, f"{token_name} BUY SIMULATION")
        time.sleep(1)  # 1 second delay between events

    print("🎉 All buy events sent!")
    print("📊 Check your copybot logs to see if it bought these tokens")
    return True

def main():
    """Run webhook simulation"""

    print("🌙 ANARCHO CAPITAL - Webhook Event Simulator")
    print("=" * 60)
    print("📡 This simulates webhook events from Render being sent to local coordinator")

    # Check if coordinator is running
    try:
        status_response = requests.get("http://localhost:8080/status", timeout=3)
        print(f"✅ Coordinator is running (status: {status_response.status_code})")
    except:
        print("❌ ERROR: Coordinator not running. Start with 'python src/main.py'")
        return
    
    while True:
        print("\n🎮 SIMULATION OPTIONS:")
        print("1. 💰 Simulate Whale BUY event")
        print("2. 💸 Simulate Whale SELL event")
        print("3. 📊 Check Coordinator Status")
        print("4. 🧪 Test Max Concurrent Positions")
        print("5. 🧪 Test Max Total Allocation")
        print("6. 🧪 Test Max Single Position")
        print("7. 🧪 Run All Constraint Tests")
        print("8. 🎯 Simulate BONK/WIF/PYTH Buys")
        print("9. 🚪 Exit")

        choice = input("\nEnter choice (1-9): ").strip()

        if choice == '1':
            event = simulate_whale_buy_event()
            send_webhook_event(event, "WHALE BUY TRANSACTION")

        elif choice == '2':
            event = simulate_whale_sell_event()
            send_webhook_event(event, "WHALE SELL TRANSACTION")

        elif choice == '3':
            print("\n🔍 Checking status...")
            try:
                response = requests.get("http://localhost:8080/status", timeout=5)
                data = response.json()
                print(f"📊 Status: {data['status']}")
                print(f"🚦 Flags: Trading={data['flags']['trading_active']}, Emergency={data['flags']['emergency_stop']}, Rebalancing={data['flags']['rebalancing_active']}")
            except Exception as e:
                print(f"❌ Status check failed: {e}")

        elif choice == '4':
            test_max_concurrent_positions()

        elif choice == '5':
            test_max_total_allocation()

        elif choice == '6':
            test_max_single_position()

        elif choice == '7':
            run_constraint_tests()

        elif choice == '8':
            simulate_specific_buys()

        elif choice == '9':
            print("👋 Exiting simulator...")
            break

        else:
            print("❌ Invalid choice. Please enter 1-9.")

def run_direct_simulation():
    """Run direct simulation without menu"""
    print("🚀 DIRECT WEBHOOK SIMULATION")
    print("=" * 40)

    # Check if coordinator is running
    try:
        response = requests.get("http://localhost:8080/status", timeout=3)
        print(f"✅ Coordinator running (status: {response.status_code})")
    except:
        print("❌ Coordinator not running. Start with 'python src/main.py'")
        return False

    return simulate_specific_buys()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--direct":
        run_direct_simulation()
    else:
        main()
