# Sell Types Documentation

## Overview

The AI Crypto Trading Agent now supports intelligent sell type detection and execution based on tracked wallet behavior. The system automatically detects whether a tracked wallet is performing a full sell, half sell, or partial sell, and mirrors the appropriate action.

## Features

- **Automatic Sell Type Detection**: Analyzes tracked wallet balance changes to determine sell type
- **Three Sell Types**: Full (100%), Half (50%), and Partial (custom percentage)
- **Balance Tracking**: SQLite-based cache tracks wallet token balances over time
- **Paper & Live Trading**: Works in both paper trading and live trading modes
- **Token Metadata Resolution**: Automatically resolves token symbols and names
- **Comprehensive Testing**: Full test suite covering all scenarios

## Sell Type Logic

### Detection Algorithm

The system determines sell type based on the percentage of tokens sold:

```python
def determine_sell_type(percentage_sold):
    if percentage_sold >= 95%:      # FULL_SELL_THRESHOLD
        return 'full', 100.0
    elif 45% <= percentage_sold <= 55%:  # HALF_SELL range
        return 'half', 50.0
    elif percentage_sold >= 10%:    # PARTIAL_SELL_MIN_THRESHOLD
        return 'partial', percentage_sold
    else:
        return 'skip', 0.0  # Too small to mirror
```

### Configuration Parameters

```python
# Sell type configuration in config.py
HALF_SELL_THRESHOLD = 0.45          # 45-55% considered half sell
HALF_SELL_UPPER_THRESHOLD = 0.55
PARTIAL_SELL_MIN_THRESHOLD = 0.10   # Minimum 10% to be considered partial
FULL_SELL_THRESHOLD = 0.95          # 95%+ considered full sell
```

## Architecture

### Components

1. **TrackedWalletBalanceCache**: SQLite-based balance tracking system
2. **WebhookHandler**: Enhanced to detect sell types from balance changes
3. **CopyBotAgent**: Updated with new sell methods
4. **TokenMetadataService**: Resolves token symbols and names
5. **PaperTrading**: Supports partial closes and position accumulation

### Data Flow

```
Webhook Event → Balance Tracking → Sell Type Detection → CopyBot Execution → Paper/Live Trade
```

## Usage Examples

### Scenario 1: Half Sell Detection

```python
# Tracked wallet sells 50% of tokens
previous_balance = 100.0
current_balance = 50.0
percentage_sold = 50.0%

# System detects: half sell
# CopyBot executes: 50% of our position
```

### Scenario 2: Partial Sell Detection

```python
# Tracked wallet sells 30% of tokens
previous_balance = 100.0
current_balance = 70.0
percentage_sold = 30.0%

# System detects: partial sell
# CopyBot executes: 30% of our position
```

### Scenario 3: Full Sell Detection

```python
# Tracked wallet sells 100% of tokens
previous_balance = 100.0
current_balance = 0.0
percentage_sold = 100.0%

# System detects: full sell
# CopyBot executes: 100% of our position
```

## API Reference

### TrackedWalletBalanceCache

```python
class TrackedWalletBalanceCache:
    def get_previous_balance(self, wallet: str, token: str) -> float
    def update_balance(self, wallet: str, token: str, new_balance: float) -> Dict
    def calculate_sell_percentage(self, previous: float, current: float) -> float
    def determine_sell_type(self, percentage_sold: float) -> Tuple[str, float]
```

### CopyBotAgent Sell Methods

```python
def _execute_half_sell(self, wallet: str, mint: str, token_data: dict, price_service) -> str
def _execute_partial_sell(self, wallet: str, mint: str, token_data: dict, price_service, percentage: float) -> str
def _execute_mirror_sell(self, wallet: str, mint: str, token_data: dict, price_service) -> str
```

### Market Exit Function

```python
def market_exit(symbol, percentage=100, slippage=200, allow_excluded: bool = False) -> bool
```

## Testing

### Running Tests

```bash
# Run all sell type tests
python test/run_sell_type_tests.py

# Run specific test suites
python -m unittest test.agents.test_copybot_sell_types
python -m unittest test.webhooks.test_balance_tracking
python -m unittest test.webhooks.test_webhook_sell_integration
python -m unittest test.test_paper_trading_sell_types
python -m unittest test.agents.test_copybot_sell_workflow
```

### Test Coverage

- **Unit Tests**: Individual method testing
- **Integration Tests**: Component interaction testing
- **End-to-End Tests**: Complete workflow testing
- **Paper Trading Tests**: Position accumulation and partial sells
- **Webhook Tests**: Event processing and sell type detection

## Configuration

### Database Setup

The balance tracking system uses SQLite with the following tables:

```sql
CREATE TABLE wallet_balances (
    wallet_address TEXT NOT NULL,
    token_address TEXT NOT NULL,
    balance REAL NOT NULL,
    last_updated INTEGER NOT NULL,
    PRIMARY KEY (wallet_address, token_address)
);

CREATE TABLE balance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL,
    token_address TEXT NOT NULL,
    previous_balance REAL,
    current_balance REAL NOT NULL,
    change_amount REAL NOT NULL,
    change_percentage REAL,
    sell_type TEXT,
    timestamp INTEGER NOT NULL
);
```

### Environment Variables

```bash
# Required for token metadata resolution
BIRDEYE_API_KEY=your_birdeye_api_key

# Optional: Custom database path
BALANCE_CACHE_DB_PATH=src/data/tracked_wallet_balances.db
```

## Monitoring and Logging

### Log Messages

The system provides detailed logging for monitoring:

```
INFO: Resolved token metadata: SOL (Solana)
INFO: Balance tracking: 100.000000 -> 50.000000 (half, 50.0%)
INFO: HALF SELL: SOL (Solana) from wallet1... - Selling 50% of position
INFO: Successfully executed HALF SELL for SOL
```

### Performance Monitoring

- Balance cache operations are logged with timing
- Sell type detection accuracy can be monitored
- Token metadata resolution success rate tracking

## Troubleshooting

### Common Issues

1. **Token metadata showing as "UNK"**
   - Check BIRDEYE_API_KEY is set
   - Verify token address is valid
   - Check network connectivity

2. **Balance tracking not working**
   - Verify database permissions
   - Check SQLite installation
   - Review webhook event format

3. **Sell type detection incorrect**
   - Check configuration thresholds
   - Verify balance calculation logic
   - Review webhook parsing

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
# In config.py
LOG_LEVEL = "DEBUG"
BALANCE_TRACKING_DEBUG = True
```

## Future Enhancements

### Planned Features

1. **Machine Learning**: AI-based sell type prediction
2. **Risk Management**: Dynamic sell percentage based on risk
3. **Portfolio Optimization**: Smart position sizing
4. **Real-time Analytics**: Live dashboard for sell type monitoring

### Webhook Ideas

1. **Multi-token Events**: Handle complex transactions with multiple tokens
2. **Time-based Analysis**: Consider transaction timing in sell type detection
3. **Volume Analysis**: Factor in trading volume for better detection
4. **Social Signals**: Integrate social media sentiment for sell decisions

## Support

For issues or questions:

1. Check the test suite for expected behavior
2. Review logs for error messages
3. Verify configuration settings
4. Test with paper trading mode first

## Changelog

### Version 1.0.0
- Initial implementation of sell type detection
- Balance tracking system
- CopyBot integration
- Comprehensive test suite
- Documentation and examples
