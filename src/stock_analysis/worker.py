"""Durable Supabase analysis worker.

Run this alongside the FastAPI control plane when ``STORAGE_BACKEND=supabase``:

    stock-analysis-worker

The worker claims one database-backed job at a time, runs the existing Python
pipeline, and lets the pipeline mark the run completed or failed. The claim
function uses row locking/leases, so a crashed worker can be retried safely.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
import uuid

from stock_analysis.config import Settings, load_env
from stock_analysis.data.cloud import SupabaseAnalysisStore
from stock_analysis.orchestrator import AnalysisPipeline

logger = logging.getLogger(__name__)


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


def process_once(settings: Settings, worker_id: str) -> bool:
    """Claim and process one job. Return whether a job was found."""
    claim_store = SupabaseAnalysisStore(settings)
    try:
        run = claim_store.claim_run(worker_id)
    finally:
        claim_store.close()
    if not run:
        return False

    run_settings = _settings_from_run(run.settings)
    pipeline_store = SupabaseAnalysisStore(settings, run_id=run.id)
    pipeline: AnalysisPipeline | None = None
    try:
        pipeline = AnalysisPipeline(
            settings=run_settings,
            market=run.market,
            as_of_date=run.as_of_date,
            store=pipeline_store,
            run_id=run.id,
        )
        asyncio.run(pipeline.run(run.symbol))
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
    if settings.storage_backend != "supabase":
        parser.error("stock-analysis-worker requires STORAGE_BACKEND=supabase")
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
