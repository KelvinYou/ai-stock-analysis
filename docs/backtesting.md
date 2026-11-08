# Backtesting and Research Reference

Detailed reference for the research modes of `stock-analysis-backtest`, portfolio
cohorts, and the evidence policy. The [README](../README.md) carries the short
version; this file holds the full flag-level behaviour.

## Portfolio decisions

Completed single-ticker runs can now feed a deterministic portfolio research
stage through `POST /api/v1/portfolio-plans`. Supply 3–50 distinct completed run
UUIDs from one US/USD decision session. The response contains nine target-weight
views: continuous hold, scheduled passive, allocator, FT weighted/agreement,
AI, and three allocator hybrids. The allocator ranks trailing twelve-month
returns and selects three equal sleeves; filtered sleeves remain cash.
An unavailable panel returns reasons and cash-only views.

These research weights use no personal holdings and place no orders. Portfolio
valuation, concentration checks and account-specific sizing remain consumers'
responsibility. See the [upgrade contract](design/portfolio-pipeline-upgrade.md)
for run binding, collection requirements and limitations.

## Freeze and score portfolio research

Use the module directly in an existing checkout; a fresh installation also
provides `stock-analysis-portfolio`.

```bash
# Export completed cloud runs; the server credentials stay in the environment.
.venv/bin/python -m stock_analysis.portfolio_cohort export \
  --run-ids '<uuid1>,<uuid2>,<uuid3>' --output /tmp/portfolio-bundle.json
.venv/bin/python -m stock_analysis.portfolio_cohort plan \
  --bundle /tmp/portfolio-bundle.json --output /tmp/portfolio-plan.json

# Freeze after the registered decision session closes, before its next open.
# Use an activated protocol with pinned calendar/model/prompt provenance.
.venv/bin/python -m stock_analysis.portfolio_cohort freeze \
  --bundle /tmp/portfolio-bundle.json --protocol /path/to/activated-protocol.json \
  --cohort /path/to/new-cohort
.venv/bin/python -m stock_analysis.portfolio_cohort verify --cohort /path/to/new-cohort
.venv/bin/python -m stock_analysis.portfolio_cohort score --cohort /path/to/mature-cohort
.venv/bin/python -m stock_analysis.portfolio_cohort compare \
  --cohorts /path/to/mature-cohort-1 /path/to/mature-cohort-2 \
  --output /tmp/portfolio-comparison.json
```

Freeze rejects legacy naive timestamps, unavailable history and missing activation
identity. Scoring rejects immature samples before fetching outcomes and never
overwrites an existing score. Comparison retains continuous hold through episode
gaps, reconciles daily equity with episode returns, and reports drawdown,
21-session paired intervals versus hold and allocator, and nine-arm DSR.
Provider-adjusted prices and assumed fees remain research inputs; all outputs
keep `promotion_ready=false`. The prepared v2 protocol has not been activated.

## Long-term holding use

The current pipeline has not demonstrated an after-cost return advantage over
strict buy-and-hold. The [September 2026 comparison](../reports/analysis/backtest-2026-09-24.md)
is development research, not a validated reason to trade on its conviction
scores, entry levels, or stop levels. Its price fetch and dated research evidence
can still support a long-term review.

For that use, the consumer should answer a smaller set of questions:

- What is held, what is each position worth, and are its price and FX inputs fresh?
- How concentrated is the portfolio by company, sector, market, and currency?
- For an individual company, what was the original holding thesis, which dated
  filings or events have changed it, and what evidence would invalidate it?
- What was the investor's actual return after dated cash flows, dividends,
  fees, and currency conversion? A current holding's shares and average cost
  cannot reconstruct that history.

Broad-market funds mainly need allocation and contribution reviews. Individual
stocks also need thesis reviews after material filings or events. This repository
does not yet provide a transaction ledger or a validated long-hold thesis-change
alert, so neither should be inferred from a briefing or a price-only P&L figure.

## Run backtests

```bash
stock-analysis-backtest --tickers AAPL,MSFT --start 2024-01-01 --end 2024-12-31

# Charge a one-way transaction cost (bps) on entry and exit. Reports gross and
# net side by side — 0 is the default but it is an assumption, not neutral.
stock-analysis-backtest --tickers AAPL --start 2024-01-01 --end 2024-12-31 \
    --cost-bps 10

# Also feed realized outcomes back into outcome memory. Off by default so that
# repeated backtests over the same window stay comparable.
stock-analysis-backtest --tickers AAPL --start 2024-01-01 --end 2024-12-31 \
    --record-outcomes
```

API backtests regenerate every briefing. The old cache was keyed only by ticker
and date, so a changed model or prompt could inherit an older prediction while
the report named the new settings. `--no-resume` remains accepted for older
scripts but is now redundant. Portfolio comparisons stop if any requested trial
has a failed or missing outcome. Same-day orders size from one pre-session cash
balance, with equal scaling if their combined target exceeds that balance.

For an implementation-only rerun, keep the original scored trials, forward
price paths, and allocator ranking history fixed:

```bash
stock-analysis-backtest --mode rescore --score-report /tmp/original-score.json \
  --cost-bps 10 --output /tmp/corrected-score
```

When allocator scoring succeeds, new score artifacts include
`allocator_price_histories`, capped at the last decision date. `rescore` uses
that frozen panel and does not reread the mutable
price store. Older score artifacts without it still recalculate the primary
scorer and portfolio, but explicitly mark the sealed allocator and AI ablation
unavailable; they cannot reproduce those diagnostics. This is a development
comparison, not a fresh out-of-sample test. A second `session-score` call can
fetch revised historical prices and is therefore a different price snapshot.
Set `STORAGE_BACKEND=local` when the scored JSON must be written to `--output`;
the configured cloud backend stores the artifact remotely instead.

To attribute the return on idle portfolio cash, pass an official FRED DFF CSV
or a JSON/JSONL replay containing `FRED:DFF` observations:

```bash
stock-analysis-backtest --mode rescore --score-report /tmp/original-score.json \
  --cash-rate-replay /tmp/fred-dff.csv --cost-bps 10 \
  --output /tmp/cash-yield-score
```

The report compounds end-of-day uninvested cash at the latest DFF observation
available by that calendar date, using ACT/365 and at most four calendar days
of carry. It identifies DFF as a reference proxy rather than a brokerage sweep
or deposit yield. Cash attribution is diagnostic: it does not alter primary
strategy returns or the promotion gate. The source observations and hash are
embedded in the scored artifact so later fixed-input rescores need no network
refresh.

Portfolio comparisons also include `overall_fundamentals_confirmed`, a
research-only alternative that takes an overall directional signal only when
the fundamentals analyst agrees. It is included in the DSR strategy-search
denominator but does not replace the `overall` promotion candidate. This
post-hoc diagnostic is exploratory on previously inspected trials.

## Run deterministic factor research

This mode uses the local `data/<TICKER>/price_history.csv` only — no API key or
LLM call. It runs the fixed long-only momentum baseline through expanding
walk-forward folds, enters on the next bar's open, and reports gross and
cost-adjusted returns side by side:

```bash
stock-analysis-backtest --mode factor --tickers AAPL \
  --start 2020-01-01 --end 2026-08-14 \
  --factor-lookback-bars 20 --factor-holding-bars 20 \
  --walk-forward-train-bars 252 --walk-forward-test-bars 63 \
  --cost-bps 10 --output factor-aapl
```

The factor is a research baseline, not a live-trading recommendation. The
output includes the exact protocol, fold boundaries, trade log, Wilson interval,
max drawdown, net p-value, and a buy-and-hold comparison. It does not fit a
model inside the test folds, so its result is evidence about one fixed rule on
one dataset rather than a claim of durable alpha.

Completed factor and cross-sectional runs append their candidate and strict-hold
benchmark to `backtest_experiments.jsonl` (override with `--experiment-ledger`).
Local runs also write `<output>.quality.json`; every Markdown report ends with
deterministic quality findings and next checks. The analysis flags benchmark
losses, uncertain intervals, small samples, and unverified return inputs. It
never changes a rule or promotes a historical winner. Ledger counts begin when
recording starts and do not reconstruct earlier manual searches; repeated
evaluations are identified separately. If identical frozen inputs and settings
produce different recorded metrics, the next quality report flags the change
for accounting review.

## Run cross-sectional allocation research

The cross-sectional mode tests a separate portfolio layer: at each month-end it
ranks a fixed universe by the previous 12 months' return, holds the equal-weight
top three for the next month, and charges entry, rebalance, and exit costs. The
strict equal-weight buy-and-hold benchmark uses the same first and last month-end:

```bash
stock-analysis-backtest --mode cross-sectional \
  --tickers AAPL,AMZN,AVGO,GOOGL,META,MSFT,NVDA,TSLA,TSM,UNH,V \
  --start 2019-01-01 --end 2026-09-17 \
  --cross-sectional-lookback-months 12 \
  --cross-sectional-top-n 3 \
  --cost-bps 10 --output cross-sectional-11
```

This is deterministic portfolio construction, not evidence that the AI analyst
layer forecasts returns. Freeze the universe and parameters before using a final
holdout; a result selected after inspecting that holdout is a research failure.

Every headline metric ships with an interval, because a point estimate over a
few dozen trials reads as an edge whether or not it is one:

- **Hit rates** carry Wilson intervals, and the report says so outright when the
  interval still spans 50%.
- **Sample size is discounted for overlap.** Weekly as-of dates at a 30-day
  horizon share most of their price path; 13 nominal trials can be worth 1.8
  independent ones, and every t-statistic uses the discounted count.
- **Sharpe is reported probabilistically** (PSR), correcting for the negative
  skew and fat tails that flatter a raw Sharpe.
- **The strategy comparison is deflated.** Scoring several strategies and
  reporting the best is a search; the winner gets a Deflated Sharpe against the
  expected best-of-N under the null.

If `--interval` is shorter than `--horizon`, the report will tell you how much
of the sample is redundant.

## Run backtests in the current session (no API key)

The Python process cannot call the current Claude/Codex conversation directly.
Use the two-stage session mode instead: the first command writes point-in-time
input packets without future prices; the current session writes the compact
`SessionPrediction` records; the second command runs the normal scorer and
portfolio simulation.

```bash
stock-analysis-backtest --mode session-prepare \
  --tickers AAPL,MSFT --start 2025-08-01 --end 2026-07-01 \
  --session-dir /tmp/aapl-msft-session

# Write predictions.json in the session directory, then:
stock-analysis-backtest --mode session-score \
  --session-dir /tmp/aapl-msft-session \
  --output /tmp/aapl-msft-backtest
```

If sealed 30-day windows overlap, the allocator/AI ablation now uses the
earliest feasible non-overlapping date subset, chosen from execution dates
without consulting returns. The primary pipeline and long-hold score still use
every trial. Markdown, JSON, and the experiment ledger label the subset
`research_only`; its result cannot satisfy the primary promotion gate. The
subset is a diagnostic of AI's incremental value, not a replacement for a
prospectively frozen non-overlapping schedule.

Session predictions must contain `ticker`, `as_of_date`, `overall_signal`,
`conviction_score`, `signal_convergence`, and optional `agent_signals` (whose
values are exact `strong_buy`, `buy`, `neutral`, `sell`, or `strong_sell`
signals). The declared ticker/date grid must be complete, extra predictions are rejected,
and every packet's identity, path, and price dates are checked before forward
prices are fetched. Historical packet metadata uses the requested ticker as
the name and market-default currency; present-day provider names are not
point-in-time evidence. During scoring, convergence is recomputed from the
analyst signals;
the conviction score uses the production cap `min(abs(raw model score), abs(net analyst consensus))`, with the signal sign, and
directional predictions that disagree with that consensus or do not clear the
deterministic conviction/convergence execution gate are scored as `neutral`.
Raw model conviction is retained as `raw_conviction_score`; neutral synthesis has zero calibrated conviction. A gated directional thesis can retain its capped score for attribution without creating a trade.
Optional `agent_confidences` can provide `high`, `medium`, or `low` weights.
Session packets also declare point-in-time evidence availability. Without a
replay directory, historical fundamentals use the yfinance filing-date adapter
and latest-only yfinance news is excluded. For a stricter replay, the builder
below supplies SEC CompanyFacts fundamentals, SEC filing events, and FRED DFF;
current company-name, sector, and industry metadata is omitted unless a
versioned source is provided. Legacy packets containing current names under
an omitted-metadata marker fail the external metadata gate. When fundamentals,
dated news/recommendations, or macro data are
unavailable, scoring forces those analysts to `neutral` with `low` confidence
instead of trusting unsupported directional output. Unavailable analysts remain neutral/low in the canonical four-role denominator, matching production. Manifest v4 records this contract. Legacy manifests still load, but old scored JSON is not silently rewritten. Use `rescore --recalibrate-session --session-dir ...` to apply the new calibration to frozen predictions and existing outcomes without fetching prices.

Scored trial JSON preserves the signal path for later attribution:
raw_agent_signals are the original analyst labels; agent_signals are the labels
used by strategies after evidence guards and name normalization;
synthesized_signal is the overall choice before deterministic gates;
overall_signal is the final executable signal; and
signal_gate_reasons contains stable reason codes. The Markdown report adds
descriptive buy-overlap and gate counts. Older artifacts remain readable, but
missing trace fields mean provenance was not recorded.

To add historical evidence without opening a look-ahead path, pass a replay
directory to `session-prepare`:

```text
replay/
├── fundamentals/AAPL.jsonl # SEC facts + fiscal_period_end + available_as_of
├── valuation/AAPL.jsonl    # optional dated price + currency + declared share_basis
├── news/AAPL.jsonl         # published_at + available_as_of per record
└── macro.jsonl             # as_of_date + available_as_of per snapshot
```

```bash
stock-analysis-backtest --mode session-prepare \
  --tickers AAPL,MSFT --start 2025-08-01 --end 2026-07-01 \
  --session-dir /tmp/aapl-msft-session --replay-dir /path/to/replay
```

The loader keeps a record only when both clocks are on or before the trial
date. Missing or malformed replay timestamps are excluded or fail closed; the
pipeline never infers availability from a fiscal/event date alone. No replay
directory means sentiment and macro remain explicitly unavailable, preserving
the current behaviour.

Both API backtests and session preparation accept `--replay-dir`. Financial
history retains each known fiscal duration and its latest available revision.
New packets and fundamental tools expose `fundamental_context`: observations,
comparable year-ago growth, valuation and separate readiness/gap diagnostics.
Quarterly and YTD cash flows are never combined. SEC date-only filing facts
become available the following day.

Valuation replay records require `price`, `price_date`, `available_as_of`,
`currency`, `share_basis` and `source`. P/E requires four contiguous fiscal
quarters or a current annual EPS period, with the same currency and declared
share basis as that price. SEC output leaves the basis unknown; auto-adjusted
technical prices do not establish it. Missing inputs keep valuation unavailable.
Old sealed packets remain readable; enriched packets are checked against their
source observations before outcome prices are fetched. Session preparation
refuses to overwrite an existing manifest or packet set.

The reproducible public-source builder is:

```bash
python -m stock_analysis.backtest.replay_builder \
  --tickers AAPL,MSFT \
  --start 2019-01-01 --end 2026-07-31 \
  --output /tmp/stock-replay \
  --user-agent 'your-project/1.0 contact: you@example.com'
```

SEC filing events are a dated primary event layer, not a complete historical
provider news feed. FRED DFF is a dated Fed-funds series, not a complete macro
dataset. These limitations are recorded in `manifest.json` and are enforced by
the external validation gate. A custom news replay must explicitly declare
`manifest.news.source.kind: provider_versioned` to satisfy that gate; an
ambiguous or SEC-only replay remains blocked.

Before treating a provider-backed score as externally validated, run:

```bash
stock-analysis-backtest --mode external-validate \
  --session-dir /tmp/stock-session \
  --score-report /tmp/stock-session/score.json
```

The gate checks packet pairing, complete scored coverage of the frozen panel,
a survivorship-safe universe artifact, externally calibrated costs, effective
sample size, and a strict long-hold win.
Provider metadata is currently self-declared: even a well-formed
`provider_run.json` remains `BLOCKED` until a real invocation is bound to the
exact predictions and scored result. Missing artifacts return `BLOCKED`;
observed mismatches return `FAIL`.

`universe.json` uses schema version 1. It must record the source URL and
extract hash, a frozen selection policy, the exact session tickers, and one
`membership_records` row per `(ticker, as_of_date)` trial with a stable
`security_id` and `member: true`. `membership_records_sha256` is the SHA-256 of
the compact, key-sorted JSON encoding of that array. Its `return_treatment`
object must identify a hashed total-return source, include distributions,
delisting returns, and merger consideration, and set
`missing_return_policy: "fail_closed"`. The scored JSON must carry the exact
same object at `result.settings.terminal_return_provenance`; otherwise the
terminal-return provenance gate fails. The current yfinance-backed scorer does
not yet emit this provenance, so a universe metadata file alone cannot make a
run pass.

The portfolio table reports each strategy's excess return versus the strict
equal-weight `buy_and_hold` benchmark: one position per ticker from its first
available entry to its last available exit. `rolling_long` is retained as a
diagnostic baseline for the older rolling-entry semantics. A strategy is not
promotion-ready merely because it ranks first on Sharpe: the benchmark gate
requires an observed benchmark win, portfolio effective sample size of at
least 30, and a deflated Sharpe of at least 95%. The effective-sample contract
is `portfolio_overlap_clustered_v1`: same-date securities share one dependence
cluster and overlapping holding windows are discounted. The external validator
requires this marker on the `overall` portfolio row; legacy scores without it
are blocked, even if their ticker-level `effective_n` is large.

`session-score` also appends a separate sealed-trial cross-sectional allocation
section and `cross_sectional_trial_allocation` JSON field. It ranks the fixed
universe by trailing price return using only data available at each as-of date,
then applies the selected tickers' sealed forward outcomes. This deterministic
layer is reported for comparison, but it does not alter the AI signal rows or
the promotion gate; a missing price history fails that section closed.

When synchronized AI predictions are available, the same output adds an
`AI Signal Ablation` section and `signal_ablation` JSON field. It reports an
AI-only long sleeve and an AI-positive filter over the fixed momentum basket,
both against exposure-matched references. A conditional permutation test
reassigns positive AI labels within each momentum basket while preserving the
period, basket, and positive-label count. These are attribution diagnostics;
they do not change the pipeline signal or promotion gate. Scored `api` and
`session-score` arms are recorded prospectively in an append-only
`backtest_experiments.jsonl` ledger in the current directory (override with
`--experiment-ledger`) with config/input fingerprints, headline and per-arm
metrics, and cumulative unique-config and scored-evaluation counts. Those
counts are audit metadata only; no cross-run DSR correction is applied.
Pre-ledger or manually explored candidates are not reconstructed.
The ablation's drawdown uses sealed-window endpoints only; it does not capture
losses inside a holding window.

## Prospective watchlist validation

The 2026-10-07 cohort is frozen under `reports/analysis/2026-10-07-forward-cohort/`: all31 current forecasts, next eligible open on/after2026-10-08, exit close on/after2026-11-06. Scoring is blocked before2026-11-07UTC so the US exit session has closed. US and MY use separate local-currency portfolios; costs and2× stress are frozen assumptions. No orders or outcome-memory writes occur. One cohort is one date cluster, not proof of statistical edge.

```bash
python -m stock_analysis.backtest.prospective verify --cohort reports/analysis/2026-10-07-forward-cohort
# On/after2026-11-07UTC:
python -m stock_analysis.backtest.prospective score --cohort reports/analysis/2026-10-07-forward-cohort
```

Hit-rate and IC intervals now use their respective portfolio-clustered effective counts. Wilson intervals preserve the observed hit fraction and apply an effective-n design-effect approximation; Fisher intervals use all completed dated windows, including neutral forecasts, and are unavailable below effective n4. These are approximate intervals, not exact coverage guarantees for correlated observations. Legacy report fields load with uncertainty method unspecified; rescore to obtain the new method metadata.

## Input isolation and evidence policy

Cloud workers seal the complete typed input and cutoff before analyst work.
Retries load that input and require matching stage SHA-256 hashes. Partial legacy
runs without an input seal fail closed; completed legacy outputs remain readable.
Apply `supabase/migrations/20261008000000_immutable_run_inputs.sql` before deploying
these worker changes. Raw seals are service-only and immutable while the run exists.

Live US/MY fetches retain quarterly history (annual fallback), statement currency,
and a separately requested plain Close. Balance and cash-flow columns must match
the income fiscal end and frequency. Provider observations are dated at capture;
they do not establish original filing vintages or a common EPS/ADR share basis.
Those unknowns stay unavailable. `STOCK_EVIDENCE_REPLAY_DIR` optionally overlays
dated statement, valuation, news and macro evidence before the seal is written.
Macro is unavailable when no dated source is configured.

`ANALYSIS_NEWS_MAX_AGE_DAYS` defaults to 30 days, measured relative to the analysis
cutoff. Archived facts are retained; stale headlines do not enter sentiment.
Explicit issuer financial-result releases do not provide independent sentiment
confirmation. Income and its derived margins count as one confidence dimension.
Session manifest version 5 records the execution-contract change: session and API
backtests require the same valid risk plan, and gated neutral execution carries
zero conviction. Raw model scores remain available for attribution. Existing sealed
packets, scored reports and forward forecasts are never rewritten by these fixes.
