# Full watchlist pipeline — 14 September 2026

[Status: Warning] Research output, not trade execution. Re-verify prices after the next completed session and before acting.

## Execution

Scope: 33 tickers from `../../../tickers.txt`, plus SunCon (5263) and Tenaga (5347): 17 Malaysian and 18 US stocks.

Completed: 35/35. Failures: 0. Signals: buy=3, neutral=24, sell=8.

Mode: In-Session Codex. Refreshed real Layer1 data, four independent analyst perspectives, two sequential bull/bear rounds for each ticker, moderator, research-manager verdict, synthesis, and repository Pydantic/convergence/conviction/freshness/RiskChecker logic. This was not a separate Anthropic API run and not a backtest. No orders were placed. Artifacts were saved locally and subsequently synced to Supabase at the user's request. All35 completed runs,140 analysis artifacts, market snapshot dates/prices and35 latest summary entries were read back and verified. See `supabase-sync.json`. The cloud summary view lacks `briefing_data_as_of`; provenance dates were verified directly in briefing payloads instead.

Outcome memory was read with the visibility cutoff 2026-09-14; no local resolved records were available for any ticker. No proven trading edge or historical win probability is claimed.

## Results

The confidence score is capped by deterministic analyst consensus. Directional convergence measures agreement, not accuracy; neutral reports lower it. A directional narrative may remain non-actionable if confidence or agreement is too weak. Entry levels are research references, not orders.

| Market | Ticker | Name | Snapshot price | Data as of | Signal | Conviction | Convergence | Levels generated |
|---|---|---|---:|---|---|---:|---:|---|
| MY | [1155](1155/briefing.json) | MAYBANK | 10.38 | 2026-09-11 | neutral | +0.0000 | 0.2727 | No |
| MY | [5258](5258/briefing.json) | BIMB | 2.09 | 2026-09-11 | neutral | +0.0000 | 0.0000 | No |
| MY | [5398](5398/briefing.json) | GAMUDA | 4.84 | 2026-09-14 | neutral | +0.0000 | 0.2727 | No |
| MY | [4197](4197/briefing.json) | SIME | 2.55 | 2026-09-14 | buy | +0.3500 | 0.5455 | Yes |
| MY | [5151](5151/briefing.json) | HEXTAR | 0.77 | 2026-09-14 | sell | -0.5000 | 0.5000 | No |
| MY | [0215](0215/briefing.json) | SLVEST | 3.30 | 2026-09-14 | neutral | +0.0000 | 0.2727 | No |
| MY | [5225](5225/briefing.json) | IHH | 7.77 | 2026-09-14 | neutral | +0.0000 | 0.2727 | No |
| MY | [5296](5296/briefing.json) | MRDIY | 1.29 | 2026-09-14 | neutral | +0.0000 | 0.5455 | No |
| MY | [0097](0097/briefing.json) | VITROX | 9.22 | 2026-09-14 | neutral | +0.0000 | 0.3000 | No |
| MY | [0128](0128/briefing.json) | FRONTKN | 4.83 | 2026-09-14 | neutral | +0.0000 | 0.3000 | No |
| MY | [0166](0166/briefing.json) | INARI | 2.58 | 2026-09-14 | sell | -0.4500 | 0.5455 | No |
| MY | [5005](5005/briefing.json) | UNISEM | 4.20 | 2026-09-14 | sell | -0.2000 | 0.2000 | No |
| MY | [5249](5249/briefing.json) | IOIPG | 3.68 | 2026-09-14 | neutral | +0.0000 | 0.3000 | No |
| MY | [6947](6947/briefing.json) | CDB | 2.72 | 2026-09-11 | neutral | +0.0000 | 0.2727 | No |
| MY | [5126](5126/briefing.json) | SOP | 6.17 | 2026-09-14 | neutral | +0.0000 | 0.5455 | No |
| US | [GOOGL](GOOGL/briefing.json) | Alphabet Inc. | 338.50 | 2026-09-11 | neutral | +0.0000 | 0.0000 | No |
| US | [MSFT](MSFT/briefing.json) | Microsoft Corporation | 495.63 | 2026-09-11 | buy | +0.4000 | 0.5455 | Yes |
| US | [NVDA](NVDA/briefing.json) | NVIDIA Corporation | 218.29 | 2026-09-11 | neutral | +0.0000 | 0.3000 | No |
| US | [AAPL](AAPL/briefing.json) | Apple Inc. | 332.27 | 2026-09-11 | neutral | +0.0000 | 0.2727 | No |
| US | [AMZN](AMZN/briefing.json) | Amazon.com, Inc. | 256.78 | 2026-09-11 | neutral | +0.0000 | 0.0000 | No |
| US | [META](META/briefing.json) | Meta Platforms, Inc. | 648.03 | 2026-09-11 | neutral | +0.0000 | 0.2727 | No |
| US | [TSLA](TSLA/briefing.json) | Tesla, Inc. | 365.44 | 2026-09-11 | sell | -0.5000 | 0.5455 | No |
| US | [AVGO](AVGO/briefing.json) | Broadcom Inc. | 361.99 | 2026-09-11 | neutral | +0.0000 | 0.3000 | No |
| US | [UNH](UNH/briefing.json) | UnitedHealth Group Incorporated | 379.09 | 2026-09-11 | neutral | +0.0000 | 0.2727 | No |
| US | [V](V/briefing.json) | Visa Inc. | 370.45 | 2026-09-11 | neutral | +0.0000 | 0.2727 | No |
| US | [TSM](TSM/briefing.json) | Taiwan Semiconductor Manufactur | 433.24 | 2026-09-11 | buy | +0.4500 | 0.6000 | Yes |
| US | [RKLB](RKLB/briefing.json) | Rocket Lab Corporation | 62.95 | 2026-09-11 | sell | -0.2000 | 0.5000 | No |
| US | [APP](APP/briefing.json) | Applovin Corporation | 323.96 | 2026-09-11 | neutral | +0.0000 | 0.0000 | No |
| US | [ORCL](ORCL/briefing.json) | Oracle Corporation | 150.28 | 2026-09-11 | sell | -0.5455 | 0.5455 | No |
| US | [NFLX](NFLX/briefing.json) | Netflix, Inc. | 77.40 | 2026-09-11 | neutral | +0.0000 | 0.2000 | No |
| US | [SOFI](SOFI/briefing.json) | SoFi Technologies, Inc. | 17.32 | 2026-09-11 | neutral | +0.0000 | 0.3000 | No |
| US | [SMR](SMR/briefing.json) | NuScale Power Corporation | 8.61 | 2026-09-11 | sell | -0.4500 | 0.5000 | No |
| US | [ONDS](ONDS/briefing.json) | Ondas Inc | 7.23 | 2026-09-11 | sell | -0.2000 | 0.5000 | No |
| MY | [5263](5263/briefing.json) | SUNCON | 7.15 | 2026-09-14 | neutral | +0.0000 | 0.2727 | No |
| MY | [5347](5347/briefing.json) | TENAGA | 13.60 | 2026-09-11 | neutral | +0.0000 | 0.0000 | No |

## Data limits

- MY September14 observations may be intraday, even when the volume heuristic accepts them; some tickers retain September11. US bars end September11, appropriate before the September14 US session.
- Several MY recent zero-volume rows remain in input and affect indicators; no missing/nonpositive OHLC was found in the inspected last25 bars.
- Provider news extraction returned blank objects for all35; sentiment reports instead cite individually dated web sources. Coverage is selective rather than exhaustive. Relative recommendation buckets are not individually dated broker revisions.
- Financial statement periods, normalized/TTM basis and forward-estimate dates may be missing. Quoted P/E and raw income may refer to different bases. TSM ADR/reporting-currency uncertainty is explicitly flagged.
- The risk module's 2-sigma drawdown heuristic is not a guaranteed worst-case loss bound. Its wording should not be interpreted as a tail-risk limit.
- Actual holdings and personal risk capacity were unavailable; this report does not calculate portfolio suitability or allocation.

## Stock-specific adjudication

### 1155 — MAYBANK

Income resilience is established, but bank-specific capital and payout evidence is missing. Neither side establishes an immediate valuation advantage.

### 5258 — BIMB

Low valuation and weak growth coexist with higher provisioning. The debate turns on capital and payout information neither side supplies.

### 5398 — GAMUDA

RM61.6bn of orders supports demand but not cash returns at 28.47x earnings. Both arguments depend on an unprovided project-conversion bridge.

### 4197 — SIME

Core profit growth of 32.6%, positive FCF and a single-digit quoted multiple give the bull concrete support beyond a dividend narrative. Thin margins temper conviction but do not erase the normalized core improvement already reported.

### 5151 — HEXTAR

High leverage, 38.50x quoted earnings and weakening quarterly conversion outweigh sales growth. The bull concedes recovery remains a prerequisite rather than established evidence.

### 0215 — SLVEST

Profit and backlog establish progress, but diluted per-share and cash returns are unresolved. Neither side supplies enough to adjudicate fair value at the growth multiple.

### 5225 — IHH

Reported growth supports quality while valuation requires organic and acquisition returns neither advocate quantifies. The bearish chart reinforces patience without proving intrinsic overvaluation.

### 5296 — MRDIY

The dated 15.2% quarterly profit decline outweighs older cash-flow support for immediate buying. Restraint wins; the evidence does not establish permanent impairment or an outright short thesis.

### 0097 — VITROX

Extraordinary growth prevents a confident sell ruling, but valuation-basis and cash-conversion gaps defeat an immediate buy at 83.82x. The bear carries the entry argument, not a claim that operations are deteriorating.

### 0128 — FRONTKN

Quality and cash conversion are well supported, but neither side values the growth needed for 43.91x earnings. In-line H1 results cannot resolve that dispute.

### 0166 — INARI

RF demand weakness is independent of the fire provision, while valuation embeds a substantial recovery. Removing an exceptional charge does not establish that recovery.

### 5005 — UNISEM

A single quarterly rebound does not offset H1 losses, negative FCF and 105x quoted earnings. Current evidence makes recovery a required assumption rather than a margin of safety.

### 5249 — IOIPG

Accounting and corporate-action uncertainty prevent a reliable valuation judgment. Both advocates depend on unquantified recurring income and monetization proceeds.

### 6947 — CDB

Maintained H1 profit and cash generation support resilience, but network funding and payout coverage remain unquantified. Neither establishes a clear return advantage.

### 5126 — SOP

Low leverage and earnings growth establish a serious value candidate, but commodity normalization is unresolved. Near-high momentum cannot be treated as a dip opportunity.

### GOOGL — Alphabet Inc.

The operating franchise is strong, but the large investment gain and incompatible earnings bases prevent judging apparent cheapness. Both sides lack a normalized valuation bridge.

### MSFT — Microsoft Corporation

Adjusted EPS growth of 23% excluding investment effects gives the bull actual earnings evidence alongside high margins and low leverage. The bear identifies unresolved incremental capex returns but does not overturn the established quality-growth case.

### NVDA — NVIDIA Corporation

Demand growth is exceptionally strong, but incompatible earnings bases block a fair-value ruling. Neither side establishes whether the forward multiple properly prices the growth.

### AAPL — Apple Inc.

Broad growth supports durability while the 38.15x multiple requires a longer growth bridge. Both cases leave the justified premium unresolved.

### AMZN — Amazon.com, Inc.

Dated negative FCF and the enlarged investment plan defeat an immediate cash-return argument. Demand remains strong, so the ruling is restraint rather than business impairment.

### META — Meta Platforms, Inc.

Current costs and earnings conversion weigh more heavily than older cash-flow quality for entry. The bull offers future productivity but not evidence that it has arrived.

### TSLA — Tesla, Inc.

The gap between 332.22x earnings and current operating economics is not filled by quantified future cash flows. The bull concedes its remaining case is speculative optionality.

### AVGO — Broadcom Inc.

AI growth and cash generation are strong but earnings-basis discrepancies prevent adjudicating the valuation. Neither establishes a reliable forward-return denominator.

### UNH — UnitedHealth Group Incorporated

Raised guidance is positive evidence but claims and reserves needed to validate it are absent. Neither side can establish the quality of the recovery from industrial ratios.

### V — Visa Inc.

Growth and cash conversion support a durable network, but neither values the premium relative to future transaction economics. Technical recovery does not resolve fair value.

### TSM — Taiwan Semiconductor Manufactur

Recent revenue growth of 53.3% and constructive price/momentum evidence give the bull the clearest combined demand-and-trend support. This is a conditional directional ruling, not a cross-currency fair-value claim.

### RKLB — Rocket Lab Corporation

Commercial momentum does not yet fund losses or establish profitable backlog conversion. The bear wins on valuation and financing evidence, without asserting imminent distress.

### APP — Applovin Corporation

Strong growth and cash generation coexist with leverage and inconsistent earnings bases. Neither resolves whether the current price already compensates for expectations.

### ORCL — Oracle Corporation

Negative FCF and debt far above equity make funding the decisive issue. Cloud demand validates spending opportunity but does not establish funded shareholder returns.

### NFLX — Netflix, Inc.

Business growth and cash generation are real, but guidance disappointment and earnings-basis mismatch leave entry value unresolved. Both sides still depend on content-return normalization.

### SOFI — SoFi Technologies, Inc.

Platform growth is established while credit-adjusted per-share returns are not. Neither side supplies the banking evidence required for a directional valuation judgment.

### SMR — NuScale Power Corporation

Reported liquidity reduces immediate funding concern but does not establish commercial deployment economics at the valuation. The bear wins on execution and cash returns, not an unsupported insolvency claim.

### ONDS — Ondas Inc

Same-portfolio growth is material, but profitability and financing through deployment remain unestablished. The bull does not quantify returns sufficient to outweigh losses and valuation.

### 5263 — SUNCON

The bear wins the immediate-entry argument because future margins and exceptional cash flow remain unreconciled at 22.34x. This is not evidence of a current earnings collapse.

### 5347 — TENAGA

FX and funding bridges are absent, so neither can establish recurring shareholder cash economics. Stable dividends and revenue do not resolve the dispute.

## Artifacts

Each ticker folder contains `analyst_reports.json`, `debate_result.json`, `research_verdict.json`, and `briefing.json`. Canonical copies are also updated in `../../../data/<TICKER>/`. `summary.json` and `run-status.json` provide machine-readable totals. Snapshot hashes and analysis dates are embedded in each briefing. Sources are embedded in the sentiment headlines and supporting analyst reports.

Macro source facts: [Fed July29 statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm) and [BNM September3 statement](https://www.bnm.gov.my/-/monetary-policy-statement-03092026). No current FX forecast was assumed.
