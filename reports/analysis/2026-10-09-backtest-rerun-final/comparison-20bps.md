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
| rolling_long | $11,999.06 | +19.99% | -0.47% | +0.00% | -15.22% | 96 | 9.0 | +48.96% | +0.120 | +63.66% |
| signal_timing_long | $10,028.82 | +0.29% | -20.18% | -1.51% | -3.17% | 3 | 3.0 | +33.33% | +0.071 | +54.06% |
| ft_weighted | $9,742.32 | -2.58% | -23.04% | +0.80% | -5.86% | 20 | 7.0 | +55.00% | -0.145 | +35.40% |
| ft_agreement | $10,000.00 | +0.00% | -20.46% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |

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
| rolling_long | +69.52% | +115.13% | 249/249 (+100.00%) |
| signal_timing_long | +2.52% | +10.00% | 63/249 (+25.30%) |
| ft_weighted | +15.93% | +44.18% | 186/249 (+74.70%) |
| ft_agreement | +0.00% | +0.00% | 0/249 (+0.00%) |

### Cash-yield diagnostic

- Unavailable: No dated FRED:DFF replay was supplied.

### Benchmark gate

- Observed benchmark: `buy_and_hold`; return leader: `rolling_long`.
- Promotion gate: **FAIL** (the `overall` pipeline must beat strict hold after costs, have effective n ≥ 30, DSR ≥ 95%, positive lower 95% paired block-bootstrap bound, positive excess at 2× costs, and max drawdown within 5 percentage points of strict hold).
- This is the numerical backtest gate only; point-in-time universe, provider, evidence, and external cost-calibration gates are checked separately.

### Selection bias

`buy_and_hold` posted the best per-trade Sharpe (+0.575) out of 11 strategies scored on the same trials. That comparison is itself a search, so its Sharpe is an order statistic rather than an unbiased estimate.
- Deflated Sharpe unavailable — too few independent trades to estimate it.
