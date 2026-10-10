"""Synthetic portfolio simulator for backtests only.

This module turns BacktestTrial signals into an equity curve. It never reads
real holdings, private account data, or portfolio policy files.

Event-driven model:
- Each directional trial reserves `position_size_pct` of cash available before
  that session's entries. Same-day orders share one cash snapshot and are
  scaled equally if their aggregate target would exceed available cash.
- Cash is reserved at entry, P&L released at exit. No marked-to-market between events
  in the event ledger; when same-source daily bars are present, reports rebuild a
  daily close-marked equity curve. Missing paths make drawdown unavailable.
- Neutral signals skipped. Sell signals skipped unless `allow_short=True`.
- Multiple strategies can be compared: overall synthesis, each agent in isolation,
  a strict equal-weight buy-and-hold baseline, or the legacy rolling-long baseline.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import BaseModel, Field

from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.market_data import MacroSnapshot, PriceBar

from . import stats
from .runner import BacktestResult, BacktestTrial

SIGNAL_TO_POSITION: dict[str, int] = {
    "strong_buy": 1,
    "buy": 1,
    "neutral": 0,
    "sell": -1,
    "strong_sell": -1,
}


class PortfolioConfig(BaseModel):
    starting_balance: float = 10_000.0
    position_size_pct: float = 0.10  # fraction of pre-session cash per trade
    allow_short: bool = False
    # One-way cost in basis points, charged on entry and again on exit. Covers
    # commission, spread, and slippage together. Zero is the historical default
    # but is a claim about the world, not a neutral choice — a strategy trading
    # a 30-day horizon on Bursa small caps can have its entire edge inside the
    # spread.
    cost_bps_per_side: float = 0.0
    bootstrap_block_days: int = Field(default=21, gt=0)
    bootstrap_resamples: int = Field(default=2_000, gt=0)
    bootstrap_seed: int = 0


class TradeLog(BaseModel):
    ticker: str
    entry_date: date
    exit_date: date
    direction: int  # +1 long, -1 short
    stake: float  # capital committed
    pnl: float  # realized dollar P&L
    return_pct: float
    entry_price: float | None = None
    exit_price: float | None = None


class EquityPoint(BaseModel):
    date: date
    equity: float


class StrategyReport(BaseModel):
    strategy: str  # "overall", agent names, "buy_and_hold", or "rolling_long"
    starting_balance: float
    final_balance: float
    total_return_pct: float
    max_drawdown_pct: float | None
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None
    equity_curve: list[EquityPoint]
    trades: list[TradeLog]
    drawdown_basis: str = "event_only_incomplete"

    # Stake-use diagnostics normalized by starting balance. They are not
    # mark-to-market beta or gross-exposure estimates.
    mean_committed_principal_pct: float | None = None
    peak_committed_principal_pct: float | None = None
    capital_utilization_active_sessions: int | None = None
    capital_utilization_market_sessions: int | None = None
    capital_utilization_basis: str | None = None

    # Per-trade Sharpe and its selection-bias-aware companions. Every candidate
    # DSR is corrected for the full candidate count in this comparison.
    trade_sharpe: float | None = None
    effective_n: float | None = None
    effective_n_basis: str = stats.PORTFOLIO_EFFECTIVE_N_BASIS
    probabilistic_sharpe: float | None = None
    deflated_sharpe: float | None = None

    # Comparison with the strict long benchmark in the same simulation. These
    # are deliberately separate from Sharpe: a strategy can rank first on
    # per-trade Sharpe while still losing money relative to simply staying
    # invested.
    benchmark_return_pct: float | None = None
    excess_return_pct: float | None = None
    beats_benchmark: bool | None = None
    matched_exposure_baseline_return_pct: float | None = None
    matched_exposure_excess_pct: float | None = None
    beats_matched_exposure_baseline: bool | None = None
    cash_yield_adjusted_return_pct: float | None = None
    cash_yield_uplift_pct: float | None = None
    cash_yield_adjusted_excess_vs_strict_hold_pct: float | None = None
    cash_yield_adjusted_excess_vs_cash_pct: float | None = None
    cash_adjusted_matched_exposure_return_pct: float | None = None
    cash_adjusted_matched_exposure_excess_pct: float | None = None
    strict_hold_log_excess_ci_95: tuple[float, float] | None = None
    twice_cost_return_pct: float | None = None
    twice_cost_excess_pct: float | None = None


class PortfolioReport(BaseModel):
    config: PortfolioConfig
    strategies: list[StrategyReport]
    # Number of strategies compared in this run. The winner's Sharpe has to be
    # read against this: pick the best of several coin-flipping strategies and
    # the best one looks good by construction.
    n_strategies_tested: int = 0
    best_strategy: str | None = None
    benchmark_strategy: str | None = "buy_and_hold"
    best_return_strategy: str | None = None
    benchmark_beaten: bool | None = None
    promotion_ready: bool | None = None
    cash_proxy_return_pct: float | None = None
    cash_proxy_source: str | None = None
    cash_proxy_replay_sha256: str | None = None
    cash_proxy_basis: str | None = None
    cash_proxy_unavailable_reason: str | None = None


_MIN_PROMOTION_EFFECTIVE_N = 30.0
_MIN_PROMOTION_DSR = 0.95
_MAX_CASH_RATE_STALENESS_DAYS = 4


# ----------------------------------------------------------------------
@dataclass
class _OpenPosition:
    ticker: str
    entry_date: date
    direction: int
    stake: float
    realized_return: float  # known from the trial (forward-looking, fixed horizon)
    entry_price: float
    exit_price: float | None


def simulate(
    result: BacktestResult,
    config: PortfolioConfig | None = None,
    strategies: list[str] | None = None,
) -> PortfolioReport:
    """Run one or more strategies over the trial set. Returns per-strategy stats."""
    config = config or PortfolioConfig()
    incomplete = [
        trial
        for trial in result.trials
        if trial.error is not None
        or trial.realized_return is None
        or trial.exit_date is None
        or trial.exit_price is None
        or not math.isfinite(trial.entry_price)
        or trial.entry_price <= 0
        or not math.isfinite(trial.exit_price)
        or trial.exit_price <= 0
    ]
    if incomplete:
        first = incomplete[0]
        raise ValueError(
            "Portfolio comparison requires complete trial outcomes for the "
            f"frozen panel; {len(incomplete)}/{len(result.trials)} incomplete "
            f"(first: {first.ticker} @ {first.as_of_date})."
        )
    strategies = strategies or [
        "overall",
        "overall_fundamentals_confirmed",
        "fundamentals",
        "technical",
        "sentiment",
        "macro",
        "buy_and_hold",
        "rolling_long",
        "signal_timing_long",
    ]

    reports = [_simulate_one(result, config, s) for s in strategies]
    _attach_selection_bias_metrics(reports)
    _attach_capital_utilization_metrics(reports, result, config)

    benchmark = next((r for r in reports if r.strategy == "buy_and_hold"), None)
    _attach_benchmark_comparison(reports, benchmark)
    _attach_matched_exposure_comparison(reports, result, config)
    _attach_paired_strict_hold_intervals(reports, benchmark, config)
    cash_proxy_return, cash_proxy_reason = _attach_cash_yield_diagnostics(
        reports, result, config, benchmark
    )

    twice_cost_config = config.model_copy(
        update={"cost_bps_per_side": 2.0 * config.cost_bps_per_side}
    )
    twice_cost_reports = {
        strategy: _simulate_one(result, twice_cost_config, strategy)
        for strategy in strategies
    }
    twice_cost_benchmark = twice_cost_reports.get("buy_and_hold")
    for report in reports:
        stressed = twice_cost_reports[report.strategy]
        report.twice_cost_return_pct = stressed.total_return_pct
        if twice_cost_benchmark is not None:
            report.twice_cost_excess_pct = (
                stressed.total_return_pct - twice_cost_benchmark.total_return_pct
            )

    ranked = [r for r in reports if r.trade_sharpe is not None]
    best = max(ranked, key=lambda r: r.trade_sharpe).strategy if ranked else None
    return_ranked = [r for r in reports if r is not benchmark]
    best_return = (
        max(return_ranked, key=lambda r: r.total_return_pct).strategy
        if return_ranked
        else None
    )
    pipeline_report = next((r for r in reports if r.strategy == "overall"), None)
    benchmark_beaten = (
        pipeline_report.beats_benchmark
        if benchmark is not None and pipeline_report is not None
        else None
    )

    return PortfolioReport(
        config=config,
        strategies=reports,
        n_strategies_tested=len(reports),
        best_strategy=best,
        benchmark_strategy=benchmark.strategy if benchmark else None,
        best_return_strategy=best_return,
        benchmark_beaten=benchmark_beaten,
        promotion_ready=_promotion_ready(
            reports, benchmark, modeled_cost=config.cost_bps_per_side > 0
        ),
        cash_proxy_return_pct=cash_proxy_return,
        cash_proxy_source=(
            str(result.settings.get("cash_rate_source"))
            if result.cash_rate_path
            else None
        ),
        cash_proxy_replay_sha256=(
            str(result.settings.get("cash_rate_replay_sha256"))
            if result.cash_rate_path
            and result.settings.get("cash_rate_replay_sha256")
            else None
        ),
        cash_proxy_basis=(
            "FRED:DFF annualized percent; latest observation is usable only on/after "
            "available_as_of; daily compounding on end-of-day uninvested cash using ACT/365; "
            "last available observation carried for at most four calendar days"
            if result.cash_rate_path and cash_proxy_reason is None
            else None
        ),
        cash_proxy_unavailable_reason=cash_proxy_reason,
    )


def _round_trip_cost(config: PortfolioConfig) -> float:
    """Entry + exit cost as a fraction of the stake."""
    return 2.0 * config.cost_bps_per_side / 10_000.0


def _attach_selection_bias_metrics(reports: list[StrategyReport]) -> None:
    """Populate Sharpe, PSR, and selection-adjusted Sharpe for each candidate.

    The deflated Sharpe answers the question the strategy table otherwise
    invites the reader to skip: the best row was chosen *because* it was best,
    so its Sharpe is an order statistic, not a sample mean. DSR reprices it
    against the expected maximum across this many candidates under the null of
    no skill.
    """
    for report in reports:
        returns = [t.return_pct for t in report.trades]
        # All securities in this strategy share a portfolio and may be
        # cross-sectionally dependent. One cluster key makes same-date trades
        # count as one observation and also discounts overlapping dates.
        n_eff = stats.effective_sample_size(
            [("portfolio", t.entry_date, t.exit_date) for t in report.trades]
        )
        report.effective_n = n_eff or None
        report.trade_sharpe = _sharpe(returns)
        if report.trade_sharpe is not None and n_eff >= 2:
            report.probabilistic_sharpe = stats.probabilistic_sharpe_ratio(
                report.trade_sharpe,
                int(n_eff),
                stats.skewness(returns),
                stats.kurtosis(returns),
            )

    ranked = [r for r in reports if r.trade_sharpe is not None]
    if len(ranked) < 2:
        return

    sharpes = [r.trade_sharpe for r in ranked]
    mean_sr = sum(sharpes) / len(sharpes)
    sr_variance = sum((s - mean_sr) ** 2 for s in sharpes) / (len(sharpes) - 1)

    for report in ranked:
        if report.effective_n and report.effective_n >= 2:
            report.deflated_sharpe = stats.deflated_sharpe_ratio(
                report.trade_sharpe,
                int(report.effective_n),
                stats.skewness([t.return_pct for t in report.trades]),
                stats.kurtosis([t.return_pct for t in report.trades]),
                n_strategies=len(reports),
                sr_variance=sr_variance,
            )


def _attach_capital_utilization_metrics(
    reports: list[StrategyReport],
    result: BacktestResult,
    config: PortfolioConfig,
) -> None:
    """Summarize committed stake on the shared price-path session set.

    Every strategy uses the same window: the first completed trial entry
    through the last completed trial exit. Positions count on both entry and
    exit sessions. The metric uses original trade stake, not market value, so
    it diagnoses cash deployment without pretending to be beta exposure.
    """

    completed = [
        trial
        for trial in result.trials
        if trial.realized_return is not None and trial.exit_date is not None
    ]
    if not completed or not result.price_paths or config.starting_balance <= 0:
        return

    start_date = min(trial.entry_date or trial.as_of_date for trial in completed)
    end_date = max(trial.exit_date for trial in completed)
    market_sessions = sorted(
        {
            bar.date
            for bars in result.price_paths.values()
            for bar in bars
            if start_date <= bar.date <= end_date
        }
    )
    if not market_sessions:
        return

    for report in reports:
        committed_by_session = [
            sum(
                trade.stake
                for trade in report.trades
                if trade.entry_date <= day <= trade.exit_date
            )
            for day in market_sessions
        ]
        report.mean_committed_principal_pct = (
            sum(committed_by_session)
            / len(market_sessions)
            / config.starting_balance
        )
        report.peak_committed_principal_pct = (
            max(committed_by_session) / config.starting_balance
        )
        report.capital_utilization_active_sessions = sum(
            amount > 0 for amount in committed_by_session
        )
        report.capital_utilization_market_sessions = len(market_sessions)
        report.capital_utilization_basis = (
            "original trade stake on the union of available price-path sessions; "
            "entry and exit sessions included; not mark-to-market exposure"
        )


def _attach_benchmark_comparison(
    reports: list[StrategyReport],
    benchmark: StrategyReport | None,
) -> None:
    """Attach an explicit return comparison to every strategy report."""
    if benchmark is None:
        return
    for report in reports:
        report.benchmark_return_pct = benchmark.total_return_pct
        report.excess_return_pct = report.total_return_pct - benchmark.total_return_pct
        report.beats_benchmark = (
            report.strategy != benchmark.strategy
            and report.total_return_pct > benchmark.total_return_pct
        )


def _attach_matched_exposure_comparison(
    reports: list[StrategyReport],
    result: BacktestResult,
    config: PortfolioConfig,
) -> None:
    """Compare each signal strategy with a passive basket on its active windows.

    The passive basket uses the same entry/exit dates and the same dollar stake
    schedule as the candidate, but equal-weights all names in the run universe.
    This is an exposure/selection diagnostic, not an independent timing test.
    """

    for report in reports:
        if report.strategy == "buy_and_hold":
            continue
        passive_return = _matched_exposure_return(
            report.trades, result.price_paths, config
        )
        report.matched_exposure_baseline_return_pct = passive_return
        if passive_return is not None:
            report.matched_exposure_excess_pct = (
                report.total_return_pct - passive_return
            )
            report.beats_matched_exposure_baseline = (
                report.total_return_pct > passive_return
            )


def _attach_cash_yield_diagnostics(
    reports: list[StrategyReport],
    result: BacktestResult,
    config: PortfolioConfig,
    benchmark: StrategyReport | None,
) -> tuple[float | None, str | None]:
    """Add a DFF cash proxy without changing any primary strategy return."""
    if not result.cash_rate_path:
        return None, "No dated FRED:DFF replay was supplied."

    completed = [
        trial
        for trial in result.trials
        if trial.exit_date is not None and trial.realized_return is not None
    ]
    if not completed:
        return None, "No completed trials define the cash-proxy window."
    start_date = min(trial.entry_date or trial.as_of_date for trial in completed)
    end_date = max(trial.exit_date for trial in completed if trial.exit_date is not None)
    observations = sorted(
        result.cash_rate_path,
        key=lambda item: (item.available_as_of, item.as_of_date),
    )
    availability_dates = [item.available_as_of for item in observations]
    missing_day = _first_cash_rate_gap(start_date, end_date, observations, availability_dates)
    if missing_day is not None:
        return (
            None,
            (
                f"FRED:DFF has no timely available observation for {missing_day}; "
                "no zero-rate or stale-rate fallback was used."
            ),
        )

    cash_proxy_return = _cash_balance_return(
        [], config, start_date, end_date, observations, availability_dates
    )
    if cash_proxy_return is None:
        return None, "The dated FRED:DFF cash proxy could not be simulated."

    for report in reports:
        adjusted_return = _cash_balance_return(
            report.trades, config, start_date, end_date, observations, availability_dates
        )
        if adjusted_return is None:
            continue
        report.cash_yield_adjusted_return_pct = adjusted_return
        report.cash_yield_uplift_pct = adjusted_return - report.total_return_pct
        report.cash_yield_adjusted_excess_vs_cash_pct = (
            adjusted_return - cash_proxy_return
        )
        if benchmark is not None:
            report.cash_yield_adjusted_excess_vs_strict_hold_pct = (
                adjusted_return - benchmark.total_return_pct
            )

        if report.strategy == "buy_and_hold":
            continue
        passive_trades = _matched_exposure_trades(
            report.trades, result.price_paths, config
        )
        if passive_trades is None:
            continue
        adjusted_passive = _cash_balance_return(
            passive_trades,
            config,
            start_date,
            end_date,
            observations,
            availability_dates,
        )
        if adjusted_passive is not None:
            report.cash_adjusted_matched_exposure_return_pct = adjusted_passive
            report.cash_adjusted_matched_exposure_excess_pct = (
                adjusted_return - adjusted_passive
            )

    return cash_proxy_return, None


def _first_cash_rate_gap(
    start_date: date,
    end_date: date,
    observations: list[MacroSnapshot],
    availability_dates: list[date],
) -> date | None:
    day = start_date
    while day < end_date:
        if _cash_rate_for_day(day, observations, availability_dates) is None:
            return day
        day += timedelta(days=1)
    return None


def _cash_rate_for_day(
    day: date,
    observations: list[MacroSnapshot],
    availability_dates: list[date],
) -> float | None:
    index = bisect_right(availability_dates, day) - 1
    if index < 0:
        return None
    observation = observations[index]
    if (day - observation.available_as_of).days > _MAX_CASH_RATE_STALENESS_DAYS:
        return None
    rate = observation.fed_funds_rate
    return rate if rate is not None and math.isfinite(rate) and rate >= 0 else None


def _cash_balance_return(
    trades: list[TradeLog],
    config: PortfolioConfig,
    start_date: date,
    end_date: date,
    observations: list[MacroSnapshot],
    availability_dates: list[date],
) -> float | None:
    """Replay fixed trade cash flows while idle cash earns available DFF."""
    entries: dict[date, list[TradeLog]] = defaultdict(list)
    exits: dict[date, list[TradeLog]] = defaultdict(list)
    for trade in trades:
        entries[trade.entry_date].append(trade)
        exits[trade.exit_date].append(trade)

    cash = config.starting_balance
    day = start_date
    while day <= end_date:
        # Enter at the open and release exit proceeds at the close. Same-day
        # exit proceeds cannot fund open orders.
        for trade in entries.get(day, []):
            if trade.stake > cash + 1e-9:
                return None
            cash -= trade.stake
        for trade in exits.get(day, []):
            cash += trade.stake + trade.pnl
            if cash < 0 or not math.isfinite(cash):
                return None
        # The rate for this calendar date compounds the free cash held after
        # today's close through the next calendar day. The scored window ends
        # at the final exit close, so it earns no post-window interest.
        if day < end_date:
            annual_rate_pct = _cash_rate_for_day(day, observations, availability_dates)
            if annual_rate_pct is None:
                return None
            cash *= 1.0 + (annual_rate_pct / 100.0) / 365.0
        day += timedelta(days=1)

    return (cash - config.starting_balance) / config.starting_balance


def _matched_exposure_trades(
    trades: list[TradeLog],
    price_paths: Mapping[str, list[PriceBar]],
    config: PortfolioConfig,
) -> list[TradeLog] | None:
    """Build passive all-name trades using candidate dates and dollar stakes."""
    if not trades or not price_paths:
        return None
    universe = sorted(price_paths)
    bars_by_ticker = {
        ticker.upper(): {bar.date: bar for bar in bars}
        for ticker, bars in price_paths.items()
    }
    round_trip_cost = _round_trip_cost(config)
    passive: list[TradeLog] = []
    for trade in trades:
        ticker_returns: list[float] = []
        for ticker in universe:
            bars = bars_by_ticker.get(ticker.upper(), {})
            entry = bars.get(trade.entry_date)
            exit_ = bars.get(trade.exit_date)
            if entry is None or exit_ is None or entry.open <= 0:
                return None
            gross_return = float(exit_.close) / float(entry.open) - 1.0
            if not math.isfinite(gross_return):
                return None
            ticker_returns.append(gross_return)
        net_return = sum(ticker_returns) / len(ticker_returns) - round_trip_cost
        passive.append(
            TradeLog(
                ticker="matched_passive",
                entry_date=trade.entry_date,
                exit_date=trade.exit_date,
                direction=1,
                stake=trade.stake,
                pnl=trade.stake * net_return,
                return_pct=net_return,
            )
        )
    return passive


def _matched_exposure_return(
    trades: list[TradeLog],
    price_paths: Mapping[str, list[PriceBar]],
    config: PortfolioConfig,
) -> float | None:
    """Simulate an all-name passive basket on the exact candidate trade windows."""

    if not trades or not price_paths:
        return None
    universe = sorted(price_paths)
    bars_by_ticker = {
        ticker.upper(): {bar.date: bar for bar in bars}
        for ticker, bars in price_paths.items()
    }
    windows: dict[tuple[date, date], float] = {}
    for trade in trades:
        returns: list[float] = []
        for ticker in universe:
            ticker_bars = bars_by_ticker.get(ticker.upper(), {})
            entry = ticker_bars.get(trade.entry_date)
            exit_ = ticker_bars.get(trade.exit_date)
            if entry is None or exit_ is None or entry.open <= 0:
                return None
            value = float(exit_.close) / float(entry.open) - 1.0
            if not math.isfinite(value):
                return None
            returns.append(value)
        windows[(trade.entry_date, trade.exit_date)] = sum(returns) / len(returns)

    cash = config.starting_balance
    pending: dict[date, list[tuple[float, float]]] = defaultdict(list)
    round_trip_cost = _round_trip_cost(config)

    def settle_through(day: date, *, inclusive: bool) -> bool:
        nonlocal cash
        due_dates = (
            sorted(item for item in pending if item <= day)
            if inclusive
            else sorted(item for item in pending if item < day)
        )
        for exit_date in due_dates:
            for stake, gross_return in pending.pop(exit_date):
                cash += stake * (1.0 + gross_return - round_trip_cost)
                if cash < 0 or not math.isfinite(cash):
                    return False
        return True

    trades_by_entry: dict[date, list[TradeLog]] = defaultdict(list)
    for trade in trades:
        trades_by_entry[trade.entry_date].append(trade)
    for entry_date in sorted(trades_by_entry):
        if not settle_through(entry_date, inclusive=False):
            return None
        for trade in trades_by_entry[entry_date]:
            if trade.stake > cash + 1e-9:
                return None
            gross_return = windows[(trade.entry_date, trade.exit_date)]
            cash -= trade.stake
            pending[trade.exit_date].append((trade.stake, gross_return))
        if not settle_through(entry_date, inclusive=True):
            return None
    if pending and not settle_through(max(pending), inclusive=True):
        return None
    return (cash - config.starting_balance) / config.starting_balance


def _attach_paired_strict_hold_intervals(
    reports: list[StrategyReport],
    benchmark: StrategyReport | None,
    config: PortfolioConfig,
) -> None:
    """Attach moving-block CIs of daily log excess on the shared test dates."""

    if benchmark is None or benchmark.drawdown_basis != "daily_close_mark_to_market":
        return
    benchmark_curve = _one_equity_point_per_day(benchmark.equity_curve)
    if len(benchmark_curve) < 2:
        return
    for report in reports:
        if (
            report is benchmark
            or report.drawdown_basis != "daily_close_mark_to_market"
        ):
            continue
        candidate_curve = _one_equity_point_per_day(report.equity_curve)
        if [point.date for point in candidate_curve] != [
            point.date for point in benchmark_curve
        ]:
            continue
        paired_daily_log_excess: list[float] = []
        for previous, current, benchmark_previous, benchmark_current in zip(
            candidate_curve[:-1],
            candidate_curve[1:],
            benchmark_curve[:-1],
            benchmark_curve[1:],
            strict=True,
        ):
            if min(
                previous.equity,
                current.equity,
                benchmark_previous.equity,
                benchmark_current.equity,
            ) <= 0:
                paired_daily_log_excess = []
                break
            candidate_return = math.log(current.equity / previous.equity)
            benchmark_return = math.log(
                benchmark_current.equity / benchmark_previous.equity
            )
            paired_daily_log_excess.append(candidate_return - benchmark_return)
        report.strict_hold_log_excess_ci_95 = stats.moving_block_bootstrap_ci(
            paired_daily_log_excess,
            block_length=config.bootstrap_block_days,
            n_resamples=config.bootstrap_resamples,
            seed=config.bootstrap_seed,
        )


def _one_equity_point_per_day(
    points: list[EquityPoint],
) -> list[EquityPoint]:
    last_by_day: dict[date, EquityPoint] = {}
    for point in points:
        last_by_day[point.date] = point
    return [last_by_day[day] for day in sorted(last_by_day)]


def _promotion_ready(
    reports: list[StrategyReport],
    benchmark: StrategyReport | None,
    *,
    modeled_cost: bool,
) -> bool | None:
    """Require the numerical strategy gates before external validation.

    Provenance, point-in-time universe, provider, and external cost gates are
    evaluated separately by ``external_validation``. Passing this numerical
    gate alone is not authorization to trade or a guarantee of future alpha.
    """
    if benchmark is None:
        return None
    pipeline = next((r for r in reports if r.strategy == "overall"), None)
    if pipeline is None or pipeline.beats_benchmark is not True:
        return False
    return bool(
        modeled_cost
        and pipeline.effective_n is not None
        and pipeline.effective_n >= _MIN_PROMOTION_EFFECTIVE_N
        and pipeline.deflated_sharpe is not None
        and pipeline.deflated_sharpe >= _MIN_PROMOTION_DSR
        and pipeline.strict_hold_log_excess_ci_95 is not None
        and pipeline.strict_hold_log_excess_ci_95[0] > 0
        and pipeline.twice_cost_excess_pct is not None
        and pipeline.twice_cost_excess_pct > 0
        and pipeline.max_drawdown_pct is not None
        and benchmark.max_drawdown_pct is not None
        and pipeline.max_drawdown_pct >= benchmark.max_drawdown_pct - 0.05
    )


def _sharpe(values: list[float]) -> float | None:
    """Per-trade Sharpe. Not annualised — holding periods vary by run."""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return None
    mean = sum(clean) / len(clean)
    var = sum((v - mean) ** 2 for v in clean) / (len(clean) - 1)
    if var <= 0:
        return None
    return mean / math.sqrt(var)


def _simulate_one(
    result: BacktestResult,
    config: PortfolioConfig,
    strategy: str,
) -> StrategyReport:
    completed = [t for t in result.trials if t.realized_return is not None and t.exit_date is not None]

    if strategy == "buy_and_hold":
        return _buy_and_hold(completed, config, result.price_paths)
    if strategy == "rolling_long":
        return _rolling_long(completed, config, result.price_paths)

    # Event queue. New-session Open entries happen before same-day Close exits,
    # so the simulator must not recycle capital from that later close early.
    cash = config.starting_balance
    equity_curve: list[EquityPoint] = []
    trades: list[TradeLog] = []
    entries: list[tuple[date, BacktestTrial, int]] = []  # (entry_date, trial, direction)

    for trial in completed:
        direction = _direction_for(trial, strategy, config.allow_short)
        if direction == 0:
            continue
        entries.append((trial.entry_date or trial.as_of_date, trial, direction))

    # Process entries chronologically, scheduling exits.
    entries.sort(key=lambda e: (e[0], e[1].ticker, e[1].as_of_date))
    pending_exits: dict[date, list[_OpenPosition]] = defaultdict(list)

    round_trip = _round_trip_cost(config)

    def flush_exits(d: date, *, inclusive: bool) -> None:
        nonlocal cash
        due_dates = (
            sorted(k for k in pending_exits if k <= d)
            if inclusive
            else sorted(k for k in pending_exits if k < d)
        )
        for ed in due_dates:
            for pos in pending_exits.pop(ed):
                net_return = pos.direction * pos.realized_return - round_trip
                pnl = pos.stake * net_return
                cash += pos.stake + pnl
                trades.append(
                    TradeLog(
                        ticker=pos.ticker,
                        entry_date=pos.entry_date,
                        exit_date=ed,
                        direction=pos.direction,
                        stake=pos.stake,
                        pnl=pnl,
                        return_pct=net_return,
                        entry_price=pos.entry_price,
                        exit_price=pos.exit_price,
                    )
                )
                equity_curve.append(EquityPoint(date=ed, equity=_equity(cash, pending_exits)))

    def flush_exits_before(d: date) -> None:
        flush_exits(d, inclusive=False)

    def flush_exits_up_to(d: date) -> None:
        flush_exits(d, inclusive=True)

    entries_by_date: dict[date, list[tuple[BacktestTrial, int]]] = defaultdict(list)
    for entry_date, trial, direction in entries:
        entries_by_date[entry_date].append((trial, direction))

    for entry_date, day_entries in sorted(entries_by_date.items()):
        flush_exits_before(entry_date)
        # All next-session-open orders use the same pre-open cash. Otherwise
        # ticker/input order silently changes position sizes and P&L.
        stake = min(cash * config.position_size_pct, cash / len(day_entries))
        if stake <= 0:
            continue
        for trial, direction in day_entries:
            cash -= stake
            pending_exits[trial.exit_date].append(
                _OpenPosition(
                    ticker=trial.ticker,
                    entry_date=trial.entry_date or trial.as_of_date,
                    direction=direction,
                    stake=stake,
                    realized_return=trial.realized_return,
                    entry_price=trial.entry_price,
                    exit_price=trial.exit_price,
                )
            )
            equity_curve.append(EquityPoint(date=entry_date, equity=_equity(cash, pending_exits)))

    # Close any remaining positions
    if pending_exits:
        final_date = max(pending_exits.keys())
        flush_exits_up_to(final_date)

    marked_curve, complete = _daily_mark_for_result(result, trades, config)
    return _build_report(
        strategy,
        config,
        cash,
        marked_curve if complete else equity_curve,
        trades,
        drawdown_basis=("daily_close_mark_to_market" if complete else "event_only_incomplete"),
        drawdown_complete=complete,
    )


def _buy_and_hold(
    trials: list[BacktestTrial],
    config: PortfolioConfig,
    price_paths: Mapping[str, list[PriceBar]],
) -> StrategyReport:
    """Hold each ticker from its first available entry to its last exit.

    This is the strict equal-weight long-hold comparison available from the
    trial endpoints: one position per ticker, entered once and exited once.
    It is intentionally independent of ``position_size_pct`` and of signals.
    """
    by_ticker: dict[str, list[BacktestTrial]] = defaultdict(list)
    for trial in trials:
        if (
            trial.entry_price is None
            or trial.exit_price is None
            or not math.isfinite(trial.entry_price)
            or not math.isfinite(trial.exit_price)
            or trial.entry_price <= 0
            or trial.exit_price <= 0
        ):
            continue
        by_ticker[trial.ticker].append(trial)

    if not by_ticker:
        return _build_report("buy_and_hold", config, config.starting_balance, [], [])

    round_trip = _round_trip_cost(config)
    stake = config.starting_balance / len(by_ticker)
    trades: list[TradeLog] = []

    for ticker, ticker_trials in sorted(by_ticker.items()):
        first = min(ticker_trials, key=lambda t: t.as_of_date)
        last = max(ticker_trials, key=lambda t: t.exit_date)
        gross_return = last.exit_price / first.entry_price - 1.0
        net_return = gross_return - round_trip
        entry_date = first.entry_date or first.as_of_date
        trades.append(
            TradeLog(
                ticker=ticker,
                entry_date=entry_date,
                exit_date=last.exit_date,
                direction=1,
                stake=stake,
                pnl=stake * net_return,
                return_pct=net_return,
                entry_price=first.entry_price,
                exit_price=last.exit_price,
            )
        )

    equity = config.starting_balance
    equity_curve = [
        EquityPoint(
            date=min(trade.entry_date for trade in trades),
            equity=equity,
        )
    ]
    for trade in sorted(trades, key=lambda t: (t.exit_date, t.ticker)):
        equity += trade.pnl
        equity_curve.append(EquityPoint(date=trade.exit_date, equity=equity))

    marked_curve, complete = _daily_mark_for_trades(
        trades, trials, price_paths, config
    )
    return _build_report(
        "buy_and_hold",
        config,
        equity,
        marked_curve if complete else equity_curve,
        trades,
        drawdown_basis=("daily_close_mark_to_market" if complete else "event_only_incomplete"),
        drawdown_complete=complete,
    )


def _rolling_long(
    trials: list[BacktestTrial],
    config: PortfolioConfig,
    price_paths: Mapping[str, list[PriceBar]],
) -> StrategyReport:
    """Take every trial as a rolling long at ``position_size_pct``.

    This is retained as a diagnostic baseline for compatibility with prior
    reports. It is not the strict long-hold benchmark used for promotion.
    """
    # Route the all-trials diagnostic through the same session cash snapshot,
    # equal capped sizing and Open-before-Close event queue as strategy trades.
    # The strict one-position-per-ticker buy-and-hold path remains separate.
    result = BacktestResult(
        trials=[trial.model_copy(update={"overall_signal": Signal.BUY}) for trial in trials],
        settings={},
        started_at=min((trial.as_of_date for trial in trials), default=date.min),
        finished_at=max((trial.exit_date or trial.as_of_date for trial in trials), default=date.min),
        price_paths=dict(price_paths),
    )
    return _simulate_one(result, config, "overall").model_copy(update={"strategy": "rolling_long"})


def _direction_for(trial: BacktestTrial, strategy: str, allow_short: bool) -> int:
    if strategy == "signal_timing_long":
        return int(trial.overall_signal.value != "neutral")
    if strategy == "overall":
        sig = trial.overall_signal.value
    elif strategy == "overall_fundamentals_confirmed":
        overall_direction = SIGNAL_TO_POSITION.get(trial.overall_signal.value, 0)
        fundamentals_direction = SIGNAL_TO_POSITION.get(
            trial.agent_signals.get("fundamentals", "neutral"), 0
        )
        if overall_direction == 0 or overall_direction != fundamentals_direction:
            return 0
        sig = trial.overall_signal.value
    else:
        sig = trial.agent_signals.get(strategy)
        if sig is None:
            return 0
    direction = SIGNAL_TO_POSITION.get(sig, 0)
    if direction == -1 and not allow_short:
        return 0
    return direction


def _equity(cash: float, pending_exits: dict[date, list[_OpenPosition]]) -> float:
    """Book equity = cash + sum of committed stakes (entry value).
    Unrealized P&L is not marked-to-market between events.
    """
    locked = sum(pos.stake for positions in pending_exits.values() for pos in positions)
    return cash + locked


def _daily_mark_for_result(
    result: BacktestResult,
    trades: list[TradeLog],
    config: PortfolioConfig,
) -> tuple[list[EquityPoint], bool]:
    return _daily_mark_for_trades(trades, result.trials, result.price_paths, config)


def _daily_mark_for_trades(
    trades: list[TradeLog],
    trials: list[BacktestTrial],
    price_paths: Mapping[str, list[PriceBar]],
    config: PortfolioConfig,
) -> tuple[list[EquityPoint], bool]:
    completed = [
        trial
        for trial in trials
        if trial.realized_return is not None and trial.exit_date is not None
    ]
    if not completed:
        return [], False
    start_date = min(trial.entry_date or trial.as_of_date for trial in completed)
    end_date = max(trial.exit_date for trial in completed)
    return _daily_mark_curve(
        trades,
        price_paths,
        config,
        start_date=start_date,
        end_date=end_date,
    )


def _daily_mark_curve(
    trades: list[TradeLog],
    price_paths: Mapping[str, list[PriceBar]],
    config: PortfolioConfig,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[list[EquityPoint], bool]:
    """Rebuild daily close equity from the same price paths used by scoring.

    Returns ``complete=False`` when an old result or a missing path cannot
    support daily marks. Callers must then report drawdown as unavailable,
    rather than treating event-only observations as a complete equity curve.
    """
    if not price_paths:
        return [], False
    if not trades and (start_date is None or end_date is None):
        return [], False

    by_ticker: dict[str, tuple[list[date], list[float]]] = {}
    for ticker, bars in price_paths.items():
        ordered = sorted(bars, key=lambda bar: bar.date)
        by_ticker[ticker.upper()] = (
            [bar.date for bar in ordered],
            [float(bar.close) for bar in ordered],
        )

    for trade in trades:
        series = by_ticker.get(trade.ticker.upper())
        if (
            series is None
            or trade.entry_price is None
            or trade.entry_price <= 0
            or trade.entry_date not in series[0]
            or trade.exit_date not in series[0]
        ):
            return [], False

    first_date = start_date or min(trade.entry_date for trade in trades)
    last_date = end_date or max(trade.exit_date for trade in trades)
    market_dates = sorted(
        {
            day
            for dates, _ in by_ticker.values()
            for day in dates
            if first_date <= day <= last_date
        }
        | {trade.entry_date for trade in trades}
        | {trade.exit_date for trade in trades}
    )
    entries: dict[date, list[TradeLog]] = defaultdict(list)
    exits: dict[date, list[TradeLog]] = defaultdict(list)
    for trade in trades:
        entries[trade.entry_date].append(trade)
        exits[trade.exit_date].append(trade)

    cash = config.starting_balance
    active: list[TradeLog] = []
    equity_curve = [EquityPoint(date=first_date, equity=cash)]
    cost_rate = config.cost_bps_per_side / 10_000.0

    def marked_value(trade: TradeLog, day: date) -> float | None:
        dates, closes = by_ticker[trade.ticker.upper()]
        index = bisect_right(dates, day) - 1
        if index < 0 or trade.entry_price is None:
            return None
        current_price = closes[index]
        return trade.stake * (
            1.0 + trade.direction * (current_price / trade.entry_price - 1.0)
        )

    def open_equity(day: date) -> float | None:
        value = cash
        for trade in active:
            mark = marked_value(trade, day)
            if mark is None:
                return None
            # The entry-side fee is incurred when the position opens. The
            # exit-side fee is charged when the trade is settled below.
            value += mark - trade.stake * cost_rate
        return value

    for day in market_dates:
        before_settlement = open_equity(day)
        if before_settlement is None:
            return [], False
        equity_curve.append(EquityPoint(date=day, equity=before_settlement))

        for trade in entries.get(day, []):
            if trade.stake > cash + 1e-9:
                return [], False
            cash -= trade.stake
            active.append(trade)

        # Entries use the session Open; same-date exits settle at the Close.
        # Do not fund an Open order with proceeds unavailable until later.
        for trade in exits.get(day, []):
            if trade not in active:
                return [], False
            cash += trade.stake + trade.pnl
            active.remove(trade)

        after_settlement = open_equity(day)
        if after_settlement is None:
            return [], False
        equity_curve.append(EquityPoint(date=day, equity=after_settlement))

    if active:
        return [], False
    return equity_curve, True


def _build_report(
    strategy: str,
    config: PortfolioConfig,
    final_cash: float,
    equity_curve: list[EquityPoint],
    trades: list[TradeLog],
    *,
    drawdown_basis: str = "event_only_incomplete",
    drawdown_complete: bool = False,
) -> StrategyReport:
    final_balance = equity_curve[-1].equity if equity_curve else final_cash
    total_return = (final_balance - config.starting_balance) / config.starting_balance

    # Max drawdown on the realized equity curve
    max_dd: float | None = None
    if drawdown_complete:
        peak = config.starting_balance
        max_dd = 0.0
        for pt in equity_curve:
            peak = max(peak, pt.equity)
            dd = (pt.equity - peak) / peak if peak else 0.0
            max_dd = min(max_dd, dd)

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    win_rate = len(wins) / len(trades) if trades else None
    best = max((t.return_pct for t in trades), default=None)
    worst = min((t.return_pct for t in trades), default=None)

    return StrategyReport(
        strategy=strategy,
        starting_balance=config.starting_balance,
        final_balance=final_balance,
        total_return_pct=total_return,
        max_drawdown_pct=max_dd,
        n_trades=len(trades),
        n_wins=len(wins),
        n_losses=len(losses),
        win_rate=win_rate,
        best_trade_pct=best,
        worst_trade_pct=worst,
        equity_curve=equity_curve,
        trades=trades,
        drawdown_basis=drawdown_basis,
    )


# ----------------------------------------------------------------------
def to_markdown(report: PortfolioReport) -> str:
    c = report.config
    cost_line = (
        f"- Transaction cost: {c.cost_bps_per_side:.1f} bps/side "
        f"({c.cost_bps_per_side * 2:.1f} bps round trip)"
        if c.cost_bps_per_side
        else "- Transaction cost: **none modelled** — returns are gross"
    )
    table_header = (
        [
            "| Strategy | Final balance | Return | vs strict hold | vs matched passive | Max DD | Trades | n_eff | Win rate | Sharpe | PSR |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        if report.benchmark_strategy is not None
        else [
            "| Strategy | Final balance | Return | Max DD | Trades | n_eff | Win rate | Sharpe | PSR |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines = [
        "## Portfolio simulation",
        "",
        f"- Starting balance: ${c.starting_balance:,.2f}",
        f"- Position size: {c.position_size_pct * 100:.1f}% of pre-session cash per trade; same-day orders share one cash snapshot and are capped at 100% in aggregate",
        f"- Shorts enabled: {c.allow_short}",
        cost_line,
        "- Drawdown: daily close mark-to-market when shared daily prices cover every trade; otherwise `n/a` (event-only marks are incomplete).",
        "- Matched passive: equal-weight all run-universe names on each candidate's exact active dates and dollar stakes; this conditions on signal timing and diagnoses selection/exposure only.",
        "- `overall_fundamentals_confirmed` is a research-only alternative: it takes an overall directional signal only when the fundamentals analyst agrees. It is counted in the strategy-search denominator and is not the primary promotion candidate.",
        "",
        *table_header,
    ]
    for s in report.strategies:
        marker = " 🏆" if s.strategy == report.best_strategy else ""
        if report.benchmark_strategy is not None:
            lines.append(
                f"| {s.strategy}{marker} "
                f"| ${s.final_balance:,.2f} "
                f"| {_fmt_pct(s.total_return_pct)} "
                f"| {_fmt_pct(s.excess_return_pct)} "
                f"| {_fmt_pct(s.matched_exposure_excess_pct)} "
                f"| {_fmt_pct(s.max_drawdown_pct)} "
                f"| {s.n_trades} "
                f"| {_fmt_n(s.effective_n)} "
                f"| {_fmt_pct(s.win_rate)} "
                f"| {_fmt_float(s.trade_sharpe)} "
                f"| {_fmt_pct(s.probabilistic_sharpe)} |"
            )
        else:
            lines.append(
                f"| {s.strategy}{marker} "
                f"| ${s.final_balance:,.2f} "
                f"| {_fmt_pct(s.total_return_pct)} "
                f"| {_fmt_pct(s.max_drawdown_pct)} "
                f"| {s.n_trades} "
                f"| {_fmt_n(s.effective_n)} "
                f"| {_fmt_pct(s.win_rate)} "
                f"| {_fmt_float(s.trade_sharpe)} "
                f"| {_fmt_pct(s.probabilistic_sharpe)} |"
            )

    lines += [
        "",
        "### Capital utilization",
        "",
        "- Mean and peak use the sum of original trade stakes divided by starting balance, over the same price-path sessions for every strategy. Entry and exit sessions count as invested. This is a cash-deployment diagnostic, not mark-to-market exposure or beta.",
        "",
        "| Strategy | Mean committed stake | Peak committed stake | Sessions with positions |",
        "| --- | ---: | ---: | ---: |",
    ]
    for strategy in report.strategies:
        active = strategy.capital_utilization_active_sessions
        observed = strategy.capital_utilization_market_sessions
        if active is None or observed is None or observed == 0:
            active_summary = "n/a"
        else:
            active_summary = (
                f"{active}/{observed} "
                f"({_fmt_pct(active / observed)})"
            )
        lines.append(
            f"| {strategy.strategy} "
            f"| {_fmt_pct(strategy.mean_committed_principal_pct)} "
            f"| {_fmt_pct(strategy.peak_committed_principal_pct)} "
            f"| {active_summary} |"
        )

    lines += ["", "### Cash-yield diagnostic", ""]
    if report.cash_proxy_return_pct is None:
        lines.append(
            f"- Unavailable: {report.cash_proxy_unavailable_reason or 'no complete dated cash-rate series.'}"
        )
    else:
        hash_note = (
            f"; replay SHA-256 `{report.cash_proxy_replay_sha256}`"
            if report.cash_proxy_replay_sha256
            else ""
        )
        lines += [
            f"- Source: `{report.cash_proxy_source or 'unknown'}`{hash_note}.",
            f"- Basis: {report.cash_proxy_basis or 'dated cash-rate replay'}.",
            f"- 100% cash-proxy return over the scored window: {_fmt_pct(report.cash_proxy_return_pct)}.",
            "- DFF is a federal-funds reference proxy, not a brokerage sweep or deposit yield. This diagnostic does not change the primary strategy returns or promotion gate.",
            "",
            "| Strategy | DFF-adjusted return | DFF uplift | vs 100% cash proxy | vs strict hold | Matched passive with DFF | Excess vs matched passive |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for strategy in report.strategies:
            lines.append(
                f"| {strategy.strategy} "
                f"| {_fmt_pct(strategy.cash_yield_adjusted_return_pct)} "
                f"| {_fmt_pct(strategy.cash_yield_uplift_pct)} "
                f"| {_fmt_pct(strategy.cash_yield_adjusted_excess_vs_cash_pct)} "
                f"| {_fmt_pct(strategy.cash_yield_adjusted_excess_vs_strict_hold_pct)} "
                f"| {_fmt_pct(strategy.cash_adjusted_matched_exposure_return_pct)} "
                f"| {_fmt_pct(strategy.cash_adjusted_matched_exposure_excess_pct)} |"
            )

    if report.benchmark_strategy is not None:
        lines += [
            "",
            "### Benchmark gate",
            "",
            (
                f"- Observed benchmark: `{report.benchmark_strategy}`; "
                f"return leader: `{report.best_return_strategy or 'n/a'}`."
            ),
            (
                f"- Promotion gate: **{'PASS' if report.promotion_ready else 'FAIL'}** "
                f"(the `overall` pipeline must beat strict hold after costs, have effective "
                f"n ≥ {_MIN_PROMOTION_EFFECTIVE_N:.0f}, DSR ≥ {_MIN_PROMOTION_DSR:.0%}, "
                "positive lower 95% paired block-bootstrap bound, positive excess at 2× costs, "
                "and max drawdown within 5 percentage points of strict hold)."
            ),
            "- This is the numerical backtest gate only; point-in-time universe, provider, evidence, and external cost-calibration gates are checked separately.",
        ]

    lines += _selection_bias_lines(report)
    return "\n".join(lines) + "\n"


def _selection_bias_lines(report: PortfolioReport) -> list[str]:
    """Spell out the multiple-testing problem the table above creates."""
    if report.n_strategies_tested < 2 or report.best_strategy is None:
        return []

    winner = next(
        (s for s in report.strategies if s.strategy == report.best_strategy), None
    )
    if winner is None:
        return []

    lines = [
        "",
        "### Selection bias",
        "",
        (
            f"`{winner.strategy}` posted the best per-trade Sharpe "
            f"({_fmt_float(winner.trade_sharpe)}) out of "
            f"{report.n_strategies_tested} strategies scored on the same trials. "
            "That comparison is itself a search, so its Sharpe is an order "
            "statistic rather than an unbiased estimate."
        ),
    ]

    if winner.deflated_sharpe is None:
        lines.append(
            "- Deflated Sharpe unavailable — too few independent trades to estimate it."
        )
        return lines

    dsr = winner.deflated_sharpe
    lines.append(
        f"- **Deflated Sharpe: {_fmt_pct(dsr)}** — probability the winner's edge "
        f"survives having been picked as the best of {report.n_strategies_tested}."
    )
    if dsr < 0.95:
        lines.append(
            "- ⚠ Below the 95% convention. This result is consistent with having "
            "searched several strategies and reported the luckiest; it is not "
            "evidence that this strategy works."
        )
    else:
        lines.append(
            "- Clears the 95% convention on this sample. Note that the strategies "
            "compared here are not independent — they score the same trials — so "
            "treat this as the optimistic end of the range."
        )
    return lines


def _fmt_n(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.1f}"


def _fmt_float(v: float | None) -> str:
    return "n/a" if v is None else f"{v:+.3f}"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:+.2f}%"
