import type {
  Action,
  ActionResult,
  HandlerCallback,
  IAgentRuntime,
  Memory,
  State,
} from '@elizaos/core';
import { logger } from '@elizaos/core';
import { WebhookClient } from '../communication/webhook-client';

/**
 * TRADING_QUERY action for general trading queries to ITORO
 */
export const tradingQueryAction: Action = {
  name: 'TRADING_QUERY',
  similes: [
    'TRADING_QUESTION',
    'MARKET_QUERY',
    'TRADE_ANALYSIS',
    'MARKET_ANALYSIS',
    'TRADING_ADVICE',
  ],
  description: 'Send a general trading query to ITORO trading system for analysis and recommendations',

  validate: async (
    runtime: IAgentRuntime,
    message: Memory,
    _state: State | undefined
  ): Promise<boolean> => {
    // Check if message contains trading-related keywords
    const text = message.content.text?.toLowerCase() || '';
    const tradingKeywords = [
      'trade',
      'trading',
      'portfolio',
      'market',
      'crypto',
      'bitcoin',
      'btc',
      'eth',
      'ethereum',
      'position',
      'buy',
      'sell',
      'hold',
      'risk',
      'profit',
      'loss',
      'strategy',
      'signal',
    ];

    return tradingKeywords.some((keyword) => text.includes(keyword));
  },

  handler: async (
    runtime: IAgentRuntime,
    message: Memory,
    _state: State | undefined,
    _options: any,
    callback?: HandlerCallback
  ): Promise<ActionResult> => {
    try {
      // Get the bridge service to access webhook client
      const bridgeService = runtime.getService('itoro-bridge' as any);
      if (!bridgeService) {
        throw new Error('ITORO bridge service not available');
      }

      const webhookClient = (bridgeService as any).webhookClient as WebhookClient;
      if (!webhookClient) {
        throw new Error('ITORO webhook client not available');
      }

      const queryText = message.content.text || '';

      // Send query to ITORO
      const response = await webhookClient.sendQuery('itoro', queryText, {
        user_id: message.entityId,
        room_id: message.roomId,
        request_type: 'trading_query',
        eliza_message_id: message.id,
        priority: 'medium',
      });

      // Wait for response
      let queryResponse;
      try {
        queryResponse = await webhookClient.waitForResponse(response.correlation_id, 30000);
      } catch (error) {
        logger.warn('Trading query timeout, using fallback response');
        queryResponse = {
          text: 'I received your trading query, but the response is taking longer than expected. Please try again in a moment.',
        };
      }

      const responseText =
        queryResponse?.text ||
        queryResponse?.content?.text ||
        'I received your query and am processing it. Please wait for a response.';

      if (callback) {
        await callback({
          text: responseText,
          actions: ['TRADING_QUERY'],
          source: message.content.source,
        });
      }

      return {
        text: responseText,
        success: true,
        data: {
          actions: ['TRADING_QUERY'],
          query: queryText,
          response: queryResponse,
        },
      };
    } catch (error) {
      logger.error('Trading query action failed:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to process trading query';

      if (callback) {
        await callback({
          text: `Sorry, I couldn't process your trading query: ${errorMessage}`,
          actions: ['TRADING_QUERY'],
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
          text: 'What do you think about BTC right now?',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Analyzing current BTC market conditions...',
        },
      },
    ],
    [
      {
        name: '{{user1}}',
        content: {
          text: 'Should I buy more ETH?',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Evaluating ETH trading opportunity...',
        },
      },
    ],
  ],
};

