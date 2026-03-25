# News Sources & Reliability Ratings

Sources used by the news-fetcher skill, rated for speed and reliability.

## Active Sources

| Source | Type | Speed | Reliability | Notes |
|--------|------|-------|-------------|-------|
| **Yahoo Finance** | API (yfinance) | Fast (<1s) | High | Broad coverage, includes wire services (Reuters, AP). Primary source. |
| **Finviz** | Web scrape | Medium (1-3s) | High | Excellent for analyst actions, SEC filings, and financial-specific news. |

## Source Characteristics

### Yahoo Finance
- Aggregates: Reuters, AP, Bloomberg (excerpts), Motley Fool, Barron's, MarketWatch
- Strength: Speed, breadth, structured data
- Weakness: Can lag on breaking SEC filings by a few minutes
- Access: `data_fetcher.get_news()` via yfinance API

### Finviz
- Aggregates: Benzinga, MarketWatch, GlobeNewsWire, PR Newswire, SEC filings
- Strength: Financial-specific filtering, analyst coverage, insider trades
- Weakness: Scraping can break if Finviz changes HTML structure; rate limited
- Access: HTML scrape of `finviz.com/quote.ashx?t=TICKER`

## Publisher Reliability Tiers

**Tier 1 — Wire services & major outlets** (cite directly)
- Reuters, AP, Bloomberg, WSJ, Financial Times, CNBC

**Tier 2 — Financial media** (cite with context)
- Benzinga, MarketWatch, Barron's, Seeking Alpha (news articles only), Investor's Business Daily

**Tier 3 — Aggregators & opinion** (flag as opinion when relevant)
- Motley Fool, InvestorPlace, Zacks (commentary), Seeking Alpha (opinion/analysis)

## Planned Future Sources

| Source | Type | Status |
|--------|------|--------|
| SEC EDGAR | API | Planned — 8-K and Form 4 real-time alerts |
| Google News RSS | RSS | Planned — broader non-financial coverage |
| Twitter/X | API | Planned — via `twitter-monitor` agent |
