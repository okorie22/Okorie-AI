//+------------------------------------------------------------------+
//|                                                  EmergencyStop.mqh|
//| Cross-version (MT4/MT5) emergency stop module for Telegram EAs   |
//| Monitors daily/overall drawdown, halts Telegram sends, sends SMS |
//+------------------------------------------------------------------+
#property strict

#ifndef __EMERGENCY_STOP_MQH__
#define __EMERGENCY_STOP_MQH__

// Version compatibility is detected via __MQL5__ macro

// Accessors for account info (MT4/MT5)
double ES_AccountEquity()
{
#ifdef __MQL5__
  return AccountInfoDouble(ACCOUNT_EQUITY);
#else
  return AccountEquity();
#endif
}

double ES_AccountBalance()
{
#ifdef __MQL5__
  return AccountInfoDouble(ACCOUNT_BALANCE);
#else
  return AccountBalance();
#endif
}

long ES_AccountLogin()
{
#ifdef __MQL5__
  return (long)AccountInfoInteger(ACCOUNT_LOGIN);
#else
  return (long)AccountNumber();
#endif
}

// Day-of-year helper compatible with MT4/MT5
int ES_DayOfYear(const datetime t)
{
  MqlDateTime dt; TimeToStruct(t, dt);
  bool isLeap = ((dt.year % 4 == 0) && ((dt.year % 100 != 0) || (dt.year % 400 == 0)));
  int mdays[12];
  mdays[0]=31; mdays[1]=28; mdays[2]=31; mdays[3]=30; mdays[4]=31; mdays[5]=30; mdays[6]=31; mdays[7]=31; mdays[8]=30; mdays[9]=31; mdays[10]=30; mdays[11]=31;
  if(isLeap) mdays[1]=29;
  int sum=0;
  int monIndex = (dt.mon>0 ? dt.mon-1 : 0);
  for(int i=0;i<monIndex;i++) sum += mdays[i];
  sum += dt.day;
  return sum;
}

// URL encoding helper
string ES_UrlEncode(const string s)
{
  string out="";
  int n = StringLen(s);
  for(int i=0;i<n;++i)
  {
    ushort c = StringGetCharacter(s,i);
    if((c>='A' && c<='Z') || (c>='a' && c<='z') || (c>='0' && c<='9') || c=='-' || c=='_' || c=='.' || c=='~')
      out += StringSubstr(s,i,1);
    else if(c==' ') out+="+";
    else out += StringFormat("%%%02X",c);
  }
  return out;
}

// Base64 helper (for Twilio basic auth) – standalone, cross-version
int ES_StringToBytes(const string s, uchar &out[])
{
  ArrayResize(out,0);
  int n = StringToCharArray(s,out,0,WHOLE_ARRAY,CP_UTF8);
  if(n<=0) return 0;
  // remove trailing null terminator if present
  if(out[n-1]==0) ArrayResize(out,n-1); else ArrayResize(out,n);
  return ArraySize(out);
}

string ES_Base64EncodeBytes(uchar &bytes[])
{
  // Base64 alphabet
  string tbl = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  int len = ArraySize(bytes);
  if(len==0) return "";
  string out="";
  int i=0;
  while(i < len)
  {
    int b0 = bytes[i++];
    int b1 = (i<len) ? bytes[i++] : -1;
    int b2 = (i<len) ? bytes[i++] : -1;

    int triple = (b0 & 0xFF) << 16;
    if(b1>=0) triple |= (b1 & 0xFF) << 8;
    if(b2>=0) triple |= (b2 & 0xFF);

    int c0 = (triple >> 18) & 0x3F;
    int c1 = (triple >> 12) & 0x3F;
    int c2 = (triple >> 6)  & 0x3F;
    int c3 = (triple)       & 0x3F;

    out += StringSubstr(tbl, c0, 1);
    out += StringSubstr(tbl, c1, 1);
    out += (b1>=0) ? StringSubstr(tbl, c2, 1) : "=";
    out += (b2>=0) ? StringSubstr(tbl, c3, 1) : "=";
  }
  return out;
}

string ES_Base64EncodeString(const string s)
{
  uchar arr[]; ES_StringToBytes(s,arr);
  return ES_Base64EncodeBytes(arr);
}

class CEmergencyStop
{
private:
  // Inputs (configured via EA)
  bool     m_enabled;
  double   m_dailyThresholdPct;
  double   m_overallThresholdPct;
  int      m_stopHours;
  string   m_phoneNumber;
  // Email notification only (configure From/To in terminal Options > Email)
  string   m_emailFromLabel;   // informational only; real sender configured in terminal
  string   m_emailToLabel;     // informational only; real recipient configured in terminal

  // State
  bool     m_stopped;
  datetime m_stopStart;
  double   m_dailyHighEquity;
  double   m_initialBalance;
  int      m_currentYDay;   // day-of-year for reset
  long     m_accountLogin;
  datetime m_lastNotifyAt;
  // Event edges for external notifiers (e.g., Telegram)
  bool     m_edgeTriggered;
  bool     m_edgeEnded;
  string   m_lastTriggerText;
  string   m_lastEndText;

  // Derived persistent keys
  string   kInitialBalance;
  string   kStopStart;
  string   kStopped;
  string   kDailyHigh;
  string   kCurrentYDay;

  // Build persistent key per-account
  string Key(const string name) const
  {
    return StringFormat("ES.%s.%ld",name,m_accountLogin);
  }

  // Persistence helpers
  void Persist()
  {
    GlobalVariableSet(kInitialBalance, m_initialBalance);
    GlobalVariableSet(kStopStart,     (double)m_stopStart);
    GlobalVariableSet(kStopped,       m_stopped ? 1.0 : 0.0);
    GlobalVariableSet(kDailyHigh,     m_dailyHighEquity);
    GlobalVariableSet(kCurrentYDay,   (double)m_currentYDay);
  }

  void Load()
  {
    if(GlobalVariableCheck(kInitialBalance)) m_initialBalance = GlobalVariableGet(kInitialBalance); else m_initialBalance = ES_AccountBalance();
    if(GlobalVariableCheck(kStopStart))      m_stopStart      = (datetime)GlobalVariableGet(kStopStart); else m_stopStart=0;
    if(GlobalVariableCheck(kStopped))        m_stopped        = (GlobalVariableGet(kStopped)>0.5);
    if(GlobalVariableCheck(kDailyHigh))      m_dailyHighEquity= GlobalVariableGet(kDailyHigh); else m_dailyHighEquity=ES_AccountEquity();
    if(GlobalVariableCheck(kCurrentYDay))    m_currentYDay    = (int)GlobalVariableGet(kCurrentYDay); else m_currentYDay= ES_DayOfYear(TimeCurrent());
  }

  // Email sending only; relies on terminal email settings
  bool SendAlertEmail(const string subject, const string text)
  {
    // Throttle to avoid duplicates within 60 seconds
    datetime now = TimeCurrent();
    if(m_lastNotifyAt>0 && (now - m_lastNotifyAt) < 60) return true;
    bool ok = SendMail(subject, text);
    if(!ok) ok = SendNotification(subject+"\n"+text); // optional push fallback
    if(ok) m_lastNotifyAt = now;
    return ok;
  }

  void TriggerStopIfNeeded(const double dailyDrawdownPct, const double overallDrawdownPct)
  {
    if(m_stopped) return;
    bool breach = (m_dailyThresholdPct>0 && dailyDrawdownPct >= m_dailyThresholdPct) ||
                  (m_overallThresholdPct>0 && overallDrawdownPct >= m_overallThresholdPct);
    if(!breach) return;

    m_stopped   = true;
    m_stopStart = TimeCurrent();
    Persist();

    string text = StringFormat(
      "EMERGENCY STOP ACTIVATED\nDaily DD: %.2f%% (thr %.2f%%)\nOverall DD: %.2f%% (thr %.2f%%)\nPaused for %d hours.",
      dailyDrawdownPct, m_dailyThresholdPct, overallDrawdownPct, m_overallThresholdPct, m_stopHours
    );
    // Record edge so EA can send Telegram alert
    m_edgeTriggered = true;
    m_lastTriggerText = text;
    Print("[EmergencyStop] ", text);
  }

  void MaybeResume()
  {
    if(!m_stopped) return;
    if(m_stopStart==0) { m_stopped=false; Persist(); return; }
    int elapsed = (int)(TimeCurrent() - m_stopStart);
    if(elapsed >= m_stopHours*3600)
    {
      m_stopped=false;
      m_stopStart=0;
      Persist();
      Print("[EmergencyStop] Stop period ended. Resuming normal operation.");
      m_edgeEnded = true;
      m_lastEndText = "Emergency stop ended. Resuming normal operation.";
    }
  }

public:
  CEmergencyStop():
    m_enabled(true),
    m_dailyThresholdPct(4.0),
    m_overallThresholdPct(8.0),
    m_stopHours(24),
    m_phoneNumber("4694739265"),
    m_emailFromLabel(""), m_emailToLabel(""),
    m_stopped(false), m_stopStart(0), m_dailyHighEquity(0), m_initialBalance(0),
    m_currentYDay(0), m_accountLogin(0), m_lastNotifyAt(0),
    m_edgeTriggered(false), m_edgeEnded(false), m_lastTriggerText(""), m_lastEndText("")
  {}

  void Configure(
    const bool enabled,
    const double dailyThresholdPct,
    const double overallThresholdPct,
    const int stopHours,
    const string phoneNumber,
    const bool  unusedSmsUseTwilio,       // deprecated
    const string emailFromLabel,
    const string emailToLabel,
    const string unusedTwilioFrom
  )
  {
    m_enabled = enabled;
    m_dailyThresholdPct = dailyThresholdPct;
    m_overallThresholdPct = overallThresholdPct;
    m_stopHours = stopHours;
    m_phoneNumber = phoneNumber;
    m_emailFromLabel = emailFromLabel;
    m_emailToLabel   = emailToLabel;
  }

  void OnInit()
  {
    m_accountLogin = ES_AccountLogin();
    kInitialBalance = Key("InitialBalance");
    kStopStart      = Key("StopStart");
    kStopped        = Key("Stopped");
    kDailyHigh      = Key("DailyHighEquity");
    kCurrentYDay    = Key("DayOfYear");

    Load();
    // Initialize defaults
    if(m_initialBalance<=0) m_initialBalance = ES_AccountBalance();
    if(m_dailyHighEquity<=0) m_dailyHighEquity = ES_AccountEquity();
    if(m_currentYDay<=0) m_currentYDay = ES_DayOfYear(TimeCurrent());
    Persist();

    // If stop persisted and still active, keep it
    if(m_stopped) MaybeResume();
  }

  void OnDeinit()
  {
    Persist();
  }

  // Should be called periodically (e.g., every second) and before send
  void OnTimer()
  {
    if(!m_enabled) return;

    datetime now = TimeCurrent();
    int yday = ES_DayOfYear(now);
    double eq  = ES_AccountEquity();
    double bal = ES_AccountBalance();

    // Daily reset at new day
    if(yday != m_currentYDay)
    {
      m_currentYDay = yday;
      m_dailyHighEquity = eq;  // reset high to current equity at day start
      Persist();
      Print("[EmergencyStop] New day: reset daily high equity.");
    }

    // Track daily high
    if(eq > m_dailyHighEquity) { m_dailyHighEquity = eq; Persist(); }

    // Compute drawdowns
    double dailyDD = 0.0;
    if(m_dailyHighEquity>0.0) dailyDD = (m_dailyHighEquity - eq) / m_dailyHighEquity * 100.0;

    double overallDD = 0.0;
    // Use initial balance as baseline; if deposit increased, allow manual reset via input or code
    if(m_initialBalance<=0.0) m_initialBalance = bal;
    if(m_initialBalance>0.0) overallDD = (m_initialBalance - eq) / m_initialBalance * 100.0;

    // Trigger / resume
    TriggerStopIfNeeded(dailyDD, overallDD);
    MaybeResume();
  }

  // Manual reset of overall baseline (e.g., after deposit)
  void ResetOverallBaselineToCurrentBalance()
  {
    m_initialBalance = ES_AccountBalance();
    Persist();
  }

  bool IsStopped() const { return m_enabled && m_stopped; }

  // Gate before sending Telegram
  bool CanSendTelegramMessage()
  {
    if(!m_enabled) return true;
    // Update state just-in-time
    OnTimer();
    return !m_stopped;
  }

  // Consume "just triggered" event and get formatted alert text
  bool TakeEmergencyTriggered(string &out)
  {
    if(!m_edgeTriggered) return false;
    out = m_lastTriggerText;
    m_edgeTriggered = false;
    return true;
  }

  // Consume "just ended" event (not used now but provided for completeness)
  bool TakeEmergencyEnded(string &out)
  {
    if(!m_edgeEnded) return false;
    out = m_lastEndText;
    m_edgeEnded = false;
    return true;
  }
};

#endif // __EMERGENCY_STOP_MQH__


