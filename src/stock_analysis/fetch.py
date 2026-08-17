from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

from stock_analysis.config import Settings, load_env
from stock_analysis.data.cloud import build_store
from stock_analysis.data.my_market import MYMarketFetcher
from stock_analysis.data.technicals import compute_technicals
from stock_analysis.data.universe import UNIVERSE_LOADERS, resolve_universe
from stock_analysis.data.us_market import USMarketFetcher
from stock_analysis.data.watchlist import WatchlistEntry, load_watchlist_map

logger = logging.getLogger(__name__)
_print_lock = threading.Lock()


def _fetch_one(
    idx: int,
    total: int,
    ticker: str,
    market: str,
    fetchers: dict,
    store,
    full: bool,
    watch: WatchlistEntry | None = None,
) -> tuple[bool, str]:
    """Fetch, persist, and compute technicals for a single ticker.

    Incremental by default: asks yfinance only for bars since the last stored date,
    then merges into the configured storage backend. ``full=True`` forces a full history
    refetch (used weekly to resync dividend-adjusted historical closes).

    Returns (ok, symbol_or_ticker). Output is serialized via a module-level lock.
    """
    fetcher = fetchers[market]
    start_date = None
    if not full:
        storage_symbol = fetcher.resolve_symbol(ticker)
        last = store.last_price_bar_date(storage_symbol)
        if last is not None:
            start_date = last + timedelta(days=1)

    try:
        data = fetcher.fetch(ticker, start_date=start_date)
        symbol = data.info.symbol
        merged = store.merge_market_data(symbol, data)
        snapshot = compute_technicals(symbol, merged)
        store.save_technicals(symbol, snapshot)
        # The cloud `tickers` table is what the dashboard reads for sector and
        # watchlist grouping; merge_market_data only guarantees symbol+market.
        # Without this, cloud mode renders every ticker as an ungrouped,
        # sector-less row. No-op on the local backend.
        store.upsert_ticker_metadata(
            symbol,
            market=data.info.market.value,
            name=data.info.name,
            sector=data.info.sector,
            industry=data.info.industry,
            currency=data.info.currency,
            watch_group=watch.group if watch else None,
            theme=watch.theme if watch else None,
        )
        mode = "FULL" if start_date is None else "INC "
        with _print_lock:
            print(
                f"[{idx}/{total}] OK  {symbol} {mode} +{len(data.price_history):>4} new "
                f"(total {len(merged)} bars, "
                f"RSI={snapshot.rsi_14}, "
                f"MACD={'▲' if (snapshot.macd_histogram or 0) > 0 else '▼'})",
                flush=True,
            )
        return True, symbol
    except Exception as e:
        with _print_lock:
            print(f"[{idx}/{total}] ERR {ticker}: {e}", file=sys.stderr, flush=True)
        return False, ticker


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
            try:
                pairs = resolve_universe(line)
            except Exception as e:
                print(f"WARN could not expand {line}: {e}", file=sys.stderr)
                continue
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
    load_env()
    parser = argparse.ArgumentParser(
        description="Layer 1 only: fetch market data into the configured backend (no LLM)."
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
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Parallel fetch workers (default: 8)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "Force a full history refetch instead of the default incremental append. "
            "Use weekly to resync dividend-adjusted historical closes."
        ),
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

    def _safe_resolve(name: str) -> list[tuple[str, str]]:
        try:
            return resolve_universe(name)
        except Exception as e:
            print(f"WARN could not expand {name}: {e}", file=sys.stderr)
            return []

    for name in args.universe:
        _extend(_safe_resolve(name))

    if args.tickers:
        for raw in args.tickers:
            token = raw.strip()
            if not token:
                continue
            if token.startswith("@"):
                _extend(_safe_resolve(token))
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
        print("ERR no tickers resolved (all universe expansions failed?)", file=sys.stderr)
        sys.exit(1)

    settings = Settings.from_env()
    store = build_store(settings)
    # Grouping/theme live only in tickers.txt markers, so they are read here even
    # when the tickers came from CLI args or a universe — a ticker that happens to
    # be on the hand-curated watchlist keeps its group either way.
    watch_map = load_watchlist_map(args.from_file)
    fetchers = {
        "US": USMarketFetcher(period=settings.price_history_period),
        "MY": MYMarketFetcher(period=settings.price_history_period),
    }

    total = len(pairs)
    mode_label = "full refetch" if args.full else "incremental"
    print(
        f"Fetching {total} tickers ({sum(1 for _, m in pairs if m == 'US')} US, "
        f"{sum(1 for _, m in pairs if m == 'MY')} MY) "
        f"with {max(1, args.workers)} workers [{mode_label}]"
    )

    failures: list[str] = []
    successes: list[str] = []
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futures = [
                ex.submit(
                    _fetch_one,
                    i,
                    total,
                    ticker,
                    market,
                    fetchers,
                    store,
                    args.full,
                    watch_map.get(ticker.upper()),
                )
                for i, (ticker, market) in enumerate(pairs, 1)
            ]
            for fut in as_completed(futures):
                ok, name = fut.result()
                (successes if ok else failures).append(name)
    finally:
        close = getattr(store, "close", None)
        if close:
            close()

    summary = f"Fetched {len(successes)}/{total} tickers"
    if failures:
        shown = ", ".join(failures[:20])
        more = " ..." if len(failures) > 20 else ""
        summary += f"; {len(failures)} failed: {shown}{more}"
    print(summary, file=sys.stderr)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as f:
            f.write(f"## Fetch summary\n\n- OK: {len(successes)}\n- Failed: {len(failures)}\n")
            if failures:
                f.write(f"- Failures: {', '.join(failures[:50])}\n")

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"success_count={len(successes)}\n")
            f.write(f"failure_count={len(failures)}\n")
            f.write(f"total_count={total}\n")

    # Exit non-zero only when nothing succeeded — partial failures shouldn't
    # block the workflow's commit step from saving good data.
    if not successes:
        sys.exit(1)


if __name__ == "__main__":
    cli()
