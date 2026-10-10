from __future__ import annotations

from datetime import UTC, date, datetime

import yfinance as yf

from stock_analysis.models.market_data import (
    FinancialStatements,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)

from .evidence import normalize_news_item
from .fetcher_base import BaseFetcher, has_splits_since, reject_unusable_bars
from .live_evidence import financial_history, plain_close, stamp_current_capture


class USMarketFetcher(BaseFetcher):
    """Fetches US market data via yfinance."""

    def __init__(self, period: str = "10y"):
        self.period = period

    def fetch(self, ticker: str, start_date: date | None = None) -> TickerData:
        stock = yf.Ticker(ticker)
        info = stock.info

        ticker_info = TickerInfo(
            symbol=ticker.upper(),
            name=info.get("shortName", info.get("longName", ticker)),
            sector=info.get("sector"),
            industry=info.get("industry"),
            market=Market.US,
            currency=info.get("currency", "USD"),
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            forward_pe=info.get("forwardPE"),
            dividend_yield=info.get("dividendYield"),
            beta=info.get("beta"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        )

        # yfinance returns split-adjusted closes, so any split since start_date
        # invalidates stored historical prices — fall back to a full refetch.
        if start_date is not None and has_splits_since(stock, start_date):
            start_date = None

        hist = (
            stock.history(start=start_date.isoformat())
            if start_date is not None
            else stock.history(period=self.period)
        )
        # yfinance intermittently returns a NaN OHLC row with a plausible
        # volume. Rejecting it here keeps it out of TickerData entirely; the
        # store re-screens the merged series for the provisional-tail case,
        # which needs a volume baseline this slice may not have.
        price_history = reject_unusable_bars(
            ticker.upper(),
            [
                PriceBar(
                    date=idx.date(),
                    open=round(row["Open"], 4),
                    high=round(row["High"], 4),
                    low=round(row["Low"], 4),
                    close=round(row["Close"], 4),
                    volume=int(row["Volume"]),
                )
                for idx, row in hist.iterrows()
            ],
        )

        captured_at = datetime.now(UTC)
        history = financial_history(stock, info, captured_at)
        news = self._extract_news(stock)
        recommendations = self._extract_recommendations(stock)
        valuation_price = plain_close(stock, ticker.upper(), ticker_info.currency, price_history, captured_at)
        captured_at = datetime.now(UTC)
        history, valuation_price = stamp_current_capture(history, valuation_price, captured_at)
        financials = history[-1] if history else None

        return TickerData(
            info=ticker_info,
            price_history=price_history,
            financials=financials,
            financial_history=history,
            valuation_price=valuation_price,
            analyst_recommendations=recommendations,
            news_headlines=news,
            fetched_at=captured_at,
            provider_capture="current",
        )

    def _extract_financials(self, stock: yf.Ticker) -> FinancialStatements | None:
        history = financial_history(stock, stock.info, datetime.now())
        return history[-1] if history else None

    def _extract_news(self, stock: yf.Ticker) -> list[dict]:
        try:
            news = []
            for item in (stock.news or [])[:10]:
                normalized = normalize_news_item(item)
                if normalized is not None:
                    news.append(normalized)
            return news
        except Exception:
            return []

    def _extract_recommendations(self, stock: yf.Ticker) -> list[dict]:
        try:
            recs = stock.recommendations
            if recs is None or recs.empty:
                return []
            recent = recs.tail(10)
            return recent.reset_index().to_dict(orient="records")
        except Exception:
            return []

    @staticmethod
    def _safe_get(series, key: str) -> float | None:
        try:
            val = series.get(key)
            if val is not None and str(val) != "nan":
                return float(val)
        except (KeyError, TypeError, ValueError):
            pass
        return None
