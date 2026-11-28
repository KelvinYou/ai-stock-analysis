# Strategy comparison (price-only, point-in-time)

Universe: AVGO, COST, MSFT, NVDA, ORCL, TSM, UNH, V · 2018-01-31 → 2026-09-01 · 103 monthly periods (effective N 103.0) · 20 bps/side · top 3

| Strategy | Net return | Max DD | Sharpe | Exposure | Excess vs hold | 95% CI (log excess, mean/mo) | DSR (excess) |
|---|---|---|---|---|---|---|---|
| Equal-weight continuous hold | +980.3% | -34.7% | 1.31 | 100% | — | — | — |
| Quality + momentum | +1462.4% | -36.0% | 1.33 | 100% | +482.1 pp | [-0.0024, +0.0103] | 0.10 |
| MA distance (21d / 200d) | +1371.7% | -29.5% | 1.40 | 100% | +391.4 pp | [-0.0019, +0.0087] | 0.06 |
| Short-term reversal | +1358.1% | -30.2% | 1.32 | 100% | +377.8 pp | [-0.0080, +0.0133] | 0.03 |
| Momentum 12m (current allocator) | +1267.4% | -35.6% | 1.26 | 100% | +287.1 pp | [-0.0027, +0.0090] | 0.04 |
| Dual momentum | +1149.1% | -35.6% | 1.22 | 99% | +168.8 pp | [-0.0042, +0.0085] | 0.02 |
| Momentum 12-1 | +1025.4% | -35.3% | 1.22 | 100% | +45.1 pp | [-0.0054, +0.0074] | 0.01 |
| MA distance + sell buffer | +880.2% | -34.2% | 1.14 | 100% | -100.1 pp | [-0.0075, +0.0055] | 0.00 |
| Revenue growth | +777.9% | -49.5% | 1.02 | 100% | -202.4 pp | [-0.0089, +0.0052] | 0.00 |
| Technical blend + trend filter | +679.9% | -30.5% | 1.19 | 96% | -300.4 pp | [-0.0100, +0.0039] | 0.00 |
| Quality (profitability, cash, leverage) | +577.5% | -41.2% | 1.02 | 100% | -402.7 pp | [-0.0120, +0.0017] | 0.00 |
| Quality, only above 200-day SMA | +554.9% | -36.0% | 1.10 | 96% | -425.4 pp | [-0.0117, +0.0012] | 0.00 |
| Strong quality only (equal weight) | +530.1% | -41.2% | 0.97 | 100% | -450.2 pp | [-0.0133, +0.0013] | 0.00 |
| Time-series momentum | +427.2% | -26.8% | 1.22 | 82% | -553.1 pp | [-0.0122, -0.0018] | 0.00 |
| Trend: price > 200-day SMA | +370.5% | -19.5% | 1.28 | 75% | -609.8 pp | [-0.0142, -0.0019] | 0.00 |
| Low volatility | +296.6% | -23.4% | 1.02 | 100% | -683.7 pp | [-0.0196, -0.0005] | 0.00 |
| Buy only strong quality (rest cash) | +118.3% | -17.3% | 1.04 | 36% | -862.0 pp | [-0.0248, -0.0070] | 0.00 |

- Monthly decisions; fills at the next common session open; one-way cost on turnover.
- 16 rules were compared; the deflated Sharpe corrects for that search.
- Universe is a fixed, curated watchlist of surviving large caps (survivorship-biased) and has been inspected before; dip-buying rules look better there than they would on a point-in-time index.
- Fundamental rules use SEC CompanyFacts by filing date plus one day, from the latest fiscal year (up to ~18 months old); value ratios are excluded because split-adjusted prices cannot be divided by as-reported per-share data.
- Prices are provider-adjusted; dividends, taxes and real-world fills are unverified.
