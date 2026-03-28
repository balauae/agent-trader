"""
data_fetcher.py — Shared Data Layer for TradeDesk
===================================================
All agent skills call this module for market data.
Never fetch data directly in a skill — always go through here.

Usage:
    from scripts.data_fetcher import get_ohlcv, get_news, get_fundamentals, get_earnings

Supported timeframes (TradingView):
    1m, 5m, 15m, 30m, 1h, 2h, 4h, 1D, 1W
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import yfinance as yf

# TradingView
from tvDatafeed import TvDatafeed, Interval

logger = logging.getLogger(__name__)

# --- Paths ---
REPO_ROOT    = Path(__file__).parent.parent
SECRETS_FILE = REPO_ROOT / ".secrets" / "tradingview.json"

# --- Timeframe map ---
TF_MAP = {
    "1m":  Interval.in_1_minute,
    "5m":  Interval.in_5_minute,
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h":  Interval.in_1_hour,
    "2h":  Interval.in_2_hour,
    "4h":  Interval.in_4_hour,
    "1D":  Interval.in_daily,
    "1W":  Interval.in_weekly,
}

# --- Exchange map (default NASDAQ, override as needed) ---
EXCHANGE_MAP = {
    "SPY": "AMEX", "QQQ": "NASDAQ", "IWM": "AMEX",
    "VIX": "CBOE", "DXY": "TVC",
    "GOLD": "TVC", "USOIL": "TVC",
}

_tv_client: Optional[TvDatafeed] = None

def reset_tv_client():
    """Force a fresh TV connection on next call."""
    global _tv_client
    _tv_client = None


def _get_tv_client() -> TvDatafeed:
    """Get or create TradingView client with fresh token."""
    global _tv_client

    token = None
    if SECRETS_FILE.exists():
        creds = json.loads(SECRETS_FILE.read_text())
        token = creds.get("auth_token")

        # Check if token is still valid (>30 min remaining)
        expires = creds.get("token_expires")
        if expires:
            exp_dt = datetime.fromisoformat(expires)
            remaining = (exp_dt - datetime.now(tz=timezone.utc)).total_seconds()
            if remaining < 1800:
                logger.warning(f"TV token expires in {remaining/60:.0f}min — refresh soon")

    tv = TvDatafeed()
    if token:
        tv.token = token
    else:
        logger.warning("No TV token found — using anonymous (limited data)")

    _tv_client = tv
    return tv


# ─────────────────────────────────────────────
# OHLCV DATA (TradingView)
# ─────────────────────────────────────────────

def get_ohlcv(
    ticker: str,
    timeframe: str = "1D",
    bars: int = 100,
    exchange: str = None
) -> pd.DataFrame:
    """
    Fetch OHLCV bars from TradingView.

    Args:
        ticker:    Stock symbol e.g. 'AAPL', 'NVDA'
        timeframe: '1m','5m','15m','30m','1h','2h','4h','1D','1W'
        bars:      Number of bars to fetch
        exchange:  Exchange override e.g. 'NYSE', 'NASDAQ'. Auto-detected if None.

    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    if timeframe not in TF_MAP:
        raise ValueError(f"Invalid timeframe '{timeframe}'. Use: {list(TF_MAP.keys())}")

    tv = _get_tv_client()
    exch = exchange or EXCHANGE_MAP.get(ticker.upper(), "NASDAQ")
    interval = TF_MAP[timeframe]

    for attempt in range(3):
        try:
            if attempt > 0:
                time.sleep(1.5 * attempt)
                tv = _get_tv_client()  # fresh client on retry
            df = tv.get_hist(ticker.upper(), exch, interval=interval, n_bars=bars)
            if df is None or df.empty:
                df = tv.get_hist(ticker.upper(), "NYSE", interval=interval, n_bars=bars)
            if df is not None and not df.empty:
                df = df[["open", "high", "low", "close", "volume"]].copy()
                df.index = pd.to_datetime(df.index)
                return df
        except Exception as e:
            logger.warning(f"TV fetch attempt {attempt+1} failed for {ticker}: {e}")

    return pd.DataFrame()


def get_current_price(ticker: str) -> Optional[float]:
    """Get the latest close price for a ticker."""
    df = get_ohlcv(ticker, timeframe="1D", bars=1)
    if not df.empty:
        return float(df["close"].iloc[-1])
    return None


# ─────────────────────────────────────────────
# FUNDAMENTALS (yfinance)
# ─────────────────────────────────────────────

def get_fundamentals(ticker: str) -> dict:
    """
    Fetch key fundamental data for a ticker.

    Returns dict with: pe_ratio, forward_pe, market_cap, revenue,
    eps, gross_margin, analyst_rating, price_target, sector, industry
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info

        return {
            "ticker":          ticker.upper(),
            "name":            info.get("longName", ""),
            "sector":          info.get("sector", ""),
            "industry":        info.get("industry", ""),
            "market_cap":      info.get("marketCap"),
            "pe_ratio":        info.get("trailingPE"),
            "forward_pe":      info.get("forwardPE"),
            "peg_ratio":       info.get("pegRatio"),
            "ps_ratio":        info.get("priceToSalesTrailing12Months"),
            "pb_ratio":        info.get("priceToBook"),
            "ev_ebitda":       info.get("enterpriseToEbitda"),
            "revenue":         info.get("totalRevenue"),
            "revenue_growth":  info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "gross_margin":    info.get("grossMargins"),
            "operating_margin":info.get("operatingMargins"),
            "net_margin":      info.get("profitMargins"),
            "free_cashflow":   info.get("freeCashflow"),
            "debt_to_equity":  info.get("debtToEquity"),
            "cash":            info.get("totalCash"),
            "eps_ttm":         info.get("trailingEps"),
            "eps_forward":     info.get("forwardEps"),
            "analyst_rating":  info.get("recommendationKey", ""),
            "price_target":    info.get("targetMeanPrice"),
            "52w_high":        info.get("fiftyTwoWeekHigh"),
            "52w_low":         info.get("fiftyTwoWeekLow"),
            "avg_volume_30d":  info.get("averageVolume30Day") or info.get("averageVolume"),
            "float_shares":    info.get("floatShares"),
            "short_ratio":     info.get("shortRatio"),
            "short_pct_float": info.get("shortPercentOfFloat"),
        }
    except Exception as e:
        logger.error(f"Fundamentals fetch failed for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}


# ─────────────────────────────────────────────
# EARNINGS (yfinance)
# ─────────────────────────────────────────────

def get_earnings(ticker: str) -> dict:
    """
    Fetch earnings calendar data and historical EPS.

    Returns dict with: next_earnings_date, eps_estimate, revenue_estimate,
    historical earnings (last 4 quarters)
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        calendar = t.calendar

        next_date = None
        eps_estimate     = info.get("forwardEps")
        revenue_estimate = None

        if isinstance(calendar, dict):
            dates = calendar.get("Earnings Date", [])
            next_date = str(dates[0]) if dates else None
            revenue_estimate = calendar.get("Revenue Average")
        elif calendar is not None:
            try:
                if "Earnings Date" in calendar.index:
                    val = calendar.loc["Earnings Date"]
                    next_date = str(val.iloc[0]) if hasattr(val, "iloc") else str(val)
            except Exception:
                pass

        # Historical quarterly earnings
        try:
            hist = t.quarterly_earnings
            history = []
            if hist is not None and isinstance(hist, pd.DataFrame) and not hist.empty:
                for idx, row in hist.iterrows():
                    history.append({
                        "date":     str(idx),
                        "eps_act":  row.get("Earnings"),
                        "eps_est":  row.get("Estimate"),
                        "surprise": row.get("Surprise(%)"),
                    })
        except Exception:
            history = []

        return {
            "ticker":           ticker.upper(),
            "next_date":        next_date,
            "eps_estimate":     eps_estimate,
            "revenue_estimate": revenue_estimate,
            "history":          history[:8],  # last 8 quarters
            "implied_move_pct": info.get("twoHundredDayAverage"),  # placeholder
        }
    except Exception as e:
        logger.error(f"Earnings fetch failed for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}


# ─────────────────────────────────────────────
# NEWS (Yahoo Finance RSS)
# ─────────────────────────────────────────────

def get_news(ticker: str, limit: int = 10) -> list:
    """
    Fetch latest news for a ticker via yfinance.

    Returns list of dicts: title, publisher, link, published_at
    """
    try:
        t = yf.Ticker(ticker)
        raw = t.news or []
        news = []
        for item in raw[:limit]:
            # yfinance new nested structure
            content = item.get("content", item)
            pub_date = content.get("pubDate") or content.get("displayTime", "")
            provider = content.get("provider", {})
            canon    = content.get("canonicalUrl", {})
            news.append({
                "title":        content.get("title", item.get("title", "")),
                "publisher":    provider.get("displayName", item.get("publisher", "")),
                "link":         canon.get("url", item.get("link", "")),
                "published_at": pub_date,
                "summary":      content.get("summary", content.get("description", "")),
            })
        return news
    except Exception as e:
        logger.error(f"News fetch failed for {ticker}: {e}")
        return []


# ─────────────────────────────────────────────
# MARKET SUMMARY
# ─────────────────────────────────────────────

def get_market_summary() -> dict:
    """
    Get quick snapshot of major market indices.
    Returns SPY, QQQ, VIX, DXY latest prices.
    """
    tickers = {"SPY": "S&P 500", "QQQ": "Nasdaq", "IWM": "Russell 2000", "^VIX": "VIX"}
    result = {}
    try:
        data = yf.download(list(tickers.keys()), period="2d", interval="1d", progress=False)
        closes = data["Close"].iloc[-1]
        prev   = data["Close"].iloc[-2]
        for sym, name in tickers.items():
            if sym in closes:
                price  = float(closes[sym])
                change = float(closes[sym] - prev[sym])
                pct    = float(change / prev[sym] * 100)
                result[sym] = {"name": name, "price": price, "change": change, "pct": pct}
    except Exception as e:
        logger.error(f"Market summary failed: {e}")
    return result


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

def get_ohlcv_smart(ticker: str, timeframe: str = "1D", bars: int = 200, tv_timeout: int = 10) -> tuple:
    """
    Fetch OHLCV bars — TradingView primary, yfinance fallback.
    Returns: (DataFrame, source_str)
    source_str is "tv" or "yfinance"
    tv_timeout: seconds to wait for TV before falling back (default 10s)
    """
    import yfinance as yf
    import concurrent.futures

    # Try TradingView first with timeout
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(get_ohlcv, ticker, timeframe, bars)
            df = future.result(timeout=tv_timeout)
        if df is not None and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            return df, "tv"
    except Exception:
        pass

    # Fallback: yfinance
    tf_map = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "60m", "2h": "90m", "4h": "1h",
        "1D": "1d", "1W": "1wk",
    }
    period_map = {
        "1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d",
        "1h": "730d", "60m": "730d", "90m": "730d",
        "1d": "2y", "1wk": "5y",
    }
    yf_tf = tf_map.get(timeframe, "1d")
    period = period_map.get(yf_tf, "2y")
    try:
        df = yf.download(ticker, period=period, interval=yf_tf,
                         progress=False, auto_adjust=True)
        if not df.empty:
            df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower()
                          for c in df.columns]
            return df.tail(bars).copy(), "yfinance"
    except Exception:
        pass

    return pd.DataFrame(), "none"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== OHLCV Test (NVDA 5m) ===")
    df = get_ohlcv("NVDA", "5m", bars=5)
    print(df)

    print("\n=== Current Price (AAPL) ===")
    print(f"AAPL: ${get_current_price('AAPL')}")

    print("\n=== Fundamentals (AAPL) ===")
    f = get_fundamentals("AAPL")
    for k, v in f.items():
        if v is not None:
            print(f"  {k}: {v}")

    print("\n=== Earnings (NVDA) ===")
    e = get_earnings("NVDA")
    print(json.dumps(e, indent=2, default=str))

    print("\n=== News (TSLA) ===")
    for n in get_news("TSLA", limit=3):
        print(f"  [{n['published_at'][:10]}] {n['title']}")

    print("\n=== Market Summary ===")
    m = get_market_summary()
    for sym, d in m.items():
        print(f"  {sym}: ${d['price']:.2f} ({d['pct']:+.2f}%)")
