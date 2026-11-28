"""Point-in-time comparison of widely used price-only equity selection rules.

Every rule sees the same universe, the same monthly decision dates, the same
next-session open fills and the same one-way cost. Signals are computed from
closes at or before the decision date only. The comparison reports every rule
that was tried (``n_strategies_tested``) and deflates the Sharpe ratio for that
search, so the best-looking line is never presented without its selection bias.

Fundamental rules join the comparison only when a point-in-time SEC fundamentals
directory is supplied; value ratios are excluded because split-adjusted price bars
cannot be divided by as-reported per-share data. AI signals have their own sealed
experiments and are not mixed in here.

This is advisory research, not a trading instruction.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field

from stock_analysis.daily_portfolio import rebalance_turnover

from . import stats
from .cross_sectional import (
    _annualized_sharpe,
    _compound,
    _daily_equity_curve,
    _max_drawdown,
    _monthly_execution_panels,
)
from .fundamental_panel import fundamental_metrics

TRADING_DAYS_SMA = 200
TRADING_DAYS_YEAR = 252
TRADING_DAYS_MONTH = 21
MIN_DAILY_HISTORY = TRADING_DAYS_YEAR + TRADING_DAYS_MONTH


class StrategyComparisonConfig(BaseModel):
    lookback_months: int = Field(default=12, gt=0)
    top_n: int = Field(default=3, gt=0)
    cost_bps_per_side: float = Field(default=20.0, ge=0.0, lt=10_000.0)
    bootstrap_block_periods: int = Field(default=3, gt=0)
    bootstrap_resamples: int = Field(default=2_000, gt=0)
    bootstrap_seed: int = 0


@dataclass(frozen=True)
class StrategySpec:
    id: str
    label: str
    family: str
    rule: str
    source: str
    signal: Callable[..., pd.Series]
    needs_fundamentals: bool = False
    stateful: bool = False  # signal also receives the names held after the last rebalance


def _equal(selected: pd.Index, columns: pd.Index, per_name: float) -> pd.Series:
    weights = pd.Series(0.0, index=columns)
    weights.loc[selected] = per_name
    return weights


def _top(score: pd.Series, n: int) -> pd.Index:
    # Ties break by ticker so a run is reproducible.
    ordered = score.dropna().sort_index().sort_values(ascending=False, kind="stable")
    return ordered.head(n).index


def _mom(monthly: pd.DataFrame, months: int, skip: int = 0) -> pd.Series:
    last = len(monthly) - 1 - skip
    return monthly.iloc[last] / monthly.iloc[last - months] - 1.0


def _sig_momentum(daily, monthly, lookback, top_n, fund=None):
    return _equal(_top(_mom(monthly, lookback), top_n), daily.columns, 1.0 / top_n)


def _sig_momentum_skip(daily, monthly, lookback, top_n, fund=None):
    return _equal(_top(_mom(monthly, lookback, skip=1), top_n), daily.columns, 1.0 / top_n)


def _sig_tsmom(daily, monthly, lookback, top_n, fund=None):
    positive = _mom(monthly, lookback)
    return _equal(positive.index[positive > 0], daily.columns, 1.0 / len(daily.columns))


def _sig_trend(daily, monthly, lookback, top_n, fund=None):
    sma = daily.iloc[-TRADING_DAYS_SMA:].mean()
    above = daily.iloc[-1] > sma
    return _equal(above.index[above], daily.columns, 1.0 / len(daily.columns))


def _sig_dual(daily, monthly, lookback, top_n, fund=None):
    score = _mom(monthly, lookback)
    chosen = [t for t in _top(score, top_n) if score[t] > 0]
    return _equal(pd.Index(chosen), daily.columns, 1.0 / top_n)


def _sig_ma_distance(daily, monthly, lookback, top_n, fund=None):
    short = daily.iloc[-TRADING_DAYS_MONTH:].mean()
    long = daily.iloc[-TRADING_DAYS_SMA:].mean()
    return _equal(_top(short / long - 1.0, top_n), daily.columns, 1.0 / top_n)


BUFFER_RANK = 5  # a held name is kept while it stays inside the top 5 (fixed in advance)


def _sig_ma_distance_buffer(daily, monthly, lookback, top_n, fund=None, held=None):
    """MA distance with a sell buffer: keep a holding until it falls out of the top
    ``BUFFER_RANK``, then fill empty slots from the top of the ranking."""
    score = daily.iloc[-TRADING_DAYS_MONTH:].mean() / daily.iloc[-TRADING_DAYS_SMA:].mean() - 1.0
    keep_zone = set(_top(score, max(BUFFER_RANK, top_n)))
    chosen = [t for t in (held or ()) if t in keep_zone]
    chosen = sorted(chosen, key=lambda t: (-score[t], t))[:top_n]
    for t in _top(score, len(score)):
        if len(chosen) >= top_n:
            break
        if t not in chosen:
            chosen.append(t)
    return _equal(pd.Index(chosen), daily.columns, 1.0 / top_n)


def _realized_vol(daily: pd.DataFrame) -> pd.Series:
    return daily.iloc[-(TRADING_DAYS_YEAR + 1) :].pct_change().dropna().std()


def _sig_low_vol(daily, monthly, lookback, top_n, fund=None):
    return _equal(_top(-_realized_vol(daily), top_n), daily.columns, 1.0 / top_n)


def _sig_reversal(daily, monthly, lookback, top_n, fund=None):
    return _equal(_top(-_mom(monthly, 1), top_n), daily.columns, 1.0 / top_n)


def _sig_composite(daily, monthly, lookback, top_n, fund=None):
    short = daily.iloc[-TRADING_DAYS_MONTH:].mean()
    long = daily.iloc[-TRADING_DAYS_SMA:].mean()
    ranks = pd.concat(
        [
            _mom(monthly, lookback, skip=1).rank(),
            (short / long - 1.0).rank(),
            (-_realized_vol(daily)).rank(),
        ],
        axis=1,
    ).mean(axis=1)
    eligible = ranks[daily.iloc[-1] > long]
    chosen = _top(eligible, top_n)
    return _equal(chosen, daily.columns, 1.0 / top_n)


def _quality_score(fund: pd.DataFrame) -> pd.Series:
    """Average percentile rank of profitability, cash conversion and leverage.

    A name needs at least two available metrics; missing ones are skipped, not
    filled, so a bank without free cash flow is judged on what it reports.
    """
    ranks = pd.concat(
        [
            fund["roe"].rank(pct=True),
            fund["net_margin"].rank(pct=True),
            fund["fcf_margin"].rank(pct=True),
            (-fund["debt_to_equity"]).rank(pct=True),
        ],
        axis=1,
    )
    score = ranks.mean(axis=1)
    return score.where(ranks.notna().sum(axis=1) >= 2)


def _sig_quality(daily, monthly, lookback, top_n, fund=None):
    return _equal(_top(_quality_score(fund), top_n), daily.columns, 1.0 / top_n)


def _sig_growth(daily, monthly, lookback, top_n, fund=None):
    return _equal(_top(fund["revenue_growth"], top_n), daily.columns, 1.0 / top_n)


def _sig_quality_momentum(daily, monthly, lookback, top_n, fund=None):
    ranks = pd.concat(
        [_quality_score(fund).rank(pct=True), _mom(monthly, lookback, skip=1).rank(pct=True)],
        axis=1,
    )
    score = ranks.mean(axis=1).where(ranks.notna().all(axis=1))
    return _equal(_top(score, top_n), daily.columns, 1.0 / top_n)


def _sig_quality_trend(daily, monthly, lookback, top_n, fund=None):
    above = daily.iloc[-1] > daily.iloc[-TRADING_DAYS_SMA:].mean()
    score = _quality_score(fund)[above.reindex(fund.index).fillna(False)]
    return _equal(_top(score, top_n), daily.columns, 1.0 / top_n)


STRONG_QUALITY_PERCENTILE = 0.75  # fixed in advance: top quartile of the universe


def _strong_names(fund: pd.DataFrame) -> pd.Index:
    score = _quality_score(fund)
    return score.index[score.rank(pct=True) >= STRONG_QUALITY_PERCENTILE]


def _sig_quality_strong_cash(daily, monthly, lookback, top_n, fund=None):
    """Each strong name keeps its 1/universe slot; every other slot stays cash."""
    return _equal(_strong_names(fund), daily.columns, 1.0 / len(daily.columns))


def _sig_quality_strong_reinvest(daily, monthly, lookback, top_n, fund=None):
    """Fully invested, split equally across only the strong names."""
    strong = _strong_names(fund)
    return _equal(strong, daily.columns, 1.0 / max(len(strong), 1))


STRATEGIES: tuple[StrategySpec, ...] = (
    StrategySpec(
        "momentum_12m",
        "Momentum 12m (current allocator)",
        "Momentum",
        "Hold the top N by trailing 12-month return, equal weight.",
        "Jegadeesh & Titman 1993; this repo's allocator",
        _sig_momentum,
    ),
    StrategySpec(
        "momentum_12_1",
        "Momentum 12-1",
        "Momentum",
        "Top N by 12-month return excluding the latest month, equal weight.",
        "Jegadeesh & Titman 1993 (skip-month convention)",
        _sig_momentum_skip,
    ),
    StrategySpec(
        "dual_momentum",
        "Dual momentum",
        "Momentum + trend",
        "Top N by 12-month return, but an asset with a negative 12-month return stays cash.",
        "Antonacci, Dual Momentum",
        _sig_dual,
    ),
    StrategySpec(
        "tsmom",
        "Time-series momentum",
        "Trend",
        "Hold every asset with a positive 12-month return at 1/universe each; rest cash.",
        "Moskowitz, Ooi & Pedersen 2012",
        _sig_tsmom,
    ),
    StrategySpec(
        "trend_sma200",
        "Trend: price > 200-day SMA",
        "Trend",
        "Hold every asset trading above its 200-day average at 1/universe each; rest cash.",
        "Faber 2007",
        _sig_trend,
    ),
    StrategySpec(
        "ma_distance",
        "MA distance (21d / 200d)",
        "Technical",
        "Top N by 21-day average relative to 200-day average, equal weight.",
        "Avramov, Cheng & Hameed (moving-average distance)",
        _sig_ma_distance,
    ),
    StrategySpec(
        "ma_distance_buffer",
        "MA distance + sell buffer",
        "Technical",
        "MA distance, but keep a holding until it drops out of the top 5 (turnover control).",
        "Variant of MA distance; buffer width fixed in advance, counted as an extra trial",
        _sig_ma_distance_buffer,
        stateful=True,
    ),
    StrategySpec(
        "low_vol",
        "Low volatility",
        "Risk",
        "Top N lowest trailing one-year daily volatility, equal weight.",
        "Low-volatility / betting-against-beta family",
        _sig_low_vol,
    ),
    StrategySpec(
        "reversal_1m",
        "Short-term reversal",
        "Mean reversion",
        "Top N by worst last-month return, equal weight.",
        "Jegadeesh 1990 short-term reversal",
        _sig_reversal,
    ),
    StrategySpec(
        "technical_blend",
        "Technical blend + trend filter",
        "Multi-signal",
        "Average rank of 12-1 momentum, MA distance and low volatility; must also be above the 200-day SMA.",
        "Composite of the rules above (a combination, not a new search axis)",
        _sig_composite,
    ),
)

FUNDAMENTAL_STRATEGIES: tuple[StrategySpec, ...] = (
    StrategySpec(
        "quality",
        "Quality (profitability, cash, leverage)",
        "Fundamental",
        "Top N by average rank of ROE, net margin, FCF margin and low debt/equity from the latest knowable fiscal year.",
        "Novy-Marx 2013 / Asness et al. quality family",
        _sig_quality,
        True,
    ),
    StrategySpec(
        "growth",
        "Revenue growth",
        "Fundamental",
        "Top N by latest knowable fiscal-year revenue growth.",
        "Growth factor (sales growth)",
        _sig_growth,
        True,
    ),
    StrategySpec(
        "quality_momentum",
        "Quality + momentum",
        "Fundamental + technical",
        "Top N by average rank of quality score and 12-1 momentum.",
        "Quality-and-momentum combination (Asness, Frazzini, Pedersen)",
        _sig_quality_momentum,
        True,
    ),
    StrategySpec(
        "quality_trend",
        "Quality, only above 200-day SMA",
        "Fundamental + technical",
        "Top N quality names, restricted to those trading above their 200-day average; empty slots stay cash.",
        "Quality with a Faber trend filter",
        _sig_quality_trend,
        True,
    ),
    StrategySpec(
        "quality_strong_cash",
        "Buy only strong quality (rest cash)",
        "Fundamental",
        "Hold a name at 1/universe only while its quality score is in the universe's top quartile; otherwise that slot is cash.",
        "Quality with an absolute-style entry gate; threshold fixed in advance",
        _sig_quality_strong_cash,
        True,
    ),
    StrategySpec(
        "quality_strong_reinvest",
        "Strong quality only (equal weight)",
        "Fundamental",
        "Split capital equally across the names whose quality score is in the top quartile.",
        "Quality top-quartile basket; threshold fixed in advance",
        _sig_quality_strong_reinvest,
        True,
    ),
)


class StrategyPeriod(BaseModel):
    as_of_date: date
    entry_date: date
    exit_date: date
    selected_tickers: list[str]
    exposure: float
    turnover: float
    net_return: float


class Holding(BaseModel):
    """One uninterrupted stay in a name, from the open that bought it to the open that sold it.

    Prices are the provider-adjusted opens the backtest filled at, not prices a
    live account would have paid. ``price_return`` is gross of cost and of any
    weight resizing while the name stayed selected.
    """

    ticker: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    days_held: int
    price_return: float
    exit_reason: str  # "dropped_from_selection" | "backtest_end"


class StrategyResult(BaseModel):
    id: str
    label: str
    family: str
    rule: str
    source: str
    net_compound_return: float
    max_drawdown: float
    annualized_sharpe: float | None
    mean_exposure: float
    mean_monthly_turnover: float
    months_with_trades: int
    excess_vs_hold: float
    log_excess_ci_95: tuple[float, float] | None
    excess_p_value: float | None
    # Both are computed on the monthly log-excess series versus continuous hold
    # (an information ratio), not on raw returns: a raw Sharpe above zero is
    # nearly guaranteed in a rising market and says nothing about beating hold.
    probabilistic_sharpe: float | None
    deflated_sharpe: float | None
    last_selection: list[str]
    holdings: list[Holding]
    period_log: list[StrategyPeriod]


class StrategyComparisonReport(BaseModel):
    hypothesis: str
    universe: list[str]
    config: StrategyComparisonConfig
    oos_start: date
    oos_end: date
    periods: int
    effective_n: float | None
    n_strategies_tested: int
    benchmark: StrategyResult
    strategies: list[StrategyResult]
    curve_dates: list[date]
    curves: dict[str, list[float]]
    drawdown_basis: str = "daily_close_mark_to_market"
    price_basis: str = "provided_open_close_not_dividend_verified"
    notes: list[str]


def run_strategy_comparison(
    price_histories: Mapping[str, pd.DataFrame],
    *,
    start: date | None = None,
    end: date | None = None,
    config: StrategyComparisonConfig | None = None,
    specs: tuple[StrategySpec, ...] | None = None,
    fundamentals_dir: Path | None = None,
) -> StrategyComparisonReport:
    config = config or StrategyComparisonConfig()
    if specs is None:
        specs = STRATEGIES + (FUNDAMENTAL_STRATEGIES if fundamentals_dir else ())
    if any(spec.needs_fundamentals for spec in specs) and fundamentals_dir is None:
        raise ValueError("Fundamental strategies need a point-in-time fundamentals directory")
    if len(price_histories) < config.top_n:
        raise ValueError("price_histories must contain at least top_n tickers")
    opens, closes, monthly, entry_dates = _monthly_execution_panels(price_histories)
    columns = monthly.columns
    cost_rate = config.cost_bps_per_side / 10_000.0
    first = pd.Timestamp(start) if start is not None else monthly.index[0]
    last = pd.Timestamp(end) if end is not None else closes.index[-1]

    ending: dict[str, pd.Series | None] = {s.id: None for s in specs}
    logs: dict[str, list[StrategyPeriod]] = {s.id: [] for s in specs}
    targets: dict[str, dict[date, pd.Series]] = {s.id: {} for s in specs}
    hold_returns: list[float] = []
    hold_weights = pd.Series(1.0 / len(columns), index=columns)

    for i in range(config.lookback_months, len(monthly) - 1):
        as_of = monthly.index[i]
        if as_of < first:
            continue
        if as_of > last:
            break
        entry, exit_ = entry_dates.get(as_of), entry_dates.get(monthly.index[i + 1])
        if entry is None or exit_ is None:
            continue
        daily = closes.loc[:as_of]  # point-in-time slice: nothing after the decision close
        if len(daily) < MIN_DAILY_HISTORY or i < config.lookback_months + 1:
            continue
        window = monthly.iloc[: i + 1]
        asset = opens.loc[pd.Timestamp(exit_)] / opens.loc[pd.Timestamp(entry)] - 1.0
        fund = (
            fundamental_metrics(fundamentals_dir, list(columns), as_of.date())
            if fundamentals_dir is not None
            else None
        )
        for spec in specs:
            extra = {}
            if spec.stateful:
                prior = ending[spec.id]
                extra["held"] = [] if prior is None else list(prior.index[prior > 1e-12])
            w = spec.signal(
                daily,
                window,
                config.lookback_months,
                config.top_n,
                fund if spec.needs_fundamentals else None,
                **extra,
            )
            if (w < -1e-12).any() or float(w.sum()) > 1.0 + 1e-9:
                raise ValueError(f"{spec.id} produced an invalid long-only weight vector")
            turnover = rebalance_turnover(ending[spec.id], w)
            gross = float((w * asset).sum())
            net = (1.0 + gross) * (1.0 - turnover * cost_rate) - 1.0
            drifted = w * (1.0 + asset)
            total = (1.0 - float(w.sum())) + float(drifted.sum())
            ending[spec.id] = drifted / total
            logs[spec.id].append(
                StrategyPeriod(
                    as_of_date=as_of.date(),
                    entry_date=entry,
                    exit_date=exit_,
                    selected_tickers=sorted(w.index[w > 0]),
                    exposure=float(w.sum()),
                    turnover=turnover,
                    net_return=net,
                )
            )
            targets[spec.id][entry] = w
        hold_returns.append(float((hold_weights * asset).sum()))
        hold_weights = hold_weights * (1.0 + asset)
        hold_weights /= float(hold_weights.sum())

    n_periods = len(hold_returns)
    if n_periods < 2:
        raise ValueError("No complete out-of-sample period was formed")
    first_entry = logs[specs[0].id][0].entry_date
    final_exit = logs[specs[0].id][-1].exit_date

    # Final liquidation is charged on the exposure actually held at the end.
    for spec in specs:
        exposure = float(ending[spec.id].sum())
        logs[spec.id][-1].net_return = (1.0 + logs[spec.id][-1].net_return) * (
            1.0 - exposure * cost_rate
        ) - 1.0
        targets[spec.id][final_exit] = pd.Series(0.0, index=columns)
    hold_net = list(hold_returns)
    hold_net[0] = (1.0 + hold_net[0]) * (1.0 - cost_rate) - 1.0
    hold_net[-1] = (1.0 + hold_net[-1]) * (1.0 - cost_rate) - 1.0
    hold_targets = {
        first_entry: pd.Series(1.0 / len(columns), index=columns),
        final_exit: pd.Series(0.0, index=columns),
    }

    windows = [
        ("portfolio", p.entry_date, max(p.entry_date, p.exit_date - timedelta(days=1)))
        for p in logs[specs[0].id]
    ]
    effective_n = stats.effective_sample_size(windows) or None

    def _results(sid, label, family, rule, source, net, log, tgt):
        curve = _daily_equity_curve(opens, closes, tgt, cost_rate)
        excess = [math.log1p(a) - math.log1p(b) for a, b in zip(net, hold_net, strict=True)]
        sharpe = _annualized_sharpe(net)
        per_period = _per_period_sharpe(excess)
        return (
            StrategyResult(
                id=sid,
                label=label,
                family=family,
                rule=rule,
                source=source,
                net_compound_return=_compound(net),
                max_drawdown=_max_drawdown(curve),
                annualized_sharpe=sharpe,
                mean_exposure=sum(p.exposure for p in log) / len(log) if log else 1.0,
                mean_monthly_turnover=sum(p.turnover for p in log) / len(log) if log else 0.0,
                months_with_trades=sum(1 for p in log if p.turnover > 1e-9),
                excess_vs_hold=_compound(net) - _compound(hold_net),
                log_excess_ci_95=stats.moving_block_bootstrap_ci(
                    excess,
                    block_length=config.bootstrap_block_periods,
                    n_resamples=config.bootstrap_resamples,
                    seed=config.bootstrap_seed,
                ),
                excess_p_value=stats.t_test_vs_zero(excess, effective_n)[1],
                probabilistic_sharpe=(
                    stats.probabilistic_sharpe_ratio(
                        per_period, len(excess), stats.skewness(excess), stats.kurtosis(excess)
                    )
                    if per_period is not None
                    else None
                ),
                deflated_sharpe=None,
                last_selection=log[-1].selected_tickers if log else list(columns),
                holdings=_holdings(opens, tgt),
                period_log=log,
            ),
            curve,
            per_period,
        )

    results: list[StrategyResult] = []
    per_period_sr: list[float | None] = []
    for spec in specs:
        net = [p.net_return for p in logs[spec.id]]
        result, _, sr = _results(
            spec.id,
            spec.label,
            spec.family,
            spec.rule,
            spec.source,
            net,
            logs[spec.id],
            targets[spec.id],
        )
        results.append(result)
        per_period_sr.append(sr)

    # Deflate every candidate for the width of this search.
    valid = [s for s in per_period_sr if s is not None]
    sr_variance = _variance(valid)
    for result, sr in zip(results, per_period_sr, strict=True):
        if sr is None or sr_variance is None:
            continue
        excess = [
            math.log1p(p.net_return) - math.log1p(b)
            for p, b in zip(result.period_log, hold_net, strict=True)
        ]
        result.deflated_sharpe = stats.deflated_sharpe_ratio(
            sr,
            len(excess),
            stats.skewness(excess),
            stats.kurtosis(excess),
            n_strategies=len(specs),
            sr_variance=sr_variance,
        )

    benchmark, _, _ = _results(
        "continuous_hold",
        "Equal-weight continuous hold",
        "Benchmark",
        "Buy every asset once at equal weight and never rebalance.",
        "Strict buy-and-hold",
        hold_net,
        [],
        hold_targets,
    )
    dates = [logs[specs[0].id][0].entry_date] + [p.exit_date for p in logs[specs[0].id]]
    curves = {"continuous_hold": _wealth(hold_net)}
    for spec, result in zip(specs, results, strict=True):
        curves[spec.id] = _wealth([p.net_return for p in result.period_log])

    return StrategyComparisonReport(
        hypothesis=(
            "Which commonly used price-only rule, if any, beats equal-weight "
            "buy-and-hold on the same universe after costs?"
        ),
        universe=list(columns),
        config=config,
        oos_start=logs[specs[0].id][0].as_of_date,
        oos_end=final_exit,
        periods=n_periods,
        effective_n=effective_n,
        n_strategies_tested=len(specs),
        benchmark=benchmark,
        strategies=results,
        curve_dates=dates,
        curves=curves,
        notes=[
            "Monthly decisions; fills at the next common session open; one-way cost on turnover.",
            f"{len(specs)} rules were compared; the deflated Sharpe corrects for that search.",
            "Universe is a fixed, curated watchlist of surviving large caps (survivorship-biased) and has been inspected before; dip-buying rules look better there than they would on a point-in-time index.",
            *(
                [
                    "Fundamental rules use SEC CompanyFacts by filing date plus one day, from the latest fiscal year (up to ~18 months old); value ratios are excluded because split-adjusted prices cannot be divided by as-reported per-share data.",
                ]
                if fundamentals_dir is not None
                else ["Fundamental rules are not included in this run."]
            ),
            "Prices are provider-adjusted; dividends, taxes and real-world fills are unverified.",
        ],
    )


def _holdings(opens: pd.DataFrame, targets: Mapping[date, pd.Series]) -> list[Holding]:
    """Turn scheduled target weights into buy-to-sell stays, using the fill opens."""
    previous = pd.Series(0.0, index=opens.columns)
    started: dict[str, tuple[date, float]] = {}
    out: list[Holding] = []
    last_day = max(targets)
    for day in sorted(targets):
        weights = targets[day].reindex(opens.columns, fill_value=0.0)
        prices = opens.loc[pd.Timestamp(day)]
        for ticker in opens.columns:
            before, after = previous[ticker] > 1e-12, weights[ticker] > 1e-12
            if after and not before:
                started[ticker] = (day, float(prices[ticker]))
            elif before and not after:
                entry_day, entry_price = started.pop(ticker)
                out.append(
                    Holding(
                        ticker=ticker,
                        entry_date=entry_day,
                        entry_price=entry_price,
                        exit_date=day,
                        exit_price=float(prices[ticker]),
                        days_held=(day - entry_day).days,
                        price_return=float(prices[ticker]) / entry_price - 1.0,
                        exit_reason="backtest_end" if day == last_day else "dropped_from_selection",
                    )
                )
        previous = weights
    return sorted(out, key=lambda h: (h.entry_date, h.ticker))


def _wealth(net: list[float]) -> list[float]:
    value, series = 100.0, [100.0]
    for r in net:
        value *= 1.0 + r
        series.append(value)
    return series


def _per_period_sharpe(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return mean / math.sqrt(variance) if variance > 0 else None


def _variance(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / (len(values) - 1)


def to_markdown(report: StrategyComparisonReport) -> str:
    c = report.config
    lines = [
        "# Strategy comparison (price-only, point-in-time)",
        "",
        (
            f"Universe: {', '.join(report.universe)} · {report.oos_start} → {report.oos_end} · "
            f"{report.periods} monthly periods (effective N {report.effective_n:.1f}) · "
            f"{c.cost_bps_per_side:g} bps/side · top {c.top_n}"
        ),
        "",
        "| Strategy | Net return | Max DD | Sharpe | Exposure | Excess vs hold | 95% CI (log excess, mean/mo) | DSR (excess) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    rows = sorted(report.strategies, key=lambda s: -s.net_compound_return)
    for s in [report.benchmark, *rows]:
        ci = s.log_excess_ci_95
        lines.append(
            f"| {s.label} | {s.net_compound_return:+.1%} | {s.max_drawdown:.1%} | "
            f"{'n/a' if s.annualized_sharpe is None else f'{s.annualized_sharpe:.2f}'} | "
            f"{s.mean_exposure:.0%} | "
            f"{'—' if s is report.benchmark else f'{s.excess_vs_hold * 100:+.1f} pp'} | "
            f"{'—' if ci is None or s is report.benchmark else f'[{ci[0]:+.4f}, {ci[1]:+.4f}]'} | "
            f"{'—' if s.deflated_sharpe is None else f'{s.deflated_sharpe:.2f}'} |"
        )
    lines += ["", *[f"- {n}" for n in report.notes]]
    return "\n".join(lines) + "\n"
