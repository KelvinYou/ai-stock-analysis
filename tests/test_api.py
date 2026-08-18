from __future__ import annotations

import time

from fastapi.testclient import TestClient

import stock_analysis.api.app as api
from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.synthesis import Briefing, ConvictionScore, RiskAssessment


def _briefing() -> Briefing:
    return Briefing(
        ticker="AAPL",
        date="2026-08-18",
        overall_signal=Signal.NEUTRAL,
        conviction=ConvictionScore(
            score=0.0,
            signal_convergence=0.5,
            explanation="mixed evidence",
        ),
        executive_summary="Research summary",
        bull_case="Bull case",
        bear_case="Bear case",
        key_uncertainties=[],
        catalysts_upcoming=[],
        risk_assessment=RiskAssessment(
            correlation_notes=[],
            max_drawdown_scenario="unknown",
        ),
        agent_signal_breakdown={},
    )


def _reset_local_state(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("API_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("ANALYSIS_MAX_CONCURRENT_RUNS", "10")
    api.jobs.clear()
    api._local_results.clear()
    api._local_quota_day = None
    api._local_accepted_runs = 0
    api._local_active_runs = 0


def test_openapi_exposes_versioned_run_contract_without_point_in_time_input():
    paths = api.app.openapi()["paths"]

    assert "/api/v1/analyze/{ticker}" in paths
    assert "/api/v1/tickers" in paths
    assert "/api/v1/tickers/{ticker}" in paths
    assert "/api/v1/watchlist" in paths
    assert "/api/v1/analysis-runs/{run_id}" in paths
    assert "/api/v1/analysis-runs/{run_id}/result" in paths
    assert "/results/{ticker}" not in paths
    assert paths["/api/v1/tickers"]["get"]["security"] == [{"BearerAuth": []}]
    assert "security" not in paths["/health/live"]["get"]
    assert api.app.openapi()["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
    request_schema = paths["/api/v1/analyze/{ticker}"]["post"]["requestBody"]
    schema = request_schema["content"]["application/json"]["schema"]
    assert any(
        item.get("$ref", "").endswith("/AnalyzeRequest")
        for item in schema["anyOf"]
    )


def test_invalid_cost_controls_use_error_envelope(monkeypatch):
    _reset_local_state(monkeypatch)

    with TestClient(api.app) as client:
        response = client.post("/api/v1/analyze/AAPL", json={"rounds": 4})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.headers["X-Request-ID"]


def test_invalid_ticker_is_rejected_before_enqueue(monkeypatch):
    _reset_local_state(monkeypatch)

    with TestClient(api.app) as client:
        analyze = client.post("/api/v1/analyze/bad_ticker")
        read = client.get("/api/v1/tickers/bad_ticker")

    assert analyze.status_code == 422
    assert read.status_code == 422
    assert analyze.json()["error"]["code"] == "validation_error"
    assert read.json()["error"]["code"] == "validation_error"
    assert not api.jobs


def test_idempotency_conflict_is_a_client_error():
    exc = api._storage_exception(
        api.SupabaseError("analysis_idempotency_conflict: request key is already bound")
    )

    assert exc.status_code == 409
    assert exc.detail == {
        "code": "idempotency_conflict",
        "message": "Idempotency key is already bound to a different request",
    }


def test_public_read_routes_use_versioned_response_contract(monkeypatch):
    _reset_local_state(monkeypatch)

    class FakePublicReadService:
        def __init__(self, _settings):
            pass

        def list_summaries(self):
            return [
                api.TickerSummaryResponse(
                    symbol="AAPL",
                    name="Apple Inc.",
                    market="US",
                    currency="USD",
                )
            ]

        def list_watchlist(self):
            return [
                api.WatchlistEntryResponse(
                    symbol="AAPL",
                    market="US",
                    group="tracked",
                )
            ]

        def load_ticker(self, symbol):
            return api.TickerBundleResponse(symbol=symbol.upper())

    monkeypatch.setattr(api, "PublicReadService", FakePublicReadService)

    with TestClient(api.app) as client:
        summaries = client.get("/api/v1/tickers")
        watchlist = client.get("/api/v1/watchlist")
        ticker = client.get("/api/v1/tickers/aapl")

    assert summaries.status_code == 200
    assert summaries.json()[0]["symbol"] == "AAPL"
    assert watchlist.status_code == 200
    assert watchlist.json()[0]["group"] == "tracked"
    assert ticker.status_code == 200
    assert ticker.json() == {
        "symbol": "AAPL",
        "fundamentals": None,
        "technicals": None,
        "price_history": [],
        "analyst_reports": None,
        "debate": None,
        "briefing": None,
    }
def test_point_in_time_input_is_rejected(monkeypatch):
    _reset_local_state(monkeypatch)

    with TestClient(api.app) as client:
        response = client.post(
            "/api/v1/analyze/AAPL",
            json={"as_of_date": "2026-08-18"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_bearer_token_protects_api_but_not_liveness(monkeypatch):
    _reset_local_state(monkeypatch)
    monkeypatch.setenv("API_BEARER_TOKEN", "test-token")

    async def fake_run(run_id, _ticker, _settings, _req):
        api.jobs[run_id].status = api.JobStatus.FAILED
        api.jobs[run_id].error = "test"
        await api._release_local_run()

    monkeypatch.setattr(api, "_run_local_analysis", fake_run)

    with TestClient(api.app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/api/v1/analysis-runs/missing").status_code == 401

        response = client.post(
            "/api/v1/analyze/AAPL",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["run_id"]
    assert "id" not in body


def test_run_scoped_result_is_returned_as_briefing(monkeypatch):
    _reset_local_state(monkeypatch)
    briefing = _briefing()

    async def fake_run(run_id, _ticker, _settings, _req):
        api.jobs[run_id].status = api.JobStatus.COMPLETED
        api._local_results[run_id] = briefing
        await api._release_local_run()

    monkeypatch.setattr(api, "_run_local_analysis", fake_run)

    with TestClient(api.app) as client:
        created = client.post("/api/v1/analyze/AAPL")
        run_id = created.json()["run_id"]
        for _ in range(20):
            result = client.get(f"/api/v1/analysis-runs/{run_id}/result")
            if result.status_code == 200:
                break
            time.sleep(0.01)

    assert result.status_code == 200
    assert result.json()["ticker"] == "AAPL"
    assert result.json()["overall_signal"] == "neutral"
