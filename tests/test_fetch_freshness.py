"""Fetch-layer freshness: a successful call is not evidence the data moved.

`data: fetch 2026-09-09 (33/33 ok)` was committed against a META CSV whose
newest bar was 2026-09-08. Both halves of that were wrong: the count only ever
meant "the HTTP round-trip worked", and the date came from the wall clock.
"""

from __future__ import annotations

from datetime import date

from stock_analysis.fetch import _stale_symbols


def test_no_results_has_no_reference_bar() -> None:
    assert _stale_symbols({}) == ([], None)


def test_a_ticker_trailing_the_run_is_reported_stale() -> None:
    as_of = {
        "AAPL": date(2026, 9, 9),
        "MSFT": date(2026, 9, 9),
        "META": date(2026, 9, 2),
    }

    stale, freshest = _stale_symbols(as_of)

    assert freshest == date(2026, 9, 9)
    assert stale == [("META", date(2026, 9, 2))]


def test_a_weekend_plus_holiday_gap_is_not_stale() -> None:
    """Fri close + Sat/Sun + Mon holiday = 3 days behind a Tuesday bar."""
    as_of = {
        "AAPL": date(2026, 9, 8),
        "MY:1155": date(2026, 9, 5),
    }

    stale, freshest = _stale_symbols(as_of)

    assert freshest == date(2026, 9, 8)
    assert stale == []


def test_stale_tickers_are_ordered_oldest_first() -> None:
    as_of = {
        "AAPL": date(2026, 9, 9),
        "ONDS": date(2026, 9, 1),
        "SMR": date(2026, 8, 20),
    }

    stale, _ = _stale_symbols(as_of)

    assert [symbol for symbol, _ in stale] == ["SMR", "ONDS"]


def test_incremental_window_reopens_the_newest_stored_bar(monkeypatch) -> None:
    """The last stored bar is re-requested so a revised bar can overwrite it.

    Asking for `last + 1 day` froze the newest bar at whatever values it was
    first seen with — which is how a provisional intraday bar became permanent.
    """
    from stock_analysis import fetch as fetch_module

    requested: dict[str, date | None] = {}

    class _Fetcher:
        def resolve_symbol(self, ticker: str) -> str:
            return ticker.upper()

        def fetch(self, ticker: str, start_date: date | None = None):
            requested["start_date"] = start_date
            raise RuntimeError("stop here — only the window matters")

    class _Store:
        def last_price_bar_date(self, symbol: str) -> date:
            return date(2026, 9, 8)

    ok, name, newest = fetch_module._fetch_one(
        1, 1, "META", "US", {"US": _Fetcher()}, _Store(), full=False
    )

    assert requested["start_date"] == date(2026, 9, 8)
    assert (ok, name, newest) == (False, "META", None)
