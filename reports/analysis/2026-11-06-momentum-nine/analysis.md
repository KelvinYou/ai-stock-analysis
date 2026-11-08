# Nine-stock momentum rerun — 2026-11-06

[Status: Warning] Universe changed from eight to nine by adding only GOOGL. New strategy ID: momentum-9-12m-top3-v2. Original eight-name historical results do not validate this strategy. No historical backtest or parameter search was run. Rules remain twelve-month momentum, equal-weight top three, monthly rebalance. No personal holdings were modified.

GOOGL November 5 OHLCV was supplemented from [Stock Analysis](https://stockanalysis.com/stocks/googl/history/) because the Yahoo close was missing. Original Yahoo response and supplemental row are retained alongside the completed panel. All nine names use November 5 for the daily ranking.

| Rank | Ticker | Twelve-month daily return | Target weight |
|---:|---|---:|---:|
| 1 | V | 25.26% | 33.33% |
| 2 | UNH | 23.93% | 33.33% |
| 3 | TSM | 21.06% | 33.33% |
| 4 | COST | 14.73% | 0.00% |
| 5 | MSFT | 6.60% | 0.00% |
| 6 | GOOGL | -0.35% | 0.00% |
| 7 | NVDA | -6.63% | 0.00% |
| 8 | AVGO | -18.18% | 0.00% |
| 9 | ORCL | -53.37% | 0.00% |

Monthly model as of October 30 remains TSM, V, UNH. GOOGL ranks seventh at -0.22%, target zero; daily preview ranks it sixth at -0.35%, also zero. Nonselection is a relative-momentum outcome, not a fundamental sell verdict.

Reproduce:

```bash
repos/ai-stock-analysis/.venv/bin/python repos/ai-stock-analysis/scripts/refresh_momentum_dashboard.py --prices-dir repos/ai-stock-analysis/reports/analysis/2026-11-06-momentum-nine/prices --price-evidence repos/ai-stock-analysis/reports/analysis/2026-11-06-momentum-nine/price-evidence.json
```
