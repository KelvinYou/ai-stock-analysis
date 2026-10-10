# Cross-Sectional Momentum Research Report

> **Hypothesis:** At each month-end, the top 3 of a fixed universe by 12-month trailing return will outperform equal-weight buy-and-hold after costs.
>
> This is a deterministic portfolio-construction experiment, not an AI forecast or live-trading recommendation.

## Protocol

- Universe: AVGO, COST, MSFT, NVDA, ORCL, TSM, UNH, V
- Data: 2016-04-22 → 2026-09-01
- Out-of-sample: 2018-01-31 → 2026-09-01
- Signal-date cutoff: 2026-08-14
- Signal: rank trailing 12-month close-to-close return at the last common session of each month
- Execution: next common-session open; rebalance/exit at the following signal's next-session open
- Portfolio: equal weight top 3; matched passive rebalances equal weight across the same names and dates
- Cost: 80.0 bps per side, charged on actual one-way turnover; final liquidation included
- Missing prices: no forward-fill; only synchronized common sessions are used
- Bootstrap: moving blocks of 3 paired monthly periods, 2000 resamples, seed 0
- Price basis: provided_open_close_not_dividend_verified; dividend/total-return treatment must be verified before interpreting CAGR

## Metrics

| Metric | Value |
| --- | ---: |
| Periods | 103 |
| Effective period sample size | 103.000 |
| Gross compound return | 1317.91% |
| Net compound return | 1126.14% |
| Strict equal-weight buy-and-hold | 967.34% |
| Strict hold max drawdown | -34.73% |
| Matched passive return | 763.49% |
| Matched passive max drawdown | -31.34% |
| Excess vs. strict hold | 158.80% |
| Excess vs. matched passive | 362.65% |
| Paired log-excess 95% CI vs. strict hold | [-0.0037, 0.0081] log excess |
| Paired log-excess 95% CI vs. matched passive | [-0.0032, 0.0113] log excess |
| Mean net monthly return | 2.76% |
| Max drawdown (daily close marks) | -36.01% |
| Annualized Sharpe | 1.214 |
| Net mean-return p-value | 0.001 |

## Audit notes

- The ranking uses only prices available at the month-end decision; orders fill at the next common-session open.
- The strict benchmark uses the exact same first entry and final exit dates; matched passive uses the exact same rebalance dates and investable universe.
- Confidence intervals are for paired monthly log excess; they are descriptive and do not correct for all parameter/universe searches.
- The strategy is not evidence that the AI analyst layer has predictive skill; it is a separate deterministic allocation rule.
- The p-value uses a temporal effective sample size; non-overlapping periods still share serial, market, and sector shocks, so treat it as descriptive.
- Universe selection and parameter selection remain separate research choices and must be frozen before a final holdout.
