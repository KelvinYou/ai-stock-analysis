from datetime import date, datetime, timedelta

import pytest

from stock_analysis.config import Settings
from stock_analysis.data.preflight import (
    InsufficientEvidenceError,
    MacroRepairError,
    diagnose,
    ensure_evidence,
)
from stock_analysis.models.market_data import (
    FinancialStatements,
    MacroSnapshot,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)

AS_OF = date(2026, 11, 6)


def _data(*, bars=210, fin=True, news=True, macro=True, capture="current") -> TickerData:
    start = AS_OF - timedelta(days=bars - 1)
    return TickerData(
        info=TickerInfo(symbol="TEST", name="Test", market=Market.US, currency="USD"),
        price_history=[
            PriceBar(date=start + timedelta(days=i), open=1, high=2, low=1, close=1.5, volume=10)
            for i in range(bars)
        ],
        financials=FinancialStatements(revenue=1.0) if fin else None,
        news_headlines=[{"title": "x", "published_at": "2026-11-05T00:00:00+00:00"}]
        if news
        else [],
        macro_snapshot=MacroSnapshot(
            as_of_date=AS_OF, available_as_of=AS_OF, source="t", fed_funds_rate=3.9
        )
        if macro
        else None,
        provider_capture=capture,
        fetched_at=datetime(2026, 11, 6, 12, 0),
    )


def _macro(as_of: date) -> MacroSnapshot:
    return MacroSnapshot(
        as_of_date=as_of, available_as_of=as_of, source="FRED", fed_funds_rate=3.88
    )


def _fail(as_of: date) -> MacroSnapshot:
    raise MacroRepairError("FRED DFF: ConnectError: certificate verify failed")


def test_diagnose_names_each_gap_with_a_code():
    codes = {
        (g.evidence, g.code)
        for g in diagnose(_data(bars=50, fin=False, news=False, macro=False), AS_OF)
    }
    assert codes == {
        ("technical", "price_history_short"),
        ("fundamentals", "financials_missing"),
        ("sentiment", "news_empty"),
        ("macro", "macro_missing"),
    }
    assert diagnose(_data(), AS_OF) == []


def test_stale_last_bar_is_a_technical_gap():
    old = _data()
    gaps = diagnose(old, AS_OF + timedelta(days=10))
    assert [(g.evidence, g.code) for g in gaps] == [("technical", "price_bars_stale")]


def test_missing_macro_is_repaired_from_primary_source():
    data, report = ensure_evidence(_data(macro=False), AS_OF, Settings(), macro_source=_macro)
    assert data.macro_snapshot is not None and report.quorum_met and report.gaps == []
    assert [(r.action, r.ok) for r in report.repairs] == [("fred_primary", True)]


def test_unrepairable_gap_below_quorum_halts_with_the_cause():
    with pytest.raises(InsufficientEvidenceError) as exc:
        ensure_evidence(
            _data(fin=False, news=False, macro=False), AS_OF, Settings(), macro_source=_fail
        )
    text = str(exc.value)
    assert "certificate verify failed" in text and "INSUFFICIENT" in text
    assert exc.value.report.usable == {
        "technical": True,
        "fundamentals": False,
        "sentiment": False,
        "macro": False,
    }


def test_one_missing_class_still_passes_quorum_of_three():
    _, report = ensure_evidence(_data(news=False), AS_OF, Settings(), macro_source=_fail)
    assert report.quorum_met and not report.usable["sentiment"]


def test_technical_is_required_even_when_other_classes_pass():
    with pytest.raises(InsufficientEvidenceError):
        ensure_evidence(
            _data(bars=50), AS_OF, Settings(min_evidence_classes=3), macro_source=_macro
        )


def test_provider_refetch_runs_once_and_keeps_repaired_macro():
    calls = []

    def refetch():
        calls.append(1)
        return _data(news=True, macro=False)

    data, report = ensure_evidence(
        _data(news=False, macro=False), AS_OF, Settings(), refetch=refetch, macro_source=_macro
    )
    assert calls == [1] and report.quorum_met and data.news_headlines
    assert {r.action for r in report.repairs} == {"provider_refetch", "fred_primary"}


def test_historical_capture_is_diagnosed_but_never_repaired_or_halted():
    historical = _data(fin=False, news=False, macro=False, capture="historical")

    def forbidden(_):  # a repair here would leak today's data into a past cutoff
        raise AssertionError("repair must not run for historical captures")

    data, report = ensure_evidence(
        historical, AS_OF, Settings(), refetch=forbidden, macro_source=forbidden
    )
    assert not report.live and not report.quorum_met and report.repairs == []
    assert data.macro_snapshot is None


def test_cli_exit_codes_and_fix(tmp_path, monkeypatch, capsys):
    from stock_analysis.data import preflight
    from stock_analysis.data.store import DataStore

    today = date.today()
    start = today - timedelta(days=209)

    def snapshot(**kw):
        d = _data(**kw)
        bars = [
            PriceBar(date=start + timedelta(days=i), open=1, high=2, low=1, close=1.5, volume=10)
            for i in range(210)
        ]
        return d.model_copy(
            update={
                "price_history": bars,
                "fetched_at": datetime.combine(today, datetime.min.time()),
            }
        )

    store = DataStore(str(tmp_path))
    store.save_market_data("GOOD", snapshot(macro=False))
    store.save_market_data("THIN", snapshot(fin=False, news=False, macro=False))
    monkeypatch.setattr(preflight, "fetch_fred_macro", _macro)

    assert preflight.cli(["GOOD", "--data-dir", str(tmp_path), "--fix"]) == 0
    assert "fed_funds_rate" in (tmp_path / "GOOD" / "fundamentals.json").read_text()
    assert preflight.cli(["MISSING", "--data-dir", str(tmp_path)]) == 1

    monkeypatch.setattr(preflight, "fetch_fred_macro", _fail)
    assert preflight.cli(["THIN", "--data-dir", str(tmp_path)]) == 2
    assert "INSUFFICIENT" in capsys.readouterr().out


def test_pipeline_halts_before_any_run_or_model_call_on_thin_live_input():
    import asyncio

    from stock_analysis.orchestrator import AnalysisPipeline

    class Fetcher:
        def fetch(self, ticker):
            return _data(fin=False, news=False, macro=False)

        def resolve_symbol(self, ticker):
            return "TEST"

    class Store:
        def begin_run(self, *a, **k):
            raise AssertionError("no run row may exist for an insufficient input")

    pipeline = AnalysisPipeline(
        Settings(),
        fetcher=Fetcher(),
        store=Store(),
        outcome_store=object(),
        as_of_date=AS_OF,
    )
    # No macro_source injection point here, so make the primary source unreachable.
    import stock_analysis.data.preflight as preflight

    original = preflight.fetch_fred_macro
    preflight.fetch_fred_macro = _fail
    try:
        with pytest.raises(InsufficientEvidenceError):
            asyncio.run(pipeline.run("TEST"))
    finally:
        preflight.fetch_fred_macro = original


def test_repaired_macro_is_knowable_at_the_capture_cutoff_not_run_day():
    captured = _data(macro=False).model_copy(update={"fetched_at": datetime(2026, 11, 7, 12, 0)})
    run_day = date(2026, 11, 9)
    seen = []

    def source(cutoff):
        seen.append(cutoff)
        return _macro(cutoff)

    start = run_day - timedelta(days=209)
    bars = [
        PriceBar(date=start + timedelta(days=i), open=1, high=2, low=1, close=1.5, volume=10)
        for i in range(210)
    ]
    data, report = ensure_evidence(
        captured.model_copy(update={"price_history": bars}),
        run_day,
        Settings(),
        macro_source=source,
    )
    assert seen == [date(2026, 11, 7)]
    assert data.macro_snapshot.available_as_of <= captured.fetched_at.date()
    assert report.quorum_met


def _fred_client(series_csv: dict[str, str]):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=series_csv[request.url.params["id"]])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fred_macro_skips_month_whose_prior_year_was_never_published():
    # BLS never published October 2025 CPI (government shutdown); FRED shows ".".
    from stock_analysis.data.preflight import fetch_fred_macro

    client = _fred_client({
        "DFF": "observation_date,DFF\n2026-11-17,3.88\n",
        "CPIAUCSL": (
            "observation_date,CPIAUCSL\n"
            "2025-09-01,324.0\n2025-10-01,.\n"
            "2026-09-01,333.72\n2026-10-01,334.5\n"
        ),
    })
    snap = fetch_fred_macro(date(2026, 11, 18), client=client)
    assert snap.inflation == pytest.approx(3.0)
    assert snap.sector_factors == ["CPI year-over-year is for 2026-09 (FRED:CPIAUCSL)"]


def test_fred_macro_fails_when_no_month_has_a_prior_year():
    from stock_analysis.data.preflight import fetch_fred_macro

    client = _fred_client({
        "DFF": "observation_date,DFF\n2026-11-17,3.88\n",
        "CPIAUCSL": "observation_date,CPIAUCSL\n2026-10-01,334.5\n",
    })
    with pytest.raises(MacroRepairError, match="year-over-year"):
        fetch_fred_macro(date(2026, 11, 18), client=client)
