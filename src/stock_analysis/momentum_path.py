"""Fixed-rule monthly momentum reconstruction for a gross, matched-date chart."""

import math
from datetime import date
from itertools import pairwise

import pandas as pd

from stock_analysis.allocation_snapshot import build_current_momentum
from stock_analysis.daily_portfolio import daily_equity_curve


def build_momentum_path(histories: dict[str, pd.DataFrame], *, start: date, end: date) -> dict:
    def unavailable(reason):
        return {"status": "unavailable", "reason": reason}

    if start >= end or len(histories) < 3:
        return unavailable("A complete multi-session strategy window is required.")
    frames = {}
    for ticker, original in histories.items():
        if not {"date", "open", "close"} <= set(original.columns):
            return unavailable("Adjusted opens and closes are required for historical execution.")
        frame = original[["date", "open", "close"]].copy()
        frame["date"] = frame.date.map(lambda d: pd.Timestamp(d).date())
        frame = frame[frame.date <= end].sort_values("date")
        if frame.empty or frame.date.duplicated().any():
            return unavailable("Historical execution dates are incomplete or duplicated.")
        frames[ticker] = frame.set_index("date")
    dates = sorted(set.intersection(*(set(f.index) for f in frames.values())))
    if start not in dates or end not in dates:
        return unavailable("Strategy and reference curves require identical start/end sessions.")
    month_ends = {}
    for day in dates:
        if day < end.replace(day=1):
            month_ends[(day.year, day.month)] = day
    initial = [day for day in month_ends.values() if day < start.replace(day=1)]
    if not initial:
        return unavailable("The month-end decision preceding the chart window is missing.")
    first_decision = max(initial)
    decisions = [d for d in month_ends.values() if d >= first_decision]
    periods = [pd.Period(d, freq="M") for d in decisions]
    if any((b - a).n != 1 for a, b in pairwise(periods)):
        return unavailable(
            "A month-end decision is missing; historical holdings cannot be inferred."
        )
    targets, rebalances = {}, []
    tickers = sorted(frames)
    for signal_date in decisions:
        panel = {
            ticker: frame[frame.index <= signal_date].reset_index()
            for ticker, frame in frames.items()
        }
        following = (pd.Timestamp(signal_date).replace(day=1) + pd.DateOffset(months=1)).date()
        ranking = build_current_momentum(panel, today=following, month_end_anchor=True)
        if ranking["status"] != "available":
            return unavailable("Twelve-month warm-up prices are missing for a historical basket.")
        subsequent = [day for day in dates if day > signal_date]
        if not subsequent:
            continue
        execution = subsequent[0]
        selected = [r["ticker"] for r in ranking["ranking"][:3]]
        weights = pd.Series(0.0, index=tickers)
        weights.loc[selected] = 1 / 3
        targets[execution] = weights
        rebalances.append(
            {
                "decision_date": str(signal_date),
                "execution_date": str(execution),
                "tickers": selected,
            }
        )
    if not targets or min(targets) > start:
        return unavailable(
            "The initial historical portfolio cannot be executed before the chart anchor."
        )
    execution_dates = [d for d in dates if min(targets) <= d <= end]
    index = pd.to_datetime(execution_dates)
    opens = pd.DataFrame(
        {t: frames[t].loc[execution_dates, "open"].to_numpy() for t in tickers}, index=index
    )
    closes = pd.DataFrame(
        {t: frames[t].loc[execution_dates, "close"].to_numpy() for t in tickers}, index=index
    )
    try:
        for panel in (opens, closes):
            if not all(math.isfinite(float(v)) and float(v) > 0 for v in panel.to_numpy().flat):
                return unavailable("Non-finite execution prices cannot form a strategy curve.")
        # Gross throughout: the existing reference curves also exclude trading fees.
        values = daily_equity_curve(opens, closes, targets, end_date=end, cost_rate=0.0)[1:]
    except (TypeError, ValueError, OverflowError):
        return unavailable("Historical daily portfolio valuation is unavailable.")
    levels = dict(zip(execution_dates, values, strict=True))
    base = levels[start]
    return {
        "status": "available",
        "start": str(start),
        "end": str(end),
        "basis": "gross",
        "cost_bps_per_side": 0,
        "curve": [
            {"date": str(d), "value": levels[d] / base * 100} for d in execution_dates if d >= start
        ],
        "rebalances": rebalances,
    }
