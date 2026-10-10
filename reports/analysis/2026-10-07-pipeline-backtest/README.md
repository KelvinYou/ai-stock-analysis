# Current-session pipeline backtest pilot — 2026-10-07

[Status: Critical] Completed exploratory diagnostic. Reliability is not established: the numerical promotion gate and external validation both FAIL. Partial historical evidence, current-session hindsight risk, and production/backtest contract differences prevent a production-pipeline efficacy claim.

The frozen sample contains AVGO, NVDA, MSFT, TSM, V, UNH, ORCL and COST over 12 repository-defined monthly windows (30-calendar-day spacing), 2025-09-01 through 2026-07-28. Each forecast has a 30-calendar-day horizon and 365-day price lookback. The selected names are current survivors chosen from current watchlist signals, not a historical investable universe.

## Evidence and execution contract

- 96 historical price packets; 55 filing-clock-qualified financial packets; no historical news; 96 macro snapshots containing only a dated FRED DFF observation.
- The SEC replay builder and a direct SEC submissions request returned HTTP 403, including outside the sandbox. Missing news is retained as unavailable, never replaced with current news.
- Current-provider financial values may be revised. An eligible filing date does not establish that the numerical values are the original published vintage.
- In-session typed analyst reports, compact two-round adversarial reasoning and compact final synthesis are retained. This is not an authenticated production-provider replay, a full ResearchManager replay, or a replay of limit/stop execution.
- Analysts work in bounded batches. Later snapshots in the same batch could expose earlier outcomes indirectly; row-specific instructions do not prove isolation. Historical model knowledge is another unresolved contamination risk. This run cannot establish blind out-of-sample forecasting skill.
- Next eligible session open entry, eligible close exit; no short positions in the portfolio. Signal-level sell accuracy in the scorer represents hypothetical short-direction prediction, not executed long-only portfolio P&L.
- Primary cost assumption: 10 bps per side; predeclared stress: 20 bps per side. Costs are not broker calibrated. Starting capital USD 10,000; 10% of available cash per signal under the repository simulator.
- Strict equal-weight buy-and-hold is the primary benchmark; rolling-long is a separate diagnostic. Lower deployed capital and cash exposure must be considered alongside raw returns.

## Production/backtest parity issue

The official session scorer replaces raw model conviction with its evidence-aware analyst consensus and excludes unavailable analysts from the denominator. Production instead includes all four typed reports, caps conviction at `min(abs(model_score), abs(consensus))`, and requires directional agreement. Both apply the real actionability gate.

For example, a raw buy score of 0.20 with consensus 0.50 and convergence 0.50 becomes actionable in session scoring, while production retains 0.20 and declines execution. A separate, predeclared production-parity arm applies the real production consensus, convergence, conviction cap and actionability functions to the same sealed forecasts and outcomes. It still does not recreate the full production execution contract.

No production code, thresholds, watchlist or Supabase research snapshots are changed by this test.

## Artifacts

`protocol.json` and `method.json` declare the sample and arms before outcomes. `inputs-compact.json` contains the deterministic indicator and evidence snapshots. The four `*-reports.json` files retain typed analyst judgments; `debate-reports.json` and `synthesis-reports.json` retain model reasoning. `session/predictions.json` is the normal session scoring input. `seal.json` records hashes before forward scoring. Scored artifacts: [normal session 10 bps](session-10bps.md), [20 bps stress](session-20bps.md), [production-score parity arm](production-parity-10bps.md), and [external validation](external-validation.md). `comparison.json` and `verification.json` retain the machine-readable summary and verification.

## Completed results

All 96 frozen trials have outcomes; no sample was dropped. Forecasts were hashed before the explicit forward-scoring price fetch and were unchanged afterward. This seal does not cure model-memory or cross-packet contamination. Raw synthesis: 10 buy, 25 sell, 61 neutral. Official session gates leave 9 buy, 25 sell, 62 neutral. The production-score parity arm leaves 3 sell, 93 neutral; no buy clears the production consensus/convergence/score gate.

| Long-only portfolio arm | Net total return | Strict hold | Excess vs strict hold | Executed long trades | Portfolio effective n |
| --- | ---: | ---: | ---: | ---: | ---: |
| Official session, 10 bps/side | +3.75% | +20.66% | -16.91 pp | 9 | 6.0 |
| Same sealed forecasts, 20 bps/side | +3.57% | +20.46% | -16.90 pp | 9 | 6.0 |
| Production-score parity, 10 bps/side | 0.00% | +20.66% | -20.66 pp | 0 | unavailable |

These are observed point estimates, not expected returns. The official session arm's 95% paired moving-block interval for **mean daily log excess** against strict hold is [-0.001985, +0.001323], spanning zero. It is not a confidence interval for the displayed total-return percentage-point difference. Overall DSR is 52.56%, below the 95% promotion threshold; each portfolio comparison counts nine strategies. The isolated ledger contains three runs / 36 counted configs/evaluations across portfolio, allocator and ablation families; cross-run DSR correction is not applied, and earlier searches are not reconstructed.

### Capital exposure and positive exploratory diagnostics

The session pipeline commits only 7.49% of initial capital on an average session, versus 100% for strict hold. Its maximum drawdown is -2.97%, versus -19.25% for strict hold. This deployment difference is substantial: losing to fully invested hold does not by itself establish inferior security selection.

On the repository's matching-date, matching-dollar passive comparison, the observed session excess is +5.90 pp. That estimate is conditional on the strategy's own chosen dates and stakes; it is not a clean out-of-sample alpha claim. The separate AI-label ablation uses a deterministic non-overlap subset, 72/96 trials across nine periods. It reports a positive AI-filtered momentum paired interval [0.0129, 0.0280] for mean episode log excess and conditional label-permutation p=0.007. Only five periods are informative for that permutation. These are possible selection signals worth testing prospectively, not evidence sufficient to promote this incomplete historical replay. The subset does not replace the primary full-panel test.

The production-score parity arm takes no long position. Zero P&L and zero drawdown therefore show abstention; they cannot establish successful timing, calibrated risk control, or predictive accuracy. Its three sell predictions are not executed short trades.

### Statistical reporting issue found during review

The existing scorer applies date-clustered effective n to t-tests/PSR, but its hit-rate Wilson interval uses the nominal directional count and its IC Fisher interval uses the nominal completed count (`backtest/scorer.py::_compute_partition`). Therefore the normal report's directional hit-rate 58.82% / nominal 95% CI [42.22%, 73.63%] and IC -0.116 / nominal CI [-0.309, 0.087] must not be read as dependence-adjusted confidence intervals. The directional effective n is only 3.73. Even these nominal intervals span their null; wider dependence-aware uncertainty would not rescue a demonstrated edge. The portfolio time-block interval and effective-n/DSR gates remain the primary reviewed inference. No production/statistical code was edited in this task.

### Validation and limitations

External validation is **FAIL**, with provider run, historical news, survivorship-safe universe, terminal-return provenance and calibrated execution cost gates **BLOCKED**. Complete scoring and fail-closed metadata pass; the validator's macro source pass proves dated input clocks, not completeness of macro information. Financial/news coverage, effective sample and strict-hold alpha gates fail.

No dated cash-yield path was attached to the score, so uninvested cash earns zero in these primary price-return comparisons. FRED was used only as a forecasting macro observation. A cash-yield diagnostic would be a separate transparent comparison, not grounds to retroactively tune the frozen forecasts.

Verification: 384 typed analyst reports validated; factual RSI and missing-evidence guards passed; 107 sealed input/prediction/method files remained unchanged; all three arms use identical entries, exits and realized outcomes. Existing selected tests: 64 passed, 1 failed, 4 subtests passed. The failure is an existing integration-test mock mismatch: its strategy list uses dictionaries while the scored-report writer expects typed `.strategy` attributes. This test fixture was not changed.

## What would establish reliability next

1. Freeze current real forecasts before their future outcomes and evaluate a sequence of prospective cohorts, retaining all neutral predictions and an exposure-matched benchmark. Do not reselect names after outcomes.
2. Make session and production consensus/conviction/denominator contracts agree, then review statistical interval dependence handling before rerunning. Preserve the current reports as pre-fix diagnostic evidence.
3. Obtain versioned point-in-time news/fundamentals and a historical investable universe, calibrate costs, and accrue at least 30 portfolio-effective observations. A longer historical sample cannot resolve unknown model training contamination by itself.

## Follow-up implementation repair — 2026-10-07

The authorized repairs are complete; see [contract and verification review](fix-review.md) and [repaired same-outcome score](fixed-10bps.md). This section does not replace the original exploratory run above. The normal session path now uses production conviction/denominator rules, and interval uncertainty uses the appropriate effective count. The original 96 predictions and outcomes remain unchanged. All 96 repaired signals/scores/convergence values agree with the predeclared production-parity arm: 93 neutral, 3 sell, no long trades.

The latest real watchlist forecasts are now independently frozen in [the 31-name prospective cohort](../2026-10-07-forward-cohort/README.md), for exit on/after 2026-11-06 and evaluation after the US close, from 2026-11-07 UTC. Their future performance is pending.
