# Pipeline vs. Long-Hold Optimization — Technical Design

**Author:** Codex  **Status:** Portfolio stage and nine-arm collector implemented locally; v2 collection inactive pending calendar/model/provider provenance; confirmation also requires verified return data and calibrated costs  **Created:** 2026-09-23  **Reviewers:** User

## 1. Context and objective

The 2026-10-09 implementation upgrade is recorded in
[`portfolio-pipeline-upgrade.md`](portfolio-pipeline-upgrade.md). Completed runs
now feed a deterministic nine-view portfolio API and immutable cohort CLI; the
canonical graph and About page include that optional stage. The earlier v2
specification remains a frozen pre-implementation record. Its collection and
promotion have not been activated by this code change.

The original 2026-09-22 report showed −0.96% versus +9.06% for the 88-trial AI run, but its same-day cash allocation was order-dependent. The same-input correction on 2026-09-23 superseded those portfolio figures: `overall` returned −1.40% versus +8.04% for strict long hold and −0.47 percentage points versus the same-stake, same-window passive basket, with portfolio effective n of 6; the promotion gate failed. This is a historical in-session rescore, not independent forecast evidence, and no authenticated production-model run has validated the AI output. A separate 12-month momentum allocator returned +15.94% versus +9.06% on sealed trials, but its effective sample size was 3 and its net-return p-value was 0.743. That historical advantage is not promotion evidence: the rule was inspected on those slices, the final 2026 slice contains seven monthly periods, and the universe is fixed rather than point-in-time. See the corrected results and their limits in [`stock-pipeline-backtest-2026-09.md`](../analysis/stock-pipeline-backtest-2026-09.md).

The goal is to build a system that has a statistically credible chance of beating long hold after costs on unseen data, while preserving a clear distinction between AI forecast value and portfolio-allocation value. No backtest or implementation can guarantee future outperformance. The enforceable guarantee is narrower: do not promote a candidate unless it clears pre-registered out-of-sample gates.

### Goals

- Establish fair, reproducible comparisons against both strict buy-and-hold and a matched-exposure passive portfolio.
- Test the 12-month top-three momentum allocator as the lead challenger, then test whether AI signals add incremental value to it.
- Use point-in-time data, realistic execution, chronological validation, and correction for trying multiple candidates.
- Keep a failing or inconclusive candidate in research/shadow mode; retain long hold as the default baseline.

### Non-goals

- Promise a positive return or future benchmark win.
- Tune prompts or thresholds against the already inspected 2026 sample and call that out-of-sample evidence.
- Add leverage or shorting to force a higher headline return.
- Claim that a price-only allocator demonstrates AI forecasting skill.
- Connect the research strategy to live brokerage execution.

## 2. Current architecture and limitations

```text
Point-in-time session packets + predictions
        ├── AI signal scorer / event-driven portfolio simulator
        ├── 12-month momentum, top-three allocator [independent of AI]
        └── strict equal-weight buy-and-hold benchmark
                         ↓
                 markdown / JSON report
```

The AI path is implemented under `src/stock_analysis/backtest/`. The price-only allocator is implemented in `backtest/cross_sectional.py`; `session-score` reports it separately from AI signal results. The separation is valuable and should remain: it prevents an allocator win from being presented as an AI forecast win.

Known limitations that affect the next comparison:

- The scored universe contains current tickers and therefore has survivorship risk. A historical membership and delisting-aware universe is not yet validated.
- The AI run has only six directional trials and lacks authenticated production-provider predictions. Its old ticker-only effective-n/DSR outputs do not account for same-date cross-sectional dependence. The new SEC/FRED replay improves dated evidence coverage, but it is not a complete historical news feed.
- The event-driven AI portfolio uses a 10% cash stake by default, while the strict long-hold comparator can keep the full starting balance invested. Return and drawdown comparisons need a matched-capital audit.
- The monthly allocator's inspected 2026 result is too short to establish an edge. All tried configurations must count toward selection-bias correction.
- The benchmark and allocator must use the same total-return convention, dates, eligible universe, and cost assumptions. The current score path fetches auto-adjusted OHLC from yfinance and does not capture delisting or merger consideration.

## 3. Proposed evaluation architecture

```text
Point-in-time prices, universe, and dated evidence [MODIFIED]
                         ↓
          frozen data + strategy run manifest [NEW]
                         ↓
       ┌─────────────────┼──────────────────┐
       ↓                 ↓                  ↓
 AI signal alone   Momentum allocator   AI + allocator
       └─────────────────┼──────────────────┘
                         ↓
 Paired walk-forward evaluation vs. two passive baselines [MODIFIED]
                         ↓
 Statistical promotion gate + shadow run [NEW]
```

**Design intent:** make the allocator earn promotion as a portfolio strategy and make the AI earn inclusion by showing incremental out-of-sample value over that allocator.

| Component | Change | Reason |
|---|---|---|
| Run manifest | Freeze data snapshot, universe, dates, model/provider, prompt, parameters, costs, and candidate count | Make every result reproducible and count the full search |
| Backtest portfolio accounting | Mark positions to market and align invested capital, dividend treatment, and costs | Prevent exposure and return-convention differences from deciding the result |
| Data/replay inputs | Add survivorship-safe membership and dated evidence; fail closed when unavailable | Prevent future information and current-universe bias |
| Strategy comparison | Keep passive, allocator-only, AI-only, and hybrid rows separate | Attribute any excess return to the component that produced it |
| Promotion/shadow gate | Require statistical and operational checks before use | Avoid promoting a lucky slice |

No public API or database schema change is planned in the first research phase. Existing report additions should remain explicit and backward-compatible; run artifacts remain disposable unless the repository later defines a durable research-results owner.

### Implementation status — 2026-09-23

The first accounting/statistics pass is implemented in this repository:

- New pipeline trials enter at the next session's open; the provider fetch explicitly requests auto-adjusted OHLC, and the same fetched bars support daily marks.
- Portfolio reporting now exposes strict long-hold excess, a same-active-window/all-name passive diagnostic, daily marked-to-market drawdown when the path is complete, and an unavailable value rather than a misleading event-only drawdown.
- The monthly allocator uses month-end signals with next-session-open execution, drift-aware turnover costs, strict long-hold and matched passive comparators, paired moving-block intervals, and daily drawdown for all three portfolios.
- Sealed-trial allocation rejects unsynchronized or overlapping windows, compares against passive returns on those exact windows, and charges a round trip for each episode.
- `session-score` now reports separate AI-only and AI-filtered-momentum diagnostic arms, with exposure-matched references and a conditional within-basket label permutation. The ablation is additive and does not alter the production `overall` strategy or promotion gate; both diagnostic arms are counted in the run artifact. It fails closed when explicit next-session entry dates are absent, and its drawdown is explicitly window-endpoint-only, not an intra-window mark.
- When complete sealed windows overlap, the scorer retains the full panel for the primary pipeline/hold comparison and runs allocator/AI attribution on an earliest-feasible non-overlapping date subset selected without returns. Markdown, JSON, and ledger diagnostics label the subset `research_only`, record its selected dates and coverage, and preserve the full-panel overlap error. Other allocator failures still mark dependent AI ablation unavailable. The subset does not repair the confirmatory v1 schedule.
- Portfolio reports and the append-only experiment ledger now record per-strategy mean/peak committed principal and the fraction of price-path sessions with positions, using one shared session calendar. These are cash-deployment diagnostics based on original stake, not mark-to-market exposure or beta; absent price paths remain unavailable rather than zero.
- Scored `api`, `session-score`, and fixed-input `rescore` runs append to `backtest_experiments.jsonl` in the working directory (or `--experiment-ledger`) with frozen configuration, source/session/result fingerprints, headline and per-arm summary metrics, and a hash chain. It reports both unique strategy-config and distinct scored-evaluation counts for future selection-bias review; neither is yet used for a cross-run DSR correction. Earlier or manually explored candidates are not backfilled. The 2026-09-24 change also records completed standalone factor/cross-sectional runs with their price-input fingerprints and writes deterministic quality findings after each run; earlier standalone searches remain outside the count.
- The external-validation universe contract now requires hashed, per-trial `(ticker, as_of_date, security_id)` membership records and a terminal-return policy covering distributions, delistings, merger consideration, and missing returns. The scored report must attest to the exact same return-data hash and policy. This is a fail-closed contract only: the current yfinance score path does not ingest or attest to CRSP terminal returns, so metadata alone cannot pass the new provenance gate.
- The numerical promotion gate requires the `overall` pipeline to beat strict hold, effective sample ≥30, DSR ≥95%, a positive lower paired block-bootstrap bound, positive excess at 2× costs, and drawdown within 5 percentage points of strict hold. External validation separately gates provenance and data coverage.
- Effective sample calculations now use one shared portfolio cluster across tickers and holding windows. `portfolio_overlap_clustered_v1` is serialized with the score; external validation reads the `overall` portfolio row and blocks legacy artifacts without that basis marker.
- Existing targeted tests and the full child-repository suite pass. Legacy report fields remain readable; old drawdowns retain their period-end/event-only labels.

Still blocked, not solved by these code changes: licensed point-in-time US security/return data and its ingestion into the scorer, authenticated production-provider replay, externally calibrated execution costs, and an untouched forward holdout. If no `ANTHROPIC_API_KEY` is available, use the repository's two-stage in-session path (`session-prepare` → session-written predictions → `session-score`) for exploratory/research-only scoring. This does not satisfy the authenticated production-provider gate or count as v1 confirmation; historical in-session forecasts may be contaminated by model recall of later outcomes. Never fabricate `provider_run.json` to make that gate pass. The checked-in cached histories stop at 2026-09-17, so they cannot anchor a 2026-09-23 prospective entry. Until the required inputs are supplied and the external gates pass, results remain research-only; no implementation can guarantee future outperformance.

### Data-source decision for the survivorship-safe US universe

**Preferred source, pending existing licensed access:** CRSP US Stock & Indexes. Use permanent `PERMNO` identity and form the eligible universe from point-in-time U.S. common shares, ranked by market capitalization known at the prior close (or use a named historical index-membership file). CRSP documents daily OHLC/price fields, total returns with distributions, and security delisting data; its delisting calculations use post-delisting value and distribution information where available. Missing terminal returns must fail closed or be separately reported, never be set to zero. See the [CRSP database overview](https://www.crsp.org/research__trashed/crsp-us-stock-databases/) and [CRSP data definitions](https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Database_Data_Descriptions_Guide.pdf).

For prospective protocol v1, keep the existing 11-name panel fixed; the point-in-time market-cap/index universe rule above is reserved for a later market-wide study. V1's conclusions apply only to the curated panel, and the fixed basket must not be presented as representative of the U.S. stock market.

No WRDS/CRSP credentials or licensed export are available in this workspace, and no subscription or data purchase was made. [Norgate US Platinum/Diamond](https://norgatedata.com/stockmarketpackages.php) is a possible retail source for historical index constituents and delisted prices, but Norgate says it does not provide explicit delisting returns; by itself it does not meet the requested merger/delisting-return treatment ([Norgate FAQ](https://norgatedata.com/data-package-faq.php)). Do not backfill current constituents or a current ticker list as historical membership.

### Return-data completion and survivor-bias audit — 2026-09-24

> **[Status: Critical]** The licensed source is absent, so no delisted securities or verified dividend-inclusive terminal returns were added. The September 24 historical allocator win remains a selected-current-name, price-basis result. Do not turn the metadata contract below into a passing gate by setting flags without ingesting and using the underlying returns.

**Observed coverage.** The 11-name *allocator* panel in [`backtest-2026-09-24.md`](../../reports/analysis/backtest-2026-09-24.md) is AAPL, AMZN, AVGO, GOOGL, META, MSFT, NVDA, TSLA, TSM, UNH, V. Each checked-in `data/<TICKER>/price_history.csv` has only `date,open,high,low,close,volume` and ends on 2026-09-17. Seven begin on 2016-04-22 and AVGO, TSM, UNH, V begin on 2016-08-12. There is no dividend-cash, total-return, permanent-security-ID, membership, merger-consideration, or delisting-return column. `us_market.py` gets the bars from yfinance `history()` and stores OHLCV only; the allocator explicitly labels its basis `provided_open_close_not_dividend_verified`. The **frozen AI v1** panel below is different: it contains APP and NFLX instead of UNH and V. Do not use one panel's performance or membership artifact to validate the other.

The existing fixed-rule sensitivity check is informative but does **not** measure survivor bias: on the 11-name allocator panel the full 2017–2026 excess was +1473.51 percentage points, versus +417.47 pp when NVDA was omitted and +473.03 pp when TSLA was omitted (each against its own smaller long-hold universe). The 2017–2018 transfer slice lost by 3.45 pp. These results show substantial dependence on the current-name basket; they say nothing quantitative about names that disappeared before the present. No survivor-bias-adjusted excess return is estimable from the current CSVs.

**Required source and return contract.** Obtain an already-licensed CRSP US Stock & Indexes extract that covers the full formation/lookback window and every holding/terminal date, including active and inactive securities. Use the source's permanent security ID (`PERMNO`) as identity, with dated name/ticker history only as display metadata. For each decision date, derive eligibility from a frozen prior-known membership/index file or prior-close common-share and market-cap rule; record excluded and eligible counts. The return stream must include dividend/distribution total returns and a terminal delisting/merger amount for every held security. CRSP documents daily total returns with dividends reinvested on the ex-date, delisting values, permanent IDs, and explicit missing-delisting-return codes ([CRSP data definitions](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-data-descriptions-guide-crspaccess/), [CRSP stock databases](https://www.crsp.org/research__trashed/crsp-us-stock-databases/)). Treat CRSP missing codes such as −55, −66, and −99 as **missing**, never as numeric returns or zero; the −88 active-security code is not a delisting loss. Stop the comparison if a held security lacks a valid terminal treatment. A merger's cash and stock consideration must be valued under the same return convention as ordinary distributions; if the source cannot resolve it, stop rather than quietly drop the security.

**Owner → consumer → migration/test map.**

| Contract | Owner/input | Consumers | Migration and acceptance gate |
|---|---|---|---|
| Historical eligibility | Hashed CRSP extract + frozen selection policy; `PERMNO`-dated membership | allocator, AI trial manifest, strict hold, matched passive | Build `universe.json` schema v1 with one source-backed membership row per trial; cover entry, exits, delistings, and ticker changes. Do not retrofit current ticker identities into historical membership. |
| Total and terminal returns | Hashed daily total-return and corporate-action extract | both candidate equity paths and both benchmarks | Add an explicit return-data adapter; use identical dated distributions, terminal value, and missing-value policy for every arm. Version the result/provenance if report semantics change. |
| External proof | `external_validation.py` owns `universe.json` and `terminal_return_provenance` checks | promotion gate and report reader | Attach the actual consumed return-data hash to the score; run the validator plus fixtures for dividend, bankruptcy, cash/stock merger, ticker change, and missing terminal return. A matching hash/boolean without observed use is insufficient. |

**Bias comparison after ingestion.** First freeze the security-selection rule, costs, dates, and code hash without inspecting new outcomes. Re-run the same allocator and long hold on the point-in-time eligible universe with the same total-return stream; show eligible/held counts, delisted and merged counts, missing-return exclusions (which must be zero for a pass), both net returns, paired excess interval, and the difference from the current-name result. Keep the current-name run as an explicitly labeled diagnostic; never rename that historical period a fresh holdout. This audit checks how much the measured result changes under complete data. It does not itself create prospective validation.

## 4. Evaluation rules

### Benchmark contract

Every candidate is evaluated against both baselines over identical dates and the same point-in-time eligible universe:

1. **Primary — strict long hold:** equal-weight the eligible names at the start and hold through the test window, with dividends and entry/exit costs represented consistently.
2. **Diagnostic — matched passive allocation:** use the same rebalance dates, exposure limits, and investable cash as the candidate, but allocate passively across the same eligible names. This isolates selection/timing value from cash utilization.

Use paired monthly portfolio returns for the primary comparison. Do not compare an underinvested event simulator with a fully invested benchmark and interpret the raw wealth gap as forecast quality. Report total return, CAGR, marked-to-market maximum drawdown, turnover, exposure, and net excess return.

### Candidate sequence

1. Reproduce the strict benchmark and the frozen 12-month/top-three allocator without changing parameters.
2. Run AI-only against the same portfolio accounting; treat AI results as a separate hypothesis.
3. Test a hybrid only as an incremental overlay on the allocator (for example, AI evidence may alter eligibility or position weight). Compare it directly with allocator-only; do not assume an AI BUY label should create a position.
4. First match gross exposure across strategies to isolate selection quality. Then test capital utilization and a small pre-registered set of position rules (equal weight, volatility-scaled weight, and a cash reserve) as separate candidates. This directly tests whether the current 10%-per-signal sizing and neutral-to-cash behavior create avoidable cash drag.
5. Explore alternative lookbacks, breadth, risk controls, and signal thresholds only inside training folds. Freeze the selected rule before each outer test fold.
6. Keep long-only and unlevered for the first promotion cycle. Any later short or leverage study requires a separate cost, borrow, and risk model.

Missing or stale point-in-time evidence is unavailable, not bearish. Neutral may mean no AI directional forecast; the allocator's exposure decision is evaluated separately. Historical records with `available_as_of` after the decision date must be rejected. Execution uses the next tradable price after the decision and the specified limit/stop rules; it must not assume a fill at an unfillable limit.

### Promotion gate (proposed defaults)

A candidate remains research-only unless all are true on pre-registered outer walk-forward results:

- Net CAGR excess over strict long hold is positive and the lower bound of a paired, time-block-bootstrap 95% confidence interval is above zero.
- Effective sample size is at least 30 independent portfolio periods, spanning at least three distinct market regimes. Resampling must cluster by rebalance date to account for correlated stocks and serial dependence.
- Deflated Sharpe probability is at least 95%, calculated using the full number of strategies, parameter sets, and prompts tried.
- Excess return remains positive at twice the base transaction-cost assumption.
- Maximum drawdown is no more than 5 percentage points worse than strict long hold, unless the reviewer explicitly accepts a different risk budget before the test is opened.
- The excess-return result is not dominated by one ticker or one short calendar slice; report leave-one-ticker-out and per-regime results.

These are release criteria, not a promise of future returns. The current seven-month final slice and effective n of 3 do not pass them.

## 5. Work plan and decision gates

| Phase | Work | Exit condition |
|---|---|---|
| 0. Freeze protocol | V1 rules are recorded below; seal run-specific provider/model, prompt, code, universe, price, and cost fingerprints before the first prediction. Mark previously inspected dates as development data. | Decision rules are frozen; no confirmatory result is admissible until every input fingerprint and required external artifact is present. |
| 1. Audit accounting | Compare invested capital, return/dividend convention, entry/exit timing, turnover costs, and daily marked-to-market equity across AI, allocator, and benchmarks. | A synthetic fixture proves identical capital and dates; drawdown includes intra-hold losses. |
| 2. Close data gaps | Build or source point-in-time membership including delistings; validate dated prices, fundamentals, news, and macro. Run the real provider with a fixed model/prompt version when authenticated. | External validation passes or the report clearly blocks the missing source/provider; no current-only evidence is backfilled. |
| 3. Run controlled ablations | Compare strict hold, matched passive, allocator-only, AI-only, and hybrid. Tune only within inner chronological folds; log every tried candidate. | The hybrid shows incremental value over allocator-only, or AI is excluded from the execution rule. |
| 4. Locked validation | Use nested walk-forward folds with non-overlapping/purged outcome horizons, then a genuinely untouched forward holdout. Apply block bootstrap, effective-n, DSR, and 2× cost checks. | Every promotion gate passes on the frozen candidate; otherwise keep research/shadow status. |
| 5. Shadow operation | Record decisions and hypothetical fills without placing trades. Reconcile predictions, evidence timestamps, and realized executions; refresh evaluation only on pre-set dates. | Data and execution behavior remain valid, and forward evidence continues to pass the same gate. |

### Frozen prospective protocol v1 (2026-09-23)

> **[Status: Warning]** The decision rules below are locked for one prospective study, but collection has not started. All previously inspected dates remain development data and cannot be renamed as the holdout.

> **[Status: Critical — superseded before collection]** The portfolio simulator previously sized same-day entries in ticker order, so its result changed when the input list was permuted. The corrected rule uses one pre-session cash snapshot and equal, capped same-day stakes. This changes the candidate implementation even though the nominal 10% parameter stays the same; v1 cannot be used for confirmation. The 30-calendar-day date grid also produces overlapping sealed windows, blocking the planned allocator/AI ablation. A v2 protocol must freeze the corrected code hash, a non-overlapping ablation schedule or an overlap-aware allocator, and all other gates before the first prospective prediction. No v1 forward observations were collected. The current provider gate remains blocked even when a self-declared `provider_run.json` is present, because no authenticated invocation-to-prediction-to-score binding exists yet.

- **Claim and universe:** test the current AI `overall` pipeline on this preselected 11-name US-listed panel: AAPL, AMZN, APP, AVGO, GOOGL, META, MSFT, NFLX, NVDA, TSLA, and TSM. This is a curated-panel claim, not a market-wide strategy claim. The raw scored artifact is unavailable, so do not claim this exactly reproduces the earlier 88-trial roster until that roster is verified. Freeze these v1 names; do not add replacements. Map each trial to its stable CRSP `PERMNO`; delistings, mergers, distributions, and remaining cash stay in the return path.
- **Schedule and execution:** collect exactly 36 predetermined as-of dates at the CLI's `monthly` spacing (30 calendar days, not calendar month-end), with a 30-calendar-day outcome horizon. Enter at the next tradable session open. The six-period margin above the n≥30 gate allows for overlap and missing observations; if the final effective n is below 30, fail the run rather than extend it after inspection. Wait until every outcome is mature before the single final score; do not inspect interim aggregate P&L. The 36 dates are nominal periods, not 396 independent ticker-trials.
- **Confirmatory candidate:** only the existing long-only `overall` portfolio rule (`position_size_pct=0.10`, no shorting) is eligible for the primary promotion claim. Freeze exact provider/model version IDs, prompt hashes, code/config fingerprint, and all run settings before the first prediction. The current default comparison scores nine rows (`overall`, `overall_fundamentals_confirmed`, four individual agents, `buy_and_hold`, `rolling_long`, and `signal_timing_long`); DSR uses the recorded full row count. `overall_fundamentals_confirmed` is an exploratory post-hoc diagnostic and cannot replace the primary candidate. The standalone momentum allocator, AI-only attribution sleeve, and AI-filtered-momentum sleeve remain secondary research and cannot replace the primary candidate after results are opened.
- **Benchmarks and costs:** compare over identical dates and names against strict equal-weight buy-and-hold from first entry to final exit; also report matched-exposure passive. Use hashed CRSP total-return inputs, including distributions and terminal delisting/merger returns, for candidates and benchmarks. Promotion is blocked until a calibrated `cost_model.json` covers spread, slippage, and commission and is applied identically; rerun the primary comparison at 2× those costs. The historical 10 bps/side setting is a development assumption, not a calibrated v1 cost.
- **Inference:** the primary effective sample is the portfolio row's `effective_n` with basis `portfolio_overlap_clustered_v1`, which clusters same-date securities and discounts overlapping holding windows. Require effective n ≥30 and observations spanning three predeclared CRSP value-weighted US-market regimes: trailing 12-month total return ≥+10% (supportive), between −10% and +10% (neutral), or ≤−10% (adverse). These cutoffs are an operational v1 definition, not a canonical taxonomy. Use the existing 21-trading-day moving-block interval for daily paired log excess (2,000 resamples, seed 0). Keep the existing promotion gates: positive net excess over strict hold, lower 95% paired interval >0, DSR ≥95%, positive excess at 2× cost, and drawdown no more than 5 percentage points worse than strict hold. Failure or insufficient data means no promotion, not a threshold change.
- **Input gate:** before the first date, require a licensed CRSP extract and its hash, a complete membership/return `universe.json`, dated evidence with first-available clocks, authenticated production-provider `provider_run.json`, and externally calibrated costs. Keep API secrets in local provider configuration; never put them in the run bundle or this repository. If no API key is available, an in-session score may be run as a separate exploratory artifact using `session-prepare` → session-written predictions → `session-score`; it does not meet the v1 provider gate, and historical session forecasts are not clean confirmation evidence.

Changing the panel, candidate, signal schedule, horizon, model/prompt, cost method, bootstrap, regime cutoffs, or any promotion threshold creates protocol v2 and requires a fresh untouched forward sample. The current 88-trial bundle cannot satisfy v1: it is historical development data, SEC-only events are not a complete provider news feed, it has no provider-backed predictions, no CRSP universe/terminal returns, and no calibrated cost model.

Historical data already inspected in the September 2026 report cannot become a fresh final holdout by renaming the split. Use it for development/nested walk-forward diagnostics and collect new forward observations after the candidate and protocol are frozen.

## 6. Failure handling and risks

| Failure | Expected behavior |
|---|---|
| Missing point-in-time membership, price, or evidence | Fail closed for that comparison; report coverage and reason. Never substitute present-day data silently. |
| Provider run is unavailable or cannot be paired with its model/prompt manifest | Mark AI evaluation blocked; allocator-only research may continue with separate attribution. |
| Benchmark accounting or cost inputs differ | Invalidate the comparison and rerun after correction. |
| Candidate fails statistical, cost, or drawdown gate | Do not promote; retain long hold as baseline and record the failure without retuning on the locked holdout. |
| A newly discovered bug changes prior outputs | Version the protocol and treat affected runs as superseded; do not overwrite their artifacts. |

Main risks are survivorship bias, repeated strategy search, missing event evidence, unrealistic fills, and confusing allocation alpha with AI forecast alpha. The mitigations are point-in-time data, frozen manifests, explicit candidate counts, execution-cost stress, and separate result rows. A real possibility is that the momentum allocator continues to beat the sample while the AI adds no value; the plan allows that result and does not force AI into the portfolio.

## 7. Alternatives and recommendation

| Option | Trade-off | Decision |
|---|---|---|
| Keep current AI signal as the portfolio driver | Preserves the intended product, but current measured signal has no demonstrated edge | Do not promote until it passes the gate |
| Promote the standalone momentum allocator now | Best measured candidate, but selected on inspected data with very small final/effective sample | Use as the lead challenger, not as a validated strategy |
| Test allocator first, then require AI to add incremental OOS value | Preserves attribution and can reject unhelpful AI complexity; takes longer and may end with a non-AI strategy | Recommend |
| Keep long hold as the only strategy | No research cost or model risk, but does not test whether a systematic improvement exists | Retain as incumbent and fallback |

## 8. Open decisions

- **Locked for v1:** maximum drawdown may be no more than 5 percentage points worse than strict hold. A different risk budget requires protocol v2 before data collection.
- **Blocking for the historical contract:** Provide an already-licensed CRSP daily export (or authorize an alternative that supplies point-in-time membership and total returns including delistings/mergers) before building `universe.json` and integrating terminal returns. This plan does not authorize a purchase.
- **Blocking for the v1 confirmatory run:** make the production provider available locally and freeze exact model versions before the first date. If no key is available, use in-session mode for exploratory scoring as documented in the quant-backtest-review skill and child README; leave the production-provider validation gate blocked and do not claim promotion evidence. No provider credentials were present during the 2026-09-23 check, so no paid model call was attempted.
- **Blocking for promotion:** provide an externally calibrated execution-cost artifact. Until then, 10 bps/side and its 2× stress are only assumptions and cannot pass the external gate.

The operational target is the complete system versus long hold. Reports must also show whether the allocator alone wins and whether adding AI improves on that allocator; those are separate claims and use separate promotion comparisons.

## 9. Immediate optimization sequence — 2026-09-24

> **[Status: Warning]** This is an implementation order for research, not a revision of the superseded v1 promotion protocol. The 88 historical AI trials and inspected allocator slices remain development data. Do not call a retuned result on them out-of-sample.

### Phase A — Make comparisons reproducible with current data

1. **Partly implemented 2026-09-24:** completed standalone `factor` and `cross-sectional` CLI runs now enter the shared append-only ledger with universe, configuration, date window, price and source fingerprints, plus new/repeated evaluation counts. A deterministic quality report flags the same frozen input producing changed metrics. Failed invocations and historical manual searches are not yet reconstructed; the cumulative count remains audit metadata, not a cross-run DSR correction.
2. Freeze one local OHLCV snapshot for development. Re-score candidates from that snapshot rather than allowing a provider refresh to change the data mid-comparison. Assert matching first entry, final exit, execution bar, currency, and cost convention across each candidate and strict/matched passive benchmark.
3. Add focused synthetic accounting fixtures for a cash dividend, split, ticker rename, bankruptcy, and cash/stock merger. Until a verified total-return source is actually ingested, mark the first and last event types as unsupported and fail closed in any claim of total-return equivalence. Keep the current OHLCV allocator explicitly labeled price-basis research.

Exit: identical inputs reproduce identical JSON; all candidate runs appear in one search ledger; the report cannot say `total return` while consuming OHLCV-only data.

### Phase B — Improve the pipeline's evidence and attribution

1. Keep separate rows for `overall`, allocator-only, AI-only, AI-filtered allocator, strict hold, and matched passive. For each row show coverage by analyst, committed capital, trade count, and paired excess. The current 88-trial in-session `overall` was −1.40% versus +8.04% strict hold and −0.47 pp versus same-stake matched passive, with mean committed principal 27.99%; larger sizing alone does not resolve the observed selection gap. An optional `--cash-rate-replay` DFF attribution reports the return on idle cash and cash-adjusted matched passive using dated, point-in-time rates; it is explicitly a reference proxy and does not alter primary returns or promotion gates.
2. Audit each non-neutral prediction at its as-of date: which dated filing, SEC event, price feature, or macro observation supported it; what was unavailable; whether the event was knowable before the trade. Missing complete historical news is an abstention/coverage issue, not a negative signal. Keep production-model output distinct from the in-session deterministic reconstruction.
3. Before changing prompts, weights, or thresholds, write down a small set of hypotheses and the outcome each would have to improve (for example, AI incremental paired excess over allocator-only at matched exposure). Tune only within chronological training folds; include every attempted prompt/parameter in the ledger. If AI remains worse than matched passive, keep it as an explanatory research layer rather than a portfolio filter.

Exit: AI's incremental value is identifiable without cash-utilization or evidence-coverage confounding. A negative or uncertain paired result stops that candidate; it does not trigger another search on the same held-out dates.

### Phase C — Upgrade validation before any promotion

1. Build a new prospective protocol after the corrected same-day sizing and a non-overlapping decision schedule are frozen. Seal universe, rules, model and prompt IDs, data snapshot, cost model, dates, and gates before collecting predictions. If no authenticated provider is available, operate a separate in-session research track and do not mark its provider gate passed.
2. Once licensed point-in-time membership, dividend-inclusive returns, and terminal delisting/merger treatment are available, run the source-backed survivor-bias audit in §3. Until then, the existing 11-name panel is a curated-name claim only; it cannot validate a market-wide edge.
3. Evaluate paired net excess against strict hold and matched passive, daily marked-to-market drawdown, block confidence intervals, effective sample size, DSR using all tried candidates, and 2× calibrated-cost sensitivity. Preserve a never-inspected forward holdout and run a shadow portfolio on a fixed calendar; do not add more dates after seeing a failure.

Exit: every promotion gate in §4 passes on genuinely unseen, source-complete results. Otherwise keep long hold as the incumbent and report the measured reason for failure.

## 10. October 9 diagnostic experiments and forward v2

The [diagnostic implementation plan](pipeline-diagnostic-experiments.md) is complete
for offline research. The [new report](../../reports/analysis/2026-10-09-pipeline-gap-diagnostics-final/README.md)
preserves the original forecasts and prices and counts all 12 full-panel / eight
episode comparison rows. It supersedes no historical observations or production rules.

At 10bps/side, accepting all ten declined raw buys would yield +3.37%, still below
the full-panel strict hold +20.66%. FT's -22.87pp gap decomposes into +0.80pp versus
same-stake/date passive and -23.67pp for that passive versus continuous hold; this
is an accounting identity combining deployment/timing differences, not causal proof.

The existing date-only selector chooses nine non-overlapping windows / 72 trials.
The fixed 12-month/top-three allocator yields +36.05%, scheduled passive +29.18%,
and strict continuous hold +20.62% under multiplicative episode fees. Adding FT
filtering reduces return to +5.92% and AI filtering to zero. FT filtering has a
weak conditional selection signal at 37.04% exposure: +9.07pp versus an equal-
exposure momentum sleeve, but permutation p=0.0835 on six informative periods.
Allocator effective N=9, DSR~0.501, and its paired passive interval crosses zero.
These inspected outcomes are not promotion evidence; they motivate a fixed new
forward comparison without changing abstention thresholds.

[Forward validation v2](pipeline-forward-validation-v2.md) specifies nine arms,
36 predetermined 35-day anchors beginning October 12, 30-day non-overlapping
episodes, and the existing statistical/data/cost gates. Rules and their digest
are recorded in the report's `forward-protocol-v2.json`. Collection has not
activated: exact provider/model/prompt provenance and a conforming nine-arm
collector must be sealed before the first entry. Missing that cutoff requires a
new future version. No historical forecast may be relabeled prospective.

The October 7 forward cohort remains immutable, separate from v2, and cannot be
scored before November 7 UTC. This research flow is separate from the production
`pipeline.json`; no unimplemented allocator or collection stage is added to the
production diagram.
