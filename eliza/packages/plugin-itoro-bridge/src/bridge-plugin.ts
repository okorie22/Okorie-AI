import type { Plugin, IAgentRuntime } from '@elizaos/core';
import { logger } from '@elizaos/core';
import { z } from 'zod';
import { ITOROBridgeService } from './services/itoro-service';
import { getPortfolioAction } from './actions/portfolio-action';
import { tradingQueryAction } from './actions/trading-query-action';
import { getTradeHistoryAction } from './actions/trade-history-action';
import { getRiskMetricsAction } from './actions/risk-metrics-action';

/**
 * Configuration schema for the bridge plugin
 */
const bridgeConfigSchema = z.object({
  // ITORO Webhook Configuration
  ITORO_WEBHOOK_URL: z
    .string()
    .url('ITORO_WEBHOOK_URL must be a valid URL')
    .min(1, 'ITORO_WEBHOOK_URL is required'),
  ITORO_WEBHOOK_SECRET: z
    .string()
    .min(32, 'ITORO_WEBHOOK_SECRET must be at least 32 characters')
    .min(1, 'ITORO_WEBHOOK_SECRET is required'),

  // Supabase Database Configuration
  SUPABASE_PAPER_TRADING_URL: z
    .string()
    .optional(),
  SUPABASE_PAPER_TRADING_ANON_KEY: z
    .string()
    .optional(),
  SUPABASE_LIVE_TRADING_URL: z
    .string()
    .optional(),
  SUPABASE_LIVE_TRADING_ANON_KEY: z
    .string()
    .optional(),
  SUPABASE_SERVICE_ROLE_KEY: z
    .string()
    .optional(),

  // Local Database Paths
  PAPER_TRADING_DB_PATH: z
    .string()
    .optional()
    .default('multi-agents/itoro/ai_crypto_agents/data/paper_trading.db'),
  LIVE_TRADING_DB_PATH: z
    .string()
    .optional(),

  // Redis Configuration
  REDIS_URL: z
    .string()
    .optional()
    .default('redis://localhost:6379'),
  REDIS_EVENT_STREAM_PREFIX: z
    .string()
    .optional()
    .default('core_signals'),

  // Bridge Configuration
  BRIDGE_MODE: z
    .enum(['unified', 'individual'])
    .default('unified')
    .optional()
    .transform((val) => val || 'unified'),
  MAX_CONCURRENT_AGENTS: z
    .string()
    .optional()
    .default('5')
    .transform((val) => parseInt(val || '5', 10))
    .refine((val) => val >= 1 && val <= 10, {
      message: 'MAX_CONCURRENT_AGENTS must be between 1 and 10',
    }),
  ENABLE_REAL_TIME_SYNC: z
    .string()
    .optional()
    .default('true')
    .transform((val) => val === 'true'),
  SYNC_INTERVAL_MS: z
    .string()
    .optional()
    .default('30000')
    .transform((val) => parseInt(val || '30000', 10)),
});

/**
 * ITORO Bridge Plugin
 */
export const itoroBridgePlugin: Plugin = {
  name: 'plugin-itoro-bridge',
  description: 'Bridge between ElizaOS and ITORO multi-agent trading system',

  config: {
    // ITORO Webhook
    ITORO_WEBHOOK_URL: process.env.ITORO_WEBHOOK_URL,
    ITORO_WEBHOOK_SECRET: process.env.ITORO_WEBHOOK_SECRET,

    // Supabase Databases (using same env vars as working agents)
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE: process.env.SUPABASE_SERVICE_ROLE,

    // Local Database Paths
    PAPER_TRADING_DB_PATH: process.env.PAPER_TRADING_DB_PATH || 'multi-agents/itoro/ai_crypto_agents/data/paper_trading.db',
    LIVE_TRADING_DB_PATH: process.env.LIVE_TRADING_DB_PATH,

    // Redis Configuration
    REDIS_URL: process.env.REDIS_URL || 'redis://localhost:6379',
    REDIS_EVENT_STREAM_PREFIX: process.env.REDIS_EVENT_STREAM_PREFIX || 'core_signals',

    // Bridge Configuration
    BRIDGE_MODE: process.env.BRIDGE_MODE || 'unified',
    MAX_CONCURRENT_AGENTS: process.env.MAX_CONCURRENT_AGENTS || '5',
    ENABLE_REAL_TIME_SYNC: process.env.ENABLE_REAL_TIME_SYNC || 'true',
    SYNC_INTERVAL_MS: process.env.SYNC_INTERVAL_MS || '30000',
  },

  async init(config: Record<string, string>, runtime: IAgentRuntime): Promise<void> {
    logger.debug('Initializing ITORO Bridge Plugin');

    try {
      const validatedConfig = await bridgeConfigSchema.parseAsync(config);

      // Set environment variables
      for (const [key, value] of Object.entries(validatedConfig)) {
        if (value !== undefined && value !== null) {
          process.env[key] = String(value);
        }
      }

      // Start the bridge service
      await ITOROBridgeService.start(runtime);

      logger.info('ITORO Bridge Plugin initialized successfully');
    } catch (error) {
      if (error instanceof z.ZodError) {
        const errorMessages = error.errors.map((e) => `${e.path.join('.')}: ${e.message}`).join(', ');
        throw new Error(`Invalid bridge configuration: ${errorMessages}`);
      }
      logger.error('Failed to initialize ITORO Bridge Plugin:', error);
      throw error;
    }
  },

  services: [ITOROBridgeService],

  actions: [
    getPortfolioAction,
    tradingQueryAction,
    getTradeHistoryAction,
    getRiskMetricsAction
  ],

  routes: [
    {
      name: 'itoro-webhook',
      path: '/api/bridge/itoro',
      type: 'POST',
      handler: async (req: any, res: any, runtime: IAgentRuntime) => {
        try {
          const bridgeService = runtime.getService(ITOROBridgeService.serviceType);
          if (!bridgeService) {
            return res.status(503).json({ error: 'Bridge service not available' });
          }

          const payload = req.body;
          await (bridgeService as ITOROBridgeService).handleWebhook(payload);

          res.json({ status: 'processed', timestamp: new Date().toISOString() });
        } catch (error) {
          logger.error('Webhook processing error:', error);
          const errorMessage =
            error instanceof Error ? error.message : 'Unknown error occurred';
          res.status(500).json({ error: 'Processing failed', message: errorMessage });
        }
      },
    },
    {
      name: 'itoro-health',
      path: '/api/bridge/itoro/health',
      type: 'GET',
      handler: async (_req: any, res: any, runtime: IAgentRuntime) => {
        try {
          const bridgeService = runtime.getService(ITOROBridgeService.serviceType);
          if (!bridgeService) {
            return res.status(503).json({
              status: 'unhealthy',
              error: 'Bridge service not available',
            });
          }

          // Get health status if health monitor is available
          const agentManager = (bridgeService as ITOROBridgeService).getAgentManager();
          const activeAgents = agentManager.getActiveAgents();

          res.json({
            status: 'healthy',
            service: 'itoro-bridge',
            activeAgents: activeAgents.length,
            timestamp: new Date().toISOString(),
          });
        } catch (error) {
          logger.error('Health check error:', error);
          res.status(500).json({
            status: 'unhealthy',
            error: error instanceof Error ? error.message : 'Unknown error',
          });
        }
      },
    },
  ],

  events: {
    MESSAGE_RECEIVED: [
      async (params: { runtime: IAgentRuntime; message: any }) => {
        try {
          const bridgeService = params.runtime.getService(ITOROBridgeService.serviceType);
          if (bridgeService) {
            await (bridgeService as ITOROBridgeService).handleElizaMessage(params);
          }
        } catch (error) {
          logger.error('Error handling MESSAGE_RECEIVED event:', error);
        }
      },
    ],
  },
};

export default itoroBridgePlugin;

