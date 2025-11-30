# Whale Ranking Agent - Implementation Summary

## Overview
The whale ranking system now follows a dual-database architecture where the crypto agents and commerce agents work together to track, aggregate, and monetize crypto whale wallet data.

## Architecture

### Data Flow
```
whale_agent.py (ai_crypto_agents)
    ↓
    ├─→ PostgreSQL whale_data table (direct psycopg2 connection)
    └─→ Supabase whale_data table (REST API via cloud_storage)
         ↓
whale_ranking_agent.py (ai_commerce_agents)
    ↓
    ├─→ Daily rankings retrieval
    ├─→ Weekly top performers aggregation
    └─→ Ocean Protocol export (JSON format)
```

### Database Architecture
- **PostgreSQL Database**: Underlying relational database for Supabase
- **Supabase**: Provides REST API layer on top of PostgreSQL
- **whale_data table**: Stores daily whale wallet rankings with metadata
- **Dual-save mechanism**: Data is saved to both PostgreSQL (for crypto agents) and Supabase (for commerce agents)

## Key Components

### 1. whale_agent.py (ai_crypto_agents)
**Purpose**: Fetches and scores whale wallet data daily

**Modifications**:
- Added tertiary sync to commerce agents' Supabase collection
- Converts `WhaleWallet` objects to `WhaleRanking` format
- Saves to both PostgreSQL and Supabase whale_data table
- Runs every 24 hours

**Key Code**:
```python
# TERTIARY: Sync to commerce agents' Supabase collection
commerce_storage = get_cloud_storage_manager()
if commerce_storage and commerce_storage.connect():
    # Convert and save whale rankings
    commerce_storage.store_whale_rankings(rankings_for_commerce)
```

### 2. whale_ranking_agent.py (ai_commerce_agents)
**Purpose**: Aggregates rankings and publishes to Ocean Protocol

**Modifications**:
- Added `_create_weekly_top_performers()` - sorts by 7-day P&L, returns top 50
- Added `export_weekly_rankings_for_ocean()` - formats for Ocean Protocol marketplace
- Added `_save_ocean_export()` - saves JSON exports locally
- Added `_get_last_data_update()` - checks data freshness
- Modified `_publish_rankings()` - implements weekly schedule and data freshness checks
- Update interval: 1 hour (down from 30 minutes)
- Weekly schedule: Sunday at 10 AM

**Key Code**:
```python
def _create_weekly_top_performers(self) -> List[Dict[str, Any]]:
    all_rankings = self.db.get_whale_rankings(limit=200)
    weekly_winners = sorted(all_rankings, key=lambda x: x.pnl_7d, reverse=True)[:50]
    return weekly_list

def export_weekly_rankings_for_ocean(self) -> Dict[str, Any]:
    weekly_data = self._create_weekly_top_performers()
    return {
        "dataset_name": "ITORO Top 50 Crypto Whale Wallets - Weekly",
        "description": "Top 50 performing crypto wallets based on 7-day performance metrics",
        "data_format": "JSON",
        "update_frequency": "Weekly",
        "rankings": weekly_data,
        "metadata": {...}
    }
```

### 3. cloud_storage.py (ai_commerce_agents)
**Purpose**: Unified interface for cloud storage operations

**Modifications**:
- Updated to consistently use `whale_data` table (not `whale_rankings`)
- Implemented upsert functionality for `store_data()` using `wallet_address` as unique key
- Enhanced `retrieve_data()` with proper query filtering
- Added `store_whale_rankings()` helper method

### 4. database.py (ai_commerce_agents)
**Purpose**: High-level database manager for commerce operations

**Modifications**:
- Added `_normalize_whale_record()` to map whale_data fields to WhaleRanking dataclass
- Updated `store_whale_rankings()` to use `wallet_address` for upsert operations
- Updated `get_whale_rankings()` to query by `risk_score` field
- Ensures database connection on initialization

### 5. config.py (ai_commerce_agents)
**Purpose**: Global configuration for commerce agents

**Modifications**:
- `WHALE_RANKING_UPDATE_INTERVAL`: Changed from 1800 to 3600 seconds (1 hour)
- Added `WHALE_RANKING_WEEKLY_SCHEDULE`:
  ```python
  {
      'day': 6,     # Sunday (0=Monday, 6=Sunday)
      'hour': 10,   # 10 AM
      'enabled': True
  }
  ```

## Data Models

### WhaleRanking (commerce agents)
```python
@dataclass
class WhaleRanking:
    address: str                # Wallet address
    twitter_handle: Optional[str]
    pnl_30d: float             # 30-day P&L %
    pnl_7d: float              # 7-day P&L %
    pnl_1d: float              # 1-day P&L %
    winrate_7d: float          # Win rate over 7 days
    txs_30d: int               # Transactions in 30 days
    token_active: int          # Active tokens
    last_active: datetime
    is_blue_verified: bool
    avg_holding_period_7d: float
    score: float               # Risk/performance score
    rank: int
    last_updated: datetime
    ranking_id: str
```

### Ocean Protocol Export Format
```json
{
  "dataset_name": "ITORO Top 50 Crypto Whale Wallets - Weekly",
  "description": "Top 50 performing crypto wallets based on 7-day performance metrics",
  "data_format": "JSON",
  "update_frequency": "Weekly",
  "timestamp": "2025-11-09T22:22:32.545812",
  "record_count": 18,
  "rankings": [
    {
      "rank": 1,
      "wallet_address": "0x...",
      "twitter_handle": "@whale_trader",
      "weekly_pnl_pct": 15.0,
      "monthly_pnl_pct": 50.0,
      "win_rate": 0.85,
      "total_score": 0.9,
      "verified": true,
      "active_tokens": 30,
      "avg_hold_time_days": 1.0
    }
  ],
  "metadata": {
    "min_score_threshold": 0.3,
    "avg_weekly_pnl": 0.99,
    "verified_count": 6
  }
}
```

## Publishing Schedule

### Daily (Every 1 hour check)
- Retrieves latest whale rankings from Supabase
- Only publishes if data is fresh (< 1 hour old)
- Creates daily leaderboard

### Weekly (Sunday 10 AM)
- Aggregates top 50 performers by 7-day P&L
- Formats data for Ocean Protocol marketplace
- Saves export to `exports/ocean_protocol/whale_rankings_weekly_latest.json`
- Creates timestamped backup

### Monthly (First day at noon)
- Creates monthly performance summary
- Publishes monthly leaderboard

## File Locations

### Exports
- **Weekly Ocean Protocol exports**: `ai_commerce_agents/exports/ocean_protocol/`
  - `whale_rankings_weekly_latest.json` - Latest export
  - `whale_rankings_weekly_YYYYMMDD_HHMMSS.json` - Timestamped backups

### Logs
- Commerce agents: `ai_commerce_agents/logs/`
- Crypto agents: `ai_crypto_agents/logs/`

### Data
- Subscription plans: `ai_commerce_agents/data/subscription_plans.json`
- Publications history: `ai_commerce_agents/data/ranking_publications.json`

## Environment Variables Required

```env
# Supabase Configuration
SUPABASE_URL=https://ggljlztzxmpvjxwgfiwu.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# PostgreSQL Configuration (for crypto agents)
POSTGRES_HOST=aws-0-us-east-1.pooler.supabase.com
POSTGRES_PORT=6543
POSTGRES_DB=postgres
POSTGRES_USER=postgres.ggljlztzxmpvjxwgfiwu
POSTGRES_PASSWORD=your_password

# Optional
WHALE_RANKING_UPDATE_INTERVAL=3600  # 1 hour
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHANNEL_ID=your_channel
```

## Testing

### Verified Flow
1. **Data Retrieval**: Successfully retrieves 18 whale rankings from Supabase
2. **Weekly Aggregation**: Creates sorted list of top performers by 7-day P&L
3. **Ocean Protocol Export**: Generates properly formatted JSON with metadata
4. **File Export**: Saves to local exports directory

### Test Output
```
Retrieved 18 rankings from Supabase
  #1 test_whale_1 (TEST_WALLE...) score=0.90 pnl_7d=30.00%
  #2 test_whale_2 (TEST_WALLE...) score=0.85 pnl_7d=27.00%
  #3 test_whale_3 (TEST_WALLE...) score=0.80 pnl_7d=24.00%
Weekly aggregation count: 18
Ocean export summary: {"dataset_name": "ITORO Top 50 Crypto Whale Wallets - Weekly", ...}
Latest export saved at: whale_rankings_weekly_latest.json
```

## Future Enhancements

1. **Ocean Protocol Integration**: Publish directly to Ocean Protocol marketplace
2. **Real-time Alerts**: Notify subscribers when whales make significant moves
3. **Historical Analysis**: Track whale performance over multiple weeks
4. **Advanced Filtering**: Allow filtering by verification status, token type, etc.
5. **API Endpoints**: Expose rankings via REST API for subscribers
6. **Telegram Notifications**: Send weekly summaries to subscribers

## Troubleshooting

### Common Issues

**Database not connected**:
- Verify environment variables are set correctly
- Check Supabase project is active
- Ensure `whale_data` table exists in Supabase

**No data in weekly export**:
- Verify whale_agent.py has run and saved data
- Check data freshness (must be < 1 hour old)
- Ensure at least 10 whale records exist

**Import errors in tests**:
- Ensure both `ai_crypto_agents` and `ai_commerce_agents` are in Python path
- Use absolute imports in test scripts

## Maintenance

### Regular Tasks
- Monitor Ocean Protocol export directory for disk space
- Review whale rankings quality weekly
- Update subscription plans as needed
- Backup ranking publications history

### Performance Monitoring
- Track database query times
- Monitor Supabase API usage
- Review agent update intervals if data freshness issues occur

---

**Status**: ✅ Fully implemented and tested
**Last Updated**: 2025-11-09
**Version**: 1.0

