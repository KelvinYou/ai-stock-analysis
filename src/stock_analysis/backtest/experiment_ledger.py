"""Append-only provenance for pipeline and deterministic backtests.

The ledger captures configuration and fingerprints for future selection-bias
reviews. Its cumulative unique-arm counts are an audit aid, not a cross-run
Deflated Sharpe correction. Runs before the ledger existed cannot be recovered
from this file.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER_SCHEMA_VERSION = 1


def build_standalone_record(
    *,
    mode: str,
    report: dict[str, Any],
    price_histories_sha256: str,
    source_root: Path | None = None,
) -> dict[str, Any]:
    """Record a deterministic factor/allocator search in the shared ledger."""

    if mode not in {"factor", "cross-sectional"}:
        raise ValueError("standalone record requires factor or cross-sectional mode")
    report = _json_safe(report)
    source_root = (source_root or Path(__file__).resolve().parents[1]).resolve()
    source_sha256 = _hash_source_tree(source_root)
    revision, dirty = _git_provenance(source_root)
    universe = report.get("universe") or [report.get("ticker")]
    config = report.get("config", {})
    dataset = {
        "tickers": sorted(universe),
        "data_start": report.get("data_start"),
        "data_end": report.get("data_end"),
        "oos_start": report.get("oos_start"),
        "oos_end": report.get("oos_end"),
        "price_histories_sha256": price_histories_sha256,
        "report_sha256": _sha256_json(report),
    }
    identity_context = {
        "strategy_config": {"mode": mode, "config": config, "universe": universe},
        "source_sha256": source_sha256,
    }
    evaluation_context = {"dataset": dataset}
    candidate = _candidate_arm(
        family=f"standalone_{mode.replace('-', '_')}",
        strategy=str(report.get("factor", mode)),
        role="research_candidate_not_ai_forecast",
        candidate_config=config,
        metrics=_pick(
            report,
            "net_compound_return",
            "buy_and_hold_return",
            "excess_return",
            "matched_passive_return",
            "matched_passive_excess_return",
            "strict_hold_log_excess_ci_95",
            "effective_n",
            "periods",
            "net_p_value",
            "max_drawdown",
        ),
        identity_context=identity_context,
        evaluation_context=evaluation_context,
    )
    benchmark = _candidate_arm(
        family=f"standalone_{mode.replace('-', '_')}",
        strategy="buy_and_hold",
        role="benchmark",
        candidate_config={"universe": universe},
        metrics={"total_return": report.get("buy_and_hold_return")},
        identity_context=identity_context,
        evaluation_context=evaluation_context,
    )
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "scope": "standalone deterministic research; not an AI forecast",
        "run_config": {"mode": mode, "config": config},
        "diagnostics": {},
        "pipeline_score": {},
        "dataset": dataset,
        "source": {
            "git_revision": revision,
            "git_worktree_dirty": dirty,
            "source_tree_sha256": source_sha256,
        },
        "portfolio_dsr_candidate_count_in_run": None,
        "signal_ablation_reported_candidate_count": 0,
        "candidate_arms_tested_in_run": 2,
        "candidate_arm_count_semantics": "One deterministic research candidate and its strict-hold benchmark.",
        "candidate_arms": [benchmark, candidate],
        "cross_run_dsr_adjustment": "not_applied; cumulative unique-arm counts are audit metadata only",
        "history_boundary": "ledger counts begin with the first recorded run; pre-ledger and manually inspected candidates are not backfilled",
    }


def build_experiment_record(
    *,
    mode: str,
    result: dict[str, Any],
    portfolio: dict[str, Any],
    cross_sectional_trial_allocation: dict[str, Any] | None,
    signal_ablation: dict[str, Any] | None,
    config: dict[str, Any],
    score_report: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
    session_dir: Path | None = None,
    source_root: Path | None = None,
) -> dict[str, Any]:
    """Build a compact run record from the scored artifact components."""

    result = _json_safe(result)
    score_report = _json_safe(score_report)
    portfolio = _json_safe(portfolio)
    cross_sectional_trial_allocation = _json_safe(cross_sectional_trial_allocation)
    signal_ablation = _json_safe(signal_ablation)
    config = _json_safe(config)
    diagnostics = _json_safe(diagnostics or {})

    forecast_rows = [
        {
            "ticker": str(trial.get("ticker", "")).upper(),
            "as_of_date": trial.get("as_of_date"),
            "horizon_days": trial.get("horizon_days"),
            "overall_signal": trial.get("overall_signal"),
            "synthesized_signal": trial.get("synthesized_signal"),
            "conviction_score": trial.get("conviction_score"),
            "signal_convergence": trial.get("signal_convergence"),
            "raw_agent_signals": trial.get("raw_agent_signals", {}),
            "agent_signals": trial.get("agent_signals", {}),
            "signal_gate_reasons": trial.get("signal_gate_reasons", []),
            "failed": trial.get("error") is not None,
        }
        for trial in result.get("trials", [])
    ]
    forecast_rows.sort(key=lambda row: (row["as_of_date"] or "", row["ticker"]))
    forecast_sha256 = _sha256_json(
        {"settings": result.get("settings", {}), "trials": forecast_rows}
    )
    result_sha256 = _sha256_json(result)
    session_inputs_sha256 = _hash_session_inputs(session_dir) if session_dir is not None else None

    source_root = (source_root or Path(__file__).resolve().parents[1]).resolve()
    source_sha256 = _hash_source_tree(source_root)
    source_revision, source_worktree_dirty = _git_provenance(source_root)

    run_config = {
        "mode": mode,
        "pipeline_settings": result.get("settings", {}),
        "cli_and_portfolio": config,
    }
    strategy_pipeline_settings = dict(result.get("settings", {}))
    strategy_pipeline_settings.pop("evidence_coverage", None)
    strategy_config = {
        "mode": mode,
        "pipeline_settings": strategy_pipeline_settings,
    }
    trial_rows = result.get("trials", [])
    dataset = {
        "tickers": sorted({str(row.get("ticker", "")).upper() for row in trial_rows}),
        "as_of_dates": sorted(
            {str(row["as_of_date"]) for row in trial_rows if row.get("as_of_date")}
        ),
        "trial_count": len(trial_rows),
        "failed_trial_count": sum(row.get("error") is not None for row in trial_rows),
        "forecast_sha256": forecast_sha256,
        "result_sha256": result_sha256,
        "session_inputs_sha256": session_inputs_sha256,
    }

    candidate_arms: list[dict[str, Any]] = []
    identity_context = {
        "strategy_config": strategy_config,
        "source_sha256": source_sha256,
    }
    evaluation_context = {"run_config": run_config, "dataset": dataset}
    for strategy in portfolio.get("strategies", []):
        name = str(strategy.get("strategy", "unknown"))
        role = {
            "buy_and_hold": "benchmark",
            "rolling_long": "diagnostic_baseline",
        }.get(name, "strategy")
        candidate_arms.append(
            _candidate_arm(
                family="portfolio_comparison",
                strategy=name,
                role=role,
                candidate_config={"portfolio": portfolio.get("config", {})},
                metrics=_pick(
                    strategy,
                    "total_return_pct",
                    "benchmark_return_pct",
                    "excess_return_pct",
                    "beats_benchmark",
                    "effective_n",
                    "effective_n_basis",
                    "deflated_sharpe",
                    "max_drawdown_pct",
                    "mean_committed_principal_pct",
                    "peak_committed_principal_pct",
                    "capital_utilization_active_sessions",
                    "capital_utilization_market_sessions",
                    "capital_utilization_basis",
                    "twice_cost_excess_pct",
                    "strict_hold_log_excess_ci_95",
                ),
                identity_context=identity_context,
                evaluation_context=evaluation_context,
            )
        )

    if cross_sectional_trial_allocation is not None:
        candidate_arms.append(
            _candidate_arm(
                family="sealed_trial_allocator",
                strategy=str(
                    cross_sectional_trial_allocation.get(
                        "factor", "cross_sectional_trial_allocator"
                    )
                ),
                role="allocation_candidate_not_ai_forecast",
                candidate_config={
                    "cross_sectional": cross_sectional_trial_allocation.get("config", {})
                },
                metrics=_pick(
                    cross_sectional_trial_allocation,
                    "net_compound_return",
                    "buy_and_hold_return",
                    "excess_return",
                    "matched_passive_return",
                    "matched_passive_excess_return",
                    "effective_n",
                    "effective_n_basis",
                    "net_p_value",
                    "max_drawdown",
                    "matched_passive_log_excess_ci_95",
                ),
                identity_context=identity_context,
                evaluation_context=evaluation_context,
            )
        )

    if signal_ablation is not None:
        for key in ("ai_only", "hybrid"):
            arm = signal_ablation.get(key)
            if not isinstance(arm, dict):
                continue
            candidate_arms.append(
                _candidate_arm(
                    family="ai_signal_ablation",
                    strategy=str(arm.get("strategy", key)),
                    role="diagnostic_candidate",
                    candidate_config={"signal_ablation": signal_ablation.get("config", {})},
                    metrics=_pick(
                        arm,
                        "net_compound_return",
                        "matched_net_compound_return",
                        "excess_return",
                        "mean_exposure",
                        "max_drawdown",
                        "paired_log_excess_ci_95",
                    ),
                    identity_context=identity_context,
                    evaluation_context=evaluation_context,
                )
            )

    candidate_arms.sort(key=lambda row: (row["family"], row["strategy"]))
    portfolio_arms = [row for row in candidate_arms if row["family"] == "portfolio_comparison"]
    ablation_arms = [row for row in candidate_arms if row["family"] == "ai_signal_ablation"]
    if signal_ablation is not None:
        diagnostics["signal_ablation_test"] = _pick(
            signal_ablation,
            "periods",
            "effective_n",
            "effective_n_basis",
            "permutation_status",
            "permutation_informative_periods",
            "permutation_resamples",
            "permutation_seed",
            "permutation_null_interval_95",
            "permutation_upper_tail_p_value",
            "drawdown_basis",
        )

    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "scope": "scored api/session-score artifacts",
        "run_config": run_config,
        "diagnostics": diagnostics,
        "pipeline_score": _score_summary(score_report),
        "dataset": dataset,
        "source": {
            "git_revision": source_revision,
            "git_worktree_dirty": source_worktree_dirty,
            "source_tree_sha256": source_sha256,
        },
        "portfolio_dsr_candidate_count_in_run": portfolio.get(
            "n_strategies_tested", len(portfolio_arms)
        ),
        "signal_ablation_reported_candidate_count": (
            signal_ablation.get("candidate_arms_tested", len(ablation_arms))
            if signal_ablation is not None
            else 0
        ),
        "candidate_arms_tested_in_run": len(candidate_arms),
        "candidate_arm_count_semantics": (
            "Counts all per-run portfolio comparison rows (including benchmark and diagnostic baselines) "
            "plus successfully scored allocator/ablation arms; permutation resamples are not arms."
        ),
        "candidate_arms": candidate_arms,
        "cross_run_dsr_adjustment": "not_applied; cumulative unique-arm counts are audit metadata only",
        "history_boundary": "ledger counts begin with the first recorded run; pre-ledger and manually inspected candidates are not backfilled",
    }


def append_experiment_record(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Append one hash-chained JSONL record and return it with ledger totals.

    A POSIX advisory lock protects the read/count/append transaction between
    cooperating CLI processes. Each line is emitted with one O_APPEND write;
    malformed, truncated, or modified history blocks further appends rather
    than silently resetting the cumulative count.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        existing = _read_and_validate_ledger(descriptor)
        row = _json_safe(record)
        if "ledger" in row:
            raise ValueError("record already contains reserved ledger metadata")
        frozen_input_id = _frozen_input_id(row)
        prior_same_input = next(
            (prior for prior in reversed(existing) if _frozen_input_id(prior) == frozen_input_id),
            None,
        )
        outcome_changed = (
            _outcome_signature(prior_same_input) != _outcome_signature(row)
            if prior_same_input is not None
            else False
        )

        prior_ids: dict[str, set[str]] = {}
        prior_evaluation_ids: dict[str, set[str]] = {}
        for prior in existing:
            for arm in prior["candidate_arms"]:
                prior_ids.setdefault(arm["family"], set()).add(arm["candidate_id"])
                prior_evaluation_ids.setdefault(arm["family"], set()).add(arm["evaluation_id"])

        all_ids = {family: set(ids) for family, ids in prior_ids.items()}
        all_evaluation_ids = {family: set(ids) for family, ids in prior_evaluation_ids.items()}
        reused_evaluations = 0
        new_evaluations = 0
        for arm in row.get("candidate_arms", []):
            family = str(arm["family"])
            candidate_id = str(arm["candidate_id"])
            evaluation_id = str(arm["evaluation_id"])
            if evaluation_id in prior_evaluation_ids.get(family, set()):
                reused_evaluations += 1
            else:
                new_evaluations += 1
            all_ids.setdefault(family, set()).add(candidate_id)
            all_evaluation_ids.setdefault(family, set()).add(evaluation_id)

        row["ledger"] = {
            "sequence": len(existing) + 1,
            "runs_before": len(existing),
            "reused_evaluation_arms_in_run": reused_evaluations,
            "new_evaluation_arms_in_run": new_evaluations,
            "frozen_input_id": frozen_input_id,
            "same_input_previous_run_id": (
                prior_same_input.get("run_id") if prior_same_input is not None else None
            ),
            "same_input_outcome_changed": outcome_changed,
            "unique_candidate_count_before": sum(len(ids) for ids in prior_ids.values()),
            "unique_candidate_count_after": sum(len(ids) for ids in all_ids.values()),
            "unique_candidate_count_by_family_after": {
                family: len(ids) for family, ids in sorted(all_ids.items())
            },
            "unique_candidate_evaluation_count_before": sum(
                len(ids) for ids in prior_evaluation_ids.values()
            ),
            "unique_candidate_evaluation_count_after": sum(
                len(ids) for ids in all_evaluation_ids.values()
            ),
            "unique_candidate_evaluation_counts_by_family_after": {
                family: len(ids) for family, ids in sorted(all_evaluation_ids.items())
            },
            "previous_record_sha256": (
                existing[-1]["ledger"]["record_sha256"] if existing else None
            ),
        }
        row["ledger"]["record_sha256"] = _sha256_json(row)
        encoded = _canonical_json(row) + b"\n"
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError(f"short append to experiment ledger: {written}/{len(encoded)} bytes")
        os.fsync(descriptor)
        return row
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _candidate_arm(
    *,
    family: str,
    strategy: str,
    role: str,
    candidate_config: dict[str, Any],
    metrics: dict[str, Any],
    identity_context: dict[str, Any],
    evaluation_context: dict[str, Any],
) -> dict[str, Any]:
    identity = {
        "family": family,
        "strategy": strategy,
        "role": role,
        "candidate_config": candidate_config,
        **identity_context,
    }
    candidate_id = _sha256_json(identity)
    evaluation_id = _sha256_json(
        {"candidate_id": candidate_id, "evaluation_context": evaluation_context}
    )
    return {
        "candidate_id": candidate_id,
        "evaluation_id": evaluation_id,
        "family": family,
        "strategy": strategy,
        "role": role,
        "candidate_config": candidate_config,
        "metrics": metrics,
    }


def _frozen_input_id(row: dict[str, Any]) -> str:
    dataset = row.get("dataset", {})
    return _sha256_json(
        {
            "run_config": row.get("run_config"),
            "tickers": dataset.get("tickers"),
            "as_of_dates": dataset.get("as_of_dates"),
            "oos_start": dataset.get("oos_start"),
            "oos_end": dataset.get("oos_end"),
            "result_sha256": dataset.get("result_sha256"),
            "session_inputs_sha256": dataset.get("session_inputs_sha256"),
            "price_histories_sha256": dataset.get("price_histories_sha256"),
        }
    )


def _outcome_signature(row: dict[str, Any]) -> str:
    return _sha256_json(
        [
            {"family": arm.get("family"), "strategy": arm.get("strategy"), "metrics": arm.get("metrics")}
            for arm in row.get("candidate_arms", [])
        ]
    )


def _pick(value: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: value[key] for key in keys if key in value}


def _score_summary(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    keys = (
        "total_trials",
        "completed_trials",
        "errored_trials",
        "directional_trials",
        "overall_hit_rate",
        "hit_rate_ci_95",
        "directional_mean_return",
        "net_directional_mean_return",
        "directional_mean_p_value",
        "net_mean_p_value",
        "effective_n",
        "effective_n_basis",
        "probabilistic_sharpe",
        "cost_bps_per_side",
        "effective_cutoff",
        "cutoff_source_model",
    )
    summary = _pick(value, *keys)
    for partition in ("pre_cutoff", "post_cutoff"):
        nested = value.get(partition)
        if isinstance(nested, dict):
            summary[partition] = _pick(nested, *keys[:-2])
    return summary


def _hash_session_inputs(session_dir: Path) -> str | None:
    root = Path(session_dir).resolve()
    if not root.is_dir():
        return None
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.as_posix() in {
            "manifest.json",
            "predictions.json",
            "provider_run.json",
        } or (relative.parts[0] in {"packets", "predictions"} and path.suffix == ".json"):
            files.append(path)
    if not files:
        return None

    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative + b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def _hash_source_tree(source_root: Path) -> str:
    if not source_root.is_dir():
        return ""
    digest = hashlib.sha256()
    ledger_path = Path(__file__).resolve()
    for path in sorted(source_root.rglob("*.py")):
        if not path.is_file() or path.resolve() == ledger_path:
            continue
        relative = path.relative_to(source_root).as_posix().encode("utf-8")
        digest.update(relative + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    repository_root = source_root.parent.parent
    for name in ("pyproject.toml", "uv.lock", "requirements.txt"):
        path = repository_root / name
        if path.is_file():
            digest.update(f"@repo/{name}".encode() + b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _git_provenance(source_root: Path) -> tuple[str | None, bool | None]:
    repository = source_root.parent.parent
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repository,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        ).stdout
        return revision, bool(status.strip())
    except (OSError, subprocess.SubprocessError):
        return None, None


def _read_and_validate_ledger(descriptor: int) -> list[dict[str, Any]]:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks = []
    while chunk := os.read(descriptor, 1024 * 1024):
        chunks.append(chunk)
    contents = b"".join(chunks)
    if contents and not contents.endswith(b"\n"):
        raise ValueError("experiment ledger ends with a truncated JSONL record")

    rows: list[dict[str, Any]] = []
    expected_previous_hash = None
    unique_by_family: dict[str, set[str]] = {}
    unique_evaluations_by_family: dict[str, set[str]] = {}
    for sequence, line in enumerate(contents.splitlines(), start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on experiment ledger line {sequence}") from exc
        if not isinstance(row, dict) or row.get("schema_version") != LEDGER_SCHEMA_VERSION:
            raise ValueError(f"unsupported experiment ledger record on line {sequence}")
        ledger = row.get("ledger")
        if not isinstance(ledger, dict) or ledger.get("sequence") != sequence:
            raise ValueError(f"invalid experiment ledger sequence on line {sequence}")
        if ledger.get("runs_before") != sequence - 1:
            raise ValueError(f"invalid prior-run count on experiment ledger line {sequence}")
        if ledger.get("previous_record_sha256") != expected_previous_hash:
            raise ValueError(f"broken experiment ledger hash chain on line {sequence}")
        record_hash = ledger.get("record_sha256")
        unsigned = json.loads(json.dumps(row))
        unsigned["ledger"].pop("record_sha256", None)
        if not isinstance(record_hash, str) or _sha256_json(unsigned) != record_hash:
            raise ValueError(f"experiment ledger record hash mismatch on line {sequence}")

        arms = row.get("candidate_arms")
        if not isinstance(arms, list):
            raise ValueError(f"candidate_arms must be a list on ledger line {sequence}")
        if row.get("candidate_arms_tested_in_run") != len(arms):
            raise ValueError(f"experiment ledger arm count mismatch on line {sequence}")
        candidate_count_before = sum(len(ids) for ids in unique_by_family.values())
        evaluation_count_before = sum(len(ids) for ids in unique_evaluations_by_family.values())
        if ledger.get("unique_candidate_count_before") != candidate_count_before:
            raise ValueError(f"experiment ledger prior candidate tally mismatch on line {sequence}")
        if ledger.get("unique_candidate_evaluation_count_before") != evaluation_count_before:
            raise ValueError(
                f"experiment ledger prior evaluation tally mismatch on line {sequence}"
            )
        for arm in arms:
            if (
                not isinstance(arm, dict)
                or not arm.get("family")
                or not arm.get("candidate_id")
                or not arm.get("evaluation_id")
            ):
                raise ValueError(f"invalid candidate arm on experiment ledger line {sequence}")
            unique_by_family.setdefault(str(arm["family"]), set()).add(str(arm["candidate_id"]))
            unique_evaluations_by_family.setdefault(str(arm["family"]), set()).add(
                str(arm["evaluation_id"])
            )
        recorded_totals = ledger.get("unique_candidate_count_by_family_after", {})
        actual_totals = {family: len(ids) for family, ids in sorted(unique_by_family.items())}
        if recorded_totals != actual_totals:
            raise ValueError(f"experiment ledger candidate tally mismatch on line {sequence}")
        if ledger.get("unique_candidate_count_after") != sum(actual_totals.values()):
            raise ValueError(f"experiment ledger total mismatch on line {sequence}")
        evaluation_totals = {
            family: len(ids) for family, ids in sorted(unique_evaluations_by_family.items())
        }
        if ledger.get("unique_candidate_evaluation_counts_by_family_after") != evaluation_totals:
            raise ValueError(f"experiment ledger evaluation tally mismatch on line {sequence}")
        if ledger.get("unique_candidate_evaluation_count_after") != sum(evaluation_totals.values()):
            raise ValueError(f"experiment ledger evaluation total mismatch on line {sequence}")
        rows.append(row)
        expected_previous_hash = record_hash
    return rows


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
