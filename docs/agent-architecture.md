# Agent Architecture

## Overview

Agent Trader uses a **hub-and-spoke multi-agent model**. The `orchestrator` is the hub — it receives all user messages, applies the user's personal prompt, and routes to specialist agents as needed.

```
User Message
     │
     ▼
┌─────────────┐
│ Orchestrator │  ← applies personal prompt
└──────┬──────┘
       │ routes to 1..N specialists
       ├──────────────────────────────────────┐
       │                                      │
  ┌────┴────┐                           ┌─────┴──────┐
  │ Market   │                           │  Context   │
  │ Analysis │                           │  & News    │
  └────┬─────┘                          └─────┬───────┘
       │                                      │
  ┌────┴──────────┐                    ┌──────┴──────────┐
  │ technical-    │                    │ news-fetcher    │
  │ analyst       │                    │ twitter-monitor │
  │ timeframe-    │                    │ sentiment-      │
  │ analyzer      │                    │ monitor         │
  │ vwap-watcher  │                    │ geopolitical-   │
  │ pattern-finder│                    │ analyst         │
  └───────────────┘                    └─────────────────┘

  ┌────────────────────┐          ┌──────────────────────┐
  │ Time-Aware Agents  │          │ Fundamental Agents   │
  └────────────────────┘          └──────────────────────┘
  premarket-specialist             fundamental-analyst
  market-open-scalper              earnings-expert
  postmarket-summarizer            economic-calendar
  overnight-expert
```

## Agent Activation by Market Session

| Session | Active Agents |
|---------|--------------|
| Pre-Market (4–9:29 AM ET) | premarket-specialist, news-fetcher, economic-calendar |
| Open Window (8:50–10:00 AM) | market-open-scalper, vwap-watcher, technical-analyst |
| Regular Hours (9:30–4:00 PM) | technical-analyst, timeframe-analyzer, vwap-watcher, sentiment-monitor, news-fetcher |
| Post-Market (4:00–8:00 PM) | postmarket-summarizer, earnings-expert (if earnings), news-fetcher |
| Overnight (8:00 PM–4:00 AM) | overnight-expert, economic-calendar, geopolitical-analyst |

## Agent Communication Protocol

- All agents receive: ticker, user personal prompt, session context
- Agents return: structured JSON response + plain text summary
- Orchestrator merges responses, deduplicates, and formats for UI
- Agents can request data from other agents via orchestrator (no direct agent-to-agent calls)

## Latency Targets

| Query Type | Target Latency |
|-----------|---------------|
| Single-agent query | <2s |
| Multi-agent (3–4 agents) | <5s |
| Full market open briefing | <8s |
| Background monitoring alerts | real-time push |

## Scalability

- Each agent is stateless per query — state lives in session context
- Agents can run in parallel for multi-agent queries
- Orchestrator handles fan-out and fan-in
