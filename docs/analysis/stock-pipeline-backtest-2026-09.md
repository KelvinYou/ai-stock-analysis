# Stock pipeline OOS backtest — 2026-09-22

> **[Status: Warning]** The point estimates are exploratory and the old effective-sample, p-value, and DSR metrics are superseded for promotion: they grouped overlapping windows by ticker but did not cluster same-date securities. Re-score with `portfolio_overlap_clustered_v1` before citing inference. The current signal has no demonstrated trading edge and must not be treated as a trade recommendation.
>
> Re-verify after **2026-12-22**, or earlier if the price/news/fundamentals source changes.

## Decision

The original scored run is not failing because it called `hold` before META's sharp move. META is an event-driven miss: that scored packet had no historical news feed and no macro feed, while its deterministic technical state was not actionable. The later price move was therefore not available evidence at the decision date.

The result is a known coverage limitation, not evidence that the pipeline can capture event catalysts. Adding current Yahoo news to a historical packet would create lookahead bias, so the scorer now abstains instead.

## OOS result

Original sealed score, run in the current Codex session with no Claude model calls:

- 11 US large-cap tickers × 8 as-of dates = **88 trials**.
- **88/88 completed, 0 errors**; 30-calendar-day horizon; 10 bps per side.
- Point-in-time fundamentals were available for **47/88** packets. The remaining 41 were excluded from fundamental evidence because no usable SEC filing date/data match was available.
- Evidence coverage was **technical 88/88**, **fundamentals 47/88**, **sentiment 0/88**, and **macro 0/88**; missing evidence is reported separately instead of being scored as a bearish view.
- Directional trials: **6**; hit rate **33.33%**; 95% Wilson interval **9.68%–70.00%**; effective n **6.0**.
- Direction-adjusted active mean: **−7.44%**. All-trial net mean after costs: **−0.52%**, p **0.761**.
- Overall portfolio simulation: **−0.96%** from $10,000 across 3 trades; strict equal-weight long hold **+9.06%**; excess return **−10.03 percentage points**. The legacy rolling-long diagnostic was **+7.45%**.
- The best non-benchmark strategy was fundamentals at **+2.76%**, still **−6.30 percentage points** behind strict long hold. The strict benchmark itself had the highest per-trade Sharpe, with a deflated-Sharpe probability of only **60.29%** after counting seven searched rows.
- The explicit benchmark promotion gate is **FAIL**: no pipeline strategy beat strict long hold, and the sample is far below the effective-n threshold for promotion.

Conclusion: the AI signal is not validated. A separate allocation layer can
improve the return path, but it must not be described as evidence that the AI
analysts forecast returns.

## External validation status

A new evidence-complete, unscored session was prepared from public SEC EDGAR,
SEC XBRL CompanyFacts, FRED DFF, and point-in-time price inputs. It is a new
input bundle, not a replacement for the original scored result:

- **88/88** packets have technical bars, SEC CompanyFacts fundamentals, dated
  SEC event evidence, and a dated FRED macro snapshot.
- Current sector/industry metadata is omitted in historical mode unless a
  versioned source is supplied; this gate passes by failing closed.
- The hard validator returns **BLOCKED**, not PASS. Historical SEC filings are
  event evidence rather than the production provider's complete news feed;
  no real provider run is authenticated; the universe and execution costs are
  not externally calibrated. At this pre-scoring check, no prediction set
  existed; the 2026-09-23 addendum below supersedes only that last point.

Run the gate with:

```text
.venv/bin/stock-analysis-backtest \
  --mode external-validate \
  --session-dir /private/tmp/stock-session-replay.secfacts2
```

The bundle is intentionally disposable under `/private/tmp`; its manifest
records the public source URLs and limitations. A BLOCKED gate cannot be
turned into a PASS by changing the scoring threshold.

## Allocation-layer candidate

> **[Status: Warning]** The deterministic allocation candidate beats the strict
> long benchmark in the measured slices, but its final slice is too short to
> promote as a validated strategy.

The new `cross-sectional` mode freezes an 11-stock universe and, at each
month-end, ranks the previous 12 months of returns, holds the equal-weight top
three for the next month, and charges 10 bps per side plus turnover costs. It
uses no analyst output.

| Slice | Allocation | Strict long hold | Excess |
|---|---:|---:|---:|
| Train 2019–2023 | +565.28% | +382.35% | +182.93pp |
| Validation 2024–2025 | +143.55% | +93.59% | +49.97pp |
| Final 2026 YTD | +13.82% | +11.23% | +2.59pp |

The final slice has only seven monthly periods and a net-return p-value of
**0.613**. The allocation layer is therefore a reproducible candidate, not a
claim of durable alpha. On the original sealed 30-day windows it produced
**+15.94%** versus the strict benchmark's **+9.06%**, but that comparison still
has only eight overlapping decision dates. I also inspected a small candidate
grid before freezing this rule; that makes the allocation result exploratory
until it survives a future untouched holdout.

The unified `session-score` output now includes this allocator as a separate
section and JSON field. A fresh rescore of the same 88 sealed trials reproduced
**+15.94%** net for the allocator versus **+9.06%** strict long hold (**+6.88pp**)
with 10 bps/side costs; overlap-adjusted effective period n is **3.0** and
net-return p-value is **0.743**. The AI signal rows and their promotion gate remain
unchanged; this is an allocation-layer win, not a repaired claim that the AI
analysts forecast returns.

## META event windows

Both event windows stayed neutral under the same evidence contract:

| As-of | Horizon | Realized move | Pipeline result |
|---|---:|---:|---|
| 2026-09-08 | 5 days | +8.50% | neutral; no trade |
| 2026-09-07 | 10 days | +11.22% | neutral; no trade |

This is not a positive or negative performance observation by itself: a neutral portfolio has no directional forecast to score. It does establish that the scorer did not backfill the news catalyst from the later outcome.

## Contract changes

- Replaced the fixed 45-day fiscal-period proxy with a filing-date gate derived from yfinance SEC filing metadata. An unmatched or empty statement is unavailable to the backtest.
- Added financial provenance fields (`fiscal_period_end`, `available_as_of`, `availability_source`).
- Excluded yfinance's latest-only news endpoint from historical sentiment evidence.
- Added fundamentals evidence guarding, provider-neutral `in-session` labeling, and session manifest version 3. Existing v2 bundles remain readable and are rescored under the current deterministic contract.
- Excluded unavailable analysts from the evidence-backed consensus denominator instead of treating missing data as a neutral view.
- Made `buy_and_hold` a strict equal-weight one-position-per-ticker benchmark from first entry to last exit; retained the former rolling-entry behavior as `rolling_long`.
- Added explicit strategy-vs-benchmark excess returns and a promotion gate requiring a benchmark win, effective n ≥ 30, and deflated Sharpe ≥ 95%.
- Renamed the scorer's displayed all-trial mean so it is not mistaken for a portfolio-level long-hold return; the historical field name remains compatible.
- Added a separate `cross-sectional` CLI research mode with a fixed-universe monthly ranking rule; its output explicitly says it is not AI forecast evidence.
- Added a sealed-trial cross-sectional adapter to `session-score`; it ranks only point-in-time prices, consumes forward outcomes only after selection, and writes an additive `cross_sectional_trial_allocation` result without changing the AI score or benchmark gate.
- Kept recalibrated conviction as an attribution score; it does not create a trade after the actionability gate fails.
- Added shared OHLC hygiene to `BacktestFetcher`, so non-finite historical bars cannot silently poison rolling indicators.
- Made analyst attribution deterministic from typed reports; cached cloud/local briefings are migrated narrowly without rewriting the thesis. A directional synthesis that fails the deterministic actionability gate is rendered as neutral instead of `BUY` with zero conviction.
- Made fundamentals fail closed when no usable financial evidence exists, and tightened the prompt to prohibit invented valuation or sector figures.
- Added a source-neutral replay contract for dated news and macro snapshots: news requires `published_at` plus `available_as_of`, macro requires `as_of_date` plus `available_as_of`, and `session-prepare --replay-dir` refuses future records. The current sealed result remains unchanged because no replay dataset was supplied.
- Added a reproducible public replay builder for SEC filing events, SEC XBRL CompanyFacts fundamentals, and FRED DFF; the new 88-trial packet set reaches 100% coverage for technical, fundamentals, dated events, and macro evidence without using current-only news.
- Added a hard `external-validate` gate for packet clocks, metadata, provider identity/run pairing, historical news source quality, survivorship-safe universe, calibrated execution costs, effective sample size, and strict long-hold promotion.
- Historical `BacktestFetcher` metadata now omits unversioned sector/industry labels instead of importing current provider classifications.
- Restored the complete typed analyst reports at every downstream LLM boundary: debate, research-manager, and synthesis now receive risks/strengths, headline details, technical levels, and macro/FX fields instead of summaries only.
- Added a deterministic point-in-time evidence envelope to downstream prompts, shared the macro availability predicate with the replay/agent path, and added descriptive trading-bar momentum, observed levels, and volatility to the technical tool.
- Tightened analyst prompts so single-period fundamentals cannot be described as trends, missing social/news/macro evidence cannot be filled from model memory, and repeated debate claims cannot masquerade as new evidence.
- Added runtime canonicalization after model output: RSI is replaced by the deterministic indicator, support/resistance values outside observed OHLC bounds are dropped, and observed technical highs/lows use bar highs/lows rather than closes.
- Added runtime source gates for future/invalid financial statements, undated historical analyst recommendations, social sentiment without a social source, and macro fields whose corresponding dated source is absent; weak fundamental evidence now caps confidence at low.

## Limitations

- The new SEC CompanyFacts replay is point-in-time by filed date and excludes later restatements until their filed date; the original scored result still used the older yfinance filing adapter.
- SEC filing events are not a complete historical provider news feed, and FRED replay currently covers DFF only; the external validator therefore keeps the news gate blocked.
- The fixed current ticker universe has survivorship bias.
- The prepared bundle has no real model-provider predictions. The current shell has no Anthropic API key and Claude CLI is not authenticated, so production-provider behavior cannot be validated in this environment.
- Execution costs remain assumptions until a broker/quote calibration artifact is supplied; the prepared sample has no scored effective n and cannot establish a strict long-hold win.

## Updated accounting rerun — 2026-09-23

> **[Status: Warning]** This is a development rerun of the frozen 12-month/top-three allocator, not a new AI-pipeline run and not a promotion result. It uses the same 11 current US tickers and 10 bps/side assumption, with next-session-open fills, matched passive comparisons, and daily-close drawdown marks.

| Signal-date slice | Periods / effective n | Allocator net | Strict hold net | Matched passive net | Allocator max DD | Strict hold max DD | 95% paired log-excess CI vs. strict / matched passive |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019–2023 | 60 / 60 | +689.14% | +397.46% | +364.71% | −40.96% | −50.24% | [−0.0049, +0.0185] / [−0.0057, +0.0226] |
| 2024–2025 | 24 / 24 | +161.50% | +91.35% | +87.10% | −41.54% | −27.73% | [−0.0048, +0.0223] / [−0.0067, +0.0249] |
| 2026 YTD signal dates through July | 7 / 7 | +14.32% | +10.78% | +12.17% | −15.25% | −13.42% | [−0.0151, +0.0340] / [−0.0184, +0.0343] |

The point estimates remain positive, but every paired interval includes zero. Validation drawdown is 13.81 percentage points worse than strict hold, exceeding the proposed 5-point budget. The 2026 slice has only seven periods and a net-return p-value of 0.584. Its July 31 signal's holding window exits on September 1, so the reported return includes prices after the signal-date cutoff. The price basis is not yet independently verified for dividend/total-return consistency; the current ticker set is still survivorship-biased. These observations fail the promotion standard and do not show that the AI forecast layer adds value.

Per-slice outputs were written to `/private/tmp/cross-sectional-next-open-*-20260923.{json,md}`. No model call was made. The run is reproducible with the frozen CLI configuration; the cached historical universe and cost assumption remain development inputs, not externally validated facts.

## Verification

- `.venv/bin/python -m pytest -q`: **234 passed**, 1 existing dependency warning (2026-09-23).
- `.venv/bin/ruff check src/stock_analysis/backtest tests`: passed (2026-09-23).
- Root `make test`: **299 passed**, 6 skipped.
- No commit was made; pre-existing dirty `data/**` state was preserved.

The implementation owner is `src/stock_analysis/backtest/`; this note is the durable summary, while the generated per-ticker JSON remains disposable run output.

## AI attribution ablation implementation — 2026-09-23

`session-score` now emits two separate, non-promoted diagnostics: AI-only
long-only selection and an AI-positive filter over the fixed momentum basket.
Unused `1 / top_n` sleeves remain in cash. Each arm is compared with a
same-window, exposure-matched reference and reports paired block-bootstrap
uncertainty. A conditional randomization test shuffles AI-positive labels only
within each period's momentum basket, preserving the basket and number of
positive labels; its one-sided p-value asks whether the observed labels pick
better names than random labels at the same exposure. The two diagnostic arms
are counted in each output; runs/configurations inspected across separate
invocations must also be counted in any later selection-bias correction.
Its drawdown is based on sealed-window endpoints, not daily marks.

No new empirical AI-alpha number is claimed here. The locally available cached
score artifact predates next-session-open execution (`entry_date` is absent),
so it is not silently reinterpreted under the corrected timing contract. The
new synthetic tests validate sleeve accounting, costs, exposure matching, and
permutation reproducibility; a fresh provider-backed rerun remains blocked by
the existing data/provenance gates.

## In-session pipeline score — 2026-09-23

> **[Status: Warning]** This is an exploratory in-session reconstruction on a
> previously inspected historical development sample, not a blind OOS test or
> production-provider replay. Its aggregate performance cannot support
> promotion.

The existing 88-packet bundle was scored without an Anthropic API call. Codex's
current GPT-5 session selected a fixed point-in-time rubric, then a local
deterministic script applied it consistently to every packet; this is not a
replay of the production four-agent LLM chain. Predictions were created before
opening trial-level outcomes, but the prior aggregate result had already been
seen, so the sample is contaminated for confirmation. The bundle covers eight
dates and AAPL, AMZN, AVGO, GOOGL, META, MSFT, NVDA, TSLA, TSM, UNH, and V; that
roster differs from frozen prospective protocol v1.

- Fundamentals signal buy only when filing data was no more than 180 days old,
  net income and free cash flow were positive, and net margin was at least 10%;
  otherwise abstain. This does not test valuation.
- Technical signal buy required price above SMA-50 and SMA-200, 20-bar return
  at least +2%, and positive 60-bar return. Sell required price below both
  averages and 20-/60-bar returns at or below −5%. Other cases were neutral.
- Sentiment abstained because the replay contains SEC events, not a complete
  historical provider news feed. Macro abstained because the replay supplies
  FRED DFF only. The normal scorer recalibrated conviction/actionability.
- Portfolio configuration was 10% of current cash per position, long-only,
  with 10 bps per side. Entries use the next session open; exits use the
  configured 30-calendar-day horizon.

| Metric | In-session `overall` | Strict equal-weight hold |
|---|---:|---:|
| Return | −2.24% | +8.04% |
| Excess vs. strict hold | −10.28 pp | — |
| Maximum drawdown | −6.39% | −15.52% |
| Trades / effective n | 23 / 6.0 | 11 / 1.0 |

The directional hit rate was 46.15% (95% Wilson interval 28.76%–64.54%); the
all-trial mean net return was −0.49% (p=0.890). The paired 95% block-bootstrap
log-excess interval versus strict hold was [−0.0029, +0.0009]. Lower drawdown
did not compensate for losing 10.28 percentage points to passive hold. The
external validator returned **FAIL**: effective n is below 30, the pipeline
did not beat strict hold, and the paired interval's lower bound is below zero;
historical news, production-provider identity, survivorship-safe universe,
terminal-return provenance, and calibrated costs remain blocked.

The same trade ledger implies mean committed principal of **22.94%** of starting
capital and a peak of **52.73%** across **165 market sessions**; the pipeline had
positions on 145/165 sessions (87.88%). Strict hold remained fully invested at
100%. These figures use original trade stakes, not marked-to-market exposure.
The same-active-window, same-dollar-stake passive comparator returned −1.00%,
so the pipeline also lagged that control by **1.24pp**. The raw strict-hold gap
therefore mixes under-allocation/timing with negative selection; increasing
position size alone is not supported while the matched-exposure edge is
negative.

The conditional AI-signal ablation was **not run**: its prerequisite sealed-trial
allocator rejected these monthly 30-day windows as overlapping. The earlier
score artifact did not surface this dependency failure; the CLI now records it
explicitly. No conclusion about AI's incremental value over the momentum basket
can be drawn from this sample.

## Same-day sizing correction and rerun — 2026-09-23

> **[Status: Critical]** This supersedes the preceding in-session portfolio
> return figures, not its research-only status. The 88 predictions and sample
> were unchanged. The implementation now reserves equal stakes from one
> pre-session cash snapshot for simultaneous entries; reversing all trial rows
> leaves the complete portfolio report unchanged. The prior simulator used
> remaining cash in ticker order, so its result was order-dependent.

| Metric | Corrected `overall` | Strict equal-weight hold |
|---|---:|---:|
| Return after assumed 10 bps/side | −1.40% | +8.04% |
| Excess versus strict hold | −9.44 pp | — |
| Excess versus same-stake matched passive | −0.47 pp | — |
| Mean / peak committed principal | 27.99% / 71.46% | 100% / 100% |
| Trades / portfolio effective n | 23 / 6.0 | 11 / 1.0 |

The scorer still reports a 46.15% directional hit rate with a 95% Wilson
interval of 28.76%–64.54%, and the paired 95% log-excess interval versus
strict hold remains negative at its lower bound (about −0.0029 to +0.0010).
The corrected pipeline remains below both strict hold and matched passive.
`fundamentals` alone returned +6.60% but also lost to strict hold; selecting
it now would be a post-hoc strategy search, not a confirmed improvement.
The frozen v1 prospective protocol is superseded before collection because
same-day sizing changed and its schedule conflicts with non-overlapping
AI/allocator ablation. The source-coverage report now labels historical
replay and FRED DFF as input presence, not complete news/macro evidence.
Self-declared provider metadata no longer passes the production-provider gate.

Verification: 253 child-repository tests passed; reversing the 88 trial rows
produced an identical portfolio report; the external validator remained
**FAIL** (effective n 6.0, benchmark loss, non-positive paired lower bound)
with provider, licensed universe/terminal returns, complete news, and calibrated
costs blocked. Its new scored-panel gate passed 88/88 complete outcomes and
fails when a manifest trial is omitted, duplicated, or errored. Repeating
`session-score` also exposed tiny revisions in
yfinance's adjusted prices (maximum per-trial realized-return change about
2.5×10⁻⁷). The `rescore` mode was added to hold the original result and all
price paths fixed while recomputing the corrected portfolio. Its input/result
objects were identical after JSON loading. The exact-input rescore is
`/private/tmp/stock-session-replay.secfacts2/sealed-rescore.json`; the separate
source-aware fresh-price run is `fixed-score-v2.json` in that directory. Both
are exploratory local artifacts, not durable confirmation datasets.

The bundle and results remain disposable under `/private/tmp/stock-session-replay.secfacts2/`:
`predictions.json`, `session_provenance.json`, `session-score.md`,
`session-score.json`, and `backtest_experiments.jsonl`. `session_provenance.json`
records the in-session model, rubric hashes, prior aggregate exposure, and
research-only limitations. No `provider_run.json` was created.

## Non-overlapping attribution diagnostic — 2026-09-23

> **[Status: Warning]** This is a new development-only evaluation on six
> mechanically selected, non-overlapping dates (66/88 trials). The earliest
> feasible window is retained using entry/exit dates only; returns and signals
> do not choose dates. The full 88-trial primary pipeline and long-hold scores
> remain unchanged. This subset cannot be used as an out-of-sample promotion
> result, and it evaluates the in-session reconstructed rubric rather than the
> production four-agent model.

| Six-window diagnostic | Net compound return | Comparison |
|---|---:|---:|
| Price-only 12-month/top-three allocator | +7.73% | strict hold +8.02%; matched passive +7.87% |
| In-session signal-only long | −13.99% | same-exposure reference −5.72% |
| In-session signal-filtered momentum | −8.49% | same-exposure momentum −5.99% |

The AI-label permutation test was informative on only 3/6 windows, with a
one-sided p-value of 0.705. The hybrid's paired 95% log-excess interval against
its same-exposure reference was [−0.0108, −0.0009]. These diagnostics point
against using this reconstructed signal to filter the momentum basket. They
do not prove the production AI pipeline lacks value. The scored artifact and
append-only ledger row are under
`/private/tmp/stock-session-replay.secfacts2/nonoverlap-diagnostic.*` and
`fixed-ledger.jsonl`; the row counts all 11 scored arms and labels the subset
`research_only`. No candidate was promoted.

## Fixed allocator transfer and concentration checks — 2026-09-23

> **[Status: Warning]** These are additional historical diagnostics of the
> already selected price-only 12-month/top-three rule on the current 11-name
> panel. They are not a clean holdout: both the universe and rule had been
> chosen after examining other periods. They do not change the 88-trial AI
> pipeline result above or provide evidence that the AI layer beats long hold.

With 10 bps per side, the fixed allocator lost on the previously unreported
2017–2018 transfer interval (16 monthly periods): **+13.66% versus strict
hold +17.11%**, or −3.45 percentage points. On the combined September 2017
through July 2026 signal-date range (107 monthly periods), it had a large
historical point-estimate lead: **+2594.79% versus strict hold +1121.28%**.
These compounded figures span nearly nine years; they are not annual returns.
The pre-specified three-period moving-block 95% interval for paired monthly
log excess was [−0.000097, +0.016608], still including zero. Repeating at
twice the assumed cost (20 bps per side) gave +2536.80% versus +1118.84%,
but its paired interval [−0.0003, +0.0164] also included zero. Neither cost
is externally calibrated, and the price series is not dividend/total-return
verified.

The selection frequency was concentrated: NVDA appeared in 68/107 baskets,
AVGO in 59/107, and TSLA in 39/107. A fixed-rule leave-one-ticker-out check
over the full range remained positive in all 11 omissions, but the compounded
excess over each reduced universe's own strict hold fell from +1473.51 pp
with all names to +417.47 pp without NVDA, +473.03 pp without TSLA, and
+674.05 pp without META. Those comparisons have different benchmark universes
and are not eleven independent confirmations. The current-name-only panel
has survivorship bias, so this check does not make the result market-wide or
promotable. Year-level returns also show the allocator losing to strict hold
in 2018 and 2019. A genuinely untouched forward sample, point-in-time
membership and total returns, calibrated costs, and an authenticated provider
would be needed for the complete AI-pipeline claim.

Local artifacts: `allocator-2017-2018.json`, `allocator-full-2017-2026.json`,
and `allocator-full-20bps.json` under
`/private/tmp/stock-session-replay.secfacts2/`. The leave-one-ticker-out
diagnostic was a temporary fixed-rule run, not a new strategy selection.

## Pipeline integrity repair and fixed-input rerun — 2026-09-23

> **[Status: Critical]** The current in-session AI `overall` rule still does
> not beat strict long hold. These repairs close identified leakage and
> reproducibility paths; they do not improve the measured forecast edge or
> validate the production four-agent provider.

Red/green tests found that historical packets could include a future company
name/currency from current `stock.info`; a manifest could omit a declared
ticker/date trial; extra predictions could be ignored; packet identity and
future-bar checks occurred too late; and malformed or escaping packet paths
could crash or bypass parts of external validation. Historical metadata now
uses only the requested ticker and market-default currency. Session scoring
requires the complete declared grid and preflights every packet before fetching
forward prices. The external validator applies the same grid contract and
fails closed on malformed JSON, dates, and out-of-bundle paths.

The prior `rescore` also reread mutable allocator price histories. In a
fixed-trial repeat, its allocator `data_end` changed from 2026-09-17 to
2026-09-11; selection and return happened to be unchanged, but future price
revisions could have changed them. New score artifacts embed the ranking
history capped at the last decision date and record its SHA-256 fingerprint.
`rescore` uses that frozen panel. Legacy score artifacts lacking it mark
allocator/ablation unavailable rather than silently rereading prices.

The fresh local `session-score` on the same 88 in-session predictions returned
**−1.3972% overall versus +8.0380% strict hold** after assumed 10 bps/side;
the paired 95% log-excess interval was [−0.00287, +0.00097], effective n=6.
The six-window research-only allocator returned +7.7333% versus matched
passive +7.8704%. This price refresh made only a tiny change to the previous
primary return and did not change the verdict. A `rescore` of the new local
artifact produced identical JSON for the frozen result, scorer, portfolio,
allocator input panel, allocator output, and AI ablation (six separate SHA-256
comparisons). The external validator still returned **FAIL**: the scored panel
was complete 88/88, but the pipeline lost to long hold, effective n was below
30, the paired lower bound was negative, and provider, universe, terminal
returns, news, and calibrated costs remained blocked. After extending the
metadata gate to company names, it also flagged **88/88 legacy packets**:
they were prepared before the code repair and retained current-provider names.
The reused predictions therefore remain historically contaminated; scoring
them again does not remove that exposure. No candidate was
promoted. Full child-repository regression: 265 tests passed; lint passed.

Local artifacts: `integrity-session-score-local.json` and
`integrity-session-rescore-local.json` under
`/private/tmp/stock-session-replay.secfacts2/` (ledger rows 8–9). An earlier
same-input run used the environment's configured cloud backend (ledger row 7,
cloud artifact `0314a495-1f9f-47ec-9776-54adff002111`); it was not a local
output and is not an independent holdout. All three runs used the same
historically inspected predictions, not fresh prospective forecasts.

A final CLI-input check also rejected case-insensitive duplicate tickers before
an API run starts. Previously `AAPL,aapl` would generate duplicate candidate
trials while strict hold collapsed them into one ticker, changing the
comparison's weights. This is an input-integrity repair, not a strategy edge.
