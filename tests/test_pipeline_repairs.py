from datetime import date, datetime
from unittest.mock import patch

import pytest

from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.market_data import (
    Market,
    PriceBar,
    TechnicalSnapshot,
    TickerData,
    TickerInfo,
)
from stock_analysis.models.synthesis import Briefing, ConvictionScore, RiskAssessment
from stock_analysis.synthesis.risk_checker import RiskChecker


def data():
    return TickerData(
        info=TickerInfo(symbol="TEST", name="TEST", market=Market.US, currency="USD"),
        fetched_at=datetime(2026, 10, 8),
        price_history=[
            PriceBar(date=date(2026, 10, 7), open=10, high=11, low=9, close=10, volume=1000)
        ],
    )


def briefing():
    return Briefing(
        ticker="TEST",
        date="2026-10-08",
        overall_signal=Signal.BUY,
        conviction=ConvictionScore(score=1, signal_convergence=1, explanation="fixture"),
        executive_summary="fixture",
        bull_case="fixture",
        bear_case="fixture",
        key_uncertainties=[],
        catalysts_upcoming=[],
        agent_signal_breakdown={},
        risk_assessment=RiskAssessment(correlation_notes=[], max_drawdown_scenario="fixture"),
    )


@pytest.mark.parametrize("atr", [5, 0, float("nan"), -1])
def test_unusable_atr_or_negative_stop_declines_all_order_levels(atr):
    snapshot = TechnicalSnapshot(
        ticker="TEST",
        as_of_date="2026-10-07",
        close=10,
        volume=1000,
        sma_20=8,
        atr_14=atr,
        bb_upper=12,
        high_52w=20,
    )
    with patch("stock_analysis.synthesis.risk_checker.compute_technicals", return_value=snapshot):
        plan = RiskChecker().plan_action(data(), briefing())
    assert plan.note
    assert plan.entry_limit is None
    assert plan.stop_loss is None
    assert plan.take_profit_1 is None


def test_session_declines_short_history_that_production_cannot_execute():
    from stock_analysis.backtest.session import SessionPrediction, calibrate_session_prediction
    from stock_analysis.models.agent_reports import Confidence

    prediction = SessionPrediction(
        ticker="TEST",
        as_of_date="2026-10-08",
        overall_signal=Signal.BUY,
        conviction_score=1,
        signal_convergence=1,
        agent_signals={n: Signal.BUY for n in ("fundamentals", "sentiment", "technical", "macro")},
        agent_confidences={
            n: Confidence.HIGH for n in ("fundamentals", "sentiment", "technical", "macro")
        },
    )
    result = calibrate_session_prediction(prediction, ticker_data=data())
    assert result.overall_signal == Signal.NEUTRAL
    assert result.conviction_score == 0
    assert "execution_risk_plan_declined" in result.signal_gate_reasons


def test_resumed_cloud_run_preserves_original_input_and_binds_stages():
    from stock_analysis.data.cloud import SupabaseAnalysisStore
    from stock_analysis.models.agent_reports import AnalystReports
    from tests.test_cloud_storage import MemoryClient, _analyst_reports, _settings

    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)
    run_id = store.begin_run("TEST", date(2026, 10, 8))
    original = data()
    store.save_run_input("TEST", original, date(2026, 10, 8))
    store.save_analyst_reports("TEST", _analyst_reports(), date(2026, 10, 8))
    resumed = SupabaseAnalysisStore(_settings(), run_id=run_id, client=client)
    assert resumed.load_run_input() == original
    assert resumed.resume_artifact("analyst_reports", AnalystReports)
    with pytest.raises(ValueError, match="immutable"):
        resumed.save_run_input(
            "TEST",
            original.model_copy(update={"fetched_at": datetime(2026, 10, 9)}),
            date(2026, 10, 8),
        )
    client.tables["analysis_artifacts"][0]["input_hash"] = "wrong"
    with pytest.raises(ValueError, match="input hash"):
        resumed.resume_artifact("analyst_reports", AnalystReports)


def test_pipeline_resume_never_refetches_a_frozen_run_input():
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from stock_analysis.config import Settings
    from stock_analysis.data.cloud import SupabaseAnalysisStore
    from stock_analysis.orchestrator import AnalysisPipeline
    from tests.test_cloud_storage import MemoryClient, _settings

    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)
    run_id = store.begin_run("TEST", date(2026, 10, 8))
    original = data()
    store.save_run_input("TEST", original, date(2026, 10, 8))
    recovered = SupabaseAnalysisStore(_settings(), run_id=run_id, client=client)
    fetcher = Mock()
    fetcher.resolve_symbol.return_value = "TEST"
    fetcher.fetch.side_effect = AssertionError("A resumed run must not refetch current input")
    pipeline = AnalysisPipeline(
        settings=Settings(enable_outcome_memory=False),
        fetcher=fetcher,
        as_of_date=date(2026, 10, 8),
        store=recovered,
        outcome_store=Mock(),
        run_id=run_id,
    )
    layers = AsyncMock(return_value=briefing())
    with patch.object(pipeline, "_run_layers", layers):
        asyncio.run(pipeline.run("TEST"))
    assert layers.call_args.args[1] == original
    fetcher.fetch.assert_not_called()


def test_live_fetch_retains_history_currency_and_separate_close_without_mixing_periods():
    from unittest.mock import Mock

    import pandas as pd

    from stock_analysis.data.us_market import USMarketFetcher

    stock = Mock()
    stock.info = {"shortName": "TEST", "currency": "USD", "financialCurrency": "USD"}
    columns = pd.to_datetime(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30"])
    stock.quarterly_income_stmt = pd.DataFrame(
        {
            c: {"Total Revenue": 100 + i, "Net Income": 20, "Diluted EPS": 1}
            for i, c in enumerate(columns)
        }
    )
    stock.quarterly_balance_sheet = pd.DataFrame({pd.Timestamp("2026-03-31"): {"Total Debt": 10}})
    stock.quarterly_cashflow = pd.DataFrame({pd.Timestamp("2026-03-31"): {"Free Cash Flow": 15}})
    stock.income_stmt = stock.balance_sheet = stock.cashflow = pd.DataFrame()
    stock.news = []
    stock.recommendations = pd.DataFrame()
    stock.history.return_value = pd.DataFrame(
        {"Open": [10], "High": [11], "Low": [9], "Close": [10], "Volume": [1000]},
        index=pd.to_datetime(["2026-10-07"]),
    )
    with patch("stock_analysis.data.us_market.yf.Ticker", return_value=stock):
        result = USMarketFetcher().fetch("TEST")
    assert len(result.financial_history) == 5
    assert result.financials.fiscal_period_end == date(2026, 6, 30)
    assert result.financials.fiscal_period_start == date(2026, 4, 1)
    assert result.financials.currency == "USD"
    assert result.financials.total_debt is None
    assert result.financials.free_cash_flow is None
    assert result.valuation_price.price == 10
    assert result.valuation_price.source.startswith("yahoo_plain_close")
    assert result.financials.available_as_of == result.fetched_at.date()
    assert result.financials.share_basis is None


def test_sentiment_does_not_call_model_for_expired_news():
    import asyncio
    from unittest.mock import AsyncMock

    from stock_analysis.agents.base import BaseAnalystAgent
    from stock_analysis.agents.sentiment import SentimentAgent

    packet = data().model_copy(
        update={
            "news_headlines": [
                {"title": "Ancient bullish event", "published_at": "2020-01-01T00:00:00Z"}
            ]
        }
    )
    with patch.object(
        BaseAnalystAgent, "analyze", AsyncMock(side_effect=AssertionError("stale evidence"))
    ):
        result = asyncio.run(SentimentAgent().analyze(packet))
    assert result.signal == Signal.NEUTRAL
    assert result.notable_headlines == []


def test_income_and_derived_margin_count_as_one_confidence_dimension():
    from stock_analysis.agents.fundamentals import FundamentalsAgent
    from stock_analysis.models.agent_reports import Confidence, FundamentalsReport
    from stock_analysis.models.market_data import FinancialStatements

    packet = data().model_copy(
        update={"financials": FinancialStatements(revenue=100, net_income=20, net_margin=0.2)}
    )
    report = FundamentalsReport(
        signal=Signal.BUY,
        confidence=Confidence.HIGH,
        pe_assessment="unavailable",
        margin_analysis="20%",
        debt_analysis="unavailable",
        growth_outlook="unavailable",
        key_strengths=[],
        key_risks=[],
        summary="fixture",
    )
    assert FundamentalsAgent.canonicalize_report(report, packet).confidence == Confidence.LOW


def test_issuer_financial_release_is_not_independent_sentiment():
    import asyncio
    from unittest.mock import AsyncMock

    from stock_analysis.agents.base import BaseAnalystAgent
    from stock_analysis.agents.sentiment import SentimentAgent

    packet = data().model_copy(
        update={
            "news_headlines": [
                {
                    "title": "TEST published financial results",
                    "publisher": "TEST issuer",
                    "published_at": "2026-10-07T00:00:00Z",
                }
            ]
        }
    )
    with patch.object(
        BaseAnalystAgent, "analyze", AsyncMock(side_effect=AssertionError("duplicate evidence"))
    ):
        result = asyncio.run(SentimentAgent().analyze(packet))
    assert result.signal == Signal.NEUTRAL


def test_news_window_includes_boundary_and_rejects_expired_or_future():
    from stock_analysis.data.evidence import filter_point_in_time_news

    news = [
        {"title": day, "published_at": day} for day in ("2026-09-08", "2026-09-07", "2026-10-09")
    ]
    assert [
        n["title"]
        for n in filter_point_in_time_news(news, as_of=date(2026, 10, 8), max_age_days=30)
    ] == ["2026-09-08"]


def test_live_replay_overlay_and_store_roundtrip_preserve_dated_evidence(tmp_path):
    import json

    from stock_analysis.config import Settings
    from stock_analysis.data.live_evidence import prepare_live_evidence
    from stock_analysis.data.store import DataStore

    (tmp_path / "fundamentals").mkdir()
    (tmp_path / "fundamentals/TEST.json").write_text(
        json.dumps(
            [
                {
                    "revenue": 100,
                    "net_income": 20,
                    "fiscal_period_end": "2026-06-30",
                    "fiscal_period_start": "2026-04-01",
                    "period_kind": "quarter",
                    "currency": "USD",
                    "available_as_of": "2026-08-01",
                    "availability_source": "test:filing",
                }
            ]
        )
    )
    (tmp_path / "macro.json").write_text(
        json.dumps(
            {
                "as_of_date": "2026-10-07",
                "available_as_of": "2026-10-08",
                "source": "test:macro",
                "fed_funds_rate": 4.0,
            }
        )
    )
    settings = Settings(evidence_replay_dir=str(tmp_path), news_max_age_days=7)
    result = prepare_live_evidence(data(), settings)
    assert result.financials.revenue == 100
    assert len(result.financial_history) == 1
    assert result.macro_snapshot.fed_funds_rate == 4
    assert result.news_max_age_days == 7
    assert "evidence_replay_dir" not in settings.pipeline_dump()
    store = DataStore(str(tmp_path / "store"))
    store.save_market_data("TEST", result)
    assert store.load_market_data("TEST") == result


def test_legacy_partial_stages_and_corrupt_seals_fail_closed():
    from stock_analysis.data.cloud import SupabaseAnalysisStore
    from tests.test_cloud_storage import MemoryClient, _analyst_reports, _settings

    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)
    run_id = store.begin_run("TEST", date(2026, 10, 8))
    store.save_analyst_reports("TEST", _analyst_reports(), date(2026, 10, 8))
    with pytest.raises(ValueError, match="Unsealed legacy"):
        store.load_run_input()
    client.tables["analysis_artifacts"] = []
    store.save_run_input("TEST", data(), date(2026, 10, 8))
    client.tables["analysis_run_inputs"][0]["payload"]["info"]["symbol"] = "CORRUPT"
    recovered = SupabaseAnalysisStore(_settings(), run_id=run_id, client=client)
    with pytest.raises(ValueError, match="hash mismatch"):
        recovered.load_run_input()


def test_live_capture_cannot_initialize_a_historical_run():
    from stock_analysis.data.run_input import validate_input

    with pytest.raises(ValueError, match="historical"):
        validate_input(data(), date(2026, 10, 7))


def test_cloud_pipeline_finishes_and_reuses_hash_bound_layers_without_refetch():
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from stock_analysis.config import Settings
    from stock_analysis.data.cloud import SupabaseAnalysisStore
    from stock_analysis.models.debate import DebateResult
    from stock_analysis.orchestrator import AnalysisPipeline
    from tests.test_cloud_storage import MemoryClient, _analyst_reports, _settings

    settings = Settings(
        storage_backend="supabase", enable_outcome_memory=False, enable_research_manager=False
    )
    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)
    run_id = store.begin_run("TEST", date(2026, 10, 8))
    store.save_run_input("TEST", data(), date(2026, 10, 8))
    reports = _analyst_reports()
    store.save_analyst_reports("TEST", reports, date(2026, 10, 8))
    debate = DebateResult(
        ticker="TEST",
        rounds=[],
        bull_case_summary="fixture",
        bear_case_summary="fixture",
        key_points_of_agreement=[],
        key_points_of_disagreement=[],
        unresolved_uncertainties=[],
    )
    fetcher = Mock()
    fetcher.resolve_symbol.return_value = "TEST"
    fetcher.fetch.side_effect = AssertionError("resume cannot refetch")
    synth = AsyncMock(return_value=briefing())
    debate_call = AsyncMock(return_value=debate)
    with (
        patch("stock_analysis.orchestrator.DebateEngine.run", debate_call),
        patch("stock_analysis.orchestrator.SynthesizerAgent.synthesize", synth),
    ):
        first = AnalysisPipeline(
            settings=settings,
            fetcher=fetcher,
            as_of_date=date(2026, 10, 8),
            store=store,
            outcome_store=Mock(),
            run_id=run_id,
        )
        result = asyncio.run(first.run("TEST"))
        assert result.action_plan.note  # Actual deterministic risk declines one-bar history.
        resumed = SupabaseAnalysisStore(_settings(), run_id=run_id, client=client)
        second = AnalysisPipeline(
            settings=settings,
            fetcher=fetcher,
            as_of_date=date(2026, 10, 8),
            store=resumed,
            outcome_store=Mock(),
            run_id=run_id,
        )
        asyncio.run(second.run("TEST"))
    synth.assert_awaited_once()
    debate_call.assert_awaited_once()
    assert client.tables["analysis_runs"][0]["status"] == "completed"
    digest = client.tables["analysis_run_inputs"][0]["input_hash"]
    assert all(row["input_hash"] == digest for row in client.tables["analysis_artifacts"])
    fetcher.fetch.assert_not_called()


def test_api_backtest_gated_execution_zeroes_score_and_preserves_raw(tmp_path):
    import asyncio
    from unittest.mock import AsyncMock, Mock

    import pandas as pd

    from stock_analysis.backtest.runner import Backtester
    from stock_analysis.config import Settings
    from stock_analysis.models.synthesis import ActionPlan

    view = briefing()
    view.action_plan = ActionPlan(note="Insufficient technical history")
    pipeline = Mock()
    pipeline.run = AsyncMock(return_value=view)
    prices = pd.DataFrame(
        {"Open": [10, 11], "Close": [10, 11]}, index=pd.to_datetime(["2026-10-09", "2026-11-07"])
    )
    backtester = Backtester(settings=Settings(data_dir=str(tmp_path)))
    with patch("stock_analysis.backtest.runner.AnalysisPipeline", return_value=pipeline):
        trial = asyncio.run(backtester._run_one("TEST", date(2026, 10, 8), prices))
    assert trial.overall_signal == Signal.NEUTRAL
    assert trial.conviction_score == 0
    assert trial.raw_conviction_score == 1


def test_sealed_provider_metadata_keeps_capture_semantics_across_midnight():
    import json

    from stock_analysis.data.evidence import current_recommendations_are_usable
    from stock_analysis.models.market_data import TickerData
    from stock_analysis.prompt_context import build_evidence_envelope

    packet = data().model_dump(mode="json")
    packet.update(
        fetched_at="2026-10-07T23:59:00",
        provider_capture="current",
        analyst_recommendations=[{"period": "0m", "strongBuy": 5}],
    )
    captured = TickerData.model_validate(packet)
    envelope = json.loads(build_evidence_envelope(captured))
    assert envelope["sentiment"]["recommendation_count"] == 1
    assert current_recommendations_are_usable(
        captured.analyst_recommendations, captured.fetched_at.date(), provider_capture="current"
    )
    assert not current_recommendations_are_usable(
        captured.analyst_recommendations, captured.fetched_at.date(), provider_capture="historical"
    )


def test_additive_model_defaults_do_not_change_a_stored_input_identity():
    from stock_analysis.data.cloud import SupabaseAnalysisStore
    from stock_analysis.data.run_input import input_digest
    from tests.test_cloud_storage import MemoryClient, _settings

    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)
    run_id = store.begin_run("TEST", date(2026, 10, 8))
    store.save_run_input("TEST", data(), date(2026, 10, 8))
    row = client.tables["analysis_run_inputs"][0]
    # Simulate a writer whose typed model predates these optional fields.
    row["payload"].pop("provider_capture")
    row["payload"].pop("news_max_age_days")
    row["input_hash"] = input_digest(row["payload"], date(2026, 10, 8))
    digest = row["input_hash"]
    resumed = SupabaseAnalysisStore(_settings(), run_id=run_id, client=client)
    original = resumed.load_run_input()
    resumed.save_run_input("TEST", original, date(2026, 10, 8))
    assert row["input_hash"] == digest
    assert "provider_capture" not in row["payload"]


def test_session_packet_rejects_internal_capture_after_manifest_cutoff(tmp_path):
    import json

    from stock_analysis.backtest.session import SessionManifest, _load_sealed_packets

    packet = {
        "ticker": "TEST",
        "market": "US",
        "as_of_date": "2026-10-07",
        "horizon_days": 30,
        "do_not_use_future_prices": True,
        "ticker_data": data().model_dump(mode="json"),
    }
    path = tmp_path / "packets/TEST/2026-10-07.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(packet))
    manifest = SessionManifest(
        market="US",
        tickers=["TEST"],
        as_of_dates=[date(2026, 10, 7)],
        horizon_days=30,
        lookback_days=365,
        created_at=date(2026, 10, 9),
        trials=[
            {"ticker": "TEST", "as_of_date": "2026-10-07", "packet": "packets/TEST/2026-10-07.json"}
        ],
    )
    with pytest.raises(ValueError, match="cutoff"):
        _load_sealed_packets(tmp_path, manifest)


def test_session_cannot_claim_absent_fundamental_or_macro_evidence():
    from stock_analysis.backtest.session import SessionPrediction, calibrate_session_prediction
    from stock_analysis.models.agent_reports import Confidence

    prediction = SessionPrediction(
        ticker="TEST",
        as_of_date="2026-10-08",
        overall_signal=Signal.BUY,
        conviction_score=1,
        signal_convergence=1,
        agent_signals={n: Signal.BUY for n in ("fundamentals", "technical", "sentiment", "macro")},
        agent_confidences={
            n: Confidence.HIGH for n in ("fundamentals", "technical", "sentiment", "macro")
        },
    )
    result = calibrate_session_prediction(
        prediction, ticker_data=data(), fundamentals_available=True, macro_available=True
    )
    assert result.agent_signals["fundamentals"] == Signal.NEUTRAL
    assert result.agent_signals["macro"] == Signal.NEUTRAL
    assert result.overall_signal == Signal.NEUTRAL


def test_session_score_coverage_does_not_trust_positive_evidence_flags(tmp_path):
    import json

    import pandas as pd

    from stock_analysis.backtest.session import (
        SessionManifest,
        SessionPrediction,
        score_session_bundle,
    )

    as_of = date(2026, 10, 8)
    trial = {"ticker": "TEST", "as_of_date": str(as_of), "packet": "packets/TEST/2026-10-08.json"}
    path = tmp_path / trial["packet"]
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "ticker": "TEST",
                "market": "US",
                "as_of_date": str(as_of),
                "horizon_days": 30,
                "do_not_use_future_prices": True,
                "ticker_data": data().model_dump(mode="json"),
                "evidence_availability": {"fundamentals": True, "macro": True, "sentiment": True},
            }
        )
    )
    manifest = SessionManifest(
        market="US",
        tickers=["TEST"],
        as_of_dates=[as_of],
        horizon_days=30,
        lookback_days=365,
        created_at=as_of,
        trials=[trial],
    )
    (tmp_path / "manifest.json").write_text(manifest.model_dump_json())
    prediction = SessionPrediction(
        ticker="TEST",
        as_of_date=as_of,
        overall_signal="buy",
        conviction_score=1,
        signal_convergence=1,
        agent_signals={n: "buy" for n in ("fundamentals", "technical", "sentiment", "macro")},
        agent_confidences={n: "high" for n in ("fundamentals", "technical", "sentiment", "macro")},
    )
    (tmp_path / "predictions.json").write_text(json.dumps([prediction.model_dump(mode="json")]))
    series = pd.DataFrame(
        {
            "Open": [10, 11],
            "High": [11, 12],
            "Low": [9, 10],
            "Close": [10, 11],
            "Volume": [1000, 1000],
        },
        index=pd.to_datetime(["2026-10-09", "2026-11-07"]),
    )
    with patch(
        "stock_analysis.backtest.session.Backtester._fetch_price_series", return_value=series
    ):
        result = score_session_bundle(tmp_path)
    coverage = result.settings["evidence_coverage"]["available"]
    assert coverage["fundamentals"] == coverage["macro"] == coverage["sentiment"] == 0
    assert result.trials[0].overall_signal == Signal.NEUTRAL
