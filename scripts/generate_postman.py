#!/usr/bin/env python3
"""Generate or verify the repository's Postman acceptance collection.

The collection is generated from the same FastAPI application that produces
the OpenAPI snapshot.  Its assertions are intentionally small and operational:
health, auth, public reads, validation, enqueue, status, and a run-scoped
result.  The paid canary is marked clearly and should be run manually.

Usage:
    python scripts/generate_postman.py
    python scripts/generate_postman.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from stock_analysis.api.app import app

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "postman" / "ai-stock-analysis.postman_collection.json"
COLLECTION_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
REQUIRED_PATHS = {
    "/health/live",
    "/health/ready",
    "/api/v1/tickers",
    "/api/v1/watchlist",
    "/api/v1/tickers/{ticker}",
    "/api/v1/analyze/{ticker}",
    "/api/v1/analysis-runs/{run_id}",
    "/api/v1/analysis-runs/{run_id}/result",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _resolve_output(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _script(listen: str, lines: Iterable[str]) -> dict[str, Any]:
    return {
        "listen": listen,
        "script": {
            "type": "text/javascript",
            "exec": list(lines),
        },
    }


def _status_test(statuses: tuple[int, ...]) -> list[str]:
    if len(statuses) == 1:
        return [f"pm.response.to.have.status({statuses[0]});"]
    expected = ", ".join(str(status) for status in statuses)
    return [f"pm.expect([{expected}]).to.include(pm.response.code);"]


def _request(
    name: str,
    method: str,
    url: str,
    *,
    tests: Iterable[str] = (),
    headers: Iterable[dict[str, str]] = (),
    body: dict[str, Any] | None = None,
    auth: dict[str, Any] | None = None,
    description: str | None = None,
    prerequest: Iterable[str] = (),
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "method": method,
        "header": list(headers),
        "url": {"raw": url},
    }
    if auth is not None:
        request["auth"] = auth
    if description:
        request["description"] = description
    if body is not None:
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, ensure_ascii=False, indent=2),
            "options": {"raw": {"language": "json"}},
        }

    events: list[dict[str, Any]] = []
    prerequest_lines = list(prerequest)
    test_lines = list(tests)
    if prerequest_lines:
        events.append(_script("prerequest", prerequest_lines))
    if test_lines:
        events.append(_script("test", test_lines))

    item: dict[str, Any] = {"name": name, "request": request}
    if events:
        item["event"] = events
    return item


def _folder(name: str, *items: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "item": list(items)}


def _build_collection() -> dict[str, Any]:
    paths = app.openapi().get("paths", {})
    missing = sorted(REQUIRED_PATHS - set(paths))
    if missing:
        raise RuntimeError("FastAPI paths missing from Postman contract: " + ", ".join(missing))

    noauth = {"type": "noauth"}
    def array_tests(label: str) -> list[str]:
        return [
            *_status_test((200,)),
            f'pm.test("{label} is an array", function () {{',
            "    pm.expect(pm.response.json()).to.be.an('array');",
            "});",
        ]
    json_headers = [{"key": "Content-Type", "value": "application/json"}]

    return {
        "info": {
            "_postman_id": "7d4d6fb4-1b9e-4d1c-93f4-9f65d0e3c8f4",
            "name": "AI Stock Analysis API",
            "description": (
                "Acceptance collection for the deployed FastAPI control plane. "
                "Set api_token before running protected requests. The 'Paid canary' "
                "request starts a real LLM analysis and must be run manually."
            ),
            "schema": COLLECTION_SCHEMA,
        },
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{api_token}}", "type": "string"}],
        },
        "variable": [
            {"key": "base_url", "value": "http://localhost:8000", "type": "string"},
            {"key": "api_token", "value": "replace-with-api-bearer-token", "type": "string"},
            {"key": "ticker", "value": "AAPL", "type": "string"},
            {"key": "run_id", "value": "replace-after-canary", "type": "string"},
            {"key": "idempotency_key", "value": "postman-canary", "type": "string"},
        ],
        "item": [
            _folder(
                "Health",
                _request(
                    "Live",
                    "GET",
                    "{{base_url}}/health/live",
                    auth=noauth,
                    tests=[
                        *_status_test((200,)),
                        'pm.test("service is live", function () {',
                        '    pm.expect(pm.response.json().status).to.eql("ok");',
                        "});",
                    ],
                ),
                _request(
                    "Ready",
                    "GET",
                    "{{base_url}}/health/ready",
                    auth=noauth,
                    description="200 means storage is reachable; 503 is an actionable readiness failure.",
                    tests=[
                        *_status_test((200, 503)),
                        'pm.test("readiness has a status", function () {',
                        '    pm.expect(pm.response.json().status).to.be.oneOf(["ok", "not_ready"]);',
                        "});",
                    ],
                ),
            ),
            _folder(
                "Public dashboard reads",
                _request(
                    "List ticker summaries",
                    "GET",
                    "{{base_url}}/api/v1/tickers",
                    tests=array_tests("ticker summaries"),
                ),
                _request(
                    "List watchlist",
                    "GET",
                    "{{base_url}}/api/v1/watchlist",
                    tests=array_tests("watchlist"),
                ),
                _request(
                    "Load ticker bundle",
                    "GET",
                    "{{base_url}}/api/v1/tickers/{{ticker}}",
                    description="Use a ticker that has a completed public analysis; 404 is valid for an unknown ticker.",
                    tests=[
                        *_status_test((200, 404)),
                        'pm.test("known ticker bundle has a symbol", function () {',
                        '    if (pm.response.code === 200) pm.expect(pm.response.json().symbol).to.be.a("string");',
                        "});",
                    ],
                ),
            ),
            _folder(
                "Contract checks",
                _request(
                    "Reject missing bearer token",
                    "GET",
                    "{{base_url}}/api/v1/tickers",
                    auth=noauth,
                    description="Production-only auth check; development mode without API_BEARER_TOKEN intentionally permits the request.",
                    tests=[
                        *_status_test((401,)),
                        'pm.test("unauthorized error envelope", function () {',
                        '    pm.expect(pm.response.json().error.code).to.eql("unauthorized");',
                        "});",
                    ],
                ),
                _request(
                    "Reject point-in-time input",
                    "POST",
                    "{{base_url}}/api/v1/analyze/{{ticker}}",
                    headers=json_headers,
                    body={"as_of_date": "2026-08-18"},
                    description="Must return 422 before enqueueing anything; this request does not spend LLM budget.",
                    tests=[
                        *_status_test((422,)),
                        'pm.test("validation error envelope", function () {',
                        '    pm.expect(pm.response.json().error.code).to.eql("validation_error");',
                        "});",
                    ],
                ),
                _request(
                    "Reject invalid ticker",
                    "POST",
                    "{{base_url}}/api/v1/analyze/invalid_ticker",
                    headers=json_headers,
                    body={},
                    description="Must return 422 before local admission or cloud enqueue; this request does not spend LLM budget.",
                    tests=[
                        *_status_test((422,)),
                        'pm.test("ticker validation error envelope", function () {',
                        '    pm.expect(pm.response.json().error.code).to.eql("validation_error");',
                        "});",
                    ],
                ),
            ),
            _folder(
                "Analysis run",
                _request(
                    "Start paid canary",
                    "POST",
                    "{{base_url}}/api/v1/analyze/{{ticker}}",
                    headers=[
                        *json_headers,
                        {"key": "X-Idempotency-Key", "value": "{{idempotency_key}}"},
                    ],
                    body={
                        "rounds": 3,
                        "model": "haiku",
                        "debate_model": "opus",
                        "market": "US",
                    },
                    description=(
                        "COST WARNING: this enqueues a real analysis and may call four analyst "
                        "agents, debate rounds, and synthesis. Run manually once only."
                    ),
                    prerequest=[
                        'pm.collectionVariables.set("idempotency_key", "postman-canary-" + Date.now());',
                    ],
                    tests=[
                        *_status_test((202,)),
                        'pm.test("run was accepted", function () {',
                        "    var body = pm.response.json();",
                        '    pm.expect(body.run_id).to.be.a("string");',
                        '    pm.collectionVariables.set("run_id", body.run_id);',
                        "});",
                    ],
                ),
                _request(
                    "Get run status",
                    "GET",
                    "{{base_url}}/api/v1/analysis-runs/{{run_id}}",
                    description="Run after Start paid canary; 404 means run_id has not been set or is unknown.",
                    tests=[
                        *_status_test((200, 404)),
                        'pm.test("known run has a status", function () {',
                        '    if (pm.response.code === 200) pm.expect(pm.response.json().status).to.be.a("string");',
                        "});",
                    ],
                ),
                _request(
                    "Get run-scoped result",
                    "GET",
                    "{{base_url}}/api/v1/analysis-runs/{{run_id}}/result",
                    description="Poll until the run is completed; 404 is expected while it is still running.",
                    tests=[
                        *_status_test((200, 404)),
                        'pm.test("completed result has a briefing", function () {',
                        '    if (pm.response.code === 200) {',
                        '        var body = pm.response.json();',
                        '        pm.expect(body.ticker).to.be.a("string");',
                        '        pm.expect(body.overall_signal).to.be.a("string");',
                        "    }",
                        "});",
                    ],
                ),
            ),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="collection path (relative paths are resolved from the repository root)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 when the collection differs from the generated contract",
    )
    args = parser.parse_args()
    output = _resolve_output(args.output)
    rendered = _canonical_json(_build_collection())

    if args.check:
        if not output.exists():
            print(f"missing Postman collection: {output}", file=sys.stderr)
            return 1
        if output.read_text() != rendered:
            print(
                f"{output} is out of date — run: python scripts/generate_postman.py",
                file=sys.stderr,
            )
            return 1
        print(f"{output} is up to date")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_text() == rendered:
        print(f"{output} already up to date")
        return 0
    output.write_text(rendered)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
