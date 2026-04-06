# ============================================================
#  CONFIG — edit these before deploying
# ============================================================

TELEGRAM_TOKEN   = "8371910339:AAFPUk7VYYrXhziu4iyLr0GxC5IvJ21Vn5c"
TELEGRAM_CHAT_ID = "7600140929"   # send /start to your bot, then message @userinfobot

# Trading pairs & timeframe — all scanned every cycle
SYMBOLS   = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
SYMBOL    = "BTC/USDT"   # kept for backtest.py single-pair runs
TIMEFRAME = "1h"

# Strategy parameters
RSI_PERIOD      = 14
RSI_OVERSOLD    = 35      # buy signal threshold
RSI_OVERBOUGHT  = 65      # sell signal threshold
EMA_FAST        = 9
EMA_SLOW        = 21
ATR_PERIOD      = 14

# Risk management
PAPER_BALANCE        = 1000.0   # starting USDT for paper trading
RISK_PER_TRADE_PCT   = 0.02     # 2% of balance per trade
STOP_LOSS_ATR_MULT   = 1.5      # stop loss = 1.5x ATR
TAKE_PROFIT_ATR_MULT = 3.0      # take profit = 3x ATR  (2:1 RR minimum)
MAX_OPEN_TRADES      = 1        # one trade at a time to stay safe

# Binance (public endpoints — no API key needed for paper trading)
EXCHANGE_ID = "binance"

# How often the bot checks for signals (seconds)
POLL_INTERVAL = 60   # every 60s on 1h chart is fine
