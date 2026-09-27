"""Point-in-time cross-sectional momentum research.

At each month-end the rule ranks a fixed universe by its trailing return,
allocates equal weight to the top ``N`` tickers, and holds those weights until
the next month-end. The signal uses only prices available at the rebalance
close; the return is realised over the following month.

This is a deterministic portfolio-construction experiment, not an AI signal
and not a live-trading recommendation. It exists separately from the
per-trial AI scorer so a price-only allocation layer cannot be mistaken for
evidence that the analyst agents forecast returns.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel, Field

from . import stats
from .factor import clean_price_history

if TYPE_CHECKING:
    from .runner import BacktestTrial

CROSS_SECTIONAL_FACTOR_NAME = "long-only cross-sectional momentum"
CROSS_SECTIONAL_TRIAL_FACTOR_NAME = (
    "long-only cross-sectional momentum on sealed trials"
)


class OverlappingSealedWindowsError(ValueError):
    """The sealed trial episodes cannot be scored as independent windows."""


class CrossSectionalConfig(BaseModel):
    """Fixed parameters for the monthly ranking rule."""

    lookback_months: int = Field(default=12, gt=0)
    top_n: int = Field(default=3, gt=0)
    cost_bps_per_side: float = Field(default=10.0, ge=0.0, lt=10_000.0)
    bootstrap_block_periods: int = Field(default=3, gt=0)
    bootstrap_resamples: int = Field(default=2_000, gt=0)
    bootstrap_seed: int = 0


class CrossSectionalPeriod(BaseModel):
    """One rebalance-to-rebalance observation."""

    as_of_date: date
    exit_date: date
    selected_tickers: list[str]
    turnover: float
    gross_return: float
    allocation_cost: float
    net_return: float
    entry_date: date | None = None
    matched_passive_gross_return: float | None = None
    matched_passive_net_return: float | None = None
    matched_passive_turnover: float | None = None
    strict_hold_net_return: float | None = None


class CrossSectionalReport(BaseModel):
    """Serializable result of one fixed-universe experiment."""

    factor: str = CROSS_SECTIONAL_FACTOR_NAME
    hypothesis: str
    universe: list[str]
    config: CrossSectionalConfig
    data_start: date
    data_end: date
    signal_date_cutoff: date | None = None
    oos_start: date
    oos_end: date
    periods: int
    effective_n: float | None
    effective_n_basis: str = stats.PORTFOLIO_EFFECTIVE_N_BASIS
    gross_compound_return: float
    net_compound_return: float
    buy_and_hold_return: float
    excess_return: float
    net_mean_period_return: float | None
    max_drawdown: float
    annualized_sharpe: float | None
    net_p_value: float | None
    final_liquidation_cost: float
    period_log: list[CrossSectionalPeriod]
    matched_passive_return: float | None = None
    matched_passive_excess_return: float | None = None
    strict_hold_log_excess_ci_95: tuple[float, float] | None = None
    matched_passive_log_excess_ci_95: tuple[float, float] | None = None
    buy_and_hold_max_drawdown: float | None = None
    matched_passive_max_drawdown: float | None = None
    # Legacy artifacts had only period-end drawdown and close-based fills.
    drawdown_basis: str = "rebalance_period_end"
    price_basis: str = "close"


class CrossSectionalTrialReport(BaseModel):
    """Result of applying the fixed allocator to sealed trial outcomes."""

    factor: str = CROSS_SECTIONAL_TRIAL_FACTOR_NAME
    hypothesis: str
    universe: list[str]
    config: CrossSectionalConfig
    data_start: date
    data_end: date
    oos_start: date
    oos_end: date
    periods: int
    effective_n: float | None
    effective_n_basis: str = stats.PORTFOLIO_EFFECTIVE_N_BASIS
    completed_trials: int
    average_holding_days: float
    gross_compound_return: float
    net_compound_return: float
    buy_and_hold_return: float
    excess_return: float
    net_mean_period_return: float | None
    max_drawdown: float
    annualized_sharpe: float | None
    net_p_value: float | None
    final_liquidation_cost: float
    period_log: list[CrossSectionalPeriod]
    matched_passive_return: float | None = None
    matched_passive_excess_return: float | None = None
    matched_passive_log_excess_ci_95: tuple[float, float] | None = None
    drawdown_basis: str = "sealed_period_endpoints"
    price_basis: str = "sealed_trial_realized_return"


def run_cross_sectional_backtest(
    price_histories: Mapping[str, pd.DataFrame],
    *,
    start: date | None = None,
    end: date | None = None,
    config: CrossSectionalConfig | None = None,
) -> CrossSectionalReport:
    """Run a fixed monthly ranking rule without using future prices.

    Signals use each month's last common close. Orders fill at the next
    common-session open, and the position exits/rebalances at the next
    month's next-session open. ``start``/``end`` filter signal dates; the last
    holding period therefore needs price data beyond ``end``.
    """

    config = config or CrossSectionalConfig()
    if len(price_histories) < config.top_n:
        raise ValueError("price_histories must contain at least top_n tickers")
    if start is not None and end is not None and start >= end:
        raise ValueError("start must be before end")

    opens, closes, monthly_closes, entry_dates = _monthly_execution_panels(
        price_histories
    )
    if len(monthly_closes) <= config.lookback_months + 1:
        raise ValueError(
            "Need more monthly observations than the configured lookback and "
            "one forward holding period"
        )

    first_date = pd.Timestamp(start) if start is not None else monthly_closes.index[0]
    last_date = pd.Timestamp(end) if end is not None else closes.index[-1]
    if first_date >= last_date:
        raise ValueError("start must be before end")

    periods: list[CrossSectionalPeriod] = []
    candidate_targets: dict[date, pd.Series] = {}
    passive_targets: dict[date, pd.Series] = {}
    ending_candidate_weights: pd.Series | None = None
    ending_passive_weights: pd.Series | None = None
    strict_weights = pd.Series(1.0 / len(monthly_closes.columns), index=monthly_closes.columns)
    cost_rate = config.cost_bps_per_side / 10_000.0

    for index in range(config.lookback_months, len(monthly_closes) - 1):
        as_of = monthly_closes.index[index]
        next_as_of = monthly_closes.index[index + 1]
        if as_of < first_date:
            continue
        if as_of > last_date:
            break
        if (next_as_of.to_period("M") - as_of.to_period("M")).n != 1:
            raise ValueError("Monthly signal history has a missing calendar month")

        entry_date = entry_dates.get(as_of)
        exit_date = entry_dates.get(next_as_of)
        if entry_date is None or exit_date is None:
            continue
        momentum = (
            monthly_closes.iloc[index]
            / monthly_closes.iloc[index - config.lookback_months]
            - 1.0
        )
        selected = list(momentum.sort_values(ascending=False).head(config.top_n).index)
        if len(selected) != config.top_n:
            raise ValueError("Not enough complete tickers for the configured top_n")

        weights = pd.Series(0.0, index=monthly_closes.columns)
        weights.loc[selected] = 1.0 / config.top_n
        asset_returns = (
            opens.loc[pd.Timestamp(exit_date)] / opens.loc[pd.Timestamp(entry_date)] - 1.0
        )
        gross_return = float((weights * asset_returns).sum())
        passive_weights = pd.Series(1.0 / len(weights), index=weights.index)
        passive_gross = float((passive_weights * asset_returns).sum())

        candidate_turnover = _rebalance_turnover(ending_candidate_weights, weights)
        passive_turnover = _rebalance_turnover(ending_passive_weights, passive_weights)
        candidate_cost = candidate_turnover * cost_rate
        passive_cost = passive_turnover * cost_rate
        candidate_net = (1.0 + gross_return) * (1.0 - candidate_cost) - 1.0
        passive_net = (1.0 + passive_gross) * (1.0 - passive_cost) - 1.0

        drifted_candidate = weights * (1.0 + asset_returns)
        if float(drifted_candidate.sum()) > 0:
            ending_candidate_weights = drifted_candidate / float(drifted_candidate.sum())
        drifted_passive = passive_weights * (1.0 + asset_returns)
        if float(drifted_passive.sum()) > 0:
            ending_passive_weights = drifted_passive / float(drifted_passive.sum())

        strict_gross = float((strict_weights * asset_returns).sum())
        strict_weights = strict_weights * (1.0 + asset_returns)
        strict_weights /= float(strict_weights.sum())
        periods.append(
            CrossSectionalPeriod(
                as_of_date=as_of.date(),
                entry_date=entry_date,
                exit_date=exit_date,
                selected_tickers=selected,
                turnover=candidate_turnover,
                gross_return=gross_return,
                allocation_cost=candidate_cost,
                net_return=candidate_net,
                matched_passive_gross_return=passive_gross,
                matched_passive_net_return=passive_net,
                matched_passive_turnover=passive_turnover,
                strict_hold_net_return=strict_gross,
            )
        )
        candidate_targets[entry_date] = weights
        passive_targets[entry_date] = passive_weights

    if not periods:
        raise ValueError("No complete monthly out-of-sample period was formed")

    final_liquidation_cost = cost_rate
    periods[-1].net_return = (
        (1.0 + periods[-1].net_return) * (1.0 - final_liquidation_cost) - 1.0
    )
    periods[-1].matched_passive_net_return = (
        (1.0 + float(periods[-1].matched_passive_net_return))
        * (1.0 - final_liquidation_cost)
        - 1.0
    )
    periods[0].strict_hold_net_return = (
        (1.0 + float(periods[0].strict_hold_net_return)) * (1.0 - cost_rate) - 1.0
    )
    periods[-1].strict_hold_net_return = (
        (1.0 + float(periods[-1].strict_hold_net_return))
        * (1.0 - final_liquidation_cost)
        - 1.0
    )

    final_exit = periods[-1].exit_date
    candidate_targets[final_exit] = pd.Series(0.0, index=monthly_closes.columns)
    passive_targets[final_exit] = pd.Series(0.0, index=monthly_closes.columns)
    strict_targets = {
        periods[0].entry_date: pd.Series(
            1.0 / len(monthly_closes.columns), index=monthly_closes.columns
        ),
        final_exit: pd.Series(0.0, index=monthly_closes.columns),
    }
    candidate_curve = _daily_equity_curve(
        opens, closes, candidate_targets, cost_rate
    )
    passive_curve = _daily_equity_curve(opens, closes, passive_targets, cost_rate)
    strict_curve = _daily_equity_curve(opens, closes, strict_targets, cost_rate)

    candidate_net_returns = [period.net_return for period in periods]
    passive_net_returns = [float(period.matched_passive_net_return) for period in periods]
    strict_net_returns = [float(period.strict_hold_net_return) for period in periods]
    final_equity = _compound(candidate_net_returns)
    matched_passive = _compound(passive_net_returns)
    buy_and_hold = _compound(strict_net_returns)
    strict_excess = [
        math.log1p(candidate) - math.log1p(benchmark)
        for candidate, benchmark in zip(
            candidate_net_returns, strict_net_returns, strict=True
        )
    ]
    passive_excess = [
        math.log1p(candidate) - math.log1p(benchmark)
        for candidate, benchmark in zip(
            candidate_net_returns, passive_net_returns, strict=True
        )
    ]
    net_returns = [period.net_return for period in periods]
    equity_curve = [1.0]
    for value in net_returns:
        equity_curve.append(equity_curve[-1] * (1.0 + value))
    effective_n = _effective_period_n(periods)

    return CrossSectionalReport(
        hypothesis=(
            f"At each month-end, the top {config.top_n} of a fixed universe by "
            f"{config.lookback_months}-month trailing return will outperform "
            "equal-weight buy-and-hold after costs."
        ),
        universe=list(monthly_closes.columns),
        config=config,
        data_start=closes.index[0].date(),
        data_end=periods[-1].exit_date,
        signal_date_cutoff=last_date.date(),
        oos_start=periods[0].as_of_date,
        oos_end=periods[-1].exit_date,
        periods=len(periods),
        effective_n=effective_n,
        gross_compound_return=_compound(period.gross_return for period in periods),
        net_compound_return=final_equity,
        buy_and_hold_return=buy_and_hold,
        excess_return=final_equity - buy_and_hold,
        net_mean_period_return=_mean(net_returns),
        max_drawdown=_max_drawdown(candidate_curve),
        annualized_sharpe=_annualized_sharpe(net_returns),
        net_p_value=stats.t_test_vs_zero(net_returns, effective_n)[1],
        final_liquidation_cost=final_liquidation_cost,
        period_log=periods,
        matched_passive_return=matched_passive,
        matched_passive_excess_return=final_equity - matched_passive,
        strict_hold_log_excess_ci_95=stats.moving_block_bootstrap_ci(
            strict_excess,
            block_length=config.bootstrap_block_periods,
            n_resamples=config.bootstrap_resamples,
            seed=config.bootstrap_seed,
        ),
        matched_passive_log_excess_ci_95=stats.moving_block_bootstrap_ci(
            passive_excess,
            block_length=config.bootstrap_block_periods,
            n_resamples=config.bootstrap_resamples,
            seed=config.bootstrap_seed,
        ),
        buy_and_hold_max_drawdown=_max_drawdown(strict_curve),
        matched_passive_max_drawdown=_max_drawdown(passive_curve),
        drawdown_basis="daily_close_mark_to_market",
        price_basis="provided_open_close_not_dividend_verified",
    )


def run_cross_sectional_trial_backtest(
    price_histories: Mapping[str, pd.DataFrame],
    trials: Iterable[BacktestTrial],
    *,
    config: CrossSectionalConfig | None = None,
) -> CrossSectionalTrialReport:
    """Apply the fixed allocator to a sealed session/backtest trial bundle.

    Ranking is point-in-time: for each trial date, only closes on or before
    that date and the configured trailing lookback are read. Forward returns
    come from the already-sealed ``BacktestTrial`` outcomes and are consulted
    only after the top-N selection has been made.

    Every ticker/date in the fixed universe must have a completed trial, and
    holding windows must be synchronized and non-overlapping. Each sealed
    window is a separate fully invested episode; cash remains idle between
    windows. The passive comparison uses the same names and exact windows.
    """

    config = config or CrossSectionalConfig()
    trial_list = list(trials)
    if not trial_list:
        raise ValueError("trials must contain at least one completed trial")

    universe = sorted({trial.ticker.upper() for trial in trial_list})
    if len(universe) < config.top_n:
        raise ValueError("trials must contain at least top_n tickers")

    normalised_histories = {
        ticker.upper(): frame for ticker, frame in price_histories.items()
    }
    histories: dict[str, pd.Series] = {}
    for ticker in universe:
        frame = normalised_histories.get(ticker)
        if frame is None:
            raise ValueError(f"Missing price history for {ticker}")
        cleaned = clean_price_history(frame)
        histories[ticker] = cleaned.set_index("date")["close"].sort_index()

    grouped: dict[date, dict[str, BacktestTrial]] = {}
    for trial in trial_list:
        ticker = trial.ticker.upper()
        if ticker not in histories:
            raise ValueError(f"Trial ticker is absent from the price universe: {ticker}")
        by_ticker = grouped.setdefault(trial.as_of_date, {})
        if ticker in by_ticker:
            raise ValueError(f"Duplicate trial: {ticker} @ {trial.as_of_date}")
        by_ticker[ticker] = trial

    for as_of, by_ticker in grouped.items():
        missing = [
            ticker
            for ticker in universe
            if ticker not in by_ticker or not _is_completed_trial(by_ticker[ticker])
        ]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Incomplete sealed trial group at {as_of}: {names}")

    windows: list[tuple[date, date, date, dict[str, BacktestTrial]]] = []
    for as_of, by_ticker in grouped.items():
        entry_dates = {
            trial.entry_date or trial.as_of_date for trial in by_ticker.values()
        }
        exit_dates = {trial.exit_date for trial in by_ticker.values()}
        if len(entry_dates) != 1 or len(exit_dates) != 1:
            raise ValueError(
                f"Sealed trial group at {as_of} does not share one entry/exit window"
            )
        entry_date = next(iter(entry_dates))
        exit_date = next(iter(exit_dates))
        if exit_date is None or entry_date >= exit_date:
            raise ValueError(f"Invalid sealed trial window at {as_of}")
        windows.append((entry_date, exit_date, as_of, by_ticker))
    windows.sort(key=lambda window: (window[0], window[1]))
    previous_exit: date | None = None
    for entry_date, exit_date, _, _ in windows:
        if previous_exit is not None and entry_date <= previous_exit:
            raise OverlappingSealedWindowsError(
                "overlapping sealed windows: trial windows must be sequential"
            )
        previous_exit = exit_date

    periods: list[CrossSectionalPeriod] = []
    cost_rate = config.cost_bps_per_side / 10_000.0

    for entry_date, exit_date, as_of, by_ticker in windows:
        lookback_date = pd.Timestamp(as_of) - pd.DateOffset(
            months=config.lookback_months
        )
        scores: dict[str, float] = {}
        for ticker in universe:
            current_close = _close_on_or_before(histories[ticker], as_of)
            prior_close = _close_on_or_before(histories[ticker], lookback_date.date())
            if current_close is not None and prior_close is not None and prior_close > 0:
                scores[ticker] = current_close / prior_close - 1.0

        if len(scores) < config.top_n:
            raise ValueError(
                f"Not enough point-in-time price histories to rank top_n at {as_of}"
            )

        selected = sorted(scores, key=lambda ticker: (-scores[ticker], ticker))[
            : config.top_n
        ]
        selected_trials = [by_ticker[ticker] for ticker in selected]
        turnover = 1.0
        allocation_cost = 1.0 - (1.0 - cost_rate) ** 2
        gross_return = sum(
            float(trial.realized_return) for trial in selected_trials
        ) / config.top_n
        net_return = (1.0 + gross_return) * (1.0 - cost_rate) ** 2 - 1.0
        passive_gross = sum(
            float(by_ticker[ticker].realized_return) for ticker in universe
        ) / len(universe)
        passive_net = (1.0 + passive_gross) * (1.0 - cost_rate) ** 2 - 1.0
        periods.append(
            CrossSectionalPeriod(
                as_of_date=as_of,
                entry_date=entry_date,
                exit_date=exit_date,
                selected_tickers=selected,
                turnover=turnover,
                gross_return=gross_return,
                allocation_cost=allocation_cost,
                net_return=net_return,
                matched_passive_gross_return=passive_gross,
                matched_passive_net_return=passive_net,
                matched_passive_turnover=turnover,
            )
        )

    final_equity = _compound(period.net_return for period in periods)
    matched_passive = _compound(
        float(period.matched_passive_net_return) for period in periods
    )
    all_completed = [
        by_ticker[ticker]
        for by_ticker in grouped.values()
        for ticker in universe
    ]
    by_ticker: dict[str, list[BacktestTrial]] = {}
    for trial in all_completed:
        by_ticker.setdefault(trial.ticker.upper(), []).append(trial)

    ticker_returns = []
    for ticker in universe:
        ticker_trials = by_ticker[ticker]
        first = min(
            ticker_trials,
            key=lambda trial: trial.entry_date or trial.as_of_date,
        )
        last = max(ticker_trials, key=lambda trial: trial.exit_date)
        gross_return = float(last.exit_price) / float(first.entry_price) - 1.0
        ticker_returns.append((1.0 + gross_return) * (1.0 - cost_rate) ** 2 - 1.0)
    buy_and_hold = sum(ticker_returns) / len(ticker_returns)

    net_returns = [period.net_return for period in periods]
    passive_returns = [float(period.matched_passive_net_return) for period in periods]
    paired_excess = [
        math.log1p(candidate) - math.log1p(passive)
        for candidate, passive in zip(net_returns, passive_returns, strict=True)
    ]
    equity_curve = [1.0]
    for value in net_returns:
        equity_curve.append(equity_curve[-1] * (1.0 + value))
    effective_n = _effective_period_n(periods)
    holding_days = [
        (trial.exit_date - (trial.entry_date or trial.as_of_date)).days
        for trial in all_completed
        if trial.exit_date is not None
    ]
    average_holding_days = sum(holding_days) / len(holding_days)
    periods_per_year = 365.0 / average_holding_days if average_holding_days > 0 else 12.0
    first_data = min(series.index[0] for series in histories.values()).date()
    last_data = max(series.index[-1] for series in histories.values()).date()

    return CrossSectionalTrialReport(
        hypothesis=(
            f"At each sealed as-of date, the top {config.top_n} of a fixed universe "
            f"by {config.lookback_months}-month trailing return will outperform "
            "an equal-weight passive portfolio on the same windows after costs."
        ),
        universe=universe,
        config=config,
        data_start=first_data,
        data_end=last_data,
        oos_start=periods[0].as_of_date,
        oos_end=max(period.exit_date for period in periods),
        periods=len(periods),
        effective_n=effective_n,
        completed_trials=len(all_completed),
        average_holding_days=average_holding_days,
        gross_compound_return=_compound(period.gross_return for period in periods),
        net_compound_return=final_equity,
        buy_and_hold_return=buy_and_hold,
        excess_return=final_equity - buy_and_hold,
        net_mean_period_return=_mean(net_returns),
        max_drawdown=_max_drawdown(equity_curve),
        annualized_sharpe=_annualized_sharpe(net_returns, periods_per_year),
        net_p_value=stats.t_test_vs_zero(net_returns, effective_n)[1],
        # Every sealed episode is closed and its exit fee is in net_return.
        final_liquidation_cost=0.0,
        period_log=periods,
        matched_passive_return=matched_passive,
        matched_passive_excess_return=final_equity - matched_passive,
        matched_passive_log_excess_ci_95=stats.moving_block_bootstrap_ci(
            paired_excess,
            block_length=config.bootstrap_block_periods,
            n_resamples=config.bootstrap_resamples,
            seed=config.bootstrap_seed,
        ),
        drawdown_basis="sealed_period_endpoints",
        price_basis="sealed_trial_realized_return",
    )


def _monthly_execution_panels(
    price_histories: Mapping[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[pd.Timestamp, date]]:
    """Build synchronized daily OHLC panels and actual month-end signal rows.

    Common dates only are retained; prices are never forward-filled. The
    latest common session in each month is the signal date and its next common
    session supplies the executable open. A month with no common session, or
    a gap in the resulting monthly sequence, is rejected rather than silently
    changing the lookback horizon.
    """

    open_series: dict[str, pd.Series] = {}
    close_series: dict[str, pd.Series] = {}
    for ticker, frame in sorted(price_histories.items()):
        cleaned = clean_price_history(frame)
        indexed = cleaned.assign(date=pd.to_datetime(cleaned["date"])).set_index("date")
        open_series[ticker.upper()] = indexed["open"].astype(float)
        close_series[ticker.upper()] = indexed["close"].astype(float)

    opens = pd.concat(open_series, axis=1).sort_index().dropna(how="any")
    closes = pd.concat(close_series, axis=1).reindex(opens.index)
    if opens.empty or closes.isna().any().any():
        raise ValueError("No common daily open/close price history across the universe")

    month_groups = pd.Series(opens.index, index=opens.index).groupby(
        opens.index.to_period("M")
    )
    signal_dates = list(month_groups.last().tolist())
    monthly_closes = closes.loc[signal_dates].copy()
    monthly_closes.index = pd.DatetimeIndex(signal_dates)
    month_keys = monthly_closes.index.to_period("M")
    expected = pd.period_range(month_keys[0], month_keys[-1], freq="M")
    if not month_keys.equals(expected):
        raise ValueError("Monthly signal history has a missing calendar month")

    entry_dates: dict[pd.Timestamp, date] = {}
    for signal_date in monthly_closes.index:
        position = opens.index.searchsorted(signal_date, side="right")
        if position < len(opens.index):
            entry_dates[signal_date] = opens.index[position].date()
    return opens, closes, monthly_closes, entry_dates


def _rebalance_turnover(
    current_weights: pd.Series | None,
    target_weights: pd.Series,
) -> float:
    """Compute one-way turnover including cash for the initial investment."""

    target_cash = max(0.0, 1.0 - float(target_weights.sum()))
    if current_weights is None:
        return float(target_weights.sum())
    current_cash = max(0.0, 1.0 - float(current_weights.sum()))
    return float(
        (
            (target_weights - current_weights).abs().sum()
            + abs(target_cash - current_cash)
        )
        / 2.0
    )


def _daily_equity_curve(
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    targets: Mapping[date, pd.Series],
    cost_rate: float,
) -> list[float]:
    """Mark a long-only portfolio to every common daily close.

    At each open, existing positions first receive the overnight gap, then
    scheduled weights are rebalanced and charged one-way turnover costs. The
    remaining positions are marked from that open to the close.
    """

    if not targets:
        return [1.0]
    first_day = min(targets)
    last_day = max(targets)
    daily = opens.loc[
        (opens.index.date >= first_day) & (opens.index.date <= last_day)
    ]
    if daily.empty:
        raise ValueError("No daily prices for the scheduled portfolio window")

    target_by_timestamp = {
        pd.Timestamp(day): weights.reindex(opens.columns, fill_value=0.0)
        for day, weights in targets.items()
    }
    weights = pd.Series(0.0, index=opens.columns)
    equity = 1.0
    curve = [equity]
    previous_close: pd.Series | None = None

    for timestamp, opening in daily.iterrows():
        closing = closes.loc[timestamp]
        if previous_close is not None:
            overnight = opening / previous_close
            overnight_factor = (1.0 - float(weights.sum())) + float(
                (weights * overnight).sum()
            )
            if not math.isfinite(overnight_factor) or overnight_factor <= 0:
                raise ValueError("Invalid overnight portfolio valuation")
            equity *= overnight_factor
            if float(weights.sum()) > 0:
                weights = weights * overnight / overnight_factor

        target = target_by_timestamp.get(timestamp)
        if target is not None:
            turnover = _rebalance_turnover(
                None if previous_close is None else weights, target
            )
            equity *= 1.0 - turnover * cost_rate
            weights = target.copy()

        intraday = closing / opening
        intraday_factor = (1.0 - float(weights.sum())) + float(
            (weights * intraday).sum()
        )
        if not math.isfinite(intraday_factor) or intraday_factor <= 0:
            raise ValueError("Invalid intraday portfolio valuation")
        equity *= intraday_factor
        if float(weights.sum()) > 0:
            weights = weights * intraday / intraday_factor
        curve.append(equity)
        previous_close = closing

    return curve


def to_markdown(report: CrossSectionalReport) -> str:
    """Render an auditable research memo."""

    c = report.config
    lines = [
        "# Cross-Sectional Momentum Research Report",
        "",
        f"> **Hypothesis:** {report.hypothesis}",
        ">",
        "> This is a deterministic portfolio-construction experiment, not an AI forecast or live-trading recommendation.",
        "",
        "## Protocol",
        "",
        f"- Universe: {', '.join(report.universe)}",
        f"- Data: {report.data_start} → {report.data_end}",
        f"- Out-of-sample: {report.oos_start} → {report.oos_end}",
        f"- Signal-date cutoff: {report.signal_date_cutoff}",
        f"- Signal: rank trailing {c.lookback_months}-month close-to-close return at the last common session of each month",
        "- Execution: next common-session open; rebalance/exit at the following signal's next-session open",
        f"- Portfolio: equal weight top {c.top_n}; matched passive rebalances equal weight across the same names and dates",
        f"- Cost: {c.cost_bps_per_side:.1f} bps per side, charged on actual one-way turnover; final liquidation included",
        "- Missing prices: no forward-fill; only synchronized common sessions are used",
        f"- Bootstrap: moving blocks of {c.bootstrap_block_periods} paired monthly periods, {c.bootstrap_resamples} resamples, seed {c.bootstrap_seed}",
        f"- Price basis: {report.price_basis}; dividend/total-return treatment must be verified before interpreting CAGR",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Periods | {report.periods} |",
        f"| Effective period sample size | {_fmt_float(report.effective_n)} |",
        f"| Gross compound return | {_fmt_pct(report.gross_compound_return)} |",
        f"| Net compound return | {_fmt_pct(report.net_compound_return)} |",
        f"| Strict equal-weight buy-and-hold | {_fmt_pct(report.buy_and_hold_return)} |",
        f"| Strict hold max drawdown | {_fmt_pct(report.buy_and_hold_max_drawdown)} |",
        f"| Matched passive return | {_fmt_pct(report.matched_passive_return)} |",
        f"| Matched passive max drawdown | {_fmt_pct(report.matched_passive_max_drawdown)} |",
        f"| Excess vs. strict hold | {_fmt_pct(report.excess_return)} |",
        f"| Excess vs. matched passive | {_fmt_pct(report.matched_passive_excess_return)} |",
        f"| Paired log-excess 95% CI vs. strict hold | {_fmt_ci(report.strict_hold_log_excess_ci_95)} |",
        f"| Paired log-excess 95% CI vs. matched passive | {_fmt_ci(report.matched_passive_log_excess_ci_95)} |",
        f"| Mean net monthly return | {_fmt_pct(report.net_mean_period_return)} |",
        f"| Max drawdown (daily close marks) | {_fmt_pct(report.max_drawdown)} |",
        f"| Annualized Sharpe | {_fmt_float(report.annualized_sharpe)} |",
        f"| Net mean-return p-value | {_fmt_float(report.net_p_value)} |",
        "",
        "## Audit notes",
        "",
        "- The ranking uses only prices available at the month-end decision; orders fill at the next common-session open.",
        "- The strict benchmark uses the exact same first entry and final exit dates; matched passive uses the exact same rebalance dates and investable universe.",
        "- Confidence intervals are for paired monthly log excess; they are descriptive and do not correct for all parameter/universe searches.",
        "- The strategy is not evidence that the AI analyst layer has predictive skill; it is a separate deterministic allocation rule.",
        "- The p-value uses a temporal effective sample size; non-overlapping periods still share serial, market, and sector shocks, so treat it as descriptive.",
        "- Universe selection and parameter selection remain separate research choices and must be frozen before a final holdout.",
    ]
    return "\n".join(lines) + "\n"


def trial_allocation_to_markdown(report: CrossSectionalTrialReport) -> str:
    """Render the sealed-trial allocator result without presenting it as AI skill."""

    c = report.config
    lines = [
        "## Sealed-Trial Cross-Sectional Allocation",
        "",
        f"> **Hypothesis:** {report.hypothesis}",
        ">",
        "> This is a deterministic portfolio-construction layer applied after the session produced its sealed predictions; it is not an AI forecast result.",
        "",
        "### Protocol",
        "",
        f"- Universe: {', '.join(report.universe)}",
        f"- Price history: {report.data_start} → {report.data_end}",
        f"- Sealed trial window: {report.oos_start} → {report.oos_end}",
        f"- Signal: rank the close-to-close return over the prior {c.lookback_months} months, using only prices on or before each as-of date",
        f"- Portfolio: equal weight top {c.top_n}; use each selected ticker's sealed forward trial return after selection",
        f"- Cost: {c.cost_bps_per_side:.1f} bps/side; one full round trip per sealed window",
        "- Windows: non-overlapping, synchronized across tickers; capital is idle between windows",
        f"- Bootstrap: moving blocks of {c.bootstrap_block_periods} paired periods, {c.bootstrap_resamples} resamples, seed {c.bootstrap_seed}",
        "- Missing price/outcome data: fail closed; the fixed universe is not silently reduced",
        "",
        "### Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| As-of periods | {report.periods} |",
        f"| Effective period sample size | {_fmt_float(report.effective_n)} |",
        f"| Completed ticker trials | {report.completed_trials} |",
        f"| Average holding days | {report.average_holding_days:.1f} |",
        f"| Gross compound return | {_fmt_pct(report.gross_compound_return)} |",
        f"| Net compound return | {_fmt_pct(report.net_compound_return)} |",
        f"| Strict equal-weight buy-and-hold | {_fmt_pct(report.buy_and_hold_return)} |",
        f"| Matched passive return (same windows) | {_fmt_pct(report.matched_passive_return)} |",
        f"| Matched passive excess | {_fmt_pct(report.matched_passive_excess_return)} |",
        f"| Paired log-excess 95% CI vs. passive | {_fmt_ci(report.matched_passive_log_excess_ci_95)} |",
        f"| Strict hold excess | {_fmt_pct(report.excess_return)} |",
        f"| Mean net allocation-period return | {_fmt_pct(report.net_mean_period_return)} |",
        f"| Max drawdown (period endpoints only) | {_fmt_pct(report.max_drawdown)} |",
        f"| Annualized Sharpe | {_fmt_float(report.annualized_sharpe)} |",
        f"| Net mean-return p-value | {_fmt_float(report.net_p_value)} |",
        "",
        "### Audit notes",
        "",
        "- The historical ranking is calculated before reading any selected ticker's forward sealed outcome.",
        "- Strict hold stays invested from the first sealed entry through the last sealed exit; matched passive invests only during each sealed episode, like the allocator.",
        "- The paired interval compares allocator and passive returns on the same sealed windows; one episode is not enough to estimate an interval.",
        "- Period-end drawdown omits losses inside each sealed holding window; use the daily-price monthly backtest for marked-to-market drawdown.",
        "- This adapter does not change the AI signal score or promotion gate. Universe and parameters must be frozen before a future holdout.",
    ]
    return "\n".join(lines) + "\n"


def _is_completed_trial(trial: BacktestTrial) -> bool:
    """Return whether a sealed outcome has usable prices and return."""

    if trial.exit_date is None or trial.realized_return is None:
        return False
    values = (trial.entry_price, trial.exit_price, trial.realized_return)
    return (
        all(math.isfinite(float(value)) for value in values)
        and trial.entry_price > 0
        and trial.exit_price > 0
    )


def _close_on_or_before(series: pd.Series, target) -> float | None:
    """Return the last observed close at or before a point-in-time target."""

    eligible = series.loc[series.index <= pd.Timestamp(target)]
    if eligible.empty:
        return None
    value = float(eligible.iloc[-1])
    return value if math.isfinite(value) and value > 0 else None


def _effective_period_n(periods: list[CrossSectionalPeriod]) -> float | None:
    """Discount overlapping allocation windows without claiming independence."""

    windows = [
        (
            "portfolio",
            period.entry_date or period.as_of_date,
            max(
                period.entry_date or period.as_of_date,
                period.exit_date - timedelta(days=1),
            ),
        )
        for period in periods
    ]
    effective_n = stats.effective_sample_size(windows)
    return effective_n or None


def _compound(values) -> float:
    result = 1.0
    for value in values:
        result *= 1.0 + value
    return result - 1.0


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1.0)
    return drawdown


def _annualized_sharpe(
    values: list[float], periods_per_year: float = 12.0
) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    if variance <= 0:
        return None
    return mean / math.sqrt(variance) * math.sqrt(periods_per_year)


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def _fmt_float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _fmt_ci(value: tuple[float, float] | None) -> str:
    if value is None:
        return "n/a (insufficient paired periods)"
    return f"[{value[0]:.4f}, {value[1]:.4f}] log excess"
