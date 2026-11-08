"""Capture and replay a fixed allocator versus VT; no parameter optimization.

Run with --fetch once, then rerun offline without that flag. All prices are a
current provider vintage, not a historical availability or total-return proof.
"""

from datetime import UTC, date, datetime
import hashlib
import json
import math
from pathlib import Path
import sys

import pandas as pd

from stock_analysis.allocation_snapshot import build_current_momentum
from stock_analysis.backtest.cross_sectional import CrossSectionalConfig, run_cross_sectional_backtest
from stock_analysis.backtest import stats

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
NAMES = ["AVGO", "COST", "MSFT", "NVDA", "ORCL", "TSM", "UNH", "V"]
SCENARIOS = [(20, 3), (40, 3), (80, 3), (20, 6), (20, 12)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prices = OUT / "prices"
    prices.mkdir(exist_ok=True)
    if "--fetch" in sys.argv:
        import yfinance as yf
        for name in [*NAMES, "VT"]:
            frame = yf.Ticker(name).history(start="2016-01-01", end="2026-10-27", auto_adjust=True, actions=False)
            if frame.empty:
                raise ValueError(f"No data: {name}")
            frame.index = frame.index.tz_localize(None).normalize()
            frame.index.name = "date"
            frame.rename(columns=str.lower).to_csv(prices / f"{name}.csv", date_format="%Y-%m-%d")
            print(f"Captured {name}: {len(frame)} bars", flush=True)
        protocol = {"captured_at_utc": datetime.now(UTC).isoformat(),
                    "scope": "post_hoc_current_provider_vintage_research_only",
                    "universe": NAMES, "reference": "VT", "lookback_months": 12, "top_n": 3,
                    "signal_start": "2018-01-01", "signal_end": "2026-08-14",
                    "scenarios_cost_bps_and_block_months": SCENARIOS,
                    "costs": "assumed_proportional_not_broker_calibrated",
                    "hashes": {n: sha(prices / f"{n}.csv") for n in [*NAMES, "VT"]}}
        (OUT / "vt-protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    protocol = json.loads((OUT / "vt-protocol.json").read_text())
    assert protocol["scenarios_cost_bps_and_block_months"] == [list(r) for r in SCENARIOS]
    histories = {}
    for name, expected in protocol["hashes"].items():
        path = prices / f"{name}.csv"
        assert sha(path) == expected
        histories[name] = pd.read_csv(path)
    snapshot = build_current_momentum({n: histories[n] for n in NAMES}, today=date(2026, 10, 27))
    snapshot["captured_at_utc"] = protocol["captured_at_utc"]
    snapshot["price_source"] = "Yahoo Finance adjusted prices; same captured vintage"
    snapshot["input_hashes"] = {n: protocol["hashes"][n] for n in NAMES}
    (OUT / "current-momentum.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    vt = histories["VT"].set_index("date")
    results = []
    for bps, block in SCENARIOS:
        report = run_cross_sectional_backtest(
            {n: histories[n] for n in NAMES}, start=date(2018, 1, 1), end=date(2026, 8, 14),
            config=CrossSectionalConfig(cost_bps_per_side=bps, bootstrap_block_periods=block))
        rate = bps / 10000
        periods = report.period_log
        returns = []
        for i, p in enumerate(periods):
            gross = float(vt.loc[str(p.exit_date), "open"] / vt.loc[str(p.entry_date), "open"])
            factor = gross * ((1-rate) if i == 0 else 1) * ((1-rate) if i == len(periods)-1 else 1)
            returns.append(factor - 1)
        first, last = str(periods[0].entry_date), str(periods[-1].exit_date)
        terminal = float(vt.loc[last, "open"] / vt.loc[first, "open"]) * (1-rate)**2
        assert math.isclose(math.prod(1+r for r in returns), terminal, abs_tol=1e-10)
        daily = (vt.loc[first:last, "close"] / vt.loc[first, "open"] * (1-rate)).tolist()
        daily[-1] = terminal  # Final liquidation is at Open, not that session's Close.
        peak, drawdown = 1.0, 0.0
        for value in [1.0, *daily]:
            peak = max(peak, value)
            drawdown = min(drawdown, value / peak - 1)
        excess = [math.log1p(p.net_return) - math.log1p(r) for p, r in zip(periods, returns, strict=True)]
        result = {"cost_bps_per_side": bps, "block_months": block,
                  "entry_date": first, "exit_date": last, "periods": report.periods,
                  "effective_n": report.effective_n,
                  "allocator_net_return": report.net_compound_return,
                  "eight_stock_hold_net_return": report.buy_and_hold_return,
                  "vt_net_return": terminal-1, "allocator_max_drawdown": report.max_drawdown,
                  "vt_max_drawdown": drawdown,
                  "mean_monthly_paired_log_excess_ci_95": stats.moving_block_bootstrap_ci(
                      excess, block_length=block, n_resamples=2000, seed=0),
                  "promotion_ready": False,
                  "period_log": [{"entry_date": str(p.entry_date), "exit_date": str(p.exit_date),
                                  "allocator_return": p.net_return, "vt_return": r}
                                 for p,r in zip(periods,returns,strict=True)]}
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k != "period_log"}), flush=True)
    (OUT / "vt-comparison.json").write_text(json.dumps({"protocol": protocol, "scenarios": results,
        "limits": ["Fixed survivor-selected eight-name allocator; VT is a different universe",
                   "All history inspected; no new holdout or full-search DSR pass",
                   "Provider adjusted returns and assumed fees; no verified investor-net total returns",
                   "Cash yield zero; USD only, no personal balances or FX P&L"],
        "promotion_ready": False}, indent=2) + "\n")


if __name__ == "__main__":
    main()
