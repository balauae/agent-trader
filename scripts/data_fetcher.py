"""
data_fetcher.py — Re-export from canonical location
=====================================================
All imports should use: from scripts.data.fetcher import ...
This file exists for backwards compatibility with root-level scripts.
"""

from scripts.data.fetcher import (  # noqa: F401
    get_ohlcv,
    get_current_price,
    get_fundamentals,
    get_earnings,
    get_news,
    get_market_summary,
    get_ohlcv_smart,
    reset_tv_client,
    EXCHANGE_MAP,
    TF_MAP,
)
