# Cross-Sectional Momentum Research Report

> **Hypothesis:** At each month-end, the top 3 of a fixed universe by 12-month trailing return will outperform equal-weight buy-and-hold after costs.
>
> This is a deterministic portfolio-construction experiment, not an AI forecast or live-trading recommendation.

## Protocol

- Universe: AAPL, AMZN, AVGO, GOOGL, META, MSFT, NVDA, TSLA, TSM, UNH, V
- Data: 2016-08-12 → 2026-09-01
- Out-of-sample: 2018-01-31 → 2026-09-01
- Signal-date cutoff: 2026-08-14
- Signal: rank trailing 12-month close-to-close return at the last common session of each month
- Execution: next common-session open; rebalance/exit at the following signal's next-session open
- Portfolio: equal weight top 3; matched passive rebalances equal weight across the same names and dates
- Cost: 20.0 bps per side, charged on actual one-way turnover; final liquidation included
- Missing prices: no forward-fill; only synchronized common sessions are used
- Bootstrap: moving blocks of 3 paired monthly periods, 2000 resamples, seed 0
- Price basis: provided_open_close_not_dividend_verified; dividend/total-return treatment must be verified before interpreting CAGR

## Metrics

| Metric | Value |
| --- | ---: |
| Periods | 103 |
| Effective period sample size | 103.000 |
| Gross compound return | 2203.66% |
| Net compound return | 2110.27% |
| Strict equal-weight buy-and-hold | 931.00% |
| Strict hold max drawdown | -47.99% |
| Matched passive return | 875.73% |
| Matched passive max drawdown | -38.98% |
| Excess vs. strict hold | 1179.27% |
| Excess vs. matched passive | 1234.54% |
| Paired log-excess 95% CI vs. strict hold | [-0.0005, 0.0167] log excess |
| Paired log-excess 95% CI vs. matched passive | [-0.0013, 0.0187] log excess |
| Mean net monthly return | 3.55% |
| Max drawdown (daily close marks) | -41.59% |
| Annualized Sharpe | 1.190 |
| Net mean-return p-value | 0.001 |

## Audit notes

- The ranking uses only prices available at the month-end decision; orders fill at the next common-session open.
- The strict benchmark uses the exact same first entry and final exit dates; matched passive uses the exact same rebalance dates and investable universe.
- Confidence intervals are for paired monthly log excess; they are descriptive and do not correct for all parameter/universe searches.
- The strategy is not evidence that the AI analyst layer has predictive skill; it is a separate deterministic allocation rule.
- The p-value uses a temporal effective sample size; non-overlapping periods still share serial, market, and sector shocks, so treat it as descriptive.
- Universe selection and parameter selection remain separate research choices and must be frozen before a final holdout.

## Automatic Quality Analysis

> [Status: Warning] Research-only diagnosis. No strategy parameters or predictions were changed.

- [Status: Warning] `historical_win_only` — The observed net return beat strict hold on this inspected window; this is not independent validation.
- [Status: Warning] `excess_uncertain` — The paired 95% excess-return interval is unavailable or includes zero.
- [Status: Warning] `return_basis_unverified` — Dividend and terminal-return treatment is not verified for the price input.
- [Status: Warning] `search_count` — Ledger has 10 unique recorded candidate arms; earlier/manual searches are not reconstructed.

### Next checks

- Freeze the rule and data snapshot; use an untouched forward period for confirmation.

## Experiment Ledger

- Appended run `43f90034-c2ea-4c31-838e-ac4d80968224` as row 5 to `/private/tmp/momentum-reliability-20261009/experiments.jsonl`.
- Recorded candidate arms so far: 10; pre-ledger and manual searches are not reconstructed, and cross-run DSR is not applied.
- New / repeated evaluation arms this run: 2 / 0.
