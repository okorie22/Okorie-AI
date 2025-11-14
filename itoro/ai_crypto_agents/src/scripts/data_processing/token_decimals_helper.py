"""
Token Decimals Helper for Anarcho Capital's Trading System
Provides utilities for handling token decimals and amount conversions
"""

from typing import Optional

def get_token_decimals(token_address: str) -> int:
    """
    Get the number of decimals for a token
    
    Args:
        token_address: The token mint address
        
    Returns:
        Number of decimals (defaults to 9 for SOL-like tokens)
    """
    # Common token decimals mapping
    common_tokens = {
        "So11111111111111111111111111111111111111112": 9,  # SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": 6,  # USDC
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": 6,  # USDT
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": 5,  # BONK
    }
    
    # Check common tokens first
    if token_address in common_tokens:
        return common_tokens[token_address]
    
    # Default to 9 decimals (like SOL) if we can't determine
    return 9

def to_token_units(raw_amount: float, token_address: str) -> float:
    """
    Convert raw amount to token units using token decimals
    
    Args:
        raw_amount: Raw amount (e.g., lamports)
        token_address: The token mint address
        
    Returns:
        Amount in token units (e.g., SOL)
    """
    try:
        decimals = get_token_decimals(token_address)
        return raw_amount / (10 ** decimals)
    except Exception:
        # Default to 9 decimals if we can't determine
        return raw_amount / (10 ** 9)

def to_raw_units(token_amount: float, token_address: str) -> int:
    """
    Convert token units to raw amount using token decimals
    
    Args:
        token_amount: Amount in token units (e.g., SOL)
        token_address: The token mint address
        
    Returns:
        Raw amount (e.g., lamports)
    """
    try:
        decimals = get_token_decimals(token_address)
        return int(token_amount * (10 ** decimals))
    except Exception:
        # Default to 9 decimals if we can't determine
        return int(token_amount * (10 ** 9))

def normalize_amount_for_validation(amount: float, token_address: str) -> float:
    """
    Normalize amount for position validation
    
    Args:
        amount: Amount to normalize
        token_address: The token mint address
        
    Returns:
        Normalized amount in token units
    """
    try:
        # If amount is very large, it's likely in raw units (lamports)
        if amount > 1e6:  # More than 1 million, likely raw units
            return to_token_units(amount, token_address)
        else:
            # Already in token units
            return amount
    except Exception:
        return amount