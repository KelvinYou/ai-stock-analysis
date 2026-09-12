"""A briefing must not be presented as current when the tape has moved on.

Anchored to the real incident: META's `briefing.json` was adjudicated on the
2026-09-02 close ($592.85) and still read as the live signal a week later,
beside `technicals.json` at 2026-09-08 ($617.79, RSI 88.6).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from stock_analysis.api.public_data import _summary_from_cloud, _summary_from_local
from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.market_data import (
    Market,
    PriceBar,
    TechnicalSnapshot,
    TickerData,
    TickerInfo,
)
from stock_analysis.models.synthesis import (
    ActionPlan,
    Briefing,
    ConvictionScore,
    RiskAssessment,
)
from stock_analysis.synthesis.freshness import (
    STALE_AFTER_DAYS,
    assess_freshness,
    briefing_freshness,
)
from stock_analysis.synthesis.risk_checker import RiskChecker, missing_level_inputs

TODAY = date(2026, 9, 10)


def _briefing(
    run_date: str = "2026-09-03",
    data_as_of: str | None = "2026-09-02",
    signal: Signal = Signal.BUY,
) -> Briefing:
    return Briefing(
        ticker="META",
        date=run_date,
        data_as_of=data_as_of,
        overall_signal=signal,
        conviction=ConvictionScore(score=0.25, signal_convergence=0.4545, explanation="x"),
        executive_summary="s",
        bull_case="b",
        bear_case="r",
        key_uncertainties=[],
        catalysts_upcoming=[],
        risk_assessment=RiskAssessment(correlation_notes=[], max_drawdown_scenario="x"),
        action_plan=ActionPlan(),
        agent_signal_breakdown={},
    )


def _technicals(as_of: date, close: float = 617.79, **overrides) -> TechnicalSnapshot:
    values = dict(
        ticker="META",
        as_of_date=as_of,
        close=close,
        sma_20=578.0245,
        sma_50=596.8424,
        sma_200=621.7149,
        ema_20=586.834,
        rsi_14=88.6203,
        bb_upper=623.5936,
        bb_lower=532.4554,
        atr_14=17.4414,
        volume=15_000_000,
        high_52w=788.2166,
        low_52w=519.7782,
    )
    values.update(overrides)
    return TechnicalSnapshot(**values)


# --- the comparison ------------------------------------------------------


def test_briefing_older_than_the_price_data_is_stale() -> None:
    freshness = assess_freshness(
        "2026-09-03", "2026-09-02", "2026-09-08", today=TODAY
    )

    assert freshness.stale
    assert "2026-09-02" in freshness.reason
    assert "2026-09-08" in freshness.reason
    assert not freshness  # __bool__ reads as "is it fresh"


def test_briefing_matching_the_newest_bar_is_fresh() -> None:
    freshness = assess_freshness(
        "2026-09-09", "2026-09-08", "2026-09-08", today=TODAY
    )

    assert not freshness.stale
    assert freshness.reason is None
    assert freshness


def test_briefing_ages_out_even_with_no_newer_bar_to_compare() -> None:
    old = TODAY - timedelta(days=STALE_AFTER_DAYS + 1)

    freshness = assess_freshness(old.isoformat(), old.isoformat(), old.isoformat(), today=TODAY)

    assert freshness.stale
    assert "days" in freshness.reason


def test_run_date_is_the_fallback_when_provenance_is_absent() -> None:
    """Briefings written before `data_as_of` existed still get compared."""
    freshness = assess_freshness("2026-09-03", None, "2026-09-08", today=TODAY)

    assert freshness.stale
    assert "2026-09-03" in freshness.reason


def test_undated_briefing_is_not_trusted() -> None:
    assert assess_freshness(None, None, "2026-09-08", today=TODAY).stale


def test_absent_briefing_is_not_reported_stale() -> None:
    """Nothing to mislabel — the dashboard shows "no analysis", not "stale"."""
    assert not briefing_freshness(None, _technicals(date(2026, 9, 8))).stale


def test_briefing_freshness_prefers_the_explicit_latest_bar() -> None:
    assert briefing_freshness(
        _briefing(), _technicals(date(2026, 9, 2)), latest_bar_date=date(2026, 9, 8),
        today=TODAY,
    ).stale


# --- the read surface ----------------------------------------------------


def test_local_summary_flags_the_stale_briefing() -> None:
    bars = [
        PriceBar(date=date(2026, 9, 2), open=578.79, high=600.38, low=577.0, close=592.85,
                 volume=16_552_700),
        PriceBar(date=date(2026, 9, 8), open=615.875, high=623.22, low=615.05, close=617.79,
                 volume=15_000_000),
    ]
    data = TickerData(
        info=TickerInfo(symbol="META", name="Meta", market=Market.US, currency="USD"),
        price_history=bars,
        fetched_at=datetime(2026, 9, 8, 23, 0, 0),
    )

    summary = _summary_from_local(
        "META", data, _technicals(date(2026, 9, 8)), _briefing()
    )

    assert summary.briefing_stale is True
    assert "2026-09-08" in summary.briefing_stale_reason
    # The signal is still served — flagged, not hidden — so the reader can see
    # what it was and that it is out of date.
    assert summary.signal == Signal.BUY


def test_cloud_summary_flags_the_stale_briefing() -> None:
    summary = _summary_from_cloud(
        {
            "symbol": "META",
            "signal": "buy",
            "briefing_date": "2026-09-03",
            "briefing_data_as_of": "2026-09-02",
            "market_as_of_date": "2026-09-08",
        }
    )

    assert summary.briefing_stale is True
    assert "2026-09-08" in summary.briefing_stale_reason


def test_summary_without_a_briefing_is_not_flagged() -> None:
    summary = _summary_from_cloud({"symbol": "META", "market_as_of_date": "2026-09-08"})

    assert summary.briefing_stale is False
    assert summary.briefing_stale_reason is None


# --- levels are not invented from missing indicators ---------------------


def test_missing_indicators_are_named() -> None:
    complete = _technicals(date(2026, 9, 8))
    assert missing_level_inputs(complete) == []

    # Exactly the 2026-09-03 shape: only EMA-20 and MACD survived.
    gutted = _technicals(
        date(2026, 9, 2),
        close=592.85,
        sma_20=None,
        sma_50=None,
        sma_200=None,
        rsi_14=None,
        bb_upper=None,
        bb_lower=None,
        atr_14=None,
    )
    missing = missing_level_inputs(gutted)
    assert any("ATR-14" in m for m in missing)
    assert any("SMA-20" in m for m in missing)


def test_high_conviction_on_a_gutted_snapshot_quotes_no_levels() -> None:
    """The conviction gate happened to catch the real case; this one wouldn't."""
    bars = [
        PriceBar(
            date=date(2026, 8, 1),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000_000,
        )
    ] * 3
    data = TickerData(
        info=TickerInfo(symbol="META", name="Meta", market=Market.US, currency="USD"),
        price_history=bars,
        fetched_at=datetime(2026, 9, 8, 23, 0, 0),
    )
    briefing = _briefing()
    briefing.conviction = ConvictionScore(
        score=0.8, signal_convergence=0.9, explanation="strong"
    )

    plan = RiskChecker().plan_action(data, briefing)

    assert plan.entry_limit is None
    assert plan.stop_loss is None
    assert "incomplete" in plan.note
    assert "ATR-14" in plan.note


@pytest.mark.parametrize("score,convergence", [(0.25, 0.4545), (0.0, 0.25)])
def test_the_conviction_gate_still_applies(score, convergence) -> None:
    data = TickerData(
        info=TickerInfo(symbol="META", name="Meta", market=Market.US, currency="USD"),
        price_history=[],
        fetched_at=datetime(2026, 9, 8, 23, 0, 0),
    )
    briefing = _briefing()
    briefing.conviction = ConvictionScore(
        score=score, signal_convergence=convergence, explanation="mixed"
    )

    plan = RiskChecker().plan_action(data, briefing)

    assert plan.entry_limit is None
    assert "too mixed" in plan.note
