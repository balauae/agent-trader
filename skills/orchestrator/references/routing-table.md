# Orchestrator Routing Table

## Intent Detection

The orchestrator parses the user query to determine intent and ticker. Intent is matched by keywords in the query.

## Routing Matrix

| Intent     | Keywords                                                        | Agents                                                              | Ticker Required |
|------------|-----------------------------------------------------------------|---------------------------------------------------------------------|-----------------|
| `analyze`  | "analyze", "analysis", "look at", "check", "what about"        | technical_analyst, vwap_watcher, news_fetcher, economic_calendar    | Yes             |
| `news`     | "news", "headlines", "what happened", "catalyst", "why"         | news_fetcher                                                        | Yes             |
| `chart`    | "chart", "setup", "technical", "indicators", "levels", "entry"  | technical_analyst, vwap_watcher                                     | Yes             |
| `calendar` | "earnings", "calendar", "events", "fomc", "fed", "opex", "macro"| economic_calendar                                                   | Optional        |
| `market`   | "market", "summary", "overview", "broad", "sector"             | technical_analyst (SPY), news_fetcher (SPY), economic_calendar      | No (defaults SPY) |

## Agent Scripts

| Agent              | Script                              | Requires Ticker | Timeout |
|--------------------|-------------------------------------|-----------------|---------|
| technical_analyst  | `scripts/technical_analyst.py`      | Yes             | 15s     |
| vwap_watcher       | `scripts/vwap_watcher.py`           | Yes             | 15s     |
| news_fetcher       | `scripts/news_fetcher.py`           | Yes             | 15s     |
| economic_calendar  | `scripts/economic_calendar.py`      | Optional        | 15s     |

## Fallback Behavior

- If no intent is matched, default to `analyze` (if ticker found) or `market` (if no ticker)
- If no ticker is found and intent requires one, use `SPY` as proxy for broad market
- If a query mentions multiple tickers, use the first one detected

## Session Routing Adjustments

| Session     | Adjustments                                                   |
|-------------|---------------------------------------------------------------|
| Pre-Market  | VWAP data may be stale — flag in output                       |
| Open        | VWAP is forming — flag first-15-min caveat                    |
| Regular     | All agents fully valid                                        |
| Post-Market | VWAP/technical data from last RTH session — flag staleness    |
| Overnight   | Only news and calendar are fully relevant                     |
