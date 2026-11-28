# Strategy comparison (price-only, point-in-time)

Universe: AAPL, AMZN, AVGO, COST, ETN, GOOGL, IBM, JPM, META, MSFT, NFLX, NVDA, ORCL, TSLA, TSM, UNH, V · 2018-01-31 → 2026-09-01 · 103 monthly periods (effective N 103.0) · 20 bps/side · top 3

| Strategy | Net return | Max DD | Sharpe | Exposure | Excess vs hold | 95% CI (log excess, mean/mo) | DSR (excess) |
|---|---|---|---|---|---|---|---|
| Equal-weight continuous hold | +702.8% | -41.8% | 1.07 | 100% | — | — | — |
| MA distance + sell buffer | +1487.5% | -37.3% | 1.14 | 100% | +784.7 pp | [-0.0037, +0.0169] | 0.25 |
| MA distance (21d / 200d) | +1387.3% | -41.2% | 1.14 | 100% | +684.5 pp | [-0.0041, +0.0167] | 0.21 |
| Momentum 12-1 | +1249.7% | -44.9% | 1.06 | 100% | +546.9 pp | [-0.0058, +0.0158] | 0.15 |
| Momentum 12m (current allocator) | +1099.2% | -42.0% | 1.00 | 100% | +396.4 pp | [-0.0064, +0.0146] | 0.10 |
| Dual momentum | +1060.1% | -43.8% | 0.99 | 100% | +357.4 pp | [-0.0069, +0.0145] | 0.09 |
| Revenue growth | +947.0% | -53.0% | 0.98 | 100% | +244.2 pp | [-0.0061, +0.0126] | 0.07 |
| Short-term reversal | +896.1% | -52.7% | 1.00 | 100% | +193.3 pp | [-0.0104, +0.0128] | 0.05 |
| Strong quality only (equal weight) | +763.8% | -44.1% | 1.19 | 100% | +61.1 pp | [-0.0068, +0.0076] | 0.03 |
| Quality + momentum | +651.9% | -40.4% | 1.02 | 100% | -50.9 pp | [-0.0078, +0.0068] | 0.01 |
| Quality (profitability, cash, leverage) | +599.9% | -36.2% | 1.06 | 100% | -102.9 pp | [-0.0115, +0.0074] | 0.01 |
| Quality, only above 200-day SMA | +546.9% | -36.3% | 1.05 | 98% | -155.9 pp | [-0.0110, +0.0061] | 0.01 |
| Technical blend + trend filter | +380.6% | -32.2% | 0.88 | 98% | -322.2 pp | [-0.0149, +0.0050] | 0.00 |
| Low volatility | +366.4% | -29.6% | 1.09 | 100% | -336.4 pp | [-0.0162, +0.0060] | 0.00 |
| Trend: price > 200-day SMA | +313.1% | -22.3% | 1.18 | 72% | -389.7 pp | [-0.0131, +0.0004] | 0.00 |
| Time-series momentum | +306.0% | -28.5% | 1.04 | 79% | -396.8 pp | [-0.0127, -0.0008] | 0.00 |
| Buy only strong quality (rest cash) | +99.0% | -15.1% | 1.19 | 29% | -603.8 pp | [-0.0245, -0.0032] | 0.00 |

- Monthly decisions; fills at the next common session open; one-way cost on turnover.
- 16 rules were compared; the deflated Sharpe corrects for that search.
- Universe is a fixed, curated watchlist of surviving large caps (survivorship-biased) and has been inspected before; dip-buying rules look better there than they would on a point-in-time index.
- Fundamental rules use SEC CompanyFacts by filing date plus one day, from the latest fiscal year (up to ~18 months old); value ratios are excluded because split-adjusted prices cannot be divided by as-reported per-share data.
- Prices are provider-adjusted; dividends, taxes and real-world fills are unverified.
