import { logger } from '@elizaos/core';
import { AgentStatusMonitor, LiveDataFeedItem } from './agent-status-monitor';
import { RedisEventStreamService, UnifiedTradingSignal } from './redis-event-stream';

/**
 * Data Feed Subscription
 */
export interface DataFeedSubscription {
  id: string;
  userId: string;
  filters: {
    agentTypes?: string[];
    symbols?: string[];
    eventTypes?: string[];
    minPriority?: 'low' | 'medium' | 'high' | 'urgent';
  };
  callback: (item: LiveDataFeedItem) => void;
  active: boolean;
}

/**
 * Live Data Feed Service
 * Provides real-time data feeds to ElizaOS with filtering and subscription management
 */
export class LiveDataFeedService {
  private statusMonitor: AgentStatusMonitor;
  private redisStream: RedisEventStreamService;
  private subscriptions: Map<string, DataFeedSubscription> = new Map();
  private feedBuffer: LiveDataFeedItem[] = [];
  private maxBufferSize = 1000;
  private initialized = false;

  constructor(statusMonitor: AgentStatusMonitor, redisStream: RedisEventStreamService) {
    this.statusMonitor = statusMonitor;
    this.redisStream = redisStream;
  }

  /**
   * Initialize the live data feed service
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    try {
      logger.info('Initializing Live Data Feed Service');

      // Set up event handlers for real-time data processing
      this.setupEventHandlers();

      this.initialized = true;
      logger.info('Live Data Feed Service initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize Live Data Feed Service:', error);
      throw error;
    }
  }

  /**
   * Set up event handlers for real-time data
   */
  private setupEventHandlers(): void {
    // Register handlers for all event types
    this.redisStream.registerEventHandler('crypto', this.handleRealtimeEvent.bind(this));
    this.redisStream.registerEventHandler('stock', this.handleRealtimeEvent.bind(this));
    this.redisStream.registerEventHandler('forex', this.handleRealtimeEvent.bind(this));
    this.redisStream.registerEventHandler('risk', this.handleRealtimeEvent.bind(this));
    this.redisStream.registerEventHandler('sentiment', this.handleRealtimeEvent.bind(this));
    this.redisStream.registerEventHandler('whale', this.handleRealtimeEvent.bind(this));
  }

  /**
   * Handle real-time events and distribute to subscribers
   */
  private async handleRealtimeEvent(signal: UnifiedTradingSignal): Promise<void> {
    try {
      // Create feed item from signal
      const feedItem: LiveDataFeedItem = {
        id: signal.signal_id,
        type: this.mapSignalToFeedType(signal),
        agent_id: signal.metadata?.agent_id || `${signal.agent_type}_agent`,
        symbol: signal.symbol,
        data: {
          signal_type: signal.signal_type,
          confidence: signal.confidence,
          price: signal.price,
          metadata: signal.metadata
        },
        timestamp: signal.timestamp,
        priority: signal.metadata?.priority || 'medium'
      };

      // Add to buffer
      this.addToBuffer(feedItem);

      // Distribute to subscribers
      await this.distributeToSubscribers(feedItem);

    } catch (error) {
      logger.error('Failed to handle real-time event:', error);
    }
  }

  /**
   * Map signal to feed item type
   */
  private mapSignalToFeedType(signal: UnifiedTradingSignal): LiveDataFeedItem['type'] {
    if (signal.metadata?.trade_execution) return 'trade';
    if (signal.metadata?.alert_type) return 'alert';
    if (signal.metadata?.status_update) return 'status';
    if (signal.metadata?.market_data) return 'market_data';
    return 'signal';
  }

  /**
   * Add item to feed buffer
   */
  private addToBuffer(item: LiveDataFeedItem): void {
    this.feedBuffer.unshift(item);

    // Maintain buffer size
    if (this.feedBuffer.length > this.maxBufferSize) {
      this.feedBuffer = this.feedBuffer.slice(0, this.maxBufferSize);
    }
  }

  /**
   * Distribute feed item to matching subscribers
   */
  private async distributeToSubscribers(item: LiveDataFeedItem): Promise<void> {
    const matchingSubscriptions = Array.from(this.subscriptions.values())
      .filter(sub => sub.active && this.matchesFilters(sub, item));

    for (const subscription of matchingSubscriptions) {
      try {
        await subscription.callback(item);
      } catch (error) {
        logger.error(`Failed to deliver feed item to subscription ${subscription.id}:`, error);
      }
    }
  }

  /**
   * Check if feed item matches subscription filters
   */
  private matchesFilters(subscription: DataFeedSubscription, item: LiveDataFeedItem): boolean {
    const filters = subscription.filters;

    // Check agent types
    if (filters.agentTypes && filters.agentTypes.length > 0) {
      const agentType = item.agent_id.split('_')[0]; // Extract agent type from ID
      if (!filters.agentTypes.includes(agentType)) return false;
    }

    // Check symbols
    if (filters.symbols && filters.symbols.length > 0) {
      if (!item.symbol || !filters.symbols.includes(item.symbol)) return false;
    }

    // Check event types
    if (filters.eventTypes && filters.eventTypes.length > 0) {
      if (!filters.eventTypes.includes(item.type)) return false;
    }

    // Check priority
    if (filters.minPriority) {
      const priorityOrder = { low: 0, medium: 1, high: 2, urgent: 3 };
      const itemPriority = priorityOrder[item.priority];
      const minPriority = priorityOrder[filters.minPriority];
      if (itemPriority < minPriority) return false;
    }

    return true;
  }

  /**
   * Subscribe to live data feed
   */
  subscribeToFeed(subscription: Omit<DataFeedSubscription, 'id' | 'active'>): string {
    const id = `feed_sub_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const fullSubscription: DataFeedSubscription = {
      ...subscription,
      id,
      active: true
    };

    this.subscriptions.set(id, fullSubscription);
    logger.info(`Created data feed subscription: ${id}`);

    return id;
  }

  /**
   * Unsubscribe from live data feed
   */
  unsubscribeFromFeed(subscriptionId: string): boolean {
    const subscription = this.subscriptions.get(subscriptionId);
    if (subscription) {
      subscription.active = false;
      this.subscriptions.delete(subscriptionId);
      logger.info(`Removed data feed subscription: ${subscriptionId}`);
      return true;
    }
    return false;
  }

  /**
   * Get buffered feed items with optional filtering
   */
  getBufferedFeed(options?: {
    limit?: number;
    agentTypes?: string[];
    symbols?: string[];
    eventTypes?: string[];
    since?: Date;
  }): LiveDataFeedItem[] {
    let feed = [...this.feedBuffer];

    // Apply time filter
    if (options?.since) {
      const sinceTime = options.since.getTime();
      feed = feed.filter(item => new Date(item.timestamp).getTime() >= sinceTime);
    }

    // Apply other filters
    if (options?.agentTypes && options.agentTypes.length > 0) {
      feed = feed.filter(item => {
        const agentType = item.agent_id.split('_')[0];
        return options.agentTypes!.includes(agentType);
      });
    }

    if (options?.symbols && options.symbols.length > 0) {
      feed = feed.filter(item => item.symbol && options.symbols!.includes(item.symbol));
    }

    if (options?.eventTypes && options.eventTypes.length > 0) {
      feed = feed.filter(item => options.eventTypes!.includes(item.type));
    }

    // Apply limit
    if (options?.limit) {
      feed = feed.slice(0, options.limit);
    }

    return feed;
  }

  /**
   * Get real-time market data snapshot
   */
  async getMarketDataSnapshot(): Promise<{
    cryptoPrices: Record<string, number>;
    stockPrices: Record<string, number>;
    forexRates: Record<string, number>;
    timestamp: string;
  }> {
    // In a real implementation, this would query live market data APIs
    // For now, return a mock snapshot based on recent feed data

    const recentFeed = this.getBufferedFeed({ limit: 50, since: new Date(Date.now() - 300000) }); // Last 5 minutes

    const cryptoPrices: Record<string, number> = {};
    const stockPrices: Record<string, number> = {};
    const forexRates: Record<string, number> = {};

    // Extract prices from recent feed items
    for (const item of recentFeed) {
      if (item.data.price && item.symbol) {
        const agentType = item.agent_id.split('_')[0];

        switch (agentType) {
          case 'crypto':
            cryptoPrices[item.symbol] = item.data.price;
            break;
          case 'stock':
            stockPrices[item.symbol] = item.data.price;
            break;
          case 'forex':
            forexRates[item.symbol] = item.data.price;
            break;
        }
      }
    }

    return {
      cryptoPrices,
      stockPrices,
      forexRates,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Get active subscription count
   */
  getActiveSubscriptionCount(): number {
    return Array.from(this.subscriptions.values()).filter(sub => sub.active).length;
  }

  /**
   * Get feed statistics
   */
  getFeedStatistics(): {
    totalSubscriptions: number;
    activeSubscriptions: number;
    bufferedItems: number;
    oldestItemAge: number;
    newestItemAge: number;
  } {
    const activeSubscriptions = Array.from(this.subscriptions.values()).filter(sub => sub.active).length;
    const now = Date.now();

    let oldestItemAge = 0;
    let newestItemAge = 0;

    if (this.feedBuffer.length > 0) {
      const oldestItem = this.feedBuffer[this.feedBuffer.length - 1];
      const newestItem = this.feedBuffer[0];

      oldestItemAge = now - new Date(oldestItem.timestamp).getTime();
      newestItemAge = now - new Date(newestItem.timestamp).getTime();
    }

    return {
      totalSubscriptions: this.subscriptions.size,
      activeSubscriptions,
      bufferedItems: this.feedBuffer.length,
      oldestItemAge,
      newestItemAge
    };
  }

  /**
   * Broadcast custom event to all subscribers
   */
  async broadcastEvent(event: Omit<LiveDataFeedItem, 'id'>): Promise<void> {
    const feedItem: LiveDataFeedItem = {
      ...event,
      id: `broadcast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    };

    this.addToBuffer(feedItem);
    await this.distributeToSubscribers(feedItem);
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    this.subscriptions.clear();
    this.feedBuffer.length = 0;
    this.initialized = false;

    logger.info('Live Data Feed Service cleaned up');
  }
}
