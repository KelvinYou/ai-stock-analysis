"""Audit missing buy evidence and isolate ORCL's post-hoc contribution."""
from collections import Counter
from datetime import UTC, date, datetime
from hashlib import sha256
import json
import math
from pathlib import Path
import runpy

from stock_analysis.backtest.experiment_ledger import append_experiment_record, build_experiment_record
from stock_analysis.backtest.portfolio import PortfolioConfig, _simulate_one, simulate
from stock_analysis.backtest.prospective import verify
from stock_analysis.backtest.runner import BacktestResult

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "2026-10-07-pipeline-backtest"
COHORT = HERE.parent / "2026-10-07-forward-cohort"
ns = runpy.run_path(str(HERE / "compare.py"))


def dump(name, payload):
    (HERE / name).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")


def main():
    sources = [OLD / "fundamentals-reports.json", OLD / "inputs-compact.json",
               HERE / "pipeline-10bps.json", HERE / "signal-trace.json"]
    hashes = {str(p.relative_to(HERE.parent)): sha256(p.read_bytes()).hexdigest() for p in sources}
    protocol = {"scope": "post_hoc_concentration_diagnostic_not_strategy_selection",
                "source_hashes": hashes,
                "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                "diagnostics": ["technical with the sole differing ORCL buy removed; keep full universe",
                                "exclude ORCL issuer from all candidates and strict hold; retain other seven names and all dates"],
                "cost_bps_per_side": 10,
                "forbidden": "Do not replace primary results with sensitivity results or rescore immature forward outcomes."}
    dump("audit-protocol.json", protocol)
    result = BacktestResult.model_validate(json.loads((HERE / "pipeline-10bps.json").read_text())["result"])
    traces = {(r["ticker"], r["as_of_date"]): r for r in json.loads((HERE / "signal-trace.json").read_text())}
    reports = {(r["ticker"], r["as_of_date"]): r["report"] for r in json.loads((OLD / "fundamentals-reports.json").read_text())}
    compact = {(r["ticker"], r["as_of_date"]): r for r in json.loads((OLD / "inputs-compact.json").read_text())}
    assert len(result.trials) == len(traces) == len(reports) == len(compact) == 96
    categories = Counter()
    ticker_rows = []
    reasons = []
    for ticker in sorted({t.ticker for t in result.trials}):
        bucket = Counter()
        for trial in result.trials:
            if trial.ticker != ticker:
                continue
            key = (ticker, str(trial.as_of_date))
            report, packet = reports[key], compact[key]
            assert report["signal"] == trial.agent_signals["fundamentals"]
            available = packet["evidence"]["fundamentals"]
            if not available:
                category = "unavailable_statement"
                assert report["signal"] == "neutral"
            elif report["signal"] == "neutral":
                category = "single_period_missing_valuation_and_growth"
                assert "point-in-time P/E" in report["pe_assessment"]
                assert "Only the statement" in report["growth_outlook"]
            else:
                category = "negative_cash_flow_and_leverage"
                assert ticker == "ORCL" and report["signal"] == "sell"
                assert packet["fundamentals"]["free_cash_flow"] < 0
                assert packet["fundamentals"]["total_debt"] > packet["fundamentals"]["total_equity"]
            categories[category] += 1
            bucket[category] += 1
            reasons.append({"ticker": ticker, "as_of_date": str(trial.as_of_date),
                            "category": category, "signal": report["signal"],
                            "summary": report["summary"], "financials": packet["fundamentals"]})
        ticker_rows.append({"ticker": ticker, "categories": dict(bucket)})
    augmented = result.model_copy(deep=True)
    different_buys = []
    for trial in augmented.trials:
        key = (trial.ticker, str(trial.as_of_date))
        trial.agent_signals.update(traces[key]["signals"])
        technical_buy = trial.agent_signals["technical"] in {"buy", "strong_buy"}
        ft_buy = trial.agent_signals["ft_weighted"] == "buy"
        if technical_buy != ft_buy:
            different_buys.append(key)
    assert different_buys == [("ORCL", "2026-05-29")]
    counterfactual = augmented.model_copy(deep=True)
    for trial in counterfactual.trials:
        if (trial.ticker, str(trial.as_of_date)) in different_buys:
            trial.agent_signals["technical"] = "neutral"
    config = PortfolioConfig(cost_bps_per_side=10)
    removed = _simulate_one(counterfactual, config, "technical")
    ft = _simulate_one(augmented, config, "ft_weighted")
    assert removed.trades == ft.trades
    assert math.isclose(removed.total_return_pct, ft.total_return_pct, abs_tol=1e-12)
    # Same issuer exclusion for every arm and benchmark. Not a new holdout.
    reduced = augmented.model_copy(deep=True)
    reduced.trials = [t for t in reduced.trials if t.ticker != "ORCL"]
    reduced.price_paths.pop("ORCL")
    sensitivity = simulate(reduced, config, strategies=ns["DEFAULTS"] + ns["ARMS"])
    rows = {r.strategy: r for r in sensitivity.strategies}
    assert rows["technical"].trades == rows["ft_weighted"].trades
    ledger_record = build_experiment_record(
        mode="ft-orcl-concentration-diagnostic", result=reduced.model_dump(mode="json"),
        portfolio=sensitivity.model_dump(mode="json"), cross_sectional_trial_allocation=None,
        signal_ablation=None, config=protocol, diagnostics={"research_only": True})
    ledger_record = append_experiment_record(Path("backtest_experiments.jsonl"), ledger_record)
    forward = verify(COHORT)
    cohort_snapshot = {"count": forward["count"], "signal_counts": dict(Counter(p["overall_signal"] for p in json.loads((COHORT / "predictions.json").read_text()))),
                       "entry_target": forward["entry_target"], "exit_target": forward["exit_target"],
                       "score_not_before_utc": forward["score_not_before_utc"],
                       "integrity": "PASS", "scored": False,
                       "mature_at_verification": datetime.now(UTC).date() >= date.fromisoformat(forward["score_not_before_utc"])}
    for path in sources:
        assert sha256(path.read_bytes()).hexdigest() == hashes[str(path.relative_to(HERE.parent))]
    seal = json.loads((OLD / "seal.json").read_text())
    assert all(sha256((OLD / name).read_bytes()).hexdigest() == checksum for name, checksum in seal["files"].items())
    payload = {"fundamental_categories": dict(categories), "per_ticker": ticker_rows,
               "fundamental_rows": reasons,
               "counterfactual": {"removed_technical_buy": different_buys,
                   "technical_without_one_buy_return": removed.total_return_pct,
                   "ft_weighted_return": ft.total_return_pct,
                   "all_20_trade_stakes_and_pnl_identical": True},
               "ex_orcl_sensitivity": sensitivity.model_dump(mode="json"),
               "experiment": ledger_record, "forward_cohort": cohort_snapshot,
               "verification": {"all_96_reports_categorized": True,
                                "original_107_sealed_files_unchanged": True}}
    dump("audit.json", payload)
    print(json.dumps({"fundamental_categories": dict(categories),
          "without_orcl": {name: {"return": r.total_return_pct, "trades": r.n_trades,
                                    "excess": r.excess_return_pct} for name, r in rows.items()
                           if name in {"technical", "ft_weighted", "buy_and_hold"}},
          "counterfactual_identical": True, "forward_cohort": cohort_snapshot}, indent=2))


if __name__ == "__main__":
    main()
