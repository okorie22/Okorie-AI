"""
Test OnChain Agent with specific tokens
Tests data collection for WIF, BONK, and PYTH tokens
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.onchain_agent import OnChainAgent
from src.scripts.shared_services.logger import info, error

def test_onchain_agent():
    """Test OnChain Agent with WIF, BONK, and PYTH tokens"""
    
    # Token addresses for testing
    test_tokens = {
        'wif': 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm',  # dogwifhat
        'bonk': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
        'pyth': 'HZ1JovNiVvGr6kJnFMDz8YNnMSYGYyaN2vLMgcVXu7rF'    # Pyth Network
    }
    
    info("🧪 Testing OnChain Agent with test tokens...")
    info(f"Tokens: {', '.join(test_tokens.keys())}")
    
    try:
        # Initialize agent
        agent = OnChainAgent()
        
        if not agent.birdeye_api_key:
            error("❌ BIRDEYE_API_KEY not configured")
            return False
        
        info("✅ Agent initialized")
        
        # Test fetching data for each token
        results = {}
        for name, address in test_tokens.items():
            info(f"\n🔍 Fetching data for {name.upper()} ({address[:8]}...)")
            
            try:
                # First test the raw API response
                print(f"  🔍 Fetching raw Birdeye API response...")
                birdeye_response = agent._fetch_birdeye_data(address)
                if birdeye_response:
                    print(f"  📋 Birdeye API returned these fields:")
                    for key, value in birdeye_response.items():
                        if isinstance(value, (int, float)):
                            print(f"      {key}: {value}")
                        elif isinstance(value, str):
                            print(f"      {key}: {value[:50]}...")
                        else:
                            print(f"      {key}: {type(value).__name__}")
                
                token_data = agent._fetch_token_data(address)
                
                if token_data:
                    info(f"✅ Successfully fetched data for {name.upper()}")
                    
                    # Print key metrics
                    print(f"\n  📊 {name.upper()} Metrics:")
                    print(f"     Holder Count: {token_data.get('holder_count', 'N/A')}")
                    print(f"     New Holders (24h): {token_data.get('new_holders_24h', 'N/A')}")
                    print(f"     Holder Growth: {token_data.get('holder_growth_pct', 0):.2f}%")
                    print(f"     TX Count (24h): {token_data.get('tx_count_24h', 'N/A')}")
                    print(f"     Liquidity USD: ${token_data.get('liquidity_usd', 0):,.2f}")
                    print(f"     Volume (24h): ${token_data.get('volume_24h', 0):,.2f}")
                    price_change = token_data.get('price_change_24h', 0)
                    print(f"     Price Change (24h): {price_change:.2f}%" if price_change is not None else "     Price Change (24h): N/A")
                    print(f"     Trend: {token_data.get('trend_signal', 'UNKNOWN')}")
                    
                    results[name] = token_data
                else:
                    info(f"⚠️ No data returned for {name.upper()}")
                    
            except Exception as e:
                error(f"❌ Error fetching data for {name.upper()}: {e}")
                import traceback
                error(traceback.format_exc())
        
        # Save data first so get_aggregated_status can read it
        info("\n💾 Saving test data...")
        agent.onchain_data = {
            'timestamp': '2024-01-01T00:00:00',
            'tokens': results
        }
        agent._save_data()
        
        # Test get_aggregated_status
        info("📈 Testing aggregated status...")
        status = agent.get_aggregated_status()
        print(f"\n📊 Aggregated Status:")
        print(f"   Growing: {status['growing_count']}")
        print(f"   Shrinking: {status['shrinking_count']}")
        print(f"   Stable: {status['stable_count']}")
        print(f"   Status Text: {status['status_text']}")
        print(f"   Color: {status['color']}")
        
        # Summary
        info(f"\n{'='*60}")
        info(f"✅ Test Complete!")
        info(f"   Tokens Tested: {len(results)}")
        info(f"   Successful Fetches: {len([r for r in results.values() if r])}")
        info(f"   Data File: {agent.data_file}")
        info(f"{'='*60}")
        
        return True
        
    except Exception as e:
        error(f"❌ Test failed: {e}")
        import traceback
        error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = test_onchain_agent()
    sys.exit(0 if success else 1)

