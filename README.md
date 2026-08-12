<p align="center">
  <img src="docs/screenshot.png" alt="AI Stock Analysis dashboard" width="100%">
</p>

<h1 align="center">AI Stock Analysis 📈</h1>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-A3E635?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://github.com/KelvinYou/ai-stock-analysis/actions/workflows/fetch.yml"><img src="https://img.shields.io/github/actions/workflow/status/KelvinYou/ai-stock-analysis/fetch.yml?branch=main&style=for-the-badge&label=Daily%20Fetch" alt="Daily Fetch"></a>
  <a href="https://github.com/anthropics/claude-agent-sdk"><img src="https://img.shields.io/badge/Built%20with-Claude%20Agent%20SDK-6B4BFF?style=for-the-badge" alt="Built with Claude Agent SDK"></a>
</p>

<p align="center">
  <b>Four specialist agents research a stock. A bull and a bear debate their findings. A synthesizer turns the argument into an actionable briefing — with entry, stop, and target levels.</b>
</p>

---

**A four-layer research pipeline for equity decision support.** Fundamentals, Sentiment, Technical, and Macro/FX agents run in parallel. A Bull and Bear researcher then debate their findings across multiple rounds. A synthesizer merges the argument into a briefing with concrete price levels gated on conviction — not abstract "hold" signals.

Built on the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) with mixed-model routing — Haiku for analyst agents, Opus for adversarial debate, Sonnet for synthesis — so cost scales with the reasoning depth each layer actually needs.

<table>
<tr><td width="30%"><b>🧑‍💼 Four parallel analyst agents</b></td><td>Fundamentals, Sentiment, Technical, and Macro/FX run concurrently. Each returns a typed report with a signal (strong buy → strong sell) and a confidence score.</td></tr>
<tr><td><b>⚖️ Adversarial bull/bear debate</b></td><td>Multi-round researcher debate surfaces points of agreement, disagreement, and unresolved uncertainty — not a single averaged take.</td></tr>
<tr><td><b>🎯 Actionable price levels</b></td><td>Briefings include entry, stop, and target levels gated on conviction. No abstract signals that tell you nothing.</td></tr>
<tr><td><b>📊 Conviction & convergence metrics</b></td><td>Every briefing reports a conviction score (−1.0 to +1.0) capped by the confidence-weighted net consensus of the four agents, plus a deterministic convergence score.</td></tr>
<tr><td><b>⏮️ Historical backtesting</b></td><td>Replay the full pipeline over any date range. Score hit rate and directional accuracy against realized price moves.</td></tr>
<tr><td><b>🖥️ Web dashboard + REST API</b></td><td>Next.js portfolio view with per-ticker drill-down. FastAPI job queue for programmatic runs. Conviction meter, debate transcript, watchlist.</td></tr>
<tr><td><b>💸 Cost-tuned model routing</b></td><td>Haiku for analyst agents, Opus for debate, Sonnet for synthesis. Configurable per layer in <code>config.py</code>.</td></tr>
</table>

---

## Quick Start

```bash
git clone https://github.com/KelvinYou/ai-stock-analysis.git
cd ai-stock-analysis
python -m venv .venv && source .venv/bin/activate
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...

stock-analysis AAPL --market US -v
```

Works on Linux, macOS, and WSL2 with Python 3.12+. Node.js 18+ is required for the web dashboard.

---

## Commands

| Command | Purpose |
|---------|---------|
| `stock-fetch <TICKER>...` | Fetch and persist market data (Layer 1 only). |
| `stock-fetch --universe sp500` | Fetch a whole universe (`sp500`, `nasdaq100`, `klci`). |
| `stock-analysis <TICKER>` | Run the full four-layer pipeline for one ticker. |
| `stock-analysis-backtest` | Replay the pipeline over a historical date range and score it. |
| `uvicorn stock_analysis.api.app:app --reload` | Start the FastAPI job server. |
| `cd web && npm run dev` | Start the Next.js dashboard on port 3000. |

See [Usage](#usage) for full flag reference.

---

## Architecture

```
Data Ingestion --> Analyst Agents --> Debate --> Research Manager --> Synthesis
  (Layer 1)         (Layer 2)         (Layer 3)     (Layer 3.5)       (Layer 4)
                                                                          |
                            Outcome Memory <-- Portfolio Risk Gate <------+
                              (Layer 6)            (Layer 5)
```

**Layer 1 — Data Ingestion** fetches market data deterministically with no LLM involvement. Supports US equities via [yfinance](https://github.com/ranaroussi/yfinance) and Bursa/KLSE (Malaysia) — the MY fetcher resolves names to codes via `BURSA_ALIASES` and appends the `.KL` suffix. Ticker universes (S&P 500, NASDAQ 100, FBM KLCI) are pulled from Wikipedia.

**Layer 2 — Analyst Agents** run four specialist LLM agents in parallel:
- **Fundamentals** — P/E ratios, margins, debt structure, growth outlook
- **Sentiment** — News tone, social sentiment, key themes
- **Technical** — RSI, MACD, volume analysis, support/resistance levels
- **Macro/FX** — Fed policy, interest rates, FX impact, geopolitical risks

Each agent produces a structured report with a signal (strong buy → strong sell) and confidence level.

**Layer 3 — Adversarial Debate** pits a Bull researcher against a Bear researcher across multiple rounds. They build cases, rebut each other, and surface points of agreement, disagreement, and unresolved uncertainty.

**Layer 3.5 — Research Manager** rules on the debate instead of summarizing it: which side carried the argument, the load-bearing thesis, the strongest counterexample to its own ruling, falsifiable invalidation conditions, and evidence gaps (data nobody had, as opposed to data both sides read differently).

**Layer 4 — Synthesis** merges reports, debate, verdict, and prior outcomes into a briefing with an executive summary, a conviction score, and deterministic entry/stop/target levels.

Two things are deliberately *not* left to the model here. `signal_convergence` is computed from the analyst reports rather than self-reported, because it gates whether concrete levels get quoted. And a neutral view is a valid result: the research view and the decision to act are separate fields, so the model is never pushed into a direction it cannot support.

**Layer 5 — Portfolio Risk Gate** (deterministic) sizes the position from the stop distance and a risk budget, checks single-name / sector / USD exposure against your configured caps, and returns `APPROVE` / `WATCH` / `REDUCE` / `REJECT`. Position size has a stated meaning: if the stop is hit, the loss is `per_trade_risk_budget_pct` of the priced equity sleeve.

It fails conservatively on purpose. An unset cap is not a pass — it reports `cap_unconfigured` and degrades to `WATCH` rather than inventing a default, and unpriced holdings are disclosed instead of dropped from the denominator.

**Layer 6 — Outcome Memory** (deterministic) records what each resolved call actually earned, computes hit rate and conviction calibration, and feeds that track record into the next synthesis. Reads are gated on *exit* date, so a backtest can never see an outcome that had not resolved on the date being analyzed. Calibration is reported, never applied — nothing silently rescales a signal by a small-sample hit rate.

See [`architecture.md`](architecture.md) for the full diagram.

---

## Markets Supported

| Market | Status | Data Sources |
|--------|--------|-------------|
| US (NYSE, NASDAQ) | Implemented | yfinance (price, financials, news, analyst recs) |
| Malaysia (Bursa/KLSE) | Implemented | yfinance via `.KL` suffix, `BURSA_ALIASES` name→code map |

---

## Prerequisites

- Python 3.12+
- An [Anthropic API key](https://console.anthropic.com/) (`ANTHROPIC_API_KEY` env var)
- Node.js 18+ (for the web dashboard)

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

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Usage

### Fetch market data

```bash
# Fetch data for one or more tickers
stock-fetch AAPL MSFT GOOGL

# Fetch all S&P 500 tickers
stock-fetch --universe sp500
```

### Run a full analysis

```bash
# Full pipeline: data → agents → debate → synthesis
stock-analysis AAPL --market US --rounds 3 --model haiku --debate-model opus -v
```

### Portfolio-aware gating (Layer 5)

The gate reads holdings from a `personal-os` checkout. It looks for
`data/finance/portfolio.yaml` by walking up from the repo root, or you can point
it anywhere:

```bash
export STOCK_ANALYSIS_FINANCE_DIR=~/personal-os/data/finance   # portfolio.yaml + policy.yaml
export STOCK_ANALYSIS_MARKET_DIR=~/personal-os/market          # fx.yaml
```

Without those files the pipeline still runs — the gate returns `WATCH` and says
why, rather than approving a trade it could not check.

Concentration caps live in `policy.yaml` under `concentration:`. **While they are
`null`, the gate can never return `APPROVE`** — an unset cap is treated as a check
that could not be performed, not as one that passed. Set them to enable approvals:

```yaml
concentration:
  max_single_position_pct_of_equity: 20
  max_sector_pct_of_equity: 40
  max_usd_pct_of_tracked_investable_assets: 60
```

### Run backtests

```bash
stock-analysis-backtest --tickers AAPL,MSFT --start 2024-01-01 --end 2024-12-31

# Also feed realized outcomes back into Layer 6 memory. Off by default so that
# repeated backtests over the same window stay comparable.
stock-analysis-backtest --tickers AAPL --start 2024-01-01 --end 2024-12-31 \
    --record-outcomes
```

### Run backtests in the current session (no API key)

The Python process cannot call the current Claude/Codex conversation directly.
Use the two-stage session mode instead: the first command writes point-in-time
input packets without future prices; the current session writes the compact
`SessionPrediction` records; the second command runs the normal scorer and
portfolio simulation.

```bash
stock-analysis-backtest --mode session-prepare \
  --tickers AAPL,MSFT --start 2025-08-01 --end 2026-07-01 \
  --session-dir /tmp/aapl-msft-session

# Write predictions.json in the session directory, then:
stock-analysis-backtest --mode session-score \
  --session-dir /tmp/aapl-msft-session \
  --output /tmp/aapl-msft-backtest
```

Session predictions must contain `ticker`, `as_of_date`, `overall_signal`,
`conviction_score`, `signal_convergence`, and optional `agent_signals` (whose
values are exact `strong_buy`, `buy`, `neutral`, `sell`, or `strong_sell`
signals). During scoring, convergence is recomputed from the analyst signals;
the conviction score is recalibrated to the net analyst consensus, and
directional predictions that disagree with that consensus or do not clear the
deterministic conviction/convergence execution gate are scored as `neutral`.
Optional `agent_confidences` can provide `high`, `medium`, or `low` weights.
Session packets also declare point-in-time evidence availability; when dated
news/recommendations or macro data are unavailable, scoring forces those
analysts to `neutral` with `low` confidence instead of trusting unsupported
directional output.

### Web dashboard

```bash
cd web
npm install
npm run dev
# → http://localhost:3000
```

---

## Project Structure

```
src/stock_analysis/
├── models/              # Pydantic data models
│   ├── market_data.py   # TickerData, PriceBar, FinancialStatements
│   ├── agent_reports.py # FundamentalsReport, SentimentReport, TechnicalReport, MacroFXReport
│   ├── debate.py        # DebateArgument, DebateRound, DebateResult
│   └── synthesis.py     # Briefing, ConvictionScore, TradeDecision, PortfolioGateResult
├── data/                # Layer 1 — data fetching and storage
│   ├── fetcher_base.py  # Abstract BaseFetcher interface
│   ├── us_market.py     # USMarketFetcher (yfinance)
│   ├── my_market.py     # MYMarketFetcher (Bursa/KLSE, BURSA_ALIASES)
│   ├── technicals.py    # Technical indicator calculations
│   ├── universe.py      # Ticker universe loaders (S&P 500, NASDAQ 100, FBM KLCI)
│   └── store.py         # DataStore — flat per-ticker JSON persistence
├── agents/              # Layer 2 — specialist analyst agents
│   ├── base.py          # BaseAnalystAgent
│   ├── fundamentals.py
│   ├── sentiment.py
│   ├── technical.py
│   └── macro.py
├── debate/              # Layer 3 — adversarial bull/bear debate
│   └── engine.py        # DebateEngine
├── synthesis/           # Layer 4 — synthesis and risk
│   ├── synthesizer.py   # SynthesizerAgent
│   └── risk_checker.py  # RiskChecker
├── backtest/            # Historical backtesting
│   ├── runner.py        # Backtester
│   ├── scorer.py        # Hit rate / accuracy scoring
│   ├── portfolio.py     # Portfolio-level simulation
│   └── fetcher.py       # Historical data helper
├── api/                 # FastAPI REST endpoints
│   └── app.py           # POST /analyze/{ticker}, GET /status/{job_id}, GET /results/{ticker}
├── config.py            # Settings (models, debate rounds, data dir)
├── orchestrator.py      # AnalysisPipeline — chains all four layers
├── fetch.py             # stock-fetch CLI entry point
└── main.py              # stock-analysis CLI entry point

pipeline.json            # Canonical pipeline shape — feeds /about + architecture.md
scripts/
└── sync_architecture.py # Regenerates the mermaid block from pipeline.json

web/                     # Next.js dashboard
├── app/
│   ├── page.tsx         # Screener — one sortable row per watchlist ticker
│   ├── about/           # Pipeline flowchart (SVG from pipeline.json) + glossary
│   ├── dashboard/       # Redirect to / (the screener moved there)
│   └── [ticker]/        # Per-ticker analysis view
├── lib/
│   ├── data.ts          # Reads data/<TICKER>/*.json into TickerSummary rows
│   ├── watchlist.ts     # Parses tickers.txt incl. #group / #theme markers
│   ├── screener.ts      # Column defs, sorting, at-entry / stale predicates
│   └── pipeline.ts      # Loads pipeline.json + computes the flowchart layout
└── components/
    ├── briefing/        # Conviction meter, decision card, analyst/debate sections
    ├── chart/           # Price chart
    ├── ticker-list/     # Screener table, cards, filters, star/watchlist
    └── shared/          # Data-status strip and other UI primitives
```

Data is stored **flat per ticker**, overwritten on each run:

```
data/
└── AAPL/
    ├── price_history.csv      # full OHLCV history, merged on each fetch
    ├── fundamentals.json      # TickerInfo + financials + news snapshot
    ├── technicals.json        # computed indicators (no LLM)
    ├── analyst_reports.json
    ├── debate_result.json
    ├── research_verdict.json  # Layer 3.5 adjudication
    ├── briefing.json
    ├── outcomes.jsonl         # Layer 6 append-only outcome log
    └── calibration.json       # Layer 6 computed track record
```

The dated `data/<TICKER>/<DATE>/` layout is a backtest-only fallback, used when a
`for_date` is passed. `DataStore`'s docstring is the authoritative reference.

---

## Development

`pipeline.json` at the repo root is the single source of truth for the pipeline's shape.
The `/about` page renders it as an SVG flowchart, and `scripts/sync_architecture.py`
renders it as the mermaid block in [`architecture.md`](architecture.md) — so edit
`pipeline.json`, never the diagram:

```bash
python scripts/sync_architecture.py           # rewrite architecture.md
python scripts/sync_architecture.py --check   # exit 1 if out of date (for CI)
```

```bash
# Lint
ruff check src/

# Format
ruff format src/

# Run API server
uvicorn stock_analysis.api.app:app --reload

# Tests
pytest
pytest tests/path/to/test_file.py::test_name   # single test
```

---

## Tech Stack

- **LLM orchestration**: [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) (Haiku / Sonnet / Opus)
- **Data models**: [Pydantic](https://docs.pydantic.dev/) v2
- **Market data**: [yfinance](https://github.com/ranaroussi/yfinance)
- **API**: [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **Web dashboard**: [Next.js](https://nextjs.org/) + [Tailwind CSS](https://tailwindcss.com/)
- **HTTP client**: [httpx](https://www.python-httpx.org/)

---

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This tool is for informational and educational purposes only. It is not financial advice. Always do your own research before making investment decisions.
