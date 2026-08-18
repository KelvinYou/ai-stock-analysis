# Backend deployment

The production shape is two long-running services built from one image:

```text
Public HTTPS API -- bearer token --> Supabase queue <-- private worker -- API key --> Anthropic
```

The API is a control plane. In `STORAGE_BACKEND=supabase` mode it does not run
the LLM pipeline itself; the worker claims the durable `analysis_runs` row.
Do not expose the worker as a public HTTP service.

## 1. Supabase

Apply all migrations before starting either service:

```bash
supabase db push
```

The deployment-safety migration adds atomic run admission, heartbeat tracking,
and lease renewal. A fresh deployment must include:

```text
supabase/migrations/20260817000000_initial_analysis_schema.sql
supabase/migrations/20260818000000_deployment_safety.sql
supabase/migrations/20260818000001_public_summary_visibility.sql
supabase/migrations/20260818000002_queue_admission_contract.sql
```

## 2. Secrets and service configuration

API service:

```text
APP_ENV=production
STORAGE_BACKEND=supabase
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=server-only-key
API_BEARER_TOKEN=long-random-inbound-api-token
ANALYSIS_MAX_DAILY_RUNS=10
ANALYSIS_QUOTA_TIMEZONE=Asia/Kuala_Lumpur
# Local backend only; cloud parallelism is the number of worker replicas.
ANALYSIS_MAX_CONCURRENT_RUNS=1
ANALYSIS_MAX_RUN_SECONDS=1800
ANALYSIS_WORKER_LEASE_SECONDS=900
ANALYSIS_WORKER_HEARTBEAT_SECONDS=60
```

Worker service uses the same Supabase and limit settings, plus:

```text
ANALYSIS_WORKER_ID=stock-worker-1
ANTHROPIC_API_KEY=server-only-anthropic-key
```

`ANTHROPIC_API_KEY` is an outbound Claude credential. `API_BEARER_TOKEN`
protects this FastAPI. `SUPABASE_SERVICE_ROLE_KEY` is a third, separate secret.
None belongs in the web bundle or Git.

The production worker does not run `claude login` and does not mount
`~/.claude`. The pinned Python Agent SDK bundles the Claude Code CLI; the image
does not need a separate Node/npm installation for that mode.

## 3. Build and run

```bash
docker build -t ai-stock-analysis:deploy .
```

Run the two services separately from the same image:

```bash
docker run --rm -p 8000:8000 --env-file .env.api \
  ai-stock-analysis:deploy

docker run --rm --env-file .env.worker \
  ai-stock-analysis:deploy stock-analysis-worker
```

For a local production-like check, copy `.env.example` to `.env`, set
`APP_ENV=production`, fill the server secrets, and run:

```bash
docker compose up --build
```

Compose uses one local env file for convenience and explicitly clears
`ANTHROPIC_API_KEY` in the API container; managed platforms should configure
API and worker secrets separately.

The API listens on `0.0.0.0:${PORT:-8000}`. On platforms that inject `PORT`,
the image uses it automatically; locally it defaults to `8000`. The worker
command needs no public port and should have an automatic restart policy.

The Next.js dashboard is a separate service. Configure its server runtime with
the API origin and the same inbound token:

```text
STOCK_ANALYSIS_API_URL=https://YOUR_API
STOCK_ANALYSIS_API_TOKEN=the-same-value-as-API_BEARER_TOKEN
NEXT_PUBLIC_SITE_URL=https://YOUR_WEB_APP
```

These are server-only variables. Do not use `NEXT_PUBLIC_` for the API URL or
token, and do not put `SUPABASE_SERVICE_ROLE_KEY` in the web service. The web
server calls `/api/v1/tickers`, `/api/v1/tickers/{ticker}`, and
`/api/v1/watchlist`; the browser never receives the FastAPI bearer token.

## 4. API smoke flow

Liveness is public; other routes require the inbound bearer token.

```bash
curl -fsS https://YOUR_API/health/live

curl -fsS -X POST https://YOUR_API/api/v1/analyze/AAPL \
  -H "Authorization: Bearer $API_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: canary-aapl-2026-08-18" \
  -d '{"rounds":3,"model":"haiku","debate_model":"opus","market":"US"}'

curl -fsS https://YOUR_API/api/v1/analysis-runs/RUN_ID \
  -H "Authorization: Bearer $API_BEARER_TOKEN"

curl -fsS https://YOUR_API/api/v1/analysis-runs/RUN_ID/result \
  -H "Authorization: Bearer $API_BEARER_TOKEN"
```

The POST response contains `run_id`. Results are run-scoped; the public API
does not accept a caller-controlled `as_of_date` or `for_date`.

`X-Idempotency-Key` is bound to the complete request identity: ticker, market,
date, and pipeline settings. Reusing a key with a different request returns
`409 idempotency_conflict`; retrying the exact same request returns the original
run. Cloud enqueue accepts pending work, so the number of worker replicas—not
an API-side running-row count—controls actual parallelism.

For repeatable manual acceptance, import
[`postman/ai-stock-analysis.postman_collection.json`](../postman/ai-stock-analysis.postman_collection.json)
into Postman. Set `base_url`, `api_token`, and `ticker`; run Health and
Contract checks before the `Start paid canary` request. The canary starts a
real LLM job and should be run manually once, with its generated idempotency
key. The generated OpenAPI contract can be checked with:

```bash
python scripts/generate_openapi.py --check
python scripts/generate_postman.py --check
```

## 5. Deployment acceptance

Before enabling a real canary, verify:

- missing production secrets prevent API/worker startup;
- missing or incorrect bearer token returns `401`;
- `/health/live` returns `200`, and `/health/ready` reaches Supabase;
- the first run for a new ticker passes the ticker/run foreign key;
- repeating the same idempotency key returns the same `run_id`;
- the daily cost quota resets at the configured local midnight and returns
  `429` without creating a new run when exhausted;
- reusing an idempotency key with a different ticker or settings returns `409`;
- worker startup fails before claiming work when the bundled Claude CLI cannot
  execute its version check;
- invalid ticker characters return `422` without creating a local job;
- a worker run longer than the initial lease renews successfully;
- killing a worker allows lease expiry/reclaim and respects max attempts;
- one approved canary returns a Pydantic-valid briefing through the run-scoped result route.
