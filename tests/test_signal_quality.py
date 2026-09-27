import asyncio
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd
from pydantic import ValidationError

from stock_analysis.agents.fundamentals import FundamentalsAgent
from stock_analysis.agents.macro import MacroFXAgent, build_macro_snapshot
from stock_analysis.agents.sentiment import SentimentAgent
from stock_analysis.agents.technical import build_indicator_payload
from stock_analysis.backtest.fetcher import BacktestFetcher
from stock_analysis.backtest.runner import execution_signal
from stock_analysis.backtest.session import (
    SESSION_MANIFEST_VERSION,
    SESSION_MODE,
    SessionManifest,
    SessionPrediction,
    calibrate_session_prediction,
    compute_session_consensus_score,
    compute_session_convergence,
)
from stock_analysis.data.technicals import compute_technicals
from stock_analysis.models.agent_reports import (
    AnalystReports,
    Confidence,
    FundamentalsReport,
    MacroFXReport,
    SentimentReport,
    Signal,
    TechnicalReport,
)
from stock_analysis.models.market_data import (
    FinancialStatements,
    MacroSnapshot,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)
from stock_analysis.models.synthesis import Briefing, ConvictionScore, RiskAssessment
from stock_analysis.synthesis.synthesizer import (
    calibrate_conviction_score,
    canonicalize_agent_signal_breakdown,
    compute_directional_consensus,
    compute_signal_convergence,
)


def _reports(
    fundamentals: Signal = Signal.BUY,
    sentiment: Signal = Signal.BUY,
    technical: Signal = Signal.BUY,
    macro: Signal = Signal.BUY,
    confidence: Confidence = Confidence.HIGH,
) -> AnalystReports:
    return AnalystReports(
        fundamentals=FundamentalsReport(
            signal=fundamentals,
            confidence=confidence,
            pe_assessment="ok",
            margin_analysis="ok",
            debt_analysis="ok",
            growth_outlook="ok",
            key_risks=[],
            key_strengths=[],
            summary="summary",
        ),
        sentiment=SentimentReport(
            signal=sentiment,
            confidence=confidence,
            news_tone="mixed",
            news_summary="summary",
            key_themes=[],
            notable_headlines=[],
            summary="summary",
        ),
        technical=TechnicalReport(
            signal=technical,
            confidence=confidence,
            trend="mixed",
            rsi_assessment="ok",
            macd_assessment="ok",
            volume_assessment="ok",
            support_levels=[],
            resistance_levels=[],
            summary="summary",
        ),
        macro=MacroFXReport(
            signal=macro,
            confidence=confidence,
            fed_impact="unknown",
            interest_rate_outlook="unknown",
            sector_macro_factors=[],
            geopolitical_risks=[],
            summary="summary",
        ),
    )


def _ticker_data() -> TickerData:
    start = date(2025, 1, 1)
    bars = [
        PriceBar(
            date=start + timedelta(days=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=1_000_000 + index,
        )
        for index in range(210)
    ]
    return TickerData(
        info=TickerInfo(
            symbol="TEST",
            name="Test Co",
            sector="Technology",
            industry="Software",
            market=Market.US,
            currency="USD",
        ),
        price_history=bars,
        financials=FinancialStatements(),
        fetched_at=datetime(2025, 7, 30, 12, 0, 0),
    )


class SignalQualityTests(unittest.TestCase):
    def test_convergence_is_confidence_weighted_and_neutral_penalises_agreement(self):
        self.assertEqual(compute_signal_convergence(_reports()), 1.0)
        self.assertEqual(compute_signal_convergence(_reports(macro=Signal.NEUTRAL)), 0.75)
        self.assertEqual(compute_signal_convergence(_reports(macro=Signal.SELL)), 0.75)
        self.assertEqual(compute_directional_consensus(_reports(macro=Signal.NEUTRAL)), 0.75)
        self.assertEqual(compute_directional_consensus(_reports(macro=Signal.SELL)), 0.5)


    def test_llm_conviction_cannot_exceed_analyst_consensus(self):
        reports = _reports(macro=Signal.NEUTRAL)
        consensus = compute_directional_consensus(reports)
        self.assertEqual(calibrate_conviction_score(Signal.BUY, 0.9, consensus), 0.75)
        self.assertEqual(calibrate_conviction_score(Signal.SELL, -0.9, consensus), 0.0)
        self.assertEqual(calibrate_conviction_score(Signal.NEUTRAL, 0.9, consensus), 0.0)


    def test_synthesizer_applies_consensus_calibration_and_historical_date(self):
        from stock_analysis.models.debate import DebateResult
        from stock_analysis.synthesis.synthesizer import SynthesizerAgent

        class FakeResult:
            structured_output = {
                "overall_signal": "buy",
                "conviction": {
                    "score": 0.9,
                    "signal_convergence": 0.99,
                    "explanation": "strong thesis",
                },
                "executive_summary": "summary",
                "bull_case": "bull",
                "bear_case": "bear",
                "key_uncertainties": [],
                "catalysts_upcoming": [],
                "agent_signal_breakdown": {},
            }
            result = None

        async def fake_query_with_retry(**kwargs):
            return FakeResult()

        debate = DebateResult(
            ticker="TEST",
            rounds=[],
            bull_case_summary="bull",
            bear_case_summary="bear",
            key_points_of_agreement=[],
            key_points_of_disagreement=[],
            unresolved_uncertainties=[],
        )
        with patch(
            "stock_analysis.synthesis.synthesizer.query_with_retry",
            new=fake_query_with_retry,
        ):
            briefing = asyncio.run(
                SynthesizerAgent().synthesize(_ticker_data(), _reports(macro=Signal.NEUTRAL), debate)
            )

        self.assertEqual(briefing.conviction.score, 0.75)
        self.assertEqual(briefing.conviction.signal_convergence, 0.75)
        self.assertEqual(briefing.date, "2025-07-30")
        self.assertEqual(
            briefing.agent_signal_breakdown,
            {
                "fundamentals": "buy",
                "sentiment": "buy",
                "technical": "buy",
                "macro": "neutral",
            },
        )


    def test_cached_briefing_attribution_is_repaired_without_rewriting_thesis(self):
        stale = Briefing(
            ticker="TEST",
            date="2025-07-30",
            overall_signal=Signal.BUY,
            conviction=ConvictionScore(
                score=0.5,
                signal_convergence=0.75,
                explanation="keep this score",
            ),
            executive_summary="keep this summary",
            bull_case="bull",
            bear_case="bear",
            key_uncertainties=[],
            catalysts_upcoming=[],
            risk_assessment=RiskAssessment(
                correlation_notes=[],
                max_drawdown_scenario="keep this risk",
            ),
            agent_signal_breakdown={"fundamentals": "sell"},
        )

        repaired = canonicalize_agent_signal_breakdown(stale, _reports(macro=Signal.NEUTRAL))

        self.assertIsNot(repaired, stale)
        self.assertEqual(repaired.executive_summary, stale.executive_summary)
        self.assertEqual(repaired.conviction, stale.conviction)
        self.assertEqual(
            repaired.agent_signal_breakdown,
            {
                "fundamentals": "buy",
                "sentiment": "buy",
                "technical": "buy",
                "macro": "neutral",
            },
        )


    def test_synthesizer_gates_weak_direction_to_neutral(self):
        from stock_analysis.models.debate import DebateResult
        from stock_analysis.synthesis.synthesizer import SynthesizerAgent

        class FakeResult:
            structured_output = {
                "overall_signal": "buy",
                "conviction": {
                    "score": 0.2,
                    "signal_convergence": 0.99,
                    "explanation": "weak thesis",
                },
                "executive_summary": "summary",
                "bull_case": "bull",
                "bear_case": "bear",
                "key_uncertainties": [],
                "catalysts_upcoming": [],
            }
            result = None

        async def fake_query_with_retry(**kwargs):
            return FakeResult()

        debate = DebateResult(
            ticker="TEST",
            rounds=[],
            bull_case_summary="bull",
            bear_case_summary="bear",
            key_points_of_agreement=[],
            key_points_of_disagreement=[],
            unresolved_uncertainties=[],
        )
        with patch(
            "stock_analysis.synthesis.synthesizer.query_with_retry",
            new=fake_query_with_retry,
        ):
            briefing = asyncio.run(
                SynthesizerAgent().synthesize(
                    _ticker_data(), _reports(macro=Signal.NEUTRAL), debate
                )
            )

        self.assertEqual(briefing.overall_signal, Signal.NEUTRAL)
        self.assertEqual(briefing.conviction.score, 0.0)


    def test_conviction_score_has_contract_bounds(self):
        with self.assertRaises(ValidationError):
            ConvictionScore(score=1.01, signal_convergence=0.5, explanation="x")
        with self.assertRaises(ValidationError):
            ConvictionScore(score=0.1, signal_convergence=-0.01, explanation="x")


    def test_technical_agent_uses_shared_ema_snapshot(self):
        ticker_data = _ticker_data()
        snapshot = compute_technicals("TEST", ticker_data.price_history)
        payload = build_indicator_payload(ticker_data)

        self.assertEqual(payload["as_of_date"], snapshot.as_of_date.isoformat())
        self.assertEqual(payload["macd"]["macd_line"], snapshot.macd_line)
        self.assertEqual(payload["macd"]["signal_line"], snapshot.macd_signal)
        self.assertEqual(payload["macd"]["histogram"], snapshot.macd_histogram)
        self.assertEqual(payload["sma_50"], snapshot.sma_50)
        self.assertEqual(payload["sma_200"], snapshot.sma_200)
        self.assertEqual(payload["atr_14"], snapshot.atr_14)
        self.assertEqual(payload["bollinger"]["pct"], snapshot.bb_pct)
        self.assertEqual(payload["volume"]["ratio"], snapshot.volume_ratio)
        self.assertEqual(payload["52_week"]["pct_from_high"], snapshot.pct_from_52w_high)

    def test_technical_series_is_aligned_and_ends_at_snapshot(self):
        snapshot = compute_technicals("TEST", _ticker_data().price_history)

        self.assertEqual(len(snapshot.series), 210)
        self.assertIsNone(snapshot.series[0].sma_20)
        self.assertIsNone(snapshot.series[13].rsi_14)
        self.assertEqual(snapshot.series[-1].date, snapshot.as_of_date)
        self.assertEqual(snapshot.series[-1].sma_20, snapshot.sma_20)
        self.assertEqual(snapshot.series[-1].sma_200, snapshot.sma_200)
        self.assertEqual(snapshot.series[-1].rsi_14, snapshot.rsi_14)
        self.assertEqual(snapshot.series[-1].macd_histogram, snapshot.macd_histogram)
        self.assertEqual(snapshot.series[-1].bb_pct, snapshot.bb_pct)


    def test_macro_snapshot_is_explicitly_unavailable_and_point_in_time(self):
        snapshot = build_macro_snapshot(_ticker_data())

        self.assertEqual(snapshot["status"], "unavailable")
        self.assertEqual(snapshot["as_of"], "2025-07-30")
        self.assertEqual(snapshot["source"], "not_configured")
        self.assertIsNone(snapshot["fed"]["fed_funds_rate"])
        self.assertNotIn("April 2026", str(snapshot))


    def test_macro_snapshot_requires_observation_and_availability_before_as_of(self):
        ticker_data = _ticker_data().model_copy(
            update={
                "macro_snapshot": MacroSnapshot(
                    as_of_date=date(2025, 7, 29),
                    available_as_of=date(2025, 7, 30),
                    source="test",
                    fed_funds_rate=4.5,
                )
            }
        )

        snapshot = build_macro_snapshot(ticker_data)

        self.assertEqual(snapshot["status"], "available")
        self.assertEqual(snapshot["available_as_of"], "2025-07-30")
        self.assertEqual(snapshot["fed"]["fed_funds_rate"], 4.5)


    def test_missing_sentiment_and_macro_data_force_neutral_low_confidence(self):
        sentiment = asyncio.run(SentimentAgent().analyze(_ticker_data()))
        macro = asyncio.run(MacroFXAgent().analyze(_ticker_data()))

        self.assertEqual(sentiment.signal, Signal.NEUTRAL)
        self.assertEqual(sentiment.confidence, Confidence.LOW)
        self.assertEqual(macro.signal, Signal.NEUTRAL)
        self.assertEqual(macro.confidence, Confidence.LOW)


    def test_undated_news_is_not_sent_to_sentiment_agent(self):
        ticker_data = _ticker_data().model_copy(
            update={"news_headlines": [{"title": "Undated headline"}]}
        )

        report = asyncio.run(SentimentAgent().analyze(ticker_data))

        self.assertEqual(report.signal, Signal.NEUTRAL)
        self.assertEqual(report.confidence, Confidence.LOW)
        self.assertIn("unavailable", report.summary.lower())


    def test_missing_fundamental_data_fails_closed_without_llm(self):
        report = asyncio.run(FundamentalsAgent().analyze(_ticker_data()))

        self.assertEqual(report.signal, Signal.NEUTRAL)
        self.assertEqual(report.confidence, Confidence.LOW)
        self.assertIn("unavailable", report.summary.lower())


    def test_backtest_does_not_use_current_shares_for_historical_valuation(self):
        class FakeStock:
            @property
            def info(self):
                return {"shortName": "Future Rebrand", "currency": "EUR"}

        ticker_data = _ticker_data()
        info = BacktestFetcher(date(2025, 7, 30))._build_info(
            "TEST",
            FakeStock(),
            ticker_data.price_history,
            FinancialStatements(net_income=100_000),
        )

        self.assertIsNone(info.market_cap)
        self.assertIsNone(info.pe_ratio)
        self.assertIsNone(info.sector)
        self.assertIsNone(info.industry)
        self.assertEqual(info.name, "TEST")
        self.assertEqual(info.currency, "USD")

    def test_backtest_price_history_drops_unusable_ohlc_bars(self):
        class FakeStock:
            def history(self, **kwargs):
                return pd.DataFrame(
                    {
                        "Open": [10.0, 11.0, 12.0],
                        "High": [10.5, float("nan"), 12.5],
                        "Low": [9.5, 10.5, 11.5],
                        "Close": [10.2, 11.2, 12.2],
                        "Volume": [1_000, 1_100, 1_200],
                    },
                    index=pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-04"]),
                )

        bars = BacktestFetcher(date(2025, 1, 4))._fetch_price_history(
            FakeStock(), "TEST"
        )

        self.assertEqual([bar.date for bar in bars], [date(2025, 1, 2), date(2025, 1, 4)])

    def test_backtest_fundamentals_use_sec_filing_date(self):
        period_q3 = pd.Timestamp("2025-09-30")
        period_q2 = pd.Timestamp("2025-06-30")

        class FakeStock:
            quarterly_income_stmt = pd.DataFrame(
                {
                    period_q3: {
                        "Total Revenue": 900.0,
                        "Net Income": 90.0,
                        "Gross Profit": 450.0,
                        "Operating Income": 180.0,
                    },
                    period_q2: {
                        "Total Revenue": 800.0,
                        "Net Income": 80.0,
                        "Gross Profit": 400.0,
                        "Operating Income": 160.0,
                    },
                }
            )
            quarterly_balance_sheet = pd.DataFrame(
                {
                    period_q3: {"Total Debt": 30.0, "Stockholders Equity": 700.0},
                    period_q2: {"Total Debt": 20.0, "Stockholders Equity": 650.0},
                }
            )
            quarterly_cashflow = pd.DataFrame(
                {
                    period_q3: {"Free Cash Flow": 120.0},
                    period_q2: {"Free Cash Flow": 110.0},
                }
            )
            sec_filings = [
                {
                    "type": "10-Q",
                    "date": date(2025, 10, 30),
                    "exhibits": {"10-Q": "https://example.test/20250930.htm"},
                },
                {
                    "type": "10-Q",
                    "date": date(2025, 7, 31),
                    "exhibits": {"10-Q": "https://example.test/20250630.htm"},
                },
            ]

        before_q3_filing = BacktestFetcher(date(2025, 10, 29))._extract_financials(
            FakeStock()
        )
        self.assertIsNotNone(before_q3_filing)
        self.assertEqual(before_q3_filing.fiscal_period_end, date(2025, 6, 30))
        self.assertEqual(before_q3_filing.available_as_of, date(2025, 7, 31))
        self.assertEqual(before_q3_filing.availability_source, "yahoo_sec_filing")
        self.assertEqual(before_q3_filing.revenue, 800.0)

        after_q3_filing = BacktestFetcher(date(2025, 10, 31))._extract_financials(
            FakeStock()
        )
        self.assertIsNotNone(after_q3_filing)
        self.assertEqual(after_q3_filing.fiscal_period_end, date(2025, 9, 30))
        self.assertEqual(after_q3_filing.available_as_of, date(2025, 10, 30))
        self.assertEqual(after_q3_filing.revenue, 900.0)

    def test_backtest_drops_financials_without_a_matching_filing_date(self):
        period = pd.Timestamp("2025-06-30")

        class FakeStock:
            quarterly_income_stmt = pd.DataFrame(
                {period: {"Total Revenue": 800.0, "Net Income": 80.0}}
            )
            quarterly_balance_sheet = pd.DataFrame({period: {}})
            quarterly_cashflow = pd.DataFrame({period: {}})
            sec_filings = []

        self.assertIsNone(
            BacktestFetcher(date(2025, 8, 1))._extract_financials(FakeStock())
        )

        class EmptyValuesStock:
            quarterly_income_stmt = pd.DataFrame({period: {"Other Metric": 1.0}})
            quarterly_balance_sheet = pd.DataFrame({period: {}})
            quarterly_cashflow = pd.DataFrame({period: {}})
            sec_filings = [
                {
                    "type": "10-Q",
                    "date": date(2025, 7, 31),
                    "exhibits": {"10-Q": "https://example.test/20250630.htm"},
                }
            ]

        self.assertIsNone(
            BacktestFetcher(date(2025, 8, 1))._extract_financials(EmptyValuesStock())
        )


    def test_session_convergence_is_recomputed_and_weak_direction_is_gated(self):
        signals = {
            "fundamentals": Signal.BUY,
            "sentiment": Signal.NEUTRAL,
            "technical": Signal.NEUTRAL,
            "macro": Signal.NEUTRAL,
        }
        self.assertEqual(compute_session_convergence(signals), 0.25)

        prediction = SessionPrediction(
            ticker="TEST",
            as_of_date=date(2025, 7, 30),
            overall_signal=Signal.BUY,
            conviction_score=0.2,
            signal_convergence=1.0,
            agent_signals=signals,
        )
        calibrated = calibrate_session_prediction(prediction)
        self.assertEqual(calibrated.signal_convergence, 0.25)
        self.assertEqual(calibrated.overall_signal, Signal.NEUTRAL)

    def test_unavailable_agents_are_excluded_from_consensus_denominator(self):
        signals = {
            "fundamentals": Signal.BUY,
            "technical": Signal.BUY,
            "sentiment": Signal.NEUTRAL,
            "macro": Signal.NEUTRAL,
        }
        available = {"fundamentals", "technical"}

        self.assertEqual(
            compute_session_convergence(signals, available_agents=available),
            1.0,
        )
        self.assertEqual(
            compute_session_consensus_score(signals, available_agents=available),
            1.0,
        )

    def test_session_mode_is_provider_neutral(self):
        self.assertEqual(SESSION_MODE, "in-session")

    def test_session_manifest_versions_evidence_contract(self):
        manifest = SessionManifest(
            market="US",
            tickers=["TEST"],
            as_of_dates=[date(2025, 7, 30)],
            horizon_days=30,
            lookback_days=365,
            created_at=date(2025, 7, 30),
            trials=[],
        )
        self.assertEqual(manifest.version, SESSION_MANIFEST_VERSION)
        self.assertEqual(manifest.version, 3)
        legacy = manifest.model_copy(update={"version": 2})
        self.assertEqual(
            SessionManifest.model_validate_json(legacy.model_dump_json()).version,
            2,
        )


    def test_session_conviction_uses_net_analyst_consensus(self):
        signals = {
            "fundamentals": Signal.BUY,
            "sentiment": Signal.NEUTRAL,
            "technical": Signal.BUY,
            "macro": Signal.NEUTRAL,
        }
        self.assertEqual(compute_session_consensus_score(signals), 0.5)

        prediction = SessionPrediction(
            ticker="TEST",
            as_of_date=date(2025, 7, 30),
            overall_signal=Signal.BUY,
            conviction_score=0.2,
            signal_convergence=1.0,
            agent_signals=signals,
        )
        calibrated = calibrate_session_prediction(prediction)
        self.assertEqual(calibrated.conviction_score, 0.5)
        self.assertEqual(calibrated.overall_signal, Signal.BUY)


    def test_session_calibration_ignores_agents_without_point_in_time_evidence(self):
        prediction = SessionPrediction(
            ticker="TEST",
            as_of_date=date(2025, 7, 30),
            overall_signal=Signal.BUY,
            conviction_score=0.9,
            signal_convergence=1.0,
            agent_signals={
                "fundamentals": Signal.BUY,
                "sentiment": Signal.NEUTRAL,
                "technical": Signal.NEUTRAL,
                "macro": Signal.BUY,
            },
        )

        calibrated = calibrate_session_prediction(prediction, macro_available=False)

        self.assertEqual(calibrated.agent_signals["macro"], Signal.NEUTRAL)
        self.assertEqual(calibrated.conviction_score, 0.3333)
        self.assertEqual(calibrated.overall_signal, Signal.NEUTRAL)

    def test_session_calibration_ignores_fundamentals_without_point_in_time_evidence(self):
        prediction = SessionPrediction(
            ticker="TEST",
            as_of_date=date(2025, 7, 30),
            overall_signal=Signal.BUY,
            conviction_score=0.9,
            signal_convergence=1.0,
            agent_signals={
                "fundamentals": Signal.BUY,
                "sentiment": Signal.NEUTRAL,
                "technical": Signal.NEUTRAL,
                "macro": Signal.NEUTRAL,
            },
        )

        calibrated = calibrate_session_prediction(
            prediction,
            fundamentals_available=False,
        )

        self.assertEqual(calibrated.agent_signals["fundamentals"], Signal.NEUTRAL)
        self.assertEqual(calibrated.agent_confidences["fundamentals"], Confidence.LOW)
        self.assertEqual(calibrated.overall_signal, Signal.NEUTRAL)


    def test_backtest_uses_only_executable_briefing_signal(self):
        from stock_analysis.models.synthesis import (
            ActionPlan,
            Briefing,
            ConvictionScore,
            RiskAssessment,
        )

        briefing = Briefing(
            ticker="TEST",
            date="2025-07-30",
            overall_signal=Signal.BUY,
            conviction=ConvictionScore(
                score=0.1,
                signal_convergence=0.25,
                explanation="weak",
            ),
            executive_summary="summary",
            bull_case="bull",
            bear_case="bear",
            key_uncertainties=[],
            catalysts_upcoming=[],
            risk_assessment=RiskAssessment(
                correlation_notes=[],
                max_drawdown_scenario="unknown",
            ),
            action_plan=ActionPlan(note="wait"),
            agent_signal_breakdown={},
        )
        self.assertEqual(execution_signal(briefing), Signal.NEUTRAL)
