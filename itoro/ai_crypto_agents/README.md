# 🌙 Anarcho Capital's AI Crypto Trading Agent Package

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Alpha-orange.svg)](https://github.com)

> **Advanced webhook-driven multi-agent cryptocurrency trading system with AI-powered decision making, risk management, and portfolio optimization.**

## 🚀 Overview

Anarcho Capital's AI Crypto Trading Agent Package is a sophisticated, event-driven trading system designed for automated cryptocurrency trading on the Solana blockchain. The system uses multiple specialized AI agents working in coordination to execute trades, manage risk, and optimize portfolio performance.

### Key Features

- **🤖 Multi-Agent Architecture**: Specialized agents for different trading functions
- **📡 Webhook-Driven**: Real-time event processing for instant trade execution
- **🛡️ Advanced Risk Management**: AI-powered risk assessment and emergency stops
- **📊 Portfolio Optimization**: Automated rebalancing and harvesting
- **🔒 Staking Integration**: Automated SOL staking for yield generation
- **📈 Technical Analysis**: AI-powered chart analysis and sentiment tracking
- **🐋 Whale Tracking**: Monitor and copy successful traders
- **💰 Paper Trading**: Safe testing environment with simulated trading
- **🌐 DeFi Integration**: Automated DeFi protocol interactions

## 🏗️ System Architecture

The system operates across multiple terminals with specialized responsibilities:

```
┌─────────────────────────────────────────────────────────────┐
│                    🌐 Webhook Server (Render)              │
│              Receives blockchain events via Helius         │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              🖥️ Terminal 1: Main Trading Coordinator       │
│  • CopyBot Agent (Primary Trading)                         │
│  • Risk Agent (Emergency Management)                       │
│  • Harvesting Agent (Portfolio Management)                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              🔒 Terminal 2: Staking Agent                  │
│  • Automated SOL staking                                   │
│  • Yield optimization                                       │
│  • Reward compounding                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              📊 Terminal 3: Data Collection                │
│  • Whale Agent (Track successful traders)                  │
│  • Sentiment Agent (Social media analysis)                 │
│  • Chart Analysis Agent (Technical indicators)             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              🌐 Terminal 4: DeFi Operations                │
│  • DeFi protocol interactions                              │
│  • Yield farming automation                                │
│  • Liquidity management                                     │
└─────────────────────────────────────────────────────────────┘
```

## 🌐 Cross-VPS Deployment

To run the crypto agents on dedicated VPS instances while sharing data with the commerce layer, configure the shared transport variables described in `docs/CROSS_VPS_DEPLOYMENT.md`:

- `CORE_CRYPTO_DB_URL` for the shared Postgres/Supabase instance (or `CORE_DB_URL` as a fallback).
- Optionally `CORE_EVENT_BUS_BACKEND=redis` with `CORE_REDIS_URL` to stream signals through Redis.
- Optionally `CORE_EVENT_BUS_BACKEND=webhook` with `CORE_EVENT_WEBHOOK_URL` / `CORE_EVENT_WEBHOOK_SECRET` to publish directly to the data aggregator.

After setting the environment variables, start the agents normally; the new event bus layer forwards signals to the configured cloud transport.

## 🤖 Trading Agents

### 1. CopyBot Agent (Primary Trading)
- **Purpose**: Executes all trading decisions based on tracked wallet activities
- **Features**:
  - Real-time wallet monitoring
  - AI-powered trade analysis
  - Position sizing optimization
  - Mirror trading capabilities
- **Safety Guards**:
  - Maximum 10% single position size
  - Maximum 60% total portfolio allocation
  - Blocks SOL/USDC trading

### 2. Risk Agent (Emergency Management)
- **Purpose**: Portfolio protection and emergency stops
- **Triggers**:
  - 5+ consecutive losses
  - 15%+ portfolio drawdown
  - Balance below $100
  - System errors
- **Actions**:
  - Emergency stop trading
  - Selective position closure
  - Portfolio rebalancing
  - System restart protocols

### 3. Harvesting Agent (Portfolio Management)
- **Purpose**: Portfolio optimization and gains management
- **Features**:
  - Dust conversion (small balances)
  - SOL/USDC rebalancing (10% SOL, 20% USDC targets)
  - Realized gains reallocation
  - External wallet transfers
- **Triggers**: Portfolio tracker events

### 4. Staking Agent (Yield Generation)
- **Purpose**: Automated SOL staking for passive income
- **Features**:
  - Multi-protocol staking (BlazeStake, Jito, Lido)
  - APY optimization
  - Reward compounding
  - Independent operation

### 5. Whale Agent (Market Intelligence)
- **Purpose**: Track and analyze successful traders
- **Features**:
  - Wallet performance scoring
  - PnL analysis (1d, 7d, 30d)
  - Win rate tracking
  - Dynamic wallet selection

### 6. Sentiment Agent (Market Psychology)
- **Purpose**: Social media sentiment analysis
- **Features**:
  - Twitter/X sentiment tracking
  - BERT-based analysis
  - Market mood indicators
  - Voice announcements

### 7. Chart Analysis Agent (Technical Analysis)
- **Purpose**: Technical indicator analysis
- **Features**:
  - Multi-timeframe analysis
  - RSI, MACD, EMA indicators
  - Fibonacci retracements
  - AI-powered buy/sell signals

## 🛠️ Installation

### Prerequisites

- Python 3.8 or higher
- Solana wallet with SOL for fees
- API keys for required services

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/ai-crypto-trading-agent-package.git
   cd ai-crypto-trading-agent-package
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and wallet address
   ```

4. **Run system health check**:
   ```bash
   python deploy/system_health_dashboard.py
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Wallet Configuration
DEFAULT_WALLET_ADDRESS=your_solana_wallet_address
PRIVATE_KEY=your_private_key

# API Keys
BIRDEYE_API_KEY=your_birdeye_api_key
HELIUS_API_KEY=your_helius_api_key
QUICKNODE_RPC_ENDPOINT=your_quicknode_endpoint
JUPITER_API_KEY=your_jupiter_api_key

# AI Models
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key

# Trading Configuration
PAPER_TRADING_ENABLED=true
POSITION_SIZE_PERCENTAGE=0.05
MAX_POSITION_SIZE_USD=100.0
```

### Key Configuration Files

- `src/config.py` - Main configuration file
- `src/data/wallets.json` - Tracked wallet addresses
- `deploy/app.py` - Webhook server configuration

## 🚀 Usage

### Starting the System

1. **Terminal 1 - Main Trading**:
   ```bash
   python src/main.py
   ```

2. **Terminal 2 - Staking**:
   ```bash
   python src/agents/staking_agent.py
   ```

3. **Terminal 3 - Data Collection**:
   ```bash
   python src/data.py
   ```

4. **Terminal 4 - DeFi Operations**:
   ```bash
   python src/defi.py
   ```

### Webhook Server (Production)

```bash
python deploy/app.py
```

### System Monitoring

```bash
python deploy/system_health_dashboard.py
```

## 📊 Trading Modes

### Paper Trading (Default)
- Simulated trading with virtual balance
- Safe testing environment
- Full feature testing without risk
- Configurable initial balance

### Live Trading
- Real cryptocurrency trading
- Requires funded wallet
- Higher risk - use with caution
- Enable in configuration

## 🛡️ Risk Management

### Built-in Safety Features

- **Position Limits**: Maximum position sizes and total allocation
- **Emergency Stops**: Automatic trading halt on risk triggers
- **Drawdown Protection**: Portfolio protection mechanisms
- **Balance Monitoring**: Minimum balance requirements
- **Error Handling**: Comprehensive error recovery

### Risk Parameters

- Maximum single position: 10% of portfolio
- Maximum total allocation: 60% of portfolio
- Emergency stop: 15% drawdown or 5+ consecutive losses
- Minimum balance: $100 USD

## 📈 Performance Monitoring

### Real-time Dashboard

The system includes a comprehensive monitoring dashboard:

- Live portfolio balance
- Position summaries
- Trading metrics
- Agent status
- Risk indicators
- Performance analytics

### Health Reports

Export detailed system health reports:

```bash
python deploy/system_health_dashboard.py --export
```

## 🔧 Advanced Features

### AI Integration

- **Multiple LLM Support**: Claude, GPT-4, DeepSeek
- **Model Selection**: Automatic best model selection
- **Confidence Scoring**: AI decision confidence levels
- **Sentiment Analysis**: Market psychology integration

### DeFi Automation

- **Yield Farming**: Automated yield optimization
- **Liquidity Management**: Dynamic liquidity allocation
- **Protocol Integration**: Multiple DeFi protocols
- **Risk Assessment**: DeFi-specific risk management

### Portfolio Optimization

- **Dynamic Rebalancing**: Automatic portfolio rebalancing
- **Dust Conversion**: Small balance optimization
- **Gains Harvesting**: Profit realization strategies
- **External Transfers**: Automated profit distribution

## 📚 Documentation

### Video Tutorials

Comprehensive video documentation is available:
- [Complete Documentation Playlist](https://www.youtube.com/playlist?list=PLXrNVMjRZUJg4M4uz52iGd1LhXXGVbIFz)

### Additional Resources

- `docs/` - Detailed documentation
- `test/` - Test files and examples
- `deploy/` - Deployment tools and scripts

## ⚠️ Important Disclaimers

### Risk Warning

- **High Risk**: Cryptocurrency trading involves substantial risk
- **No Guarantees**: Past performance doesn't guarantee future results
- **Test First**: Always test with paper trading before live trading
- **Monitor Closely**: Never leave the system unattended
- **Start Small**: Begin with small position sizes

### Legal Notice

- This software is for educational and research purposes
- Users are responsible for compliance with local regulations
- No financial advice is provided
- Use at your own risk

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Getting Help

1. Check the [documentation videos](https://www.youtube.com/playlist?list=PLXrNVMjRZUJg4M4uz52iGd1LhXXGVbIFz)
2. Review the configuration files
3. Check system health dashboard
4. Review logs in `logs/` directory

### Common Issues

- **API Key Errors**: Verify all API keys are correctly configured
- **Wallet Issues**: Ensure wallet has sufficient SOL for fees
- **Connection Problems**: Check RPC endpoint connectivity
- **Agent Conflicts**: Ensure only one instance of each agent runs

## 🌟 Acknowledgments

- Built with love by Anarcho Capital 🌙
- Powered by advanced AI and blockchain technology
- Community-driven development and testing

---

**⚠️ Remember**: This is alpha software. Always test thoroughly and never risk more than you can afford to lose.

**🚀 Ready to start?** Begin with paper trading and gradually increase your position sizes as you become comfortable with the system.

---

*For the latest updates and community discussions, join our community channels.*
