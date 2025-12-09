#!/usr/bin/env python3
"""
Manual test for whale data flow
Tests the actual database operations without complex mocking
"""

import sys
import os

# Add paths
commerce_src = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, commerce_src)
# Also add parent directory for relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_whale_ranking_agent_functions():
    """Test whale ranking agent functions directly"""
    print("=" * 80)
    print("TESTING WHALE RANKING AGENT")
    print("=" * 80)
    
    try:
        from ai_commerce_agents.src.agents.whale_ranking_agent import get_whale_ranking_agent
        from ai_commerce_agents.src.shared.database import WhaleRanking
        from datetime import datetime
        
        agent = get_whale_ranking_agent()
        print("\n[1] Whale Ranking Agent initialized successfully")
        
        # Test health check
        health = agent.health_check()
        print(f"\n[2] Health check: {health['agent']} - Running: {health['running']}")
        
        # Test getting last data update
        last_update = agent._get_last_data_update()
        print(f"\n[3] Last data update: {last_update}")
        
        # Test database connection
        rankings = agent.db.get_whale_rankings(limit=5)
        print(f"\n[4] Retrieved {len(rankings)} rankings from database")
        
        if rankings:
            print("\n[5] Sample ranking:")
            r = rankings[0]
            print(f"    Address: {r.address[:10]}...")
            print(f"    Twitter: {r.twitter_handle}")
            print(f"    Score: {r.score}")
            print(f"    Rank: {r.rank}")
            print(f"    7D P&L: {r.pnl_7d * 100:.2f}%")
            
            # Test weekly aggregation
            print("\n[6] Testing weekly aggregation...")
            weekly_data = agent._create_weekly_top_performers()
            print(f"    Created weekly list with {len(weekly_data)} performers")
            
            if weekly_data:
                print(f"    Top performer: {weekly_data[0]['wallet_address'][:10]}... with {weekly_data[0]['weekly_pnl_pct'] * 100:.2f}% 7D P&L")
                
                # Test Ocean Protocol export
                print("\n[7] Testing Ocean Protocol export...")
                ocean_data = agent.export_weekly_rankings_for_ocean()
                
                if 'error' not in ocean_data:
                    print(f"    Dataset: {ocean_data['dataset_name']}")
                    print(f"    Record count: {ocean_data['record_count']}")
                    print(f"    Avg weekly P&L: {ocean_data['metadata']['avg_weekly_pnl'] * 100:.2f}%")
                    print(f"    Verified wallets: {ocean_data['metadata']['verified_count']}")
                    
                    # Test saving export
                    print("\n[8] Testing Ocean Protocol export save...")
                    agent._save_ocean_export(ocean_data)
                    print("    Export saved successfully")
                else:
                    print(f"    Error: {ocean_data['error']}")
        else:
            print("\n[WARNING] No whale data found in database yet")
            print("         Run the whale_agent.py first to populate data")
        
        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_values():
    """Test configuration values"""
    print("\n" + "=" * 80)
    print("TESTING CONFIGURATION")
    print("=" * 80)
    
    try:
        from ai_commerce_agents.src.shared.config import (
            WHALE_RANKING_UPDATE_INTERVAL,
            WHALE_RANKING_WEEKLY_SCHEDULE,
            SUPABASE_URL,
            CLOUD_DATABASE_TYPE
        )
        
        print(f"\n[1] Update interval: {WHALE_RANKING_UPDATE_INTERVAL} seconds ({WHALE_RANKING_UPDATE_INTERVAL/3600} hours)")
        print(f"\n[2] Weekly schedule:")
        print(f"    Day: {WHALE_RANKING_WEEKLY_SCHEDULE['day']} (Sunday)")
        print(f"    Hour: {WHALE_RANKING_WEEKLY_SCHEDULE['hour']} AM")
        print(f"    Enabled: {WHALE_RANKING_WEEKLY_SCHEDULE['enabled']}")
        
        print(f"\n[3] Database type: {CLOUD_DATABASE_TYPE}")
        print(f"[4] Supabase URL configured: {bool(SUPABASE_URL)}")
        
        print("\n" + "=" * 80)
        print("CONFIGURATION OK")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Config test failed: {e}")
        return False

if __name__ == "__main__":
    print("\n\n")
    print("*" * 80)
    print("WHALE DATA FLOW MANUAL TEST")
    print("*" * 80)
    print()
    
    # Test config first
    config_ok = test_config_values()
    
    # Test agent functions
    agent_ok = test_whale_ranking_agent_functions()
    
    print("\n" + "*" * 80)
    if config_ok and agent_ok:
        print("SUCCESS: All manual tests passed!")
    else:
        print("FAILURE: Some tests failed")
    print("*" * 80)
    print()

