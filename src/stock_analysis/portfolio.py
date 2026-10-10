"""Deterministic portfolio stage over run-bound inputs; no trading or LLM calls."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from datetime import date
from importlib.metadata import version
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from stock_analysis.data.bars import drop_invalid_bars
from stock_analysis.data.run_input import input_digest, validate_input
from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.market_data import Market, TickerData
from stock_analysis.synthesis.signal_views import (
    SessionPrediction,
    calibrate_session_prediction,
    fundamental_technical_views,
)

PORTFOLIO_ARMS = (
    "continuous_strict_hold", "scheduled_passive", "allocator_only",
    "ft_weighted_only", "ft_agreement_only", "ai_only",
    "allocator_plus_ft_weighted", "allocator_plus_ft_agreement", "allocator_plus_ai",
)


def implementation_runtime() -> dict[str, str]:
    return {"python": platform.python_version(),
            **{name: version(name) for name in ("numpy", "pandas", "pydantic")}}


def implementation_identity(package: Path | None = None) -> str:
    """Pin source and numerical runtimes so forward cohorts cannot silently retune."""
    package = package or Path(__file__).resolve().parent
    payload = {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(package.rglob("*.py"))}
    payload["runtime"] = implementation_runtime()
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    ticker_data: TickerData
    prediction: SessionPrediction
    source_input_hash: str | None = None
    provider_provenance: dict = Field(default_factory=dict)
    source_synthesized_signal: Signal | None = None
    source_signal_gate_reasons: list[str] = Field(default_factory=list)


class PortfolioBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    as_of_date: date
    snapshots: list[PortfolioSnapshot] = Field(min_length=3, max_length=50)


class TargetWeightView(BaseModel):
    strategy: str
    weights: dict[str, float]
    cash_weight: float = Field(ge=0, le=1)


class PortfolioPlan(BaseModel):
    version: Literal[1] = 1
    plan_id: str
    implementation_sha256: str
    as_of_date: date
    data_as_of: date
    market: Literal["US"] = "US"
    currency: Literal["USD"] = "USD"
    status: Literal["ready", "unavailable"]
    research_only: Literal[True] = True
    promotion_ready: Literal[False] = False
    lookback_months: Literal[12] = 12
    top_n: Literal[3] = 3
    momentum_ranking: list[str]
    momentum_scores: dict[str, float]
    arms: list[TargetWeightView]
    input_hashes: dict[str, str]
    run_ids: dict[str, str]
    signal_trace: list[dict]
    unavailable_reasons: list[str]


def _weights(names: list[str], denominator: int) -> dict[str, float]:
    return {name: 1 / denominator for name in names}


def build_portfolio_plan(bundle: PortfolioBundle) -> PortfolioPlan:
    """Create all nine weights using only one completed, synchronized panel."""
    snapshots = sorted(bundle.snapshots, key=lambda row: row.prediction.ticker)
    symbols = [row.prediction.ticker for row in snapshots]
    if len(set(symbols)) != len(symbols) or len({row.run_id for row in snapshots}) != len(symbols):
        raise ValueError("Duplicate ticker or run in portfolio panel")
    last_dates, hashes, run_ids, scores, signals, traces, unavailable = set(), {}, {}, {}, {}, [], []
    for row in snapshots:
        data, prediction = row.ticker_data, row.prediction
        ticker = prediction.ticker
        if ticker != data.info.symbol or prediction.as_of_date != bundle.as_of_date:
            raise ValueError("Portfolio prediction/input identity or date mismatch")
        if data.info.market != Market.US or data.info.currency != "USD":
            raise ValueError("Portfolio stage requires one US/USD universe")
        validate_input(data, bundle.as_of_date)
        if not data.price_history:
            raise ValueError("Portfolio input has no completed price bars")
        ordered = sorted(data.price_history, key=lambda bar: bar.date)
        if len({bar.date for bar in ordered}) != len(ordered):
            raise ValueError("Duplicate portfolio price dates")
        last_dates.add(ordered[-1].date)
        audit = drop_invalid_bars(ordered)
        if audit.dropped:
            raise ValueError("Invalid portfolio price bars")
        hashes[ticker] = input_digest(data.model_dump(mode="json"), bundle.as_of_date)
        run_ids[ticker] = row.run_id
        cutoff = (pd.Timestamp(bundle.as_of_date) - pd.DateOffset(months=12)).date()
        prior = [bar for bar in ordered if bar.date <= cutoff]
        if not prior or (cutoff - prior[-1].date).days > 7:
            unavailable.append(f"missing_12_month_history:{ticker}")
        else:
            scores[ticker] = ordered[-1].close / prior[-1].close - 1
        guarded = calibrate_session_prediction(prediction, ticker_data=data)
        ft = fundamental_technical_views(guarded, data)
        signals[ticker] = {"ai": guarded.overall_signal, **ft}
        traces.append({"ticker": ticker, "raw_signal": prediction.overall_signal.value,
                       "source_synthesized_signal": row.source_synthesized_signal,
                       "source_gate_reasons": row.source_signal_gate_reasons,
                       "ai_signal": guarded.overall_signal.value,
                       "conviction": guarded.conviction_score,
                       "gate_reasons": guarded.signal_gate_reasons,
                       **{key: value.value for key, value in ft.items()}})
    if len(last_dates) != 1:
        raise ValueError("Portfolio price snapshots do not share one completed session")
    data_as_of = next(iter(last_dates))
    if (bundle.as_of_date - data_as_of).days > 4:
        unavailable.append("stale_price_panel")
    ranking = sorted(scores, key=lambda ticker: (-scores[ticker], ticker)) if not unavailable else []
    selected = ranking[:3]
    positives = {}
    for label in ("ai", "ft_weighted", "ft_agreement"):
        names = [ticker for ticker in symbols if signals[ticker][label] in {Signal.BUY, Signal.STRONG_BUY}]
        if label == "ai":
            trace_map = {row["ticker"]: row for row in traces}
            names.sort(key=lambda ticker: (
                -int(signals[ticker][label] == Signal.STRONG_BUY),
                -trace_map[ticker]["conviction"], ticker,
            ))
        positives[label] = names[:3]
    views = {"continuous_strict_hold": _weights(symbols, len(symbols)),
             "scheduled_passive": _weights(symbols, len(symbols)),
             "allocator_only": _weights(selected, 3)}
    for label, names in positives.items():
        views[f"{label}_only"] = _weights(names, 3)
        views[f"allocator_plus_{label}"] = _weights(
            [ticker for ticker in selected if signals[ticker][label] in {Signal.BUY, Signal.STRONG_BUY}], 3,
        )
    if unavailable:
        views = {name: {} for name in PORTFOLIO_ARMS}
    implementation = implementation_identity()
    identity = {"bundle": bundle.model_dump(mode="json"), "rules": "portfolio_v1_12month_top3_nine_views",
                "implementation_sha256": implementation}
    identity["bundle"]["snapshots"].sort(key=lambda row: row["prediction"]["ticker"])
    plan_id = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()
    arms = [TargetWeightView(strategy=name, weights=views[name],
                             cash_weight=max(0, 1 - sum(views[name].values()))) for name in PORTFOLIO_ARMS]
    assert all(math.isclose(sum(arm.weights.values()) + arm.cash_weight, 1) for arm in arms)
    return PortfolioPlan(plan_id=plan_id, implementation_sha256=implementation, as_of_date=bundle.as_of_date,
                         data_as_of=data_as_of, status="unavailable" if unavailable else "ready",
                         momentum_ranking=ranking, momentum_scores=scores, arms=arms,
                         input_hashes=hashes, run_ids=run_ids, signal_trace=traces,
                         unavailable_reasons=unavailable)
