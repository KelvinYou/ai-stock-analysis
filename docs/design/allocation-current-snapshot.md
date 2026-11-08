# Allocation current snapshot — Design-Lite

Author: Codex. Status: Implementation authorized by owner. Updated: 2026-10-27.

## 1. Context

The owner approved a VT comparison, a current allocation view and refreshed
TSM/V/UNH research. The current page exposes only frozen historical selections.
Current price ranking must not appear to be a sealed portfolio plan or confirmed edge.

## 2. Scope

| Capability | Owner | Change |
|---|---|---|
| Current 12-month ranking | Python snapshot builder | Same-session eight-name coverage, dated scores and top-three research weights |
| Current snapshot tab | Approved export and web | Preview table, source date, stale suppression and explicit monthly cadence |
| VT diagnostic | New dated research runner | Same captured price vintage, allocator dates, assumed cost stresses and paired intervals |
| Candidate research | In-session pipeline | Four analyst roles, two debate rounds, actual deterministic risk calculation |

No orders, personal sizing, provider attestations or promotion status changes.

## 4. Proposed architecture

```text
Captured public prices -> Python snapshot [NEW] -> hash-pinned export [MODIFIED]
                                                   -> snapshot tab [MODIFIED]
Captured public prices -> fixed-rule VT diagnostic [NEW]
```

Python owns ranking; TypeScript validates and renders it. The existing
`current_plan` stays unavailable because an indicative ranking is not a sealed plan.
Add optional `current_momentum` to v1: legacy exports still load and show unavailable.
Its available shape includes `as_of`, `captured_at_utc`, `source_sha256`,
`lookback_months:12`, `top_n:3`, `scope:indicative_price_only`, `universe`,
and `ranking:[{ticker,score,lookback_date,target_weight}]`. Missing or inconsistent
inputs produce `status:unavailable,reason`; no partial ranking is published.
The current data source is allowlisted in the existing manifest and hash verified.

## 7. Trade-offs

A captured, hash-pinned export fits the current read-only dashboard and keeps
network calls out of page loads. It needs an explicit refresh command. A live
broker/API planner adds credentials and run-binding requirements that this feature
does not need. The view therefore states its observation date and remains a preview.

## 8. Rules, failure handling and verification

- All eight latest bars must share a completed session; missing/duplicate/nonfinite
  dates and prices, future bars, missing 12-month anchors and stale inputs fail closed.
- Reuse the portfolio's four-calendar-day freshness boundary; it is an age check,
  not proof of the latest exchange session. The page rechecks age at render time.
- Fixed top three, equal one-third research weights, including when all scores are
  negative. No AI veto or implicit cash filter. Ties use lexical ticker ordering.
- A daily snapshot previews the next month-end ranking; it does not authorize daily rotation.
- VT is held continuously with entry/exit proportional fees, same exact first/last
  Opens as the allocator and daily-close marks. All cost/block scenarios are declared
  before computation. No total-return or broker-calibration pass is inferred.
- Public exports contain market facts only. No private holdings or personal targets.
- Tests cover ranking, stale/mixed inputs, old export compatibility, malformed web
  payloads and visible current snapshot behavior. Python owns all return arithmetic.

## 9. Open questions

What amount belongs to an eventual personal momentum sleeve? Owner decision;
this feature displays research weights and does not require that answer.
Will a future sealed execution plan replace the preview? Defer until provenance,
cost and forward-sample contracts are satisfied.

## Work sequence

1. Capture nine public price series and freeze hashes/config before the VT run.
2. Add snapshot behavior with a failing synthetic test, implement and verify.
3. Extend exporter/validator/UI, then run Python, TypeScript and browser acceptance.
4. Finalize candidate research through actual risk code and review contracts.
