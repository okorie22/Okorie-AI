#!/usr/bin/env python3
"""Environment variable check for webhook debugging"""

import os

def check_env():
    """Check environment variables"""
    print("Environment Check:")
    print(f"PORT: {os.environ.get('PORT', 'not set')}")
    print(f"HELIUS_API_KEY: {'configured' if os.environ.get('HELIUS_API_KEY') else 'not configured'}")
    print(f"BIRDEYE_API_KEY: {'configured' if os.environ.get('BIRDEYE_API_KEY') else 'not configured'}")
    print(f"DEFAULT_WALLET_ADDRESS: {'configured' if os.environ.get('DEFAULT_WALLET_ADDRESS') else 'not configured'}")
    print(f"SOLANA_PRIVATE_KEY: {'configured' if os.environ.get('SOLANA_PRIVATE_KEY') else 'not configured'}")
    print(f"RPC_ENDPOINT: {'configured' if os.environ.get('RPC_ENDPOINT') else 'not configured'}")

    # Show actual values for debugging (without sensitive info)
    wallet = os.environ.get('DEFAULT_WALLET_ADDRESS', '')
    if wallet:
        print(f"DEFAULT_WALLET_ADDRESS: {wallet[:8]}...{wallet[-4:]}")

    helius_key = os.environ.get('HELIUS_API_KEY', '')
    if helius_key:
        print(f"HELIUS_API_KEY: {helius_key[:8]}...{helius_key[-4:]}")

    birdeye_key = os.environ.get('BIRDEYE_API_KEY', '')
    if birdeye_key:
        print(f"BIRDEYE_API_KEY: {birdeye_key[:8]}...{birdeye_key[-4:]}")

if __name__ == "__main__":
    check_env() 
