import type {
  Action,
  ActionResult,
  HandlerCallback,
  IAgentRuntime,
  Memory,
  State,
} from '@elizaos/core';
import { logger } from '@elizaos/core';
import { SupabaseDatabaseService, Trade } from '../services/supabase-service';

/**
 * Format trade history response
 */
function formatTradeHistoryResponse(trades: Trade[], limit?: number): string {
  if (!trades || trades.length === 0) {
    return '📭 No trading history found.';
  }

  const displayTrades = limit ? trades.slice(0, limit) : trades;
  const totalTrades = trades.length;

  let response = `📊 Trade History (Showing ${displayTrades.length} of ${totalTrades} trades):\n\n`;

  displayTrades.forEach((trade, index) => {
    const pnl = trade.pnl !== undefined ? trade.pnl.toFixed(2) : '0.00';
    const pnlSign = trade.pnl && trade.pnl >= 0 ? '+' : '';
    const pnlColor = trade.pnl && trade.pnl >= 0 ? '🟢' : '🔴';

    const date = new Date(trade.timestamp).toLocaleDateString();
    const time = new Date(trade.timestamp).toLocaleTimeString();

    response += `${index + 1}. ${trade.side.toUpperCase()} ${trade.symbol}\n`;
    response += `   Size: ${trade.size} @ $${trade.price.toFixed(trade.symbol.includes('USDT') ? 4 : 2)}\n`;
    response += `   P&L: ${pnlColor} ${pnlSign}$${pnl}\n`;
    response += `   Date: ${date} ${time}\n\n`;
  });

  // Add summary statistics
  const profitableTrades = trades.filter(t => (t.pnl || 0) > 0);
  const losingTrades = trades.filter(t => (t.pnl || 0) < 0);
  const winRate = totalTrades > 0 ? (profitableTrades.length / totalTrades * 100).toFixed(1) : '0.0';
  const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);

  response += `📈 Summary:\n`;
  response += `• Total Trades: ${totalTrades}\n`;
  response += `• Win Rate: ${winRate}%\n`;
  response += `• Profitable: ${profitableTrades.length}\n`;
  response += `• Losing: ${losingTrades.length}\n`;
  response += `• Total P&L: ${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`;

  return response;
}

/**
 * GET_TRADE_HISTORY action for retrieving trade history
 */
export const getTradeHistoryAction: Action = {
  name: 'GET_TRADE_HISTORY',
  similes: ['TRADE_HISTORY', 'SHOW_TRADES', 'MY_TRADES', 'TRADING_HISTORY'],
  description: 'Retrieve trading history with optional filtering',

  validate: async (
    _runtime: IAgentRuntime,
    _message: Memory,
    _state: State | undefined
  ): Promise<boolean> => {
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
      const bridgeService = runtime.getService('itoro-bridge' as any);
      if (!bridgeService) {
        throw new Error('ITORO bridge service not available');
      }

      const dbService = (bridgeService as any).dbService as SupabaseDatabaseService;
      if (!dbService) {
        throw new Error('Database service not available');
      }

      // Parse message for limit parameter
      const text = message.content.text?.toLowerCase() || '';
      let limit = 10; // default

      if (text.includes('last') || text.includes('recent')) {
        const match = text.match(/(\d+)/);
        if (match) {
          limit = Math.min(parseInt(match[1]), 100); // max 100
        }
      }

      // Get trade history from all available databases
      const availableDBs = dbService.getAvailableDatabases();
      const tradePromises = availableDBs.map(db =>
        dbService.queryTradeHistory(db, limit * 2, message.entityId) // Get more to filter
      );

      const tradeResults = await Promise.allSettled(tradePromises);

      // Combine and sort all trades
      const allTrades: Trade[] = [];
      tradeResults.forEach(result => {
        if (result.status === 'fulfilled') {
          allTrades.push(...result.value);
        }
      });

      // Sort by timestamp (most recent first) and limit
      allTrades.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      const finalTrades = allTrades.slice(0, limit);

      const formattedResponse = formatTradeHistoryResponse(finalTrades, limit);

      if (callback) {
        await callback({
          text: formattedResponse,
          actions: ['GET_TRADE_HISTORY'],
          source: message.content.source,
        });
      }

      return {
        text: formattedResponse,
        success: true,
        data: {
          actions: ['GET_TRADE_HISTORY'],
          trades: finalTrades,
          limit,
          sources: availableDBs
        },
      };
    } catch (error) {
      logger.error('Trade history action failed:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to retrieve trade history';

      if (callback) {
        await callback({
          text: `Sorry, I couldn't retrieve your trade history: ${errorMessage}`,
          actions: ['GET_TRADE_HISTORY'],
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
          text: 'Show me my last 5 trades',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Retrieving your recent trading history...',
        },
      },
    ],
    [
      {
        name: '{{user1}}',
        content: {
          text: 'What trades did I make recently?',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Getting your trade history...',
        },
      },
    ],
  ],
};
