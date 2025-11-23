# Supabase Database Connectivity Troubleshooting

## Problem: "Tenant or user not found" Error

### Symptoms
- Error: `FATAL: Tenant or user not found` when connecting to Supabase
- Connection attempts to `aws-0-us-east-1.pooler.supabase.com:6543` fail
- System falls back to local SQLite database

### Root Causes

1. **Pooler Connection Issues**: Supabase pooler requires specific authentication format
2. **IPv6 Connectivity**: Some environments can't reach Supabase IPv6 addresses
3. **SNI Requirements**: Pooler connections need proper hostname-based TLS SNI

### Solutions Implemented

#### Option A: REST API Fallback (Recommended)
When Postgres connection fails, the system automatically falls back to Supabase REST API.

**Environment Variables Required:**
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE=your_service_role_key
```

**Benefits:**
- Works over HTTPS (no port/firewall issues)
- Bypasses Postgres driver problems
- Automatic fallback when Postgres fails
- No SNI or IPv6 issues

#### Option B: Direct Postgres (Alternative)
If you prefer direct Postgres connections:

**Environment Variables:**
```bash
POSTGRES_HOST=db.your-project.supabase.co
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_db_password
POSTGRES_SSL_MODE=require
DB_FORCE_IPV4=true
DB_TRY_SUPABASE_POOLER=0
```

### Verification Steps

1. **Test REST Fallback:**
   ```bash
   python -m test.verify_cloud_db_sync
   ```

2. **Test Connectivity:**
   ```bash
   python -m test.diagnose_supabase_connectivity
   ```

3. **Check Logs:**
   - Look for "RestDatabaseManager" in logs
   - Verify "Portfolio data saved to cloud database" messages

### Deployment Configuration

#### Render.com Environment Variables
Add these to your Render service:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE=your_service_role_key
```

#### Local Development
Ensure your `.env` file contains:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE=your_service_role_key
```

### Troubleshooting

#### If REST Fallback Still Fails
1. Verify service role key is correct (from Supabase Dashboard > Settings > API)
2. Check Supabase project URL format
3. Ensure tables exist in Supabase:
   - `paper_trading_portfolio`
   - `paper_trading_transactions`
   - `portfolio_history`
   - `live_trades`
   - `agent_shared_data`

#### If Direct Postgres Preferred
1. Use Direct connection (not pooler)
2. Set `DB_TRY_SUPABASE_POOLER=0`
3. Ensure IPv4 connectivity with `DB_FORCE_IPV4=true`

### Success Indicators
- ✅ "RestDatabaseManager" appears in logs
- ✅ "Portfolio data saved to cloud database" messages
- ✅ No "Tenant or user not found" errors
- ✅ Webhook events process successfully
- ✅ Portfolio snapshots sync between local and Render

### Support
If issues persist, check:
1. Supabase service status
2. Network connectivity from Render
3. Service role key permissions
4. Table schema matches expected format
