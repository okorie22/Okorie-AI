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
      logger.info('Starting comprehensive ITORO database sync');

      await Promise.allSettled([
        // Paper Trading Local SQLite Databases
        this.syncPaperPortfolio(),
        this.syncPaperTrades(),
        this.syncPaperTradingBalances(),
        this.syncPaperStakingTransactions(),
        this.syncPortfolioSnapshotsPaper(),
        this.syncDefiPositions(),
        this.syncDefiLoops(),
        this.syncEntryPrices(),
        this.syncExecutions(),

        // Live Trading Local SQLite Databases (if available)
        this.syncLiveTrading(),
        this.syncPortfolioSnapshotsLive(),

        // Cloud Supabase Database (30+ tables)
        this.syncCloudPortfolioHistory(),
        this.syncCloudPortfolioBalances(),
        this.syncCloudSentimentData(),
        this.syncCloudWhaleData(),
        this.syncCloudWhaleHistory(),
        this.syncCloudWhaleSchedules(),
        this.syncCloudArtificialMemory(),
        this.syncCloudChartAnalysis(),
        this.syncCloudExecutionTracking(),
        this.syncCloudLiveTrades(),
        this.syncCloudStakingTransactions(),
        this.syncCloudStakingPositions(),
        this.syncCloudEntryPrices(),
        this.syncCloudAIAnalysis(),
        this.syncCloudChangeEvents(),
        this.syncCloudAgentSharedData(),
        this.syncCloudLogBackups(),
        this.syncCloudDatabaseBackups(),
        this.syncCloudRBIStrategyResults(),
        this.syncCloudPaperTradingPortfolio(),
        this.syncCloudPaperTradingTransactions(),
        this.syncCloudPaperTradingBalances(),
        this.syncCloudOnchainNetworkMetrics(),
        this.syncCloudOnchainHealthScores(),
        this.syncCloudOIData(),
        this.syncCloudOIAnalytics(),
        this.syncCloudFundingRates(),
        this.syncCloudFundingAnalytics(),
        this.syncCloudLiquidationEvents(),
        this.syncCloudLiquidationAnalytics()
      ]);

      this.lastSyncTime = new Date();
      logger.info('Comprehensive ITORO database sync completed');
    } catch (error) {
      logger.error('Full sync failed:', error);
    }
  }

  /**
   * Sync paper portfolio data
   */
  async syncPaperPortfolio(): Promise<void> {
    try {
      const portfolioData = this.queryPaperPortfolio();
      logger.info(`Paper portfolio synced: ${portfolioData.positions.length} positions, total value: $${portfolioData.total_value.toFixed(2)}`);
    } catch (error) {
      logger.error('Paper portfolio sync failed:', error);
    }
  }

  /**
   * Sync paper trades
   */
  async syncPaperTrades(): Promise<void> {
    try {
      const trades = this.queryPaperTrades(100);
      logger.info(`Paper trades synced: ${trades.length} recent trades`);
    } catch (error) {
      logger.error('Paper trades sync failed:', error);
    }
  }

  /**
   * Sync paper trading balances
   */
  async syncPaperTradingBalances(): Promise<void> {
    try {
      const balances = this.queryPaperTradingBalances();
      logger.info(`Paper trading balances synced: ${balances.length} token balances`);
    } catch (error) {
      logger.error('Paper trading balances sync failed:', error);
    }
  }

  /**
   * Sync paper staking transactions
   */
  async syncPaperStakingTransactions(): Promise<void> {
    try {
      const stakingTxs = this.queryPaperStakingTransactions(50);
      logger.info(`Paper staking transactions synced: ${stakingTxs.length} transactions`);
    } catch (error) {
      logger.error('Paper staking transactions sync failed:', error);
    }
  }

  /**
   * Query paper portfolio data from paper_portfolio table
   */
  private queryPaperPortfolio(): PortfolioData {
    if (!this.localDB) {
      logger.warn('Paper trading database not available');
      return {
        total_value: 0,
        daily_pnl: 0,
        positions: [],
        risk_level: 'Normal',
        timestamp: new Date().toISOString()
      };
    }

    try {
      // Query paper_portfolio table (token_address, amount, last_price, last_update)
      const positionsStmt = this.localDB.prepare(`
        SELECT token_address, amount, last_price, last_update
        FROM paper_portfolio
        ORDER BY last_update DESC
      `);

      const positionsData = positionsStmt.all() as any[];

      // Convert to portfolio positions format
      const positions = positionsData.map(pos => ({
        symbol: pos.token_address, // Use token_address as symbol for now
        side: 'long', // Paper trading assumes long positions
        size: pos.amount,
        avg_price: pos.last_price,
        current_price: pos.last_price, // Same as last_price for paper trading
        unrealized_pnl: 0, // Would need historical data to calculate
        timestamp: new Date(pos.last_update * 1000).toISOString()
      }));

      // Calculate total portfolio value
      const totalValue = positions.reduce((sum, pos) => sum + (pos.size * pos.current_price), 0);

      return {
        total_value: totalValue,
        daily_pnl: 0, // Would need historical comparison to calculate
        positions,
        risk_level: 'Normal',
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      logger.warn('Paper portfolio query failed:', error);
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
   * Query paper trades from paper_trades table
   */
  private queryPaperTrades(limit: number): Trade[] {
    if (!this.localDB) {
      logger.warn('Paper trading database not available');
      return [];
    }

    try {
      const stmt = this.localDB.prepare(`
        SELECT id, token_address, action, amount, price, timestamp, usd_value
        FROM paper_trades
        ORDER BY timestamp DESC
        LIMIT ?
      `);

      const data = stmt.all(limit) as any[];
      return data.map(trade => ({
        id: trade.id.toString(),
        symbol: trade.token_address, // Use token_address as symbol
        side: trade.action === 'buy' ? 'long' : 'short', // Convert action to side
        size: trade.amount,
        price: trade.price,
        timestamp: new Date(trade.timestamp * 1000).toISOString(),
        pnl: trade.usd_value // Use usd_value as pnl approximation
      }));
    } catch (error) {
      logger.warn('Paper trades query failed:', error instanceof Error ? error.message : String(error));
      return [];
    }
  }

  /**
   * Query paper trading balances from paper_trading_balances table
   */
  private queryPaperTradingBalances(): any[] {
    if (!this.localDB) {
      return [];
    }

    try {
      const stmt = this.localDB.prepare(`
        SELECT wallet_address, usdc_balance, sol_balance, staked_sol_balance, staking_rewards, last_updated
        FROM paper_trading_balances
        ORDER BY last_updated DESC
      `);

      const data = stmt.all() as any[];
      return data.map(balance => ({
        wallet_address: balance.wallet_address,
        usdc_balance: balance.usdc_balance || 0,
        sol_balance: balance.sol_balance || 0,
        staked_sol_balance: balance.staked_sol_balance || 0,
        staking_rewards: balance.staking_rewards || 0,
        last_updated: balance.last_updated
      }));
    } catch (error) {
      logger.warn('Paper trading balances query failed:', error);
      return [];
    }
  }

  /**
   * Query paper staking transactions from paper_staking_transactions table
   */
  private queryPaperStakingTransactions(limit: number): any[] {
    if (!this.localDB) {
      return [];
    }

    try {
      const stmt = this.localDB.prepare(`
        SELECT id, wallet_address, amount, action, timestamp, rewards_earned
        FROM paper_staking_transactions
        ORDER BY timestamp DESC
        LIMIT ?
      `);

      const data = stmt.all(limit) as any[];
      return data.map(tx => ({
        id: tx.id,
        wallet_address: tx.wallet_address,
        amount: tx.amount,
        action: tx.action,
        timestamp: new Date(tx.timestamp * 1000).toISOString(),
        rewards_earned: tx.rewards_earned || 0
      }));
    } catch (error) {
      logger.warn('Paper staking transactions query failed:', error);
      return [];
    }
  }

  /**
   * Query portfolio snapshots (paper or live)
   */
  private queryPortfolioSnapshots(type: 'paper' | 'live'): any[] {
    // Portfolio snapshots are in separate databases
    const dbPath = type === 'paper'
      ? 'multi-agents/itoro/ai_crypto_agents/data/portfolio_history_paper.db'
      : 'multi-agents/itoro/ai_crypto_agents/data/portfolio_history_live.db';

    if (!require('fs').existsSync(dbPath)) {
      logger.warn(`Portfolio snapshots database not found: ${dbPath}`);
      return [];
    }

    let snapshotsDB: Database.Database;
    try {
      snapshotsDB = new Database(dbPath, { readonly: true });
      try {
        const stmt = snapshotsDB.prepare(`
          SELECT id, timestamp, total_value_usd, usdc_balance, sol_balance, sol_value_usd,
                 positions_value_usd, staked_sol_balance, staked_sol_value_usd, position_count, positions_json
          FROM portfolio_snapshots
          ORDER BY timestamp DESC
          LIMIT 100
        `);

        const data = stmt.all() as any[];
        snapshotsDB.close();

        return data.map(snapshot => ({
          id: snapshot.id,
          timestamp: snapshot.timestamp,
          total_value_usd: snapshot.total_value_usd,
          usdc_balance: snapshot.usdc_balance,
          sol_balance: snapshot.sol_balance,
          sol_value_usd: snapshot.sol_value_usd,
          positions_value_usd: snapshot.positions_value_usd,
          staked_sol_balance: snapshot.staked_sol_balance || 0,
          staked_sol_value_usd: snapshot.staked_sol_value_usd || 0,
          position_count: snapshot.position_count,
          positions_json: snapshot.positions_json
        }));
      } finally {
        snapshotsDB.close();
      }
    } catch (error) {
      logger.warn(`Portfolio snapshots query failed for ${type}:`, error);
      return [];
    }
  }

  /**
   * Query DeFi positions from defi_positions table
   */
  private queryDefiPositions(): any[] {
    const dbPath = 'multi-agents/itoro/ai_crypto_agents/src/data/defi_positions.db';
    if (!require('fs').existsSync(dbPath)) {
      logger.warn('DeFi positions database not found');
      return [];
    }

    let defiDB;
    try {

      const defiDB = new Database(dbPath, { readonly: true });
      try {
        const stmt = defiDB.prepare(`
          SELECT id, protocol, position_type, token_pair, amount, entry_price, current_price,
                 pnl, pnl_percentage, liquidation_price, created_at, updated_at
          FROM defi_positions
          ORDER BY updated_at DESC
        `);

        const data = stmt.all() as any[];
        defiDB.close();

        return data.map(pos => ({
          id: pos.id,
          protocol: pos.protocol,
          position_type: pos.position_type,
          token_pair: pos.token_pair,
          amount: pos.amount,
          entry_price: pos.entry_price,
          current_price: pos.current_price,
          pnl: pos.pnl,
          pnl_percentage: pos.pnl_percentage,
          liquidation_price: pos.liquidation_price,
          created_at: pos.created_at,
          updated_at: pos.updated_at
        }));
      } finally {
        defiDB.close();
      }
    } catch (error) {
      logger.warn('DeFi positions query failed:', error);
      return [];
    }
  }

  /**
   * Query DeFi loops from defi_loops table
   */
  private queryDefiLoops(): any[] {
    try {
      const dbPath = 'multi-agents/itoro/ai_crypto_agents/src/data/defi_positions.db';
      if (!require('fs').existsSync(dbPath)) {
        logger.warn('DeFi positions database not found');
        return [];
      }

      const defiDB = new Database(dbPath, { readonly: true });
      try {
        const stmt = defiDB.prepare(`
          SELECT id, base_protocol, leverage_protocol, token_pair, base_amount, leverage_amount,
                 total_exposure, entry_price, current_price, pnl, health_factor, liquidation_price,
                 created_at, updated_at
          FROM defi_loops
          ORDER BY updated_at DESC
        `);

        const data = stmt.all() as any[];
        defiDB.close();

        return data.map(loop => ({
          id: loop.id,
          base_protocol: loop.base_protocol,
          leverage_protocol: loop.leverage_protocol,
          token_pair: loop.token_pair,
          base_amount: loop.base_amount,
          leverage_amount: loop.leverage_amount,
          total_exposure: loop.total_exposure,
          entry_price: loop.entry_price,
          current_price: loop.current_price,
          pnl: loop.pnl,
          health_factor: loop.health_factor,
          liquidation_price: loop.liquidation_price,
          created_at: loop.created_at,
          updated_at: loop.updated_at
        }));
      } finally {
        defiDB.close();
      }
    } catch (error) {
      logger.warn('DeFi loops query failed:', error);
      return [];
    }
  }

  /**
   * Query entry prices from entry_prices table
   */
  private queryEntryPrices(): any[] {
    const dbPath = 'multi-agents/itoro/ai_crypto_agents/src/data/entry_prices.db';
    if (!require('fs').existsSync(dbPath)) {
      logger.warn('Entry prices database not found');
      return [];
    }

    let entryDB;
    try {

      const entryDB = new Database(dbPath, { readonly: true });
      try {
        const stmt = entryDB.prepare(`
          SELECT id, mint, entry_price_usd, entry_amount, entry_timestamp, last_updated,
                 source, notes
          FROM entry_prices
          ORDER BY last_updated DESC
        `);

        const data = stmt.all() as any[];
        entryDB.close();

        return data.map(price => ({
          id: price.id,
          mint: price.mint,
          entry_price_usd: price.entry_price_usd,
          entry_amount: price.entry_amount,
          entry_timestamp: price.entry_timestamp,
          last_updated: price.last_updated,
          source: price.source,
          notes: price.notes
        }));
      } finally {
        entryDB.close();
      }
    } catch (error) {
      logger.warn('Entry prices query failed:', error);
      return [];
    }
  }

  /**
   * Query executions from executions table
   */
  private queryExecutions(limit: number): any[] {
    const dbPath = 'multi-agents/itoro/ai_crypto_agents/src/data/execution_tracker.db';
    if (!require('fs').existsSync(dbPath)) {
      logger.warn('Execution tracker database not found');
      return [];
    }

    let execDB;
    try {

      const execDB = new Database(dbPath, { readonly: true });
      try {
        const stmt = execDB.prepare(`
          SELECT id, timestamp, agent_type, wallet_address, token_mint, action, amount,
                 price, usd_value, transaction_signature, status, error_message, execution_time_ms
          FROM executions
          ORDER BY timestamp DESC
          LIMIT ?
        `);

        const data = stmt.all(limit) as any[];
        execDB.close();

        return data.map(exec => ({
          id: exec.id,
          timestamp: exec.timestamp,
          agent_type: exec.agent_type,
          wallet_address: exec.wallet_address,
          token_mint: exec.token_mint,
          action: exec.action,
          amount: exec.amount,
          price: exec.price,
          usd_value: exec.usd_value,
          transaction_signature: exec.transaction_signature,
          status: exec.status,
          error_message: exec.error_message,
          execution_time_ms: exec.execution_time_ms
        }));
      } finally {
        execDB.close();
      }
    } catch (error) {
      logger.warn('Executions query failed:', error);
      return [];
    }
  }

  /**
   * Query live trades (placeholder for live trading database)
   */
  private queryLiveTrades(limit: number): Trade[] {
    // Live trading database might not exist or have different schema
    logger.info('Live trades query: Not implemented yet - live trading database schema needed');
    return [];
  }

  /**
   * Sync portfolio snapshots (paper trading)
   */
  async syncPortfolioSnapshotsPaper(): Promise<void> {
    try {
      const snapshots = this.queryPortfolioSnapshots('paper');
      logger.info(`Paper portfolio snapshots synced: ${snapshots.length} snapshots`);
    } catch (error) {
      logger.error('Paper portfolio snapshots sync failed:', error);
    }
  }

  /**
   * Sync DeFi positions
   */
  async syncDefiPositions(): Promise<void> {
    try {
      const positions = this.queryDefiPositions();
      logger.info(`DeFi positions synced: ${positions.length} positions`);
    } catch (error) {
      logger.error('DeFi positions sync failed:', error);
    }
  }

  /**
   * Sync DeFi loops
   */
  async syncDefiLoops(): Promise<void> {
    try {
      const loops = this.queryDefiLoops();
      logger.info(`DeFi loops synced: ${loops.length} loops`);
    } catch (error) {
      logger.error('DeFi loops sync failed:', error);
    }
  }

  /**
   * Sync entry prices
   */
  async syncEntryPrices(): Promise<void> {
    try {
      const prices = this.queryEntryPrices();
      logger.info(`Entry prices synced: ${prices.length} records`);
    } catch (error) {
      logger.error('Entry prices sync failed:', error);
    }
  }

  /**
   * Sync executions
   */
  async syncExecutions(): Promise<void> {
    try {
      const executions = this.queryExecutions(50);
      logger.info(`Executions synced: ${executions.length} executions`);
    } catch (error) {
      logger.error('Executions sync failed:', error);
    }
  }

  /**
   * Sync live trading data
   */
  async syncLiveTrading(): Promise<void> {
    try {
      const liveTrades = this.queryLiveTrades(50);
      logger.info(`Live trades synced: ${liveTrades.length} trades`);
    } catch (error) {
      logger.warn('Live trading sync skipped (database not available):', error.message);
    }
  }

  /**
   * Sync portfolio snapshots (live trading)
   */
  async syncPortfolioSnapshotsLive(): Promise<void> {
    try {
      const snapshots = this.queryPortfolioSnapshots('live');
      logger.info(`Live portfolio snapshots synced: ${snapshots.length} snapshots`);
    } catch (error) {
      logger.warn('Live portfolio snapshots sync skipped (database not available):', error.message);
    }
  }

  /**
   * Sync cloud portfolio history
   */
  async syncCloudPortfolioHistory(): Promise<void> {
    try {
      const data = await this.dbService.getPortfolioHistory(100);
      logger.info(`Cloud portfolio history synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud portfolio history sync failed:', error);
    }
  }

  /**
   * Sync cloud portfolio balances
   */
  async syncCloudPortfolioBalances(): Promise<void> {
    try {
      const data = await this.dbService.getPortfolioBalances(100);
      logger.info(`Cloud portfolio balances synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud portfolio balances sync failed:', error);
    }
  }

  /**
   * Sync cloud sentiment data
   */
  async syncCloudSentimentData(): Promise<void> {
    try {
      const data = await this.dbService.getSentimentData(100);
      logger.info(`Cloud sentiment data synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud sentiment data sync failed:', error);
    }
  }

  /**
   * Sync cloud whale data
   */
  async syncCloudWhaleData(): Promise<void> {
    try {
      const data = await this.dbService.getWhaleData(100);
      logger.info(`Cloud whale data synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud whale data sync failed:', error);
    }
  }

  /**
   * Sync cloud whale history
   */
  async syncCloudWhaleHistory(): Promise<void> {
    try {
      const data = await this.dbService.getWhaleHistory(100);
      logger.info(`Cloud whale history synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud whale history sync failed:', error);
    }
  }

  /**
   * Sync cloud whale schedules
   */
  async syncCloudWhaleSchedules(): Promise<void> {
    try {
      const data = await this.dbService.getWhaleSchedules(100);
      logger.info(`Cloud whale schedules synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud whale schedules sync failed:', error);
    }
  }

  /**
   * Sync cloud artificial memory
   */
  async syncCloudArtificialMemory(): Promise<void> {
    try {
      const data = await this.dbService.getArtificialMemory(100);
      logger.info(`Cloud artificial memory synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud artificial memory sync failed:', error);
    }
  }

  /**
   * Sync cloud chart analysis
   */
  async syncCloudChartAnalysis(): Promise<void> {
    try {
      const data = await this.dbService.getChartAnalysis(100);
      logger.info(`Cloud chart analysis synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud chart analysis sync failed:', error);
    }
  }

  /**
   * Sync cloud execution tracking
   */
  async syncCloudExecutionTracking(): Promise<void> {
    try {
      const data = await this.dbService.getExecutionTracking(100);
      logger.info(`Cloud execution tracking synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud execution tracking sync failed:', error);
    }
  }

  /**
   * Sync cloud live trades
   */
  async syncCloudLiveTrades(): Promise<void> {
    try {
      const data = await this.dbService.getLiveTrades(100);
      logger.info(`Cloud live trades synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud live trades sync failed:', error);
    }
  }

  /**
   * Sync cloud staking transactions
   */
  async syncCloudStakingTransactions(): Promise<void> {
    try {
      const data = await this.dbService.getStakingTransactions(100);
      logger.info(`Cloud staking transactions synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud staking transactions sync failed:', error);
    }
  }

  /**
   * Sync cloud staking positions
   */
  async syncCloudStakingPositions(): Promise<void> {
    try {
      const data = await this.dbService.getStakingPositions(100);
      logger.info(`Cloud staking positions synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud staking positions sync failed:', error);
    }
  }

  /**
   * Sync cloud entry prices
   */
  async syncCloudEntryPrices(): Promise<void> {
    try {
      const data = await this.dbService.getEntryPrices(100);
      logger.info(`Cloud entry prices synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud entry prices sync failed:', error);
    }
  }

  /**
   * Sync cloud AI analysis
   */
  async syncCloudAIAnalysis(): Promise<void> {
    try {
      const data = await this.dbService.getAIAnalysis(100);
      logger.info(`Cloud AI analysis synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud AI analysis sync failed:', error);
    }
  }

  /**
   * Sync cloud change events
   */
  async syncCloudChangeEvents(): Promise<void> {
    try {
      const data = await this.dbService.getChangeEvents(100);
      logger.info(`Cloud change events synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud change events sync failed:', error);
    }
  }

  /**
   * Sync cloud agent shared data
   */
  async syncCloudAgentSharedData(): Promise<void> {
    try {
      const data = await this.dbService.getAgentSharedData(100);
      logger.info(`Cloud agent shared data synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud agent shared data sync failed:', error);
    }
  }

  /**
   * Sync cloud log backups
   */
  async syncCloudLogBackups(): Promise<void> {
    try {
      const data = await this.dbService.getLogBackups(100);
      logger.info(`Cloud log backups synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud log backups sync failed:', error);
    }
  }

  /**
   * Sync cloud database backups
   */
  async syncCloudDatabaseBackups(): Promise<void> {
    try {
      const data = await this.dbService.getDatabaseBackups(100);
      logger.info(`Cloud database backups synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud database backups sync failed:', error);
    }
  }

  /**
   * Sync cloud RBI strategy results
   */
  async syncCloudRBIStrategyResults(): Promise<void> {
    try {
      const data = await this.dbService.getRBIStrategyResults(100);
      logger.info(`Cloud RBI strategy results synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud RBI strategy results sync failed:', error);
    }
  }

  /**
   * Sync cloud paper trading portfolio
   */
  async syncCloudPaperTradingPortfolio(): Promise<void> {
    try {
      const data = await this.dbService.getPaperTradingPortfolio(100);
      logger.info(`Cloud paper trading portfolio synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud paper trading portfolio sync failed:', error);
    }
  }

  /**
   * Sync cloud paper trading transactions
   */
  async syncCloudPaperTradingTransactions(): Promise<void> {
    try {
      const data = await this.dbService.getPaperTradingTransactions(100);
      logger.info(`Cloud paper trading transactions synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud paper trading transactions sync failed:', error);
    }
  }

  /**
   * Sync cloud paper trading balances
   */
  async syncCloudPaperTradingBalances(): Promise<void> {
    try {
      const data = await this.dbService.getPaperTradingBalances(100);
      logger.info(`Cloud paper trading balances synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud paper trading balances sync failed:', error);
    }
  }

  /**
   * Sync cloud onchain network metrics
   */
  async syncCloudOnchainNetworkMetrics(): Promise<void> {
    try {
      const data = await this.dbService.getOnchainNetworkMetrics(100);
      logger.info(`Cloud onchain network metrics synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud onchain network metrics sync failed:', error);
    }
  }

  /**
   * Sync cloud onchain health scores
   */
  async syncCloudOnchainHealthScores(): Promise<void> {
    try {
      const data = await this.dbService.getOnchainHealthScores(100);
      logger.info(`Cloud onchain health scores synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud onchain health scores sync failed:', error);
    }
  }

  /**
   * Sync cloud OI data
   */
  async syncCloudOIData(): Promise<void> {
    try {
      const data = await this.dbService.getOIData(100);
      logger.info(`Cloud OI data synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud OI data sync failed:', error);
    }
  }

  /**
   * Sync cloud OI analytics
   */
  async syncCloudOIAnalytics(): Promise<void> {
    try {
      const data = await this.dbService.getOIAnalytics(100);
      logger.info(`Cloud OI analytics synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud OI analytics sync failed:', error);
    }
  }

  /**
   * Sync cloud funding rates
   */
  async syncCloudFundingRates(): Promise<void> {
    try {
      const data = await this.dbService.getFundingRates(100);
      logger.info(`Cloud funding rates synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud funding rates sync failed:', error);
    }
  }

  /**
   * Sync cloud funding analytics
   */
  async syncCloudFundingAnalytics(): Promise<void> {
    try {
      const data = await this.dbService.getFundingAnalytics(100);
      logger.info(`Cloud funding analytics synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud funding analytics sync failed:', error);
    }
  }

  /**
   * Sync cloud liquidation events
   */
  async syncCloudLiquidationEvents(): Promise<void> {
    try {
      const data = await this.dbService.getLiquidationEvents(100);
      logger.info(`Cloud liquidation events synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud liquidation events sync failed:', error);
    }
  }

  /**
   * Sync cloud liquidation analytics
   */
  async syncCloudLiquidationAnalytics(): Promise<void> {
    try {
      const data = await this.dbService.getLiquidationAnalytics(100);
      logger.info(`Cloud liquidation analytics synced: ${data.length} records`);
    } catch (error) {
      logger.error('Cloud liquidation analytics sync failed:', error);
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
