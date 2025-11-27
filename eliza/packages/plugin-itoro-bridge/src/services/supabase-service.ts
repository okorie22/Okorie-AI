// Removed Supabase client import - using direct REST API calls like working Python agents
import { logger } from '@elizaos/core';
import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

/**
 * Trading data types
 */
export interface PortfolioData {
  total_value: number;
  daily_pnl: number;
  positions: Position[];
  risk_level: string;
  timestamp: string;
}

export interface Position {
  symbol: string;
  side: string;
  size: number;
  avg_price: number;
  current_price: number;
  unrealized_pnl: number;
  timestamp: string;
}

export interface Trade {
  id: string;
  symbol: string;
  side: string;
  size: number;
  price: number;
  timestamp: string;
  pnl?: number;
}

export interface RiskMetrics {
  max_drawdown: number;
  sharpe_ratio: number;
  volatility: number;
  value_at_risk: number;
  timestamp: string;
}

export interface WhaleData {
  symbol: string;
  whale_address: string;
  amount: number;
  transaction_type: string;
  timestamp: string;
}

/**
 * Database connection types
 */
export type DatabaseType = 'supabase' | 'sqlite';

/**
 * Database configuration
 */
export interface DatabaseConfig {
  type: DatabaseType;
  url?: string;
  anonKey?: string;
  serviceRoleKey?: string;
  path?: string;
  isPaperTrading?: boolean;
}

/**
 * Supabase Database Access Service
 * Provides unified access to both Supabase cloud databases and local SQLite databases
 */
export class SupabaseDatabaseService {
  private supabaseClients: Map<string, SupabaseClient> = new Map();
  private sqliteConnections: Map<string, Database.Database> = new Map();
  private initialized = false;

  /**
   * Initialize database connections
   */
  async initialize(configs: Record<string, DatabaseConfig>): Promise<void> {
    if (this.initialized) {
      return;
    }

    let sqliteInitialized = false;
    let supabaseInitialized = false;

    logger.info('Initializing Database Service (SQLite + Supabase REST API)');

    // Always try SQLite first (reliable)
    for (const [name, config] of Object.entries(configs)) {
      if (config.type === 'sqlite') {
        try {
          await this.initializeSQLiteConnection(name, config);
          sqliteInitialized = true;
          logger.info(`✓ SQLite database ${name} initialized`);
        } catch (error) {
          logger.error(`✗ Failed to initialize SQLite ${name}:`, error);
        }
      }
    }

    // Try Supabase REST API but don't fail if it doesn't work (like working Python agents)
    for (const [name, config] of Object.entries(configs)) {
      if (config.type === 'supabase') {
        try {
          await this.initializeSupabaseClient(name, config);
          supabaseInitialized = true;
          logger.info(`✓ Supabase REST API ${name} initialized`);
        } catch (error) {
          logger.warn(`⚠ Supabase REST API ${name} not available, continuing with SQLite only:`, error.message);
        }
      }
    }

    // Mark as initialized if we have at least SQLite
    if (sqliteInitialized) {
      this.initialized = true;
      const sources = supabaseInitialized ? 'SQLite + Supabase REST API' : 'SQLite only';
      logger.info(`Database Service initialized successfully (${sources})`);
    } else {
      throw new Error('Failed to initialize any database connections');
    }
  }

  /**
   * Initialize Supabase REST API connection (like working Python agents)
   */
  private async initializeSupabaseClient(name: string, config: DatabaseConfig): Promise<void> {
    if (!config.url || !config.serviceRoleKey) {
      throw new Error(`Supabase configuration incomplete for ${name}`);
    }

    // Store REST API configuration instead of client
    const restConfig = {
      baseUrl: `${config.url}/rest/v1`,
      headers: {
        'Authorization': `Bearer ${config.serviceRoleKey}`,
        'apikey': config.serviceRoleKey,
        'Content-Type': 'application/json',
      }
    };

    // Test connection using direct REST API call (like working Python agents)
    try {
      const testUrl = `${restConfig.baseUrl}/paper_trading_portfolio?select=id&limit=1`;
      const response = await fetch(testUrl, {
        method: 'GET',
        headers: restConfig.headers,
        signal: AbortSignal.timeout(10000) // 10 second timeout like Python agents
      });

      if (!response.ok && !response.statusText.includes('relation "paper_trading_portfolio" does not exist')) {
        throw new Error(`Supabase REST API test failed: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'TimeoutError') {
        throw new Error(`Supabase connection timeout for ${name}`);
      }
      throw new Error(`Failed to connect to Supabase REST API for ${name}: ${error instanceof Error ? error.message : String(error)}`);
    }

    this.supabaseClients.set(name, restConfig as any);
    logger.info(`Supabase REST API initialized for ${name}`);
  }

  /**
   * Initialize SQLite connection
   */
  private async initializeSQLiteConnection(name: string, config: DatabaseConfig): Promise<void> {
    if (!config.path) {
      throw new Error(`SQLite path not provided for ${name}`);
    }

    const dbPath = path.resolve(config.path);
    if (!fs.existsSync(dbPath)) {
      logger.warn(`SQLite database file not found: ${dbPath}. Creating empty database file.`);
      // Create an empty file if it doesn't exist
      fs.writeFileSync(dbPath, '');
    }

    try {
      const connection = new Database(dbPath, { readonly: true });
      this.sqliteConnections.set(name, connection);
      logger.info(`SQLite connection initialized for ${name}`);
    } catch (error) {
      logger.warn(`Failed to initialize SQLite connection for ${name}: ${error.message}. Continuing without SQLite connection.`);
      // Create a mock connection object to prevent other code from failing
      this.sqliteConnections.set(name, {
        close: () => {},
        prepare: () => ({ all: () => [], run: () => {} }),
        exec: () => {}
      } as any);
    }
  }

  /**
   * Query portfolio data from specified database
   */
  async queryPortfolio(dbName: string, userId?: string): Promise<PortfolioData> {
    const dbType = this.getDatabaseType(dbName);

    if (dbType === 'supabase') {
      return this.queryPortfolioFromSupabase(dbName, userId);
    } else {
      return this.queryPortfolioFromSQLite(dbName);
    }
  }

  /**
   * Query portfolio from Supabase
   */
  private async queryPortfolioFromSupabase(dbName: string, userId?: string): Promise<PortfolioData> {
    const client = this.supabaseClients.get(dbName);
    if (!client) {
      throw new Error(`Supabase client not found: ${dbName}`);
    }

    // Query current portfolio from Supabase
    const { data: portfolioData, error } = await client
      .from('portfolio_current')
      .select('*')
      .eq('user_id', userId || 'default')
      .single();

    if (error) {
      logger.warn(`Portfolio query failed for ${dbName}, using fallback: ${error.message}`);
      return this.getEmptyPortfolio();
    }

    // Query positions
    const { data: positionsData } = await client
      .from('positions')
      .select('*')
      .eq('user_id', userId || 'default')
      .eq('is_active', true);

    const positions = positionsData?.map(pos => ({
      symbol: pos.symbol,
      side: pos.side,
      size: pos.size,
      avg_price: pos.avg_price,
      current_price: pos.current_price,
      unrealized_pnl: pos.unrealized_pnl,
      timestamp: pos.updated_at
    })) || [];

    return {
      total_value: portfolioData.total_value || 0,
      daily_pnl: portfolioData.daily_pnl || 0,
      positions,
      risk_level: portfolioData.risk_level || 'Normal',
      timestamp: portfolioData.updated_at
    };
  }

  /**
   * Query portfolio from SQLite (paper trading database)
   */
  private queryPortfolioFromSQLite(dbName: string): PortfolioData {
    const connection = this.sqliteConnections.get(dbName);
    if (!connection) {
      throw new Error(`SQLite connection not found: ${dbName}`);
    }

    try {
      // Query paper_portfolio table
      const portfolioStmt = connection.prepare(`
        SELECT total_value, daily_pnl, risk_level, updated_at
        FROM paper_portfolio
        ORDER BY updated_at DESC
        LIMIT 1
      `);

      const portfolioData = portfolioStmt.get() as any;

      // Query positions
      const positionsStmt = connection.prepare(`
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
      logger.warn(`SQLite portfolio query failed for ${dbName}: ${error}`);
      return this.getEmptyPortfolio();
    }
  }

  /**
   * Query trade history
   */
  async queryTradeHistory(dbName: string, limit = 50, userId?: string): Promise<Trade[]> {
    const dbType = this.getDatabaseType(dbName);

    if (dbType === 'supabase') {
      return this.queryTradeHistoryFromSupabase(dbName, limit, userId);
    } else {
      return this.queryTradeHistoryFromSQLite(dbName, limit);
    }
  }

  /**
   * Query trade history from Supabase
   */
  private async queryTradeHistoryFromSupabase(dbName: string, limit: number, userId?: string): Promise<Trade[]> {
    const client = this.supabaseClients.get(dbName);
    if (!client) {
      throw new Error(`Supabase client not found: ${dbName}`);
    }

    const { data, error } = await client
      .from('trades')
      .select('*')
      .eq('user_id', userId || 'default')
      .order('timestamp', { ascending: false })
      .limit(limit);

    if (error) {
      logger.warn(`Trade history query failed for ${dbName}: ${error.message}`);
      return [];
    }

    return data?.map(trade => ({
      id: trade.id,
      symbol: trade.symbol,
      side: trade.side,
      size: trade.size,
      price: trade.price,
      timestamp: trade.timestamp,
      pnl: trade.pnl
    })) || [];
  }

  /**
   * Query trade history from SQLite
   */
  private queryTradeHistoryFromSQLite(dbName: string, limit: number): Trade[] {
    const connection = this.sqliteConnections.get(dbName);
    if (!connection) {
      throw new Error(`SQLite connection not found: ${dbName}`);
    }

    try {
      const stmt = connection.prepare(`
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
      logger.warn(`SQLite trade history query failed for ${dbName}: ${error}`);
      return [];
    }
  }

  /**
   * Query risk metrics
   */
  async queryRiskMetrics(dbName: string, userId?: string): Promise<RiskMetrics> {
    const dbType = this.getDatabaseType(dbName);

    if (dbType === 'supabase') {
      return this.queryRiskMetricsFromSupabase(dbName, userId);
    } else {
      return this.queryRiskMetricsFromSQLite(dbName);
    }
  }

  /**
   * Query risk metrics from Supabase
   */
  private async queryRiskMetricsFromSupabase(dbName: string, userId?: string): Promise<RiskMetrics> {
    const client = this.supabaseClients.get(dbName);
    if (!client) {
      throw new Error(`Supabase client not found: ${dbName}`);
    }

    const { data, error } = await client
      .from('risk_metrics')
      .select('*')
      .eq('user_id', userId || 'default')
      .order('timestamp', { ascending: false })
      .limit(1)
      .single();

    if (error) {
      logger.warn(`Risk metrics query failed for ${dbName}: ${error.message}`);
      return this.getDefaultRiskMetrics();
    }

    return {
      max_drawdown: data.max_drawdown || 0,
      sharpe_ratio: data.sharpe_ratio || 0,
      volatility: data.volatility || 0,
      value_at_risk: data.value_at_risk || 0,
      timestamp: data.timestamp
    };
  }

  /**
   * Query risk metrics from SQLite
   */
  private queryRiskMetricsFromSQLite(dbName: string): RiskMetrics {
    const connection = this.sqliteConnections.get(dbName);
    if (!connection) {
      throw new Error(`SQLite connection not found: ${dbName}`);
    }

    try {
      const stmt = connection.prepare(`
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
      logger.warn(`SQLite risk metrics query failed for ${dbName}: ${error}`);
    }

    return this.getDefaultRiskMetrics();
  }

  /**
   * Query whale data
   */
  async queryWhaleData(dbName: string, limit = 20): Promise<WhaleData[]> {
    const dbType = this.getDatabaseType(dbName);

    if (dbType === 'supabase') {
      return this.queryWhaleDataFromSupabase(dbName, limit);
    } else {
      return this.queryWhaleDataFromSQLite(dbName, limit);
    }
  }

  /**
   * Query whale data from Supabase
   */
  private async queryWhaleDataFromSupabase(dbName: string, limit: number): Promise<WhaleData[]> {
    const client = this.supabaseClients.get(dbName);
    if (!client) {
      throw new Error(`Supabase client not found: ${dbName}`);
    }

    const { data, error } = await client
      .from('whale_movements')
      .select('*')
      .order('timestamp', { ascending: false })
      .limit(limit);

    if (error) {
      logger.warn(`Whale data query failed for ${dbName}: ${error.message}`);
      return [];
    }

    return data?.map(whale => ({
      symbol: whale.symbol,
      whale_address: whale.whale_address,
      amount: whale.amount,
      transaction_type: whale.transaction_type,
      timestamp: whale.timestamp
    })) || [];
  }

  /**
   * Query whale data from SQLite
   */
  private queryWhaleDataFromSQLite(dbName: string, limit: number): WhaleData[] {
    const connection = this.sqliteConnections.get(dbName);
    if (!connection) {
      throw new Error(`SQLite connection not found: ${dbName}`);
    }

    try {
      const stmt = connection.prepare(`
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
      logger.warn(`SQLite whale data query failed for ${dbName}: ${error}`);
      return [];
    }
  }

  /**
   * Get database type for a given name
   */
  private getDatabaseType(dbName: string): DatabaseType {
    if (this.supabaseClients.has(dbName)) {
      return 'supabase';
    } else if (this.sqliteConnections.has(dbName)) {
      return 'sqlite';
    } else {
      throw new Error(`Database not found: ${dbName}`);
    }
  }

  /**
   * Get empty portfolio data
   */
  private getEmptyPortfolio(): PortfolioData {
    return {
      total_value: 0,
      daily_pnl: 0,
      positions: [],
      risk_level: 'Normal',
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Get default risk metrics
   */
  private getDefaultRiskMetrics(): RiskMetrics {
    return {
      max_drawdown: 0,
      sharpe_ratio: 0,
      volatility: 0,
      value_at_risk: 0,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Close all database connections
   */
  async close(): Promise<void> {
    logger.info('Closing database connections');

    // Close SQLite connections
    for (const [name, connection] of this.sqliteConnections) {
      try {
        connection.close();
        logger.info(`SQLite connection closed: ${name}`);
      } catch (error) {
        logger.error(`Error closing SQLite connection ${name}:`, error);
      }
    }

    this.sqliteConnections.clear();
    this.supabaseClients.clear();
    this.initialized = false;
  }

  /**
   * Get available database names
   */
  getAvailableDatabases(): string[] {
    return [
      ...Array.from(this.supabaseClients.keys()),
      ...Array.from(this.sqliteConnections.keys())
    ];
  }
}
