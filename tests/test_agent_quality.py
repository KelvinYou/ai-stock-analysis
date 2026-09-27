import asyncio
from datetime import date, datetime, timedelta

from stock_analysis.agents.fundamentals import FundamentalsAgent
from stock_analysis.agents.macro import MacroFXAgent
from stock_analysis.agents.sentiment import SentimentAgent
from stock_analysis.agents.technical import canonicalize_technical_report
from stock_analysis.models.agent_reports import (
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


def _ticker_data() -> TickerData:
    start = date(2025, 1, 1)
    bars = [
        PriceBar(
            date=start + timedelta(days=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=1_000,
        )
        for index in range(210)
    ]
    return TickerData(
        info=TickerInfo(
            symbol="TEST",
            name="Test Co",
            market=Market.US,
            currency="USD",
        ),
        price_history=bars,
        fetched_at=datetime(2025, 7, 30, 12, 0, 0),
    )


def test_technical_facts_are_canonicalized_and_out_of_range_levels_removed():
    report = TechnicalReport(
        signal=Signal.BUY,
        confidence=Confidence.HIGH,
        trend="up",
        rsi_14=99,
        rsi_assessment="overbought",
        macd_assessment="positive",
        volume_assessment="confirmed",
        support_levels=[50, 290, 999],
        resistance_levels=[100, 309, 999],
        summary="summary",
    )

    canonical = canonicalize_technical_report(report, _ticker_data())

    assert canonical.rsi_14 != 99
    assert canonical.support_levels == [290.0]
    assert canonical.resistance_levels == [309.0]


def test_sentiment_has_no_social_claim_without_a_social_source():
    report = SentimentReport(
        signal=Signal.BUY,
        confidence=Confidence.MEDIUM,
        news_tone="positive",
        news_summary="dated headline",
        key_themes=[],
        notable_headlines=[],
        social_sentiment="very bullish",
        summary="summary",
    )

    canonical = SentimentAgent.canonicalize_report(report, _ticker_data())

    assert canonical.social_sentiment is None
    assert canonical.notable_headlines == []


def test_fundamentals_caps_confidence_when_only_one_input_is_available():
    report = FundamentalsReport(
        signal=Signal.BUY,
        confidence=Confidence.HIGH,
        pe_assessment="ok",
        margin_analysis="unavailable",
        debt_analysis="unavailable",
        growth_outlook="unavailable",
        key_risks=[],
        key_strengths=[],
        summary="summary",
    )
    ticker_data = _ticker_data().model_copy(
        update={"financials": FinancialStatements(net_income=100)}
    )

    canonical = FundamentalsAgent.canonicalize_report(report, ticker_data)

    assert canonical.confidence == Confidence.LOW
    assert canonical.signal == Signal.BUY


def test_future_financials_are_unavailable_to_the_fundamentals_gate():
    ticker_data = _ticker_data().model_copy(
        update={
            "financials": FinancialStatements(
                net_income=100,
                fiscal_period_end=date(2025, 8, 31),
                available_as_of=date(2025, 8, 31),
            )
        }
    )

    # The async agent returns its deterministic fail-closed report without an
    # LLM call when the statement is after the analysis cutoff.
    report = asyncio.run(FundamentalsAgent().analyze(ticker_data))

    assert report.signal == Signal.NEUTRAL
    assert report.confidence == Confidence.LOW
    assert "unavailable" in report.summary.lower()


def test_historical_undated_recommendations_are_not_sent_to_sentiment():
    ticker_data = _ticker_data().model_copy(
        update={"analyst_recommendations": [{"strongBuy": 10}]}
    )

    report = asyncio.run(SentimentAgent().analyze(ticker_data))

    assert report.signal == Signal.NEUTRAL
    assert report.confidence == Confidence.LOW
    assert "unavailable" in report.summary.lower()


def test_macro_claims_are_removed_when_snapshot_has_no_matching_source():
    report = MacroFXReport(
        signal=Signal.BUY,
        confidence=Confidence.HIGH,
        fed_impact="rates supportive",
        interest_rate_outlook="falling",
        fx_impact="MYR weak",
        sector_macro_factors=["AI demand"],
        geopolitical_risks=["invented risk"],
        summary="summary",
    )
    ticker_data = _ticker_data().model_copy(
        update={
            "macro_snapshot": MacroSnapshot(
                as_of_date=date(2025, 7, 29),
                available_as_of=date(2025, 7, 30),
                source="test",
                sector_factors=["dated sector factor"],
            )
        }
    )

    canonical = MacroFXAgent.canonicalize_report(report, ticker_data)

    assert canonical.fx_impact is None
    assert canonical.sector_macro_factors == ["AI demand"]
    assert canonical.geopolitical_risks == []
    assert "unavailable" in canonical.fed_impact.lower()
    assert "unavailable" in canonical.interest_rate_outlook.lower()
