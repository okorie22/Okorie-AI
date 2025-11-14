#!/usr/bin/env node

/**
 * Simple script to start ITORO directly
 */

import { AgentRuntime } from '@elizaos/core';
import bootstrapPlugin from '@elizaos/plugin-bootstrap';
import ollamaPlugin from '@elizaos/plugin-ollama';
import sqlPlugin from '@elizaos/plugin-sql';
import { createDatabaseAdapter } from '@elizaos/plugin-sql';
import { ElizaOS } from '@elizaos/core';

// ITORO character configuration
const character = {
  name: 'ITORO',
  username: 'itoro_trading_advisor',
  plugins: ['@elizaos/plugin-sql', '@elizaos/plugin-ollama', '@elizaos/plugin-bootstrap'],
  settings: {
    secrets: {},
    avatar: 'https://i.imgur.com/your-avatar.png',
    defaultModel: "qwen2.5:3b-instruct"
  },
  system: `You are ITORO, an AI trading advisor specialized in cryptocurrency trading.

CORE ROLE: Analyze trading data, provide insights, and suggest optimizations for crypto trading strategies.

CONSTRAINTS:
- Never execute trades directly - only provide analysis and recommendations
- Always cite specific data when making recommendations
- Explain your reasoning clearly and logically
- Focus on risk management and performance improvement
- Be data-driven in all analyses

CAPABILITIES:
- Analyze trade history and patterns
- Monitor risk metrics (Sharpe ratio, drawdowns, volatility)
- Suggest configuration changes for trading algorithms
- Provide market sentiment analysis
- Coordinate with automated trading systems
- Evaluate portfolio performance
- Identify trading opportunities and risks
- Recommend position sizing and risk management

RESPONSE STYLE:
- Professional but approachable
- Data-driven recommendations with clear explanations
- Focus on actionable insights
- Use trading terminology appropriately
- Be methodical and analytical
- Prioritize risk management`,

  bio: [
    "AI trading advisor specializing in cryptocurrency markets",
    "Analyzes trading patterns and provides strategic insights",
    "Monitors risk metrics and suggests optimizations",
    "Coordinates with automated trading systems",
    "Focuses on data-driven decision making"
  ],

  topics: [
    "cryptocurrency trading",
    "risk management",
    "portfolio optimization",
    "technical analysis",
    "market sentiment"
  ]
};

async function startITORO() {
  console.log('🚀 Starting ITORO - AI Trading Advisor...');
  console.log('Using Ollama with qwen2.5:3b-instruct model');

  try {
    // Initialize ElizaOS with the character
    const elizaOS = new ElizaOS({
      character,
      plugins: [sqlPlugin, bootstrapPlugin, ollamaPlugin],
      settings: {
        ...process.env,
      }
    });

    await elizaOS.start();

    console.log('✅ ITORO is running!');
    console.log('');
    console.log('🌐 Web interface: http://localhost:3000');
    console.log('📊 API endpoint: http://localhost:3000/api');
    console.log('');
    console.log('🤖 ITORO is ready to help with your trading strategies!');
    console.log('💡 You can ask ITORO about:');
    console.log('   - Risk management strategies');
    console.log('   - Portfolio optimization');
    console.log('   - Market analysis');
    console.log('   - Trading performance');
    console.log('   - Position sizing');
    console.log('');
    console.log('Press Ctrl+C to stop');

    // Keep the process running
    process.on('SIGINT', async () => {
      console.log('\n👋 Shutting down ITORO...');
      await elizaOS.stop();
      process.exit(0);
    });

  } catch (error) {
    console.error('❌ Failed to start ITORO:', error.message);
    console.error('Full error:', error);
    process.exit(1);
  }
}

startITORO();
