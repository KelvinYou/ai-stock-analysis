# Forward validation preparation — 2026-10-09

[Status: Warning] Existing v2 rules preserved; collection is not activated.

The immutable original protocol copy and its SHA-256 retain all 36 anchors,
eight stocks, nine arms, 12-month/Top-3 rule and 0/10/20bps cost assumptions.
The 35-day episode calendar is separate from continuous monthly historical
rebalancing; its results cannot silently validate a different schedule.

The nine-arm collector now exists and its 13 focused tests passed, including
clock, unavailable-history, protocol identity, immaturity and holiday cases.
The earlier specification's absent-collector statement is historical; current
implementation evidence is in ../2026-10-09-portfolio-pipeline-upgrade/README.md
relative to the analysis directory. Readiness is checked against actual code.

NYSE's [official calendar](https://www.nyse.com/trade/hours-calendars) publishes
2026–2028 holidays. Draft decision mapping is recorded for those years only;
2029–2030 remain unavailable. This mapping is not a full common-exchange or
exceptional-closure contract. No schedule has been fabricated to pass activation.

First proposed anchor is October 12, 2026. Inputs/forecasts must be captured
after the actual decision session closes and sealed before next session Open.
No present or historical bundle is substituted for future October 12 inputs.
If that cutoff is missed, prepare a new future protocol version; never backdate.

Actual model/provider and prompt/tool identity, complete calendar mapping and
same-session inputs remain activation blockers. Source-complete returns,
calibrated costs and mature unseen samples remain promotion blockers.

Run after satisfying those blockers, from the child root:

```sh
.venv/bin/python -m stock_analysis.portfolio_cohort freeze --bundle /path/to/same-session-bundle.json --protocol /path/to/activation-complete-v2.json --cohort /path/to/new-cohort
```

This preparation does not run model calls, create a forecast seal, schedule
automation, buy securities or claim an activated forward cohort.
