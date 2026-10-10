"""Deterministic historical evidence context shared by packets and analyst tools."""

from __future__ import annotations

import math
from datetime import date, timedelta
from itertools import pairwise

from stock_analysis.data.evidence import financials_are_usable
from stock_analysis.models.market_data import FinancialStatements, TickerData


def select_financial_history(
    records: list[FinancialStatements],
    as_of: date,
) -> list[FinancialStatements]:
    """Keep one knowable vintage per exact fiscal duration/currency.

    Date-only filing clocks are required here, even though legacy live single
    snapshots may remain usable without clocks. Missing and conflicting data
    cannot create apparent multi-period evidence.
    """
    selected: dict[tuple, FinancialStatements] = {}
    for record in records:
        end, filed, start = (
            record.fiscal_period_end,
            record.available_as_of,
            record.fiscal_period_start,
        )
        if end is None or filed is None or filed < end:
            continue
        if start is not None and start > end:
            continue
        if not financials_are_usable(record, as_of):
            continue
        values = (
            record.revenue,
            record.net_income,
            record.total_debt,
            record.total_equity,
            record.free_cash_flow,
            record.gross_margin,
            record.operating_margin,
            record.net_margin,
            record.diluted_eps,
            record.shares_outstanding,
        )
        if any(v is not None and not math.isfinite(v) for v in values):
            continue
        key = (start, end, record.period_kind, record.currency)
        prior = selected.get(key)
        if prior is None or filed > prior.available_as_of:
            selected[key] = record
        elif filed == prior.available_as_of and record != prior:
            raise ValueError(f"Conflicting financial vintages for {start}/{end} at {filed}")
    return sorted(
        selected.values(),
        key=lambda r: (
            r.fiscal_period_end,
            r.fiscal_period_start or date.min,
            r.available_as_of,
            r.currency or "",
            r.period_kind or "",
        ),
    )


def _duration(statement: FinancialStatements) -> int | None:
    if statement.fiscal_period_start is None or statement.fiscal_period_end is None:
        return None
    return (statement.fiscal_period_end - statement.fiscal_period_start).days + 1


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def _ttm_eps(history: list[FinancialStatements]) -> tuple[float | None, list[FinancialStatements]]:
    # Bounds reflect SEC fiscal-quarter/year duration classes (including 52/53
    # week calendars), not trading thresholds or an inferred reporting cadence.
    quarters = [
        r
        for r in history
        if r.period_kind == "quarter"
        and r.diluted_eps is not None
        and r.share_basis
        and r.currency
        and _duration(r) is not None
        and 60 <= _duration(r) <= 121
    ]
    window = quarters[-4:]
    if (
        len(window) == 4
        and window[-1].fiscal_period_end == history[-1].fiscal_period_end
        and all(
            a.fiscal_period_end + timedelta(days=1) == b.fiscal_period_start
            for a, b in pairwise(window)
        )
        and len({(r.diluted_eps_currency or r.currency, r.share_basis) for r in window}) == 1
    ):
        total = _finite(sum(r.diluted_eps for r in window))
        return (total, window) if total is not None else (None, [])
    annuals = [
        r
        for r in history
        if r.period_kind == "annual"
        and r.diluted_eps is not None
        and r.share_basis
        and r.currency
        and _duration(r) is not None
        and 300 <= _duration(r) <= 400
    ]
    # An annual report cannot substitute for a newer EPS window silently.
    latest_eps_end = max((r.fiscal_period_end for r in history), default=None)
    if annuals and annuals[-1].fiscal_period_end == latest_eps_end:
        return annuals[-1].diluted_eps, [annuals[-1]]
    return None, []


def _growth(history: list[FinancialStatements]) -> dict:
    result = {
        "revenue_yoy": None,
        "net_income_yoy": None,
        "current_period_end": None,
        "comparison_period_end": None,
    }
    if not history:
        return result
    current = history[-1]
    if not current.currency or current.period_kind not in {"quarter", "annual"}:
        return result
    duration = _duration(current)
    if duration is None:
        return result
    bounds = (60, 121) if current.period_kind == "quarter" else (300, 400)
    if not bounds[0] <= duration <= bounds[1]:
        return result
    previous = [
        r
        for r in history[:-1]
        if r.currency == current.currency
        and r.period_kind == current.period_kind
        and _duration(r) is not None
        and abs(_duration(r) - duration) <= 7
        and abs((current.fiscal_period_end - r.fiscal_period_end).days - 365) <= 7
    ]
    if not previous:
        return result
    prior = previous[-1]
    result.update(
        current_period_end=current.fiscal_period_end.isoformat(),
        comparison_period_end=prior.fiscal_period_end.isoformat(),
    )
    for name in ("revenue", "net_income"):
        before, after = getattr(prior, name), getattr(current, name)
        if before is not None and before > 0 and after is not None:
            result[f"{name}_yoy"] = _finite(after / before - 1.0)
    return result


def build_fundamental_context(data: TickerData, as_of: date | None = None) -> dict:
    """Expose observations and gaps without forcing a fundamental buy/sell."""
    as_of = as_of or data.fetched_at.date()
    history = select_financial_history(data.financial_history, as_of)
    if not history and data.financials is not None:
        history = select_financial_history([data.financials], as_of)
    # Reporting currency can differ from the listing/valuation currency (ADRs).
    # Follow the declared primary statement, rather than a secondary currency's
    # lexical position. Valuation still requires a direct currency match.
    reporting_currency = (
        data.financials.currency
        if data.financials and data.financials.currency
        else data.info.currency
    )
    history = [r for r in history if r.currency in {None, reporting_currency}]
    statement = history[-1] if history else data.financials
    statement_available = financials_are_usable(statement, as_of) and (
        statement.currency in {None, reporting_currency}
    )
    eps, eps_window = _ttm_eps(history)
    growth = _growth(history)
    valuation = {
        "ttm_diluted_eps": eps,
        "eps_period_end": None,
        "pe_ratio": None,
        "market_cap": None,
        "price_date": None,
        "source": None,
        "basis_authority": "provider_declared_not_independently_authenticated",
    }
    if eps_window:
        valuation["eps_period_end"] = eps_window[-1].fiscal_period_end.isoformat()
        if any(r.diluted_eps_currency is not None for r in eps_window):
            valuation["eps_currency"] = eps_window[-1].diluted_eps_currency or eps_window[-1].currency
    price = data.valuation_price
    last_bar = max((bar.date for bar in data.price_history if bar.date <= as_of), default=None)
    valid_price = price is not None and (
        price.price_date == last_bar
        and price.price_date <= price.available_as_of <= as_of
        and price.currency == data.info.currency
        and all(s.strip() for s in (price.currency, price.share_basis, price.source))
    )
    if valid_price:
        valuation.update(price_date=price.price_date.isoformat(), source=price.source)
        if (
            eps is not None
            and eps > 0
            and all(
                (r.diluted_eps_currency or r.currency) == price.currency
                and r.share_basis == price.share_basis
                for r in eps_window
            )
        ):
            valuation["pe_ratio"] = _finite(price.price / eps)
        share_records = [
            r
            for r in history
            if r.shares_outstanding is not None
            and r.shares_outstanding > 0
            and r.currency == price.currency
            and r.share_basis == price.share_basis
        ]
        if share_records:
            valuation["market_cap"] = _finite(price.price * share_records[-1].shares_outstanding)
    gaps = []
    if not statement_available:
        gaps.append("statement_unavailable")
    if not history:
        gaps.append("dated_history_unavailable")
    if growth["revenue_yoy"] is None and growth["net_income_yoy"] is None:
        gaps.append("comparable_year_ago_period_unavailable")
    if eps is None:
        gaps.append("trailing_eps_with_common_share_basis_unavailable")
    if not valid_price:
        gaps.append("dated_same_basis_valuation_price_unavailable")
    if valuation["pe_ratio"] is None:
        gaps.append("pe_unavailable")
    if valuation["market_cap"] is None:
        gaps.append("market_cap_unavailable")
    return {
        "as_of_date": as_of.isoformat(),
        "financials": statement.model_dump(mode="json") if statement_available else None,
        "history": [r.model_dump(mode="json") for r in history],
        "growth": growth,
        "valuation": valuation,
        "readiness": {
            "statement": statement_available,
            "history_periods": len(history),
            "growth": growth["revenue_yoy"] is not None or growth["net_income_yoy"] is not None,
            "valuation": valuation["pe_ratio"] is not None,
            "statement_age_days": (as_of - statement.fiscal_period_end).days
            if statement_available and statement.fiscal_period_end
            else None,
            "statement_filing_age_days": (as_of - statement.available_as_of).days
            if statement_available and statement.available_as_of
            else None,
            "gaps": gaps,
        },
    }


def fundamental_evidence_count(ticker_data: TickerData) -> int:
    """Count distinct measured dimensions, grouping income and derived margins."""
    from math import isfinite

    from .evidence import current_metadata_are_usable, financials_are_usable
    financials = ticker_data.financials
    if not financials_are_usable(financials, ticker_data.fetched_at.date()):
        return 0
    context = build_fundamental_context(ticker_data)
    def present(*values):
        return any(value is not None and isfinite(value) for value in values)
    live_metadata = current_metadata_are_usable(ticker_data)
    return sum((
        present(financials.revenue, financials.net_income, financials.gross_margin,
                financials.operating_margin, financials.net_margin),
        present(financials.total_debt, financials.total_equity),
        present(financials.free_cash_flow),
        present(context["valuation"]["pe_ratio"],
                ticker_data.info.pe_ratio if live_metadata else None,
                ticker_data.info.forward_pe if live_metadata else None),
        context["readiness"]["growth"],
    ))
