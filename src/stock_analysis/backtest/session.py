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

from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.data.evidence import (
    current_recommendations_are_usable,
    financials_are_usable,
    independent_sentiment_news,
    macro_snapshot_is_usable,
)
from stock_analysis.data.fundamentals import build_fundamental_context
from stock_analysis.data.run_input import validate_input
from stock_analysis.models.market_data import TickerData
from stock_analysis.synthesis.signal_views import (
    CalibratedSessionPrediction as CalibratedSessionPrediction,
)
from stock_analysis.synthesis.signal_views import (
    SessionPrediction as SessionPrediction,
)
from stock_analysis.synthesis.signal_views import (
    calibrate_session_prediction as calibrate_session_prediction,
)
from stock_analysis.synthesis.signal_views import (
    compute_session_consensus_score as compute_session_consensus_score,
)
from stock_analysis.synthesis.signal_views import (
    compute_session_convergence as compute_session_convergence,
)

from .fetcher import BacktestFetcher
from .replay import (
    historical_news_source,
    load_fundamentals_history_replay,
    load_macro_replay,
    load_news_replay,
    load_valuation_price_replay,
)
from .runner import Backtester, BacktestResult, BacktestTrial

# Provider-neutral label: the current session may be Claude Code, Codex, or
# another host capable of writing the compact SessionPrediction records.
SESSION_MODE = "in-session"
# v5 also shares production risk eligibility and zeroes declined conviction.
# Older manifests remain readable; historical scored artifacts are immutable.
SESSION_MANIFEST_VERSION = 5

_EXPECTED_AGENTS = ("fundamentals", "sentiment", "technical", "macro")


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

    if (output_dir / "manifest.json").exists() or (
        (output_dir / "packets").exists() and any((output_dir / "packets").rglob("*.json"))
    ):
        raise FileExistsError(f"Refusing to overwrite session evidence: {output_dir}")
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
                replay_dir=replay_dir,
            )
            ticker_data = fetcher.fetch(ticker)
            replay_news_dir = replay_dir / "news" if replay_dir else None
            macro_replay_path = replay_dir / "macro.jsonl" if replay_dir else None
            if replay_dir and not macro_replay_path.exists():
                macro_replay_path = replay_dir / "macro.json"
            news_window = Settings().news_max_age_days
            replay_news = independent_sentiment_news(load_news_replay(replay_news_dir, ticker, as_of),
                                                      as_of=as_of, max_age_days=news_window)
            replay_macro = load_macro_replay(macro_replay_path, as_of)
            replay_history = load_fundamentals_history_replay(replay_dir, ticker, as_of)
            ticker_data = ticker_data.model_copy(
                update={
                    "financials": (
                        (replay_history[-1] if replay_history else None)
                        if replay_dir is not None
                        else ticker_data.financials
                    ),
                    "news_headlines": replay_news,
                    "news_max_age_days": news_window,
                    "macro_snapshot": replay_macro,
                    "financial_history": (
                        replay_history if replay_dir is not None else ticker_data.financial_history
                    ),
                    "valuation_price": load_valuation_price_replay(replay_dir, ticker, as_of),
                }
            )

            fundamental_context = build_fundamental_context(ticker_data, as_of)
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
                "fundamental_context": fundamental_context,
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
                    "fundamentals_readiness": fundamental_context["readiness"],
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
        data = TickerData.model_validate(packet["ticker_data"])
        validate_input(data, as_of)
        if data.info.symbol.upper() != ticker or data.info.market.value != manifest.market.upper():
            raise ValueError(f"Typed session input identity mismatch: {ticker} @ {as_of}")
        # Legacy sealed packets remain readable. Enriched packets additionally
        # bind their ready-to-use context to dated source observations, before
        # any forward price fetch can expose outcomes.
        if "fundamental_context" in packet:
            data = TickerData.model_validate(packet["ticker_data"])
            for record in data.financial_history:
                if (record.fiscal_period_end is None or record.available_as_of is None
                    or record.fiscal_period_end > as_of or record.available_as_of > as_of
                    or record.available_as_of < record.fiscal_period_end
                    or (record.fiscal_period_start is not None
                        and record.fiscal_period_start > record.fiscal_period_end)):
                    raise ValueError(f"Future or undated fundamental history: {ticker} @ {as_of}")
            price = data.valuation_price
            if price is not None and (price.price_date > as_of or price.available_as_of > as_of):
                raise ValueError(f"Future valuation price: {ticker} @ {as_of}")
            context = build_fundamental_context(data, as_of)
            if packet["fundamental_context"] != context or packet.get("evidence_availability", {}).get("fundamentals_readiness") != context["readiness"]:
                raise ValueError(f"Fundamental context mismatch: {ticker} @ {as_of}")
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
    missing_keys = sorted(expected_keys - set(predictions))
    if missing_keys:
        raise ValueError(f"Missing {len(missing_keys)} session predictions before price fetch")
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
    readiness_counts = {"recorded": 0, "multi_period": 0, "growth": 0, "valuation": 0}
    for item in manifest.trials:
        key = (item["ticker"].upper(), date.fromisoformat(item["as_of_date"]))
        prediction = predictions.get(key)
        if prediction is None:
            missing.append(f"{key[0]} @ {key[1]}")
            continue

        packet = packets[key]
        ticker_data = packet.get("ticker_data", {})
        evidence = packet.get("evidence_availability", {})
        typed_data = TickerData.model_validate(ticker_data)
        # Coverage reports and directional guards must describe the same usable sources.
        evidence = dict(evidence)
        evidence["fundamentals"] = bool(evidence.get("fundamentals")) and financials_are_usable(
            typed_data.financials, key[1])
        evidence["macro"] = bool(evidence.get("macro")) and macro_snapshot_is_usable(
            typed_data.macro_snapshot, key[1])
        evidence["sentiment"] = bool(evidence.get("sentiment", bool(
            typed_data.news_headlines or typed_data.analyst_recommendations))) and bool(
            independent_sentiment_news(typed_data.news_headlines, as_of=key[1],
                max_age_days=typed_data.news_max_age_days or Settings().news_max_age_days)
            or current_recommendations_are_usable(typed_data.analyst_recommendations,
                typed_data.fetched_at.date(), provider_capture=typed_data.provider_capture))
        readiness = evidence.get("fundamentals_readiness")
        if isinstance(readiness, dict):
            readiness_counts["recorded"] += 1
            readiness_counts["multi_period"] += int(readiness.get("history_periods", 0) >= 2)
            for dimension in ("growth", "valuation"):
                readiness_counts[dimension] += int(readiness.get(dimension) is True)
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
            ticker_data=TickerData.model_validate(ticker_data),
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
                raw_conviction_score=prediction.raw_conviction_score,
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
            "consensus_denominator": "production_all_four_roles",
            "conviction_calibration": "production_cap_raw_model_by_consensus_v1",
            "execution_eligibility": "validated_risk_plan_v2",
            "signal_trace_schema": 1,
            "evidence_coverage": {
                "total_trials": len(manifest.trials),
                "available": evidence_counts,
                "sources": evidence_sources,
                "fundamentals_readiness": readiness_counts,
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


def recalibrate_session_result(result: BacktestResult, session_dir: Path) -> BacktestResult:
    """Reapply current scoring contract to sealed predictions without price reads."""
    manifest = SessionManifest.model_validate_json((session_dir / "manifest.json").read_text())
    expected = validate_manifest_panel(manifest)
    predictions = load_session_predictions(session_dir)
    packets = _load_sealed_packets(session_dir, manifest)
    trial_keys = {(t.ticker.upper(), t.as_of_date) for t in result.trials}
    if trial_keys != expected or set(predictions) != expected or len(result.trials) != len(expected):
        raise ValueError("Recalibration requires the exact complete sealed prediction/outcome panel")
    if result.settings.get("horizon_days") != manifest.horizon_days:
        raise ValueError("Recalibration horizon mismatch")
    trials = []
    for trial in result.trials:
        key = (trial.ticker.upper(), trial.as_of_date)
        evidence = packets[key]["evidence_availability"]
        calibrated = calibrate_session_prediction(
            predictions[key], fundamentals_available=bool(evidence.get("fundamentals")),
            sentiment_available=bool(evidence.get("sentiment")), macro_available=bool(evidence.get("macro")),
            ticker_data=TickerData.model_validate(packets[key]["ticker_data"]),
        )
        trials.append(trial.model_copy(update={
            "overall_signal": calibrated.overall_signal,
            "conviction_score": calibrated.conviction_score,
            "raw_conviction_score": calibrated.raw_conviction_score,
            "signal_convergence": calibrated.signal_convergence,
            "agent_signals": {k: v.value for k, v in calibrated.agent_signals.items()},
            "raw_agent_signals": {k: v.value for k, v in calibrated.raw_agent_signals.items()},
            "synthesized_signal": calibrated.synthesized_signal,
            "signal_gate_reasons": calibrated.signal_gate_reasons,
        }))
    settings = dict(result.settings)
    settings.update(consensus_denominator="production_all_four_roles",
                    conviction_calibration="production_cap_raw_model_by_consensus_v1",
                    execution_eligibility="validated_risk_plan_v2")
    return result.model_copy(update={"trials": trials, "settings": settings})
