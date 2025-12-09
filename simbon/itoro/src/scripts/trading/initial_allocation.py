"""
Initial SOL allocation for paper trading
"""

import os
import sqlite3
from src.paper_trading import execute_paper_trade, print_portfolio_status, init_paper_trading_db
from src.config import PAPER_TRADING_ENABLED

def allocate_initial_sol():
    """Execute initial SOL allocation paper trade"""
    if not PAPER_TRADING_ENABLED:
        print("❌ Paper trading is not enabled")
        return
        
    # Initialize DB if needed but don't reset
    init_paper_trading_db()
    
    # SOL token address
    sol_address = "So11111111111111111111111111111111111111112"
    
    # Calculate amount to achieve 5% allocation ($50 worth)
    sol_price = 162.50
    sol_amount = 50.0 / sol_price  # About 0.3077 SOL
    
    # Execute paper trade
    success = execute_paper_trade(
        token_address=sol_address,
        action="BUY",
        amount=sol_amount,
        price=sol_price,
        agent="rebalancing"
    )
    
    if success:
        print("\n✅ Successfully allocated initial SOL position")
        print_portfolio_status()
    else:
        print("\n❌ Failed to allocate initial SOL position")

if __name__ == "__main__":
    allocate_initial_sol() 