from datetime import date, timedelta

import pytest

from stock_analysis.backtest.runner import BacktestResult, BacktestTrial
from stock_analysis.backtest.scorer import Scorer
from stock_analysis.backtest.session import SessionPrediction, calibrate_session_prediction


def test_session_does_not_promote_low_model_conviction():
    prediction = SessionPrediction(
        ticker="TEST",
        as_of_date="2026-01-01",
        overall_signal="buy",
        conviction_score=0.2,
        signal_convergence=1,
        agent_signals={
            "fundamentals": "buy",
            "technical": "buy",
            "macro": "neutral",
            "sentiment": "neutral",
        },
        agent_confidences={
            "fundamentals": "medium",
            "technical": "medium",
            "macro": "low",
            "sentiment": "low",
        },
    )
    result = calibrate_session_prediction(prediction)
    assert result.overall_signal.value == "neutral"
    assert result.conviction_score == 0


def _panel(copies):
    trials = []
    for i, (ret, score) in enumerate(
        zip([0.01, -0.02, 0.03, -0.04, 0.05], [0.5, 0.4, 0.7, 0.6, 0.2], strict=True)
    ):
        day = date(2025, 1, 1) + timedelta(days=60 * i)
        for j in range(copies):
            trials.append(
                BacktestTrial(
                    ticker=f"TEST{j}",
                    as_of_date=day,
                    horizon_days=30,
                    entry_price=100,
                    exit_date=day + timedelta(days=30),
                    exit_price=100 * (1 + ret),
                    realized_return=ret,
                    overall_signal="buy",
                    conviction_score=score,
                    signal_convergence=0.6,
                    agent_signals={},
                )
            )
    return BacktestResult(
        trials=trials, settings={}, started_at=date(2025, 1, 1), finished_at=date(2026, 1, 1)
    )


def test_duplicate_same_date_securities_do_not_narrow_intervals():
    single = Scorer.score(_panel(1))
    duplicated = Scorer.score(_panel(8))
    assert duplicated.overall_hit_rate == single.overall_hit_rate
    assert duplicated.hit_rate_ci_95 == pytest.approx(single.hit_rate_ci_95)
    assert duplicated.info_coefficient_ci_95 == pytest.approx(single.info_coefficient_ci_95)


def test_unavailable_evidence_cannot_shrink_execution_denominator():
    prediction = SessionPrediction(
        ticker="TEST",
        as_of_date="2026-01-01",
        overall_signal="buy",
        conviction_score=0.9,
        signal_convergence=1,
        agent_signals={"technical": "buy"},
        agent_confidences={"technical": "medium"},
    )
    result = calibrate_session_prediction(
        prediction, fundamentals_available=False, sentiment_available=False, macro_available=False
    )
    assert result.signal_convergence == pytest.approx(0.3333)
    assert result.conviction_score == 0
    assert result.overall_signal.value == "neutral"
    assert result.raw_conviction_score == 0.9


def test_ic_uses_all_completed_windows_including_neutral():
    result = _panel(1)
    result.trials[0] = result.trials[0].model_copy(update={"overall_signal": "neutral"})
    # Validated enum field required when callers replace signals.
    from stock_analysis.models.agent_reports import Signal

    result.trials[0].overall_signal = Signal.NEUTRAL
    report = Scorer.score(result)
    assert report.effective_n == pytest.approx(4)
    assert report.ic_effective_n == pytest.approx(5)
