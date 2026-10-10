from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from stock_analysis.config import Settings
from stock_analysis.data.evidence import filter_point_in_time_news
from stock_analysis.data.fetcher_base import BaseFetcher, reject_unusable_bars
from stock_analysis.data.fundamentals import build_fundamental_context, select_financial_history
from stock_analysis.data.my_market import BURSA_ALIASES
from stock_analysis.models.market_data import (
    FinancialStatements,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)

from .replay import (
    load_fundamentals_history_replay,
    load_macro_replay,
    load_news_replay,
    load_valuation_price_replay,
)


class BacktestFetcher(BaseFetcher):
    """Point-in-time fetcher that produces TickerData *as if* on a past date.

    Truncates price history strictly to `as_of_date`, filters financial
    statements using the SEC filing date exposed by yfinance, and drops news
    and analyst recommendations — yfinance returns current ones, which leaks
    the future. If a statement period cannot be matched to a filing date, it
    is not used as point-in-time evidence.
    """

    def __init__(
        self,
        as_of_date: date,
        market: str = "US",
        lookback_days: int = 365,
        replay_dir: Path | None = None,
        news_max_age_days: int | None = None,
    ):
        self.as_of_date = as_of_date
        self.market = market.upper()
        self.lookback_days = lookback_days
        self.replay_dir = replay_dir
        self.news_max_age_days = news_max_age_days or Settings().news_max_age_days

    def fetch(self, ticker: str) -> TickerData:
        yf_ticker = self._resolve_ticker(ticker)
        stock = yf.Ticker(yf_ticker)

        price_history = self._fetch_price_history(stock, ticker)
        if not price_history:
            raise RuntimeError(
                f"No price history for {ticker} on or before {self.as_of_date}"
            )

        history = (load_fundamentals_history_replay(self.replay_dir, ticker, self.as_of_date)
                   if self.replay_dir is not None else self._extract_financial_history(stock))
        financials = history[-1] if history else None
        ticker_info = self._build_info(ticker, stock, price_history, financials)

        data = TickerData(
            info=ticker_info,
            price_history=price_history,
            financials=financials,
            financial_history=history,
            analyst_recommendations=[],
            news_headlines=[],
            fetched_at=datetime.combine(self.as_of_date, time()),
            provider_capture="historical",
        )
        if self.replay_dir is not None:
            macro_path = self.replay_dir / "macro.jsonl"
            if not macro_path.exists():
                macro_path = self.replay_dir / "macro.json"
            data.valuation_price = load_valuation_price_replay(self.replay_dir, ticker, self.as_of_date)
            data.macro_snapshot = load_macro_replay(macro_path, self.as_of_date)
            data.news_headlines = load_news_replay(self.replay_dir / "news", ticker, self.as_of_date)
            context = build_fundamental_context(data, self.as_of_date)
            data.info = data.info.model_copy(update={k: context["valuation"][k]
                                                   for k in ("pe_ratio", "market_cap")})
        data.news_max_age_days = self.news_max_age_days
        data.news_headlines = filter_point_in_time_news(data.news_headlines, as_of=self.as_of_date,
                                                       max_age_days=data.news_max_age_days)
        return data

    # ------------------------------------------------------------------
    # price history
    # ------------------------------------------------------------------
    def _fetch_price_history(
        self, stock: yf.Ticker, ticker: str | None = None
    ) -> list[PriceBar]:
        start = self.as_of_date - timedelta(days=self.lookback_days + 30)
        end = self.as_of_date + timedelta(days=1)
        hist = stock.history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=True
        )
        if hist.empty:
            return []

        # Strict truncation: keep only bars on or before as_of_date.
        # yfinance history is inclusive on start, exclusive on end.
        hist = hist[hist.index.date <= self.as_of_date]

        bars = [
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
        return reject_unusable_bars(ticker or "backtest", bars)

    # ------------------------------------------------------------------
    # financials — pick the latest statement whose mapped SEC filing date is
    # on or before as_of_date
    # ------------------------------------------------------------------
    def _extract_financials(self, stock: yf.Ticker) -> FinancialStatements | None:
        history = self._extract_financial_history(stock)
        return history[-1] if history else None

    def _extract_financial_history(self, stock: yf.Ticker) -> list[FinancialStatements]:
        try:
            inc, bal, cf = stock.quarterly_income_stmt, stock.quarterly_balance_sheet, stock.quarterly_cashflow
            kind = "quarter"
            if inc is None or inc.empty:
                inc, bal, cf = stock.income_stmt, stock.balance_sheet, stock.cashflow
                kind = "annual"
        except Exception:
            return []
        if inc is None or inc.empty:
            return []
        filing_dates = self._filing_dates_by_period(stock, inc.columns)
        history = []
        for col in inc.columns:
            end = self._to_date(col)
            dates = [d for d in filing_dates.get(end, []) if d <= self.as_of_date]
            if end is None or end > self.as_of_date or not dates:
                continue
            income = inc[col]
            balance = bal[col] if bal is not None and not bal.empty and col in bal.columns else {}
            cashflow = cf[col] if cf is not None and not cf.empty and col in cf.columns else {}
            revenue = self._safe_get(income, "Total Revenue")
            net_income = self._safe_get(income, "Net Income")
            gross = self._safe_get(income, "Gross Profit")
            operating = self._safe_get(income, "Operating Income")
            if all(v is None for v in (revenue, net_income, gross, operating)):
                continue
            shares = self._safe_get(balance, "Ordinary Shares Number")
            history.append(FinancialStatements(
                revenue=revenue, net_income=net_income,
                total_debt=self._safe_get(balance, "Total Debt"),
                total_equity=self._safe_get(balance, "Stockholders Equity"),
                free_cash_flow=self._safe_get(cashflow, "Free Cash Flow"),
                gross_margin=gross / revenue if gross is not None and revenue else None,
                operating_margin=operating / revenue if operating is not None and revenue else None,
                net_margin=net_income / revenue if net_income is not None and revenue else None,
                diluted_eps=self._safe_get(income, "Diluted EPS"),
                shares_outstanding=shares if shares and shares > 0 else None,
                fiscal_period_end=end, available_as_of=max(dates), period_kind=kind,
                availability_source="yahoo_sec_filing",
                # Current-provider frames do not establish original vintages,
                # exact duration starts, historical currency or share basis.
            ))
        return select_financial_history(history, self.as_of_date)

    def _pick_statement_column(
        self, stock: yf.Ticker, df: pd.DataFrame
    ) -> tuple[object, date, date] | None:
        filing_dates = self._filing_dates_by_period(stock, df.columns)
        eligible: list[tuple[object, date, date]] = []
        for column in df.columns:
            period_end = self._to_date(column)
            if period_end is None:
                continue
            available_dates = [
                filing_date
                for filing_date in filing_dates.get(period_end, [])
                if filing_date <= self.as_of_date
            ]
            if available_dates:
                eligible.append((column, period_end, max(available_dates)))
        if not eligible:
            return None
        return max(eligible, key=lambda item: item[1])

    def _filing_dates_by_period(
        self, stock: yf.Ticker, statement_columns: Iterable[object]
    ) -> dict[date, list[date]]:
        """Map statement periods to filing dates from yfinance SEC metadata.

        yfinance exposes the filing date and exhibit URLs, but not a stable
        report-period field. Restrict URL matching to periods that actually
        exist in the statement frame so accession-number dates cannot be
        mistaken for a fiscal period.
        """
        period_tokens = {
            period.strftime("%Y%m%d"): period
            for column in statement_columns
            if (period := self._to_date(column)) is not None
        }
        if not period_tokens:
            return {}

        try:
            filings = stock.sec_filings
        except Exception:
            return {}
        if isinstance(filings, dict):
            filings = filings.get("filings", [])

        result: dict[date, list[date]] = {}
        for filing in filings or []:
            if str(filing.get("type", "")).removesuffix("/A") not in {"10-Q", "10-K", "20-F", "40-F", "6-K"}:
                continue
            filing_date = self._to_date(filing.get("date"))
            if filing_date is None:
                continue
            exhibits = filing.get("exhibits") or {}
            urls = [filing.get("edgarUrl", ""), *exhibits.values()]
            filing_text = " ".join(str(url) for url in urls)
            for token, period in period_tokens.items():
                if token in filing_text:
                    result.setdefault(period, []).append(filing_date)
        return result

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
        _stock: yf.Ticker,
        price_history: list[PriceBar],
        financials: FinancialStatements | None,
    ) -> TickerInfo:
        # Current provider metadata is not point-in-time, including a name
        # changed by a future rebrand or a currency changed by relisting.
        # Use only deterministic identifiers until dated metadata is supplied.

        # Truncated 52-week high/low from price history
        last_year = [
            p for p in price_history
            if (self.as_of_date - p.date).days <= 365
        ]
        hi = max((p.high for p in last_year), default=None)
        lo = min((p.low for p in last_year), default=None)

        # Current `stock.info` shares are not point-in-time. Do not derive
        # historical market cap/P-E from a future share count; leave valuation
        # fields unknown until a dated shares source is available.
        pe_ratio: float | None = None
        market_cap: float | None = None

        # Normalize display symbol for MY
        sym = display_symbol.upper().strip()
        if self.market == "MY" and sym.endswith(".KL"):
            sym = sym[:-3]

        market_enum = Market.MY if self.market == "MY" else Market.US
        currency = "MYR" if market_enum == Market.MY else "USD"

        return TickerInfo(
            symbol=sym,
            name=sym,
            sector=None,
            industry=None,
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
            val = series.get(key) if hasattr(series, "get") else None
            if val is not None and str(val) != "nan":
                return float(val)
        except (KeyError, TypeError, ValueError):
            pass
        return None
