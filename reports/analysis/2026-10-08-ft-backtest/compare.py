"""Fixed-input, post-hoc FT ablation; run from the stock-analysis repo root."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from stock_analysis.backtest.experiment_ledger import (
    append_experiment_record, build_experiment_record,
)
from stock_analysis.backtest.portfolio import (
    PortfolioConfig, SIGNAL_TO_POSITION, simulate, to_markdown,
)
from stock_analysis.backtest.runner import BacktestResult
from stock_analysis.backtest.scorer import Scorer
from stock_analysis.models.agent_reports import Signal
from stock_analysis.synthesis.risk_checker import is_actionable

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "2026-10-07-pipeline-backtest"
ARMS = ["ft_weighted", "ft_agreement"]
WEIGHTS = {"high": 1.0, "medium": 0.75, "low": 0.5}
DEFAULTS = ["overall", "overall_fundamentals_confirmed", "fundamentals",
            "technical", "sentiment", "macro", "buy_and_hold",
            "rolling_long", "signal_timing_long"]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def derive(trial, prediction):
    # Consume guarded analyst directions only. Missing fundamentals remains
    # neutral/low in the two-role denominator, never dropped or backfilled.
    directions, weights = {}, {}
    for role in ("fundamentals", "technical"):
        directions[role] = SIGNAL_TO_POSITION[trial.agent_signals[role]]
        confidence = prediction["agent_confidences"].get(role, "medium")
        if f"evidence_unavailable:{role}" in trial.signal_gate_reasons:
            assert directions[role] == 0
            confidence = "low"
        weights[role] = WEIGHTS[confidence]
    total = sum(weights.values())
    buy = sum(weights[r] for r in weights if directions[r] == 1)
    sell = sum(weights[r] for r in weights if directions[r] == -1)
    score = round((buy - sell) / total, 4)
    convergence = round(max(buy, sell) / total, 4)
    direction = 1 if score > 0 else -1 if score < 0 else 0
    weighted = ("buy" if direction == 1 else "sell") if (
        direction and is_actionable(score, convergence)
    ) else "neutral"
    agreement = weighted if (
        directions["fundamentals"] == directions["technical"] != 0
    ) else "neutral"
    return {"ft_weighted": weighted, "ft_agreement": agreement}, score, convergence


def main():
    source_paths = [HERE / "pipeline-10bps.json", HERE / "pipeline-20bps.json",
                    OLD / "session/predictions.json", OLD / "seal.json"]
    hashes = {str(p.relative_to(HERE.parent)): digest(p) for p in source_paths}
    protocol = {
        "status": "research_only_post_hoc_on_previously_observed_outcomes",
        "input_hashes": hashes,
        "script_sha256": digest(Path(__file__)),
        "arms": ARMS,
        "weights": WEIGHTS,
        "rule": "Two-role confidence-weighted signed direction; neutral remains in denominator; reuse is_actionable consensus magnitude >0.30 and convergence >=0.40. Agreement additionally requires both directions equal and nonzero. No synthesized conviction or debate in FT arms.",
        "missing_evidence": "neutral/low; all 96 trials retained",
        "costs_bps_per_side": [0, 10, 20],
        "portfolio": "long-only, 10% of pre-session cash per signal; equal capped same-day sizing; next-session open, fixed 30-calendar-day close exit; idle cash earns zero in primary return",
        "dsr_count": 11,
        "limitations": ["Existing sample and outcomes already inspected; this rule freeze is not prospective validation.", "No fresh model/provider calls; sealed analyst forecasts reused.", "55/96 historical fundamental packets; no historical sentiment; only one-rate macro snapshots.", "Current-provider financials may be restated; survivor-selected 8-name basket; unknown model historical contamination.", "Assumed costs, unverified terminal/distribution completeness; no production limit/stop execution replay.", "DSR covers all 11 rows in this comparison, not all historical experiments."],
    }
    # Persist rule and provenance before computing the new candidate returns.
    dump(HERE / "protocol.json", protocol)
    original = json.loads((HERE / "pipeline-10bps.json").read_text())
    result = BacktestResult.model_validate(original["result"])
    predictions = {(p["ticker"], p["as_of_date"]): p for p in
                   json.loads((OLD / "session/predictions.json").read_text())}
    keys = {(t.ticker, t.as_of_date.isoformat()) for t in result.trials}
    assert len(result.trials) == len(keys) == 96
    assert keys == set(predictions)
    traces = []
    augmented = result.model_copy(deep=True)
    for trial in augmented.trials:
        signals, score, convergence = derive(
            trial, predictions[(trial.ticker, trial.as_of_date.isoformat())]
        )
        trial.agent_signals.update(signals)
        traces.append({"ticker": trial.ticker, "as_of_date": str(trial.as_of_date),
                       "signals": signals, "consensus": score,
                       "convergence": convergence,
                       "fundamentals_available": "evidence_unavailable:fundamentals" not in trial.signal_gate_reasons})
    dump(HERE / "signal-trace.json", traces)
    summaries = {}
    for cost in (0, 10, 20):
        portfolio = simulate(augmented, PortfolioConfig(cost_bps_per_side=cost),
                             strategies=DEFAULTS + ARMS)
        assert portfolio.n_strategies_tested == 11
        if cost:
            official = json.loads((HERE / f"pipeline-{cost}bps.json").read_text())
            by_name = {r.strategy: r for r in portfolio.strategies}
            for old_report in official["portfolio"]["strategies"]:
                new_report = by_name[old_report["strategy"]]
                assert new_report.total_return_pct == old_report["total_return_pct"]
                assert new_report.n_trades == old_report["n_trades"]
        scores = {}
        markdown = "# Fundamental + technical fixed-input diagnostic\n\n[Status: Warning] Exploratory post-hoc ablation. See protocol.json for rules and limits.\n\n" + to_markdown(portfolio)
        for arm in ARMS:
            view = augmented.model_copy(deep=True)
            for trial, trace in zip(view.trials, traces, strict=True):
                trial.overall_signal = Signal(trial.agent_signals[arm])
                trial.conviction_score = trace["consensus"] if trial.overall_signal != Signal.NEUTRAL else 0.0
                trial.raw_conviction_score = None
                trial.signal_convergence = trace["convergence"]
                trial.synthesized_signal = None
                trial.signal_gate_reasons = ["deterministic_ft_research_view"]
            score = Scorer.score(view, cost_bps_per_side=cost)
            scores[arm] = score.model_dump(mode="json")
            markdown += f"\n## {arm} directional diagnostic\n\nIncludes sell forecasts as hypothetical directional calls; the portfolio executes only buys. Consensus score is deterministic, not model conviction.\n\n" + Scorer.to_markdown(view, score)
        payload = portfolio.model_dump(mode="json")
        record = build_experiment_record(
            mode="ft-fixed-input-ablation", result=augmented.model_dump(mode="json"),
            portfolio=payload, cross_sectional_trial_allocation=None,
            signal_ablation=None, config={"protocol": protocol, "cost_bps_per_side": cost},
            diagnostics={"scope": "research_only_post_hoc"},
        )
        record = append_experiment_record(Path("backtest_experiments.jsonl"), record)
        dump(HERE / f"comparison-{cost}bps.json", {
            "portfolio": payload, "scores": scores, "experiment": record,
            "protocol": protocol,
        })
        (HERE / f"comparison-{cost}bps.md").write_text(markdown)
        summaries[cost] = [{k: getattr(r, k) for k in (
            "strategy", "total_return_pct", "excess_return_pct", "max_drawdown_pct",
            "n_trades", "effective_n", "deflated_sharpe", "strict_hold_log_excess_ci_95",
            "matched_exposure_excess_pct", "mean_committed_principal_pct",
        )} for r in portfolio.strategies if r.strategy in ["overall", *ARMS, "fundamentals", "technical", "buy_and_hold"]]
    for path in source_paths:
        assert digest(path) == hashes[str(path.relative_to(HERE.parent))]
    seal = json.loads((OLD / "seal.json").read_text())
    assert all(digest(OLD / name) == checksum for name, checksum in seal["files"].items())
    dump(HERE / "summary.json", {"costs": summaries,
         "signals": {a: dict(Counter(t["signals"][a] for t in traces)) for a in ARMS},
         "verification": {"original_sealed_files_unchanged": len(seal["files"]),
                          "complete_trials": 96, "existing_strategy_returns_match": True,
                          "original_scored_inputs_unchanged": True}})
    print(json.dumps(summaries[10], indent=2))


if __name__ == "__main__":
    main()
