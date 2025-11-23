//+------------------------------------------------------------------+
//|                                            TelegramAlert_MT4.mq4 |
//|                                        Copyright 2020, Assetbase |
//|                                         https://t.me/assetbaseTS |
//+------------------------------------------------------------------+
#property copyright "Copyright 2020, Assetbase"
#property link      "https://t.me/assetbaseTS"
#property version   "3.00"
#property strict
#include <Telegram.mqh>
#include <EmergencyStop.mqh>

// helper to describe closed amount
string CloseLabel(double prev,double closed,double after)
{
   if(after<=0.0000001)
      return("CLOSED ALL");
   double r = closed/prev;
   if(MathAbs(r-0.50)<0.05)
      return("CLOSED HALF");
   return("CLOSED PARTIAL");
}


//--- input parameters
input string InpChannelName="-1002563857196";//Channel Name
input string InpToken="8207482320:AAFGPbeclzjvcu6Mx1UG7stsYHmOLHG0Sz8";//Token
extern string mySigalname = "Niani";
input string _template = ""; //TemplateName e.g ADX

input bool AlertonTelegram = true;
input bool UseFormat_forCopier = false;
input bool SendScreenShot = false;
input ENUM_TIMEFRAMES ScreenShotTimeFrame = PERIOD_CURRENT;
input bool MobileNotification = false;
input bool EmailNotification = false;
uint   ServerDelayMilliseconds = 300;
string AllowSymbols            = "";              // Allow Trading Symbols (Ex: EURUSDq,EURUSDx,EURUSDa)

CCustomBot bot;
bool checked;
// Emergency Stop inputs (same defaults as MT5)
input bool   EmergencyStopEnabled      = true;
input double EmergencyDailyDrawdownPct = 4.0;
input double EmergencyOverallDrawdownPct = 8.0;
input int    EmergencyStopHours        = 24;
input string EmergencyPhoneNumber      = "4694739265"; // not used for SMS anymore
// Email labels (configure actual sender/recipient in Terminal Options > Email)
input string EmergencyEmailFromLabel   = "chibuokem.okorie@gmail.com";
input string EmergencyEmailToLabel     = "contact@okemokorie.com";

CEmergencyStop g_es;
uint   pushdelay     = 0;
bool   telegram_runningstatus = false;

int    ordersize            = 0;
int    orderids[];
double orderopenprice[];
double orderlot[];
double ordersl[];
double ordertp[];
long   ordermsgid[];
bool   orderchanged           = false;
bool   orderpartiallyclosed   = false;
int    orderpartiallyclosedid = -1;

int    prev_ordersize         = 0;

//--- Globales File
string local_symbolallow[];
int    symbolallow_size = 0;

//+------------------------------------------------------------------+
//| Debug Functions                                                   |
//+------------------------------------------------------------------+
void TestWebRequestConnection()
{
   // removed verbose connection diagnostics
   string result;
   string url = "https://api.telegram.org/bot" + InpToken + "/getMe";
   char data[];
   char result_array[];
   WebRequest("GET", url, NULL, 5000, data, result_array, result);
}

//+------------------------------------------------------------------+
void TestTelegramConnection()
{
   bot.Token(InpToken);
   int result = bot.GetMe();
   if(result == 0)
      Print("Bot name: ", bot.Name());
}

//+------------------------------------------------------------------+
long SendMessageWithDebug(const string channel, const string message, long reply_to=0)
{
   // Per-chat pacing (~1 msg/sec per chat) to avoid Telegram rate limits
   static uint last_ms = 0;
   uint now = GetTickCount();
   if(last_ms>0)
   {
      uint elapsed = now - last_ms;
      if(elapsed < 1000) Sleep(1000 - elapsed);
   }

   int result = 0;
   if(reply_to>0)
      result = bot.SendMessageReply(channel, message, reply_to);
   else
      result = bot.SendMessage(channel, message);

   long msg_id = bot.LastMessageId();

   // Retry once on transient failure (HTTP error or no message id)
   if(msg_id<=0 || result!=0)
   {
      Sleep(1200);
      if(reply_to>0)
         result = bot.SendMessageReply(channel, message, reply_to);
      else
         result = bot.SendMessage(channel, message);
      msg_id = bot.LastMessageId();
   }

   last_ms = GetTickCount();

   if(result == 0 && msg_id>0)
      return msg_id;
   return (msg_id>0 ? msg_id : result);
}

//+------------------------------------------------------------------+
void TestChatID()
{
   // removed noisy chat-id test message
}

//+------------------------------------------------------------------+
void GetCorrectChatID()
{
   // removed noisy chat-id verification diagnostics
}

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void init()
  {
   // Configure and init emergency stop
   g_es.Configure(
      EmergencyStopEnabled,
      EmergencyDailyDrawdownPct,
      EmergencyOverallDrawdownPct,
      EmergencyStopHours,
      EmergencyPhoneNumber,
      false, // deprecated param
      EmergencyEmailFromLabel,
      EmergencyEmailToLabel,
      ""
   );
   g_es.OnInit();

  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_KEYDOWN &&
      lparam=='Q')
     {

      bot.SendMessage(InpChannelName,"ee\nAt:100\nDDDD");
     }
  }


//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   StopTelegramServer();
   g_es.OnDeinit();

  }
bool copmod = false;
//+------------------------------------------------------------------+
//| Expert program start function                                    |
//+------------------------------------------------------------------+
void start()
  {
   if(DetectEnvironment() == false)
     {
      Alert("Error: The property is fail, please check and try again.");
      return;
     }

   // Minimal bot identification on start
   TestTelegramConnection();

   StartTelegramServer();

  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool DetectEnvironment()
  {


   

   pushdelay     = (ServerDelayMilliseconds > 0) ? ServerDelayMilliseconds : 10;
   telegram_runningstatus  = false;

// Load the Symbol allow map
   if(AllowSymbols != "")
     {
      string symboldata[];
      int    symbolsize = StringSplit(AllowSymbols, ',', symboldata);
      int    symbolindex = 0;

      ArrayResize(local_symbolallow, symbolsize);

      for(symbolindex=0; symbolindex<symbolsize; symbolindex++)
        {
         if(symboldata[symbolindex] == "")
            continue;

         local_symbolallow[symbolindex] = symboldata[symbolindex];
        }

      symbolallow_size = symbolsize;
     }

   return true;
  }

//+------------------------------------------------------------------+
//| Start the Telegram server                                        |
//+------------------------------------------------------------------+
int StartTelegramServer()
  {
   
   bot.Token(InpToken);
    if(!checked)
     {
      if(StringLen(InpChannelName)==0)
        {
         Print("Error: Channel name is empty");
         Sleep(10000);
         return (0);
        }

      int result=bot.GetMe();
      if(result==0)
        {
         Print("Bot name: ",bot.Name());
         checked=true;
        }
      else
        {
         Print("Error: ",GetErrorDescription(result));
         Sleep(10000);
         return(0);
        }
     }

   GetCurrentOrdersOnStart();

   int  changed     = 0;
   uint delay   =    pushdelay;
   uint ticketstart = 0;
   uint tickcount   = 0;

   telegram_runningstatus = true;

   while(!IsStopped())
     {
      // Update emergency stop periodically
      g_es.OnTimer();
      // If emergency stop just triggered, send Telegram alert immediately (bypass gate)
      string esMsg;
      if(g_es.TakeEmergencyTriggered(esMsg))
      {
         bot.SendMessage(InpChannelName, esMsg);
      }
      ticketstart = GetTickCount();
      changed = GetCurrentOrdersOnTicket();

      if(changed > 0)
         UpdateCurrentOrdersOnTicket();

      tickcount = GetTickCount() - ticketstart;

      if(delay > tickcount)
         Sleep(delay-tickcount-2);
     }


  
   return(0);
  }

//+------------------------------------------------------------------+
//| Stop the Telegram server                                         |
//+------------------------------------------------------------------+
void StopTelegramServer()
  {


   ArrayFree(orderids);
   ArrayFree(orderopenprice);
   ArrayFree(orderlot);
   ArrayFree(ordersl);
   ArrayFree(ordertp);
   ArrayFree(ordermsgid);
   ArrayFree(local_symbolallow);



   telegram_runningstatus = false;
  }

//+------------------------------------------------------------------+
//| Get all of the orders                                            |
//+------------------------------------------------------------------+
void GetCurrentOrdersOnStart()
  {
   prev_ordersize = 0;
   ordersize      = OrdersTotal();

   if(ordersize == prev_ordersize)
      return;

   if(ordersize > 0)
     {
      ArrayResize(orderids, ordersize);
      ArrayResize(orderopenprice, ordersize);
      ArrayResize(orderlot, ordersize);
      ArrayResize(ordersl, ordersize);
      ArrayResize(ordertp, ordersize);
      ArrayResize(ordermsgid, ordersize);
     }

   prev_ordersize = ordersize;

   int orderindex = 0;

// Save the orders to cache
   for(orderindex=0; orderindex<ordersize; orderindex++)
     {
      if(OrderSelect(orderindex, SELECT_BY_POS, MODE_TRADES) == false)
         continue;

      orderids[orderindex]       = OrderTicket();
      orderopenprice[orderindex] = OrderOpenPrice();
      orderlot[orderindex]       = OrderLots();
      ordersl[orderindex]        = OrderStopLoss();
      ordertp[orderindex]        = OrderTakeProfit();
//      ordermsgid[orderindex]     = 0;
     }
  }

//+------------------------------------------------------------------+
//| Get all of the orders                                            |
//+------------------------------------------------------------------+
int GetCurrentOrdersOnTicket()
  {
   ordersize = OrdersTotal();

   int changed = 0;

   if(ordersize > prev_ordersize)
     {
      // Trade has been added
      changed = PushOrderOpen();
     }
   else
      if(ordersize < prev_ordersize)
        {
         // Trade has been closed
         changed = PushOrderClosed();
        }
      else
         if(ordersize == prev_ordersize)
           {
            // Trade has been modify
            changed = PushOrderModify();
           }

   return changed;
  }

//+------------------------------------------------------------------+
//| Update all of the orders status                                  |
//+------------------------------------------------------------------+
void UpdateCurrentOrdersOnTicket()
  {
   if(ordersize > 0)
     {
      ArrayResize(orderids, ordersize);
      ArrayResize(orderopenprice, ordersize);
      ArrayResize(orderlot, ordersize);
      ArrayResize(ordersl, ordersize);
      ArrayResize(ordertp, ordersize);
      ArrayResize(ordermsgid, ordersize);
     }

   int orderindex = 0;

// Save the orders to cache
   for(orderindex=0; orderindex<ordersize; orderindex++)
     {
      if(OrderSelect(orderindex, SELECT_BY_POS, MODE_TRADES) == false)
         continue;

      orderids[orderindex]       = OrderTicket();
      orderopenprice[orderindex] = OrderOpenPrice();
      orderlot[orderindex]       = OrderLots();
      ordersl[orderindex]        = OrderStopLoss();
      ordertp[orderindex]        = OrderTakeProfit();
//      ordermsgid[orderindex]     = 0;
     }

// Changed the old orders count as current orders count
   prev_ordersize = ordersize;
  }

//+------------------------------------------------------------------+
//| Push the open order to all of the subscriber                     |
//+------------------------------------------------------------------+
int PushOrderOpen()
  {
   int changed    = 0;

   // ensure message id array size matches current orders
   if(ArraySize(ordermsgid) < ordersize)
      ArrayResize(ordermsgid, ordersize);

   int orderindex = 0;
   string message="";
   for(orderindex=0; orderindex<ordersize; orderindex++)
     {
      if(OrderSelect(orderindex, SELECT_BY_POS, MODE_TRADES) == false)
         continue;

      if(FindOrderInPrevPool(OrderTicket()) == false)
         {
          if(GetOrderSymbolAllowed(OrderSymbol()) == false)
             continue;

          Print("Order Added:", OrderSymbol(), ", Size:", ArraySize(orderids), ", OrderId:", OrderTicket());
          Print("Message Name: ", mySigalname);
         if(UseFormat_forCopier == false){
         message =StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: %s\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",mySigalname,
                               OrderSymbol(),TypeMnem(OrderType()),"OPEN",
                               DoubleToString(OrderOpenPrice(),MarketInfo(OrderSymbol(),MODE_DIGITS)),
                               TimeToString(OrderOpenTime()),DoubleToString(OrderLots(), 2),DoubleToString(OrderTakeProfit(), MarketInfo(OrderSymbol(),MODE_DIGITS)),DoubleToString(OrderStopLoss(), MarketInfo(OrderSymbol(),MODE_DIGITS)));
                               }
                               
                                if(UseFormat_forCopier == true){
         message =StringFormat(" \nAssetname: %s\nType: %s\nStopLoss: %s\nTakeProfit: %s\nLots: %s\nComment: %s",
                                  OrderSymbol(),
                                  TypeMnem(OrderType()),
                                 DoubleToString(OrderStopLoss(), MarketInfo(OrderSymbol(),MODE_DIGITS)),
                                 DoubleToString(OrderTakeProfit(), MarketInfo(OrderSymbol(),MODE_DIGITS)),
                                  DoubleToString(OrderLots(), 2),
                                  mySigalname


                                 );
                                 
                                 }

         ordermsgid[orderindex] = PushToSubscriber(OrderSymbol(), message);

         changed ++;
        }
     }

   return changed;
  }

//+------------------------------------------------------------------+
//| Push the close order to all of the subscriber                    |
//+------------------------------------------------------------------+
int PushOrderClosed()
  {
   int      changed    = 0;
   int      orderindex = 0;
   datetime ctm;
   string message;

   for(orderindex=0; orderindex<prev_ordersize; orderindex++)
     {
      if(OrderSelect(orderids[orderindex], SELECT_BY_TICKET, MODE_TRADES) == false)
         continue;

      ctm = OrderCloseTime();

      if(ctm > 0)
         {
          if(GetOrderSymbolAllowed(OrderSymbol()) == false)
             continue;

          Print("Order Closed:", OrderSymbol(), ", Size:", ArraySize(orderids), ", OrderId:", OrderTicket());
          Print("Message Name: ", mySigalname);
         message =StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: %s\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",mySigalname,
                               OrderSymbol(),TypeMnem(OrderType()),CloseLabel(orderlot[orderindex], orderlot[orderindex], 0),
                               DoubleToString(OrderClosePrice(),MarketInfo(OrderSymbol(),MODE_DIGITS)),
                               TimeToString(OrderCloseTime()),DoubleToString(OrderLots(), 2),DoubleToString(OrderTakeProfit(), MarketInfo(OrderSymbol(),MODE_DIGITS)),                     DoubleToString(OrderStopLoss(), MarketInfo(OrderSymbol(),MODE_DIGITS)));
         PushToSubscriber(OrderSymbol(), message, ordermsgid[orderindex]);

         changed ++;
        }
     }

   return changed;
  }

//+------------------------------------------------------------------+
//| Push the modify order to all of the subscriber                   |
//+------------------------------------------------------------------+
int PushOrderModify()
  {
   int changed    = 0;
   int orderindex = 0;
   string message;
   for(orderindex=0; orderindex<ordersize; orderindex++)
     {
      orderchanged           = false;
      orderpartiallyclosed   = false;
      orderpartiallyclosedid = -1;

      if(OrderSelect(orderindex, SELECT_BY_POS, MODE_TRADES) == false)
         continue;

      if(GetOrderSymbolAllowed(OrderSymbol()) == false)
         continue;

      if(orderlot[orderindex] != OrderLots())
        {
         orderchanged = true;

         string ordercomment = OrderComment();
         int    orderid      = 0;

         // Partially closed a trade
         // Partially closed is a different lots from trade
         if(StringFind(ordercomment, "from #", 0) >= 0)
           {
            if(StringReplace(ordercomment, "from #", "") >= 0)
              {
               orderpartiallyclosed   = true;
               orderpartiallyclosedid = StringToInteger(ordercomment);
              }
           }
        }

      if(ordersl[orderindex] != OrderStopLoss())
         orderchanged = true;

      if(ordertp[orderindex] != OrderTakeProfit())
         orderchanged = true;

      // Temporarily method for recognize modify order or part-closed order
      // Part-close order will close order by a litte lots and re-generate an new order with new order id
      if(orderchanged == true)
        {
         if(orderpartiallyclosed == true)
           {
            Print("Partially Closed:", OrderSymbol(), ", Size:", ArraySize(orderids), ", OrderId:", OrderTicket(), ", Before OrderId: ", orderpartiallyclosedid);
            Print("Message Name: ", mySigalname);
            message =StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: %s\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",mySigalname,
                                  OrderSymbol(),TypeMnem(OrderType()),CloseLabel(orderlot[orderindex], orderlot[orderindex]-OrderLots(), OrderLots()),
                                  DoubleToString(OrderOpenPrice(),(int)MarketInfo(OrderSymbol(),MODE_DIGITS)),
                                  TimeToString(TimeCurrent()),DoubleToString(OrderLots(), 2),DoubleToString(OrderTakeProfit(), (int)MarketInfo(OrderSymbol(),MODE_DIGITS)),DoubleToString(OrderStopLoss(), (int)MarketInfo(OrderSymbol(),MODE_DIGITS)));
            PushToSubscriber(OrderSymbol(), message, ordermsgid[orderindex]);
           }
         else
           {
            Print("Order Modify:", OrderSymbol(), ", Size:", ArraySize(orderids), ", OrderId:", OrderTicket());
            Print("Message Name: ", mySigalname);
            message =StringFormat("Name: %s\nSymbol: %s\nType: %s\nAction: %s\nPrice: %s\nTime: %s\nLots: %s\nTakeProfit: %s\nStopLoss: %s",mySigalname,
                                  OrderSymbol(),TypeMnem(OrderType()),"Order Modified",
                                  DoubleToString(OrderOpenPrice(),(int)MarketInfo(OrderSymbol(),MODE_DIGITS)),
                                  TimeToString(TimeCurrent()),DoubleToString(OrderLots(), 2),DoubleToString(OrderTakeProfit(), (int)MarketInfo(OrderSymbol(),MODE_DIGITS)),DoubleToString(OrderStopLoss(), (int)MarketInfo(OrderSymbol(),MODE_DIGITS)));
            PushToSubscriber(OrderSymbol(), message, ordermsgid[orderindex]);
           }

         changed ++;
        }
     }

   return changed;
  }

//+------------------------------------------------------------------+
//| Push the message                                                  |
//+------------------------------------------------------------------+
long PushToSubscriber(const string symbl,const string message,long reply_to_id=0)
  {
   if(message == "")
      return 0;

   // Emergency stop gate before sending anything
   if(!g_es.CanSendTelegramMessage())
      return 0;

   if(MobileNotification)
      SendNotification(message);

   if(EmailNotification)
      SendMail("Order Notification", message);

   long msg_id = 0;

   if(AlertonTelegram)
     {
      if(SendScreenShot)
     {
         // If screenshots are enabled, send them with caption (message)
         if(StringFind(symbl, "null") != -1)
            return 0;
         sendSnapShots(symbl, ScreenShotTimeFrame, message);
         msg_id = bot.LastMessageId();
      }
      else
      {
         if(reply_to_id > 0)
            msg_id = SendMessageWithDebug(InpChannelName, message, reply_to_id);
         else
            msg_id = SendMessageWithDebug(InpChannelName, message);
      }
   }

   return msg_id;

  }

//+------------------------------------------------------------------+
//| Get the symbol allowd on trading                                 |
//+------------------------------------------------------------------+
bool GetOrderSymbolAllowed(const string symbol)
  {
   bool result = true;

   if(symbolallow_size == 0)
      return result;

// Change result as FALSE when allow list is not empty
   result = false;

   int symbolindex = 0;

   for(symbolindex=0; symbolindex<symbolallow_size; symbolindex++)
     {
      if(local_symbolallow[symbolindex] == "")
         continue;

      if(symbol == local_symbolallow[symbolindex])
        {
         result = true;

         break;
        }
     }

   return result;
  }

//+------------------------------------------------------------------+
//| Find a order by ticket id                                        |
//+------------------------------------------------------------------+
bool FindOrderInPrevPool(const int order_ticketid)
  {
   int orderfound = 0;
   int orderindex = 0;

   if(prev_ordersize == 0)
      return false;

   for(orderindex=0; orderindex<prev_ordersize; orderindex++)
     {
      if(order_ticketid == orderids[orderindex])
         orderfound ++;
     }

   return (orderfound > 0) ? true : false;
  }
  
  int sendSnapShots(string thesymbol, ENUM_TIMEFRAMES _period, string message){
   
     int result=0;
           long chart_id=ChartOpen(thesymbol,_period);
     // if(chart_id==0)
     //    return(ERR_CHART_NOT_FOUND);

      ChartSetInteger(ChartID(),CHART_BRING_TO_TOP,true);

      //--- updates chart
      int wait=60;
      while(--wait>0)
        {
         if(SeriesInfoInteger(thesymbol,_period,SERIES_SYNCHRONIZED))
            break;
         Sleep(500);
        }

      if(_template!= ""){
         ChartApplyTemplate(chart_id,_template);
        //    PrintError(_LastError,InpLanguage);
          //  ChartApplyTemplate(chart_id,_template);
         }
      ChartRedraw(chart_id);
      Sleep(500);

      ChartSetInteger(chart_id,CHART_SHOW_GRID,false);

      ChartSetInteger(chart_id,CHART_SHOW_PERIOD_SEP,false);

      string filename=StringFormat("%s%d.gif",thesymbol,_period);

      if(FileIsExist(filename))
         FileDelete(filename);
      ChartRedraw(chart_id);

      Sleep(100);

      if(ChartScreenShot(chart_id,filename,800,600,ALIGN_RIGHT))
        {
         Sleep(100);

         //--- waitng 30 sec for save screenshot 
         wait=30;
         while(!FileIsExist(filename) && --wait>0)
            Sleep(500);

         //---
         if(FileIsExist(filename))
           {
            string screen_id;
           
            result=bot.SendPhoto(screen_id,InpChannelName,filename,thesymbol + message);
            
       
           }
        

        } 

      ChartClose(chart_id);    
   
   
   
  return result; 
   }
  
  


//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string TypeMnem(int type)
  {
   switch(type)
     {
      case OP_BUY:
         return("buy");
      case OP_SELL:
         return("sell");
      case OP_BUYLIMIT:
         return("buy limit");
      case OP_SELLLIMIT:
         return("sell limit");
      case OP_BUYSTOP:
         return("buy stop");
      case OP_SELLSTOP:
         return("sell stop");
      default:
         return("???");
     }
  }
