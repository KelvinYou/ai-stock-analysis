# Momentum allocation signals — completed November 5 panel

[Status: Warning] Yahoo November 5 closes remain missing. This rerun supplements only that completed session with Stock Analysis OHLCV, attributed by that service to S&P Global Market Intelligence. Raw Yahoo inputs remain in prices/; completed inputs are in completed-prices/; row-level source URLs and hashes are in supplemental-source.json. Historical adjusted prices remain Yahoo data. Supplemental adjusted closes equal closes. This is a mixed-source research calculation, not independently verified total-return evidence.

Strategy: fixed eight names, twelve-month momentum, top three equal weights, monthly rebalance. No AI calls, broker orders or private holding changes.

Latest daily preview: 2026-11-05. November monthly model: 2026-10-30. Monthly ranking and targets exactly match the prior run. Daily order changes from TSM/V/UNH to V/UNH/TSM; basket membership does not change.

| Rank | Ticker | November 5 close (USD) | Twelve-month return | Daily target |
|---:|---|---:|---:|---:|
| 1 | V | 422.54 | 25.26% | 33.33% |
| 2 | UNH | 395.63 | 23.93% | 33.33% |
| 3 | TSM | 351.76 | 21.06% | 33.33% |
| 4 | COST | 1066.46 | 14.73% | 0.00% |
| 5 | MSFT | 536.21 | 6.60% | 0.00% |
| 6 | NVDA | 181.84 | -6.63% | 0.00% |
| 7 | AVGO | 291.54 | -18.18% | 0.00% |
| 8 | ORCL | 115.19 | -53.37% | 0.00% |

Monthly transition versus October remains: V enters; NVDA exits; TSM and UNH retained. AVGO was already outside the basket. Daily ranking is a preview and does not trigger extra intramonth rebalance. Weights apply to this strategy sleeve only; promotion_ready=false.

Reproduce:

```bash
repos/ai-stock-analysis/.venv/bin/python repos/ai-stock-analysis/scripts/refresh_momentum_dashboard.py --prices-dir repos/ai-stock-analysis/reports/analysis/2026-11-06-momentum-signals/completed-prices --price-evidence repos/ai-stock-analysis/reports/analysis/2026-11-06-momentum-signals/price-evidence.json
```
