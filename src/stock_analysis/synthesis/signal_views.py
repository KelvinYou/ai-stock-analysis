"""Shared production/session evidence guards and deterministic signal views."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, Field

from stock_analysis.config import Settings
from stock_analysis.data.evidence import (
    current_recommendations_are_usable,
    financials_are_usable,
    independent_sentiment_news,
    macro_snapshot_is_usable,
)
from stock_analysis.data.fundamentals import fundamental_evidence_count
from stock_analysis.data.run_input import validate_input
from stock_analysis.models.agent_reports import Confidence, Signal
from stock_analysis.models.market_data import TickerData
from stock_analysis.synthesis.risk_checker import RiskChecker, is_actionable
from stock_analysis.synthesis.synthesizer import (
    calibrate_conviction_score,
    weighted_directional_totals,
)


class SessionPrediction(BaseModel):
    """The minimum structured output needed to score one session trial."""

    ticker: str
    as_of_date: date
    overall_signal: Signal
    conviction_score: float = Field(ge=-1.0, le=1.0)
    signal_convergence: float = Field(ge=0.0, le=1.0)
    agent_signals: dict[str, Signal] = Field(default_factory=dict)
    agent_confidences: dict[str, Confidence] = Field(default_factory=dict)


class CalibratedSessionPrediction(SessionPrediction):
    """A scored session prediction with its pre-gate inputs preserved."""

    synthesized_signal: Signal
    raw_conviction_score: float
    raw_agent_signals: dict[str, Signal] = Field(default_factory=dict)
    signal_gate_reasons: list[str] = Field(default_factory=list)


def compute_session_convergence(
    agent_signals: dict[str, Signal],
    agent_confidences: dict[str, Confidence] | None = None,
    available_agents: Iterable[str] | None = None,
) -> float:
    """Production convergence; availability never removes a role.

    ``available_agents`` is retained for call compatibility but ignored. Evidence
    guards set unavailable roles to neutral/low before this calculation.
    """
    buy, sell, total = weighted_directional_totals(agent_signals, agent_confidences or {})
    return round(max(buy, sell) / total, 4) if total else 0.0


def compute_session_consensus_score(
    agent_signals: dict[str, Signal],
    agent_confidences: dict[str, Confidence] | None = None,
    available_agents: Iterable[str] | None = None,
) -> float:
    """Production net direction over all four roles; availability is not a filter."""
    buy, sell, total = weighted_directional_totals(agent_signals, agent_confidences or {})
    return round((buy - sell) / total, 4) if total else 0.0


def calibrate_session_prediction(
    prediction: SessionPrediction,
    *,
    fundamentals_available: bool = True,
    sentiment_available: bool = True,
    macro_available: bool = True,
    ticker_data: TickerData | None = None,
) -> CalibratedSessionPrediction:
    """Apply evidence guards and the production conviction/actionability contract.

    Raw model conviction is retained; calibrated magnitude never exceeds it.
    Unavailable sources remain neutral/low in the four-role denominator.
    """
    raw_agent_signals = dict(prediction.agent_signals)
    agent_signals = dict(raw_agent_signals)
    agent_confidences = dict(prediction.agent_confidences)
    signal_gate_reasons: list[str] = []
    if ticker_data is not None:
        validate_input(ticker_data, prediction.as_of_date)
        fundamentals_available = fundamentals_available and financials_are_usable(
            ticker_data.financials, prediction.as_of_date)
        macro_available = macro_available and macro_snapshot_is_usable(
            ticker_data.macro_snapshot, prediction.as_of_date)
        news = independent_sentiment_news(ticker_data.news_headlines,
            as_of=prediction.as_of_date,
            max_age_days=ticker_data.news_max_age_days or Settings().news_max_age_days)
        sentiment_available = sentiment_available and bool(news or
            current_recommendations_are_usable(ticker_data.analyst_recommendations,
                                              ticker_data.fetched_at.date(),
                                              provider_capture=ticker_data.provider_capture))
        if fundamental_evidence_count(ticker_data) < 2:
            agent_confidences["fundamentals"] = Confidence.LOW
    if not fundamentals_available:
        agent_signals["fundamentals"] = Signal.NEUTRAL
        agent_confidences["fundamentals"] = Confidence.LOW
        signal_gate_reasons.append("evidence_unavailable:fundamentals")
    if not sentiment_available:
        agent_signals["sentiment"] = Signal.NEUTRAL
        agent_confidences["sentiment"] = Confidence.LOW
        signal_gate_reasons.append("evidence_unavailable:sentiment")
    if not macro_available:
        agent_signals["macro"] = Signal.NEUTRAL
        agent_signals["macro_fx"] = Signal.NEUTRAL
        agent_confidences["macro"] = Confidence.LOW
        agent_confidences["macro_fx"] = Confidence.LOW
        signal_gate_reasons.append("evidence_unavailable:macro")

    prediction = prediction.model_copy(
        update={
            "agent_signals": agent_signals,
            "agent_confidences": agent_confidences,
        }
    )
    convergence = compute_session_convergence(agent_signals, agent_confidences)
    consensus_score = compute_session_consensus_score(agent_signals, agent_confidences)
    conviction_score = calibrate_conviction_score(
        prediction.overall_signal, prediction.conviction_score, consensus_score
    )
    calibrated = CalibratedSessionPrediction(
        **prediction.model_dump(),
        synthesized_signal=prediction.overall_signal,
        raw_conviction_score=prediction.conviction_score,
        raw_agent_signals=raw_agent_signals,
        signal_gate_reasons=signal_gate_reasons,
    ).model_copy(
        update={
            "conviction_score": conviction_score,
            "signal_convergence": convergence,
        }
    )
    final_direction = _signal_direction(calibrated.overall_signal)
    consensus_direction = _signal_direction_from_score(consensus_score)
    directional_gate_reasons = []
    if final_direction != 0 and final_direction != consensus_direction:
        directional_gate_reasons.append("consensus_direction_mismatch")
    if final_direction != 0 and not is_actionable(conviction_score, convergence):
        directional_gate_reasons.append("session_actionability_gate_failed")
    if (final_direction != 0 and ticker_data is not None
        and RiskChecker().plan_levels(ticker_data, conviction_score, convergence).note):
        directional_gate_reasons.append("execution_risk_plan_declined")
    if directional_gate_reasons:
        calibrated = calibrated.model_copy(
            update={
                "overall_signal": Signal.NEUTRAL,
                "conviction_score": 0.0,
                "signal_gate_reasons": [
                    *calibrated.signal_gate_reasons,
                    *directional_gate_reasons,
                ],
            }
        )
    return calibrated


def _signal_direction(signal: Signal) -> int:
    if signal in (Signal.STRONG_BUY, Signal.BUY):
        return 1
    if signal in (Signal.SELL, Signal.STRONG_SELL):
        return -1
    return 0


def _signal_direction_from_score(score: float) -> int:
    if score > 0:
        return 1
    if score < 0:
        return -1
    return 0


def fundamental_technical_views(
    prediction: CalibratedSessionPrediction, data: TickerData,
) -> dict[str, Signal]:
    """Fixed two-role diagnostic, with the same evidence and risk eligibility."""
    weights = {Confidence.HIGH: 1.0, Confidence.MEDIUM: 0.75, Confidence.LOW: 0.5}
    directions, weighted = {}, {}
    for role in ("fundamentals", "technical"):
        directions[role] = _signal_direction(prediction.agent_signals.get(role, Signal.NEUTRAL))
        weighted[role] = weights[prediction.agent_confidences.get(role, Confidence.MEDIUM)]
    total = sum(weighted.values())
    buy = sum(weighted[r] for r in weighted if directions[r] == 1)
    sell = sum(weighted[r] for r in weighted if directions[r] == -1)
    score, convergence = round((buy - sell) / total, 4), round(max(buy, sell) / total, 4)
    direction = _signal_direction_from_score(score)
    signal = Signal.BUY if direction > 0 else Signal.SELL if direction < 0 else Signal.NEUTRAL
    if not is_actionable(score, convergence) or RiskChecker().plan_levels(data, score, convergence).note:
        signal = Signal.NEUTRAL
    agreement = signal if directions["fundamentals"] == directions["technical"] != 0 else Signal.NEUTRAL
    return {"ft_weighted": signal, "ft_agreement": agreement}
