# Latest-code backtest review — 2026-10-07

[Status: OK] Corrected score behavior is reproducible. [Status: Critical] This result cannot be cited as evidence of a reliable trading edge. Numerical promotion and external validation both FAIL.

## What was rerun

The latest working-tree implementation was executed through `rescore --recalibrate-session` on all 96 previously sealed forecasts/outcomes: AVGO, NVDA, MSFT, TSM, V, UNH, ORCL and COST, 12 dates from 2025-09-01 through 2026-07-28, 30-day horizon, 365-day lookback. Costs were rerun at 10 and 20 bps per side. No sample, forecast, threshold, entry, exit, outcome or daily price path was changed, and no API/model invocation or live price refetch occurred.

This is an implementation replay of already observed historical outcomes, not a new blind forecast experiment or a full production-provider pipeline replay. Working-tree source hashes are recorded in `run-provenance.json`. The original 107 sealed files remain unchanged. All 96 calibrated signals, scores and convergence values agree with the previous corrected result.

## Results

| Long-only arm | Final signals | Long trades | Net total return | Strict equal-weight hold | Excess vs hold |
| --- | --- | ---: | ---: | ---: | ---: |
| Latest rules, 10 bps/side | 93 neutral / 3 sell / 0 buy | 0 | 0.00% | +20.66% | -20.66 pp |
| Latest rules, 20 bps/side | 93 neutral / 3 sell / 0 buy | 0 | 0.00% | +20.46% | -20.46 pp |

No trades means no Sharpe/DSR or trade-effective sample for the primary portfolio. Zero drawdown is the mechanical consequence of zero deployment, not demonstrated risk control. The 10-bps paired 95% time-block interval for mean daily log excess is [-0.002122, +0.001163], spanning zero; it is not a CI for total-return percentage points. The nine portfolio comparison views remain counted in selection-bias corrections; all runs remain in the append-only experiment ledger, whose cross-run counts do not themselves constitute a cross-run DSR correction.

## Directional forecasts and gate review

Only three sell forecasts remain, all on ORCL:

| Forecast date | Subsequent underlying return | Sell direction correct? |
| --- | ---: | --- |
| 2025-11-30 | -1.64% | Yes |
| 2026-01-29 | -11.25% | Yes |
| 2026-03-30 | +17.18% | No |

The observed directional hit rate is 66.67%, with approximate effective-n Wilson 95% CI [20.77%, 93.85%]. Effective n is 3.0; the interval spans 50%. One large wrong direction outweighs the two correct ones: mean gross hypothetical short-direction return is -1.43%. These are predictions, not short trades in the long-only portfolio, and all observations are concentrated in one issuer.

Conviction/return IC is -0.070; approximate effective-n Fisher 95% CI [-0.943, +0.926], spanning zero. IC effective n is 4.33 across the completed dated windows. The updated intervals correctly avoid treating 96 concurrent/overlapping ticker trials as 96 independent observations.

All ten raw synthesized buys have convergence at most 0.3333 (two at 0.25), below the production 0.40 execution gate. Several additionally have conviction at/below 0.30. The four-role denominator and `min(raw model magnitude, consensus magnitude)` cap are shared with production; conviction is no longer raised by consensus. No threshold was lowered to force positions. This panel is therefore primarily testing abstention under insufficient corroboration, not demonstrating the efficacy of the full pipeline on complete inputs.

## Quant review findings

- [Status: OK] `session.py::calibrate_session_prediction` uses the canonical production weights, denominator, signed score cap and real actionability gate. Raw conviction is retained and unavailable sources remain neutral/low. The complete trial grid and point-in-time packet clocks are checked.
- [Status: OK] `scorer.py::_compute_partition` applies the correct directional/all-completed effective counts to the approximate Wilson/Fisher intervals. Full-sample warnings are surfaced. `portfolio.py` counts all comparison strategies and retains the strict-hold, doubled-cost and paired interval gates.
- [Status: Warning] Point-in-time input coverage is technical96/96, fundamentals55/96, sentiment0/96, macro96/96 with only one DFF rate observation. Macro clock validation is not proof of complete macro evidence; current-provider historical financial values may be restated.
- [Status: Critical] Neither execution nor forecast skill is established: zero primary trades, three issuer-concentrated directional forecasts, null-spanning intervals, and failed promotion gates. The standalone technical comparison also does not rescue the AI pipeline: its observed net return is -5.91% at10bps, with effective n7 and DSR1.65%; it remains exploratory, not an alternative selected for deployment.
- [Status: Warning] Historical universe selection uses current survivors; exact session model training cutoff is unknown; batch analysts could see later snapshots and model historical knowledge cannot be excluded. Authenticated provider, historical news, survivorship-safe universe, terminal-return provenance and calibrated cost authority gates remain BLOCKED. A same-outcome rerun does not cure those gaps.

Review conclusion: the scoring repair is working, but pipeline reliability is **not established**. This result does not show that every live forecast is wrong; it shows that the present historical evidence cannot validate a trading edge. The latest31 live forecasts remain independently sealed for prospective evaluation after the2026-11-06 exit session (not before2026-11-07UTC).

## Verification and artifacts

- Entire repository tests rerun:276 passed,4 subtests passed; one existing dependency deprecation warning. Scoped Ruff checks passed.
- Original107 sealed hashes verified;96 outcomes unchanged in both reruns; latest code hashes verified; append-only ledger chain verified.
- The31-name prospective cohort verified without scoring its immature outcomes.
- [10-bps full report](10bps.md), [20-bps full report](20bps.md), [external validation](external-10bps.md), and machine-readable `review.json` retain the evidence.
