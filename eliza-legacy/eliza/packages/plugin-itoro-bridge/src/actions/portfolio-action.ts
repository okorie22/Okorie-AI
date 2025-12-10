import type {
  Action,
  ActionResult,
  HandlerCallback,
  IAgentRuntime,
  Memory,
  State,
} from '@elizaos/core';
import { logger } from '@elizaos/core';
import { RAGEngine } from '../services/rag-engine';
import { SupabaseDatabaseService } from '../services/supabase-service';
import { UnifiedDataAggregator } from '../services/unified-data-aggregator';

/**
 * Format portfolio response data into readable text
 */
function formatPortfolioResponse(data: any): string {
  if (!data || typeof data !== 'object') {
    return 'Portfolio data is not available at this time.';
  }

  const totalValue = data.total_value?.toLocaleString?.() || data.total_value || 'N/A';
  const dailyPnl = data.daily_pnl !== undefined ? data.daily_pnl.toFixed(2) : '0.00';
  const dailyPnlSign = data.daily_pnl >= 0 ? '+' : '';
  const totalPnl = data.total_pnl !== undefined ? data.total_pnl.toFixed(2) : '0.00';
  const totalPnlSign = data.total_pnl >= 0 ? '+' : '';
  const positions = data.positions || [];
  const riskLevel = data.risk_level || 'Normal';
  const sources = data.sources || [];

  let response = `📊 Portfolio Status (Real-time):
• Total Value: $${totalValue}
• Daily P&L: ${dailyPnlSign}$${dailyPnl}
• Total P&L: ${totalPnlSign}$${totalPnl}
• Active Positions: ${positions.length}
• Risk Level: ${riskLevel}`;

  if (sources.length > 0) {
    response += `\n• Data Sources: ${sources.join(', ')}`;
  }

  if (positions.length > 0) {
    response += '\n\n💼 Key Positions:';

    // Group positions by market type
    const cryptoPositions = positions.filter((p: any) => p.market_type === 'crypto');
    const stockPositions = positions.filter((p: any) => p.market_type === 'stock');
    const forexPositions = positions.filter((p: any) => p.market_type === 'forex');

    if (cryptoPositions.length > 0) {
      response += '\n\n🪙 Cryptocurrency:';
      cryptoPositions.slice(0, 5).forEach((pos: any) => {
        const symbol = pos.symbol || 'N/A';
        const side = pos.side || 'N/A';
        const size = pos.size || 'N/A';
        const avgPrice = pos.avg_price?.toFixed(4) || 'N/A';
        const unrealizedPnl = pos.unrealized_pnl !== undefined ? pos.unrealized_pnl.toFixed(2) : '0.00';
        const pnlSign = pos.unrealized_pnl >= 0 ? '+' : '';
        response += `\n• ${symbol}: ${side} ${size} @ $${avgPrice} (${pnlSign}$${unrealizedPnl})`;
      });
    }

    if (stockPositions.length > 0) {
      response += '\n\n📈 Stocks:';
      stockPositions.slice(0, 5).forEach((pos: any) => {
        const symbol = pos.symbol || 'N/A';
        const side = pos.side || 'N/A';
        const size = pos.size || 'N/A';
        const avgPrice = pos.avg_price?.toFixed(2) || 'N/A';
        const unrealizedPnl = pos.unrealized_pnl !== undefined ? pos.unrealized_pnl.toFixed(2) : '0.00';
        const pnlSign = pos.unrealized_pnl >= 0 ? '+' : '';
        response += `\n• ${symbol}: ${side} ${size} @ $${avgPrice} (${pnlSign}$${unrealizedPnl})`;
      });
    }

    if (forexPositions.length > 0) {
      response += '\n\n💱 Forex:';
      forexPositions.slice(0, 3).forEach((pos: any) => {
        const symbol = pos.symbol || 'N/A';
        const side = pos.side || 'N/A';
        const size = pos.size || 'N/A';
        const avgPrice = pos.avg_price?.toFixed(4) || 'N/A';
        const unrealizedPnl = pos.unrealized_pnl !== undefined ? pos.unrealized_pnl.toFixed(2) : '0.00';
        const pnlSign = pos.unrealized_pnl >= 0 ? '+' : '';
        response += `\n• ${symbol}: ${side} ${size} @ ${avgPrice} (${pnlSign}$${unrealizedPnl})`;
      });
    }
  } else {
    response += '\n\n📭 No active positions';
  }

  return response;
}

/**
 * GET_PORTFOLIO action for retrieving portfolio status from ITORO
 */
export const getPortfolioAction: Action = {
  name: 'GET_PORTFOLIO',
  similes: ['PORTFOLIO_STATUS', 'SHOW_PORTFOLIO', 'PORTFOLIO_SUMMARY', 'MY_PORTFOLIO'],
  description: 'Retrieve current portfolio status from ITORO trading system',

  validate: async (
    _runtime: IAgentRuntime,
    _message: Memory,
    _state: State | undefined
  ): Promise<boolean> => {
    // Always valid for portfolio queries
    return true;
  },

  handler: async (
    runtime: IAgentRuntime,
    message: Memory,
    _state: State | undefined,
    _options: any,
    callback?: HandlerCallback
  ): Promise<ActionResult> => {
    try {
      // Get the bridge service
      const bridgeService = runtime.getService('itoro-bridge' as any);
      if (!bridgeService) {
        throw new Error('ITORO bridge service not available');
      }

      // Get the data aggregator from the bridge service
      const dataAggregator = (bridgeService as any).dataAggregator as UnifiedDataAggregator;
      if (!dataAggregator) {
        throw new Error('Data aggregator not available');
      }

      // Get unified portfolio data
      const portfolioData = await dataAggregator.getUnifiedPortfolio(message.entityId);

      // Get market exposure for additional context
      const marketExposure = await dataAggregator.getMarketExposure(message.entityId);

      // Enhance portfolio data with market exposure
      const enhancedPortfolioData = {
        ...portfolioData,
        market_exposure: marketExposure
      };

      const formattedResponse = formatPortfolioResponse(enhancedPortfolioData);

      if (callback) {
        await callback({
          text: formattedResponse,
          actions: ['GET_PORTFOLIO'],
          source: message.content.source,
        });
      }

      return {
        text: formattedResponse,
        success: true,
        data: {
          actions: ['GET_PORTFOLIO'],
          portfolio: enhancedPortfolioData,
        },
      };
    } catch (error) {
      logger.error('Portfolio action failed:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to retrieve portfolio data';

      if (callback) {
        await callback({
          text: `Sorry, I couldn't retrieve your portfolio data: ${errorMessage}`,
          actions: ['GET_PORTFOLIO'],
          source: message.content.source,
        });
      }

      return {
        success: false,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    }
  },

  examples: [
    [
      {
        name: '{{user1}}',
        content: {
          text: 'Show me my portfolio status',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Retrieving your current portfolio data...',
        },
      },
    ],
    [
      {
        name: '{{user1}}',
        content: {
          text: 'What is my portfolio value?',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Getting your portfolio information...',
        },
      },
    ],
  ],
};

