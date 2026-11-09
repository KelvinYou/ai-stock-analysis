# AI Stock Analysis — Agent Instructions

This file owns shared agent instructions. `CLAUDE.md` links here; maintain one copy.

## Read order

Use [docs/INDEX.md](docs/INDEX.md) to select the relevant topic. Before changing a pipeline layer, read its section in [the pipeline guide](docs/pipeline-guide.md) and the applicable design contract. Commands live in [the development guide](docs/development.md).

## Project and boundaries

Stock research, price-only momentum and portfolio strategy comparisons. Research output is advisory; personal holdings and portfolio decisions belong to the consuming application. Keep private personal state outside this public repository.

## Essential invariants

- `pipeline.json` owns pipeline shape. Run `python scripts/sync_architecture.py` after changing it; do not hand-edit the generated diagram in `architecture.md` or its dashboard consumer.
- Preserve data validation and completed-bar gates at ingestion, storage and technical computation.
- Preserve historical visibility boundaries for filings, input snapshots and resolved outcome memory; never expose future evidence to an analysis date.
- Deterministic code owns convergence, actionability, freshness and risk levels. Neutral results and unavailable levels are valid outputs; do not force a trade or invent missing inputs.
- Report costs, effective samples and uncertainty with backtest results; preserve comparisons and selection-bias adjustments.
- Read [the pipeline guide](docs/pipeline-guide.md) for the detailed invariants and exceptions before editing these areas.

## Commands

Run from the repository root:

- `pip install -e ".[dev]"` — install development dependencies.
- `ruff check src/` — lint.
- `ruff format src/` — format (writes files).
- `pytest` — tests; select a relevant file for focused changes.
- `python scripts/sync_architecture.py --check` — verify the generated diagram without writing.

Do not run paid research or network fetches merely to verify documentation. Model defaults and CLI entry points remain owned by `src/stock_analysis/config.py` and `pyproject.toml`.

## Documentation

Keep detailed guidance in its indexed owner under `docs/` or the existing root documents. `architecture.md` retains the generated pipeline overview; this entry point routes to it rather than copying the diagram. Preserve historical research records and distinguish proposed designs from implemented behavior.
