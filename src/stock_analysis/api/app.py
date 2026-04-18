from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.data.store import DataStore
from stock_analysis.orchestrator import AnalysisPipeline

logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="AI Stock Analysis", version="0.1.0")

# In-memory job tracker
jobs: dict[str, Job] = {}


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


@app.post("/analyze/{ticker}")
async def start_analysis(ticker: str, req: AnalyzeRequest | None = None):
    req = req or AnalyzeRequest()
    job_id = str(uuid.uuid4())[:8]
    job = Job(id=job_id, ticker=ticker.upper(), status=JobStatus.PENDING)
    jobs[job_id] = job

    settings = Settings(
        quick_think_model=req.model,
        deep_think_model=req.debate_model,
        debate_rounds=req.rounds,
    )

    asyncio.create_task(_run_analysis(job_id, ticker.upper(), settings))
    return {"job_id": job_id, "ticker": ticker.upper(), "status": "pending"}


async def _run_analysis(job_id: str, ticker: str, settings: Settings):
    job = jobs[job_id]
    job.status = JobStatus.RUNNING
    try:
        pipeline = AnalysisPipeline(settings)
        await pipeline.run(ticker)
        job.status = JobStatus.COMPLETED
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()


@app.get("/results/{ticker}")
async def get_results(ticker: str, for_date: str | None = None):
    store = DataStore()
    d = date.fromisoformat(for_date) if for_date else None
    briefing = store.load_briefing(ticker.upper(), for_date=d)
    if not briefing:
        raise HTTPException(status_code=404, detail="No results found")
    return briefing.model_dump()
