from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx

from stock_analysis.config import Settings
from stock_analysis.data.cloud import SupabaseAnalysisStore, SupabaseRestClient
from stock_analysis.data.watchlist import parse_watchlist
from stock_analysis.memory.cloud import SupabaseOutcomeStore
from stock_analysis.memory.outcomes import OutcomeRecord
from stock_analysis.models.agent_reports import (
    AnalystReports,
    Confidence,
    FundamentalsReport,
    MacroFXReport,
    SentimentReport,
    Signal,
    TechnicalReport,
)
from stock_analysis.models.market_data import Market, PriceBar, TickerData, TickerInfo
from stock_analysis.models.synthesis import Briefing


class MemoryClient:
    """Small PostgREST-shaped fake for storage contract tests."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []
        self.rpc_results: dict[str, list[dict[str, Any]]] = {}
        self.updates: list[tuple[str, dict[str, Any], dict[str, str]]] = []
        # Write volume is part of the storage contract here, not an
        # implementation detail: see test_merge_market_data_only_writes_incoming_bars.
        self.upserts: list[tuple[str, list[dict[str, Any]]]] = []

    def close(self) -> None:
        pass

    def _filtered(self, table: str, params: dict[str, str] | None) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.tables.get(table, [])]
        for key, value in (params or {}).items():
            if key in {"select", "order", "limit", "offset"}:
                continue
            if value.startswith("eq."):
                expected = value[3:]
                rows = [
                    row
                    for row in rows
                    if (
                        str(row.get(key)).lower() == expected.lower()
                        if isinstance(row.get(key), bool)
                        else str(row.get(key)) == expected
                    )
                ]
        order = (params or {}).get("order")
        if order:
            for expression in reversed(order.split(",")):
                field, _, direction = expression.partition(".")
                rows.sort(key=lambda row: row.get(field) or "", reverse=direction == "desc")
        offset = int((params or {}).get("offset", "0"))
        limit = int((params or {}).get("limit", str(len(rows))))
        return rows[offset : offset + limit]

    def select(self, table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        return self._filtered(table, params)

    def select_all(self, table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        return self._filtered(table, params)

    def upsert(
        self,
        table: str,
        rows: list[dict[str, Any]] | dict[str, Any],
        *,
        on_conflict: str,
    ) -> list[dict[str, Any]]:
        incoming = rows if isinstance(rows, list) else [rows]
        self.upserts.append((table, [dict(row) for row in incoming]))
        keys = on_conflict.split(",")
        stored = self.tables.setdefault(table, [])
        result = []
        for row in incoming:
            existing = next(
                (
                    item
                    for item in stored
                    if all(item.get(key) == row.get(key) for key in keys)
                ),
                None,
            )
            if existing is None:
                existing = dict(row)
                stored.append(existing)
            else:
                existing.update(row)
            result.append(dict(existing))
        return result

    def insert(
        self,
        table: str,
        rows: list[dict[str, Any]] | dict[str, Any],
    ) -> list[dict[str, Any]]:
        incoming = rows if isinstance(rows, list) else [rows]
        self.tables.setdefault(table, []).extend(dict(row) for row in incoming)
        return [dict(row) for row in incoming]

    def update(
        self,
        table: str,
        values: dict[str, Any],
        params: dict[str, str],
    ) -> list[dict[str, Any]]:
        self.updates.append((table, dict(values), dict(params)))
        rows = self._filtered(table, params)
        for row in self.tables.get(table, []):
            if row in rows:
                row.update(values)
        return rows

    def rpc(self, function: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        self.rpc_calls.append((function, payload))
        return [dict(row) for row in self.rpc_results.get(function, [])]


def _settings() -> Settings:
    return Settings(
        storage_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_service_key="server-secret",
    )


def _record(
    *,
    as_of: date = date(2026, 1, 1),
    exit_date: date | None = date(2026, 1, 31),
) -> OutcomeRecord:
    return OutcomeRecord(
        ticker="AAPL",
        as_of_date=as_of,
        horizon_days=30,
        signal=Signal.BUY,
        conviction_score=0.7,
        signal_convergence=0.8,
        entry_price=100.0,
        exit_date=exit_date,
        exit_price=105.0 if exit_date else None,
        realized_return=0.05 if exit_date else None,
    )


def test_pipeline_dump_excludes_cloud_credentials(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "env-secret")
    settings = Settings.from_env(
        storage_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_service_key="server-secret",
    )

    payload = settings.pipeline_dump()

    assert "server-secret" not in payload.values()
    assert "env-secret" not in payload.values()
    assert "supabase_service_key" not in payload
    assert "data_dir" not in payload
    assert "quota_timezone" not in payload


def test_rest_client_sends_supabase_headers_and_parses_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/tickers"
        assert request.headers["apikey"] == "publishable"
        assert request.headers["authorization"] == "Bearer publishable"
        assert request.headers["accept-profile"] == "public"
        return httpx.Response(200, json=[{"symbol": "AAPL"}])

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = SupabaseRestClient(
        "https://example.supabase.co",
        "publishable",
        client=http_client,
    )
    try:
        assert client.select("tickers") == [{"symbol": "AAPL"}]
    finally:
        http_client.close()


def test_analysis_store_creates_run_without_clobbering_worker_lease():
    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)

    run_id = store.begin_run("aapl", date(2026, 8, 14), _settings())

    run = client.tables["analysis_runs"][0]
    assert run["id"] == run_id
    assert run["symbol"] == "AAPL"
    assert run["status"] == "running"
    assert "lease_until" not in run
    assert client.tables["tickers"][0]["symbol"] == "AAPL"
    assert [table for table, _ in client.upserts[:2]] == ["tickers", "analysis_runs"]


def test_enqueue_run_uses_atomic_admission_rpc():
    client = MemoryClient()
    client.rpc_results["enqueue_analysis_run"] = [{"id": "run-1"}]
    settings = _settings().model_copy(
        update={"max_daily_runs": 4, "quota_timezone": "Asia/Kuala_Lumpur"}
    )
    store = SupabaseAnalysisStore(settings, client=client)

    run_id = store.enqueue_run(
        "aapl",
        market="us",
        as_of_date=date(2026, 8, 18),
        idempotency_key="request-1",
    )

    assert run_id == "run-1"
    assert client.rpc_calls == [
        (
            "enqueue_analysis_run",
            {
                "p_symbol": "AAPL",
                "p_market": "US",
                "p_as_of_date": "2026-08-18",
                "p_settings": settings.pipeline_dump(),
                "p_request_idempotency_key": "request-1",
                "p_max_daily_runs": 4,
                "p_quota_timezone": "Asia/Kuala_Lumpur",
            },
        )
    ]


def test_renew_run_lease_uses_run_and_worker_owner():
    client = MemoryClient()
    client.rpc_results["renew_analysis_run_lease"] = [{"renewed": True}]
    store = SupabaseAnalysisStore(_settings(), client=client)

    assert store.renew_run_lease("run-1", "worker-1", lease_seconds=120) is True
    assert client.rpc_calls == [
        (
            "renew_analysis_run_lease",
            {
                "p_run_id": "run-1",
                "p_worker_id": "worker-1",
                "p_lease_seconds": 120,
            },
        )
    ]


def test_terminal_run_updates_keep_the_active_worker_owner():
    client = MemoryClient()
    settings = _settings().model_copy(update={"worker_id": "worker-1"})
    store = SupabaseAnalysisStore(settings, client=client)

    store.complete_run("run-1")
    store.fail_run("run-1", "boom")

    assert client.updates[0][2] == {
        "id": "eq.run-1",
        "status": "eq.running",
        "worker_id": "eq.worker-1",
    }
    assert client.updates[1][2] == {
        "id": "eq.run-1",
        "status": "eq.running",
        "worker_id": "eq.worker-1",
    }


def test_claim_run_uses_sql_function_argument_names():
    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)

    assert store.claim_run("worker-1", lease_seconds=60) is None
    assert client.rpc_calls == [
        (
            "claim_analysis_run",
            {"p_worker_id": "worker-1", "p_lease_seconds": 60},
        )
    ]


def _analyst_reports() -> AnalystReports:
    return AnalystReports(
        fundamentals=FundamentalsReport(
            signal=Signal.BUY,
            confidence=Confidence.HIGH,
            pe_assessment="ok",
            margin_analysis="ok",
            debt_analysis="ok",
            growth_outlook="ok",
            key_risks=[],
            key_strengths=[],
            summary="summary",
        ),
        sentiment=SentimentReport(
            signal=Signal.NEUTRAL,
            confidence=Confidence.MEDIUM,
            news_tone="mixed",
            news_summary="summary",
            key_themes=[],
            notable_headlines=[],
            summary="summary",
        ),
        technical=TechnicalReport(
            signal=Signal.BUY,
            confidence=Confidence.MEDIUM,
            trend="up",
            rsi_assessment="ok",
            macd_assessment="ok",
            volume_assessment="ok",
            support_levels=[],
            resistance_levels=[],
            summary="summary",
        ),
        macro=MacroFXReport(
            signal=Signal.NEUTRAL,
            confidence=Confidence.LOW,
            fed_impact="unknown",
            interest_rate_outlook="unknown",
            sector_macro_factors=[],
            geopolitical_risks=[],
            summary="summary",
        ),
    )


def _ticker_data(bars: list[tuple[str, float]]) -> TickerData:
    return TickerData(
        info=TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            market=Market.US,
            sector="Technology",
            currency="USD",
        ),
        fetched_at=datetime(2026, 1, 6, tzinfo=UTC),
        price_history=[
            PriceBar(date=day, open=price, high=price, low=price, close=price, volume=1_000)
            for day, price in bars
        ],
    )


def test_merge_market_data_only_writes_incoming_bars():
    """A daily incremental fetch must not rewrite the whole series.

    The bug this pins: reading and re-upserting every bar turned a 1-row append
    into a full-history read *and* write, per ticker, per day.
    """
    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)
    store.merge_market_data("AAPL", _ticker_data([("2026-01-02", 100.0)]))

    client.upserts.clear()
    merged = store.merge_market_data("AAPL", _ticker_data([("2026-01-05", 101.0)]))

    price_writes = [rows for table, rows in client.upserts if table == "price_bars"]
    assert [row["bar_date"] for rows in price_writes for row in rows] == ["2026-01-05"]
    # The return value still carries the full merged history, because callers
    # feed it to compute_technicals (200-day SMA, 52-week high).
    assert [bar.date.isoformat() for bar in merged] == ["2026-01-02", "2026-01-05"]


def test_resume_artifact_reads_the_in_flight_run():
    """A reclaimed run must see its own durable stages, which are not 'completed'."""
    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)
    run_id = store.begin_run("AAPL", date(2026, 8, 14), _settings())
    assert store.resume_artifact("briefing", Briefing) is None

    reclaimed = SupabaseAnalysisStore(_settings(), run_id=run_id, client=client)
    reclaimed.save_analyst_reports("AAPL", _analyst_reports(), date(2026, 8, 14))

    resumed = reclaimed.resume_artifact("analyst_reports", AnalystReports)
    assert resumed is not None
    assert resumed.fundamentals.signal is Signal.BUY
    # `_load_artifact` still refuses it: the run has not completed, so no public
    # reader should be able to see it yet.
    assert reclaimed.load_analyst_reports("AAPL", date(2026, 8, 14)) is None


def test_public_artifact_reader_excludes_private_artifacts():
    client = MemoryClient()
    store = SupabaseAnalysisStore(_settings(), client=client)
    run_id = store.begin_run("AAPL", date(2026, 8, 14), _settings())
    client.tables["analysis_runs"][0]["status"] = "completed"
    reports = _analyst_reports()
    client.tables["analysis_artifacts"] = [
        {
            "run_id": run_id,
            "stage": "analyst_reports",
            "is_public": False,
            "payload": reports.model_dump(mode="json"),
        }
    ]

    assert store.load_public_artifact("AAPL", "analyst_reports", AnalystReports) is None

    client.tables["analysis_artifacts"][0]["is_public"] = True
    loaded = store.load_public_artifact("AAPL", "analyst_reports", AnalystReports)
    assert loaded is not None
    assert loaded.fundamentals.signal is Signal.BUY


def test_watchlist_markers_survive_the_python_side():
    entries = {
        entry.symbol: entry
        for entry in parse_watchlist(
            "\n".join(
                [
                    "#group: tracked",
                    "#theme: MY core banks",
                    "MY:1155",
                    "#group: candidate",
                    "AAPL",
                    "@us-major",
                    "# 5151 Hextar — a comment, not a ticker",
                ]
            )
        )
    }

    assert entries["1155"].market == "MY"
    assert (entries["1155"].group, entries["1155"].theme) == ("tracked", "MY core banks")
    # The theme persists across a group marker, matching web/lib/watchlist.ts.
    assert (entries["AAPL"].group, entries["AAPL"].theme) == ("candidate", "MY core banks")
    assert "@US-MAJOR" not in entries and len(entries) == 2


def test_cloud_outcomes_match_local_visibility_and_deduplication():
    client = MemoryClient()
    store = SupabaseOutcomeStore(_settings(), client=client)
    visible = _record()
    future = _record(as_of=date(2026, 2, 1), exit_date=date(2026, 8, 20))
    unresolved = _record(as_of=date(2026, 3, 1), exit_date=None)

    assert store.append([visible, visible, future, unresolved]) == 3
    assert store.append([visible]) == 0
    assert store.load("AAPL", before=date(2026, 8, 17)) == [visible]
    assert store.load("AAPL") == [visible, future, unresolved]
