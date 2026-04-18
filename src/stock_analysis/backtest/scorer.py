from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date

from pydantic import BaseModel

from stock_analysis.models.agent_reports import Signal

from .runner import BacktestResult, BacktestTrial

# Signal → directional position (+1 long, -1 short, 0 flat).
SIGNAL_TO_POSITION: dict[Signal, int] = {
    Signal.STRONG_BUY: 1,
    Signal.BUY: 1,
    Signal.NEUTRAL: 0,
    Signal.SELL: -1,
    Signal.STRONG_SELL: -1,
}

# Approximate knowledge cutoffs for the model aliases used by the pipeline.
# A trial's as_of_date on or before this cutoff is at risk of training-data
# contamination: the model may "recall" the outcome rather than forecast it.
# Tied to the aliases' current resolution (Haiku 4.5, Sonnet 4.6, Opus 4.7).
MODEL_TRAINING_CUTOFFS: dict[str, date] = {
    "haiku": date(2025, 2, 1),
    "sonnet": date(2025, 7, 1),
    "opus": date(2026, 1, 1),
}


class SignalBucket(BaseModel):
    signal: str
    n: int
    hit_rate: float | None  # fraction where sign(return) matches position
    mean_return: float | None
    median_return: float | None


class PartitionReport(BaseModel):
    """Metrics for a subset of trials (e.g. pre-cutoff, post-cutoff)."""

    total_trials: int
    completed_trials: int
    errored_trials: int
    buckets: list[SignalBucket]
    overall_hit_rate: float | None
    directional_mean_return: float | None
    conviction_weighted_return: float | None
    buy_and_hold_mean_return: float | None
    directional_sharpe: float | None
    info_coefficient: float | None


class ScoreReport(BaseModel):
    total_trials: int
    completed_trials: int  # trials with a realized return
    errored_trials: int
    buckets: list[SignalBucket]
    overall_hit_rate: float | None  # excludes neutral
    directional_mean_return: float | None  # mean position * return
    conviction_weighted_return: float | None  # mean conviction * return
    buy_and_hold_mean_return: float | None
    directional_sharpe: float | None  # per-trial, not annualized
    info_coefficient: float | None  # corr(conviction_score, return)

    # Training-cutoff-aware partition. `effective_cutoff` is the latest cutoff
    # across all models used — a trial at or before this date may have leaked
    # into at least one model's training data. `post_cutoff` is the clean slice.
    effective_cutoff: date | None = None
    cutoff_source_model: str | None = None
    pre_cutoff: PartitionReport | None = None
    post_cutoff: PartitionReport | None = None


class Scorer:
    @staticmethod
    def score(result: BacktestResult) -> ScoreReport:
        trials = result.trials
        overall = _compute_partition(trials)

        cutoff, source_model = _effective_cutoff(result.settings)
        pre = post = None
        if cutoff is not None:
            pre_trials = [t for t in trials if t.as_of_date <= cutoff]
            post_trials = [t for t in trials if t.as_of_date > cutoff]
            pre = _compute_partition(pre_trials)
            post = _compute_partition(post_trials)

        return ScoreReport(
            **overall.model_dump(),
            effective_cutoff=cutoff,
            cutoff_source_model=source_model,
            pre_cutoff=pre,
            post_cutoff=post,
        )

    @staticmethod
    def to_markdown(result: BacktestResult, report: ScoreReport) -> str:
        horizon = result.settings.get("horizon_days")
        lines = [
            "# Backtest Report",
            "",
            f"- Horizon: {horizon} calendar days",
            f"- Trials: {report.total_trials} "
            f"({report.completed_trials} completed, {report.errored_trials} errored)",
            f"- Models: quick={result.settings.get('quick_think_model')} "
            f"deep={result.settings.get('deep_think_model')} "
            f"rounds={result.settings.get('debate_rounds')}",
        ]
        if report.effective_cutoff is not None:
            lines.append(
                f"- Training cutoff: {report.effective_cutoff.isoformat()} "
                f"(driven by `{report.cutoff_source_model}` — latest across models used)"
            )
        lines += [
            "",
            "## Headline metrics (all trials)",
            "",
        ]
        lines += _metric_lines(report)
        lines += ["", "## By signal (all trials)", "", *_bucket_table(report.buckets)]

        if report.pre_cutoff is not None and report.post_cutoff is not None:
            lines += [
                "",
                "## Training-cutoff-aware split",
                "",
                "Trials at or before the cutoff may be contaminated by model training data. "
                "Only the post-cutoff slice is a clean out-of-sample test.",
                "",
                f"### Pre-cutoff (≤ {report.effective_cutoff.isoformat()}) — potentially contaminated",
                "",
                f"- Trials: {report.pre_cutoff.total_trials} "
                f"({report.pre_cutoff.completed_trials} completed, "
                f"{report.pre_cutoff.errored_trials} errored)",
            ]
            lines += _metric_lines(report.pre_cutoff)
            lines += [
                "",
                f"### Post-cutoff (> {report.effective_cutoff.isoformat()}) — clean out-of-sample",
                "",
                f"- Trials: {report.post_cutoff.total_trials} "
                f"({report.post_cutoff.completed_trials} completed, "
                f"{report.post_cutoff.errored_trials} errored)",
            ]
            lines += _metric_lines(report.post_cutoff)
            if report.post_cutoff.completed_trials < 10:
                lines += [
                    "",
                    f"> ⚠ Only {report.post_cutoff.completed_trials} clean trials — "
                    "sample too small for statistical inference. Extend the date range past the cutoff.",
                ]

        return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _compute_partition(trials: list[BacktestTrial]) -> PartitionReport:
    completed = [t for t in trials if t.realized_return is not None and t.error is None]
    errored = [t for t in trials if t.error is not None]

    buckets_raw: dict[str, list[BacktestTrial]] = defaultdict(list)
    for t in completed:
        buckets_raw[t.overall_signal.value].append(t)
    buckets = [_bucket_stats(sig, buckets_raw.get(sig.value, [])) for sig in Signal]

    directional = [t for t in completed if SIGNAL_TO_POSITION[t.overall_signal] != 0]
    overall_hit_rate = (
        _fraction(
            sum(
                1
                for t in directional
                if _same_sign(SIGNAL_TO_POSITION[t.overall_signal], t.realized_return)
            ),
            len(directional),
        )
        if directional
        else None
    )

    directional_returns = [
        SIGNAL_TO_POSITION[t.overall_signal] * t.realized_return for t in completed
    ]
    conviction_weighted = [t.conviction_score * t.realized_return for t in completed]

    return PartitionReport(
        total_trials=len(trials),
        completed_trials=len(completed),
        errored_trials=len(errored),
        buckets=buckets,
        overall_hit_rate=overall_hit_rate,
        directional_mean_return=_safe_mean(directional_returns),
        conviction_weighted_return=_safe_mean(conviction_weighted),
        buy_and_hold_mean_return=_safe_mean([t.realized_return for t in completed]),
        directional_sharpe=_safe_sharpe(directional_returns),
        info_coefficient=_correlation(
            [t.conviction_score for t in completed],
            [t.realized_return for t in completed],
        ),
    )


def _effective_cutoff(settings: dict) -> tuple[date | None, str | None]:
    """Return (latest cutoff across models used, source model alias) or (None, None)
    if none of the configured models have a known cutoff."""
    model_keys = ("quick_think_model", "deep_think_model", "synthesis_model")
    candidates = []
    for key in model_keys:
        alias = settings.get(key)
        if alias in MODEL_TRAINING_CUTOFFS:
            candidates.append((MODEL_TRAINING_CUTOFFS[alias], alias))
    if not candidates:
        return None, None
    cutoff, alias = max(candidates, key=lambda p: p[0])
    return cutoff, alias


def _metric_lines(r: PartitionReport | ScoreReport) -> list[str]:
    return [
        f"- Overall directional hit rate (excludes neutral): {_fmt_pct(r.overall_hit_rate)}",
        f"- Directional mean return per trial: {_fmt_pct(r.directional_mean_return)}",
        f"- Conviction-weighted mean return: {_fmt_pct(r.conviction_weighted_return)}",
        f"- Buy-and-hold baseline mean return: {_fmt_pct(r.buy_and_hold_mean_return)}",
        f"- Per-trial Sharpe (directional): {_fmt_float(r.directional_sharpe)}",
        f"- Information coefficient (conviction vs return): {_fmt_float(r.info_coefficient)}",
    ]


def _bucket_table(buckets: list[SignalBucket]) -> list[str]:
    rows = [
        "| Signal | N | Hit rate | Mean return | Median return |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for b in buckets:
        rows.append(
            f"| {b.signal} | {b.n} | "
            f"{_fmt_pct(b.hit_rate)} | "
            f"{_fmt_pct(b.mean_return)} | "
            f"{_fmt_pct(b.median_return)} |"
        )
    return rows


def _bucket_stats(signal: Signal, trials: list[BacktestTrial]) -> SignalBucket:
    if not trials:
        return SignalBucket(
            signal=signal.value, n=0, hit_rate=None, mean_return=None, median_return=None
        )
    returns = [t.realized_return for t in trials]
    position = SIGNAL_TO_POSITION[signal]
    if position == 0:
        # For neutral: "hit" = realized return close to zero (abs < 1%)
        hits = sum(1 for r in returns if abs(r) < 0.01)
    else:
        hits = sum(1 for r in returns if _same_sign(position, r))
    return SignalBucket(
        signal=signal.value,
        n=len(trials),
        hit_rate=_fraction(hits, len(trials)),
        mean_return=_safe_mean(returns),
        median_return=statistics.median(returns) if returns else None,
    )


def _same_sign(position: int, realized: float) -> bool:
    if position == 0 or realized == 0:
        return False
    return (position > 0 and realized > 0) or (position < 0 and realized < 0)


def _fraction(num: int, denom: int) -> float | None:
    return num / denom if denom else None


def _safe_mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None and not _is_nan(v)]
    return statistics.fmean(values) if values else None


def _safe_sharpe(values: list[float]) -> float | None:
    values = [v for v in values if v is not None and not _is_nan(v)]
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    stdev = statistics.stdev(values)
    if stdev == 0:
        return None
    return mean / stdev


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 2:
        return None
    xs_c = [p[0] for p in pairs]
    ys_c = [p[1] for p in pairs]
    try:
        return statistics.correlation(xs_c, ys_c)
    except statistics.StatisticsError:
        return None


def _is_nan(v: float) -> bool:
    return isinstance(v, float) and math.isnan(v)


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:+.2f}%"


def _fmt_float(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.3f}"
