# Standalone momentum page acceptance — 2026-10-27

[Status: OK] Local implementation and browser acceptance passed.
[Status: Warning] Remote schedule and production URL are not activated: changes
have not been committed/pushed or deployed.

## User-visible outcome

`/momentum` has a dedicated navigation entry and shows two separate views:

- Monthly model: 2026-09-30 decision prices, TSM/NVDA/UNH, one-third each.
- Daily preview: 2026-10-26 prices, TSM/V/UNH, one-third each if that preview
  were the final decision. A daily change is not a mid-month order instruction.

All model weights are within a separate research sleeve; they are not actual
holdings or personal sizing. AI ratings do not filter either view. The page
links back to historical uncertainty and retains reliability unconfirmed.

## AI-free calculation and automation

`config/momentum.json` owns the eight-stock, 12-month/top-three rule.
`scripts/refresh_momentum_dashboard.py` downloads a 15-month adjusted OHLCV
panel, applies the existing bar-sanitization gate, and calculates both views.
It can reproduce offline using `--prices-dir`. No model calls, AI keys, database,
broker credentials or private finance data are used.

The real network downloader completed locally. The published snapshot is
`web/data/momentum.json` with its companion SHA-256. Failed or incomplete
refreshes leave the previous pair unchanged; stale/invalid pairs hide targets.

The new GitHub workflow is scheduled daily at 01:15 UTC / 09:15 Malaysia,
including weekends so month rollover is ready before Monday. It installs only
pandas, pydantic and yfinance and commits only the two public snapshot files.
Production reads the public main-branch pair with a 60-second application cache;
it does not require a daily deployment. Local development reads local files.

GitHub scheduled workflows must exist on the default branch, and scheduled
starts may be delayed. Bot pushes using `GITHUB_TOKEN` do not trigger another
Actions push workflow, which is why the page reads the public artifact directly.
See [GitHub event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
and [token-trigger behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
Production delivery remains an operational acceptance item after publication.
This automation produces research weights; brokerage execution is separate.

## Contract review

| Owner → consumer | Acceptance |
|---|---|
| Fixed config → Python dashboard builder | Complete universe required; rule IDs and settings explicit |
| Shared ranking function → daily and monthly wrappers | Daily trailing-date anchor and monthly prior-year month-end anchor are distinct and tested |
| Month-end input slice → monthly targets | Later daily prices cannot change the already completed-month ranking |
| Public JSON/hash → TS validator and loader | Full coverage, rank order, weights, cycle month and integrity verified |
| Snapshot dates → page | Four-day freshness and current-cycle checks; stale weights suppressed |
| Optional analysis navigation → root layout | An unavailable analysis backend degrades navigation without blocking the momentum page |
| Schedule → public snapshot → production reader | Configured locally; activation and remote delivery unverified until main publication |

No historical reports or AI signal rules were rewritten. The existing Allocation
view continues to pass its runtime contract and browser regression. The new
monthly-anchor option leaves the earlier daily-preview default unchanged.

The monthly date edge was tested with October 30 versus October 31: the backtest
uses last common closes in corresponding calendar months, not necessarily the
same day number. A failing test exposed and then verified the corrected anchor.
The future-clock browser check also exposed a hydration mismatch; the component
now hydrates the server's verified state first and rechecks client freshness in
an effect, once per minute thereafter. The same acceptance then passed without
page JavaScript errors.

## Verification

- 105 focused Python tests plus four subtests passed.
- Full `ruff check src tests scripts` passed.
- Web TypeScript, `check:momentum` and `check:allocation` passed.
- Real browser: dedicated route, monthly and daily baskets, desktop/390px mobile,
  no whole-page overflow, stale target suppression, and Allocation tab regression.
- The browser server deliberately pointed its analysis API at an unavailable
  endpoint. `/momentum` and `/allocation` still returned 200. Existing dynamic
  favicon fallback returned 500 in this outage fixture; the page had no JS errors.
- Desktop and mobile screenshots are in this folder. Normal server configuration
  was restored after the outage acceptance.

Reproduce the data from the child root:

```sh
.venv/bin/python scripts/refresh_momentum_dashboard.py
.venv/bin/python -m pytest tests/test_momentum_dashboard.py tests/test_current_momentum.py tests/test_allocation_export.py tests/test_cross_sectional.py tests/test_backtest_stats.py tests/test_portfolio_pipeline.py -q
cd web
npm run check:momentum
npm run check:allocation
npm run typecheck
```

Known non-blocking environment warnings: existing Starlette/httpx deprecation
and outdated Browserslist data. No deployment, Git mutation or brokerage action
was performed in this session.
