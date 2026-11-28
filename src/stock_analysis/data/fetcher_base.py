from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date

from stock_analysis.data.bars import drop_invalid_bars
from stock_analysis.models.market_data import PriceBar, TickerData

logger = logging.getLogger(__name__)


def reject_unusable_bars(ticker: str, bars: list[PriceBar]) -> list[PriceBar]:
    """Drop bars whose OHLC cannot be computed on, logging what went.

    The upstream feed is the origin of the defect, so this is where it is
    named. The provisional-tail check is left to the store, which always holds
    the full history the volume baseline needs.
    """
    audit = drop_invalid_bars(bars)
    if audit.dropped:
        logger.warning(
            "%s: upstream returned %d unusable bar(s), dropped: %s",
            ticker,
            len(audit.dropped),
            "; ".join(audit.dropped),
        )
    return audit.bars


def _has_event_since(events, since: date) -> bool:
    if events is None or events.empty:
        return False
    return any(idx.date() >= since for idx in events.index)


def has_adjustments_since(stock, since: date) -> bool:
    """True if the yfinance Ticker has a split or dividend on/after ``since``.

    yfinance returns split- and dividend-adjusted closes, so either event
    rewrites every bar before its ex-date and invalidates the stored history.
    Callers use this to fall back from an incremental to a full refetch for
    that ticker alone, instead of rewriting every ticker on a fixed schedule.
    A lookup failure counts as no event; the scheduled full resync is the
    backstop for that case.
    """
    for attribute in ("splits", "dividends"):
        try:
            events = getattr(stock, attribute)
        except Exception:
            continue
        if _has_event_since(events, since):
            return True
    return False


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
        """Return the storage symbol for a ticker, without hitting the network."""
        return ticker.upper().strip()
