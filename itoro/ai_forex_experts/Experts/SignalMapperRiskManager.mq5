#property strict
#property copyright ""
#property link      ""

#include <Trade/Trade.mqh>

// Input configuration for symbol mapping
enum SymbolMappingMode
{
	MAP_StrictExact = 0,      // Only exact symbol names
	MAP_FirstSixChars = 1,    // Match by first 6 chars (e.g., EURUSD* variants)
	MAP_MetalsAlias = 2,      // XAUUSD <-> GOLD, XAGUSD <-> SILVER
	MAP_ManualList = 3,       // Use ManualMappings list below
	MAP_AutoFallback = 4      // Try all strategies in a robust order
};

// Lot sizing configuration
enum LotSizingMode
{
	LOT_Fixed = 0,
	LOT_RiskPercent = 1,
	LOT_FromSignal = 2
};

// SL/TP calculation modes
enum LevelCalcMode
{
	LEVEL_FixedPips = 0,
	LEVEL_ATR = 1,
	LEVEL_PercentBalance = 2, // Uses lot size to convert money -> distance; avoid with LOT_RiskPercent for SL
	LEVEL_Money = 3,
	LEVEL_RMultiple = 4       // Only meaningful for TP (as multiple of SL distance)
};

input string              InpSignalFileName        = "signals.csv";  // CSV file in MQL5/Files
input int                 InpTimerSeconds          = 1;               // Poll interval seconds

input SymbolMappingMode   InpMappingMode           = MAP_AutoFallback;
input string              InpManualMappings        = "XAUUSD.SV=XAUUSD;GOLD=XAUUSD;SILVER=XAGUSD"; // semi-colon separated pairs A=B

input LotSizingMode       InpLotMode               = LOT_RiskPercent;
input double              InpFixedLot              = 0.10;            // Used if LOT_Fixed
input double              InpRiskPercent           = 1.0;             // % of equity risk per trade (if LOT_RiskPercent)

input bool                InpEnableSL              = true;            // If false, do not set SL
input bool                InpEnableTP              = true;            // If false, do not set TP

input LevelCalcMode       InpSLMode                = LEVEL_FixedPips;
input double              InpSL_Pips               = 300.0;           // Fixed SL pips or ATR multiplier/Percent/Money (see below)
input double              InpSL_ATRMult            = 2.0;             // SL ATR multiple (if LEVEL_ATR)
input int                 InpATR_Period            = 14;              // ATR period
input double              InpSL_BalancePercent     = 1.0;             // SL % of balance (if LEVEL_PercentBalance)
input double              InpSL_Money              = 100.0;           // SL money amount (if LEVEL_Money)

input LevelCalcMode       InpTPMode                = LEVEL_RMultiple;  // Default to RR target
input double              InpTP_Pips               = 600.0;           // Fixed TP pips or ATR multiplier/Percent/Money
input double              InpTP_ATRMult            = 4.0;             // TP ATR multiple (if LEVEL_ATR)
input double              InpTP_BalancePercent     = 2.0;             // TP % of balance (if LEVEL_PercentBalance)
input double              InpTP_Money              = 200.0;           // TP money amount (if LEVEL_Money)
input double              InpTP_RMultiple          = 2.0;             // TP = R multiple of SL distance (if LEVEL_RMultiple)

input bool                InpAutoPipDetection      = true;            // Auto compute pip size from digits
input double              InpPipPointsOverride     = 0.0;             // Override pip size in points (0=auto)
input bool                InpAllowHedgingOpen      = true;            // Allow opening opposite positions in hedging accounts
input bool                InpCloseOppositeNetting  = true;            // In netting, close opposite before open
input int                 InpStopBufferPoints      = 20;              // Extra points beyond StopsLevel
input double              InpMaxMarginUsePercent   = 95.0;            // Max % of free margin to use
input bool                InpRetryAdjustStops      = true;            // Retry once widening stops on invalid

// Trading
input int                 InpSlippagePoints        = 20;              // Max slippage in points
input ulong               InpMagic                 = 20250911;        // Magic number

// Internal runtime
CTrade g_trade;

// Track processed signal IDs in memory to avoid duplicates
string g_processed_ids[];

// Choose a supported filling mode for the symbol based on server mask
ENUM_ORDER_TYPE_FILLING ChooseFillingMode(const string symbol)
{
	long mask = 0;
	if(!SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE, mask))
		return ORDER_FILLING_FOK;
	if((mask & ORDER_FILLING_FOK) == ORDER_FILLING_FOK)
		return ORDER_FILLING_FOK;
	if((mask & ORDER_FILLING_IOC) == ORDER_FILLING_IOC)
		return ORDER_FILLING_IOC;
	if((mask & ORDER_FILLING_RETURN) == ORDER_FILLING_RETURN)
		return ORDER_FILLING_RETURN;
	return ORDER_FILLING_FOK;
}

bool SendOrderWithBestFilling(MqlTradeRequest &req, MqlTradeResult &res, const string symbol)
{
	long mask = 0;
	if(!SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE, mask))
		mask = ORDER_FILLING_FOK | ORDER_FILLING_IOC | ORDER_FILLING_RETURN;

	ENUM_ORDER_TYPE_FILLING candidates[3];
	int cnt = 0;
	// Prefer RETURN → IOC → FOK as many brokers require RETURN for market orders
	if((mask & ORDER_FILLING_RETURN) == ORDER_FILLING_RETURN) candidates[cnt++] = ORDER_FILLING_RETURN;
	if((mask & ORDER_FILLING_IOC) == ORDER_FILLING_IOC)   candidates[cnt++] = ORDER_FILLING_IOC;
	if((mask & ORDER_FILLING_FOK) == ORDER_FILLING_FOK)   candidates[cnt++] = ORDER_FILLING_FOK;
	if(cnt == 0) { candidates[cnt++] = ORDER_FILLING_FOK; }

	for(int i=0;i<cnt;i++)
	{
		req.type_filling = candidates[i];
		if(OrderSend(req, res))
		{
			if(res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_PLACED)
				return true;
		}
	}
	return false;
}

// Utility: trim
string Trim(const string text)
{
	int start = 0;
	int end = StringLen(text) - 1;
	while(start <= end && (StringGetCharacter(text, start) <= ' ')) start++;
	while(end >= start && (StringGetCharacter(text, end) <= ' ')) end--;
	if(start > end) return "";
	return StringSubstr(text, start, end - start + 1);
}

// Utility: uppercase
string Upper(const string s)
{
	string t = s;
	StringToUpper(t);
	return t;
}

// Parse manual mappings into pairs
int ParseManualMappings(string &fromSymbols[], string &toSymbols[])
{
	ArrayResize(fromSymbols, 0);
	ArrayResize(toSymbols, 0);
	string pairs[];
	int n = StringSplit(InpManualMappings, ';', pairs);
	for(int i=0;i<n;i++)
	{
		string kv = Trim(pairs[i]);
		if(kv == "") continue;
		int eq = StringFind(kv, "=");
		if(eq <= 0) continue;
		string from = Trim(StringSubstr(kv, 0, eq));
		string to   = Trim(StringSubstr(kv, eq+1));
		int sz = ArraySize(fromSymbols);
		ArrayResize(fromSymbols, sz+1);
		ArrayResize(toSymbols, sz+1);
		fromSymbols[sz] = Upper(from);
		toSymbols[sz]   = to;
	}
	return ArraySize(fromSymbols);
}

// Normalize a symbol string by removing separators and making uppercase
string NormalizeBase(const string sym)
{
	string u = Upper(Trim(sym));
	string out = "";
	for(int i=0;i<(int)StringLen(u);i++)
	{
		ushort ch = StringGetCharacter(u, i);
		if((ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9'))
			out += CharToString((uchar)ch);
	}
	return out;
}

bool IsTradeAllowedSymbol(const string symbol)
{
	if(symbol == "") return false;
	if(!SymbolSelect(symbol, true)) return false;
	long trade_mode = 0;
	if(!SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE, trade_mode)) return false;
	if(trade_mode == SYMBOL_TRADE_MODE_DISABLED) return false;
	return true;
}

bool IsMetalsAlias(const string a, const string b)
{
	string na = NormalizeBase(a);
	string nb = NormalizeBase(b);
	bool gold = (na == "XAUUSD" && nb == "GOLD") || (na == "GOLD" && nb == "XAUUSD");
	bool silver = (na == "XAGUSD" && nb == "SILVER") || (na == "SILVER" && nb == "XAGUSD");
	return gold || silver;
}

// Try to resolve a provider symbol to a broker tradable symbol
string ResolveBrokerSymbol(const string provider_symbol)
{
	string p = Trim(provider_symbol);
	if(p == "") return "";
	string p_upper = Upper(p);

	// 1) Strict exact
	if(InpMappingMode == MAP_StrictExact || InpMappingMode == MAP_AutoFallback)
	{
		if(IsTradeAllowedSymbol(p_upper))
			return p_upper;
	}

	// 2) Manual list
	if(InpMappingMode == MAP_ManualList || InpMappingMode == MAP_AutoFallback)
	{
		string froms[]; string tos[];
		ParseManualMappings(froms, tos);
		for(int i=0;i<ArraySize(froms);i++)
		{
			if(Upper(p_upper) == froms[i])
			{
				string target = tos[i];
				if(IsTradeAllowedSymbol(target)) return target;
			}
		}
	}

	// 3) Metals alias
	if(InpMappingMode == MAP_MetalsAlias || InpMappingMode == MAP_AutoFallback)
	{
		int total = (int)SymbolsTotal(true);
		for(int i=0;i<total;i++)
		{
			string sym = SymbolName(i, true);
			if(IsMetalsAlias(p_upper, sym) && IsTradeAllowedSymbol(sym))
				return sym;
		}
	}

	// 4) First six chars match
	if(InpMappingMode == MAP_FirstSixChars || InpMappingMode == MAP_AutoFallback)
	{
		string base_p = NormalizeBase(p_upper);
		string p6 = (StringLen(base_p) >= 6 ? StringSubstr(base_p, 0, 6) : base_p);
		int total = (int)SymbolsTotal(true);
		for(int i=0;i<total;i++)
		{
			string sym = SymbolName(i, true);
			string base_s = NormalizeBase(sym);
			string s6 = (StringLen(base_s) >= 6 ? StringSubstr(base_s, 0, 6) : base_s);
			if(p6 == s6 && IsTradeAllowedSymbol(sym))
				return sym;
		}
	}

	// 5) Fallback: try stripping suffix after a dot or underscore
	if(InpMappingMode == MAP_AutoFallback)
	{
		int dot = StringFind(p_upper, ".");
		int us  = StringFind(p_upper, "_");
		int cut = -1;
		if(dot > 0) cut = dot; else if(us > 0) cut = us;
		if(cut > 0)
		{
			string base = StringSubstr(p_upper, 0, cut);
			if(IsTradeAllowedSymbol(base)) return base;
		}
	}

	return ""; // not found
}

// Compute pip size in POINTS units (not price). For 5/3 digits, 1 pip = 10 points; for 4/2 digits, 1 pip = 1 point.
double PipPointsInPoints(const string symbol)
{
	int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
	if(digits == 5 || digits == 3) return 10.0;
	if(digits == 4 || digits == 2) return 1.0;
	return 10.0;
}

// ATR calculation
double CalcATR(const string symbol, ENUM_TIMEFRAMES tf, int period)
{
	int handle = iATR(symbol, tf, period);
	if(handle == INVALID_HANDLE) return 0.0;
	double buf[];
	int copied = CopyBuffer(handle, 0, 0, 1, buf);
	IndicatorRelease(handle);
	if(copied <= 0) return 0.0;
	return buf[0];
}

// Monetary value per point per 1 lot
double MoneyPerPointPerLot(const string symbol)
{
	double tick_value = 0.0; double tick_size = 0.0;
	if(!SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE, tick_value)) return 0.0;
	if(!SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE, tick_size)) return 0.0;
	double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
	if(point <= 0.0 || tick_size <= 0.0) return 0.0;
	// Convert monetary per point using linear proportion
	return tick_value * (point / tick_size);
}

// Cap lot by available margin to avoid TRADE_RETCODE_NO_MONEY
double CapLotByMargin(const string symbol, const ENUM_ORDER_TYPE ord_type, const double entry_price, double lot)
{
	double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
	double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
	double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
	if(min_lot <= 0.0) min_lot = 0.01;
	if(max_lot <= 0.0) max_lot = 100.0;
	if(lot_step <= 0.0) lot_step = 0.01;

	lot = MathMax(min_lot, MathMin(max_lot, lot));
	double margin_per1 = 0.0;
	if(!OrderCalcMargin((ord_type == ORDER_TYPE_SELL || ord_type == ORDER_TYPE_SELL_LIMIT || ord_type == ORDER_TYPE_SELL_STOP) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY,
						symbol, 1.0, entry_price, margin_per1))
	{
		return lot; // fallback if API fails
	}
	if(margin_per1 <= 0.0) return lot;
	double free_margin = AccountInfoDouble(ACCOUNT_FREEMARGIN);
	double cap_money = free_margin * (InpMaxMarginUsePercent/100.0);
	double max_lot_by_margin = cap_money / margin_per1;
	double lot_capped = MathMin(lot, max_lot_by_margin);
	// Quantize
	lot_capped = MathFloor(lot_capped / lot_step) * lot_step;
	if(lot_capped < min_lot) return 0.0; // not enough margin even for min lot
	return lot_capped;
}

// Enforce minimal stop distance (StopsLevel + buffer)
void EnforceStopsMinDistance(const string symbol, const ENUM_ORDER_TYPE ord_type, const double entry_price, const double point, double &sl_price, double &tp_price)
{
	long stops_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
	if(stops_level <= 0 && InpStopBufferPoints <= 0) return;
	double min_dist = ((double)stops_level + (double)InpStopBufferPoints) * point;
	bool is_buy = (ord_type == ORDER_TYPE_BUY || ord_type == ORDER_TYPE_BUY_LIMIT || ord_type == ORDER_TYPE_BUY_STOP);
	if(is_buy)
	{
		if(sl_price > 0.0 && (entry_price - sl_price) < min_dist)
			sl_price = NormalizePrice(symbol, entry_price - min_dist);
		if(tp_price > 0.0 && (tp_price - entry_price) < min_dist)
			tp_price = NormalizePrice(symbol, entry_price + min_dist);
	}
	else
	{
		if(sl_price > 0.0 && (sl_price - entry_price) < min_dist)
			sl_price = NormalizePrice(symbol, entry_price + min_dist);
		if(tp_price > 0.0 && (entry_price - tp_price) < min_dist)
			tp_price = NormalizePrice(symbol, entry_price - min_dist);
	}
}

// Determine SL/TP distances (in points). Some modes depend on lot size (PercentBalance/Money)
bool ComputeSLTPDistancesPoints(
	const string symbol,
	const ENUM_ORDER_TYPE order_type,
	const double entry_price,
	const double lot_size,
	/*out*/ double &sl_points,
	/*out*/ double &tp_points,
	/*out*/ double &sl_to_tp_ratio
)
{
	sl_points = 0.0; tp_points = 0.0; sl_to_tp_ratio = 0.0;
	double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
	if(point <= 0.0) return false;
	double pip_points = PipPointsInPoints(symbol); // pip in POINTS units
	double mpppl = MoneyPerPointPerLot(symbol); // money per point per 1 lot
	if(mpppl <= 0.0) mpppl = 0.0; // allow zero -> avoid division by zero

	// SL distance
	if(InpSLMode == LEVEL_FixedPips)
	{
		sl_points = MathMax(0.0, InpSL_Pips) * pip_points; // result in POINTS
	}
	else if(InpSLMode == LEVEL_ATR)
	{
		double atr = CalcATR(symbol, PERIOD_CURRENT, InpATR_Period);
		if(atr <= 0.0) return false;
		sl_points = (atr * InpSL_ATRMult) / point; // convert ATR price to points
	}
	else if(InpSLMode == LEVEL_PercentBalance || InpSLMode == LEVEL_Money)
	{
		if(lot_size <= 0.0 || mpppl <= 0.0)
			return false; // cannot compute money->distance without lot and mpppl
		double equity = AccountInfoDouble(ACCOUNT_EQUITY);
		double money = (InpSLMode == LEVEL_PercentBalance) ? (equity * (InpSL_BalancePercent/100.0)) : InpSL_Money;
		if(money <= 0.0) return false;
		double points_needed = money / (mpppl * lot_size);
		sl_points = points_needed;
	}
	else if(InpSLMode == LEVEL_RMultiple)
	{
		// Not meaningful for SL; fall back to fixed pips
		sl_points = MathMax(0.0, InpSL_Pips) * pip_points;
	}

	// TP distance
	if(InpTPMode == LEVEL_FixedPips)
	{
		tp_points = MathMax(0.0, InpTP_Pips) * pip_points; // in POINTS
	}
	else if(InpTPMode == LEVEL_ATR)
	{
		double atr2 = CalcATR(symbol, PERIOD_CURRENT, InpATR_Period);
		if(atr2 <= 0.0) return false;
		tp_points = (atr2 * InpTP_ATRMult) / point;
	}
	else if(InpTPMode == LEVEL_PercentBalance || InpTPMode == LEVEL_Money)
	{
		if(lot_size <= 0.0 || mpppl <= 0.0)
			return false;
		double equity = AccountInfoDouble(ACCOUNT_EQUITY);
		double money = (InpTPMode == LEVEL_PercentBalance) ? (equity * (InpTP_BalancePercent/100.0)) : InpTP_Money;
		if(money <= 0.0) return false;
		double points_needed = money / (mpppl * lot_size);
		tp_points = points_needed;
	}
	else if(InpTPMode == LEVEL_RMultiple)
	{
		if(sl_points <= 0.0) return false;
		tp_points = sl_points * MathMax(0.0, InpTP_RMultiple);
	}

	if(sl_points <= 0.0) return false;
	if(tp_points < 0.0) tp_points = 0.0; // allow TP optional
	if(sl_points > 0.0)
		sl_to_tp_ratio = (tp_points > 0.0 ? tp_points / sl_points : 0.0);
	return true;
}

// Compute lot size respecting volume limits; if LOT_RiskPercent, use SL points
double ComputeLotSize(const string symbol, const double sl_points)
{
	double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
	double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
	double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
	if(min_lot <= 0.0) min_lot = 0.01;
	if(max_lot <= 0.0) max_lot = 100.0;
	if(lot_step <= 0.0) lot_step = 0.01;

	if(InpLotMode == LOT_Fixed)
	{
		double lot = InpFixedLot;
		lot = MathMax(min_lot, MathMin(max_lot, lot));
		lot = MathFloor(lot / lot_step) * lot_step;
		if(lot < min_lot) lot = min_lot;
		return lot;
	}

	// Risk percent mode
	if(sl_points <= 0.0) return min_lot; // safe fallback
	double equity = AccountInfoDouble(ACCOUNT_EQUITY);
	double risk_money = equity * (InpRiskPercent/100.0);
	double mpppl = MoneyPerPointPerLot(symbol);
	if(mpppl <= 0.0) return min_lot;
	double lot = risk_money / (mpppl * sl_points);
	lot = MathMax(min_lot, MathMin(max_lot, lot));
	lot = MathFloor(lot / lot_step) * lot_step;
	if(lot < min_lot) lot = min_lot;
	return lot;
}

bool IsAlreadyProcessed(const string id)
{
	for(int i=0;i<ArraySize(g_processed_ids);i++)
		if(g_processed_ids[i] == id) return true;
	return false;
}

void MarkProcessed(const string id)
{
	int sz = ArraySize(g_processed_ids);
	ArrayResize(g_processed_ids, sz+1);
	g_processed_ids[sz] = id;
}

// Signal structure from CSV
struct SignalRow
{
	string id;
	string symbol;
	string side;    // BUY/SELL
	string type;    // MARKET/LIMIT/STOP
	double price;    // for pending orders; 0 for market
	double sl;       // optional; 0=not provided
	double tp;       // optional; 0=not provided
	string comment;
};

// Basic CSV splitter for simple comma-separated lines
int SplitCSV(const string line, string &outFields[])
{
	string temp[];
	int n = StringSplit(line, ',', temp);
	ArrayResize(outFields, n);
	for(int i=0;i<n;i++)
	{
		string f = Trim(temp[i]);
		int len = (int)StringLen(f);
		if(len >= 2 && StringGetCharacter(f, 0) == '"' && StringGetCharacter(f, len-1) == '"')
			f = StringSubstr(f, 1, len-2);
		outFields[i] = f;
	}
	return n;
}

bool ParseHeaderLine(const string headerLine, int &idx_id, int &idx_symbol, int &idx_side, int &idx_type, int &idx_price, int &idx_sl, int &idx_tp, int &idx_comment)
{
	string header[];
	int cols = SplitCSV(headerLine, header);
	if(cols <= 0) return false;
	idx_id = idx_symbol = idx_side = idx_type = idx_price = idx_sl = idx_tp = idx_comment = -1;
	int idx_volume = -1;
	for(int i=0;i<cols;i++)
	{
		string h = Upper(Trim(header[i]));
		if(h == "ID") idx_id = i;
		else if(h == "SYMBOL") idx_symbol = i;
		else if(h == "SIDE") idx_side = i;
		else if(h == "TYPE") idx_type = i;
		else if(h == "PRICE") idx_price = i;
		else if(h == "SL") idx_sl = i;
		else if(h == "TP") idx_tp = i;
		else if(h == "COMMENT") idx_comment = i;
		else if(h == "VOLUME") idx_volume = i;
	}
	// store volume index in a static for later read
	GlobalVariableSet("__sigmap_vol_idx", (double)idx_volume);
	return idx_id >= 0 && idx_symbol >= 0 && idx_side >= 0 && idx_type >= 0;
}

bool ParseSignalLine(const string line, const int idx_id, const int idx_symbol, const int idx_side, const int idx_type, const int idx_price, const int idx_sl, const int idx_tp, const int idx_comment, /*out*/ SignalRow &row)
{
	string fields[];
	int n = SplitCSV(line, fields);
	if(n <= 0) return false;
	row.id = (idx_id >= 0 && idx_id < n ? Trim(fields[idx_id]) : "");
	row.symbol = (idx_symbol >= 0 && idx_symbol < n ? Trim(fields[idx_symbol]) : "");
	row.side = Upper((idx_side >= 0 && idx_side < n ? Trim(fields[idx_side]) : ""));
	row.type = Upper((idx_type >= 0 && idx_type < n ? Trim(fields[idx_type]) : ""));
	row.price = (idx_price >= 0 && idx_price < n ? StringToDouble(fields[idx_price]) : 0.0);
	row.sl = (idx_sl >= 0 && idx_sl < n ? StringToDouble(fields[idx_sl]) : 0.0);
	row.tp = (idx_tp >= 0 && idx_tp < n ? StringToDouble(fields[idx_tp]) : 0.0);
	row.comment = (idx_comment >= 0 && idx_comment < n ? Trim(fields[idx_comment]) : "");
	// Optional volume
	int vindex = (int)GlobalVariableGet("__sigmap_vol_idx");
	if(vindex >= 0 && vindex < n)
	{
		double vol = StringToDouble(fields[vindex]);
		GlobalVariableSet("__sigmap_vol_val", vol);
	}
	else
	{
		GlobalVariableDel("__sigmap_vol_val");
	}
	return true;
}

ENUM_ORDER_TYPE MapOrderType(const string typ, const string side)
{
	bool is_buy = (side == "BUY");
	if(typ == "MARKET") return (is_buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
	if(typ == "LIMIT") return (is_buy ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT);
	if(typ == "STOP") return (is_buy ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP);
	return (is_buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
}

double NormalizePrice(const string symbol, const double price)
{
	double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
	if(tick_size <= 0.0) return price;
	return MathRound(price / tick_size) * tick_size;
}

bool EnsureTradable(const string symbol)
{
	if(!IsTradeAllowedSymbol(symbol))
		return false;
	return true;
}

bool ExecuteSignal(const SignalRow &sig)
{
	string broker_symbol = ResolveBrokerSymbol(sig.symbol);
	if(broker_symbol == "")
	{
		PrintFormat("[Signal %s] Mapping failed for provider symbol '%s'", sig.id, sig.symbol);
		return false;
	}
	if(Upper(sig.symbol) != Upper(broker_symbol))
		PrintFormat("[Signal %s] Mapped '%s' -> '%s'", sig.id, sig.symbol, broker_symbol);
	if(!EnsureTradable(broker_symbol))
	{
		PrintFormat("[Signal %s] Symbol '%s' not tradable", sig.id, broker_symbol);
		return false;
	}

	ENUM_ORDER_TYPE ord_type = MapOrderType(sig.type, sig.side);
	bool is_buy = (sig.side == "BUY");

	// Entry price
	double entry_price = 0.0;
	if(ord_type == ORDER_TYPE_BUY || ord_type == ORDER_TYPE_SELL)
	{
		double price = (is_buy ? SymbolInfoDouble(broker_symbol, SYMBOL_ASK) : SymbolInfoDouble(broker_symbol, SYMBOL_BID));
		if(price <= 0.0) return false;
		entry_price = price;
	}
	else
	{
		if(sig.price <= 0.0)
		{
			PrintFormat("[Signal %s] Pending order requires a price", sig.id);
			return false;
		}
		entry_price = NormalizePrice(broker_symbol, sig.price);
	}

	// SL/TP prices
	double sl_price = 0.0; double tp_price = 0.0;
	// First determine SL distance for lot sizing
	double temp_lot_for_money_modes = (InpLotMode == LOT_Fixed ? InpFixedLot : 0.0);
	double sl_points0 = 0.0; double tp_points0 = 0.0; double rr = 0.0;
	if(!ComputeSLTPDistancesPoints(broker_symbol, ord_type, entry_price, temp_lot_for_money_modes, sl_points0, tp_points0, rr))
	{
		PrintFormat("[Signal %s] Failed to compute SL/TP distances (pre-lot)", sig.id);
		return false;
	}

	// Final lot based on SL distance
	double lot = 0.0;
	if(InpLotMode == LOT_FromSignal)
	{
		double vol = 0.0;
		if(GlobalVariableCheck("__sigmap_vol_val")) vol = GlobalVariableGet("__sigmap_vol_val");
		double min_lot = SymbolInfoDouble(broker_symbol, SYMBOL_VOLUME_MIN);
		double step = SymbolInfoDouble(broker_symbol, SYMBOL_VOLUME_STEP);
		if(step <= 0.0) step = 0.01;
		if(vol <= 0.0) vol = min_lot;
		// quantize
		lot = MathMax(min_lot, MathFloor(vol / step) * step);
	}
	else if(sig.sl > 0.0 && sig.tp >= 0.0)
	{
		// If provider gave SL, use it to compute lot if RiskPercent
		double point = SymbolInfoDouble(broker_symbol, SYMBOL_POINT);
		double sl_points_provider = MathAbs((sig.sl - entry_price) / point);
		lot = (InpLotMode == LOT_RiskPercent ? ComputeLotSize(broker_symbol, sl_points_provider) : ComputeLotSize(broker_symbol, sl_points0));
	}
	else
	{
		// If SL is disabled and LotMode is RiskPercent, fallback to fixed lot (or min)
		if(InpLotMode == LOT_RiskPercent && !InpEnableSL)
		{
			double min_lot = SymbolInfoDouble(broker_symbol, SYMBOL_VOLUME_MIN);
			double step = SymbolInfoDouble(broker_symbol, SYMBOL_VOLUME_STEP);
			if(step <= 0.0) step = 0.01;
			double lot_fixed = (InpFixedLot > 0.0 ? InpFixedLot : min_lot);
			lot = MathMax(min_lot, MathFloor(lot_fixed / step) * step);
		}
		else
		{
			lot = ComputeLotSize(broker_symbol, sl_points0);
		}
	}
	if(lot <= 0.0)
	{
		PrintFormat("[Signal %s] Computed lot is invalid", sig.id);
		return false;
	}

	// Recompute distances for money/percent modes now that lot is known
	if(!ComputeSLTPDistancesPoints(broker_symbol, ord_type, entry_price, lot, sl_points0, tp_points0, rr))
	{
		PrintFormat("[Signal %s] Failed to compute SL/TP distances (final)", sig.id);
		return false;
	}

	double point = SymbolInfoDouble(broker_symbol, SYMBOL_POINT);
	if(InpEnableSL)
	{
		if(sig.sl > 0.0)
		{
			sl_price = sig.sl;
		}
		else
		{
			double d = sl_points0 * point;
			sl_price = NormalizePrice(broker_symbol, is_buy ? (entry_price - d) : (entry_price + d));
		}
	}
	else
	{
		sl_price = 0.0;
	}
	if(InpEnableTP)
	{
		if(sig.tp > 0.0)
		{
			tp_price = sig.tp;
		}
		else if(tp_points0 > 0.0)
		{
			double d2 = tp_points0 * point;
			tp_price = NormalizePrice(broker_symbol, is_buy ? (entry_price + d2) : (entry_price - d2));
		}
	}
	else
	{
		tp_price = 0.0;
	}

	// Enforce minimal stop distance (StopsLevel + buffer)
	long stops_level = SymbolInfoInteger(broker_symbol, SYMBOL_TRADE_STOPS_LEVEL);
	EnforceStopsMinDistance(broker_symbol, ord_type, entry_price, point, sl_price, tp_price);

	// Enforce pending entry distance relative to current prices
	if(stops_level > 0 && (ord_type == ORDER_TYPE_BUY_LIMIT || ord_type == ORDER_TYPE_SELL_LIMIT || ord_type == ORDER_TYPE_BUY_STOP || ord_type == ORDER_TYPE_SELL_STOP))
	{
		double min_dist = (double)stops_level * point;
		double bid = SymbolInfoDouble(broker_symbol, SYMBOL_BID);
		double ask = SymbolInfoDouble(broker_symbol, SYMBOL_ASK);
		if(ord_type == ORDER_TYPE_BUY_LIMIT)
		{
			if(entry_price > bid - min_dist)
				entry_price = NormalizePrice(broker_symbol, bid - min_dist);
		}
		else if(ord_type == ORDER_TYPE_SELL_LIMIT)
		{
			if(entry_price < ask + min_dist)
				entry_price = NormalizePrice(broker_symbol, ask + min_dist);
		}
		else if(ord_type == ORDER_TYPE_BUY_STOP)
		{
			if(entry_price < ask + min_dist)
				entry_price = NormalizePrice(broker_symbol, ask + min_dist);
		}
		else if(ord_type == ORDER_TYPE_SELL_STOP)
		{
			if(entry_price > bid - min_dist)
				entry_price = NormalizePrice(broker_symbol, bid - min_dist);
		}
	}

	// If netting and configured, close opposite position first
	long margin_mode = AccountInfoInteger(ACCOUNT_MARGIN_MODE);
	bool hedging = (margin_mode == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
	if(!hedging && InpCloseOppositeNetting)
	{
		if(PositionSelect(broker_symbol))
		{
			long ptype = PositionGetInteger(POSITION_TYPE);
			bool opposite = (is_buy && ptype == POSITION_TYPE_SELL) || (!is_buy && ptype == POSITION_TYPE_BUY);
			if(opposite)
			{
				g_trade.PositionClose(broker_symbol, InpSlippagePoints);
			}
		}
	}
	// In hedging, optionally block opening opposite positions
	if(hedging && !InpAllowHedgingOpen)
	{
		if(PositionSelect(broker_symbol))
		{
			long ptype = PositionGetInteger(POSITION_TYPE);
			bool opposite = (is_buy && ptype == POSITION_TYPE_SELL) || (!is_buy && ptype == POSITION_TYPE_BUY);
			if(opposite)
			{
				PrintFormat("[Signal %s] Opposite position exists on hedging account and InpAllowHedgingOpen=false. Skipping.", sig.id);
				return false;
			}
		}
	}

	// Place order
	g_trade.SetExpertMagicNumber(InpMagic);
	g_trade.SetDeviationInPoints(InpSlippagePoints);

	bool ok = false;
	MqlTradeRequest req;
	MqlTradeResult  res;
	ZeroMemory(req);
	ZeroMemory(res);

	// Cap by margin before sending
	lot = CapLotByMargin(broker_symbol, ord_type, entry_price, lot);
	if(lot <= 0.0)
	{
		PrintFormat("[Signal %s] Not enough margin for min lot", sig.id);
		return false;
	}

	req.action   = TRADE_ACTION_DEAL;
	req.symbol   = broker_symbol;
	req.magic    = InpMagic;
	req.volume   = lot;
	req.type     = ord_type;
	req.price    = entry_price;
	req.sl       = sl_price;
	req.tp       = (tp_price > 0.0 ? tp_price : 0.0);
	req.deviation= InpSlippagePoints;
	req.comment  = sig.comment;
	req.type_time= ORDER_TIME_GTC;

	// Set default filling policy where applicable (ignored for pending)
	req.type_filling = ChooseFillingMode(broker_symbol);

	if(ord_type == ORDER_TYPE_BUY_LIMIT || ord_type == ORDER_TYPE_SELL_LIMIT || ord_type == ORDER_TYPE_BUY_STOP || ord_type == ORDER_TYPE_SELL_STOP)
	{
		req.action = TRADE_ACTION_PENDING;
		req.price  = entry_price;
		// Some servers ignore filling mode for pending; set to RETURN to be safe
		req.type_filling = ORDER_FILLING_RETURN;
	}

	bool sent = SendOrderWithBestFilling(req, res, broker_symbol);
	if(!sent && InpRetryAdjustStops)
	{
		// Retry once widening stops by buffer
		double extra = (double)(MathMax(1, InpStopBufferPoints)) * point;
		if(is_buy)
		{
			sl_price = NormalizePrice(broker_symbol, sl_price - extra);
			if(tp_price > 0.0) tp_price = NormalizePrice(broker_symbol, tp_price + extra);
		}
		else
		{
			sl_price = NormalizePrice(broker_symbol, sl_price + extra);
			if(tp_price > 0.0) tp_price = NormalizePrice(broker_symbol, tp_price - extra);
		}
		req.sl = sl_price; req.tp = (tp_price>0.0?tp_price:0.0);
		sent = SendOrderWithBestFilling(req, res, broker_symbol);
	}
	// For market orders, as a last resort, send without SL/TP and modify after
	if(!sent && (ord_type == ORDER_TYPE_BUY || ord_type == ORDER_TYPE_SELL))
	{
		double sl_saved = sl_price, tp_saved = tp_price;
		req.sl = 0.0; req.tp = 0.0;
		sent = SendOrderWithBestFilling(req, res, broker_symbol);
		if(sent && (sl_saved > 0.0 || tp_saved > 0.0))
		{
			// Give server-friendly modify
			g_trade.PositionModify(broker_symbol, sl_saved, (tp_saved>0.0?tp_saved:0.0));
		}
	}
	if(!sent)
	{
		PrintFormat("[Signal %s] OrderSend failed: %d - %s", sig.id, GetLastError(), res.comment);
		return false;
	}

	PrintFormat("[Signal %s] Placed %s %s lot=%.2f entry=%.5f SL=%.5f TP=%.5f", sig.id, sig.side, broker_symbol, lot, entry_price, sl_price, (tp_price>0.0?tp_price:0.0));
	return true;
}

int OnInit()
{
	EventSetTimer(MathMax(1, InpTimerSeconds));
	ArrayResize(g_processed_ids, 0);
	return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
	EventKillTimer();
}

void OnTimer()
{
	int fh = FileOpen(InpSignalFileName, FILE_READ|FILE_SHARE_READ|FILE_TXT|FILE_ANSI);
	if(fh == INVALID_HANDLE)
		return;
	// Read header line
	string headerLine = FileReadString(fh);
	headerLine = Trim(headerLine);
	int idx_id, idx_symbol, idx_side, idx_type, idx_price, idx_sl, idx_tp, idx_comment;
	if(!ParseHeaderLine(headerLine, idx_id, idx_symbol, idx_side, idx_type, idx_price, idx_sl, idx_tp, idx_comment))
	{
		FileClose(fh);
		return;
	}

	while(!FileIsEnding(fh))
	{
		string line = FileReadString(fh);
		line = Trim(line);
		if(line == "") continue;
		SignalRow row;
		if(!ParseSignalLine(line, idx_id, idx_symbol, idx_side, idx_type, idx_price, idx_sl, idx_tp, idx_comment, row))
			continue;
		if(row.id == "") continue;
		if(IsAlreadyProcessed(row.id)) continue;

		bool ok = ExecuteSignal(row);
		MarkProcessed(row.id);
	}
	FileClose(fh);
}

void OnTick()
{
	// No work; we process via OnTimer
}


