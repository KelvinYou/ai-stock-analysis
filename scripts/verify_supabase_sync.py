"""Verify that local flat pipeline artifacts have complete Supabase runs.

The verifier uses the local ``briefing.json`` files as the expected ticker/date
set, then requires one completed remote run with all four public pipeline
stages: analyst reports, debate result, research verdict, and briefing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from stock_analysis.config import Settings, load_env
from stock_analysis.data.cloud import SupabaseError, SupabaseRestClient

REQUIRED_STAGES = frozenset(
    {"analyst_reports", "debate_result", "research_verdict", "briefing"}
)
LOCAL_STAGE_FILES = {
    "analyst_reports": "analyst_reports.json",
    "debate_result": "debate_result.json",
    "research_verdict": "research_verdict.json",
    "briefing": "briefing.json",
}


def discover_local_targets(
    data_dir: Path, as_of_date: date | None = None
) -> tuple[dict[str, date], list[str]]:
    """Return ``{symbol: briefing date}`` and local completeness problems."""
    targets: dict[str, date] = {}
    problems: list[str] = []

    if not data_dir.exists():
        return {}, [f"local data directory does not exist: {data_dir}"]

    for directory in sorted(data_dir.iterdir()):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        briefing_path = directory / LOCAL_STAGE_FILES["briefing"]
        if not briefing_path.exists():
            continue

        symbol = directory.name.upper()
        try:
            briefing = json.loads(briefing_path.read_text())
            briefing_date = date.fromisoformat(str(briefing["date"])[:10])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f"{symbol}: invalid local briefing.json ({exc})")
            continue

        if as_of_date is not None and briefing_date != as_of_date:
            continue

        missing = [
            filename
            for filename in LOCAL_STAGE_FILES.values()
            if not (directory / filename).exists()
        ]
        if missing:
            problems.append(f"{symbol}: missing local artifact(s): {', '.join(missing)}")
        targets[symbol] = briefing_date

    return targets, problems


def validate_remote_rows(
    targets: Mapping[str, date],
    runs: Iterable[Mapping[str, Any]],
    artifacts: Iterable[Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    """Validate remote rows without making any network calls."""
    runs_by_target: dict[tuple[str, date], list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        if run.get("status") != "completed" or not run.get("id"):
            continue
        symbol = str(run.get("symbol", "")).upper()
        try:
            run_date = date.fromisoformat(str(run["as_of_date"])[:10])
        except (KeyError, TypeError, ValueError):
            continue
        if symbol in targets and targets[symbol] == run_date:
            runs_by_target[(symbol, run_date)].append(run)

    stages_by_run_target: dict[tuple[str, str, date], set[str]] = defaultdict(set)
    for artifact in artifacts:
        run_id = artifact.get("run_id")
        stage = artifact.get("stage")
        if not run_id or stage not in REQUIRED_STAGES:
            continue
        if artifact.get("is_public") not in (True, "true"):
            continue
        symbol = str(artifact.get("symbol", "")).upper()
        try:
            artifact_date = date.fromisoformat(str(artifact["as_of_date"])[:10])
        except (KeyError, TypeError, ValueError):
            continue
        stages_by_run_target[(str(run_id), symbol, artifact_date)].add(str(stage))

    passed: list[str] = []
    problems: list[str] = []
    for symbol, target_date in sorted(targets.items()):
        candidates = runs_by_target.get((symbol, target_date), [])
        if not candidates:
            problems.append(f"{symbol}: no completed remote run for {target_date}")
            continue

        complete = any(
            REQUIRED_STAGES.issubset(
                stages_by_run_target.get((str(run["id"]), symbol, target_date), set())
            )
            for run in candidates
        )
        if complete:
            passed.append(symbol)
            continue

        observed = set().union(
            *(
                stages_by_run_target.get((str(run["id"]), symbol, target_date), set())
                for run in candidates
            )
        )
        missing = sorted(REQUIRED_STAGES - observed)
        problems.append(
            f"{symbol}: completed remote run exists for {target_date}, "
            f"but missing stage(s): {', '.join(missing)}"
        )

    return passed, problems


def fetch_rows(
    client: SupabaseRestClient, targets: Mapping[str, date]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch only the run/artifact rows needed for the local target set."""
    runs: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    by_date: dict[date, list[str]] = defaultdict(list)
    for symbol, target_date in targets.items():
        by_date[target_date].append(symbol)

    for target_date, symbols in by_date.items():
        symbol_filter = f"({','.join(sorted(symbols))})"
        date_filter = f"eq.{target_date.isoformat()}"
        date_runs = client.select(
            "analysis_runs",
            {
                "symbol": f"in.{symbol_filter}",
                "as_of_date": date_filter,
                "select": "id,symbol,as_of_date,status",
                "limit": "1000",
            },
        )
        runs.extend(date_runs)

        run_ids = [str(run["id"]) for run in date_runs if run.get("id")]
        if not run_ids:
            continue
        artifacts.extend(
            client.select(
                "analysis_artifacts",
                {
                    "run_id": f"in.({','.join(run_ids)})",
                    "select": "run_id,symbol,stage,as_of_date,is_public",
                    "limit": "5000",
                },
            )
        )

    return runs, artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify local pipeline artifacts are complete in Supabase."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--as-of-date", type=date.fromisoformat)
    args = parser.parse_args()

    load_env()
    settings = Settings.from_env(storage_backend="supabase")
    targets, local_problems = discover_local_targets(args.data_dir, args.as_of_date)
    if not targets:
        print("Supabase sync verification: FAIL 0/0 (no local briefings found)")
        for problem in local_problems:
            print(f"FAIL {problem}", file=sys.stderr)
        return 1

    client = None
    try:
        client = SupabaseRestClient(
            settings.supabase_url or "",
            settings.supabase_service_key or "",
            schema=settings.supabase_schema,
        )
        runs, artifacts = fetch_rows(client, targets)
    except SupabaseError as exc:
        print(f"Supabase sync verification: ERROR {exc}", file=sys.stderr)
        return 2
    finally:
        if client is not None:
            client.close()

    passed, remote_problems = validate_remote_rows(targets, runs, artifacts)
    problems = local_problems + remote_problems
    result = "PASS" if not problems and len(passed) == len(targets) else "FAIL"
    print(f"Supabase sync verification: {result} {len(passed)}/{len(targets)}")
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
