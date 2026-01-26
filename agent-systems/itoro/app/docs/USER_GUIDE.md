# AI Trading Assistant User Guide

## Overview

The AI Trading Assistant is a comprehensive crypto trading system that collects market data, detects chart patterns, and provides AI-powered analysis and recommendations.

## System Architecture

The system consists of two main services:

1. **Data Collection Service** (`data.py`) - Collects Open Interest, Funding Rates, and Chart Analysis data
2. **Pattern Detection Strategy** (`pattern_service.py`) - Detects candlestick patterns and provides AI analysis

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Redis server (for real-time data updates)
- Required Python packages:
  ```bash
  pip install PySide6 redis pandas pyarrow talib ccxt discord.py python-dotenv
  ```

### Configuration

1. Copy `config-example.env` to `.env`
2. Configure your API keys and settings:
   ```env
   # AI Analysis
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   
   # Discord Notifications
   DISCORD_BOT_TOKEN=your_discord_bot_token
   
   # Trading Configuration
   TRADING_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT
   SCAN_INTERVAL=300
   TIMEFRAME=1d
   ```

## Starting the Application

### Method 1: Using the UI

1. Run the main application:
   ```bash
   python src/trading_ui_connected.py
   ```

2. The UI will open with the following components:
   - **Dashboard Tab**: Shows data collection status cards and AI analysis console
   - **Configuration Tab**: Configure data sources and system settings
   - **Menu Bar**: Control data collection and strategy execution

### Method 2: Running Services Independently

#### Start Data Collection

```bash
python src/data.py
```

This starts the data collection agents for OI, Funding, and Chart Analysis.

#### Start Pattern Detection

```bash
python src/pattern_recognition.py
```

This starts the pattern detection strategy.

## Using the UI

### Dashboard Tab

#### Data Status Cards

Three cards display real-time data collection status:

1. **Open Interest** - Shows OI data from exchanges
2. **Funding Rates** - Displays perpetual futures funding rates
3. **Chart Analysis** - Technical analysis updates

#### AI Analysis Console

- Displays detected patterns with AI analysis
- Shows recommendations for each pattern
- Auto-scrolls to latest analysis
- Keeps history of last 50 patterns

#### System Logs

Clean console showing:
- System status messages
- Data collection updates
- Strategy execution alerts
- Error messages

### Menu Operations

#### File Menu

- **Exit**: Close the application

#### Data Collection Menu

- **Start Data Collection**: Launches data.py service
- **Stop Data Collection**: Stops data collection service

#### Strategy Menu

- **Run Pattern Detection**: Starts pattern detection strategy
- **Stop Strategy**: Stops active strategy

### Configuration Tab

#### Data Collection Sources

Select which data sources to monitor:
- ☑ Open Interest Data
- ☑ Funding Rates
- ☑ Chart Analysis

Click "Apply Data Sources" to save settings.

#### System Configuration

Edit configuration values:
- API keys
- Trading symbols
- Scan intervals
- Timeframes

## Features

### Pattern Detection

The system detects 5 candlestick patterns:
- Hammer / Inverted Hammer (Bullish)
- Shooting Star / Hanging Man (Bearish)
- Doji (Indecision)
- Bullish / Bearish Engulfing

### AI Analysis

Each detected pattern receives AI-powered analysis including:
- Pattern significance
- Market context (OI, Funding, Chart trends)
- Trading recommendations
- Confidence levels

### Alert System

Alerts are sent via:
- Discord Private DMs
- Desktop Notifications (if enabled)
- UI Console Display

### Alert Cooldown

The system prevents duplicate alerts using a 24-hour cooldown period per symbol/pattern combination.

## Data Flow

```
┌─────────────────┐
│   data.py       │
│  (Coordinator)  │
└────────┬────────┘
         │
    ┌────┼────┐
    │    │    │
┌───▼┐ ┌─▼──┐ ┌▼────┐
│ OI │ │Fund│ │Chart│
└──┬─┘ └──┬─┘ └─┬───┘
   │      │     │
   └──────┼─────┘
          │
   ┌──────▼────────┐
   │ Redis / Files │
   └──────┬────────┘
          │
   ┌──────▼────────────┐
   │ pattern_service   │
   │ (Strategy)        │
   └──────┬────────────┘
          │
   ┌──────▼─────────┐
   │  UI Console    │
   │ + Notifications│
   └────────────────┘
```

## Troubleshooting

### Redis Connection Errors

If you see "Redis not available" warnings:
1. Install Redis: [Download Redis](https://redis.io/download)
2. Start Redis server: `redis-server`
3. Restart the application

### Module Not Found Errors

If you get import errors:
```bash
# Install missing packages
pip install -r requirements.txt

# For TA-Lib specifically
conda install -c conda-forge ta-lib
```

### No Data Updates

If status cards show "Never":
1. Ensure data.py is running
2. Check Redis is running
3. Verify network connectivity
4. Check console logs for errors

### Pattern Detection Not Running

If patterns aren't being detected:
1. Check Strategy menu shows "Running"
2. Verify .env file has correct API keys
3. Check console logs for scan updates
4. Ensure symbols are valid

## Status Bar Indicators

Bottom status bar shows:
- **Data Collection**: Idle / Running
- **Strategy**: Idle / Pattern Detection Running

## Best Practices

### For Optimal Performance

1. **Start Services in Order**:
   - Start Redis first
   - Start Data Collection
   - Start Pattern Detection

2. **Monitor Resource Usage**:
   - Data collection updates every 2-4 hours
   - Pattern detection scans every 5 minutes (configurable)
   - Keep Redis memory under 512MB

3. **Configure Alerts**:
   - Enable Discord for private notifications
   - Disable desktop notifications if running headless
   - Set appropriate alert cooldown (24h recommended)

### Security

- Never commit `.env` files to version control
- Keep API keys secure
- Use read-only API keys when possible
- Regularly rotate Discord bot tokens

## Support

### Logs

Check logs for debugging:
- UI Console: Real-time system messages
- Terminal Output: Detailed execution logs
- Pattern Database: `patterns.db` (SQLite)

### Common Issues

1. **"Pattern already alerted"**: Normal - cooldown period active
2. **"No market context"**: Data collection not running
3. **"Failed to fetch data"**: API rate limit or connectivity issue

## Advanced Usage

### Custom Strategies

The system supports multiple strategies through the strategy runner architecture. To add a new strategy:

1. Create strategy class implementing the same interface as PatternService
2. Add strategy to StrategyRunner
3. Update UI menu with new strategy option

### Data Export

Access stored data:
```python
import sqlite3
conn = sqlite3.connect('patterns.db')
df = pd.read_sql_query("SELECT * FROM patterns", conn)
```

### Discord Bot Commands

Users can interact with the Discord bot:
- `!enable_alerts` - Enable pattern notifications
- `!disable_alerts` - Disable notifications
- `!status` - Check bot status
- `!info` - Bot information

## Keyboard Shortcuts

- `Ctrl+Q`: Quit application
- `F5`: Refresh console
- `Ctrl+S`: Save configuration

## System Requirements

### Minimum

- 2 CPU cores
- 4GB RAM
- 1GB disk space
- Stable internet connection

### Recommended

- 4 CPU cores
- 8GB RAM
- 10GB disk space (for historical data)
- High-speed internet

## Updates

Check for updates regularly:
- Pattern detection algorithms
- Data collection sources
- UI improvements
- Security patches

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Support**: Check project repository for issues and updates

