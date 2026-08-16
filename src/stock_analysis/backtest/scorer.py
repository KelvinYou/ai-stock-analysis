from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date

from pydantic import BaseModel

from stock_analysis.models.agent_reports import Signal

from . import stats
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
    """Metrics for a subset of trials (e.g. pre-cutoff, post-cutoff).

    Point estimates are paired with interval estimates throughout. A hit rate
    without a confidence interval reads as an edge at any sample size, and the
    sample sizes here are small enough that it usually is not one.
    """

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

    # --- Denominators -------------------------------------------------
    # `overall_hit_rate` is computed over directional trials only, while
    # `directional_mean_return` averages across every completed trial (neutral
    # contributing 0.0). Both are legitimate; they are not comparable, so the
    # counts are surfaced rather than left for the reader to infer.
    directional_trials: int = 0
    active_mean_return: float | None = None  # same denominator as the hit rate

    # --- Uncertainty --------------------------------------------------
    # `effective_n` discounts overlapping holding windows. Every t-statistic
    # below uses it in place of the nominal trial count.
    effective_n: float | None = None
    hit_rate_ci_95: tuple[float, float] | None = None
    directional_mean_t_stat: float | None = None
    directional_mean_p_value: float | None = None
    info_coefficient_ci_95: tuple[float, float] | None = None
    return_skew: float | None = None
    return_kurtosis: float | None = None
    probabilistic_sharpe: float | None = None  # P(true Sharpe > 0)

    # --- Costs --------------------------------------------------------
    # Gross figures above; net figures here. Round-trip cost is charged only
    # to directional trials — sitting out is free.
    cost_bps_per_side: float = 0.0
    net_directional_mean_return: float | None = None
    net_directional_sharpe: float | None = None
    net_mean_p_value: float | None = None


class ScoreReport(PartitionReport):
    """Whole-run metrics, plus the cutoff-aware split.

    Extends `PartitionReport` rather than restating its fields: the two were
    duplicate field-for-field, so every new metric had to be added twice or the
    two would drift.
    """

    # Training-cutoff-aware partition. `effective_cutoff` is the latest cutoff
    # across all models used — a trial at or before this date may have leaked
    # into at least one model's training data. `post_cutoff` is the clean slice.
    effective_cutoff: date | None = None
    cutoff_source_model: str | None = None
    pre_cutoff: PartitionReport | None = None
    post_cutoff: PartitionReport | None = None


class Scorer:
    @staticmethod
    def score(result: BacktestResult, cost_bps_per_side: float = 0.0) -> ScoreReport:
        """Score a backtest run.

        `cost_bps_per_side` charges a one-way transaction cost in basis points
        to each leg of a directional trial. Realized returns from the runner
        are gross; net figures are reported alongside rather than replacing
        them, so the cost assumption stays visible instead of being baked in.
        """
        trials = result.trials
        overall = _compute_partition(trials, cost_bps_per_side)

        cutoff, source_model = _effective_cutoff(result.settings)
        pre = post = None
        if cutoff is not None:
            pre_trials = [t for t in trials if t.as_of_date <= cutoff]
            post_trials = [t for t in trials if t.as_of_date > cutoff]
            pre = _compute_partition(pre_trials, cost_bps_per_side)
            post = _compute_partition(post_trials, cost_bps_per_side)

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
            (f"- Trials: {report.total_trials} "
            f"({report.completed_trials} completed, {report.errored_trials} errored)"),
            f"- Pipeline mode: {result.settings.get('pipeline_mode', 'api')}",
            (f"- Models: quick={result.settings.get('quick_think_model')} "
            f"deep={result.settings.get('deep_think_model')} "
            f"rounds={result.settings.get('debate_rounds')}"),
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
                ("Trials at or before the cutoff may be contaminated by model training data. "
                "Only the post-cutoff slice is a clean out-of-sample test."),
                "",
                f"### Pre-cutoff (≤ {report.effective_cutoff.isoformat()}) — potentially contaminated",
                "",
                (f"- Trials: {report.pre_cutoff.total_trials} "
                f"({report.pre_cutoff.completed_trials} completed, "
                f"{report.pre_cutoff.errored_trials} errored)"),
            ]
            lines += _metric_lines(report.pre_cutoff)
            lines += [
                "",
                f"### Post-cutoff (> {report.effective_cutoff.isoformat()}) — clean out-of-sample",
                "",
                (f"- Trials: {report.post_cutoff.total_trials} "
                f"({report.post_cutoff.completed_trials} completed, "
                f"{report.post_cutoff.errored_trials} errored)"),
            ]
            lines += _metric_lines(report.post_cutoff)
            lines += _small_sample_warning(report.post_cutoff)

        lines += [
            "",
            "## How to read this",
            "",
            ("- A hit rate whose 95% interval spans 50% is not evidence of skill, "
            "however far the point estimate sits from 50%."),
            ("- `p` values use the **effective** sample size, not the trial count. "
            "Overlapping holding windows are not independent observations."),
            ("- Probabilistic Sharpe is the Sharpe corrected for skew and fat tails; "
            "a raw Sharpe flatters strategies with occasional large losses."),
            ("- Gross figures ignore slippage and commission. On thin books "
            "(Bursa small caps especially) costs can exceed the entire edge."),
        ]

        return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _compute_partition(
    trials: list[BacktestTrial], cost_bps_per_side: float = 0.0
) -> PartitionReport:
    completed = [t for t in trials if t.realized_return is not None and t.error is None]
    errored = [t for t in trials if t.error is not None]

    buckets_raw: dict[str, list[BacktestTrial]] = defaultdict(list)
    for t in completed:
        buckets_raw[t.overall_signal.value].append(t)
    buckets = [_bucket_stats(sig, buckets_raw.get(sig.value, [])) for sig in Signal]

    directional = [t for t in completed if SIGNAL_TO_POSITION[t.overall_signal] != 0]
    hits = sum(
        1
        for t in directional
        if _same_sign(SIGNAL_TO_POSITION[t.overall_signal], t.realized_return)
    )
    overall_hit_rate = _fraction(hits, len(directional)) if directional else None

    directional_returns = [
        SIGNAL_TO_POSITION[t.overall_signal] * t.realized_return for t in completed
    ]
    active_returns = [
        SIGNAL_TO_POSITION[t.overall_signal] * t.realized_return for t in directional
    ]
    conviction_weighted = [t.conviction_score * t.realized_return for t in completed]

    # Independence: overlapping holding windows are not separate observations.
    # Only directional trials commit capital, so only they carry a window.
    n_eff = stats.effective_sample_size(
        [
            (t.ticker, t.as_of_date, t.exit_date)
            for t in directional
            if t.exit_date is not None
        ]
    )
    n_eff = n_eff or None

    # Round trip = both legs. Charged only where a position was actually taken.
    round_trip = 2.0 * cost_bps_per_side / 10_000.0
    net_directional_returns = [
        (SIGNAL_TO_POSITION[t.overall_signal] * t.realized_return - round_trip)
        if SIGNAL_TO_POSITION[t.overall_signal] != 0
        else 0.0
        for t in completed
    ]

    all_returns = [t.realized_return for t in completed]
    convictions = [t.conviction_score for t in completed]
    ic = _correlation(convictions, all_returns)

    t_stat, gross_p = stats.t_test_vs_zero(directional_returns, n_eff)
    _, net_p = stats.t_test_vs_zero(net_directional_returns, n_eff)

    sharpe = _safe_sharpe(directional_returns)
    skew = stats.skewness(directional_returns)
    kurt = stats.kurtosis(directional_returns)
    psr = (
        stats.probabilistic_sharpe_ratio(sharpe, int(n_eff), skew, kurt)
        if sharpe is not None and n_eff and n_eff >= 2
        else None
    )

    return PartitionReport(
        total_trials=len(trials),
        completed_trials=len(completed),
        errored_trials=len(errored),
        buckets=buckets,
        overall_hit_rate=overall_hit_rate,
        directional_mean_return=_safe_mean(directional_returns),
        conviction_weighted_return=_safe_mean(conviction_weighted),
        buy_and_hold_mean_return=_safe_mean(all_returns),
        directional_sharpe=sharpe,
        info_coefficient=ic,
        directional_trials=len(directional),
        active_mean_return=_safe_mean(active_returns),
        effective_n=n_eff,
        hit_rate_ci_95=stats.wilson_interval(hits, len(directional)) if directional else None,
        directional_mean_t_stat=t_stat,
        directional_mean_p_value=gross_p,
        info_coefficient_ci_95=(
            stats.fisher_ci(ic, len(completed)) if ic is not None else None
        ),
        return_skew=skew,
        return_kurtosis=kurt,
        probabilistic_sharpe=psr,
        cost_bps_per_side=cost_bps_per_side,
        net_directional_mean_return=_safe_mean(net_directional_returns),
        net_directional_sharpe=_safe_sharpe(net_directional_returns),
        net_mean_p_value=net_p,
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
    hit = f"- Overall directional hit rate: {_fmt_pct(r.overall_hit_rate)}"
    if r.hit_rate_ci_95:
        lo, hi = r.hit_rate_ci_95
        hit += f" (95% CI {_fmt_pct(lo)} – {_fmt_pct(hi)}{_coin_flip_note(lo, hi)})"
    hit += f" — n={r.directional_trials} directional trials"

    ic = f"- Information coefficient (conviction vs return): {_fmt_float(r.info_coefficient)}"
    if r.info_coefficient_ci_95:
        lo, hi = r.info_coefficient_ci_95
        ic += f" (95% CI {_fmt_float(lo)} – {_fmt_float(hi)}{_zero_note(lo, hi)})"

    lines = [
        hit,
        (
            f"- Mean return, directional trials only: {_fmt_pct(r.active_mean_return)} "
            f"(same denominator as the hit rate)"
        ),
        (
            f"- Mean return, all trials incl. flat: {_fmt_pct(r.directional_mean_return)}"
            f"{_significance_note(r.directional_mean_p_value)}"
        ),
        f"- Conviction-weighted mean return: {_fmt_pct(r.conviction_weighted_return)}",
        f"- Buy-and-hold baseline mean return: {_fmt_pct(r.buy_and_hold_mean_return)}",
        f"- Per-trial Sharpe (directional, gross): {_fmt_float(r.directional_sharpe)}",
        ic,
    ]

    if r.effective_n is not None:
        overlap = ""
        if r.directional_trials and r.effective_n < r.directional_trials * 0.95:
            ratio = r.effective_n / r.directional_trials
            overlap = (
                f" — overlapping holding windows collapse {r.directional_trials} nominal "
                f"trials to {r.effective_n:.1f} independent ones ({ratio * 100:.0f}%)"
            )
        lines.append(f"- Effective sample size: {r.effective_n:.1f}{overlap}")

    if r.directional_mean_t_stat is not None:
        lines.append(
            f"- t-statistic vs zero (on effective n): "
            f"{_fmt_float(r.directional_mean_t_stat)}, "
            f"p = {_fmt_p(r.directional_mean_p_value)}"
        )

    if r.probabilistic_sharpe is not None:
        lines.append(
            f"- Probabilistic Sharpe (P[true SR > 0], skew/kurtosis adjusted): "
            f"{_fmt_pct(r.probabilistic_sharpe)}"
        )

    if r.return_skew is not None or r.return_kurtosis is not None:
        lines.append(
            f"- Return distribution: skew {_fmt_float(r.return_skew)}, "
            f"kurtosis {_fmt_float(r.return_kurtosis)} (normal = 3.0)"
        )

    if r.cost_bps_per_side:
        lines += [
            (
                f"- **Net of costs** ({r.cost_bps_per_side:.1f} bps/side, "
                f"{r.cost_bps_per_side * 2:.1f} bps round trip): "
                f"mean {_fmt_pct(r.net_directional_mean_return)}"
                f"{_significance_note(r.net_mean_p_value)}, "
                f"Sharpe {_fmt_float(r.net_directional_sharpe)}"
            ),
        ]
    else:
        lines.append(
            "- ⚠ Costs not modelled — all figures above are gross. "
            "Pass `--cost-bps` for a net view."
        )

    return lines


def _small_sample_warning(r: PartitionReport) -> list[str]:
    """Escalating warnings, keyed on effective rather than nominal sample size.

    A run can show 40 completed trials and still carry the inferential weight
    of 6 once overlap is discounted, so the nominal count is the wrong trigger.
    """
    n_eff = r.effective_n or 0.0
    if r.completed_trials == 0:
        return ["", "> ⚠ No completed trials — nothing to infer from."]

    notes: list[str] = []
    if n_eff < 30:
        notes.append(
            f"> ⚠ Effective sample size is {n_eff:.1f} "
            f"({r.directional_trials} nominal directional trials). Below ~30 the "
            "interval estimates above are wide enough that almost any point "
            "estimate is consistent with zero edge. Extend the date range, add "
            "tickers, or widen the interval between as-of dates so windows stop "
            "overlapping."
        )
    if r.directional_trials and n_eff < r.directional_trials * 0.5:
        notes.append(
            "> ⚠ More than half the nominal sample is redundant through "
            "overlapping holding periods. Consider `--interval` ≥ `--horizon`."
        )
    if not notes:
        return []
    return ["", *notes]


def _coin_flip_note(lo: float, hi: float) -> str:
    """Flag a hit-rate interval that still contains 50%."""
    return ", spans 50% — not distinguishable from a coin flip" if lo <= 0.5 <= hi else ""


def _zero_note(lo: float, hi: float) -> str:
    return ", spans 0 — no demonstrated skill" if lo <= 0.0 <= hi else ""


def _significance_note(p: float | None) -> str:
    if p is None:
        return ""
    if p < 0.01:
        return f" (p = {_fmt_p(p)}, significant at 1%)"
    if p < 0.05:
        return f" (p = {_fmt_p(p)}, significant at 5%)"
    return f" (p = {_fmt_p(p)}, **not** significant)"


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
    pairs = [(x, y) for x, y in zip(xs, ys, strict=False) if x is not None and y is not None]
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


def _fmt_p(v: float | None) -> str:
    if v is None:
        return "n/a"
    if v < 0.001:
        return "<0.001"
    return f"{v:.3f}"
