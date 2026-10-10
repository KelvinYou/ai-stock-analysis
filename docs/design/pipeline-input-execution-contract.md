# Pipeline input and execution contract repair

[Status: OK] Six code repairs implemented and locally validated.
[Status: Warning] Database execution/deployment remains pending; see the validation record.

## Acceptance and scope

The 2026-10-08 review reproduced: resumed old reports paired with freshly fetched
prices; negative stops and zero-ATR synthetic fallback; session buys that the
production execution gate declines; empty multi-period live input; indefinitely
old news entering sentiment; derived margin/income counted as independent inputs.
Acceptance follows the research-only pipeline's point-in-time and fail-closed
contracts. Existing scored artifacts and prospective forecasts remain immutable.

## Design-Lite and work sequence

1. Risk levels: reject non-finite/non-positive ATR or prices and invalid ordering.
   Both production and session execution use the same pure input/plan validator.
2. Run isolation: seal a complete typed input, cutoff and canonical SHA-256 before
   analyst work. Resume only that input and hash-bound stage artifacts. Current
   provider input cannot initialize an explicitly historical job. Legacy in-flight
   artifacts without a provable input fail closed; completed public results load.
3. Live evidence: share US/MY extraction of dated quarterly/annual history. Match
   balance/cash observations by fiscal end/duration; never match by column position.
   Provider-current frames are marked as observed today, not original-vintage proof.
   Dated plain Close is separate from technical adjusted bars; no price/share/EPS
   basis or currency is invented. Optional replay supplies authoritative dated
   evidence; unavailable macro remains explicit.
4. News: configurable recent window owned by Settings. Preserve historical facts
   in raw archives; only timely facts can enter sentiment or its availability gate.
   Financial/earnings announcements are not independent sentiment confirmation.
5. Confidence: one income statement (income plus derived margins) is one evidence
   dimension. Comparable growth, dated valuation, matched balance and same-period
   cash flow contribute separately; current metadata cannot inflate historical
   confidence. Analyst reports expose stable evidence diagnostics where useful.
6. Integration: update the canonical flow and generated docs, API schema and
   settings serialization. Add regressions through fetch, pipeline/retry, source
   guards and session scoring; review without tuning old outcomes.

```text
live source / optional dated replay [MODIFIED]
  -> dated evidence preparation [MODIFIED]
  -> run input snapshot + hash [NEW]
  -> analysts -> debate -> synthesis [MODIFIED: hash-bound resume]
  -> consensus -> shared execution eligibility [MODIFIED]
  -> validated levels -> research output
```

## Owner and consumers

| Contract | Owner | Consumers | Compatibility / acceptance |
| --- | --- | --- | --- |
| Dated financial units/periods | market_data + financial context | live fetchers, fundamentals, replay | Additive; legacy statements readable; no invented basis |
| News recency | Settings + evidence filter | live/session, sentiment, evidence envelope | New configurable window; no sealed packet rewrite |
| Run input hash | run input storage | orchestrator, cloud stage resume | New SQL migration; service-only inputs; old completed outputs readable |
| Execution eligibility | RiskChecker/shared pure validator | runner + session scorer | New session implementation version; old results immutable |
| Confidence dimensions | FundamentalsAgent | synthesis/convergence | No threshold adjustment or outcome calibration |
| Pipeline shape | pipeline.json | React SVG + generated architecture | Regenerate both consumers' checks |

## Failure and rollout

| State | Behavior |
| --- | --- |
| Missing immutable input with durable partial stages | Refuse resume; new job required |
| Corrupt input or stage hash | Refuse before further LLM calls |
| Provider capture after explicit historical cutoff | Refuse live fallback |
| Missing filing history or unclear native/ADR currency | Preserve uncertainty; no synthetic valuation |
| Stale/earnings-only news | Not independent sentiment evidence |
| Invalid ATR or rounded price ordering | Null action plan with reason; neutral execution |

SQL changes are delivered as a migration, not applied to a remote deployment.
No trades, paid model calls, commits, pushes or promotion decisions are in scope.
Offline mocks/source replay establish behavior; real provider/DB deployment
verification is reported separately. Frozen evidence hashes record the old
implementation; a new implementation must not relabel those historical checks.

## Open decisions

No additional user decision is required for the six authorized corrections.
Defaults for news recency are explicit research policy, configurable and disclosed.
Original-vintage data licensing, production migration application and fresh
profitability forecasts remain distinct from this engineering repair.

## Delivery evidence

[Repair record](../../reports/analysis/2026-10-08-pipeline-repairs/README.md)
contains regression counts, real US/MY source smoke and immutable historical
artifact checks. Canonical graph and generated documentation now show input
isolation and shared risk eligibility. Disposable SQL CI checks enforce service
privileges and stage/input binding; they have not executed in this local session.
Current capture metadata is anchored to its capture cutoff across midnight;
stored raw input hashes survive additive typed-model defaults.
