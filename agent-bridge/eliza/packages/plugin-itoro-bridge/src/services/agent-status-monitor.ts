import { logger } from '@elizaos/core';
import { EventBusConnector } from './event-bus-connector';
import { SupabaseDatabaseService } from './supabase-service';
import { RedisEventStreamService, UnifiedTradingSignal } from './redis-event-stream';

/**
 * Agent Status Information
 */
export interface AgentStatus {
  agent_id: string;
  agent_type: 'crypto' | 'stock' | 'forex' | 'risk' | 'sentiment' | 'whale';
  status: 'online' | 'offline' | 'error' | 'maintenance';
  last_seen: string;
  version?: string;
  uptime_seconds?: number;
  memory_usage_mb?: number;
  active_trades?: number;
  last_trade_time?: string;
  health_score: number; // 0-100
  error_count?: number;
  metadata?: Record<string, any>;
}

/**
 * System Health Status
 */
export interface SystemHealthStatus {
  overall_health: number;
  total_agents: number;
  online_agents: number;
  offline_agents: number;
  error_agents: number;
  last_updated: string;
  agent_statuses: AgentStatus[];
  system_load: {
    cpu_percent: number;
    memory_percent: number;
    disk_usage_percent: number;
  };
}

/**
 * Live Data Feed Item
 */
export interface LiveDataFeedItem {
  id: string;
  type: 'trade' | 'signal' | 'alert' | 'status' | 'market_data';
  agent_id: string;
  symbol?: string;
  data: any;
  timestamp: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
}

/**
 * Agent Status Monitor Service
 * Monitors status of all trading agents and provides live data feeds
 */
export class AgentStatusMonitor {
  private eventBusConnector: EventBusConnector;
  private dbService: SupabaseDatabaseService;
  private redisStream: RedisEventStreamService;
  private agentStatuses: Map<string, AgentStatus> = new Map();
  private liveDataFeed: LiveDataFeedItem[] = [];
  private maxFeedItems = 100;
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private initialized = false;

  constructor(
    eventBusConnector: EventBusConnector,
    dbService: SupabaseDatabaseService,
    redisStream: RedisEventStreamService
  ) {
    this.eventBusConnector = eventBusConnector;
    this.dbService = dbService;
    this.redisStream = redisStream;
  }

  /**
   * Initialize the agent status monitor
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    try {
      logger.info('Initializing Agent Status Monitor');

      // Set up event handlers for status monitoring
      this.setupEventHandlers();

      // Start periodic health checks
      this.startHealthChecks();

      // Load initial agent statuses
      await this.loadInitialAgentStatuses();

      this.initialized = true;
      logger.info('Agent Status Monitor initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize Agent Status Monitor:', error);
      throw error;
    }
  }

  /**
   * Set up event handlers for monitoring agent activities
   */
  private setupEventHandlers(): void {
    // Register handlers for all agent types
    const agentTypes: UnifiedTradingSignal['agent_type'][] = ['crypto', 'stock', 'forex', 'risk', 'sentiment', 'whale'];

    for (const agentType of agentTypes) {
      this.redisStream.registerEventHandler(agentType, this.handleAgentSignal.bind(this));
    }

    // Register ITORO event bus handlers
    this.eventBusConnector.registerEventHandler('agent_status', this.handleAgentStatusUpdate.bind(this));
    this.eventBusConnector.registerEventHandler('trade_executions', this.handleTradeExecution.bind(this));
    this.eventBusConnector.registerEventHandler('signals', this.handleTradingSignal.bind(this));
    this.eventBusConnector.registerEventHandler('risk_alerts', this.handleRiskAlert.bind(this));
  }

  /**
   * Start periodic health checks
   */
  private startHealthChecks(): void {
    const intervalMs = parseInt(process.env.HEALTH_CHECK_INTERVAL_MS || '30000', 10);

    this.healthCheckInterval = setInterval(async () => {
      try {
        await this.performHealthChecks();
      } catch (error) {
        logger.error('Health check failed:', error);
      }
    }, intervalMs);

    logger.info(`Started health checks every ${intervalMs}ms`);
  }

  /**
   * Perform periodic health checks
   */
  private async performHealthChecks(): Promise<void> {
    const now = new Date();
    const timeoutMs = 60000; // 1 minute timeout

    for (const [agentId, status] of this.agentStatuses) {
      const lastSeen = new Date(status.last_seen);
      const timeSinceLastSeen = now.getTime() - lastSeen.getTime();

      // Mark as offline if no activity for timeout period
      if (timeSinceLastSeen > timeoutMs && status.status === 'online') {
        this.updateAgentStatus(agentId, {
          ...status,
          status: 'offline',
          health_score: Math.max(0, status.health_score - 10)
        });
      }

      // Send ping/health check signal
      await this.sendHealthCheckPing(agentId);
    }
  }

  /**
   * Send health check ping to agent
   */
  private async sendHealthCheckPing(agentId: string): Promise<void> {
    const pingSignal: UnifiedTradingSignal = {
      signal_id: `health_ping_${Date.now()}_${agentId}`,
      agent_type: this.getAgentTypeFromId(agentId),
      signal_type: 'info',
      symbol: 'HEALTH_CHECK',
      confidence: 1.0,
      timestamp: new Date().toISOString(),
      metadata: {
        ping: true,
        source: 'status_monitor'
      }
    };

    try {
      await this.redisStream.publishTradingSignal(pingSignal);
    } catch (error) {
      logger.warn(`Failed to send health ping to ${agentId}:`, error);
    }
  }

  /**
   * Load initial agent statuses from database
   */
  private async loadInitialAgentStatuses(): Promise<void> {
    try {
      // Query agent statuses from databases
      const availableDBs = this.dbService.getAvailableDatabases();

      for (const dbName of availableDBs) {
        try {
          // This would query an agent_status table in the database
          // For now, we'll create default statuses for known agent types
          await this.createDefaultAgentStatuses(dbName);
        } catch (error) {
          logger.warn(`Failed to load agent statuses from ${dbName}:`, error);
        }
      }
    } catch (error) {
      logger.warn('Failed to load initial agent statuses:', error);
    }
  }

  /**
   * Create default agent statuses for known agent types
   */
  private async createDefaultAgentStatuses(dbName: string): Promise<void> {
    const agentTypes = ['crypto', 'stock', 'forex'];
    const now = new Date().toISOString();

    for (const agentType of agentTypes) {
      const agentId = `${agentType}_agent_1`; // Default agent ID

      if (!this.agentStatuses.has(agentId)) {
        const status: AgentStatus = {
          agent_id: agentId,
          agent_type: agentType as AgentStatus['agent_type'],
          status: 'offline', // Start as offline, will be updated when agents come online
          last_seen: now,
          health_score: 50,
          active_trades: 0,
          error_count: 0
        };

        this.agentStatuses.set(agentId, status);
      }
    }
  }

  /**
   * Handle agent signal events
   */
  private async handleAgentSignal(signal: UnifiedTradingSignal): Promise<void> {
    const agentId = signal.metadata?.agent_id || `${signal.agent_type}_agent_1`;

    // Update agent status to online and update last seen
    this.updateAgentStatus(agentId, {
      status: 'online',
      last_seen: signal.timestamp,
      health_score: Math.min(100, (this.agentStatuses.get(agentId)?.health_score || 50) + 5)
    });

    // Add to live data feed
    this.addToLiveDataFeed({
      id: signal.signal_id,
      type: 'signal',
      agent_id: agentId,
      symbol: signal.symbol,
      data: signal,
      timestamp: signal.timestamp,
      priority: signal.metadata?.priority === 'urgent' ? 'urgent' : 'medium'
    });
  }

  /**
   * Handle agent status update events
   */
  private async handleAgentStatusUpdate(signal: UnifiedTradingSignal): Promise<void> {
    const agentId = signal.metadata?.agent_id || signal.agent_type;
    const statusData = signal.metadata?.status_data || {};

    const status: Partial<AgentStatus> = {
      status: statusData.status || 'online',
      last_seen: signal.timestamp,
      version: statusData.version,
      uptime_seconds: statusData.uptime_seconds,
      memory_usage_mb: statusData.memory_usage_mb,
      active_trades: statusData.active_trades,
      last_trade_time: statusData.last_trade_time,
      health_score: statusData.health_score || 80,
      error_count: statusData.error_count || 0,
      metadata: statusData.metadata
    };

    this.updateAgentStatus(agentId, status);

    // Add to live data feed
    this.addToLiveDataFeed({
      id: signal.signal_id,
      type: 'status',
      agent_id: agentId,
      data: statusData,
      timestamp: signal.timestamp,
      priority: 'low'
    });
  }

  /**
   * Handle trade execution events
   */
  private async handleTradeExecution(signal: UnifiedTradingSignal): Promise<void> {
    const agentId = signal.metadata?.agent_id || signal.agent_type;

    // Update agent status
    const currentStatus = this.agentStatuses.get(agentId);
    if (currentStatus) {
      this.updateAgentStatus(agentId, {
        last_trade_time: signal.timestamp,
        active_trades: (currentStatus.active_trades || 0) + 1,
        health_score: Math.min(100, currentStatus.health_score + 1)
      });
    }

    // Add to live data feed
    this.addToLiveDataFeed({
      id: signal.signal_id,
      type: 'trade',
      agent_id: agentId,
      symbol: signal.symbol,
      data: {
        side: signal.metadata?.side,
        size: signal.metadata?.size,
        price: signal.price,
        pnl: signal.metadata?.pnl
      },
      timestamp: signal.timestamp,
      priority: 'high'
    });
  }

  /**
   * Handle trading signals
   */
  private async handleTradingSignal(signal: UnifiedTradingSignal): Promise<void> {
    const agentId = signal.metadata?.agent_id || signal.agent_type;

    // Add to live data feed
    this.addToLiveDataFeed({
      id: signal.signal_id,
      type: 'signal',
      agent_id: agentId,
      symbol: signal.symbol,
      data: {
        signal_type: signal.signal_type,
        confidence: signal.confidence,
        price: signal.price
      },
      timestamp: signal.timestamp,
      priority: signal.metadata?.priority === 'urgent' ? 'urgent' : 'medium'
    });
  }

  /**
   * Handle risk alerts
   */
  private async handleRiskAlert(signal: UnifiedTradingSignal): Promise<void> {
    const agentId = signal.metadata?.agent_id || 'risk_agent';

    // Update agent status if it's a risk agent
    if (agentId.includes('risk')) {
      this.updateAgentStatus(agentId, {
        status: 'online',
        last_seen: signal.timestamp,
        health_score: signal.metadata?.severity === 'critical' ? 60 : 80
      });
    }

    // Add to live data feed
    this.addToLiveDataFeed({
      id: signal.signal_id,
      type: 'alert',
      agent_id: agentId,
      symbol: signal.symbol,
      data: {
        alert_type: signal.metadata?.alert_type,
        severity: signal.metadata?.severity,
        message: signal.metadata?.message
      },
      timestamp: signal.timestamp,
      priority: signal.metadata?.severity === 'critical' ? 'urgent' : 'high'
    });
  }

  /**
   * Update agent status
   */
  private updateAgentStatus(agentId: string, updates: Partial<AgentStatus>): void {
    const currentStatus = this.agentStatuses.get(agentId);
    const agentType = this.getAgentTypeFromId(agentId);

    const newStatus: AgentStatus = {
      agent_id: agentId,
      agent_type: agentType,
      status: 'offline',
      last_seen: new Date().toISOString(),
      health_score: 50,
      active_trades: 0,
      error_count: 0,
      ...currentStatus,
      ...updates
    };

    this.agentStatuses.set(agentId, newStatus);
    logger.debug(`Updated status for agent ${agentId}: ${newStatus.status}`);
  }

  /**
   * Add item to live data feed
   */
  private addToLiveDataFeed(item: LiveDataFeedItem): void {
    this.liveDataFeed.unshift(item);

    // Keep only the most recent items
    if (this.liveDataFeed.length > this.maxFeedItems) {
      this.liveDataFeed = this.liveDataFeed.slice(0, this.maxFeedItems);
    }
  }

  /**
   * Get agent type from agent ID
   */
  private getAgentTypeFromId(agentId: string): AgentStatus['agent_type'] {
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
   * Get current system health status
   */
  getSystemHealthStatus(): SystemHealthStatus {
    const agentStatuses = Array.from(this.agentStatuses.values());
    const onlineAgents = agentStatuses.filter(s => s.status === 'online').length;
    const offlineAgents = agentStatuses.filter(s => s.status === 'offline').length;
    const errorAgents = agentStatuses.filter(s => s.status === 'error').length;

    const averageHealth = agentStatuses.length > 0 ?
      agentStatuses.reduce((sum, s) => sum + s.health_score, 0) / agentStatuses.length : 0;

    return {
      overall_health: averageHealth,
      total_agents: agentStatuses.length,
      online_agents: onlineAgents,
      offline_agents: offlineAgents,
      error_agents: errorAgents,
      last_updated: new Date().toISOString(),
      agent_statuses: agentStatuses,
      system_load: this.getSystemLoad()
    };
  }

  /**
   * Get live data feed
   */
  getLiveDataFeed(limit?: number): LiveDataFeedItem[] {
    const feed = this.liveDataFeed.slice();
    return limit ? feed.slice(0, limit) : feed;
  }

  /**
   * Get agent status by ID
   */
  getAgentStatus(agentId: string): AgentStatus | undefined {
    return this.agentStatuses.get(agentId);
  }

  /**
   * Get all agent statuses
   */
  getAllAgentStatuses(): AgentStatus[] {
    return Array.from(this.agentStatuses.values());
  }

  /**
   * Get system load (simplified)
   */
  private getSystemLoad() {
    // In a real implementation, this would query actual system metrics
    return {
      cpu_percent: Math.random() * 100, // Placeholder
      memory_percent: Math.random() * 100, // Placeholder
      disk_usage_percent: Math.random() * 100 // Placeholder
    };
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }

    this.agentStatuses.clear();
    this.liveDataFeed.length = 0;
    this.initialized = false;

    logger.info('Agent Status Monitor cleaned up');
  }
}
