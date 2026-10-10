# Frozen forward cohort — 2026-10-07

[Status: Expected] Forecasts are frozen; future outcomes are not yet available.

All 31 forecasts from the corrected watchlist analysis are retained: 7 buy, 22 neutral, 2 sell. Their input bars end on 2026-10-06. Full briefing, analyst, debate, verdict and input snapshots are copied under `frozen/`; `manifest.json` binds their hashes and `predictions.json`. Existing cohort directories cannot be overwritten by the freeze command. `code-provenance.json` records the evaluation implementation before the first eligible entry.

- Entry: first eligible open on or after 2026-10-08.
- Exit: first eligible close on or after 2026-11-06.
- Scoring available from 2026-11-07 UTC, after the US exit session has closed. A missing market outcome blocks the entire score; the panel is never reduced.
- Separate US/USD and MY/MYR portfolios; no unsupported FX aggregation.
- USD/MYR 10,000 synthetic starting balances, 10% of pre-session cash per long signal. Neutral and sell allocate no new long position. No shorts, orders or outcome-memory writes.
- US costs: 10/20 bps per side; MY costs: 50/100 bps per side. These are frozen assumptions, not calibrated brokerage estimates.
- Benchmarks: strict equal-weight hold and the repository's same-date, same-dollar passive comparison.
- This measures a standardized market-open/close forecast policy. It does not simulate the original briefing's limit orders, stops, targets or actual holdings.
- One forecast date is only one portfolio cluster per market. Results will describe this cohort, not establish statistical reliability across time.

Verify the frozen forecasts now:

```bash
.venv/bin/python -m stock_analysis.backtest.prospective verify \
  --cohort reports/analysis/2026-10-07-forward-cohort
```

After 2026-11-07 UTC, score all forecasts:

```bash
.venv/bin/python -m stock_analysis.backtest.prospective score \
  --cohort reports/analysis/2026-10-07-forward-cohort
```

The scorer writes `score.json` and `score.md` only after all markets have complete outcomes. It refuses to replace an existing `score.json`. Retain future cohorts and repeated dates to accumulate independent evidence; do not discard neutral predictions or reselect names after outcomes.
