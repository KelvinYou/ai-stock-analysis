from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from stock_analysis.models.market_data import TickerData


def has_splits_since(stock, since: date) -> bool:
    """True if the yfinance Ticker has any split on/after ``since``.

    yfinance returns split/dividend-adjusted closes, so a split invalidates
    previously stored historical bars — callers use this to decide whether
    to fall back from an incremental to a full refetch.
    """
    try:
        splits = stock.splits
    except Exception:
        return False
    if splits is None or splits.empty:
        return False
    return any(idx.date() >= since for idx in splits.index)


class BaseFetcher(ABC):
    """Abstract base for all market data fetchers."""

    @abstractmethod
    def fetch(self, ticker: str, start_date: date | None = None) -> TickerData:
        """Fetch market data.

        When ``start_date`` is set, price history is limited to bars on/after that date
        (incremental refresh). Fundamentals/news/recommendations always reflect the
        latest snapshot regardless of start_date.
        """
        ...

    def resolve_symbol(self, ticker: str) -> str:
        """Return the on-disk storage symbol for a ticker, without hitting the network."""
        return ticker.upper().strip()
