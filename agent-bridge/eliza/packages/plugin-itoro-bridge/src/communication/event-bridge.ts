import type { IAgentRuntime, Memory } from '@elizaos/core';
import { EventType, logger, createMessageMemory, stringToUuid } from '@elizaos/core';
import { WebhookClient, ITOROMessage } from './webhook-client';
import crypto from 'node:crypto';

/**
 * Event bridge for bidirectional communication between ElizaOS and ITORO
 */
export class EventBridge {
  private runtime: IAgentRuntime;
  private webhookClient: WebhookClient;
  private agentSubscriptions: Map<string, IAgentRuntime> = new Map();
  private messageHandlers: Map<string, (message: Memory) => Promise<void>> = new Map();

  constructor(runtime: IAgentRuntime, webhookClient: WebhookClient) {
    this.runtime = runtime;
    this.webhookClient = webhookClient;
  }

  /**
   * Register an agent runtime with the event bridge
   */
  async registerAgent(agentId: string, agentRuntime: IAgentRuntime): Promise<void> {
    if (this.agentSubscriptions.has(agentId)) {
      logger.warn(`Agent ${agentId} already registered with event bridge`);
      return;
    }

    // Store the agent runtime
    this.agentSubscriptions.set(agentId, agentRuntime);

    // Create message handler for this agent
    const messageHandler = async (message: Memory) => {
      await this.handleAgentMessage(agentId, message);
    };

    this.messageHandlers.set(agentId, messageHandler);

    // Subscribe to agent's message events
    // Note: This assumes the runtime has an event emitter pattern
    // The actual implementation may vary based on ElizaOS runtime API
    logger.debug(`Registered agent ${agentId} with event bridge`);
  }

  /**
   * Unregister an agent from the event bridge
   */
  async unregisterAgent(agentId: string): Promise<void> {
    this.agentSubscriptions.delete(agentId);
    this.messageHandlers.delete(agentId);
    logger.debug(`Unregistered agent ${agentId} from event bridge`);
  }

  /**
   * Handle message from an ElizaOS agent and forward to ITORO
   */
  private async handleAgentMessage(agentId: string, message: Memory): Promise<void> {
    try {
      // Only forward messages that are from users (not from the agent itself)
      if (message.content.text && message.entityId) {
        // Convert ElizaOS Memory to ITORO message format
        const itoroMessage: ITOROMessage = {
          agent_id: agentId,
          message_type: 'query',
          content: {
            text: message.content.text,
            metadata: {
              priority: 'medium',
              context: {
                source: message.content.source || 'eliza',
                channelType: message.content.channelType,
              },
              source_agent: 'eliza-bridge',
              user_id: message.entityId,
              room_id: message.roomId,
              eliza_message_id: message.id,
            },
          },
          timestamp: message.createdAt
            ? new Date(message.createdAt).toISOString()
            : new Date().toISOString(),
          correlation_id: message.id || crypto.randomUUID(),
        };

        // Send to ITORO via webhook
        await this.webhookClient.sendMessage(itoroMessage);
        logger.debug(`Forwarded message from agent ${agentId} to ITORO`);
      }
    } catch (error) {
      logger.error(`Failed to forward message from agent ${agentId}:`, error);
    }
  }

  /**
   * Handle incoming message from ITORO and forward to appropriate ElizaOS agent
   */
  async handleITOROMessage(itoroMessage: ITOROMessage): Promise<void> {
    try {
      const agentRuntime = this.agentSubscriptions.get(itoroMessage.agent_id);
      if (!agentRuntime) {
        logger.warn(`No active runtime for agent ${itoroMessage.agent_id}`);
        return;
      }

      // Convert ITORO message to ElizaOS Memory format
      // Note: createMessageMemory requires roomId, so we need to use stringToUuid or provide a valid UUID
      const roomId = itoroMessage.content.metadata?.room_id
        ? stringToUuid(itoroMessage.content.metadata.room_id)
        : stringToUuid('default-room');
      const entityId = itoroMessage.content.metadata?.user_id
        ? stringToUuid(itoroMessage.content.metadata.user_id)
        : stringToUuid('system');

      const elizaMessage: Memory = createMessageMemory({
        id: itoroMessage.correlation_id ? stringToUuid(itoroMessage.correlation_id) : undefined,
        entityId,
        roomId,
        content: {
          text: itoroMessage.content.text,
          source: 'itoro-bridge',
          channelType: itoroMessage.content.metadata?.context?.channelType,
        },
      });

      // Emit message to ElizaOS runtime
      await agentRuntime.emitEvent(EventType.MESSAGE_RECEIVED, {
        runtime: agentRuntime,
        message: elizaMessage,
      });

      // Handle response correlation if this is a response to a query
      if (itoroMessage.message_type === 'response' && itoroMessage.correlation_id) {
        this.webhookClient.handleResponse(itoroMessage.correlation_id, itoroMessage);
      }

      logger.debug(`Forwarded ITORO message to agent ${itoroMessage.agent_id}`);
    } catch (error) {
      logger.error('Failed to handle ITORO message:', error);
    }
  }

  /**
   * Get agent runtime by ID
   */
  getAgentRuntime(agentId: string): IAgentRuntime | null {
    return this.agentSubscriptions.get(agentId) || null;
  }

  /**
   * Get all registered agent IDs
   */
  getRegisteredAgents(): string[] {
    return Array.from(this.agentSubscriptions.keys());
  }
}

