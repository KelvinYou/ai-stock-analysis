"""Portfolio simulator: turns BacktestTrial signals into an equity curve.

Event-driven model:
- Each directional trial is an independent bet of `position_size_pct` of current cash.
- Cash is reserved at entry, P&L released at exit. No marked-to-market between events
  (we don't have intra-horizon prices).
- Neutral signals skipped. Sell signals skipped unless `allow_short=True`.
- Multiple strategies can be compared: overall synthesis, each agent in isolation,
  or a buy-and-hold baseline.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel

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


class PortfolioReport(BaseModel):
    config: PortfolioConfig
    strategies: list[StrategyReport]


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
    return PortfolioReport(config=config, strategies=reports)


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

    def flush_exits_up_to(d: date) -> None:
        nonlocal cash
        # Close any positions whose exit_date is on or before d
        due_dates = sorted(k for k in pending_exits.keys() if k <= d)
        for ed in due_dates:
            for pos in pending_exits.pop(ed):
                pnl = pos.stake * pos.direction * pos.realized_return
                cash += pos.stake + pnl
                trades.append(
                    TradeLog(
                        ticker=pos.ticker,
                        entry_date=pos.entry_date,
                        exit_date=ed,
                        direction=pos.direction,
                        stake=pos.stake,
                        pnl=pnl,
                        return_pct=pos.direction * pos.realized_return,
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

    def flush_up_to(d: date) -> None:
        nonlocal cash
        for ed in sorted(k for k in pending_exits.keys() if k <= d):
            for pos in pending_exits.pop(ed):
                pnl = pos.stake * pos.realized_return
                cash += pos.stake + pnl
                trades.append(
                    TradeLog(
                        ticker=pos.ticker,
                        entry_date=pos.entry_date,
                        exit_date=ed,
                        direction=1,
                        stake=pos.stake,
                        pnl=pnl,
                        return_pct=pos.realized_return,
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
    lines = [
        "## Portfolio simulation",
        "",
        f"- Starting balance: ${c.starting_balance:,.2f}",
        f"- Position size: {c.position_size_pct * 100:.1f}% of cash per trade",
        f"- Shorts enabled: {c.allow_short}",
        "",
        "| Strategy | Final balance | Return | Max DD | Trades | Win rate | Best | Worst |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in report.strategies:
        lines.append(
            f"| {s.strategy} "
            f"| ${s.final_balance:,.2f} "
            f"| {_fmt_pct(s.total_return_pct)} "
            f"| {_fmt_pct(s.max_drawdown_pct)} "
            f"| {s.n_trades} "
            f"| {_fmt_pct(s.win_rate)} "
            f"| {_fmt_pct(s.best_trade_pct)} "
            f"| {_fmt_pct(s.worst_trade_pct)} |"
        )
    return "\n".join(lines) + "\n"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:+.2f}%"
