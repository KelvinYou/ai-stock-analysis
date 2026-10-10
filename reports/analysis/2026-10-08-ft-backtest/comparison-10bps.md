# Fundamental + technical fixed-input diagnostic

[Status: Warning] Exploratory post-hoc ablation. See protocol.json for rules and limits.

## Portfolio simulation

- Starting balance: $10,000.00
- Position size: 10.0% of pre-session cash per trade; same-day orders share one cash snapshot and are capped at 100% in aggregate
- Shorts enabled: False
- Transaction cost: 10.0 bps/side (20.0 bps round trip)
- Drawdown: daily close mark-to-market when shared daily prices cover every trade; otherwise `n/a` (event-only marks are incomplete).
- Matched passive: equal-weight all run-universe names on each candidate's exact active dates and dollar stakes; this conditions on signal timing and diagnoses selection/exposure only.
- `overall_fundamentals_confirmed` is a research-only alternative: it takes an overall directional signal only when the fundamentals analyst agrees. It is counted in the strategy-search denominator and is not the primary promotion candidate.

| Strategy | Final balance | Return | vs strict hold | vs matched passive | Max DD | Trades | n_eff | Win rate | Sharpe | PSR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | $10,000.00 | +0.00% | -20.66% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| overall_fundamentals_confirmed | $10,000.00 | +0.00% | -20.66% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| fundamentals | $10,000.00 | +0.00% | -20.66% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| technical | $9,409.00 | -5.91% | -26.57% | -2.14% | -9.16% | 21 | 7.0 | +52.38% | -0.238 | +24.92% |
| sentiment | $10,000.00 | +0.00% | -20.66% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| macro | $10,000.00 | +0.00% | -20.66% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| buy_and_hold 🏆 | $12,066.46 | +20.66% | +0.00% | n/a | -19.25% | 8 | 1.0 | +75.00% | +0.580 | n/a |
| rolling_long | $11,548.14 | +15.48% | -5.18% | +1.05% | -10.65% | 96 | 9.0 | +48.96% | +0.135 | +65.36% |
| signal_timing_long | $10,034.83 | +0.35% | -20.32% | -1.51% | -3.15% | 3 | 3.0 | +33.33% | +0.085 | +54.85% |
| ft_weighted | $9,779.63 | -2.20% | -22.87% | +0.80% | -5.73% | 20 | 7.0 | +55.00% | -0.123 | +37.64% |
| ft_agreement | $10,000.00 | +0.00% | -20.66% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |

### Capital utilization

- Mean and peak use the sum of original trade stakes divided by starting balance, over the same price-path sessions for every strategy. Entry and exit sessions count as invested. This is a cash-deployment diagnostic, not mark-to-market exposure or beta.

| Strategy | Mean committed stake | Peak committed stake | Sessions with positions |
| --- | ---: | ---: | ---: |
| overall | +0.00% | +0.00% | 0/249 (+0.00%) |
| overall_fundamentals_confirmed | +0.00% | +0.00% | 0/249 (+0.00%) |
| fundamentals | +0.00% | +0.00% | 0/249 (+0.00%) |
| technical | +16.56% | +52.36% | 186/249 (+74.70%) |
| sentiment | +0.00% | +0.00% | 0/249 (+0.00%) |
| macro | +0.00% | +0.00% | 0/249 (+0.00%) |
| buy_and_hold | +100.00% | +100.00% | 249/249 (+100.00%) |
| rolling_long | +52.53% | +94.00% | 249/249 (+100.00%) |
| signal_timing_long | +2.52% | +10.00% | 63/249 (+25.30%) |
| ft_weighted | +15.96% | +44.30% | 186/249 (+74.70%) |
| ft_agreement | +0.00% | +0.00% | 0/249 (+0.00%) |

### Cash-yield diagnostic

- Unavailable: No dated FRED:DFF replay was supplied.

### Benchmark gate

- Observed benchmark: `buy_and_hold`; return leader: `rolling_long`.
- Promotion gate: **FAIL** (the `overall` pipeline must beat strict hold after costs, have effective n ≥ 30, DSR ≥ 95%, positive lower 95% paired block-bootstrap bound, positive excess at 2× costs, and max drawdown within 5 percentage points of strict hold).
- This is the numerical backtest gate only; point-in-time universe, provider, evidence, and external cost-calibration gates are checked separately.

### Selection bias

`buy_and_hold` posted the best per-trade Sharpe (+0.580) out of 11 strategies scored on the same trials. That comparison is itself a search, so its Sharpe is an order statistic rather than an unbiased estimate.
- Deflated Sharpe unavailable — too few independent trades to estimate it.

## ft_weighted directional diagnostic

Includes sell forecasts as hypothetical directional calls; the portfolio executes only buys. Consensus score is deterministic, not model conviction.

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

- Overall directional hit rate: +54.10% (95% CI +17.40% – +86.83%, spans 50% — not distinguishable from a coin flip) — n=61 directional trials (approximate effective-n Wilson interval)
- Mean return, directional trials only: -3.21% (same denominator as the hit rate)
- Mean return, all trials incl. flat: -2.04% (p = 0.732, **not** significant)
- Conviction-weighted mean return: -1.01%
- Mean realized return across all trials (not a portfolio hold): +1.97%
- Per-trial Sharpe (directional, gross): -0.185
- Information coefficient (conviction vs return): -0.108 (95% CI -0.947 – +0.920, spans 0 — no demonstrated skill) — IC effective n=4.33 (approximate effective-n Fisher interval)
- Effective sample size (portfolio date-clustered): 4.1 — overlapping holding windows collapse 61 nominal trials to 4.1 independent ones (7%)
- t-statistic vs zero (on effective n): -0.375, p = 0.732
- Probabilistic Sharpe (P[true SR > 0], skew/kurtosis adjusted): +35.82%
- Return distribution: skew -1.420, kurtosis +6.085 (normal = 3.0)
- **Net of costs** (10.0 bps/side, 20.0 bps round trip): mean -2.17% (p = 0.716, **not** significant), Sharpe -0.197

## By signal (all trials)

| Signal | N | Hit rate | Mean return | Median return |
| --- | ---: | ---: | ---: | ---: |
| strong_buy | 0 | n/a | n/a | n/a |
| buy | 20 | +60.00% | -0.91% | +0.55% |
| neutral | 35 | +5.71% | +0.86% | +0.17% |
| sell | 41 | +51.22% | +4.33% | -0.05% |
| strong_sell | 0 | n/a | n/a | n/a |

> ⚠ Effective sample size is 4.1 (61 nominal directional trials). Below ~30 the interval estimates above are wide enough that almost any point estimate is consistent with zero edge. Extend the pre-registered date range or widen the interval between as-of dates; adding names on an already-scored date does not create another portfolio period.
> ⚠ More than half the nominal sample is redundant through overlapping holding periods. Consider `--interval` ≥ `--horizon`.

## How to read this

- A hit rate whose 95% interval spans 50% is not evidence of skill, however far the point estimate sits from 50%.
- `p` values use the **effective** sample size, not the trial count. Overlapping holding windows are not independent observations.
- Probabilistic Sharpe is the Sharpe corrected for skew and fat tails; a raw Sharpe flatters strategies with occasional large losses.
- Gross figures ignore slippage and commission. On thin books (Bursa small caps especially) costs can exceed the entire edge.

## ft_agreement directional diagnostic

Includes sell forecasts as hypothetical directional calls; the portfolio executes only buys. Consensus score is deterministic, not model conviction.

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

- Overall directional hit rate: +75.00% (95% CI +27.22% – +96.01%, spans 50% — not distinguishable from a coin flip) — n=8 directional trials (approximate effective-n Wilson interval)
- Mean return, directional trials only: +3.78% (same denominator as the hit rate)
- Mean return, all trials incl. flat: +0.32% (p = 0.918, **not** significant)
- Conviction-weighted mean return: +0.32%
- Mean realized return across all trials (not a portfolio hold): +1.97%
- Per-trial Sharpe (directional, gross): +0.063
- Information coefficient (conviction vs return): +0.133 (95% CI -0.916 – +0.950, spans 0 — no demonstrated skill) — IC effective n=4.33 (approximate effective-n Fisher interval)
- Effective sample size (portfolio date-clustered): 3.3 — overlapping holding windows collapse 8 nominal trials to 3.3 independent ones (42%)
- t-statistic vs zero (on effective n): +0.114, p = 0.918
- Probabilistic Sharpe (P[true SR > 0], skew/kurtosis adjusted): +53.50%
- Return distribution: skew +0.090, kurtosis +20.746 (normal = 3.0)
- **Net of costs** (10.0 bps/side, 20.0 bps round trip): mean +0.30% (p = 0.922, **not** significant), Sharpe +0.059

## By signal (all trials)

| Signal | N | Hit rate | Mean return | Median return |
| --- | ---: | ---: | ---: | ---: |
| strong_buy | 0 | n/a | n/a | n/a |
| buy | 0 | n/a | n/a | n/a |
| neutral | 88 | +12.50% | +2.50% | +0.55% |
| sell | 8 | +75.00% | -3.78% | -6.62% |
| strong_sell | 0 | n/a | n/a | n/a |

> ⚠ Effective sample size is 3.3 (8 nominal directional trials). Below ~30 the interval estimates above are wide enough that almost any point estimate is consistent with zero edge. Extend the pre-registered date range or widen the interval between as-of dates; adding names on an already-scored date does not create another portfolio period.
> ⚠ More than half the nominal sample is redundant through overlapping holding periods. Consider `--interval` ≥ `--horizon`.

## How to read this

- A hit rate whose 95% interval spans 50% is not evidence of skill, however far the point estimate sits from 50%.
- `p` values use the **effective** sample size, not the trial count. Overlapping holding windows are not independent observations.
- Probabilistic Sharpe is the Sharpe corrected for skew and fat tails; a raw Sharpe flatters strategies with occasional large losses.
- Gross figures ignore slippage and commission. On thin books (Bursa small caps especially) costs can exceed the entire edge.
