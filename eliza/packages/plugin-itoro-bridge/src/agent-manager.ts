import type { IAgentRuntime, Character } from '@elizaos/core';
import { AgentRuntime, logger } from '@elizaos/core';
import { EventBridge } from './communication/event-bridge';
import { MessageRouter } from './communication/message-router';

/**
 * Agent manager for spawning and managing multiple agent runtime instances
 */
export class AgentManager {
  private runtime: IAgentRuntime;
  private eventBridge: EventBridge;
  private messageRouter: MessageRouter;
  private activeAgents: Map<string, IAgentRuntime> = new Map();
  private agentLastUsed: Map<string, number> = new Map(); // For LRU eviction
  private maxConcurrentAgents: number;

  constructor(runtime: IAgentRuntime, eventBridge: EventBridge) {
    this.runtime = runtime;
    this.eventBridge = eventBridge;
    this.messageRouter = new MessageRouter();
    this.maxConcurrentAgents = parseInt(
      process.env.MAX_CONCURRENT_AGENTS || '5',
      10
    );
  }

  /**
   * Initialize the agent manager
   */
  async initialize(): Promise<void> {
    logger.info('Agent Manager initialized');
  }

  /**
   * Spawn a new agent runtime instance
   */
  async spawnAgent(
    agentId: string,
    characterConfig: Character
  ): Promise<IAgentRuntime> {
    if (this.activeAgents.has(agentId)) {
      logger.warn(`Agent ${agentId} already active`);
      return this.activeAgents.get(agentId)!;
    }

    // Check if we've reached the maximum concurrent agents
    if (this.activeAgents.size >= this.maxConcurrentAgents) {
      await this.evictLeastRecentlyUsedAgent();
    }

    try {
      // Create new runtime instance for the agent
      const agentRuntime = new AgentRuntime({
        character: characterConfig,
        plugins: [], // Agent-specific plugins can be added here
        settings: {
          ...this.runtime.settings,
          agentId,
        },
        fetch: this.runtime.fetch,
      });

      // Initialize the runtime
      await agentRuntime.initialize();

      // Register with event bridge for communication
      await this.eventBridge.registerAgent(agentId, agentRuntime);

      // Store the agent
      this.activeAgents.set(agentId, agentRuntime);
      this.agentLastUsed.set(agentId, Date.now());

      logger.info(`Spawned agent: ${agentId}`);
      return agentRuntime;
    } catch (error) {
      logger.error(`Failed to spawn agent ${agentId}:`, error);
      throw error;
    }
  }

  /**
   * Spawn an agent on demand based on agent type
   */
  async spawnAgentOnDemand(
    agentType: string,
    context: any
  ): Promise<IAgentRuntime> {
    // Check if agent type is supported
    if (!this.isSupportedAgentType(agentType)) {
      throw new Error(`Agent type ${agentType} not supported`);
    }

    // Check concurrent agent limits
    if (this.activeAgents.size >= this.maxConcurrentAgents) {
      await this.evictLeastRecentlyUsedAgent();
    }

    // Generate unique agent ID
    const agentId = `${agentType}_${Date.now()}_${Math.random()
      .toString(36)
      .substr(2, 9)}`;

    // Import agent factory to create character
    const { AgentFactory } = await import('./characters/agent-factory');
    const character = AgentFactory.createCharacter(agentType, context);

    // Spawn the agent
    return await this.spawnAgent(agentId, character);
  }

  /**
   * Despawn an agent
   */
  async despawnAgent(agentId: string): Promise<void> {
    const agent = this.activeAgents.get(agentId);
    if (agent) {
      await this.eventBridge.unregisterAgent(agentId);
      await agent.stop();
      this.activeAgents.delete(agentId);
      this.agentLastUsed.delete(agentId);
      logger.info(`Despawned agent: ${agentId}`);
    }
  }

  /**
   * Get an agent by ID
   */
  getAgent(agentId: string): IAgentRuntime | undefined {
    // Update last used timestamp
    if (this.activeAgents.has(agentId)) {
      this.agentLastUsed.set(agentId, Date.now());
    }
    return this.activeAgents.get(agentId);
  }

  /**
   * Get all active agent IDs
   */
  getActiveAgents(): string[] {
    return Array.from(this.activeAgents.keys());
  }

  /**
   * Check if agent type is supported
   */
  private isSupportedAgentType(agentType: string): boolean {
    const supportedAgents = [
      'itoro',
      'ikon',
      'mansa',
      'niani',
      'simbon',
      'xirsi',
      'ginikandu',
    ];
    return supportedAgents.includes(agentType.toLowerCase());
  }

  /**
   * Evict the least recently used agent
   */
  private async evictLeastRecentlyUsedAgent(): Promise<void> {
    if (this.agentLastUsed.size === 0) {
      return;
    }

    // Find the least recently used agent
    let lruAgentId: string | null = null;
    let lruTime = Infinity;

    for (const [agentId, lastUsed] of this.agentLastUsed) {
      if (lastUsed < lruTime) {
        lruTime = lastUsed;
        lruAgentId = agentId;
      }
    }

    if (lruAgentId) {
      logger.info(`Evicting least recently used agent: ${lruAgentId}`);
      await this.despawnAgent(lruAgentId);
    }
  }

  /**
   * Cleanup all agents
   */
  async cleanup(): Promise<void> {
    const agentIds = Array.from(this.activeAgents.keys());
    for (const agentId of agentIds) {
      await this.despawnAgent(agentId);
    }
    this.messageRouter.clear();
    logger.info('Agent Manager cleaned up');
  }

  /**
   * Get message router
   */
  getMessageRouter(): MessageRouter {
    return this.messageRouter;
  }
}

