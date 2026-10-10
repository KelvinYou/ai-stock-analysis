import json,hashlib
from pathlib import Path
from collections import Counter
from stock_analysis.backtest.external_validation import validate_session_bundle
R=Path('reports/analysis/2026-10-07-pipeline-backtest');S=R/'session'
seal=json.loads((R/'seal.json').read_text());assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in seal['files'].items())
base=json.loads((R/'session-10bps.json').read_text());stress=json.loads((R/'session-20bps.json').read_text());parity=json.loads((R/'production-parity-10bps.json').read_text())
for p in [stress,parity]:
 assert len(p['result']['trials'])==96
 for a,b in zip(base['result']['trials'],p['result']['trials'],strict=True):
  assert all(a[k]==b[k] for k in ['ticker','as_of_date','entry_price','entry_date','exit_price','exit_date','realized_return'])
ledger=[json.loads(s) for s in (R/'experiments.jsonl').read_text().splitlines() if s.strip()]
assert len(ledger)==3 and [x['ledger']['sequence'] for x in ledger]==[1,2,3]
validation=validate_session_bundle(S,score_report=R/'session-10bps.json');(R/'external-validation.json').write_text(json.dumps(validation.as_dict(),indent=2)+'\n')
verify=json.loads((R/'verification.json').read_text());verify.update(sealed_files_unchanged=len(seal['files']),scored_trials_complete=96,arms_with_identical_outcomes=3,experiment_ledger_rows=3,external_validation=validation.status)
(R/'verification.json').write_text(json.dumps(verify,indent=2)+'\n')
readme=(R/'README.md').read_text().replace('[Status: Warning] Exploratory diagnostic. Prediction preparation is in progress; this is not a completed performance verdict yet.','[Status: Critical] Completed exploratory diagnostic. Reliability is not established: the numerical promotion gate and external validation both FAIL. Partial historical evidence, current-session hindsight risk, and production/backtest contract differences prevent a production-pipeline efficacy claim.')
readme=readme.replace('Scored reports and external validation will be linked after completion.','Scored artifacts: [normal session 10 bps](session-10bps.md), [20 bps stress](session-20bps.md), [production-score parity arm](production-parity-10bps.md), and [external validation](external-validation.md). `comparison.json` and `verification.json` retain the machine-readable summary and verification.')
readme += '''
## Completed results

All 96 frozen trials have outcomes; no sample was dropped. Forecasts were hashed before the explicit forward-scoring price fetch and were unchanged afterward. This seal does not cure model-memory or cross-packet contamination. Raw synthesis: 10 buy, 25 sell, 61 neutral. Official session gates leave 9 buy, 25 sell, 62 neutral. The production-score parity arm leaves 3 sell, 93 neutral; no buy clears the production consensus/convergence/score gate.

| Long-only portfolio arm | Net total return | Strict hold | Excess vs strict hold | Executed long trades | Portfolio effective n |
| --- | ---: | ---: | ---: | ---: | ---: |
| Official session, 10 bps/side | +3.75% | +20.66% | -16.91 pp | 9 | 6.0 |
| Same sealed forecasts, 20 bps/side | +3.57% | +20.46% | -16.90 pp | 9 | 6.0 |
| Production-score parity, 10 bps/side | 0.00% | +20.66% | -20.66 pp | 0 | unavailable |

These are observed point estimates, not expected returns. The official session arm's 95% paired moving-block interval for **mean daily log excess** against strict hold is [-0.001985, +0.001323], spanning zero. It is not a confidence interval for the displayed total-return percentage-point difference. Overall DSR is 52.56%, below the 95% promotion threshold; each portfolio comparison counts nine strategies. The isolated ledger contains three runs / 36 counted configs/evaluations across portfolio, allocator and ablation families; cross-run DSR correction is not applied, and earlier searches are not reconstructed.

### Capital exposure and positive exploratory diagnostics

The session pipeline commits only 7.49% of initial capital on an average session, versus 100% for strict hold. Its maximum drawdown is -2.97%, versus -19.25% for strict hold. This deployment difference is substantial: losing to fully invested hold does not by itself establish inferior security selection.

On the repository's matching-date, matching-dollar passive comparison, the observed session excess is +5.90 pp. That estimate is conditional on the strategy's own chosen dates and stakes; it is not a clean out-of-sample alpha claim. The separate AI-label ablation uses a deterministic non-overlap subset, 72/96 trials across nine periods. It reports a positive AI-filtered momentum paired interval [0.0129, 0.0280] for mean episode log excess and conditional label-permutation p=0.007. Only five periods are informative for that permutation. These are possible selection signals worth testing prospectively, not evidence sufficient to promote this incomplete historical replay. The subset does not replace the primary full-panel test.

The production-score parity arm takes no long position. Zero P&L and zero drawdown therefore show abstention; they cannot establish successful timing, calibrated risk control, or predictive accuracy. Its three sell predictions are not executed short trades.

### Statistical reporting issue found during review

The existing scorer applies date-clustered effective n to t-tests/PSR, but its hit-rate Wilson interval uses the nominal directional count and its IC Fisher interval uses the nominal completed count (`backtest/scorer.py::_compute_partition`). Therefore the normal report's directional hit-rate 58.82% / nominal 95% CI [42.22%, 73.63%] and IC -0.116 / nominal CI [-0.309, 0.087] must not be read as dependence-adjusted confidence intervals. The directional effective n is only 3.73. Even these nominal intervals span their null; wider dependence-aware uncertainty would not rescue a demonstrated edge. The portfolio time-block interval and effective-n/DSR gates remain the primary reviewed inference. No production/statistical code was edited in this task.

### Validation and limitations

External validation is **FAIL**, with provider run, historical news, survivorship-safe universe, terminal-return provenance and calibrated execution cost gates **BLOCKED**. Complete scoring and fail-closed metadata pass; the validator's macro source pass proves dated input clocks, not completeness of macro information. Financial/news coverage, effective sample and strict-hold alpha gates fail.

No dated cash-yield path was attached to the score, so uninvested cash earns zero in these primary price-return comparisons. FRED was used only as a forecasting macro observation. A cash-yield diagnostic would be a separate transparent comparison, not grounds to retroactively tune the frozen forecasts.

Verification: 384 typed analyst reports validated; factual RSI and missing-evidence guards passed; 107 sealed input/prediction/method files remained unchanged; all three arms use identical entries, exits and realized outcomes. Existing selected tests: 64 passed, 1 failed, 4 subtests passed. The failure is an existing integration-test mock mismatch: its strategy list uses dictionaries while the scored-report writer expects typed `.strategy` attributes. This test fixture was not changed.

## What would establish reliability next

1. Freeze current real forecasts before their future outcomes and evaluate a sequence of prospective cohorts, retaining all neutral predictions and an exposure-matched benchmark. Do not reselect names after outcomes.
2. Make session and production consensus/conviction/denominator contracts agree, then review statistical interval dependence handling before rerunning. Preserve the current reports as pre-fix diagnostic evidence.
3. Obtain versioned point-in-time news/fundamentals and a historical investable universe, calibrate costs, and accrue at least 30 portfolio-effective observations. A longer historical sample cannot resolve unknown model training contamination by itself.
'''
(R/'README.md').write_text(readme)
print('Completed report.107seal hashes unchanged;96complete outcomes identical across3arms;ledger3rows;external',validation.status)
