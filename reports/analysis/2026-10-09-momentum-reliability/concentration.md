# Momentum return concentration — 2026-10-09

[Status: Warning] Post-hoc sensitivity analysis on the same inspected history. No strategy or universe was changed.

Contributions use additive paired monthly log excess versus continuous hold, including the benchmark entry/final-liquidation cost legs stored in the source report. Positive-contribution shares use the sum of positive log excess, not the signed net total. Removing months below omits those same intervals from both return series; it is an artificial diagnostic, not an executable strategy, fresh holdout, causal effect or forecast of expected returns. Ranking by realized excess uses hindsight.

| Universe | Months beating hold | Relative terminal wealth advantage | Top 5 share of positive log excess | Log excess after omitting best 5 |
|---|---:|---:|---:|---:|
| primary8 | 54/103 | 28.64% | 29.25% | -0.1590 |
| prior11 | 59/103 | 118.43% | 25.92% | +0.1840 |
| prior5 | 44/103 | -26.10% | 34.62% | -0.5821 |

## Primary eight-name sensitivity

| Best excess months omitted from both arms | Allocator return on remaining months | Hold return on remaining months | Remaining log excess |
|---|---:|---:|---:|
| 1 | 1101.55% | 938.06% | +0.1463 |
| 3 | 712.74% | 733.38% | -0.0251 |
| 5 | 706.85% | 845.86% | -0.1590 |
| 10 | 573.80% | 897.66% | -0.3925 |

## Primary strongest and weakest months

| Signal date | Selected tickers | Paired log excess |
|---|---|---:|
| 2024-11-29 | NVDA, TSM, AVGO | +0.1056 |
| 2020-06-30 | NVDA, MSFT, TSM | +0.0864 |
| 2023-04-28 | NVDA, ORCL, AVGO | +0.0850 |
| 2020-01-31 | MSFT, NVDA, TSM | +0.0773 |
| 2022-05-31 | AVGO, COST, UNH | +0.0566 |
| 2022-10-31 | UNH, COST, V | -0.0794 |
| 2021-11-30 | NVDA, ORCL, MSFT | -0.0723 |
| 2026-07-31 | UNH, TSM, AVGO | -0.0601 |
| 2022-12-30 | UNH, V, ORCL | -0.0566 |
| 2025-02-28 | NVDA, AVGO, ORCL | -0.0518 |

Selection frequency measures exposure, not name-level causal P&L. Details, annual contributions and omitted-month rows for all three panels are in concentration.json. Exact reconciliation with original terminal relative wealth passed for all panels. Existing uncertainty, survivor-universe and return-source limitations remain unchanged.
