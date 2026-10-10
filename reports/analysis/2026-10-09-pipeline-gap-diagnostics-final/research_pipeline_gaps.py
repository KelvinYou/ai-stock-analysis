"""Offline refusal and allocator diagnostics on frozen forecasts, never trading advice."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

import pandas as pd

from stock_analysis.backtest import stats
from stock_analysis.backtest.cross_sectional import (
    CrossSectionalConfig,
    run_cross_sectional_trial_backtest,
)
from stock_analysis.backtest.experiment_ledger import (
    append_experiment_record,
    build_experiment_record,
)
from stock_analysis.backtest.main import _nonoverlapping_trial_subset
from stock_analysis.backtest.portfolio import PortfolioConfig, simulate
from stock_analysis.backtest.runner import BacktestResult
from stock_analysis.backtest.signal_ablation import SignalAblationConfig, run_signal_ablation
from stock_analysis.models.agent_reports import Signal

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/analysis"
FINAL = REPORTS / "2026-10-09-backtest-rerun-final"
SOURCE = REPORTS / "2026-10-08-ft-backtest/pipeline-10bps.json"
PREDICTIONS = REPORTS / "2026-10-07-pipeline-backtest/session/predictions.json"
BASE_ARMS = [
    "overall", "overall_fundamentals_confirmed", "fundamentals", "technical",
    "sentiment", "macro", "buy_and_hold", "rolling_long", "signal_timing_long",
    "ft_weighted", "ft_agreement",
]
RAW_ARM = "raw_buy_without_guards_counterfactual"
BUY = {Signal.BUY, Signal.STRONG_BUY}
SELL = {Signal.SELL, Signal.STRONG_SELL}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def refusal_partition(raw: Signal, executed: Signal) -> str:
    """One partition per call; reason codes remain overlapping diagnostics."""
    if raw == Signal.NEUTRAL:
        if executed != Signal.NEUTRAL:
            raise ValueError("A guard cannot turn a neutral source into a directional call")
        return "raw_neutral"
    if executed != Signal.NEUTRAL:
        if (raw in BUY) != (executed in BUY):
            raise ValueError("A guard cannot reverse the raw forecast direction")
        return "buy_passed_guards" if raw in BUY else "sell_passed_guards_long_only_skip"
    return "raw_buy_declined" if raw in BUY else "raw_sell_declined"


def gap_decomposition(candidate: float, matched: float | None, hold: float) -> dict:
    """An exact accounting identity, not a causal estimate of market timing."""
    return {
        "total_excess_vs_hold": candidate - hold,
        "selection_vs_matched": None if matched is None else candidate - matched,
        "deployment_and_timing_vs_hold": None if matched is None else matched - hold,
        "unattributed_no_exposure": matched is None,
    }


def compound(values: list[float]) -> float:
    return math.prod(1 + value for value in values) - 1


def paired_ci(candidate: list[float], baseline: list[float]) -> tuple | None:
    values = [math.log1p(a) - math.log1p(b) for a, b in zip(candidate, baseline, strict=True)]
    return stats.moving_block_bootstrap_ci(
        values, block_length=3, n_resamples=2000, seed=0,
    )


def episode_summary(series: dict[str, list[float]], n_eff: float) -> list[dict]:
    """Count every episode row in DSR; no annualization of a nine-period panel."""
    sharpes = {
        name: statistics.mean(values) / statistics.stdev(values)
        for name, values in series.items()
        if len(values) >= 2 and statistics.stdev(values) > 0
    }
    variance = statistics.variance(sharpes.values()) if len(sharpes) > 1 else 0.0
    allocator = series["allocator_only"]
    passive = series["scheduled_passive"]
    rows = []
    for name, values in series.items():
        sr = sharpes.get(name)
        dsr = None if sr is None else stats.deflated_sharpe_ratio(
            sr, int(n_eff), stats.skewness(values), stats.kurtosis(values),
            n_strategies=len(series), sr_variance=variance,
        )
        rows.append({
            "strategy": name, "net_return": compound(values), "effective_n": n_eff,
            "excess_vs_allocator": compound(values) - compound(allocator),
            "excess_vs_scheduled_passive": compound(values) - compound(passive),
            "allocator_paired_log_ci_95": paired_ci(values, allocator),
            "passive_paired_log_ci_95": paired_ci(values, passive),
            "deflated_sharpe": dsr, "n_strategies_tested": len(series),
        })
    return rows


def episode_experiment(result: BacktestResult, histories: dict, cost: int) -> dict:
    subset, dates = _nonoverlapping_trial_subset(result.trials)
    allocator = run_cross_sectional_trial_backtest(
        {ticker: pd.DataFrame(rows) for ticker, rows in histories.items()}, subset,
        config=CrossSectionalConfig(lookback_months=12, top_n=3, cost_bps_per_side=cost),
    )
    series = {
        "allocator_only": [p.net_return for p in allocator.period_log],
        "scheduled_passive": [p.matched_passive_net_return for p in allocator.period_log],
    }
    reports = {}
    checks = 0
    for label, field in [("ai", "overall"), ("ft_weighted", "ft_weighted"),
                         ("ft_agreement", "ft_agreement")]:
        view = [t.model_copy(deep=True) for t in subset]
        for trial in view:
            if field != "overall":
                trial.overall_signal = Signal(trial.agent_signals[field])
                # FT-only ties use deterministic symbol order, never AI conviction.
                trial.conviction_score = 1.0 if trial.overall_signal in BUY else 0.0
        report = run_signal_ablation(
            view, allocator.period_log,
            config=SignalAblationConfig(top_n=3, cost_bps_per_side=cost),
        )
        payload = report.model_dump(mode="json")
        payload["label_source"] = field
        payload["interpretation"] = "AI-named fields refer to the chosen fixed label source"
        if report.ai_only.mean_exposure == 0:
            payload["ai_only"]["paired_log_excess_ci_95"] = None
        if report.hybrid.mean_exposure == 0:
            payload["hybrid"]["paired_log_excess_ci_95"] = None
        reports[label] = payload
        series[f"{label}_only"] = [p.ai_only_net_return for p in report.period_log]
        series[f"allocator_plus_{label}"] = [p.hybrid_net_return for p in report.period_log]
        by_key = {(t.ticker, t.as_of_date): t for t in view}
        for period in report.period_log:
            # Independent reconciliation uses frozen outcomes only after selection.
            for names, actual in [
                (period.allocator_selected_tickers, period.allocator_net_return),
                (period.ai_only_selected_tickers, period.ai_only_net_return),
                (period.hybrid_selected_tickers, period.hybrid_net_return),
            ]:
                expected = sum(
                    ((1 + by_key[(name, period.as_of_date)].realized_return)
                     * (1 - cost / 10000) ** 2 - 1) / 3 for name in names
                )
                assert math.isclose(actual, expected, abs_tol=1e-12)
                checks += 1
    summaries = episode_summary(series, allocator.effective_n)
    for row in summaries:
        row["excess_vs_continuous_strict_hold"] = row["net_return"] - allocator.buy_and_hold_return
    return {
        "scope": "post_hoc_nonoverlap_episode_diagnostic_not_monthly_live_strategy",
        "selected_dates": [str(day) for day in dates], "selected_trials": len(subset),
        "total_trials": len(result.trials), "allocator": allocator.model_dump(mode="json"),
        "signal_views": reports, "period_returns": series, "summary": summaries,
        "independent_return_checks": checks,
        "strict_hold_note": "Continuous hold on exact outer dates; idle episode gaps differ",
        "cost_note": "Multiplicative entry/exit episode fees; full-panel simulator uses additive trade costs",
        "limits": "N<30, endpoint drawdown, fixed surviving names, assumed costs, inspected outcomes; no promotion",
    }


def run(output: Path) -> dict:
    paths = [FINAL / "result.json", FINAL / "signal-trace.json", SOURCE, PREDICTIONS,
             REPORTS / "2026-10-07-pipeline-backtest/seal.json"]
    paths += list((ROOT / "src/stock_analysis").rglob("*.py"))
    paths.append(Path(__file__).resolve())
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    output.mkdir(parents=True, exist_ok=False)
    # Preserve the exact runner even when later research versions change the script.
    (output / "research_pipeline_gaps.py").write_bytes(Path(__file__).read_bytes())
    protocol = {
        "status": "research_only_post_hoc", "input_and_code_hashes": hashes,
        "costs_bps_per_side": [0, 10, 20], "new_model_calls": 0, "new_price_fetches": 0,
        "full_panel_arms": [*BASE_ARMS, RAW_ARM], "episode_arms": 8,
        "allocator": {"lookback_months": 12, "top_n": 3},
        "subset_rule": "Existing earliest-feasible complete date windows; no returns used",
        "ft_ties": "All executable FT buys equal strength; lexical symbol ties; no AI conviction",
        "counterfactual": "Raw original BUY only, all deterministic guards bypassed for diagnosis",
        "reason_codes": "Overlapping correlations; never sum as independent causes",
        "hypotheses": ["Guard refusal missed profitable raw buys",
                       "FT or AI improves a fixed momentum basket at matched exposure"],
        "selection_bias": "DSR counts 12 full-panel and 8 episode rows separately; all historical search not reconstructed",
        "promotion_allowed": False,
    }
    write_json(output / "protocol.json", protocol)
    result = BacktestResult.model_validate_json((FINAL / "result.json").read_text())
    predictions = {(p["ticker"], p["as_of_date"]): p
                   for p in json.loads(PREDICTIONS.read_text())}
    trace = {(p["ticker"], p["as_of_date"]): p
             for p in json.loads((FINAL / "signal-trace.json").read_text())}
    keys = {(t.ticker, str(t.as_of_date)) for t in result.trials}
    assert len(keys) == len(result.trials) == len(predictions) == len(trace) == 96
    assert keys == set(predictions) == set(trace)
    groups, reasons, audit_rows = Counter(), Counter(), []
    for trial in result.trials:
        key = (trial.ticker, str(trial.as_of_date))
        raw = Signal(predictions[key]["overall_signal"])
        assert trial.synthesized_signal == raw
        partition = refusal_partition(raw, trial.overall_signal)
        groups[partition] += 1
        reasons.update(trial.signal_gate_reasons)
        trial.agent_signals[RAW_ARM] = raw.value
        audit_rows.append({
            "ticker": trial.ticker, "as_of_date": str(trial.as_of_date),
            "raw_signal": raw.value, "executed_signal": trial.overall_signal.value,
            "partition": partition, "gate_reasons": trial.signal_gate_reasons,
            "ft_risk_note": trace[key]["risk_decline_note"],
            "realized_long_return": trial.realized_return,
        })
    write_json(output / "refusal-trace.json", audit_rows)
    histories = json.loads(SOURCE.read_text())["allocator_price_histories"]
    result_payload = result.model_dump(mode="json")
    summary = {"partitions": dict(groups), "overlapping_reasons": dict(reasons), "costs": {}}
    reverse = result.model_copy(deep=True)
    reverse.trials.reverse()
    independent_checks = 0
    for cost in protocol["costs_bps_per_side"]:
        report = simulate(result, PortfolioConfig(cost_bps_per_side=cost),
                          strategies=protocol["full_panel_arms"])
        reversed_report = simulate(reverse, PortfolioConfig(cost_bps_per_side=cost),
                                   strategies=protocol["full_panel_arms"])
        assert [(r.strategy, r.total_return_pct) for r in report.strategies] == [
            (r.strategy, r.total_return_pct) for r in reversed_report.strategies
        ]
        hold = next(r for r in report.strategies if r.strategy == "buy_and_hold")
        gaps = []
        for row in report.strategies:
            if row.strategy not in {"overall", "ft_weighted", "ft_agreement", RAW_ARM}:
                continue
            gaps.append({
                "strategy": row.strategy, "net_return": row.total_return_pct,
                "n_trades": row.n_trades, "effective_n": row.effective_n,
                "deflated_sharpe": row.deflated_sharpe,
                "hold_paired_log_ci_95": row.strict_hold_log_excess_ci_95,
                "mean_committed_principal": row.mean_committed_principal_pct,
                **gap_decomposition(row.total_return_pct,
                                    row.matched_exposure_baseline_return_pct, hold.total_return_pct),
            })
        episodes = episode_experiment(result, histories, cost)
        independent_checks += episodes["independent_return_checks"]
        reversed_episodes = episode_experiment(reverse, histories, cost)
        assert episodes == reversed_episodes
        record = build_experiment_record(
            mode="frozen-pipeline-gap-diagnostics", result=result_payload,
            portfolio=report.model_dump(mode="json"),
            cross_sectional_trial_allocation=episodes["allocator"],
            signal_ablation=episodes["signal_views"]["ai"],
            config={"protocol": protocol, "cost_bps_per_side": cost},
            diagnostics={"episode_arms_tested": 8, "additional_ft_ablation": True,
                         "promotion_allowed": False},
        )
        append_experiment_record(output / "experiments.jsonl", record)
        write_json(output / f"diagnostics-{cost}bps.json", {
            "portfolio": report.model_dump(mode="json"), "gap_decomposition": gaps,
            "episodes": episodes,
        })
        summary["costs"][str(cost)] = {"full_panel": gaps, "episodes": episodes["summary"]}
    assert result.model_dump(mode="json") == result_payload
    for name, checksum in hashes.items():
        assert digest(ROOT / name) == checksum
    seal = json.loads((REPORTS / "2026-10-07-pipeline-backtest/seal.json").read_text())
    old = REPORTS / "2026-10-07-pipeline-backtest"
    assert all(digest(old / name) == checksum for name, checksum in seal["files"].items())
    write_json(output / "summary.json", summary)
    write_json(output / "verification.json", {
        "input_and_code_hashes_unchanged": True, "original_sealed_files": len(seal["files"]),
        "full_panel_order_invariance": True, "episode_order_invariance": True,
        "independent_episode_return_checks": independent_checks,
        "new_forecasts": 0, "new_price_fetches": 0,
        "promotion_allowed": False,
    })
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
