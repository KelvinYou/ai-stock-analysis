"""Controlled AI-signal ablations on sealed, synchronized trial windows.

The module keeps the AI signal out of the allocator itself. It reports an
AI-only long sleeve and an AI-filtered momentum sleeve, then conditionally
permutes AI-positive labels inside each fixed momentum basket to test whether
the labels select better names at unchanged exposure.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable
from datetime import date, timedelta

from pydantic import BaseModel, Field

from stock_analysis.models.agent_reports import Signal

from . import stats
from .cross_sectional import CrossSectionalPeriod
from .runner import BacktestTrial

_BUY_STRENGTH = {Signal.BUY: 1, Signal.STRONG_BUY: 2}


class SignalAblationConfig(BaseModel):
    """Frozen accounting and randomization settings for the diagnostic."""

    top_n: int = Field(gt=0)
    cost_bps_per_side: float = Field(default=10.0, ge=0.0, lt=10_000.0)
    bootstrap_block_periods: int = Field(default=3, gt=0)
    bootstrap_resamples: int = Field(default=2_000, gt=0)
    bootstrap_seed: int = 0
    permutation_resamples: int = Field(default=2_000, gt=0)
    permutation_seed: int = 0


class SignalAblationPeriod(BaseModel):
    """Per-window candidate selections and equal-exposure controls."""

    as_of_date: date
    entry_date: date
    exit_date: date
    allocator_selected_tickers: list[str]
    ai_only_selected_tickers: list[str]
    hybrid_selected_tickers: list[str]
    ai_only_exposure: float
    hybrid_exposure: float
    allocator_net_return: float
    ai_only_net_return: float
    ai_only_matched_net_return: float
    hybrid_net_return: float
    hybrid_matched_allocator_net_return: float
    hybrid_positive_signals_in_basket: int


class SignalAblationArm(BaseModel):
    """Compound result versus an exposure-matched reference sleeve."""

    strategy: str
    net_compound_return: float
    matched_net_compound_return: float
    excess_return: float
    mean_exposure: float
    max_drawdown: float
    paired_log_excess_ci_95: tuple[float, float] | None


class SignalAblationReport(BaseModel):
    """Result of AI-only and hybrid signal attribution experiments."""

    hypothesis: str
    universe: list[str]
    config: SignalAblationConfig
    periods: int
    effective_n: float | None
    effective_n_basis: str = stats.PORTFOLIO_EFFECTIVE_N_BASIS
    candidate_arms_tested: int = 2
    allocator_net_compound_return: float
    ai_only: SignalAblationArm
    hybrid: SignalAblationArm
    permutation_status: str
    permutation_informative_periods: int
    permutation_resamples: int
    permutation_seed: int
    permutation_observed_mean_log_excess: float | None = None
    permutation_null_interval_95: tuple[float, float] | None = None
    permutation_upper_tail_p_value: float | None = None
    period_log: list[SignalAblationPeriod]
    drawdown_basis: str = "sealed_window_endpoints"
    price_basis: str = "sealed_trial_realized_return"


def run_signal_ablation(
    trials: Iterable[BacktestTrial],
    allocator_periods: Iterable[CrossSectionalPeriod],
    *,
    config: SignalAblationConfig,
) -> SignalAblationReport:
    """Compare AI-only and AI-filtered momentum on identical sealed windows.

    A BUY/STRONG_BUY signal occupies one fixed ``1 / top_n`` sleeve. Remaining
    sleeves stay in cash; shorts are not used. AI-only ranks positive signals
    by signal strength, then conviction, then ticker. The hybrid filters the
    price-momentum top-N basket to positive AI signals.

    For the hybrid's conditional randomization test, each period's number of
    positive labels in the momentum basket is held fixed, and labels are
    reassigned uniformly within that basket. This preserves dates, outcomes,
    selected momentum names, and gross exposure under the null.
    """

    trial_list = list(trials)
    periods = sorted(
        allocator_periods,
        key=lambda period: (period.entry_date or period.as_of_date, period.exit_date),
    )
    if not trial_list or not periods:
        raise ValueError("signal ablation requires completed trials and allocator periods")
    if len({period.as_of_date for period in periods}) != len(periods):
        raise ValueError("duplicate allocator period dates are not allowed")

    universe = sorted({trial.ticker.upper() for trial in trial_list})
    if config.top_n > len(universe):
        raise ValueError("top_n cannot exceed the sealed trial universe")

    grouped: dict[date, dict[str, BacktestTrial]] = {}
    for trial in trial_list:
        ticker = trial.ticker.upper()
        by_ticker = grouped.setdefault(trial.as_of_date, {})
        if ticker in by_ticker:
            raise ValueError(f"Duplicate trial: {ticker} @ {trial.as_of_date}")
        if trial.entry_date is None:
            raise ValueError(
                f"explicit next-session entry dates are required for signal ablation at {trial.as_of_date}"
            )
        if (
            trial.error is not None
            or trial.realized_return is None
            or trial.exit_date is None
            or not math.isfinite(trial.realized_return)
            or trial.realized_return < -1.0
            or not math.isfinite(trial.conviction_score)
        ):
            raise ValueError(f"Incomplete or invalid sealed trial: {ticker} @ {trial.as_of_date}")
        by_ticker[ticker] = trial
    if {period.as_of_date for period in periods} != set(grouped):
        raise ValueError("allocator periods must cover exactly the sealed trial date groups")

    previous_exit: date | None = None
    cost_rate = config.cost_bps_per_side / 10_000.0
    period_results: list[SignalAblationPeriod] = []
    ai_only_returns: list[float] = []
    ai_only_baselines: list[float] = []
    ai_only_exposures: list[float] = []
    hybrid_returns: list[float] = []
    hybrid_baselines: list[float] = []
    hybrid_exposures: list[float] = []
    allocator_returns: list[float] = []
    permutation_cases: list[tuple[dict[str, float], list[str], int]] = []

    for period in periods:
        as_of = period.as_of_date
        by_ticker = grouped.get(as_of)
        if by_ticker is None or set(by_ticker) != set(universe):
            raise ValueError(f"Incomplete sealed signal group at {as_of}")
        if period.entry_date is None:
            raise ValueError(
                f"explicit next-session entry dates are required for signal ablation at {as_of}"
            )

        entry_date = period.entry_date
        if entry_date >= period.exit_date:
            raise ValueError(f"Invalid sealed trial window at {as_of}")
        if previous_exit is not None and entry_date <= previous_exit:
            raise ValueError("overlapping sealed windows: trial windows must be sequential")
        previous_exit = period.exit_date

        for trial in by_ticker.values():
            trial_entry = trial.entry_date
            if trial_entry != entry_date or trial.exit_date != period.exit_date:
                raise ValueError(f"Allocator and AI trials do not share the same window at {as_of}")

        momentum_names = [ticker.upper() for ticker in period.selected_tickers]
        if (
            len(momentum_names) != config.top_n
            or len(set(momentum_names)) != config.top_n
            or not set(momentum_names).issubset(universe)
        ):
            raise ValueError(f"Invalid momentum selection at {as_of}")

        returns = {ticker: float(trial.realized_return) for ticker, trial in by_ticker.items()}
        ai_positive = [ticker for ticker in universe if _is_ai_positive(by_ticker[ticker])]
        ai_only_names = sorted(
            ai_positive,
            key=lambda ticker: (
                -_BUY_STRENGTH[by_ticker[ticker].overall_signal],
                -by_ticker[ticker].conviction_score,
                ticker,
            ),
        )[: config.top_n]
        hybrid_names = [ticker for ticker in momentum_names if _is_ai_positive(by_ticker[ticker])]

        ai_exposure = len(ai_only_names) / config.top_n
        hybrid_exposure = len(hybrid_names) / config.top_n
        ai_net = _portfolio_net_return(
            {ticker: 1.0 / config.top_n for ticker in ai_only_names},
            returns,
            cost_rate,
        )
        ai_matched = _portfolio_net_return(
            {ticker: ai_exposure / len(universe) for ticker in universe},
            returns,
            cost_rate,
        )
        hybrid_net = _portfolio_net_return(
            {ticker: 1.0 / config.top_n for ticker in hybrid_names},
            returns,
            cost_rate,
        )
        hybrid_matched = _portfolio_net_return(
            {ticker: hybrid_exposure / config.top_n for ticker in momentum_names},
            returns,
            cost_rate,
        )
        allocator_net = _portfolio_net_return(
            {ticker: 1.0 / config.top_n for ticker in momentum_names},
            returns,
            cost_rate,
        )
        if not math.isclose(allocator_net, period.net_return, rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError(f"Allocator return does not reconcile with sealed trials at {as_of}")

        period_results.append(
            SignalAblationPeriod(
                as_of_date=as_of,
                entry_date=entry_date,
                exit_date=period.exit_date,
                allocator_selected_tickers=momentum_names,
                ai_only_selected_tickers=ai_only_names,
                hybrid_selected_tickers=hybrid_names,
                ai_only_exposure=ai_exposure,
                hybrid_exposure=hybrid_exposure,
                allocator_net_return=allocator_net,
                ai_only_net_return=ai_net,
                ai_only_matched_net_return=ai_matched,
                hybrid_net_return=hybrid_net,
                hybrid_matched_allocator_net_return=hybrid_matched,
                hybrid_positive_signals_in_basket=len(hybrid_names),
            )
        )
        ai_only_returns.append(ai_net)
        ai_only_baselines.append(ai_matched)
        ai_only_exposures.append(ai_exposure)
        hybrid_returns.append(hybrid_net)
        hybrid_baselines.append(hybrid_matched)
        hybrid_exposures.append(hybrid_exposure)
        allocator_returns.append(allocator_net)
        permutation_cases.append((returns, momentum_names, len(hybrid_names)))

    informative_periods = sum(
        0 < positive_count < config.top_n for _, _, positive_count in permutation_cases
    )
    permutation_status = "INFORMATIVE" if informative_periods else "UNINFORMATIVE"
    observed_log_excess: float | None = None
    null_interval: tuple[float, float] | None = None
    permutation_p: float | None = None
    if informative_periods:
        observed_values = _paired_log_excess(hybrid_returns, hybrid_baselines)
        observed_log_excess = sum(observed_values) / len(observed_values)
        rng = random.Random(config.permutation_seed)
        null_statistics: list[float] = []
        for _ in range(config.permutation_resamples):
            permuted_excess: list[float] = []
            for returns, momentum_names, positive_count in permutation_cases:
                selected = (
                    rng.sample(momentum_names, positive_count)
                    if 0 < positive_count < config.top_n
                    else momentum_names[:positive_count]
                )
                exposure = positive_count / config.top_n
                candidate = _portfolio_net_return(
                    {ticker: 1.0 / config.top_n for ticker in selected},
                    returns,
                    cost_rate,
                )
                matched = _portfolio_net_return(
                    {ticker: exposure / config.top_n for ticker in momentum_names},
                    returns,
                    cost_rate,
                )
                permuted_excess.append(_log_excess(candidate, matched))
            null_statistics.append(sum(permuted_excess) / len(permuted_excess))
        null_interval = (
            _percentile(null_statistics, 0.025),
            _percentile(null_statistics, 0.975),
        )
        permutation_p = (1 + sum(value >= observed_log_excess for value in null_statistics)) / (
            config.permutation_resamples + 1
        )

    windows = [
        (
            "portfolio",
            period.entry_date,
            max(period.entry_date, period.exit_date - timedelta(days=1)),
        )
        for period in period_results
    ]
    effective_n = stats.effective_sample_size(windows) or None

    return SignalAblationReport(
        hypothesis=(
            "AI BUY/STRONG_BUY labels improve selection over an exposure-matched "
            "passive sleeve, and improve a price-momentum basket when the AI label "
            "is used only as a long-only filter."
        ),
        universe=universe,
        config=config,
        periods=len(period_results),
        effective_n=effective_n,
        allocator_net_compound_return=_compound(allocator_returns),
        ai_only=_arm_report(
            "AI-only long", ai_only_returns, ai_only_baselines, ai_only_exposures, config
        ),
        hybrid=_arm_report(
            "AI-filtered momentum",
            hybrid_returns,
            hybrid_baselines,
            hybrid_exposures,
            config,
        ),
        permutation_status=permutation_status,
        permutation_informative_periods=informative_periods,
        permutation_resamples=config.permutation_resamples,
        permutation_seed=config.permutation_seed,
        permutation_observed_mean_log_excess=observed_log_excess,
        permutation_null_interval_95=null_interval,
        permutation_upper_tail_p_value=permutation_p,
        period_log=period_results,
    )


def signal_ablation_to_markdown(report: SignalAblationReport) -> str:
    """Render the ablation while keeping attribution and limitations explicit."""

    lines = [
        "## AI Signal Ablation",
        "",
        f"- Universe: {', '.join(report.universe)}",
        f"- Periods / effective n: {report.periods} / {_fmt(report.effective_n)}",
        f"- Candidate arms counted: {report.candidate_arms_tested}",
        f"- Cost: {report.config.cost_bps_per_side:g} bps per side",
        f"- Price / drawdown basis: `{report.price_basis}` / `{report.drawdown_basis}`",
        f"- Allocator-only net compound return: {_fmt_pct(report.allocator_net_compound_return)}",
        "",
        "| Diagnostic arm | Net compound | Exposure-matched reference | Excess | Mean exposure | Max DD (window endpoints) | 95% paired log-excess CI |",
        "|---|---:|---:|---:|---:|---:|---:|",
        _arm_row(report.ai_only),
        _arm_row(report.hybrid),
        "",
        "### Conditional AI-label permutation",
        "",
    ]
    if report.permutation_status == "INFORMATIVE":
        lines.extend(
            [
                f"- Observed mean hybrid log excess over exposure-matched momentum: {_fmt(report.permutation_observed_mean_log_excess)}",
                f"- Null 95% interval: {_fmt_ci(report.permutation_null_interval_95)}",
                f"- One-sided conditional permutation p-value: {_fmt(report.permutation_upper_tail_p_value)}",
                f"- Randomization: {report.permutation_resamples} draws, seed {report.permutation_seed}; informative windows {report.permutation_informative_periods}/{report.periods}.",
            ]
        )
    else:
        lines.append(
            "- **Uninformative:** no momentum basket has a mix of AI-positive and other labels, so within-basket selection cannot be tested."
        )
    lines.extend(
        [
            "",
            "- Each positive AI signal gets a fixed `1 / top_n` long-only sleeve; unused sleeves remain in cash. AI-only ranks BUY/STRONG_BUY by signal strength, conviction, then ticker. The hybrid intersects AI-positive names with the fixed momentum top-N basket.",
            "- Exposure-matched references retain the same dates and total invested weight. The permutation holds each period's momentum basket and AI-positive count fixed, randomizing only which basket names receive positive labels.",
            "- Maximum drawdown marks only the ordered sealed-window endpoints; it misses intra-window losses. This is a conditional attribution diagnostic, not a general forecast-significance test or promotion result. Small samples, historical universe survivorship, provider provenance, dividend basis, and execution-cost calibration remain unresolved. Do not tune the tested rule on these same periods.",
        ]
    )
    return "\n".join(lines)


def _is_ai_positive(trial: BacktestTrial) -> bool:
    return trial.overall_signal in _BUY_STRENGTH


def _portfolio_net_return(
    weights: dict[str, float], returns: dict[str, float], cost_rate: float
) -> float:
    cost_multiplier = (1.0 - cost_rate) ** 2
    return sum(
        weight * ((1.0 + returns[ticker]) * cost_multiplier - 1.0)
        for ticker, weight in weights.items()
    )


def _paired_log_excess(candidate: list[float], baseline: list[float]) -> list[float]:
    return [
        _log_excess(candidate_return, baseline_return)
        for candidate_return, baseline_return in zip(candidate, baseline, strict=True)
    ]


def _log_excess(candidate: float, baseline: float) -> float:
    if candidate <= -1.0 or baseline <= -1.0:
        raise ValueError("log-excess attribution is undefined after a total loss")
    return math.log1p(candidate) - math.log1p(baseline)


def _arm_report(
    name: str,
    returns: list[float],
    baselines: list[float],
    exposures: list[float],
    config: SignalAblationConfig,
) -> SignalAblationArm:
    paired = _paired_log_excess(returns, baselines)
    return SignalAblationArm(
        strategy=name,
        net_compound_return=_compound(returns),
        matched_net_compound_return=_compound(baselines),
        excess_return=_compound(returns) - _compound(baselines),
        mean_exposure=sum(exposures) / len(exposures),
        max_drawdown=_max_drawdown(returns),
        paired_log_excess_ci_95=stats.moving_block_bootstrap_ci(
            paired,
            block_length=config.bootstrap_block_periods,
            n_resamples=config.bootstrap_resamples,
            seed=config.bootstrap_seed,
        ),
    )


def _compound(returns: list[float]) -> float:
    equity = 1.0
    for value in returns:
        equity *= 1.0 + value
    return equity - 1.0


def _max_drawdown(returns: list[float]) -> float:
    equity = peak = 1.0
    drawdown = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1.0)
    return drawdown


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _arm_row(arm: SignalAblationArm) -> str:
    return (
        f"| {arm.strategy} | {_fmt_pct(arm.net_compound_return)} | "
        f"{_fmt_pct(arm.matched_net_compound_return)} | {_fmt_pct(arm.excess_return)} | "
        f"{_fmt_pct(arm.mean_exposure)} | {_fmt_pct(arm.max_drawdown)} | "
        f"{_fmt_ci(arm.paired_log_excess_ci_95)} |"
    )


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _fmt_ci(value: tuple[float, float] | None) -> str:
    return (
        "n/a (insufficient paired periods)"
        if value is None
        else f"[{value[0]:.4f}, {value[1]:.4f}]"
    )
