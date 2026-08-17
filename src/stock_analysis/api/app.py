from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from enum import Enum
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.data.cloud import SupabaseAnalysisStore, build_store
from stock_analysis.orchestrator import AnalysisPipeline

logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="AI Stock Analysis", version="0.2.0")

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    id: str
    ticker: str
    status: JobStatus
    error: str | None = None


class AnalyzeRequest(BaseModel):
    rounds: int = 3
    model: str = "haiku"
    debate_model: str = "opus"
    market: Literal["US", "MY"] = "US"
    as_of_date: date | None = None


# Local mode remains useful for ``uvicorn`` development without a worker. Cloud
# mode persists all job state in Supabase and uses the separate worker process.
jobs: dict[str, Job] = {}
_background_tasks: set[asyncio.Task] = set()


def _settings(req: AnalyzeRequest) -> Settings:
    return Settings.from_env(
        quick_think_model=req.model,
        deep_think_model=req.debate_model,
        debate_rounds=req.rounds,
    )


@app.post("/analyze/{ticker}")
async def start_analysis(
    ticker: str,
    req: AnalyzeRequest | None = None,
    x_idempotency_key: str | None = Header(default=None),
):
    req = req or AnalyzeRequest()
    symbol = ticker.upper()
    settings = _settings(req)

    if settings.storage_backend == "supabase":
        store = SupabaseAnalysisStore(settings)
        try:
            run_id = store.enqueue_run(
                symbol,
                market=req.market,
                as_of_date=req.as_of_date,
                settings=settings,
                idempotency_key=x_idempotency_key,
            )
        finally:
            store.close()
        return {"job_id": run_id, "ticker": symbol, "status": "pending"}

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = Job(id=job_id, ticker=symbol, status=JobStatus.PENDING)
    task = asyncio.create_task(_run_local_analysis(job_id, symbol, settings, req))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"job_id": job_id, "ticker": symbol, "status": "pending"}


async def _run_local_analysis(
    job_id: str,
    ticker: str,
    settings: Settings,
    req: AnalyzeRequest,
):
    job = jobs[job_id]
    job.status = JobStatus.RUNNING
    pipeline: AnalysisPipeline | None = None
    try:
        pipeline = AnalysisPipeline(
            settings,
            market=req.market,
            as_of_date=req.as_of_date,
            run_id=job_id,
        )
        await pipeline.run(ticker)
        job.status = JobStatus.COMPLETED
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
    finally:
        if pipeline is not None:
            pipeline.close()


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    settings = Settings.from_env()
    if settings.storage_backend == "supabase":
        store = SupabaseAnalysisStore(settings)
        try:
            run = store.get_run(job_id)
        finally:
            store.close()
        if not run:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "id": run.id,
            "ticker": run.symbol,
            "status": run.status,
            "error": run.error,
        }

    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()


@app.get("/results/{ticker}")
async def get_results(ticker: str, for_date: str | None = None):
    settings = Settings.from_env()
    store = build_store(settings)
    try:
        d = date.fromisoformat(for_date) if for_date else None
        briefing = store.load_briefing(ticker.upper(), for_date=d)
    finally:
        close = getattr(store, "close", None)
        if close:
            close()
    if not briefing:
        raise HTTPException(status_code=404, detail="No results found")
    return briefing.model_dump(mode="json")
