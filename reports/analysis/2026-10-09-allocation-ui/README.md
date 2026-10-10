# Allocation research UI verification

[Status: Warning] V1 historical research implemented; strategy reliability remains unconfirmed and V2 current plans remain disconnected.

## Scope and validation

- Six approved, hash-pinned experiments exported into a sanitized deployment asset. Python owns compounding and paired log excess; TypeScript only formats the results.
- Eight synthetic Python exporter tests pass, including reconciliation, nonfinite returns, incomplete observations, changed hashes and outside-manifest paths. Ruff passes for both exporter and tests.
- `npm run check:allocation` verifies the actual generated asset/checksum and rejects nine corrupt boundary cases. Missing AI metrics and genuine zero AI exposure/returns are explicitly distinguished.
- Production build passes, including TypeScript validation. Existing unrelated image/a11y warnings and dynamic share-card font warnings remain.
- Production evidence route returns 200 with a JSON attachment for `monthly-20`; unknown IDs return 404.
- Desktop browser accessibility state verifies default experiment, four strategy rows, chart descriptions, paired CI, percentage-point excess and historical selection labels. Mobile and theme visual inspection remains unverified because the shared native browser is being concurrently operated; no visual pass is claimed.

See `docs/design/momentum-analysis-ui.md` for refresh commands, scope and V2 boundaries. No live strategy activation, orders, personal holdings, backend migration or deployment was performed.
