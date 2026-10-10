from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_DNS, uuid5

from stock_analysis.models.market_data import Market, PriceBar, TickerData, TickerInfo


def protocol_for(source, anchors=None):
    from stock_analysis.portfolio import PORTFOLIO_ARMS

    return {"version": 2, "anchors": anchors or [str(source.as_of_date)],
            "universe": [row.prediction.ticker for row in source.snapshots],
            "arms": list(PORTFOLIO_ARMS), "horizon_calendar_days": 30,
            "cost_bps_per_side": [0, 10, 20]}


def bundle():
    from stock_analysis.portfolio import PortfolioBundle, PortfolioSnapshot
    from stock_analysis.synthesis.signal_views import SessionPrediction

    as_of = date(2026, 10, 9)
    snapshots = []
    for index, ticker in enumerate(["AAA", "BBB", "CCC", "DDD"]):
        bars = []
        for offset in range(401):
            price = 100 + offset * (4 - index) / 100
            bars.append(PriceBar(date=as_of - timedelta(days=400 - offset),
                                 open=price, high=price + 1, low=price - 1,
                                 close=price, volume=10000))
        snapshots.append(PortfolioSnapshot(
            run_id=str(uuid5(NAMESPACE_DNS, ticker)),
            ticker_data=TickerData(
                info=TickerInfo(symbol=ticker, name=ticker, market=Market.US, currency="USD"),
                price_history=bars, fetched_at=datetime(2026, 10, 9, 22, tzinfo=UTC),
            ),
            prediction=SessionPrediction(
                ticker=ticker, as_of_date=as_of, overall_signal="neutral",
                conviction_score=0, signal_convergence=0,
                agent_signals={"technical": "buy"},
                agent_confidences={"technical": "high"},
            ),
        ))
    return PortfolioBundle(as_of_date=as_of, snapshots=snapshots)


def test_portfolio_stage_produces_nine_views_without_forcing_ai_buys():
    from stock_analysis.portfolio import build_portfolio_plan

    source = bundle()
    plan = build_portfolio_plan(source)
    assert plan.status == "ready"
    assert len(plan.arms) == 9
    arms = {arm.strategy: arm for arm in plan.arms}
    assert arms["allocator_only"].weights == {"AAA": 1 / 3, "BBB": 1 / 3, "CCC": 1 / 3}
    assert arms["allocator_plus_ai"].weights == {}
    assert arms["allocator_plus_ai"].cash_weight == 1
    assert arms["continuous_strict_hold"].weights == {
        "AAA": 0.25, "BBB": 0.25, "CCC": 0.25, "DDD": 0.25,
    }
    assert plan.research_only is True
    assert plan.promotion_ready is False
    reverse = source.model_copy(deep=True)
    reverse.snapshots.reverse()
    assert build_portfolio_plan(reverse) == plan


def test_completed_run_ids_feed_authenticated_portfolio_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    import stock_analysis.api.app as api

    source = bundle()
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_BEARER_TOKEN", "portfolio-test-only")
    monkeypatch.setattr(api, "_local_portfolio_snapshots",
                        {row.run_id: row for row in source.snapshots}, raising=False)
    body = {"run_ids": [row.run_id for row in source.snapshots]}
    with TestClient(api.app) as client:
        unauthorized = client.post("/api/v1/portfolio-plans", json=body)
        assert unauthorized.status_code == 401
        response = client.post("/api/v1/portfolio-plans", json=body,
                               headers={"Authorization": "Bearer portfolio-test-only"})
    assert response.status_code == 200
    assert len(response.json()["arms"]) == 9
    assert response.json()["status"] == "ready"


def test_forward_cohort_is_immutable_and_cannot_fetch_immature_outcomes(tmp_path, monkeypatch):
    import json
    from datetime import UTC

    import pytest

    from stock_analysis.portfolio_cohort import freeze_cohort, score_cohort, verify_cohort

    source = bundle()
    protocol = {"version": 2, "anchors": ["2026-10-09"],
                "universe": [row.prediction.ticker for row in source.snapshots],
                "arms": list(__import__("stock_analysis.portfolio", fromlist=["PORTFOLIO_ARMS"]).PORTFOLIO_ARMS),
                "horizon_calendar_days": 30, "cost_bps_per_side": [0, 10, 20]}
    folder = tmp_path / "cohort"
    freeze_cohort(source, protocol, folder, now=datetime(2026, 10, 9, 23, tzinfo=UTC))
    assert verify_cohort(folder)["scope"] == "prospective_research_only"
    monkeypatch.setattr("stock_analysis.portfolio_cohort._now",
                        lambda: datetime(2026, 10, 10, tzinfo=UTC))
    monkeypatch.setattr("stock_analysis.backtest.runner.Backtester._fetch_price_series",
                        lambda *args: pytest.fail("premature outcome fetch"))
    with pytest.raises(ValueError, match="not mature"):
        score_cohort(folder)
    predictions = folder / "plan.json"
    payload = json.loads(predictions.read_text())
    payload["arms"][0]["cash_weight"] = 1
    predictions.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="changed"):
        verify_cohort(folder)


def test_missing_history_preserves_panel_and_rejects_forward_freeze(tmp_path):
    import pytest

    from stock_analysis.portfolio import build_portfolio_plan
    from stock_analysis.portfolio_cohort import freeze_cohort

    source = bundle()
    source.snapshots[0].ticker_data.price_history = source.snapshots[0].ticker_data.price_history[-100:]
    plan = build_portfolio_plan(source)
    assert plan.status == "unavailable"
    assert plan.unavailable_reasons == ["missing_12_month_history:AAA"]
    assert all(view.cash_weight == 1 and not view.weights for view in plan.arms)
    with pytest.raises(ValueError, match="ready"):
        freeze_cohort(source, protocol_for(source), tmp_path / "cohort",
                      now=datetime(2026, 10, 9, 23, tzinfo=UTC))


def test_mixed_sessions_and_duplicate_runs_reject_planning():
    import pytest

    from stock_analysis.portfolio import build_portfolio_plan

    source = bundle()
    source.snapshots[1].run_id = source.snapshots[0].run_id
    with pytest.raises(ValueError, match="Duplicate"):
        build_portfolio_plan(source)
    source = bundle()
    source.snapshots[1].ticker_data.price_history.pop()
    with pytest.raises(ValueError, match="one completed session"):
        build_portfolio_plan(source)


def test_legacy_clock_and_changed_allocator_cannot_be_forward_samples(tmp_path):
    import pytest

    from stock_analysis.portfolio_cohort import freeze_cohort

    source = bundle()
    source.snapshots[0].ticker_data.fetched_at = datetime(2026, 10, 9, 22)
    with pytest.raises(ValueError, match="timezone"):
        freeze_cohort(source, protocol_for(source), tmp_path / "legacy",
                      now=datetime(2026, 10, 9, 23, tzinfo=UTC))
    source = bundle()
    protocol = protocol_for(source)
    protocol["allocator"] = {"lookback_months": 6, "top_n": 3}
    with pytest.raises(ValueError, match="allocator"):
        freeze_cohort(source, protocol, tmp_path / "changed",
                      now=datetime(2026, 10, 9, 23, tzinfo=UTC))


def test_two_mature_cohorts_reconcile_daily_costs_and_continuous_hold(tmp_path):
    import math

    import pandas as pd
    import pytest

    from stock_analysis.portfolio_cohort import compare_cohorts, freeze_cohort, score_with_histories

    source = bundle()
    anchors = ["2026-10-09", "2026-11-13"]
    protocol = protocol_for(source, anchors)
    folders, scored = [], []
    for index, anchor in enumerate(anchors):
        source = bundle()
        day = date.fromisoformat(anchor)
        shift = day - source.as_of_date
        source.as_of_date = day
        for row in source.snapshots:
            row.run_id = str(uuid5(NAMESPACE_DNS, f"{anchor}:{row.prediction.ticker}"))
            row.prediction.as_of_date = day
            row.ticker_data.fetched_at = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=22)
            for bar in row.ticker_data.price_history:
                bar.date += shift
        folder = tmp_path / str(index)
        freeze_cohort(source, protocol, folder,
                      now=datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=23))
        histories = {}
        for ticker_index, row in enumerate(source.snapshots):
            dates = pd.bdate_range(day - timedelta(days=7), day + timedelta(days=41))
            prices = [100 + (d.date() - date(2026, 10, 1)).days * (ticker_index + 1) / 10
                      for d in dates]
            histories[row.prediction.ticker] = pd.DataFrame(
                {"Open": prices, "High": [p + 1 for p in prices],
                 "Low": [p - 1 for p in prices], "Close": prices, "Volume": 10000}, index=dates)
        outcome = score_with_histories(folder, histories, today=day + timedelta(days=42))
        scored.append(outcome)
        with pytest.raises(FileExistsError, match="already scored"):
            score_with_histories(folder, histories, today=day + timedelta(days=42))
        folders.append(folder)
    report = compare_cohorts(list(reversed(folders)))
    assert report["effective_n"] == 2
    assert report["promotion_ready"] is False
    for bps in (0, 10, 20):
        by_name = {row["strategy"]: row for row in report["costs"][str(bps)]}
        first, last = scored[0]["fills"], scored[-1]["fills"]
        hold = sum(last[ticker]["exit_price"] / first[ticker]["entry_price"]
                   for ticker in first) / len(first) * (1 - bps / 10000) ** 2 - 1
        assert by_name["continuous_strict_hold"]["net_return"] == pytest.approx(hold)
        passive = math.prod(1 + row["arms"][str(bps)]["scheduled_passive"] for row in scored) - 1
        assert by_name["scheduled_passive"]["net_return"] == pytest.approx(passive)
        assert by_name["ai_only"]["net_return"] == 0
        assert hold > passive
        for row in by_name.values():
            assert row["daily_equity"][-1]["equity"] - 1 == pytest.approx(row["net_return"])
            assert row["max_drawdown"] <= 0


def test_cloud_portfolio_uses_sealed_completed_inputs_and_rejects_stage_hash_mismatch(monkeypatch):
    import pytest

    from stock_analysis.api.portfolio_data import load_portfolio_bundle
    from stock_analysis.data.cloud import SupabaseAnalysisStore
    from stock_analysis.models.synthesis import Briefing, ConvictionScore, RiskAssessment
    from stock_analysis.portfolio import build_portfolio_plan
    from tests.test_cloud_storage import MemoryClient, _analyst_reports, _settings

    source, client, settings, run_ids = bundle(), MemoryClient(), _settings(), []
    for row in source.snapshots:
        ticker = row.prediction.ticker
        store = SupabaseAnalysisStore(settings, client=client)
        run_id = store.begin_run(ticker, source.as_of_date, settings)
        store.save_run_input(ticker, row.ticker_data, source.as_of_date)
        store.save_analyst_reports(ticker, _analyst_reports(), source.as_of_date)
        briefing = Briefing(
            ticker=ticker, date=str(source.as_of_date), data_as_of=str(source.as_of_date),
            overall_signal="neutral",
            conviction=ConvictionScore(score=0, signal_convergence=0, explanation="fixture"),
            executive_summary="fixture", bull_case="fixture", bear_case="fixture",
            key_uncertainties=[], catalysts_upcoming=[], agent_signal_breakdown={},
            risk_assessment=RiskAssessment(correlation_notes=[], max_drawdown_scenario="fixture"),
        )
        store.save_briefing(ticker, briefing, source.as_of_date)
        store.complete_run()
        run_ids.append(run_id)
    monkeypatch.setattr("stock_analysis.api.portfolio_data.SupabaseAnalysisStore",
                        lambda config, run_id: SupabaseAnalysisStore(config, run_id=run_id, client=client))
    loaded = load_portfolio_bundle(settings, run_ids)
    assert build_portfolio_plan(loaded).status == "ready"
    assert all(row.source_input_hash for row in loaded.snapshots)
    client.tables["analysis_artifacts"][0]["input_hash"] = "changed"
    with pytest.raises(ValueError, match="hash mismatch"):
        load_portfolio_bundle(settings, run_ids)


def test_ft_view_does_not_use_ai_conviction_or_overall_signal():
    from stock_analysis.synthesis.signal_views import (
        CalibratedSessionPrediction,
        fundamental_technical_views,
    )

    data = bundle().snapshots[0].ticker_data
    prediction = CalibratedSessionPrediction(
        ticker="AAA", as_of_date=date(2026, 10, 9), overall_signal="neutral",
        conviction_score=0, signal_convergence=0, synthesized_signal="neutral", raw_conviction_score=0,
        agent_signals={"fundamentals": "buy", "technical": "buy"},
        agent_confidences={"fundamentals": "high", "technical": "high"},
    )
    views = fundamental_technical_views(prediction, data)
    assert views == {"ft_weighted": "buy", "ft_agreement": "buy"}
    opposite = prediction.model_copy(update={"conviction_score": -1, "overall_signal": "strong_sell"})
    assert fundamental_technical_views(opposite, data) == views


def test_cloud_admission_uses_capture_date_instead_of_quota_timezone(monkeypatch):
    from fastapi.testclient import TestClient

    import stock_analysis.api.app as api
    from tests.test_cloud_storage import _settings

    submitted = {}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 12, 21, tzinfo=UTC).astimezone(tz)

    class Store:
        def __init__(self, settings):
            pass

        def enqueue_run(self, symbol, **kwargs):
            submitted.update(kwargs)
            return str(uuid5(NAMESPACE_DNS, symbol))

        def close(self):
            pass

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_BEARER_TOKEN", "")
    monkeypatch.setattr(api, "datetime", Clock)
    monkeypatch.setattr(api, "_settings", lambda req: _settings())
    monkeypatch.setattr(api, "SupabaseAnalysisStore", Store)
    with TestClient(api.app) as client:
        response = client.post("/api/v1/analyze/AAA", json={})
    assert response.status_code == 202
    assert submitted["as_of_date"] == date(2026, 10, 12)


def test_prepared_protocol_cannot_activate_without_calendar_and_model_identity(tmp_path):
    import pytest

    from stock_analysis.portfolio_cohort import freeze_cohort

    source = bundle()
    protocol = protocol_for(source)
    protocol["activation_required"] = ["collector_acceptance", "model_and_prompt_identity"]
    with pytest.raises(ValueError, match="pinned calendar, model and prompt"):
        freeze_cohort(source, protocol, tmp_path / "unactivated",
                      now=datetime(2026, 10, 9, 23, tzinfo=UTC))
    assert not (tmp_path / "unactivated").exists()


def test_pinned_holiday_anchor_freezes_on_its_prior_completed_session(tmp_path):
    from stock_analysis.portfolio_cohort import freeze_cohort

    source = bundle()
    decision = date(2028, 5, 26)
    shift = decision - source.as_of_date
    source.as_of_date = decision
    for row in source.snapshots:
        row.prediction.as_of_date = decision
        row.ticker_data.fetched_at = datetime(2028, 5, 26, 22, tzinfo=UTC)
        for bar in row.ticker_data.price_history:
            bar.date += shift
    protocol = protocol_for(source, ["2028-05-29"])
    protocol["decision_sessions"] = {"2028-05-29": "2028-05-26"}
    protocol["calendar_provenance"] = "test fixture, not an external attestation"
    manifest = freeze_cohort(source, protocol, tmp_path / "holiday",
                             now=datetime(2028, 5, 26, 23, tzinfo=UTC))
    assert manifest["as_of_date"] == "2028-05-26"
    assert manifest["exit_target"] == "2028-06-25"


def test_changed_implementation_blocks_outcome_fetch(tmp_path, monkeypatch):
    import pytest

    from stock_analysis.portfolio_cohort import freeze_cohort, score_cohort

    source = bundle()
    folder = tmp_path / "pinned"
    freeze_cohort(source, protocol_for(source), folder,
                  now=datetime(2026, 10, 9, 23, tzinfo=UTC))
    monkeypatch.setattr("stock_analysis.portfolio_cohort._now",
                        lambda: datetime(2026, 11, 20, tzinfo=UTC))
    monkeypatch.setattr("stock_analysis.portfolio_cohort.implementation_identity", lambda: "changed")
    monkeypatch.setattr("stock_analysis.backtest.runner.Backtester._fetch_price_series",
                        lambda *args: pytest.fail("changed implementation read outcomes"))
    with pytest.raises(ValueError, match="frozen implementation"):
        score_cohort(folder)
