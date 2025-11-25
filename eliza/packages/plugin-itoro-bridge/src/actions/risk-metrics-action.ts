import type {
  Action,
  ActionResult,
  HandlerCallback,
  IAgentRuntime,
  Memory,
  State,
} from '@elizaos/core';
import { logger } from '@elizaos/core';
import { UnifiedDataAggregator, UnifiedRiskMetrics } from '../services/unified-data-aggregator';

/**
 * Format risk metrics response
 */
function formatRiskMetricsResponse(riskMetrics: UnifiedRiskMetrics): string {
  let response = `⚠️ Risk Analysis Report:\n\n`;

  // Risk level assessment
  const maxDrawdownPercent = (riskMetrics.max_drawdown * 100).toFixed(2);
  let riskLevel = 'Low';
  let riskEmoji = '🟢';
  let riskDescription = 'Your portfolio is well within safe risk parameters.';

  if (riskMetrics.max_drawdown > 0.20) {
    riskLevel = 'High';
    riskEmoji = '🔴';
    riskDescription = 'High risk detected. Consider reducing position sizes or implementing stricter risk controls.';
  } else if (riskMetrics.max_drawdown > 0.10) {
    riskLevel = 'Moderate';
    riskEmoji = '🟡';
    riskDescription = 'Moderate risk level. Monitor closely and consider position adjustments.';
  }

  response += `${riskEmoji} Overall Risk Level: ${riskLevel}\n`;
  response += `${riskDescription}\n\n`;

  response += `📊 Key Risk Metrics:\n`;
  response += `• Maximum Drawdown: ${maxDrawdownPercent}%\n`;
  response += `• Sharpe Ratio: ${riskMetrics.sharpe_ratio.toFixed(2)}\n`;
  response += `• Portfolio Volatility: ${(riskMetrics.volatility * 100).toFixed(2)}%\n`;
  response += `• Value at Risk (VaR): ${(riskMetrics.value_at_risk * 100).toFixed(2)}%\n`;
  response += `• Expected Shortfall: ${(riskMetrics.expected_shortfall * 100).toFixed(2)}%\n`;
  response += `• Portfolio Beta: ${riskMetrics.beta.toFixed(2)}\n\n`;

  // Risk interpretation
  response += `💡 Risk Interpretation:\n`;

  if (riskMetrics.sharpe_ratio > 1.5) {
    response += `• Sharpe Ratio indicates good risk-adjusted returns\n`;
  } else if (riskMetrics.sharpe_ratio > 0.5) {
    response += `• Sharpe Ratio is acceptable but could be improved\n`;
  } else {
    response += `• Sharpe Ratio suggests poor risk-adjusted returns\n`;
  }

  if (riskMetrics.volatility < 0.15) {
    response += `• Portfolio volatility is relatively stable\n`;
  } else if (riskMetrics.volatility < 0.25) {
    response += `• Moderate volatility - normal market fluctuations\n`;
  } else {
    response += `• High volatility detected - increased risk of large swings\n`;
  }

  if (riskMetrics.beta < 0.8) {
    response += `• Portfolio is defensive (less sensitive to market movements)\n`;
  } else if (riskMetrics.beta > 1.2) {
    response += `• Portfolio is aggressive (more sensitive to market movements)\n`;
  } else {
    response += `• Portfolio tracks market movements closely\n`;
  }

  // Recommendations
  response += `\n🎯 Recommendations:\n`;
  if (riskMetrics.max_drawdown > 0.15) {
    response += `• Consider implementing stop-loss orders\n`;
    response += `• Diversify across more uncorrelated assets\n`;
  }

  if (riskMetrics.volatility > 0.20) {
    response += `• Consider reducing position sizes\n`;
    response += `• Implement position sizing based on volatility\n`;
  }

  if (riskMetrics.sharpe_ratio < 0.5) {
    response += `• Review trading strategy effectiveness\n`;
    response += `• Consider adjusting risk-reward ratios\n`;
  }

  if (riskMetrics.sources && riskMetrics.sources.length > 0) {
    response += `\n📋 Data Sources: ${riskMetrics.sources.join(', ')}`;
  }

  return response;
}

/**
 * GET_RISK_METRICS action for retrieving risk analysis
 */
export const getRiskMetricsAction: Action = {
  name: 'GET_RISK_METRICS',
  similes: ['RISK_ANALYSIS', 'SHOW_RISK', 'PORTFOLIO_RISK', 'RISK_METRICS'],
  description: 'Retrieve comprehensive risk analysis and metrics',

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

      const dataAggregator = (bridgeService as any).dataAggregator as UnifiedDataAggregator;
      if (!dataAggregator) {
        throw new Error('Data aggregator not available');
      }

      // Get unified risk metrics
      const riskMetrics = await dataAggregator.getUnifiedRiskMetrics(message.entityId);

      const formattedResponse = formatRiskMetricsResponse(riskMetrics);

      if (callback) {
        await callback({
          text: formattedResponse,
          actions: ['GET_RISK_METRICS'],
          source: message.content.source,
        });
      }

      return {
        text: formattedResponse,
        success: true,
        data: {
          actions: ['GET_RISK_METRICS'],
          risk_metrics: riskMetrics,
        },
      };
    } catch (error) {
      logger.error('Risk metrics action failed:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to retrieve risk metrics';

      if (callback) {
        await callback({
          text: `Sorry, I couldn't retrieve your risk metrics: ${errorMessage}`,
          actions: ['GET_RISK_METRICS'],
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
          text: 'Show me my portfolio risk',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Analyzing your portfolio risk metrics...',
        },
      },
    ],
    [
      {
        name: '{{user1}}',
        content: {
          text: 'How risky is my portfolio?',
        },
      },
      {
        name: 'ITORO',
        content: {
          text: 'Getting your risk analysis...',
        },
      },
    ],
  ],
};
