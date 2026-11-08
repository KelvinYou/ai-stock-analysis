# Momentum reference acceptance

[Status: OK] Local only; original nine-stock selection is unchanged.

| Contract | Owner | Consumer | Compatibility | Evidence |
|---|---|---|---|---|
| Price metrics, references, cycle and rank history | momentum_context.py | recursive TS context validator, momentum desk | Optional dashboard-v1 context; missing means unavailable | 25 focused Python tests; invalid/missing-reference and future-row cases |
| Reference protocol and fee scenario | config/momentum.json | Python only | SPY remains outside candidate universe; 20 bps/side is illustrative | Gross versus explicit entry/liquidation scenario, independent fixture arithmetic |
| Price/reference provenance | Refresh CLI and Python allowlist | runtime validator and collapsed disclosures | Old provenance/context may be absent; no guessed provider | Supplemented dates must survive sanitation; invalid dates/fields/URLs rejected |
| Snapshot GET and refresh | Existing verified loader, no-store route, client hook | momentum page | Existing hashes, expiry and daily/monthly separation retained | Real HTTP 200/no-store; route 503 check; real-browser mocked refresh/recovery/expiry |
| Public boundary | Explicit public snapshot fields | Public web | No holding quantities, cost bases or private finance paths | Changed source and emitted JSON inspected |

Passed: child typecheck, runtime contract/corruption checks, 25 focused Python tests, Ruff, parent make design-check and make test. Parent design check reports two pre-existing chart contrast warnings. Real Chrome: 320/390/1440 light/dark; no document horizontal overflow; month basket near top; all sections; disclosure interaction. Settled 390px top and desktop dark market chart visually reviewed. Keyboard Enter toggles disclosure; refresh target >=44px.

Refresh replay passed: valid newer snapshot replaces server props, 503 retains verified data and shows error, malformed payload rejected, older generation cannot overwrite data, 60-second polling recovers, and expiry hides weights on failed refresh. A pure contract check also rejects a newly captured snapshot with an older price session.

Replay check-browser.cjs with PLAYWRIGHT_MODULE pointing to an installed @playwright/test and MOMENTUM_BASE_URL for the running app. It uses real Chrome and mocks only refresh responses; it does not alter disk data. Verification file hashes and base HEAD are in verification-version.json. Current runtime code remains uncommitted. No production deployment, broker integration, full nine-name backtest or automatic secondary provider fallback was performed.
