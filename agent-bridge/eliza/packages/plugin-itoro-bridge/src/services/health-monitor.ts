import { logger } from '@elizaos/core';
import { WebhookClient } from '../communication/webhook-client';
import { AgentManager } from '../agent-manager';

/**
 * Health status interface
 */
export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  webhook: {
    connected: boolean;
    lastCheck: number;
    latency?: number;
  };
  agents: {
    active: number;
    max: number;
    spawnRate: number;
    despawnRate: number;
  };
  messages: {
    sent: number;
    received: number;
    failed: number;
    throughput: number; // messages per minute
  };
  timestamp: number;
}

/**
 * Health monitor for tracking system health
 */
export class HealthMonitor {
  private webhookClient: WebhookClient;
  private agentManager: AgentManager;
  private messageStats = {
    sent: 0,
    received: 0,
    failed: 0,
    startTime: Date.now(),
  };
  private healthCheckInterval?: NodeJS.Timeout;

  constructor(webhookClient: WebhookClient, agentManager: AgentManager) {
    this.webhookClient = webhookClient;
    this.agentManager = agentManager;
  }

  /**
   * Start health monitoring
   */
  start(intervalMs: number = 60000): void {
    if (this.healthCheckInterval) {
      return;
    }

    this.healthCheckInterval = setInterval(() => {
      this.checkHealth().catch((error) => {
        logger.error('Health check failed:', error);
      });
    }, intervalMs);

    logger.info('Health monitor started');
  }

  /**
   * Stop health monitoring
   */
  stop(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = undefined;
    }
    logger.info('Health monitor stopped');
  }

  /**
   * Check system health
   */
  async checkHealth(): Promise<HealthStatus> {
    const startTime = Date.now();
    let webhookConnected = false;
    let latency: number | undefined;

    try {
      // Check webhook connectivity with a simple health check
      // This would need to be implemented in the webhook client
      const checkStart = Date.now();
      // In a real implementation, this would make a health check request
      // For now, we'll assume connected if webhook client exists
      webhookConnected = !!this.webhookClient;
      latency = Date.now() - checkStart;
    } catch (error) {
      logger.warn('Webhook health check failed:', error);
      webhookConnected = false;
    }

    const activeAgents = this.agentManager.getActiveAgents();
    const maxAgents = parseInt(process.env.MAX_CONCURRENT_AGENTS || '5', 10);

    // Calculate message throughput
    const elapsedMinutes = (Date.now() - this.messageStats.startTime) / 60000;
    const throughput =
      elapsedMinutes > 0
        ? (this.messageStats.sent + this.messageStats.received) / elapsedMinutes
        : 0;

    // Determine overall status
    let status: 'healthy' | 'degraded' | 'unhealthy' = 'healthy';
    if (!webhookConnected || this.messageStats.failed > this.messageStats.sent * 0.1) {
      status = 'unhealthy';
    } else if (
      activeAgents.length >= maxAgents * 0.8 ||
      this.messageStats.failed > this.messageStats.sent * 0.05
    ) {
      status = 'degraded';
    }

    const healthStatus: HealthStatus = {
      status,
      webhook: {
        connected: webhookConnected,
        lastCheck: Date.now(),
        latency,
      },
      agents: {
        active: activeAgents.length,
        max: maxAgents,
        spawnRate: 0, // Would need to track spawn/despawn events
        despawnRate: 0,
      },
      messages: {
        sent: this.messageStats.sent,
        received: this.messageStats.received,
        failed: this.messageStats.failed,
        throughput: Math.round(throughput * 100) / 100,
      },
      timestamp: Date.now(),
    };

    return healthStatus;
  }

  /**
   * Record a sent message
   */
  recordSent(): void {
    this.messageStats.sent++;
  }

  /**
   * Record a received message
   */
  recordReceived(): void {
    this.messageStats.received++;
  }

  /**
   * Record a failed message
   */
  recordFailed(): void {
    this.messageStats.failed++;
  }

  /**
   * Get current health status
   */
  async getHealthStatus(): Promise<HealthStatus> {
    return await this.checkHealth();
  }
}

