"""Two-stage backtesting support for the no-API-key In-Session mode.

The current Claude/Codex conversation cannot be invoked from a Python
subprocess.  This module therefore separates the deterministic parts of a
backtest from the session's structured predictions:

1. :func:`prepare_session_bundle` writes point-in-time input packets and keeps
   future outcome calculation out of the session bundle.
2. :func:`score_session_bundle` validates session predictions, joins them with
   the hidden outcomes, and returns the normal :class:`BacktestResult` used by
   :class:`~stock_analysis.backtest.scorer.Scorer` and the portfolio simulator.

The prediction file is intentionally compact.  The session is responsible for
the analyst/debate/synthesis reasoning and records the final signal plus the
four analyst directions needed for attribution.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import Confidence, Signal
from stock_analysis.synthesis.risk_checker import is_actionable

from .fetcher import BacktestFetcher
from .runner import BacktestResult, BacktestTrial, Backtester


SESSION_MODE = "in-session-claude-code"

_CONFIDENCE_WEIGHT = {
    Confidence.HIGH: 1.0,
    Confidence.MEDIUM: 0.75,
    Confidence.LOW: 0.5,
}
_EXPECTED_AGENTS = ("fundamentals", "sentiment", "technical", "macro")


class SessionPrediction(BaseModel):
    """The minimum structured output needed to score one session trial."""

    ticker: str
    as_of_date: date
    overall_signal: Signal
    conviction_score: float = Field(ge=-1.0, le=1.0)
    signal_convergence: float = Field(ge=0.0, le=1.0)
    agent_signals: dict[str, Signal] = Field(default_factory=dict)
    agent_confidences: dict[str, Confidence] = Field(default_factory=dict)


def compute_session_convergence(
    agent_signals: dict[str, Signal],
    agent_confidences: dict[str, Confidence] | None = None,
) -> float:
    """Compute a point-in-time convergence score from session attribution.

    Session predictions may omit confidence fields, so missing confidence
    defaults to medium. Missing analyst outputs count as neutral evidence in
    the denominator rather than disappearing from the score.
    """
    confidences = agent_confidences or {}
    directional_weights = {1: 0.0, -1: 0.0}
    total_weight = 0.0
    for name in _EXPECTED_AGENTS:
        signal = agent_signals.get(name)
        if signal is None and name == "macro":
            signal = agent_signals.get("macro_fx")
        confidence = confidences.get(name, Confidence.MEDIUM)
        weight = _CONFIDENCE_WEIGHT[confidence]
        total_weight += weight
        if signal in (Signal.STRONG_BUY, Signal.BUY):
            directional_weights[1] += weight
        elif signal in (Signal.SELL, Signal.STRONG_SELL):
            directional_weights[-1] += weight

    if total_weight == 0:
        return 0.0
    return round(max(directional_weights.values()) / total_weight, 4)


def compute_session_consensus_score(
    agent_signals: dict[str, Signal],
    agent_confidences: dict[str, Confidence] | None = None,
) -> float:
    """Return net confidence-weighted direction in ``[-1, 1]``."""
    confidences = agent_confidences or {}
    net_weight = 0.0
    total_weight = 0.0
    for name in _EXPECTED_AGENTS:
        signal = agent_signals.get(name)
        if signal is None and name == "macro":
            signal = agent_signals.get("macro_fx")
        confidence = confidences.get(name, Confidence.MEDIUM)
        weight = _CONFIDENCE_WEIGHT[confidence]
        total_weight += weight
        if signal in (Signal.STRONG_BUY, Signal.BUY):
            net_weight += weight
        elif signal in (Signal.SELL, Signal.STRONG_SELL):
            net_weight -= weight

    if total_weight == 0:
        return 0.0
    return round(net_weight / total_weight, 4)


def calibrate_session_prediction(
    prediction: SessionPrediction,
    *,
    sentiment_available: bool = True,
    macro_available: bool = True,
) -> SessionPrediction:
    """Apply evidence guards, then replace self-reported scores."""
    agent_signals = dict(prediction.agent_signals)
    agent_confidences = dict(prediction.agent_confidences)
    if not sentiment_available:
        agent_signals["sentiment"] = Signal.NEUTRAL
        agent_confidences["sentiment"] = Confidence.LOW
    if not macro_available:
        agent_signals["macro"] = Signal.NEUTRAL
        agent_signals["macro_fx"] = Signal.NEUTRAL
        agent_confidences["macro"] = Confidence.LOW
        agent_confidences["macro_fx"] = Confidence.LOW

    prediction = prediction.model_copy(
        update={
            "agent_signals": agent_signals,
            "agent_confidences": agent_confidences,
        }
    )
    convergence = compute_session_convergence(
        agent_signals,
        agent_confidences,
    )
    consensus_score = compute_session_consensus_score(
        agent_signals,
        agent_confidences,
    )
    calibrated = prediction.model_copy(
        update={
            "conviction_score": consensus_score,
            "signal_convergence": convergence,
        }
    )
    final_direction = _signal_direction(calibrated.overall_signal)
    consensus_direction = _signal_direction_from_score(consensus_score)
    if (
        final_direction == 0
        or final_direction != consensus_direction
        or not is_actionable(consensus_score, convergence)
    ):
        calibrated = calibrated.model_copy(update={"overall_signal": Signal.NEUTRAL})
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


class SessionManifest(BaseModel):
    """Metadata for a prepared session bundle."""

    version: int = 1
    pipeline_mode: str = SESSION_MODE
    market: str
    tickers: list[str]
    as_of_dates: list[date]
    horizon_days: int
    lookback_days: int
    created_at: date
    predictions_file: str = "predictions.json"
    trials: list[dict[str, str]]


def prepare_session_bundle(
    *,
    tickers: Iterable[str],
    as_of_dates: Iterable[date],
    output_dir: Path,
    market: str = "US",
    horizon_days: int = 30,
    lookback_days: int = 365,
) -> SessionManifest:
    """Prepare point-in-time packets for the current session to analyze.

    Only data available on each ``as_of_date`` is written to a packet.  Entry
    and exit prices are fetched later by ``session-score`` so the session
    cannot accidentally read the answer while producing a prediction.
    """

    ticker_list = [t.strip().upper() for t in tickers if t.strip()]
    dates = sorted(set(as_of_dates))
    if not ticker_list:
        raise ValueError("tickers must not be empty")
    if not dates:
        raise ValueError("as_of_dates must not be empty")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "packets").mkdir(parents=True, exist_ok=True)

    manifest_trials: list[dict[str, str]] = []

    for ticker in ticker_list:
        for as_of in dates:
            fetcher = BacktestFetcher(
                as_of_date=as_of,
                market=market,
                lookback_days=lookback_days,
            )
            ticker_data = fetcher.fetch(ticker)

            packet_rel = Path("packets") / ticker / f"{as_of.isoformat()}.json"
            packet_path = output_dir / packet_rel
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet = {
                "pipeline_mode": SESSION_MODE,
                "ticker": ticker,
                "market": market.upper(),
                "as_of_date": as_of.isoformat(),
                "horizon_days": horizon_days,
                "do_not_use_future_prices": True,
                "ticker_data": ticker_data.model_dump(mode="json"),
                "evidence_availability": {
                    "sentiment": bool(
                        ticker_data.news_headlines
                        or ticker_data.analyst_recommendations
                    ),
                    "macro": False,
                },
                "prediction_schema": SessionPrediction.model_json_schema(),
            }
            packet_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False))

            prediction_rel = Path("predictions") / ticker / f"{as_of.isoformat()}.json"
            manifest_trials.append(
                {
                    "ticker": ticker,
                    "as_of_date": as_of.isoformat(),
                    "packet": packet_rel.as_posix(),
                    "prediction": prediction_rel.as_posix(),
                }
            )

    manifest = SessionManifest(
        market=market.upper(),
        tickers=ticker_list,
        as_of_dates=dates,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
        created_at=date.today(),
        trials=manifest_trials,
    )
    (output_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2)
    )
    return manifest


def load_session_predictions(session_dir: Path) -> dict[tuple[str, date], SessionPrediction]:
    """Load predictions from ``predictions.json`` or per-trial JSON files."""

    predictions_path = session_dir / "predictions.json"
    if predictions_path.exists():
        raw = json.loads(predictions_path.read_text())
        if not isinstance(raw, list):
            raise ValueError("predictions.json must contain a JSON array")
        predictions = [SessionPrediction.model_validate(item) for item in raw]
    else:
        predictions = []
        per_trial_dir = session_dir / "predictions"
        if per_trial_dir.exists():
            for path in sorted(per_trial_dir.rglob("*.json")):
                predictions.append(SessionPrediction.model_validate_json(path.read_text()))
        if not predictions:
            raise FileNotFoundError(
                f"No predictions found in {predictions_path} or {per_trial_dir}"
            )

    result: dict[tuple[str, date], SessionPrediction] = {}
    for prediction in predictions:
        key = (prediction.ticker.upper(), prediction.as_of_date)
        if key in result:
            raise ValueError(f"Duplicate session prediction: {key[0]} @ {key[1]}")
        result[key] = prediction.model_copy(update={"ticker": key[0]})
    return result


def score_session_bundle(session_dir: Path) -> BacktestResult:
    """Join validated session predictions with prices fetched after scoring."""

    manifest = SessionManifest.model_validate_json(
        (session_dir / "manifest.json").read_text()
    )
    predictions = load_session_predictions(session_dir)

    backtester = Backtester(
        settings=Settings(),
        market=manifest.market,
        horizon_days=manifest.horizon_days,
        lookback_days=manifest.lookback_days,
    )
    max_exit = max(manifest.as_of_dates) + timedelta(
        days=manifest.horizon_days + 10
    )
    forward_series = {
        ticker: backtester._fetch_price_series(
            ticker, min(manifest.as_of_dates), max_exit
        )
        for ticker in manifest.tickers
    }

    trials: list[BacktestTrial] = []
    missing: list[str] = []
    for item in manifest.trials:
        key = (item["ticker"].upper(), date.fromisoformat(item["as_of_date"]))
        prediction = predictions.get(key)
        if prediction is None:
            missing.append(f"{key[0]} @ {key[1]}")
            continue

        packet = json.loads(
            (session_dir / item["packet"]).read_text()
        )
        ticker_data = packet.get("ticker_data", {})
        evidence = packet.get("evidence_availability", {})
        sentiment_available = evidence.get(
            "sentiment",
            bool(
                ticker_data.get("news_headlines")
                or ticker_data.get("analyst_recommendations")
            ),
        )
        macro_available = evidence.get("macro", False)
        prediction = calibrate_session_prediction(
            prediction,
            sentiment_available=sentiment_available,
            macro_available=macro_available,
        )

        entry_price, entry_date = backtester._price_on_or_after(
            forward_series[key[0]], key[1]
        )
        exit_price, exit_date = backtester._price_on_or_after(
            forward_series[key[0]],
            key[1] + timedelta(days=manifest.horizon_days),
        )

        realized_return = (
            (exit_price - entry_price) / entry_price
            if entry_price and exit_price
            else None
        )
        error = None
        if realized_return is None:
            error = "No forward price available for entry or exit"

        trials.append(
            BacktestTrial(
                ticker=key[0],
                as_of_date=key[1],
                horizon_days=manifest.horizon_days,
                entry_price=entry_price if entry_price is not None else float("nan"),
                exit_date=exit_date,
                exit_price=exit_price,
                realized_return=realized_return,
                overall_signal=prediction.overall_signal,
                conviction_score=prediction.conviction_score,
                signal_convergence=prediction.signal_convergence,
                agent_signals=prediction.agent_signals,
                error=error,
            )
        )

    if missing:
        preview = ", ".join(missing[:8])
        suffix = " ..." if len(missing) > 8 else ""
        raise ValueError(
            f"Missing {len(missing)} session predictions: {preview}{suffix}"
        )

    return BacktestResult(
        trials=trials,
        settings={
            "market": manifest.market,
            "horizon_days": manifest.horizon_days,
            "lookback_days": manifest.lookback_days,
            "quick_think_model": "session",
            "deep_think_model": "session",
            "synthesis_model": "session",
            "debate_rounds": 2,
            "pipeline_mode": SESSION_MODE,
            "deterministic_convergence": True,
            "trade_gate": "conviction > 0.3 and convergence >= 0.4",
            "evidence_guard": True,
        },
        started_at=manifest.created_at,
        finished_at=date.today(),
    )
