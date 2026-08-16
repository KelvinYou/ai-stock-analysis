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

`pipeline.json` (repo root) is the single source of truth for the pipeline's shape.
`web/app/about` renders it as an SVG flowchart; `scripts/sync_architecture.py` renders
it as the mermaid block in `architecture.md`. Change the pipeline → edit `pipeline.json`
and run the script; never hand-edit the mermaid or the diagram component.

This is a multi-agent pipeline for AI-driven stock research: four analyst layers,
a debate adjudicator, deterministic risk levels, and an outcome-memory loop. It
emits structured research models persisted as JSON; portfolio decisions belong
to the consuming application.

Storage is a **flat per-ticker directory** — `data/AAPL/{price_history.csv,
fundamentals.json, technicals.json, analyst_reports.json, debate_result.json,
research_verdict.json, briefing.json, outcomes.jsonl, calibration.json}`. The
dated `data/<TICKER>/<DATE>/` layout is a backtest-only fallback used when
`for_date` is passed; there is no `market_data.json`. See the docstring on
`DataStore` for the authoritative layout.

### Layer 1 — Data Ingestion (`data/`)
Deterministic, no LLM. `USMarketFetcher` uses yfinance to produce a `TickerData` object (price history, financials, analyst recs, news). `MYMarketFetcher` covers Bursa/KLSE, resolving names to codes via `BURSA_ALIASES` and appending `.KL`. `DataStore` persists the flat layout above.

### Layer 2 — Analyst Agents (`agents/`)
Four specialist agents run **concurrently** (each inherits `BaseAnalystAgent`): Fundamentals, Sentiment, Technical, MacroFX. Each uses the Claude Agent SDK with custom MCP tools that expose `TickerData` as structured inputs, and returns a typed `*Report` with a `Signal` (strong_buy → strong_sell) and `Confidence`.

Default model: Haiku (`quick_think_model`).

### Layer 3 — Adversarial Debate (`debate/engine.py`)
`DebateEngine` runs N sequential rounds (default 3) of Bull vs. Bear researchers using the Layer 2 reports as source facts. Output is a `DebateResult` with both cases, points of agreement/disagreement, and unresolved uncertainties.

Default model: Opus (`deep_think_model`).

### Layer 3.5 — Research Manager (`debate/research_manager.py`)
`ResearchManager` adjudicates the debate rather than summarizing it: `winning_side`, `thesis`, the strongest counterexample to its own ruling, falsifiable `invalidation_conditions`, and `evidence_gaps` (data nobody had, as distinct from data both sides dispute). Advisory — it shapes the briefing's prose but cannot move `signal_convergence`.

Default model: Sonnet (`research_manager_model`). Disable with `enable_research_manager=False`.

### Layer 4 — Synthesis (`synthesis/synthesizer.py`)
`SynthesizerAgent` merges analyst reports + debate + verdict + outcome memory into a `Briefing`, then `RiskChecker` attaches deterministic entry/stop/target levels and drawdown scenarios.

Two invariants here, both load-bearing:

- **`signal_convergence` is computed, not authored.** It is a deterministic
  confidence-weighted function of the four analyst reports
  (`compute_signal_convergence`); the LLM's self-reported value is discarded.
  It gates whether RiskChecker will quote precise levels, so an LLM-authored
  value would let the model talk itself into a trade setup.
- **Neutral is a valid output.** `overall_signal=neutral` is a complete research
  result. Do not add prompt pressure to force a trade direction.

Default model: Sonnet (`synthesis_model`).

### Supporting context — Outcome Memory (`memory/outcomes.py`)
Deterministic, no LLM. Appends resolved calls to `outcomes.jsonl`, computes hit rate / conviction calibration, and injects the track record into the next synthesis prompt.

**The leakage guard is the critical invariant.** `OutcomeRecord.visible_on()` admits a record only when its *exit* date precedes the analysis date — gating on entry date would feed backtests outcomes that had not happened yet, silently turning every backtest metric into future knowledge. Calibration is reported, never applied: nothing rescales conviction by a small-sample hit rate.

Backfill from a backtest with `stock-analysis-backtest --record-outcomes` (off by default, so repeated backtests stay comparable).

### Orchestration
`AnalysisPipeline` in `orchestrator.py` chains every layer. Configuration lives in `config.py` as a Pydantic `Settings` object (models, debate rounds, data directory, price history period, and optional research enrichments).

### Agent Pattern
Every agent subclasses `BaseAnalystAgent` and implements three methods: `system_prompt()`, `build_tools()` (MCP tool definitions over `TickerData`), and `output_model()` (the Pydantic response type). LLM calls go through `query_with_retry()` in `_query_retry.py`.

### API (WIP)
`api/app.py` exposes `POST /analyze/{ticker}` (async job), `GET /status/{job_id}`, and `GET /results/{ticker}` via FastAPI.

### Backtesting (`backtest/`)
`Backtester` reruns the full pipeline across historical date ranges. `Scorer` computes hit rate and accuracy against actual price movement over a configurable holding horizon.

**Point estimates never ship alone.** `stats.py` implements the small-sample machinery from scratch (no scipy — the normal approximations a light dependency would buy are wrong in exactly the regime that matters here): Wilson intervals for hit rates, an exact Student-t tail for p-values, Fisher-z intervals for the information coefficient, and PSR/DSR for Sharpe.

Three invariants to preserve when touching this module:

- **Significance is computed on `effective_n`, not the trial count.** Overlapping holding windows are not independent observations — weekly as-of dates at a 30-day horizon collapse 5 nominal trials to 1. `stats.effective_sample_size` applies a per-trial simplification of López de Prado's uniqueness weighting. It does not model cross-sectional dependence, so it is an upper bound on independence.
- **Gross and net are reported side by side.** `--cost-bps` charges a round trip to directional trials only. Costs are never folded silently into the headline number.
- **The strategy table is a search.** `portfolio.simulate` scores six strategies; the winner's Sharpe is an order statistic, so it carries a Deflated Sharpe against the expected best-of-N under the null. Adding strategies to that comparison raises the bar the winner must clear — which is the correct behaviour, not a regression.
