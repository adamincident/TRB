# TRB

# 🤖 ETH/USDT Trading Bot

RSI + EMA Crossover strategy with ATR-based risk management.
Paper trades ETH/USDT on Binance, sends all alerts to Telegram.

-----

## 📁 Files

|File             |Purpose                               |
|-----------------|--------------------------------------|
|`config.py`      |All settings (tokens, strategy params)|
|`strategy.py`    |RSI + EMA signal logic                |
|`paper_trader.py`|Virtual trading engine + PnL tracking |
|`telegram_bot.py`|Telegram commands & alert formatting  |
|`main.py`        |Entry point — runs everything         |
|`backtest.py`    |Historical strategy test              |

-----

## ⚡ Quick Setup (5 steps)

### 1. Get your Telegram Chat ID

1. Open Telegram, search `@userinfobot`
1. Send it `/start`
1. It replies with your numeric ID — copy it

### 2. Fill in config.py

```python
TELEGRAM_TOKEN   = "your_token_here"     # from BotFather
TELEGRAM_CHAT_ID = "your_chat_id_here"   # from @userinfobot
```

### 3. Run the backtest locally first

```bash
pip install -r requirements.txt
python backtest.py
```

Look for:

- Win rate > 50%
- Profit factor > 1.5

### 4. Paper trade locally (optional)

```bash
python main.py
```

### 5. Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project
railway init

# Deploy
railway up
```

Then go to Railway dashboard → add these environment variables:

```
TELEGRAM_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

And update `config.py` to read from env (optional for extra security):

```python
import os
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
```

-----

## 📲 Telegram Commands

|Command  |What it does              |
|---------|--------------------------|
|`/status`|Bot status + current price|
|`/pnl`   |Quick profit/loss         |
|`/stats` |Full performance stats    |
|`/trades`|Last 5 closed trades      |
|`/open`  |Current open position     |
|`/stop`  |Pause trading             |
|`/resume`|Resume trading            |
|`/help`  |Command list              |

-----

## 📊 Strategy Logic

**BUY when:**

- RSI crosses above 35 (recovering from oversold)
- Fast EMA (9) is above Slow EMA (21) → uptrend confirmed

**SELL when:**

- RSI drops below 65 (overbought reversal) OR
- Fast EMA crosses below Slow EMA → trend reversal

**Risk Management:**

- Stop Loss: 1.5× ATR below entry (adapts to volatility)
- Take Profit: 3.0× ATR above entry (2:1 reward-to-risk)
- Risk per trade: 2% of balance

-----

## 📈 Paper Trading → Real Trading

After 1-2 weeks of paper trading:

1. Check `/stats` — aim for win rate > 50%, profit factor > 1.5
1. Create a Binance account
1. Generate API keys (enable spot trading only, NO withdrawals)
1. Add to config.py:

```python
BINANCE_API_KEY    = "your_api_key"
BINANCE_API_SECRET = "your_api_secret"
LIVE_TRADING       = True   # flip this when ready
```

1. Start small — $50-100 — let it run, scale up gradually

-----

## ⚠️ Disclaimer

This is for educational purposes. Crypto trading involves real financial risk.
Always start with paper trading, validate your results, and never trade more than you can afford to lose.
