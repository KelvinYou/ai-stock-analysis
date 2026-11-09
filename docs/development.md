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
