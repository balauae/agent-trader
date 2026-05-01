"""
position_sizer.py — Position Size & Risk Calculator
=====================================================
Calculates optimal position size based on risk management rules.

Usage:
    python scripts/tools/position_sizer.py TICKER ENTRY STOP [--account 100000] [--risk-pct 1.0]
    python scripts/tools/position_sizer.py PLTR 145 140                    # default $100K account, 1% risk
    python scripts/tools/position_sizer.py NVDA 950 920 --account 50000    # custom account size
    python scripts/tools/position_sizer.py MU 450 435 --risk-pct 0.5       # half-percent risk
"""

import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.data.fetcher import get_ohlcv_smart

logger = logging.getLogger(__name__)


def calculate(
    ticker: str,
    entry: float,
    stop: float,
    account: float = 100000,
    risk_pct: float = 1.0,
    target: float | None = None,
) -> dict:
    """Calculate position size and risk parameters.

    Args:
        ticker: Stock symbol
        entry: Planned entry price
        stop: Stop loss price
        account: Total account value
        risk_pct: Max risk per trade as % of account (default 1%)
        target: Optional profit target price
    """
    ticker = ticker.upper()

    if entry <= 0 or stop <= 0:
        return {"ticker": ticker, "error": "Entry and stop must be positive"}
    if entry == stop:
        return {"ticker": ticker, "error": "Entry and stop cannot be the same price"}

    # Direction
    direction = "LONG" if entry > stop else "SHORT"

    # Risk per share
    risk_per_share = abs(entry - stop)
    risk_pct_per_share = round(risk_per_share / entry * 100, 2)

    # Dollar risk budget
    dollar_risk = account * (risk_pct / 100)

    # Shares
    shares = int(dollar_risk / risk_per_share)
    if shares <= 0:
        return {"ticker": ticker, "error": f"Risk per share (${risk_per_share:.2f}) exceeds account risk budget (${dollar_risk:.2f})"}

    # Position value
    position_value = round(shares * entry, 2)
    position_pct = round(position_value / account * 100, 2)

    # R multiples
    actual_risk = round(shares * risk_per_share, 2)

    # Target analysis
    target_info = None
    if target:
        reward_per_share = abs(target - entry)
        rr_ratio = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else 0
        potential_profit = round(shares * reward_per_share, 2)
        target_info = {
            "price": round(target, 2),
            "reward_per_share": round(reward_per_share, 2),
            "potential_profit": potential_profit,
            "risk_reward": rr_ratio,
        }

    # Fetch ATR for context
    atr_info = None
    try:
        daily_df, src = get_ohlcv_smart(ticker, "1D", 20)
        daily_df.columns = [c.lower() for c in daily_df.columns]
        if not daily_df.empty and len(daily_df) >= 14:
            h, l, c = daily_df["high"], daily_df["low"], daily_df["close"]
            import pandas as pd
            tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])
            current_price = float(c.iloc[-1])
            atr_info = {
                "atr_14": round(atr, 2),
                "atr_pct": round(atr / current_price * 100, 2),
                "current_price": round(current_price, 2),
                "stop_in_atr": round(risk_per_share / atr, 2) if atr > 0 else None,
                "suggested_stop_1atr": round(entry - atr if direction == "LONG" else entry + atr, 2),
                "suggested_stop_1_5atr": round(entry - 1.5 * atr if direction == "LONG" else entry + 1.5 * atr, 2),
            }
    except Exception:
        pass

    # Tiered position sizing (scale in)
    tiers = {
        "full": shares,
        "half": shares // 2,
        "third": shares // 3,
        "quarter": shares // 4,
    }

    return {
        "ticker": ticker,
        "direction": direction,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "risk_per_share": round(risk_per_share, 2),
        "risk_pct_per_share": risk_pct_per_share,
        "account": round(account, 2),
        "risk_pct": risk_pct,
        "dollar_risk": round(dollar_risk, 2),
        "shares": shares,
        "position_value": position_value,
        "position_pct": position_pct,
        "actual_risk": actual_risk,
        "tiers": tiers,
        "target": target_info,
        "atr": atr_info,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    import argparse
    parser = argparse.ArgumentParser(description="Position Size Calculator")
    parser.add_argument("ticker", help="Stock symbol")
    parser.add_argument("entry", type=float, help="Entry price")
    parser.add_argument("stop", type=float, help="Stop loss price")
    parser.add_argument("--account", type=float, default=100000, help="Account size (default: $100,000)")
    parser.add_argument("--risk-pct", type=float, default=1.0, help="Risk per trade %% (default: 1.0)")
    parser.add_argument("--target", type=float, default=None, help="Profit target price")
    args = parser.parse_args()

    result = calculate(args.ticker, args.entry, args.stop, args.account, args.risk_pct, args.target)
    print(json.dumps(result, indent=2, default=str))
