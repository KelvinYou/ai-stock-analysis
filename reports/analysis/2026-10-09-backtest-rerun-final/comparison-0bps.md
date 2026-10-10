## Portfolio simulation

- Starting balance: $10,000.00
- Position size: 10.0% of pre-session cash per trade; same-day orders share one cash snapshot and are capped at 100% in aggregate
- Shorts enabled: False
- Transaction cost: **none modelled** — returns are gross
- Drawdown: daily close mark-to-market when shared daily prices cover every trade; otherwise `n/a` (event-only marks are incomplete).
- Matched passive: equal-weight all run-universe names on each candidate's exact active dates and dollar stakes; this conditions on signal timing and diagnoses selection/exposure only.
- `overall_fundamentals_confirmed` is a research-only alternative: it takes an overall directional signal only when the fundamentals analyst agrees. It is counted in the strategy-search denominator and is not the primary promotion candidate.

| Strategy | Final balance | Return | vs strict hold | vs matched passive | Max DD | Trades | n_eff | Win rate | Sharpe | PSR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | $10,000.00 | +0.00% | -20.86% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| overall_fundamentals_confirmed | $10,000.00 | +0.00% | -20.86% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| fundamentals | $10,000.00 | +0.00% | -20.86% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| technical | $9,446.95 | -5.53% | -26.40% | -2.15% | -9.02% | 21 | 7.0 | +57.14% | -0.221 | +26.70% |
| sentiment | $10,000.00 | +0.00% | -20.86% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| macro | $10,000.00 | +0.00% | -20.86% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |
| buy_and_hold 🏆 | $12,086.46 | +20.86% | +0.00% | n/a | -19.23% | 8 | 1.0 | +87.50% | +0.586 | n/a |
| rolling_long | $12,367.76 | +23.68% | +2.81% | +0.00% | -14.31% | 96 | 9.0 | +52.08% | +0.150 | +67.04% |
| signal_timing_long | $10,040.85 | +0.41% | -20.46% | -1.51% | -3.13% | 3 | 3.0 | +33.33% | +0.099 | +55.65% |
| ft_weighted | $9,817.05 | -1.83% | -22.69% | +0.79% | -5.59% | 20 | 7.0 | +60.00% | -0.101 | +39.89% |
| ft_agreement | $10,000.00 | +0.00% | -20.86% | n/a | +0.00% | 0 | n/a | n/a | n/a | n/a |

### Capital utilization

- Mean and peak use the sum of original trade stakes divided by starting balance, over the same price-path sessions for every strategy. Entry and exit sessions count as invested. This is a cash-deployment diagnostic, not mark-to-market exposure or beta.

| Strategy | Mean committed stake | Peak committed stake | Sessions with positions |
| --- | ---: | ---: | ---: |
| overall | +0.00% | +0.00% | 0/249 (+0.00%) |
| overall_fundamentals_confirmed | +0.00% | +0.00% | 0/249 (+0.00%) |
| fundamentals | +0.00% | +0.00% | 0/249 (+0.00%) |
| technical | +16.59% | +52.50% | 186/249 (+74.70%) |
| sentiment | +0.00% | +0.00% | 0/249 (+0.00%) |
| macro | +0.00% | +0.00% | 0/249 (+0.00%) |
| buy_and_hold | +100.00% | +100.00% | 249/249 (+100.00%) |
| rolling_long | +70.48% | +117.83% | 249/249 (+100.00%) |
| signal_timing_long | +2.52% | +10.00% | 63/249 (+25.30%) |
| ft_weighted | +15.98% | +44.42% | 186/249 (+74.70%) |
| ft_agreement | +0.00% | +0.00% | 0/249 (+0.00%) |

### Cash-yield diagnostic

- Unavailable: No dated FRED:DFF replay was supplied.

### Benchmark gate

- Observed benchmark: `buy_and_hold`; return leader: `rolling_long`.
- Promotion gate: **FAIL** (the `overall` pipeline must beat strict hold after costs, have effective n ≥ 30, DSR ≥ 95%, positive lower 95% paired block-bootstrap bound, positive excess at 2× costs, and max drawdown within 5 percentage points of strict hold).
- This is the numerical backtest gate only; point-in-time universe, provider, evidence, and external cost-calibration gates are checked separately.

### Selection bias

`buy_and_hold` posted the best per-trade Sharpe (+0.586) out of 11 strategies scored on the same trials. That comparison is itself a search, so its Sharpe is an order statistic rather than an unbiased estimate.
- Deflated Sharpe unavailable — too few independent trades to estimate it.
