# Cross-Sectional Momentum Research Report

> **Hypothesis:** At each month-end, the top 3 of a fixed universe by 12-month trailing return will outperform equal-weight buy-and-hold after costs.
>
> This is a deterministic portfolio-construction experiment, not an AI forecast or live-trading recommendation.

## Protocol

- Universe: AVGO, COST, MSFT, NVDA, ORCL, TSM, UNH, V
- Data: 2016-10-07 → 2026-02-02
- Out-of-sample: 2024-01-31 → 2026-02-02
- Signal-date cutoff: 2025-12-31
- Signal: rank trailing 12-month close-to-close return at the last common session of each month
- Execution: next common-session open; rebalance/exit at the following signal's next-session open
- Portfolio: equal weight top 3; matched passive rebalances equal weight across the same names and dates
- Cost: 10.0 bps per side, charged on actual one-way turnover; final liquidation included
- Missing prices: no forward-fill; only synchronized common sessions are used
- Bootstrap: moving blocks of 3 paired monthly periods, 2000 resamples, seed 0
- Price basis: provided_open_close_not_dividend_verified; dividend/total-return treatment must be verified before interpreting CAGR

## Metrics

| Metric | Value |
| --- | ---: |
| Periods | 24 |
| Effective period sample size | 24.000 |
| Gross compound return | 128.80% |
| Net compound return | 127.39% |
| Strict equal-weight buy-and-hold | 82.27% |
| Strict hold max drawdown | -24.68% |
| Matched passive return | 73.57% |
| Matched passive max drawdown | -21.68% |
| Excess vs. strict hold | 45.12% |
| Excess vs. matched passive | 53.82% |
| Paired log-excess 95% CI vs. strict hold | [-0.0064, 0.0177] log excess |
| Paired log-excess 95% CI vs. matched passive | [-0.0075, 0.0220] log excess |
| Mean net monthly return | 3.84% |
| Max drawdown (daily close marks) | -35.53% |
| Annualized Sharpe | 1.522 |
| Net mean-return p-value | 0.042 |

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
- [Status: Warning] `small_period_sample` — Fewer than 30 monthly periods were observed.
- [Status: Warning] `return_basis_unverified` — Dividend and terminal-return treatment is not verified for the price input.
- [Status: Warning] `search_count` — Ledger has 18 unique recorded candidate arms; earlier/manual searches are not reconstructed.

### Next checks

- Freeze the rule and data snapshot; use an untouched forward period for confirmation.

## Experiment Ledger

- Appended run `19b01bb4-be48-4c9f-aee0-e8154233c280` as row 11 to `/private/tmp/momentum-reliability-20261009/experiments.jsonl`.
- Recorded candidate arms so far: 18; pre-ledger and manual searches are not reconstructed, and cross-run DSR is not applied.
- New / repeated evaluation arms this run: 2 / 0.
