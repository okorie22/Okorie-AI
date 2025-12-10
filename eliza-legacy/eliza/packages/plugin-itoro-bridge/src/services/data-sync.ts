import { logger } from '@elizaos/core';
import { WebhookClient } from '../communication/webhook-client';

/**
 * Data synchronization service for keeping data in sync between ElizaOS and ITORO
 */
export class DataSyncService {
  private webhookClient: WebhookClient;
  private syncInterval?: NodeJS.Timeout;
  private cache: Map<string, { data: any; timestamp: number }> = new Map();
  private cacheTTL = 60000; // 1 minute default TTL

  constructor(webhookClient: WebhookClient) {
    this.webhookClient = webhookClient;
  }

  /**
   * Start periodic data synchronization
   */
  start(intervalMs: number = 300000): void {
    // 5 minutes default interval
    if (this.syncInterval) {
      return;
    }

    this.syncInterval = setInterval(() => {
      this.syncData().catch((error) => {
        logger.error('Data sync failed:', error);
      });
    }, intervalMs);

    logger.info('Data sync service started');
  }

  /**
   * Stop data synchronization
   */
  stop(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = undefined;
    }
    this.cache.clear();
    logger.info('Data sync service stopped');
  }

  /**
   * Synchronize data from ITORO
   */
  async syncData(): Promise<void> {
    try {
      // Sync portfolio data
      await this.syncPortfolioData();

      // Sync market data
      await this.syncMarketData();

      logger.debug('Data synchronization completed');
    } catch (error) {
      logger.error('Data synchronization error:', error);
    }
  }

  /**
   * Sync portfolio data
   */
  private async syncPortfolioData(): Promise<void> {
    try {
      const response = await this.webhookClient.sendQuery('portfolio', 'sync_portfolio', {
        sync_type: 'portfolio',
      });

      // Cache the response
      this.cache.set('portfolio', {
        data: response,
        timestamp: Date.now(),
      });
    } catch (error) {
      logger.warn('Portfolio data sync failed:', error);
    }
  }

  /**
   * Sync market data
   */
  private async syncMarketData(): Promise<void> {
    try {
      const response = await this.webhookClient.sendQuery('market', 'sync_market_data', {
        sync_type: 'market',
      });

      // Cache the response
      this.cache.set('market', {
        data: response,
        timestamp: Date.now(),
      });
    } catch (error) {
      logger.warn('Market data sync failed:', error);
    }
  }

  /**
   * Get cached data
   */
  getCached(key: string): any | null {
    const cached = this.cache.get(key);
    if (!cached) {
      return null;
    }

    // Check if cache is still valid
    if (Date.now() - cached.timestamp > this.cacheTTL) {
      this.cache.delete(key);
      return null;
    }

    return cached.data;
  }

  /**
   * Set cache TTL
   */
  setCacheTTL(ttl: number): void {
    this.cacheTTL = ttl;
  }

  /**
   * Clear cache
   */
  clearCache(): void {
    this.cache.clear();
  }
}

