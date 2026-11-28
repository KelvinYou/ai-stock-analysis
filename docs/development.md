# Development

Paths and commands are relative to the repository root. `pyproject.toml` owns Python dependencies and CLI entry points.

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

Install the optional filing embedder with `pip install -e ".[rag]"`; retrieval without it remains BM25-only. These CLI examples can call external services or paid models; documentation validation does not require running them.

## Data refresh schedule

`.github/workflows/fetch.yml` runs `stock-fetch` once per trading day (Tuesday–Saturday 00:30 UTC, after both the US and Bursa closes) and commits `data/` as `data: fetch <newest bar>`. Fetches are incremental. A split or dividend on or after a ticker's newest stored bar forces a full refetch of that ticker, because yfinance adjusts every earlier close; a full resync of all tickers runs on the 1st of each month as a backstop.

## Releases

`hatch-vcs` derives the package version from the latest `vX.Y.Z` tag; untagged commits report a development version such as `0.2.1.dev3+g1a2b3c4`. Tags are created by hand on `main`; data refreshes never change the version.

| Bump | When |
|---|---|
| Minor (`0.X.0`) | A public contract changes (`/api/v1`, `contracts/`, `web/data/momentum.json`, CLI flags), or a scoring, strategy or backtest rule changes so that results are not comparable with the previous version |
| Patch (`0.x.Y`) | Bug fixes and internal changes with comparable results |
| None | `data:`, documentation-only and submodule-pointer commits |

To release, with [git-cliff](https://git-cliff.org/) installed:

1. `git-cliff --tag vX.Y.Z -o CHANGELOG.md` regenerates the changelog from conventional commits (`cliff.toml` skips `data:`, merges and CI chores).
2. Under the new version heading, add a `### Results comparability` section stating whether backtest and pipeline results from the previous version can be compared with this one, and why.
3. Commit as `chore(release): vX.Y.Z`, then `git tag -a vX.Y.Z -m "vX.Y.Z"` on that commit.
4. Push the commit first, then the tag. `.github/workflows/release.yml` publishes the version's `CHANGELOG.md` section as the GitHub Release and fails if that section is missing.

The fetch workflow pushes to `main` daily. If a push needs a rebase, the commit hash changes, so create the tag after the release commit has reached `origin/main`.
