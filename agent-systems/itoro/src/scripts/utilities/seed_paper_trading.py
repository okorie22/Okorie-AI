#!/usr/bin/env python3
"""
Seed Paper Trading Wallets with Tokens
This script seeds your paper trading wallets with tokens that are being traded in live events
"""

import os
import sys
import time
import sqlite3
from datetime import datetime

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.paper_trading import get_paper_trading_db, init_paper_trading_db
from src.scripts.shared_services.logger import info, warning, error

def seed_paper_trading_wallets():
    """Seed paper trading wallets with tokens from live events"""
    
    print("🌱 Seeding Paper Trading Wallets...")
    
    # Initialize database
    init_paper_trading_db()
    
    # Tokens that are being traded in your live events
    tokens_to_seed = {
        # SOL (Native Solana token)
        "So11111111111111111111111111111111111111112": {
            "amount": 10.0,  # 10 SOL
            "price": 162.50,
            "name": "Solana",
            "symbol": "SOL"
        },
        # USDC (Stablecoin)
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {
            "amount": 5000.0,  # $5000 USDC
            "price": 1.0,
            "name": "USD Coin",
            "symbol": "USDC"
        },
        # The specific token from your live events
        "2MuDS29b6rQb9MydKLMvggST5Yqez3B6gYWitvvjc6ir": {
            "amount": 1000000.0,  # 1M tokens (enough for the 583,478 trade)
            "price": 0.0097,
            "name": "Unknown Token",
            "symbol": "UNK"
        },
                            # Add more tokens that might be traded
                    "6jtS916EFxUXtjPUDFn6pKSuVezX6vQ2S3FrQVBM98ZG": {
                        "amount": 50000.0,
                        "price": 0.001,
                        "name": "Another Token",
                        "symbol": "TOK2"
                    },
                    # The specific token from your live events (G1DgiWcBUPVqnfi9SB7yUVcsBRAvF15mWBVDmKKbbonk)
                    "G1DgiWcBUPVqnfi9SB7yUVcsBRAvF15mWBVDmKKbbonk": {
                        "amount": 100000000.0,  # 100M tokens (enough for the 35M+ trades)
                        "price": 0.000007,  # Based on the price in logs
                        "name": "Live Event Token",
                        "symbol": "LIVE"
                    }
    }
    
    try:
        with get_paper_trading_db() as conn:
            # Clear existing portfolio
            conn.execute("DELETE FROM paper_portfolio")
            print("🗑️ Cleared existing portfolio")
            
            # Seed with tokens
            for token_address, token_data in tokens_to_seed.items():
                conn.execute(
                    "INSERT INTO paper_portfolio (token_address, amount, last_price, last_update) VALUES (?, ?, ?, ?)",
                    (
                        token_address,
                        token_data["amount"],
                        token_data["price"],
                        int(time.time())
                    )
                )
                print(f"✅ Added {token_data['amount']} {token_data['symbol']} ({token_address[:8]}...)")
            
            # Update staking balances if personal wallet exists
            from src.config import address
            if address:
                # Calculate total SOL and USDC
                sol_amount = tokens_to_seed["So11111111111111111111111111111111111111112"]["amount"]
                usdc_amount = tokens_to_seed["EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"]["amount"]
                
                conn.execute('''
                    INSERT OR REPLACE INTO paper_trading_balances 
                    (wallet_address, usdc_balance, sol_balance, staked_sol_balance, staking_rewards, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    address,
                    usdc_amount,
                    sol_amount,
                    0.0,  # Staked SOL balance
                    0.0,  # Staking rewards
                    datetime.now().isoformat()
                ))
                print(f"✅ Updated staking balances for wallet {address[:8]}...")
            
            conn.commit()
            
        print("\n🎉 Paper trading wallets seeded successfully!")
        print("💰 Available tokens:")
        for token_address, token_data in tokens_to_seed.items():
            usd_value = token_data["amount"] * token_data["price"]
            print(f"   • {token_data['amount']} {token_data['symbol']} = ${usd_value:,.2f}")
        
        return True
        
    except Exception as e:
        error(f"Failed to seed paper trading wallets: {e}")
        return False

def check_paper_trading_status():
    """Check current paper trading status"""
    print("\n📊 Current Paper Trading Status:")
    
    try:
        with get_paper_trading_db() as conn:
            # Check portfolio
            cursor = conn.execute("SELECT * FROM paper_portfolio")
            portfolio = cursor.fetchall()
            
            if portfolio:
                print("📈 Portfolio:")
                for row in portfolio:
                    token_address, amount, price, timestamp = row
                    usd_value = amount * price
                    print(f"   • {amount} tokens ({token_address[:8]}...) = ${usd_value:,.2f}")
            else:
                print("   ❌ No tokens in portfolio")
            
            # Check recent trades
            cursor = conn.execute("SELECT * FROM paper_trades ORDER BY timestamp DESC LIMIT 5")
            trades = cursor.fetchall()
            
            if trades:
                print("\n📋 Recent Trades:")
                for row in trades:
                    trade_id, timestamp, token_address, action, amount, price, usd_value, agent = row
                    print(f"   • {action} {amount} tokens @ ${price} (${usd_value:,.2f}) by {agent}")
            else:
                print("\n📋 No recent trades")
                
    except Exception as e:
        error(f"Error checking paper trading status: {e}")

if __name__ == "__main__":
    print("🚀 Paper Trading Seeding Script")
    print("=" * 50)
    
    # Seed the wallets
    success = seed_paper_trading_wallets()
    
    if success:
        # Check status
        check_paper_trading_status()
        
        print("\n🎯 Next Steps:")
        print("1. Restart your main.py in Anaconda")
        print("2. Wait for live webhook events")
        print("3. You should now see successful trades in the logs!")
        print("\n💡 The system will now be able to execute paper trades when it receives webhook events.")
    else:
        print("\n❌ Failed to seed paper trading wallets. Please check the error above.") 