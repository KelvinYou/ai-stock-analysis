export type AllocationArm = {
  id: string; label: string; status: "available" | "not_tested";
  net_return: number | null; drawdown: number | null; mean_exposure: number | null;
};
export type AllocationExperiment = {
  id: string; label: string; kind: "monthly" | "episodes"; cost_bps: number; excess_vs_hold: number;
  universe: string[]; start: string; end: string; periods: number; effective_n: number;
  drawdown_basis: string; price_basis: string; fee_basis: string;
  reference_label: string; ci_reference: string; ci: [number, number] | null;
  curve: {date: string; allocator: number; reference: number; log_excess: number | null}[];
  last_selection: {as_of: string; tickers: string[]}; arms: AllocationArm[];
  notes: string[]; source_sha256: string;
};
export type AllocationResearch = {
  robustness: {rolling_wins: number; rolling_windows: number; rolling_min: number; omitted_months: number; omitted_allocator: number; omitted_hold: number};
  version: 1; generated_at_utc: string; default_id: string;
  experiments: AllocationExperiment[]; current_plan: {status: "unavailable"; reason: string};
  reliability_status: string; promotion_ready: false; limitations: string[];
};
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const nullable = (v: unknown) => v === null || finite(v);
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === "string");
const date = (v: unknown) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
export function isAllocationResearch(v: unknown): v is AllocationResearch {
  if (!record(v) || v.version !== 1 || v.promotion_ready !== false || typeof v.generated_at_utc !== "string" || !Number.isFinite(Date.parse(v.generated_at_utc)) || typeof v.default_id !== "string" || typeof v.reliability_status !== "string" || !strings(v.limitations) || !record(v.current_plan) || v.current_plan.status !== "unavailable" || typeof v.current_plan.reason !== "string" || !Array.isArray(v.experiments) || !v.experiments.length) return false;
  const robustness = v.robustness;
  if (!record(robustness) || !["rolling_wins","rolling_windows","rolling_min","omitted_months","omitted_allocator","omitted_hold"].every(k => finite(robustness[k]))) return false;
  const valid = v.experiments.every(e => {
    if (!record(e) || typeof e.id !== "string" || !/^[a-z0-9-]+$/.test(e.id)) return false;
    if (!record(e) || !["monthly", "episodes"].includes(String(e.kind)) || !["id", "label", "drawdown_basis", "price_basis", "fee_basis", "reference_label", "ci_reference"].every(k => typeof e[k] === "string") || typeof e.source_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(e.source_sha256) || !finite(e.excess_vs_hold) || !finite(e.cost_bps) || e.cost_bps < 0 || !finite(e.periods) || !Number.isInteger(e.periods) || e.periods < 1 || !finite(e.effective_n) || e.effective_n < 0 || !date(e.start) || !date(e.end) || !strings(e.universe) || e.universe.length < 3 || !strings(e.notes)) return false;
    if (!(e.ci === null || (Array.isArray(e.ci) && e.ci.length === 2 && e.ci.every(finite) && e.ci[0] <= e.ci[1]))) return false;
    if (!record(e.last_selection) || !date(e.last_selection.as_of) || !strings(e.last_selection.tickers) || !e.last_selection.tickers.every(t => (e.universe as string[]).includes(t))) return false;
    if (!Array.isArray(e.curve) || e.curve.length !== e.periods + 1 || !e.curve.every(p => record(p) && date(p.date) && finite(p.allocator) && p.allocator > 0 && finite(p.reference) && p.reference > 0 && nullable(p.log_excess))) return false;
    if (!Array.isArray(e.arms) || !e.arms.length || !e.arms.every(a => record(a) && typeof a.id === "string" && typeof a.label === "string" && ["available", "not_tested"].includes(String(a.status)) && nullable(a.net_return) && nullable(a.drawdown) && nullable(a.mean_exposure) && (a.status !== "not_tested" || [a.net_return,a.drawdown,a.mean_exposure].every(x => x === null)))) return false;
    const arms = e.arms as Record<string, unknown>[];
    return new Set(arms.map(a => a.id)).size === arms.length && ["allocator_only", "continuous_strict_hold", "ai_only", "allocator_plus_ai"].every(id => arms.some(a => a.id === id)) && arms.every(a => (a.status !== "available" || finite(a.net_return)) && (a.mean_exposure === null || (finite(a.mean_exposure) && a.mean_exposure >= 0 && a.mean_exposure <= 1)));
  });
  return valid && new Set(v.experiments.map(e => e.id)).size === v.experiments.length && v.experiments.some(e => e.id === v.default_id);
}
