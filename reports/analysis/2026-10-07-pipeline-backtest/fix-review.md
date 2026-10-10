# Scoring contract repair — 2026-10-07

[Status: OK] Implementation contracts and regression checks pass. [Status: Warning] Historical efficacy remains unproven and prospective outcomes remain pending.

## Scope and impact matrix

| Contract | Owner | Consumers | Compatibility/version | Verification |
| --- | --- | --- | --- | --- |
| Four-role consensus/convergence | `synthesis/synthesizer.py::weighted_directional_totals` | Production typed reports; session consensus/convergence wrappers | Production numerical behavior preserved; session availability argument retained but no longer removes roles | Production signal-quality tests; unavailable-only technical regression |
| Conviction cap | `synthesis/synthesizer.py::calibrate_conviction_score` | Production synthesis; guarded session predictions | Session manifest v4; raw score retained; old manifests readable | Weak 0.20 conviction stays below execution gate |
| Frozen-result recalibration | `backtest/session.py::recalibrate_session_result` | CLI `rescore --recalibrate-session` | Explicit opt-in; requires complete exact panel and matching horizon; existing outcomes/paths preserved | 96 unchanged outcomes and exact match to predeclared production-parity arm |
| Uncertainty | `backtest/stats.py`; `scorer.py` | Markdown, scored JSON, ledger and external validation | Additive optional `ic_effective_n`, `uncertainty_method`; legacy records remain readable | Same-date eightfold duplication does not narrow Wilson/Fisher intervals |
| Raw conviction trace | `SessionPrediction` calibration; `BacktestTrial` | Scored JSON and immutable result provenance | Optional raw score on historical trial records | Raw score retained after evidence/actionability guards |
| Prospective cohort | `backtest/prospective.py` | Freeze/verify/score CLI and report artifacts | Separate v1 cohort manifest; frozen forecasts unaffected by scoring repairs | Changed prediction rejection; no premature fetch; backdated freeze rejection; actual 31-row verification |

No Personal-OS finance schema, personal threshold, holdings, web report contract, database schema or Supabase research result changes are included. Public artifacts contain tracked market research, not private account data. Historical audit files are preserved; the repaired result is written separately as `fixed-10bps.json` / `fixed-10bps.md`.

## Behavior changes

Unavailable analysts are guarded to neutral/low and stay in the production four-role denominator. Conviction is capped by the model's own magnitude and net consensus, rather than being replaced by consensus. The shared totals function prevents independent weight implementations from drifting. Existing public function entry points remain available.

Wilson uncertainty retains the observed hit fraction while using portfolio date-clustered effective n as a design-effect approximation. IC Fisher uncertainty uses effective n from **all completed dated windows**, including neutral forecasts; it is unavailable below four effective observations. Both intervals are explicitly approximate. Missing exit clocks do not silently fall back to the nominal trial count. The full-report small-sample warning is now surfaced even without a model-training-cutoff partition.

The old ledger integration-test fixture used dictionaries where the report writer consumes typed `.strategy` attributes. Its fixture now uses typed attribute objects, allowing the existing ledger integration assertions to run. No runtime writer fallback was added.

## Validation

- Entire stock-analysis test suite: 276 passed; 4 subtests passed. One existing dependency deprecation warning.
- Ruff checks on the changed implementation/new regression files: passed.
- 96 frozen model predictions unchanged; 96 exact entry/exit/realized outcome records unchanged.
- All 96 repaired signal/conviction/convergence values match the predeclared production-score parity arm.
- Original 107 sealed files retain their original hashes.
- Repaired historical long-only portfolio: no buy passes the gate; zero long trades. This is abstention, not successful forecasting or risk control.
- Actual prospective cohort integrity verification: 31 forecasts; 7 buy, 22 neutral, 2 sell.
- Actual prospective score attempt: rejected before price reads as not mature until 2026-11-07 UTC.

## Decision

GO for the implementation repair and frozen research cohort. BLOCKED for claims of a reliable trading edge: historical news/vintage data/provider/universe/cost provenance and model-hindsight risks remain unresolved; the repaired portfolio has no long trades; future outcomes are not yet available. No forecast or threshold was tuned after seeing historical performance.

Commands and immutable forward protocol are in [the cohort README](../2026-10-07-forward-cohort/README.md). Machine-readable repair checks are in `fix-verification.json`.
