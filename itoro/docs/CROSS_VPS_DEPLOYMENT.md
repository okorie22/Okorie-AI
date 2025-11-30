# Cross-VPS Deployment Guide

This document explains how to run the crypto, forex, stock, data-aggregator, and commerce systems on separate VPS instances while keeping them connected through shared cloud infrastructure.

## 1. Transport Options

| Transport | When to use it | Notes |
|-----------|----------------|-------|
| **Shared Postgres / Supabase** | Default option when all agents can reach a common database. | Lowest effort—every ecosystem already supports the unified schema expected by `data_aggregator` and the commerce layer. |
| **Redis Streams Event Bus** | When you need real-time fan-out or want to avoid direct DB writes from trading agents. | Requires a managed Redis instance. Supported via `CORE_EVENT_BUS_BACKEND=redis`. |
| **HTTPS Webhook** | When agents cannot access the DB but can make outbound HTTPS requests. | Aggregator exposes an endpoint that accepts signed requests (`AuthManager`). Use `CORE_EVENT_BUS_BACKEND=webhook`. |

You can mix transports. For example, crypto agents may write to Postgres while forex agents send webhooks. The aggregator will consume from whichever backends are enabled.

## 2. Required Environment Variables

| Variable | Purpose |
|----------|---------|
| `CORE_DB_URL` | Shared Postgres connection string for core services. |
| `CORE_CRYPTO_DB_URL`, `CORE_FOREX_DB_URL`, `CORE_STOCK_DB_URL` | Optional overrides for ecosystem-specific databases. |
| `CORE_EVENT_BUS_BACKEND` | Backend selector: `memory` (default), `redis`, or `webhook`. |
| `CORE_REDIS_URL` | Redis connection string when using the Redis event bus. |
| `CORE_EVENT_WEBHOOK_URL` | Target URL for webhook publishing (used by trading agents). |
| `CORE_EVENT_WEBHOOK_SECRET` | HMAC secret used to sign webhook payloads. |
| `CORE_API_KEYS` | Pipe-separated API keys (`id:value`) recognised by `AuthManager`. |
| `CORE_AUTH_SECRET` | Secret used to salt API key hashes. |
| `AGG_SIGNAL_ENDPOINT` | Public HTTPS endpoint for the data aggregator when running in webhook mode. |

Set these variables on each VPS according to the transports you choose.

### Event Bus Fallback Order

1. If `CORE_EVENT_BUS_BACKEND=redis` and `CORE_REDIS_URL` is valid, signals are appended to Redis Streams (`<prefix>:<topic>`).
2. Else if `CORE_EVENT_BUS_BACKEND=webhook` and `CORE_EVENT_WEBHOOK_URL`/`CORE_EVENT_WEBHOOK_SECRET` are set, signals are POSTed to the webhook endpoint with HMAC protection.
3. Otherwise the bus remains in-memory and only services local subscribers.

## 3. Recommended Topologies

1. **Database-first (recommended MVP)**
   - Provision a managed Postgres/Supabase instance.
   - Set `CORE_DB_URL` on the data-aggregator and commerce VPS.
   - Set ecosystem-specific variables (`CORE_CRYPTO_DB_URL`, etc.) on each trading VPS.
   - Run the data aggregator with `CORE_EVENT_BUS_BACKEND=memory` (default).

2. **Redis-backed event bus**
   - Provision Redis Cloud or similar.
   - Set `CORE_EVENT_BUS_BACKEND=redis` and `CORE_REDIS_URL=redis://...` on all VPS nodes.
   - Trading agents publish to Redis streams; aggregator consumes from the same streams.

3. **Webhook publishing**
   - Expose the data aggregator over HTTPS (e.g., FastAPI or Cloudflare Tunnel).
   - Set `CORE_EVENT_BUS_BACKEND=webhook` on agents and `AGG_SIGNAL_ENDPOINT` to the aggregator URL.
   - Configure `CORE_EVENT_WEBHOOK_SECRET` and add matching API keys via `CORE_API_KEYS`.
   - Deploy the optional receiver: `uvicorn data_aggregator.webhook_server:app --host 0.0.0.0 --port 8000`.

## 4. Checklist per VPS

- [ ] Configure environment variables for the chosen transport.
- [ ] Ensure outbound network access to the shared database/Redis/webhook endpoint.
- [ ] Run health checks: `python -m data_aggregator.main` (aggregator), `python -m ai_crypto_agents.src.main` (crypto), etc.
- [ ] Monitor logs for `EventBus` backend connection messages.

## 5. Monitoring and Troubleshooting

- Use the new `HealthChecker` probes exposed by the data aggregator to monitor adapter status.
- For Redis: inspect stream lag with `XINFO STREAM core_signals`.
- For webhooks: enable structured logging and verify HMAC signatures.
- For the database flow: query `trading_signals` table to confirm records arriving from each ecosystem.

