from __future__ import annotations

from datetime import datetime

import yfinance as yf

from stock_analysis.models.market_data import (
    FinancialStatements,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)

from .fetcher_base import BaseFetcher


class USMarketFetcher(BaseFetcher):
    """Fetches US market data via yfinance."""

    def __init__(self, period: str = "10y"):
        self.period = period

    def fetch(self, ticker: str) -> TickerData:
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

        hist = stock.history(period=self.period)
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
