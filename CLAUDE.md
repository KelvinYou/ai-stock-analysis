# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install
pip install -e ".[dev]"

# Lint / format
ruff check src/
ruff format src/

# Test
pytest
pytest tests/path/to/test_file.py::test_name   # single test

# Run CLI
stock-analysis AAPL --market US --rounds 3 --model haiku --debate-model opus -v
stock-analysis-backtest --tickers AAPL,MSFT --start 2024-01-01 --end 2024-12-31

# Run API
uvicorn stock_analysis.api.app:app --reload
```

## Architecture

This is a 4-layer multi-agent pipeline for AI-driven stock analysis. Each layer feeds into the next and outputs structured Pydantic models persisted as JSON under `data/<TICKER>/<DATE>/`.

### Layer 1 — Data Ingestion (`data/`)
Deterministic, no LLM. `USMarketFetcher` uses yfinance to produce a `TickerData` object (price history, financials, analyst recs, news). `DataStore` persists results to `data/<TICKER>/<DATE>/market_data.json`.

### Layer 2 — Analyst Agents (`agents/`)
Four specialist agents run **concurrently** (each inherits `BaseAnalystAgent`): Fundamentals, Sentiment, Technical, MacroFX. Each uses the Claude Agent SDK with custom MCP tools that expose `TickerData` as structured inputs, and returns a typed `*Report` with a `Signal` (strong_buy → strong_sell) and `Confidence`.

Default model: Haiku (`quick_think_model`).

### Layer 3 — Adversarial Debate (`debate/engine.py`)
`DebateEngine` runs N sequential rounds (default 3) of Bull vs. Bear researchers using the Layer 2 reports as source facts. Output is a `DebateResult` with both cases, points of agreement/disagreement, and unresolved uncertainties.

Default model: Opus (`deep_think_model`).

### Layer 4 — Synthesis & Risk (`synthesis/`)
`SynthesizerAgent` merges analyst reports + debate into a `Briefing`. `RiskChecker` adds position sizing and drawdown scenarios. The `Briefing` contains an overall `Signal`, a `ConvictionScore` (−1.0 to +1.0), and a `signal_convergence` metric (0 = agents disagree, 1 = full agreement).

Default model: Sonnet (`synthesis_model`).

### Orchestration
`AnalysisPipeline` in `orchestrator.py` chains all four layers. Configuration lives in `config.py` as a Pydantic `Settings` object (models, debate rounds, data directory, price history period).

### Agent Pattern
Every agent subclasses `BaseAnalystAgent` and implements three methods: `system_prompt()`, `build_tools()` (MCP tool definitions over `TickerData`), and `output_model()` (the Pydantic response type). LLM calls go through `query_with_retry()` in `_query_retry.py`.

### API (WIP)
`api/app.py` exposes `POST /analyze/{ticker}` (async job), `GET /status/{job_id}`, and `GET /results/{ticker}` via FastAPI.

### Backtesting (`backtest/`)
`Backtester` reruns the full pipeline across historical date ranges. `Scorer` computes hit rate and accuracy against actual price movement over a configurable holding horizon.
