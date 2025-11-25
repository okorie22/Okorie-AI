import { logger } from '@elizaos/core';
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { SupabaseDatabaseService, PortfolioData, Trade } from './supabase-service';

/**
 * Crypto Agent Data Sync Service
 * Synchronizes data from crypto agents to ITORO bridge
 */
export class CryptoAgentSyncService {
  private dbService: SupabaseDatabaseService;
  private localDB: Database.Database | null = null;
  private syncInterval: NodeJS.Timeout | null = null;
  private isRunning = false;
  private lastSyncTime: Date = new Date();

  constructor(dbService: SupabaseDatabaseService) {
    this.dbService = dbService;
  }

  /**
   * Initialize the sync service
   */
  async initialize(paperTradingDBPath?: string): Promise<void> {
    if (paperTradingDBPath && fs.existsSync(paperTradingDBPath)) {
      this.localDB = new Database(paperTradingDBPath, { readonly: true });
      logger.info('Crypto agent sync service initialized with local database');
    } else {
      logger.warn('Crypto agent sync service initialized without local database');
    }
  }

  /**
   * Start periodic synchronization
   */
  startPeriodicSync(intervalMs: number = 30000): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }

    this.isRunning = true;
    this.syncInterval = setInterval(async () => {
      try {
        await this.performFullSync();
      } catch (error) {
        logger.error('Periodic sync failed:', error);
      }
    }, intervalMs);

    logger.info(`Started periodic sync every ${intervalMs}ms`);
  }

  /**
   * Stop periodic synchronization
   */
  stopPeriodicSync(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
    this.isRunning = false;
    logger.info('Stopped periodic sync');
  }

  /**
   * Perform full synchronization
   */
  async performFullSync(): Promise<void> {
    if (!this.isRunning) return;

    try {
      logger.info('Starting crypto agent data sync');

      await Promise.allSettled([
        this.syncPortfolio(),
        this.syncTradeHistory(),
        this.syncRiskMetrics(),
        this.syncWhaleData()
      ]);

      this.lastSyncTime = new Date();
      logger.info('Crypto agent data sync completed');
    } catch (error) {
      logger.error('Full sync failed:', error);
    }
  }

  /**
   * Sync portfolio data
   */
  async syncPortfolio(): Promise<void> {
    if (!this.localDB) {
      logger.warn('No local database available for portfolio sync');
      return;
    }

    try {
      const portfolioData = this.queryLocalPortfolio();

      // Here you would typically sync to Supabase or another central store
      // For now, we just log the data
      logger.info('Portfolio data synced:', {
        total_value: portfolioData.total_value,
        positions_count: portfolioData.positions.length,
        timestamp: portfolioData.timestamp
      });
    } catch (error) {
      logger.error('Portfolio sync failed:', error);
    }
  }

  /**
   * Sync trade history
   */
  async syncTradeHistory(): Promise<void> {
    if (!this.localDB) {
      logger.warn('No local database available for trade history sync');
      return;
    }

    try {
      const trades = this.queryLocalTradeHistory(50);

      // Here you would sync to Supabase
      logger.info(`Trade history synced: ${trades.length} trades`);
    } catch (error) {
      logger.error('Trade history sync failed:', error);
    }
  }

  /**
   * Sync risk metrics
   */
  async syncRiskMetrics(): Promise<void> {
    if (!this.localDB) {
      logger.warn('No local database available for risk metrics sync');
      return;
    }

    try {
      const riskMetrics = this.queryLocalRiskMetrics();

      // Here you would sync to Supabase
      logger.info('Risk metrics synced:', riskMetrics);
    } catch (error) {
      logger.error('Risk metrics sync failed:', error);
    }
  }

  /**
   * Sync whale data
   */
  async syncWhaleData(): Promise<void> {
    if (!this.localDB) {
      logger.warn('No local database available for whale data sync');
      return;
    }

    try {
      const whaleData = this.queryLocalWhaleData(20);

      // Here you would sync to Supabase
      logger.info(`Whale data synced: ${whaleData.length} movements`);
    } catch (error) {
      logger.error('Whale data sync failed:', error);
    }
  }

  /**
   * Query local portfolio data
   */
  private queryLocalPortfolio(): PortfolioData {
    if (!this.localDB) {
      throw new Error('Local database not available');
    }

    try {
      // Query paper_portfolio table
      const portfolioStmt = this.localDB.prepare(`
        SELECT total_value, daily_pnl, risk_level, updated_at
        FROM paper_portfolio
        ORDER BY updated_at DESC
        LIMIT 1
      `);

      const portfolioData = portfolioStmt.get() as any;

      // Query positions
      const positionsStmt = this.localDB.prepare(`
        SELECT symbol, side, size, avg_price, current_price, unrealized_pnl, updated_at
        FROM paper_positions
        WHERE is_active = 1
      `);

      const positionsData = positionsStmt.all() as any[];
      const positions = positionsData.map(pos => ({
        symbol: pos.symbol,
        side: pos.side,
        size: pos.size,
        avg_price: pos.avg_price,
        current_price: pos.current_price,
        unrealized_pnl: pos.unrealized_pnl,
        timestamp: pos.updated_at
      }));

      return {
        total_value: portfolioData?.total_value || 0,
        daily_pnl: portfolioData?.daily_pnl || 0,
        positions,
        risk_level: portfolioData?.risk_level || 'Normal',
        timestamp: portfolioData?.updated_at || new Date().toISOString()
      };
    } catch (error) {
      logger.warn('Local portfolio query failed:', error);
      return {
        total_value: 0,
        daily_pnl: 0,
        positions: [],
        risk_level: 'Normal',
        timestamp: new Date().toISOString()
      };
    }
  }

  /**
   * Query local trade history
   */
  private queryLocalTradeHistory(limit: number): Trade[] {
    if (!this.localDB) {
      throw new Error('Local database not available');
    }

    try {
      const stmt = this.localDB.prepare(`
        SELECT id, symbol, side, size, price, timestamp, pnl
        FROM paper_trades
        ORDER BY timestamp DESC
        LIMIT ?
      `);

      const data = stmt.all(limit) as any[];
      return data.map(trade => ({
        id: trade.id.toString(),
        symbol: trade.symbol,
        side: trade.side,
        size: trade.size,
        price: trade.price,
        timestamp: trade.timestamp,
        pnl: trade.pnl
      }));
    } catch (error) {
      logger.warn('Local trade history query failed:', error);
      return [];
    }
  }

  /**
   * Query local risk metrics
   */
  private queryLocalRiskMetrics(): any {
    if (!this.localDB) {
      throw new Error('Local database not available');
    }

    try {
      const stmt = this.localDB.prepare(`
        SELECT max_drawdown, sharpe_ratio, volatility, value_at_risk, timestamp
        FROM risk_metrics
        ORDER BY timestamp DESC
        LIMIT 1
      `);

      const data = stmt.get() as any;
      if (data) {
        return {
          max_drawdown: data.max_drawdown || 0,
          sharpe_ratio: data.sharpe_ratio || 0,
          volatility: data.volatility || 0,
          value_at_risk: data.value_at_risk || 0,
          timestamp: data.timestamp
        };
      }
    } catch (error) {
      logger.warn('Local risk metrics query failed:', error);
    }

    return {
      max_drawdown: 0,
      sharpe_ratio: 0,
      volatility: 0,
      value_at_risk: 0,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Query local whale data
   */
  private queryLocalWhaleData(limit: number): any[] {
    if (!this.localDB) {
      throw new Error('Local database not available');
    }

    try {
      const stmt = this.localDB.prepare(`
        SELECT symbol, whale_address, amount, transaction_type, timestamp
        FROM whale_movements
        ORDER BY timestamp DESC
        LIMIT ?
      `);

      const data = stmt.all(limit) as any[];
      return data.map(whale => ({
        symbol: whale.symbol,
        whale_address: whale.whale_address,
        amount: whale.amount,
        transaction_type: whale.transaction_type,
        timestamp: whale.timestamp
      }));
    } catch (error) {
      logger.warn('Local whale data query failed:', error);
      return [];
    }
  }

  /**
   * Get sync status
   */
  getSyncStatus(): {
    isRunning: boolean;
    lastSyncTime: Date;
    hasLocalDB: boolean;
  } {
    return {
      isRunning: this.isRunning,
      lastSyncTime: this.lastSyncTime,
      hasLocalDB: this.localDB !== null
    };
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    this.stopPeriodicSync();

    if (this.localDB) {
      this.localDB.close();
      this.localDB = null;
    }

    logger.info('Crypto agent sync service cleaned up');
  }
}
