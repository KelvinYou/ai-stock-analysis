# Forward pipeline validation v2 — Prepared protocol

**Author:** Codex **Prepared:** 2026-10-09
**Status:** Rules specified; collection not activated; no promotion evidence

This document specifies a new research cohort. It does not rewrite the October 7
cohort or turn the September/October historical panels into a fresh holdout. The
existing long-hold optimization design remains the owner of the overall strategy.
Machine-readable rules and their digest are in
[`../../reports/analysis/2026-10-09-pipeline-gap-diagnostics-final/forward-protocol-v2.json`](../../reports/analysis/2026-10-09-pipeline-gap-diagnostics-final/forward-protocol-v2.json).

## Objective and fixed comparison

Primary hypothesis: the fixed 12-month/top-three momentum allocator exceeds
continuous equal-weight hold after costs on newly collected observations.
Secondary hypothesis: adding FT or AI labels improves that allocator. A secondary
arm must beat the allocator as well as hold; an allocator win alone is not AI alpha.

The curated US universe is fixed to AVGO, COST, MSFT, NVDA, ORCL, TSM, UNH and V,
matching the current research panel. This does not validate a market-wide edge.
Bursa is excluded from this protocol and requires its own currency/cost/universe
contract. No FX aggregation, borrowing, leverage, shorts or brokerage execution.

| Arm | Fixed rule |
|---|---|
| Continuous strict hold | Equal weight all eight names at first eligible Open; retain until last eligible exit Close |
| Scheduled passive | Equal weight all eight during each research episode; cash between episodes |
| Allocator only — primary | Rank trailing 12-calendar-month close returns at decision date; top three, equal one-third sleeves |
| FT weighted only | Guarded F/T labels with high/medium/low weights 1/0.75/0.5, neutral kept in denominator; top three eligible buys with lexical ties |
| FT agreement only | Same rule, additionally both F/T directions must match and be non-neutral |
| AI only | Final guarded BUY/STRONG_BUY; strength, conviction, symbol tie order; maximum three one-third sleeves |
| Allocator + FT weighted | Retain only FT-weighted buys inside the same momentum top three; rejected sleeves stay cash |
| Allocator + FT agreement | Retain only FT-agreement buys inside the same momentum top three; rejected sleeves stay cash |
| Allocator + AI | Retain only final AI buys inside the same momentum top three; rejected sleeves stay cash |

FT requires the existing actionability test (absolute consensus >0.30,
convergence >=0.40) and the shared RiskChecker eligibility. All missing-evidence,
input-cutoff, confidence and positive-ATR guards remain enforced. Sell means no
new long position in these sleeves. It is not a short or a forced sell of strict
hold. Neutral does not become a buy to fill the basket. Raw-buy guard bypass is
excluded: the October diagnostic counterfactual did not beat hold.

## Decision and execution calendar

The proposed first decision date is **2026-10-12**. Use 36 predetermined calendar
anchors 35 days apart. An anchor means the latest fully completed common US session
on or before that date; the run input must be captured and forecasts sealed after
that session closes and before the next common session opens. These are 30-day
episodes separated by gaps, not a continuous monthly rebalancing strategy.

For every anchor: enter at the first common-session Open strictly after the
decision date; exit at the first common-session Close on or after decision date
+30 calendar days. The manifest records the actual decisions and fill dates. The
same dates, price basis and eligible universe apply to all arms. Missing or
unsynchronized fills make that comparison unavailable; do not shorten the panel.

If inputs and forecast provenance cannot be sealed before the first entry, v2
does not activate. Pick a new future start in a new protocol version before any
outcomes are read. No backdated forecast or retrospective activation. The 36-anchor
schedule is fixed, not extended until a strategy wins. Descriptive checkpoints at
6, 12 and 24 completed anchors do not permit changing rules or early promotion.
One independent date cluster contributes at most one effective observation.

## Evidence and immutable provenance

1. Seal rules, code hashes, symbol/security identities, exact model/provider IDs,
   prompt/tool hashes, cost method and the full date schedule before first entry.
   Model aliases without a pinned identity are insufficient for confirmation.
2. Every dated input records its actual first-available clock. Use only completed
   bars and known filings/news/valuation/macro facts at the decision cutoff.
   Missing inputs cause the existing abstentions and remain in coverage reports.
3. Capture raw analyst directions/confidences, raw synthesis, final executable
   direction, every gate reason and risk-plan availability before observing any
   forward prices. Never transplant old forecasts onto newly enriched inputs.
4. Use the authenticated production-provider path for the primary AI track. If it
   is unavailable, the existing `session-prepare` -> predictions -> `session-score`
   track may collect a separately identified exploratory cohort; it does not satisfy
   provider confirmation. Record real model identity; never invent provider attestations.
5. Freeze each cohort with exclusive file creation and hashes; retry must use its
   sealed inputs. Resolve outcomes only after the exit session is completed. Store
   outcome prices separately from the forecast packet and verify all hashes first.
6. Preserve the old October 7 forward cohort as a separate version-1 research
   cohort. Its earliest score date is **2026-11-07 UTC**, checked by
   `backtest.prospective.score`; do not score or amend it early.

Prepared JSON is not an executable collection scheduler or a passing seal. The
existing prospective helper supports immutable single-date AI cohorts; it does
not yet collect all nine v2 arms. A nine-arm collector must preserve the above
rules and pass the acceptance tests below before v2 can activate.

## Accounting and statistical gates

The exploratory US cost assumption remains 10bps per side; 20bps is the fixed
stress. Report zero-cost returns separately as a diagnostic. Episode fees use
the current multiplicative entry/exit convention; preserve that convention for
the strict benchmark. Idle cash earns zero in the primary comparison. A dated
cash-yield proxy may be shown as a separate diagnostic.

Show daily marked-to-market equity, drawdown, trade count, capital use, missing
evidence by role, strict-hold excess and matched-exposure excess. Report the
allocator/AI incremental effect separately from deployment and timing differences.
Use 21-trading-day moving-block paired log-excess intervals, 2,000 resamples,
seed 0; retain effective portfolio-cluster N, PSR/DSR and all attempted candidates.
The nine rows count in within-run selection correction. Historical/manual search
must also be reconstructed or acknowledged as an unresolved selection gate;
within-run DSR alone does not clear repeated tuning.

Promotion requires all of the following on the locked final sample:

- Effective N >=30, positive net excess over strict hold and a positive lower
  95% paired block interval; DSR >=0.95 with the declared full search count.
- Positive excess at twice calibrated costs and drawdown no more than five
  percentage points worse than strict hold.
- For a hybrid: positive incremental excess over allocator-only and a positive
  lower paired interval; matched-exposure selection must be reported.
- Verified dividend/distribution, delisting and merger return treatment using
  actual ingested source data, plus externally calibrated execution costs.
- Authenticated AI provenance for any AI claim, sealed forecast coverage,
  reproducible outputs and no unresolved accounting/clock defects.

Failure, unavailable gates or too few independent observations means no promotion.
Current provider OHLC and assumed 10/20bps may support exploratory collection but
cannot satisfy verified total-return/cost gates. No data purchase is authorized.

## Acceptance and contract map

| Owner | Consumer | Acceptance |
|---|---|---|
| Prepared v2 rules and SHA-256 | Future collector | Reject changed rules or missing model/prompt identity before activation |
| Sealed forecast input | Analysts, FT derivation, momentum ranking | No post-cutoff facts; raw/final calls tied to one input hash |
| Fixed anchors | Episode collector and passive baselines | Next-session Open, common Close exits, no overlap or return-based omission |
| Frozen predictions | Outcome scorer | Verify before fetching outcomes; reject immature, duplicate or partial cohorts |
| Return-data/cost sources | All nine arms and promotion gate | Same source/basis/fees; missing terminal/distribution facts remain unavailable |
| Daily equity and search ledger | Statistical reports | All arms counted, endpoint drawdown cannot pass daily-drawdown gate |

Activation remains blocked on the nine-arm collector and exact provider/prompt
provenance. Promotion additionally remains blocked on source-complete returns,
calibrated costs and a mature forward sample. These are distinct gates; neither
document preparation nor the old historical allocator's win satisfies them.
