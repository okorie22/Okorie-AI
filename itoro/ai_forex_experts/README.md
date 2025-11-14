# MT5-MT4-Telegram-API-Bot
MT5-MT4-Telegram-API-Bot is a Bot that communicates with Telegram, and copy all trades from your MT4 or MT5 terminal to Telegram Groups or channel - It support MQL4/MQL5 language.
it delivers Trade Signal Alert From MT4 and MT5 Terminal to Telegram, EMail, or the notification terminal


# Cross-VPS Streaming

When running the MT5/MT4 bridge on a dedicated VPS, configure shared transports so the signals reach the central commerce system:

- Set `CORE_FOREX_DB_URL` (or fallback to `CORE_DB_URL`) so the telemetry bridge can persist rows to the unified database.
- Optionally set `CORE_EVENT_BUS_BACKEND=webhook` along with `CORE_EVENT_WEBHOOK_URL` / `CORE_EVENT_WEBHOOK_SECRET` to push signals directly to the aggregator endpoint (`AGG_SIGNAL_ENDPOINT`).
- Optionally set `CORE_EVENT_BUS_BACKEND=redis` with `CORE_REDIS_URL` to publish via Redis Streams.

Refer to `docs/CROSS_VPS_DEPLOYMENT.md` for detailed topology guidance.

# SignalMapperRiskManager EA (MQL5)

An MT5 Expert Advisor located at `Experts/SignalMapperRiskManager.mq5` which:
- Maps provider symbols to your broker symbols (handles suffixes and common aliases)
- Executes market and pending orders read from a CSV file (`MQL5/Files/signals.csv` by default)
- Adds configurable SL/TP if the signal does not provide them
- Supports fixed lots or risk-percent lot sizing

Inputs overview:
- Mapping mode: exact, first-6-chars, metals aliases, manual list, or auto-fallback
- SL/TP modes: FixedPips, ATR, PercentBalance, Money, R-multiple
- Lot sizing: Fixed or RiskPercent
- CSV filename and timer frequency

CSV format (first row is header):
```
id,symbol,side,type,price,sl,tp,comment
1,XAUUSD.SV,BUY,MARKET,0,0,0,Example
```
Fields:
- id: unique string per signal
- symbol: provider symbol (EA maps to broker symbol)
- side: BUY or SELL
- type: MARKET, LIMIT, or STOP
- price: pending entry price (0 for market)
- sl/tp: prices (0 means let EA compute)
- comment: optional text

Usage:
1) Copy `Experts/SignalMapperRiskManager.mq5` to your terminal’s `MQL5/Experts` and compile.
2) Put `signals.csv` into `MQL5/Files` folder of the same terminal.
3) Attach EA to any chart, configure inputs (risk, SL/TP modes, manual mappings).
4) EA reads `signals.csv` on a timer and places orders with mapped symbols and SL/TP.

# TODO
* Search for a bot on telegram with name "@BotFather". We will find it through the search engine. After adding it to the list of contacts,
we will start communicating with it using the /start command. As a response it will send you a list of all available commands, As shown in the image below
![pic1](https://user-images.githubusercontent.com/32399318/56162967-1fe7ed00-5fc5-11e9-9555-192c33b34d7f.jpg)


* With the /newbot command we begin the registration of a new bot. We need to come up with two names. The first one is a name of a bot that 
can be set in your native language. The second one is a username of a bot in Latin that ends with a “bot” prefix. As a result, we obtain 
a token or API Key – the access key for operating with a bot through API as shown below

![pic2](https://user-images.githubusercontent.com/32399318/56163370-0d21e800-5fc6-11e9-8481-69861daa4a1e.jpg)

## Operation mode for bots

With regard to bots, you can let them join groups by using the /setjoingroups command. If a bot is added to a group, then by using the /setprivacy command you can set the option to either receive all messages, or only those that start with a sign of the symbol team “/”. 

![pic4](https://user-images.githubusercontent.com/32399318/56163746-05af0e80-5fc7-11e9-801c-362d94e36a4d.jpg)

The other mode focuses on operation on a channel. Telegram channels are accounts for transmitting messages for a wide audience that support an unlimited number of subscribers. The important feature of channels is that users can't leave comments and likes on the news feed (one-way connection). Only channel administrators can create messages there 

![pic5__2](https://user-images.githubusercontent.com/32399318/56163931-8241ed00-5fc7-11e9-99e4-96a879ae0b9a.jpg)


* Export and copy all files from include to the MT4/MT5 include folder, input the api key from the bot to the Expert Advisor's token, add the bot as an administrator of your signal channel or Group, any event that happens on your trade terminal will be notify to instantly on your channel


![mt4-telegram-signal-provider-screen-8054](https://user-images.githubusercontent.com/32399318/56166011-7147aa80-5fcc-11e9-9444-1bcaa574219e.jpg)

![test1](https://user-images.githubusercontent.com/32399318/56165638-63ddf080-5fcb-11e9-9b88-5e9fb94821b6.jpg)










