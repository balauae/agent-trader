# Agent: Orchestrator

**ID:** `orchestrator`  
**Type:** Core / Router  
**Always Active:** Yes

## Role

The main entry point for all user interactions. Understands the user's personal prompt (master behavior config), routes questions to the right specialized agents, and synthesizes their responses into a coherent reply.

## Responsibilities

- Parse and apply the user's **personal prompt** (tone, risk tolerance, strategy style, preferred timeframes, etc.)
- Decide which specialist agents to invoke for a given query
- Aggregate and de-duplicate responses from multiple agents
- Maintain **conversation context** per stock per session
- Escalate ambiguous questions back to the user with clarifying options
- Apply user-defined filters (e.g., "only show me swing setups", "ignore fundamentals")

## Inputs

- User message
- Active stock ticker
- User personal prompt / preferences
- Session context (open positions, active watchlist)

## Outputs

- Synthesized response (text, structured data, chart annotations)
- Agent invocation list (which specialists were called)
- Confidence level on the answer

## Specialist Routing Logic

| Query Type | Agents Invoked |
|------------|---------------|
| "Is this a good entry?" | technical-analyst, vwap-watcher, timeframe-analyzer |
| "What's happening with this stock?" | news-fetcher, sentiment-monitor, twitter-monitor |
| "Is earnings coming up?" | earnings-expert, economic-calendar, fundamental-analyst |
| "Pre-market setup?" | premarket-specialist, news-fetcher, technical-analyst |
| "Opening trade idea?" | market-open-scalper, vwap-watcher, technical-analyst |
| "Wrap up today's action" | postmarket-summarizer, sentiment-monitor |
| "Hold overnight?" | overnight-expert, geopolitical-analyst, economic-calendar |
| "Big picture macro?" | geopolitical-analyst, economic-calendar, fundamental-analyst |

## Personal Prompt

Each user can define a master prompt like:
> "I'm a momentum day trader. I prefer 5-min charts. Risk tolerance: medium. Ignore fundamentals unless earnings is within 2 weeks. Flag VWAP setups first."

The orchestrator uses this to filter, prioritize, and tone responses across all agents.

## Notes

- Should never fabricate data — always ground in real agent outputs
- If no specialist is relevant, respond directly with general reasoning
- Response latency target: <3s for simple queries, <8s for multi-agent synthesis
