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

# Common Bursa Malaysia ticker aliases — map friendly names to stock codes
BURSA_ALIASES: dict[str, str] = {
    "MAYBANK": "1155",
    "PBBANK": "1295",
    "CIMB": "1023",
    "TENAGA": "5347",
    "IHH": "5225",
    "PCHEM": "5183",
    "TOPGLOVE": "7113",
    "AXIATA": "6888",
    "DIGI": "6947",
    "GENTING": "3182",
    "GENM": "4715",
    "HLBANK": "5819",
    "RHBBANK": "1066",
    "AMBANK": "1015",
    "MAXIS": "6012",
    "PETRONAS_GAS": "6033",
    "DIALOG": "7277",
    "HARTA": "5168",
    "KLK": "2445",
    "SIME": "4197",
    "MISC": "3816",
}


class MYMarketFetcher(BaseFetcher):
    """Fetches Bursa Malaysia (KLSE) data via yfinance (.KL suffix)."""

    def __init__(self, period: str = "10y"):
        self.period = period

    def _resolve_ticker(self, ticker: str) -> str:
        """Resolve a Bursa ticker to yfinance format (CODE.KL).

        Accepts: stock code (1155), name (MAYBANK), or already-suffixed (1155.KL).
        """
        t = ticker.upper().strip()
        if t.endswith(".KL"):
            return t
        if t in BURSA_ALIASES:
            return f"{BURSA_ALIASES[t]}.KL"
        return f"{t}.KL"

    def resolve_symbol(self, ticker: str) -> str:
        t = ticker.upper().strip()
        if t.endswith(".KL"):
            return t[:-3]
        return t

    def fetch(self, ticker: str, start_date: date | None = None) -> TickerData:
        yf_ticker = self._resolve_ticker(ticker)
        stock = yf.Ticker(yf_ticker)
        info = stock.info

        # Use the original user-supplied ticker as display symbol
        display_symbol = self.resolve_symbol(ticker)

        ticker_info = TickerInfo(
            symbol=display_symbol,
            name=info.get("shortName", info.get("longName", display_symbol)),
            sector=info.get("sector"),
            industry=info.get("industry"),
            market=Market.MY,
            currency=info.get("currency", "MYR"),
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            forward_pe=info.get("forwardPE"),
            dividend_yield=info.get("dividendYield"),
            beta=info.get("beta"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        )

        if start_date is not None and has_splits_since(stock, start_date):
            start_date = None

        hist = (
            stock.history(start=start_date.isoformat())
            if start_date is not None
            else stock.history(period=self.period)
        )
        # See USMarketFetcher: a NaN OHLC row from the feed is rejected before
        # it can reach TickerData, where it would void 200 bars of indicators.
        price_history = reject_unusable_bars(
            display_symbol,
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
        valuation_price = plain_close(stock, yf_ticker, ticker_info.currency, price_history, captured_at)
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
