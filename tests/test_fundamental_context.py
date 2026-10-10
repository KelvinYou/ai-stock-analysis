from datetime import date, datetime

import pytest

from stock_analysis.data.fundamentals import build_fundamental_context, select_financial_history
from stock_analysis.models.market_data import (
    FinancialStatements,
    HistoricalValuationPrice,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)


def statement(start, end, filed, **values):
    return FinancialStatements(
        fiscal_period_start=start,
        fiscal_period_end=end,
        available_as_of=filed,
        period_kind="quarter",
        currency="USD",
        availability_source="fixture",
        share_basis="fixture-split-basis-2025",
        revenue=100,
        **values,
    )


def ticker(history):
    return TickerData(
        info=TickerInfo(symbol="TEST", name="TEST", market=Market.US, currency="USD"),
        fetched_at=datetime(2025, 8, 15),
        financials=history[-1],
        financial_history=history,
        price_history=[
            PriceBar(date=date(2025, 8, 15), open=20, high=21, low=19, close=20, volume=10000)
        ],
        valuation_price=HistoricalValuationPrice(
            price=20,
            price_date=date(2025, 8, 15),
            available_as_of=date(2025, 8, 15),
            currency="USD",
            share_basis="fixture-split-basis-2025",
            source="fixture",
        ),
    )


def quarters():
    return [
        statement("2024-07-01", "2024-09-30", "2024-11-01", diluted_eps=1),
        statement("2024-10-01", "2024-12-31", "2025-02-01", diluted_eps=2),
        statement("2025-01-01", "2025-03-31", "2025-05-01", diluted_eps=3),
        statement("2025-04-01", "2025-06-30", "2025-08-01", diluted_eps=4, shares_outstanding=1000),
    ]


def test_ttm_and_valuation_use_only_four_contiguous_same_basis_quarters():
    context = build_fundamental_context(ticker(quarters()))
    assert context["valuation"]["ttm_diluted_eps"] == 10
    assert context["valuation"]["pe_ratio"] == 2
    assert context["valuation"]["market_cap"] == 20000
    assert context["readiness"]["valuation"] is True
    assert context["readiness"]["history_periods"] == 4


def test_issuer_quoted_adr_eps_has_explicit_currency_separate_from_reporting_currency():
    history = [r.model_copy(update={"currency": "TWD", "diluted_eps_currency": "USD"})
               for r in quarters()]
    data = ticker(history)
    context = build_fundamental_context(data)
    assert context["financials"]["currency"] == "TWD"
    assert context["valuation"]["eps_currency"] == "USD"
    assert context["valuation"]["pe_ratio"] == 2
    history[-1] = history[-1].model_copy(update={"diluted_eps_currency": None})
    assert build_fundamental_context(ticker(history))["valuation"]["pe_ratio"] is None


@pytest.mark.parametrize("problem", ["future_revision", "undated", "future_period"])
def test_history_excludes_unavailable_financial_values(problem):
    original = quarters()[0]
    bad = original.model_copy(
        update={
            "available_as_of": date(2026, 1, 1) if problem == "future_revision" else None,
            "revenue": 999,
            **({"fiscal_period_end": date(2026, 1, 1)} if problem == "future_period" else {}),
        }
    )
    assert select_financial_history([original, bad], date(2025, 8, 15)) == [original]


def test_revision_selection_uses_cutoff_and_latest_period_not_last_filing():
    old, latest = quarters()[0], quarters()[-1]
    amendment = old.model_copy(update={"available_as_of": date(2025, 8, 10), "revenue": 150})
    selected = select_financial_history([old, latest, amendment], date(2025, 8, 15))
    assert selected == [amendment, latest]


def test_conflicting_same_clock_vintages_are_rejected():
    original = quarters()[0]
    conflicting = original.model_copy(update={"revenue": 999})
    with pytest.raises(ValueError, match="Conflicting financial"):
        select_financial_history([original, conflicting], date(2025, 8, 15))


@pytest.mark.parametrize(
    "problem",
    [
        "basis",
        "currency",
        "missing_quarter",
        "overlap",
        "price_date",
        "future_price",
        "negative_eps",
    ],
)
def test_unsafe_pe_is_not_derived(problem):
    data = ticker(quarters())
    if problem == "basis":
        data.financial_history[0].share_basis = "different-split-basis"
    elif problem == "currency":
        data.financial_history[0].currency = "EUR"
    elif problem == "missing_quarter":
        data.financial_history.pop(1)
    elif problem == "overlap":
        data.financial_history[1].fiscal_period_start = date(2024, 9, 1)
    elif problem == "price_date":
        data.valuation_price.price_date = date(2025, 8, 14)
    elif problem == "future_price":
        data.valuation_price.available_as_of = date(2025, 8, 16)
    else:
        data.financial_history[0].diluted_eps = -20
    assert build_fundamental_context(data)["valuation"]["pe_ratio"] is None


def test_growth_compares_matching_fiscal_durations_and_currency():
    prior = statement("2024-04-01", "2024-06-30", "2024-08-01", net_income=10)
    latest = quarters()[-1].model_copy(update={"revenue": 120, "net_income": 12})
    context = build_fundamental_context(ticker([prior, latest]))
    assert context["growth"]["revenue_yoy"] == pytest.approx(0.2)
    assert context["growth"]["net_income_yoy"] == pytest.approx(0.2)
    prior.fiscal_period_start = date(2024, 1, 1)
    assert build_fundamental_context(ticker([prior, latest]))["growth"]["revenue_yoy"] is None


def test_old_single_statement_is_compatible_but_not_growth_or_valuation_ready():
    data = ticker(quarters())
    old = data.model_dump(mode="json")
    old.pop("financial_history")
    old.pop("valuation_price")
    restored = TickerData.model_validate(old)
    context = build_fundamental_context(restored)
    assert context["readiness"]["statement"] is True
    assert context["readiness"]["history_periods"] == 1
    assert context["readiness"]["valuation"] is False
    assert context["growth"]["revenue_yoy"] is None


def test_local_storage_roundtrip_preserves_new_evidence(tmp_path):
    from stock_analysis.data.store import DataStore

    data = ticker(quarters())
    store = DataStore(tmp_path)
    store.save_market_data("TEST", data)
    restored = store.load_market_data("TEST")
    assert restored.financial_history == data.financial_history
    assert restored.valuation_price == data.valuation_price


@pytest.mark.parametrize(
    "problem",
    ["new_missing_eps", "eps_overflow", "cap_overflow", "pe_overflow", "foreign_currency"],
)
def test_context_rejects_stale_or_nonfinite_derived_valuation(problem):
    data = ticker(quarters())
    if problem == "new_missing_eps":
        data.financial_history.append(statement("2025-07-01", "2025-09-30", "2025-11-01"))
        context = build_fundamental_context(data, date(2025, 11, 15))
        assert context["valuation"]["ttm_diluted_eps"] is None
        return
    if problem == "eps_overflow":
        for record in data.financial_history:
            record.diluted_eps = 1e308
    elif problem == "cap_overflow":
        data.financial_history[-1].shares_outstanding = 1e308
    elif problem == "pe_overflow":
        for record in data.financial_history:
            record.diluted_eps = 1e-320
    elif problem == "foreign_currency":
        foreign = data.financial_history[-1].model_copy(
            update={"currency": "ZAR", "diluted_eps": 999}
        )
        data.financial_history.append(foreign)
        context = build_fundamental_context(data)
        assert context["valuation"]["pe_ratio"] == 2
        assert all(r["currency"] == "USD" for r in context["history"])
        return
    context = build_fundamental_context(data)
    name = "market_cap" if problem == "cap_overflow" else "pe_ratio"
    assert context["valuation"][name] is None


def test_growth_overflow_remains_unavailable():
    old = statement("2024-04-01", "2024-06-30", "2024-08-01")
    current = quarters()[-1]
    old.revenue = 1e-320
    current.revenue = 1e308
    context = build_fundamental_context(ticker([old, current]))
    assert context["growth"]["revenue_yoy"] is None
    assert context["readiness"]["growth"] is False


def test_foreign_reporting_currency_keeps_growth_without_currency_conversion():
    old = statement("2024-04-01", "2024-06-30", "2024-08-01")
    current = quarters()[-1]
    old.currency = current.currency = "TWD"
    current.revenue = 150
    context = build_fundamental_context(ticker([old, current]))
    assert context["growth"]["revenue_yoy"] == 0.5
    assert context["readiness"]["statement"] is True
    assert context["valuation"]["pe_ratio"] is None


@pytest.mark.asyncio
async def test_fundamental_tools_expose_the_shared_context():
    import json

    from stock_analysis.agents.fundamentals import FundamentalsAgent

    data = ticker(quarters())
    data.info.pe_ratio = 999
    data.info.forward_pe = 999
    tools = {tool.name: tool for tool in FundamentalsAgent().build_tools(data)}
    response = await tools["get_financials"].handler({"ticker": "TEST"})
    payload = json.loads(response["content"][0]["text"])
    assert len(payload["financial_history"]) == 4
    assert payload["valuation"]["pe_ratio"] == 2
    assert payload["readiness"] == build_fundamental_context(data)["readiness"]


@pytest.mark.asyncio
async def test_historical_info_tool_does_not_reuse_current_only_valuation():
    import json

    from stock_analysis.agents.fundamentals import FundamentalsAgent

    data = ticker(quarters())
    data.valuation_price = None
    data.info.pe_ratio = data.info.forward_pe = data.info.market_cap = 999
    tools = {tool.name: tool for tool in FundamentalsAgent().build_tools(data)}
    response = await tools["get_ticker_info"].handler({"ticker": "TEST"})
    info = json.loads(response["content"][0]["text"])
    assert info["pe_ratio"] is info["forward_pe"] is info["market_cap"] is None
