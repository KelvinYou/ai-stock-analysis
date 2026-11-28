"""Strategy comparison contracts use synthetic prices, never owner data."""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pandas as pd

from stock_analysis.backtest.cross_sectional import (
    CrossSectionalConfig,
    run_cross_sectional_backtest,
)
from stock_analysis.backtest.strategy_comparison import (
    STRATEGIES,
    StrategyComparisonConfig,
    run_strategy_comparison,
)


def _histories(seed: int = 7, days: int = 900) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2019-01-01", periods=days)
    out = {}
    for i, name in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE"]):
        close = 100 * np.cumprod(1 + rng.normal(0.0004 * (i + 1), 0.012 + 0.003 * i, days))
        out[name] = pd.DataFrame(
            {
                "date": index,
                "open": close * 0.999,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000,
            }
        )
    return out


def test_every_rule_is_long_only_and_search_width_is_counted():
    report = run_strategy_comparison(_histories())
    assert report.n_strategies_tested == len(STRATEGIES) == len(report.strategies)
    for result in report.strategies:
        assert all(0.0 <= p.exposure <= 1.0 + 1e-9 for p in result.period_log)
        assert len(report.curves[result.id]) == len(report.curve_dates)
    assert report.benchmark.mean_exposure == 1.0


def test_momentum_arm_reconciles_with_existing_allocator():
    histories = _histories()
    comparison = run_strategy_comparison(
        histories, config=StrategyComparisonConfig(cost_bps_per_side=20)
    )
    start = comparison.oos_start
    allocator = run_cross_sectional_backtest(
        histories, start=start, config=CrossSectionalConfig(cost_bps_per_side=20)
    )
    ours = next(s for s in comparison.strategies if s.id == "momentum_12m")
    assert abs(ours.net_compound_return - allocator.net_compound_return) < 1e-9
    assert abs(comparison.benchmark.net_compound_return - allocator.buy_and_hold_return) < 1e-9


def test_signals_ignore_prices_after_the_decision_date():
    base = _histories()
    cutoff = pd.Timestamp("2021-06-30")
    changed = {}
    for name, frame in base.items():
        copy = frame.copy()
        later = copy["date"] > cutoff
        copy.loc[later, ["open", "high", "low", "close"]] *= 3.0  # a future shock
        changed[name] = copy
    a = run_strategy_comparison(base, end=cutoff.date())
    b = run_strategy_comparison(changed, end=cutoff.date())
    for x, y in zip(a.strategies, b.strategies, strict=True):
        # Selections made on or before the cutoff cannot depend on later prices.
        assert [p.selected_tickers for p in x.period_log[:-1]] == [
            p.selected_tickers for p in y.period_log[:-1]
        ], x.id


def _fund_row(end: str, filed: str, revenue: float, net_income: float) -> dict:
    return {
        "ticker": "AAA",
        "fiscal_period_start": f"{int(end[:4]) - 1}-{end[5:]}",
        "fiscal_period_end": end,
        "period_kind": "annual",
        "available_as_of": filed,
        "availability_source": "sec_companyfacts",
        "currency": "USD",
        "revenue": revenue,
        "net_income": net_income,
        "total_equity": 500.0,
        "total_debt": 100.0,
        "free_cash_flow": net_income,
        "net_margin": net_income / revenue,
    }


def test_fundamentals_are_invisible_before_their_filing_date(tmp_path):
    import json
    from datetime import date

    from stock_analysis.backtest.fundamental_panel import fundamental_metrics

    folder = tmp_path / "fundamentals"
    folder.mkdir()
    rows = [
        _fund_row("2019-12-31", "2020-02-15", 1000.0, 100.0),
        _fund_row("2020-12-31", "2021-02-15", 1500.0, 300.0),
    ]
    (folder / "AAA.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    before = fundamental_metrics(tmp_path, ["AAA"], date(2021, 1, 31))
    after = fundamental_metrics(tmp_path, ["AAA"], date(2021, 3, 31))
    assert before.loc["AAA", "net_margin"] == 0.1  # FY2020 was not yet public
    assert before["revenue_growth"].isna().all()
    assert after.loc["AAA", "net_margin"] == 0.2
    assert abs(after.loc["AAA", "revenue_growth"] - 0.5) < 1e-12


def test_fundamental_rules_run_and_are_counted_in_the_search(tmp_path):
    import json

    histories = _histories()
    folder = tmp_path / "fundamentals"
    folder.mkdir()
    for i, name in enumerate(histories):
        rows = [
            {
                **_fund_row(f"{y}-12-31", f"{y + 1}-02-15", 1000.0 * (1 + 0.1 * i), 50.0 * (i + 1)),
                "ticker": name,
            }
            for y in (2018, 2019, 2020, 2021)
        ]
        (folder / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    price_only = run_strategy_comparison(histories)
    full = run_strategy_comparison(histories, fundamentals_dir=tmp_path)
    assert full.n_strategies_tested == price_only.n_strategies_tested + 6
    # Adding rules must not change an existing rule's result.
    assert (
        next(s for s in full.strategies if s.id == "momentum_12m").net_compound_return
        == next(s for s in price_only.strategies if s.id == "momentum_12m").net_compound_return
    )


def test_holdings_are_unbroken_stays_priced_at_the_fill_open():
    histories = _histories()
    report = run_strategy_comparison(histories)
    opens = {t: f.set_index("date")["open"] for t, f in histories.items()}
    for result in report.strategies:
        stays = result.holdings
        for h in stays:
            assert h.entry_date < h.exit_date and h.days_held == (h.exit_date - h.entry_date).days
            assert abs(h.entry_price - float(opens[h.ticker][pd.Timestamp(h.entry_date)])) < 1e-9
            assert abs(h.exit_price - float(opens[h.ticker][pd.Timestamp(h.exit_date)])) < 1e-9
            assert abs(h.price_return - (h.exit_price / h.entry_price - 1)) < 1e-12
        # A name cannot be held twice at once.
        for ticker in {h.ticker for h in stays}:
            spans = sorted((h.entry_date, h.exit_date) for h in stays if h.ticker == ticker)
            assert all(a[1] <= b[0] for a, b in pairwise(spans)), result.id
        # Only the last scheduled exit is a forced liquidation.
        ends = {h.exit_date for h in stays if h.exit_reason == "backtest_end"}
        assert len(ends) <= 1
    momentum = next(s for s in report.strategies if s.id == "momentum_12m")
    selected = [set(p.selected_tickers) for p in momentum.period_log]
    entries = sum(len(b - a) for a, b in zip([set(), *selected[:-1]], selected, strict=True))
    assert len(momentum.holdings) == entries  # every entry has exactly one matching exit


def test_sell_buffer_rule_keeps_holdings_and_trades_less():
    from stock_analysis.backtest.strategy_comparison import STRATEGIES

    specs = tuple(s for s in STRATEGIES if s.id in {"ma_distance", "ma_distance_buffer"})
    report = run_strategy_comparison(_histories(), config=StrategyComparisonConfig(), specs=specs)
    rows = {r.id: r for r in report.strategies}
    assert report.n_strategies_tested == 2
    assert (
        rows["ma_distance_buffer"].mean_monthly_turnover
        <= rows["ma_distance"].mean_monthly_turnover
    )
