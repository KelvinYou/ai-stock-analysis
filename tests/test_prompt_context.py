from datetime import date, datetime, timedelta

from stock_analysis.agents.technical import build_indicator_payload
from stock_analysis.debate.engine import DebateEngine
from stock_analysis.models.agent_reports import (
    AnalystReports,
    Confidence,
    FundamentalsReport,
    MacroFXReport,
    SentimentReport,
    Signal,
    TechnicalReport,
)
from stock_analysis.models.debate import DebateResult
from stock_analysis.models.market_data import (
    FinancialStatements,
    MacroSnapshot,
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)
from stock_analysis.prompt_context import build_analyst_reports_context, build_evidence_envelope
from stock_analysis.synthesis.synthesizer import SynthesizerAgent


def _reports() -> AnalystReports:
    return AnalystReports(
        fundamentals=FundamentalsReport(
            signal=Signal.BUY,
            confidence=Confidence.MEDIUM,
            pe_assessment="PE 20x",
            margin_analysis="Margins stable",
            debt_analysis="Debt manageable",
            growth_outlook="Growth uncertain",
            key_risks=["Competition"],
            key_strengths=["Cash generation"],
            summary="Fundamental summary",
        ),
        sentiment=SentimentReport(
            signal=Signal.NEUTRAL,
            confidence=Confidence.LOW,
            news_tone="mixed",
            news_summary="One dated headline",
            key_themes=["Demand"],
            notable_headlines=["Headline citation"],
            summary="Sentiment summary",
        ),
        technical=TechnicalReport(
            signal=Signal.BUY,
            confidence=Confidence.MEDIUM,
            trend="uptrend",
            rsi_14=55,
            rsi_assessment="Neutral-positive",
            macd_assessment="Positive histogram",
            volume_assessment="Confirmed",
            support_levels=[95],
            resistance_levels=[110],
            summary="Technical summary",
        ),
        macro=MacroFXReport(
            signal=Signal.NEUTRAL,
            confidence=Confidence.LOW,
            fed_impact="Unavailable",
            interest_rate_outlook="Unavailable",
            fx_impact=None,
            sector_macro_factors=["Rates"],
            geopolitical_risks=["Supply chain"],
            summary="Macro summary",
        ),
    )


def _ticker_data() -> TickerData:
    start = date(2025, 1, 1)
    bars = [
        PriceBar(
            date=start + timedelta(days=i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100 + i,
            volume=1_000,
        )
        for i in range(210)
    ]
    return TickerData(
        info=TickerInfo(
            symbol="TEST",
            name="Test Co",
            market=Market.US,
            currency="USD",
            sector="Technology",
        ),
        price_history=bars,
        financials=FinancialStatements(
            revenue=100,
            available_as_of=date(2025, 7, 1),
            fiscal_period_end=date(2025, 6, 30),
            availability_source="test",
        ),
        news_headlines=[
            {
                "title": "Known headline",
                "published_at": "2025-07-29T00:00:00Z",
            }
        ],
        fetched_at=datetime(2025, 7, 30, 12, 0, 0),
    )


def test_complete_report_context_keeps_fields_that_summary_prompts_used_to_drop():
    context = build_analyst_reports_context(_reports())

    for expected in (
        "Competition",
        "Headline citation",
        "Positive histogram",
        "110.0",
        "Supply chain",
    ):
        assert expected in context


def test_evidence_envelope_labels_point_in_time_provenance():
    envelope = build_evidence_envelope(_ticker_data())

    assert '"analysis_as_of": "2025-07-30"' in envelope
    assert '"price_data_as_of": "2025-07-29"' in envelope
    assert '"dated_news_count": 1' in envelope
    assert '"status": "available"' in envelope


def test_future_macro_factors_are_not_marked_available():
    ticker_data = _ticker_data().model_copy(
        update={
            "macro_snapshot": MacroSnapshot(
                as_of_date=date(2025, 8, 1),
                available_as_of=date(2025, 8, 1),
                source="future-test",
                geopolitical_risks=["future event"],
            )
        }
    )

    envelope = build_evidence_envelope(ticker_data)

    assert '"status": "unavailable"' in envelope


def test_downstream_contexts_include_complete_reports_and_evidence():
    ticker_data = _ticker_data()
    reports = _reports()

    debate_context = DebateEngine()._build_context(ticker_data, reports)
    synthesis_context = SynthesizerAgent()._build_full_context(
        ticker_data,
        reports,
        debate_result=DebateResult(
            ticker="TEST",
            rounds=[],
            bull_case_summary="bull",
            bear_case_summary="bear",
            key_points_of_agreement=[],
            key_points_of_disagreement=[],
            unresolved_uncertainties=[],
        ),
    )

    for context in (debate_context, synthesis_context):
        assert "Point-in-time evidence envelope" in context
        assert "Competition" in context
        assert "Positive histogram" in context


def test_technical_payload_adds_descriptive_momentum_and_observed_levels():
    payload = build_indicator_payload(_ticker_data())

    assert payload["price_momentum"]["return_5_bars"] is not None
    assert payload["price_momentum"]["return_20_bars"] is not None
    assert payload["observed_levels"]["20_bar_high"] == 310
    assert payload["observed_levels"]["20_bar_low"] == 289
    assert payload["risk_context"]["daily_volatility_20_bars"] == 0.0001
