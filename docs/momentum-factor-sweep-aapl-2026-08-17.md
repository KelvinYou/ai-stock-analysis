# Momentum Factor Parameter Sweep

> [Status: Warning] This is a historical research result, not a live-trading recommendation.

## Selected protocol

The selected candidate is **20-bar lookback / 20-bar holding**, with a long
position only when close-to-close momentum is positive.

- Data: local `data/AAPL/price_history.csv`, 2016-04-22 → 2026-08-14
- Signal: positive 20-bar close-to-close momentum
- Execution: next-bar open → close after 20 trading bars
- Trades: non-overlapping
- Walk-forward: 252-bar initial warm-up, 63-bar out-of-sample windows
- Primary cost assumption: 10 bps/side (20 bps round trip)
- Stress cost: 30 bps/side (60 bps round trip)

## Selection protocol

I evaluated the grid below:

- Lookback: 5, 10, 20, 40, 60, 120 bars
- Holding: 5, 10, 20, 30, 40 bars

Parameters were selected using 2016-04-22 → 2022-12-31 only. The period from
2023-01-01 → 2026-08-14 was then treated as a frozen holdout. Ranking considered
net compound return, fold stability, Sharpe, and drawdown; it was not based on
the single highest full-history return.

## AAPL holdout comparison

| Lookback / holding | Net return | Max drawdown | Sharpe | Positive folds | Trades |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 60 / 20 | 68.89% | -18.50% | 1.124 | 58.33% | 28 |
| **20 / 20** | **67.72%** | **-14.34%** | **1.316** | **75.00%** | **25** |
| 20 / 30 | 54.66% | -12.36% | 1.181 | 70.00% | 16 |
| 20 / 10 | 52.14% | -12.39% | 1.122 | 57.14% | 51 |
| 5 / 5 | 40.49% | -14.92% | 0.928 | 73.33% | 92 |

The `20/20` candidate is preferred because it gives up only 1.17 percentage
points of holdout compound return versus `60/20`, while having the best Sharpe,
the highest positive-fold rate, and a materially smaller drawdown.

At 30 bps/side, `20/20` remains positive on the AAPL holdout:

- Net return: 51.73%
- Max drawdown: -15.03%
- Sharpe: 1.084
- Positive folds: 66.67%
- Mean-return p-value: 0.140

## Full AAPL run

The exact reproducible CLI run is:

```bash
stock-analysis-backtest \
  --mode factor \
  --tickers AAPL \
  --start 2016-04-22 \
  --end 2026-08-14 \
  --factor-lookback-bars 20 \
  --factor-holding-bars 20 \
  --walk-forward-train-bars 252 \
  --walk-forward-test-bars 63 \
  --cost-bps 10 \
  --output /tmp/aapl-factor-20-20-10bps
```

This produces 71 trades across 37 out-of-sample folds:

- Gross compound return: 623.90%
- Net compound return: 528.03%
- Buy-and-hold over the same OOS window: 830.77%
- Max drawdown: -19.46%
- Annualized Sharpe: 1.390
- Net mean-return p-value: 0.002

The factor did not beat AAPL buy-and-hold over this full window. Its result is
therefore evidence about this particular rule and data, not proof of durable
alpha.

## Cross-ticker sensitivity

The holdout was also checked on 12 local US ticker series: AAPL, AMZN, AVGO,
GOOGL, META, MSFT, NVDA, RKLB, TSLA, TSM, UNH, and V. Results below are the
median across tickers; `RKLB` is shown separately because its extreme move can
distort averages.

| Config | Cost | Positive tickers | Median net | Median Sharpe | Median drawdown |
| ---: | ---: | ---: | ---: | ---: | ---: |
| **20 / 20** | **10 bps** | **10 / 12** | **62.03%** | **1.228** | **-18.92%** |
| 20 / 30 | 10 bps | 11 / 12 | 70.19% | 0.980 | -19.09% |
| 60 / 20 | 10 bps | 10 / 12 | 70.42% | 0.922 | -18.80% |
| **20 / 20** | **30 bps** | **10 / 12** | **46.86%** | **1.002** | **-20.92%** |
| 20 / 30 | 30 bps | 10 / 12 | 59.58% | 0.872 | -20.21% |
| 60 / 20 | 30 bps | 10 / 12 | 51.11% | 0.802 | -21.12% |

Excluding RKLB, `20/20` still had 9/11 positive tickers and a 41.99% median
net return at 30 bps/side. The cross-ticker comparison supports `20/20` as the
risk-adjusted default, while `20/30` is a reasonable lower-turnover alternative.

## Conclusion

Use **20-bar lookback / 20-bar holding / 10 bps per side** as the current
research baseline. Do not treat it as globally optimal or as a trade signal:
the parameters were searched, the sample is historical, and the AAPL factor
still lagged buy-and-hold over the full out-of-sample window.
