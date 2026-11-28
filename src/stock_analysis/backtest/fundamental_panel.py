"""Point-in-time fundamental metrics for a ticker panel.

Reads the SEC CompanyFacts replay through the existing historical-visibility
loader, so a filing is visible only after its own availability clock. Only
metrics that need no share count or price are produced: split-adjusted price
bars cannot be divided by as-reported per-share values, and the stored share
basis is unverified, so earnings-yield style value ratios are deliberately not
computed here.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from stock_analysis.backtest.replay import load_fundamentals_history_replay

METRICS = ("roe", "net_margin", "fcf_margin", "debt_to_equity", "revenue_growth")
MAX_STALE_DAYS = 550  # latest fiscal year older than this is treated as unavailable


def fundamental_metrics(replay_dir: Path, tickers: list[str], as_of: date) -> pd.DataFrame:
    """Metrics knowable on ``as_of``, built from the latest annual fiscal year."""
    rows: dict[str, dict[str, float | None]] = {}
    for ticker in tickers:
        history = load_fundamentals_history_replay(replay_dir, ticker, as_of)
        annual = [r for r in history if r.period_kind == "annual" and r.fiscal_period_end]
        row: dict[str, float | None] = dict.fromkeys(METRICS)
        if annual:
            latest = max(annual, key=lambda r: r.fiscal_period_end)
            if (as_of - latest.fiscal_period_end).days <= MAX_STALE_DAYS:
                prior = [
                    r
                    for r in annual
                    if timedelta(days=300)
                    <= latest.fiscal_period_end - r.fiscal_period_end
                    <= timedelta(days=430)
                    and r.currency == latest.currency
                ]
                equity, revenue = latest.total_equity, latest.revenue
                if equity and equity > 0 and latest.net_income is not None:
                    row["roe"] = latest.net_income / equity
                    if latest.total_debt is not None:
                        row["debt_to_equity"] = latest.total_debt / equity
                if revenue and revenue > 0:
                    row["net_margin"] = latest.net_margin
                    if latest.free_cash_flow is not None:
                        row["fcf_margin"] = latest.free_cash_flow / revenue
                    if prior and prior[-1].revenue and prior[-1].revenue > 0:
                        row["revenue_growth"] = revenue / prior[-1].revenue - 1.0
        rows[ticker] = row
    return pd.DataFrame.from_dict(rows, orient="index", columns=list(METRICS)).astype(float)
