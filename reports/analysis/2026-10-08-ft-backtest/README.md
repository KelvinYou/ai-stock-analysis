# Pipeline and fundamental + technical versus long hold — 2026-10-08

[Status: Warning] Fixed-input historical diagnostic completed. Neither the pipeline nor either fundamental + technical rule beat strict long hold in this panel. [Status: Critical] These results do not establish a deployable trading edge; the pipeline numerical promotion gate and external validation both FAIL.

The full pipeline was rerun through the current working-tree `rescore --recalibrate-session` path. The new FT arms reuse the sealed specialist forecasts and remove sentiment, macro, debate and synthesized conviction from the decision rule. They are deterministic combinations of existing analyst judgments, not newly generated two-agent model forecasts. No API key was present; no paid model call or price refetch was made. No production source code, execution thresholds, current research snapshots or prospective cohort predictions were changed.

## Fixed sample and rules

- AVGO, NVDA, MSFT, TSM, V, UNH, ORCL, COST; all 96 trials retained.
- Twelve existing forecast dates from 2025-09-01 to 2026-07-28, spaced by 30 calendar days; 30-calendar-day holding horizon. Portfolio comparison runs from 2025-09-02 entry through 2026-08-27 final exit.
- USD 10,000 starting capital; long-only; each buy uses 10% of pre-session available cash. Same-day orders share that snapshot and are capped equally. Entry uses next-session open and exit uses the eligible close; no production stop/limit replay. A sell forecast skips a new long entry; it does not close an existing long early or create a short.
- Strict hold buys the same eight names at equal weight at the start and holds through the end. Primary idle cash earns zero; this is not a brokerage cash-yield comparison.
- **FT weighted:** high/medium/low confidence weights 1.0/0.75/0.5. Signed consensus `(buy weight - sell weight) / total two-role weight`; convergence `max(buy weight, sell weight) / total`. Reuse the existing actionability function: absolute consensus >0.30 and convergence >=0.40. Consensus is a deterministic research score, not model conviction.
- **FT agreement:** use the weighted rule only when fundamentals and technical are both directional and agree. For this long-only portfolio, both must be bullish to enter.
- Missing fundamentals remains neutral/low in the two-role denominator; it is never removed or substituted with current data. A technical view can therefore still qualify for FT weighted when fundamentals is neutral or unavailable; this arm does not require two independent positive confirmations.
- The new rules, costs and hashes were written to [protocol.json](protocol.json) before computing their returns in this session. The historical outcomes were already inspected previously, so this freeze does not create an untouched holdout. No threshold sweep was performed.

## Returns and deployment

Primary assumption: 10 bps per side. Returns below are whole-portfolio returns, net of entry/exit costs, not mean individual ticker returns.

| Strategy | Gross return | Net return, 10 bps | Net return, 20 bps | Excess vs hold, 10 bps | Long trades | Max drawdown, 10 bps | Mean committed principal |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Strict equal-weight hold | +20.86% | +20.66% | +20.46% | — | 8 | 19.25% | 100.00% |
| Full pipeline | 0.00% | 0.00% | 0.00% | -20.66 pp | 0 | 0.00% | 0.00% |
| FT weighted | -1.83% | -2.20% | -2.58% | -22.87 pp | 20 | 5.73% | 15.96% |
| FT agreement | 0.00% | 0.00% | 0.00% | -20.66 pp | 0 | 0.00% | 0.00% |
| Technical alone | -5.53% | -5.91% | -6.29% | -26.57 pp | 21 | 9.16% | 16.56% |
| Fundamentals alone | 0.00% | 0.00% | 0.00% | -20.66 pp | 0 | 0.00% | 0.00% |

Drawdown is shown as a positive loss magnitude here; machine-readable portfolio fields use negative drawdown fractions. Mean committed principal is original stakes divided by starting capital over shared market sessions, not mark-to-market beta. Lower FT drawdown accompanies far lower capital deployment. Zero drawdown with no trades demonstrates no realized execution risk, not validated risk-control skill.

## What changed when fundamentals was added

Fundamentals produced 85 neutral and 11 sell judgments, with no buy judgments. Evidence was present for 55/96 windows; the remaining 41 retained unavailable/neutral evidence. Consequently FT agreement had 88 neutral and 8 sell forecasts, and zero executed longs.

FT weighted produced 20 buy, 41 sell and 35 neutral forecasts. Its 20 long entries are the technical strategy's 21 entries minus one ORCL entry: forecast 2026-05-29, entry 2026-06-01, exit 2026-06-29. That excluded technical trade lost 35.90% gross / 36.10% net at 10 bps per side, on a USD 1,006.83 stake. Later available-cash stakes also change after excluding it. The FT improvement over technical is 3.71 percentage points, substantially explained by this one exclusion rather than broad demonstrated fundamental stock-selection skill.

The matched-exposure passive diagnostic returns -3.00% for the FT trade schedule; FT's -2.20% is +0.80 pp better. This conditions on the strategy's already selected dates and stakes. It diagnoses selection at the same deployment, not an independent long-hold alpha claim or confidence interval.

The [follow-up audit](audit.md) categorizes all 96 fundamental abstentions/sells, proves that removing the sole differing ORCL technical entry exactly reproduces all 20 FT trades and their capital path, and reports the issuer-exclusion sensitivity. The verified 31-name forward cohort remains unscored until at least 2026-11-07 UTC.

## Quant verdict

- [Status: OK] Current production calibration was rerun on every sealed pipeline trial. Existing nine strategy returns and trade counts agree exactly with the new eleven-row comparison. The FT rules consume guarded, pre-existing analyst directions and their original confidence weights, not forward returns.
- [Status: OK] Costs are shown gross/net and at doubled assumptions; all eleven portfolio rows enter current-run DSR correction. FT weighted trade effective n is 7.0, rather than treating 20 longs or 96 overlapping trials as independent observations. Its DSR is 5.24%; technical's DSR is 1.67% in this expanded comparison. Cross-run cumulative searches are recorded but are not a cross-run DSR correction.
- [Status: Warning] FT weighted paired 95% time-block-bootstrap mean daily log-excess interval versus hold is [-0.002167, +0.001012], spanning zero. This is not a total-return-percentage-point interval. Its directional hit rate including hypothetical sell calls is 54.10%, with approximate effective-n Wilson 95% CI [17.40%, 86.83%], also spanning the null. Those sell calls are not executed shorts.
- [Status: Critical] Full pipeline made no long trades; FT weighted lost money and lagged strict hold even before costs; FT agreement made no long trades. No candidate demonstrated the requested long-hold outperformance. The full pipeline's numerical promotion gate and [external validation](external-validation.md) FAIL.
- [Status: Warning] The current-survivor universe, 55/96 fundamental coverage, possibly restated financials, historical model/batch hindsight exposure, absent authenticated provider run, incomplete licensed total-return provenance and assumed execution costs remain unresolved. These limitations also prevent extrapolating this panel to all live pipeline performance or declaring FT intrinsically ineffective.

## Verification and reproduction

91 targeted repository tests and 4 subtests passed. Independent [verification.json](verification.json) confirms all 60 FT long-trade cost/P&L calculations across the three cost levels, identical returns with reversed trial order, no missing-fundamental agreement entry, matching source/script hashes and the five-row append-only ledger chain. All 107 originally sealed files remain unchanged; 96 trials are complete. Artifact integrity passing is distinct from statistical/external validation failing.

From `repos/ai-stock-analysis`, after retaining the two current pipeline rescored inputs:

```bash
.venv/bin/python reports/analysis/2026-10-08-ft-backtest/compare.py
.venv/bin/python reports/analysis/2026-10-08-ft-backtest/verify.py
```

`compare.py` reproduces the fixed rules and appends research runs to `backtest_experiments.jsonl`; it never refreshes prices or forecasts. Full comparisons: [gross](comparison-0bps.md), [10 bps](comparison-10bps.md), [20 bps](comparison-20bps.md). [summary.json](summary.json) and [signal-trace.json](signal-trace.json) retain the numerical summary and all per-trial rule decisions. The full pipeline reruns are [10 bps](pipeline-10bps.md) and [20 bps](pipeline-20bps.md).
