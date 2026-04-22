from __future__ import annotations

from datetime import date, datetime

import yfinance as yf

from stock_analysis.models.market_data import (
    FinancialStatements,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)

from .fetcher_base import BaseFetcher, has_splits_since

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
        price_history = [
            PriceBar(
                date=idx.date(),
                open=round(row["Open"], 4),
                high=round(row["High"], 4),
                low=round(row["Low"], 4),
                close=round(row["Close"], 4),
                volume=int(row["Volume"]),
            )
            for idx, row in hist.iterrows()
        ]

        financials = self._extract_financials(stock)
        news = self._extract_news(stock)
        recommendations = self._extract_recommendations(stock)

        return TickerData(
            info=ticker_info,
            price_history=price_history,
            financials=financials,
            analyst_recommendations=recommendations,
            news_headlines=news,
            fetched_at=datetime.now(),
        )

    def _extract_financials(self, stock: yf.Ticker) -> FinancialStatements | None:
        try:
            inc = stock.income_stmt
            bal = stock.balance_sheet
            cf = stock.cashflow
            if inc.empty:
                return None

            latest_inc = inc.iloc[:, 0]
            latest_bal = bal.iloc[:, 0] if not bal.empty else {}
            latest_cf = cf.iloc[:, 0] if not cf.empty else {}

            revenue = self._safe_get(latest_inc, "Total Revenue")
            net_income = self._safe_get(latest_inc, "Net Income")

            return FinancialStatements(
                revenue=revenue,
                net_income=net_income,
                total_debt=self._safe_get(latest_bal, "Total Debt"),
                total_equity=self._safe_get(latest_bal, "Stockholders Equity"),
                free_cash_flow=self._safe_get(latest_cf, "Free Cash Flow"),
                gross_margin=(
                    self._safe_get(latest_inc, "Gross Profit") / revenue
                    if revenue and self._safe_get(latest_inc, "Gross Profit")
                    else None
                ),
                operating_margin=(
                    self._safe_get(latest_inc, "Operating Income") / revenue
                    if revenue and self._safe_get(latest_inc, "Operating Income")
                    else None
                ),
                net_margin=(
                    net_income / revenue if revenue and net_income else None
                ),
            )
        except Exception:
            return None

    def _extract_news(self, stock: yf.Ticker) -> list[dict]:
        try:
            return [
                {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "publisher": item.get("publisher", ""),
                }
                for item in (stock.news or [])[:10]
            ]
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
