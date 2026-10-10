# Quant and contract review

[Status: Warning] GO for descriptive offline diagnosis. No promotion or live
strategy change: the historical sample is inspected, small, survivor-selected
and incomplete. Prepared forward rules are not an activated collection service.

## Scope and ownership

| Contract | Owner | Consumers | Version/migration | Verification | Result |
|---|---|---|---|---|---|
| Raw versus guarded forecast | Existing sealed session predictions and result | Diagnostic partitions and counterfactual adapter | New additive offline report; old records unchanged | Complete 96-key identity, source hashes, synthetic partitions | OK |
| Refusal reasons | Existing session guards | Diagnostic trace | Overlapping reason codes kept; sell approval is not a long trade | Exact same 32 calls have actionability/risk codes | OK |
| Portfolio accounting | `backtest/portfolio.py` | Twelve-row full-panel diagnostic | No production change or migration | Existing strategy returns/trades unchanged; cost/P&L reconciliation | OK |
| Momentum and non-overlap selection | Existing allocator and date-only subset helper | Eight episode arms | Separate window-level experiment | Outcome mutation and reverse-order tests; independent fee checks | OK |
| FT ablation ranking | Offline adapter | Existing generic signal ablation | Equal FT buy strength, lexical ties; no AI conviction | Synthetic FT/AI rank separation | OK |
| Statistical meaning | `backtest/stats.py` | DSR, intervals, permutation reports | Twelve/eight within-comparison counts; all-history count unresolved | N=7/9, interval and permutation limits explicit | Warning |
| Forward v2 rules | New forward specification and hashed JSON | Future nine-arm collector | New prospective version; old cohort preserved | Schedule/links/hashes checked; activation null | Warning |
| Public/private boundary | Stock subrepository public research data | Reports and internal design docs | No private finance imports; no API/schema/DB changes | Scoped reads and diff inspection | OK |

## Verified findings

- [Status: OK] `research_pipeline_gaps.py` fixes the sample, arms and rules before
  computing returns; it preserves the runner and refuses existing output folders.
  It invokes no provider, model or price-fetch path. Historical ranking reads closes
  on/before each signal date; outcomes enter only after the basket is selected.
- [Status: OK] Counterfactual raw buys are labeled guard-bypass research and do
  not alter the executable pipeline, risk thresholds, forecast memory or holdings.
  Their positive point return is paired with N/DSR/CI and remains below hold.
- [Status: OK] FT-only and FT-filtered comparisons reuse guarded labels. An
  explicit constant rank score prevents importing AI conviction into an FT claim.
- [Status: Warning] Episode fees/drawdowns differ from full-panel accounting;
  the report identifies multiplicative episode fees and endpoint-only drawdown,
  including the resulting +20.62% versus +20.66% hold difference.
- [Status: Warning] The conditional FT selection interval is positive, but its
  permutation p=0.0835 on six informative windows does not establish robust alpha.
  Full hybrid return remains below the allocator. All prior tuning has not been
  reconstructed, so eight-row DSR cannot clear repeated-search bias.
- [Status: Warning] Future provider/prompt identities and nine-arm collection
  are absent. Prepared rule hashes are not provider attestations. Licensed return
  completion, calibrated costs and a mature new sample remain promotion gates.

## Verification

- Focused Python suite: **78 passed, 4 subtests passed**, including four new
  diagnostic tests and existing portfolio/allocator/ablation regressions.
- Ruff for new script/tests and scoped Git whitespace checks: passed.
- Independent episode accounting: 243 reconciliations; all full-panel/episode
  order-reversal checks passed and the 107 original pilot files retain their hashes.
- October 7 forward cohort: 31 immutable forecasts verified; November 7 maturity
  remains enforced. No scoring call was made.
- Prepared protocol and specification digests, calendar uniqueness, local document
  links, full-panel gap identities and old-strategy trade/return equality checked.

API, frontend, database migration/deployment and production flow changes are out
of scope; no tests of changed behavior in those layers are claimed. No commit,
paid model call, data subscription purchase or brokerage action occurred.
