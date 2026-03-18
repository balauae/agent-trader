# Agent Trader

An AI-powered trading assistant platform backed by a multi-agent architecture.

## Overview

Agent Trader is a web/mobile app where traders manage their watchlists, analyze stocks with TradingView-integrated charts, and interact with a fleet of specialized AI agents — all in one place.

## Key Features

- **Multi-user, personalized** — each user has a master prompt that controls agent behavior
- **Watchlists** — up to 10 per user, default `main` watchlist
- **Stock Detail Page** — TradingView chart (2/3 screen) + AI Chat Panel (1/3, collapsible overlay)
- **Multi-Agent Chat** — specialized agents collaborate in a single chat window per stock
- **Market-hours-aware** — agents adapt to pre-market, open, intraday, post-market contexts

## Agent Fleet

See [`agents/`](./agents/) for individual agent specs.

| Agent | Role |
|-------|------|
| [orchestrator](./agents/orchestrator.md) | Main router, user context, personal prompt |
| [technical-analyst](./agents/technical-analyst.md) | Chart analysis, EMAs, MACD, RSI, multi-timeframe |
| [timeframe-analyzer](./agents/timeframe-analyzer.md) | Timeframe-specific setups (1m, 5m, 15m, 1h, 1D) |
| [vwap-watcher](./agents/vwap-watcher.md) | VWAP bounces, breaks, band setups |
| [pattern-finder](./agents/pattern-finder.md) | Historical chart pattern recognition |
| [fundamental-analyst](./agents/fundamental-analyst.md) | Earnings, valuation, balance sheet |
| [sentiment-monitor](./agents/sentiment-monitor.md) | Social sentiment, options flow, put/call |
| [news-fetcher](./agents/news-fetcher.md) | Real-time news aggregation |
| [twitter-monitor](./agents/twitter-monitor.md) | X/Twitter sentiment & influencer tracking |
| [geopolitical-analyst](./agents/geopolitical-analyst.md) | Macro/geopolitical impact on sectors & stocks |
| [economic-calendar](./agents/economic-calendar.md) | Fed, CPI, NFP, earnings dates |
| [earnings-expert](./agents/earnings-expert.md) | Earnings plays, IV crush, historical patterns |
| [premarket-specialist](./agents/premarket-specialist.md) | 4AM–9:30AM gaps, futures, pre-market flow |
| [market-open-scalper](./agents/market-open-scalper.md) | 8:50–9:15AM opening range & scalp setups |
| [postmarket-summarizer](./agents/postmarket-summarizer.md) | After-hours recap, next-day outlook |
| [overnight-expert](./agents/overnight-expert.md) | After-close to before-open trade planning |

## Docs

- [Agent Architecture](./docs/agent-architecture.md)
- [User Personalization](./docs/user-personalization.md)
