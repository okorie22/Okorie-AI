import { describe, test, expect, beforeEach, afterEach, mock } from 'bun:test';
import { AgentRuntime } from '@elizaos/core';
import { itoroBridgePlugin } from '../bridge-plugin';
import { ITOROBridgeService } from '../services/itoro-service';
import { SupabaseDatabaseService } from '../services/supabase-service';
import { RAGEngine } from '../services/rag-engine';
import { RedisEventStreamService } from '../services/redis-event-stream';
import { CryptoAgentSyncService } from '../services/crypto-agent-sync';
import { UnifiedDataAggregator } from '../services/unified-data-aggregator';
import { EventBusConnector } from '../services/event-bus-connector';
import { AgentStatusMonitor } from '../services/agent-status-monitor';
import { LiveDataFeedService } from '../services/live-data-feed';
import { WebhookClient } from '../communication/webhook-client';
import { AgentManager } from '../agent-manager';
import { getPortfolioAction } from '../actions/portfolio-action';
import { getTradeHistoryAction } from '../actions/trade-history-action';
import { getRiskMetricsAction } from '../actions/risk-metrics-action';
import { coordinateAgentsAction } from '../actions/agent-coordination-action';

describe('ITORO Bridge Integration', () => {
  let runtime: AgentRuntime;

  beforeEach(() => {
    // Create a mock runtime for testing
    runtime = new AgentRuntime({
      character: {
        name: 'Test',
        username: 'test',
        plugins: [],
      },
      plugins: [],
    });
  });

  afterEach(async () => {
    if (runtime) {
      await runtime.stop();
    }
  });

  test('should initialize bridge plugin with valid configuration', async () => {
    // Set up environment variables
    process.env.ITORO_WEBHOOK_URL = 'https://example.com/api';
    process.env.ITORO_WEBHOOK_SECRET = 'test-secret-key-that-is-at-least-32-characters-long';

    const config = {
      ITORO_WEBHOOK_URL: process.env.ITORO_WEBHOOK_URL,
      ITORO_WEBHOOK_SECRET: process.env.ITORO_WEBHOOK_SECRET,
      BRIDGE_MODE: 'unified',
      MAX_CONCURRENT_AGENTS: '5',
    };

    // Initialize plugin
    await expect(itoroBridgePlugin.init(config, runtime)).resolves.not.toThrow();
  });

  test('should reject invalid webhook URL', async () => {
    const config = {
      ITORO_WEBHOOK_URL: 'not-a-valid-url',
      ITORO_WEBHOOK_SECRET: 'test-secret-key-that-is-at-least-32-characters-long',
    };

    await expect(itoroBridgePlugin.init(config, runtime)).rejects.toThrow();
  });

  test('should reject short webhook secret', async () => {
    const config = {
      ITORO_WEBHOOK_URL: 'https://example.com/api',
      ITORO_WEBHOOK_SECRET: 'short',
    };

    await expect(itoroBridgePlugin.init(config, runtime)).rejects.toThrow();
  });

  test('should register bridge service', async () => {
    process.env.ITORO_WEBHOOK_URL = 'https://example.com/api';
    process.env.ITORO_WEBHOOK_SECRET = 'test-secret-key-that-is-at-least-32-characters-long';

    const config = {
      ITORO_WEBHOOK_URL: process.env.ITORO_WEBHOOK_URL,
      ITORO_WEBHOOK_SECRET: process.env.ITORO_WEBHOOK_SECRET,
    };

    await itoroBridgePlugin.init(config, runtime);

    const service = runtime.getService(ITOROBridgeService.serviceType);
    expect(service).toBeDefined();
    expect(service).toBeInstanceOf(ITOROBridgeService);
  });

  test('should have all trading actions', () => {
    expect(itoroBridgePlugin.actions).toBeDefined();
    expect(itoroBridgePlugin.actions?.length).toBeGreaterThan(0);

    const actionNames = itoroBridgePlugin.actions?.map((a) => a.name) || [];
    expect(actionNames).toContain('GET_PORTFOLIO');
    expect(actionNames).toContain('TRADING_QUERY');
    expect(actionNames).toContain('GET_TRADE_HISTORY');
    expect(actionNames).toContain('GET_RISK_METRICS');
    expect(actionNames).toContain('COORDINATE_AGENTS');
  });

  test('should have webhook and health routes', () => {
    expect(itoroBridgePlugin.routes).toBeDefined();
    expect(itoroBridgePlugin.routes?.length).toBeGreaterThan(0);

    const routePaths = itoroBridgePlugin.routes?.map((r) => r.path) || [];
    expect(routePaths).toContain('/api/bridge/itoro');
    expect(routePaths).toContain('/api/bridge/itoro/health');
  });

  test('should handle MESSAGE_RECEIVED events', () => {
    expect(itoroBridgePlugin.events).toBeDefined();
    expect(itoroBridgePlugin.events?.MESSAGE_RECEIVED).toBeDefined();
    expect(Array.isArray(itoroBridgePlugin.events?.MESSAGE_RECEIVED)).toBe(true);
  });
});

describe('WebhookClient', () => {
  test('should generate HMAC signature', () => {
    const client = new WebhookClient({
      baseUrl: 'https://example.com',
      secret: 'test-secret-key-that-is-at-least-32-characters-long',
    });

    // Access private method via type assertion for testing
    const payload = 'test payload';
    // In a real test, we would test the signature generation
    expect(client).toBeDefined();
  });
});

describe('AgentManager', () => {
  test('should enforce max concurrent agents limit', async () => {
    // This would require a full runtime setup
    // For now, we just verify the class exists
    expect(AgentManager).toBeDefined();
  });
});

describe('SupabaseDatabaseService', () => {
  test('should initialize with database configurations', async () => {
    const dbService = new SupabaseDatabaseService();

    const configs = {
      'test_db': {
        type: 'sqlite' as const,
        path: ':memory:'
      }
    };

    await expect(dbService.initialize(configs)).resolves.not.toThrow();
    expect(dbService.getAvailableDatabases()).toContain('test_db');
  });

  test('should return empty portfolio for missing database', async () => {
    const dbService = new SupabaseDatabaseService();
    await dbService.initialize({});

    const portfolio = await dbService.queryPortfolio('nonexistent', 'test_user');
    expect(portfolio.total_value).toBe(0);
    expect(portfolio.positions).toHaveLength(0);
  });
});

describe('RAGEngine', () => {
  let dbService: SupabaseDatabaseService;
  let ragEngine: RAGEngine;

  beforeEach(async () => {
    dbService = new SupabaseDatabaseService();
    await dbService.initialize({
      'test_db': {
        type: 'sqlite' as const,
        path: ':memory:'
      }
    });
    ragEngine = new RAGEngine(dbService);
    await ragEngine.initialize();
  });

  test('should initialize successfully', () => {
    expect(ragEngine).toBeDefined();
  });

  test('should handle portfolio queries', async () => {
    const result = await ragEngine.query('Show me my portfolio');

    expect(result).toBeDefined();
    expect(result.answer).toBeDefined();
    expect(result.confidence).toBeGreaterThan(0);
    expect(result.sources).toBeDefined();
  });

  test('should parse query intent correctly', () => {
    // Access private method for testing
    const engine = ragEngine as any;

    expect(engine.parseQueryIntent('show my portfolio')).toBe('portfolio');
    expect(engine.parseQueryIntent('what trades did I make')).toBe('trade_history');
    expect(engine.parseQueryIntent('how risky is my portfolio')).toBe('risk');
    expect(engine.parseQueryIntent('what are whales doing')).toBe('whale');
  });
});

describe('RedisEventStreamService', () => {
  let redisService: RedisEventStreamService;

  beforeEach(() => {
    redisService = new RedisEventStreamService();
  });

  test('should initialize', () => {
    expect(redisService).toBeDefined();
  });

  test('should not be connected initially', () => {
    expect(redisService.isConnected()).toBe(false);
  });

  test('should handle connection failure gracefully', async () => {
    // Try to connect to invalid Redis URL
    await expect(redisService.connect('redis://invalid-host:9999')).rejects.toThrow();
    expect(redisService.isConnected()).toBe(false);
  });
});

describe('UnifiedDataAggregator', () => {
  let dbService: SupabaseDatabaseService;
  let aggregator: UnifiedDataAggregator;

  beforeEach(async () => {
    dbService = new SupabaseDatabaseService();
    await dbService.initialize({
      'test_db': {
        type: 'sqlite' as const,
        path: ':memory:'
      }
    });
    aggregator = new UnifiedDataAggregator(dbService);
    await aggregator.initialize();
  });

  test('should get unified portfolio', async () => {
    const portfolio = await aggregator.getUnifiedPortfolio('test_user');

    expect(portfolio).toBeDefined();
    expect(portfolio.total_value).toBeDefined();
    expect(portfolio.positions).toBeDefined();
    expect(portfolio.sources).toBeDefined();
  });

  test('should calculate market exposure', async () => {
    const exposure = await aggregator.getMarketExposure('test_user');

    expect(exposure).toBeDefined();
    expect(exposure.total).toBeDefined();
    expect(typeof exposure.crypto).toBe('number');
    expect(typeof exposure.stocks).toBe('number');
    expect(typeof exposure.forex).toBe('number');
  });
});

describe('Trading Actions', () => {
  let mockRuntime: any;

  beforeEach(() => {
    mockRuntime = {
      getService: mock(() => ({
        dataAggregator: {
          getUnifiedPortfolio: mock(() => Promise.resolve({
            total_value: 100000,
            daily_pnl: 500,
            positions: [],
            risk_level: 'Normal',
            sources: ['test_db']
          }))
        }
      }))
    };
  });

  test('GET_PORTFOLIO action should handle requests', async () => {
    const message = {
      entityId: 'test_user',
      roomId: 'test_room',
      content: { text: 'show portfolio', source: 'user' },
      id: 'test_message_id'
    };

    const result = await getPortfolioAction.handler(
      mockRuntime,
      message,
      undefined,
      {},
      mock(() => Promise.resolve())
    );

    expect(result.success).toBe(true);
    expect(result.data.portfolio).toBeDefined();
  });

  test('GET_TRADE_HISTORY action should handle requests', async () => {
    const message = {
      entityId: 'test_user',
      roomId: 'test_room',
      content: { text: 'show my trades', source: 'user' },
      id: 'test_message_id'
    };

    const result = await getTradeHistoryAction.handler(
      mockRuntime,
      message,
      undefined,
      {},
      mock(() => Promise.resolve())
    );

    expect(result.success).toBe(true);
  });

  test('GET_RISK_METRICS action should handle requests', async () => {
    const message = {
      entityId: 'test_user',
      roomId: 'test_room',
      content: { text: 'how risky is my portfolio', source: 'user' },
      id: 'test_message_id'
    };

    const result = await getRiskMetricsAction.handler(
      mockRuntime,
      message,
      undefined,
      {},
      mock(() => Promise.resolve())
    );

    expect(result.success).toBe(true);
  });

  test('COORDINATE_AGENTS action should parse commands', async () => {
    const message = {
      entityId: 'test_user',
      roomId: 'test_room',
      content: { text: 'start all crypto agents', source: 'user' },
      id: 'test_message_id'
    };

    const result = await coordinateAgentsAction.handler(
      mockRuntime,
      message,
      undefined,
      {},
      mock(() => Promise.resolve())
    );

    expect(result.success).toBe(true);
  });
});

describe('Event Bus Connector', () => {
  let redisService: RedisEventStreamService;
  let eventBusConnector: EventBusConnector;

  beforeEach(() => {
    redisService = new RedisEventStreamService();
    eventBusConnector = new EventBusConnector(redisService);
  });

  test('should initialize', async () => {
    await expect(eventBusConnector.initialize()).resolves.not.toThrow();
  });

  test('should report connection status', () => {
    const status = eventBusConnector.getConnectionStatus();
    expect(status).toBeDefined();
    expect(status.initialized).toBe(true);
    expect(typeof status.itoroEventBusConnected).toBe('boolean');
  });
});

describe('Agent Status Monitor', () => {
  let eventBusConnector: EventBusConnector;
  let dbService: SupabaseDatabaseService;
  let redisService: RedisEventStreamService;
  let statusMonitor: AgentStatusMonitor;

  beforeEach(async () => {
    eventBusConnector = new EventBusConnector({} as RedisEventStreamService);
    dbService = new SupabaseDatabaseService();
    redisService = new RedisEventStreamService();

    await dbService.initialize({
      'test_db': {
        type: 'sqlite' as const,
        path: ':memory:'
      }
    });

    statusMonitor = new AgentStatusMonitor(eventBusConnector, dbService, redisService);
  });

  test('should initialize', async () => {
    await expect(statusMonitor.initialize()).resolves.not.toThrow();
  });

  test('should provide system health status', () => {
    const health = statusMonitor.getSystemHealthStatus();
    expect(health).toBeDefined();
    expect(health.agent_statuses).toBeDefined();
    expect(typeof health.overall_health).toBe('number');
  });

  test('should provide live data feed', () => {
    const feed = statusMonitor.getLiveDataFeed(10);
    expect(Array.isArray(feed)).toBe(true);
  });
});

describe('Live Data Feed Service', () => {
  let statusMonitor: AgentStatusMonitor;
  let redisService: RedisEventStreamService;
  let liveDataFeed: LiveDataFeedService;

  beforeEach(async () => {
    statusMonitor = new AgentStatusMonitor({} as EventBusConnector, {} as SupabaseDatabaseService, {} as RedisEventStreamService);
    redisService = new RedisEventStreamService();
    liveDataFeed = new LiveDataFeedService(statusMonitor, redisService);
  });

  test('should initialize', async () => {
    await expect(liveDataFeed.initialize()).resolves.not.toThrow();
  });

  test('should provide feed statistics', () => {
    const stats = liveDataFeed.getFeedStatistics();
    expect(stats).toBeDefined();
    expect(typeof stats.totalSubscriptions).toBe('number');
  });

  test('should create subscriptions', () => {
    const subscriptionId = liveDataFeed.subscribeToFeed({
      userId: 'test_user',
      filters: {},
      callback: () => {}
    });

    expect(typeof subscriptionId).toBe('string');
    expect(subscriptionId).toBeTruthy();
  });
});

describe('End-to-End Integration', () => {
  test('should handle complete plugin lifecycle', async () => {
    // Set up comprehensive environment
    process.env.ITORO_WEBHOOK_URL = 'https://example.com/api';
    process.env.ITORO_WEBHOOK_SECRET = 'test-secret-key-that-is-at-least-32-characters-long';
    process.env.REDIS_URL = 'redis://localhost:6379';
    process.env.PAPER_TRADING_DB_PATH = ':memory:';
    process.env.ENABLE_REAL_TIME_SYNC = 'false'; // Disable for testing

    const config = {
      ITORO_WEBHOOK_URL: process.env.ITORO_WEBHOOK_URL,
      ITORO_WEBHOOK_SECRET: process.env.ITORO_WEBHOOK_SECRET,
      REDIS_URL: process.env.REDIS_URL,
      PAPER_TRADING_DB_PATH: process.env.PAPER_TRADING_DB_PATH,
      ENABLE_REAL_TIME_SYNC: process.env.ENABLE_REAL_TIME_SYNC
    };

    // Create runtime
    const runtime = new AgentRuntime({
      character: {
        name: 'Test ITORO',
        username: 'itoro_test',
        plugins: [],
      },
      plugins: [],
    });

    try {
      // Initialize plugin
      await itoroBridgePlugin.init(config, runtime);

      // Verify services are registered
      const bridgeService = runtime.getService(ITOROBridgeService.serviceType);
      expect(bridgeService).toBeDefined();

      // Test service access
      const service = bridgeService as ITOROBridgeService;
      expect(service.getAgentManager()).toBeDefined();

    } finally {
      await runtime.stop();
    }
  });
});

