import json
from pathlib import Path

import pytest

from stock_analysis.backtest.experiment_ledger import (
    append_experiment_record,
    build_experiment_record,
    build_standalone_record,
)


def _sample_inputs(source_root: Path, session_dir: Path | None = None):
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "pipeline.py").write_text("SIGNAL_VERSION = 1\n")
    result = {
        "settings": {"market": "US", "horizon_days": 30, "entry_execution": "next_session_open"},
        "trials": [
            {
                "ticker": "AAPL",
                "as_of_date": "2026-01-02",
                "horizon_days": 30,
                "overall_signal": "buy",
                "conviction_score": 0.7,
                "signal_convergence": 0.6,
                "agent_signals": {"technical": "buy"},
                "error": None,
                "realized_return": 0.05,
            }
        ],
        "price_paths": {"AAPL": [{"date": "2026-01-05", "close": 101.0}]},
    }
    portfolio = {
        "config": {"position_size_pct": 0.1, "cost_bps_per_side": 10.0},
        "n_strategies_tested": 2,
        "strategies": [
            {
                "strategy": "overall",
                "total_return_pct": 3.0,
                "excess_return_pct": -2.0,
                "beats_benchmark": False,
                "effective_n": 1.0,
                "effective_n_basis": "portfolio_overlap_clustered_v1",
                "deflated_sharpe": 0.2,
                "mean_committed_principal_pct": 0.25,
                "peak_committed_principal_pct": 0.4,
                "capital_utilization_active_sessions": 8,
                "capital_utilization_market_sessions": 20,
                "capital_utilization_basis": "test basis",
            },
            {
                "strategy": "buy_and_hold",
                "total_return_pct": 5.0,
                "excess_return_pct": 0.0,
                "beats_benchmark": None,
            },
        ],
    }
    allocator = {
        "factor": "long-only cross-sectional momentum on sealed trials",
        "config": {"lookback_months": 12, "top_n": 3, "cost_bps_per_side": 10.0},
        "net_compound_return": 0.04,
        "buy_and_hold_return": 0.05,
        "excess_return": -0.01,
        "effective_n": 1.0,
        "effective_n_basis": "portfolio_overlap_clustered_v1",
    }
    ablation = {
        "candidate_arms_tested": 2,
        "periods": 3,
        "effective_n": 2.0,
        "effective_n_basis": "portfolio_overlap_clustered_v1",
        "permutation_status": "informative",
        "permutation_informative_periods": 2,
        "permutation_resamples": 2000,
        "permutation_seed": 0,
        "permutation_upper_tail_p_value": 0.4,
        "config": {"top_n": 3, "cost_bps_per_side": 10.0},
        "ai_only": {
            "strategy": "AI-only long sleeve",
            "net_compound_return": 0.01,
            "matched_net_compound_return": 0.02,
            "excess_return": -0.01,
        },
        "hybrid": {
            "strategy": "AI-positive momentum filter",
            "net_compound_return": 0.02,
            "matched_net_compound_return": 0.03,
            "excess_return": -0.01,
        },
    }
    record = build_experiment_record(
        mode="session-score",
        result=result,
        score_report={
            "total_trials": 1,
            "completed_trials": 1,
            "directional_trials": 1,
            "overall_hit_rate": 0.33,
            "hit_rate_ci_95": [0.01, 0.75],
            "effective_n": 1.0,
            "effective_n_basis": "portfolio_overlap_clustered_v1",
            "post_cutoff": {
                "overall_hit_rate": 0.25,
                "effective_n": 0.5,
                "effective_n_basis": "portfolio_overlap_clustered_v1",
            },
        },
        portfolio=portfolio,
        cross_sectional_trial_allocation=allocator,
        signal_ablation=ablation,
        config={"cost_bps_per_side": 10.0},
        session_dir=session_dir,
        source_root=source_root,
    )
    return record


def test_ledger_appends_hash_chained_runs_and_deduplicates_identical_arms(tmp_path):
    ledger_path = tmp_path / "runs.jsonl"
    record = _sample_inputs(tmp_path / "source")

    first = append_experiment_record(ledger_path, record)
    first_bytes = ledger_path.read_bytes()
    second = append_experiment_record(ledger_path, record)
    rows = [json.loads(line) for line in ledger_path.read_text().splitlines()]

    assert ledger_path.read_bytes().startswith(first_bytes)
    assert first["ledger"]["sequence"] == 1
    assert second["ledger"]["sequence"] == 2
    assert first["ledger"]["new_evaluation_arms_in_run"] == 5
    assert second["ledger"]["reused_evaluation_arms_in_run"] == 5
    assert second["ledger"]["new_evaluation_arms_in_run"] == 0
    assert second["ledger"]["previous_record_sha256"] == first["ledger"]["record_sha256"]
    assert second["candidate_arms_tested_in_run"] == 5
    assert second["pipeline_score"]["overall_hit_rate"] == 0.33
    assert second["pipeline_score"]["post_cutoff"] == {
        "overall_hit_rate": 0.25,
        "effective_n": 0.5,
        "effective_n_basis": "portfolio_overlap_clustered_v1",
    }
    overall_arm = next(
        arm
        for arm in second["candidate_arms"]
        if arm["family"] == "portfolio_comparison" and arm["strategy"] == "overall"
    )
    assert overall_arm["metrics"]["effective_n_basis"] == "portfolio_overlap_clustered_v1"
    assert overall_arm["metrics"]["mean_committed_principal_pct"] == 0.25
    assert overall_arm["metrics"]["peak_committed_principal_pct"] == 0.4
    assert overall_arm["metrics"]["capital_utilization_active_sessions"] == 8
    assert overall_arm["metrics"]["capital_utilization_market_sessions"] == 20
    assert overall_arm["metrics"]["capital_utilization_basis"] == "test basis"
    assert second["diagnostics"]["signal_ablation_test"]["permutation_upper_tail_p_value"] == 0.4
    assert second["ledger"]["unique_candidate_count_before"] == 5
    assert second["ledger"]["unique_candidate_count_after"] == 5
    assert second["ledger"]["unique_candidate_evaluation_count_before"] == 5
    assert second["ledger"]["unique_candidate_evaluation_count_after"] == 5
    assert second["ledger"]["unique_candidate_count_by_family_after"] == {
        "ai_signal_ablation": 2,
        "portfolio_comparison": 2,
        "sealed_trial_allocator": 1,
    }
    assert [row["ledger"]["sequence"] for row in rows] == [1, 2]
    assert "not_applied" in second["cross_run_dsr_adjustment"]


def test_standalone_runs_share_ledger_and_count_parameter_search(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "signal.py").write_text("RULE = 1\n")
    ledger = tmp_path / "runs.jsonl"
    report = {
        "factor": "monthly momentum",
        "universe": ["AAA", "BBB", "CCC"],
        "config": {"lookback_months": 12, "top_n": 2, "cost_bps_per_side": 10},
        "data_start": "2020-01-01",
        "data_end": "2025-01-01",
        "oos_start": "2021-01-01",
        "oos_end": "2025-01-01",
        "net_compound_return": 0.2,
        "buy_and_hold_return": 0.15,
    }
    first = append_experiment_record(
        ledger,
        build_standalone_record(
            mode="cross-sectional", report=report,
            price_histories_sha256="a" * 64, source_root=source,
        ),
    )
    second = append_experiment_record(
        ledger,
        build_standalone_record(
            mode="cross-sectional", report=report,
            price_histories_sha256="a" * 64, source_root=source,
        ),
    )
    changed = {**report, "config": {**report["config"], "top_n": 3}}
    third = append_experiment_record(
        ledger,
        build_standalone_record(
            mode="cross-sectional", report=changed,
            price_histories_sha256="a" * 64, source_root=source,
        ),
    )

    assert first["ledger"]["unique_candidate_count_after"] == 2
    assert second["ledger"]["unique_candidate_count_after"] == 2
    assert second["ledger"]["reused_evaluation_arms_in_run"] == 2
    assert third["ledger"]["unique_candidate_count_after"] == 4
    assert third["ledger"]["sequence"] == 3

    revised_result = {**report, "net_compound_return": 0.1}
    fourth = append_experiment_record(
        ledger,
        build_standalone_record(
            mode="cross-sectional", report=revised_result,
            price_histories_sha256="a" * 64, source_root=source,
        ),
    )
    assert fourth["ledger"]["same_input_previous_run_id"] == second["run_id"]
    assert fourth["ledger"]["same_input_outcome_changed"] is True


def test_candidate_fingerprint_changes_when_session_inputs_change(tmp_path):
    session_dir = tmp_path / "session"
    (session_dir / "packets").mkdir(parents=True)
    (session_dir / "manifest.json").write_text('{"trials": []}\n')
    (session_dir / "predictions.json").write_text('[{"signal": "buy"}]\n')
    (session_dir / "packets" / "trial.json").write_text('{"as_of_date": "2026-01-02"}\n')

    first = _sample_inputs(tmp_path / "source", session_dir)
    first_hash = first["dataset"]["session_inputs_sha256"]
    first_candidates = {arm["candidate_id"] for arm in first["candidate_arms"]}
    first_evaluations = {arm["evaluation_id"] for arm in first["candidate_arms"]}
    ledger_path = tmp_path / "runs.jsonl"
    append_experiment_record(ledger_path, first)

    (session_dir / "predictions.json").write_text('[{"signal": "neutral"}]\n')
    second = _sample_inputs(tmp_path / "source", session_dir)
    second_candidates = {arm["candidate_id"] for arm in second["candidate_arms"]}
    second_evaluations = {arm["evaluation_id"] for arm in second["candidate_arms"]}
    appended = append_experiment_record(ledger_path, second)

    assert second["dataset"]["session_inputs_sha256"] != first_hash
    assert second_candidates == first_candidates
    assert second_evaluations != first_evaluations
    assert appended["ledger"]["unique_candidate_count_after"] == 5
    assert appended["ledger"]["unique_candidate_evaluation_count_after"] == 10


def test_ledger_refuses_tampered_or_truncated_history(tmp_path):
    ledger_path = tmp_path / "runs.jsonl"
    append_experiment_record(ledger_path, _sample_inputs(tmp_path / "source"))
    original = ledger_path.read_text()
    row = json.loads(original)
    row["candidate_arms"][0]["strategy"] = "tampered"
    ledger_path.write_text(json.dumps(row) + "\n")

    with pytest.raises(ValueError, match="hash mismatch"):
        append_experiment_record(ledger_path, _sample_inputs(tmp_path / "source"))

    ledger_path.write_text(original[:-1])
    with pytest.raises(ValueError, match="truncated"):
        append_experiment_record(ledger_path, _sample_inputs(tmp_path / "source"))


def test_nonfinite_diagnostics_are_serializable_as_null(tmp_path):
    record = _sample_inputs(tmp_path / "source")
    record["diagnostics"]["nonfinite"] = float("nan")

    appended = append_experiment_record(tmp_path / "runs.jsonl", record)

    assert appended["diagnostics"]["nonfinite"] is None
