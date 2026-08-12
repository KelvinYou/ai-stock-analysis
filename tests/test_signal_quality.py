import asyncio
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from pydantic import ValidationError

from stock_analysis.agents.macro import MacroFXAgent, build_macro_snapshot
from stock_analysis.agents.sentiment import SentimentAgent
from stock_analysis.agents.technical import build_indicator_payload
from stock_analysis.backtest.fetcher import BacktestFetcher
from stock_analysis.backtest.runner import execution_signal
from stock_analysis.backtest.session import (
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
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)
from stock_analysis.models.synthesis import ConvictionScore
from stock_analysis.synthesis.synthesizer import (
    calibrate_conviction_score,
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


    def test_macro_snapshot_is_explicitly_unavailable_and_point_in_time(self):
        snapshot = build_macro_snapshot(_ticker_data())

        self.assertEqual(snapshot["status"], "unavailable")
        self.assertEqual(snapshot["as_of"], "2025-07-30")
        self.assertEqual(snapshot["source"], "not_configured")
        self.assertIsNone(snapshot["fed"]["fed_funds_rate"])
        self.assertNotIn("April 2026", str(snapshot))


    def test_missing_sentiment_and_macro_data_force_neutral_low_confidence(self):
        sentiment = asyncio.run(SentimentAgent().analyze(_ticker_data()))
        macro = asyncio.run(MacroFXAgent().analyze(_ticker_data()))

        self.assertEqual(sentiment.signal, Signal.NEUTRAL)
        self.assertEqual(sentiment.confidence, Confidence.LOW)
        self.assertEqual(macro.signal, Signal.NEUTRAL)
        self.assertEqual(macro.confidence, Confidence.LOW)


    def test_backtest_does_not_use_current_shares_for_historical_valuation(self):
        class FakeStock:
            info = {
                "sharesOutstanding": 1_000_000,
                "shortName": "Test Co",
                "sector": "Technology",
                "industry": "Software",
                "currency": "USD",
            }

        ticker_data = _ticker_data()
        info = BacktestFetcher(date(2025, 7, 30))._build_info(
            "TEST",
            FakeStock(),
            ticker_data.price_history,
            FinancialStatements(net_income=100_000),
        )

        self.assertIsNone(info.market_cap)
        self.assertIsNone(info.pe_ratio)


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
        self.assertEqual(calibrated.conviction_score, 0.2727)
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
                position_size_suggestion="0%",
                correlation_notes=[],
                max_drawdown_scenario="unknown",
            ),
            action_plan=ActionPlan(note="wait"),
            agent_signal_breakdown={},
        )
        self.assertEqual(execution_signal(briefing), Signal.NEUTRAL)
