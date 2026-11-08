# Momentum Risk Overlay — Draft

Status: **draft, not approved**. Research only; no change to the published
momentum rule (`momentum-9-12m-top3-v2`).

## Problem

The 2026-10-30 basket (TSM, V, UNH) returned -5.08% gross through 2026-11-05
against -3.46% for VOO. TSM alone accounted for about -4.4pp. The last six
monthly baskets repeated semiconductor and AI-complex names (TSM, GOOGL, NVDA,
AVGO), so the loss was one theme, not three independent bets.

## Evidence (exploratory backtest, not validated)

Setup: 9-stock universe, 12m momentum, month-end decision, next-session open
entry, adjusted prices, 2018-01 onward, 106 months, **no trading costs**.
Universe is chosen today, so survivorship bias applies.

| Rule | CAGR | Max DD | Worst month |
|---|---|---|---|
| Base top-3 | 34.8% | -27.7% | -15.4% |
| Vol skip (20d vol > 1.5x own 1y median → cash) | 32.9% | -20.1% | -15.4% |
| AI complex max 2 | 30.8% | -24.9% | -13.5% |
| Combo (AI max 2 + vol skip) | 28.2% | -15.4% | -13.3% |

Split-sample check (CAGR / max DD):

| Window | Base | Vol skip | AI max 2 | Combo |
|---|---|---|---|---|
| 2018–2022 | 21.5% / -27.7% | 24.4% / -15.4% | 19.1% / -24.9% | 20.1% / -15.4% |
| 2023–2026 | 54.4% / -24.4% | 44.9% / -20.1% | 47.8% / -17.2% | 39.7% / -13.7% |

Reading: vol skip cut drawdown in both windows; its CAGR cost was negative in
2018–2022 and about -9.5pp in 2023–2026. Other rules tested and rejected:
3m>0 filter (CAGR -10pp, no drawdown gain), 1m>0 filter (CAGR roughly halved),
top-5 (lower CAGR, deeper drawdown), semis max 1 (CAGR -12pp).

## Realized shadow results

Source: `scripts/momentum_shadow.py --score` (gross, next-session open to the
following month-end close, cash earns 0). Append one block per closed cycle.

| Decision | Status | Base | AI max 2 | Vol skip | Combo | Note |
|---|---|---|---|---|---|---|
| 2026-10-30 | open, to 2026-11-05 | -5.08% | -5.08% | -5.08% | -5.08% | All variants picked TSM, V, UNH; TSM 20d vol was 1.35x its 1y median, below the 1.5x trigger |

The first cycle with different baskets is the first informative data point.
Closed cycles replace the `open` row on the first run after month-end.

## Caveats

- Several rules were tried; the best-looking one is an order statistic.
  Differences of a few pp are not evidence. Apply the Deflated Sharpe bar from
  `backtest/stats.py` before any claim of improvement.
- The 2018–2026 sample has few independent regimes; drawdown estimates rest on
  a handful of episodes.
- The AI-complex grouping is a manual judgement (AVGO, NVDA, TSM, ORCL, MSFT,
  GOOGL), not a derived sector classification.
- `momentum_dashboard.build_momentum_dashboard` rejects `top_n != 3` and any
  changed universe. Any overlay needs code and contract changes, plus
  dashboard copy changes ("fixed-rule portfolio").

## Plan

1. **Shadow phase (now):** `scripts/momentum_shadow.py` appends each month-end
   basket for `base`, `ai_cap2`, `vol_skip`, `combo` to
   `reports/momentum_shadow/picks.jsonl`. Idempotent per decision date. No
   dashboard or config changes.
2. **Review (earliest 2027-03):** compare realized next-cycle returns of the
   four variants. Four to five cycles is a sanity check, not validation.
3. **Decision gate:** promote an overlay only if it holds up on
   out-of-sample months and clears the Deflated Sharpe bar. Otherwise keep the
   fixed rule and document the concentration risk on the page.
4. **If promoted:** new strategy id (`momentum-9-12m-top3-v3`), new tests in
   `tests/test_momentum_*.py`, updated dashboard disclosures, and a note in
   `docs/DECISIONS.md` in the parent repo.

## Non-goals

- No change to universe, lookback, or execution convention.
- No live orders or holdings linkage.
