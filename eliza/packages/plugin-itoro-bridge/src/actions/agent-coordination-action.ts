import type {
  Action,
  ActionResult,
  HandlerCallback,
  IAgentRuntime,
  Memory,
  State,
} from '@elizaos/core';
import { logger } from '@elizaos/core';
import { RedisEventStreamService, UnifiedTradingSignal } from '../services/redis-event-stream';

/**
 * Agent coordination command types
 */
type AgentCommand = 'START_TRADING' | 'STOP_TRADING' | 'PAUSE_TRADING' | 'RESUME_TRADING' | 'UPDATE_STRATEGY' | 'GET_STATUS' | 'EXECUTE_TRADE';

/**
 * Agent coordination message format
 */
interface AgentCoordinationMessage {
  target_agent: 'crypto' | 'stock' | 'forex' | 'all';
  command: AgentCommand;
  parameters?: Record<string, any>;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
}

/**
 * COORDINATE_AGENTS action for commanding trading agents
 */
export const coordinateAgentsAction: Action = {
  name: 'COORDINATE_AGENTS',
  similes: ['COMMAND_AGENTS', 'SEND_AGENT_COMMAND', 'CONTROL_TRADING_AGENTS', 'AGENT_COORDINATION'],
  description: 'Send commands to coordinate actions across trading agents',

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

      const redisStream = (bridgeService as any).redisStream as RedisEventStreamService;
      if (!redisStream) {
        throw new Error('Redis event stream not available');
      }

      const text = message.content.text?.toLowerCase() || '';

      // Parse the coordination command from user input
      const coordinationMessage = parseCoordinationCommand(text);

      if (!coordinationMessage) {
        return {
          success: false,
          error: new Error('Could not parse coordination command from message'),
        };
      }

      // Send coordination signal via Redis event stream
      const signal: UnifiedTradingSignal = {
        signal_id: `coord_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        agent_type: coordinationMessage.target_agent === 'all' ? 'crypto' : coordinationMessage.target_agent,
        signal_type: 'info', // Coordination commands are info signals
        symbol: '*', // Wildcard for all symbols
        confidence: 1.0,
        timestamp: new Date().toISOString(),
        metadata: {
          coordination_command: coordinationMessage.command,
          parameters: coordinationMessage.parameters,
          priority: coordinationMessage.priority || 'medium',
          source: 'eliza_coordination',
          target_agents: coordinationMessage.target_agent
        }
      };

      // If targeting all agents, send to multiple streams
      if (coordinationMessage.target_agent === 'all') {
        const streams = ['crypto', 'stock', 'forex'];
        for (const agentType of streams) {
          const agentSignal = { ...signal, agent_type: agentType as UnifiedTradingSignal['agent_type'] };
          await redisStream.publishTradingSignal(agentSignal);
        }
      } else {
        await redisStream.publishTradingSignal(signal);
      }

      const response = formatCoordinationResponse(coordinationMessage);

      if (callback) {
        await callback({
          text: response,
          actions: ['COORDINATE_AGENTS'],
          source: message.content.source,
        });
      }

      return {
        text: response,
        success: true,
        data: {
          actions: ['COORDINATE_AGENTS'],
          coordination_message: coordinationMessage,
          signal_id: signal.signal_id
        },
      };
    } catch (error) {
      logger.error('Agent coordination action failed:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to coordinate agents';

      if (callback) {
        await callback({
          text: `Sorry, I couldn't coordinate the agents: ${errorMessage}`,
          actions: ['COORDINATE_AGENTS'],
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
          text: 'Tell all crypto agents to start trading',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Sending start trading command to all crypto agents...',
        },
      },
    ],
    [
      {
        name: '{{user1}}',
        content: {
          text: 'Pause stock trading temporarily',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Pausing all stock trading agents...',
        },
      },
    ],
  ],
};

/**
 * Parse coordination command from natural language
 */
function parseCoordinationCommand(text: string): AgentCoordinationMessage | null {
  const lowerText = text.toLowerCase();

  // Determine target agent type
  let targetAgent: 'crypto' | 'stock' | 'forex' | 'all' = 'all';
  if (lowerText.includes('crypto')) targetAgent = 'crypto';
  else if (lowerText.includes('stock')) targetAgent = 'stock';
  else if (lowerText.includes('forex') || lowerText.includes('currency')) targetAgent = 'forex';

  // Determine command type
  let command: AgentCommand | null = null;
  let parameters: Record<string, any> = {};

  if (lowerText.includes('start') && lowerText.includes('trad')) {
    command = 'START_TRADING';
  } else if (lowerText.includes('stop') && lowerText.includes('trad')) {
    command = 'STOP_TRADING';
  } else if (lowerText.includes('pause')) {
    command = 'PAUSE_TRADING';
  } else if (lowerText.includes('resume')) {
    command = 'RESUME_TRADING';
  } else if (lowerText.includes('update') && lowerText.includes('strategy')) {
    command = 'UPDATE_STRATEGY';
  } else if (lowerText.includes('status')) {
    command = 'GET_STATUS';
  } else if (lowerText.includes('execute') || lowerText.includes('trade')) {
    command = 'EXECUTE_TRADE';
    // Try to extract trade parameters
    const symbolMatch = text.match(/([A-Z]{2,5})/);
    if (symbolMatch) {
      parameters.symbol = symbolMatch[1];
    }
  }

  if (!command) return null;

  return {
    target_agent: targetAgent,
    command,
    parameters,
    priority: lowerText.includes('urgent') ? 'urgent' : 'medium'
  };
}

/**
 * Format coordination response
 */
function formatCoordinationResponse(message: AgentCoordinationMessage): string {
  const agentTypeText = message.target_agent === 'all' ? 'all trading agents' : `${message.target_agent} agents`;

  let commandText = '';
  switch (message.command) {
    case 'START_TRADING':
      commandText = '🚀 Starting trading operations';
      break;
    case 'STOP_TRADING':
      commandText = '⏹️ Stopping all trading operations';
      break;
    case 'PAUSE_TRADING':
      commandText = '⏸️ Pausing trading operations';
      break;
    case 'RESUME_TRADING':
      commandText = '▶️ Resuming trading operations';
      break;
    case 'UPDATE_STRATEGY':
      commandText = '📊 Updating trading strategy';
      break;
    case 'GET_STATUS':
      commandText = '📊 Requesting status update';
      break;
    case 'EXECUTE_TRADE':
      commandText = `💰 Executing trade${message.parameters?.symbol ? ` for ${message.parameters.symbol}` : ''}`;
      break;
    default:
      commandText = `📢 Sending ${message.command} command`;
  }

  return `${commandText} for ${agentTypeText}\n\nCommand sent with ${message.priority} priority. Agents will respond with confirmation.`;
}
