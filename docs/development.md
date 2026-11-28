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
