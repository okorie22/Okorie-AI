import type { IAgentRuntime, Memory } from '@elizaos/core';
import { Service, logger } from '@elizaos/core';
import { WebhookClient } from '../communication/webhook-client';
import { EventBridge } from '../communication/event-bridge';
import { AgentManager } from '../agent-manager';
import { ITOROCharacter } from '../characters/itoro-character';
import { ITOROMessage } from '../communication/webhook-client';
import { SupabaseDatabaseService } from './supabase-service';
import { RAGEngine } from './rag-engine';
import { RedisEventStreamService } from './redis-event-stream';
import { CryptoAgentSyncService } from './crypto-agent-sync';
import { UnifiedDataAggregator } from './unified-data-aggregator';
import { EventBusConnector } from './event-bus-connector';
import { AgentStatusMonitor } from './agent-status-monitor';
import { LiveDataFeedService } from './live-data-feed';
import { randomUUID } from 'crypto';

/**
 * ITORO Bridge Service for managing communication between ElizaOS and ITORO
 */
export class ITOROBridgeService extends Service {
  static serviceType = 'itoro-bridge';
  capabilityDescription =
    'Bridge service connecting ElizaOS with ITORO multi-agent trading system for bidirectional communication and real-time data synchronization.';

  private webhookClient: WebhookClient;
  private eventBridge: EventBridge;
  private agentManager: AgentManager;
  private dbService: SupabaseDatabaseService;
  private ragEngine: RAGEngine;
  private redisStream: RedisEventStreamService;
  private cryptoSync: CryptoAgentSyncService;
  private dataAggregator: UnifiedDataAggregator;
  private eventBusConnector: EventBusConnector;
  private agentStatusMonitor: AgentStatusMonitor;
  private liveDataFeed: LiveDataFeedService;
  private initialized = false;

  constructor(protected runtime: IAgentRuntime) {
    super(runtime);
  }

  /**
   * Start the bridge service
   */
  static async start(runtime: IAgentRuntime): Promise<Service> {
    logger.info('Starting ITORO Bridge Service');

    const service = new ITOROBridgeService(runtime);
    await service.initialize();

    return service;
  }

  /**
   * Stop the bridge service
   */
  static async stop(runtime: IAgentRuntime): Promise<void> {
    logger.info('Stopping ITORO Bridge Service');
    const service = runtime.getService(ITOROBridgeService.serviceType);
    if (!service) {
      throw new Error('ITORO bridge service not found');
    }
    await (service as ITOROBridgeService).stop();
  }

  /**
   * Initialize the bridge service
   */
  private async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    try {
      // Validate configuration
      const webhookUrl = process.env.ITORO_WEBHOOK_URL;
      const webhookSecret = process.env.ITORO_WEBHOOK_SECRET;

      if (!webhookUrl || !webhookSecret) {
        throw new Error(
          'ITORO_WEBHOOK_URL and ITORO_WEBHOOK_SECRET must be set in environment variables'
        );
      }

      // Initialize webhook client
      this.webhookClient = new WebhookClient({
        baseUrl: webhookUrl,
        secret: webhookSecret,
        timeout: 30000,
      });

      // Initialize event bridge
      this.eventBridge = new EventBridge(this.runtime, this.webhookClient);

      // Initialize database service
      this.dbService = new SupabaseDatabaseService();
      const dbConfigs: Record<string, any> = {};

      // Configure paper trading database
      const paperDBPath = process.env.PAPER_TRADING_DB_PATH || 'multi-agents/itoro/ai_crypto_agents/data/paper_trading.db';
      dbConfigs['paper_trading'] = {
        type: 'sqlite',
        path: paperDBPath,
        isPaperTrading: true
      };

      // Configure live trading database if available
      const liveDBPath = process.env.LIVE_TRADING_DB_PATH;
      if (liveDBPath) {
        dbConfigs['live_trading'] = {
          type: 'sqlite',
          path: liveDBPath,
          isPaperTrading: false
        };
      }

      // Configure Supabase database if available (using same env vars as working agents)
      if (process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE) {
        dbConfigs['supabase'] = {
          type: 'supabase',
          url: process.env.SUPABASE_URL,
          serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE,
          isPaperTrading: false // Will be determined by data source
        };
      }

      await this.dbService.initialize(dbConfigs);

      // Initialize RAG engine
      this.ragEngine = new RAGEngine(this.dbService);
      await this.ragEngine.initialize();

      // Initialize Redis event stream (optional - won't crash if Redis unavailable)
      this.redisStream = new RedisEventStreamService();
      const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';

      // Connect to Redis synchronously with timeout
      try {
        await this.redisStream.connect(redisUrl);
        logger.info('✓ Redis event stream connected');
      } catch (error) {
        logger.warn('⚠ Redis event stream unavailable, continuing without real-time events:', error.message);
      }

      // Initialize data aggregator
      this.dataAggregator = new UnifiedDataAggregator(this.dbService);
      await this.dataAggregator.initialize();

      // Initialize crypto sync service
      this.cryptoSync = new CryptoAgentSyncService(this.dbService);
      await this.cryptoSync.initialize(paperDBPath);

      // Initialize event bus connector AFTER Redis is connected
      this.eventBusConnector = new EventBusConnector(this.redisStream);
      try {
        await this.eventBusConnector.initialize();
        logger.info('✓ Event bus connector initialized');
      } catch (error) {
        logger.warn('⚠ Event bus connector failed, continuing without real-time events:', error.message);
      }

      // Initialize agent status monitor
      this.agentStatusMonitor = new AgentStatusMonitor(
        this.eventBusConnector,
        this.dbService,
        this.redisStream
      );
      try {
        await this.agentStatusMonitor.initialize();
        logger.info('✓ Agent status monitor initialized');
      } catch (error) {
        logger.warn('⚠ Agent status monitor failed:', error.message);
      }

      // Initialize live data feed service
      this.liveDataFeed = new LiveDataFeedService(
        this.agentStatusMonitor,
        this.redisStream
      );
      try {
        await this.liveDataFeed.initialize();
        logger.info('✓ Live data feed initialized');
      } catch (error) {
        logger.warn('⚠ Live data feed failed:', error.message);
      }

      // Start periodic sync if enabled
      const enableSync = process.env.ENABLE_REAL_TIME_SYNC !== 'false';
      if (enableSync) {
        const syncInterval = parseInt(process.env.SYNC_INTERVAL_MS || '30000', 10);
        this.cryptoSync.startPeriodicSync(syncInterval);
      }

      // Initialize agent manager
      this.agentManager = new AgentManager(this.runtime, this.eventBridge);
      await this.agentManager.initialize();

      // Spawn ITORO agent by default
      await this.agentManager.spawnAgent('itoro', ITOROCharacter);

      // Expose services for actions
      (this as any).webhookClient = this.webhookClient;
      (this as any).dbService = this.dbService;
      (this as any).ragEngine = this.ragEngine;
      (this as any).dataAggregator = this.dataAggregator;
      (this as any).redisStream = this.redisStream;
      (this as any).eventBusConnector = this.eventBusConnector;
      (this as any).agentStatusMonitor = this.agentStatusMonitor;
      (this as any).liveDataFeed = this.liveDataFeed;

      this.initialized = true;
      logger.info('ITORO Bridge Service initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize ITORO Bridge Service:', error);
      throw error;
    }
  }

  /**
   * Handle incoming webhook message from ITORO
   */
  async handleWebhook(payload: any): Promise<void> {
    try {
      // Convert payload to ITORO message format
      const itoroMessage: ITOROMessage = {
        agent_id: payload.agent_id || 'itoro',
        message_type: payload.message_type || 'data_update',
        content: {
          text: payload.content?.text || payload.text || '',
          metadata: {
            priority: payload.content?.metadata?.priority || 'medium',
            context: payload.content?.metadata?.context || {},
            source_agent: payload.content?.metadata?.source_agent,
            user_id: payload.content?.metadata?.user_id,
            room_id: payload.content?.metadata?.room_id,
            eliza_message_id: payload.content?.metadata?.eliza_message_id,
          },
        },
        timestamp: payload.timestamp || new Date().toISOString(),
        correlation_id: payload.correlation_id || randomUUID(),
      };

      // Forward to event bridge for processing
      await this.eventBridge.handleITOROMessage(itoroMessage);
    } catch (error) {
      logger.error('Failed to handle webhook message:', error);
      throw error;
    }
  }

  /**
   * Handle message from ElizaOS and forward to ITORO
   */
  async handleElizaMessage(params: { runtime: IAgentRuntime; message: Memory }): Promise<void> {
    try {
      const { message } = params;

      // Check if message should be forwarded to ITORO
      // Only forward messages that are relevant to trading
      const text = message.content.text?.toLowerCase() || '';
      const tradingKeywords = [
        'trade',
        'trading',
        'portfolio',
        'market',
        'crypto',
        'bitcoin',
        'btc',
        'position',
        'buy',
        'sell',
      ];

      const shouldForward = tradingKeywords.some((keyword) => text.includes(keyword));

      if (shouldForward && this.eventBridge) {
        // Get ITORO agent runtime
        const itoroAgent = this.agentManager.getAgent('itoro');
        if (itoroAgent) {
          // The event bridge will handle forwarding
          await this.eventBridge.handleAgentMessage('itoro', message);
        }
      }
    } catch (error) {
      logger.error('Failed to handle Eliza message:', error);
    }
  }

  /**
   * Get webhook client (exposed for actions)
   */
  getWebhookClient(): WebhookClient {
    return this.webhookClient;
  }

  /**
   * Get agent manager
   */
  getAgentManager(): AgentManager {
    return this.agentManager;
  }

  /**
   * Get event bridge
   */
  getEventBridge(): EventBridge {
    return this.eventBridge;
  }

  /**
   * Stop the service
   */
  async stop(): Promise<void> {
    logger.info('Stopping ITORO Bridge Service');

    // Stop periodic sync
    if (this.cryptoSync) {
      this.cryptoSync.stopPeriodicSync();
      await this.cryptoSync.cleanup();
    }

    // Clean up live data feed
    if (this.liveDataFeed) {
      await this.liveDataFeed.cleanup();
    }

    // Clean up agent status monitor
    if (this.agentStatusMonitor) {
      await this.agentStatusMonitor.cleanup();
    }

    // Clean up event bus connector
    if (this.eventBusConnector) {
      await this.eventBusConnector.cleanup();
    }

    // Disconnect Redis
    if (this.redisStream) {
      await this.redisStream.disconnect();
    }

    // Close database connections
    if (this.dbService) {
      await this.dbService.close();
    }

    if (this.agentManager) {
      await this.agentManager.cleanup();
    }

    if (this.webhookClient) {
      await this.webhookClient.disconnect();
    }

    this.initialized = false;
  }
}

