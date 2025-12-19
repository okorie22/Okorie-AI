"""
🌙 Moon Dev's RBI AI v3.0 (Research-Backtest-Implement-Execute-OPTIMIZE)
Built with love by Moon Dev 🚀

🎯 THE PROFIT TARGET HUNTER 🎯

NEW IN v3.0: AUTONOMOUS OPTIMIZATION LOOP!
- Automatically executes backtests
- Captures errors and stats
- Loops back to debug agent on failures
- ⭐ RUNS CONTINUOUSLY UNTIL PROFIT TARGET IS HIT! ⭐
- Optimizes entry/exit, indicators, risk management, filters
- Each iteration improves the strategy to chase your target return
- Never gives up until TARGET_RETURN % is achieved! 🚀

HOW IT WORKS:
1. Researches your trading idea
2. Codes the backtest
3. Debugs until it executes successfully
4. Checks the return %
5. IF return < TARGET_RETURN:
   → Optimization AI improves the strategy
   → Executes improved version
   → Checks new return
   → Repeats until TARGET_RETURN is hit! 🎯
6. Saves TARGET_HIT version when goal achieved!

Required Setup:
1. Conda environment 'tflow' with backtesting packages
2. Set your TARGET_RETURN below (default: 50%)
3. Run and watch it optimize until profit target is achieved! 🚀💰

IMPORTANT: This agent will keep running optimizations (up to MAX_OPTIMIZATION_ITERATIONS)
until it achieves your target return. Set realistic targets!
"""

# Import execution functionality
import subprocess
import json
from pathlib import Path
from anthropic import Anthropic
import openai
import sys
import os

# Fix Windows console encoding for emojis
import sys
import os
if os.name == 'nt':  # Windows
    try:
        # Force UTF-8 encoding for stdout/stderr to handle emojis
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass  # If it fails, continue with default encoding

# Core imports only
import os
import time
import re
import hashlib
from datetime import datetime
from termcolor import cprint
import threading
import itertools
import sys
from dotenv import load_dotenv

# Load environment variables FIRST
# .env file is in the main ITORO root directory (parent of agent-systems)
project_root = Path(__file__).parent.parent.parent.parent.parent  # Go up 5 levels to ITORO root
env_path = project_root / '.env'
load_dotenv(env_path)
print(f"[OK] Environment variables loaded from: {env_path}")

# Add config values directly to avoid import issues
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 4000

# Import model factory with proper path handling
import sys
from pathlib import Path

# Add the current project's src directory to path
project_root = Path(__file__).parent.parent.parent  # Go up to itoro directory
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

print(f"[SEARCH] Added to Python path: {src_path}")

try:
    from models.model_factory import model_factory
    print("[OK] Successfully imported model_factory")
except ImportError as e:
    print(f"[WARN] Could not import model_factory: {e}")
    print(f"   Current Python path: {sys.path[:3]}...")
    sys.exit(1)

# Model Configurations
# You can switch between "deepseek", "xai", "openai", "claude", "groq", etc.
# Now using DeepSeek for all AI operations - excellent reasoning capabilities!
RESEARCH_CONFIG = {
    "type": "deepseek",  # Using DeepSeek for research and idea generation
    "name": "deepseek-chat"
}

BACKTEST_CONFIG = {
    "type": "deepseek",  # Using DeepSeek for backtest coding
    "name": "deepseek-chat"
}

DEBUG_CONFIG = {
    "type": "deepseek",  # Using DeepSeek for debugging
    "name": "deepseek-chat"
}

PACKAGE_CONFIG = {
    "type": "deepseek",  # Using DeepSeek for package checking
    "name": "deepseek-chat"
}

OPTIMIZE_CONFIG = {
    "type": "deepseek",  # Using DeepSeek for strategy optimization
    "name": "deepseek-chat"
}

# 🎯🎯🎯 PROFIT TARGET CONFIGURATION 🎯🎯🎯
# ============================================
# The agent will CONTINUOUSLY OPTIMIZE the strategy until this target is achieved!
# It will run up to MAX_OPTIMIZATION_ITERATIONS attempting to hit this goal.
# Set a realistic target based on your market and timeframe!
# ============================================
TARGET_RETURN = 50  # Target return in % (50 = 50%)
# Examples: 10 = 10%, 25 = 25%, 50 = 50%, 100 = 100%

# Execution Configuration
CONDA_ENV = "tflow"  # Your conda environment
MAX_DEBUG_ITERATIONS = 10  # Max times to try debugging before moving to optimization
MAX_OPTIMIZATION_ITERATIONS = 10  # Max times to KEEP OPTIMIZING until target is hit! 🎯
                                  # Agent runs this many optimization loops trying to achieve TARGET_RETURN
                                  # Higher = more chances to hit target, but takes longer
EXECUTION_TIMEOUT = 300  # 5 minutes

# DeepSeek Configuration
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Get today's date for organizing outputs
TODAY_DATE = datetime.now().strftime("%m_%d_%Y")

# Update data directory paths - V3 uses separate folder structure
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data/rbi_v3"  # NEW: Separate V3 folder
TODAY_DIR = DATA_DIR / TODAY_DATE
RESEARCH_DIR = TODAY_DIR / "research"
BACKTEST_DIR = TODAY_DIR / "backtests"
PACKAGE_DIR = TODAY_DIR / "backtests_package"
FINAL_BACKTEST_DIR = TODAY_DIR / "backtests_final"
OPTIMIZATION_DIR = TODAY_DIR / "backtests_optimized"  # NEW for V3!
CHARTS_DIR = TODAY_DIR / "charts"
EXECUTION_DIR = TODAY_DIR / "execution_results"
PROCESSED_IDEAS_LOG = DATA_DIR / "processed_ideas.log"

# IDEAS file is in the main data/rbi folder (shared with other versions)
IDEAS_FILE = PROJECT_ROOT / "data/rbi/ideas.txt"

# Create main directories if they don't exist
for dir in [DATA_DIR, TODAY_DIR, RESEARCH_DIR, BACKTEST_DIR, PACKAGE_DIR,
            FINAL_BACKTEST_DIR, OPTIMIZATION_DIR, CHARTS_DIR, EXECUTION_DIR]:
    dir.mkdir(parents=True, exist_ok=True)

# All prompts (same as v1)
RESEARCH_PROMPT = """
You are Moon Dev's Research AI

IMPORTANT NAMING RULES:
1. Create a UNIQUE TWO-WORD NAME for this specific strategy
2. The name must be DIFFERENT from any generic names like "TrendFollower" or "MomentumStrategy"
3. First word should describe the main approach (e.g., Adaptive, Neural, Quantum, Fractal, Dynamic)
4. Second word should describe the specific technique (e.g., Reversal, Breakout, Oscillator, Divergence)
5. Make the name SPECIFIC to this strategy's unique aspects

Examples of good names:
- "AdaptiveBreakout" for a strategy that adjusts breakout levels
- "FractalMomentum" for a strategy using fractal analysis with momentum
- "QuantumReversal" for a complex mean reversion strategy
- "NeuralDivergence" for a strategy focusing on divergence patterns

BAD names to avoid:
- "TrendFollower" (too generic)
- "SimpleMoving" (too basic)
- "PriceAction" (too vague)

Output format must start with:
STRATEGY_NAME: [Your unique two-word name]

Then analyze the trading strategy content and create detailed instructions.
Focus on:
1. Key strategy components
2. Entry/exit rules
3. Risk management
4. Required indicators

Your complete output must follow this format:
STRATEGY_NAME: [Your unique two-word name]

STRATEGY_DETAILS:
[Your detailed analysis]

Remember: The name must be UNIQUE and SPECIFIC to this strategy's approach!
"""

BACKTEST_PROMPT = """
You are Moon Dev's Backtest AI. ONLY SEND BACK CODE, NO OTHER TEXT.
Create a backtesting.py implementation for the strategy.
USE BACKTESTING.PY
Include:
1. All necessary imports
2. Strategy class with indicators
3. Entry/exit logic
4. Risk management
5. your size should be 1,000,000
6. If you need indicators use TA lib or pandas TA.

IMPORTANT DATA HANDLING:
1. Clean column names by removing spaces: data.columns = data.columns.str.strip().str.lower()
2. Drop any unnamed columns: data = data.drop(columns=[col for col in data.columns if 'unnamed' in col.lower()])
3. Ensure proper column mapping to match backtesting requirements:
   - Required columns: 'Open', 'High', 'Low', 'Close', 'Volume'
   - Use proper case (capital first letter)

FOR THE PYTHON BACKTESTING LIBRARY USE BACKTESTING.PY AND SEND BACK ONLY THE CODE, NO OTHER TEXT.

INDICATOR CALCULATION RULES:
1. ALWAYS use self.I() wrapper for ANY indicator calculations
2. Use talib functions instead of pandas operations:
   - Instead of: self.data.Close.rolling(20).mean()
   - Use: self.I(talib.SMA, self.data.Close, timeperiod=20)
3. For swing high/lows use talib.MAX/MIN:
   - Instead of: self.data.High.rolling(window=20).max()
   - Use: self.I(talib.MAX, self.data.High, timeperiod=20)

CRITICAL BACKTESTING.PY DATA ACCESS RULES:
1. self.data.* columns are _Array objects, NOT pandas Series or DataFrames
2. FORBIDDEN operations on self.data.* columns:
   - .values (not needed - already an array)
   - .iloc (use array indexing instead)
   - .loc (use array indexing instead)
   - .shift() (calculate shifts outside and use self.I())
   - .rolling() (use talib functions with self.I() instead)
   - Any other pandas Series methods
3. CORRECT usage examples:
   - Instead of: self.data.OI.values → use: self.data.OI (already an array)
   - Instead of: self.data.OI.iloc[-1] → use: self.data.OI[-1] (array indexing)
   - Instead of: self.data.OI.shift(1) → calculate shift in pandas before backtest, then use self.I()
   - Instead of: self.data.Close.rolling(20) → use: self.I(talib.SMA, self.data.Close, timeperiod=20)

BACKTEST EXECUTION ORDER:
1. Run initial backtest with default parameters first
2. Print full stats using print(stats) and print(stats._strategy)
3. no optimization code needed, just print the final stats, make sure full stats are printed, not just part or some. stats = bt.run() print(stats) is an example of the last line of code. no need for plotting ever.

do not creeate charts to plot this, just print stats. no charts needed.

CRITICAL POSITION SIZING RULES (MUST FOLLOW EXACTLY):
1. Position sizes MUST be either:
   - A fraction between 0 and 1 (e.g., 0.1 for 10% of equity)
   - A positive whole number (integer) for units

2. NEVER use floating point numbers for position sizes
3. Always round and convert to int: position_size = int(round(position_size))
4. For risk-based sizing: risk_amount = self.equity * risk_percentage
5. Then: position_size = int(round(risk_amount / stop_distance))

VALID: self.buy(size=0.1) or self.buy(size=5)
INVALID: self.buy(size=3.14159) or self.buy(size=1.5)

Fix any calculation that results in non-integer, non-fraction sizes.

RISK MANAGEMENT:
1. Always calculate position sizes based on risk percentage
2. Use proper stop loss and take profit calculations
3. Print entry/exit signals with simple debug messages

If you need indicators use TA lib or pandas TA. 

CRITICAL DATA LOADING INSTRUCTIONS:
1. Load data directly using pandas - this backtest runs as a standalone script:
   - For OI data: oi_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/oi/oi_20251218.parquet')
     * OI data contains multiple symbols - filter for specific symbol: oi_data = oi_data[oi_data['symbol'] == 'BTC']
     * Use 'open_interest' column (NOT 'OI' or 'oi_value')
   - For Funding data: funding_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/funding/funding_20251218.parquet')
     * Funding data contains multiple symbols - DO NOT filter for BTC only
     * Test all symbols in the funding data, or iterate through symbols that have extreme funding rates
     * Example: for symbol in funding_data['symbol'].unique(): process_symbol_data(symbol)
   - For OHLCV data: price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
   - For Onchain data: onchain_data = pd.read_json('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/token_onchain_data.json')
     * On-chain data has nested JSON structure - normalize to flat DataFrame
     * Extract: timestamp, symbol, whale_concentration (from holder_distribution.whale_pct), market_cap (estimate from liquidity_usd * 10)
     * Also extract: holder_count, transaction_volume (volume_24h), transaction_count (tx_count_24h)
     * Align timestamps with OHLCV data using merge and forward-fill to match price data frequency
2. Clean column names if needed: data.columns = data.columns.str.strip().str.lower()
3. Drop unnamed columns if needed: data = data.drop(columns=[col for col in data.columns if 'unnamed' in col.lower()])
4. Set datetime index: data = data.set_index(pd.to_datetime(data['timestamp']))
5. Ensure proper column capitalization for backtesting.py
6. For time resampling use lowercase frequency strings (e.g., '4h' not '4H') to avoid pandas warnings

STRICT RULES:
- NEVER define functions named load_oi_data, load_funding_data, load_ohlcv_data, or load_onchain_data
- NEVER call RBI v3 functions - load data directly with pandas
- This script runs standalone and must load its own data

Add simple debug prints using plain text only. Do NOT use emojis or special characters that might cause encoding issues.
Use prints like: print("[INFO] Entry signal detected") or print("[BUY] Opening position")

DEBUG DATA STRUCTURE LOGGING:
When loading OI data, add debug prints to verify data structure:
print(f"[DEBUG] OI data shape: {oi_data.shape}")
print(f"[DEBUG] OI data columns: {list(oi_data.columns)}")
print(f"[DEBUG] OI data dtypes: {oi_data.dtypes.to_dict()}")
if 'open_interest' in oi_data.columns:
    print(f"[DEBUG] OI column exists with {len(oi_data)} rows")
else:
    print("[ERROR] No 'open_interest' column found in OI data")
    raise ValueError("No 'open_interest' column found in OI data")

FOR THE PYTHON BACKTESTING LIBRARY USE BACKTESTING.PY AND SEND BACK ONLY THE CODE, NO OTHER TEXT.
ONLY SEND BACK CODE, NO OTHER TEXT.
"""

DEBUG_PROMPT = """
You are Moon Dev's Debug AI
Fix technical issues in the backtest code WITHOUT changing the strategy logic.

CRITICAL ERROR TO FIX:
{error_message}

CRITICAL DATA LOADING REQUIREMENTS:
The CSV file has these exact columns after processing:
- datetime, open, high, low, close, volume (all lowercase after .str.lower())
- After capitalization: Datetime, Open, High, Low, Close, Volume

CRITICAL BACKTESTING REQUIREMENTS:
1. Data Loading Rules:
   - Use data.columns.str.strip().str.lower() to clean columns
   - Drop unnamed columns: data.drop(columns=[col for col in data.columns if 'unnamed' in col.lower()])
   - Rename columns properly: data.rename(columns={{'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}})
   - Set datetime as index: data = data.set_index(pd.to_datetime(data['datetime']))

2. Position Sizing Rules:
   - Must be either a fraction (0 < size < 1) for percentage of equity
   - OR a positive whole number (round integer) for units
   - NEVER use floating point numbers for unit-based sizing

3. Indicator Issues:
   - Cannot use .shift() on backtesting indicators
   - Use array indexing like indicator[-2] for previous values
   - All indicators must be wrapped in self.I()
   - CRITICAL: Cannot use pandas methods on backtesting.py data columns
   - self.data.* columns are _Array objects, NOT pandas Series
   - FORBIDDEN on self.data.*: .values, .iloc, .loc, .shift(), .rolling()
   - Use array indexing: self.data.OI[-1] instead of self.data.OI.iloc[-1]
   - Use self.data.OI directly instead of self.data.OI.values

4. Position Object Issues:
   - Position object does NOT have .entry_price attribute
   - Use self.trades[-1].entry_price if you need entry price from last trade
   - Available position attributes: .size, .pl, .pl_pct
   - For partial closes: use self.position.close() without parameters (closes entire position)
   - For stop losses: use sl= parameter in buy/sell calls, not in position.close()

5. No Trades Issue (Signals but no execution):
   - If strategy prints "ENTRY SIGNAL" but shows 0 trades, the self.buy() call is not executing
   - Common causes: invalid size parameter, insufficient cash, missing self.buy() call
   - Ensure self.buy() is actually called in the entry condition block
   - Check size parameter: must be fraction (0-1) or positive integer
   - Verify cash/equity is sufficient for the trade size

Focus on:
1. KeyError issues with column names
2. Syntax errors and import statements
3. Indicator calculation methods
4. Data loading and preprocessing
5. Position object attribute errors (.entry_price, .close() parameters)

DO NOT change strategy logic, entry/exit conditions, or risk management rules.

Return the complete fixed code with simple debug prints using plain text only.
ONLY SEND BACK CODE, NO OTHER TEXT.
"""

PACKAGE_PROMPT = """
You are Moon Dev's Package AI
Your job is to ensure the backtest code NEVER uses ANY backtesting.lib imports or functions AND to fix data loading issues.

❌ STRICTLY FORBIDDEN:
1. from backtesting.lib import *
2. import backtesting.lib
3. from backtesting.lib import crossover
4. ANY use of backtesting.lib
5. Defining your own data loading functions (load_oi_data, load_funding_data, load_ohlcv_data, load_onchain_data)

✅ REQUIRED REPLACEMENTS:
1. For crossover detection:
   Instead of: backtesting.lib.crossover(a, b)
   Use: (a[-2] < b[-2] and a[-1] > b[-1])  # for bullish crossover
        (a[-2] > b[-2] and a[-1] < b[-1])  # for bearish crossover

2. For indicators:
   - Use talib for all standard indicators (SMA, RSI, MACD, etc.)
   - Use pandas-ta for specialized indicators
   - ALWAYS wrap in self.I()

3. For signal generation:
   - Use numpy/pandas boolean conditions
   - Use rolling window comparisons with array indexing
   - Use mathematical comparisons (>, <, ==)

4. For data loading:
   - REPLACE RBI v3 function calls with direct data loading:
     * oi_data = load_oi_data('BTC') → oi_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/oi/oi_20251218.parquet')
     * funding_data = load_funding_data('BTC') → funding_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/funding/funding_20251218.parquet')
     * price_data = load_ohlcv_data('BTC') → price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
     * onchain_data = load_onchain_data() → onchain_data = pd.read_json('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/token_onchain_data.json')
     * For liquidation data: try pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/liquidations/liquidations_20251218.parquet') and handle if file doesn't exist
   - REMOVE any function definitions for load_oi_data, load_funding_data, load_ohlcv_data, load_onchain_data
   - CRITICAL: self.data.* columns are _Array objects, NOT pandas Series
   - NEVER use on self.data.*: .values, .iloc, .loc, .shift(), .rolling()
   - Correct usage: self.data.OI[-1] (array indexing)
   - Wrong usage: self.data.OI.values or self.data.OI.iloc[-1]
   - FIX backtesting.py OI calculation: Replace pandas .shift() with numpy operations that work with _Array objects:
     * self.oi_pct_change = self.I(lambda x: ((x - x.shift(n)) / x.shift(n)) * 100, data)
       → Calculate oi_pct_change outside self.I(): oi_pct_change = ((oi_data - oi_data.shift(n)) / oi_data.shift(n)) * 100
       → Then use: self.oi_pct_change = self.I(lambda: oi_pct_change)

Example conversions:
❌ from backtesting.lib import crossover
❌ if crossover(fast_ma, slow_ma):
✅ if fast_ma[-2] < slow_ma[-2] and fast_ma[-1] > slow_ma[-1]:

❌ self.sma = self.I(backtesting.lib.SMA, self.data.Close, 20)
✅ self.sma = self.I(talib.SMA, self.data.Close, timeperiod=20)

❌ oi_data = load_oi_data('BTC')
✅ oi_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/oi/oi_20251218.parquet')

❌ def load_oi_data(symbol):
❌     # custom implementation
❌ oi_data = load_oi_data('BTC')  # but this was defined above

❌ oi_array = self.data.OI.values
✅ oi_array = self.data.OI  # Already an array, no .values needed

❌ oi_value = self.data.OI.iloc[-1]
✅ oi_value = self.data.OI[-1]  # Use array indexing

IMPORTANT: Scan the ENTIRE code for any backtesting.lib usage AND any custom data loading function definitions, then replace ALL instances!
IMPORTANT: Scan for any .values, .iloc, .loc usage on self.data.* columns and replace with array indexing!
Return the complete fixed code with simple debug prints using plain text only.
ONLY SEND BACK CODE, NO OTHER TEXT.
"""

OPTIMIZE_PROMPT = """
You are Moon Dev's Optimization AI
Your job is to IMPROVE the strategy to achieve higher returns while maintaining good risk management.

CURRENT PERFORMANCE:
Return [%]: {current_return}%
TARGET RETURN: {target_return}%

YOUR MISSION: Optimize this strategy to hit the target return!

OPTIMIZATION TECHNIQUES TO CONSIDER:
1. **Entry Optimization:**
   - Tighten entry conditions to catch better setups
   - Add filters to avoid low-quality signals
   - Use multiple timeframe confirmation
   - Add volume/momentum filters

2. **Exit Optimization:**
   - Improve take profit levels
   - Add trailing stops
   - Use dynamic position sizing based on volatility
   - Scale out of positions

3. **Risk Management:**
   - Adjust position sizing
   - Use volatility-based position sizing (ATR)
   - Add maximum drawdown limits
   - Improve stop loss placement

4. **Indicator Optimization:**
   - Fine-tune indicator parameters
   - Add complementary indicators
   - Use indicator divergence
   - Combine multiple timeframes

5. **Market Regime Filters:**
   - Add trend filters
   - Avoid choppy/ranging markets
   - Only trade in favorable conditions

IMPORTANT RULES:
- DO NOT break the code structure
- Keep simple debug prints using plain text only (no emojis)
- Maintain proper backtesting.py format
- Use self.I() for all indicators
- Position sizes must be int or fraction (0-1)
- Focus on REALISTIC improvements (no curve fitting!)
- Explain your optimization changes in comments

Return ONLY the complete Python code for the optimized strategy class.
CRITICAL: Do NOT include markdown formatting (```), explanations, emojis, or ANY text outside of valid Python code.
The response must start directly with "import" or "class" and contain ONLY executable Python code.
NO markdown, NO explanations, NO emojis - just pure Python code.
"""

def parse_return_from_output(stdout: str) -> float:
    """
    Extract the Return [%] from backtest output
    Returns the percentage as a float, or None if not found
    """
    try:
        # Look for pattern like "Return [%]                            45.67"
        match = re.search(r'Return \[%\]\s+([-\d.]+)', stdout)
        if match:
            return_pct = float(match.group(1))
            cprint(f"📊 Extracted return: {return_pct}%", "cyan")
            return return_pct
        else:
            cprint("[WARN] Could not find Return [%] in output", "yellow")
            return None
    except Exception as e:
        cprint(f"❌ Error parsing return: {str(e)}", "red")
        return None

def execute_backtest(file_path: str, strategy_name: str) -> dict:
    """
    Execute a backtest file in conda environment and capture output
    This is the NEW MAGIC! 🚀
    """
    # #region agent log - execute_backtest entry
    import json
    import time
    log_path = r"c:\Users\Top Cash Pawn\ITORO\.cursor\debug.log"
    with open(log_path, 'a', encoding='utf-8') as f:
        json.dump({
            "id": f"log_{int(time.time() * 1000)}_execute_entry",
            "timestamp": int(time.time() * 1000),
            "location": "rbi_agent_v3.py:execute_backtest",
            "message": "Starting backtest execution",
            "data": {
                "file_path": str(file_path),
                "strategy_name": strategy_name,
                "conda_env": CONDA_ENV,
                "file_exists": os.path.exists(file_path),
                "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0
            },
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "exec_1"
        }, f)
        f.write('\n')
    # #endregion

    cprint(f"\n[ROCKET] Executing backtest: {strategy_name}", "cyan")
    cprint(f"📂 File: {file_path}", "cyan")
    cprint(f"🐍 Using conda env: {CONDA_ENV}", "cyan")

    # #region agent log - file validation
    with open(log_path, 'a', encoding='utf-8') as f:
        json.dump({
            "id": f"log_{int(time.time() * 1000)}_file_validation",
            "timestamp": int(time.time() * 1000),
            "location": "rbi_agent_v3.py:execute_backtest",
            "message": "File validation check",
            "data": {
                "file_path": str(file_path),
                "exists": os.path.exists(file_path),
                "is_file": os.path.isfile(file_path) if os.path.exists(file_path) else False,
                "permissions": oct(os.stat(file_path).st_mode) if os.path.exists(file_path) else "N/A"
            },
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "exec_2"
        }, f)
        f.write('\n')
    # #endregion

    if not os.path.exists(file_path):
        # #region agent log - file not found error
        with open(log_path, 'a', encoding='utf-8') as f:
            json.dump({
                "id": f"log_{int(time.time() * 1000)}_file_not_found",
                "timestamp": int(time.time() * 1000),
                "location": "rbi_agent_v3.py:execute_backtest",
                "message": "File not found error",
                "data": {"file_path": str(file_path)},
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "exec_3"
            }, f)
            f.write('\n')
        # #endregion
        raise FileNotFoundError(f"File not found: {file_path}")

    start_time = datetime.now()

    # Run the backtest with better Windows conda handling
    try:
        # #region agent log - environment check
        conda_python = r"C:\Users\Top Cash Pawn\AppData\Local\anaconda3\envs\tflow\python.exe"
        conda_bat = r"C:\Users\Top Cash Pawn\AppData\Local\anaconda3\condabin\conda.bat"
        conda_exe = r"C:\Users\Top Cash Pawn\AppData\Local\anaconda3\Scripts\conda.exe"

        with open(log_path, 'a', encoding='utf-8') as f:
            json.dump({
                "id": f"log_{int(time.time() * 1000)}_env_check",
                "timestamp": int(time.time() * 1000),
                "location": "rbi_agent_v3.py:execute_backtest",
                "message": "Conda environment check",
                "data": {
                    "os_name": os.name,
                    "conda_python_exists": os.path.exists(conda_python),
                    "conda_bat_exists": os.path.exists(conda_bat),
                    "conda_exe_exists": os.path.exists(conda_exe),
                    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
                },
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "exec_4"
            }, f)
            f.write('\n')
        # #endregion

        if os.name == 'nt':  # Windows
            # Try multiple conda approaches in order of preference

            # Method 1: Use Python executable directly from conda environment
            if os.path.exists(conda_python):
                cprint(f"[DEBUG] Using conda Python directly: {conda_python}", "yellow")
                # Execute Python script directly with conda environment's Python
                cmd = [
                    conda_python, str(file_path)
                ]

                # Debug: Print the exact command being executed
                cprint(f"[DEBUG] Command to execute: {cmd}", "cyan")

                # #region agent log - command setup
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        "id": f"log_{int(time.time() * 1000)}_cmd_setup",
                        "timestamp": int(time.time() * 1000),
                        "location": "rbi_agent_v3.py:execute_backtest",
                        "message": "Command setup for direct Python execution",
                        "data": {
                            "method": "direct_python",
                            "command": cmd,
                            "working_directory": os.getcwd()
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "exec_5"
                    }, f)
                    f.write('\n')
                # #endregion

                # #region agent log - subprocess execution
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        "id": f"log_{int(time.time() * 1000)}_subprocess_start",
                        "timestamp": int(time.time() * 1000),
                        "location": "rbi_agent_v3.py:execute_backtest",
                        "message": "Starting subprocess execution",
                        "data": {
                            "method": "direct_python",
                            "timeout": EXECUTION_TIMEOUT,
                            "start_time": datetime.now().isoformat()
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "exec_6"
                    }, f)
                    f.write('\n')
                # #endregion

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=EXECUTION_TIMEOUT
                )

                # #region agent log - subprocess result
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        "id": f"log_{int(time.time() * 1000)}_subprocess_result",
                        "timestamp": int(time.time() * 1000),
                        "location": "rbi_agent_v3.py:execute_backtest",
                        "message": "Subprocess execution completed",
                        "data": {
                            "returncode": result.returncode,
                            "stdout_length": len(result.stdout),
                            "stderr_length": len(result.stderr),
                            "execution_time": (datetime.now() - start_time).total_seconds(),
                            "timeout": EXECUTION_TIMEOUT
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "exec_7"
                    }, f)
                    f.write('\n')
                # #endregion

            # Method 2: Fallback to conda.bat with shell=True
            else:
                # #region agent log - fallback method
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        "id": f"log_{int(time.time() * 1000)}_fallback_method",
                        "timestamp": int(time.time() * 1000),
                        "location": "rbi_agent_v3.py:execute_backtest",
                        "message": "Using fallback conda.bat method",
                        "data": {"reason": "direct_python_not_found"},
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "exec_8"
                    }, f)
                    f.write('\n')
                # #endregion

                conda_bat = r"C:\Users\Top Cash Pawn\AppData\Local\anaconda3\condabin\conda.bat"
                if os.path.exists(conda_bat):
                    cprint(f"[DEBUG] Fallback: Using conda.bat: {conda_bat}", "yellow")
                    cmd = [
                        conda_bat, "run", "-n", CONDA_ENV, "python", str(file_path)
                    ]

                    # #region agent log - conda.bat command
                    with open(log_path, 'a', encoding='utf-8') as f:
                        json.dump({
                            "id": f"log_{int(time.time() * 1000)}_conda_bat_cmd",
                            "timestamp": int(time.time() * 1000),
                            "location": "rbi_agent_v3.py:execute_backtest",
                            "message": "Conda.bat command setup",
                            "data": {"command": cmd},
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "exec_9"
                        }, f)
                        f.write('\n')
                    # #endregion

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=EXECUTION_TIMEOUT,
                        shell=True
                    )
                else:
                    # Last resort - try conda.exe (known to be broken)
                    conda_exe = r"C:\Users\Top Cash Pawn\AppData\Local\anaconda3\Scripts\conda.exe"
                    cprint(f"[DEBUG] Last resort (likely to fail): Using conda.exe: {conda_exe}", "yellow")
                    cmd = [
                        conda_exe, "run", "-n", CONDA_ENV,
                        "python", str(file_path)
                    ]

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=EXECUTION_TIMEOUT
                    )
        else:
            # Unix-like systems
            cmd = [
                "conda", "run", "-n", CONDA_ENV,
                "python", str(file_path)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=EXECUTION_TIMEOUT
            )
    except Exception as e:
        # #region agent log - execution exception
        execution_time = (datetime.now() - start_time).total_seconds()
        with open(log_path, 'a', encoding='utf-8') as f:
            json.dump({
                "id": f"log_{int(time.time() * 1000)}_execution_exception",
                "timestamp": int(time.time() * 1000),
                "location": "rbi_agent_v3.py:execute_backtest",
                "message": "Exception during backtest execution",
                "data": {
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                    "execution_time": execution_time,
                    "traceback": traceback.format_exc()
                },
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "exec_10"
            }, f)
            f.write('\n')
        # #endregion

        # If all methods fail, return error info
        output = {
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Failed to execute conda command: {str(e)}",
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        }
        return output
    
    execution_time = (datetime.now() - start_time).total_seconds()

    output = {
        "success": result.returncode == 0,
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "execution_time": execution_time,
        "timestamp": datetime.now().isoformat()
    }

    # #region agent log - result analysis
    with open(log_path, 'a', encoding='utf-8') as f:
        json.dump({
            "id": f"log_{int(time.time() * 1000)}_result_analysis",
            "timestamp": int(time.time() * 1000),
            "location": "rbi_agent_v3.py:execute_backtest",
            "message": "Analyzing execution results",
            "data": {
                "success": output["success"],
                "return_code": output["return_code"],
                "stdout_length": len(output["stdout"]),
                "stderr_length": len(output["stderr"]),
                "execution_time": execution_time,
                "has_stderr": len(output["stderr"]) > 0,
                "has_stdout": len(output["stdout"]) > 0
            },
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "exec_11"
        }, f)
        f.write('\n')
    # #endregion
    
    # Save execution results
    result_file = EXECUTION_DIR / f"{strategy_name}_{datetime.now().strftime('%H%M%S')}.json"

    # #region agent log - result file save
    with open(log_path, 'a', encoding='utf-8') as f:
        json.dump({
            "id": f"log_{int(time.time() * 1000)}_result_save",
            "timestamp": int(time.time() * 1000),
            "location": "rbi_agent_v3.py:execute_backtest",
            "message": "Saving execution results to file",
            "data": {
                "result_file": str(result_file),
                "result_dir_exists": EXECUTION_DIR.exists(),
                "strategy_name": strategy_name
            },
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "exec_12"
        }, f)
        f.write('\n')
    # #endregion

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    # #region agent log - final output processing
    with open(log_path, 'a', encoding='utf-8') as f:
        json.dump({
            "id": f"log_{int(time.time() * 1000)}_final_processing",
            "timestamp": int(time.time() * 1000),
            "location": "rbi_agent_v3.py:execute_backtest",
            "message": "Final output processing and error analysis",
            "data": {
                "success": output['success'],
                "stdout_preview": output['stdout'][:200] + "..." if len(output['stdout']) > 200 else output['stdout'],
                "stderr_preview": output['stderr'][:200] + "..." if len(output['stderr']) > 200 else output['stderr'],
                "has_traceback": "Traceback" in output['stderr'],
                "has_attribute_error": "AttributeError" in output['stderr'],
                "has_importerror": "ImportError" in output['stderr'] or "ModuleNotFoundError" in output['stderr'],
                "has_value_error": "ValueError" in output['stderr']
            },
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "exec_13"
        }, f)
        f.write('\n')
    # #endregion

    # Print results
    if output['success']:
        cprint(f"✅ Backtest executed successfully in {execution_time:.2f}s!", "green")
        if output['stdout']:
            cprint("\n📊 BACKTEST RESULTS:", "green")
            print(output['stdout'])
    else:
        cprint(f"❌ Backtest failed with return code: {output['return_code']}", "red")
        if output['stderr']:
            cprint("\n🐛 ERRORS:", "red")
            print(output['stderr'])
    
    return output

def parse_execution_error(execution_result: dict) -> str:
    """Extract meaningful error message for debug agent"""
    # #region agent log - error parsing
    log_path = r"c:\Users\Top Cash Pawn\ITORO\.cursor\debug.log"
    with open(log_path, 'a', encoding='utf-8') as f:
        json.dump({
            "id": f"log_{int(time.time() * 1000)}_error_parsing",
            "timestamp": int(time.time() * 1000),
            "location": "rbi_agent_v3.py:parse_execution_error",
            "message": "Parsing execution error for debug agent",
            "data": {
                "has_stderr": bool(execution_result.get('stderr')),
                "stderr_length": len(execution_result.get('stderr', '')),
                "has_error_field": bool(execution_result.get('error')),
                "return_code": execution_result.get('return_code', 'unknown')
            },
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "error_1"
        }, f)
        f.write('\n')
    # #endregion

    if execution_result.get('stderr'):
        stderr = execution_result['stderr'].strip()

        # #region agent log - stderr analysis
        with open(log_path, 'a', encoding='utf-8') as f:
            json.dump({
                "id": f"log_{int(time.time() * 1000)}_stderr_analysis",
                "timestamp": int(time.time() * 1000),
                "location": "rbi_agent_v3.py:parse_execution_error",
                "message": "Analyzing stderr content",
                "data": {
                    "contains_traceback": "Traceback" in stderr,
                    "contains_attributeerror": "AttributeError" in stderr,
                    "contains_importerror": "ImportError" in stderr or "ModuleNotFoundError" in stderr,
                    "contains_valueerror": "ValueError" in stderr,
                    "contains_keyerror": "KeyError" in stderr,
                    "contains_syntaxerror": "SyntaxError" in stderr,
                    "first_line": stderr.split('\n')[0] if stderr else "No stderr"
                },
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "error_2"
            }, f)
            f.write('\n')
        # #endregion

        # Return the full stderr for better debugging context
        # This includes the full Python traceback, not just the conda error
        return stderr
    return execution_result.get('error', 'Unknown error')

def get_idea_hash(idea: str) -> str:
    """Generate a unique hash for an idea to track processing status"""
    # Create a hash of the idea to use as a unique identifier
    return hashlib.md5(idea.encode('utf-8')).hexdigest()

def is_idea_processed(idea: str) -> bool:
    """Check if an idea has already been processed"""
    if not PROCESSED_IDEAS_LOG.exists():
        return False
        
    idea_hash = get_idea_hash(idea)
    
    with open(PROCESSED_IDEAS_LOG, 'r', encoding='utf-8') as f:
        processed_hashes = [line.strip().split(',')[0] for line in f if line.strip()]
        
    return idea_hash in processed_hashes

def log_processed_idea(idea: str, strategy_name: str = "Unknown") -> None:
    """Log an idea as processed with timestamp and strategy name"""
    idea_hash = get_idea_hash(idea)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create the log file if it doesn't exist
    if not PROCESSED_IDEAS_LOG.exists():
        PROCESSED_IDEAS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PROCESSED_IDEAS_LOG, 'w', encoding='utf-8') as f:
            f.write("# Moon Dev's RBI AI - Processed Ideas Log 🌙\n")
            f.write("# Format: hash,timestamp,strategy_name,idea_snippet\n")

    # Add the entry
    idea_snippet = idea[:50].replace(',', ';') + ('...' if len(idea) > 50 else '')
    with open(PROCESSED_IDEAS_LOG, 'a', encoding='utf-8') as f:
        f.write(f"{idea_hash},{timestamp},{strategy_name},{idea_snippet}\n")
    
    cprint(f"[LIST] Logged processed idea: {strategy_name}", "green")

# Include all the original functions from v1
def init_deepseek_client():
    """Initialize DeepSeek client with proper error handling"""
    try:
        deepseek_key = os.getenv("DEEPSEEK_KEY")
        if not deepseek_key:
            cprint("[WARN] DEEPSEEK_KEY not found - DeepSeek models will not be available", "yellow")
            return None
            
        client = openai.OpenAI(
            api_key=deepseek_key,
            base_url=DEEPSEEK_BASE_URL
        )
        return client
    except Exception as e:
        print(f"❌ Error initializing DeepSeek client: {str(e)}")
        return None

def has_nan_results(execution_result: dict) -> bool:
    """Check if backtest results contain NaN values indicating no trades"""
    if not execution_result.get('success'):
        return False
        
    stdout = execution_result.get('stdout', '')
    
    # Look for indicators of no trades/NaN results
    nan_indicators = [
        '# Trades                                    0',
        'Win Rate [%]                              NaN',
        'Exposure Time [%]                         0.0',
        'Return [%]                                0.0'
    ]
    
    # Check if multiple NaN indicators are present
    nan_count = sum(1 for indicator in nan_indicators if indicator in stdout)
    return nan_count >= 2  # If 2+ indicators, likely no trades taken

def analyze_no_trades_issue(execution_result: dict) -> str:
    """Analyze why strategy shows signals but no trades"""
    stdout = execution_result.get('stdout', '')
    
    # Check if entry signals are being printed but no trades executed
    if 'ENTRY SIGNAL' in stdout and '# Trades                                    0' in stdout:
        return "Strategy is generating entry signals but self.buy() calls are not executing. This usually means: 1) Position sizing issues (size parameter invalid), 2) Insufficient cash/equity, 3) Logic preventing buy execution, or 4) Missing actual self.buy() call in the code. The strategy prints signals but never calls self.buy()."
    
    elif '# Trades                                    0' in stdout:
        return "Strategy executed but took 0 trades, resulting in NaN values. The entry conditions are likely too restrictive or there are logic errors preventing trade execution."
    
    return "Strategy executed but took 0 trades, resulting in NaN values. Please adjust the strategy logic to actually generate trading signals and take trades."

def chat_with_model(system_prompt, user_content, model_config):
    """Chat with AI model using model factory"""
    model = model_factory.get_model(model_config["type"], model_config["name"])
    if not model:
        raise ValueError(f"🚨 Could not initialize {model_config['type']} {model_config['name']} model!")

    cprint(f"[AI] Using {model_config['type']} model: {model_config['name']}", "cyan")
    
    if model_config["type"] == "ollama":
        response = model.generate_response(
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=AI_TEMPERATURE
        )
        if isinstance(response, str):
            return response
        if hasattr(response, 'content'):
            return response.content
        return str(response)
    else:
        response = model.generate_response(
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=AI_TEMPERATURE,
            max_tokens=AI_MAX_TOKENS
        )
        if not response:
            raise ValueError("Model returned None response")
        return response.content

def clean_model_output(output, content_type="text"):
    """Clean model output by removing thinking tags and extracting code from markdown"""
    cleaned_output = output
    
    # Remove thinking tags if present
    if "<think>" in output and "</think>" in output:
        clean_content = output.split("</think>")[-1].strip()
        if not clean_content:
            import re
            clean_content = re.sub(r'<think>.*?</think>', '', output, flags=re.DOTALL).strip()
        if clean_content:
            cleaned_output = clean_content
    
    # Extract code from markdown if needed
    if content_type == "code":
        try:
            import re

            # Debug: print what we're trying to extract from
            print(f"[DEBUG] Extracting code from response (first 200 chars): {cleaned_output[:200]}...")

            # Look for markdown code blocks
            if "```" in cleaned_output:
                # Try multiple patterns to extract code
                patterns = [
                    r'```python\s*\n(.*?)\n```',  # ```python\ncode\n```
                    r'```\s*\n(.*?)\n```',        # ```\ncode\n```
                    r'```python(.*?)```',          # ```pythoncode```
                    r'```(.*?)```',                # ```code```
                ]

                code_found = False
                for pattern in patterns:
                    code_blocks = re.findall(pattern, cleaned_output, re.DOTALL | re.IGNORECASE)
                    if code_blocks:
                        # Take the largest code block (usually the main one)
                        cleaned_output = max(code_blocks, key=len).strip()
                        print(f"[DEBUG] Extracted code using pattern: {pattern}")
                        code_found = True
                        break

                if not code_found:
                    print("[WARN] No code blocks found in markdown, using raw response")
                    # If no code blocks found, try to extract anything that looks like Python code
                    # Remove markdown formatting manually
                    lines = cleaned_output.split('\n')
                    code_lines = []
                    in_code_block = False

                    for line in lines:
                        if line.strip().startswith('```'):
                            in_code_block = not in_code_block
                            continue
                        if in_code_block:
                            code_lines.append(line)

                    if code_lines:
                        cleaned_output = '\n'.join(code_lines).strip()
                        print("[DEBUG] Extracted code by parsing markdown manually")
                    else:
                        print("[WARN] Could not extract code from response")
            else:
                print("[DEBUG] No markdown formatting found, using response as-is")

        except Exception as e:
            print(f"[ERROR] Code extraction failed: {str(e)}")
            # Return original output if extraction fails
            pass

    # Final cleanup: remove any remaining markdown artifacts
    if content_type == "code":
        cleaned_output = cleaned_output.strip()
        # Remove any leading/trailing ``` or ```python
        if cleaned_output.startswith('```'):
            lines = cleaned_output.split('\n')
            # Find first line that doesn't start with ```
            start_idx = 0
            for i, line in enumerate(lines):
                if not line.strip().startswith('```'):
                    start_idx = i
                    break
            cleaned_output = '\n'.join(lines[start_idx:])

        # Remove any trailing ```
        if cleaned_output.endswith('```'):
            lines = cleaned_output.split('\n')
            # Find last line that doesn't end with ```
            end_idx = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if not lines[i].strip().endswith('```'):
                    end_idx = i + 1
                    break
            cleaned_output = '\n'.join(lines[:end_idx])

        cleaned_output = cleaned_output.strip()

        # Validate that it looks like Python code
        if not (cleaned_output.startswith(('import', 'from', 'class', '#')) or 'class' in cleaned_output[:200]):
            print(f"[WARN] Extracted code doesn't look like Python: {cleaned_output[:100]}...")
        else:
            print("[DEBUG] Code extraction successful")
    
    return cleaned_output

def animate_progress(agent_name, stop_event):
    """Fun animation while AI is thinking"""
    spinners = ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘']
    messages = [
        "brewing coffee ☕️",
        "studying charts 📊",
        "checking signals 📡",
        "doing math 🔢",
        "reading docs 📚",
        "analyzing data 🔍",
        "making magic ✨",
        "trading secrets 🤫",
        "Moon Dev approved 🌙",
        "to the moon! 🚀"
    ]
    
    spinner = itertools.cycle(spinners)
    message = itertools.cycle(messages)
    
    while not stop_event.is_set():
        sys.stdout.write(f'\r{next(spinner)} {agent_name} is {next(message)}...')
        sys.stdout.flush()
        time.sleep(0.5)
    sys.stdout.write('\r' + ' ' * 50 + '\r')
    sys.stdout.flush()

def run_with_animation(func, agent_name, *args, **kwargs):
    """Run a function with a fun loading animation"""
    stop_animation = threading.Event()
    animation_thread = threading.Thread(target=animate_progress, args=(agent_name, stop_animation))
    
    try:
        animation_thread.start()
        result = func(*args, **kwargs)
        return result
    finally:
        stop_animation.set()
        animation_thread.join()

# Include all the other functions from v1 (research, backtest, package, etc.)
def research_strategy(content):
    """Research AI: Analyzes and creates trading strategy"""
    cprint("\n[SEARCH] Starting Research AI...", "cyan")
    
    output = run_with_animation(
        chat_with_model,
        "Research AI",
        RESEARCH_PROMPT, 
        content,
        RESEARCH_CONFIG
    )
    
    if output:
        output = clean_model_output(output, "text")
        
        # Extract strategy name
        strategy_name = "UnknownStrategy"
        if "STRATEGY_NAME:" in output:
            try:
                name_section = output.split("STRATEGY_NAME:")[1].strip()
                if "\n\n" in name_section:
                    strategy_name = name_section.split("\n\n")[0].strip()
                else:
                    strategy_name = name_section.split("\n")[0].strip()
                    
                strategy_name = re.sub(r'[^\w\s-]', '', strategy_name)
                strategy_name = re.sub(r'[\s]+', '', strategy_name)
                
                cprint(f"✅ Strategy name: {strategy_name}", "green")
            except Exception as e:
                cprint(f"[WARN] Error extracting strategy name: {str(e)}", "yellow")
        
        # Save research output
        filepath = RESEARCH_DIR / f"{strategy_name}_strategy.txt"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
        cprint(f"[LIST] Research saved to {filepath}", "green")
        return output, strategy_name
    return None, None

def create_backtest(strategy, strategy_name="UnknownStrategy", strategy_idea=None):
    """Backtest AI: Creates backtest implementation"""
    cprint("\n📊 Starting Backtest AI...", "cyan")

    # Customize the prompt based on data type needed
    data_type = determine_data_type_needed(strategy_idea) if strategy_idea else "indicator"
    customized_prompt = customize_backtest_prompt_for_data_type(BACKTEST_PROMPT, data_type)

    output = run_with_animation(
        chat_with_model,
        "Backtest AI",
        customized_prompt,
        f"Create a backtest for this strategy:\n\n{strategy}",
        BACKTEST_CONFIG
    )
    
    if output:
        output = clean_model_output(output, "code")
        
        filepath = BACKTEST_DIR / f"{strategy_name}_BT.py"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
        cprint(f"🔥 Backtest saved to {filepath}", "green")
        return output
    return None

def package_check(backtest_code, strategy_name="UnknownStrategy"):
    """Package AI: Ensures correct indicator packages are used"""
    cprint("\n📦 Starting Package AI...", "cyan")
    
    output = run_with_animation(
        chat_with_model,
        "Package AI",
        PACKAGE_PROMPT,
        f"Check and fix indicator packages in this code:\n\n{backtest_code}",
        PACKAGE_CONFIG
    )
    
    if output:
        output = clean_model_output(output, "code")
        
        filepath = PACKAGE_DIR / f"{strategy_name}_PKG.py"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
        cprint(f"📦 Package-fixed code saved to {filepath}", "green")
        return output
    return None

def debug_backtest(backtest_code, error_message, strategy_name="UnknownStrategy", iteration=1):
    """Debug AI: Fixes technical issues in backtest code"""
    cprint(f"\n🔧 Starting Debug AI (iteration {iteration})...", "cyan")
    cprint(f"🐛 Error to fix: {error_message}", "yellow")

    # Ensure directories exist
    FINAL_BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

    # Create debug prompt with specific error
    debug_prompt_with_error = DEBUG_PROMPT.format(error_message=error_message)

    output = run_with_animation(
        chat_with_model,
        "Debug AI",
        debug_prompt_with_error,
        f"Fix this backtest code:\n\n{backtest_code}",
        DEBUG_CONFIG
    )

    if output:
        output = clean_model_output(output, "code")

        filepath = FINAL_BACKTEST_DIR / f"{strategy_name}_BTFinal_v{iteration}.py"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
        cprint(f"🔧 Debugged code saved to {filepath}", "green")
        return output
    return None

def optimize_strategy(backtest_code, current_return, target_return, strategy_name="UnknownStrategy", iteration=1):
    """Optimization AI: Improves strategy to hit target return"""
    cprint(f"\n[TARGET] Starting Optimization AI (iteration {iteration})...", "cyan")
    cprint(f"[CHART] Current Return: {current_return}%", "yellow")
    cprint(f"[TARGET] Target Return: {target_return}%", "green")
    cprint(f"[UP] Gap to close: {target_return - current_return}%", "magenta")

    # Create optimization prompt with current performance
    optimize_prompt_with_stats = OPTIMIZE_PROMPT.format(
        current_return=current_return,
        target_return=target_return
    )

    output = run_with_animation(
        chat_with_model,
        "Optimization AI",
        optimize_prompt_with_stats,
        f"Optimize this backtest code to hit the target:\n\n{backtest_code}",
        OPTIMIZE_CONFIG
    )

    if output:
        output = clean_model_output(output, "code")

        filepath = OPTIMIZATION_DIR / f"{strategy_name}_OPT_v{iteration}.py"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
        cprint(f"[TARGET] Optimized code saved to {filepath}", "green")
        return output
    return None

def process_trading_idea_with_execution(idea: str) -> None:
    """
    THE NEW V3.0 PROCESS WITH OPTIMIZATION LOOP! 🚀🎯
    Research -> Backtest -> Package -> Execute -> Debug (loop) -> OPTIMIZE (loop) -> Target Hit!
    """
    print("\n[ROCKET] Moon Dev's RBI AI v3.0 Processing New Idea!")
    print("[TARGET] Now with OPTIMIZATION LOOP!")
    print(f"[TARGET] Target Return: {TARGET_RETURN}%")
    print(f"[LIST] Processing idea: {idea[:100]}...")

    # Check if we have the required data for this strategy type
    data_type = determine_data_type_needed(idea)
    print(f"[DEBUG] Data type determined: {data_type}")
    print(f"[DEBUG] About to call ensure_rbi_data_exists()")
    
    # Write to file before calling ensure_rbi_data_exists
    try:
        pre_call_file = open(r"c:\Users\Top Cash Pawn\ITORO\.cursor\pre_call.txt", "w", encoding='utf-8')
        pre_call_file.write(f"About to call ensure_rbi_data_exists\nData type: {data_type}\n")
        pre_call_file.close()
    except Exception as e:
        print(f"[DEBUG] Pre-call file write failed: {e}")
    
    result = ensure_rbi_data_exists(idea)
    print(f"[DEBUG] ensure_rbi_data_exists() returned: {result}")
    
    if not result:
        print(f"❌ Required {data_type} data not available for this strategy type. Skipping.")
        return

    # Phase 1: Research
    print("\n🧪 Phase 1: Research")
    # For this example, using the idea directly
    strategy, strategy_name = research_strategy(idea)
    
    if not strategy:
        raise ValueError("Research phase failed - no strategy generated")
        
    print(f"🏷️ Strategy Name: {strategy_name}")
    
    # Log the idea as processed once we have a strategy name
    log_processed_idea(idea, strategy_name)
    
    # Phase 2: Backtest
    print("\n📈 Phase 2: Backtest")
    backtest = create_backtest(strategy, strategy_name, idea)
    
    if not backtest:
        raise ValueError("Backtest phase failed - no code generated")
    
    # Phase 3: Package Check
    print("\n📦 Phase 3: Package Check")
    package_checked = package_check(backtest, strategy_name)
    
    if not package_checked:
        raise ValueError("Package check failed - no fixed code generated")
    
    # Save the package-checked version
    package_file = PACKAGE_DIR / f"{strategy_name}_PKG.py"
    
    # Phase 4: EXECUTION LOOP! 🔄
    print("\n🔄 Phase 4: Execution Loop")
    
    debug_iteration = 0
    current_code = package_checked
    current_file = package_file
    error_history = []  # Track previous errors to detect loops
    
    while debug_iteration < MAX_DEBUG_ITERATIONS:
        # #region agent log - debug iteration start
        log_path = r"c:\Users\Top Cash Pawn\ITORO\.cursor\debug.log"
        with open(log_path, 'a', encoding='utf-8') as f:
            json.dump({
                "id": f"log_{int(time.time() * 1000)}_debug_iteration_start",
                "timestamp": int(time.time() * 1000),
                "location": "rbi_agent_v3.py:main_execution_loop",
                "message": f"Starting debug iteration {debug_iteration + 1}",
                "data": {
                    "iteration": debug_iteration + 1,
                    "max_iterations": MAX_DEBUG_ITERATIONS,
                    "current_file": str(current_file),
                    "strategy_name": strategy_name,
                    "error_history_count": len(error_history)
                },
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "loop_1"
            }, f)
            f.write('\n')
        # #endregion

        # Execute the current code
        print(f"\n[ROCKET] Execution attempt {debug_iteration + 1}/{MAX_DEBUG_ITERATIONS}")
        execution_result = execute_backtest(current_file, strategy_name)
        
        if execution_result['success']:
            # #region agent log - execution success
            with open(log_path, 'a', encoding='utf-8') as f:
                json.dump({
                    "id": f"log_{int(time.time() * 1000)}_execution_success",
                    "timestamp": int(time.time() * 1000),
                    "location": "rbi_agent_v3.py:main_execution_loop",
                    "message": "Backtest execution succeeded",
                    "data": {
                        "iteration": debug_iteration + 1,
                        "execution_time": execution_result.get('execution_time', 0),
                        "stdout_length": len(execution_result.get('stdout', ''))
                    },
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "loop_2"
                }, f)
                f.write('\n')
            # #endregion

            # Check if results have NaN values (no trades taken)
            if has_nan_results(execution_result):
                # #region agent log - nan results detected
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        "id": f"log_{int(time.time() * 1000)}_nan_results",
                        "timestamp": int(time.time() * 1000),
                        "location": "rbi_agent_v3.py:main_execution_loop",
                        "message": "NaN results detected - no trades taken",
                        "data": {"iteration": debug_iteration + 1},
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "loop_3"
                    }, f)
                    f.write('\n')
                # #endregion

                print("\n⚠️ BACKTEST EXECUTED BUT NO TRADES TAKEN (NaN results)")
                print("🔧 Sending to Debug AI to fix strategy logic...")
                
                # Analyze the specific no-trades issue
                error_message = analyze_no_trades_issue(execution_result)
                
                debug_iteration += 1
                
                if debug_iteration < MAX_DEBUG_ITERATIONS:
                    debugged_code = debug_backtest(
                        current_code, 
                        error_message, 
                        strategy_name, 
                        debug_iteration
                    )
                    
                    if not debugged_code:
                        raise ValueError("Debug AI failed to generate fixed code")
                        
                    current_code = debugged_code
                    current_file = FINAL_BACKTEST_DIR / f"{strategy_name}_BTFinal_v{debug_iteration}.py"
                    print("🔄 Retrying with debugged code...")
                    continue
                else:
                    print(f"\n❌ Max debug iterations ({MAX_DEBUG_ITERATIONS}) reached - strategy still not taking trades")
                    print("🔄 Moving to next idea...")
                    return  # Move to next idea instead of crashing
            else:
                # SUCCESS! Code executes with trades! 🎉
                print("\n🎉 BACKTEST EXECUTED SUCCESSFULLY WITH TRADES!")

                # Extract the return %
                current_return = parse_return_from_output(execution_result['stdout'])

                if current_return is None:
                    print("⚠️ Could not parse return % - saving as working version")
                    final_file = FINAL_BACKTEST_DIR / f"{strategy_name}_BTFinal_WORKING.py"
                    with open(final_file, 'w', encoding='utf-8') as f:
                        f.write(current_code)
                    print(f"✅ Final working backtest saved to: {final_file}")
                    break

                # Check if we hit the target!
                print(f"\n📊 Current Return: {current_return}%")
                print(f"[TARGET] Target Return: {TARGET_RETURN}%")

                if current_return >= TARGET_RETURN:
                    # WE HIT THE TARGET! 🚀🚀🚀
                    print("\n[ROCKET][ROCKET][ROCKET] TARGET RETURN ACHIEVED! [ROCKET][ROCKET][ROCKET]")
                    print(f"🎉 Strategy returned {current_return}% (target was {TARGET_RETURN}%)")

                    # Save as TARGET_HIT version
                    final_file = OPTIMIZATION_DIR / f"{strategy_name}_TARGET_HIT_{current_return}pct.py"
                    with open(final_file, 'w', encoding='utf-8') as f:
                        f.write(current_code)

                    print(f"✅ Target-hitting backtest saved to: {final_file}")
                    break
                else:
                    # Need to optimize! 🎯
                    gap = TARGET_RETURN - current_return
                    print(f"\n📈 Need to gain {gap}% more to hit target")
                    print(f"[TARGET] Starting OPTIMIZATION LOOP...")

                    # Save the working version
                    working_file = FINAL_BACKTEST_DIR / f"{strategy_name}_BTFinal_WORKING_{current_return}pct.py"
                    with open(working_file, 'w', encoding='utf-8') as f:
                        f.write(current_code)
                    print(f"💾 Saved working version: {working_file}")

                    # 🎯🎯🎯 OPTIMIZATION LOOP! 🎯🎯🎯
                    # This is the magic of v3.0!
                    # Agent will keep improving the strategy until TARGET_RETURN is hit
                    # Each iteration: Optimize → Execute → Check Return → Repeat
                    optimization_iteration = 0
                    optimization_code = current_code
                    best_return = current_return
                    best_code = current_code

                    while optimization_iteration < MAX_OPTIMIZATION_ITERATIONS:
                        optimization_iteration += 1
                        print(f"\n🔄 Optimization attempt {optimization_iteration}/{MAX_OPTIMIZATION_ITERATIONS}")

                        # Optimize the strategy
                        optimized_code = optimize_strategy(
                            optimization_code,
                            best_return,
                            TARGET_RETURN,
                            strategy_name,
                            optimization_iteration
                        )

                        if not optimized_code:
                            print("❌ Optimization AI failed to generate code")
                            break

                        # Save and execute the optimized version
                        opt_file = OPTIMIZATION_DIR / f"{strategy_name}_OPT_v{optimization_iteration}.py"
                        opt_result = execute_backtest(opt_file, strategy_name)

                        if not opt_result['success']:
                            print(f"⚠️ Optimized code failed to execute, trying again...")
                            continue

                        if has_nan_results(opt_result):
                            print(f"⚠️ Optimized code has no trades, trying again...")
                            continue

                        # Parse the new return
                        new_return = parse_return_from_output(opt_result['stdout'])

                        if new_return is None:
                            print(f"⚠️ Could not parse return, trying again...")
                            continue

                        print(f"\n📊 Optimization Result:")
                        print(f"  Previous: {best_return}%")
                        print(f"  New:      {new_return}%")
                        print(f"  Change:   {new_return - best_return:+.2f}%")

                        # Check if we improved
                        if new_return > best_return:
                            print(f"✅ IMPROVEMENT! Return increased by {new_return - best_return:.2f}%")
                            best_return = new_return
                            best_code = optimized_code
                            optimization_code = optimized_code  # Use improved version for next iteration

                            # Did we hit the target?
                            if new_return >= TARGET_RETURN:
                                print("\n🚀🚀🚀 TARGET RETURN ACHIEVED THROUGH OPTIMIZATION! 🚀🚀🚀")
                                print(f"🎉 Strategy returned {new_return}% (target was {TARGET_RETURN}%)")
                                print(f"💪 Took {optimization_iteration} optimization iterations!")

                                # Save as TARGET_HIT version
                                final_file = OPTIMIZATION_DIR / f"{strategy_name}_TARGET_HIT_{new_return}pct.py"
                                with open(final_file, 'w', encoding='utf-8') as f:
                                    f.write(best_code)

                                print(f"✅ Target-hitting backtest saved to: {final_file}")
                                return  # DONE!
                        else:
                            print(f"⚠️ No improvement. Trying different optimization approach...")

                    # Maxed out optimization attempts
                    print(f"\n⚠️ Reached max optimization iterations ({MAX_OPTIMIZATION_ITERATIONS})")
                    print(f"📊 Best return achieved: {best_return}% (target was {TARGET_RETURN}%)")
                    print(f"📈 Gap remaining: {TARGET_RETURN - best_return}%")

                    # Save best version
                    best_file = OPTIMIZATION_DIR / f"{strategy_name}_BEST_{best_return}pct.py"
                    with open(best_file, 'w', encoding='utf-8') as f:
                        f.write(best_code)
                    print(f"💾 Saved best version: {best_file}")
                    return  # Move to next idea
            
        else:
            # #region agent log - execution failure
            with open(log_path, 'a', encoding='utf-8') as f:
                json.dump({
                    "id": f"log_{int(time.time() * 1000)}_execution_failure",
                    "timestamp": int(time.time() * 1000),
                    "location": "rbi_agent_v3.py:main_execution_loop",
                    "message": "Backtest execution failed",
                    "data": {
                        "iteration": debug_iteration + 1,
                        "return_code": execution_result.get('return_code', 'unknown'),
                        "stderr_length": len(execution_result.get('stderr', '')),
                        "execution_time": execution_result.get('execution_time', 0)
                    },
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "loop_4"
                }, f)
                f.write('\n')
            # #endregion

            # Extract error and debug
            error_message = parse_execution_error(execution_result)
            print(f"\n🐛 Execution failed with error: {error_message}")
            
            # Check for repeated errors (infinite loop detection)
            error_signature = error_message.split('\n')[-1] if '\n' in error_message else error_message
            if error_signature in error_history:
                print(f"\n🔄 DETECTED REPEATED ERROR: {error_signature}")
                print("🛑 Breaking loop to prevent infinite debugging")
                raise ValueError(f"Repeated error detected after {debug_iteration + 1} attempts: {error_signature}")
            
            error_history.append(error_signature)
            debug_iteration += 1
            
            if debug_iteration < MAX_DEBUG_ITERATIONS:
                # #region agent log - debug AI call
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        "id": f"log_{int(time.time() * 1000)}_debug_ai_call",
                        "timestamp": int(time.time() * 1000),
                        "location": "rbi_agent_v3.py:main_execution_loop",
                        "message": f"Sending to Debug AI (attempt {debug_iteration})",
                        "data": {
                            "iteration": debug_iteration,
                            "error_message_length": len(error_message),
                            "error_signature": error_message.split('\n')[-1] if '\n' in error_message else error_message[:100]
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "loop_5"
                    }, f)
                    f.write('\n')
                # #endregion

                # Debug the code
                print(f"\n🔧 Sending to Debug AI (attempt {debug_iteration})...")
                debugged_code = debug_backtest(
                    current_code,
                    error_message,
                    strategy_name,
                    debug_iteration
                )
                
                if not debugged_code:
                    raise ValueError("Debug AI failed to generate fixed code")
                    
                current_code = debugged_code
                current_file = FINAL_BACKTEST_DIR / f"{strategy_name}_BTFinal_v{debug_iteration}.py"
                print("🔄 Retrying with debugged code...")
            else:
                # #region agent log - max debug iterations reached
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        "id": f"log_{int(time.time() * 1000)}_max_debug_iterations",
                        "timestamp": int(time.time() * 1000),
                        "location": "rbi_agent_v3.py:main_execution_loop",
                        "message": f"Max debug iterations ({MAX_DEBUG_ITERATIONS}) reached - could not fix code",
                        "data": {
                            "final_iteration": debug_iteration,
                            "error_history_count": len(error_history),
                            "last_error_signature": error_history[-1] if error_history else "none"
                        },
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "loop_6"
                    }, f)
                    f.write('\n')
                # #endregion

                print(f"\n❌ Max debug iterations ({MAX_DEBUG_ITERATIONS}) reached - could not fix code")
                print("🔄 Moving to next idea...")
                return  # Move to next idea instead of crashing
    
    print("\n✨ Processing complete!")

def ensure_rbi_data_exists(strategy_idea=None):
    """Ensure RBI backtest data exists, collect if missing. Now supports multiple data types."""
    # Determine what type of data we need based on strategy
    data_type = determine_data_type_needed(strategy_idea)

    # ALL strategies need OHLCV data for backtesting.py framework
    cprint("[OHLCV] Ensuring OHLCV data exists for all strategies...", "cyan")
    print(f"[DEBUG] ensure_rbi_data_exists: About to call ensure_ohlcv_data_exists()")
    
    # Write to file before calling
    try:
        pre_ohlcv_file = open(r"c:\Users\Top Cash Pawn\ITORO\.cursor\pre_ohlcv_call.txt", "w", encoding='utf-8')
        pre_ohlcv_file.write(f"About to call ensure_ohlcv_data_exists\n")
        pre_ohlcv_file.close()
    except Exception as e:
        print(f"[DEBUG] Pre-OHLCV call file write failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        ohlcv_ok = ensure_ohlcv_data_exists()
        print(f"[DEBUG] ensure_ohlcv_data_exists() returned: {ohlcv_ok}")
    except Exception as e:
        print(f"[DEBUG] Exception in ensure_ohlcv_data_exists(): {e}")
        import traceback
        traceback.print_exc()
        ohlcv_ok = False
    
    if not ohlcv_ok:
        cprint("[ERROR] Failed to ensure OHLCV data exists", "red")
        return False

    # Now check for strategy-specific data
    if data_type == "indicator":
        # For indicator strategies, OHLCV data is sufficient (already checked above)
        return True
    elif data_type == "oi":
        # For OI strategies, we need OI data in addition to OHLCV
        return ensure_oi_data_exists()
    elif data_type == "funding":
        # For funding strategies, we need funding rate data in addition to OHLCV
        return ensure_funding_data_exists()
    elif data_type == "liquidation":
        # For liquidation strategies, we need liquidation data in addition to OHLCV
        return ensure_liquidation_data_exists()
    elif data_type == "onchain":
        # For onchain strategies, we need onchain data in addition to OHLCV
        return ensure_onchain_data_exists()
    else:
        # Default to OHLCV for unknown strategy types (already checked above)
        cprint(f"[INFO] Unknown strategy type '{data_type}', OHLCV data ensured", "yellow")
        return True


def determine_data_type_needed(strategy_idea):
    """Determine what type of data is needed based on the strategy idea"""
    if not strategy_idea:
        return "indicator"  # Default

    idea_lower = strategy_idea.lower()

    # OI-based strategies
    if any(keyword in idea_lower for keyword in ['oi', 'open interest', 'institutional', 'accumulation', 'distribution']):
        return "oi"

    # Funding-based strategies
    if any(keyword in idea_lower for keyword in ['funding', 'funding rate', 'arbitrage']):
        return "funding"

    # Liquidation-based strategies
    if any(keyword in idea_lower for keyword in ['liquidation', 'liquidation cascade', 'liquidation reversal']):
        return "liquidation"

    # Onchain-based strategies
    if any(keyword in idea_lower for keyword in ['whale', 'holder', 'onchain', 'transaction', 'blockchain']):
        return "onchain"

    # Default to indicator-based
    return "indicator"


def ensure_ohlcv_data_exists():
    """Ensure OHLCV data exists for indicator-based strategies"""
    from pathlib import Path  # Import at the start to avoid UnboundLocalError

    # IMMEDIATE file write to verify function is called
    try:
        immediate_log = Path(r"c:\Users\Top Cash Pawn\ITORO\.cursor\function_called.txt")
        immediate_log.parent.mkdir(parents=True, exist_ok=True)
        immediate_log.write_text(f"Function called at {__import__('time').time()}\nPROJECT_ROOT: {PROJECT_ROOT}", encoding='utf-8')
    except Exception as e:
        print(f"[CRITICAL] Immediate log write failed: {e}")
        import traceback
        traceback.print_exc()
    
    cprint("[INDICATOR] Checking for OHLCV data (candlesticks)...", "cyan")
    print(f"[DEBUG] ensure_ohlcv_data_exists() called - PROJECT_ROOT: {PROJECT_ROOT}")
    
    # Test file write to verify I/O works
    try:
        test_file = Path(r"c:\Users\Top Cash Pawn\ITORO\.cursor\test_write.txt")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("test", encoding='utf-8')
        print(f"[DEBUG] Test file write successful: {test_file}")
    except Exception as e:
        print(f"[DEBUG] Test file write failed: {e}")
        import traceback
        traceback.print_exc()

    # #region agent log
    import json
    import os
    log_entry = {
        "id": f"log_{int(__import__('time').time() * 1000)}_function_entry",
        "timestamp": int(__import__('time').time() * 1000),
        "location": "rbi_agent_v3.py:ensure_ohlcv_data_exists",
        "message": "Function entry - checking PROJECT_ROOT",
        "data": {
            "project_root": str(PROJECT_ROOT),
            "project_root_absolute": str(PROJECT_ROOT.resolve()),
            "__file__": str(Path(__file__)),
            "__file__parent": str(Path(__file__).parent),
            "__file__parent_parent": str(Path(__file__).parent.parent),
            "cwd": os.getcwd()
        },
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "A"
    }
    # Use absolute path to workspace root .cursor/debug.log
    # Calculate workspace root: go up 5 levels from agents/rbi_agent_v3.py
    workspace_root = Path(__file__).parent.parent.parent.parent.parent
    log_path = workspace_root / ".cursor" / "debug.log"
    # Debug: print the calculated path
    print(f"[DEBUG] Log path calculated: {log_path}")
    print(f"[DEBUG] Log path absolute: {log_path.resolve()}")
    print(f"[DEBUG] Workspace root: {workspace_root}")
    print(f"[DEBUG] Workspace root exists: {workspace_root.exists()}")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        # Print error to console for debugging
        print(f"[DEBUG] Failed to write log: {e}")
        print(f"[DEBUG] Log path attempted: {log_path}")
        print(f"[DEBUG] Log path absolute: {log_path.resolve()}")
        pass
    # #endregion

    RBI_DATA_SYMBOLS = ['BTC', 'ETH', 'SOL']
    data_dir = PROJECT_ROOT / "data" / "rbi"
    
    # #region agent log
    log_entry = {
        "id": f"log_{int(__import__('time').time() * 1000)}_data_dir_resolved",
        "timestamp": int(__import__('time').time() * 1000),
        "location": "rbi_agent_v3.py:ensure_ohlcv_data_exists",
        "message": "Data directory path resolved",
        "data": {
            "data_dir": str(data_dir),
            "data_dir_absolute": str(data_dir.resolve()),
            "data_dir_exists": data_dir.exists(),
            "data_dir_is_dir": data_dir.is_dir() if data_dir.exists() else False
        },
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "A"
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f"[DEBUG] Failed to write log: {e}")
        pass
    # #endregion
    
    data_dir.mkdir(parents=True, exist_ok=True)

    # #region agent log
    # List actual files in directory
    actual_files = []
    if data_dir.exists() and data_dir.is_dir():
        try:
            actual_files = [f.name for f in data_dir.iterdir() if f.is_file()]
        except:
            pass
    log_entry = {
        "id": f"log_{int(__import__('time').time() * 1000)}_directory_contents",
        "timestamp": int(__import__('time').time() * 1000),
        "location": "rbi_agent_v3.py:ensure_ohlcv_data_exists",
        "message": "Directory contents before check",
        "data": {
            "data_dir": str(data_dir),
            "actual_files": actual_files,
            "file_count": len(actual_files)
        },
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "C"
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f"[DEBUG] Failed to write log: {e}")
        pass
    # #endregion

    missing_data = []
    for symbol in RBI_DATA_SYMBOLS:
        data_file = data_dir / f"{symbol}-USD-15m.csv"
        
        # #region agent log
        log_entry = {
            "id": f"log_{int(__import__('time').time() * 1000)}_file_check_{symbol}",
            "timestamp": int(__import__('time').time() * 1000),
            "location": "rbi_agent_v3.py:ensure_ohlcv_data_exists",
            "message": f"Checking file existence for {symbol}",
            "data": {
                "symbol": symbol,
                "data_file": str(data_file),
                "data_file_absolute": str(data_file.resolve()),
                "file_exists": data_file.exists(),
                "file_is_file": data_file.is_file() if data_file.exists() else False
            },
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "B"
        }
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except:
            pass
        # #endregion
        
        if not data_file.exists():
            missing_data.append(symbol)

    if missing_data:
        cprint(f"[WARN] Missing OHLCV data for: {', '.join(missing_data)}", "yellow")
        cprint("[COLLECT] Collecting OHLCV data via collector...", "cyan")

        try:
            # #region agent log
            import json
            import os
            from pathlib import Path
            log_entry = {
                "id": f"log_{int(__import__('time').time() * 1000)}_import_attempt",
                "timestamp": int(__import__('time').time() * 1000),
                "location": "rbi_agent_v3.py:ensure_ohlcv_data_exists",
                "message": "Attempting to import collector",
                "data": {
                    "python_path": __import__('sys').path[:3],
                    "working_dir": os.getcwd(),
                    "pandas_available": "pandas" in __import__('sys').modules
                },
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "B"
            }
            # Use absolute path to workspace root .cursor/debug.log
            # Calculate workspace root: go up 5 levels from agents/rbi_agent_v3.py
            workspace_root = Path(__file__).parent.parent.parent.parent.parent
            log_path = workspace_root / ".cursor" / "debug.log"
            # Debug: print the calculated path
            print(f"[DEBUG] Log path calculated: {log_path}")
            print(f"[DEBUG] Log path absolute: {log_path.resolve()}")
            print(f"[DEBUG] Workspace root: {workspace_root}")
            print(f"[DEBUG] Workspace root exists: {workspace_root.exists()}")
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry) + '\n')
            except Exception as e:
                print(f"[DEBUG] Failed to write log: {e}")
                pass
            # #endregion

            # Import the collector function directly since we're in the same environment
            from scripts.shared_services.ohlcv_collector import collect_rbi_data

            # Call the data collection function
            cprint("[COLLECT] Starting OHLCV data collection via collector...", "cyan")
            rbi_data = collect_rbi_data()

            if rbi_data and len(rbi_data) > 0:
                cprint("[SUCCESS] OHLCV data collection completed!", "green")

                # Verify files were actually created
                collected_files = []
                for symbol in RBI_DATA_SYMBOLS:
                    data_file = data_dir / f"{symbol}-USD-15m.csv"
                    if data_file.exists():
                        collected_files.append(symbol)

                if collected_files:
                    cprint(f"[VERIFY] Confirmed OHLCV data files created for: {', '.join(collected_files)}", "green")
                    return True
                else:
                    cprint("[ERROR] OHLCV collection completed but no files were found", "red")
                    return False
            else:
                cprint("[ERROR] OHLCV data collection returned no data", "red")
                cprint("[WARN] Creating synthetic OHLCV data for testing purposes", "yellow")

                # #region agent log
                import json
                import os
                from pathlib import Path
                log_entry = {
                    "id": f"log_{int(__import__('time').time() * 1000)}_synthetic_start",
                    "timestamp": int(__import__('time').time() * 1000),
                    "location": "rbi_agent_v3.py:synthetic_data_generation",
                    "message": "Starting synthetic data generation",
                    "data": {
                        "symbols": RBI_DATA_SYMBOLS,
                        "data_dir": str(data_dir)
                    },
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "C"
                }
                # Use absolute path to workspace root .cursor/debug.log
                # Calculate workspace root: go up 5 levels from agents/rbi_agent_v3.py
                workspace_root = Path(__file__).parent.parent.parent.parent.parent
                log_path = workspace_root / ".cursor" / "debug.log"
                # Debug: print the calculated path
                print(f"[DEBUG] Log path calculated: {log_path}")
                print(f"[DEBUG] Log path absolute: {log_path.resolve()}")
                print(f"[DEBUG] Workspace root: {workspace_root}")
                print(f"[DEBUG] Workspace root exists: {workspace_root.exists()}")
                try:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(log_path, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(log_entry) + '\n')
                except Exception as e:
                    print(f"[DEBUG] Failed to write log: {e}")
                    pass
                # #endregion

                # Create synthetic OHLCV data for testing
                try:
                    import pandas as pd
                    from datetime import datetime, timedelta
                    import numpy as np

                    # Create synthetic data for the past 30 days, 15-minute intervals
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=30)

                    # Generate timestamps (15-minute intervals)
                    timestamps = []
                    current = start_date
                    while current <= end_date:
                        timestamps.append(current)
                        current += timedelta(minutes=15)

                    # Create synthetic OHLCV data
                    np.random.seed(42)  # For reproducible results
                    base_price = 95000  # BTC around $95K

                    synthetic_data = []
                    for i, ts in enumerate(timestamps):
                        # Add some trend and volatility
                        trend = (i / len(timestamps)) * 5000  # Upward trend
                        noise = np.random.normal(0, 1000)  # Random noise
                        price = base_price + trend + noise

                        # Create OHLC with some spread
                        spread = np.random.uniform(50, 200)
                        high = price + spread/2
                        low = price - spread/2
                        open_price = price + np.random.uniform(-spread/4, spread/4)
                        close_price = price + np.random.uniform(-spread/4, spread/4)

                        # Volume and open interest
                        volume = np.random.uniform(100, 1000)
                        open_interest = 22845.72232  # Same as real data

                        synthetic_data.append({
                            'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                            'open': round(open_price, 2),
                            'high': round(high, 2),
                            'low': round(low, 2),
                            'close': round(close_price, 2),
                            'volume': round(volume, 6),
                            'open_interest': open_interest
                        })

                    # Save synthetic data for each symbol
                    df = pd.DataFrame(synthetic_data)
                    for symbol in RBI_DATA_SYMBOLS:
                        data_file = data_dir / f"{symbol}-USD-15m.csv"
                        df.to_csv(data_file, index=False)
                        cprint(f"[SYNTHETIC] Created {len(df)} rows of synthetic data for {symbol}", "cyan")

                    cprint("[SUCCESS] Synthetic OHLCV data created for testing", "green")
                    return True

                except Exception as synth_error:
                    cprint(f"[ERROR] Failed to create synthetic data: {str(synth_error)}", "red")
                    return False

        except Exception as e:
            cprint(f"[ERROR] Failed to collect OHLCV data: {str(e)}", "red")
            cprint("[WARN] Creating synthetic OHLCV data for testing purposes", "yellow")

            # Create synthetic OHLCV data for testing
            try:
                import pandas as pd
                from datetime import datetime, timedelta

                # Create synthetic data for the past 30 days, 15-minute intervals
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)

                # Generate timestamps (15-minute intervals)
                timestamps = []
                current = start_date
                while current <= end_date:
                    timestamps.append(current)
                    current += timedelta(minutes=15)

                # Create synthetic OHLCV data
                np.random.seed(42)  # For reproducible results
                base_price = 95000  # BTC around $95K

                synthetic_data = []
                for i, ts in enumerate(timestamps):
                    # Add some trend and volatility
                    trend = (i / len(timestamps)) * 5000  # Upward trend
                    noise = np.random.normal(0, 1000)  # Random noise
                    price = base_price + trend + noise

                    # Create OHLC with some spread
                    spread = np.random.uniform(50, 200)
                    high = price + spread/2
                    low = price - spread/2
                    open_price = price + np.random.uniform(-spread/4, spread/4)
                    close_price = price + np.random.uniform(-spread/4, spread/4)

                    # Volume and open interest
                    volume = np.random.uniform(100, 1000)
                    open_interest = 22845.72232  # Same as real data

                    synthetic_data.append({
                        'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                        'open': round(open_price, 2),
                        'high': round(high, 2),
                        'low': round(low, 2),
                        'close': round(close_price, 2),
                        'volume': round(volume, 6),
                        'open_interest': open_interest
                    })

                # Save synthetic data for each symbol
                df = pd.DataFrame(synthetic_data)
                for symbol in RBI_DATA_SYMBOLS:
                    data_file = data_dir / f"{symbol}-USD-15m.csv"
                    df.to_csv(data_file, index=False)
                    cprint(f"[SYNTHETIC] Created {len(df)} rows of synthetic data for {symbol}", "cyan")

                cprint("[SUCCESS] Synthetic OHLCV data created for testing", "green")
                return True

            except Exception as synth_error:
                cprint(f"[ERROR] Failed to create synthetic data: {str(synth_error)}", "red")
                return False
    else:
        cprint("[SUCCESS] All OHLCV data files exist!", "green")
        return True


def ensure_oi_data_exists():
    """Ensure OI data exists for OI-based strategies"""
    cprint("[OI] Checking for Open Interest data...", "cyan")

    oi_dir = PROJECT_ROOT / "data" / "oi"
    oi_files = list(oi_dir.glob("*.parquet")) if oi_dir.exists() else []

    if oi_files:
        cprint(f"[SUCCESS] Found OI data files: {len(oi_files)} files", "green")
        for file in oi_files:
            cprint(f"  📄 {file.name}", "white")

            # Load and inspect OI data structure
            try:
                import pandas as pd
                oi_data = pd.read_parquet(file)
                cprint(f"[DEBUG] OI data shape: {oi_data.shape}", "white")
                cprint(f"[DEBUG] OI data columns: {list(oi_data.columns)}", "white")
                cprint(f"[DEBUG] OI data dtypes: {oi_data.dtypes.to_dict()}", "white")

                # Check for required columns
                required_cols = ['timestamp', 'symbol', 'open_interest']
                missing_cols = [col for col in required_cols if col not in oi_data.columns]
                if missing_cols:
                    cprint(f"[WARN] Missing expected columns: {missing_cols}", "yellow")
                else:
                    cprint("[SUCCESS] OI data has all expected columns", "green")

                    # Show sample data
                    cprint(f"[DEBUG] Sample OI data (first 3 rows):", "white")
                    cprint(str(oi_data.head(3)), "white")

            except ImportError:
                # Pandas not available in base environment - this is expected
                # The backtest will run in tflow environment where pandas is available
                cprint("[INFO] Pandas not available in base environment - skipping detailed inspection", "yellow")
                cprint("[INFO] OI data files exist and will be accessible in backtest environment", "cyan")
            except Exception as e:
                cprint(f"[ERROR] Failed to load OI data for inspection: {e}", "red")

        return True
    else:
        cprint("[WARN] No OI data files found", "yellow")
        cprint("[INFO] Run your OI agent to collect historical OI data first", "cyan")
        cprint("[HINT] Command: python src/agents/oi_agent.py", "white")
        return False


def ensure_funding_data_exists():
    """Ensure funding rate data exists for funding-based strategies"""
    cprint("[FUNDING] Checking for funding rate data...", "cyan")

    funding_dir = PROJECT_ROOT / "data" / "funding"
    funding_files = list(funding_dir.glob("*.parquet")) if funding_dir.exists() else []

    if funding_files:
        cprint(f"[SUCCESS] Found funding data files: {len(funding_files)} files", "green")
        for file in funding_files:
            cprint(f"  📄 {file.name}", "white")
        return True
    else:
        cprint("[WARN] No funding data files found", "yellow")
        cprint("[INFO] Run your funding agent to collect historical funding rate data first", "cyan")
        cprint("[HINT] Command: python src/agents/funding_agent.py", "white")
        return False


def ensure_liquidation_data_exists():
    """Ensure liquidation data exists for liquidation-based strategies"""
    cprint("[LIQUIDATION] Checking for liquidation data...", "cyan")

    liquidation_dir = PROJECT_ROOT / "src" / "data" / "liquidations"
    liquidation_files = list(liquidation_dir.glob("*.parquet")) if liquidation_dir.exists() else []

    if liquidation_files:
        cprint(f"[SUCCESS] Found liquidation data files: {len(liquidation_files)} files", "green")
        for file in liquidation_files:
            cprint(f"  📄 {file.name}", "white")
        return True
    else:
        cprint("[WARN] No liquidation data files found", "yellow")
        cprint("[INFO] Run your liquidation agent to collect historical liquidation data first", "cyan")
        cprint("[HINT] Command: python src/agents/liquidation_agent.py", "white")
        return False


def ensure_onchain_data_exists():
    """Ensure onchain data exists for onchain-based strategies"""
    cprint("[ONCHAIN] Checking for onchain data...", "cyan")

    onchain_files = [
        PROJECT_ROOT / "data" / "token_onchain_data.json",
        PROJECT_ROOT / "data" / "token_onchain_history.json"
    ]

    existing_files = [f for f in onchain_files if f.exists()]

    if existing_files:
        cprint(f"[SUCCESS] Found onchain data files: {len(existing_files)} files", "green")
        for file in existing_files:
            cprint(f"  📄 {file.name}", "white")
        return True
    else:
        cprint("[WARN] No onchain data files found", "yellow")
        cprint("[INFO] Run your onchain agent to collect blockchain data first", "cyan")
        return False


def load_data_for_strategy(strategy_idea, symbol='BTC'):
    """Load the appropriate data for the given strategy type"""
    data_type = determine_data_type_needed(strategy_idea)

    if data_type == "oi":
        return load_oi_data(symbol)
    elif data_type == "funding":
        return load_funding_data(symbol)
    elif data_type == "liquidation":
        return load_liquidation_data(symbol)
    elif data_type == "onchain":
        return load_onchain_data()
    else:  # indicator or default
        return load_ohlcv_data(symbol)


def load_ohlcv_data(symbol='BTC'):
    """Load OHLCV data from RBI folder"""
    try:
        import pandas as pd
        import os
        from pathlib import Path

        # Try multiple path resolution strategies
        possible_paths = [
            # Try relative to current script
            Path(__file__).parent.parent / "data" / "rbi" / f"{symbol}-USD-15m.csv",
            # Try absolute path
            Path("C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi") / f"{symbol}-USD-15m.csv",
            # Try relative to current working directory
            Path.cwd() / "src" / "data" / "rbi" / f"{symbol}-USD-15m.csv",
        ]

        for data_file in possible_paths:
            absolute_path = str(data_file.resolve())
            print(f"[DEBUG] Trying OHLCV data path: {absolute_path}")
            if data_file.exists():
                print(f"[SUCCESS] Found OHLCV data at: {absolute_path}")
                df = pd.read_csv(data_file)
                # Ensure datetime index
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                return df

        print(f"[ERROR] OHLCV data file not found for {symbol} in any expected location")
        print(f"[DEBUG] Searched paths: {[str(p) for p in possible_paths]}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load OHLCV data: {str(e)}")
        return None


def load_oi_data(symbol='BTC'):
    """Load OI data from parquet files"""
    try:
        import pandas as pd
        import os
        from pathlib import Path

        # Try multiple path resolution strategies
        possible_dirs = [
            # Try relative to current script
            Path(__file__).parent.parent / "data" / "oi",
            # Try absolute path
            Path("C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/oi"),
            # Try relative to current working directory
            Path.cwd() / "src" / "data" / "oi",
        ]

        for oi_dir in possible_dirs:
            absolute_path = str(oi_dir.resolve())
            print(f"[DEBUG] Looking for OI data in: {absolute_path}")
            if oi_dir.exists():
                # Look for OI files (may need to filter by symbol)
                parquet_files = list(oi_dir.glob("*.parquet"))
                if parquet_files:
                    # For now, load the first file (you may need more sophisticated filtering)
                    file_path = str(parquet_files[0].resolve())
                    print(f"[SUCCESS] Loading OI data from: {file_path}")
                    df = pd.read_parquet(parquet_files[0])
                    return df

        print(f"[ERROR] OI data files not found in any expected location")
        print(f"[DEBUG] Searched directories: {[str(p) for p in possible_dirs]}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load OI data: {str(e)}")
        return None


def load_funding_data(symbol='BTC'):
    """Load funding rate data from parquet files"""
    try:
        import pandas as pd
        import os
        from pathlib import Path

        # Try multiple path resolution strategies
        possible_dirs = [
            # Try relative to current script
            Path(__file__).parent.parent / "data" / "funding",
            # Try absolute path
            Path("C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/funding"),
            # Try relative to current working directory
            Path.cwd() / "src" / "data" / "funding",
        ]

        for funding_dir in possible_dirs:
            absolute_path = str(funding_dir.resolve())
            print(f"[DEBUG] Looking for funding data in: {absolute_path}")
            if funding_dir.exists():
                # Look for funding files (may need to filter by symbol)
                parquet_files = list(funding_dir.glob("*.parquet"))
                if parquet_files:
                    # For now, load the first file (you may need more sophisticated filtering)
                    file_path = str(parquet_files[0].resolve())
                    print(f"[SUCCESS] Loading funding data from: {file_path}")
                    df = pd.read_parquet(parquet_files[0])
                    return df

        print(f"[ERROR] Funding data files not found in any expected location")
        print(f"[DEBUG] Searched directories: {[str(p) for p in possible_dirs]}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load funding data: {str(e)}")
        return None


def load_liquidation_data(symbol='BTC'):
    """Load liquidation data from parquet files"""
    try:
        import pandas as pd
        import os
        from pathlib import Path

        # Try multiple path resolution strategies
        possible_dirs = [
            # Try using PROJECT_ROOT (most reliable)
            PROJECT_ROOT / "src" / "data" / "liquidations",
            # Try relative to current script
            Path(__file__).parent.parent / "data" / "liquidations",
            # Try absolute path
            Path("C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/liquidations"),
            # Try relative to current working directory
            Path.cwd() / "src" / "data" / "liquidations",
        ]

        for liquidation_dir in possible_dirs:
            absolute_path = str(liquidation_dir.resolve())
            print(f"[DEBUG] Looking for liquidation data in: {absolute_path}")
            if liquidation_dir.exists():
                # Look for liquidation files (may need to filter by symbol)
                parquet_files = list(liquidation_dir.glob("*.parquet"))
                if parquet_files:
                    # For now, load the first file (you may need more sophisticated filtering)
                    file_path = str(parquet_files[0].resolve())
                    print(f"[SUCCESS] Loading liquidation data from: {file_path}")
                    df = pd.read_parquet(parquet_files[0])
                    return df

        print(f"[ERROR] Liquidation data files not found in any expected location")
        print(f"[DEBUG] Searched directories: {[str(p) for p in possible_dirs]}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load liquidation data: {str(e)}")
        return None


def normalize_onchain_data(raw_data, ohlcv_data=None):
    """
    Normalize on-chain data structure to match strategy requirements.
    
    Converts nested JSON structure to flat DataFrame with required columns:
    - timestamp, symbol (or token_address), whale_concentration, market_cap
    - holder_count, transaction_volume, transaction_count, liquidity_usd
    
    Args:
        raw_data: Raw JSON data from token_onchain_data.json or token_onchain_history.json
        ohlcv_data: Optional OHLCV DataFrame for timestamp alignment
        
    Returns:
        Normalized DataFrame with required columns
    """
    try:
        import pandas as pd
        import numpy as np
        from datetime import datetime
        
        if raw_data is None:
            return None
        
        records = []
        
        # Handle different JSON structures
        if isinstance(raw_data, dict):
            # Structure 1: token_onchain_data.json - has 'timestamp' and 'tokens' keys
            if 'tokens' in raw_data:
                root_timestamp = pd.to_datetime(raw_data.get('timestamp', datetime.now()))
                tokens = raw_data['tokens']
                
                for token_address, token_data in tokens.items():
                    # Extract timestamp (use token-specific or root)
                    token_timestamp = pd.to_datetime(
                        token_data.get('timestamp', root_timestamp)
                    )
                    
                    # Extract whale concentration from holder_distribution
                    holder_dist = token_data.get('holder_distribution', {})
                    whale_pct = holder_dist.get('whale_pct', 0.0)
                    whale_concentration = float(whale_pct) if whale_pct is not None else 0.0
                    
                    # Calculate market cap estimate from liquidity (rough estimate: liquidity * multiplier)
                    # If we have price data, we could use price * supply, but for now use liquidity as proxy
                    liquidity_usd = float(token_data.get('liquidity_usd', 0.0) or 0.0)
                    # Estimate market cap as liquidity * 10 (rough multiplier for DeFi tokens)
                    # This is a placeholder - real market cap would need price and supply data
                    market_cap = liquidity_usd * 10 if liquidity_usd > 0 else 0.0
                    
                    record = {
                        'timestamp': token_timestamp,
                        'symbol': token_address[:8],  # Use first 8 chars of address as symbol
                        'token_address': token_address,
                        'whale_concentration': whale_concentration,
                        'market_cap': market_cap,
                        'holder_count': int(token_data.get('holder_count', 0) or 0),
                        'holder_change_pct': float(token_data.get('holder_change_pct', 0.0) or 0.0),
                        'transaction_volume': float(token_data.get('volume_24h', 0.0) or 0.0),
                        'transaction_count': int(token_data.get('tx_count_24h', 0) or 0),
                        'liquidity_usd': liquidity_usd,
                    }
                    records.append(record)
            
            # Structure 2: token_onchain_history.json - token addresses as keys, arrays as values
            else:
                for token_address, history_array in raw_data.items():
                    if isinstance(history_array, list):
                        for entry in history_array:
                            token_timestamp = pd.to_datetime(entry.get('timestamp', datetime.now()))
                            
                            # Extract whale concentration (may not be in history, use 0.0 as default)
                            whale_concentration = 0.0
                            
                            # Calculate market cap estimate
                            liquidity_usd = float(entry.get('liquidity_usd', 0.0) or 0.0)
                            market_cap = liquidity_usd * 10 if liquidity_usd > 0 else 0.0
                            
                            record = {
                                'timestamp': token_timestamp,
                                'symbol': token_address[:8],
                                'token_address': token_address,
                                'whale_concentration': whale_concentration,
                                'market_cap': market_cap,
                                'holder_count': int(entry.get('holder_count', 0) or 0),
                                'holder_change_pct': float(entry.get('holder_change_pct', 0.0) or 0.0),
                                'transaction_volume': float(entry.get('volume_24h', 0.0) or 0.0),
                                'transaction_count': int(entry.get('tx_count_24h', 0) or 0),
                                'liquidity_usd': liquidity_usd,
                            }
                            records.append(record)
        
        if not records:
            print("[WARN] No on-chain records extracted from data")
            return None
        
        # Create DataFrame
        df = pd.DataFrame(records)
        
        # Ensure timestamp is datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        # If OHLCV data provided, align timestamps
        if ohlcv_data is not None and not ohlcv_data.empty:
            # Get OHLCV timestamp range
            if 'timestamp' in ohlcv_data.columns:
                ohlcv_timestamps = pd.to_datetime(ohlcv_data['timestamp'])
            elif ohlcv_data.index.name == 'timestamp' or isinstance(ohlcv_data.index, pd.DatetimeIndex):
                ohlcv_timestamps = pd.to_datetime(ohlcv_data.index)
            else:
                ohlcv_timestamps = None
            
            if ohlcv_timestamps is not None:
                # Forward-fill on-chain data to match OHLCV timestamps
                # Create a merged DataFrame with OHLCV timestamps
                ohlcv_df = pd.DataFrame({'timestamp': ohlcv_timestamps})
                ohlcv_df = ohlcv_df.sort_values('timestamp')
                
                # Merge and forward-fill
                merged = ohlcv_df.merge(df, on='timestamp', how='left', sort=True)
                # Forward-fill missing values (using ffill() instead of deprecated fillna(method='ffill'))
                for col in ['whale_concentration', 'market_cap', 'holder_count', 
                           'transaction_volume', 'transaction_count', 'liquidity_usd']:
                    if col in merged.columns:
                        merged[col] = merged[col].ffill().fillna(0)
                
                # Fill symbol and token_address with last known value
                merged['symbol'] = merged['symbol'].ffill()
                merged['token_address'] = merged['token_address'].ffill()
                
                df = merged
        
        print(f"[INFO] Normalized {len(df)} on-chain records")
        print(f"[DEBUG] On-chain data columns: {list(df.columns)}")
        print(f"[DEBUG] On-chain data date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"[ERROR] Failed to normalize on-chain data: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def load_onchain_data():
    """Load onchain data from JSON files and normalize structure"""
    try:
        import json
        import pandas as pd
        import os
        from pathlib import Path

        # Try multiple path resolution strategies for both files
        possible_files = [
            # Try relative to current script
            (Path(__file__).parent.parent / "data" / "token_onchain_history.json",
             Path(__file__).parent.parent / "data" / "token_onchain_data.json"),
            # Try absolute path
            (Path("C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/token_onchain_history.json"),
             Path("C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/token_onchain_data.json")),
            # Try relative to current working directory
            (Path.cwd() / "src" / "data" / "token_onchain_history.json",
             Path.cwd() / "src" / "data" / "token_onchain_data.json"),
        ]

        raw_data = None
        for history_file, data_file in possible_files:
            # Try to load historical data first
            if history_file.exists():
                absolute_path = str(history_file.resolve())
                print(f"[SUCCESS] Loading onchain history data from: {absolute_path}")
                with open(history_file, 'r') as f:
                    raw_data = json.load(f)
                break

            # Fallback to current data
            if data_file.exists():
                absolute_path = str(data_file.resolve())
                print(f"[SUCCESS] Loading onchain data from: {absolute_path}")
                with open(data_file, 'r') as f:
                    raw_data = json.load(f)
                break

        if raw_data is None:
            print("[ERROR] Onchain data files not found in any expected location")
            print(f"[DEBUG] Searched file pairs: {[(str(h), str(d)) for h, d in possible_files]}")
            return None
        
        # Normalize the data structure
        normalized_df = normalize_onchain_data(raw_data)
        return normalized_df
        
    except Exception as e:
        print(f"[ERROR] Failed to load onchain data: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def customize_backtest_prompt_for_data_type(base_prompt, data_type):
    """Customize the backtest prompt based on data type needed"""

    if data_type == "oi":
        data_loading_instruction = """
        DATA LOADING FOR OI STRATEGY:
        Load OI data directly: oi_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/oi/oi_20251218.parquet')
        This script runs standalone and must load data directly.
        Expected columns: timestamp, symbol, open_interest, funding_rate, mark_price, volume_24h
        IMPORTANT: OI data contains multiple symbols. Filter for specific symbol (e.g., BTC):
        oi_data = oi_data[oi_data['symbol'] == 'BTC'].copy()
        Access OI values using: oi_data['open_interest'] (NOT 'OI' or 'oi_value')
        """
    elif data_type == "funding":
        data_loading_instruction = """
        DATA LOADING FOR FUNDING STRATEGY:
        Load funding data directly: funding_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/funding/funding_20251218.parquet')
        This script runs standalone and must load data directly.
        Expected columns: timestamp (or event_time), funding_rate, mark_price, index_price, symbol
        IMPORTANT: DO NOT filter for BTC only. Test all symbols in the funding data.
        The funding data contains multiple symbols (BTC, ETH, DOT, SUSHI, etc.) - iterate through all symbols
        or focus on symbols with extreme funding rates (below -0.05% or above +0.05%).
        Example multi-symbol approach:
        for symbol in funding_data['symbol'].unique():
            symbol_funding = funding_data[funding_data['symbol'] == symbol]
            # Process each symbol's funding data
        """
    elif data_type == "liquidation":
        data_loading_instruction = """
        DATA LOADING FOR LIQUIDATION STRATEGY:
        Try to load liquidation data directly: liquidation_data = pd.read_parquet('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/liquidations/liquidations_20251218.parquet')
        Handle case where file might not exist: if liquidation_data is None or file doesn't exist, create synthetic liquidation data for backtesting
        This script runs standalone and must load data directly.
        Expected columns: timestamp, price, quantity, side, usd_value, symbol
        """
    elif data_type == "onchain":
        data_loading_instruction = """
        DATA LOADING FOR ONCHAIN STRATEGY:
        Load onchain data directly: onchain_data = pd.read_json('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/token_onchain_data.json')
        This script runs standalone and must load data directly.
        
        IMPORTANT: The raw JSON has nested structure. You need to normalize it:
        1. Extract tokens from the 'tokens' key (if present)
        2. For each token, extract: timestamp, symbol (or token_address), whale_concentration, market_cap
        3. Also extract: holder_count, transaction_volume (volume_24h), transaction_count (tx_count_24h), liquidity_usd
        4. whale_concentration comes from holder_distribution.whale_pct (convert to decimal, e.g., 30.0% -> 30.0)
        5. market_cap can be estimated from liquidity_usd * 10 (or use actual if available)
        6. Create a DataFrame with columns: timestamp, symbol, whale_concentration, market_cap, holder_count, transaction_volume, transaction_count
        7. Align timestamps with OHLCV data using merge and forward-fill (ffill()) to match price data frequency
        8. Handle missing values: forward-fill numeric columns, fill remaining NaN with 0
        
        Expected normalized columns: timestamp, symbol, whale_concentration, market_cap, holder_count, transaction_volume, transaction_count, liquidity_usd
        """
    else:  # indicator/ohlcv
        data_loading_instruction = """
        DATA LOADING FOR INDICATOR STRATEGY:
        Load OHLCV data directly: price_data = pd.read_csv('C:/Users/Top Cash Pawn/ITORO/agent-systems/itoro/src/data/rbi/BTC-USD-15m.csv')
        This script runs standalone and must load data directly.
        Required columns: timestamp, open, high, low, close, volume, open_interest
        """

    # Insert the data loading instruction into the base prompt
    customized_prompt = base_prompt.replace(
        "IMPORTANT DATA HANDLING:",
        f"IMPORTANT DATA HANDLING:\n{data_loading_instruction}\n\nIMPORTANT DATA HANDLING:"
    )

    return customized_prompt

def main():
    """Main function - process ideas from file"""
    cprint(f"\n[STAR] Moon Dev's RBI AI v3.0 Starting Up!", "green")
    cprint(f"[DATE] Today's Date: {TODAY_DATE}", "magenta")
    cprint(f"[TARGET] OPTIMIZATION LOOP ENABLED!", "yellow")
    cprint(f"[TARGET] Target Return: {TARGET_RETURN}%", "green")
    cprint(f"[PYTHON] Using conda env: {CONDA_ENV}", "cyan")
    cprint(f"[SETTINGS] Max debug iterations: {MAX_DEBUG_ITERATIONS}", "cyan")
    cprint(f"[ROCKET] Max optimization iterations: {MAX_OPTIMIZATION_ITERATIONS}", "cyan")

    # Data checks will be performed per strategy in process_trading_idea_with_execution()

    cprint(f"\n[FOLDER] RBI v3.0 Data Directory: {DATA_DIR}", "magenta")
    cprint(f"[LIST] Reading ideas from: {IDEAS_FILE}", "magenta")
    
    # Use the ideas file from original RBI directory
    ideas_file = IDEAS_FILE
    
    if not ideas_file.exists():
        cprint("❌ ideas.txt not found! Creating template...", "red")
        ideas_file.parent.mkdir(parents=True, exist_ok=True)
        with open(ideas_file, 'w', encoding='utf-8') as f:
            f.write("# Add your trading ideas here (one per line)\n")
            f.write("# Can be YouTube URLs, PDF links, or text descriptions\n")
            f.write("# Lines starting with # are ignored\n\n")
            f.write("Create a simple RSI strategy that buys when RSI < 30 and sells when RSI > 70\n")
            f.write("Momentum strategy using 20/50 SMA crossover with volume confirmation\n")
        cprint(f"[LIST] Created template ideas.txt at: {ideas_file}", "yellow")
        cprint("[HINT] Add your trading ideas and run again!", "yellow")
        return
        
    with open(ideas_file, 'r', encoding='utf-8') as f:
        ideas = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
    total_ideas = len(ideas)
    cprint(f"\n[TARGET] Found {total_ideas} trading ideas to process", "cyan")
    
    # Write debug file
    try:
        main_debug_file = open(r"c:\Users\Top Cash Pawn\ITORO\.cursor\main_debug.txt", "w", encoding='utf-8')
        main_debug_file.write(f"Total ideas: {total_ideas}\n")
        main_debug_file.close()
    except Exception as e:
        print(f"[DEBUG] Main debug file write failed: {e}")
    
    # Count how many ideas have already been processed
    already_processed = sum(1 for idea in ideas if is_idea_processed(idea))
    new_ideas = total_ideas - already_processed
    
    cprint(f"[SEARCH] Status: {already_processed} already processed, {new_ideas} new ideas", "cyan")
    
    if new_ideas == 0:
        cprint("[WARN] All ideas have already been processed!", "yellow")
        try:
            main_debug_file = open(r"c:\Users\Top Cash Pawn\ITORO\.cursor\main_debug.txt", "a", encoding='utf-8')
            main_debug_file.write(f"All ideas already processed - exiting\n")
            main_debug_file.close()
        except:
            pass
    
    for i, idea in enumerate(ideas, 1):
        # Check if this idea has already been processed
        if is_idea_processed(idea):
            cprint(f"\n{'='*50}", "red")
            cprint(f"⏭️  SKIPPING idea {i}/{total_ideas} - ALREADY PROCESSED", "red", attrs=['reverse'])
            idea_snippet = idea[:100] + ('...' if len(idea) > 100 else '')
            cprint(f"[LIST] Idea: {idea_snippet}", "red")
            cprint(f"{'='*50}\n", "red")
            continue
        
        cprint(f"\n{'='*50}", "yellow")
        cprint(f"[MOON] Processing idea {i}/{total_ideas}", "cyan")
        cprint(f"[LIST] Idea: {idea[:100]}{'...' if len(idea) > 100 else ''}", "yellow")
        cprint(f"{'='*50}\n", "yellow")
        
        # Write debug file before processing
        try:
            idea_debug_file = open(r"c:\Users\Top Cash Pawn\ITORO\.cursor\idea_debug.txt", "w", encoding='utf-8')
            idea_debug_file.write(f"Processing idea {i}/{total_ideas}\nIdea: {idea[:200]}\n")
            idea_debug_file.close()
        except Exception as e:
            print(f"[DEBUG] Idea debug file write failed: {e}")
        
        try:
            process_trading_idea_with_execution(idea)
        except Exception as e:
            print(f"[DEBUG] Exception in process_trading_idea_with_execution: {e}")
            import traceback
            traceback.print_exc()
            try:
                error_file = open(r"c:\Users\Top Cash Pawn\ITORO\.cursor\error.txt", "w", encoding='utf-8')
                error_file.write(f"Exception: {e}\n{traceback.format_exc()}")
                error_file.close()
            except:
                pass
        
        cprint(f"\n{'='*50}", "green")
        cprint(f"✅ Completed idea {i}/{total_ideas}", "green")
        cprint(f"{'='*50}\n", "green")
        
        # Break between ideas
        if i < total_ideas:
            cprint("😴 Taking a break before next idea...", "yellow")
            time.sleep(5)

if __name__ == "__main__":
    main()
