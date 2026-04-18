from __future__ import annotations

from abc import ABC, abstractmethod

from stock_analysis.models.market_data import TickerData


class BaseFetcher(ABC):
    """Abstract base for all market data fetchers."""

    @abstractmethod
    def fetch(self, ticker: str) -> TickerData:
        """Fetch complete market data for a ticker."""
        ...
