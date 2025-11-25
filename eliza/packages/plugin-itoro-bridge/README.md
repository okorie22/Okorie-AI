# ITORO Bridge Plugin

A comprehensive bridge plugin for connecting ElizaOS with the ITORO multi-agent trading system. This plugin enables real-time awareness of all trading agent activities through RAG-based database access, event streaming, and data synchronization.

## Overview

The ITORO Bridge Plugin provides seamless integration between ElizaOS agents and the ITORO trading ecosystem, allowing:

- **Real-time Database Access**: Direct access to both paper trading and live trading databases
- **RAG-Powered Queries**: Retrieval-augmented generation for intelligent trading data analysis
- **Event Streaming**: Real-time event streaming via Redis for instant trading updates
- **Multi-Database Support**: Unified access to Supabase cloud databases and local SQLite databases
- **Advanced Trading Actions**: Portfolio analysis, trade history, risk metrics, and whale tracking
- **Data Synchronization**: Automatic sync between crypto, stock, and forex agents
- **Dynamic Agent Coordination**: Coordinate actions across all trading agent types

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ElizaOS ITORO Character                      │
│              (Chat Interface + AI Reasoning)                     │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│              ITORO Bridge Plugin (Enhanced)                      │
├─────────────────────────────────────────────────────────────────┤
│  • RAG Engine → Database Queries → Real Trading Data            │
│  • Event Stream Service → Redis → Real-time Updates            │
│  • Data Sync Services → Periodic Sync → Agent Data              │
│  • Event Bus Connector → ITORO Event Bus → Cross-Agent Events  │
│  • Agent Status Monitor → Health Tracking → Live Monitoring    │
│  • Live Data Feed → Real-time Streams → Subscription Service    │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│ Crypto Agents│ │Stock Agents │ │Forex Agents │
│              │ │             │ │             │
│ • Supabase DB │ │ • Databases │ │ • MT4/MT5   │
│ • SQLite DB   │ │ • Positions │ │ • Positions │
│ • Event Bus   │ │ • Events    │ │ • Events    │
│ • Status Mon. │ │ • Health    │ │ • Health    │
└───────┬──────┘ └──────┬──────┘ └──────┬──────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
            ┌───────────▼───────────┐
            │  ITORO Event Bus     │
            │  (Redis/Webhook)     │
            │  + Live Data Feeds   │
            └──────────────────────┘
```

## Key Services

### SupabaseDatabaseService
- **Multi-database support**: Connects to both Supabase cloud and local SQLite databases
- **Unified interface**: Single API for paper trading and live trading data
- **Automatic failover**: Falls back gracefully when databases are unavailable

### RAGEngine
- **Semantic search**: Understands natural language trading queries
- **Context aggregation**: Combines data from multiple sources for comprehensive answers
- **Query intent parsing**: Automatically categorizes user requests (portfolio, trades, risk, etc.)

### RedisEventStreamService
- **Real-time events**: Sub-second updates from trading agents
- **Event persistence**: Redis streams ensure no event loss
- **Multi-agent coordination**: Unified event format across all agent types

### UnifiedDataAggregator
- **Cross-market view**: Combines crypto, stock, and forex data into unified portfolio
- **Risk calculation**: Aggregated risk metrics across all trading activities
- **Performance analysis**: Unified P&L and performance tracking

### AgentStatusMonitor
- **Health tracking**: Real-time monitoring of all trading agents
- **Automatic failover**: Detects and reports agent failures
- **System diagnostics**: Comprehensive health checks and reporting

### LiveDataFeedService
- **Real-time subscriptions**: Filtered data feeds for specific users/interests
- **Event distribution**: Efficient distribution to multiple subscribers
- **Historical access**: Buffered recent events for catch-up

### EventBusConnector
- **ITORO integration**: Direct connection to ITORO's event bus system
- **Fallback support**: Automatic fallback to Redis when ITORO event bus unavailable
- **Cross-agent communication**: Enables agents to communicate through unified event system

### CryptoAgentSyncService
- **Periodic synchronization**: Configurable sync intervals (default 30 seconds)
- **Database monitoring**: Tracks changes in paper trading databases
- **Real-time updates**: Immediate sync on detected changes

## New Features

### Advanced Trading Actions
- **GET_TRADE_HISTORY**: Complete trading history with P&L analysis
- **GET_RISK_METRICS**: Comprehensive risk analysis with recommendations
- **COORDINATE_AGENTS**: Send commands to control trading agents

### Real-Time Capabilities
- **Live data feeds**: Subscribe to real-time trading updates
- **Agent health monitoring**: Track status of all trading agents
- **Event-driven updates**: Instant notifications of trading events

### Multi-Database Support
- **Supabase integration**: Cloud database support for live trading
- **SQLite fallback**: Local database support for paper trading
- **Unified queries**: Single interface for all data sources

### Enhanced Security
- **Service role keys**: Secure admin access to databases
- **HMAC authentication**: Secure webhook communication
- **Environment-based config**: Secure credential management

## Installation

1. Navigate to the plugin directory:
```bash
cd eliza/packages/plugin-itoro-bridge
```

2. Install dependencies:
```bash
bun install
```

3. Build the plugin:
```bash
bun run build
```

## Configuration

### Environment Variables

The plugin supports comprehensive configuration for different database types and real-time features:

#### Required Variables
- **ITORO_WEBHOOK_URL** (required): The base URL of the ITORO webhook server
- **ITORO_WEBHOOK_SECRET** (required): Secret key for HMAC signature authentication (minimum 32 characters)

#### Supabase Database Configuration
- **SUPABASE_PAPER_TRADING_URL**: Supabase project URL for paper trading data
- **SUPABASE_PAPER_TRADING_ANON_KEY**: Anonymous key for paper trading database
- **SUPABASE_LIVE_TRADING_URL**: Supabase project URL for live trading data
- **SUPABASE_LIVE_TRADING_ANON_KEY**: Anonymous key for live trading database
- **SUPABASE_SERVICE_ROLE_KEY**: Service role key for admin operations

#### Local Database Paths
- **PAPER_TRADING_DB_PATH**: Path to paper trading SQLite database (default: `multi-agents/itoro/ai_crypto_agents/data/paper_trading.db`)
- **LIVE_TRADING_DB_PATH**: Path to live trading SQLite database

#### Redis Configuration
- **REDIS_URL**: Redis connection URL (default: `redis://localhost:6379`)
- **REDIS_EVENT_STREAM_PREFIX**: Prefix for Redis event streams (default: `core_signals`)

#### Bridge Configuration
- **BRIDGE_MODE**: Bridge mode - 'unified' or 'individual' (default: 'unified')
- **MAX_CONCURRENT_AGENTS**: Maximum concurrent agent instances (default: 5, range: 1-10)
- **ENABLE_REAL_TIME_SYNC**: Enable real-time data synchronization (default: true)
- **SYNC_INTERVAL_MS**: Data sync interval in milliseconds (default: 30000)

### Example Configuration

Create a `.env` file in your ElizaOS root directory:

```env
# ITORO Webhook Configuration
ITORO_WEBHOOK_URL=http://localhost:8000
ITORO_WEBHOOK_SECRET=your_webhook_secret_here_minimum_32_chars

# Supabase Database Configuration
SUPABASE_PAPER_TRADING_URL=https://your-paper-trading-project.supabase.co
SUPABASE_PAPER_TRADING_ANON_KEY=your_paper_trading_anon_key
SUPABASE_LIVE_TRADING_URL=https://your-live-trading-project.supabase.co
SUPABASE_LIVE_TRADING_ANON_KEY=your_live_trading_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Local Database Paths
PAPER_TRADING_DB_PATH=multi-agents/itoro/ai_crypto_agents/data/paper_trading.db
LIVE_TRADING_DB_PATH=

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_EVENT_STREAM_PREFIX=core_signals

# Bridge Configuration
BRIDGE_MODE=unified
MAX_CONCURRENT_AGENTS=5
ENABLE_REAL_TIME_SYNC=true
SYNC_INTERVAL_MS=30000
```

## Usage

### Registering the Plugin

Add the plugin to your character configuration:

```typescript
import { itoroBridgePlugin } from '@elizaos/plugin-itoro-bridge';

const character = {
  name: 'ITORO',
  username: 'itoro_trading_advisor',
  plugins: [
    '@elizaos/plugin-itoro-bridge',
    // ... other plugins
  ],
  // ... character configuration
};
```

### Using Trading Actions

The plugin provides comprehensive trading actions powered by real database queries:

#### GET_PORTFOLIO

Retrieves current portfolio status from all connected databases:

```typescript
// User message: "Show me my portfolio status"
// Action: GET_PORTFOLIO
// Response: Unified portfolio data with positions, P&L, and market exposure across crypto/stock/forex
```

#### GET_TRADE_HISTORY

Retrieves trading history with optional filtering:

```typescript
// User message: "Show me my last 10 trades"
// Action: GET_TRADE_HISTORY
// Response: Formatted trade history with P&L, win rate, and performance metrics
```

#### GET_RISK_METRICS

Provides comprehensive risk analysis:

```typescript
// User message: "How risky is my portfolio?"
// Action: GET_RISK_METRICS
// Response: Risk metrics including drawdown, Sharpe ratio, volatility, and recommendations
```

#### GET_TRADE_HISTORY

Retrieves trading history with filtering:

```typescript
// User message: "Show me my last 10 trades"
// Action: GET_TRADE_HISTORY
// Response: Formatted trade history with P&L analysis and performance metrics
```

#### COORDINATE_AGENTS

Sends commands to coordinate trading agents:

```typescript
// User message: "Start all crypto agents"
// Action: COORDINATE_AGENTS
// Response: Coordination commands sent to specified agents with confirmation
```

#### TRADING_QUERY

Sends general trading queries to ITORO with RAG-powered responses:

```typescript
// User message: "What do you think about BTC right now?"
// Action: TRADING_QUERY
// Response: AI-powered trading analysis using real market data
```

### Webhook Endpoints

The plugin exposes the following HTTP endpoints:

#### POST `/api/bridge/itoro`

Receives webhook messages from ITORO:

```json
{
  "agent_id": "itoro",
  "message_type": "data_update",
  "content": {
    "text": "Portfolio updated",
    "metadata": {
      "priority": "medium",
      "context": {}
    }
  },
  "timestamp": "2024-01-01T00:00:00Z",
  "correlation_id": "uuid-here"
}
```

#### GET `/api/bridge/itoro/health`

Health check endpoint:

```json
{
  "status": "healthy",
  "service": "itoro-bridge",
  "activeAgents": 1,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## API Reference

### ITOROBridgeService

Main service class for managing the bridge connection.

**Methods:**

- `static start(runtime: IAgentRuntime): Promise<Service>` - Start the bridge service
- `static stop(runtime: IAgentRuntime): Promise<void>` - Stop the bridge service
- `handleWebhook(payload: any): Promise<void>` - Handle incoming webhook message
- `handleElizaMessage(params: { runtime: IAgentRuntime; message: Memory }): Promise<void>` - Handle ElizaOS message
- `getWebhookClient(): WebhookClient` - Get webhook client instance
- `getAgentManager(): AgentManager` - Get agent manager instance
- `getEventBridge(): EventBridge` - Get event bridge instance

### WebhookClient

Client for sending messages to ITORO webhook server.

**Methods:**

- `sendMessage(message: ITOROMessage): Promise<any>` - Send a message to ITORO
- `sendQuery(agentId: string, query: string, context?: any): Promise<ITOROMessage>` - Send a query and get response
- `waitForResponse(correlationId: string, timeout?: number): Promise<any>` - Wait for response with correlation ID

### AgentManager

Manages agent runtime instances.

**Methods:**

- `spawnAgent(agentId: string, characterConfig: Character): Promise<IAgentRuntime>` - Spawn a new agent
- `despawnAgent(agentId: string): Promise<void>` - Despawn an agent
- `getAgent(agentId: string): IAgentRuntime | undefined` - Get agent by ID
- `getActiveAgents(): string[]` - Get all active agent IDs
- `cleanup(): Promise<void>` - Cleanup all agents

### EventBridge

Handles bidirectional message conversion and routing.

**Methods:**

- `registerAgent(agentId: string, agentRuntime: IAgentRuntime): Promise<void>` - Register agent with bridge
- `unregisterAgent(agentId: string): Promise<void>` - Unregister agent
- `handleITOROMessage(itoroMessage: ITOROMessage): Promise<void>` - Handle ITORO message
- `getAgentRuntime(agentId: string): IAgentRuntime | null` - Get agent runtime

## Supported Agent Types

The plugin supports the following agent types (via AgentFactory):

- **itoro**: Economic & Financial Intelligence
- **ikon**: Media & Content Creation
- **mansa**: Business & Enterprise Intelligence
- **niani**: Governance & Coordination
- **simbon**: Defense & Security
- **xirsi**: Coordination & Communication
- **ginikandu**: Self-Evolution & Code Generation

## Error Handling

The plugin includes comprehensive error handling:

- **Webhook Connection Failures**: Automatic retry logic with exponential backoff
- **Invalid Message Format**: Validation and error reporting
- **Agent Spawn Failures**: Cleanup and error recovery
- **Timeout Handling**: Configurable timeouts for webhook requests

## Performance Considerations

- **Connection Pooling**: Webhook client uses connection pooling for efficiency
- **Message Queue**: High-throughput scenarios use message queuing
- **Agent Reuse**: Agent instances are reused when possible
- **Efficient Correlation Tracking**: Fast correlation ID lookup for request/response pairs

## Development

### Building

```bash
bun run build
```

### Testing

```bash
bun test
```

### Linting

```bash
bun run lint
```

## Troubleshooting

### Plugin Not Initializing

- Verify environment variables are set correctly
- Check that ITORO_WEBHOOK_URL is accessible
- Ensure ITORO_WEBHOOK_SECRET is at least 32 characters

### Webhook Messages Not Received

- Verify webhook endpoint is accessible at `/api/bridge/itoro`
- Check HMAC signature is being generated correctly
- Ensure ITORO server can reach your ElizaOS instance

### Agent Spawning Fails

- Check MAX_CONCURRENT_AGENTS limit
- Verify character configuration is valid
- Check runtime initialization logs

## License

MIT

## Contributing

Contributions are welcome! Please ensure:

1. Code follows the existing style
2. Tests are included for new features
3. Documentation is updated
4. All tests pass

## Support

For issues and questions, please open an issue on the repository.

