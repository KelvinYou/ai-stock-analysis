from __future__ import annotations

import argparse
import logging
import sys

from stock_analysis.config import Settings
from stock_analysis.data.my_market import MYMarketFetcher
from stock_analysis.data.store import DataStore
from stock_analysis.data.us_market import USMarketFetcher

logger = logging.getLogger(__name__)


def cli():
    parser = argparse.ArgumentParser(
        description="Layer 1 only: fetch market data and save to data/ (no LLM)."
    )
    parser.add_argument("tickers", nargs="+", help="Ticker symbols, e.g. AAPL MSFT NVDA")
    parser.add_argument(
        "--market",
        choices=["US", "MY"],
        default="US",
        help="Market: US (default) or MY (Bursa Malaysia)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    settings = Settings()
    store = DataStore(settings.data_dir)
    fetcher = (
        MYMarketFetcher(period=settings.price_history_period)
        if args.market.upper() == "MY"
        else USMarketFetcher(period=settings.price_history_period)
    )

    failures: list[str] = []
    for ticker in args.tickers:
        symbol = ticker.upper()
        try:
            data = fetcher.fetch(symbol)
            path = store.save_market_data(symbol, data)
            print(f"OK  {symbol} -> {path} ({len(data.price_history)} bars)")
        except Exception as e:
            failures.append(symbol)
            print(f"ERR {symbol}: {e}", file=sys.stderr)

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    cli()
