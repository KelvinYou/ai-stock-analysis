from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import yfinance as yf

from stock_analysis.data.fetcher_base import BaseFetcher
from stock_analysis.data.my_market import BURSA_ALIASES
from stock_analysis.models.market_data import (
    FinancialStatements,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)


class BacktestFetcher(BaseFetcher):
    """Point-in-time fetcher that produces TickerData *as if* on a past date.

    Truncates price history strictly to `as_of_date`, filters financial
    statements to those whose fiscal period ended at least `financial_lag_days`
    before `as_of_date` (a coarse proxy for filing availability), and drops
    news and analyst recommendations — yfinance returns current ones, which
    leaks the future.
    """

    def __init__(
        self,
        as_of_date: date,
        market: str = "US",
        lookback_days: int = 365,
        financial_lag_days: int = 45,
    ):
        self.as_of_date = as_of_date
        self.market = market.upper()
        self.lookback_days = lookback_days
        self.financial_lag_days = financial_lag_days

    def fetch(self, ticker: str) -> TickerData:
        yf_ticker = self._resolve_ticker(ticker)
        stock = yf.Ticker(yf_ticker)

        price_history = self._fetch_price_history(stock)
        if not price_history:
            raise RuntimeError(
                f"No price history for {ticker} on or before {self.as_of_date}"
            )

        financials = self._extract_financials(stock)
        ticker_info = self._build_info(ticker, stock, price_history, financials)

        return TickerData(
            info=ticker_info,
            price_history=price_history,
            financials=financials,
            analyst_recommendations=[],
            news_headlines=[],
            fetched_at=datetime.combine(self.as_of_date, time()),
        )

    # ------------------------------------------------------------------
    # price history
    # ------------------------------------------------------------------
    def _fetch_price_history(self, stock: yf.Ticker) -> list[PriceBar]:
        start = self.as_of_date - timedelta(days=self.lookback_days + 30)
        end = self.as_of_date + timedelta(days=1)
        hist = stock.history(start=start.isoformat(), end=end.isoformat())
        if hist.empty:
            return []

        # Strict truncation: keep only bars on or before as_of_date.
        # yfinance history is inclusive on start, exclusive on end.
        hist = hist[hist.index.date <= self.as_of_date]

        return [
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

    # ------------------------------------------------------------------
    # financials — pick the latest statement whose fiscal period end
    # is at least `financial_lag_days` before as_of_date
    # ------------------------------------------------------------------
    def _extract_financials(self, stock: yf.Ticker) -> FinancialStatements | None:
        try:
            inc = stock.quarterly_income_stmt
            bal = stock.quarterly_balance_sheet
            cf = stock.quarterly_cashflow
        except Exception:
            return None

        if inc is None or inc.empty:
            # Fall back to annual if quarterly missing
            try:
                inc = stock.income_stmt
                bal = stock.balance_sheet
                cf = stock.cashflow
            except Exception:
                return None
        if inc is None or inc.empty:
            return None

        col = self._pick_statement_column(inc)
        if col is None:
            return None

        latest_inc = inc[col] if col in inc.columns else None
        latest_bal = (
            bal[col] if bal is not None and not bal.empty and col in bal.columns else {}
        )
        latest_cf = (
            cf[col] if cf is not None and not cf.empty and col in cf.columns else {}
        )
        if latest_inc is None:
            return None

        revenue = self._safe_get(latest_inc, "Total Revenue")
        net_income = self._safe_get(latest_inc, "Net Income")
        gross_profit = self._safe_get(latest_inc, "Gross Profit")
        operating_income = self._safe_get(latest_inc, "Operating Income")

        return FinancialStatements(
            revenue=revenue,
            net_income=net_income,
            total_debt=self._safe_get(latest_bal, "Total Debt"),
            total_equity=self._safe_get(latest_bal, "Stockholders Equity"),
            free_cash_flow=self._safe_get(latest_cf, "Free Cash Flow"),
            gross_margin=(gross_profit / revenue) if revenue and gross_profit else None,
            operating_margin=(
                operating_income / revenue if revenue and operating_income else None
            ),
            net_margin=(net_income / revenue) if revenue and net_income else None,
        )

    def _pick_statement_column(self, df: pd.DataFrame):
        cutoff = self.as_of_date - timedelta(days=self.financial_lag_days)
        eligible = [c for c in df.columns if self._to_date(c) and self._to_date(c) <= cutoff]
        if not eligible:
            return None
        return max(eligible, key=lambda c: self._to_date(c))

    @staticmethod
    def _to_date(c) -> date | None:
        if isinstance(c, datetime):
            return c.date()
        if isinstance(c, date):
            return c
        try:
            return pd.Timestamp(c).date()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # info — recomputed from truncated price history (no live lookup)
    # ------------------------------------------------------------------
    def _build_info(
        self,
        display_symbol: str,
        stock: yf.Ticker,
        price_history: list[PriceBar],
        financials: FinancialStatements | None,
    ) -> TickerInfo:
        # Static metadata we allow to leak (sector/industry/name/currency)
        # — these are stable and don't encode future information.
        try:
            raw_info = stock.info
        except Exception:
            raw_info = {}

        # Truncated 52-week high/low from price history
        last_year = [
            p for p in price_history
            if (self.as_of_date - p.date).days <= 365
        ]
        hi = max((p.high for p in last_year), default=None)
        lo = min((p.low for p in last_year), default=None)
        last_close = price_history[-1].close

        # Rough PE: last_close * shares_outstanding / net_income (if both available)
        pe_ratio: float | None = None
        market_cap: float | None = None
        shares = raw_info.get("sharesOutstanding") or raw_info.get("impliedSharesOutstanding")
        if shares and financials and financials.net_income:
            try:
                market_cap = float(shares) * last_close
                if financials.net_income > 0:
                    pe_ratio = market_cap / financials.net_income
            except Exception:
                pass

        # Normalize display symbol for MY
        sym = display_symbol.upper().strip()
        if self.market == "MY" and sym.endswith(".KL"):
            sym = sym[:-3]

        market_enum = Market.MY if self.market == "MY" else Market.US
        currency = raw_info.get("currency", "MYR" if market_enum == Market.MY else "USD")

        return TickerInfo(
            symbol=sym,
            name=raw_info.get("shortName", raw_info.get("longName", sym)),
            sector=raw_info.get("sector"),
            industry=raw_info.get("industry"),
            market=market_enum,
            currency=currency,
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            forward_pe=None,  # requires forward estimates — would leak
            dividend_yield=None,  # point-in-time unknown
            beta=None,  # computed against current; regenerate if needed
            fifty_two_week_high=hi,
            fifty_two_week_low=lo,
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _resolve_ticker(self, ticker: str) -> str:
        t = ticker.upper().strip()
        if self.market != "MY":
            return t
        if t.endswith(".KL"):
            return t
        if t in BURSA_ALIASES:
            return f"{BURSA_ALIASES[t]}.KL"
        return f"{t}.KL"

    @staticmethod
    def _safe_get(series, key: str) -> float | None:
        try:
            if hasattr(series, "get"):
                val = series.get(key)
            else:
                val = None
            if val is not None and str(val) != "nan":
                return float(val)
        except (KeyError, TypeError, ValueError):
            pass
        return None
