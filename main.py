"""
main.py — Bot entry point
--------------------------
Runs two async tasks concurrently:
  1. Trading loop  — fetches candles, checks signals, manages positions
  2. Telegram app  — listens for commands from your phone
"""

import asyncio
import logging
import sys
import ccxt.async_support as ccxt_async
import pandas as pd
from datetime import datetime, timezone

import config
import telegram_bot as tg
from strategy import generate_signals
from paper_trader import PaperTrader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)


async def fetch_ohlcv(exchange, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    raw = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df  = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df


async def scan_pair(exchange, symbol: str, traders: dict, bot):
    """Scan a single pair for signals and manage its position."""
    try:
        df = await fetch_ohlcv(exchange, symbol, config.TIMEFRAME, limit=100)
        df = generate_signals(df, config)

        last   = df.iloc[-1]
        price  = float(last["close"])
        signal = int(last["signal"])
        sl     = float(last["stop_loss"])
        tp     = float(last["take_profit"])
        rsi    = float(last["rsi"])

        trader = traders[symbol]
        tg.set_price(symbol, price)

        log.info(f"{symbol} ${price:,.2f} | RSI={rsi:.1f} | Signal={signal}")

        # ── Check SL/TP ───────────────────────────────────────────────────
        closed_trade = trader.check_exit_conditions(price)
        if closed_trade:
            log.info(f"[{symbol}] Closed via {closed_trade.exit_reason}: PnL ${closed_trade.pnl:+.2f}")
            await tg.send_message(bot, config.TELEGRAM_CHAT_ID,
                                  tg.fmt_trade_closed(closed_trade))

        # ── Buy signal ────────────────────────────────────────────────────
        if signal == 1 and tg.is_active() and not trader.open_trade:
            new_trade = trader.open_position(
                price       = price,
                stop_loss   = sl,
                take_profit = tp,
                risk_pct    = config.RISK_PER_TRADE_PCT,
            )
            if new_trade:
                log.info(f"[{symbol}] BUY — Entry ${price:,.2f} SL ${sl:,.2f} TP ${tp:,.2f}")
                await tg.send_message(bot, config.TELEGRAM_CHAT_ID,
                                      tg.fmt_trade_opened(new_trade, price))

        # ── Sell signal ───────────────────────────────────────────────────
        elif signal == -1 and trader.open_trade:
            closed = trader.close_position(price, reason="SIGNAL")
            if closed:
                log.info(f"[{symbol}] SELL — Exit ${price:,.2f} PnL ${closed.pnl:+.2f}")
                await tg.send_message(bot, config.TELEGRAM_CHAT_ID,
                                      tg.fmt_trade_closed(closed))

    except Exception as e:
        log.error(f"[{symbol}] Scan error: {e}", exc_info=True)


async def trading_loop(bot, traders: dict):
    """Core loop: scan all pairs every POLL_INTERVAL seconds."""
    exchange = ccxt_async.binance({"enableRateLimit": True})
    log.info(f"🚀 Trading loop started — {list(traders.keys())} {config.TIMEFRAME}")

    try:
        while True:
            tasks = [scan_pair(exchange, symbol, traders, bot)
                     for symbol in config.SYMBOLS]
            await asyncio.gather(*tasks)
            await asyncio.sleep(config.POLL_INTERVAL)
    finally:
        await exchange.close()


async def daily_summary(bot, traders: dict):
    """Send a performance summary every 24 hours."""
    while True:
        await asyncio.sleep(86400)
        msg = "📅 *DAILY SUMMARY — ALL PAIRS*\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for symbol, trader in traders.items():
            stats = trader.get_stats()
            sign  = "+" if stats["total_pnl"] >= 0 else ""
            msg  += (f"`{symbol}` — {stats['total_trades']} trades | "
                     f"WR: {stats['win_rate']}% | "
                     f"PnL: {sign}${stats['total_pnl']:.2f}\n")
        await tg.send_message(bot, config.TELEGRAM_CHAT_ID, msg)


async def main():
    log.info("=" * 55)
    log.info("  MULTI-PAIR TRADING BOT — STARTING")
    log.info("=" * 55)

    if config.TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        log.error("❌ Set your TELEGRAM_TOKEN in config.py!")
        sys.exit(1)
    if config.TELEGRAM_CHAT_ID == "YOUR_CHAT_ID":
        log.error("❌ Set your TELEGRAM_CHAT_ID in config.py!")
        sys.exit(1)

    # One paper trader per symbol
    traders = {
        symbol: PaperTrader(
            starting_balance = config.PAPER_BALANCE / len(config.SYMBOLS),
            symbol           = symbol,
        )
        for symbol in config.SYMBOLS
    }

    log.info(f"💼 {len(traders)} pairs | ${config.PAPER_BALANCE / len(config.SYMBOLS):,.2f} USDT each")

    app = tg.build_app(config.TELEGRAM_TOKEN)
    tg.init(traders, config)

    bot = app.bot

    pairs_str = " | ".join(f"`{s}`" for s in config.SYMBOLS)
    bal_each  = config.PAPER_BALANCE / len(config.SYMBOLS)

    await bot.send_message(
        chat_id    = config.TELEGRAM_CHAT_ID,
        text       = (
            f"🤖 *Multi-Pair Bot Online!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Pairs   : {pairs_str}\n"
            f"TF      : `{config.TIMEFRAME}`\n"
            f"Balance : `${bal_each:,.2f} USDT per pair`\n"
            f"Mode    : `📄 Paper Trading`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Strategy: RSI({config.RSI_PERIOD}) + EMA({config.EMA_FAST}/{config.EMA_SLOW})\n"
            f"Risk/trade: {config.RISK_PER_TRADE_PCT*100:.0f}% | "
            f"SL: {config.STOP_LOSS_ATR_MULT}x ATR | TP: {config.TAKE_PROFIT_ATR_MULT}x ATR\n\n"
            f"Type /help for commands 🚀"
        ),
        parse_mode = "Markdown"
    )

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

        log.info("✅ Bot is live! Check your Telegram.")

        await asyncio.gather(
            trading_loop(bot, traders),
            daily_summary(bot, traders),
        )

        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
