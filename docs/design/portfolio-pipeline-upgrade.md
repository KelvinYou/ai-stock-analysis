# Portfolio pipeline upgrade — Design-lite

**Author:** Codex **Date:** 2026-10-09 **Status:** Implemented locally; prospective collection inactive

## Outcome and scope

Completed single-ticker runs feed a deterministic portfolio stage through
`POST /api/v1/portfolio-plans`. It returns nine research target-weight views,
cash weights, momentum ranks, evidence/gate reasons and input identity. A CLI
exports the same plan and freezes/scores immutable forward cohorts. Existing
briefings remain the single-ticker output; no trade execution or automatic
promotion is added. The production graph and About page describe the actual path.

## Contracts

- New request: `{"run_ids": ["<completed run UUID>", "..."]}`; 3–50 unique runs,
  one ticker each, same decision and latest-bar date, US/USD only. Caller cannot
  supply evidence, outcome prices, historical cutoffs or model settings.
- Completed cloud inputs and analyst/briefing stages must share the stored input
  hash. Local API runs retain their own typed snapshots, never mix flat latest files.
- Shared signal guards and FT derivation own confidence/evidence/actionability;
  the session API retains import compatibility. No second arithmetic owner in web.
- Fixed 12-month/top-three ranking, equal one-third sleeves. Strict and scheduled
  passive views have all-name weights; filtered rejected sleeves remain cash.
  Missing/invalid/synchronized history is unavailable, not an invented momentum.
- Return schema is additive; OpenAPI/Postman are regenerated. No database table,
  migration, private holding read, remote deploy or paid model call is required.

## Implementation slices

1. Shared deterministic signal views and typed portfolio planner, with ranking,
   availability, neutral preservation and order-invariance tests.
2. Run-bound cloud/local adapter plus authenticated API and snapshot CLI.
3. Forward cohort seal/verify/score/compare path, with pre-entry clocks, exclusive
   writes, mature-only outcomes, fee accounting and fixed nine-arm comparisons.
4. Canonical `pipeline.json`, generated architecture, API contracts, About text,
   CLI instructions and full regression checks.

## Failure behavior and validation

Incomplete/legacy-unsealed/running/duplicate/mixed-market runs reject the plan
request. Missing history produces an unavailable plan with explicit cash-only
views; collectors reject it. Changed files or immature outcomes reject scoring
before fetch. A missed prospective cutoff is not relabeled a forward run.

Test API authorization and validation, input-to-artifact binding, deterministic
weights, FT isolation, cash/fee reconciliation and immutable/mature cohorts.
Run full Python tests, Ruff, OpenAPI/Postman/architecture checks and web type/layout
checks. Production deployment remains separate from implementation verification.

## Open constraints

No current result proves edge. Assumed costs and provider price-basis returns
remain research-only. Exact provider identities and licensed total-return/cost
evidence remain independent promotion gates. The new collector must report those
missing gates; it must not fabricate a provider attestation or rewrite old cohorts.

## Operational contract and acceptance

The nine-view planner, authenticated run-ID API and `stock-analysis-portfolio`
module CLI are implemented. API admission and new provider capture timestamps use
UTC, separate from the quota timezone. This prevents US after-close runs from
being relabeled as the next Malaysian day. Local snapshots live for the API
process lifetime; persistent export uses completed cloud runs. Existing cloud
storage requires the earlier immutable-input migration; this upgrade introduces
no further table or migration. Its remote application has not been verified.

The collector accepts only a same-session after-close freeze, on the actual
decision date. An activated prepared protocol must add `decision_sessions`
(a complete anchor-to-latest-completed-session mapping), `calendar_provenance`,
`model_provenance` and `prompt_provenance`. Closed-day anchors are collected on
their mapped prior session, before the next open; they are never shifted after
outcomes become known. All mapping dates must be no more than four calendar days
before their anchors. The collector checks the mapping shape and timing;
independent exchange-calendar/provider authenticity remains external evidence.
The immutable prepared v2 files remain unchanged. Record activation in a new
protocol artifact before the first decision cutoff; a missed first cutoff needs
a new future protocol version.

Frozen artifacts contain typed run inputs, all nine weights, protocol, hashes and
missing promotion evidence. Plans and manifests also pin a SHA-256 of the Python
source package and Python/NumPy/pandas/Pydantic versions. Each cohort archives
the Python source package under `implementation/stock_analysis`, and hashes
every archived file. Scoring and comparison reject a changed implementation;
use that archived source with the pinned numerical runtime for mature outcomes
rather than silently applying a later optimization. Scored artifacts bind the manifest and preserve
fills and daily price paths. Comparison rejects overlapping windows, changed
artifacts or inconsistent price bases. Hold purchases once and stays invested
through episode gaps; other arms enter/exit each episode. Daily equity reconciles
with compounded returns; costs are multiplicative 0/10/20 bps per side. Reports
include daily drawdown, 21-session paired log-return intervals against hold and
allocator, and episode DSR using nine comparisons. These statistics do not clear
the provider, total-return, cost-calibration or full-search-history gates.

No scheduler, live provider cohort, paid analysis, database application or remote
deployment was performed. Collection begins only with real completed inputs and
the required prospective activation identity, rather than relabeling a fixture.
