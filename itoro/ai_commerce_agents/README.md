# 💰 ITORO Commerce Layer

A modular, scalable commerce system for monetizing AI trading intelligence. Transform your trading agents into revenue-generating assets by selling signals, data, rankings, and analytics to traders and institutions.

## 🎯 Overview

The ITORO Commerce Layer enables AI trading systems to generate revenue from their intelligence outputs. Built with modularity and security in mind, it operates independently from trading operations while maintaining data integrity and user privacy.

### Key Features

- **🤖 5 Specialized Commerce Agents** - Independent agents for different monetization channels
- **☁️ Cloud-Native Architecture** - Multi-provider cloud storage support
- **💳 Flexible Payment Processing** - Stripe, Solana Pay, and crypto payments
- **🔐 Enterprise Security** - API key management, rate limiting, encryption
- **📊 Comprehensive Analytics** - Revenue tracking, performance metrics, user analytics
- **🔌 RESTful API** - Full programmatic access to all features

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    💰 ITORO COMMERCE LAYER                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ Signal      │ │ Data        │ │ Merchant    │ │ Whale       │ │
│  │ Service     │ │ Service     │ │ Agent       │ │ Ranking     │ │
│  │ Agent       │ │ Agent       │ │             │ │ Agent       │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ Strategy    │ │ Pricing     │ │ Database    │ │ Cloud       │ │
│  │ Metadata    │ │ Engine      │ │ Manager     │ │ Storage     │ │
│  │ Agent       │ └─────────────┘ └─────────────┘ └─────────────┘ │
│  └─────────────┘                                                   │
├─────────────────────────────────────────────────────────────────┤
│                    🔗 SHARED INFRASTRUCTURE                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ Trading     │ │ Whale       │ │ Strategy    │ │ Executed    │ │
│  │ Signals     │ │ Rankings    │ │ Metadata    │ │ Trades      │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🤖 Commerce Agents

### 1. 📢 Telegram Management Agent
**Purpose**: Automate Telegram channel content, promotions, and community engagement

**Features**:
- AI-assisted content generation (DeepSeek) with template fallbacks
- Automated posting cadence with configurable schedules
- GMGN copy-trading promotions and forex community cross-posting
- Community prompts, educational threads, and marketing flows

**Capabilities**:
- Fully automated or manual post triggers
- Custom content rotation and topic lists via environment variables
- Health checks and dry-run logging for safe testing

### 2. 📊 Data Service Agent
**Purpose**: Package and sell trading datasets

**Features**:
- Automated dataset creation from trading data
- Multi-platform publishing (Ocean Protocol, Dune, RapidAPI)
- Dynamic pricing based on data freshness and quality
- Secure download links with expiration

**Supported Platforms**:
- Ocean Protocol (decentralized data marketplace)
- Dune Analytics (query and visualization)
- RapidAPI (API marketplace)
- Custom API endpoints

### 3. 💰 Merchant Agent
**Purpose**: Handle payments and subscription management

**Features**:
- Stripe and Solana Pay integration
- Subscription lifecycle management
- Automated billing and dunning
- Revenue analytics and reporting
- Refund processing

**Payment Methods**:
- Credit cards (Stripe)
- Cryptocurrency (Solana Pay)
- Future: PayPal, Apple Pay, Google Pay

### 4. 🐋 Whale Ranking Agent
**Purpose**: Publish whale wallet rankings and leaderboards

**Features**:
- Real-time whale wallet tracking and ranking
- Performance-based leaderboards
- Social media integration (Twitter verification)
- Alert system for whale movements

**Ranking Types**:
- Top performers (30-day P&L)
- Weekly champions (7-day performance)
- Monthly congress (institutional wallets)
- Social verification rankings

### 5. 📈 Strategy Metadata Agent
**Purpose**: Publish strategy performance and risk analysis

**Features**:
- Automated strategy performance analysis
- Risk assessment and mitigation recommendations
- Market intelligence generation
- Comparative strategy analytics

**Analysis Types**:
- Performance metrics (Sharpe ratio, win rate, drawdown)
- Risk metrics (VaR, volatility, correlation)
- Market condition assessment
- Strategy recommendations

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Cloud database account (Supabase/Firebase/MongoDB/AWS)
- Payment processor accounts (Stripe/Solana)

### Installation

1. **Clone and setup**:
```bash
cd itoro/
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp config.example.py config.py
# Edit config.py with your settings
```

3. **Run quick test**:
```bash
python test_commerce_system.py --quick
```

4. **Start the system**:
```python
from commerce_agents.signal_service_agent import get_signal_service_agent

# Initialize and start agents
signal_agent = get_signal_service_agent()
signal_agent.start()

# System is now running and ready to process data
```

## ⚙️ Configuration

### Environment Variables

Copy `config.example.py` to `config.py` and configure:

#### Cloud Database
```python
CLOUD_DATABASE_TYPE = 'supabase'  # or 'firebase', 'mongodb', 'aws_s3'
SUPABASE_URL = 'your-supabase-url'
SUPABASE_ANON_KEY = 'your-anon-key'
```

#### Payment Processing
```python
STRIPE_SECRET_KEY = 'sk_test_your-stripe-key'
SOLANA_PAY_WALLET_PRIVATE_KEY = 'your-solana-private-key'
```

#### External APIs
```python
TELEGRAM_BOT_TOKEN = 'your-telegram-token'
TELEGRAM_CHAT_ID = '@your_channel'
DEEPSEEK_KEY = 'your-deepseek-api-key'  # used for AI content creation
GMGN_PROMO_LINK = 'https://gmgn.ai/wallet/your-wallet'  # optional
FOREX_COMMUNITY_LINK = 'https://t.me/yourforexchannel'  # optional
```

#### Telegram Content Automation
```python
# Toggle marketing automation
TELEGRAM_CONTENT_ENABLED = True

# Daily HH:MM posting cadence (comma separated)
TELEGRAM_CONTENT_SCHEDULES = "09:00,14:00,19:00"

# Optional JSON arrays to fine-tune topics & rotation
TELEGRAM_CONTENT_TOPICS = '["momentum", "liquidity", "risk management"]'
TELEGRAM_CONTENT_ROTATION = '["market", "tip", "promo", "community"]'
TELEGRAM_CONTENT_MAX_RETRIES = 2
```

#### Legacy Signal Ingestion (optional)
```python
# Enable if you still ingest external trading signals
SIGNAL_TRIGGER_MODE = True

# Optional JSON mapping of ecosystems to Telegram chat IDs
# Example: {"crypto": "-1003295412345", "forex": "-1001234567890"}
TELEGRAM_CHANNEL_MAP = '{"crypto": "-1003295412345"}'

# Comma separated ecosystems that should broadcast via GMGN
GMGN_ECOSYSTEMS = "crypto,forex"

# Optional webhook hardening
SIGNAL_WEBHOOK_SECRET = 'shared-secret'
SIGNAL_WEBHOOK_ALLOWED_IPS = '["127.0.0.1"]'
```

### Feature Flags

Control which agents are active:

```python
ENABLE_SIGNAL_SERVICE = True
ENABLE_DATA_SERVICE = True
ENABLE_WHALE_RANKING = True
ENABLE_STRATEGY_METADATA = True
ENABLE_MERCHANT_SERVICES = True
```

## 📡 API Reference

### Authentication

All API endpoints require authentication via API key:

```python
headers = {
    'Authorization': 'Bearer your-api-key',
    'Content-Type': 'application/json'
}
```

### Signal Service API

```python
# Get live signals
response = requests.get('/api/signals/live', headers=headers, params={'limit': 20})

# Subscribe to signals
response = requests.post('/api/signals/subscribe', headers=headers,
                        json={'channel': 'telegram', 'filters': {'symbols': ['SOL/USD']}})
```

### Data Service API

```python
# Get available datasets
response = requests.get('/api/datasets', headers=headers)

# Purchase dataset
response = requests.post('/api/datasets/purchase', headers=headers,
                        json={'dataset_id': 'dataset_123'})
```

### Whale Ranking API

```python
# Get whale rankings
response = requests.get('/api/whales/rankings', headers=headers,
                       params={'period': 'weekly', 'limit': 50})

# Get top performers
response = requests.get('/api/whales/top-performers', headers=headers,
                       params={'metric': 'score'})
```

### Merchant API

```python
# Create payment intent
response = requests.post('/api/payments/intent', headers=headers,
                        json={'amount': 29.99, 'payment_method': 'stripe'})

# Get subscription status
response = requests.get('/api/subscription/status', headers=headers)
```

## 💰 Pricing & Revenue

### Subscription Tiers

| Tier | Monthly | Annual | API Calls/Day | Signals/Day | Data Retention |
|------|---------|--------|---------------|-------------|----------------|
| Free | $0 | $0 | 100 | 10 | 7 days |
| Basic | $9.99 | $99.90 | 1,000 | 100 | 30 days |
| Pro | $29.99 | $299.90 | 10,000 | 1,000 | 90 days |
| Enterprise | $99.99 | $999.90 | Unlimited | Unlimited | 1 year |

### API Pricing

- Signal requests: $0.01 each
- Dataset downloads: $0.50 each
- Whale rankings: $0.02 per request
- Strategy analytics: $0.03 per request

### Revenue Channels

1. **Signal Subscriptions** - Real-time trading signals
2. **Data Sales** - Historical datasets and analytics
3. **API Access** - Programmatic data access
4. **Whale Intelligence** - Premium wallet rankings
5. **Strategy Insights** - Performance analytics

## 🔒 Security

### Data Protection
- End-to-end encryption for sensitive data
- Secure API key management with rotation
- Rate limiting and abuse prevention
- GDPR compliance features

### Access Control
- Role-based permissions
- API key authentication
- IP whitelisting options
- Audit logging

### Payment Security
- PCI DSS compliance (Stripe)
- Secure key management
- Transaction monitoring
- Fraud detection

## 📊 Monitoring & Analytics

### System Metrics
- Agent health and performance
- API response times and error rates
- Database query performance
- Payment processing success rates

### Business Metrics
- Revenue by channel and time period
- User acquisition and retention
- Popular datasets and signals
- Geographic usage patterns

### Monitoring Dashboard
Access real-time metrics via the API:

```python
# System health
response = requests.get('/api/health')

# Revenue analytics
response = requests.get('/api/analytics/revenue')

# User statistics
response = requests.get('/api/analytics/users')
```

## 🧪 Testing

### Run Integration Tests

```bash
# Full test suite
python test_commerce_system.py

# Quick smoke test
python test_commerce_system.py --quick

# Verbose output
python test_commerce_system.py --verbose
```

### Test Coverage

- ✅ Database connectivity and operations
- ✅ Agent initialization and health checks
- ✅ API endpoint functionality
- ✅ Payment processing simulation
- ✅ Data flow between agents
- ✅ Error handling and edge cases

### Rollout & Safeguards Checklist

- Configure API keys and allowed IPs before exposing the ingest endpoint.
- Keep `SIGNAL_TRIGGER_MODE=False` during initial rollout to retain polling as a fallback; enable once real-time traffic is verified.
- Monitor `signal_service_agent.health_check()` output for delivery backlog and subscription stats.
- Enable database logging/alerts to ensure persistence succeeds; ingestion responses include `stored` status for each signal.
- For trading agents, keep database insertion enabled until the commerce ingest API is confirmed stable in production.

## 🚀 Deployment

### Cross-VPS Architecture

Run trading ecosystems on separate VPS nodes by pointing them to shared cloud transports:

- **Shared Database (default)**: set `CORE_DB_URL` (plus optional `CORE_CRYPTO_DB_URL`, `CORE_FOREX_DB_URL`, `CORE_STOCK_DB_URL`) so each agent writes to the unified schema consumed by `data_aggregator`.
- **Redis Event Bus**: set `CORE_EVENT_BUS_BACKEND=redis` and `CORE_REDIS_URL=redis://...` to publish signals through Redis Streams.
- **Webhook Publishing**: set `CORE_EVENT_BUS_BACKEND=webhook`, supply `CORE_EVENT_WEBHOOK_URL` / `AGG_SIGNAL_ENDPOINT`, and configure API keys via `CORE_API_KEYS`.

See `docs/CROSS_VPS_DEPLOYMENT.md` for detailed topologies, environment variables, and operational checklists.

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "main.py"]
```

### Cloud Deployment

Recommended deployment targets:
- **AWS**: ECS/Fargate with RDS and S3
- **GCP**: Cloud Run with Firestore and Cloud Storage
- **Azure**: Container Apps with Cosmos DB and Blob Storage
- **Railway**: Simple deployment with built-in database
- **Render**: Managed cloud deployment

### Production Checklist

- [ ] Configure production database
- [ ] Set up payment processors
- [ ] Configure domain and SSL
- [ ] Set up monitoring and alerts
- [ ] Configure backup systems
- [ ] Test load handling
- [ ] Set up CDN for static assets

## 🤝 Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python test_commerce_system.py`
5. Submit a pull request

### Code Standards

- Type hints for all function parameters
- Comprehensive docstrings
- Unit tests for new features
- Integration tests for API changes

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Documentation
- [API Reference](docs/api.md)
- [Configuration Guide](docs/configuration.md)
- [Deployment Guide](docs/deployment.md)

### Community
- [Discord Server](https://discord.gg/itoro)
- [Telegram Channel](https://t.me/itoro_commerce)
- [GitHub Issues](https://github.com/itoro/commerce/issues)

### Enterprise Support
For enterprise deployments and custom integrations:
- Email: enterprise@itoro.com
- Schedule a call: [Calendly Link]

---

## 🎯 Roadmap

### Phase 1 (Current)
- [x] Core commerce agents
- [x] Payment processing
- [x] API infrastructure
- [x] Basic analytics

### Phase 2 (Next)
- [ ] Advanced AI-driven pricing
- [ ] Machine learning-based signal quality scoring
- [ ] Decentralized data marketplace integration
- [ ] Mobile app SDK
- [ ] Advanced risk management tools

### Phase 3 (Future)
- [ ] Cross-chain payment support
- [ ] AI-powered market prediction models
- [ ] Institutional-grade analytics platform
- [ ] Global compliance and localization

---

**Built with ❤️ by the ITORO team**

Transforming AI trading intelligence into sustainable revenue streams.
