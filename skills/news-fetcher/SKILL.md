# Skill: News Fetcher

**Agent:** `news-fetcher`
**Trigger:** News lookup, sudden price move investigation, pre-market context, "what happened to [ticker]?"

## Purpose

Fetch, classify, and present the most relevant recent news for a stock ticker. Identify market-moving catalysts and flag whether news explains an observed price move.

## How to Execute

### Step 1: Fetch News

Run the news fetcher script with the target ticker:

```bash
.venv/bin/python scripts/news_fetcher.py TICKER --pretty
```

Replace `TICKER` with the actual symbol (e.g., `AAPL`, `NVDA`, `TSLA`).

### Step 2: Parse Results

The script returns JSON with this structure:

```json
{
  "ticker": "NVDA",
  "fetched_at": "2026-03-25T...",
  "count": 15,
  "items": [
    {
      "title": "...",
      "publisher": "...",
      "published_at": "...",
      "summary": "...",
      "impact": "High",
      "source": "yahoo"
    }
  ]
}
```

Items are pre-sorted by impact: High > Medium > Low.

### Step 3: Present Results

Format output as a ranked news list:

```
NEWS REPORT: [TICKER] — [date]
═══════════════════════════════

[HIGH] Earnings beat: NVDA reports Q4 EPS $5.16 vs $4.64 est.
       Source: Reuters | 2h ago
       → This likely explains the +8% intraday move

[HIGH] Analyst upgrade: Goldman raises PT to $180
       Source: Benzinga | 5h ago

[MED]  New partnership with Microsoft on AI infra
       Source: TechCrunch | 1d ago

[LOW]  Opinion: Why NVDA remains a long-term hold
       Source: Motley Fool | 2d ago
```

### Step 4: Flag Catalysts

After listing news, add a **Catalyst Summary** section:

- If any **High** impact news was published in the last 4 hours, flag it as a potential catalyst for the current move
- If the user mentioned a price move, explicitly connect the most likely news item to that move
- If no obvious catalyst exists, state: "No clear news catalyst found — move may be technical or sector-driven"

## Impact Classification

| Rating | Triggers |
|--------|----------|
| **High** | Earnings, FDA decisions, mergers/acquisitions, SEC filings (8-K), analyst upgrades/downgrades, guidance changes, bankruptcy, layoffs |
| **Medium** | Product launches, partnerships, executive changes, contract wins, offerings |
| **Low** | General coverage, opinion pieces, listicles, sector commentary |

## Data Sources

- **Yahoo Finance** — broad coverage, fast, via `data_fetcher.get_news()`
- **Finviz** — aggregated financial news, good for analyst/SEC coverage

See `references/sources.md` for source reliability ratings.

## Error Handling

- If the script returns `"count": 0`, inform the user: "No recent news found for [TICKER]. The move may be driven by sector rotation, technical levels, or after-hours activity."
- If the script fails entirely, fall back to describing what you know from context and suggest the user check Finviz or Yahoo Finance directly.

## Coordination

- If news is **earnings-related**, hand off to `earnings-expert` for deeper analysis
- If news is **geopolitical/macro**, hand off to `geopolitical-analyst`
- If the user wants **social sentiment**, coordinate with `twitter-monitor`
