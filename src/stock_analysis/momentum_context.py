"""Display-only price context. Never changes the momentum selection or weights."""

import math

import pandas as pd

from stock_analysis.allocation_snapshot import build_current_momentum
from stock_analysis.momentum_path import build_momentum_path

PERIODS = ("d1", "m1", "m3", "m12")


def _panel(histories):
    frames = {}
    for ticker, original in histories.items():
        frame = original.copy()
        frame["date"] = frame.date.map(lambda d: pd.Timestamp(d).date())
        frames[ticker] = frame.set_index("date").sort_index()
    common = sorted(set.intersection(*(set(f.index) for f in frames.values())))
    return frames, common


def _anchor(dates, end, months):
    cutoff = (pd.Timestamp(end) - pd.DateOffset(months=months)).date()
    eligible = [d for d in dates if d <= cutoff]
    return eligible[-1] if eligible and (cutoff - eligible[-1]).days <= 7 else None


def _ratio(frame, start, end, start_column="close"):
    if start is None or start not in frame.index or end not in frame.index:
        return None
    if start_column not in frame:
        return None
    a, b = float(frame.loc[start, start_column]), float(frame.loc[end, "close"])
    return b / a - 1 if math.isfinite(a) and math.isfinite(b) and a > 0 and b > 0 else None


def build_momentum_context(
    histories,
    preview,
    monthly,
    *,
    today,
    reference=None,
    reference_config=None,
    comparisons=None,
    comparison_config=None,
):
    if preview["status"] != "available":
        return {"status": "unavailable", "reason": "A complete current ranking is required."}
    frames, dates = _panel(histories)
    end = pd.Timestamp(preview["as_of"]).date()
    dates = [d for d in dates if d <= end]
    starts = {"d1": dates[-2] if len(dates) >= 2 else None}
    starts.update({f"m{n}": _anchor(dates, end, n) for n in (1, 3, 12)})
    periods = {
        key: {"start": str(value) if value else None, "end": str(end)}
        for key, value in starts.items()
    }
    monthly_rows = monthly.get("ranking", [])
    monthly_ranks = {r["ticker"]: i + 1 for i, r in enumerate(monthly_rows)}
    previous = None
    if len(dates) >= 2:
        cutoff = dates[-2]
        previous = build_current_momentum(
            {
                t: f[f.date.map(lambda d: pd.Timestamp(d).date()) <= cutoff]
                for t, f in histories.items()
            },
            today=end,
        )
    previous_ranks = (
        {r["ticker"]: i + 1 for i, r in enumerate(previous.get("ranking", []))} if previous else {}
    )
    threshold = preview["ranking"][2]["score"]
    stocks = []
    for rank, row in enumerate(preview["ranking"], 1):
        ticker, frame = row["ticker"], frames[row["ticker"]]
        tail = frame.loc[[d for d in dates[-63:] if d in frame.index], "close"]
        anchor = pd.Timestamp(row["lookback_date"]).date()
        monthly_date = (
            pd.Timestamp(monthly["as_of"]).date() if monthly["status"] == "available" else None
        )
        stocks.append(
            {
                "ticker": ticker,
                "close": float(frame.loc[end, "close"]),
                "lookback_date": str(anchor),
                "lookback_close": float(frame.loc[anchor, "close"]),
                "returns": {key: _ratio(frame, start, end) for key, start in starts.items()},
                "drawdown_63": float(tail.iloc[-1] / tail.max() - 1) if len(tail) == 63 else None,
                "return_since_monthly_close": _ratio(frame, monthly_date, end),
                "gap_pp": (row["score"] - threshold) * 100,
                "monthly_rank": monthly_ranks.get(ticker),
                "previous_rank": previous_ranks.get(ticker),
                "rank_change_monthly": monthly_ranks[ticker] - rank
                if ticker in monthly_ranks
                else None,
                "rank_change_previous": previous_ranks[ticker] - rank
                if ticker in previous_ranks
                else None,
            }
        )
    history = []
    months = sorted({(d.year, d.month) for d in dates if d < today.replace(day=1)})[-3:]
    for year, month in months:
        month_dates = [d for d in dates if (d.year, d.month) == (year, month)]
        last = month_dates[-1]
        following = (pd.Timestamp(last).replace(day=1) + pd.DateOffset(months=1)).date()
        ranked = build_current_momentum(
            {
                t: f[f.date.map(lambda d: pd.Timestamp(d).date()) <= last]
                for t, f in histories.items()
            },
            today=following,
            month_end_anchor=True,
        )
        if ranked["status"] == "available":
            history.append(
                {
                    "as_of": str(last),
                    "ranking": [
                        {"ticker": r["ticker"], "score": r["score"], "rank": i + 1}
                        for i, r in enumerate(ranked["ranking"])
                    ],
                }
            )
    ref_config = reference_config or {
        "ticker": "SPY",
        "label": "SPY · S&P 500",
        "cost_bps_per_side": 20,
    }
    market = {
        "status": "unavailable",
        "reason": "Synchronized market reference prices are unavailable.",
    }
    cycle = {
        "status": "unavailable",
        "reason": "Next common-session adjusted opens and reference prices are required.",
    }
    if reference is not None and not reference.empty:
        try:
            ref_frames, _ = _panel({"reference": reference})
            ref = ref_frames["reference"]
            needed = [d for d in starts.values() if d is not None] + [end]
            if all(
                d in ref.index
                and math.isfinite(float(ref.loc[d, "close"]))
                and ref.loc[d, "close"] > 0
                for d in needed
            ):
                ref_returns = {key: _ratio(ref, start, end) for key, start in starts.items()}
                equal_returns = {
                    key: sum(_ratio(f, start, end) for f in frames.values()) / len(frames)
                    if start
                    else None
                    for key, start in starts.items()
                }
                curve = []
                curve_start = starts["m3"]
                curve_dates = [d for d in dates if curve_start and d >= curve_start]
                if curve_dates and all(
                    d in ref.index
                    and math.isfinite(float(ref.loc[d, "close"]))
                    and ref.loc[d, "close"] > 0
                    for d in curve_dates
                ):
                    curve = [
                        {
                            "date": str(d),
                            "market": (1 + _ratio(ref, curve_start, d)) * 100,
                            "equal_weight": sum(
                                1 + _ratio(f, curve_start, d) for f in frames.values()
                            )
                            / len(frames)
                            * 100,
                        }
                        for d in curve_dates
                    ]
                market = {
                    "status": "available",
                    "ticker": ref_config["ticker"],
                    "label": ref_config["label"],
                    "as_of": str(end),
                    "returns": ref_returns,
                    "equal_weight_returns": equal_returns,
                    "curve": curve,
                }
                if monthly["status"] == "available":
                    decision = pd.Timestamp(monthly["as_of"]).date()
                    eligible = [d for d in dates if d > decision]
                    if eligible:
                        first = eligible[0]
                        selected = [r["ticker"] for r in monthly_rows[:3]]
                        basket = [_ratio(frames[t], first, end, "open") for t in selected]
                        equal = [_ratio(f, first, end, "open") for f in frames.values()]
                        market_return = _ratio(ref, first, end, "open")
                        if all(r is not None for r in [*basket, *equal, market_return]):
                            cost = ref_config["cost_bps_per_side"] / 10000
                            gross = [sum(basket) / 3, sum(equal) / len(equal), market_return]
                            cycle = {
                                "status": "available",
                                "decision_date": str(decision),
                                "start": str(first),
                                "end": str(end),
                                "cost_bps_per_side": ref_config["cost_bps_per_side"],
                                "rows": [
                                    {
                                        "id": key,
                                        "gross": r,
                                        "net_scenario": (1 + r) * (1 - cost) ** 2 - 1,
                                    }
                                    for key, r in zip(
                                        ("monthly_basket", "equal_weight", "market"),
                                        gross,
                                        strict=True,
                                    )
                                ],
                            }
        except (KeyError, TypeError, ValueError, OverflowError):
            # An optional benchmark must not change or suppress a valid stock ranking.
            market = {
                "status": "unavailable",
                "reason": "Reference prices are malformed or incomplete.",
            }
            cycle = {
                "status": "unavailable",
                "reason": "Complete matched reference evidence is required.",
            }
    comparison_rows = []
    for item in comparison_config or []:
        ticker = item["ticker"]
        row = {
            **item,
            "status": "unavailable",
            "reason": "Matched completed-session reference data is unavailable.",
        }
        frame = (comparisons or {}).get(ticker)
        if frame is not None and not frame.empty:
            try:
                other = _panel({ticker: frame})[0][ticker]
                needed = [d for d in starts.values() if d is not None] + [end]
                if all(
                    d in other.index
                    and math.isfinite(float(other.loc[d, "close"]))
                    and other.loc[d, "close"] > 0
                    for d in needed
                ):
                    curve_start = starts["m3"]
                    curve_dates = [d for d in dates if curve_start and d >= curve_start]
                    curve = (
                        [
                            {"date": str(d), "value": (1 + _ratio(other, curve_start, d)) * 100}
                            for d in curve_dates
                        ]
                        if curve_dates
                        and all(
                            d in other.index
                            and math.isfinite(float(other.loc[d, "close"]))
                            and other.loc[d, "close"] > 0
                            for d in curve_dates
                        )
                        else []
                    )
                    comparison_cycle = {
                        "status": "unavailable",
                        "reason": "Matched next-session open is unavailable.",
                    }
                    if cycle["status"] == "available":
                        gross = _ratio(other, pd.Timestamp(cycle["start"]).date(), end, "open")
                        if gross is not None:
                            cost = ref_config["cost_bps_per_side"] / 10000
                            comparison_cycle = {
                                "status": "available",
                                "gross": gross,
                                "net_scenario": (1 + gross) * (1 - cost) ** 2 - 1,
                            }
                    row = {
                        **item,
                        "status": "available",
                        "as_of": str(end),
                        "returns": {
                            key: _ratio(other, start, end) for key, start in starts.items()
                        },
                        "curve": curve,
                        "cycle": comparison_cycle,
                    }
            except (KeyError, TypeError, ValueError, OverflowError):
                pass  # The reference stays explicitly unavailable; stock ranking is unchanged.
        comparison_rows.append(row)
    next_month_end = (pd.Timestamp(today).replace(day=1) + pd.offsets.MonthEnd(0)).date()
    monthly_selected = {r["ticker"] for r in monthly_rows[:3]}
    prior_selected = (
        {r["ticker"] for r in history[-2]["ranking"][:3]} if len(history) >= 2 else None
    )
    return {
        "status": "available",
        "version": 1,
        "as_of": str(end),
        "periods": periods,
        "stocks": stocks,
        "previous_rank_date": previous["as_of"]
        if previous and previous["status"] == "available"
        else None,
        "monthly_rank_date": monthly.get("as_of"),
        "ranking_history": history,
        "transition": {
            "from": history[-2]["as_of"],
            "to": monthly["as_of"],
            "entries": sorted(monthly_selected - prior_selected),
            "exits": sorted(prior_selected - monthly_selected),
        }
        if prior_selected is not None and monthly["status"] == "available"
        else None,
        "decision_month_end": str(next_month_end),
        "reference_ticker": ref_config["ticker"],
        "comparisons": comparison_rows,
        "momentum_curve": build_momentum_path(histories, start=starts["m3"], end=end)
        if starts["m3"]
        else {"status": "unavailable", "reason": "A three-month chart anchor is required."},
        "market": market,
        "cycle": cycle,
    }
