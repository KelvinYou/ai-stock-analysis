# Return-source and cost evidence audit — 2026-10-09

[Status: Warning] Supplemental current-provider data captured; original sealed backtest prices unchanged.

## Return basis

Installed yfinance 1.6.0 history defaults to auto_adjust=True. The local fetcher uses that default and persists only OHLCV; the historical adapter explicitly enables auto adjustment. The library scales OHLC by Adj Close / Close. [Official API documentation](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html) documents automatic OHLC adjustment and available action APIs. Therefore the stored series is provider-adjusted, not verified unadjusted trade fills or a separately audited dividend cash ledger. Adding dividends again would risk double counting.

An independent supplementary fetch requested auto_adjust=False and actions=True for all eight symbols over 2016-04-22 through 2026-09-17. Current-provider snapshots retain unadjusted OHLC, Adj Close, Dividends and Stock Splits. Hashes and capture clocks are in return-source-audit-network/summary.json. These are a new current vintage, not original historical data availability proof or an authenticated terminal-return source.

| Symbol | Dividend events | Split events | Matched sessions | Maximum close difference after endpoint normalization |
|---|---:|---:|---:|---:|
| AVGO | 41 | 1 | 2538 | 0.1825% |
| COST | 45 | 0 | 2499 | 0.0001% |
| MSFT | 42 | 0 | 2616 | 0.4054% |
| NVDA | 42 | 2 | 2616 | 0.2339% |
| ORCL | 41 | 0 | 2537 | 0.0002% |
| TSM | 33 | 0 | 2538 | 0.2684% |
| UNH | 42 | 0 | 2538 | 0.6158% |
| V | 42 | 0 | 2538 | 0.1858% |

Endpoint normalization removes one constant later adjustment factor so relative historical paths can be compared. This is a descriptive cross-vintage consistency check, not event-by-event total-return reconciliation. Original data lacks action snapshots/adjustment factors, and complete delisting, merger, dividend tax and fractional reinvestment treatment remains unverified. No total-return promotion gate is passed.

## Cost calibration

The previous 10/20/50bps runs remain assumptions. Broker, account plan and order notional have been requested from the owner and are not yet known. No unrelated broker fee schedule is substituted. Dated commission/platform minimums, sell-side fees, share-based charges, currency conversion, spread and slippage must be assessed for actual orders; convert fixed charges to bps with 10,000 × dollar charge / order notional. Execution slippage needs fills or measured spread evidence, not just a published commission table.

cost-evidence.json preserves unknown fields as null and calibration status as unavailable. Fee schedules can establish quoted fees once the broker/plan is identified; complete execution calibration may still require actual order/fill data. This does not authorize live transactions.
