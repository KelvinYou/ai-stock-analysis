# Frozen pipeline gap diagnostics — 2026-10-09

[Status: Warning] Offline, post-hoc diagnostics of the same previously observed
96 forecasts/outcomes. No new predictions or price/provider calls. These results
explain this panel; they do not establish a tradable edge or clear promotion.

## 1. Refusal and full-panel attribution

The forecast partitions are mutually exclusive: 61 original neutral calls,
10 declined buys, 22 declined sells, and three guard-approved sells skipped by
the long-only allocation rule. All 96 remain in the panel. Sentiment is unavailable
96 times and fundamentals 41 times. Actionability and risk-decline codes occur
32 times each on the same 32 calls: these are overlapping diagnostics, not 64
independent refusals or identifiable causal effects of separate gates.

At 10bps per side, the final pipeline executes no positions and returns 0.00%
versus continuous strict hold +20.66%. A counterfactual that accepts the ten
original raw buys with *all* deterministic guards bypassed returns +3.37%, with
10 trades and effective N=7. It still trails hold by 17.29 percentage points; its
DSR is approximately 0.443 across all 12 comparison rows and its paired daily
log-excess interval spans zero. The result does not support removing the guards.
It neither repairs missing evidence nor tests predictions on the enriched panel.

FT weighted returns -2.20%. Its same-date, same-dollar all-name passive reference
returns -3.00%. The exact descriptive identity is:

```text
FT minus strict hold = (FT minus matched passive) + (matched passive minus strict hold)
              -22.87pp =             +0.80pp     +                    -23.67pp
```

Mean committed principal is 15.96% of starting balance. The +0.80pp is conditional
selection at this timing and sizing; the -23.67pp combines timing, cash deployment,
episode gaps and benchmark differences. It is not a causal market-timing estimate,
not beta, and not proof that simply increasing position size fixes the strategy.
No-trade rows retain unavailable matched-selection effects rather than invented zeroes.

## 2. Allocator and signal comparison

The full 96 trials overlap. The existing earliest-feasible complete-window rule,
which reads dates but never returns, selects nine non-overlapping windows / 72
trials. All eight arms use these same windows and multiplicative entry/exit fees.
The momentum rule is unchanged: trailing 12 calendar months, top three, equal
one-third sleeves. FT-only buys have equal strength with lexical symbol ties;
they never inherit AI conviction. Filtered sleeves stay cash when rejected.

| Arm | 0bps | 10bps | 20bps |
|---|---:|---:|---:|
| Allocator only | +38.53% | +36.05% | +33.62% |
| Scheduled equal-weight passive | +31.53% | +29.18% | +26.87% |
| AI only | 0.00% | 0.00% | 0.00% |
| Allocator + AI | 0.00% | 0.00% | 0.00% |
| FT weighted only | -4.84% | -5.85% | -6.85% |
| Allocator + FT weighted | +6.63% | +5.92% | +5.21% |
| FT agreement only | 0.00% | 0.00% | 0.00% |
| Allocator + FT agreement | 0.00% | 0.00% | 0.00% |

The continuous hold comparator on the exact outer dates returns +20.62% at 10bps
under this episode experiment's multiplicative fee convention. This differs from
the full-panel simulator's additive-cost +20.66%. Do not mix the two experiments'
returns, stakes, endpoint/daily drawdowns or fee conventions.

The allocator beats scheduled passive by 6.87pp descriptively, but effective N is
only 9, DSR across all eight episode rows is approximately 0.501, and its paired
per-episode log-excess 95% interval is [-0.02003, +0.03380], spanning zero. A high
point return here is not a verified edge. All historical search is not reconstructed
by this within-comparison DSR; the historical panel remains development data.

FT-weighted filtering reduces the allocator return by 30.14pp and keeps mean
exposure at 37.04%. However, compared with the *same-exposure* momentum basket,
the hybrid's +5.92% exceeds -3.16% by 9.07pp. Its conditional bootstrap interval is
positive [0.00070, 0.02357], but the within-basket permutation test is only
p=0.0835, with six informative periods. This is a weak selection hypothesis,
not a robust improvement of the complete system: small sample, multiple searches
and the larger deployment loss remain. Adding old AI labels rejects every sleeve.

## 3. Forward rules and remaining activation work

See [forward-protocol-v2.json](forward-protocol-v2.json) and the authoritative
[prepared forward specification](../../../docs/design/pipeline-forward-validation-v2.md).
The proposed October 12 start uses 36 fixed 35-day anchors, 30-day episodes,
nine comparison arms and unchanged statistical/coverage gates. The rule digest
is recorded before forward collection. This is a prepared protocol, not an
activated scheduler: exact provider/model/prompt provenance and the nine-arm
collector still need to pass activation checks before the first eligible entry.
If that cutoff is missed, use a new future protocol version, never backdate v2.

The already frozen October 7 cohort remains separate and unmodified; its earliest
score date remains November 7 UTC. Licensed/source-complete returns, calibrated
costs and mature unseen observations remain necessary for promotion. No purchases,
paid model calls, threshold changes, database apply, deployment or trades occurred.

## Verification

- Twelve full-panel rows and eight episode arms counted in their own DSR comparisons.
- All full-panel returns and complete episode reports invariant under trial reversal.
- 243 independent episode return reconciliations across three cost settings.
- Source/code/script hashes and all 107 original sealed pilot files unchanged.
- Raw/final partitions distinguish research calls from actual long-only positions.
- Synthetic tests verify exact gap identity, unavailable semantics, immutable writes,
  unchanged selection after outcome mutation and FT isolation from AI conviction.

See [protocol.json](protocol.json), [summary.json](summary.json),
[diagnostics-10bps.json](diagnostics-10bps.json), [refusal-trace.json](refusal-trace.json),
[verification.json](verification.json) and [review.md](review.md).

Reproduce into a fresh directory from the child repository root:

```sh
.venv/bin/python scripts/research_pipeline_gaps.py --output reports/analysis/<new-run>
```

The runner refuses to reuse an existing directory and preserves its exact source.
