"""Offline audit of frozen allocation evidence; run from the child repo root.

Command: .venv/bin/python reports/analysis/2026-10-27-allocation-revalidation/reproduce.py
No parameter search, network calls, old-artifact writes or promotion authority.
"""

from datetime import date
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pandas as pd

from stock_analysis.backtest.cross_sectional import (
    CrossSectionalConfig,
    run_cross_sectional_backtest,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = ROOT / "reports/analysis/2026-10-09-momentum-validation-extended"
SOURCE = ROOT / "reports/analysis/2026-10-09-momentum-reliability/return-source-audit-network"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((OLD / "protocol.json").read_text())
    histories, source_hashes = {}, {}
    for symbol in protocol["panels"]:
        path = SOURCE / f"{symbol}-unadjusted-actions.csv"
        expected = next(v for k, v in protocol["input_hashes"].items()
                        if k.endswith(f"/{path.name}"))
        assert digest(path) == expected, f"Changed frozen source: {symbol}"
        source_hashes[str(path.relative_to(ROOT))] = expected
        frame = pd.read_csv(path)
        ratio = frame["Adj Close"] / frame["Close"]
        histories[symbol] = pd.DataFrame({
            "date": frame.iloc[:, 0].str[:10],
            "open": frame.Open * ratio,
            "close": frame["Adj Close"],
        })

    # Reuse all declared current-vintage scenarios; never select a winning setting.
    scenarios = []
    reports = []
    for run in protocol["runs"]:
        if run["snapshot"] != "current_adjusted":
            continue
        key = f"current_adjusted-{run['cost_bps']}bps-block{run['bootstrap_block_months']}"
        prior = json.loads((OLD / f"{key}.json").read_text())
        report = run_cross_sectional_backtest(
            histories, start=date.fromisoformat(protocol["signal_dates"][0]),
            end=date.fromisoformat(protocol["signal_dates"][1]),
            config=CrossSectionalConfig(**prior["config"]),
        ).model_dump(mode="json")
        # Compare the complete report, including every selection, fee, CI and daily DD.
        assert report == prior, f"Full report drift: {key}"
        rows = report["period_log"]
        for row in rows:
            assert row["as_of_date"] < row["entry_date"] < row["exit_date"]
        for field, terminal in (("net_return", "net_compound_return"),
                                ("strict_hold_net_return", "buy_and_hold_return")):
            value = math.prod(1 + row[field] for row in rows) - 1
            assert math.isclose(value, report[terminal], abs_tol=1e-10)
        ci = report["strict_hold_log_excess_ci_95"]
        scenarios.append({
            "id": key, "full_report_matches": True,
            **{k: report[k] for k in (
                "periods", "effective_n", "net_compound_return", "buy_and_hold_return",
                "max_drawdown", "buy_and_hold_max_drawdown", "strict_hold_log_excess_ci_95",
            )},
            "positive_lower_ci": ci[0] > 0,
        })
        reports.append(report)
        print(f"PASS full frozen-report replay: {key}", flush=True)

    # Independently recompute concentration on the current 20bps primary series.
    primary = reports[0]
    ranked = sorted(primary["period_log"], key=lambda p:
                    math.log1p(p["net_return"]) - math.log1p(p["strict_hold_net_return"]),
                    reverse=True)
    remaining = ranked[3:]
    concentration = {
        "scope": "post_hoc_sensitivity_not_an_executable_strategy",
        "omitted_best_excess_months": 3,
        "allocator_return": math.prod(1 + p["net_return"] for p in remaining) - 1,
        "hold_return": math.prod(1 + p["strict_hold_net_return"] for p in remaining) - 1,
    }

    # Validate hashes and reconciliation for every published experiment without exporting.
    spec = importlib.util.spec_from_file_location("allocation_export", ROOT / "scripts/export_allocation_research.py")
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    published = exporter.export()
    checked_sources = {
        str(path.relative_to(ROOT)): digest(path)
        for path in [OLD / "protocol.json", ROOT / "config/allocation_research.json",
                     ROOT / "src/stock_analysis/backtest/cross_sectional.py",
                     ROOT / "src/stock_analysis/backtest/stats.py",
                     ROOT / "src/stock_analysis/portfolio_cohort.py"]
    }
    result = {
        "scope": "frozen_historical_reproduction_not_fresh_out_of_sample",
        "reliability_status": "Unconfirmed", "promotion_ready": False,
        "source_hashes": source_hashes, "implementation_and_protocol_hashes": checked_sources,
        "scenarios": scenarios, "concentration": concentration,
        "published_experiments_verified": len(published["experiments"]),
        "all_declared_current_vintage_intervals_span_zero": all(
            r["strict_hold_log_excess_ci_95"][0] <= 0 <= r["strict_hold_log_excess_ci_95"][1]
            for r in scenarios),
        "unresolved_gates": [
            "positive_paired_excess_interval_on_locked_unseen_sample",
            "full_prior_search_correction", "broker_calibrated_costs",
            "verified_distributions_taxes_and_terminal_returns",
            "survivor_universe_generalization", "activated_mature_matching_schedule_forward_cohort",
        ],
    }
    for path, expected in source_hashes.items():
        assert digest(ROOT / path) == expected
    (OUT / "verification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print("Audit complete; reliability remains Unconfirmed.")


if __name__ == "__main__":
    main()
