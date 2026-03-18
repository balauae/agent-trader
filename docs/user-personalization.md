# User Personalization

## Personal Prompt

Every user can define a **master personal prompt** that shapes how all agents respond. Think of it as your trading profile — it tells the system who you are and how you trade.

### Example Personal Prompts

**Day Trader:**
> "I'm a momentum day trader. Prefer 5-min and 1-min charts. Risk tolerance: medium. Max position size: $15K. Always lead with VWAP setups. Ignore fundamentals unless earnings is within 2 weeks. Flag gap-and-go setups at open."

**Swing Trader:**
> "I swing trade 3–10 days. Focus on daily chart setups. I want fundamentals context on every stock. Risk per trade: 1.5% of portfolio. Flag earnings dates prominently. Prefer clean breakout setups on high volume."

**Options Trader:**
> "I trade options primarily. Always show IV rank and implied move. Prefer defined-risk spreads. Flag IV crush risk on earnings plays. Show me put/call flow on any stock I'm watching."

### What the Personal Prompt Controls

| Setting | Effect |
|---------|--------|
| Trading style (day/swing/scalp) | Agents adjust timeframe depth and output detail |
| Preferred timeframes | Timeframe-analyzer defaults to these |
| Risk tolerance | Stop loss sizing, position size warnings |
| Fundamentals interest | Fundamental-analyst verbosity |
| Options vs stock | Earnings-expert output format |
| Preferred setup types | Orchestrator prioritizes matching setups |
| Notification preferences | Which alerts to push proactively |

---

## Watchlists

- Each user gets up to **10 watchlists**
- Default watchlist: `main`
- Each watchlist: up to 50 tickers
- Watchlists can be named (e.g., "Earnings plays", "Tech momentum", "Swing setups")
- Active watchlist is used for morning briefings and proactive alerts

---

## Notification & Alert Preferences

Users can configure proactive alerts per ticker or globally:

- Price alerts (above/below level)
- VWAP break alerts
- News catalyst alerts
- Earnings approaching (7 days, 2 days, day-of)
- Pre-market gap alerts (>X%)
- Unusual options activity
- Sentiment spike (mention volume >3x)
