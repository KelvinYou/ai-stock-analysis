from datetime import date

import pandas as pd
import pytest

from stock_analysis.backtest.cross_sectional import _daily_equity_curve


def test_daily_engine_can_mark_to_latest_close_after_the_last_rebalance():
    index = pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-04"])
    opens = pd.DataFrame({"AAA": [100, 115, 120]}, index=index)
    closes = pd.DataFrame({"AAA": [110, 120, 121]}, index=index)
    targets = {date(2026, 11, 2): pd.Series({"AAA": 1.0})}
    assert _daily_equity_curve(opens, closes, targets, 0) == pytest.approx([1, 1.1])
    assert _daily_equity_curve(
        opens, closes, targets, 0, end_date=date(2026, 11, 4)
    ) == pytest.approx([1, 1.1, 1.2, 1.21])


def synthetic_prices():
    dates = pd.bdate_range("2025-01-01", "2026-11-05")
    frames = {}
    for ticker, july in [("AAA", 120), ("BBB", 110), ("CCC", 105), ("DDD", 100)]:
        f = pd.DataFrame({"date": dates, "open": 100.0, "close": 100.0})
        f.loc[f.date >= "2026-07-31", ["open", "close"]] = july
        frames[ticker] = f
    f = frames["DDD"]
    f.loc[f.date >= "2026-08-31", ["open", "close"]] = 130
    f.loc[f.date >= "2026-09-01", ["open", "close"]] = 260
    f.loc[f.date >= "2026-09-02", ["open", "close"]] = 286
    f.loc[f.date == "2026-09-02", "open"] = 260
    return frames


def test_path_uses_historical_baskets_and_next_open_not_decision_close():
    from stock_analysis.momentum_path import build_momentum_path

    result = build_momentum_path(synthetic_prices(), start=date(2026, 8, 5), end=date(2026, 9, 2))
    assert result["status"] == "available"
    assert result["cost_bps_per_side"] == 0
    assert result["rebalances"] == [
        {
            "decision_date": "2026-07-31",
            "execution_date": "2026-08-03",
            "tickers": ["AAA", "BBB", "CCC"],
        },
        {
            "decision_date": "2026-08-31",
            "execution_date": "2026-09-01",
            "tickers": ["DDD", "AAA", "BBB"],
        },
    ]
    path = {p["date"]: p["value"] for p in result["curve"]}
    assert path["2026-08-05"] == 100
    assert path["2026-08-31"] == pytest.approx(100)  # DDD's gain preceded entry.
    assert path["2026-09-01"] == pytest.approx(100)  # Entry is 260, not the 130 decision close.
    assert path["2026-09-02"] == pytest.approx(100 * (1 + 0.1 / 3))


def test_future_winner_cannot_rewrite_earlier_allocations_or_curve():
    from stock_analysis.momentum_path import build_momentum_path

    histories = synthetic_prices()
    baseline = build_momentum_path(histories, start=date(2026, 8, 5), end=date(2026, 11, 5))
    histories["CCC"].loc[histories["CCC"].date >= "2026-10-01", ["open", "close"]] = 9999
    changed = build_momentum_path(histories, start=date(2026, 8, 5), end=date(2026, 11, 5))
    assert [r for r in changed["rebalances"] if r["execution_date"] <= "2026-09-01"] == [
        r for r in baseline["rebalances"] if r["execution_date"] <= "2026-09-01"
    ]
    assert [r for r in changed["curve"] if r["date"] < "2026-10-01"] == [
        r for r in baseline["curve"] if r["date"] < "2026-10-01"
    ]


def test_missing_warmup_or_open_does_not_fabricate_a_strategy_line():
    from stock_analysis.momentum_path import build_momentum_path

    histories = synthetic_prices()
    short = {t: f[f.date >= "2025-08-06"] for t, f in histories.items()}
    assert (
        build_momentum_path(short, start=date(2026, 8, 5), end=date(2026, 11, 5))["status"]
        == "unavailable"
    )
    histories["AAA"] = histories["AAA"].drop(columns="open")
    assert (
        build_momentum_path(histories, start=date(2026, 8, 5), end=date(2026, 11, 5))["status"]
        == "unavailable"
    )


def test_dashboard_import_does_not_require_ai_or_backtest_runtime():
    import subprocess
    import sys

    source = """
import importlib.abc
import sys
class BlockHeavyRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "stock_analysis.backtest" or fullname.split(".")[0] in {"claude_agent_sdk", "pydantic_settings"}:
            raise AssertionError("Price-only dashboard imported heavy runtime: " + fullname)
sys.meta_path.insert(0, BlockHeavyRuntime())
from stock_analysis.momentum_dashboard import build_momentum_dashboard
"""
    subprocess.run([sys.executable, "-c", source], check=True)
