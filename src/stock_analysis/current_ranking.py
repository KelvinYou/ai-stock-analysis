"""Current price-only ranking for every price rule in the strategy comparison.

This previews what each rule would choose at today's last completed session. The
backtest decides at month-end, so a mid-month result is a preview, not a signal.
No network, no AI, no holdings. Weights come from the same signal functions the
backtest uses; this module only adds the metric each rule ranks on.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date

import pandas as pd

from stock_analysis.backtest.strategy_comparison import (
    STRATEGIES,
    TRADING_DAYS_MONTH,
    TRADING_DAYS_SMA,
    TRADING_DAYS_YEAR,
    StrategyComparisonConfig,
    _mom,
    _realized_vol,
)

CHART_SESSIONS = 252
HISTORY_MONTHS = 12
MAX_AGE_DAYS = 4
MIN_HISTORY_SESSIONS = TRADING_DAYS_YEAR + TRADING_DAYS_MONTH


def _sma_gap(daily: pd.DataFrame) -> pd.Series:
    return daily.iloc[-1] / daily.iloc[-TRADING_DAYS_SMA:].mean() - 1.0


def _ma_distance(daily: pd.DataFrame) -> pd.Series:
    return daily.iloc[-TRADING_DAYS_MONTH:].mean() / daily.iloc[-TRADING_DAYS_SMA:].mean() - 1.0


def _blend(daily: pd.DataFrame, monthly: pd.DataFrame, lookback: int) -> pd.Series:
    ranks = pd.concat(
        [
            _mom(monthly, lookback, skip=1).rank(pct=True),
            _ma_distance(daily).rank(pct=True),
            (-_realized_vol(daily)).rank(pct=True),
        ],
        axis=1,
    ).mean(axis=1)
    return ranks.where(_sma_gap(daily) > 0)  # must also trade above the 200-day SMA


# id -> (metric label, unit, higher_is_better, value(daily, monthly, lookback))
Metric = tuple[str, str, bool, Callable[[pd.DataFrame, pd.DataFrame, int], pd.Series]]
METRICS: dict[str, Metric] = {
    "momentum_12m": ("12-month return", "pct", True, lambda d, m, n: _mom(m, n)),
    "momentum_12_1": ("12-1 month return", "pct", True, lambda d, m, n: _mom(m, n, skip=1)),
    "dual_momentum": ("12-month return", "pct", True, lambda d, m, n: _mom(m, n)),
    "tsmom": ("12-month return", "pct", True, lambda d, m, n: _mom(m, n)),
    "trend_sma200": ("Price vs 200-day SMA", "pct", True, lambda d, m, n: _sma_gap(d)),
    "ma_distance": ("21-day vs 200-day average", "pct", True, lambda d, m, n: _ma_distance(d)),
    "low_vol": (
        "Daily volatility, 1 year",
        "pct",
        False,
        lambda d, m, n: _realized_vol(d),
    ),
    "reversal_1m": ("Last-month return", "pct", False, lambda d, m, n: _mom(m, 1)),
    "technical_blend": ("Blend rank (0-1)", "score", True, _blend),
}


def _selection_history(
    spec, panel: pd.DataFrame, month_ends: pd.DataFrame, tickers: list[str], config
) -> list[dict]:
    """What the rule would have chosen at each of the last month-ends, using only
    prices up to that date. The final entry is the current month-to-date preview."""
    history = []
    for stamp in month_ends.index[-(HISTORY_MONTHS + 1) :]:
        daily = panel.loc[:stamp, tickers]
        monthly = month_ends.loc[:stamp, tickers]
        if len(daily) < MIN_HISTORY_SESSIONS or len(monthly) < config.lookback_months + 2:
            continue
        weights = spec.signal(daily, monthly, config.lookback_months, config.top_n, None)
        history.append(
            {
                "as_of": stamp.date().isoformat(),
                "selected": sorted(t for t in tickers if weights[t] > 0),
            }
        )
    return history


def build_current_ranking(
    histories: dict[str, pd.DataFrame],
    *,
    universes: dict[str, list[str]],
    today: date,
    config: StrategyComparisonConfig | None = None,
) -> dict:
    """Rank every price rule for each named universe; reject partial evidence."""
    config = config or StrategyComparisonConfig()

    def unavailable(reason: str) -> dict:
        return {"status": "unavailable", "reason": reason}

    needed = sorted({t for tickers in universes.values() for t in tickers})
    closes: dict[str, pd.Series] = {}
    for ticker in needed:
        frame = histories.get(ticker)
        if frame is None or frame.empty or not {"date", "close"} <= set(frame.columns):
            return unavailable(f"Missing price history: {ticker}.")
        series = pd.Series(
            pd.to_numeric(frame["close"], errors="coerce").to_numpy(),
            index=pd.to_datetime(frame["date"]),
        ).sort_index()
        if series.index.duplicated().any() or not all(math.isfinite(x) and x > 0 for x in series):
            return unavailable(f"Invalid or duplicate prices: {ticker}.")
        closes[ticker] = series
    panel = pd.concat(closes, axis=1).dropna(how="any")
    if len(panel) < TRADING_DAYS_YEAR + TRADING_DAYS_MONTH + CHART_SESSIONS // 4:
        return unavailable("Not enough common price history.")
    tails = {s.index[-1] for s in closes.values()}
    if len(tails) != 1:
        return unavailable("All symbols must share one completed session.")
    as_of = panel.index[-1].date()
    if as_of >= today or (today - as_of).days > MAX_AGE_DAYS:
        return unavailable("Require a prior completed date no older than four calendar days.")

    month_ends = panel.groupby(panel.index.to_period("M")).tail(1)
    experiments = {}
    for comparison_id, tickers in universes.items():
        daily = panel[tickers]
        monthly = month_ends[tickers]
        rules = []
        for spec in STRATEGIES:
            if spec.id not in METRICS:
                continue
            label, unit, higher, fn = METRICS[spec.id]
            weights = spec.signal(daily, monthly, config.lookback_months, config.top_n, None)
            values = fn(daily, monthly, config.lookback_months)
            order = sorted(
                tickers,
                key=lambda t: (
                    (
                        pd.isna(values[t]),
                        -values[t] if higher else values[t],
                        t,
                    )
                    if not pd.isna(values[t])
                    else (True, 0.0, t)
                ),
            )
            rules.append(
                {
                    "id": spec.id,
                    "label": spec.label,
                    "family": spec.family,
                    "rule": spec.rule,
                    "metric": label,
                    "unit": unit,
                    "higher_is_better": higher,
                    "cash_weight": max(0.0, 1.0 - float(weights.sum())),
                    "history": _selection_history(spec, panel, month_ends, tickers, config),
                    "ranking": [
                        {
                            "ticker": t,
                            "rank": i + 1,
                            "value": None if pd.isna(values[t]) else float(values[t]),
                            "weight": float(weights[t]),
                        }
                        for i, t in enumerate(order)
                    ],
                }
            )
        experiments[comparison_id] = {"universe": sorted(tickers), "rules": rules}

    series = {}
    for ticker in needed:
        close = panel[ticker]
        frame = pd.DataFrame(
            {
                "close": close,
                "sma21": close.rolling(TRADING_DAYS_MONTH).mean(),
                "sma200": close.rolling(TRADING_DAYS_SMA).mean(),
            }
        ).iloc[-CHART_SESSIONS:]
        series[ticker] = {
            "dates": [d.date().isoformat() for d in frame.index],
            **{c: [None if pd.isna(x) else round(float(x), 4) for x in frame[c]] for c in frame},
        }
    return {
        "status": "available",
        "scope": "indicative_price_only",
        "as_of": as_of.isoformat(),
        "top_n": config.top_n,
        "lookback_months": config.lookback_months,
        "experiments": experiments,
        "series": series,
    }


def public_current_ranking(
    raw: dict, *, universes: dict[str, list[str]], source_hash: str, today: date
) -> dict:
    """Allowlist a pinned artifact; an expired one never reaches the page as current."""
    if raw.get("status") != "available" or raw.get("scope") != "indicative_price_only":
        return {"status": "unavailable", "reason": "Current ranking evidence is unavailable."}
    if len(source_hash) != 64 or not all(c in "0123456789abcdef" for c in source_hash):
        raise ValueError("Invalid current ranking source hash")
    as_of = date.fromisoformat(raw["as_of"])
    if as_of >= today or (today - as_of).days > MAX_AGE_DAYS:
        return {
            "status": "unavailable",
            "reason": "Current ranking expired; refresh the complete price panel.",
        }
    if set(raw["experiments"]) != set(universes):
        raise ValueError("Current ranking experiments do not match the approved universes")
    experiments = {}
    for key, tickers in universes.items():
        block = raw["experiments"][key]
        if sorted(block["universe"]) != sorted(tickers):
            raise ValueError(f"Current ranking universe mismatch: {key}")
        rules = []
        for rule in block["rules"]:
            rows = rule["ranking"]
            if sorted(r["ticker"] for r in rows) != sorted(tickers):
                raise ValueError(f"Incomplete ranking: {key}/{rule['id']}")
            if [r["rank"] for r in rows] != list(range(1, len(rows) + 1)):
                raise ValueError(f"Ranks are not consecutive: {key}/{rule['id']}")
            held = sum(r["weight"] for r in rows) + rule["cash_weight"]
            if not math.isclose(held, 1.0, abs_tol=1e-9) or any(
                r["weight"] < 0 or (r["value"] is not None and not math.isfinite(r["value"]))
                for r in rows
            ):
                raise ValueError(f"Invalid weights or values: {key}/{rule['id']}")
            hist = rule["history"]
            dates = [h["as_of"] for h in hist]
            if dates != sorted(set(dates)) or any(
                not set(h["selected"]) <= set(tickers) for h in hist
            ):
                raise ValueError(f"Invalid selection history: {key}/{rule['id']}")
            current = sorted(r["ticker"] for r in rows if r["weight"] > 0)
            if hist and (hist[-1]["as_of"] != raw["as_of"] or hist[-1]["selected"] != current):
                raise ValueError(f"History disagrees with the current ranking: {key}/{rule['id']}")
            rules.append(
                {
                    k: rule[k]
                    for k in (
                        "id",
                        "label",
                        "family",
                        "rule",
                        "metric",
                        "unit",
                        "higher_is_better",
                        "cash_weight",
                        "ranking",
                        "history",
                    )
                }
            )
        experiments[key] = {"universe": sorted(tickers), "rules": rules}
    series = {}
    for ticker, s in raw["series"].items():
        n = len(s["dates"])
        if not all(len(s[c]) == n for c in ("close", "sma21", "sma200")) or n < 2:
            raise ValueError(f"Misaligned price series: {ticker}")
        series[ticker] = {k: s[k] for k in ("dates", "close", "sma21", "sma200")}
    return {
        "status": "available",
        "scope": "indicative_price_only",
        "as_of": raw["as_of"],
        "captured_at_utc": raw["captured_at_utc"],
        "source_sha256": source_hash,
        "top_n": raw["top_n"],
        "experiments": experiments,
        "series": series,
    }
