# Momentum strategy curve acceptance

[Status: OK] Descriptive point-in-time reconstruction is suitable for display. Local only, not committed/deployed.
[Status: Warning] This gross curve is not evidence of cost-adjusted alpha or real account returns. Fixed current universe, reconstructed historical choices, short display window and no independent statistical promotion evidence.

| Contract | Owner | Consumers | Compatibility | Verification |
|---|---|---|---|---|
| Daily portfolio valuation and turnover | daily_portfolio.py | existing backtest wrappers, momentum path | Default end remains last target; dashboard supplies explicit latest end | Existing cross-sectional tests; independent overnight/next-open fixture |
| Historical baskets | momentum_path.py + canonical current ranker | optional v1 context momentum_curve | Unavailable without full warm-up/opens/decisions | Future winner invariance; next-open gap case; no current-winner backfill |
| Gross chart | Python normalized levels | recursive TS validator, five-line React chart | Missing new field stays explicit | NaN/basis/rebalance corruption checks, aligned dates, initial 100 |
| AI-free scheduled refresh | 18-month price fetch and leaf valuation owner | existing minimal-dependency workflow | No new AI requirement | Subprocess rejects all AI/backtest runtime imports and still imports dashboard |

46 relevant Python tests passed, including existing cross-sectional backtests, arithmetic, freshness and new path cases. Child typecheck and runtime contract passed. Parent make design-check and make test passed (two pre-existing contrast warnings). Real Chrome 320/390/1440 light/dark verified five SVG paths, thicker first Momentum path, Momentum/VOO visibility controls, bounded page width and disclosures. Refresh/error/recovery/expiry and exchange-close-boundary replays passed. Mobile comparison visually reviewed; desktop dark comparison captured. No production deployment was tested.

Window: August 5–November 5, 2026, 66 common daily closes. Initial month-end decision July 31 executes August 3, followed by September 1, October 1 and November 2 rebalances. All five lines share closing-date normalization and exclude trading fees. The strategy line reuses historical selections and opening prices; it is not current top-three stocks held backward. Raw eighteen-month candidate inputs and reference inputs are preserved in prices/. Replay is under ui/check-browser.cjs; source hashes identify the uncommitted verification version.
