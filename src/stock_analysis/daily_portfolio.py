"""Shared deterministic daily portfolio valuation; no AI or backtest runtime imports."""

import math
from collections.abc import Mapping
from datetime import date

import pandas as pd


def rebalance_turnover(
    current_weights: pd.Series | None,
    target_weights: pd.Series,
) -> float:
    """Compute one-way turnover including cash for the initial investment."""

    target_cash = max(0.0, 1.0 - float(target_weights.sum()))
    if current_weights is None:
        return float(target_weights.sum())
    current_cash = max(0.0, 1.0 - float(current_weights.sum()))
    return float(
        ((target_weights - current_weights).abs().sum() + abs(target_cash - current_cash)) / 2.0
    )


def daily_equity_curve(
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    targets: Mapping[date, pd.Series],
    cost_rate: float,
    *,
    end_date: date | None = None,
) -> list[float]:
    """Mark a long-only portfolio to every common daily close.

    At each open, existing positions first receive the overnight gap, then
    scheduled weights are rebalanced and charged one-way turnover costs. The
    remaining positions are marked from that open to the close.
    """

    if not targets:
        return [1.0]
    first_day = min(targets)
    last_day = end_date if end_date is not None else max(targets)
    if last_day < max(targets):
        raise ValueError("Valuation end precedes a scheduled rebalance")
    daily = opens.loc[(opens.index.date >= first_day) & (opens.index.date <= last_day)]
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
            overnight_factor = (1.0 - float(weights.sum())) + float((weights * overnight).sum())
            if not math.isfinite(overnight_factor) or overnight_factor <= 0:
                raise ValueError("Invalid overnight portfolio valuation")
            equity *= overnight_factor
            if float(weights.sum()) > 0:
                weights = weights * overnight / overnight_factor

        target = target_by_timestamp.get(timestamp)
        if target is not None:
            turnover = rebalance_turnover(None if previous_close is None else weights, target)
            equity *= 1.0 - turnover * cost_rate
            weights = target.copy()

        intraday = closing / opening
        intraday_factor = (1.0 - float(weights.sum())) + float((weights * intraday).sum())
        if not math.isfinite(intraday_factor) or intraday_factor <= 0:
            raise ValueError("Invalid intraday portfolio valuation")
        equity *= intraday_factor
        if float(weights.sum()) > 0:
            weights = weights * intraday / intraday_factor
        curve.append(equity)
        previous_close = closing

    return curve
