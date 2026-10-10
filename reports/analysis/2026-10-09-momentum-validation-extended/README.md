# Extended momentum validation — 2026-10-09

[Status: Warning] Additional fixed-rule historical diagnostics; no confirmed edge or live activation.

## Fixed protocol and costs

Same original eight symbols, 12-month lookback, top three, equal weight, 103 monthly periods over 2018–2026. No new strategy, universe optimization or AI forecast. Primary cost is 20bps per side; fixed stresses 40 and 80bps. The owner authorized an agent-selected research cost assumption. This does not satisfy externally calibrated execution costs. [IBKR published commission tiers/minimums](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php) show that fees depend on share count, order size and pricing plan. This is context only; 20bps is our assumption, not their quote or a bound on all orders. FX, dividend withholding, ADR/custody charges, small-ticket minimums and actual spread/slippage remain unresolved.

Supplementary current-provider prices already captured in the previous audit are transformed using Adj Close / Close for OHLC, matching installed yfinance auto-adjust arithmetic. They remain a current vintage from the same provider, not an independent data source. Both snapshots are frozen by hash before runs. All eight scenarios were declared before computation and recorded in a local append-only ledger. No cross-run DSR pass is claimed.

## Current adjusted snapshot results

| Cost per side | Allocator net | Strict hold net | 95% mean monthly paired log-excess CI, 3-month blocks |
|---|---:|---:|---|
| 20bps | 1267.38% | 980.29% | [-0.00272, +0.00896] |
| 40bps | 1218.62% | 975.96% | [-0.00306, +0.00867] |
| 80bps | 1126.14% | 967.34% | [-0.00374, +0.00813] |

New-versus-original snapshot changed zero selected Top-3 sets across all 103 months. At 20bps, original return was +1267.39%; refreshed adjusted return is +1267.38%. New snapshots therefore do not explain the historical advantage or rescue significance.

## Dependence and time consistency

At 20bps, paired monthly log-excess 95% intervals with 3-, 6- and 12-month moving blocks all include zero. These intervals estimate mean monthly log excess, not cumulative percentage-point gains. Reporting all block assumptions prevents selecting only a favorable inference. Tests remain descriptive and do not correct all previously searched universes/strategies.

Of 80 overlapping trailing 24-month windows, 63 have positive paired log excess (78.75%). Relative terminal-wealth advantage ranges from -15.36% to +36.59%. Overlap makes these dependent observations; 63/80 is not a forecast success probability or 80 effective observations. Windows slice ongoing strategy/hold returns, retaining the actual original entry/final cost legs; they are not freshly restarted 24-month investment simulations. Prior best-month removal sensitivity still applies: omitting the best three excess months from both original 10bps series removes the eight-stock advantage.

## Dividend convention check

Captured raw/adjusted closes and dividend records allow a declared cash-dividend reinvest-at-close arithmetic check. Its maximum per-event daily-return difference from provider adjusted returns is about 5.91bps (TSM). Differences reflect convention/timing and provider adjustment, not an independently verified error. Split normalization is not applied twice. This calculation does not establish a broker dividend cash ledger, taxes, terminal-return coverage, historical data vintage or complete total return. No price-source promotion gate is passed.

## Verification and verdict

All eight monthly return series independently reconcile to their terminal strategy and hold returns; all input hashes are unchanged. 103 selection sets and 80 rolling windows were checked. The underlying 12 cross-sectional and 13 portfolio/cohort tests passed in the preceding validation; no production code changed, so those tests were not redundantly rerun here.

[Status: OK] Observed historical excess is insensitive to these price vintages and proportional cost stresses. [Status: Warning] Reliable excess remains unproven: all declared intervals include zero, results depend on survivor-selected universe and a few strong months, rolling windows overlap and inspected-history selection remains unresolved. No cost calibration, source-complete returns, unseen outcome maturity or forward activation is claimed. Prepared original nine-arm v2 protocol remains separate and unchanged; the current historical cost assumptions do not silently alter it.
