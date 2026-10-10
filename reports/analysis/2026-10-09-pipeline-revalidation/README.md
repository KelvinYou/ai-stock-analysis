# Pipeline revalidation — 2026-10-09

[Status: OK] Local regression and contract checks pass after two additional repairs.
[Status: Warning] Database enforcement has not been executed locally; deployment
approval and profitability evidence are outside this result.

## Reproduced findings and repairs

1. **Session accepted an internal capture clock after its manifest cutoff.**
   A temporary copy of the MSFT 2025-09-01 packet kept its outer cutoff and all
   historical bars, but changed `ticker_data.fetched_at` to 2026-10-08 and supplied
   a 2026-10-07 headline. Before repair, `_load_sealed_packets` accepted it and
   calibration retained BUY with no gate reasons. This was a constructed input
   counterexample; the original historical packet was not changed.
   Session preflight now applies `validate_input` to every typed packet and checks
   its ticker/market identity. Calibration independently validates the capture
   cutoff and uses the prediction cutoff for news eligibility.
2. **Positive availability flags could bypass missing source evidence.**
   A typed one-bar packet with no fundamentals/macro could retain those BUY analyst
   calls when its flags claimed they were available. Calibration now intersects
   flags with actual financial/macro eligibility. Scoring uses actual eligibility
   for coverage counts too, including news recency and independent-source rules.
   The synthetic end-to-end scoring test confirms zero coverage for absent
   fundamentals, macro and sentiment, and neutral final execution.

Both issues extend the earlier session/production parity repair. They were
reproduced before editing, fixed, and covered by three new regressions in
`tests/test_pipeline_repairs.py`. No consensus threshold, strategy parameter,
universe, historical prediction or observed outcome was changed.

## Owner and consumer review

| Contract | Owner | Consumers | Verification | Result |
| --- | --- | --- | --- | --- |
| Capture cutoff and typed identity | run_input / market_data | session preflight and calibration | Future-capture regression; two original 96-packet panels still load | OK |
| Usable source eligibility | evidence helpers | analyst guards, session calibration and coverage | Absent-source and synthetic scoring regressions | OK |
| Valid execution levels | RiskChecker | production and session | Existing ATR/ordering and execution regressions | OK |
| Canonical flow | pipeline.json | generated architecture and web SVG | Generator, typecheck, SVG/layout checks | OK |
| Immutable cloud input and stage binding | cloud store / SQL migration | worker retry and public result readers | Python regressions pass; SQL execution unavailable | Warning |

## Verification

- Full Python suite: **341 passed, 4 subtests passed**. The existing Starlette/httpx
  deprecation warning remains.
- Ruff, OpenAPI, Postman and architecture snapshot checks: PASS.
- Web typecheck and rendered pipeline layout: PASS, 21 nodes and 20 edges.
- Frozen hashes: 107 original pilot files, 135 backfill artifacts, four FT input
  artifacts and 249 prospective files all match. Both old 96-packet panels remain
  accepted by the strengthened preflight.
- Real read-only fetch/prepare smoke: AAPL returned 251 bars and five financial
  periods; Bursa 1155 returned 246 bars and five financial periods. Both supplied
  native statement currency and separate plain Close. Both provider feeds returned
  zero headlines, so this smoke does not establish news-feed coverage; synthetic
  regressions exercise the recency policy.
- Docker inspection failed because the local daemon is not running. The migration
  and SQL assertions were **not executed**, and no remote database was touched.

See [verification.json](verification.json) for current source hashes and gate
results, and [live-smoke.json](live-smoke.json) for provider observations. The
2026-10-08 repair record remains unchanged and records its original implementation.
The only changed source files since that record are the session module and its
repair regression tests.

## Decision

**CONDITIONAL GO for the locally verified engineering changes.** Database
migration/permission/foreign-key behavior still requires the disposable Postgres
job in `.github/workflows/ci.yml`, followed by an explicitly authorized deployment.
This turn produced no new forecast return comparison and provides no evidence
that the pipeline beats long hold. Existing vintage, share-basis, news completeness,
survivorship, cost and model-contamination limitations remain.
