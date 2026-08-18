from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi import Path as FastAPIPath
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from stock_analysis.api.public_data import (
    TICKER_RE,
    PublicReadService,
    TickerBundleResponse,
    TickerSummaryResponse,
    WatchlistEntryResponse,
    normalize_ticker,
)
from stock_analysis.config import Settings
from stock_analysis.data.cloud import SupabaseAnalysisStore, SupabaseError
from stock_analysis.models.synthesis import Briefing
from stock_analysis.orchestrator import AnalysisPipeline

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeRequest(BaseModel):
    """Public request contract; cost-bearing knobs are deliberately bounded."""

    model_config = ConfigDict(extra="forbid")

    rounds: int = Field(default=3, ge=1, le=3)
    model: Literal["haiku", "sonnet", "opus"] = "haiku"
    debate_model: Literal["haiku", "sonnet", "opus"] = "opus"
    market: Literal["US", "MY"] = "US"


class AnalysisRunResponse(BaseModel):
    run_id: str
    ticker: str
    status: JobStatus
    error: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    service: str = "ai-stock-analysis-api"
    storage_backend: str
    checks: dict[str, str]


TickerPath = Annotated[str, FastAPIPath(pattern=TICKER_RE.pattern)]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorDetail(
                code=code,
                message=message,
                request_id=_request_id(request),
                details=details,
            )
        ).model_dump(mode="json"),
        headers=headers,
    )
    response.headers["X-Request-ID"] = _request_id(request)
    return response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Production must never silently fall back to the in-process local queue.
    settings = Settings.from_env()
    settings.require_api_runtime()
    yield


app = FastAPI(
    title="AI Stock Analysis",
    version="0.3.0",
    lifespan=lifespan,
)


_PUBLIC_PATHS = {"/health/live", "/health/ready"}


def _openapi_with_auth() -> dict[str, Any]:
    """Describe the middleware-enforced bearer contract in generated OpenAPI."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description=(
            "FastAPI control plane for durable stock-analysis runs and public "
            "completed dashboard reads. All routes except health checks require "
            "the configured bearer token."
        ),
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "BearerAuth"
    ] = {"type": "http", "scheme": "bearer"}
    for path, operations in schema.get("paths", {}).items():
        if path in _PUBLIC_PATHS:
            continue
        for operation in operations.values():
            if isinstance(operation, dict):
                operation["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_auth


@app.middleware("http")
async def request_context_and_auth(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    settings = Settings.from_env()

    if request.url.path not in _PUBLIC_PATHS:
        if settings.environment == "production" and not settings.api_bearer_token:
            return _error_response(
                request,
                status_code=503,
                code="api_not_configured",
                message="Production API authentication is not configured",
            )
        if settings.api_bearer_token:
            authorization = request.headers.get("Authorization", "")
            scheme, _, presented = authorization.partition(" ")
            if scheme.lower() != "bearer" or not presented or not secrets.compare_digest(
                presented, settings.api_bearer_token
            ):
                return _error_response(
                    request,
                    status_code=401,
                    code="unauthorized",
                    message="A valid bearer token is required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = "http_error"
    message = str(exc.detail)
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", code))
        message = str(exc.detail.get("message", message))
    return _error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return _error_response(
        request,
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details=exc.errors(),
    )


# Local mode remains useful for development and tests. Production rejects it
# during lifespan startup, so these process-local counters are not a cloud
# safety mechanism.
jobs: dict[str, AnalysisRunResponse] = {}
_local_results: dict[str, Briefing] = {}
_background_tasks: set[asyncio.Task] = set()
_local_quota_lock = asyncio.Lock()
_local_quota_day: date | None = None
_local_accepted_runs = 0
_local_active_runs = 0


def _settings(req: AnalyzeRequest) -> Settings:
    return Settings.from_env(
        quick_think_model=req.model,
        deep_think_model=req.debate_model,
        debate_rounds=req.rounds,
    )


def _storage_exception(exc: SupabaseError) -> HTTPException:
    message = str(exc)
    if "analysis_idempotency_conflict" in message:
        return HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_conflict",
                "message": "Idempotency key is already bound to a different request",
            },
        )
    if "analysis_daily_quota_exceeded" in message:
        return HTTPException(
            status_code=429,
            detail={
                "code": "daily_quota_exceeded",
                "message": "The daily analysis run quota has been reached",
            },
        )
    if "analysis_concurrency_limit_exceeded" in message:
        return HTTPException(
            status_code=429,
            detail={
                "code": "concurrency_limit_exceeded",
                "message": "The analysis concurrency limit has been reached",
            },
        )
    logger.exception("Supabase request failed")
    return HTTPException(
        status_code=503,
        detail={
            "code": "storage_unavailable",
            "message": "Analysis storage is temporarily unavailable",
        },
    )


async def _admit_local_run(settings: Settings) -> None:
    global _local_quota_day, _local_accepted_runs, _local_active_runs
    today = datetime.now(ZoneInfo(settings.quota_timezone)).date()
    async with _local_quota_lock:
        if _local_quota_day != today:
            _local_quota_day = today
            _local_accepted_runs = 0
            _local_active_runs = 0
        if _local_accepted_runs >= settings.max_daily_runs:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "daily_quota_exceeded",
                    "message": "The daily analysis run quota has been reached",
                },
            )
        if _local_active_runs >= settings.max_concurrent_runs:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "concurrency_limit_exceeded",
                    "message": "The analysis concurrency limit has been reached",
                },
            )
        _local_accepted_runs += 1
        _local_active_runs += 1


async def _release_local_run() -> None:
    global _local_active_runs
    async with _local_quota_lock:
        _local_active_runs = max(0, _local_active_runs - 1)


@app.get("/health/live", response_model=HealthResponse)
async def health_live():
    settings = Settings.from_env()
    return HealthResponse(
        status="ok",
        storage_backend=settings.storage_backend,
        checks={"process": "ok"},
    )


@app.get("/health/ready", response_model=HealthResponse)
async def health_ready(request: Request):
    settings = Settings.from_env()
    checks: dict[str, str] = {"config": "ok", "storage": "ok"}
    try:
        settings.require_api_runtime()
        if settings.storage_backend == "supabase":
            store = SupabaseAnalysisStore(settings)
            try:
                store.client.select("tickers", {"select": "symbol", "limit": "1"})
            finally:
                store.close()
    except (RuntimeError, SupabaseError) as exc:
        checks["config" if isinstance(exc, RuntimeError) else "storage"] = "not_ready"
        body = HealthResponse(
            status="not_ready",
            storage_backend=settings.storage_backend,
            checks=checks,
        )
        response = JSONResponse(status_code=503, content=body.model_dump(mode="json"))
        response.headers["X-Request-ID"] = _request_id(request)
        return response
    return HealthResponse(
        status="ok",
        storage_backend=settings.storage_backend,
        checks=checks,
    )


@app.get("/api/v1/tickers", response_model=list[TickerSummaryResponse])
async def list_ticker_summaries():
    settings = Settings.from_env()
    try:
        return PublicReadService(settings).list_summaries()
    except SupabaseError as exc:
        raise _storage_exception(exc) from exc


@app.get("/api/v1/watchlist", response_model=list[WatchlistEntryResponse])
async def get_watchlist():
    settings = Settings.from_env()
    try:
        return PublicReadService(settings).list_watchlist()
    except SupabaseError as exc:
        raise _storage_exception(exc) from exc


@app.get("/api/v1/tickers/{ticker}", response_model=TickerBundleResponse)
async def get_ticker(ticker: TickerPath):
    settings = Settings.from_env()
    try:
        bundle = PublicReadService(settings).load_ticker(ticker)
    except SupabaseError as exc:
        raise _storage_exception(exc) from exc
    if bundle is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return bundle


@app.post(
    "/api/v1/analyze/{ticker}",
    response_model=AnalysisRunResponse,
    status_code=202,
)
@app.post(
    "/analyze/{ticker}",
    response_model=AnalysisRunResponse,
    status_code=202,
    include_in_schema=False,
)
async def start_analysis(
    ticker: TickerPath,
    req: AnalyzeRequest | None = None,
    x_idempotency_key: str | None = Header(default=None, max_length=128),
):
    req = req or AnalyzeRequest()
    symbol = normalize_ticker(ticker)
    settings = _settings(req)

    if settings.storage_backend == "supabase":
        store = SupabaseAnalysisStore(settings)
        try:
            run_id = store.enqueue_run(
                symbol,
                market=req.market,
                settings=settings,
                idempotency_key=x_idempotency_key,
            )
        except SupabaseError as exc:
            raise _storage_exception(exc) from exc
        finally:
            store.close()
        return AnalysisRunResponse(run_id=run_id, ticker=symbol, status=JobStatus.PENDING)

    await _admit_local_run(settings)
    run_id = str(uuid.uuid4())
    jobs[run_id] = AnalysisRunResponse(
        run_id=run_id,
        ticker=symbol,
        status=JobStatus.PENDING,
    )
    task = asyncio.create_task(_run_local_analysis(run_id, symbol, settings, req))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return jobs[run_id]


async def _run_local_analysis(
    run_id: str,
    ticker: str,
    settings: Settings,
    req: AnalyzeRequest,
):
    job = jobs[run_id]
    job.status = JobStatus.RUNNING
    pipeline: AnalysisPipeline | None = None
    try:
        pipeline = AnalysisPipeline(
            settings,
            market=req.market,
            run_id=run_id,
        )
        briefing = await asyncio.wait_for(
            pipeline.run(ticker), timeout=settings.max_run_seconds
        )
        _local_results[run_id] = briefing
        job.status = JobStatus.COMPLETED
    except TimeoutError:
        job.status = JobStatus.FAILED
        job.error = "analysis exceeded the configured max_run_seconds"
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
    finally:
        if pipeline is not None:
            pipeline.close()
        await _release_local_run()


@app.get(
    "/api/v1/analysis-runs/{run_id}",
    response_model=AnalysisRunResponse,
)
@app.get(
    "/status/{run_id}",
    response_model=AnalysisRunResponse,
    include_in_schema=False,
)
async def get_status(run_id: str):
    settings = Settings.from_env()
    if settings.storage_backend == "supabase":
        store = SupabaseAnalysisStore(settings)
        try:
            run = store.get_run(run_id)
        except SupabaseError as exc:
            raise _storage_exception(exc) from exc
        finally:
            store.close()
        if not run:
            raise HTTPException(status_code=404, detail="Analysis run not found")
        return AnalysisRunResponse(
            run_id=run.id,
            ticker=run.symbol,
            status=run.status,
            error=run.error,
        )

    job = jobs.get(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return job


@app.get(
    "/api/v1/analysis-runs/{run_id}/result",
    response_model=Briefing,
)
async def get_result(run_id: str):
    settings = Settings.from_env()
    if settings.storage_backend == "supabase":
        store = SupabaseAnalysisStore(settings)
        try:
            briefing = store.load_briefing_for_run(run_id)
        except SupabaseError as exc:
            raise _storage_exception(exc) from exc
        finally:
            store.close()
    else:
        briefing = _local_results.get(run_id)

    if briefing is None:
        raise HTTPException(status_code=404, detail="Completed result not found")
    return briefing
