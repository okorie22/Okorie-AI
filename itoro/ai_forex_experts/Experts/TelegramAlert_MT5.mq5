//+------------------------------------------------------------------+
//|                                               TelegramAlert_MT5  |
//|                Clean MT5 port – full position/deal model support |
//+------------------------------------------------------------------+
#property version   "4.00"
#property strict

#include <Telegram.mqh>
#include <EmergencyStop.mqh>

//--- inputs
input string InpChannelName = "-1002563857196";   // Chat ID or @channel
input string InpToken       = "8207482320:AAFGPbeclzjvcu6Mx1UG7stsYHmOLHG0Sz8";   // Telegram token
input string SignalName     = "Xirsi";
input bool   SendScreenShot = false;
input ENUM_TIMEFRAMES ScreenShotTF = PERIOD_CURRENT;
input bool   MobileNotification   = false;
input bool   EmailNotification    = false;

//--- Emergency Stop settings
input bool   EmergencyStopEnabled      = true;   // Enable emergency stop
input double EmergencyDailyDrawdownPct = 4.0;    // Daily drawdown threshold (%)
input double EmergencyOverallDrawdownPct = 8.0;  // Overall drawdown threshold (%)
input int    EmergencyStopHours        = 24;     // Stop duration (hours)
input string EmergencyPhoneNumber      = ""; // Phone for SMS/Push
// Optional: Twilio integration for SMS (requires adding api.twilio.com to WebRequest list)
input bool   SmsUseTwilio              = false;  // Use Twilio for SMS
input string TwilioSID                 = "";     // Twilio Account SID
input string TwilioAuthToken           = "";     // Twilio Auth Token
input string TwilioFrom                = "";     // Twilio phone number (from)

//--- bot instance
CCustomBot bot;

//--- emergency stop instance
CEmergencyStop g_es;

//--- simple struct to track an active position
struct PState
{
   ulong   ticket;      // POSITION_IDENTIFIER
   long    msgId;       // telegram message id of the OP message
   double  vol;         // volume
   double  sl;
   double  tp;
   int     type;        // original buy/sell
   string  symbol;
};
PState positions[];

// Track active pending-limit orders so we can thread modify/cancel messages
struct OState
{
   ulong   order;     // ORDER_TICKET
   long    msgId;     // telegram message id of the initial message
   string  symbol;
   int     type;      // ORDER_TYPE_*
   double  price;     // ORDER_PRICE_OPEN
   double  volInit;   // ORDER_VOLUME_INITIAL (lots)
   double  volRem;    // ORDER_VOLUME_CURRENT (lots remaining)
   double  sl;        // ORDER_SL
   double  tp;        // ORDER_TP
};
OState orders[];

// Track orders that were just fully filled so we can suppress cancel and OPEN notifications reliably
struct FilledEdge { ulong order; long msgId; datetime at; };
FilledEdge justFilled[];

// Queue of cancels to be sent after a short delay to avoid false cancels when broker emits ORDER_DELETE before DEAL_ADD
struct CancelItem { OState os; string reason; datetime at; };
CancelItem cancelQueue[];

bool IsPendingOrderType(const int t)
{
   return (t==ORDER_TYPE_BUY_LIMIT || t==ORDER_TYPE_SELL_LIMIT ||
           t==ORDER_TYPE_BUY_STOP  || t==ORDER_TYPE_SELL_STOP  ||
           t==ORDER_TYPE_BUY_STOP_LIMIT || t==ORDER_TYPE_SELL_STOP_LIMIT);
}

void AddFilledEdge(const ulong order, const long msgId)
{
   int n=ArraySize(justFilled);
   ArrayResize(justFilled,n+1);
   justFilled[n].order=order;
   justFilled[n].msgId=msgId;
   justFilled[n].at=TimeCurrent();
}

bool TakeFilledEdgeIfRecent(const ulong order, const int windowSec)
{
   datetime now = TimeCurrent();
   for(int i=0;i<ArraySize(justFilled);++i)
   {
      if(justFilled[i].order==order)
      {
         bool recent = (now-justFilled[i].at <= windowSec);
         ArrayRemove(justFilled,i);
         return recent;
      }
   }
   return false;
}

// Persist telegram message id for each order ticket so replies are always threaded
string GVKeyOrderMsg(const ulong order)
{
   return StringFormat("TG.MSG.ORDER.%I64u", order);
}

void SaveOrderMsgId(const ulong order, const long msgId)
{
   if(order==0 || msgId<=0) return;
   GlobalVariableSet(GVKeyOrderMsg(order), (double)msgId);
}

long LoadOrderMsgId(const ulong order)
{
   if(order==0) return 0;
   string k = GVKeyOrderMsg(order);
   if(GlobalVariableCheck(k))
      return (long)GlobalVariableGet(k);
   return 0;
}

// Persist and retrieve threading id for positions so all position events reply to the pending root
string GVKeyPosMsg(const ulong posTicket)
{
   return StringFormat("TG.MSG.POS.%I64u", posTicket);
}

void SavePositionMsgId(const ulong posTicket, const long msgId)
{
   if(posTicket==0 || msgId<=0) return;
   GlobalVariableSet(GVKeyPosMsg(posTicket), (double)msgId);
}

long LoadPositionMsgId(const ulong posTicket)
{
   if(posTicket==0) return 0;
   string k = GVKeyPosMsg(posTicket);
   if(GlobalVariableCheck(k)) return (long)GlobalVariableGet(k);
   return 0;
}

// Resolve and persist a thread id for a position by looking up its originating order
long ResolvePositionThreadId(const ulong posTicket)
{
   if(posTicket==0) return 0;
   datetime now = TimeCurrent();
   HistorySelect(now - 30*86400, now);
   int total = HistoryDealsTotal();
   for(int i=total-1; i>=0; --i)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(!HistoryDealSelect(dealTicket)) continue;
      ulong posId = (ulong)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
      if(posId!=posTicket) continue;
      ENUM_DEAL_ENTRY e = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
      if(e==DEAL_ENTRY_IN)
      {
         ulong ord = (ulong)HistoryDealGetInteger(dealTicket, DEAL_ORDER);
         long omid = LoadOrderMsgId(ord);
         if(omid>0)
         {
            SavePositionMsgId(posTicket, omid);
            return omid;
         }
      }
   }
   // Fallback to any previously saved thread id for this position
   return LoadPositionMsgId(posTicket);
}

// Return true if there is at least one recent deal associated with the order id
bool HasRecentDealsForOrder(const ulong orderId, const int lookbackSec)
{
   if(orderId==0) return false;
   datetime now = TimeCurrent();
   datetime from = now - MathMax(lookbackSec, 1);
   HistorySelect(from, now);
   int total = HistoryDealsTotal();
   for(int i=total-1; i>=0; --i)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(!HistoryDealSelect(dealTicket)) continue;
      ulong ord = (ulong)HistoryDealGetInteger(dealTicket, DEAL_ORDER);
      if(ord==orderId)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert init                                                       |
//+------------------------------------------------------------------+
int OnInit()
  {
   bot.Token(InpToken);
   if(bot.GetMe()!=0)
   {
      Print("Telegram token invalid or WebRequest blocked");
      return(INIT_FAILED);
   }
    // Configure emergency stop
    g_es.Configure(
      EmergencyStopEnabled,
      EmergencyDailyDrawdownPct,
      EmergencyOverallDrawdownPct,
      EmergencyStopHours,
      EmergencyPhoneNumber,
      SmsUseTwilio,
      TwilioSID,
      TwilioAuthToken,
      TwilioFrom
    );
    g_es.OnInit();
   // create a 1-second timer to poll SL/TP modifications
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ArrayFree(positions);
    g_es.OnDeinit();
  }
//+------------------------------------------------------------------+
//| Utility – find index in positions[] by ticket                     |
//+------------------------------------------------------------------+
int FindPosIndex(ulong ticket)
{
   for(int i=0;i<ArraySize(positions);i++)
      if(positions[i].ticket==ticket)
         return i;
   return -1;
  }

//+------------------------------------------------------------------+
//| Send helpers                                                      |
//+------------------------------------------------------------------+
long SendMsg(const string text,long replyTo=0)
{
   // Emergency stop gate
   if(!g_es.CanSendTelegramMessage())
      return 0;

   // Per-chat pacing to avoid Telegram 429 rate limits (~1 msg/sec per chat)
   static uint last_ms = 0;
   uint now = GetTickCount();
   if(last_ms>0)
   {
      uint elapsed = now - last_ms;
      if(elapsed < 1000) Sleep(1000 - elapsed);
   }

   int res = 0;
   if(SendScreenShot)
   {
      // screenshot path not implemented yet for MT5
      res = bot.SendMessage(InpChannelName,text);
   }
   else
   {
      res = (replyTo>0)
            ? bot.SendMessageReply(InpChannelName,text,replyTo)
            : bot.SendMessage(InpChannelName,text);
   }

   long mid = bot.LastMessageId();

   // Retry once on transient failure
   if(mid<=0 || res!=0)
   {
      Sleep(1200);
      res = (replyTo>0)
            ? bot.SendMessageReply(InpChannelName,text,replyTo)
            : bot.SendMessage(InpChannelName,text);
      mid = bot.LastMessageId();
   }

   last_ms = GetTickCount();

   if(MobileNotification)  SendNotification(text);
   if(EmailNotification)   SendMail("Order Notification",text);
   return mid;
}

// Find index in orders[] by order ticket
int FindOrderIndex(ulong order)
{
   for(int i=0;i<ArraySize(orders);i++)
      if(orders[i].order==order)
         return i;
   return -1;
}

string FormatType(int t)
{
   switch(t)
   {
      case POSITION_TYPE_BUY:  return "buy";
      case POSITION_TYPE_SELL: return "sell";
      default: return "?";
   }
}

// Human readable order type for pending orders
string FormatOrderType(const int t)
{
   switch(t)
   {
      case ORDER_TYPE_BUY_LIMIT:  return "buy limit";
      case ORDER_TYPE_SELL_LIMIT: return "sell limit";
      case ORDER_TYPE_BUY_STOP:   return "buy stop";
      case ORDER_TYPE_SELL_STOP:  return "sell stop";
      case ORDER_TYPE_BUY_STOP_LIMIT:  return "buy stop limit";
      case ORDER_TYPE_SELL_STOP_LIMIT: return "sell stop limit";
      default: return "?";
   }
}

//+------------------------------------------------------------------+
//| Helper: correct digits for a given symbol                         |
//+------------------------------------------------------------------+
int DigitsFor(const string sym)
{
   int d = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   return (d>0 ? d : _Digits);
}

//+------------------------------------------------------------------+
//| Helper to label closed amount                                     |
//+------------------------------------------------------------------+
string CloseLabel(double prev,double closed,double after)
{
   if(after<=0.0000001)
      return "CLOSED ALL";
   double r = closed/prev;
   if(MathAbs(r-0.50) < 0.05)
      return "CLOSED HALF";
   return "CLOSED PARTIAL";
}
//+------------------------------------------------------------------+
//| Build and send OPEN message                                       |
//+------------------------------------------------------------------+
long NotifyOpen(const ulong ticket, long replyTo=0)
{
   string sym   = (string)PositionGetString(POSITION_SYMBOL);
   int    type  = (int)PositionGetInteger(POSITION_TYPE);
   double price = PositionGetDouble(POSITION_PRICE_OPEN);
   double vol   = PositionGetDouble(POSITION_VOLUME);
   double sl    = PositionGetDouble(POSITION_SL);
   double tp    = PositionGetDouble(POSITION_TP);
   datetime tm  = (datetime)PositionGetInteger(POSITION_TIME);

   string msg = StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: OPEN\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",
                              SignalName,sym,FormatType(type),
                              DoubleToString(price,DigitsFor(sym)),
                              TimeToString(tm),DoubleToString(vol,2),
                              DoubleToString(tp,DigitsFor(sym)),DoubleToString(sl,DigitsFor(sym)));
   long id = SendMsg(msg, replyTo);
   return id;
}
//+------------------------------------------------------------------+
//| Build and send MODIFY message                                     |
//+------------------------------------------------------------------+
void NotifyModify(const PState &ps)
{
   string sym = ps.symbol;
   int type   = ps.type;
   double price= PositionGetDouble(POSITION_PRICE_OPEN);
   double vol  = PositionGetDouble(POSITION_VOLUME);
   double sl   = PositionGetDouble(POSITION_SL);
   double tp   = PositionGetDouble(POSITION_TP);

   string msg = StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: Order Modified\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",
                              SignalName,sym,FormatType(type),
                              DoubleToString(price,DigitsFor(sym)),
                              TimeToString(TimeCurrent()),DoubleToString(vol,2),
                              DoubleToString(tp,DigitsFor(sym)),DoubleToString(sl,DigitsFor(sym)));
   // Always reply to the pending root thread id
   long replyId = ResolvePositionThreadId(ps.ticket);
   if(replyId>0)
      SendMsg(msg,replyId);
}
//+------------------------------------------------------------------+
//| Build and send CLOSE message                                      |
//+------------------------------------------------------------------+
void NotifyClose(const PState &ps,const double closedVol,const double closePrice)
{
   string sym = ps.symbol;
   int type   = ps.type;

   string action = CloseLabel(ps.vol, closedVol, PositionSelectByTicket(ps.ticket)?PositionGetDouble(POSITION_VOLUME):0.0);
   string msg = StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: %s\nPrice: %s\nTime: %s\nLots: %s", SignalName,sym,FormatType(type),action, DoubleToString(closePrice,DigitsFor(sym)),TimeToString(TimeCurrent()),DoubleToString(closedVol,2));
   // Always reply to the pending root thread id
   long replyId = ResolvePositionThreadId(ps.ticket);
   if(replyId>0)
      SendMsg(msg,replyId);
}

//+------------------------------------------------------------------+
//| Pending orders: Build and send PLACE message                      |
//+------------------------------------------------------------------+
long NotifyPendingPlace(const ulong order_ticket)
{
   string sym   = OrderGetString(ORDER_SYMBOL);
   int    type  = (int)OrderGetInteger(ORDER_TYPE);
   double price = OrderGetDouble(ORDER_PRICE_OPEN);
   double vol   = OrderGetDouble(ORDER_VOLUME_INITIAL);
   double sl    = OrderGetDouble(ORDER_SL);
   double tp    = OrderGetDouble(ORDER_TP);
   datetime tm  = (datetime)OrderGetInteger(ORDER_TIME_SETUP);

   // Per requirement: present pending order placements as Action: OPEN to align with copier behavior
   string msg = StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: OPEN\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",
                              SignalName, sym, FormatOrderType(type),
                              DoubleToString(price,DigitsFor(sym)),
                              TimeToString(tm), DoubleToString(vol,2),
                              DoubleToString(tp,DigitsFor(sym)), DoubleToString(sl,DigitsFor(sym)));
   long mid = SendMsg(msg);
   // Persist mapping so all future updates reply under this message
   SaveOrderMsgId(order_ticket, mid);
   return mid;
}

//+------------------------------------------------------------------+
//| Pending orders: Build and send MODIFY message                     |
//+------------------------------------------------------------------+
void NotifyPendingModify(const OState &os)
{
   string sym   = os.symbol;
   int    type  = os.type;
   double price = OrderGetDouble(ORDER_PRICE_OPEN);
   double vol   = OrderGetDouble(ORDER_VOLUME_INITIAL);
   double sl    = OrderGetDouble(ORDER_SL);
   double tp    = OrderGetDouble(ORDER_TP);

   string msg = StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: Order Modified\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",
                              SignalName, sym, FormatOrderType(type),
                              DoubleToString(price,DigitsFor(sym)),
                              TimeToString(TimeCurrent()), DoubleToString(vol,2),
                              DoubleToString(tp,DigitsFor(sym)), DoubleToString(sl,DigitsFor(sym)));
   SendMsg(msg, os.msgId);
}

//+------------------------------------------------------------------+
//| Pending orders: Build and send CANCEL message                     |
//+------------------------------------------------------------------+
void NotifyPendingCancel(const OState &os, const string reason)
{
   string msg = StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: %s\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",
                              SignalName, os.symbol, FormatOrderType(os.type), reason,
                              DoubleToString(os.price,DigitsFor(os.symbol)),
                              TimeToString(TimeCurrent()), DoubleToString(os.volRem,2),
                              DoubleToString(os.tp,DigitsFor(os.symbol)), DoubleToString(os.sl,DigitsFor(os.symbol)));
   SendMsg(msg, os.msgId);
}

//+------------------------------------------------------------------+
//| Pending orders: Build and send PARTIAL/FULL fill message          |
//+------------------------------------------------------------------+
void NotifyPendingClosed(const OState &os, const double volClosed, const double fillPrice)
{
   double prev = os.volRem + volClosed;
   double after = os.volRem;
   string action = CloseLabel(prev, volClosed, after);
   string msg = StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: %s\nPrice: %s\nTime: %s\nLots: %s",
                              SignalName, os.symbol, FormatOrderType(os.type), action,
                              DoubleToString(fillPrice,DigitsFor(os.symbol)),
                              TimeToString(TimeCurrent()), DoubleToString(volClosed,2));
   SendMsg(msg, os.msgId);
}


//+------------------------------------------------------------------+
//| Trade Transaction handler – central event hub                     |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &tx,
                        const MqlTradeRequest      &req,
                        const MqlTradeResult       &res)
{
   // Track if an OPEN that appears later in this callback came from a pending fill
   long replyToForOpen = 0;
   // 1) Handle pending order lifecycle (Buy/Sell Limit and others)
   if(tx.type==TRADE_TRANSACTION_ORDER_ADD || tx.type==TRADE_TRANSACTION_ORDER_UPDATE || tx.type==TRADE_TRANSACTION_ORDER_DELETE)
   {
      // ORDER_ADD / UPDATE rely on current order pool; ORDER_DELETE uses history
      if(tx.type==TRADE_TRANSACTION_ORDER_ADD || tx.type==TRADE_TRANSACTION_ORDER_UPDATE)
      {
          if(!OrderSelect(tx.order)) return; // not found (shouldn't happen)
         int otype = (int)OrderGetInteger(ORDER_TYPE);
          if(!IsPendingOrderType(otype))
         {
            // Only handle limit orders per requirements
         }
         else
         {
            if(tx.type==TRADE_TRANSACTION_ORDER_ADD)
            {
               // Create state, send initial PENDING message
               int newIdx = ArraySize(orders);
               ArrayResize(orders,newIdx+1);
               orders[newIdx].order  = tx.order;
               orders[newIdx].symbol = OrderGetString(ORDER_SYMBOL);
               orders[newIdx].type   = otype;
               orders[newIdx].price  = OrderGetDouble(ORDER_PRICE_OPEN);
               orders[newIdx].volInit= OrderGetDouble(ORDER_VOLUME_INITIAL);
               orders[newIdx].volRem = OrderGetDouble(ORDER_VOLUME_CURRENT);
               orders[newIdx].sl     = OrderGetDouble(ORDER_SL);
               orders[newIdx].tp     = OrderGetDouble(ORDER_TP);
               long mid = NotifyPendingPlace(tx.order);
               orders[newIdx].msgId = mid;
            }
            else // UPDATE
            {
               int oidx = FindOrderIndex(tx.order);
               if(oidx>=0)
               {
                  // Detect changes and send a modify message
                  double curPrice = OrderGetDouble(ORDER_PRICE_OPEN);
                  double curSL    = OrderGetDouble(ORDER_SL);
                  double curTP    = OrderGetDouble(ORDER_TP);
                  if(!MathCompare(curPrice,orders[oidx].price) || !MathCompare(curSL,orders[oidx].sl) || !MathCompare(curTP,orders[oidx].tp))
                  {
                     NotifyPendingModify(orders[oidx]);
                     orders[oidx].price = curPrice;
                     orders[oidx].sl    = curSL;
                     orders[oidx].tp    = curTP;
                  }
                  // Always refresh remaining volume to reflect partial fills
                  orders[oidx].volRem = OrderGetDouble(ORDER_VOLUME_CURRENT);
               }
               else
               {
                  // Not tracked (e.g., EA attached after placement). Track it now and send initial message.
                  int newIdx2 = ArraySize(orders);
                  ArrayResize(orders,newIdx2+1);
                  orders[newIdx2].order  = tx.order;
                  orders[newIdx2].symbol = OrderGetString(ORDER_SYMBOL);
                  orders[newIdx2].type   = otype;
                  orders[newIdx2].price  = OrderGetDouble(ORDER_PRICE_OPEN);
                  orders[newIdx2].volInit= OrderGetDouble(ORDER_VOLUME_INITIAL);
                  orders[newIdx2].volRem = OrderGetDouble(ORDER_VOLUME_CURRENT);
                  orders[newIdx2].sl     = OrderGetDouble(ORDER_SL);
                  orders[newIdx2].tp     = OrderGetDouble(ORDER_TP);
                  long knownMid = LoadOrderMsgId(tx.order);
                  if(knownMid<=0) knownMid = NotifyPendingPlace(tx.order);
                  orders[newIdx2].msgId = knownMid;
               }
            }
         }
      }
      else if(tx.type==TRADE_TRANSACTION_ORDER_DELETE)
      {
          // Order moved to history; decide if it was canceled/expired or filled
          // Ensure history range is available for immediate lookup across brokers
          HistorySelect(TimeCurrent()-30*86400, TimeCurrent());
          bool inHistory = HistoryOrderSelect(tx.order);
          int otypeH = inHistory ? (int)HistoryOrderGetInteger(tx.order, ORDER_TYPE) : -1;
          int state   = inHistory ? (int)HistoryOrderGetInteger(tx.order, ORDER_STATE) : -1;
          // If history not yet available, try to use cached order state and treat as cancel unless we saw a recent fill edge
          if(!inHistory)
          {
             int oidxTmp = FindOrderIndex(tx.order);
             if(oidxTmp>=0 && IsPendingOrderType(orders[oidxTmp].type))
             {
                if(!TakeFilledEdgeIfRecent(orders[oidxTmp].order, 3))
                {
                   NotifyPendingCancel(orders[oidxTmp], "CANCELLED");
                }
                ArrayRemove(orders, oidxTmp);
             }
             return;
          }
          if(IsPendingOrderType(otypeH))
         {
            int oidx = FindOrderIndex(tx.order);
            // Prepare state (fallback to history if we didn't track)
            OState os;
            if(oidx>=0)
               os = orders[oidx];
            else
            {
               os.order  = tx.order;
               os.symbol = HistoryOrderGetString(tx.order, ORDER_SYMBOL);
               os.type   = otypeH;
               os.price  = HistoryOrderGetDouble(tx.order, ORDER_PRICE_OPEN);
               os.volInit= HistoryOrderGetDouble(tx.order, ORDER_VOLUME_INITIAL);
               os.volRem = HistoryOrderGetDouble(tx.order, ORDER_VOLUME_CURRENT);
               os.sl     = HistoryOrderGetDouble(tx.order, ORDER_SL);
               os.tp     = HistoryOrderGetDouble(tx.order, ORDER_TP);
               os.msgId  = LoadOrderMsgId(tx.order);
            }
            
            // Notify cancellations/expiration of non-triggered orders. Do not send CLOSED ALL on fill.
            if(state==ORDER_STATE_CANCELED || state==ORDER_STATE_EXPIRED || state==ORDER_STATE_REJECTED)
            {
               // If there are recent deals linked to this order, treat as filled; suppress cancel and any OPEN
               if(HasRecentDealsForOrder(os.order, 20) || TakeFilledEdgeIfRecent(os.order, 20))
               {
                  // suppress
               }
               else
               {
                  int qi = ArraySize(cancelQueue);
                  ArrayResize(cancelQueue, qi+1);
                  cancelQueue[qi].os = os;
                  cancelQueue[qi].reason = (state==ORDER_STATE_EXPIRED ? "EXPIRED" : "CANCELLED");
                  cancelQueue[qi].at = TimeCurrent();
               }
            }
            // If order is fully filled, send CLOSED ALL if remaining > 0 (safety to avoid duplicates)
            else if(state==ORDER_STATE_FILLED)
            {
               // Fully filled: no cancel/closed messages; record edge with msgId to suppress false cancels and thread if ever needed
               AddFilledEdge(os.order, os.msgId);
            }
            // Remove from tracked array if we had it
            if(oidx>=0) ArrayRemove(orders, oidx);
         }
      }
      // After handling order events, continue to process deals if present
      // Do not return here; the same transaction callback may have both fields unused
   }

   // 2) Handle position lifecycle via deals (original behavior)
   if(tx.type!=TRADE_TRANSACTION_DEAL_ADD) return;

   if(!HistoryDealSelect(tx.deal)) return;
   ENUM_DEAL_ENTRY dEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(tx.deal, DEAL_ENTRY);
   // Map this deal back to a pending order (e.g., partial/complete fill of any pending order type)
   ulong relatedOrder = (ulong)HistoryDealGetInteger(tx.deal, DEAL_ORDER);
   if(relatedOrder>0)
   {
      int oidx = FindOrderIndex(relatedOrder);
      if(oidx>=0 && IsPendingOrderType(orders[oidx].type))
      {
         double volClosed = HistoryDealGetDouble(tx.deal, DEAL_VOLUME);
         // Guard against negative/zero
         if(volClosed>0.0)
         {
            // Decrease remaining and notify
            double newRem = MathMax(0.0, orders[oidx].volRem - volClosed);
            OState snapshot = orders[oidx];
            snapshot.volRem = newRem; // after state for action label
            // The CloseLabel expects prev, closed, after; handled inside NotifyPendingClosed
            // Send partial notifications only; for full fills we will not notify (requirement)
            if(newRem>0.0)
               NotifyPendingClosed(snapshot, volClosed, tx.price);
            orders[oidx].volRem = newRem;
            if(newRem<=0.0)
            {
                // fully filled – mark to suppress OPEN announcement later and store msgId in edge memory
                replyToForOpen = orders[oidx].msgId; // presence >0 means came from pending
                AddFilledEdge(relatedOrder, orders[oidx].msgId);
               ArrayRemove(orders, oidx);
            }
         }
      }
   }
   ulong posTicket = (ulong)HistoryDealGetInteger(tx.deal, DEAL_POSITION_ID);
   if(posTicket==0) return;

   int idx = FindPosIndex(posTicket);

   if(dEntry==DEAL_ENTRY_IN)
   {
      if(idx<0)
      {
         if(!PositionSelectByTicket(posTicket)) return;
         int newIdx = ArraySize(positions);
         ArrayResize(positions,newIdx+1);
         positions[newIdx].ticket = posTicket;
         positions[newIdx].symbol = PositionGetString(POSITION_SYMBOL);
         positions[newIdx].type   = (int)PositionGetInteger(POSITION_TYPE);
         positions[newIdx].sl     = PositionGetDouble(POSITION_SL);
         positions[newIdx].tp     = PositionGetDouble(POSITION_TP);
         positions[newIdx].vol    = PositionGetDouble(POSITION_VOLUME);
         // Suppress OPEN if this position comes from a recent pending fill
         bool suppressOpen = false;
         ulong openRelatedOrder = (ulong)HistoryDealGetInteger(tx.deal, DEAL_ORDER);
         if(openRelatedOrder>0)
            suppressOpen = TakeFilledEdgeIfRecent(openRelatedOrder, 15);
          // Always thread position OPEN under the original pending order if available
          long threadId = replyToForOpen;
          if(threadId<=0 && openRelatedOrder>0) threadId = LoadOrderMsgId(openRelatedOrder);
          if(threadId<=0) threadId = ResolvePositionThreadId(posTicket);
          if(threadId>0)
          {
             // Always send OPEN as a reply to the original pending order's message id
             NotifyOpen(posTicket, threadId);
             // Persist the thread id for this position so all future updates reply to the same pending root
             SavePositionMsgId(posTicket, threadId);
          }
          else
          {
             // Market execution: send initial OPEN as root message and persist its message id for threading
             long rootMsgId = NotifyOpen(posTicket, 0);
             if(rootMsgId>0)
             {
                SavePositionMsgId(posTicket, rootMsgId);
                positions[newIdx].msgId = rootMsgId;
             }
          }
      }
      else
      {
         positions[idx].vol = PositionGetDouble(POSITION_VOLUME);
      }
   }
   else if(dEntry==DEAL_ENTRY_OUT)
   {
      if(idx<0) return;

      double volAfter = PositionSelectByTicket(posTicket) ? PositionGetDouble(POSITION_VOLUME) : 0.0;
      double volClosed= positions[idx].vol - volAfter;
      double priceCls = tx.price;

      NotifyClose(positions[idx],volClosed,priceCls);

      if(volAfter<=0.0)
         ArrayRemove(positions,idx);
      else
         positions[idx].vol = volAfter;
   }
}
//+------------------------------------------------------------------+
//| Timer – detect SL/TP changes                                      |
//+------------------------------------------------------------------+
void OnTimer()
{
   // Update emergency stop state
   g_es.OnTimer();
   // If an emergency stop just triggered, send Telegram alert immediately (bypass gate)
   string esMsg;
   if(g_es.TakeEmergencyTriggered(esMsg))
   {
      bot.SendMessage(InpChannelName, esMsg);
   }
   // Flush delayed cancel queue (send only if no fill edge appeared within small window)
   if(ArraySize(cancelQueue)>0)
   {
      datetime now = TimeCurrent();
      for(int i=ArraySize(cancelQueue)-1;i>=0;i--)
      {
         // wait ~2 seconds before sending to filter out fills; also re-check edge suppression
         if(now - cancelQueue[i].at >= 2)
         {
            if(!TakeFilledEdgeIfRecent(cancelQueue[i].os.order, 15))
               NotifyPendingCancel(cancelQueue[i].os, cancelQueue[i].reason);
            ArrayRemove(cancelQueue,i);
         }
      }
   }

   int total = ArraySize(positions);
   for(int i=0;i<total;i++)
   {
      if(!PositionSelectByTicket(positions[i].ticket)) continue;
      double curSL = PositionGetDouble(POSITION_SL);
      double curTP = PositionGetDouble(POSITION_TP);
      if(!MathCompare(curSL,positions[i].sl) || !MathCompare(curTP,positions[i].tp))
      {
         NotifyModify(positions[i]);
         positions[i].sl = curSL;
         positions[i].tp = curTP;
      }
   }
}
//+------------------------------------------------------------------+
//| helper MathCompare                                                 |
//+------------------------------------------------------------------+
bool MathCompare(double a,double b){return(MathAbs(a-b)<0.0000001);}