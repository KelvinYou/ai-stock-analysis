from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from stock_analysis.config import Settings
from stock_analysis.data.my_market import MYMarketFetcher
from stock_analysis.data.store import DataStore
from stock_analysis.data.technicals import compute_technicals
from stock_analysis.data.us_market import USMarketFetcher

logger = logging.getLogger(__name__)


def _parse_tickers(lines: list[str]) -> list[tuple[str, str]]:
    """Return list of (ticker, market) from tickers.txt lines.

    Lines may be bare tickers (US assumed) or prefixed with MY: for Bursa.
    """
    result = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("MY:"):
            result.append((line[3:].upper(), "MY"))
        else:
            result.append((line.upper(), "US"))
    return result


def cli():
    parser = argparse.ArgumentParser(
        description="Layer 1 only: fetch market data and save to data/ (no LLM)."
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Ticker symbols, e.g. AAPL MSFT MY:MAYBANK (omit to read from --from-file)",
    )
    parser.add_argument(
        "--from-file",
        metavar="FILE",
        default="tickers.txt",
        help="Read tickers from a text file, one per line (default: tickers.txt)",
    )
    parser.add_argument(
        "--market",
        choices=["US", "MY"],
        default="US",
        help="Default market for bare tickers passed as CLI args (default: US)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    if args.tickers:
        pairs = _parse_tickers(args.tickers)
        # CLI args without MY: prefix use --market
        pairs = [
            (t, m if ":" in raw else args.market)
            for (t, m), raw in zip(pairs, args.tickers)
        ]
    else:
        ticker_file = Path(args.from_file)
        if not ticker_file.exists():
            print(f"ERR no tickers given and {ticker_file} not found", file=sys.stderr)
            sys.exit(1)
        pairs = _parse_tickers(ticker_file.read_text().splitlines())
        if not pairs:
            print(f"ERR {ticker_file} is empty", file=sys.stderr)
            sys.exit(1)

    settings = Settings()
    store = DataStore(settings.data_dir)
    fetchers = {
        "US": USMarketFetcher(period=settings.price_history_period),
        "MY": MYMarketFetcher(period=settings.price_history_period),
    }

    failures: list[str] = []
    for ticker, market in pairs:
        try:
            data = fetchers[market].fetch(ticker)
            symbol = data.info.symbol
            store.save_market_data(symbol, data)  # → price_history.csv + fundamentals.json
            snapshot = compute_technicals(symbol, data.price_history)
            store.save_technicals(symbol, snapshot)
            print(
                f"OK  {symbol} -> data/{symbol}/  "
                f"({len(data.price_history)} bars, "
                f"RSI={snapshot.rsi_14}, "
                f"MACD={'▲' if (snapshot.macd_histogram or 0) > 0 else '▼'})"
            )
        except Exception as e:
            failures.append(ticker)
            print(f"ERR {ticker}: {e}", file=sys.stderr)

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    cli()
