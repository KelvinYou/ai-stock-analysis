# Historical issuer evidence backfill

[Status: Warning] Core financial input coverage is filled. This is evidence
preparation, with no new forecasts or profitability result. Full historical
news, macro vintages and independently authenticated share bases remain open.

## Delivered

Downloaded and hash-bound **98 issuer documents/index pages**, captured eight
separate valuation-price histories, and extracted **71 dated fiscal observations**
for the unchanged AVGO, NVDA, MSFT, TSM, V, UNH, ORCL and COST universe. Prepared
**96 new packets** in [session-enriched](session-enriched/manifest.json), using the
original twelve dates, 365-day lookback and 30-day horizon. The technical bars
are identical to the frozen pilot; old forecasts and scored results were not
rewritten or attached to these new inputs.

| Evidence | Frozen pilot | New enriched packets |
| --- | --- | --- |
| Available financial statement | 55/96 | 96/96 |
| At least four fiscal history periods | 0/96 | 96/96 |
| Comparable year-ago revenue/profit growth | 0/96 | 96/96 |
| Computable same-declared-basis historical P/E | 0/96 | 96/96 |
| Same-quarter free cash flow | Not separately audited | 84/96 |
| At least one known issuer earnings event | 0/96 | 96/96 |
| Market cap from dated period-end shares | Unavailable | 0/96 |

Counts are input coverage, not trading performance or statistical significance.
The issuer-event count means at least one prior earnings announcement; events
are cumulative and do not represent complete recent news or sentiment coverage.
P/E is sum-of-four-quarter diluted EPS against a separate dated Close, with a
declared matching basis; it is not independent corporate-action authentication.
Detailed ticker counts and packet hashes: [coverage.json](coverage.json).

## Data and calculation rules

- Source URLs, retrieval timestamps and file hashes are retained in
  [download-manifest.json](download-manifest.json), [price-manifest.json](price-manifest.json)
  and every financial fact's provenance. SEC CompanyFacts and several investor
  domains returned HTTP 403; accessible original issuer newsrooms, official
  report/CDN PDFs and Broadcom-issued PRNewswire releases supplied the evidence.
- Use actual GAAP quarterly revenue, net income and diluted EPS. Income is
  scaled from issuer-declared millions/billions; Oracle narrative revenue/profit
  and Visa summary revenue retain issuer rounding. UNH net income is attributable
  to common shareholders as explicitly labeled in its statement.
- Fiscal weeks are retained: Costco quarters are 12/16 weeks; NVIDIA/Broadcom
  use their declared quarterly end dates and 13-week periods. Three explicit
  year-ago comparative columns fill initial AVGO/COST/ORCL comparison gaps.
- Availability is conservatively the issuer publication date plus one calendar
  day. No fiscal-end date substitutes for a publication clock. Original-vintage
  completeness is not certified merely because a document is retrieved today.
- TSMC revenue/profit/FCF stay in TWD. Its explicitly issuer-quoted USD-per-ADR
  diluted EPS is separately labeled `diluted_eps_currency="USD"` and `TSM-ADR`.
  No FX conversion is inferred. Native-share EPS is not paired with an ADR price.
- P/E uses Yahoo Finance `Close` with `auto_adjust=False`, not `Adj Close` or the
  dividend-adjusted technical bars. Close remains split adjusted. No provider
  split events occur within this pilot; the broader split/basis history is still
  provider-declared. Prices are knowable at the historical session-date close;
  the original execution policy enters at a subsequent open. Rows beyond each
  cutoff are excluded from packets.
- FCF uses matching quarterly operating cash less capex; NVIDIA also subtracts
  property/equipment principal payments. UNH/Costco fiscal-YTD differences are
  taken only across the same fiscal start and adjoining quarter ends, with both
  source documents and their availability retained. Visa/TSMC explicitly issuer-
  defined FCF is labeled in provenance. Annual/YTD totals are never inserted as
  quarterly cash flow. Debt lacking a full reported sum is explicitly partial.
- News replay is classified `issuer_event_subset`, exposed as `historical_replay`.
  It does not pass a provider-versioned historical-news gate. Macro replay retains
  the original dated FRED DFF snapshots and does not manufacture missing indicators.

## Remaining evidence gaps

1. **ORCL quarterly FCF: 12 windows.** The selected sources include annual/YTD/TTM
   cash-flow presentations and rounded narratives, but do not supply every paired
   fiscal-YTD observation needed for the current quarter. These values stay missing.
2. **Market cap: all 96 windows.** Period-end outstanding shares on the matching
   listing basis are not extracted/authenticated. Diluted weighted-average shares
   are not substituted for outstanding shares.
3. **Sentiment and macro completeness.** Selected earnings announcements are not
   a full independent archived news feed. DFF alone does not fill inflation,
   sector/geopolitical data or certify original macro vintages.
4. **Research validity.** Fixed current survivors, provider-retrieved price vintage,
   declared share basis, hypothetical transaction costs, historical model recall
   and the already inspected pilot outcomes remain limitations. No thresholds,
   strategy search width or portfolio rules changed in this evidence build.

## Verification and use

- **319 Python tests passed, 4 subtests passed**; Ruff and OpenAPI snapshot checks
  pass. One existing FastAPI/httpx deprecation warning remains.
- **37 targeted issuer checks**, 98 raw-source hashes and 71 fiscal observations
  validated before packet preparation. Regression checks cover actual EPS versus
  weighted share counts, quarter EPS versus full-year outlook, signed losses,
  source clocks, PDF row ordering, fiscal-YTD cash-flow differences and ADR units.
- **96 packet contexts/hashes** verified against source observations and cutoffs;
  separate valuation Close values match their cached source. Original technical
  packet hashes match. The original comparison still passes 60 trade/cost checks
  and its six-row experiment-ledger chain. All 31 forward forecasts verify unchanged.
- Failed/partial extraction iterations are quarantined in `drafts/`; use only
  `session-enriched/`. They contain no predictions and must not be scored.

From the stock repository, verification is offline and repeatable:

```bash
.venv/bin/python reports/analysis/2026-10-08-evidence-backfill/verify.py
```

The one-off PDF extractor requires `pypdf` (6.19.0 used here), plus the repository's
existing pandas/BeautifulSoup/lxml dependencies. Its scripts and replay inputs are
bound by [protocol.json](protocol.json). Preparation refuses to overwrite a session;
reproduction must use a new output directory.

**Next profitability experiment:** form fresh complete schema-valid predictions
from these packets, then use the normal session scorer and portfolio comparison
for full pipeline, fundamental+technical and strict long hold. Preserve the sample,
cost stress and multiple-testing accounting. An in-session historical run remains
exploratory; it is not prospective validation. No new predictions, provider-run
authentication, outcome score or promotion decision is present in this artifact.
