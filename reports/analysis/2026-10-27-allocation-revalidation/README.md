# Allocation reliability revalidation — 2026-10-27

[Status: Warning] Reliability remains **Unconfirmed**. Historical calculations
reproduce; evidence does not establish durable excess or promotion readiness.
This audit preserves all existing rules, source artifacts and dashboard labels.

## Reproduction and accounting

`reproduce.py` verifies eight captured price-source hashes against the frozen
October 9 protocol, reconstructs adjusted opens/closes and reruns every declared
current-vintage scenario. All five **complete reports match exactly**, including
103 monthly selections, returns, costs, intervals and drawdowns. Ten terminal
returns independently reconcile by compounding period logs. Execution ordering
is checked for every period: signal date < entry date < exit date.

The actual production implementation executes at next-common-session Open;
the monthly module's introductory prose is less precise than its function
contract. These replays use that implementation, not an assumed same-close fill.

| Per-side cost | Block months | Allocator net | Continuous hold net | 95% mean monthly paired log-excess interval |
|---|---|---|---|---|
| 20 bps | 3 | 1267.38% | 980.29% | [-0.002721, 0.008958] |
| 40 bps | 3 | 1218.62% | 975.96% | [-0.003057, 0.008672] |
| 80 bps | 3 | 1126.14% | 967.34% | [-0.003736, 0.008133] |
| 20 bps | 6 | 1267.38% | 980.29% | [-0.002247, 0.008768] |
| 20 bps | 12 | 1267.38% | 980.29% | [-0.002012, 0.008803] |

Every interval contains zero. At 20 bps, daily-close drawdown is -35.60% versus
-34.73% for hold. The temporal effective count of 103 does not establish 103
independent regimes or make the previously inspected data an unseen holdout.
Omitting the best three realized excess months from both current 20-bps series
leaves allocator +698.41% versus hold +731.71%. This artificial post-hoc
sensitivity is not a tradeable rule or a failure probability.

All six allowlisted published experiments pass source-hash and curve checks.
Monthly AI-only/hybrid arms remain untested; in the separate nine-episode
experiment they remain zero exposure. Neither supports an AI forecasting claim.

## Moomoo cost evidence

The owner requested Moomoo; this audit assumes **Moomoo Malaysia**, standard US
ordinary-share pricing. The [official tariff](https://www.moomoo.com/my/support/topic9_136?from_platform=4&lang=en-us&platform_langArea=my)
lists 0.03% commission rounded upward to cents, $0.99/order platform fee,
MYR1/started MYR1,000 stamp duty (MYR1,000 ordinary-share cap), $0.003/share
settlement capped at 1%, sell SEC 0.0000206 of value (minimum $0.01), sell
TAF $0.000195/share ($0.01–$9.79), and CAT $0.000003/share for NMS stocks.
Direct retrieval returned JS/403; the official search extraction supplied these
terms. Historical tariff effective dates remain unverified.

`moomoo_costs.py` computes these illustrative subtotals, with **synthetic $100/share,
USD/MYR 4, one order/one fill**, no commission waiver:

| Order USD | Buy subtotal bps | Sell subtotal bps |
|---|---|---|
| 100 | 127.30 | 129.30 |
| 500 | 33.10 | 33.51 |
| 1,000 | 23.20 | 23.51 |
| 5,000 | 15.28 | 15.51 |

These are arithmetic scenarios, not actual fills or all-in calibration.
SST applicability, ADR charges (relevant to the TSM universe member), FX costs,
dividend taxes, spread/slippage and actual rounding remain unresolved. Actual
order amounts are unknown. Thus 20 bps cannot be asserted to cover all Moomoo
orders, and 80 bps is not a universal small-order bound. Broker identification
resolves part of the evidence gap but cannot pass the execution-cost gate.
The existing proportional-cost backtests were not relabeled as broker simulations.

## Confirmation gaps and consumers

The initial reproduction below concerns allocator versus the eight-name hold.
The separately added VT experiment is described after this audit; its positive
intervals do not change the eight-name comparison's non-significant intervals.

| Evidence owner | Consumer | Status and remaining evidence |
|---|---|---|
| Frozen monthly reports and replay | Allocation research view | [Status: OK] Computation reproducible; excess intervals fail to exclude zero |
| Prior experiment/search history | Statistical inference | [Status: Warning] Full search correction unresolved; five replays are not five new candidate strategies |
| Broker tariff, order/fill evidence | Net-return simulation | [Status: Warning] Moomoo MY identified; actual amounts, execution and FX evidence missing |
| Corporate actions and terminal returns | Candidate and passive accounting | [Status: Warning] Same-provider adjustment consistency is not independent total-return verification |
| Universe definition | Generalization claim | [Status: Warning] Survivor-selected eight names; no broad-market reliability claim |
| Matching frozen forward protocol and seals | Promotion evaluation | [Status: Warning] No matching activated monthly cohort located in local reports/data |
| Exporter, TypeScript validator and UI | Reliability badge | [Status: Warning] Research-only contract: exporter/UI hardcode Unconfirmed, type/validator permit only promotion_ready=false |

The badge currently is not an automatic evaluation of newly supplied evidence.
A future Confirmed path needs evidence-based, fail-closed evaluation and coordinated
exporter/validator/UI acceptance tests. Removing hardcoded text alone would not
establish reliability.

The existing [v2 protocol](../../../docs/design/pipeline-forward-validation-v2.md)
requires locked-sample effective N >=30, positive net excess, lower paired interval
above zero, DSR >=0.95 with full search count, positive excess at twice calibrated
costs, drawdown within five percentage points of hold, verified returns and sealed
provenance. It concerns **30-day episodes every 35 days**, not continuous monthly
rebalancing. It cannot silently promote the monthly strategy. Its October 12
start has passed; without a contemporaneous valid seal, activation requires a
new future protocol version rather than retrospective collection. The older
October 7 single-date AI cohort is separate and cannot score before November 7
UTC, nor can one date establish independent-sample reliability.

Selection correction matters because searching strategies inflates reported
performance; the [DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
addresses multiple testing and non-normality. Replaying inspected history does
not repair that search or create prospective evidence. Newly matured observations
may eventually pass or fail; no date or amount of repeated testing guarantees
confirmation.

## Validation and reproduction

- 93 tests passed, plus four unittest subtests, across cross-sectional execution,
  statistical helpers, nine-arm portfolio/cohort guards, export and quality analysis.
- `node web/scripts/check-allocation.cjs` passed the six-experiment display contract.
- One existing Starlette/httpx deprecation warning; no test failures.
- `verification.json` records the five replays and input/implementation digests.
- `moomoo-cost-evidence.json` records fee arithmetic and unresolved assumptions.

Run from the child repo root:

```sh
.venv/bin/python reports/analysis/2026-10-27-allocation-revalidation/reproduce.py
.venv/bin/python reports/analysis/2026-10-27-allocation-revalidation/moomoo_costs.py
.venv/bin/python -m pytest tests/test_cross_sectional.py tests/test_backtest_stats.py tests/test_portfolio_pipeline.py tests/test_allocation_export.py tests/test_backtest_quality_analysis.py -q
cd web
node scripts/check-allocation.cjs
```

[Status: OK] Suitable to cite as a reproduced historical observation.
[Status: Warning] Not suitable to cite as confirmed excess-return reliability;
promotion remains blocked by failed and unavailable evidence gates.

## Follow-up completed: VT comparison, current view and candidate research

The owner approved all three follow-ups. `vt-protocol.json` freezes the same
eight-name universe, 12-month/top-three rule, 2018-01-01 through 2026-08-14
signal cutoffs, all five cost/block cases and nine captured adjusted-price
series before calculating results. `prices/` preserves those public inputs.
`compare_vt.py` reruns offline without `--fetch`. The last liquidation is
2026-09-01 Open, matching the allocator rather than the later capture date.

| Per-side cost | Allocator net | Eight-name hold net | VT continuous hold net | 95% mean monthly paired log-excess CI vs VT, block 3 |
|---|---|---|---|---|
| 20 bps | 1267.38% | 980.29% | 142.77% | [0.006949, 0.028672] |
| 40 bps | 1218.62% | 975.96% | 141.80% | [0.006635, 0.028332] |
| 80 bps | 1126.14% | 967.34% | 139.86% | [0.006039, 0.027755] |

At 20 bps, 6- and 12-month block intervals are [0.008189, 0.028373] and
[0.008716, 0.028933]. Allocator daily-close drawdown is -35.60% versus VT
-34.24%. VT is charged initial and final proportional fees only; its ETF fund
expenses are already reflected in its observed prices, with no extra invented
expense deduction. Both arms start with unit equity and zero cash yield;
there are no contributions or personal currency conversions. Every period
compounds to the VT Open-to-Open terminal return independently.

[Status: OK] Historical outperformance versus VT is reproduced and has positive
descriptive paired intervals in these declared cases. [Status: Warning] This
is still inspected-history research. The eight-name hold also beats VT by a
large amount: the survivor-selected, concentrated universe is a material part
of the comparison, and the VT gap cannot all be attributed to monthly ranking.
There is no full-search correction, fresh holdout or investor-net return pass.

### Current momentum view

`/allocation` → **Current snapshot** now shows the full eight-name price ranking,
latest common session and research weights. October 26 scores are TSM +45.40%,
V +17.28%, UNH +16.31%, NVDA +16.24%, COST +8.46%, MSFT +2.55%, AVGO -6.36%,
ORCL -54.91%. UNH/NVDA's boundary gap is only about 0.07 percentage points.

This is a daily **month-end preview**, not a sealed portfolio plan or a daily
trading instruction. Existing `current_plan` and promotion status stay unavailable
and false. The page states that one-third weights refer to a separate research
sleeve. Missing, mixed-session, malformed or expired panels cannot show current
weights. Export and page load check freshness; the client also suppresses an
expired snapshot. The four-day age boundary is conservative and is not an
exchange-calendar completeness guarantee. Current-day bars are excluded rather
than presumed complete.

From the child root, a future refresh uses the normal Layer 1 command followed
by the new offline exporter:

```sh
STORAGE_BACKEND=local .venv/bin/stock-fetch AVGO COST MSFT NVDA ORCL TSM UNH V --market US --full
.venv/bin/python scripts/refresh_allocation_snapshot.py
```

The exporter obtains its universe from the hash-verified default experiment,
pins the new public snapshot in `config/allocation_research.json`, and rebuilds
the allowlisted web export. For today's acceptance run, `--prices-dir` pointed
to this report's fresh captured `prices/`. The generated snapshot is in
`../2026-10-27-current-allocation/current-momentum.json`.

### Refreshed formal research

All three candidates ran through **In-Session Pipeline**: deterministic fresh
Layer 1; four analyst roles using canonical prompts; bull→bear→bull→bear;
moderation; research-manager adjudication; synthesis; actual `RiskChecker` via
the wealth-manager finalizer. Exact schemas validate. Analyst statements,
two-round debate, verdicts, synthesis, issuer evidence, input copies and hashes
are archived in `research/`. Current files and provenance were updated under
`data/TSM/`, `data/V/`, `data/UNH/`.

| Candidate | Final signal / score | Computed convergence | New-purchase assessment |
|---|---|---|---|
| TSM | Neutral / 0 | 0.5455 | Positive business growth, but ADR/ordinary-share/provider EPS bases are not reconciled and short-term reversal is unconfirmed |
| V | Neutral / 0 | 0.2727 | Earnings scheduled after US close October 27 are unobserved; reassess actual release and margin evidence |
| UNH | Neutral / 0 | 0.2727 | Newer official Q3 guidance supports recovery research, but canonical statements lag and margin/valuation evidence is incomplete |

The current news feeds contain no independent headlines. Recommendation
distributions are dated provider observations, not fresh rating upgrades.
Macro snapshots are null, so macro remains neutral/low despite separately
verified official context. Missing roles remain in the canonical denominator.
No entry, stop or take-profit prices were invented: actual risk code returns
null levels for all three neutral outputs. A neutral new-purchase judgment
does not instruct an existing holder to sell and does not change pure momentum
weights into an AI-veto strategy.

Examples of primary evidence are the [TSMC Q3 release](https://pr.tsmc.com/english/news/3346)
and [Visa earnings schedule](https://investor.visa.com/news/news-details/2026/Visa-to-Announce-Fiscal-Fourth-Quarter-and-Full-Year-2026-Financial-Results-on-October-27-2026/default.aspx).
Full source dates and claim boundaries are in the role evidence JSON.

All research updates are **local**. Supabase and deployed ticker pages were not
published or changed. The local Allocation preview uses its own verified export;
ticker detail links retain their independently dated data-source behavior.

### Final contract review and acceptance

[Status: OK] GO for the local research preview and archived historical evidence.
[Status: Warning] No promotion or live-order readiness is established.

| Contract | Owner → consumer | Compatibility / verification |
|---|---|---|
| Ranking math | `allocation_snapshot.py` → exporter → snapshot tab | Python sole owner; complete coverage and synthetic ranking tests |
| Public snapshot | Hash-pinned manifest → allowlisted exporter | Public market facts only; no personal holdings or target amounts |
| Web v1 payload | Python export → `allocation-types.ts` / loader / UI | Optional additive `current_momentum`; legacy exports remain valid |
| Freshness | Existing portfolio four-day boundary → Python and web guards | Mixed, stale, future and current-day cases fail closed; browser future-clock case suppresses weights |
| Candidate signals | Typed analysts → debate/verdict → finalizer | Schemas and actual risk math verified; provenance updated with current hashes |
| VT experiment | Frozen nine-price capture → fixed-rule simulator | Same dates/cost assumptions, terminal reconciliation; no new promotion claim |

No private finance paths are consumed by the new child-repo code. No account
balances, holdings, personal policy or user-specific sizing were exported.
Daily-log schemas, personal thresholds, parent wealth valuation and release
integration are outside this change's scope.

Final checks: **100 tests passed plus four subtests**, Python Ruff passed,
TypeScript typecheck passed and the expanded six-experiment web contract passed.
The dated `browser-acceptance.cjs` ran against the actual Next page in headless
Chrome: all eight rows and top-three weights, research-tab switching, desktop
and 390px mobile views, no whole-page horizontal overflow, expired-data hiding
and no page errors. Screenshots are `current-snapshot-desktop.png` and
`current-snapshot-mobile.png`. One existing Starlette/httpx deprecation warning
remains; Next also reports an outdated Browserslist database.

The browser acceptance source needs `@playwright/test` available to Node and
defaults to the installed macOS Chrome; `CHROME_EXECUTABLE` can select another
Chrome binary. It is a dated fixture, not an assertion that these tickers must
remain the top three in future snapshots. No commit or deployment was made.
