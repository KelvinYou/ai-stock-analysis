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
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import Confidence, Signal
from stock_analysis.synthesis.risk_checker import is_actionable

from .fetcher import BacktestFetcher
from .replay import (
    historical_news_source,
    load_fundamentals_replay,
    load_macro_replay,
    load_news_replay,
)
from .runner import Backtester, BacktestResult, BacktestTrial

# Provider-neutral label: the current session may be Claude Code, Codex, or
# another host capable of writing the compact SessionPrediction records.
SESSION_MODE = "in-session"
# v3 records the evidence-aware consensus denominator. Older manifests remain
# readable and are rescored with the current deterministic contract.
SESSION_MANIFEST_VERSION = 3

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


class CalibratedSessionPrediction(SessionPrediction):
    """A scored session prediction with its pre-gate inputs preserved."""

    synthesized_signal: Signal
    raw_agent_signals: dict[str, Signal] = Field(default_factory=dict)
    signal_gate_reasons: list[str] = Field(default_factory=list)


def compute_session_convergence(
    agent_signals: dict[str, Signal],
    agent_confidences: dict[str, Confidence] | None = None,
    available_agents: Iterable[str] | None = None,
) -> float:
    """Compute a point-in-time convergence score from session attribution.

    Session predictions may omit confidence fields, so missing confidence
    defaults to medium. Missing analyst outputs count as neutral evidence in
    the denominator rather than disappearing from the score. When
    ``available_agents`` is supplied, analysts whose point-in-time evidence is
    unavailable are excluded from the denominator; unavailable evidence is
    not the same thing as a neutral view.
    """
    confidences = agent_confidences or {}
    names = _normalise_available_agents(available_agents)
    directional_weights = {1: 0.0, -1: 0.0}
    total_weight = 0.0
    for name in _EXPECTED_AGENTS:
        if name not in names:
            continue
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
    available_agents: Iterable[str] | None = None,
) -> float:
    """Return net confidence-weighted direction in ``[-1, 1]``.

    If ``available_agents`` is supplied, only evidence-backed analysts enter
    the denominator. This prevents an unavailable source from being treated
    as contradictory neutral evidence.
    """
    confidences = agent_confidences or {}
    names = _normalise_available_agents(available_agents)
    net_weight = 0.0
    total_weight = 0.0
    for name in _EXPECTED_AGENTS:
        if name not in names:
            continue
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


def _normalise_available_agents(available_agents: Iterable[str] | None) -> set[str]:
    """Return the expected analyst names included in a consensus denominator."""
    if available_agents is None:
        return set(_EXPECTED_AGENTS)
    names = {
        "macro" if name == "macro_fx" else name
        for name in available_agents
    }
    return names.intersection(_EXPECTED_AGENTS)


def calibrate_session_prediction(
    prediction: SessionPrediction,
    *,
    fundamentals_available: bool = True,
    sentiment_available: bool = True,
    macro_available: bool = True,
) -> CalibratedSessionPrediction:
    """Apply evidence guards, then replace self-reported scores.

    ``conviction_score`` records the confidence-weighted analyst consensus,
    not an executable position. A prediction can therefore remain ``neutral``
    after failing the actionability gate while retaining a non-zero consensus
    score for attribution; portfolio simulation still takes no trade. Missing
    point-in-time evidence forces the corresponding analyst to neutral/low.
    """
    raw_agent_signals = dict(prediction.agent_signals)
    agent_signals = dict(raw_agent_signals)
    agent_confidences = dict(prediction.agent_confidences)
    signal_gate_reasons: list[str] = []
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
    available_agents = {"technical"}
    if fundamentals_available:
        available_agents.add("fundamentals")
    if sentiment_available:
        available_agents.add("sentiment")
    if macro_available:
        available_agents.add("macro")
    convergence = compute_session_convergence(
        agent_signals,
        agent_confidences,
        available_agents=available_agents,
    )
    consensus_score = compute_session_consensus_score(
        agent_signals,
        agent_confidences,
        available_agents=available_agents,
    )
    calibrated = CalibratedSessionPrediction(
        **prediction.model_dump(),
        synthesized_signal=prediction.overall_signal,
        raw_agent_signals=raw_agent_signals,
        signal_gate_reasons=signal_gate_reasons,
    ).model_copy(
        update={
            "conviction_score": consensus_score,
            "signal_convergence": convergence,
        }
    )
    final_direction = _signal_direction(calibrated.overall_signal)
    consensus_direction = _signal_direction_from_score(consensus_score)
    directional_gate_reasons = []
    if final_direction != 0 and final_direction != consensus_direction:
        directional_gate_reasons.append("consensus_direction_mismatch")
    if final_direction != 0 and not is_actionable(consensus_score, convergence):
        directional_gate_reasons.append("session_actionability_gate_failed")
    if directional_gate_reasons:
        calibrated = calibrated.model_copy(
            update={
                "overall_signal": Signal.NEUTRAL,
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


class SessionManifest(BaseModel):
    """Metadata for a prepared session bundle."""

    version: int = SESSION_MANIFEST_VERSION
    pipeline_mode: str = SESSION_MODE
    market: str
    tickers: list[str]
    as_of_dates: list[date]
    horizon_days: int
    lookback_days: int
    created_at: date
    predictions_file: str = "predictions.json"
    trials: list[dict[str, str]]


def validate_manifest_panel(manifest: SessionManifest) -> set[tuple[str, date]]:
    """Require the sealed trial list to equal the declared ticker/date grid."""

    tickers = [ticker.strip().upper() for ticker in manifest.tickers]
    if not tickers or any(not ticker for ticker in tickers) or len(set(tickers)) != len(tickers):
        raise ValueError("Invalid or duplicate tickers in session manifest")
    dates = manifest.as_of_dates
    if not dates or len(set(dates)) != len(dates):
        raise ValueError("Invalid or duplicate dates in session manifest")
    expected = {(ticker, day) for ticker in tickers for day in dates}
    try:
        observed = [
            (item["ticker"].strip().upper(), date.fromisoformat(item["as_of_date"]))
            for item in manifest.trials
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid session manifest trial key") from exc
    if len(observed) != len(expected) or set(observed) != expected:
        raise ValueError("Incomplete or duplicate session manifest trial grid")
    return expected


def prepare_session_bundle(
    *,
    tickers: Iterable[str],
    as_of_dates: Iterable[date],
    output_dir: Path,
    market: str = "US",
    horizon_days: int = 30,
    lookback_days: int = 365,
    replay_dir: Path | None = None,
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
    if len(set(ticker_list)) != len(ticker_list):
        raise ValueError("Duplicate ticker in session universe")
    if not dates:
        raise ValueError("as_of_dates must not be empty")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "packets").mkdir(parents=True, exist_ok=True)

    manifest_trials: list[dict[str, str]] = []
    sentiment_source = historical_news_source(replay_dir)

    for ticker in ticker_list:
        for as_of in dates:
            fetcher = BacktestFetcher(
                as_of_date=as_of,
                market=market,
                lookback_days=lookback_days,
            )
            ticker_data = fetcher.fetch(ticker)
            replay_news_dir = replay_dir / "news" if replay_dir else None
            macro_replay_path = replay_dir / "macro.jsonl" if replay_dir else None
            if replay_dir and not macro_replay_path.exists():
                macro_replay_path = replay_dir / "macro.json"
            replay_news = load_news_replay(replay_news_dir, ticker, as_of)
            replay_macro = load_macro_replay(macro_replay_path, as_of)
            replay_fundamentals = load_fundamentals_replay(replay_dir, ticker, as_of)
            ticker_data = ticker_data.model_copy(
                update={
                    "financials": (
                        replay_fundamentals
                        if replay_dir is not None
                        else ticker_data.financials
                    ),
                    "news_headlines": replay_news,
                    "macro_snapshot": replay_macro,
                }
            )

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
                    "technical": bool(ticker_data.price_history),
                    "technical_source": "historical_price_replay",
                    "metadata_source": "fail_closed_current_provider_metadata_omitted",
                    "fundamentals": bool(
                        ticker_data.financials
                        and ticker_data.financials.available_as_of
                        and ticker_data.financials.available_as_of <= as_of
                    ),
                    "fundamentals_as_of": (
                        ticker_data.financials.available_as_of.isoformat()
                        if ticker_data.financials
                        and ticker_data.financials.available_as_of
                        else None
                    ),
                    "fundamentals_source": (
                        ticker_data.financials.availability_source
                        if ticker_data.financials
                        else "unavailable"
                    ),
                    "sentiment": bool(ticker_data.news_headlines),
                    "sentiment_source": sentiment_source,
                    "macro": replay_macro is not None,
                    "macro_source": (
                        replay_macro.source if replay_macro else "not_configured"
                    ),
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


def _load_sealed_packets(
    session_dir: Path, manifest: SessionManifest
) -> dict[tuple[str, date], dict]:
    """Preflight packet identity and clocks before fetching forward prices."""

    packets: dict[tuple[str, date], dict] = {}
    session_root = session_dir.resolve()
    for item in manifest.trials:
        ticker = item["ticker"].upper()
        as_of = date.fromisoformat(item["as_of_date"])
        relative = Path(item["packet"])
        packet_path = (session_dir / relative).resolve()
        if (
            relative.is_absolute()
            or not relative.parts
            or relative.parts[0] != "packets"
            or not packet_path.is_relative_to(session_root)
        ):
            raise ValueError(f"Invalid session packet path: {relative}")
        packet = json.loads(packet_path.read_text())
        if not isinstance(packet, dict) or (
            str(packet.get("ticker", "")).upper() != ticker
            or packet.get("as_of_date") != as_of.isoformat()
            or str(packet.get("market", "")).upper() != manifest.market.upper()
            or packet.get("horizon_days") != manifest.horizon_days
        ):
            raise ValueError(f"Session packet identity mismatch: {ticker} @ {as_of}")
        bars = packet.get("ticker_data", {}).get("price_history")
        if (
            packet.get("do_not_use_future_prices") is not True
            or not isinstance(bars, list)
            or not bars
        ):
            raise ValueError(f"Invalid point-in-time packet: {ticker} @ {as_of}")
        try:
            if any(date.fromisoformat(bar["date"]) > as_of for bar in bars):
                raise ValueError(f"Future price bar in session packet: {ticker} @ {as_of}")
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Invalid price bar date: {ticker} @ {as_of}") from exc
        packets[(ticker, as_of)] = packet
    return packets


def score_session_bundle(session_dir: Path) -> BacktestResult:
    """Join validated session predictions with prices fetched after scoring."""

    manifest = SessionManifest.model_validate_json(
        (session_dir / "manifest.json").read_text()
    )
    expected_keys = validate_manifest_panel(manifest)
    predictions = load_session_predictions(session_dir)
    unexpected = sorted(set(predictions) - expected_keys)
    if unexpected:
        preview = ", ".join(f"{ticker} @ {day}" for ticker, day in unexpected[:8])
        raise ValueError(f"Unexpected session predictions outside manifest: {preview}")
    packets = _load_sealed_packets(session_dir, manifest)

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
    evidence_counts = {
        "technical": 0,
        "fundamentals": 0,
        "sentiment": 0,
        "macro": 0,
    }
    evidence_sources: dict[str, dict[str, int]] = {
        name: {} for name in evidence_counts
    }
    for item in manifest.trials:
        key = (item["ticker"].upper(), date.fromisoformat(item["as_of_date"]))
        prediction = predictions.get(key)
        if prediction is None:
            missing.append(f"{key[0]} @ {key[1]}")
            continue

        packet = packets[key]
        ticker_data = packet.get("ticker_data", {})
        evidence = packet.get("evidence_availability", {})
        for name in evidence_counts:
            available = (
                bool(ticker_data.get("price_history"))
                if name == "technical"
                else bool(evidence.get(name, False))
            )
            if available:
                evidence_counts[name] += 1
                source = str(evidence.get(f"{name}_source") or "unspecified")
                evidence_sources[name][source] = evidence_sources[name].get(source, 0) + 1
        sentiment_available = evidence.get(
            "sentiment",
            bool(
                ticker_data.get("news_headlines")
                or ticker_data.get("analyst_recommendations")
            ),
        )
        macro_available = evidence.get("macro", False)
        fundamentals_available = evidence.get("fundamentals", False)
        prediction = calibrate_session_prediction(
            prediction,
            fundamentals_available=fundamentals_available,
            sentiment_available=sentiment_available,
            macro_available=macro_available,
        )

        entry_price, entry_date = backtester._price_on_or_after(
            forward_series[key[0]],
            key[1] + timedelta(days=1),
            price_column="Open",
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
                raw_agent_signals={
                    name: signal.value
                    for name, signal in prediction.raw_agent_signals.items()
                },
                synthesized_signal=prediction.synthesized_signal,
                signal_gate_reasons=prediction.signal_gate_reasons,
                error=error,
                entry_date=entry_date,
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
            "entry_execution": "next_session_open",
            "price_path_source": "yfinance_auto_adjusted_ohlc",
            "quick_think_model": "session",
            "deep_think_model": "session",
            "synthesis_model": "session",
            "debate_rounds": 2,
            "pipeline_mode": SESSION_MODE,
            "deterministic_convergence": True,
            "trade_gate": "conviction > 0.3 and convergence >= 0.4",
            "evidence_guard": True,
            "fundamentals_filing_date_gate": True,
            "consensus_denominator": "available_evidence_only",
            "signal_trace_schema": 1,
            "evidence_coverage": {
                "total_trials": len(manifest.trials),
                "available": evidence_counts,
                "sources": evidence_sources,
            },
        },
        started_at=manifest.created_at,
        finished_at=date.today(),
        price_paths={
            ticker.upper(): backtester._price_bars(forward_series[ticker])
            for ticker in manifest.tickers
            if not forward_series[ticker].empty
        },
    )
