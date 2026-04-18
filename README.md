# AI Stock Analysis

A multi-agent AI system that analyzes stocks through a four-layer pipeline: data ingestion, specialist analyst agents, adversarial bull/bear debate, and synthesis into actionable briefings. Designed as a decision-support tool — it surfaces structured analysis, not trade signals.

## Architecture

The system processes stock data through four sequential layers:

```
Data Ingestion  -->  Analyst Agents  -->  Adversarial Debate  -->  Synthesis & Briefing
  (Layer 1)           (Layer 2)            (Layer 3)               (Layer 4)
```

**Layer 1 — Data Ingestion** fetches market data from external sources with no LLM involvement. Currently supports US equities via [yfinance](https://github.com/ranaroussi/yfinance). Bursa/KLSE (Malaysia) support is planned.

**Layer 2 — Analyst Agents** run four specialist LLM agents in parallel:
- **Fundamentals** — P/E ratios, margins, debt structure, growth outlook
- **Sentiment** — News tone, social sentiment, key themes
- **Technical** — RSI, MACD, volume analysis, support/resistance levels
- **Macro/FX** — Fed policy, interest rates, FX impact, geopolitical risks

Each agent produces a structured report with a signal (strong buy → strong sell) and confidence level.

**Layer 3 — Adversarial Debate** pits a Bull researcher against a Bear researcher across multiple rounds. They build cases, rebut each other, and surface points of agreement, disagreement, and unresolved uncertainty.

**Layer 4 — Synthesis** merges all reports and debate output into a final briefing with a conviction score, risk assessment, and executive summary.

See [`architecture.md`](architecture.md) for the full diagram.

## Markets Supported

| Market | Status | Data Sources |
|--------|--------|-------------|
| US (NYSE, NASDAQ) | Implemented | yfinance (price, financials, news, analyst recs) |
| Malaysia (Bursa/KLSE) | Planned | Bursa API, i3investor, BNM rates, MYR/USD FX |

## Prerequisites

- Python 3.12+
- An Anthropic API key (for the Claude-powered agents)

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd ai-stock-analysis

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e .

# For development (linting, testing)
pip install -e ".[dev]"
```

No API keys are required — the project uses Claude Code's built-in model access.

## Project Structure

```
src/stock_analysis/
├── models/              # Pydantic data models
│   ├── market_data.py   # TickerData, PriceBar, FinancialStatements
│   ├── agent_reports.py # FundamentalsReport, SentimentReport, TechnicalReport, MacroFXReport
│   ├── debate.py        # DebateArgument, DebateRound, DebateResult
│   └── synthesis.py     # Briefing, ConvictionScore, RiskAssessment
├── data/                # Data fetching and storage
│   ├── fetcher_base.py  # Abstract BaseFetcher interface
│   ├── us_market.py     # USMarketFetcher (yfinance)
│   ├── my_market.py     # MYMarketFetcher (stub)
│   └── store.py         # DataStore — JSON file persistence per ticker/date
├── agents/              # Layer 2 analyst agents (WIP)
├── debate/              # Layer 3 adversarial debate (WIP)
├── synthesis/           # Layer 4 synthesis and risk (WIP)
└── api/                 # FastAPI endpoints (WIP)
```

Data is stored as JSON files organized by ticker and date:

```
data/
└── AAPL/
    └── 2026-04-16/
        ├── market_data.json
        ├── analyst_reports.json
        ├── debate_result.json
        └── briefing.json
```

## Development

```bash
# Run linter
ruff check src/

# Run formatter
ruff format src/

# Run tests
pytest
```

## Tech Stack

- **LLM orchestration**: [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
- **Data models**: [Pydantic](https://docs.pydantic.dev/) v2
- **Market data**: [yfinance](https://github.com/ranaroussi/yfinance)
- **API**: [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **HTTP client**: [httpx](https://www.python-httpx.org/)

## Disclaimer

This tool is for informational and educational purposes only. It is not financial advice. Always do your own research before making investment decisions.
