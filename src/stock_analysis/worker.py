"""Durable Supabase analysis worker.

Run this alongside the FastAPI control plane when ``STORAGE_BACKEND=supabase``:

    stock-analysis-worker

The worker claims one database-backed job at a time, runs the existing Python
pipeline, and lets the pipeline mark the run completed or failed. The claim
function uses row locking/leases, and the active worker renews its lease so a
long analysis is not reclaimed while it is still running.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from stock_analysis.config import Settings, load_env
from stock_analysis.data.cloud import SupabaseAnalysisStore
from stock_analysis.orchestrator import AnalysisPipeline

logger = logging.getLogger(__name__)


class LeaseLostError(RuntimeError):
    """The worker can no longer prove ownership of a running analysis."""


def _resolve_claude_cli() -> Path:
    """Find the CLI bundled with claude-agent-sdk, with PATH as a fallback."""
    try:
        import claude_agent_sdk

        package_file = getattr(claude_agent_sdk, "__file__", None)
        if package_file:
            bundled = Path(package_file).resolve().parent / "_bundled" / (
                "claude.exe" if os.name == "nt" else "claude"
            )
            if bundled.is_file():
                return bundled
    except ImportError:
        pass

    system_cli = shutil.which("claude")
    if system_cli:
        return Path(system_cli)
    raise FileNotFoundError("claude-agent-sdk bundled CLI and PATH claude are both missing")


def preflight_claude_cli() -> str:
    """Verify the exact Claude CLI the SDK will spawn before claiming work."""
    try:
        cli_path = _resolve_claude_cli()
    except FileNotFoundError as exc:
        raise RuntimeError("Claude CLI is not available in the worker image") from exc

    if not os.access(cli_path, os.X_OK):
        raise RuntimeError(f"Claude CLI is not executable: {cli_path}")
    try:
        result = subprocess.run(
            [str(cli_path), "-v"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Claude CLI preflight failed: {cli_path}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"Claude CLI preflight failed ({result.returncode}): {detail or cli_path}"
        )
    return (result.stdout or result.stderr).strip()


def _settings_from_run(run_settings: dict) -> Settings:
    allowed = {
        key: value
        for key, value in run_settings.items()
        if key in {
            "quick_think_model",
            "deep_think_model",
            "synthesis_model",
            "research_manager_model",
            "debate_rounds",
            "price_history_period",
            "enable_research_manager",
            "enable_outcome_memory",
        }
    }
    return Settings.from_env(
        storage_backend="supabase",
        **allowed,
    )


async def _renew_lease_until_done(
    store: SupabaseAnalysisStore,
    run_id: str,
    worker_id: str,
    settings: Settings,
) -> None:
    interval = min(
        settings.worker_heartbeat_seconds,
        max(5, settings.worker_lease_seconds // 3),
    )
    while True:
        await asyncio.sleep(interval)
        try:
            renewed = store.renew_run_lease(
                run_id,
                worker_id,
                lease_seconds=settings.worker_lease_seconds,
            )
        except Exception as exc:
            raise LeaseLostError(f"lease renewal failed for run {run_id}") from exc
        if not renewed:
            raise LeaseLostError(f"lease ownership lost for run {run_id}")


async def _run_pipeline_with_lease(
    pipeline: AnalysisPipeline,
    store: SupabaseAnalysisStore,
    run_id: str,
    worker_id: str,
    settings: Settings,
    ticker: str,
) -> None:
    """Run the pipeline while renewing its database lease."""
    pipeline_task = asyncio.create_task(pipeline.run(ticker))
    heartbeat_task = asyncio.create_task(
        _renew_lease_until_done(store, run_id, worker_id, settings)
    )
    try:
        done, _ = await asyncio.wait(
            {pipeline_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if heartbeat_task in done:
            # Awaiting propagates LeaseLostError and prevents the still-running
            # pipeline from spending more tokens after ownership is gone.
            await heartbeat_task
        await pipeline_task
    finally:
        for task in (pipeline_task, heartbeat_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(pipeline_task, heartbeat_task, return_exceptions=True)


async def _process_claimed_run(settings: Settings, worker_id: str, run) -> None:
    run_settings = _settings_from_run(run.settings)
    worker_settings = settings.model_copy(update={"worker_id": worker_id})
    pipeline_store = SupabaseAnalysisStore(worker_settings, run_id=run.id)
    pipeline: AnalysisPipeline | None = None
    try:
        pipeline = AnalysisPipeline(
            settings=run_settings,
            market=run.market,
            as_of_date=run.as_of_date,
            store=pipeline_store,
            run_id=run.id,
        )
        await asyncio.wait_for(
            _run_pipeline_with_lease(
                pipeline,
                pipeline_store,
                run.id,
                worker_id,
                settings,
                run.symbol,
            ),
            timeout=settings.max_run_seconds,
        )
    except LeaseLostError:
        # Do not mark the row failed: another worker may already have reclaimed
        # it. Cancelling the pipeline is what prevents duplicate LLM spend.
        logger.exception("Lease lost; abandoning run without terminal update: %s", run.id)
    except TimeoutError:
        logger.error("Analysis run exceeded max duration: %s", run.id)
        pipeline_store.fail_run(run.id, "analysis exceeded the configured max_run_seconds")
    except Exception:
        logger.exception("Analysis run failed: %s", run.id)
        # The pipeline normally marks failures itself. This fallback covers
        # errors before it can establish its lifecycle context.
        pipeline_store.fail_run(run.id, "worker failed; see worker logs")
    finally:
        if pipeline is not None:
            pipeline.close()
        else:
            pipeline_store.close()


def process_once(settings: Settings, worker_id: str) -> bool:
    """Claim and process one job. Return whether a job was found."""
    claim_store = SupabaseAnalysisStore(settings)
    try:
        run = claim_store.claim_run(worker_id, lease_seconds=settings.worker_lease_seconds)
    finally:
        claim_store.close()
    if not run:
        return False

    asyncio.run(_process_claimed_run(settings, worker_id, run))
    return True


def cli() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Process Supabase-backed stock-analysis jobs.")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit.")
    parser.add_argument("--poll-seconds", type=float, default=None)
    parser.add_argument("--worker-id", default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    try:
        settings.require_worker_runtime()
    except RuntimeError as exc:
        parser.error(str(exc))
    if settings.storage_backend != "supabase":
        parser.error("stock-analysis-worker requires STORAGE_BACKEND=supabase")
    try:
        version = preflight_claude_cli()
    except RuntimeError as exc:
        parser.error(str(exc))
    logger.info("Claude CLI preflight passed: %s", version)
    worker_id = args.worker_id or settings.worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    poll_seconds = max(1.0, args.poll_seconds or settings.worker_poll_seconds)

    while True:
        found = process_once(settings, worker_id)
        if args.once:
            return
        if not found:
            time.sleep(min(poll_seconds, 30.0))


if __name__ == "__main__":
    cli()
