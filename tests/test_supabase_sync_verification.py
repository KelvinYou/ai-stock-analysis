from datetime import date

from scripts.verify_supabase_sync import REQUIRED_STAGES, validate_remote_rows


def _run(symbol: str, run_id: str, status: str = "completed") -> dict:
    return {
        "id": run_id,
        "symbol": symbol,
        "as_of_date": "2026-08-28",
        "status": status,
    }


def _artifacts(symbol: str, run_id: str, stages: set[str]) -> list[dict]:
    return [
        {
            "run_id": run_id,
            "symbol": symbol,
            "stage": stage,
            "as_of_date": "2026-08-28",
            "is_public": True,
        }
        for stage in stages
    ]


def test_validate_remote_rows_requires_all_four_public_stages():
    targets = {"AAPL": date(2026, 8, 28), "MSFT": date(2026, 8, 28)}
    runs = [_run("AAPL", "run-a"), _run("MSFT", "run-m")]
    artifacts = _artifacts("AAPL", "run-a", set(REQUIRED_STAGES)) + _artifacts(
        "MSFT", "run-m", REQUIRED_STAGES - {"research_verdict"}
    )

    passed, problems = validate_remote_rows(targets, runs, artifacts)

    assert passed == ["AAPL"]
    assert problems == [
        (
            "MSFT: completed remote run exists for 2026-08-28, "
            "but missing stage(s): research_verdict"
        )
    ]


def test_validate_remote_rows_ignores_failed_runs_and_private_artifacts():
    targets = {"AAPL": date(2026, 8, 28)}
    runs = [_run("AAPL", "failed", status="failed"), _run("AAPL", "run-a")]
    artifacts = _artifacts("AAPL", "run-a", set(REQUIRED_STAGES))
    next(artifact for artifact in artifacts if artifact["stage"] == "briefing")["is_public"] = False

    passed, problems = validate_remote_rows(targets, runs, artifacts)

    assert passed == []
    assert problems == [
        (
            "AAPL: completed remote run exists for 2026-08-28, "
            "but missing stage(s): briefing"
        )
    ]
