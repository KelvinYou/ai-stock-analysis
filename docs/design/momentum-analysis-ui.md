# Momentum allocation analysis UI — Design-Lite

**Author:** Codex **Status:** V1 implemented; V2 deferred **Updated:** 2026-10-09

## Implemented V1

`/allocation` displays six frozen experiments: original eight-stock adjusted monthly history at 20/40/80 bps per side, and the sealed nine-episode diagnostic at 0/10/20 bps. Other universes and the overlapping 96-trial diagnostic are not in this initial selector. AI arms are explicitly not tested in monthly history; genuine zero return/exposure is retained in the episode experiments. The episode chart and paired interval use scheduled passive, while the headline cumulative difference uses continuous hold and is labeled in percentage points.

The page includes cumulative wealth, paired log excess, confidence interval and effective count, separate rolling/concentration diagnostics, last historical selection and an evidence download. Current snapshot is explicitly unavailable until V2 supplies a pinned same-session plan; complete rankings and ticker-level veto traces belong to V2.

Refresh the sanitized deployment asset from the repository root:

```sh
.venv/bin/python scripts/export_allocation_research.py
cd web
node scripts/check-allocation.cjs
npm run typecheck
npm run build
```

`config/allocation_research.json` owns the allowed source paths and SHA-256 identities. Refreshing fails if an approved source changed. Review the new source before updating its manifest hash. Only `web/data/allocation-research.json` and its checksum are packaged for the page and evidence route. Raw research/provider payloads are not serialized. Missing, corrupt or structurally invalid assets render an unavailable state. Python exporter tests use synthetic fixtures; `web/scripts/check-allocation.cjs` checks the actual generated boundary and rejects malformed units/states/identities.

## Outcome and scope

Add `/allocation` to the existing stock-analysis web app so readers can distinguish the deterministic momentum allocator, AI signals and their hybrid. The current Screener is ticker-oriented; About describes the allocator, but no page shows its rankings, portfolio weights or validation evidence. Observed allocator gains cannot be presented as AI gains, and a research target weight is not a personal holding or trade instruction.

V1 is a read-only research view of approved historical experiments. V2 connects an explicitly pinned same-session `PortfolioPlan`. No model execution, strategy parameter optimization, broker execution, actual personal holdings, future-cohort activation or database migration is included.

## Page composition

| Section | Reader question | Content |
|---|---|---|
| Header | What am I inspecting? | Allocation; experiment name, historical/forward scope, universe, decision/evaluation dates, 12-month/Top-3 rule, cost per side, price basis and validation status |
| Research / Current snapshot tabs | Am I looking at outcomes or a current plan? | Research opens by default; current snapshot has a separate identity and unavailable state until a valid pinned plan exists |
| Comparison | Which component contributes? | Allocator, strict hold, AI-only and allocator+AI rows; net return, excess, exposure/trade count when available and drawdown basis |
| Return history | When did the advantage arise? | Allocator and strict hold monthly cumulative wealth, rebased to 100; paired monthly excess bars; shared hover dates |
| Reliability | How much can I trust it? | Paired interval crossing zero, period/effective sample count, rolling-window dependence, best-month removal sensitivity, cost/source limitations |
| Current ranking and weights | What did the fixed rule select? | All eligible names ranked by 12-month return; selected Top 3, one-third target sleeves, selected strategy cash weight and as-of date |
| Filter explanation | Why does the hybrid differ? | Compare allocator-only, allocator+AI and allocator+FT views; ticker-level final labels, rejection reasons and rejected sleeve cash |
| Evidence details | Can I reproduce it? | Protocol ID/hash, approved report link, cost status, calendar and source availability; supporting details collapsed |

Do not place an oversized green historical return headline above scope/uncertainty. Lead with a neutral status such as `Historical advantage · reliability unconfirmed`. Positive returns use normal directional colors; validation status uses a separate explicit label. Display the confidence interval with its unit and benchmark: monthly mean log excess, not a cumulative-return interval.

## Historical experiment boundaries

Use distinct experiment groups, never one combined ranking:

1. **Monthly long-history comparison:** three previously inspected universes, original/current price vintages and approved cost cases. Allocator/hold are available; AI/hybrid are unavailable for this protocol.
2. **Sealed nine-episode diagnostic:** eight names, non-overlapping approximately 30-day windows and multiplicative fees. Allocator, AI-only and hybrid outcomes are available. Clearly label endpoint-only drawdown where relevant.
3. **Full 96-trial AI portfolio diagnostic:** different sizing and overlapping trial windows; daily drawdown and continuous hold. It is not a substitute for either experiment above.

The selector changes whole experiment identities, not independently mixable rows. A long-history tab must label AI/hybrid `Not tested in this experiment`; the nine-episode tab may show all relevant arms. Cost cases remain frozen cases from each protocol: extended history has 20/40/80bps, older episode experiments have 0/10/20bps. No slider silently interpolates costs or re-runs a parameter search.

V1 charts use actual period-log compounded monthly returns, marked `Monthly observations`. Existing JSON does not contain the historical daily equity path, although its max-drawdown statistic was computed from daily closes. Never interpolate monthly observations and call them daily equity. The nine-arm forward comparer already returns daily curves and can be connected separately once actual mature comparison artifacts exist. Immature/unactivated cohorts have no performance chart.

## Existing owners and new data flow

```text
Python backtest/cohort artifacts [EXISTING metric owners]
    -> allowlisted Python research-view exporter [NEW]
    -> versioned, sanitized research JSON [NEW]
    -> server-only Next.js research loader [NEW]
    -> /allocation page and client charts [NEW]

Pinned same-session PortfolioPlan [EXISTING]
    -> server-only adapter [V2 NEW]
    -> current snapshot section
```

Python remains the only owner of compounding, ranking, fees, weights, intervals, curve normalization and validation facts. React formats and plots values. Export only approved public market research; do not export raw model/provider payloads, API secrets, filesystem paths, private finance records or personal account data. A server-only loader does not make serialized page props private; sanitize before rendering.

### V1 display contract

Add a Python-exported `AllocationResearchView` with `version: 1`, `generated_at_utc`, an experiment catalog and an explicit default experiment ID. Proposed per-experiment shape:

```json
{
  "id": "primary8-current-20bps-monthly",
  "scope": "historical_research",
  "protocol_id": "momentum-validation-extended",
  "universe": ["AVGO", "COST", "MSFT", "NVDA", "ORCL", "TSM", "UNH", "V"],
  "cost": {"bps_per_side": 20, "status": "research_assumption"},
  "observation_basis": "monthly",
  "arms": [
    {"id": "allocator_only", "status": "available"},
    {"id": "continuous_strict_hold", "status": "available"},
    {"id": "ai_only", "status": "not_tested_in_protocol"},
    {"id": "allocator_plus_ai", "status": "not_tested_in_protocol"}
  ],
  "reliability": {"status": "unconfirmed", "promotion_ready": false},
  "current_plan": {"status": "unavailable", "reason": "no_pinned_same_session_plan"}
}
```

This abbreviated example shows semantics, not a complete implemented schema. The full typed exporter must include date range, period/effective counts, metrics, metric units, paired CI benchmark/basis, curves, price/drawdown basis and source identity. In Python fractions are retained as fractions; TypeScript formats percentages exactly once. Null/unavailable metrics remain distinct from genuine zero return, zero exposure and zero trades. Gate facts are sourced, not inferred from a frontend return threshold.

Export approved reports through a fixed manifest of experiment IDs and source hashes. Do not accept user-supplied file paths or load an entire reports directory recursively. Place only the sanitized generated view in the application deployment assets; the source reports remain under `reports/analysis/`. Recommended generated asset: `web/data/allocation-research.json`, loaded server-side. Missing/invalid assets produce an explicit empty/error state, never hardcoded sample performance.

No new backend endpoint or database migration is required for V1. The new Python/JSON/TypeScript contract needs a focused contract fixture and export validation. Existing ticker API consumers remain unchanged.

### V2 current plan boundary

`POST /api/v1/portfolio-plans` already accepts 3–50 completed run UUIDs and returns `PortfolioPlan`: momentum rankings/scores, all nine weight views, cash, input/run identity and signal trace. Reuse it through the server-side API adapter; never expose the bearer token. Do not generate new LLM analyses on page load.

The existing ticker summary interface does not expose a selectable synchronized run set to the frontend. Therefore add an explicit approved run-set manifest or a backend resolver before wiring current plans. Do not combine independently latest per-ticker files or assume starred names form a valid same-date research universe. Local completed snapshots are process-lifetime state, so persisted plans must be exported or resolved from verified completed cloud runs. A snapshot label means `Target weights as of <date>`, not `Current holdings`.

Expose AI veto explanations from `signal_trace` with understandable labels (for example `Evidence unavailable`, `Consensus below execution threshold`); raw hashes and reason codes belong in evidence details. A neutral/missing input is not automatically a sell. For rejected sleeves, preserve their one-third slot as cash; never renormalize survivors to 100%.

## Failure states and controls

| State | UI behavior |
|---|---|
| No approved historical export | Explain that no research artifact is available; do not render zero-return cards |
| Unknown version, malformed fields or stale manifest hash | Data error; retain no misleading metrics |
| AI/hybrid absent in a protocol | Not tested, distinct from available zero-trade result |
| Current plan unavailable, mixed dates/markets or missing history | Explain why rankings/weights are unavailable; no fabricated Top 3 |
| HTTP 401/409/503 in V2 | Authentication/input/service message; no fallback to arbitrary latest files |
| Zero AI long exposure | Show cash weight and gate explanation, with zero-trade result |
| Forward preparation only / immature sample | Prepared / awaiting maturity; no estimated realized returns |
| Different drawdown or fee bases | Keep rows within their experiment and label bases |

Use approved experiment and cost selectors only. Parameter tuning, return-maximizing default selection and Buy/Apply portfolio controls are outside this view.

## Frontend implementation map

- `web/app/allocation/page.tsx`: server-rendered page, independent metadata and explicit data states.
- `web/lib/allocation-data.ts` and a typed display model: sanitized server-only loader and structural validation.
- `web/components/allocation/`: comparison table, wealth/excess charts, reliability panel, snapshot ranking and filter explanation.
- `web/components/layout/sidebar.tsx`: Allocation navigation item.
- `web/components/layout/topbar.tsx`: explicit Allocation breadcrumb; otherwise the current fallback interprets the route as a ticker.
- `web/app/about/page.tsx`: link to Allocation, retaining explanation of the actual pipeline.
- Python exporter, manifest and a compact fixture: source-to-display parity; avoid hardcoded repeated performance numbers in JSX.

Reuse current typography, semantic color tokens, `SectionCard`, tabs and Recharts. Do not reskin the screener or ticker briefing. Desktop comparison tables share aligned columns; on mobile use a labeled scroll region or compact strategy rows. Charts need textual summaries, readable labels, keyboard-accessible controls and theme-aware colors. A prototype may use labeled synthetic data; the delivered data view must use approved exports.

## Implementation slices and acceptance

1. Export the primary extended monthly experiment and nine-episode diagnostic with explicit identities and missing-arm states. Validate the JSON contract, source hashes, units and all displayed values against source artifacts.
2. Add `/allocation`, navigation and breadcrumbs. Show comparison, monthly curves and reliability; source links must be safe and resolvable in the chosen deployment.
3. Add current plan data only after an explicit synchronized run resolver/manifest exists. Validate the existing API response, cash weights and reason semantics. Do not show stale plans as live.
4. Check Python export/contract tests, web typecheck, and actual desktop/mobile light/dark renders. Verify empty, unavailable, zero-trade, interval-crossing-zero and absent-hybrid cases. Ensure auth secrets and private holdings are absent from generated JSON and client props.

## Trade-offs and decisions

A dedicated Allocation page fits the portfolio-wide question and avoids overloading individual ticker cards. Historical research first is the smallest useful slice because approved evidence exists today while current synchronized plan selection is not yet wired. Keep the current page data-first rather than an LLM-written narrative: explanation follows reproducible metrics and fixed rules.

Proposed defaults: original eight-name research universe, primary extended 20bps case, research tab first, current snapshot unavailable until genuinely supplied. Broader universes remain distinct sensitivity experiments, not automatic winners. No user agreement is inferred for deployment or live trading.

Open product decisions for implementation: whether to include the eleven/five-name sensitivity catalog in V1 (proposal: collapsed comparison); where sanitized research assets are deployed (proposal: generated server-side asset); whether V2 run-set selection is operator-managed or a new authenticated resolver (proposal: explicit manifest first). None blocks writing this proposal.
