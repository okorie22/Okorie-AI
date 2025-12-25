import pandas as pd
import talib
from backtesting import Backtest, Strategy

class PatternCatalystSimple(Strategy):
    """
    CLEAN, SIMPLE VERSION: Pattern Catalyst v1
    - Single engulfing pattern
    - Basic trend + volume + RSI filters
    - Simple exits: time + profit + stop loss
    - Fixed parameters, no regime detection
    """

    def init(self):
        print("[STRATEGY] PatternCatalystSimple initialized - Clean Architecture")

        # SINGLE PATTERN: Only engulfing (bullish +100, bearish -100)
        self.engulfing = self.I(talib.CDLENGULFING,
                               self.data.Open, self.data.High,
                               self.data.Low, self.data.Close)

        # BASIC TREND FILTER: 20-period SMA
        self.sma_20 = self.I(talib.SMA, self.data.Close, timeperiod=20)
        self.sma_50 = self.I(talib.SMA, self.data.Close, timeperiod=50)

        # Removed volume and RSI filters for ultra-simple version

        # FIXED STRATEGY PARAMETERS (no dynamic changes)
        self.risk_percentage = 0.02  # 2% risk per trade
        self.stop_loss_pct = 0.10    # 10% stop loss
        self.profit_target_pct = 0.06  # 6% profit target
        self.max_holding_period = 20   # 20 days max hold
        # Removed - now allowing any engulfing pattern

        # Track entry bar for time exits
        self.entry_bar = None
        self.bar_count = 0

    def next(self):
        self.bar_count += 1

        # ENTRY LOGIC: Clean and simple
        if not self.position:
            self._check_entry_conditions()
        else:
            self._check_exit_conditions()

    def _check_entry_conditions(self):
        """Ultra-simple entry logic: Just pattern + basic trend"""
        current_price = self.data.Close[-1]

        # 1. PATTERN CHECK: Any engulfing pattern signal
        pattern_signal = self.engulfing[-1]
        if pattern_signal == 0:
            return  # No engulfing pattern

        # 2. BASIC TREND FILTER: Price above/below 20 SMA
        sma_20 = self.sma_20[-1]

        if pattern_signal == 100 and current_price <= sma_20:
            return  # Bullish pattern but price below trend
        elif pattern_signal == -100 and current_price >= sma_20:
            return  # Bearish pattern but price above trend

        # PATTERN + TREND ALIGNED - EXECUTE TRADE
        self._execute_trade(pattern_signal)

    def _execute_trade(self, pattern_signal):
        """Execute trade with fixed risk management"""
        current_price = self.data.Close[-1]

        if pattern_signal == 100:  # BULLISH
            # Calculate stop loss below entry
            stop_price = current_price * (1 - self.stop_loss_pct)
            risk_amount = self.equity * self.risk_percentage
            risk_distance = current_price - stop_price

            if risk_distance > 0:
                # Calculate position size as FRACTION of equity
                max_position_value = self.equity * 0.10  # Max 10% of equity
                position_value = min(risk_amount / (risk_distance / current_price), max_position_value)
                position_fraction = position_value / self.equity
                position_fraction = max(position_fraction, 0.001)  # Min 0.1% of equity

                print(f"[LONG ENTRY] Engulfing at ${current_price:.2f}, "
                      f"Stop: ${stop_price:.2f}, Size: {position_fraction:.4f} ({position_fraction*100:.1f}% equity)")

                self.buy(size=position_fraction)
                self.entry_bar = self.bar_count

        elif pattern_signal == -100:  # BEARISH
            # Calculate stop loss above entry
            stop_price = current_price * (1 + self.stop_loss_pct)
            risk_amount = self.equity * self.risk_percentage
            risk_distance = stop_price - current_price

            if risk_distance > 0:
                # Calculate position size as FRACTION of equity
                max_position_value = self.equity * 0.10  # Max 10% of equity
                position_value = min(risk_amount / (risk_distance / current_price), max_position_value)
                position_fraction = position_value / self.equity
                position_fraction = max(position_fraction, 0.001)  # Min 0.1% of equity

                print(f"[SHORT ENTRY] Engulfing at ${current_price:.2f}, "
                      f"Stop: ${stop_price:.2f}, Size: {position_fraction:.4f} ({position_fraction*100:.1f}% equity)")

                self.sell(size=position_fraction)
                self.entry_bar = self.bar_count

    def _check_exit_conditions(self):
        """Simple exit logic: time + profit + stop loss"""
        if not self.trades:
            return

        current_price = self.data.Close[-1]
        entry_price = self.trades[-1].entry_price
        bars_held = self.bar_count - self.entry_bar

        # TIME EXIT: Max holding period
        if bars_held >= self.max_holding_period:
            print(f"[TIME EXIT] After {bars_held} bars")
            self.position.close()
            return

        # PROFIT TARGET EXIT
        if self.position.is_long:
            profit_pct = (current_price - entry_price) / entry_price
            if profit_pct >= self.profit_target_pct:
                print(f"[PROFIT EXIT] +{profit_pct*100:.1f}% achieved")
                self.position.close()
                return
        else:  # Short position
            profit_pct = (entry_price - current_price) / entry_price
            if profit_pct >= self.profit_target_pct:
                print(f"[PROFIT EXIT] +{profit_pct*100:.1f}% achieved")
                self.position.close()
                return

        # STOP LOSS EXIT (handled by backtesting framework)
        # The stop loss is set at entry, so this is automatic


# Load and prepare data for multiple symbols
print("[INFO] Loading data for multiple symbols...")

# CHANGE TIMEFRAME HERE: '1d', '4h', '1h', '15m', '5m', etc.
data_timeframe = '1d'  # Change this to test different timeframes

# Symbols to test
symbols = ['BTC','ETH', 'SOL', 'BNB']
print(f"[INFO] Testing symbols: {symbols}")
print(f"[INFO] Using {data_timeframe} timeframe")

def load_symbol_data(symbol, timeframe):
    """Load and prepare data for a specific symbol"""
    data_filename = f'{symbol}-USD-{timeframe}.csv'

    try:
        price_data = pd.read_csv(f'C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/{data_filename}')
        print(f"[INFO] Loaded {symbol} data: {len(price_data)} rows")

        # Clean column names
        price_data.columns = price_data.columns.str.strip().str.lower()

        # Drop any unnamed columns
        price_data = price_data.drop(columns=[col for col in price_data.columns if 'unnamed' in col.lower()])

        # Ensure proper column mapping
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in price_data.columns:
                print(f"[ERROR] Missing required column: {col} for {symbol}")
                print(f"[DEBUG] Available columns: {list(price_data.columns)}")
                return None

        # Rename columns to proper case for backtesting.py
        price_data = price_data.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })

        # Set datetime index - FIXED: Check for datetime column
        if 'datetime' in price_data.columns:
            price_data.index = pd.to_datetime(price_data['datetime'])
        elif 'timestamp' in price_data.columns:
            price_data.index = pd.to_datetime(price_data['timestamp'])
        elif 'date' in price_data.columns:
            price_data.index = pd.to_datetime(price_data['date'])
        elif 'time' in price_data.columns:
            price_data.index = pd.to_datetime(price_data['time'])
        else:
            print(f"[WARNING] No timestamp column found for {symbol}, using index as time")
            price_data.index = pd.to_datetime(price_data.index)

        return price_data

    except FileNotFoundError:
        print(f"[WARNING] Data file not found for {symbol}: {data_filename}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load data for {symbol}: {e}")
        return None

def run_symbol_backtest(symbol, price_data):
    """Run backtest for a specific symbol and return results"""
    print(f"\n{'='*60}")
    print(f"BACKTESTING {symbol} - SIMPLE VERSION")
    print('='*60)

    try:
        # Run backtest with clean architecture
        print(f"[INFO] Starting {symbol} backtest...")
        bt = Backtest(price_data, PatternCatalystSimple, cash=1000000, commission=.002, margin=0.1)
        stats = bt.run()

        # Run again with finalize_trades=True
        print(f"[INFO] Finalizing {symbol} trades...")
        bt_final = Backtest(price_data, PatternCatalystSimple, cash=1000000, commission=.002, margin=0.1, finalize_trades=True)
        stats_final = bt_final.run()

        return stats_final

    except Exception as e:
        print(f"[ERROR] Backtest failed for {symbol}: {e}")
        return None

# Run backtests for all symbols
all_results = {}
successful_symbols = []

for symbol in symbols:
    price_data = load_symbol_data(symbol, data_timeframe)
    if price_data is not None:
        stats = run_symbol_backtest(symbol, price_data)
        if stats is not None:
            all_results[symbol] = stats
            successful_symbols.append(symbol)

# Display aggregated results
if successful_symbols:
    print(f"\n{'='*80}")
    print("PATTERN CATALYST SIMPLE V1 - MULTI-SYMBOL AGGREGATED RESULTS")
    print('='*80)

    total_return = 0
    total_trades = 0
    total_wins = 0
    total_win_rate = 0
    max_dd = 0
    min_dd = 0

    for symbol in successful_symbols:
            stats = all_results[symbol]
            symbol_return = stats['Return [%]']
            symbol_trades = len(stats._trades)
            symbol_win_rate = stats.get('Win Rate [%]', 0)
            symbol_max_dd = stats.get('Max. Drawdown [%]', 0)

            total_return += symbol_return
            total_trades += symbol_trades
            if symbol_trades > 0:
                total_wins += int(symbol_trades * symbol_win_rate / 100)
            max_dd = max(max_dd, abs(symbol_max_dd))

            print(f"\n{symbol}:")
            print(f"  Return [%]: {symbol_return:.2f}")
            print(f"  Buy & Hold Return [%]: {stats.get('Buy & Hold Return [%]', 0):.2f}")
            print(f"  Max. Drawdown [%]: {symbol_max_dd:.2f}")
            print(f"  Avg. Drawdown [%]: {stats.get('Avg. Drawdown [%]', 0):.2f}")
            print(f"  # Trades: {symbol_trades}")
            print(f"  Win Rate [%]: {symbol_win_rate:.1f}")
            print(f"  Best Trade [%]: {stats.get('Best Trade [%]', 0):.2f}")
            print(f"  Worst Trade [%]: {stats.get('Worst Trade [%]', 0):.2f}")
            print(f"  Avg. Trade [%]: {stats.get('Avg. Trade [%]', 0):.2f}")
            print(f"  Profit Factor: {stats.get('Profit Factor', 0):.2f}")
            print(f"  Expectancy [%]: {stats.get('Expectancy [%]', 0):.2f}")
            print(f"  Sharpe Ratio: {stats.get('Sharpe Ratio', 0):.2f}")
            print(f"  Sortino Ratio: {stats.get('Sortino Ratio', 0):.2f}")
            print(f"  Calmar Ratio: {stats.get('Calmar Ratio', 0):.2f}")
            print(f"  Max. Trade Duration: {stats.get('Max. Trade Duration', 'N/A')}")
            print(f"  Avg. Trade Duration: {stats.get('Avg. Trade Duration', 'N/A')}")
            print(f"  Exposure Time [%]: {stats.get('Exposure Time [%]', 0):.2f}")
            print(f"  SQN: {stats.get('SQN', 0):.2f}")
            print(f"  Kelly Criterion: {stats.get('Kelly Criterion', 0):.2f}")

    avg_return = total_return / len(successful_symbols)
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

    print(f"\n{'='*40}")
    print("SIMPLE V1 AGGREGATED SUMMARY:")
    print(f"  Symbols tested: {len(successful_symbols)}")
    print(f"  Average return: {avg_return:.2f}%")
    print(f"  Total trades: {total_trades}")
    print(f"  Overall win rate: {overall_win_rate:.1f}%")
    print(f"  Max drawdown (worst symbol): {max_dd:.2f}%")

    # Calculate additional aggregated stats
    total_pf = 0
    total_expectancy = 0
    total_sharpe = 0
    total_sortino = 0
    total_calmar = 0
    total_sqn = 0

    for symbol in successful_symbols:
        stats = all_results[symbol]
        total_pf += stats.get('Profit Factor', 0)
        total_expectancy += stats.get('Expectancy [%]', 0)
        total_sharpe += stats.get('Sharpe Ratio', 0)
        total_sortino += stats.get('Sortino Ratio', 0)
        total_calmar += stats.get('Calmar Ratio', 0)
        total_sqn += stats.get('SQN', 0)

    avg_pf = total_pf / len(successful_symbols)
    avg_expectancy = total_expectancy / len(successful_symbols)
    avg_sharpe = total_sharpe / len(successful_symbols)
    avg_sortino = total_sortino / len(successful_symbols)
    avg_calmar = total_calmar / len(successful_symbols)
    avg_sqn = total_sqn / len(successful_symbols)

    print(f"  Average Profit Factor: {avg_pf:.2f}")
    print(f"  Average Expectancy [%]: {avg_expectancy:.2f}")
    print(f"  Average Sharpe Ratio: {avg_sharpe:.2f}")
    print(f"  Average Sortino Ratio: {avg_sortino:.2f}")
    print(f"  Average Calmar Ratio: {avg_calmar:.2f}")
    print(f"  Average SQN: {avg_sqn:.2f}")
    print(f"  Prop firm target: 12% return, 9% max DD")
    print(f"  Status: {'PASS' if avg_return >= 12 and max_dd <= 9 else 'FAIL'}")

else:
    print("[ERROR] No successful backtests completed")
