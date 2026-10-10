# Pipeline diagnostic experiments — Implementation plan

**Author:** Codex **Date:** 2026-10-09 **Status:** Offline diagnostics complete; forward rules prepared, collection inactive

## Goal

Explain the frozen October panel's refusal and capital-deployment gap, and measure
whether the existing FT or AI labels add value to the fixed momentum allocator.
Prepare an explicit forward protocol without turning inspected historical returns
into validation evidence.

## Approach

Add `scripts/research_pipeline_gaps.py` as an offline adapter over the existing
portfolio, non-overlap selection, cross-sectional allocator and signal-ablation
modules. Freeze file and code hashes before calculating results. Keep the 96-trial
full-panel accounting separate from the deterministic 72-trial episode comparison.
No model calls, data refresh, production thresholds, API or database changes.

## Steps

1. Partition raw forecast versus executed signal and summarize overlapping gate
   reasons; replay raw buys as an explicitly unsafe research counterfactual.
2. Compare fixed 12-month/top-three allocation, FT-only, AI-only and the three
   filtered allocator arms on identical non-overlapping windows at 0/10/20bps.
3. Record paired block intervals, effective sample size, full within-comparison
   search counts and deterministic order checks in a fresh report directory.
4. Specify prospective v2 dates, fixed arms, evidence/model provenance and gates;
   preserve the already frozen October 7 cohort and its November 7 maturity gate.
5. Link the new plan and report from the existing long-hold optimization owner.

## Verification

Use synthetic regression tests for the exact gap decomposition, mutually exclusive
refusal partitions and the prevention of outcome-based trial selection. Recompute
episode returns independently, reverse trial input order, and compare all input
hashes after the run. Run the focused tests and Ruff; inspect the new contract map.

## Risks / unresolved inputs

Counterfactual gains do not authorize bypassing guards. Nine episodes cannot
establish an edge. Existing cost assumptions, survivor-selected names and incomplete
historical evidence remain disclosed. Forward activation requires exact model/prompt
identities and sealed usable inputs; promotion additionally requires verified return
data and calibrated costs. Their absence is a blocked gate, never a fabricated value.

## Result

All five offline steps completed. See
[the diagnostic report](../../reports/analysis/2026-10-09-pipeline-gap-diagnostics-final/README.md)
and [the prepared forward v2 specification](pipeline-forward-validation-v2.md).
The preserved first attempt used an ambiguous `directional_executed` label for
guard-approved sell calls; a fresh final run distinguishes long-only sell skips.
The naming correction did not alter strategy returns. No actual forward collection
or nine-arm scheduler is claimed by this completed diagnostic plan.
