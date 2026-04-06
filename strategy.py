"""
strategy.py — RSI + EMA Crossover with ATR-based stops
-------------------------------------------------------
Signal logic:
  BUY  when RSI crosses ABOVE oversold level AND fast EMA > slow EMA
  SELL when RSI crosses BELOW overbought level OR fast EMA < slow EMA
  Stop loss & take profit are set dynamically using ATR so they adapt
  to current market volatility.
"""

import pandas as pd
import numpy as np


# ── Indicator calculations ──────────────────────────────────────────────────

def calc_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


# ── Main signal function ────────────────────────────────────────────────────

def generate_signals(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """
    Expects a DataFrame with columns: open, high, low, close, volume
    Returns the same DataFrame with added indicator + signal columns.
    """
    df = df.copy()

    df["rsi"]      = calc_rsi(df["close"], cfg.RSI_PERIOD)
    df["ema_fast"] = calc_ema(df["close"], cfg.EMA_FAST)
    df["ema_slow"] = calc_ema(df["close"], cfg.EMA_SLOW)
    df["atr"]      = calc_atr(df["high"], df["low"], df["close"], cfg.ATR_PERIOD)

    # Trend filter: fast EMA above/below slow EMA
    df["uptrend"]   = df["ema_fast"] > df["ema_slow"]
    df["downtrend"] = df["ema_fast"] < df["ema_slow"]

    # RSI crossover detection
    df["rsi_was_oversold"]   = df["rsi"].shift(1) < cfg.RSI_OVERSOLD
    df["rsi_now_recovering"] = df["rsi"] >= cfg.RSI_OVERSOLD
    df["rsi_was_overbought"] = df["rsi"].shift(1) > cfg.RSI_OVERBOUGHT
    df["rsi_now_dropping"]   = df["rsi"] <= cfg.RSI_OVERBOUGHT

    # Signal columns
    df["signal"] = 0  # 0 = hold, 1 = buy, -1 = sell

    buy_condition = (
        df["rsi_was_oversold"] & df["rsi_now_recovering"] & df["uptrend"]
    )
    sell_condition = (
        (df["rsi_was_overbought"] & df["rsi_now_dropping"]) | df["downtrend"]
    )

    df.loc[buy_condition,  "signal"] = 1
    df.loc[sell_condition, "signal"] = -1

    # Dynamic SL/TP based on ATR
    df["stop_loss"]   = df["close"] - df["atr"] * cfg.STOP_LOSS_ATR_MULT
    df["take_profit"] = df["close"] + df["atr"] * cfg.TAKE_PROFIT_ATR_MULT

    return df


def get_signal_strength(row: pd.Series) -> str:
    """Returns a human-readable signal strength label."""
    rsi = row.get("rsi", 50)
    if rsi < 25 or rsi > 75:
        return "💪 STRONG"
    elif rsi < 35 or rsi > 65:
        return "✅ MODERATE"
    return "⚠️ WEAK"
