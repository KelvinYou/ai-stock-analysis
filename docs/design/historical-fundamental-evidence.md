# Historical fundamental evidence and pipeline flow

**Status:** Implemented; validation recorded below. **Updated:** 2026-10-08.

## Context and scope

The frozen historical pilot has 41 missing statements, 44 neutral fundamental
judgments with single-period financials and no historical valuation, and 11
ORCL sell judgments. Improving input fidelity is necessary before measuring
fundamental purchase selection. Previously inspected outcomes are not a tuning
target. Existing forecasts, prospective cohorts and production signal thresholds
remain immutable for this change.

This Design-Lite changes the data schema, SEC replay builder, historical loader,
session packets, fundamental tools and the two consumers of `pipeline.json`.
No new remote service, paid provider, trade allocator or forecast policy is added.
The existing official SEC adapter is retained; the official APIs already expose
filing history and CompanyFacts, including units and period clocks:
[SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

## Proposed flow

```text
SEC facts [MODIFIED: preserve periods, durations, units and filing vintages]
  -> replay history loader [MODIFIED: per-period revision selection at cutoff]
  -> TickerData [MODIFIED: history + dated valuation price]
  -> fundamental evidence context [NEW: readiness, TTM and comparison checks]
  -> FundamentalsAgent [MODIFIED: provide history and evidence gaps]
  -> existing debate -> synthesis -> existing risk checks -> Briefing
```

The Python evidence context owns derived fundamentals; the model interprets
observations without inventing missing valuation or growth. History defaults to
an empty list; old single-statement artifacts continue to load. New packets carry
an additive readiness object separate from the existing availability boolean.
No old packet is migrated or rewritten.

## Rules and failure behavior

| Input state | Result |
| --- | --- |
| Future period, future filing or missing historical filing clock | Excluded from history |
| Multiple vintages of one start/end period | Latest known revision at cutoff; conflicting same-clock values rejected |
| Same end date, quarterly and YTD facts | Separate periods; never mix durations when deriving margins/FCF |
| More than one currency | Follow declared primary-statement currency; never combine currencies |
| Same-period income/balance fields | Retained; source tags/units preserved by SEC builder |
| No trusted share adjustment basis | EPS/shares may be displayed, valuation stays unavailable |
| Four non-overlapping contiguous quarters with matching EPS currency and share basis | Sum diluted EPS for TTM; never annualize a single quarter |
| Dated valuation price and EPS/share basis match | P/E or market cap can be derived; no reuse of auto-adjusted technical bars |
| Missing valuation, growth, shares or stale period | Separate gap/age diagnostics; no forced directional signal |

Valuation replay prices require positive finite price, currency, source, an
observed date, an availability date and a declared share basis. They must match
the last historical price-bar date. A matching basis is a provider declaration,
not independently authenticated corporate-action proof. SEC data alone does not
establish that basis; the builder must not manufacture one.

Issuer-quoted ADR EPS can declare `diluted_eps_currency` separately from the
statement's reporting `currency`. It is never inferred through FX conversion.
TTM EPS requires four matching EPS currencies and share bases; price/EPS currency
must still match directly. For example, TSMC's issuer-quoted USD per ADR amount
can support a USD ADR P/E while TWD revenue/profit remain within their reporting
currency. The default is the statement currency, preserving legacy replay behavior.
Explicit overrides expose `valuation.eps_currency`; no override changes the shape
of previously sealed fundamental contexts.

The issuer backfill is a separate evidence build under
`reports/analysis/2026-10-08-evidence-backfill/`. Its `session-enriched/` packets use
the frozen historical pilot's pre-cutoff technical observations with newly
source-linked financial history and dated valuation prices. Existing forecasts
are not reused as predictions for the enriched inputs. Selected issuer releases
are an event subset, not full independently archived sentiment coverage.

## Contract map and compatibility

| Owner | Consumers | Compatibility and tests |
| --- | --- | --- |
| `models/market_data.py` | replay, fetchers, stores, agents | Additive optional statement fields and empty history defaults; storage roundtrip |
| `backtest/replay_builder.py` | replay JSONL | Duration/currency/filing-aware records; existing source format remains readable |
| `backtest/replay.py` | session preparation | New per-period history loader; existing latest-snapshot function retained |
| `data/fundamentals.py` | analyst tools, session packet diagnostics | One deterministic calculation owner; leakage and basis mismatch tests |
| `pipeline.json` | SVG UI, generated Mermaid | Explicit canonical edges; renderer validation, generator check and UI typecheck |

The live fetcher's current financial snapshots remain valid. Historical
information must pass stronger clocks at the consuming evidence boundary. No
private financial holdings or personal thresholds are read or copied.

## Optimization loop and acceptance

1. Add history and valuation models; reproduce future-revision and basis hazards
   in synthetic tests; implement the evidence context and validate it.
2. Preserve SEC periods and exact-duration fields, connect replay/session/tools,
   then validate loader/tool/storage compatibility and the existing scored pilot.
3. Fix the graph's memory and risk dependencies through canonical explicit
   edges, regenerate Mermaid, validate layout and inspect the actual server-rendered SVG (browser unavailable).
4. Review actual changed contracts and lookahead/cost/statistical invariants;
   fix concrete failures, rerun only affected checks, then run full repository
   tests once after integration.

Completion means code, contracts and flow agree and checks pass. It does not mean
the revised pipeline has beaten long hold. New enriched experiments require a
new directory/protocol and new sealed predictions; missing external inputs are
reported as missing rather than filled from current-only snapshots.

## Trade-offs and remaining decisions

Automatic valuation from existing auto-adjusted OHLC would be simpler, but those
bars do not establish an EPS-compatible corporate-action basis. An explicit dated
valuation-price replay is therefore required. Keeping all fiscal durations costs
more records than a latest-only snapshot but avoids conflating quarter/YTD/annual.

Remaining external decisions: which source can provide verified historical share
bases and original-vintage coverage for every frozen universe member? Defaults:
retain unavailable valuation and research-only status until that authority exists.


## Implementation validation

All four bounded engineering loops are complete. Full Python validation passed
318 tests and 4 subtests; lint, additive OpenAPI/Postman snapshots, architecture
parity, web typecheck, actual SVG layout/render checks and offline web build pass.
Frozen pilot input hashes and the 31 prospective forecasts remain valid. Browser
interaction was unavailable; the actual server-rendered SVG was visually inspected.
Details and limitations are recorded in
[the implementation review](../../reports/analysis/2026-10-08-fundamental-upgrade/README.md).
This is an engineering acceptance result; provider evidence and profitability
acceptance remain pending.
