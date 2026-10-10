"""Current-provider evidence, dated at capture rather than backdated to filing."""

from datetime import timedelta
from math import isfinite

import pandas as pd

from stock_analysis.models.market_data import FinancialStatements, HistoricalValuationPrice


def number(series, key):
    try:
        value = float(series.get(key))
        return value if isfinite(value) else None
    except (TypeError, ValueError):
        return None


def frame(stock, attribute):
    try:
        value = getattr(stock, attribute)
        return value if isinstance(value, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def financial_history(stock, info, captured_at):
    quarterly = frame(stock, "quarterly_income_stmt")
    kind = "quarter" if not quarterly.empty else "annual"
    prefix = "quarterly_" if kind == "quarter" else ""
    income = quarterly if kind == "quarter" else frame(stock, "income_stmt")
    balance = frame(stock, prefix + "balance_sheet")
    cashflow = frame(stock, prefix + "cashflow")
    columns = sorted(income.columns)
    history = []
    for i, column in enumerate(columns):
        end = column.date()
        if end > captured_at.date():
            continue
        start = None
        if i:
            previous = columns[i - 1].date()
            days = (end - previous).days
            if 60 <= days <= 121 if kind == "quarter" else 300 <= days <= 400:
                start = previous + timedelta(days=1)
        inc = income[column]
        bal = balance.get(column, {})
        cf = cashflow.get(column, {})
        revenue, net_income = number(inc, "Total Revenue"), number(inc, "Net Income")
        values = dict(
            revenue=revenue,
            net_income=net_income,
            total_debt=number(bal, "Total Debt"),
            total_equity=number(bal, "Stockholders Equity"),
            free_cash_flow=number(cf, "Free Cash Flow"),
            diluted_eps=number(inc, "Diluted EPS"),
        )
        for name, key in (
            ("gross_margin", "Gross Profit"),
            ("operating_margin", "Operating Income"),
            ("net_margin", "Net Income"),
        ):
            numerator = number(inc, key)
            values[name] = numerator / revenue if revenue and numerator is not None else None
        provenance = {
            name: {
                "source": "yahoo_current_provider",
                "fiscal_period_end": str(end),
                "frequency": kind,
                "observed_at": captured_at.isoformat(),
            }
            for name, value in values.items()
            if value is not None
        }
        history.append(
            FinancialStatements(
                **values,
                fiscal_period_end=end,
                fiscal_period_start=start,
                period_kind=kind,
                currency=info.get("financialCurrency"),
                diluted_eps_currency=info.get("financialCurrency"),
                available_as_of=captured_at.date(),
                availability_source="yahoo_current_provider_observed_at_capture",
                debt_scope="reported_total" if values["total_debt"] is not None else "unavailable",
                fact_provenance=provenance,
            )
        )
    return history


def plain_close(stock, symbol, currency, price_history, captured_at):
    if not price_history:
        return None
    try:
        prices = stock.history(period="1mo", auto_adjust=False, back_adjust=False)
        target = price_history[-1].date
        matches = prices.loc[[idx.date() == target for idx in prices.index]]
        if matches.empty:
            return None
        price = number(matches.iloc[-1], "Close")
        if price is None or price <= 0:
            return None
        return HistoricalValuationPrice(
            price=price,
            price_date=target,
            available_as_of=captured_at.date(),
            currency=currency,
            share_basis=f"yahoo-listed:{symbol}",
            source="yahoo_plain_close_provider_observed_at_capture",
        )
    except Exception:
        return None


def prepare_live_evidence(data, settings):
    """Overlay explicit dated sources before sealing the run input."""
    from pathlib import Path

    from stock_analysis.backtest.replay import (
        load_fundamentals_history_replay,
        load_macro_replay,
        load_news_replay,
        load_valuation_price_replay,
    )

    from .evidence import independent_sentiment_news

    as_of = data.fetched_at.date()
    updates = {"news_max_age_days": settings.news_max_age_days}
    news = list(data.news_headlines or [])
    if settings.evidence_replay_dir:
        directory = Path(settings.evidence_replay_dir)
        if not directory.is_dir():
            raise ValueError("Configured evidence replay directory does not exist")
        history = load_fundamentals_history_replay(directory, data.info.symbol, as_of)
        if history:
            updates.update(financial_history=history, financials=history[-1])
        price = load_valuation_price_replay(directory, data.info.symbol, as_of)
        if price:
            updates["valuation_price"] = price
        macro_path = directory / "macro.jsonl"
        if not macro_path.exists():
            macro_path = directory / "macro.json"
        macro = load_macro_replay(macro_path, as_of)
        if macro:
            updates["macro_snapshot"] = macro
        news.extend(load_news_replay(directory / "news", data.info.symbol, as_of))
    updates["news_headlines"] = independent_sentiment_news(
        news, as_of=as_of, max_age_days=settings.news_max_age_days
    )
    return data.model_copy(update=updates)


def stamp_current_capture(history, price, captured_at):
    """Use completion of provider reads as the conservative availability clock."""
    records = [record.model_copy(update={
        "available_as_of": captured_at.date(),
        "fact_provenance": {key: {**value, "observed_at": captured_at.isoformat()}
                            for key, value in record.fact_provenance.items()},
    }) for record in history]
    price = price.model_copy(update={"available_as_of": captured_at.date()}) if price else None
    return records, price
