# Supabase deployment

This repository supports two storage backends:

- `STORAGE_BACKEND=local` keeps the existing flat `data/` workflow for offline
  development and tests.
- `STORAGE_BACKEND=supabase` makes Supabase the canonical store. The Python
  process holds the current pipeline in memory and writes market snapshots,
  stage artifacts, outcomes, and backtest reports to Postgres.

## 1. Create the schema

Run the migration in the Supabase SQL editor or through the Supabase CLI:

```bash
supabase db push
```

The migration is:

```text
supabase/migrations/20260817000000_initial_analysis_schema.sql
```

It creates the typed market tables, immutable analysis artifacts, durable run
queue, idempotency key, public summary view, and RLS policies. Do not add a
service key to Git.

## 2. Configure the Python worker

Copy `.env.example` to `.env` and fill it in. Every CLI (`stock-analysis`,
`stock-fetch`, `stock-analysis-backtest`, `stock-analysis-worker`, and the
importer) calls `load_env()` as its first statement, so no exports are needed:

```bash
cp .env.example .env   # then set STORAGE_BACKEND=supabase + URL + secret key
stock-analysis-worker
```

`load_env` is deliberately *not* called from `Settings.from_env`. The library
stays hermetic, so a checked-out `.env` pointing at production cannot leak into
the test suite — `tests/test_env_loading.py` pins that boundary. Real
environment variables always beat the file, so a one-off
`STORAGE_BACKEND=local stock-fetch AAPL` still works.

Use the new-style `sb_secret_...` key. The legacy `service_role` JWT still
authenticates but Supabase is deprecating it; the publishable/anon key cannot
write and the importer's preflight now rejects it explicitly.

### Behind a TLS-inspecting proxy

If HTTPS on your network is intercepted (a corporate root CA in the OS trust
store, absent from certifi), install the optional extra:

```bash
pip install -e ".[proxy]"
```

`stock_analysis/__init__.py` then routes TLS through the OS verifier via
`truststore`. This also sidesteps proxy CAs that are not RFC 5280 conformant,
which Python 3.13+ rejects outright because it enables `VERIFY_X509_STRICT`.

Node needs the same trust separately, and `NODE_EXTRA_CA_CERTS` is read before
Next.js loads `.env.local`, so it lives in `web/package.json`'s scripts and
points at a gitignored `.corp-ca.pem`. Extract one with:

```bash
security find-certificate -a -p /Library/Keychains/System.keychain > .corp-ca.pem
```

A missing file is a no-op for Node, so this is inert on a clean network.

The API is only a control plane in cloud mode. It inserts a pending
`analysis_runs` row; the worker claims it and runs the existing Python/Claude
pipeline:

```bash
STORAGE_BACKEND=supabase uvicorn stock_analysis.api.app:app --host 0.0.0.0 --port 8000
STORAGE_BACKEND=supabase stock-analysis-worker
```

Use `X-Idempotency-Key` on `POST /analyze/<ticker>` when a client may retry the
request. The same key returns the existing run instead of starting another
LLM job.

### Retry semantics

`claim_analysis_run` caps attempts at 3 (`p_max_attempts`). A worker that exits
cleanly marks its own run `failed`, which is terminal. A worker killed hard
(OOM, SIGKILL) cannot, so its run stays `running` until the lease expires and is
then reclaimed — up to the cap, after which the run is retired as `failed` with
an `abandoned after N attempt(s)` error. Without that cap a job that always
crashes would re-run a full Opus debate on every lease expiry, indefinitely.

Reclaiming is cheap because each layer's artifact is written as it finishes and
keyed `(run_id, stage)`. `AnalysisPipeline` reads those back before re-entering a
layer, so a reclaimed run resumes at the first unfinished stage instead of paying
for Layer 2-4 again.

## 3. Configure Next.js

The web app only needs the publishable/anon key for public, read-only queries:

```text
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
NEXT_PUBLIC_SITE_URL=https://your-site.example
```

`NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` are also accepted. Never put
`SUPABASE_SERVICE_ROLE_KEY` in the web environment.

When cloud variables are present, `web/lib/data.ts` reads `tickers`,
`latest_ticker_summary`, `market_snapshots`, `price_bars`, and
`analysis_artifacts`. It no longer needs a local `data/` directory.

The local reader is a **separate mode, not a fallback**: the backend is chosen
by whether the two env vars are set, and a failed cloud query raises rather than
silently reading `data/`. That is deliberate — a dashboard quietly serving a
stale local snapshot is worse than one that errors. Transient blips are absorbed
by ISR (`revalidate: 60`), which keeps serving the last good render.

## 4. Import existing files

First verify the import without writing:

```bash
STORAGE_BACKEND=supabase \
SUPABASE_URL=https://YOUR_PROJECT.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_SERVICE_KEY \
python scripts/import_to_supabase.py --data-dir data --dry-run
```

`--dry-run` writes nothing but still contacts Supabase: it selects from every
target table and the summary view, so a missing migration, wrong schema, or bad
key fails here rather than halfway through the real import. It also pre-checks
local records against the table `check` constraints and warns on violations.

Then run it once without `--dry-run`. It is idempotent for the current flat
briefing snapshot and upserts price bars/outcomes; a briefing whose run is
already `completed` is left untouched rather than reset to `running`, so
re-running the importer does not blank live ticker pages. Verify ticker counts
and a few ticker pages before switching scheduled fetches to cloud mode.

Two things the import carries that are easy to miss:

- **Watchlist grouping.** `watch_group` and `theme` exist only as `#group:` /
  `#theme:` markers in `tickers.txt`. Both the importer and `stock-fetch` parse
  them via `stock_analysis.data.watchlist`, which must stay in sync with
  `web/lib/watchlist.ts`. Without them the dashboard renders every ticker as an
  ungrouped candidate.
- **Ticker metadata.** `name`, `sector`, `industry`, and `currency` are written
  to `tickers` on every fetch, not just at import — the screener reads those
  columns, not the snapshot JSON.

## 5. Cutover rule

With `STORAGE_BACKEND=supabase` in `.env`, fetch, analysis, backtest, API, and
web all read and write Postgres. Do not run a local writer and the cloud writer
for the same ticker concurrently.

`data/` is frozen at the cutover snapshot: cloud mode never writes to it, and
nothing currently exports back to it. That means the git history of `data/`
stops being an audit trail — the `data: fetch <date> (N/N ok)` commits end here.
If that trail matters, write an exporter before deleting the directory; until
then `data/` is a static backup of the pre-cutover state, not a live mirror.

