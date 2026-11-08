# Standalone momentum dashboard and automation

Author: Codex. Status: Owner-authorized implementation. Date: 2026-10-27.

## Scope and design

Expose `/momentum` separately from AI research and historical allocation analysis.
`config/momentum.json` owns the current fixed universe/rule. The new Python builder
reuses `allocation_snapshot.py` ranking math and owns both daily and monthly views.
No model key, analyst, debate, broker, private finance input or database is required.

```text
Public prices -> Python ranker [NEW wrapper, shared math] -> momentum.json [NEW]
GitHub schedule [NEW] -> commit validated public snapshot -> /momentum [NEW]
```

The daily preview uses one synchronized prior-UTC-date panel. Monthly targets
use only prices strictly before the current calendar month's first day and the
same 12-month/top-three rule. Recomputing a past month-end from current-vintage
prices is explicitly labeled reconstruction, not a prospectively sealed trade.
All negative returns still produce three equal sleeves; no implicit AI/cash gate.

The monthly anchor uses the last common session in the same calendar month one
year earlier, matching the backtest's monthly-close shift. The daily preview uses
the trailing calendar-date convention. These can differ by a trading day when
month-end falls on a weekend; a synthetic October 30/31 case tests that boundary.

## Ownership and compatibility

| Contract | Owner | Consumer / gate |
|---|---|---|
| Current universe and rule | `config/momentum.json` | Python builder; complete coverage required |
| Ranking math | `allocation_snapshot.py` | Existing allocation and new momentum views |
| Dashboard v1 | `momentum_dashboard.py` | TS validator, loader and page; explicit false AI/promotion flags |
| Refresh and bar validity | New refresh CLI + existing `sanitize_bars` | Failed/incomplete runs preserve last published files |
| Public delivery | Daily GitHub workflow | Production reader fetches raw public JSON and companion hash |
| Optional ticker navigation | Root layout | Degrades to empty summaries if analysis backend is unavailable |

Existing Allocation export and AI pipeline contracts remain unchanged. Runtime
JSON is public market information only; the page never computes personal sizing.

## Automation and failure behavior

Daily 01:15 UTC / 09:15 Malaysia refresh is after US close in both DST regimes.
Weekend runs handle calendar-month rollover before the next Monday Open. Download
requests exclude today's UTC date and use an 18-month history. Normal US holiday
gaps are covered by the existing four-day freshness boundary; longer gaps fail
closed rather than pretend to identify the latest exchange session.

Only pandas, pydantic and yfinance are installed in this workflow. Its built-in
GitHub token commits only the two public momentum artifacts. Production reads
the public snapshot directly, with 60-second application revalidation, so it
does not rely on a bot commit triggering another Actions workflow or a deployment.
Raw GitHub/CDN and Actions delays mean the schedule is a target, not an SLA.
On hash mismatch, invalid shape, stale prices or a missed month rollover, the page
withholds current targets. The two-file local replacement can briefly mismatch;
readers fail closed until a consistent pair is available.

Local development reads `web/data/momentum.*`. Production defaults to the
public main-branch raw URL; `MOMENTUM_SNAPSHOT_URL` overrides that server-side
source. Before publishing the workflow and route to main, scheduled operation
is configured but not activated or verified remotely. No deployment is performed
by this task, and no brokerage orders are automated.

## Acceptance and remaining operational decisions

Verify daily/monthly separation, no future-price influence on month-end targets,
weekend month rollover, missing symbol and failed-refresh preservation. Verify
JSON/hash and TS runtime contract, both page layouts and expiry suppression.
The real network price path must complete once locally. No need to query AI.

Owner publication to main and web deployment remain necessary to activate the
remote route/workflow. Future changes to the universe/rule require a versioned
strategy ID and fresh validation; the existing historical report does not
automatically validate a changed strategy.

## Price evidence metadata (2026-11-06)

Dashboard v1 accepts optional `price_evidence`: primary and supplemental source
names/HTTPS URLs, primary-source `missing_sessions`, and `supplemented_sessions`,
each with a session date and affected configured tickers. Python owns this
allowlisted public metadata; TypeScript validates it before rendering. Existing
v1 snapshots remain readable and display unknown provenance rather than an
inferred provider. Invalid metadata fails publication and runtime validation.
Supplemented sessions must identify a recorded primary gap and survive bar
sanitization in the input panel. Ranking and freshness rules are unchanged.

Network refreshes record Yahoo as their source and retain dates/tickers of
rejected invalid or provisional bars. Offline inputs default to “Local price
files”; use `--price-evidence <public-json>` with `--prices-dir` to preserve known
source and replacement details. Supplemental metadata documents a supplied
panel; it does not fetch replacement prices or enable an automatic fallback.
No holdings, balances or local filesystem paths enter the public metadata.

## Nine-stock universe (2026-11-06)

The owner authorized adding only GOOGL to the existing eight names. The active
configuration is now `momentum-9-12m-top3-v2`; lookback, top-three selection,
equal weighting and monthly cadence are unchanged. The page displays the
strategy ID and full universe. Existing eight-name historical allocation
experiments remain unchanged and do not validate the nine-name strategy.
`promotion_ready` remains false. The dated eight-name snapshot is retained;
the separate nine-name rerun and source evidence live under
`reports/analysis/2026-11-06-momentum-nine/`.

## Reference context and snapshot polling (2026-11-06)

See [Momentum reference context](momentum-reference-context.md) for the additive
context contract, matched SPY/equal-weight comparisons, reconstructed cycle and
rank history, and verified refresh/error behavior. Offline reproduction can pass
`--reference-prices <SPY.csv> --reference-evidence <public-evidence.json>` in
addition to the existing stock panel/evidence arguments. Missing or unusable
reference data remains unavailable without changing the candidate ranking.
