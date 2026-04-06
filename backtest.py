"""
backtest.py — Run historical simulation of the strategy
--------------------------------------------------------
Usage:
    python backtest.py

Fetches the last 500 candles of ETH/USDT 1h from Binance,
runs the strategy, and prints a full performance report.
"""

import ccxt
import pandas as pd
import config
from strategy import generate_signals
from paper_trader import TRADE_FEE


def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    exchange = ccxt.binance({"enableRateLimit": True})
    raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df


def run_backtest():
    print(f"\n{'='*55}")
    print(f"  BACKTEST — {config.SYMBOL} {config.TIMEFRAME}")
    print(f"{'='*55}\n")

    print("📡 Fetching historical data from Binance...")
    df = fetch_ohlcv(config.SYMBOL, config.TIMEFRAME, limit=500)
    df = generate_signals(df, config)
    print(f"✅ Got {len(df)} candles ({df.index[0].date()} → {df.index[-1].date()})\n")

    balance      = config.PAPER_BALANCE
    start_bal    = balance
    open_trade   = None
    trades       = []

    for i in range(len(df)):
        row   = df.iloc[i]
        price = row["close"]

        # Check SL/TP first
        if open_trade:
            reason = None
            if price <= open_trade["sl"]:
                reason = "STOP_LOSS"
            elif price >= open_trade["tp"]:
                reason = "TAKE_PROFIT"

            if reason:
                proceeds   = open_trade["qty"] * price * (1 - TRADE_FEE)
                cost_basis = open_trade["qty"] * open_trade["entry"] * (1 + TRADE_FEE)
                pnl        = proceeds - cost_basis
                balance   += proceeds
                trades.append({
                    "entry":  open_trade["entry"],
                    "exit":   price,
                    "pnl":    round(pnl, 4),
                    "reason": reason,
                    "entry_time": open_trade["entry_time"],
                    "exit_time":  row.name,
                })
                open_trade = None
                continue

        # Check for new signal
        signal = row["signal"]

        if signal == 1 and open_trade is None:
            risk_amount  = balance * config.RISK_PER_TRADE_PCT
            risk_per_unit = price - row["stop_loss"]
            if risk_per_unit <= 0:
                continue
            qty  = risk_amount / risk_per_unit
            cost = qty * price * (1 + TRADE_FEE)
            if cost > balance:
                qty  = (balance * 0.95) / (price * (1 + TRADE_FEE))
                cost = qty * price * (1 + TRADE_FEE)
            balance -= cost
            open_trade = {
                "entry":      price,
                "qty":        qty,
                "sl":         row["stop_loss"],
                "tp":         row["take_profit"],
                "entry_time": row.name,
            }

        elif signal == -1 and open_trade:
            proceeds   = open_trade["qty"] * price * (1 - TRADE_FEE)
            cost_basis = open_trade["qty"] * open_trade["entry"] * (1 + TRADE_FEE)
            pnl        = proceeds - cost_basis
            balance   += proceeds
            trades.append({
                "entry":  open_trade["entry"],
                "exit":   price,
                "pnl":    round(pnl, 4),
                "reason": "SIGNAL",
                "entry_time": open_trade["entry_time"],
                "exit_time":  row.name,
            })
            open_trade = None

    # Close any open trade at last price
    if open_trade:
        last_price = df.iloc[-1]["close"]
        proceeds   = open_trade["qty"] * last_price * (1 - TRADE_FEE)
        cost_basis = open_trade["qty"] * open_trade["entry"] * (1 + TRADE_FEE)
        pnl        = proceeds - cost_basis
        balance   += proceeds
        trades.append({
            "entry":  open_trade["entry"],
            "exit":   last_price,
            "pnl":    round(pnl, 4),
            "reason": "END_OF_DATA",
            "entry_time": open_trade["entry_time"],
            "exit_time":  df.index[-1],
        })

    # ── Report ───────────────────────────────────────────────────────────────
    if not trades:
        print("⚠️  No trades generated. Try adjusting RSI thresholds in config.py")
        return

    wins   = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total_profit = sum(t["pnl"] for t in wins)
    total_loss   = abs(sum(t["pnl"] for t in losses))

    print("📊 TRADE LOG")
    print("-" * 55)
    for t in trades:
        emoji = "🟢" if t["pnl"] > 0 else "🔴"
        sign  = "+" if t["pnl"] > 0 else ""
        print(f"  {emoji} Entry: ${t['entry']:,.2f} → Exit: ${t['exit']:,.2f}  "
              f"PnL: {sign}${t['pnl']:.2f}  [{t['reason']}]")

    print(f"\n{'='*55}")
    print(f"  PERFORMANCE SUMMARY")
    print(f"{'='*55}")
    print(f"  Starting balance : ${start_bal:,.2f}")
    print(f"  Final balance    : ${balance:,.2f}")
    print(f"  Net PnL          : ${balance - start_bal:+,.2f}  "
          f"({((balance - start_bal) / start_bal * 100):+.2f}%)")
    print(f"  Total trades     : {len(trades)}")
    print(f"  Wins / Losses    : {len(wins)} / {len(losses)}")
    print(f"  Win rate         : {len(wins)/len(trades)*100:.1f}%")
    print(f"  Avg win          : ${total_profit/len(wins):.2f}" if wins else "  Avg win  : N/A")
    print(f"  Avg loss         : ${total_loss/len(losses):.2f}" if losses else "  Avg loss : N/A")
    pf = total_profit / total_loss if total_loss > 0 else float("inf")
    print(f"  Profit factor    : {pf:.2f}  (>1.5 is solid)")
    best  = max(trades, key=lambda t: t["pnl"])
    worst = min(trades, key=lambda t: t["pnl"])
    print(f"  Best trade       : +${best['pnl']:.2f}")
    print(f"  Worst trade      : ${worst['pnl']:.2f}")
    print(f"{'='*55}\n")

    if pf >= 1.5 and len(wins)/len(trades) >= 0.5:
        print("✅ Strategy looks solid! Ready for paper trading.")
    else:
        print("⚠️  Strategy needs tuning. Tweak RSI thresholds or ATR multipliers in config.py")


if __name__ == "__main__":
    run_backtest()
