"""Supabase-backed persistence for the stock-analysis pipeline.

The local ``DataStore`` is intentionally kept as the offline/test backend. This
module provides the production backend with the same high-level operations, but
uses Supabase's PostgREST API so the Python package does not need a second SDK.

The important boundary is that Pydantic models remain the source of truth for
artifact payloads. Postgres stores those payloads as JSONB alongside typed
dates/status fields used for querying, freshness, and idempotency.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, Field

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.debate import DebateResult, ResearchVerdict
from stock_analysis.models.market_data import PriceBar, TechnicalSnapshot, TickerData
from stock_analysis.models.synthesis import Briefing

T = TypeVar("T", bound=BaseModel)

class SupabaseError(RuntimeError):
    """A useful error for a failed Supabase REST/RPC request."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SupabaseRestClient:
    """Small synchronous PostgREST client used by the worker and CLI."""

    def __init__(
        self,
        url: str,
        key: str,
        schema: str = "public",
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ):
        if not url or not key:
            raise SupabaseError(
                "Supabase storage requires SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY"
            )
        self.base_url = url.rstrip("/")
        self.schema = schema
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept-Profile": schema,
            "Content-Profile": schema,
        }

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = dict(self._headers)
        if body is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer

        response = self._client.request(
            method,
            f"{self.base_url}/rest/v1/{path.lstrip('/')}",
            params=params,
            json=body,
            headers=headers,
        )
        if response.is_error:
            detail = response.text.strip()
            raise SupabaseError(
                f"Supabase {method} {path} failed ({response.status_code}): {detail}",
                response.status_code,
            )
        if not response.content:
            return []
        try:
            return response.json()
        except ValueError as exc:
            raise SupabaseError(
                f"Supabase {method} {path} returned non-JSON content", response.status_code
            ) from exc

    def select(self, table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        result = self._request("GET", table, params=params)
        if not isinstance(result, list):
            raise SupabaseError(f"Expected a row list from {table}, got {type(result).__name__}")
        return result

    def select_all(
        self,
        table: str,
        params: dict[str, str] | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Read all rows without relying on the project API max-row setting."""
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page_params = dict(params or {})
            page_params["offset"] = str(offset)
            page_params["limit"] = str(page_size)
            page = self.select(table, page_params)
            rows.extend(page)
            if len(page) < page_size:
                return rows
            offset += page_size

    def upsert(
        self,
        table: str,
        rows: list[dict[str, Any]] | dict[str, Any],
        *,
        on_conflict: str,
    ) -> list[dict[str, Any]]:
        result = self._request(
            "POST",
            table,
            params={"on_conflict": on_conflict},
            body=rows,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return result if isinstance(result, list) else [result]

    def insert(
        self,
        table: str,
        rows: list[dict[str, Any]] | dict[str, Any],
    ) -> list[dict[str, Any]]:
        result = self._request("POST", table, body=rows, prefer="return=representation")
        return result if isinstance(result, list) else [result]

    def update(
        self,
        table: str,
        values: dict[str, Any],
        params: dict[str, str],
    ) -> list[dict[str, Any]]:
        result = self._request(
            "PATCH", table, params=params, body=values, prefer="return=representation"
        )
        return result if isinstance(result, list) else [result]

    def rpc(self, function: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        result = self._request("POST", f"rpc/{function}", body=payload)
        if result is None:
            return []
        return result if isinstance(result, list) else [result]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _as_date(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value[:10])


def _chunked(items: list[dict[str, Any]], size: int = 500):
    for start in range(0, len(items), size):
        yield items[start : start + size]


class CloudRun(BaseModel):
    id: str
    symbol: str
    market: str = "US"
    as_of_date: date
    status: str
    settings: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    attempts: int = 0


class SupabaseAnalysisStore:
    """Cloud equivalent of ``DataStore`` plus durable run/job operations."""

    def __init__(
        self,
        settings: Settings,
        *,
        run_id: str | None = None,
        client: SupabaseRestClient | Any | None = None,
    ):
        self.settings = settings
        self.client = client or SupabaseRestClient(
            settings.supabase_url or "",
            settings.supabase_service_key or "",
            schema=settings.supabase_schema,
        )
        self._run_id = run_id
        self._run_as_of: date | None = None

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close:
            close()

    # ------------------------------------------------------------------
    # Durable analysis runs

    def begin_run(
        self,
        ticker: str,
        as_of_date: date,
        settings: Settings | None = None,
        *,
        market: str = "US",
    ) -> str:
        symbol = ticker.upper()
        run_id = self._run_id or str(uuid.uuid4())
        values = {
            "id": run_id,
            "symbol": symbol,
            "market": market.upper(),
            "as_of_date": as_of_date.isoformat(),
            "status": "running",
            "settings": (settings or self.settings).pipeline_dump(),
            "started_at": _now(),
        }
        if self.settings.worker_id:
            values["worker_id"] = self.settings.worker_id
        # ``analysis_runs.symbol`` references ``tickers.symbol``. Keep this
        # order valid for a fresh ticker in real Postgres (the memory test
        # client does not enforce foreign keys).
        self.client.upsert(
            "tickers",
            {"symbol": symbol, "market": market.upper(), "updated_at": _now()},
            on_conflict="symbol",
        )
        self.client.upsert("analysis_runs", values, on_conflict="id")
        self._run_id = run_id
        self._run_as_of = as_of_date
        return run_id

    def complete_run(self, run_id: str | None = None) -> None:
        run_id = run_id or self._run_id
        if not run_id:
            return
        params = {"id": f"eq.{run_id}", "status": "eq.running"}
        if self.settings.worker_id:
            params["worker_id"] = f"eq.{self.settings.worker_id}"
        self.client.update(
            "analysis_runs",
            {
                "status": "completed",
                "completed_at": _now(),
                "lease_until": None,
                "error": None,
            },
            params,
        )

    def fail_run(self, run_id: str | None, error: str) -> None:
        run_id = run_id or self._run_id
        if not run_id:
            return
        params = {"id": f"eq.{run_id}", "status": "eq.running"}
        if self.settings.worker_id:
            params["worker_id"] = f"eq.{self.settings.worker_id}"
        self.client.update(
            "analysis_runs",
            {
                "status": "failed",
                "completed_at": _now(),
                "lease_until": None,
                "error": error[:4000],
            },
            params,
        )

    def enqueue_run(
        self,
        ticker: str,
        *,
        market: str = "US",
        as_of_date: date | None = None,
        settings: Settings | None = None,
        idempotency_key: str | None = None,
        max_daily_runs: int | None = None,
    ) -> str:
        symbol = ticker.upper()
        effective_settings = settings or self.settings
        rows = self.client.rpc(
            "enqueue_analysis_run",
            {
                "p_symbol": symbol,
                "p_market": market.upper(),
                "p_as_of_date": as_of_date.isoformat() if as_of_date is not None else None,
                "p_settings": effective_settings.pipeline_dump(),
                "p_request_idempotency_key": idempotency_key,
                "p_max_daily_runs": (
                    max_daily_runs
                    if max_daily_runs is not None
                    else effective_settings.max_daily_runs
                ),
                "p_quota_timezone": effective_settings.quota_timezone,
            },
        )
        if not rows or not rows[0].get("id"):
            raise SupabaseError("Supabase enqueue_analysis_run returned no run")
        return str(rows[0]["id"])

    def claim_run(
        self,
        worker_id: str,
        lease_seconds: int | None = None,
    ) -> CloudRun | None:
        lease_seconds = (
            lease_seconds if lease_seconds is not None else self.settings.worker_lease_seconds
        )
        rows = self.client.rpc(
            "claim_analysis_run",
            {"p_worker_id": worker_id, "p_lease_seconds": lease_seconds},
        )
        return CloudRun.model_validate(rows[0]) if rows else None

    def renew_run_lease(
        self,
        run_id: str,
        worker_id: str,
        lease_seconds: int | None = None,
    ) -> bool:
        lease_seconds = (
            lease_seconds if lease_seconds is not None else self.settings.worker_lease_seconds
        )
        rows = self.client.rpc(
            "renew_analysis_run_lease",
            {
                "p_run_id": run_id,
                "p_worker_id": worker_id,
                "p_lease_seconds": lease_seconds,
            },
        )
        return bool(rows and (rows[0].get("renewed") is True or rows[0].get("renewed") == "true"))

    def get_run(self, run_id: str) -> CloudRun | None:
        rows = self.client.select(
            "analysis_runs",
            {"id": f"eq.{run_id}", "select": "*", "limit": "1"},
        )
        return CloudRun.model_validate(rows[0]) if rows else None

    # ------------------------------------------------------------------
    # Layer 1: market data

    def _ensure_ticker(self, ticker: str, market: str | None = None) -> str:
        symbol = ticker.upper()
        values: dict[str, Any] = {"symbol": symbol, "updated_at": _now()}
        if market is not None:
            values["market"] = market.upper()
        self.client.upsert(
            "tickers",
            values,
            on_conflict="symbol",
        )
        return symbol

    def upsert_ticker_metadata(self, ticker: str, **metadata: Any) -> None:
        """Upsert public watchlist/fundamental metadata without a run."""
        symbol = ticker.upper()
        values = {key: value for key, value in metadata.items() if value is not None}
        values.update({"symbol": symbol, "updated_at": _now()})
        self.client.upsert("tickers", values, on_conflict="symbol")

    def last_price_bar_date(self, ticker: str) -> date | None:
        rows = self.client.select(
            "price_bars",
            {
                "symbol": f"eq.{ticker.upper()}",
                "select": "bar_date",
                "order": "bar_date.desc",
                "limit": "1",
            },
        )
        return _as_date(rows[0].get("bar_date")) if rows else None

    def _load_price_bars(self, ticker: str) -> list[PriceBar]:
        rows = self.client.select_all(
            "price_bars",
            {
                "symbol": f"eq.{ticker.upper()}",
                "select": "bar_date,open,high,low,close,volume",
                "order": "bar_date.asc",
            },
        )
        return [
            PriceBar(
                date=row["bar_date"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
            )
            for row in rows
        ]

    def load_price_history(self, ticker: str) -> list[PriceBar]:
        """Public price-history reader for cloud-native factor backtests."""
        return self._load_price_bars(ticker)

    def merge_market_data(self, ticker: str, data: TickerData) -> list[PriceBar]:
        """Upsert the incoming bars and return the full merged history.

        Only ``data.price_history`` is written. The ``(symbol, bar_date)``
        conflict target already makes a partial write idempotent, so rewriting
        the whole series would cost a full read *and* a full write to add the
        handful of bars an incremental fetch actually produces — which defeats
        the point of the incremental path in ``fetch.py``.

        The read stays full because ``compute_technicals`` needs a 200-day SMA
        and a 52-week high, and callers use the return value for exactly that.
        """
        symbol = self._ensure_ticker(ticker, data.info.market.value)
        incoming = {bar.date: bar for bar in data.price_history}
        existing = {bar.date: bar for bar in self._load_price_bars(symbol)}
        existing.update(incoming)
        merged = sorted(existing.values(), key=lambda bar: bar.date)

        rows = [
            {
                "symbol": symbol,
                "bar_date": bar.date.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in sorted(incoming.values(), key=lambda bar: bar.date)
        ]
        for chunk in _chunked(rows):
            self.client.upsert("price_bars", chunk, on_conflict="symbol,bar_date")

        as_of = merged[-1].date if merged else data.fetched_at.date()
        existing_snapshot = self._snapshot(symbol, as_of)
        fundamentals = data.model_dump(mode="json")
        fundamentals.pop("price_history", None)
        self.client.upsert(
            "market_snapshots",
            {
                "symbol": symbol,
                "as_of_date": as_of.isoformat(),
                "fetched_at": data.fetched_at.isoformat(),
                "fundamentals": fundamentals,
                "technicals": existing_snapshot.get("technicals") if existing_snapshot else None,
            },
            on_conflict="symbol,as_of_date",
        )
        return merged

    def save_market_data(self, ticker: str, data: TickerData) -> None:
        self.merge_market_data(ticker, data)

    def _snapshot(self, ticker: str, as_of_date: date) -> dict[str, Any] | None:
        rows = self.client.select(
            "market_snapshots",
            {
                "symbol": f"eq.{ticker.upper()}",
                "as_of_date": f"eq.{as_of_date.isoformat()}",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def _latest_snapshot(self, ticker: str) -> dict[str, Any] | None:
        rows = self.client.select(
            "market_snapshots",
            {
                "symbol": f"eq.{ticker.upper()}",
                "select": "*",
                "order": "as_of_date.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def load_market_data(self, ticker: str) -> TickerData | None:
        snapshot = self._latest_snapshot(ticker)
        if not snapshot:
            return None
        fundamentals = dict(snapshot.get("fundamentals") or {})
        fundamentals["price_history"] = [
            bar.model_dump(mode="json") for bar in self._load_price_bars(ticker)
        ]
        return TickerData.model_validate(fundamentals)

    def save_technicals(self, ticker: str, snapshot: TechnicalSnapshot) -> None:
        symbol = self._ensure_ticker(ticker)
        existing = self._snapshot(symbol, snapshot.as_of_date)
        self.client.upsert(
            "market_snapshots",
            {
                "symbol": symbol,
                "as_of_date": snapshot.as_of_date.isoformat(),
                "fetched_at": existing.get("fetched_at", _now()) if existing else _now(),
                "fundamentals": existing.get("fundamentals", {}) if existing else {},
                "technicals": snapshot.model_dump(mode="json"),
            },
            on_conflict="symbol,as_of_date",
        )

    def load_technicals(self, ticker: str) -> TechnicalSnapshot | None:
        snapshot = self._latest_snapshot(ticker)
        if not snapshot or not snapshot.get("technicals"):
            return None
        return TechnicalSnapshot.model_validate(snapshot["technicals"])

    # ------------------------------------------------------------------
    # Pipeline artifacts

    def _ensure_run(self, ticker: str, for_date: date | None = None) -> str:
        if self._run_id:
            return self._run_id
        return self.begin_run(ticker, for_date or date.today(), self.settings)

    def _save_artifact(
        self,
        stage: str,
        ticker: str,
        model: BaseModel,
        for_date: date | None,
    ) -> None:
        run_id = self._ensure_run(ticker, for_date)
        as_of = for_date or self._run_as_of or date.today()
        self.client.upsert(
            "analysis_artifacts",
            {
                "run_id": run_id,
                "symbol": ticker.upper(),
                "stage": stage,
                "as_of_date": as_of.isoformat(),
                "schema_version": 1,
                "payload": model.model_dump(mode="json"),
                "is_public": True,
            },
            on_conflict="run_id,stage",
        )

    def _load_artifact(
        self,
        stage: str,
        ticker: str,
        model_type: type[T],
        for_date: date | None,
    ) -> T | None:
        run = self._find_run(ticker, for_date)
        if not run:
            return None
        rows = self.client.select(
            "analysis_artifacts",
            {
                "run_id": f"eq.{run['id']}",
                "stage": f"eq.{stage}",
                "select": "payload",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return model_type.model_validate(rows[0]["payload"])

    def resume_artifact(self, stage: str, model_type: type[T]) -> T | None:
        """Return this run's already-persisted stage output, if any.

        ``_load_artifact`` deliberately reads only completed runs, so it cannot
        see the run currently in flight. A reclaimed run needs exactly that: the
        lease expires, the worker picks the run back up, and without this the
        pipeline would pay for Layer 2-4 again even though the artifacts are
        already durable. Keyed on ``(run_id, stage)``, same as the write.
        """
        if not self._run_id:
            return None
        rows = self.client.select(
            "analysis_artifacts",
            {
                "run_id": f"eq.{self._run_id}",
                "stage": f"eq.{stage}",
                "select": "payload",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return model_type.model_validate(rows[0]["payload"])

    def _find_run(self, ticker: str, for_date: date | None) -> dict[str, Any] | None:
        params = {
            "symbol": f"eq.{ticker.upper()}",
            "status": "eq.completed",
            "select": "id,symbol,as_of_date,status",
            "order": "as_of_date.desc,completed_at.desc",
            "limit": "1",
        }
        if for_date:
            params["as_of_date"] = f"eq.{for_date.isoformat()}"
        rows = self.client.select("analysis_runs", params)
        return rows[0] if rows else None

    def save_analyst_reports(
        self, ticker: str, reports: AnalystReports, for_date: date | None = None
    ) -> None:
        self._save_artifact("analyst_reports", ticker, reports, for_date)

    def load_analyst_reports(
        self, ticker: str, for_date: date | None = None
    ) -> AnalystReports | None:
        return self._load_artifact("analyst_reports", ticker, AnalystReports, for_date)

    def save_debate_result(
        self, ticker: str, result: DebateResult, for_date: date | None = None
    ) -> None:
        self._save_artifact("debate_result", ticker, result, for_date)

    def load_debate_result(
        self, ticker: str, for_date: date | None = None
    ) -> DebateResult | None:
        return self._load_artifact("debate_result", ticker, DebateResult, for_date)

    def save_research_verdict(
        self, ticker: str, verdict: ResearchVerdict, for_date: date | None = None
    ) -> None:
        self._save_artifact("research_verdict", ticker, verdict, for_date)

    def load_research_verdict(
        self, ticker: str, for_date: date | None = None
    ) -> ResearchVerdict | None:
        return self._load_artifact("research_verdict", ticker, ResearchVerdict, for_date)

    def save_briefing(
        self, ticker: str, briefing: Briefing, for_date: date | None = None
    ) -> None:
        self._save_artifact("briefing", ticker, briefing, for_date)

    def load_briefing(self, ticker: str, for_date: date | None = None) -> Briefing | None:
        return self._load_artifact("briefing", ticker, Briefing, for_date)

    def load_public_artifact(
        self,
        ticker: str,
        stage: str,
        model_type: type[T],
        for_date: date | None = None,
    ) -> T | None:
        """Load a completed artifact only when its public flag is true."""
        run = self._find_run(ticker, for_date)
        if not run:
            return None
        rows = self.client.select(
            "analysis_artifacts",
            {
                "run_id": f"eq.{run['id']}",
                "stage": f"eq.{stage}",
                "is_public": "eq.true",
                "select": "payload",
                "limit": "1",
            },
        )
        return model_type.model_validate(rows[0]["payload"]) if rows else None

    def load_briefing_for_run(self, run_id: str) -> Briefing | None:
        """Load only the completed briefing belonging to one run."""
        runs = self.client.select(
            "analysis_runs",
            {
                "id": f"eq.{run_id}",
                "status": "eq.completed",
                "select": "id",
                "limit": "1",
            },
        )
        if not runs:
            return None
        rows = self.client.select(
            "analysis_artifacts",
            {
                "run_id": f"eq.{run_id}",
                "stage": "eq.briefing",
                "is_public": "eq.true",
                "select": "payload",
                "limit": "1",
            },
        )
        return Briefing.model_validate(rows[0]["payload"]) if rows else None

    # ------------------------------------------------------------------
    # Backtest artifacts

    def save_backtest_artifact(
        self,
        *,
        mode: str,
        tickers: list[str],
        payload: dict[str, Any],
        markdown: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        artifact_id = str(uuid.uuid4())
        self.client.insert(
            "backtest_artifacts",
            {
                "id": artifact_id,
                "mode": mode,
                "symbols": tickers,
                "metadata": metadata or {},
                "payload": payload,
                "markdown": markdown,
            },
        )
        return artifact_id


def build_store(settings: Settings, *, run_id: str | None = None):
    """Select the configured backend without changing the local default."""
    if settings.storage_backend == "supabase":
        return SupabaseAnalysisStore(settings, run_id=run_id)

    # Imported lazily to keep the cloud module usable without touching local
    # paths and to avoid a module cycle during package startup.
    from stock_analysis.data.store import DataStore

    return DataStore(settings.data_dir)
