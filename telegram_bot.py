"""
telegram_bot.py — All Telegram messaging & command handling
------------------------------------------------------------
Commands:
  /start   — welcome message
  /status  — is the bot running + current price
  /pnl     — today's PnL summary
  /stats   — full performance stats
  /trades  — last 5 closed trades
  /open    — current open position
  /stop    — pause trading
  /resume  — resume trading
  /help    — command list
"""

import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# Shared state injected by main.py
_traders: dict    = {}
_prices:  dict    = {}
_bot_active = True
_start_time = datetime.now(timezone.utc)


def init(traders: dict, config):
    global _traders, _config
    _traders = traders
    _config  = config


def set_price(symbol: str, price: float):
    _prices[symbol] = price


def is_active() -> bool:
    return _bot_active


# ── Formatters ────────────────────────────────────────────────────────────────

def fmt_trade_opened(trade, current_price: float) -> str:
    return (
        f"🚀 *TRADE OPENED — Paper*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Pair       : `{trade.symbol}`\n"
        f"💵 Entry      : `${trade.entry_price:,.2f}`\n"
        f"🔴 Stop Loss  : `${trade.stop_loss:,.2f}`\n"
        f"🟢 Take Profit: `${trade.take_profit:,.2f}`\n"
        f"📦 Qty        : `{trade.quantity:.6f} ETH`\n"
        f"🕐 Time       : `{trade.entry_time}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_RSI + EMA Crossover signal_"
    )


def fmt_trade_closed(trade) -> str:
    emoji  = "🟢 PROFIT" if trade.pnl > 0 else "🔴 LOSS"
    sign   = "+" if trade.pnl > 0 else ""
    reason_emoji = {
        "SIGNAL":      "📉 Signal reversal",
        "STOP_LOSS":   "🛑 Stop loss hit",
        "TAKE_PROFIT": "🎯 Take profit hit",
    }.get(trade.exit_reason, trade.exit_reason)

    return (
        f"{emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Pair       : `{trade.symbol}`\n"
        f"💵 Entry      : `${trade.entry_price:,.2f}`\n"
        f"💵 Exit       : `${trade.exit_price:,.2f}`\n"
        f"💰 PnL        : `{sign}${trade.pnl:.2f} ({sign}{trade.pnl_pct:.2f}%)`\n"
        f"📋 Reason     : {reason_emoji}\n"
        f"🕐 Closed     : `{trade.exit_time}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


def fmt_stats(stats: dict) -> str:
    pf = stats['profit_factor']
    pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"
    pnl_sign = "+" if stats['total_pnl'] >= 0 else ""
    bal_change = stats['balance'] - stats['starting_balance']
    bal_sign   = "+" if bal_change >= 0 else ""

    return (
        f"📊 *PERFORMANCE STATS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💼 Balance     : `${stats['balance']:,.2f}`\n"
        f"📈 Total PnL   : `{pnl_sign}${stats['total_pnl']:.2f} ({bal_sign}{stats['total_pnl_pct']:.2f}%)`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Trades      : `{stats['total_trades']}`\n"
        f"✅ Wins        : `{stats.get('wins', 0)}`\n"
        f"❌ Losses      : `{stats.get('losses', 0)}`\n"
        f"📉 Win Rate    : `{stats['win_rate']}%`\n"
        f"⚡ Profit Factor: `{pf_str}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Best Trade  : `+${stats.get('best_trade', 0):.2f}`\n"
        f"💔 Worst Trade : `${stats.get('worst_trade', 0):.2f}`\n"
        f"🎯 Avg Win     : `+${stats['avg_win']:.2f}`\n"
        f"📉 Avg Loss    : `-${stats['avg_loss']:.2f}`"
    )


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *ETH/USDT Trading Bot — Online*\n\n"
        "I'm running 24/7, scanning for RSI + EMA signals on the 1h chart.\n\n"
        "*Commands:*\n"
        "/status — bot status & current price\n"
        "/pnl — profit & loss summary\n"
        "/stats — full performance breakdown\n"
        "/trades — last 5 closed trades\n"
        "/open — current open position\n"
        "/stop — pause trading\n"
        "/resume — resume trading\n"
        "/help — show this message",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    status  = "🟢 ACTIVE" if _bot_active else "🔴 PAUSED"
    uptime  = datetime.now(timezone.utc) - _start_time
    hours   = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)

    msg = (
        f"🤖 *BOT STATUS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Status  : {status}\n"
        f"Uptime  : `{hours}h {minutes}m`\n"
        f"TF      : `{_config.TIMEFRAME}` | Mode: `📄 Paper`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    for symbol, trader in _traders.items():
        price   = _prices.get(symbol, 0)
        open_tr = trader.open_trade
        if open_tr:
            unreal = trader.unrealized_pnl(price)
            sign   = "+" if unreal >= 0 else ""
            msg   += f"`{symbol}` 📌 Open @ `${open_tr.entry_price:,.2f}` | Unreal: `{sign}${unreal:.2f}`\n"
        else:
            msg += f"`{symbol}` `${price:,.2f}` — No position\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_pnl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _traders:
        await update.message.reply_text("⚠️ Trader not initialized.")
        return
    msg = "💰 *PnL SUMMARY — ALL PAIRS*\n━━━━━━━━━━━━━━━━━━━━━━\n"
    total_pnl = 0
    for symbol, trader in _traders.items():
        stats = trader.get_stats()
        sign  = "+" if stats["total_pnl"] >= 0 else ""
        msg  += f"`{symbol}` {stats['total_trades']} trades | WR: `{stats['win_rate']}%` | `{sign}${stats['total_pnl']:.2f}`\n"
        total_pnl += stats["total_pnl"]
    sign = "+" if total_pnl >= 0 else ""
    msg += f"━━━━━━━━━━━━━━━━━━━━━━\n*Total PnL: `{sign}${total_pnl:.2f}`*"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _traders:
        await update.message.reply_text("⚠️ Trader not initialized.")
        return
    for symbol, trader in _traders.items():
        stats = trader.get_stats()
        if stats["total_trades"] == 0:
            await update.message.reply_text(f"`{symbol}` — No closed trades yet.", parse_mode=ParseMode.MARKDOWN)
            continue
        await update.message.reply_text(
            f"*{symbol}*\n" + fmt_stats(stats), parse_mode=ParseMode.MARKDOWN
        )


async def cmd_trades(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _traders:
        await update.message.reply_text("⚠️ Trader not initialized.")
        return
    msg = "📋 *RECENT TRADES — ALL PAIRS*\n━━━━━━━━━━━━━━━━━━━━━━\n"
    any_trades = False
    for symbol, trader in _traders.items():
        recent = trader.get_recent_trades(3)
        if recent:
            any_trades = True
            msg += f"*{symbol}*\n"
            for t in recent:
                emoji = "🟢" if t.pnl > 0 else "🔴"
                sign  = "+" if t.pnl > 0 else ""
                msg  += f"  {emoji} `${t.entry_price:,.0f}` → `${t.exit_price:,.0f}` | `{sign}${t.pnl:.2f}`\n"
    if not any_trades:
        await update.message.reply_text("📭 No closed trades yet.")
        return
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _traders:
        await update.message.reply_text("⚠️ Trader not initialized.")
        return
    open_positions = [(s, t) for s, t in _traders.items() if t.open_trade]
    if not open_positions:
        await update.message.reply_text("📭 No open positions right now.")
        return
    msg = "📌 *OPEN POSITIONS*\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for symbol, trader in open_positions:
        trade  = trader.open_trade
        price  = _prices.get(symbol, trade.entry_price)
        unreal = trader.unrealized_pnl(price)
        sign   = "+" if unreal >= 0 else ""
        msg   += (
            f"*{symbol}*\n"
            f"  Entry: `${trade.entry_price:,.2f}` | Now: `${price:,.2f}`\n"
            f"  Unreal: `{sign}${unreal:.2f}` | SL: `${trade.stop_loss:,.2f}` | TP: `${trade.take_profit:,.2f}`\n"
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _bot_active
    _bot_active = False
    await update.message.reply_text(
        "🔴 *Trading PAUSED*\n"
        "Bot will stop opening new trades.\n"
        "Use /resume to restart.",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _bot_active
    _bot_active = True
    await update.message.reply_text(
        "🟢 *Trading RESUMED*\n"
        "Bot is back to scanning for signals!",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, ctx)


# ── App builder ───────────────────────────────────────────────────────────────

def build_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("pnl",    cmd_pnl))
    app.add_handler(CommandHandler("stats",  cmd_stats))
    app.add_handler(CommandHandler("trades", cmd_trades))
    app.add_handler(CommandHandler("open",   cmd_open))
    app.add_handler(CommandHandler("stop",   cmd_stop))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("help",   cmd_help))
    return app


async def send_message(bot: Bot, chat_id: str, text: str):
    """Utility — send a message from outside a command handler."""
    try:
        await bot.send_message(chat_id=chat_id, text=text,
                               parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
