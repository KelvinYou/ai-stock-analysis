# Historical evidence and pipeline flow implementation review

[Status: Warning] Engineering checks pass. No new out-of-sample profitability claim.

## Completed loops

1. Added multi-period fiscal observations, filing vintages, duration/currency provenance,
   diluted EPS, shares and explicitly dated valuation-price replay. Old artifacts load.
2. Preserved comparative periods and revisions in SEC replay; wired history into API
   backtests, sealed session packets and the fundamental analyst tools. Date-only SEC
   facts are available the next calendar day. Readiness distinguishes a statement from
   sufficient growth or valuation evidence.
3. Corrected canonical flow: optional Research Manager and resolved Outcome Memory
   feed synthesis; analyst reports and debate also feed synthesis directly. Consensus
   and actionability precede deterministic risk checks. Mermaid and the actual React
   SVG consume the same 19 explicit edges. CI now checks graph/render consistency.
4. Adversarial review fixed stale EPS windows, finite-derived-value overflow,
   currency mixing, partial long-term debt labeling, historical tool reuse of current
   valuation, enriched packet corruption before outcome fetching, and session overwrite.

## Validation

- Full Python suite: **318 passed, 4 subtests passed**. One existing FastAPI/httpx deprecation warning.
- `ruff check src tests scripts`: pass.
- OpenAPI snapshot regenerated with additive financial fields and existing signal trace
  fields; OpenAPI, Postman and generated architecture checks pass.
- Web TypeScript, canonical layout/server-rendered SVG check: pass (20 nodes, 19 edges).
- Offline Next.js production build: pass; existing image/a11y lint warnings remain.
- Actual component SVG raster visually inspected; corrected preview attached. No
  browser was available, so interactive browser/end-to-end validation is not claimed.
- Initial dev/build overlap caused a shared `.next` conflict; stopped our dev server
  and reran the offline build independently successfully.
- Frozen historical comparison verification: pass, 60 trade/cost checks; input/script
  hashes match, ticker order invariance holds, experiment ledger has 6 valid chained rows.
- Prospective cohort verification: 31 immutable forecasts, 7 buy / 22 neutral / 2 sell.
  No prospective outcomes scored, forecasts rewritten, or production thresholds tuned.
- Source/doc whitespace check passes; existing tracked price CSV CRLF warnings in the
  wider dirty worktree were left unchanged.

## Meaning and limits

The existing 10-bps-per-side pilot remains: long hold **+20.6646%**, full pipeline
**0%** with no buys, fundamentals + technical **−2.2037%**. The engineering upgrade
adds reliable input contracts and exposes gaps; it does not retroactively enrich
those sealed predictions or prove that fundamentals can beat hold. The observed FT
improvement over technical was wholly attributable to skipping one ORCL trade.

SEC CompanyFacts alone does not authenticate original-vintage completeness or a
corporate-action/share basis. A declared matching basis is not independent proof;
valuation stays unavailable when missing. The yfinance fallback is provider-current
financial data with filing clocks, not authenticated original-vintage data. Listing
currency can differ from primary-statement currency; growth remains within one
reporting currency and valuation requires a direct price/EPS currency match. Replay
providers must choose an authoritative primary representation when several currencies
or overlapping fiscal durations coexist. Complete provider-backed evidence and fresh
sealed forecasts are prerequisites for the next profitability experiment. Historical
model predictions may contain knowledge of subsequent outcomes and remain exploratory.

See [design and contract map](../../../docs/design/historical-fundamental-evidence.md),
[canonical architecture](../../../architecture.md), [prior audit](../2026-10-08-ft-backtest/audit.md)
and [flow preview](pipeline-preview.png). Implementation hashes record the reviewed
working-tree state; this report is not a new backtest experiment.
