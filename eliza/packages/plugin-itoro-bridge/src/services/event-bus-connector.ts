import { logger } from '@elizaos/core';
import { RedisEventStreamService, UnifiedTradingSignal } from './redis-event-stream';

/**
 * ITORO Event Bus Message Format
 */
export interface ITOROEventBusMessage {
  event_type: string;
  agent_id: string;
  data: any;
  timestamp: string;
  correlation_id?: string;
  metadata?: Record<string, any>;
}

/**
 * Event Bus Backend Types
 */
export type EventBusBackend = 'redis' | 'webhook' | 'memory';

/**
 * Event Bus Connector for ITORO Integration
 * Connects directly to ITORO's event bus system using their patterns
 */
export class EventBusConnector {
  private redisStream: RedisEventStreamService;
  private eventBusBackend: EventBusBackend;
  private itoroEventBus: any = null; // ITORO's global event bus instance
  private initialized = false;
  private eventHandlers: Map<string, Function[]> = new Map();

  constructor(redisStream: RedisEventStreamService) {
    this.redisStream = redisStream;
  }

  /**
   * Initialize the event bus connector
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    try {
      // Determine event bus backend from environment
      this.eventBusBackend = this.getEventBusBackend();

      logger.info(`Initializing Event Bus Connector with ${this.eventBusBackend} backend`);

      // Try to connect to ITORO's global event bus
      await this.connectToITOROEventBus();

      // Set up event handlers for different event types
      this.setupEventHandlers();

      this.initialized = true;
      logger.info('Event Bus Connector initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize Event Bus Connector:', error);
      throw error;
    }
  }

  /**
   * Connect to ITORO's global event bus
   */
  private async connectToITOROEventBus(): Promise<void> {
    try {
      // Try to import and connect to ITORO's event bus
      // This assumes ITORO exposes a global event bus instance
      const itoroModule = await this.tryImportITOROModule();

      if (itoroModule && itoroModule.get_global_event_bus) {
        this.itoroEventBus = itoroModule.get_global_event_bus();
        logger.info('Connected to ITORO global event bus');

        // Subscribe to ITORO event bus topics
        await this.subscribeToITOROEvents();
      } else {
        logger.warn('ITORO global event bus not available, falling back to Redis');
        await this.initializeRedisFallback();
      }
    } catch (error) {
      logger.warn('Failed to connect to ITORO event bus, using Redis fallback:', error);
      await this.initializeRedisFallback();
    }
  }

  /**
   * Try to import ITORO event bus module
   */
  private async tryImportITOROModule(): Promise<any> {
    try {
      // Try different paths where ITORO might expose the event bus
      const possiblePaths = [
        '../../../multi-agents/itoro/core/event_bus',
        '../../../multi-agents/itoro/core',
        '../multi-agents/itoro/core/event_bus'
      ];

      for (const path of possiblePaths) {
        try {
          const module = await import(path);
          if (module.get_global_event_bus) {
            return module;
          }
        } catch (e) {
          // Continue to next path
        }
      }
    } catch (error) {
      // All import attempts failed
    }

    return null;
  }

  /**
   * Initialize Redis as fallback event bus
   */
  private async initializeRedisFallback(): Promise<void> {
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    await this.redisStream.connect(redisUrl);

    const streamPrefix = process.env.REDIS_EVENT_STREAM_PREFIX || 'core_signals';
    await this.redisStream.subscribeToSignals(streamPrefix);
  }

  /**
   * Subscribe to ITORO event bus events
   */
  private async subscribeToITOROEvents(): Promise<void> {
    if (!this.itoroEventBus) return;

    const eventTopics = [
      'signals',
      'whale_rankings',
      'portfolio_updates',
      'risk_alerts',
      'trade_executions',
      'agent_status',
      'market_data'
    ];

    for (const topic of eventTopics) {
      try {
        await this.itoroEventBus.subscribe(topic, (message: ITOROEventBusMessage) => {
          this.handleITOROEvent(topic, message);
        });
        logger.info(`Subscribed to ITORO event bus topic: ${topic}`);
      } catch (error) {
        logger.error(`Failed to subscribe to ITORO topic ${topic}:`, error);
      }
    }
  }

  /**
   * Handle events from ITORO event bus
   */
  private async handleITOROEvent(topic: string, message: ITOROEventBusMessage): Promise<void> {
    try {
      logger.info(`Received ITORO event: ${topic}`, message);

      // Convert ITORO message to UnifiedTradingSignal
      const signal = this.convertITOROToUnifiedSignal(topic, message);

      if (signal) {
        // Call registered handlers
        const handlers = this.eventHandlers.get(topic) || [];
        await Promise.allSettled(
          handlers.map(handler => handler(signal))
        );

        // Also forward through Redis if connected
        if (this.redisStream.isConnected()) {
          await this.redisStream.publishTradingSignal(signal);
        }
      }
    } catch (error) {
      logger.error(`Failed to handle ITORO event ${topic}:`, error);
    }
  }

  /**
   * Convert ITORO event bus message to UnifiedTradingSignal
   */
  private convertITOROToUnifiedSignal(topic: string, message: ITOROEventBusMessage): UnifiedTradingSignal | null {
    try {
      const agentType = this.mapITOROAgentType(message.agent_id);
      const signalType = this.mapITOROSignalType(topic, message.data);

      return {
        signal_id: message.correlation_id || `itoro_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        agent_type: agentType,
        signal_type: signalType,
        symbol: message.data.symbol || message.data.asset || '',
        price: message.data.price ? parseFloat(message.data.price) : undefined,
        confidence: message.data.confidence ? parseFloat(message.data.confidence) : 0.8,
        timestamp: message.timestamp,
        metadata: {
          ...message.metadata,
          itoro_event_type: topic,
          itoro_agent_id: message.agent_id,
          source: 'itoro_event_bus'
        }
      };
    } catch (error) {
      logger.error('Failed to convert ITORO message to unified signal:', error);
      return null;
    }
  }

  /**
   * Map ITORO agent ID to unified agent type
   */
  private mapITOROAgentType(agentId: string): UnifiedTradingSignal['agent_type'] {
    const id = agentId.toLowerCase();
    if (id.includes('crypto')) return 'crypto';
    if (id.includes('stock')) return 'stock';
    if (id.includes('forex')) return 'forex';
    if (id.includes('risk')) return 'risk';
    if (id.includes('sentiment')) return 'sentiment';
    if (id.includes('whale')) return 'whale';
    return 'crypto'; // default
  }

  /**
   * Map ITORO event topic to unified signal type
   */
  private mapITOROSignalType(topic: string, data: any): UnifiedTradingSignal['signal_type'] {
    switch (topic) {
      case 'signals':
        return data.signal === 'buy' ? 'buy' : data.signal === 'sell' ? 'sell' : 'info';
      case 'risk_alerts':
        return 'alert';
      case 'trade_executions':
        return 'info';
      default:
        return 'info';
    }
  }

  /**
   * Set up event handlers for different event types
   */
  private setupEventHandlers(): void {
    // Register handlers for different event types
    this.registerEventHandler('signals', this.handleTradingSignal.bind(this));
    this.registerEventHandler('whale_rankings', this.handleWhaleSignal.bind(this));
    this.registerEventHandler('portfolio_updates', this.handlePortfolioUpdate.bind(this));
    this.registerEventHandler('risk_alerts', this.handleRiskAlert.bind(this));
    this.registerEventHandler('trade_executions', this.handleTradeExecution.bind(this));
    this.registerEventHandler('agent_status', this.handleAgentStatus.bind(this));
  }

  /**
   * Register event handler for specific topic
   */
  registerEventHandler(topic: string, handler: Function): void {
    if (!this.eventHandlers.has(topic)) {
      this.eventHandlers.set(topic, []);
    }
    this.eventHandlers.get(topic)!.push(handler);
    logger.info(`Registered event handler for topic: ${topic}`);
  }

  /**
   * Publish event to ITORO event bus
   */
  async publishToITOROEventBus(topic: string, message: ITOROEventBusMessage): Promise<void> {
    if (this.itoroEventBus && typeof this.itoroEventBus.publish === 'function') {
      await this.itoroEventBus.publish(topic, message);
      logger.info(`Published message to ITORO event bus topic: ${topic}`);
    } else {
      // Fallback to Redis
      await this.publishToRedisFallback(topic, message);
    }
  }

  /**
   * Publish to Redis as fallback
   */
  private async publishToRedisFallback(topic: string, message: ITOROEventBusMessage): Promise<void> {
    if (!this.redisStream.isConnected()) return;

    const signal = this.convertITOROToUnifiedSignal(topic, message);
    if (signal) {
      const streamName = `core_signals:${topic}`;
      await this.redisStream.publishEvent(streamName, signal);
    }
  }

  /**
   * Get event bus backend type
   */
  private getEventBusBackend(): EventBusBackend {
    const backend = process.env.CORE_EVENT_BUS_BACKEND;
    if (backend === 'redis' || backend === 'webhook' || backend === 'memory') {
      return backend;
    }
    return 'redis'; // default
  }

  /**
   * Event handler methods
   */
  private async handleTradingSignal(signal: UnifiedTradingSignal): Promise<void> {
    logger.info(`Processing trading signal: ${signal.signal_type} ${signal.symbol}`);
    // Forward to ElizaOS runtime or handle locally
  }

  private async handleWhaleSignal(signal: UnifiedTradingSignal): Promise<void> {
    logger.info(`Processing whale signal: ${signal.symbol}`);
    // Handle whale movement signals
  }

  private async handlePortfolioUpdate(signal: UnifiedTradingSignal): Promise<void> {
    logger.info(`Processing portfolio update`);
    // Handle portfolio update notifications
  }

  private async handleRiskAlert(signal: UnifiedTradingSignal): Promise<void> {
    logger.info(`Processing risk alert: ${signal.metadata?.alert_type}`);
    // Handle risk management alerts
  }

  private async handleTradeExecution(signal: UnifiedTradingSignal): Promise<void> {
    logger.info(`Processing trade execution: ${signal.symbol}`);
    // Handle trade execution confirmations
  }

  private async handleAgentStatus(signal: UnifiedTradingSignal): Promise<void> {
    logger.info(`Processing agent status update: ${signal.metadata?.agent_id}`);
    // Handle agent health/status updates
  }

  /**
   * Get connection status
   */
  getConnectionStatus(): {
    initialized: boolean;
    itoroEventBusConnected: boolean;
    redisFallbackConnected: boolean;
    backend: EventBusBackend;
  } {
    return {
      initialized: this.initialized,
      itoroEventBusConnected: this.itoroEventBus !== null,
      redisFallbackConnected: this.redisStream.isConnected(),
      backend: this.eventBusBackend
    };
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    if (this.itoroEventBus && typeof this.itoroEventBus.disconnect === 'function') {
      await this.itoroEventBus.disconnect();
    }

    await this.redisStream.disconnect();
    this.eventHandlers.clear();
    this.initialized = false;

    logger.info('Event Bus Connector cleaned up');
  }
}
