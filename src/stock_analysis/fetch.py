from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from stock_analysis.config import Settings
from stock_analysis.data.my_market import MYMarketFetcher
from stock_analysis.data.store import DataStore
from stock_analysis.data.technicals import compute_technicals
from stock_analysis.data.universe import UNIVERSE_LOADERS, resolve_universe
from stock_analysis.data.us_market import USMarketFetcher

logger = logging.getLogger(__name__)


def _parse_tickers(lines: list[str]) -> list[tuple[str, str]]:
    """Return list of (ticker, market) from tickers.txt lines.

    Lines may be bare tickers (US assumed), prefixed with MY: for Bursa,
    or @universe-name directives (e.g. @us-major, @my-klci) which expand
    to the constituent list.
    """
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            pairs = resolve_universe(line)
        elif line.upper().startswith("MY:"):
            pairs = [(line[3:].upper(), "MY")]
        else:
            pairs = [(line.upper(), "US")]
        for pair in pairs:
            if pair not in seen:
                seen.add(pair)
                result.append(pair)
    return result


def cli():
    parser = argparse.ArgumentParser(
        description="Layer 1 only: fetch market data and save to data/ (no LLM)."
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        help=(
            "Ticker symbols, e.g. AAPL MSFT MY:MAYBANK, or @universe "
            "(e.g. @us-major, @my-klci); omit to read from --from-file"
        ),
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
    parser.add_argument(
        "--universe",
        action="append",
        default=[],
        choices=sorted(UNIVERSE_LOADERS),
        help="Expand a named universe; repeatable (e.g. --universe us-major --universe my-klci)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _extend(new_pairs: list[tuple[str, str]]) -> None:
        for p in new_pairs:
            if p not in seen:
                seen.add(p)
                pairs.append(p)

    for name in args.universe:
        _extend(resolve_universe(name))

    if args.tickers:
        for raw in args.tickers:
            token = raw.strip()
            if not token:
                continue
            if token.startswith("@"):
                _extend(resolve_universe(token))
            elif token.upper().startswith("MY:"):
                _extend([(token[3:].upper(), "MY")])
            elif ":" in token:
                _extend(_parse_tickers([token]))
            else:
                _extend([(token.upper(), args.market)])
    elif not args.universe:
        ticker_file = Path(args.from_file)
        if not ticker_file.exists():
            print(f"ERR no tickers given and {ticker_file} not found", file=sys.stderr)
            sys.exit(1)
        _extend(_parse_tickers(ticker_file.read_text().splitlines()))
        if not pairs:
            print(f"ERR {ticker_file} is empty", file=sys.stderr)
            sys.exit(1)

    settings = Settings()
    store = DataStore(settings.data_dir)
    fetchers = {
        "US": USMarketFetcher(period=settings.price_history_period),
        "MY": MYMarketFetcher(period=settings.price_history_period),
    }

    total = len(pairs)
    print(f"Fetching {total} tickers ({sum(1 for _, m in pairs if m == 'US')} US, "
          f"{sum(1 for _, m in pairs if m == 'MY')} MY)")

    failures: list[str] = []
    for i, (ticker, market) in enumerate(pairs, 1):
        try:
            data = fetchers[market].fetch(ticker)
            symbol = data.info.symbol
            store.save_market_data(symbol, data)  # → price_history.csv + fundamentals.json
            snapshot = compute_technicals(symbol, data.price_history)
            store.save_technicals(symbol, snapshot)
            print(
                f"[{i}/{total}] OK  {symbol} -> data/{symbol}/  "
                f"({len(data.price_history)} bars, "
                f"RSI={snapshot.rsi_14}, "
                f"MACD={'▲' if (snapshot.macd_histogram or 0) > 0 else '▼'})"
            )
        except Exception as e:
            failures.append(ticker)
            print(f"[{i}/{total}] ERR {ticker}: {e}", file=sys.stderr)

    if failures:
        print(f"\n{len(failures)}/{total} failed: {', '.join(failures[:20])}"
              f"{' ...' if len(failures) > 20 else ''}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
