# TradingView Authentication — How It Works

## Overview

TradingView uses a JWT auth token to authenticate WebSocket data connections.
We extract this token from the logged-in browser session automatically.

## Why This Approach

- Bala logs into TradingView via **Google OAuth** (no password)
- The `bala` OpenClaw browser profile has persistent Google login saved
- TradingView embeds the JWT auth token directly in the chart page HTML
- We extract it via a simple JS regex — no scraping tricks needed
- Token is injected into `tvdatafeed` to pull real-time data

## Token Details

| Field | Value |
|-------|-------|
| Plan | `pro_premium` |
| Username | `balaprasannav2009` |
| Extended hours | ✅ enabled |
| Expiry | ~4 hours from issue |
| Max charts | 8 |
| Max studies | 25 |

## Files

| File | Purpose |
|------|---------|
| `.secrets/tradingview.json` | Stores current token (gitignored) |
| `scripts/refresh_tv_token.py` | Token refresh script |

## `.secrets/tradingview.json` Format

```json
{
  "auth_token": "eyJ...",
  "plan": "pro_premium",
  "user_id": "18463147",
  "token_expires": "2026-03-25T14:00:00+00:00",
  "token_refreshed_at": "2026-03-25T10:00:00+00:00",
  "login_method": "google"
}
```

## Refresh Script

```bash
python scripts/refresh_tv_token.py
```

**What it does:**
1. Starts the `bala` OpenClaw browser profile (already logged in via Google)
2. Opens `https://www.tradingview.com/chart/`
3. Waits 6 seconds for page to load
4. Extracts `auth_token` from page HTML via regex
5. Decodes JWT to verify plan + expiry
6. Saves to `.secrets/tradingview.json`
7. Closes browser

## Auto-Refresh (Cron)

Token is refreshed every 4 hours via OpenClaw cron job.
See `openclaw-impl/PLAN.md` for cron schedule.

## Using the Token in Code

```python
import json
from tvDatafeed import TvDatafeed, Interval

creds = json.load(open('.secrets/tradingview.json'))
tv = TvDatafeed()
tv.token = creds['auth_token']

df = tv.get_hist('NVDA', 'NASDAQ', interval=Interval.in_5_minute, n_bars=100)
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Token not found in page | Page didn't load fully — increase `WAIT_LOAD_SEC` |
| Browser won't start | Check `openclaw browser status --profile bala` |
| Google session expired | Open `bala` profile manually, re-login once |
| `tvdatafeed` returns no data | Token may be expired — run refresh script |
