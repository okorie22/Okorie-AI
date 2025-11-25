import { logger } from '@elizaos/core';
import { ITOROMessage } from './webhook-client';

/**
 * Message router for directing messages to appropriate agents
 */
export class MessageRouter {
  private agentPriorities: Map<string, number> = new Map();
  private correlationMap: Map<string, string> = new Map(); // correlationId -> agentId

  /**
   * Route a message to the appropriate agent based on context
   */
  routeMessage(message: ITOROMessage, availableAgents: string[]): string | null {
    // If message specifies an agent_id, use it
    if (message.agent_id && availableAgents.includes(message.agent_id)) {
      return message.agent_id;
    }

    // Check if this is a response to a previous message
    if (message.correlation_id) {
      const agentId = this.correlationMap.get(message.correlation_id);
      if (agentId && availableAgents.includes(agentId)) {
        return agentId;
      }
    }

    // Route based on message type and priority
    if (message.message_type === 'query') {
      // For queries, try to find the most appropriate agent
      // Default to 'itoro' if available
      if (availableAgents.includes('itoro')) {
        return 'itoro';
      }
      // Otherwise, return the first available agent
      return availableAgents.length > 0 ? availableAgents[0] : null;
    }

    // For other message types, use context metadata
    const contextAgent = message.content.metadata?.context?.target_agent;
    if (contextAgent && availableAgents.includes(contextAgent)) {
      return contextAgent;
    }

    return null;
  }

  /**
   * Register a correlation ID with an agent
   */
  registerCorrelation(correlationId: string, agentId: string): void {
    this.correlationMap.set(correlationId, agentId);
    // Clean up old correlations after 1 hour
    setTimeout(() => {
      this.correlationMap.delete(correlationId);
    }, 3600000);
  }

  /**
   * Get agent ID for a correlation ID
   */
  getAgentForCorrelation(correlationId: string): string | null {
    return this.correlationMap.get(correlationId) || null;
  }

  /**
   * Set agent priority (higher number = higher priority)
   */
  setAgentPriority(agentId: string, priority: number): void {
    this.agentPriorities.set(agentId, priority);
  }

  /**
   * Get agent priority
   */
  getAgentPriority(agentId: string): number {
    return this.agentPriorities.get(agentId) || 0;
  }

  /**
   * Clear all routing data
   */
  clear(): void {
    this.correlationMap.clear();
    this.agentPriorities.clear();
  }
}

