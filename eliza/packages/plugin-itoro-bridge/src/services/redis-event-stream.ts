import { createClient, RedisClientType } from 'redis';
import { logger } from '@elizaos/core';

/**
 * Unified Trading Signal interface
 */
export interface UnifiedTradingSignal {
  signal_id: string;
  agent_type: 'crypto' | 'stock' | 'forex' | 'risk' | 'sentiment' | 'whale';
  signal_type: 'buy' | 'sell' | 'hold' | 'alert' | 'info';
  symbol: string;
  price?: number;
  confidence: number;
  timestamp: string;
  metadata: Record<string, any>;
}

/**
 * Event handler type
 */
export type EventHandler = (event: UnifiedTradingSignal) => Promise<void>;

/**
 * Redis Event Stream Service
 * Connects to ITORO's Redis event bus for real-time trading updates
 */
export class RedisEventStreamService {
  private client: RedisClientType | null = null;
  private subscriber: RedisClientType | null = null;
  private eventHandlers: Map<string, EventHandler[]> = new Map();
  private connected = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 5000;

  /**
   * Connect to Redis
   */
  async connect(redisUrl: string): Promise<void> {
    try {
      logger.info('Connecting to Redis event stream:', redisUrl);

      // Create main client for publishing
      this.client = createClient({ url: redisUrl });
      this.client.on('error', (error) => {
        logger.error('Redis client error:', error);
      });

      // Create subscriber client
      this.subscriber = createClient({ url: redisUrl });
      this.subscriber.on('error', (error) => {
        logger.error('Redis subscriber error:', error);
      });

      // Connect both clients
      await Promise.all([
        this.client.connect(),
        this.subscriber.connect()
      ]);

      this.connected = true;
      this.reconnectAttempts = 0;
      logger.info('Successfully connected to Redis event stream');
    } catch (error) {
      logger.error('Failed to connect to Redis:', error);
      throw error;
    }
  }

  /**
   * Disconnect from Redis
   */
  async disconnect(): Promise<void> {
    logger.info('Disconnecting from Redis event stream');

    if (this.client) {
      await this.client.disconnect();
      this.client = null;
    }

    if (this.subscriber) {
      await this.subscriber.disconnect();
      this.subscriber = null;
    }

    this.connected = false;
    this.eventHandlers.clear();
  }

  /**
   * Subscribe to trading signals stream
   */
  async subscribeToSignals(streamPrefix = 'core_signals'): Promise<void> {
    if (!this.subscriber || !this.connected) {
      throw new Error('Redis subscriber not connected');
    }

    try {
      // Subscribe to different signal streams
      const streams = [
        `${streamPrefix}:signals`,
        `${streamPrefix}:whale_rankings`,
        `${streamPrefix}:portfolio_updates`,
        `${streamPrefix}:risk_alerts`,
        `${streamPrefix}:trade_executions`
      ];

      for (const stream of streams) {
        await this.subscribeToStream(stream);
        logger.info(`Subscribed to Redis stream: ${stream}`);
      }
    } catch (error) {
      logger.error('Failed to subscribe to signal streams:', error);
      throw error;
    }
  }

  /**
   * Subscribe to a specific stream
   */
  private async subscribeToStream(streamName: string): Promise<void> {
    if (!this.subscriber) {
      throw new Error('Redis subscriber not available');
    }

    // Use Redis streams (XREAD) for persistent message queues
    await this.startStreamConsumer(streamName);
  }

  /**
   * Start stream consumer for persistent streams
   */
  private async startStreamConsumer(streamName: string): Promise<void> {
    if (!this.subscriber) return;

    const consumerGroup = 'eliza_bridge';
    const consumerName = `consumer_${Date.now()}`;

    try {
      // Create consumer group if it doesn't exist
      await this.subscriber.xGroupCreate(streamName, consumerGroup, '0', {
        MKSTREAM: true
      });
    } catch (error: any) {
      // Ignore if consumer group already exists
      if (!error.message.includes('BUSYGROUP')) {
        logger.warn(`Failed to create consumer group for ${streamName}:`, error);
      }
    }

    // Start consuming messages
    this.consumeStreamMessages(streamName, consumerGroup, consumerName);
  }

  /**
   * Consume messages from stream
   */
  private async consumeStreamMessages(
    streamName: string,
    consumerGroup: string,
    consumerName: string
  ): Promise<void> {
    if (!this.subscriber) return;

    while (this.connected) {
      try {
        // Read pending messages
        const messages = await this.subscriber.xReadGroup(
          consumerGroup,
          consumerName,
          [{ key: streamName, id: '>' }],
          { COUNT: 10, BLOCK: 5000 }
        );

        if (messages && messages.length > 0) {
          for (const message of messages) {
            await this.processStreamMessage(streamName, message);
          }
        }
      } catch (error) {
        logger.error(`Error consuming messages from ${streamName}:`, error);

        // If consumer doesn't exist, try to recreate it
        if (error instanceof Error && error.message.includes('NOGROUP')) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          await this.startStreamConsumer(streamName);
        }
      }
    }
  }

  /**
   * Process a stream message
   */
  private async processStreamMessage(streamName: string, message: any): Promise<void> {
    try {
      const messageId = message.id;
      const messageData = message.messages[0]?.message;

      if (!messageData) {
        logger.warn(`Empty message received from ${streamName}`);
        return;
      }

      // Parse the trading signal
      const signal = this.parseTradingSignal(messageData);

      if (signal) {
        // Acknowledge the message
        await this.subscriber!.xAck(streamName, 'eliza_bridge', messageId);

        // Process the signal
        await this.handleTradingSignal(signal);
      }
    } catch (error) {
      logger.error(`Failed to process stream message from ${streamName}:`, error);
    }
  }

  /**
   * Parse trading signal from message data
   */
  private parseTradingSignal(data: any): UnifiedTradingSignal | null {
    try {
      // Handle different message formats
      let signalData: any;

      if (typeof data === 'string') {
        signalData = JSON.parse(data);
      } else {
        signalData = data;
      }

      // Normalize to UnifiedTradingSignal format
      const signal: UnifiedTradingSignal = {
        signal_id: signalData.signal_id || signalData.id || `signal_${Date.now()}`,
        agent_type: this.mapAgentType(signalData.agent_type || signalData.source),
        signal_type: this.mapSignalType(signalData.signal_type || signalData.type),
        symbol: signalData.symbol || signalData.asset || '',
        price: signalData.price ? parseFloat(signalData.price) : undefined,
        confidence: signalData.confidence ? parseFloat(signalData.confidence) : 0.5,
        timestamp: signalData.timestamp || new Date().toISOString(),
        metadata: signalData.metadata || {}
      };

      return signal;
    } catch (error) {
      logger.error('Failed to parse trading signal:', error);
      return null;
    }
  }

  /**
   * Map agent type to standardized format
   */
  private mapAgentType(agentType: string): UnifiedTradingSignal['agent_type'] {
    const type = agentType?.toLowerCase();
    if (type?.includes('crypto')) return 'crypto';
    if (type?.includes('stock')) return 'stock';
    if (type?.includes('forex')) return 'forex';
    if (type?.includes('risk')) return 'risk';
    if (type?.includes('sentiment')) return 'sentiment';
    if (type?.includes('whale')) return 'whale';
    return 'crypto'; // default
  }

  /**
   * Map signal type to standardized format
   */
  private mapSignalType(signalType: string): UnifiedTradingSignal['signal_type'] {
    const type = signalType?.toLowerCase();
    if (type?.includes('buy')) return 'buy';
    if (type?.includes('sell')) return 'sell';
    if (type?.includes('hold')) return 'hold';
    if (type?.includes('alert')) return 'alert';
    if (type?.includes('info')) return 'info';
    return 'info'; // default
  }

  /**
   * Handle incoming trading signal
   */
  private async handleTradingSignal(signal: UnifiedTradingSignal): Promise<void> {
    logger.info(`Processing trading signal: ${signal.signal_type} ${signal.symbol} from ${signal.agent_type} agent`);

    // Get handlers for this agent type
    const handlers = this.eventHandlers.get(signal.agent_type) || [];

    // Also get general handlers
    const generalHandlers = this.eventHandlers.get('all') || [];

    const allHandlers = [...handlers, ...generalHandlers];

    // Process with all relevant handlers
    await Promise.allSettled(
      allHandlers.map(handler => handler(signal))
    );
  }

  /**
   * Register event handler for specific agent type
   */
  registerEventHandler(agentType: string, handler: EventHandler): void {
    if (!this.eventHandlers.has(agentType)) {
      this.eventHandlers.set(agentType, []);
    }
    this.eventHandlers.get(agentType)!.push(handler);
    logger.info(`Registered event handler for agent type: ${agentType}`);
  }

  /**
   * Publish event to Redis stream
   */
  async publishEvent(streamName: string, event: UnifiedTradingSignal): Promise<void> {
    if (!this.client || !this.connected) {
      throw new Error('Redis client not connected');
    }

    try {
      const messageId = await this.client.xAdd(streamName, '*', {
        signal_id: event.signal_id,
        agent_type: event.agent_type,
        signal_type: event.signal_type,
        symbol: event.symbol,
        price: event.price?.toString() || '',
        confidence: event.confidence.toString(),
        timestamp: event.timestamp,
        metadata: JSON.stringify(event.metadata)
      });

      logger.info(`Published event to ${streamName}: ${messageId}`);
    } catch (error) {
      logger.error(`Failed to publish event to ${streamName}:`, error);
      throw error;
    }
  }

  /**
   * Publish trading signal to ITORO event bus
   */
  async publishTradingSignal(signal: UnifiedTradingSignal, streamPrefix = 'core_signals'): Promise<void> {
    const streamName = `${streamPrefix}:signals`;
    await this.publishEvent(streamName, signal);
  }

  /**
   * Get connection status
   */
  isConnected(): boolean {
    return this.connected;
  }

  /**
   * Get stream info for debugging
   */
  async getStreamInfo(streamName: string): Promise<any> {
    if (!this.client || !this.connected) {
      throw new Error('Redis client not connected');
    }

    try {
      const info = await this.client.xInfoStream(streamName);
      return info;
    } catch (error) {
      logger.error(`Failed to get stream info for ${streamName}:`, error);
      return null;
    }
  }

  /**
   * Attempt to reconnect to Redis
   */
  private async attemptReconnect(redisUrl: string): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      logger.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    logger.info(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    try {
      await new Promise(resolve => setTimeout(resolve, this.reconnectDelay));
      await this.connect(redisUrl);
      logger.info('Successfully reconnected to Redis');
    } catch (error) {
      logger.error(`Reconnection attempt ${this.reconnectAttempts} failed:`, error);
      await this.attemptReconnect(redisUrl);
    }
  }
}
