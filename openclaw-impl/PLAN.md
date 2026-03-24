# OpenClaw Implementation Plan — TradeDesk

> This is the build plan for implementing all agent-trader skills inside OpenClaw.
> The AI agent running this is `@aii_trader_bot` (agent-trader workspace).

---

## Overview

Each agent from the repo becomes an OpenClaw **skill** — a `SKILL.md` file that teaches the agent how to behave as that specialist. The `orchestrator` skill routes all incoming messages to the right specialists.

---

## Phase 1 — Foundation (Data Layer)

Before any skill works, we need reliable, shared data fetching. All skills call the same utility — no duplicated logic.

**Deliverable:** `scripts/data_fetcher.py` — shared module for price, news, fundamentals.

### Data Sources Decision Matrix

| Data Type | Free Option | Paid Upgrade |
|-----------|------------|--------------|
| OHLCV (intraday) | Yahoo Finance (`yfinance`) / Alpha Vantage | Polygon.io ($29/mo) — real-time |
| News | Yahoo Finance RSS, Finviz, Google News | — |
| Fundamentals | Yahoo Finance, Finviz scrape | — |
| Options chains | Tradier API (free) | — |
| Options flow / IV | Market Chameleon (free tier) | Unusual Whales (~$50/mo) |
| Social sentiment | StockTwits API (free) | X (Twitter) API ($100/mo) |
| Economic calendar | Trading Economics (scrape), Yahoo earnings | — |
| SEC filings | EDGAR API (free) | — |

### Decisions — Locked ✅

- [x] **Data tier:** Free only — Yahoo Finance (`yfinance`) for OHLCV, 15-min delay acceptable
- [x] **Options:** Tradier free tier for chains, Market Chameleon scrape for IV rank
- [x] **Social:** StockTwits API (free, trader-focused)
- [x] **Budget:** $0 — free stack only

**Known limitations with free stack:**
- 15-min intraday delay → `market-open-scalper` is a planning tool, not live execution
- No real-time options flow (Unusual Whales is paid) → `sentiment-monitor` limited
- No X/Twitter → `twitter-monitor` uses StockTwits only

---

## Phase 2 — Core Skills (Must-Have)

These 5 skills cover 80% of daily usage. Build in this order.

| # | Skill | Key Dependencies | Status |
|---|-------|-----------------|--------|
| 1 | `news-fetcher` | web_search, web_fetch, Yahoo/Finviz | ⬜ Not started |
| 2 | `technical-analyst` | data_fetcher (OHLCV + indicators) | ⬜ Not started |
| 3 | `vwap-watcher` | intraday OHLCV (1m/5m) | ⬜ Not started |
| 4 | `economic-calendar` | Yahoo earnings, Trading Economics | ⬜ Not started |
| 5 | `orchestrator` | all above wired up | ⬜ Not started |

---

## Phase 3 — Session Skills (Time-Aware)

Agents that activate based on market session. Depend on Phase 2.

| # | Skill | Active Window (ET) | Status |
|---|-------|--------------------|--------|
| 6 | `premarket-specialist` | 4:00–9:29 AM | ⬜ Not started |
| 7 | `market-open-scalper` | 8:50–10:00 AM | ⬜ Not started |
| 8 | `postmarket-summarizer` | 4:00–8:00 PM | ⬜ Not started |
| 9 | `overnight-expert` | 8:00 PM–4:00 AM | ⬜ Not started |

---

## Phase 4 — Deep Analysis Skills

| # | Skill | Complexity | Status |
|---|-------|-----------|--------|
| 10 | `timeframe-analyzer` | Medium | ⬜ Not started |
| 11 | `fundamental-analyst` | Medium | ⬜ Not started |
| 12 | `earnings-expert` | Medium | ⬜ Not started |
| 13 | `geopolitical-analyst` | Low (web tools) | ⬜ Not started |
| 14 | `pattern-finder` | High (algorithmic) | ⬜ Not started |

---

## Phase 5 — Social & Sentiment

| # | Skill | Needs | Status |
|---|-------|-------|--------|
| 15 | `sentiment-monitor` | Options flow API (Tradier/Unusual Whales) | ⬜ Not started |
| 16 | `twitter-monitor` | StockTwits or X API | ⬜ Not started |

---

## Skill File Structure (Per Skill)

Each skill lives in the OpenClaw workspace at `skills/<name>/`:

```
skills/
  technical-analyst/
    SKILL.md              ← instructions for the agent
    references/
      indicators.md       ← indicator formulas and thresholds
      output-templates.md ← structured output formats
    scripts/
      fetch_ohlcv.py      ← data fetch
      calc_indicators.py  ← compute EMAs, MACD, RSI, etc.

  news-fetcher/
    SKILL.md
    references/
      sources.md          ← list of news sources and URLs
    scripts/
      fetch_news.py

  orchestrator/
    SKILL.md              ← routing logic, session detection, personal prompt application
    references/
      routing-table.md    ← query → agents mapping
```

---

## Watchlist & User Config

- Watchlists stored in `USER.md` (already present in workspace)
- Upgrade path: `watchlists.json` for structured multi-watchlist support
- Personal prompt in `USER.md` — controls all agent tone and behavior

---

## Proactive Alerts via Cron

| Alert | Cron Schedule (Dubai GMT+4) | Agent |
|-------|----------------------------|-------|
| Morning briefing | 1:00 PM (9 AM ET) | orchestrator → premarket/calendar |
| Pre-market setup | 4:00 PM (12 PM ET... TODO: confirm ET offset) | premarket-specialist |
| Post-market recap | 12:30 AM (8:30 PM ET) | postmarket-summarizer |

> Note: Dubai is GMT+4. US Eastern (ET) is GMT-4 in EDT. Offset = 8 hours.
> 9:30 AM ET = 5:30 PM Dubai time.

---

## Suggested Build Timeline

| Week | Focus |
|------|-------|
| Week 1 | Finalize API choices, build `data_fetcher.py`, build `news-fetcher` skill |
| Week 2 | `technical-analyst` + `vwap-watcher` skills |
| Week 3 | `orchestrator` wiring + `economic-calendar` skill |
| Week 4 | Session agents: pre/open/post/overnight |
| Week 5 | `fundamental-analyst` + `earnings-expert` + `timeframe-analyzer` |
| Week 6 | `geopolitical-analyst` + `pattern-finder` |
| Week 7+ | `sentiment-monitor` + `twitter-monitor` (paid API phase) |

---

## Open Questions — ✅ All Resolved

1. ~~Real-time or delayed?~~ → **Delayed (free) — Yahoo Finance 15-min delay**
2. ~~Options trading?~~ → **Yes, free tier — Tradier + Market Chameleon**
3. ~~Social sentiment?~~ → **StockTwits (free)**
4. ~~Budget?~~ → **Free only ($0)**

---

*Last updated: 2026-03-24 | Author: @aii_trader_bot (agent-trader)*
