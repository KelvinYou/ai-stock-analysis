# Fixed momentum allocator reliability check — 2026-10-09

[Status: Warning] Observed historical wins do not establish reliable excess return.

## Protocol

The existing eight-name pilot universe is primary; previously inspected eleven- and five-name universes are sensitivity checks. Rule stays trailing 12-month return, top three, equal-weight, monthly decisions and next-common-session Open fills. No AI filter. Signal dates: January 2018 through August 14, 2026; price snapshots capped September 17, 2026. Strict hold uses the exact first entry and final exit. Primary assumed cost is 10bps per side; 20/50bps are stress assumptions, not broker calibration. Idle cash has no yield. Daily-close marks measure drawdown. These continuous monthly tests differ from the earlier nine sealed episodes; do not mix their returns.

## Full-period results at 10bps

| Universe | Periods | Allocator net | Strict hold | Allocator max DD | Hold max DD | 95% paired monthly log-excess CI |
|---|---:|---:|---:|---:|---:|---|
| primary8 | 103 | 1292.42% | 982.45% | -35.53% | -34.73% | [-0.00255, 0.00908] |
| prior11 | 103 | 2156.49% | 933.07% | -41.54% | -47.99% | [-0.00028, 0.01686] |
| prior5 | 103 | 784.37% | 1096.70% | -49.30% | -42.28% | [-0.00680, 0.00197] |

All twelve paired intervals span zero. Intervals refer to mean monthly log excess, not cumulative-return percentage-point differences. Effective N=103 for full runs is a descriptive temporal count, not 103 independent market regimes. The bootstrap uses three-month blocks and 2,000 resamples; it does not account for all earlier universe/strategy searches. No cross-run DSR pass is claimed.

## Primary eight-name slices

| Signal-date slice | Periods | Allocator net | Strict hold |
|---|---:|---:|---:|
| early: 2018-01-01–2023-12-31 | 72 | 436.59% | 338.27% |
| middle: 2024-01-01–2025-12-31 | 24 | 127.39% | 82.27% |
| recent: 2026-01-01–2026-08-14 | 7 | 13.67% | 14.14% |

At 50bps per side primary full-period allocator return remains +1194.88%, versus hold +973.80%; its excess interval still spans zero. Costs alone do not explain the uncertainty. The five-name rule loses at every tested cost, revealing universe sensitivity; this does not isolate the causal contribution of particular names. The recent primary slice also loses, and 2024–2025 primary drawdown is -35.53% versus hold -24.68%.

## Verdict and verification

[Status: OK] Accounting/implementation checks: 12 existing cross-sectional tests passed, including trailing-only ranking, next-common-open execution, same-window strict benchmark/costs, daily reporting, and sealed-window overlap guards. All 12 run artifacts were completed; source hashes unchanged; net returns decrease with higher fees in each full-panel cost sweep. These checks establish implementation consistency, not investment efficacy.

[Status: Warning] Statistical/generalization verdict: reliability unproven. Fixed current-survivor universes, previously inspected history, unverified dividend/distribution/terminal-return treatment and assumed execution costs prevent a clean prospective or total-return claim. The model field named oos_start denotes evaluation start here, not an unseen holdout. No forecasts, price refreshes, parameter optimization, purchases or deployment occurred.

Protocol, raw reports, ledger and summary are preserved alongside this report. Capped price snapshots and the runnable harness are in /private/tmp/momentum-reliability-20261009; protocol source hashes identify local source files. Future evidence requires frozen investable membership, validated returns/costs and unseen outcomes, not picking the best of these panels.


## Follow-up evidence

- [Return concentration](concentration.md): exact log-excess reconciliation and best-month sensitivity.
- [Forward preparation](forward-preparation/README.md): original v2 rules preserved, calendar draft and explicit activation blockers.
- [Return/cost audit](return-and-cost-audit.md): separate current-provider actions capture; broker-specific costs still awaiting input.
