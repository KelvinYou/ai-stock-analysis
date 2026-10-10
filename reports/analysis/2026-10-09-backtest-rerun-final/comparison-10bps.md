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
| rolling_long | $12,182.17 | +21.82% | +1.16% | +0.00% | -14.76% | 96 | 9.0 | +48.96% | +0.135 | +65.36% |
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
| rolling_long | +70.00% | +116.48% | 249/249 (+100.00%) |
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
