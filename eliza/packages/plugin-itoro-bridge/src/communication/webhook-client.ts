import { logger } from '@elizaos/core';
import crypto from 'node:crypto';

/**
 * Configuration for the webhook client
 */
export interface WebhookConfig {
  baseUrl: string;
  secret: string;
  timeout?: number;
}

/**
 * Message format for communication with ITORO
 */
export interface ITOROMessage {
  agent_id: string;
  message_type: 'query' | 'response' | 'data_update' | 'command';
  content: {
    text: string;
    metadata: {
      priority: 'low' | 'medium' | 'high' | 'urgent';
      context: Record<string, any>;
      source_agent?: string;
      user_id?: string;
      room_id?: string;
      eliza_message_id?: string;
    };
  };
  timestamp: string;
  correlation_id: string;
}

/**
 * Webhook client for sending messages to ITORO webhook server
 */
export class WebhookClient {
  private config: WebhookConfig;
  private pendingResponses: Map<string, {
    resolve: (value: any) => void;
    reject: (error: Error) => void;
    timeout: NodeJS.Timeout;
  }> = new Map();

  constructor(config: WebhookConfig) {
    this.config = {
      timeout: 30000,
      ...config,
    };
  }

  /**
   * Send a message to ITORO webhook server
   */
  async sendMessage(message: ITOROMessage): Promise<any> {
    const payload = JSON.stringify(message);
    const signature = this.generateSignature(payload);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

      const response = await fetch(`${this.config.baseUrl}/api/signals`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Signature': signature,
          'X-Topic': 'eliza-bridge',
        },
        body: payload,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        logger.error('Webhook request timed out');
        throw new Error('Request timeout');
      }
      logger.error('Webhook send failed:', error);
      throw error;
    }
  }

  /**
   * Send a query to ITORO and wait for response
   */
  async sendQuery(
    agentId: string,
    query: string,
    context?: any
  ): Promise<ITOROMessage> {
    const correlationId = crypto.randomUUID();
    const message: ITOROMessage = {
      agent_id: agentId,
      message_type: 'query',
      content: {
        text: query,
        metadata: {
          priority: context?.priority || 'medium',
          context: context || {},
          source_agent: 'eliza-bridge',
          user_id: context?.user_id,
          room_id: context?.room_id,
          eliza_message_id: context?.eliza_message_id,
        },
      },
      timestamp: new Date().toISOString(),
      correlation_id: correlationId,
    };

    await this.sendMessage(message);
    return message;
  }

  /**
   * Wait for a response with a specific correlation ID
   */
  async waitForResponse(
    correlationId: string,
    timeout: number = 30000
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        this.pendingResponses.delete(correlationId);
        reject(new Error(`Response timeout for correlation ID: ${correlationId}`));
      }, timeout);

      this.pendingResponses.set(correlationId, {
        resolve: (value) => {
          clearTimeout(timeoutId);
          this.pendingResponses.delete(correlationId);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timeoutId);
          this.pendingResponses.delete(correlationId);
          reject(error);
        },
        timeout: timeoutId,
      });
    });
  }

  /**
   * Handle incoming response message
   */
  handleResponse(correlationId: string, data: any): void {
    const pending = this.pendingResponses.get(correlationId);
    if (pending) {
      pending.resolve(data);
    } else {
      logger.warn(`No pending request found for correlation ID: ${correlationId}`);
    }
  }

  /**
   * Generate HMAC-SHA256 signature for webhook authentication
   */
  private generateSignature(payload: string): string {
    return crypto
      .createHmac('sha256', this.config.secret)
      .update(payload)
      .digest('hex');
  }

  /**
   * Disconnect and cleanup
   */
  async disconnect(): Promise<void> {
    // Clear all pending responses
    for (const [correlationId, pending] of this.pendingResponses) {
      clearTimeout(pending.timeout);
      pending.reject(new Error('Client disconnected'));
    }
    this.pendingResponses.clear();
  }
}

