# ITORO Agents Directory

This directory contains agent definitions and configurations for the ITORO crypto trading system.

## Master Agent

The **ITORO Master Agent** (Asset Manager) is the supreme orchestrator that monitors and optimizes the entire trading system.

### Key Responsibilities

1. **Performance Monitoring**: Track PnL progress toward monthly goals (e.g., 30%)
2. **System Health**: Monitor all trading agents and their effectiveness
3. **Data Quality**: Ensure data collection agents provide optimal information
4. **Config Optimization**: Auto-adjust data collection parameters and suggest trading config improvements
5. **Market Adaptation**: Adapt system behavior based on market conditions

### Adaptive Personality

The master agent switches between three personality modes:

- **AGGRESSIVE**: Bull markets, strong performance (>15% monthly PnL)
- **BALANCED**: Neutral markets, steady performance (default)
- **CONSERVATIVE**: Bear markets, underperformance (<-5% monthly PnL)

### Monitoring

The master agent runs every 30 minutes, monitoring system performance and making intelligent adjustments.

### Configuration Control

The master agent manages two categories of configs:

#### Auto-Adjust (Data Collection)
- Chart analysis timeframes and lookback periods
- Whale agent scoring weights and update intervals
- Sentiment analysis intervals
- Data collection thresholds

#### Suggest & Approve (Trading)
- Allocation limits and position sizing
- Risk management parameters
- SOL/USDC reserve targets
- Staking and DeFi allocation percentages

### Integration

The master agent is integrated into `main.py` and runs continuously in the background, making adjustments and generating suggestions based on system performance and market conditions.

### Dashboard

Access the master agent dashboard at `/master` to view:
- Current personality mode
- PnL progress toward goals
- Recent config adjustments
- Pending trading suggestions
- System health metrics

