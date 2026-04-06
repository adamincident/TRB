"""
paper_trader.py — Simulated trading engine
------------------------------------------
Tracks virtual balance, open positions, and full trade history.
All PnL calculations are realistic (includes a simulated 0.1% fee).
"""

import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

TRADE_FEE = 0.001   # 0.1% per side (Binance standard)
DATA_FILE  = "paper_trades.json"


@dataclass
class Trade:
    id:           int
    symbol:       str
    side:         str          # "BUY" or "SELL"
    entry_price:  float
    quantity:     float
    stop_loss:    float
    take_profit:  float
    entry_time:   str
    exit_price:   Optional[float] = None
    exit_time:    Optional[str]   = None
    pnl:          Optional[float] = None
    pnl_pct:      Optional[float] = None
    exit_reason:  Optional[str]   = None   # "SIGNAL" | "STOP_LOSS" | "TAKE_PROFIT"
    open:         bool = True


class PaperTrader:

    def __init__(self, starting_balance: float, symbol: str):
        self.symbol           = symbol
        self.starting_balance = starting_balance
        self.balance          = starting_balance
        self.open_trade: Optional[Trade] = None
        self.trade_history: list[Trade]  = []
        self.trade_counter = 0
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE) as f:
                    data = json.load(f)
                self.balance       = data.get("balance", self.starting_balance)
                self.trade_counter = data.get("trade_counter", 0)
                history = data.get("trade_history", [])
                self.trade_history = [Trade(**t) for t in history]
                open_trade = data.get("open_trade")
                if open_trade:
                    self.open_trade = Trade(**open_trade)
            except Exception:
                pass

    def _save(self):
        data = {
            "balance":       self.balance,
            "trade_counter": self.trade_counter,
            "trade_history": [asdict(t) for t in self.trade_history],
            "open_trade":    asdict(self.open_trade) if self.open_trade else None,
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)

    # ── Core trade logic ──────────────────────────────────────────────────────

    def open_position(self, price: float, stop_loss: float,
                      take_profit: float, risk_pct: float) -> Optional[Trade]:
        if self.open_trade:
            return None   # already in a trade

        risk_amount = self.balance * risk_pct
        risk_per_unit = price - stop_loss
        if risk_per_unit <= 0:
            return None

        quantity = risk_amount / risk_per_unit
        cost     = quantity * price * (1 + TRADE_FEE)

        if cost > self.balance:
            quantity = (self.balance * 0.95) / (price * (1 + TRADE_FEE))
            cost     = quantity * price * (1 + TRADE_FEE)

        self.balance -= cost
        self.trade_counter += 1

        trade = Trade(
            id          = self.trade_counter,
            symbol      = self.symbol,
            side        = "BUY",
            entry_price = price,
            quantity    = quantity,
            stop_loss   = stop_loss,
            take_profit = take_profit,
            entry_time  = _now(),
        )
        self.open_trade = trade
        self._save()
        return trade

    def check_exit_conditions(self, current_price: float) -> Optional[Trade]:
        """Check SL/TP hit on every candle close — call this before signal check."""
        if not self.open_trade:
            return None

        reason = None
        if current_price <= self.open_trade.stop_loss:
            reason = "STOP_LOSS"
        elif current_price >= self.open_trade.take_profit:
            reason = "TAKE_PROFIT"

        if reason:
            return self.close_position(current_price, reason)
        return None

    def close_position(self, price: float, reason: str = "SIGNAL") -> Optional[Trade]:
        if not self.open_trade:
            return None

        trade = self.open_trade
        proceeds  = trade.quantity * price * (1 - TRADE_FEE)
        cost_basis = trade.quantity * trade.entry_price * (1 + TRADE_FEE)

        trade.exit_price  = price
        trade.exit_time   = _now()
        trade.pnl         = round(proceeds - cost_basis, 4)
        trade.pnl_pct     = round((trade.pnl / cost_basis) * 100, 2)
        trade.exit_reason = reason
        trade.open        = False

        self.balance += proceeds
        self.trade_history.append(trade)
        self.open_trade = None
        self._save()
        return trade

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        closed = self.trade_history
        if not closed:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "total_pnl_pct": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "balance": round(self.balance, 2),
                "starting_balance": self.starting_balance,
            }

        wins  = [t for t in closed if t.pnl and t.pnl > 0]
        loses = [t for t in closed if t.pnl and t.pnl <= 0]

        total_profit = sum(t.pnl for t in wins)  if wins  else 0
        total_loss   = abs(sum(t.pnl for t in loses)) if loses else 0

        return {
            "total_trades":    len(closed),
            "wins":            len(wins),
            "losses":          len(loses),
            "win_rate":        round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "total_pnl":       round(sum(t.pnl for t in closed), 2),
            "total_pnl_pct":   round(((self.balance - self.starting_balance) / self.starting_balance) * 100, 2),
            "avg_win":         round(total_profit / len(wins), 2)  if wins  else 0,
            "avg_loss":        round(total_loss   / len(loses), 2) if loses else 0,
            "profit_factor":   round(total_profit / total_loss, 2) if total_loss > 0 else float("inf"),
            "balance":         round(self.balance, 2),
            "starting_balance": self.starting_balance,
            "best_trade":      max((t.pnl for t in closed), default=0),
            "worst_trade":     min((t.pnl for t in closed), default=0),
        }

    def get_recent_trades(self, n: int = 5) -> list[Trade]:
        return list(reversed(self.trade_history[-n:]))

    def unrealized_pnl(self, current_price: float) -> float:
        if not self.open_trade:
            return 0.0
        current_value = self.open_trade.quantity * current_price * (1 - TRADE_FEE)
        cost_basis    = self.open_trade.quantity * self.open_trade.entry_price * (1 + TRADE_FEE)
        return round(current_value - cost_basis, 4)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
