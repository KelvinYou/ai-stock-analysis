"""Independent artifact checks, without generating predictions or resampling."""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import runpy

from stock_analysis.backtest.experiment_ledger import _read_and_validate_ledger
from stock_analysis.backtest.portfolio import PortfolioConfig, _simulate_one
from stock_analysis.backtest.runner import BacktestResult

HERE = Path(__file__).resolve().parent
namespace = runpy.run_path(str(HERE / "compare.py"))
source = json.loads((HERE / "pipeline-10bps.json").read_text())
result = BacktestResult.model_validate(source["result"])
traces = json.loads((HERE / "signal-trace.json").read_text())
trace_lookup = {(r["ticker"], r["as_of_date"]): r for r in traces}
original_lookup = {(t.ticker, str(t.as_of_date)): t for t in result.trials}
reversed_result = result.model_copy(deep=True)
reversed_result.trials.reverse()
for trial in reversed_result.trials:
    trace = trace_lookup[(trial.ticker, str(trial.as_of_date))]
    trial.agent_signals.update(trace["signals"])
    assert trial.entry_date > trial.as_of_date
    assert trial.exit_date >= trial.entry_date
    if not trace["fundamentals_available"]:
        assert trial.agent_signals["fundamentals"] == "neutral"
        assert trace["signals"]["ft_agreement"] == "neutral"

checked_trades = 0
for cost in (0, 10, 20):
    scored = json.loads((HERE / f"comparison-{cost}bps.json").read_text())
    assert scored["portfolio"]["n_strategies_tested"] == 11
    for row in scored["portfolio"]["strategies"]:
        if row["strategy"] not in namespace["ARMS"]:
            continue
        # Permute the whole panel: same-day sizing must not depend on ticker order.
        rerun = _simulate_one(reversed_result, PortfolioConfig(cost_bps_per_side=cost), row["strategy"])
        assert math.isclose(rerun.total_return_pct, row["total_return_pct"], abs_tol=1e-12)
        for trade in row["trades"]:
            trial = next(t for t in result.trials if t.ticker == trade["ticker"] and str(t.entry_date) == trade["entry_date"])
            trace = trace_lookup[(trial.ticker, str(trial.as_of_date))]
            assert trace["signals"][row["strategy"]] == "buy"
            assert trade["direction"] == 1
            expected_return = trial.exit_price / trial.entry_price - 1 - 2 * cost / 10_000
            assert math.isclose(trade["return_pct"], expected_return, abs_tol=1e-12)
            assert math.isclose(trade["pnl"], trade["stake"] * expected_return, abs_tol=1e-8)
            checked_trades += 1
        assert math.isclose(row["final_balance"], 10_000 + sum(t["pnl"] for t in row["trades"]), abs_tol=1e-8)

protocol = json.loads((HERE / "protocol.json").read_text())
for path, checksum in protocol["input_hashes"].items():
    assert sha256((HERE.parent / path).read_bytes()).hexdigest() == checksum
assert sha256((HERE / "compare.py").read_bytes()).hexdigest() == protocol["script_sha256"]
descriptor = os.open("backtest_experiments.jsonl", os.O_RDONLY)
try:
    ledger_rows = _read_and_validate_ledger(descriptor)
finally:
    os.close(descriptor)
verification = {
    "status": "PASS", "ft_trade_cost_and_pnl_checks": checked_trades,
    "reversed_trial_order_identical_returns": True,
    "no_long_trade_from_missing_fundamental_agreement": True,
    "input_and_script_hashes_match": True,
    "ledger_hash_chain_rows_validated": len(ledger_rows),
}
(HERE / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
print(json.dumps(verification, indent=2))
