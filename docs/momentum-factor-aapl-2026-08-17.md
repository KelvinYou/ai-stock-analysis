# Momentum Factor Research Memo — AAPL

Date: 2026-08-17  
Data: local `data/AAPL/price_history.csv`, 2020-01-02 → 2026-08-14  
Protocol: 20-bar momentum, next-bar open entry, 20-bar holding period, 10 bps/side cost

## Hypothesis

If 20-bar close-to-close momentum is positive at the signal close, the next
20-bar long trade should have a positive return after transaction costs.

## Walk-forward result

The experiment used a 252-bar initial warm-up and 63-bar expanding
out-of-sample test windows. It produced 67 non-overlapping opportunities and 44
active trades.

| Metric | Result |
| --- | ---: |
| Gross compound return | 87.94% |
| Net compound return | 72.10% |
| Buy-and-hold over the same OOS window | 137.49% |
| Mean trade return, gross / net | 1.66% / 1.45% |
| Win rate | 61.36% |
| 95% Wilson interval | 46.62% → 74.28% |
| Max drawdown, net | -22.05% |
| Annualized Sharpe, net | 0.783 |
| Net mean-return p-value | 0.151 |

## Interpretation

This is a useful engineering artifact, not evidence that the factor has a
durable edge. The strategy underperformed buy-and-hold over this window, and
the confidence interval includes a 50% hit rate. The next research step is to
keep the protocol fixed while testing another time period or ticker, not to
search many lookback/holding combinations until one wins.

Full machine-readable trade/fold output is produced by:

```bash
stock-analysis-backtest --mode factor --tickers AAPL \
  --start 2020-01-01 --end 2026-08-14 \
  --cost-bps 10 --output factor-aapl
```
