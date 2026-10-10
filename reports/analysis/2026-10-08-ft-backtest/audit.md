# Fundamental abstention, ORCL concentration and forward readiness audit

[Status: Warning] All three follow-up checks are complete for the evidence available on 2026-10-08. Fundamental abstention is largely explained by inadequate historical inputs. The entire observed improvement over technical is attributable to one avoided ORCL entry and the resulting capital path. The forward cohort passes integrity checks but is not mature; no outcomes were scored.

## Why fundamentals never bought

All 96 sealed fundamental reports were joined to their original point-in-time packets and guarded trial directions, with complete identity coverage:

| Ticker | No statement | Statement present, neutral | Statement present, sell | Buy |
| --- | ---: | ---: | ---: | ---: |
| AVGO | 12 | 0 | 0 | 0 |
| NVDA | 12 | 0 | 0 | 0 |
| TSM | 12 | 0 | 0 | 0 |
| MSFT | 2 | 10 | 0 | 0 |
| COST | 2 | 10 | 0 | 0 |
| V | 0 | 12 | 0 | 0 |
| UNH | 0 | 12 | 0 | 0 |
| ORCL | 1 | 0 | 11 | 0 |
| Total | 41 | 44 | 11 | 0 |

- **41 unavailable:** no qualifying historical statement was supplied. AVGO, NVDA and TSM account for 36 of these. The saved packets establish absence, not the exact upstream reason for each absence; a provider failure, missing statement or filing-date mapping failure cannot be distinguished retrospectively from these packets alone.
- **44 available but neutral:** every report explicitly identifies missing historical valuation and comparative-period growth evidence. Reports recognize positive profitability/cash generation where present, but cannot conclude that the stock was attractively priced. This is evidence abstention, not a finding that all four issuers were overvalued or fundamentally poor.
- **11 sells:** all ORCL; each packet has negative free cash flow and debt exceeding equity. These judgments concern cash generation and leverage, not inferred insolvency or an observed P/E valuation.

All 55 reports with statements have an unavailable P/E assessment and only one financial period per packet. Coverage presence therefore overstates the information available for a complete purchase thesis. Repeated dates also reuse the same statement: COST's 2025-08-31 period is reused for ten windows, including 2026-07-28, when that period is 331 days old and its mapped filing is 293 days old. This does not prove that no newer real-world filing existed.

The implementation explains these constraints: `BacktestFetcher._extract_financials` selects one mapped eligible statement column; `FinancialStatements` represents a single period without a comparative series, EPS or share count; `BacktestFetcher._build_info` intentionally leaves P/E and market capitalization absent because current shares are not historical evidence. This protective omission prevents future-share-count leakage. Relaxing the execution threshold or asking the analyst to force buys would not repair the missing evidence.

For a new source-complete experiment, the needed inputs are original-vintage, availability-dated multi-period statements and share/EPS data, with compatible price/share adjustment bases for dated valuation. Preserve fiscal periods and first-known filing timestamps; do not substitute current P/E, retrospectively revised fundamentals, or a single quarter's profit for trailing annual earnings. Freeze a new data/code protocol before new predictions and retain this incomplete-input experiment as its own record. No ingestion/model contract was changed in this audit.

## Is the FT improvement concentrated in ORCL?

Yes, exactly for this experiment. Buy-entry comparison has one differing trial: ORCL, forecast 2026-05-29, entry 2026-06-01, exit 2026-06-29. Its technical buy had a gross return of -35.90%, net return of -36.10%, USD 1,006.83 committed stake and USD -363.43 P&L. The fundamental packet used then contains free cash flow USD -11.484bn, debt USD 153.117bn and equity USD 38.495bn, period ending 2026-02-28 and available 2026-03-11. The medium-confidence fundamental sell offsets the technical buy, so FT consensus declines that entry.

**Exact counterfactual:** keep the original eight-name panel, costs, dates, rules and prices; neutralize only that technical buy. All remaining 20 trade records, including stakes and P&L, match FT weighted exactly. Technical becomes -2.20%, exactly the FT result. The improvement from -5.91% to -2.20% is therefore fully explained by this one avoided entry plus its subsequent available-cash sizing consequences. It is not 20 independent instances of demonstrated fundamental selection value.

**Issuer exclusion sensitivity:** remove ORCL from both strategies and their benchmark, retain all dates, the other seven names and 10-bps-per-side costs:

| Seven-name diagnostic | Net portfolio return | Long trades | Excess vs its own hold |
| --- | ---: | ---: | ---: |
| Technical | -2.20% | 20 | -30.25 pp |
| FT weighted | -2.20% | 20 | -30.25 pp |
| Strict equal-weight hold | +28.04% | 7 | — |

These two candidate trade lists are identical. The seven-name hold is a different benchmark basket and cannot replace the original +20.66% eight-name benchmark. Exclusion was selected after seeing outcomes and measures concentration, not robustness on a fresh holdout. The eleven-row sensitivity and its source/protocol fingerprints were appended to the experiment ledger; no cross-run DSR correction is claimed.

## Forward scoring readiness

[Status: OK] Official `prospective verify` validates all 31 immutable forecasts: 7 buy, 22 neutral, 2 sell. The manifest and all declared frozen-file hashes match. The protocol retains separate US/USD and MY/MYR portfolios and every neutral/sell forecast.

- Entry target: 2026-10-08 first eligible open.
- Exit target: 2026-11-06 first eligible close.
- Earliest scoring: **2026-11-07 UTC (08:00 MYT)**. Complete eligible market outcomes are still required; the date alone does not guarantee availability.
- The scorer checks maturity before constructing the price-fetching backtester. No early price request or outcome score was made here. The frozen cohort was not modified. No future automatic execution was scheduled.

When mature, from `repos/ai-stock-analysis`:

```bash
.venv/bin/python -m stock_analysis.backtest.prospective verify --cohort reports/analysis/2026-10-07-forward-cohort
.venv/bin/python -m stock_analysis.backtest.prospective score --cohort reports/analysis/2026-10-07-forward-cohort
```

This is one forecast-date cluster per market. Even a positive result would describe that cohort, not establish reliable long-hold outperformance across time. The existing frozen cohort validates its original pipeline forecasts; it was not retrospectively amended to introduce the newly inspected FT rule.

## Reproduction and checks

```bash
.venv/bin/python reports/analysis/2026-10-08-ft-backtest/audit.py
.venv/bin/python reports/analysis/2026-10-08-ft-backtest/verify.py
```

The audit records rules and hashes before its sensitivity simulation, but explicitly remains post-hoc. [audit.json](audit.json) retains all 96 report explanations, per-ticker categories, exact counterfactual assertions, the full eleven-strategy issuer-exclusion simulation, ledger provenance and forward readiness. [audit-protocol.json](audit-protocol.json) preserves the diagnostic specification. Both original scored inputs and all 107 sealed historical files remain unchanged. `audit.py` appends a research ledger record on rerun.
