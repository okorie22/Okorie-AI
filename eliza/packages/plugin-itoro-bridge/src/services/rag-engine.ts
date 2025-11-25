import { logger } from '@elizaos/core';
import { SupabaseDatabaseService, PortfolioData, Trade, RiskMetrics, WhaleData } from './supabase-service';

/**
 * Query result interface
 */
export interface QueryResult {
  answer: string;
  confidence: number;
  sources: string[];
  data?: any;
  timestamp: string;
}

/**
 * Context data for LLM
 */
export interface ContextData {
  portfolio: PortfolioData;
  recentTrades: Trade[];
  riskMetrics: RiskMetrics;
  whaleData: WhaleData[];
  marketContext: string;
}

/**
 * RAG Engine for ITORO Trading Data
 * Implements retrieval-augmented generation for trading queries
 */
export class RAGEngine {
  private dbService: SupabaseDatabaseService;
  private initialized = false;

  constructor(dbService: SupabaseDatabaseService) {
    this.dbService = dbService;
  }

  /**
   * Initialize the RAG engine
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    this.initialized = true;
    logger.info('RAG Engine initialized');
  }

  /**
   * Process a natural language query about trading data
   */
  async query(query: string, userId?: string): Promise<QueryResult> {
    try {
      // Parse query intent
      const intent = this.parseQueryIntent(query);

      // Retrieve relevant context
      const context = await this.retrieveContext(intent, userId);

      // Generate response using retrieved context
      const result = await this.generateResponse(query, intent, context);

      return result;
    } catch (error) {
      logger.error('RAG query failed:', error);
      return {
        answer: 'Sorry, I encountered an error while processing your trading query.',
        confidence: 0,
        sources: [],
        timestamp: new Date().toISOString()
      };
    }
  }

  /**
   * Parse query intent from natural language
   */
  private parseQueryIntent(query: string): QueryIntent {
    const lowerQuery = query.toLowerCase();

    // Portfolio queries
    if (lowerQuery.includes('portfolio') || lowerQuery.includes('balance') ||
        lowerQuery.includes('position') || lowerQuery.includes('holding')) {
      return 'portfolio';
    }

    // Trade history queries
    if (lowerQuery.includes('trade') || lowerQuery.includes('history') ||
        lowerQuery.includes('transaction') || lowerQuery.includes('buy') ||
        lowerQuery.includes('sell')) {
      return 'trade_history';
    }

    // Performance queries
    if (lowerQuery.includes('performance') || lowerQuery.includes('pnl') ||
        lowerQuery.includes('profit') || lowerQuery.includes('loss') ||
        lowerQuery.includes('return') || lowerQuery.includes('gain')) {
      return 'performance';
    }

    // Risk queries
    if (lowerQuery.includes('risk') || lowerQuery.includes('drawdown') ||
        lowerQuery.includes('sharpe') || lowerQuery.includes('volatility') ||
        lowerQuery.includes('var')) {
      return 'risk';
    }

    // Whale queries
    if (lowerQuery.includes('whale') || lowerQuery.includes('large') ||
        lowerQuery.includes('big') || lowerQuery.includes('movement')) {
      return 'whale';
    }

    // Market sentiment queries
    if (lowerQuery.includes('sentiment') || lowerQuery.includes('market') ||
        lowerQuery.includes('trend') || lowerQuery.includes('analysis')) {
      return 'market_sentiment';
    }

    return 'general';
  }

  /**
   * Retrieve relevant context based on query intent
   */
  private async retrieveContext(intent: QueryIntent, userId?: string): Promise<ContextData> {
    const availableDBs = this.dbService.getAvailableDatabases();

    // Try to get data from both paper and live databases if available
    const paperDB = availableDBs.find(db => db.includes('paper'));
    const liveDB = availableDBs.find(db => db.includes('live'));

    const context: ContextData = {
      portfolio: await this.getPortfolioContext(paperDB || liveDB, userId),
      recentTrades: await this.getTradeContext(paperDB || liveDB, userId),
      riskMetrics: await this.getRiskContext(paperDB || liveDB, userId),
      whaleData: await this.getWhaleContext(paperDB || liveDB),
      marketContext: await this.getMarketContext(intent)
    };

    return context;
  }

  /**
   * Get portfolio context
   */
  private async getPortfolioContext(dbName?: string, userId?: string): Promise<PortfolioData> {
    if (!dbName) {
      return {
        total_value: 0,
        daily_pnl: 0,
        positions: [],
        risk_level: 'Normal',
        timestamp: new Date().toISOString()
      };
    }

    try {
      return await this.dbService.queryPortfolio(dbName, userId);
    } catch (error) {
      logger.warn(`Failed to get portfolio context from ${dbName}:`, error);
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
   * Get trade history context
   */
  private async getTradeContext(dbName?: string, userId?: string): Promise<Trade[]> {
    if (!dbName) return [];

    try {
      return await this.dbService.queryTradeHistory(dbName, 10, userId);
    } catch (error) {
      logger.warn(`Failed to get trade context from ${dbName}:`, error);
      return [];
    }
  }

  /**
   * Get risk metrics context
   */
  private async getRiskContext(dbName?: string, userId?: string): Promise<RiskMetrics> {
    if (!dbName) {
      return {
        max_drawdown: 0,
        sharpe_ratio: 0,
        volatility: 0,
        value_at_risk: 0,
        timestamp: new Date().toISOString()
      };
    }

    try {
      return await this.dbService.queryRiskMetrics(dbName, userId);
    } catch (error) {
      logger.warn(`Failed to get risk context from ${dbName}:`, error);
      return {
        max_drawdown: 0,
        sharpe_ratio: 0,
        volatility: 0,
        value_at_risk: 0,
        timestamp: new Date().toISOString()
      };
    }
  }

  /**
   * Get whale data context
   */
  private async getWhaleContext(dbName?: string): Promise<WhaleData[]> {
    if (!dbName) return [];

    try {
      return await this.dbService.queryWhaleData(dbName, 5);
    } catch (error) {
      logger.warn(`Failed to get whale context from ${dbName}:`, error);
      return [];
    }
  }

  /**
   * Get market context based on intent
   */
  private async getMarketContext(intent: QueryIntent): Promise<string> {
    // This would typically call market data APIs or use cached data
    // For now, return a generic context
    switch (intent) {
      case 'portfolio':
        return 'Market conditions appear stable with moderate volatility.';
      case 'risk':
        return 'Current market volatility is within normal ranges.';
      case 'whale':
        return 'Large holder movements detected in major cryptocurrencies.';
      default:
        return 'Market analysis indicates normal trading conditions.';
    }
  }

  /**
   * Generate response using retrieved context
   */
  private async generateResponse(
    query: string,
    intent: QueryIntent,
    context: ContextData
  ): Promise<QueryResult> {
    const sources = ['portfolio_data', 'trade_history', 'risk_metrics'];

    switch (intent) {
      case 'portfolio':
        return this.generatePortfolioResponse(query, context, sources);
      case 'trade_history':
        return this.generateTradeHistoryResponse(query, context, sources);
      case 'performance':
        return this.generatePerformanceResponse(query, context, sources);
      case 'risk':
        return this.generateRiskResponse(query, context, sources);
      case 'whale':
        return this.generateWhaleResponse(query, context, sources);
      default:
        return this.generateGeneralResponse(query, context, sources);
    }
  }

  /**
   * Generate portfolio-focused response
   */
  private generatePortfolioResponse(
    query: string,
    context: ContextData,
    sources: string[]
  ): QueryResult {
    const portfolio = context.portfolio;
    const totalValue = portfolio.total_value.toLocaleString();
    const dailyPnl = portfolio.daily_pnl.toFixed(2);
    const pnlSign = portfolio.daily_pnl >= 0 ? '+' : '';

    let answer = `Your current portfolio value is $${totalValue} with a daily P&L of ${pnlSign}$${dailyPnl}. `;

    if (portfolio.positions.length > 0) {
      answer += `You have ${portfolio.positions.length} active positions. `;
      answer += `Key holdings include: ${portfolio.positions.slice(0, 3).map(p =>
        `${p.symbol} (${p.side} ${p.size} @ $${p.avg_price.toFixed(2)})`
      ).join(', ')}.`;
    } else {
      answer += 'You currently have no active positions.';
    }

    return {
      answer,
      confidence: 0.95,
      sources,
      data: portfolio,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Generate trade history response
   */
  private generateTradeHistoryResponse(
    query: string,
    context: ContextData,
    sources: string[]
  ): QueryResult {
    const trades = context.recentTrades;

    if (trades.length === 0) {
      return {
        answer: 'I don\'t see any recent trades in your trading history.',
        confidence: 0.8,
        sources,
        data: [],
        timestamp: new Date().toISOString()
      };
    }

    const recentTrades = trades.slice(0, 5);
    const totalTrades = trades.length;

    let answer = `You have ${totalTrades} total trades. Here are your most recent ${recentTrades.length} trades:\n\n`;

    recentTrades.forEach((trade, index) => {
      const pnl = trade.pnl ? ` (${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(2)})` : '';
      answer += `${index + 1}. ${trade.side.toUpperCase()} ${trade.size} ${trade.symbol} @ $${trade.price.toFixed(2)}${pnl} on ${new Date(trade.timestamp).toLocaleDateString()}\n`;
    });

    return {
      answer,
      confidence: 0.9,
      sources,
      data: recentTrades,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Generate performance response
   */
  private generatePerformanceResponse(
    query: string,
    context: ContextData,
    sources: string[]
  ): QueryResult {
    const portfolio = context.portfolio;
    const risk = context.riskMetrics;

    const totalValue = portfolio.total_value.toLocaleString();
    const dailyPnl = portfolio.daily_pnl.toFixed(2);
    const pnlSign = portfolio.daily_pnl >= 0 ? '+' : '';

    let answer = `Performance Summary:\n`;
    answer += `• Portfolio Value: $${totalValue}\n`;
    answer += `• Daily P&L: ${pnlSign}$${dailyPnl}\n`;
    answer += `• Sharpe Ratio: ${risk.sharpe_ratio.toFixed(2)}\n`;
    answer += `• Max Drawdown: ${(risk.max_drawdown * 100).toFixed(2)}%\n`;
    answer += `• Volatility: ${(risk.volatility * 100).toFixed(2)}%\n`;

    return {
      answer,
      confidence: 0.85,
      sources,
      data: { portfolio, risk },
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Generate risk analysis response
   */
  private generateRiskResponse(
    query: string,
    context: ContextData,
    sources: string[]
  ): QueryResult {
    const risk = context.riskMetrics;
    const portfolio = context.portfolio;

    let answer = `Risk Analysis:\n`;
    answer += `• Risk Level: ${portfolio.risk_level}\n`;
    answer += `• Max Drawdown: ${(risk.max_drawdown * 100).toFixed(2)}%\n`;
    answer += `• Sharpe Ratio: ${risk.sharpe_ratio.toFixed(2)}\n`;
    answer += `• Portfolio Volatility: ${(risk.volatility * 100).toFixed(2)}%\n`;
    answer += `• Value at Risk (VaR): ${(risk.value_at_risk * 100).toFixed(2)}%\n`;

    const riskAssessment = risk.max_drawdown > 0.2 ? 'High Risk' :
                          risk.max_drawdown > 0.1 ? 'Moderate Risk' : 'Low Risk';
    answer += `• Overall Risk Assessment: ${riskAssessment}`;

    return {
      answer,
      confidence: 0.9,
      sources,
      data: risk,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Generate whale data response
   */
  private generateWhaleResponse(
    query: string,
    context: ContextData,
    sources: string[]
  ): QueryResult {
    const whales = context.whaleData;

    if (whales.length === 0) {
      return {
        answer: 'No recent whale movements detected in the market.',
        confidence: 0.7,
        sources,
        data: [],
        timestamp: new Date().toISOString()
      };
    }

    let answer = `Recent whale movements:\n\n`;
    whales.forEach((whale, index) => {
      const amount = whale.amount.toLocaleString();
      answer += `${index + 1}. ${whale.transaction_type.toUpperCase()} ${amount} ${whale.symbol} by whale ${whale.whale_address.substring(0, 8)}... on ${new Date(whale.timestamp).toLocaleDateString()}\n`;
    });

    return {
      answer,
      confidence: 0.8,
      sources,
      data: whales,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Generate general response
   */
  private generateGeneralResponse(
    query: string,
    context: ContextData,
    sources: string[]
  ): QueryResult {
    const portfolio = context.portfolio;

    const answer = `Based on your current trading data: Your portfolio is valued at $${portfolio.total_value.toLocaleString()} with ${portfolio.positions.length} active positions. ${context.marketContext} How else can I help you with your trading information?`;

    return {
      answer,
      confidence: 0.6,
      sources,
      data: context,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Query intent types
 */
type QueryIntent = 'portfolio' | 'trade_history' | 'performance' | 'risk' | 'whale' | 'market_sentiment' | 'general';
