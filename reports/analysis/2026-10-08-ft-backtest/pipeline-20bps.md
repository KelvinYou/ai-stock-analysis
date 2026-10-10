# Backtest Report

- Horizon: 30 calendar days
- Trials: 96 (96 completed, 0 errored)
- Pipeline mode: in-session
- Models: quick=session deep=session rounds=2

## Point-in-time evidence coverage

Availability is reported separately from signal direction; unavailable evidence is not treated as a bearish view.
- technical: 96/96 trials (100.0%)
  - Sources: historical_price_replay 96/96
- fundamentals: 55/96 trials (57.3%)
  - Sources: yahoo_sec_filing 55/96
- sentiment: 0/96 trials (0.0%)
- macro: 96/96 trials (100.0%)
  - Sources: FRED:DFF; single-rate observation only 96/96
- Availability counts input presence, not feed completeness or independent corroboration.

## Headline metrics (all trials)

- Overall directional hit rate: +66.67% (95% CI +20.77% – +93.85%, spans 50% — not distinguishable from a coin flip) — n=3 directional trials (approximate effective-n Wilson interval)
- Mean return, directional trials only: -1.43% (same denominator as the hit rate)
- Mean return, all trials incl. flat: -0.04% (p = 0.974, **not** significant)
- Conviction-weighted mean return: -0.25%
- Mean realized return across all trials (not a portfolio hold): +1.97%
- Per-trial Sharpe (directional, gross): -0.021
- Information coefficient (conviction vs return): -0.070 (95% CI -0.943 – +0.926, spans 0 — no demonstrated skill) — IC effective n=4.33 (approximate effective-n Fisher interval)
- Effective sample size (portfolio date-clustered): 3.0
- t-statistic vs zero (on effective n): -0.037, p = 0.974
- Probabilistic Sharpe (P[true SR > 0], skew/kurtosis adjusted): +48.76%
- Return distribution: skew -4.020, kurtosis +54.673 (normal = 3.0)
- **Net of costs** (20.0 bps/side, 40.0 bps round trip): mean -0.06% (p = 0.967, **not** significant), Sharpe -0.027

## By signal (all trials)

| Signal | N | Hit rate | Mean return | Median return |
| --- | ---: | ---: | ---: | ---: |
| strong_buy | 0 | n/a | n/a | n/a |
| buy | 0 | n/a | n/a | n/a |
| neutral | 93 | +11.83% | +1.99% | +0.17% |
| sell | 3 | +66.67% | +1.43% | -1.64% |
| strong_sell | 0 | n/a | n/a | n/a |

## Signal trace (descriptive)

- Pre-gate synthesized BUY: 10/96; final executable BUY: 0/96; pre-gate buys blocked: 10.
- Raw technical BUY: 21/96; same-trial overlap with pre-gate synthesized BUY: 10.
- Gate reasons: evidence_unavailable:fundamentals 41, evidence_unavailable:sentiment 96, session_actionability_gate_failed 32
- These are label-flow counts only; they do not measure forecast performance.

> ⚠ Effective sample size is 3.0 (3 nominal directional trials). Below ~30 the interval estimates above are wide enough that almost any point estimate is consistent with zero edge. Extend the pre-registered date range or widen the interval between as-of dates; adding names on an already-scored date does not create another portfolio period.

## How to read this

- A hit rate whose 95% interval spans 50% is not evidence of skill, however far the point estimate sits from 50%.
- `p` values use the **effective** sample size, not the trial count. Overlapping holding windows are not independent observations.
- Probabilistic Sharpe is the Sharpe corrected for skew and fat tails; a raw Sharpe flatters strategies with occasional large losses.
- Gross figures ignore slippage and commission. On thin books (Bursa small caps especially) costs can exceed the entire edge.

## Portfolio simulation

- Starting balance: $10,000.00
- Position size: 10.0% of pre-session cash per trade; same-day orders share one cash snapshot and are capped at 100% in aggregate
- Shorts enabled: False
- Transaction cost: 20.0 bps/side (40.0 bps round trip)
- Drawdown: daily close mark-to-market when shared daily prices cover every trade; otherwise `n/a` (event-only marks are incomplete).
- Matched passive: equal-weight all run-universe names on each candidate's exact active dates and dollar stakes; this conditions on signal timing and diagnoses selection/exposure only.
- `overall_fundamentals_confirmed` is a research-only alternative: it takes an overall directional signal only when the fundamentals analyst agrees. It is counted in the strategy-search denominator and is not the primary promotion candidate.

| Strategy | Final balance | Return | vs strict hold | vs matched passive | Max DD | Trades | n_eff | Win rate | Sharpe | PSR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | $10,000.00 | +0.00% | -20.46% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| overall_fundamentals_confirmed | $10,000.00 | +0.00% | -20.46% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| fundamentals | $10,000.00 | +0.00% | -20.46% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| technical | $9,371.18 | -6.29% | -26.75% | -2.12% | -9.30% | 21 | 7.0 | +52.38% | -0.255 | +23.17% |
| sentiment | $10,000.00 | +0.00% | -20.46% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| macro | $10,000.00 | +0.00% | -20.46% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| buy_and_hold 🏆 | $12,046.46 | +20.46% | +0.00% | n/a | -19.27% | 8 | 1.0 | +75.00% | +0.575 | n/a |
| rolling_long | $11,414.47 | +14.14% | -6.32% | +1.05% | -11.01% | 96 | 9.0 | +48.96% | +0.120 | +63.66% |
| signal_timing_long | $10,028.82 | +0.29% | -20.18% | -1.51% | -3.17% | 3 | 3.0 | +33.33% | +0.071 | +54.06% |

### Capital utilization

- Mean and peak use the sum of original trade stakes divided by starting balance, over the same price-path sessions for every strategy. Entry and exit sessions count as invested. This is a cash-deployment diagnostic, not mark-to-market exposure or beta.

| Strategy | Mean committed stake | Peak committed stake | Sessions with positions |
| --- | ---: | ---: | ---: |
| overall | +0.00% | +0.00% | 0/249 (+0.00%) |
| overall_fundamentals_confirmed | +0.00% | +0.00% | 0/249 (+0.00%) |
| fundamentals | +0.00% | +0.00% | 0/249 (+0.00%) |
| technical | +16.54% | +52.21% | 186/249 (+74.70%) |
| sentiment | +0.00% | +0.00% | 0/249 (+0.00%) |
| macro | +0.00% | +0.00% | 0/249 (+0.00%) |
| buy_and_hold | +100.00% | +100.00% | 249/249 (+100.00%) |
| rolling_long | +52.25% | +93.17% | 249/249 (+100.00%) |
| signal_timing_long | +2.52% | +10.00% | 63/249 (+25.30%) |

### Cash-yield diagnostic

- Unavailable: No dated FRED:DFF replay was supplied.

### Benchmark gate

- Observed benchmark: `buy_and_hold`; return leader: `rolling_long`.
- Promotion gate: **FAIL** (the `overall` pipeline must beat strict hold after costs, have effective n ≥ 30, DSR ≥ 95%, positive lower 95% paired block-bootstrap bound, positive excess at 2× costs, and max drawdown within 5 percentage points of strict hold).
- This is the numerical backtest gate only; point-in-time universe, provider, evidence, and external cost-calibration gates are checked separately.

### Selection bias

`buy_and_hold` posted the best per-trade Sharpe (+0.575) out of 9 strategies scored on the same trials. That comparison is itself a search, so its Sharpe is an order statistic rather than an unbiased estimate.
- Deflated Sharpe unavailable — too few independent trades to estimate it.

> **[Status: Warning]** Sealed-trial allocation and AI ablation below use a deterministic non-overlapping subset (9 dates, 72/96 trials). The full panel is still used for the primary pipeline/hold score; the subset is research-only and cannot satisfy its promotion gate.

## Sealed-Trial Cross-Sectional Allocation

> **Hypothesis:** At each sealed as-of date, the top 3 of a fixed universe by 12-month trailing return will outperform an equal-weight passive portfolio on the same windows after costs.
>
> This is a deterministic portfolio-construction layer applied after the session produced its sealed predictions; it is not an AI forecast result.

### Protocol

- Universe: AVGO, COST, MSFT, NVDA, ORCL, TSM, UNH, V
- Price history: 2016-04-22 → 2026-07-28
- Sealed trial window: 2025-09-01 → 2026-08-27
- Signal: rank the close-to-close return over the prior 12 months, using only prices on or before each as-of date
- Portfolio: equal weight top 3; use each selected ticker's sealed forward trial return after selection
- Cost: 20.0 bps/side; one full round trip per sealed window
- Windows: non-overlapping, synchronized across tickers; capital is idle between windows
- Bootstrap: moving blocks of 3 paired periods, 2000 resamples, seed 0
- Missing price/outcome data: fail closed; the fixed universe is not silently reduced

### Metrics

| Metric | Value |
| --- | ---: |
| As-of periods | 9 |
| Effective period sample size | 9.000 |
| Completed ticker trials | 72 |
| Average holding days | 29.0 |
| Gross compound return | 38.53% |
| Net compound return | 33.62% |
| Strict equal-weight buy-and-hold | 20.38% |
| Matched passive return (same windows) | 26.87% |
| Matched passive excess | 6.75% |
| Paired log-excess 95% CI vs. passive | [-0.0200, 0.0338] log excess |
| Strict hold excess | 13.24% |
| Mean net allocation-period return | 3.82% |
| Max drawdown (period endpoints only) | -9.86% |
| Annualized Sharpe | 1.165 |
| Net mean-return p-value | 0.353 |

### Audit notes

- The historical ranking is calculated before reading any selected ticker's forward sealed outcome.
- Strict hold stays invested from the first sealed entry through the last sealed exit; matched passive invests only during each sealed episode, like the allocator.
- The paired interval compares allocator and passive returns on the same sealed windows; one episode is not enough to estimate an interval.
- Period-end drawdown omits losses inside each sealed holding window; use the daily-price monthly backtest for marked-to-market drawdown.
- This adapter does not change the AI signal score or promotion gate. Universe and parameters must be frozen before a future holdout.

## AI Signal Ablation

- Universe: AVGO, COST, MSFT, NVDA, ORCL, TSM, UNH, V
- Periods / effective n: 9 / 9.0000
- Candidate arms counted: 2
- Cost: 20 bps per side
- Price / drawdown basis: `sealed_trial_realized_return` / `sealed_window_endpoints`
- Allocator-only net compound return: 33.62%

| Diagnostic arm | Net compound | Exposure-matched reference | Excess | Mean exposure | Max DD (window endpoints) | 95% paired log-excess CI |
|---|---:|---:|---:|---:|---:|---:|
| AI-only long | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | [0.0000, 0.0000] |
| AI-filtered momentum | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | [0.0000, 0.0000] |

### Conditional AI-label permutation

- **Uninformative:** no momentum basket has a mix of AI-positive and other labels, so within-basket selection cannot be tested.

- Each positive AI signal gets a fixed `1 / top_n` long-only sleeve; unused sleeves remain in cash. AI-only ranks BUY/STRONG_BUY by signal strength, conviction, then ticker. The hybrid intersects AI-positive names with the fixed momentum top-N basket.
- Exposure-matched references retain the same dates and total invested weight. The permutation holds each period's momentum basket and AI-positive count fixed, randomizing only which basket names receive positive labels.
- Maximum drawdown marks only the ordered sealed-window endpoints; it misses intra-window losses. This is a conditional attribution diagnostic, not a general forecast-significance test or promotion result. Small samples, historical universe survivorship, provider provenance, dividend basis, and execution-cost calibration remain unresolved. Do not tune the tested rule on these same periods.
## Experiment Ledger

- Appended run `4ad40d7a-ba98-445c-9ec0-35188b463425` as ledger row 2 to `backtest_experiments.jsonl`.
- Tested arms this run: 12 (ai_signal_ablation=2, portfolio_comparison=9, sealed_trial_allocator=1); unique strategy configs: 24; distinct scored evaluations: 24.
- New / repeated evaluation arms this run: 12 / 0.
- The portfolio count includes benchmark/diagnostic rows to match the current-run DSR denominator.
- Cross-run DSR adjustment is not applied. Counts begin with this ledger's first row; earlier/manual searches are not reconstructed.

## Automatic Quality Analysis

> [Status: Warning] Research-only diagnosis. No strategy parameters or predictions were changed.

- [Status: Critical] `strict_hold_loss` — The overall pipeline did not beat strict hold after costs.
- [Status: Warning] `small_effective_sample` — Portfolio effective sample size is below the promotion threshold of 30.
- [Status: Warning] `excess_uncertain` — The paired 95% excess-return interval is unavailable or includes zero.
- [Status: Critical] `promotion_gate_failed` — The numerical portfolio promotion gate did not pass.
- [Status: Warning] `evidence_gap` — fundamentals evidence was present for 55/96 trials.
- [Status: Warning] `evidence_gap` — sentiment evidence was present for 0/96 trials.
- [Status: Warning] `provider_unverified` — In-session historical predictions are not authenticated production-provider forecasts.
- [Status: Warning] `ai_overlay_loss` — The AI filter did not add return over its exposure-matched momentum reference.
- [Status: Warning] `search_count` — Ledger has 24 unique recorded candidate arms; earlier/manual searches are not reconstructed.

### Next checks

- Resolve provider, point-in-time data, total-return, and calibrated-cost gates before promotion.
