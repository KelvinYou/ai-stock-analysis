# Portfolio pipeline upgrade — 2026-10-09

[Status: OK] Local implementation acceptance passed. This report records code
and contract validation, not a new performance backtest or a promotion decision.

Completed same-session US/USD runs now feed `POST /api/v1/portfolio-plans`.
The deterministic twelve-month/top-three allocator returns nine research views:
continuous hold, scheduled passive, allocator, FT weighted/agreement, AI and
their three allocator hybrids. Rejected sleeves retain cash; unavailable history
does not invent rankings. Run inputs and stored analyst/briefing stages bind to
the same cloud input hash. Local API snapshots bind to their original run IDs.
UTC captures/admission no longer inherit the Malaysian quota date.

The portfolio CLI exports inputs/plans and freezes, verifies, scores and compares
cohorts. It rejects premature outcome reads, changed artifacts, changed source
or numerical runtimes and overlapping outcome windows. Cohorts archive and hash
their Python source. Daily equity reconciles with episode returns, continuous
hold stays invested across episode gaps, and 0/10/20 bps fees apply to actual
entry/exit legs. Reports include daily drawdown, 21-session paired intervals
against hold and allocator, and DSR with nine comparisons.

Validation:

- Full Python regression: **359 passed**, four subtests; 13 new portfolio tests.
- Ruff, OpenAPI/Postman snapshots and generated architecture checks passed.
- Web typecheck and actual React SVG/layout passed: 24 nodes, 27 edges.
- Mermaid portability check passed. The derived [pipeline.svg](pipeline.svg)
  records the native graph; browser visual inspection was not performed.
- The CLI produced [synthetic-plan-final.json](synthetic-plan-final.json) from
  [synthetic-bundle.json](synthetic-bundle.json). These are artificial AAA–DDD
  fixtures with synthetic prices, not real forecasts or market performance.
  `synthetic-plan.json` preserves an earlier smoke before source archival was
  added; it is superseded by the final plan for implementation identity.
- Frozen v2 protocol and specification SHA-256 checks passed without alteration.
- Non-data Git whitespace checks passed. The global check reports pre-existing
  CSV CRLF whitespace in fetched market files; those files were not changed here.

[Status: Warning] Actual forward collection remains inactive. The prepared
protocol needs a complete exchange-calendar decision mapping, calendar source,
model and prompt identity before its first prospective cutoff. The collector
enforces those missing activation inputs instead of fabricating them. Assumed
fees, provider-adjusted returns, provider authenticity and incomplete search
history still prevent promotion. No paid model execution, remote deployment,
live trading or remote migration application occurred. The existing cloud
immutable-input migration is required and its remote application remains
unverified; cloud binding was validated with the storage contract fake.

Acceptance details and artifact hashes are in [verification.json](verification.json).
The implementation contract is
[portfolio-pipeline-upgrade.md](../../../docs/design/portfolio-pipeline-upgrade.md).
