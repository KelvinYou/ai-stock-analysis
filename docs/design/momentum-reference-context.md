# Momentum reference context

[Status: OK] Owner authorized all review improvements on 2026-11-06.
Design-Lite: one Python snapshot and one web consumer with an additive context contract.

## Scope and rules

Keep momentum-9-12m-top3-v2 selection unchanged. Python computes price anchors,
1-session/1-calendar-month/3-calendar-month/12-month returns, drawdown from the
63-common-session closing high, third-place score gap, previous-session and
month-end rank changes, and up to three reconstructed month-end ranking sets.
Show the calendar month-end review window; execution stays at the next common
session open after the final completed month-end decision, never intramonth.

SPY (S&P 500 market proxy) and fixed-universe equal-weight buy-and-hold references
use the exact same common session dates as stock comparisons. They do not enter
the candidate universe or gate trades. A three-month indexed curve uses fixed
initial weights, not daily rebalancing. The current monthly basket is only
measured from its next common session adjusted open, with gross and a configured
20-bps-per-side round-trip liquidation scenario, not claimed broker fees or a
backtest. Changing the universe means the old eight-stock research cannot
validate this nine-stock reconstruction. No historical alpha claim is added.

## Owners and compatibility

Python context builder -> optional dashboard v1 context -> recursive TS runtime
validation -> display-only React. Missing references/short history remain null
or unavailable with a reason; never drop a stock or roll the reference to a
different date. Old v1 snapshots remain readable with explicit unavailable
context. Public inputs contain only market data. No holdings enter the child.

Refresh CLI fetches/sanitizes SPY separately and records its evidence separately.
Offline runs accept an optional reference panel and matching public provenance.
GET /api/momentum calls the existing verified loader and returns a no-store
response; the client fetches every 60 seconds and on request, validates payloads,
and replaces snapshots without allowing an older response to overwrite newer
state. Failure preserves the last snapshot plus an error; existing expiry gates
still hide old targets. Unmount aborts in-flight requests. This refreshes published
snapshots, not market downloads. The server source cache remains up to 60 seconds.

## UI and failures

Order: compact freshness summary and monthly basket; ranking and recent context;
market references and cycle comparison; rank history; collapsed source details.
Reuse SectionCard, Button, host tokens and Recharts. No new palette or assets.
At narrow widths tables scroll inside labelled regions; page width stays bounded.
Source gaps distinguish excluded rows from included supplementary replacements.

| Failure | Result |
|---|---|
| SPY missing, malformed or unsynchronized | Reference unavailable; stock ranks remain |
| Not enough anchor history | Affected horizon null, with dates visible |
| No next-session open yet | Cycle performance unavailable |
| Legacy snapshot | Context unavailable; existing basket remains readable |
| Invalid metadata/context/hash | Loader fails closed |
| Refresh HTTP failure or invalid payload | Visible error; last verified snapshot retains expiry |

## Implementation and acceptance

1. Context arithmetic and CLI reference input, synthetic independent-value tests.
2. Recursive TS validator, no-store route and refreshed UI; contract corruption tests.
3. Regenerate with captured nine-stock panel plus SPY; test real-browser update,
   error recovery and old-response handling; inspect 320/390/1440 light/dark.
4. Focused Python tests, child web contract/typecheck, parent design-check/test.

## Open questions

None blocking. The 20-bps scenario is illustrative and configurable, not a
substitute for actual broker fees. Offline supplemental data remains explicit;
this feature does not introduce an automatic secondary-price-provider service.

## Acceptance — 2026-11-06

Implemented and verified locally; no commit, push or deployment. Python owns
all calculations; React only formats values. Matched SPY data and its separate
provenance are captured alongside the nine-stock inputs. The no-store snapshot
route and client polling retain hash/runtime validation, prevent capture-clock
and price-session regression, preserve valid data on failure, and retain expiry
suppression. Existing v1 snapshots without context still load explicitly.

Focused Python tests (25), Ruff, child typecheck/runtime corruption checks,
parent make design-check and make test passed. Real Chrome verified 320/390/1440
light/dark, bounded page width, early basket placement, source disclosure,
keyboard disclosure and refresh touch target. Mocked-response browser checks
verified new data replacement, HTTP failure, invalid data, older response,
60-second recovery and expiry on failure. Chart and settled mobile top were
visually inspected. Parent design gate retains two pre-existing chart contrast
warnings. Production publishing and actual broker fees remain unverified.

SPY reference definition: https://www.ssga.com/us/en/institutional/etfs/state-street-spdr-sp-500-etf-trust-spy
Calendar context: https://www.nyse.com/trade/hours-calendars
The UI deliberately labels a calendar month-end review window, rather than
claiming an unverified future exchange execution date.

## Completed-session freshness and ETF comparisons (2026-11-06)

Owner requested VOO, VT and long-hold lines and raised concern that a recently
checked snapshot could still contain old prices. The refresh producer now embeds
an XNYS calendar projection (exchange_calendars >=4.11,<5; UTC closes; holidays,
DST and early closes) and explicit stock/reference session coverage. Runtime
compares the clock to those supplied closes. Complete dates matching the latest
scheduled completed session receive the latest label; missing reference evidence
is partial; lagging stock prices, unknown/expired calendar coverage or a missing
month rollover hide current targets. Old v1 snapshots still parse, but without
calendar coverage current target freshness is unverified. Source-date matching
verifies completed-session coverage, not exchange-authenticated quote accuracy.
Unscheduled exchange closures and provider corrections require refreshed evidence.

The CLI refuses to replace the published snapshot when the stock panel misses
the latest completed session, even if its capture timestamp is new. The normal
network download still excludes the current UTC date and runs at 09:15 MYT; the
UI therefore reports delay after a new US close until that session is published.
Web polling checks existing published snapshots and does not initiate market
price downloads. The calendar projection has finite coverage and fails closed
outside it. Python owns the schedule; TS compares timestamps without duplicating
holiday or DST rules. Workflow dependencies include the calendar library.

VOO and VT are comparison-only config entries, outside the nine-name universe.
They use precisely the same price anchors, sessions, USD adjusted prices and
cycle fee scenario as SPY. Missing references are explicit rather than backfilled
with an older date. Long hold is the fixed nine-stock equal-initial-weight
buy-and-hold reference, with no interim rebalance. The three-month comparison is
indexed to 100 and has accessible per-line visibility buttons; it is not the
nine-stock momentum strategy's historical backtest. Separate VOO/VT source
metadata and raw downloads are captured under the dated latest-run directory.

Verification adds frozen calendar tests around US close, weekend, Thanksgiving,
early close and DST; older-data/new-capture regression; missing comparison tests;
and real-browser close-boundary suppression. Freshly downloaded public prices
for all 12 symbols cover 2026-11-05 without supplemental rows.

## Momentum strategy line (2026-11-06)

Owner requested the Momentum strategy in the same chart as SPY/VOO/VT/Long hold.
Python now reconstructs every historical month-end top-three basket using only
prices through that decision date, executes at the next common-session adjusted
open, and carries drifting weights until the next scheduled rebalance. It marks
to every common daily close, including days after the final rebalance. The
three-month chart is normalized at the same closing anchor as all references;
all five curves are gross before transaction fees, tax and FX. This is not a
current-winners backfill, an account-return chart, or validated alpha.

The single valuation owner is the AI-independent `daily_portfolio.py`, extracted
from the existing cross-sectional engine. The old private backtest entry point
and turnover helper remain compatible aliases/wrappers with unchanged default
end semantics and numerical rules. Only the dashboard requests valuation through
an explicit latest end date. This leaf module prevents the scheduled price-only
workflow from importing the backtest package's AI/SDK runtime. A blocked-import
subprocess verifies that boundary. No strategy search, significance metric,
selection threshold or promotion flag is changed.

The network download window is 18 months: a three-month plot needs twelve-month
warm-up plus the preceding month-end decision. Missing warm-up, opens or monthly
decisions produces an explicit unavailable curve. TS recursively validates the
optional v1 `momentum_curve`; React only joins dated values. Momentum is the
first, thicker line with its own visibility control and an expandable audit of
decision date, execution date and selected names. Existing context without this
field remains readable.

[Status: OK] Point-in-time selection, next-open execution, future-data invariance,
post-rebalance valuation and existing backtest compatibility pass focused tests.
[Status: Warning] Gross descriptive reconstruction under a fixed current universe;
no cost-adjusted edge or promotion readiness is established by this chart.
