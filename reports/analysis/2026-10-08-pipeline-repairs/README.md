# Pipeline review repairs — 2026-10-08

[Status: OK] All six review findings have code repairs and regression coverage.
[Status: Warning] The database migration has not been applied or executed locally.
These changes establish engineering consistency; they provide no new profitability
or promotion evidence.

| Finding | Result | Evidence |
| --- | --- | --- |
| Retry combines old reports with new market input | Complete typed input/cutoff sealed before analysts; stages bind to its SHA-256; retries never refetch. Unsealed partial legacy runs fail closed; completed public outputs remain readable. | Cloud input round-trip, corruption/mismatch rejection, full downstream retry integration with model calls stubbed |
| Negative or synthetic risk levels | Reject non-finite/non-positive ATR/close and invalid rounded level ordering; no zero-ATR fallback. | Negative-stop, zero/negative/NaN ATR regressions |
| Session bypasses execution input gate | Session and API backtests use the same RiskChecker plan eligibility. Gated neutral execution has zero conviction; raw scores remain recorded. New session manifest version 5. | One-bar execution decline and API/session score regressions |
| Live evidence remains single-period | US/MY share quarterly extraction with annual fallback, exact fiscal-end balance/cash matching, reporting currency and separately requested plain Close. Optional dated replay overlays financials, valuation, news and macro before sealing. | Mock mismatched periods, replay/store round-trip, real AAPL and 1155 fetches |
| News never expires | Settings owns a default 30-day cutoff-relative window; worker serialization preserves it. Explicit issuer financial-results releases are excluded from independent sentiment. | Old headline makes no model call; boundary/future-date and issuer-event regressions |
| Income plus derived margin counts twice | One income dimension; balance, cash flow, valuation and comparable multi-period growth contribute separately. Historical provider-current metadata cannot inflate confidence. | Single income/margin source is capped LOW; the same count is used in session calibration |

The final review also covered two retry compatibility boundaries: provider-current
metadata remains usable at its original captured cutoff after midnight, and input
hashes are checked against the stored raw payload before additive model defaults
are applied. Existing seals retain their original identity across additive fields.
Availability of live statements and valuation prices uses completion of provider
reads; no historical filing date or EPS/ADR basis is invented.

## Validation

- `pytest -q`: 338 passed, 4 subtests passed. One existing Starlette/httpx
  deprecation warning remains.
- `ruff check src tests scripts`: PASS.
- OpenAPI, Postman and generated architecture checks: PASS. Public route schema
  remains unchanged; typed input fields are persisted inside snapshots/seals.
- Web typecheck and server-rendered SVG/layout: PASS, 21 nodes, 20 canonical edges.
- Real read-only provider smoke: AAPL and Bursa 1155 each returned 251 bars,
  five financial periods, native statement currency and separate plain Close.
  See [live-smoke.json](live-smoke.json). No model calls were made.
- Frozen evidence: 107 original pilot files, four FT comparison input artifacts,
  135 backfill artifacts and 249 prospective files retain their sealed hashes.
  New implementation hashes are recorded separately in
  [verification.json](verification.json); old implementation checks are not relabelled.
- Scoped `git diff --check`: PASS. Existing CSV CRLF whitespace outside this
  repair scope remains untouched.

## Deployment and remaining evidence gaps

Apply [the migration](../../../supabase/migrations/20261008000000_immutable_run_inputs.sql)
before deploying workers. It revokes inherited table mutation/public access,
permits service-role select/insert, rejects updates even by a privileged role,
and binds version-2 stage hashes to their parent input using a foreign key.
A new disposable Postgres CI job applies all migrations and runs
[SQL contract assertions](../../../tests/sql/run_input_contract.sql). That job
has not run in this session: Docker daemon is unavailable and no local Postgres
server binary is installed. Memory-backed tests do not prove database enforcement.
No remote migration or deployment was performed.

The real live snapshots still lack a confirmed comparable year-ago duration and
common trailing-EPS share basis, so derived growth, P/E and market cap remain
unavailable. Observed current-provider quote valuation metadata stays distinct
from deterministic same-basis valuation. Optional replay can supply dated facts;
it cannot authenticate an unknown original vintage or complete news coverage.
Macro remains unavailable without a configured dated source.

No existing predictions/outcomes were regenerated, no strategy or consensus
threshold was tuned, and no new return result was produced. The old historical
sample, selected universe, assumed costs, incomplete independent news, and model
knowledge contamination limitations still apply. Profitability against long hold
requires a separate, frozen comparison with new forecasts.

Provider references: [financial statement API](https://ranaroussi.github.io/yfinance/reference/yfinance.financials.html)
and [price history API](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html).
Design and ownership: [input/execution contract](../../../docs/design/pipeline-input-execution-contract.md).
