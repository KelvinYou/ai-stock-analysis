"""Synthetic portfolio simulator for backtests only.

This module turns BacktestTrial signals into an equity curve. It never reads
real holdings, private account data, or portfolio policy files.

Event-driven model:
- Each directional trial is an independent bet of `position_size_pct` of current cash.
- Cash is reserved at entry, P&L released at exit. No marked-to-market between events
  (we don't have intra-horizon prices).
- Neutral signals skipped. Sell signals skipped unless `allow_short=True`.
- Multiple strategies can be compared: overall synthesis, each agent in isolation,
  or a buy-and-hold baseline.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel

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
    position_size_pct: float = 0.10  # fraction of current cash per trade
    allow_short: bool = False
    # One-way cost in basis points, charged on entry and again on exit. Covers
    # commission, spread, and slippage together. Zero is the historical default
    # but is a claim about the world, not a neutral choice — a strategy trading
    # a 30-day horizon on Bursa small caps can have its entire edge inside the
    # spread.
    cost_bps_per_side: float = 0.0


class TradeLog(BaseModel):
    ticker: str
    entry_date: date
    exit_date: date
    direction: int  # +1 long, -1 short
    stake: float  # capital committed
    pnl: float  # realized dollar P&L
    return_pct: float


class EquityPoint(BaseModel):
    date: date
    equity: float


class StrategyReport(BaseModel):
    strategy: str  # "overall", "technical", "fundamentals", "sentiment", "macro", "buy_and_hold"
    starting_balance: float
    final_balance: float
    total_return_pct: float
    max_drawdown_pct: float
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None
    equity_curve: list[EquityPoint]
    trades: list[TradeLog]

    # Per-trade Sharpe and its selection-bias-aware companions. `deflated_sharpe`
    # is only populated for the best strategy in a comparison — it is defined
    # relative to how many candidates were searched.
    trade_sharpe: float | None = None
    effective_n: float | None = None
    probabilistic_sharpe: float | None = None
    deflated_sharpe: float | None = None


class PortfolioReport(BaseModel):
    config: PortfolioConfig
    strategies: list[StrategyReport]
    # Number of strategies compared in this run. The winner's Sharpe has to be
    # read against this: pick the best of six coin-flipping strategies and the
    # best one looks good by construction.
    n_strategies_tested: int = 0
    best_strategy: str | None = None


# ----------------------------------------------------------------------
@dataclass
class _OpenPosition:
    ticker: str
    entry_date: date
    direction: int
    stake: float
    realized_return: float  # known from the trial (forward-looking, fixed horizon)


def simulate(
    result: BacktestResult,
    config: PortfolioConfig | None = None,
    strategies: list[str] | None = None,
) -> PortfolioReport:
    """Run one or more strategies over the trial set. Returns per-strategy stats."""
    config = config or PortfolioConfig()
    strategies = strategies or ["overall", "fundamentals", "technical", "sentiment", "macro", "buy_and_hold"]

    reports = [_simulate_one(result, config, s) for s in strategies]
    _attach_selection_bias_metrics(reports)

    ranked = [r for r in reports if r.trade_sharpe is not None]
    best = max(ranked, key=lambda r: r.trade_sharpe).strategy if ranked else None

    return PortfolioReport(
        config=config,
        strategies=reports,
        n_strategies_tested=len(reports),
        best_strategy=best,
    )


def _round_trip_cost(config: PortfolioConfig) -> float:
    """Entry + exit cost as a fraction of the stake."""
    return 2.0 * config.cost_bps_per_side / 10_000.0


def _attach_selection_bias_metrics(reports: list[StrategyReport]) -> None:
    """Populate Sharpe, PSR, and — for the winner only — the deflated Sharpe.

    The deflated Sharpe answers the question the strategy table otherwise
    invites the reader to skip: the best row was chosen *because* it was best,
    so its Sharpe is an order statistic, not a sample mean. DSR reprices it
    against the expected maximum across this many candidates under the null of
    no skill.
    """
    for report in reports:
        returns = [t.return_pct for t in report.trades]
        # Trades overlap in time exactly as trials do; reuse the same discount.
        n_eff = stats.effective_sample_size(
            [(t.ticker, t.entry_date, t.exit_date) for t in report.trades]
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

    winner = max(ranked, key=lambda r: r.trade_sharpe)
    if winner.effective_n and winner.effective_n >= 2:
        winner.deflated_sharpe = stats.deflated_sharpe_ratio(
            winner.trade_sharpe,
            int(winner.effective_n),
            stats.skewness([t.return_pct for t in winner.trades]),
            stats.kurtosis([t.return_pct for t in winner.trades]),
            n_strategies=len(ranked),
            sr_variance=sr_variance,
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
        return _buy_and_hold(completed, config)

    # Event queue: (date, order, kind, trial, direction, stake)
    # Order: exits before entries on the same day, so capital recycles.
    cash = config.starting_balance
    equity_curve: list[EquityPoint] = []
    trades: list[TradeLog] = []
    entries: list[tuple[date, BacktestTrial, int]] = []  # (entry_date, trial, direction)

    for trial in completed:
        direction = _direction_for(trial, strategy, config.allow_short)
        if direction == 0:
            continue
        entries.append((trial.as_of_date, trial, direction))

    # Process entries chronologically, scheduling exits.
    entries.sort(key=lambda e: e[0])
    pending_exits: dict[date, list[_OpenPosition]] = defaultdict(list)

    round_trip = _round_trip_cost(config)

    def flush_exits_up_to(d: date) -> None:
        nonlocal cash
        # Close any positions whose exit_date is on or before d
        due_dates = sorted(k for k in pending_exits if k <= d)
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
                    )
                )
                equity_curve.append(EquityPoint(date=ed, equity=_equity(cash, pending_exits)))

    for entry_date, trial, direction in entries:
        flush_exits_up_to(entry_date)
        stake = cash * config.position_size_pct
        if stake <= 0:
            continue
        cash -= stake
        pending_exits[trial.exit_date].append(
            _OpenPosition(
                ticker=trial.ticker,
                entry_date=trial.as_of_date,
                direction=direction,
                stake=stake,
                realized_return=trial.realized_return,
            )
        )
        equity_curve.append(EquityPoint(date=entry_date, equity=_equity(cash, pending_exits)))

    # Close any remaining positions
    if pending_exits:
        final_date = max(pending_exits.keys())
        flush_exits_up_to(final_date)

    return _build_report(strategy, config, cash, equity_curve, trades)


def _buy_and_hold(trials: list[BacktestTrial], config: PortfolioConfig) -> StrategyReport:
    """Take every trial as a long at position_size_pct — no signal filter."""
    cash = config.starting_balance
    equity_curve: list[EquityPoint] = []
    trades: list[TradeLog] = []
    pending_exits: dict[date, list[_OpenPosition]] = defaultdict(list)

    round_trip = _round_trip_cost(config)

    def flush_up_to(d: date) -> None:
        nonlocal cash
        for ed in sorted(k for k in pending_exits if k <= d):
            for pos in pending_exits.pop(ed):
                net_return = pos.realized_return - round_trip
                pnl = pos.stake * net_return
                cash += pos.stake + pnl
                trades.append(
                    TradeLog(
                        ticker=pos.ticker,
                        entry_date=pos.entry_date,
                        exit_date=ed,
                        direction=1,
                        stake=pos.stake,
                        pnl=pnl,
                        return_pct=net_return,
                    )
                )
                equity_curve.append(EquityPoint(date=ed, equity=_equity(cash, pending_exits)))

    for trial in sorted(trials, key=lambda t: t.as_of_date):
        flush_up_to(trial.as_of_date)
        stake = cash * config.position_size_pct
        if stake <= 0:
            continue
        cash -= stake
        pending_exits[trial.exit_date].append(
            _OpenPosition(
                ticker=trial.ticker,
                entry_date=trial.as_of_date,
                direction=1,
                stake=stake,
                realized_return=trial.realized_return,
            )
        )
        equity_curve.append(EquityPoint(date=trial.as_of_date, equity=_equity(cash, pending_exits)))

    if pending_exits:
        flush_up_to(max(pending_exits.keys()))

    return _build_report("buy_and_hold", config, cash, equity_curve, trades)


def _direction_for(trial: BacktestTrial, strategy: str, allow_short: bool) -> int:
    if strategy == "overall":
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


def _build_report(
    strategy: str,
    config: PortfolioConfig,
    final_cash: float,
    equity_curve: list[EquityPoint],
    trades: list[TradeLog],
) -> StrategyReport:
    final_balance = equity_curve[-1].equity if equity_curve else final_cash
    total_return = (final_balance - config.starting_balance) / config.starting_balance

    # Max drawdown on the realized equity curve
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
    lines = [
        "## Portfolio simulation",
        "",
        f"- Starting balance: ${c.starting_balance:,.2f}",
        f"- Position size: {c.position_size_pct * 100:.1f}% of cash per trade",
        f"- Shorts enabled: {c.allow_short}",
        cost_line,
        "",
        "| Strategy | Final balance | Return | Max DD | Trades | n_eff | Win rate | Sharpe | PSR |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in report.strategies:
        marker = " 🏆" if s.strategy == report.best_strategy else ""
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
