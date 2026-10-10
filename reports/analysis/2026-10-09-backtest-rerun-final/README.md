# Fixed-forecast backtest rerun — 2026-10-09

[Status: Warning] The current execution and evidence guards were replayed against
96 previously frozen forecasts and outcomes. This is a post-hoc engineering
revalidation, not a newly generated pipeline forecast or evidence of a tradable edge.
Neither the pipeline nor either FT view beats strict long hold in this panel.

## Results

The same eight surviving tickers, historical dates, 30-day horizon, next-session
Open fills and cached daily price paths were retained. Costs are per side. Strategy
stakes use 10% of the cash available before that session, capped equally; strict
hold owns one equal-weight position per ticker. Idle cash earns zero in the primary
comparison. All eleven existing strategy views remain in the DSR comparison.

| Strategy | 0bps net return | 10bps net return | 20bps net return | Trades at 10bps |
| --- | ---: | ---: | ---: | ---: |
| Pipeline | 0.00% | 0.00% | 0.00% | 0 |
| FT weighted | -1.83% | -2.20% | -2.58% | 20 |
| FT same-direction agreement | 0.00% | 0.00% | 0.00% | 0 |
| Technical alone | -5.53% | -5.91% | -6.29% | 21 |
| Strict long hold | +20.86% | +20.66% | +20.46% | 8 |

FT weighted trails hold by 22.87 percentage points at 10bps. Pipeline has no
executed positions and misses the benchmark's rise. Its retained forecasts are
neutral or fail current directional/actionability gates; the trace records 32
weak directional calls declined at the execution gate. Sentiment is unavailable
for all 96 inputs and fundamentals for 41. FT agreement finds no executable
same-direction combined call. FT weighted does trade, but its selected entries
lose even before assumed costs. These are descriptive outcomes of the old panel.

FT weighted effective N is 7, DSR is approximately 0.052, and its paired daily
strict-hold log-excess interval spans zero. The old survivor-selected universe,
small clustered sample, incomplete evidence, possible restatements, unknown model
historical contamination, assumed costs and unverified distribution/terminal-price
completeness remain limitations. No promotion gate is claimed as passed.

## New defect found and repaired

The first rerun's order-reversal check failed for `rolling_long`: at zero cost,
return changed from 16.83% to 14.33% when trial order reversed. Its same-day entries
used successively shrinking cash instead of one shared session snapshot.
`portfolio._rolling_long` now routes its all-trial long positions through the same
cash allocation and Open-before-Close event queue used by strategy trades. The
strict buy-and-hold implementation is unchanged. The regression requires equal
same-day stakes, identical reversed-input reports and zero net return for equal
positive/negative fixture returns. All eleven views now pass reversal checks.
The stopped attempt remains preserved in `../2026-10-09-backtest-rerun/`.

## Verification and scope

- Full Python suite: 342 passed, 4 subtests passed; existing Starlette/httpx warning.
- Ruff, web typecheck, pipeline SVG/layout, OpenAPI, Postman and architecture: PASS.
- Independent trade cost, P&L and final-balance checks: 444 trades across the
  three cost settings. Experiment hash chain: three repeat-run records.
- Input/source/script hashes match; 107 original pilot files, 135 backfill
  artifacts and 249 prospective frozen files remain unchanged. Both old
  96-packet panels remain readable.
- Local Docker daemon is unavailable. Database migration enforcement remains
  unexecuted, and no remote migration or deployment was performed.

See [protocol.json](protocol.json), [summary.json](summary.json),
[verification.json](verification.json), [10bps comparison](comparison-10bps.md)
and [signal trace](signal-trace.json). The run can be reproduced into a fresh output
folder; its script refuses to overwrite existing result/protocol artifacts.

**No new LLM forecasts or new price fetches were made.** The enriched 96-packet
panel has not been assigned new predictions, so this run does not test how the
analysts respond to the newly backfilled evidence. It tests the corrected scoring,
execution and portfolio rules on old immutable predictions. Historical returns
are already observed; a fresh historical session run would still be exploratory,
and prospective sealed forecasts remain separate.
