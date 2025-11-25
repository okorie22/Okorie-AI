import { logger } from '@elizaos/core';
import { SupabaseDatabaseService, PortfolioData, Trade, RiskMetrics, WhaleData } from './supabase-service';

/**
 * Unified Portfolio Data
 */
export interface UnifiedPortfolioData {
  total_value: number;
  daily_pnl: number;
  total_pnl: number;
  positions: UnifiedPosition[];
  risk_level: string;
  last_updated: string;
  sources: string[];
}

/**
 * Unified Position
 */
export interface UnifiedPosition {
  symbol: string;
  side: string;
  size: number;
  avg_price: number;
  current_price: number;
  unrealized_pnl: number;
  market_type: 'crypto' | 'stock' | 'forex';
  source: string;
  timestamp: string;
}

/**
 * Unified Performance Metrics
 */
export interface UnifiedPerformanceMetrics {
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  volatility: number;
  win_rate: number;
  profit_factor: number;
  calmar_ratio: number;
  timestamp: string;
  sources: string[];
}

/**
 * Unified Risk Metrics
 */
export interface UnifiedRiskMetrics {
  max_drawdown: number;
  sharpe_ratio: number;
  volatility: number;
  value_at_risk: number;
  expected_shortfall: number;
  beta: number;
  correlation_matrix: Record<string, Record<string, number>>;
  timestamp: string;
  sources: string[];
}

/**
 * Market Exposure
 */
export interface MarketExposure {
  crypto: number;
  stocks: number;
  forex: number;
  total: number;
  diversification_ratio: number;
}

/**
 * Unified Data Aggregator
 * Combines data from all trading agent types into unified formats
 */
export class UnifiedDataAggregator {
  private dbService: SupabaseDatabaseService;
  private initialized = false;

  constructor(dbService: SupabaseDatabaseService) {
    this.dbService = dbService;
  }

  /**
   * Initialize the aggregator
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;
    this.initialized = true;
    logger.info('Unified Data Aggregator initialized');
  }

  /**
   * Get unified portfolio across all markets
   */
  async getUnifiedPortfolio(userId?: string): Promise<UnifiedPortfolioData> {
    const availableDBs = this.dbService.getAvailableDatabases();

    // Separate paper and live databases
    const paperDBs = availableDBs.filter(db => db.includes('paper'));
    const liveDBs = availableDBs.filter(db => db.includes('live'));

    // Get data from all available databases
    const allPortfolios = await Promise.allSettled([
      ...paperDBs.map(db => this.dbService.queryPortfolio(db, userId)),
      ...liveDBs.map(db => this.dbService.queryPortfolio(db, userId))
    ]);

    return this.aggregatePortfolios(allPortfolios, availableDBs);
  }

  /**
   * Aggregate multiple portfolio data sources
   */
  private aggregatePortfolios(
    portfolioResults: PromiseSettledResult<PortfolioData>[],
    sources: string[]
  ): UnifiedPortfolioData {
    let totalValue = 0;
    let totalDailyPnl = 0;
    let totalPnl = 0;
    const allPositions: UnifiedPosition[] = [];
    let highestRiskLevel = 'Low';
    let latestTimestamp = new Date(0).toISOString();

    const riskLevels = ['Low', 'Normal', 'Moderate', 'High', 'Extreme'];

    for (let i = 0; i < portfolioResults.length; i++) {
      const result = portfolioResults[i];
      const source = sources[i];

      if (result.status === 'fulfilled') {
        const portfolio = result.value;

        totalValue += portfolio.total_value;
        totalDailyPnl += portfolio.daily_pnl;
        // Estimate total P&L (this would need more sophisticated calculation)
        totalPnl += portfolio.daily_pnl * 30; // Rough monthly estimate

        // Convert positions to unified format
        portfolio.positions.forEach(pos => {
          const marketType = this.determineMarketType(pos.symbol);
          allPositions.push({
            ...pos,
            market_type: marketType,
            source
          });
        });

        // Update risk level (take the highest risk)
        const riskIndex = riskLevels.indexOf(portfolio.risk_level);
        const currentRiskIndex = riskLevels.indexOf(highestRiskLevel);
        if (riskIndex > currentRiskIndex) {
          highestRiskLevel = portfolio.risk_level;
        }

        // Update latest timestamp
        if (portfolio.timestamp > latestTimestamp) {
          latestTimestamp = portfolio.timestamp;
        }
      } else {
        logger.warn(`Failed to aggregate portfolio from ${source}:`, result.reason);
      }
    }

    return {
      total_value: totalValue,
      daily_pnl: totalDailyPnl,
      total_pnl: totalPnl,
      positions: allPositions,
      risk_level: highestRiskLevel,
      last_updated: latestTimestamp,
      sources: sources.filter((_, i) => portfolioResults[i].status === 'fulfilled')
    };
  }

  /**
   * Get unified performance metrics
   */
  async getUnifiedPerformanceMetrics(userId?: string): Promise<UnifiedPerformanceMetrics> {
    const availableDBs = this.dbService.getAvailableDatabases();

    // Get trade history from all databases
    const tradeResults = await Promise.allSettled(
      availableDBs.map(db => this.dbService.queryTradeHistory(db, 1000, userId))
    );

    const allTrades = tradeResults
      .filter((result, i) => {
        if (result.status === 'rejected') {
          logger.warn(`Failed to get trades from ${availableDBs[i]}:`, result.reason);
          return false;
        }
        return true;
      })
      .flatMap(result => (result as PromiseFulfilledResult<Trade[]>).value);

    return this.calculatePerformanceMetrics(allTrades, availableDBs);
  }

  /**
   * Calculate unified performance metrics from trade data
   */
  private calculatePerformanceMetrics(trades: Trade[], sources: string[]): UnifiedPerformanceMetrics {
    if (trades.length === 0) {
      return {
        total_return: 0,
        sharpe_ratio: 0,
        max_drawdown: 0,
        volatility: 0,
        win_rate: 0,
        profit_factor: 0,
        calmar_ratio: 0,
        timestamp: new Date().toISOString(),
        sources: []
      };
    }

    // Sort trades by timestamp
    trades.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    // Calculate basic metrics
    const totalReturn = trades.reduce((sum, trade) => sum + (trade.pnl || 0), 0);
    const winningTrades = trades.filter(trade => (trade.pnl || 0) > 0);
    const losingTrades = trades.filter(trade => (trade.pnl || 0) < 0);
    const winRate = winningTrades.length / trades.length;

    const grossProfit = winningTrades.reduce((sum, trade) => sum + (trade.pnl || 0), 0);
    const grossLoss = Math.abs(losingTrades.reduce((sum, trade) => sum + (trade.pnl || 0), 0));
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : 0;

    // Calculate returns series for advanced metrics
    const returns = this.calculateReturnsSeries(trades);
    const sharpeRatio = this.calculateSharpeRatio(returns);
    const volatility = this.calculateVolatility(returns);
    const maxDrawdown = this.calculateMaxDrawdown(returns);
    const calmarRatio = maxDrawdown > 0 ? totalReturn / maxDrawdown : 0;

    return {
      total_return: totalReturn,
      sharpe_ratio: sharpeRatio,
      max_drawdown: maxDrawdown,
      volatility: volatility,
      win_rate: winRate,
      profit_factor: profitFactor,
      calmar_ratio: calmarRatio,
      timestamp: new Date().toISOString(),
      sources
    };
  }

  /**
   * Get unified risk metrics
   */
  async getUnifiedRiskMetrics(userId?: string): Promise<UnifiedRiskMetrics> {
    const availableDBs = this.dbService.getAvailableDatabases();

    // Get risk metrics from all databases
    const riskResults = await Promise.allSettled(
      availableDBs.map(db => this.dbService.queryRiskMetrics(db, userId))
    );

    const validRiskMetrics = riskResults
      .filter((result, i) => {
        if (result.status === 'rejected') {
          logger.warn(`Failed to get risk metrics from ${availableDBs[i]}:`, result.reason);
          return false;
        }
        return true;
      })
      .map(result => (result as PromiseFulfilledResult<RiskMetrics>).value);

    return this.aggregateRiskMetrics(validRiskMetrics, availableDBs);
  }

  /**
   * Aggregate risk metrics from multiple sources
   */
  private aggregateRiskMetrics(riskMetrics: RiskMetrics[], sources: string[]): UnifiedRiskMetrics {
    if (riskMetrics.length === 0) {
      return {
        max_drawdown: 0,
        sharpe_ratio: 0,
        volatility: 0,
        value_at_risk: 0,
        expected_shortfall: 0,
        beta: 0,
        correlation_matrix: {},
        timestamp: new Date().toISOString(),
        sources: []
      };
    }

    // Take the most conservative (worst) values
    const maxDrawdown = Math.max(...riskMetrics.map(r => r.max_drawdown));
    const sharpeRatio = Math.min(...riskMetrics.map(r => r.sharpe_ratio)); // Lower is worse
    const volatility = Math.max(...riskMetrics.map(r => r.volatility));
    const valueAtRisk = Math.max(...riskMetrics.map(r => r.value_at_risk));

    // Estimate expected shortfall (simplified)
    const expectedShortfall = valueAtRisk * 1.5;

    // Beta and correlation would need more sophisticated calculation
    const beta = riskMetrics.reduce((sum, r) => sum + (r as any).beta || 1, 0) / riskMetrics.length;

    return {
      max_drawdown: maxDrawdown,
      sharpe_ratio: sharpeRatio,
      volatility: volatility,
      value_at_risk: valueAtRisk,
      expected_shortfall: expectedShortfall,
      beta: beta,
      correlation_matrix: {}, // Would need cross-market correlation analysis
      timestamp: new Date().toISOString(),
      sources
    };
  }

  /**
   * Get market exposure breakdown
   */
  async getMarketExposure(userId?: string): Promise<MarketExposure> {
    const portfolio = await this.getUnifiedPortfolio(userId);

    let cryptoValue = 0;
    let stockValue = 0;
    let forexValue = 0;

    portfolio.positions.forEach(position => {
      const positionValue = position.size * position.current_price;
      switch (position.market_type) {
        case 'crypto':
          cryptoValue += positionValue;
          break;
        case 'stock':
          stockValue += positionValue;
          break;
        case 'forex':
          forexValue += positionValue;
          break;
      }
    });

    const total = cryptoValue + stockValue + forexValue;
    const diversificationRatio = total > 0 ?
      1 / (Math.pow(cryptoValue/total, 2) + Math.pow(stockValue/total, 2) + Math.pow(forexValue/total, 2)) : 0;

    return {
      crypto: cryptoValue,
      stocks: stockValue,
      forex: forexValue,
      total,
      diversification_ratio: diversificationRatio
    };
  }

  /**
   * Determine market type from symbol
   */
  private determineMarketType(symbol: string): 'crypto' | 'stock' | 'forex' {
    const upperSymbol = symbol.toUpperCase();

    // Common forex pairs
    const forexPairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF'];
    if (forexPairs.some(pair => upperSymbol.includes(pair))) {
      return 'forex';
    }

    // Crypto symbols (typically end with USDT, BTC, ETH, etc.)
    if (upperSymbol.includes('USDT') || upperSymbol.includes('BTC') ||
        upperSymbol.includes('ETH') || upperSymbol.includes('BNB') ||
        upperSymbol.includes('ADA') || upperSymbol.includes('SOL')) {
      return 'crypto';
    }

    // Default to stock
    return 'stock';
  }

  /**
   * Calculate returns series from trades
   */
  private calculateReturnsSeries(trades: Trade[]): number[] {
    // This is a simplified calculation
    // In reality, you'd need to consider position sizing and time-weighted returns
    const returns: number[] = [];
    let cumulativeReturn = 0;

    for (const trade of trades) {
      if (trade.pnl) {
        const tradeReturn = trade.pnl / 10000; // Assuming $10k starting capital
        cumulativeReturn += tradeReturn;
        returns.push(tradeReturn);
      }
    }

    return returns;
  }

  /**
   * Calculate Sharpe ratio
   */
  private calculateSharpeRatio(returns: number[]): number {
    if (returns.length === 0) return 0;

    const avgReturn = returns.reduce((sum, r) => sum + r, 0) / returns.length;
    const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length;
    const stdDev = Math.sqrt(variance);

    // Assuming 2% risk-free rate (annualized)
    const riskFreeRate = 0.02 / 252; // Daily risk-free rate

    return stdDev > 0 ? (avgReturn - riskFreeRate) / stdDev : 0;
  }

  /**
   * Calculate volatility (standard deviation)
   */
  private calculateVolatility(returns: number[]): number {
    if (returns.length === 0) return 0;

    const avgReturn = returns.reduce((sum, r) => sum + r, 0) / returns.length;
    const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length;

    return Math.sqrt(variance);
  }

  /**
   * Calculate maximum drawdown
   */
  private calculateMaxDrawdown(returns: number[]): number {
    if (returns.length === 0) return 0;

    let peak = 0;
    let maxDrawdown = 0;
    let cumulative = 0;

    for (const return_val of returns) {
      cumulative += return_val;
      if (cumulative > peak) {
        peak = cumulative;
      }
      const drawdown = peak - cumulative;
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
      }
    }

    return maxDrawdown;
  }
}
